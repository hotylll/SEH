from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer

from app.api import ApiHandler
from app.storage import Repository


def create_server(host: str = "127.0.0.1", port: int = 8000, db_path: str = "data/app.db") -> ThreadingHTTPServer:
    repository = Repository(db_path)
    repository.seed_demo()
    ApiHandler.repository = repository
    return ThreadingHTTPServer((host, port), ApiHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description="信息收集整合系统后端服务")
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

