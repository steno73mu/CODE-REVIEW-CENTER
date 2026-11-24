from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from .finding import Finding
from .orchestration import ScanBatchResult


_SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class ScanStore:
    """Small SQLite-backed history store for completed scan batches."""

    def __init__(self, database: str | Path) -> None:
        self.database = Path(database).expanduser()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10.0)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS scan_sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_seconds REAL NOT NULL,
                    cancelled INTEGER NOT NULL CHECK (cancelled IN (0, 1))
                );
                CREATE TABLE IF NOT EXISTS scan_jobs (
                    session_id TEXT NOT NULL REFERENCES scan_sessions(session_id) ON DELETE CASCADE,
                    job_order INTEGER NOT NULL,
                    job_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT,
                    returncode INTEGER,
                    duration_seconds REAL,
                    PRIMARY KEY (session_id, job_id),
                    UNIQUE (session_id, job_order)
                );
                CREATE TABLE IF NOT EXISTS findings (
                    session_id TEXT NOT NULL REFERENCES scan_sessions(session_id) ON DELETE CASCADE,
                    fingerprint TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (session_id, fingerprint)
                );
                CREATE TABLE IF NOT EXISTS scan_correlations (
                    session_id TEXT NOT NULL REFERENCES scan_sessions(session_id) ON DELETE CASCADE,
                    group_order INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (session_id, group_order)
                );
                CREATE INDEX IF NOT EXISTS idx_scan_sessions_created
                    ON scan_sessions(created_at DESC);
                """
            )

    @staticmethod
    def _validate_session_id(session_id: str) -> None:
        if not isinstance(session_id, str) or not _SESSION_ID.fullmatch(session_id):
            raise ValueError("session_id must be 1-128 safe letters, digits, dots, underscores or hyphens")

    @staticmethod
    def _finding_payload(finding: Finding) -> dict[str, Any]:
        return {
            "tool": finding.tool,
            "message": finding.message,
            "severity": finding.severity.value,
            "rule_id": finding.rule_id,
            "tool_version": finding.tool_version,
            "path": finding.path,
            "start_line": finding.start_line,
            "start_column": finding.start_column,
            "end_line": finding.end_line,
            "end_column": finding.end_column,
            "help_uri": finding.help_uri,
            "fingerprint": finding.fingerprint,
        }

    def save_batch(self, session_id: str, batch: ScanBatchResult) -> None:
        self._validate_session_id(session_id)
        if not isinstance(batch, ScanBatchResult):
            raise TypeError("batch must be a ScanBatchResult")

        statuses = {item.status.value for item in batch.jobs}
        if batch.cancelled and not any(status == "succeeded" for status in statuses):
            overall_status = "cancelled"
        elif statuses <= {"succeeded"}:
            overall_status = "completed"
        else:
            overall_status = "partial"

        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO scan_sessions
                    (session_id, created_at, status, duration_seconds, cancelled)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (session_id, created_at, overall_status, batch.duration_seconds, int(batch.cancelled)),
                )
                for order, item in enumerate(batch.jobs):
                    process = item.scan_result.process_result if item.scan_result else None
                    connection.execute(
                        """
                        INSERT INTO scan_jobs
                        (session_id, job_order, job_id, status, error, returncode, duration_seconds)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            session_id,
                            order,
                            item.job_id,
                            item.status.value,
                            item.error,
                            process.returncode if process else None,
                            process.duration_seconds if process else None,
                        ),
                    )
                for finding in batch.findings:
                    payload = json.dumps(
                        self._finding_payload(finding),
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    connection.execute(
                        "INSERT INTO findings (session_id, fingerprint, payload) VALUES (?, ?, ?)",
                        (session_id, finding.fingerprint, payload),
                    )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"scan session {session_id!r} already exists or violates storage constraints") from exc

    def get_batch(self, session_id: str) -> dict[str, Any] | None:
        self._validate_session_id(session_id)
        with self._connect() as connection:
            session = connection.execute(
                "SELECT * FROM scan_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if session is None:
                return None
            jobs = connection.execute(
                "SELECT * FROM scan_jobs WHERE session_id = ? ORDER BY job_order",
                (session_id,),
            ).fetchall()
            findings = connection.execute(
                "SELECT payload FROM findings WHERE session_id = ? ORDER BY rowid",
                (session_id,),
            ).fetchall()
            correlations = connection.execute(
                "SELECT payload FROM scan_correlations WHERE session_id = ? ORDER BY group_order",
                (session_id,),
            ).fetchall()
        return {
            "session_id": session["session_id"],
            "created_at": session["created_at"],
            "status": session["status"],
            "duration_seconds": session["duration_seconds"],
            "cancelled": bool(session["cancelled"]),
            "jobs": [dict(job) for job in jobs],
            "findings": [json.loads(row["payload"]) for row in findings],
            "correlations": [json.loads(row["payload"]) for row in correlations],
        }

    def list_sessions(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("limit must be an integer between 1 and 500")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT session_id, created_at, status, duration_seconds, cancelled
                FROM scan_sessions
                ORDER BY created_at DESC, rowid DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [dict(row) | {"cancelled": bool(row["cancelled"])} for row in rows]
