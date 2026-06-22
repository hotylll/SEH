from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.schemas import DataSource
from app.storage import Repository


class RepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repository(Path(self.tmp.name) / "test.db")
        self.repo.initialize()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_collect_task_creates_items_and_trends(self) -> None:
        source = self.repo.create_source(
            DataSource(
                name="测试源",
                source_type="news",
                endpoint="https://example.com",
                keywords="人工智能",
            )
        )
        task = self.repo.start_collect_task(int(source["id"]))
        items = self.repo.list_items(keyword="人工智能")
        trends = self.repo.list_trends()

        self.assertEqual(task["task_status"], "success")
        self.assertGreaterEqual(task["success_count"], 1)
        self.assertGreaterEqual(len(items), 1)
        self.assertGreaterEqual(len(trends), 1)

    def test_duplicate_collection_is_deduplicated(self) -> None:
        source = self.repo.create_source(DataSource("测试源", "news", "https://example.com"))
        first = self.repo.start_collect_task(int(source["id"]))
        second = self.repo.start_collect_task(int(source["id"]))

        self.assertGreater(first["success_count"], 0)
        self.assertEqual(second["success_count"], 0)
        self.assertEqual(len(self.repo.list_items()), first["success_count"])

    def test_health_check(self) -> None:
        health = self.repo.health()

        self.assertEqual(health["status"], "ok")
        self.assertIn("db", health)


if __name__ == "__main__":
    unittest.main()

