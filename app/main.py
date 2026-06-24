from __future__ import annotations

import argparse
import os
from http.server import ThreadingHTTPServer
from pathlib import Path

from app.api import ApiHandler
from app.storage import Repository


def _load_dotenv() -> None:
    """自动加载 .env 文件（如果存在）。"""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and value and not os.environ.get(key):
            os.environ[key] = value


def create_server(host: str = "127.0.0.1", port: int = 8000, db_path: str = "data/app.db") -> ThreadingHTTPServer:
    repository = Repository(db_path)
    repository.seed_demo()
    ApiHandler.repository = repository
    return ThreadingHTTPServer((host, port), ApiHandler)


def main() -> None:
    _load_dotenv()
    parser = argparse.ArgumentParser(description="集思 · 信息收集整合系统后端服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--db", default="data/app.db")
    args = parser.parse_args()

    server = create_server(args.host, args.port, args.db)
    print(f"server running at http://{args.host}:{args.port}")
    print("health check: /api/v1/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("server stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
