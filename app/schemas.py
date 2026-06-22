from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def response(data: Any = None, message: str = "ok", code: int = 0) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "data": data,
        "trace_id": f"trace-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
    }


@dataclass(frozen=True)
class DataSource:
    name: str
    source_type: str
    endpoint: str
    keywords: str = ""
    schedule: str = "manual"
    status: str = "enabled"


@dataclass(frozen=True)
class RawItem:
    source_id: int
    task_id: int
    title: str
    content: str
    url: str
    published_at: str
    author: str = ""

