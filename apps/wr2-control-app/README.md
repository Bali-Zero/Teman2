# WR2 Control

A native **macOS 27 (Tahoe) SwiftUI** app to launch and monitor the Bali Zero **WR2 carousel
pipeline** in plain human language. Local-only, runs entirely on this Mac, drives the real
pipeline through the `claude` CLI. No cloud, no Anthropic SDK, no API keys.

![status](https://img.shields.io/badge/build-green-success) — 46 unit + 6 integration tests passing.

---

## Canonical source (2026-07-14)

**This directory (`apps/wr2-control-app/` in the `nuzantara` repo) is the canonical source.**
Per repo principle "WR2 codebase + Control app = UN organismo"
(`~/.claude/projects/-Users-nuzantara/memory/principle_wr2_codebase_app_indissoluble_2026_06_25.md`),
the app is not allowed to be an orphan unversioned fork of the pipeline it controls — it lives in
git, in this repo, like everything else the organism depends on.

**Vendoring history**: until 2026-07-14 this app's Swift source lived ONLY on disk at
`~/Desktop/WR2 Control.app.old-2026-07-11/wr2-control-app-caption-editor/`, in two diverged,
undeclared copies (classic HOME-fork, superscar #1 — `research/operations/2026-07-14-wr2-deep-audit.md`
§1a). The newer copy (`wr2-control-app/`, which had its **own standalone local git repo**, 23+
commits on `master`, no remote) was confirmed a strict superset of the older one — every line
present only in the older copy was a refactor already superseded by equivalent-or-better code in
the newer copy (verified file-by-file: `AppState.swift`, `ClaudeRunner.swift`,
`Conversationalist.swift`, `Localization.swift`, `QueueWriter.swift`, `Views/ReviewView.swift` —
zero unique functionality lost). That newer copy is what was vendored here. The standalone repo's
own 23+-commit history was **not** migrated commit-by-commit (no remote, no shared identity with
this repo's history) — if that history is wanted later, it can still be imported via
`git subtree`/`format-patch` from `~/Desktop/WR2 Control.app.old-2026-07-11/wr2-control-app-caption-editor/wr2-control-app/.git`
(untouched, left in place).

**Install target**: the compiled bundle you actually run stays at
`/Users/balizero/Desktop/WR2 Control.app` (outside git, like any build artifact — see `.gitignore`
in the `~/Desktop/wr2-control-app` dev-copy convention below). Build with `./build.sh`, install by
copying `build/WR2 Control.app` over `/Users/balizero/Desktop/WR2 Control.app`.

**Desktop copies are build artifacts / history, not sources of truth going forward.** The
`~/Desktop/WR2 Control.app.old-2026-07-11/` tree (both `Sources/` copies + the standalone `.git`)
was left untouched by this vendoring — cleanup/retirement of that tree is a separate, later
operator-gated step, not part of this commit.

---

## What it does

WR2 is the editorial-carousel pipeline behind Bali Zero's Instagram (`@balizero0`). It is **not**
an HTTP service — it's a Claude agent (`wr2-design-architect`) that fans out to 4 specialists
(brief → storyboard → images → layout → critic) and drops a finished carousel on disk.

WR2 Control wraps that agent so a non-developer can:

1. **Studio** — type *"fammi un carosello sul nuovo visto E33G"* and watch the pipeline run,
   step by step, in human language (no jargon). Live monitor reads the agent's real output.
2. **Caroselli** — browse every generated carousel with slide previews, topic, domain, and the
   critic's verdict. Click for the full slide deck + the brief facts.
3. **Revisione** — see what's waiting for approval in the review queue, interactively.

The app **consumes** the pipeline — it never rewrites it.

---

## Requirements

- **macOS 26/27**, Apple Silicon.
- The **`claude` CLI**, already logged in with the system OAuth (`CLAUDE_CODE_OAUTH_TOKEN` in the
  environment). The app shells out to it; it manages no secrets and uses **no** `ANTHROPIC_API_KEY`
  (in fact it strips that key from the child environment as defense-in-depth).
- An installed **Xcode(-beta).app** *somewhere on disk* (e.g. `~/Downloads/Xcode-beta.app`).
  It is **not** activated as the developer dir and **no `sudo`/`xcode-select` is run** — the build
  only borrows one dylib (`libSwiftUIMacros`) from it via a compiler flag, because the SwiftUI
  state macros (`@State`/`@StateObject`) cannot expand under Command-Line-Tools alone.
- The WR2 output dir on disk: `~/nuzantara/apps/war-room/output/`.

## Build & run

```bash
cd ~/Desktop/wr2-control-app
./build.sh        # compiles with swiftc → build/WR2 Control.app  (no Xcode project)
./run.sh          # build + open the app
```

## Tests

```bash
./test.sh             # 46 unit tests (Foundation core: parsing, resolver, reducer)
./test-integration.sh # 6 integration assertions — drives the REAL claude CLI (cheap prompt)
./liverun.sh "..."    # drives a FULL real WR2 carousel run through the production runner
```

### Screenshots without a screen-recording grant

```bash
"build/WR2 Control.app/Contents/MacOS/WR2Control" --snapshot _proof
# renders studio.png / gallery.png / review.png via SwiftUI ImageRenderer (no TCC grant needed)
```

---

## How it works (the wiring)

```
Studio text field ─► PromptBuilder ─► ClaudeRunner (Process)
                                          │  zsh -lc 'claude -p "<topic>"
                                          │     --agent wr2-design-architect
                                          │     --output-format stream-json --verbose'
                                          ▼
                              stdout (one JSON object / line)
                                          │
                              StreamEvent.parse  ──►  RunReducer  ──►  pipeline steps in the UI
                                          ▼
                              (the agent writes a carousel on disk)
                                          ▼
                       WarRoom.scanCarousels / readQueue  ──►  Gallery + Review views
```

### Real paths consumed (verified on disk)

| What | Path |
|---|---|
| Orchestrator agent | `~/.claude/agents/wr2-design-architect.md` |
| Generated carousels | `~/nuzantara/apps/war-room/output/carousel/<slug>/slides/NN.png` |
| Per-carousel brief | `…/carousel/<slug>/brief.json` |
| Review queue | `…/apps/war-room/output/queue/human-review-queue.json` |

## Source layout

```
Sources/
  WR2ControlApp.swift   @main App
  Models.swift          Run, RunStep, Carousel, ReviewItem (multi-schema)
  WarRoom.swift         path resolver + queue parser + carousel scanner
  StreamEvent.swift     stream-json decode + RunReducer (events → steps)
  ClaudeRunner.swift    Process wrapper, async stdout streaming
  AppState.swift        @MainActor ObservableObject orchestrator
  PromptBuilder.swift   human request → "design a carousel for <topic>"
  Theme.swift           Bali Zero brand tokens (antracite/yellow/red)
  Views/                RootView, StudioView, GalleryView, ReviewView
Tests/
  main.swift            unit harness (46 tests)
  integration/main.swift  live-CLI integration test
  liverun/main.swift    full real-run driver
```

## Design decisions & terrain hazards handled

- **No Xcode project / `xcodebuild`** — this machine has CLT only. `build.sh` compiles with
  `swiftc` and assembles the `.app` bundle by hand. SwiftUI macros are loaded from an installed
  Xcode bundle via `-external-plugin-path` (no privilege escalation).
- **Scar #1 (HOME-fork / path-drift)** — the queue JSON stores absolute paths under
  `/Users/nuzantara/…` (dead on this `balizero` machine). `WarRoom.resolveCarouselDir` never
  trusts them; it re-roots by slug against the live war-room dir.
- **Scar #9 (schema drift)** — the queue has ≥3 item shapes (legacy / FSM / hybrid, incl. both
  `canva_url` and `canva_design_url`). Every field decodes as optional; a partial mid-write read
  keeps the last good queue instead of flashing empty.
- **Scar #6 (anti-hallucination)** — the monitor only reflects state actually read from the
  agent's stdout and from disk. Malformed stream lines become `.unparsable`, never crash.

## Known limits

- A full carousel run takes ~15-30 min and costs OAuth quota (it's the real agent: NB queries +
  imagegen + render + critic). The Studio monitor reflects coarse steps; deep per-subagent detail
  is in the "Dettagli tecnici" raw log pane.
- Screen-recording of the live window from a terminal-launched session is blocked by macOS TCC
  (operator must grant Screen Recording to capture screenshots that way) — the app itself is
  unaffected; this only limits automated screenshotting.
- Instagram publishing stays behind an explicit operator gate (Legge 5). Before dry-run or
  publishing, the generated caption is loaded into an editable field and validated against
  Instagram's 2,200-character limit.

See `PROVENANCE.md` for the dependency/license posture (zero third-party code).
