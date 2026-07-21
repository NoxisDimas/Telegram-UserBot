"""
Task dispatch — maps job types to handler functions.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

logger = logging.getLogger(__name__)

# ── Task handler registry ────────────────────────────────────
TaskHandler = Callable[[Dict[str, Any]], Awaitable[None]]
_handlers: Dict[str, TaskHandler] = {}


def register_task(job_type: str) -> Callable[[TaskHandler], TaskHandler]:
    """Decorator to register a task handler for a given job type."""
    def wrapper(fn: TaskHandler) -> TaskHandler:
        _handlers[job_type] = fn
        logger.debug("Registered task handler: %s → %s", job_type, fn.__name__)
        return fn
    return wrapper


async def dispatch_task(job_type: str, data: Dict[str, Any]) -> None:
    """Dispatch a job to its registered handler.

    Raises KeyError if no handler is registered for the job type.
    """
    handler = _handlers.get(job_type)
    if handler is None:
        raise KeyError(f"No handler registered for job type: {job_type!r}")
    await handler(data)


# ──────────────────────────────────────────────────────────────
# Task implementations
# ──────────────────────────────────────────────────────────────

@register_task("membership_check")
async def handle_membership_check(data: Dict[str, Any]) -> None:
    """Batch membership verification task.

    Expected data:
        {"user_id": int, "channel_ids": list[int]}
    """
    user_id = data["user_id"]
    channel_ids = data.get("channel_ids", [])

    logger.info(
        "Membership check job: user=%d channels=%s",
        user_id, channel_ids,
    )

    # Note: This would typically use a bot client instance to call
    # get_chat_member, but workers don't have direct access to the
    # Hydrogram client. In production, this would connect via a
    # shared client or a separate bot session.
    #
    # For now, this is a placeholder that logs the intent.
    # The actual membership check is done inline in the bot handlers.


@register_task("send_content")
async def handle_send_content(data: Dict[str, Any]) -> None:
    """Send content to a user (deferred delivery).

    Expected data:
        {"user_id": int, "content_id": str}
    """
    user_id = data["user_id"]
    content_id = data.get("content_id", "")

    logger.info(
        "Send content job: user=%d content=%s",
        user_id, content_id,
    )
    # In production, this would use a secondary bot client instance
    # to send the content files to the user.


@register_task("webhook_delivery")
async def handle_webhook_delivery(data: Dict[str, Any]) -> None:
    """Deliver a webhook to the Group Help bot.

    Expected data:
        {"url": str, "payload": dict, "headers": dict}
    """
    import aiohttp

    url = data["url"]
    payload = data.get("payload", {})
    headers = data.get("headers", {})

    logger.info("Webhook delivery job: url=%s", url)

    async with aiohttp.ClientSession() as http_session:
        async with http_session.post(
            url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            if resp.status >= 400:
                body = await resp.text()
                raise RuntimeError(
                    f"Webhook delivery failed: {resp.status} — {body}"
                )
            logger.info("Webhook delivered: %s → %d", url, resp.status)


@register_task("scheduled_post")
async def handle_scheduled_post(data: Dict[str, Any]) -> None:
    """Execute a scheduled post.

    Expected data:
        {"content_id": str, "target_chats": list[int], "caption": str | None}
    """
    content_id = data.get("content_id", "")
    target_chats = data.get("target_chats", [])

    logger.info(
        "Scheduled post job: content=%s targets=%s",
        content_id, target_chats,
    )
    # In production, this would iterate over target chats and send
    # the content using a bot client instance.
