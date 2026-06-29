from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EvalCase:
    id: str
    prompt: str
    expected_output: str | None = None
    files: tuple[str, ...] = ()
    expectations: tuple[str, ...] = ()
    checks: tuple[dict[str, Any], ...] = ()
    subjective_checks: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class EvalSuite:
    name: str
    type: str
    fixture: dict[str, Any]
    cases: tuple[EvalCase, ...]
    mode: str = "forced"
    unsupported_reason: str | None = None
    custom_grader: str | None = None


@dataclass(frozen=True)
class EvalManifest:
    path: Path
    skill: dict[str, Any]
    suites: tuple[EvalSuite, ...]
    configurations: dict[str, dict[str, Any]]
    schema_version: int | None = None

    def suite(self, name: str) -> EvalSuite:
        for suite in self.suites:
            if suite.name == name:
                return suite
        raise KeyError(f"Unknown eval suite: {name}")


def load_manifest(path: str | Path) -> EvalManifest:
    manifest_path = Path(path)
    data = json.loads(manifest_path.read_text())
    suites = tuple(_suite_from_dict(suite, manifest_path.parent) for suite in data.get("suites", ()))
    return EvalManifest(
        path=manifest_path,
        skill=dict(data.get("skill", {})),
        suites=suites,
        configurations={name: dict(value) for name, value in data.get("configurations", {}).items()},
        schema_version=data.get("schema_version"),
    )


def _suite_from_dict(data: dict[str, Any], base_dir: Path) -> EvalSuite:
    cases_data = data.get("cases")
    if cases_data is None and "legacy_evals" in data:
        cases_data = _load_legacy_cases(base_dir / data["legacy_evals"])
    cases = tuple(_case_from_dict(case) for case in cases_data or ())
    return EvalSuite(
        name=data["name"],
        type=data.get("type", "workflow"),
        fixture=dict(data.get("fixture", {"type": "empty"})),
        cases=cases,
        mode=data.get("mode", "forced"),
        unsupported_reason=data.get("unsupported_reason"),
        custom_grader=data.get("custom_grader"),
    )


def _load_legacy_cases(path: Path) -> list[dict[str, Any]]:
    legacy = json.loads(path.read_text())
    return list(legacy.get("evals", ()))


def _case_from_dict(data: dict[str, Any]) -> EvalCase:
    metadata = {k: v for k, v in data.items() if k not in {
        "id", "prompt", "expected_output", "files", "expectations", "checks", "subjective_checks"
    }}
    return EvalCase(
        id=str(data["id"]),
        prompt=data["prompt"],
        expected_output=data.get("expected_output"),
        files=tuple(data.get("files", ())),
        expectations=tuple(data.get("expectations", ())),
        checks=tuple(dict(check) for check in data.get("checks", ())),
        subjective_checks=tuple(dict(check) for check in data.get("subjective_checks", ())),
        metadata=metadata or None,
    )
