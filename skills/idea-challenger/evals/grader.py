from __future__ import annotations

import re
from typing import Any


def grade(response: str = "", case: Any = None, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    text = response or ""
    lower = text.lower()
    case_id = str(getattr(case, "id", ""))

    if case_id == "final-decision-record":
        return _grade_final_decision(text, lower)
    return _grade_quick_triage(text, lower)


def _grade_quick_triage(text: str, lower: str) -> list[dict[str, Any]]:
    question_count = text.count("?")
    return [
        _result(
            "idea_challenger.skeptical_triage",
            _has_any(lower, ("current read", "current verdict", "likely verdict", "do not build yet", "conditional pursue", "revise", "defer", "reject")),
            "response should start with a skeptical current read or triage verdict",
            None,
        ),
        _result(
            "idea_challenger.weakest_assumption",
            "weakest assumption" in lower or "biggest concern" in lower or "make-or-break" in lower,
            "response should identify the weakest assumption or biggest concern",
            None,
        ),
        _result(
            "idea_challenger.one_question",
            1 <= question_count <= 2,
            f"response should ask one focused Socratic question; found {question_count} question marks",
            {"question_count": question_count},
        ),
        _result(
            "idea_challenger.decision_changing_standard",
            "what would change" in lower or "change the decision" in lower or "would move" in lower,
            "response should explain what answer or evidence would change the decision",
            None,
        ),
        _result(
            "idea_challenger.no_premature_planning",
            not _contains_planning_drift(lower),
            "response should not start implementation planning, task creation, or feature brainstorming",
            None,
        ),
    ]


def _grade_final_decision(text: str, lower: str) -> list[dict[str, Any]]:
    required_sections = (
        "decision",
        "desirability verdict",
        "fit verdict",
        "strongest evidence",
        "weakest assumptions",
        "validation vs build",
        "kill criteria",
        "next step",
    )
    missing = [section for section in required_sections if section not in lower]
    verdict_present = bool(re.search(r"\b(pursue|conditional pursue|revise|defer|reject)\b", lower))
    build_boundary = "do not build yet" in lower or "not recommended yet" in lower or "do not build" in lower
    evidence_boundary = "two support tickets" in lower and _has_any(lower, ("insufficient", "weak", "unsupported", "missing"))

    return [
        _result(
            "idea_challenger.decision_record_sections",
            not missing,
            "final output should include the decision-record sections",
            {"missing": missing},
        ),
        _result(
            "idea_challenger.explicit_verdict",
            verdict_present,
            "decision record should include an explicit pursue/conditional pursue/revise/defer/reject verdict",
            None,
        ),
        _result(
            "idea_challenger.validation_build_boundary",
            "validation work" in lower and "building work" in lower and build_boundary,
            "decision record should separate validation work from building work and avoid premature building",
            None,
        ),
        _result(
            "idea_challenger.evidence_skepticism",
            evidence_boundary,
            "decision record should treat weak evidence as insufficient, not as proof to build",
            None,
        ),
        _result(
            "idea_challenger.no_task_creation",
            not _contains_planning_drift(lower),
            "decision record should stop at decision and not create implementation tasks or PRDs",
            None,
        ),
    ]


def _contains_planning_drift(lower: str) -> bool:
    forbidden_phrases = (
        "implementation plan",
        "prd",
        "product requirements document",
        "task breakdown",
        "created tasks",
        "create tasks",
        "let's build",
        "we should build",
        "start by implementing",
        "sprint plan",
        "roadmap",
    )
    return any(phrase in lower for phrase in forbidden_phrases)


def _has_any(lower: str, needles: tuple[str, ...]) -> bool:
    return any(needle in lower for needle in needles)


def _result(check_id: str, passed: bool, evidence: str, details: Any) -> dict[str, Any]:
    return {
        "id": check_id,
        "type": "custom_contract",
        "status": "passed" if passed else "failed",
        "passed": passed,
        "evidence": evidence,
        "details": details,
    }
