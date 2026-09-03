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
                    "max": None,
                },
                "wouldSendNone": False,
            },
        )

    def test_maps_none_and_max_variants(self):
        script = textwrap.dedent(
            f"""
            import {{ getKiloThinkingLevelMap }} from {json.dumps(HELPER.as_uri())};
            console.log(JSON.stringify({{
                nova: getKiloThinkingLevelMap({{
                    id: "kilo-internal/nova",
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
                "nova": {
                    "off": "none",
                    "minimal": None,
                    "low": "low",
                    "medium": "medium",
                    "high": "high",
                    "xhigh": "xhigh",
                    "max": "max",
                },
                "kimi": {
                    "off": "none",
                    "minimal": None,
                    "low": None,
                    "medium": None,
                    "high": "high",
                    "xhigh": None,
                    "max": "max",
                },
                "instant": {
                    "off": "none",
                    "minimal": None,
                    "low": "low",
                    "medium": None,
                    "high": None,
                    "xhigh": None,
                    "max": None,
                },
                "empty": None,
                "deepseek": {
                    "minimal": None,
                    "low": None,
                    "medium": None,
                    "high": "high",
                    "xhigh": None,
                    "max": "max",
                },
            },
        )

    def test_extended_variants_preserve_provider_efforts(self):
        script = textwrap.dedent(
            f"""
            import {{ getKiloThinkingLevelMap }} from {json.dumps(HELPER.as_uri())};
            const variants = {{
                xhigh: {{ reasoning: {{ effort: "provider-xhigh" }} }},
                max: {{ reasoning: {{ effort: "provider-max" }} }},
            }};
            const both = getKiloThinkingLevelMap({{
                id: "example/mapped-efforts", opencode: {{ variants }},
            }});
            delete variants.max;
            const withoutMax = getKiloThinkingLevelMap({{
                id: "example/mapped-efforts", opencode: {{ variants }},
            }});
            console.log(JSON.stringify({{
                both: {{ xhigh: both.xhigh, max: both.max }},
                withoutMax: {{ xhigh: withoutMax.xhigh, max: withoutMax.max }},
            }}));
            """
        )

        self.assertEqual(
            self.run_node(script),
            {
                "both": {"xhigh": "provider-xhigh", "max": "provider-max"},
                "withoutMax": {"xhigh": "provider-xhigh", "max": None},
            },
        )
