# WR2 Instagram Caption Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the WR2 operator inspect and edit the generated Instagram caption before dry-run or publication, then deploy the verified app to Air-M5, Pro, and Mini.

**Architecture:** Keep `wr2_ig_caption.py` as the only caption author. Add caption-output and caption-file inputs to the existing remote publisher, then let SwiftUI load the default asynchronously and pass the approved text through a temporary UTF-8 file. The Fly endpoint remains unchanged.

**Tech Stack:** SwiftUI/macOS, Swift Foundation `Process`, Python 3.11+, argparse, pytest, existing Fly WR2 API.

## Global Constraints

- The explicit **Pubblica ora** click remains the final Legge 5 gate.
- Caption contents must never be interpolated into a shell command.
- Blank captions and captions longer than 2,200 characters are blocked.
- Existing unrelated changes in every checkout must be preserved.
- No backend schema or Instagram Graph API changes.

---

### Task 1: Remote publisher caption contract

**Files:**

- Modify: `/Users/balizero/Desktop/nuzantara/.worktrees/wr2-caption-editor/scripts/wr2_ig_publish_remote.py`
- Create: `/Users/balizero/Desktop/nuzantara/.worktrees/wr2-caption-editor/scripts/test_wr2_ig_publish_remote_caption.py`

**Interfaces:**

- Produces: `_resolve_caption(slug: str, caption_file: Path | None) -> str`
- Produces: CLI options `--print-caption` and `--caption-file PATH`

- [ ] Write pytest cases proving generated fallback, UTF-8 file override, blank-file rejection, and caption-only output without credentials or upload.
- [ ] Run the focused pytest file and verify RED because `_resolve_caption` and the new CLI arguments do not exist.
- [ ] Implement `_resolve_caption`, argparse options, and the early `--print-caption` return before slide discovery or credential lookup.
- [ ] Run the focused pytest file and verify GREEN.
- [ ] Commit the Python contract as `feat(wr2): accept operator-approved Instagram caption`.

### Task 2: Swift caption validation model

**Files:**

- Create: `/Users/balizero/Desktop/wr2-control-app-caption-editor/Sources/InstagramCaption.swift`
- Modify: `/Users/balizero/Desktop/wr2-control-app-caption-editor/Tests/main.swift`
- Modify: `/Users/balizero/Desktop/wr2-control-app-caption-editor/test.sh`

**Interfaces:**

- Produces: `InstagramCaption.maxLength == 2200`
- Produces: `InstagramCaption.isPublishable(_ text: String) -> Bool`
- Produces: `InstagramCaption.characterCount(_ text: String) -> Int`

- [ ] Add tests for whitespace-only, exactly 2,200 characters, and 2,201 characters.
- [ ] Run `./test.sh` and verify RED because `InstagramCaption` does not exist.
- [ ] Add the minimal Foundation-only validation type and include it in the test compilation list.
- [ ] Run `./test.sh` and verify GREEN.
- [ ] Commit as `feat(app): validate Instagram captions`.

### Task 3: Caption loading and safe publish handoff

**Files:**

- Modify: `/Users/balizero/Desktop/wr2-control-app-caption-editor/Sources/AppState.swift`

**Interfaces:**

- Produces: `loadInstagramCaption(slug:completion:)`
- Changes: `publishToInstagram(slug:caption:lang:confirm:)`

- [ ] Add a testable command/temporary-file helper assertion to the Swift harness before production changes and verify it fails.
- [ ] Implement async `--print-caption` loading with stdout/stderr separation so the editor receives caption text only.
- [ ] Write the approved caption to a unique temporary UTF-8 file; invoke the remote publisher with `--caption-file`; delete the file in both launch-failure and termination paths.
- [ ] Run `./test.sh` and verify GREEN.
- [ ] Commit as `feat(app): pass reviewed caption to Instagram publisher`.

### Task 4: SwiftUI caption editor

**Files:**

- Modify: `/Users/balizero/Desktop/wr2-control-app-caption-editor/Sources/Views/CarouselDetailView.swift`
- Modify: `/Users/balizero/Desktop/wr2-control-app-caption-editor/Sources/Localization.swift`

**Interfaces:**

- Consumes: `loadInstagramCaption`, `InstagramCaption.isPublishable`, and the caption-aware publish method.

- [ ] Add view state for caption text, loading, and load error.
- [ ] Load the generated caption when **Pubblica su IG** opens.
- [ ] Render a multiline `TextEditor`, `characters / 2200` counter, loading/error states, and disabled dry-run/publish controls.
- [ ] Keep the popover open after dry-run; close only on cancel or real publish.
- [ ] Run `./test.sh`, `./build.sh`, and a local UI inspection.
- [ ] Commit as `feat(app): edit caption before Instagram publish`.

### Task 5: Integration and fleet alignment

**Files:**

- Modify if needed: `/Users/balizero/Desktop/wr2-control-app-caption-editor/README.md`
- Deploy: `WR2 Control.app` to the appropriate local application location on Air-M5, Pro, and Mini.

- [ ] Run fresh Python focused tests, the full Swift unit suite, `git diff --check`, and `./build.sh`.
- [ ] Merge the isolated WR2 Control branch into the local master without touching the pre-existing untracked `wr2-design-handoff/` directory.
- [ ] Integrate the Nuzantara script commit through its isolated branch and preserve the main checkout state.
- [ ] Inspect Pro and Mini source/app destinations and stop on overlapping dirty changes.
- [ ] Synchronize committed sources, build or copy the verified app as appropriate, restart the app, and verify the installed binary/process on all three machines.
- [ ] Report exact commit IDs, test counts, app locations, and any machine that could not be reached.
