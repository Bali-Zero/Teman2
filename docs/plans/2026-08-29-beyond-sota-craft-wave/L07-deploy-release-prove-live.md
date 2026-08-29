---
date: 2026-08-29
domain: operations
plan: beyond-sota-craft-wave
lane: "L07 — Deploy, release & prove-live"
source_report: research/operations/2026-08-28-beyond-sota-deploy-release-prove-live.md (PR #5177 branch)
status: SPEC-FINAL
---

# L07 — Deploy, release & prove-live

## Mission

Cure the "control plane's announcement is the state of the data plane" belief (report §8):
health=200 has hidden a dead RAG worker, a READY Vercel deployment has served yesterday's build,
and an advisory smoke test has been red for 30 runs with nobody looking. Falsifying number: a
scheduled journey probe as designed by ASSEMBLY-LINE would catch only **2 of 5** measured
2026-08-28 public-surface defects (certain, +1 with a persona matrix) — because it does not exist
yet, and time-to-detect a dead public funnel is today **unbounded** (a human notices). This lane
arms the first receptor: an anonymous-visitor probe of the VOA journey with a dead-man that can
pull `GARUDA_PUBLIC_ENABLED` off across both platforms when the heartbeat goes silent.

## Ground to load (orchestrator first reads)

- `docs/factory/ASSEMBLY-LINE.md` [exists] — stages 6-7, ship ladder + dead-man doctrine armed
  here. `docs/plans/2026-08-24-garuda-voa-live/MANDATE.md` [exists] — switchboard reserving
  exposure flips as Zero's gesture (§7).
- `.github/workflows/garuda-arm.yml` [exists] — sanctioned two-platform flag actuator (closed
  `GARUDA_*` allowlist, `type: choice` inputs, `garuda_public_enabled` at line 50).
  `.github/workflows/lint-garuda-environment-values.yml` [exists] — schema-parity lint it leans
  on, do not duplicate. `.github/workflows/fly-secrets-check.yml` [exists] — dead-man pattern to
  imitate for the probe's own channel self-check.
- `.github/workflows/fly-deploy.yml` [exists] — 6-job deploy DAG; PR-1's guilt check breaks the
  evaluate route on a scratch branch; this file itself is NOT touched by this lane.
- `scripts/prod_crm_smoke.cjs` [exists] — smoke-script mechanics reference.
  `research/operations/2026-05-20-probe-sandbox-setup.md` [exists] — `is_probe_sandbox` tenancy,
  reuse verbatim. `docs/runbooks/synthetic-probe-cleanup.md` [exists] — idempotent cleanup SQL
  pattern to follow, not reinvent.
- `apps/mouth/e2e/visa-oracle-fullstack.spec.ts` [exists] — advisory, never-green fullstack smoke
  PR-1 repairs (13F/17S/0P over 30 runs per report §2).
- `apps/mouth/src/app/visa/voa/flag.ts` + `flag.test.ts` [exists] — frontend half of the
  two-platform flag; literal `"true"` grammar, `notFound()` otherwise.
- `infra/launchagents/` [exists, 74 `com.nuzantara.*` plists verified] — new plists follow that
  naming (`com.nuzantara.voa-probe.plist` / `.voa-deadman.plist`). `infra/launchagents/wrappers/`
  [exists] — wrapper shape to imitate (e.g. `fly-pg-proxy-wrapper.sh`, `garuda-consumer.sh`).
- `scripts/probes/` [exists: `intel_lake_e2e_probe.py`, `wr2_e2e_probe.py`] — new files land
  alongside these. `scripts/tests/test_voa_probe_wrapper.sh` — **[proposed, verified absent]**.
- Scars: superscar family #2 (`.claude/rules/cicatrix-superscar.md`, "green≠working");
  `discovery_five_measured_defects_on_public_surfaces_2026_08_28.md`; cookie-jar-404 trap memory
  (2026-08-28, quoted below).

## PR-1: fix(e2e): make the visa-oracle fullstack smoke green and stable

**Files**: `apps/mouth/e2e/visa-oracle-fullstack.spec.ts` [exists, advisory + never-green today —
this PR repairs it, does not create it]
**Gear**: 2
**Build**:

- Read the current 13F/17S/0P pattern from the last 30 CI runs (`gh run list`) before touching
  assertions — do not guess the failure cause.
- Rebuild the seed fixture against the CURRENT resume/evaluate contract (report's own fix plan);
  the spec was written against a stale contract shape.
- Fix assertions against the real current API contract — never weaken an assertion to force green.
- Once green locally, flip the job from advisory (`continue-on-error`) to blocking.
- This PR stops at green-and-stable. Promoting the job to a branch-protection required-check is
  NOT self-authorized here — it is an operator/Zero ruleset action (see Needs-ruling item 7);
  this lane only supplies the evidence (2 consecutive green runs) that promotion needs.
  **Acceptance**: Guilt — break the evaluate route on a scratch branch (malformed verdict) → red for
  that specific reason. Innocence — green on 2 consecutive unrelated PRs. Command:
  `gh run list --workflow=<fullstack-smoke> --limit=5 --json conclusion` shows `success` twice.
  **Seats**: implementer = Sonnet 5; refuter = Kimi K3 (test-repair, no prod-flag surface); final
  gate = orchestrator (Opus 5 xhigh).
  **Arming / prove-live**: armed when the job is green and blocking (non-advisory) on 2 consecutive
  unrelated PRs — green-without-blocking is the never-armed state this PR cures. Required-check
  promotion is a separate, later operator/Zero action and is not part of this PR's arming.
  **Conflicts / order**: MUST land+verify green before PR-2 (PR-2 reuses this journey material and
  must not inherit a known-red spec).

## PR-2: feat(probes): anonymous VOA journey probe, sandbox-tenant, Mini-scheduled

**Files**: `scripts/probes/voa_journey_probe.mjs` [proposed]; `infra/launchagents/com.nuzantara.voa-probe.plist` [proposed] + wrapper [proposed]; `scripts/tests/test_voa_probe_wrapper.sh` [proposed]
**Gear**: 2
**Build**:

- Real cookie jar, not bare `fetch` — the funnel's POST sets an HttpOnly cookie; a GET without a
  jar reads as a false 404 (quote this trap verbatim so nobody "fixes" it into a bug).
- Content assertions, not status-only: assert absence of `NEXT_HTTP_ERROR_FALLBACK` in the body —
  a disabled flag answers HTTP 200 with a Next.js 404 template AND the correct `<title>`, so
  status+title probes both falsely pass.
- `is_probe_sandbox` tenancy exactly per the probe-sandbox-setup doc; cleanup per the
  synthetic-probe-cleanup runbook, idempotent, 0 rows left even on partial failure.
- Do NOT probe order/payment routes — 503 BY DESIGN today (missing `GARUDA_XENDIT_SECRET_KEY`);
  stop at the pre-payment leg, do not treat that 503 as a failure signal.
- Write one JSON heartbeat row/run (timestamp, verdict, latency) at a path PR-3 reads — define
  this contract explicitly in the PR description.
- Schedule on Mini via `StartInterval` (NOT `KeepAlive` — family #7 trap), every 15 min; run
  `scripts/lint_plist_keepalive.py` against the new plist before opening the PR.
- Wrapper corpus test follows the `vercel-autopromote-tests.yml` pattern: asserts exit code AND
  heartbeat-file content, not exit code alone (family #2).
  **Acceptance**: Guilt — probe against a deliberately dark route (flag off) → verdict FAIL,
  heartbeat `verdict: fail`, reason names the `NEXT_HTTP_ERROR_FALLBACK` match. Innocence — probe
  against the live funnel → verdict PASS, 0 sandbox rows after cleanup (verify via
  `mcp__postgres-nuzantara__query` read-only count on the tenant marker). Wrapper corpus green in CI.
  **Seats**: implementer = Sonnet 5; refuter = Codex GPT-5.6 sol (xhigh) — this builds the sensor
  PR-3 trusts, a false-green probe silently disarms it; final gate = orchestrator (Opus 5 xhigh).
  **Arming / prove-live**: armed when `launchctl print` on Mini shows loaded AND at least one real
  heartbeat row with a real timestamp exists (superscar #2: check log content, not exit 0).
  **Conflicts / order**: depends on PR-1. Must not duplicate any L11 journey (L11 owns
  dream/clock/magic-link against `apps/mouth`; this probe is VOA-funnel-only).

## PR-3: feat(probes): dead-man receptor — heartbeat silence flips GARUDA_PUBLIC_ENABLED off

**Files**: `scripts/probes/voa_deadman.py` [proposed], `com.nuzantara.voa-deadman.plist` [proposed], tests [proposed]
**Gear**: 2
**Build**:

- Watches the heartbeat PR-2 writes, NOT the probe process — a dead probe and a probe reporting
  FAIL are different states the dead-man must distinguish.
- Silence or red 15 min → fire `gh workflow run garuda-arm.yml -f garuda_public_enabled=false`.
- DRY-RUN ONLY by default: log the fire decision + Telegram, do not actually invoke `gh workflow
run` until real-fire is explicitly enabled via its own env gate — real-fire authority is Zero's
  (§ Needs-ruling item 2).
- Record that probe+dead-man colocated on Mini is a single failure domain (refuter-flagged);
  worst-case actuation is ~30 min (15-min probe interval + 15-min silence threshold) — use that
  as the honest acceptance target, not the report's original `<20 min` optimistic figure.
- Self-probe the Telegram channel itself (`test_alert`-style) so silence ≠ "channel is dead", same
  discipline as `cron-fly-watcher.yml`.
  **Acceptance**: Guilt — seed a stale heartbeat (>15 min old) → dry-run fire logged, `gh workflow
run` dry-run-equivalent proof captured, Telegram message sent AND delivery verified. Innocence —
  fresh heartbeat (<15 min, PASS) → no fire, no alert. Real-fire path stays behind its own default-
  off env gate.
  **Seats**: implementer = Sonnet 5; refuter = Codex GPT-5.6 sol (xhigh) — mandatory, this is the
  prod-flag-touching PR; final gate = orchestrator (Opus 5 xhigh).
  **Arming / prove-live**: armed when (a) `launchctl print` loaded with real log content, (b) a
  seeded-stale-heartbeat dry run has actually produced a Telegram message this session, (c) real-fire
  gate is explicitly OFF and documented as requiring Zero's go.
  **Conflicts / order**: depends on PR-2's heartbeat contract; never merges with real-fire default
  ON; do not build ahead of PR-1/PR-2 armed.

## Needs-ruling carried (Zero only — this spec does NOT decide these)

1. **Exposure-changing flag flips** — dark→5%→100% and GARUDA go-live itself (MANDATE §3, 5
   prepared decisions: payment provider + his credentials; retention number; visual identity).
   PR-3's dead-man only ever flips **off**.
2. **Real-fire authority for the dead-man** (PR-3) — behavior is pre-ruled doctrine (ASSEMBLY-LINE
   §7), but first arming of real-fire (vs dry-run) hands an automated organ authority over a
   public business surface — needs Zero's explicit go. Until then: dry-run only.
3. **Payment-provider credentials** (sandbox and live) — MANDATE row 1, owner signs up and holds
   them; this lane's probe stops before the payment leg.
4. **New Actions secrets** for any future restore-drill Qdrant leg (report §6 wave 3, out of scope
   here) — secret values are operator-held.
5. **Optional, parked**: a fleet-local `nuzantara-rag`-scoped Fly token (`operator[gui]`) — this
   lane routes via `gh workflow run garuda-arm.yml` instead, so this stays parked.
6. **SLO targets as commitments** — the deploy-frequency number re-derives mechanically (R6, not
   this lane); CFR/time-to-restore targets are a business promise Zero signs.
7. **PR-1's required-check promotion** — making the fullstack-smoke job a branch-protection
   required-check (`gh api` the ruleset) is an operator/Zero ruleset action, not something this
   PR self-authorizes. PR-1 delivers green-and-blocking plus the 2-consecutive-green evidence;
   promotion happens after, on Zero's or the operator's own action.

## Suspend & ledger rules

- Rule 8: a PR red for the SAME cause three times (gate/lint/refuter, same surface) gets no
  fourth round — SUSPEND with one PENDING-ARMS line naming the cause, branch left alive, move on.
- Fix-of-a-fix stops at depth 1: a wrong correction means the surface is under-specified — write
  the spec or escalate to Needs-ruling, never open a third corrective PR.
- Every built-not-armed step gets one PENDING-ARMS row (e.g. "PR-2 merged, plist not installed on
  Mini"), closed only when `launchctl print` + real log content confirm the arm.
- PR-3's real-fire gate is itself a standing PENDING-ARMS row until Needs-ruling item 2 is ruled.

## Out of scope

- `fly-deploy.yml` deploy-DAG changes (R4 fixture-replay judge, R5 expand/contract) — wave 3.
- Deploy-gap `?dpl=` and surface-inventory parity probes (R2); `flags.yaml` SSOT + lint (R3) —
  separate PRs, not this lane's 3.
- Any L11 journey sentinel (dream/clock/magic-link) — VOA-funnel probe only, do not widen.
- Flipping `GARUDA_PUBLIC_ENABLED` to true on either platform — this lane only arms an OFF-switch.
- Real-fire mode for the dead-man — dry-run only per Needs-ruling item 2.
