# WR2 DEFINITIVA v1 — guaranteed daily carousel, seen by the human, KB-grounded, self-healing

> Mandate (Zero, 2026-07-07): "la WR2 non crea in autonomia quotidianamente... consegnami la WR2
> definitiva sia in codebase e parallelamente in app... completamente operativa, funzionante,
> testata pesantemente live in prod, self-healing e fin dove si può in loop di self improvement.
> Caroselli perfetti e completamente permeati dal sangue del nostro sistema e della nostra
> smisurata KB. Pronta a farci arrivare a un milione di follower."
>
> Loop: modus Gear 3. Ground evidence gathered live 2026-07-07 (session M5, probes on Pro + prod DB).

## 0. Root-cause diagnosis (evidence, all re-executed this session)

The pipeline PRODUCES near-daily but is INVISIBLE. Production legs green, every
"prove-it-to-the-human" leg dead:

| #   | Leg                                                            | State                                                                    | Evidence                                                                                                                                                                                                                                                                                                           |
| --- | -------------------------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| R1  | WhatsApp "Carousel pronto" notify                              | **DEAD since 2026-06-17**                                                | every `wa_outbox` row for carousel notifications: `status=failed, attempts=0, error=24h_window_closed` (14 rows, both recipients). Meta 24h customer-care window never opens because Zero/Damar never message the bot number. Structural: freeform WA push cannot work operator-bound.                             |
| R2  | Review queue JSON (feeds Damar web UI :8765 + WR2 Control app) | **DEAD since 2026-06-25**                                                | `apps/war-room/output/queue/human-review-queue.json` on Pro: 46 items, last non-published item `carousel_2026-06-25...indonesia-visafree-myth-reality`. Daily rendered drafts (07-02→07-06) never appended.                                                                                                        |
| R3  | Local PNG artifacts                                            | **EPHEMERAL**                                                            | `wr2_html_render_apply.py:583` renders into `tempfile.mkdtemp` → uploads to Drive → tempdir lost. No durable local carousel dir → app/queue/sync have nothing to show.                                                                                                                                             |
| R4  | DB publish records                                             | **EMPTY FOREVER**                                                        | `war_room_posts` = 0 rows, `wr2_publish_attempts` = 0 rows. IG publishes happened queue-JSON-only → metrics/learning loops starve (confirmed "loops alive but starved", memory 2026-06-23).                                                                                                                        |
| R5  | Runtime freshness                                              | **FROZEN since 2026-07-05**                                              | deploy clone `~/nuzantara-deploy` dirty (` D infra/launchagents/com.balizero.wr2.canva-token-watchdog.daily.plist`) → `wr2-deploy-pull` exit 1 hourly, alert cooldown-suppressed, HEAD stuck at #1956. html-apply logs `runtime provenance impure (gate=warn) dirty=True` every tick (C2 gate sees it, warn-only). |
| R6  | Daily cadence robustness                                       | **ONE-SHOT, NO RETRY**                                                   | topic-selector 05:10 WITA picks ONE topic/day; if the day's draft dies (20 drafts piled in `render_failed`, never retried; 17 `missed`) the day is silently lost. Gaps: 06-30, 07-01, 07-04 (UTC).                                                                                                                 |
| R7  | KB permeation                                                  | **INERT BY FLAG**                                                        | `scripts/wr2_grounding.py` ships `WR2_RESEARCH_STEP_ENABLED` default OFF + known citation-source gap → `brief_json.enrichment={}` → `fact_check_status='degraded'` on most rendered drafts (log today: `enrichment=False`). The "blood of the KB" wire exists and is unplugged.                                    |
| R8  | Ops alerts                                                     | **FIRE INTO THE VOID**                                                   | `_ops_alert` → raw Telegram sendMessage to owner chat = one of 206 unread senders (Zero 2026-07-06: notification economy "out of control"). Must route via `tg_notify` gateway (born+armed+proven 2026-07-07).                                                                                                     |
| R9  | Agentic orchestrator (wr2_carousel_runs, NB-grounded fan-out)  | **ABANDONED since 2026-06-03**                                           | last row `failed_cascade` 06-03. The smarter pipeline is unplugged; the live one (war_room_drafts) is the consolidated P-1 lane. Decision: keep war_room_drafts as THE lane; orchestrator stays parked (no resurrection in this arc — separate decision).                                                          |
| R10 | Zombie daemons                                                 | measurer last exit 2, canva-renderer exit 2, canva-oauth-watchdog exit 1 | `launchctl list` on Pro 2026-07-07. Canva render lane is superseded by HTML renderer (decision 2026-06-06).                                                                                                                                                                                                        |

**Meta-pattern**: the organism optimizes for producing, not for being seen producing. Every
delivery leg decayed independently and nothing watched the OUTCOME "a human saw today's
carousel". Family #2 (Esiste≠Armato) at the pipeline level + W89 (producer's own log is a proxy;
prove by downstream state-delta).

## 1. Cures (ranked by blast radius)

### A — VISIBILITY CHAIN (P0): "rendered" must mean "on Zero's screen"

- **A1 durable artifacts**: html-apply, after render, copies `slides/*.png` + `caption.txt` +
  `meta.json` to `~/nuzantara/apps/war-room/output/carousel/<YYYY-MM-DD>-<slug>/`
  (Pro main-checkout output tree = existing convention the queue server, warroom-sync and app
  already read). Tempdir remains the workdir; Drive upload unchanged.
- **A2 queue writer reborn**: same persist step appends a `human-review-queue.json` entry
  (schema per `skills/bali-zero-brand/_review-queue-schema.md`) state=`drafted`, with
  `carousel_path`, caption, slide_count, drive_url, fact_check_status. Atomic write (fcntl lock —
  reuse queue-server's lock helper).
- **A3 notify via tg_notify P0**: replace raw `_ops_alert`-for-success + WA-only with
  `tg_notify` tier P0 (dedup 6h) "🎠 Carousel pronto: <topic> — Drive: <url> — review: <app>".
  WA send stays best-effort (window may be open someday); its failure no longer matters.
- **A4 publish records**: the IG publish flow (`wr2_ig_publish*.py` + Fly endpoint) writes
  `war_room_posts` + updates queue entry state=`published`. Learning loops get food.

### B — RUNTIME FRESHNESS (P0): kill the frozen-clone class

- **B1 unfreeze now** (ops, this session): `git -C ~/nuzantara-deploy checkout -- <plist>`
  → puller advances to today's main. (PENDING-ARMS line 2026-07-05 closes.)
- **B2 deploy-pull self-heal**: classify dirty: (a) paths under `output/`, `logs/`, untracked
  runtime junk → ignore and proceed; (b) tracked-file modified/deleted with NO local-only value
  (file byte-restorable from HEAD) → `git checkout --` it, log `self-healed dirty: <path>`,
  proceed; (c) anything else → tg_notify P0 (not cooldown-void) and hold. Guilt+innocence tests.
- **B3 post-advance kickstart**: after a successful advance, puller kickstarts long-running
  consumers (supervisor; html-apply is StartInterval so next tick picks fresh code) — verify
  existing logic, add if missing.
- **B4 C2 strict**: after 7 days of quiet warn-logs post-B1/B2, flip `WR2_RUNTIME_SHA_GATE=strict`
  (existing ledger line stands).

### C — GUARANTEED DAILY (P0): retry until produced

- **C1 daily reconciler** `scripts/wr2_daily_reconciler.py` (launchd 09:00/13:00/18:00 WITA):
  - "exists a draft created today (WITA) with status ∈ {rendered, later}?" → done, heartbeat ok.
  - else if today's draft is in a recoverable state → requeue/kick (reset render lease,
    re-trigger html-apply; render_failed with attempts<3 → back to `drafts_imaged_checked`).
  - else (dead or absent) → run topic-selector again (dedup skips used topics → next-ranked).
  - 18:00 tick still empty → tg_notify P0 "WR2: NO carousel today — <reason>".
  - writes heartbeat `~/.organism/last_seen/pro.wr2_daily_carousel.json` {status, draft_id, day}.
- **C2 backlog policy**: reconciler nightly arm: retry up to 2 stale `render_failed` (fresh code
  post-B1 will likely converge — most failures are from the pre-fix era); >14d unrecovered →
  `missed` (dedup index frees the topic pool).

### D — KB BLOOD (P1-high): arm the grounding wire

- **D1 citation source**: add cron-safe backend endpoint (or reuse existing search that returns
  chunk text with citations) so `wr2_grounding._rag_query` receives text containing
  `PP/PMK/UU N/YYYY` citations; verify LAW_PATTERNS extraction on live data.
- **D2 arm flag**: set `WR2_RESEARCH_STEP_ENABLED=true` in topic-selector plist once D1 proves
  a non-empty enrichment on a real topic. Acceptance: next carousels majority
  `fact_check_status='pass'` and slide bodies carry verbatim reg citations.

### E — SELF-HEALING (P1): the organism sees WR2

- **E1 organ registration**: WR2 chain organs get heartbeat sidecars + `organs_registry.yaml`
  entries → healer receptors (registry scan) cover them; healer-pro tick kickstarts dead ones.
- **E2 outcome receptor**: C1's `pro.wr2_daily_carousel` heartbeat is THE outcome probe
  (downstream state-delta, not producer log). organism_digest SessionStart surfaces it.
- **E3 watchdog outcome check**: supervisor-watchdog gains "no draft rendered in 26h" alarm
  (tg_notify P0) if not already equivalent (M9 pipeline_frozen exists — verify coverage).
- **E4 zombie triage**: retire canva-renderer + canva-oauth-watchdog + canva-apply plists
  (superseded lane) or fix measurer; each gets a PENDING-ARMS/ledger line.

### F — SELF-IMPROVEMENT (P2): close the learning loops

- **F1 feed**: A4 publish records + existing ig-metrics-scrape daily → wr2-ig-metrics-analyst
  (Monday) + learner-nightly + reflexion weekly now have real data. Verify next scheduled runs
  consume (PENDING-ARMS passive line).
- **F2 actuator**: B1 layout-swap actuator (`_swap_layout_family`) remains the open next-level
  item — separate arc.

## 2. Acceptance (falsifiable)

1. **Prove-live E2E**: drive one REAL production run this session: draft → rendered → PNGs in
   durable dir → queue entry → tg_notify P0 received → visible in app data source. By content.
2. `wr2.deploy_pull.json` status=ok with advancing head; html-apply provenance warn silent.
3. Reconciler dry-run: detects today's state correctly on live DB; guilt (no-carousel day) and
   innocence (carousel exists) both proven.
4. Grounding: one real topic returns non-empty enrichment with ≥1 verbatim citation.
5. Heartbeats visible in `~/.organism/last_seen/`; healer registry shows WR2 organs ok/never_armed→ok.
6. Every alert path lands in tg_notify (grep: no new raw sendMessage for WR2 success/failure).

## 3. §Solo-operatore

- IG publish stays manual-approve (Legge 5) — the button, never auto.
- Meta template-message approval (if we ever want WA push again) — business/GUI.
- Any required-check/branch-protection flips — sanctioned API path with GO already standing.

## 4. Out of scope (declared)

- Resurrecting the wr2_carousel_runs agentic orchestrator (R9) — separate decision memo.
- WR3 video pipeline. Newsletter/X/LinkedIn lanes.
