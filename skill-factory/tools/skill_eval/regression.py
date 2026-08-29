from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from .manifest import EvalCase, load_manifest


def promote_failures_to_regression_cases(
    *,
    manifest_path: str | Path,
    result_root: str | Path,
    output_manifest_path: str | Path | None = None,
    source_bead: str | None = None,
) -> dict[str, Any]:
    """Promote failed real harness runs from a result bundle into regression cases."""
    manifest_path = Path(manifest_path)
    result_root = Path(result_root)
    output_path = Path(output_manifest_path) if output_manifest_path else manifest_path
    manifest = json.loads(manifest_path.read_text())
    loaded_manifest = load_manifest(manifest_path)
    summary = json.loads((result_root / "summary.json").read_text())
    if summary.get("suite_type") == "trigger":
        raise ValueError("Trigger failures cannot be promoted to workflow regressions. Retain the trace and add a natural trigger case instead.")
    suites_by_name = {suite.name: suite for suite in loaded_manifest.suites}
    cases_by_suite = {
        suite.name: {case.id: case for case in suite.cases}
        for suite in loaded_manifest.suites
    }
    regression_suite = _ensure_regression_suite(manifest)
    existing_ids = {case.get("id") for case in regression_suite.setdefault("cases", [])}
    promoted_cases = []

    for run in summary.get("runs", []):
        if not _is_promotable_real_failure(run):
            continue
        suite_name = summary.get("suite")
        source_suite = suites_by_name.get(str(suite_name))
        if source_suite and source_suite.custom_grader and not regression_suite.get("custom_grader"):
            regression_suite["custom_grader"] = source_suite.custom_grader
        source_case = cases_by_suite.get(suite_name, {}).get(str(run.get("case_id")))
        case_id = _unique_id(
            f"regression-{suite_name}-{run.get('case_id')}-{run.get('configuration')}",
            existing_ids,
        )
        existing_ids.add(case_id)
        source_run_id = f"{suite_name}/{run.get('case_id')}/{run.get('configuration')}"
        promoted = {
            "id": case_id,
            **_source_case_fields(source_case, run),
            "regression_from": source_bead or source_run_id,
            "source_bead": source_bead,
            "source_run_id": source_run_id,
            "trace_path": run.get("run_dir"),
            "failure_summary": _failure_summary(run),
            "source_suite": suite_name,
            "source_case_id": str(run.get("case_id")),
            "source_configuration": run.get("configuration"),
            "harness_mode": run.get("harness_mode"),
        }
        regression_suite["cases"].append(promoted)
        promoted_cases.append(promoted)

    if output_path.parent.resolve() != manifest_path.parent.resolve():
        _rewrite_relative_paths_for_output(manifest, manifest_path.parent, output_path.parent)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return {
        "manifest": str(output_path),
        "promoted": len(promoted_cases),
        "cases": promoted_cases,
    }


def _rewrite_relative_paths_for_output(manifest: dict[str, Any], input_dir: Path, output_dir: Path) -> None:
    skill = manifest.get("skill")
    if isinstance(skill, dict) and skill.get("path"):
        skill["path"] = _relocate_path(str(skill["path"]), input_dir, output_dir)
    for suite in manifest.get("suites", []):
        if not isinstance(suite, dict):
            continue
        for key in ("legacy_evals", "custom_grader"):
            if suite.get(key):
                suite[key] = _relocate_path(str(suite[key]), input_dir, output_dir)
        fixture = suite.get("fixture")
        if isinstance(fixture, dict) and fixture.get("type") == "copy" and fixture.get("path"):
            fixture["path"] = _relocate_path(str(fixture["path"]), input_dir, output_dir)


def _relocate_path(value: str, input_dir: Path, output_dir: Path) -> str:
    path = Path(value).expanduser()
    if path.is_absolute():
        return str(path)
    resolved = (input_dir / path).resolve()
    return os.path.relpath(resolved, output_dir.resolve())


def _source_case_fields(source_case: EvalCase | None, run: dict[str, Any]) -> dict[str, Any]:
    if source_case is None:
        return {"prompt": run.get("prompt") or "", "checks": []}
    fields: dict[str, Any] = {
        "prompt": source_case.prompt,
        "checks": [dict(check) for check in source_case.checks],
    }
    if source_case.expected_output is not None:
        fields["expected_output"] = source_case.expected_output
    if source_case.expectations:
        fields["expectations"] = list(source_case.expectations)
    if source_case.subjective_checks:
        fields["subjective_checks"] = [dict(check) for check in source_case.subjective_checks]
    return fields


def _ensure_regression_suite(manifest: dict[str, Any]) -> dict[str, Any]:
    for suite in manifest.setdefault("suites", []):
        if suite.get("name") == "regression":
            suite.setdefault("type", "regression")
            suite.setdefault("fixture", {"type": "empty"})
            suite.setdefault("cases", [])
            return suite
    suite = {"name": "regression", "type": "regression", "fixture": {"type": "empty"}, "cases": []}
    manifest["suites"].append(suite)
    return suite


def _is_promotable_real_failure(run: dict[str, Any]) -> bool:
    return run.get("harness_mode") == "real" and run.get("status") != "skipped" and run.get("passed") is False


def _failure_summary(run: dict[str, Any]) -> str:
    summary = run.get("grade_summary") or "failed real eval run"
    return summary if "fail" in summary.lower() else f"failed: {summary}"


def _unique_id(seed: str, existing_ids: set[str | None]) -> str:
    base = re.sub(r"[^a-zA-Z0-9_.-]+", "-", seed).strip("-").lower()
    if base not in existing_ids:
        return base
    index = 2
    while f"{base}-{index}" in existing_ids:
        index += 1
    return f"{base}-{index}"
