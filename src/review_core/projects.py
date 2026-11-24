from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
import uuid


_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._+-]{0,63}")


@dataclass(frozen=True, slots=True)
class Project:
    project_id: str
    name: str
    path: str
    created_at: str


class ProjectRegistry:
    """SQLite registry of local source directories; it never executes project code."""

    def __init__(self, database: str | Path) -> None:
        self.database = Path(database).expanduser()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    path TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10.0)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _validate_name(name: str) -> str:
        if not isinstance(name, str):
            raise ValueError("project name must be a string")
        normalized = name.strip()
        if not _NAME.fullmatch(normalized):
            raise ValueError("project name must be 1-64 safe letters, digits, spaces, dots, underscores, plus or hyphens")
        return normalized

    @staticmethod
    def _project(row: sqlite3.Row) -> Project:
        return Project(
            project_id=row["project_id"],
            name=row["name"],
            path=row["path"],
            created_at=row["created_at"],
        )

    def register(self, name: str, path: str | Path) -> Project:
        normalized_name = self._validate_name(name)
        try:
            resolved = Path(path).expanduser().resolve(strict=True)
        except (OSError, TypeError, ValueError) as exc:
            raise ValueError("project path must point to an existing directory") from exc
        if not resolved.is_dir():
            raise ValueError("project path must point to an existing directory")

        project_id = str(uuid.uuid4())
        from datetime import datetime, timezone
        created_at = datetime.now(timezone.utc).isoformat()
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO projects (project_id, name, path, created_at) VALUES (?, ?, ?, ?)",
                    (project_id, normalized_name, str(resolved), created_at),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("a project with this name or path is already registered") from exc
        return Project(project_id, normalized_name, str(resolved), created_at)

    def list_projects(self) -> list[Project]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM projects ORDER BY name COLLATE NOCASE, project_id"
            ).fetchall()
        return [self._project(row) for row in rows]

    def get(self, project_id: str) -> Project | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        return self._project(row) if row else None

    def rename(self, project_id: str, name: str) -> Project:
        normalized_name = self._validate_name(name)
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    "UPDATE projects SET name = ? WHERE project_id = ?",
                    (normalized_name, project_id),
                )
                if cursor.rowcount == 0:
                    raise KeyError(f"project {project_id!r} does not exist")
                row = connection.execute(
                    "SELECT * FROM projects WHERE project_id = ?",
                    (project_id,),
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            raise ValueError("a project with this name is already registered") from exc
        return self._project(row)

    def remove(self, project_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM projects WHERE project_id = ?",
                (project_id,),
            )
        return cursor.rowcount > 0
