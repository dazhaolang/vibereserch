"""
Timezone-aware datetime utilities
"""
from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return current UTC time with timezone awareness"""
    return datetime.now(timezone.utc)