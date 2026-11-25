from __future__ import annotations

from collections.abc import Iterable

from .finding import Finding


def deduplicate_findings(findings: Iterable[Finding]) -> list[Finding]:
    """Remove exact fingerprint duplicates while preserving first-seen order.

    The first occurrence is retained intentionally: this function does not
    merge evidence or silently choose a severity from competing sources.
    Cross-tool correlation is a separate concern from exact deduplication.
    """
    unique: list[Finding] = []
    seen: set[str] = set()

    for finding in findings:
        if not isinstance(finding, Finding):
            raise TypeError("deduplicate_findings accepts only Finding instances")
        if finding.fingerprint in seen:
            continue
        seen.add(finding.fingerprint)
        unique.append(finding)

    return unique
