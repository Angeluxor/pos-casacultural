from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

BOGOTA_TZ = ZoneInfo("America/Bogota")

def get_colombia_time() -> datetime:
    """Returns the current timezone-aware datetime for America/Bogota."""
    return datetime.now(BOGOTA_TZ)
