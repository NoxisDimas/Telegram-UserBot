"""
Main Worker Loop with Priority Queue Support
Polls Redis queues (high > normal > low) and executes tasks.
"""
import asyncio
import json
from app.redis_conn import RedisClient
from app.handlers.executor import TaskExecutor
from app.client import TelegramBotClient
from app.config import config
from app.utils.logger import get_logger
from app.services.kill_switch import KillSwitch
from app.services.time_window import TimeWindow
from app.services.risk_control import RiskControl

logger = get_logger(__name__)

# Priority queue names (highest to lowest)
PRIORITY_QUEUES = [
    "userbot:queue:high",
    "userbot:queue:normal", 
    "userbot:queue:low"
]
LEGACY_QUEUE = "userbot:queue"

async def start_worker():
    """
    Main worker loop with priority queue support.
    Checks kill switch, time window, and risk control before processing.
    """
    logger.info("Worker started, waiting for tasks...")
    
    redis = RedisClient.get_instance()
    
    worker_clients_dict = await TelegramBotClient.get_worker_clients()
    if not worker_clients_dict:
        logger.warning("No worker clients available! Worker loop will sleep.")
        # We could either break or sleep. Let's sleep and wait.
    
    worker_clients = list(worker_clients_dict.values())
    executor = TaskExecutor(worker_clients)
    
    while True:
        try:
            # 1. Check Kill Switch
            if not await KillSwitch.check_and_wait():
                await asyncio.sleep(10)  # Check again in 10s
                continue
            
            # 2. Check Time Window
            if not TimeWindow.is_active_hours():
                wait_seconds = TimeWindow.seconds_until_active()
                logger.info("Outside active hours, sleeping", 
                           status=TimeWindow.get_status(),
                           resume_in_seconds=min(wait_seconds, 300))
                await asyncio.sleep(min(wait_seconds, 300))  # Max 5 min sleep
                continue
            
            # 3. Check Risk Control
            can_proceed, risk_reason = await RiskControl.can_proceed()
            if not can_proceed:
                logger.warning("Risk control blocked", reason=risk_reason)
                await asyncio.sleep(60)  # Wait 1 min before retry
                continue
            
            # 4. Poll Queues (Priority Order)
            task_data = None
            
            if config.PRIORITY_QUEUE_ENABLED:
                # Try each priority queue in order
                for queue_name in PRIORITY_QUEUES:
                    result = await redis.lpop(queue_name)
                    if result:
                        try:
                            task_data = json.loads(result)
                            task_data["_queue"] = queue_name  # Track source queue
                            logger.debug("Task from priority queue", queue=queue_name)
                        except json.JSONDecodeError:
                            logger.error("Failed to decode task JSON", raw=result)
                        break
            
            # Fallback to legacy queue if no priority task
            if not task_data:
                result = await redis.blpop(LEGACY_QUEUE, timeout=5)
                if result:
                    queue_name, task_json = result
                    try:
                        task_data = json.loads(task_json)
                    except json.JSONDecodeError:
                        logger.error("Failed to decode task JSON", raw=task_json)
            
            # 5. Execute Task
            if task_data:
                await executor.execute(task_data)
                    
        except asyncio.CancelledError:
            logger.info("Worker task cancelled")
            break
        except Exception as e:
            logger.error("Critical worker error", error=str(e))
            await asyncio.sleep(5)


async def push_task(task: dict, priority: str = "normal"):
    """
    Push a task to the appropriate priority queue.
    priority: "high", "normal", or "low"
    """
    redis = RedisClient.get_instance()
    
    if config.PRIORITY_QUEUE_ENABLED:
        queue_map = {
            "high": PRIORITY_QUEUES[0],
            "normal": PRIORITY_QUEUES[1],
            "low": PRIORITY_QUEUES[2]
        }
        queue = queue_map.get(priority, PRIORITY_QUEUES[1])
    else:
        queue = LEGACY_QUEUE
    
    await redis.lpush(queue, json.dumps(task))
    logger.info("Task pushed", queue=queue, task_id=task.get("task_id"))
