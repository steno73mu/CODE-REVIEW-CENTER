# CODE-REVIEW-CENTER — Product Architecture and Delivery Path

**Document type:** Product design and roadmap  
**Status:** Proposed hybrid architecture; awaiting owner approval  
**Audience:** Contributors and future users  
**Updated:** 2026-11-25

## 1. Product intent

CODE-REVIEW-CENTER is a downloadable application for individual developers and teams. A user can review a folder or Git repository on their computer, or a change hosted on GitHub and other Git platforms. The application gathers independent analysis results in one workspace, explains where each result came from, and lets the user decide whether to publish comments back to the hosting platform.

It is a review workspace, not a single AI model and not a repackaging of third-party scanners. Its core should work without a hosted AI subscription. Users choose which local tools, AI reviewers, and source connections to enable.

**Primary user outcome:** choose source → choose review tools → run review → inspect a clear report in the app → optionally publish selected results online.

Initial desktop targets are Pop!_OS/Linux and Windows. Installation must work for users other than the original developer and must not depend on personal paths, accounts, or machine configuration.

## 2. Requirements established so far

- Sources include local folders/local Git and remote repositories or change requests.
- GitHub is first for hosted review. GitLab, Bitbucket, and other/self-hosted Git platforms are intended through separate connectors; support must be implemented and verified rather than implied.
- The report is always available in the application. On the completed report, an unchecked-by-default **Publish comments/checks** checkbox controls whether the review's eligible findings are sent to the hosting platform. Checking it enables publication; the user must still choose the explicit Publish action. Read-only access is used until publication; write access is requested only then.
- The initial analysis-toolchain under consideration is Semgrep CE, Gitleaks, Trivy, OSV-Scanner, and Reviewdog. Reviewdog presents/forwards results; it is not a scanner.
- AI reviewers are a separate category. **NVIDIA NIM API support is required for the owner's workflow and is a first-class provider integration.** The downloadable product must let other users configure their own provider/key; never bundle or hard-code the owner's key. Local and other remote providers may be added as alternatives. No code is sent to an AI service by default.
- The user wants a dedicated integration and user-facing panel for each enabled tool/service.
- The product is intended for external download and use. Public release requires a project-license decision and a full redistribution/dependency audit.
- Do not let any reviewer edit the repository, commit, or merge changes. Code review and comment publication are distinct from code modification.

## 3. Approaches considered

| Approach | Strengths | Trade-offs |
|---|---|---|
| Local-only engine | Strong privacy and predictable operation; useful for folders and offline work. | Cannot offer native hosted PR/MR workflows or publish comments without additional connectors. |
| External-agent dashboard | Fast access to hosted reviewer services and their platform comments. | Depends on account plans, network, external code handling, and provider APIs; poor baseline for a downloadable product that should also work locally. |
| **Hybrid (selected)** | Local scanners and local reviews form the baseline; platform connectors and hosted AI reviewers are optional. One results view supports local reports and opt-in publication. | More adapter work; each provider's real capabilities must be discovered and shown instead of pretending every integration is equivalent. |

The selected direction is the hybrid. It keeps the core usable without an external AI service while supporting remote repositories and optional provider integrations.

## 4. Current repository baseline

The development branch currently contains a Python 3.11+ application with:

- A shared core, CLI, and an initial Tkinter desktop interface.
- Local project registration and GitHub clone/update.
- Semgrep and Gitleaks adapters, SARIF parsing, normalized findings, exact deduplication, conservative correlation, SQLite history, triage, and JSON/SARIF/Markdown reports.
- Optional OpenAI-compatible AI review of finding metadata, with remote opt-in; current documentation says source code and code excerpts are not sent.
- Automated package/CLI CI on Linux and Windows. Synthetic Semgrep and Gitleaks adapter checks are recorded in CI.

The current desktop interface is an MVP, not a release-ready visual design. Built-in Trivy and OSV-Scanner presets now feed their SARIF output through the shared parser, but still need independent supported-platform verification and dedicated status/configuration screens. The codebase does not yet establish GitLab/Bitbucket/self-hosted PR/MR review, host comment publishing, Reviewdog integration, or dedicated screens for AI reviewers. The user reports that Semgrep 1.186.0 now works on their Pop!_OS machine after replacing a broken pipx symlink with a wrapper that uses an existing Python 3.14 installation; version/help and a `--config auto` scan were reported successful. This is a machine-specific user-reported verification, separate from CI's Semgrep 1.187.0 fixture test and from a clean install for future users. Real interactive desktop verification on Pop!_OS and Windows, broader correlation fixtures, and the project's license remain open. A Python package is not yet a polished consumer installer.

Treat these statements as a snapshot; update them when implementation changes.

## 5. Architecture

### 5.1 Source connectors

Each connector resolves user intent into a common `ReviewTarget`:

- source provider and repository identity;
- local folder or managed checkout location;
- selected branch, commit, or PR/MR;
- base/head revisions and changed-file diff, when available;
- authentication capability and whether the connection is read-only or can publish comments.

Initial connectors: local folder/local Git, then GitHub. Later connectors: GitLab, Bitbucket, and generic/self-hosted Git. A generic Git URL supports fetching code, but platform-specific PR/MR metadata and comments require a matching host adapter.

Remote repositories are fetched into an application-managed workspace. Do not run repository scripts, hooks, builds, or setup commands during fetch or review. Leave a user's local checkout unchanged.

### 5.2 Review orchestrator and tool adapters

A central orchestrator runs only the tools selected for a review, reports progress, handles cancellation and timeouts, and records each tool's independent outcome. Invoke local binaries through argument arrays, validate bounded output, and preserve tool version and exit status.

Use separate adapters and capability profiles for:
- **Static/security/dependency analysis:** Semgrep CE, Gitleaks, Trivy, OSV-Scanner.
- **Result presentation:** Reviewdog or a compatible reporting adapter.
- **AI review agents:** local/self-hosted or hosted, each optional and isolated from the deterministic scanner contract.

Each tool gets a dedicated panel in the UI showing availability, connection/configuration, supported review modes, version or service status, cost/network implications where relevant, and findings/results. A capability matrix must distinguish `local review`, `remote PR/MR review`, `read repository`, `publish comments/checks`, and `requires external model/service`.

Do not assume every named service exposes a public API, CLI, or redistribution right. Add an adapter only through a documented and supportable interface. Where a vendor service can only run in its own web interface, present it as an external hand-off rather than falsely claiming native execution.

### 5.3 Seven requested AI-review integrations

The requested seven targets are PR-Agent, CodeRabbit, Greptile, Qodo Code Review, GitHub Copilot Code Review, Codex Code Review, and OpenCode. These are not all the same kind of product: some are local tools, others are hosted services or native platform reviewers. Each gets its own product panel and an explicit capability label. The integration level must be verified before claiming support:

1. **Native adapter:** a supported CLI, API, or platform integration can be operated by CODE-REVIEW-CENTER.
2. **Import/connection:** CODE-REVIEW-CENTER can read a supported result format or platform comments/checks.
3. **External hand-off:** the panel explains the required account/setup and opens the official tool or review page, without pretending to control it.

Prefer native adapters where officially supported. Do not copy another product's UI or claim automation when only a hand-off is available. Evaluate code/data flow, permission scopes, API/CLI stability, pricing, and redistribution terms for every target.

| Requested integration | Intended role | First verification |
|---|---|---|
| PR-Agent | Open-source/self-hostable AI reviewer; prior discussion paired it with NVIDIA NIM for GitHub. | Verify community maintenance, local diff support, host permissions, NVIDIA model configuration, and data flow. |
| CodeRabbit | Hosted reviewer with multiple Git-platform integrations. | Supported APIs/results, external code processing, account plan and cost. |
| Greptile | Hosted reviewer emphasizing repository context. | Supported platforms, results/API surface, and hosted data handling. |
| Qodo Code Review | Hosted multi-platform reviewer, separate from community PR-Agent. | Product plan, current platform support, and supported integration contract. |
| GitHub Copilot Code Review | Native reviewer for GitHub pull requests. | Platform/plan requirements and available request/result APIs. |
| Codex Code Review | Local review and hosted pull-request review candidate. | Supported local invocation and currently available remote platforms/APIs. |
| OpenCode | Local coding-agent CLI configured for review tasks; model endpoint may be local or remote. | Stable command/interface for read-only review, prompt controls, permissions, and output format. |

LM Studio is a local model server, not a separate reviewer; it can be an optional model endpoint for a compatible agent. The remembered name “OpenReview” is not confirmed; the user has now identified OpenCode as the seventh requested integration.

### 5.4 Findings, correlation, and report

Every normalized finding retains the originating tool/agent and rule, severity, message, path/line, source revision, fingerprint where possible, and supporting evidence. Do not collapse different engines into one unexplained result. Begin with exact deduplication; cross-engine correlation remains conservative and auditable.

Show results in the app regardless of publication choice. On the completed report, **Publish comments/checks** is unchecked by default. If the user checks it and chooses Publish, send the eligible findings for that review using the selected provider's supported review/check format. If unchecked, do not send comments and use read-only host permissions. Never commit, edit source, approve automatically, or merge.

### 5.5 AI, NVIDIA API, and privacy

NVIDIA NIM is the required first remote model-provider integration for the owner's workflow. NVIDIA documents an OpenAI-compatible Chat Completions endpoint at `https://integrate.api.nvidia.com/v1/chat/completions`; model IDs remain configurable and must be checked against NVIDIA's current catalog. A first-class NVIDIA NIM setup preset now pre-fills the official endpoint, a configurable catalog model, and the NVIDIA_API_KEY environment-variable name. It reuses the OpenAI-compatible client; an end-to-end NVIDIA API test must still confirm authentication, request shape, response parsing, limits, and errors.

For the downloadable product, users enter their own NVIDIA API key and select a model. No key is embedded in the application or stored in project files, scan history, or logs. Use the operating system credential store where available. The provider panel shows which model/provider is selected and whether the endpoint is local or remote.

Local scanners and local reviewers run on the user's computer where supported. Before a review sends source code or diffs to NVIDIA or another hosted AI provider, show the destination and data scope and require a separate explicit **Send code to AI provider** opt-in. It is off by default. Review findings in the application independently of this setting. Keep AI output visibly labeled as model-generated and separate from verified scanner results.

Store local history and settings in per-user application data. Do not record API keys in logs or history.

### 5.6 User interface and distribution

Replace the Tkinter prototype with a polished desktop interface after selecting a framework. The user has selected the [Dribbble reference: AI Agent Dashboard — Driftwork](https://dribbble.com/shots/27905826-AI-Agent-Dashboard-Driftwork) as the design to follow closely. Use its overall dashboard composition, dark visual treatment, card layout, navigation, and information hierarchy as the visual template, adapting labels and content to code review instead of reproducing unrelated product behavior. Add restrained red accents to the dark graphite/near-black base for primary actions, active navigation, focus, and important states. Keep severity cues distinguishable and accessible; do not make every status red. Treat exact red shades and typography as implementation details to sample from the reference when producing the mockup.

The experience should feel like a current developer review workspace, not a legacy utility window. Give each integrated scanner and review agent a dedicated panel with its own settings and status, while keeping navigation and results consistent. Each configured AI reviewer has a separate conversation for the selected saved scan; local chat history is keyed by review session and provider. Scanner panels show setup and availability instead of presenting command-line tools as chat agents. Keep the interaction consistent across Linux and Windows:

1. Choose a local folder, repository URL, or hosted PR/MR.
2. Choose tools and their profiles using dedicated panels.
3. Inspect progress and per-tool status.
4. Review one unified, filterable findings report with provenance and source context.
5. Decide whether to publish comments/checks using the explicit checkbox.
6. View local scan history and export supported report formats.

Package for clean Linux and Windows user accounts. Detect tools and show missing prerequisites without silently replacing binaries. Decide which components are bundled only after license/notice review. Provide verified downloads, upgrade/uninstall guidance, checksums, SBOM, and release signing. Do not publish a public release until the project license and release gates are complete.

## 6. Delivery path and completion gates

### Phase 0 — Freeze the product contract
- Confirm and freeze the seven reviewer integrations listed in section 5.3; mark each as scanner, reporter, local reviewer, hosted service, native adapter, import/connection, or external hand-off.
- Define first-release platforms, source modes, comment behavior, and AI data consent.
- Choose the UI framework, installer approach, credential storage, and project license.
- Produce a provider/tool capability and permission matrix.

**Gate:** the intended integrations and user-visible behaviors are named and classified; unknown items stay visibly unresolved.

### Phase 1 — Stabilize the existing local MVP
- Audit current CLI, UI, storage, scanner and AI behavior against the README.
- Finish normalization and increase labeled test fixtures for duplicates/correlation.
- Verify Semgrep and Gitleaks on supported Linux/Windows versions; define how missing or broken executables are diagnosed.
- Redesign only after a UI framework is chosen; preserve working core behavior.

**Gate:** clean-install local review works and results can be inspected/exported without any hosted account.

### Phase 2 — Complete local analysis tools
- Verify the new Trivy and OSV-Scanner SARIF presets on supported platforms and implement dedicated status/configuration panels.
- Decide the exact role for Reviewdog; implement it as reporting/presentation, never as a scanner.
- Provide individual settings/status panels and per-tool error handling.

**Gate:** each selected tool has a verified input, output, version, failure state, and documented user setup.

### Phase 3 — Remote source review
- Add GitHub PR/commit source review through the shared ReviewTarget.
- Add GitLab and Bitbucket, then generic/self-hosted host support based on user priority.
- Handle private repositories, diffs, renames/deletions, pagination, revisions, and read-only permissions.

**Gate:** local and remote snapshots produce the same finding contract, while host-specific details remain in connectors.

### Phase 4 — Optional review agents
- Implement the plugin/capability contract and verify NVIDIA NIM API as the required first remote model provider, including an end-to-end review with a user-supplied key and configurable model ID.
- Evaluate PR-Agent and OpenCode as local/self-hostable reviewers that can use NVIDIA NIM where supported.
- Evaluate CodeRabbit, Greptile, Qodo, Copilot, and Codex for supported APIs/CLIs and lawful integration.
- Add a dedicated panel for each of the seven requested integrations, labeling unavailable native automation as import/connection or external hand-off.
- Add local Ollama/LM Studio and remote provider tests only where the selected review agent uses them; do not require a model.

**Gate:** every enabled reviewer has verified data flow, permissions, cost/status disclosure, and a useful error path.

### Phase 5 — Comment publication
- Add read-only source review first.
- Add the Publish comments/checks checkbox to the completed report, off by default.
- Require the user to choose Publish before sending findings. Request write permission only for publication, map findings to supported host features, and prevent duplicates on repeated runs.
- Never publish an approval, commit, source change, or merge automatically.

**Gate:** tests prove unchecked means no writes and checked publishes only the selected review output to the selected target.

### Phase 6 — Product UI and user testing
- Implement the chosen polished desktop UX with dedicated panels for each integrated tool.
- Test keyboard/accessibility, cancellation, large results, missing dependencies, privacy explanations, and history.
- Perform interactive testing on real Pop!_OS and Windows systems.

**Gate:** an external user can add a local project or hosted source and complete a review without undocumented terminal setup.

### Phase 7 — Downloadable public release
- Complete license and third-party notice audits, decide bundling, and generate SBOM/checksums/signatures.
- Build and verify Linux/Windows installers on clean environments.
- Complete security/privacy review, release documentation, CI gates, upgrade/uninstall validation, and final changelog.
- Keep release separate from the development branch until every release gate passes.

**Gate:** a user outside the development team can verify, install, and use the product with no machine-specific setup or hidden network behavior.

## 7. Decisions still open

1. What desktop UI and installer technologies should be used?
2. What is the project's license?
3. Which hosted platforms should follow GitHub first, if the planned GitLab-then-Bitbucket order should change?
4. Which of the seven AI-review targets expose a stable interface CODE-REVIEW-CENTER can operate or consume, and which are external hand-offs?
5. Which NVIDIA model ID is preferred after a real review-quality and cost check?
6. Which result types can each host publish as review comments/checks?

Until these choices and gates are resolved, call the software an early-development MVP, not a public-ready product.

## 8. Reference material

- [Current architecture overview](overview.md)
- [Third-party integration and license notes](../third-party-integrations.md)
- [Release readiness checklist](../release-readiness.md)
- [PR-Agent local setup](https://github.com/The-PR-Agent/pr-agent/blob/main/docs/docs/installation/locally.md)
- [CodeRabbit platform and FAQ](https://www.coderabbit.ai/faq)
- [Greptile documentation](https://www.greptile.com/docs/introduction)
- [GitHub Copilot Code Review](https://docs.github.com/en/copilot/concepts/agents/code-review)
- [Codex pull-request review guidance](https://help.openai.com/en/articles/20001552-review-pull-requests-with-codex)
- [Qodo Code Review configuration](https://docs.qodo.ai/qodo-documentation/code-review/get-started/configuration-overview/configuration-file)
- [NVIDIA NIM LLM API reference](https://docs.api.nvidia.com/nim/reference/llm-apis)
