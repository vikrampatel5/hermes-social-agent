import sqlite3
from pathlib import Path

from database import Database


def test_database_creates_schema_and_persists_rows(tmp_path):
    db = Database(str(tmp_path / "state.db"))
    try:
        platform_id = db.insert(
            "platforms",
            {"name": "youtube", "url": "https://youtube.com", "enabled": 1},
        )
        query_id = db.insert(
            "search_queries",
            {"query": "stock screening", "platform_id": platform_id, "created_at": "2026-09-13T00:00:00Z"},
        )
        content_id = db.insert(
            "content_items",
            {
                "platform_id": platform_id,
                "platform_name": "youtube",
                "url": "https://youtube.com/watch?v=test",
                "title": "How to screen stocks",
                "description": "A useful investing tutorial",
                "discovered_at": "2026-09-13T00:00:00Z",
                "status": "discovered",
                "search_query_id": query_id,
                "relevance_score": 92,
                "stockscribe_fit_score": 87,
                "audience_fit_score": 94,
                "comment_value_score": 88,
                "spam_risk_score": 7,
                "conversion_potential_score": 82,
                "creator_quality_score": 90,
                "overall_score": 88,
            },
        )

        assert platform_id == 1
        assert query_id == 1
        assert content_id == 1
        row = db.select("SELECT title, status, relevance_score FROM content_items WHERE id = ?", (content_id,))[0]
        assert dict(row) == {
            "title": "How to screen stocks",
            "status": "discovered",
            "relevance_score": 92.0,
        }

        db.update("content_items", {"id": content_id}, {"status": "qualified"})
        row = db.select("SELECT status FROM content_items WHERE id = ?", (content_id,))[0]
        assert row["status"] == "qualified"
    finally:
        db.close()


def test_database_uses_wal_and_foreign_keys(tmp_path):
    db = Database(str(tmp_path / "state.db"))
    try:
        journal_mode = db.select("PRAGMA journal_mode")[0][0]
        foreign_keys = db.select("PRAGMA foreign_keys")[0][0]
        assert journal_mode == "wal"
        assert foreign_keys == 1
    finally:
        db.close()
