# Pi UI customization

This Pi UI customization makes clickable tool-output behavior more compact and readable in the fullscreen TUI. Collapsed tool output shows the command and the last visible output line with a darker left gutter and a separating space. Clicking it expands only that tool block; expanded output uses a lighter gutter, and clicking it collapses the block again. Completed successful `read` tool rows are also clickable when Pi omits its expansion hint. Successful reads of `SKILL.md` use the theme's purple custom-message background instead of the green tool-success background. Terminal image lines (Kitty graphics and iTerm2 inline images) are left unmodified so `read` can still render photos. `Ctrl+O` continues to toggle all tool output.

Inline `Agent` tool results are clickable across their rendered non-empty lines. When `@tintinweb/pi-subagents` is installed and the live subagent session is available, clicking an inline result opens its existing conversation viewer overlay. The integration is optional: if the package, registry record, or viewer cannot be loaded, the extension keeps normal tool-link behavior and shows a non-fatal notification.

It uses the fullscreen TUI's terminal mouse support, which is enabled in `settings.json` and requires `tuiMode: "fullscreen"`. Reload Pi with `/reload` after updating this extension.

## Validation

```sh
python3 -m unittest harness/pi/extensions/pi-ui-customization/tests/test_terminal_image_lines.py harness/pi/extensions/pi-ui-customization/tests/test_skill_read.py -v
```
