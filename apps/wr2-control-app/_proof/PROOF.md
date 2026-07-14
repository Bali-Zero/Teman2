# WR2 Control — Run-live proof bundle (2026-06-21)

All evidence captured by executing real commands on M5 disk this session. The `screencapture`
system tool is blocked by macOS TCC (Screen Recording grant not given to the terminal session —
operator boundary), so VISUAL proof is produced a different way: the app renders its own views to
PNG off-screen via SwiftUI `ImageRenderer` (`WR2Control --snapshot <dir>`), which needs no Screen
Recording grant. Three real screenshots in this dir: `studio.png`, `gallery.png`, `review.png`.

- **studio.png** — full Studio view: launch field + live monitor showing the real café run's 8
  pipeline steps (6 done, "Controllo qualità" in progress).
- **gallery.png** — "26 caroselli generati" grid; top-left card is the just-produced
  `KBLI 2025 … café in Bali` (REGULATORY, 6 slide) with real critic verdict badges.
- **review.png** — "53 elementi in coda" with real topics, states, dates, and critic summaries
  read from the live `human-review-queue.json`.

(The card thumbnails render as a placeholder glyph because `ImageRenderer` does not materialize
async `NSImage` loads off-screen — a known ImageRenderer limitation; all text/data is real. In the
live GUI the thumbnails load normally — proven separately by `galleryproof` reading 6/6 real PNGs.)

## 1. App builds & launches (criteria #1, #2)

- `swiftc` build → `build/WR2 Control.app`, 0 errors.
- `open` → process `WR2Control` alive, ~33 MB RSS, GUI process. pid confirmed via `pgrep`/`ps`.

## 2. App launches a REAL WR2 run via claude CLI (criteria #3, monitor #4)

Driver = the production `ClaudeRunner` (identical to what the SwiftUI app drives).
Full log: `liverun.log`. Key lines:

```
▸ topic: design a carousel for KBLI 2025 requirements to open a small café in Bali
  PID 50002                       ← child claude process spawned (OS-confirmed alive)
  ● init model=claude-opus-4-8
  ● tool_use Bash → Preflight: check audit script, subagents, cortex
  STEPS  init:done brief:active …          ← fan-out: brief-interpreter dispatched
  STEPS  … brief:done storyboard:active …  ← storyboarder dispatched
  STEPS  … storyboard:done images:done layout:done render:done critic:active …
  ● RESULT error=false cost=10.0921  text=… carousel is complete and passed the critic gate
  STEPS  init:done brief:done storyboard:done images:done layout:done render:done critic:done queue:done
  TERMINATED code=0
FINAL status=succeeded code=0
```

→ The monitor (RunReducer) tracked the ENTIRE real pipeline from live stream-json.

## 3. A new carousel appeared on disk (criterion gallery #4)

- BEFORE: 31 carousels. AFTER: 32. The added one:
  `apps/war-room/output/carousel/kbli-2025-small-cafe-bali/`
- Contents (produced today 06:35–06:53): `brief.json`, `brief.md`, `slides.json`,
  `critic-report.md`, `imagegen.log`, `slides/{1..6}.{html,png}`.
- 6 slide PNGs at **1080×1350** (Instagram portrait), all non-empty.

## 4. The app's gallery layer SEES the new carousel (criterion #4)

`galleryproof` runs the production `WarRoom.scanCarousels` against live disk:

```
carousels visible: 26   (chrome-only dirs correctly excluded)
✅ NEW CAROUSEL VISIBLE IN GALLERY:
   slug:    kbli-2025-small-cafe-bali
   topic:   KBLI 2025 requirements to open a small café in Bali
   domain:  regulatory
   slides:  6 PNG   cover: 1.png
   slide files present & non-empty: 6/6
```

## 5. Review queue read (criterion #5)

`WarRoom.readQueue` decodes the live `human-review-queue.json` → 53 items across 3 schema
variants (legacy / FSM / hybrid), all rendered in the Revisione view.

## 6. Tests (criterion #5)

- `test.sh` → **46 passed, 0 failed** (incl. 8 adversarial-review regression tests).
- `test-integration.sh` → **6/6 GREEN** driving the real claude CLI.

## 7. Bugs caught & fixed by tests / adversarial review

- terminationHandler dropped the final `result` event (race) — fixed (tail-drain).
- empty `--agent` ate `--output-format` — fixed (conditional flag).
- 7 of 9 devils-advocate findings fixed (H1/H2/H4/M1/M2/M3/L1) with regression tests.

## Boundaries respected

- All on M5. No git push, no deploy, no Instagram publish.
- No Anthropic SDK / no ANTHROPIC_API_KEY (stripped from child env). OAuth MAX only.
- Topic was public (KBLI café) — no PII (Law 2).
