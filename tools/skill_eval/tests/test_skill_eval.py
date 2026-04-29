import json
import tempfile
import unittest
from pathlib import Path

from tools.skill_eval.grading import grade_response
from tools.skill_eval.manifest import load_manifest
from tools.skill_eval.regression import promote_failures_to_regression_cases
from tools.skill_eval.runner import run_suite
from tools.skill_eval.sandbox import create_sandbox


class SkillEvalSmokeTests(unittest.TestCase):
    def test_custom_command_skill_and_eval_contracts_clarify_artifacts_and_nested_fences(self):
        skill = Path("skills/custom-command/SKILL.md").read_text()
        evals = json.loads(Path("skills/custom-command/evals/evals.json").read_text())
        prompts = "\n".join(case["prompt"] for case in evals["evals"])

        self.assertIn("Unless the user explicitly asks you to write or install files", skill)
        self.assertIn("When rewriting an existing agent-specific command into one shared file", skill)
        self.assertIn("remove `agent`, `model`, and `subtask` from the emitted frontmatter", skill)
        self.assertIn("Do not merely mention these fields in the audit and then keep them", skill)
        self.assertIn("four-backtick outer fence", skill)
        self.assertIn("You may either return the complete Markdown command contents or write the command file", prompts)
        self.assertIn("If you write a file, summarize the path", prompts)

    def test_skill_eval_documentation_covers_real_workflow_and_caveats(self):
        doc = Path("tools/skill_eval/README.md").read_text()
        agent_doc = Path("tools/skill_eval/AGENTS.md").read_text()

        self.assertIn("## Overview", doc)
        self.assertIn("## Quick usage", doc)
        self.assertIn("manifest suites", doc)
        self.assertIn("harness modes", doc)
        self.assertIn("with_skill", doc)
        self.assertIn("without_skill", doc)
        self.assertIn("regression", doc)
        self.assertIn("static smoke", doc)
        self.assertIn("--require-real", doc)
        self.assertIn("SKILL_EVAL_ALLOW_LIVE_PI=1", doc)
        self.assertIn("grade.json", doc)
        self.assertIn("artifact_manifest.json", doc)
        self.assertIn("process failures are not graded", doc.lower())
        self.assertIn("promote-regressions", doc)
        self.assertIn("trustworthy enough to compare skill versions", doc)
        self.assertIn("Treat static and replay harnesses as synthetic", agent_doc)
        self.assertIn("Regression suites run through the same case runner as workflow suites", agent_doc)

    def test_custom_command_manifest_maps_legacy_eval_data_to_workflow_suite(self):
        manifest = load_manifest(Path("skills/custom-command/evals/manifest.json"))
        suite = manifest.suite("workflow")

        self.assertEqual(manifest.skill["name"], "custom-command")
        self.assertEqual(suite.type, "workflow")
        self.assertEqual(suite.fixture["type"], "empty")
        self.assertEqual(len(suite.cases), 5)
        self.assertEqual(suite.cases[0].id, "1")
        self.assertIn("fix-tests", suite.cases[0].prompt)
        self.assertIn("complete portable Markdown command", suite.cases[0].expected_output)
        self.assertIn("$ARGUMENTS", "\n".join(suite.cases[0].expectations))
        self.assertIn("agent and model", "\n".join(suite.cases[1].expectations))
        self.assertIn("optional coverage command or focus area", suite.cases[1].prompt)
        self.assertIn("$ARGUMENTS", "\n".join(suite.cases[1].expectations))

    def test_eval_cases_keep_subjective_checks_separate_and_judge_is_optional(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "skill": {"name": "demo", "path": "skills/demo/SKILL.md"},
                        "suites": [
                            {
                                "name": "workflow",
                                "type": "workflow",
                                "fixture": {"type": "empty"},
                                "cases": [
                                    {
                                        "id": "subjective",
                                        "prompt": "Write a helpful answer",
                                        "checks": [{"type": "required_content", "value": "helpful"}],
                                        "subjective_checks": [
                                            {"id": "tone", "rubric": "Answer should be warm and concise."}
                                        ],
                                    },
                                    {
                                        "id": "deterministic",
                                        "prompt": "Say helpful",
                                        "checks": [{"type": "required_content", "value": "helpful"}],
                                    },
                                ],
                            }
                        ],
                    }
                )
            )

            manifest = load_manifest(manifest_path)
            self.assertEqual(manifest.suite("workflow").cases[0].subjective_checks[0]["id"], "tone")
            self.assertEqual(manifest.suite("workflow").cases[1].subjective_checks, ())

            run_suite(
                manifest_path,
                "workflow",
                root / "results",
                configurations={"default": {"harness": "static", "response": "helpful"}},
            )
            subjective_grade = json.loads((root / "results" / "demo" / "workflow" / "subjective" / "default" / "grade.json").read_text())
            deterministic_grade = json.loads((root / "results" / "demo" / "workflow" / "deterministic" / "default" / "grade.json").read_text())

            self.assertEqual(subjective_grade["judge"]["status"], "not_run")
            self.assertEqual(subjective_grade["judge"]["reason"], "no_judge_configured")
            self.assertEqual(subjective_grade["judge"]["subjective_checks"][0]["id"], "tone")
            self.assertEqual(deterministic_grade["judge"]["status"], "skipped")
            self.assertEqual(deterministic_grade["judge"]["reason"], "no_subjective_checks")
            self.assertEqual(deterministic_grade["judge"]["results"], [])

    def test_manifest_loader_reads_fixtureless_workflow_suite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "skill": {"name": "demo", "path": "skills/demo/SKILL.md"},
                        "suites": [
                            {
                                "name": "smoke",
                                "type": "workflow",
                                "fixture": {"type": "empty"},
                                "cases": [
                                    {
                                        "id": "hello",
                                        "prompt": "Say hello",
                                        "expected_output": "hello",
                                    }
                                ],
                            }
                        ],
                    }
                )
            )

            manifest = load_manifest(manifest_path)

            self.assertEqual(manifest.skill["name"], "demo")
            self.assertEqual(manifest.suites[0].name, "smoke")
            self.assertEqual(manifest.suites[0].cases[0].id, "hello")
            self.assertEqual(manifest.suites[0].fixture["type"], "empty")

    def test_copy_fixture_paths_are_resolved_relative_to_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            eval_dir = root / "evals"
            fixture_dir = eval_dir / "fixtures" / "project"
            fixture_dir.mkdir(parents=True)
            (fixture_dir / "README.md").write_text("fixture file")
            manifest_path = eval_dir / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "skill": {"name": "demo", "path": "../skill/SKILL.md"},
                        "suites": [
                            {
                                "name": "workflow",
                                "type": "workflow",
                                "fixture": {"type": "copy", "path": "fixtures/project"},
                                "cases": [{"id": "hello", "prompt": "Say hello", "checks": [{"type": "required_content", "value": "hello"}]}],
                            }
                        ],
                    }
                )
            )

            run_suite(
                manifest_path,
                "workflow",
                root / "results",
                configurations={"default": {"harness": "static", "response": "hello"}},
            )

            metadata = json.loads((root / "results" / "demo" / "workflow" / "hello" / "default" / "metadata.json").read_text())
            sandbox = Path(metadata["sandbox"])
            self.assertEqual((sandbox / "README.md").read_text(), "fixture file")

    def test_generic_deterministic_grader_supports_content_regex_and_structured_checks(self):
        grade = grade_response(
            '{"name": "fix-tests", "body": "Use $ARGUMENTS and never use model frontmatter"}',
            [
                {"type": "required_content", "value": "$ARGUMENTS"},
                {"type": "forbidden_content", "value": "subtask:"},
                {"type": "regex", "pattern": r'"name"\s*:\s*"fix-tests"'},
                {"type": "json_field_equals", "path": "name", "value": "fix-tests"},
            ],
        )

        self.assertTrue(grade["passed"])
        self.assertEqual(grade["totals"], {"passed": 4, "failed": 0, "skipped": 0})
        self.assertTrue(all("evidence" in check for check in grade["checks"]))

    def test_custom_command_skill_local_grader_checks_markdown_contract(self):
        response = """Filename: `fix-tests.md`

```markdown
---
description: "Fix tests"
---

Run tests from: $ARGUMENTS
```
"""

        grade = grade_response(
            response,
            [],
            custom_grader="skills/custom-command/evals/grader.py",
        )

        self.assertTrue(grade["passed"])
        check_ids = {check["id"] for check in grade["checks"]}
        self.assertIn("custom-command.markdown_frontmatter", check_ids)
        self.assertIn("custom-command.arguments", check_ids)

    def test_custom_command_grader_prefers_generated_markdown_artifacts(self):
        manifest = load_manifest(Path("skills/custom-command/evals/manifest.json"))
        suite = manifest.suite("workflow")
        case = suite.cases[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "fix-tests.md"
            artifact.write_text(
                "---\n"
                "description: \"Run tests and fix failures\"\n"
                "argument-hint: \"[test command or focus area]\"\n"
                "---\n\n"
                "Run tests and diagnose failures. User input: $ARGUMENTS\n"
            )
            grade = grade_response(
                "Created fix-tests.md in the current directory. Install paths: .opencode/commands/fix-tests.md and .pi/prompts/fix-tests.md.",
                case.checks,
                custom_grader=str(Path("skills/custom-command/evals") / suite.custom_grader),
                case=case,
                context={
                    "sandbox_path": str(root),
                    "artifact_manifest": {"files": [{"path": "fix-tests.md", "change": "added"}]},
                },
            )

        self.assertTrue(grade["passed"])
        artifact_checks = [check for check in grade["checks"] if check["id"] == "custom-command.artifact_source"]
        self.assertEqual(artifact_checks[0]["details"]["path"], "fix-tests.md")

    def test_custom_command_grader_handles_text_fences_nested_fences_and_recommended_filename(self):
        manifest = load_manifest(Path("skills/custom-command/evals/manifest.json"))
        suite = manifest.suite("workflow")
        case = suite.cases[1]
        response = '''Recommended filename:

```text
analyze-coverage.md
```

Compatible Markdown contents:

````markdown
---
description: "Analyze coverage"
---

Run the coverage command and analyze the results.

Arguments: $ARGUMENTS

If no command is supplied, run:

```sh
npm test -- --coverage
```
````
'''

        grade = grade_response(
            response,
            case.checks,
            custom_grader=str(Path("skills/custom-command/evals") / suite.custom_grader),
            case=case,
        )

        self.assertTrue(grade["passed"])
        self.assertFalse(any(check["status"] == "failed" for check in grade["checks"]))

    def test_custom_command_structured_checks_grade_generated_artifact_not_legacy_prose(self):
        manifest = load_manifest(Path("skills/custom-command/evals/manifest.json"))
        suite = manifest.suite("workflow")
        case = suite.cases[0]
        response = """Here is the command.

Filename: `fix-tests.md`

```markdown
---
description: "Run and fix tests"
---

Run the relevant test suite. If the user supplied an optional test command or focus area in $ARGUMENTS, use that first. Diagnose failures, make the smallest safe fix, and rerun tests.
```

Install it at `.opencode/commands/fix-tests.md` and `.pi/prompts/fix-tests.md`.
"""

        grade = grade_response(
            response,
            case.checks,
            custom_grader=str(Path("skills/custom-command/evals") / suite.custom_grader),
            case=case,
        )

        check_ids = {check["id"] for check in grade["checks"]}
        self.assertTrue(grade["passed"])
        self.assertNotIn(case.expected_output, response)
        self.assertFalse(any(check_id.startswith("legacy_expectation_") for check_id in check_ids))
        self.assertIn("custom-command.filename", check_ids)
        self.assertIn("custom-command.install_paths", check_ids)

        bad_grade = grade_response(
            response.replace('description: "Run and fix tests"', 'description: "Run and fix tests"\nagent: build'),
            case.checks,
            custom_grader=str(Path("skills/custom-command/evals") / suite.custom_grader),
            case=case,
        )
        self.assertFalse(bad_grade["passed"])
        self.assertIn("custom-command.no_behavior_frontmatter", {check["id"] for check in bad_grade["checks"] if check["status"] == "failed"})

    def test_custom_command_static_smoke_can_still_run_with_explicit_static_configurations(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_suite(
                Path("skills/custom-command/evals/manifest.json"),
                "workflow",
                Path(tmp) / "results",
                configurations={
                    "with_skill": {"harness": "static", "response_strategy": "expected_output_and_expectations", "force_skill": True},
                    "without_skill": {"harness": "static", "response_strategy": "prompt", "force_skill": False},
                },
            )

            self.assertEqual(len(summary["runs"]), 10)
            configurations = {run["configuration"] for run in summary["runs"]}
            self.assertEqual(configurations, {"with_skill", "without_skill"})

            first_with = Path(tmp) / "results" / "custom-command" / "workflow" / "1" / "with_skill"
            first_without = Path(tmp) / "results" / "custom-command" / "workflow" / "1" / "without_skill"
            self.assertTrue((first_with / "raw_output.json").exists())
            self.assertTrue((first_without / "raw_output.json").exists())
            self.assertIn("complete portable Markdown command", (first_with / "response.md").read_text())
            self.assertIn("Create a slash command", (first_without / "response.md").read_text())
            with_grade = json.loads((first_with / "grade.json").read_text())
            without_grade = json.loads((first_without / "grade.json").read_text())
            self.assertEqual(with_grade["judge"]["status"], "skipped")
            self.assertEqual(with_grade["judge"]["reason"], "no_subjective_checks")
            self.assertFalse(with_grade["passed"])
            self.assertFalse(without_grade["passed"])
            self.assertFalse(any(check["id"].startswith("legacy_expectation_") for check in with_grade["checks"]))
            self.assertGreater(with_grade["totals"]["failed"], 0)
            self.assertGreater(without_grade["totals"]["failed"], 0)
            self.assertNotEqual(
                json.loads((first_with / "metadata.json").read_text())["sandbox"],
                json.loads((first_without / "metadata.json").read_text())["sandbox"],
            )
            raw = json.loads((first_with / "raw_output.json").read_text())
            self.assertEqual(raw["status"], "passed")
            self.assertEqual(raw["exit_code"], 0)
            self.assertIn("stdout", raw)
            self.assertIn("stderr", raw)
            self.assertIn("elapsed_ms", json.loads((first_with / "timing.json").read_text()))
            self.assertIn("input_chars", json.loads((first_with / "usage.json").read_text()))

    def test_custom_command_workflow_defaults_to_real_pi_and_skips_when_live_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            result_root = Path(tmp) / "results"
            summary = run_suite(Path("skills/custom-command/evals/manifest.json"), "workflow", result_root, require_real=True)

            self.assertEqual(len(summary["runs"]), 10)
            self.assertEqual(summary["harness_modes"], {"with_skill": "real", "without_skill": "real"})
            self.assertFalse(summary["synthetic"])
            self.assertTrue(all(run["status"] == "skipped" for run in summary["runs"]))
            first_with = result_root / "custom-command" / "workflow" / "1" / "with_skill"
            raw = json.loads((first_with / "raw_output.json").read_text())
            self.assertEqual(raw["status"], "skipped")
            self.assertIn("live Pi execution is disabled", raw["skip_reason"])
            self.assertNotIn("complete portable Markdown command", (first_with / "response.md").read_text())

    def test_custom_command_workflow_can_run_all_cases_through_fake_real_pi(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_pi = root / "fake-pi.py"
            fake_pi.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "prompt = sys.argv[-1]\n"
                "print('generated command artifact for ' + prompt[:20])\n"
            )
            fake_pi.chmod(fake_pi.stat().st_mode | 0o111)
            result_root = root / "results"
            summary = run_suite(
                Path("skills/custom-command/evals/manifest.json"),
                "workflow",
                result_root,
                configurations={
                    "with_skill": {"harness": "pi", "executable": str(fake_pi), "allow_live": True, "force_skill": True},
                    "without_skill": {"harness": "pi", "executable": str(fake_pi), "allow_live": True, "force_skill": False},
                },
                require_real=True,
            )

            self.assertEqual(len(summary["runs"]), 10)
            self.assertTrue(all(run["harness_mode"] == "real" for run in summary["runs"]))
            self.assertTrue(all(not run["synthetic"] for run in summary["runs"]))
            first_with_response = (result_root / "custom-command" / "workflow" / "1" / "with_skill" / "response.md").read_text()
            first_without_response = (result_root / "custom-command" / "workflow" / "1" / "without_skill" / "response.md").read_text()
            self.assertIn("generated command artifact", first_with_response)
            self.assertIn("generated command artifact", first_without_response)
            self.assertNotIn("complete portable Markdown command", first_with_response)
            self.assertNotEqual(first_without_response, load_manifest(Path("skills/custom-command/evals/manifest.json")).suite("workflow").cases[0].prompt)

    def test_manifest_represents_suite_purposes_and_trigger_is_explicitly_not_run(self):
        manifest = load_manifest(Path("skills/custom-command/evals/manifest.json"))
        suites = {suite.name: suite for suite in manifest.suites}

        self.assertEqual({suite.type for suite in manifest.suites}, {"workflow", "trigger", "capability", "regression"})
        self.assertTrue(suites["trigger"].cases[0].metadata["should_trigger"])
        self.assertFalse(suites["trigger"].cases[1].metadata["should_trigger"])
        self.assertEqual(suites["regression"].cases[0].metadata["regression_from"], "agents-bf0")

        with tempfile.TemporaryDirectory() as tmp:
            summary = run_suite(Path("skills/custom-command/evals/manifest.json"), "trigger", Path(tmp) / "results")
            saved = json.loads((Path(tmp) / "results" / "summary.json").read_text())

            self.assertEqual(summary["suite_type"], "trigger")
            self.assertEqual(summary["status"], "unsupported")
            self.assertEqual(summary["runs"], [])
            self.assertIn("not implemented", summary["unsupported_reason"])
            self.assertEqual(saved["status"], "unsupported")

    def test_promote_real_failures_into_regression_suite_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_pi = root / "fake-pi.py"
            fake_pi.write_text("#!/usr/bin/env python3\nprint('wrong output')\n")
            fake_pi.chmod(fake_pi.stat().st_mode | 0o111)
            (root / "evals.json").write_text(
                json.dumps(
                    {
                        "evals": [
                            {
                                "id": "hello",
                                "prompt": "Say hello",
                                "checks": [{"id": "contains-hello", "type": "required_content", "value": "hello"}],
                            }
                        ]
                    }
                )
            )
            (root / "grader.py").write_text("def grade(response, case=None, context=None):\n    return []\n")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "skill": {"name": "demo", "path": "skills/demo/SKILL.md"},
                        "suites": [
                            {
                                "name": "workflow",
                                "type": "workflow",
                                "fixture": {"type": "empty"},
                                "legacy_evals": "evals.json",
                                "custom_grader": "grader.py",
                            },
                            {"name": "regression", "type": "regression", "fixture": {"type": "empty"}, "cases": []},
                        ],
                    }
                )
            )
            result_root = root / "results"
            run_suite(
                manifest_path,
                "workflow",
                result_root,
                configurations={"real": {"harness": "pi", "executable": str(fake_pi), "allow_live": True}},
                require_real=True,
            )
            output_manifest = root / "review" / "manifest.with-regression.json"

            promotion = promote_failures_to_regression_cases(
                manifest_path=manifest_path,
                result_root=result_root,
                output_manifest_path=output_manifest,
                source_bead="agents-1cs.7",
            )

            promoted_manifest = json.loads(output_manifest.read_text())
            regression_suite = next(suite for suite in promoted_manifest["suites"] if suite["name"] == "regression")
            promoted_case = regression_suite["cases"][0]
            loaded_case = load_manifest(output_manifest).suite("regression").cases[0]

            self.assertEqual(promotion["promoted"], 1)
            self.assertEqual(promoted_case["source_run_id"], "workflow/hello/real")
            self.assertIn("workflow/hello/real", promoted_case["trace_path"])
            self.assertIn("failed", promoted_case["failure_summary"])
            self.assertEqual(promoted_case["source_bead"], "agents-1cs.7")
            self.assertEqual(promoted_case["prompt"], "Say hello")
            self.assertEqual(promoted_case["checks"], [{"id": "contains-hello", "type": "required_content", "value": "hello"}])
            self.assertEqual(regression_suite["custom_grader"], "../grader.py")
            self.assertEqual(promoted_manifest["suites"][0]["legacy_evals"], "../evals.json")
            self.assertEqual(loaded_case.metadata["source_run_id"], "workflow/hello/real")

            passing_pi = root / "passing-pi.py"
            passing_pi.write_text("#!/usr/bin/env python3\nprint('hello')\n")
            passing_pi.chmod(passing_pi.stat().st_mode | 0o111)
            regression_summary = run_suite(
                output_manifest,
                "regression",
                root / "regression-results",
                configurations={"real": {"harness": "pi", "executable": str(passing_pi), "allow_live": True}},
                require_real=True,
            )

            self.assertEqual(regression_summary["status"], "completed")
            self.assertEqual(regression_summary["suite_type"], "regression")
            self.assertEqual(regression_summary["runs"][0]["case_id"], promoted_case["id"])
            self.assertTrue(regression_summary["runs"][0]["passed"])

    def test_report_labels_metric_provenance_and_caveats_synthetic_comparisons(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "skill": {"name": "demo", "path": "skills/demo/SKILL.md"},
                        "suites": [
                            {
                                "name": "smoke",
                                "type": "workflow",
                                "fixture": {"type": "empty"},
                                "cases": [{"id": "hello", "prompt": "Say hello", "checks": [{"type": "required_content", "value": "hello"}]}],
                            }
                        ],
                    }
                )
            )

            run_suite(
                manifest_path,
                "smoke",
                root / "results",
                configurations={
                    "baseline": {"harness": "static", "response": "hello", "model": "static-model", "provider": "static-provider"},
                    "candidate": {"harness": "static", "response": "hello"},
                },
            )

            benchmark = json.loads((root / "results" / "benchmark.json").read_text())
            report = (root / "results" / "report.md").read_text()
            baseline = benchmark["configurations"]["baseline"]

            self.assertEqual(baseline["harness_mode"], "static")
            self.assertTrue(baseline["synthetic"])
            self.assertEqual(baseline["model"], "static-model")
            self.assertEqual(baseline["provider"], "static-provider")
            self.assertEqual(baseline["metric_provenance"]["usage"], "character_count_placeholder")
            self.assertFalse(benchmark["comparison"]["comparable"])
            self.assertIn("synthetic", benchmark["comparison"]["caveat"])
            self.assertIn("Synthetic/static results warning", report)
            self.assertIn("Token metrics are unavailable", report)
            self.assertIn("Comparison caveat", report)

    def test_custom_command_run_emits_comparable_benchmark_and_review_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            result_root = Path(tmp) / "results"
            run_suite(
                Path("skills/custom-command/evals/manifest.json"),
                "workflow",
                result_root,
                configurations={
                    "with_skill": {"harness": "static", "response_strategy": "expected_output_and_expectations", "force_skill": True},
                    "without_skill": {"harness": "static", "response_strategy": "prompt", "force_skill": False},
                },
            )

            benchmark = json.loads((result_root / "benchmark.json").read_text())
            report = (result_root / "report.md").read_text()

            self.assertEqual(benchmark["suite"], "workflow")
            self.assertIn("with_skill", benchmark["configurations"])
            self.assertIn("without_skill", benchmark["configurations"])
            self.assertIn("pass_rate", benchmark["configurations"]["with_skill"])
            self.assertEqual(benchmark["configurations"]["with_skill"]["harness_mode"], "static")
            self.assertTrue(benchmark["configurations"]["with_skill"]["synthetic"])
            self.assertEqual(benchmark["comparison"]["baseline"], "without_skill")
            self.assertEqual(benchmark["comparison"]["candidate"], "with_skill")
            self.assertIn("pass_rate_delta", benchmark["comparison"])
            self.assertIn("elapsed_ms_delta", benchmark["comparison"])
            self.assertIn("usage_delta", benchmark["comparison"])
            self.assertEqual(benchmark["cases"]["1"]["prompt"].split()[0], "Create")
            self.assertIn("with_skill", benchmark["cases"]["1"]["configurations"])
            self.assertIn("without_skill", benchmark["cases"]["1"]["configurations"])
            self.assertIn("custom-command / workflow", report)
            self.assertIn("Case 1", report)
            self.assertIn("Create a slash command", report)
            self.assertIn("with_skill", report)
            self.assertIn("without_skill", report)

    def test_empty_sandbox_is_isolated_and_repeatable(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = create_sandbox(Path(tmp), "case-a", {"type": "empty"})
            second = create_sandbox(Path(tmp), "case-a", {"type": "empty"})

            (first.path / "only-first.txt").write_text("first")

            self.assertTrue(first.path.exists())
            self.assertTrue(second.path.exists())
            self.assertNotEqual(first.path, second.path)
            self.assertFalse((second.path / "only-first.txt").exists())
            self.assertEqual(first.fixture_type, "empty")
            self.assertEqual(second.fixture_type, "empty")

    def test_process_failures_are_not_graded_as_content_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_pi = root / "slow-pi.py"
            fake_pi.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(2)\n")
            fake_pi.chmod(fake_pi.stat().st_mode | 0o111)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "skill": {"name": "demo", "path": "skills/demo/SKILL.md"},
                        "suites": [
                            {
                                "name": "workflow",
                                "type": "workflow",
                                "fixture": {"type": "empty"},
                                "cases": [{"id": "hello", "prompt": "Say hello", "checks": [{"type": "required_content", "value": "hello"}]}],
                            }
                        ],
                    }
                )
            )

            summary = run_suite(
                manifest_path,
                "workflow",
                root / "results",
                configurations={"real": {"harness": "pi", "executable": str(fake_pi), "allow_live": True, "timeout_seconds": 0.01}},
                require_real=True,
            )
            grade = json.loads((root / "results" / "demo" / "workflow" / "hello" / "real" / "grade.json").read_text())
            raw = json.loads((root / "results" / "demo" / "workflow" / "hello" / "real" / "raw_output.json").read_text())

            benchmark = json.loads((root / "results" / "benchmark.json").read_text())
            report = (root / "results" / "report.md").read_text()

            self.assertEqual(summary["runs"][0]["status"], "process_failed")
            self.assertIsNone(summary["runs"][0]["passed"])
            self.assertEqual(raw["status"], "process_failed")
            self.assertEqual(raw["error"], "timeout")
            self.assertEqual(grade["status"], "not_graded")
            self.assertIsNone(grade["passed"])
            self.assertIn("timeout", grade["summary"])
            self.assertEqual(grade["checks"], [])
            self.assertEqual(benchmark["configurations"]["real"]["not_graded"], 1)
            self.assertEqual(benchmark["configurations"]["real"]["status_counts"]["process_failed"], 1)
            self.assertIn("Not graded", report)

    def test_real_harness_trace_bundle_captures_artifacts_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: demo skill\n---\n")
            fake_pi = root / "fake-pi.py"
            fake_pi.write_text(
                "#!/usr/bin/env python3\n"
                "from pathlib import Path\n"
                "Path('artifact.md').write_text('# generated artifact\\n')\n"
                "print('generated response')\n"
            )
            fake_pi.chmod(fake_pi.stat().st_mode | 0o111)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 7,
                        "skill": {"name": "demo", "path": "skill/SKILL.md"},
                        "suites": [
                            {
                                "name": "workflow",
                                "type": "workflow",
                                "fixture": {"type": "empty"},
                                "cases": [{"id": "hello", "prompt": "Say hello", "checks": [{"type": "required_content", "value": "generated"}]}],
                            }
                        ],
                    }
                )
            )

            run_suite(
                manifest_path,
                "workflow",
                root / "results",
                configurations={
                    "with_skill": {
                        "harness": "pi",
                        "executable": str(fake_pi),
                        "allow_live": True,
                        "force_skill": True,
                        "model": "fake-model",
                        "provider": "fake-provider",
                    }
                },
                require_real=True,
            )

            run_dir = root / "results" / "demo" / "workflow" / "hello" / "with_skill"
            artifacts = json.loads((run_dir / "artifact_manifest.json").read_text())
            metadata = json.loads((run_dir / "metadata.json").read_text())
            events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
            workspace_diff = (run_dir / "workspace_diff.txt").read_text()

            self.assertIn("artifact.md", {entry["path"] for entry in artifacts["files"]})
            self.assertIn("A artifact.md", workspace_diff)
            self.assertEqual(metadata["manifest"]["schema_version"], 7)
            self.assertEqual(metadata["suite"], "workflow")
            self.assertEqual(metadata["case_id"], "hello")
            self.assertEqual(metadata["configuration"], "with_skill")
            self.assertEqual(metadata["harness"]["mode"], "real")
            self.assertEqual(metadata["harness"]["model"], "fake-model")
            self.assertEqual(metadata["harness"]["provider"], "fake-provider")
            self.assertTrue(metadata["skill_paths_loaded"])
            self.assertEqual(events[-1]["event"], "run_finished")
            self.assertEqual(events[1]["status"], "passed")

    def test_real_pi_harness_adapter_runs_fake_pi_with_and_without_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: demo skill\n---\n")
            fake_pi = root / "fake-pi.py"
            fake_pi.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "with open(os.environ['FAKE_PI_INVOCATIONS'], 'a') as f:\n"
                "    f.write(json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd()}) + '\\n')\n"
                "print('generated by fake pi')\n"
            )
            fake_pi.chmod(fake_pi.stat().st_mode | 0o111)
            invocations = root / "invocations.jsonl"
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "skill": {"name": "demo", "path": "skill/SKILL.md"},
                        "suites": [
                            {
                                "name": "workflow",
                                "type": "workflow",
                                "fixture": {"type": "empty"},
                                "cases": [{"id": "hello", "prompt": "Say hello", "checks": [{"type": "required_content", "value": "generated"}]}],
                            }
                        ],
                    }
                )
            )

            summary = run_suite(
                manifest_path,
                "workflow",
                root / "results",
                configurations={
                    "with_skill": {
                        "harness": "pi",
                        "executable": str(fake_pi),
                        "allow_live": True,
                        "force_skill": True,
                        "env": {"FAKE_PI_INVOCATIONS": str(invocations)},
                        "model": "fake-model",
                        "provider": "fake-provider",
                    },
                    "without_skill": {
                        "harness": "pi",
                        "executable": str(fake_pi),
                        "allow_live": True,
                        "force_skill": False,
                        "env": {"FAKE_PI_INVOCATIONS": str(invocations)},
                    },
                },
                require_real=True,
            )

            with_dir = root / "results" / "demo" / "workflow" / "hello" / "with_skill"
            without_dir = root / "results" / "demo" / "workflow" / "hello" / "without_skill"
            with_raw = json.loads((with_dir / "raw_output.json").read_text())
            without_raw = json.loads((without_dir / "raw_output.json").read_text())
            with_metadata = json.loads((with_dir / "metadata.json").read_text())
            without_metadata = json.loads((without_dir / "metadata.json").read_text())
            invocations_data = [json.loads(line) for line in invocations.read_text().splitlines()]

            self.assertEqual(summary["harness_modes"], {"with_skill": "real", "without_skill": "real"})
            self.assertFalse(summary["synthetic"])
            self.assertEqual((with_dir / "response.md").read_text().strip(), "generated by fake pi")
            self.assertEqual(with_raw["exit_code"], 0)
            self.assertEqual(with_raw["stdout"].strip(), "generated by fake pi")
            self.assertIn("stderr", with_raw)
            self.assertIn("command", with_raw)
            self.assertIn("--skill", with_raw["command"])
            self.assertNotIn("--skill", without_raw["command"])
            self.assertEqual(with_metadata["harness"]["mode"], "real")
            self.assertFalse(with_metadata["harness"]["synthetic"])
            self.assertEqual(with_metadata["harness"]["model"], "fake-model")
            self.assertEqual(with_metadata["harness"]["provider"], "fake-provider")
            self.assertEqual(len(with_metadata["skill_paths_loaded"]), 1)
            self.assertEqual(without_metadata["skill_paths_loaded"], [])
            self.assertTrue(any("Say hello" in arg for invocation in invocations_data for arg in invocation["argv"]))

    def test_static_harness_is_labeled_synthetic_and_can_be_rejected_for_benchmarks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "skill": {"name": "demo", "path": "skills/demo/SKILL.md"},
                        "suites": [
                            {
                                "name": "smoke",
                                "type": "workflow",
                                "fixture": {"type": "empty"},
                                "cases": [{"id": "hello", "prompt": "Say hello", "expected_output": "hello"}],
                            }
                        ],
                    }
                )
            )
            result_root = root / "results"

            summary = run_suite(
                manifest_path,
                "smoke",
                result_root,
                configurations={"default": {"harness": "static", "response": "hello"}},
            )

            run = summary["runs"][0]
            benchmark = json.loads((result_root / "benchmark.json").read_text())
            metadata = json.loads((result_root / "demo" / "smoke" / "hello" / "default" / "metadata.json").read_text())
            report = (result_root / "report.md").read_text()

            self.assertEqual(run["harness_mode"], "static")
            self.assertTrue(run["synthetic"])
            self.assertEqual(summary["harness_modes"], {"default": "static"})
            self.assertTrue(summary["synthetic"])
            self.assertEqual(metadata["harness"]["mode"], "static")
            self.assertTrue(metadata["harness"]["synthetic"])
            self.assertTrue(benchmark["configurations"]["default"]["synthetic"])
            self.assertIn("Synthetic/static", report)

            with self.assertRaisesRegex(ValueError, "requires real harness"):
                run_suite(
                    manifest_path,
                    "smoke",
                    root / "rejected",
                    configurations={"default": {"harness": "static", "response": "hello"}},
                    require_real=True,
                )

    def test_runner_writes_standard_trace_bundle_for_trivial_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "skill": {"name": "demo", "path": "skills/demo/SKILL.md"},
                        "suites": [
                            {
                                "name": "smoke",
                                "type": "workflow",
                                "fixture": {"type": "empty"},
                                "cases": [
                                    {
                                        "id": "hello",
                                        "prompt": "Say hello",
                                        "expected_output": "hello",
                                    }
                                ],
                            }
                        ],
                    }
                )
            )
            result_root = root / "results"

            summary = run_suite(
                manifest_path,
                "smoke",
                result_root,
                configurations={"default": {"harness": "static", "response": "hello"}},
            )

            run_dir = result_root / "demo" / "smoke" / "hello" / "default"
            self.assertEqual(summary["suite"], "smoke")
            self.assertEqual(summary["runs"][0]["case_id"], "hello")
            self.assertEqual(summary["runs"][0]["configuration"], "default")
            self.assertTrue((run_dir / "raw_output.json").exists())
            self.assertTrue((run_dir / "events.jsonl").exists())
            self.assertEqual((run_dir / "response.md").read_text(), "hello")
            timing = json.loads((run_dir / "timing.json").read_text())
            usage = json.loads((run_dir / "usage.json").read_text())
            grade = json.loads((run_dir / "grade.json").read_text())
            events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
            self.assertIn("elapsed_ms", timing)
            self.assertIn("input_chars", usage)
            self.assertEqual(grade["status"], "graded")
            self.assertTrue(grade["passed"])
            self.assertEqual(events[0]["event"], "run_started")
            self.assertEqual(events[-1]["event"], "run_finished")


if __name__ == "__main__":
    unittest.main()
