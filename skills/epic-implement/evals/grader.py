from __future__ import annotations

from typing import Any


def grade(response: str, case: Any = None, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    text = response or ""
    lower = text.lower()
    return [
        _result(
            "epic_implement.parent_only_closure",
            _has_any(lower, "parent closes", "parent-owned closure", "parent only", "only the parent")
            and _has_any(lower, "must not close", "do not close", "child gates must not", "children must not")
            and "after" in lower
            and _has_any(lower, "validation", "review"),
            "requires parent-only task closure after validation/review gates",
            None,
        ),
        _result(
            "epic_implement.script_preflight",
            "bash -n" in lower and _has_any(lower, "mapfile", "readarray", "compatibility", "bash version", "shell supports"),
            "requires generated-script syntax and shell compatibility preflight",
            None,
        ),
        _result(
            "epic_implement.append_only_resume",
            _has_any(lower, "append-only", "append only")
            and _has_any(lower, "resume", "restart")
            and _has_any(lower, "do not truncate", "never truncate", "must not truncate"),
            "requires append-only resume state",
            None,
        ),
        _result(
            "epic_implement.invariant_mutation_validation",
            _has_any(lower, "invalidating", "invalidate", "mutation", "later mutation", "parent-update", "parent update")
            and _has_any(lower, "direct", "create/update", "creation")
            and _has_any(lower, "validation", "validator", "task-validate"),
            "requires validation of direct paths and later invalidating mutations",
            None,
        ),
        _result(
            "epic_implement.stop_on_unsafe_state",
            _has_any(lower, "stop", "do not continue", "do not continue blindly")
            and _has_any(lower, "dirty", "unsafe", "failed gate", "blocker")
            and _has_any(lower, "output path", "gate output", "child output"),
            "requires stopping and reporting unsafe failed-gate state",
            None,
        ),
        _result(
            "epic_implement.no_bare_br_sync",
            "br sync --flush-only" in lower or "bare `br sync`" in lower or "bare br sync" in lower,
            "requires br sync safety rule",
            None,
        ),
    ]


def _has_any(lower: str, *needles: str) -> bool:
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
