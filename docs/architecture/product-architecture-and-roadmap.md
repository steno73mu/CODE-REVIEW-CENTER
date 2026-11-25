# Product Architecture and Roadmap

**Status:** Working proposal  
**Audience:** Project contributors and future users  
**Last updated:** 2026-11-25

## 1. Product direction

CODE-REVIEW-CENTER is a downloadable code review application for individual developers and teams. It should help users review code from a local folder or from repositories hosted on services they choose. It must not depend on the original project owner's machine, account, installed paths, or preferred provider.

The application owns the review workflow and a common findings model. Source hosts, scanners, AI providers, and report destinations connect through replaceable adapters.

The first supported desktop targets are Pop!_OS/Linux and Windows. The application should remain useful without an AI service or a hosted account: users can select a local checkout and run available analysis tools locally.

## 2. Sources and review modes

A source connector turns a selected project or change request into a consistent `RepositorySnapshot`:

- **Local folder:** scan a chosen directory, or review a selected local Git branch/commit and its diff.
- **GitHub:** clone or fetch a repository and review a branch, commit, or pull request.
- **GitLab:** review a project, branch, commit, or merge request.
- **Bitbucket:** review a repository, branch, commit, or pull request.
- **Other Git hosts:** support generic HTTPS/SSH Git remotes, including self-hosted Git services. Host-specific review-request features require a provider adapter.

A snapshot records the provider, repository identity, selected revision, optional base revision and change-request identity, local checkout location, and changed-file list. The scanner adapters receive a local read-only checkout path and optional diff context; they do not need to know which host supplied it.

Fetching remote code is an explicit user action. Credentials are kept in the operating system credential store where available, with least-privilege scopes. A remote repository is cloned into an application-managed temporary workspace and can be deleted after the scan. Source connectors must not run repository hooks, scripts, builds, or other project commands.

## 3. Application architecture

| Component | Responsibility |
|---|---|
| User interface | Select a local or hosted source, choose a review mode, configure each tool, inspect findings and scan history, and export or publish results. |
| Source connectors | Fetch or describe local and hosted repositories and create a common repository snapshot. |
| Review orchestrator | Coordinate a scan, enforce timeouts and cancellation, isolate per-tool failures, and report progress. |
| Engine adapters | Detect tool availability, validate configuration, invoke a tool without a shell, capture bounded output, and parse its results. |
| Finding domain model | Store normalized findings while retaining the original engine, rule, evidence, and source location. |
| Correlation | Deduplicate exact matches first; add explainable cross-engine correlation only after its quality is measured. |
| Storage | Keep user settings, scan history, and findings locally. Use separate locations for configuration, cache, and temporary checkouts. |
| Report adapters | Export results and, when explicitly requested, publish review annotations or check summaries to a host. |
| Optional AI adapters | Offer local or remote AI review as a separate, opt-in capability. |

Keep these boundaries stable so a provider or scanner can be added without rewriting the whole application. Version public adapter contracts before third parties are encouraged to build plugins.

## 4. Analysis tools and result presentation

The initial agreed toolchain contains five tools, with distinct responsibilities:

| Tool | Role in the product |
|---|---|
| Semgrep CE | Static analysis and rule-based code findings |
| Gitleaks | Secret detection |
| Trivy | Vulnerability and misconfiguration analysis |
| OSV-Scanner | Dependency vulnerability analysis |
| Reviewdog | Review-result presentation and integration with supported reporting formats; it is not a scanner |

Each tool has its own adapter and user-facing settings panel: availability/version, supported scan modes, profile or ruleset, exclusions, limits, status, and links to the tool's own documentation. The interface should show what each tool did and why it could not run. A tool being installed on one developer's computer does not mean it is bundled with, or available in, the downloadable product.

The shared findings view groups results without hiding their origin. Each finding should retain at least its engine and rule ID, severity, message, file and location, stable fingerprint where possible, confidence/evidence, and relevant source revision. The user can filter by tool, severity, file, and status, then open the source context. Preserve raw tool output only when needed for troubleshooting, bound its size, and redact secrets before display or storage.

## 5. Optional AI review

AI review is separate from deterministic scanners and is never required to use the application. Local providers, such as an OpenAI-compatible local endpoint, and remote providers can be added through separate adapters.

Before any code or diff is sent to a remote provider, the application must identify the destination and ask the user to opt in for that provider and review. The default is no code upload. Show what will be sent, support excluding files, and provide clear provider status and data-handling information. Do not require users to install a model.

AI suggestions remain labeled as AI-generated evidence and must not silently become confirmed scanner findings or be published as review comments.

## 6. User experience and distribution

The current desktop interface is a prototype, not the final design. The product should offer one coherent application with:

1. a clear start screen for local folders and hosted repositories;
2. a review setup screen with source, revision, tools, and profile;
3. separate, understandable settings for each integrated tool;
4. scan progress and per-tool status;
5. a unified findings view with tool provenance and source context;
6. local history, export, and explicit host publishing controls.

The interface should be usable by people who have not read the source code, support keyboard navigation and accessible contrast, and explain missing tools in plain language. Keep product screens independent of any specific developer's paths or shell configuration.

Distribution must be planned for fresh user accounts on Linux and Windows. An installer or documented setup flow should detect prerequisites, explain optional tool installation, avoid replacing existing binaries, and verify downloads before installation. Decide separately which tools can be bundled after the license and redistribution audit. Provide upgrade and uninstall guidance, release checksums, and a software bill of materials (SBOM). The project's own license is still undecided and must be selected before public distribution.

## 7. Security and privacy defaults

- Treat repository contents, filenames, diffs, tool output, and AI output as untrusted input.
- Never execute code from the reviewed repository as part of fetching or scanning.
- Invoke tools with argument arrays, not shell-composed commands; constrain paths, output size, run time, and concurrency.
- Keep tokens in the system credential store when available; request only the permissions needed for the chosen operation.
- Scan locally by default. Do not upload source code to an AI provider or publish findings to a hosting service without a clear user action.
- Make remote comments/checks an explicit later action, scoped to the selected review. Never commit changes or merge a pull request.
- Keep temporary checkouts separate from the user's working tree and make cleanup behavior visible.
- Document telemetry, retention, and network activity; ship with telemetry off unless a future, explicit product decision says otherwise.

## 8. Delivery roadmap

### Stage 0 — Product contract

- Confirm the first-release source providers and review modes.
- Keep the five-tool roster above and classify scanners, result presentation, and optional AI correctly.
- Choose the UI technology, configuration format, credential-store approach, and install/update strategy.
- Decide the project's license and audit the licenses of dependencies and any bundled tools.

**Exit condition:** written decisions, supported-platform matrix, and release boundaries agreed.

### Stage 1 — Stable local workflow

- Define the source snapshot and adapter contracts.
- Make local-folder and local-Git reviews predictable and isolated.
- Make each scanner's detection, configuration, failure, timeout, and result status visible.
- Complete finding normalization and establish a representative correlation corpus.

**Exit condition:** local review works on a clean supported Linux installation without relying on the original developer's machine.

### Stage 2 — Hosted-source adapters

- Add GitHub repository and pull-request workflows.
- Add GitLab and Bitbucket adapters, followed by generic and self-hosted Git support.
- Add provider capability reporting so users can distinguish fetch/review support from comment/check publishing.
- Test authentication, pagination, diffs, deleted/renamed files, and inaccessible repositories.

**Exit condition:** the same review pipeline works across local and hosted snapshots, with provider-specific behavior isolated in adapters.

### Stage 3 — Toolchain and result quality

- Finish and verify adapters for Semgrep CE, Gitleaks, Trivy, and OSV-Scanner.
- Implement Reviewdog only for supported reporting/presentation paths.
- Expand fixtures and tests for parsing, stable fingerprints, deduplication, path mapping, and failure isolation.
- Preserve each engine's identity and version in every result.

**Exit condition:** repeatable reports with transparent per-tool status and measured correlation behavior.

### Stage 4 — Product interface

- Replace the prototype presentation with the agreed user-facing experience.
- Add dedicated per-tool configuration and diagnostic views.
- Add local history, export, accessible navigation, and clear privacy controls.
- Verify the app in real Pop!_OS and Windows desktop sessions.

**Exit condition:** a new user can configure and complete a review without using the command line for routine work.

### Stage 5 — Optional publishing and AI

- Add opt-in review comments/checks for providers where scopes and APIs are verified.
- Add optional local and remote AI adapters with the upload consent flow.
- Ensure publishing and AI failures do not corrupt local findings or the source repository.

**Exit condition:** users can clearly review every outbound action before it happens.

### Stage 6 — Downloadable release readiness

- Complete Linux and Windows packaging, install/upgrade/uninstall checks, and clean-machine verification.
- Complete the project and dependency license audit, notices, SBOM, checksums, and release signing.
- Document supported platforms, required versus optional tools, network behavior, data storage, and limitations.
- Run CI for supported platforms and keep the release separate from the development branch until all gates pass.

**Exit condition:** a user outside the development team can download, verify, install, and use the product with no undocumented machine-specific setup.

## 9. Decisions still open

1. Which hosted providers ship first after GitHub: GitLab, Bitbucket, or both?
2. Which UI framework best supports a polished Linux and Windows desktop application?
3. Is Reviewdog retained as a runtime dependency, or should its supported output formats be implemented by native report adapters?
4. Which tools are bundled, installed by the user, or detected as existing system tools?
5. What project license and contribution policy will apply?
6. Which local and remote AI providers, if any, are supported in the first release?

Until these decisions and the roadmap gates are complete, the product should be described as under development, not ready for public distribution.
