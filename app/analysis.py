from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from hashlib import sha256
from typing import Iterable

from app.schemas import RawItem


STOP_WORDS = {"的", "和", "与", "及", "在", "对", "为", "了", "信息", "系统"}


def content_hash(title: str, content: str, url: str) -> str:
    payload = f"{title.strip()}|{content.strip()[:200]}|{url.strip()}".encode("utf-8")
    return sha256(payload).hexdigest()


def normalize_text(value: str) -> str:
    return " ".join(value.replace("\u3000", " ").split())


def extract_keywords(title: str, content: str, limit: int = 5) -> list[str]:
    text = normalize_text(f"{title} {content}")
    tokens: list[str] = []
    for raw in text.replace("，", " ").replace("。", " ").replace(",", " ").replace(".", " ").split():
        token = raw.strip("：:；;（）()[]【】")
        if len(token) >= 2 and token not in STOP_WORDS:
            tokens.append(token)
    return [word for word, _ in Counter(tokens).most_common(limit)]


def quality_score(title: str, content: str, url: str) -> float:
    score = 40.0
    if len(title.strip()) >= 6:
        score += 20
    if len(content.strip()) >= 40:
        score += 25
    if url.startswith(("http://", "https://", "file://")):
        score += 10
    if "�" not in content:
        score += 5
    return min(score, 100.0)


def clean_raw_item(raw: RawItem) -> dict[str, object]:
    title = normalize_text(raw.title)
    content = normalize_text(raw.content)
    keywords = extract_keywords(title, content)
    return {
        "normalized_title": title,
        "normalized_content": content,
        "keywords": ",".join(keywords),
        "quality_score": quality_score(title, content, raw.url),
    }


def trend_direction(current: int, previous: int) -> str:
    if previous == 0 and current > 0:
        return "surge"
    if current > previous * 1.2:
        return "up"
    if current < previous * 0.8:
        return "down"
    return "stable"


def calculate_trends(items: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    topic_counts: Counter[str] = Counter()
    latest_time: dict[str, str] = defaultdict(str)
    for item in items:
        keywords = str(item.get("keywords") or "").split(",")
        published_at = str(item.get("published_at") or "")
        for keyword in filter(None, keywords):
            topic_counts[keyword] += 1
            latest_time[keyword] = max(latest_time[keyword], published_at)

    results: list[dict[str, object]] = []
    for topic, count in topic_counts.most_common(20):
        recency_bonus = 1.0
        try:
            if latest_time[topic]:
                datetime.fromisoformat(latest_time[topic].replace("Z", "+00:00"))
                recency_bonus = 1.2
        except ValueError:
            recency_bonus = 1.0
        score = round(count * 10 * recency_bonus, 2)
        results.append(
            {
                "topic": topic,
                "score": score,
                "direction": trend_direction(count, max(count - 1, 0)),
            }
        )
    return results

