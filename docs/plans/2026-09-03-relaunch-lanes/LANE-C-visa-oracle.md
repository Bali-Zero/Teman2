# LANE C — Visa Oracle: source currency, seq-15, gold ruling sheet, red PR

**Machine:** Mini (Python-only, long replays; one `ssh pro` step for the sentinel install).
**Corner:** `.agents/skills/visaoracle/SKILL.md` — read `## LIVE STATE` FIRST (the 2026-08-29 and
2026-08-23 entries), `CURRENT_STATE.md` is archaeology. **Contract:** `README.md` here.

Production is **SHADOW / NO-GO** and stays so. This lane closes enforce-gate PRECONDITIONS; it never
touches `VISA_ENGINE_EVALUATE_MODE`. A future session must not read progress here as momentum
toward the flip.

## C1 — All 18 OFFICIAL_PORTAL sources are STALE (ledger 2026-08-30)

- The engine refuses correctly because every source in the ACTIVE pack is past the freshness
  window. Rows to read on `origin/main` first: seq-17 re-stamp "attestation unprovable from the
  artifact" (2026-08-31), "four places still call the window 7-day" after seq-18 widened it,
  "RulePack `version` field", "seq-16".
- Design the re-attestation so it is PROVABLE from the artifact (what was fetched, when, hash,
  by whom) — the imigrasi mirror on Mini (`scripts/imigrasi_mirror/`, LaunchAgents
  `com.nuzantara.imigrasi-mirror.daily/.weekly`) is the natural evidence source; the ledger says the
  ARMED copy has no repo trace for its plists — measure and promote.
- Then re-stamp as a new pack seq (signed, SHADOW), prove-live by probe.

## C2 — `pro.visa_freshness_sentinel`: built, born, never installed (ledger 2026-08-20)

- 19 tests green, wrapper + plist in `infra/launchagents/`. From Mini: `ssh pro`, copy wrapper to
  `~/scripts/` and plist to `~/Library/LaunchAgents/`, `launchctl bootout` + `bootstrap` (never
  `kickstart -k` — it does not reload the plist env), then `launchctl print` and a heartbeat read.
  Verify the pair with `python3 scripts/lint_home_fork.py` afterwards. Its alert path row
  (2026-08-31) must be proven with a real send through `tg_notify.py`, judged on the status word.

## C3 — seq-15 (E31B/E31D fail-open repair): authored, activation unknown

- Ledger 2026-08-29: `op:known` on `family.sponsor_status_code` repaired at pack level. Read the
  activation ledger via `scripts/pg.sh` (never `fly pg connect`, never `ssh console` without `-C`):
  which seq is ACTIVE, is seq-15 folded into the current signed bundle? If not, sign + activate in
  SHADOW with the two-login ceremony the 2026-08-08 activation used, prove by probe
  (`sponsor_status_code="NONE"` must no longer be SUPPORTED).

## C4 — Gold 4/20 divergences: produce the RULING SHEET, not a decision

- `gold_coverage_eval.py` / `gold_coverage_replay.py` (under
  `apps/backend-rag/backend/scripts/visa_engine/`) and the report
  `research/visa/2026-08-28-visa-oracle-gold-coverage-and-divergence-adjudication.md` exist. The
  precondition closes only when Zero ratifies expectations. Deliver one table: divergence ·
  canonical expectation · engine answer · proposed cause · YES/NO box — ≤ 1 page, into
  `ZERO-DECISIONS.md` item 6. Add the 7 uncovered products' personas (E31E, E31G, E31H, E31J, E33,
  E33E, E33F) — mechanical, Sonnet builder, behind `test_gold_coverage_floor.py`.

## C5 — PR #5037 (consultant-request tables, migrations 293/294/295) is ARMED and red

- Red on `Backend Shard 2` + `Backend Tests (Python)` + harness floor. Diagnose the FIRST red job
  (shards are fail-fast). If the cause is the base having moved, `bash scripts/mq.sh requeue`; if
  it is the code, fix in a NEW PR from fresh main and close #5037. Three rounds max.

## C6 — Small, spec-only

- 56 interview questions carry `sensitive:` and no code reads it: write the spec that says what
  should (DPIA V2 §A pointer), do not code it here.
- `Visa Oracle fullstack smoke (advisory)` has never been green since #4709: fix or delete; an
  advisory that is always red is noise (Lane F may take it if you run out of budget).

## LIVE STATE (update before ending the session)

- 2026-09-03: nothing proved yet. Order: C2 (one hour, unblocks C1's evidence) → C1 → C3 → C4 →
  C5.
