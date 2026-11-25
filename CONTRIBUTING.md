# Contributing

Thanks for helping improve CODE-REVIEW-CENTER.

## Development setup

- Python 3.11 or newer.
- Install the package in editable mode: `python -m pip install -e .`.
- Run the complete test suite: `python -m unittest discover -s tests -v`.
- Verify the CLI: `crc --help`.
- Verify source compilation: `python -m compileall -q src tests`.

## Contribution rules

1. Keep the product's domain model, orchestration, and user experience original.
2. Integrate external scanners through documented CLI, JSON, or SARIF interfaces; do not copy whole third-party applications.
3. Write tests before behavior changes and keep each change focused.
4. Never execute untrusted repository scripts, hooks, or build commands as part of a scan.
5. Scanner profiles must use argument arrays, never shell command strings.
6. Never put API keys in scanner arguments, provider configuration, source files, or commits. Use environment variables.
7. Preserve finding provenance and explain any cross-engine correlation.
8. Update README, architecture documentation, and CHANGELOG when user-visible behavior changes.

## Pull requests

- Explain the user-visible behavior and security implications.
- Include test evidence and supported platform details.
- Identify any new dependency and document its license, notices, transitive dependencies, and security posture.
- Do not weaken CI checks to make a change pass.
