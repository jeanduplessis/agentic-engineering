from __future__ import annotations

from pathlib import Path
from typing import Any


REQUIRED_TERMS = ("Workspace", "User", "Seat", "Billing Account")
REQUIRED_HEADINGS = (
    "# Context",
    "## Scope",
    "## Contexts",
    "## Canonical Terms",
    "## Relationships",
    "## Agent Rules",
    "## Ambiguities",
    "## Context Boundaries",
)
CANONICAL_TABLE_HEADER = "| Term | Agent meaning | Use this when | Avoid |"
CONTEXT_TABLE_HEADER = "| Context | Owns | Location | Notes |"


def grade(*, response: str, case: Any | None = None, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    context = context or {}
    sandbox_path = Path(str(context.get("sandbox_path"))) if context.get("sandbox_path") else None
    context_path = sandbox_path / "CONTEXT.md" if sandbox_path else None
    legacy_path = sandbox_path / "AGENT_LEXICON.md" if sandbox_path else None
    agents_path = sandbox_path / "AGENTS.md" if sandbox_path else None

    text = context_path.read_text() if context_path and context_path.exists() else ""
    legacy_text = legacy_path.read_text() if legacy_path and legacy_path.exists() else ""
    agents_text = agents_path.read_text() if agents_path and agents_path.exists() else ""
    normalized_table_text = _normalize_table_spacing(text)

    return [
        _check(
            "context.file-created",
            "custom_artifact",
            bool(text.strip()),
            "CONTEXT.md was created" if text.strip() else "CONTEXT.md was not created or was empty",
            {"path": "CONTEXT.md"},
        ),
        _check(
            "context.required-headings",
            "custom_markdown_structure",
            all(heading in text for heading in REQUIRED_HEADINGS),
            "Context includes required headings" if all(heading in text for heading in REQUIRED_HEADINGS) else "Context is missing one or more required headings",
            {"required": REQUIRED_HEADINGS, "missing": [heading for heading in REQUIRED_HEADINGS if heading not in text]},
        ),
        _check(
            "context.context-table-format",
            "custom_markdown_structure",
            CONTEXT_TABLE_HEADER in normalized_table_text,
            "Context includes the context ownership table" if CONTEXT_TABLE_HEADER in normalized_table_text else "Context is missing the context ownership table shape",
        ),
        _check(
            "context.canonical-table-format",
            "custom_markdown_structure",
            CANONICAL_TABLE_HEADER in normalized_table_text and "|---|---|---|---|" in text.replace(" ", ""),
            "Context includes the canonical term table" if CANONICAL_TABLE_HEADER in normalized_table_text and "|---|---|---|---|" in text.replace(" ", "") else "Context is missing the canonical term table shape",
        ),
        _check(
            "context.domain-terms",
            "custom_context_content",
            all(term in text for term in REQUIRED_TERMS),
            "Context includes core domain terms" if all(term in text for term in REQUIRED_TERMS) else "Context is missing one or more core domain terms",
            {"required": REQUIRED_TERMS, "missing": [term for term in REQUIRED_TERMS if term not in text]},
        ),
        _check(
            "context.account-ambiguity",
            "custom_context_content",
            "account" in text.lower() and "ambigu" in text.lower() and "Workspace" in text and "Billing Account" in text,
            "Context flags account ambiguity" if "account" in text.lower() and "ambigu" in text.lower() and "Workspace" in text and "Billing Account" in text else "Context does not clearly flag account ambiguity",
        ),
        _check(
            "context.agent-facing-rules",
            "custom_context_content",
            "Use **" in text and "Do not" in text,
            "Context includes operational agent rules" if "Use **" in text and "Do not" in text else "Context is missing operational agent rules",
        ),
        _check(
            "context.agents-pointer",
            "custom_artifact",
            "## Domain Context" in agents_text and "CONTEXT.md" in agents_text,
            "AGENTS.md includes the domain-context pointer" if "## Domain Context" in agents_text and "CONTEXT.md" in agents_text else "AGENTS.md is missing the domain-context pointer",
            {"path": "AGENTS.md"},
        ),
        _check(
            "context.agents-pointer-short",
            "custom_artifact",
            "| Term |" not in agents_text and "## Canonical Terms" not in agents_text and "## Context Boundaries" not in agents_text,
            "AGENTS.md does not duplicate the full context contract" if "| Term |" not in agents_text and "## Canonical Terms" not in agents_text and "## Context Boundaries" not in agents_text else "AGENTS.md appears to duplicate the full context contract",
            {"path": "AGENTS.md"},
        ),
        _check(
            "context.no-legacy-artifact-created",
            "custom_artifact",
            not legacy_text.strip(),
            "AGENT_LEXICON.md was not created" if not legacy_text.strip() else "AGENT_LEXICON.md should not be created under the new contract",
            {"path": "AGENT_LEXICON.md"},
        ),
        _check(
            "context.no-old-artifact-contract",
            "custom_context_content",
            "# Agent Lexicon" not in text and "Ubiquitous Language" not in text and "Example dialogue" not in text,
            "Context uses the new agent-facing contract" if "# Agent Lexicon" not in text and "Ubiquitous Language" not in text and "Example dialogue" not in text else "Context still contains old lexicon/ubiquitous-language/example-dialogue contract",
        ),
    ]


def _normalize_table_spacing(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            lines.append("| " + " | ".join(cells) + " |")
        else:
            lines.append(line)
    return "\n".join(lines)


def _check(check_id: str, check_type: str, passed: bool, evidence: str, details: Any = None) -> dict[str, Any]:
    return {
        "id": check_id,
        "type": check_type,
        "status": "passed" if passed else "failed",
        "passed": passed,
        "evidence": evidence,
        "details": details,
    }
