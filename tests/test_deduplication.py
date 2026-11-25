import unittest

from review_core import FindingSeverity, deduplicate_findings, parse_sarif


def finding_document(path="src/app.py", line=12, message="Unsafe query"):
    return {
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "ExampleScanner"}},
            "results": [{
                "ruleId": "sql-injection",
                "level": "warning",
                "message": {"text": message},
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": path},
                        "region": {"startLine": line},
                    }
                }],
            }],
        }],
    }


class DeduplicationTests(unittest.TestCase):
    def test_removes_repeated_findings_and_preserves_first_seen_order(self):
        first = parse_sarif(finding_document())[0]
        second = parse_sarif(finding_document(path="src/other.py"))[0]
        repeated_first = parse_sarif(finding_document())[0]

        result = deduplicate_findings([first, second, repeated_first])

        self.assertEqual(result, [first, second])

    def test_keeps_findings_at_different_lines(self):
        first = parse_sarif(finding_document(line=12))[0]
        second = parse_sarif(finding_document(line=13))[0]

        self.assertEqual(len(deduplicate_findings([first, second])), 2)

    def test_keeps_findings_with_different_messages(self):
        first = parse_sarif(finding_document(message="Unsafe query"))[0]
        second = parse_sarif(finding_document(message="Untrusted SQL"))[0]

        self.assertEqual(len(deduplicate_findings([first, second])), 2)

    def test_rejects_non_finding_items(self):
        with self.assertRaises(TypeError):
            deduplicate_findings([object()])


if __name__ == "__main__":
    unittest.main()
