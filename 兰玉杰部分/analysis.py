from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
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
    """原代码
    if previous == 0 and current > 0:
        return "surge"
    if current > previous * 1.2:
        return "up"
    if current < previous * 0.8:
        return "down"
    return "stable"
    """
    """
    提供更细腻的趋势描述。
    """
    if previous == 0:
        if current > 0:
            return "surge"  # 从无到有，视为激增
        return "stable"     # 一直为零，视为平稳

    ratio = current / previous
    if ratio >= 1.5:
        return "surge"      # 增长超过50%，视为激增
    elif ratio > 1.1:
        return "up"         # 增长10%~50%，视为上升
    elif ratio >= 0.9:
        return "stable"     # 变化在±10%以内，视为平稳
    elif ratio > 0.6:
        return "down"       # 下降10%~40%，视为下降
    else:
        return "plunge"     # 下降超过40%，视为骤降

def calculate_trends(items: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    """
    计算话题趋势，引入时间衰减因子。
    返回结构：[{"topic": "...", "score": 123.45, "direction": "up"}, ...]
    """
    topic_counts: Counter[str] = Counter()
    latest_time: dict[str, str] = defaultdict(str)

    # 获取当前时间 (UTC)，用于计算衰减
    now = datetime.now(timezone.utc)

    # 1. 统计频次与最新时间
    for item in items:
        keywords_str = str(item.get("keywords") or "")
        published_at = str(item.get("published_at") or "")

        # 过滤空关键词
        keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]

        for keyword in keywords:
            topic_counts[keyword] += 1
            # 记录每个话题最新的发布时间
            if published_at > latest_time[keyword]:
                latest_time[keyword] = published_at

    results: list[dict[str, object]] = []

    # 2. 获取 Top 20 热门话题
    # most_common 返回的是 [(keyword, count), ...] 列表，已按 count 降序排列
    top_topics = topic_counts.most_common(20)

    for idx, (topic, count) in enumerate(top_topics):
        # --- A. 计算时间衰减因子 ---
        decay_factor = 1.0
        latest_timestamp = latest_time.get(topic)

        if latest_timestamp:
            try:
                # 兼容 'Z' 结尾的ISO格式
                time_str = latest_timestamp.replace("Z", "+00:00")
                post_time = datetime.fromisoformat(time_str)

                # 如果解析出的时间没有时区信息，则假设为UTC
                if post_time.tzinfo is None:
                    post_time = post_time.replace(tzinfo=timezone.utc)

                # 计算时间差（以天为单位）
                time_diff = now - post_time
                days_diff = time_diff.total_seconds() / 86400

                # 应用衰减函数：每过一天，权重衰减10% (0.9^days)
                # 1天内: ~1.0, 3天内: ~0.73, 7天内: ~0.48
                decay_factor = 0.90 ** max(days_diff, 0)

            except (ValueError, TypeError, OverflowError):
                # 如果时间解析失败，不应用衰减
                decay_factor = 1.0

        # --- B. 计算最终得分 ---
        base_score = count * 10
        final_score = round(base_score * decay_factor, 2)

        # --- C. 计算趋势方向 ---
        # 逻辑修正：使用排名靠后的话题作为“历史/平均”基准，避免自身减自身导致的逻辑错误
        # 如果是第一个（最热），对比第二个；如果是最后一个，对比平均值或前一个
        if len(top_topics) > 1:
            # 取列表中下一个元素的 count 作为 previous（模拟“上一梯队”的热度）
            # 如果是最后一个元素，则对比前一个
            next_idx = idx + 1 if idx < len(top_topics) - 1 else idx - 1
            previous_count = top_topics[next_idx][1]
        else:
            previous_count = 0

        direction = trend_direction(count, previous_count)

        # --- D. 组装结果  ---
        results.append({
            "topic": topic,
            "score": final_score,
            "direction": direction,
        })
    return results

