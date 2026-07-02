# SPEC — Proprioception v1: the boundary-reconciliation organ

date: 2026-07-02 · owner: Zero · status: panel-reviewed draft → build
origin: full-system TAC 2026-07-02 (`research/operations/2026-07-02-full-system-tac-first-pass.md`) — meta-pattern "unreconciled boundaries"

## Problem (the malattia-delle-malattie)

Every recurring trauma family reduces to: a signal emitted on ONE side of a boundary
(api↔rag process, repo↔$HOME, machine↔fleet, defined↔live, wrapper↔payload,
produced↔promoted, code↔docs) is trusted as truth for BOTH sides, and nothing probes across.
The organism already owns ~7 per-boundary reconcilers — `launchagent_reconcile.py` (#1926),
`launchd_liveness_detector.py` (W84), `organism_stale_detector.py`, `docs_sync.py --check`,
`runtime-reconcile.sh` (W81), `verify_mcp_integrity.sh`, `branch_graveyard_cleanup.sh` —
but they are themselves unreconciled: different outputs, no single consumption point, nobody
watches THEIR freshness, and 3+ boundary classes have no probe at all (git-lag/ledger
freshness, produced↔promoted, cross-machine fleet view).

## The organ

**Proprioception** = the organism's sense of its own body position. One registry, one runner,
one report, one receptor.

1. **`config/boundaries.yaml`** — declarative registry. Each entry:
   `id, boundary (sideA ↔ sideB), kind (wrap|builtin), cmd/args or builtin name,
machines [m5|pro|mini|all], timeout_sec, severity (P1|P2|P3), fix_hint`.
   The SSOT of "which boundaries exist and how each is probed". A boundary without a
   registry entry is _declared unwatched_ (listed in the report's tail — visible debt).

2. **`scripts/proprioception.py`** — the runner (stdlib-only, no deps).
   - Executes every probe scoped to this machine, each under its own timeout, never letting
     one probe kill the run.
   - `wrap` probes shell out to the existing reconcilers (JSON mode where available) and
     normalize; `builtin` probes are implemented in-file:
     - `git_alignment` — behind-count vs origin/main (fetch --quiet allowed, never pull),
       dirty-file count, and **ledger freshness** (blob of `.claude/skills/modus/PENDING-ARMS.md`
       local vs origin/main — kills the "TRIAGE read a stale ledger" class).
     - `produced_promoted` — configurable glob pairs: files present on the producing side but
       not committed (e.g. `research/regulatory/*-delta.json` untracked count + newest age).
     - `home_fork_scripts` — generic $HOME-executed script vs repo counterpart sha-compare
       for configured path pairs (covers non-launchd cases; launchd targets are #1926's job).
     - `guardian_freshness` — age of the OTHER reconcilers' last outputs (report/log/state
       files) vs their expected cadence → a stale guardian is itself DIVERGED
       (guardian-of-guardians, kills silent-when-broken).
   - Output: normalized verdicts `{id, boundary, status: RECONCILED|DIVERGED|UNPROBEABLE,
n_findings, evidence[≤5 lines], fix_hint}` → `~/.nuzantara-proprioception/last.json` - human `last.md`. ALWAYS writes a summary line (timestamp, probe count, diverged count)
     — an empty report is impossible by construction.
   - `--fleet`: ssh pro/mini with a REDUCED inline probe set (git_alignment + remote report
     age) — read-only one-liners, no file dependency on the remote checkout (bootstrap-safe
     while fleet mains lag). Full remote runs come free once merged+pulled.
   - Exit 0 always (report is the product); `--strict` exits 1 on any P1 DIVERGED (for CI/cron).

3. **`scripts/hooks/proprioception_sessionstart.sh`** — the receptor (registered in repo
   `.claude/settings.json`, same pattern as the escalations receptor).
   - Reads `last.json`. Report **missing or older than 48h → LOUD**: "PROPRIOCEZIONE STALE —
     run `python3 scripts/proprioception.py`". Fresh + diverged>0 → compact block (top items).
     Fresh + clean → silent (safe: staleness is loud, so silence now proves recency+cleanliness).
   - Fail-open, ≤4s hard budget, kill-switch `PROPRIOCEPTION_RECEPTOR_ENABLED=false`.

## Invariants (non-negotiable)

- **SIGNALER, never actuator** (W33/W81): no restart, no pull, no unload, no fix. Ever.
- **Content compare, never proxy** (W88): sha/blob, not timestamps/exit-codes, wherever both
  sides are readable.
- Machine-aware paths (`balizero` on M5, `nuzantara` on Pro/Mini) — no hardcoded users.
- **No secret values** in yaml, report, evidence lines (paths/names/ages only).
- No new daemon in v1 (176 exist; W84). Arming = receptor via repo settings + on-demand runs;
  optional single-host cron is a later, operator-gated step (PENDING-ARMS line).

## Cures bundled in the same PR (boundary port-backs, verified today)

- `scripts/fly_pg_tunnel_supervisor.sh` ← port the live-only FLY_ACCESS_TOKEN hoist
  (scar 2026-06-25, ~/.fly/bin copy ahead of repo — verified by diff).
- `infra/launchagents/com.balizero.regulatory-watcher.daily.plist` ← commit the Pro-only
  plist into repo canon (secrets-scrubbed if any inline).

## Out of scope v1 (explicit)

Qdrant defined↔live (A6 — needs env), `/health/detailed` process-provenance fix (A2 — backend
change), auto-remediation of any divergence, cron installation on Pro/Mini.

## Acceptance (falsifiable)

1. Runner on M5 exits 0, ≥7 probes, and — run before cures — flags the KNOWN divergences:
   fly-tunnel DIVERGED, M5 behind origin/main, regulatory deltas stranded (guilt test).
2. After port-backs: fly-tunnel probe → RECONCILED (innocence test).
3. Receptor: fresh report → block/silence as designed; artificially aged report → STALE alarm.
4. `--fleet` returns Pro+Mini git-lag read-only.
5. Zero secret values anywhere in committed files or reports.
