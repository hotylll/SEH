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

    for attempt in range(2):
        try:
            resp = session.post(url, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return str(data["choices"][0]["message"]["content"])
        except requests.RequestException as exc:
            # 主模型失败，尝试回退模型
            if attempt == 0 and model is None:
                print(f"[llm] 主模型失败，尝试回退模型: {exc}")
                payload["model"] = FALLBACK_MODEL
                continue
            raise RuntimeError(f"AI 分析失败: {exc}") from exc
        except (KeyError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"AI 响应解析失败: {exc}") from exc

    return ""


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
