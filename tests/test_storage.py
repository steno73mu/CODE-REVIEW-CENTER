import json
import sys
import tempfile
import unittest
from pathlib import Path

from review_core.adapters import parse_semgrep
from review_core.orchestration import ScanJob, run_scan_batch
from review_core.storage import ScanStore


class ScanStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Path(self.temp_dir.name) / "review.sqlite3"
        self.store = ScanStore(self.database)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _batch(self):
        report = json.dumps({
            "results": [{
                "check_id": "test.rule",
                "path": "src/app.py",
                "start": {"line": 7, "col": 3},
                "extra": {"message": "Unsafe operation", "severity": "ERROR"},
            }]
        })
        return run_scan_batch([
            ScanJob(
                "semgrep",
                [sys.executable, "-c", "import sys; print(sys.argv[1])", report],
                parse_semgrep,
            )
        ])

    def test_persists_and_reloads_a_completed_scan_batch(self):
        batch = self._batch()
        self.store.save_batch("scan-001", batch)
        loaded = self.store.get_batch("scan-001")

        self.assertEqual(loaded["session_id"], "scan-001")
        self.assertEqual(loaded["status"], "completed")
        self.assertEqual(len(loaded["jobs"]), 1)
        self.assertEqual(loaded["jobs"][0]["status"], "succeeded")
        self.assertEqual(len(loaded["findings"]), 1)
        self.assertEqual(loaded["findings"][0]["path"], "src/app.py")

    def test_rejects_duplicate_session_ids_without_overwriting_history(self):
        self.store.save_batch("scan-001", self._batch())
        with self.assertRaises(ValueError):
            self.store.save_batch("scan-001", self._batch())
        self.assertEqual(self.store.get_batch("scan-001")["session_id"], "scan-001")

    def test_lists_sessions_newest_first(self):
        self.store.save_batch("scan-001", self._batch())
        self.store.save_batch("scan-002", self._batch())

        sessions = self.store.list_sessions()

        self.assertEqual({item["session_id"] for item in sessions}, {"scan-001", "scan-002"})
        self.assertEqual(len(sessions), 2)

    def test_missing_session_returns_none(self):
        self.assertIsNone(self.store.get_batch("missing"))

    def test_rejects_invalid_session_ids(self):
        for session_id in ("", " ", "../escape"):
            with self.subTest(session_id=session_id):
                with self.assertRaises(ValueError):
                    self.store.save_batch(session_id, self._batch())

    def test_persists_correlation_evidence_with_the_scan(self):
        import sys
        from review_core.finding import Finding
        from review_core.orchestration import ScanJob, run_scan_batch

        batch = run_scan_batch([
            ScanJob("engine-a", [sys.executable, "-c", "print('report')"],
                    lambda _report: [Finding(tool="A", path="a.py", start_line=3, message="Unsafe call")]),
            ScanJob("engine-b", [sys.executable, "-c", "print('report')"],
                    lambda _report: [Finding(tool="B", path="a.py", start_line=3, message="Unsafe call")]),
        ])
        self.store.save_batch("scan-correlated", batch)
        loaded = self.store.get_batch("scan-correlated")

        self.assertEqual(len(loaded["correlations"]), 1)
        self.assertEqual(loaded["correlations"][0]["evidence"][0]["method"], "same_location_and_message")


if __name__ == "__main__":
    unittest.main()
