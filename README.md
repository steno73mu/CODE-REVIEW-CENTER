# CODE-REVIEW-CENTER

An original desktop code-review product that brings local analysis engines and configurable AI reviewers into one workflow. It aims to turn heterogeneous diagnostics into consistent, traceable, actionable review results.

## Project principles

- **Our product, our architecture.** External projects are research references or optional tools, not the foundation or identity of this application.
- **Integrate before reimplementing.** Prefer invoking mature scanners through stable process boundaries and documented output formats.
- **Own the intelligence layer.** Finding normalization, correlation, deduplication, orchestration, provider management, review history, and user experience belong to this project.
- **Replaceable components.** No external scanner, model provider, or review engine should become an irreplaceable architectural dependency.
- **License-aware development.** Before redistributing source or binaries, record licenses, notices, dependency obligations, provenance, and compatibility.

## Current implementation

The first original core package is under active development:

- Finding: tool-independent finding model with stable SHA-256 fingerprint.
- parse_sarif: SARIF 2.1.0 normalization into the project model.
- deduplicate_findings: deterministic exact-fingerprint deduplication.
- Python 3.11+, standard-library runtime; no runtime dependencies.

## Development

Run the unit tests from the repository root:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

The same compile and unit-test checks run in GitHub Actions on feature branches and pull requests.

## Architecture

See [the architecture overview](docs/architecture/overview.md) for module boundaries, integration rules, and the current implementation sequence.
