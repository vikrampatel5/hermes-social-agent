"""SQLite-backed persistence for the Hermes social engagement agent.

Schema mirrors the spec's PostgreSQL design but uses SQLite so the
system runs without a separate database server on this VPS.
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path


class Database:
    def __init__(self, db_path: str = "data/state.db"):
        # Handle SQLite URL format: sqlite:///path/to/db
        if isinstance(db_path, str) and db_path.startswith("sqlite:///"):
            db_path = db_path[8:]  # Remove 'sqlite:///' prefix
        # Windows path fix: sqlite3 on Windows misinterprets absolute paths
        # that contain backslashes. Resolve to absolute before connecting.
        db_path_str = str(db_path)
        # If it starts with a drive-letter after stripping sqlite:///, resolve it
        if db_path_str.startswith("/") and not db_path_str.startswith("//"):
            db_path_str = db_path_str.lstrip("/")
        db_path_str = os.path.abspath(db_path_str)
        self.db_path = Path(db_path_str)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Pass absolute path string to sqlite3 (not Path object) for Windows compat
        self.conn = sqlite3.connect(str(self.db_path.resolve()))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self._create_tables()

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
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        values = tuple(data.values())
        cur = self.execute(query, values)
        return cur.lastrowid

    def update(self, table, condition, data):
        set_clause = ", ".join(f"{k} = ?" for k in data)
        where_clause = " AND ".join(f"{k} = ?" for k in condition)
        query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        values = tuple(data.values()) + tuple(condition.values())
        self.execute(query, values)

    def delete(self, table, condition):
        where_clause = " AND ".join(f"{k} = ?" for k in condition)
        query = f"DELETE FROM {table} WHERE {where_clause}"
        self.execute(query, tuple(condition.values()))

    def get_last_insert_id(self):
        return self.conn.lastrowid

    def close(self):
        self.conn.close()

    def row_to_dict(self, row):
        if row is None:
            return None
        return dict(row)