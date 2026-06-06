# Spec — Guardrail Liveness Sentinel (v2, post 4-LLM panel)

**Date**: 2026-06-06
**Author**: Claude (Opus 4.8), autonomous, M5
**Status**: DRAFT v2 — panel-reviewed, pending Antonello approval + Pro re-verification
**Origin**: Reflection on Anthropic essay "When AI builds itself" (5 Jun 2026). Its single named
bottleneck for the most-likely future (Scenario 2): _"code review becomes the constraint as Claude
generates faster than humans verify."_ We have scars of the same shape — guardrail alive-on-paper,
dead-in-fact, found by luck. This spec makes guardrail decay **observable**.

> ⚠️ **Authoring caveat**: written on M5 while **Pro AND Mini were offline** (Tailscale: Pro
> last-seen 13 min, Mini 1 day — `[VERIFIED-M5]`). Live state of Pro tiers/scripts NOT inspectable.
> Facts tagged `[VERIFIED-M5]` (tool run this turn) or `[ASSUMED-MEMORY]` (re-verify on Pro first).

---

## 0. PANEL OUTCOME (4-LLM, 2026-06-06) — the spec was demolished, correctly

Panel ran 3 external reviewers + orchestrator. Honest cascade note: **DeepSeek first attempt
returned empty (my JSON-encoding bug, not the tier); Codex first attempt HUNG 30 min on a dead
Tavily-MCP OAuth token** — itself a live instance of "guardrail rotted silently." Both re-run
successfully (DeepSeek via urllib; Codex with `-c mcp_servers={}`). Effective panel: **4-deep**
(Gemini 3.1 Pro, DeepSeek V4 Pro, Codex GPT-5.5, Claude Opus). Gemini + Codex both did empirical
filesystem verification, not just text review.

**Two panel findings I independently re-verified on disk `[VERIFIED-M5]`:**

- **`stop_verify.py` is WIRED-BUT-DISABLED**: `settings.json:472` invokes it as
  `STOP_VERIFY_ALLOW_DIRTY=1 python3 ...`; `stop_verify.py:24-25` `sys.exit(0)` immediately under
  that env. My v1 "present + wired" check would have marked a dead guardrail alive. **This is the
  whole thesis proven against my own spec.**
- **The wheel already half-exists**: `scripts/sentinel_meta_watchdog.sh` +
  `infra/launchagents/com.nuzantara.sentinel-meta-watchdog.plist` + `docs/sentinel-watchdog.md`
  already solve "who watches the watcher" via **status-file freshness** (not presence) for
  `nuzantara-sentinel.py` (~58 jobs). There is also `supervisor-liveness-watchdog`. **reuse-first:
  this spec must EXTEND that infra, not build a parallel one.**

## 1. PIVOT (consequence of the panel)

v1 was "build a new weekly sentinel." v2 is: **add the 3 missing checks to the existing
`nuzantara-sentinel.py` + `sentinel_meta_watchdog.sh` stack**, applying liveness semantics
(behavior, not presence) and the panel's anti-silent-failure fixes.

## 2. The 3 checks (corrected)

### Check A — cascade tier liveness — by PER-TIER STATUS, not depth count

- Per-tier ping with **hard per-tier timeout** (`gtimeout`/perl-alarm; macOS has no `timeout`)
  [Codex #6, Gemini #3]. Capture **stderr too** (`2>&1`) — errors go to stderr, grepping stdout
  only reports false-alive [Gemini #7, DeepSeek #3].
- Regression key = **per-tier identity vector** `{T1:ok,T2:ok,T3:dead,T4:dead}`, NOT
  `cascade_depth=N` — a count hides "T1 died but T4 appeared" [Codex #4].
- Error detection must be **allowlist of success**, not denylist of known error strings — an
  unanticipated error (403, timeout) must NOT pass [DeepSeek #3, Codex].
- T3 codex: detect the Tavily-MCP-style hang explicitly; run health-pings with `-c mcp_servers={}`.
- T4 ollama: **`ollama list` FIRST**, never `ollama run` blind (auto-pulls ~5GB) [all 3 panels].
- Do NOT treat `regulatory-watcher-run.sh` as source-of-truth executable: it uses
  `set -euo pipefail` + bare tier commands → a nonzero tier exits the script before fallback
  [Codex #5]. Borrow its _patterns_ by reference, fix the `-e` bug if we touch it.

### Check B — guardrail liveness — BEHAVIOR, not presence+wiring

- "Present + wired" is insufficient (the `stop_verify` ALLOW_DIRTY counterexample). Each guardrail
  needs a **behavioral probe**: feed a known-bad input, assert it BLOCKS [Codex #7].
- Registry must enumerate **explicit required hosts** (`host=Pro`, `host=Mini`), never
  `host=any-claude-machine` — presence on M5 says nothing about Pro [Codex #9, DeepSeek #12].
- Registry must include the **destructive-MCP guardrail** (`guardrails-client.sh`,
  `settings.json:260`, CLAUDE.md:98) — v1 omitted a core safety mechanism [Codex #8].
- Registry-completeness gap: new guardrails added but not registered decay unnoticed. Mitigation:
  Check B also greps `settings.json` hooks for any command not in the registry → "unregistered
  guardrail" warning [DeepSeek #10].

### Check C — fleet reachability — must run OFF the watched host

- v1 fatal: scheduling Check C on Pro to detect "Pro unreachable" — if Pro is down the check is
  down too [Codex #2, both panels]. **Mutual heartbeat**: M5 ↔ Pro ↔ Mini each verify the others;
  the dead-man's-switch lives on a DIFFERENT machine [Codex #1, DeepSeek #2, Gemini #1].
- Concrete reachability threshold required (e.g. unreachable > 2 consecutive runs) [DeepSeek #8].
- SSH from launchd has no GUI keychain / `SSH_AUTH_SOCK` → key-with-passphrase fails as false
  "offline" [Gemini #4, DeepSeek #12]. Use a dedicated passphrase-less key or ssh-agent in plist.

## 3. Anti-silent-failure (the part the whole spec is ABOUT)

- **First-run / baseline-while-dead**: "alert only on regression" makes a born-dead guardrail
  normal forever. Fix: on first run OR any `dead` state, alert regardless of regression; only
  _steady-green_ is silent [Codex #3, DeepSeek #4/#5, Gemini #2].
- **State corruption**: unparseable JSON must fail LOUD, never default to "ok" (the reused pattern
  defaults to ok) [Codex #11, DeepSeek #15].
- **Telegram channel health**: missing creds / 400-on-HTML-escape must not set cooldown and must
  self-report via a second channel or log+exit-nonzero [Codex #10, Gemini #11, DeepSeek #9].
  Sanitize HTML special chars before `parse_mode=HTML` [Gemini #11].
- **Token in process list**: do NOT put the bot token in the curl URL (`ps aux` leak); use
  `-d` body or `--config`/netrc [Gemini #15].
- **Dead-man on the sentinel itself**: cannot be self-hosted [all]. Reuse the EXISTING
  `sentinel_meta_watchdog.sh` freshness mechanism — register this sentinel's status file with it.

## 4. launchd correctness [Gemini #9/#10, DeepSeek #13, Codex]

- Naming: `com.nuzantara.*` (workhorse user = `nuzantara`), NOT `com.balizero.*` [Gemini #14].
- launchd minimal PATH → set `EnvironmentVariables.PATH` explicitly (homebrew + `~/.local/bin`)
  or absolute-path every binary [Gemini #10].
- LaunchAgent needs GUI session; for headless survival prefer the existing daemon pattern.

## 5. Cost / privacy (corrected) [Codex #13]

- NOT "4 tokens/week" — CLI wrappers add system+context overhead. Still ~$0 (subscriptions).
- NOT "no PII": raw stderr/stdout can leak usernames, absolute paths, OAuth/account details,
  loaded project instructions. **Redact before any Telegram send.** Pings stay literal "ping".

## 6. Acceptance (expanded) [Codex #14]

- Behavioral: disable a guardrail via env (the ALLOW_DIRTY case) → Check B reports DEAD.
- Born-dead: first run with a tier already down → alert fires (not silent baseline).
- Hung tier: inject a sleep → per-tier timeout trips, state still written, alert fires.
- Corrupt state file → loud failure, not silent "ok".
- Telegram creds removed → self-reports, does not set cooldown.
- Sentinel status stale > threshold → existing meta-watchdog fires (not a new mechanism).
- Steady all-green → NO alert.

## 7. Next steps (gated)

1. **Antonello approval** of this v2 direction (extend-not-build).
2. **Re-verify on Pro** every `[ASSUMED-MEMORY]` tag once Pro is back online (esp.
   `verify_mcp_integrity.sh` location, tier binaries, existing watchdog coverage).
3. Implement as extension to `nuzantara-sentinel.py` + register with `sentinel_meta_watchdog.sh`.
4. TDD per acceptance §6 before any LaunchAgent install.
