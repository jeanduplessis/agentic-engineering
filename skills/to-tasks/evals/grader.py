from __future__ import annotations

import re
from typing import Any


def grade(response: str, case: Any = None, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    text = response or ""
    lower = text.lower()
    slice_count = _count_slices(text)
    return [
        _result(
            "to_tasks.multiple_vertical_slices",
            slice_count >= 3,
            f"found {slice_count} slice/task sections; expected at least 3 proposed vertical slices",
            {"slice_count": slice_count},
        ),
        _result(
            "to_tasks.required_task_body_fields",
            _has_required_fields(lower),
            "checked for task body fields: Source, What to build, Acceptance criteria, Classification, Slice type, Beads type, Priority, Blocked by, and Notes for future agents",
            {"missing": _missing_required_fields(lower)},
        ),
        _result(
            "to_tasks.hitl_and_afk_classification",
            "hitl" in lower and "afk" in lower,
            "response should classify slices and surface any human-interaction checkpoint",
            {"has_hitl": "hitl" in lower, "has_afk": "afk" in lower},
        ),
        _result(
            "to_tasks.br_creation_workflow",
            _mentions_br_creation_workflow(lower),
            "response should keep the work in br and describe task creation plus dependency/blocker handling",
            None,
        ),
        _result(
            "to_tasks.no_silent_init",
            _respects_no_silent_init(text, lower),
            "response should not initialize beads silently when no beads database is available, and should ask how to proceed",
            None,
        ),
        _result(
            "to_tasks.no_false_creation_without_db",
            not _appears_to_create_beads(lower),
            "response should not claim that beads were created when the prompt says no beads database exists",
            None,
        ),
    ]


def _count_slices(text: str) -> int:
    title_fields = len(re.findall(r"(?im)^\s*(?:[-*]\s*)?(?:\d+[.)]\s*)?\*{0,2}Title\*{0,2}\s*:", text))
    slice_type_fields = len(re.findall(r"(?im)^\s*(?:[-*]\s*)?\*{0,2}Slice type\*{0,2}\s*:", text))
    what_to_build_fields = len(re.findall(r"(?im)^\s*#{1,6}\s*What to build\b", text))
    numbered_headings = len(re.findall(r"(?im)^\s*#{2,}\s*(?:\d+[.)]?\s+)?(?:Slice|Task)\b", text))
    numbered_items = len(re.findall(r"(?im)^\s*\d+[.)]\s+\*{0,2}(?:Slice|Task)\b", text))
    return max(title_fields, slice_type_fields, what_to_build_fields, numbered_headings, numbered_items)


def _missing_required_fields(lower: str) -> list[str]:
    required = {
        "source": r"(?:^|\n)\s*#{1,6}\s*source\b|\*{0,2}\s*source\s*\*{0,2}\s*:",
        "what to build": r"(?:^|\n)\s*#{1,6}\s*what to build\b|\*{0,2}\s*what to build\s*\*{0,2}\s*:",
        "acceptance criteria": r"(?:^|\n)\s*#{1,6}\s*acceptance criteria\b|\*{0,2}\s*acceptance criteria\s*\*{0,2}\s*:",
        "classification": r"(?:^|\n)\s*#{1,6}\s*classification\b|\*{0,2}\s*classification\s*\*{0,2}\s*:",
        "slice type": r"\*{0,2}\s*slice type\s*\*{0,2}\s*:",
        "beads type": r"\*{0,2}\s*beads type\s*\*{0,2}\s*:",
        "priority": r"\*{0,2}\s*priority\s*\*{0,2}\s*:",
        "blocked by": r"(?:^|\n)\s*#{1,6}\s*blocked by\b|\*{0,2}\s*blocked by\s*\*{0,2}\s*:",
        "notes for future agents": r"(?:^|\n)\s*#{1,6}\s*notes for future agents\b|\*{0,2}\s*notes for future agents\s*\*{0,2}\s*:",
    }
    return [name for name, pattern in required.items() if not re.search(pattern, lower, re.MULTILINE)]


def _has_required_fields(lower: str) -> bool:
    return not _missing_required_fields(lower)


def _mentions_br_creation_workflow(lower: str) -> bool:
    mentions_br = "br create" in lower or ("br" in lower and "bead" in lower and "task" in lower and "create" in lower)
    mentions_dependencies = "br dep add" in lower or "blocked by" in lower or "dependenc" in lower
    avoids_other_trackers = "github issue" not in lower and "jira" not in lower
    return mentions_br and mentions_dependencies and avoids_other_trackers


def _respects_no_silent_init(text: str, lower: str) -> bool:
    runs_init = bool(re.search(r"(?im)^\s*(?:`{3,}\s*)?br init\b", text))
    mentions_unavailable_db = any(
        phrase in lower
        for phrase in (
            "no initialized beads database",
            "no beads database",
            "beads database",
            "database is available",
            "database exists",
            "br info",
        )
    )
    asks_how_to_proceed = "?" in text and any(word in lower for word in ("proceed", "setup", "set up", "initialize", "database", "beads"))
    return not runs_init and mentions_unavailable_db and asks_how_to_proceed


def _appears_to_create_beads(lower: str) -> bool:
    creation_claims = (
        "created bead",
        "created the bead",
        "created these bead",
        "created tasks in br",
        "i created",
        "i've created",
        "i have created",
        "beads created",
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
