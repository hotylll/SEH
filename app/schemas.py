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


class ValidationError(ValueError):
    """数据校验异常，用于向客户端返回 400 状态码。"""
    pass


VALID_SOURCE_TYPES = ("news", "forum", "api", "csv")
VALID_SCHEDULES = ("manual", "hourly", "daily", "weekly")
VALID_STATUSES = ("enabled", "disabled")


@dataclass(frozen=True)
class DataSource:
    name: str
    source_type: str
    endpoint: str
    keywords: str = ""
    schedule: str = "manual"
    status: str = "enabled"

    def __post_init__(self) -> None:
        if self.source_type not in VALID_SOURCE_TYPES:
            raise ValidationError(
                f"source_type 必须是 {'/'.join(VALID_SOURCE_TYPES)} 之一，收到: {self.source_type}"
            )
        if not self.endpoint.strip():
            raise ValidationError("endpoint 不能为空")
        if self.keywords:
            parts = [k.strip() for k in self.keywords.split(",") if k.strip()]
            if not parts:
                raise ValidationError("keywords 格式错误，请使用逗号分隔，如: 人工智能,新能源")
        if self.schedule not in VALID_SCHEDULES:
            raise ValidationError(
                f"schedule 必须是 {'/'.join(VALID_SCHEDULES)} 之一，收到: {self.schedule}"
            )
        if self.status not in VALID_STATUSES:
            raise ValidationError(
                f"status 必须是 {'/'.join(VALID_STATUSES)} 之一，收到: {self.status}"
            )


@dataclass(frozen=True)
class RawItem:
    source_id: int
    task_id: int
    title: str
    content: str
    url: str
    published_at: str
    author: str = ""

