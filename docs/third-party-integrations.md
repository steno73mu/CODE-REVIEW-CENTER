# Third-party integration and license notes

## Integration boundary

CODE-REVIEW-CENTER does not vendor scanner source code or redistribute scanner binaries. It invokes separately installed executables through argument arrays and consumes their documented JSON/SARIF output. The project has no Python runtime dependencies.

This distinction is intentional: the scanner projects remain independently installed products. Their own binary distributions and transitive dependencies are not included in CODE-REVIEW-CENTER's wheel or source distribution.

## Scanner projects reviewed

| Scanner | Upstream license file | Integration used here | Distribution status |
|---|---|---|---|
| Semgrep | [LGPL-2.1](https://github.com/semgrep/semgrep/blob/develop/LICENSE) | External CLI; Semgrep JSON output | Not bundled or vendored |
| Gitleaks | [MIT](https://github.com/gitleaks/gitleaks/blob/master/LICENSE) | External CLI; redacted JSON output | Not bundled or vendored |

The license labels above describe the upstream repository license files inspected on 2026-11-25. They are not a substitute for checking the exact version and all notices of any binary a user installs. The Gitleaks upstream README currently describes the project as feature-complete with future releases focused on security patches; re-evaluate maintenance and compatibility before depending on new functionality.

## CI integration versions

The cross-platform scanner integration workflow currently pins and validates:

- **Semgrep 1.187.0** — local YAML rule against a generated Python fixture.
- **Gitleaks 8.30.1** — official release archives with SHA-256 checksum verification; a synthetic GitHub token is detected and its value is confirmed absent from stdout and normalized findings.

Both integration checks passed on GitHub-hosted Ubuntu and Windows runners. These are smoke tests of the CLI adapters and redaction boundary, not a substitute for validating Semgrep's built-in `--config auto` preset against a representative repository.

## Obligations and release gates

- No scanner source files, libraries, or executable binaries are copied into this repository.
- The adapters and process launcher are original CODE-REVIEW-CENTER code; they communicate with scanners through CLI arguments and output formats.
- If a future release bundles, redistributes, links against, or copies code from either scanner, perform a new version-specific license and notice review before shipping.
- If new Python runtime dependencies are introduced, record each direct and transitive dependency, its license, and applicable notices in the release audit.
- The repository's own license has not been selected. Until the owner chooses and adds one, public visibility does not grant permission to reuse this repository's code.

## Verification still required

- Record the exact Semgrep and Gitleaks versions tested on Linux and Windows.
- Run the built-in presets against real local repositories and verify report redaction and exit-code handling.
- Re-check upstream licenses and maintenance status at each release candidate.
