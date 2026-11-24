# Security Policy

## Supported scope

Security reports are welcome for the current development branch and the latest published source state.

## Reporting a vulnerability

Please do not open a public issue for an exploitable vulnerability. Use GitHub's private vulnerability reporting feature for this repository when available. Include:

- affected commit or branch;
- reproducible steps and impact;
- relevant logs or proof of concept, with secrets removed.

Do not include live credentials, private source code, or personal data in a report.

## Security boundaries

- The scanner process launcher is not a sandbox. Only trusted, locally installed scanner executables may be configured.
- Timeouts and cancellation terminate scanner child processes (POSIX process groups; Windows `taskkill /T`), but do not provide filesystem, network, or privilege isolation.
- The application does not intentionally run repository scripts, hooks, or build commands.
- Scanner stdout/stderr capture is bounded; raw scanner output is not persisted by default.
- Gitleaks secret values and matched source text are not copied into normalized findings.
- Provider API keys are loaded from environment variables and are not stored in the local database.
- Remote AI review requires explicit user opt-in and HTTPS. Literal and DNS-resolved non-public destination addresses are rejected before a request. This check is not a network sandbox and does not eliminate DNS-rebinding races; use network egress controls for high-risk environments. Only normalized finding metadata is sent; source files are not uploaded by this feature.
- Self-hosted runners must not execute untrusted pull-request code from forks.
