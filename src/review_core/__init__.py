"""Original domain and normalization core for CODE-REVIEW-CENTER."""

from .adapters import parse_gitleaks, parse_semgrep
from .deduplication import deduplicate_findings
from .finding import Finding, FindingSeverity
from .sarif import parse_sarif

__all__ = [
    "Finding",
    "FindingSeverity",
    "deduplicate_findings",
    "parse_gitleaks",
    "parse_sarif",
    "parse_semgrep",
]
