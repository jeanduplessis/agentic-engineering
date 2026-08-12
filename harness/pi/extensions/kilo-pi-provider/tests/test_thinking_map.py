import json
import subprocess
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[5]
HELPER = REPO_ROOT / "harness" / "pi" / "extensions" / "kilo-pi-provider" / "thinking-map.ts"


class ThinkingMapTests(unittest.TestCase):
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

    def test_galaxy_without_none_marks_off_unsupported(self):
        script = textwrap.dedent(
            f"""
            import {{ getKiloThinkingLevelMap }} from {json.dumps(HELPER.as_uri())};
            const galaxy = getKiloThinkingLevelMap({{
                id: "kilo-internal/galaxy",
                opencode: {{
                    variants: {{
                        low: {{ reasoning: {{ enabled: true, effort: "low" }} }},
                        medium: {{ reasoning: {{ enabled: true, effort: "medium" }} }},
                        high: {{ reasoning: {{ enabled: true, effort: "high" }} }},
                    }},
                }},
            }});
            console.log(JSON.stringify({{
                galaxy,
                wouldSendNone: galaxy?.off !== null,
            }}));
            """
        )

        self.assertEqual(
            self.run_node(script),
            {
                "galaxy": {
                    "off": None,
                    "minimal": None,
                    "low": "low",
                    "medium": "medium",
                    "high": "high",
                    "xhigh": None,
                },
                "wouldSendNone": False,
            },
        )

    def test_maps_none_and_max_variants(self):
        script = textwrap.dedent(
            f"""
            import {{ getKiloThinkingLevelMap }} from {json.dumps(HELPER.as_uri())};
            console.log(JSON.stringify({{
                sol: getKiloThinkingLevelMap({{
                    id: "openai/gpt-5.6-sol",
                    opencode: {{
                        variants: {{
                            none: {{ reasoning: {{ enabled: false, effort: "none" }} }},
                            low: {{ reasoning: {{ enabled: true, effort: "low" }} }},
                            medium: {{ reasoning: {{ enabled: true, effort: "medium" }} }},
                            high: {{ reasoning: {{ enabled: true, effort: "high" }} }},
                            xhigh: {{ reasoning: {{ enabled: true, effort: "xhigh" }} }},
                            max: {{ reasoning: {{ enabled: true, effort: "max" }} }},
                        }},
                    }},
                }}),
                kimi: getKiloThinkingLevelMap({{
                    id: "kilo-internal/kimi-k3-fast",
                    opencode: {{
                        variants: {{
                            none: {{ reasoning: {{ enabled: false, effort: "none" }} }},
                            high: {{ reasoning: {{ enabled: true, effort: "high" }} }},
                            max: {{ reasoning: {{ enabled: true, effort: "max" }} }},
                        }},
                    }},
                }}),
                instant: getKiloThinkingLevelMap({{
                    id: "example/instant",
                    opencode: {{
                        variants: {{
                            instant: {{ reasoning: {{ enabled: false, effort: "none" }} }},
                            low: {{ reasoning: {{ enabled: true, effort: "low" }} }},
                        }},
                    }},
                }}),
                empty: getKiloThinkingLevelMap({{ id: "example/empty", opencode: {{ variants: {{}} }} }}) ?? null,
                deepseek: getKiloThinkingLevelMap({{ id: "deepseek/deepseek-v4-pro" }}),
            }}));
            """
        )

        self.assertEqual(
            self.run_node(script),
            {
                "sol": {
                    "off": "none",
                    "minimal": None,
                    "low": "low",
                    "medium": "medium",
                    "high": "high",
                    "xhigh": "xhigh",
                },
                "kimi": {
                    "off": "none",
                    "minimal": None,
                    "low": None,
                    "medium": None,
                    "high": "high",
                    "xhigh": "max",
                },
                "instant": {
                    "off": "none",
                    "minimal": None,
                    "low": "low",
                    "medium": None,
                    "high": None,
                    "xhigh": None,
                },
                "empty": None,
                "deepseek": {
                    "minimal": None,
                    "low": None,
                    "medium": None,
                    "high": "high",
                    "xhigh": "max",
                },
            },
        )
