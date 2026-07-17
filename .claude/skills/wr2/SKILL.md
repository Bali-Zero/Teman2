---
name: wr2
description: "WR2 corner — the live shared context for the War Room 2 editorial organism (intel → carousel → Instagram). Load BEFORE touching any WR2 script, the Control app, the queue, metrics, or brand surfaces — or when Zero says /wr2, 'war room', 'carosello', 'WR2'. Holds: the north star (a self-improving, facts-honest editorial machine), the anatomy map (every hot file/daemon/log), LIVE STATE, blood-bought rules, and the standing GROWTH LOOP mandate for no-stop improvement sessions."
---

# /wr2 — War Room 2 corner (project brain)

> Created 2026-07-17 on Zero's order after the facts-first ship ("crea la skill di contesto /wr2
> dove inserisci i file più importanti per avere un contesto caldo e pronto e dove possiamo
> continuare a fare crescere la wr2"). This file is the HOT CONTEXT shared by every Fable/Claude
> session and every Codex dispatch working on WR2. **Update §1 LIVE STATE whenever it changes —
> this corner is only useful if it stays true.**

## 0. What WR2 is + the north star

WR2 is Bali Zero's autonomous editorial organism: Indonesian regulatory/visa/tax intel →
grounded brief → 7-10 slide branded carousel → human review → Instagram. It spans a Python
pipeline (Pro launchd), a macOS review app (M5), a queue protocol (Pro SSOT + M5 mirror), a
metrics loop (IG Graph scrape → weekly analyst), and the brand cortex.

**Constitutional principle** ([[principle_wr2_codebase_app_indissoluble_2026_06_25]]): the WR2
codebase and the Control app are ONE organism — never evolve one side without the other.

**THE NORTH STAR: a self-improving editorial machine that is facts-honest by construction.**
Every carousel must tell a TRUE, CONCRETE story (facts-first — the 2026-07-16 "storia inventata"
incident is the founding scar), pass brand + accessibility bars, and feed measured engagement
back into the next editorial decision. Growth = the standing loop in §4.

**Legge 5 (absolute)**: publishing to Instagram is Zero's act. The pipeline stops at `drafted`
in the review queue. No session ever publishes autonomously.

## 1. LIVE STATE (last update 2026-07-17 night — keep current)

**Shipped & proven (July 16-17 arc):** complete-or-nothing gate (#2543 app / #2553 py) ·
take-label variety + vendored agent defs (#2544) · archive-aware M5 merge + reconciler repair
(#2563) · external-post registration + IG metrics FIRST LIVE on native carousels (#2578, hotfix
#2579, 49 entries backfilled with numeric Graph ids) · **facts-first + park backstop (#2598,
migration 245 `parked` on prod)** · capture ledger (#2581, #2609).

**In queue awaiting Zero (Legge 5):** deportation carousel remake (`drafted`, 2026-07-17, tells
the real event) · EN "1 August" tax carousel · bahasa lane awaiting Subhi/Ari reply.

**Open wounds / next targets:**

- **Liveness scorer returns 0.0 for ALL items** (classifier lane paused, #2501) → live pool
  always empty → every topic composes as `evergreen`. The tier steers (length/tone) are dead
  weight until this is rewired. HIGH-value fix.
- **13 unknown_intent** queue entries (complete-or-nothing backfill refused to guess) — need
  adjudication = re-render from slides.json. · **3 render_incomplete** same family.
- **fact_check_status "degraded" pipeline-wide** — the checker runs in degraded mode on every
  recent deck; ground-truth leg needs investigation.
- **Gate log noise**: app re-emits ~29 exclusions every ~10s cycle → `wr2control.err` grows
  ~30MB/day. Needs delta-logging or rotation.
- **4 accessibility amendments** in conflict with the constitution await Zero's reconciliation
  (`~/.claude/skills/bali-zero-brand/_proposed-amendments/2026-07-16-accessibility-discipline.md`).
- **Slide-7 closer micro-text** (remake deck): elegant-close layout renders the kicker tiny.
- **Ledgered structural cures** (modus PENDING-ARMS): docs-guardian regen cron on main ·
  official `--rebrief` verb (see §3 remake hygiene) · M5 queue shared-lock protocol ·
  Swift tolerant decode · plist validator red on main · 19 env-coupled tests.

## 2. Anatomy — the hot files (verified 2026-07-17)

**Pipeline (Pro, launchd `com.balizero.wr2.*`, logs `~/logs/wr2*.log`; wrapper
`~/.openclaw/bin/wr2/wr2-script-wrapper.sh` → `REPO_ROOT=${WR2_REPO_ROOT:-~/nuzantara-deploy}`
— deploy = pull BOTH `~/Desktop/nuzantara` AND `~/nuzantara-deploy`, scar #1):**

| Stage         | Script                                                                                            | launchd          | Notes                                                                                                                                                                                                                                                                              |
| ------------- | ------------------------------------------------------------------------------------------------- | ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | ------------------------------------ |
| Topic pick    | `scripts/wr2_topic_selector.py`                                                                   | topic-selector   | scores staging items, writes `war_room_drafts` (status `briefed`) with brief_json = article_summary[:2000] + enrichment + source_url; RAG grounding via `scripts/wr2_grounding.py` (citation injection + `_grounding_injected_only` marker + `is_citations_only_the_facts()` SSOT) |
| Compose       | `scripts/wr2_draft_generator.py`                                                                  | draft-generator  | **facts-first prompt** (article leads, enriched brief supports); park backstop (news-shaped + no usable source → `parked`, never composed); tri-state outcome `success                                                                                                             | parked | failed`, exit 0 unless real failures |
| Hero images   | `scripts/wr2_image_generator.py`                                                                  | image-generator  | Codex $imagegen primary, FlowKit fallback; CAS lease on `lease_owner`, stale-sweep TTL 40min                                                                                                                                                                                       |
| Facts         | `scripts/wr2_fact_extractor.py`                                                                   | fact-extractor   | gates on `fact_check_json IS NULL`                                                                                                                                                                                                                                                 |
| Check         | fact-checker lane                                                                                 | fact-checker     | writes `fact_check_status` (currently degraded pipeline-wide)                                                                                                                                                                                                                      |
| Render        | `scripts/wr2_html_render_apply.py` + `apps/backend-rag/backend/services/canva_renderer_v2/_pg.py` | html-apply       | HTML/CSS→PNG Playwright; fetch gates on `drive_url IS NULL` + `lease_owner IS NULL`; official re-render verb: `_pg.requeue_draft_for_rerender`                                                                                                                                     |
| Orchestration | `scripts/wr2_supervisor.py` + `scripts/wr2_supervisor_watchdog.py`                                | supervisor       | TRANSITIONS maps (from,to)→launchd label; TERMINAL_STATUSES includes `parked`                                                                                                                                                                                                      |
| Reconcile     | `scripts/wr2_daily_reconciler.py`                                                                 | daily-reconciler | slides-dir resolution 3-level, `--repair-false-incomplete`, `--backfill-completeness`                                                                                                                                                                                              |

**DB**: `war_room_drafts` on nuzantara-postgres. Status machine (CHECK constraint, migration 245):
briefed → drafts → drafts_imaged → drafts_imaged_facted → drafts_imaged_checked → rendering →
rendered (+ parked/rejected/failed terminals). Backend model `apps/backend-rag/backend/services/
war_room/models.py::DraftStatus` must stay in sync (repository raises on unknown status).

**Queue (SSOT Pro)**: `~/Desktop/nuzantara/apps/war-room/output/queue/human-review-queue.json` +
`queue-archive.json`. Writers: `scripts/wr2_queue_writer.py` ONLY (fcntl EX on
`human-review-queue.lock`, tmp+os.replace). M5 mirror: `~/bin/wr2-queue-pull.sh` (declared
HOME-fork pair — deploy = cp from repo + kickstart) pulls archive FIRST, merges via
`scripts/wr2_queue_pull_merge.py` (remote-wins, published-local protected, `archived_dropped`,
external push-back with `synced_to_pro`).

**App (M5)**: `apps/wr2-control-app/` (Swift; build via repo `build.sh`, canonical bundle in
`~/Applications`, Desktop symlink). Complete-or-nothing gate, external-post sheet, ReviewView.

**Metrics**: `scripts/wr2_ig_metrics_scraper.py` (authoritative `ig_media_id` numeric Graph id;
token from Pro `.env.master`, NEVER printed) + `scripts/wr2_ig_discovery.py` (shortcode
compare-and-set backfill) → weekly `wr2-ig-metrics-analyst` (Monday 06:00) → amendments in
`~/.claude/skills/bali-zero-brand/_proposed-amendments/`.

**Brand cortex**: `~/.claude/skills/bali-zero-brand/` (constitution, tokens, voice, surfaces,
external benches). Agent defs vendored in repo `.claude/agents/wr2-*.md` (#2544 — repo shadows
HOME).

**Deploy**: backend/migrations ride the CI pipeline `.github/workflows/fly-deploy.yml` (push to
main touching `apps/backend-rag/**`; release_command applies migrations). WR2 scripts on Pro =
pull both checkouts + kickstart affected daemons. Prove-live per consumer surface, always.

## 3. Blood-bought rules (violate = repeat a paid scar)

1. **Facts-first, refuse-to-guess** (founding scar 2026-07-16): the article summary LEADS the
   composition prompt; grounding citations SUPPORT, never replace. News-shaped topic with no
   usable source → `parked`, never composed. Never "tidy" this.
2. **Remake hygiene**: re-briefing a composed draft by status reset leaves stale derived fields —
   `fact_check_json` starves the extractor, `drive_url` starves the render lane. Clear
   fact_check_json/status/at + use `_pg.requeue_draft_for_rerender` for the render leg. (Official
   `--rebrief` verb is a ledgered TODO.)
3. **Never `launchctl kickstart -k` a one-shot job that may be mid-run** — it kills the worker
   and orphans its DB lease (42-min starvation, 2026-07-17). Plain kickstart; `-k` only for
   daemons you intend to restart.
4. **Queue mutations only via canonical writers under flock** — never hand-edit
   human-review-queue.json/queue-archive.json (data-plane guard blocks it; the merge protocol
   depends on writer invariants).
5. **The wrapper runs from `~/nuzantara-deploy`**, not `~/Desktop/nuzantara`. Aligning only one
   Pro checkout deploys nothing (scar #1 HOME-fork). M5's `~/bin/wr2-queue-pull.sh` same family.
6. **Migration PRs = auto-merge OFF** — the session merges manually after Squawk/migration gates,
   then probes the applied constraint on prod with its own query.
7. **Generator≠grader always**: implementer lane ≠ reviewer; Codex red-team on behavior changes;
   the final on-disk/live gate is the session's own tool calls.
8. **Probe entity-match** (3 strikes 2026-07-17): probes assert exact ids/status enums/counts —
   never generic "error" greps (matches fail-open observability noise), never `jq '.[0]'` output
   tested with `[ -n ]` (empty array prints literal "null null").
9. **Tests must not write prod state** (W96): WR2 workers default `Path.home()` output roots —
   conftest must redirect `WR2_OUTPUT_ROOT`/Telegram to tmp_path.
10. **Legge 5**: `drafted` is the pipeline's last stop. Zero publishes.

## 4. GROWTH LOOP — standing mandate for no-stop improvement sessions

> Zero's order (2026-07-17): a session that works in a loop on WR2 improvement, alternating deep
> research of best practices / cutting-edge tools with concrete experimentation on the automation
> and continuous live fixes. Paste the prompt below into a fresh session (or invoke with /loop).

```
/wr2 — GROWTH LOOP. Sessione no-stop di accrescimento della WR2. Lavora in loop autonomo
alternando due sprint, finché io non ti fermo:

SPRINT R (research, ~30% del tempo): deep research su UNA domanda concreta di frontiera per la
WR2 — agentic content pipelines SOTA, editorial automation, IG-format best practice, layout/
accessibility, metrics-driven editorial loops, tool nuovi (modelli, renderer, vision-QA).
Multi-fonte (web + external-bench esistenti in ~/.claude/skills/bali-zero-brand/ + carousel
corpus + metriche IG reali). Output: research capture in research/marketing/ con ≥3 fonti e UNA
raccomandazione azionabile ("adotta X per Y, atteso Z"). Niente ricerca senza raccomandazione.

SPRINT B (build, ~70% del tempo): prendi UN item — dalla raccomandazione dell'ultimo sprint R,
dalla §1 LIVE STATE del corner /wr2 (open wounds: liveness scorer 0.0, 13 unknown_intent,
fact-check degraded, log noise, --rebrief verb…), o da un fix emerso live — e portalo fino in
fondo con modus: GROUND (ri-grep dei file citati) → BUILD (implementer Sonnet in worktree) →
VERIFY (red-team Codex per i behavior change, generator≠grader) → SHIP+ARM (PR + auto-merge;
migration = merge manuale) → PROVE-LIVE (deploy Pro dual-checkout + kickstart + probe con
entity-match sull'esito REALE) → CAPTURE (aggiorna §1 LIVE STATE del corner + ledger + scar).

Regole del loop:
- UNA cosa per sprint, chiusa fino a prove-live — mai 3 cose a metà.
- Alterna: dopo ogni sprint B chiuso, uno sprint R. Se uno sprint B si blocca su un gate
  operator-only, scrivi la riga PENDING-ARMS e passa al prossimo item invece di aspettare.
- Rispetta le blood-bought rules del corner /wr2 §3 — tutte, sempre.
- Legge 5: mai pubblicare su IG. I risultati arrivano a 'drafted' e si fermano.
- Niente API a pagamento nuove senza mia autorizzazione; arsenale esistente (Claude OAuth,
  agy, Codex, DeepSeek pre-autorizzato, Ollama) libero.
- Budget-onestà: dichiara a inizio sessione quanti sprint stimi; se un item supera 2x la stima,
  fermalo, ledger, passa oltre.
- Ogni 3 sprint: riga di sintesi a me su Telegram-style (cosa è cresciuto, cosa è in coda).
- A fine sessione (o /loop stop): CAPTURE finale — memoria + §1 LIVE STATE aggiornata + prompt
  di ripartenza per la sessione successiva.
```

**Seed backlog for the first loops** (in rough value order): (1) liveness scorer rewire — the
single highest-leverage fix, unlocks the whole breaking/developing register system; (2)
fact-check degraded root-cause; (3) unknown_intent/render_incomplete adjudication via re-render;
(4) `--rebrief` official verb; (5) metrics→editorial feedback: use the now-live IG metrics to
auto-tune topic selection weights; (6) gate log delta-emission; (7) accessibility amendment
implementation once Zero rules; (8) slide-7 closer layout fix; (9) A/B hook experiments on
cover copy measured via the metrics loop.

## 5. Access & artifacts

- Memory (M5): `ops_wr2_trifront_gate_variety_accessibility_shipped_2026_07_16.md` (the July
  16-17 arc, all codas) · `discovery_wr2_app_published_blind_and_contract_d_2026_07_14` ·
  `p1-wr2-pipeline-consolidation-spec.md` (REV 2, awaiting GO) ·
  `decision_wr2_renderer_html_css_over_canva_2026_06_06`.
- Modus ledger: `.claude/skills/modus/PENDING-ARMS.md` + `AMENDMENTS.md` (WR2 lines 2026-07-17).
- Output tree (Pro SSOT): `~/Desktop/nuzantara/apps/war-room/output/` (carousel/, queue/).
- Drive renders: per-draft `drive_url` in war_room_drafts.
- DB access RO: `mcp__postgres-nuzantara__query` / `scripts/pg.sh`; writes ONLY via backend
  code from Pro env (never MCP).
- IG token: Pro `.env.master` — grep into env vars, never print (scar #4).

> Chi cambia lo stato AGGIORNA la §1. Un corner stantio è peggio di nessun corner (W90: anche il
> ground-truth invecchia).
