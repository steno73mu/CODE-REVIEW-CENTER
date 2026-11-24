import unittest

from review_core import Finding, FindingSeverity


class FindingContractTests(unittest.TestCase):
    def test_rejects_empty_or_non_string_tool(self):
        for value in ("", "   ", None, 42):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    Finding(tool=value, message="Issue")

    def test_rejects_empty_or_non_string_message(self):
        for value in ("", "   ", None, 42):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    Finding(tool="scanner", message=value)

    def test_requires_a_known_severity_value(self):
        with self.assertRaises(ValueError):
            Finding(tool="scanner", message="Issue", severity="urgent")

    def test_rejects_non_positive_or_boolean_coordinates(self):
        for field in ("start_line", "start_column", "end_line", "end_column"):
            for value in (0, -1, True, 1.5, "2"):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        Finding(tool="scanner", message="Issue", **{field: value})

    def test_rejects_end_line_before_start_line(self):
        with self.assertRaises(ValueError):
            Finding(tool="scanner", message="Issue", start_line=9, end_line=8)

    def test_rejects_end_column_before_start_column_on_same_line(self):
        with self.assertRaises(ValueError):
            Finding(
                tool="scanner",
                message="Issue",
                start_line=9,
                start_column=12,
                end_line=9,
                end_column=4,
            )

    def test_rejects_non_string_optional_metadata(self):
        for field in ("rule_id", "tool_version", "path", "help_uri"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    Finding(tool="scanner", message="Issue", **{field: 7})

    def test_rejects_malformed_explicit_fingerprint(self):
        for value in ("not-a-hash", "a" * 63, "g" * 64):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    Finding(tool="scanner", message="Issue", fingerprint=value)

    def test_generates_a_sha256_fingerprint_by_default(self):
        finding = Finding(tool="scanner", message="Issue")
        self.assertEqual(len(finding.fingerprint), 64)
        self.assertEqual(finding.severity, FindingSeverity.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
