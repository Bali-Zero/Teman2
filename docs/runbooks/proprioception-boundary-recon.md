# Proprioception — the boundary-reconciliation organ

> Born from the full-system TAC 2026-07-02 (meta-pattern **"unreconciled boundaries"**:
> `research/operations/2026-07-02-full-system-tac-first-pass.md` §2). One registry, one runner,
> one report, one receptor — the reconciler of reconcilers. Spec:
> `docs/specs/proprioception-boundary-recon-v1.md` (panel-reviewed: Codex red-team 13 findings
> incorporated, Gemini costruttivo 4/4 adopted).

## What it does

`scripts/proprioception.py` probes every declared **boundary** of the organism and reports
divergence. It RUNS the existing per-boundary reconcilers (launchd liveness W84, launchagent
canon #1926, organ heartbeats, docs sync W86) and adds builtins for the previously-unwatched
classes: git lag + **PENDING-ARMS ledger freshness** (checkout↔origin), **HOME-fork sha compare**
(home↔repo), **produced↔promoted** (e.g. regulatory deltas stranded on Pro), **guardian
freshness** (a stale guardian is itself DIVERGED). Boundary classes with no probe are listed
as UNWATCHED in every report — absence is visible, never silent.

**SIGNALER, never actuator** (W33/W81): it never pulls, restarts, unloads or fixes anything.

## Run it

```bash
python3 scripts/proprioception.py              # this machine, writes ~/.nuzantara-proprioception/last.{json,md}
python3 scripts/proprioception.py --fleet      # + streams itself to the other machines over ssh (read-only)
python3 scripts/proprioception.py --tags fast  # quick subset
python3 scripts/proprioception.py --strict     # exit 1 on P1 DIVERGED (CI/cron use)
python3 scripts/proprioception.py --selftest   # registry + parser-guard checks
```

Exit codes: `0` organ worked (even with divergences — the report is the product) · `1` only
with `--strict` and a P1 divergence · `2` infrastructure failure (registry invalid, zero
probes ran, report unwritable) — never trust a run that exited 2.

## The receptor (how findings reach a session)

`scripts/hooks/proprioception_sessionstart.sh` (registered in `.claude/settings.json`) reads
`last.json` at every session boot. **It is never silent**: fresh+clean → one-line heartbeat;
divergences → compact block with copy-pasteable fixes; report missing/older than 48 h → loud
STALE alarm; internal error → visible error line. Silence therefore means exactly one thing:
the hook is not registered on this machine. Kill switch: `PROPRIOCEPTION_RECEPTOR_ENABLED=false`.

## Registry (where boundaries are declared)

The embedded `DEFAULT_REGISTRY` in `scripts/proprioception.py` **is the SSOT** — versioned in
git, validated at start (`--selftest` in CI-mind). `config/boundaries.json` exists only as an
optional override (`{"probes": [...]}`); a config file that merely duplicated the defaults
would itself become an unreconciled boundary. Every report stamps `runner_version`,
`config_source`, `config_sha`, `repo_head`, and expected-vs-actual probe counts — a report
that can't prove its provenance is not a clean report.

Adding a boundary = add an entry (builtin args or a `wrap` around an existing tool with a
declared parse contract: `exit_code` | `findings_list` | `category_counts`). Wrapped output
that doesn't match its declared schema is **UNPROBEABLE, never RECONCILED** (schema drift
must not normalize into calm).

## Declared exceptions & known side-writes (audited, not hidden)

- `git fetch` in the `git_alignment` probe refreshes remote-tracking refs — it changes what
  the checkout KNOWS, never what it RUNS. Escape: `--no-fetch` (fleet-stream uses it).
- Wrapped tools write their own self-state when probed: `docs_sync --check` writes
  `.docs_sync_cache.json` (now gitignored so it can never dirty a probed checkout);
  `organism_stale_detector` appends to its own `~/.organism/alerts/` channel. These are the
  wrapped tools' designed outputs, not proprioception acting on the world.
- Evidence lines are redacted (`redact()`: token-shaped substrings → `<REDACTED>`) because
  wrapped output can quote log lines.

## Known limits (v1, accepted explicitly)

- **No cron**: with no session there is no alarm. The receptor is the consumption point;
  a single-host daily run is a later, operator-gated arming (PENDING-ARMS).
- `defined<->live` (Qdrant collections) and `process<->process` (backend `/health/detailed`
  provenance) have NO probe yet — they appear as UNWATCHED (backlog A6/A2 of the TAC).
- Fleet mode streams the script over ssh (bootstrap-safe while fleet mains lag) and runs the
  `remote-safe` tag only; full remote reports come from running the organ ON that machine.

## Bundled port-back cures (2026-07-02)

- `scripts/fly_pg_tunnel_supervisor.sh`: FLY_ACCESS_TOKEN hoist (scar 2026-06-25) ported from
  the live `~/.fly/bin` copy — the two are byte-identical again.
- `infra/launchagents/com.balizero.regulatory-watcher.daily.plist`: Pro's live plist committed
  to repo canon (was armed-but-invisible; no secrets inline, verified).
