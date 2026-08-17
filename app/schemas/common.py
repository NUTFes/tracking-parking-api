from datetime import datetime
from typing import Annotated

from pydantic import PlainSerializer

from app.utils import LOCAL_TZ


def _serialize_local_datetime(value: datetime) -> str:
    """Stamps a naive local (JST) datetime with its UTC offset before
    serializing, so clients parse it as JST regardless of their own
    timezone/locale — see app.utils.now_local, which returns naive JST
    values that would otherwise be ambiguous to a JS `Date` parser."""
    aware = value if value.tzinfo is not None else value.replace(tzinfo=LOCAL_TZ)
    return aware.isoformat()


# Use in place of `datetime` on response schema fields (never on request
# fields — those already accept both naive and offset-aware input via
# app.utils.to_naive_local).
JSTDateTime = Annotated[datetime, PlainSerializer(_serialize_local_datetime, return_type=str)]
