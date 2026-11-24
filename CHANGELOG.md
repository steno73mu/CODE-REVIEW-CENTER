# Changelog

All notable changes to CODE-REVIEW-CENTER are documented here.

## Unreleased

### Added
- Immutable normalized finding model and SHA-256 fingerprints.
- SARIF 2.1.0, Semgrep JSON, and Gitleaks JSON adapters.
- Exact fingerprint deduplication and conservative explainable cross-engine correlation.
- Trusted scanner process execution with argv-only invocation, timeouts, bounded output, and cancellation.
- Concurrent multi-scanner orchestration with per-engine outcomes.
- SQLite project, scanner-profile, scan-history, correlation-evidence, and AI-review persistence.
- Local project registry and validated scanner/provider configuration.
- `crc` CLI for projects, scanner profiles, scans, providers, AI reviews, and history.
- `crc-desktop` Tkinter workspace for local project management, scanner profiles, background scans, findings, history, and AI review.
- JSON, SARIF 2.1.0, and Markdown report export, including correlation evidence and saved AI reviews.
- Offline environment doctor and built-in Semgrep scanner preset.
- GitHub Actions checks for package installation, CLI entry point, desktop module import, and unit tests across Linux and Windows on Python 3.11-3.13.

### Security
- Gitleaks secret values and matched source text are excluded from normalized findings.
- Provider API keys are referenced through environment variables and are never stored in SQLite.
- Remote AI review requires explicit opt-in; remote endpoints must use HTTPS.
- Scanner output and provider responses have bounded capture sizes.
- SQLite connections are explicitly closed after each transaction for Windows compatibility.
- Application data directory permissions are restricted to the current user on POSIX systems.
- Public pull-request CI uses GitHub-hosted runners, not the self-hosted Pop!_OS runner.
