# Apple Vision Pro in the balizero tailnet — capability study & organization plan

- **Date**: 2026-08-11
- **Author**: Fable 5 session on Pro (interactive mandate from Zero: "analizza e studia le potenzialità, organizza come vuoi")
- **Status**: study + proposed pilots — pilots gated on Zero's pick (interactive)

## 1. Verified facts (probed this session, Pro)

| Fact | Evidence |
|---|---|
| New tailnet node `ipad-pro-11-gen-3` = `100.97.28.18`, OS "iOS", owner `antonellosiano@gmail.com` | `tailscale status` + `tailscale whois` 2026-08-11 |
| Node is ALIVE on home LAN | `tailscale ping` → pong via `192.168.0.17:41641` in ~1s |
| Tailnet-only HTTPS `https://nuzantara.tail461666.ts.net` → OpenClaw Control (node, `127.0.0.1:18789`) | `tailscale serve status` + `curl 127.0.0.1:18789` (title "OpenClaw Control") |
| Public Funnel `https://nuzantara.tail461666.ts.net:8443` → FastAPI on `127.0.0.1:8789` (root answers `{"detail":"Not Found"}`) | `tailscale funnel status` + curl. Pre-existing, unrelated to AVP — noted only |
| Tailscale runs on Apple Vision Pro (visionOS ≥1.0, iPad-class app) | App Store listing / tailscale GitHub FRs (links below) |

**Identity hypothesis (STRONG, unconfirmed on-device)**: the node is the **Apple Vision Pro**, not a physical iPad. Rationale: (a) Zero states the AVP joined the tailnet; (b) no iPad was ever in the fleet inventory; (c) iPad-compatibility apps on visionOS report an iPad Pro 11-inch device model, which matches the auto-generated hostname; (d) this very Claude session runs under `applevisionpro1987@gmail.com`, a dedicated AVP account. **10-second confirmation (operator)**: open the Tailscale app on the visor → the device name shown must match `ipad-pro-11-gen-3`. Until then, treat as hypothesis (cicatrix #6 discipline).

## 2. Hard boundaries (inherited from the 2026-08-03 iPhone study — visionOS is iOS-family; do not relitigate)

- Client-only node: **no daemon, no SSH server, no `tailscale serve`/`funnel` on the device**, background apps suspended (~30s).
- Not a compute node — it consumes tailnet services, never provides them.
- `funnel` never for client/CRM/intake data (public internet).
- Reference: memory `decision-two-iphones-tailnet-leverage-2026-08-03` (4-LLM convergent brainstorm). This study reuses that ground and covers only what is **unique to the visor** — no new council convened (anti-sperpero: overlapping priors would rubber-stamp).

## 3. What is UNIQUE to the Vision Pro (vs the two iPhones already studied)

1. **Spatial ops deck (P0 — works TODAY, zero dev).** Safari windows pinned in space at wall size. Already reachable from the visor: `https://nuzantara.tail461666.ts.net` (OpenClaw Control, tailnet-only), plus the public surfaces (kita/my/prime/zantara.balizero.com). The visor turns the existing web surfaces into a multi-panel control room — the one thing no other device in the fleet can do.
2. **Full dev cockpit in Safari (P2 — ~30-60 min).** `ttyd` (terminal) and/or `code-server` (VS Code) on Mini (H24), bound via `tailscale serve` **tailnet-only** → real `claude` CLI + shell in the visor from anywhere. No App Store dependency. Guard: basic-auth on top of tailnet identity; NEVER funnel; secrets stay on the Mac.
3. **Remote macOS control (P3 — operator-gated).** macOS Screen Sharing on Pro/Mini + a visionOS VNC client (e.g. Screens) over Tailscale = full Mac desktop in the visor from anywhere. Note: Apple's native "Mac Virtual Display" needs physical proximity + same Apple ID — it does NOT ride the tailnet; VNC does.
4. **Editorial QA at cinema scale (zero dev).** WR2 carousels / WR3 episodes reviewed at wall size (color, typography, pacing) — a print-proof-grade review surface. Files via web surfaces or Taildrop.
5. **Property vertical, client-facing (P4 — business, Legge 5).** Immersive villa tours (360/panorama; true spatial video requires an iPhone 15 Pro+/16 non-e — neither current fleet phone can shoot it), in-office client demos, FaceTime Persona for remote consults. Strategic/business call — Zero only.
6. **Form-factor QA.** balizero.com surfaces tested in visionOS Safari occasionally.

## 4. Organization actions

| Action | Owner | Status |
|---|---|---|
| Update `reference_tailnet_topology` memory with the new node + naming gotcha | session | DONE this session |
| Confirm node identity on-device (Tailscale app on visor) | operator[physical] | OPEN |
| Rename node → `vision-pro` in admin console (kills the iPad-name ambiguity; MagicDNS name follows) | operator[GUI] | OPEN — recommended |
| Clarify the `applevisionpro1987@gmail.com` Claude seat (new account this session runs under — which plan? roster impact?) | operator[business] | OPEN — flagged |
| Pilots P1/P2 build | session (on Zero's pick) | AWAITING PICK |

## 5. Proposed pilots (ranked, interactive pick)

- **P0 — today, nothing to build**: open `https://nuzantara.tail461666.ts.net` in visor Safari (OpenClaw Control) + public surfaces. Proves the whole chain.
- **P1 — "spatial deck" launcher (~30 min, session)**: one static HTML page served tailnet-only (new `tailscale serve` path on Pro or Mini) linking every ops surface (escalations board, OpenClaw Control, kita/my/prime, WR2 queue), laid out to be opened as N separate spatial windows.
- **P2 — dev cockpit (~30-60 min, session)**: `ttyd` (+ optional `code-server`) on Mini, tailnet-only serve → `claude` CLI in the visor.
- **P3 — VNC full desktop (operator-gated)**: Screen Sharing on Pro/Mini + visionOS VNC client.
- **P4 — business uses (Legge 5)**: property immersive demos, client Personas.

## Sources

- [Tailscale App Store listing (visionOS 1.0+)](https://apps.apple.com/us/app/tailscale/id1470499037)
- [tailscale/tailscale#11081 — FR: Tailscale on Apple Vision Pro](https://github.com/tailscale/tailscale/issues/11081)
- [tailscale/tailscale#11178 — FR: use Vision Pro with Tailscale](https://github.com/tailscale/tailscale/issues/11178)
- Memory `decision-two-iphones-tailnet-leverage-2026-08-03` (4-LLM brainstorm, hard iOS boundaries)
- Live probes this session: `tailscale status/whois/ping/serve status`, `lsof`/`curl` on 18789/8789
