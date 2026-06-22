from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator
from typing import Any

from app.analysis import calculate_trends, clean_raw_item, content_hash
from app.schemas import DataSource, RawItem, utc_now


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'enabled',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS data_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    keywords TEXT,
    schedule TEXT,
    status TEXT NOT NULL DEFAULT 'enabled',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collect_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    task_status TEXT NOT NULL,
    success_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY(source_id) REFERENCES data_sources(id)
);

CREATE TABLE IF NOT EXISTS raw_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    url TEXT,
    author TEXT,
    published_at TEXT,
    raw_hash TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(source_id) REFERENCES data_sources(id),
    FOREIGN KEY(task_id) REFERENCES collect_tasks(id)
);

CREATE TABLE IF NOT EXISTS clean_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_id INTEGER UNIQUE NOT NULL,
    normalized_title TEXT NOT NULL,
    normalized_content TEXT,
    keywords TEXT,
    quality_score REAL NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(raw_id) REFERENCES raw_items(id)
);

CREATE TABLE IF NOT EXISTS topic_trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    score REAL NOT NULL,
    direction TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_name TEXT NOT NULL,
    report_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    generated_by TEXT NOT NULL,
    generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id INTEGER,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_items_source_time ON raw_items(source_id, published_at);
CREATE INDEX IF NOT EXISTS idx_clean_items_quality ON clean_items(quality_score);
CREATE INDEX IF NOT EXISTS idx_topic_trends_topic_period ON topic_trends(topic, period_start, period_end);
"""


DEMO_ITEMS = [
    (
        "人工智能 助力 城市治理 热点上升",
        "多地开始使用人工智能技术整理政务公开信息，辅助城市管理者发现热点问题并生成趋势报告。",
        "https://example.com/news/ai-city",
        "2026-06-15T08:00:00+00:00",
    ),
    (
        "新能源汽车 市场 数据 持续增长",
        "公开报道显示新能源汽车相关讨论在近七天持续增长，用户关注续航、补能和价格变化。",
        "https://example.com/news/ev-market",
        "2026-06-16T08:00:00+00:00",
    ),
    (
        "高校 软件工程 课程 强调 文档规范",
        "软件工程课程要求学生按国家标准完成需求、设计、测试和总结文档，体现工程过程管理能力。",
        "https://example.com/forum/software-docs",
        "2026-06-17T08:00:00+00:00",
    ),
    (
        "人工智能 趋势 分析 平台 受到关注",
        "趋势分析平台通过采集、清洗、存储和可视化帮助用户快速理解多源信息。",
        "https://example.com/api/trend-ai",
        "2026-06-18T08:00:00+00:00",
    ),
]


class Repository:
    def __init__(self, db_path: Path | str = "data/app.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.session() as conn:
            conn.executescript(SCHEMA)
            if not conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                conn.execute(
                    "INSERT INTO users(username, password_hash, role, status, created_at) VALUES(?,?,?,?,?)",
                    ("admin", "demo-password-hash", "admin", "enabled", utc_now()),
                )

    def create_source(self, source: DataSource) -> dict[str, Any]:
        with self.session() as conn:
            cursor = conn.execute(
                """
                INSERT INTO data_sources(name, source_type, endpoint, keywords, schedule, status, created_at)
                VALUES(?,?,?,?,?,?,?)
                """,
                (source.name, source.source_type, source.endpoint, source.keywords, source.schedule, source.status, utc_now()),
            )
            source_id = int(cursor.lastrowid)
            self._audit(conn, "create_source", "data_sources", source_id)
            row = conn.execute("SELECT * FROM data_sources WHERE id = ?", (source_id,)).fetchone()
            return dict(row)

    def list_sources(self, source_type: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM data_sources WHERE 1=1"
        params: list[Any] = []
        if source_type:
            sql += " AND source_type = ?"
            params.append(source_type)
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY id DESC"
        with self.session() as conn:
            return [dict(row) for row in conn.execute(sql, params)]

    def get_source(self, source_id: int) -> dict[str, Any]:
        with self.session() as conn:
            row = conn.execute("SELECT * FROM data_sources WHERE id = ?", (source_id,)).fetchone()
            if row is None:
                raise ValueError(f"source {source_id} not found")
            return dict(row)

    def start_collect_task(self, source_id: int) -> dict[str, Any]:
        source = self.get_source(source_id)
        now = utc_now()
        with self.session() as conn:
            cursor = conn.execute(
                "INSERT INTO collect_tasks(source_id, task_status, started_at) VALUES(?,?,?)",
                (source_id, "running", now),
            )
            task_id = int(cursor.lastrowid)
            success_count = 0
            for title, content, url, published_at in DEMO_ITEMS:
                raw = RawItem(
                    source_id=source_id,
                    task_id=task_id,
                    title=title,
                    content=content,
                    url=url,
                    published_at=published_at,
                    author=source["name"],
                )
                if self._insert_raw_and_clean(conn, raw):
                    success_count += 1
            conn.execute(
                """
                UPDATE collect_tasks
                SET task_status = ?, success_count = ?, failed_count = ?, finished_at = ?
                WHERE id = ?
                """,
                ("success", success_count, len(DEMO_ITEMS) - success_count, utc_now(), task_id),
            )
            self.rebuild_trends(conn)
            self._audit(conn, "start_collect_task", "collect_tasks", task_id)
        return self.get_task(task_id)

    def get_task(self, task_id: int) -> dict[str, Any]:
        with self.session() as conn:
            row = conn.execute("SELECT * FROM collect_tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise ValueError(f"task {task_id} not found")
            return dict(row)

    def list_items(self, keyword: str | None = None, source_id: int | None = None, limit: int = 50) -> list[dict[str, Any]]:
        sql = """
            SELECT raw_items.id, raw_items.source_id, raw_items.title, raw_items.url, raw_items.published_at,
                   clean_items.normalized_title, clean_items.keywords, clean_items.quality_score
            FROM raw_items
            JOIN clean_items ON clean_items.raw_id = raw_items.id
            WHERE 1=1
        """
        params: list[Any] = []
        if keyword:
            sql += " AND (raw_items.title LIKE ? OR raw_items.content LIKE ? OR clean_items.keywords LIKE ?)"
            like = f"%{keyword}%"
            params.extend([like, like, like])
        if source_id:
            sql += " AND raw_items.source_id = ?"
            params.append(source_id)
        sql += " ORDER BY raw_items.published_at DESC LIMIT ?"
        params.append(limit)
        with self.session() as conn:
            return [dict(row) for row in conn.execute(sql, params)]

    def get_item(self, item_id: int) -> dict[str, Any]:
        with self.session() as conn:
            row = conn.execute(
                """
                SELECT raw_items.*, clean_items.normalized_title, clean_items.normalized_content,
                       clean_items.keywords, clean_items.quality_score
                FROM raw_items
                JOIN clean_items ON clean_items.raw_id = raw_items.id
                WHERE raw_items.id = ?
                """,
                (item_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"item {item_id} not found")
            return dict(row)

    def list_trends(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.session() as conn:
            rows = conn.execute(
                """
                SELECT topic, score, direction, period_start, period_end
                FROM topic_trends
                ORDER BY score DESC, topic ASC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in rows]

    def create_report(self, report_type: str = "summary", generated_by: str = "组长") -> dict[str, Any]:
        name = f"{PROJECT_REPORT_PREFIX}-{utc_now()}.{report_type}"
        path = f"reports/{name}"
        with self.session() as conn:
            cursor = conn.execute(
                "INSERT INTO reports(report_name, report_type, file_path, generated_by, generated_at) VALUES(?,?,?,?,?)",
                (name, report_type, path, generated_by, utc_now()),
            )
            report_id = int(cursor.lastrowid)
            self._audit(conn, "create_report", "reports", report_id)
            row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
            return dict(row)

    def health(self) -> dict[str, Any]:
        with self.session() as conn:
            conn.execute("SELECT 1").fetchone()
            return {
                "status": "ok",
                "db": str(self.db_path),
                "version": "1.0.0",
                "time": utc_now(),
            }

    def seed_demo(self) -> None:
        self.initialize()
        if self.list_sources():
            return
        source = self.create_source(
            DataSource(
                name="演示数据源",
                source_type="news",
                endpoint="https://example.com/demo",
                keywords="人工智能,新能源汽车,软件工程",
            )
        )
        self.start_collect_task(int(source["id"]))

    def rebuild_trends(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            SELECT clean_items.keywords, raw_items.published_at
            FROM clean_items
            JOIN raw_items ON raw_items.id = clean_items.raw_id
            """
        ).fetchall()
        trends = calculate_trends(dict(row) for row in rows)
        # 从数据中自动提取统计周期
        dates = [str(row["published_at"] or utc_now())[:10] for row in rows]
        period_start = min(dates) if dates else utc_now()[:10]
        period_end = max(dates) if dates else utc_now()[:10]
        conn.execute("DELETE FROM topic_trends")
        now = utc_now()
        for trend in trends:
            conn.execute(
                """
                INSERT INTO topic_trends(topic, score, direction, period_start, period_end, created_at)
                VALUES(?,?,?,?,?,?)
                """,
                (trend["topic"], trend["score"], trend["direction"], period_start, period_end, now),
            )

    def _insert_raw_and_clean(self, conn: sqlite3.Connection, raw: RawItem) -> bool:
        raw_hash = content_hash(raw.title, raw.content, raw.url)
        try:
            cursor = conn.execute(
                """
                INSERT INTO raw_items(source_id, task_id, title, content, url, author, published_at, raw_hash, created_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    raw.source_id,
                    raw.task_id,
                    raw.title,
                    raw.content,
                    raw.url,
                    raw.author,
                    raw.published_at,
                    raw_hash,
                    utc_now(),
                ),
            )
        except sqlite3.IntegrityError:
            return False
        raw_id = int(cursor.lastrowid)
        clean = clean_raw_item(raw)
        conn.execute(
            """
            INSERT INTO clean_items(raw_id, normalized_title, normalized_content, keywords, quality_score, created_at)
            VALUES(?,?,?,?,?,?)
            """,
            (
                raw_id,
                clean["normalized_title"],
                clean["normalized_content"],
                clean["keywords"],
                clean["quality_score"],
                utc_now(),
            ),
        )
        return True

    def _audit(self, conn: sqlite3.Connection, action: str, target_type: str, target_id: int) -> None:
        conn.execute(
            "INSERT INTO audit_logs(action, target_type, target_id, created_at) VALUES(?,?,?,?)",
            (action, target_type, target_id, utc_now()),
        )


PROJECT_REPORT_PREFIX = "trend-report"
