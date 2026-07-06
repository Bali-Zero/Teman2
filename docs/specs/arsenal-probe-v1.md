# Arsenal Probe v1 — spec (DESIGN artifact, modus stage 2)

Date: 2026-07-06 · Author: Fable 5 (interactive) · Implementer: Sonnet 5 (worktree ops-arsenal-probe)
Mandate: Zero 2026-07-06 "sonda pesantemente" — the quota-cascade can silently degrade to 2-deep
(Codex 401 silent, agy keychain-bound, GLM 529/401, DeepSeek 402). Recommended since 2026-05-24,
never armed. This tool makes every AI seat's liveness EMPIRICAL, per-machine, per-context.

## What it is

`scripts/arsenal_probe.py` — a standalone, signal-only prober (never mutates anything outside
`~/.organism/`). One run = live-probe every AI seat reachable from THIS machine, classify each
into an honest taxonomy, write a JSON report + heartbeat sidecar, detect transitions vs the
previous run. Consumed by: healer wrapper (Mini, 4h), proprioception (freshness + verdict reader),
humans (`--table`).

## Seats & probe commands (each: subprocess, per-seat timeout, thread-parallel)

| seat | probe | LIVE signal |
|---|---|---|
| claude | `$ARSENAL_CLAUDE_BIN -p "Reply with exactly: PONG" --model claude-sonnet-5` (default bin `/opt/homebrew/bin/claude`; strip `ANTHROPIC_API_KEY` from env, pass through `CLAUDE_CODE_OAUTH_TOKEN` if set) | `PONG` in stdout |
| glm | token = `security find-generic-password -s glm-coding-plan-token -w` (NEVER logged); direct `curl` POST `https://api.z.ai/api/anthropic/v1/messages`, model `glm-5.2`, max_tokens 8, anthropic-version 2023-06-01 | HTTP 200 + `"model"` in body |
| agy | `agy -p "Reply with exactly: PONG"` (which-resolve; also try `~/.local/bin/agy`) | `PONG` in stdout |
| codex | `codex exec --sandbox read-only --skip-git-repo-check "Reply with exactly: PONG"` with stdin=DEVNULL (it blocks on open stdin) | `PONG` in stdout |
| deepseek | key = parse `DEEPSEEK_API_KEY=` from `~/.openclaw/workspace/.env.master` (read in-python, value NEVER logged); `curl` POST `https://api.deepseek.com/chat/completions` model `deepseek-v4-flash`, max_tokens 1 | HTTP 200 |
| ollama | `ollama list` → presence of `qwen3.5`; with `--live-gen` also 1-token `ollama run qwen3.5:9b` | model listed (or gen output) |
| nlm | `nlm list notebooks` (which-resolve) | stdout parses as JSON (list or dict) |

Timeouts (defaults, per-seat override via `--timeout SEC` global multiplier): claude 120s,
glm 45s, agy 120s, codex 180s, deepseek 45s, ollama 30s (live-gen 120s), nlm 60s.

## Status taxonomy (the heart — classify by OUTPUT CONTENT, never exit code alone; scar #2)

- `LIVE` — the live signal observed.
- `AUTH_DEAD` — output matches `401|Authentication Failed|token_revoked|refresh_token_reused|OAuth token|authentication failed` (codex/glm/claude/nlm auth class). For agy: only when NOT in an ssh context.
- `CONTEXT_AUTH` — agy-style GUI-keychain failure while `SSH_CONNECTION`/`SSH_TTY` env present or no GUI session: the seat is dead IN THIS CONTEXT, possibly alive in GUI. Distinct because the cure differs (context, not credential).
- `QUOTA_DEAD` — `out of extra usage|usage limit|quota|429|rate.limit|exhausted`.
- `BALANCE_DEAD` — HTTP 402 / `Insufficient Balance` (deepseek class).
- `MODEL_ERR` — `1211|Unknown Model` (glm class — config drift, e.g. the fable-5[1m] leak).
- `SHED` — HTTP 529 / `overloaded` (provider-side transient load-shedding).
- `TIMEOUT` — probe hit its per-seat timeout.
- `CRED_UNAVAILABLE` — credential source absent/locked on this host (keychain locked → `security` exit 36/25300-class or empty in non-interactive; env.master missing; token file absent). NOT a seat death — a host limitation. Never strict-fails.
- `NOT_INSTALLED` — binary not found on PATH (nor known fallback paths). Never strict-fails.
- `UNKNOWN_ERR` — none of the above matched; evidence tail retained.

`healthy` bool = status == LIVE. `context_limited` = status in {CONTEXT_AUTH, CRED_UNAVAILABLE, NOT_INSTALLED}.
STRICT-FAIL set (persistent + fixable): {AUTH_DEAD, BALANCE_DEAD, MODEL_ERR, UNKNOWN_ERR}.
(QUOTA_DEAD/SHED/TIMEOUT are alarm-worthy transitions but transient — never exit-1.)

## Machine awareness

`machine_label()`: hostname → `m5` (Air-M5) / `pro` (Nuzantara) / `mini` (Mini-Pro2) / raw-lowercase.
Default seat selection = all 7; `--seats claude,glm,...` filters. REQUIRED map (used by `--strict`):
`mini: [claude, glm, codex, ollama]` · `pro: [claude, codex, deepseek, ollama, nlm]` ·
`m5: [claude, glm, agy, codex]` — a required seat in the STRICT-FAIL set → exit 1.
Non-required seats always probed and reported (unless filtered), just never fail the run.

## Outputs

1. Report `~/.organism/arsenal/last.json` (atomic write via tempfile+rename; keep previous as
   `prev.json` before overwrite):
```json
{"schema": 1, "machine": "mini", "ts": "2026-07-06T12:00:00Z",
 "context": {"ssh": true, "interactive": false},
 "seats": [{"seat": "glm", "status": "LIVE", "healthy": true, "latency_ms": 1240,
             "evidence": "HTTP 200 model glm-5.2", "required": true}],
 "transitions": [{"seat": "codex", "from": "LIVE", "to": "AUTH_DEAD"}],
 "summary": {"live": 5, "dead_strict": 1, "context_limited": 1, "transient": 0}}
```
2. Heartbeat `~/.organism/last_seen/<machine>.arsenal_probe.json` — same shape as healer's:
   `{"organ": "<machine>.arsenal_probe", "status": "ok|degraded", "note": "<summary line>", "ts": ...}`
   (`degraded` iff any strict-fail among required seats).
3. stdout: human table by default; `--json` full report; `--quiet` one summary line.

## Flags

`--seats CSV` · `--json` · `--table` (default) · `--quiet` · `--strict` · `--timeout MULT`
(float multiplier on all per-seat timeouts) · `--live-gen` (ollama real generate) ·
`--read-last` (NO probing: re-emit last.json as `{"findings": [seats not in ok-set]}` for the
proprioception wrap consumer; missing file → `{"findings": [{"seat": "(all)", "status": "NEVER_RAN"}]}`) ·
`--selftest` (see below).

## Redaction (scar #4 — non-negotiable)

Evidence tails (≤160 chars) pass through `scrub()`: replace `Bearer\s+\S+`, `sk-[A-Za-z0-9_-]{8,}`,
any 24+ char alnum/`._-` token, and the literal values of any env var whose NAME matches
`(TOKEN|KEY|PASSWORD|SECRET)` that the probe itself loaded, with `<REDACTED>`. Credential values
live only in locals, never in the report, never in exceptions (wrap curl calls so the
Authorization header never appears in error strings). `security`/env.master reads must not echo.

## Selftest (W84 blind-scan guard)

`--selftest`: (a) classifier table — canned output samples per status (the real strings above:
z.ai 1211 body, 529 body, codex token_revoked line, agy auth-failed line, deepseek 402, quota
strings) each classify correctly; (b) scrub() removes a planted fake token; (c) blind-scan guard:
a run that probed 0 seats must exit 2, never "clean"; (d) `--read-last` on a fixture file. Exit 0
only if all pass, print `SELFTEST OK — N checks`.

## Tests — `scripts/tests/test_arsenal_probe.py` (pytest, NO live network/LLM calls)

Monkeypatch subprocess/HTTP layers. Guilt AND innocence per classifier (e.g. `PONG` → LIVE never
AUTH_DEAD; `1211` → MODEL_ERR never SHED; agy auth-fail + SSH_CONNECTION set → CONTEXT_AUTH,
without ssh env → AUTH_DEAD). Transitions computed vs prev report. Strict exit semantics: required
AUTH_DEAD → 1; CRED_UNAVAILABLE → 0. Redaction: fake `Bearer abc...` and a 40-char token never
appear in report JSON. Atomic write leaves prev.json. `--read-last` fixtures (ok-set filtering,
NEVER_RAN). Blind-scan exit 2. Aim ~20-30 focused tests. Style: mirror existing
`scripts/tests/test_pending_arms_report.py` conventions (tmp_path, capsys).

## Explicitly OUT of scope for the implementer (Fable does these after, funnel-in)

- Edits to `scripts/proprioception.py` (guardian_freshness item + wrap registry entry)
- Edits to `infra/healer/healer-run.sh` (receptor 4: run probe + transitions→ACTIONABLE + Telegram line)
- `.github/workflows/immune-enforcement.yml` test wiring
- `docs/runbooks/arsenal-probe.md`
- PENDING-ARMS arming lines

## Style contract

Python 3.11 stdlib-only (subprocess, json, concurrent.futures, urllib.request for HTTP — no
requests dep), full type hints, logger-style stderr prints OK for a CLI tool, module docstring
with the one-line mission + scar references (#2 Esiste≠Armato, #4 secrets, W84 blind-scan).
Match the voice of `scripts/proprioception.py` (concise comments explaining WHY, not what).
