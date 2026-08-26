---
date: 2026-08-27
domain: operations
client_case: none
sources:
  - "tailscale.com/pricing (fetched live 2026-08-27)"
  - "tailscale.com/docs — grants, access-control, grants-vs-acls"
  - "headscale.net + juanfont/headscale (GitHub) + HN production reports"
  - "local ground truth: memory reference_tailnet_topology.md (verified 2026-08-11) + live `tailscale status` on M5 2026-08-27"
  - "prior internal research: 2026-08-11-apple-vision-pro-tailnet-leverage.md, decision_two_iphones_tailnet_leverage_2026_08_03"
---

# Extending the balizero tailnet to all team members' computers — feasibility, benefits, risks, plan

**Mandate (Zero, 2026-08-27):** "associare alla nostra tailnet tutti i computer dei team members — deep research su come sfruttarla e i benefici per il team."

## 1. Ground truth (measured 2026-08-27 on M5)

- Tailnet `balizero` (`tail461666.ts.net`), owner `antonellosiano@gmail.com`, **Free plan**.
- 7 devices, ALL owned by Zero's accounts: M5, Pro, Mini, Vision Pro, 2 iPhones, 1 Android (`iqoo15`). **Zero team-member devices.** Subhi is console Admin but has no device enrolled.
- **ACL is the factory default**: one rule, every node → `0.0.0.0/0`, all ports. A node that joins today sees EVERYTHING.
- **Pro publishes a writable, unauthenticated shell to the whole tailnet** (`tailscale serve :443/term` → ttyd `-W zsh`, no `-c`), plus OpenClaw Control `/`, `/deck`, `/cinema`. Verified 2026-08-11: `GET /term` = 200 from another node.
- Tailscale SSH policy is maximally permissive (`"*":"=", "root":"root"`) but LATENT (no node runs the SSH server; one `tailscale up --ssh` arms it).
- No Tailscale API token anywhere on the fleet → every admin change is `operator[GUI]` in the console.

**Consequence:** the single hard precondition of this whole idea is **ACL first, machines after** (already a standing rule in `reference_tailnet_topology.md`). Enrolling a team laptop against today's policy hands that laptop a root-equivalent shell on Pro.

## 2. What the team gains (mapped to real Nuzantara assets, not generic VPN marketing)

| # | Benefit | Nuzantara asset it unlocks | Dev cost |
|---|---|---|---|
| 1 | **Client documents stop travelling on WhatsApp/email** — Taildrop or a tailnet-only upload page straight into the intake OCR pipeline | existing intake endpoint (per the 2026-08-03 iPhone research: Shortcut → `tailscale serve` → OCR) | near-zero |
| 2 | **Internal dashboards without public exposure** — intake review queue, ops boards, WR2 Control served tailnet-only instead of on public URLs behind auth | `tailscale serve` already in use on Pro | near-zero |
| 3 | **PII-safe AI for the team** — team laptops reach Ollama on Mini (qwen3.5, qwen2.5vl OCR) so client-doc processing stays on our metal (UU PDP / SYMBIOSIS Law 2) | Mini's Ollama arsenal | small (expose + ACL) |
| 4 | **Remote support** — Screen Sharing / SSH to a team member's Mac (with consent) instead of WhatsApp video-of-a-screen | macOS built-ins over tailnet | zero |
| 5 | **Stable office IP for government portals** — exit node on Mini (office, own ISP line) so DJP/OSS/Coretax sessions come from one known Indonesian IP even when staff work from home | Mini as exit node | zero (toggle + ACL) |
| 6 | **MagicDNS names** (`mini-pro2`, `nuzantara`) instead of IPs; no port-forwarding, no dynamic-DNS, works across any Wi-Fi/4G | built-in | zero |
| 7 | **Postgres/CRM tooling without public DB exposure** — read-only role reachable only from tagged devices | `nuzantara_readonly` role exists | ACL only |
| 8 | **Offboarding = one click** — remove the user in the console and every access dies at once (vs chasing shared passwords) | admin console | zero |

Security model is honest for UU PDP: data plane is peer-to-peer WireGuard, end-to-end encrypted; Tailscale's coordination server (US) sees only public keys + metadata, never file contents. That is a *better* story than client PDFs sitting on Meta's WhatsApp servers.

## 3. Risks (and the mitigation each one has)

1. **Default-allow ACL + Pro's `/term` shell** → write a deny-by-default grants policy BEFORE the first invite; kill or auth-gate `/term`. This is the blocker; everything else is secondary.
2. **BYOD / personal laptops bring their own malware** → `tag:team-device` reachable as DESTINATION-only for the few services they need; team devices must never be able to initiate to Zero's Macs beyond the allowed ports. Basic device posture is on all plans; MDM/EDR integrations need Standard+.
3. **Tailscale SSH policy is a loaded gun** → rewrite `sshUsers` before any expansion (drop `root`, restrict principals to Zero's devices).
4. **Key/identity hygiene** → keep default key expiry (180d) for team devices; disable expiry only on servers (Pro/Mini). Remove the stale `iphone-14-pro-max` entry.
5. **Plan/terms** → today's Free plan is the *Personal* tier (up to 6 users). A staff rollout is business use → **Standard $8/user/month** is the correct plan. Personal-free covers only a ≤6-user pilot.
6. **Not everyone needs it** → enrolling a front-desk browser-only workflow buys nothing; enroll by role, not by headcount.

## 4. Cost (verified on tailscale.com/pricing, 2026-08-27)

- **Personal: free, up to 6 users**, unlimited devices — enough for Zero + a 4-5 person pilot.
- **Standard: $8/user/month** — unlimited users, SCIM, roles, MDM/posture integrations. Full team (~14 users) ≈ **$112/mo ≈ $1,344/yr**.
- **Premium: $18/user/month** — adds network flow logs, log streaming, advanced SSH, JIT access. Only worth it if we want per-connection audit logs for UU PDP accountability.
- **Headscale (self-hosted control server, $0)** — maximal sovereignty (Law 6) but: no `serve`/`funnel` (Pro's current OpenClaw serve setup would break), no posture integrations, no web console, community-only support, single-tailnet. Verdict: **not now** — the ops burden lands on the same operator already running 176 daemons; revisit only if per-user cost ever hurts.

## 5. Recommended plan (phased)

- **Phase 0 — harden (operator[GUI] + one PR):** write grants policy in `infra/tailscale/` (deny-by-default; `group:team` → only named services; `tag:server` for Pro/Mini-facing bits), fix SSH policy, gate `/term`, purge stale nodes. *No invite before this lands.*
- **Phase 1 — pilot (free plan, ≤6 users):** Zero + 2-3 ops-heavy members (e.g. visa-docs intake, tax portals via exit node, onboarding docs). One concrete workflow each — doc-capture → intake OCR is the proven first pick.
- **Phase 2 — measure:** did WhatsApp doc-traffic drop? did anyone actually use the dashboards? 30 days.
- **Phase 3 — full team on Standard** ($8/u/mo) only if the pilot proves usage; enroll by role. SSO with `@balizero.com` Google Workspace identities; offboarding = console removal.

## 6. What NOT to do

- Do not invite anyone onto today's default-allow ACL (see §1).
- Do not use `funnel` for anything client/CRM/intake (public internet).
- Do not commit `tskey-*` auth keys to repo/memory (standing rule).
- Do not treat this as a compute grid: team laptops are access clients, not workers.
- Do not migrate the control plane to Headscale while Pro depends on `tailscale serve`.

## §Solo-operatore

- Writing the ACL/grants policy in the admin console (no API token on fleet → GUI), plan upgrade/billing, inviting users, on-device enrollment of team machines.

## Meta-pattern

The value of the idea is real but the tailnet's current shape is *single-operator trust* frozen into infrastructure (default ACL, unauthenticated serve endpoints, permissive SSH policy). Every expansion step is cheap EXCEPT the first one — converting implicit trust into explicit policy. Same famiglia as scar #2 (esiste≠armato): the tailnet "has" security features; none are armed.
