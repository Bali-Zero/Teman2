---
date: 2026-08-27
domain: operations
client_case: none
sources:
  - "4-LLM panel run 2026-08-27: Codex GPT-5.6-sol (xhigh), Kimi K3, Gemini 3.1 Pro (agy), Qwen (qwen CLI, minimal-payload retry) — raw outputs in ./2026-08-27-tailnet-panel-raw/"
  - "tailscale.com/blog/patterns-from-the-field-use-cases"
  - "Paperless-ngx guides (pistack.xyz, techfuelhq.com, elest.io)"
  - "wz-it.com — local AI for law firms (on-prem Open WebUI+Ollama pattern)"
  - "cloudzy.com — self-hosted password managers 2026 (Vaultwarden)"
adversarial_review: exempt-this-file-is-the-4-llm-panel-synthesis-itself-not-a-reviewed-deliverable
---

# Tailnet team expansion — 4-LLM panel round + external scan (companion to 2026-08-27-tailnet-team-expansion-research.md)

Zero ordered a panel round (Codex sol, Kimi K3, Qwen, Gemini 3.1 Pro) on the "digital campus"
design, plus external deep research. All 4 seats delivered (Qwen needed a minimal-payload
relaunch — known behavior). Shared brief + verbatim outputs: `./2026-08-27-tailnet-panel-raw/`.

## Unanimous verdicts (design changes)

1. **A company OS account on a personal Mac is NOT a security boundary** (4/4). The personal
   user remains machine admin. Practical cure, no MDM purchase: FileVault on, browser-only
   no-download access for the most sensitive data, live practices stay on OUR Macs — the team
   workstation is a *window* on the campus, not a store of copies. Codex: "no compliant
   device, no PII access". Leaver checklist > "1-click offboarding" (ACL is 10% of it).
2. **Week-1 room is Intake Drop + Coda Review shipped as ONE workflow** (Kimi, Codex),
   overturning the draft's "zero-dev rooms first". Zero-dev rooms change nobody's day; intake
   attacks the #1 legal exposure (client PII in WhatsApp) and is used daily by everyone.
   A review queue without an owner + same-day SLA is a backlog generator (Kimi).
3. **Officina AI (generic internal ChatGPT) moves LAST** (3/4). A 24GB Mini collapses at ~2
   concurrent users → staff conclude "internal AI is slow/dumb" → return to personal ChatGPT
   WITH client text: we'd be building the shadow-IT incentive ourselves. Ship narrow locked
   workflows (translate/summarize/extract) instead of open chat; RAM upgrade before rollout.
4. **Single office exit node for gov portals: pilot with 2-3 users, never day-1 policy.**
   SPOF (one reboot locks 14 people out of portals — Gemini) and 14 users from one
   residential IP is a fraud-heuristic/captcha pattern (Kimi).
5. **Bus factor is the #1 year-one risk** (4/4). Cheapest cure (Qwen): one-page runbook +
   one trusted non-technical L1 custodian walked through it once + uptime alerts +
   2 restore drills/year. ~2 hours, zero rupiah.
6. **"Local processing" alone ≠ UU PDP compliance** (Kimi, Codex): must be able to SHOW who
   accessed which client record when. Append-only audit logging everywhere from day 1
   (vault, intake, CRM) + a one-page retention/deletion SOP. Retrofitting in month 9 = 10×.
7. **Rejected**: Time Machine of personal laptops → Mini (I/O saturation + captures personal
   data; back up managed company folders only, encrypted) · "10-minute onboarding" (plan a
   half-day with checklist) · merely ACL-gating the exposed `/term` shell (Codex: REMOVE it,
   inspect the host, rotate what transited it).

## Strongest new ideas (deduplicated, attributed)

1. **Cross-document Consistency Gate** (Codex): local OCR compares passport/KITAS/NPWP/akta/
   NIB within one practice and flags the exact conflicting FIELDS before filing.
2. **Bacheca as document-driven case checklist** (Kimi): each intake event updates
   "what's missing for this KITAS" — dashboard becomes work list; no training needed.
3. **Expiry/deadline watcher with per-department 30/14/7 digests** (Kimi) — structured
   extraction, not chat. NOTE: exists as draft agent (compliance-deadline-sentinel);
   the campus finally gives it a delivery channel.
4. **Field Mission Pack + offline-first capture** (Codex/Qwen/Gemini): encrypted offline
   case pack before a government-office visit; photos enter the case via native share sheet
   without touching the camera roll; sync on reconnect.
5. **Submission Control Room (four-eyes)** (Codex): one prepares the tax/OSS/immigration
   filing, another verifies identifiers/amounts/attachments, only then is the credential
   released from the vault — also fixes shared-credential zero-accountability (Kimi).
6. **Privacy Export Gateway** (Codex): the dangerous moment is when a file LEAVES the mesh —
   mandatory local PII detection, redaction option, watermark, export ledger.
7. **Chain-of-custody receipts** (Kimi): hash + timestamp every document at intake,
   auto-receipt to client. ~1 day of work, permanent legal value.
8. **Deterministic government-form auto-filler** (Gemini): OCR fields → official PDF
   templates (Surat Kuasa, LKPM, OSS forms); no manual copying of passport numbers.
9. **Cited SOP assistant over Biblioteca** (Kimi): local RAG answering procedure questions
   with handbook citations — cuts the 20×/day interruptions of senior staff.

Honesty flag: Qwen cited "UU PDP Art. 23" and portal names (SIMPASI, e-POA) that were NOT
verified — do not repeat those citations; its ideas stand without them. Its "tailscale scp
from phone" is imprecise (Taildrop is the actual mechanism on iOS); its "exit-node logs as
audit trail" overstates what non-Premium plans log.

## External scan (outside the den)

- Canonical tailnet team pattern = exactly our campus: internal dashboards/tools never
  publicly exposed; JIT privileged access via API-managed ACLs; contractors on allowlists
  (tailscale.com patterns-from-the-field).
- Document archive: the world does not build from scratch — **Paperless-ngx** (consume
  folder → OCR → auto-tag/file by correspondent/type, workflow triggers) is the de-facto
  small-org standard. Reuse-first: evaluate it (hooked to our local OCR) before writing a
  custom Biblioteca archive — likely covers ~70%.
- Law/accounting firms in 2026 adopt precisely the on-prem "AI box" (Open WebUI + Ollama)
  for confidentiality obligations — direction validated; the forgotten recurring cost is
  model/update maintenance (bus factor again).
- Vaultwarden = de-facto standard for small teams (single container, ~50MB RAM).

## Revised build sequence (fusion of all four seats)

1. Foundations: REMOVE the Pro shell + rotate what transited it + deny-by-default ACL +
   audit logging on everywhere from day 1.
2. Intake Drop + Coda Review as one product (owner, SLA, hash receipt) — 3-person field pilot.
3. Cassaforte (Vaultwarden) with audit + TOTP; migrate portal credentials.
4. Bacheca-as-checklist + expiry watcher.
5. Zantara Desk (once per-assignment RBAC is proven).
6. Officina AI last, as narrow workflows — likely after a Mini RAM upgrade.
7. Exit node, printers, all-team phones: after the pilot, measured.

## §Solo-operatore

Unchanged from the companion doc: admin-console ACL/policy work, plan/billing, invites,
on-device enrollment. New from this round: choosing the L1 continuity custodian (Legge 5).
