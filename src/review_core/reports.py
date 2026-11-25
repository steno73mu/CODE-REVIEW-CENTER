from __future__ import annotations

from collections import defaultdict
import html
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any


def _level(severity: str) -> str:
    if severity in {"critical", "high", "error"}:
        return "error"
    if severity in {"medium", "warning"}:
        return "warning"
    return "note"


def _sarif(record: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for finding in record.get("findings", []):
        grouped[finding["tool"]].append(finding)
    runs = []
    triage_by_fingerprint = {item["fingerprint"]: item for item in record.get("triage", [])}
    for tool, findings in grouped.items():
        rules = list(dict.fromkeys(x.get("rule_id") for x in findings if x.get("rule_id")))
        results = []
        for finding in findings:
            item = {
                "level": _level(finding.get("severity", "unknown")),
                "message": {"text": finding["message"]},
                "partialFingerprints": {"codeReviewCenterFingerprint": finding["fingerprint"]},
                "properties": {"sourceTool": tool, "normalizedSeverity": finding.get("severity", "unknown")},
            }
            triage = triage_by_fingerprint.get(finding["fingerprint"])
            if triage:
                item["properties"]["triageStatus"] = triage.get("status", "open")
                if triage.get("note"):
                    item["properties"]["triageNote"] = triage["note"]
            if finding.get("rule_id"):
                item["ruleId"] = finding["rule_id"]
            if finding.get("help_uri"):
                item["helpUri"] = finding["help_uri"]
            if finding.get("path"):
                physical = {"artifactLocation": {"uri": finding["path"]}}
                region = {}
                for key in ("start_line", "start_column", "end_line", "end_column"):
                    if finding.get(key) is not None:
                        region_key = {
                            "start_line": "startLine", "start_column": "startColumn",
                            "end_line": "endLine", "end_column": "endColumn",
                        }[key]
                        region[region_key] = finding[key]
                if region:
                    physical["region"] = region
                item["locations"] = [{"physicalLocation": physical}]
            results.append(item)
        run = {
            "tool": {"driver": {
                "name": tool,
                "rules": [{"id": rule, "shortDescription": {"text": rule}} for rule in rules],
            }},
            "results": results,
        }
        if record.get("correlations"):
            run["properties"] = {"codeReviewCenterCorrelations": record["correlations"]}
        runs.append(run)
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": runs,
    }


def _markdown(record: dict[str, Any]) -> str:
    def cell(value: object) -> str:
        escaped = html.escape(str(value if value is not None else ""))
        escaped = escaped.replace("\\", "\\\\")
        for character in ("`", "*", "_", "{", "}", "[", "]", "(", ")", "!", "~"):
            escaped = escaped.replace(character, "\\" + character)
        return escaped.replace("|", "&#124;").replace("\n", " ")

    findings = record.get("findings", [])
    jobs = record.get("jobs", [])
    correlations = record.get("correlations", [])
    lines = [
        "# CODE-REVIEW-CENTER report", "",
        f"- **Session:** {cell(record.get('session_id'))}",
        f"- **Status:** {cell(record.get('status'))}",
        f"- **Duration:** {record.get('duration_seconds', 0):.2f}s",
        f"- **Scanner jobs:** {len(jobs)}",
        f"- **Unique findings:** {len(findings)}",
        f"- **Correlation groups:** {len(correlations)}", "",
        "## Findings", "",
        "| Severity | Tool | Rule | Location | Finding |",
        "|---|---|---|---|---|",
    ]
    for finding in findings:
        location = finding.get("path") or ""
        if finding.get("start_line") is not None:
            location += f":{finding['start_line']}"
        values = (
            finding.get("severity"), finding.get("tool"), finding.get("rule_id"),
            location, finding.get("message"),
        )
        lines.append("| " + " | ".join(cell(value) for value in values) + " |")
    if not findings:
        lines.append("| — | — | — | — | No findings reported |")
    lines.extend(["", "## Cross-engine correlation", ""])
    if correlations:
        for index, group in enumerate(correlations, start=1):
            scores = ", ".join(f"{item.get('similarity', 0):.0%}" for item in group.get("evidence", []))
            lines.append(f"{index}. {len(group.get('fingerprints', []))} findings linked · similarity: {cell(scores)}")
    else:
        lines.append("No cross-engine correlation groups.")
    lines.extend(["", "## Scanner outcomes", "", "| Scanner | Status | Exit code |", "|---|---|---:|"])
    for job in jobs:
        code = job.get("returncode") if job.get("returncode") is not None else "—"
        lines.append(f"| {cell(job.get('job_id'))} | {cell(job.get('status'))} | {cell(code)} |")
    lines.extend(["", "## Triage", "", "| Status | Tool | Location | Note |", "|---|---|---|---|"])
    triage_items = record.get("triage", [])
    for item in triage_items:
        location = item.get("path") or ""
        if item.get("start_line") is not None:
            location += ":" + str(item["start_line"])
        values = (item.get("status", "open"), item.get("tool"), location, item.get("note"))
        lines.append("| " + " | ".join(cell(value) for value in values) + " |")
    if not triage_items:
        lines.append("No triage updates have been recorded.")
    lines.extend(["", "## AI reviews", ""])
    reviews = record.get("ai_reviews", [])
    if reviews:
        for review in reviews:
            review_content = str(review.get("content") or "")
            longest_backtick_run = max(
                (len(match.group(0)) for match in re.finditer(r"`+", review_content)),
                default=0,
            )
            fence = "`" * max(3, longest_backtick_run + 1)
            lines.extend([
                f"### {cell(review.get('provider_id'))} · {cell(review.get('model'))}",
                "",
                f"{fence}text",
                review_content,
                fence,
                "",
            ])
    else:
        lines.append("No AI review has been saved for this session.")
    return "\n".join(lines).rstrip() + "\n"


def render_report(record: dict[str, Any], format: str) -> str:
    """Render a scan-history record as JSON, SARIF 2.1.0, or Markdown."""
    if not isinstance(record, dict):
        raise TypeError("record must be a scan-history mapping")
    if format == "json":
        return json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if format == "sarif":
        return json.dumps(_sarif(record), ensure_ascii=False, indent=2) + "\n"
    if format == "markdown":
        return _markdown(record)
    raise ValueError("format must be one of: json, sarif, markdown")


def write_report(path: str | Path, content: str, *, overwrite: bool = False) -> Path:
    """Write UTF-8 output; overwriting requires explicit confirmation."""
    if not isinstance(content, str):
        raise TypeError("report content must be a string")
    if not isinstance(overwrite, bool):
        raise ValueError("overwrite must be a boolean")
    target = Path(path).expanduser()
    if not target.parent.exists() or not target.parent.is_dir():
        raise ValueError("report destination directory does not exist")
    if not overwrite:
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        return target
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=target.parent,
            prefix=f".{target.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return target
