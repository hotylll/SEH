"""AI 分析模块

通过 OpenAI 兼容格式的 API 对搜索结果进行智能分析。
"""

from __future__ import annotations

import json
import os
from typing import Any

import requests

# ── 配置（必须通过环境变量设置 AI_API_KEY） ──

DEFAULT_API_BASE = "https://clip.ranai.cc.cd/v1"
DEFAULT_MODEL = "z-ai/glm5.1"
FALLBACK_MODEL = "deepseek-v4-flash-free"

_SESSION: requests.Session | None = None


def _get_session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.timeout = (10, 60)
    return _SESSION


def _config() -> dict[str, str]:
    api_key = os.environ.get("AI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "缺少 AI_API_KEY 环境变量。\n"
            "请设置: $env:AI_API_KEY='your-api-key'"
        )
    return {
        "api_base": os.environ.get("AI_API_BASE", DEFAULT_API_BASE).rstrip("/"),
        "api_key": api_key,
        "model": os.environ.get("AI_MODEL", DEFAULT_MODEL),
    }


def _call_llm(
    messages: list[dict[str, str]],
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> str:
    """调用 OpenAI 兼容 API。"""
    cfg = _config()
    session = _get_session()
    url = f"{cfg['api_base']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }

    payload: dict[str, Any] = {
        "model": model or cfg["model"],
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }

    # 不同用途超时：分析60s，过滤10s
    request_timeout = 10 if max_tokens <= 1024 else 60

    for attempt in range(2):
        try:
            resp = session.post(url, json=payload, headers=headers, timeout=request_timeout)
            resp.raise_for_status()
            data = resp.json()
            return str(data["choices"][0]["message"]["content"])
        except requests.RequestException as exc:
            if attempt == 0 and model is None:
                print(f"[llm] 主模型失败，尝试回退模型: {exc}")
                payload["model"] = FALLBACK_MODEL
                continue
            raise RuntimeError(f"AI 分析失败: {exc}") from exc
        except (KeyError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"AI 响应解析失败: {exc}") from exc

    return ""


def filter_trend_topics(
    topics: list[dict[str, object]],
    max_topics: int = 20,
) -> list[dict[str, object]]:
    """过滤无意义的趋势热词。

    默认使用规则过滤（快速可靠）。
    设置环境变量 AI_FILTER=1 可启用 AI 辅助增强。
    """
    if not topics:
        return topics

    # 规则快速过滤
    filtered = _rule_filter_topics(topics, max_topics * 2)

    # AI 辅助过滤（默认关闭，需设置 AI_FILTER=1）
    if os.environ.get("AI_FILTER") == "1":
        try:
            ai_filtered = _ai_filter_topics(filtered, max_topics)
            return ai_filtered
        except Exception as exc:
            print(f"[llm] AI 增强过滤跳过: {exc}")

    return filtered[:max_topics]


def _rule_filter_topics(
    topics: list[dict[str, object]],
    max_topics: int = 20,
) -> list[dict[str, object]]:
    """纯规则过滤掉无意义热词。"""
    # 无意义模式（大小写不敏感）
    _GARBAGE_PATTERNS = (
        r"^(教程|菜鸟教程|本教程介绍了|首页|导航|菜单|搜索)$",
        r"^(维基百科|自由的百科全书|百度百科|知乎|博客园|CSDN)$",
        r"^(汽车之家|国际会议云|电子工程世界|澎湃新闻|36氪|界面新闻)$",
        r"^[^a-zA-Z\u4e00-\u9fff]{2,}$",
        r"^[a-z]{1,3}$",
        r"^[零一二三四五六七八九十\d]{1,4}年?$",
        r"^\d{4}年\d{1,2}月\d{1,2}日$",
        r"^(language|science|english|中文|英文|日本語|한국어|英語)$",
        r"^(artificial|intelligence|welcome|home|page|powered|designed)$",
        r"^(该词也指出|通常人工智能是指|系统梳理AI的|英文缩写为AI|因此)$",
        r"^[年月日时分秒]{1,4}$",
        r"^.{15,}.*[（(].*[）)].*$",
        r"^.*[、，。！？].*[、，。！？].*[、，。！？].+$",
        r"^(什么是|如何|怎样|怎么|为什么|哪些|哪个).{10,}",
        r"^.*[。？].+$",
    )
    import re
    compiled = [re.compile(p, re.IGNORECASE) for p in _GARBAGE_PATTERNS]

    filtered = []
    for t in topics:
        topic = str(t["topic"]).strip()
        if not topic or len(topic) <= 1:
            continue
        is_garbage = any(p.match(topic) for p in compiled)
        if is_garbage:
            continue
        filtered.append(t)

    return filtered[:max_topics] if filtered else topics[:max_topics]


def _ai_filter_topics(
    topics: list[dict[str, object]],
    max_topics: int = 20,
) -> list[dict[str, object]]:
    """AI 审核热词（短超时）。"""
    if not topics:
        return topics

    topic_names = [t["topic"] for t in topics]
    prompt = (
        f"从以下热词中剔除无意义的网页模板词、导航词、站名词、停用词、无意义短语。"
        f"只保留有实际含义的词。\n热词：{json.dumps(topic_names, ensure_ascii=False)}\n"
        "返回 JSON 数组，如 [\"人工智能\",\"Python\"]"
    )
    messages = [
        {"role": "system", "content": "只返回 JSON 数组，不解释。"},
        {"role": "user", "content": prompt},
    ]
    import os as _os
    _old = _os.environ.get("AI_MODEL")
    _os.environ["AI_MODEL"] = "z-ai/glm5.1"
    try:
        raw = _call_llm(messages, max_tokens=512, temperature=0.1)
    finally:
        if _old:
            _os.environ["AI_MODEL"] = _old
        else:
            _os.environ.pop("AI_MODEL", None)
    raw = (raw or "").strip()
    # 提取 JSON
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    kept: list[str] = json.loads(raw)
    if not isinstance(kept, list):
        return topics[:max_topics]
    kept_set = {t.strip() for t in kept if t.strip()}
    filtered = [t for t in topics if t["topic"] in kept_set]
    return filtered[:max_topics] if filtered else topics[:max_topics]


def analyze_topic(
    topic: str,
    search_results: list[dict[str, str]],
) -> str:
    """对搜索到的信息进行 AI 分析。

    参数:
        topic: 用户输入的主题
        search_results: [{title, content, url}, ...]

    返回:
        Markdown 格式的分析报告
    """
    # 整理搜索结果摘要
    context_parts: list[str] = []
    for i, r in enumerate(search_results, 1):
        title = r.get("title", "无标题")
        content = r.get("content", "无内容")[:500]
        url = r.get("url", "")
        context_parts.append(f"[{i}] {title}\n   来源: {url}\n   摘要: {content}")

    context = "\n\n".join(context_parts) if context_parts else "（未找到相关结果）"

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个专业的信息分析助手。你的任务是根据用户提供的主题和搜索结果，"
                "生成一份结构清晰、有深度的分析报告。\n\n"
                "请按以下格式输出：\n"
                "## 📊 主题概述\n"
                "一句话概括该主题的核心内容。\n\n"
                "## 🔍 关键发现\n"
                "- 发现1\n"
                "- 发现2\n\n"
                "## 📈 趋势分析\n"
                "分析该主题的发展趋势和热度变化。\n\n"
                "## 💡 核心观点\n"
                "提炼出最有价值的观点和见解。\n\n"
                "## 🔗 参考来源\n"
                "列出分析中引用的信息来源。\n\n"
                "请用中文回答，语言简洁专业。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"## 分析主题\n{topic}\n\n"
                f"## 全网搜索结果\n{context}\n\n"
                "请基于以上搜索结果，对该主题进行全面分析。"
            ),
        },
    ]

    return _call_llm(messages)
