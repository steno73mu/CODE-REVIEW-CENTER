from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
import math
from pathlib import PurePosixPath

from .finding import Finding


@dataclass(frozen=True, slots=True)
class CorrelationEvidence:
    left_fingerprint: str
    right_fingerprint: str
    method: str
    similarity: float


@dataclass(frozen=True, slots=True)
class CorrelatedFinding:
    """A conservative group of cross-tool findings with explicit pairwise evidence."""

    findings: tuple[Finding, ...]
    evidence: tuple[CorrelationEvidence, ...]


def _normalized_path(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).as_posix()


def _normalized_message(message: str) -> str:
    return " ".join(message.casefold().split())


def correlate_findings(
    findings: Iterable[Finding],
    *,
    minimum_similarity: float = 0.95,
) -> tuple[CorrelatedFinding, ...]:
    """Group likely cross-tool duplicates only at the same file and line.

    This is deliberately conservative and explainable: missing locations are
    not correlated, same-tool findings are not merged, and every match records
    the exact location/message criterion and similarity score. Severity and
    original finding records are never rewritten.
    """
    if (
        isinstance(minimum_similarity, bool)
        or not isinstance(minimum_similarity, (int, float))
        or not math.isfinite(minimum_similarity)
        or not 0.0 <= minimum_similarity <= 1.0
    ):
        raise ValueError("minimum_similarity must be a number between 0 and 1")

    items = tuple(findings)
    if any(not isinstance(item, Finding) for item in items):
        raise TypeError("correlate_findings accepts only Finding instances")

    groups: list[list[Finding]] = []
    evidence_groups: list[list[CorrelationEvidence]] = []

    for candidate in items:
        if candidate.path is None or candidate.start_line is None:
            continue
        candidate_path = _normalized_path(candidate.path)
        candidate_message = _normalized_message(candidate.message)
        matched = False

        for group, evidence in zip(groups, evidence_groups):
            anchor = group[0]
            if any(item.tool.casefold() == candidate.tool.casefold() for item in group):
                continue
            if anchor.path is None or anchor.start_line is None:
                continue
            if _normalized_path(anchor.path) != candidate_path or anchor.start_line != candidate.start_line:
                continue

            similarity = SequenceMatcher(
                None,
                _normalized_message(anchor.message),
                candidate_message,
                autojunk=False,
            ).ratio()
            if similarity < minimum_similarity:
                continue

            group.append(candidate)
            evidence.append(
                CorrelationEvidence(
                    left_fingerprint=anchor.fingerprint,
                    right_fingerprint=candidate.fingerprint,
                    method="same_location_and_message",
                    similarity=similarity,
                )
            )
            matched = True
            break

        if not matched:
            groups.append([candidate])
            evidence_groups.append([])

    return tuple(
        CorrelatedFinding(tuple(group), tuple(evidence))
        for group, evidence in zip(groups, evidence_groups)
        if len(group) > 1
    )
