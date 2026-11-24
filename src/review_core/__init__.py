"""Original domain and normalization core for CODE-REVIEW-CENTER."""

from .deduplication import deduplicate_findings
from .finding import Finding, FindingSeverity
from .sarif import parse_sarif

__all__ = [
    "Finding",
    "FindingSeverity",
    "deduplicate_findings",
    "parse_sarif",
]
