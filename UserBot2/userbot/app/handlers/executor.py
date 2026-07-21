"""
Task Executor with Phase 2 Service Integration
Handles send_message, forward_message, safe_gcast with all safety features.
Multi-Worker Support: Uses Round-Robin and Failover.
"""
import asyncio
import random
import json
import os
import time
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from app.utils.logger import get_logger
from app.guards.rate_limit import RateLimiter
from app.guards.anti_spam import AntiSpamGuard
from app.config import config
from app.services.warmup import WarmupEngine
from app.services.risk_control import RiskControl
from app.services.delivery_tracker import DeliveryTracker
from app.services.ai_rewriter import get_rewriter
from app.client import TelegramBotClient

logger = get_logger(__name__)

class TaskExecutor:
    def __init__(self, worker_clients: list[TelegramClient]):
        self.worker_clients = worker_clients
        self.resting_workers = {} # {session_id: wakeup_timestamp}
        self.current_worker_idx = 0

    def get_session_id(self, client: TelegramClient) -> str:
        """Extracts session name from the client's session file."""
        if hasattr(client.session, 'filename') and client.session.filename:
            basename = os.path.basename(client.session.filename)
            return basename.replace(".session", "")
        return "unknown_worker"

    def get_next_active_worker(self) -> TelegramClient:
        """Returns the next available worker using round-robin. Skips resting workers."""
        if not self.worker_clients:
            return None
            
        now = time.time()
        start_idx = self.current_worker_idx
        
        while True:
            client = self.worker_clients[self.current_worker_idx]
            session_id = self.get_session_id(client)
            
            self.current_worker_idx = (self.current_worker_idx + 1) % len(self.worker_clients)
            
            # Check if resting
            if session_id in self.resting_workers:
                if now < self.resting_workers[session_id]:
                    # Still resting
                    if self.current_worker_idx == start_idx:
                        # Looped through all and all are resting
                        return None
                    continue
                else:
                    # Wake up
                    del self.resting_workers[session_id]
            
            return client

    def mark_worker_resting(self, client: TelegramClient, seconds: int):
        """Marks a worker to rest for X seconds (e.g. FloodWait)."""
        session_id = self.get_session_id(client)
        self.resting_workers[session_id] = time.time() + seconds
        logger.warning(f"Worker {session_id} is resting for {seconds}s")

    async def execute(self, task: dict):
        """Dispatches the task to the appropriate handler."""
        action = task.get("action")
        task_id = task.get("task_id")
        
        logger.info("Processing task", task_id=task_id, action=action)
        
        try:
            if action == "forward_message":
                await self.handle_forward(task)
            elif action == "send_message":
                await self.handle_send(task)
            elif action == "safe_gcast":
                await self.handle_gcast(task)
            elif action == "spam":
                await self.handle_spam(task)
            else:
                logger.warning("Unknown action", action=action)
        except Exception as e:
            logger.error("Task execution failed", task_id=task_id, error=str(e))

    async def _sleep_random(self, range_seconds):
        if not range_seconds:
            return
        
        multiplier = await RiskControl.get_delay_multiplier()
        base_sleep = random.uniform(range_seconds[0], range_seconds[1])
        sleep_time = base_sleep * multiplier
        
        logger.debug("Sleeping", seconds=sleep_time, multiplier=multiplier)
        await asyncio.sleep(sleep_time)

    async def _check_warmup(self, session_id: str) -> bool:
        """Check warm-up eligibility for a specific worker."""
        if not config.WARMUP_ENABLED:
            return True
        
        can_send, reason = await WarmupEngine.can_send(session_id)
        if not can_send:
            logger.warning(f"Warm-up check failed for {session_id}", reason=reason)
        return can_send

    async def handle_forward(self, task):
        source = task.get("source_chat_id")
        target = task.get("target_chat_id")
        msg_id = task.get("message_id")
        delay = task.get("delay_range", [2, 5])
        
        worker = self.get_next_active_worker()
        if not worker:
            logger.error("No active workers available for forward")
            return

        if not await RateLimiter.check_and_increment("forward", 100, 3600):
            logger.error("Rate limit hit for forward")
            return

        await self._sleep_random(delay)
        try:
            await worker.forward_messages(target, msg_id, source)
            logger.info("Message forwarded", source=source, target=target, worker=self.get_session_id(worker))
        except FloodWaitError as e:
            self.mark_worker_resting(worker, e.seconds)
            await RiskControl.record_flood_error()

    async def handle_send(self, task):
        target = task.get("target_chat_id")
        message = task.get("message")
        delay = task.get("delay_range", [2, 5])
        
        worker = self.get_next_active_worker()
        if not worker:
            logger.error("No active workers available for send")
            return

        if not await RateLimiter.check_and_increment("send", 100, 3600):
            return

        await self._sleep_random(delay)
        try:
            await worker.send_message(target, message)
            session_id = self.get_session_id(worker)
            if config.WARMUP_ENABLED:
                await WarmupEngine.increment_count(session_id)
            logger.info("Message sent", target=target, worker=session_id)
        except FloodWaitError as e:
            self.mark_worker_resting(worker, e.seconds)
            await RiskControl.record_flood_error()

    async def handle_gcast(self, task):
        """
        Executes a safe broadcast with all Phase 2 features and Multi-Worker failover.
        """
        task_id = task.get("task_id", "unknown")
        message = task.get("message")
        raw_recipients = task.get("recipients", [])
        limits = task.get("limits", {})
        delay_range = task.get("delay_range", [20, 90])
        origin_chat_id = task.get("origin_chat_id")
        origin_message_id = task.get("origin_message_id")
        resume_from = task.get("resume_from", 0)
        
        hourly_limit = limits.get("per_hour", 5)
        daily_limit = limits.get("per_day", 20)
        
        valid_ids = AntiSpamGuard.validate_gcast_recipients(raw_recipients)
        
        await DeliveryTracker.initialize(task_id, len(valid_ids))
        
        if resume_from == 0:
            resume_from = await DeliveryTracker.get_resume_index(task_id)
        
        rewriter = get_rewriter()
        sent_count = 0
        failed_count = 0
        should_complete = True
        
        for idx, user_id in enumerate(valid_ids):
            if idx < resume_from:
                continue
            
            # 1. Get active worker (Failover / Round Robin)
            worker = self.get_next_active_worker()
            if not worker:
                await DeliveryTracker.mark_paused(task_id, "All workers are resting/banned")
                should_complete = False
                break
                
            session_id = self.get_session_id(worker)
            
            # 2. Warm-up Check for this specific worker
            if not await self._check_warmup(session_id):
                self.mark_worker_resting(worker, 3600) # Rest for 1h if warmup limits hit
                # Retry same user with next worker on next loop iteration?
                # For simplicity, we'll mark failed for this specific target, or we can use a retry loop.
                # Let's use a retry loop for this target
            
            # For robustness, we can try multiple workers for the same user_id if one fails
            max_retries = len(self.worker_clients)
            success = False
            
            for attempt in range(max_retries):
                if attempt > 0:
                    worker = self.get_next_active_worker()
                    if not worker:
                        break
                    session_id = self.get_session_id(worker)
                
                # 3. Global Rate Limit Check
                if not await RateLimiter.check_global_gcast_limit(daily_limit, hourly_limit):
                    logger.warning("Gcast halted: Global limit reached")
                    await DeliveryTracker.mark_paused(task_id, "Global Rate limit reached")
                    should_complete = False
                    break # Break retry loop
                
                # 4. Risk Control Check
                can_proceed, _ = await RiskControl.can_proceed()
                if not can_proceed:
                    await DeliveryTracker.mark_paused(task_id, "Risk control blocked")
                    should_complete = False
                    break
                    
                # 5. Safety Check
                is_safe = await AntiSpamGuard.is_safe_recipient(worker, user_id)
                if not is_safe:
                    logger.warning("Skipping unsafe recipient", user_id=user_id, worker=session_id)
                    await DeliveryTracker.record_skipped(task_id, user_id, "unsafe")
                    break # Skip user entirely
                    
                # 6. Apply delay
                await self._sleep_random(delay_range)
                
                try:
                    # 7. AI Rewrite
                    final_message = message
                    if config.ENABLE_AI_REWRITE:
                        final_message = await rewriter.get_random_variant(message)
                    
                    # 8. Typing simulation & Send
                    async with worker.action(user_id, 'typing'):
                        await asyncio.sleep(random.uniform(1, 3))
                        
                    await worker.send_message(user_id, final_message)
                    sent_count += 1
                    success = True
                    
                    await DeliveryTracker.record_sent(task_id, idx)
                    if config.WARMUP_ENABLED:
                        await WarmupEngine.increment_count(session_id)
                    
                    logger.info("Gcast sent", recipient=user_id, progress=f"{idx+1}/{len(valid_ids)}", worker=session_id)
                    break # Success, move to next user
                    
                except FloodWaitError as e:
                    logger.warning(f"Worker {session_id} got FloodWait for {e.seconds}s")
                    self.mark_worker_resting(worker, e.seconds)
                    await RiskControl.record_flood_error()
                    # Loop continues, retrying with next worker
                    
                except Exception as e:
                    err_str = str(e).lower()
                    if "flood" in err_str or "limit" in err_str:
                        logger.warning(f"Worker {session_id} got Limit error")
                        self.mark_worker_resting(worker, 3600)
                        await RiskControl.record_flood_error()
                        # Loop continues, retrying with next worker
                    else:
                        logger.error("Failed to send to user", user_id=user_id, error=str(e), worker=session_id)
                        await DeliveryTracker.record_failed(task_id, user_id, str(e))
                        failed_count += 1
                        break # Unrecoverable error for this user, move to next user
            
            if not should_complete:
                break
                
            if not success and should_complete:
                # If we exhausted retries and didn't succeed or skip
                # It means all workers failed for this user
                pass

        if should_complete:
            await DeliveryTracker.mark_completed(task_id)
        
        progress = await DeliveryTracker.get_progress(task_id)
        logger.info("Gcast finished (completed or paused)", 
                   sent=progress["sent"], 
                   failed=progress["failed"],
                   skipped=progress["skipped"],
                   total=progress["total"])
        
        if origin_chat_id:
            try:
                completion_msg = (
                    f"✅ **Gcast Completed!**\n"
                    f"📤 Sent: `{progress['sent']}/{progress['total']}`\n"
                    f"❌ Failed: `{progress['failed']}`\n"
                    f"⏭️ Skipped: `{progress['skipped']}`"
                )
                owner_client = await TelegramBotClient.get_owner_client()
                if owner_client:
                    await owner_client.send_message(
                        origin_chat_id, 
                        completion_msg, 
                        reply_to=origin_message_id
                    )
            except Exception as e:
                logger.error("Failed to send completion notification via owner", error=str(e))

    async def handle_spam(self, task):
        """
        Executes a spam task to a single user using multiple workers.
        """
        task_id = task.get("task_id", "unknown")
        target = task.get("target_chat_id")
        message = task.get("message")
        count = task.get("count", 1)
        origin_chat_id = task.get("origin_chat_id")
        origin_message_id = task.get("origin_message_id")
        
        sent_count = 0
        failed_count = 0
        
        logger.info(f"Starting spam task {task_id} to {target} ({count} times)")
        
        for i in range(count):
            worker = self.get_next_active_worker()
            if not worker:
                logger.error("No active workers available for spam")
                break
                
            session_id = self.get_session_id(worker)
            
            # Sangat cepat untuk spam (0.5 - 1 detik)
            await self._sleep_random([0.5, 1.0])
            
            try:
                await worker.send_message(target, message)
                sent_count += 1
                if config.WARMUP_ENABLED:
                    await WarmupEngine.increment_count(session_id)
            except FloodWaitError as e:
                logger.warning(f"Worker {session_id} got FloodWait for {e.seconds}s during spam")
                self.mark_worker_resting(worker, e.seconds)
                await RiskControl.record_flood_error()
                failed_count += 1
            except Exception as e:
                logger.error("Spam send failed", target=target, error=str(e), worker=session_id)
                failed_count += 1
                
        # Send completion notification
        if origin_chat_id:
            try:
                completion_msg = (
                    f"✅ **Spam Selesai!**\n"
                    f"🎯 Target: `{target}`\n"
                    f"📤 Berhasil: `{sent_count}/{count}`\n"
                    f"❌ Gagal: `{failed_count}`"
                )
                owner_client = await TelegramBotClient.get_owner_client()
                if owner_client:
                    await owner_client.send_message(
                        origin_chat_id, 
                        completion_msg, 
                        reply_to=origin_message_id
                    )
            except Exception as e:
                logger.error("Failed to send spam completion notification", error=str(e))
