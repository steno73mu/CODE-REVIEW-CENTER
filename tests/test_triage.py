import json
import sys
import tempfile
import unittest
from pathlib import Path

from review_core.adapters import parse_semgrep
from review_core.orchestration import ScanJob, run_scan_batch
from review_core.storage import ScanStore
from review_core.triage import TriageStore


class TriageStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Path(self.temp_dir.name) / "review.sqlite3"
        self.scans = ScanStore(self.database)
        self.triage = TriageStore(self.database)
        report = json.dumps({
            "results": [{
                "check_id": "rule.test",
                "path": "app.py",
                "start": {"line": 4, "col": 1},
                "extra": {"message": "Unsafe call", "severity": "ERROR"},
            }]
        })
        batch = run_scan_batch([
            ScanJob("semgrep", [sys.executable, "-c", "import sys; print(sys.argv[1])", report], parse_semgrep)
        ])
        self.scans.save_batch("scan-triage", batch)
        self.fingerprint = batch.findings[0].fingerprint

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_lists_findings_as_open_until_triaged(self):
        records = self.triage.list_for_session("scan-triage")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "open")

    def test_updates_triage_status_and_note(self):
        record = self.triage.set_status(
            "scan-triage", self.fingerprint, "false_positive", note="Confirmed test fixture"
        )
        self.assertEqual(record["status"], "false_positive")
        self.assertEqual(record["note"], "Confirmed test fixture")
        self.assertEqual(self.triage.list_for_session("scan-triage")[0]["status"], "false_positive")

    def test_rejects_unknown_fingerprint_status_and_oversized_note(self):
        with self.assertRaises(ValueError):
            self.triage.set_status("scan-triage", "0" * 64, "fixed")
        with self.assertRaises(ValueError):
            self.triage.set_status("scan-triage", self.fingerprint, "unknown")
        with self.assertRaises(ValueError):
            self.triage.set_status("scan-triage", self.fingerprint, "fixed", note="x" * 4001)

    def test_requires_existing_scan_session(self):
        with self.assertRaises(ValueError):
            self.triage.list_for_session("missing")


if __name__ == "__main__":
    unittest.main()
