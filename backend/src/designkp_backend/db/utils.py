from __future__ import annotations

import uuid
from datetime import datetime, timezone


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
