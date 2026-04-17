# OAuth Live Validation — Partial Results

**Session:** 2026-04-17 evening (Pro)
**Branch:** `main`
**Related commits:** `279df8cda` (chown fix), `ce880b1d4` (smoke script)

## TL;DR

- Chown fix from `279df8cda` is LIVE and verified (`ls -ld` inside container shows `nuzantara:nuzantara` on `/home/nuzantara`, `.claude`, `.local`)
- `claude` CLI 2.1.112 is installed and **answers** to prompts (e.g. `Pong! I'm ready to help...`)
- The CLI does **NOT close stdout after responding**. `asyncio.subprocess.communicate()` in `claude_oauth_client.py` therefore blocks until `timeout_s`, then kills the process. Every token attempt hits this → all 3 attempts time out → wrapper raises `ClaudeOAuthError`.
- End-to-end wrapper call (`complete_async`) currently unusable in container for this reason.

## Evidence

### Chown fix verified

```
drwx------ 4 nuzantara nuzantara 4096 Apr 17 16:07 /home/nuzantara
drwxr-xr-x 2 nuzantara nuzantara 4096 Apr 17 16:07 /home/nuzantara/.claude
drwxr-xr-x 5 nuzantara nuzantara 4096 Apr 17 15:52 /home/nuzantara/.local
/usr/bin/claude   (version 2.1.112)
```

### Direct CLI answers but doesn't exit

```bash
env CLAUDE_CODE_OAUTH_TOKEN=$CLAUDE_CODE_OAUTH_TOKEN_1 \
  timeout 30 claude -p --permission-mode bypassPermissions --model claude-haiku-4-5 ping
# Output:
#   Pong! I'm ready to help. What would you like to work on?
#   exit=124      ← bash timeout killed the still-running CLI
```

Token_1 length = 108 bytes, env var correctly injected. Response arrives quickly (<3s observed), but the process never exits → `timeout` must SIGKILL it.

### Python wrapper hangs

```
[enum] labels: ['token_1', 'token_2', 'token_3', 'keychain']
[enum] non-empty tokens: 3
<60s later: outer bash timeout 60 kills script before first attempt completes>
```

`complete_async` with `timeout_s=30` → 30s × 4 tokens = up to 120s worst case.

## Root cause (confirmed: non-TTY behavior)

**Local (Pro) `claude -p ... "prompt"`:** exit 0 in ~1s, clean. Same 2.1.112 CLI version as container.

**Container `claude -p ... "prompt"` test matrix:**

| Scenario                                               | Result                                              |
| ------------------------------------------------------ | --------------------------------------------------- |
| stdout→TTY (fly-ssh direct), stdin→TTY                 | "Pong!" + exit 124 (hangs after response)           |
| stdout→file, stdin→TTY                                 | silent + exit 124                                   |
| stdout→file, stdin→/dev/null                           | silent + exit 124                                   |
| `-d` debug + stdout→file + stdin→/dev/null             | silent + exit 124 (even debug output is suppressed) |
| wrapped in `script -qc` (pty allocation) + stdout→file | silent + exit 124                                   |

**Interpretation:**

1. Without TTY stdout, the CLI buffers and never flushes. Debug flag doesn't help.
2. Even with TTY stdout ("Pong!" case), the process keeps running after response — some background task keeps the event loop alive (token refresh? telemetry? keepalive?).
3. `stdin=DEVNULL` doesn't fix it.
4. Allocating a pty with `util-linux script` doesn't fix it either (likely because CLI checks both stdin and stdout for TTY independently).

**This is an upstream `@anthropic-ai/claude-code` issue** on Linux non-interactive use. The chown fix was necessary but not sufficient.

## Workaround options (for next session)

1. **Allocate pty from Python via `pty.openpty()`** and wire both stdin+stdout through it. Read until a delimiter pattern (e.g. end-of-line marker the CLI emits reliably). Send SIGKILL after capturing response. Complex, brittle.
2. **Wait for upstream fix.** File issue against `@anthropic-ai/claude-code` describing the non-TTY non-exit behavior on Linux containers.
3. **Accept permanent escape hatch for KG.** The other 3 call sites (`article_composer`, `coreference`, `multi_ai_adapter`) will time out for `timeout_s` seconds on call — not a crash, just slow failure. Acceptable if none are on hot paths.
4. **Keep OAuth for Pro (dev/cron) only, use Gemini on Fly.io.** Revert the Fly OAuth migration for the 4 call sites, leave keychain-based path working on Pro.

## Escape hatch status

- `KG_REASONING_PROVIDER=openai` staged on `nuzantara-rag`: **still active**, KG reasoning safely on OpenAI.
- `article_composer`, `coreference`, `multi_ai_adapter.ClaudeAdapter`: **NO fallback**. Any call in hot path will hang for `timeout_s` seconds then error. Do NOT remove the escape hatch before the CLI-exit problem is fixed.

## Deploy flakiness observed

- Deploy `24573903471` (chown fix commit `279df8cda`): `fly-deploy` reported FAILED due to release_command (migration apply-all) timing out at 5 minutes — but Fly promoted the new image to both machines anyway (v2929 complete right after v2928 failed). The chown layer made it to prod.
- 2 more deploys triggered mid-session by a parallel actor pushing visa-oracle fixes (`1c33a8bd5`, `2ed7c1e0e`). Machines cycled through v2930 / v2931.

## Recommendation

1. Do NOT push any more Dockerfile / claude_oauth_client changes until the CLI-exit behavior is fixed upstream or worked around in-wrapper.
2. **Keep `KG_REASONING_PROVIDER=openai` set permanently** on `nuzantara-rag` Fly app until OAuth in-container is functional.
3. Consider reverting the Fly-side migration for `article_composer`, `coreference`, `multi_ai_adapter` back to Gemini on Fly (keep OAuth only for Pro local dev). Rationale: Max plan cost savings are achieved only if OAuth actually runs; on Fly it's currently broken, so users see 30-120s wrapper timeouts instead.
4. To reproduce locally: build the container image, run it (not via fly), and invoke `claude -p` from inside. Same 2.1.112 binary + Linux kernel should reproduce the non-exit hang, enabling fast iteration without touching prod.

## Confirmed safe state

- `CLAUDE_CODE_OAUTH_TOKEN_{1,2,3}` injected (verified via `_collect_tokens()` enum)
- `KG_REASONING_PROVIDER=openai` active → KG LangGraph falls back to OpenAI on Fly
- `ANTHROPIC_API_KEY` NOT_SET (policy compliant — `memory/feedback_claude_oauth_only.md`)
- Chown fix in prod Dockerfile (commit `279df8cda`)
- Smoke test script committed (`ce880b1d4`) — runnable against Pro local; broken against Fly due to CLI issue described above
