from __future__ import annotations

from typing import Any


def grade(response: str, case: Any = None, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    text = response or ""
    lower = text.lower()
    return [
        _result(
            "epic_orchestrate.parent_only_closure",
            _has_any(lower, "parent closes", "parent-owned closure", "parent only", "only the parent")
            and _has_any(lower, "must not close", "do not close", "gate executors must not")
            and "after" in lower
            and _has_any(lower, "validation", "review"),
            "requires parent-only issue closure after validation/review gates",
            None,
        ),
        _result(
            "epic_orchestrate.script_preflight",
            "bash -n" in lower and _has_any(lower, "mapfile", "readarray", "compatibility", "bash version", "shell supports"),
            "requires generated-script syntax and shell compatibility preflight",
            None,
        ),
        _result(
            "epic_orchestrate.append_only_resume",
            _has_any(lower, "append-only", "append only")
            and _has_any(lower, "resume", "restart")
            and _has_any(lower, "do not truncate", "never truncate", "must not truncate"),
            "requires append-only resume state",
            None,
        ),
        _result(
            "epic_orchestrate.invariant_mutation_validation",
            _has_any(lower, "invalidating", "invalidate", "mutation", "later mutation", "parent-update", "parent update")
            and _has_any(lower, "direct", "create/update", "creation")
            and _has_any(lower, "validation", "validator", "task-validate"),
            "requires validation of direct paths and later invalidating mutations",
            None,
        ),
        _result(
            "epic_orchestrate.stop_on_unsafe_state",
            _has_any(lower, "stop", "do not continue", "do not continue blindly")
            and _has_any(lower, "dirty", "unsafe", "failed gate", "blocker")
            and _has_any(lower, "output path", "gate output", "child output"),
            "requires stopping and reporting unsafe failed-gate state",
            None,
        ),
        _result(
            "epic_orchestrate.ait_cli_safety",
            _has_any(lower, "ait", "ait cli")
            and _has_any(lower, "--actor", "actor")
            and _has_any(lower, "ok=false", "ok: false", "error.code", "error code")
            and _has_any(lower, "do not edit .ait", "never edit .ait", "cli-only", "only mutation surface"),
            "requires ait CLI-only mutation, actor use, and ok=false error handling",
            None,
        ),
        _result(
            "epic_orchestrate.no_force_close_without_approval",
            _has_any(lower, "force-close", "force close", "--force")
            and _has_any(lower, "explicit", "approval", "approve", "without user"),
            "requires no force-close without explicit approval",
            None,
        ),
        _result(
            "epic_orchestrate.harness_neutral_gate_execution",
            _has_any(lower, "native subagent", "subagent")
            and _has_any(lower, "current harness", "harness runner", "non-interactive runner")
            and _has_any(lower, "current session", "sequential fallback", "sequentially")
            and _has_any(lower, "pi is optional", "pi optional", "pi self-invocation is optional", "pi executable or native subagent is available")
            and _has_any(lower, "same gate", "same prompt", "same contract", "preserve gate"),
            "requires optional runners and complete sequential current-session fallback",
            None,
        ),
        _result(
            "epic_orchestrate.canonical_template_precedence",
            _has_any(lower, "commands/tdd-task.md", "commands/<name>.md", "commands/")
            and _has_any(lower, "first", "before", "precedence", "prefer", "canonical")
            and ".pi/prompts" in lower
            and _has_any(lower, "optional", "fallback", "after"),
            "requires canonical commands template before optional Pi locations",
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
