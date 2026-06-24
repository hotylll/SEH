from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from app.schemas import DataSource, ValidationError, response
from app.storage import Repository


class FileDownload:
    def __init__(self, path: Path, filename: str, content_type: str) -> None:
        self.path = path
        self.filename = filename
        self.content_type = content_type


class ApiHandler(BaseHTTPRequestHandler):
    repository = Repository()

    def do_GET(self) -> None:  # noqa: N802 - stdlib API
        self._handle("GET")

    def do_POST(self) -> None:  # noqa: N802 - stdlib API
        self._handle("POST")

    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib API
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return

    def _handle(self, method: str) -> None:
        parsed = urlparse(self.path)
        query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        try:
            data = self._dispatch(method, parsed.path, query)
            if isinstance(data, FileDownload):
                self._send_file(data)
                return
            self._send_json(200, response(data))
        except ValidationError as exc:
            self._send_json(400, response(None, str(exc), 400))
        except ValueError as exc:
            self._send_json(404, response(None, str(exc), 404))
        except Exception as exc:  # pragma: no cover - defensive HTTP boundary
            self._send_json(500, response(None, f"internal error: {exc}", 500))

    def _dispatch(self, method: str, path: str, query: dict[str, str]) -> Any:
        repo = self.repository
        if method == "GET" and path == "/api/v1/health":
            return repo.health()
        if method == "GET" and path == "/api/v1/sources":
            return {"items": repo.list_sources(query.get("type"), query.get("status"))}
        if method == "POST" and path == "/api/v1/sources":
            payload = self._read_json()
            source = DataSource(
                name=str(payload.get("name", "未命名数据源")),
                source_type=str(payload.get("type", payload.get("source_type", "news"))),
                endpoint=str(payload.get("endpoint", "")),
                keywords=str(payload.get("keywords", "")),
                schedule=str(payload.get("schedule", "manual")),
                status=str(payload.get("status", "enabled")),
            )
            return repo.create_source(source)
        if method == "POST" and path == "/api/v1/tasks/collect":
            payload = self._read_json()
            source_id = self._payload_positive_int(payload, "source_id")
            return repo.start_collect_task(source_id)
        if method == "GET" and path.startswith("/api/v1/tasks/"):
            return repo.get_task(self._path_positive_int(path, "task_id"))
        if method == "GET" and path == "/api/v1/items":
            limit = self._query_limit(query, default=50)
            source_id = self._query_positive_int(query, "source_id") if "source_id" in query else None
            items = repo.list_items(query.get("keyword"), source_id, limit)
            return {"items": items, "total": len(items)}
        if method == "GET" and path.startswith("/api/v1/items/"):
            return repo.get_item(self._path_positive_int(path, "item_id"))
        if method == "GET" and path == "/api/v1/trends":
            return {"topics": repo.list_trends(self._query_limit(query, default=20))}
        if method == "GET" and path.startswith("/api/v1/trends/"):
            topic = unquote(path.rsplit("/", 1)[-1]).strip()
            if not topic:
                raise ValidationError("topic 不能为空")
            return repo.get_topic_detail(topic, self._query_limit(query, default=20))
        if method == "GET" and path == "/api/v1/reports":
            return {"items": repo.list_reports()}
        if method == "GET" and path.startswith("/api/v1/reports/") and path.endswith("/download"):
            report_id = self._download_report_id(path)
            report_path, report = repo.get_report_file(report_id)
            return FileDownload(
                report_path,
                str(report["report_name"]),
                self._report_content_type(str(report["file_format"])),
            )
        if method == "POST" and path == "/api/v1/reports":
            payload = self._read_json()
            return repo.create_report(
                report_type=str(payload.get("report_type", "summary")),
                file_format=str(payload.get("format", "xlsx")),
                generated_by=str(payload.get("generated_by", "组长")),
            )
        raise ValueError(f"route {method} {path} not found")

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValidationError("Content-Length 格式错误") from exc
        if length == 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(body or "{}")
        except json.JSONDecodeError as exc:
            raise ValidationError("JSON 格式错误") from exc
        if not isinstance(payload, dict):
            raise ValidationError("JSON body 必须是对象")
        return payload

    def _query_limit(self, query: dict[str, str], default: int, maximum: int = 500) -> int:
        raw = query.get("limit", str(default))
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValidationError("limit 必须是正整数") from exc
        if value <= 0:
            raise ValidationError("limit 必须大于 0")
        if value > maximum:
            raise ValidationError(f"limit 不能超过 {maximum}")
        return value

    def _query_positive_int(self, query: dict[str, str], key: str) -> int:
        return self._positive_int(query.get(key), key)

    def _payload_positive_int(self, payload: dict[str, Any], key: str) -> int:
        return self._positive_int(payload.get(key), key)

    def _path_positive_int(self, path: str, key: str) -> int:
        return self._positive_int(path.rsplit("/", 1)[-1], key)

    def _download_report_id(self, path: str) -> int:
        parts = path.strip("/").split("/")
        if len(parts) != 5 or parts[:3] != ["api", "v1", "reports"] or parts[4] != "download":
            raise ValueError(f"route GET {path} not found")
        return self._positive_int(parts[3], "report_id")

    def _positive_int(self, raw: Any, key: str) -> int:
        if raw is None or str(raw).strip() == "":
            raise ValidationError(f"{key} 不能为空")
        try:
            value = int(str(raw))
        except ValueError as exc:
            raise ValidationError(f"{key} 必须是正整数") from exc
        if value <= 0:
            raise ValidationError(f"{key} 必须大于 0")
        return value

    def _report_content_type(self, file_format: str) -> str:
        if file_format == "xlsx":
            return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if file_format == "pdf":
            return "application/pdf"
        return "application/octet-stream"

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_file(self, download: FileDownload) -> None:
        raw = download.path.read_bytes()
        self.send_response(200)
        self._send_cors_headers()
        self.send_header("Content-Type", download.content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Content-Disposition", f'attachment; filename="{download.filename}"')
        self.end_headers()
        self.wfile.write(raw)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
