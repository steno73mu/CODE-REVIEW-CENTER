import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from review_core.engine import (
    EngineCancelledError,
    EngineExecutionError,
    EngineTimeoutError,
    run_engine,
)


class EngineRunnerTests(unittest.TestCase):
    def test_captures_stdout_stderr_and_exit_code(self):
        result = run_engine(
            [sys.executable, "-c", "import sys; print('ready'); print('note', file=sys.stderr)"]
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "ready")
        self.assertEqual(result.stderr.strip(), "note")
        self.assertGreaterEqual(result.duration_seconds, 0)

    def test_resolves_bare_executable_from_path_before_changing_to_project_directory(self):
        with tempfile.TemporaryDirectory() as project_directory:
            with patch("shutil.which", return_value=sys.executable) as which:
                result = run_engine(
                    ["python", "-c", "print('trusted executable')"],
                    cwd=project_directory,
                )

        self.assertEqual(result.stdout.strip(), "trusted executable")
        which.assert_called_once()
        self.assertEqual(which.call_args.args[0], "python")

    def test_passes_arguments_without_shell_interpretation(self):
        literal = "value; touch SHOULD_NOT_EXIST"
        result = run_engine([sys.executable, "-c", "import sys; print(sys.argv[1])", literal])

        self.assertEqual(result.stdout.strip(), literal)

    def test_returns_nonzero_exit_code_without_hiding_diagnostics(self):
        result = run_engine(
            [sys.executable, "-c", "import sys; print('bad input', file=sys.stderr); sys.exit(7)"]
        )

        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stderr.strip(), "bad input")

    def test_rejects_empty_or_invalid_commands(self):
        for command in ([], [""], [" ", "arg"], "python --version"):
            with self.subTest(command=command):
                with self.assertRaises(EngineExecutionError):
                    run_engine(command)

    def test_reports_missing_executable_as_engine_error(self):
        with self.assertRaises(EngineExecutionError):
            run_engine(["__code_review_center_missing_executable__"])

    def test_raises_specific_error_when_process_times_out(self):
        with self.assertRaises(EngineTimeoutError):
            run_engine(
                [sys.executable, "-c", "import time; time.sleep(2)"],
                timeout_seconds=0.05,
            )

    def test_timeout_terminates_descendants_that_inherit_output_pipes(self):
        child = "import time; time.sleep(3)"
        parent = (
            "import subprocess, sys, time; "
            "subprocess.Popen([sys.executable, '-c', sys.argv[1]]); "
            "time.sleep(10)"
        )
        started = time.monotonic()
        with self.assertRaises(EngineTimeoutError):
            run_engine(
                [sys.executable, "-c", parent, child],
                timeout_seconds=0.15,
            )

        self.assertLess(time.monotonic() - started, 2.0)

    def test_rejects_non_positive_timeout(self):
        with self.assertRaises(EngineExecutionError):
            run_engine([sys.executable, "--version"], timeout_seconds=0)

    def test_bounds_captured_output_and_marks_truncation(self):
        result = run_engine(
            [sys.executable, "-c", "print('x' * 10000)"],
            max_output_bytes=128,
        )

        self.assertLessEqual(len(result.stdout.encode("utf-8")), 128)
        self.assertTrue(result.stdout_truncated)
        self.assertFalse(result.stderr_truncated)

    def test_cancellation_terminates_running_process(self):
        cancellation = threading.Event()

        def cancel_soon():
            time.sleep(0.1)
            cancellation.set()

        thread = threading.Thread(target=cancel_soon)
        thread.start()
        try:
            with self.assertRaises(EngineCancelledError):
                run_engine(
                    [sys.executable, "-c", "import time; time.sleep(5)"],
                    cancel_event=cancellation,
                )
        finally:
            thread.join(timeout=1)

    def test_rejects_invalid_output_limit(self):
        for limit in (0, 64 * 1024 * 1024 + 1):
            with self.subTest(limit=limit), self.assertRaises(EngineExecutionError):
                run_engine([sys.executable, "--version"], max_output_bytes=limit)


if __name__ == "__main__":
    unittest.main()
