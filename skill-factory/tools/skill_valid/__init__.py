from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TextIO

from tools.llm_optimal_check import check_path as default_llm_optimal_check
from tools.skill_eval.manifest import EvalManifest, load_manifest, suite_configurations
from tools.skill_eval.runner import run_suite
from tools.skill_valid.spec_checks import run_skill_spec_checks, summarize_checks

GATE_ORDER = ("target", "skill_spec", "eval_manifest", "agents_md", "llm_optimal_check", "live_opt_in", "validate_skills", "live_eval")
REQUIRED_AGENT_HEADINGS = ("Purpose", "How the skill works", "Eval and validation", "Change guidelines")
SENTINEL_PREFIX = "SKILL_VALID_RESULT="


@dataclass(frozen=True)
class ValidationOptions:
    target: Path | str
    repo_root: Path | str = Path.cwd()
    allow_live: bool = False
    allow_live_pi: bool = False
    harness: str | None = None
    provider: str | None = None
    model: str | None = None
    thinking: str | None = None
    artifact_base: Path | str | None = None
    env: dict[str, str] | None = None
    harness_executable: str | None = None
    pi_executable: str = "pi"
    validate_timeout_seconds: float = 300.0
    include_trigger: bool = False


@dataclass(frozen=True)
class CompletedProcessLike:
    returncode: int
    stdout: str
    stderr: str


PiRunner = Callable[..., CompletedProcessLike]
EvalRunner = Callable[..., dict[str, Any]]
LlmOptimalChecker = Callable[[Path], dict[str, Any]]


@dataclass(frozen=True)
class ValidationDependencies:
    harness_runner: PiRunner | None = None
    pi_runner: PiRunner | None = None
    eval_runner: EvalRunner = run_suite
    llm_optimal_checker: LlmOptimalChecker = default_llm_optimal_check

    def run_harness(self, command: list[str], *, cwd: Path, env: dict[str, str], timeout: float) -> CompletedProcessLike:
        runner = self.harness_runner or self.pi_runner
        if runner is not None:
            return runner(command, cwd=cwd, env=env, timeout=timeout)
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return CompletedProcessLike(completed.returncode, completed.stdout, completed.stderr)


@dataclass(frozen=True)
class SentinelParseResult:
    passed: bool
    message: str
    payload: dict[str, Any] | None = None


@dataclass
class ManifestValidation:
    manifest: EvalManifest
    raw: dict[str, Any]
    manifest_path: Path
    workflow_suite: str
    regression_suite: str | None
    asset_refs: list[str]
    workflow_case_count: int
    regression_case_count: int
    with_skill_config: dict[str, Any]


@dataclass
class ArtifactManager:
    base: Path | None
    root: Path | None = None

    def ensure(self) -> Path:
        if self.root is None:
            if self.base is None:
                self.root = Path(tempfile.mkdtemp(prefix="skill-valid-"))
            else:
                self.base.mkdir(parents=True, exist_ok=True)
                self.root = Path(tempfile.mkdtemp(prefix="skill-valid-", dir=str(self.base)))
        return self.root

    def child(self, name: str) -> Path:
        path = self.ensure() / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def cleanup_success(self) -> None:
        if self.root and self.root.exists():
            shutil.rmtree(self.root)

    def failure_path(self) -> str | None:
        if self.root and self.root.exists():
            return str(self.root)
        return None


@dataclass
class ValidationContext:
    options: ValidationOptions
    deps: ValidationDependencies
    repo_root: Path
    env: dict[str, str]
    stderr: TextIO | None = None
    result: dict[str, Any] = field(default_factory=dict)
    target_dir: Path | None = None
    target_rel: str | None = None
    manifest_info: ManifestValidation | None = None
    artifacts: ArtifactManager | None = None

    def log(self, message: str) -> None:
        if self.stderr is not None:
            print(f"skill_valid: {message}", file=self.stderr)


class GateFailure(Exception):
    def __init__(self, gate: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.gate = gate
        self.message = message
        self.details = details or {}


def validate_skill(
    options: ValidationOptions,
    *,
    deps: ValidationDependencies | None = None,
    stderr: TextIO | None = None,
) -> tuple[int, dict[str, Any]]:
    deps = deps or ValidationDependencies()
    repo_root = Path(options.repo_root).expanduser().resolve()
    env = dict(os.environ if options.env is None else options.env)
    result = _initial_result(options.target, repo_root)
    ctx = ValidationContext(
        options=options,
        deps=deps,
        repo_root=repo_root,
        env=env,
        stderr=stderr,
        result=result,
        artifacts=ArtifactManager(Path(options.artifact_base).expanduser().resolve() if options.artifact_base else None),
    )

    if not _run_required_gate(ctx, _gate_target, stop_after_failure=True):
        return _failed_result(ctx)

    cheap_gates_passed = True
    for gate in (_gate_skill_spec, _gate_eval_manifest, _gate_agents_md, _gate_llm_optimal_check, _gate_live_opt_in):
        cheap_gates_passed = _run_required_gate(ctx, gate, stop_after_failure=False) and cheap_gates_passed

    if not cheap_gates_passed:
        _mark_live_gates_not_run(ctx.result, "deterministic prerequisite gates failed")
        return _failed_result(ctx)

    if not _live_execution_allowed(ctx):
        _mark_live_gates_not_run(ctx.result, "live validation was not explicitly enabled")
        ctx.result["valid"] = True
        if ctx.artifacts:
            ctx.artifacts.cleanup_success()
        ctx.log("deterministic gates passed; live gates not enabled")
        return 0, ctx.result

    for gate in (_gate_validate_skills, _gate_live_eval):
        if not _run_required_gate(ctx, gate, stop_after_failure=True):
            return _failed_result(ctx)

    ctx.result["valid"] = True
    if ctx.artifacts:
        ctx.artifacts.cleanup_success()
    ctx.log("all gates passed")
    return 0, ctx.result


def _initial_result(target: Path | str, repo_root: Path) -> dict[str, Any]:
    target_path = Path(target).expanduser()
    if not target_path.is_absolute():
        target_path = repo_root / target_path
    target_display = _display_path(target_path, repo_root)
    return {
        "valid": False,
        "target": target_display,
        "gates": {name: {"status": "not_run", "message": "not run"} for name in GATE_ORDER},
    }


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(repo_root).as_posix()
    except ValueError:
        return str(path)


def _set_gate(result: dict[str, Any], gate: str, status: str, message: str, details: dict[str, Any] | None = None) -> None:
    value: dict[str, Any] = {"status": status, "message": message}
    if details:
        value["details"] = details
    result["gates"][gate] = value


def _pass_gate(ctx: ValidationContext, gate: str, message: str, details: dict[str, Any] | None = None) -> None:
    _set_gate(ctx.result, gate, "passed", message, details)
    ctx.log(f"gate {gate} passed")


def _warn_gate(ctx: ValidationContext, gate: str, message: str, details: dict[str, Any] | None = None) -> None:
    _set_gate(ctx.result, gate, "warn", message, details)
    ctx.log(f"gate {gate} warned: {message}")


def _run_required_gate(ctx: ValidationContext, gate_func: Callable[[ValidationContext], None], *, stop_after_failure: bool) -> bool:
    gate = _gate_name(gate_func)
    try:
        gate_func(ctx)
        return True
    except GateFailure as exc:
        _set_gate(ctx.result, exc.gate, "failed", exc.message, exc.details)
        if stop_after_failure:
            _mark_remaining_not_run(ctx.result, exc.gate)
        ctx.log(f"gate {exc.gate} failed: {exc.message}")
        return False
    except Exception as exc:  # Fail closed; callers still receive the compact JSON contract.
        message = f"Unexpected {gate} gate error: {exc}"
        _set_gate(ctx.result, gate, "failed", message, {"exception_type": type(exc).__name__})
        if stop_after_failure:
            _mark_remaining_not_run(ctx.result, gate)
        ctx.log(f"gate {gate} failed unexpectedly: {exc}")
        return False


def _gate_name(gate_func: Callable[[ValidationContext], None]) -> str:
    name = gate_func.__name__
    return name.removeprefix("_gate_")


def _failed_result(ctx: ValidationContext) -> tuple[int, dict[str, Any]]:
    failure_artifacts = ctx.artifacts.failure_path() if ctx.artifacts else None
    if failure_artifacts:
        ctx.result["failure_artifacts"] = failure_artifacts
    ctx.result["valid"] = False
    return 1, ctx.result


def _mark_remaining_not_run(result: dict[str, Any], failed_gate: str) -> None:
    seen_failed = False
    for gate in GATE_ORDER:
        if gate == failed_gate:
            seen_failed = True
            continue
        if seen_failed and result["gates"][gate]["status"] == "not_run":
            result["gates"][gate] = {"status": "not_run", "message": f"not run because {failed_gate} failed"}


def _mark_live_gates_not_run(result: dict[str, Any], reason: str) -> None:
    for gate in ("validate_skills", "live_eval"):
        if result["gates"][gate]["status"] == "not_run":
            result["gates"][gate] = {"status": "not_run", "message": f"not run because {reason}"}


def _gate_target(ctx: ValidationContext) -> None:
    target = Path(ctx.options.target).expanduser()
    if not target.is_absolute():
        target = ctx.repo_root / target
    target = target.resolve(strict=False)
    skills_root = (ctx.repo_root / "skills").resolve(strict=False)
    try:
        target.relative_to(skills_root)
    except ValueError:
        raise GateFailure("target", "Target must be inside the repo-local skills collection (skills/<skill-name>).")
    if target.parent != skills_root:
        raise GateFailure("target", "Target must be one direct repo-local skill directory under skills/<skill-name>.")
    ctx.result["target"] = target.relative_to(ctx.repo_root).as_posix()
    if not target.exists() or not target.is_dir():
        raise GateFailure("target", f"Target directory does not exist: {ctx.result['target']}")
    skill_file = target / "SKILL.md"
    if not skill_file.exists() or not skill_file.is_file():
        raise GateFailure("target", f"Target skill is missing SKILL.md: {skill_file.relative_to(ctx.repo_root).as_posix()}")
    ctx.target_dir = target
    ctx.target_rel = target.relative_to(ctx.repo_root).as_posix()
    _pass_gate(ctx, "target", "Target skill directory and SKILL.md exist.")


def _gate_skill_spec(ctx: ValidationContext) -> None:
    assert ctx.target_dir is not None
    checks = run_skill_spec_checks(ctx.target_dir)
    status, message = summarize_checks(checks)
    details = {"checks": [check.as_dict() for check in checks]}
    if status == "failed":
        raise GateFailure("skill_spec", message, details)
    if status == "warn":
        _warn_gate(ctx, "skill_spec", message, details)
        return
    _pass_gate(ctx, "skill_spec", message, details)


def _gate_eval_manifest(ctx: ValidationContext) -> None:
    assert ctx.target_dir is not None
    manifest_path = ctx.target_dir / "evals" / "manifest.json"
    if not manifest_path.exists():
        raise GateFailure("eval_manifest", f"Missing eval manifest: {manifest_path.relative_to(ctx.repo_root).as_posix()}")
    try:
        raw = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        raise GateFailure("eval_manifest", f"Invalid JSON in eval manifest: {exc}") from exc
    except OSError as exc:
        raise GateFailure("eval_manifest", f"Could not read eval manifest: {exc}") from exc

    asset_refs = _manifest_asset_refs(raw, manifest_path, ctx.target_dir, ctx.repo_root)
    try:
        manifest = load_manifest(manifest_path)
    except Exception as exc:
        raise GateFailure("eval_manifest", f"Manifest loader error: {exc}") from exc

    skill_name = manifest.skill.get("name")
    if skill_name != ctx.target_dir.name:
        raise GateFailure("eval_manifest", f"Manifest skill name must match target directory name: expected {ctx.target_dir.name}, got {skill_name!r}")
    skill_path = _resolve_manifest_path(manifest_path, manifest.skill.get("path"))
    expected_skill_path = (ctx.target_dir / "SKILL.md").resolve()
    if skill_path != expected_skill_path:
        got = str(skill_path) if skill_path else "missing"
        raise GateFailure("eval_manifest", f"Manifest skill path must resolve to target SKILL.md; got {got}")

    workflow = next((suite for suite in manifest.suites if suite.name == "workflow" and suite.type == "workflow"), None)
    if workflow is None:
        raise GateFailure("eval_manifest", "A workflow suite named 'workflow' with type 'workflow' is required.")
    if not workflow.cases:
        raise GateFailure("eval_manifest", "The workflow suite must be non-empty.")

    with_skill = manifest.configurations.get("with_skill")
    if with_skill is None:
        raise GateFailure("eval_manifest", "Manifest must declare a with_skill configuration.")
    harness = with_skill.get("harness")
    if harness != "pi":
        raise GateFailure("eval_manifest", "with_skill configuration must use a supported real harness: pi.")
    if with_skill.get("force_skill") is not True:
        raise GateFailure("eval_manifest", "with_skill configuration must have force-skill enabled.")

    regression = next((suite for suite in manifest.suites if suite.name == "regression" and suite.type == "regression"), None)
    ctx.manifest_info = ManifestValidation(
        manifest=manifest,
        raw=raw,
        manifest_path=manifest_path,
        workflow_suite=workflow.name,
        regression_suite=regression.name if regression else None,
        asset_refs=asset_refs,
        workflow_case_count=len(workflow.cases),
        regression_case_count=len(regression.cases) if regression else 0,
        with_skill_config=dict(with_skill),
    )
    if ctx.options.include_trigger:
        from tools.skill_eval.trigger import validate_trigger_suite
        try:
            trigger = manifest.suite("trigger")
            if trigger.type != "trigger" or _selected_harness(ctx) != "pi":
                raise ValueError("--include-trigger requires a trigger suite and the Pi harness.")
            validate_trigger_suite(manifest, trigger, _generated_trigger_configs(ctx))
        except (KeyError, ValueError) as exc:
            raise GateFailure("eval_manifest", f"Invalid trigger configuration: {exc}") from exc
    _pass_gate(
        ctx,
        "eval_manifest",
        "Eval manifest is structurally valid for skill_valid.",
        {"manifest": manifest_path.relative_to(ctx.repo_root).as_posix(), "asset_refs": asset_refs},
    )


def _manifest_asset_refs(raw: dict[str, Any], manifest_path: Path, target_dir: Path, repo_root: Path) -> list[str]:
    refs: list[str] = []
    for suite in raw.get("suites", ()):
        if not isinstance(suite, dict):
            continue
        for key in ("legacy_evals", "custom_grader"):
            if suite.get(key):
                path = _resolve_manifest_path(manifest_path, str(suite[key]))
                if path is None or not path.exists():
                    rel = _target_relative(path, target_dir, repo_root) if path else str(suite[key])
                    raise GateFailure("eval_manifest", f"Referenced {key} path does not exist: {rel}")
                refs.append(_target_relative(path, target_dir, repo_root))
        fixture = suite.get("fixture") if isinstance(suite.get("fixture"), dict) else {}
        if fixture.get("type") == "copy" and fixture.get("path"):
            path = _resolve_manifest_path(manifest_path, str(fixture["path"]))
            if path is None or not path.exists():
                rel = _target_relative(path, target_dir, repo_root) if path else str(fixture["path"])
                raise GateFailure("eval_manifest", f"Referenced copy fixture path does not exist: {rel}")
            refs.append(_target_relative(path, target_dir, repo_root))
    return sorted(dict.fromkeys(refs))


def _target_relative(path: Path, target_dir: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(target_dir).as_posix()
    except ValueError:
        return _display_path(path, repo_root)


def _resolve_manifest_path(manifest_path: Path, relative_or_absolute: str | None) -> Path | None:
    if not relative_or_absolute:
        return None
    path = Path(relative_or_absolute)
    if path.is_absolute():
        return path.resolve()
    return (manifest_path.parent / path).resolve()


def _gate_agents_md(ctx: ValidationContext) -> None:
    assert ctx.target_dir is not None
    path = ctx.target_dir / "AGENTS.md"
    if not path.exists():
        raise GateFailure("agents_md", f"Missing skill-local AGENTS.md: {path.relative_to(ctx.repo_root).as_posix()}")
    text = path.read_text()
    if not text.strip():
        raise GateFailure("agents_md", "Skill-local AGENTS.md is empty.")
    headings = {_normalize_heading(line) for line in text.splitlines() if _normalize_heading(line)}
    for required in REQUIRED_AGENT_HEADINGS:
        if required.lower() not in headings:
            raise GateFailure("agents_md", f"Skill-local AGENTS.md is missing required heading: {required}")
    manifest_asset_refs = ctx.manifest_info.asset_refs if ctx.manifest_info else []
    required_refs = ["SKILL.md", *manifest_asset_refs]
    if ctx.manifest_info:
        required_refs.append("evals/manifest.json")
    for ref in sorted(dict.fromkeys(required_refs)):
        if ref not in text:
            raise GateFailure("agents_md", f"Skill-local AGENTS.md is missing concrete reference: {ref}")
    _pass_gate(ctx, "agents_md", "Skill-local AGENTS.md includes required maintenance sections and references.")


def _normalize_heading(line: str) -> str | None:
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None
    text = stripped.lstrip("#").strip().rstrip("#").strip()
    return text.lower() if text else None


def _gate_llm_optimal_check(ctx: ValidationContext) -> None:
    assert ctx.target_dir is not None
    skill_path = ctx.target_dir / "SKILL.md"
    try:
        report = ctx.deps.llm_optimal_checker(skill_path)
    except Exception as exc:
        raise GateFailure(
            "llm_optimal_check",
            f"LLM Optimal Check tool error: {exc}",
            {"exception_type": type(exc).__name__},
        ) from exc

    if not isinstance(report, dict):
        raise GateFailure("llm_optimal_check", "LLM Optimal Check returned a non-object report.")
    status = report.get("status")
    details = {"report": _compact_llm_optimal_report(report)}
    score = report.get("score")
    finding_count = len(report.get("findings") or []) if isinstance(report.get("findings"), list) else 0
    if status == "pass":
        _pass_gate(ctx, "llm_optimal_check", f"LLM Optimal Check passed with score {score}.", details)
        return
    if status == "warn":
        _warn_gate(
            ctx,
            "llm_optimal_check",
            f"LLM Optimal Check returned warnings with score {score} and {finding_count} finding(s).",
            details,
        )
        return
    if status == "fail":
        raise GateFailure(
            "llm_optimal_check",
            f"LLM Optimal Check failed with score {score} and {finding_count} finding(s).",
            details,
        )
    raise GateFailure("llm_optimal_check", f"LLM Optimal Check returned unknown status: {status!r}", details)


def _compact_llm_optimal_report(report: dict[str, Any]) -> dict[str, Any]:
    metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else {}
    compact_metrics = {
        key: value
        for key, value in metrics.items()
        if key not in {"analyzed_preview", "body", "preview"}
    }
    findings = report.get("findings") if isinstance(report.get("findings"), list) else []
    return {
        "status": report.get("status"),
        "score": report.get("score"),
        "metrics": compact_metrics,
        "findings": findings,
    }


def _live_execution_allowed(ctx: ValidationContext) -> bool:
    return bool(
        ctx.options.allow_live
        or ctx.options.allow_live_pi
        or ctx.env.get("SKILL_EVAL_ALLOW_LIVE") == "1"
        or ctx.env.get("SKILL_EVAL_ALLOW_LIVE_PI") == "1"
    )


def _gate_live_opt_in(ctx: ValidationContext) -> None:
    harness = _selected_harness(ctx)
    if harness != "pi":
        raise GateFailure("live_opt_in", f"Unsupported live harness: {harness}")
    if _live_execution_allowed(ctx):
        _pass_gate(ctx, "live_opt_in", "Live harness execution is explicitly allowed.")
        return
    _pass_gate(ctx, "live_opt_in", "Live validation not enabled; deterministic validation only.")


def _gate_validate_skills(ctx: ValidationContext) -> None:
    assert ctx.target_rel is not None
    artifact_dir = ctx.artifacts.child("validate_skills") if ctx.artifacts else None
    command = build_validate_skills_command(ctx)
    harness = _selected_harness(ctx)
    env = dict(os.environ)
    env.update(ctx.env)
    started = time.time()
    try:
        completed = ctx.deps.run_harness(command, cwd=ctx.repo_root, env=env, timeout=ctx.options.validate_timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        stdout = _text_output(exc.stdout)
        stderr = _text_output(exc.stderr)
        if artifact_dir:
            _write_validate_artifacts(artifact_dir, stdout, stderr, command, None, started)
        raise GateFailure("validate_skills", f"validate-skills {harness} run timed out.") from exc
    if artifact_dir:
        _write_validate_artifacts(artifact_dir, completed.stdout, completed.stderr, command, completed.returncode, started)
    if completed.returncode != 0:
        raise GateFailure("validate_skills", f"validate-skills {harness} run exited nonzero: exit {completed.returncode}")
    parsed = parse_sentinel_result(completed.stdout, expected_target=ctx.target_rel)
    if not parsed.passed:
        raise GateFailure("validate_skills", parsed.message, {"sentinel": parsed.payload} if parsed.payload else None)
    _pass_gate(ctx, "validate_skills", "validate-skills sentinel result passed.", {"checks": parsed.payload.get("checks", []) if parsed.payload else []})


def _selected_harness(ctx: ValidationContext) -> str:
    if ctx.options.harness:
        return ctx.options.harness
    if ctx.manifest_info:
        return str(ctx.manifest_info.with_skill_config.get("harness", "pi"))
    return "pi"


def _harness_executable(ctx: ValidationContext, harness: str) -> str:
    if ctx.options.harness_executable:
        return ctx.options.harness_executable
    if harness == "pi":
        return ctx.options.pi_executable
    return harness


def _text_output(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value or ""


def build_validate_skills_command(ctx: ValidationContext) -> list[str]:
    assert ctx.target_rel is not None
    validate_skill_path = ctx.repo_root / "skill-factory" / "validate-skills" / "SKILL.md"
    prompt = render_wrapper_prompt(ctx.target_rel)
    harness = _selected_harness(ctx)
    executable = _harness_executable(ctx, harness)
    if harness != "pi":
        raise GateFailure("validate_skills", f"Unsupported live harness: {harness}")

    command = [
        executable,
        "--no-session",
        "--no-context-files",
        "--no-extensions",
        "--no-prompt-templates",
        "--no-skills",
        "--tools",
        "read,grep,find,ls",
        "--skill",
        str(validate_skill_path),
    ]
    if ctx.options.provider:
        command.extend(["--provider", ctx.options.provider])
    if ctx.options.model:
        command.extend(["--model", ctx.options.model])
    if ctx.options.thinking:
        command.extend(["--thinking", ctx.options.thinking])
    command.extend(["-p", prompt])
    return command


def render_wrapper_prompt(target_rel: str) -> str:
    wrapper_path = Path(__file__).with_name("WRAPPER_PROMPT.md")
    template = wrapper_path.read_text()
    return template.replace("{{TARGET_SKILL}}", target_rel)


def _write_validate_artifacts(path: Path, stdout: str, stderr: str, command: list[str], exit_code: int | None, started: float) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "stdout.txt").write_text(stdout)
    (path / "stderr.txt").write_text(stderr)
    (path / "command.json").write_text(
        json.dumps(
            {
                "command": command,
                "exit_code": exit_code,
                "started_at_unix": started,
                "finished_at_unix": time.time(),
            },
            indent=2,
            sort_keys=True,
        )
    )


def parse_sentinel_result(stdout: str, *, expected_target: str | None = None) -> SentinelParseResult:
    non_empty = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not non_empty:
        return SentinelParseResult(False, "Missing validate-skills sentinel line.")
    last = non_empty[-1]
    if not last.startswith(SENTINEL_PREFIX):
        if any(line.startswith(SENTINEL_PREFIX) for line in non_empty):
            return SentinelParseResult(False, "Sentinel line must be the final non-empty stdout line.")
        return SentinelParseResult(False, "Missing validate-skills sentinel line.")
    try:
        payload = json.loads(last[len(SENTINEL_PREFIX):])
    except json.JSONDecodeError as exc:
        return SentinelParseResult(False, f"Sentinel JSON is malformed: {exc}")
    if not isinstance(payload, dict):
        return SentinelParseResult(False, "Sentinel JSON must be an object.")
    for field_name in ("status", "target", "checks"):
        if field_name not in payload:
            return SentinelParseResult(False, f"Sentinel JSON is missing required field: {field_name}", payload)
    if expected_target is not None and payload.get("target") != expected_target:
        return SentinelParseResult(False, f"Sentinel target mismatch: expected {expected_target}, got {payload.get('target')}", payload)
    checks = payload.get("checks")
    if not isinstance(checks, list) or not checks:
        return SentinelParseResult(False, "Sentinel checks must be a non-empty array.", payload)
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            return SentinelParseResult(False, f"Sentinel check {index} must be an object.", payload)
        for field_name in ("id", "status", "message"):
            if field_name not in check:
                return SentinelParseResult(False, f"Sentinel check {index} is missing required field: {field_name}", payload)
    if payload.get("status") != "passed":
        return SentinelParseResult(False, f"Sentinel top-level status is not passed: {payload.get('status')}", payload)
    failed_checks = [check for check in checks if check.get("status") != "passed"]
    if failed_checks:
        ids = ", ".join(str(check.get("id")) for check in failed_checks)
        return SentinelParseResult(False, f"Sentinel check failed: {ids}", payload)
    return SentinelParseResult(True, "Sentinel result passed.", payload)


def _gate_live_eval(ctx: ValidationContext) -> None:
    assert ctx.manifest_info is not None
    artifact_dir = ctx.artifacts.child("skill_eval") if ctx.artifacts else None
    config = _generated_with_skill_config(ctx)
    required = [(ctx.manifest_info.workflow_suite, ctx.manifest_info.workflow_case_count, {"with_skill": dict(config)})]
    if ctx.manifest_info.regression_suite:
        required.append((ctx.manifest_info.regression_suite, ctx.manifest_info.regression_case_count, {"with_skill": dict(config)}))
    if ctx.options.include_trigger:
        trigger = ctx.manifest_info.manifest.suite("trigger")
        profiles = _generated_trigger_configs(ctx)
        required.append((trigger.name, len(trigger.cases) * len(profiles), profiles))
    summaries: list[dict[str, Any]] = []
    for suite_name, expected_cases, profiles in required:
        result_root = (artifact_dir / suite_name) if artifact_dir else Path(tempfile.mkdtemp(prefix=f"skill-valid-eval-{suite_name}-"))
        try:
            summary = ctx.deps.eval_runner(
                ctx.manifest_info.manifest_path,
                suite_name,
                result_root,
                profiles,
                require_real=True,
            )
        except Exception as exc:
            raise GateFailure("live_eval", f"skill_eval runner failed for {suite_name}: {exc}") from exc
        summaries.append(summary)
        _enforce_strict_real_run_success(summary, suite_name=suite_name, expected_cases=expected_cases,
                                       configurations=set(profiles))
        if suite_name == "trigger":
            expected = {(case.id, name) for case in trigger.cases for name in profiles}
            actual = [(run.get("case_id"), run.get("configuration")) for run in summary["runs"]]
            if len(actual) != len(expected) or set(actual) != expected:
                raise GateFailure("live_eval", "Trigger suite has duplicate, missing, or unexpected runs.")
    _pass_gate(ctx, "live_eval", "Live skill eval suites passed strict real-run success.", {"suites": [summary.get("suite") for summary in summaries]})


def _generated_with_skill_config(ctx: ValidationContext) -> dict[str, Any]:
    assert ctx.manifest_info is not None
    config = dict(ctx.manifest_info.with_skill_config)
    harness = _selected_harness(ctx)
    config.update({"harness": harness, "force_skill": True, "allow_live": True})
    if ctx.options.harness_executable:
        config["executable"] = ctx.options.harness_executable
    elif harness == "pi" and ctx.options.pi_executable != "pi":
        config["executable"] = ctx.options.pi_executable
    if ctx.options.provider:
        config["provider"] = ctx.options.provider
    if ctx.options.model:
        config["model"] = ctx.options.model
    if ctx.options.thinking:
        config["thinking"] = ctx.options.thinking
    return config


def _generated_trigger_configs(ctx: ValidationContext) -> dict[str, dict[str, Any]]:
    assert ctx.manifest_info is not None
    manifest = ctx.manifest_info.manifest
    configs = suite_configurations(manifest, manifest.suite("trigger"))
    result = {}
    for name, config in configs.items():
        profile = {**config, "allow_live": True}
        for field in ("provider", "model", "thinking"):
            if getattr(ctx.options, field):
                profile[field] = getattr(ctx.options, field)
        if ctx.options.harness_executable:
            profile["executable"] = ctx.options.harness_executable
        elif ctx.options.pi_executable != "pi":
            profile["executable"] = ctx.options.pi_executable
        result[name] = profile
    return result


def _enforce_strict_real_run_success(summary: dict[str, Any], *, suite_name: str, expected_cases: int,
                                   configurations: set[str] | None = None) -> None:
    if summary.get("status") != "completed":
        raise GateFailure("live_eval", f"Suite {suite_name} did not complete: {summary.get('status')}")
    runs = summary.get("runs")
    if not isinstance(runs, list):
        raise GateFailure("live_eval", f"Suite {suite_name} summary is missing runs.")
    if expected_cases > 0 and len(runs) < expected_cases:
        raise GateFailure("live_eval", f"Suite {suite_name} has missing runs: expected at least {expected_cases}, got {len(runs)}")
    for run in runs:
        case_id = run.get("case_id", "unknown") if isinstance(run, dict) else "unknown"
        if not isinstance(run, dict):
            raise GateFailure("live_eval", f"Suite {suite_name} contains a malformed run.")
        if run.get("configuration") not in (configurations or {"with_skill"}):
            raise GateFailure("live_eval", f"Suite {suite_name} run {case_id} did not use an expected configuration.")
        if run.get("synthetic") is True or run.get("harness_mode") != "real":
            raise GateFailure("live_eval", f"Suite {suite_name} run {case_id} is synthetic, not a strict real run.")
        if run.get("status") != "passed":
            raise GateFailure("live_eval", f"Suite {suite_name} run {case_id} process status is {run.get('status')}")
        if run.get("passed") is not True:
            raise GateFailure("live_eval", f"Suite {suite_name} run {case_id} content did not pass.")


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    deps: ValidationDependencies | None = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = argparse.ArgumentParser(description="Validate one repo-local skill through skill_valid gates.")
    parser.add_argument("target", type=Path, help="Repo-local skill directory, e.g. skills/custom-command")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root; defaults to current directory")
    parser.add_argument("--allow-live", action="store_true", help="Explicitly allow live harness/model calls")
    parser.add_argument("--allow-live-pi", action="store_true", help="Deprecated alias for --allow-live")
    parser.add_argument("--include-trigger", action="store_true", help="Also validate and, with live opt-in, execute the Pi trigger suite")
    parser.add_argument("--harness", choices=("pi",), help="Real harness override; defaults to manifest with_skill harness")
    parser.add_argument("--provider", help="Provider override for live harness gates")
    parser.add_argument("--model", help="Model override for live harness gates")
    parser.add_argument("--thinking", help="Thinking override for live harness gates")
    parser.add_argument("--artifact-base", type=Path, help="Directory for temporary child artifacts")
    parser.add_argument("--harness-executable", help="Executable override for selected live harness")
    parser.add_argument("--pi-executable", default="pi", help="Deprecated Pi executable override")
    args = parser.parse_args(argv)
    options = ValidationOptions(
        target=args.target,
        repo_root=args.repo_root,
        allow_live=args.allow_live,
        allow_live_pi=args.allow_live_pi,
        include_trigger=args.include_trigger,
        harness=args.harness,
        provider=args.provider,
        model=args.model,
        thinking=args.thinking,
        artifact_base=args.artifact_base,
        harness_executable=args.harness_executable,
        pi_executable=args.pi_executable,
    )
    code, result = validate_skill(options, deps=deps, stderr=stderr)
    stdout.write(json.dumps(result, separators=(",", ":"), sort_keys=True) + "\n")
    stdout.flush()
    return code


__all__ = [
    "GATE_ORDER",
    "SENTINEL_PREFIX",
    "SentinelParseResult",
    "ValidationDependencies",
    "ValidationOptions",
    "build_validate_skills_command",
    "main",
    "parse_sentinel_result",
    "render_wrapper_prompt",
    "validate_skill",
]
