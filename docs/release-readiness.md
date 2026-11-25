# Release readiness

The current branch is a functional MVP, not a production release. Complete this checklist before publishing a tagged release or inviting third-party reuse.

## Required decisions and validation

- [ ] Select a repository license with the project owner. No license is currently granted by this repository.
- [x] Record current upstream scanner license files and confirm that scanner source/binaries are not vendored; see [third-party integration notes](third-party-integrations.md).
- [x] Inspect the exact upstream license files at Semgrep v1.187.0 (LGPL-2.1) and Gitleaks v8.30.1 (MIT); no scanner binaries or third-party Python runtime dependencies are bundled.
- [ ] Complete a notice audit for scanner distributions if a release package ever redistributes them, and audit any future runtime dependencies.
- [x] Record the tested Semgrep and Gitleaks versions, installation instructions, and upstream license terms. Scanner binaries are external tools and are not bundled; see [third-party integration notes](third-party-integrations.md).
- [x] Validate the synthetic Semgrep `--config auto` path on Ubuntu and Windows; the representative-repository check remains open.
- [x] Validate Semgrep `--config auto` against a synthetic Python fixture on GitHub-hosted Ubuntu and Windows; [workflow run 45503977330](https://github.com/steno73mu/CODE-REVIEW-CENTER/actions/runs/45503977330). The check enables Semgrep run metrics because auto-config creation requires them.
- [ ] Validate the built-in Semgrep preset against a representative real local repository and confirm exit-code behavior.
- [x] Validate the Gitleaks adapter and a supported cross-platform invocation on Linux and Windows; CI confirms redacted output on both platforms.
- [x] Prevent scanner executable shadowing: relative PATH entries and executable paths inside the scanned project are rejected.
- [x] Smoke-test Tk workspace initialization on GitHub-hosted Linux (Xvfb) and Windows runners.
- [ ] Run the Tkinter desktop application interactively on real Pop!_OS and Windows desktops, including scan cancellation, triage, AI review, and report export.
- [ ] Verify the Trivy and OSV-Scanner SARIF presets on supported Linux and Windows versions, including clean repositories, findings, and scanner errors.
- [ ] Test local providers (Ollama and/or LM Studio) and at least one remote OpenAI-compatible provider with explicit consent and a non-production test key.
- [ ] Review data retention, local database backup/restore, permissions, and user-facing disclosure for AI review metadata.
- [x] Build wheel and source distributions, install each artifact, and run package/CLI checks in the Linux/Windows Python 3.11-3.13 CI matrix.
- [ ] Verify release CI, changelog, security policy, and contribution guidance.
- [x] Confirm public repository workflows use GitHub-hosted Ubuntu/Windows runners only; the self-hosted Pop!_OS runner is not referenced.

## Known product boundaries

- Scanner processes are not sandboxed. Only trusted installed executables may be configured; executable lookup excludes relative PATH entries and rejects executables inside the scanned project.
- Timeout and cancellation terminate the scanner process tree (POSIX process groups; Windows `taskkill /T`). The launcher remains a process-lifecycle control, not an OS sandbox.
- Cross-engine correlation is conservative and needs a larger labeled fixture corpus before being used as a definitive duplicate classifier.
- Reviewer chat transmits finding metadata and user-entered chat messages to the selected provider after explicit opt-in. The app does not attach source files, but code or sensitive text pasted into chat is transmitted. Conversations are stored locally per scan/provider. Literal and DNS-resolved non-public addresses are rejected, but DNS rebinding is not fully prevented; network egress controls remain the stronger boundary.
- The desktop UI is an initial operational workspace and has not yet undergone manual cross-platform usability testing.

Do not remove these limitations from the documentation until the corresponding evidence exists.
