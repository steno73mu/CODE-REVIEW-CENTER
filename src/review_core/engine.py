from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
import os
import signal
import shutil
import subprocess
import threading
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


class EngineCancelledError(EngineExecutionError):
    """Raised when a running analysis engine is cancelled."""

    def __init__(
        self,
        message: str,
        *,
        command: tuple[str, ...],
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        super().__init__(message)
        self.command = command
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
    stdout_truncated: bool = False
    stderr_truncated: bool = False


class _BoundedPipeReader(threading.Thread):
    def __init__(self, pipe, limit: int) -> None:
        super().__init__(daemon=True)
        self.pipe = pipe
        self.limit = limit
        self.data = bytearray()
        self.truncated = False

    def run(self) -> None:
        try:
            while True:
                chunk = self.pipe.read(65536)
                if not chunk:
                    break
                remaining = self.limit - len(self.data)
                if remaining > 0:
                    self.data.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    self.truncated = True
        finally:
            self.pipe.close()

    def text(self) -> str:
        return self.data.decode("utf-8", errors="replace")


def _resolve_executable(executable: str, env: Mapping[str, str] | None) -> str:
    has_path_component = (
        os.path.isabs(executable)
        or os.sep in executable
        or (os.altsep is not None and os.altsep in executable)
    )
    if has_path_component:
        try:
            resolved = os.path.abspath(os.path.expanduser(executable))
            if not os.path.isfile(resolved):
                raise EngineExecutionError("configured analysis engine executable is not a file")
            return resolved
        except (OSError, ValueError) as exc:
            raise EngineExecutionError("could not resolve configured analysis engine executable") from exc

    search_path = (
        env["PATH"]
        if env is not None and "PATH" in env
        else os.environ.get("PATH", os.defpath)
    )
    trusted_path = os.pathsep.join(
        entry for entry in search_path.split(os.pathsep)
        if entry and os.path.isabs(entry)
    )
    if not trusted_path:
        raise EngineExecutionError(
            "analysis engine PATH must contain at least one absolute directory"
        )
    resolved = shutil.which(executable, path=trusted_path)
    if resolved is None:
        raise EngineExecutionError("analysis engine executable was not found on PATH")
    return os.path.abspath(resolved)


def _terminate_process_tree(process: subprocess.Popen) -> None:
    """Terminate the scanner and any child processes it started."""
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            if process.poll() is None:
                process.kill()
        process.wait()
        return

    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def run_engine(
    command: Command,
    *,
    timeout_seconds: float = 300.0,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    max_output_bytes: int = 1_048_576,
    cancel_event: threading.Event | None = None,
) -> EngineResult:
    """Run a trusted executable without a shell and bound captured output.

    A non-zero exit status is returned as data because scanners commonly use
    it to report findings. This is a process launcher, not a sandbox: callers
    must only invoke trusted, locally installed executables. Each output stream
    is drained fully but only the first max_output_bytes are retained.
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
    if (
        isinstance(max_output_bytes, bool)
        or not isinstance(max_output_bytes, int)
        or max_output_bytes < 1
        or max_output_bytes > 64 * 1024 * 1024
    ):
        raise EngineExecutionError("max_output_bytes must be between 1 byte and 64 MiB")
    if cancel_event is not None and not isinstance(cancel_event, threading.Event):
        raise EngineExecutionError("cancel_event must be a threading.Event or None")

    if env is not None:
        if not isinstance(env, Mapping) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in env.items()
        ):
            raise EngineExecutionError("env must be a mapping of string keys and values")
        if any("\x00" in key or "\x00" in value or "=" in key for key, value in env.items()):
            raise EngineExecutionError("env contains an invalid variable name or value")

    resolved_executable = _resolve_executable(normalized_command[0], env)
    process_command = (resolved_executable, *normalized_command[1:])

    started_at = time.perf_counter()
    try:
        process_options = (
            {"start_new_session": True}
            if os.name == "posix"
            else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        )
        process = subprocess.Popen(
            process_command,
            cwd=cwd,
            env=env,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            **process_options,
        )
    except (OSError, ValueError, TypeError) as exc:
        raise EngineExecutionError(
            f"could not execute analysis engine ({type(exc).__name__})"
        ) from exc

    stdout_reader = _BoundedPipeReader(process.stdout, max_output_bytes)
    stderr_reader = _BoundedPipeReader(process.stderr, max_output_bytes)
    stdout_reader.start()
    stderr_reader.start()

    deadline = started_at + float(timeout_seconds)
    termination: str | None = None
    while process.poll() is None:
        if cancel_event is not None and cancel_event.is_set():
            termination = "cancelled"
            break
        if time.perf_counter() >= deadline:
            termination = "timeout"
            break
        time.sleep(0.02)

    if termination is not None:
        _terminate_process_tree(process)
    else:
        process.wait()

    stdout_reader.join()
    stderr_reader.join()
    stdout = stdout_reader.text()
    stderr = stderr_reader.text()

    if termination == "cancelled":
        raise EngineCancelledError(
            "analysis engine was cancelled",
            command=normalized_command,
            stdout=stdout,
            stderr=stderr,
        )
    if termination == "timeout":
        raise EngineTimeoutError(
            f"analysis engine exceeded timeout of {timeout_seconds} seconds",
            command=normalized_command,
            timeout_seconds=float(timeout_seconds),
            stdout=stdout,
            stderr=stderr,
        )

    return EngineResult(
        command=normalized_command,
        returncode=process.returncode,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=max(0.0, time.perf_counter() - started_at),
        stdout_truncated=stdout_reader.truncated,
        stderr_truncated=stderr_reader.truncated,
    )
