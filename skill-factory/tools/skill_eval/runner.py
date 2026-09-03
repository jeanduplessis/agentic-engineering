from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from .grading import checks_from_legacy_expectations, grade_response
from .manifest import EvalCase, load_manifest, suite_configurations
from .reporting import write_reports
from .sandbox import create_sandbox


EXECUTABLE_SUITE_TYPES = {"workflow", "regression", "trigger"}
REAL_HARNESSES = {"pi"}
LIVE_OPT_IN_ENV = "SKILL_EVAL_ALLOW_LIVE"
LEGACY_PI_LIVE_OPT_IN_ENV = "SKILL_EVAL_ALLOW_LIVE_PI"


def run_suite(
    manifest_path: str | Path,
    suite_name: str,
    result_root: str | Path,
    configurations: dict[str, dict[str, Any]] | None = None,
    *,
    require_real: bool = False,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    suite = manifest.suite(suite_name)
    configs = suite_configurations(manifest, suite)
    if configurations is not None and (configurations or suite.type == "trigger"):
        configs = configurations
    if suite.type == "trigger":
        from .trigger import validate_trigger_suite
        validate_trigger_suite(manifest, suite, configs)
    for config in configs.values():
        _harness_contract(config)  # Reject unsupported harnesses before creating artifacts or processes.
    if require_real:
        synthetic_configs = [name for name, config in configs.items() if _harness_contract(config)["synthetic"]]
        if synthetic_configs:
            raise ValueError(
                "Benchmark-quality run requires real harness; "
                f"synthetic configurations are not allowed: {', '.join(synthetic_configs)}"
            )
    result_root = Path(result_root).resolve()
    if suite.type == "trigger" and result_root.exists() and any(result_root.iterdir()):
        raise FileExistsError("Trigger results require a fresh directory; prior evidence will not be overwritten.")
    result_root.mkdir(parents=True, exist_ok=True)
    runs = []

    if suite.type not in EXECUTABLE_SUITE_TYPES:
        summary = {
            "skill": manifest.skill.get("name"),
            "suite": suite.name,
            "suite_type": suite.type,
            "status": "unsupported",
            "unsupported_reason": suite.unsupported_reason or f"{suite.type} suite execution is not implemented in this runner.",
            "runs": [],
        }
        (result_root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
        return summary

    trigger_plan = None
    if suite.type == "trigger":
        from .trigger import freeze_trigger_inputs
        trigger_plan = freeze_trigger_inputs(manifest, suite, configs, result_root)

    for case in suite.cases:
        for config_name, config in configs.items():
            run_dir = result_root / manifest.skill.get("name", "unknown-skill") / suite.name / case.id / config_name
            run_dir.mkdir(parents=True, exist_ok=True)
            sandbox = create_sandbox(
                result_root,
                f"{suite.name}-{case.id}-{config_name}",
                trigger_plan["fixture"] if trigger_plan else _resolve_fixture(manifest.path, suite.fixture),
            )
            run = _run_case(
                case,
                config_name,
                config,
                sandbox.path,
                run_dir,
                skill_path=_resolve_manifest_path(manifest.path, manifest.skill.get("path")),
                custom_grader_path=_resolve_manifest_path(manifest.path, suite.custom_grader),
                manifest_metadata={
                    "path": str(manifest.path),
                    "schema_version": manifest.schema_version,
                },
                suite_name=suite.name,
                trigger_plan=trigger_plan,
            )
            runs.append(run)

    benchmark = write_reports(
        result_root=result_root,
        skill_name=manifest.skill.get("name", "unknown-skill"),
        suite=suite,
        runs=runs,
    )
    summary = {
        "skill": manifest.skill.get("name"),
        "suite": suite.name,
        "suite_type": suite.type,
        "status": "completed",
        "harness_modes": {name: _harness_contract(config)["mode"] for name, config in configs.items()},
        "synthetic": any(_harness_contract(config)["synthetic"] for config in configs.values()),
        "runs": runs,
        "benchmark": benchmark,
    }
    (result_root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def _run_case(
    case: EvalCase,
    config_name: str,
    config: dict[str, Any],
    sandbox_path: Path,
    run_dir: Path,
    *,
    skill_path: Path | None = None,
    custom_grader_path: Path | None = None,
    manifest_metadata: dict[str, Any] | None = None,
    suite_name: str | None = None,
    trigger_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    start = time.perf_counter()
    started_at = time.time()
    before_workspace = _snapshot_workspace(sandbox_path)
    harness_result = _execute_harness(
        case, config, sandbox_path=sandbox_path, skill_path=skill_path,
        trigger_plan=trigger_plan, config_name=config_name, run_dir=run_dir,
    )
    response = harness_result["response"]
    elapsed_ms = round((time.perf_counter() - start) * 1000, 3)
    finished_at = time.time()
    contract = _harness_contract(config)
    if trigger_plan:
        contract["metric_provenance"]["pass_rate"] = "observed_pi_skill_selection"
    raw_output = {
        "harness": config.get("harness", "static"),
        "harness_mode": contract["mode"],
        "synthetic": contract["synthetic"],
        **harness_result["raw_output"],
    }
    timing = {
        "started_at_unix": started_at,
        "finished_at_unix": finished_at,
        "elapsed_ms": elapsed_ms,
    }
    usage = {
        "input_chars": len(case.prompt),
        "output_chars": len(response),
        "tokens": None,
    }
    after_workspace = _snapshot_workspace(sandbox_path)
    artifact_manifest = _artifact_manifest(before_workspace, after_workspace)
    workspace_diff = _workspace_diff(before_workspace, after_workspace)
    checks = list(case.checks) or checks_from_legacy_expectations(case.expected_output, case.expectations)
    trigger_observation = None
    if trigger_plan is not None:
        from .trigger import inputs_unchanged, inspect_trigger_trace
        (run_dir / "pi-events.jsonl").write_text(raw_output.get("stdout", ""))
        observer_path = run_dir / "observer-context.jsonl"
        try:
            observer_output = observer_path.read_text() if observer_path.exists() else ""
        except (OSError, UnicodeError):
            observer_output = "unreadable observer evidence"
        trigger_observation = inspect_trigger_trace(
            raw_output.get("stdout", ""), plan=trigger_plan, sandbox=sandbox_path, config=config,
            observer_output=observer_output,
        )
        if not inputs_unchanged(trigger_plan, config_name) or workspace_diff:
            trigger_observation["errors"].append("inputs_or_workspace_changed")
            trigger_observation["valid"] = False
        response = trigger_observation["response"]
        usage["output_chars"] = len(response)
        harness_result["skill_paths_loaded"] = [trigger_plan["skill_path"]] if trigger_observation["loaded"] else []
        harness_result["skill_paths_advertised"] = [trigger_plan["skill_path"]] if trigger_observation["advertised"] else []
        if raw_output["status"] == "passed" and not trigger_observation["valid"]:
            raw_output["status"] = "trace_invalid"
            raw_output["error"] = ", ".join(trigger_observation["errors"])
        (run_dir / "trigger.json").write_text(json.dumps(trigger_observation, indent=2, sort_keys=True))
    if raw_output["status"] == "skipped":
        grade = _not_graded(raw_output.get("skip_reason", "Run skipped."), "run_skipped")
    elif raw_output["status"] != "passed":
        reason = raw_output.get("error") or raw_output.get("stderr") or f"Harness status: {raw_output['status']}"
        kind = "trace_invalid" if raw_output["status"] == "trace_invalid" else "process_failed"
        label = "Invalid trace" if kind == "trace_invalid" else "Process failure"
        grade = _not_graded(f"{label}; deterministic grading not run: {reason}", kind)
    elif trigger_observation is not None:
        from .trigger import grade_trigger
        grade = grade_trigger(trigger_observation, case.metadata["should_trigger"])
    else:
        grade = grade_response(
            response,
            checks,
            custom_grader=str(custom_grader_path) if custom_grader_path else None,
            case=case,
            context={
                "configuration": config_name,
                "sandbox_path": str(sandbox_path),
                "run_dir": str(run_dir),
                "artifact_manifest": artifact_manifest,
                "workspace_diff": workspace_diff,
            },
            subjective_checks=case.subjective_checks,
            judge_config=config.get("judge"),
        )
    events = [
        {"event": "run_started", "case_id": case.id, "configuration": config_name, "time_unix": started_at},
        {"event": "harness_finished", "exit_code": raw_output.get("exit_code"), "status": raw_output["status"], "time_unix": finished_at},
        *(trigger_observation["events"] if trigger_observation else []),
        {"event": "run_finished", "case_id": case.id, "configuration": config_name, "time_unix": finished_at},
    ]

    (run_dir / "raw_output.json").write_text(json.dumps(raw_output, indent=2, sort_keys=True))
    (run_dir / "events.jsonl").write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events))
    (run_dir / "response.md").write_text(response)
    (run_dir / "timing.json").write_text(json.dumps(timing, indent=2, sort_keys=True))
    (run_dir / "usage.json").write_text(json.dumps(usage, indent=2, sort_keys=True))
    (run_dir / "grade.json").write_text(json.dumps(grade, indent=2, sort_keys=True))
    (run_dir / "artifact_manifest.json").write_text(json.dumps(artifact_manifest, indent=2, sort_keys=True))
    (run_dir / "workspace_diff.txt").write_text("\n".join(workspace_diff) + ("\n" if workspace_diff else ""))
    (run_dir / "metadata.json").write_text(json.dumps({
        "sandbox": str(sandbox_path),
        "suite": suite_name,
        "case_id": case.id,
        "configuration": config_name,
        "manifest": manifest_metadata or {},
        "harness": contract,
        "skill_paths_loaded": harness_result.get("skill_paths_loaded", []),
        "skill_paths_advertised": harness_result.get("skill_paths_advertised", []),
        "skill_loading_evidence": "pi_tool_events" if trigger_plan else "unobserved",
    }, indent=2, sort_keys=True))

    return {
        "case_id": case.id,
        "configuration": config_name,
        "run_dir": str(run_dir),
        "prompt": case.prompt,
        "status": raw_output["status"],
        "passed": grade["passed"],
        "elapsed_ms": elapsed_ms,
        "usage": usage,
        "harness_mode": contract["mode"],
        "synthetic": contract["synthetic"],
        "metric_provenance": contract["metric_provenance"],
        "model": contract.get("model"),
        "provider": contract.get("provider"),
        "grade_summary": grade["summary"],
        **({"should_trigger": case.metadata["should_trigger"],
            "trigger_outcome": grade.get("outcome", "invalid"),
            "observed_model": trigger_observation["model"],
            "observed_provider": trigger_observation["provider"]} if trigger_observation else {}),
    }


def _not_graded(summary: str, judge_reason: str) -> dict[str, Any]:
    return {
        "status": "not_graded",
        "passed": None,
        "summary": summary,
        "checks": [],
        "totals": {"passed": 0, "failed": 0, "skipped": 0},
        "judge": {"status": "skipped", "reason": judge_reason, "metadata": None, "subjective_checks": [], "results": []},
    }


def _harness_contract(config: dict[str, Any]) -> dict[str, Any]:
    harness = config.get("harness", "static")
    if harness == "static":
        mode = "static"
        synthetic = True
        provenance = {
            "pass_rate": "synthetic_static_response",
            "timing": "runner_wall_clock_only",
            "usage": "character_count_placeholder",
        }
    elif harness == "replay":
        mode = "replay"
        synthetic = True
        provenance = {
            "pass_rate": "replayed_prior_output",
            "timing": "replayed_or_runner_wall_clock",
            "usage": "replayed_or_unknown",
        }
    elif harness in REAL_HARNESSES:
        mode = "real"
        synthetic = False
        provenance = {
            "pass_rate": "real_agent_output",
            "timing": "real_process_wall_clock",
            "usage": "provider_or_harness_reported_when_available",
        }
    else:
        raise ValueError(f"Unsupported harness: {harness}")
    return {
        "name": harness,
        "mode": mode,
        "synthetic": synthetic,
        "metric_provenance": provenance,
        "model": config.get("model"),
        "provider": config.get("provider"),
    }


def _snapshot_workspace(path: Path) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return snapshot
    for file_path in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        relative = file_path.relative_to(path).as_posix()
        data = file_path.read_bytes()
        snapshot[relative] = {
            "path": relative,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    return snapshot


def _artifact_manifest(before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]) -> dict[str, Any]:
    files = []
    for path, metadata in sorted(after.items()):
        prior = before.get(path)
        if prior is None:
            change = "added"
        elif prior.get("sha256") != metadata.get("sha256"):
            change = "modified"
        else:
            change = "unchanged"
        files.append({**metadata, "change": change})
    deleted = sorted(path for path in before if path not in after)
    return {"files": files, "deleted": deleted}


def _workspace_diff(before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]) -> list[str]:
    diff: list[str] = []
    for path in sorted(after):
        if path not in before:
            diff.append(f"A {path}")
        elif before[path].get("sha256") != after[path].get("sha256"):
            diff.append(f"M {path}")
    for path in sorted(path for path in before if path not in after):
        diff.append(f"D {path}")
    return diff


def _execute_harness(
    case: EvalCase,
    config: dict[str, Any],
    *,
    sandbox_path: Path,
    skill_path: Path | None,
    trigger_plan: dict[str, Any] | None = None,
    config_name: str = "",
    run_dir: Path | None = None,
) -> dict[str, Any]:
    harness = config.get("harness", "static")
    if harness == "static":
        response = config.get("response")
        if response is None:
            strategy = config.get("response_strategy", "expected_output")
            if strategy == "expected_output":
                response = case.expected_output or ""
            elif strategy == "expected_output_and_expectations":
                response = "\n\n".join(part for part in [case.expected_output or "", *case.expectations] if part)
            elif strategy == "prompt":
                response = case.prompt
            elif strategy == "prompt_and_expectations":
                response = "\n\n".join(part for part in [case.prompt, *case.expectations] if part)
            else:
                raise ValueError(f"Unsupported static response strategy: {strategy}")
        response = str(response)
        return {
            "response": response,
            "raw_output": {"status": "passed", "stdout": response, "stderr": "", "exit_code": 0},
            "skill_paths_loaded": [],
        }
    if harness == "replay":
        response_path = config.get("response_path")
        response = Path(response_path).read_text() if response_path else str(config.get("response", ""))
        return {
            "response": response,
            "raw_output": {"status": "passed", "stdout": response, "stderr": "", "exit_code": 0},
            "skill_paths_loaded": [],
        }
    if harness == "pi":
        return _execute_pi_harness(case, config, sandbox_path=sandbox_path, skill_path=skill_path,
                                   trigger_plan=trigger_plan, config_name=config_name, run_dir=run_dir)
    raise ValueError(f"Unsupported harness: {harness}")


def _live_execution_allowed(config: dict[str, Any]) -> bool:
    return bool(
        config.get("allow_live")
        or os.environ.get(LIVE_OPT_IN_ENV) == "1"
        or os.environ.get(LEGACY_PI_LIVE_OPT_IN_ENV) == "1"
    )


def _resolve_executable(config: dict[str, Any], default: str) -> str | None:
    executable = str(config.get("executable") or default)
    return shutil.which(executable) if not Path(executable).exists() else executable


def _process_harness_result(
    command: list[str],
    *,
    sandbox_path: Path,
    env: dict[str, str],
    timeout_seconds: float,
    skill_paths_loaded: list[str],
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=sandbox_path,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout or ""
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr or ""
        return {
            "response": stdout,
            "raw_output": {
                "status": "process_failed",
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": None,
                "command": command,
                "cwd": str(sandbox_path),
                "error": "timeout",
            },
            "skill_paths_loaded": skill_paths_loaded,
        }
    except OSError as exc:
        return {
            "response": "", "skill_paths_loaded": skill_paths_loaded,
            "raw_output": {"status": "process_failed", "stdout": "", "stderr": str(exc),
                           "exit_code": None, "command": command, "cwd": str(sandbox_path),
                           "error": "process_start_failed"},
        }

    return {
        "response": completed.stdout,
        "raw_output": {
            "status": "passed" if completed.returncode == 0 else "process_failed",
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "exit_code": completed.returncode,
            "command": command,
            "cwd": str(sandbox_path),
        },
        "skill_paths_loaded": skill_paths_loaded,
    }


def _execute_pi_harness(
    case: EvalCase,
    config: dict[str, Any],
    *,
    sandbox_path: Path,
    skill_path: Path | None,
    trigger_plan: dict[str, Any] | None = None,
    config_name: str = "",
    run_dir: Path | None = None,
) -> dict[str, Any]:
    if not _live_execution_allowed(config):
        return _skipped_harness_result(
            f"live harness execution is disabled; set allow_live or {LIVE_OPT_IN_ENV}=1"
        )

    if trigger_plan is not None:
        from .trigger import inputs_unchanged
        if not inputs_unchanged(trigger_plan, config_name):
            return _skipped_harness_result("Frozen trigger inputs changed; refusing another process.")

    executable = str(config.get("executable") or "pi")
    resolved_executable = _resolve_executable(config, "pi")
    if not resolved_executable:
        return _skipped_harness_result(f"Pi executable not found: {executable}")

    command = [
        resolved_executable,
        "--no-session",
        "--no-context-files",
        "--no-extensions",
        "--no-prompt-templates",
        "--no-skills",
    ]
    if config.get("provider"):
        command.extend(["--provider", str(config["provider"])])
    if config.get("model"):
        command.extend(["--model", str(config["model"])])
    if config.get("thinking"):
        command.extend(["--thinking", str(config["thinking"])])

    advertised: list[str] = []
    trigger_env: dict[str, str] = {}
    if trigger_plan is not None:
        from .trigger import trigger_command
        assert run_dir is not None
        command, trigger_env = trigger_command(command, trigger_plan, config_name, sandbox_path, run_dir)
        advertised.append(trigger_plan["skill_path"])
    elif config.get("force_skill"):
        if skill_path is None:
            return _skipped_harness_result("force_skill requested but manifest skill.path is missing")
        command.extend(["--skill", str(skill_path)])
        advertised.append(str(skill_path))

    command.extend(["-p", "--", case.prompt])
    env = os.environ.copy()
    env.update({str(key): str(value) for key, value in dict(config.get("env", {})).items()})
    env.update(trigger_env)
    result = _process_harness_result(
        command,
        sandbox_path=sandbox_path,
        env=env,
        timeout_seconds=float(config.get("timeout_seconds", 120)),
        skill_paths_loaded=[],
    )
    result["skill_paths_advertised"] = advertised
    return result


def _skipped_harness_result(reason: str) -> dict[str, Any]:
    return {
        "response": "",
        "raw_output": {
            "status": "skipped",
            "stdout": "",
            "stderr": reason,
            "exit_code": None,
            "skip_reason": reason,
        },
        "skill_paths_loaded": [],
    }


def _resolve_manifest_path(manifest_path: Path, relative_or_absolute: str | None) -> Path | None:
    if not relative_or_absolute:
        return None
    path = Path(relative_or_absolute)
    if path.is_absolute():
        return path
    return (manifest_path.parent / path).resolve()


def _resolve_fixture(manifest_path: Path, fixture: dict[str, Any]) -> dict[str, Any]:
    resolved = dict(fixture)
    if resolved.get("type") == "copy" and resolved.get("path"):
        source = Path(str(resolved["path"])).expanduser()
        if not source.is_absolute():
            source = (manifest_path.parent / source).resolve()
        resolved["path"] = str(source)
    return resolved
