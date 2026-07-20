# Runtime/Dev checkout split — runbook (P0 shipped, P1/P2 operator-gated)

> **Why this exists.** On Pro, `~/nuzantara` is BOTH the h24 runtime (104 launchd organs
> run from it) AND a dirty dev scratch (sessions sully it). So it can't be pulled — it sits 169
> commits / 6 days behind origin/main, and every merge is **sterile** (never reaches the live
> organs). 20 more organs point at `~/nuzantara-deploy`, a stable auto-pulled checkout
> that **vanished** (scar W81). Fix: every runtime organ runs from a read-only, auto-pulled
> `-deploy` clone; the main checkout becomes dev-only.
>
> Council-validated design + full rationale: `mem query "runtime dev checkout split"` (decision
> 2026-06-27). This runbook is the operative half.

## Phases (each its own PR + operator gate — DO NOT batch)

- **P0 — INERT scaffolding (this PR).** Three scripts, nothing migrated, no live organ touched.
- **P1 — operator-gated, no live session on Pro.** Bootstrap the `-deploy` clone, point the
  deploy-puller at it, install + arm the reconcile watchdog (strict mode).
- **P2 — operator-gated, in waves.** Migrate the 20 already-deploy-intended organs first, verify,
  then the 104 in waves with health-wait + per-label rollback.

## P0 artifacts (all in `scripts/`, all inert, all kill-switchable)

### `runtime-reconcile.sh` — anti-W81 watchdog (signaller, not actuator)

Asserts: `-deploy` exists (`.git` as dir OR file — clone or worktree), on the right branch,
pulled recently. P0 default `RUNTIME_RECONCILE_STRICT=0` → records breaches to log + heartbeat,
does NOT page. P1 flips `STRICT=1` → P0 Telegram on any breach. Kill: `NUZ_RUNTIME_RECONCILE_DISABLED=1`.
Heartbeat: `~/.organism/last_seen/pro.runtime_reconcile.json` (A2-observable).

> **P1 reality (2026-06-27): runtime root is a WORKTREE, not a clone.** The council Q1 design
> was a full clone (isolation from the main's `.git` churn — W63/#5). On execution the Pro disk
> was **98% full (8GB free), and the ~18GB of `.worktrees/*` were all UNMERGED sibling work**
> (`ahead≥1`, many dirty, 2 with live procs) — un-reapable without scar W80. So the clone was not
> physically affordable. The existing `wr2-deploy-pull.sh` bootstraps a worktree, which is what
> was armed. The reconcile logs this as a **visible DEBT, not a breach**. **Clone is deferred
> until free disk > 60GB** (needs an external archive target for the sibling worktrees, or those
> PRs merged). Until then deploy shares the main's object store — a corrupted/prune'd main can
> take it down. `deploy/main` is a separate branch, so ref-churn is mitigated; object-store
> coupling is not.

```
bash scripts/runtime-reconcile.sh          # warn-only
RUNTIME_RECONCILE_STRICT=1 bash scripts/runtime-reconcile.sh   # pages on breach (P1)
```

### `runtime-health-gate.sh <CHECKOUT_DIR>` — pre-advance gate (council Q3)

Run against a CANDIDATE checkout at the target SHA. Exit 0 = safe to become runtime; 1 = BLOCK
(do not advance — keep last_good_head). Checks: registry valid+checksum, owner_module scripts
exist (≤ tolerance, default 60 — today's baseline is 42 missing), sentinel compiles, A2 test
green. Resolves python via the checkout's venv (Golden Rule #1). Kill: `NUZ_RUNTIME_HEALTH_GATE_DISABLED=1`.
P1 wires this into `wr2-deploy-pull.sh` BEFORE the ff-only advance.

```
bash scripts/runtime-health-gate.sh ~/nuzantara-deploy
```

### `runtime_checkout_report.py` — migration map (council Q2/E)

Read-only. Cross-refs the registry against installed (or repo) plists and classifies each
pro_launchd organ's runtime root: deploy | dirty-main | external | unknown. This is the list
P2 migrates FROM (instead of eyeballing 104 plists). `--strict` exits 1 if any organ still runs
from dirty-main (a P2 done-check). Run on the **Pro** for the real installed-plist truth.

```
python3 scripts/runtime_checkout_report.py --json | jq .summary
```

## Known gap (flagged, not solved in P0)

`registry_launchd_gap` in the report = organs with no readable plist to classify. The registry
lacks launchd schedule/env/args fields, so P0 does NOT generate full plists yet. Enriching
`organs_registry.yaml` with `runtime_root` + launchd fields (then a real plist generator) is the
first task of P1 — it also closes the ~42 owner_module "missing" audit (same source-of-truth).

## P1/P2 are operator-gated because

They touch 104 production h24 organs (bounded restarts = real disruption) and require the main
checkout to be clonable — blocked today by a LIVE session's 213 dirty files (scar #5, leave-dirty).
Run P1/P2 when no live session is active on Pro. That's Zero's call (DNA L6).
