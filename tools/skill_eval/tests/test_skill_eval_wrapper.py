import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WRAPPER = ROOT / "tools" / "skill_eval" / "skill_eval.sh"


class SkillEvalWrapperTests(unittest.TestCase):
    def run_wrapper_with_fake_skill_valid(self, payload: dict, *, exit_code: int = 0):
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
                }
            )
            return subprocess.run(
                [str(WRAPPER), str(target)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

    def test_friendly_wrapper_renders_llm_optimal_warn_findings_as_non_blocking(self):
        payload = {
            "valid": True,
            "target": "skills/demo",
            "gates": {
                "target": {"status": "passed", "message": "ok"},
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
