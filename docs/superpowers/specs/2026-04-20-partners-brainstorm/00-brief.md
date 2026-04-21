# CRM Partners Module — Multi-LLM Council Brief (2026-04-20)

You are one of 4 LLMs (Gemini 2.5 Pro, Codex, DeepSeek, NotebookLM NB-2)
being asked the same 10 questions in parallel. Another Claude will synthesize
all answers, flag disagreement, apply devil's advocate, and produce a final
spec. Be opinionated, be concrete, keep answers compact.

## Context

**Business:** Bali Zero (balizero.com) — Indonesian business services (visa,
company setup, tax, property) for 5000+ clients in Bali. Based in Indonesia,
clients often abroad.

**Current state:** Bali Zero works with "third parties" (agents, hotels,
property managers, consultants) who **refer paying clients** in exchange for
cash commission. Today this relationship is **informal** — no DB record, no
automated tracking, no legal formality. Owner wants to formalize it end-to-end
in the CRM.

**Target state:** new "Partners" module, visible as sidebar section in the
team portal between `/process` and `/hr`. A partner has a portal login
(role = `partner`) mirroring the team portal, seeing only their own
referrals and commissions. Team members owning a partner see the same,
filtered view.

## Stack constraints (non-negotiable)

- Backend: FastAPI, Python 3.11, Postgres, Redis, Qdrant.
- Backend dir: `apps/backend-rag/backend/`. Last migration: **118**.
- EventBus: PG LISTEN/NOTIFY + in-process pub/sub
  (`backend/services/events/`, 10s dedup window).
- Email: **Brevo only** (key `xkeysib-`), from
  `zantara@balizero.com`, via `POST /api/notifications/send-email` +
  `X-API-Key`.
- Frontend team: `apps/mouth/app/portal/(authenticated)/*` (Next.js 16,
  warm-depth design tokens `packages/core/styles/bz-tokens.css`).
- RBAC: existing pattern `verify_client_access` with
  `except HTTPException: raise` before generic except (SCAR 2026-03-26).
- Admin: Zero (`zero@`), Antonello (`antonellosiano@`), Asya (`asya@`) see all.
- Indonesian regulatory context: UU PDP (personal data), PPh 21/23 (witholding
  tax on professional services), kwitansi/invoice standard.

## Functional requirements (locked)

1. Team member creates partner: full name, work role, `assigned_to` owner,
   company name, office address, email, phone. Evaluate: IBAN/rekening, NPWP,
   preferred language.
2. Welcome email on creation → Bali Zero services + prices + referral
   schema + T&C (commission paid only when process = `completed` + `paid`).
3. Partner portal mirroring team portal: referrals list + status +
   commissions (accrued / paid / pending) + total earned.
4. Team member sees same view filtered to `assigned_to = self`.
5. On process open/edit: optional dropdown "referrer" populated with partners
   where `assigned_to = current_team_member`.
6. On process `completed + paid`: automatic email to partner (CC team member)
   with commission amount + payment schedule.
7. Postgres tables: `partners`, `partner_referrals`, `partner_commissions`
   (ledger: `accrued | approved | paid`). Indexes: `assigned_to`, `partner_id`,
   `process_id`. EventBus channel `partner_commission_changed`.

## The 10 open questions (answer each concisely, <150 words each)

**Q1. Commission policy.** Fixed % per service, variable % per partner, tiers,
flat fee? Should there be a `commission_rules` table? What's the minimal
viable schema that supports future flexibility without over-engineering?

**Q2. Timing.** Does the commission accrue **instantly** when the process
flips to `completed + paid`, or with a delay (e.g., 30 days cooling-off to
absorb refunds/clawbacks)? Default?

**Q3. Payment rail.** Manual ledger only (team marks `paid` in UI) or
integrate Indonesian bank transfer (BCA, Mandiri, OVO, Xendit)? YAGNI vs.
automation? Pick one for v1.

**Q4. Fiscal receipt.** Partner commission = income for the partner.
Indonesia requires what: self-billed invoice from Bali Zero? Kwitansi signed
by partner? PPh 21/23 withholding? Is this blocking for v1 or can we defer?
Be specific about Indonesian compliance.

**Q5. Portal topology.** New subdomain `partners.balizero.com` (separate
Vercel app) OR role-gated section of existing `portal.balizero.com`?
Pros/cons for a 5000-client CRM with 20-100 partners.

**Q6. RBAC.** Reaffirm: partner sees only own, team member sees only own
partners, Zero/Asya see all. Any edge case? (E.g., partner referring another
partner — multi-level? Bali Zero internal team member as partner?)

**Q7. Team↔partner cardinality.** Single `assigned_to` owner per partner
(one-to-one) OR multi-contact team (many-to-many through
`partner_team_members`)? Which wins for YAGNI + future flexibility?

**Q8. Reassignment.** Team member leaves Bali Zero → who inherits their
partners? Auto-reassignment is **forbidden** by policy (memory
`feedback_no_auto_assignment`). What's the manual workflow?

**Q9. Clawback.** Process marked `paid`, commission `paid` to partner, then
client cancels / refund issued. What happens to the commission ledger?
Refund owed by partner? Write-off? Design a clean state transition.

**Q10. Multi-referral per process.** Can multiple partners share a single
process (split commission 50/50) OR is referrer strictly 0-or-1 per process?
For v1, pick the simpler one; design a path to the other.

## Output format

Return **valid Markdown** with sections `## Q1` through `## Q10`, each
ending with a **Recommendation:** line (max 1 sentence). Optionally add
`## Additional concerns` with anything the 10 questions miss.

Do NOT write code. Do NOT write SQL. Do NOT write API endpoints.
This is design brainstorming only.
