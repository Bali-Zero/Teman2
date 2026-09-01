---
date: 2026-08-29
domain: operations
plan: beyond-sota-craft-wave
lane: "08 — Observability, immune system & self-healing"
source_report: research/operations/2026-08-28-beyond-sota-observability-immune-self-healing.md (PR #5177 branch)
status: SPEC-FINAL
---

# L08 — Observability, immune system & self-healing

## Mission

Cure the meta-pattern this lane names: "a signal, once emitted, is information." The organism is
emitter-rich and contract-poor — every scar here is a consumption contract that silently didn't
hold (wrong transport, wrong key, wrong threshold pair, wrong org, wrong freshness). Falsifying
numbers (2026-08-28/29): PENDING-ARMS strict rows 244/244 older than 48h (median 33 days); the
retro's combined figure is 476/586 = 81.2% overdue; 28% of Sentry errors dropped for quota on
`bali-zero-7p`; one alarm produced 34.6% of a month's Telegram traffic, none actionable; W120
proved the ledger's overdue-alarm sentinel read a key the reporter never emits. These PRs make the
meters honest before anything downstream trusts them.

## Ground to load (orchestrator first reads)

- `.claude/rules/cicatrix-superscar.md` [exists] — families #2 (Esiste≠Armato, ~28 members), #7
  (KeepAlive), #8 (network flap), #10 (split-brain).
- `scripts/pending_arms_report.py` [exists] — emits `"class"` (~line 1003) and
  `tech_debt_overdue` (~line 851); PR-1's lint anchors to this schema.
- `.claude/skills/modus/PENDING-ARMS.md` [exists] — the saturated ledger itself.
- `scripts/proprioception.py` [exists, 1424 lines] — probe pattern (`probe_home_fork_scripts`,
  `probe_guardian_freshness`) to model any new probe on.
- `infra/home-fork/declared-pairs.json` [exists].
- `.github/workflows/immune-enforcement.yml` [exists] — sentinel pattern: every `pull_request`/
  `merge_group`, in-job path detection; PR-1's lint wires in here.
- `scripts/lint_home_fork.py` [exists] — family #1 antidote, model for PR-3's `--discover`.
- `infra/claude-hooks/` [exists] — REPO CANON for hooks; the LIVE control plane is
  `~/.claude/hooks/` per machine, outside this repo.
- `apps/backend-rag/backend/app/setup/sentry_config.py`, `apps/mouth/sentry.{server,client,edge}.config.ts`
  [exist] — actual Sentry init points, candidates for PR-2's edge-deprioritization half.
- `.github/workflows/cron-sentry-quota-check.yml` [exists] — checks trace-sample-rate/PII flags via
  `flyctl ssh console`, NOT an accepted-count probe; do not conflate with PR-2's target.
- `docs/SLO.md` [exists] — stale since 2026-04-06.
- Memory `MEMORY_SENTRY.md` (not in this repo) — carries the org/quota facts used below.

## PR-1: feat(immune): contracts.json + lint_immune_contracts.py

**Files**: `infra/immune-contracts/contracts.json` [proposed], `scripts/lint_immune_contracts.py`
[proposed], wiring into `.github/workflows/immune-enforcement.yml` [exists].
**Gear**: 2
**Build**:

- One registry where each machine-readable health emitter (`pending_arms_report --json`,
  proprioception `last.json`, `arsenal/last.json`, heartbeat sidecars, escalations JSONL, tg spool)
  declares its schema (keys + enum domains); each consumer declares which keys it reads.
- `lint_immune_contracts.py`: pure-python CI check — fails when a consumed key is absent from the
  producer's schema, or an enum literal is compared outside the producer's declared domain.
- Scope v1 to static literals; anything dynamic is declared `UNCHECKED`, visibly, never silently
  passed.
- Fixture reproducing W120 exactly (consumer reads `classification`, producer emits `class`) must
  fail the lint; normalize the escalations `NORMAL`/`normal` case split so live tree passes.
- Wire into `immune-enforcement.yml`'s existing sentinel pattern. Keep at or under 400 lines.

**Acceptance**: guilt = W120-shaped fixture → lint RED. Innocence = matched schema, escalations
priority normalized → lint GREEN. Commands: `python3 scripts/lint_immune_contracts.py --check`
plus the paired test file under `scripts/tests/`.
**Seats**: implementer = Sonnet 5; refuter = Kimi K3 or Codex GPT-5.6 (non-Anthropic); final gate =
orchestrator (Opus 5 xhigh).
**Arming / prove-live**: armed once wired into `immune-enforcement.yml`'s sentinel path and green
on a live PR touching `pending_arms_report.py`.
**Conflicts / order**: `immune-enforcement.yml` is hot-zone — auto-merge OFF, session merges after
gates, serialize against any other workflow-touching PR this wave.

## PR-2: fix(sentry): repoint fleet quota probe at the org with traffic; deprioritize known-noise at the edge

**Files**: `apps/backend-rag/backend/app/setup/sentry_config.py`, `apps/mouth/sentry.server.config.ts`,
`apps/mouth/sentry.client.config.ts`, `apps/mouth/sentry.edge.config.ts` [exist, edge-filter half];
the "fleet quota probe" itself **[report claims — NOT found on origin/main, re-verify: no
committed script matches `bali-zero-cf`/`bali-zero-7p`; may be a home-script outside repo scope, or
already decommissioned]**.
**Gear**: 1-2
**Build** — **RE-GROUND MANDATORY**: on 2026-08-29 the fleet Sentry credential was already deleted
and its token revoked (zero consumers, pointed at `bali-zero-cf` — Fly-provisioned, SSO-only, zero
traffic). The org with real traffic is `bali-zero-7p` (28% dropped for quota over 7 days; its
`mouth` project is `nuzantara-frontend`). Minting/placing any new credential is `operator[secret]`.

- First act: grep the fleet for any surviving probe referencing either org string (this session
  found none in-repo); if one exists outside this repo, document its path and stop editing it.
- Credential-free work that ships now: `before_send`/inbound-filter logic in `sentry_config.py` and
  the three `apps/mouth/sentry.*.config.ts` files, deprioritizing known-noise (health-check pings,
  the cured `logger.warn`-per-visitor class from #5096).
- If Zero authorizes a new credential (`operator[secret]`), the probe-repoint half becomes
  buildable; until then record it as a PENDING-ARMS row blocked on the credential.
- Do not repoint `cron-sentry-quota-check.yml` — different check, out of scope.

**Acceptance**: guilt = a synthetic health-check-shaped event reaches `before_send` and is dropped.
Innocence = a real error event passes unfiltered. If credentialed: repointed probe returns nonzero
accepted-count against `bali-zero-7p`, weekly `rate_limited%` appears in digest (baseline 28%).
**Seats**: implementer = Sonnet 5; refuter = Codex GPT-5.6 or Kimi K3; final gate = orchestrator
(Opus 5 xhigh).
**Arming / prove-live**: edge-filter half armed on deploy + a live noisy event dropping before
ingestion (verify via Sentry's event stream, read-only). Probe-repoint half cannot arm without the
gated credential.
**Conflicts / order**: none known; sequence edge-filter before any probe-repoint attempt.

## PR-3: chore(hooks): purge .bak sprawl + guard

**Files**: `scripts/lint_home_fork.py` [exists, extend `--discover` for `.bak` coverage]; the
deletion target is 35 `.bak` files under **live** `~/.claude/hooks/` on 3 machines, outside this
repo's tree.
**Gear**: 2
**Build**:

- The source report gave **no acceptance test** for this PR (a recorded defect); this spec
  supplies one below.
- Extend `lint_home_fork.py --discover` to enumerate `.bak` files under any directory declared in
  `infra/home-fork/declared-pairs.json` and report them as a coverage gap.
- The actual `.bak` deletion is NOT a repo change — `~/.claude/hooks/` is live control-plane state.
  Classify precisely: deleting it is `operator[control-plane]` per this repo's Part A §2 (hook-dir
  edits are a named operator-only category); a session does not delete these on its own authority.
- Sequence to hand to the operator (not executed here): (1) tar backup of all `.bak` files across
  the 3 machines, (2) explicit file list with sha256 against repo canon
  (`infra/claude-hooks/`) — cross-reference today's 4 DIVERGED live hooks before assuming any
  `.bak` is safe to drop, (3) delete only after review.
- Ship the lint extension only; no deletion in this PR's own execution.

**Acceptance**: guilt = a `.bak` dropped into a fixture HOME-fork directory not covered by any
declared pair → flagged. Innocence = a directory with zero `.bak` files → silent. Commands:
`python3 scripts/lint_home_fork.py --discover --fixture-dir <tmp>`.
**Seats**: implementer = Sonnet 5; refuter = Kimi K3; final gate = orchestrator (Opus 5 xhigh).
**Arming / prove-live**: armed once `--discover` accurately reports the live 35-file count on at
least one machine (read-only proof; deletion not required to arm the lint).
**Conflicts / order**: the fleet-wide deletion is a separate, operator-owned action; do not block
the lint's merge on it.

## Needs-ruling carried (Zero only — this spec does NOT decide these)

- **Sentry quota increase** is a purchase — already ruled owner-only. Roadmap assumes NO purchase;
  if 28% drop is unacceptable after edge-deprioritization, that is Zero's call.
- **TCC re-grants** for DEAD-GREEN launchd jobs (`operator[tcc]`) — no session can cure these.
- **Retirement candidates among ~100 canon-less live plists**: adopting into repo is session work;
  _deleting_ live jobs needs a per-batch Zero ack.
- **The `.bak` deletion list** (PR-3): session prepares list + backup; deletion on each machine's
  live control plane is `operator[control-plane]`.

## Suspend & ledger rules

A PR red for the SAME cause three times (gate, lint, or refuter finding on the same surface) gets
no fourth round: SUSPEND with one PENDING-ARMS line naming the cause, branch left alive, move to
the next PR. A fix-of-a-fix chain stops at depth 1 — a wrong correction means the surface is
under-specified and needs a written spec, not a third attempt. Every built-but-not-armed step
(PR-2's credential-blocked half, PR-3's fleet-wide deletion) gets one PENDING-ARMS row naming the
artifact, the missing arming step, and the owner.

## Out of scope

- Any new LaunchAgent daemon (W84: "no 177th daemon").
- Purchasing additional Sentry quota (needs-ruling).
- Deleting any live `~/.claude/hooks/` file directly from this session.
- The burn-rate receptors (R1), wide-event stream (R5), mute-cron battery (R3), restart-budget gene
  (R4), and alert-precision ledger (R6) from the source report's §5 — real recommendations, none
  promoted to this wave; candidates for a later wave.
