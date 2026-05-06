# SYMBIOSIS W2 — KG Bridge A Operational Runbook

Bridge A: mata-garuda KG SQLite (Mini, `~/.agent/mata-garuda/kg.db`) exposed as
Pro-side MCP tool via Tailscale. Three tools:
`kg_intel_search`, `kg_intel_entity`, `kg_intel_health`. Admin-gated.

Spec: [`docs/superpowers/specs/2026-05-07-symbiosis-w2-kg-mcp-bridge-design.md`](../superpowers/specs/2026-05-07-symbiosis-w2-kg-mcp-bridge-design.md).
Plan: [`docs/superpowers/plans/2026-05-07-symbiosis-w2-kg-mcp-bridge.md`](../superpowers/plans/2026-05-07-symbiosis-w2-kg-mcp-bridge.md).

## Topology

```
Pro (Claude Code stdio)
  └─ apps/nuzantara-mcp        kg_intel_{search,entity,health}
       └─ httpx.AsyncClient    base_url=http://100.93.236.6:8990 (Tailscale)
                                ↓
Mini (Tailscale 100.93.236.6, mDNS mini-pro2.local)
  └─ launchd com.matagaruda.kg-query-api
       └─ /Users/nuzantara/.../scripts/mata-garuda-kg-api.sh
            └─ python -m mata_garuda.api.kg_query
                 └─ stdlib http.server, bind 100.93.236.6:8990
                 └─ SQLite read-only on ~/.agent/mata-garuda/kg.db
```

## Install on Mini (one-time)

```bash
ssh nuzantara@100.93.236.6
cd ~/Desktop/nuzantara
git pull origin main

# Logs dir
mkdir -p ~/logs

# Plist (mode 0444 per cicatrix STRUCTURAL plist-tampering hardening)
install -m 0444 infra/launchagents/com.matagaruda.kg-query-api.plist \
  ~/Library/LaunchAgents/

# Load
launchctl load ~/Library/LaunchAgents/com.matagaruda.kg-query-api.plist
launchctl print gui/$(id -u)/com.matagaruda.kg-query-api | head -30
```

Verify daemon up (after ~2s warmup):

```bash
curl -fsS http://100.93.236.6:8990/health | python3 -m json.tool
```

Expected: `{"ok": true, "entities_count": 409, ...}` (counts depend on KG state).

## Verify from Pro

```bash
curl -fsS http://100.93.236.6:8990/health | python3 -m json.tool
curl -fsS "http://100.93.236.6:8990/kg/search?q=imigrasi&limit=5" | python3 -m json.tool
curl -fsS "http://100.93.236.6:8990/kg/entity/$(python3 -c 'import urllib.parse;print(urllib.parse.quote("Direktorat Jenderal Imigrasi"))')?type=organizations" | python3 -m json.tool
```

## Use the MCP tool

From Claude Code (with `nuzantara-mcp` stdio attached):

```text
kg_intel_health()
kg_intel_search("imigrasi", 10)
kg_intel_entity("Direktorat Jenderal Imigrasi", "organizations")
```

`AGENT_ROLE=admin` must be set in the env that launches `nuzantara-mcp`
(default for Pro Claude Code sessions; the OpenClaw wrapper enforces the same
mapping per `apps/team-agent/mcp-wrapper/config/roles.yaml`).

## Logs

- `~/logs/mata-garuda-kg-api.log` — stdout (request audit: status + path + duration)
- `~/logs/mata-garuda-kg-api.err` — stderr (startup failures)

The audit line shape is `<ip> - <BaseHTTPRequestHandler default format>` —
**never** the request body (per OSINT-blindato §1.4).

## Restart / Reload

```bash
# Restart with cached config
launchctl kickstart -k gui/$(id -u)/com.matagaruda.kg-query-api

# Reload after plist edit
chmod u+w ~/Library/LaunchAgents/com.matagaruda.kg-query-api.plist  # cicatrix step
# ... edit ...
chmod 0444 ~/Library/LaunchAgents/com.matagaruda.kg-query-api.plist
launchctl bootout gui/$(id -u)/com.matagaruda.kg-query-api
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.matagaruda.kg-query-api.plist
```

## Latency benchmark

From Pro:

```bash
python3 ~/Desktop/nuzantara/apps/mata-garuda/scripts/bench_kg_api.py \
  http://100.93.236.6:8990 100 "/kg/search?q=imigrasi" \
  | tee /tmp/kg-bench.txt
```

Pass threshold per spec §10: **p99 < 800 ms**.

## Rollback (Mini)

```bash
launchctl unload ~/Library/LaunchAgents/com.matagaruda.kg-query-api.plist
chmod u+w ~/Library/LaunchAgents/com.matagaruda.kg-query-api.plist
rm ~/Library/LaunchAgents/com.matagaruda.kg-query-api.plist
```

After rollback, the Pro-side MCP tool returns
`{"error": "kg_unavailable", ...}` on every call — no crash, no propagation.
To remove the tool entirely, revert the wiring commit on
`apps/nuzantara-mcp/nuzantara_mcp/server.py`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `curl: (7) Failed to connect to 100.93.236.6 port 8990` | Daemon not loaded OR Tailscale flap | `launchctl print gui/$(id -u)/com.matagaruda.kg-query-api`; if not listed, `launchctl load …`. If listed, check `tail -50 ~/logs/mata-garuda-kg-api.err`. |
| `kg_path` is right but `entities_count: 0` | Reading wrong DB (stale Pro snapshot) | Verify Mini KG: `sqlite3 ~/.agent/mata-garuda/kg.db 'SELECT COUNT(*) FROM kg_entities'`. Confirm plist `MATA_GARUDA_REPO` points at the right repo. |
| `schema_ok: false` in `/health` | KG DB corrupt or migration in flight | Don't restart blindly; check `kg_linker.py` log to see if a writer is mid-batch. |
| MCP tool returns `{"error": "kg_unavailable"}` repeatedly | Tailscale data-plane down (NordVPN trap, see `lessons_nordvpn_tailscale_block.md`) | `tailscale ping mini-pro2`. If DERP-only, disconnect NordVPN. |
| MCP tool raises `MCPAccessDenied` | `AGENT_ROLE` env not set or set to non-admin | Inspect with `env \| grep AGENT_ROLE`. The OpenClaw wrapper sets it; direct stdio sessions need to set it explicitly. |
| Plist mode is `0644` after edit | Forgot to restore `0444` per cicatrix hardening | `chmod 0444 ~/Library/LaunchAgents/com.matagaruda.kg-query-api.plist`. |

## Latency benchmark result

(Filled in at deploy time — Task 12.)

## Tri-LLM review

(Filled in at PR-prep time — Task 12.)
