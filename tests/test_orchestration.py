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
from review_core.finding import Finding


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

    def test_cancellation_stops_an_already_running_scanner(self):
        cancellation = threading.Event()

        def cancel_soon():
            time.sleep(0.1)
            cancellation.set()

        thread = threading.Thread(target=cancel_soon)
        thread.start()
        try:
            result = run_scan_batch(
                [ScanJob("slow", [sys.executable, "-c", "import time; time.sleep(5)"], parse_semgrep)],
                cancel_event=cancellation,
            )
        finally:
            thread.join(timeout=1)

        self.assertEqual(result.jobs[0].status, ScanStatus.CANCELLED)

    def test_parser_exception_text_is_not_exposed_in_scan_result(self):
        secret = "SENSITIVE-REPORT-CONTENT"

        def unsafe_parser(_report):
            raise ValueError(secret)

        result = run_scan_batch([
            ScanJob("parser-error", [sys.executable, "-c", "print('report')"], unsafe_parser)
        ])

        self.assertEqual(result.jobs[0].status, ScanStatus.FAILED)
        self.assertNotIn(secret, result.jobs[0].error)

    def test_batch_includes_explainable_cross_engine_correlations(self):
        first = lambda _report: [Finding(tool="EngineA", path="app.py", start_line=9, message="Unsafe call")]
        second = lambda _report: [Finding(tool="EngineB", path="app.py", start_line=9, message="Unsafe call")]
        jobs = [
            ScanJob("a", [sys.executable, "-c", "print('report')"], first),
            ScanJob("b", [sys.executable, "-c", "print('report')"], second),
        ]
        result = run_scan_batch(jobs, max_workers=2)
        self.assertEqual([item.status for item in result.jobs], [ScanStatus.SUCCEEDED, ScanStatus.SUCCEEDED])
        self.assertEqual(len(result.findings), 2)
        self.assertEqual(len(result.correlations), 1)
        self.assertEqual(len(result.correlations[0].findings), 2)

    def test_preserves_process_evidence_when_scanner_exit_code_is_unaccepted(self):
        result = run_scan_batch([
            ScanJob("nonzero", [sys.executable, "-c", "import sys; print('report'); sys.exit(7)"], parse_semgrep)
        ])
        self.assertEqual(result.jobs[0].status, ScanStatus.FAILED)
        self.assertEqual(result.jobs[0].process_result.returncode, 7)

    def test_rejects_empty_scan_batch(self):
        with self.assertRaises(ValueError):
            run_scan_batch([])

    def test_rejects_invalid_worker_limits_and_duplicate_job_ids(self):
        job = ScanJob("same", [sys.executable, "-c", "print('{}')"], parse_semgrep)
        for workers in (0, 33, True):
            with self.subTest(workers=workers), self.assertRaises(ValueError):
                run_scan_batch([job], max_workers=workers)
        with self.assertRaises(ValueError):
            run_scan_batch([job, job])

if __name__ == "__main__":
    unittest.main()
