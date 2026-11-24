from __future__ import annotations

from collections.abc import Sequence
import threading

from .adapters import parse_gitleaks, parse_semgrep
from .configuration import ScannerProfile
from .orchestration import ScanBatchResult, ScanJob, run_scan_batch
from .projects import Project
from .sarif import parse_sarif


_PARSERS = {
    "semgrep": parse_semgrep,
    "gitleaks": parse_gitleaks,
    "sarif": parse_sarif,
}


def build_scan_jobs(
    project: Project,
    profiles: Sequence[ScannerProfile],
) -> tuple[ScanJob, ...]:
    """Resolve configured profiles into safe argv-based jobs for one project."""
    if not isinstance(project, Project):
        raise TypeError("project must be a Project")
    jobs: list[ScanJob] = []
    for profile in profiles:
        if not isinstance(profile, ScannerProfile):
            raise TypeError("profiles must contain ScannerProfile instances")
        if not profile.enabled:
            continue
        command = tuple(
            part.replace("{project_path}", project.path)
            for part in profile.command
        )
        jobs.append(
            ScanJob(
                job_id=profile.scanner_id,
                command=command,
                parser=_PARSERS[profile.parser],
                accepted_exit_codes=profile.accepted_exit_codes,
                timeout_seconds=profile.timeout_seconds,
                cwd=project.path,
            )
        )
    return tuple(jobs)


def scan_project(
    project: Project,
    profiles: Sequence[ScannerProfile],
    *,
    max_workers: int = 4,
    cancel_event: threading.Event | None = None,
) -> ScanBatchResult:
    jobs = build_scan_jobs(project, profiles)
    if not jobs:
        raise ValueError("no enabled scanner profiles are configured")
    return run_scan_batch(
        jobs,
        max_workers=max_workers,
        cancel_event=cancel_event,
    )
