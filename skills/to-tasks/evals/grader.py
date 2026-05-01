from __future__ import annotations

import re
from typing import Any


def grade(response: str, case: Any = None, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    text = response or ""
    lower = text.lower()
    return [
        _result(
            "to_tasks.multiple_vertical_slices",
            _count_slices(text) >= 3,
            f"found {_count_slices(text)} slice titles/headings; expected at least 3 proposed slices",
            {"slice_count": _count_slices(text)},
        ),
        _result(
            "to_tasks.required_slice_fields",
            _has_required_fields(lower),
            "checked for Title, Type, Beads type, Priority, Blocked by, and Acceptance criteria fields",
            {"missing": _missing_required_fields(lower)},
        ),
        _result(
            "to_tasks.hitl_and_afk_classification",
            "hitl" in lower and "afk" in lower,
            "response should classify slices and surface any human-interaction checkpoint",
            {"has_hitl": "hitl" in lower, "has_afk": "afk" in lower},
        ),
        _result(
            "to_tasks.approval_quiz",
            _asks_approval_quiz(lower),
            "response should ask about granularity, dependencies, merge/split choices, and HITL/AFK labels before creating beads",
            None,
        ),
        _result(
            "to_tasks.no_premature_bd_creation",
            not _appears_to_create_beads(lower),
            "response should not claim that beads were created during the pre-approval quiz step",
            None,
        ),
    ]


def _count_slices(text: str) -> int:
    title_fields = len(re.findall(r"(?im)^\s*(?:[-*]\s*)?(?:\d+[.)]\s*)?\*{0,2}Title\*{0,2}\s*:", text))
    numbered_headings = len(re.findall(r"(?im)^\s*#{2,}\s*\d+[.)]?\s+\S", text))
    return max(title_fields, numbered_headings)


def _missing_required_fields(lower: str) -> list[str]:
    required = {
        "type": r"\*{0,2}\s*type\s*\*{0,2}\s*:",
        "beads type": r"\*{0,2}\s*beads type\s*\*{0,2}\s*:",
        "priority": r"\*{0,2}\s*priority\s*\*{0,2}\s*:",
        "blocked by": r"\*{0,2}\s*blocked by\s*\*{0,2}\s*:",
        "acceptance criteria": r"\*{0,2}\s*acceptance criteria\s*\*{0,2}\s*:",
    }
    missing = [name for name, pattern in required.items() if not re.search(pattern, lower, re.MULTILINE)]
    if not re.search(r"\*{0,2}\s*title\s*\*{0,2}\s*:", lower, re.MULTILINE) and _count_slices(lower) < 3:
        missing.insert(0, "title")
    return missing


def _has_required_fields(lower: str) -> bool:
    return not _missing_required_fields(lower)


def _asks_approval_quiz(lower: str) -> bool:
    granularity = "granularity" in lower and any(word in lower for word in ("coarse", "fine", "right"))
    dependencies = "dependenc" in lower
    merge_split = "merge" in lower and "split" in lower
    classification = "hitl" in lower and "afk" in lower
    approval = any(word in lower for word in ("approve", "approval", "before creating", "create the beads"))
    return granularity and dependencies and merge_split and classification and approval


def _appears_to_create_beads(lower: str) -> bool:
    creation_claims = (
        "created bead",
        "created the bead",
        "created these bead",
        "created tasks in bd",
        "i created",
    )
    if any(claim in lower for claim in creation_claims):
        return True
    return bool(re.search(r"\b[a-z][a-z0-9_-]+-\d+(?:\.\d+)?\b", lower))


def _result(check_id: str, passed: bool, evidence: str, details: Any) -> dict[str, Any]:
    return {
        "id": check_id,
        "type": "custom_contract",
        "status": "passed" if passed else "failed",
        "passed": passed,
        "evidence": evidence,
        "details": details,
    }
