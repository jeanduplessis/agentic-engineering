"""Pi natural-discovery probes: frozen inputs and evidence-based selection grades.

This is a read-only, target-only profile, not a workflow executor or an OS sandbox.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .manifest import EvalManifest, EvalSuite

OBSERVER = Path(__file__).resolve().parents[3] / "harness/pi/extensions/skill-eval-observer/index.ts"
PROFILE = "pi-target-only-read-v1"


def validate_trigger_suite(manifest: EvalManifest, suite: EvalSuite, configs: dict[str, dict[str, Any]]) -> None:
    if suite.mode != "natural":
        raise ValueError("Trigger suites require mode: natural.")
    if not suite.cases or not configs:
        raise ValueError("Trigger suites require cases and discovery configurations.")
    name = manifest.skill.get("name")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError("Trigger target needs a valid skill name.")
    source = manifest.skill.get("path")
    if not source or not resolve_path(manifest, source).is_file():
        raise ValueError("Trigger target skill.path must resolve to a file.")
    ids = [case.id for case in suite.cases]
    if len(set(ids)) != len(ids):
        raise ValueError("Trigger case IDs must be unique.")
    for identifier in [suite.name, *ids, *configs]:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", identifier):
            raise ValueError(f"Unsafe trigger identifier: {identifier!r}")
    for case in suite.cases:
        metadata = case.metadata or {}
        if type(metadata.get("should_trigger")) is not bool:
            raise ValueError(f"{case.id}: should_trigger must be a boolean.")
        expected = metadata.get("expected_skill")
        if expected not in (None, name) or (not metadata["should_trigger"] and expected is not None):
            raise ValueError(f"{case.id}: expected_skill must describe the manifest target, not another skill.")
        if not isinstance(case.prompt, str) or not case.prompt.strip() or case.prompt.lstrip().startswith(("/", "@")):
            raise ValueError(f"{case.id}: trigger prompts must be ordinary tasks, not commands or attachments.")
        if case.files:
            raise ValueError("Trigger file inputs must use a copy fixture, not the legacy files field.")
        if case.checks or case.expected_output or case.expectations or case.subjective_checks or suite.custom_grader:
            raise ValueError("Trigger suites grade selection only; keep output checks in workflow suites.")
    for config in configs.values():
        if config.get("harness") != "pi":
            raise ValueError("Trigger execution supports Pi only (no static/replay or Kilo probes).")
        if "force_skill" in config:
            raise ValueError("Trigger configurations must omit force_skill; the target is always discoverable.")
        if "allow_live" in config and type(config["allow_live"]) is not bool:
            raise ValueError("Trigger allow_live must be a boolean, not a truthy string.")
        if not isinstance(config.get("env", {}), dict):
            raise ValueError("Trigger env must be an object.")
        unknown = config.keys() - {"harness", "executable", "allow_live", "provider", "model", "thinking", "env", "timeout_seconds", "extensions"}
        if unknown:
            raise ValueError(f"Unsupported trigger configuration fields: {', '.join(sorted(unknown))}")
        timeout = float(config.get("timeout_seconds", 120))
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Trigger timeout_seconds must be positive and finite.")
        extensions = config.get("extensions", [])
        if not isinstance(extensions, list) or any(not isinstance(p, str) for p in extensions):
            raise ValueError("Trigger extensions must be a list of local entry-point paths.")
        for extension in extensions:
            if not resolve_path(manifest, extension).is_file():
                raise ValueError(f"Trigger extension is not a local file: {extension}")


def resolve_path(manifest: EvalManifest, value: str) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else manifest.path.parent / path).resolve()


def freeze_trigger_inputs(manifest: EvalManifest, suite: EvalSuite, configs: dict[str, dict[str, Any]], root: Path) -> dict[str, Any]:
    """Called once before execution, including no-live runs; never overwrite prior evidence."""
    inputs = root / "input"
    inputs.mkdir()
    source = resolve_path(manifest, manifest.skill["path"])
    skill = inputs / manifest.skill["name"] / "SKILL.md"
    skill.parent.mkdir()
    skill.write_bytes(source.read_bytes())
    fixture = dict(suite.fixture)
    if fixture.get("type", "empty") == "copy":
        fixture_source = resolve_path(manifest, fixture["path"])
        if root.is_relative_to(fixture_source):
            raise ValueError("Trigger results must be outside the source fixture.")
        if any(p.is_symlink() for p in fixture_source.rglob("*")):
            raise ValueError("Trigger fixtures must not contain symlinks.")
        destination = inputs / "fixture"
        shutil.copytree(fixture_source, destination)
        fixture["path"] = str(destination)
    elif fixture.get("type", "empty") != "empty":
        raise ValueError("Trigger fixtures support only empty or copy.")
    cases = [{"id": c.id, "prompt": c.prompt, "should_trigger": c.metadata["should_trigger"]} for c in suite.cases]
    (inputs / "cases.json").write_text(json.dumps(cases, indent=2) + "\n")
    profiles = {}
    for name, config in configs.items():
        extensions = [resolve_path(manifest, p) for p in config.get("extensions", [])]
        profiles[name] = {
            **{key: config[key] for key in ("provider", "model", "thinking", "timeout_seconds") if key in config},
            "extensions": [{"path": str(p), "sha256": digest(p)} for p in extensions],
        }
    plan = {
        "profile": PROFILE, "skill_name": manifest.skill["name"], "skill_path": str(skill),
        "source_skill_path": str(source), "skill_sha256": digest(skill), "fixture": fixture,
        "observer": {"path": str(OBSERVER), "sha256": digest(OBSERVER)},
        "configurations": profiles, "process_run_count": len(cases) * len(configs),
        "input_hashes": {str(p.relative_to(inputs)): digest(p) for p in sorted(inputs.rglob("*")) if p.is_file()},
    }
    # Environment values (possibly credentials) are deliberately not serialized.
    (root / "plan.json").write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    return plan


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs_unchanged(plan: dict[str, Any], config_name: str) -> bool:
    inputs = Path(plan["skill_path"]).parents[1]
    resources = [(inputs / path, sha) for path, sha in plan["input_hashes"].items()]
    resources.extend((Path(item["path"]), item["sha256"])
                     for item in [plan["observer"], *plan["configurations"][config_name]["extensions"]])
    try:
        return all(path.is_file() and digest(path) == sha for path, sha in resources)
    except OSError:
        return False


def trigger_command(command: list[str], plan: dict[str, Any], config_name: str,
                    sandbox: Path, run_dir: Path) -> tuple[list[str], dict[str, str]]:
    observer_config = run_dir / "observer-config.json"
    observer_config.write_text(json.dumps({"skill_path": plan["skill_path"], "workspace": str(sandbox),
                                           "context_path": str(run_dir / "observer-context.jsonl")}))
    command += ["--mode", "json", "--tools", "read", "--no-approve", "--offline",
                "--system-prompt", "", "--append-system-prompt", ""]
    for extension in plan["configurations"][config_name]["extensions"]:
        command += ["--extension", extension["path"]]
    command += ["--extension", str(OBSERVER), "--skill", plan["skill_path"]]
    return command, {"SKILL_EVAL_OBSERVER_CONFIG": str(observer_config), "PI_OFFLINE": "1"}


def inspect_trigger_trace(stdout: str, *, plan: dict[str, Any], sandbox: Path,
                          config: dict[str, Any], observer_output: str = "") -> dict[str, Any]:
    """Only authoritative message/tool events count. Missing evidence fails closed."""
    events: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    errors: list[str] = []
    # Keep native events separate from observer evidence; extension stdout is redirected by Pi.
    # JSONL is LF-delimited: splitlines() corrupts valid JSON containing U+2028/U+2029.
    for stream, destination, expected_type in ((stdout, events, None), (observer_output, contexts, "skill_eval_context")):
        for line in stream.split("\n"):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if not isinstance(event, dict) or not isinstance(event.get("type"), str):
                    raise ValueError("not an event object")
                if expected_type and event["type"] != expected_type:
                    raise ValueError("unexpected observer event")
                destination.append(event)
            except (ValueError, TypeError):
                errors.append("malformed_observer_event" if expected_type else "malformed_json_event")
    target = Path(plan["skill_path"]).resolve()
    advertised = False
    observed_model = observed_provider = None
    if len(contexts) != 1:
        errors.append("missing_or_repeated_context_observation")
    else:
        context = contexts[0]
        observed_model, observed_provider = context.get("model"), context.get("provider")
        try:
            catalogs = context["catalogs"]
            if context.get("version") != 1 or len(catalogs) != 1:
                raise ValueError("catalog")
            catalog = ET.fromstring(catalogs[0])
            skills = catalog.findall("skill")
            if (catalog.tag != "available_skills" or len(skills) != 1
                    or skills[0].findtext("name") != plan["skill_name"]
                    or Path(skills[0].findtext("location", "")).resolve() != target
                    or not skills[0].findtext("description", "").strip()):
                raise ValueError("target catalog")
            if context.get("tools") != ["read"] or context.get("read_source") != "builtin":
                raise ValueError("tools")
            if not observed_model or not observed_provider:
                raise ValueError("model identity")
            for field in ("model", "provider", "thinking"):
                if config.get(field) and context.get(field) != config[field]:
                    raise ValueError(f"{field} mismatch")
            advertised = True
        except (ValueError, TypeError, KeyError, AttributeError, ET.ParseError):
            errors.append("invalid_catalog_or_execution_profile")
    starts = sum(e["type"] == "agent_start" for e in events)
    ends = sum(e["type"] == "agent_end" for e in events)
    if starts != 1 or ends != 1:
        errors.append("incomplete_or_retried_agent_run")
    calls: dict[str, dict[str, Any]] = {}
    requested: dict[str, dict[str, Any]] = {}
    tool_results: set[str] = set()
    completed: set[str] = set()
    attempts: list[str] = []
    reads: list[str] = []
    texts: list[str] = []
    messages: list[dict[str, Any]] = []
    normalized: list[dict[str, Any]] = []
    ended = False
    for event in events:
        kind = event["type"]
        if ended and kind in {"message_end", "tool_execution_start", "tool_execution_end"}:
            errors.append("events_after_agent_end")
        if kind == "agent_end":
            ended = True
        if kind == "tool_execution_start":
            call_id = event.get("toolCallId")
            args = event.get("args")
            if not isinstance(call_id, str) or call_id in calls or event.get("toolName") != "read" or not isinstance(args, dict):
                errors.append("invalid_tool_start")
                continue
            path = args.get("path")
            if not isinstance(path, str):
                errors.append("invalid_read_path")
                continue
            try:
                resolved = Path(path.removeprefix("@")).expanduser()
                resolved = (resolved if resolved.is_absolute() else sandbox / resolved).resolve()
            except (OSError, RuntimeError, ValueError):
                errors.append("invalid_read_path")
                continue
            calls[call_id] = {"target": resolved == target, "args": args}
            if resolved == target:
                attempts.append(call_id)
                normalized.append({"event": "skill_read_attempted", "tool_call_id": call_id, "path": str(target)})
        if kind == "tool_execution_end":
            call_id = event.get("toolCallId")
            if not isinstance(call_id, str) or call_id not in calls or call_id in completed or event.get("toolName") != "read" or type(event.get("isError")) is not bool:
                errors.append("unmatched_or_invalid_tool_end")
                continue
            completed.add(call_id)
            content = event.get("result", {}).get("content", []) if isinstance(event.get("result"), dict) else []
            delivered = isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str) and b["text"].strip() for b in content)
            if calls[call_id]["target"]:
                success = not event["isError"] and delivered
                if success:
                    reads.append(call_id)
                normalized.append({"event": "skill_read_finished", "tool_call_id": call_id, "succeeded": success})
        if kind == "message_end":
            message = event.get("message")
            if not isinstance(message, dict):
                errors.append("invalid_message")
                continue
            if message.get("role") == "toolResult":
                call_id = message.get("toolCallId")
                if not isinstance(call_id, str) or call_id not in completed or call_id in tool_results:
                    errors.append("invalid_tool_result_message")
                else:
                    tool_results.add(call_id)
            if message.get("role") == "assistant":
                messages.append(message)
                if message.get("model") != observed_model or message.get("provider") != observed_provider:
                    errors.append("assistant_model_identity_mismatch")
                if message.get("stopReason") not in ("stop", "toolUse") or message.get("errorMessage"):
                    errors.append("assistant_error_or_truncation")
                content = message.get("content")
                if not isinstance(content, list):
                    errors.append("invalid_assistant_content")
                    continue
                texts.extend(b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str))
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "toolCall":
                        call_id = block.get("id")
                        if not isinstance(call_id, str) or call_id in requested or block.get("name") != "read" or not isinstance(block.get("arguments"), dict):
                            errors.append("invalid_assistant_tool_call")
                        else:
                            requested[call_id] = block["arguments"]
    if set(calls) != completed or set(calls) != set(requested) or completed != tool_results:
        errors.append("incomplete_tool_execution")
    if any(requested[call_id] != calls[call_id]["args"] for call_id in requested.keys() & calls.keys()):
        errors.append("tool_arguments_mismatch")
    if not messages or messages[-1].get("stopReason") != "stop" or not any(text.strip() for text in texts):
        errors.append("missing_completed_assistant_response")
    return {
        "valid": not errors, "errors": sorted(set(errors)), "advertised": advertised,
        "attempted": bool(attempts), "loaded": bool(reads), "attempt_call_ids": attempts,
        "successful_call_ids": reads, "response": "\n\n".join(texts), "events": normalized,
        "model": observed_model, "provider": observed_provider,
        "context": contexts[0] if len(contexts) == 1 else None,
    }


def grade_trigger(observation: dict[str, Any], should_trigger: bool) -> dict[str, Any]:
    if not observation["valid"]:
        outcome, passed = "invalid", None
    elif should_trigger and observation["attempted"] and not observation["loaded"]:
        outcome, passed = "load_error", None
    elif should_trigger:
        outcome = "true_positive" if observation["loaded"] else "false_negative"
        passed = observation["loaded"]
    else:
        outcome = "false_positive" if observation["attempted"] else "true_negative"
        passed = not observation["attempted"]
    return {
        "status": "not_graded" if passed is None else "graded", "passed": passed,
        "summary": f"Trigger: {outcome}", "outcome": outcome,
        "checks": [{"id": "target_selection", "type": "trigger", "status": "skipped" if passed is None else "passed" if passed else "failed",
                    "passed": passed, "evidence": {"should_trigger": should_trigger, **{k: observation[k] for k in ("advertised", "attempted", "loaded", "errors")}}}],
        "totals": {"passed": int(passed is True), "failed": int(passed is False), "skipped": int(passed is None)},
        "judge": {"status": "skipped", "reason": "deterministic_trigger_selection", "metadata": None,
                  "subjective_checks": [], "results": []},
    }
