from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import json


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
    """A normalized, tool-independent code-review finding."""

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
        if not self.tool.strip():
            raise ValueError("Finding.tool must not be empty")
        if not self.message.strip():
            raise ValueError("Finding.message must not be empty")
        if not self.fingerprint:
            object.__setattr__(self, "fingerprint", self.make_fingerprint())

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
