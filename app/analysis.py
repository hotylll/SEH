from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime
from hashlib import sha256
from typing import Iterable

from app.schemas import RawItem


STOP_WORDS = {"的", "和", "与", "及", "在", "对", "为", "了", "信息", "系统"}
_HTML_TAG_RE = re.compile(r"<[^>]+>")
REQUIRED_CLEAN_KEYS = ("normalized_title", "normalized_content", "keywords", "quality_score")


def content_hash(title: str, content: str, url: str) -> str:
    payload = f"{title.strip()}|{content.strip()[:200]}|{url.strip()}".encode("utf-8")
    return sha256(payload).hexdigest()


def strip_html_tags(value: str) -> str:
    return _HTML_TAG_RE.sub(" ", value)


def normalize_text(value: str) -> str:
    cleaned = strip_html_tags(value or "")
    return " ".join(cleaned.replace("\u3000", " ").split())


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in text.replace("，", " ").replace("。", " ").replace(",", " ").replace(".", " ").split():
        token = raw.strip("：:；;（）()[]【】")
        if len(token) >= 2 and token not in STOP_WORDS:
            tokens.append(token)
    return tokens


def extract_keywords(title: str, content: str, limit: int = 5) -> list[str]:
    return [word for word, _ in Counter(tokenize(normalize_text(f"{title} {content}"))).most_common(limit)]


def keyword_density(title: str, content: str, keywords: list[str]) -> float:
    tokens = tokenize(normalize_text(f"{title} {content}"))
    if not tokens:
        return 0.0
    unique_tokens = set(tokens)
    if not unique_tokens:
        return 0.0
    matched = sum(1 for keyword in keywords if keyword in unique_tokens)
    return round(matched / len(unique_tokens), 4)


def _score_title_length(title: str) -> float:
    length = len(title.strip())
    if length == 0:
        return 0.0
    if length < 6:
        return 8.0
    if length <= 30:
        return 15.0
    return 12.0


def _score_content_length(content: str) -> float:
    length = len(content.strip())
    if length == 0:
        return 0.0
    if length < 40:
        return 10.0
    if length < 200:
        return 20.0
    return 25.0


def _score_keyword_density(density: float) -> float:
    if density <= 0:
        return 0.0
    if density < 0.05:
        return 6.0
    if density < 0.2:
        return 15.0
    if density <= 0.5:
        return 20.0
    return 12.0


def quality_score(title: str, content: str, url: str, keywords: list[str] | None = None) -> float:
    normalized_title = normalize_text(title)
    normalized_content = normalize_text(content)
    keywords = keywords if keywords is not None else extract_keywords(normalized_title, normalized_content)

    score = 0.0
    score += _score_title_length(normalized_title)
    score += _score_content_length(normalized_content)

    if url.strip().startswith(("http://", "https://", "file://")):
        score += 10.0

    score += _score_keyword_density(keyword_density(normalized_title, normalized_content, keywords))

    if "�" not in normalized_content and "�" not in normalized_title:
        score += 8.0

    if normalized_title and normalized_content:
        score += 12.0
    elif normalized_title or normalized_content:
        score += 6.0

    overlap = set(keywords) & set(tokenize(normalized_title))
    if overlap:
        score += min(10.0, len(overlap) * 3.0)

    return round(min(score, 100.0), 2)


def validate_clean_result(clean: dict[str, object]) -> dict[str, object]:
    missing = [key for key in REQUIRED_CLEAN_KEYS if key not in clean]
    if missing:
        raise ValueError(f"clean result missing fields: {', '.join(missing)}")

    normalized_title = str(clean["normalized_title"])
    normalized_content = str(clean["normalized_content"])
    keywords = str(clean["keywords"])
    quality = clean["quality_score"]
    if not isinstance(quality, (int, float)):
        raise ValueError("quality_score must be numeric")

    return {
        "normalized_title": normalized_title,
        "normalized_content": normalized_content,
        "keywords": keywords,
        "quality_score": round(min(max(float(quality), 0.0), 100.0), 2),
    }


def clean_raw_item(raw: RawItem) -> dict[str, object]:
    title = normalize_text(raw.title)
    content = normalize_text(raw.content)
    keywords = extract_keywords(title, content)
    return validate_clean_result(
        {
            "normalized_title": title,
            "normalized_content": content,
            "keywords": ",".join(keywords),
            "quality_score": quality_score(title, content, raw.url, keywords),
        }
    )


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
