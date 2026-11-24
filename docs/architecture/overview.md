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
| Orchestration | Concurrent scanner batches, per-engine status, timeout, cancellation, bounded output and aggregate evidence | CODE-REVIEW-CENTER |
| Configuration | Validated scanner profiles and local project registry | CODE-REVIEW-CENTER |
| Persistence | Transactional SQLite scan history, projects and scanner profiles | CODE-REVIEW-CENTER |
| Application | Shared project-scan service used by CLI and desktop | CODE-REVIEW-CENTER |
| Presentation | Local CLI and Tkinter desktop workspace | CODE-REVIEW-CENTER |
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
- parse_semgrep accepts Semgrep JSON output and maps rule, message, severity, version, and source coordinates.
- parse_gitleaks accepts Gitleaks JSON output but deliberately discards Secret and Match fields to avoid persisting credential material.
- deduplicate_findings removes exact fingerprint repeats while preserving first-seen order.
- correlate_findings groups only cross-tool findings at the same normalized file path and line with a configurable high message-similarity threshold. Every group retains pairwise fingerprints, method, and score; original severities and finding records are not merged.

The core currently uses Python 3.11+ and the standard library only.

`run_engine` launches a trusted executable from an argument sequence (never through a shell), applies a positive timeout, captures UTF-8 stdout/stderr up to a configurable byte limit per stream, and records exit status, duration, and truncation flags. It can terminate a running process on timeout or cancellation. Non-zero exit codes remain available to the caller because scanners may use them to signal findings. Startup failures and timeouts have distinct exception types. The runner is not a sandbox: only trusted, locally installed analysis binaries may be invoked, and untrusted repository scripts, hooks, or build commands must never be executed by this layer.

## Implementation sequence

1. Establish and test the domain model and SARIF normalization. **Implemented first slice.**
2. Add native JSON adapters for scanner formats not adequately represented by SARIF. **Semgrep and Gitleaks implemented.**
3. Define scan/project persistence and engine execution contracts. **Implemented: SQLite history, project registry, scanner profiles.**
4. Add cross-engine correlation with explainable matching evidence. **Conservative first implementation complete; thresholds and precision require broader fixture validation.**
5. Add provider configuration and AI review orchestration. **Pending.**
6. Build the desktop workflow and reporting experience. **First local desktop slice implemented; advanced triage/reporting pending.**

Each step must have focused tests and a recorded compatibility/licensing review where third-party components are involved.

## Current limitations

- The desktop UI is an initial operational workspace, not a polished release UI. Tkinter must be available on the host (on some Linux distributions install the matching `python3-tk` package).
- Scanner profiles invoke only explicitly configured local executables. The launcher is not a security sandbox; do not configure untrusted commands or run arbitrary repository hooks/build scripts.
- Process output is bounded to 1 MiB per stream by default. History stores normalized findings and process metadata, not raw stdout/stderr.
- Cancellation terminates the scanner process directly; it does not promise to terminate arbitrary descendant processes spawned by a scanner.
- Cross-engine semantic correlation, AI provider integration, code-context navigation, report export, and Windows/Linux end-to-end desktop testing remain pending.
- The repository has no license file yet; do not assume code reuse or redistribution rights until the owner selects and adds a license.
