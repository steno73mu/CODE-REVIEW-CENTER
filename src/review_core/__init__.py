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
from .configuration import ProviderConfigStore, ProviderProfile, ScannerConfigStore, ScannerProfile
from .application import build_scan_jobs, scan_project
from .correlation import CorrelatedFinding, CorrelationEvidence, correlate_findings
from .providers import AIReviewClient, AIReviewError, AIReviewResult
from .reports import render_report, write_report

__all__ = [
    "AIReviewClient",
    "AIReviewError",
    "AIReviewResult",
    "CorrelatedFinding",
    "CorrelationEvidence",
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
    "ProviderConfigStore",
    "ProviderProfile",
    "Project",
    "ProjectRegistry",
    "ScannerConfigStore",
    "ScannerProfile",
    "ScanResult",
    "FindingSeverity",
    "build_scan_jobs",
    "correlate_findings",
    "deduplicate_findings",
    "parse_gitleaks",
    "parse_sarif",
    "parse_semgrep",
    "scan_project",
    "render_report",
    "write_report",
    "run_engine",
    "run_scanner",
    "run_scan_batch",
]

