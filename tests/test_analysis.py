from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.analysis import (
    calculate_trends,
    clean_raw_item,
    extract_keywords,
    keyword_density,
    normalize_text,
    quality_score,
    recency_decay,
    trend_direction,
    validate_clean_result,
)
from app.schemas import RawItem


class AnalysisTest(unittest.TestCase):
    def test_normalize_text_strips_html_and_whitespace(self) -> None:
        text = "<p>人工智能</p>  \n  助力   城市治理"
        self.assertEqual(normalize_text(text), "人工智能 助力 城市治理")

    def test_quality_score_rewards_rich_content(self) -> None:
        low = quality_score("短", "内容", "https://example.com")
        high = quality_score(
            "人工智能助力城市治理",
            "公开报道显示人工智能相关讨论在近七天持续增长，用户关注治理效率与数据质量。",
            "https://example.com/news/ai-city",
        )
        self.assertLess(low, high)
        self.assertGreaterEqual(high, 70.0)

    def test_keyword_density_increases_score(self) -> None:
        title = "新能源汽车 市场 数据"
        content = "新能源汽车市场数据持续增长，用户关注续航、补能和价格变化。"
        keywords = extract_keywords(title, content)
        density = keyword_density(title, content, keywords)
        self.assertGreater(density, 0.0)
        self.assertGreater(quality_score(title, content, "https://example.com", keywords), 50.0)

    def test_clean_raw_item_returns_complete_fields(self) -> None:
        raw = RawItem(
            source_id=1,
            task_id=1,
            title="<b>高校 软件工程 课程</b>",
            content="软件工程课程强调文档规范与测试覆盖。",
            url="https://example.com/forum/software-docs",
            published_at="2026-06-17T08:00:00+00:00",
        )
        clean = clean_raw_item(raw)

        self.assertEqual(set(clean.keys()), {"normalized_title", "normalized_content", "keywords", "quality_score"})
        self.assertNotIn("<b>", clean["normalized_title"])
        self.assertTrue(clean["keywords"])
        self.assertGreaterEqual(float(clean["quality_score"]), 0.0)
        self.assertLessEqual(float(clean["quality_score"]), 100.0)

    def test_validate_clean_result_rejects_incomplete_payload(self) -> None:
        with self.assertRaises(ValueError):
            validate_clean_result({"normalized_title": "标题"})

    def test_trend_direction_supports_five_states(self) -> None:
        self.assertEqual(trend_direction(10, 0), "surge")
        self.assertEqual(trend_direction(15, 10), "surge")
        self.assertEqual(trend_direction(12, 10), "up")
        self.assertEqual(trend_direction(10, 10), "stable")
        self.assertEqual(trend_direction(7, 10), "down")
        self.assertEqual(trend_direction(5, 10), "plunge")

    def test_recency_decay_lowers_old_topic_score(self) -> None:
        now = datetime(2026, 6, 23, tzinfo=timezone.utc)
        recent = recency_decay("2026-06-23T00:00:00+00:00", now)
        old = recency_decay("2026-06-13T00:00:00+00:00", now)

        self.assertGreater(recent, old)

    def test_calculate_trends_uses_recency_and_direction(self) -> None:
        trends = calculate_trends(
            [
                {"keywords": "人工智能", "published_at": "2026-06-23T00:00:00+00:00"},
                {"keywords": "人工智能", "published_at": "2026-06-22T00:00:00+00:00"},
                {"keywords": "新能源汽车", "published_at": "2026-06-13T00:00:00+00:00"},
            ]
        )

        self.assertEqual(trends[0]["topic"], "人工智能")
        self.assertIn(trends[0]["direction"], {"surge", "up"})
        self.assertGreater(float(trends[0]["score"]), float(trends[1]["score"]))


if __name__ == "__main__":
    unittest.main()
