# Pi UI customization

This Pi UI customization makes clickable tool-output behavior more compact and readable in the fullscreen TUI. Every tool row is clickable and collapsed by default: the block shows the command and the last visible output line with a darker left gutter and a separating space. Clicking it expands only that tool block; expanded output uses a lighter gutter, and clicking it collapses the block again. Compaction summaries are also clickable and toggle Pi's native summary expansion. Successful reads of `SKILL.md` use the theme's purple custom-message background instead of the green tool-success background. Terminal image lines (Kitty graphics and iTerm2 inline images) are left unmodified so `read` can still render photos. `Ctrl+O` continues to toggle all tool output.

Trailing blank lines in streamed text collapse to one padding row, preventing repeated height changes as the next line arrives. Expanded output keeps its original spacing; image-height rows are preserved.

`subagent` tool results are clickable across their rendered non-empty lines and use the same collapse/expand behavior as other clickable tool rows. There is no in-process conversation viewer; missing viewer integrations stay a no-op.

It uses the fullscreen TUI's terminal mouse support, which is enabled in `settings.json` and requires `tuiMode: "fullscreen"`. Reload Pi with `/reload` after updating this extension.

## Validation

```sh
python3 -m unittest harness/pi/extensions/pi-ui-customization/tests/test_terminal_image_lines.py harness/pi/extensions/pi-ui-customization/tests/test_skill_read.py harness/pi/extensions/pi-ui-customization/tests/test_tool_collapse.py -v
node --test harness/pi/extensions/pi-ui-customization/tests/streaming-layout.test.mjs
```

The streaming-layout tests use the locally or globally installed Pi SDK, without calling a model. They explicitly skip when the SDK is unavailable.
