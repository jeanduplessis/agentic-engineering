from __future__ import annotations

import re
from typing import Any


def _result(check_id: str, passed: bool, evidence: str, details: Any = None) -> dict[str, Any]:
    return {
        "id": check_id,
        "type": "custom_contract",
        "status": "passed" if passed else "failed",
        "passed": passed,
        "evidence": evidence,
        "details": details,
    }


def _contains_all(response: str, terms: list[str]) -> tuple[bool, list[str]]:
    lower = response.lower()
    missing = [term for term in terms if term.lower() not in lower]
    return not missing, missing


def grade(response: str, case=None, context=None):
    context = context or {}
    checks = []

    terms = ["Module", "Interface", "Seam", "Locality", "Leverage"]
    passed, missing = _contains_all(response, terms)
    checks.append(_result(
        "architecture-vocabulary",
        passed,
        "response uses required architecture vocabulary" if passed else "missing required architecture vocabulary",
        {"missing": missing},
    ))

    labels = ["Files", "Problem", "Solution", "Benefits"]
    passed, missing = _contains_all(response, labels)
    checks.append(_result(
        "candidate-shape",
        passed,
        "response includes the deepening candidate labels" if passed else "response is missing candidate labels",
        {"missing": missing},
    ))

    domain_terms = ["Order", "Inventory Reservation", "Payment Authorization"]
    passed, missing = _contains_all(response, domain_terms)
    checks.append(_result(
        "domain-language",
        passed,
        "response uses fixture CONTEXT.md vocabulary" if passed else "response misses fixture domain terms",
        {"missing": missing},
    ))

    question_pattern = re.compile(r"which of these would you like to explore\?", re.IGNORECASE)
    checks.append(_result(
        "asks-next-question",
        bool(question_pattern.search(response)),
        "response asks the required follow-up question" if question_pattern.search(response) else "response did not ask the required follow-up question",
    ))

    has_code_fence = "```" in response
    checks.append(_result(
        "no-interface-proposal-yet",
        not has_code_fence,
        "response avoided code/interface proposals" if not has_code_fence else "response included a code block before the user selected a candidate",
    ))

    workspace_diff = list(context.get("workspace_diff") or [])
    checks.append(_result(
        "read-only-workflow",
        not workspace_diff,
        "sandbox files were not changed" if not workspace_diff else "sandbox files changed despite read-only prompt",
        {"workspace_diff": workspace_diff},
    ))

    return checks
