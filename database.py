"""SQLite-backed persistence with PostgreSQL fallback.

Schema mirrors the spec's PostgreSQL design (WAL + FKs + indexes).
PostgreSQL is activated by DATABASE_URL starting with postgresql://.
"""

import os
import sqlite3
import psycopg2
import psycopg2.extras
from datetime import datetime
from pathlib import Path

class Database:
    def __init__(self, db_path: str = "data/state.db"):
        # If DATABASE_URL is PostgreSQL, use psycopg2 (takes precedence)
        pg_url = os.getenv("DATABASE_URL", "")
        if pg_url.startswith("postgresql://") or pg_url.startswith("postgres://"):
            self._postgre_init(pg_url)
            return
        # SQLite path (with URL stripping + Windows fix)
        if isinstance(db_path, str) and db_path.startswith("sqlite:///"):
            db_path = db_path[8:]
        db_path_str = str(db_path)
        if db_path_str.startswith("/") and not db_path_str.startswith("//"):
            db_path_str = db_path_str.lstrip("/")
        db_path_str = os.path.abspath(db_path_str)
        self.db_path = Path(db_path_str)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path.resolve()))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self._create_tables()

    def _postgre_init(self, url: str):
        # PostgreSQL connector (host=localhost, port=5433, user=postgres)
        # Password provided via DB_PASSWORD env var (never hardcoded).
        # DATABASE_URL is used only for the connection string; the
        # database itself is created if it does not already exist.
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        dbname = parsed.path[1:] if parsed.path else "hermes_social"
        host = parsed.hostname or "localhost"
        port = parsed.port or 5433
        user = parsed.username or "postgres"
        password = parsed.password or os.getenv("DB_PASSWORD", "")

        # Connect to the default maintenance database first, create target
        # database if missing, then (re)connect to it.
        admin_conn = psycopg2.connect(
            dbname="postgres",
            user=user,
            password=password,
            host=host,
            port=port,
        )
        admin_conn.set_session(autocommit=True)
        admin_cur = admin_conn.cursor()
        admin_cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
        if not admin_cur.fetchone():
            admin_cur.execute("CREATE DATABASE %s", (dbname,))
        admin_conn.close()

        # Now connect to the target database
        self.conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port,
        )
        self.conn.set_session(autocommit=False)
        self._create_tables_pg()
        self.db_path = Path(url.replace("://", "/").replace("/", "_"))

    def _create_tables_pg(self):
        # PostgreSQL-compatible schema (same columns, using SERIAL for PKs)
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                website TEXT,
                target TEXT,
                geography TEXT,
                topics TEXT,
                cta_style TEXT,
                comment_style TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS platforms (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT,
                enabled INTEGER DEFAULT 1
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id SERIAL PRIMARY KEY,
                platform_id INTEGER,
                platform_name TEXT,
                username TEXT,
                url TEXT,
                followers INTEGER,
                enabled INTEGER DEFAULT 1
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS search_queries (
                id SERIAL PRIMARY KEY,
                query TEXT NOT NULL,
                platform_id INTEGER,
                created_at TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS content_items (
                id SERIAL PRIMARY KEY,
                platform_id INTEGER,
                platform_name TEXT,
                url TEXT,
                title TEXT,
                description TEXT,
                transcript TEXT,
                published_date TEXT,
                creator_id INTEGER,
                keywords TEXT,
                search_query_id INTEGER,
                discovered_at TIMESTAMP,
                status TEXT DEFAULT 'discovered',
                relevance_score REAL DEFAULT 0,
                stockscribe_fit_score REAL DEFAULT 0,
                audience_fit_score REAL DEFAULT 0,
                comment_value_score REAL DEFAULT 0,
                spam_risk_score REAL DEFAULT 0,
                conversion_potential_score REAL DEFAULT 0,
                creator_quality_score REAL DEFAULT 0,
                overall_score REAL DEFAULT 0
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id SERIAL PRIMARY KEY,
                content_item_id INTEGER,
                comment_text TEXT,
                strategy_id INTEGER,
                created_at TIMESTAMP,
                published INTEGER DEFAULT 0,
                quality_score REAL DEFAULT 0,
                spam_risk REAL DEFAULT 0,
                conversion_rate REAL DEFAULT 0,
                clicks INTEGER DEFAULT 0,
                signups INTEGER DEFAULT 0,
                created_by INTEGER,
                platform TEXT,
                creator_id INTEGER,
                tracking_url TEXT,
                status TEXT DEFAULT 'generated'
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS comment_strategies (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                example TEXT,
                weight REAL DEFAULT 0.2
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS learning (
                id SERIAL PRIMARY KEY,
                strategy_id INTEGER,
                metric TEXT,
                trend REAL,
                updated_at TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS campaigns_log (
                id SERIAL PRIMARY KEY,
                campaign_id INTEGER,
                action TEXT,
                timestamp TIMESTAMP,
                details TEXT
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_content_items_platform ON content_items(platform_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_content_items_search_query ON content_items(search_query_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_content_items_status ON content_items(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_comments_content_item ON comments(content_item_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_comments_created_at ON comments(created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_comments_quality ON comments(quality_score)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_comments_spam_risk ON comments(spam_risk)")
        self.conn.commit()

    def _create_tables(self):
        cur = self.conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                website TEXT,
                target TEXT,
                geography TEXT,
                topics TEXT,
                cta_style TEXT,
                comment_style TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS platforms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT,
                enabled INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform_id INTEGER,
                platform_name TEXT,
                username TEXT,
                url TEXT,
                followers INTEGER,
                enabled INTEGER DEFAULT 1,
                FOREIGN KEY (platform_id) REFERENCES platforms(id)
            );
            CREATE TABLE IF NOT EXISTS search_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                platform_id INTEGER,
                created_at TEXT,
                FOREIGN KEY (platform_id) REFERENCES platforms(id)
            );
            CREATE TABLE IF NOT EXISTS content_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform_id INTEGER,
                platform_name TEXT,
                url TEXT,
                title TEXT,
                description TEXT,
                transcript TEXT,
                published_date TEXT,
                creator_id INTEGER,
                keywords TEXT,
                search_query_id INTEGER,
                discovered_at TEXT,
                status TEXT DEFAULT 'discovered',
                relevance_score REAL DEFAULT 0,
                stockscribe_fit_score REAL DEFAULT 0,
                audience_fit_score REAL DEFAULT 0,
                comment_value_score REAL DEFAULT 0,
                spam_risk_score REAL DEFAULT 0,
                conversion_potential_score REAL DEFAULT 0,
                creator_quality_score REAL DEFAULT 0,
                overall_score REAL DEFAULT 0,
                FOREIGN KEY (platform_id) REFERENCES platforms(id),
                FOREIGN KEY (creator_id) REFERENCES accounts(id),
                FOREIGN KEY (search_query_id) REFERENCES search_queries(id)
            );
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_item_id INTEGER,
                comment_text TEXT,
                strategy_id INTEGER,
                created_at TEXT,
                published INTEGER DEFAULT 0,
                quality_score REAL DEFAULT 0,
                spam_risk REAL DEFAULT 0,
                conversion_rate REAL DEFAULT 0,
                clicks INTEGER DEFAULT 0,
                signups INTEGER DEFAULT 0,
                created_by INTEGER,
                platform TEXT,
                creator_id INTEGER,
                tracking_url TEXT,
                status TEXT DEFAULT 'generated',
                FOREIGN KEY (content_item_id) REFERENCES content_items(id),
                FOREIGN KEY (strategy_id) REFERENCES comment_strategies(id),
                FOREIGN KEY (created_by) REFERENCES accounts(id),
                FOREIGN KEY (creator_id) REFERENCES accounts(id)
            );
            CREATE TABLE IF NOT EXISTS comment_strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                example TEXT,
                weight REAL DEFAULT 0.2
            );
            CREATE TABLE IF NOT EXISTS learning (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER,
                metric TEXT,
                trend REAL,
                updated_at TEXT,
                FOREIGN KEY (strategy_id) REFERENCES comment_strategies(id)
            );
            CREATE TABLE IF NOT EXISTS campaigns_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER,
                action TEXT,
                timestamp TEXT,
                details TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_content_items_platform ON content_items(platform_id);
            CREATE INDEX IF NOT EXISTS idx_content_items_search_query ON content_items(search_query_id);
            CREATE INDEX IF NOT EXISTS idx_content_items_status ON content_items(status);
            CREATE INDEX IF NOT EXISTS idx_comments_content_item ON comments(content_item_id);
            CREATE INDEX IF NOT EXISTS idx_comments_created_at ON comments(created_at);
            CREATE INDEX IF NOT EXISTS idx_comments_quality ON comments(quality_score);
            CREATE INDEX IF NOT EXISTS idx_comments_spam_risk ON comments(spam_risk);
        """)
        self.conn.commit()

    def execute(self, query, params=None):
        cur = self.conn.cursor()
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        self.conn.commit()
        return cur

    def select(self, query, params=None):
        cur = self.conn.cursor()
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        return cur.fetchall()

    def insert(self, table, data):
        if isinstance(self.conn, sqlite3.Connection):
            placeholders = ", ".join("?" for _ in data)
            query = f"INSERT INTO {table} ({', '.join(data.keys())}) VALUES ({placeholders})"
            values = tuple(data.values())
            cur = self.conn.cursor()
            cur.execute(query, values)
            self.conn.commit()
            return cur.lastrowid
        # PostgreSQL path (used when DATABASE_URL is postgresql://)
        columns = ", ".join(data.keys())
        placeholders = ", ".join("%s" for _ in data)
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING id"
        values = tuple(data.values())
        cur = self.conn.cursor()
        cur.execute(query, values)
        self.conn.commit()
        row = cur.fetchone()
        return row[0] if row else None

    def update(self, table, condition, data):
        if isinstance(self.conn, sqlite3.Connection):
            set_clause = ", ".join(f"{k} = ?" for k in data)
            where_clause = " AND ".join(f"{k} = ?" for k in condition)
            query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
            values = tuple(data.values()) + tuple(condition.values())
            cur = self.conn.cursor()
            cur.execute(query, values)
            self.conn.commit()
            return
        set_clause = ", ".join(f"{k} = %s" for k in data)
        where_clause = " AND ".join(f"{k} = %s" for k in condition)
        query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        values = tuple(data.values()) + tuple(condition.values())
        cur = self.conn.cursor()
        cur.execute(query, values)
        self.conn.commit()

    def delete(self, table, condition):
        where_clause = " AND ".join(f"{k} = %s" for k in condition)
        query = f"DELETE FROM {table} WHERE {where_clause}"
        cur = self.conn.cursor()
        cur.execute(query, tuple(condition.values()))
        self.conn.commit()

    def get_last_insert_id(self):
        if hasattr(self.conn, 'cursor') and hasattr(self.conn.cursor(), 'lastrowid'):
            return self.conn.cursor().lastrowid
        return None

    def close(self):
        self.conn.close()

    def row_to_dict(self, row):
        if row is None:
            return None
        # psycopg2 RealDictCursor or sqlite3.Row
        if hasattr(row, 'keys'):
            return dict(row)
        return dict(zip([d[0] for d in row.description], row)) if hasattr(row, 'description') else dict(row)
