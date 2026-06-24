"""真实数据采集模块

通过 SearXNG 搜索引擎检索 + 网页内容抓取，替代 Mock 数据池。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# 已知会屏蔽爬虫或超时的域名，直接跳过爬取
_BLOCKED_DOMAINS = {
    "baike.baidu.com",
    "car.autohome.com.cn",
    "www.autohome.com.cn",
}

_SESSION: requests.Session | None = None


def _get_session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update({"User-Agent": _USER_AGENT})
    return _SESSION


def _domain_of(url: str) -> str:
    """从 URL 中提取域名。"""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).hostname or ""
        return host.removeprefix("www.")
    except Exception:
        return ""


def search_searxng(
    keywords: list[str],
    base_url: str,
    max_results: int = 10,
) -> list[dict[str, str]]:
    """通过 SearXNG JSON API 搜索关键词。

    参数:
        keywords: 关键词列表
        base_url: SearXNG 实例地址（如 https://your-searxng-instance.com）
        max_results: 最多返回结果数

    返回:
        [{title, content, url, keyword}, ...]
    """
    results: list[dict[str, str]] = []
    session = _get_session()
    seen_urls: set[str] = set()

    for kw in keywords:
        if len(results) >= max_results:
            break
        try:
            resp = session.get(
                f"{base_url.rstrip('/')}/search",
                params={"q": kw, "format": "json", "language": "zh-CN", "pageno": 1},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("results", []):
                url = item.get("url", "")
                title = item.get("title", "")
                content = item.get("content", "")
                if not url or not title or url in seen_urls:
                    continue
                seen_urls.add(url)
                results.append({
                    "title": title,
                    "content": content or "(暂无摘要)",
                    "url": url,
                    "keyword": kw,
                })
                if len(results) >= max_results:
                    break
        except requests.RequestException as exc:
            print(f"[crawler] SearXNG 搜索失败 '{kw}': {exc}")

    return results


def crawl_page(url: str, max_chars: int = 1500) -> str | None:
    """抓取单个网页，提取正文纯文本。

    参数:
        url: 目标网页 URL
        max_chars: 最多提取字符数

    返回:
        提取的纯文本，失败返回 None（用原标题+摘要兜底）
    """
    domain = _domain_of(url)
    if domain in _BLOCKED_DOMAINS:
        return None

    try:
        resp = _get_session().get(url, timeout=5)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n".join(lines)[:max_chars]
    except requests.RequestException as exc:
        print(f"[crawler] 页面抓取失败 {url}: {exc}")
        return None


def is_searxng_endpoint(endpoint: str) -> bool:
    """判断 endpoint 是否为可用的 SearXNG 实例地址。"""
    endpoint = endpoint.strip()
    if not endpoint.startswith("http"):
        return False
    if "example.com" in endpoint:
        return False
    return True


def collect_from_searxng(
    source: dict[str, Any],
    max_items: int = 8,
) -> list[tuple[str, str, str, str]]:
    """从 SearXNG 采集真实数据。

    参数:
        source: 数据源字典（需含 keywords, endpoint）
        max_items: 最多采集数

    返回:
        [(title, content, url, published_at), ...]
    """
    keywords_str = source.get("keywords") or ""
    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
    if not keywords:
        keywords = ["信息科技"]

    base_url = source.get("endpoint", "").strip()
    if not base_url or not is_searxng_endpoint(base_url):
        return []

    search_results = search_searxng(keywords, base_url, max_results=max_items)
    now = datetime.now(timezone.utc)
    items: list[tuple[str, str, str, str]] = []

    for r in search_results:
        content = r["content"]
        # 如果摘要很短（<80字符），尝试抓取全文；跳过已知屏蔽的域名
        if len(content) < 80:
            full = crawl_page(r["url"])
            if full:
                content = full
        items.append((r["title"], content, r["url"], now.isoformat()))

    return items
