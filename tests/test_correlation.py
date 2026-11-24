import unittest

from review_core.correlation import correlate_findings
from review_core.finding import Finding, FindingSeverity


class FindingCorrelationTests(unittest.TestCase):
    def test_correlates_cross_tool_findings_with_same_location_and_message(self):
        findings = [
            Finding(tool="Semgrep", rule_id="rule-a", path="src/app.py", start_line=12, message="Unsafe deserialization"),
            Finding(tool="CodeQL", rule_id="rule-b", path="src/app.py", start_line=12, message="Unsafe deserialization"),
        ]

        groups = correlate_findings(findings)

        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0].findings), 2)
        self.assertEqual(groups[0].evidence[0].method, "same_location_and_message")
        self.assertEqual(groups[0].evidence[0].similarity, 1.0)

    def test_does_not_correlate_findings_from_the_same_tool(self):
        findings = [
            Finding(tool="Semgrep", path="app.py", start_line=2, message="Unsafe call"),
            Finding(tool="Semgrep", path="app.py", start_line=2, message="Unsafe call"),
        ]
        self.assertEqual(correlate_findings(findings), ())

    def test_does_not_correlate_different_locations_or_missing_locations(self):
        findings = [
            Finding(tool="A", path="app.py", start_line=2, message="Unsafe call"),
            Finding(tool="B", path="app.py", start_line=3, message="Unsafe call"),
            Finding(tool="C", message="Unsafe call"),
        ]
        self.assertEqual(correlate_findings(findings), ())

    def test_uses_a_conservative_similarity_threshold(self):
        findings = [
            Finding(tool="A", path="app.py", start_line=2, message="Unsafe deserialization detected"),
            Finding(tool="B", path="app.py", start_line=2, message="Unsafe deserialization was detected"),
        ]
        self.assertEqual(correlate_findings(findings, minimum_similarity=0.99), ())
        self.assertEqual(len(correlate_findings(findings, minimum_similarity=0.8)), 1)

    def test_exposes_pairwise_evidence_and_does_not_merge_severity(self):
        findings = [
            Finding(tool="A", path="app.py", start_line=2, message="Unsafe call", severity=FindingSeverity.HIGH),
            Finding(tool="B", path="app.py", start_line=2, message="Unsafe call", severity=FindingSeverity.LOW),
        ]
        group = correlate_findings(findings)[0]
        self.assertEqual([item.severity for item in group.findings], [FindingSeverity.HIGH, FindingSeverity.LOW])
        self.assertEqual(group.evidence[0].left_fingerprint, findings[0].fingerprint)
        self.assertEqual(group.evidence[0].right_fingerprint, findings[1].fingerprint)

    def test_correlates_normalized_windows_paths_and_messages_across_three_tools(self):
        findings = [
            Finding(
                tool="Semgrep",
                path="src\\\\app.py",
                start_line=12,
                message="  Unsafe   deserialization ",
            ),
            Finding(
                tool="CodeQL",
                path="src/app.py",
                start_line=12,
                message="unsafe deserialization",
            ),
            Finding(
                tool="Bandit",
                path="src//app.py",
                start_line=12,
                message="UNSAFE DESERIALIZATION",
            ),
        ]

        groups = correlate_findings(findings)

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].findings, tuple(findings))
        self.assertEqual(len(groups[0].evidence), 2)
        self.assertTrue(all(item.similarity == 1.0 for item in groups[0].evidence))
        self.assertTrue(
            all(item.left_fingerprint == findings[0].fingerprint for item in groups[0].evidence)
        )

    def test_rejects_invalid_similarity_threshold(self):
        for threshold in (-0.1, 1.1, True):
            with self.subTest(threshold=threshold):
                with self.assertRaises(ValueError):
                    correlate_findings([], minimum_similarity=threshold)

    def test_never_places_two_findings_from_the_same_tool_in_one_group(self):
        findings = [
            Finding(tool="A", path="app.py", start_line=2, message="Unsafe call"),
            Finding(tool="B", path="app.py", start_line=2, message="Unsafe call"),
            Finding(tool="B", path="app.py", start_line=2, message="Unsafe call"),
        ]
        groups = correlate_findings(findings)
        self.assertEqual(len(groups), 1)
        self.assertEqual([item.tool for item in groups[0].findings], ["A", "B"])


if __name__ == "__main__":
    unittest.main()
