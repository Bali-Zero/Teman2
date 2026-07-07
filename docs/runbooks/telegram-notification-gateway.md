# Telegram notification gateway — tg_notify / tg_digest_flush / lint

**Born**: 2026-07-06, Zero's mandate: *"stiamo riorganizzando telegram perché non posso
più ricevere 600 messaggi al giorno."* The census found **171 tracked executable files**
calling `api.telegram.org` directly, each deciding alone whether Zero's phone buzzes.
This gateway makes that decision ONE place with three tiers, a daily P0 budget, and
dedup — and a CI lint guarantees the direct-sender family only shrinks.

## The three tiers

| Tier | Meaning | Delivery |
|---|---|---|
| `p0` | Zero must act NOW (prod hotfix, guardian red, money, client blocked) | immediate send; max `TG_P0_BUDGET` (12) per day per machine; dedup window `TG_DEDUP_HOURS` (6h) |
| `digest` | informative (cron green, cures, merges, watcher findings) | spooled → ONE grouped message at 08:00 + 20:00 WITA |
| `log` | heartbeat / liveness / retry-ok | disk only (`log-only.jsonl`), counted in the digest footer, never sent |

## Components

- `scripts/tg_notify.py` — the gate. Stdlib-only, never fails the caller (any internal
  error → best-effort spool, exit 0). Token chain: env → `~/.nuzantara-secrets.env` →
  ssh relay (`TG_RELAY_SSH`, for M5 which holds no token) → spool as `p0_unsent`
  (fail-visible: surfaced by the next digest).
- `scripts/tg_digest_flush.py` — the flusher. Empty spool = silent success (self-probe:
  `~/.organism/tg_spool/last_flush.json` — W84 rule, healthy-silence must be provable).
  Send failure = spool preserved + exit 3 (visible in launchd LastExitStatus).
- `scripts/lint_tg_direct_senders.py` — anti-regrowth guard. New direct sender outside
  `infra/tg-gateway/grandfathered.json` fails CI (`.github/workflows/tg-gateway.yml`).
  Registered in `infra/guard-conformance/registry.json` (`_guard_new_direct_sender`,
  guilt+innocence pinned in `scripts/tests/test_tg_gateway.py`).
- `infra/launchagents/com.nuzantara.tg-digest-flush.plist` + wrapper
  `infra/launchagents/wrappers/pro-tg-digest-flush.sh` — organ `pro.tg_digest_flush`
  born via `organ_birth.py` (10 genes: registry, heartbeat sidecar, node guard,
  kill switch `PRO_TG_DIGEST_FLUSH_ENABLED=false`, single-instance, …).
  `StartInterval` 43200s (2×/day), no KeepAlive (superscar #7). Armed on **Pro**
  (PROVEN live 2026-07-07). Mini twin: `mini.tg_digest_flush`
  (`com.nuzantara.mini.tg-digest-flush` + `mini-tg-digest-flush.sh`, born
  cohort-2) — the digest is per-node: each node flushes its OWN spool.
  M5 holds no token by design (P0s relay via `TG_RELAY_SSH=pro`).

## Adoption (migrating a sender)

```bash
# shell
python3 "$REPO/scripts/tg_notify.py" --tier p0 --source my-organ --dedup-key my-key -- "message"
# python
subprocess.run([sys.executable, "scripts/tg_notify.py", "--tier", "digest", "--source", "my-organ", "--", msg])
```

Then remove the file from `infra/tg-gateway/grandfathered.json` (or run
`lint_tg_direct_senders.py --prune` to list prunable entries).

Migrated in the gateway-birth PR (pilot cohort):
- `scripts/cron-wrapper.sh` — cron failures → p0, dedup per job (flapping collapses)
- `scripts/dlq_autopilot.py` — escalations/TERMINAL → p0 · auto-fixes/sweeps → digest

Migrated in cohort-2 (2026-07-07):
- `scripts/sentinel_lib/alerter.py` — the shared sentinel library: one migration
  routes the whole family (nuzantara-sentinel, intake sentinel, system_doctor,
  daily fleet report). CRITICAL/DEADMAN → p0, WARNING/INFO → digest. Local 1h
  md5 dedup kept as fast-path for the sent/deduped return contract.
- `scripts/wa-mirror-attention-telegram.py` — realtime critical reasons → p0
  (dedup per phone+reason), daily summary → digest tier (merges into the ONE
  gateway digest). HTML stripped: the gateway sends plain text.

## Spool anatomy (`~/.organism/tg_spool/`)

- `pending.jsonl` — digest-tier events + p0 overflow/unsent, waiting for the flusher
- `log-only.jsonl` — log-tier events, rotated into archive at flush, never sent
- `state.json` — dedup index (pruned at 2× window) + daily P0 budget counter
- `archive/YYYY-MM-DD.jsonl` — flushed history · `archive-p0.jsonl` — sent P0s
- `last_flush.json` — flusher self-probe (ts, sent, events)

## Ops

```bash
python3 scripts/tg_digest_flush.py --dry-run    # render without sending/consuming
python3 scripts/tg_digest_flush.py              # flush now
python3 scripts/tg_notify.py --selftest         # 10 hermetic checks
python3 scripts/lint_tg_direct_senders.py       # 0 = clean, 1 = new senders, 2 = blind scan
```

Kill switches: unload the plist (digest stops, spool accumulates harmlessly);
`TG_P0_BUDGET=0` forces everything into the digest.

## Hardening (Codex red-team, 2026-07-06)

Accepted and fixed: spool-wide `flock` (dedup/budget/rotation races), budget slot
reserve+rollback, crash-adoption of stale `.flushing-*` claims, O_APPEND restore,
locked `log-only` rotation, `shlex.quote` on the ssh relay (alert text embeds raw
log content), safe env-knob parsing, **monotone grandfather check** (the list may
only shrink vs origin/main — a PR can't self-grandfather a new sender), wider
suffix coverage. Rejected with rationale: argparse fail-fast on a bad `--tier`
(programmer error should be loud at adoption time; runtime paths stay fail-open);
constructed-URL evasion (threat model is accidental regrowth, not insiders).

## Known boundaries (2026-07-06)

- Fly.io backend senders (prod alerts) are a separate leg — grandfathered, not yet
  migrated; the gateway runs on the Macs.
- M5's `~/.nuzantara-secrets.env` has no Telegram token (discovered during the ukraina
  suspension): P0s from M5 relay via `ssh pro` automatically when `TG_RELAY_SSH=pro`.
- The ~169 remaining grandfathered senders migrate cohort by cohort; each removal
  shrinks `grandfathered.json` and the lint keeps it monotone.
