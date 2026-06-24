from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from app.schemas import DataSource, RawItem, utc_now
from app.storage import Repository


class PerformanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repository(Path(self.tmp.name) / "performance.db")
        self.repo.initialize()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_search_10000_demo_items_under_three_seconds(self) -> None:
        source = self.repo.create_source(
            DataSource("性能测试源", "news", "https://example.com/performance", "人工智能,新能源汽车")
        )
        with self.repo.session() as conn:
            cursor = conn.execute(
                "INSERT INTO collect_tasks(source_id, task_status, started_at) VALUES(?,?,?)",
                (int(source["id"]), "running", utc_now()),
            )
            task_id = int(cursor.lastrowid)
            for index in range(10000):
                keyword = "人工智能" if index % 2 == 0 else "新能源汽车"
                raw = RawItem(
                    source_id=int(source["id"]),
                    task_id=task_id,
                    title=f"{keyword} 演示数据 第{index}条",
                    content=f"{keyword} 测试内容用于验证一万条数据规模下的信息检索响应速度和清洗入库稳定性。",
                    url=f"https://example.com/performance/{index}",
                    published_at="2026-06-23T00:00:00+00:00",
                    author="性能测试源",
                )
                self.assertTrue(self.repo._insert_raw_and_clean(conn, raw))
            conn.execute(
                """
                UPDATE collect_tasks
                SET task_status = ?, success_count = ?, failed_count = ?, finished_at = ?
                WHERE id = ?
                """,
                ("success", 10000, 0, utc_now(), task_id),
            )
            self.repo.rebuild_trends(conn)

        start = time.perf_counter()
        items = self.repo.list_items(keyword="人工智能", limit=50)
        elapsed = time.perf_counter() - start

        self.assertEqual(len(items), 50)
        self.assertLess(elapsed, 3.0)


if __name__ == "__main__":
    unittest.main()
