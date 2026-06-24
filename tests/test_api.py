from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

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

    def request_raw(self, method: str, path: str, body: str) -> tuple[int, dict[str, Any]]:
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        try:
            conn.request(method, path, body=body.encode("utf-8"), headers={"Content-Type": "application/json"})
            response = conn.getresponse()
            data = json.loads(response.read().decode("utf-8"))
            return response.status, data
        finally:
            conn.close()

    def download(self, path: str) -> tuple[int, str | None, bytes]:
        conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
        try:
            conn.request("GET", path)
            response = conn.getresponse()
            return response.status, response.getheader("Content-Type"), response.read()
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

    def test_bad_request_inputs_return_400(self) -> None:
        cases = [
            ("POST", "/api/v1/tasks/collect", {}),
            ("GET", "/api/v1/items?limit=abc", None),
            ("GET", "/api/v1/items?limit=-1", None),
            ("GET", "/api/v1/items/abc", None),
            ("GET", "/api/v1/trends?limit=0", None),
        ]
        for method, path, payload in cases:
            with self.subTest(path=path):
                status, response = self.request(method, path, payload)
                self.assertEqual(status, 400)
                self.assertEqual(response["code"], 400)

        status, response = self.request_raw("POST", "/api/v1/tasks/collect", "{bad json")
        self.assertEqual(status, 400)
        self.assertEqual(response["code"], 400)

    def test_chinese_topic_detail_returns_series_or_items(self) -> None:
        status, trends = self.request("GET", "/api/v1/trends")
        self.assertEqual(status, 200)
        topic = trends["data"]["topics"][0]["topic"]

        status, detail = self.request("GET", f"/api/v1/trends/{quote(topic)}")

        self.assertEqual(status, 200)
        self.assertEqual(detail["data"]["topic"], topic)
        self.assertTrue(detail["data"]["series"] or detail["data"]["items"])

    def test_report_validation_and_downloads(self) -> None:
        status, response = self.request("POST", "/api/v1/reports", {"report_type": "bad", "format": "xlsx"})
        self.assertEqual(status, 400)
        self.assertEqual(response["code"], 400)

        status, response = self.request("POST", "/api/v1/reports", {"report_type": "summary", "format": "bad"})
        self.assertEqual(status, 400)
        self.assertEqual(response["code"], 400)

        for file_format, content_type in (
            ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("pdf", "application/pdf"),
        ):
            with self.subTest(file_format=file_format):
                status, created = self.request(
                    "POST",
                    "/api/v1/reports",
                    {"report_type": "detail", "format": file_format, "generated_by": "罗元恒"},
                )
                self.assertEqual(status, 200)
                self.assertEqual(created["data"]["file_format"], file_format)
                self.assertTrue(created["data"]["download_url"].endswith("/download"))

                status, report_content_type, body = self.download(created["data"]["download_url"])
                self.assertEqual(status, 200)
                self.assertEqual(report_content_type, content_type)
                self.assertGreater(len(body), 100)

        status, reports = self.request("GET", "/api/v1/reports")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(reports["data"]["items"]), 2)


if __name__ == "__main__":
    unittest.main()
