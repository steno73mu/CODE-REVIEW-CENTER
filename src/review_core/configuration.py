from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import json
import math
from pathlib import Path
from .database import connect_database
import re
import sqlite3
from urllib.parse import urlparse


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
_NAME = re.compile(r".*\S.*", re.DOTALL)
_ALLOWED_PARSERS = {"semgrep", "gitleaks", "sarif"}
_ALLOWED_PLACEHOLDERS = {"{project_path}"}


@dataclass(frozen=True, slots=True)
class ScannerProfile:
    scanner_id: str
    name: str
    parser: str
    command: tuple[str, ...]
    accepted_exit_codes: tuple[int, ...]
    timeout_seconds: float
    enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.scanner_id, str) or not _ID.fullmatch(self.scanner_id):
            raise ValueError("scanner_id must be 1-64 safe letters, digits, dots, underscores or hyphens")
        if not isinstance(self.name, str) or not _NAME.fullmatch(self.name.strip()):
            raise ValueError("scanner name must not be empty")
        if not isinstance(self.parser, str) or self.parser not in _ALLOWED_PARSERS:
            raise ValueError(f"parser must be one of: {', '.join(sorted(_ALLOWED_PARSERS))}")
        if (
            isinstance(self.command, (str, bytes))
            or not isinstance(self.command, (tuple, list))
            or not self.command
            or any(not isinstance(part, str) or not part for part in self.command)
        ):
            raise ValueError("command must be a non-empty argument sequence, not a shell string")
        for index, part in enumerate(self.command):
            if "\x00" in part:
                raise ValueError("command arguments must not contain NUL characters")
            if re.fullmatch(r"\{[A-Za-z_][A-Za-z0-9_]*\}", part) and part not in _ALLOWED_PLACEHOLDERS:
                raise ValueError("command contains an unsupported placeholder")
            if index == 0 and part in _ALLOWED_PLACEHOLDERS:
                raise ValueError("the executable cannot be a project-path placeholder")
        if (
            isinstance(self.accepted_exit_codes, (str, bytes))
            or not isinstance(self.accepted_exit_codes, (tuple, list))
            or not self.accepted_exit_codes
            or any(not isinstance(code, int) or isinstance(code, bool) for code in self.accepted_exit_codes)
        ):
            raise ValueError("accepted_exit_codes must be a non-empty sequence of integers")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be a positive finite number")
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "command", tuple(self.command))
        object.__setattr__(self, "accepted_exit_codes", tuple(self.accepted_exit_codes))
        object.__setattr__(self, "timeout_seconds", float(self.timeout_seconds))


class ScannerConfigStore:
    """SQLite-backed, allowlisted scanner profiles; no shell expansion is supported."""

    def __init__(self, database: str | Path) -> None:
        self.database = Path(database).expanduser()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scanner_profiles (
                    scanner_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    parser TEXT NOT NULL,
                    command_json TEXT NOT NULL,
                    exit_codes_json TEXT NOT NULL,
                    timeout_seconds REAL NOT NULL,
                    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1))
                )
                """
            )

    def _connect(self):
        return connect_database(self.database)

    @staticmethod
    def _from_row(row: sqlite3.Row) -> ScannerProfile:
        return ScannerProfile(
            scanner_id=row["scanner_id"],
            name=row["name"],
            parser=row["parser"],
            command=tuple(json.loads(row["command_json"])),
            accepted_exit_codes=tuple(json.loads(row["exit_codes_json"])),
            timeout_seconds=row["timeout_seconds"],
            enabled=bool(row["enabled"]),
        )

    def save(self, profile: ScannerProfile) -> None:
        if not isinstance(profile, ScannerProfile):
            raise TypeError("profile must be a ScannerProfile")
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO scanner_profiles
                    (scanner_id, name, parser, command_json, exit_codes_json, timeout_seconds, enabled)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        profile.scanner_id,
                        profile.name,
                        profile.parser,
                        json.dumps(profile.command),
                        json.dumps(profile.accepted_exit_codes),
                        profile.timeout_seconds,
                        int(profile.enabled),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"scanner profile {profile.scanner_id!r} already exists") from exc

    def get(self, scanner_id: str) -> ScannerProfile | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM scanner_profiles WHERE scanner_id = ?",
                (scanner_id,),
            ).fetchone()
        return self._from_row(row) if row else None

    def list_profiles(self, *, enabled_only: bool = False) -> list[ScannerProfile]:
        query = "SELECT * FROM scanner_profiles"
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY name COLLATE NOCASE, scanner_id"
        with self._connect() as connection:
            rows = connection.execute(query).fetchall()
        return [self._from_row(row) for row in rows]

    def remove(self, scanner_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM scanner_profiles WHERE scanner_id = ?",
                (scanner_id,),
            )
        return cursor.rowcount > 0


_API_KEY_ENV = re.compile(r"[A-Z][A-Z0-9_]{0,127}")


@dataclass(frozen=True, slots=True)
class ProviderProfile:
    provider_id: str
    name: str
    base_url: str
    model: str
    api_key_env: str | None
    timeout_seconds: float = 60.0
    enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.provider_id, str) or not _ID.fullmatch(self.provider_id):
            raise ValueError("provider_id must be 1-64 safe letters, digits, dots, underscores or hyphens")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("provider name must not be empty")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("provider model must not be empty")
        if not isinstance(self.base_url, str):
            raise ValueError("provider base_url must be a URL string")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("provider base_url must use http or https and include a host")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("provider base_url must not contain credentials, query, or fragment")
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("provider base_url has an invalid port") from exc
        host = parsed.hostname.casefold()
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = host == "localhost"
        if parsed.scheme == "http" and not loopback:
            raise ValueError("plain HTTP is allowed only for loopback/local providers")
        if self.api_key_env is not None and (
            not isinstance(self.api_key_env, str) or not _API_KEY_ENV.fullmatch(self.api_key_env)
        ):
            raise ValueError("api_key_env must be an environment-variable name, never a secret value")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be a positive finite number")
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "base_url", self.base_url.rstrip("/"))
        object.__setattr__(self, "model", self.model.strip())
        object.__setattr__(self, "timeout_seconds", float(self.timeout_seconds))


class ProviderConfigStore:
    """SQLite provider settings store; API key values are never persisted."""

    def __init__(self, database: str | Path) -> None:
        self.database = Path(database).expanduser()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS provider_profiles (
                    provider_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    model TEXT NOT NULL,
                    api_key_env TEXT,
                    timeout_seconds REAL NOT NULL,
                    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1))
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10.0)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _from_row(row: sqlite3.Row) -> ProviderProfile:
        return ProviderProfile(
            provider_id=row["provider_id"],
            name=row["name"],
            base_url=row["base_url"],
            model=row["model"],
            api_key_env=row["api_key_env"],
            timeout_seconds=row["timeout_seconds"],
            enabled=bool(row["enabled"]),
        )

    def save(self, profile: ProviderProfile) -> None:
        if not isinstance(profile, ProviderProfile):
            raise TypeError("profile must be a ProviderProfile")
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO provider_profiles
                    (provider_id, name, base_url, model, api_key_env, timeout_seconds, enabled)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        profile.provider_id,
                        profile.name,
                        profile.base_url,
                        profile.model,
                        profile.api_key_env,
                        profile.timeout_seconds,
                        int(profile.enabled),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"provider profile {profile.provider_id!r} already exists") from exc

    def get(self, provider_id: str) -> ProviderProfile | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM provider_profiles WHERE provider_id = ?",
                (provider_id,),
            ).fetchone()
        return self._from_row(row) if row else None

    def list_profiles(self, *, enabled_only: bool = False) -> list[ProviderProfile]:
        query = "SELECT * FROM provider_profiles"
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY name COLLATE NOCASE, provider_id"
        with self._connect() as connection:
            rows = connection.execute(query).fetchall()
        return [self._from_row(row) for row in rows]

    def remove(self, provider_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM provider_profiles WHERE provider_id = ?",
                (provider_id,),
            )
        return cursor.rowcount > 0
