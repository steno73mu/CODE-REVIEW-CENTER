import unittest

from review_core import FindingSeverity, parse_sarif


def sarif_result(**overrides):
    result = {
        "ruleId": "python.security.sql-injection",
        "level": "error",
        "message": {"text": "Query uses string concatenation"},
        "locations": [{
            "physicalLocation": {
                "artifactLocation": {"uri": "src/app.py"},
                "region": {"startLine": 12, "startColumn": 4, "endLine": 12, "endColumn": 28},
            }
        }],
    }
    result.update(overrides)
    return result


def sarif_document(results, *, rule_level=None):
    rule = {"id": "python.security.sql-injection"}
    if rule_level:
        rule["defaultConfiguration"] = {"level": rule_level}
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [{
            "tool": {"driver": {"name": "ExampleScanner", "version": "3.2.1", "rules": [rule]}},
            "results": results,
        }],
    }


class SarifNormalizationTests(unittest.TestCase):
    def test_maps_error_and_preserves_location_and_provenance(self):
        finding = parse_sarif(sarif_document([sarif_result()]))[0]

        self.assertEqual(finding.severity, FindingSeverity.ERROR)
        self.assertEqual(finding.tool, "ExampleScanner")
        self.assertEqual(finding.tool_version, "3.2.1")
        self.assertEqual(finding.rule_id, "python.security.sql-injection")
        self.assertEqual(finding.path, "src/app.py")
        self.assertEqual(finding.start_line, 12)
        self.assertEqual(finding.start_column, 4)
        self.assertEqual(finding.end_line, 12)
        self.assertEqual(finding.end_column, 28)

    def test_uses_rule_default_level_when_result_level_is_missing(self):
        result = sarif_result()
        result.pop("level")
        finding = parse_sarif(sarif_document([result], rule_level="warning"))[0]
        self.assertEqual(finding.severity, FindingSeverity.WARNING)

    def test_maps_note_to_info_and_unknown_level_to_unknown(self):
        note = parse_sarif(sarif_document([sarif_result(level="note")]))[0]
        unknown = parse_sarif(sarif_document([sarif_result(level="none")]))[0]
        self.assertEqual(note.severity, FindingSeverity.INFO)
        self.assertEqual(unknown.severity, FindingSeverity.UNKNOWN)

    def test_skips_suppressed_and_non_problem_results(self):
        suppressed = sarif_result(suppressions=[{"kind": "external"}])
        not_problem = sarif_result(kind="notApplicable")
        findings = parse_sarif(sarif_document([suppressed, not_problem]))
        self.assertEqual(findings, [])

    def test_accepts_uri_with_spaces_and_normalizes_separators(self):
        result = sarif_result()
        result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] = "src\\legacy file.py"
        finding = parse_sarif(sarif_document([result]))[0]
        self.assertEqual(finding.path, "src/legacy file.py")

    def test_keeps_result_without_physical_location(self):
        result = sarif_result()
        result["locations"] = [{"logicalLocations": [{"name": "Database.query"}]}]
        finding = parse_sarif(sarif_document([result]))[0]
        self.assertIsNone(finding.path)
        self.assertIsNone(finding.start_line)

    def test_uses_first_physical_location_as_primary_location(self):
        result = sarif_result()
        result["locations"].append({
            "physicalLocation": {
                "artifactLocation": {"uri": "src/other.py"},
                "region": {"startLine": 99},
            }
        })
        finding = parse_sarif(sarif_document([result]))[0]
        self.assertEqual(finding.path, "src/app.py")
        self.assertEqual(finding.start_line, 12)

    def test_fingerprint_is_stable_for_equivalent_path_separators(self):
        first = sarif_result()
        second = sarif_result()
        second["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] = "src\\app.py"
        a = parse_sarif(sarif_document([first]))[0]
        b = parse_sarif(sarif_document([second]))[0]
        self.assertEqual(a.fingerprint, b.fingerprint)
        self.assertEqual(len(a.fingerprint), 64)

    def test_supports_json_text_input(self):
        import json
        findings = parse_sarif(json.dumps(sarif_document([sarif_result()])))
        self.assertEqual(len(findings), 1)

    def test_rejects_unsupported_sarif_version(self):
        document = sarif_document([])
        document["version"] = "2.0.0"
        with self.assertRaises(ValueError):
            parse_sarif(document)

    def test_rejects_malformed_document_shape(self):
        with self.assertRaises(ValueError):
            parse_sarif({"version": "2.1.0", "runs": "not-a-list"})

    def test_rejects_invalid_region_coordinates(self):
        result = sarif_result()
        result["locations"][0]["physicalLocation"]["region"]["startLine"] = 0
        with self.assertRaises(ValueError):
            parse_sarif(sarif_document([result]))

    def test_rejects_end_line_before_start_line(self):
        result = sarif_result()
        region = result["locations"][0]["physicalLocation"]["region"]
        region["endLine"] = 11
        with self.assertRaises(ValueError):
            parse_sarif(sarif_document([result]))

    def test_fingerprint_does_not_change_when_severity_changes(self):
        error = parse_sarif(sarif_document([sarif_result(level="error")]))[0]
        warning = parse_sarif(sarif_document([sarif_result(level="warning")]))[0]
        self.assertEqual(error.fingerprint, warning.fingerprint)


if __name__ == "__main__":
    unittest.main()
