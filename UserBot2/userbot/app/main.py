import asyncio
import argparse
import sys
from app.config import config
from app.utils.logger import setup_logger, get_logger
from app.client import TelegramBotClient
from app.redis_conn import RedisClient
from app.handlers.monitor import setup_monitor
from app.handlers.scraper import setup_scraper
from app.handlers.spam import setup_spam
from app.worker import start_worker

setup_logger()
logger = get_logger(__name__)

async def main():
    parser = argparse.ArgumentParser(description="Telegram Userbot Worker")
    parser.add_argument("--auth-only", action="store_true", help="Run only authentication to generate session file")
    args = parser.parse_args()

    # 1. Initialize Request
    logger.info("Starting Userbot Service...")

    if args.auth_only:
        logger.info("Running in AUTH-ONLY mode")
        client = await TelegramBotClient.get_client()
        await client.start() # Interactive login
        user = await client.get_me()
        logger.info("Authentication successful", user_id=user.id)
        await client.disconnect()
        sys.exit(0)

    # 2. Start Application
    try:
        # Start Telegram Clients
        await TelegramBotClient.start()
        
        # Get clients
        owner_client = await TelegramBotClient.get_owner_client()
        worker_clients = await TelegramBotClient.get_worker_clients()
        
        if not owner_client:
            logger.error("Owner client not found. Cannot start command listeners.")
            # We don't exit here, workers might still be running queued jobs
        else:
            # Setup Handlers on Owner Client ONLY
            await setup_monitor(owner_client)
            await setup_scraper(owner_client)
            await setup_spam(owner_client)
            logger.info("Command handlers bound to Owner client.")
        
        # Start Worker Task
        worker_task = asyncio.create_task(start_worker())
        
        # Wait until clients disconnect
        if owner_client:
            await owner_client.run_until_disconnected()
        elif worker_clients:
            # If no owner but we have workers, wait on the first worker
            first_worker = list(worker_clients.values())[0]
            await first_worker.run_until_disconnected()
        else:
            logger.error("No clients running. Exiting.")
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.critical("Fatal error", error=str(e))
    finally:
        await RedisClient.close()
        await TelegramBotClient.stop()

if __name__ == "__main__":
    asyncio.run(main())
