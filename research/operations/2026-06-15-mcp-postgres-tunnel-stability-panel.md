# MCP Postgres tunnel stability — 4-LLM panel + empirical (2026-06-15, M5)

## Problem
postgres-nuzantara MCP → localhost:15432 → `fly proxy` wireguard M5→Fly `sin`. MCP failing
-32603 (tunnel down). Nobody keeps the proxy alive; and the proxy itself was measured flaky.

## Empirical findings (verified on disk, not assumed)
- Fly app healthy (primary+replica, checks pass).
- BEFORE `fly wg reset`: 6 heartbeats `SELECT 1` over open proxy → **OK=2/6 (~33%)**.
  Socket LISTEN but end-to-end SELECT timeout = "zombie tunnel" (superscar #8 worst form).
- ROOT CAUSE: stale WireGuard peer (M5 roaming IP destabilizes UDP wireguard — confirmed by
  Fly community + web research "WireGuard UDP destabilizes under roaming IP").
- AFTER `fly wg reset personal`: **6/6, then 10/10 over ~100s = 100%**. The flakiness was the
  stale peer, NOT permanent network.
- `nuzantara_dev` local snapshot DB **does NOT exist** and NO snapshot on disk (runbook claimed
  otherwise — false; verified `psql -d nuzantara_dev` → does not exist).

## Panel verdict (Gemini 3.1 Pro + DeepSeek V4 Pro + GPT-5.5, independent dispatch)
CONVERGENCE on:
1. **Local-snapshot-as-default is a TRAP for "what is true NOW" questions** (CRM status, newly
   added/removed team member, compliance/deletion checks). Fine only for "what exists structurally".
2. **Best option = live via Pro** (Pro has stable Fly net): SSH local-forward
   `ssh -L 15432:localhost:15432 pro` (+autossh) OR proxy-on-Pro over Tailscale. Live, $0,
   NO PII on M5 disk, no `fly` binary needed on M5.
3. Gemini: **snapshot on M5 = Law 2 / UU PDP risk** (replicates PII/OSINT to workstation).
4. Codex flaw: **"add scheduled refresh" is underspecified — if refresh uses the same flaky
   tunnel, you move flakiness from query-time to refresh-time, more silently.**
5. If snapshot used at all: expose `source/refreshed_at/age/refresh_status`; **fail closed past
   TTL** (roster 24h, CRM 4h → STALE_BLOCK). Never silent fallback live→snapshot.

## DECISION (synthesis — gated by the wg-reset empirical result)
The `wg reset` → 100% result reframes everything: the tunnel CAN be stable from M5 once the
peer is fresh. So the chosen design is:

- **Primary: keep MCP LIVE on localhost:15432, kept alive by a supervisor LaunchAgent**
  (`scripts/fly_pg_tunnel_supervisor.sh`) whose heartbeat is end-to-end `SELECT 1` and which,
  on sustained heartbeat failure, runs `fly wg reset` BEFORE respawning the proxy — auto-curing
  the actual root cause. "Stable for ever" with NO snapshot/PII risk and NO Pro dependency.
- Snapshot-as-default REJECTED (PII + staleness trap). Pro-forward kept as documented fallback
  if M5 wireguard ever proves unrecoverable.

## Why this beats the original "point MCP at local snapshot"
The original proposal assumed the tunnel was unfixable. It is fixable (wg reset). Live data with
a self-healing supervisor dominates a stale PII-bearing snapshot on every axis the panel raised.
