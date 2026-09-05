# Arsenal Probe — seat liveness runbook

Date: 2026-07-06 · Spec: `docs/specs/arsenal-probe-v1.md` · Tool: `scripts/arsenal_probe.py`

## Why it exists

The multi-LLM quota cascade (claude → agy → codex → ollama, plus glm/deepseek council seats)
can silently thin to 2-deep: Codex OAuth dies with a quiet 401 `token_revoked`, agy is
GUI-keychain-bound (dead under sshd/launchd), GLM can 401/1211/529, DeepSeek runs out of balance
(402). Every one of these has ALREADY happened (superscar #2, Esiste≠Armato at the arsenal
level; audit 2026-05-24 found the cascade 2-deep with nobody noticing). A weekly empirical
health-ping was recommended 2026-05-24 and never armed — this tool is that arming, done heavier.

## What it does

One run live-probes every AI seat reachable from this machine (claude, glm, kimi, agy, codex,
deepseek, ollama, nlm — thread-parallel, per-seat timeouts) and classifies each by OUTPUT
CONTENT (never exit code alone) into: `LIVE · AUTH_DEAD · CONTEXT_AUTH · QUOTA_DEAD ·
BALANCE_DEAD · MODEL_ERR · SHED · TIMEOUT · CRED_UNAVAILABLE · NOT_INSTALLED · UNKNOWN_ERR`.

Outputs:

- `~/.organism/arsenal/last.json` (report; previous kept as `prev.json`; transitions computed)
- `~/.organism/last_seen/<machine>.arsenal_probe.json` (heartbeat sidecar, healer-compatible)
- stdout table (`--table`), full JSON (`--json`), or one line (`--quiet`)

Credential values are never printed, logged, or reported (scrub layer; scar #4).

## How it is armed (no 177th daemon — W84)

- **Mini (primary)**: the healer wrapper (`infra/healer/healer-run.sh`, 4h loop) refreshes the
  probe when the report is ≥20h old (≈1 live probe/day, preserving the healer's
  "healthy tick ≈ zero LLM cost" promise) and reads `transitions` EVERY tick: a NEW persistent
  death (AUTH/BALANCE/MODEL/UNKNOWN) → ACTIONABLE + direct Telegram to Zero.
- **Proprioception**: `arsenal_seats` wrap entry (`--read-last`, no live calls) DIVERGEs on
  persistent deaths in the last report; `guardian_freshness` flags the report stale >26h on Mini.
- **On demand, any machine**: `python3 scripts/arsenal_probe.py --table` (M5/Pro give the
  GUI-context truth — agy/keychain seats can be LIVE here and CONTEXT_AUTH under sshd; both
  truths are real, per-context).

## Reading a report

- `CONTEXT_AUTH` / `CRED_UNAVAILABLE` / `NOT_INSTALLED` = host/context limitation, not seat
  death — the seat may be LIVE elsewhere. Never strict-fails.
- `QUOTA_DEAD` / `SHED` / `TIMEOUT` = transient; alarm-worthy only as trend.
- `AUTH_DEAD` / `BALANCE_DEAD` / `MODEL_ERR` = persistent and fixable — almost always
  operator-gated:

| Seat dead               | Cure (operator unless noted)                                                                                                                                                                                                                                                                                     |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| codex AUTH_DEAD         | interactive `codex login` on that machine                                                                                                                                                                                                                                                                        |
| codex BALANCE_DEAD      | top up ChatGPT Pro / Codex workspace credits (evidence: "Your workspace is out of credits. Add credits to continue.") — was misclassified `UNKNOWN_ERR` before 2026-08-31, see the note below                                                                                                                    |
| codex-spark MODEL_ERR   | `gpt-5.3-codex-spark` is rejected on this ChatGPT-account plan ("model is not supported when using Codex with a ChatGPT account") — verify the current model roster (`~/.codex/models_cache.json`) before pinning that slug again; was misclassified `UNKNOWN_ERR` before 2026-08-31                             |
| claude AUTH/QUOTA       | `claude auth status`; window cap → wait reset or switch slot                                                                                                                                                                                                                                                     |
| glm AUTH_DEAD           | re-copy token from a live keychain (see memory `discovery_glm_mini_seat_armed_fable_model_leak_2026_07_06`)                                                                                                                                                                                                      |
| glm MODEL_ERR           | config drift — launch from repo cwd or pin `--model glm-5.2` (fable-5[1m] leak)                                                                                                                                                                                                                                  |
| deepseek BALANCE_DEAD   | top-up at platform.deepseek.com                                                                                                                                                                                                                                                                                  |
| agy AUTH_DEAD (GUI ctx) | interactive `agy` login in a live session                                                                                                                                                                                                                                                                        |
| nlm AUTH_DEAD           | `nlm login` on Pro (recurs ~monthly)                                                                                                                                                                                                                                                                             |
| kimi AUTH_DEAD          | `kimi login` on that machine (device-code flow — authorize the printed URL/code from a kimi.com-logged browser; Allegro subscription, seat added 2026-07-19)                                                                                                                                                     |
| kimi BALANCE_DEAD       | verify/renew the Allegro membership at kimi.com — distinct from AUTH_DEAD: the device-code login itself succeeds, but the API replies "unable to verify your membership benefits ... ensure your membership is active" (a subscription-status check, not a token check, so `kimi login` alone will not clear it) |

Note (2026-08-13, healer tick): first live occurrence of `kimi BALANCE_DEAD` (evidence: "We're
unable to verify your membership benefits at this time. Please ensure your membership is active",
matched by the same generic `_BALANCE_DEAD_PAT` deepseek's `HTTP 402` hits) — added to the table
above since it previously only documented `kimi AUTH_DEAD`. Operator-gated; no code change.

Note (2026-08-05, healer tick): `claude` and `nlm`'s unauthenticated shapes ("Not logged in ·
Please run /login", "Run nlm login to re-authenticate") carry no 401/oauth-token marker, only
short prose — this table already promised `claude AUTH/QUOTA` and `nlm AUTH_DEAD` as the cure,
but the classifier fell through to a bare `UNKNOWN_ERR` for both (the same shape `kimi`'s "No
providers configured" already had a local override for). Matched locally per-seat now, mirroring
the existing `kimi` pattern — `scripts/tests/test_arsenal_probe.py` carries the guilt+innocence
pair for each.

Note (2026-08-31, healer tick, Mini): same disease, two more seats. `codex` ("Your workspace is
out of credits. Add credits to continue.") and `codex-spark` ("The 'gpt-5.3-codex-spark' model is
not supported when using Codex with a ChatGPT account.") both fell through to `UNKNOWN_ERR` —
`_BALANCE_DEAD_PAT`/`_MODEL_ERR_PAT` only matched `402`/`insufficient balance` and
`1211`/`unknown model`, not either observed phrase. Widened both patterns (`out of credits`,
`model is not supported`) with guilt+innocence pairs in `scripts/tests/test_arsenal_probe.py` and
canned entries in `_SELFTEST_CANNED`. Operator-gated either way (top up credits / verify the model
roster) — this only fixes which cure the board points at.

## Selftest / CI

`python3 scripts/arsenal_probe.py --selftest` — classifier table on canned provider outputs,
scrub check, blind-scan guard (0 seats probed → exit 2). CI: `scripts/tests/test_arsenal_probe.py`
in `immune-enforcement.yml` (offline, guilt+innocence per classifier).

## 2026-08-07 incident: the probe could hang forever and print zero bytes

`timeout 60 python3 scripts/arsenal_probe.py --table` produced **0 bytes on stdout+stderr** on
Pro, while every seat answered fine in an interactive shell seconds later. Root cause, found by
reproducing empirically (not guessed from the two leading hypotheses — codex-stdin and PATH
poverty — which turned out to be adjacent, real, but not the dominant cause):

- **agy's stdout pipe never closes.** agy's own process exits in ~1s, but a detached grandchild
  (likely a background/telemetry helper) inherits the stdout/stderr file descriptors without
  closing them. `subprocess.run()`'s `communicate()` waits for EOF on those pipes, which never
  comes — the probe ate its FULL per-seat timeout (verified live at 12s/15s/45s cutoffs; `PONG`
  was already sitting in the partial stdout every single time). Since all seats probe
  concurrently in one `ThreadPoolExecutor` and nothing prints until every future resolves, agy's
  old 120s timeout alone explained the reported hang under any outer wrapper shorter than that —
  the process was not stuck, it was faithfully waiting out a 120s budget nobody could see.
- Compounding: `claude`/`nlm`/`ollama`'s `resolve_bin()` fallback was wrong (claude) or absent
  (nlm, ollama), so a PATH-poor calling context (the SessionStart hook receptor, which reported
  `claude NOT_INSTALLED` the same day) reported false `NOT_INSTALLED` for genuinely-installed
  seats. Real, but not the hang's cause — a separate manifestation of the same "sensor measures
  its own environment, not the seat" disease (scar family #2, W108 lineage).

Fix (PR that introduced this section):

1. **Judge the reply, not the timeout** (scar W104) — every subprocess-backed probe now checks
   the partial stdout for a live signal (`PONG`, valid JSON, etc.) BEFORE accepting `TIMEOUT`. A
   seat whose process never cleanly exits but already answered is `LIVE`, full stop.
2. **Per-seat timeouts collapsed from 30-180s to ~15s** — safe specifically because of (1): even
   if a reply takes the full 15s to print, that's what gets judged, not whether the process later
   tore itself down cleanly.
3. **Fail-visible header**, printed and flushed to **stderr** before any probe fires
   (`arsenal_probe <ts> — probing N seat(s) on <machine>: ...`) — stderr so `--json`'s stdout
   stays machine-parseable. Zero bytes for 60s is now impossible by construction: something is on
   the wire before the first probe even starts.
4. **`stdin=subprocess.DEVNULL` is now the unconditional default** in `run_probe_cmd` (previously
   opt-in per call — only kimi/codex had it). No seat probe may ever inherit an open stdin.
5. **`resolve_bin()` gained `COMMON_BIN_DIRS` fallback** (`~/.local/bin`, `/opt/homebrew/bin`,
   `/usr/local/bin`, `~/.kimi-code/bin`) and now returns `(path, found_via_path)` — a binary found
   only through a fallback (not the process's own `$PATH`) gets a `[NOT_ON_PATH: ...]` evidence
   note instead of silently reading as a normal `LIVE`/`NOT_INSTALLED`, or worse, being missed
   entirely under a thin `$PATH`.
6. Final line always states **`N of M seats OK`** (`render_table` and `summary_line`) — never let
   a partial or all-dead run read as ambiguous about how many seats were actually probed.

Known NOT fixed here (reported to the ledger, out of scope for this diff):

- **glm can be genuinely LIVE but reported `UNKNOWN_ERR`.** `probe_glm`'s live-check is
  `'"model"' in ev` where `ev` is `evidence_tail(raw, ...)` — the LAST 160 chars of the response.
  A real glm PONG reply places the `"model"` field near the START of the JSON body (Anthropic
  message-shape: `id, type, role, model, content, stop_reason, stop_sequence, usage`), so it is
  routinely truncated away by the tail-slice before the live-check ever sees it. Observed live
  2026-08-07: a genuine `HTTP 200` reply classified `UNKNOWN_ERR`. Fixing this correctly needs the
  live-check to run against the untruncated (but still scrubbed) body, which means widening
  `http_post_json`'s return contract — deliberately left out of this diff to keep it scoped to the
  hang; tracked as a follow-up.
- The SessionStart hook receptor's own environment (separate from this script) is a different
  component — this diff does not touch anything under `~/.claude/hooks/` (control-plane,
  operator-only per repo convention). If it still shows stale/wrong seat statuses after this
  fix lands, that is a receptor-side issue (possibly reading a stale cached run, or a `--read-last`
  call against an old `last.json`), not this tool.
