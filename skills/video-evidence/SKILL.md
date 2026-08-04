---
name: video-evidence
user-invocable: false
description: Record, edit, and validate concise video evidence of a product workflow. Use when asked to capture a walkthrough, browser journey, manual verification video, demo recording, or before/after behavior, whether the artifact will remain local or be published later. Uses agent-browser for browser capture and FFmpeg/ffprobe for truthful editing and technical validation.
---

# Video evidence

Produce evidence, not a recording of the testing process. Show the initiating action, meaningful state changes, and readable
outcome. Exclude setup noise, misleading edits, and exposed data.

## Non-negotiable rules

Preparation:

- Dry-run the journey before recording.
- Keep media outside the repository unless the user asks to commit it.
- Record one journey per clip. Split personas, permissions, viewports, and unrelated scenarios.

Integrity and privacy:

- Use one source take per final clip and preserve chronology.
- Never splice attempts, reorder events, or hide a failure/intervention that affected the outcome.
- Use freeze detection only to find review candidates, not automatic cuts.
- Inspect visually and validate technically before declaring an artifact ready.
- Exclude credentials, tokens, cookies, production data, unrelated private data, and authentication setup.

## 1. Load tools and choose external storage

Before any browser command, load the installed agent-browser workflow so commands match the installed version:

```sh
agent-browser skills get core --full
```

Require `agent-browser`, `ffmpeg`, and `ffprobe`. Use a temporary working directory outside the repository:

```sh
workdir=$(mktemp -d "${TMPDIR:-/tmp}/video-evidence.XXXXXX")
printf 'Video workspace: %s\n' "$workdir"
```

## 2. Define the proof

Write a short shot list for each clip before opening the browser:

1. Starting page and preconditions.
2. Initiating action.
3. Important confirmation, validation, loading, or intermediate state.
4. Final user-visible result.
5. Refresh, revisit, or navigation that proves persistence, when persistence is part of the claim.

Also state what the clip does **not** prove. Video supplements tests; it does not establish behavior outside the shown account,
viewport, data, and path.

Do not add unrelated navigation, title cards, narration, or repeated clicks merely to make a video feel complete.

## 3. Prepare and dry-run

Environment:

- Start or reuse the required services and verify the actual application URL/port.
- Create accounts, seed fixtures, set permissions and feature flags, and prepare repeatable state.
- Prefer supported fixtures or seed commands over ad hoc database edits.
- Use dedicated non-production test data and credentials.
- Set a consistent viewport, normally `1440 900`, unless mobile or responsive behavior is the proof.

Dry run:

- Run the entire journey without recording.
- Verify selectors, button state, dialogs, redirects, external calls, final state, persistence, and unrelated errors.
- Reset state if the action is not repeatable.

Do not record service startup, seeding, login, account creation, debugging, selector repair, failed attempts, credential
retrieval, or logs.

## 4. Record deliberately

Navigate to the ready starting page before recording. Use a named session consistently:

```sh
agent-browser --session "$session" set viewport 1440 900
agent-browser --session "$session" record start "$workdir/journey-raw.webm"
# perform only the dry-run journey
agent-browser --session "$session" record stop
```

For each proof point:

1. Hold the initial state for about 1 second.
2. Perform the action once.
3. Wait for the visible state change by element, text, URL, or condition instead of a long fixed sleep.
4. Hold ordinary results for 1-2 seconds and dense results for up to 3-4 seconds.
5. Stop as soon as the final proof is readable.

Do not leave recording active during static waits, repeated snapshots, log inspection, manual repair, or irrelevant
navigation. For a long-running operation, retain submission, initial progress, and completion; remove only the static middle wait.

If sensitive entry is unavoidable, stop recording first. Enter the value through a user-approved secret-safe mechanism that
does not place it in command source, shell history, logs, or tool output. Start a new clip only after the value is masked or
cleared. Never weaken application masking or logging for the demo.

If the recorded run needed troubleshooting or material intervention, discard it, restore state, and record a clean take.
Editing must not turn a failed or assisted run into apparent end-to-end success.

## 5. Inspect raw footage

Check metadata and decode the entire file:

```sh
ffprobe -v error \
  -select_streams v:0 \
  -show_entries stream=codec_name,width,height,pix_fmt \
  -show_entries format=filename,duration,size \
  -of json \
  "$workdir/journey-raw.webm"

ffmpeg -v error -i "$workdir/journey-raw.webm" -f null -
```

Find candidate static intervals:

```sh
ffmpeg -hide_banner -i "$workdir/journey-raw.webm" \
  -vf "freezedetect=n=0.002:d=1.5" -an -f null - 2>&1 \
  | grep -E 'freeze_(start|duration|end)' || true
```

Build a 12-frame contact sheet spanning the whole clip:

```sh
duration=$(ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 "$workdir/journey-raw.webm")
interval=$(awk -v d="$duration" 'BEGIN { print (d > 0 ? d / 12 : 1) }')
ffmpeg -y -i "$workdir/journey-raw.webm" \
  -vf "fps=1/${interval},scale=480:-2,tile=4x3:padding=4" \
  -frames:v 1 "$workdir/journey-raw-contact-sheet.png"
```

Inspect the contact sheet with an image-capable viewer. Watch or sample the source around each action and proposed cut. The
sheet should show context, initiation, meaningful transition, result, and persistence where claimed. Adjacent duplicate frames
suggest dead time, but a static confirmation may still be necessary evidence.

## 6. Edit by semantic transitions

Prefer a clean re-record when cuts could confuse the story. Otherwise, choose explicit source intervals from the same take.
Keep a short lead-in, the interaction/transition, and a readable hold. Preserve interval order.

Example for a silent recording with broad browser compatibility:

```sh
ffmpeg -y -i "$workdir/journey-raw.webm" \
  -filter_complex "\
[0:v]trim=start=0:end=4,setpts=PTS-STARTPTS[v0];\
[0:v]trim=start=14:end=20,setpts=PTS-STARTPTS[v1];\
[0:v]trim=start=31:end=38,setpts=PTS-STARTPTS[v2];\
[v0][v1][v2]concat=n=3:v=1:a=0,\
scale=trunc(iw/2)*2:trunc(ih/2)*2[v]" \
  -map "[v]" -an \
  -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p \
  -movflags +faststart \
  "$workdir/journey-final.mp4"
```

Replace the ranges with observed semantic boundaries. Do not blindly remove every freeze or speed up the whole clip. Keep
audio only when narration/audio is part of the requested proof and has passed the same privacy review; otherwise use `-an`.

Typical targets, not hard limits:

- Small journey: 15-30 seconds.
- Multi-page journey: under 60 seconds when practical.
- Ordinary static hold: 1-2 seconds.
- Dense readable result: up to 3-4 seconds.

H.264 MP4 with `yuv420p` and `+faststart` provides broad playback compatibility. Reduce bitrate or raise CRF slightly only
when a destination has a size limit; do not sacrifice text legibility.

## 7. Validate the final artifact

Repeat metadata, full-decode, freeze, and contact-sheet checks on the final file.

Story and privacy:

- The first frame provides context and the ending remains readable.
- Each action has an understandable result and every claimed state is present.
- Cuts preserve truthful order and do not imply unperformed continuity.
- Text is legible at normal playback size.
- No secret, personal data, unrelated tab, notification, or debug output appears in sampled frames.

Technical:

- The video stream is H.264, dimensions are even, and pixel format is `yuv420p`.
- The entire file decodes without error.
- The file size fits any known destination limit.

Do not publish to a destination whose visibility is inappropriate for the footage.

## Output contract

Return one record per final clip:

```text
path: absolute path to the final artifact
label: short human-readable journey name
claim: behavior visibly demonstrated by this clip
limits: behavior or environments this clip does not prove
source_duration: raw duration in seconds
final_duration: edited duration in seconds
size_bytes: final file size
format: container, codec, dimensions, and pixel format
validation: full decode, contact-sheet inspection, legibility, chronology, and privacy results
repository_state: whether media was committed (normally no)
```

A publishing workflow may consume this record, but publication is outside this skill.

## Completion checklist

Capture:

- [ ] Shot list and proof scope were defined.
- [ ] State was deterministic and the journey dry-ran successfully.
- [ ] Setup, authentication, and debugging were not recorded.
- [ ] Independent journeys have separate clips.
- [ ] Final clips come from one take each and preserve chronology.
- [ ] Dead time was removed without cutting required context.

Validation:

- [ ] Raw and final videos were visually inspected and fully decoded.
- [ ] Final contact sheets cover the complete story.
- [ ] Format, legibility, size, chronology, and privacy checks passed.
- [ ] Media stayed outside the repository unless explicitly requested.
- [ ] Each clip has a complete output record.
