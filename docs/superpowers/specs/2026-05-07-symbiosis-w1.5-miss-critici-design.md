# Symbiosis W1.5 — Enroll 9 MISS CRITICI organi (78 → 87)

**Date**: 2026-05-07
**Branch**: `feat/symbiosis-W1.5-organi-2026-05-07`
**Doctrine ref**: PR #479 (Symbiosis Turn-On Plan), PR #488 (W1 enrollment 26→78), Issue #490 (W1.5 follow-up scoping)
**Target**: enroll the 9 MISS CRITICI organi flagged in PR #488 tri-LLM cross-check
into `apps/organism/organism/genome.yaml`, expanding the registry from 78 to 87.

---

## 1. Goal

Close the gap left by W1: 9 plist labels currently loaded on Pro that look
like real organi but were excluded from W1 to keep that PR atomic. Each
sits on a known production blast radius (federation A2A bridge,
auto-healing observatory, publishing pipeline tail, Lamarckian feedback
distillation). Enrolling them gives the Innervation Genoma observability
on the missing surfaces; recovery still dispatches via `launchctl_kickstart`
on Pro (no schema changes).

Registry-only change. Zero modifications to organ source code (vincolo
inviolabile #5).

## 2. Topology constraints (smoke-tested 2026-05-07)

`launchctl print gui/$(id -u)/<label>` on Pro confirmed the 9 issue-#490
labels are bootstrapped, with `state = running` (KeepAlive daemons) or
`state = not running, last exit code = 0` (idle crons between ticks):

| Label | State at smoke time | Schedule | Type |
|---|---|---|---|
| `com.balizero.nlm-bridge` | running, daemon | KeepAlive=true RunAtLoad=true | daemon (uvicorn :18790) |
| `com.nuzantara.cell-observatory` | running, daemon | KeepAlive=true RunAtLoad=true | daemon (collector) |
| `com.nuzantara.cell-observatory-prune` | not running, idle | StartCalendarInterval Hour=4 Minute=0 | cron (daily 04:00) |
| `com.nuzantara.cell-observatory-selfcheck` | last exit 1, idle | StartInterval=300 | cron (5-min poll) |
| `com.balizero.post-publish-poller` | not running, last exit 0 | RunAtLoad=true | cron (RunAtLoad — daemon-style trigger, no recurring schedule) |
| `com.balizero.sota.m13-checkpoint` | not running, last exit 0 | StartCalendarInterval Hour=9 Minute=0 | cron (daily 09:00) |
| `com.balizero.sota.m13-collect` | not running | RunAtLoad=true | cron (RunAtLoad-only) |
| `com.balizero.sota.m13-monthly` | not running | StartCalendarInterval Day=1 Hour=4 Minute=30 | cron (monthly day-1 04:30) |
| `com.balizero.sota.m13-weekly` | not running | StartCalendarInterval Weekday=0 Hour=6 Minute=0 | cron (weekly Sunday 06:00) |

All 9 plists are read-only mode 0444 / 0400 since the 2026-04-29 chmod
hardening. None require schema or validator changes — every label maps
to existing enums (`pro_launchd`, `daemon`/`cron`, `launchctl_kickstart`,
`warning`/`error`/`critical`).

**Smoke-test discovery (logged for the orchestrator):** the prompt
listed organ family labels (`com.cell.observatory.collector/.heartbeat/.crisis`
and `com.nuzantara.sota.m13-skill-extractor/.reflection-aggregator/...`)
that **do NOT exist on disk**. The labels in GitHub issue #490 are the
ground truth — they are what's in `~/Library/LaunchAgents/`. This design
follows the issue.

## 3. Schema decisions

**D1 — No validator change.** All 9 entries use existing enum values
(`pro_launchd` runtime, `daemon`/`cron` type, `launchctl_kickstart`
recovery, `warning`/`error`/`critical` severity). The `mini_launchd`
addition shipped in PR #488 covers the only Modo B extension we need;
nothing here is on Mini.

**D2 — Naming.** Use the same convention as W1:

- `nlm.bridge` (singular family — Federation v3 A2A Agent 8)
- `cell.observatory`, `cell.observatory_prune`, `cell.observatory_selfcheck`
  (matches the existing `cell.organism` family namespace)
- `pro.post_publish_poller` (matches `pro.*` Pro-background namespace from W1)
- `sota.m13_checkpoint`, `sota.m13_collect`, `sota.m13_monthly`, `sota.m13_weekly`
  (new family namespace; underscore form of the launchd label after the
  trailing dot)

**D3 — `expected_hb_seconds`.** Apply the W1 rule (`expected_period + 1h grace`):

| Schedule | period | expected_hb_seconds |
|---|---|---|
| KeepAlive daemon | n/a | 60–180 (per organ class — 90 for collector parity with `cell.organism`, 180 for `nlm-bridge` because uvicorn cold-start is heavier) |
| `StartInterval=300` | 300 s | 3900 (1h grace minimum) |
| Daily `Hour/Minute` (no Day) | 86400 s | 90000 (24h + 1h grace) — same as W1's `wr2.dossier_compiler` |
| Weekly `Weekday + Hour/Minute` | 604800 s | 691200 (7d + 1d grace) |
| Monthly `Day=1 + Hour + Minute` | ~2.6 Ms | 2_678_400 (31d + 1d grace) |
| `RunAtLoad`-only (no schedule) | unscheduled | 90000 (treat as daily — produces a heartbeat-stale alert if no operator triggers it within ~25h, matching the daily-cron heuristic) |

**D4 — Severity.**

- `nlm.bridge`: **critical**. Federation v3 A2A bridge — async multi-doc
  synthesis fails silently when the bridge is down (NB-1 architectural
  rationale).
- `cell.observatory`: **critical**. Listens on PG channels
  `federation_alert` + `cell.pulse.observed`; FAD is blind without it.
- `cell.observatory_prune`: **warning**. Self-maintenance (daily prune of
  pulse rows). Failure does not break observability — only inflates DB
  size over time.
- `cell.observatory_selfcheck`: **warning**. Health checker for the
  observatory itself. Cron-driven, recoverable. Last exit 1 at smoke time
  — known pre-existing failure mode separate from enrollment scope.
- `pro.post_publish_poller`: **error**. Final pipeline motor (SEO + Fireworks
  Flux.1 cover + git push). When down, mouth articles published by WR2
  pipeline get stuck mid-flow. Not "critical" because the upstream
  WR2 chain can be replayed once the poller is restored.
- `sota.m13_*` (4 entries): **warning** for collect/checkpoint/weekly,
  **info** for monthly. Lamarckian feedback distillation — failure
  degrades skill-extraction quality but doesn't break user-facing flows.
  m13-monthly is "info" because a 1-month delay in monthly rollups is
  cosmetic; m13-weekly already covers the operational window.

**D5 — Dependencies.** Resolve only to ids already in `genome.yaml`:

- `nlm.bridge`: depends on `infra.postgres` only (uvicorn HTTP service —
  it pulls from PG-backed metrics + accepts NLM client requests).
- `cell.observatory`: depends on `infra.postgres` only. **Empirical
  correction (Codex sandbox review 2026-05-07):** the collector at
  `apps/cell-observatory-collector/cell_observatory/config.py` requires
  `EVENTBUS_DATABASE_URL` (PG LISTEN), `OPENROUTER_API_KEY/MINIMAX*` (LLM
  classifier API), and `OBSERVATORY_DB_PATH` (SQLite). NO Redis path. The
  initial draft included `infra.redis` for parity with `cell.organism`,
  but that misstates the blast radius — corrected.
- `cell.observatory_prune`: depends on `infra.postgres` (DELETE old rows).
- `cell.observatory_selfcheck`: depends on `cell.observatory` (heartbeat
  probe) and nothing else.
- `pro.post_publish_poller`: depends on `infra.postgres` (mouth metadata)
  and that's it. The Fireworks API + git remote are external — not
  in-tree organi.
- `sota.m13_*`: depends on `infra.postgres` (post_metrics_history table).
  The supervisor for these is `wr2.supervisor` (the wrapper script
  `wr2-cron-wrapper.sh`); declare it as a dependency for the daily/
  monthly/weekly entries (they follow the WR2 cron pattern). m13-collect
  with `RunAtLoad` only also depends on `wr2.supervisor`.

**D6 — Recovery.** All 9 use `recovery_action: launchctl_kickstart` with
`recovery_params: {host: "pro", label: <full-label>}`. Same pattern as the
W1 Pro-background entries.

**D7 — `bridge_source`.** Match the W1 convention only where W1 already
declares one for sibling organi.

- `cell.observatory` daemon: declare a `state_file` bridge_source pointing
  at `~/.organism/last_seen/cell.observatory.json`, mirroring the
  `cell.organism` pattern. **Caveat:** the collector does not currently
  emit that file. Until a sidecar emitter ships, the Supervisor will
  surface `dead/no_signal` for this organ until heartbeat-staleness
  fallback kicks in. This is consistent with the W1 convention (the
  same is true for `cell.organism` itself per the W1 plan).

- `nlm.bridge` daemon: **NO `bridge_source` declared.** Empirical
  correction (Codex sandbox review): the live endpoint is `/nlm/health`
  (NOT `/health`) and the `HealthResponse` model returns `status`,
  `uptime`, `request_count` only — NO `ts` field. The cell
  `BridgeStateReader` at `apps/cell/cell/sensors/bridge_state_reader.py:203`
  hard-fails with "http body missing timestamp field 'ts'" when the
  expected timestamp_field is absent. Two options: (a) declare an http
  bridge anyway and accept it will read as error until the
  `HealthResponse` model gains a `ts` field (visible follow-up), or (b)
  omit `bridge_source` and rely on the heartbeat-staleness fallback
  (matches `mata_garuda.bridge_adaptive.pro` daemon pattern in W1).
  Option (b) is chosen — adding a permanently-erroring bridge would be
  worse signal than no bridge. Follow-up: add `ts` to nlm-bridge's
  `HealthResponse` and re-declare the bridge in W2 sidecar work.

- `cell.observatory_prune`, `cell.observatory_selfcheck`,
  `pro.post_publish_poller`, `sota.m13_*` (4): NO `bridge_source` field —
  same as the W1 Pro-background and matagaruda cron entries which omit
  it. The aggregator at
  `apps/cell/cell/sensors/genome_aggregator_sensor.py:300` will surface
  `dead/no_signal` for these until W2 sidecar emitters write last-seen
  JSON. Acceptable per W1 mass-pattern (56/78 W1 organi have no
  `bridge_source`); separate W2 sidecar PR will address the broader
  fleet.

**D8 — `cicatrix_refs`.** Empty `[]` for all 9. None of these labels
are mentioned in `.claude/rules/cicatrix-scars.md` STRUCTURAL entries.

## 4. Architecture

Single PR / 2 commits on `feat/symbiosis-W1.5-organi-2026-05-07`:

- Commit 1: design doc (this file) + plan doc
- Commit 2: 9 new genome.yaml entries + checksum update + 1 new test
  in `apps/organism/tests/tools/test_validate_genome.py`

Registry-only change confined to:
- `apps/organism/organism/genome.yaml` (9 new entries appended after
  `pro.secrets_sync_mini`)
- `apps/organism/tests/tools/test_validate_genome.py` (1 new test
  validating the 9 ids exist with the expected fields, family-grouped:
  cell-observatory ×3 in a single class, sota.m13 ×4 in a single class,
  nlm.bridge + post_publish_poller as singletons)

NO modifications to:
- `apps/organism/organism/tools/validate_genome.py` (no schema change)
- Plist files
- Existing 78 genome entries

## 5. Components

### 5.1 Genome.yaml entries

9 new entries appended after `pro.secrets_sync_mini` (line 1201).

```yaml
  # === Wave 1.5 MISS CRITICI (2026-05-07) — issue #490 ===

  - id: nlm.bridge
    runtime: pro_launchd
    type: daemon
    expected_hb_seconds: 180
    owner_module: apps/nlm-bridge/main.py
    dependencies:
      - infra.postgres
    recovery_action: launchctl_kickstart
    recovery_params:
      host: pro
      label: com.balizero.nlm-bridge
    severity_on_silence: critical
    cicatrix_refs: []

  - id: cell.observatory
    runtime: pro_launchd
    type: daemon
    expected_hb_seconds: 90
    owner_module: apps/cell-observatory-collector/cell_observatory/__main__.py
    dependencies:
      - infra.postgres
    recovery_action: launchctl_kickstart
    recovery_params:
      host: pro
      label: com.nuzantara.cell-observatory
    severity_on_silence: critical
    cicatrix_refs: []
    bridge_source:
      type: state_file
      path: ~/.organism/last_seen/cell.observatory.json
      timestamp_field: ts
      status_field: status

  - id: cell.observatory_prune
    runtime: pro_launchd
    type: cron
    expected_hb_seconds: 90000
    owner_module: apps/cell-observatory-collector/cell_observatory/prune.py
    dependencies:
      - infra.postgres
    recovery_action: launchctl_kickstart
    recovery_params:
      host: pro
      label: com.nuzantara.cell-observatory-prune
    severity_on_silence: warning
    cicatrix_refs: []

  - id: cell.observatory_selfcheck
    runtime: pro_launchd
    type: cron
    expected_hb_seconds: 3900
    owner_module: apps/cell-observatory-collector/scripts/healthcheck.sh
    dependencies:
      - cell.observatory
    recovery_action: launchctl_kickstart
    recovery_params:
      host: pro
      label: com.nuzantara.cell-observatory-selfcheck
    severity_on_silence: warning
    cicatrix_refs: []

  - id: pro.post_publish_poller
    runtime: pro_launchd
    type: cron
    expected_hb_seconds: 90000
    owner_module: apps/bali-intel-scraper/scripts/post_publish_poller.py
    dependencies:
      - infra.postgres
    recovery_action: launchctl_kickstart
    recovery_params:
      host: pro
      label: com.balizero.post-publish-poller
    severity_on_silence: error
    cicatrix_refs: []

  - id: sota.m13_checkpoint
    runtime: pro_launchd
    type: cron
    expected_hb_seconds: 90000
    owner_module: apps/backend-rag/backend/services/sota_loop/m13_checkpoint.py
    dependencies:
      - infra.postgres
      - wr2.supervisor
    recovery_action: launchctl_kickstart
    recovery_params:
      host: pro
      label: com.balizero.sota.m13-checkpoint
    severity_on_silence: warning
    cicatrix_refs: []

  - id: sota.m13_collect
    runtime: pro_launchd
    type: cron
    expected_hb_seconds: 90000
    owner_module: apps/backend-rag/backend/services/sota_loop/m13_collect.py
    dependencies:
      - infra.postgres
      - wr2.supervisor
    recovery_action: launchctl_kickstart
    recovery_params:
      host: pro
      label: com.balizero.sota.m13-collect
    severity_on_silence: warning
    cicatrix_refs: []

  - id: sota.m13_monthly
    runtime: pro_launchd
    type: cron
    expected_hb_seconds: 2678400
    owner_module: apps/backend-rag/backend/services/sota_loop/m13_monthly.py
    dependencies:
      - infra.postgres
      - wr2.supervisor
    recovery_action: launchctl_kickstart
    recovery_params:
      host: pro
      label: com.balizero.sota.m13-monthly
    severity_on_silence: info
    cicatrix_refs: []

  - id: sota.m13_weekly
    runtime: pro_launchd
    type: cron
    expected_hb_seconds: 691200
    owner_module: apps/backend-rag/backend/services/sota_loop/m13_weekly.py
    dependencies:
      - infra.postgres
      - wr2.supervisor
    recovery_action: launchctl_kickstart
    recovery_params:
      host: pro
      label: com.balizero.sota.m13-weekly
    severity_on_silence: warning
    cicatrix_refs: []
```

### 5.2 Test (single new test class added to test_validate_genome.py)

A single test class `TestW1_5MissCritici` with 4 test methods:

- `test_nlm_bridge_enrolled` — id, type=daemon, severity=critical, http
  bridge to :18790/health
- `test_cell_observatory_triplet_enrolled` — 3 cell-observatory ids exist
  with correct types (daemon + 2 crons) and the daemon has a state_file
  bridge
- `test_post_publish_poller_enrolled` — id, type=cron, severity=error,
  recovery label
- `test_sota_m13_quartet_enrolled` — 4 sota.m13_* ids exist, all type=cron,
  expected_hb_seconds matches schedule (daily / weekly / monthly), and all
  depend on `wr2.supervisor`

Family-grouped per the orchestrator brief; one test per family covers
the 9 organi without redundant assertions per-organ.

### 5.3 Checksum update

After committing the YAML edits, run:

```bash
cd apps/organism && python -m organism.tools.validate_genome --update-checksum
```

The validator strips header comments via `yaml.safe_dump`. Re-apply the
header preamble (lines 1–43 of genome.yaml) by hand after `--update-checksum`
— same protocol as W1.

## 6. Data flow

Identical to W1 §6. plist file → classify → derive expected_hb_seconds →
genome.yaml entry. No new data flow.

## 7. Error handling

Identical to W1 §7. The pre-commit hook + 18+ unit tests catch
schema/dependency/checksum errors. No new error classes introduced by
W1.5.

## 8. Testing

- Pre-commit `python -m organism.tools.validate_genome` PASS after every
  commit.
- 4 new test methods in `TestW1_5MissCritici` (one per organ family) PASS.
- All existing tests in `apps/organism/tests/tools/test_validate_genome.py`
  PASS unchanged (regression guard).
- OSINT field leak grep CLEAN.
- Tri-LLM cross-check 2/3 minimum (Claude self + Codex sandbox + Gemini OR
  DeepSeek; relaxed under capacity exhaustion).

## 9. Build sequence (2 commits)

| # | Commit | Files | Validator | Push |
|---|---|---|---|---|
| 1 | `docs(symbiosis): W1.5 MISS CRITICI design + plan` | this file + plan doc | — | within 30s |
| 2 | `feat(organism): enroll Wave 1.5 MISS CRITICI (78→87)` | genome.yaml + tests + checksum | PASS | within 30s |

Compound atomic `git add && git commit && git push` per W1.

## 10. PR deliverable

**Title**: `feat(organism): enroll Wave 1.5 MISS CRITICI organi (78→87)`

**Body** (template):

```markdown
## Summary

Wave 1.5 of the Symbiosis Turn-On Plan, follow-up to PR #488 W1
(merged 2026-05-07). Enrolls the 9 MISS CRITICI organi flagged in the
W1 tri-LLM cross-check, expanding the registry from 78 to 87 entries.

Closes #490.

## Organi enrolled (9)

| ID | Plist label | Type | Severity | Why critical |
|---|---|---|---|---|
| `nlm.bridge` | `com.balizero.nlm-bridge` | daemon | critical | Federation v3 A2A Agent 8 (uvicorn :18790). Async multi-doc synthesis fails silently when down. |
| `cell.observatory` | `com.nuzantara.cell-observatory` | daemon | critical | Listens on PG channels `federation_alert` + `cell.pulse.observed`. FAD is blind without it. |
| `cell.observatory_prune` | `com.nuzantara.cell-observatory-prune` | cron | warning | Self-maintenance (daily 04:00 prune). |
| `cell.observatory_selfcheck` | `com.nuzantara.cell-observatory-selfcheck` | cron | warning | 5-min health probe of the observatory daemon. |
| `pro.post_publish_poller` | `com.balizero.post-publish-poller` | cron | error | Final pipeline motor: SEO + Fireworks Flux.1 cover + git push. |
| `sota.m13_checkpoint` | `com.balizero.sota.m13-checkpoint` | cron | warning | Lamarckian feedback distillation — daily 09:00 checkpoint. |
| `sota.m13_collect` | `com.balizero.sota.m13-collect` | cron | warning | post_metrics_history collector (RunAtLoad-driven). |
| `sota.m13_monthly` | `com.balizero.sota.m13-monthly` | cron | info | Monthly rollup (day-1 04:30). |
| `sota.m13_weekly` | `com.balizero.sota.m13-weekly` | cron | warning | Weekly rollup (Sun 06:00). |

## Verification

- [x] Smoke-test all 9 plists bootstrapped on Pro (launchctl print)
- [x] Pre-commit `validate_genome` PASS
- [x] OSINT field leak grep clean
- [x] 78 + 9 = 87 organi in registry post-commit
- [x] Validator unmodified (no schema change required)
- [x] Tests added: family-grouped per organ family
- [ ] Tri-LLM cross-check (filled in pre-merge)

## Refs

- W1 PR (merged): #488
- Doctrine: PR #479
- Issue: #490
- W1 design: `docs/superpowers/specs/2026-05-07-symbiosis-w1-genome-enroll-design.md`
- W1.5 design: `docs/superpowers/specs/2026-05-07-symbiosis-w1.5-miss-critici-design.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

## 11. Out of scope

- 13 active-active mata_garuda labels (W2-C separato)
- Wave 2 nuovi organi (Wave 3 separato)
- mini_launchd runtime extension (already shipped in PR #488)
- `com.nuzantara.organism.supervisor` — NB-1 flagged as "likely legacy
  artifact" in W1 PR; verify-or-remove is a separate decision, not part
  of W1.5
- Strict typing of `duplicates_id` in validator
- Backfilling `bridge_source` for the 4 sota.m13 + post_publish_poller
  entries (their wrappers don't emit last-seen JSON yet — separate W2
  sidecar work)
