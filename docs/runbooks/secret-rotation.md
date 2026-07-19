# Runbook: Secret Rotation & Fleet Propagation

> Born from scar 2026-07-18 (Kimi S2): a rotated `NUZANTARA_API_KEY` lived only in
> Pro's `~/.nuzantara-secrets.env`; every `.mcp.json` in the fleet kept an inline
> stale copy that shadowed the good one (env > file fallback in
> `nuzantara_mcp/server.py:_secret_from_env_file`). Two days of silent 401s on
> memory/expiry endpoints. Mini had TWO dead variants. **Rule: a secret is rotated
> only when every consumer reads the NEW value — never when you changed one file.**

## The fleet's secret store (canonical)

Per-machine, `0600`: `~/.nuzantara-secrets.env` — flat `NAME=value` (optional
`export ` prefix). Readers: `nuzantara-mcp` (file fallback), cron wrappers,
sentinel/healer scripts. **This file is the single source of truth for
machine-local secrets.** Nothing else should carry the value:

- `.mcp.json` `env` blocks — FORBIDDEN for `NUZANTARA_API_KEY` (they shadow the
  file fallback). After the 2026-07-18/19 sweep: clean on M5, Pro, Mini.
- Launchd plist `EnvironmentVariables` — scar family W65 (world-readable).
- Any committed file — scar family W38/W65.

## Rotation procedure (atomic across the fleet)

1. **Generate** the new value where the issuer lives (e.g. Fly secrets for
   backend-validated keys: `fly secrets set API_KEYS=<new_csv> -a nuzantara-rag` —
   note: Fly restarts machines; pick a low-traffic window).
2. **Verify the new value works BEFORE touching local stores** (empirical, never
   assumed): `curl -s -o /dev/null -w '%{http_code}' -H "X-API-Key: <new>" https://nuzantara-rag.fly.dev/api/crm/expiry-alerts` → expect 200.
3. **Propagate to every machine's `~/.nuzantara-secrets.env`** — REPLACE, never
   append (a second `NAME=` line makes the last one win silently and confuses the
   next operator):
   ```bash
   # on each machine (pro / mini / m5), value never echoed to transcripts:
   grep -v '^NUZANTARA_API_KEY=' ~/.nuzantara-secrets.env > /tmp/s.env && \
     echo "NUZANTARA_API_KEY=<new>" >> /tmp/s.env && \
     mv /tmp/s.env ~/.nuzantara-secrets.env && chmod 600 ~/.nuzantara-secrets.env
   ```
4. **Sweep inline copies** (the shadow class): any `NUZANTARA_API_KEY` inside
   `.mcp.json` env blocks on all machines — delete the key so the file fallback
   engages. Check with hash parity, not eyeballs:
   ```bash
   # expected: identical sha256[:16] of the value on pro/mini/m5
   grep '^NUZANTARA_API_KEY=' ~/.nuzantara-secrets.env | tail -1 | cut -d= -f2 | shasum -a 256 | cut -c1-16
   ```
5. **Prove per machine** (content, never exit code): the 200-check from step 2
   run FROM that machine. MCP servers pick up the new value on next spawn —
   currently-running stdio servers keep the old env until the host respawns them
   (tell users to restart the agent session).
6. **Retire the old value** at the issuer (remove from `API_KEYS` csv) only AFTER
   step 5 passes on every machine.

## If you find a stale key (forensics)

Symptoms: `401 {"detail":"Authentication required"}` from authed MCP tools while
public endpoints (`/health`) answer 200. Diagnose in order:

1. Is the key empty? (`_secret_from_env_file` returns `""` → no auth headers at all)
2. Hash-compare the machine's value vs the live one (step 4) — different = stale.
3. Check BOTH shadow layers: `.mcp.json` inline env AND `~/.nuzantara-secrets.env`
   (Mini had two dead variants; the inline one won, both were dead).

## Non-negotiables

- Never print a secret value into a transcript/log; compare by `shasum -a 256 | cut -c1-16`.
- Never commit `~/.nuzantara-secrets.env` (it's machine-local, perms 0600).
- One issuer change → one propagation sweep → one verification pass. No partial rotations.
