import redis.asyncio as redis
from app.config import config
from app.utils.logger import get_logger

logger = get_logger(__name__)

class RedisClient:
    _instance = None

    @classmethod
    def get_instance(cls) -> redis.Redis:
        if cls._instance is None:
            logger.info("Initializing New Redis Connection", url=config.REDIS_URL)
            cls._instance = redis.from_url(
                config.REDIS_URL, 
                encoding="utf-8", 
                decode_responses=True
            )
        return cls._instance

    @classmethod
    async def close(cls):
        if cls._instance:
            await cls._instance.close()
            cls._instance = None
            logger.info("Redis Connection Closed")
