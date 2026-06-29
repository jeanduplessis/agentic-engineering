from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any, Iterable


def grade_response(
    response: str,
    checks: Iterable[dict[str, Any]],
    *,
    custom_grader: str | None = None,
    case: Any | None = None,
    context: dict[str, Any] | None = None,
    subjective_checks: Iterable[dict[str, Any]] | None = None,
    judge_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    results = [_run_check(response, dict(check)) for check in checks]
    if custom_grader:
        results.extend(_run_custom_grader(custom_grader, response, case, context or {}))

    totals = {
        "passed": sum(1 for check in results if check["status"] == "passed"),
        "failed": sum(1 for check in results if check["status"] == "failed"),
        "skipped": sum(1 for check in results if check["status"] == "skipped"),
    }
    passed = totals["failed"] == 0 if results else None
    status = "graded" if results else "not_graded"
    return {
        "status": status,
        "passed": passed,
        "summary": _summary(totals, status),
        "checks": results,
        "totals": totals,
        "judge": _judge_placeholder(subjective_checks or (), judge_config),
    }


def _judge_placeholder(
    subjective_checks: Iterable[dict[str, Any]],
    judge_config: dict[str, Any] | None,
) -> dict[str, Any]:
    checks = [dict(check) for check in subjective_checks]
    if not checks:
        return {
            "status": "skipped",
            "reason": "no_subjective_checks",
            "metadata": None,
            "subjective_checks": [],
            "results": [],
        }
    if not judge_config:
        return {
            "status": "not_run",
            "reason": "no_judge_configured",
            "metadata": None,
            "subjective_checks": checks,
            "results": [],
        }
    return {
        "status": "not_run",
        "reason": "judge_execution_not_implemented",
        "metadata": dict(judge_config),
        "subjective_checks": checks,
        "results": [],
    }


def checks_from_legacy_expectations(expected_output: str | None, expectations: Iterable[str]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if expected_output:
        checks.append({"id": "expected_output", "type": "required_content", "value": expected_output})
    for index, expectation in enumerate(expectations, start=1):
        checks.append({
            "id": f"legacy_expectation_{index}",
            "type": "required_content",
            "value": expectation,
        })
    return checks


def _run_check(response: str, check: dict[str, Any]) -> dict[str, Any]:
    check_type = check.get("type")
    check_id = check.get("id", check_type or "check")
    try:
        if check_type == "required_content":
            value = str(check["value"])
            passed = value in response
            return _result(check_id, check_type, passed, f"required content {'found' if passed else 'missing'}", value)
        if check_type == "forbidden_content":
            value = str(check["value"])
            passed = value not in response
            return _result(check_id, check_type, passed, f"forbidden content {'absent' if passed else 'present'}", value)
        if check_type == "regex":
            pattern = str(check["pattern"])
            match = re.search(pattern, response, re.MULTILINE | re.DOTALL)
            return _result(check_id, check_type, bool(match), "regex matched" if match else "regex did not match", pattern)
        if check_type == "json_field_equals":
            data = json.loads(response)
            actual = _read_path(data, str(check["path"]))
            expected = check.get("value")
            return _result(
                check_id,
                check_type,
                actual == expected,
                f"field {check['path']} was {actual!r}",
                {"expected": expected, "actual": actual},
            )
        if check_type == "non_empty_response":
            passed = bool(response.strip())
            return _result(check_id, check_type, passed, "response is non-empty" if passed else "response is empty", None)
        return {
            "id": check_id,
            "type": check_type or "unknown",
            "status": "skipped",
            "passed": None,
            "evidence": f"Unsupported deterministic check type: {check_type}",
        }
    except Exception as exc:  # keep grade files machine-readable on malformed outputs
        return {
            "id": check_id,
            "type": check_type or "unknown",
            "status": "failed",
            "passed": False,
            "evidence": f"Check raised {exc.__class__.__name__}: {exc}",
        }


def _result(check_id: str, check_type: str, passed: bool, evidence: str, details: Any) -> dict[str, Any]:
    return {
        "id": check_id,
        "type": check_type,
        "status": "passed" if passed else "failed",
        "passed": passed,
        "evidence": evidence,
        "details": details,
    }


def _read_path(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current[part]
        elif isinstance(current, list):
            current = current[int(part)]
        else:
            raise KeyError(path)
    return current


def _run_custom_grader(
    custom_grader: str,
    response: str,
    case: Any | None,
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    module_path = Path(custom_grader)
    spec = importlib.util.spec_from_file_location("skill_eval_custom_grader", module_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load custom grader: {custom_grader}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    grade = getattr(module, "grade")
    return list(grade(response=response, case=case, context=context))


def _summary(totals: dict[str, int], status: str) -> str:
    if status == "not_graded":
        return "No deterministic checks configured for this run."
    return f"{totals['passed']} passed, {totals['failed']} failed, {totals['skipped']} skipped"
