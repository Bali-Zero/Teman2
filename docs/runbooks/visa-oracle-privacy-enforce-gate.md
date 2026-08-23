# Visa Oracle privacy and ENFORCE gate

Last verified: 2026-08-06 on Mini against `nuzantara-rag` / production
PostgreSQL, read-only.

Authority: `docs/policies/visa-oracle-privacy-policy-v1.md` and its adjacent
JSON record.

## Current verdict

**NO-GO for ENFORCE.** Production is correctly still `SHADOW`. Trust-store,
fingerprint/HMAC, driver-token and mode secrets exist, so Zero does not need to
generate replacement keys for this gate. The remaining production change is a
controlled database/operations ceremony, not a UI decision.

Read-only observation found:

- migrations 251, 253 and 254 applied; 264 is not applied;
- `visa_activation_executor` exists as `NOLOGIN`, but has direct `SELECT` and
  `INSERT` on `visa_rule_packs`;
- the runtime role `backend_rag_v2` can directly insert activation rows;
- activation and mutation functions are still owned by `backend_rag_v2`;
- `visa_ledger_owner` does not exist.

These are latent while mode is SHADOW, but are hard ENFORCE blockers.

## Approved values

| Control            | Value                                                                    | Operational owner       |
| ------------------ | ------------------------------------------------------------------------ | ----------------------- |
| Decision retention | 30 days from `evaluated_at`                                              | Privacy owner           |
| Idempotency        | 24 hours                                                                 | Backend owner           |
| PII-free telemetry | 365 days (12 months, DPIA V2 §A ruling 2026-08-20, signed §8 2026-08-23) | Product analytics owner |
| Retention cadence  | Every 15 minutes                                                         | Infra/on-call           |
| Purge-lag alert    | Any backlog remaining after a run, or lag over 60 minutes                | Infra/on-call           |
| DSR SLA            | 3 x 24 hours                                                             | Privacy owner           |
| Legal-hold review  | Every 30 days                                                            | Legal/privacy owner     |
| CRM / WhatsApp     | Separate explicit opt-ins                                                | Product owner           |
| Minor              | Parent/guardian confirmation; otherwise human review                     | Privacy/product owner   |
| DPIA               | Approved before ENFORCE                                                  | Zero + privacy owner    |

## Change order

Perform the steps in staging first. Production changes require an approved
window and backup/restore confirmation. Do not combine the steps with an
ENFORCE flip.

### 1. Apply schema through migration 267

Migrations 264–266 add the unseeded policy authority, retention binding,
bounded purge, aggregate evidence, DSR erasure, legal hold and decision backlog
evidence. Migration 267 adds the atomic, bounded replacement of a complete
activation set for signed legal-period corrections. Migration 264 deliberately
seeds no production duration, so applying the schema remains fail-closed until
the approved policy is registered.

Run the normal migration mechanism. Do not paste only selected statements.
Afterward, confirm all four functions exist:

```sql
SELECT to_regprocedure('public.purge_visa_decisions(integer,text)'),
       to_regprocedure('public.erase_visa_decision_for_dsr(uuid,text,text)'),
       to_regprocedure('public.visa_replace_activation_set(uuid[],text,text)'),
       to_regprocedure(
         'public.set_visa_decision_legal_hold(uuid,boolean,text,text,text,text,timestamp with time zone)'
       );
```

### 2. Repair ownership and capabilities

Provision these `NOLOGIN`, non-superuser capability roles:

| Role                       | Allowed                                                                                | Forbidden                                     |
| -------------------------- | -------------------------------------------------------------------------------------- | --------------------------------------------- |
| `visa_ledger_owner`        | Own Visa Oracle tables, triggers and SECURITY DEFINER functions                        | LOGIN; serving traffic                        |
| `visa_pack_writer`         | `SELECT`/`INSERT` immutable signed packs                                               | activation execution; activation-table writes |
| `visa_activation_executor` | `EXECUTE visa_activate_rule_pack` and `visa_replace_activation_set` only               | any direct pack/activation table privilege    |
| `visa_policy_writer`       | read/insert approved policy; close a prior effective period during a reviewed rotation | delete policy; serving traffic                |
| `visa_retention_executor`  | read the non-PII approved policy row; execute purge/evidence functions                 | every other direct table privilege            |
| `visa_privacy_operator`    | execute legal-hold and DSR functions                                                   | direct decision/payload/idempotency DML       |

The runtime role keeps only the reads and writes used by evaluation:

- `SELECT` active signed packs/activations;
- `INSERT`/`SELECT` decision audit rows required by the actual writer;
- `SELECT`/`INSERT`/completion-only `UPDATE` on idempotency rows;
- `EXECUTE prepare_visa_evaluate_idempotency_reservation`.

It must not own Visa Oracle relations/functions, activate a pack, write an
activation row, register a policy, run retention, change a hold or run DSR
erasure.

Use different login principals for pack write and activation. No login may be
a member of both capability roles. This preserves the two-person boundary: a
compromised pack writer cannot make its inserted pack active, and a compromised
activator cannot insert a new pack.

Run the read-only gate after provisioning:

```bash
cd apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. VISA_ENGINE_PREFLIGHT_DATABASE_URL="$READ_ONLY_DSN" \
  python -m backend.scripts.visa_engine.operational_preflight
```

Exit `0` is required. Exit `2` means ENFORCE remains blocked. The preflight is
safe against production because it performs no writes and never logs a DSN.
It evaluates an explicit EXECUTE allowlist across every activation,
idempotency, retention, evidence, DSR and legal-hold function; an exact table-
privilege allowlist across all governed Visa Oracle tables; and runtime membership in
every operational capability role. The table matrix includes PostgreSQL 17's
`MAINTAIN` privilege without breaking the PostgreSQL 15 CI harness. A missing
required grant and an unexpected grant both fail the gate.

Signed legal-period corrections use the offline
`backend.scripts.visa_engine.replace_activation_set` ceremony. It accepts at
most 64 separately signed segments, rejects duplicate/ambiguous JSON and
oversized bundles, verifies Ed25519 plus the supplied chain head, preflights
both separated identities before inserting, closes the pack-writer pool, then
lets the database re-check exact coverage, sequence/hash continuity and the
single-clock replacement atomically. Its dry run deliberately makes no claim
about live DB coverage.

### 3. Register Privacy Policy V1

Choose `effective-from` at the actual policy change window; never backdate it
to the conversation approval time. Validate first:

```bash
cd apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. python -m backend.scripts.visa_engine.register_privacy_policy \
  --effective-from 2026-08-10T02:00:00+00:00
```

Then repeat with `--apply` and a separated policy-writer DSN in
`VISA_ENGINE_POLICY_WRITER_DATABASE_URL`. The tool rejects the runtime role and
superuser sessions and is idempotent only when every immutable value matches.

### 4. Arm retention outside the API process

Schedule every 15 minutes using a dedicated retention login/capability. First
run evidence-only, then `--apply`:

```bash
cd apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. python -m backend.scripts.visa_engine.retention_worker

PYTHONPATH=. python -m backend.scripts.visa_engine.retention_worker --apply
```

The DSN comes only from `VISA_ENGINE_RETENTION_DATABASE_URL`. Exit `2` pages
on-call. Logs contain aggregate counts, held-expired count and lag only; no
answer, nationality, passport, request, response or decision identifier.

The scheduler must alert on missed executions as well as command exit status.
Use a 30-minute missed-run warning and a 60-minute critical threshold. Legal
holds appear separately and do not count as a purgeable backlog.

The repository-ready LaunchAgent example and Cell sensor are documented in
`docs/runbooks/visa-oracle-retention-operations.md`. The manifest is dry-run
and uninstalled. It intentionally performs zero immediate retries: backlog or
lag exit `2` must page rather than being retried until the evidence disappears;
the next bounded attempt is the next 15-minute tick.

### 5. Enforce the 365-day (12-month) analytics deletion

The frontend now omits generic user/session identifiers and sends only the Visa
Oracle field allowlist. Before enabling its analytics endpoint, configure the
destination dataset with a 365-day TTL/deletion job and prove deletion with a
synthetic event older than 365 days (corrected 2026-08-23: supersedes the old
90-day provisional per Zero's 2026-08-20 retention ruling, DPIA V2 §A,
`docs/audits/2026-08-20-visa-oracle-dpia-v2.md`, signed §8 2026-08-23). If the
destination cannot enforce a Visa-specific TTL, keep
`NEXT_PUBLIC_ANALYTICS_ENDPOINT` unset for this surface; no telemetry is safer
than over-retention.

### 6. Operate DSR and legal hold

Receive DSRs at `privacy@balizero.com`, assign an opaque case token, verify the
requester proportionately and keep identity evidence out of tickets/logs. Use
the engine `decision_id` supplied with the result; never search by passport,
nationality or family facts in engineering tools.

Every command is a dry run until `--apply`:

```bash
cd apps/backend-rag
source .venv/bin/activate

PYTHONPATH=. python -m backend.scripts.visa_engine.privacy_ops hold \
  --decision-id "$DECISION_ID" --case-reference DSR-2026-001 \
  --actor privacy.operator --reason-code LEGAL-CLAIM-PRESERVATION \
  --approved-by privacy.approver \
  --review-due-at 2026-09-04T00:00:00+08:00

PYTHONPATH=. python -m backend.scripts.visa_engine.privacy_ops release \
  --decision-id "$DECISION_ID" --case-reference DSR-2026-001 \
  --actor privacy.operator --reason-code CLAIM-CLOSED \
  --approved-by privacy.approver

PYTHONPATH=. python -m backend.scripts.visa_engine.privacy_ops erase \
  --decision-id "$DECISION_ID" --case-reference DSR-2026-001 \
  --actor privacy.operator
```

With `--apply`, the DSN must be in
`VISA_ENGINE_PRIVACY_OPERATOR_DATABASE_URL`. Erasure deletes the decision,
encrypted payload and matching unexpired replay atomically. It returns exit `2`
when the record is already absent and fails when a legal hold is active. Audit
evidence stores aggregate counts and the opaque case token, never the decision
identifier.

A hold command is rejected unless it includes an opaque reason code, a
separate approver and a timezone-aware review deadline no later than the
policy's 30-day review interval. A release is independently audited and cannot
carry a future review deadline.

### 7. Complete and approve the DPIA

Use `docs/audits/2026-08-20-visa-oracle-dpia-v2.md` as the evidence packet
(corrected 2026-08-23: supersedes `docs/audits/2026-08-06-visa-oracle-dpia-v1.md`,
which stays on disk as the incorporated baseline record — V2 references its
processing description, data-flow table and rights/deletion model rather than
restating them). Its §8 is signed: Product owner (Zero) in person, 2026-08-23;
the Privacy/DPO and Security/Infra owner lines are recorded as adopted on Zero's
instruction, not personally executed (§8 provenance note). Signing approved the
assessment — it does not authorize ENFORCE. Two High residual risks stay open
per §8/§D and keep mode in SHADOW: the analytics destination behind
`NEXT_PUBLIC_ANALYTICS_ENDPOINT` is still unidentified, and the cross-border
processor/subprocessor register (Annex 1) is still `OPEN`/`UNKNOWN`.
The signed DPIA must name:

- controller, processors, storage regions and cross-border safeguards;
- data categories and exact purpose/lawful basis for evaluation, WhatsApp and
  CRM separately;
- automated triage impact, abstention/human-review controls and the fact that
  the tool never grants a visa;
- minors and guardian-consent path;
- threat model for signed RulePacks, HMACs, replay, rollback, DB failure,
  unauthorized activation and DSR abuse;
- 30-day/24-hour/365-day deletion evidence and legal-hold exceptions (the
  telemetry figure is 365 days, not 90 — DPIA V2 §A, signed §8 2026-08-23);
- residual risks, owners, due dates and Zero's approval.

Any open high risk keeps mode in SHADOW. Store the signed PDF immutably with
content hash and approval reference; do not store it in the public source KB.

### 8. Production smoke before mode change

While production is still SHADOW:

1. run the privilege preflight and evidence-only retention worker;
2. verify one supported fixture, one `NEEDS_INPUT`, one
   `HUMAN_REVIEW_REQUIRED`, one `NO_SUPPORTED_PATH` and one controlled outage;
3. confirm no fallback candidate appears on timeout/DB failure;
4. confirm prices come from exact PricingTool identities only;
5. run desktop/mobile, keyboard and reduced-motion Playwright;
6. verify logs contain none of the raw test answers;
7. obtain independent review with no BLOCKER or MEDIUM.

Only after that evidence packet is signed may the separate mode-change window
be proposed. ENFORCE change, canary, rollback and post-change monitoring are a
new explicit authorization; this runbook does not perform them.

## Zero's remaining actions

Zero does not need to operate CLI or generate keys now. Zero has two approval
actions later:

1. approve the completed DPIA/residual-risk record;
2. approve the separate ENFORCE change window after the smoke and independent
   gate are green.

Engineering/Infra owns migrations, roles, credentials, scheduler, telemetry
TTL and evidence collection.
