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

| Symptom                                                   | Likely cause                                                                       | Fix                                                                                                                                                       |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `curl: (7) Failed to connect to 100.93.236.6 port 8990`   | Daemon not loaded OR Tailscale flap                                                | `launchctl print gui/$(id -u)/com.matagaruda.kg-query-api`; if not listed, `launchctl load …`. If listed, check `tail -50 ~/logs/mata-garuda-kg-api.err`. |
| `kg_path` is right but `entities_count: 0`                | Reading wrong DB (stale Pro snapshot)                                              | Verify Mini KG: `sqlite3 ~/.agent/mata-garuda/kg.db 'SELECT COUNT(*) FROM kg_entities'`. Confirm plist `MATA_GARUDA_REPO` points at the right repo.       |
| `schema_ok: false` in `/health`                           | KG DB corrupt or migration in flight                                               | Don't restart blindly; check `kg_linker.py` log to see if a writer is mid-batch.                                                                          |
| MCP tool returns `{"error": "kg_unavailable"}` repeatedly | Tailscale data-plane down (NordVPN trap, see `lessons_nordvpn_tailscale_block.md`) | `tailscale ping mini-pro2`. If DERP-only, disconnect NordVPN.                                                                                             |
| MCP tool raises `MCPAccessDenied`                         | `AGENT_ROLE` env not set or set to non-admin                                       | Inspect with `env \| grep AGENT_ROLE`. The OpenClaw wrapper sets it; direct stdio sessions need to set it explicitly.                                     |
| Plist mode is `0644` after edit                           | Forgot to restore `0444` per cicatrix hardening                                    | `chmod 0444 ~/Library/LaunchAgents/com.matagaruda.kg-query-api.plist`.                                                                                    |

## Latency benchmark result

Captured 2026-05-07 from Pro → Mini via Tailscale (100 calls, `/kg/search?q=imigrasi`):

```
target  : http://100.93.236.6:8990/kg/search?q=imigrasi
samples : 100/100 (errors=0)
p50_ms  : 22.5
p95_ms  : 25.7
p99_ms  : 30.3
min_ms  : 19.0
max_ms  : 40.0
```

**Pass:** p99 = 30.3 ms, 26× under the 800 ms spec threshold.

Note: measured while Tailscale was routed via DERP USA relay per the Pro
ssh.config patch; the p50 around 22 ms suggests Tailscale promoted the
data-plane to direct peer-to-peer (DERP-relay RTT was ~62 ms). Once
Mini moves back to the same router as Pro for LAN-direct, expect
single-digit-ms p99. Either way the 800 ms budget is comfortable.

## Tri-LLM review

Captured 2026-05-07 pre-merge. Threshold ≥2/3 approvals (per Wave-2 Pro
2026-04-29 capacity-exhaustion pattern); NotebookLM NB-1 MCP not exposed in
this session; Gemini opportunistic, skipped because the 2/3 threshold was
already met by DeepSeek + Codex.

### DeepSeek-V4-flash: APPROVE-WITH-NITS

```
SPOF: stale _client after Tailscale flap; the singleton is never reset,
its connection pool may hold dead connections. (Mitigated partially by
the `if _client is None or _client.is_closed` check in _get_client.)

LEAK: error path returns "kg_path" in 503 (/health), revealing
$HOME prefix. Low-severity (Tailscale-gated, mata-garuda audit logs
already include the path).

RACE: _get_client() singleton race on first call. asyncio cooperative
concurrency makes this a paper risk in single-process; pytest-xdist
spawns separate worker processes so test isolation is fine.

ONE-IMPROVEMENT: connection-pool health check before each call.
Rejected by maintainer — would halve throughput; the graceful-
degradation path already handles flap.

VERDICT: APPROVE-WITH-NITS
```

(Captured `/tmp/w2-deepseek-review.txt`, model `deepseek-v4-flash`,
input_tokens=11953 output_tokens=924, ~$0.01 charge against the existing
DEEPSEEK_API_KEY budget — within the article_composer pattern Zero
already accepts.)

### Codex (sandbox read-only): APPROVE-WITH-NITS

```
UNHANDLED: kg_intel.py covers ConnectError/Timeout/ReadError/
RemoteProtocolError + the new httpx.RequestError safety net. For a
literal "NEVER raises" contract, a final `except Exception` would
catch asyncio loop misuse and bad-config exceptions. Maintainer
deferred — bare `except Exception` would also mask CancelledError,
defeating the cooperative-cancellation contract.

TEST-SEAM: _TRANSPORT_OVERRIDE is process-local, pytest-xdist spawns
worker processes so cross-worker races are impossible. In-process
serial tests work because the fixture resets _client = None.

TCC: plist documents the bypass and execs venv python directly. No
shell wrapper is a positive. Long-term audit-hostile because it
relies on interpreter identity for Desktop access; if mata-garuda
ever moves out of ~/Desktop, the trick goes away naturally.

VERDICT: APPROVE-WITH-NITS
```

(Captured `/tmp/w2-codex-review.txt`, ChatGPT Plus subscription, no
incremental cost.)

### Gemini 3.1 Pro: opportunistic-skipped

The 2/3 threshold was met before invoking Gemini. Skipped to conserve
quota per the Wave-2 Pro capacity-exhaustion pattern. Re-runnable if a
future change wants the third axis.

### Deferred nits (tracked, not blocking)

- `_handle_health` 503 echoes `kg_path` (DeepSeek LEAK #1). Will mask
  to basename in a follow-up PR; operator diagnostic is preserved.
- `_safe_get` final `except Exception` (Codex UNHANDLED). Deferred
  because bare except would mask `asyncio.CancelledError`.
