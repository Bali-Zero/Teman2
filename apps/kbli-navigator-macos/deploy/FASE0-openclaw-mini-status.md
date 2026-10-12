# FASE 0 — OpenClaw zantara-kbli on Mini (status 2026-06-23)

Goal: arm a single Zantara-KBLI chat brain on Mini-Pro2 (GPT-5.5 via OpenClaw `agent --json`).

## Done (idempotent, re-runnable)

- `arm-openclaw-zantara-kbli.py` — fixes 2 config errors (removed `openai-codex.contextTokens`,
  `telegram.streaming` {mode:off}→"off"), creates agent `zantara-kbli` (gpt-5.5 primary, cloned
  from `coder`, workspace `~/.openclaw/workspace-zantara-kbli`). `openclaw config validate` → VALID.
- `zantara-kbli-IDENTITY.md` → installed at `~/.openclaw/workspace-zantara-kbli/IDENTITY.md`.
  NLM-style grounding (answer only from injected FONTI, never invent a code/status) + GPT fluency.
- Proof-of-life: `openclaw agent --agent zantara-kbli --local --json` returns clean text. The
  grounding WORKS: with no FONTI injected, Zantara REFUSES to invent ("non invento mai codici o
  stati senza i dati corretti"). Reply text lives at `result.output[].text` (NOT
  `finalAssistantVisibleText` — that's the WhatsApp-bridge gateway shape). JSON is emitted on
  STDERR (banners precede it; first `{` at line 45). OpenClawRunner must read stderr + slice from
  first `{`.

## OPERATOR-GATED (cannot self-fix — scar: codex OAuth token_invalidated)

- GPT-5.5 (`openai-codex`) skips with `reason=auth` (401 token_invalidated). It falls through to
  OpenRouter/DeepSeek fallbacks (no keys) → currently answered by a local fallback model.
- **To get real GPT-5.5**: on Mini, interactive `codex login` (OAuth flow — operator only).
- Optional: start the OpenClaw gateway H24 (LaunchAgent) so `--local` failover isn't needed.

The app (Task 6) is built against the contract `openclaw agent --agent zantara-kbli --json` →
reply text. It works today via the local fallback; it becomes true GPT-5.5 the moment `codex login`
is refreshed. No app change needed.
