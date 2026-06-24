from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from app.main import create_server


class ApiIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.server = create_server("127.0.0.1", 0, str(Path(self.tmp.name) / "api.db"))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"} if payload is not None else {}
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers)
            response = conn.getresponse()
            data = json.loads(response.read().decode("utf-8"))
            return response.status, data
        finally:
            conn.close()

    def test_health_endpoint(self) -> None:
        status, payload = self.request("GET", "/api/v1/health")

        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["status"], "ok")

    def test_options_preflight(self) -> None:
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        try:
            conn.request("OPTIONS", "/api/v1/sources")
            response = conn.getresponse()
            self.assertEqual(response.status, 204)
            self.assertEqual(response.getheader("Access-Control-Allow-Origin"), "*")
        finally:
            conn.close()

    def test_create_source_validation_returns_400(self) -> None:
        status, payload = self.request(
            "POST",
            "/api/v1/sources",
            {"name": "坏源", "type": "bad", "endpoint": "https://example.com"},
        )

        self.assertEqual(status, 400)
        self.assertEqual(payload["code"], 400)

    def test_collect_and_query_items_flow(self) -> None:
        status, created = self.request(
            "POST",
            "/api/v1/sources",
            {
                "name": "API集成测试源",
                "type": "forum",
                "endpoint": "https://example.com/forum",
                "keywords": "人工智能",
                "schedule": "weekly",
            },
        )
        self.assertEqual(status, 200)
        source_id = int(created["data"]["id"])

        status, task = self.request("POST", "/api/v1/tasks/collect", {"source_id": source_id})
        self.assertEqual(status, 200)
        self.assertEqual(task["data"]["task_status"], "success")
        self.assertGreater(task["data"]["success_count"], 0)

        status, items = self.request("GET", f"/api/v1/items?{urlencode({'keyword': '人工智能'})}")
        self.assertEqual(status, 200)
        self.assertGreater(items["data"]["total"], 0)

        status, trends = self.request("GET", "/api/v1/trends")
        self.assertEqual(status, 200)
        self.assertGreater(len(trends["data"]["topics"]), 0)


if __name__ == "__main__":
    unittest.main()
