import tempfile
import unittest
from pathlib import Path

from review_core.configuration import ScannerConfigStore, ScannerProfile


class ScannerConfigStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = ScannerConfigStore(Path(self.temp_dir.name) / "config.sqlite3")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_saves_and_loads_scanner_profile(self):
        profile = ScannerProfile(
            scanner_id="semgrep-default",
            name="Semgrep",
            parser="semgrep",
            command=("semgrep", "scan", "--json", "{project_path}"),
            accepted_exit_codes=(0, 1),
            timeout_seconds=180,
        )
        self.store.save(profile)
        self.assertEqual(self.store.get("semgrep-default"), profile)
        self.assertEqual(self.store.list_profiles(), [profile])

    def test_rejects_shell_strings_and_unknown_parser(self):
        with self.assertRaises(ValueError):
            ScannerProfile("bad", "Bad", "semgrep", "semgrep scan", (0,), 60)
        with self.assertRaises(ValueError):
            ScannerProfile("bad", "Bad", "custom-python", ("python", "scan"), (0,), 60)

    def test_rejects_invalid_placeholders_and_exit_codes(self):
        for command, codes in (
            (("semgrep", "{unknown}"), (0,)),
            (("semgrep",), (True,)),
            (("semgrep",), ()),
        ):
            with self.subTest(command=command, codes=codes):
                with self.assertRaises(ValueError):
                    ScannerProfile("bad", "Bad", "semgrep", command, codes, 60)

    def test_rejects_duplicate_ids_and_supports_removal(self):
        profile = ScannerProfile("semgrep", "Semgrep", "semgrep", ("semgrep",), (0,), 60)
        self.store.save(profile)
        with self.assertRaises(ValueError):
            self.store.save(profile)
        self.assertTrue(self.store.remove("semgrep"))
        self.assertFalse(self.store.remove("semgrep"))


if __name__ == "__main__":
    unittest.main()
