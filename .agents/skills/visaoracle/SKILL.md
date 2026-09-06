---
name: visaoracle
description: "Corner for Visa Oracle v2 — the immigration Decision Tree rebuild (Bali Zero flagship). Load FIRST on any Visa Oracle / visa funnel work."
---

## Notes (moved from description 2026-09-02)

Holds: live state, established truths, research log, loop protocol.

# VISA ORACLE v2 — Decision Tree (corner /visaoracle)

> **CURRENT HANDOFF (read first):** read **LIVE STATE** below FIRST — it is the current record,
> updated on every state change. `CURRENT_STATE.md` is a SUPERSEDED 2026-08-15 snapshot (reviewed
> SHAs, gate matrix, evidence, safe resume sequence as of that date) kept as archaeology; four pack
> activations (seq-9 through seq-12) have shipped since it was last touched. Production verdict is
> unchanged from that snapshot: **NO-GO / SHADOW**, repository G0–G6 passed on the frozen baseline.

## Mission

Rebuild the Visa Oracle immigration funnel as Bali Zero's flagship public tool: an interactive
decision tree guiding foreigners to the correct Indonesian visa/stay-permit path. Bar: (a) stunning
interactive aesthetics ("immediatezza estetica"), (b) simple, impeccable content — zero wrong
answers, (c) authoritative enough to demo to Ditjen Imigrasi Jakarta, (d) a true expat guide.
Mandate: Zero, 2026-07-17. Working mode: multi-LLM deep-research ↔ brainstorm loop (unlimited
rounds), all work in worktree `mouth-visa-oracle` until final draft for operator analysis. This is
Subhi's surface (`apps/mouth`) — verification per CLAUDE.md §13 (CI + AI review, generator≠grader).

## ENFORCE-GATE (canonical ruling as of 2026-08-08 — NO-GO / SHADOW)

**The 2026-08-08 Zero ruling supersedes the 2026-07-19 gate proposal.** There
is no automated traffic-volume threshold for ENFORCE: no 1,000 sessions/7d,
no 100 real sessions/14d fallback and no Wilson lower-bound test. Organic
traffic measurements remain useful diagnostic evidence, but they neither
authorize nor mechanically block the mode change. The business-validation
gate is Bali Zero team heavy-testing and verification against the engine in
SHADOW. See
`research/visa/2026-08-08-decision-tree-v2-full-index-design.md` §4.

ENFORCE remains a distinct, explicit Zero-gated action. A session must not
infer pre-authorization from operational checks, a RulePack activation,
traffic counts or this skill. It must keep `VISA_ENGINE_EVALUATE_MODE=SHADOW`
until all of the following are true:

- the Bali Zero team has completed heavy manual SHADOW testing and signed off
  the observed outcomes;
- the current gold-persona replay has zero unexplained divergences;
- current decisions carry valid, in-force citations and no ungrounded claims;
- the kill switch has a current, independently reproducible rollback proof —
  **SATISFIED 2026-08-23**, see LIVE STATE below and
  `research/visa/2026-08-23-killswitch-rollback-proof.md` (this bullet alone; the other six are
  untouched and this does not authorize ENFORCE);
- the DPIA is complete, signed and its residual privacy risks are accepted;
- the real analytics destination/provider is identified and a fresh,
  closed-schema **365-day (12-month)** TTL proof has been independently
  reproduced (corrected 2026-08-23 — Zero's 2026-08-20 retention ruling,
  DPIA V2 §A, superseded the old 90-day provisional; §8 signed 2026-08-23,
  `docs/audits/2026-08-20-visa-oracle-dpia-v2.md`; still unsatisfiable
  today — the destination itself remains unidentified, see LIVE STATE
  below); and
- Zero explicitly authorizes the ENFORCE flip after the preceding blockers
  close.

**Current status: 🟢 ENFORCE IN PRODUCTION since 2026-09-06T01:1xZ — OWNER
OVERRIDE.** Zero flipped `VISA_ENGINE_EVALUATE_MODE=ENFORCE` on Fly
(`nuzantara-rag`) by his own explicit instruction ("accendi tutto",
2026-09-06, after being told the DPIA v2 §8 text still reads "DO NOT
ENFORCE" with two High residual risks open — analytics destination,
cross-border processor register — and that gold-persona divergences were
not re-measured on seq-19). The seven preconditions below remain the
documented standard; the ones still open are now RESIDUAL RISKS to close
in production, not blockers. Rollback is one command:
`fly secrets set VISA_ENGINE_EVALUATE_MODE=SHADOW -a nuzantara-rag`.

Traffic provenance must stay explicit while evidence is collected. Only
requests deliberately labelled `traffic_source=real` are organic evidence;
synthetic lanes stay separate and legacy/NULL rows are not silently promoted
to real traffic. This classification is diagnostic under the current ruling,
not an automated ENFORCE threshold.

## Established truths (GROUND 2026-07-17, scout-verified file:line)

- **v1 is LIVE, not missing** — www.balizero.com/visa, last touched 2026-07-14, 29 commits/90d.
  "Rebuild" = experience + content layer, NOT greenfield.
- Frontend: `apps/mouth/src/app/visa/` — entry branch-selector ("Already in Indonesia?") →
  `/visa/clock` (expiry countdown, 133 lines) | `/visa/match` (4-step wizard:
  nationality→purpose→duration→budget, 315 lines); decision tree logic in
  `apps/mouth/src/lib/visa-oracle/quiz-logic.ts` (84 lines, 7 purposes); AI chat layer
  `apps/mouth/src/components/visa/VisaChat.tsx` (341 lines → `/visa-oracle/chat`); shareable hash
  result URLs; Playwright E2E `apps/mouth/e2e/visa-funnel-fusion.spec.ts`.
- Shared funnel framework: `packages/core/` (`@balizero/core`) — AppFrame / AppWizard /
  AppBranchSelector / useFunnelApp — proven across visa + property-eligibility + tax-calendar.
  REUSE-FIRST candidate #1.
- Also reusable: `apps/mouth/src/components/blog/interactive/DecisionTree.tsx` (553 lines, generic
  tree primitive).
- Backend (FastAPI, all registered in `router_registration.py`): `routers/visa_check.py` (346 l.,
  `/api/visa`: clock+match), `routers/visa_oracle.py` (928 l., `/visa-oracle`:
  recommend/chat/handoff/visa-types), `routers/knowledge_visa.py` (CRUD catalog, backs MCP
  list_visa_types/get_visa_details); services `visa_check/match_tree.py` (the real tree logic),
  `visa_oracle/visa_oracle_service.py` (471 l., scoring), `visa_unified/bridge.py`. Full pytest
  coverage exists.
- Data: `migrations_v2/124_visa_checks.sql` (visa_checks table, hash URLs); seed
  `seed_visa_types_complete_2026.py` = **114 visa codes** (A1→F4, incl. E28A investor, E33A-G
  digital-nomad/retirement family) — the canonical catalog; Qdrant `visa_oracle` collection ~90
  curated points.
- Paper trail: `docs/plans/2026-04-19-4apps/01-visa-check.md` (the executed v1 spec);
  `docs/superpowers/plans/2026-04-04-visa-oracle-implementation.md` + specs;
  `2026-04-21-visa-funnel-fusion.md` (PR #165); `2026-04-21-visa-catalogue-rebuild.md`. Unexplored:
  `apps/mouth/src/app/(assessment)/`, `apps/kb/data/immigration`.
- Unrealized vision from memory: "3D FUNNELS: Waypoint 1.5 (Overworld)" (2026-04-12) — candidate
  inspiration for v2 metaphor.

## Arsenal & seat status (probed live 2026-07-17)

- Gemini 3.1 Pro (High) via `agy` v1.1.3 — ARMED. GOTCHA: flag order changed vs v1.0 — use
  `agy --print-timeout 15m --model "Gemini 3.1 Pro (High)" -p "<prompt>"`; the old
  `agy -p --print-timeout 5m` feeds the FLAGS as prompt (RC=0, garbage out).
- Codex GPT-5.6-sol ultra — ARMED (PONG).
- GLM 5.2 via TP1 seat `tp1-glm-5.2` (OpenAI-compatible base `https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`, key loaded by `load_tp1_settings_key()` from `~/.qwen/settings.json`) — ARMED (PONG). TP1 seats are roster lines, not CLIs.
- DeepSeek V4 — **DEAD** (balance -0.04 USD, is_available:false). Operator-only top-up. Declared
  substitute: house Sonnet web-grounded lane (live WebSearch, URL-verified).
- Harness scar (2026-07-17): Agent spawns WITH `name:` can be born dead (mailbox never delivered) —
  spawn anonymous for fan-out.

## Loop protocol (the pallegiamento)

Round N = 4-lane parallel deep research (Gemini width / Codex architecture+red-team / GLM design /
web-grounded verification) → orchestrator reports ALL content faithfully to Zero → brainstorm →
interesting points spawn round N+1 research. No round limit. Opus 5 orchestrates only (no hands,
hook-enforced — RULED 2026-08-20: Fable is out of the workflow, CLAUDE.md §5); Sonnet implements; research outputs persisted under `research/visa/` in the worktree
as `2026-07-17-visa-oracle-v2-round<N>-<lane>.md`.

## LIVE STATE (update on every state change — whoever changes state updates this section)

- 2026-09-06 (M5, owner decision — ENFORCE + GARUDA VOA public): **this is an owner decision
  recorded by the session, not a session-inferred authorization.** (1) Production evaluate mode
  measured `mode='ENGINE'` at 01:1xZ via `probe_evaluate.py` (was `CURATED`), rule pack seq-19
  v2026.9.5, backend healthy — visitors of `/visa-oracle` now see real verdicts (the frontend's
  `requireEngineResponse` boundary in `_lib/engine-response.ts` passes ENGINE envelopes; in
  SHADOW it withheld every decision). (2) The same Fly command also set
  `GARUDA_PUBLIC_ENABLED=true` on the backend, and Zero added `GARUDA_PUBLIC_ENABLED=true` to
  the Vercel `mouth` Production environment (Vercel marks Production vars sensitive by default,
  so `vercel env pull` shows `""` — not empty); `/visa/voa` proven LIVE in headless Chromium at
  02:4xZ (h1 "Visa on Arrival", step 1 of 4, 0 console errors) after the alias moved to a
  deployment built after the var, and re-proven after promoting `mouth-f4mditqo6` at 02:55Z;
  gotcha: `vercel ls` "Ready" is not the same as aliased — the truth is
  `vercel inspect https://balizero.com --scope nuzantara-2026`, and production deployments were
  NOT auto-promoted (used `vercel promote`). (3) What stays open as residual risk: DPIA v2 two
  High rows, gold replay on seq-19, team manual sign-off. (4) Rollback commands for both
  switches — mode: `fly secrets set VISA_ENGINE_EVALUATE_MODE=SHADOW -a nuzantara-rag`; VOA
  public: `vercel env rm GARUDA_PUBLIC_ENABLED production` + redeploy/promote.

- 2026-09-05 (M5, two-consul lane — seq-19 SIGNED + ACTIVATED): **SEQ-19 IS THE ACTIVE PRODUCTION
  PACK (SHADOW; activation ≠ ENFORCE, `VISA_ENGINE_EVALUATE_MODE` untouched).** Chain as MEASURED in
  `visa_rule_packs` (readonly, 21:05Z, before the ceremony): 13 → 16 → 17 → 18 (seq-14/15 were never
  inserted; the seq-17/seq-18 activations of 2026-08-30 had no entry here — seq-18 was activated
  2026-08-30T17:28:56Z by `operator.zero.freshness-window-2026-08-31`, activation
  `be75facc-b1c0-4daa-ae87-247b5bd408d2`, payload `5a24472d…`). seq-19 = seq-18 + seq-15's E31
  fail-open repair re-landed (fold PR #5784, source `rulepack-prod-019.source.json`, 109 rules: the
  only delta vs 018 is the two `el.e31d` byte-duplicates removed; `review.e23u|e23v.requested-product`
  KEPT after a gate BLOCK caught their removal). Signed by Zero on M5 (`sign_pack.py`, kid
  `prod-2026-07-1`, `signed_at 2026-09-05T20:48:52Z`, payload_sha256
  `bac5da8e4727e7f639c947c50211e6f95e15c1403cf6aef0dd57a92014d6e6ea`, rule_pack_id
  `8c09e059-4ab2-5963-b5af-d1363d55e508`); bundle PR #5812 gated by an independent Opus-xhigh reader
  (mutation-verified) + the session's read (PASS-WITH-CONDITIONS, four low evidence/wrapper
  follow-ups), merged 21:48:28Z (`4b06438363`), file on `origin/main` byte-identical to the signed
  one. **Activated 2026-09-05T21:52:20.519792Z** (Zero's explicit authorisation the same evening):
  `activate_pack.py --yes` with two DISTINCT ephemeral logins (`visa_pack_writer_ceremony_260906` IN
  ROLE `visa_pack_writer`, `visa_activation_ceremony_260906` IN ROLE `visa_activation_executor`, minted
  and dropped by Zero on the PG primary `0801696b541568`, leftover 0), actor `fable-session-m5`,
  reason `seq19-shadow-activation-260906`, `activation_id 891720d3-e391-413f-8b5f-968889a4bd28`. DB
  verified readonly with the runtime predicate (`legal_period @> now() AND system_period @> now()`):
  exactly ONE open activation = seq-19; seq-18 `system_period` closed at the same instant, no gap.
  **PROVE-LIVE:** `POST /api/visa-oracle/evaluate?traffic_source=synthetic_driver` ×2 → HTTP 200,
  `mode=CURATED`, `rule_pack sequence=19 version=2026.9.5`; all-UNKNOWN facts →
  `HUMAN_REVIEW_REQUIRED` (fail-closed). Ceremony gotchas measured this time: `activate_pack.py`
  needs NO `JWT_SECRET_KEY`/`API_KEYS` dummies and its dry-run opens no DB connection; `DROP ROLE`
  of an ephemeral role fails on "privileges for database" until `REVOKE CONNECT ON DATABASE` runs
  first; the session's security classifier refuses superuser `psql` on the primary, so mint/drop
  are the owner's `!`-prefixed commands while proxy/dry-run/`--yes`/verification/smoke stay with
  the session. ENFORCE-GATE unchanged: 🔴 NO-GO / SHADOW.

- 2026-08-29 (M5, gold-coverage lane, PR #5182): **the 4/20 zero-movement wall now has a first
  instrument and a first corpus.** New offline helper `gold_coverage_eval.py` (single persona →
  exact replay path vs highest signed pack) + `gold_coverage_replay.py` (fail-closed corpus runner)
  - **18 synthetic personas** — one per SUPPORT-reachable product the 20 canonical expectations
    never name — each proven `SUPPORTED_CANDIDATES`, behind `test_gold_coverage_floor.py` (any
    persona losing its product's support goes red). Report
    `research/visa/2026-08-28-visa-oracle-gold-coverage-and-divergence-adjudication.md`: full
    16-divergence matrix vs seq-13 with PROPOSED causes (no acceptance — owner act), **E31B/E31D
    fail-open re-confirmed live by probe** (sponsor_status_code="NONE" still SUPPORTED; FAMILY intent
    alone → E31D), the two stepchild evidence facts confirmed referenced by ZERO rules, blocked
    census 9. Limits: cross-family tie-breaks and realism refutation did NOT complete (session caps;
    per-lane artifacts lost) — 9 disagreement personas flagged in the report; 7 products still
    uncovered (E31E,E31G,E31H,E31J,E33,E33E,E33F — mechanical follow-up). The 4/20 gold-persona
    divergence PRECONDITION of the enforce-gate is NOT closed by this: expectations remain
    un-ratified; this entry adds the measuring instrument, not the ruling.

- 2026-08-23 (M5, dedicated verification lane — kill-switch rollback proof; **corrected same day
  after a real cross-family adversarial review found the first version's pack-rollback proof
  FATALLY incomplete — see below**): **THE ENFORCE-GATE'S "kill switch has a current,
  independently reproducible rollback proof" PRECONDITION IS NOW SATISFIED.** This closes ONLY
  that one precondition — it does not touch, weaken, or move any of the gate's other six
  preconditions (DPIA, analytics-TTL, gold-persona divergence, source currency, Bali Zero manual
  SHADOW sign-off, Zero's explicit authorization), and it does **not** authorize ENFORCE or change
  the posture: `VISA_ENGINE_EVALUATE_MODE` remains `SHADOW` in production, untouched throughout
  this work. **A future session must not read this entry as momentum toward the flip.**

  **Correction note**: the first version of this entry (same date) described the PACK-rollback
  half as proven via a DB/repository-layer test that, on real adversarial review (Codex
  gpt-5.6-sol xhigh, briefed against the committed PR), turned out to use a documented-non-real
  placeholder hash and a fabricated signature, and never drove the real evaluator — it proved
  ledger bookkeeping, not that a restored pack actually reproduces the original's decisions. That
  proof was rebuilt for real (real Ed25519 signing, real verification, real evaluator, real
  decision-equality assertion) before this precondition was allowed to stay marked satisfied; two
  other absolute claims in the first version were also narrowed after the same review (below).
  This is the corrected wording; the report itself documents the full review in its own
  `## Adversarial review` section.

  Full artifact: `research/visa/2026-08-23-killswitch-rollback-proof.md` (+ two re-runnable
  companion scripts in the same directory: `2026-08-23-killswitch-mode-proof.py`,
  `2026-08-23-killswitch-pack-rollback-proof-test.py`). Two genuinely distinct kill switches were
  identified, read, and driven end-to-end through the real code path — never against production —
  in a dedicated worktree.

  **(1) The MODE switch** (`VISA_ENGINE_EVALUATE_MODE`, `evaluate_path.py:212-243`): unset/invalid
  fails closed to `OFF` (never `ENFORCE` — the only fallback path in `resolve_evaluate_mode()`),
  read fresh from `os.environ` on every call (no import-time cache, no redeploy required by the
  code itself). Reproduced locally by driving `run_evaluation()` directly with identical
  applicant facts and the identical gold TEST pack across all three values in one process:
  `SHADOW` reaches a real, non-abstaining `decision_state` (`HUMAN_REVIEW_REQUIRED`) but the
  response carries `"mode":"CURATED"` (non-authoritative); `ENFORCE` reaches the IDENTICAL
  `decision_state` but `"mode":"ENGINE"` (authoritative) — proving the switch changes AUTHORITY,
  not the answer; `OFF`/unset/`BOGUS` all collapse to `decision.state="TEMPORARILY_UNAVAILABLE"`,
  `outage.code="EVALUATE_SURFACE_DISABLED"`, zero DB writes (proven with a pool sentinel that
  raises on any attribute access — the OFF path never reaches I/O). Mechanism verified unchanged
  since the 2026-08-08 live drill recorded above (only 1 commit has touched `evaluate_path.py`
  since then, and it does not touch the mode resolver — checked via `git log`/`git show`, not
  assumed). **Scope, narrowed after adversarial review**: this is the BACKEND resolver
  (`evaluate_path.resolve_evaluate_mode()`) only. The frontend has a separate resolver,
  `resolveVisaOracleMode()` (`apps/mouth/.../_lib/runtime-mode.ts:21-32`), that fails OPEN to
  `"ENGINE"` on unset/invalid outside a test build — a real, confirmed asymmetry, not currently
  exploitable on its own (the adapter still requires a genuine ENGINE envelope from this backend),
  but not covered by the proof above.

  **(2) The PACK rollback** (`activate_pack.py` / `replace_activation_set.py` +
  `visa_activate_rule_pack` / `visa_replace_activation_set`, migrations 250/251/253/267 — 253
  hardens/replaces the insert-guard trigger 250 originally created; cite 253 as the live
  definition): **no code path available to the intended executor role — trigger enabled, normal
  `session_replication_role=origin` — can reactivate a pack at sequence ≤ the current head**
  (narrowed after adversarial review: an ordinary trigger IS bypassable via
  `session_replication_role=replica` or direct `ALTER TABLE ... DISABLE TRIGGER` by a
  table-owning role — this repo's own `test_repository.py:1316` proves the second form
  practicable — but the production executor role holds only `EXECUTE` on the activation
  functions, never table-owner/superuser privileges, so it cannot reach either bypass). Enforced
  independently by (a) the Python `validate_activation` pre-gate, (b) the SQL trigger
  (`reject_visa_activation_insert`, migration 253's current body) that re-derives the TRUE current
  head live from the table rather than trusting the caller's
  `--current-sequence`/`--current-payload-sha256` arguments, and (c) for the multi-segment path,
  `visa_replace_activation_set`'s own explicit chain-walk. The system's actual rollback mechanism
  is therefore: **re-sign the desired content as a NEW pack at the next sequence, chained via
  `previous_payload_sha256` from the true current head, and activate that** — exactly the pattern
  already used live for the 2026-08-08 Cameroon/Guinea Calling Visa fix above. Proved three ways,
  all today, all local, no production DB touched: (i) the existing reviewed integration suites
  re-run fresh against an ephemeral pytest-xdist-cloned throwaway Postgres database
  (`test_activation_writer.py` 43 passed/1 skipped, `test_replace_activation_set.py` 10 passed,
  `test_activate_pack.py` 17 passed — never the shared `nuzantara_test`/`nuzantara_dev` DB their
  own docstrings warn against; corrected 2026-08-23, count fix — the original entry read
  44/11/18, each inflated +1 by transcribing pytest's "N collected" as "N passed" without
  subtracting the 1 skip; re-measured against merge commit `292795a26364d` with `pytest -n 1 -q`
  on each file, zero failures, see the report's own correction note for detail); (ii) a custom
  end-to-end ceremony test using REAL Ed25519-signed packs over the real evaluatable TEST rule
  pack (not placeholder hashes — see correction note above): activate real pack A seq1 → real
  decision via the unmocked evaluator =
  `SUPPORTED_CANDIDATES [C1]` → activate real "bad deploy" pack B seq2 (tightened HARD_FILTER,
  chained from A's real hash) → SAME facts now genuinely EXCLUDE C1 through the real evaluator →
  naive reactivation of A REJECTED while B is head, B verified untouched → re-sign A's exact
  content as real pack C seq3 chained from B's real hash → activates cleanly, exactly ONE open
  activation, B/C `system_period` adjacent with zero temporal gap → **driven through the same real
  unmocked evaluate path, C reproduces A's exact original decision**: `SUPPORTED_CANDIDATES [C1]`
  with identical `reason_codes`/`product_version_id` — not merely a matching ledger row; (iii) the
  actual `activate_pack.py` CLI run as a real subprocess (dry-run, zero DB access by construction)
  against the repo's checked-in signed TEST pack with real Ed25519 verification — bootstrap
  accepted, naive same-sequence reactivation rejected with `"candidate sequence 1 is not greater
than the current sequence 1"`, exit 1.

  **Environment disclosed, per the "reproducible" requirement — do not silently re-run on a
  different one and compare results without accounting for this**: local Postgres was **17.10**
  (M5's existing Homebrew instance), while CI's visa_engine integration jobs run
  **`postgres:15`** (`.github/workflows/tests.yml:501,1385`,
  `scripts-tests-sweep.yml:97`, `intel-router-tests.yml:30`) — no Docker was available in this
  environment to match exactly. Judged low-risk (the code is explicitly PG17-aware exactly where
  it matters — `_supported_table_privileges()` branches on `server_version_num >= 170000` for the
  PG17-only `MAINTAIN` privilege — and no PG16/17-only syntax was found in migrations
  250/251/253/254/267), and this is now a doubly-checked non-finding rather than a single-pass
  hedge: the adversarial review above was specifically briefed to find a PG15/17 divergence risk
  in this mechanism's actual primitives (triggers, `session_replication_role`,
  `pg_advisory_xact_lock`, ranges/`range_agg`, `SECURITY DEFINER`/search_path/privileges) and
  reported none. Direct measurement on a real `postgres:15` instance is still the one thing that
  would raise this further; exact re-run command is in the report §3 (`TEST_DATABASE_URL` pointed
  at a `postgres:15` Docker container, same `pytest -n 1` invocations) — not required to close
  this precondition. Also used local role `test` in place of CI's `nuzantara` (absent on this
  machine) — benign (both local superusers on a throwaway DB) but disclosed rather than silent.

  Safe, exact, never-executed operator commands for a REAL production drill of each switch (for
  whoever eventually runs one) are preserved in the report §1.4 (MODE: `fly secrets set
VISA_ENGINE_EVALUATE_MODE=OFF`/`SHADOW`, expected outage-code/verdict transitions) and §2.4 (PACK:
  the exact `activate_pack.py --yes` invocation shape against the real two-role prod DSNs,
  `operator[secret]`/`operator[credential]` — not executed, not required to close this precondition).

- 2026-08-23 (M5, truth-first ledger backfill — D1): **SEQ-12 IS LIVE IN PRODUCTION SHADOW; this
  corner's ledger had never recorded it.** `grep -c "seq-12" SKILL.md` returned 0 on both this
  checkout and `origin/main` before this entry, despite the pack chain having closed three days
  earlier: fold+source-restamp PR #4409 merged `2026-08-20T07:43:45Z` ("RulePack seq-12 — weekly
  re-attestation of all 18 portal sources") → signed on M5 (`kid prod-2026-07-1`, protected header
  `signed_at 2026-08-20T07:45:28.449722Z`, `payload_sha256
ff43d55e79e833a91820c4b68dd9ffdd086e7969b3b3a44dbd80747aa451406d`) → signed bundle PR #4413
  merged `2026-08-20T08:45:32Z`. Independently verified against the signed pack bytes on disk
  (`apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-012.signed.json`):
  `payload.sequence 12`, `payload.version "2026.8.20"`, 110 rules, 28 source_records, of which 18
  carry `authority_type "OFFICIAL_PORTAL"` re-stamped `verified_at` `2026-08-20T06:14:00Z` /
  `06:15:00Z` with `freshness_policy.max_age_seconds 604800` (7 days) → **expires
  2026-08-27T06:14Z**.

  **Sentinel (`pro.visa_freshness_sentinel`, PR #4410) is LOADED, RUNNING, and READING THE
  ACTIVE PACK FROM THE PRODUCTION DB on Pro — NOT "built but not armed" as PENDING-ARMS still
  claimed** (row closed by this same PR, scope corrected below). Re-verified live this session,
  not recalled from context: `launchctl print gui/501/com.nuzantara.visa-freshness-sentinel`
  shows the job loaded (`program /Users/nuzantara/scripts/pro-visa-freshness-sentinel.sh`);
  `~/logs/pro-visa_freshness_sentinel/run.log` and `~/.organism/last_seen/pro.visa_freshness_sentinel.json`
  report `{"ts":"2026-08-22T21:58:09Z","status":"ok","note":"run done"}` / `[2026-08-23 05:58:09]
run done rc=0` reporting `"pack_sequence": 12, "pack_version": "2026.8.20", "pack_source":
"database"` — **these are ONE run cited twice, not two witnesses**: Pro's local clock is WITA
  (UTC+8, confirmed live), so `05:58:09` local and `21:58:09Z` are the identical instant.
  `pack_source: "database"` is meaningful — `_fetch_active_pack_from_db`
  (`scripts/visa_freshness_sentinel.py:407-447`) runs a real bitemporal ACTIVE-pack query against
  Postgres (`legal_period`/`system_period @> now()`), not the labelled repository fallback — so
  this run genuinely read the live pack.

  **What this does NOT prove: that an alert would ever reach anyone.** The alert path is
  fire-and-forget by explicit design — `send_alert` (`scripts/visa_freshness_sentinel.py:626-661`,
  under a section literally headed "Telegram gateway — fire-and-forget, exact house pattern")
  routes through `scripts/tg_notify.py`, and on ANY failure (`tg_notify.py` missing, subprocess
  exception, non-zero exit) only `logger.warning` fires — the docstring states the house contract
  verbatim: "NEVER raises — a gateway failure must not crash the sentinel." **A sentinel with a
  dead Telegram path produces byte-identical evidence to what is cited above** — same `status:ok`,
  same `rc=0`, same fresh `last_seen` — because `send_alert` short-circuits to `return None` the
  instant `verdict.outcome == OUTCOME_OK`, which is exactly the outcome this one observed run had:
  the alert path was never even exercised, let alone proven to deliver. This is cicatrix
  superscar family #2 (Esiste≠Armato) — the sentinel's own `G2_heartbeat` gene names the
  discipline this entry initially failed to apply to its own claim.

  **Delivery proof is therefore still owed, ideally before 2026-08-25T06:14Z** (the sentinel's
  48h-ahead warn window on the 2026-08-27T06:14Z expiry above) — because after that date, silence
  from the sentinel is ambiguous: equally consistent with "nothing to warn about yet" and with
  "the send path is dead." A new PENDING-ARMS row is opened for this (owner: team-lead/orchestrator
  session, this same review lane — proof-of-armed = an observed test alert actually arriving on
  Telegram, not another green run log). The PENDING-ARMS row this PR closes is narrower than that
  and stays closed: its own proof-of-armed clause (fresh `last_seen` AND non-fallback
  `pack_source`) asked only about load+DB-read state, and that clause is genuinely satisfied — the
  delivery gap is a distinct, newly-opened claim, not a reopening of the old one.

  **CORRECTION, amended same day (2026-08-23) — this entry's own first version overclaimed.**
  The two "residual doctrine gaps" this backfill's own originating mandate named as open are
  PARTIALLY cured since seq-10 (2026-08-19), not fully as the first version of this entry said.
  Verified against the signed seq-12 payload bytes, not against any narrative:
  `el.c2.corporate-sponsor-type` is **ABSENT** from `rules[]` (retired behavior-preservingly in
  seq-10 — its promised tightening was refuted by the live C2 page, CF-17). `el.e31c-mixed-marriage-parents`
  is **PRESENT**, tightened to 4 conjuncts (`intent.purposes intersects [FAMILY]`,
  `family.relation_to_sponsor eq PARENT`, `family.sponsor_nationalities intersects [ID]`,
  `family.marriage_registered eq true`). NEW `hf.e31c-marriage-not-registered` is **PRESENT**
  (`stage HARD_FILTER`, `effect.type EXCLUDE`, `safety_critical: true`), scoped to 3 conjuncts
  (drops the nationality conjunct so non-FAMILY paths stay uncontaminated). **That registration
  leg genuinely works** — fail-closed EXCLUDE on `marriage_registered: false`, `BLOCKED_UNKNOWN`
  on unknown (engine precedence: a definite-TRUE hard filter returns EXCLUDED before any SUPPORT
  rule is even consulted). The cure shipped in seq-10 (PR #4350, 2-family refuter quorum — Codex
  GPT-5.6-sol xhigh REJECT→cured, Kimi K3 MAJOR→cured; see the 2026-08-19 third LIVE STATE entry
  below for the full chain); rationale on main at
  `research/visa/doctrine-factory/e5/inc4-pack-edits/cure-c2-e31c.md`.
  `apps/backend-rag/backend/tests/services/visa_engine/test_seq10_pack.py` already asserts this
  cure structure. `test_pack_chain_and_pricing.py:370`'s `_KNOWN_PRE_EXISTING_LINT_RESIDUALS`
  still names both rule ids — that is CORRECT and deliberate: it is scoped to the `seq9_source`
  fixture and pins seq-9's true historical state, and this entry does not touch it.

  **What the first version missed: a third E31C rule, untouched by the seq-10 cure, independently
  grants the same product.** `el.e31c-child-mixed-marriage-support` (present unchanged since
  seq-9) carries `product_version_ids: ["62ab2d13-1d7e-5048-9cf7-9622c0098439"]` — the identical
  E31C product id as both rules above — and fires SUPPORT/`PURPOSE_PRODUCT_MATCH` on exactly
  **2 conjuncts**: `intent.purposes intersects [FAMILY]` and `family.relation_to_sponsor eq
PARENT`. No `sponsor_nationalities` conjunct, no `marriage_registered` conjunct. Because
  `hit_policy.eligibility = "COVER_ALL_DECLARED_PURPOSES"` makes rule coverage OR-like — ONE
  firing SUPPORT rule suffices regardless of what sibling rules decide — this rule alone carries
  the product to SUPPORTED. **Proven live against the real evaluator, not inferred from the rule
  graph** (found by Kimi K3's cross-family review of this entry, independently re-run against
  `evaluate_product` on a real `CompiledRulePack` built from the seq-12 payload): FAMILY intent +
  PARENT relation + `marriage_registered=true` + `sponsor_nationalities=["US"]` →
  `ProductProofStatus.SUPPORTED`, `support_rules=['el.e31c-child-mixed-marriage-support']` alone
  — the tightened rule correctly withholds (no `ID` nationality) and the hard filter correctly
  does not fire (marriage IS registered), and the untouched sibling carries the product through
  by itself. Positive control: excluding the sibling from the compiled rule set in memory drops
  the identical US case to `UNSUPPORTED`, while the `ID` case still reaches SUPPORTED via the
  tightened rule alone — clean discrimination, not a shared artifact of the harness. Exactly
  three rules in seq-12 are scoped to this E31C product id; no fourth, uncited hard filter covers
  the nationality leg.

  **Client-facing shape, stated plainly because that is what a future reader needs to act on:**
  E31C is "Family Visa — Child of Legal Mixed Marriage" — a _perkawinan campuran_ is by
  definition between an Indonesian citizen and a foreign national. Today the engine reaches
  SUPPORTED for a child of two non-Indonesian parents whose marriage happens to be registered.
  The **registration leg is cured**; the **nationality leg is unenforced**.

  This defect is **PRE-EXISTING, not introduced by seq-10/11/12** —
  `el.e31c-child-mixed-marriage-support` is byte-unchanged since seq-9; it was surfaced by
  adversarial review of this entry's own overclaim, not by a new pack edit. Worth recording as
  method: the overclaim ("already cured") is what made a real, unrelated-to-the-cure gap
  findable — a correction that itself needs a correction is not a failure of this ledger's
  discipline, it is the discipline working across two rounds instead of one.

  **Correcting, not quietly dropping, this entry's own earlier conclusion: noindex condition (b)
  is NOT satisfied by seq-12, and a seq-13 IS warranted** — see the noindex bullet below and the
  new PENDING-ARMS row this entry opens for the artifact itself.

  **Zero's rulings, 2026-08-23 (Legge 5):**
  - **DPIA V2 §8** (`docs/audits/2026-08-20-visa-oracle-dpia-v2.md`) signatory fields: controller
    entity = **PT Bali Nol Impresariat**, DPO = **Zainal Abidin**. Zero gave these two identity
    fields today but NOT a signing date — the date field is left for him. Signature itself still
    pending — the retention preflight (`scripts/visa_oracle_analytics_retention_preflight.py`,
    `EXPECTED_TTL_DAYS = 90`) stays hard-locked at 90 days until §8 is actually signed
    (PENDING-ARMS row, unchanged by this entry — a separate PR).
    **Overtaken later the same day (correction, 2026-08-23):** §8 WAS signed — Zero, in person,
    same date, recorded in `docs/audits/2026-08-20-visa-oracle-dpia-v2.md` §8. PR #4593 merged
    (`adf37ca99e5`) carrying the signature and the runbook+preflight 90→365 amendment in one
    atomic commit — `EXPECTED_TTL_DAYS` is now `365`, not `90`. This does not close the
    ENFORCE-GATE analytics-TTL precondition: the destination behind
    `NEXT_PUBLIC_ANALYTICS_ENDPOINT` remains unidentified, and no real attestation (only the
    schema contract + tests against fabricated fixtures) exists yet. Independently verified via
    gate-review audit, 2026-08-23.
  - **noindex on `/visa-oracle`: RESTORE now, RATIFY at ENFORCE.** The `index: false` directive
    removed in the G0–G6 rebuild (`63234a12a`, PR #3732, 2026-08-07 — see the POSTURE FINDING
    below) is to be put back immediately; indexability itself is ratified only once ALL of:
    (a) DPIA §8 signed; (b) seq-13 active with the two doctrine gaps cured; (c) the
    SHADOW→ENFORCE decision taken (or at minimum the accuracy gate passed); (d) E30 prices
    defined. **Correcting this entry's own earlier conclusion here (found wrong the same day by
    adversarial review — see the amended CORRECTION above): condition (b) as stated names
    seq-13, and it IS actually required — not for the reason the originating mandate gave (both
    doctrine gaps assumed cured), but because the nationality leg of the E31C mixed-marriage cure
    is unenforced (`el.e31c-child-mixed-marriage-support`, 2-conjunct SUPPORT, no nationality
    check). The mandate named the right deliverable for the wrong reason; the corrected reason is
    the PENDING-ARMS row this entry opens below.** The restore action itself (an `index: false`
    code change in `apps/mouth`) is a separate PR, not this docs/ledger one, and is NOT yet
    shipped as of this entry.
  - **E30/E30E/E30F pricing formula RULED, and the PNBP research lane CONCLUDED
    2026-08-23.** Zero's formula: client-facing price = PNBP + IDR 3,000,000, exposed as one
    all-inclusive number (extends standing ruling R1 2026-07-17 — never a PNBP-vs-fee split
    shown to the client). The authoritative PNBP source is the "Biaya (PNBP)" field on the
    official per-code Ditjen page (`imigrasi.go.id/wna/daftar-visa-indonesia/<CODE>`), NOT the PP
    45/2024 lampiran — PR #4383 established this and the arithmetic reconciles exactly against
    the live price file: E30A 1y PNBP Rp 6.000.000 → listed 9.0M; E30A 2y Rp 8.500.000 → 11.5M;
    E30B 4y Rp 12.000.000 → 15.0M (all verified in
    `apps/backend-rag/backend/data/bali_zero_official_prices_2026.json` this session). The E30A
    page states its PNBP figure already composes four components (visa, ITAS, re-entry,
    verification fee) — re-deriving one from PP 45/2024 line items will NOT reproduce the portal
    figure and must not be attempted. **The formula is ruled but INAPPLICABLE to E30/E30E/E30F**:
    fetched live today (positive control on the same page shape) `E30A` returns
    `Rp. 6.000.000,-` / `Rp. 8.500.000,-` (byte-stable vs #4383, proving the fetch mechanism
    works), while `E30E` ("Visa Pendidikan Kawasan Ekonomi Khusus") and `E30F` ("Visa Pertukaran
    Pelajar") both return **`Data Belum Tersedia`** with no duration options listed at all — a
    genuine state-side absence, not a probe failure. **Correction, same day: the first version of
    this paragraph never actually fetched plain `E30` — its unpriced status was carried by
    association with its two siblings, the identical inference-from-neighbours shape the E31C
    correction above exists to warn against.** Fetched independently this session, two ways
    (a summarized fetch + a raw `curl` with tag-stripped grep on the same response, HTTP 200):
    `imigrasi.go.id/wna/daftar-visa-indonesia/E30` — title `E30 Visa Pendidikan` — ALSO returns
    `Data Belum Tersedia` immediately after the title, with no duration options, same shape as
    E30E/E30F. The paragraph's conclusion was correct; it is now measured for all three products,
    not inferred for one of them. Pricing any of the three would require asserting a PNBP the
    state has not published — a business decision (Legge 5), not a fact; do not attempt a
    workaround. **Correction to this entry's own first-pass framing here, found wrong the same
    day by adversarial review and independently re-verified against the running code, not just
    the payload: `public_catalog` is metadata with NO runtime consumer, and reading it as a
    suppression switch was the error.** Repo-wide grep for `public_catalog` (excluding
    worktrees) returns exactly one non-test hit — a plain model field,
    `VisaProductVersion.public_catalog` (`services/visa_engine/models.py:371`) — and zero hits
    in any router, service, adapter, or compiler; `compiler.py`'s `compiled_products` is built as
    an unconditional comprehension over `payload.products` with no `public_catalog` filter of
    any kind, and no `internal_only` flag or equivalent exists anywhere in the models. The raw
    field values were correctly transcribed (`E30 public_catalog: false`; `E30E`/`E30F
public_catalog: true`) — it is the SEMANTICS that were wrong: `E30` is not internal-only and
    is not exempt from needing a price. All three of `E30`/`E30E`/`E30F` are reachable by the
    compiler (three seq-12 rules cite E30's `product_version_id`) and all three resolve to
    `CONTACT_REQUIRED` at pricing time (`pricing_adapter.py:122-126`, triggered whenever
    `pricing_key is None`) — concrete, not hypothetical, since all three DO have `pricing_key:
null`. **General form, because it is the reusable lesson: reading a metadata flag and
    concluding about runtime behaviour is not the same as finding the code that actually
    consumes it.** Does not change the E30-family LIVE STATE below (2026-08-20 entry) — the
    three products remain deliberately unpriced, now for the correct reason.

  - **NEW FINDING, 2026-08-23 (adversarial review of this entry's own "current record" framing,
    independently re-run twice — once by a separate verification lane, once by this session):
    the offline gold-persona replay has been failing at the SAME 4/20 with ZERO movement across
    at least two pack sequences, and the first version of this entry promoted itself to "current
    record" without disclosing that against a gate this same file names as an ENFORCE
    precondition.** Re-run this session, `--offline` against the currently-signed pack
    (`apps/backend-rag/backend/scripts/visa_engine/gold_replay_driver.py`): `matches=4/20`,
    `unexplained_divergences=16`, `explained_divergences=0`, `overall_pass: false`. Re-run again
    against an isolated copy of ONLY `rulepack-prod-011.signed.json` (seq-11, the immediately
    preceding pack): byte-identical — same `4/20`, same `16` unexplained, same divergent
    persona-id set `[1,2,5,6,7,8,9,10,11,13,14,15,16,17,19,20]`, and every persona's `actual`
    decision identical field-for-field. **Seq-12 introduced no regression — the gate has simply
    never passed across this window.** This is NOT comparable to `CURRENT_STATE.md`'s "5 fixture
    matches / 15 unexplained divergences" figure (line ~38) — that number comes from a `--live`
    bounded replay dated 2026-08-14 against the production endpoint stack, a different code path
    and a different, older pack; presenting 5/15 → 4/16 as movement would be comparing two
    different instruments, not two points on the same one. The ENFORCE-GATE section of this file
    requires "the current gold-persona replay has zero unexplained divergences" — the first
    version of this entry was incomplete, not wrong on the bytes it cited, in promoting itself to
    current record while omitting the current state of a named ENFORCE precondition.

    The divergence shape matters more than the count. Most of the 16 are the engine erring
    toward MORE caution than the fixture expects (e.g. personas 6/11/14/15: fixture expects
    `SUPPORTED_CANDIDATES`, engine returns `HUMAN_REVIEW_REQUIRED`/`NEEDS_INPUT` — conservative,
    not dangerous). Four are the opposite and more serious — the engine lands at full
    `SUPPORTED_CANDIDATES` where the fixture expects something stricter: persona 8
    (marriage-registration unverified, expected `NEEDS_INPUT`), persona 9 (investor direct
    onshore conversion, expected `NO_SUPPORTED_PATH`), persona 10 (same investor facts via
    status bridging, expected `HUMAN_REVIEW_REQUIRED`), persona 16 (investor capital 1 IDR below
    minimum, expected `NO_SUPPORTED_PATH`). Recurring review codes on the abstention side:
    `CITIZENSHIP_LIST_DIVERGENCE` ×2, `MINOR_GUARDIAN_PRIVACY_REVIEW` ×2,
    `E33G_INCOME_EVIDENCE_REVIEW` ×2.

    **The 4-vs-6 count, RESOLVED as definitional, not factual (2026-08-23, same-day
    reconciliation).** **4** is measured this session by running the driver under the narrow
    axis stated above — "lands at full `SUPPORTED_CANDIDATES` against a stricter expectation":
    personas 8, 9, 10, 16. **6** was relayed from a cross-family review and never independently
    re-measured at the time it was first written into this entry. Re-checked this session under
    the WIDER axis the cross-family review implied — any persona whose `actual` state is
    strictly MORE permissive than `expected` under the ranking `NO_SUPPORTED_PATH <
NEEDS_INPUT < HUMAN_REVIEW_REQUIRED < SUPPORTED_CANDIDATES` (i.e. treating a review
    triggered further into evaluation as more open than a request for more facts) — reproduces
    **exactly 6**: personas 1, 8, 9, 10, 16, 20 (persona 1: `NO_SUPPORTED_PATH` →
    `HUMAN_REVIEW_REQUIRED`; persona 20: `NEEDS_INPUT` → `HUMAN_REVIEW_REQUIRED`, both newly
    included under this axis). **Both numbers are correct under their own definition; the
    discrepancy is resolved, not open.** The qualitative point is unaffected by which axis is
    used: personas exist — at minimum 4, as many as 6 depending on definition — that land MORE
    permissive than the fixture expects, the same direction as the E31C nationality gap above.

    **Named pattern, not three separate incidents — this is the finding of the session.**
    Personas 9 and 16 above and the E31C nationality-leg correction earlier in this entry are the
    SAME disease: the engine grants SUPPORT where the fact that DEFINES the product is absent or
    contradicted, because `hit_policy.eligibility = "COVER_ALL_DECLARED_PURPOSES"` makes rule
    coverage OR-like — one broad SUPPORT rule dominates regardless of what its siblings decide,
    and nothing in the rule graph systematically checks that a product cannot be reached without
    its own defining constraint. This reframes the E31C fix from "patch one rule" to "audit the
    class" — a separate PENDING-ARMS row is opened for the gold gate below, distinct from the
    E31C row, because the audit this implies is broader than E31C alone.

- 2026-08-20 (M5, fourth entry — seq-11 SHIPPED end-to-end): **SEQ-11 IS LIVE IN PRODUCTION
  SHADOW — E30A/E30B now carry a resolvable `pricing_key`.** The executed half of Zero's
  E30-family pricing order ("E30 Education Visa ti ho detto +3jt sul PNBP", single
  all-inclusive price per ruling R1 2026-07-17): canonical prices landed in #4383
  (`bali_zero_official_prices_2026.json` +5 education entries, mouth copy regenerated via
  `sync_frontend_prices.py`), and seq-11 binds them into the pack. Chain of custody, every
  link verified: fold `fold_pack_seq11.py` (deterministic + idempotent, source sha256
  `32e548aa07021a9c…`, only delta vs seq-10 = `pricing_key` on E30A/E30B; PRICING-RESOLUTION
  gate resolves every key against the canonical price file before mutation) → PR #4393
  merged (`0d04da077`) with 16-test corpus (`test_seq11_pack.py`: chain gate recomputed from
  bytes, 26/12 pricing parity with positive controls, byte-invariance, E30/E30E/E30F
  honestly-unpriced pin) → signed on M5 kid `prod-2026-07-1`
  (`rule_pack_id 5c3974ab-bb15-5a73-b74f-f9f0af88a4a7`, payload_sha256
  `836acc511bcadd41c28284e7f00bd8be27c6109ebcc5536f7053c3f61eaa2865`, previous =
  `188442baee0af899…` = signed seq-10 payload, triple-derived) → bundle PR #4398 merged
  (`1c27a620e`) → two-login ceremony 10→11 (TAG 260820a): pre-state open activation seq-10
  `11a305cc…`, trust-store verify + anti-rollback pre-gate PASS, activation
  `6acb05c8-5d03-4bf6-b889-b81f318cd46c` by `fable-session-m5`, post-state seq-11 sole open
  activation (open_count=1), ephemeral roles dropped to zero. Live smoke 2/2 both citing
  `sequence=11 / version 2026.8.20`: full-facts family case → `SUPPORTED_CANDIDATES`
  (conclusive, same states as seq-10 — the pack delta is pricing-only); all-unknown →
  `HUMAN_REVIEW_REQUIRED` (fail-safe intact). The evaluate surface exposes no price fields
  (candidate keys checked live), so `pricing_key` consumption is proven by the merged 26/26
  resolution parity, not by an HTTP smoke. Two CI defects found and cured en route, both
  frozen-measurement class: Detect Secrets needed CONTENT_KEYED_RULES #11 (exact-value pin
  for the seq-10 chain anchor in the fold script), and `test_gold_replay_driver.py`'s
  `_OFFLINE_AT` was a frozen wall date (2026-08-19T12:00Z) that rejected every future signed
  pack — now derived as max(pack `signed_at`)+1h, structurally immune. Source freshness is
  INHERITED from seq-10's re-stamp (seq-11 does not touch `source_records`): the ~7-day
  portal window still expires ~2026-08-26 — the re-attestation cadence ledger row (owner
  Zero, `operator[business]`) is unchanged and now covers seq-11. Still open on the E30
  lane: E30/E30E/E30F remain deliberately unpriced (Ditjen pages read "Data Belum
  Tersedia" — needs Zero's number, ledger row stays open). ENFORCE unchanged: NO-GO
  (DPIA/analytics-TTL are Zero-only).

- 2026-08-19 (M5, third entry — seq-10 SHIPPED end-to-end): **SEQ-10 IS LIVE IN PRODUCTION
  SHADOW — and the stale-abstain era is over.** Zero's order "procedi con seq-10: re-stamp
  fonti + cura el.c2/el.e31c" executed in one session. Chain of custody: fold
  (`fold_pack_seq10.py`, deterministic+idempotent, source sha256 `1ff7383f…`) → 2-family
  adversarial refutation (Codex sol xhigh REJECT→cured; Kimi K3 MAJOR→cured; every finding
  re-verified, HF gained FAMILY+PARENT scoping, companion mouth change makes the interview
  ask `family_marriage_registered` for PARENT) → PR #4350 merged (`f99680a17`, 10:06Z;
  survived 2 runner blips + 1 ReDoS flake + 2 DIRTY ejections + a Detect-Secrets cure that
  became auto-triage CONTENT_KEYED_RULES #10) → signed on M5 (payload `188442baee0af899…`,
  kid `prod-2026-07-1`, signed_at 10:09Z) → bundle PR #4365 merged (`310eb17f1`, 11:36Z) →
  two-login activation 9→10 (activation `11a305cc-ade7-467f-a872-7c2b790c09c5`,
  `fable-session-m5`, open_count=1, ephemeral roles dropped) → LIVE SMOKE 5/5 on prod:
  IT full-facts → `SUPPORTED_CANDIDATES` **[B1, C1] with ZERO review reasons** (no
  `DECISIVE_SOURCE_STALE` — first conclusive portal-path verdict since ~08-13), NG →
  `CALLING_VISA_REVIEW` (mechanism armed), all-UNKNOWN → fail-closed, E31C guilt
  (marriage=false) → E31C ABSENT from candidates (exclusion surfaces as absence — the API
  has no excluded-list field), E31C innocence (marriage=true) → E31C rank 2 with
  `REQ_MIXED_MARRIAGE_PARENTS`. Content: 17 sources re-stamped (QW-5 verbatim-quote method,
  `inc4-pack-edits/freshness-restamp-2026-08-19.md`), `ee8fe5b8` dropped at zero refs,
  `el.c2.corporate-sponsor-type` RETIRED behavior-preserving (tightening REFUTED by the live
  C2 page → CF-17), `el.e31c-mixed-marriage-parents` tightened + new
  `hf.e31c-marriage-not-registered` grounded by CL-E31C-02/03. PENDING-ARMS 1008+1009
  closed; NEW rows: 7-day re-attestation cadence (owner Zero, Legge 5), E30-family pricing
  (PNBP+3jt owner rule), E30A re-sourcing, interview EDIT no-op. Freshness clock: the
  re-stamp buys until ~2026-08-26. ENFORCE untouched — still NO-GO (DPIA/analytics-TTL are
  Zero-only). Gate status: G-c evidence now accumulating on conclusive verdicts; G-a still
  needs the MATCH-lane arming + traffic.

- 2026-08-19 (M5, second entry — CP3 GO executed): **SEQ-9 IS LIVE IN PRODUCTION SHADOW.**
  Zero's GO on the CP3 package (incl. decision #4: ship with the el.c2/el.e31c residuals,
  cure in seq-10). Chain of custody, every link verified: PR #4332 merged (`952a6b4a388`,
  00:28:28Z) → merged pack bytes proven byte-identical to the CP3-approved candidate
  (sha256 `e3c1457952722706ec59b0a23e66c7d7a6a7b88735cda982b54957f5e4648660`) → signed on M5
  from a detached worktree at that commit after a fresh `compile_pack` RC 0 (kid
  `prod-2026-07-1`, self-verified; signed `payload_sha256
47feff8246c608c7c6085ffdac776fdc020bb56688d5f35a0a3e685eb40f271e` — the value seq-10 must
  chain to) → signed bundle PR #4338 (bundle-only, armed) → two-login activation on prod
  primary (`0801696b541568` via fly proxy from Pro; superuser pw fetched machine-side to a
  0600 file, deleted after; ephemeral roles `visa_pack_writer_ceremony_260819` /
  `visa_activation_ceremony_260819` minted stdin→psql and dropped same session).
  `activate_pack --yes`: anti-rollback pre-gate passed against seq-7
  (`3d068aef…9719f82`), pack row inserted, **activation_id
  `6655b8f9-3db8-42a4-82f0-34bd9ce625d5`**, actor `fable-session-m5`, reason
  `seq9-shadow-activation-260819`. Independent DB re-verification: exactly ONE open
  activation = seq-9 opened 2026-08-19T00:41:25.348033Z, seq-7 system_period closed the
  SAME instant, `no_gap = t`, zero ceremony roles left. Live smoke 4/4 HTTP 200, **every
  response citing `sequence=9 version=2026.8.19`**, audit rows bound to the new
  activation_id; all-UNKNOWN → HUMAN_REVIEW_REQUIRED (fail-closed ✓). SHADOW stays on;
  ENFORCE untouched (still NO-GO, DPIA/analytics-TTL Zero-only).
  **FINDING (pre-existing, NOT a seq-9 regression — measured, byte-compared):** the IT and
  NG smokes returned HRR with single reason `DECISIVE_SOURCE_STALE`: **18/29 pack sources
  are past their 7-day `MAX_AGE_SINCE_VERIFIED_AT` window today** (most `verified_at
2026-08-06`, the VOA country list `2026-08-08`) — stamps byte-identical in seq-7, so
  production has been stale-abstaining on every portal-source-decisive path since
  ~2026-08-13/15. The freshness guardrail is working as designed; what is missing is the
  OPERATIONAL CADENCE (re-verify portal sources + re-stamp `verified_at` in a new signed
  pack at least every 7 days), without which the SHADOW ledger abstains forever and
  G-a/G-c can never mature. Conclusive-path witnesses (IT full-facts → [B1,C1], NG →
  CALLING_VISA_REVIEW) are unreachable until that re-attestation lands — folded into the
  seq-10 scope (ledger row). Ceremony evidence: probe outputs + audit-row queries in the
  session scratchpad; smoke rows labelled `synthetic_driver` (G-a uncontaminated).

- 2026-08-19 (M5, E5 increment 3 — the seq-9 fold): **SEQ-9 CANDIDATE BUILT, GATED, AND ON ITS
  PR; CP3 PRESENTED TO ZERO. SHADOW/ENFORCE UNCHANGED (seq-7 stays active until CP4).**
  Everything in the 08-18 NEXT line except the ceremony itself: (1) the two seq-9 signing-gate
  blockers CURED BY RETIREMENT — `el.e33e.deposit-income-basis` proved REDUNDANT, not just UNSAT
  (CL-E33-04 VERIFIED says deposit AND income, already encoded by healthy `el.e33e.retirement`;
  the spec's OR assumption was refuted on claim evidence), and `el.e33g.income-60k-manual`
  retired in favor of the pre-existing `el.e33g.remote-work` + NEW `review.e33g.income-evidence`
  (OD-1 pattern: the USD 60k/yr requirement has no FactPath, so E33G can no longer reach
  SUPPORTED silently — a deliberate delta vs OD-3's 27-reachable count, E33G was reachable
  through the defect). (2) Rule-authoring for the 7 blocked products landed claim-cited through
  the E5 compiler (0 findings): E30E/E30F real SUPPORT (E30F sponsor-constrained to EDUCATION
  after a Codex P0 caught the missing conjunct live on the evaluator), E33A/B/C sponsor
  HARD_FILTERs (SUPPORT shape rejected — W3 factbase "manufactured offer" bug), E23U/E23V
  requested-product review rules (W3: no safe SUPPORT exists; NOTE: production-inert until the
  interview collects `intent.requested_product_code` — fact-mapper hard-codes NOT_ASKED; same
  property as the pre-existing e33 review rules; PENDING-ARMS row opened, Track C/E6 scope).
  (3) OD-2 fold executed: seq-8's 11 `pricing_key` folded, its broken chain permanently pinned
  by test; seq-9 chains to seq-7's RECOMPUTED signed payload hash
  (`3d068aef…9719f82`), `sequence 9`, `version 2026.8.19`, `rule_pack_id 66eb0b4c-…` (uuid5
  convention). (4) Freshness: E31E's two HARD_FILTERs re-sourced from dead `ecd22722` to
  primary law `c9e6f0e4` (Permenkumham 22/2023 Pasal 33(2)(h)(5), "belum berusia 18 … dan belum
  kawin" grounds BOTH predicates); `0497cb52` dropped (0 refs); `ee8fe5b8` CHANGED → de-referenced
  from all 18 citing rules (each keeps ≥2 sources). (5) The `_LEDGER_FILES` gap CLOSED:
  batch3+e2c ledgers wired into the compiler tests after fixing two real parser traps found by
  running the parser (dual-header CL-E31C-01/CL-E31F-01 swallowed both ids; CL-E33B-03's state
  bullet produced spurious product_states). Assembly is deterministic
  (`fold_pack.py`, 2 runs byte-identical, sha256 `e3c14579…4648660`, atomic write). VERIFY:
  2-family refuter quorum (Codex sol-high DO-NOT-SHIP → 7 findings → fix round; Kimi K3 3 P2/3
  P3 — BOTH drove the real evaluator; Kimi mutation-proved the first test suite content-blind →
  content-parity + 21 evaluator witness tests added; UNKNOWN semantics proven safe:
  `on_unknown=NEEDS_INPUT`, no D1/D2/D12-class masking, no exclude-on-UNKNOWN). Gates: 129
  targeted pytest + 25 vitest + compile_pack RC 0 + R1 green. **KNOWN RESIDUALS (CP3 decision
  #4):** `el.c2.corporate-sponsor-type` + `el.e31c-mixed-marriage-parents` are the SAME
  name-promises-untested-predicate class as the cured e33g, byte-inherited from seq-7, NOT cured
  (no compilable claim grounds a tightening — attempted, stopped; refuters split
  indefensible-vs-defensible), pinned in tests + ledger; recommended cure = seq-10 after an
  E31C/C2 doctrine batch. Reachability 27→29 / 9 blocked. CP3 package:
  `research/visa/doctrine-factory/e5/cp3-decision-package.md`; full delta:
  `research/visa/doctrine-factory/e5/2026-08-19-e5-increment3-fold.md`. NEXT on Zero's GO:
  sign (M5 kid `prod-2026-07-1`) → two-login activation → live smoke → then HRR/flag-veto
  reform (the 26 reformed slice rules deliberately NOT in this fold) and E6/E7.

- 2026-08-18 (M5, doctrine-factory E2/E3 close): **E2 CLOSED, E3 COMPLETE, OD-4 RULED.**
  E2 (OD-3 arrest criterion): MET — 27/27 REACHABLE products, per the closure verdict in
  #4278 (merged; #4264 is a closed-without-merge sibling, content blob-identical, no loss).
  The E2c mini-batch (#4294, merged) closed the 5 query-disposition BLOCKED products;
  two new conflicts surfaced there: CF-16 (C2 onshore conversion, OPEN, non-blocking) and
  CF-17 (E33A/B/C internal-DB identity — RESOLVED via hierarchy: primary law governs, the
  internal DB is superseded, the live pack is already correct). CF-7/8/10/12 RESOLVED via
  article-level pinpoints (E33E retirement age = 55; KITAP conversion = 3y under Pasal
  179(1) Permenkumham 22/2023). **CF-8 caveat: further refinement is in #4308 (OPEN,
  awaiting owner review, NOT yet merged)** — its finding: no 5-year ACCESS route exists;
  the internal "5" traces to superseded UU 6/2011 Pasal 60(1) and/or KITAP's own 5-year
  validity period (Pasal 121(1)), not an alternate eligibility pathway. E3: 38/38 Product
  Doctrine Cards on main (#4250+#4251 slice, #4279 visit, #4280 work/invest, #4282
  long-stay, #4300 E30 repoint follow-up — all merged). OD-4 RULED by Zero 2026-08-18: no
  product gets OUT_OF_COMMERCIAL_SCOPE; E28B/C/D/F keep always-REVIEW by design; E23U/V +
  E33A/B/C doctrine closed via the E2c ledger; E30E/F await rule-authoring only (E5
  backlog). Decision package: `research/visa/doctrine-factory/e3/od4-decision-package.md`
  (#4288, merged). ENGINE DEFECTS (seq-9 signing inputs, cross-verified against
  `origin/main` pack bytes): `el.e33e.deposit-income-basis` is UNSATISFIABLE (brute-force
  0/64 assignments) and `el.e33g.income-60k-manual` is VACUOUS (duplicated subtree, no
  income fact, "60000" absent from any pack) — both flagged by the E5 lint compiler,
  inc-1 #4283 + inc-2 #4291 (both merged, gate 77/77), and RECORDED AS SEQ-9
  SIGNING-GATE BLOCKERS: neither rule enters the fold uncured. Known gap:
  `_LEDGER_FILES` in the compiler is a hand-wired list — batch3/e2c ledgers have no CI
  reader yet (PENDING-ARMS row open, owner E5). OWNER items still open (business,
  outside repo, per OD-4): internal E33E guide still says 60 (must become 55); E28F
  internal-DB definition (CF-14); E33A/B/C internal-DB identity (CF-17); noindex ruling.
  NEXT: E5 rule-authoring (E30E/F + the 5 E2c products), cure the 2 defective rules, fold
  seq-8→seq-9 (OD-2), freshness 20/20 (replace `ecd22722`), CP3 (Zero) → signing ceremony
  (M5 key) → activation. Then HRR/flag-veto reform and the E6/E7 path to the ENFORCE gate.

- 2026-08-18 (M5, E5 perimeter — twin-partition: this session owns E5/compiler/backend
  `visa_engine`; nuzantara-df owns E3 bulk + OD-4): **E5 INCREMENTS 1+2 ARE ON MAIN.**
  Inc-1 PR #4283 (merge `93b9ae18f`): claim-ledger parser (`claim_ledger.py`, per-product
  state resolution for the mixed CL-D-FUNDS line) + compiler CLI
  (`backend/scripts/visa_engine/compile_claims.py`) with hard lints VERIFIED-only and
  R-OVERSTAY-PLANNING (Zero ruling 2026-08-18: any `immigration.overstay_days` reference
  must be gated by `immigration.currently_in_indonesia == true` in its ALL-ancestor
  chain), plus the 26 reformed claim-backed slice rules (D1/D2/D12/E31B/E31D) in
  `research/visa/doctrine-factory/e5/slice-rule-manifest.json`. Inc-2 PR #4291 (armed at
  green, gate passed 77/77 tests): lints UNSATISFIABLE-CONDITION and VACUOUS-RULE
  (duplicate-subtree + optional `must_reference_facts`), each proven on the real seq-7
  defects `el.e33e.deposit-income-basis` (brute-force UNSAT, 0/64 assignments) and
  `el.e33g.income-60k-manual` (duplicated block, zero income facts, `60000` absent from
  the pack) — both independently confirmed on `origin/main` pack bytes and RECORDED AS
  SEQ-9 SIGNING-GATE BLOCKERS: neither rule enters the fold uncured. OD-4 ratified (Zero
  via nuzantara-df session, package #4288): no OUT_OF_COMMERCIAL_SCOPE labels, E28B/C/D/F
  always-HUMAN_REVIEW rules stay as designed, E30E/E30F = pure rule-authoring (next E5
  increment), E23U/V+E33A/B/C await the E2c ledger. SHADOW/ENFORCE posture unchanged.

- 2026-08-15 (Pro continuation): **THE EXACT PR #4192 FRONTEND CANDIDATE IS
  PROMOTED TO THE PRODUCTION ALIAS.** Interactive Fable independently checked
  the Vercel identity, project, target, READY state, old alias owner and exact
  source commit, then ran one promotion at `2026-08-14T23:47:31Z`: deployment
  `dpl_GCXrsjrXwPjL9mrZdwDg9seFnLK7`, commit
  `32c8b26d2d632fc21af1d17fff74bcdc1a55fa49` (`#4192`). Independent Vercel API
  verification now resolves `mouth-nuzantara-2026.vercel.app` to that exact
  deployment with target `production` and state `READY`. A read-only
  `GET /visa` returned the expected Vercel deployment-protection redirect
  (`302`, no 5xx); no evaluation POST or backend traffic was generated. This
  promotion changes neither the backend queue nor RulePack state. SHADOW and
  the ENFORCE prohibition remain unchanged.

- 2026-08-15 (Pro continuation): **PR #4200 MERGED THROUGH THE LIVE MERGE QUEUE
  AT ITS EXACT REVIEWED SHA.** Exact head
  `4367d2c7aa2739011a7bedadb46d374424b6041a`, binary diff SHA-256
  `77019d5daa5c1915a253aa78f3aacbea1885f0964f212a809a9a53398fcd48e0`.
  The independent Fable 5 exact-SHA gate returned SHIP and left audit marker
  `visa-fable-exact-sha-gate:4367d2c7`. A separate Fable operator rechecked the
  immutable head, merge-base, diff digest and 66 clean check conclusions, then
  executed exactly one canonical `scripts/mq.sh arm 4200`. Independent GraphQL
  verification immediately afterward reported `isInMergeQueue=true`, state
  `AWAITING_CHECKS`, position 2, with the head unchanged. It advanced to
  position 1 at `2026-08-14T23:52:59Z`; all merge-group checks then completed
  successfully and the queue merged it at `2026-08-15T00:06:34Z` as exact
  merge-group commit `0fae2a64c5f495ead2a0f4f497c253f6f0cee2bd`. GraphQL
  now reports `state=MERGED` and no merge-queue entry. The mode-`0600` arm
  receipt records the reviewed head. Automatic backend deployment run
  `31852588636` completed successfully for that exact merge at
  `2026-08-15T00:16:26Z`, including every migration and post-deploy health job.
  Fly release 4126 runs image digest
  `sha256:d195c251d9ae9f8ae4f016c9029604d296455631b3bf05c19835366c06c388b6`;
  all four image records carry OCI label `GH_SHA=0fae2a64...`, the API machine
  health check is passing, and a separate read-only `GET /health/ready`
  returned `ready=true`. No evaluation POST was sent. This
  merge does not authorize any other
  PR merge, frontend promotion, RulePack signing/activation or ENFORCE change.
  SHADOW remains mandatory.

- 2026-08-15 (Pro continuation): **DEPENDENT DRAFT PR #4198 PASSED ITS EXACT-SHA
  FABLE 5 GATE.** Independent session
  `a4d7d067-5556-4f29-ae7d-83aa52088de9` verified the unchanged head
  `94ed6bd9204ef63080339d2a24ba5d8ea9de98a1`, merge-base
  `7e66a8b3d003de0327e1ff7669e038b467ee8a94`, binary diff SHA-256
  `bc3187b018bf265424ce9a2caae0e8cf4c2dfe515db5e3617c1a2b9a186a1fb6`,
  replay claims, official E31B/E31D sources, SHADOW/PII boundaries and all exact
  head CI, then returned SHIP. Pro independently rechecked the live head and
  clean check set and recorded audit marker
  `visa-fable-exact-sha-gate:94ed6bd9` in PR comment
  `#issuecomment-5299331193`. Fable operator session
  `1327f48a-b8b2-47a9-ba30-84d70a08aada` subsequently revalidated the unchanged
  head, gate marker, diff and terminal-green CI, marked the PR ready, and ran
  `scripts/mq.sh arm 4198` exactly once. The resulting mode-`0600` receipt
  records the exact head at `2026-08-15T00:21:27Z`, and GraphQL initially
  confirmed #4198 `QUEUED`/`AWAITING_CHECKS` at position 3 behind unrelated
  #4204 and #4202. At `2026-08-15T00:25:40Z`, their aggregate merge group failed
  `Immune enforcement`: the census identified #4202's new
  `scripts/ci/test_bot_provider_gate.py` as a `codex exec` caller without the
  required `codex_seat` resolver. GraphQL consequently marked #4202 and
  downstream #4198 `UNMERGEABLE`, while #4198 itself remained exact-head
  `MERGEABLE`/`CLEAN` with no bad checks. No queue mutation was attempted.
  GitHub subsequently removed the unrelated failing predecessor, advanced
  `main` to `ef8db35d...`, and rebuilt #4198 alone at `2026-08-15T00:29:21Z`
  as merge-group `2b0cae1866bc24d4b77c0b81840dca1f9b2da393`; GraphQL now reports it
  `AWAITING_CHECKS` at position 1. At `2026-08-15T00:46:22Z`, all 42/42
  merge-group checks were terminal-clean with zero bad conclusions; no re-arm
  or queue mutation was attempted. The queue merged the exact reviewed head at
  `2026-08-15T00:46:36Z` as squash/merge-group commit
  `2b0cae1866bc24d4b77c0b81840dca1f9b2da393` directly atop
  `ef8db35dbd4d5943354a5d3479f63080a4811f3d`. Independent GraphQL verification
  reports `state=MERGED`, `main` at that exact commit and no merge-queue entry;
  the PR still records reviewed head `94ed6bd9...`. No signing, activation,
  deploy or ENFORCE action occurred.

- 2026-08-15 (Pro continuation): **DEPENDENT PR #4199 PASSED ITS EXACT-SHA
  FABLE 5 GATE.** Independent session
  `e06d3c01-a41e-410e-90e0-a679638634bc` verified the unchanged head
  `903b01f8b5d2bb33141ddacaca9ac6aa6043efcc`, merge-base
  `f05a577a9f6d876b0914088b884e1406677ae4f8`, binary diff SHA-256
  `ae31cc045030dcb4b778f19bdf2904d80c394533d938e7586a05f5ed0606abd2`,
  both preserved artifact hashes, every substantive replay/disposition claim,
  the exact-path plus exact-content detector exception, PII/scope boundaries,
  R1 and live exact-head CI, then returned SHIP. Pro independently rechecked
  the live head and clean check set and recorded audit marker
  `visa-fable-exact-sha-gate:903b01f8` in PR comment
  `#issuecomment-5299393419`. The grader explicitly treated its M5 system-Python
  failures as missing local project dependencies/DB role rather than PR
  failures and relied on the green exact-head Backend Tests job. Fable queue
  operator session `d0837493-4bdb-403d-ad4e-0a56c4e31771` then independently
  revalidated the unchanged head, merge-base, binary diff, unique gate marker,
  clean worktree and all 58 exact-head check-runs plus successful combined
  status before marking the PR ready exactly once. The post-ready retrigger
  settled at 61 check-runs with zero pending/bad and combined status `success`.
  After a final immutable-identity check, the same operator invoked
  `scripts/mq.sh arm 4199` exactly once. Its mode-`0600` receipt records the
  exact head at `2026-08-15T00:52:49Z`; GraphQL independently confirmed
  `QUEUED` and then `AWAITING_CHECKS` at position 1 with the head unchanged.
  GitHub built merge-group commit
  `d56550a5d89a543d3f5e2de13d20b0fd5f6d57c7` directly after current `main`;
  at `2026-08-15T01:21:09Z` all 43/43 merge-group checks were terminal
  `success`, with combined commit status `success`. The queue merged the exact
  reviewed head at `2026-08-15T01:21:41Z` as that same commit, whose sole
  parent is the #4198 merge
  `2b0cae1866bc24d4b77c0b81840dca1f9b2da393`. Independent GraphQL
  verification reports `state=MERGED`, `main` at `d56550a5...` and no queue
  entry; the PR still records reviewed head `903b01f8...`. No signing,
  activation, deploy or ENFORCE action was taken.

- 2026-08-15 (Pro continuation): **DEPENDENT DRAFT PR #4201 PASSED ITS EXACT-SHA
  FABLE 5 GATE.** Independent session
  `59087feb-2b5f-4c49-b230-b63f39453fac` verified unchanged head
  `69c7493146ed23fc717b73a18fff652e05089204`, merge-base
  `35494716abcfdb4bf7e104382cc2fef81ff3b2d7`, binary diff SHA-256
  `d92a1f986a6d706d7fa6cac4ee95a9f2783895fc1bc4b251eef32c8e4b3fa53a`
  and all changed bytes. It independently reproduced the pinned replay report
  byte-for-byte at SHA-256
  `520d1205735edb0955aed337196fbcdcd21809c5b20690458a9c03bea7ee2d58`,
  confirmed the 5/20 match set and 15 unexplained divergences, source-expiry
  arithmetic, inclusive freshness boundary, policy-adapter parity, R1/PII
  posture and terminal-green exact-head CI, then returned SHIP. Pro rechecked
  the live head, clean diff and zero pending/bad checks before recording marker
  `visa-fable-exact-sha-gate:69c74931` in PR comment
  `#issuecomment-5299448049`. Independent queue-operator session
  `ea8bf063-9e6b-4dc8-b622-0b655bc25e63` then revalidated the unique marker,
  clean exact-head worktree, fresh merge-base and binary diff digest and invoked
  `gh pr ready 4201` exactly once at `2026-08-15T01:24:59Z`. Its post-ready
  suite settled 51/51 terminal-clean, after which Fable invoked the canonical
  queue arm exactly once. The mode-`0600` receipt records the exact reviewed
  head at `2026-08-15T01:25:52Z`; GraphQL first reported it `QUEUED` at
  position 1 from `2026-08-15T01:25:53Z`, then advanced it to
  `AWAITING_CHECKS` on speculative merge commit
  `d54999e3ab3d01d90828ffc231f0dd3c575edd7f`. All 43/43 merge-group checks
  settled terminal-clean with combined status `success`; the queue merged the
  exact reviewed head at `2026-08-15T01:43:30Z` as that commit, directly after
  #4199 merge `d56550a5d89a543d3f5e2de13d20b0fd5f6d57c7`. Independent REST,
  GraphQL and remote-ref verification agree on `state=MERGED`, no queue entry
  and `main` at `d54999e3...`. No signing, activation, deploy or ENFORCE action
  was taken.

- 2026-08-15 (Pro continuation): **PHASE B IS RECOMPOSED AS ONE LOCAL COMMIT
  DIRECTLY ATOP THE #4200 MERGE AND HAS PASSED ITS EXACT-SHA FABLE 5 GATE.** Branch
  `agent/nuzantara/backend-rag/visa-required-traffic-source-final`, head
  `b5d6da2e989d2943099236b8871734cb7b378d0d`, parent
  `0fae2a64c5f495ead2a0f4f497c253f6f0cee2bd`, binary diff SHA-256
  `c0724febc0d2cbfd3b1239a756cd2e54d979cde532b1d786fd45b154c5dfb8fe`.
  The 7-file candidate makes `traffic_source` required and fail-closed and is
  green after rebase under the focused endpoint suite, Ruff, mypy, mouth proxy
  Vitest, Prettier, TypeScript and the Visa OpenAPI contract validator. The
  missing-label 422 boundary remains mutation-proven. Independent Fable 5
  session `8bef8be3-9ced-4860-9b42-f9cfb2e7949b` reviewed every changed byte,
  rechecked the immutable head, merge-base and diff digest, reproduced focused
  backend 3/3, mouth 35/35, TypeScript and OpenAPI-validator passes, and proved
  that restoring the former implicit `real` default makes both boundary guards
  fail. Its final live read found 63 exact-head check-runs terminal-clean (57
  success, 6 path/config skips), zero pending/bad, and combined commit status
  `success`, then returned SHIP. Pro independently repeated the identity,
  digest and live-check read and recorded the unique audit marker
  `visa-fable-exact-sha-gate:b5d6da2e` in PR comment
  `#issuecomment-5299580365`. Independent queue-operator session
  `f7f9ba3f-105e-430c-88c3-ee124a5b24b0` revalidated every predecessor and
  immutable-target invariant, invoked `gh pr ready 4208` exactly once, waited
  for all 66 resulting exact-head checks to settle terminal-clean (59 success,
  6 skips, one neutral advisory; combined status `success`), revalidated again
  and invoked the canonical arm exactly once. The mode-`0600` receipt records
  the reviewed head at `2026-08-15T01:49:28Z`; GraphQL first reported it
  `QUEUED` at position 1 from `2026-08-15T01:49:29Z`, then advanced it to
  `AWAITING_CHECKS` on speculative merge commit `650716442c81298647eb07542e198565709de014`.
  All 42/42 merge-group checks settled terminal-clean (39 success, 3 skips)
  with combined status `success`; the queue merged the exact reviewed head at
  `2026-08-15T02:16:05Z` as that commit, directly after #4201 merge
  `d54999e3ab3d01d90828ffc231f0dd3c575edd7f`. Independent REST, GraphQL and
  remote-ref verification agree on `state=MERGED`, no queue entry and `main`
  at `65071644...`. Automatic deploy run `31858744114` completed `success` at
  `2026-08-15T02:25:55Z`; Fly release 4127 is complete at digest
  `sha256:6bef531ce86eef0f9bca6ea3934ed3a53bf65d7d6495d024ceba319328dee0c6`,
  all four image records carry exact `GH_SHA=65071644...`, and API health is
  passing. Exactly one missing-label evaluate POST then returned the sanitized
  `422` detail in live logs; the production handler additionally supplies its
  non-applicant correlation ID. A separate zero-POST readback proved required
  live OpenAPI, `ready=true`, read-only SQL and zero matching idempotency rows.
  The final aggregate is 20 `synthetic_gold`, 0 `real`, 0 legacy and remains
  RED/`enforce_ready=false`. Evidence:
  `research/visa/2026-08-15-traffic-source-fail-closed-live-proof.json` and
  `research/visa/2026-08-15-shadow-evidence-final.json`. No explicit-real
  smoke, RulePack, activation or ENFORCE action occurred. Any head change
  voids the historical gate identity.

- 2026-08-07 (Mini, Visa Oracle V2 completion): **REPOSITORY CANDIDATE G0–G6 PASS;
  PRODUCTION REMAINS NO-GO/SHADOW.** Exact independently reviewed delivery
  `e15fc1b84501cbdc2e023497b3e1af298f51034f`, baseline `cd343655c`, verdict
  0 BLOCKER / 0 MEDIUM. Migration 267 closes atomic complete-set legal-period
  correction; `activate_pack` now binds separation to real `session_user` and
  rejects the same-login/two-`SET ROLE` attack. Privacy Policy V1, exact
  PricingTool, retention scheduler artifacts, official Calling Visa archive,
  five-state UI and real backend authority are repository-ready. Mini/Pro were
  out of sync at handoff and the branch was behind later `main`; do not merge or
  ENFORCE before sync/rebase, impacted G5/G6, role/migration provisioning,
  analytics TTL proof, DPIA, production smoke and kill-switch drill. Full state:
  `.agents/skills/visaoracle/CURRENT_STATE.md`.

- 2026-08-08 (Mini, night 07→08, operational gates executed): **ONLINE IN
  SHADOW — every operational blocker from the prior entry now proven green
  in real production, except the 2 that stay Zero-only (DPIA, analytics TTL)
  and ENFORCE itself.** PR #3732 merged to `main` (`63234a12a`). D1 roles
  provisioned; P0 outage (D1 broke `FOR SHARE` in 3 migration-264 triggers)
  diagnosed and hand-cured same night, PR #3766 open to codify as migration
  268 (idempotent catch-up, not a new prod change). Privacy Policy V1
  registered; retention scheduler installed on Mini and later flipped
  `APPLY=true` (real deletions, confirmed healthy from 16:01:37Z). Cell
  sensor + Telegram P0-on-failure alerting both confirmed armed (a benign
  false page fired once during a DSN test bug, worth mentioning to Zero, not
  a real incident).

  Cameroon/Guinea Calling Visa fix activated as `rulepack-prod-003` (seq 3,
  version `2026.8.8`, `rule_pack_id 37be33e4-8fbb-55bc-8fe2-7dcb23eab979`,
  activation `783f5fcc-d7cd-4cc5-ba22-c6724d4a3bf1`, reason
  `g1-calling-visa-retroactive-fix`, 16:34:34Z). `rulepack-prod-002` (the
  first attempt, seq 2, `valid_period.from=2026-08-06`) was signed and
  inserted but the bitemporal guard refused activation twice — its
  legal_period did not fully cover `prod-001`'s still-open
  `[2026-07-25, ∞)`; its row is now permanently inert (append-only, sequence
  unique per env/jurisdiction/domain). Fix: re-signed identical content as
  seq 3 with `valid_period.from=2026-07-25` (retroactive — the official
  CM/GN removal sources predate the whole contested window). New
  `rule_pack_id` convention adopted (historical one not reconstructable from
  2 samples): `uuid5(NAMESPACE_URL,
"https://balizero.com/visa-oracle/rule-pack/<ENV>/<JURISDICTION>/<DOMAIN>/<sequence>")`.
  A mandatory pre-activation semantic diff caught one change outside the
  expected CM/GN/NE scope (`LIMITED_STAY.extension_policy.allowed
true→false`) — verified deliberate (G1 packet point 9, fail-closed
  `UNKNOWN` invariant), Zero-approved, not a defect.

  Live smoke 3/3 (16:37:16–16:37:37Z), all citing `sequence=3/version
2026.8.8`: Cameroon → normal document path, no more `CALLING_VISA_REVIEW`
  (the fix); **Nigeria → still `CALLING_VISA_REVIEW` only** (positive
  control, mechanism stays armed); Italy → unchanged baseline. Freshness gap
  closed: all 28 sources now `CURRENT` (19 portal @ 7d, 9 primary-law @
  365d) vs the previously-active pack's `freshness_policy=null` on every
  source. Independent post-activation DB re-verification (separate
  operator): 2 activation rows, seq 3 current, seq 1 closed with no gap.

  Kill-switch drill executed both directions and proven (not just
  rehearsed): `SHADOW→OFF` 16:10:50Z, verified `EVALUATE_SURFACE_DISABLED`
  by 16:12:28Z; `OFF→SHADOW` 16:12:43Z, verified restored by 16:13:44Z, all
  4 machines consistent — this doubles as the rollback proof. Engine
  confirmed live `VISA_ENGINE_EVALUATE_MODE=SHADOW`; ENFORCE was never
  requested or flipped, remains blocked on the DPIA/analytics-TTL items.
  Full evidence: `.agents/skills/visaoracle/CURRENT_STATE.md` §"Production
  operational verification"; memory
  `ops_visa_oracle_pack003_gates_proven_2026_08_08.md`.

- 2026-08-08 (Mini, second entry same day — 0%-conclusive-rate diagnosis): **ROOT
  CAUSE FOUND for the prod ledger's 6,610/6,610 `HUMAN_REVIEW_REQUIRED` (0%
  conclusive).** Not a fact-collection gap — a live SHADOW `evaluate` call
  (`mode:CURATED`, innocuous) with ALL 40 facts supplied (IT/TOURISM/10d/valid
  passport) still returned `HUMAN_REVIEW_REQUIRED`, citing 15 review reasons, all
  `hr.d1-*`/`hr.d2-*`/`hr.d12-*` (multiple-entry e-visa siblings), zero mention of B1.
  Mechanism: 31/63 `PRODUCTS`-scoped `HUMAN_REVIEW` rules in the active pack (seq 3,
  content = `rulepack-prod-002.source.json`) are keyed on `intent.purposes` alone
  (± `stay_days`) — always TRUE for the declared purpose, regardless of which
  product route the applicant actually wants (D1/D2/D12 don't even check
  `intent.entry_pattern`/purpose-specificity) — and `evaluator.py:1391-1397`'s
  documented precedence ("REVIEW beats SUPPORTED unconditionally", `enums.py:41-47`)
  lets ANY one reviewed sibling product mask a fully-eligible B1 candidate in the
  same purpose-set. Systemic, not TOURISM-specific — the 31-rule pattern spans
  EMPLOYMENT/STUDY/FAMILY/TOURISM/BUSINESS/INVESTMENT categories, explaining the
  ledger's near-100% abstention across all purposes, not just tourism. Full
  root-cause write-up + ordered fix list (RulePack seq-4: narrow D1/D2/D12 scope +
  add VOA-eligible-nationality gate to `el.b1.tourism`, currently absent) in
  `.agents/skills/visaoracle/HANDOFF-2026-08-08-voa-conclusive-rate.md`. Deploy
  pipeline note (unrelated to this diagnosis, found while checking state): PR #3766
  (migration 268, retention-binding `SECURITY DEFINER`) merged to main
  (`9d27f0f84`), but its post-merge Fly deploy **failed** — `must be owner of
function public.bind_visa_evaluate_idempotency_retention_policy` (least-privilege
  ownership gap on the release-command role) — no fix PR open yet as of this commit;
  does not block the RulePack-only fix above (pack changes go through
  `activate_pack.py`, not a schema migration). GATE STATUS (ENFORCE) unchanged: 🔴
  RED, DPIA/analytics-TTL still Zero-only.

- 2026-07-17: corner created. Round 1 research lanes in flight (Gemini/Codex/GLM/web). Worktree
  `mouth-visa-oracle` active. No PR — worktree-only until operator-analyzed final draft.
- 2026-07-17 (late night): ROUND 1 COMPLETE — 4 lanes delivered (Gemini survey / GLM design / Codex
  sol-ultra architecture+red-team / Sonnet web-verified) + repo scout map. Corpus persisted in
  research/visa/2026-07-17-visa-oracle-v2-round1-\*.md. Codex verdict: v1 NO-GO as legal engine (9
  P0s, 5 spot-verified on disk by orchestrator — see round1-verification-note). Panel canon: GOV.UK
  skeleton + behavioral interview (TurboTax) + living-tree design language + deterministic
  rules-as-data engine + visible-honesty moat. Chat demoted to escape-hatch explainer. Round 2 lanes
  fired: Gemini regulatory-delta (catalog staleness vs Kepmen M.IP-08/2025 index reclassification
  133→110 + Permen Imipas 10/2026), Codex engine-concretization, GLM interview design, Sonnet
  reuse-first OSS survey.
- 2026-07-17 (pre-dawn): ROUND 2 COMPLETE — 4 lanes delivered and persisted (gemini
  regulatory-delta: catalog has DEAD B211\* codes since Kepmen M.IP-08/2025 effective 2026-06-02,
  133→110 indexes, BVK now nationality-only per Permen Imipas 10/2026 [+6 states: TR/BR/PE/KZ/MO/BY],
  Permenkumham 36/2021 guarantor rules revoked by Permen Imipas 5/2025, regulatory-event cadence
  ~every 3-4 months; glm interview-design: framing card + Q0 date-driven onshore lanes + 10
  categories EN/ID + full behavioral trees Work/Invest/Remote + 5-state outcome skeletons + 10
  microcopy rules; codex engine-concretization: 110KB spec — visa_engine module layout, complete
  JSON Schema 2020-12 contract, RFC8785+Ed25519 signed anti-rollback bundles, tri-state evaluator
  with purpose-coverage hit policy, bitemporal SQL with append-only triggers, strangler plan with
  per-surface OFF/SHADOW/ENFORCE flags, 20 gold personas, file-by-file salvage map, 10 PR increments
  ≈41-56 eng-days; reuse-first: ZEN Engine MIT found [arbitration pending], xyflow+elkjs for
  /visualise, AGPL blockers identified, Stepperize license trap caught). Golden-visa stats conflict
  ARBITRATED by orchestrator: 1,274 visas / Rp52.1T VERIFIED-OFFICIAL (imigrasi.go.id siaran pers +
  Antara + CNN, as-of 2026-05-18; E28D Rp50.88T). Codex R2 spot-checks verified on disk: AppWizard
  onComplete is synchronous (packages/core/components/apps/AppWizard.tsx), api.ts hardcodes Fly
  fallback URL. Round 3 fired: Opus 4.8 xhigh fresh-context arbitration ZEN-vs-custom-evaluator.
- 2026-07-17 (dawn): ROUND 3 verdict — custom Python evaluator (Opus 4.8 xhigh arbiter, confidence 0.85;
  ZEN → authoring/visual only). RESEARCH PHASE CLOSED. Final draft composed:
  docs/plans/2026-07-17-visa-oracle-v2/00-product-design.md — awaiting owner analysis (mandate firebreak:
  worktree-only until analyzed). DeepSeek burn hunt still in flight.
- 2026-07-17 (dawn): OWNER RULING R1 applied to draft — single client-facing price, no PNBP/fee split
  (honesty = citations/assumptions/abstention, not price anatomy). Draft review ongoing, further rulings
  expected.
- 2026-07-17: R1 cross-family reviews done (codex×7, gemini×4; 2 REFUTED handled with recorded
  dispositions). Calling-visa corrected 8→7 (live-verified). Bridging ≥3-day interview-lane correction
  recorded.
- 2026-07-17: TRACK B claimed by Mini/2026-07-17 — content program active in worktree `research-visa-content` (lane research). FASE 1 in flight: Bridging Visa branch profile + D7A/D7B close-out + diaspora-index coverage check (per PR #2602 bonifica report Table 2). FASE 2 (7 interview categories) gated on PR #2602 merge.
- 2026-07-17: TRACK C claimed by Pro/2026-07-17 — experience track active in worktree `mouth-visa-experience-c1` (lane mouth; relocated from `mouth-visa-experience` after a twin-session filesystem race — twin's untracked work at `apps/mouth/src/app/(visa-oracle)/` left intact, candidate salvage for PR C2 once that session ends). PR C1: vo2 design tokens + mock interview model + `/visa-v2` prototype route (noindex, mock-only; engine wiring deferred until PR1 engine contracts land on main). C1 diff passed independent Codex GPT-5.6-sol review (6 P1 findings, all fixed in-PR).
- 2026-07-17: FASE 1 COMPLETE — `research/visa/2026-07-17-bridging-visa-branch-d7ab-diaspora-closeout.md` closes all 3 open Table-2 items: D7A/D7B/D8A/D8B RESOLVED-EXIST (per-code body-content discriminator, 2 dead-code negative controls), Bridging Visa fact-base primary-grounded (Permenkumham 11/2024 + Permen Imipas 3/2025 Pasal 45 partial-revocation resolved), diaspora COVERED (product-level, Kepmen-gated). Real cross-family adversarial review: Codex (gpt-5.6 refused locally, ran codex-mini-latest), 3 passes — 2 REFUTED-and-fixed, final pass REFUTED only on 2 wording nits, ALL load-bearing claims explicitly not refuted. PR #2607 open, auto-merge armed (SQUASH), all 40 CI checks green except "Backend Tests (Python)" still running (docs-only diff, no code touched). FASE 2 (7 interview categories) STAYS GATED: PR #2602 (bonifica, branch `agent/air-m5/mouth/visa-catalog-bonifica`) is still OPEN and now shows `mergeable: CONFLICTING` / `mergeStateStatus: DIRTY` — out of this track's scope to resolve (different lane/owner), flagging as external blocker.
- 2026-07-17 (night): PR #2617 E2E red diagnosed (Pro): CI-only — Next 16 dev blocks cross-origin dev resources for 127.0.0.1 baseURL, React never hydrates; visa-oracle-v2.spec.ts is the only CI e2e exercising hydration (latent repo-wide CI blind spot). Fix: allowedDevOrigins in apps/mouth/next.config.ts, verified locally (5/5 on 127.0.0.1). Pushed to the same branch; automerge already armed.
- 2026-07-18: TRACK C increment C3 shipped (Pro, worktree `mouth-visa-experience`, branch `agent/nuzantara/mouth/visa-experience-c3`) — verdict tree→card morph (View Transitions API + FLIP-style shared `view-transition-name`, feature-detected, spring-reveal fallback, reduced-motion instant swap), tree tap-to-edit (completed trunk steps are real buttons dispatching the existing EDIT action, guarded by new `isEditableTreeStep`), a real scannable QR (`qrcode` npm, reuse-first from `apps/wa-mirror`, synchronous SSR-safe SVG render — no canvas/network) beside the still-visible wa.me link, and a checkable + printable document checklist (real checkboxes, `window.print()` + dedicated `@media print` stylesheet, copy-summary with visible confirmation). Mock-only, single all-inclusive price untouched, EN/ID both updated. 58 unit + 9 e2e passing.
- 2026-07-18: TRACK C SHIPPED — PR #2617 (C2, consolidated living-tree experience) merged 00:21 WITA and proven live: `https://www.balizero.com/visa-oracle` (200, noindex meta present) is now the single Track C foundation; `/visa-v2` 308-redirects there and C1 artifacts were removed in the consolidation. Experience is mock-only (5-state RecommendState, 12-card catalog, EN/ID, WCAG AA); real engine wiring stays gated on PR1 engine contracts landing on main. Worktree `mouth-visa-experience` intentionally kept alive for the sibling session's post-merge follow-up (widening CI e2e coverage back to the 4 interactive tests).
- 2026-07-18: PR #2602 (bonifica) MERGED 2026-07-17T15:51Z — FASE 2 gate OPEN. PR #2607 had gone DIRTY after the night's LIVE-STATE merges (#2602/#2606/#2627/#2628 touch the same skill files); resolved the legal way (merge of origin/main into the branch, LIVE STATE lines reconciled, no force-push), automerge still armed.
- 2026-07-18 (S3 engine lane): TWIN-PR COLLISION ADJUDICATED by Zero (Legge 5): **ADOPT_A** — PR #2654 (M5 tree "A") MERGED to main (f73cbb4a); S3's PR #2718 (tree "B") CLOSED, its branch `agent/nuzantara/mouth/visa-engine-pr1-0718` intentionally KEPT as the PR3 seed (strong-Kleene evaluator + truth-table tests). Binding order from Zero: (1) correctness HOTFIX first — Codex gaps confirmed live in A, fix+guilt+innocence same commit; (2) PR1b port-list from B (only proven incremental value); (3) PR2 signed-bundle re-adapted to A's API with REDONE 3-seat verify; (4) PR3 from seed. Comparative A-vs-B report: `research/visa/2026-07-18-visa-oracle-v2-pr1-a-vs-b-portlist.md`. Hotfix branch `agent/nuzantara/mouth/visa-engine-hotfix-0718` in flight: 4 live gaps (canonical-date-literal P0, ordering-ops-on-enum-strings P1, GLOBAL+explicit-null P1, country-code-format P1).
- 2026-07-18 (S3, STEP 1 SHIPPED): hotfix **PR #2739 MERGED** to main 12:44Z (`8ac3184ce`) — 4 gaps fixed TDD-style (date literals P0 / ordering fail-closed P1 / country-code shape P1 / KnownDate calendar P0, the last found by the GLM refutation pass); **Gap C (Codex #8 GLOBAL+explicit-null) REFUTED at implementation** — deliberate round-4/5 schema design, evidence re-verified on disk, recorded in the report's §Post-implementation correction. Suite 235→258. 4-stage generator≠grader chain held (Sonnet implementer → GLM report pass → Codex sol-xhigh diff SHIP → Fable final gate). STEP 2 (PR1b) in flight on branch `agent/nuzantara/mouth/visa-engine-pr1b-0718`: 7/8 port-list items done (item 1 product_code dedup SKIPPED with evidence — bitemporal multi-version per product_code is the evaluator's intended §4.3 pattern; the B port would have broken it), suite 258→293, GLM diff review pending.
- 2026-07-18 (S3, STEP 2 + STEP 3): **STEP 2 SHIPPED** — PR1b **#2745 MERGED** to main (`8ac3184ce`→squash) 14:17Z: 9 hardening commits (F6 quote↔candidate, StrictBool×5, alias-only wire, registry (kind,value_format) consistency, +2 GLM-prescribed P2: `_DATETIME_SHAPE` ASCII, duplicate-candidate-id guard); item-1 product_code dedup SKIPPED, skip **independently confirmed** by GLM (SKIP-RATIONALE CONFIRMED) — follow-up for PR3: enforce uniqueness of the effective+ACTIVE slice per product_code. Suite 258→300. **STEP 3 (PR2 signed bundle) in flight** on branch `agent/nuzantara/mouth/visa-engine-pr2b-clean-0718` (the `-pr2b-0718` branch was W88-rebased onto fresh main to drop the now-squashed PR1b commits): `bundle.py` re-adapted to A's API, **fresh 3-seat verify** (GLM SHIP / Codex FIX-FIRST(1,4,5,6) / Gemini FIX-FIRST) → 11 FIX-NOW hardening applied (TOCTOU, env-bound keys, future-skew on signed_at, unsigned-into-PROD refusal, …), **3 findings REFUTED on the real model** (Codex bootstrap-sequence — model already enforces it; Gemini env-defaults-to-PROD and hex-uppercase — both blocked upstream). FIREBREAK intact (no key ceremony, unsigned fail-closed behind flag, never PROD). Suite 300→385. rfc8785+rfc3339-validator declared, lock honors manifest (W98). Round-4 regulatory recheck persisted on the closed B branch (M.IP-08/2025 effective 2025-06-02 per dictum KELIMA; BVK Permenimipas 10/2026 adds Macau — 19-state official list; number-collision trap with Permenkumham 10/2026 Second Home) — to be re-landed with a later PR.
- 2026-07-19: TRACK A key ceremony DONE — 2 kids minted (`2026-07-test-1`/TEST, `2026-07-prod-1`/PRODUCTION); private-key custody M5 `~/.config/nuzantara/visa-signing/` (0600/0700, not in Keychain, not on Pro/Mini); Fly secret `VISA_ENGINE_TRUST_STORE_KEYS_JSON` staged on `nuzantara-rag` (digest `a68f076bc9993f0c`) — inert until SHADOW wiring. Runbook: `docs/runbooks/visa-engine-key-ceremony.md`. Engine chain complete on main: PR1 #2654, PR1b #2745 (+residual #2795), PR2b #2757, PR3 #2773. Next: RulePack legal authoring + SHADOW wiring.
- 2026-07-19: TRACK A **AUTHORING claimed by M5** — RulePack authoring+signing pipeline is bound to M5 by key custody (private Ed25519 keys exist only on M5); next increment: offline authoring/signing tool + first signed TEST pack from the bonified catalog. S3/other lanes: coordinate here before touching authoring.
- 2026-07-18: TRACK A PR1 foundations pushed (M5) — merge commits against origin/main resolved by regenerating docs_sync markers (README/AI_ONBOARDING quick-numbers) rather than picking a side; PR #2654 open, automerge armed.
- 2026-07-18: TRACK A PR1 MERGED — dual-PR1 collision (M5 #2654 vs sibling S3 #2718, same
  visa_engine foundations scope) adjudicated ADOPT_A via independent cross-family comparative
  review (Codex sol xhigh; verdict with file:line evidence posted on #2718, now closed as
  superseded). #2654 merged to main, merge commit f73cbb4a7b. Branch
  `agent/nuzantara/mouth/visa-engine-pr1-0718` (the S3 tree) intentionally preserved, not deleted —
  its strong-Kleene evaluator + truth-table tests are the PR3 seed.
- 2026-07-18: TRACK A next — PR1b port-list BEFORE PR2: (1) canonical YYYY-MM-DD literal
  validation, (2) semantic STAGE_ORDER (WARNING: the two trees disagree on ELIGIBILITY vs
  HUMAN_REVIEW precedence — arbitrate against
  research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-concretization.md before porting),
  (3) StrictBool on wire-level booleans, (4) common residual: JSON Schema `integer` accepts 2.0
  while StrictInt rejects (schema-valid/model-invalid gap). Then PR2 signing (Ed25519, RFC8785,
  anti-rollback). CodeQL note: iterate enums via `list(Enum)` in tests —
  py/non-iterable-in-for-loop is a required-check failure class (S3 cured it on their tree in
  commit 1a4360dc1b; A-tree tests should adopt the same pattern in PR1b).

- 2026-07-19: **TRACK A PR1b ARBITRATION RESOLVED + STAGE_ORDER CORRECTED.** The 2026-07-18 line
  126-134 WARNING above ("the two trees disagree on ELIGIBILITY vs HUMAN_REVIEW precedence —
  arbitrate against the round-2 spec") was itself resolved WRONG the first time: the M5 lane's PR1b
  attempt (worktree `backend-rag-visa-engine-pr1b`) arbitrated to the enum-DECLARATION order
  (HARD_FILTER→ELIGIBILITY→HUMAN_REVIEW→RANKING, matching enums.py's literal source order + the
  spec's JSON Schema enum listing) — flagged **P0 by tri-LLM review on its own PR #2781** and
  independently re-verified by re-reading the spec's §4.2 `evaluate_product` ALGORITHM pseudocode
  directly: the correct order is **HARD_FILTER→HUMAN_REVIEW→ELIGIBILITY→RANKING**, exactly what
  sibling PR #2773 already shipped (commit message: "the prior docstring's 'evaluated in this strict
  order' claim was wrong"). Declaration order ≠ processing order — do not re-litigate this without
  re-reading §4.2 fresh. Meanwhile a sibling S3 lane had independently re-shipped the whole PR1b
  port-list as **PR #2745 MERGED 2026-07-18T14:17:49Z** (after hotfix #2739, before PR2b #2757 and
  PR3 #2773 — all 4 verified MERGED via `gh pr view` against `Balizero1987/Teman2`), making the M5
  lane's #2781 a twin-race casualty: **CLOSED 2026-07-19T02:33:58Z**, no merge attempted, full
  investigative writeup on the PR. Items 1 (canonical date literals) and 3 (StrictBool) were also
  redundant against #2745's more mature equivalents. Only 2 of the original 5 port-list items were
  genuinely still unclaimed after a fresh `origin/main` content grep (no merged commit, no open
  PR/branch): CodeQL `list(Enum)` pattern (7 sites) and the JSON-Schema-vs-StrictInt integer-parity
  documentation+pin (line 130-131's "common residual" above) — both shipped via branch
  `agent/air-m5/backend-rag/visa-engine-pr1b-residual` (commit `fc24dc7913`, 492/492 suite green,
  ruff clean, docs_sync clean).
- 2026-07-19: **LEDGER GAP FLAGGED (not backfilled here — respecting "whoever changes state updates
  this file")**: lines 116-118 above narrate Track A only through "STEP 3 (PR2 signed bundle) in
  flight" — PR2b (#2757, merged 2026-07-18T17:45:52Z) and PR3 (#2773, strong-Kleene evaluator +
  2-seat fixes, merged 2026-07-18T19:34:19Z) both already landed on main since then but have no
  LIVE STATE entry recording it. Track A's own next-lane session should backfill STEP 4/5 entries.
  **Verified standing blocker**: Ed25519 key ceremony remains explicitly operator-side and undone —
  `bundle.py:269`'s own comment ("the key ceremony (generating...") plus the STEP-2/3 entry's
  "FIREBREAK intact (no key ceremony, unsigned fail-closed behind flag, never PROD)" both confirm
  signing code ships unarmed pending real production keys. With PR1→PR3 all merged, "Track A next"
  is genuinely PR4-6 (undefined in this file) gated behind that ceremony — NOT "PR3 evaluator", which
  is done.
- 2026-07-19: GOLD HARNESS (G-b) shipped by M5 (`backend/tests/services/visa_engine/gold_harness/`)
  — 20 self-authored personas + hand-designed rule pack + a Decision-agnostic thin adapter (built
  because PR5 was OPEN, not merged, at task launch) + 3 real metamorphic property tests
  (monotonicity, fact-order invariance, rule-order invariance, fixed seeded shuffles) + a
  replay-report JSON evidence-artifact CLI.
- 2026-07-20 (CORRECTION, discovered on merge — read this before citing G-b evidence): **PR5
  merged overnight** (`c26211da2e`, #2841, "Decision evaluator — pure tri-state orchestrator") and
  it ships its OWN canonical 20-gold-persona acceptance suite (spec §7's literal persona table,
  `backend/tests/services/visa_engine/test_evaluator_gold.py` + `_gold_fixtures.py`) run directly
  against the REAL `evaluator.evaluate()` — that suite, not M5's harness, is the stronger/primary
  G-b evidence (real engine, not a stand-in adapter). M5's harness predates the merge and uses its
  own non-canonical persona set + rule pack against its own adapter, so it should be read as
  COMPLEMENTARY evidence, not the G-b primary satisfier: it adds two things PR5's suite does not
  have — per-product proof-state assertions (PR5 asserts global `DecisionState` only) and genuine
  input-order metamorphic invariance (PR5's `test_evaluator_determinism.py` proves repeat-call
  purity, not fact-dict-order/rule-declaration-order invariance). Follow-up owed: port the
  fact-order/rule-order metamorphic properties onto the real `evaluator.evaluate()` directly (the
  highest-value reconciliation) and settle G-b's canonical evidence pointer — likely PR5's suite
  plus a ported property-test file, with M5's `gold_harness/` package retired or kept only as
  design reference. Do not cite M5's harness alone as "G-b satisfied."
- 2026-07-20 (M5, overnight coordinator sweep): ceremony runbook **#2861 MERGED** (`1f16223335`),
  gold-harness package **#2876 MERGED** (`1606f7af25`); RulePack authoring pipeline
  (`compile_pack.py` + offline `sign_pack.py` + first signed TEST fixture) **PR #2869 in flight**
  (mergeable, CI running, 2 Codex adversarial rounds cured, round-3 confirm died on network —
  shipped under authorized fallback with a transparent PR-body note). Both PRs fought the same
  DOCSYNC conflict (`docs/DOCS_INVENTORY.md`) four times overnight as main advanced ~15 commits —
  cured each time by regenerating via `scripts/docs_inventory_regen.sh`, never side-picking. A
  **Kimi session** was independently reconciling the same two PR branches in parallel from
  `/tmp/wt-2876-gold` — its commits carry the SAME git author identity as this machine's session
  (Kimi inherits the global `git config user.name/email`, has no committer identity of its own),
  which caused two pushes to be rejected as "behind" before the pattern was recognized; resolved
  by fetch+legal-merge each time, never force-push, no work lost on either side. Detail:
  memory `discovery_kimi_parallel_worktree_pr2876_2026_07_20`. SHADOW-wiring prerequisite for the
  ENFORCE-GATE (STEP-6c) still not live — S3/Pro's PR #2824 (migration 252 SHADOW substrate)
  remains the actual blocker for evaluating any gate criterion, G-b included.
- 2026-07-21 (Pro, SHADOW evidence lane): prior blocker superseded — **#2916 MERGED**
  (`8b28ac418481`, STEP-6c Match wiring), **#2930 MERGED** (`09f7cd2273c9`, real HMAC
  facts-fingerprint provider), and **#2952 MERGED** (`60c6f348c9a4`, finite activation-system-period
  guard). Production release 3888 is deployed, but collection remains dark: Fly has only the Visa trust
  store, while Match mode and the facts-fingerprint key are absent. Read-only DB proof is separately
  blocked because the `nuzantara_readonly` Keychain password is absent; no write-capable fallback used.
  Worktree `backend-rag-visa-oracle-shadow-evidence` now prepares migration 255 plus a PII-free,
  fail-closed G-a/G-c collector and CLI; 1,070 Visa-engine tests collected with all runnable tests green
  (one pre-existing executor-role skip). **No PR, merge, deploy, secret change, SHADOW activation, or
  ENFORCE activation performed.** Receipt:
  `research/visa/2026-07-21-shadow-evidence-collection.md`.
- 2026-07-22 (Pro, SHADOW evidence lane): Kimi review follow-up adds direct G-c,
  collector, CLI, and legacy fail-closed coverage; `duplicate_evaluations` now counts only
  repeated valid 32-byte fingerprints. The focused local-test-DB suite is green (57 tests;
  SHADOW evidence module 85.30% branch coverage). **L3/L4 remain deferred; ENFORCE remains OFF.**
- 2026-07-23 (M5, Kimi architect session): full state-analysis + 4-seat adversarial panel
  (gemini/codex/design-house/web-grounded — GLM seat degraded, Keychain token absent via SSH)
  synthesized into the definitive correction+completion plan:
  `research/visa/2026-07-23-architect-review-synthesis.md` (analysis + 4 lane files alongside).
  Verified discoveries: (1) **v1 funnel dead since 2026-04-25** — the auth floor (PR #108)
  never registered `/api/visa/*` in `public_endpoints.py`; POST 401s through the catch-all
  proxy; 28 `visa_checks` rows total, all ≤2026-04-21; sibling endpoints clock/match-hash
  equally dead. (2) **SHADOW-on-v1 feeds only 3/35 FactPaths** — weak gate evidence; plan
  moves SHADOW to a new full-fact evaluate read-path API (gate-blocking, Track A). (3) Gate
  "7 categories" matches no vocabulary (255 enum=8 incl. `other`; v2 interview=10; business/
  diaspora uninstrumented). (4) Kepmen M.IP-08.GR.01.01/2025 **effective 2025-06-01** (dictum
  KELIMA, primary source; B211\* death = dictum KEEMPAT); "Permenkumham 10/2026 Second Home"
  REFUTED (notary PMPJ — the parked round-4 recheck note must be corrected before re-landing);
  BVK = 19 states/SARs + 1 entity (Permen Imipas 10/2026, effective 2026-07-09). Plan forks on
  **owner decisions D1 (G-a semantics/threshold vs ~7/day organic traffic) / D2 (110-code pack
  for ENFORCE) / D3 (adopt 9 E-gates)**. GATE STATUS unchanged: 🔴 RED.
- 2026-07-23: correction+completion plan lands as PR (research/docs-only, no automerge);
  next executable items: P0-1 registry fix `/api/visa/*` + telemetry, P0-3 read-path API,
  P0-4 RulePack first slice (E28/E33/BVK/Bridging mandated), P1-1 G-b independent replay.
- 2026-07-23 (late): **FABLE 5 FINAL GATE on the plan** (seat `zero@balizero.com`, requested
  by Zero) — verdict **FIX-FIRST**: plan adopted with **7 deltas** (full report
  `research/visa/2026-07-23-architect-review-fable5.md`, addendum in the synthesis). Headline
  blind spot: under D1(c) as written **G-a and G-b collapse into the same test** (facts
  collectible for only 3/10 interview categories + no synthetic marker → breadth could only
  come from the same corpus G-b replays). Deltas adopted: migration 256 `is_synthetic`/
  `traffic_source` column; G-a split into `G-a-vol` (real, owner-set) + `G-a-breadth`
  (corpus, labeled); P0-3 must emit `request_category` + 10-tile→8-enum mapping + explicit
  business/diaspora ruling; DAG names the window's traffic source; D2 coupled with Track B
  FASE 2 (110 codes AND behavioral trees per launched category); NEEDS_INPUT disclaimer fix
  (`OutcomeSheet.tsx:455`, Law-2-adjacent) promoted into the P0-1 batch; DB/Fly facts marked
  receipt-owed for the D1 threshold decision. Fable D-recs: D1(c) split as above / D2 adopt
  with FASE-2 coupling / D3 adopt with tiers (E-a/E-e/E-g blocking; E-b/E-f fast-follow).
  Conflict adjudicated: Gemini's deadlock claim WRONG (evaluate endpoint ≠ UI launch),
  Codex/design/orchestrator RIGHT. GATE STATUS unchanged: 🔴 RED.
- 2026-07-24 (M5, Kimi orchestrator): **WAVE 0 + W1a LANDED on main.** Merged: #3032
  (`8875b95ad35b`, `/api/visa/*` public — **v1 funnel resurrected**, live smoke 201 + row 29
  in `visa_checks` after 3 months dead), #3033 (`0185dc5c9c24`, disclaimer all-5-states +
  PII-free `app_form_submit_failed`), #3038 (`6e88b24b6773`, next-steps gated on
  SUPPORTED_CANDIDATES — Fable MEDIUM, owner call "fai tu"), #3046 (`7f99e570147d`,
  migration 256 `traffic_source` + collector G-a-vol/G-a-breadth split). All Fable-gated
  SHIP, all merged by the **delegated Opus verifier** (new pattern per Zero: "io non faccio
  review, chiedi a opus" — build=agents, gate=Fable, merge=Opus seat `claude-zero-team`;
  note the seat caps ~4:20 WITA reset and acct2/3/4 are NOT logged in). **Codex CLI auth
  DEAD on M5** (401, operator re-login needed — graders fall back to Opus per Zero).
  **W1b in flight** (evaluate read-path API, agent lane `visa-evaluate-endpoint`).
  #3034 (G-b) still open on the docsync treadmill (3rd regen pushed; content SHIP-verified
  twice). #3028 (this corpus) R1-green but blocked by a **main-side npm-audit failure**
  (find-my-way/hono/prisma, 3 high — infra-lane fix needed on main, not the visa lane).
  R1-gate lesson recorded: `adversarial_review:` accepts only gate seats
  (agy/codex/gemini/glm/gpt-5.5/grok/kimi*/nlm) + `human-*`/`exempt-\*`, and every research
  file needs a `## Adversarial review` body section with surviving-objection dispositions.
  GATE STATUS unchanged: 🔴 RED.
- 2026-07-24 (M5, Kimi orchestrator, evening): **WAVE 1 100% on main + W2 KICKED OFF** (Zero:
  "parti ora"). Wave 0+1 all merged: #3032 (funnel resurrected, live-smoked 201), #3033,
  #3038, #3046 (mig 256), #3028 (corpus), #3060 (mig 257, owner-merged), #3061 (**evaluate
  read-path API live on Fly** — prod smoke: strict no-echo validation, fail-closed
  TEMP/`CURATED`, 0 rows), #3034 (G-b metamorphic+replay), #3079 (runbook+reports). Gemini
  adversarial pass on W1b caught 5 real findings (chunked-OOM, rollback rows, synthetic
  abuse, param echo, blind hint) — all cured and Opus-verified SOLID pre-merge; Opus is the
  delegated merger (Zero: "io non faccio review"); codex CLI still dead; Opus seat caps
  ~4-5h cadence; prettier-3.8.4-vs-main skew and docsync/inventory date-drift are the two
  recurring repo-wide friction points (both flagged for infra). **W2 RulePack factory
  started**: 4 research lanes in flight (E28+ BVK via Gemini/agy; E33 + Bridging via house
  seats) producing per-code fact-bases (`research/visa/2026-07-24-w2-factbase-*.md`) for the
  30-priority-code pack; signing stays M5 (Track A), FASE 2 trees stay Mini (Track B).
  Next: rule authoring → sign → activate → arm SHADOW per
  `research/visa/2026-07-24-shadow-arming-runbook.md`. GATE STATUS unchanged: 🔴 RED.
- 2026-07-25 (M5, Kimi orchestrator, ~04:00 WITA): **W2 FIRST PACK SIGNED + ON MAIN.**
  `#3092` (`c33c183ad8ea`, 12 fact-bases corpus) and `#3090` (`3c412c96b085`, first signed
  PRODUCTION RulePack: **38 products / 110 rules / 28 sources**, `compile_pack` zero errors,
  kid `prod-2026-07-1`, `payload_sha256 47a97c32…`, Fable gate SHIP with adversarial
  counter-probe) both merged. Chain: 8 fact-bases (live primary sources 2026-07-24, 2
  Gemini grade rounds with dispositions) → 2 authoring agents (A1 18p/47r, A2 20p/63r, zero
  overlap) → assemble → compile → sign → verify. **Kid-pattern bug found+fixed at first
  signing** (ceremony kids start with a digit, fail the engine's `IDENTIFIER_PATTERN`;
  relabeled `test-2026-07-1`/`prod-2026-07-1` same key material; Fly trust store re-staged
  digest `ab319439ecf92a0f`; errata in `docs/runbooks/visa-engine-key-ceremony.md`).
  **Detect-secrets cure**: pack hashes audited in baseline + naming-scoped triage rule
  (`contracts/packs/rulepack-*.json`). **Next: activation addendum
  (`research/visa/2026-07-25-activation-addendum.md`)** — provision `visa_activation_executor`
  (one-time, operator), build the small `activate_pack.py` ops tool, activate, then the 3
  SHADOW secrets + smoke per the arming runbook. GATE STATUS unchanged: 🔴 RED.
- 2026-07-25 (M5, Kimi orchestrator, ~12:30 WITA): **SHADOW IS LIVE IN PRODUCTION — first
  real evidence row.** The full activation arc is done: `activate_pack.py` ops CLI built
  (PR #3101, 8/8 tests, dry-run verified); fingerprint HMAC key store minted (kid
  `fp-2026-07-1`, M5 custody) + 3 secrets set on Fly (`VISA_ENGINE_EVALUATE_MODE=SHADOW`,
  `VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON`, `VISA_ENGINE_DRIVER_TOKEN`); roles provisioned
  on prod PG (`visa_activation_executor` NOLOGIN + grants on `nuzantara_rag`, ops role
  `visa_activation_operator` LOGIN granted executor — Fly PG is 2-machine HA, primary
  `5683e090f3d228`, `OPERATOR_PASSWORD` from keeper environ; `fly pg connect` hangs on
  wireguard — use `fly ssh console -C` + `fly ssh sftp put` with `--machine` pinning, sftp
  never overwrites); **pack ACTIVATED** (`activation_id bb35cb81-276d-4a6e-8570-e46a2c692777`,
  actor token `operator.zero-2026-07`). **Smoke green end-to-end:**
  `POST /api/visa-oracle/evaluate` now returns a real engine verdict
  (`HUMAN_REVIEW_REQUIRED` + `BRIDGING_FROM_VISIT_ITK_PROHIBITED`, `mode:CURATED`,
  `rule_pack 446ee4ee seq 1`, HMAC fingerprint `fp-2026-07-1`) and the FIRST row landed in
  `visa_decisions` (`RECOMMEND`/`SHADOW`, `long_tourism`, 32-byte fingerprint,
  `ruleset_activation_id` set). The collection window is accumulating from real traffic.
  GATE STATUS unchanged: 🔴 RED (volume/breadth = 1 row so far).
- 2026-07-25 (M5, Kimi orchestrator, consolidation): **FINAL LEDGER of the two-day run.**
  **12 PRs merged**: #3032 `8875b95a` (funnel v1 resurrected, live-smoked 201 + DB row),
  #3033 `0185dc5c` (disclaimer all-5-states + PII-free submit-failure telemetry), #3038
  `6e88b24b` (next-steps gated on SUPPORTED_CANDIDATES), #3046 `7f99e570` (mig 256
  traffic_source + G-a-vol/breadth split), #3028 `8b5dffbd` (architect corpus + definitive
  plan), #3060 `35da9284` (mig 257 business/diaspora categories), #3061 `726dbc93`
  (**evaluate read-path API**), #3034 `dbb31e4d` (G-b metamorphic + canonical replay CLI),
  #3079 `f43f04c1` (SHADOW arming runbook), #3092 `c33c183a` (12 W2 fact-bases), #3090
  `3c412c96` (**first signed PRODUCTION RulePack** 38p/110r/28s, kid prod-2026-07-1),
  #3101 `6893ea5d` (activate_pack ops CLI). **Production state**: endpoint live serving
  real verdicts in SHADOW+CURATED; pack `446ee4ee` seq 1 ACTIVE (activation bb35cb81);
  secrets staged: trust store (relabeled kids), EVALUATE_MODE=SHADOW, FINGERPRINT_KEYS,
  DRIVER_TOKEN; roles: visa_activation_executor (NOLOGIN, grants on nuzantara_rag),
  visa_activation_operator (LOGIN, custody M5); `visa_decisions` accumulating.
  **Standing bugs fixed en route**: key-ceremony digit-start kids (errata + relabel),
  detect-secrets pack-hash baseline (+ triage rule), docsync/inventory date-drift pattern,
  prettier-3.8.4-vs-main skew (3 files, flagged for infra), `fly pg connect` wireguard
  hang (use fly ssh console -C + sftp put --machine). **Open items**: D1/D2/D3 owner
  decisions (pack in `research/visa/2026-07-23-d1-decision-pack.md`); W1c persona breadth
  extension (after window data); Track C wiring 4a/4b (Pro, briefed); Track B FASE 2
  (Mini, briefed); G-d drill + flip only at all-green. Seat status: codex CLI dead on M5,
  GLM Keychain-only, Opus caps ~4-5h — graders fall back to Opus/Fable per Zero.
- 2026-07-27 (M5): **TRACK C claimed by M5/2026-07-27 — SHADOW WIRING BUILT AND LIVE-PROVEN.**
  Track C was free (no branch/PR/worktree; Pro was briefed 07-25 but never started). Per spec §B.1
  the SHADOW era changes the UI by NOTHING: the only new runtime behaviour is an invisible
  fire-and-forget POST. NEW `_lib/fact-mapper.ts` (pure, all 40 wire keys) + NEW `_lib/shadow-client.ts`
  (the route's only network code, `keepalive`, errors swallowed, never awaited) + MOD `OracleShell.tsx`
  (dedupe effect) + MOD `flow.ts` (`FlowState.attempt`). 147 tests / 9 files green, `tsc --noEmit`
  clean — both re-run by the orchestrator, not taken on report.
  **TWO SPEC-vs-REALITY CORRECTIONS (the spec is 2026-07-19 and predates its own dependencies):**
  (1) it says "35-key wire shape" — the live `ApplicantFactsData` has **40** required dotted-alias
  fields, `extra="forbid"`, so a 35-key mapper 422s on every call; the delta is the 5 `secondhome.*`
  fields the E33 vertical added on 07-23 (#3044). `FactPath` = 43 members (40 applicant + 3 `derived.*`,
  correctly absent from the wire). (2) it targets `POST /api/v1/visa-oracle/recommend`; the endpoint that
  actually shipped is **`POST /api/visa-oracle/evaluate`** (#3061, 07-24). Do not build from the spec's
  §B.2 table without re-grounding both.
  **LIVE PROOF (end-to-end, first time ever performed):** the mapper's real payload POSTed to prod
  returned **HTTP 200** with a genuine engine verdict (`HUMAN_REVIEW_REQUIRED` / `CALLING_VISA_REVIEW`
  — the calling-visa overlay firing because nationality is UNKNOWN), `mode:CURATED`, `rule_pack sequence 1`,
  `decision_id` present; row landed in `visa_decisions` at `2026-07-26T18:12:26Z` — `engine_mode SHADOW`,
  `request_category long_tourism` **derived server-side from the facts** (not the caller's hint), 32-byte
  HMAC fingerprint, `ruleset_activation_id` set.
  **THREE DEFECT ROUNDS, all found by DRIVING the component, none by reading it** — record this, it is the
  method: (R1) the one-shot ref latched at first verdict arrival, so `REVIEW_ANSWERS`/`SELECT_CATEGORY`
  sent the user's PRE-EDIT answers — a wrong audit row is worse than a missing one; (R2) the cure enumerated
  those two paths and missed **`RESTART`** (two honest interviews, one row) while keying on RAW UI facts
  instead of the wire payload (editing `remote_income`, which has no FactPath, produced a byte-identical
  duplicate row). Root cause of both: one key wrong in BOTH dimensions — content and lifetime.
  **CURE (final):** `flow.ts` gains `FlowState.attempt`, bumped ONLY by a new `resetFlow()` (the reducer's
  single reset primitive); `OracleShell` holds `{attempt, keys:Set<string>}` keyed on
  `stableFactsKey(mapOracleFactsToApplicantFacts(...).facts)` — the SAME transform the POST applies.
  Contract: exactly one POST per **(interview attempt × distinct wire payload)**. Any future action that
  returns to the verdict by TRUNCATING history is covered by construction — there is no path list to keep
  in sync. **Do not "simplify" this back to a boolean ref: that shape has now failed twice.**
  **W100 CONFIRMED AGAIN:** the external GLM seat reviewed R1's diff statically and returned **SHIP** while
  the defect was live; the house lane refused the verdict, drove the component, and falsified it. Static
  review is not acceptable evidence on this surface — a reviewer must RUN the tree.
  **NEW GATE FINDING (owner-relevant, unresolved):** our own verification POSTs persist with
  `traffic_source='real'` (3 such rows on 07-26). The probe/smoke label is NOT separated from organic
  traffic, so **G-a-vol currently counts our own tests as real end-user requests**. This must be fixed
  before the collection window means anything — it is the same defect class as the 11 bootstrap rows.
  **Infra facts established (re-usable):** endpoint is fully anonymous (exact-match in `public_endpoints.py`);
  CORS already allows `https://balizero.com`; `next.config.ts` CSP `connect-src` already allowlists
  `nuzantara-rag.fly.dev` (no CSP change needed); rate limit 30 req/60s per IP; `VISA_ENGINE_DRIVER_TOKEN`
  gates ONLY the synthetic traffic classes (header `X-Visa-Driver-Token`), never normal calls; an
  all-UNKNOWN payload is contract-VALID ("thin facts are NEVER rejected"). GATE STATUS unchanged: 🔴 RED.
- 2026-07-28 (M5): **FIRST MEASUREMENT OF THE LIVE SHADOW SUBSTRATE — we are collecting on the one lane
  that cannot pass.** Collection has been writing since 07-25 (the 07-21 "still dark" line was stale), so
  this is the first read of what it wrote rather than of the ledger's narration of it. Receipt with
  re-runnable SQL + Fly evidence: `research/visa/2026-07-28-shadow-gate-measurement.md`. Numbers in GATE
  STATUS above. The shape of the finding is a **lane asymmetry**: RECOMMEND abstains by construction
  (interview never asks nationality × pack's correct `on_unknown: HUMAN_REVIEW`), while MATCH — which sets
  nationality, mints per-request random fingerprints, is counted by the collector, and sits on the funnel
  that actually has users — is simply OFF (`VISA_ENGINE_MATCH_MODE` absent from `fly secrets list`).
  **Next step is therefore arming MATCH, not fixing the RECOMMEND interview first.**
  **METHOD NOTE — record this, it cost three refutations.** The first draft of this entry claimed (a) G-a
  volume is interview-bounded and (b) G-d is unfalsifiable because ENFORCE is unbuilt. **Both were WRONG**,
  killed by the Codex `sol` xhigh adversarial pass and then re-verified on disk by the author: the
  fingerprint semantics differ PER LANE (HMAC-over-facts on RECOMMEND, random-token on MATCH), and OFF
  genuinely short-circuits before the engine, so the kill-switch is real and G-d is drillable today — what
  is unbuilt is only the authoritative ENGINE render. The generalisable trap: **a property measured on one
  surface was carried to a gate that aggregates two surfaces.** Before saying "the gate cannot be reached",
  enumerate every surface the collector counts and check the property on each. W65 also held — the refuter
  itself was checked, and its `MATCH_MODE never set` objection was right on method (inference from a zero
  count) even though the conclusion survived once real Fly evidence replaced the inference.
  GATE STATUS updated above: 🔴 RED, now with numbers and with the right reason.
- 2026-07-28 (M5, same session, hours later): **CORRECTION TO THE ENTRY ABOVE — "arm MATCH" was wrong, and
  the 07-24 runbook was right.** Caught while executing it, before the `fly secrets set`. Two facts, both
  verified: (1) `shadow.py`'s MATCH writer does NOT include `traffic_source` in its INSERT column list
  (`shadow.py:538-547`) and the column has **no default and is nullable** (checked on the live prod schema,
  not just the migration) — so every MATCH row would land NULL = **legacy = counted toward NEITHER G-a
  gate** (`shadow_evidence.py:296-303`, fail-closed). Arming MATCH without first teaching the writer to
  label its rows is a **G-a no-op** — precisely: those rows cannot advance G-a-vol or G-a-breadth, but they
  DO flow into G-c, which is deliberately not split by provenance (`shadow_evidence.py:28-29`), so they can
  still move a criterion. **Why no test caught it:** the MATCH writer's fixtures layer only migrations
  252+255 (`test_shadow_match.py:505-518`) — 256 is never applied, so `traffic_source` is not even a column
  in the schema those tests assert against. (2) `research/visa/2026-07-24-shadow-arming-runbook.md:40`
  had already recorded "leave `VISA_ENGINE_MATCH_MODE` OFF" as a deliberate **plan decision** — the window's
  evidence is to be **full-fact only**, since MATCH carries 3 of 40 facts. That decision is not mine to flip
  unilaterally: a 3-fact corpus certifies a thinner engine than the one ENFORCE would arm. **So the fork is
  an owner call**: (A) keep MATCH dark and fix the RECOMMEND interview → slower, full-fact evidence, matches
  the plan; (B) label MATCH rows `real` + arm → faster volume, thin-fact evidence. Do NOT execute (B)
  without a ruling.
  **METHOD NOTE — the lesson that keeps costing:** I read the COLLECTOR's surface allow-list
  (`EVIDENCE_ENGINE_SURFACES={"MATCH","RECOMMEND"}`) and concluded MATCH rows would count. But **a row is
  counted only if the WRITER labels it** — reader-accepts-the-surface ≠ writer-emits-the-label. Check the
  INSERT column list and the column default on the LIVE schema, not the migration file, before calling any
  lane "evidence". Same shape as the earlier two refutations this session: a property verified at one end of
  a pipe, asserted about the whole pipe. And: **before executing a step, grep the runbooks for a recorded
  decision about it** — the 07-24 rationale was one file away.

- 2026-08-10 (Pro, seq-6 activation): **SEQ-6 IS THE ACTIVE PRODUCTION PACK (SHADOW).** Signed on M5 (kid
  `prod-2026-07-1`, `payload_sha256 9691534c15e95821…3ca83f6`, from a detached worktree at origin/main),
  activated via the proven two-login ceremony (ephemeral roles
  `visa_pack_writer_ceremony_260810`/`visa_activation_ceremony_260810`, minted via stdin→psql and dropped
  same session; `activation_id 4c25cfbb-748e-404c-b639-1213304695da`, reason
  `seq6-shadow-activation-260810`). Pre-activation semantic diff seq5→seq6 verified rule-by-rule
  (113−54+45=104; every delta inside the declared perimeter, incl. the 3 within-stage changes: E30E/E30F
  removed from generic student support, e30a/e30b level-band filters conjoined to STUDY). DB verified with
  the runtime predicate (`legal_period @> now() AND system_period @> now()`): exactly ONE open activation
  — seq-6; seq-5 `system_period` closed the same instant, no gap. **PROVE-LIVE:** IT/TOURISM/10d full-facts
  → `SUPPORTED_CANDIDATES` [B1, C1] (the exact 6,610/6,610-abstention case from HANDOFF-2026-08-08);
  incomplete facts → `NEEDS_INPUT` naming `immigration.overstay_days`; negative control NG →
  `CALLING_VISA_REVIEW`, no B1. The engine binds per-request: seq-6 served with NO deploy. Ops notes:
  postgres-flex user `postgres` authenticates with `OPERATOR_PASSWORD` (`SU_PASSWORD` belongs to
  `flypgadmin`); psql inside the machine via TCP :5433 (no unix socket). **EVALUATE_MODE stays SHADOW;
  ENFORCE remains NO-GO** (DPIA/analytics-TTL unchanged). Probe cost: 4 rows in `visa_decisions` labelled
  `traffic_source='real'` (known collector-contamination class). PR #3983 (sponsor.type seam) was armed in
  the merge queue at the time of writing — separate entry when it lands.
- 2026-08-12 (M5→Mini, custody widened on Zero's explicit "copia tutto su mini"): **the private signing
  keys now exist on BOTH M5 and Mini.** The 2026-07-19 entries above ("private-key custody M5 … not on
  Pro/Mini", "AUTHORING claimed by M5 … bound to M5 by key custody") remain true as of THEIR date and are
  false as of this one — read them as history, not as current custody. All five files under
  `~/.config/nuzantara/visa-signing/` were COPIED, not moved: `2026-07-prod-1.ed25519.pem`,
  `2026-07-test-1.ed25519.pem`, `activation-operator-password`, `driver-token`,
  `facts-fingerprint-keys.json` — sha256 identical on both machines, every file `0600`, directory `0700`.
  Proven functional rather than merely present: the prod PEM loads on Mini as an `Ed25519PrivateKey` and
  derives the identical public key `819a28d67cccb11a705a0c381c2cd5ff6618c54d156ede4531f2d678ecc07210`, and
  the mode passes the check `sign_pack.py` enforces (it refuses any key file looser than 0600, fstat'd on
  the same fd it reads). All ten `backend.scripts.visa_engine.*` modules resolve in Mini's venv and
  `activate_pack.py --help` runs there, so the ceremony can now be driven from Mini. Nothing broke because
  no EXECUTABLE guard ever bound signing to M5 — the M5-only claim lived purely in prose (this log and
  `research/visa/2026-07-23-architect-state-analysis.md:123`). **Caveat recorded, deliberately not
  changed:** Mini's `~/.config/nuzantara` parent is `0755` where M5's is `0700`; `visa-signing` itself is
  `0700` on both, so the key material is unreadable to another local user, but the directory's existence
  is not hidden. **Why this happened now:** the Mini-only retention scheduler (`APPLY=true`) had been dead
  ~8h. flyctl rejects its OWN stored token 720h after `last_login` even when that token still
  authenticates — the same string exported as `FLY_API_TOKEN` worked throughout, while the config path
  answered `no access token available. Please login`, i.e. it accuses an ABSENT credential while holding a
  working one. Mini crossed that line 2026-08-11 20:40 WITA; a standing `flyctl proxy` masked it until the
  07:04 reboot killed the process. Cured on Mini with an app-scoped `FLY_API_TOKEN` in
  `~/.nuzantara-secrets.env` — the env path skips the clock entirely, so `flyctl auth login` is NOT the
  cure, it only restarts the same 30-day countdown. Pro crosses the same line 2026-08-26 03:49 WITA; its
  nightly PG backup is immune (`infra/scripts/fly-backup.sh` sources the secrets file itself), other Pro
  fly consumers were unaudited at the time of writing. The 8h of silence was a SECOND, independent defect:
  `scripts/cron-wrapper.sh` swallowed every failure alert (PR #4119).

- 2026-08-12 (Mini, completion pass — LEDGER CORRECTION FIRST): **the ACTIVE pack is sequence 7
  (`2026.8.11`, `rule_pack_id 453ee842-7f35-5d77-b460-31d67e2784c2`), not seq-6.** Every entry above stops
  at the 08-10 seq-6 activation, so this file was one activation behind; measured live in-session, not
  taken on report (`POST /api/visa-oracle/evaluate` → `decision.rule_pack.sequence 7`, `mode CURATED`,
  all-UNKNOWN payload → `HUMAN_REVIEW_REQUIRED`, the correct fail-closed). Whoever activated seq-7 did not
  update this section — the standing rule held in the breach.
  **THREE ITEMS THE LEDGER CARRIED AS OPEN ARE ACTUALLY CLOSED** (verified on disk this session, not
  inferred): the frontend/backend MODE MISMATCH is a TESTED INVARIANT, not a defect (`OracleShell.tsx`
  fails closed to `CLIENT_GUARD` on a CURATED response in ENGINE mode, pinned by `OracleShell.test.tsx`);
  the "authoritative ENGINE render is unbuilt" claim is STALE — `resolve_response_mode()` is a real
  function (`evaluate_path.py`) and all five ENGINE states render under test; and migration 268's owner
  gap is closed (PR #3766 merged, file present). Do not re-open these from the 07-28 prose.
  **STILL GENUINELY OPEN, and worked this session:** (1) G-b replays against a HAND-WRITTEN FIXTURE pack,
  never the active signed one (`_gold_fixtures.py::build_gold_compiled_pack`), and `shadow_evidence.py`
  says so itself — the `synthetic_gold` + driver-token plumbing exists but NO consumer was ever built;
  (2) internal probes land `traffic_source='real'` and contaminate G-a-vol — cured structurally here
  (`probe_evaluate.py`, defaults to `synthetic_driver`, fails closed without the custody token) instead of
  being noted in prose for the fourth time; (3) 11/38 products remain unreachable as SUPPORTED for want of
  discriminating facts — design corpus in `research/visa/2026-08-12-fact-vocabulary-extension-design.md`,
  whose regulatory citations are GENERIC and are a research lead, NOT authority to author a pack.
  **NEW OWNER-FACING FINDING (red-team, unresolved):** a pack activation needs no deploy, so a pack can
  outrun the frontend that must supply its facts; and the ≥1,000-request G-a window is semantically MIXED
  across pack/schema revisions — if that reading holds, each activation starts a fresh window, which at
  ~7 organic requests/day bears directly on whether ENFORCE is reachable at all. This is D1 territory,
  Zero's call, not a session cure.
  **MEASUREMENT BLOCKED (operator-gated, declared not skipped):** the G-a numbers could not be read from
  Mini or Pro. Pro's login Keychain is locked and an SSH session cannot unlock it or borrow the console's
  unlock (`errSecInteractionNotAllowed`); on Mini both local credentials are correctly least-privilege
  (`visa_activation_operator` and `visa_retention_worker_mini` are both `permission denied for table
visa_decisions` — the retention worker operates through `SECURITY DEFINER` functions). Unblock is
  `operator[credential]`: unlock Pro's screen once, or provision a readonly credential on Mini.
  `VISA_ENGINE_MATCH_MODE` is confirmed ABSENT from all 212 secrets on `nuzantara-rag` (genuinely absent,
  not set-to-off), so the 07-28 MATCH-vs-RECOMMEND fork is still unexecuted and still owner-gated.

- 2026-08-15 (Pro takeover, finalization in progress): **Mini is unavailable;
  Pro owns the continuation, but no authority boundary changed.** SHADOW remains
  live and ENFORCE remains NO-GO; no RulePack was signed or activated. Frontend
  labeling PR #4192 is merged at `32c8b26d2d632fc21af1d17fff74bcdc1a55fa49`.
  Its exact production-target Vercel candidate
  `dpl_GCXrsjrXwPjL9mrZdwDg9seFnLK7` is READY, contains one
  `traffic_source=real` call site and was promoted exactly once by the
  interactive Fable operator; independent API verification resolves the
  production alias to that exact candidate.
  Backend replay support from #4195 is live at merge
  `35494716abcfdb4bf7e104382cc2fef81ff3b2d7` (Fly release 4125). A bounded
  20-request `synthetic_gold` replay returned 5 matches and 15 unexplained
  divergences, with all 20 rows labeled synthetic and distinct; it supplied no
  organic evidence.

  The policy-parity repair PR #4200 was frozen at
  `4367d2c7aa2739011a7bedadb46d374424b6041a`, exact diff SHA-256
  `77019d5daa5c1915a253aa78f3aacbea1885f0964f212a809a9a53398fcd48e0`,
  with local 240-test verification and GitHub CI green, then merged through the
  queue at `2026-08-15T00:06:34Z` as
  `0fae2a64c5f495ead2a0f4f497c253f6f0cee2bd` after the exact-head Fable gate
  and green merge-group CI. Automatic backend deployment run `31852588636`
  completed successfully at `2026-08-15T00:16:26Z`, including all migrations
  and post-deploy health. Fly release 4126 carries the exact merge in every
  image's `GH_SHA` label at digest
  `sha256:d195c251d9ae9f8ae4f016c9029604d296455631b3bf05c19835366c06c388b6`;
  machine health and a separate read-only `/health/ready` request are green.
  No evaluation request was generated. The dependent draft
  queue is #4198 at `94ed6bd9204ef63080339d2a24ba5d8ea9de98a1`, #4199 at
  `903b01f8b5d2bb33141ddacaca9ac6aa6043efcc`, and #4201 at
  `69c7493146ed23fc717b73a18fff652e05089204`; Phase B follows as #4208 at
  `b5d6da2e989d2943099236b8871734cb7b378d0d`. The intended merge order is
  #4200 -> #4198 -> #4199 -> #4201 -> #4208. #4200 and #4198 are merged. #4198 was made ready and
  armed once by Fable at its reviewed head; its mode-`0600` receipt is exact and
  GraphQL first reported it `QUEUED`/`AWAITING_CHECKS` at position 3 behind
  unrelated #4204 and #4202, then marked it `UNMERGEABLE` when their aggregate
  merge group failed #4202's unrelated `codex_seat` census. #4198 itself stayed
  exact-head `MERGEABLE`/`CLEAN`; no queue mutation was made. GitHub removed the
  failing predecessor and rebuilt #4198 alone as merge-group `2b0cae18...`.
  After all 42 group checks passed, the queue merged that exact reviewed head
  at `2026-08-15T00:46:36Z`; GraphQL now reports no queue entry and `main` at
  `2b0cae18...`. #4199 was made ready exactly once by Fable after an immutable
  identity and 58-check preflight; its post-ready checks settled 61/61 clean,
  after which Fable invoked the canonical arm exactly once. Its mode-`0600`
  receipt records `903b01f8...` at `2026-08-15T00:52:49Z`, and GraphQL advanced
  it from `QUEUED` to `AWAITING_CHECKS` at position 1 on merge-group
  `d56550a5...`. After all 43/43 group checks passed, the queue merged that
  exact reviewed head at `2026-08-15T01:21:41Z`; GraphQL now reports no queue
  entry and `main` at `d56550a5...`, directly after #4198. #4201 was made ready
  exactly once by Fable at `2026-08-15T01:24:59Z` after revalidation; its 51
  post-ready checks settled clean before Fable armed it exactly once. Its
  mode-`0600` receipt records the reviewed head at `2026-08-15T01:25:52Z`, and
  GraphQL advanced it from `QUEUED` at position 1 to `AWAITING_CHECKS` on
  speculative merge commit `d54999e3...`. All 43/43 group checks settled
  terminal-clean, and the queue merged the exact reviewed head at
  `2026-08-15T01:43:30Z` as `d54999e3...`, directly after #4199. Independent
  verification now reports no queue entry and `main` at that commit. All three have
  passed their
  immutable exact-SHA Fable gates with audit markers
  `visa-fable-exact-sha-gate:94ed6bd9` and
  `visa-fable-exact-sha-gate:903b01f8` and
  `visa-fable-exact-sha-gate:69c74931`, respectively.
  Phase B (`traffic_source` required and fail-closed) is one local commit
  `b5d6da2e989d2943099236b8871734cb7b378d0d` directly atop the #4200 merge;
  it passed its immutable exact-SHA Fable gate, carries audit marker
  `visa-fable-exact-sha-gate:b5d6da2e`, and is published as PR #4208. Fable
  made it ready exactly once, observed 66 terminal-clean exact-head checks,
  then armed it exactly once. Its mode-`0600` receipt records the immutable
  head at `2026-08-15T01:49:28Z`, and GraphQL first reported it `QUEUED` at
  position 1 from `2026-08-15T01:49:29Z`, then `AWAITING_CHECKS` on speculative
  merge commit `650716442c81298647eb07542e198565709de014`. All 42/42 group checks
  settled terminal-clean, and the queue merged the exact reviewed head at
  `2026-08-15T02:16:05Z` as `65071644...`, directly after #4201. Independent
  verification reports no queue entry and `main` at that commit. Automatic
  deploy run `31858744114` completed successfully and Fly release 4127 carries
  exact `GH_SHA=65071644...` on every image record at digest
  `sha256:6bef531ce86eef0f9bca6ea3934ed3a53bf65d7d6495d024ceba319328dee0c6`.
  Its boundary test is mutation-proven: restoring
  the former implicit `real` default makes the missing-label test fail on an
  attempted evaluation, and restoring the candidate bytes makes it pass. The
  final live proof now records exactly one missing-label POST, sanitized live
  `422`, required OpenAPI, passing health and zero matching ledger persistence.
  The refreshed aggregate remains 20 synthetic/0 real and RED; no
  explicit-real smoke, RulePack action or ENFORCE change occurred. See
  `research/visa/2026-08-15-traffic-source-fail-closed-live-proof.json` and
  `research/visa/2026-08-15-shadow-evidence-final.json`.

- 2026-08-16 (M5, QW-8 ledger correction): **seq-8 exists, unsigned, chain
  BROKEN — adjudicated 2026-08-15.** `rulepack-prod-008.source.json`
  (pricing-only, 11 products) is on disk with no `.signed.json`; its
  `previous_payload_sha256` points to seq-6's signed hash instead of the
  currently-active seq-7's, so signing it as-is would either violate the
  anti-rollback check or fork the chain. Full evidence:
  `visa-oracle-adjudication/adjudication-report.md` §8 (in worktree
  `ops-visaoracle-adjudication`). **Owner GO received 2026-08-16 on Fase 3
  REV 2, OD-2 = fold**: seq-8 folds into seq-9 rather than being
  sign-activated standalone; seq-9's `previous_payload_sha256` MUST point to
  `rulepack-prod-007.signed.json` (the current highest-signed pack), not to
  seq-8. Wave-1 quick wins launched same day: QW-1 (NB-2 transport
  isolation — fresh-conversation runner, citation audit, B0 canary) is
  PR #4222, armed into the merge queue 2026-08-16 (verified via GraphQL
  `isInMergeQueue`, position 5 at arm time).

- 2026-08-17 (M5, wave-1 close + G-E1): **FASE 3 REV 2 WAVE-1 COMPLETE — 8 PRs
  MERGED TO MAIN 2026-08-16.** #4222 QW-1 (NB-2 transport isolation:
  fresh-conversation runner + citation audit, B0 canary PASS) · #4230 QW-8
  (ledger corrections) · #4231 QW-5 (freshness recheck 20 OFFICIAL_PORTAL: 16
  CURRENT / 1 CURRENT-with-exception / 3 CHANGED; source `ecd22722` — the
  E31E page — does NOT support the 2 HARD_FILTER rules citing it, seq-9
  signing gate input) · #4232 QW-3 (reachability vs active seq-7: 27/11
  identical to seq-6, 0 orphan rules, 8/44 FactPaths referenced by zero
  rules) · #4234 QW-2 (real SHADOW parity baseline pinned on sha256 of
  `evaluate_path.py`; discovery: ANY "unsure" answer on the public path
  forces `HUMAN_REVIEW_REQUIRED` via the monotone `DISCLOSED_UNCERTAINTY_REVIEW`
  adapter — the live mechanics of the flag-veto RC-1 that E5 reforms) ·
  #4235 QW-9 (source hierarchy draft) · #4236 QW-6a (HRR reason audit
  tooling, mandatory traffic_source split; QW-6b stays
  `operator[credential]`-gated) · #4238 QW-4a (2 stale
  `REVIEW_REASON_COPY` keys renamed + exhaustiveness test with
  `KNOWN_UNMAPPED` list; QW-4b stays copy-deck-gated). Still gated: QW-4b,
  QW-6b, QW-7 (OD-5).

  **POSTURE FINDING (owner-gated, deliberately NOT cured):** post-wave
  prove-live shows `https://balizero.com/visa-oracle` answers 200 but
  serves `<meta name="robots" content="index, follow">`, inherited from
  the root layout. The corner's "noindex" claims (2026-07-18/07-28 entries)
  are STALE, and the disappearance is dated: the group's
  `visa-oracle/layout.tsx` carried `robots: { index: false, follow: false }`
  from creation (`07b46cf1a`, PR #2617, 2026-07-18) until it was removed
  in `63234a12a` (PR #3732, 2026-08-07) — the exact G0–G6 rebuild merge
  (correction: an earlier `git log -S noindex` check on the group returned
  0 commits and was read as "never carried a directive" — the directive was
  written as `index: false`, never the literal string `noindex`, so that
  probe was a false negative by construction; `git log -S "index: false"`
  shows the true add/remove pair). The substantive conclusion holds — the
  noindex disappeared with the G0–G6 rebuild, NOT with wave-1 (no wave-1
  diff touches metadata, verified). Restore-vs-ratify is
  Zero's call (publish posture, Legge 5); until ruled, the SHADOW surface
  is indexable.

  **G-E1 APPROVED by Zero 2026-08-17 ("go"):** source hierarchy draft
  (#4235) ratified, artifact home confirmed (`research/visa/doctrine-factory/`
  for the ledger, `contracts/` for compiled artifacts), OD-1..5 registry
  per plan REV 2 (OD-2 = fold explicit). E2a (vertical slice D1/D2/D12 +
  E31B/E31D refuter claims — PR #4245) and E2b prep (fused query bank
  A∪B∪C, 247 unique queries, coverage matrix skeleton, zero holes on the 27
  reachable products — PR #4241) dispatched same day. The noindex ruling
  was RULED by Zero 2026-08-23 — restore `index: false` now, ratify indexability at ENFORCE
  under a 4-condition checklist — see the 2026-08-23 LIVE STATE entry above. The restore code
  change is a separate `apps/mouth` PR, not yet shipped as of that entry.

## TRACKS — parallel work groups (multi-session coordination)

The v2 program runs as separate tracks, one per surface, coordinated ONLY through this skill. Any
session on any machine: load /visaoracle → read LIVE STATE → claim a free track → work exclusively
inside that track's path scope. Scopes are disjoint by construction, so parallel tracks cannot
merge-conflict.

| Track               | Path scope (exclusive)                                | Home machine | Dependencies                                                                                                                                                                          |
| ------------------- | ----------------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A — Engine**      | `apps/backend-rag/backend/services/visa_engine/**`    | M5           | Serial chain: PR1 → PR2 (signing) → PR3 (evaluator) → PR4-6. Never parallelize within the chain.                                                                                      |
| **B — Content**     | `research/visa/**` (later curated kb via its own PRs) | Mini         | Bridging Visa branch, D7A/D7B + diaspora gap research: free NOW. The 7 interview categories: only AFTER PR #2602 (catalog bonifica) merges.                                           |
| **C — Experience**  | `apps/mouth/**` visa-oracle surfaces                  | Pro          | Prototypes/design-system with mock data: free NOW. Wiring to the real engine contract: only AFTER PR1 merges (schemas in `apps/backend-rag/backend/services/visa_engine/contracts/`). |
| **D — Ditjen demo** | (defined later)                                       | —            | Blocked until green gold-harness.                                                                                                                                                     |

**Claim protocol**

1. A track with an open `TRACK <X> claimed by …` line in LIVE STATE is TAKEN — pick another or coordinate.
2. Claiming = adding `TRACK <X> claimed by <machine>/<date>` to LIVE STATE in your track's FIRST PR; release it in the PR that closes the track.
3. Every PR from a track updates its own LIVE STATE lines (standing rule: whoever changes state updates this file).

**Quality invariants (identical for every track — parallelism never relaxes them)**

- Own worktree via `scripts/agent_start.py`; the main checkout stays read-only.
- generator≠grader before every push: cross-family adversarial review (Codex or Gemini seat) of the track's diff; the author never grades its own work.
- Final on-disk gate = an Opus 5 xhigh-effort session per track (RULED 2026-08-20, was Fable — CLAUDE.md §5); never delegated to the implementer.
- Pre-push runs on the track's own machine (3 machines = 3 independent push queues). On M5: quiet-window rule — first loadavg value < 8 and zero real pytest processes before pushing.
- All established truths in this skill bind every track — including the single all-inclusive client price ruling (never a PNBP-vs-fee split).

## PENDING (W81 ledger, project-scoped)

- SEAT-DEEPSEEK: DeepSeek V4 balance -0.04 USD (probed live 2026-07-17) — panel runs 3-external-seat and house web lane, DECLARED degraded. Arming step: operator
  top-up (Zero). Proof-of-armed: 1-token live probe HTTP 200 with is_available:true.
- R2-BROWSER-LANE deferred: 403-blocked gov wizards (IRCC / Australia / US Visa Wizard) +
  evisa.imigrasi.go.id SPA + Awwwards pixel-study need claude-in-chrome browser automation — run in
  an attended session.
- WORKTREE-REBASE: branch is behind origin/main (2+ commits at last check) — rebase before the final
  draft PR.
- DEEPSEEK-BURN-ATTRIBUTION: fleet key consumed ~$48.75/30d (~1,100 req/day bursts; $10 top-up of
  2026-07-15 burned in 48h). Eliminated: instrumented scripts (ledger=pennies), Fly backend
  (llm_cost_events=0 rows), CI, OpenClaw config, intel pipeline, devils-advocate. Hunt agent
  dispatched (leads: cognitive oracle, war-room-v2, healer, mata-garuda). Do NOT top up until
  attributed.
