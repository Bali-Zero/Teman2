---
date: 2026-07-12
domain: compliance
client_case: internal (Case OS Fase-0, P0-03)
sources:
  - UU 27/2022 (UU PDP — Pelindungan Data Pribadi), Art. 20 (consent), 21 (purpose), 42-46 (controller obligations), 56 (cross-border), 67-68 (sanctions)
  - PP 71/2019 (Penyelenggaraan Sistem dan Transaksi Elektronik) — PSE definition + registration
  - Permenkominfo 5/2020 + 10/2021 (PSE Lingkup Privat registration mechanics)
  - Repo state (Balizero/Teman2) verified on disk 2026-07-12
---

# PSE / UU PDP — Evidence Matrix (Case OS P0-03)

> **Scope & honesty note.** This is a *compilation anchored to actual repo/infra state*, not legal
> advice and not a decision that needs Zero's sign-off (the earlier "avvocato entro 14 giorni" framing
> was a hallucination — corrected). It maps each UU PDP / PSE obligation to (a) what the codebase
> already provides, with `file:migration` anchors, (b) what is missing, and (c) a status. Where a row
> is a business/legal judgement (e.g. whether Bali Zero must register as PSE Lingkup Privat), it is
> flagged **DECISION** and left to Zero + counsel — the matrix does not resolve it, it scopes it.

## 0. Applicability — is Bali Zero a PSE?

Bali Zero operates client-facing electronic systems (CRM portal `kita/my.balizero.com`, WhatsApp/IG/web
chat channels, RAG knowledge service) that collect and process Indonesian personal data (KTP, passport,
NPWP, NIB). Under **PP 71/2019 Art. 2** a private party running an electronic system that serves the
public is a *Penyelenggara Sistem Elektronik Lingkup Privat*. Registration with Kominfo (now Komdigi)
is mandatory for qualifying PSE Lingkup Privat under **Permenkominfo 5/2020**.

| | |
|---|---|
| **PSE Lingkup Privat registration (Kominfo/Komdigi)** | ❌ **No evidence of registration in repo or infra.** No PSE ID, no registration artifact. **DECISION** — whether Bali Zero's systems meet the registration threshold (public-serving + one of the Art. 2(3) triggers) is a legal call for Zero + counsel. Non-registration risk under Permenkominfo 5/2020 is administrative (access blocking), not the PII-breach class. |

## 1. Data-controller obligations (UU PDP Art. 42-46)

| Obligation | Repo evidence | Gap | Status |
|---|---|---|---|
| **Consent, per-purpose (Art. 20-21)** | `client_consent_log` table — append-only, immutable, `purpose_key` + `action IN (granted,revoked)` + indexed active-grant lookup (`migration_091_client_consent_log.py`) | Consent is *recorded* when written, but no audit that every PII-collecting flow (WA intake, portal signup) actually writes a grant before processing. Mechanism ✅, coverage ⚠️ unverified | 🟡 PARTIAL |
| **Purpose limitation** | `purpose_key` column scopes consent to a purpose | No enforcement that processing checks the matching purpose grant before acting | 🟡 PARTIAL |
| **Audit trail (accountability)** | `audit_logs` (action / resource / actor / ip_address / user_agent / timestamp, indexed) — `migration_069_audit_logs.py`; separate `api_audit_trail` with 90-day retention sweep (`olympus/pulse.py:172`) | Not all mutating routes emit an audit row (ties to Fase-1 authz work — 65 nude routes) | 🟡 PARTIAL |
| **Data accuracy / rectification** | CRM update paths exist (`crm_clients.py`) | No subject-facing rectification flow | 🟡 PARTIAL |
| **Security of processing (Art. 35)** | See §3 (PII redaction, sovereignty gates) | — | 🟢 PRESENT |

## 2. Data-subject rights (UU PDP Art. 5-13)

| Right | Repo evidence | Gap | Status |
|---|---|---|---|
| **Access (DSAR — get a copy of my data)** | none found | ❌ **No DSAR/export endpoint** (`grep` for data-subject/export/erasure in routers → empty) | 🔴 MISSING |
| **Erasure / "right to be forgotten" (Art. 8)** | `delete_episode`, CRM delete paths exist piecemeal | No single subject-scoped erasure that spans clients + interactions + consent + Drive + Qdrant vectors | 🔴 MISSING (no unified flow) |
| **Withdraw consent (Art. 9)** | `client_consent_log` supports `action='revoked'` | No subject-facing revoke UI/endpoint verified | 🟡 PARTIAL |
| **Objection / restriction** | none | ❌ | 🔴 MISSING |

## 3. Security & sovereignty (UU PDP Art. 35 + SYMBIOSIS Law 2)

| Control | Repo evidence | Status |
|---|---|---|
| **PII detection + outbound redaction** | `middleware/pii_scanner.py` — Presidio recognizers for KTP (16-digit), NPWP (old 15 + new 16-digit), Indonesian passport, +62 phone, email; violations logged to `pii_violations` with severity (`migration_114a_pii_violations.py`) | 🟢 PRESENT |
| **Error-tracking PII redaction** | `sentry_config.py::_before_send` strips NPWP/NIB/passport/email/phone/client_id/name (load-bearing, CLAUDE.md) | 🟢 PRESENT |
| **Local-sovereign PII processing** | OCR / vision on-Pro local (`qwen2.5vl:7b`), `cloud_vision_gate` fail-closed; raw WA mirror Pro-bound by operational choice (Law 2) | 🟢 PRESENT |
| **Access control on mutating APIs** | JWT middleware authenticates all non-public routes; **but 65 mutating routes have zero role distinction** (Fase-1 authz work, this campaign) | 🟡 IN PROGRESS |
| **Secret management** | Fly secrets; public-repo admin key `zantara-secret-2024` rotated + revoked 2026-07-12 | 🟢 PRESENT (post-rotation) |

## 4. Cross-border transfer (UU PDP Art. 56)

PII in transit/at-rest touches foreign-hosted subprocessors. Art. 56 permits transfer with adequate
safeguards + explicit consent (CLAUDE.md §14: UU PDP imposes no data-localization on private agencies;
transit is lawful under Art. 56 with Workspace DPA + consent).

| Subprocessor | Role | PII exposure | Safeguard status |
|---|---|---|---|
| **Fly.io (US)** | app + Postgres host | client PII at rest in Postgres | needs DPA on file — ⚠️ unverified |
| **Tigris** | Postgres backup (daily) | PII in backups | needs DPA — ⚠️ unverified |
| **Vercel** | frontend host | PII in transit (portal) | needs DPA — ⚠️ unverified |
| **Brevo** | transactional email | client email + name | needs DPA — ⚠️ unverified |
| **Sentry** | error tracking | **redacted** by `_before_send` before leaving | 🟢 mitigated in-code |
| **Google Workspace** | Drive (client docs) | client documents | Workspace DPA (standard) — likely ✅, confirm |

**Gap:** no consolidated subprocessor register with DPA-on-file status. The *code-side* mitigations
(Sentry redaction, local PII processing) are real and present; the *paper-side* (signed DPAs, subprocessor
list, transfer-consent language) is the unverified half.

## 5. Incident response (UU PDP Art. 46 — breach notification within 3×24 hours)

| Element | Repo evidence | Status |
|---|---|---|
| **PII-violation detection** | `pii_violations` table + severity grading feeds a signal | 🟢 detection present |
| **Breach notification runbook (72h / 3×24h to subject + authority)** | none found | 🔴 MISSING (no documented runbook) |
| **This session's own precedent** | the `zantara-secret-2024` public-key exposure was detected + rotated same-day (12/7) — an *ad-hoc* good outcome, but not a codified process | 🟡 informal |

## Summary — where the real work is

| Bucket | State |
|---|---|
| **Code-side security controls** (PII redaction, sovereignty, secret mgmt) | 🟢 genuinely strong |
| **Consent + audit mechanisms** | 🟡 built, coverage unverified |
| **Data-subject rights (DSAR, unified erasure, objection)** | 🔴 the biggest gap — no subject-facing endpoints |
| **Paper trail (DPAs, subprocessor register, PSE registration, breach runbook)** | 🔴/⚠️ largely absent — business/legal work, not code |

**Two clean next actions (not decisions — buildable):**
1. A DSAR/erasure endpoint that spans clients + interactions + consent + Drive + Qdrant (closes the
   single biggest UU PDP rights gap).
2. A subprocessor register file (`docs/compliance/subprocessors.md`) + breach-notification runbook —
   cheap, closes two paper gaps.

**One DECISION for Zero + counsel (genuinely not mine):** whether Bali Zero's public-serving systems
cross the PSE Lingkup Privat registration threshold under PP 71/2019 + Permenkominfo 5/2020. The matrix
scopes it; it does not resolve it.
