# PROVENANCE — WR2 Control

App: **WR2 Control** — native macOS 27 (Tahoe) SwiftUI control panel for the Bali Zero WR2
editorial-carousel pipeline. Built 2026-06-21 on M5 (`balizero@Air-M5`), local-only.

## Dependencies

**ZERO third-party code.** The entire app is built on Apple system frameworks only:

| Component                        | Framework                                                | Why                             |
| -------------------------------- | -------------------------------------------------------- | ------------------------------- |
| App shell, windows, scenes       | SwiftUI                                                  | native macOS 27                 |
| Glass/depth/material, NSImage    | AppKit + SwiftUI                                         | native chrome                   |
| Subprocess launch + async stdout | Foundation `Process` / `FileHandle`                      | stdlib, no shell-out lib        |
| stream-json parse                | Foundation `JSONDecoder`, `JSONSerialization`            | the format is Claude Code's own |
| File watching                    | Foundation `DispatchSourceFileSystemObject` + timer poll | stdlib                          |
| Tests                            | XCTest                                                   | stdlib                          |

No license gate needed — nothing is vendored. No supply-chain surface.

## Build

No Xcode.app on this machine — only Command Line Tools. The app is compiled directly with
`swiftc` against the macOS 27 SDK and assembled into a `.app` bundle by `build.sh`. See README.

## What it consumes (verified on disk 2026-06-21)

- `claude` CLI v2.1.185 (OAuth MAX, `apiKeySource: none` — no `ANTHROPIC_API_KEY`, ban respected)
- agent `~/.claude/agents/wr2-design-architect.md` (`isolation: worktree`)
- `apps/war-room/output/carousel/<slug>/slides/NN.png` + `NN.html` + `brief.json` + `slides.json`
- `apps/war-room/output/queue/human-review-queue.json` (multi-schema, see Models.swift)

## Known terrain hazards baked into the code

- **#1 HOME-fork / path-drift**: queue JSON stores absolute paths under `/Users/nuzantara/...`
  (dead on M5 where user is `balizero`). `WarRoom.resolve()` never trusts absolute paths from the
  JSON — it re-roots every carousel/slides path against the live war-room dir by basename.
- **#9 schema drift**: queue items come in ≥3 shapes (legacy `id`/`critic_overall_verdict`,
  FSM `item_id`/`state`, hybrid). All fields decoded as optional.
- **#6 anti-hallucination**: the monitor only reflects state actually read from stdout/disk in
  the current run — never fabricated progress.
