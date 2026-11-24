import json
import tempfile
import unittest
from pathlib import Path

from review_core.reports import render_report, write_report


class ReportGenerationTests(unittest.TestCase):
    def _record(self):
        return {
            "session_id": "scan-001",
            "created_at": "2026-01-01T00:00:00+00:00",
            "status": "completed",
            "duration_seconds": 1.2,
            "cancelled": False,
            "jobs": [{"job_id": "semgrep", "status": "succeeded", "returncode": 0}],
            "findings": [{
                "tool": "Semgrep",
                "message": "Unsafe deserialization",
                "severity": "high",
                "rule_id": "python.security.audit",
                "path": "src/app.py",
                "start_line": 12,
                "start_column": 3,
                "fingerprint": "a" * 64,
                "help_uri": None,
            }],
            "correlations": [{
                "fingerprints": ["a" * 64, "b" * 64],
                "evidence": [{
                    "left_fingerprint": "a" * 64,
                    "right_fingerprint": "b" * 64,
                    "method": "same_location_and_message",
                    "similarity": 0.98,
                }],
            }],
            "ai_reviews": [],
        }

    def test_renders_machine_readable_json(self):
        rendered = render_report(self._record(), "json")
        self.assertEqual(json.loads(rendered)["session_id"], "scan-001")

    def test_renders_valid_sarif_structure_and_fingerprints(self):
        rendered = json.loads(render_report(self._record(), "sarif"))
        self.assertEqual(rendered["version"], "2.1.0")
        result = rendered["runs"][0]["results"][0]
        self.assertEqual(result["ruleId"], "python.security.audit")
        self.assertEqual(result["level"], "error")
        self.assertEqual(result["partialFingerprints"]["codeReviewCenterFingerprint"], "a" * 64)
        self.assertEqual(result["locations"][0]["physicalLocation"]["region"]["startLine"], 12)

    def test_renders_markdown_with_findings_and_correlation_evidence(self):
        rendered = render_report(self._record(), "markdown")
        self.assertIn("Unsafe deserialization", rendered)
        self.assertIn("98%", rendered)
        self.assertIn("src/app.py:12", rendered)

    def test_rejects_unknown_report_format(self):
        with self.assertRaises(ValueError):
            render_report(self._record(), "xml")

    def test_writes_report_without_overwriting_existing_file_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.md"
            write_report(target, "first")
            with self.assertRaises(FileExistsError):
                write_report(target, "second")
            self.assertEqual(target.read_text(encoding="utf-8"), "first")

    def test_can_explicitly_replace_existing_report(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.md"
            write_report(target, "first")
            write_report(target, "second", overwrite=True)
            self.assertEqual(target.read_text(encoding="utf-8"), "second")


if __name__ == "__main__":
    unittest.main()
