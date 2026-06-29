from __future__ import annotations

import json
from typing import Any

SENTINEL_PREFIX = "SKILL_VALID_RESULT="
EXPECTED_TARGET = "skills/example-good"


def _result(check_id: str, passed: bool, evidence: str, details: Any = None) -> dict[str, Any]:
    return {
        "id": check_id,
        "type": "custom_contract",
        "status": "passed" if passed else "failed",
        "passed": passed,
        "evidence": evidence,
        "details": details,
    }


def grade(response: str, case=None, context=None) -> list[dict[str, Any]]:
    lines = [line.strip() for line in response.splitlines() if line.strip()]
    if not lines:
        return [_result("sentinel.present", False, "response was empty")]

    final_line = lines[-1]
    results: list[dict[str, Any]] = []
    has_final_sentinel = final_line.startswith(SENTINEL_PREFIX)
    earlier_sentinel = any(line.startswith(SENTINEL_PREFIX) for line in lines[:-1])
    results.append(_result(
        "sentinel.final_line",
        has_final_sentinel and not earlier_sentinel,
        "sentinel is the final non-empty line" if has_final_sentinel and not earlier_sentinel else "missing final sentinel or sentinel appeared before final line",
    ))
    if not has_final_sentinel:
        return results

    try:
        payload = json.loads(final_line[len(SENTINEL_PREFIX):])
    except json.JSONDecodeError as exc:
        results.append(_result("sentinel.valid_json", False, f"sentinel JSON did not parse: {exc}"))
        return results

    results.append(_result("sentinel.valid_json", isinstance(payload, dict), "sentinel JSON is an object", payload))
    if not isinstance(payload, dict):
        return results

    checks = payload.get("checks")
    checks_valid = isinstance(checks, list) and bool(checks) and all(
        isinstance(check, dict)
        and {"id", "status", "message"}.issubset(check)
        and check.get("status") == "passed"
        for check in checks
    )
    results.extend([
        _result("sentinel.target", payload.get("target") == EXPECTED_TARGET, f"target was {payload.get('target')!r}"),
        _result("sentinel.status", payload.get("status") == "passed", f"status was {payload.get('status')!r}"),
        _result("sentinel.checks", checks_valid, "checks are non-empty and all passed", checks),
    ])
    return results
