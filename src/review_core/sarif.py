from __future__ import annotations

from collections.abc import Mapping
import json
import posixpath
from typing import Any
from urllib.parse import unquote, urlsplit

from .finding import Finding, FindingSeverity


_LEVELS = {
    "error": FindingSeverity.ERROR,
    "warning": FindingSeverity.WARNING,
    "note": FindingSeverity.INFO,
    "none": FindingSeverity.UNKNOWN,
}


def parse_sarif(document: Mapping[str, Any] | str | bytes) -> list[Finding]:
    """Normalize SARIF 2.1.0 results into the project's Finding contract.

    Suppressed results and results explicitly marked as pass/notApplicable are
    omitted. A result without a physical location is retained with path=None.
    """
    if isinstance(document, (str, bytes)):
        try:
            document = json.loads(document)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"Invalid SARIF JSON: {exc}") from exc

    if not isinstance(document, Mapping):
        raise ValueError("SARIF document must be a JSON object")
    if document.get("version") != "2.1.0":
        raise ValueError("Only SARIF version 2.1.0 is supported")

    runs = document.get("runs")
    if not isinstance(runs, list):
        raise ValueError("SARIF document 'runs' must be an array")

    findings: list[Finding] = []
    for run_index, run in enumerate(runs):
        if not isinstance(run, Mapping):
            raise ValueError(f"SARIF run at index {run_index} must be an object")
        findings.extend(_parse_run(run, run_index))
    return findings


def _parse_run(run: Mapping[str, Any], run_index: int) -> list[Finding]:
    tool = run.get("tool")
    driver = tool.get("driver") if isinstance(tool, Mapping) else None
    if not isinstance(driver, Mapping):
        raise ValueError(f"SARIF run at index {run_index} has no tool.driver object")

    tool_name = _nonempty_string(driver.get("name")) or "Unknown tool"
    tool_version = _nonempty_string(driver.get("version"))
    rules = driver.get("rules", [])
    if not isinstance(rules, list):
        raise ValueError(f"SARIF run at index {run_index} has invalid tool.driver.rules")
    rule_by_id = {
        rule["id"]: rule
        for rule in rules
        if isinstance(rule, Mapping) and isinstance(rule.get("id"), str)
    }

    artifacts = run.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError(f"SARIF run at index {run_index} has invalid artifacts")

    results = run.get("results", [])
    if not isinstance(results, list):
        raise ValueError(f"SARIF run at index {run_index} has invalid results")

    findings: list[Finding] = []
    for result_index, result in enumerate(results):
        if not isinstance(result, Mapping):
            raise ValueError(
                f"SARIF result at run {run_index}, index {result_index} must be an object"
            )
        if result.get("suppressions"):
            continue
        if result.get("kind") in {"pass", "notApplicable"}:
            continue

        rule_id = _nonempty_string(result.get("ruleId"))
        rule = rule_by_id.get(rule_id or "", {})
        level = result.get("level")
        if level is None:
            configuration = rule.get("defaultConfiguration", {})
            level = configuration.get("level") if isinstance(configuration, Mapping) else None
        severity = _LEVELS.get(level, FindingSeverity.UNKNOWN)

        message_data = result.get("message", {})
        message = ""
        if isinstance(message_data, Mapping):
            message = (
                _nonempty_string(message_data.get("text"))
                or _nonempty_string(message_data.get("markdown"))
                or ""
            )
        if not message:
            message = rule_id or "Finding reported without a message"

        location = _primary_location(result.get("locations", []), artifacts)
        findings.append(
            Finding(
                tool=tool_name,
                tool_version=tool_version,
                rule_id=rule_id,
                message=message,
                severity=severity,
                path=location["path"],
                start_line=location["start_line"],
                start_column=location["start_column"],
                end_line=location["end_line"],
                end_column=location["end_column"],
                help_uri=_nonempty_string(rule.get("helpUri")),
            )
        )
    return findings


def _primary_location(
    locations: Any, artifacts: list[Any]
) -> dict[str, str | int | None]:
    if not isinstance(locations, list):
        raise ValueError("SARIF result 'locations' must be an array")

    for location in locations:
        if not isinstance(location, Mapping):
            continue
        physical = location.get("physicalLocation")
        if not isinstance(physical, Mapping):
            continue

        artifact_location = physical.get("artifactLocation", {})
        if not isinstance(artifact_location, Mapping):
            artifact_location = {}
        uri = _nonempty_string(artifact_location.get("uri"))
        if uri is None:
            index = artifact_location.get("index")
            if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(artifacts):
                artifact = artifacts[index]
                if isinstance(artifact, Mapping):
                    artifact_location = artifact.get("location", {})
                    if isinstance(artifact_location, Mapping):
                        uri = _nonempty_string(artifact_location.get("uri"))

        region = physical.get("region", {})
        if not isinstance(region, Mapping):
            region = {}
        start_line = _coordinate(region.get("startLine"), "startLine")
        start_column = _coordinate(region.get("startColumn"), "startColumn")
        end_line = _coordinate(region.get("endLine"), "endLine")
        end_column = _coordinate(region.get("endColumn"), "endColumn")
        if start_line is not None and end_line is not None and end_line < start_line:
            raise ValueError("SARIF region endLine must not precede startLine")
        if (
            start_line is not None
            and end_line == start_line
            and start_column is not None
            and end_column is not None
            and end_column < start_column
        ):
            raise ValueError("SARIF region endColumn must not precede startColumn")

        return {
            "path": _normalize_uri(uri) if uri else None,
            "start_line": start_line,
            "start_column": start_column,
            "end_line": end_line,
            "end_column": end_column,
        }

    return {
        "path": None,
        "start_line": None,
        "start_column": None,
        "end_line": None,
        "end_column": None,
    }


def _coordinate(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"SARIF region {name} must be a positive integer")
    return value


def _normalize_uri(uri: str) -> str:
    """Convert common SARIF file URIs to stable slash-separated paths."""
    parsed = urlsplit(uri)
    if parsed.scheme.casefold() == "file":
        uri = unquote(parsed.path)
    elif len(parsed.scheme) == 1 and len(uri) > 2 and uri[1:3] in {":/", ":\\"}:
        uri = unquote(uri)
    else:
        uri = unquote(uri)

    normalized = uri.replace("\\", "/")
    if normalized.startswith("//"):
        return normalized
    return posixpath.normpath(normalized)


def _nonempty_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
