# ChatGPT Business marketing bridge

## Purpose

Connect the private Bali Zero ChatGPT workspace to a dedicated Nuzantara
marketing MCP surface through OpenAI Secure MCP Tunnel. The Pro makes an
outbound HTTPS connection; there is no public MCP URL and no inbound firewall
port.

This bridge is not the full Nuzantara MCP server. It creates a fresh FastMCP
instance with an exact allowlist:

- public-intended News Room review plus the guarded update, cover, publish, and
  live-verification contract;
- sanitized WR2 human-review queue reads;
- a confirmed, idempotent SOL 5.6 strategy selection that returns only closed,
  enumerated creative codes for human development in WR2 Control;
- guarded WR2 re-render requests plus allowlisted Google Drive delivery;
- sanitized FlowKit health, prompt-to-image/video generation, durable status,
  and allowlisted Google media delivery;
- no social publication action.

The following domains are not exposed: CRM, client records,
documents, raw OSINT, admin, arbitrary filesystem paths, email, WhatsApp,
federation, and social publishing.

## Owner-only prerequisites

1. Provision one random dedicated News Room projection key. Store the same
   value as `WORKSPACE_MARKETING_API_KEY` in Fly and as
   `NUZANTARA_WORKSPACE_MARKETING_API_KEY` in the Pro-only
   `~/.nuzantara-secrets.env`. This key is accepted only by the two GET
   projections under `/api/workspace-marketing/news/*`; never add it to
   `API_KEYS`. Provisioning and the backend deployment follow the normal PR/CI
   gate. Keep the value out of this document, chat, and shell history.
2. Open <https://platform.openai.com/settings/organization/tunnels> in the
   intended Platform organization.
3. Create a tunnel named `nuzantara-marketing-pro` and associate it with the
   Bali Zero ChatGPT workspace. The operator needs Tunnels **Read + Manage**;
   the runtime principal needs only Tunnels **Read + Use**.
4. Create a dedicated runtime API key for that principal. Do not use an admin
   key, an existing embedding key, or a key from another service.
5. Keep the `tunnel_id` and runtime key off chat, tickets, shell history, and
   the repository.

If the Tunnels page reports that access is required or cannot associate the
workspace, stop there. Grant the documented organization/workspace permissions
or contact the OpenAI account team. Do not fall back to ngrok, a public proxy,
or the full MCP server.

## Pro setup

The approved installer is:

```bash
ssh pro
cd /Users/nuzantara/nuzantara
bash scripts/setup_chatgpt_marketing_tunnel.sh --tunnel-id tunnel_...
```

The script asks for the runtime key with hidden terminal input, stores it in a
mode-0600 file outside the repository, creates/reuses a native tunnel-client
profile, starts the MCP child from an empty environment allowlist, and
supervises the runtime with `tunnel-client runtimes`. It ends by printing
machine-readable runtime status. Do not report success unless that status says
the process is running, healthy, and ready.

The initial runtime is read-only. After the app has passed discovery and read
tests, enable the bounded write surface with the explicit operator gate:

```bash
bash scripts/setup_chatgpt_marketing_tunnel.sh \
  --tunnel-id tunnel_... \
  --arm-writes
```

This does not allow social publication. News Room write actions remain bounded
by article completeness, cover, independent fact gate, explicit Damar request,
idempotency, and live HTTP verification. SOL cannot
execute the privileged WR2 writer, runs outside the repository, returns no
free-form model text, and is capped at four accepted jobs per UTC day with one
active job. A team member develops the returned strategy codes through governed
WR2 Control, which stops in human review. The private bridge can requeue an
existing pre-publication WR2 draft through the official renderer without the
force override, then return its allowlisted Drive delivery URL. Flow generation
is capped at six accepted requests per UTC day, pins project/tier server-side,
and accepts no paths. SOL, WR2 re-render, and Flow calls require a unique
request key and an explicit
`CONFIRM`, `CONFERMO`, or `SETUJU`; that string is a secondary intent marker,
not a cryptographic proof of who typed it. The real gates are the runtime
arming flag, the bounded non-publishing surface, and the visible approval step
whenever ChatGPT presents one for a tool marked destructive. Never leave the
write runtime armed for an unattended session; stop it or reconnect read-only
after the supervised production block.

Only public campaign subjects belong in these tools. Never enter client names,
phone numbers, email addresses, passport/identity numbers, case documents,
credentials, or local paths. Common identifiers are rejected/redacted, but the
boundary is the operating rule rather than an invitation to test the filter.

## ChatGPT workspace connection

While the managed runtime is healthy:

1. Open <https://chatgpt.com/plugins> in the Bali Zero workspace.
2. Create a developer-mode app named `Nuzantara Marketing Bridge`.
3. Choose **Tunnel** as the connection method and select or paste the tunnel
   id.
4. Review discovered tools. The exact expected count is 22. The only tool whose
   name contains `publish` must be `newsroom_publish`; any social-publish, CRM,
   client, document, admin, email, WhatsApp, upload, or arbitrary-path tool is a
   hard failure.
5. Restrict the app to the Bali Zero marketing group inside the workspace. All
   users who can access the app can request every exposed tool; do not enable
   public plugin distribution or workspace-wide access for non-marketing roles.
6. Restrict access to Damar's workspace identity `selamat@balizero.com`, attach
   the app to `Nuzantara — Bali Zero Desk` in Agent Studio, and update the
   agent. ChatGPT Business freezes the discovered tool snapshot when an app is
   approved; after this manifest changes, an owner/admin must recreate or
   republish the private app before Damar can see the new commands.

## Acceptance proof

Run these in order:

1. `workspace_health` reports the live News Room contract and writes disarmed.
2. `newsroom_list_pending(limit=1)` returns only the documented public fields.
3. `wr2_list_review_queue(limit=1)` returns no local path or Drive URL; only an
   explicit `wr2_get_delivery` call may return an allowlisted Drive URL.
4. A write call while disarmed fails before side effects.
5. Confirm that `wr2_request_rerender` rejects a published item and that a
   repeated request key cannot enqueue twice.
6. After explicit arming, run one SOL strategy-code job using public subject
   data. Confirm the result contains only enumerated codes and a reference.
7. Use one low-risk Flow image as the first credit-spending proof, confirm the
   same request key does not spend twice, then exercise
   `flow_generate_video_from_prompt` only after owner approval for the credits.
8. Use `flow_operation_status` and `flow_get_media` to confirm resumability and
   delivery without receiving encoded bytes or a non-Google URL.
9. Confirm no social post, email, WhatsApp, or client record was created.

## Operations and revocation

```bash
tunnel-client runtimes status nuzantara-marketing --json
tunnel-client doctor --profile nuzantara-marketing --explain
tunnel-client runtimes stop nuzantara-marketing
```

For emergency revocation, stop the runtime, revoke the dedicated runtime key in
Platform, and unlink the ChatGPT app. Removing the tunnel association blocks
workspace discovery without exposing the local server.

If `wr2_prepare_with_sol` reports that the active-job limit is reached after a
Pro reboot or forced process termination, treat the visible `queued` or
`running` record as potentially orphaned. Stop the tunnel runtime first and
verify that no `workspace_marketing_worker` process remains. An authorized Pro
operator may then change only that job record under
`~/.nuzantara/workspace-marketing/jobs/` to `status: failed`, `phase: stopped`,
and `error_kind: recovered_orphan`, using an atomic JSON replacement while
preserving the original request operation record. Restart read-only and run
`wr2_job_status` before re-arming. Never delete the whole state directory or
reuse the old request key; a new supervised attempt needs a new request key.

Never enable raw HTTP logging or payload capture in production. Tunnel
transport logs and app-level compliance logs are different boundaries; keep
both free of article bodies, prompts, identifiers, and secrets.

The Pro-only setup paths are intentional. Do not run this installer from
Air-M5 or Mini; those machines are not the tunnel runtime.
