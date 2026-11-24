from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
import threading
from dataclasses import dataclass

from .engine import EngineExecutionError, EngineResult, run_engine
from .finding import Finding


FindingParser = Callable[[str], Iterable[Finding]]


class ScanExecutionError(EngineExecutionError):
    """Raised when a scanner process exits with an unaccepted status."""

    def __init__(
        self,
        message: str,
        *,
        process_result: EngineResult | None = None,
    ) -> None:
        super().__init__(message)
        self.process_result = process_result


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Normalized findings together with the process evidence that produced them."""

    process_result: EngineResult
    findings: tuple[Finding, ...]


def run_scanner(
    command: Sequence[str],
    *,
    parser: FindingParser,
    accepted_exit_codes: Sequence[int] = (0,),
    timeout_seconds: float = 300.0,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    max_output_bytes: int = 1_048_576,
    cancel_event: threading.Event | None = None,
) -> ScanResult:
    """Execute a trusted scanner and normalize its stdout report.

    Some scanners use a non-zero status to indicate that findings were
    detected. Callers must opt into those statuses explicitly, for example
    with accepted_exit_codes=(0, 1) for a configured Gitleaks invocation.
    """
    if not callable(parser):
        raise ScanExecutionError("parser must be callable")
    if (
        isinstance(accepted_exit_codes, (str, bytes))
        or not isinstance(accepted_exit_codes, Sequence)
        or not accepted_exit_codes
        or any(
            not isinstance(code, int) or isinstance(code, bool)
            for code in accepted_exit_codes
        )
    ):
        raise ScanExecutionError("accepted_exit_codes must be a non-empty sequence of integers")

    process_result = run_engine(
        command,
        timeout_seconds=timeout_seconds,
        cwd=cwd,
        env=env,
        max_output_bytes=max_output_bytes,
        cancel_event=cancel_event,
    )
    if process_result.returncode not in accepted_exit_codes:
        raise ScanExecutionError(
            f"scanner exited with unaccepted status {process_result.returncode}",
            process_result=process_result,
        )

    parsed_findings = tuple(parser(process_result.stdout))
    if any(not isinstance(finding, Finding) for finding in parsed_findings):
        raise TypeError("scanner parser must return only Finding instances")

    return ScanResult(process_result=process_result, findings=parsed_findings)
