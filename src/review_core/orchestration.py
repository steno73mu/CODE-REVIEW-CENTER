from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import StrEnum
import threading
import time

from .deduplication import deduplicate_findings
from .engine import EngineCancelledError, EngineExecutionError, EngineTimeoutError
from .finding import Finding
from .correlation import CorrelatedFinding, correlate_findings
from .scanning import ScanResult, run_scanner


class ScanStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ScanJob:
    """One configured scanner invocation; command must target a trusted binary."""

    job_id: str
    command: Sequence[str]
    parser: object
    accepted_exit_codes: Sequence[int] = (0,)
    timeout_seconds: float = 300.0
    cwd: str | None = None
    env: dict[str, str] | None = None
    max_output_bytes: int = 1_048_576


@dataclass(frozen=True, slots=True)
class ScanJobResult:
    job_id: str
    status: ScanStatus
    scan_result: ScanResult | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ScanBatchResult:
    jobs: tuple[ScanJobResult, ...]
    findings: tuple[Finding, ...]
    duration_seconds: float
    cancelled: bool
    correlations: tuple[CorrelatedFinding, ...]


def _execute_job(job: ScanJob, cancel_event: threading.Event) -> ScanJobResult:
    if cancel_event.is_set():
        return ScanJobResult(job_id=job.job_id, status=ScanStatus.CANCELLED)
    try:
        result = run_scanner(
            job.command,
            parser=job.parser,
            accepted_exit_codes=job.accepted_exit_codes,
            timeout_seconds=job.timeout_seconds,
            cwd=job.cwd,
            env=job.env,
            max_output_bytes=job.max_output_bytes,
            cancel_event=cancel_event,
        )
        return ScanJobResult(
            job_id=job.job_id,
            status=ScanStatus.SUCCEEDED,
            scan_result=result,
        )
    except EngineCancelledError:
        return ScanJobResult(job_id=job.job_id, status=ScanStatus.CANCELLED, error="scanner was cancelled")
    except EngineTimeoutError:
        return ScanJobResult(
            job_id=job.job_id,
            status=ScanStatus.TIMED_OUT,
            error="scanner exceeded its execution timeout",
        )
    except (EngineExecutionError, ValueError, TypeError) as exc:
        return ScanJobResult(
            job_id=job.job_id,
            status=ScanStatus.FAILED,
            error=f"scanner execution failed ({type(exc).__name__})",
        )
    except Exception as exc:
        # A faulty parser must not erase results from other independent engines.
        return ScanJobResult(
            job_id=job.job_id,
            status=ScanStatus.FAILED,
            error=f"scanner report processing failed ({type(exc).__name__})",
        )


def run_scan_batch(
    jobs: Sequence[ScanJob],
    *,
    max_workers: int = 4,
    cancel_event: threading.Event | None = None,
) -> ScanBatchResult:
    """Run independent trusted scanners concurrently and aggregate their findings.

    Cancellation is cooperative: it prevents queued jobs from starting and
    is checked immediately before each process launch. Already running scanner
    processes are bounded by their own timeout and are not force-killed.
    """
    if isinstance(max_workers, bool) or not isinstance(max_workers, int) or max_workers < 1:
        raise ValueError("max_workers must be a positive integer")
    if isinstance(jobs, (str, bytes)) or not isinstance(jobs, Sequence):
        raise ValueError("jobs must be a sequence of ScanJob instances")

    normalized_jobs = tuple(jobs)
    if any(not isinstance(job, ScanJob) for job in normalized_jobs):
        raise ValueError("jobs must contain only ScanJob instances")
    ids = [job.job_id for job in normalized_jobs]
    if any(not isinstance(job_id, str) or not job_id.strip() for job_id in ids):
        raise ValueError("every job must have a non-empty string job_id")
    if len(ids) != len(set(ids)):
        raise ValueError("job_id values must be unique")

    cancellation = cancel_event or threading.Event()
    started_at = time.perf_counter()
    results: dict[str, ScanJobResult] = {}

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="crc-scan") as executor:
        futures: dict[Future[ScanJobResult], ScanJob] = {
            executor.submit(_execute_job, job, cancellation): job
            for job in normalized_jobs
        }
        for future in as_completed(futures):
            job = futures[future]
            if future.cancelled():
                results[job.job_id] = ScanJobResult(
                    job_id=job.job_id,
                    status=ScanStatus.CANCELLED,
                )
                continue
            results[job.job_id] = future.result()

    ordered_results = tuple(results[job.job_id] for job in normalized_jobs)
    all_findings = (
        finding
        for item in ordered_results
        if item.scan_result is not None
        for finding in item.scan_result.findings
    )
    unique_findings = tuple(deduplicate_findings(all_findings))
    return ScanBatchResult(
        jobs=ordered_results,
        findings=unique_findings,
        duration_seconds=max(0.0, time.perf_counter() - started_at),
        cancelled=cancellation.is_set(),
        correlations=correlate_findings(unique_findings),
    )
