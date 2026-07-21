"""
Proxy Rotation Service
Auto-switch proxy on connection issues.
"""
import json
import random
from typing import Optional, List, Dict
from app.redis_conn import RedisClient
from app.config import config
from app.utils.logger import get_logger

logger = get_logger(__name__)

class ProxyManager:
    """
    Manages proxy rotation for Telethon client.
    """
    
    PROXIES_KEY = "proxy:list"
    CURRENT_KEY = "proxy:current"
    STATS_KEY = "proxy:stats"
    
    @classmethod
    async def initialize(cls):
        """Initialize proxies from config."""
        # Load from PROXY_LIST env var (comma-separated)
        proxy_list = getattr(config, 'PROXY_LIST', '')
        
        if not proxy_list:
            logger.info("No proxies configured")
            return
        
        redis = RedisClient.get_instance()
        proxies = []
        
        for proxy_str in proxy_list.split(','):
            proxy_str = proxy_str.strip()
            if not proxy_str:
                continue
            
            # Parse: type://host:port or type://user:pass@host:port
            try:
                proxy = cls._parse_proxy(proxy_str)
                if proxy:
                    proxies.append(proxy)
            except Exception as e:
                logger.error("Invalid proxy format", proxy=proxy_str, error=str(e))
        
        if proxies:
            await redis.set(cls.PROXIES_KEY, json.dumps(proxies))
            logger.info("Proxies loaded", count=len(proxies))
    
    @classmethod
    def _parse_proxy(cls, proxy_str: str) -> Optional[Dict]:
        """Parse proxy string to dict."""
        import re
        
        # Format: socks5://user:pass@host:port or http://host:port
        pattern = r'^(socks[45]|http|mtproto)://(?:([^:]+):([^@]+)@)?([^:]+):(\d+)$'
        match = re.match(pattern, proxy_str)
        
        if not match:
            return None
        
        proxy_type, user, password, host, port = match.groups()
        
        return {
            "type": proxy_type,
            "host": host,
            "port": int(port),
            "username": user,
            "password": password
        }
    
    @classmethod
    async def get_proxies(cls) -> List[Dict]:
        """Get all configured proxies."""
        redis = RedisClient.get_instance()
        data = await redis.get(cls.PROXIES_KEY)
        return json.loads(data) if data else []
    
    @classmethod
    async def get_current(cls) -> Optional[Dict]:
        """Get currently active proxy."""
        redis = RedisClient.get_instance()
        data = await redis.get(cls.CURRENT_KEY)
        return json.loads(data) if data else None
    
    @classmethod
    async def set_current(cls, proxy: Dict):
        """Set current proxy."""
        redis = RedisClient.get_instance()
        await redis.set(cls.CURRENT_KEY, json.dumps(proxy))
        logger.info("Proxy set", host=proxy.get("host"))
    
    @classmethod
    async def rotate(cls) -> Optional[Dict]:
        """Rotate to next proxy."""
        proxies = await cls.get_proxies()
        
        if not proxies:
            return None
        
        current = await cls.get_current()
        
        # Find next proxy (skip current)
        available = [p for p in proxies if p != current]
        
        if not available:
            available = proxies
        
        next_proxy = random.choice(available)
        await cls.set_current(next_proxy)
        
        # Update stats
        redis = RedisClient.get_instance()
        await redis.hincrby(cls.STATS_KEY, "rotation_count", 1)
        
        logger.info("Proxy rotated", new_host=next_proxy.get("host"))
        return next_proxy
    
    @classmethod
    async def mark_failed(cls, proxy: Dict):
        """Mark a proxy as failed."""
        redis = RedisClient.get_instance()
        await redis.hincrby(cls.STATS_KEY, f"failed:{proxy.get('host')}", 1)
        
        # Auto-rotate on failure
        await cls.rotate()
    
    @classmethod
    def to_telethon_format(cls, proxy: Dict) -> tuple:
        """Convert to Telethon proxy format."""
        import socks
        
        proxy_type = proxy.get("type", "socks5")
        
        type_map = {
            "socks4": socks.SOCKS4,
            "socks5": socks.SOCKS5,
            "http": socks.HTTP
        }
        
        return (
            type_map.get(proxy_type, socks.SOCKS5),
            proxy.get("host"),
            proxy.get("port"),
            True,  # rdns
            proxy.get("username"),
            proxy.get("password")
        )
