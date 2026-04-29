from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .manifest import EvalSuite


def write_reports(
    *,
    result_root: Path,
    skill_name: str,
    suite: EvalSuite,
    runs: list[dict[str, Any]],
) -> dict[str, Any]:
    benchmark = build_benchmark(skill_name=skill_name, suite=suite, runs=runs)
    result_root.mkdir(parents=True, exist_ok=True)
    (result_root / "benchmark.json").write_text(json.dumps(benchmark, indent=2, sort_keys=True))
    (result_root / "report.md").write_text(render_report(benchmark))
    return benchmark


def build_benchmark(*, skill_name: str, suite: EvalSuite, runs: list[dict[str, Any]]) -> dict[str, Any]:
    configurations: dict[str, dict[str, Any]] = {}
    cases: dict[str, dict[str, Any]] = {
        case.id: {"id": case.id, "prompt": case.prompt, "configurations": {}} for case in suite.cases
    }

    for run in runs:
        config_name = run["configuration"]
        config = configurations.setdefault(config_name, _empty_config_summary())
        config["total"] += 1
        run_status = str(run.get("status") or "unknown")
        config["status_counts"][run_status] = config["status_counts"].get(run_status, 0) + 1
        if run.get("passed") is True:
            config["passed"] += 1
        elif run.get("passed") is False:
            config["failed"] += 1
        else:
            config["not_graded"] += 1
        config["elapsed_ms"] += run.get("elapsed_ms") or 0
        config["harness_mode"] = run.get("harness_mode") or config.get("harness_mode")
        config["synthetic"] = bool(run.get("synthetic")) or config.get("synthetic", False)
        config["metric_provenance"] = run.get("metric_provenance") or config.get("metric_provenance", {})
        config["model"] = run.get("model") or config.get("model")
        config["provider"] = run.get("provider") or config.get("provider")
        usage = run.get("usage") or {}
        config["usage"]["input_chars"] += usage.get("input_chars") or 0
        config["usage"]["output_chars"] += usage.get("output_chars") or 0

        cases.setdefault(run["case_id"], {"id": run["case_id"], "prompt": run.get("prompt", ""), "configurations": {}})
        cases[run["case_id"]]["configurations"][config_name] = {
            "status": run.get("status"),
            "passed": run.get("passed"),
            "elapsed_ms": run.get("elapsed_ms"),
            "usage": usage,
            "run_dir": run.get("run_dir"),
            "grade_summary": run.get("grade_summary"),
        }

    for config in configurations.values():
        total = config["total"]
        config["pass_rate"] = config["passed"] / total if total else 0.0
        config["avg_elapsed_ms"] = config["elapsed_ms"] / total if total else 0.0

    comparison = _comparison(configurations)
    return {
        "skill": skill_name,
        "suite": suite.name,
        "suite_type": suite.type,
        "configurations": configurations,
        "comparison": comparison,
        "cases": cases,
    }


def render_report(benchmark: dict[str, Any]) -> str:
    lines = [
        f"# Skill eval report: {benchmark['skill']} / {benchmark['suite']}",
        "",
    ]
    if any(config.get("synthetic") for config in benchmark["configurations"].values()):
        lines.extend([
            "> **Synthetic/static results warning:** at least one configuration used a static or replay harness. Treat pass rates, timings, and usage as smoke-test plumbing signals, not behavioral benchmark evidence.",
            "",
        ])
    lines.extend([
        "## Configuration summary",
        "",
        "| Configuration | Harness mode | Synthetic | Pass rate | Passed | Failed | Not graded | Avg time (ms) | Input chars | Output chars |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for name, config in benchmark["configurations"].items():
        lines.append(
            f"| {name} | {config.get('harness_mode') or 'unknown'} | {config.get('synthetic')} | "
            f"{config['pass_rate']:.2f} | {config['passed']} | {config['failed']} | {config['not_graded']} | "
            f"{config['avg_elapsed_ms']:.3f} | {config['usage']['input_chars']} | {config['usage']['output_chars']} |"
        )
    lines.extend([
        "",
        "Pass rate is passed runs divided by total runs for that configuration; inspect Failed, Not graded, and per-run Status before interpreting it as content quality.",
        "",
        "Token metrics are unavailable when the harness does not report provider token usage; character counts are shown separately and must not be treated as tokens.",
        "",
        "## Metric provenance",
        "",
    ])
    for name, config in benchmark["configurations"].items():
        provenance = config.get("metric_provenance") or {}
        lines.append(
            f"- `{name}`: pass_rate={provenance.get('pass_rate', 'unknown')}; "
            f"timing={provenance.get('timing', 'unknown')}; usage={provenance.get('usage', 'unknown')}"
        )
    lines.extend(["", "## Comparison", ""])
    comparison = benchmark["comparison"]
    if comparison:
        lines.extend([
            f"- Baseline: `{comparison['baseline']}`",
            f"- Candidate: `{comparison['candidate']}`",
        ])
        if comparison.get("caveat"):
            lines.append(f"- Comparison caveat: {comparison['caveat']}")
        lines.extend([
            f"- Pass-rate delta: `{comparison['pass_rate_delta']:.2f}`",
            f"- Elapsed-ms delta: `{comparison['elapsed_ms_delta']:.3f}`",
            f"- Usage delta: input `{comparison['usage_delta']['input_chars']}`, output `{comparison['usage_delta']['output_chars']}`",
        ])
    else:
        lines.append("No comparison available.")
    lines.extend(["", "## Cases", ""])
    for case_id, case in benchmark["cases"].items():
        lines.extend([
            f"### Case {case_id}",
            "",
            f"Prompt: {case['prompt']}",
            "",
            "| Configuration | Status | Passed | Time (ms) | Grade |",
            "| --- | --- | ---: | ---: | --- |",
        ])
        for config_name, run in case["configurations"].items():
            lines.append(
                f"| {config_name} | {run.get('status') or 'unknown'} | {run['passed']} | {run['elapsed_ms']:.3f} | {run.get('grade_summary') or ''} |"
            )
        lines.append("")
    return "\n".join(lines)


def _empty_config_summary() -> dict[str, Any]:
    return {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "not_graded": 0,
        "status_counts": {},
        "elapsed_ms": 0.0,
        "avg_elapsed_ms": 0.0,
        "pass_rate": 0.0,
        "usage": {"input_chars": 0, "output_chars": 0},
        "harness_mode": None,
        "synthetic": False,
        "metric_provenance": {},
        "model": None,
        "provider": None,
    }


def _comparison(configurations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if "without_skill" in configurations and "with_skill" in configurations:
        baseline_name = "without_skill"
        candidate_name = "with_skill"
    else:
        names = list(configurations)
        if len(names) < 2:
            return {}
        baseline_name, candidate_name = names[0], names[1]

    baseline = configurations[baseline_name]
    candidate = configurations[candidate_name]
    comparable = True
    caveats: list[str] = []
    if baseline.get("synthetic") or candidate.get("synthetic"):
        comparable = False
        caveats.append("synthetic or replayed harness metrics are smoke-test signals, not behavioral benchmark evidence")
    if baseline.get("harness_mode") != candidate.get("harness_mode"):
        comparable = False
        caveats.append("harness modes differ")
    return {
        "baseline": baseline_name,
        "candidate": candidate_name,
        "comparable": comparable,
        "caveat": "; ".join(caveats) if caveats else None,
        "pass_rate_delta": candidate["pass_rate"] - baseline["pass_rate"],
        "elapsed_ms_delta": candidate["avg_elapsed_ms"] - baseline["avg_elapsed_ms"],
        "usage_delta": {
            "input_chars": candidate["usage"]["input_chars"] - baseline["usage"]["input_chars"],
            "output_chars": candidate["usage"]["output_chars"] - baseline["usage"]["output_chars"],
        },
    }
