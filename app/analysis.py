from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from typing import Iterable

from app.schemas import RawItem


STOP_WORDS = {
    # ── 中文停用词 ──
    "的", "和", "与", "及", "在", "对", "为", "了", "信息", "系统",
    "我", "你", "他", "她", "它", "我们", "你们", "他们", "她们",
    "它们", "这", "那", "这些", "那些", "这个", "那个", "什么", "怎么",
    "如何", "为什么", "哪个", "谁", "哪", "哪儿", "哪里", "那里", "这里",
    "不", "也", "就", "都", "而", "但", "是", "有", "被", "把",
    "从", "到", "让", "上", "下", "中", "很", "会", "可以", "能",
    "要", "将", "会", "已", "已经", "还", "还是", "没有", "没", "如果",
    "因为", "所以", "但是", "而且", "虽然", "然而", "或者", "还是", "然后",
    "之", "所", "被", "把", "让", "给", "向", "往", "比", "同",
    "跟", "但", "可", "却", "则", "或", "若", "关于", "对于", "根据",
    "按照", "通过", "利用", "作为", "包括", "关于", "基于",
    # ── 英文停用词 ──
    "the", "and", "to", "of", "a", "an", "in", "is", "it", "for",
    "on", "that", "this", "with", "be", "are", "was", "were", "been",
    "have", "has", "had", "do", "does", "did", "but", "not", "or",
    "so", "if", "no", "just", "about", "up", "out", "as", "at", "by",
    "from", "into", "through", "we", "you", "they", "he", "she", "me",
    "my", "your", "his", "her", "its", "our", "their", "him", "us",
    "them", "i", "etc", "also", "will", "can", "would", "could",
    "should", "may", "might", "shall", "must", "need", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such",
    "only", "own", "same", "than", "too", "very", "just", "because",
    "when", "where", "how", "what", "which", "who", "whom", "why",
    "while", "during", "before", "after", "above", "below", "between",
    "under", "over", "here", "there", "then", "now", "any", "anything",
    "everything", "nothing", "something", "always", "never", "often",
    "usually", "sometimes", "already", "yet", "still", "even", "well",
    "back", "been", "being", "having", "doing", "getting", "make",
    "made", "going", "go", "goes", "went", "come", "came", "take",
    "took", "use", "used", "using", "get", "got", "see", "seen",
    "know", "knew", "think", "thought", "want", "wanted", "give",
    "gave", "find", "found", "tell", "told", "become", "became",
    "leave", "left", "feel", "felt", "put", "set", "let", "say",
    "said", "try", "tried", "ask", "asked", "need", "needed",
    "seem", "seemed", "help", "helped", "show", "showed", "shown",
    "hear", "heard", "start", "started", "end", "ended", "way",
    "ways", "part", "parts", "thing", "things", "time", "times",
    "year", "years", "day", "days", "week", "weeks", "month", "months",
    "new", "first", "last", "next", "top", "bottom", "best", "worst",
    "better", "worse", "like", "look", "looks", "looking", "make",
    "makes", "making", "used", "using", "called",
    # ── 常见无意义英文词 ──
    "welcome", "home", "page", "pages", "site", "sites", "web",
    "website", "content", "menu", "link", "links", "login", "logout",
    "sign", "register", "search", "read", "more", "click", "here",
    "please", "thanks", "thank", "contact", "about", "privacy",
    "terms", "policy", "copyright", "rights", "reserved", "powered",
    "designed", "developed", "copyright", "blog", "article",
    "org", "com", "net", "io", "www", "http", "https", "html",
    "index", "default", "main", "body", "header", "footer",
}
_STOP_WORDS_LOWER: frozenset[str] = frozenset({w.lower() for w in STOP_WORDS})
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
        token = raw.strip("：:；;（）()[]【】\"'`")
        if len(token) >= 2 and token.lower() not in _STOP_WORDS_LOWER:
            tokens.append(token)
    return tokens


def extract_keywords(title: str, content: str, limit: int = 5) -> list[str]:
    return [word for word, _ in Counter(tokenize(normalize_text(f"{title} {content}"))).most_common(limit)]


def keyword_density(title: str, content: str, keywords: list[str]) -> float:
    tokens = tokenize(normalize_text(f"{title} {content}"))
    if not tokens:
        return 0.0
    unique_tokens = {t.lower() for t in tokens}
    if not unique_tokens:
        return 0.0
    matched = sum(1 for keyword in keywords if keyword.lower() in unique_tokens)
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
    if previous == 0:
        return "surge" if current > 0 else "stable"

    ratio = current / previous
    if ratio >= 1.5:
        return "surge"
    if ratio > 1.1:
        return "up"
    if ratio >= 0.9:
        return "stable"
    if ratio > 0.6:
        return "down"
    return "plunge"


def recency_decay(published_at: str, now: datetime | None = None) -> float:
    if not published_at:
        return 1.0
    now = now or datetime.now(timezone.utc)
    try:
        post_time = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return 1.0
    if post_time.tzinfo is None:
        post_time = post_time.replace(tzinfo=timezone.utc)
    days_diff = max((now - post_time).total_seconds() / 86400, 0.0)
    return 0.90 ** days_diff


def calculate_trends(items: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    topic_counts: Counter[str] = Counter()
    latest_time: dict[str, str] = defaultdict(str)
    for item in items:
        keywords = [keyword.strip() for keyword in str(item.get("keywords") or "").split(",") if keyword.strip()]
        published_at = str(item.get("published_at") or "")
        for keyword in keywords:
            topic_counts[keyword] += 1
            latest_time[keyword] = max(latest_time[keyword], published_at)

    results: list[dict[str, object]] = []
    top_topics = topic_counts.most_common(20)
    now = datetime.now(timezone.utc)
    for index, (topic, count) in enumerate(top_topics):
        if len(top_topics) > 1:
            previous_index = index + 1 if index < len(top_topics) - 1 else index - 1
            previous_count = top_topics[previous_index][1]
        else:
            previous_count = 0
        score = round(count * 10 * recency_decay(latest_time[topic], now), 2)
        results.append(
            {
                "topic": topic,
                "score": score,
                "direction": trend_direction(count, previous_count),
            }
        )
    return results
