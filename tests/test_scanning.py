import json
import sys
import unittest

from review_core.adapters import parse_gitleaks, parse_semgrep
from review_core.finding import Finding
from review_core.scanning import ScanExecutionError, run_scanner


class ScannerExecutionTests(unittest.TestCase):
    def test_runs_engine_and_normalizes_semgrep_stdout(self):
        report = {
            "version": "1.2.3",
            "results": [
                {
                    "check_id": "python.lang.security.audit",
                    "path": "app.py",
                    "start": {"line": 4, "col": 2},
                    "end": {"line": 4, "col": 8},
                    "extra": {"message": "Unsafe call", "severity": "ERROR"},
                }
            ],
        }
        result = run_scanner(
            [sys.executable, "-c", "import sys; print(sys.argv[1])", json.dumps(report)],
            parser=parse_semgrep,
        )

        self.assertEqual(result.process_result.returncode, 0)
        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].tool, "Semgrep")
        self.assertEqual(result.findings[0].path, "app.py")

    def test_accepts_configured_nonzero_exit_code_for_findings(self):
        report = [{"RuleID": "generic-api-key", "File": "config.env", "StartLine": 3}]
        result = run_scanner(
            [
                sys.executable,
                "-c",
                "import sys; print(sys.argv[1]); sys.exit(1)",
                json.dumps(report),
            ],
            parser=parse_gitleaks,
            accepted_exit_codes=(0, 1),
        )

        self.assertEqual(result.process_result.returncode, 1)
        self.assertEqual(len(result.findings), 1)

    def test_rejects_unaccepted_exit_code_and_preserves_process_result(self):
        with self.assertRaises(ScanExecutionError) as raised:
            run_scanner(
                [sys.executable, "-c", "import sys; print('diagnostic'); sys.exit(7)"],
                parser=parse_semgrep,
            )

        self.assertEqual(raised.exception.process_result.returncode, 7)
        self.assertEqual(raised.exception.process_result.stdout.strip(), "diagnostic")

    def test_rejects_parser_output_that_is_not_a_finding(self):
        with self.assertRaises(TypeError):
            run_scanner(
                [sys.executable, "-c", "print('report')"],
                parser=lambda _report: ["not a Finding"],
            )

    def test_surfaces_malformed_scanner_report(self):
        with self.assertRaises(ValueError):
            run_scanner(
                [sys.executable, "-c", "print('{invalid json}')"],
                parser=parse_semgrep,
            )

    def test_rejects_empty_or_invalid_accepted_exit_codes(self):
        for codes in ((), (True,), ("0",), "0"):
            with self.subTest(codes=codes):
                with self.assertRaises(ScanExecutionError):
                    run_scanner(
                        [sys.executable, "-c", "print('{}')"],
                        parser=parse_semgrep,
                        accepted_exit_codes=codes,
                    )


if __name__ == "__main__":
    unittest.main()
