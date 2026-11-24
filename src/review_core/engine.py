from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
import os
import subprocess
import time
from typing import TypeAlias


Command: TypeAlias = Sequence[str]


class EngineExecutionError(RuntimeError):
    """Raised when an analysis engine cannot be started or configured."""


class EngineTimeoutError(EngineExecutionError):
    """Raised when an analysis engine exceeds its execution deadline."""

    def __init__(
        self,
        message: str,
        *,
        command: tuple[str, ...],
        timeout_seconds: float,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        super().__init__(message)
        self.command = command
        self.timeout_seconds = timeout_seconds
        self.stdout = stdout
        self.stderr = stderr


@dataclass(frozen=True, slots=True)
class EngineResult:
    """Captured result of one external analysis-engine process."""

    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float


def run_engine(
    command: Command,
    *,
    timeout_seconds: float = 300.0,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> EngineResult:
    """Run a trusted executable without a shell and capture its diagnostics.

    A non-zero exit status is returned as data because scanners commonly use
    it to report findings. This function is a process launcher, not a sandbox:
    callers must only invoke trusted, locally installed executables.
    """
    if (
        isinstance(command, (str, bytes))
        or not isinstance(command, Sequence)
        or not command
        or any(not isinstance(argument, str) for argument in command)
    ):
        raise EngineExecutionError("command must be a non-empty sequence of strings")

    normalized_command = tuple(command)
    if not normalized_command[0].strip():
        raise EngineExecutionError("command executable must not be empty")
    if any("\x00" in argument for argument in normalized_command):
        raise EngineExecutionError("command arguments must not contain NUL characters")

    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
    ):
        raise EngineExecutionError("timeout_seconds must be a positive finite number")

    if env is not None:
        if not isinstance(env, Mapping) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in env.items()
        ):
            raise EngineExecutionError("env must be a mapping of string keys and values")
        if any("\x00" in key or "\x00" in value or "=" in key for key, value in env.items()):
            raise EngineExecutionError("env contains an invalid variable name or value")

    started_at = time.perf_counter()
    try:
        completed = subprocess.run(
            normalized_command,
            cwd=cwd,
            env=env,
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=float(timeout_seconds),
        )
    except subprocess.TimeoutExpired as exc:
        raise EngineTimeoutError(
            f"analysis engine exceeded timeout of {timeout_seconds} seconds",
            command=normalized_command,
            timeout_seconds=float(timeout_seconds),
            stdout=_as_text(exc.stdout),
            stderr=_as_text(exc.stderr),
        ) from exc
    except (OSError, ValueError, TypeError) as exc:
        # Avoid embedding environment values or arbitrary command arguments in
        # the public diagnostic; callers may include secrets in those values.
        raise EngineExecutionError(
            f"could not execute analysis engine ({type(exc).__name__})"
        ) from exc

    return EngineResult(
        command=normalized_command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_seconds=max(0.0, time.perf_counter() - started_at),
    )


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
