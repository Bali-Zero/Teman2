# Visa Oracle V2 — Data Protection Impact Assessment V2

Status: **DRAFT FOR SIGNATURE / STILL NO-GO FOR ENFORCE**

- Assessment date: 2026-08-20
- Supersedes: `docs/audits/2026-08-06-visa-oracle-dpia-v1.md` (V1 remains on disk as the
  baseline record; this V2 attaches the closure evidence V1 demanded and records the
  owner's retention ruling)
- Privacy authority: `docs/policies/visa-oracle-privacy-policy-v1.json`
- Product owner: Zero
- Controller legal entity: **PT Bali Nol Impresariat** (Zero ruling, 2026-08-23, Legge 5)
- Privacy/DPO owner: **Zainal Abidin** (Zero ruling, 2026-08-23, Legge 5)
- Incident contacts: **OPEN — Zero must name them before approval**

V1's processing description (§1), data-flow table (§2), affected-people analysis (§3),
automated-triage safeguards (§4) and rights/deletion model (§5) remain accurate and are
incorporated by reference — nothing in the engine's data flow changed between 2026-08-06
and 2026-08-20 except the addition of two protective controls (the weekly re-attestation
lane and the freshness sentinel, §C below). This V2 exists to do three things V1 could
not:

1. attach the §7 closure evidence that has since been produced, with receipts;
2. record the owner's analytics/telemetry retention ruling of 2026-08-20;
3. re-score the residual-risk rows whose "High until X is armed" conditions have since
   been armed — and say plainly which rows have NOT moved.

## A. Owner retention ruling (2026-08-20)

On 2026-08-20 Zero ruled on the telemetry TTL question V1 left open ("per TTL quanto e'
di solito il tempo? 1 anno?" — confirming the session's proposal):

- **Analytics/product telemetry retention: 12 months** from event time. Reference point:
  the CNIL's 13-month ceiling for analytics identifiers is the widely used benchmark;
  12 months sits inside it and matches the product's genuine need (year-over-year
  seasonality of visa demand). This replaces V1's provisional "destination deletion at
  90 days must be proven before use" wording — the binding number is now 12 months,
  and the proof obligation is unchanged in kind: **the destination must be identified
  and its 12-month deletion must be evidenced before ENFORCE**.
  **Known enforcement-vehicle conflict (disclosed, adversarial finding):** the existing
  attestation contract is hard-locked to the old provisional number — the runbook
  mandates "exactly 90 days" and `scripts/visa_oracle_analytics_retention_preflight.py`
  hard-codes `EXPECTED_TTL_DAYS = 90` and rejects anything else — so a 12-month
  attestation **cannot pass the cited gate today**. Executing this ruling therefore
  REQUIRES amending both the runbook's evidence contract and the preflight constant to
  12 months; that amendment is a named session task in §E, gated on Zero's §8 signature
  (amending an enforcement gate before the ruling it implements is signed would be the
  gate drifting ahead of its authority).
- **Durable audit ledger: unchanged and untouched by this ruling** — the policy-bound
  30-day deletion for decision projections and 24-hour replay-binding retention are
  migration-enforced (264/266/268) and are NOT loosened to 12 months. The 12-month
  figure applies to the PII-free telemetry stream only.
- This section becomes binding when Zero signs §8; until then it is the recorded
  ruling awaiting signature, and SHADOW continues.

## B. §7 closure evidence — item by item

V1 §7 listed 8 mandatory attachments. State as of 2026-08-20, each with its receipt:

| #   | V1 requirement                                                                                                 | State                                                                   | Evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| --- | -------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Controller entity, privacy owner, incident contacts                                                            | **CLOSED for entity+DPO (2026-08-23); incident contacts OPEN — Zero**   | Business facts only Zero can record; slots in the header above.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| 2   | Processor/subprocessor register                                                                                | **DRAFTED (Annex 1 below), two rows still UNKNOWN**                     | Annex 1; the analytics destination row is the same Blocker the retention runbook names in its blocker table (`docs/runbooks/visa-oracle-retention-operations.md`, "Analytics destination                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | UNKNOWN" row). |
| 3   | Migrations 264–266 applied + Privacy Policy V1 registration                                                    | **CLOSED**                                                              | Migrations 264–267 applied in production, 268 hand-cured then codified (`.agents/skills/visaoracle/CURRENT_STATE.md:754-757`); policy registered via `register_privacy_policy.py` ceremony with retention-gate query `count=1` for `environment=PRODUCTION` (`CURRENT_STATE.md:619-624`).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| 4   | Privilege preflight, no combined pack-write/activation login                                                   | **CLOSED**                                                              | `operational_preflight.py:301-320` (`membership:no-pack-writer-activation-combination`), enforced at activation by `activate_pack.py:166-193` (`session_user`-bound, refuses combined or superuser logins in PRODUCTION); production preflight green (`CURRENT_STATE.md:616-618`); every activation since (seq-3, 10, 11) ran with distinct ephemeral roles minted and dropped inside the ceremony.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| 5   | Scheduler, missed-run, purge-lag, telemetry-deletion evidence                                                  | **CLOSED for the database retention half; OPEN for the analytics half** | Retention scheduler installed on Mini (15-min LaunchAgent); `VISA_ORACLE_RETENTION_APPLY=true` (real-deletion mode) armed at 16:01:37Z on 2026-08-08 and healthy since — first runs were clean no-ops with 0 expired rows, so the capability is armed but no nonzero deletion event is yet attested (`CURRENT_STATE.md:627-637`). Analytics half: destination still unidentified; 12-month TTL now ruled (§A) but unattestable until the destination is named AND the attestation gate is amended (§A conflict).                                                                                                                                                                                                                                                                                                                                                                                                                        |
| 6   | DSR/legal-hold tabletop (wrong-ID, active-hold, absent-record)                                                 | **PARTIAL**                                                             | Automated coverage exists and is strong: `test_evaluate_endpoint.py:4103` proves active-hold blocks erasure, hold→release→erase, and idempotent re-erase of an absent record. Missing: a _distinct_ wrong-ID scenario and a _documented human tabletop_ record. Small, named task — not evidence that the mechanism is unsafe, evidence that the rehearsal record V1 demanded has not been produced.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| 7   | SHADOW production smoke: five terminal states, network/DB failure, PII-free logs, desktop/mobile accessibility | **PARTIAL (4 of 5 states; two sub-requirements unevidenced)**           | `TEMPORARILY_UNAVAILABLE` proven by the kill-switch drill (SHADOW→OFF 16:10:50Z → verified fail-closed 16:12:28Z → restored and verified 16:13:44Z, all 4 machines — `CURRENT_STATE.md:648-660`); `SUPPORTED_CANDIDATES` and `HUMAN_REVIEW_REQUIRED` cited in live smokes on 2026-08-19/20 (seq-10/11 ship records, visaoracle SKILL LIVE STATE); `NEEDS_INPUT` last proven live in the seq-6 smoke of 2026-08-10 (SKILL LIVE STATE). **`NO_SUPPORTED_PATH` has never been observed in a production smoke** — open item, to be attempted in the next ceremony's smoke set; if the state is not reachable with a crafted fact set, that finding itself gets recorded here instead. **V1 also required PII-free-logs and desktop/mobile-accessibility smoke evidence: neither has a post-2026-08-08 production record — both stay OPEN in §E (they were silently absent from this table's first draft; restored on adversarial review).** |
| 8   | Independent review, no BLOCKER/MEDIUM                                                                          | **CLOSED for the reviewed baseline; rolling for later increments**      | 2026-08-07 delivery `e15fc1b84501...` independently reviewed at 0 BLOCKER / 0 MEDIUM (`CURRENT_STATE.md`, V2-completion entry). Later pack increments, precisely: seq-10 carried the inc1-4 capture docs (`research/visa/doctrine-factory/e5/`, `adversarial_review: codex`); seq-12 carries the inc5 capture (`adversarial_review: kimi-k3`, in PR #4409); seq-11 was a minimal pricing-key fold with no source-claim surface — its gate was CI + AI review + 26/26 pricing-resolution tests, not a QW-5 capture.                                                                                                                                                                                                                                                                                                                                                                                                                      |

## C. Controls added since V1 (they move risk rows, so they belong in the DPIA)

**Arming status disclosed (adversarial finding at assessment time): both controls below
existed as OPEN, armed PRs when this V2 was drafted — built is not armed.** Neither may
be counted toward a residual-risk move until its PR is MERGED and, for the sentinel,
the cron is INSTALLED and heart-beating on Pro. The signer must re-verify both statuses
at §8 time; §D's contingent rows say so explicitly.

1. **Weekly re-attestation lane** (first execution assembled as RulePack seq-12, PR
   #4409, 2026-08-20): every OFFICIAL_PORTAL source record is re-verified against the
   live page by the QW-5 method (verbatim quotes per record, cross-family adversarial
   review) and re-stamped BEFORE its 7-day freshness window closes. Pre-expiry by
   design: zero abstain gap. Not complete until seq-12 is signed AND activated.
2. **Freshness sentinel** (`scripts/visa_freshness_sentinel.py`, PR #4410): a 6-hourly
   cron that alerts Telegram ~48h before the ACTIVE pack's oldest portal stamp crosses
   `max_age_seconds`, reading the activation truth from the bitemporal ledger (disk
   fallback explicitly labelled as a proxy; DB-unreachable is a distinct cannot-verify
   state, never a silent green). A missed re-attestation week can no longer pass
   silently — once installed on Pro (post-merge deploy step, PENDING-ARMS ledgered).

Both controls protect the _availability and honesty_ of the abstention machinery — they
make the fail-closed posture sustainable instead of one-shot. Neither adds a new data
flow: the sentinel reads pack metadata (no applicant data) and alerts contain source
record identifiers only.

## D. Risk table — what moved and what did not

Referencing V1 §6 rows verbatim:

| V1 row                                                     | V1 residual                        | V2 residual                                       | Why                                                                                                                                                                                                                                                                                                          |
| ---------------------------------------------------------- | ---------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Raw facts leak through logs/analytics                      | High until destination proven      | **High — UNCHANGED**                              | The destination is still unidentified; the 12-month ruling (§A) defines the target but attests nothing. This row is the single largest remaining ENFORCE blocker on the privacy side.                                                                                                                        |
| Durable records outlive approved purpose                   | High until scheduler armed         | **Low-Medium**                                    | Scheduler in apply-mode and healthy since 2026-08-08 (receipt in §B.5 — deletion capability armed, first runs clean no-ops); migrations enforce the deadlines. The sentinel/re-attestation contribution is CONTINGENT on #4409/#4410 landing (§C). Residual: analytics half of retention still open.         |
| Unauthorized pack activation or data mutation              | High (privilege inspection failed) | **Medium**                                        | Privilege preflight green in production; combined-login refusal enforced in code at activation; ephemeral per-ceremony roles used in every activation since. Residual: periodic re-run of the preflight is manual.                                                                                           |
| Replay/rollback or stale authority re-enables unsafe rules | Medium after key/alert evidence    | **Low-Medium (core) — freshness half CONTINGENT** | Anti-rollback chain proven across three consecutive live ceremonies (seq-3→10→11) — that core evidence alone carries the move. The freshness half (weekly lane + sentinel) counts only once #4409/#4410 merge and the sentinel is installed (§C).                                                            |
| Child case automated handoff                               | Medium                             | **Medium — UNCHANGED**                            | `review.minor-without-guardian` remains armed; its sourcing defect (the E30A page never mentions minors/guardians) is disclosed and ledgered, re-confirmed 2026-08-20 — the rule still fails safe (forces review), so the defect does not weaken the control; guardian wording/SOP validation still pending. |
| Unsupported recommendation causes harm                     | Medium                             | **Medium — UNCHANGED**                            | Structurally bounded by the deterministic engine; moves only with ENFORCE-gate evidence (G-a/G-b/G-c volumes), not with paperwork.                                                                                                                                                                           |
| DSR erases wrong record / exposes identity                 | Medium after rehearsal             | **Medium — rehearsal still missing**              | §B.6: automated proofs strong, human tabletop record absent.                                                                                                                                                                                                                                                 |
| Cross-border obligations incomplete                        | High                               | **High — UNCHANGED**                              | Annex 1 drafts the register, but contracts/safeguards/controller identity are Zero-side facts; unsigned = open.                                                                                                                                                                                              |
| Network/DB outage fabricates a result                      | Low after smoke                    | **Low**                                           | Kill-switch drill + fail-closed `TEMPORARILY_UNAVAILABLE` proven live.                                                                                                                                                                                                                                       |

## E. What remains before §8 can be signed (the honest short list)

1. **Zero**: controller legal entity + DPO/privacy owner — **DONE 2026-08-23** (header
   above). Incident contacts remain **OPEN — Zero must name them before approval**.
2. **Zero + session**: identify the real analytics destination behind
   `NEXT_PUBLIC_ANALYTICS_ENDPOINT`; then the session produces the 12-month deletion
   attestation per the runbook contract. Until then the telemetry row stays High.
3. **Session**: complete Annex 1's two UNKNOWN rows once (2) is answered; produce the
   DSR tabletop record (wrong-ID + active-hold + absent-record, two-person, documented);
   attempt `NO_SUPPORTED_PATH` in the next ceremony smoke and record the outcome either
   way; produce the two V1 §7.7 sub-requirements this V2's first draft dropped and the
   adversarial review restored — a PII-free-logs production smoke record and a
   desktop/mobile accessibility evidence record.
4. **Session, gated on §8 signature — PREPARED, NOT MERGED (PR #TBD-THIS-PR)**: amends the
   analytics-TTL attestation vehicle to the ruled 12 months —
   `docs/runbooks/visa-oracle-retention-operations.md` §"Evidence contract" (was "exactly
   90 days", now 365) and `scripts/visa_oracle_analytics_retention_preflight.py`
   (`EXPECTED_TTL_DAYS` was 90, now 365), citing this DPIA §A as the authority, with
   guilt+innocence tests proving a 12-month attestation now passes and a 90-day one is
   now rejected. The PR is deliberately held unarmed (no auto-merge) and merges only
   after §8 below is signed — amending the gate's diff before the signature is fine to
   prepare, but flipping it live ahead of the ruling's own signature would be the gate
   drifting ahead of its authority, so the merge itself is the gated step, not the diff.
5. **Session — DONE (this PR)**: ledgered the 2026-08-20 TTL ruling in the modus
   PENDING-ARMS ledger (the other two same-day rulings were already ledgered; this row
   references PR #TBD-THIS-PR as the prepared-but-gated amendment and stays OPEN until §8 is
   signed and the PR merges).
6. **Signatures (§8 below, this file)**: Privacy/DPO owner, Security/Infra owner,
   Product owner (Zero). Approval closes the privacy-impact gate ONLY — the ENFORCE flip
   remains a separate authorization behind the objective G-a/G-b/G-c/G-d gate. This
   section supersedes V1 §8 as the operative signing block; V1 §8 stays on disk
   unchanged, as the historical record it always was.

## 8. Decision and signatures

Current decision: **DO NOT ENFORCE — open high residual risks remain** (Annex 1's
analytics-destination row and the cross-border processor register are both still
`OPEN`/`UNKNOWN`; see §D).

Signing this section approves the DPIA V2 privacy-impact assessment as of 2026-08-20/23
and its §A retention ruling. It does **not** authorize `VISA_ENGINE_EVALUATE_MODE=ENFORCE`
— that stays a separate, later authorization gated on the objective G-a/G-b/G-c/G-d
volumes (§7 item 8 / independent review), evaluated on its own evidence when it comes up.

By signing, the Privacy/DPO owner and Product owner are accepting the residual risks
recorded in §D as of this assessment, in particular the two rows still scored **High —
UNCHANGED**: raw facts leaking through logs/analytics until the destination is proven
(§D row 1), and the cross-border processor/subprocessor register being incomplete until
Annex 1's `OPEN` contract/safeguard cells are filled (§D row 8) — plus the Medium rows
still open (child-case handoff sourcing defect, DSR rehearsal record missing, structural
bound on unsupported-recommendation harm).

- Controller legal entity: PT Bali Nol Impresariat
- Privacy/DPO owner: Zainal Abidin
- Privacy/DPO owner signature: ____________________ Date: __________ Decision: ________
- Security/Infra owner signature: __________________ Date: __________ Decision: ________
- Product owner (Zero) signature: _________________ Date: __________ Decision: ________

## Annex 1 — Processor / subprocessor register (draft)

Regions and roles read from live configuration where possible; contract/safeguard
columns are deliberately empty where only Zero can attest them.

| Processor                       | Role                                                                                                | Data touched                                                                                  | Region (evidence)                            | Retention                                                                                                                    | Transfer basis / contract |
| ------------------------------- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| Fly.io (app `nuzantara-rag`)    | Backend hosting                                                                                     | Structured facts in transit; decision projections                                             | `sin` — Singapore (fly.toml primary region)  | Ephemeral (compute)                                                                                                          | **OPEN — Zero**           |
| Fly.io (`nuzantara-postgres`)   | Database                                                                                            | Durable audit (30d), replay bindings (24h), retention/hold ledgers                            | `sin` (same platform)                        | Migration-enforced (264/266/268)                                                                                             | **OPEN — Zero**           |
| Tigris (via Fly)                | DB backup storage                                                                                   | Encrypted backups of the above                                                                | Fly-adjacent object storage                  | Daily cycle; WAL archiving re-enabled 2026-08-09 (recorded in the repository's own `CLAUDE.md` §11 deploy-lifecycle section) | **OPEN — Zero**           |
| Vercel                          | Frontend hosting                                                                                    | No applicant payloads at rest; serves the interview UI                                        | Global edge (project `nuzantara-2026` scope) | N/A (static/edge)                                                                                                            | **OPEN — Zero**           |
| Sentry (org `Bali-Zero/Teman2`) | Error telemetry                                                                                     | Redacted exceptions ONLY — `_before_send` PII redaction is load-bearing (`sentry_config.py`)  | US cloud (free tier)                         | Sentry default (90d events)                                                                                                  | **OPEN — Zero**           |
| Analytics destination           | Product telemetry (PII-free allowlist: event, state, correlation hash, pack hash, frontend version) | **UNKNOWN — `NEXT_PUBLIC_ANALYTICS_ENDPOINT` does not identify a provider/dataset. BLOCKER.** | UNKNOWN                                      | **12 months once identified (§A ruling)**                                                                                    | **OPEN**                  |
| WhatsApp / Meta                 | Optional opt-in handoff                                                                             | Result state + opaque reference, only after separate consent                                  | Meta infrastructure                          | **UNKNOWN — provider retention to be recorded**                                                                              | **OPEN — Zero**           |
| CRM                             | Not active                                                                                          | None (future, separate consent + assessment)                                                  | —                                            | —                                                                                                                            | —                         |

## Official legal sources

- <https://www.peraturan.go.id/id/uu-no-27-tahun-2022>
- <https://jdih.komdigi.go.id/produk_hukum/view/id/832/t/undangundang%2Bnomor%2B27%2Btahun%2B2022>
- CNIL, cookies/analytics identifier guidance (13-month benchmark for analytics
  identifiers) — used as the reference ceiling for the §A ruling, not as binding
  Indonesian law.
