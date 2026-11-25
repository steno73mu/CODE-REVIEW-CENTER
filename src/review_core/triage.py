from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
import re
import sqlite3

from .database import connect_database


_FINGERPRINT = re.compile(r"[0-9a-f]{64}")


class TriageStatus(StrEnum):
    OPEN = "open"
    ACCEPTED = "accepted"
    FALSE_POSITIVE = "false_positive"
    FIXED = "fixed"
    WONT_FIX = "wont_fix"


class TriageStore:
    """Persistent per-session finding disposition and reviewer note."""

    def __init__(self, database: str | Path) -> None:
        self.database = Path(database).expanduser()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS finding_triage (
                    session_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('open', 'accepted', 'false_positive', 'fixed', 'wont_fix')),
                    note TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, fingerprint),
                    FOREIGN KEY (session_id, fingerprint)
                        REFERENCES findings(session_id, fingerprint) ON DELETE CASCADE
                )
                """
            )

    def _connect(self):
        return connect_database(self.database)

    @staticmethod
    def _validate_fingerprint(fingerprint: str) -> None:
        if not isinstance(fingerprint, str) or not _FINGERPRINT.fullmatch(fingerprint):
            raise ValueError("fingerprint must be a 64-character lowercase SHA-256 hex value")

    def list_for_session(self, session_id: str) -> list[dict]:
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must not be empty")
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM scan_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if exists is None:
                raise ValueError(f"unknown scan session: {session_id}")
            rows = connection.execute(
                """
                SELECT f.fingerprint, json_extract(f.payload, '$.tool') AS tool,
                       json_extract(f.payload, '$.severity') AS severity,
                       json_extract(f.payload, '$.path') AS path,
                       json_extract(f.payload, '$.start_line') AS start_line,
                       COALESCE(t.status, 'open') AS status,
                       t.note, t.updated_at
                FROM findings f
                LEFT JOIN finding_triage t
                  ON t.session_id = f.session_id AND t.fingerprint = f.fingerprint
                WHERE f.session_id = ?
                ORDER BY f.rowid
                """,
                (session_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_status(
        self,
        session_id: str,
        fingerprint: str,
        status: str | TriageStatus,
        *,
        note: str | None = None,
    ) -> dict:
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must not be empty")
        self._validate_fingerprint(fingerprint)
        try:
            normalized_status = TriageStatus(status)
        except (ValueError, TypeError) as exc:
            raise ValueError("status must be open, accepted, false_positive, fixed, or wont_fix") from exc
        if note is not None and (not isinstance(note, str) or len(note) > 4000):
            raise ValueError("note must be a string of at most 4000 characters")

        updated_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM findings WHERE session_id = ? AND fingerprint = ?",
                (session_id, fingerprint),
            ).fetchone()
            if exists is None:
                raise ValueError("finding fingerprint does not belong to this scan session")
            connection.execute(
                """
                INSERT INTO finding_triage (session_id, fingerprint, status, note, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id, fingerprint) DO UPDATE SET
                    status = excluded.status,
                    note = excluded.note,
                    updated_at = excluded.updated_at
                """,
                (session_id, fingerprint, normalized_status.value, note, updated_at),
            )
        return {
            "session_id": session_id,
            "fingerprint": fingerprint,
            "status": normalized_status.value,
            "note": note,
            "updated_at": updated_at,
        }
