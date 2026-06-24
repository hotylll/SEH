"""真实数据采集模块

通过 SearXNG + Exa MCP 双引擎搜索 + 网页内容抓取，替代 Mock 数据池。
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

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


# ═══════════════════════════════════════════
#  Exa MCP 客户端
# ═══════════════════════════════════════════

class ExaMCPClient:
    """通过 MCP 协议调用 Exa 搜索服务的轻量客户端。

    用法:
        client = ExaMCPClient(api_key="...")
        results = client.search("人工智能", num_results=5)
    """

    _MCP_URL = "https://mcp.exa.ai/mcp"
    _PROTOCOL_VERSION = "2024-11-05"

    def __init__(self, api_key: str | None = None) -> None:
        self._session_id: str | None = None
        self._headers: dict[str, str] = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if api_key:
            self._headers["x-api-key"] = api_key

    # ── 底层 MCP 调用 ──────────────────────

    def _sse_post(self, body: dict[str, object]) -> dict[str, object] | None:
        """发送 JSON-RPC 请求，从 SSE 流中解析 data 事件。"""
        headers = dict(self._headers)
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        try:
            resp = requests.post(
                self._MCP_URL,
                json=body,
                headers=headers,
                stream=True,
                timeout=30,
            )
            # 首次请求时保存 Session ID
            if self._session_id is None:
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    self._session_id = sid
            # 解析 SSE 行
            for raw in resp.iter_lines():
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if line.startswith("data: "):
                    return json.loads(line[6:])
            return None  # 没有 data 事件
        except (requests.RequestException, json.JSONDecodeError) as exc:
            print(f"[crawler] Exa MCP 请求失败: {exc}")
            return None

    def initialize(self) -> bool:
        """初始化 MCP 会话。"""
        resp = self._sse_post({
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": self._PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "jisi-crawler", "version": "1.0.0"},
            },
            "id": 1,
        })
        if resp and "result" in resp:
            return True
        return False

    def search(
        self,
        query: str,
        num_results: int = 10,
    ) -> list[dict[str, str]]:
        """调用 web_search_exa 工具进行搜索。

        返回:
            [{title, content, url}, ...]
        """
        if self._session_id is None:
            if not self.initialize():
                return []

        resp = self._sse_post({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "web_search_exa",
                "arguments": {
                    "query": query,
                    "numResults": num_results,
                },
            },
            "id": 2,
        })
        if resp is None or "result" not in resp:
            return []

        content_list = resp["result"].get("content", [])
        results: list[dict[str, str]] = []
        seen_urls: set[str] = set()

        for entry in content_list:
            text = entry.get("text", "")
            if not text:
                continue
            # 解析 Exa 返回的文本格式
            title = ""
            url = ""
            body = text
            for line in text.split("\n"):
                if line.startswith("Title: "):
                    title = line[7:].strip()
                elif line.startswith("URL: "):
                    url = line[5:].strip()
                elif line.startswith("Highlights:"):
                    # 摘要在 Highlights: 后面
                    body = text[text.index("Highlights:") + 11:].strip()
                    break
            if not url or not title or url in seen_urls:
                continue
            seen_urls.add(url)
            results.append({
                "title": title,
                "content": body if body else title,
                "url": url,
            })

        return results


# ── 全局 Exa 客户端（惰性初始化） ──

_exa_client: ExaMCPClient | None = None


def _get_exa_client() -> ExaMCPClient:
    global _exa_client
    if _exa_client is None:
        api_key = os.environ.get("EXA_API_KEY")
        _exa_client = ExaMCPClient(api_key=api_key or None)
    return _exa_client


# ═══════════════════════════════════════════
#  通用工具
# ═══════════════════════════════════════════

def _get_session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update({"User-Agent": _USER_AGENT})
    return _SESSION


def _domain_of(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
        return host.removeprefix("www.")
    except Exception:
        return ""


# ═══════════════════════════════════════════
#  SearXNG 引擎
# ═══════════════════════════════════════════

def search_searxng(
    keywords: list[str],
    base_url: str,
    max_results: int = 10,
) -> list[dict[str, str]]:
    """通过 SearXNG JSON API 搜索关键词。"""
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


# ═══════════════════════════════════════════
#  网页抓取
# ═══════════════════════════════════════════

def crawl_page(url: str, max_chars: int = 1500) -> str | None:
    """抓取单个网页，提取正文纯文本。"""
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


# ═══════════════════════════════════════════
#  Endpoint 判断
# ═══════════════════════════════════════════

def is_searxng_endpoint(endpoint: str) -> bool:
    """判断 endpoint 是否为可用的 SearXNG 实例地址。"""
    ep = endpoint.strip()
    if not ep.startswith("http"):
        return False
    if "example.com" in ep or "mcp.exa" in ep:
        return False
    return True


def is_exa_endpoint(endpoint: str) -> bool:
    """判断 endpoint 是否为 Exa MCP 搜索。"""
    ep = endpoint.strip().lower()
    return "exa" in ep or "mcp.exa" in ep


# ═══════════════════════════════════════════
#  高层采集函数
# ═══════════════════════════════════════════

def collect_from_searxng(
    source: dict[str, Any],
    max_items: int = 8,
) -> list[tuple[str, str, str, str]]:
    """从 SearXNG 采集真实数据。"""
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
        if len(content) < 80:
            full = crawl_page(r["url"])
            if full:
                content = full
        items.append((r["title"], content, r["url"], now.isoformat()))

    return items


def collect_from_exa(
    source: dict[str, Any],
    max_items: int = 8,
) -> list[tuple[str, str, str, str]]:
    """从 Exa MCP 采集真实数据。"""
    keywords_str = source.get("keywords") or ""
    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
    if not keywords:
        keywords = ["信息科技"]

    client = _get_exa_client()
    now = datetime.now(timezone.utc)
    items: list[tuple[str, str, str, str]] = []
    seen_urls: set[str] = set()

    for kw in keywords:
        if len(items) >= max_items:
            break
        try:
            results = client.search(kw, num_results=min(5, max_items - len(items) + 2))
            for r in results:
                url = r["url"]
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                content = r["content"]
                if len(content) < 80:
                    full = crawl_page(r["url"])
                    if full:
                        content = full
                items.append((r["title"], content, url, now.isoformat()))
        except Exception as exc:
            print(f"[crawler] Exa 搜索失败 '{kw}': {exc}")

    return items
