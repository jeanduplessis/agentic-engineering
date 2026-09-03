# Prompt stash

Temporarily set aside a chat draft so you can ask another question.

## Enable

Run `./setup.sh` from the repository root. Select **Harness → extensions → prompt-stash**, then run `/reload` in Pi. Selection is opt-in. No build or `npm install` is needed.

## Use

1. Write a draft in the main chat editor.
2. Press **Cmd+Shift+S**. The draft moves into one in-memory slot and the editor becomes empty. Pi's built-in footer shows `Prompt stashed`, without the draft content. Custom footers must opt in to displaying it.
3. Type and submit another chat message. The draft returns to the editor before Pi starts processing that message. It is **not sent**; keep editing it or submit it yourself later.

Press Cmd+Shift+S with an empty editor to restore manually. If both the editor and stash contain text, the extension keeps both and shows a warning. It does not stack or overwrite drafts. An empty editor with no stash does nothing. Whitespace-only drafts count as text.

If you type new text before an automatic restore can run, the extension leaves the stash pending rather than replacing your text. Clear the editor when safe, then press Cmd+Shift+S to restore.

## Footer integration

Stash presence is available through Pi's existing extension-status API:

```ts
const hasPromptStash = footerData.getExtensionStatuses().has("prompt-stash");
```

The stable key is `prompt-stash`. It is present while a draft is stashed, including when restoration is blocked or fails. It is removed after successful automatic/manual restoration or session lifecycle reset. Consumers should check key presence, not parse the display text. No draft text or preview is exposed.

Pi requests a render when the status changes, so a custom footer can read this value in its render function. This extension does not modify the repository's `custom-footer`; its stash display can be added separately.

## Compatibility and limits

- The registered shortcut is `super+shift+s`. On macOS, Super is Command. Your terminal must forward this combination through the **Kitty keyboard protocol**, including the Super modifier. A terminal or OS shortcut can intercept it. Support for Shift+Enter alone does not prove Command forwarding works. This extension makes no terminal or keybinding configuration changes and adds no fallback shortcut.
- Checked against **Pi 0.84.4** with its default editor. Pi clears that editor before the interactive `input` hook, so restoration needs no timer. Normal submissions, mid-response steering, and follow-up submissions use this hook. A follow-up draft returns when the follow-up is submitted, not when its eventual reply starts.
- Local built-in commands, registered extension commands, and `!`/`!!` shell commands bypass the normal chat input hook and do not consume the stash. Session-changing commands still discard it as described below. Skills and prompt templates that pass through the hook can trigger restoration.
- Input queued during compaction can reach the hook later. Some compaction/retry queue paths bypass it entirely, leaving the stash pending. An earlier extension that handles input can also prevent this hook from running. Use manual restore in these cases. Other extensions can still change the editor after this extension runs.
- Only interactive TUI input can trigger restoration. RPC, print/JSON modes, and extension-injected messages cannot consume a stash.
- The stash preserves the exact text returned by Pi's editor API, including leading/trailing whitespace, blank lines, and expanded large-paste content. Pi already normalizes tabs and line endings as text enters its default editor. Restored large pastes appear as full text, not collapsed markers. Cursor position, selection, undo history, and attachments are not stashed.
- A custom editor must support Pi's editor text API and clear before submission. If a restore fails or does not round-trip exactly, the extension keeps its copy and warns. Custom editors are not otherwise verified.

## Draft lifetime and privacy

The slot belongs to one extension instance and session. **Reloading, starting or switching sessions, forking/cloning, or exiting discards an unrestored stash.** Restore or save important text first. This is a temporary convenience, not a backup.

The extension does not persist or log drafts, add them to session entries, or send them to the model. It only writes a draft back into the editor. Notifications and status text contain no draft content. Pi's normal editor behavior and other extensions remain outside this guarantee.

## Check

Run offline tests from the repository root with Node.js 24 or newer:

```sh
node --test harness/pi/extensions/prompt-stash/tests/*.test.mjs
```

Handler tests run without Pi. Runtime tests discover an existing local or global Pi SDK and explicitly skip if none is installed. They use Pi's loader, shortcut routing, editor, and input preflight with fake delivery endpoints; no terminal session, credentials, or model request is needed.

Manual smoke check in your own Pi session:

1. Paste a multiline draft with blank lines and trailing spaces. Press Cmd+Shift+S and check that the editor empties. With Pi's built-in footer, also check that the status appears.
2. Submit a short question. Check that the question alone enters chat, while the full draft returns to the editor before the reply.
3. Stash it again, type different text, and press Cmd+Shift+S. Check that the new text stays and a warning appears. Clear the editor, then press the shortcut to recover the draft.
4. Repeat with an empty editor to check manual restore. If the shortcut never fires, check your terminal's Command-key forwarding before using important text.
