"""
Time Window & Human Mode
Configurable active hours to avoid non-human activity patterns.
"""
from datetime import datetime, time
from app.config import config
from app.utils.logger import get_logger

logger = get_logger(__name__)

class TimeWindow:
    """
    Manages active hours for the worker.
    Pauses execution outside configured time window.
    """
    
    @staticmethod
    def get_active_hours() -> tuple[int, int]:
        """Get configured active hours (start, end)."""
        start = getattr(config, 'ACTIVE_HOURS_START', 9)
        end = getattr(config, 'ACTIVE_HOURS_END', 21)
        return start, end
    
    @classmethod
    def is_active_hours(cls) -> bool:
        """Check if current time is within active hours."""
        start_hour, end_hour = cls.get_active_hours()
        
        # If feature is disabled (start == end == 0), always active
        if start_hour == 0 and end_hour == 0:
            return True
        
        current_hour = datetime.now().hour
        
        # Handle overnight windows (e.g., 22:00 - 06:00)
        if start_hour > end_hour:
            return current_hour >= start_hour or current_hour < end_hour
        
        return start_hour <= current_hour < end_hour
    
    @classmethod
    def get_status(cls) -> dict:
        """Get time window status."""
        start, end = cls.get_active_hours()
        current = datetime.now().hour
        active = cls.is_active_hours()
        
        return {
            "active_hours": f"{start:02d}:00 - {end:02d}:00",
            "current_hour": f"{current:02d}:00",
            "is_active": active
        }
    
    @classmethod
    def seconds_until_active(cls) -> int:
        """Calculate seconds until next active window."""
        if cls.is_active_hours():
            return 0
        
        start_hour, _ = cls.get_active_hours()
        now = datetime.now()
        
        # Calculate next start time
        next_start = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        
        if next_start <= now:
            # Start is tomorrow
            from datetime import timedelta
            next_start += timedelta(days=1)
        
        delta = next_start - now
        return int(delta.total_seconds())
