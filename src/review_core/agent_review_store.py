from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3
import uuid

from .database import connect_database


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


class AgentReviewStore:
    """Local SQLite history for reports returned by independent CLI reviewers."""

    def __init__(self, database: str | Path) -> None:
        self.database = Path(database).expanduser()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_reviews (
                    review_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    project_name TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    model TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_reviews_created "
                "ON agent_reviews(created_at DESC)"
            )

    def _connect(self) -> sqlite3.Connection:
        return connect_database(self.database)

    def save(
        self,
        *,
        project_id: str,
        project_name: str,
        agent_id: str,
        agent_name: str,
        model: str,
        content: str,
    ) -> str:
        for value, label in ((project_id, "project_id"), (agent_id, "agent_id")):
            if not isinstance(value, str) or not _ID.fullmatch(value):
                raise ValueError(f"{label} must be a safe identifier")
        for value, label in ((project_name, "project_name"), (agent_name, "agent_name"), (model, "model")):
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError(f"{label} must contain 1-256 characters")
        if not isinstance(content, str) or not content.strip() or len(content.encode("utf-8")) > 2 * 1024 * 1024:
            raise ValueError("report must contain 1-2097152 UTF-8 bytes")
        review_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO agent_reviews
                (review_id, project_id, project_name, agent_id, agent_name, model, content, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (review_id, project_id, project_name.strip(), agent_id, agent_name.strip(), model.strip(), content, created_at),
            )
        return review_id

    def list_reviews(self, *, limit: int = 200) -> list[dict[str, str]]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit must be an integer between 1 and 1000")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT review_id, project_id, project_name, agent_id, agent_name, model, created_at
                FROM agent_reviews
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, review_id: str) -> dict[str, str] | None:
        if not isinstance(review_id, str) or not _ID.fullmatch(review_id):
            raise ValueError("review_id must be a safe identifier")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM agent_reviews WHERE review_id = ?",
                (review_id,),
            ).fetchone()
        return dict(row) if row is not None else None
