# Measured diagnosis — 2026-09-17

## Contrast (`Tools/contrast/measure_contrast.py` → `contrast-2026-09-17.json`)

74 (fg,bg) pairs, day+night, from grep-verified call sites. **17 fail** (min 4.5:1):

- 15/17 are the literal `.white` (SwiftUI, not `Theme.white`) risk-tier chips at
  `KBLIRegistryView.swift:1541` (0.55 fill) and `:1708` (0.45 fill) — **day is worse than
  night** (2.06–2.62:1 vs 3.22–4.43:1), the opposite of the 06-24 review's night-only framing.
- 2/17 (`pmaClosed`, `riskHigh` StatusBadge text on their own 10%-tint fill, night) miss by
  0.07:1 — effectively borderline, not the 2.2–2.9:1 the review measured.
- 3 pairs pixel-cross-checked against `baseline-2026-09-17/detail-card-day-en.png`: sampled
  ratios ran 0.6–1.5:1 higher than computed (decorative wash + AA blending), same pass/fail verdict.

## Truncation (`truncation-2026-09-17.json`)

**25 grep hits**, not "seven": 21 are unreachable content caps (`lineLimit`/`truncationMode`,
no reveal control), 1 is reachable (`KBLIRegistryView.swift:1528`, a Button-driven disclosure),
2 are non-content (chat input auto-grow, an anti-wrap header label), 1 is a dead comment
(documents the REMOVED "+26 more" pattern). The "+N more" caption class itself is GONE —
`ExpandableList` (`Theme.swift`) ships a real "Show all N" button; confirmed live in
`dossier-day-en.png` ("Show all 6").

## States (`states-2026-09-17.json`)

20 empty-state branches + 2 hover states measured across 4 of 10 View files (Dossier,
DetailRich, Registry, VerdictSheet) — real conditionals (`EmptyView()`, hidden sections), not
silent blanks. **6 files (Chat/RegistryTable/DetailView/Root/Media/SearchList) were
inaccessible this run** — EPERM on every read path (cat/grep/cp/Read tool) across 5 retries,
consistent with sibling-worktree contention (cicatrix #5), not a stable rule: `stat` shows
those files sitting at the last-commit mtime while their 4 readable siblings carry a later one.
`.focusable`/`.focused`: zero hits in the 4 readable files; not checked in the other 6.

## C1 — pixel check, header region, 55101

Scanned `dossier-day-en.png` (top 62%) and `detail-card-day-en.png` (top 42%) for
`Theme.pmaOpen` green (±35/channel): **0 matches in either** — `pmaClosed` red: 2970 / 1012
matches. So the review's "green/open badge" is not literally present as a color swatch.
**But** the contradiction is textual and still measured: the stat strip reads "Open · 100% /
MAX FOREIGN" in plain ink (`#2C2A28`, sampled) directly under the red "HEADS UP — A PT PMA
cannot register this code in Bali" banner, same viewport, both PNGs. **C1 = true (textual, not
chromatic) on both.**
