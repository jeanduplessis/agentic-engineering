import json
import subprocess
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[5]
HELPER = REPO_ROOT / "harness" / "pi" / "extensions" / "pi-ui-customization" / "tool-collapse.ts"


class ToolCollapseTests(unittest.TestCase):
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

    def test_edit_blocks_are_collapsed_and_clickable_by_default(self):
        script = textwrap.dedent(
            f"""
            import {{ decideToolCollapse }} from {json.dumps(HELPER.as_uri())};
            const collapsedEdit = decideToolCollapse({{
                toolName: "edit",
                expanded: false,
                isPartial: false,
                isError: false,
                hasExpandHint: false,
            }});
            const pendingEdit = decideToolCollapse({{
                toolName: "edit",
                expanded: false,
                isPartial: true,
                hasExpandHint: false,
            }});
            const expandedEdit = decideToolCollapse({{
                toolName: "edit",
                expanded: true,
                isPartial: false,
                isError: false,
                hasExpandHint: false,
            }});
            const failedEdit = decideToolCollapse({{
                toolName: "edit",
                expanded: false,
                isPartial: false,
                isError: true,
                hasExpandHint: false,
            }});
            console.log(JSON.stringify({{
                collapsedEdit,
                pendingEdit,
                expandedEdit,
                failedEdit,
            }}));
            """
        )

        self.assertEqual(
            self.run_node(script),
            {
                "collapsedEdit": {"clickable": True, "compact": True},
                "pendingEdit": {"clickable": True, "compact": True},
                "expandedEdit": {"clickable": True, "compact": False},
                "failedEdit": {"clickable": True, "compact": True},
            },
        )

    def test_existing_collapse_rules_stay_unchanged(self):
        script = textwrap.dedent(
            f"""
            import {{ decideToolCollapse }} from {json.dumps(HELPER.as_uri())};
            console.log(JSON.stringify({{
                hintedBash: decideToolCollapse({{
                    toolName: "bash",
                    expanded: false,
                    isPartial: false,
                    isError: false,
                    hasExpandHint: true,
                }}),
                shortBash: decideToolCollapse({{
                    toolName: "bash",
                    expanded: false,
                    isPartial: false,
                    isError: false,
                    hasExpandHint: false,
                }}),
                completedRead: decideToolCollapse({{
                    toolName: "read",
                    expanded: false,
                    isPartial: false,
                    isError: false,
                    hasExpandHint: false,
                }}),
                subagent: decideToolCollapse({{
                    toolName: "subagent",
                    expanded: false,
                    isPartial: false,
                    hasExpandHint: false,
                }}),
            }}));
            """
        )

        self.assertEqual(
            self.run_node(script),
            {
                "hintedBash": {"clickable": True, "compact": True},
                "shortBash": {"clickable": False, "compact": False},
                "completedRead": {"clickable": True, "compact": False},
                "subagent": {"clickable": True, "compact": False},
            },
        )
