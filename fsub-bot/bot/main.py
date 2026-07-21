"""
Application entry point — boots the Hydrogram bot and optionally the worker.

Usage:
    python main.py          # Run the bot
    python main.py worker   # Run the worker consumer
    python main.py both     # Run both bot and worker
"""

from __future__ import annotations

import asyncio
import logging
import sys

# ── Logging Setup ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("fsub_bot")


async def run_bot() -> None:
    """Start the Hydrogram bot with lifecycle hooks."""
    from app.bot.main import create_bot, on_shutdown, on_startup

    bot = create_bot()


    try:
        logger.info("Starting bot polling...")
        await bot.start()
        await on_startup(bot)
        logger.info("Bot is running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()  # Run forever
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received.")
    finally:
        try:
            await bot.stop()
        except ConnectionError:
            pass
        await on_shutdown(bot)


async def run_worker() -> None:
    """Start the Redis queue consumer."""
    from app.core.database import close_db, init_db
    from app.core.redis import close_redis, get_redis
    from app.workers.consumer import consume_loop

    logger.info("Initialising worker...")
    await init_db()
    await get_redis()

    try:
        await consume_loop()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Worker shutdown signal received.")
    finally:
        await close_db()
        await close_redis()


async def run_both() -> None:
    """Run bot and worker concurrently."""
    from app.bot.main import create_bot, on_shutdown, on_startup
    from app.core.database import close_db, init_db
    from app.core.redis import close_redis, get_redis
    from app.workers.consumer import consume_loop

    bot = create_bot()
    await on_startup(bot)

    try:
        await bot.start()
        logger.info("Bot and worker are running.")
        # Run worker in background while bot polls
        worker_task = asyncio.create_task(consume_loop())
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received.")
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        try:
            await bot.stop()
        except ConnectionError:
            pass
        await on_shutdown(bot)


def run_api() -> None:
    """Start the FastAPI server."""
    import uvicorn
    
    logger.info("Starting FastAPI server on port 8000...")
    uvicorn.run("app.api.main:create_api", host="0.0.0.0", port=8000, factory=True, reload=True)


def main() -> None:
    """CLI dispatcher based on command-line argument."""
    mode = sys.argv[1] if len(sys.argv) > 1 else "bot"

    runner_map = {
        "bot": run_bot,
        "worker": run_worker,
        "both": run_both,
        "api": run_api,
    }

    runner = runner_map.get(mode)
    if runner is None:
        print(f"Unknown mode: {mode}")
        print(f"Usage: python main.py [{' | '.join(runner_map)}]")
        sys.exit(1)

    logger.info("Starting fsub-bot in '%s' mode...", mode)

    try:
        if mode == "api":
            runner()  # Uvicorn handles its own asyncio loop
        else:
            asyncio.run(runner())
    except KeyboardInterrupt:
        logger.info("Process interrupted.")


if __name__ == "__main__":
    main()
