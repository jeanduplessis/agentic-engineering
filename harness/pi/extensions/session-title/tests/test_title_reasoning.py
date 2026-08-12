import json
import subprocess
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[5]
HELPER = REPO_ROOT / "harness" / "pi" / "extensions" / "session-title" / "title-reasoning.ts"


class TitleReasoningTests(unittest.TestCase):
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

    def test_picks_cheapest_supported_non_off_effort(self):
        script = textwrap.dedent(
            f"""
            import {{ titleReasoningEffort }} from {json.dumps(HELPER.as_uri())};
            console.log(JSON.stringify({{
                off: titleReasoningEffort({{ reasoning: false }}) ?? null,
                galaxy: titleReasoningEffort({{
                    reasoning: true,
                    thinkingLevelMap: {{
                        off: null,
                        minimal: null,
                        low: "low",
                        medium: "medium",
                        high: "high",
                        xhigh: null,
                    }},
                }}),
                sol: titleReasoningEffort({{
                    reasoning: true,
                    thinkingLevelMap: {{
                        off: "none",
                        minimal: null,
                        low: "low",
                        medium: "medium",
                        high: "high",
                        xhigh: "xhigh",
                    }},
                }}),
                highOnly: titleReasoningEffort({{
                    reasoning: true,
                    thinkingLevelMap: {{
                        off: "none",
                        minimal: null,
                        low: null,
                        medium: null,
                        high: "high",
                        xhigh: "max",
                    }},
                }}),
                unsetMap: titleReasoningEffort({{ reasoning: true }}) ?? null,
                noNonOff: titleReasoningEffort({{
                    reasoning: true,
                    thinkingLevelMap: {{
                        off: null,
                        minimal: null,
                        low: null,
                        medium: null,
                        high: null,
                        xhigh: null,
                    }},
                }}) ?? null,
            }}));
            """
        )

        self.assertEqual(
            self.run_node(script),
            {
                "off": None,
                "galaxy": "low",
                "sol": "low",
                "highOnly": "high",
                "unsetMap": "minimal",
                "noNonOff": None,
            },
        )
