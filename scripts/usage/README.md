# scripts/usage/ — Consumi flotta (dashboard + collector seat)

> Creato 2026-08-09 da sessione Cowork (Fable 5). Contesto: FLEET_TOPOLOGY.json + AGENTS.md §17.

## Cosa c'è

| File | Cosa fa |
|---|---|
| `usage-dashboard.html` | Dashboard self-contained. Sezione API **già viva** (snapshot dal ledger PG `llm_cost_events`, mig 117). Sezione seat si accende quando il collector gira accanto (fetch di `seat_usage_snapshot.json`). |
| `seat_usage_collector.py` | Parsa i log locali delle CLI (Claude ×N profili, Codex ×2 CODEX_HOME, agy, kimi) → snapshot JSON. **Armato 2026-08-19 via launchd su M5+Pro+Mini (`infra/launchagents/install_seat_usage_cron.sh` — la prova è lo snapshot scritto dal daemon, mtime-advance, mai un run a mano).** |
| `seat_map.json` | Generato al primo run: mappa profili locali → seat A1/A2/A3/AZ/O1/O2. Da editare dopo l'installazione di cswap. |
| `com.nuzantara.seat-usage.plist.template` | Template LaunchAgent (StartInterval 1800, no secrets). L'arming è avvenuto: l'installer `infra/launchagents/install_seat_usage_cron.sh` renderizza QUESTO template (che resta qui accanto al collector by design — l'installer lo risolve dal proprio checkout). |

## La verità sulle fonti (matrice onestà)

| Fonte | Metodo | Stato |
|---|---|---|
| API a consumo (gemini, claude_oauth, embeddings, openrouter) | ledger PG `llm_cost_events` → già esportato ogni 30' in `~/.agent/cost-ledger/` (`cost_ledger_export`) + cost-breaker armato | ✅ VIVO |
| Claude Max/Team (4 account) | nessuna API pubblica quota → parse transcript `~/.claude*/projects/**/*.jsonl` per profilo (pattern ccusage); finestre 5h/7d stimate dai timestamp | 🔧 collector da armare |
| Codex Pro (2 account) | parse `$CODEX_HOME/sessions/**/*.jsonl` per home | 🔧 collector da armare |
| Google AI Ultra (agy) | nessuna API quota → conteggio invocazioni dai log + quota % solo in settings UI | 🟡 parziale per natura |
| Kimi (piano Vivace — ex "Allegro" nei doc) | console GUI kimi.com/membership/subscription?tab=quota → manual snapshot in `~/.agent/seat-usage/console_quota_snapshot.json` (local, 0600, NEVER committed — schema self-documented in the file; monthly total + 5h/7d Code windows) | ✅ ARMED (manual, 2026-08-15 first reading) |
| Alibaba Token Plan (crediti) | console GUI Model Studio → same local snapshot file (`alibaba_tp1` key: 7-day rolling % + cycle + auto-renewal); PROBE-1 residual (programmatic credits endpoint) stays open | ✅ ARMED (manual, 2026-08-15) |
| Infra (Fly/Vercel/Upstash) | fatture console; fuori scope v1 | ⏳ |

Console snapshots: sources with no API live in `~/.agent/seat-usage/console_quota_snapshot.json` (local-only, never in this public repo). A session or the operator refreshes it from the two console pages; the dashboard can fetch it when served locally alongside the seat snapshot.

## Arming (sessione Mac, in ordine)

1. `python3 scripts/usage/seat_usage_collector.py` → verifica parse sui log VERI (aspettarsi schema-drift: sistemare i campi, è scritto difensivo).
2. Editare `seat_map.json` con i profili cswap reali → seat.
3. Test 2-3 run; poi spostare il plist template in `infra/launchagents/` e armarlo col pattern degli installer esistenti (wrapper, no secrets, W64 graceful).
4. Servire la dashboard: opzione minima `python3 -m http.server` nella dir; opzione vera: aggiungerla a `apps/nuz-status-mac` (PENDING).
5. PROBE-1: aggiungere il poller crediti DashScope al collector.

## Estensioni future

- Pannello Grafana (lo stack monitoring/ esiste già) leggendo lo stesso snapshot.
- Quota % Anthropic via cswap (`cswap list` espone finestre 5h/7d) — parse dell'output come sorgente aggiuntiva.
- Refresh automatico dell'artifact Cowork via scheduled task.

## Task outcomes and observed usage (`task-outcome/1`)

The existing collector and its 30-minute LaunchAgent also consume
`~/.agent/cost-ledger/task-outcomes/*.json`. The additive `tasks` and `tasks_meta`
fields are emitted only when manifests exist and do not change `seats[]`.
Use `--task-outcomes DIR` to select a directory;
`--tasks-only` prints the task report without writing the snapshot. No additional
daemon is needed. `task_outcome_manifest.example.json` is a valid shape with
placeholder hashes and an explicitly unknown outcome; replace every placeholder.

The release owner writes one redacted manifest per task after consulting the
independent gate. These are **trusted outcome attestations**, not a replacement
for the gate or a cryptographic verification of the artifact named by its hash.
Never mark an outcome complete merely because a session exited or a PR merged.
`verified_complete` requires an evidence SHA-256, verification time, at least
one non-gate participant, and a distinct listed `gate` session observed in logs
(`verifier_role=fresh-gate`). The gate cannot be an ancestor or descendant of
any non-gate participant. The graph combines native and declared parent edges,
including cross-provider edges. Missing, ambiguous or cyclic lineage cannot
establish independence. The gate needs an event inside the task window no later
than verification time; unrelated old activity is insufficient. Independent fresh
CLI roots can be declared as overhead: their usage is included even without a
shared conversation parent. Never erase a real contribution edge for eligibility.
CI-only attestations remain `unknown` and outside the denominator until a CI
evidence join exists. It also requires a closed, timezone-aware
`started_utc`/`ended_utc` interval ending no later than the snapshot time and
containing the verification time. Otherwise the
collector downgrades the outcome to `unknown`.

Hash **the full identifier**, with SHA-256 and no truncation. Claude main sessions
use `sessionId`; a sidecar's logical identity is `sessionId:agent-<full-agent-id>`
(the sidecar filename stem). Codex uses the first `session_meta.payload.id` in
each file, ignoring metadata embedded by a fork; native children
link through `source.subagent.thread_spawn.parent_thread_id`. The collector adds
observed local descendants once, including retries. Explicit child rows override
inherited `overhead`/attempt metadata. Cross-provider CLI children must be listed
explicitly: their parent cannot be discovered from a native same-provider tree.

Provider-native counter names stay separate: Claude `input_tokens`,
`cache_read_input_tokens`, `cache_creation_input_tokens`, `output_tokens`; Codex
`input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens`.
For Codex, cached input is a subset of total input: uncached input is
`input_tokens - cached_input_tokens`; reasoning output is a subset of output.
For Claude, input, cache-read input and cache-creation input are separate buckets.
Do not sum the Codex subsets into their totals or treat its total input as raw
uncached input. Keep the provider breakdown instead of adding unlike counters.
`usage_events` counts observed response groups/cumulative updates, **not API calls**.
Codex repeats are deduplicated, increments are counted across counter resets,
and the first event uses `last_token_usage` to avoid billing inherited cumulative
history to a child. Claude reuses the existing per-field streaming reducer.
Window attribution uses the latest response timestamp / cumulative-update
timestamp and is observed, provisional usage, not a provider invoice.

Missing sessions, missing counters, damaged records, incomplete response identity,
and overlapping task attribution are visible and exclude a task from the verified
denominator. Unknown is never zero. `failed_or_retried_sessions` counts declared
rows with `status=failed` or `attempt>1`; both failed and successful attempts still
contribute usage. `overhead_tokens` is a subset of `by_provider`, not extra spend.
An explicitly declared non-overhead participant with no usage inside the window
is incomplete (`declared_session_without_window_usage`), not a zero-cost worker.
The mean includes only verified tasks with complete observed usage and is withheld
across different task classes/cohorts. It is not a causal savings estimate.

Coverage is **local Claude/Codex logs in the configured profile map and existing
mtime window**. A task starting before that scan window is marked
`lineage_possibly_truncated` and excluded from the denominator; increase `--days`
to cover it. There is no automatic cross-host or other-provider accounting.
List nonlocal sessions too: missing joins must remain incomplete until their usage
is available in the configured sources. Undiscovered remote/manual child sessions
cannot be inferred, so the manifest author must declare them. Outcome metadata is
not proof that the session list is exhaustive. Keep all audit/review/probe sessions
in the task tree and mark overhead instead of silently excluding them.

Only hashes, controlled enums, counters, booleans and timestamps are accepted;
unknown fields are rejected without echoing their content. Classes are
`infra-hooks|workflow|code|docs|research|operations|other`; cohorts are
`baseline|pre-token-efficiency-six|post-token-efficiency-six|compact-only|manual`.
Roles are `dux|implementer|review|gate|probe|release`. Optional session status is
`unknown|succeeded|failed`; outcome status is
`verified_complete|failed|abandoned|unknown`. Per-host activation and rollback
remain the existing collector install/LaunchAgent lifecycle.

## cswap — Claude-profile rotation (2026-08-11)

`cswap.py` swaps `CLAUDE_CONFIG_DIR` across the seats mapped in `seat_map.json`
(A1/A2/A3/AZ + the orphan/legacy entries it flags) using `CLAUDE_CONFIG_DIR`. Lane-affine
per the harness-flotta dossier (`Desktop/harness-flotta-2026-08-09/2026-08-09-quattro-gruppi-e-continuita.md`
§1): A1 interactive/architect · A2 subagents/build · A3 cron/batch (donor) · AZ =
the Team Premium gate-primary seat and this M5's default `~/.claude`.

### Commands

```bash
python3 scripts/usage/cswap.py list                          # seats + fingerprint identity + 5h/7d consumption
python3 scripts/usage/cswap.py fingerprint                    # ARM: claude auth status per profile -> LOCAL fingerprints.json only
python3 scripts/usage/cswap.py run A2 -- claude -p "..."       # exec under A2's CLAUDE_CONFIG_DIR (default cmd: interactive `claude`)
python3 scripts/usage/cswap.py auto --print                   # pick least-loaded eligible seat, print its dir only
python3 scripts/usage/cswap.py auto --activate                # same, and remember the choice (hysteresis state)
python3 scripts/usage/cswap.py auto --print --exclude A3       # rank excluding A3 for this run
```

Composable, interactive:

```bash
CLAUDE_CONFIG_DIR=$(python3 scripts/usage/cswap.py auto --print) claude
```

### Honesty constraint (W106 — the proxy lies if you let it)

Anthropic exposes **no API for a seat's remaining 5h/7d quota**. Every number
`cswap` prints or ranks by is **local consumption already spent**, parsed from
`~/.claude*/projects/**/*.jsonl` by reusing `seat_usage_collector.collect_claude()`
— never remaining headroom. Two concrete limits, stated rather than hidden:

- A seat driven from **another machine** (Pro/Mini) looks idle here — `cswap`
  only ever sees this machine's local transcripts.
- The "5h"/"7d" windows are **not** an audited rolling-window sum: the
  collector gates by transcript **file mtime**, not by each JSONL line's own
  timestamp, so a file touched inside the window contributes ALL of its
  lines, including ones written before the window started. Read both numbers
  as "how much recent activity has accumulated", not as a precise interval
  total.

`cswap auto`'s 90%-of-observed-max threshold is therefore a proxy for "this
seat looks closer to its ceiling than the others", not a measurement of an
actual ceiling — there is no ceiling to measure.

### `auto`'s decision (rank + hysteresis + anti-collision)

1. Rank eligible seats (mapped, dir exists, not orphan/legacy, not `--exclude`d)
   ascending by 5h consumption, tie-break 7d — the least-loaded seat wins by default.
2. **Keep** the currently-active seat (state in `~/.config/cswap/state.json`) if
   EITHER holds: its 5h consumption is under 90% of the max observed among
   candidates, OR the last switch was under 30 minutes ago (anti flip-flop).
   Only when both fail does it actually rotate.
3. **Anti-collision**: an `mkdir`-atomic lock at `~/.config/cswap/auto.lock`
   (same primitive as `scripts/prepush_suite_lock.sh` — POSIX-atomic, no
   TOCTOU), with stale-holder reclaim via `kill -0`. Unlike that wrapper this
   is a **single-attempt trylock**, not a poll loop: a held lock means
   another rotation decision is in flight right now, so `cswap auto` exits
   `75` (EX_TEMPFAIL) immediately with an actionable message rather than
   silently waiting or silently picking a stale verdict.

No symlinks in `$HOME`, no shell-rc edits (cicatrix-superscar.md family #1,
HOME-fork drift) — all state lives under `~/.config/cswap/`.

### Relationship to `claude-cascade.sh`

`cswap` is the **interactive/on-demand** rotation tool (a human or an
on-demand session picking/forcing a seat). It does **not** replace
`scripts/claude-cascade.sh`, which remains the **cron-side** rotation
(quota-exhaust fallback across the numbered `CLAUDE_CODE_OAUTH_TOKEN_1/2/3`
tokens for headless/cron callers). The two solve different problems on
different call paths — don't collapse one into the other.

### Arming (per machine)

```bash
python3 scripts/usage/cswap.py fingerprint   # writes identities to ~/.config/cswap/fingerprints.json (LOCAL, 0600, never committed)
python3 scripts/usage/cswap.py list          # verify identities + dirs before relying on `auto`
```

`seat_map.json` is tracked in the **public** `Bali-Zero/Teman2` repo and
carries ONLY profile-dir → seat-id mapping — `fingerprint` never writes an
identity (a real personal email) there. It also never writes a
token/secret-shaped string into the local fingerprints file either, even on
the raw-first-line fallback path (defensive redaction, tested in
`scripts/usage/test_cswap.py`) — cicatrix-superscar.md family #4, secret in
the clear.

Tests: `python3 -m pytest scripts/usage/test_cswap.py -q` — fully isolated
from the real `$HOME` (W96), guilt+innocence corpus for the lock, the
hysteresis, the orphan/legacy exclusion, seat resolution, and the redaction
guard.
