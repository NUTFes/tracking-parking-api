from datetime import datetime
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Asia/Tokyo")


def now_local() -> datetime:
    """Naive local (Asia/Tokyo) timestamp — matches the convention used by the
    edge-device fleet, whose system clocks run in local time, not UTC."""
    return datetime.now(LOCAL_TZ).replace(tzinfo=None)


def to_naive_local(dt: datetime) -> datetime:
    """Normalizes a possibly tz-aware timestamp from an edge device to naive
    local time. A naive input is assumed to already be local time."""
    if dt.tzinfo is not None:
        return dt.astimezone(LOCAL_TZ).replace(tzinfo=None)
    return dt
