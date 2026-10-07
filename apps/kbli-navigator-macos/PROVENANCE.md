# PROVENANCE — KBLI Navigator

Native macOS (Tahoe / macOS 26) SwiftUI app for browsing KBLI 2025 codes with the Bali PMA
moratorium status, reading the Bali Threshold book + 20 articles, and chatting with a
KBLI-grounded Zantara. Built 2026-06-23/24 on M5 (`balizero@Air-M5`), runs on M5 + Pro + Mini.

## Reuse (reuse-first discipline)

| What                                                                                               | Source                                                            | License  | How                                                                                                                      |
| -------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------ |
| `Theme.swift`, `BZLogo`, `FactRule`, `GlassCard`                                                   | `~/Desktop/wr2-control-app` (internal Bali Zero repo, no LICENSE) | internal | copied + surgically forked (removed WR2 `stepColor`/`statusColor`/`zeroDesignStudioURL`; added `kbliStatusColor/Symbol`) |
| `build.sh` (swiftc + Xcode-beta macro plugin)                                                      | wr2-control-app                                                   | internal | adapted (renamed app/exec, +PDFKit framework)                                                                            |
| `Localization` (LanguageManager) pattern, `ChatView` shape, `OpenClawRunner` (from `ClaudeRunner`) | wr2-control-app                                                   | internal | re-implemented slim (no WarRoom/QueueWriter/AppState bloat)                                                              |
| Markdown rendering                                                                                 | NONE — vendored ~150-line block parser                            | ours     | `AttributedString(markdown:)` alone loses headings (spec §9 F3) → vendored `MarkdownParser`                              |
| Search / PDF                                                                                       | Apple frameworks (`.searchable`, `PDFKit`, `NavigationSplitView`) | system   | no SPM (build.sh constraint)                                                                                             |

Design research: `research/operations/2026-06-23-sota-macos-native-reference-app-design.md` (in the
nuzantara worktree). Top-5 reference apps: Dash, Bear, Reflect, Dictionary.app, Proxyman.

## Data

- `Resources/KBLI_2025_FINAL_CLEAN.json` — 1559 codes. Has `l4_bali` (Bali moratorium status,
  populated for all 1559), `per_skala`, `pma_status`, `ruang_lingkup`.

  **ANCHOR, 2026-09-13 (`k2/row-identity`, mission SAETTA-K2).** This file is now the monorepo
  CANONICAL, byte for byte, and it is committed rather than left to `build.sh` to sync:

  | what                | value                                                                                                                                                                                                                            |
  | ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
  | sha256              | `c69a260dba597d6b172996da7b99460f1498c3bb9d9df6f2ca6c9e4f782b2b40`                                                                                                                                                               |
  | canonical source    | `Bali-Zero/Teman2` `origin/main` `e35e22a21a`, identical bytes at `apps/mouth/data/KBLI_2025_FINAL_CLEAN.json` and `data/source_documents/KBLI_2025_FINAL_CLEAN.json`                                                            |
  | supersedes          | the committed `a5721756d5b2ea080e805eee582562d17eb16b9d33fc6f61ee227ccade25ca77` (pre-L2-re-ingestion)                                                                                                                           |
  | why it is committed | `docs/gates/ROW-IDENTITY-CONTRACT.md` §2: a `per_skala` ordinal is meaningless across datasets, so the benchmark's two halves must anchor the SAME bytes. A copy that `build.sh` may or may not have refreshed is not an anchor. |

  Two consequences, both MEASURED on this worktree, neither predicted:
  1. the L2 re-ingestion added a top-level `absent_probes` (an array of ISO probe dates) to 13
     records — 02202, 03223, 03232, 35131, 35132, 56400, 58120, 58130, 59111, 59121, 60102,
     66303, 74300. `KBLISchemaSnapshot` is fail-closed on unknown keys, so without listing it the
     builder REFUSES to serve those 13. It is listed, as the provenance metadata it is.
  2. the `l4_bali.blocked == true` census reads **519**, not the 518 the pre-L2 copy gave.
     Leftover L2, not a verdict-rule change; `Tests/verdicttest` follows the anchor.

- `Resources/articles/` (20) + `Resources/book-chapters/` (13) + 2 PDFs — from `KBLI-2025-Content/`.

## Chat brain

Single Zantara-KBLI on the Mini (OpenClaw `agent --agent zantara-kbli --json`, GPT-5.5). The app is
a dual-mode client (local on Mini, `ssh mini` from M5/Pro). NLM-style grounded: each turn injects a
local FONTI block so Zantara answers only from the real dataset. See `deploy/FASE0-openclaw-mini-status.md`.
Stable GPT-5.5 replies require an interactive `codex login` on the Mini (OAuth — operator only).

## Review

Spec reviewed by a severe 4-LLM panel (Gemini agy + DeepSeek V4 Pro + Codex). 3 FATAL incorporated
(F1 codex-not-chat → OpenClaw; F2 Gatekeeper re-sign; F3 vendored markdown). All findings verified
empirically in-turn. Built TDD: every task has standalone Swift tests under `Tests/`.

## Verification snapshots

`docs/snapshot-55203.png` (detail card: red badge + amber moratorium callout),
`docs/snapshot-article.png` (article markdown: H1/H2/bold/bullets rendered, not flat).
