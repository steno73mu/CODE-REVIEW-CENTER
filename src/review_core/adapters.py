from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any

from .finding import Finding, FindingSeverity


_SEMGREP_SEVERITIES = {
    "error": FindingSeverity.ERROR,
    "warning": FindingSeverity.WARNING,
    "info": FindingSeverity.INFO,
}


def parse_semgrep(document: Mapping[str, Any] | str | bytes) -> list[Finding]:
    """Normalize Semgrep's JSON report without retaining source snippets."""
    data = _decode_json(document, "Semgrep")
    if not isinstance(data, Mapping):
        raise ValueError("Semgrep report must be a JSON object")

    results = data.get("results")
    if not isinstance(results, list):
        raise ValueError("Semgrep report 'results' must be an array")

    version = data.get("version")
    if version is not None and not isinstance(version, str):
        raise ValueError("Semgrep report 'version' must be a string")

    findings: list[Finding] = []
    for index, result in enumerate(results):
        if not isinstance(result, Mapping):
            raise ValueError(f"Semgrep result at index {index} must be an object")

        rule_id = _required_string(result.get("check_id"), f"Semgrep result {index} check_id")
        path = _required_string(result.get("path"), f"Semgrep result {index} path")
        extra = result.get("extra", {})
        if not isinstance(extra, Mapping):
            raise ValueError(f"Semgrep result at index {index} extra must be an object")

        message = _optional_string(extra.get("message")) or rule_id
        severity_value = _optional_string(extra.get("severity"))
        severity = _SEMGREP_SEVERITIES.get(
            severity_value.casefold() if severity_value else "",
            FindingSeverity.UNKNOWN,
        )
        start = result.get("start", {})
        end = result.get("end", {})
        if not isinstance(start, Mapping) or not isinstance(end, Mapping):
            raise ValueError(f"Semgrep result at index {index} positions must be objects")

        findings.append(
            Finding(
                tool="Semgrep",
                tool_version=version,
                rule_id=rule_id,
                message=message,
                severity=severity,
                path=path,
                start_line=_optional_coordinate(start.get("line"), "start.line"),
                start_column=_optional_coordinate(start.get("col"), "start.col"),
                end_line=_optional_coordinate(end.get("line"), "end.line"),
                end_column=_optional_coordinate(end.get("col"), "end.col"),
            )
        )
    return findings


def parse_gitleaks(document: list[Any] | str | bytes) -> list[Finding]:
    """Normalize Gitleaks JSON while deliberately discarding secret values.

    Gitleaks reports contain Secret and Match fields. Neither is copied into
    Finding: storing the detected credential in the review database/report
    would create a second secret store.
    """
    data = _decode_json(document, "Gitleaks")
    if not isinstance(data, list):
        raise ValueError("Gitleaks report must be a JSON array")

    findings: list[Finding] = []
    for index, result in enumerate(data):
        if not isinstance(result, Mapping):
            raise ValueError(f"Gitleaks finding at index {index} must be an object")

        rule_id = _required_string(result.get("RuleID"), f"Gitleaks finding {index} RuleID")
        description = _optional_string(result.get("Description"))
        path = _required_string(result.get("File"), f"Gitleaks finding {index} File")
        message = description or f"Secret detected by Gitleaks rule {rule_id}"

        findings.append(
            Finding(
                tool="Gitleaks",
                rule_id=rule_id,
                message=message,
                severity=FindingSeverity.UNKNOWN,
                path=path,
                start_line=_optional_coordinate(result.get("StartLine"), "StartLine"),
                start_column=_optional_coordinate(result.get("StartColumn"), "StartColumn"),
                end_line=_optional_coordinate(result.get("EndLine"), "EndLine"),
                end_column=_optional_coordinate(result.get("EndColumn"), "EndColumn"),
            )
        )
    return findings


def _decode_json(document: Any, tool: str) -> Any:
    if isinstance(document, (str, bytes)):
        try:
            return json.loads(document)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"Invalid {tool} JSON: {exc}") from exc
    if isinstance(document, (Mapping, list)):
        return document
    raise ValueError(f"{tool} input must be a decoded JSON value or JSON text")


def _required_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _optional_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if value is None:
        return None
    raise ValueError("Expected a string value")


def _optional_coordinate(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value
