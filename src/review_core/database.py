from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from collections.abc import Iterator


@contextmanager
def connect_database(path: str | Path) -> Iterator[sqlite3.Connection]:
    """Open a SQLite connection and always commit/rollback and close it."""
    connection = sqlite3.connect(path, timeout=10.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
