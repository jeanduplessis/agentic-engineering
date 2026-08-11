import json
import subprocess
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[5]
HELPER = REPO_ROOT / "harness" / "pi" / "extensions" / "pi-ui-customization" / "skill-read.ts"


class SkillReadTests(unittest.TestCase):
    def run_node(self, script: str) -> object:
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

    def test_detects_skill_md_paths_only(self):
        script = textwrap.dedent(
            f"""
            import {{ isSkillReadPath }} from {json.dumps(HELPER.as_uri())};
            console.log(JSON.stringify({{
                file: isSkillReadPath("SKILL.md"),
                nested: isSkillReadPath("skills/local-development/SKILL.md"),
                windows: isSkillReadPath(String.raw`skills\\local-development\\SKILL.md`),
                lowercase: isSkillReadPath("skills/local-development/skill.md"),
                agents: isSkillReadPath("AGENTS.md"),
                similarlyNamed: isSkillReadPath("SKILL.md.bak"),
                empty: isSkillReadPath(""),
            }}));
            """
        )

        self.assertEqual(
            self.run_node(script),
            {
                "file": True,
                "nested": True,
                "windows": True,
                "lowercase": False,
                "agents": False,
                "similarlyNamed": False,
                "empty": False,
            },
        )

    def test_replaces_only_matching_background_ansi(self):
        script = textwrap.dedent(
            f"""
            import {{ replaceBackgroundAnsi }} from {json.dumps(HELPER.as_uri())};
            const fromAnsi = "\\x1b[48;2;40;50;40m";
            const toAnsi = "\\x1b[48;2;45;40;56m";
            const line = fromAnsi + "[skill] local-development\\x1b[49m";
            const other = "\\x1b[48;2;40;40;40munchanged\\x1b[49m";
            console.log(JSON.stringify({{
                replaced: replaceBackgroundAnsi(line, fromAnsi, toAnsi),
                unchanged: replaceBackgroundAnsi(other, fromAnsi, toAnsi),
                same: replaceBackgroundAnsi(line, fromAnsi, fromAnsi),
                emptyFrom: replaceBackgroundAnsi(line, "", toAnsi),
            }}));
            """
        )

        self.assertEqual(
            self.run_node(script),
            {
                "replaced": "\x1b[48;2;45;40;56m[skill] local-development\x1b[49m",
                "unchanged": "\x1b[48;2;40;40;40munchanged\x1b[49m",
                "same": "\x1b[48;2;40;50;40m[skill] local-development\x1b[49m",
                "emptyFrom": "\x1b[48;2;40;50;40m[skill] local-development\x1b[49m",
            },
        )
