"""Catalog of independent review agents shown by the desktop application.

The catalog describes the integration surface honestly: a product card and an
official setup link do not imply that CODE-REVIEW-CENTER can invoke or publish
results through that product.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReviewAgent:
    agent_id: str
    name: str
    category: str
    description: str
    integration: str
    official_url: str
    executable: str | None = None


REVIEW_AGENTS = (
    ReviewAgent(
        "pr-agent",
        "PR-Agent",
        "Self-hosted · GitHub / GitLab",
        "Open-source PR reviewer. Can use a configured model provider; publishing requires host credentials.",
        "CLI / self-hosted",
        "https://github.com/qodo-ai/pr-agent",
        "pr-agent",
    ),
    ReviewAgent(
        "coderabbit",
        "CodeRabbit",
        "Hosted · pull requests",
        "Independent hosted review service. Repository access and code processing are managed by CodeRabbit.",
        "External service",
        "https://app.coderabbit.ai/",
    ),
    ReviewAgent(
        "greptile",
        "Greptile",
        "Hosted · pull requests",
        "Repository-aware hosted reviewer. Connect and manage repository access in Greptile.",
        "External service",
        "https://www.greptile.com/docs/introduction",
    ),
    ReviewAgent(
        "qodo-review",
        "Qodo Code Review",
        "Hosted · pull requests",
        "Hosted code review product with its own account, repository connection, and review configuration.",
        "External service",
        "https://docs.qodo.ai/qodo-documentation/code-review/get-started/configuration-overview/configuration-file",
    ),
    ReviewAgent(
        "copilot-review",
        "GitHub Copilot Code Review",
        "GitHub native · pull requests",
        "GitHub pull request reviewer. Enable and request it through GitHub; this app does not control its review run.",
        "GitHub hand-off",
        "https://docs.github.com/en/copilot/concepts/agents/code-review",
    ),
    ReviewAgent(
        "codex-review",
        "Codex Code Review",
        "Codex · local or pull request",
        "Independent review through Codex. Availability and data handling follow the signed-in Codex environment.",
        "External hand-off",
        "https://help.openai.com/en/articles/20001552-review-pull-requests-with-codex",
        "codex",
    ),
    ReviewAgent(
        "opencode",
        "OpenCode",
        "Local CLI · configurable model",
        "Local coding agent with a non-interactive run command. A read-only review adapter is not enabled yet.",
        "CLI detected; run adapter pending",
        "https://opencode.ai/docs/cli/",
        "opencode",
    ),
    ReviewAgent(
        "reviewly",
        "Reviewly",
        "Independent review · bridge",
        "Used for NEXORA reviews through its OpenCode bridge. This product needs a supported connection before CRC can invoke it.",
        "Bridge / external hand-off",
        "https://github.com/volnei/reviewly",
    ),
)
