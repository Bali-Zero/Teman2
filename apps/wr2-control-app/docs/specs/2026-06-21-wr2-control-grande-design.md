# WR2 Control "grande" — design spec

- **Date:** 2026-06-21
- **Author:** Claude (Opus 4.8) + Antonello (Zero)
- **Status:** approved (all 6 sections), ready for implementation plan
- **App location:** `~/Desktop/wr2-control-app/` (native SwiftUI, ISOLATED — not in nuzantara monorepo)
- **Approach chosen:** A — incremental evolution of the existing prototype (not rewrite)

## Goal

Turn the working WR2 Control prototype into a "grande" native macOS app: one Swift binary
running on M5 + Pro + Mini. The Mini (server H24, already wired to a 4K TV) becomes the
shared office postazione-TV for the Bali Zero editorial team. Dual-mode: ambient editorial
wall (viewed from afar) + hands-on work mode (up close). No login (the team is trusted —
"tutti fanno tutto"). Heart of the app: **carousel COVERS shown next to their real Instagram
RESULTS**, closing the long-broken "last mile" feedback loop.

## Hard boundaries (unchanged from original mandate)

- Native SwiftUI, confined to the Bali Zero fleet (M5/Pro/Mini). NO git push / PR / deploy /
  Instagram publish from the app.
- Wraps the `claude` CLI as subprocess (MAX OAuth). NO Anthropic SDK, NO `ANTHROPIC_API_KEY`.
- Does NOT modify the WR2 pipeline or the off-limits files.
- "Mark as published" is a LOCAL state change — it never posts to Instagram (Legge 5).

## Why this matters beyond UI (the discovery that reframed the spec)

The WR2 "results analysis → market-driven calibration" loop EXISTS in code but is starved:

- `meta_graph_sampler.py` (official Meta Graph API, tested) reads **shares/saves/reach/
  impressions/likes/comments** and writes them to table `war_room_metrics`. This is the
  OFFICIAL path (Meta verified + official IG/WA bots) — the old Playwright DOM scraper only
  got likes+comments and is now obsolete for metrics.
- `_reflexion-synthesis.py` turns metrics into lessons → agent amendments.
- BUT: 0 carousels are in `published` state (queue has 53 items, 43 stuck at
  `applied_ready_for_damar`) → sampler has no targets → 0 metrics → reflexion correctly
  gates "insufficient data" → loop open. WR2 produces but never learns from the market.

The missing link is a human gesture: "this one I published". This app provides it
(mark-published + IG media id), which feeds the sampler that already exists, which closes
the loop. The app does not rewrite the loop — it FUELS it and SHOWS its fruit.

References (memory): discovery-wr2-last-mile-loop-exists-but-starved,
discovery-meta-graph-sampler-official-insights, decision-wr2-control-native-swift-fleet-mini-tv.

---

## Section 1 — Architecture (dual-mode + shared core)

One Swift binary, Foundation-pure where it must be (CLI tests). Two faces over one state:

- **Work mode** (up close, mouse/keyboard): left sidebar with 6 sections + IT/ID switch +
  live status dot. Dense, full workflow.
- **Ambient mode** (TV, 3–4m): no sidebar, full-screen editorial wall.
- **Toggle:** manual button always available + auto-enter ambient after ~3 min idle
  (configurable); any input returns to work. ("screensaver vivo" behavior.)

Shared core (UNCHANGED, reused as-is): `AppState`, `ClaudeRunner` (CLI wrap),
`StreamEvent`/`RunReducer` (parse), `WarRoom` (disk resolver), `Theme`, `Localization`.
Both modes read the SAME `AppState` — no duplicated data, no second poller. Ambient is just
a different layout + a Timer rotating the cover index.

No login, no server: everything reads/writes local disk. Per-machine path-drift
(`/Users/balizero` vs `/Users/nuzantara`) handled by the WarRoom resolver (to be hardened).

## Section 2 — Cover & Results (the heart)

Data model per carousel (read from disk):

- cover → `slides/1.png` (resolve order: `slides/1.png` → `slides/01.png` →
  `<slug>-editorial.png`; real image, no gray placeholder)
- slides[] → `slides/2..N.png` (thumbnails, swipeable)
- title/domain/facts/numbers → `brief.json`
- critic verdict → critic json / queue (PASS/FAIL + reason)
- publish state → queue: drafted / approved / PUBLISHED
- **results** → table `war_room_metrics` (written by the official sampler):
  🔁 shares (KING metric, shown first), ❤ likes, 💬 comments, 💾 saves, 👁 reach, 📊 impressions

Three surfaces, same data:

- **A) Covers gallery** — grid of real covers, each with a result/state badge. Sortable:
  most viral / most recent / awaiting / to redo. Click → carousel view.
- **B) Carousel view** — big cover left, results panel right (shares on top), critic verdict,
  facts, slide thumbnails. Empty states are honest: "not yet published" → "awaiting
  measurement (~24h)" → real metrics. If unpublished: shows mark-published action.
- **C) Ambient** — uses the same big cover, rotating (Section 3).

Fix that unlocks it: today covers show gray placeholders due to path-drift + multi-schema
queue. Harden WarRoom: resolve cover paths relative to the real machine root; tolerate the
≥3 queue item shapes. This same fix makes the app work identically on the Mini.

Metrics are 0 today (loop starved) → most carousels will honestly read "not yet published"
at first. Correct, not a bug.

## Section 3 — Ambient (the living editorial TV)

Full-screen, activates on toggle or ~3 min idle; any input returns to work.

- Covers cycle one at a time, slow (~8–10s), soft cross-fade. Default selection rule:
  **most viral of the last ~240 days** (sort: shares↓ then reach↓) among published.
  Honest fallback (today's reality): most-recent covers with critic PASS, labeled "awaiting
  numbers". Degrades automatically — no code change when metrics arrive.
- Beside the cover: that cover's results (shares first) + one editorial line ("most shared
  this week" / "just published" / "awaiting numbers").
- Bottom ribbon ALWAYS: what's running NOW (live progress bar from the same RunReducer) +
  counters (awaiting, published, avg shares this week).
- If a run is in progress, it takes priority: a large "a carousel is being born" indicator
  with steps checking off live.
- Readable from 3–4m: big type, high contrast (antracite/yellow/white), zero small text.

Implementation: a SwiftUI View reading the same AppState. A Timer rotates the cover index.
No new core logic.

## Section 4 — Mark-published & last-mile closure

From carousel view (or Review). The gesture:

1. Paste the IG post link (or media id) + publish date.
2. Extract the **media id**; write ONLY to local `human-review-queue.json`: advance that
   item to `published`, save `ig_url`, `ig_media_id`, `published_at`.
3. Done. No network, no posting.

Then existing machinery takes over (NOT written here):
sampler (`meta_graph_sampler.py`, cron Pro) reads published items → fetches insights from
Meta → writes `war_room_metrics` → app reads them (Section 2) → weekly Reflexion → agent
amendments.

- **Reversible:** "undo publish" restores prior state and CLEARS `ig_media_id`/`published_at`
  so the sampler stops measuring it.
- **Safe queue write** (scar #9 schema-drift): atomic write (tmp + rename); preserve unknown
  fields; modify ONLY the 4 publish-state fields, never rewrite the item (scar #5 — never
  destroy sibling work in flight).

Constraints respected: Legge 5 (mark ≠ publish), confined (local JSON, no token, no git),
reversible (nothing destructive).

## Section 5 — History & pipeline metrics

Production control panel (distinct from market results of Section 2):

- Three big numbers up top: runs this month, % critic PASS first-try, avg duration.
- Sober list: date, topic, critic result (PASS/FAIL), # slides, duration, cost if available.
  Click a run → opens its carousel view.
- Data source: `AppState.pastRuns` (session) + `wr2-episodic.db → carousel_runs` (history
  beyond session). No charts in v1 — premature while metrics bootstrap; add later when there
  is real data to plot.

## Section 6 — Mini deployment + Desk icons

- **Build:** compile on M5 (existing `build.sh`: swiftc + manual `.app` bundle + macro plugin
  from Xcode-beta), then COPY the finished `.app` to the Mini (arm64, same arch, runs
  identically). The Mini need not compile. Verify the `.app` actually launches on the Mini.
- **Postazione-TV (Mini):** LaunchAgent so it auto-starts on boot (Mini is H24), opens
  full-screen on the 4K TV, default ambient mode.
  - scar W84: LaunchAgent + wrapper must NOT live under `~/Desktop` (launchd loses the TCC
    grant there → green-but-dead). Put under `~/Library/LaunchAgents` + wrapper outside
    `~/Desktop`.
  - scar #7: no `KeepAlive` on a one-shot; use the correct daemon nature.
- **Desk icons (M5, Pro):** a "WR2 Control" icon on the Desktop opening the LOCAL `.app`
  (native double-click). The `.app` already carries its BZ icon (`--makeicon`).
- **Cross-machine data coherence (open node):** the app reads covers/queue/metrics from disk;
  authoritative queue + metrics live on the Pro (where pipeline + sampler run). Decide in
  implementation whether the Mini app reads Pro data via sync/mount or a local copy. This is
  the ONE node not closed in design — resolve as first implementation task, verifying on disk,
  not by guessing.

No push/deploy/publish anywhere. Just local `.app` install + LaunchAgent + icons.

---

## Open items carried into implementation

1. Cross-machine war-room data path for the Mini app (read Pro vs local). FIRST task, verify on disk.
2. Whether the official sampler currently runs on a schedule, or needs arming (separate step).
3. IG token scope `instagram_manage_insights` validity (Graph error 190 on 2026-06-21) — a
   live test; if invalid, token regen is an operator gesture (not app's job).
4. Fonts (.ttf) for Claude Design handoff — Montserrat + IBM Plex Mono are Google Fonts;
   attach only if desired.

## Testing posture

Keep the existing 52 tests green (unit + integration + chat-immersion). Add tests for:
new WarRoom cover-resolution (path-drift + multi-schema), mark-published queue write
(atomic + field-preserving + reversible), metrics read from war_room_metrics, ambient
selection rule (viral-fallback). Foundation-pure files stay pure for CLI test harness.
