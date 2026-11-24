# Release readiness

The current branch is a functional MVP, not a production release. Complete this checklist before publishing a tagged release or inviting third-party reuse.

## Required decisions and validation

- [ ] Select a repository license with the project owner. No license is currently granted by this repository.
- [ ] Audit all copied/adapted code, dependencies, GitHub Actions, scanner integrations, and documentation for license compatibility and required notices.
- [ ] Record the tested Semgrep and Gitleaks versions, installation instructions, and license terms. Scanner binaries are external tools and are not bundled.
- [ ] Validate the built-in Semgrep preset against a real local repository and confirm exit-code behavior.
- [ ] Validate the Gitleaks adapter and a supported cross-platform invocation on Linux and Windows.
- [ ] Run the Tkinter desktop application interactively on real Pop!_OS and Windows desktops, including scan cancellation, triage, AI review, and report export.
- [ ] Test local providers (Ollama and/or LM Studio) and at least one remote OpenAI-compatible provider with explicit consent and a non-production test key.
- [ ] Review data retention, local database backup/restore, permissions, and user-facing disclosure for AI review metadata.
- [ ] Build and install wheel/sdist artifacts in clean Linux and Windows environments.
- [ ] Verify release CI, changelog, security policy, and contribution guidance.
- [ ] Confirm public repository workflows never route untrusted fork pull requests to a self-hosted runner.

## Known product boundaries

- Scanner processes are not sandboxed. Only trusted installed executables may be configured.
- Cancellation terminates the scanner process directly, not arbitrary descendants.
- Cross-engine correlation is conservative and needs a larger labeled fixture corpus before being used as a definitive duplicate classifier.
- AI review transmits finding metadata, including scanner messages, to the selected provider. Source files and code excerpts are not uploaded by the current implementation.
- The desktop UI is an initial operational workspace and has not yet undergone manual cross-platform usability testing.

Do not remove these limitations from the documentation until the corresponding evidence exists.
