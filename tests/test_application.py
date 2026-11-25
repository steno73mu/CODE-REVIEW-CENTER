import json
import sys
import unittest
from pathlib import Path
from threading import Event

from review_core.application import build_scan_jobs, scan_project
from review_core.configuration import ScannerProfile
from review_core.projects import Project
from review_core.orchestration import ScanStatus


class ApplicationServiceTests(unittest.TestCase):
    def setUp(self):
        self.project = Project("project-id", "Demo", str(Path.cwd()), "2026-01-01T00:00:00+00:00")

    def test_builds_commands_with_project_path_as_one_argument(self):
        profile = ScannerProfile(
            "semgrep", "Semgrep", "semgrep",
            ("semgrep", "scan", "{project_path}"), (0,), 30,
        )
        jobs = build_scan_jobs(self.project, [profile])

        self.assertEqual(jobs[0].command[-1], self.project.path)
        self.assertEqual(jobs[0].cwd, self.project.path)

    def test_disabled_profiles_are_not_scheduled(self):
        profile = ScannerProfile(
            "disabled", "Disabled", "semgrep",
            ("semgrep", "{project_path}"), (0,), 30, enabled=False,
        )
        self.assertEqual(build_scan_jobs(self.project, [profile]), ())

    def test_scan_project_runs_profile_and_returns_normalized_findings(self):
        report = json.dumps({"results": []})
        profile = ScannerProfile(
            "test", "Test", "semgrep",
            (sys.executable, "-c", "import sys; print(sys.argv[1])", report),
            (0,), 30,
        )
        batch = scan_project(self.project, [profile])

        self.assertEqual(batch.jobs[0].status, ScanStatus.SUCCEEDED)
        self.assertEqual(batch.findings, ())

    def test_scan_project_respects_cancellation(self):
        profile = ScannerProfile(
            "test", "Test", "semgrep",
            (sys.executable, "-c", "print('{\"results\": []}')"), (0,), 30,
        )
        cancellation = Event()
        cancellation.set()
        batch = scan_project(self.project, [profile], cancel_event=cancellation)

        self.assertEqual(batch.jobs[0].status, ScanStatus.CANCELLED)


if __name__ == "__main__":
    unittest.main()
