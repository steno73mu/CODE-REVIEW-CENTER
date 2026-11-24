# Architecture overview

## Product boundary

CODE-REVIEW-CENTER is an independent application. The repositories and tools studied during research are not copied wholesale and do not define this product's architecture.

The application owns the workflow and the normalized domain model. External tools are replaceable analysis engines connected through explicit adapters.

## Core layers

| Layer | Responsibility | Ownership |
|---|---|---|
| Domain | Finding, scan, project, provider and review concepts | CODE-REVIEW-CENTER |
| Normalization | Convert engine output into the domain model | CODE-REVIEW-CENTER |
| Correlation | Exact deduplication and later cross-engine correlation | CODE-REVIEW-CENTER |
| Engine adapters | Start tools, validate exit status, collect output and metadata | CODE-REVIEW-CENTER |
| Analysis engines | SAST, secret detection, dependency and AI review | External tools or providers, replaceable |
| Orchestration | Scan lifecycle, concurrency, cancellation and evidence | CODE-REVIEW-CENTER |
| Presentation | Desktop interface, history and actionable reports | CODE-REVIEW-CENTER |

## Integration rules

1. Prefer a documented CLI, JSON, or SARIF boundary over copying a third-party implementation.
2. Keep each engine behind an adapter with explicit input, output, timeout, cancellation, and error contracts.
3. Treat tool output as untrusted input: validate structure, paths, coordinates, and size limits before storing or displaying it.
4. Preserve source identity, rule identifiers, tool versions, and original evidence so normalized findings remain traceable.
5. Keep exact duplicate removal separate from cross-tool correlation. Similar findings from different engines must not be merged without explainable evidence.
6. Do not add a source dependency or redistribute a binary until its license, notices, transitive dependencies, platform support, and security posture have been reviewed.
7. Record every adopted component and the exact integration mode. Researching a repository does not imply adopting or copying it.

## Current core contract

The initial Python package lives in src/review_core/.

- Finding is immutable and carries tool identity, rule, severity, message, location, help URI, and a stable fingerprint.
- FindingSeverity provides the shared severity vocabulary.
- parse_sarif accepts a decoded SARIF mapping or JSON text/bytes and supports SARIF 2.1.0.
- deduplicate_findings removes exact fingerprint repeats while preserving first-seen order. It deliberately does not perform cross-engine correlation or severity arbitration.

The core currently uses Python 3.11+ and the standard library only.

## Implementation sequence

1. Establish and test the domain model and SARIF normalization. **In progress / first slice implemented.**
2. Add adapters for concrete scanner output formats that are not adequately represented by SARIF.
3. Define scan/project persistence and engine execution contracts.
4. Add cross-engine correlation with explainable matching evidence.
5. Add provider configuration and AI review orchestration.
6. Build the desktop workflow and reporting experience.

Each step must have focused tests and a recorded compatibility/licensing review where third-party components are involved.
