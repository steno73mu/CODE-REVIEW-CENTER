import json
import sys
import threading
import time
import unittest

from review_core.orchestration import (
    ScanJob,
    ScanStatus,
    run_scan_batch,
)
from review_core.scanning import run_scanner
from review_core.adapters import parse_semgrep


def _semgrep_report(path="app.py"):
    return json.dumps({
        "results": [{
            "check_id": "test.rule",
            "path": path,
            "start": {"line": 1, "col": 1},
            "extra": {"message": "Test finding", "severity": "WARNING"},
        }]
    })


class ScanOrchestrationTests(unittest.TestCase):
    def test_runs_multiple_scanners_concurrently_and_preserves_job_order(self):
        jobs = [
            ScanJob("semgrep", [sys.executable, "-c", "import sys,time; time.sleep(.15); print(sys.argv[1])", _semgrep_report("a.py")], parse_semgrep),
            ScanJob("second", [sys.executable, "-c", "print('{\"results\": []}')"], parse_semgrep),
        ]
        started = time.monotonic()
        result = run_scan_batch(jobs, max_workers=2)

        self.assertEqual([item.job_id for item in result.jobs], ["semgrep", "second"])
        self.assertTrue(all(item.status is ScanStatus.SUCCEEDED for item in result.jobs))
        self.assertGreaterEqual(result.duration_seconds, 0)
        self.assertLess(time.monotonic() - started, .8)

    def test_isolates_one_scanner_failure_and_returns_other_results(self):
        jobs = [
            ScanJob("bad", ["__crc_missing_scanner__"], parse_semgrep),
            ScanJob("good", [sys.executable, "-c", "print('{\"results\": []}')"], parse_semgrep),
        ]
        result = run_scan_batch(jobs, max_workers=2)

        self.assertEqual(result.jobs[0].status, ScanStatus.FAILED)
        self.assertEqual(result.jobs[1].status, ScanStatus.SUCCEEDED)
        self.assertEqual(len(result.findings), 0)

    def test_deduplicates_findings_across_scanner_results_without_mutating_evidence(self):
        report = _semgrep_report()
        jobs = [
            ScanJob("one", [sys.executable, "-c", "import sys; print(sys.argv[1])", report], parse_semgrep),
            ScanJob("two", [sys.executable, "-c", "import sys; print(sys.argv[1])", report], parse_semgrep),
        ]
        result = run_scan_batch(jobs, max_workers=2)

        self.assertEqual(len(result.findings), 1)
        self.assertEqual(sum(len(item.scan_result.findings) for item in result.jobs), 2)

    def test_cancellation_prevents_not_yet_started_jobs(self):
        cancel = threading.Event()
        cancel.set()
        jobs = [ScanJob("one", [sys.executable, "-c", "print('{\"results\": []}')"], parse_semgrep)]
        result = run_scan_batch(jobs, cancel_event=cancel)

        self.assertEqual(result.jobs[0].status, ScanStatus.CANCELLED)

    def test_rejects_duplicate_ids_and_invalid_worker_count(self):
        job = ScanJob("same", [sys.executable, "-c", "print('{\"results\": []}')"], parse_semgrep)
        with self.assertRaises(ValueError):
            run_scan_batch([job, job])
        with self.assertRaises(ValueError):
            run_scan_batch([job], max_workers=0)

    def test_marks_job_timeout_without_aborting_batch(self):
        jobs = [
            ScanJob("slow", [sys.executable, "-c", "import time; time.sleep(2)"], parse_semgrep, timeout_seconds=.05),
            ScanJob("fast", [sys.executable, "-c", "print('{\"results\": []}')"], parse_semgrep),
        ]
        result = run_scan_batch(jobs, max_workers=2)

        self.assertEqual(result.jobs[0].status, ScanStatus.TIMED_OUT)
        self.assertEqual(result.jobs[1].status, ScanStatus.SUCCEEDED)


if __name__ == "__main__":
    unittest.main()
