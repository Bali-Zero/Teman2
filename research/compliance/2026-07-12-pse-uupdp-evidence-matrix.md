---
date: 2026-07-12
domain: compliance
client_case: internal (Case OS Fase-0, P0-03)
adversarial_review: codex
sources:
  - UU 27/2022 (UU PDP), Art. 20 (6 lawful bases), 21 (consent-info duty), 28 (purpose limitation), 34 (DPIA), 42-46 (controller obligations), 51 (subprocessor authz), 53 (DPO), 56 (cross-border hierarchy), 57 (administrative sanctions), 67-68 (criminal — intentional misuse)
  - PP 71/2019 (Penyelenggaraan Sistem dan Transaksi Elektronik) — Art. 2(5) private-PSE definition, Art. 6 registration
  - Permenkominfo 5/2020 Art. 2 + 10/2021 (PSE Lingkup Privat registration mechanics)
  - Repo state (Balizero/Teman2) verified on disk 2026-07-12
  - Adversarial review: Codex GPT-5.5 (verdict FLAWED → corrections applied), see §Adversarial review
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
NPWP, NIB). A private party running such systems is a *Penyelenggara Sistem Elektronik Lingkup Privat*
defined under **PP 71/2019 Art. 2(5)** (Art. 2(3) covers *public* PSE — cited wrong in an earlier draft,
corrected after adversarial review); the registration obligation itself is **PP 71/2019 Art. 6** +
**Permenkominfo 5/2020 Art. 2**. There is no size/revenue threshold in the text — applicability turns on
"runs an electronic system + processes personal data for the public", which on the functions above is
**prima facie probable, not marginal**.

| | |
|---|---|
| **PSE Lingkup Privat registration (Kominfo/Komdigi)** | ⚠️ **No registration artifact in repo or infra** — but note: registration lives in Komdigi's external OSS/PSE portal, so *absence in the repo does not prove non-registration* (it may exist externally). **DECISION** — confirming registration status and, if unregistered, whether the systems cross the Art. 2(5) + Art. 6 obligation is a legal call for Zero + counsel. Non-registration risk under Permenkominfo 5/2020 is administrative (access blocking), not the PII-breach class. |

## 1. Data-controller obligations (UU PDP Art. 42-46)

| Obligation | Repo evidence | Gap | Status |
|---|---|---|---|
| **Lawful basis / consent (Art. 20 — consent is 1 of 6 bases; Art. 21 = info to give when relying on consent)** | `client_consent_log` table — `purpose_key` + `action IN (granted,revoked)` + partial index on `action='granted'` (`migration_091_client_consent_log.py`) | (a) The table is **not proven append-only/immutable** — the migration creates columns + indexes but adds **no trigger or grant that blocks UPDATE/DELETE** (over-claimed in an earlier draft, corrected). (b) No runtime consumer verified; a stale `granted` row stays indexed after a revoke, so the partial index alone doesn't identify the *currently valid* grant. (c) No processing-by-purpose-by-lawful-basis inventory (contract / legal obligation / legitimate interest, not just consent). Mechanism partial, coverage ⚠️ unverified | 🟡 PARTIAL |
| **Purpose limitation (Art. 28, not Art. 21)** | `purpose_key` column scopes consent to a purpose | No enforcement that processing checks the matching purpose grant before acting | 🟡 PARTIAL |
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
| **PII detection + outbound redaction** | `middleware/pii_scanner.py` — Presidio recognizers for KTP, NPWP (old 15 + new 16-digit), passport, +62 phone, email; violations → `pii_violations` (`migration_114a`) | 🟡 **PARTIAL, not general DLP** (corrected): the scanner covers only JSON responses of `/api/agentic/*` and a few top-level fields; nested objects, arrays, streaming, non-JSON text, and other endpoints pass uncovered, the middleware is optional, and the violation store degrades silently. Best-effort guardrail on a narrow surface, not reliable breach detection |
| **Error-tracking PII redaction** | `sentry_config.py::_before_send` | 🟡 PARTIAL — reliably scrubs known **keys** (email/client_id/name/etc.); free-text bodies are only best-effort, so a KTP/NPWP embedded in prose can still slip. Load-bearing but not a proof that all egress is PII-free |
| **Local-sovereign PII processing** | OCR / vision on-Pro local (`qwen2.5vl:7b`); `cloud_vision_gate` is an **operational fail-closed flag** (not a technical classifier that blocks PII when the gate is open); raw WA mirror Pro-bound by choice (Law 2) | 🟢 PRESENT (gate is a policy control, not egress DLP) |
| **Access control on mutating APIs** | JWT middleware authenticates all non-public routes; the 65 nude routes are now down to 48 (17 R3 gated this campaign, PR #2304 merged) | 🟡 IN PROGRESS |
| **Secret management** | Fly secrets; the public-repo admin keys `zantara-secret-2024`/`admin-key-2024` were rotated + revoked in prod 2026-07-12 (#2296, 401 verified live) and the legacy allowlist is now **empty** (`api_key_auth.py::_LEGACY_ADMIN_KEYS = frozenset()`, on main) | 🟢 PRESENT (post-rotation; an adversarial pass flagged a stale hardcoded key, but that was the pre-#2296 snapshot — corrected on main) |

## 4. Cross-border transfer (UU PDP Art. 56)

PII in transit/at-rest touches foreign-hosted subprocessors. **Art. 56 is a strict hierarchy, not a
menu** (corrected after adversarial review): (1) transfer to a country with *adequate* protection; (2)
absent adequacy, *adequate binding safeguards*; (3) only if both are unavailable, data-subject consent.
"Safeguards + consent" as co-equal was wrong. The mechanism must be picked **per transfer** (destination
+ subprocessor + effective guarantee), not per vendor list. Note also vendor domicile ≠ processing
location: Fly's `primary_region` is **Singapore** (`apps/backend-rag/fly.toml`), not the US.

| Subprocessor | Role | PII exposure | Safeguard status |
|---|---|---|---|
| **Fly.io (Singapore region)** | app + Postgres host | client PII at rest in Postgres | needs DPA on file — ⚠️ unverified |
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
| **Code-side security controls** (secret mgmt, local sovereignty) | 🟢 present; but PII redaction is a **narrow best-effort guardrail**, not general DLP (see §3) |
| **Consent + audit mechanisms** | 🟡 built as DB structure, **not proven immutable, no runtime consumer verified** |
| **Data-subject rights (DSAR, unified erasure, objection)** | 🔴 the biggest gap — no subject-facing endpoints; existing "delete" is **soft-delete** (sets `inactive/deleted_at`, keeps the Drive file) |
| **Paper trail (DPAs, subprocessor register, PSE registration, breach runbook)** | 🔴/⚠️ largely absent — business/legal work, not code |
| **Uncovered obligation classes** (flagged by adversarial review) | 🔴 DPIA (Art. 34, triggered by AI/OCR/large-scale), DPO (Art. 53), written subprocessor authorization (Art. 51), portability (Art. 13), objection to automated decisions (Art. 10), retention schedule + erasure propagation — none mapped here |

**Buildable next actions (not decisions):**
1. A DSAR/erasure endpoint that spans clients + interactions + consent + Drive + Qdrant — and it must do a **hard** delete/anonymize (the current path is soft-delete + Drive-file-retained), with identity verification, legal-hold exceptions, processor-side deletion, and completion notice.
2. A subprocessor register file (`docs/compliance/subprocessors.md`) + breach-notification runbook.
3. An immutability guarantee on `client_consent_log` (trigger or revoked-grant permissions) + a runtime consumer that writes a grant before PII processing — today the table is structure-only.

**One DECISION for Zero + counsel (genuinely not mine):** whether Bali Zero's public-serving systems cross the PSE Lingkup Privat obligation under **PP 71/2019 Art. 2(5) + Art. 6** and Permenkominfo 5/2020 Art. 2 — applicability is *prima facie probable*, and registration may already exist in Komdigi's external portal (absence in the repo ≠ non-registration). The matrix scopes it; it does not resolve it.

## Adversarial review

**Reviewer:** `codex` (GPT-5.5, ChatGPT Pro) — a seat distinct from the author (Claude), satisfying generator ≠ grader. Run read-only against this file + the repo at `2c64a2587a` on 2026-07-12.

**Verdict: FLAWED (first pass) → corrections applied.** The refuter confirmed the *substantive* conclusions hold — the DSAR / unified-erasure / breach-runbook / subprocessor-register gaps are real, and PSE applicability is prima-facie probable — but found genuine defects, all fixed above:

- **§0 cited the wrong PSE clause** — PP 71/2019 Art. 2(3) is *public* PSE; private is Art. 2(5), registration Art. 6. Corrected. Also added "no repo artifact ≠ not registered (external OSS/PSE portal)".
- **UU PDP citations imprecise** — purpose limitation is Art. 28 (not 21); Art. 20 lists 6 lawful bases (consent is one); Art. 56 cross-border is a strict hierarchy (adequacy → binding safeguards → consent), not "safeguards + consent"; Arts. 67-68 are *criminal* (intentional misuse), while ordinary controller shortfalls are *administrative* Art. 57. All corrected.
- **Over-claimed 🟢 controls** — `client_consent_log` is not proven append-only/immutable (no trigger/grant blocks UPDATE/DELETE) and has no verified runtime consumer; `pii_scanner` covers only `/api/agentic/*` JSON (not general DLP); Sentry scrubs keys, not free-text PII. All downgraded to 🟡 with the real scope.
- **Factual error** — Fly region is Singapore (`fly.toml`), not US. Corrected.
- **Missed obligations** — DPIA (Art. 34), DPO (Art. 53), Art. 51 subprocessor authorization, Art. 13 portability, Art. 10 objection-to-automated-decisions. Added as an explicit 🔴 row.
- **W90 note** — the refuter flagged a stale hardcoded admin key at the reviewed snapshot; that was the pre-#2296 state. On main the allowlist is empty and the keys are revoked (401 verified live) — the "secret rotated" claim is accurate on main, and the row now says so.

The one thing not fully resolved in-doc (deliberately): a complete processing-by-purpose-by-lawful-basis inventory and the full PP 71/2019 operational-obligation set (SLA, security agreements, risk management) — those are compliance-program work beyond a repo-evidence matrix, and are named as out-of-scope rather than silently omitted.
