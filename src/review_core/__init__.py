"""Original domain and normalization core for CODE-REVIEW-CENTER."""

from .adapters import parse_gitleaks, parse_semgrep
from .deduplication import deduplicate_findings
from .engine import EngineExecutionError, EngineResult, EngineTimeoutError, run_engine
from .finding import Finding, FindingSeverity
from .sarif import parse_sarif
from .scanning import ScanExecutionError, ScanResult, run_scanner

__all__ = [
    "EngineExecutionError",
    "EngineResult",
    "EngineTimeoutError",
    "Finding",
    "ScanExecutionError",
    "ScanResult",
    "FindingSeverity",
    "deduplicate_findings",
    "parse_gitleaks",
    "parse_sarif",
    "parse_semgrep",
    "run_engine",
    "run_scanner",
]
