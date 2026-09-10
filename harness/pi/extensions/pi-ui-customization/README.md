# Pi UI customization

User messages sit on the right, with text left-aligned inside the bubble so multiline prose and code stay readable. Short bubbles fit their longest rendered line plus horizontal padding, with one background-colored blank row above and below the text. Long messages wrap at 80% of the available width, capped at 88 columns; this wrapping limit has a 40-column minimum when space allows. Narrower terminals can use the full width. Pi still handles Markdown, theme colors, links, and prompt navigation (`Ctrl+Up` / `Ctrl+Down`); assistant messages, summaries, and custom messages keep their existing layout.

This Pi UI customization also makes clickable tool-output behavior more compact and readable in the fullscreen TUI. Every tool row is clickable and collapsed by default: the block normally shows the command and the last visible output line with a darker left gutter and a separating space. Clicking it expands only that tool block; expanded output uses a lighter gutter, and clicking it collapses the block again. Compaction summaries are also clickable and toggle Pi's native summary expansion. Successful text reads of `SKILL.md` show only `[skill] name` when collapsed, without a file-content preview, and use the theme's purple custom-message background instead of the green tool-success background. Ordinary built-in text reads also show only their title when collapsed; expanding either read shows the native output. Terminal image lines (Kitty graphics and iTerm2 inline images) are left unmodified so `read` can still render photos. `Ctrl+O` continues to toggle all tool output.

Successful built-in `edit` cards show only their title when collapsed, even when Pi's edit renderer owns its shell. Clicking or `Ctrl+O` reveals the native diff. Errors and partial results keep their existing output. Custom self-owned renderers retain their own framing and all safety/detail rows, including custom `edit` renderers.

Trailing blank lines in streamed text collapse to one padding row, preventing repeated height changes as the next line arrives. Expanded output keeps its original spacing. Image reads retain the colored bottom padding below the header, native image spacing, and image-height rows.

`subagent` tool results are clickable across their rendered non-empty lines and use the same collapse/expand behavior as other clickable tool rows. There is no in-process conversation viewer; missing viewer integrations stay a no-op.

It uses the fullscreen TUI's terminal mouse support, which is enabled in `settings.json` and requires `tuiMode: "fullscreen"`. Native URL links remain usable across tool redraws, session resets, and extension reloads.

Reload Pi with `/reload` after updating this extension. When upgrading from the URL-callback wrapping bug, restart Pi instead: `/reload` cannot recover an already-wrapped callback chain. Resume the session with `pi -c` from the same directory.

In Ghostty, Kitty, and Foot, hovering a clickable link or tool row shows a hand pointer in fullscreen mode. The pointer returns to the terminal default off-link, during text selection, on focus loss, and when Pi stops or reloads the extension. Hover targets follow redraws and scrolling. This uses [OSC 22 pointer shapes](https://ghostty.org/docs/vt/osc/22); other terminals, disabled mouse capture, and tmux/Screen/Zellij sessions keep their existing pointer behavior.

In Ghostty on macOS, hold `Shift+Command` to use native link handling while Pi captures mouse input in fullscreen mode. The extension does not change right-click menus.

## Validation

```sh
python3 -m unittest harness/pi/extensions/pi-ui-customization/tests/test_terminal_image_lines.py harness/pi/extensions/pi-ui-customization/tests/test_skill_read.py harness/pi/extensions/pi-ui-customization/tests/test_tool_collapse.py -v
node --test harness/pi/extensions/pi-ui-customization/tests/*.test.mjs
```

The Node tests use the locally or globally installed Pi SDK, without calling a model or opening a browser. They cover content-sized user bubbles, visible top and bottom padding, resizing, Unicode and ANSI widths, native prompt navigation and OSC 133 stripping, keyboard input, streaming layout, images, URL forwarding through Pi's real TUI proxy, and hover feedback through Pi's real fullscreen renderer with an in-memory terminal. Coverage includes redraws, scrolling, overlays, selection, lifecycle cleanup, and renderer replacement. After `/reload`, check user-message placement at wide and narrow terminal sizes and the visible hand pointer; the offline tests verify rendered lines and emitted controls, not terminal artwork. They explicitly skip when the SDK is unavailable.
