"""Original domain and normalization core for CODE-REVIEW-CENTER."""

from .adapters import parse_gitleaks, parse_semgrep
from .deduplication import deduplicate_findings
from .engine import EngineCancelledError, EngineExecutionError, EngineResult, EngineTimeoutError, run_engine
from .finding import Finding, FindingSeverity
from .sarif import parse_sarif
from .scanning import ScanExecutionError, ScanResult, run_scanner
from .orchestration import ScanBatchResult, ScanJob, ScanJobResult, ScanStatus, run_scan_batch
from .storage import ScanStore
from .projects import Project, ProjectRegistry
from .configuration import ScannerConfigStore, ScannerProfile

__all__ = [
    "EngineCancelledError",
    "EngineExecutionError",
    "EngineResult",
    "EngineTimeoutError",
    "Finding",
    "ScanBatchResult",
    "ScanExecutionError",
    "ScanJob",
    "ScanJobResult",
    "ScanStatus",
    "ScanStore",
    "Project",
    "ProjectRegistry",
    "ScannerConfigStore",
    "ScannerProfile",
    "ScanResult",
    "FindingSeverity",
    "deduplicate_findings",
    "parse_gitleaks",
    "parse_sarif",
    "parse_semgrep",
    "run_engine",
    "run_scanner",
    "run_scan_batch",
]

from .application import build_scan_jobs, scan_project
