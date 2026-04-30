from __future__ import annotations

from pathlib import Path
from typing import Any


REQUIRED_TERMS = ("Workspace", "User", "Seat", "Billing Account")
REQUIRED_HEADINGS = (
    "# Agent Lexicon",
    "## Canonical Terms",
    "## Agent Rules",
    "## Relationships",
    "## Ambiguities",
)
CANONICAL_TABLE_HEADER = "| Term | Agent meaning | Use this when | Avoid |"


def grade(*, response: str, case: Any | None = None, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    context = context or {}
    sandbox_path = Path(str(context.get("sandbox_path"))) if context.get("sandbox_path") else None
    lexicon_path = sandbox_path / "AGENT_LEXICON.md" if sandbox_path else None
    agents_path = sandbox_path / "AGENTS.md" if sandbox_path else None

    text = lexicon_path.read_text() if lexicon_path and lexicon_path.exists() else ""
    agents_text = agents_path.read_text() if agents_path and agents_path.exists() else ""
    normalized_table_text = _normalize_table_spacing(text)

    return [
        _check(
            "agent-lexicon.file-created",
            "custom_artifact",
            bool(text.strip()),
            "AGENT_LEXICON.md was created" if text.strip() else "AGENT_LEXICON.md was not created or was empty",
            {"path": "AGENT_LEXICON.md"},
        ),
        _check(
            "agent-lexicon.required-headings",
            "custom_markdown_structure",
            all(heading in text for heading in REQUIRED_HEADINGS),
            "Lexicon includes required headings" if all(heading in text for heading in REQUIRED_HEADINGS) else "Lexicon is missing one or more required headings",
            {"required": REQUIRED_HEADINGS, "missing": [heading for heading in REQUIRED_HEADINGS if heading not in text]},
        ),
        _check(
            "agent-lexicon.canonical-table-format",
            "custom_markdown_structure",
            CANONICAL_TABLE_HEADER in normalized_table_text and "|---|---|---|---|" in text.replace(" ", ""),
            "Lexicon includes the canonical term table" if CANONICAL_TABLE_HEADER in normalized_table_text and "|---|---|---|---|" in text.replace(" ", "") else "Lexicon is missing the canonical term table shape",
        ),
        _check(
            "agent-lexicon.domain-terms",
            "custom_lexicon_content",
            all(term in text for term in REQUIRED_TERMS),
            "Lexicon includes core domain terms" if all(term in text for term in REQUIRED_TERMS) else "Lexicon is missing one or more core domain terms",
            {"required": REQUIRED_TERMS, "missing": [term for term in REQUIRED_TERMS if term not in text]},
        ),
        _check(
            "agent-lexicon.account-ambiguity",
            "custom_lexicon_content",
            "account" in text.lower() and "ambigu" in text.lower() and "Workspace" in text and "Billing Account" in text,
            "Lexicon flags account ambiguity" if "account" in text.lower() and "ambigu" in text.lower() and "Workspace" in text and "Billing Account" in text else "Lexicon does not clearly flag account ambiguity",
        ),
        _check(
            "agent-lexicon.agent-facing-rules",
            "custom_lexicon_content",
            "Use **" in text and "Do not" in text,
            "Lexicon includes operational agent rules" if "Use **" in text and "Do not" in text else "Lexicon is missing operational agent rules",
        ),
        _check(
            "agent-lexicon.agents-pointer",
            "custom_artifact",
            "## Terminology" in agents_text and "AGENT_LEXICON.md" in agents_text,
            "AGENTS.md includes the terminology pointer" if "## Terminology" in agents_text and "AGENT_LEXICON.md" in agents_text else "AGENTS.md is missing the terminology pointer",
            {"path": "AGENTS.md"},
        ),
        _check(
            "agent-lexicon.agents-pointer-short",
            "custom_artifact",
            "| Term |" not in agents_text and "## Canonical Terms" not in agents_text,
            "AGENTS.md does not duplicate the full lexicon" if "| Term |" not in agents_text and "## Canonical Terms" not in agents_text else "AGENTS.md appears to duplicate the full lexicon",
            {"path": "AGENTS.md"},
        ),
        _check(
            "agent-lexicon.no-old-artifact-contract",
            "custom_lexicon_content",
            "Ubiquitous Language" not in text and "Example dialogue" not in text,
            "Lexicon uses the new agent-facing contract" if "Ubiquitous Language" not in text and "Example dialogue" not in text else "Lexicon still contains old ubiquitous-language/example-dialogue contract",
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
