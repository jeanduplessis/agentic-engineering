import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[4]
WRAPPER = ROOT / "skill-factory" / "tools" / "skill_valid" / "skill_validate.sh"


class SkillValidateWrapperTests(unittest.TestCase):
    def run_wrapper_with_fake_skill_valid(self, payload: dict, *, exit_code: int = 0, wrapper_args=(), extra_env=None):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "skills" / "demo"
            target.mkdir(parents=True)
            fake_bin = tmp_path / "bin"
            fake_bin.mkdir()
            stub = fake_bin / "python3"
            stub.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"$1\" == \"-m\" && \"$2\" == \"tools.skill_valid\" ]]; then\n"
                "  printf '%s\\n' \"$*\" > \"$FAKE_SKILL_VALID_ARGS\"\n"
                "  printf '%s\\n' \"$FAKE_SKILL_VALID_JSON\"\n"
                "  exit \"${FAKE_SKILL_VALID_EXIT:-0}\"\n"
                "fi\n"
                f"exec {sys.executable!r} \"$@\"\n",
                encoding="utf-8",
            )
            stub.chmod(0o755)
            env = os.environ.copy()
            env.update(
                {
                    "NO_COLOR": "1",
                    "PATH": f"{fake_bin}{os.pathsep}{env.get('PATH', '')}",
                    "FAKE_SKILL_VALID_JSON": json.dumps(payload, separators=(",", ":")),
                    "FAKE_SKILL_VALID_EXIT": str(exit_code),
                    "FAKE_SKILL_VALID_ARGS": str(tmp_path / "args.txt"),
                }
            )
            env.update(extra_env or {})
            completed = subprocess.run(
                [str(WRAPPER), str(target), *wrapper_args],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            return SimpleNamespace(
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                skill_valid_args=(tmp_path / "args.txt").read_text(),
            )

    def test_wrapper_does_not_enable_live_execution_unconditionally(self):
        payload = {"valid": False, "target": "skills/demo", "gates": {}}

        default_run = self.run_wrapper_with_fake_skill_valid(payload, exit_code=1)
        live_run = self.run_wrapper_with_fake_skill_valid(payload, exit_code=1, wrapper_args=("--allow-live", "--harness", "kilo"))
        env_live_run = self.run_wrapper_with_fake_skill_valid(payload, exit_code=1, extra_env={"SKILL_VALID_ALLOW_LIVE": "1"})

        self.assertNotIn("--allow-live", default_run.skill_valid_args)
        self.assertIn("Deterministic validation only", default_run.stderr)
        self.assertIn("--allow-live", live_run.skill_valid_args)
        self.assertIn("--harness kilo", live_run.skill_valid_args)
        self.assertIn("--allow-live", env_live_run.skill_valid_args)

    def test_wrapper_runs_from_monorepo_root_with_skill_factory_python_path(self):
        payload = {"valid": True, "target": "skills/demo", "gates": {}}

        completed = self.run_wrapper_with_fake_skill_valid(payload)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(WRAPPER.is_relative_to(ROOT / "skill-factory" / "tools"))

    def test_friendly_wrapper_renders_llm_optimal_warn_findings_as_non_blocking(self):
        payload = {
            "valid": True,
            "target": "skills/demo",
            "gates": {
                "target": {"status": "passed", "message": "ok"},
                "skill_spec": {"status": "passed", "message": "spec ok"},
                "eval_manifest": {"status": "passed", "message": "ok"},
                "agents_md": {"status": "passed", "message": "ok"},
                "llm_optimal_check": {
                    "status": "warn",
                    "message": "LLM Optimal Check returned warnings.",
                    "details": {
                        "report": {
                            "status": "warn",
                            "score": 85,
                            "metrics": {"tokens": 123, "characters": 456},
                            "findings": [
                                {
                                    "rule_id": "REL002",
                                    "severity": "minor",
                                    "category": "reliability",
                                    "location": {"line": 7},
                                    "message": "Overlong workflow step.",
                                    "suggestion": "Split it into ordered actions.",
                                }
                            ],
                        }
                    },
                },
                "live_opt_in": {"status": "passed", "message": "ok"},
                "validate_skills": {"status": "passed", "message": "ok"},
                "live_eval": {"status": "passed", "message": "ok"},
            },
        }

        completed = self.run_wrapper_with_fake_skill_valid(payload, exit_code=0)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Skill validation passed", completed.stdout)
        self.assertIn("Skill spec", completed.stdout)
        self.assertIn("(skill_spec)", completed.stdout)
        self.assertIn("LLM optimal check", completed.stdout)
        self.assertIn("(llm_optimal_check)", completed.stdout)
        self.assertIn("optimization: status=warn score=85/100", completed.stdout)
        self.assertIn("REL002 [minor] line 7: Overlong workflow step.", completed.stdout)
        self.assertIn("suggestion: Split it into ordered actions.", completed.stdout)
        self.assertIn("Result: VALID", completed.stdout)
        self.assertNotIn("Result: INVALID", completed.stdout)

    def test_friendly_wrapper_exits_with_underlying_skill_valid_code(self):
        payload = {
            "valid": False,
            "target": "skills/demo",
            "gates": {
                "target": {"status": "passed", "message": "ok"},
                "skill_spec": {"status": "passed", "message": "spec ok"},
                "eval_manifest": {"status": "passed", "message": "ok"},
                "agents_md": {"status": "passed", "message": "ok"},
                "llm_optimal_check": {"status": "failed", "message": "LLM Optimal Check failed.", "details": {"report": {"status": "fail", "score": 60, "metrics": {}, "findings": []}}},
                "live_opt_in": {"status": "passed", "message": "ok"},
                "validate_skills": {"status": "not_run", "message": "not run"},
                "live_eval": {"status": "not_run", "message": "not run"},
            },
        }

        completed = self.run_wrapper_with_fake_skill_valid(payload, exit_code=1)

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Skill validation failed", completed.stdout)
        self.assertIn("LLM optimal check", completed.stdout)
        self.assertIn("Result: INVALID", completed.stdout)


if __name__ == "__main__":
    unittest.main()
