from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import json
import re


class FindingSeverity(StrEnum):
    """Severity vocabulary shared by all analysis engines."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Finding:
    """A normalized, tool-independent code-review finding.

    Coordinates follow SARIF's one-based convention. The fingerprint is an
    identity for exact deduplication, not a claim that two different tools'
    reports are semantically equivalent.
    """

    tool: str
    message: str
    severity: FindingSeverity = FindingSeverity.UNKNOWN
    rule_id: str | None = None
    tool_version: str | None = None
    path: str | None = None
    start_line: int | None = None
    start_column: int | None = None
    end_line: int | None = None
    end_column: int | None = None
    help_uri: str | None = None
    fingerprint: str = field(default="", compare=True)

    def __post_init__(self) -> None:
        if not isinstance(self.tool, str) or not self.tool.strip():
            raise ValueError("Finding.tool must be a non-empty string")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("Finding.message must be a non-empty string")

        if not isinstance(self.severity, FindingSeverity):
            try:
                object.__setattr__(self, "severity", FindingSeverity(self.severity))
            except (TypeError, ValueError) as exc:
                raise ValueError("Finding.severity must be a FindingSeverity value") from exc

        for name in ("rule_id", "tool_version", "path", "help_uri"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"Finding.{name} must be a string or None")

        for name in ("start_line", "start_column", "end_line", "end_column"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 1
            ):
                raise ValueError(f"Finding.{name} must be a positive integer or None")

        if (
            self.start_line is not None
            and self.end_line is not None
            and self.end_line < self.start_line
        ):
            raise ValueError("Finding.end_line must not precede start_line")
        if (
            self.start_line is not None
            and self.start_line == self.end_line
            and self.start_column is not None
            and self.end_column is not None
            and self.end_column < self.start_column
        ):
            raise ValueError("Finding.end_column must not precede start_column on the same line")

        if not self.fingerprint:
            object.__setattr__(self, "fingerprint", self.make_fingerprint())
        elif not isinstance(self.fingerprint, str) or not re.fullmatch(
            r"[0-9a-fA-F]{64}", self.fingerprint
        ):
            raise ValueError("Finding.fingerprint must be a 64-character SHA-256 hex digest")
        else:
            object.__setattr__(self, "fingerprint", self.fingerprint.lower())

    def make_fingerprint(self) -> str:
        """Return a stable SHA-256 identity independent of severity/version."""
        canonical = {
            "tool": self.tool.casefold().strip(),
            "rule_id": (self.rule_id or "").strip(),
            "path": self.path or "",
            "start_line": self.start_line,
            "start_column": self.start_column,
            "message": " ".join(self.message.split()).casefold(),
        }
        encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
