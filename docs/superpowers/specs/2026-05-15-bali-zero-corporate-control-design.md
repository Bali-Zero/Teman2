# Bali Zero Corporate Control System — Design Spec
**Date:** 2026-05-15  
**Author:** Antonello Siano (Zero) + Claude Sonnet 4.6  
**Brainstorm panel:** DeepSeek V4 Pro + Gemini 3.1 Pro + Codex GPT-5.5  
**Ground-truth:** NB-6 (Ops & Compliance / UU PDP) + NB-10 (Team Guides / Indonesian labor law)  
**Status:** Draft — pending user review

---

## 1. Goal & Constraints

### Business goal
Deploy a "trust + verify" corporate control package for 9 Indonesian team members by Q3 2026. The system must prevent data exfiltration and unauthorized use of corporate assets (WA Business number, client CRM, corporate email) without crossing into keylogger/screen-record territory.

### Hard constraints
| # | Constraint | Source |
|---|---|---|
| C1 | Zero additional recurring cost (no Workspace Enterprise upgrade) | User |
| C2 | No screen recording, no keyloggers | User: "non voglio essere un tiranno" |
| C3 | Trust + verify ethos — anomaly alert, not continuous surveillance | User |
| C4 | UU 27/2022 PDP compliant (DPIA + Privacy Notice + consent) | NB-6 ground-truth |
| C5 | All contracts Bahasa Indonesia only (UU 24/2009 art. 31) | User |
| C6 | Waarmerking notarization only (Level 2, ~Rp 200-500k/contract) | User |
| C7 | SIM management: 15 corporate Telkomsel Halo Business SIMs already purchased | User |
| C8 | Android standardization (all corporate phones) | Derived from MDM choice |

### Out of scope
- Physical office infrastructure (armadietti, laptop purchase) — user's decision, not a system deliverable
- Air decommissioned — Mini-Pro2 is the server companion, not relevant here
- Workspace Enterprise upgrade — explicitly rejected

---

## 2. Target Population

9 team members subject to Q3 rollout. Cross-reference with `apps/backend-rag/backend/data/team_members.py` after KTP OCR extraction (Phase 1).

Known from CRM (pending confirmation against 9 KTP):
Vino · Krisna · Adit · Ari Firda · Dea · Surya · Damar · Sahira · Rina  
(Asya excluded as Platform/Backend, admin-equivalent)

---

## 3. Architecture — 4 Layers

### Layer 1 — Employment Contracts (PKWTT + 5 Annexes)

**Primary legal pillars** (highest enforceability under Indonesian law):
1. **Lampiran I — Kerahasiaan dan Non-Divulgasi (NDA/Confidentiality)**  
   Perpetual duty of confidentiality on client data, pricing, processes. No time limit, no geographic limit. Strongest pillar under KUHPerdata.

2. **Lampiran II — Penyerahan Hak Kekayaan Intelektual (IP Assignment)**  
   All work product, code, content, client lists created during employment → assigned to PT. Work-for-hire language aligned with UU 28/2014 Hak Cipta.

3. **Lampiran III — Non-Solicit + Non-Compete (optional)**  
   - **Non-solicit** (primary, strong): prohibition on soliciting Bali Zero clients and employees for 24 months post-termination. Anchored on NDA violation, not standalone.  
   - **Non-compete** (optional, narrow): if included, limited to 12 months, geographic scope Bali only, requires 50% last-month salary as compensation during restriction period. Reference: PN Jakarta Timur No. 54/Pdt.G/2017/PN.Jkt.Tim.  
   - **DO NOT CITE** MA RI 1331/K/Pdt/2010 — irrelevant Hukum Adat Bali inheritance case.

4. **Lampiran IV — Acceptable Use Policy + Privacy Notice (UU PDP)**  
   - Defines corporate-only use of: corporate email (Zoho), Google Drive (zero@balizero.com), WA Business number, CRM (kita.balizero.com).  
   - Explicit prohibition: linking corporate WA Business to personal devices; personal Gmail/WA on corporate devices during office hours (09:00–18:00 WITA).  
   - **Privacy Notice** (mandatory per NB-6/UU PDP): describes what monitoring data is collected (access logs, device enrollment status, anomaly alerts), purpose, retention period, employee rights.  
   - **Informed consent** signature: employee acknowledges and consents to monitoring of company-owned systems.

5. **Lampiran V — Ganti Rugi Likuidasi (Liquidated Damages)**  
   Graduated penalty schedule:
   - Rp 5.000.000 per device: personal device found linked to corporate WA Business (physical audit)
   - Rp 10.000.000 per incident: confirmed client data forwarded to external number
   - Rp 25.000.000 per incident: NDA breach (client list, pricing exfiltration)
   - Non-compete violation: 3× last-month salary (if Lampiran III non-compete opted in)  
   All capped at "actual demonstrated loss + penalty multiplier ≤ 3×" to pass KUHPerdata reasonableness test.

**Notarization:** Waarmerking only (certifies signatures, not content). ~Rp 200–500k per contract × 9 = ~Rp 2–4.5M one-time. Recommended batch at one notary appointment.

**DPIA status:** Required before deploying Layer 4 (anomaly monitoring). Lampiran IV Privacy Notice partially satisfies DPIA documentation obligation. Full DPIA assessment file: `research/compliance/2026-05-15-dpia-corporate-monitoring.md` (to be created in Phase 2).

---

### Layer 2 — Browser & Desktop Policy

**Goal:** Prevent personal profile use and unauthorized access to personal cloud services from corporate devices during office hours. Zero additional recurring cost.

#### 2a. Chrome Enterprise Core (free)
- Enroll corporate Chrome profiles at `admin.google.com` under Workspace Business Plus (already active for `zero@balizero.com`).
- Policies to enforce:
  - `BrowserSignin: 2` (force sign-in to corporate account, prevent personal account)
  - `URLBlocklist: ["accounts.google.com/*/personal*", "mail.google.com", "web.whatsapp.com", "wa.me"]` during office hours context
  - `URLAllowlist: ["mail.zoho.com", "kita.balizero.com", "my.balizero.com", "drive.google.com/drive/folders/*"]` (zero@balizero.com shared drive)
  - `SessionLength: 540` (9h forced re-login — kills personal session drift, no Enterprise required)
  - `DefaultBrowserSettingEnabled: true` (block profile switch to personal)
- **Limitation acknowledged (Gemini):** Chrome policy = browser only. Does not block Firefox, Edge, or hotspot bypass. Complemented by DNS filter (Layer 2b).

#### 2b. DNS Filtering at office router
- **Tool:** NextDNS free tier (300k queries/month, sufficient for 9 users).
- Blocks at network level — immune to browser switch, hotspot cannot be controlled but is not company infrastructure.
- Block categories: Personal email, Personal messaging (WhatsApp Web), Social media (if policy requires).
- Office router DNS → NextDNS upstream. Apply to SSID corporate network only.
- **Limitation:** Does not apply to corporate SIM data (personal hotspot). Covered by Lampiran IV Acceptable Use prohibition.

#### 2c. AppLocker (Windows Pro — where applicable)
- Whitelist-only execution policy for corporate Windows devices.
- Approved executables: Chrome (corporate profile), Zoho Desktop, Canva Desktop, VS Code (Asya only), Figma.
- Block: Firefox, Edge, Telegram Desktop, WhatsApp Desktop.
- Applied via Group Policy or local AppLocker rules (no domain controller required for local policy).

#### 2d. Zoho Admin Policies
- Enforce 2FA on all `@balizero.com` Zoho accounts.
- IP allowlist: office static IP + Tailscale range (for remote work by authorized staff).
- Audit log retention: 90 days.
- Shared inbox for client-facing email: prevents individual mailbox exfiltration.

---

### Layer 3 — WhatsApp Business & Mobile Control

**Architectural decision: PIVOT to WhatsApp Business Cloud API (Meta official)**

All 3 LLM panelists independently recommended this pivot. Native WA Business app on corporate phones is eliminated.

#### 3a. WhatsApp Business Cloud API
- **What it is:** Meta's official server-side API for WA Business. No "linked devices" concept. All messages route through Meta's cloud → Bali Zero backend → team dashboard.
- **Why:** Eliminates the linked-device attack vector entirely. Employees respond from a shared inbox (e.g., Zoho Desk + WA channel, or lightweight custom UI) — no WA app needed.
- **Implementation path:**
  1. Create/verify Meta Business Manager account (`business.facebook.com`)
  2. Add WA Business number (Bali Zero's current corporate number) to Meta Business Manager
  3. Apply for Cloud API access (approved for Indonesian businesses)
  4. Implement webhook → `apps/backend-rag/backend/channels/whatsapp/` (existing channel handler)
  5. Team responds via shared dashboard (Phase 3 implementation detail)
- **SIM role changes:** Corporate SIM no longer needs WA app. SIM is now exclusively: OTP token for corporate accounts + Telkomsel Halo data for field work.

#### 3b. SIM Management (treat as bank token)
Per Codex panel recommendation — SIM = identity root.
- **Registry:** Antonello holds physical registry of all 15 SIMs (number ↔ employee name ↔ slot).
- **SIM PIN:** All corporate SIMs have SIM PIN enabled. PIN known only to Antonello.
- **Prohibition:** SIM removal from corporate phone during office hours. Covered by Lampiran IV.
- **Exit-day protocol:** On termination/resignation → immediately suspend SIM at Telkomsel business portal before employee leaves building.
- **OTP interception risk:** If employee keeps SIM outside office hours, they could receive OTPs for corporate accounts. Mitigated by: 2FA tied to Authenticator app (not SMS where possible) + SIM PIN.

#### 3c. Miradore Free MDM (Android only)
- 50-device free tier covers all 15 corporate phones.
- Enforce: device encryption, screen lock PIN, remote wipe capability, app installation policy.
- **Enroll:** All 15 corporate Android phones via QR code enrollment (Android Enterprise Work Profile or Device Owner mode).
- **Policy:** Separate work profile — corporate apps in work profile, personal apps blocked in work profile. Work profile can be remotely wiped without affecting personal data.
- **Audit:** Device compliance status visible in Miradore console (enrolled Y/N, last check-in, encryption Y/N).

#### 3d. Weekly Physical Audit
- **What:** Manager checks WA Business `Linked Devices` screen on corporate phone during team meeting.
- **Frequency:** Weekly, Monday morning.
- **Trigger for penalty:** Personal device found linked → Rp 5M per Lampiran V.
- **Responsibility:** Team lead or Antonello (5 minutes per device, 9 × 5 = 45 min/week).

---

### Layer 4 — Anomaly-Based Monitoring

**Philosophy (Codex):** No productivity score theatrics. Only anomaly detection for security events. Alerts go to management only, not visible to employees.

#### 4a. Monitoring signals (CRM + backend logs)
| Signal | Threshold | Action |
|---|---|---|
| New device login to `kita.balizero.com` | Any | Telegram alert → Zero |
| Bulk data export (>50 records CSV/PDF) | Any | Telegram alert → Zero |
| Off-hours access (before 08:00 or after 20:00 WITA) | Any | Log, weekly digest |
| External file share (Drive link shared outside `@balizero.com`) | Any | Telegram alert → Zero |
| WA Cloud API: message forwarded to non-CRM number | >3/day | Telegram alert → Zero |
| Failed 2FA attempt on Zoho | >3 consecutive | Telegram alert + account lock |

#### 4b. Implementation touchpoints
- CRM backend: `apps/backend-rag/backend/app/routers/` — add audit event emitter on export endpoints.
- Cell pulse: `apps/cell/` — enroll anomaly detector as a new cell type.
- Telegram alert: existing `TELEGRAM_BOT_TOKEN` + `TELEGRAM_OWNER_CHAT_ID` (1125336968).
- Google Drive: `scripts/drive_poll_service.py` — extend to detect external share events.

#### 4c. What is explicitly NOT monitored
- Keystroke / screen content (keylogger prohibition)
- Personal device activity
- Personal phone usage
- Off-site personal activities
- Message content (only metadata: who, when, external Y/N)

---

## 4. Implementation Phases

| Phase | Deliverables | Effort | Timeline |
|---|---|---|---|
| **Phase 1** | OCR 9 KTP → roster sheet; Draft 9 PKWTT + Lampiran I-V | 2-3 days | Week 1 |
| **Phase 2** | Chrome Enterprise Core policies; Zoho 2FA + IP allowlist; NextDNS office router; DPIA doc | 1 day | Week 2 |
| **Phase 3** | WA Cloud API enrollment + webhook integration; Miradore MDM enrollment 15 phones; SIM registry | 3-4 days | Week 3-4 |
| **Phase 4** | CRM anomaly detector; Drive external-share alert; Cell pulse enrollment; Telegram alerts | 2 days | Week 5 |
| **Phase 5** | Notary appointment (waarmerking × 9); Employee onboarding session | 1 day | Week 6 |

---

## 5. Cost Summary

| Item | Type | Cost |
|---|---|---|
| Chrome Enterprise Core | Recurring | Rp 0 (free) |
| NextDNS | Recurring | Rp 0 (free tier) |
| Miradore Free MDM | Recurring | Rp 0 (free, ≤50 devices) |
| WA Business Cloud API | Recurring | Meta per-conversation pricing (~USD 0.005/conv) |
| Corporate SIMs (15×) | Recurring | Rp 825k/month (already purchased) |
| PKWTT waarmerking × 9 | One-time | ~Rp 2–4.5M |
| Meta Business Manager | One-time | Rp 0 (free account) |
| **Total new recurring** | | **~USD 0–50/month** (WA API usage only) |

---

## 6. Legal Anchors & Citations

| Document | Relevance | Status |
|---|---|---|
| UU 13/2003 Ketenagakerjaan + UU Cipta Kerja 6/2023 | PKWTT framework | Verified via NB-10 |
| KUHPerdata Pasal 1337-1338 | Non-compete + liquidated damages enforceability | Verified |
| UU 28/2014 Hak Cipta | IP Assignment | Verified |
| UU 27/2022 PDP | Monitoring privacy compliance | Verified via NB-6 |
| UU 24/2009 Pasal 31 | Bahasa Indonesia contract requirement | Verified |
| PN Jakarta Timur No. 54/Pdt.G/2017/PN.Jkt.Tim | Non-compete precedent (fair + LD = valid) | Verified via NB-10 |
| UU 19/2016 ITE + UU 27/2022 PDP | Employee monitoring lawfulness | Verified via NB-6 |

**FORBIDDEN citation:** MA RI 1331/K/Pdt/2010 — Hukum Adat Bali inheritance case, zero relevance to employment law. DO NOT USE.

---

## 7. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Employee uses personal hotspot to bypass DNS filter | Medium | Low (policy violation only) | Lampiran IV prohibition (contractual deterrent); Miradore Work Profile does NOT detect this — requires manual spot-check |
| WA Cloud API delivery latency vs. native app | Low | Medium | SLA monitoring; Meta guarantees 99.9% uptime |
| Non-compete voided by court | Medium | Low (non-solicit + confidentiality intact) | Non-solicit is primary; non-compete is optional |
| DPIA not completed before monitoring deploy | Low | High (UU PDP violation, up to Rp 60M fine) | Block Phase 4 on DPIA completion |
| SIM OTP interception after hours | Low | Medium | Authenticator-app 2FA preferred over SMS |
| Document forwarding in WA (10s exploit per DeepSeek) | Medium | High | CRM chokepoints: client docs stored in Drive, not WA |

---

## 8. Open Decisions

| # | Question | Default if not resolved |
|---|---|---|
| OD-1 | Non-compete in Lampiran III: include for all 9 or only client-facing roles? | Include for: Ari (visa), Sahira (sales), Adit (onboarding). Exclude: Krisna, Vino, Rina |
| OD-2 | WA Cloud API shared inbox: Zoho Desk (existing) or lightweight custom UI? | Zoho Desk (existing subscription) |
| OD-3 | NextDNS profile: block social media entirely or log-only? | Log-only (trust + verify) |
| OD-4 | Miradore: Device Owner mode (full control) or Work Profile (split)? | Work Profile (less invasive, per C2 constraint) |
| OD-5 | DPIA: internal document only or submit to KOMDIGI PSE/TDPSE? | Internal only (PSE registration is separate obligation) |
