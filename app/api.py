from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.schemas import DataSource, ValidationError, response
from app.storage import Repository


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
            return repo.start_collect_task(int(payload["source_id"]))
        if method == "GET" and path.startswith("/api/v1/tasks/"):
            return repo.get_task(int(path.rsplit("/", 1)[-1]))
        if method == "GET" and path == "/api/v1/items":
            limit = int(query.get("limit", "50"))
            source_id = int(query["source_id"]) if "source_id" in query else None
            items = repo.list_items(query.get("keyword"), source_id, limit)
            return {"items": items, "total": len(items)}
        if method == "GET" and path.startswith("/api/v1/items/"):
            return repo.get_item(int(path.rsplit("/", 1)[-1]))
        if method == "GET" and path == "/api/v1/trends":
            return {"topics": repo.list_trends(int(query.get("limit", "20")))}
        if method == "GET" and path.startswith("/api/v1/trends/"):
            topic = path.rsplit("/", 1)[-1]
            topics = [trend for trend in repo.list_trends(100) if trend["topic"] == topic]
            return {"topic": topic, "series": topics}
        if method == "POST" and path == "/api/v1/reports":
            payload = self._read_json()
            return repo.create_report(
                report_type=str(payload.get("format", payload.get("report_type", "summary"))),
                generated_by=str(payload.get("generated_by", "组长")),
            )
        raise ValueError(f"route {method} {path} not found")

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body or "{}")

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
