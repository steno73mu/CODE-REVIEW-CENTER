import json
import unittest

from review_core import FindingSeverity, parse_gitleaks, parse_semgrep


class SemgrepAdapterTests(unittest.TestCase):
    def test_maps_result_fields_and_severity(self):
        report = {
            "version": "1.186.0",
            "results": [{
                "check_id": "python.lang.security.audit.eval-detected",
                "path": "src/app.py",
                "start": {"line": 8, "col": 3},
                "end": {"line": 8, "col": 12},
                "extra": {"message": "Avoid eval on untrusted input", "severity": "ERROR"},
            }],
        }
        finding = parse_semgrep(report)[0]
        self.assertEqual(finding.tool, "Semgrep")
        self.assertEqual(finding.tool_version, "1.186.0")
        self.assertEqual(finding.rule_id, "python.lang.security.audit.eval-detected")
        self.assertEqual(finding.severity, FindingSeverity.ERROR)
        self.assertEqual(finding.path, "src/app.py")
        self.assertEqual((finding.start_line, finding.start_column), (8, 3))
        self.assertEqual((finding.end_line, finding.end_column), (8, 12))

    def test_maps_warning_and_info(self):
        base = {"path": "a.py", "start": {"line": 1}, "end": {"line": 1}}
        reports = [
            {**base, "check_id": "warning-rule", "extra": {"message": "Warn", "severity": "WARNING"}},
            {**base, "check_id": "info-rule", "extra": {"message": "Info", "severity": "INFO"}},
        ]
        findings = parse_semgrep({"results": reports})
        self.assertEqual([f.severity for f in findings], [FindingSeverity.WARNING, FindingSeverity.INFO])

    def test_accepts_json_text_and_empty_results(self):
        self.assertEqual(parse_semgrep(json.dumps({"results": []})), [])

    def test_rejects_malformed_semgrep_report(self):
        for report in ([], {"results": "bad"}, {"results": [None]}):
            with self.subTest(report=report):
                with self.assertRaises(ValueError):
                    parse_semgrep(report)

    def test_rejects_invalid_semgrep_coordinates(self):
        report = {"results": [{
            "check_id": "rule", "path": "a.py",
            "start": {"line": True}, "end": {"line": 2},
            "extra": {"message": "Issue", "severity": "ERROR"},
        }]}
        with self.assertRaises(ValueError):
            parse_semgrep(report)


class GitleaksAdapterTests(unittest.TestCase):
    def test_maps_report_without_copying_secret_material(self):
        report = [{
            "RuleID": "generic-api-key",
            "Description": "Generic API Key",
            "File": ".env",
            "StartLine": 4,
            "EndLine": 4,
            "StartColumn": 1,
            "EndColumn": 24,
            "Secret": "DO_NOT_PERSIST_THIS_SECRET",
            "Match": "API_KEY=DO_NOT_PERSIST_THIS_SECRET",
            "Fingerprint": "commit:path:rule:4",
        }]
        finding = parse_gitleaks(report)[0]
        self.assertEqual(finding.tool, "Gitleaks")
        self.assertEqual(finding.rule_id, "generic-api-key")
        self.assertEqual(finding.message, "Generic API Key")
        self.assertEqual(finding.path, ".env")
        self.assertEqual(finding.severity, FindingSeverity.UNKNOWN)
        self.assertFalse(hasattr(finding, "secret"))
        self.assertNotIn("DO_NOT_PERSIST_THIS_SECRET", repr(finding))

    def test_accepts_json_text_and_empty_report(self):
        self.assertEqual(parse_gitleaks("[]"), [])

    def test_rejects_malformed_gitleaks_report(self):
        for report in ({}, [{"RuleID": "x"}], [None]):
            with self.subTest(report=report):
                with self.assertRaises(ValueError):
                    parse_gitleaks(report)

    def test_generates_deterministic_project_fingerprint(self):
        item = {"RuleID": "token", "Description": "Token found", "File": "a.env", "StartLine": 2}
        first = parse_gitleaks([item])[0]
        second = parse_gitleaks([dict(item)])[0]
        self.assertEqual(first.fingerprint, second.fingerprint)


if __name__ == "__main__":
    unittest.main()
