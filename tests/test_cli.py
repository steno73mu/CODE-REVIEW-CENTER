import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from review_core.cli import main


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name)
        self.project = self.home / "project"
        self.project.mkdir()
        self.environment = patch.dict(os.environ, {"CODE_REVIEW_CENTER_HOME": str(self.home / "app")})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temp_dir.cleanup()

    def invoke(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = main(args)
        return code, output.getvalue()

    def test_project_scanner_scan_and_history_work_as_one_cli_flow(self):
        code, output = self.invoke(["project", "add", "--name", "Demo", "--path", str(self.project)])
        self.assertEqual(code, 0, output)
        project_id = json.loads(output)["project_id"]

        command = [
            "python",
            "-c",
            "print('{\"results\": []}')",
            "{project_path}",
        ]
        code, output = self.invoke([
            "scanner", "add", "--id", "semgrep-local", "--name", "Semgrep local",
            "--parser", "semgrep", "--command-json", json.dumps(command),
        ])
        self.assertEqual(code, 0, output)

        code, output = self.invoke(["scan", "--project", project_id])
        self.assertEqual(code, 0, output)
        session_id = json.loads(output)["session_id"]

        code, output = self.invoke(["history", "show", session_id])
        self.assertEqual(code, 0, output)
        self.assertEqual(json.loads(output)["status"], "completed")

    def test_rejects_unknown_project_without_running_a_scanner(self):
        code, output = self.invoke(["scan", "--project", "missing"])
        self.assertEqual(code, 2)
        self.assertIn("unknown project", output)

    def test_remote_ai_review_requires_explicit_opt_in(self):
        code, output = self.invoke([
            "provider", "add", "--id", "remote", "--name", "Remote reviewer",
            "--url", "https://api.example.com/v1", "--model", "review-model",
        ])
        self.assertEqual(code, 0, output)
        self.assertNotIn("test-secret-key", output)
        code, output = self.invoke([
            "review", "--session", "missing-session", "--provider", "remote",
        ])
        self.assertEqual(code, 2)
        self.assertIn("unknown scan session", output)


if __name__ == "__main__":
    unittest.main()
