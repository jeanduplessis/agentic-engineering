#!/usr/bin/env python3
"""Normalize, validate, and persist code-quality reviewer responses."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any

MAX_ATTEMPTS = 2

STATUS_VALUES = {
    "findings": "FINDINGS",
    "pass": "PASS",
    "not applicable": "NOT_APPLICABLE",
    "not_applicable": "NOT_APPLICABLE",
    "not-applicable": "NOT_APPLICABLE",
    "n/a": "NOT_APPLICABLE",
    "blocked": "BLOCKED",
}
ANALYZER_STATUS_VALUES = {
    "pass": "PASS",
    "fail": "FAIL",
    "not applicable": "NOT_APPLICABLE",
    "not_applicable": "NOT_APPLICABLE",
    "not-applicable": "NOT_APPLICABLE",
    "n/a": "NOT_APPLICABLE",
}


def _load_validator() -> ModuleType:
    validator_path = (
        Path(__file__).resolve().parents[2] / "code-quality" / "scripts" / "validate_contract.py"
    )
    spec = importlib.util.spec_from_file_location("code_quality_validate_contract", validator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load contract validator: {validator_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_validator()
FOCI = frozenset(VALIDATOR.FOCI)


def _atomic_create(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.link(temporary, path)
    except FileExistsError as exc:
        raise RuntimeError(f"destination already exists: {path}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _preserve_raw(path: Path, content: bytes) -> None:
    if path.exists():
        if path.read_bytes() != content:
            raise RuntimeError(f"attempt artifact already exists with different content: {path}")
        return
    _atomic_create(path, content)


def _replace_json(path: Path, value: dict[str, Any]) -> None:
    content = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _read_state(path: Path, review_id: str, focus: str) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "review_id": review_id, "focus": focus, "attempts": 0}
    try:
        state = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read gate state {path}: {exc}") from exc
    if not isinstance(state, dict):
        raise RuntimeError("gate state must be an object")
    if state.get("review_id") != review_id or state.get("focus") != focus:
        raise RuntimeError("gate state identity does not match packet and focus")
    attempts = state.get("attempts")
    if not isinstance(attempts, int) or attempts < 0 or attempts >= MAX_ATTEMPTS:
        raise RuntimeError("gate state has no remaining reviewer attempts")
    return state


def _bounded_error(error: Exception) -> str:
    message = " ".join(str(error).split())
    return (message or error.__class__.__name__)[:500]


def _decode_response(raw: bytes) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise VALIDATOR.ContractError(f"response is not UTF-8: {exc}") from exc

    stripped = text.strip()
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        # Task runners and models sometimes wrap an otherwise valid object in a
        # fence or a short sentence. Accept exactly one decodable root object;
        # semantic validation below still rejects incomplete or unsafe content.
        start = stripped.find("{")
        if start < 0:
            raise VALIDATOR.ContractError("response does not contain a JSON object")
        try:
            value, end = json.JSONDecoder().raw_decode(stripped, start)
        except json.JSONDecodeError as exc:
            raise VALIDATOR.ContractError(f"cannot decode response JSON: {exc}") from exc
        remainder = stripped[end:]
        if "{" in remainder:
            raise VALIDATOR.ContractError("response contains multiple JSON objects")
    if not isinstance(value, dict):
        raise VALIDATOR.ContractError("response JSON root must be an object")
    return value


def _canonical_enum(value: Any, mapping: dict[str, str]) -> Any:
    if not isinstance(value, str):
        return value
    return mapping.get(value.strip().casefold(), value)


def _normalize_response(
    raw: bytes, *, review_id: str, focus: str
) -> tuple[dict[str, Any], list[str]]:
    try:
        bare_value = json.loads(raw.decode("utf-8"))
        bare_object = isinstance(bare_value, dict)
    except (UnicodeDecodeError, json.JSONDecodeError):
        bare_object = False
    value = _decode_response(raw)
    normalized = dict(value)
    changes: list[str] = []
    if not bare_object:
        changes.append("unwrapped response JSON")

    defaults: dict[str, Any] = {
        "schema_version": 1,
        "review_id": review_id,
        "focus": focus,
        "files_reviewed": [],
        "coverage_notes": [],
        "findings": [],
    }
    for field, default in defaults.items():
        if field not in normalized:
            normalized[field] = default
            changes.append(f"filled {field}")

    if isinstance(normalized.get("focus"), str):
        canonical_focus = normalized["focus"].strip().casefold()
        if canonical_focus in FOCI and canonical_focus != normalized["focus"]:
            normalized["focus"] = canonical_focus
            changes.append("canonicalized focus")

    canonical_status = _canonical_enum(normalized.get("status"), STATUS_VALUES)
    if canonical_status != normalized.get("status"):
        normalized["status"] = canonical_status
        changes.append("canonicalized status")
    if "status" not in normalized:
        findings = normalized.get("findings")
        if isinstance(findings, list) and findings:
            normalized["status"] = "FINDINGS"
            changes.append("derived FINDINGS status from non-empty findings")

    summary_defaults = {
        "PASS": "No findings reported.",
        "NOT_APPLICABLE": "Review focus was reported as not applicable.",
        "BLOCKED": "Reviewer reported that this focus was blocked.",
    }
    if "summary" not in normalized:
        status = normalized.get("status")
        findings = normalized.get("findings")
        if status == "FINDINGS" and isinstance(findings, list) and findings:
            count = len(findings)
            normalized["summary"] = f"Reviewer reported {count} finding{'s' if count != 1 else ''}."
            changes.append("generated summary from findings")
        elif status in summary_defaults:
            normalized["summary"] = summary_defaults[status]
            changes.append("generated summary from status")

    if (
        focus == "react"
        and normalized.get("status") == "NOT_APPLICABLE"
        and "analyzer" not in normalized
    ):
        normalized["analyzer"] = {
            "command": "not run",
            "status": "NOT_APPLICABLE",
            "notes": normalized.get("summary", "React focus was not applicable."),
        }
        changes.append("generated non-applicable React analyzer result")

    analyzer = normalized.get("analyzer")
    if isinstance(analyzer, dict):
        analyzer = dict(analyzer)
        canonical_analyzer_status = _canonical_enum(
            analyzer.get("status"), ANALYZER_STATUS_VALUES
        )
        if canonical_analyzer_status != analyzer.get("status"):
            analyzer["status"] = canonical_analyzer_status
            changes.append("canonicalized analyzer.status")
        normalized["analyzer"] = analyzer

    severities = {item.casefold(): item for item in VALIDATOR.SEVERITIES}
    categories = {item.casefold(): item for item in VALIDATOR.CATEGORIES}
    findings = normalized.get("findings")
    if isinstance(findings, list):
        canonical_findings: list[Any] = []
        for index, finding in enumerate(findings):
            if not isinstance(finding, dict):
                canonical_findings.append(finding)
                continue
            canonical_finding = dict(finding)
            for field, values in (("severity", severities), ("category", categories)):
                current = canonical_finding.get(field)
                if isinstance(current, str):
                    canonical = values.get(current.strip().casefold(), current)
                    if canonical != current:
                        canonical_finding[field] = canonical
                        changes.append(f"canonicalized findings[{index}].{field}")
            if "supporting_locations" not in canonical_finding:
                canonical_finding["supporting_locations"] = []
                changes.append(f"filled findings[{index}].supporting_locations")
            canonical_findings.append(canonical_finding)
        normalized["findings"] = canonical_findings

    return normalized, changes


def _blocked_result(review_id: str, focus: str, errors: list[str]) -> dict[str, Any]:
    notes = [f"Attempt {index} was rejected: {error}" for index, error in enumerate(errors, 1)]
    result: dict[str, Any] = {
        "schema_version": 1,
        "review_id": review_id,
        "focus": focus,
        "status": "BLOCKED",
        "summary": "Reviewer responses failed contract validation twice.",
        "files_reviewed": [],
        "coverage_notes": notes,
        "findings": [],
    }
    if focus == "react":
        result["analyzer"] = {
            "command": "not run",
            "status": "NOT_APPLICABLE",
            "notes": "No contract-valid React reviewer response was available.",
        }
    return result


def gate_result(
    *, packet_path: Path, focus: str, raw_path: Path, state_path: Path, output_path: Path
) -> dict[str, Any]:
    if focus not in FOCI:
        raise RuntimeError(f"invalid focus: {focus}")
    if output_path.exists():
        raise RuntimeError(f"result is already finalized: {output_path}")

    packet = VALIDATOR.validate_packet(packet_path)
    review_id = packet["review_id"]
    state = _read_state(state_path, review_id, focus)
    attempt = state["attempts"] + 1
    raw = raw_path.read_bytes()
    raw_artifact = state_path.parent / f"raw-{focus}-attempt-{attempt}.txt"
    _preserve_raw(raw_artifact, raw)

    try:
        normalized, changes = _normalize_response(raw, review_id=review_id, focus=focus)
        normalized_bytes = (json.dumps(normalized, separators=(",", ":")) + "\n").encode()
        with tempfile.NamedTemporaryFile(dir=state_path.parent, delete=False) as handle:
            handle.write(normalized_bytes)
            normalized_candidate = Path(handle.name)
        try:
            validation_errors = VALIDATOR.validate_result_errors(
                normalized_candidate, packet_path, focus
            )
            if validation_errors:
                raise VALIDATOR.ContractError("; ".join(validation_errors))
        finally:
            normalized_candidate.unlink(missing_ok=True)
    except Exception as exc:
        error = _bounded_error(exc)
        errors = [*state.get("errors", []), error]
        if attempt < MAX_ATTEMPTS:
            _replace_json(
                state_path,
                {**state, "attempts": attempt, "errors": errors, "status": "retry_required"},
            )
            return {
                "accepted": False,
                "status": "retry_required",
                "attempt": attempt,
                "error": error,
            }

        blocked = _blocked_result(review_id, focus, errors)
        blocked_bytes = (json.dumps(blocked, separators=(",", ":")) + "\n").encode()
        with tempfile.NamedTemporaryFile(dir=state_path.parent, delete=False) as handle:
            handle.write(blocked_bytes)
            blocked_candidate = Path(handle.name)
        try:
            VALIDATOR.validate_result(blocked_candidate, packet_path, focus)
        finally:
            blocked_candidate.unlink(missing_ok=True)
        _atomic_create(output_path, blocked_bytes)
        _replace_json(
            state_path, {**state, "attempts": attempt, "errors": errors, "status": "blocked"}
        )
        return {"accepted": False, "status": "blocked", "attempt": attempt, "error": error}
    accepted_bytes = normalized_bytes if changes else raw
    _atomic_create(output_path, accepted_bytes)
    _replace_json(state_path, {**state, "attempts": attempt, "errors": [], "status": "accepted"})
    return {
        "accepted": True,
        "status": "accepted",
        "attempt": attempt,
        "normalized": bool(changes),
        "normalizations": changes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--focus", required=True, choices=sorted(FOCI))
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        outcome = gate_result(
            packet_path=args.packet,
            focus=args.focus,
            raw_path=args.raw,
            state_path=args.state,
            output_path=args.output,
        )
    except (OSError, RuntimeError, VALIDATOR.ContractError) as exc:
        print(json.dumps({"ok": False, "error": _bounded_error(exc)}, separators=(",", ":")))
        return 1
    print(json.dumps({"ok": True, **outcome}, separators=(",", ":")))
    return 0 if outcome["status"] in {"accepted", "blocked"} else 2


if __name__ == "__main__":
    sys.exit(main())
