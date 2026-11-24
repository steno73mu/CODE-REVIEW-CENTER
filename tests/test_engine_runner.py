import sys
import unittest

from review_core.engine import (
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

    def test_rejects_non_positive_timeout(self):
        with self.assertRaises(EngineExecutionError):
            run_engine([sys.executable, "--version"], timeout_seconds=0)


if __name__ == "__main__":
    unittest.main()
