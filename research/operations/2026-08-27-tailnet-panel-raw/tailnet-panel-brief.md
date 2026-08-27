You are one seat of a 4-LLM advisory panel. Answer directly, in English, max ~900 words. No preamble.

# Context: Bali Zero "digital campus" on Tailscale

Bali Zero is a 14-person Indonesian business-services agency (visas/KITAS, PT PMA company setup, tax, property) run by a solo technical owner. Infrastructure: 3 Macs (dev workstation; a 48GB workhorse running ~170 automation daemons; a 24GB always-on server with local Ollama LLMs) + a FastAPI/Postgres backend on Fly.io + Next.js frontends on Vercel. Strict constraints: Indonesian data-protection law (UU PDP) — client documents/PII are processed ONLY on our own machines (local OCR/LLM), never sent to cloud LLMs; flat-rate subscriptions preferred over per-token APIs; the owner is the only technical person.

Today the Tailscale tailnet contains only the owner's 7 devices (free plan). Plan: every team member gets a SEPARATE COMPANY USER ACCOUNT on their personal computer (signed consent/liberatoria already collected), and that account joins the tailnet. Non-negotiable precondition already identified: replace the factory default allow-all ACL with deny-by-default grants per role BEFORE any invite (today one node even serves an unauthenticated writable shell tailnet-wide — will be fixed first).

## The current draft design ("the campus" — internal-only services over the tailnet)

- Zantara Desk: internal web UI for the company AI assistant (per-assignment CRM visibility; the bot brain exists but has no channel today)
- Intake Drop: drag&drop + phone-photo page feeding the existing local OCR document-intake pipeline (client docs stop travelling via WhatsApp)
- Coda Review: human review queue UI for the intake refinery
- Bacheca: read-only ops dashboards (practice states, compliance deadlines)
- Cassaforte: self-hosted Vaultwarden for shared government-portal credentials
- Officina AI: Open WebUI + Ollama on the server Mac = internal "ChatGPT" on our metal for PII-safe translation/drafting/OCR
- Biblioteca: internal handbook/procedures wiki + golinks
- Ufficio: office printer/scanner via subnet router; exit node on the office Mac so staff working from home hit Indonesian gov portals (tax/immigration) from one stable office IP
- Plus: Time Machine backups of the company user to the server Mac; screen-sharing support; 10-minute onboarding / 1-click offboarding via ACL groups per department (tax, visa, marketing, ops)
- Team phones also enrolled: field capture at immigration offices/notaries → photo goes straight into intake OCR

Rollout: harden ACL → zero-dev rooms (Vaultwarden, Open WebUI) → standard workstation setup script → 3-person pilot → intake surfaces → Zantara Desk → full team (Tailscale Standard $8/user/mo beyond 6 free users).

# Your task (answer all 4, numbered)

1. CRITIQUE: what is weak, naive, or missing in this design? Where will it actually fail in daily operations with non-technical staff?
2. FIVE IDEAS we have NOT listed: concrete, high-leverage things a 14-person compliance/immigration agency can build on a private mesh network with local LLMs. Prioritize ideas exploiting OUR specifics (field work at government offices, document-heavy workflows, per-role data segregation, local AI). No generic VPN benefits.
3. SEQUENCE: would you change the build order? What single room delivers the most value in week 1?
4. PITFALLS: the 3 most likely failure modes of this whole program in year 1 (technical, human, or legal) and the cheapest countermeasure for each.

Be opinionated. If an idea is bad, say so and why.
