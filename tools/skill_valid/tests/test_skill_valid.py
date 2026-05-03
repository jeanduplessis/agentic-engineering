import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tools.skill_valid import ValidationDependencies, ValidationOptions, main, parse_sentinel_result, validate_skill


VALID_SENTINEL = 'review text\nSKILL_VALID_RESULT={"status":"passed","target":"skills/demo","checks":[{"id":"spec","status":"passed","message":"ok"}]}\n'


class SkillValidTests(unittest.TestCase):
    @contextlib.contextmanager
    def make_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield None, Path(tmp)

    def write_valid_skill(self, root: Path, *, name: str = "demo", regression: bool = True) -> Path:
        skill_dir = root / "skills" / name
        eval_dir = skill_dir / "evals"
        fixture_dir = eval_dir / "fixtures" / "project"
        fixture_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: demo skill\n---\n")
        (fixture_dir / "README.md").write_text("fixture\n")
        (eval_dir / "evals.json").write_text(
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
        (eval_dir / "grader.py").write_text("def grade(response, case=None, context=None):\n    return []\n")
        suites = [
            {
                "name": "workflow",
                "type": "workflow",
                "fixture": {"type": "copy", "path": "fixtures/project"},
                "legacy_evals": "evals.json",
                "custom_grader": "grader.py",
            },
            {
                "name": "trigger",
                "type": "trigger",
                "unsupported_reason": "represented but not executable",
                "cases": [{"id": "trigger-case", "prompt": "Maybe trigger", "should_trigger": True}],
            },
        ]
        if regression:
            suites.append(
                {
                    "name": "regression",
                    "type": "regression",
                    "fixture": {"type": "empty"},
                    "cases": [
                        {
                            "id": "fixed",
                            "prompt": "Say fixed",
                            "checks": [{"id": "contains-fixed", "type": "required_content", "value": "fixed"}],
                        }
                    ],
                }
            )
        manifest = {
            "schema_version": 1,
            "skill": {"name": name, "path": "../SKILL.md"},
            "suites": suites,
            "configurations": {
                "with_skill": {"harness": "pi", "force_skill": True, "timeout_seconds": 45},
                "without_skill": {"harness": "pi", "force_skill": False},
            },
        }
        (eval_dir / "manifest.json").write_text(json.dumps(manifest))
        (skill_dir / "AGENTS.md").write_text(
            "# Purpose\n\nDemo skill. See SKILL.md.\n\n"
            "# How the skill works\n\nUses the skill instructions in SKILL.md.\n\n"
            "# Eval and validation\n\nRun evals/manifest.json, evals/evals.json, evals/grader.py, and evals/fixtures/project.\n\n"
            "# Change guidelines\n\nUpdate evals whenever behavior changes.\n"
        )
        return skill_dir

    def passing_deps(self, *, pi_stdout: str = VALID_SENTINEL, pi_returncode: int = 0, eval_run=None, llm_check=None):
        calls = {"pi": [], "eval": [], "llm": []}

        def pi_runner(command, *, cwd, env, timeout):
            calls["pi"].append({"command": command, "cwd": cwd, "env": env, "timeout": timeout})
            return SimpleNamespace(returncode=pi_returncode, stdout=pi_stdout, stderr="pi stderr")

        def default_eval_run(manifest_path, suite_name, result_root, configurations, *, require_real):
            calls["eval"].append(
                {
                    "manifest_path": Path(manifest_path),
                    "suite_name": suite_name,
                    "result_root": Path(result_root),
                    "configurations": configurations,
                    "require_real": require_real,
                }
            )
            Path(result_root).mkdir(parents=True, exist_ok=True)
            (Path(result_root) / "summary.json").write_text(json.dumps({"suite": suite_name}))
            runs = []
            if suite_name == "workflow":
                runs = [
                    {
                        "case_id": "hello",
                        "configuration": "with_skill",
                        "status": "passed",
                        "passed": True,
                        "harness_mode": "real",
                        "synthetic": False,
                    }
                ]
            elif suite_name == "regression":
                runs = [
                    {
                        "case_id": "fixed",
                        "configuration": "with_skill",
                        "status": "passed",
                        "passed": True,
                        "harness_mode": "real",
                        "synthetic": False,
                    }
                ]
            return {"suite": suite_name, "suite_type": suite_name, "status": "completed", "runs": runs}

        def default_llm_check(path):
            calls["llm"].append(Path(path))
            if llm_check is not None:
                return llm_check(Path(path))
            return {"status": "pass", "score": 100, "metrics": {"path": str(path), "tokens": 1, "analyzed_preview": "hidden"}, "findings": []}

        return ValidationDependencies(pi_runner=pi_runner, eval_runner=eval_run or default_eval_run, llm_optimal_checker=default_llm_check), calls

    def validate(self, root: Path, target: Path, **kwargs):
        deps, calls = self.passing_deps(**kwargs.pop("deps_kwargs", {}))
        options = ValidationOptions(target=target, repo_root=root, allow_live_pi=True, **kwargs)
        return validate_skill(options, deps=deps), calls

    def test_cli_emits_compact_stdout_json_for_missing_skill_md_and_logs_to_stderr(self):
        with self.make_repo() as (tmp, root):
            target = root / "skills" / "demo"
            target.mkdir(parents=True)
            stdout = io.StringIO()
            stderr = io.StringIO()

            code = main([str(target), "--allow-live-pi", "--repo-root", str(root)], stdout=stdout, stderr=stderr)

            self.assertEqual(code, 1)
            stdout_text = stdout.getvalue()
            self.assertTrue(stdout_text.startswith("{"))
            self.assertNotIn("skill_valid:", stdout_text)
            self.assertNotIn("\n  ", stdout_text)
            result = json.loads(stdout_text)
            self.assertFalse(result["valid"])
            self.assertEqual(result["target"], "skills/demo")
            self.assertEqual(result["gates"]["target"]["status"], "failed")
            self.assertIn("SKILL.md", result["gates"]["target"]["message"])
            self.assertIn("skill_valid:", stderr.getvalue())
            self.assertEqual(set(result["gates"]), {"target", "skill_spec", "eval_manifest", "agents_md", "llm_optimal_check", "live_opt_in", "validate_skills", "live_eval"})

    def test_rejects_targets_outside_repo_local_skills_collection_before_live_work(self):
        with self.make_repo() as (tmp, root):
            outside = root / "not-skills" / "demo"
            outside.mkdir(parents=True)
            (outside / "SKILL.md").write_text("demo")
            deps, calls = self.passing_deps()

            code, result = validate_skill(ValidationOptions(outside, repo_root=root, allow_live_pi=True), deps=deps)

            self.assertEqual(code, 1)
            self.assertEqual(result["gates"]["target"]["status"], "failed")
            self.assertIn("repo-local skills collection", result["gates"]["target"]["message"])
            self.assertEqual(calls["pi"], [])
            self.assertEqual(calls["eval"], [])
            self.assertNotIn("failure_artifacts", result)

    def test_missing_live_opt_in_fails_after_cheap_gates_and_before_live_calls(self):
        with self.make_repo() as (tmp, root):
            target = self.write_valid_skill(root)
            deps, calls = self.passing_deps()

            code, result = validate_skill(
                ValidationOptions(target, repo_root=root, allow_live_pi=False, env={}),
                deps=deps,
            )

            self.assertEqual(code, 1)
            self.assertEqual(result["gates"]["target"]["status"], "passed")
            self.assertEqual(result["gates"]["eval_manifest"]["status"], "passed")
            self.assertEqual(result["gates"]["agents_md"]["status"], "passed")
            self.assertEqual(result["gates"]["llm_optimal_check"]["status"], "passed")
            self.assertEqual(result["gates"]["live_opt_in"]["status"], "failed")
            self.assertEqual(result["gates"]["validate_skills"]["status"], "not_run")
            self.assertEqual(calls["pi"], [])
            self.assertEqual(calls["eval"], [])

    def test_live_opt_in_accepts_existing_skill_eval_environment_convention(self):
        with self.make_repo() as (tmp, root):
            target = self.write_valid_skill(root)
            deps, calls = self.passing_deps()

            code, result = validate_skill(
                ValidationOptions(target, repo_root=root, allow_live_pi=False, env={"SKILL_EVAL_ALLOW_LIVE_PI": "1"}),
                deps=deps,
            )

            self.assertEqual(code, 0)
            self.assertTrue(result["valid"])
            self.assertEqual(len(calls["pi"]), 1)
            self.assertEqual([call["suite_name"] for call in calls["eval"]], ["workflow", "regression"])

    def test_eval_manifest_structural_gate_passes_and_ignores_unsupported_suite_types(self):
        with self.make_repo() as (tmp, root):
            target = self.write_valid_skill(root)

            (code, result), calls = self.validate(root, target)

            self.assertEqual(code, 0)
            self.assertTrue(result["valid"])
            self.assertEqual(result["gates"]["eval_manifest"]["status"], "passed")
            self.assertEqual([call["suite_name"] for call in calls["eval"]], ["workflow", "regression"])

    def test_deterministic_validation_reports_multiple_missing_requirements_before_live_work(self):
        with self.make_repo() as (tmp, root):
            target = root / "skills" / "demo"
            target.mkdir(parents=True)
            (target / "SKILL.md").write_text("---\nname: demo\ndescription: demo\n---\n")
            deps, calls = self.passing_deps()

            code, result = validate_skill(ValidationOptions(target, repo_root=root, allow_live_pi=True), deps=deps)

            self.assertEqual(code, 1)
            self.assertEqual(result["gates"]["target"]["status"], "passed")
            self.assertIn(result["gates"]["skill_spec"]["status"], {"passed", "warn"})
            self.assertEqual(result["gates"]["eval_manifest"]["status"], "failed")
            self.assertIn("evals/manifest.json", result["gates"]["eval_manifest"]["message"])
            self.assertEqual(result["gates"]["agents_md"]["status"], "failed")
            self.assertIn("AGENTS.md", result["gates"]["agents_md"]["message"])
            self.assertEqual(result["gates"]["llm_optimal_check"]["status"], "passed")
            self.assertEqual(result["gates"]["live_opt_in"]["status"], "passed")
            self.assertEqual(result["gates"]["validate_skills"]["status"], "not_run")
            self.assertEqual(result["gates"]["live_eval"]["status"], "not_run")
            self.assertEqual(calls["pi"], [])
            self.assertEqual(calls["eval"], [])

    def test_skill_spec_gate_reports_deterministic_spec_failures_before_live_work(self):
        with self.make_repo() as (tmp, root):
            target = self.write_valid_skill(root)
            (target / "SKILL.md").write_text("---\nname: other\ndescription: <bad>\nunknown: nope\n---\nSee [missing](references/missing.md).\n")
            deps, calls = self.passing_deps()

            code, result = validate_skill(ValidationOptions(target, repo_root=root, allow_live_pi=True), deps=deps)

            self.assertEqual(code, 1)
            self.assertEqual(result["gates"]["target"]["status"], "passed")
            self.assertEqual(result["gates"]["skill_spec"]["status"], "failed")
            checks = result["gates"]["skill_spec"]["details"]["checks"]
            failed_ids = {check["id"] for check in checks if check["status"] == "failed"}
            self.assertIn("frontmatter.allowed-fields", failed_ids)
            self.assertIn("name.directory-match", failed_ids)
            self.assertIn("description.no-xml", failed_ids)
            self.assertIn("references.paths-exist", failed_ids)
            self.assertEqual(calls["pi"], [])
            self.assertEqual(calls["eval"], [])

    def test_skill_spec_warnings_do_not_block_live_gates(self):
        with self.make_repo() as (tmp, root):
            target = self.write_valid_skill(root)
            # This is spec-valid but short and lacks trigger context, so it should warn only.
            (target / "SKILL.md").write_text("---\nname: demo\ndescription: demo skill\n---\n# Demo\n")
            deps, calls = self.passing_deps()

            code, result = validate_skill(ValidationOptions(target, repo_root=root, allow_live_pi=True), deps=deps)

            self.assertEqual(code, 0)
            self.assertTrue(result["valid"])
            self.assertEqual(result["gates"]["skill_spec"]["status"], "warn")
            warning_ids = {check["id"] for check in result["gates"]["skill_spec"]["details"]["checks"] if check["status"] == "warn"}
            self.assertIn("description.trigger-context", warning_ids)
            self.assertEqual(len(calls["pi"]), 1)
            self.assertTrue(calls["eval"])

    def test_skill_spec_accepts_pi_disable_model_invocation_and_non_reserved_names(self):
        with self.make_repo() as (tmp, root):
            target = self.write_valid_skill(root, name="pi-helper", regression=False)
            (target / "SKILL.md").write_text(
                "---\n"
                "name: pi-helper\n"
                "description: Use when a Pi user wants a hidden helper workflow.\n"
                "disable-model-invocation: true\n"
                "---\n"
                "# Hidden helper\n"
            )
            deps, calls = self.passing_deps(
                pi_stdout='review text\nSKILL_VALID_RESULT={"status":"passed","target":"skills/pi-helper","checks":[{"id":"spec","status":"passed","message":"ok"}]}\n'
            )

            code, result = validate_skill(ValidationOptions(target, repo_root=root, allow_live_pi=True), deps=deps)

            self.assertEqual(code, 0)
            self.assertTrue(result["valid"])
            checks = result["gates"]["skill_spec"]["details"]["checks"]
            check_map = {check["id"]: check for check in checks}
            self.assertEqual(check_map["frontmatter.allowed-fields"]["status"], "passed")
            self.assertEqual(check_map["disable-model-invocation.type"]["status"], "passed")
            self.assertNotIn("name.reserved-words", check_map)
            self.assertEqual(len(calls["pi"]), 1)

    def test_eval_manifest_structural_failures_fail_before_live_work(self):
        cases = []

        def remove_manifest(root, target):
            (target / "evals" / "manifest.json").unlink()

        cases.append(("missing eval manifest", remove_manifest, "manifest"))

        def invalid_json(root, target):
            (target / "evals" / "manifest.json").write_text("{")

        cases.append(("invalid JSON", invalid_json, "JSON"))

        def name_mismatch(root, target):
            data = json.loads((target / "evals" / "manifest.json").read_text())
            data["skill"]["name"] = "other"
            (target / "evals" / "manifest.json").write_text(json.dumps(data))

        cases.append(("skill name mismatch", name_mismatch, "skill name"))

        def path_mismatch(root, target):
            wrong = target / "OTHER.md"
            wrong.write_text("other")
            data = json.loads((target / "evals" / "manifest.json").read_text())
            data["skill"]["path"] = "../OTHER.md"
            (target / "evals" / "manifest.json").write_text(json.dumps(data))

        cases.append(("skill path mismatch", path_mismatch, "skill path"))

        def no_workflow(root, target):
            data = json.loads((target / "evals" / "manifest.json").read_text())
            data["suites"] = [suite for suite in data["suites"] if suite["name"] != "workflow"]
            (target / "evals" / "manifest.json").write_text(json.dumps(data))

        cases.append(("missing workflow", no_workflow, "workflow"))

        def empty_workflow(root, target):
            data = json.loads((target / "evals" / "manifest.json").read_text())
            data["suites"][0].pop("legacy_evals", None)
            data["suites"][0]["cases"] = []
            (target / "evals" / "manifest.json").write_text(json.dumps(data))

        cases.append(("empty workflow", empty_workflow, "non-empty"))

        def no_with_skill(root, target):
            data = json.loads((target / "evals" / "manifest.json").read_text())
            data["configurations"].pop("with_skill")
            (target / "evals" / "manifest.json").write_text(json.dumps(data))

        cases.append(("missing with_skill", no_with_skill, "with_skill"))

        def with_skill_not_pi(root, target):
            data = json.loads((target / "evals" / "manifest.json").read_text())
            data["configurations"]["with_skill"]["harness"] = "static"
            (target / "evals" / "manifest.json").write_text(json.dumps(data))

        cases.append(("with_skill not pi", with_skill_not_pi, "Pi harness"))

        def with_skill_not_forced(root, target):
            data = json.loads((target / "evals" / "manifest.json").read_text())
            data["configurations"]["with_skill"]["force_skill"] = False
            (target / "evals" / "manifest.json").write_text(json.dumps(data))

        cases.append(("with_skill not forced", with_skill_not_forced, "force-skill"))

        def missing_legacy(root, target):
            (target / "evals" / "evals.json").unlink()

        cases.append(("missing legacy evals", missing_legacy, "evals/evals.json"))

        def missing_grader(root, target):
            (target / "evals" / "grader.py").unlink()

        cases.append(("missing custom grader", missing_grader, "evals/grader.py"))

        def missing_fixture(root, target):
            import shutil

            shutil.rmtree(target / "evals" / "fixtures" / "project")

        cases.append(("missing copy fixture", missing_fixture, "evals/fixtures/project"))

        for label, mutate, expected in cases:
            with self.subTest(label=label), self.make_repo() as (tmp, root):
                target = self.write_valid_skill(root)
                mutate(root, target)
                deps, calls = self.passing_deps()

                code, result = validate_skill(ValidationOptions(target, repo_root=root, allow_live_pi=True), deps=deps)

                self.assertEqual(code, 1)
                self.assertEqual(result["gates"]["eval_manifest"]["status"], "failed")
                self.assertIn(expected, result["gates"]["eval_manifest"]["message"])
                self.assertEqual(calls["pi"], [])
                self.assertEqual(calls["eval"], [])

    def test_agents_md_gate_requires_headings_and_concrete_manifest_references(self):
        cases = []

        def missing(root, target):
            (target / "AGENTS.md").unlink()

        cases.append(("missing AGENTS.md", missing, "AGENTS.md"))

        def empty(root, target):
            (target / "AGENTS.md").write_text("  \n")

        cases.append(("empty AGENTS.md", empty, "empty"))

        def missing_heading(root, target):
            text = (target / "AGENTS.md").read_text().replace("# Change guidelines", "# Other")
            (target / "AGENTS.md").write_text(text)

        cases.append(("missing heading", missing_heading, "Change guidelines"))

        def missing_base_reference(root, target):
            text = (target / "AGENTS.md").read_text().replace("evals/manifest.json", "manifest file")
            (target / "AGENTS.md").write_text(text)

        cases.append(("missing base reference", missing_base_reference, "evals/manifest.json"))

        def missing_manifest_reference(root, target):
            text = (target / "AGENTS.md").read_text().replace("evals/grader.py", "grader")
            (target / "AGENTS.md").write_text(text)

        cases.append(("missing manifest-derived reference", missing_manifest_reference, "evals/grader.py"))

        for label, mutate, expected in cases:
            with self.subTest(label=label), self.make_repo() as (tmp, root):
                target = self.write_valid_skill(root)
                mutate(root, target)
                deps, calls = self.passing_deps()

                code, result = validate_skill(ValidationOptions(target, repo_root=root, allow_live_pi=True), deps=deps)

                self.assertEqual(code, 1)
                self.assertEqual(result["gates"]["agents_md"]["status"], "failed")
                self.assertIn(expected, result["gates"]["agents_md"]["message"])
                self.assertEqual(calls["pi"], [])
                self.assertEqual(calls["eval"], [])

    def test_llm_optimal_check_gate_maps_pass_warn_fail_and_compacts_report(self):
        def report(status):
            return {
                "status": status,
                "score": {"pass": 100, "warn": 85, "fail": 60}[status],
                "metrics": {"path": "SKILL.md", "tokens": 12, "characters": 44, "analyzed_preview": "do not embed"},
                "findings": [
                    {
                        "rule_id": "REL002",
                        "severity": "major",
                        "category": "reliability",
                        "location": {"line": 3},
                        "message": "Overlong workflow step.",
                        "suggestion": "Split it.",
                    }
                ] if status != "pass" else [],
            }

        cases = [("pass", 0, True, "passed"), ("warn", 0, True, "warn"), ("fail", 1, False, "failed")]
        for check_status, expected_code, expected_valid, gate_status in cases:
            with self.subTest(check_status=check_status), self.make_repo() as (tmp, root):
                target = self.write_valid_skill(root)
                deps, calls = self.passing_deps(llm_check=lambda path, s=check_status: report(s))

                code, result = validate_skill(ValidationOptions(target, repo_root=root, allow_live_pi=True), deps=deps)

                self.assertEqual(code, expected_code)
                self.assertEqual(result["valid"], expected_valid)
                gate = result["gates"]["llm_optimal_check"]
                self.assertEqual(gate["status"], gate_status)
                compact = gate["details"]["report"]
                self.assertEqual(compact["status"], check_status)
                self.assertNotIn("analyzed_preview", compact["metrics"])
                if check_status == "fail":
                    self.assertEqual(calls["pi"], [])
                    self.assertEqual(calls["eval"], [])
                    self.assertEqual(result["gates"]["validate_skills"]["status"], "not_run")

    def test_llm_optimal_check_tool_error_fails_closed_before_live_gates(self):
        with self.make_repo() as (tmp, root):
            target = self.write_valid_skill(root)

            def broken_checker(path):
                raise RuntimeError("missing tokenizer")

            deps, calls = self.passing_deps(llm_check=broken_checker)

            code, result = validate_skill(ValidationOptions(target, repo_root=root, allow_live_pi=True), deps=deps)

            self.assertEqual(code, 1)
            self.assertFalse(result["valid"])
            self.assertEqual(result["gates"]["llm_optimal_check"]["status"], "failed")
            self.assertIn("tool error", result["gates"]["llm_optimal_check"]["message"])
            self.assertEqual(calls["pi"], [])
            self.assertEqual(calls["eval"], [])
            self.assertEqual(result["gates"]["validate_skills"]["status"], "not_run")
            self.assertEqual(result["gates"]["live_eval"]["status"], "not_run")

    def test_validate_skills_pi_command_uses_wrapper_prompt_read_only_tools_and_overrides(self):
        with self.make_repo() as (tmp, root):
            target = self.write_valid_skill(root)
            deps, calls = self.passing_deps()

            code, result = validate_skill(
                ValidationOptions(
                    target,
                    repo_root=root,
                    allow_live_pi=True,
                    provider="openrouter",
                    model="gpt-test",
                    thinking="low",
                ),
                deps=deps,
            )

            self.assertEqual(code, 0)
            command = calls["pi"][0]["command"]
            self.assertEqual(calls["pi"][0]["cwd"], root.resolve())
            self.assertIn("--no-session", command)
            self.assertIn("--no-context-files", command)
            self.assertIn("--no-extensions", command)
            self.assertIn("--no-prompt-templates", command)
            self.assertIn("--no-skills", command)
            self.assertIn("--tools", command)
            self.assertIn("read,grep,find,ls", command)
            self.assertIn("--skill", command)
            skill_arg = command[command.index("--skill") + 1]
            self.assertTrue(skill_arg.endswith("skills/validate-skills/SKILL.md"))
            self.assertIn("--provider", command)
            self.assertIn("openrouter", command)
            self.assertIn("--model", command)
            self.assertIn("gpt-test", command)
            self.assertIn("--thinking", command)
            self.assertIn("low", command)
            prompt = command[-1]
            self.assertIn("SKILL_VALID_RESULT=", prompt)
            self.assertIn("skills/demo", prompt)

    def test_sentinel_parser_requires_final_line_schema_and_passed_checks(self):
        result = parse_sentinel_result(VALID_SENTINEL, expected_target="skills/demo")
        self.assertTrue(result.passed)
        self.assertEqual(result.payload["checks"][0]["id"], "spec")

        bad_outputs = [
            ("missing", "no sentinel\n", "sentinel"),
            ("not final", 'SKILL_VALID_RESULT={"status":"passed","target":"skills/demo","checks":[{"id":"x","status":"passed","message":"ok"}]}\ntrailing\n', "final"),
            ("malformed", "SKILL_VALID_RESULT={\n", "JSON"),
            ("missing fields", 'SKILL_VALID_RESULT={"status":"passed"}\n', "target"),
            ("empty checks", 'SKILL_VALID_RESULT={"status":"passed","target":"skills/demo","checks":[]}\n', "checks"),
            ("bad check", 'SKILL_VALID_RESULT={"status":"passed","target":"skills/demo","checks":[{"id":"x","status":"passed"}]}\n', "message"),
            ("top failed", 'SKILL_VALID_RESULT={"status":"failed","target":"skills/demo","checks":[{"id":"x","status":"passed","message":"ok"}]}\n', "status"),
            ("check failed", 'SKILL_VALID_RESULT={"status":"passed","target":"skills/demo","checks":[{"id":"x","status":"failed","message":"bad"}]}\n', "failed"),
            ("target mismatch", 'SKILL_VALID_RESULT={"status":"passed","target":"skills/other","checks":[{"id":"x","status":"passed","message":"ok"}]}\n', "target"),
        ]
        for label, stdout, expected in bad_outputs:
            with self.subTest(label=label):
                parsed = parse_sentinel_result(stdout, expected_target="skills/demo")
                self.assertFalse(parsed.passed)
                self.assertIn(expected, parsed.message)

    def test_validate_skills_gate_fails_closed_and_preserves_raw_artifacts_on_bad_live_result(self):
        bad_live_results = [
            ("nonzero", VALID_SENTINEL, 17, "exit"),
            ("missing sentinel", "prose only\n", 0, "sentinel"),
            ("failed check", 'SKILL_VALID_RESULT={"status":"passed","target":"skills/demo","checks":[{"id":"x","status":"failed","message":"bad"}]}\n', 0, "failed"),
        ]
        for label, stdout_text, returncode, expected in bad_live_results:
            with self.subTest(label=label), self.make_repo() as (tmp, root):
                target = self.write_valid_skill(root)
                artifact_base = root / "artifacts"
                deps, calls = self.passing_deps(pi_stdout=stdout_text, pi_returncode=returncode)

                code, result = validate_skill(
                    ValidationOptions(target, repo_root=root, allow_live_pi=True, artifact_base=artifact_base),
                    deps=deps,
                )

                self.assertEqual(code, 1)
                self.assertEqual(result["gates"]["validate_skills"]["status"], "failed")
                self.assertIn(expected, result["gates"]["validate_skills"]["message"])
                self.assertEqual(calls["eval"], [])
                self.assertIn("failure_artifacts", result)
                artifacts = Path(result["failure_artifacts"])
                self.assertTrue((artifacts / "validate_skills" / "stdout.txt").exists())
                self.assertTrue((artifacts / "validate_skills" / "stderr.txt").exists())

    def test_live_eval_gate_runs_only_required_suites_with_generated_with_skill_config_and_overrides(self):
        with self.make_repo() as (tmp, root):
            target = self.write_valid_skill(root)
            deps, calls = self.passing_deps()

            code, result = validate_skill(
                ValidationOptions(
                    target,
                    repo_root=root,
                    allow_live_pi=True,
                    provider="provider-x",
                    model="model-y",
                    thinking="medium",
                ),
                deps=deps,
            )

            self.assertEqual(code, 0)
            self.assertTrue(result["valid"])
            self.assertEqual([call["suite_name"] for call in calls["eval"]], ["workflow", "regression"])
            for call in calls["eval"]:
                self.assertTrue(call["require_real"])
                self.assertEqual(set(call["configurations"]), {"with_skill"})
                config = call["configurations"]["with_skill"]
                self.assertEqual(config["harness"], "pi")
                self.assertTrue(config["force_skill"])
                self.assertTrue(config["allow_live"])
                self.assertEqual(config["provider"], "provider-x")
                self.assertEqual(config["model"], "model-y")
                self.assertEqual(config["thinking"], "medium")
                self.assertNotIn("without_skill", call["configurations"])

    def test_live_eval_gate_strict_real_run_success_fails_skipped_failed_missing_or_synthetic_runs(self):
        bad_runs = [
            ("skipped", {"status": "skipped", "passed": None, "harness_mode": "real", "synthetic": False}, "skipped"),
            ("process_failed", {"status": "process_failed", "passed": None, "harness_mode": "real", "synthetic": False}, "process_failed"),
            ("content_failed", {"status": "passed", "passed": False, "harness_mode": "real", "synthetic": False}, "content"),
            ("synthetic", {"status": "passed", "passed": True, "harness_mode": "static", "synthetic": True}, "synthetic"),
            ("missing_runs", None, "missing"),
        ]
        for label, run_overrides, expected in bad_runs:
            with self.subTest(label=label), self.make_repo() as (tmp, root):
                target = self.write_valid_skill(root, regression=False)

                def eval_run(manifest_path, suite_name, result_root, configurations, *, require_real):
                    Path(result_root).mkdir(parents=True, exist_ok=True)
                    if run_overrides is None:
                        return {"suite": suite_name, "suite_type": "workflow", "status": "completed", "runs": []}
                    run = {
                        "case_id": "hello",
                        "configuration": "with_skill",
                        "status": "passed",
                        "passed": True,
                        "harness_mode": "real",
                        "synthetic": False,
                    }
                    run.update(run_overrides)
                    return {"suite": suite_name, "suite_type": "workflow", "status": "completed", "runs": [run]}

                deps, calls = self.passing_deps(eval_run=eval_run)
                code, result = validate_skill(
                    ValidationOptions(target, repo_root=root, allow_live_pi=True, artifact_base=root / "artifacts"),
                    deps=deps,
                )

                self.assertEqual(code, 1)
                self.assertEqual(result["gates"]["live_eval"]["status"], "failed")
                self.assertIn(expected, result["gates"]["live_eval"]["message"])
                self.assertIn("failure_artifacts", result)

    def test_success_deletes_temporary_artifacts_and_cheap_failure_creates_none(self):
        with self.make_repo() as (tmp, root):
            target = self.write_valid_skill(root)
            artifact_base = root / "artifacts"
            deps, calls = self.passing_deps()

            code, result = validate_skill(
                ValidationOptions(target, repo_root=root, allow_live_pi=True, artifact_base=artifact_base),
                deps=deps,
            )

            self.assertEqual(code, 0)
            self.assertNotIn("failure_artifacts", result)
            self.assertEqual(list(artifact_base.glob("skill-valid-*")), [])

        with self.make_repo() as (tmp, root):
            target = root / "skills" / "missing"
            artifact_base = root / "artifacts"
            deps, calls = self.passing_deps()

            code, result = validate_skill(
                ValidationOptions(target, repo_root=root, allow_live_pi=True, artifact_base=artifact_base),
                deps=deps,
            )

            self.assertEqual(code, 1)
            self.assertNotIn("failure_artifacts", result)
            self.assertFalse(artifact_base.exists())

    def test_tool_docs_and_wrapper_prompt_document_final_contract(self):
        readme = Path("tools/skill_valid/README.md").read_text()
        agents = Path("tools/skill_valid/AGENTS.md").read_text()
        wrapper = Path("tools/skill_valid/WRAPPER_PROMPT.md").read_text()
        language = Path("tools/skill_valid/UBIQUITOUS_LANGUAGE.md").read_text()

        self.assertIn("python3 -m tools.skill_valid", readme)
        self.assertIn("--allow-live-pi", readme)
        self.assertIn("provider", readme)
        self.assertIn("stdout JSON", readme)
        self.assertIn("failure_artifacts", readme)
        self.assertIn("Validation Gate", agents)
        self.assertIn("live-run safety", agents)
        self.assertIn("SKILL_VALID_RESULT=", wrapper)
        self.assertIn("Sentinel Line", language)


if __name__ == "__main__":
    unittest.main()
