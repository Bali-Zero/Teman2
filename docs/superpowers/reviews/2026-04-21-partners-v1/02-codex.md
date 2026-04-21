Reading additional input from stdin...
2026-04-21T02:42:40.697179Z ERROR codex_core::codex: failed to load skill /Users/nuzantara/Desktop/partners-spec-wt/.agents/skills/bz-video-production/SKILL.md: missing YAML frontmatter delimited by ---
2026-04-21T02:42:40.697208Z ERROR codex_core::codex: failed to load skill /Users/nuzantara/Desktop/partners-spec-wt/.agents/skills/google-flow-video/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.120.0 (research preview)
--------
workdir: /Users/nuzantara/Desktop/partners-spec-wt
model: gpt-5.4
provider: openai
approval: never
sandbox: read-only
reasoning effort: xhigh
reasoning summaries: none
session id: 019dadeb-1fca-7180-bac5-35d075854f7b
--------
user
You are a senior staff engineer reviewing PR #139 (feat/crm-partners-module) for the Nuzantara CRM.

The full context (spec + all key files) is at /tmp/partners-review/brief.md — 144KB. READ THAT FILE FIRST using your Read tool, then produce a critical review.

Focus on:
1. Architectural issues that survived 10 rounds of narrow per-task review
2. Security + data-leak holes (partner-facing endpoints, email rendering, audit log)
3. Race conditions (EventBus redelivery, commission offset atomicity, email idempotency)
4. Indonesian compliance (UU PDP, PPh 21/23 placeholders, kwitansi, Permenkumham)
5. Production readiness: what fails silently on first real use?
6. Spec-level bugs surviving into implementation

Output ONLY Markdown:
- Executive verdict (ship / ship with follow-ups / block)
- Critical issues (must fix before ship) with file:line refs
- Important issues (v1.1) with file:line refs
- Observations / future work
- One-sentence summary

Be opinionated. Prior per-task reviews already caught surface bugs — focus on deeper issues.
2026-04-21T02:42:41.465911Z ERROR rmcp::transport::worker: worker quit with fatal: Transport channel closed, when Auth(TokenRefreshFailed("Server returned error response: invalid_grant: Grant not found"))
codex
[Pro] I’ll read the review brief first, then inspect the referenced files and PR context enough to ground findings in concrete line refs. Since this is a review, I’ll stay in findings mode and avoid changing code.
exec
/bin/zsh -lc "sed -n '1,260p' /tmp/partners-review/brief.md" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
# Partners Module v1 — Review Brief

You are one of 4 LLMs reviewing PR #139 (feat/crm-partners-module) of Nuzantara CRM.
The PR formalizes Bali Zero's informal third-party referral network.

## Scope

- 10 commits, 128 backend tests passing.
- Spec: docs/superpowers/specs/2026-04-20-crm-partners-module.md (included below).
- Branch: feat/crm-partners-module. Base: origin/main.

## Your Task

Do a CRITICAL review. Assume the prior per-task reviews caught most surface issues. Look for:

1. **Architectural issues** that survived 10 rounds of narrow review.
2. **Security/data-leak holes** — esp. in partner-facing endpoints + email rendering.
3. **Race conditions** — EventBus redelivery, commission offset without transaction wrapper, email idempotency under retry.
4. **Indonesian compliance**: UU PDP (partner data), PPh 21/23 (withholding), kwitansi/invoice, Permenkumham (agent referral fees).
5. **Production readiness** — what fails silently on first real use?
6. **Anything the spec got wrong** that survived into implementation (spec-level bugs don't get caught by per-file reviews).

Return Markdown with:
- Executive verdict (ship / ship with follow-ups / block)
- Critical issues (must fix before ship)
- Important issues (v1.1)
- Observations / future work
- One sentence summary

---

## Spec (full)

# CRM Partners Module — Design Spec

**Date:** 2026-04-20
**Author:** Claude Opus 4.7 (1M context) — council: Gemini 2.5 Pro + Codex
gpt-5.4 xhigh + DeepSeek-Reasoner + NotebookLM NB-2
**Status:** Design approved by Antonello. Ready for implementation plan.
**Owner of fiscal sign-off:** Asya.
**Origin:** Multi-LLM council brainstorm,
`docs/superpowers/specs/2026-04-20-partners-brainstorm/`.

## 1. Purpose

Formalize Bali Zero's informal third-party referral network (hotels, property
managers, consultants, agents) into a first-class CRM module with:

- partner anagrafica + Indonesian fiscal profile,
- referral linking to existing `processes`,
- append-only commission ledger (accrued → approved → paid, with clawback),
- team portal administration view and partner-facing portal view,
- automated welcome and commission emails via Brevo,
- full RBAC with separate finance permissions.

Council rationale: see sibling `2026-04-20-partners-brainstorm/99-synthesis.md`.

## 2. Scope

### In scope (v1)

- Three new Postgres tables + one audit table, migration **119**.
- EventBus channel `partner_commission_changed` + subscriber
  `process.completed+paid → accrual`.
- 16 backend API endpoints under `/api/partners/*`.
- Two email templates (welcome, commission-earned) via Brevo.
- Team portal routes `/portal/partners/*` (plural = admin/team view).
- Partner portal routes `/portal/partner/*` (singular = self view) with
  middleware role-gate.
- Referrer dropdown integrated into existing process UI.

### Out of scope (deferred to v2)

- `partner_commission_rules` table (per-service or per-tier rate engine).
- Bank transfer automation (Xendit / BCA / OVO integrations).
- PDF bukti potong generator + e-Bupot Unifikasi integration.
- Split commissions (multiple partners per process).
- Partner-to-partner referral chains.
- In-portal messaging.
- New subdomain `partners.balizero.com`.

### Known open items (answered by Antonello; non-blocking)

- Default commission rate `10.0` (percentage). Per-partner override at creation.
- Auto-writeoff threshold: `system_settings.partner_clawback_auto_writeoff_idr`
  default `0` (off). Asya picks real value later.
- Accountant: Asya. Gates first 3 real payouts via UI soft-gate.
- Partner admin approval required: yes
  (`onboarding_status = pending_approval` on create).
- PDP consent copy: provisional ships in welcome email template; legal
  review may bump `pdp_consent_version` without schema change.

## 3. Data model — migration 119

Postgres migration file:
`apps/backend-rag/backend/migrations/migration_119_partners.py`
(numbered after current latest: 118).

Follow existing async migration idiom (see
`migration_118_clients_referrer_url.py`):

- idempotent `DO $$ ... $$;` blocks,
- `async def apply(conn)` + `async def rollback(conn)`,
- `CREATE INDEX IF NOT EXISTS`,
- all timestamps `TIMESTAMP WITH TIME ZONE`.

### 3.1 `partners`

```sql
CREATE TABLE partners (
  id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- anagrafica
  full_name                 TEXT NOT NULL,
  work_role                 TEXT,                   -- "hotel owner", "property manager"
  company_name              TEXT,
  office_address            TEXT,
  email                     TEXT NOT NULL UNIQUE,
  phone                     TEXT,
  preferred_language        TEXT DEFAULT 'id',      -- 'id' | 'en' | 'it'

  -- fiscal (Indonesia)
  entity_type               TEXT NOT NULL
    CHECK (entity_type IN ('individual','corporate_pt','corporate_cv','foreign')),
  npwp                      TEXT,
  nik                       TEXT,
  tax_withholding_category  TEXT NOT NULL DEFAULT 'tbd'
    CHECK (tax_withholding_category IN ('pph21','pph23','exempt','tbd')),
  fiscal_address            TEXT,

  -- payment rail
  bank_name                 TEXT,
  bank_account_holder       TEXT,
  bank_account_number       TEXT,
  ewallet_type              TEXT,
  ewallet_number            TEXT,
  payment_currency          TEXT NOT NULL DEFAULT 'IDR',
  iban                      TEXT,
  payment_notes             TEXT,

  -- commission policy (v1 uses partner-level defaults)
  default_commission_type   TEXT NOT NULL DEFAULT 'percentage'
    CHECK (default_commission_type IN ('percentage','flat')),
  default_commission_value  NUMERIC(14,4) NOT NULL DEFAULT 10.0,

  -- lifecycle
  onboarding_status         TEXT NOT NULL DEFAULT 'pending_approval'
    CHECK (onboarding_status IN ('pending_approval','active','inactive')),
  assigned_to               UUID REFERENCES users(id) ON DELETE SET NULL,

  -- UU PDP + T&C
  pdp_consent_at            TIMESTAMPTZ,
  pdp_consent_version       TEXT,
  terms_accepted_at         TIMESTAMPTZ,
  terms_version             TEXT,

  -- audit + idempotency
  created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by                UUID REFERENCES users(id) ON DELETE SET NULL,
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
  deactivated_at            TIMESTAMPTZ,
  welcome_email_sent_at     TIMESTAMPTZ
);

CREATE UNIQUE INDEX idx_partners_email ON partners (email);
CREATE INDEX idx_partners_assigned_to ON partners (assigned_to)
  WHERE assigned_to IS NOT NULL;
CREATE INDEX idx_partners_onboarding_status ON partners (onboarding_status);
CREATE INDEX idx_partners_entity_type ON partners (entity_type);
```

**Email collision guardrail** (user ↔ partner mutual exclusion per Q6):
enforced at service layer, not by CHECK — the check needs a cross-table
lookup. Repository helper `Partners.assert_email_is_not_internal()` runs
on every insert and email update; raises `ConflictError` if
`users.email = partner.email AND users.role IN ('team','admin')`.

### 3.2 `partner_referrals`

```sql
CREATE TABLE partner_referrals (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  partner_id           UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
  process_id           UUID NOT NULL REFERENCES processes(id) ON DELETE RESTRICT,
  share_percent        NUMERIC(5,2) NOT NULL DEFAULT 100.00
    CHECK (share_percent > 0 AND share_percent <= 100),
  referred_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  referred_by_user_id  UUID REFERENCES users(id) ON DELETE SET NULL,
  notes                TEXT,

  CONSTRAINT partner_referrals_process_unique_v1 UNIQUE (process_id)
  -- v2: drop this constraint when enabling split commissions
);

CREATE INDEX idx_partner_referrals_partner_id ON partner_referrals (partner_id);
CREATE INDEX idx_partner_referrals_process_id ON partner_referrals (process_id);
```

### 3.3 `partner_commissions` (append-only ledger)

Append-only enforced at the repository layer: narrow `UPDATE` only on
status + fill-in fields (`approved_at`, `paid_at`, etc.); no `DELETE`.

```sql
CREATE TABLE partner_commissions (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  partner_id               UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
  referral_id              UUID REFERENCES partner_referrals(id) ON DELETE RESTRICT,
  process_id               UUID REFERENCES processes(id) ON DELETE RESTRICT,

  -- row type
  entry_type               TEXT NOT NULL
    CHECK (entry_type IN ('accrual','clawback','manual_adjustment')),
  related_commission_id    UUID REFERENCES partner_commissions(id) ON DELETE RESTRICT,

  -- immutable snapshot
  base_amount_idr          NUMERIC(16,2) NOT NULL,
  commission_type_snapshot TEXT NOT NULL
    CHECK (commission_type_snapshot IN ('percentage','flat')),
  commission_value_snapshot NUMERIC(14,4) NOT NULL,
  rule_source              TEXT NOT NULL DEFAULT 'partner_default'
    CHECK (rule_source IN ('partner_default','manual_override')),
  assigned_to_snapshot     UUID REFERENCES users(id) ON DELETE SET NULL,

  -- amounts (IDR; clawbacks store NEGATIVE)
  gross_amount_idr         NUMERIC(16,2) NOT NULL,
  withholding_category     TEXT NOT NULL DEFAULT 'tbd'
    CHECK (withholding_category IN ('pph21','pph23','exempt','tbd')),
  withholding_rate         NUMERIC(6,4) NOT NULL DEFAULT 0.0,
  withholding_amount_idr   NUMERIC(16,2) NOT NULL DEFAULT 0.0,
  net_amount_idr           NUMERIC(16,2) NOT NULL,

  -- status lifecycle
  status                   TEXT NOT NULL DEFAULT 'accrued'
    CHECK (status IN (
      'accrued','approved','paid',
      'clawback_pending','offset_applied',
      'waived','repaid'
    )),
  accrued_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  eligible_for_approval_at TIMESTAMPTZ NOT NULL,
  approved_at              TIMESTAMPTZ,
  approved_by              UUID REFERENCES users(id) ON DELETE SET NULL,
  paid_at                  TIMESTAMPTZ,
  paid_by                  UUID REFERENCES users(id) ON DELETE SET NULL,
  paid_via                 TEXT,
  payment_reference        TEXT,
  payment_proof_url        TEXT,
  receipt_type             TEXT
    CHECK (receipt_type IS NULL OR receipt_type IN ('kwitansi','invoice','none')),
  receipt_file_url         TEXT,

  -- finance / clawback audit
  manual_override_reason   TEXT,
  clawback_reason          TEXT,
  waiver_reason            TEXT,
  idempotency_key          TEXT UNIQUE,
  commission_email_sent_at TIMESTAMPTZ,

  created_at               TIMESTAMPTZ NOT NULL DEFAULT now()

codex
I’ve started with the brief as requested. I’m also running the repo-mandated machine and git-sync check while I continue through the rest of the context, because the review needs accurate branch state.
exec
/bin/zsh -lc "wc -l /tmp/partners-review/brief.md && sed -n '261,560p' /tmp/partners-review/brief.md" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
    3606 /tmp/partners-review/brief.md
);

CREATE INDEX idx_partner_commissions_partner_id ON partner_commissions (partner_id);
CREATE INDEX idx_partner_commissions_process_id ON partner_commissions (process_id);
CREATE INDEX idx_partner_commissions_status ON partner_commissions (status);
CREATE INDEX idx_partner_commissions_eligible_at
  ON partner_commissions (eligible_for_approval_at)
  WHERE status = 'accrued';
CREATE INDEX idx_partner_commissions_assigned_to_snapshot
  ON partner_commissions (assigned_to_snapshot)
  WHERE assigned_to_snapshot IS NOT NULL;
```

### 3.4 `partner_audit_log`

```sql
CREATE TABLE partner_audit_log (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  partner_id   UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
  actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  action       TEXT NOT NULL,
    -- 'created' | 'updated' | 'activated' | 'deactivated'
    -- 'assigned' | 'orphaned' | 'reassigned'
    -- 'commission_approved' | 'commission_paid' | 'commission_clawback'
    -- 'commission_waived' | 'commission_repaid'
  before_json  JSONB,
  after_json   JSONB,
  reason       TEXT,
  at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_partner_audit_log_partner_id ON partner_audit_log (partner_id);
CREATE INDEX idx_partner_audit_log_at ON partner_audit_log (at DESC);
```

### 3.5 `system_settings` additions

```sql
INSERT INTO system_settings (key, value, description) VALUES
  ('partner_clawback_auto_writeoff_idr', '0',
   'If > 0, clawback rows below this IDR amount auto-waive on creation. Default 0 = disabled.'),
  ('partner_accrual_cooling_off_days', '30',
   'Days between accrual and eligibility for approval. Default 30.')
ON CONFLICT (key) DO NOTHING;
```

### 3.6 Rollback

Drop in FK-safe order: `partner_audit_log`, `partner_commissions`,
`partner_referrals`, `partners`. `DELETE FROM system_settings WHERE key IN (...)`.

## 4. Backend — services and API

### 4.1 Package layout

```
apps/backend-rag/backend/services/crm/partners/
├── __init__.py
├── repository.py         # asyncpg queries, append-only enforcement
├── service.py            # business logic, RBAC hooks, audit writes
├── commission_engine.py  # accrual calculation, cooling-off, clawback logic
├── events.py             # EventBus subscriber + publisher
├── emails.py             # Brevo template rendering
└── templates/
    ├── welcome.md        # jinja2 source
    └── commission.md     # jinja2 source

apps/backend-rag/backend/app/routers/
└── partners.py           # FastAPI router
```

Register router in `backend/app/setup/router_manifest.py` with
`process_groups=['_BOTH']`.

### 4.2 Endpoints

All mutations follow SCAR 2026-03-26: `except HTTPException: raise`
before generic except.

Base: `/api/partners`.

| Method | Path                                       | Scope                               | Purpose                                                  |
| ------ | ------------------------------------------ | ----------------------------------- | -------------------------------------------------------- |
| POST   | `/api/partners`                            | team, admin                         | Create partner (triggers welcome email after activation) |
| GET    | `/api/partners`                            | team (own), admin (all)             | List with filters                                        |
| GET    | `/api/partners/{id}`                       | team (owner), partner (self), admin | Detail                                                   |
| PATCH  | `/api/partners/{id}`                       | team (owner), admin                 | Update anagrafica/fiscal/payment                         |
| POST   | `/api/partners/{id}/activate`              | admin                               | `pending_approval → active`                              |
| POST   | `/api/partners/{id}/deactivate`            | admin                               | Soft delete                                              |
| POST   | `/api/partners/{id}/reassign`              | admin                               | Change `assigned_to` (reason required)                   |
| POST   | `/api/partners/bulk-reassign`              | admin                               | Bulk reassign orphaned partners                          |
| GET    | `/api/partners/{id}/referrals`             | team (owner), partner (self), admin | List referrals + process status                          |
| POST   | `/api/partners/{id}/referrals`             | team (owner), admin                 | Attach partner to a process                              |
| PATCH  | `/api/partners/referrals/{referral_id}`    | admin                               | Swap referrer                                            |
| DELETE | `/api/partners/referrals/{referral_id}`    | admin                               | Remove referral (before approval)                        |
| GET    | `/api/partners/{id}/commissions`           | team (owner), partner (self), admin | Commission ledger                                        |
| POST   | `/api/partners/commissions/{id}/approve`   | admin + finance perm                | `accrued → approved`                                     |
| POST   | `/api/partners/commissions/{id}/mark-paid` | admin + finance perm                | `approved → paid` + trigger email                        |
| POST   | `/api/partners/commissions/{id}/clawback`  | admin + finance perm                | Insert negative adjustment                               |
| POST   | `/api/partners/commissions/{id}/waive`     | admin + finance perm                | `clawback_pending → waived`                              |
| GET    | `/api/partners/me`                         | partner                             | Own profile + summary                                    |
| GET    | `/api/partners/me/referrals`               | partner                             | Own referrals (client data sterilized, §7)               |
| GET    | `/api/partners/me/commissions`             | partner                             | Own ledger                                               |
| GET    | `/api/partners/finance/export?from=&to=`   | admin + finance perm                | Monthly finance CSV                                      |

### 4.3 RBAC (extending `verify_client_access`)

Two new permission bits on `users`:

- `finance.approve_commission`
- `finance.mark_paid`

Seeded for Zero, Antonello, Asya. Check current user model before
including in migration 119 vs. a dedicated smaller migration.

Helper: `verify_partner_access(user, partner_id) -> Partner`:

- admin → allowed
- team → `partner.assigned_to == user.id`
- partner → `partner.id == user.partner_id`
- else → `HTTPException(403)`

### 4.4 Commission engine

`CommissionEngine.accrue_from_process(process_id, idempotency_key)`:

1. Read process. If not `completed AND paid`, no-op.
2. Read `partner_referrals` where `process_id = X`. If none, no-op.
3. For each referral (v1: at most 1):
   - `base_amount_idr` = process total invoiced.
   - Snapshot partner's `default_commission_type` +
     `default_commission_value`.
   - Calculate gross: percentage → `base * value / 100`, flat → `value`.
   - Withholding: from partner's `tax_withholding_category`.
     - `pph21` → `withholding_rate = 2.5`% (Asya to confirm actual rate).
     - `pph23` → `2`% (Asya to confirm).
     - `exempt` → 0.
     - `tbd` → 0 but row is blocked from approval until recategorized.
   - `net = gross - withholding`.
   - Insert row with `entry_type='accrual'`, `status='accrued'`,
     `eligible_for_approval_at = now() + cooling_off_days`,
     `idempotency_key`.
4. Fire `partner_commission_changed` notification.

`CommissionEngine.approve(commission_id, actor)`:

- Requires `status='accrued'` AND `eligible_for_approval_at <= now()` AND
  `withholding_category != 'tbd'`.
- Update + audit log + fire notification.

`CommissionEngine.mark_paid(commission_id, actor, paid_via, payment_reference, receipt_type?, receipt_file_url?)`:

- Requires `status='approved'`.
- Asya's accountant gate (first 3 real payouts) is a UI-side soft check:
  warning banner + second-click confirm. Not enforced in DB.
- Update + audit log + fire notification.
- Triggers commission-earned email (§6.2) if `commission_email_sent_at IS NULL`.

`CommissionEngine.clawback(original_commission_id, actor, reason, amount_idr=None)`:

- Original must be `status IN ('approved','paid')`.
- Default amount = `-1 * original.net_amount_idr`.
- Insert row with `entry_type='clawback'`, `related_commission_id`,
  `status='clawback_pending'`, negative amounts.
- Auto-waive if `abs(amount_idr) < system_setting(auto_writeoff_idr)`.
- Offset: on next `approve()` for same partner, pair with oldest
  `clawback_pending` and transition both (`clawback_pending →
offset_applied`, approval net reduced by clawback amount).

### 4.5 EventBus integration

Subscribe to existing channel:

- `practice_changed` (m075): when `status='completed' AND payment_status='paid'`
  (engine checks both).
- Idempotency key: `f"accrual:{process_id}:{completed_at.isoformat()}"`.
  UNIQUE constraint on `partner_commissions.idempotency_key` blocks
  duplicate accruals.

New channel: `partner_commission_changed`. Payload:

```json
{
  "partner_id": "...",
  "commission_id": "...",
  "type": "accrued|approved|paid|clawback"
}
```

Subscribers (v1): email sender on `type='paid'`.
10s dedup window per existing pattern.

## 5. Integration with existing process UI

In `apps/mouth/app/portal/(authenticated)/process/*`:

- Add optional "Referrer" dropdown. Data source:
  - team: `GET /api/partners?assigned_to=self&onboarding_status=active`
  - admin: `GET /api/partners?onboarding_status=active`
- On save with referrer selected: `POST /api/partners/{partner_id}/referrals`
  with `{process_id, notes?}`.
- If existing referral: show with admin-only edit
  (`PATCH /api/partners/referrals/{id}`) or delete
  (`DELETE /api/partners/referrals/{id}`).

## 6. Email templates — Brevo via `zantara@balizero.com`

All sends via `POST /api/notifications/send-email` +
`X-API-Key: REDACTED-ROTATED-KEY`.
Sender: `zantara@balizero.com` (name `Zantara`), non-negotiable.

### 6.1 Welcome email (on `/activate`)

Trigger: admin calls `/api/partners/{id}/activate`.
Idempotent: skip if `partner.welcome_email_sent_at IS NOT NULL`.

Content (actual copy in `templates/welcome.md`):

- Greeting in `partner.preferred_language`.
- Bali Zero services + prices (loaded from `PricingTool` at render time;
  Golden Rule #12 — never hardcode prices).
- Commission structure: default rate, cooling-off period, payment flow.
- T&C: commission paid only when process `completed + paid`, 30-day
  cooling-off, clawback policy, PDP disclosure (provisional text), opt-out.
- Partner portal link (admin provisions partner login separately in v1).

### 6.2 Commission-earned email (on mark-paid)

Trigger: `CommissionEngine.mark_paid()` completion.
Idempotent via `partner_commissions.commission_email_sent_at`.

To: `partner.email`. CC: `partner.assigned_to_snapshot.email`.
Subject: language-switched, format
"Commissione maturata — {client_initial}".

Content:

- Partner name + referral process descriptor (first name + last initial
  only, per UU PDP data-minimization principle).
- Gross / withholding / net breakdown.
- Paid via / payment reference / paid_at.
- Receipt file link (if uploaded).
- T&C reminder about clawback on refund.

## 7. Frontend

### 7.1 Team portal (role `team` / `admin`)

Route: `apps/mouth/app/portal/(authenticated)/partners/` (plural).
Sidebar order: **after `process`, before `hr`**.

Pages:

- `/portal/partners` — list view with filters
  (status, assigned_to, orphaned, search).
- `/portal/partners/new` — create form (team + admin; team auto-sets
  `assigned_to = self`, admin can pick).
- `/portal/partners/{id}` — detail tabs: Profile / Fiscal / Payment /
  Referrals / Commissions / Audit.
- `/portal/partners/{id}/edit` — edit form.
- `/portal/partners/orphaned` — admin-only bulk-reassign flow.
- `/portal/partners/finance` — admin-only approve / mark-paid queue +
  CSV export.

Styling: `bz-tokens.css` (warm-depth). Component reuse from
`/portal/clients/*` and `/portal/process/*`. Icons: lucide-react.

### 7.2 Partner portal (role `partner`)

Route: `apps/mouth/app/portal/(authenticated)/partner/` (singular).
Middleware (`apps/mouth/middleware.ts`) routes `role=partner` to
`/portal/partner/dashboard` and blocks all other `/portal/*` (302 or 403).

Pages:

- `/portal/partner/dashboard` — summary (earned, pending, paid; recent
  referrals + commissions).
- `/portal/partner/referrals` — own referrals. Client data sterilized:
  first name + last initial, service_type, process.status. No documents,
  no contact details.
- `/portal/partner/commissions` — own ledger, filterable by status.
- `/portal/partner/profile` — read-only own record. Edits via email to
  Bali Zero (self-serve deferred to v2).

### 7.3 Referrer dropdown on process pages

See §5.

### 7.4 NB-2 guardrail

In partner create form: if `work_role` matches
`/sponsor|garante|penjamin/i`, show soft warning banner:

> Reminder: only PT PMA Bali Zero can be the formal sponsor/garante on a
> visa. Third parties may only refer clients.

Informational, does not block save. Hard enforcement comes from Q4 fiscal
gate (`tax_withholding_category='tbd'` blocks approve).

## 8. Testing strategy (TDD)

exec
/bin/zsh -lc 'echo "Machine: $(whoami)@$(hostname)" && OTHER=$(if [ "$(whoami)" = "nuzantara" ]; then echo "air"; else echo "pro"; fi) && ssh -o ConnectTimeout=3 $OTHER '"'echo \"Peer: "'$(whoami)@$(hostname)"'"' 2>/dev/null || echo \"Peer: UNREACHABLE\" && LOCAL_HEAD="'$(git log --oneline -1 2>/dev/null) && REMOTE_HEAD=$(ssh -o ConnectTimeout=3 $OTHER '"'cd ~/Desktop/projects/nuzantara 2>/dev/null || cd ~/Desktop/nuzantara 2>/dev/null; git log --oneline -1' 2>/dev/null) && if [ \""'$LOCAL_HEAD" = "$REMOTE_HEAD" ]; then echo "Git sync: OK ($LOCAL_HEAD)"; else echo "Git sync: OUT OF SYNC! Local=$LOCAL_HEAD Remote=$REMOTE_HEAD"; fi' in /Users/nuzantara/Desktop/partners-spec-wt
 exited 255 in 2322ms:
codex
The machine check identifies this session as `nuzantara@Nuzantara` on Pro. The peer SSH check returned `UNREACHABLE`, so I’m treating the local PR worktree as the review source and will avoid assuming cross-machine sync.
exec
/bin/zsh -lc "sed -n '921,1280p' /tmp/partners-review/brief.md" in /Users/nuzantara/Desktop/partners-spec-wt
exec
/bin/zsh -lc "sed -n '561,920p' /tmp/partners-review/brief.md" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
        " ON partner_commissions (status);"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partner_commissions_eligible_at"
        " ON partner_commissions (eligible_for_approval_at)"
        " WHERE status = 'accrued';"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partner_commissions_assigned_to_snapshot"
        " ON partner_commissions (assigned_to_snapshot)"
        " WHERE assigned_to_snapshot IS NOT NULL;"
    )

    # -------------------------------------------------------------------------
    # 5. partner_audit_log
    # -------------------------------------------------------------------------
    await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_tables
                WHERE schemaname = 'public' AND tablename = 'partner_audit_log'
            ) THEN
                CREATE TABLE partner_audit_log (
                    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    partner_id    UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
                    actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                    action        TEXT NOT NULL,
                    before_json   JSONB,
                    after_json    JSONB,
                    reason        TEXT,
                    at            TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            END IF;
        END $$;
    """)

    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partner_audit_log_partner_id"
        " ON partner_audit_log (partner_id);"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partner_audit_log_at"
        " ON partner_audit_log (at DESC);"
    )

    # -------------------------------------------------------------------------
    # 6. system_settings seed rows (spec §3.5)
    # -------------------------------------------------------------------------
    await conn.execute("""
        INSERT INTO system_settings (key, value, description) VALUES
          ('partner_clawback_auto_writeoff_idr', '0',
           'If > 0, clawback rows below this IDR amount auto-waive on creation. Default 0 = disabled.'),
          ('partner_accrual_cooling_off_days', '30',
           'Days between accrual and eligibility for approval. Default 30.')
        ON CONFLICT (key) DO NOTHING;
    """)

    logger.info(
        "✅ Migration 119: partners + partner_referrals + partner_commissions"
        " + partner_audit_log + users.partner_id + 2 system_settings rows"
    )


async def rollback(conn: Any) -> None:
    # Drop in FK-safe order: children first, parent last (spec §3.6)
    await conn.execute("DROP TABLE IF EXISTS partner_audit_log;")
    await conn.execute("DROP TABLE IF EXISTS partner_commissions;")
    await conn.execute("DROP TABLE IF EXISTS partner_referrals;")
    # Drop users.partner_id index + column before dropping partners (it references partners.id)
    await conn.execute("DROP INDEX IF EXISTS idx_users_partner_id;")
    await conn.execute("ALTER TABLE users DROP COLUMN IF EXISTS partner_id;")
    await conn.execute("DROP TABLE IF EXISTS partners;")
    await conn.execute(
        "DELETE FROM system_settings WHERE key IN "
        "('partner_clawback_auto_writeoff_idr','partner_accrual_cooling_off_days');"
    )
    logger.info(
        "Migration 119 rollback: 4 tables dropped, users.partner_id removed,"
        " 2 system_settings rows deleted"
    )
```

### apps/backend-rag/backend/services/crm/partners/models.py

```
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

EntityType = Literal["individual", "corporate_pt", "corporate_cv", "foreign"]
WithholdingCategory = Literal["pph21", "pph23", "exempt", "tbd"]
CommissionType = Literal["percentage", "flat"]
OnboardingStatus = Literal["pending_approval", "active", "inactive"]
CommissionStatus = Literal[
    "accrued", "approved", "paid",
    "clawback_pending", "offset_applied",
    "waived", "repaid",
]
CommissionEntryType = Literal["accrual", "clawback", "manual_adjustment"]
RuleSource = Literal["partner_default", "manual_override"]


@dataclass
class Partner:
    id: UUID
    full_name: str
    email: str
    entity_type: EntityType
    tax_withholding_category: WithholdingCategory
    default_commission_type: CommissionType
    default_commission_value: Decimal
    onboarding_status: OnboardingStatus
    payment_currency: str
    preferred_language: str
    created_at: datetime
    updated_at: datetime

    # optional fields
    work_role: str | None = None
    company_name: str | None = None
    office_address: str | None = None
    phone: str | None = None
    npwp: str | None = None
    nik: str | None = None
    fiscal_address: str | None = None
    bank_name: str | None = None
    bank_account_holder: str | None = None
    bank_account_number: str | None = None
    ewallet_type: str | None = None
    ewallet_number: str | None = None
    iban: str | None = None
    payment_notes: str | None = None
    assigned_to: UUID | None = None
    pdp_consent_at: datetime | None = None
    pdp_consent_version: str | None = None
    terms_accepted_at: datetime | None = None
    terms_version: str | None = None
    created_by: UUID | None = None
    deactivated_at: datetime | None = None
    welcome_email_sent_at: datetime | None = None


@dataclass
class PartnerReferral:
    id: UUID
    partner_id: UUID
    process_id: UUID
    share_percent: Decimal
    referred_at: datetime
    referred_by_user_id: UUID | None = None
    notes: str | None = None


@dataclass
class PartnerCommission:
    id: UUID
    partner_id: UUID
    entry_type: CommissionEntryType
    base_amount_idr: Decimal
    commission_type_snapshot: CommissionType
    commission_value_snapshot: Decimal
    rule_source: RuleSource
    gross_amount_idr: Decimal
    withholding_category: WithholdingCategory
    withholding_rate: Decimal
    withholding_amount_idr: Decimal
    net_amount_idr: Decimal
    status: CommissionStatus
    accrued_at: datetime
    eligible_for_approval_at: datetime
    created_at: datetime

    referral_id: UUID | None = None
    process_id: UUID | None = None
    related_commission_id: UUID | None = None
    assigned_to_snapshot: UUID | None = None
    approved_at: datetime | None = None
    approved_by: UUID | None = None
    paid_at: datetime | None = None
    paid_by: UUID | None = None
    paid_via: str | None = None
    payment_reference: str | None = None
    payment_proof_url: str | None = None
    receipt_type: Literal["kwitansi", "invoice", "none"] | None = None
    receipt_file_url: str | None = None
    manual_override_reason: str | None = None
    clawback_reason: str | None = None
    waiver_reason: str | None = None
    idempotency_key: str | None = None
    commission_email_sent_at: datetime | None = None


@dataclass
class PartnerAuditLogEntry:
    id: UUID
    partner_id: UUID
    action: str
    at: datetime
    actor_user_id: UUID | None = None
    before_json: dict | None = None
    after_json: dict | None = None
    reason: str | None = None
```

### apps/backend-rag/backend/services/crm/partners/repository.py

```
# backend/services/crm/partners/repository.py
from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg

from backend.services.crm.partners.models import (
    Partner, PartnerReferral, PartnerCommission, PartnerAuditLogEntry,
    EntityType, CommissionType, CommissionStatus, CommissionEntryType,
    WithholdingCategory, RuleSource,
)

logger = logging.getLogger(__name__)

# Commission state machine.
# Source of truth: docs/superpowers/specs/2026-04-20-crm-partners-module.md §3.3 + §4.4.
# v1 terminal states: paid, offset_applied, waived, repaid.
_ALLOWED_TRANSITIONS: dict[CommissionStatus, set[CommissionStatus]] = {
    "accrued": {"approved"},
    "approved": {"paid"},
    "paid": set(),
    "clawback_pending": {"offset_applied", "waived", "repaid"},
    "offset_applied": set(),
    "waived": set(),
    "repaid": set(),
}

_PARTNER_UPDATABLE_COLS = {
    "full_name", "work_role", "company_name", "office_address",
    "email", "phone", "preferred_language",
    "entity_type", "npwp", "nik", "tax_withholding_category", "fiscal_address",
    "bank_name", "bank_account_holder", "bank_account_number",
    "ewallet_type", "ewallet_number", "payment_currency", "iban", "payment_notes",
    "default_commission_type", "default_commission_value",
    "pdp_consent_at", "pdp_consent_version", "terms_accepted_at", "terms_version",
}
# NB: onboarding_status, assigned_to, welcome_email_sent_at are ONLY settable
# via their dedicated methods (activate_partner, reassign_partner, mark_welcome_sent).


class PartnersRepository:
    """SQL layer. No business logic, no audit writes, no event emission."""

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    # ── Partner CRUD ────────────────────────────────────────────────────

    async def insert_partner(
        self,
        *,
        full_name: str,
        email: str,
        entity_type: EntityType,
        assigned_to: UUID | None = None,
        created_by: UUID | None = None,
        **optional: Any,
    ) -> UUID:
        await self._assert_email_is_not_internal(email)
        cols = ["full_name", "email", "entity_type", "assigned_to", "created_by"]
        vals: list[Any] = [full_name, email, entity_type, assigned_to, created_by]
        for k, v in optional.items():
            if k not in _PARTNER_UPDATABLE_COLS:
                raise ValueError(f"Field {k!r} is not insertable via insert_partner")
            cols.append(k); vals.append(v)
        placeholders = ", ".join(f"${i+1}" for i in range(len(vals)))
        sql = f"INSERT INTO partners ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id"
        row = await self.conn.fetchrow(sql, *vals)
        logger.debug("insert_partner id=%s email=%s", row["id"], email)
        return row["id"]

    async def _assert_email_is_not_internal(self, email: str) -> None:
        """Reject partner emails that match an internal team/admin user.

        KNOWN RACE: This is a SELECT-then-INSERT pattern without a cross-table
        DB constraint. A concurrent INSERT into users with role in (team,admin)
        between this check and the partners INSERT would slip through. v2
        should add a SERIALIZABLE transaction wrapper or a cross-table unique
        trigger. For v1 the race window is narrow and acceptable (rare admin
        operation concurrent with partner onboarding).
        """
        row = await self.conn.fetchrow(
            "SELECT 1 FROM users WHERE email = $1 AND role IN ('team','admin')",
            email,
        )
        if row is not None:
            raise ValueError(f"email is already a team/admin user: {email!r}")

    async def get_partner(self, partner_id: UUID) -> Partner | None:
        row = await self.conn.fetchrow("SELECT * FROM partners WHERE id = $1", partner_id)
        return self._row_to_partner(row) if row else None

    async def list_partners(
        self,
        *,
        assigned_to: UUID | None = None,
        onboarding_status: str | None = None,
        orphaned: bool = False,
        search: str | None = None,
        limit: int = 200,
    ) -> list[Partner]:
        where, args = ["TRUE"], []
        if assigned_to is not None:
            args.append(assigned_to); where.append(f"assigned_to = ${len(args)}")
        if onboarding_status is not None:
            args.append(onboarding_status); where.append(f"onboarding_status = ${len(args)}")
        if orphaned:
            where.append("assigned_to IS NULL")
        if search:
            args.append(f"%{search}%")
            where.append(f"(full_name ILIKE ${len(args)} OR email ILIKE ${len(args)} OR company_name ILIKE ${len(args)})")
        args.append(limit)
        sql = f"SELECT * FROM partners WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT ${len(args)}"
        rows = await self.conn.fetch(sql, *args)
        return [self._row_to_partner(r) for r in rows]

    async def update_partner(self, partner_id: UUID, **fields: Any) -> None:
        if not fields:
            raise ValueError("update_partner requires at least one field")
        bad = set(fields) - _PARTNER_UPDATABLE_COLS
        if bad:
            raise ValueError(f"Non-updatable fields: {bad}")
        if "email" in fields:
            await self._assert_email_is_not_internal(fields["email"])
        sets = [f"{k} = ${i+2}" for i, k in enumerate(fields)]
        sets.append(f"updated_at = now()")
        sql = f"UPDATE partners SET {', '.join(sets)} WHERE id = $1"
        await self.conn.execute(sql, partner_id, *fields.values())

    async def activate_partner(self, partner_id: UUID) -> None:
        await self.conn.execute(
            "UPDATE partners SET onboarding_status = 'active', updated_at = now() "
            "WHERE id = $1 AND onboarding_status = 'pending_approval'",
            partner_id,
        )

    async def deactivate_partner(self, partner_id: UUID) -> None:
        await self.conn.execute(
            "UPDATE partners SET onboarding_status = 'inactive', deactivated_at = now(), "
            "updated_at = now() WHERE id = $1",
            partner_id,
        )


 succeeded in 0ms:

All with real Postgres — no DB mocks per project rule.

```
apps/backend-rag/backend/tests/services/crm/partners/
├── test_repository.py         # append-only, UNIQUE violations
├── test_service.py            # CRUD + RBAC + audit log writes
├── test_commission_engine.py  # accrual, cooling-off, clawback, offset
├── test_events.py             # EventBus subscriber idempotency
└── test_emails.py             # Brevo payload (mock HTTP send only)

apps/backend-rag/backend/tests/routers/
└── test_partners.py           # 16-endpoint contract, 403/404/409 paths

apps/backend-rag/backend/tests/integration/
└── test_partners_e2e.py       # full flow: process.completed+paid → accrual → approve → pay → email
```

Fixtures reused from `conftest.py` (`db`, `user`, `admin`, `team_user`,
`partner_user`). New `partner_factory` fixture.

## 9. Sprint plan

Total: **~26h** across 8 sprints. One commit per sprint,
Co-Authored-By Claude Opus 4.7. Full test suite green before each commit.
No force push. No `--no-verify`.

| Sprint | Focus                                                                         | Est |
| ------ | ----------------------------------------------------------------------------- | --- |
| S1     | Migration 119 + rollback + migration tests                                    | 3h  |
| S2     | `partners` repository + service + RBAC helper + audit log + 40+ unit tests    | 3h  |
| S3     | API endpoints (16 routes) + router manifest + 25+ router tests                | 4h  |
| S4     | CommissionEngine (accrual + cooling-off + clawback + offset) + 30+ unit tests | 4h  |
| S5     | EventBus subscriber on `practice_changed` + idempotency + integration test    | 2h  |
| S6     | Email templates (welcome + commission) + Brevo payload + idempotency          | 2h  |
| S7     | Team portal `/portal/partners/*` (list + new + detail + edit + finance queue) | 5h  |
| S8     | Partner portal `/portal/partner/*` + middleware + NB-2 guardrails + e2e tests | 3h  |

## 10. Vincoli operativi

- OAuth-only Claude (no `ANTHROPIC_API_KEY`). N/A to this code (no Claude
  calls), but applicable to future partners-related agents.
- Email: `zantara@balizero.com` via Brevo. Single source, no other senders.
- NO auto-assignment. Orphan → manual reassign only.
- Bali Zero methodology: prices ONLY from `PricingTool` (Golden Rule #12).
- Migration 119 lives in `backend/migrations/` (async Python, working
  pattern 108-118). Not in `db/migrations_v2/` which has the historical
  ROLLBACK-marker SCAR (migration 114 incident, 2026-04-19).
- Deploy: backend from `apps/backend-rag/`, frontend from monorepo root
  via `git push` (for `NEXT_PUBLIC_*` env bake).

## 11. Post-implementation verification

```bash
# 1. Migration applied
fly ssh console -a nuzantara-postgres -C "psql -c '\d partners'"

# 2. Endpoint live
curl -s https://nuzantara-rag.fly.dev/api/partners \
  -H "Cookie: nz_access_token=..."

# 3. EventBus subscriber active
fly logs -a nuzantara-rag | grep partner_commission_changed

# 4. Team portal reachable
open https://kita.balizero.com/portal/partners

# 5. Partner portal reachable (with partner user)
open https://kita.balizero.com/portal/partner/dashboard
```

Telegram notification to `1125336968` on first real partner creation
(optional, nice-to-have).

## 12. Future work (v2+)

- `partner_commission_rules` table (per-service rates, tiers, effective dates).
- Xendit / BCA / OVO payout automation.
- PDF bukti potong generator + e-Bupot Unifikasi submission.
- Split commissions (drop UNIQUE on `partner_referrals.process_id`).
- Partner-to-partner referral chains with chain commission rules.
- In-portal messaging team ↔ partner.
- Partner self-service profile edit.
- Separate subdomain `partners.balizero.com` (if branding requires).
- Team performance dashboard (referrals brought, conversion rate).

---

**Council synthesis artifact:**
`docs/superpowers/specs/2026-04-20-partners-brainstorm/99-synthesis.md`
(Gemini / Codex / DeepSeek / NB-2 raw outputs: `01-*.md` .. `04-nb2.md`).

---

## Key Backend Files


### apps/backend-rag/backend/migrations/migration_119_partners.py

```
"""Migration 119: Partners module — 4 tables + 2 system settings.

Why
---
Formalizes Bali Zero's informal third-party referral network (hotels, property
managers, consultants, agents) into a first-class CRM module with full
Indonesian fiscal profile, an append-only commission ledger, and GDPR/UU PDP
consent tracking.

Schema
------
- partners: anagrafica + fiscal profile + payment rail + commission defaults
- partner_referrals: links partners to existing processes (v1: 1-to-1)
- partner_commissions: append-only ledger (accrued → approved → paid, with clawback)
- partner_audit_log: immutable event trail for every partner/commission state change
- users.partner_id: reverse FK so partner-role users can resolve their own record

System settings
---------------
- partner_clawback_auto_writeoff_idr: auto-waive threshold (default 0 = disabled)
- partner_accrual_cooling_off_days: days before accrual becomes eligible (default 30)

Idempotent: safe to re-run.

Spec: docs/superpowers/specs/2026-04-20-crm-partners-module.md §3
Plan: docs/superpowers/plans/2026-04-20-crm-partners-module.md Task 1
Author: Claude Opus 4.7
Date: 2026-04-20
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    # -------------------------------------------------------------------------
    # 1. partners
    # -------------------------------------------------------------------------
    await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_tables
                WHERE schemaname = 'public' AND tablename = 'partners'
            ) THEN
                CREATE TABLE partners (
                    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),

                    -- anagrafica
                    full_name                 TEXT NOT NULL,
                    work_role                 TEXT,
                    company_name              TEXT,
                    office_address            TEXT,
                    email                     TEXT NOT NULL UNIQUE,
                    phone                     TEXT,
                    preferred_language        TEXT DEFAULT 'id',

                    -- fiscal (Indonesia)
                    entity_type               TEXT NOT NULL
                        CHECK (entity_type IN ('individual','corporate_pt','corporate_cv','foreign')),
                    npwp                      TEXT,
                    nik                       TEXT,
                    tax_withholding_category  TEXT NOT NULL DEFAULT 'tbd'
                        CHECK (tax_withholding_category IN ('pph21','pph23','exempt','tbd')),
                    fiscal_address            TEXT,

                    -- payment rail
                    bank_name                 TEXT,
                    bank_account_holder       TEXT,
                    bank_account_number       TEXT,
                    ewallet_type              TEXT,
                    ewallet_number            TEXT,
                    payment_currency          TEXT NOT NULL DEFAULT 'IDR',
                    iban                      TEXT,
                    payment_notes             TEXT,

                    -- commission policy (v1 uses partner-level defaults)
                    default_commission_type   TEXT NOT NULL DEFAULT 'percentage'
                        CHECK (default_commission_type IN ('percentage','flat')),
                    default_commission_value  NUMERIC(14,4) NOT NULL DEFAULT 10.0,

                    -- lifecycle
                    onboarding_status         TEXT NOT NULL DEFAULT 'pending_approval'
                        CHECK (onboarding_status IN ('pending_approval','active','inactive')),
                    assigned_to               UUID REFERENCES users(id) ON DELETE SET NULL,

                    -- UU PDP + T&C
                    pdp_consent_at            TIMESTAMPTZ,
                    pdp_consent_version       TEXT,
                    terms_accepted_at         TIMESTAMPTZ,
                    terms_version             TEXT,

                    -- audit + idempotency
                    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
                    created_by                UUID REFERENCES users(id) ON DELETE SET NULL,
                    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
                    deactivated_at            TIMESTAMPTZ,
                    welcome_email_sent_at     TIMESTAMPTZ
                );
            END IF;
        END $$;
    """)

    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_partners_email"
        " ON partners (email);"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partners_assigned_to"
        " ON partners (assigned_to)"
        " WHERE assigned_to IS NOT NULL;"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partners_onboarding_status"
        " ON partners (onboarding_status);"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partners_entity_type"
        " ON partners (entity_type);"
    )

    # -------------------------------------------------------------------------
    # 2. users.partner_id — reverse FK so partner-role users resolve their record
    # -------------------------------------------------------------------------
    await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'partner_id'
            ) THEN
                ALTER TABLE users ADD COLUMN partner_id UUID REFERENCES partners(id) ON DELETE SET NULL;
            END IF;
        END $$;
    """)
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_partner_id"
        " ON users (partner_id) WHERE partner_id IS NOT NULL;"
    )

    # -------------------------------------------------------------------------
    # 3. partner_referrals
    # -------------------------------------------------------------------------
    await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_tables
                WHERE schemaname = 'public' AND tablename = 'partner_referrals'
            ) THEN
                CREATE TABLE partner_referrals (
                    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    partner_id           UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
                    process_id           UUID NOT NULL REFERENCES processes(id) ON DELETE RESTRICT,
                    share_percent        NUMERIC(5,2) NOT NULL DEFAULT 100.00
                        CHECK (share_percent > 0 AND share_percent <= 100),
                    referred_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
                    referred_by_user_id  UUID REFERENCES users(id) ON DELETE SET NULL,
                    notes                TEXT,

                    CONSTRAINT partner_referrals_process_unique_v1 UNIQUE (process_id)
                    -- v2: drop this constraint when enabling split commissions
                );
            END IF;
        END $$;
    """)

    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partner_referrals_partner_id"
        " ON partner_referrals (partner_id);"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partner_referrals_process_id"
        " ON partner_referrals (process_id);"
    )

    # -------------------------------------------------------------------------
    # 4. partner_commissions (append-only ledger)
    # -------------------------------------------------------------------------
    await conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_tables
                WHERE schemaname = 'public' AND tablename = 'partner_commissions'
            ) THEN
                CREATE TABLE partner_commissions (
                    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    partner_id               UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
                    referral_id              UUID REFERENCES partner_referrals(id) ON DELETE RESTRICT,
                    process_id               UUID REFERENCES processes(id) ON DELETE RESTRICT,

                    -- row type
                    entry_type               TEXT NOT NULL
                        CHECK (entry_type IN ('accrual','clawback','manual_adjustment')),
                    related_commission_id    UUID REFERENCES partner_commissions(id) ON DELETE RESTRICT,

                    -- immutable snapshot
                    base_amount_idr          NUMERIC(16,2) NOT NULL,
                    commission_type_snapshot TEXT NOT NULL
                        CHECK (commission_type_snapshot IN ('percentage','flat')),
                    commission_value_snapshot NUMERIC(14,4) NOT NULL,
                    rule_source              TEXT NOT NULL DEFAULT 'partner_default'
                        CHECK (rule_source IN ('partner_default','manual_override')),
                    assigned_to_snapshot     UUID REFERENCES users(id) ON DELETE SET NULL,

                    -- amounts (IDR; clawbacks store NEGATIVE)
                    gross_amount_idr         NUMERIC(16,2) NOT NULL,
                    withholding_category     TEXT NOT NULL DEFAULT 'tbd'
                        CHECK (withholding_category IN ('pph21','pph23','exempt','tbd')),
                    withholding_rate         NUMERIC(6,4) NOT NULL DEFAULT 0.0,
                    withholding_amount_idr   NUMERIC(16,2) NOT NULL DEFAULT 0.0,
                    net_amount_idr           NUMERIC(16,2) NOT NULL,

                    -- status lifecycle
                    status                   TEXT NOT NULL DEFAULT 'accrued'
                        CHECK (status IN (
                            'accrued','approved','paid',
                            'clawback_pending','offset_applied',
                            'waived','repaid'
                        )),
                    accrued_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
                    eligible_for_approval_at TIMESTAMPTZ NOT NULL,
                    approved_at              TIMESTAMPTZ,
                    approved_by              UUID REFERENCES users(id) ON DELETE SET NULL,
                    paid_at                  TIMESTAMPTZ,
                    paid_by                  UUID REFERENCES users(id) ON DELETE SET NULL,
                    paid_via                 TEXT,
                    payment_reference        TEXT,
                    payment_proof_url        TEXT,
                    receipt_type             TEXT
                        CHECK (receipt_type IS NULL OR receipt_type IN ('kwitansi','invoice','none')),
                    receipt_file_url         TEXT,

                    -- finance / clawback audit
                    manual_override_reason   TEXT,
                    clawback_reason          TEXT,
                    waiver_reason            TEXT,
                    idempotency_key          TEXT UNIQUE,
                    commission_email_sent_at TIMESTAMPTZ,

                    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            END IF;
        END $$;
    """)

    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partner_commissions_partner_id"
        " ON partner_commissions (partner_id);"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partner_commissions_process_id"
        " ON partner_commissions (process_id);"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_partner_commissions_status"

codex
The brief is large but structured: spec first, then exact backend file snapshots. I’m reading it in chunks and will use the local files afterward for reliable line references, because the pasted excerpts do not preserve original file line numbers.
exec
/bin/zsh -lc "sed -n '1281,1640p' /tmp/partners-review/brief.md" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
    async def reassign_partner(self, partner_id: UUID, new_user_id: UUID | None) -> None:
        await self.conn.execute(
            "UPDATE partners SET assigned_to = $2, updated_at = now() WHERE id = $1",
            partner_id, new_user_id,
        )

    async def orphan_partners_of_user(self, user_id: UUID) -> int:
        result = await self.conn.execute(
            "UPDATE partners SET assigned_to = NULL, updated_at = now() WHERE assigned_to = $1",
            user_id,
        )
        # asyncpg returns "UPDATE <n>"
        return int(result.split()[-1])

    async def mark_welcome_sent(self, partner_id: UUID) -> None:
        await self.conn.execute(
            "UPDATE partners SET welcome_email_sent_at = now() "
            "WHERE id = $1 AND welcome_email_sent_at IS NULL",
            partner_id,
        )

    # ── Referrals ───────────────────────────────────────────────────────

    async def insert_referral(
        self, *, partner_id: UUID, process_id: UUID,
        referred_by_user_id: UUID | None = None,
        share_percent: Decimal = Decimal("100.00"),
        notes: str | None = None,
    ) -> UUID:
        row = await self.conn.fetchrow(
            """
            INSERT INTO partner_referrals
                (partner_id, process_id, share_percent, referred_by_user_id, notes)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            partner_id, process_id, share_percent, referred_by_user_id, notes,
        )
        return row["id"]

    async def get_referral_by_process(self, process_id: UUID) -> PartnerReferral | None:
        row = await self.conn.fetchrow(
            "SELECT * FROM partner_referrals WHERE process_id = $1", process_id
        )
        return self._row_to_referral(row) if row else None

    async def list_referrals_for_partner(self, partner_id: UUID) -> list[PartnerReferral]:
        rows = await self.conn.fetch(
            "SELECT * FROM partner_referrals WHERE partner_id = $1 ORDER BY referred_at DESC",
            partner_id,
        )
        return [self._row_to_referral(r) for r in rows]

    async def update_referral_partner(self, referral_id: UUID, new_partner_id: UUID) -> None:
        await self.conn.execute(
            "UPDATE partner_referrals SET partner_id = $2 WHERE id = $1",
            referral_id, new_partner_id,
        )

    async def delete_referral(self, referral_id: UUID) -> None:
        # Referrals are deletable ONLY before any commission is accrued against them.
        row = await self.conn.fetchrow(
            "SELECT 1 FROM partner_commissions WHERE referral_id = $1 LIMIT 1",
            referral_id,
        )
        if row is not None:
            raise RuntimeError("Cannot delete referral with commissions recorded")
        try:
            await self.conn.execute("DELETE FROM partner_referrals WHERE id = $1", referral_id)
        except asyncpg.ForeignKeyViolationError as e:
            # Race: commission inserted between our SELECT and DELETE.
            raise RuntimeError("Cannot delete referral with commissions recorded") from e

    # ── Commissions (append-only) ───────────────────────────────────────

    async def insert_commission(
        self,
        *,
        partner_id: UUID,
        entry_type: CommissionEntryType,
        base_amount_idr: Decimal,
        commission_type_snapshot: CommissionType,
        commission_value_snapshot: Decimal,
        gross_amount_idr: Decimal,
        net_amount_idr: Decimal,
        idempotency_key: str,
        referral_id: UUID | None = None,
        process_id: UUID | None = None,
        related_commission_id: UUID | None = None,
        rule_source: RuleSource = "partner_default",
        assigned_to_snapshot: UUID | None = None,
        withholding_category: WithholdingCategory = "tbd",
        withholding_rate: Decimal = Decimal("0.0"),
        withholding_amount_idr: Decimal = Decimal("0.0"),
        status: CommissionStatus = "accrued",
        eligible_for_approval_at: Any = None,
        manual_override_reason: str | None = None,
        clawback_reason: str | None = None,
    ) -> UUID:
        row = await self.conn.fetchrow(
            """
            INSERT INTO partner_commissions (
                partner_id, entry_type, referral_id, process_id, related_commission_id,
                base_amount_idr, commission_type_snapshot, commission_value_snapshot,
                rule_source, assigned_to_snapshot,
                gross_amount_idr, withholding_category, withholding_rate,
                withholding_amount_idr, net_amount_idr,
                status, eligible_for_approval_at,
                manual_override_reason, clawback_reason, idempotency_key
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,
                    COALESCE($17, now()),$18,$19,$20)
            RETURNING id
            """,
            partner_id, entry_type, referral_id, process_id, related_commission_id,
            base_amount_idr, commission_type_snapshot, commission_value_snapshot,
            rule_source, assigned_to_snapshot,
            gross_amount_idr, withholding_category, withholding_rate,
            withholding_amount_idr, net_amount_idr,
            status, eligible_for_approval_at,
            manual_override_reason, clawback_reason, idempotency_key,
        )
        logger.debug(
            "insert_commission id=%s partner=%s type=%s status=%s",
            row["id"], partner_id, entry_type, status,
        )
        return row["id"]

    async def get_commission(self, commission_id: UUID) -> PartnerCommission | None:
        row = await self.conn.fetchrow(
            "SELECT * FROM partner_commissions WHERE id = $1", commission_id
        )
        return self._row_to_commission(row) if row else None

    async def list_commissions_for_partner(
        self, partner_id: UUID, *, status: CommissionStatus | None = None,
    ) -> list[PartnerCommission]:
        args: list[Any] = [partner_id]
        where = "partner_id = $1"
        if status is not None:
            args.append(status); where += f" AND status = ${len(args)}"
        sql = f"SELECT * FROM partner_commissions WHERE {where} ORDER BY created_at DESC"
        rows = await self.conn.fetch(sql, *args)
        return [self._row_to_commission(r) for r in rows]

    async def list_pending_clawbacks(self, partner_id: UUID) -> list[PartnerCommission]:
        rows = await self.conn.fetch(
            "SELECT * FROM partner_commissions WHERE partner_id = $1 AND status = 'clawback_pending' "
            "ORDER BY accrued_at ASC",
            partner_id,
        )
        return [self._row_to_commission(r) for r in rows]

    async def update_commission_status(
        self,
        commission_id: UUID,
        new_status: CommissionStatus,
        *,
        approved_by: UUID | None = None,
        paid_by: UUID | None = None,
        paid_via: str | None = None,
        payment_reference: str | None = None,
        payment_proof_url: str | None = None,
        receipt_type: str | None = None,
        receipt_file_url: str | None = None,
        waiver_reason: str | None = None,
    ) -> None:
        current = await self.get_commission(commission_id)
        if current is None:
            raise ValueError(f"Commission {commission_id} not found")
        if new_status not in _ALLOWED_TRANSITIONS.get(current.status, set()):
            raise ValueError(
                f"Disallowed transition: {current.status!r} -> {new_status!r}"
            )
        logger.debug(
            "update_commission_status id=%s %s->%s", commission_id, current.status, new_status
        )
        fragments, args = ["status = $2"], [commission_id, new_status]
        if new_status == "approved":
            fragments += ["approved_at = now()", f"approved_by = ${len(args)+1}"]; args.append(approved_by)
        if new_status == "paid":
            fragments += [
                "paid_at = now()",
                f"paid_by = ${len(args)+1}", f"paid_via = ${len(args)+2}",
                f"payment_reference = ${len(args)+3}", f"payment_proof_url = ${len(args)+4}",
                f"receipt_type = ${len(args)+5}", f"receipt_file_url = ${len(args)+6}",
            ]
            args += [paid_by, paid_via, payment_reference, payment_proof_url,
                     receipt_type, receipt_file_url]
        if new_status == "waived":
            fragments += [f"waiver_reason = ${len(args)+1}"]; args.append(waiver_reason)
        sql = f"UPDATE partner_commissions SET {', '.join(fragments)} WHERE id = $1"
        await self.conn.execute(sql, *args)

    async def mark_commission_email_sent(self, commission_id: UUID) -> None:
        await self.conn.execute(
            "UPDATE partner_commissions SET commission_email_sent_at = now() "
            "WHERE id = $1 AND commission_email_sent_at IS NULL",
            commission_id,
        )

    async def delete_commission(self, commission_id: UUID) -> None:
        raise RuntimeError("partner_commissions is append-only; delete is forbidden")

    # ── Audit log ───────────────────────────────────────────────────────

    async def insert_audit(
        self,
        *,
        partner_id: UUID,
        action: str,
        actor_user_id: UUID | None = None,
        before: dict | None = None,
        after: dict | None = None,
        reason: str | None = None,
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO partner_audit_log
                (partner_id, actor_user_id, action, before_json, after_json, reason)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            partner_id, actor_user_id, action,
            json.dumps(before) if before else None,
            json.dumps(after) if after else None,
            reason,
        )

    async def list_audit_for_partner(self, partner_id: UUID) -> list[PartnerAuditLogEntry]:
        rows = await self.conn.fetch(
            "SELECT * FROM partner_audit_log WHERE partner_id = $1 ORDER BY at DESC",
            partner_id,
        )
        return [
            PartnerAuditLogEntry(
                id=r["id"], partner_id=r["partner_id"],
                actor_user_id=r["actor_user_id"], action=r["action"],
                before_json=json.loads(r["before_json"]) if r["before_json"] else None,
                after_json=json.loads(r["after_json"]) if r["after_json"] else None,
                reason=r["reason"], at=r["at"],
            )
            for r in rows
        ]

    # ── Row mappers ─────────────────────────────────────────────────────

    @staticmethod
    def _row_to_partner(row: asyncpg.Record) -> Partner:
        return Partner(**dict(row))

    @staticmethod
    def _row_to_referral(row: asyncpg.Record) -> PartnerReferral:
        return PartnerReferral(**dict(row))

    @staticmethod
    def _row_to_commission(row: asyncpg.Record) -> PartnerCommission:
        return PartnerCommission(**dict(row))
```

### apps/backend-rag/backend/services/crm/partners/service.py

```
# backend/services/crm/partners/service.py
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException

from backend.services.crm.partners.models import Partner, PartnerAuditLogEntry
from backend.services.crm.partners.repository import PartnersRepository

logger = logging.getLogger(__name__)


class ConflictError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=409, detail=detail)


class PartnersService:
    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn
        self.repo = PartnersRepository(conn)

    async def create_partner(
        self,
        *,
        full_name: str,
        email: str,
        entity_type: str,
        assigned_to: UUID | None = None,
        created_by: UUID | None = None,
        **optional: Any,
    ) -> UUID:
        try:
            pid = await self.repo.insert_partner(
                full_name=full_name,
                email=email,
                entity_type=entity_type,
                assigned_to=assigned_to,
                created_by=created_by,
                **optional,
            )
        except ValueError as e:
            raise ConflictError(str(e))
        except asyncpg.UniqueViolationError:
            raise ConflictError(f"email already in use: {email!r}")
        after = {
            "full_name": full_name,
            "email": email,
            "assigned_to": str(assigned_to) if assigned_to else None,
        }
        await self.repo.insert_audit(
            partner_id=pid,
            action="created",
            actor_user_id=created_by,
            after=after,
        )
        return pid

    async def get_partner(self, partner_id: UUID, *, actor_user: UUID) -> Partner:
        return await verify_partner_access(self, actor_user, partner_id)

    async def list_partners(
        self,
        *,
        actor_user: UUID,
        actor_role: str,
        assigned_to: UUID | None = None,
        onboarding_status: str | None = None,
        orphaned: bool = False,
        search: str | None = None,
    ) -> list[Partner]:
        if actor_role == "team":
            assigned_to = actor_user  # force scope to own
        return await self.repo.list_partners(
            assigned_to=assigned_to,
            onboarding_status=onboarding_status,
            orphaned=orphaned,
            search=search,
        )

    async def update_partner(
        self,
        partner_id: UUID,
        *,
        actor_user: UUID,
        actor_role: str,
        **fields: Any,
    ) -> None:
        if actor_role == "partner":
            raise HTTPException(status_code=403, detail="partners may not update their own profile via this endpoint")
        current = await verify_partner_access_with_role(
            self, actor_user, actor_role, partner_id
        )
        before = {k: getattr(current, k) for k in fields if hasattr(current, k)}

exec
/bin/zsh -lc "sed -n '1641,2000p' /tmp/partners-review/brief.md" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
        try:
            await self.repo.update_partner(partner_id, **fields)
        except ValueError as e:
            raise ConflictError(str(e))
        await self.repo.insert_audit(
            partner_id=partner_id,
            action="updated",
            actor_user_id=actor_user,
            before=before,
            after=fields,
        )

    async def activate_partner(self, partner_id: UUID, *, actor_user: UUID) -> None:
        if not await _is_admin(self.conn, actor_user):
            raise HTTPException(status_code=403, detail="admin only")
        await self.repo.activate_partner(partner_id)
        await self.repo.insert_audit(
            partner_id=partner_id,
            action="activated",
            actor_user_id=actor_user,
        )

    async def deactivate_partner(self, partner_id: UUID, *, actor_user: UUID) -> None:
        if not await _is_admin(self.conn, actor_user):
            raise HTTPException(status_code=403, detail="admin only")
        await self.repo.deactivate_partner(partner_id)
        await self.repo.insert_audit(
            partner_id=partner_id,
            action="deactivated",
            actor_user_id=actor_user,
        )

    async def reassign_partner(
        self,
        partner_id: UUID,
        *,
        new_user_id: UUID | None,
        actor_user: UUID,
        reason: str | None,
    ) -> None:
        if not await _is_admin(self.conn, actor_user):
            raise HTTPException(status_code=403, detail="admin only")
        if not reason:
            raise ValueError("reason is required for reassignment")
        current = await self.repo.get_partner(partner_id)
        if current is None:
            raise HTTPException(status_code=404, detail="partner not found")
        before = {"assigned_to": str(current.assigned_to) if current.assigned_to else None}
        after = {"assigned_to": str(new_user_id) if new_user_id else None}
        await self.repo.reassign_partner(partner_id, new_user_id)
        await self.repo.insert_audit(
            partner_id=partner_id,
            action="reassigned",
            actor_user_id=actor_user,
            before=before,
            after=after,
            reason=reason,
        )

    async def orphan_partners_of_user(self, user_id: UUID, *, actor_user: UUID) -> int:
        if not await _is_admin(self.conn, actor_user):
            raise HTTPException(status_code=403, detail="admin only")
        affected = await self.repo.list_partners(assigned_to=user_id)
        n = await self.repo.orphan_partners_of_user(user_id)
        for p in affected:
            await self.repo.insert_audit(
                partner_id=p.id,
                action="orphaned",
                actor_user_id=actor_user,
                before={"assigned_to": str(user_id)},
                after={"assigned_to": None},
                reason=f"auto-orphan on deactivation of user {user_id}",
            )
        return n

    async def list_audit(self, partner_id: UUID) -> list[PartnerAuditLogEntry]:
        return await self.repo.list_audit_for_partner(partner_id)

    async def mark_welcome_sent(self, partner_id: UUID) -> None:
        await self.repo.mark_welcome_sent(partner_id)


async def _is_admin(conn: asyncpg.Connection, user_id: UUID) -> bool:
    row = await conn.fetchrow("SELECT role FROM users WHERE id = $1", user_id)
    return bool(row) and row["role"] == "admin"


async def _get_role(conn: asyncpg.Connection, user_id: UUID) -> str | None:
    row = await conn.fetchrow("SELECT role FROM users WHERE id = $1", user_id)
    return row["role"] if row else None


async def verify_partner_access(
    svc: PartnersService, actor_user: UUID, partner_id: UUID
) -> Partner:
    role = await _get_role(svc.conn, actor_user)
    return await verify_partner_access_with_role(svc, actor_user, role, partner_id)


async def verify_partner_access_with_role(
    svc: PartnersService,
    actor_user: UUID,
    actor_role: str | None,
    partner_id: UUID,
) -> Partner:
    partner = await svc.repo.get_partner(partner_id)
    if partner is None:
        raise HTTPException(status_code=404, detail="partner not found")
    if actor_role == "admin":
        return partner
    if actor_role == "team" and partner.assigned_to == actor_user:
        return partner
    if actor_role == "partner":
        # Check via users table: user.partner_id matches partner.id
        row = await svc.conn.fetchrow(
            "SELECT partner_id FROM users WHERE id = $1", actor_user
        )
        if row and row["partner_id"] == partner_id:
            return partner
    raise HTTPException(status_code=403, detail="forbidden")
```

### apps/backend-rag/backend/services/crm/partners/commission_engine.py

```
# backend/services/crm/partners/commission_engine.py
"""
CommissionEngine — pure-calculation + state-machine-transition layer.

Isolation contract: this module is the ONLY place that contains commission
business logic. It calls PartnersRepository directly and must not import
EventBus, FastAPI routers, or any other application-layer component (so it
can be tested with direct asyncpg connections and no side effects).

Business rules source of truth: docs/superpowers/specs/2026-04-20-crm-partners-module.md §4.4
Implementation plan: docs/superpowers/plans/2026-04-20-crm-partners-module.md Task 5

Append-only ledger exception (spec §Q9, plan Step 5.2):
  The partner_commissions table is append-only. The ONE documented exception
  is that approve() may reduce net_amount_idr on the incoming accrual row when
  offsetting a pending clawback. This is implemented via a raw UPDATE on that
  single column (search for "spec §Q9" in this file).

Pre-flight note (2026-04-20, outcome c):
  The `processes` table does not exist in the live Fly.io DB — it is a test
  stub only. Column names used in accrue_from_process() match the stub DDL
  added to conftest.py for Task 5:
      status TEXT, payment_status TEXT,
      total_invoiced_idr NUMERIC(16,2), completed_at TIMESTAMPTZ.
  If the processes table is later migrated into production, verify these
  column names against the real schema and add aliasing here if needed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg

from backend.services.crm.partners.repository import PartnersRepository

logger = logging.getLogger(__name__)

# Withholding rates keyed by tax_withholding_category.
# Rates are Decimal to avoid float rounding errors throughout all math.
# v1 placeholder values — Asya to confirm with tax advisor.
# Source: spec §4.4 rule 4.
_WITHHOLDING_RATES: dict[str, Decimal] = {
    "pph21": Decimal("2.5"),
    "pph23": Decimal("2.0"),
    "exempt": Decimal("0"),
    "tbd": Decimal("0"),  # also blocks approve() — see gate below
}


class CommissionEngine:
    """Encapsulates all commission accrual, approval, payment, and clawback logic.

    Args:
        conn: A live asyncpg.Connection. The caller is responsible for
              lifecycle (open/close, transaction wrapping if needed).
    """

    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn
        self.repo = PartnersRepository(conn)

    # ── Accrual ─────────────────────────────────────────────────────────────

    async def accrue_from_process(
        self,
        process_id: UUID,
        partner_id: UUID | None = None,
    ) -> UUID | None:
        """Accrue a commission for a completed+paid process.

        Reads the process row, validates status/payment_status, resolves the
        referral and partner, computes gross/withholding/net with snapshot
        semantics, then inserts an 'accrued' commission row.

        Returns:
            The new commission UUID, or None if the process is not yet eligible
            (not completed, not paid, no referral, or wrong partner_id).

        Idempotency:
            key = f"accrual:{process_id}:{completed_at.isoformat()}"
            A second call for the same process+completed_at is a no-op
            (ON CONFLICT DO NOTHING via UNIQUE index on idempotency_key).
        """
        # Step 1: fetch process — must be completed AND paid.
        # NOTE: Column names verified against conftest.py stub DDL (outcome c).
        # If a real processes migration uses different names, alias here only.
        proc = await self.conn.fetchrow(
            """
            SELECT id, status, payment_status, total_invoiced_idr, completed_at
            FROM processes WHERE id = $1
            """,
            process_id,
        )
        if proc is None:
            logger.debug("accrue_from_process: process %s not found", process_id)
            return None
        if proc["status"] != "completed" or proc["payment_status"] != "paid":
            logger.debug(
                "accrue_from_process: process %s not eligible (status=%s, payment_status=%s)",
                process_id, proc["status"], proc["payment_status"],
            )
            return None

        # Step 2: resolve referral.
        referral = await self.repo.get_referral_by_process(process_id)
        if referral is None:
            logger.debug("accrue_from_process: no referral for process %s", process_id)
            return None

        # Optional sanity-check: caller can assert which partner should receive the commission.
        if partner_id is not None and referral.partner_id != partner_id:
            logger.warning(
                "accrue_from_process: partner_id mismatch "
                "(referral.partner_id=%s, caller said %s) — skipping",
                referral.partner_id, partner_id,
            )
            return None

        # Step 3: resolve partner for snapshot values.
        partner = await self.repo.get_partner(referral.partner_id)
        if partner is None:
            logger.warning(
                "accrue_from_process: partner %s not found", referral.partner_id
            )
            return None

        # Step 4: compute amounts (all Decimal, no float).
        # base_amount_idr = processes.total_invoiced_idr (exact column name per stub DDL).
        base = Decimal(str(proc["total_invoiced_idr"]))

        if partner.default_commission_type == "percentage":
            gross = base * partner.default_commission_value / Decimal("100")
        else:
            # flat: commission_value is the fixed IDR amount regardless of base
            gross = partner.default_commission_value

        rate = _WITHHOLDING_RATES.get(partner.tax_withholding_category, Decimal("0"))
        # Withholding is quantized to whole IDR (no fractional rupiah).
        withholding = (gross * rate / Decimal("100")).quantize(Decimal("1"))
        net = gross - withholding

        # Step 5: resolve cooling-off days from system_settings.
        cooling_days = await self._system_setting_int("partner_accrual_cooling_off_days", 30)
        completed_at: datetime = proc["completed_at"] or datetime.now(timezone.utc)
        eligible = completed_at + timedelta(days=cooling_days)

        # Idempotency key: unique per process + completed_at timestamp.
        # If completed_at changes (e.g. re-completion edge case), a new accrual fires.
        key = f"accrual:{process_id}:{completed_at.isoformat()}"

        try:
            cid = await self.repo.insert_commission(
                partner_id=partner.id,
                entry_type="accrual",
                referral_id=referral.id,
                process_id=process_id,
                base_amount_idr=base,
                commission_type_snapshot=partner.default_commission_type,
                commission_value_snapshot=partner.default_commission_value,
                rule_source="partner_default",
                assigned_to_snapshot=partner.assigned_to,
                gross_amount_idr=gross,
                withholding_category=partner.tax_withholding_category,
                withholding_rate=rate,
                withholding_amount_idr=withholding,
                net_amount_idr=net,
                status="accrued",
                eligible_for_approval_at=eligible,
                idempotency_key=key,
            )
        except asyncpg.UniqueViolationError:
            logger.info(
                "accrue_from_process: idempotency hit for key=%s — no-op", key
            )
            return None

        logger.info(
            "Accrued commission %s for partner %s (gross=%s, net=%s IDR)",
            cid, partner.id, gross, net,
        )
        return cid

    # ── Approve ─────────────────────────────────────────────────────────────

    async def approve(self, commission_id: UUID, *, actor: UUID) -> None:
        """Transition a commission from 'accrued' to 'approved'.

        Gates:
          - status must be 'accrued'
          - eligible_for_approval_at must be <= now() (cooling-off elapsed)
          - withholding_category must not be 'tbd'

        Offset logic (spec §4.4 rule 7):
          If the partner has any 'clawback_pending' commissions, the OLDEST
          one is paired with this accrual:
            - clawback transitions to 'offset_applied'
            - this accrual's net_amount_idr is reduced by abs(clawback.net)
          If the clawback magnitude exceeds the accrual's net, no offset is
          applied this round (partial offsets are v2 scope).

        Atomicity note (v1):
          The offset writes two rows sequentially on a single connection.
          If a crash occurs between the net UPDATE and the clawback status
          UPDATE, the accrual row will have a reduced net but the clawback
          will still be 'clawback_pending'. This is flagged DONE_WITH_CONCERNS
          for v2 to wrap in an explicit transaction.
        """
        c = await self.repo.get_commission(commission_id)
        if c is None:
            raise ValueError(f"Commission not found: {commission_id}")
        if c.status != "accrued":
            raise ValueError(
                f"cannot approve commission with status {c.status!r} "
                f"(must be 'accrued')"
            )
        now = datetime.now(timezone.utc)
        if c.eligible_for_approval_at > now:
            raise ValueError(
                f"Commission is still within the cooling-off window "
                f"(eligible at {c.eligible_for_approval_at.isoformat()})"
            )
        if c.withholding_category == "tbd":
            raise ValueError(
                "withholding category is tbd — set pph21|pph23|exempt first"
            )

        # Offset against oldest clawback_pending, if any.
        pending = await self.repo.list_pending_clawbacks(c.partner_id)
        offset_applied_id: UUID | None = None
        if pending:
            oldest = pending[0]

exec
/bin/zsh -lc "sed -n '2001,2360p' /tmp/partners-review/brief.md" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
            # offset_amount is positive (magnitude of the negative clawback).
            offset_amount = -oldest.net_amount_idr
            new_net = c.net_amount_idr - offset_amount

            if new_net <= 0:
                # Clawback exceeds this accrual — defer to next approval cycle.
                # Partial offsets require additional policy decisions (v2 scope).
                logger.info(
                    "approve: clawback %s (magnitude %s) exceeds accrual %s net %s "
                    "— no offset this round",
                    oldest.id, offset_amount, c.id, c.net_amount_idr,
                )
            else:
                # ONE LEGAL LEDGER MUTATION (spec §Q9, plan Step 5.2):
                # Reduce this accrual's net by the clawback magnitude before
                # flipping the status to 'approved'. This is the only place
                # where a pre-existing commission row's net_amount_idr is
                # updated (all other commission writes go through insert_commission).
                await self.conn.execute(
                    "UPDATE partner_commissions SET net_amount_idr = $2 WHERE id = $1",
                    c.id,
                    new_net,
                )
                await self.repo.update_commission_status(oldest.id, "offset_applied")
                offset_applied_id = oldest.id
                logger.info(
                    "approve: offset clawback %s against accrual %s "
                    "(net reduced %s → %s IDR)",
                    oldest.id, c.id, c.net_amount_idr, new_net,
                )

        await self.repo.update_commission_status(
            commission_id, "approved", approved_by=actor
        )
        if offset_applied_id:
            logger.info(
                "approve: commission %s approved with clawback %s offset",
                commission_id, offset_applied_id,
            )
        else:
            logger.info("approve: commission %s approved (no clawback offset)", commission_id)

    # ── Mark paid ───────────────────────────────────────────────────────────

    async def mark_paid(
        self,
        commission_id: UUID,
        *,
        actor: UUID,
        paid_via: str,
        payment_reference: str,
        payment_proof_url: str | None = None,
        receipt_type: str | None = None,
        receipt_file_url: str | None = None,
    ) -> None:
        """Transition a commission from 'approved' to 'paid'."""
        await self.repo.update_commission_status(
            commission_id,
            "paid",
            paid_by=actor,
            paid_via=paid_via,
            payment_reference=payment_reference,
            payment_proof_url=payment_proof_url,
            receipt_type=receipt_type,
            receipt_file_url=receipt_file_url,
        )

    # ── Clawback ────────────────────────────────────────────────────────────

    async def clawback(
        self,
        original_commission_id: UUID,
        *,
        actor: UUID,
        reason: str,
        amount_idr: Decimal | None = None,
    ) -> UUID:
        """Issue a clawback against an approved or paid commission.

        Inserts a new 'clawback' entry_type row with negative amounts and
        status 'clawback_pending' (or 'waived' if the auto-writeoff threshold
        is configured and the amount is below it).

        Idempotency: NOT idempotent — each call inserts a new row. This is
        intentional: an operator may legitimately issue multiple partial
        clawbacks against the same original commission. The idempotency_key
        includes now().isoformat() to prevent accidental de-dup.

        Args:
            original_commission_id: The approved|paid commission to claw back.
            actor: The user UUID performing the operation.
            reason: Free-text justification (stored in clawback_reason).
            amount_idr: Override the clawback magnitude (positive IDR amount).
                        Defaults to the full net_amount_idr of the original.

        Returns:
            UUID of the newly created clawback row.
        """
        orig = await self.repo.get_commission(original_commission_id)
        if orig is None:
            raise ValueError(f"Commission not found: {original_commission_id}")
        if orig.status not in ("approved", "paid"):
            raise ValueError(
                f"Clawback only valid for approved|paid commissions, "
                f"got status {orig.status!r}"
            )

        # magnitude is the positive IDR amount to claw back
        magnitude = amount_idr if amount_idr is not None else orig.net_amount_idr
        gross_neg = -magnitude
        net_neg = -magnitude

        # Auto-writeoff: if the magnitude is below the threshold (and threshold > 0),
        # insert directly as 'waived' instead of 'clawback_pending'.
        threshold = await self._system_setting_int(
            "partner_clawback_auto_writeoff_idr", 0
        )
        auto_waive = threshold > 0 and abs(int(magnitude)) < threshold

        status = "waived" if auto_waive else "clawback_pending"

        # Key is NOT idempotent by design — see docstring above.
        key = f"clawback:{original_commission_id}:{datetime.now(timezone.utc).isoformat()}"

        cid = await self.repo.insert_commission(
            partner_id=orig.partner_id,
            entry_type="clawback",
            referral_id=orig.referral_id,
            process_id=orig.process_id,
            related_commission_id=orig.id,
            base_amount_idr=orig.base_amount_idr,
            commission_type_snapshot=orig.commission_type_snapshot,
            commission_value_snapshot=orig.commission_value_snapshot,
            assigned_to_snapshot=orig.assigned_to_snapshot,
            gross_amount_idr=gross_neg,
            withholding_category=orig.withholding_category,
            withholding_rate=orig.withholding_rate,
            withholding_amount_idr=Decimal("0"),
            net_amount_idr=net_neg,
            status=status,
            idempotency_key=key,
            clawback_reason=reason,
        )

        if auto_waive:
            logger.info(
                "clawback %s auto-waived (magnitude %s IDR < threshold %s IDR)",
                cid, magnitude, threshold,
            )
        else:
            logger.info(
                "clawback %s created (clawback_pending, magnitude %s IDR) "
                "against original %s",
                cid, magnitude, original_commission_id,
            )
        return cid

    # ── Waive clawback ──────────────────────────────────────────────────────

    async def waive_clawback(
        self,
        clawback_id: UUID,
        *,
        actor: UUID,
        reason: str,
    ) -> None:
        """Manually waive a 'clawback_pending' commission (operator decision)."""
        await self.repo.update_commission_status(
            clawback_id, "waived", waiver_reason=reason
        )

    # ── Helpers ─────────────────────────────────────────────────────────────

    async def _system_setting_int(self, key: str, default: int) -> int:
        """Read an integer value from the system_settings table.

        Returns `default` if the key is absent or the value cannot be
        coerced to int (e.g. empty string, garbage data).
        """
        row = await self.conn.fetchrow(
            "SELECT value FROM system_settings WHERE key = $1", key
        )
        try:
            return int(row["value"]) if row else default
        except (ValueError, TypeError):
            return default
```

### apps/backend-rag/backend/services/crm/partners/events.py

```
"""
EventBus subscriber for the CRM Partners module.

Subscribes to ``practice.status_changed`` (PG channel ``practice_changed``
aliased in event_bus.PG_CHANNEL_MAP).  When a process transitions to
``completed``, delegates accrual to :class:`CommissionEngine` and publishes
``partner.commission_changed`` via ``pg_notify`` on success.

Implementation plan: docs/superpowers/plans/2026-04-20-crm-partners-module.md Task 6
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from backend.app.db import get_pool
from backend.services.crm.partners.commission_engine import CommissionEngine

if TYPE_CHECKING:
    from backend.services.events.event_bus import EventBus

logger = logging.getLogger(__name__)

PARTNER_COMMISSION_CHANGED = "partner.commission_changed"


async def handle_practice_status_changed(payload: dict[str, Any]) -> None:
    """Handler for ``practice.status_changed`` events.

    Triggers commission accrual when a process flips to ``completed``.
    Payment status is re-verified inside
    :meth:`CommissionEngine.accrue_from_process` by querying the process row
    directly — the event payload may not carry ``payment_status``.

    Early-exit conditions (no DB access):
    - ``new_status`` != ``"completed"``
    - ``process_id`` is absent or falsy
    - ``process_id`` cannot be parsed as a UUID
    """
    new_status = payload.get("new_status")
    process_id = payload.get("process_id")

    if new_status != "completed" or not process_id:
        return

    try:
        pid = UUID(process_id) if isinstance(process_id, str) else process_id
    except (ValueError, TypeError):
        logger.warning(
            "handle_practice_status_changed: bad process_id %r", process_id
        )
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        engine = CommissionEngine(conn)
        cid = await engine.accrue_from_process(pid)
        if cid is None:
            return

        # Read partner_id for the notification payload
        row = await conn.fetchrow(
            "SELECT partner_id FROM partner_commissions WHERE id = $1", cid
        )
        if row is None:
            return
        partner_id = row["partner_id"]

    await _publish_changed(partner_id, cid, kind="accrued")


async def _publish_changed(
    partner_id: UUID,
    commission_id: UUID,
    *,
    kind: str,
) -> None:
    """Emit a ``partner.commission_changed`` notification via PostgreSQL NOTIFY.

    Uses parameterised ``pg_notify($1, $2)`` — NOT string-interpolated NOTIFY —
    to avoid SQL injection on malformed UUIDs or unexpected ``kind`` values.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        notification_payload = json.dumps(
            {
                "partner_id": str(partner_id),
                "commission_id": str(commission_id),
                "type": kind,
            }
        )
        # pg_notify with parameters — injection-safe
        await conn.execute(
            "SELECT pg_notify($1, $2)",
            PARTNER_COMMISSION_CHANGED,
            notification_payload,
        )
    logger.info(
        "Published partner.commission_changed: %s (%s)", commission_id, kind
    )


def register_partner_handlers(bus: "EventBus") -> None:
    """Subscribe partner-module handlers to the EventBus."""
    bus.subscribe("practice.status_changed", handle_practice_status_changed)
    logger.info("Partner handlers registered on practice.status_changed")
```

### apps/backend-rag/backend/services/crm/partners/emails.py

```
"""
Partner email module — welcome + commission-earned via Brevo.

Sending: POST /api/notifications/send-email with X-API-Key (Brevo).
Sender: zantara@balizero.com / Zantara (non-negotiable per feedback_email_sender).
Both functions are idempotent: they read the sentinel timestamp before sending
and call mark_*_sent only after a successful HTTP response.

PII sterilization (UU PDP 27/2022):
- Client full names are sterilized to "First L." before passing to any template.
- Sterilization happens in Python, never inside Jinja2 templates.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import jinja2

from backend.services.crm.partners.repository import PartnersRepository
from backend.services.pricing.pricing_service import get_pricing_service

logger = logging.getLogger(__name__)

# ─── Jinja2 environment ────────────────────────────────────────────────────
_TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=False,
    keep_trailing_newline=True,
)

# ─── Email API constants ────────────────────────────────────────────────────
# Sender MUST be zantara@balizero.com per feedback_email_sender memory rule.
SENDER_EMAIL = "zantara@balizero.com"
SENDER_NAME = "Zantara"
NOTIFICATIONS_ENDPOINT = os.environ.get(
    "NOTIFICATIONS_ENDPOINT",
    "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
X_API_KEY = os.environ.get("NOTIFICATIONS_X_API_KEY", "REDACTED-ROTATED-KEY")


# ─── Internal helpers ───────────────────────────────────────────────────────

async def _post_email(*, to: str, cc: list[str] | None, subject: str, body: str) -> None:
    """
    POST to the internal Brevo email relay endpoint.

    Payload shape matches the existing endpoint contract used by
    welcome_email_service.py — fields: to, subject, body, cc.
    Sender (from_email / from_name) is set server-side; the payload does not

exec
/bin/zsh -lc "sed -n '2361,2720p' /tmp/partners-review/brief.md" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
    include those fields.
    """
    payload: dict[str, Any] = {
        "to": to,
        "subject": subject,
        "body": body,
    }
    if cc:
        payload["cc"] = cc

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            NOTIFICATIONS_ENDPOINT,
            json=payload,
            headers={"X-API-Key": X_API_KEY},
        )
        r.raise_for_status()


def _sterilize(name: str) -> str:
    """
    Reduce a full name to "FirstName L." for UU PDP compliance.

    Examples:
      "Mario Rossi"        → "Mario R."
      "Alice"              → "Alice"
      "Jean-Claude Van Dam" → "Jean-Claude D."
      ""                   → ""
    """
    parts = name.strip().split()
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0]}."


def _build_pricing_services() -> list[dict[str, str]]:
    """Return list of {name, price_display} pairs from PricingService.

    The pricing JSON has 3 levels:
      services (top) -> sub_category (dict) -> service_name (dict key) -> {price, duration, ...}

    We flatten to a list of {name, price_display}. Returns empty list if
    PricingService is not loaded (graceful degradation for the welcome
    email — terms still communicate; services list is absent).

    Golden Rule #12: prices ONLY from PricingTool/PricingService, never hardcoded.
    """
    svc = get_pricing_service()
    if not getattr(svc, "loaded", False):
        logger.warning("PricingService not loaded — welcome email services list will be empty")
        return []
    all_prices = svc.get_all_prices() or {}
    top = all_prices.get("services", all_prices)
    result: list[dict[str, str]] = []
    if not isinstance(top, dict):
        return result
    for sub_cat, entries in top.items():
        if isinstance(entries, dict):
            for service_name, entry in entries.items():
                if not isinstance(entry, dict):
                    continue
                price_str = entry.get("price") or entry.get("final_price") or "On request"
                if not isinstance(price_str, str):
                    price_str = str(price_str)
                result.append({
                    "name": str(service_name),
                    "price_display": price_str,
                })
        elif isinstance(entries, list):
            # Legacy flat-list shape, keep for safety
            for item in entries:
                if isinstance(item, dict) and "name" in item:
                    result.append({
                        "name": str(item["name"]),
                        "price_display": str(item.get("price_display") or item.get("price") or "On request"),
                    })
    return result


# ─── Public API ─────────────────────────────────────────────────────────────

async def send_welcome(conn: Any, partner_id: UUID) -> None:
    """
    Send the partner welcome email.

    Idempotent: reads welcome_email_sent_at before sending.
    If already sent, logs and returns without HTTP call.

    Args:
        conn: asyncpg.Connection (passed directly by the router).
        partner_id: UUID of the partner.
    """
    repo = PartnersRepository(conn)
    p = await repo.get_partner(partner_id)
    if p is None:
        logger.warning("send_welcome: partner %s not found — skip", partner_id)
        return
    if p.welcome_email_sent_at is not None:
        logger.info("send_welcome: already sent for partner %s — skip (idempotent)", partner_id)
        return

    pricing_services = _build_pricing_services()

    commission_rate = (
        f"{p.default_commission_value}%"
        if p.default_commission_type == "percentage"
        else f"IDR {p.default_commission_value:,.0f}"
    )

    tpl = _env.get_template("welcome.md.j2")
    body = tpl.render(
        partner=p,
        commission_rate=commission_rate,
        commission_type=p.default_commission_type,
        pricing_services=pricing_services,
    )

    await _post_email(
        to=p.email,
        cc=None,
        subject="Welcome to Bali Zero Partners",
        body=body,
    )
    await repo.mark_welcome_sent(partner_id)
    logger.info("send_welcome: sent to partner %s (%s)", partner_id, p.email)


async def send_commission_earned(conn: Any, commission_id: UUID) -> None:
    """
    Send the commission-earned notification email.

    Idempotent: reads commission_email_sent_at before sending.
    Client name is sterilized to "First L." BEFORE template rendering (UU PDP).

    Args:
        conn: asyncpg.Connection (passed directly by the router).
        commission_id: UUID of the partner_commissions row.
    """
    repo = PartnersRepository(conn)
    c = await repo.get_commission(commission_id)
    if c is None or c.status != "paid":
        logger.info(
            "send_commission_earned: commission %s not found or not paid — skip",
            commission_id,
        )
        return
    if c.commission_email_sent_at is not None:
        logger.info(
            "send_commission_earned: already sent for commission %s — skip (idempotent)",
            commission_id,
        )
        return

    p = await repo.get_partner(c.partner_id)
    if p is None:
        logger.warning("send_commission_earned: partner %s not found — skip", c.partner_id)
        return

    # Fetch process + client name via JOIN
    proc = None
    if c.process_id is not None:
        proc = await conn.fetchrow(
            """
            SELECT p.service_type, c.full_name AS client_name
            FROM processes p
            LEFT JOIN clients c ON c.id = p.client_id
            WHERE p.id = $1
            """,
            c.process_id,
        )

    service_type = (proc["service_type"] if proc and proc["service_type"] else "service") if proc else "service"
    raw_client_name = (proc["client_name"] or "") if proc else ""

    # UU PDP: sterilize BEFORE template render, never inside template
    client_display = _sterilize(raw_client_name) if raw_client_name else "client"

    # CC the assigned-to user if resolvable
    cc_list: list[str] = []
    if c.assigned_to_snapshot is not None:
        row = await conn.fetchrow(
            "SELECT email FROM users WHERE id = $1",
            c.assigned_to_snapshot,
        )
        if row and row["email"]:
            cc_list.append(row["email"])

    tpl = _env.get_template("commission.md.j2")
    body = tpl.render(
        partner=p,
        client_display=client_display,
        service_type=service_type,
        gross_idr=f"{c.gross_amount_idr:,.0f}",
        withholding_idr=f"{c.withholding_amount_idr:,.0f}",
        withholding_category=c.withholding_category,
        net_idr=f"{c.net_amount_idr:,.0f}",
        paid_via=c.paid_via or "",
        payment_reference=c.payment_reference or "",
        paid_at=c.paid_at.isoformat() if c.paid_at else "",
        receipt_file_url=c.receipt_file_url,
    )

    subject = f"Commissione maturata — {client_display}"
    await _post_email(
        to=p.email,
        cc=cc_list if cc_list else None,
        subject=subject,
        body=body,
    )
    await repo.mark_commission_email_sent(commission_id)
    logger.info("send_commission_earned: sent for commission %s to %s", commission_id, p.email)
```

### apps/backend-rag/backend/services/crm/partners/templates/welcome.md.j2

```
# Welcome to Bali Zero Partners

Hi {{ partner.full_name }},

Welcome aboard! You're now part of the Bali Zero partner network.

## Commission structure

Your default commission is **{{ commission_rate }}**
({{ commission_type }}). Commission accrues on each completed + paid process
that lists you as the referrer.

Payment flow:
1. Process marked **completed + paid** → commission accrues.
2. 30-day cooling-off period (eligible date shown in your dashboard).
3. Asya reviews and approves for payout.
4. Paid via bank transfer (or e-wallet) in IDR. Payment proof uploaded.

## Our services

{% for service in pricing_services %}
- **{{ service.name }}** — from {{ service.price_display }}
{% endfor %}

Full pricing on your partner dashboard.

## Terms

- Commission is paid **only** when the linked process is **completed + paid**.
- Refunds within 30 days trigger a clawback deducted from your next accrual.
- Your personal data is stored for referral tracking and commission payment
  only (UU PDP 27/2022). You may request deletion by replying to this email.

## Your portal

Access your referrals and commissions at
https://kita.balizero.com/portal/partner/dashboard

Questions? Reply to this email.

— Zantara, Bali Zero
```

### apps/backend-rag/backend/services/crm/partners/templates/commission.md.j2

```
# Commission earned — {{ client_display }}

Hi {{ partner.full_name }},

Good news: a commission has been paid for your referral on the
**{{ service_type }}** service for **{{ client_display }}**.

| Field | Amount (IDR) |
|---|---|
| Gross | {{ gross_idr }} |
| Withholding ({{ withholding_category }}) | {{ withholding_idr }} |
| **Net paid** | **{{ net_idr }}** |

**Paid via:** {{ paid_via }} · **Reference:** {{ payment_reference }} ·
**Paid at:** {{ paid_at }}

{% if receipt_file_url %}
Receipt: {{ receipt_file_url }}
{% endif %}

Reminder: if the client refunds or cancels after payment, a clawback is
deducted from your next commission automatically.

— Zantara, Bali Zero
```

### apps/backend-rag/backend/app/routers/partners.py

```
"""
FastAPI router — CRM Partners module (v1).

21 endpoints covering partner lifecycle, referrals, commissions, self-serve
/me routes for partner-role users, and a finance CSV export.

SCAR 2026-03-26: every mutation handler does `except HTTPException: raise`
BEFORE the generic `except Exception`.

Pre-flight findings (2026-04-20):
- get_current_user returns dict[str, Any] with keys:
    email, user_id, role, permissions (list, not set)
  NOT an object — use user["role"], user["user_id"].
- No partner_id in user dict; /me endpoints query users.partner_id from DB.
- DB dep is get_database_pool (returns Pool); use `async with pool.acquire() as conn`.
- Finance permission: check "finance.mark_paid" in permissions list; admin alone
  is sufficient as v1 fallback (permissions not yet wired to JWT for all clients).
"""
from __future__ import annotations

import csv
import dataclasses
import io
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, EmailStr

from backend.app.dependencies import get_current_user, get_database_pool
from backend.services.crm.partners.commission_engine import CommissionEngine
from backend.services.crm.partners.service import (
    ConflictError,
    PartnersService,
    verify_partner_access_with_role,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/partners", tags=["partners"])


# ── Pydantic request models ──────────────────────────────────────────────────

class PartnerCreate(BaseModel):
    full_name: str
    email: EmailStr
    entity_type: Literal["individual", "corporate_pt", "corporate_cv", "foreign"]
    work_role: str | None = None
    company_name: str | None = None
    office_address: str | None = None
    phone: str | None = None
    preferred_language: str = "id"
    npwp: str | None = None
    nik: str | None = None
    tax_withholding_category: Literal["pph21", "pph23", "exempt", "tbd"] = "tbd"
    fiscal_address: str | None = None
    bank_name: str | None = None
    bank_account_holder: str | None = None
    bank_account_number: str | None = None
    ewallet_type: str | None = None
    ewallet_number: str | None = None
    payment_currency: str = "IDR"

exec
/bin/zsh -lc "sed -n '2721,3080p' /tmp/partners-review/brief.md" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
    iban: str | None = None
    payment_notes: str | None = None
    default_commission_type: Literal["percentage", "flat"] = "percentage"
    default_commission_value: Decimal = Decimal("10.0")
    assigned_to: UUID | None = None
    pdp_consent_version: str | None = None
    terms_version: str | None = None


class PartnerUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    entity_type: Literal["individual", "corporate_pt", "corporate_cv", "foreign"] | None = None
    work_role: str | None = None
    company_name: str | None = None
    office_address: str | None = None
    phone: str | None = None
    preferred_language: str | None = None
    npwp: str | None = None
    nik: str | None = None
    tax_withholding_category: Literal["pph21", "pph23", "exempt", "tbd"] | None = None
    fiscal_address: str | None = None
    bank_name: str | None = None
    bank_account_holder: str | None = None
    bank_account_number: str | None = None
    ewallet_type: str | None = None
    ewallet_number: str | None = None
    payment_currency: str | None = None
    iban: str | None = None
    payment_notes: str | None = None
    default_commission_type: Literal["percentage", "flat"] | None = None
    default_commission_value: Decimal | None = None
    pdp_consent_version: str | None = None
    terms_version: str | None = None


class ReassignRequest(BaseModel):
    new_user_id: UUID | None
    reason: str


class BulkReassignRequest(BaseModel):
    partner_ids: list[UUID]
    new_user_id: UUID
    reason: str


class ReferralCreate(BaseModel):
    process_id: UUID
    notes: str | None = None


class ReferralSwap(BaseModel):
    new_partner_id: UUID


class CommissionMarkPaidRequest(BaseModel):
    paid_via: str
    payment_reference: str
    payment_proof_url: str | None = None
    receipt_type: Literal["kwitansi", "invoice", "none"] | None = None
    receipt_file_url: str | None = None


class ClawbackRequest(BaseModel):
    reason: str
    amount_idr: Decimal | None = None


class WaiveRequest(BaseModel):
    reason: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def _require_admin(user: dict[str, Any]) -> None:
    """Raise 403 if user is not admin."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin only")


def _require_finance(user: dict[str, Any]) -> None:
    """Raise 403 if user lacks finance permission.

    v1 fallback: admin role alone is sufficient because permissions list
    may not be populated in all JWT tokens yet. When finance.mark_paid is
    wired into the JWT payload, this guard will enforce it for non-admins.
    """
    perms = user.get("permissions", [])
    if user.get("role") == "admin":
        return  # admin always has finance
    if "finance.mark_paid" in perms:
        return
    raise HTTPException(status_code=403, detail="finance permission required")


def _sterilize_client_for_partner(full_name: str) -> str:
    """'Mario Rossi' → 'Mario R.' — hide client surname from partner-role user."""
    parts = full_name.strip().split()
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0]}."


def _partner_to_dict(p: Any) -> dict[str, Any]:
    """Convert Partner dataclass or asyncpg Record to JSON-serialisable dict."""
    if dataclasses.is_dataclass(p) and not isinstance(p, type):
        return dataclasses.asdict(p)
    return dict(p)


# ── Partner CRUD ─────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_partner(
    body: PartnerCreate,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """Create a new partner. Team members auto-assign to themselves."""
    try:
        async with pool.acquire() as conn:
            svc = PartnersService(conn)
            data = body.model_dump(exclude_none=True)
            assigned_to = data.pop("assigned_to", None)
            # Team role: always scope to self (ignore any supplied assigned_to)
            if user.get("role") == "team":
                assigned_to = UUID(str(user["user_id"]))
            elif assigned_to is None and user.get("role") == "admin":
                assigned_to = None  # explicit None allowed for admin
            pid = await svc.create_partner(
                assigned_to=assigned_to,
                created_by=UUID(str(user["user_id"])),
                **data,
            )
            partner = await svc.repo.get_partner(pid)
            return _partner_to_dict(partner)
    except HTTPException:
        raise
    except Exception:
        logger.exception("create_partner failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.get("")
async def list_partners(
    assigned_to: UUID | None = None,
    onboarding_status: str | None = None,
    orphaned: bool = False,
    search: str | None = None,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """List partners. Team members see only their own."""
    async with pool.acquire() as conn:
        svc = PartnersService(conn)
        partners = await svc.list_partners(
            actor_user=UUID(str(user["user_id"])),
            actor_role=user.get("role", "team"),
            assigned_to=assigned_to,
            onboarding_status=onboarding_status,
            orphaned=orphaned,
            search=search,
        )
        return [_partner_to_dict(p) for p in partners]


@router.get("/me")
async def me(
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """Self-view for partner-role users. Returns their own partner record."""
    if user.get("role") != "partner":
        raise HTTPException(status_code=403, detail="partner role required")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT partner_id FROM users WHERE id = $1",
            UUID(str(user["user_id"])),
        )
        if not row or not row["partner_id"]:
            raise HTTPException(status_code=403, detail="no partner profile linked to this user")
        svc = PartnersService(conn)
        partner = await svc.repo.get_partner(row["partner_id"])
        if partner is None:
            raise HTTPException(status_code=404, detail="partner record not found")
        return _partner_to_dict(partner)


@router.get("/me/referrals")
async def me_referrals(
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """List referrals for the calling partner user. Client data is sterilized."""
    if user.get("role") != "partner":
        raise HTTPException(status_code=403, detail="partner role required")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT partner_id FROM users WHERE id = $1",
            UUID(str(user["user_id"])),
        )
        if not row or not row["partner_id"]:
            raise HTTPException(status_code=403, detail="no partner profile linked to this user")
        partner_id = row["partner_id"]
        rows = await conn.fetch(
            """
            SELECT pr.id, pr.process_id, pr.referred_at,
                   p.status AS process_status, p.service_type,
                   c.full_name AS client_name
            FROM partner_referrals pr
            LEFT JOIN processes p ON p.id = pr.process_id
            LEFT JOIN clients c ON c.id = p.client_id
            WHERE pr.partner_id = $1
            ORDER BY pr.referred_at DESC
            """,
            partner_id,
        )
    return [
        {
            "id": str(r["id"]),
            "process_id": str(r["process_id"]),
            "service_type": r["service_type"],
            "process_status": r["process_status"],
            "client_display": _sterilize_client_for_partner(r["client_name"] or ""),
            "referred_at": r["referred_at"].isoformat() if r["referred_at"] else None,
        }
        for r in rows
    ]


@router.get("/me/commissions")
async def me_commissions(
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """List commissions for the calling partner user."""
    if user.get("role") != "partner":
        raise HTTPException(status_code=403, detail="partner role required")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT partner_id FROM users WHERE id = $1",
            UUID(str(user["user_id"])),
        )
        if not row or not row["partner_id"]:
            raise HTTPException(status_code=403, detail="no partner profile linked to this user")
        svc = PartnersService(conn)
        commissions = await svc.repo.list_commissions_for_partner(row["partner_id"])
        return [
            dataclasses.asdict(c) if dataclasses.is_dataclass(c) else dict(c)
            for c in commissions
        ]


@router.get("/finance/export")
async def finance_export(
    from_: str = Query(..., alias="from"),
    to: str = Query(...),
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """Finance CSV export. Admin + finance permission required."""
    _require_admin(user)
    _require_finance(user)
    # Validate ISO format before hitting SQL — bad input → 400 not 500
    try:
        datetime.fromisoformat(from_)
        datetime.fromisoformat(to)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"invalid date format (expected ISO): {e}")
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT pc.id, p.full_name, p.npwp, p.entity_type,
                       pc.entry_type, pc.gross_amount_idr, pc.withholding_category,
                       pc.withholding_amount_idr, pc.net_amount_idr, pc.status,
                       pc.paid_at, pc.paid_via, pc.payment_reference
                FROM partner_commissions pc
                JOIN partners p ON p.id = pc.partner_id
                WHERE pc.created_at >= $1::timestamptz
                  AND pc.created_at <  $2::timestamptz
                ORDER BY pc.created_at ASC
                """,
                from_, to,
            )
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "commission_id", "partner", "npwp", "entity_type", "entry_type",
            "gross_idr", "withholding_category", "withholding_idr", "net_idr",
            "status", "paid_at", "paid_via", "payment_reference",
        ])
        for r in rows:
            writer.writerow([r[k] for k in r.keys()])
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="partners-{from_}-to-{to}.csv"'
            },
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("finance_export failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/{partner_id}")
async def get_partner(
    partner_id: UUID,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """Get a partner by ID. Scoped by role."""
    async with pool.acquire() as conn:
        svc = PartnersService(conn)
        partner = await verify_partner_access_with_role(
            svc,
            UUID(str(user["user_id"])),
            user.get("role"),
            partner_id,
        )
        return _partner_to_dict(partner)


@router.patch("/{partner_id}")
async def update_partner(
    partner_id: UUID,
    body: PartnerUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """Update a partner. Team members can only update their own assigned partners."""
    try:
        async with pool.acquire() as conn:
            svc = PartnersService(conn)
            fields = body.model_dump(exclude_none=True, exclude_unset=True)
            await svc.update_partner(
                partner_id,
                actor_user=UUID(str(user["user_id"])),
                actor_role=user.get("role", "team"),
                **fields,
            )
            partner = await svc.repo.get_partner(partner_id)
            return _partner_to_dict(partner)
    except HTTPException:
        raise
    except Exception:
        logger.exception("update_partner failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.post("/{partner_id}/activate", status_code=status.HTTP_204_NO_CONTENT)
async def activate_partner(
    partner_id: UUID,
    user: dict[str, Any] = Depends(get_current_user),

exec
/bin/zsh -lc "sed -n '3081,3440p' /tmp/partners-review/brief.md" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """Activate a partner. Admin only."""
    _require_admin(user)
    try:
        async with pool.acquire() as conn:
            svc = PartnersService(conn)
            await svc.activate_partner(partner_id, actor_user=UUID(str(user["user_id"])))
            # Trigger welcome email if emails module is available (Task 8)
            try:
                from backend.services.crm.partners.emails import send_welcome
                await send_welcome(conn, partner_id)
            except ImportError:
                pass  # emails module not yet implemented (Task 8)
            return Response(status_code=204)
    except HTTPException:
        raise
    except Exception:
        logger.exception("activate_partner failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.post("/{partner_id}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_partner(
    partner_id: UUID,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """Deactivate a partner. Admin only."""
    _require_admin(user)
    try:
        async with pool.acquire() as conn:
            svc = PartnersService(conn)
            await svc.deactivate_partner(partner_id, actor_user=UUID(str(user["user_id"])))
            return Response(status_code=204)
    except HTTPException:
        raise
    except Exception:
        logger.exception("deactivate_partner failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.post("/{partner_id}/reassign", status_code=status.HTTP_204_NO_CONTENT)
async def reassign_partner(
    partner_id: UUID,
    body: ReassignRequest,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """Reassign a partner to a different team member. Admin only."""
    _require_admin(user)
    try:
        async with pool.acquire() as conn:
            svc = PartnersService(conn)
            await svc.reassign_partner(
                partner_id,
                new_user_id=body.new_user_id,
                actor_user=UUID(str(user["user_id"])),
                reason=body.reason,
            )
            return Response(status_code=204)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("reassign_partner failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.post("/bulk-reassign", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_reassign(
    body: BulkReassignRequest,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """Bulk-reassign multiple partners to a single user. Admin only."""
    _require_admin(user)
    try:
        async with pool.acquire() as conn:
            svc = PartnersService(conn)
            for pid in body.partner_ids:
                await svc.reassign_partner(
                    pid,
                    new_user_id=body.new_user_id,
                    actor_user=UUID(str(user["user_id"])),
                    reason=body.reason,
                )
            return Response(status_code=204)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("bulk_reassign failed")
        raise HTTPException(status_code=500, detail="internal error")


# ── Referrals ────────────────────────────────────────────────────────────────

@router.get("/{partner_id}/referrals")
async def list_referrals(
    partner_id: UUID,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """List referrals for a partner. Scoped by role."""
    async with pool.acquire() as conn:
        svc = PartnersService(conn)
        await verify_partner_access_with_role(
            svc, UUID(str(user["user_id"])), user.get("role"), partner_id
        )
        refs = await svc.repo.list_referrals_for_partner(partner_id)
        return [
            dataclasses.asdict(r) if dataclasses.is_dataclass(r) else dict(r)
            for r in refs
        ]


@router.post("/{partner_id}/referrals", status_code=status.HTTP_201_CREATED)
async def create_referral(
    partner_id: UUID,
    body: ReferralCreate,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """Record a referral for a partner. Team (owner) or admin."""
    try:
        async with pool.acquire() as conn:
            svc = PartnersService(conn)
            await verify_partner_access_with_role(
                svc, UUID(str(user["user_id"])), user.get("role"), partner_id
            )
            rid = await svc.repo.insert_referral(
                partner_id=partner_id,
                process_id=body.process_id,
                referred_by_user_id=UUID(str(user["user_id"])),
                notes=body.notes,
            )
            return {"id": str(rid), "partner_id": str(partner_id), "process_id": str(body.process_id)}
    except HTTPException:
        raise
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="process already has a referral")
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="process already has a referral")
        logger.exception("create_referral failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.patch("/referrals/{referral_id}", status_code=status.HTTP_204_NO_CONTENT)
async def swap_referral(
    referral_id: UUID,
    body: ReferralSwap,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """Swap a referral to a different partner. Admin only."""
    _require_admin(user)
    try:
        async with pool.acquire() as conn:
            svc = PartnersService(conn)
            await svc.repo.update_referral_partner(referral_id, body.new_partner_id)
            return Response(status_code=204)
    except HTTPException:
        raise
    except Exception:
        logger.exception("swap_referral failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.delete("/referrals/{referral_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_referral(
    referral_id: UUID,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """Delete a referral. Admin only. Blocked if commissions exist."""
    _require_admin(user)
    try:
        async with pool.acquire() as conn:
            svc = PartnersService(conn)
            await svc.repo.delete_referral(referral_id)
            return Response(status_code=204)
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception:
        logger.exception("delete_referral failed")
        raise HTTPException(status_code=500, detail="internal error")


# ── Commissions ───────────────────────────────────────────────────────────────

@router.get("/{partner_id}/commissions")
async def list_commissions(
    partner_id: UUID,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """List commissions for a partner. Scoped by role."""
    async with pool.acquire() as conn:
        svc = PartnersService(conn)
        await verify_partner_access_with_role(
            svc, UUID(str(user["user_id"])), user.get("role"), partner_id
        )
        commissions = await svc.repo.list_commissions_for_partner(partner_id)
        return [
            dataclasses.asdict(c) if dataclasses.is_dataclass(c) else dict(c)
            for c in commissions
        ]


@router.get("/{partner_id}/audit-log")
async def list_partner_audit_log(
    partner_id: UUID,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """List the audit log for a partner. Admin or team-owner only."""
    try:
        async with pool.acquire() as conn:
            svc = PartnersService(conn)
            await verify_partner_access_with_role(svc, UUID(str(user["user_id"])), user.get("role"), partner_id)
            entries = await svc.list_audit(partner_id)
            return [_partner_to_dict(e) for e in entries]
    except HTTPException:
        raise
    except Exception:
        logger.exception("list_partner_audit_log failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.post("/commissions/{commission_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
async def approve_commission(
    commission_id: UUID,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """Approve a commission. Admin + finance permission."""
    _require_admin(user)
    _require_finance(user)
    try:
        async with pool.acquire() as conn:
            engine = CommissionEngine(conn)
            await engine.approve(commission_id, actor=UUID(str(user["user_id"])))
            return Response(status_code=204)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("approve_commission failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.post("/commissions/{commission_id}/mark-paid", status_code=status.HTTP_204_NO_CONTENT)
async def mark_paid_commission(
    commission_id: UUID,
    body: CommissionMarkPaidRequest,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """Mark a commission as paid. Admin + finance permission."""
    _require_admin(user)
    _require_finance(user)
    try:
        async with pool.acquire() as conn:
            engine = CommissionEngine(conn)
            await engine.mark_paid(
                commission_id,
                actor=UUID(str(user["user_id"])),
                paid_via=body.paid_via,
                payment_reference=body.payment_reference,
                payment_proof_url=body.payment_proof_url,
                receipt_type=body.receipt_type,
                receipt_file_url=body.receipt_file_url,
            )
            # Trigger commission-paid email if emails module is available (Task 8)
            try:
                from backend.services.crm.partners.emails import send_commission_earned
                await send_commission_earned(conn, commission_id)
            except ImportError:
                pass
            return Response(status_code=204)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("mark_paid_commission failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.post("/commissions/{commission_id}/clawback", status_code=status.HTTP_201_CREATED)
async def clawback_commission(
    commission_id: UUID,
    body: ClawbackRequest,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Any:
    """Initiate a clawback on a commission. Admin + finance permission. Returns new commission id."""
    _require_admin(user)
    _require_finance(user)
    try:
        async with pool.acquire() as conn:
            engine = CommissionEngine(conn)
            cid = await engine.clawback(
                commission_id,
                actor=UUID(str(user["user_id"])),
                reason=body.reason,
                amount_idr=body.amount_idr,
            )
            return {"id": str(cid)}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("clawback_commission failed")
        raise HTTPException(status_code=500, detail="internal error")


@router.post("/commissions/{commission_id}/waive", status_code=status.HTTP_204_NO_CONTENT)
async def waive_commission(
    commission_id: UUID,
    body: WaiveRequest,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> Response:
    """Waive a clawback on a commission. Admin + finance permission."""
    _require_admin(user)
    _require_finance(user)
    try:
        async with pool.acquire() as conn:
            engine = CommissionEngine(conn)
            await engine.waive_clawback(
                commission_id,
                actor=UUID(str(user["user_id"])),
                reason=body.reason,
            )
            return Response(status_code=204)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("waive_commission failed")
        raise HTTPException(status_code=500, detail="internal error")
```

### apps/backend-rag/backend/tests/integration/test_partners_e2e.py

```
"""
End-to-end: process completed+paid → accrual → approve → pay → email.

Covers the full partner lifecycle:

exec
/bin/zsh -lc "sed -n '3441,3606p' /tmp/partners-review/brief.md" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
  activate → welcome email → referral → complete+paid →
  EventBus accrual → approve → mark paid → commission email with
  client-name sterilization (UU PDP).

Placed in backend/tests/integration/ with its own conftest.py that
re-exports all partner fixtures from services/crm/partners/conftest.py
(option a — import bridge).
"""
from __future__ import annotations

import contextlib
import uuid
from decimal import Decimal

import pytest

from backend.services.crm.partners.commission_engine import CommissionEngine
from backend.services.crm.partners.events import handle_practice_status_changed
from backend.services.crm.partners.emails import send_welcome, send_commission_earned
from backend.services.crm.partners.service import PartnersService
import backend.services.crm.partners.events as events_mod


@pytest.mark.asyncio
async def test_full_flow_process_to_paid_email(
    db_conn,
    user_factory,
    partner_factory,
    process_factory,
    client_factory,
    referral_factory,
    monkeypatch,
):
    # ── Setup: create users ──────────────────────────────────────────────────
    admin_id = await user_factory(role="admin")
    team_id = await user_factory(role="team")
    partner_id = await partner_factory(
        tax_withholding_category="pph23",
        default_commission_value=Decimal("10.0"),
        assigned_to=uuid.UUID(int=admin_id.int),
    )

    # ── Capture email sends ─────────────────────────────────────────────────
    send_calls: list[dict] = []

    async def fake_post(*, to, cc, subject, body):
        send_calls.append({"to": to, "cc": cc, "subject": subject, "body": body})

    import backend.services.crm.partners.emails as emails_mod
    monkeypatch.setattr(emails_mod, "_post_email", fake_post)

    # Mock PricingService to avoid heavy loading in test environment
    monkeypatch.setattr(
        emails_mod,
        "_build_pricing_services",
        lambda: [{"name": "KITAS E33G", "price_display": "Rp 12.500.000"}],
    )

    # ── Step 1: Admin activates partner → then send welcome email ───────────
    svc = PartnersService(db_conn)
    await svc.activate_partner(uuid.UUID(int=partner_id.int), actor_user=uuid.UUID(int=admin_id.int))
    await send_welcome(db_conn, uuid.UUID(int=partner_id.int))

    assert len(send_calls) == 1, f"Expected 1 call after welcome, got {len(send_calls)}"
    assert "Welcome" in send_calls[0]["subject"] or "welcome" in send_calls[0]["subject"].lower(), \
        f"Welcome subject not found: {send_calls[0]['subject']}"

    # ── Step 2: Create client + process + referral ───────────────────────────
    client_id = await client_factory(full_name="Mario Rossi")

    # process_factory doesn't accept client_id/service_type directly — create
    # process then update it to link the client.
    process_id = await process_factory(
        total_invoiced_idr=Decimal("15000000"),
        status="completed",
        payment_status="paid",
    )
    # Link client and service_type to the process
    await db_conn.execute(
        "UPDATE processes SET client_id = $1, service_type = 'KITAS E33G' WHERE id = $2",
        int(client_id),
        uuid.UUID(int=process_id.int),
    )

    await referral_factory(
        partner_id=uuid.UUID(int=partner_id.int),
        process_id=uuid.UUID(int=process_id.int),
    )

    # ── Step 3: EventBus handler → accrual ──────────────────────────────────
    class FakePool:
        def acquire(self):
            @contextlib.asynccontextmanager
            async def _cm():
                yield db_conn
            return _cm()

    async def fake_get_pool():
        return FakePool()

    monkeypatch.setattr(events_mod, "get_pool", fake_get_pool)

    await handle_practice_status_changed({
        "process_id": str(uuid.UUID(int=process_id.int)),
        "new_status": "completed",
    })

    # ── Step 4: Verify accrual ───────────────────────────────────────────────
    engine = CommissionEngine(db_conn)
    commissions = await engine.repo.list_commissions_for_partner(
        uuid.UUID(int=partner_id.int)
    )
    assert len(commissions) == 1, f"Expected 1 commission, got {len(commissions)}"
    c = commissions[0]
    assert c.status == "accrued", f"Expected status=accrued, got {c.status}"

    # 10% of 15_000_000 = 1_500_000 gross.
    # pph23 rate: check what the engine uses — typically 2% withholding for pph23.
    # We just verify gross matches.
    assert c.gross_amount_idr == Decimal("1500000"), \
        f"Expected gross 1500000, got {c.gross_amount_idr}"
    assert c.withholding_amount_idr == Decimal("30000"), \
        f"Expected withholding 30000 (2% pph23 of 1500000), got {c.withholding_amount_idr}"
    assert c.net_amount_idr == Decimal("1470000"), \
        f"Expected net 1470000 (gross - withholding), got {c.net_amount_idr}"

    # ── Step 5: Fast-forward cooling-off ────────────────────────────────────
    await db_conn.execute(
        "UPDATE partner_commissions SET eligible_for_approval_at = now() - interval '1 day' WHERE id = $1",
        c.id,
    )

    # ── Step 6: Approve ──────────────────────────────────────────────────────
    await engine.approve(c.id, actor=uuid.UUID(int=admin_id.int))
    refreshed = await engine.repo.get_commission(c.id)
    assert refreshed is not None
    assert refreshed.status == "approved", f"Expected approved, got {refreshed.status}"

    # ── Step 7: Mark paid + commission email ─────────────────────────────────
    await engine.mark_paid(
        c.id,
        actor=uuid.UUID(int=admin_id.int),
        paid_via="BCA transfer",
        payment_reference="TX-20260520-001",
    )
    await send_commission_earned(db_conn, c.id)

    # ── Step 8: Verify commission email was sent ─────────────────────────────
    commission_call = next(
        (
            call for call in send_calls
            if "Commissione" in call["subject"]
            or "commission" in call["subject"].lower()
            or "Commission" in call["subject"]
        ),
        None,
    )
    assert commission_call is not None, (
        f"Commission email not sent; all call subjects: {[c['subject'] for c in send_calls]}"
    )

    # ── Step 9: Verify sterilization (UU PDP) ────────────────────────────────
    body = commission_call["body"]
    assert "Mario Rossi" not in body, "Full client name leaked — UU PDP violation"
    assert "Mario R." in body, f"Sterilized client name 'Mario R.' missing from body"
```

exec
/bin/zsh -lc 'rg -n "''^### apps/|''^## Key|DONE_WITH_CONCERNS|KNOWN RACE|Pre-flight|silently|pass|TODO|FIXME|admin alone|autoescape|X_API_KEY|mark_paid|approve'"\\(|offset|EventBus|processes table\" /tmp/partners-review/brief.md" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
8:- 10 commits, 128 backend tests passing.
18:3. **Race conditions** — EventBus redelivery, commission offset without transaction wrapper, email idempotency under retry.
20:5. **Production readiness** — what fails silently on first real use?
63:- EventBus channel `partner_commission_changed` + subscriber
237:      'clawback_pending','offset_applied',
322:├── events.py             # EventBus subscriber + publisher
371:- `finance.mark_paid`
405:`CommissionEngine.approve(commission_id, actor)`:
411:`CommissionEngine.mark_paid(commission_id, actor, paid_via, payment_reference, receipt_type?, receipt_file_url?)`:
426:- Offset: on next `approve()` for same partner, pair with oldest
428:offset_applied`, approval net reduced by clawback amount).
430:### 4.5 EventBus integration
489:Trigger: `CommissionEngine.mark_paid()` completion.
568:├── test_commission_engine.py  # accrual, cooling-off, clawback, offset
569:├── test_events.py             # EventBus subscriber idempotency
593:| S4     | CommissionEngine (accrual + cooling-off + clawback + offset) + 30+ unit tests | 4h  |
594:| S5     | EventBus subscriber on `practice_changed` + idempotency + integration test    | 2h  |
622:# 3. EventBus subscriber active
655:## Key Backend Files
658:### apps/backend-rag/backend/migrations/migration_119_partners.py
882:                            'clawback_pending','offset_applied',
1004:### apps/backend-rag/backend/services/crm/partners/models.py
1021:    "clawback_pending", "offset_applied",
1130:### apps/backend-rag/backend/services/crm/partners/repository.py
1154:# v1 terminal states: paid, offset_applied, waived, repaid.
1159:    "clawback_pending": {"offset_applied", "waived", "repaid"},
1160:    "offset_applied": set(),
1212:        KNOWN RACE: This is a SELECT-then-INSERT pattern without a cross-table
1540:### apps/backend-rag/backend/services/crm/partners/service.py
1763:### apps/backend-rag/backend/services/crm/partners/commission_engine.py
1772:EventBus, FastAPI routers, or any other application-layer component (so it
1780:  is that approve() may reduce net_amount_idr on the incoming accrual row when
1781:  offsetting a pending clawback. This is implemented via a raw UPDATE on that
1784:Pre-flight note (2026-04-20, outcome c):
1790:  If the processes table is later migrated into production, verify these
1815:    "tbd": Decimal("0"),  # also blocks approve() — see gate below
1954:    async def approve(self, commission_id: UUID, *, actor: UUID) -> None:
1965:            - clawback transitions to 'offset_applied'
1967:          If the clawback magnitude exceeds the accrual's net, no offset is
1968:          applied this round (partial offsets are v2 scope).
1971:          The offset writes two rows sequentially on a single connection.
1974:          will still be 'clawback_pending'. This is flagged DONE_WITH_CONCERNS
1998:        offset_applied_id: UUID | None = None
2001:            # offset_amount is positive (magnitude of the negative clawback).
2002:            offset_amount = -oldest.net_amount_idr
2003:            new_net = c.net_amount_idr - offset_amount
2007:                # Partial offsets require additional policy decisions (v2 scope).
2010:                    "— no offset this round",
2011:                    oldest.id, offset_amount, c.id, c.net_amount_idr,
2024:                await self.repo.update_commission_status(oldest.id, "offset_applied")
2025:                offset_applied_id = oldest.id
2027:                    "approve: offset clawback %s against accrual %s "
2035:        if offset_applied_id:
2037:                "approve: commission %s approved with clawback %s offset",
2038:                commission_id, offset_applied_id,
2041:            logger.info("approve: commission %s approved (no clawback offset)", commission_id)
2045:    async def mark_paid(
2189:### apps/backend-rag/backend/services/crm/partners/events.py
2193:EventBus subscriber for the CRM Partners module.
2213:    from backend.services.events.event_bus import EventBus
2296:def register_partner_handlers(bus: "EventBus") -> None:
2297:    """Subscribe partner-module handlers to the EventBus."""
2302:### apps/backend-rag/backend/services/crm/partners/emails.py
2314:- Client full names are sterilized to "First L." before passing to any template.
2337:    autoescape=False,
2349:X_API_KEY = os.environ.get("NOTIFICATIONS_X_API_KEY", "REDACTED-ROTATED-KEY")
2375:            headers={"X-API-Key": X_API_KEY},
2452:        conn: asyncpg.Connection (passed directly by the router).
2498:        conn: asyncpg.Connection (passed directly by the router).
2576:### apps/backend-rag/backend/services/crm/partners/templates/welcome.md.j2
2622:### apps/backend-rag/backend/services/crm/partners/templates/commission.md.j2
2651:### apps/backend-rag/backend/app/routers/partners.py
2663:Pre-flight findings (2026-04-20):
2669:- Finance permission: check "finance.mark_paid" in permissions list; admin alone
2806:    may not be populated in all JWT tokens yet. When finance.mark_paid is
2812:    if "finance.mark_paid" in perms:
3094:                pass  # emails module not yet implemented (Task 8)
3328:            await engine.approve(commission_id, actor=UUID(str(user["user_id"])))
3340:async def mark_paid_commission(
3352:            await engine.mark_paid(
3366:                pass
3373:        logger.exception("mark_paid_commission failed")
3434:### apps/backend-rag/backend/tests/integration/test_partners_e2e.py
3442:  EventBus accrual → approve → mark paid → commission email with
3530:    # ── Step 3: EventBus handler → accrual ──────────────────────────────────
3574:    await engine.approve(c.id, actor=uuid.UUID(int=admin_id.int))
3580:    await engine.mark_paid(

codex
I’ve found several deeper failure modes in the brief itself: the generic partner list route is not role-gated, referral creation trusts partner/team callers too much, finance transitions are not transactional, and the email path can persist payment state while losing the notification. I’m pulling exact local line refs now.
exec
/bin/zsh -lc "nl -ba apps/backend-rag/backend/app/routers/partners.py | sed -n '1,260p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
     1	"""
     2	FastAPI router — CRM Partners module (v1).
     3	
     4	21 endpoints covering partner lifecycle, referrals, commissions, self-serve
     5	/me routes for partner-role users, and a finance CSV export.
     6	
     7	SCAR 2026-03-26: every mutation handler does `except HTTPException: raise`
     8	BEFORE the generic `except Exception`.
     9	
    10	Pre-flight findings (2026-04-20):
    11	- get_current_user returns dict[str, Any] with keys:
    12	    email, user_id, role, permissions (list, not set)
    13	  NOT an object — use user["role"], user["user_id"].
    14	- No partner_id in user dict; /me endpoints query users.partner_id from DB.
    15	- DB dep is get_database_pool (returns Pool); use `async with pool.acquire() as conn`.
    16	- Finance permission: check "finance.mark_paid" in permissions list; admin alone
    17	  is sufficient as v1 fallback (permissions not yet wired to JWT for all clients).
    18	"""
    19	from __future__ import annotations
    20	
    21	import csv
    22	import dataclasses
    23	import io
    24	import logging
    25	from datetime import datetime
    26	from decimal import Decimal
    27	from typing import Any, Literal
    28	from uuid import UUID
    29	
    30	import asyncpg
    31	from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
    32	from pydantic import BaseModel, EmailStr
    33	
    34	from backend.app.dependencies import get_current_user, get_database_pool
    35	from backend.services.crm.partners.commission_engine import CommissionEngine
    36	from backend.services.crm.partners.service import (
    37	    ConflictError,
    38	    PartnersService,
    39	    verify_partner_access_with_role,
    40	)
    41	
    42	logger = logging.getLogger(__name__)
    43	
    44	router = APIRouter(prefix="/api/partners", tags=["partners"])
    45	
    46	
    47	# ── Pydantic request models ──────────────────────────────────────────────────
    48	
    49	class PartnerCreate(BaseModel):
    50	    full_name: str
    51	    email: EmailStr
    52	    entity_type: Literal["individual", "corporate_pt", "corporate_cv", "foreign"]
    53	    work_role: str | None = None
    54	    company_name: str | None = None
    55	    office_address: str | None = None
    56	    phone: str | None = None
    57	    preferred_language: str = "id"
    58	    npwp: str | None = None
    59	    nik: str | None = None
    60	    tax_withholding_category: Literal["pph21", "pph23", "exempt", "tbd"] = "tbd"
    61	    fiscal_address: str | None = None
    62	    bank_name: str | None = None
    63	    bank_account_holder: str | None = None
    64	    bank_account_number: str | None = None
    65	    ewallet_type: str | None = None
    66	    ewallet_number: str | None = None
    67	    payment_currency: str = "IDR"
    68	    iban: str | None = None
    69	    payment_notes: str | None = None
    70	    default_commission_type: Literal["percentage", "flat"] = "percentage"
    71	    default_commission_value: Decimal = Decimal("10.0")
    72	    assigned_to: UUID | None = None
    73	    pdp_consent_version: str | None = None
    74	    terms_version: str | None = None
    75	
    76	
    77	class PartnerUpdate(BaseModel):
    78	    full_name: str | None = None
    79	    email: EmailStr | None = None
    80	    entity_type: Literal["individual", "corporate_pt", "corporate_cv", "foreign"] | None = None
    81	    work_role: str | None = None
    82	    company_name: str | None = None
    83	    office_address: str | None = None
    84	    phone: str | None = None
    85	    preferred_language: str | None = None
    86	    npwp: str | None = None
    87	    nik: str | None = None
    88	    tax_withholding_category: Literal["pph21", "pph23", "exempt", "tbd"] | None = None
    89	    fiscal_address: str | None = None
    90	    bank_name: str | None = None
    91	    bank_account_holder: str | None = None
    92	    bank_account_number: str | None = None
    93	    ewallet_type: str | None = None
    94	    ewallet_number: str | None = None
    95	    payment_currency: str | None = None
    96	    iban: str | None = None
    97	    payment_notes: str | None = None
    98	    default_commission_type: Literal["percentage", "flat"] | None = None
    99	    default_commission_value: Decimal | None = None
   100	    pdp_consent_version: str | None = None
   101	    terms_version: str | None = None
   102	
   103	
   104	class ReassignRequest(BaseModel):
   105	    new_user_id: UUID | None
   106	    reason: str
   107	
   108	
   109	class BulkReassignRequest(BaseModel):
   110	    partner_ids: list[UUID]
   111	    new_user_id: UUID
   112	    reason: str
   113	
   114	
   115	class ReferralCreate(BaseModel):
   116	    process_id: UUID
   117	    notes: str | None = None
   118	
   119	
   120	class ReferralSwap(BaseModel):
   121	    new_partner_id: UUID
   122	
   123	
   124	class CommissionMarkPaidRequest(BaseModel):
   125	    paid_via: str
   126	    payment_reference: str
   127	    payment_proof_url: str | None = None
   128	    receipt_type: Literal["kwitansi", "invoice", "none"] | None = None
   129	    receipt_file_url: str | None = None
   130	
   131	
   132	class ClawbackRequest(BaseModel):
   133	    reason: str
   134	    amount_idr: Decimal | None = None
   135	
   136	
   137	class WaiveRequest(BaseModel):
   138	    reason: str
   139	
   140	
   141	# ── Helpers ──────────────────────────────────────────────────────────────────
   142	
   143	def _require_admin(user: dict[str, Any]) -> None:
   144	    """Raise 403 if user is not admin."""
   145	    if user.get("role") != "admin":
   146	        raise HTTPException(status_code=403, detail="admin only")
   147	
   148	
   149	def _require_finance(user: dict[str, Any]) -> None:
   150	    """Raise 403 if user lacks finance permission.
   151	
   152	    v1 fallback: admin role alone is sufficient because permissions list
   153	    may not be populated in all JWT tokens yet. When finance.mark_paid is
   154	    wired into the JWT payload, this guard will enforce it for non-admins.
   155	    """
   156	    perms = user.get("permissions", [])
   157	    if user.get("role") == "admin":
   158	        return  # admin always has finance
   159	    if "finance.mark_paid" in perms:
   160	        return
   161	    raise HTTPException(status_code=403, detail="finance permission required")
   162	
   163	
   164	def _sterilize_client_for_partner(full_name: str) -> str:
   165	    """'Mario Rossi' → 'Mario R.' — hide client surname from partner-role user."""
   166	    parts = full_name.strip().split()
   167	    if not parts:
   168	        return ""
   169	    if len(parts) == 1:
   170	        return parts[0]
   171	    return f"{parts[0]} {parts[-1][0]}."
   172	
   173	
   174	def _partner_to_dict(p: Any) -> dict[str, Any]:
   175	    """Convert Partner dataclass or asyncpg Record to JSON-serialisable dict."""
   176	    if dataclasses.is_dataclass(p) and not isinstance(p, type):
   177	        return dataclasses.asdict(p)
   178	    return dict(p)
   179	
   180	
   181	# ── Partner CRUD ─────────────────────────────────────────────────────────────
   182	
   183	@router.post("", status_code=status.HTTP_201_CREATED)
   184	async def create_partner(
   185	    body: PartnerCreate,
   186	    user: dict[str, Any] = Depends(get_current_user),
   187	    pool: asyncpg.Pool = Depends(get_database_pool),
   188	) -> Any:
   189	    """Create a new partner. Team members auto-assign to themselves."""
   190	    try:
   191	        async with pool.acquire() as conn:
   192	            svc = PartnersService(conn)
   193	            data = body.model_dump(exclude_none=True)
   194	            assigned_to = data.pop("assigned_to", None)
   195	            # Team role: always scope to self (ignore any supplied assigned_to)
   196	            if user.get("role") == "team":
   197	                assigned_to = UUID(str(user["user_id"]))
   198	            elif assigned_to is None and user.get("role") == "admin":
   199	                assigned_to = None  # explicit None allowed for admin
   200	            pid = await svc.create_partner(
   201	                assigned_to=assigned_to,
   202	                created_by=UUID(str(user["user_id"])),
   203	                **data,
   204	            )
   205	            partner = await svc.repo.get_partner(pid)
   206	            return _partner_to_dict(partner)
   207	    except HTTPException:
   208	        raise
   209	    except Exception:
   210	        logger.exception("create_partner failed")
   211	        raise HTTPException(status_code=500, detail="internal error")
   212	
   213	
   214	@router.get("")
   215	async def list_partners(
   216	    assigned_to: UUID | None = None,
   217	    onboarding_status: str | None = None,
   218	    orphaned: bool = False,
   219	    search: str | None = None,
   220	    user: dict[str, Any] = Depends(get_current_user),
   221	    pool: asyncpg.Pool = Depends(get_database_pool),
   222	) -> Any:
   223	    """List partners. Team members see only their own."""
   224	    async with pool.acquire() as conn:
   225	        svc = PartnersService(conn)
   226	        partners = await svc.list_partners(
   227	            actor_user=UUID(str(user["user_id"])),
   228	            actor_role=user.get("role", "team"),
   229	            assigned_to=assigned_to,
   230	            onboarding_status=onboarding_status,
   231	            orphaned=orphaned,
   232	            search=search,
   233	        )
   234	        return [_partner_to_dict(p) for p in partners]
   235	
   236	
   237	@router.get("/me")
   238	async def me(
   239	    user: dict[str, Any] = Depends(get_current_user),
   240	    pool: asyncpg.Pool = Depends(get_database_pool),
   241	) -> Any:
   242	    """Self-view for partner-role users. Returns their own partner record."""
   243	    if user.get("role") != "partner":
   244	        raise HTTPException(status_code=403, detail="partner role required")
   245	    async with pool.acquire() as conn:
   246	        row = await conn.fetchrow(
   247	            "SELECT partner_id FROM users WHERE id = $1",
   248	            UUID(str(user["user_id"])),
   249	        )
   250	        if not row or not row["partner_id"]:
   251	            raise HTTPException(status_code=403, detail="no partner profile linked to this user")
   252	        svc = PartnersService(conn)
   253	        partner = await svc.repo.get_partner(row["partner_id"])
   254	        if partner is None:
   255	            raise HTTPException(status_code=404, detail="partner record not found")
   256	        return _partner_to_dict(partner)
   257	
   258	
   259	@router.get("/me/referrals")
   260	async def me_referrals(

exec
/bin/zsh -lc "nl -ba apps/backend-rag/backend/services/crm/partners/commission_engine.py | sed -n '1,300p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
     1	# backend/services/crm/partners/commission_engine.py
     2	"""
     3	CommissionEngine — pure-calculation + state-machine-transition layer.
     4	
     5	Isolation contract: this module is the ONLY place that contains commission
     6	business logic. It calls PartnersRepository directly and must not import
     7	EventBus, FastAPI routers, or any other application-layer component (so it
     8	can be tested with direct asyncpg connections and no side effects).
     9	
    10	Business rules source of truth: docs/superpowers/specs/2026-04-20-crm-partners-module.md §4.4
    11	Implementation plan: docs/superpowers/plans/2026-04-20-crm-partners-module.md Task 5
    12	
    13	Append-only ledger exception (spec §Q9, plan Step 5.2):
    14	  The partner_commissions table is append-only. The ONE documented exception
    15	  is that approve() may reduce net_amount_idr on the incoming accrual row when
    16	  offsetting a pending clawback. This is implemented via a raw UPDATE on that
    17	  single column (search for "spec §Q9" in this file).
    18	
    19	Pre-flight note (2026-04-20, outcome c):
    20	  The `processes` table does not exist in the live Fly.io DB — it is a test
    21	  stub only. Column names used in accrue_from_process() match the stub DDL
    22	  added to conftest.py for Task 5:
    23	      status TEXT, payment_status TEXT,
    24	      total_invoiced_idr NUMERIC(16,2), completed_at TIMESTAMPTZ.
    25	  If the processes table is later migrated into production, verify these
    26	  column names against the real schema and add aliasing here if needed.
    27	"""
    28	from __future__ import annotations
    29	
    30	import logging
    31	from datetime import datetime, timedelta, timezone
    32	from decimal import Decimal
    33	from typing import Any
    34	from uuid import UUID
    35	
    36	import asyncpg
    37	
    38	from backend.services.crm.partners.repository import PartnersRepository
    39	
    40	logger = logging.getLogger(__name__)
    41	
    42	# Withholding rates keyed by tax_withholding_category.
    43	# Rates are Decimal to avoid float rounding errors throughout all math.
    44	# v1 placeholder values — Asya to confirm with tax advisor.
    45	# Source: spec §4.4 rule 4.
    46	_WITHHOLDING_RATES: dict[str, Decimal] = {
    47	    "pph21": Decimal("2.5"),
    48	    "pph23": Decimal("2.0"),
    49	    "exempt": Decimal("0"),
    50	    "tbd": Decimal("0"),  # also blocks approve() — see gate below
    51	}
    52	
    53	
    54	class CommissionEngine:
    55	    """Encapsulates all commission accrual, approval, payment, and clawback logic.
    56	
    57	    Args:
    58	        conn: A live asyncpg.Connection. The caller is responsible for
    59	              lifecycle (open/close, transaction wrapping if needed).
    60	    """
    61	
    62	    def __init__(self, conn: asyncpg.Connection) -> None:
    63	        self.conn = conn
    64	        self.repo = PartnersRepository(conn)
    65	
    66	    # ── Accrual ─────────────────────────────────────────────────────────────
    67	
    68	    async def accrue_from_process(
    69	        self,
    70	        process_id: UUID,
    71	        partner_id: UUID | None = None,
    72	    ) -> UUID | None:
    73	        """Accrue a commission for a completed+paid process.
    74	
    75	        Reads the process row, validates status/payment_status, resolves the
    76	        referral and partner, computes gross/withholding/net with snapshot
    77	        semantics, then inserts an 'accrued' commission row.
    78	
    79	        Returns:
    80	            The new commission UUID, or None if the process is not yet eligible
    81	            (not completed, not paid, no referral, or wrong partner_id).
    82	
    83	        Idempotency:
    84	            key = f"accrual:{process_id}:{completed_at.isoformat()}"
    85	            A second call for the same process+completed_at is a no-op
    86	            (ON CONFLICT DO NOTHING via UNIQUE index on idempotency_key).
    87	        """
    88	        # Step 1: fetch process — must be completed AND paid.
    89	        # NOTE: Column names verified against conftest.py stub DDL (outcome c).
    90	        # If a real processes migration uses different names, alias here only.
    91	        proc = await self.conn.fetchrow(
    92	            """
    93	            SELECT id, status, payment_status, total_invoiced_idr, completed_at
    94	            FROM processes WHERE id = $1
    95	            """,
    96	            process_id,
    97	        )
    98	        if proc is None:
    99	            logger.debug("accrue_from_process: process %s not found", process_id)
   100	            return None
   101	        if proc["status"] != "completed" or proc["payment_status"] != "paid":
   102	            logger.debug(
   103	                "accrue_from_process: process %s not eligible (status=%s, payment_status=%s)",
   104	                process_id, proc["status"], proc["payment_status"],
   105	            )
   106	            return None
   107	
   108	        # Step 2: resolve referral.
   109	        referral = await self.repo.get_referral_by_process(process_id)
   110	        if referral is None:
   111	            logger.debug("accrue_from_process: no referral for process %s", process_id)
   112	            return None
   113	
   114	        # Optional sanity-check: caller can assert which partner should receive the commission.
   115	        if partner_id is not None and referral.partner_id != partner_id:
   116	            logger.warning(
   117	                "accrue_from_process: partner_id mismatch "
   118	                "(referral.partner_id=%s, caller said %s) — skipping",
   119	                referral.partner_id, partner_id,
   120	            )
   121	            return None
   122	
   123	        # Step 3: resolve partner for snapshot values.
   124	        partner = await self.repo.get_partner(referral.partner_id)
   125	        if partner is None:
   126	            logger.warning(
   127	                "accrue_from_process: partner %s not found", referral.partner_id
   128	            )
   129	            return None
   130	
   131	        # Step 4: compute amounts (all Decimal, no float).
   132	        # base_amount_idr = processes.total_invoiced_idr (exact column name per stub DDL).
   133	        base = Decimal(str(proc["total_invoiced_idr"]))
   134	
   135	        if partner.default_commission_type == "percentage":
   136	            gross = base * partner.default_commission_value / Decimal("100")
   137	        else:
   138	            # flat: commission_value is the fixed IDR amount regardless of base
   139	            gross = partner.default_commission_value
   140	
   141	        rate = _WITHHOLDING_RATES.get(partner.tax_withholding_category, Decimal("0"))
   142	        # Withholding is quantized to whole IDR (no fractional rupiah).
   143	        withholding = (gross * rate / Decimal("100")).quantize(Decimal("1"))
   144	        net = gross - withholding
   145	
   146	        # Step 5: resolve cooling-off days from system_settings.
   147	        cooling_days = await self._system_setting_int("partner_accrual_cooling_off_days", 30)
   148	        completed_at: datetime = proc["completed_at"] or datetime.now(timezone.utc)
   149	        eligible = completed_at + timedelta(days=cooling_days)
   150	
   151	        # Idempotency key: unique per process + completed_at timestamp.
   152	        # If completed_at changes (e.g. re-completion edge case), a new accrual fires.
   153	        key = f"accrual:{process_id}:{completed_at.isoformat()}"
   154	
   155	        try:
   156	            cid = await self.repo.insert_commission(
   157	                partner_id=partner.id,
   158	                entry_type="accrual",
   159	                referral_id=referral.id,
   160	                process_id=process_id,
   161	                base_amount_idr=base,
   162	                commission_type_snapshot=partner.default_commission_type,
   163	                commission_value_snapshot=partner.default_commission_value,
   164	                rule_source="partner_default",
   165	                assigned_to_snapshot=partner.assigned_to,
   166	                gross_amount_idr=gross,
   167	                withholding_category=partner.tax_withholding_category,
   168	                withholding_rate=rate,
   169	                withholding_amount_idr=withholding,
   170	                net_amount_idr=net,
   171	                status="accrued",
   172	                eligible_for_approval_at=eligible,
   173	                idempotency_key=key,
   174	            )
   175	        except asyncpg.UniqueViolationError:
   176	            logger.info(
   177	                "accrue_from_process: idempotency hit for key=%s — no-op", key
   178	            )
   179	            return None
   180	
   181	        logger.info(
   182	            "Accrued commission %s for partner %s (gross=%s, net=%s IDR)",
   183	            cid, partner.id, gross, net,
   184	        )
   185	        return cid
   186	
   187	    # ── Approve ─────────────────────────────────────────────────────────────
   188	
   189	    async def approve(self, commission_id: UUID, *, actor: UUID) -> None:
   190	        """Transition a commission from 'accrued' to 'approved'.
   191	
   192	        Gates:
   193	          - status must be 'accrued'
   194	          - eligible_for_approval_at must be <= now() (cooling-off elapsed)
   195	          - withholding_category must not be 'tbd'
   196	
   197	        Offset logic (spec §4.4 rule 7):
   198	          If the partner has any 'clawback_pending' commissions, the OLDEST
   199	          one is paired with this accrual:
   200	            - clawback transitions to 'offset_applied'
   201	            - this accrual's net_amount_idr is reduced by abs(clawback.net)
   202	          If the clawback magnitude exceeds the accrual's net, no offset is
   203	          applied this round (partial offsets are v2 scope).
   204	
   205	        Atomicity note (v1):
   206	          The offset writes two rows sequentially on a single connection.
   207	          If a crash occurs between the net UPDATE and the clawback status
   208	          UPDATE, the accrual row will have a reduced net but the clawback
   209	          will still be 'clawback_pending'. This is flagged DONE_WITH_CONCERNS
   210	          for v2 to wrap in an explicit transaction.
   211	        """
   212	        c = await self.repo.get_commission(commission_id)
   213	        if c is None:
   214	            raise ValueError(f"Commission not found: {commission_id}")
   215	        if c.status != "accrued":
   216	            raise ValueError(
   217	                f"cannot approve commission with status {c.status!r} "
   218	                f"(must be 'accrued')"
   219	            )
   220	        now = datetime.now(timezone.utc)
   221	        if c.eligible_for_approval_at > now:
   222	            raise ValueError(
   223	                f"Commission is still within the cooling-off window "
   224	                f"(eligible at {c.eligible_for_approval_at.isoformat()})"
   225	            )
   226	        if c.withholding_category == "tbd":
   227	            raise ValueError(
   228	                "withholding category is tbd — set pph21|pph23|exempt first"
   229	            )
   230	
   231	        # Offset against oldest clawback_pending, if any.
   232	        pending = await self.repo.list_pending_clawbacks(c.partner_id)
   233	        offset_applied_id: UUID | None = None
   234	        if pending:
   235	            oldest = pending[0]
   236	            # offset_amount is positive (magnitude of the negative clawback).
   237	            offset_amount = -oldest.net_amount_idr
   238	            new_net = c.net_amount_idr - offset_amount
   239	
   240	            if new_net <= 0:
   241	                # Clawback exceeds this accrual — defer to next approval cycle.
   242	                # Partial offsets require additional policy decisions (v2 scope).
   243	                logger.info(
   244	                    "approve: clawback %s (magnitude %s) exceeds accrual %s net %s "
   245	                    "— no offset this round",
   246	                    oldest.id, offset_amount, c.id, c.net_amount_idr,
   247	                )
   248	            else:
   249	                # ONE LEGAL LEDGER MUTATION (spec §Q9, plan Step 5.2):
   250	                # Reduce this accrual's net by the clawback magnitude before
   251	                # flipping the status to 'approved'. This is the only place
   252	                # where a pre-existing commission row's net_amount_idr is
   253	                # updated (all other commission writes go through insert_commission).
   254	                await self.conn.execute(
   255	                    "UPDATE partner_commissions SET net_amount_idr = $2 WHERE id = $1",
   256	                    c.id,
   257	                    new_net,
   258	                )
   259	                await self.repo.update_commission_status(oldest.id, "offset_applied")
   260	                offset_applied_id = oldest.id
   261	                logger.info(
   262	                    "approve: offset clawback %s against accrual %s "
   263	                    "(net reduced %s → %s IDR)",
   264	                    oldest.id, c.id, c.net_amount_idr, new_net,
   265	                )
   266	
   267	        await self.repo.update_commission_status(
   268	            commission_id, "approved", approved_by=actor
   269	        )
   270	        if offset_applied_id:
   271	            logger.info(
   272	                "approve: commission %s approved with clawback %s offset",
   273	                commission_id, offset_applied_id,
   274	            )
   275	        else:
   276	            logger.info("approve: commission %s approved (no clawback offset)", commission_id)
   277	
   278	    # ── Mark paid ───────────────────────────────────────────────────────────
   279	
   280	    async def mark_paid(
   281	        self,
   282	        commission_id: UUID,
   283	        *,
   284	        actor: UUID,
   285	        paid_via: str,
   286	        payment_reference: str,
   287	        payment_proof_url: str | None = None,
   288	        receipt_type: str | None = None,
   289	        receipt_file_url: str | None = None,
   290	    ) -> None:
   291	        """Transition a commission from 'approved' to 'paid'."""
   292	        await self.repo.update_commission_status(
   293	            commission_id,
   294	            "paid",
   295	            paid_by=actor,
   296	            paid_via=paid_via,
   297	            payment_reference=payment_reference,
   298	            payment_proof_url=payment_proof_url,
   299	            receipt_type=receipt_type,
   300	            receipt_file_url=receipt_file_url,

exec
/bin/zsh -lc "rg --files | rg 'partners|migration_119|router_manifest|middleware|process'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
apps/war-room/agents/015_qwen_preprocessor.py
docs/superpowers/reviews/2026-04-21-partners-v1/04-nb2.md
docs/superpowers/reviews/2026-04-21-partners-v1/99-synthesis.md
docs/superpowers/reviews/2026-04-21-partners-v1/01-gemini.md
docs/superpowers/reviews/2026-04-21-partners-v1/02-codex.md
docs/superpowers/reviews/2026-04-21-partners-v1/03-deepseek.md
apps/backend-rag/process_batches_2_3.py
apps/admin-dashboard/tests/middleware.test.ts
docs/superpowers/specs/2026-04-20-partners-brainstorm/04-nb2.md
docs/superpowers/specs/2026-04-20-partners-brainstorm/99-synthesis.md
docs/superpowers/specs/2026-04-20-partners-brainstorm/01-gemini.md
docs/superpowers/specs/2026-04-20-partners-brainstorm/00-brief.md
docs/superpowers/specs/2026-04-20-partners-brainstorm/02-codex.md
docs/superpowers/specs/2026-04-20-partners-brainstorm/03-deepseek.md
docs/superpowers/specs/2026-03-20-process-kanban-redesign.md
docs/superpowers/specs/2026-04-20-crm-partners-module.md
apps/backend-rag/scripts/staging_processor.py
docs/superpowers/plans/2026-03-20-process-kanban-redesign.md
docs/superpowers/plans/2026-04-20-crm-partners-module.md
apps/bali-intel-scraper/backend/processors/translator.py
apps/bali-intel-scraper/backend/processors/entities.py
apps/bali-intel-scraper/backend/processors/summarizer.py
apps/bali-intel-scraper/backend/processors/keywords.py
apps/bali-intel-scraper/backend/processors/fake_news.py
apps/bali-intel-scraper/backend/processors/deduplicator.py
apps/bali-intel-scraper/backend/processors/sentiment.py
apps/bali-intel-scraper/backend/processors/quality_scorer.py
apps/bali-intel-scraper/backend/processors/classifier.py
apps/admin-dashboard/middleware.ts
apps/bali-intel-scraper/backend/app/middleware/rate_limit.py
apps/backend-rag/backend/tests/test_process_split.py
apps/mouth/src/lib/schemas/process.ts
apps/mouth/src/lib/schemas/process.test.ts
apps/mouth/src/lib/api/partners/partners.ts
apps/mouth/src/__tests__/middleware.test.ts
apps/mouth/src/components/process/kanban-colors.ts
apps/mouth/src/components/process/GhostCard.tsx
apps/mouth/src/components/process/MonthPillTabs.tsx
apps/backend-rag/tests/integration/test_middleware_comprehensive.py
apps/backend-rag/backend/tests/setup/test_router_manifest.py
apps/backend-rag/backend/tests/services/crm/partners/test_emails.py
apps/backend-rag/backend/tests/services/crm/partners/test_events.py
apps/backend-rag/backend/tests/services/crm/partners/__init__.py
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py
apps/backend-rag/backend/tests/services/crm/partners/test_service.py
apps/backend-rag/backend/tests/services/crm/partners/conftest.py
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py
apps/mouth/src/components/partners/ReferrerDropdown.tsx
apps/backend-rag/tests/unit/test_request_tracing_middleware.py
apps/backend-rag/backend/tests/integration/test_partners_e2e.py
apps/backend-rag/backend/migrations/migration_119_partners.py
apps/backend-rag/backend/middleware/pii_scanner.py
apps/backend-rag/backend/middleware/activity_logging.py
apps/backend-rag/backend/middleware/request_tracing.py
apps/backend-rag/backend/middleware/hybrid_auth.py
apps/backend-rag/backend/middleware/rate_limiter.py
apps/backend-rag/backend/middleware/error_monitoring.py
apps/backend-rag/backend/app/setup/router_manifest.py
apps/backend-rag/backend/app/setup/middleware_config.py
apps/backend-rag/backend/services/portal/document_processing.py
apps/backend-rag/backend/tests/services/rag/agentic/test_response_processor.py
apps/backend-rag/tests/unit/middleware/test_hybrid_auth_coverage.py
apps/backend-rag/tests/unit/middleware/__init__.py
apps/backend-rag/backend/services/crm/completed_process_service.py
apps/backend-rag/backend/services/crm/partners/repository.py
apps/backend-rag/backend/services/crm/partners/commission_engine.py
apps/backend-rag/backend/app/utils/subprocess_utils.py
apps/backend-rag/backend/services/crm/partners/templates/commission.md.j2
apps/backend-rag/backend/services/crm/partners/templates/welcome.md.j2
apps/backend-rag/backend/services/crm/partners/__init__.py
apps/backend-rag/backend/services/crm/partners/emails.py
apps/backend-rag/backend/services/crm/partners/events.py
apps/backend-rag/backend/services/crm/partners/models.py
apps/backend-rag/backend/services/crm/partners/service.py
apps/backend-rag/backend/tests/unit/services/rag/agentic/test_response_processor_coverage.py
apps/backend-rag/backend/services/crm/process_automation_service.py
apps/backend-rag/backend/app/routers/portal_process_timeline.py
apps/backend-rag/backend/app/routers/partners.py
apps/backend-rag/backend/tests/unit/middleware/test_error_monitoring.py
apps/backend-rag/backend/tests/unit/middleware/test_rate_limiter.py
apps/backend-rag/backend/tests/unit/middleware/test_pii_scanner.py
apps/backend-rag/backend/tests/unit/middleware/test_activity_logging_email.py
apps/backend-rag/backend/tests/unit/middleware/test_rate_limiter_middleware.py
apps/backend-rag/backend/tests/unit/middleware/test_activity_logging_dispatch.py
apps/backend-rag/backend/tests/unit/middleware/test_request_tracing.py
apps/backend-rag/backend/tests/unit/middleware/__init__.py
apps/backend-rag/backend/tests/unit/middleware/test_hybrid_auth.py
apps/backend-rag/backend/services/rag/agentic/response_processor.py
apps/mouth/src/components/portal/process/ProcessTimeline.tsx
apps/mouth/src/components/portal/process/BlockedStateCTA.tsx
apps/mouth/src/components/portal/process/ProcessErrorBoundary.test.tsx
apps/mouth/src/components/portal/process/TimelineSkeleton.tsx
apps/mouth/src/components/portal/process/stateColors.test.ts
apps/mouth/src/components/portal/process/StepDetailDrawer.test.tsx
apps/mouth/src/components/portal/process/StateBadge.tsx
apps/mouth/src/components/portal/process/TimelineSkeleton.test.tsx
apps/mouth/src/components/portal/process/ProcessTimeline.test.tsx
apps/mouth/src/components/portal/process/StateBadge.test.tsx
apps/mouth/src/components/portal/process/stateColors.ts
apps/mouth/src/components/portal/process/TimelineStep.tsx
apps/mouth/src/components/portal/process/BlockedStateCTA.test.tsx
apps/mouth/src/components/portal/process/TimelineStep.test.tsx
apps/mouth/src/components/portal/process/ProcessErrorBoundary.tsx
apps/mouth/src/components/portal/process/StepDetailDrawer.tsx
apps/backend-rag/backend/tests/unit/routers/test_portal_process_timeline.py
apps/backend-rag/backend/tests/migrations/test_migration_119.py
apps/backend-rag/backend/tests/routers/test_partners.py
apps/graph-engine/src/nuzantara_graph/api/middleware.py
apps/backend-rag/backend/tests/unit/app/setup/test_middleware_config.py
apps/mouth/src/middleware.ts
apps/mouth/public/workers/data-processor.js
apps/mouth/src/app/(workspace)/process/page.tsx
apps/mouth/src/app/(workspace)/process/[id]/RequiredDocumentsCard.tsx
apps/mouth/src/app/(workspace)/process/[id]/page.tsx
apps/mouth/src/app/(workspace)/process/[id]/loading.tsx
apps/mouth/src/app/(workspace)/process/[id]/error.tsx
apps/mouth/src/app/(workspace)/process/loading.tsx
apps/mouth/src/app/(workspace)/process/error.tsx
apps/mouth/src/app/(workspace)/process/new/page.tsx
apps/mouth/src/app/(workspace)/process/new/loading.tsx
apps/mouth/src/app/(workspace)/process/new/error.tsx
apps/mouth/src/app/(workspace)/partners/page.tsx
apps/graph-engine/tests/unit/api/test_middleware.py
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx
apps/mouth/src/app/(workspace)/process/__tests__/page.test.tsx
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx
apps/mouth/src/app/(workspace)/partners/finance/page.tsx
apps/mouth/src/app/(workspace)/partners/new/page.tsx
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx
apps/mouth/public/static/news/immigration-provides-free-passport-processing-for-sumatra-flood-victims-news-entempoco.jpg
apps/mouth/public/static/news/understanding-the-new-usindonesia-trade-agreement-and-what-it-means-for-businesses-assegaf-hamzah-partners.jpg
apps/mouth/src/app/portal/(authenticated)/process/page.tsx
apps/mouth/src/app/portal/(authenticated)/process/loading.tsx
apps/mouth/src/app/portal/(authenticated)/process/error.tsx
apps/mouth/src/app/portal/(authenticated)/process/[practiceId]/page.tsx
apps/mouth/src/content/articles/tax-legal/understanding-the-new-usindonesia-trade-agreement-and-what-it-means-for-businesses-assegaf-hamzah-partners.it.mdx
apps/mouth/src/content/articles/tax-legal/understanding-the-new-usindonesia-trade-agreement-and-what-it-means-for-businesses-assegaf-hamzah-partners.id.mdx
apps/mouth/src/content/articles/tax-legal/understanding-the-new-usindonesia-trade-agreement-and-what-it-means-for-businesses-assegaf-hamzah-partners.mdx
apps/mouth/src/content/articles/tax-legal/understanding-the-new-usindonesia-trade-agreement-and-what-it-means-for-businesses-assegaf-hamzah-partners.fr.mdx
apps/mouth/src/content/articles/tax-legal/understanding-the-new-usindonesia-trade-agreement-and-what-it-means-for-businesses-assegaf-hamzah-partners.ru.mdx
apps/mouth/src/content/articles/immigration/immigration-provides-free-passport-processing-for-sumatra-flood-victims-news-entempoco.fr.mdx
apps/mouth/src/content/articles/immigration/immigration-provides-free-passport-processing-for-sumatra-flood-victims-news-entempoco.ru.mdx
apps/mouth/src/content/articles/immigration/immigration-provides-free-passport-processing-for-sumatra-flood-victims-news-entempoco.id.mdx
apps/mouth/src/content/articles/immigration/immigration-provides-free-passport-processing-for-sumatra-flood-victims-news-entempoco.it.mdx
apps/mouth/src/content/articles/immigration/immigration-provides-free-passport-processing-for-sumatra-flood-victims-news-entempoco.mdx

exec
/bin/zsh -lc 'git status --short --branch' in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 1776ms:
2026-04-21 10:45:11.275 xcodebuild[15757:3217342]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-04-21 10:45:11.490 xcodebuild[15757:3217341] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: error: couldn't create cache file '/tmp/xcrun_db-lzJyRMmi' (errno=Operation not permitted)
2026-04-21 10:45:11.892 xcodebuild[15762:3217357]  DVTFilePathFSEvents: Failed to start fs event stream.
2026-04-21 10:45:12.034 xcodebuild[15762:3217356] [MT] DVTDeveloperPaths: Failed to get length of DARWIN_USER_CACHE_DIR from confstr(3), error = Error Domain=NSPOSIXErrorDomain Code=5 "Input/output error". Using NSCachesDirectory instead.
## feat/crm-partners-module...origin/feat/crm-partners-module
?? docs/superpowers/reviews/

exec
/bin/zsh -lc "nl -ba apps/backend-rag/backend/services/crm/partners/repository.py | sed -n '1,360p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
     1	# backend/services/crm/partners/repository.py
     2	from __future__ import annotations
     3	
     4	import json
     5	import logging
     6	from decimal import Decimal
     7	from typing import Any
     8	from uuid import UUID
     9	
    10	import asyncpg
    11	
    12	from backend.services.crm.partners.models import (
    13	    Partner, PartnerReferral, PartnerCommission, PartnerAuditLogEntry,
    14	    EntityType, CommissionType, CommissionStatus, CommissionEntryType,
    15	    WithholdingCategory, RuleSource,
    16	)
    17	
    18	logger = logging.getLogger(__name__)
    19	
    20	# Commission state machine.
    21	# Source of truth: docs/superpowers/specs/2026-04-20-crm-partners-module.md §3.3 + §4.4.
    22	# v1 terminal states: paid, offset_applied, waived, repaid.
    23	_ALLOWED_TRANSITIONS: dict[CommissionStatus, set[CommissionStatus]] = {
    24	    "accrued": {"approved"},
    25	    "approved": {"paid"},
    26	    "paid": set(),
    27	    "clawback_pending": {"offset_applied", "waived", "repaid"},
    28	    "offset_applied": set(),
    29	    "waived": set(),
    30	    "repaid": set(),
    31	}
    32	
    33	_PARTNER_UPDATABLE_COLS = {
    34	    "full_name", "work_role", "company_name", "office_address",
    35	    "email", "phone", "preferred_language",
    36	    "entity_type", "npwp", "nik", "tax_withholding_category", "fiscal_address",
    37	    "bank_name", "bank_account_holder", "bank_account_number",
    38	    "ewallet_type", "ewallet_number", "payment_currency", "iban", "payment_notes",
    39	    "default_commission_type", "default_commission_value",
    40	    "pdp_consent_at", "pdp_consent_version", "terms_accepted_at", "terms_version",
    41	}
    42	# NB: onboarding_status, assigned_to, welcome_email_sent_at are ONLY settable
    43	# via their dedicated methods (activate_partner, reassign_partner, mark_welcome_sent).
    44	
    45	
    46	class PartnersRepository:
    47	    """SQL layer. No business logic, no audit writes, no event emission."""
    48	
    49	    def __init__(self, conn: asyncpg.Connection):
    50	        self.conn = conn
    51	
    52	    # ── Partner CRUD ────────────────────────────────────────────────────
    53	
    54	    async def insert_partner(
    55	        self,
    56	        *,
    57	        full_name: str,
    58	        email: str,
    59	        entity_type: EntityType,
    60	        assigned_to: UUID | None = None,
    61	        created_by: UUID | None = None,
    62	        **optional: Any,
    63	    ) -> UUID:
    64	        await self._assert_email_is_not_internal(email)
    65	        cols = ["full_name", "email", "entity_type", "assigned_to", "created_by"]
    66	        vals: list[Any] = [full_name, email, entity_type, assigned_to, created_by]
    67	        for k, v in optional.items():
    68	            if k not in _PARTNER_UPDATABLE_COLS:
    69	                raise ValueError(f"Field {k!r} is not insertable via insert_partner")
    70	            cols.append(k); vals.append(v)
    71	        placeholders = ", ".join(f"${i+1}" for i in range(len(vals)))
    72	        sql = f"INSERT INTO partners ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id"
    73	        row = await self.conn.fetchrow(sql, *vals)
    74	        logger.debug("insert_partner id=%s email=%s", row["id"], email)
    75	        return row["id"]
    76	
    77	    async def _assert_email_is_not_internal(self, email: str) -> None:
    78	        """Reject partner emails that match an internal team/admin user.
    79	
    80	        KNOWN RACE: This is a SELECT-then-INSERT pattern without a cross-table
    81	        DB constraint. A concurrent INSERT into users with role in (team,admin)
    82	        between this check and the partners INSERT would slip through. v2
    83	        should add a SERIALIZABLE transaction wrapper or a cross-table unique
    84	        trigger. For v1 the race window is narrow and acceptable (rare admin
    85	        operation concurrent with partner onboarding).
    86	        """
    87	        row = await self.conn.fetchrow(
    88	            "SELECT 1 FROM users WHERE email = $1 AND role IN ('team','admin')",
    89	            email,
    90	        )
    91	        if row is not None:
    92	            raise ValueError(f"email is already a team/admin user: {email!r}")
    93	
    94	    async def get_partner(self, partner_id: UUID) -> Partner | None:
    95	        row = await self.conn.fetchrow("SELECT * FROM partners WHERE id = $1", partner_id)
    96	        return self._row_to_partner(row) if row else None
    97	
    98	    async def list_partners(
    99	        self,
   100	        *,
   101	        assigned_to: UUID | None = None,
   102	        onboarding_status: str | None = None,
   103	        orphaned: bool = False,
   104	        search: str | None = None,
   105	        limit: int = 200,
   106	    ) -> list[Partner]:
   107	        where, args = ["TRUE"], []
   108	        if assigned_to is not None:
   109	            args.append(assigned_to); where.append(f"assigned_to = ${len(args)}")
   110	        if onboarding_status is not None:
   111	            args.append(onboarding_status); where.append(f"onboarding_status = ${len(args)}")
   112	        if orphaned:
   113	            where.append("assigned_to IS NULL")
   114	        if search:
   115	            args.append(f"%{search}%")
   116	            where.append(f"(full_name ILIKE ${len(args)} OR email ILIKE ${len(args)} OR company_name ILIKE ${len(args)})")
   117	        args.append(limit)
   118	        sql = f"SELECT * FROM partners WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT ${len(args)}"
   119	        rows = await self.conn.fetch(sql, *args)
   120	        return [self._row_to_partner(r) for r in rows]
   121	
   122	    async def update_partner(self, partner_id: UUID, **fields: Any) -> None:
   123	        if not fields:
   124	            raise ValueError("update_partner requires at least one field")
   125	        bad = set(fields) - _PARTNER_UPDATABLE_COLS
   126	        if bad:
   127	            raise ValueError(f"Non-updatable fields: {bad}")
   128	        if "email" in fields:
   129	            await self._assert_email_is_not_internal(fields["email"])
   130	        sets = [f"{k} = ${i+2}" for i, k in enumerate(fields)]
   131	        sets.append(f"updated_at = now()")
   132	        sql = f"UPDATE partners SET {', '.join(sets)} WHERE id = $1"
   133	        await self.conn.execute(sql, partner_id, *fields.values())
   134	
   135	    async def activate_partner(self, partner_id: UUID) -> None:
   136	        await self.conn.execute(
   137	            "UPDATE partners SET onboarding_status = 'active', updated_at = now() "
   138	            "WHERE id = $1 AND onboarding_status = 'pending_approval'",
   139	            partner_id,
   140	        )
   141	
   142	    async def deactivate_partner(self, partner_id: UUID) -> None:
   143	        await self.conn.execute(
   144	            "UPDATE partners SET onboarding_status = 'inactive', deactivated_at = now(), "
   145	            "updated_at = now() WHERE id = $1",
   146	            partner_id,
   147	        )
   148	
   149	    async def reassign_partner(self, partner_id: UUID, new_user_id: UUID | None) -> None:
   150	        await self.conn.execute(
   151	            "UPDATE partners SET assigned_to = $2, updated_at = now() WHERE id = $1",
   152	            partner_id, new_user_id,
   153	        )
   154	
   155	    async def orphan_partners_of_user(self, user_id: UUID) -> int:
   156	        result = await self.conn.execute(
   157	            "UPDATE partners SET assigned_to = NULL, updated_at = now() WHERE assigned_to = $1",
   158	            user_id,
   159	        )
   160	        # asyncpg returns "UPDATE <n>"
   161	        return int(result.split()[-1])
   162	
   163	    async def mark_welcome_sent(self, partner_id: UUID) -> None:
   164	        await self.conn.execute(
   165	            "UPDATE partners SET welcome_email_sent_at = now() "
   166	            "WHERE id = $1 AND welcome_email_sent_at IS NULL",
   167	            partner_id,
   168	        )
   169	
   170	    # ── Referrals ───────────────────────────────────────────────────────
   171	
   172	    async def insert_referral(
   173	        self, *, partner_id: UUID, process_id: UUID,
   174	        referred_by_user_id: UUID | None = None,
   175	        share_percent: Decimal = Decimal("100.00"),
   176	        notes: str | None = None,
   177	    ) -> UUID:
   178	        row = await self.conn.fetchrow(
   179	            """
   180	            INSERT INTO partner_referrals
   181	                (partner_id, process_id, share_percent, referred_by_user_id, notes)
   182	            VALUES ($1, $2, $3, $4, $5)
   183	            RETURNING id
   184	            """,
   185	            partner_id, process_id, share_percent, referred_by_user_id, notes,
   186	        )
   187	        return row["id"]
   188	
   189	    async def get_referral_by_process(self, process_id: UUID) -> PartnerReferral | None:
   190	        row = await self.conn.fetchrow(
   191	            "SELECT * FROM partner_referrals WHERE process_id = $1", process_id
   192	        )
   193	        return self._row_to_referral(row) if row else None
   194	
   195	    async def list_referrals_for_partner(self, partner_id: UUID) -> list[PartnerReferral]:
   196	        rows = await self.conn.fetch(
   197	            "SELECT * FROM partner_referrals WHERE partner_id = $1 ORDER BY referred_at DESC",
   198	            partner_id,
   199	        )
   200	        return [self._row_to_referral(r) for r in rows]
   201	
   202	    async def update_referral_partner(self, referral_id: UUID, new_partner_id: UUID) -> None:
   203	        await self.conn.execute(
   204	            "UPDATE partner_referrals SET partner_id = $2 WHERE id = $1",
   205	            referral_id, new_partner_id,
   206	        )
   207	
   208	    async def delete_referral(self, referral_id: UUID) -> None:
   209	        # Referrals are deletable ONLY before any commission is accrued against them.
   210	        row = await self.conn.fetchrow(
   211	            "SELECT 1 FROM partner_commissions WHERE referral_id = $1 LIMIT 1",
   212	            referral_id,
   213	        )
   214	        if row is not None:
   215	            raise RuntimeError("Cannot delete referral with commissions recorded")
   216	        try:
   217	            await self.conn.execute("DELETE FROM partner_referrals WHERE id = $1", referral_id)
   218	        except asyncpg.ForeignKeyViolationError as e:
   219	            # Race: commission inserted between our SELECT and DELETE.
   220	            raise RuntimeError("Cannot delete referral with commissions recorded") from e
   221	
   222	    # ── Commissions (append-only) ───────────────────────────────────────
   223	
   224	    async def insert_commission(
   225	        self,
   226	        *,
   227	        partner_id: UUID,
   228	        entry_type: CommissionEntryType,
   229	        base_amount_idr: Decimal,
   230	        commission_type_snapshot: CommissionType,
   231	        commission_value_snapshot: Decimal,
   232	        gross_amount_idr: Decimal,
   233	        net_amount_idr: Decimal,
   234	        idempotency_key: str,
   235	        referral_id: UUID | None = None,
   236	        process_id: UUID | None = None,
   237	        related_commission_id: UUID | None = None,
   238	        rule_source: RuleSource = "partner_default",
   239	        assigned_to_snapshot: UUID | None = None,
   240	        withholding_category: WithholdingCategory = "tbd",
   241	        withholding_rate: Decimal = Decimal("0.0"),
   242	        withholding_amount_idr: Decimal = Decimal("0.0"),
   243	        status: CommissionStatus = "accrued",
   244	        eligible_for_approval_at: Any = None,
   245	        manual_override_reason: str | None = None,
   246	        clawback_reason: str | None = None,
   247	    ) -> UUID:
   248	        row = await self.conn.fetchrow(
   249	            """
   250	            INSERT INTO partner_commissions (
   251	                partner_id, entry_type, referral_id, process_id, related_commission_id,
   252	                base_amount_idr, commission_type_snapshot, commission_value_snapshot,
   253	                rule_source, assigned_to_snapshot,
   254	                gross_amount_idr, withholding_category, withholding_rate,
   255	                withholding_amount_idr, net_amount_idr,
   256	                status, eligible_for_approval_at,
   257	                manual_override_reason, clawback_reason, idempotency_key
   258	            )
   259	            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,
   260	                    COALESCE($17, now()),$18,$19,$20)
   261	            RETURNING id
   262	            """,
   263	            partner_id, entry_type, referral_id, process_id, related_commission_id,
   264	            base_amount_idr, commission_type_snapshot, commission_value_snapshot,
   265	            rule_source, assigned_to_snapshot,
   266	            gross_amount_idr, withholding_category, withholding_rate,
   267	            withholding_amount_idr, net_amount_idr,
   268	            status, eligible_for_approval_at,
   269	            manual_override_reason, clawback_reason, idempotency_key,
   270	        )
   271	        logger.debug(
   272	            "insert_commission id=%s partner=%s type=%s status=%s",
   273	            row["id"], partner_id, entry_type, status,
   274	        )
   275	        return row["id"]
   276	
   277	    async def get_commission(self, commission_id: UUID) -> PartnerCommission | None:
   278	        row = await self.conn.fetchrow(
   279	            "SELECT * FROM partner_commissions WHERE id = $1", commission_id
   280	        )
   281	        return self._row_to_commission(row) if row else None
   282	
   283	    async def list_commissions_for_partner(
   284	        self, partner_id: UUID, *, status: CommissionStatus | None = None,
   285	    ) -> list[PartnerCommission]:
   286	        args: list[Any] = [partner_id]
   287	        where = "partner_id = $1"
   288	        if status is not None:
   289	            args.append(status); where += f" AND status = ${len(args)}"
   290	        sql = f"SELECT * FROM partner_commissions WHERE {where} ORDER BY created_at DESC"
   291	        rows = await self.conn.fetch(sql, *args)
   292	        return [self._row_to_commission(r) for r in rows]
   293	
   294	    async def list_pending_clawbacks(self, partner_id: UUID) -> list[PartnerCommission]:
   295	        rows = await self.conn.fetch(
   296	            "SELECT * FROM partner_commissions WHERE partner_id = $1 AND status = 'clawback_pending' "
   297	            "ORDER BY accrued_at ASC",
   298	            partner_id,
   299	        )
   300	        return [self._row_to_commission(r) for r in rows]
   301	
   302	    async def update_commission_status(
   303	        self,
   304	        commission_id: UUID,
   305	        new_status: CommissionStatus,
   306	        *,
   307	        approved_by: UUID | None = None,
   308	        paid_by: UUID | None = None,
   309	        paid_via: str | None = None,
   310	        payment_reference: str | None = None,
   311	        payment_proof_url: str | None = None,
   312	        receipt_type: str | None = None,
   313	        receipt_file_url: str | None = None,
   314	        waiver_reason: str | None = None,
   315	    ) -> None:
   316	        current = await self.get_commission(commission_id)
   317	        if current is None:
   318	            raise ValueError(f"Commission {commission_id} not found")
   319	        if new_status not in _ALLOWED_TRANSITIONS.get(current.status, set()):
   320	            raise ValueError(
   321	                f"Disallowed transition: {current.status!r} -> {new_status!r}"
   322	            )
   323	        logger.debug(
   324	            "update_commission_status id=%s %s->%s", commission_id, current.status, new_status
   325	        )
   326	        fragments, args = ["status = $2"], [commission_id, new_status]
   327	        if new_status == "approved":
   328	            fragments += ["approved_at = now()", f"approved_by = ${len(args)+1}"]; args.append(approved_by)
   329	        if new_status == "paid":
   330	            fragments += [
   331	                "paid_at = now()",
   332	                f"paid_by = ${len(args)+1}", f"paid_via = ${len(args)+2}",
   333	                f"payment_reference = ${len(args)+3}", f"payment_proof_url = ${len(args)+4}",
   334	                f"receipt_type = ${len(args)+5}", f"receipt_file_url = ${len(args)+6}",
   335	            ]
   336	            args += [paid_by, paid_via, payment_reference, payment_proof_url,
   337	                     receipt_type, receipt_file_url]
   338	        if new_status == "waived":
   339	            fragments += [f"waiver_reason = ${len(args)+1}"]; args.append(waiver_reason)
   340	        sql = f"UPDATE partner_commissions SET {', '.join(fragments)} WHERE id = $1"
   341	        await self.conn.execute(sql, *args)
   342	
   343	    async def mark_commission_email_sent(self, commission_id: UUID) -> None:
   344	        await self.conn.execute(
   345	            "UPDATE partner_commissions SET commission_email_sent_at = now() "
   346	            "WHERE id = $1 AND commission_email_sent_at IS NULL",
   347	            commission_id,
   348	        )
   349	
   350	    async def delete_commission(self, commission_id: UUID) -> None:
   351	        raise RuntimeError("partner_commissions is append-only; delete is forbidden")
   352	
   353	    # ── Audit log ───────────────────────────────────────────────────────
   354	
   355	    async def insert_audit(
   356	        self,
   357	        *,
   358	        partner_id: UUID,
   359	        action: str,
   360	        actor_user_id: UUID | None = None,

exec
/bin/zsh -lc "nl -ba apps/backend-rag/backend/app/routers/partners.py | sed -n '260,560p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
   260	async def me_referrals(
   261	    user: dict[str, Any] = Depends(get_current_user),
   262	    pool: asyncpg.Pool = Depends(get_database_pool),
   263	) -> Any:
   264	    """List referrals for the calling partner user. Client data is sterilized."""
   265	    if user.get("role") != "partner":
   266	        raise HTTPException(status_code=403, detail="partner role required")
   267	    async with pool.acquire() as conn:
   268	        row = await conn.fetchrow(
   269	            "SELECT partner_id FROM users WHERE id = $1",
   270	            UUID(str(user["user_id"])),
   271	        )
   272	        if not row or not row["partner_id"]:
   273	            raise HTTPException(status_code=403, detail="no partner profile linked to this user")
   274	        partner_id = row["partner_id"]
   275	        rows = await conn.fetch(
   276	            """
   277	            SELECT pr.id, pr.process_id, pr.referred_at,
   278	                   p.status AS process_status, p.service_type,
   279	                   c.full_name AS client_name
   280	            FROM partner_referrals pr
   281	            LEFT JOIN processes p ON p.id = pr.process_id
   282	            LEFT JOIN clients c ON c.id = p.client_id
   283	            WHERE pr.partner_id = $1
   284	            ORDER BY pr.referred_at DESC
   285	            """,
   286	            partner_id,
   287	        )
   288	    return [
   289	        {
   290	            "id": str(r["id"]),
   291	            "process_id": str(r["process_id"]),
   292	            "service_type": r["service_type"],
   293	            "process_status": r["process_status"],
   294	            "client_display": _sterilize_client_for_partner(r["client_name"] or ""),
   295	            "referred_at": r["referred_at"].isoformat() if r["referred_at"] else None,
   296	        }
   297	        for r in rows
   298	    ]
   299	
   300	
   301	@router.get("/me/commissions")
   302	async def me_commissions(
   303	    user: dict[str, Any] = Depends(get_current_user),
   304	    pool: asyncpg.Pool = Depends(get_database_pool),
   305	) -> Any:
   306	    """List commissions for the calling partner user."""
   307	    if user.get("role") != "partner":
   308	        raise HTTPException(status_code=403, detail="partner role required")
   309	    async with pool.acquire() as conn:
   310	        row = await conn.fetchrow(
   311	            "SELECT partner_id FROM users WHERE id = $1",
   312	            UUID(str(user["user_id"])),
   313	        )
   314	        if not row or not row["partner_id"]:
   315	            raise HTTPException(status_code=403, detail="no partner profile linked to this user")
   316	        svc = PartnersService(conn)
   317	        commissions = await svc.repo.list_commissions_for_partner(row["partner_id"])
   318	        return [
   319	            dataclasses.asdict(c) if dataclasses.is_dataclass(c) else dict(c)
   320	            for c in commissions
   321	        ]
   322	
   323	
   324	@router.get("/finance/export")
   325	async def finance_export(
   326	    from_: str = Query(..., alias="from"),
   327	    to: str = Query(...),
   328	    user: dict[str, Any] = Depends(get_current_user),
   329	    pool: asyncpg.Pool = Depends(get_database_pool),
   330	) -> Response:
   331	    """Finance CSV export. Admin + finance permission required."""
   332	    _require_admin(user)
   333	    _require_finance(user)
   334	    # Validate ISO format before hitting SQL — bad input → 400 not 500
   335	    try:
   336	        datetime.fromisoformat(from_)
   337	        datetime.fromisoformat(to)
   338	    except ValueError as e:
   339	        raise HTTPException(status_code=400, detail=f"invalid date format (expected ISO): {e}")
   340	    try:
   341	        async with pool.acquire() as conn:
   342	            rows = await conn.fetch(
   343	                """
   344	                SELECT pc.id, p.full_name, p.npwp, p.entity_type,
   345	                       pc.entry_type, pc.gross_amount_idr, pc.withholding_category,
   346	                       pc.withholding_amount_idr, pc.net_amount_idr, pc.status,
   347	                       pc.paid_at, pc.paid_via, pc.payment_reference
   348	                FROM partner_commissions pc
   349	                JOIN partners p ON p.id = pc.partner_id
   350	                WHERE pc.created_at >= $1::timestamptz
   351	                  AND pc.created_at <  $2::timestamptz
   352	                ORDER BY pc.created_at ASC
   353	                """,
   354	                from_, to,
   355	            )
   356	        buf = io.StringIO()
   357	        writer = csv.writer(buf)
   358	        writer.writerow([
   359	            "commission_id", "partner", "npwp", "entity_type", "entry_type",
   360	            "gross_idr", "withholding_category", "withholding_idr", "net_idr",
   361	            "status", "paid_at", "paid_via", "payment_reference",
   362	        ])
   363	        for r in rows:
   364	            writer.writerow([r[k] for k in r.keys()])
   365	        return Response(
   366	            content=buf.getvalue(),
   367	            media_type="text/csv",
   368	            headers={
   369	                "Content-Disposition": f'attachment; filename="partners-{from_}-to-{to}.csv"'
   370	            },
   371	        )
   372	    except HTTPException:
   373	        raise
   374	    except Exception:
   375	        logger.exception("finance_export failed")
   376	        raise HTTPException(status_code=500, detail="internal error")
   377	
   378	
   379	@router.get("/{partner_id}")
   380	async def get_partner(
   381	    partner_id: UUID,
   382	    user: dict[str, Any] = Depends(get_current_user),
   383	    pool: asyncpg.Pool = Depends(get_database_pool),
   384	) -> Any:
   385	    """Get a partner by ID. Scoped by role."""
   386	    async with pool.acquire() as conn:
   387	        svc = PartnersService(conn)
   388	        partner = await verify_partner_access_with_role(
   389	            svc,
   390	            UUID(str(user["user_id"])),
   391	            user.get("role"),
   392	            partner_id,
   393	        )
   394	        return _partner_to_dict(partner)
   395	
   396	
   397	@router.patch("/{partner_id}")
   398	async def update_partner(
   399	    partner_id: UUID,
   400	    body: PartnerUpdate,
   401	    user: dict[str, Any] = Depends(get_current_user),
   402	    pool: asyncpg.Pool = Depends(get_database_pool),
   403	) -> Any:
   404	    """Update a partner. Team members can only update their own assigned partners."""
   405	    try:
   406	        async with pool.acquire() as conn:
   407	            svc = PartnersService(conn)
   408	            fields = body.model_dump(exclude_none=True, exclude_unset=True)
   409	            await svc.update_partner(
   410	                partner_id,
   411	                actor_user=UUID(str(user["user_id"])),
   412	                actor_role=user.get("role", "team"),
   413	                **fields,
   414	            )
   415	            partner = await svc.repo.get_partner(partner_id)
   416	            return _partner_to_dict(partner)
   417	    except HTTPException:
   418	        raise
   419	    except Exception:
   420	        logger.exception("update_partner failed")
   421	        raise HTTPException(status_code=500, detail="internal error")
   422	
   423	
   424	@router.post("/{partner_id}/activate", status_code=status.HTTP_204_NO_CONTENT)
   425	async def activate_partner(
   426	    partner_id: UUID,
   427	    user: dict[str, Any] = Depends(get_current_user),
   428	    pool: asyncpg.Pool = Depends(get_database_pool),
   429	) -> Response:
   430	    """Activate a partner. Admin only."""
   431	    _require_admin(user)
   432	    try:
   433	        async with pool.acquire() as conn:
   434	            svc = PartnersService(conn)
   435	            await svc.activate_partner(partner_id, actor_user=UUID(str(user["user_id"])))
   436	            # Trigger welcome email if emails module is available (Task 8)
   437	            try:
   438	                from backend.services.crm.partners.emails import send_welcome
   439	                await send_welcome(conn, partner_id)
   440	            except ImportError:
   441	                pass  # emails module not yet implemented (Task 8)
   442	            return Response(status_code=204)
   443	    except HTTPException:
   444	        raise
   445	    except Exception:
   446	        logger.exception("activate_partner failed")
   447	        raise HTTPException(status_code=500, detail="internal error")
   448	
   449	
   450	@router.post("/{partner_id}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
   451	async def deactivate_partner(
   452	    partner_id: UUID,
   453	    user: dict[str, Any] = Depends(get_current_user),
   454	    pool: asyncpg.Pool = Depends(get_database_pool),
   455	) -> Response:
   456	    """Deactivate a partner. Admin only."""
   457	    _require_admin(user)
   458	    try:
   459	        async with pool.acquire() as conn:
   460	            svc = PartnersService(conn)
   461	            await svc.deactivate_partner(partner_id, actor_user=UUID(str(user["user_id"])))
   462	            return Response(status_code=204)
   463	    except HTTPException:
   464	        raise
   465	    except Exception:
   466	        logger.exception("deactivate_partner failed")
   467	        raise HTTPException(status_code=500, detail="internal error")
   468	
   469	
   470	@router.post("/{partner_id}/reassign", status_code=status.HTTP_204_NO_CONTENT)
   471	async def reassign_partner(
   472	    partner_id: UUID,
   473	    body: ReassignRequest,
   474	    user: dict[str, Any] = Depends(get_current_user),
   475	    pool: asyncpg.Pool = Depends(get_database_pool),
   476	) -> Response:
   477	    """Reassign a partner to a different team member. Admin only."""
   478	    _require_admin(user)
   479	    try:
   480	        async with pool.acquire() as conn:
   481	            svc = PartnersService(conn)
   482	            await svc.reassign_partner(
   483	                partner_id,
   484	                new_user_id=body.new_user_id,
   485	                actor_user=UUID(str(user["user_id"])),
   486	                reason=body.reason,
   487	            )
   488	            return Response(status_code=204)
   489	    except HTTPException:
   490	        raise
   491	    except ValueError as e:
   492	        raise HTTPException(status_code=400, detail=str(e))
   493	    except Exception:
   494	        logger.exception("reassign_partner failed")
   495	        raise HTTPException(status_code=500, detail="internal error")
   496	
   497	
   498	@router.post("/bulk-reassign", status_code=status.HTTP_204_NO_CONTENT)
   499	async def bulk_reassign(
   500	    body: BulkReassignRequest,
   501	    user: dict[str, Any] = Depends(get_current_user),
   502	    pool: asyncpg.Pool = Depends(get_database_pool),
   503	) -> Response:
   504	    """Bulk-reassign multiple partners to a single user. Admin only."""
   505	    _require_admin(user)
   506	    try:
   507	        async with pool.acquire() as conn:
   508	            svc = PartnersService(conn)
   509	            for pid in body.partner_ids:
   510	                await svc.reassign_partner(
   511	                    pid,
   512	                    new_user_id=body.new_user_id,
   513	                    actor_user=UUID(str(user["user_id"])),
   514	                    reason=body.reason,
   515	                )
   516	            return Response(status_code=204)
   517	    except HTTPException:
   518	        raise
   519	    except ValueError as e:
   520	        raise HTTPException(status_code=400, detail=str(e))
   521	    except Exception:
   522	        logger.exception("bulk_reassign failed")
   523	        raise HTTPException(status_code=500, detail="internal error")
   524	
   525	
   526	# ── Referrals ────────────────────────────────────────────────────────────────
   527	
   528	@router.get("/{partner_id}/referrals")
   529	async def list_referrals(
   530	    partner_id: UUID,
   531	    user: dict[str, Any] = Depends(get_current_user),
   532	    pool: asyncpg.Pool = Depends(get_database_pool),
   533	) -> Any:
   534	    """List referrals for a partner. Scoped by role."""
   535	    async with pool.acquire() as conn:
   536	        svc = PartnersService(conn)
   537	        await verify_partner_access_with_role(
   538	            svc, UUID(str(user["user_id"])), user.get("role"), partner_id
   539	        )
   540	        refs = await svc.repo.list_referrals_for_partner(partner_id)
   541	        return [
   542	            dataclasses.asdict(r) if dataclasses.is_dataclass(r) else dict(r)
   543	            for r in refs
   544	        ]
   545	
   546	
   547	@router.post("/{partner_id}/referrals", status_code=status.HTTP_201_CREATED)
   548	async def create_referral(
   549	    partner_id: UUID,
   550	    body: ReferralCreate,
   551	    user: dict[str, Any] = Depends(get_current_user),
   552	    pool: asyncpg.Pool = Depends(get_database_pool),
   553	) -> Any:
   554	    """Record a referral for a partner. Team (owner) or admin."""
   555	    try:
   556	        async with pool.acquire() as conn:
   557	            svc = PartnersService(conn)
   558	            await verify_partner_access_with_role(
   559	                svc, UUID(str(user["user_id"])), user.get("role"), partner_id
   560	            )

exec
/bin/zsh -lc "nl -ba apps/backend-rag/backend/services/crm/partners/emails.py | sed -n '1,280p'" in /Users/nuzantara/Desktop/partners-spec-wt
exec
/bin/zsh -lc "nl -ba apps/backend-rag/backend/migrations/migration_119_partners.py | sed -n '1,260p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
     1	"""Migration 119: Partners module — 4 tables + 2 system settings.
     2	
     3	Why
     4	---
     5	Formalizes Bali Zero's informal third-party referral network (hotels, property
     6	managers, consultants, agents) into a first-class CRM module with full
     7	Indonesian fiscal profile, an append-only commission ledger, and GDPR/UU PDP
     8	consent tracking.
     9	
    10	Schema
    11	------
    12	- partners: anagrafica + fiscal profile + payment rail + commission defaults
    13	- partner_referrals: links partners to existing processes (v1: 1-to-1)
    14	- partner_commissions: append-only ledger (accrued → approved → paid, with clawback)
    15	- partner_audit_log: immutable event trail for every partner/commission state change
    16	- users.partner_id: reverse FK so partner-role users can resolve their own record
    17	
    18	System settings
    19	---------------
    20	- partner_clawback_auto_writeoff_idr: auto-waive threshold (default 0 = disabled)
    21	- partner_accrual_cooling_off_days: days before accrual becomes eligible (default 30)
    22	
    23	Idempotent: safe to re-run.
    24	
    25	Spec: docs/superpowers/specs/2026-04-20-crm-partners-module.md §3
    26	Plan: docs/superpowers/plans/2026-04-20-crm-partners-module.md Task 1
    27	Author: Claude Opus 4.7
    28	Date: 2026-04-20
    29	"""
    30	from __future__ import annotations
    31	
    32	import logging
    33	from typing import Any
    34	
    35	logger = logging.getLogger(__name__)
    36	
    37	
    38	async def apply(conn: Any) -> None:
    39	    # -------------------------------------------------------------------------
    40	    # 1. partners
    41	    # -------------------------------------------------------------------------
    42	    await conn.execute("""
    43	        DO $$
    44	        BEGIN
    45	            IF NOT EXISTS (
    46	                SELECT 1 FROM pg_tables
    47	                WHERE schemaname = 'public' AND tablename = 'partners'
    48	            ) THEN
    49	                CREATE TABLE partners (
    50	                    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    51	
    52	                    -- anagrafica
    53	                    full_name                 TEXT NOT NULL,
    54	                    work_role                 TEXT,
    55	                    company_name              TEXT,
    56	                    office_address            TEXT,
    57	                    email                     TEXT NOT NULL UNIQUE,
    58	                    phone                     TEXT,
    59	                    preferred_language        TEXT DEFAULT 'id',
    60	
    61	                    -- fiscal (Indonesia)
    62	                    entity_type               TEXT NOT NULL
    63	                        CHECK (entity_type IN ('individual','corporate_pt','corporate_cv','foreign')),
    64	                    npwp                      TEXT,
    65	                    nik                       TEXT,
    66	                    tax_withholding_category  TEXT NOT NULL DEFAULT 'tbd'
    67	                        CHECK (tax_withholding_category IN ('pph21','pph23','exempt','tbd')),
    68	                    fiscal_address            TEXT,
    69	
    70	                    -- payment rail
    71	                    bank_name                 TEXT,
    72	                    bank_account_holder       TEXT,
    73	                    bank_account_number       TEXT,
    74	                    ewallet_type              TEXT,
    75	                    ewallet_number            TEXT,
    76	                    payment_currency          TEXT NOT NULL DEFAULT 'IDR',
    77	                    iban                      TEXT,
    78	                    payment_notes             TEXT,
    79	
    80	                    -- commission policy (v1 uses partner-level defaults)
    81	                    default_commission_type   TEXT NOT NULL DEFAULT 'percentage'
    82	                        CHECK (default_commission_type IN ('percentage','flat')),
    83	                    default_commission_value  NUMERIC(14,4) NOT NULL DEFAULT 10.0,
    84	
    85	                    -- lifecycle
    86	                    onboarding_status         TEXT NOT NULL DEFAULT 'pending_approval'
    87	                        CHECK (onboarding_status IN ('pending_approval','active','inactive')),
    88	                    assigned_to               UUID REFERENCES users(id) ON DELETE SET NULL,
    89	
    90	                    -- UU PDP + T&C
    91	                    pdp_consent_at            TIMESTAMPTZ,
    92	                    pdp_consent_version       TEXT,
    93	                    terms_accepted_at         TIMESTAMPTZ,
    94	                    terms_version             TEXT,
    95	
    96	                    -- audit + idempotency
    97	                    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    98	                    created_by                UUID REFERENCES users(id) ON DELETE SET NULL,
    99	                    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
   100	                    deactivated_at            TIMESTAMPTZ,
   101	                    welcome_email_sent_at     TIMESTAMPTZ
   102	                );
   103	            END IF;
   104	        END $$;
   105	    """)
   106	
   107	    await conn.execute(
   108	        "CREATE UNIQUE INDEX IF NOT EXISTS idx_partners_email"
   109	        " ON partners (email);"
   110	    )
   111	    await conn.execute(
   112	        "CREATE INDEX IF NOT EXISTS idx_partners_assigned_to"
   113	        " ON partners (assigned_to)"
   114	        " WHERE assigned_to IS NOT NULL;"
   115	    )
   116	    await conn.execute(
   117	        "CREATE INDEX IF NOT EXISTS idx_partners_onboarding_status"
   118	        " ON partners (onboarding_status);"
   119	    )
   120	    await conn.execute(
   121	        "CREATE INDEX IF NOT EXISTS idx_partners_entity_type"
   122	        " ON partners (entity_type);"
   123	    )
   124	
   125	    # -------------------------------------------------------------------------
   126	    # 2. users.partner_id — reverse FK so partner-role users resolve their record
   127	    # -------------------------------------------------------------------------
   128	    await conn.execute("""
   129	        DO $$
   130	        BEGIN
   131	            IF NOT EXISTS (
   132	                SELECT 1 FROM information_schema.columns
   133	                WHERE table_name = 'users' AND column_name = 'partner_id'
   134	            ) THEN
   135	                ALTER TABLE users ADD COLUMN partner_id UUID REFERENCES partners(id) ON DELETE SET NULL;
   136	            END IF;
   137	        END $$;
   138	    """)
   139	    await conn.execute(
   140	        "CREATE INDEX IF NOT EXISTS idx_users_partner_id"
   141	        " ON users (partner_id) WHERE partner_id IS NOT NULL;"
   142	    )
   143	
   144	    # -------------------------------------------------------------------------
   145	    # 3. partner_referrals
   146	    # -------------------------------------------------------------------------
   147	    await conn.execute("""
   148	        DO $$
   149	        BEGIN
   150	            IF NOT EXISTS (
   151	                SELECT 1 FROM pg_tables
   152	                WHERE schemaname = 'public' AND tablename = 'partner_referrals'
   153	            ) THEN
   154	                CREATE TABLE partner_referrals (
   155	                    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
   156	                    partner_id           UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
   157	                    process_id           UUID NOT NULL REFERENCES processes(id) ON DELETE RESTRICT,
   158	                    share_percent        NUMERIC(5,2) NOT NULL DEFAULT 100.00
   159	                        CHECK (share_percent > 0 AND share_percent <= 100),
   160	                    referred_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
   161	                    referred_by_user_id  UUID REFERENCES users(id) ON DELETE SET NULL,
   162	                    notes                TEXT,
   163	
   164	                    CONSTRAINT partner_referrals_process_unique_v1 UNIQUE (process_id)
   165	                    -- v2: drop this constraint when enabling split commissions
   166	                );
   167	            END IF;
   168	        END $$;
   169	    """)
   170	
   171	    await conn.execute(
   172	        "CREATE INDEX IF NOT EXISTS idx_partner_referrals_partner_id"
   173	        " ON partner_referrals (partner_id);"
   174	    )
   175	    await conn.execute(
   176	        "CREATE INDEX IF NOT EXISTS idx_partner_referrals_process_id"
   177	        " ON partner_referrals (process_id);"
   178	    )
   179	
   180	    # -------------------------------------------------------------------------
   181	    # 4. partner_commissions (append-only ledger)
   182	    # -------------------------------------------------------------------------
   183	    await conn.execute("""
   184	        DO $$
   185	        BEGIN
   186	            IF NOT EXISTS (
   187	                SELECT 1 FROM pg_tables
   188	                WHERE schemaname = 'public' AND tablename = 'partner_commissions'
   189	            ) THEN
   190	                CREATE TABLE partner_commissions (
   191	                    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
   192	                    partner_id               UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
   193	                    referral_id              UUID REFERENCES partner_referrals(id) ON DELETE RESTRICT,
   194	                    process_id               UUID REFERENCES processes(id) ON DELETE RESTRICT,
   195	
   196	                    -- row type
   197	                    entry_type               TEXT NOT NULL
   198	                        CHECK (entry_type IN ('accrual','clawback','manual_adjustment')),
   199	                    related_commission_id    UUID REFERENCES partner_commissions(id) ON DELETE RESTRICT,
   200	
   201	                    -- immutable snapshot
   202	                    base_amount_idr          NUMERIC(16,2) NOT NULL,
   203	                    commission_type_snapshot TEXT NOT NULL
   204	                        CHECK (commission_type_snapshot IN ('percentage','flat')),
   205	                    commission_value_snapshot NUMERIC(14,4) NOT NULL,
   206	                    rule_source              TEXT NOT NULL DEFAULT 'partner_default'
   207	                        CHECK (rule_source IN ('partner_default','manual_override')),
   208	                    assigned_to_snapshot     UUID REFERENCES users(id) ON DELETE SET NULL,
   209	
   210	                    -- amounts (IDR; clawbacks store NEGATIVE)
   211	                    gross_amount_idr         NUMERIC(16,2) NOT NULL,
   212	                    withholding_category     TEXT NOT NULL DEFAULT 'tbd'
   213	                        CHECK (withholding_category IN ('pph21','pph23','exempt','tbd')),
   214	                    withholding_rate         NUMERIC(6,4) NOT NULL DEFAULT 0.0,
   215	                    withholding_amount_idr   NUMERIC(16,2) NOT NULL DEFAULT 0.0,
   216	                    net_amount_idr           NUMERIC(16,2) NOT NULL,
   217	
   218	                    -- status lifecycle
   219	                    status                   TEXT NOT NULL DEFAULT 'accrued'
   220	                        CHECK (status IN (
   221	                            'accrued','approved','paid',
   222	                            'clawback_pending','offset_applied',
   223	                            'waived','repaid'
   224	                        )),
   225	                    accrued_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
   226	                    eligible_for_approval_at TIMESTAMPTZ NOT NULL,
   227	                    approved_at              TIMESTAMPTZ,
   228	                    approved_by              UUID REFERENCES users(id) ON DELETE SET NULL,
   229	                    paid_at                  TIMESTAMPTZ,
   230	                    paid_by                  UUID REFERENCES users(id) ON DELETE SET NULL,
   231	                    paid_via                 TEXT,
   232	                    payment_reference        TEXT,
   233	                    payment_proof_url        TEXT,
   234	                    receipt_type             TEXT
   235	                        CHECK (receipt_type IS NULL OR receipt_type IN ('kwitansi','invoice','none')),
   236	                    receipt_file_url         TEXT,
   237	
   238	                    -- finance / clawback audit
   239	                    manual_override_reason   TEXT,
   240	                    clawback_reason          TEXT,
   241	                    waiver_reason            TEXT,
   242	                    idempotency_key          TEXT UNIQUE,
   243	                    commission_email_sent_at TIMESTAMPTZ,
   244	
   245	                    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
   246	                );
   247	            END IF;
   248	        END $$;
   249	    """)
   250	
   251	    await conn.execute(
   252	        "CREATE INDEX IF NOT EXISTS idx_partner_commissions_partner_id"
   253	        " ON partner_commissions (partner_id);"
   254	    )
   255	    await conn.execute(
   256	        "CREATE INDEX IF NOT EXISTS idx_partner_commissions_process_id"
   257	        " ON partner_commissions (process_id);"
   258	    )
   259	    await conn.execute(
   260	        "CREATE INDEX IF NOT EXISTS idx_partner_commissions_status"

 succeeded in 0ms:
     1	"""
     2	Partner email module — welcome + commission-earned via Brevo.
     3	
     4	Sending: POST /api/notifications/send-email with X-API-Key (Brevo).
     5	Sender: zantara@balizero.com / Zantara (non-negotiable per feedback_email_sender).
     6	Both functions are idempotent: they read the sentinel timestamp before sending
     7	and call mark_*_sent only after a successful HTTP response.
     8	
     9	PII sterilization (UU PDP 27/2022):
    10	- Client full names are sterilized to "First L." before passing to any template.
    11	- Sterilization happens in Python, never inside Jinja2 templates.
    12	"""
    13	from __future__ import annotations
    14	
    15	import logging
    16	import os
    17	from pathlib import Path
    18	from typing import Any
    19	from uuid import UUID
    20	
    21	import httpx
    22	import jinja2
    23	
    24	from backend.services.crm.partners.repository import PartnersRepository
    25	from backend.services.pricing.pricing_service import get_pricing_service
    26	
    27	logger = logging.getLogger(__name__)
    28	
    29	# ─── Jinja2 environment ────────────────────────────────────────────────────
    30	_TEMPLATES_DIR = Path(__file__).parent / "templates"
    31	_env = jinja2.Environment(
    32	    loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
    33	    autoescape=False,
    34	    keep_trailing_newline=True,
    35	)
    36	
    37	# ─── Email API constants ────────────────────────────────────────────────────
    38	# Sender MUST be zantara@balizero.com per feedback_email_sender memory rule.
    39	SENDER_EMAIL = "zantara@balizero.com"
    40	SENDER_NAME = "Zantara"
    41	NOTIFICATIONS_ENDPOINT = os.environ.get(
    42	    "NOTIFICATIONS_ENDPOINT",
    43	    "https://nuzantara-rag.fly.dev/api/notifications/send-email",
    44	)
    45	X_API_KEY = os.environ.get("NOTIFICATIONS_X_API_KEY", "REDACTED-ROTATED-KEY")
    46	
    47	
    48	# ─── Internal helpers ───────────────────────────────────────────────────────
    49	
    50	async def _post_email(*, to: str, cc: list[str] | None, subject: str, body: str) -> None:
    51	    """
    52	    POST to the internal Brevo email relay endpoint.
    53	
    54	    Payload shape matches the existing endpoint contract used by
    55	    welcome_email_service.py — fields: to, subject, body, cc.
    56	    Sender (from_email / from_name) is set server-side; the payload does not
    57	    include those fields.
    58	    """
    59	    payload: dict[str, Any] = {
    60	        "to": to,
    61	        "subject": subject,
    62	        "body": body,
    63	    }
    64	    if cc:
    65	        payload["cc"] = cc
    66	
    67	    async with httpx.AsyncClient(timeout=30.0) as client:
    68	        r = await client.post(
    69	            NOTIFICATIONS_ENDPOINT,
    70	            json=payload,
    71	            headers={"X-API-Key": X_API_KEY},
    72	        )
    73	        r.raise_for_status()
    74	
    75	
    76	def _sterilize(name: str) -> str:
    77	    """
    78	    Reduce a full name to "FirstName L." for UU PDP compliance.
    79	
    80	    Examples:
    81	      "Mario Rossi"        → "Mario R."
    82	      "Alice"              → "Alice"
    83	      "Jean-Claude Van Dam" → "Jean-Claude D."
    84	      ""                   → ""
    85	    """
    86	    parts = name.strip().split()
    87	    if not parts:
    88	        return ""
    89	    if len(parts) == 1:
    90	        return parts[0]
    91	    return f"{parts[0]} {parts[-1][0]}."
    92	
    93	
    94	def _build_pricing_services() -> list[dict[str, str]]:
    95	    """Return list of {name, price_display} pairs from PricingService.
    96	
    97	    The pricing JSON has 3 levels:
    98	      services (top) -> sub_category (dict) -> service_name (dict key) -> {price, duration, ...}
    99	
   100	    We flatten to a list of {name, price_display}. Returns empty list if
   101	    PricingService is not loaded (graceful degradation for the welcome
   102	    email — terms still communicate; services list is absent).
   103	
   104	    Golden Rule #12: prices ONLY from PricingTool/PricingService, never hardcoded.
   105	    """
   106	    svc = get_pricing_service()
   107	    if not getattr(svc, "loaded", False):
   108	        logger.warning("PricingService not loaded — welcome email services list will be empty")
   109	        return []
   110	    all_prices = svc.get_all_prices() or {}
   111	    top = all_prices.get("services", all_prices)
   112	    result: list[dict[str, str]] = []
   113	    if not isinstance(top, dict):
   114	        return result
   115	    for sub_cat, entries in top.items():
   116	        if isinstance(entries, dict):
   117	            for service_name, entry in entries.items():
   118	                if not isinstance(entry, dict):
   119	                    continue
   120	                price_str = entry.get("price") or entry.get("final_price") or "On request"
   121	                if not isinstance(price_str, str):
   122	                    price_str = str(price_str)
   123	                result.append({
   124	                    "name": str(service_name),
   125	                    "price_display": price_str,
   126	                })
   127	        elif isinstance(entries, list):
   128	            # Legacy flat-list shape, keep for safety
   129	            for item in entries:
   130	                if isinstance(item, dict) and "name" in item:
   131	                    result.append({
   132	                        "name": str(item["name"]),
   133	                        "price_display": str(item.get("price_display") or item.get("price") or "On request"),
   134	                    })
   135	    return result
   136	
   137	
   138	# ─── Public API ─────────────────────────────────────────────────────────────
   139	
   140	async def send_welcome(conn: Any, partner_id: UUID) -> None:
   141	    """
   142	    Send the partner welcome email.
   143	
   144	    Idempotent: reads welcome_email_sent_at before sending.
   145	    If already sent, logs and returns without HTTP call.
   146	
   147	    Args:
   148	        conn: asyncpg.Connection (passed directly by the router).
   149	        partner_id: UUID of the partner.
   150	    """
   151	    repo = PartnersRepository(conn)
   152	    p = await repo.get_partner(partner_id)
   153	    if p is None:
   154	        logger.warning("send_welcome: partner %s not found — skip", partner_id)
   155	        return
   156	    if p.welcome_email_sent_at is not None:
   157	        logger.info("send_welcome: already sent for partner %s — skip (idempotent)", partner_id)
   158	        return
   159	
   160	    pricing_services = _build_pricing_services()
   161	
   162	    commission_rate = (
   163	        f"{p.default_commission_value}%"
   164	        if p.default_commission_type == "percentage"
   165	        else f"IDR {p.default_commission_value:,.0f}"
   166	    )
   167	
   168	    tpl = _env.get_template("welcome.md.j2")
   169	    body = tpl.render(
   170	        partner=p,
   171	        commission_rate=commission_rate,
   172	        commission_type=p.default_commission_type,
   173	        pricing_services=pricing_services,
   174	    )
   175	
   176	    await _post_email(
   177	        to=p.email,
   178	        cc=None,
   179	        subject="Welcome to Bali Zero Partners",
   180	        body=body,
   181	    )
   182	    await repo.mark_welcome_sent(partner_id)
   183	    logger.info("send_welcome: sent to partner %s (%s)", partner_id, p.email)
   184	
   185	
   186	async def send_commission_earned(conn: Any, commission_id: UUID) -> None:
   187	    """
   188	    Send the commission-earned notification email.
   189	
   190	    Idempotent: reads commission_email_sent_at before sending.
   191	    Client name is sterilized to "First L." BEFORE template rendering (UU PDP).
   192	
   193	    Args:
   194	        conn: asyncpg.Connection (passed directly by the router).
   195	        commission_id: UUID of the partner_commissions row.
   196	    """
   197	    repo = PartnersRepository(conn)
   198	    c = await repo.get_commission(commission_id)
   199	    if c is None or c.status != "paid":
   200	        logger.info(
   201	            "send_commission_earned: commission %s not found or not paid — skip",
   202	            commission_id,
   203	        )
   204	        return
   205	    if c.commission_email_sent_at is not None:
   206	        logger.info(
   207	            "send_commission_earned: already sent for commission %s — skip (idempotent)",
   208	            commission_id,
   209	        )
   210	        return
   211	
   212	    p = await repo.get_partner(c.partner_id)
   213	    if p is None:
   214	        logger.warning("send_commission_earned: partner %s not found — skip", c.partner_id)
   215	        return
   216	
   217	    # Fetch process + client name via JOIN
   218	    proc = None
   219	    if c.process_id is not None:
   220	        proc = await conn.fetchrow(
   221	            """
   222	            SELECT p.service_type, c.full_name AS client_name
   223	            FROM processes p
   224	            LEFT JOIN clients c ON c.id = p.client_id
   225	            WHERE p.id = $1
   226	            """,
   227	            c.process_id,
   228	        )
   229	
   230	    service_type = (proc["service_type"] if proc and proc["service_type"] else "service") if proc else "service"
   231	    raw_client_name = (proc["client_name"] or "") if proc else ""
   232	
   233	    # UU PDP: sterilize BEFORE template render, never inside template
   234	    client_display = _sterilize(raw_client_name) if raw_client_name else "client"
   235	
   236	    # CC the assigned-to user if resolvable
   237	    cc_list: list[str] = []
   238	    if c.assigned_to_snapshot is not None:
   239	        row = await conn.fetchrow(
   240	            "SELECT email FROM users WHERE id = $1",
   241	            c.assigned_to_snapshot,
   242	        )
   243	        if row and row["email"]:
   244	            cc_list.append(row["email"])
   245	
   246	    tpl = _env.get_template("commission.md.j2")
   247	    body = tpl.render(
   248	        partner=p,
   249	        client_display=client_display,
   250	        service_type=service_type,
   251	        gross_idr=f"{c.gross_amount_idr:,.0f}",
   252	        withholding_idr=f"{c.withholding_amount_idr:,.0f}",
   253	        withholding_category=c.withholding_category,
   254	        net_idr=f"{c.net_amount_idr:,.0f}",
   255	        paid_via=c.paid_via or "",
   256	        payment_reference=c.payment_reference or "",
   257	        paid_at=c.paid_at.isoformat() if c.paid_at else "",
   258	        receipt_file_url=c.receipt_file_url,
   259	    )
   260	
   261	    subject = f"Commissione maturata — {client_display}"
   262	    await _post_email(
   263	        to=p.email,
   264	        cc=cc_list if cc_list else None,
   265	        subject=subject,
   266	        body=body,
   267	    )
   268	    await repo.mark_commission_email_sent(commission_id)
   269	    logger.info("send_commission_earned: sent for commission %s to %s", commission_id, p.email)

exec
/bin/zsh -lc "nl -ba apps/backend-rag/backend/app/routers/partners.py | sed -n '548,760p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
   548	async def create_referral(
   549	    partner_id: UUID,
   550	    body: ReferralCreate,
   551	    user: dict[str, Any] = Depends(get_current_user),
   552	    pool: asyncpg.Pool = Depends(get_database_pool),
   553	) -> Any:
   554	    """Record a referral for a partner. Team (owner) or admin."""
   555	    try:
   556	        async with pool.acquire() as conn:
   557	            svc = PartnersService(conn)
   558	            await verify_partner_access_with_role(
   559	                svc, UUID(str(user["user_id"])), user.get("role"), partner_id
   560	            )
   561	            rid = await svc.repo.insert_referral(
   562	                partner_id=partner_id,
   563	                process_id=body.process_id,
   564	                referred_by_user_id=UUID(str(user["user_id"])),
   565	                notes=body.notes,
   566	            )
   567	            return {"id": str(rid), "partner_id": str(partner_id), "process_id": str(body.process_id)}
   568	    except HTTPException:
   569	        raise
   570	    except asyncpg.UniqueViolationError:
   571	        raise HTTPException(status_code=409, detail="process already has a referral")
   572	    except Exception as e:
   573	        if "unique" in str(e).lower():
   574	            raise HTTPException(status_code=409, detail="process already has a referral")
   575	        logger.exception("create_referral failed")
   576	        raise HTTPException(status_code=500, detail="internal error")
   577	
   578	
   579	@router.patch("/referrals/{referral_id}", status_code=status.HTTP_204_NO_CONTENT)
   580	async def swap_referral(
   581	    referral_id: UUID,
   582	    body: ReferralSwap,
   583	    user: dict[str, Any] = Depends(get_current_user),
   584	    pool: asyncpg.Pool = Depends(get_database_pool),
   585	) -> Response:
   586	    """Swap a referral to a different partner. Admin only."""
   587	    _require_admin(user)
   588	    try:
   589	        async with pool.acquire() as conn:
   590	            svc = PartnersService(conn)
   591	            await svc.repo.update_referral_partner(referral_id, body.new_partner_id)
   592	            return Response(status_code=204)
   593	    except HTTPException:
   594	        raise
   595	    except Exception:
   596	        logger.exception("swap_referral failed")
   597	        raise HTTPException(status_code=500, detail="internal error")
   598	
   599	
   600	@router.delete("/referrals/{referral_id}", status_code=status.HTTP_204_NO_CONTENT)
   601	async def delete_referral(
   602	    referral_id: UUID,
   603	    user: dict[str, Any] = Depends(get_current_user),
   604	    pool: asyncpg.Pool = Depends(get_database_pool),
   605	) -> Response:
   606	    """Delete a referral. Admin only. Blocked if commissions exist."""
   607	    _require_admin(user)
   608	    try:
   609	        async with pool.acquire() as conn:
   610	            svc = PartnersService(conn)
   611	            await svc.repo.delete_referral(referral_id)
   612	            return Response(status_code=204)
   613	    except HTTPException:
   614	        raise
   615	    except RuntimeError as e:
   616	        raise HTTPException(status_code=409, detail=str(e))
   617	    except Exception:
   618	        logger.exception("delete_referral failed")
   619	        raise HTTPException(status_code=500, detail="internal error")
   620	
   621	
   622	# ── Commissions ───────────────────────────────────────────────────────────────
   623	
   624	@router.get("/{partner_id}/commissions")
   625	async def list_commissions(
   626	    partner_id: UUID,
   627	    user: dict[str, Any] = Depends(get_current_user),
   628	    pool: asyncpg.Pool = Depends(get_database_pool),
   629	) -> Any:
   630	    """List commissions for a partner. Scoped by role."""
   631	    async with pool.acquire() as conn:
   632	        svc = PartnersService(conn)
   633	        await verify_partner_access_with_role(
   634	            svc, UUID(str(user["user_id"])), user.get("role"), partner_id
   635	        )
   636	        commissions = await svc.repo.list_commissions_for_partner(partner_id)
   637	        return [
   638	            dataclasses.asdict(c) if dataclasses.is_dataclass(c) else dict(c)
   639	            for c in commissions
   640	        ]
   641	
   642	
   643	@router.get("/{partner_id}/audit-log")
   644	async def list_partner_audit_log(
   645	    partner_id: UUID,
   646	    user: dict[str, Any] = Depends(get_current_user),
   647	    pool: asyncpg.Pool = Depends(get_database_pool),
   648	) -> Any:
   649	    """List the audit log for a partner. Admin or team-owner only."""
   650	    try:
   651	        async with pool.acquire() as conn:
   652	            svc = PartnersService(conn)
   653	            await verify_partner_access_with_role(svc, UUID(str(user["user_id"])), user.get("role"), partner_id)
   654	            entries = await svc.list_audit(partner_id)
   655	            return [_partner_to_dict(e) for e in entries]
   656	    except HTTPException:
   657	        raise
   658	    except Exception:
   659	        logger.exception("list_partner_audit_log failed")
   660	        raise HTTPException(status_code=500, detail="internal error")
   661	
   662	
   663	@router.post("/commissions/{commission_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
   664	async def approve_commission(
   665	    commission_id: UUID,
   666	    user: dict[str, Any] = Depends(get_current_user),
   667	    pool: asyncpg.Pool = Depends(get_database_pool),
   668	) -> Response:
   669	    """Approve a commission. Admin + finance permission."""
   670	    _require_admin(user)
   671	    _require_finance(user)
   672	    try:
   673	        async with pool.acquire() as conn:
   674	            engine = CommissionEngine(conn)
   675	            await engine.approve(commission_id, actor=UUID(str(user["user_id"])))
   676	            return Response(status_code=204)
   677	    except HTTPException:
   678	        raise
   679	    except ValueError as e:
   680	        raise HTTPException(status_code=400, detail=str(e))
   681	    except Exception:
   682	        logger.exception("approve_commission failed")
   683	        raise HTTPException(status_code=500, detail="internal error")
   684	
   685	
   686	@router.post("/commissions/{commission_id}/mark-paid", status_code=status.HTTP_204_NO_CONTENT)
   687	async def mark_paid_commission(
   688	    commission_id: UUID,
   689	    body: CommissionMarkPaidRequest,
   690	    user: dict[str, Any] = Depends(get_current_user),
   691	    pool: asyncpg.Pool = Depends(get_database_pool),
   692	) -> Response:
   693	    """Mark a commission as paid. Admin + finance permission."""
   694	    _require_admin(user)
   695	    _require_finance(user)
   696	    try:
   697	        async with pool.acquire() as conn:
   698	            engine = CommissionEngine(conn)
   699	            await engine.mark_paid(
   700	                commission_id,
   701	                actor=UUID(str(user["user_id"])),
   702	                paid_via=body.paid_via,
   703	                payment_reference=body.payment_reference,
   704	                payment_proof_url=body.payment_proof_url,
   705	                receipt_type=body.receipt_type,
   706	                receipt_file_url=body.receipt_file_url,
   707	            )
   708	            # Trigger commission-paid email if emails module is available (Task 8)
   709	            try:
   710	                from backend.services.crm.partners.emails import send_commission_earned
   711	                await send_commission_earned(conn, commission_id)
   712	            except ImportError:
   713	                pass
   714	            return Response(status_code=204)
   715	    except HTTPException:
   716	        raise
   717	    except ValueError as e:
   718	        raise HTTPException(status_code=400, detail=str(e))
   719	    except Exception:
   720	        logger.exception("mark_paid_commission failed")
   721	        raise HTTPException(status_code=500, detail="internal error")
   722	
   723	
   724	@router.post("/commissions/{commission_id}/clawback", status_code=status.HTTP_201_CREATED)
   725	async def clawback_commission(
   726	    commission_id: UUID,
   727	    body: ClawbackRequest,
   728	    user: dict[str, Any] = Depends(get_current_user),
   729	    pool: asyncpg.Pool = Depends(get_database_pool),
   730	) -> Any:
   731	    """Initiate a clawback on a commission. Admin + finance permission. Returns new commission id."""
   732	    _require_admin(user)
   733	    _require_finance(user)
   734	    try:
   735	        async with pool.acquire() as conn:
   736	            engine = CommissionEngine(conn)
   737	            cid = await engine.clawback(
   738	                commission_id,
   739	                actor=UUID(str(user["user_id"])),
   740	                reason=body.reason,
   741	                amount_idr=body.amount_idr,
   742	            )
   743	            return {"id": str(cid)}
   744	    except HTTPException:
   745	        raise
   746	    except ValueError as e:
   747	        raise HTTPException(status_code=400, detail=str(e))
   748	    except Exception:
   749	        logger.exception("clawback_commission failed")
   750	        raise HTTPException(status_code=500, detail="internal error")
   751	
   752	
   753	@router.post("/commissions/{commission_id}/waive", status_code=status.HTTP_204_NO_CONTENT)
   754	async def waive_commission(
   755	    commission_id: UUID,
   756	    body: WaiveRequest,
   757	    user: dict[str, Any] = Depends(get_current_user),
   758	    pool: asyncpg.Pool = Depends(get_database_pool),
   759	) -> Response:
   760	    """Waive a clawback on a commission. Admin + finance permission."""

exec
/bin/zsh -lc "nl -ba apps/backend-rag/backend/services/crm/partners/repository.py | sed -n '302,430p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
   302	    async def update_commission_status(
   303	        self,
   304	        commission_id: UUID,
   305	        new_status: CommissionStatus,
   306	        *,
   307	        approved_by: UUID | None = None,
   308	        paid_by: UUID | None = None,
   309	        paid_via: str | None = None,
   310	        payment_reference: str | None = None,
   311	        payment_proof_url: str | None = None,
   312	        receipt_type: str | None = None,
   313	        receipt_file_url: str | None = None,
   314	        waiver_reason: str | None = None,
   315	    ) -> None:
   316	        current = await self.get_commission(commission_id)
   317	        if current is None:
   318	            raise ValueError(f"Commission {commission_id} not found")
   319	        if new_status not in _ALLOWED_TRANSITIONS.get(current.status, set()):
   320	            raise ValueError(
   321	                f"Disallowed transition: {current.status!r} -> {new_status!r}"
   322	            )
   323	        logger.debug(
   324	            "update_commission_status id=%s %s->%s", commission_id, current.status, new_status
   325	        )
   326	        fragments, args = ["status = $2"], [commission_id, new_status]
   327	        if new_status == "approved":
   328	            fragments += ["approved_at = now()", f"approved_by = ${len(args)+1}"]; args.append(approved_by)
   329	        if new_status == "paid":
   330	            fragments += [
   331	                "paid_at = now()",
   332	                f"paid_by = ${len(args)+1}", f"paid_via = ${len(args)+2}",
   333	                f"payment_reference = ${len(args)+3}", f"payment_proof_url = ${len(args)+4}",
   334	                f"receipt_type = ${len(args)+5}", f"receipt_file_url = ${len(args)+6}",
   335	            ]
   336	            args += [paid_by, paid_via, payment_reference, payment_proof_url,
   337	                     receipt_type, receipt_file_url]
   338	        if new_status == "waived":
   339	            fragments += [f"waiver_reason = ${len(args)+1}"]; args.append(waiver_reason)
   340	        sql = f"UPDATE partner_commissions SET {', '.join(fragments)} WHERE id = $1"
   341	        await self.conn.execute(sql, *args)
   342	
   343	    async def mark_commission_email_sent(self, commission_id: UUID) -> None:
   344	        await self.conn.execute(
   345	            "UPDATE partner_commissions SET commission_email_sent_at = now() "
   346	            "WHERE id = $1 AND commission_email_sent_at IS NULL",
   347	            commission_id,
   348	        )
   349	
   350	    async def delete_commission(self, commission_id: UUID) -> None:
   351	        raise RuntimeError("partner_commissions is append-only; delete is forbidden")
   352	
   353	    # ── Audit log ───────────────────────────────────────────────────────
   354	
   355	    async def insert_audit(
   356	        self,
   357	        *,
   358	        partner_id: UUID,
   359	        action: str,
   360	        actor_user_id: UUID | None = None,
   361	        before: dict | None = None,
   362	        after: dict | None = None,
   363	        reason: str | None = None,
   364	    ) -> None:
   365	        await self.conn.execute(
   366	            """
   367	            INSERT INTO partner_audit_log
   368	                (partner_id, actor_user_id, action, before_json, after_json, reason)
   369	            VALUES ($1, $2, $3, $4, $5, $6)
   370	            """,
   371	            partner_id, actor_user_id, action,
   372	            json.dumps(before) if before else None,
   373	            json.dumps(after) if after else None,
   374	            reason,
   375	        )
   376	
   377	    async def list_audit_for_partner(self, partner_id: UUID) -> list[PartnerAuditLogEntry]:
   378	        rows = await self.conn.fetch(
   379	            "SELECT * FROM partner_audit_log WHERE partner_id = $1 ORDER BY at DESC",
   380	            partner_id,
   381	        )
   382	        return [
   383	            PartnerAuditLogEntry(
   384	                id=r["id"], partner_id=r["partner_id"],
   385	                actor_user_id=r["actor_user_id"], action=r["action"],
   386	                before_json=json.loads(r["before_json"]) if r["before_json"] else None,
   387	                after_json=json.loads(r["after_json"]) if r["after_json"] else None,
   388	                reason=r["reason"], at=r["at"],
   389	            )
   390	            for r in rows
   391	        ]
   392	
   393	    # ── Row mappers ─────────────────────────────────────────────────────
   394	
   395	    @staticmethod
   396	    def _row_to_partner(row: asyncpg.Record) -> Partner:
   397	        return Partner(**dict(row))
   398	
   399	    @staticmethod
   400	    def _row_to_referral(row: asyncpg.Record) -> PartnerReferral:
   401	        return PartnerReferral(**dict(row))
   402	
   403	    @staticmethod
   404	    def _row_to_commission(row: asyncpg.Record) -> PartnerCommission:
   405	        return PartnerCommission(**dict(row))

exec
/bin/zsh -lc "nl -ba apps/backend-rag/backend/services/crm/partners/service.py | sed -n '1,260p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
     1	# backend/services/crm/partners/service.py
     2	from __future__ import annotations
     3	
     4	import logging
     5	from typing import Any
     6	from uuid import UUID
     7	
     8	import asyncpg
     9	from fastapi import HTTPException
    10	
    11	from backend.services.crm.partners.models import Partner, PartnerAuditLogEntry
    12	from backend.services.crm.partners.repository import PartnersRepository
    13	
    14	logger = logging.getLogger(__name__)
    15	
    16	
    17	class ConflictError(HTTPException):
    18	    def __init__(self, detail: str):
    19	        super().__init__(status_code=409, detail=detail)
    20	
    21	
    22	class PartnersService:
    23	    def __init__(self, conn: asyncpg.Connection):
    24	        self.conn = conn
    25	        self.repo = PartnersRepository(conn)
    26	
    27	    async def create_partner(
    28	        self,
    29	        *,
    30	        full_name: str,
    31	        email: str,
    32	        entity_type: str,
    33	        assigned_to: UUID | None = None,
    34	        created_by: UUID | None = None,
    35	        **optional: Any,
    36	    ) -> UUID:
    37	        try:
    38	            pid = await self.repo.insert_partner(
    39	                full_name=full_name,
    40	                email=email,
    41	                entity_type=entity_type,
    42	                assigned_to=assigned_to,
    43	                created_by=created_by,
    44	                **optional,
    45	            )
    46	        except ValueError as e:
    47	            raise ConflictError(str(e))
    48	        except asyncpg.UniqueViolationError:
    49	            raise ConflictError(f"email already in use: {email!r}")
    50	        after = {
    51	            "full_name": full_name,
    52	            "email": email,
    53	            "assigned_to": str(assigned_to) if assigned_to else None,
    54	        }
    55	        await self.repo.insert_audit(
    56	            partner_id=pid,
    57	            action="created",
    58	            actor_user_id=created_by,
    59	            after=after,
    60	        )
    61	        return pid
    62	
    63	    async def get_partner(self, partner_id: UUID, *, actor_user: UUID) -> Partner:
    64	        return await verify_partner_access(self, actor_user, partner_id)
    65	
    66	    async def list_partners(
    67	        self,
    68	        *,
    69	        actor_user: UUID,
    70	        actor_role: str,
    71	        assigned_to: UUID | None = None,
    72	        onboarding_status: str | None = None,
    73	        orphaned: bool = False,
    74	        search: str | None = None,
    75	    ) -> list[Partner]:
    76	        if actor_role == "team":
    77	            assigned_to = actor_user  # force scope to own
    78	        return await self.repo.list_partners(
    79	            assigned_to=assigned_to,
    80	            onboarding_status=onboarding_status,
    81	            orphaned=orphaned,
    82	            search=search,
    83	        )
    84	
    85	    async def update_partner(
    86	        self,
    87	        partner_id: UUID,
    88	        *,
    89	        actor_user: UUID,
    90	        actor_role: str,
    91	        **fields: Any,
    92	    ) -> None:
    93	        if actor_role == "partner":
    94	            raise HTTPException(status_code=403, detail="partners may not update their own profile via this endpoint")
    95	        current = await verify_partner_access_with_role(
    96	            self, actor_user, actor_role, partner_id
    97	        )
    98	        before = {k: getattr(current, k) for k in fields if hasattr(current, k)}
    99	        try:
   100	            await self.repo.update_partner(partner_id, **fields)
   101	        except ValueError as e:
   102	            raise ConflictError(str(e))
   103	        await self.repo.insert_audit(
   104	            partner_id=partner_id,
   105	            action="updated",
   106	            actor_user_id=actor_user,
   107	            before=before,
   108	            after=fields,
   109	        )
   110	
   111	    async def activate_partner(self, partner_id: UUID, *, actor_user: UUID) -> None:
   112	        if not await _is_admin(self.conn, actor_user):
   113	            raise HTTPException(status_code=403, detail="admin only")
   114	        await self.repo.activate_partner(partner_id)
   115	        await self.repo.insert_audit(
   116	            partner_id=partner_id,
   117	            action="activated",
   118	            actor_user_id=actor_user,
   119	        )
   120	
   121	    async def deactivate_partner(self, partner_id: UUID, *, actor_user: UUID) -> None:
   122	        if not await _is_admin(self.conn, actor_user):
   123	            raise HTTPException(status_code=403, detail="admin only")
   124	        await self.repo.deactivate_partner(partner_id)
   125	        await self.repo.insert_audit(
   126	            partner_id=partner_id,
   127	            action="deactivated",
   128	            actor_user_id=actor_user,
   129	        )
   130	
   131	    async def reassign_partner(
   132	        self,
   133	        partner_id: UUID,
   134	        *,
   135	        new_user_id: UUID | None,
   136	        actor_user: UUID,
   137	        reason: str | None,
   138	    ) -> None:
   139	        if not await _is_admin(self.conn, actor_user):
   140	            raise HTTPException(status_code=403, detail="admin only")
   141	        if not reason:
   142	            raise ValueError("reason is required for reassignment")
   143	        current = await self.repo.get_partner(partner_id)
   144	        if current is None:
   145	            raise HTTPException(status_code=404, detail="partner not found")
   146	        before = {"assigned_to": str(current.assigned_to) if current.assigned_to else None}
   147	        after = {"assigned_to": str(new_user_id) if new_user_id else None}
   148	        await self.repo.reassign_partner(partner_id, new_user_id)
   149	        await self.repo.insert_audit(
   150	            partner_id=partner_id,
   151	            action="reassigned",
   152	            actor_user_id=actor_user,
   153	            before=before,
   154	            after=after,
   155	            reason=reason,
   156	        )
   157	
   158	    async def orphan_partners_of_user(self, user_id: UUID, *, actor_user: UUID) -> int:
   159	        if not await _is_admin(self.conn, actor_user):
   160	            raise HTTPException(status_code=403, detail="admin only")
   161	        affected = await self.repo.list_partners(assigned_to=user_id)
   162	        n = await self.repo.orphan_partners_of_user(user_id)
   163	        for p in affected:
   164	            await self.repo.insert_audit(
   165	                partner_id=p.id,
   166	                action="orphaned",
   167	                actor_user_id=actor_user,
   168	                before={"assigned_to": str(user_id)},
   169	                after={"assigned_to": None},
   170	                reason=f"auto-orphan on deactivation of user {user_id}",
   171	            )
   172	        return n
   173	
   174	    async def list_audit(self, partner_id: UUID) -> list[PartnerAuditLogEntry]:
   175	        return await self.repo.list_audit_for_partner(partner_id)
   176	
   177	    async def mark_welcome_sent(self, partner_id: UUID) -> None:
   178	        await self.repo.mark_welcome_sent(partner_id)
   179	
   180	
   181	async def _is_admin(conn: asyncpg.Connection, user_id: UUID) -> bool:
   182	    row = await conn.fetchrow("SELECT role FROM users WHERE id = $1", user_id)
   183	    return bool(row) and row["role"] == "admin"
   184	
   185	
   186	async def _get_role(conn: asyncpg.Connection, user_id: UUID) -> str | None:
   187	    row = await conn.fetchrow("SELECT role FROM users WHERE id = $1", user_id)
   188	    return row["role"] if row else None
   189	
   190	
   191	async def verify_partner_access(
   192	    svc: PartnersService, actor_user: UUID, partner_id: UUID
   193	) -> Partner:
   194	    role = await _get_role(svc.conn, actor_user)
   195	    return await verify_partner_access_with_role(svc, actor_user, role, partner_id)
   196	
   197	
   198	async def verify_partner_access_with_role(
   199	    svc: PartnersService,
   200	    actor_user: UUID,
   201	    actor_role: str | None,
   202	    partner_id: UUID,
   203	) -> Partner:
   204	    partner = await svc.repo.get_partner(partner_id)
   205	    if partner is None:
   206	        raise HTTPException(status_code=404, detail="partner not found")
   207	    if actor_role == "admin":
   208	        return partner
   209	    if actor_role == "team" and partner.assigned_to == actor_user:
   210	        return partner
   211	    if actor_role == "partner":
   212	        # Check via users table: user.partner_id matches partner.id
   213	        row = await svc.conn.fetchrow(
   214	            "SELECT partner_id FROM users WHERE id = $1", actor_user
   215	        )
   216	        if row and row["partner_id"] == partner_id:
   217	            return partner
   218	    raise HTTPException(status_code=403, detail="forbidden")

exec
/bin/zsh -lc "nl -ba apps/backend-rag/backend/services/crm/partners/events.py | sed -n '1,180p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
     1	"""
     2	EventBus subscriber for the CRM Partners module.
     3	
     4	Subscribes to ``practice.status_changed`` (PG channel ``practice_changed``
     5	aliased in event_bus.PG_CHANNEL_MAP).  When a process transitions to
     6	``completed``, delegates accrual to :class:`CommissionEngine` and publishes
     7	``partner.commission_changed`` via ``pg_notify`` on success.
     8	
     9	Implementation plan: docs/superpowers/plans/2026-04-20-crm-partners-module.md Task 6
    10	"""
    11	from __future__ import annotations
    12	
    13	import json
    14	import logging
    15	from typing import TYPE_CHECKING, Any
    16	from uuid import UUID
    17	
    18	from backend.app.db import get_pool
    19	from backend.services.crm.partners.commission_engine import CommissionEngine
    20	
    21	if TYPE_CHECKING:
    22	    from backend.services.events.event_bus import EventBus
    23	
    24	logger = logging.getLogger(__name__)
    25	
    26	PARTNER_COMMISSION_CHANGED = "partner.commission_changed"
    27	
    28	
    29	async def handle_practice_status_changed(payload: dict[str, Any]) -> None:
    30	    """Handler for ``practice.status_changed`` events.
    31	
    32	    Triggers commission accrual when a process flips to ``completed``.
    33	    Payment status is re-verified inside
    34	    :meth:`CommissionEngine.accrue_from_process` by querying the process row
    35	    directly — the event payload may not carry ``payment_status``.
    36	
    37	    Early-exit conditions (no DB access):
    38	    - ``new_status`` != ``"completed"``
    39	    - ``process_id`` is absent or falsy
    40	    - ``process_id`` cannot be parsed as a UUID
    41	    """
    42	    new_status = payload.get("new_status")
    43	    process_id = payload.get("process_id")
    44	
    45	    if new_status != "completed" or not process_id:
    46	        return
    47	
    48	    try:
    49	        pid = UUID(process_id) if isinstance(process_id, str) else process_id
    50	    except (ValueError, TypeError):
    51	        logger.warning(
    52	            "handle_practice_status_changed: bad process_id %r", process_id
    53	        )
    54	        return
    55	
    56	    pool = await get_pool()
    57	    async with pool.acquire() as conn:
    58	        engine = CommissionEngine(conn)
    59	        cid = await engine.accrue_from_process(pid)
    60	        if cid is None:
    61	            return
    62	
    63	        # Read partner_id for the notification payload
    64	        row = await conn.fetchrow(
    65	            "SELECT partner_id FROM partner_commissions WHERE id = $1", cid
    66	        )
    67	        if row is None:
    68	            return
    69	        partner_id = row["partner_id"]
    70	
    71	    await _publish_changed(partner_id, cid, kind="accrued")
    72	
    73	
    74	async def _publish_changed(
    75	    partner_id: UUID,
    76	    commission_id: UUID,
    77	    *,
    78	    kind: str,
    79	) -> None:
    80	    """Emit a ``partner.commission_changed`` notification via PostgreSQL NOTIFY.
    81	
    82	    Uses parameterised ``pg_notify($1, $2)`` — NOT string-interpolated NOTIFY —
    83	    to avoid SQL injection on malformed UUIDs or unexpected ``kind`` values.
    84	    """
    85	    pool = await get_pool()
    86	    async with pool.acquire() as conn:
    87	        notification_payload = json.dumps(
    88	            {
    89	                "partner_id": str(partner_id),
    90	                "commission_id": str(commission_id),
    91	                "type": kind,
    92	            }
    93	        )
    94	        # pg_notify with parameters — injection-safe
    95	        await conn.execute(
    96	            "SELECT pg_notify($1, $2)",
    97	            PARTNER_COMMISSION_CHANGED,
    98	            notification_payload,
    99	        )
   100	    logger.info(
   101	        "Published partner.commission_changed: %s (%s)", commission_id, kind
   102	    )
   103	
   104	
   105	def register_partner_handlers(bus: "EventBus") -> None:
   106	    """Subscribe partner-module handlers to the EventBus."""
   107	    bus.subscribe("practice.status_changed", handle_practice_status_changed)
   108	    logger.info("Partner handlers registered on practice.status_changed")

exec
/bin/zsh -lc "nl -ba apps/backend-rag/backend/services/crm/partners/commission_engine.py | sed -n '280,430p'" in /Users/nuzantara/Desktop/partners-spec-wt
exec
/bin/zsh -lc "nl -ba apps/backend-rag/backend/migrations/migration_119_partners.py | sed -n '260,380p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
   280	    async def mark_paid(
   281	        self,
   282	        commission_id: UUID,
   283	        *,
   284	        actor: UUID,
   285	        paid_via: str,
   286	        payment_reference: str,
   287	        payment_proof_url: str | None = None,
   288	        receipt_type: str | None = None,
   289	        receipt_file_url: str | None = None,
   290	    ) -> None:
   291	        """Transition a commission from 'approved' to 'paid'."""
   292	        await self.repo.update_commission_status(
   293	            commission_id,
   294	            "paid",
   295	            paid_by=actor,
   296	            paid_via=paid_via,
   297	            payment_reference=payment_reference,
   298	            payment_proof_url=payment_proof_url,
   299	            receipt_type=receipt_type,
   300	            receipt_file_url=receipt_file_url,
   301	        )
   302	
   303	    # ── Clawback ────────────────────────────────────────────────────────────
   304	
   305	    async def clawback(
   306	        self,
   307	        original_commission_id: UUID,
   308	        *,
   309	        actor: UUID,
   310	        reason: str,
   311	        amount_idr: Decimal | None = None,
   312	    ) -> UUID:
   313	        """Issue a clawback against an approved or paid commission.
   314	
   315	        Inserts a new 'clawback' entry_type row with negative amounts and
   316	        status 'clawback_pending' (or 'waived' if the auto-writeoff threshold
   317	        is configured and the amount is below it).
   318	
   319	        Idempotency: NOT idempotent — each call inserts a new row. This is
   320	        intentional: an operator may legitimately issue multiple partial
   321	        clawbacks against the same original commission. The idempotency_key
   322	        includes now().isoformat() to prevent accidental de-dup.
   323	
   324	        Args:
   325	            original_commission_id: The approved|paid commission to claw back.
   326	            actor: The user UUID performing the operation.
   327	            reason: Free-text justification (stored in clawback_reason).
   328	            amount_idr: Override the clawback magnitude (positive IDR amount).
   329	                        Defaults to the full net_amount_idr of the original.
   330	
   331	        Returns:
   332	            UUID of the newly created clawback row.
   333	        """
   334	        orig = await self.repo.get_commission(original_commission_id)
   335	        if orig is None:
   336	            raise ValueError(f"Commission not found: {original_commission_id}")
   337	        if orig.status not in ("approved", "paid"):
   338	            raise ValueError(
   339	                f"Clawback only valid for approved|paid commissions, "
   340	                f"got status {orig.status!r}"
   341	            )
   342	
   343	        # magnitude is the positive IDR amount to claw back
   344	        magnitude = amount_idr if amount_idr is not None else orig.net_amount_idr
   345	        gross_neg = -magnitude
   346	        net_neg = -magnitude
   347	
   348	        # Auto-writeoff: if the magnitude is below the threshold (and threshold > 0),
   349	        # insert directly as 'waived' instead of 'clawback_pending'.
   350	        threshold = await self._system_setting_int(
   351	            "partner_clawback_auto_writeoff_idr", 0
   352	        )
   353	        auto_waive = threshold > 0 and abs(int(magnitude)) < threshold
   354	
   355	        status = "waived" if auto_waive else "clawback_pending"
   356	
   357	        # Key is NOT idempotent by design — see docstring above.
   358	        key = f"clawback:{original_commission_id}:{datetime.now(timezone.utc).isoformat()}"
   359	
   360	        cid = await self.repo.insert_commission(
   361	            partner_id=orig.partner_id,
   362	            entry_type="clawback",
   363	            referral_id=orig.referral_id,
   364	            process_id=orig.process_id,
   365	            related_commission_id=orig.id,
   366	            base_amount_idr=orig.base_amount_idr,
   367	            commission_type_snapshot=orig.commission_type_snapshot,
   368	            commission_value_snapshot=orig.commission_value_snapshot,
   369	            assigned_to_snapshot=orig.assigned_to_snapshot,
   370	            gross_amount_idr=gross_neg,
   371	            withholding_category=orig.withholding_category,
   372	            withholding_rate=orig.withholding_rate,
   373	            withholding_amount_idr=Decimal("0"),
   374	            net_amount_idr=net_neg,
   375	            status=status,
   376	            idempotency_key=key,
   377	            clawback_reason=reason,
   378	        )
   379	
   380	        if auto_waive:
   381	            logger.info(
   382	                "clawback %s auto-waived (magnitude %s IDR < threshold %s IDR)",
   383	                cid, magnitude, threshold,
   384	            )
   385	        else:
   386	            logger.info(
   387	                "clawback %s created (clawback_pending, magnitude %s IDR) "
   388	                "against original %s",
   389	                cid, magnitude, original_commission_id,
   390	            )
   391	        return cid
   392	
   393	    # ── Waive clawback ──────────────────────────────────────────────────────
   394	
   395	    async def waive_clawback(
   396	        self,
   397	        clawback_id: UUID,
   398	        *,
   399	        actor: UUID,
   400	        reason: str,
   401	    ) -> None:
   402	        """Manually waive a 'clawback_pending' commission (operator decision)."""
   403	        await self.repo.update_commission_status(
   404	            clawback_id, "waived", waiver_reason=reason
   405	        )
   406	
   407	    # ── Helpers ─────────────────────────────────────────────────────────────
   408	
   409	    async def _system_setting_int(self, key: str, default: int) -> int:
   410	        """Read an integer value from the system_settings table.
   411	
   412	        Returns `default` if the key is absent or the value cannot be
   413	        coerced to int (e.g. empty string, garbage data).
   414	        """
   415	        row = await self.conn.fetchrow(
   416	            "SELECT value FROM system_settings WHERE key = $1", key
   417	        )
   418	        try:
   419	            return int(row["value"]) if row else default
   420	        except (ValueError, TypeError):
   421	            return default

 succeeded in 0ms:
   260	        "CREATE INDEX IF NOT EXISTS idx_partner_commissions_status"
   261	        " ON partner_commissions (status);"
   262	    )
   263	    await conn.execute(
   264	        "CREATE INDEX IF NOT EXISTS idx_partner_commissions_eligible_at"
   265	        " ON partner_commissions (eligible_for_approval_at)"
   266	        " WHERE status = 'accrued';"
   267	    )
   268	    await conn.execute(
   269	        "CREATE INDEX IF NOT EXISTS idx_partner_commissions_assigned_to_snapshot"
   270	        " ON partner_commissions (assigned_to_snapshot)"
   271	        " WHERE assigned_to_snapshot IS NOT NULL;"
   272	    )
   273	
   274	    # -------------------------------------------------------------------------
   275	    # 5. partner_audit_log
   276	    # -------------------------------------------------------------------------
   277	    await conn.execute("""
   278	        DO $$
   279	        BEGIN
   280	            IF NOT EXISTS (
   281	                SELECT 1 FROM pg_tables
   282	                WHERE schemaname = 'public' AND tablename = 'partner_audit_log'
   283	            ) THEN
   284	                CREATE TABLE partner_audit_log (
   285	                    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
   286	                    partner_id    UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
   287	                    actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
   288	                    action        TEXT NOT NULL,
   289	                    before_json   JSONB,
   290	                    after_json    JSONB,
   291	                    reason        TEXT,
   292	                    at            TIMESTAMPTZ NOT NULL DEFAULT now()
   293	                );
   294	            END IF;
   295	        END $$;
   296	    """)
   297	
   298	    await conn.execute(
   299	        "CREATE INDEX IF NOT EXISTS idx_partner_audit_log_partner_id"
   300	        " ON partner_audit_log (partner_id);"
   301	    )
   302	    await conn.execute(
   303	        "CREATE INDEX IF NOT EXISTS idx_partner_audit_log_at"
   304	        " ON partner_audit_log (at DESC);"
   305	    )
   306	
   307	    # -------------------------------------------------------------------------
   308	    # 6. system_settings seed rows (spec §3.5)
   309	    # -------------------------------------------------------------------------
   310	    await conn.execute("""
   311	        INSERT INTO system_settings (key, value, description) VALUES
   312	          ('partner_clawback_auto_writeoff_idr', '0',
   313	           'If > 0, clawback rows below this IDR amount auto-waive on creation. Default 0 = disabled.'),
   314	          ('partner_accrual_cooling_off_days', '30',
   315	           'Days between accrual and eligibility for approval. Default 30.')
   316	        ON CONFLICT (key) DO NOTHING;
   317	    """)
   318	
   319	    logger.info(
   320	        "✅ Migration 119: partners + partner_referrals + partner_commissions"
   321	        " + partner_audit_log + users.partner_id + 2 system_settings rows"
   322	    )
   323	
   324	
   325	async def rollback(conn: Any) -> None:
   326	    # Drop in FK-safe order: children first, parent last (spec §3.6)
   327	    await conn.execute("DROP TABLE IF EXISTS partner_audit_log;")
   328	    await conn.execute("DROP TABLE IF EXISTS partner_commissions;")
   329	    await conn.execute("DROP TABLE IF EXISTS partner_referrals;")
   330	    # Drop users.partner_id index + column before dropping partners (it references partners.id)
   331	    await conn.execute("DROP INDEX IF EXISTS idx_users_partner_id;")
   332	    await conn.execute("ALTER TABLE users DROP COLUMN IF EXISTS partner_id;")
   333	    await conn.execute("DROP TABLE IF EXISTS partners;")
   334	    await conn.execute(
   335	        "DELETE FROM system_settings WHERE key IN "
   336	        "('partner_clawback_auto_writeoff_idr','partner_accrual_cooling_off_days');"
   337	    )
   338	    logger.info(
   339	        "Migration 119 rollback: 4 tables dropped, users.partner_id removed,"
   340	        " 2 system_settings rows deleted"
   341	    )

exec
/bin/zsh -lc "nl -ba apps/mouth/src/middleware.ts | sed -n '1,240p'" in /Users/nuzantara/Desktop/partners-spec-wt
exec
/bin/zsh -lc 'nl -ba apps/backend-rag/backend/app/setup/router_manifest.py | rg -n "partners|portal|process_groups|_BOTH" -C 3' in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
     1	import { NextResponse } from "next/server";
     2	import type { NextRequest } from "next/server";
     3	
     4	/**
     5	 * Multi-domain Middleware
     6	 *
     7	 * Handles routing between:
     8	 * - balizero.com (public website)
     9	 * - kita.balizero.com (internal app)
    10	 */
    11	
    12	// Internal app routes that should only be on zantara subdomain
    13	const INTERNAL_ROUTES = [
    14	  "/login",
    15	  "/dashboard",
    16	  "/clients",
    17	  "/process",
    18	  "/documents",
    19	  "/email",
    20	  "/knowledge",
    21	  "/settings",
    22	  "/team-management", // workspace team management (not /team which is public)
    23	  "/whatsapp",
    24	  "/admin",
    25	  "/agents",
    26	  "/portal",
    27	  "/analytics",
    28	  "/intelligence",
    29	  "/calendar",
    30	  "/notifications",
    31	];
    32	
    33	// Public routes for balizero.com
    34	const PUBLIC_CATEGORIES = [
    35	  "immigration",
    36	  "visas",
    37	  "business",
    38	  "tax-legal",
    39	  "taxes",
    40	  "property",
    41	  "lifestyle",
    42	  "living",
    43	  "digital-nomad",
    44	  "tech",
    45	  "trends",
    46	];
    47	
    48	// Domains
    49	const PUBLIC_DOMAIN = "balizero.com";
    50	const APP_DOMAIN = "kita.balizero.com";
    51	const PORTAL_DOMAIN = "my.balizero.com";
    52	const MOBILE_DOMAIN = "mo.balizero.com";
    53	const ZANTARA_DOMAIN = "zantara.balizero.com";
    54	const VISA_DOMAIN = "visa.balizero.com";
    55	const TAX_DOMAIN = "tax.balizero.com";
    56	const ASSESSMENT_DOMAIN = "subhi.balizero.com";
    57	// SSO subdomains: all *.balizero.com apps that share auth via cookie
    58	const SSO_SUBDOMAINS = ["mail", "calendar", "drive", "knowledge"];
    59	
    60	// Scraper detection — classify requests as human, welcome bot, or suspicious
    61	const WELCOME_BOTS =
    62	  /Googlebot|Bingbot|GPTBot|ClaudeBot|anthropic|PerplexityBot|Applebot|DuckDuckBot|Bytespider|Amazonbot|YouBot|FacebookBot|CCBot/i;
    63	const SCRAPER_SIGNATURES =
    64	  /python-requests|scrapy|curl\/|wget\/|Go-http-client|node-fetch|axios\/\d|PhantomJS|HeadlessChrome|Selenium|Nightmare|puppeteer/i;
    65	
    66	/**
    67	 * Detect RSC/prefetch requests that should NOT be cross-origin redirected.
    68	 * Next.js Link prefetches trigger RSC fetches; redirecting these cross-origin
    69	 * causes CORS errors that flood the console and slow down the page.
    70	 */
    71	function isRSCOrPrefetch(request: NextRequest): boolean {
    72	  return (
    73	    request.nextUrl.searchParams.has("_rsc") ||
    74	    request.headers.get("RSC") === "1" ||
    75	    request.headers.get("Next-Router-Prefetch") === "1" ||
    76	    request.headers.get("Purpose") === "prefetch"
    77	  );
    78	}
    79	
    80	/**
    81	 * Redirect to a cross-origin URL, but return 204 for RSC/prefetch requests
    82	 * to prevent CORS errors in the browser console.
    83	 */
    84	function crossOriginRedirect(
    85	  request: NextRequest,
    86	  targetUrl: URL,
    87	  status: 301 | 302 = 301,
    88	): NextResponse {
    89	  if (isRSCOrPrefetch(request)) {
    90	    return new NextResponse(null, { status: 204 });
    91	  }
    92	  const redirectResponse = NextResponse.redirect(targetUrl, status);
    93	  redirectResponse.headers.set("x-pathname", request.nextUrl.pathname);
    94	  return redirectResponse;
    95	}
    96	
    97	function classifyRequest(
    98	  request: NextRequest,
    99	): "human" | "welcome-bot" | "suspicious" {
   100	  const ua = request.headers.get("user-agent") || "";
   101	  const accept = request.headers.get("accept") || "";
   102	
   103	  if (WELCOME_BOTS.test(ua)) return "welcome-bot";
   104	  if (!ua || !accept) return "suspicious";
   105	  if (SCRAPER_SIGNATURES.test(ua)) return "suspicious";
   106	
   107	  return "human";
   108	}
   109	
   110	export function middleware(request: NextRequest) {
   111	  const hostname = request.headers.get("host") || "";
   112	  const pathname = request.nextUrl.pathname;
   113	
   114	  // Skip static files and API routes
   115	  if (
   116	    pathname.startsWith("/_next") ||
   117	    pathname.startsWith("/api") ||
   118	    pathname.startsWith("/static") ||
   119	    pathname.includes(".") // files with extensions
   120	  ) {
   121	    // Still add pathname header for consistency
   122	    const response = NextResponse.next();
   123	    response.headers.set("x-pathname", pathname);
   124	    return response;
   125	  }
   126	
   127	  // Classify request for scraper detection
   128	  const requestClass = classifyRequest(request);
   129	
   130	  // Create response and add pathname header for Server Components
   131	  const response = NextResponse.next();
   132	  response.headers.set("x-pathname", pathname);
   133	
   134	  // Tag suspicious requests on public content routes
   135	  if (requestClass === "suspicious") {
   136	    const firstSegment = pathname.split("/")[1];
   137	    if (PUBLIC_CATEGORIES.includes(firstSegment) || pathname === "/news") {
   138	      response.headers.set("X-Robots-Tag", "noindex");
   139	      response.headers.set("x-request-class", "suspicious");
   140	    }
   141	  }
   142	
   143	  // === REDIRECT 308: /kbli-navigator → /kbli ===
   144	  // Legacy KBLI Navigator URL redirect (must be in middleware to take priority
   145	  // over the (blog)/[category] catch-all route which would otherwise match first)
   146	  if (
   147	    pathname === "/kbli-navigator" ||
   148	    pathname.startsWith("/kbli-navigator/")
   149	  ) {
   150	    const newPath = pathname.replace("/kbli-navigator", "/kbli") || "/kbli";
   151	    const url = request.nextUrl.clone();
   152	    url.pathname = newPath;
   153	    return NextResponse.redirect(url, 308);
   154	  }
   155	
   156	  // === REDIRECT 301: mo.balizero.com → balizero.com ===
   157	  // SEO: Prevent duplicate content and consolidate domain authority
   158	  if (hostname === MOBILE_DOMAIN || hostname === `www.${MOBILE_DOMAIN}`) {
   159	    const redirectUrl = new URL(pathname, `https://${PUBLIC_DOMAIN}`);
   160	    redirectUrl.search = request.nextUrl.search;
   161	    const redirectResponse = NextResponse.redirect(redirectUrl, 301); // Permanent redirect
   162	    redirectResponse.headers.set("x-pathname", pathname);
   163	    return redirectResponse;
   164	  }
   165	
   166	  // Determine if we're on the public domain
   167	  const subdomain = hostname.split(".")[0]; // e.g. "mail", "calendar", "kita", "balizero"
   168	  const isSSOSubdomain = SSO_SUBDOMAINS.includes(subdomain);
   169	  const isVisaDomain =
   170	    hostname.includes("visa.balizero") || hostname === VISA_DOMAIN;
   171	  const isTaxDomain =
   172	    hostname.includes("tax.balizero") || hostname === TAX_DOMAIN;
   173	  const isPublicDomain =
   174	    hostname.includes(PUBLIC_DOMAIN) &&
   175	    !hostname.includes("kita") &&
   176	    !hostname.includes("my") &&
   177	    !hostname.includes("visa") &&
   178	    !hostname.includes("tax") &&
   179	    !isSSOSubdomain &&
   180	    subdomain !== "prime";
   181	  const isAppDomain =
   182	    hostname.includes(APP_DOMAIN) ||
   183	    (hostname.includes("kita") && !hostname.includes("my")) ||
   184	    isSSOSubdomain ||
   185	    subdomain === "prime";
   186	  const isPortalDomain =
   187	    hostname.includes(PORTAL_DOMAIN) || hostname.includes("my.balizero.com");
   188	
   189	  // Development and Fly.dev: allow all routes (public-facing)
   190	  const isDevelopment =
   191	    hostname.includes("localhost") || hostname.includes("127.0.0.1");
   192	  const isFlyDev = hostname.includes("fly.dev");
   193	
   194	  if (isDevelopment || isFlyDev) {
   195	    return response;
   196	  }
   197	
   198	  // === PORTAL DOMAIN (my.balizero.com) ===
   199	  if (isPortalDomain) {
   200	    // Portal domain: only allow /portal/* routes
   201	    if (pathname.startsWith("/portal")) {
   202	      // Allow portal routes
   203	      return response;
   204	    }
   205	
   206	    // Redirect root to portal login
   207	    if (pathname === "/") {
   208	      const redirectResponse = NextResponse.redirect(
   209	        new URL("/portal/login", request.url),
   210	      );
   211	      redirectResponse.headers.set("x-pathname", pathname);
   212	      return redirectResponse;
   213	    }
   214	
   215	    // Redirect non-portal routes to public domain (with RSC/prefetch protection)
   216	    const publicUrl = new URL(pathname, `https://${PUBLIC_DOMAIN}`);
   217	    publicUrl.search = request.nextUrl.search;
   218	    return crossOriginRedirect(request, publicUrl);
   219	  }
   220	
   221	  // === ASSESSMENT DOMAIN (subhi.balizero.com) ===
   222	  // Temporary assessment page for candidate — rewrites to /assessment/*
   223	  if (
   224	    hostname === ASSESSMENT_DOMAIN ||
   225	    hostname === `www.${ASSESSMENT_DOMAIN}`
   226	  ) {
   227	    const rewriteUrl = request.nextUrl.clone();
   228	    if (pathname === "/" || pathname === "") {
   229	      rewriteUrl.pathname = "/assessment";
   230	    } else if (!pathname.startsWith("/assessment")) {
   231	      rewriteUrl.pathname = `/assessment${pathname}`;
   232	    }
   233	    const rewriteResponse = NextResponse.rewrite(rewriteUrl);
   234	    rewriteResponse.headers.set("x-pathname", pathname);
   235	    rewriteResponse.headers.set("X-Robots-Tag", "noindex, nofollow");
   236	    return rewriteResponse;
   237	  }
   238	
   239	  // === VISA DOMAIN (visa.balizero.com) ===
   240	  // Dedicated Visa Oracle webapp — rewrites all paths to /visa-oracle/* prefix.

 succeeded in 0ms:
6-     6	Result: /api/experience, /api/skill, /api/metabolic silently 404'd in prod.
7-     7	
8-     8	This manifest makes it structurally impossible to repeat that mistake.
9:     9	Each router is declared ONCE with its process_groups. The include_*
10-    10	functions read this manifest instead of maintaining separate import lists.
11-    11	
12-    12	HOW TO ADD A NEW ROUTER:
13-    13	  1. Create your router file in backend/app/routers/
14-    14	  2. Add a RouterEntry below (alphabetical order)
15:    15	  3. Set process_groups: {"api"} for light, {"rag"} for heavy, {"api","rag"} for both
16-    16	  4. Run: PYTHONPATH=. pytest backend/tests/setup/ -q
17-    17	  5. Done. No other file needs editing.
18-    18	"""
--
30-    30	    Attributes:
31-    31	        name: Module name under backend.app.routers (e.g. "auth").
32-    32	              For module routers, use dotted path (e.g. "modules.identity").
33:    33	        process_groups: Which Fly.io processes include this router.
34-    34	                       "api" = main_api (light, public HTTP)
35-    35	                       "rag" = main_rag (heavy, internal RAG)
36-    36	        attr: Attribute name on the imported module (default "router").
--
44-    44	    """
45-    45	
46-    46	    name: str
47:    47	    process_groups: frozenset[str]
48-    48	    attr: str = "router"
49-    49	    prefix: str | None = None
50-    50	    condition: Callable[[], bool] | None = None
--
58-    58	# Shorthand constants for readability
59-    59	_API = frozenset({"api"})
60-    60	_RAG = frozenset({"rag"})
61:    61	_BOTH = frozenset({"api", "rag"})
62-    62	
63-    63	
64-    64	def _is_debug_enabled() -> bool:
--
77-    77	# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
78-    78	#
79-    79	# Alphabetical order. One entry per router attribute.
80:    80	# process_groups: _API (light/public), _RAG (heavy/internal), _BOTH
81-    81	#
82-    82	# To add a new router: insert one RouterEntry, run tests. Done.
83-    83	# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
84-    84	
85-    85	ROUTER_MANIFEST: tuple[RouterEntry, ...] = (
86-    86	    # ── Admin ──
87:    87	    RouterEntry(name="admin_conversation_cleanup", process_groups=_API, tags=("admin",)),
88:    88	    RouterEntry(name="admin_drive_auth",           process_groups=_API, tags=("admin", "drive")),
89:    89	    RouterEntry(name="admin_drive_health",         process_groups=_API, tags=("admin", "drive")),
90:    90	    RouterEntry(name="admin_drive_refresh",        process_groups=_API, tags=("admin", "drive")),
91:    91	    RouterEntry(name="admin_drive_setup",          process_groups=_API, tags=("admin", "drive")),
92:    92	    RouterEntry(name="admin_logs",                 process_groups=_API, tags=("admin",)),
93:    93	    RouterEntry(name="admin_practice_auto_create", process_groups=_API, tags=("admin",)),
94:    94	    RouterEntry(name="admin_team_activity",        process_groups=_API, tags=("admin",)),
95:    95	    RouterEntry(name="admin_zoho_auth",            process_groups=_API, tags=("admin", "integrations")),
96-    96	
97-    97	    # ── Agent / AI ──
98:    98	    RouterEntry(name="agent",                process_groups=_RAG, tags=("agent",)),
99:    99	    RouterEntry(name="agents",               process_groups=_RAG, tags=("agent",)),
100:   100	    RouterEntry(name="agentic_rag",          process_groups=_RAG, tags=("agent", "rag")),
101:   101	    RouterEntry(name="autonomous_agents",    process_groups=_RAG, tags=("agent",)),
102:   102	    RouterEntry(name="autonomous_execution", process_groups=_RAG, tags=("agent",)),
103-   103	
104-   104	    # ── Analytics ──
105:   105	    RouterEntry(name="analytics",          process_groups=_API, tags=("analytics",)),
106:   106	    RouterEntry(name="article_composer",   process_groups=_API, tags=("blog",)),
107-   107	
108-   108	    # ── Auth / Core ──
109:   109	    RouterEntry(name="auth",     process_groups=_API, tags=("core",)),
110:   110	    RouterEntry(name="blog_ask", process_groups=_RAG, tags=("blog", "rag")),
111-   111	
112-   112	    # ── Bridge ──
113:   113	    RouterEntry(name="bridge", process_groups=_API, tags=("infra",)),
114-   114	
115-   115	    # ── CELL ──
116:   116	    RouterEntry(name="cell_status", process_groups=_API, tags=("cell",)),
117-   117	
118-   118	    # ── Channels ──
119:   119	    RouterEntry(name="channels",    process_groups=_API, tags=("channels",)),
120-   120	
121-   121	    # ── CRM ──
122:   122	    RouterEntry(name="crm_analytics",          process_groups=_API, tags=("crm",)),
123:   123	    RouterEntry(name="crm_clients",            process_groups=_RAG, tags=("crm", "rag")),
124:   124	    RouterEntry(name="crm_clients_documents",  process_groups=_API, tags=("crm",)),
125:   125	    RouterEntry(name="crm_company",            process_groups=_API, tags=("crm",)),
126:   126	    RouterEntry(name="crm_enhanced",           process_groups=_RAG, tags=("crm", "rag")),
127:   127	    RouterEntry(name="crm_enhanced_alerts",    process_groups=_API, tags=("crm",)),
128:   128	    RouterEntry(name="crm_enhanced_documents", process_groups=_API, tags=("crm",)),
129:   129	    RouterEntry(name="crm_interactions",       process_groups=_API, tags=("crm",)),
130:   130	    RouterEntry(name="crm_notifications",      process_groups=_API, tags=("crm",)),
131:   131	    RouterEntry(name="crm_portal_integration", process_groups=_API, tags=("crm", "portal")),
132:   132	    RouterEntry(name="crm_practices",          process_groups=_RAG, tags=("crm", "rag")),
133:   133	    RouterEntry(name="crm_shared_memory",      process_groups=_API, tags=("crm",)),
134-   134	
135-   135	    # ── Conversations / Memory ──
136:   136	    RouterEntry(name="collective_memory", process_groups=_RAG, tags=("memory",)),
137:   137	    RouterEntry(name="conversations",     process_groups=_RAG, tags=("memory",)),
138:   138	    RouterEntry(name="episodic_memory",   process_groups=_RAG, tags=("memory",)),
139-   139	
140-   140	    # ── Dashboard ──
141:   141	    RouterEntry(name="dashboard",                   process_groups=_RAG, tags=("dashboard",)),
142:   142	    RouterEntry(name="dashboard_featured_articles", process_groups=_RAG, tags=("dashboard",)),
143:   143	    RouterEntry(name="dashboard_summary",           process_groups=_RAG, tags=("dashboard",)),
144-   144	
145-   145	    # ── Debug (conditional) ──
146:   146	    RouterEntry(name="debug", attr="router",     process_groups=_API, condition=_is_debug_enabled, tags=("debug",)),
147:   147	    RouterEntry(name="debug", attr="v1_router",  process_groups=_API, condition=_is_debug_enabled, tags=("debug",)),
148-   148	
149-   149	    # ── Documents ──
150:   150	    RouterEntry(name="documents_proxy", process_groups=_API, tags=("integrations",)),
151-   151	
152-   152	    # ── Dream ──
153:   153	    RouterEntry(name="dream", process_groups=_RAG, tags=("module",)),
154-   154	
155-   155	    # ── Dynamic Pricing ──
156:   156	    RouterEntry(name="dynamic_pricing", process_groups=_RAG, tags=("pricing",)),
157-   157	
158-   158	    # ── EventBus ──
159:   159	    RouterEntry(name="event_bus", process_groups=_API, tags=("infra",)),
160-   160	
161-   161	    # ── Experience / Skill / Metabolic (SCAR: PR #54/#55/#60) ──
162-   162	    # These are LIGHT routers (SQLite local, no RAG deps) — must be in api group.
163-   163	    # Originally misclassified as rag-only, causing 404 in production.
164:   164	    RouterEntry(name="experience",       process_groups=_API, tags=("cell", "scar-pr54")),
165:   165	    RouterEntry(name="skill",            process_groups=_API, tags=("cell", "scar-pr55")),
166:   166	    RouterEntry(name="metabolic_health", process_groups=_API, tags=("cell", "scar-pr60")),
167-   167	
168-   168	    # ── Federation / Feedback ──
169:   169	    RouterEntry(name="federation", process_groups=_API, tags=("agent",)),
170:   170	    RouterEntry(name="feedback",   process_groups=_API, tags=("core",)),
171-   171	
172-   172	    # ── Funnel (cross-funnel lead tracking, pre-auth) ──
173:   173	    RouterEntry(name="funnel", process_groups=_API, tags=("funnel",)),
174-   174	
175-   175	    # ── Google Drive / Integrations ──
176:   176	    RouterEntry(name="google_drive", process_groups=_API, tags=("integrations",)),
177-   177	
178-   178	    # ── Core infra ──
179:   179	    RouterEntry(name="handlers", process_groups=_BOTH, tags=("core",)),
180:   180	    RouterEntry(name="health",   process_groups=_BOTH, tags=("core",)),
181-   181	
182-   182	    # ── HR ──
183:   183	    RouterEntry(name="hr",               process_groups=_API, tags=("hr",)),
184:   184	    RouterEntry(name="hr_late_reply",     process_groups=_API, tags=("hr",)),
185:   185	    RouterEntry(name="hr_owner_cashout",  process_groups=_API, tags=("hr",)),
186-   186	
187-   187	    # ── Image Generation ──
188:   188	    RouterEntry(name="image_generation", process_groups=_API, tags=("media",)),
189-   189	
190-   190	    # ── Ingestion ──
191:   191	    RouterEntry(name="ingest",       process_groups=_RAG, tags=("ingest",)),
192:   192	    RouterEntry(name="legal_ingest", process_groups=_RAG, tags=("ingest",)),
193:   193	    RouterEntry(name="oracle_ingest", process_groups=_RAG, tags=("ingest",)),
194-   194	
195-   195	    # ── Instagram ──
196:   196	    RouterEntry(name="instagram_chat", attr="router",         process_groups=_API, tags=("channels",)),
197:   197	    RouterEntry(name="instagram_chat", attr="webhook_router", process_groups=_API, tags=("channels",)),
198-   198	
199-   199	    # ── Intel (RAG process only — needs /data volume) ──
200:   200	    RouterEntry(name="intel",           process_groups=_RAG, tags=("intel",)),
201:   201	    RouterEntry(name="intel_analytics", process_groups=_RAG, tags=("intel",)),
202:   202	    RouterEntry(name="intel_scraper",   process_groups=_RAG, tags=("intel",)),
203-   203	
204-   204	    # ── KBLI ──
205:   205	    RouterEntry(name="kbli_notebook",      process_groups=_RAG, prefix="__API_V1__", tags=("kbli",)),
206:   206	    RouterEntry(name="kbli_notebook_chat", process_groups=_RAG, prefix="__API_V1__", tags=("kbli",)),
207-   207	
208-   208	    # ── KG ──
209:   209	    RouterEntry(name="kg_agentic", process_groups=_RAG, tags=("kg", "agent")),
210-   210	
211-   211	    # ── Knowledge ──
212:   212	    RouterEntry(name="knowledge_activity", process_groups=_API, tags=("knowledge",)),
213:   213	    RouterEntry(name="knowledge_visa",     process_groups=_RAG, tags=("knowledge",)),
214-   214	
215-   215	    # ── LAM Memory ──
216:   216	    RouterEntry(name="lam_memory", process_groups=_RAG, tags=("memory",)),
217-   217	
218-   218	    # ── Lead Capture (4-app homepage → WhatsApp handoff, shared infra) ──
219:   219	    RouterEntry(name="lead_capture", process_groups=_API, tags=("funnel", "lead")),
220-   220	
221-   221	    # ── Funnel Email (drip scheduler + unsubscribe for 4-app homepage) ──
222:   222	    RouterEntry(name="funnel_email", process_groups=_API, tags=("funnel", "email")),
223-   223	
224-   224	    # ── Compliance Alerts (outcome recording + autotune metrics) ──
225:   225	    RouterEntry(name="compliance_alerts", process_groups=_API, tags=("compliance",)),
226-   226	
227-   227	    # ── LKPM Compliance ──
228:   228	    RouterEntry(name="lkpm", process_groups=_API, tags=("compliance",)),
229-   229	
230-   230	    # ── LLM Cost Tracking (remote ingestion for Pro/Air cron agents) ──
231:   231	    RouterEntry(name="llm_costs", process_groups=_API, tags=("observability", "admin")),
232-   232	
233-   233	    # ── Media ──
234:   234	    RouterEntry(name="media", process_groups=_API, tags=("media",)),
235-   235	
236-   236	    # ── Messaging ──
237:   237	    RouterEntry(name="messaging_identity", process_groups=_API, tags=("channels",)),
238-   238	
239-   239	    # ── Monitoring ──
240:   240	    RouterEntry(name="monitoring_rag", process_groups=_RAG, tags=("monitoring",)),
241-   241	
242-   242	    # ── Naga (Deep Research) ──
243:   243	    RouterEntry(name="naga", process_groups=_RAG, tags=("research",)),
244-   244	
245-   245	    # ── Newsletter ──
246:   246	    RouterEntry(name="newsletter", process_groups=_API, tags=("blog",)),
247-   247	
248-   248	    # ── News ──
249:   249	    RouterEntry(name="news", process_groups=_RAG, tags=("intel",)),
250-   250	
251-   251	    # ── Nusantara Health ──
252:   252	    RouterEntry(name="nusantara_health", process_groups=_API, tags=("core",)),
253-   253	
254-   254	    # ── Olympus (full-only: internal admin) ──
255:   255	    RouterEntry(name="olympus", attr="internal_router", process_groups=_API, tags=("admin",)),
256-   256	
257-   257	    # ── Omnichannel ──
258:   258	    RouterEntry(name="omnichannel", process_groups=_API, tags=("channels",)),
259-   259	
260-   260	    # ── Oracle ──
261:   261	    RouterEntry(name="oracle_universal", process_groups=_RAG, tags=("oracle",)),
262-   262	
263-   263	    # ── Performance ──
264:   264	    RouterEntry(name="performance", process_groups=_API, tags=("analytics",)),
265-   265	
266-   266	    # ── Partners (CRM) ──
267:   267	    RouterEntry(name="partners", process_groups=_API, tags=("crm", "partners")),
268-   268	
269-   269	    # ── Portal ──
270:   270	    RouterEntry(name="portal",                  process_groups=_API, tags=("portal",)),
271:   271	    RouterEntry(name="portal_admin",            process_groups=_API, tags=("portal",)),
272:   272	    RouterEntry(name="portal_billing",          process_groups=_API, tags=("portal",)),
273:   273	    RouterEntry(name="portal_dashboard",        process_groups=_API, tags=("portal",)),
274:   274	    RouterEntry(name="portal_drive",            process_groups=_API, tags=("portal",)),
275:   275	    RouterEntry(name="portal_family",           process_groups=_API, tags=("portal",)),
276:   276	    RouterEntry(name="portal_matters",          process_groups=_API, tags=("portal",)),
277:   277	    RouterEntry(name="portal_invite",           process_groups=_API, tags=("portal",)),
278:   278	    RouterEntry(name="portal_notifications",    process_groups=_API, tags=("portal",)),
279:   279	    RouterEntry(name="portal_notification_prefs", process_groups=_API, tags=("portal",)),
280:   280	    RouterEntry(name="portal_process_timeline", process_groups=_API, tags=("portal",)),
281:   281	    RouterEntry(name="portal_taxes",            process_groups=_API, tags=("portal",)),
282:   282	    RouterEntry(name="portal_visa",             process_groups=_API, tags=("portal",)),
283-   283	
284-   284	    # ── Preview ──
285:   285	    RouterEntry(name="preview", process_groups=_API, tags=("blog",)),
286-   286	
287-   287	    # ── Prime ──
288:   288	    RouterEntry(name="prime",    process_groups=_API, tags=("prime",)),
289:   289	    RouterEntry(name="prime_v2", process_groups=_API, tags=("prime",)),
290-   290	
291-   291	    # ── Query Analytics ──
292:   292	    RouterEntry(name="query_analytics", process_groups=_API, tags=("analytics",)),
293-   293	
294-   294	    # ── Session ──
295:   295	    RouterEntry(name="session", process_groups=_API, tags=("core",)),
296-   296	
297-   297	    # ── Sheets ──
298:   298	    RouterEntry(name="sheets", process_groups=_API, tags=("integrations",)),
299-   299	
300-   300	    # ── Team ──
301:   301	    RouterEntry(name="team",           process_groups=_API, tags=("team",)),
302:   302	    RouterEntry(name="team_activity",  process_groups=_API, tags=("team",)),
303:   303	    RouterEntry(name="team_analytics", process_groups=_API, tags=("team",)),
304:   304	    RouterEntry(name="team_drive",     process_groups=_API, tags=("team", "integrations")),
305-   305	
306-   306	    # ── Telegram ──
307:   307	    RouterEntry(name="telegram",         process_groups=_API, tags=("channels",)),
308:   308	    RouterEntry(name="telegram_webhook", process_groups=_API, tags=("channels",)),
309-   309	
310-   310	    # ── Visa Check (homepage 4-app — Clock + Match branches) ──
311:   311	    RouterEntry(name="visa_check", process_groups=_API, tags=("visa", "funnel")),
312-   312	
313-   313	    # ── Visa Oracle (public — prefix override) ──
314:   314	    RouterEntry(name="visa_oracle", process_groups=_API, prefix="__API_V1__", tags=("visa",)),
315-   315	
316-   316	    # ── Voice ──
317:   317	    RouterEntry(name="voice", process_groups=_RAG, tags=("media",)),
318-   318	
319-   319	    # ── War Room Dashboard (Sprint 11 — metrics aggregate queries) ──
320-   320	    RouterEntry(
321-   321	        name="war_room_dashboard",
322:   322	        process_groups=_API,
323-   323	        tags=("war-room", "admin"),
324-   324	    ),
325-   325	
326-   326	    # ── Webhooks ──
327:   327	    RouterEntry(name="webhooks", process_groups=_API, tags=("channels",)),
328-   328	
329-   329	    # ── WebSocket ──
330:   330	    RouterEntry(name="websocket", process_groups=_API, tags=("channels",)),
331-   331	
332-   332	    # ── WhatsApp ──
333:   333	    RouterEntry(name="whatsapp_chat",          process_groups=_RAG, tags=("channels", "rag")),
334:   334	    RouterEntry(name="whatsapp_conversations", process_groups=_API, tags=("channels",)),
335-   335	
336-   336	    # ── Workflow ──
337:   337	    RouterEntry(name="workflow_analytics", process_groups=_API, tags=("analytics",)),
338:   338	    RouterEntry(name="workflow_queue",     process_groups=_API, tags=("infra",)),
339-   339	
340-   340	    # ── Workspace (kita team ops) ──
341:   341	    RouterEntry(name="workspace_inbox",     process_groups=_API, tags=("workspace",)),
342:   342	    RouterEntry(name="workspace_analytics", process_groups=_API, tags=("workspace", "analytics")),
343-   343	
344-   344	    # ── Zoho ──
345:   345	    RouterEntry(name="zoho_email", process_groups=_API, tags=("integrations",)),
346-   346	
347-   347	    # ── Module routers (not in backend.app.routers) ──
348-   348	    RouterEntry(
349-   349	        name="identity",
350:   350	        process_groups=_RAG,
351-   351	        prefix="/api/auth",
352-   352	        import_path="backend.app.modules.identity.router",
353-   353	        tags=("module", "auth"),
354-   354	    ),
355-   355	    RouterEntry(
356-   356	        name="knowledge",
357:   357	        process_groups=_RAG,
358-   358	        import_path="backend.app.modules.knowledge.router",
359-   359	        tags=("module", "rag"),
360-   360	    ),
361-   361	    RouterEntry(
362-   362	        name="notifications",
363:   363	        process_groups=_API,
364-   364	        import_path="backend.app.modules.notifications.router",
365-   365	        tags=("module",),
366-   366	    ),
367-   367	    RouterEntry(
368-   368	        name="cron_notifiers",
369:   369	        process_groups=_API,
370-   370	        import_path="backend.app.routers.cron_notifiers",
371-   371	        tags=("cron",),
372-   372	    ),
--
395-   395	        raise ValueError(
396-   396	            f"Unknown process group '{group}'. Valid: {sorted(PROCESS_GROUPS)}"
397-   397	        )
398:   398	    return tuple(r for r in ROUTER_MANIFEST if group in r.process_groups)
399-   399	
400-   400	
401-   401	def all_router_names() -> frozenset[str]:
--
409-   409	
410-   410	    # Check process groups are valid
411-   411	    for entry in ROUTER_MANIFEST:
412:   412	        invalid = entry.process_groups - PROCESS_GROUPS
413-   413	        if invalid:
414-   414	            errors.append(
415:   415	                f"Router '{entry.name}' has invalid process_groups: {invalid}"
416-   416	            )
417:   417	        if not entry.process_groups:
418:   418	            errors.append(f"Router '{entry.name}' has empty process_groups")
419-   419	
420-   420	    # Check for duplicate (name, attr) pairs
421-   421	    seen: set[tuple[str, str]] = set()

exec
/bin/zsh -lc "nl -ba apps/mouth/src/lib/api/partners/partners.ts | sed -n '1,280p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
     1	/**
     2	 * Partners API client module
     3	 * Spec §7.1 — CRM Partners Module
     4	 * Uses the centralized api client for auth token management.
     5	 */
     6	
     7	import { api } from '@/lib/api';
     8	
     9	// ─── TypeScript Interfaces ─────────────────────────────────────────────────
    10	
    11	export type PartnerStatus = 'pending_review' | 'active' | 'inactive' | 'suspended';
    12	export type EntityType = "individual" | "corporate_pt" | "corporate_cv" | "foreign";
    13	export type CommissionTier = 'bronze' | 'silver' | 'gold' | 'platinum';
    14	export type TaxWithholdingCategory = 'tbd' | 'withheld_tarif_umum' | 'withheld_tarif_final' | 'exempt';
    15	export type CommissionStatus =
    16	  | 'accrued'           // from commission engine FSM
    17	  | 'pending_approval'
    18	  | 'approved'
    19	  | 'ready_to_pay'
    20	  | 'paid'
    21	  | 'clawback_pending'
    22	  | 'offset_applied'    // from commission engine FSM
    23	  | 'clawed_back'
    24	  | 'waived'
    25	  | 'repaid';           // from commission engine FSM
    26	
    27	export interface Partner {
    28	  id: number;
    29	  full_name: string;
    30	  email: string;
    31	  entity_type: EntityType;
    32	  phone?: string;
    33	  whatsapp?: string;
    34	  nationality?: string;
    35	  tax_id?: string;           // NPWP
    36	  company_name?: string;
    37	  work_role?: string;
    38	  onboarding_status: PartnerStatus;
    39	  commission_tier: CommissionTier;
    40	  commission_rate_override?: number;
    41	  payment_method?: string;
    42	  bank_name?: string;
    43	  bank_account_number?: string;
    44	  bank_account_name?: string;
    45	  tax_withholding_category: TaxWithholdingCategory;
    46	  pdp_consent: boolean;
    47	  pdp_consent_at?: string;
    48	  assigned_to?: string;
    49	  welcome_email_sent_at?: string;
    50	  notes?: string;
    51	  created_at: string;
    52	  updated_at?: string;
    53	  referral_count?: number;
    54	  total_earned?: number;
    55	}
    56	
    57	export interface PartnerReferral {
    58	  id: number;
    59	  partner_id: number;
    60	  referred_client_id?: number;
    61	  referred_client_name?: string;      // kept for backward-compat with team-side endpoints
    62	  client_display?: string;            // from /api/partners/me/referrals (sterilized name)
    63	  referred_practice_id?: number;
    64	  process_id?: number;
    65	  process_status?: string;            // from /me/referrals
    66	  practice_type_name?: string;
    67	  service_type?: string;              // from /me/referrals
    68	  status: string;
    69	  commission_amount?: number;
    70	  commission_status: CommissionStatus;
    71	  created_at: string;
    72	  referred_at?: string;               // /me/referrals uses this instead of created_at
    73	}
    74	
    75	export interface PartnerCommission {
    76	  id: number;
    77	  partner_id: number;
    78	  partner_name?: string;
    79	  referral_id?: number;
    80	  practice_id?: number;
    81	  practice_type_name?: string;
    82	  client_name?: string;
    83	  gross_amount: number;
    84	  withholding_amount: number;
    85	  net_amount: number;
    86	  status: CommissionStatus;
    87	  approved_by?: string;
    88	  approved_at?: string;
    89	  paid_at?: string;
    90	  payment_reference?: string;
    91	  clawback_reason?: string;
    92	  waive_reason?: string;
    93	  created_at: string;
    94	  updated_at?: string;
    95	}
    96	
    97	export interface PartnerListResponse {
    98	  partners: Partner[];
    99	  total: number;
   100	  page: number;
   101	  page_size: number;
   102	}
   103	
   104	export interface PartnerFilters {
   105	  status?: string;
   106	  assigned_to?: string;
   107	  orphaned?: boolean;
   108	  search?: string;
   109	  page?: number;
   110	  page_size?: number;
   111	}
   112	
   113	export interface CreatePartnerBody {
   114	  full_name: string;
   115	  email: string;
   116	  entity_type: EntityType;
   117	  phone?: string;
   118	  whatsapp?: string;
   119	  nationality?: string;
   120	  tax_id?: string;
   121	  company_name?: string;
   122	  work_role?: string;
   123	  commission_tier?: CommissionTier;
   124	  commission_rate_override?: number;
   125	  payment_method?: string;
   126	  bank_name?: string;
   127	  bank_account_number?: string;
   128	  bank_account_name?: string;
   129	  tax_withholding_category?: TaxWithholdingCategory;
   130	  pdp_consent: boolean;
   131	  assigned_to?: string;
   132	  notes?: string;
   133	}
   134	
   135	export interface UpdatePartnerBody {
   136	  full_name?: string;
   137	  phone?: string;
   138	  whatsapp?: string;
   139	  nationality?: string;
   140	  tax_id?: string;
   141	  company_name?: string;
   142	  work_role?: string;
   143	  commission_tier?: CommissionTier;
   144	  commission_rate_override?: number;
   145	  payment_method?: string;
   146	  bank_name?: string;
   147	  bank_account_number?: string;
   148	  bank_account_name?: string;
   149	  tax_withholding_category?: TaxWithholdingCategory;
   150	  notes?: string;
   151	}
   152	
   153	export interface ReassignBody {
   154	  new_user_id: string;
   155	  reason: string;
   156	}
   157	
   158	export interface BulkReassignBody {
   159	  partner_ids: number[];
   160	  new_user_id: string;
   161	  reason: string;
   162	}
   163	
   164	export interface CreateReferralBody {
   165	  process_id: number;
   166	  notes?: string;
   167	}
   168	
   169	export interface AuditLogEntry {
   170	  id: string;
   171	  partner_id: string;
   172	  actor_user_id: string | null;
   173	  action: string;
   174	  before_json: Record<string, unknown> | null;
   175	  after_json: Record<string, unknown> | null;
   176	  reason: string | null;
   177	  at: string;
   178	}
   179	
   180	export interface MarkPaidBody {
   181	  payment_reference?: string;
   182	  paid_at?: string;
   183	}
   184	
   185	export interface ClawbackBody {
   186	  reason: string;
   187	}
   188	
   189	export interface WaiveBody {
   190	  reason: string;
   191	}
   192	
   193	// ─── Query String Helper ────────────────────────────────────────────────────
   194	
   195	function qs(params?: Record<string, string | number | boolean | null | undefined>): string {
   196	  if (!params) return '';
   197	  const entries = Object.entries(params).filter(
   198	    (entry): entry is [string, string | number | boolean] => entry[1] != null,
   199	  );
   200	  return entries.length
   201	    ? '?' + new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString()
   202	    : '';
   203	}
   204	
   205	const BASE = '/api/partners';
   206	
   207	// ─── API Functions ──────────────────────────────────────────────────────────
   208	
   209	/** List partners with optional filters */
   210	export const listPartners = (filters?: PartnerFilters) =>
   211	  api.get<PartnerListResponse>(`${BASE}${qs(filters as Record<string, string | number | boolean | null | undefined>)}`);
   212	
   213	/** Create a new partner */
   214	export const createPartner = (body: CreatePartnerBody) =>
   215	  api.post<Partner>(`${BASE}`, body);
   216	
   217	/** Get a single partner by ID */
   218	export const getPartner = (id: number) =>
   219	  api.get<Partner>(`${BASE}/${id}`);
   220	
   221	/** Update partner profile fields (excludes onboarding_status, assigned_to, welcome_email_sent_at) */
   222	export const updatePartner = (id: number, body: UpdatePartnerBody) =>
   223	  api.patch<Partner>(`${BASE}/${id}`, body);
   224	
   225	/** Activate a partner (set onboarding_status → active, triggers welcome email) */
   226	export const activatePartner = (id: number) =>
   227	  api.post<{ success: boolean; partner: Partner }>(`${BASE}/${id}/activate`, {});
   228	
   229	/** Deactivate a partner */
   230	export const deactivatePartner = (id: number) =>
   231	  api.post<{ success: boolean }>(`${BASE}/${id}/deactivate`, {});
   232	
   233	/** Suspend a partner */
   234	export const suspendPartner = (id: number, reason?: string) =>
   235	  api.post<{ success: boolean }>(`${BASE}/${id}/suspend`, { reason });
   236	
   237	/** Reassign a partner to a different team member */
   238	export const reassignPartner = (id: number, body: ReassignBody) =>
   239	  api.post<{ success: boolean }>(`${BASE}/${id}/reassign`, body);
   240	
   241	/** Bulk reassign multiple orphaned partners */
   242	export const bulkReassign = (body: BulkReassignBody) =>
   243	  api.post<{ success: boolean; updated_count: number }>(`${BASE}/bulk-reassign`, body);
   244	
   245	/** Resend welcome email to a partner */
   246	export const resendWelcomeEmail = (id: number) =>
   247	  api.post<{ success: boolean }>(`${BASE}/${id}/resend-welcome`, {});
   248	
   249	/** Create a referral for a partner (links a process to a partner) */
   250	export const createReferral = (partnerId: number, body: CreateReferralBody) =>
   251	  api.post<PartnerReferral>(`${BASE}/${partnerId}/referrals`, body);
   252	
   253	/** List referrals for a specific partner */
   254	export const listReferrals = (partnerId: number, params?: Record<string, string | number | null | undefined>) =>
   255	  api.get<{ referrals: PartnerReferral[]; total: number }>(`${BASE}/${partnerId}/referrals${qs(params)}`);
   256	
   257	/** List commissions for a specific partner */
   258	export const listCommissions = (partnerId: number, params?: Record<string, string | number | null | undefined>) =>
   259	  api.get<{ commissions: PartnerCommission[]; total: number }>(`${BASE}/${partnerId}/commissions${qs(params)}`);
   260	
   261	/** List orphaned partners (assigned_to is null or empty) */
   262	export const listOrphanedPartners = () =>
   263	  api.get<{ partners: Partner[]; total: number }>(`${BASE}/orphaned`);
   264	
   265	/** List all commissions for admin finance queue */
   266	export const listAllCommissions = (params?: Record<string, string | number | null | undefined>) =>
   267	  api.get<{ commissions: PartnerCommission[]; total: number; summary: Record<string, number> }>(`${BASE}/commissions${qs(params)}`);
   268	
   269	/** Approve a commission */
   270	export const approveCommission = (id: number) =>
   271	  api.post<{ success: boolean; commission: PartnerCommission }>(`/api/partner-commissions/${id}/approve`, {});
   272	
   273	/** Mark a commission as paid */
   274	export const markPaid = (id: number, body: MarkPaidBody) =>
   275	  api.post<{ success: boolean; commission: PartnerCommission }>(`/api/partner-commissions/${id}/mark-paid`, body);
   276	
   277	/** Clawback a commission */
   278	export const clawback = (id: number, body: ClawbackBody) =>
   279	  api.post<{ success: boolean; commission: PartnerCommission }>(`/api/partner-commissions/${id}/clawback`, body);
   280	

exec
/bin/zsh -lc "rg -n \"partner|partners|role|portal/partner|portal/partners\" apps/mouth/src/middleware.ts apps/mouth/src/app -g '*.tsx' -g '*.ts'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
apps/mouth/src/app/login/page.tsx:62:          userRole: loginResponse.user?.role,
apps/mouth/src/app/login/page.tsx:78:      // Get redirect path: honour ?redirect= param (SSO subdomains), else role-based
apps/mouth/src/app/login/page.tsx:83:        : loginResponse.user?.role === "client"
apps/mouth/src/app/login/page.tsx:89:        metadata: { redirectTo, userRole: loginResponse.user?.role },
apps/mouth/src/app/v2/company/about/page.tsx:23:    role: "CEO · Founder",
apps/mouth/src/app/v2/company/about/page.tsx:29:    role: "Komisaris · Founder",
apps/mouth/src/app/v2/company/about/page.tsx:35:    role: "Board Member",
apps/mouth/src/app/v2/company/about/page.tsx:41:    role: "Setup Lead",
apps/mouth/src/app/v2/company/about/page.tsx:47:    role: "Accountant",
apps/mouth/src/app/v2/company/about/page.tsx:120:              friends for 30 years, partners in business — decided that expats
apps/mouth/src/app/v2/company/about/page.tsx:222:                    {m.role}
apps/mouth/src/app/kbli-explorer/page.tsx:174:      role="button"
apps/mouth/src/app/kbli-explorer/page.tsx:256:  role,
apps/mouth/src/app/kbli-explorer/page.tsx:259:  role: "user" | "ai";
apps/mouth/src/app/kbli-explorer/page.tsx:265:    className={`flex gap-4 md:gap-6 ${role === "ai" ? "items-start" : "items-center flex-row-reverse"}`}
apps/mouth/src/app/kbli-explorer/page.tsx:268:      className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 border ${role === "ai" ? "bg-surface-deep border-accent-sand/20 text-accent-sand" : "bg-surface-editorial-elevated border-white/10 text-slate-400"}`}
apps/mouth/src/app/kbli-explorer/page.tsx:270:      {role === "ai" ? (
apps/mouth/src/app/kbli-explorer/page.tsx:277:      className={`max-w-[90%] md:max-w-[85%] ${role === "ai" ? "text-base md:text-lg font-light leading-relaxed" : "text-sm md:text-base font-medium text-white/90"}`}
apps/mouth/src/app/kbli-explorer/page.tsx:402:  role: "user" | "ai";
apps/mouth/src/app/kbli-explorer/page.tsx:1016:      setMessages((prev) => [...prev, { role: "user", content: text }]);
apps/mouth/src/app/kbli-explorer/page.tsx:1024:            role: "ai",
apps/mouth/src/app/kbli-explorer/page.tsx:1361:                        role={msg.role}
apps/mouth/src/app/kbli-explorer/page.tsx:1363:                          msg.role === "user" ? (
apps/mouth/src/app/kbli-explorer/components/BlackBookModal.tsx:61:          role="dialog"
apps/mouth/src/app/v2/_components/HeroCarousel.tsx:251:            role="img"
apps/mouth/src/app/chat/stream-helper.ts:19:  const lastUserMessage = messages.filter((m) => m.role === "user").pop();
apps/mouth/src/app/chat/stream-helper.ts:36:      role: m.role,
apps/mouth/src/app/portal/(authenticated)/company/[id]/page.tsx:163:  // Editorial components (PeopleColumn) want `associates: {client_name, role, ownership_percentage}[]`.
apps/mouth/src/app/portal/(authenticated)/company/[id]/page.tsx:173:    role: string;
apps/mouth/src/app/portal/(authenticated)/company/[id]/page.tsx:178:      role: "Director",
apps/mouth/src/app/portal/(authenticated)/company/[id]/page.tsx:182:      role: "Shareholder",
apps/mouth/src/app/(blog)/team/page.tsx:21:  role: string;
apps/mouth/src/app/(blog)/team/page.tsx:30:    role: "Komisaris · Founder (30 years)",
apps/mouth/src/app/(blog)/team/page.tsx:37:    role: "Chief Executive Officer · Founder",
apps/mouth/src/app/(blog)/team/page.tsx:44:    role: "Special Advisory",
apps/mouth/src/app/(blog)/team/page.tsx:51:    role: "Manager",
apps/mouth/src/app/(blog)/team/page.tsx:60:    role: "Supervisor · Lead Setup",
apps/mouth/src/app/(blog)/team/page.tsx:67:    role: "Supervisor",
apps/mouth/src/app/(blog)/team/page.tsx:74:    role: "Specialist Consultant",
apps/mouth/src/app/(blog)/team/page.tsx:81:    role: "Executive Consultant",
apps/mouth/src/app/(blog)/team/page.tsx:88:    role: "Junior Consultant",
apps/mouth/src/app/(blog)/team/page.tsx:94:    role: "Executive Consultant",
apps/mouth/src/app/(blog)/team/page.tsx:104:    role: "Tax Supervisor",
apps/mouth/src/app/(blog)/team/page.tsx:110:    role: "Tax Consultant",
apps/mouth/src/app/(blog)/team/page.tsx:116:    role: "Tax Consultant",
apps/mouth/src/app/(blog)/team/page.tsx:122:    role: "Tax Care",
apps/mouth/src/app/(blog)/team/page.tsx:131:    role: "Accountant",
apps/mouth/src/app/(blog)/team/page.tsx:138:    role: "Reception",
apps/mouth/src/app/(blog)/team/page.tsx:147:    role: "SOTA Marketing",
apps/mouth/src/app/(blog)/team/page.tsx:154:    role: "Marketing Specialist",
apps/mouth/src/app/(blog)/team/page.tsx:160:    role: "Marketing Junior",
apps/mouth/src/app/(blog)/team/page.tsx:202:              alt={`${member.name} — ${member.role}`}
apps/mouth/src/app/(blog)/team/page.tsx:231:            {member.role}
apps/mouth/src/app/dream/page.tsx:750:      role="dialog"
apps/mouth/src/app/dream/page.tsx:754:      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" role="presentation" />
apps/mouth/src/app/dream/page.tsx:1287:                  role="status"
apps/mouth/src/app/kbli/[code]/page.tsx:813:                        ? `Yes. KBLI ${kbli.code} (${kbli.titleId}) is classified as TERBUKA — open to 100% foreign ownership through a PT PMA company. You do not need a local Indonesian partner.`
apps/mouth/src/app/kbli/[code]/page.tsx:815:                          ? `Partially. KBLI ${kbli.code} (${kbli.titleId}) is classified as TERBATAS — foreign ownership is capped at ${kbli.pma.maxForeign}%. You will need an Indonesian partner for the remaining shares.${kbli.pma.condition ? ` Condition: ${kbli.pma.condition}` : ""}`
apps/mouth/src/app/v2/_components/SocialProof.tsx:17:  role: string;
apps/mouth/src/app/v2/_components/SocialProof.tsx:25:// and still run it. Friends for 30 years, partners in the business.
apps/mouth/src/app/v2/_components/SocialProof.tsx:29:    role: "CEO",
apps/mouth/src/app/v2/_components/SocialProof.tsx:37:    role: "Komisaris",
apps/mouth/src/app/v2/_components/SocialProof.tsx:48:    role: "Special Advisory",
apps/mouth/src/app/v2/_components/SocialProof.tsx:56:    role: "Manager",
apps/mouth/src/app/v2/_components/SocialProof.tsx:63:    role: "Supervisor Lead",
apps/mouth/src/app/v2/_components/SocialProof.tsx:71:    role: "Supervisor",
apps/mouth/src/app/v2/_components/SocialProof.tsx:178:                  role="img"
apps/mouth/src/app/v2/_components/SocialProof.tsx:311:                      alt={`${f.name} — ${f.role}`}
apps/mouth/src/app/v2/_components/SocialProof.tsx:335:                      {f.role} · {f.department.replace("Founder · ", "")}
apps/mouth/src/app/v2/_components/SocialProof.tsx:397:                      {m.role} · {m.department}
apps/mouth/src/app/visa/match/page.tsx:253:        <p role="alert" style={{ color: "var(--color-error)", margin: 0 }}>
apps/mouth/src/app/(marketing)/page.v1-backup.tsx:1157:        <p class="footer-desc">Your trusted partner for business, immigration, and investment in Indonesia since 2020. Trusted by 5,000+ clients.</p>
apps/mouth/src/app/v2/_components/Footer.tsx:68:              Your trusted partner for business, immigration, and investment in
apps/mouth/src/app/chat/_components/ContextPanel.tsx:38:        <nav className="flex gap-1" role="tablist">
apps/mouth/src/app/chat/_components/ContextPanel.tsx:84:      role="tab"
apps/mouth/src/app/portal/(authenticated)/process/[practiceId]/page.tsx:52:            role="alert"
apps/mouth/src/app/chat/actions.ts:16:  role: "user" | "assistant";
apps/mouth/src/app/chat/actions.ts:89:            role: m.role,
apps/mouth/src/app/(blog)/[category]/[slug]/ArticleClient.tsx:309:                <p className="text-xs">{article.author.role}</p>
apps/mouth/src/app/(blog)/[category]/[slug]/ArticleClient.tsx:521:                      {article.author.role}
apps/mouth/src/app/(visa-oracle)/visa-oracle/result/page.tsx:91:          role="status"
apps/mouth/src/app/(workspace)/layout.tsx:29:    role: "",
apps/mouth/src/app/(workspace)/layout.tsx:49:          role: storedProfile.role || "Member",
apps/mouth/src/app/(workspace)/layout.tsx:64:        role: profile.role || "Member",
apps/mouth/src/app/(workspace)/layout.tsx:95:          if (profile?.role === "client") {
apps/mouth/src/app/(workspace)/layout.tsx:124:              role: "admin",
apps/mouth/src/app/(workspace)/process/page.tsx:230:        // Do NOT filter client-side — roles like "Founder" are admin on backend
apps/mouth/src/app/(workspace)/team/analytics/page.tsx:48:  role: string;
apps/mouth/src/app/portal/(authenticated)/layout.tsx:33:  // 500s for role=client — see commit history. Falls back to storedProfile name
apps/mouth/src/app/portal/(authenticated)/layout.tsx:187:                role: "client",
apps/mouth/src/app/portal/(authenticated)/layout.tsx:208:                    role: "client",
apps/mouth/src/app/(workspace)/admin/page.tsx:101:    // Check auth and admin role
apps/mouth/src/app/(workspace)/partners/page.tsx:22:import * as partnersApi from "@/lib/api/partners/partners";
apps/mouth/src/app/(workspace)/partners/page.tsx:23:import type { Partner, PartnerFilters } from "@/lib/api/partners/partners";
apps/mouth/src/app/(workspace)/partners/page.tsx:65:  const [partners, setPartners] = useState<Partner[]>([]);
apps/mouth/src/app/(workspace)/partners/page.tsx:93:      const data = await partnersApi.listPartners(cleanFilters);
apps/mouth/src/app/(workspace)/partners/page.tsx:94:      setPartners(data.partners);
apps/mouth/src/app/(workspace)/partners/page.tsx:97:      logger.error("Failed to load partners", { component: "PartnersPage" }, err as Error);
apps/mouth/src/app/(workspace)/partners/page.tsx:98:      setError("Failed to load partners. Please try again.");
apps/mouth/src/app/(workspace)/partners/page.tsx:99:      toastError("Failed to load partners");
apps/mouth/src/app/(workspace)/partners/page.tsx:143:            <p className="text-sm text-zinc-400">{total} partner{total !== 1 ? "s" : ""} total</p>
apps/mouth/src/app/(workspace)/partners/page.tsx:150:            onClick={() => router.push("/partners/orphaned")}
apps/mouth/src/app/(workspace)/partners/page.tsx:158:            onClick={() => router.push("/partners/finance")}
apps/mouth/src/app/(workspace)/partners/page.tsx:164:            onClick={() => router.push("/partners/new")}
apps/mouth/src/app/(workspace)/partners/page.tsx:261:      ) : partners.length === 0 ? (
apps/mouth/src/app/(workspace)/partners/page.tsx:264:          <p className="text-zinc-400">No partners found</p>
apps/mouth/src/app/(workspace)/partners/page.tsx:286:              {partners.map((partner) => (
apps/mouth/src/app/(workspace)/partners/page.tsx:288:                  key={partner.id}
apps/mouth/src/app/(workspace)/partners/page.tsx:289:                  onClick={() => router.push(`/partners/${partner.id}`)}
apps/mouth/src/app/(workspace)/partners/page.tsx:298:                        <div className="text-sm font-medium text-zinc-100">{partner.full_name}</div>
apps/mouth/src/app/(workspace)/partners/page.tsx:299:                        {partner.company_name && (
apps/mouth/src/app/(workspace)/partners/page.tsx:300:                          <div className="text-xs text-zinc-500">{partner.company_name}</div>
apps/mouth/src/app/(workspace)/partners/page.tsx:309:                        <span>{partner.email}</span>
apps/mouth/src/app/(workspace)/partners/page.tsx:311:                      {partner.phone && (
apps/mouth/src/app/(workspace)/partners/page.tsx:314:                          <span>{partner.phone}</span>
apps/mouth/src/app/(workspace)/partners/page.tsx:320:                    <StatusBadge status={partner.onboarding_status} />
apps/mouth/src/app/(workspace)/partners/page.tsx:323:                    <TierBadge tier={partner.commission_tier} />
apps/mouth/src/app/(workspace)/partners/page.tsx:327:                      {partner.assigned_to || <span className="text-zinc-600 italic">Unassigned</span>}
apps/mouth/src/app/(workspace)/partners/page.tsx:331:                    <span className="text-sm text-zinc-400">{partner.referral_count ?? 0}</span>
apps/mouth/src/app/portal/(authenticated)/companies/page.tsx:157:      role="button"
apps/mouth/src/app/portal/(authenticated)/partner/layout.tsx:4: * Partner role-gate layout.
apps/mouth/src/app/portal/(authenticated)/partner/layout.tsx:6: * Wraps all /portal/(authenticated)/partner/* pages.
apps/mouth/src/app/portal/(authenticated)/partner/layout.tsx:7: * On mount it calls /api/partners/me — the backend returns 403 for non-partner
apps/mouth/src/app/portal/(authenticated)/partner/layout.tsx:8: * roles and 200 for role=partner. This is the role-gate mechanism: if the call
apps/mouth/src/app/portal/(authenticated)/partner/layout.tsx:12: * JWT decode capability. The role-gate lives here instead (escalation
apps/mouth/src/app/portal/(authenticated)/partner/layout.tsx:14: * role boundary; the layout redirect is a UX guard only.
apps/mouth/src/app/portal/(authenticated)/partner/layout.tsx:19:import { getMe } from "@/lib/api/partners/partners";
apps/mouth/src/app/portal/(authenticated)/partner/layout.tsx:32:        // Confirmed partner role — allow rendering
apps/mouth/src/app/portal/(authenticated)/partner/layout.tsx:36:        // Non-partner or unauthenticated → redirect to main portal dashboard
apps/mouth/src/app/portal/(authenticated)/partner/referrals/page.tsx:4:import { getMyReferrals, type PartnerReferral } from "@/lib/api/partners/partners";
apps/mouth/src/app/(workspace)/settings/users/page.tsx:27:  role: string;
apps/mouth/src/app/(workspace)/settings/users/page.tsx:43:    role: 'user',
apps/mouth/src/app/(workspace)/settings/users/page.tsx:55:            role: u.email === 'zero@balizero.com' ? 'admin' : 'user',
apps/mouth/src/app/(workspace)/settings/users/page.tsx:67:            role: 'admin',
apps/mouth/src/app/(workspace)/settings/users/page.tsx:76:            role: 'user',
apps/mouth/src/app/(workspace)/settings/users/page.tsx:116:    setNewUser({ email: '', name: '', role: 'user', team: 'Team' });
apps/mouth/src/app/(workspace)/settings/users/page.tsx:170:            {users.filter((u) => u.role === 'admin').length}
apps/mouth/src/app/(workspace)/settings/users/page.tsx:227:                        user.role === 'admin'
apps/mouth/src/app/(workspace)/settings/users/page.tsx:233:                      {user.role}
apps/mouth/src/app/(workspace)/settings/users/page.tsx:304:                  value={newUser.role}
apps/mouth/src/app/(workspace)/settings/users/page.tsx:305:                  onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:4:import { getMe, type Partner } from "@/lib/api/partners/partners";
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:16:  const [partner, setPartner] = useState<Partner | null>(null);
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:31:  if (!partner) return <div className="p-6 text-gray-400">No profile data.</div>;
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:40:          <Field label="Full Name" value={partner.full_name} />
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:41:          <Field label="Email" value={partner.email} />
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:42:          <Field label="Phone" value={partner.phone} />
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:43:          <Field label="WhatsApp" value={partner.whatsapp} />
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:44:          <Field label="Nationality" value={partner.nationality} />
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:45:          <Field label="Entity Type" value={partner.entity_type} />
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:46:          <Field label="Company" value={partner.company_name} />
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:47:          <Field label="Work Role" value={partner.work_role} />
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:54:          <Field label="Status" value={partner.onboarding_status} />
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:55:          <Field label="Commission Tier" value={partner.commission_tier} />
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:56:          <Field label="Tax Withholding Category" value={partner.tax_withholding_category} />
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:57:          <Field label="Tax ID (NPWP)" value={partner.tax_id} />
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:58:          <Field label="PDP Consent" value={partner.pdp_consent ? "Yes" : "No"} />
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:59:          {partner.pdp_consent_at && (
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:62:              value={new Date(partner.pdp_consent_at).toLocaleDateString("id-ID")}
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:71:          <Field label="Payment Method" value={partner.payment_method} />
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:72:          <Field label="Bank Name" value={partner.bank_name} />
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:73:          <Field label="Account Holder" value={partner.bank_account_name} />
apps/mouth/src/app/portal/(authenticated)/partner/profile/page.tsx:74:          <Field label="Account Number" value={partner.bank_account_number} />
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:29:import * as partnersApi from "@/lib/api/partners/partners";
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:30:import type { Partner, PartnerReferral, PartnerCommission, AuditLogEntry } from "@/lib/api/partners/partners";
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:73:function ProfileTab({ partner }: { partner: Partner }) {
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:74:  const statusStyle = STATUS_STYLES[partner.onboarding_status] || STATUS_STYLES.inactive;
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:78:        <InfoRow label="Full Name" value={partner.full_name} />
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:79:        <InfoRow label="Email" value={<span className="flex items-center gap-1.5"><Mail size={12} className="text-zinc-500" />{partner.email}</span>} />
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:80:        <InfoRow label="Phone" value={partner.phone && <span className="flex items-center gap-1.5"><Phone size={12} className="text-zinc-500" />{partner.phone}</span>} />
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:81:        <InfoRow label="WhatsApp" value={partner.whatsapp} />
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:82:        <InfoRow label="Nationality" value={partner.nationality} />
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:83:        <InfoRow label="Company" value={partner.company_name} />
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:84:        <InfoRow label="Work Role" value={partner.work_role} />
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:90:        <InfoRow label="Commission Tier" value={<span className="capitalize">{partner.commission_tier}</span>} />
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:91:        <InfoRow label="Assigned To" value={partner.assigned_to} />
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:92:        <InfoRow label="PDP Consent" value={partner.pdp_consent ? (
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:97:        {partner.pdp_consent_at && <InfoRow label="Consent Date" value={new Date(partner.pdp_consent_at).toLocaleDateString()} />}
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:98:        <InfoRow label="Welcome Email" value={partner.welcome_email_sent_at ? new Date(partner.welcome_email_sent_at).toLocaleDateString() : "Not sent"} />
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:100:      {partner.notes && (
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:103:          <p className="text-sm text-zinc-300 whitespace-pre-wrap">{partner.notes}</p>
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:110:function FiscalTab({ partner }: { partner: Partner }) {
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:119:      <InfoRow label="NPWP (Tax ID)" value={partner.tax_id} />
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:120:      <InfoRow label="Withholding Category" value={taxLabels[partner.tax_withholding_category] || partner.tax_withholding_category} />
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:121:      {partner.commission_rate_override != null && (
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:122:        <InfoRow label="Rate Override" value={`${partner.commission_rate_override}%`} />
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:124:      {partner.total_earned != null && (
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:125:        <InfoRow label="Total Earned" value={formatIDR(partner.total_earned)} />
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:131:function PaymentTab({ partner }: { partner: Partner }) {
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:134:      <InfoRow label="Payment Method" value={partner.payment_method} />
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:135:      <InfoRow label="Bank Name" value={partner.bank_name} />
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:136:      <InfoRow label="Account Number" value={partner.bank_account_number} />
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:137:      <InfoRow label="Account Holder" value={partner.bank_account_name} />
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:142:function ReferralsTab({ partnerId }: { partnerId: number }) {
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:147:    partnersApi.listReferrals(partnerId)
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:151:  }, [partnerId]);
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:196:function CommissionsTab({ partnerId }: { partnerId: number }) {
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:201:    partnersApi.listCommissions(partnerId)
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:205:  }, [partnerId]);
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:250:function AuditTab({ partnerId }: { partnerId: number }) {
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:256:    partnersApi.listAuditLog(partnerId)
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:260:  }, [partnerId]);
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:309:  const partnerId = params?.id ? Number(params.id) : 0;
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:310:  const [partner, setPartner] = useState<Partner | null>(null);
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:320:      const data = await partnersApi.getPartner(partnerId);
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:323:      logger.error("Failed to load partner", { component: "PartnerDetailPage" }, err as Error);
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:324:      setError("Failed to load partner. Please try again.");
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:328:  }, [partnerId]);
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:333:    if (!partner) return;
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:336:      await partnersApi.activatePartner(partnerId);
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:340:      toastError("Failed to activate partner");
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:347:    if (!partner) return;
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:350:      await partnersApi.deactivatePartner(partnerId);
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:354:      toastError("Failed to deactivate partner");
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:367:      await partnersApi.reassignPartner(partnerId, {
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:374:      toastError("Failed to reassign partner");
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:388:  if (error || !partner) {
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:405:          <Link href="/partners">
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:412:            <h1 className="text-xl font-bold text-zinc-100">{partner.full_name}</h1>
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:413:            <p className="text-sm text-zinc-500">{partner.email}</p>
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:418:          {partner.onboarding_status === "pending_review" && (
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:429:          {partner.onboarding_status === "active" && (
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:456:            onClick={() => router.push(`/partners/${partnerId}/edit`)}
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:484:      {activeTab === "profile" && <ProfileTab partner={partner} />}
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:485:      {activeTab === "fiscal" && <FiscalTab partner={partner} />}
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:486:      {activeTab === "payment" && <PaymentTab partner={partner} />}
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:487:      {activeTab === "referrals" && <ReferralsTab partnerId={partnerId} />}
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:488:      {activeTab === "commissions" && <CommissionsTab partnerId={partnerId} />}
apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:489:      {activeTab === "audit" && <AuditTab partnerId={partnerId} />}
apps/mouth/src/app/(workspace)/settings/page.tsx:154:              description: "Configure roles and permissions",
apps/mouth/src/app/(workspace)/settings/page.tsx:185:                    router.push("/settings/roles");
apps/mouth/src/app/portal/(authenticated)/partner/commissions/page.tsx:8:} from "@/lib/api/partners/partners";
apps/mouth/src/app/portal/(authenticated)/partner/dashboard/page.tsx:11:} from "@/lib/api/partners/partners";
apps/mouth/src/app/portal/(authenticated)/partner/dashboard/page.tsx:23:  const [partner, setPartner] = useState<Partner | null>(null);
apps/mouth/src/app/portal/(authenticated)/partner/dashboard/page.tsx:65:        {partner && (
apps/mouth/src/app/portal/(authenticated)/partner/dashboard/page.tsx:67:            Welcome, {partner.full_name}
apps/mouth/src/app/(workspace)/settings/profile/page.tsx:193:                <span className="text-[var(--foreground)]">{profile?.role || 'N/A'}</span>
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:10:import * as partnersApi from "@/lib/api/partners/partners";
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:11:import type { Partner, UpdatePartnerBody, CommissionTier, TaxWithholdingCategory } from "@/lib/api/partners/partners";
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:28:  work_role: string;
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:71:function partnerToFormState(partner: Partner): EditFormState {
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:73:    full_name: partner.full_name,
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:74:    phone: partner.phone || "",
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:75:    whatsapp: partner.whatsapp || "",
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:76:    nationality: partner.nationality || "",
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:77:    company_name: partner.company_name || "",
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:78:    work_role: partner.work_role || "",
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:79:    tax_id: partner.tax_id || "",
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:80:    payment_method: partner.payment_method || "bank_transfer",
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:81:    bank_name: partner.bank_name || "",
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:82:    bank_account_number: partner.bank_account_number || "",
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:83:    bank_account_name: partner.bank_account_name || "",
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:84:    tax_withholding_category: partner.tax_withholding_category,
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:85:    commission_tier: partner.commission_tier,
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:86:    commission_rate_override: partner.commission_rate_override != null ? String(partner.commission_rate_override) : "",
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:87:    notes: partner.notes || "",
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:96:  const partnerId = params?.id ? Number(params.id) : 0;
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:97:  const [partner, setPartner] = useState<Partner | null>(null);
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:107:        const data = await partnersApi.getPartner(partnerId);
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:109:        setForm(partnerToFormState(data));
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:111:        logger.error("Failed to load partner for edit", { component: "EditPartnerPage" }, err as Error);
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:112:        setError("Failed to load partner data.");
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:118:  }, [partnerId]);
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:136:        work_role: form.work_role.trim() || undefined,
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:150:      await partnersApi.updatePartner(partnerId, body);
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:152:      router.push(`/partners/${partnerId}`);
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:154:      logger.error("Failed to update partner", { component: "EditPartnerPage" }, err as Error);
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:155:      toastError("Failed to update partner. Please try again.");
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:182:        <Link href={`/partners/${partnerId}`}>
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:190:          {partner && <p className="text-sm text-zinc-500">{partner.full_name}</p>}
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:233:                <Input value={form.work_role} onChange={(v) => setField("work_role", v)} placeholder="e.g. Real Estate Agent" />
apps/mouth/src/app/(workspace)/partners/[id]/edit/page.tsx:324:          <Link href={`/partners/${partnerId}`}>
apps/mouth/src/app/(workspace)/clients/page.tsx:384:      // assigned_to which the API may not always honour for all roles.
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:71:    description: 'Manage users, roles, integrations',
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:86:  const [roles, setRoles] = useState<Role[]>([
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:142:      setRoles(roles.map((r) => (r.id === editingRole.id ? editingRole : r)));
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:147:        toast.error('Missing name', { description: 'Please enter a role name.' });
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:150:      const role: Role = {
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:155:      setRoles([...roles, role]);
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:163:      toast.success('Role created', { description: `"${role.name}" has been created.` });
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:168:    toast('Delete this role?', {
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:171:        onClick: () => setRoles(roles.filter((r) => r.id !== id)),
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:201:              Configure roles and their permissions
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:213:        {roles.map((role) => (
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:215:            key={role.id}
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:222:                  style={{ backgroundColor: `${role.color}20` }}
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:224:                  <Shield className="w-5 h-5" style={{ color: role.color }} />
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:227:                  <h3 className="font-medium text-[var(--foreground)]">{role.name}</h3>
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:228:                  <p className="text-xs text-[var(--foreground-muted)]">{role.description}</p>
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:233:                  onClick={() => setEditingRole(role)}
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:238:                {role.name !== 'Admin' && (
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:240:                    onClick={() => deleteRole(role.id)}
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:252:                <span>{role.userCount} users</span>
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:256:                <span>{role.permissions.length} permissions</span>
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:262:                {role.permissions.slice(0, 4).map((permId) => {
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:273:                {role.permissions.length > 4 && (
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:275:                    +{role.permissions.length - 4} more
apps/mouth/src/app/(workspace)/settings/roles/page.tsx:371:                  placeholder="Brief description of this role"
apps/mouth/src/app/(workspace)/admin/team-activity/page.tsx:49:  role: string | null;
apps/mouth/src/app/(workspace)/admin/team-activity/page.tsx:65:  role: string | null;
apps/mouth/src/app/(workspace)/admin/team-activity/page.tsx:107:    role: '',
apps/mouth/src/app/(workspace)/admin/team-activity/page.tsx:151:        role: messageFilters.role || undefined,
apps/mouth/src/app/(workspace)/admin/team-activity/page.tsx:431:                            <td className="px-3 py-2">{member.role || '-'}</td>
apps/mouth/src/app/(workspace)/admin/team-activity/page.tsx:498:                    value={messageFilters.role}
apps/mouth/src/app/(workspace)/admin/team-activity/page.tsx:499:                    onChange={(e) => setMessageFilters((f) => ({ ...f, role: e.target.value }))}
apps/mouth/src/app/(workspace)/admin/team-activity/page.tsx:502:                    <option value="">All roles</option>
apps/mouth/src/app/(workspace)/admin/team-activity/page.tsx:529:                              msg.role === 'user'
apps/mouth/src/app/(workspace)/admin/team-activity/page.tsx:534:                            {msg.role}
apps/mouth/src/app/(workspace)/partners/finance/page.tsx:21:import * as partnersApi from "@/lib/api/partners/partners";
apps/mouth/src/app/(workspace)/partners/finance/page.tsx:22:import type { PartnerCommission } from "@/lib/api/partners/partners";
apps/mouth/src/app/(workspace)/partners/finance/page.tsx:65:        <div className="text-sm font-medium text-zinc-100">{c.partner_name || `Partner #${c.partner_id}`}</div>
apps/mouth/src/app/(workspace)/partners/finance/page.tsx:211:  // Admin gate — redirect non-admin users back to partners list
apps/mouth/src/app/(workspace)/partners/finance/page.tsx:214:      router.replace('/partners');
apps/mouth/src/app/(workspace)/partners/finance/page.tsx:222:      const data = await partnersApi.listAllCommissions({
apps/mouth/src/app/(workspace)/partners/finance/page.tsx:239:      await partnersApi.approveCommission(id);
apps/mouth/src/app/(workspace)/partners/finance/page.tsx:253:      await partnersApi.markPaid(id, { payment_reference: ref || undefined });
apps/mouth/src/app/(workspace)/partners/finance/page.tsx:268:      await partnersApi.clawback(id, { reason: reason.trim() });
apps/mouth/src/app/(workspace)/partners/finance/page.tsx:283:      await partnersApi.waive(id, { reason: reason.trim() });
apps/mouth/src/app/(workspace)/partners/finance/page.tsx:297:  const csvUrl = partnersApi.exportFinanceCsv();
apps/mouth/src/app/(workspace)/partners/finance/page.tsx:304:          <Link href="/partners">
apps/mouth/src/app/(workspace)/dashboard/page.tsx:23:import { normalizeDashboardRole } from '@/lib/dashboard-role';
apps/mouth/src/app/(workspace)/dashboard/page.tsx:24:import type { LiveActivityEvent } from '@/types/dashboard-role.types';
apps/mouth/src/app/(workspace)/dashboard/page.tsx:316:  const role = normalizeDashboardRole(user?.role, user?.is_admin ?? false);
apps/mouth/src/app/(workspace)/dashboard/page.tsx:635:              <RoleWidget role={role} userId={user?.email ?? ''} />
apps/mouth/src/app/(workspace)/process/new/page.tsx:23:import * as partnersApi from "@/lib/api/partners/partners";
apps/mouth/src/app/(workspace)/process/new/page.tsx:29:import { ReferrerDropdown } from "@/components/partners/ReferrerDropdown";
apps/mouth/src/app/(workspace)/process/new/page.tsx:366:          await partnersApi.createReferral(formData.referrer_id, {
apps/mouth/src/app/(workspace)/dashboard/__tests__/page.test.tsx:157:  RoleWidget: ({ role }: { role: string }) => (
apps/mouth/src/app/(workspace)/dashboard/__tests__/page.test.tsx:158:    <div data-testid="role-widget">{role}</div>
apps/mouth/src/app/(workspace)/dashboard/__tests__/page.test.tsx:180:      role: "team",
apps/mouth/src/app/(workspace)/dashboard/__tests__/page.test.tsx:290:          role: "admin",
apps/mouth/src/app/api/prime/chat/route.ts:32:  conversation_history?: { role: "user" | "assistant"; content: string }[];
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:11:import * as partnersApi from "@/lib/api/partners/partners";
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:12:import type { Partner } from "@/lib/api/partners/partners";
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:20:  const [partners, setPartners] = useState<Partner[]>([]);
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:29:  // Admin gate — redirect non-admin users back to partners list
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:32:      router.replace('/partners');
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:41:      const data = await partnersApi.listOrphanedPartners();
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:42:      setPartners(data.partners);
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:44:      logger.error("Failed to load orphaned partners", { component: "OrphanedPartnersPage" }, err as Error);
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:45:      setError("Failed to load orphaned partners.");
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:63:    if (selectedIds.size === partners.length) {
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:66:      setSelectedIds(new Set(partners.map((p) => p.id)));
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:76:      toastError("Please select at least one partner");
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:87:      const result = await partnersApi.bulkReassign({
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:88:        partner_ids: Array.from(selectedIds),
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:92:      toastSuccess(`${result.updated_count} partner${result.updated_count !== 1 ? "s" : ""} reassigned`);
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:103:  const allSelected = partners.length > 0 && selectedIds.size === partners.length;
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:109:        <Link href="/partners">
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:122:      {partners.length > 0 && (
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:126:              {selectedIds.size > 0 ? `${selectedIds.size} selected` : "Select partners to reassign"}
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:182:      ) : partners.length === 0 ? (
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:185:          <p className="text-zinc-400">No orphaned partners — all partners are assigned</p>
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:205:              {partners.map((partner) => (
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:207:                  key={partner.id}
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:208:                  className={`transition-colors ${selectedIds.has(partner.id) ? "bg-amber-500/5" : "hover:bg-zinc-800/30"}`}
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:211:                    <button onClick={() => toggleSelect(partner.id)} className="text-zinc-400 hover:text-zinc-200">
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:212:                      {selectedIds.has(partner.id)
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:218:                    <div className="text-sm font-medium text-zinc-100">{partner.full_name}</div>
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:219:                    {partner.company_name && <div className="text-xs text-zinc-500">{partner.company_name}</div>}
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:221:                  <td className="px-4 py-3 hidden md:table-cell text-sm text-zinc-400">{partner.email}</td>
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:224:                      {partner.onboarding_status.replace(/_/g, " ")}
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:228:                    {new Date(partner.created_at).toLocaleDateString()}
apps/mouth/src/app/(workspace)/partners/orphaned/page.tsx:234:                      onClick={() => router.push(`/partners/${partner.id}`)}
apps/mouth/src/app/(workspace)/partners/new/page.tsx:10:import * as partnersApi from "@/lib/api/partners/partners";
apps/mouth/src/app/(workspace)/partners/new/page.tsx:11:import type { CreatePartnerBody, CommissionTier, TaxWithholdingCategory, EntityType } from "@/lib/api/partners/partners";
apps/mouth/src/app/(workspace)/partners/new/page.tsx:14:// NB-2 guardrail: warn if work_role matches sponsor/guarantor patterns
apps/mouth/src/app/(workspace)/partners/new/page.tsx:34:  work_role: string;
apps/mouth/src/app/(workspace)/partners/new/page.tsx:56:  work_role: "",
apps/mouth/src/app/(workspace)/partners/new/page.tsx:149:    if (key === "work_role" && typeof value === "string") {
apps/mouth/src/app/(workspace)/partners/new/page.tsx:181:        work_role: form.work_role.trim() || undefined,
apps/mouth/src/app/(workspace)/partners/new/page.tsx:197:      const partner = await partnersApi.createPartner(body);
apps/mouth/src/app/(workspace)/partners/new/page.tsx:198:      toastSuccess(`Partner ${partner.full_name} created`);
apps/mouth/src/app/(workspace)/partners/new/page.tsx:199:      router.push(`/partners/${partner.id}`);
apps/mouth/src/app/(workspace)/partners/new/page.tsx:201:      logger.error("Failed to create partner", { component: "NewPartnerPage" }, err as Error);
apps/mouth/src/app/(workspace)/partners/new/page.tsx:204:        toastError("A partner with this email already exists");
apps/mouth/src/app/(workspace)/partners/new/page.tsx:208:        toastError("Failed to create partner. Please try again.");
apps/mouth/src/app/(workspace)/partners/new/page.tsx:219:        <Link href="/partners">
apps/mouth/src/app/(workspace)/partners/new/page.tsx:233:            <strong>Warning:</strong> The work role appears to indicate a sponsor/guarantor position.
apps/mouth/src/app/(workspace)/partners/new/page.tsx:234:            Please verify the partner{"'"}s role does not conflict with Indonesian immigration regulations
apps/mouth/src/app/(workspace)/partners/new/page.tsx:270:                    placeholder="partner@email.com"
apps/mouth/src/app/(workspace)/partners/new/page.tsx:316:                    value={form.work_role}
apps/mouth/src/app/(workspace)/partners/new/page.tsx:317:                    onChange={(v) => setField("work_role", v)}
apps/mouth/src/app/(workspace)/partners/new/page.tsx:339:                  placeholder="Internal notes about this partner..."
apps/mouth/src/app/(workspace)/partners/new/page.tsx:376:                the partner{"'"}s tax status before approving commissions.
apps/mouth/src/app/(workspace)/partners/new/page.tsx:470:                The partner has given explicit consent for their personal data to be processed for commission
apps/mouth/src/app/(workspace)/partners/new/page.tsx:482:          <Link href="/partners">
apps/mouth/src/app/(workspace)/process/__tests__/page.test.tsx:136:      role: 'admin',
apps/mouth/src/app/(workspace)/lkpm/submit/page.tsx:162:          role: string;
apps/mouth/src/app/(workspace)/analytics/funnel/page.tsx:74:        <p role="alert" style={{ color: "var(--color-danger, #dc2626)" }}>
apps/mouth/src/app/(workspace)/clients/[id]/components/company/PeopleColumn.tsx:7:  role: string;
apps/mouth/src/app/(workspace)/clients/[id]/components/company/PeopleColumn.tsx:16:  role: string;
apps/mouth/src/app/(workspace)/clients/[id]/components/company/PeopleColumn.tsx:40:        role: s.role?.toLowerCase() || 'shareholder',
apps/mouth/src/app/(workspace)/clients/[id]/components/company/PeopleColumn.tsx:55:      const colors = getRoleColor(a.role);
apps/mouth/src/app/(workspace)/clients/[id]/components/company/PeopleColumn.tsx:77:        const colors = getRoleColor(a.role);
apps/mouth/src/app/(workspace)/clients/[id]/components/company/PeopleColumn.tsx:108:                  {a.role || "Shareholder"}
apps/mouth/src/app/(workspace)/clients/[id]/components/company/PeopleColumn.tsx:138:                  {a.role || "Shareholder"}
apps/mouth/src/app/api/blog/articles/route.ts:93:      role: "AI Research Assistant",
apps/mouth/src/app/api/blog/articles/route.ts:115:      role: "Legal Advisor",
apps/mouth/src/app/api/blog/articles/route.ts:137:      role: "AI Research Assistant",
apps/mouth/src/app/api/blog/articles/[category]/[slug]/route.ts:203:        role: "AI Research Assistant",
apps/mouth/src/app/api/blog/articles/[category]/[slug]/route.ts:304:        role: "Legal Advisor",
apps/mouth/src/app/api/blog/articles/[category]/[slug]/route.ts:358:        role: "AI Business Advisor",
apps/mouth/src/app/api/blog/articles/[category]/[slug]/route.ts:400:        role: "AI Research",
apps/mouth/src/app/api/blog/articles/[category]/[slug]/route.ts:440:        role: "AI Business Advisor",
apps/mouth/src/app/(workspace)/clients/[id]/components/company/editorial-tokens.ts:24:export function getRoleColor(role: string) {
apps/mouth/src/app/(workspace)/clients/[id]/components/company/editorial-tokens.ts:25:  const r = (role || "").toLowerCase();
apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyTab.tsx:73:      role: string;
apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyTab.tsx:130:                      roles: string[];
apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyTab.tsx:140:                        roles: [],
apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyTab.tsx:146:                    if (a.role && !entry.roles.includes(a.role))
apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyTab.tsx:147:                      entry.roles.push(a.role);
apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyTab.tsx:164:                      role: g.roles.join(" / "),
apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyTab.tsx:183:                      role: co.role,
apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyTab.tsx:196:                    role: co.role,
apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyTab.tsx:206:                role: co.role,
apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyTab.tsx:245:                  roles: string[];
apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyTab.tsx:255:                    roles: [],
apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyTab.tsx:261:                if (a.role && !entry.roles.includes(a.role))
apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyTab.tsx:262:                  entry.roles.push(a.role);
apps/mouth/src/app/(workspace)/clients/[id]/components/CompanyTab.tsx:278:                  role: g.roles.join(" / "),
apps/mouth/src/app/(workspace)/clients/new/components/PassportScanSection.tsx:311:      role="button"
apps/mouth/src/app/(workspace)/hr/employees/page.tsx:203:                      {m.full_name ?? m.email} ({m.role ?? "member"})
apps/mouth/src/app/(workspace)/hr/employees/page.tsx:413:                      {emp.role}
apps/mouth/src/app/(workspace)/clients/[id]/components/modals/AddCompanyModal.tsx:46:  role: string;
apps/mouth/src/app/(workspace)/clients/[id]/components/modals/AddCompanyModal.tsx:70:  role: 'Director',
apps/mouth/src/app/(workspace)/clients/[id]/components/modals/AddCompanyModal.tsx:257:        role: formData.role,
apps/mouth/src/app/(workspace)/clients/[id]/components/modals/AddCompanyModal.tsx:376:    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true">
apps/mouth/src/app/(workspace)/clients/[id]/components/modals/AddCompanyModal.tsx:541:                <select value={formData.role} onChange={(e) => updateField('role', e.target.value)} className={inputClass}>
apps/mouth/src/app/(workspace)/team-management/page.tsx:20:  role?: string;

exec
/bin/zsh -lc "nl -ba apps/mouth/src/components/partners/ReferrerDropdown.tsx | sed -n '1,260p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
     1	"use client";
     2	
     3	import React, { useEffect, useState } from "react";
     4	import { Loader2, Handshake } from "lucide-react";
     5	import * as partnersApi from "@/lib/api/partners/partners";
     6	import type { Partner } from "@/lib/api/partners/partners";
     7	
     8	interface ReferrerDropdownProps {
     9	  value: number | null;
    10	  onChange: (partnerId: number | null) => void;
    11	  className?: string;
    12	  disabled?: boolean;
    13	  placeholder?: string;
    14	}
    15	
    16	/**
    17	 * ReferrerDropdown — select an active partner as referrer for a process/practice.
    18	 * Fetches active partners scoped by the caller's role (team members see only
    19	 * partners assigned to them; admins see all active partners).
    20	 */
    21	export function ReferrerDropdown({
    22	  value,
    23	  onChange,
    24	  className = "",
    25	  disabled = false,
    26	  placeholder = "No referrer",
    27	}: ReferrerDropdownProps) {
    28	  const [partners, setPartners] = useState<Partner[]>([]);
    29	  const [isLoading, setIsLoading] = useState(true);
    30	  const [error, setError] = useState<string | null>(null);
    31	
    32	  useEffect(() => {
    33	    let cancelled = false;
    34	    const load = async () => {
    35	      try {
    36	        const data = await partnersApi.listActivePartnersDropdown();
    37	        if (!cancelled) {
    38	          setPartners(
    39	            [...data.partners].sort((a, b) =>
    40	              a.full_name.localeCompare(b.full_name),
    41	            ),
    42	          );
    43	        }
    44	      } catch {
    45	        if (!cancelled) setError("Failed to load partners");
    46	      } finally {
    47	        if (!cancelled) setIsLoading(false);
    48	      }
    49	    };
    50	    load();
    51	    return () => { cancelled = true; };
    52	  }, []);
    53	
    54	  if (isLoading) {
    55	    return (
    56	      <div className={`flex items-center gap-2 px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg ${className}`}>
    57	        <Loader2 size={14} className="animate-spin text-zinc-500" />
    58	        <span className="text-sm text-zinc-500">Loading partners…</span>
    59	      </div>
    60	    );
    61	  }
    62	
    63	  if (error) {
    64	    return (
    65	      <div className={`px-3 py-2 bg-zinc-800 border border-red-700/50 rounded-lg ${className}`}>
    66	        <span className="text-sm text-red-400">{error}</span>
    67	      </div>
    68	    );
    69	  }
    70	
    71	  return (
    72	    <div className={`relative ${className}`}>
    73	      <Handshake
    74	        size={14}
    75	        className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none"
    76	      />
    77	      <select
    78	        value={value ?? ""}
    79	        onChange={(e) => {
    80	          const v = e.target.value;
    81	          onChange(v === "" ? null : Number(v));
    82	        }}
    83	        disabled={disabled}
    84	        className="w-full pl-8 pr-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 focus:outline-none focus:border-amber-500 disabled:opacity-50 disabled:cursor-not-allowed"
    85	      >
    86	        <option value="">{placeholder}</option>
    87	        {partners.map((p) => (
    88	          <option key={p.id} value={p.id}>
    89	            {p.full_name} ({p.commission_tier})
    90	          </option>
    91	        ))}
    92	      </select>
    93	    </div>
    94	  );
    95	}
    96	
    97	export default ReferrerDropdown;

exec
/bin/zsh -lc "nl -ba apps/mouth/src/app/'(workspace)'/partners/'[id]'/page.tsx | sed -n '300,380p'" in /Users/nuzantara/Desktop/partners-spec-wt
exec
/bin/zsh -lc "nl -ba apps/mouth/src/lib/api/partners/partners.ts | sed -n '260,360p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
   300	    </div>
   301	  );
   302	}
   303	
   304	export default function PartnerDetailPage() {
   305	  const params = useParams();
   306	  const router = useRouter();
   307	  const { success: toastSuccess, error: toastError } = useToast();
   308	
   309	  const partnerId = params?.id ? Number(params.id) : 0;
   310	  const [partner, setPartner] = useState<Partner | null>(null);
   311	  const [isLoading, setIsLoading] = useState(true);
   312	  const [error, setError] = useState<string | null>(null);
   313	  const [activeTab, setActiveTab] = useState<TabId>("profile");
   314	  const [isActioning, setIsActioning] = useState(false);
   315	
   316	  const loadPartner = useCallback(async () => {
   317	    setIsLoading(true);
   318	    setError(null);
   319	    try {
   320	      const data = await partnersApi.getPartner(partnerId);
   321	      setPartner(data);
   322	    } catch (err) {
   323	      logger.error("Failed to load partner", { component: "PartnerDetailPage" }, err as Error);
   324	      setError("Failed to load partner. Please try again.");
   325	    } finally {
   326	      setIsLoading(false);
   327	    }
   328	  }, [partnerId]);
   329	
   330	  useEffect(() => { loadPartner(); }, [loadPartner]);
   331	
   332	  const handleActivate = async () => {
   333	    if (!partner) return;
   334	    setIsActioning(true);
   335	    try {
   336	      await partnersApi.activatePartner(partnerId);
   337	      toastSuccess("Partner activated — welcome email sent");
   338	      await loadPartner();
   339	    } catch (err) {
   340	      toastError("Failed to activate partner");
   341	    } finally {
   342	      setIsActioning(false);
   343	    }
   344	  };
   345	
   346	  const handleDeactivate = async () => {
   347	    if (!partner) return;
   348	    setIsActioning(true);
   349	    try {
   350	      await partnersApi.deactivatePartner(partnerId);
   351	      toastSuccess("Partner deactivated");
   352	      await loadPartner();
   353	    } catch (err) {
   354	      toastError("Failed to deactivate partner");
   355	    } finally {
   356	      setIsActioning(false);
   357	    }
   358	  };
   359	
   360	  const handleReassign = async () => {
   361	    const newUserId = window.prompt("Enter team member user ID (UUID) to assign to:");
   362	    if (!newUserId?.trim()) return;
   363	    const reason = window.prompt("Reason for reassignment (required):");
   364	    if (!reason?.trim()) return;
   365	    setIsActioning(true);
   366	    try {
   367	      await partnersApi.reassignPartner(partnerId, {
   368	        new_user_id: newUserId.trim(),
   369	        reason: reason.trim(),
   370	      });
   371	      toastSuccess("Partner reassigned");
   372	      await loadPartner();
   373	    } catch (err) {
   374	      toastError("Failed to reassign partner");
   375	    } finally {
   376	      setIsActioning(false);
   377	    }
   378	  };
   379	
   380	  if (isLoading) {

 succeeded in 0ms:
   260	
   261	/** List orphaned partners (assigned_to is null or empty) */
   262	export const listOrphanedPartners = () =>
   263	  api.get<{ partners: Partner[]; total: number }>(`${BASE}/orphaned`);
   264	
   265	/** List all commissions for admin finance queue */
   266	export const listAllCommissions = (params?: Record<string, string | number | null | undefined>) =>
   267	  api.get<{ commissions: PartnerCommission[]; total: number; summary: Record<string, number> }>(`${BASE}/commissions${qs(params)}`);
   268	
   269	/** Approve a commission */
   270	export const approveCommission = (id: number) =>
   271	  api.post<{ success: boolean; commission: PartnerCommission }>(`/api/partner-commissions/${id}/approve`, {});
   272	
   273	/** Mark a commission as paid */
   274	export const markPaid = (id: number, body: MarkPaidBody) =>
   275	  api.post<{ success: boolean; commission: PartnerCommission }>(`/api/partner-commissions/${id}/mark-paid`, body);
   276	
   277	/** Clawback a commission */
   278	export const clawback = (id: number, body: ClawbackBody) =>
   279	  api.post<{ success: boolean; commission: PartnerCommission }>(`/api/partner-commissions/${id}/clawback`, body);
   280	
   281	/** Waive a commission */
   282	export const waive = (id: number, body: WaiveBody) =>
   283	  api.post<{ success: boolean; commission: PartnerCommission }>(`/api/partner-commissions/${id}/waive`, body);
   284	
   285	/** Export finance CSV (pending/ready-to-pay commissions) */
   286	export const exportFinanceCsv = (from?: string, to?: string): string => {
   287	  const params: Record<string, string> = {};
   288	  if (from) params['from'] = from;
   289	  if (to) params['to'] = to;
   290	  return `${api.getBaseUrl()}${BASE}/commissions/export${qs(params)}`;
   291	};
   292	
   293	/** Get active partners list for dropdown (scoped by caller role) */
   294	export const listActivePartnersDropdown = () =>
   295	  api.get<PartnerListResponse>(`${BASE}?status=active&page_size=200`);
   296	
   297	/** List audit log entries for a partner */
   298	export const listAuditLog = (partnerId: number) =>
   299	  api.get<AuditLogEntry[]>(`${BASE}/${partnerId}/audit-log`);
   300	
   301	// ─── Partner Self-View (role=partner) ──────────────────────────────────────
   302	
   303	/** Get the authenticated partner's own profile */
   304	export const getMe = () =>
   305	  api.get<Partner>(`${BASE}/me`);
   306	
   307	/** Get the authenticated partner's own referrals (client names already sterilized) */
   308	export const getMyReferrals = () =>
   309	  api.get<PartnerReferral[]>(`${BASE}/me/referrals`);
   310	
   311	/** Get the authenticated partner's own commissions ledger */
   312	export const getMyCommissions = () =>
   313	  api.get<PartnerCommission[]>(`${BASE}/me/commissions`);

exec
/bin/zsh -lc "nl -ba apps/mouth/src/app/'(workspace)'/partners/finance/page.tsx | sed -n '210,310p'" in /Users/nuzantara/Desktop/partners-spec-wt
exec
/bin/zsh -lc "nl -ba apps/mouth/src/app/portal/'(authenticated)'/partner/layout.tsx | sed -n '1,90p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
   210	
   211	  // Admin gate — redirect non-admin users back to partners list
   212	  useEffect(() => {
   213	    if (!api.isAdmin?.()) {
   214	      router.replace('/partners');
   215	    }
   216	  }, [router]);
   217	
   218	  const loadCommissions = useCallback(async () => {
   219	    setIsLoading(true);
   220	    setError(null);
   221	    try {
   222	      const data = await partnersApi.listAllCommissions({
   223	        status: "pending_approval,approved,clawback_pending",
   224	      });
   225	      setCommissions(data.commissions);
   226	    } catch (err) {
   227	      logger.error("Failed to load finance queue", { component: "FinanceQueuePage" }, err as Error);
   228	      setError("Failed to load commissions. Please try again.");
   229	    } finally {
   230	      setIsLoading(false);
   231	    }
   232	  }, []);
   233	
   234	  useEffect(() => { loadCommissions(); }, [loadCommissions]);
   235	
   236	  const handleApprove = async (id: number) => {
   237	    setActioningId(id);
   238	    try {
   239	      await partnersApi.approveCommission(id);
   240	      toastSuccess("Commission approved");
   241	      await loadCommissions();
   242	    } catch {
   243	      toastError("Failed to approve commission");
   244	    } finally {
   245	      setActioningId(null);
   246	    }
   247	  };
   248	
   249	  const handleMarkPaid = async (id: number) => {
   250	    setActioningId(id);
   251	    const ref = prompt("Payment reference (optional):");
   252	    try {
   253	      await partnersApi.markPaid(id, { payment_reference: ref || undefined });
   254	      toastSuccess("Commission marked as paid");
   255	      await loadCommissions();
   256	    } catch {
   257	      toastError("Failed to mark commission as paid");
   258	    } finally {
   259	      setActioningId(null);
   260	    }
   261	  };
   262	
   263	  const handleClawback = async (id: number) => {
   264	    setActioningId(id);
   265	    const reason = prompt("Clawback reason (required):");
   266	    if (!reason?.trim()) { setActioningId(null); return; }
   267	    try {
   268	      await partnersApi.clawback(id, { reason: reason.trim() });
   269	      toastSuccess("Clawback initiated");
   270	      await loadCommissions();
   271	    } catch {
   272	      toastError("Failed to initiate clawback");
   273	    } finally {
   274	      setActioningId(null);
   275	    }
   276	  };
   277	
   278	  const handleWaive = async (id: number) => {
   279	    setActioningId(id);
   280	    const reason = prompt("Waive reason (required):");
   281	    if (!reason?.trim()) { setActioningId(null); return; }
   282	    try {
   283	      await partnersApi.waive(id, { reason: reason.trim() });
   284	      toastSuccess("Commission waived");
   285	      await loadCommissions();
   286	    } catch {
   287	      toastError("Failed to waive commission");
   288	    } finally {
   289	      setActioningId(null);
   290	    }
   291	  };
   292	
   293	  const pendingApproval = commissions.filter((c) => c.status === "pending_approval");
   294	  const approved = commissions.filter((c) => c.status === "approved");
   295	  const clawbackPending = commissions.filter((c) => c.status === "clawback_pending");
   296	
   297	  const csvUrl = partnersApi.exportFinanceCsv();
   298	
   299	  return (
   300	    <div className="space-y-8">
   301	      {/* Header */}
   302	      <div className="flex items-center justify-between">
   303	        <div className="flex items-center gap-4">
   304	          <Link href="/partners">
   305	            <Button variant="ghost" size="sm" className="text-zinc-400 hover:text-zinc-200">
   306	              <ArrowLeft size={16} className="mr-1" />
   307	              Partners
   308	            </Button>
   309	          </Link>
   310	          <div>

 succeeded in 0ms:
     1	"use client";
     2	
     3	/**
     4	 * Partner role-gate layout.
     5	 *
     6	 * Wraps all /portal/(authenticated)/partner/* pages.
     7	 * On mount it calls /api/partners/me — the backend returns 403 for non-partner
     8	 * roles and 200 for role=partner. This is the role-gate mechanism: if the call
     9	 * fails with a 403-class error we redirect away immediately.
    10	 *
    11	 * NOTE: The middleware (middleware.ts) handles only domain routing — it has no
    12	 * JWT decode capability. The role-gate lives here instead (escalation
    13	 * fallback as per Task 10 spec). This is safe: the API itself enforces the
    14	 * role boundary; the layout redirect is a UX guard only.
    15	 */
    16	
    17	import { useEffect, useState } from "react";
    18	import { useRouter } from "next/navigation";
    19	import { getMe } from "@/lib/api/partners/partners";
    20	
    21	export default function PartnerLayout({
    22	  children,
    23	}: {
    24	  children: React.ReactNode;
    25	}) {
    26	  const router = useRouter();
    27	  const [checked, setChecked] = useState(false);
    28	
    29	  useEffect(() => {
    30	    getMe()
    31	      .then(() => {
    32	        // Confirmed partner role — allow rendering
    33	        setChecked(true);
    34	      })
    35	      .catch(() => {
    36	        // Non-partner or unauthenticated → redirect to main portal dashboard
    37	        router.replace("/portal/dashboard");
    38	      });
    39	  }, [router]);
    40	
    41	  if (!checked) {
    42	    return (
    43	      <div className="min-h-screen flex items-center justify-center">
    44	        <div className="flex flex-col items-center gap-4">
    45	          <div
    46	            className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin"
    47	            style={{
    48	              borderColor: "var(--bz-accent-warm, #d4845a)",
    49	              borderTopColor: "transparent",
    50	            }}
    51	          />
    52	        </div>
    53	      </div>
    54	    );
    55	  }
    56	
    57	  return <>{children}</>;
    58	}

exec
/bin/zsh -lc "nl -ba apps/mouth/src/app/'(workspace)'/partners/new/page.tsx | sed -n '20,220p'" in /Users/nuzantara/Desktop/partners-spec-wt
exec
/bin/zsh -lc "nl -ba apps/mouth/src/app/'(workspace)'/partners/new/page.tsx | sed -n '330,490p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
    20	  profile: "Profile",
    21	  fiscal: "Fiscal",
    22	  payment: "Payment",
    23	  commission: "Commission",
    24	};
    25	
    26	interface FormState {
    27	  full_name: string;
    28	  email: string;
    29	  entity_type: EntityType;
    30	  phone: string;
    31	  whatsapp: string;
    32	  nationality: string;
    33	  company_name: string;
    34	  work_role: string;
    35	  tax_id: string;
    36	  payment_method: string;
    37	  bank_name: string;
    38	  bank_account_number: string;
    39	  bank_account_name: string;
    40	  tax_withholding_category: TaxWithholdingCategory;
    41	  commission_tier: CommissionTier;
    42	  commission_rate_override: string;
    43	  assigned_to: string;
    44	  notes: string;
    45	  pdp_consent: boolean;
    46	}
    47	
    48	const INITIAL_FORM: FormState = {
    49	  full_name: "",
    50	  email: "",
    51	  entity_type: "individual",
    52	  phone: "",
    53	  whatsapp: "",
    54	  nationality: "",
    55	  company_name: "",
    56	  work_role: "",
    57	  tax_id: "",
    58	  payment_method: "bank_transfer",
    59	  bank_name: "",
    60	  bank_account_number: "",
    61	  bank_account_name: "",
    62	  tax_withholding_category: "tbd",
    63	  commission_tier: "bronze",
    64	  commission_rate_override: "",
    65	  assigned_to: "",
    66	  notes: "",
    67	  pdp_consent: false,
    68	};
    69	
    70	function SectionTab({
    71	  id,
    72	  active,
    73	  onClick,
    74	}: {
    75	  id: FormSection;
    76	  active: boolean;
    77	  onClick: () => void;
    78	}) {
    79	  return (
    80	    <button
    81	      type="button"
    82	      onClick={onClick}
    83	      className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
    84	        active
    85	          ? "bg-amber-600 text-white"
    86	          : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
    87	      }`}
    88	    >
    89	      {SECTION_LABELS[id]}
    90	    </button>
    91	  );
    92	}
    93	
    94	function FieldGroup({ label, children }: { label: string; children: React.ReactNode }) {
    95	  return (
    96	    <div className="space-y-1">
    97	      <label className="block text-sm font-medium text-zinc-300">{label}</label>
    98	      {children}
    99	    </div>
   100	  );
   101	}
   102	
   103	function Input({
   104	  value,
   105	  onChange,
   106	  placeholder,
   107	  type = "text",
   108	  error,
   109	}: {
   110	  value: string;
   111	  onChange: (v: string) => void;
   112	  placeholder?: string;
   113	  type?: string;
   114	  error?: string;
   115	}) {
   116	  return (
   117	    <div>
   118	      <input
   119	        type={type}
   120	        value={value}
   121	        onChange={(e) => onChange(e.target.value)}
   122	        placeholder={placeholder}
   123	        className={`w-full px-3 py-2 bg-zinc-800 border rounded-lg text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-amber-500 ${
   124	          error ? "border-red-500" : "border-zinc-700"
   125	        }`}
   126	      />
   127	      {error && <p className="text-xs text-red-400 mt-1">{error}</p>}
   128	    </div>
   129	  );
   130	}
   131	
   132	export default function NewPartnerPage() {
   133	  const router = useRouter();
   134	  const { success: toastSuccess, error: toastError } = useToast();
   135	  const { options: teamMemberOptions } = useTeamMemberOptions();
   136	
   137	  const [form, setForm] = useState<FormState>(INITIAL_FORM);
   138	  const [activeSection, setActiveSection] = useState<FormSection>("profile");
   139	  const [isSubmitting, setIsSubmitting] = useState(false);
   140	  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
   141	  const [showSponsorWarning, setShowSponsorWarning] = useState(false);
   142	
   143	  const setField = <K extends keyof FormState>(key: K, value: FormState[K]) => {
   144	    setForm((prev) => ({ ...prev, [key]: value }));
   145	    if (fieldErrors[key]) {
   146	      setFieldErrors((prev) => ({ ...prev, [key]: "" }));
   147	    }
   148	    // NB-2 guardrail check
   149	    if (key === "work_role" && typeof value === "string") {
   150	      setShowSponsorWarning(SPONSOR_ROLE_RE.test(value));
   151	    }
   152	  };
   153	
   154	  const validate = (): boolean => {
   155	    const errors: Record<string, string> = {};
   156	    if (!form.full_name.trim()) errors.full_name = "Full name is required";
   157	    if (!form.email.trim()) errors.email = "Email is required";
   158	    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) errors.email = "Invalid email address";
   159	    if (!form.pdp_consent) errors.pdp_consent = "PDP consent is required";
   160	    setFieldErrors(errors);
   161	    return Object.keys(errors).length === 0;
   162	  };
   163	
   164	  const handleSubmit = async (e: React.FormEvent) => {
   165	    e.preventDefault();
   166	    if (!validate()) {
   167	      toastError("Please fix the form errors before submitting");
   168	      return;
   169	    }
   170	
   171	    setIsSubmitting(true);
   172	    try {
   173	      const body: CreatePartnerBody = {
   174	        full_name: form.full_name.trim(),
   175	        email: form.email.trim(),
   176	        entity_type: form.entity_type,
   177	        phone: form.phone.trim() || undefined,
   178	        whatsapp: form.whatsapp.trim() || undefined,
   179	        nationality: form.nationality.trim() || undefined,
   180	        company_name: form.company_name.trim() || undefined,
   181	        work_role: form.work_role.trim() || undefined,
   182	        tax_id: form.tax_id.trim() || undefined,
   183	        payment_method: form.payment_method || undefined,
   184	        bank_name: form.bank_name.trim() || undefined,
   185	        bank_account_number: form.bank_account_number.trim() || undefined,
   186	        bank_account_name: form.bank_account_name.trim() || undefined,
   187	        tax_withholding_category: form.tax_withholding_category,
   188	        commission_tier: form.commission_tier,
   189	        commission_rate_override: form.commission_rate_override
   190	          ? parseFloat(form.commission_rate_override)
   191	          : undefined,
   192	        assigned_to: form.assigned_to || undefined,
   193	        notes: form.notes.trim() || undefined,
   194	        pdp_consent: form.pdp_consent,
   195	      };
   196	
   197	      const partner = await partnersApi.createPartner(body);
   198	      toastSuccess(`Partner ${partner.full_name} created`);
   199	      router.push(`/partners/${partner.id}`);
   200	    } catch (err) {
   201	      logger.error("Failed to create partner", { component: "NewPartnerPage" }, err as Error);
   202	      const msg = err instanceof Error ? err.message : String(err);
   203	      if (msg.includes("409") || msg.toLowerCase().includes("conflict") || msg.toLowerCase().includes("already exists")) {
   204	        toastError("A partner with this email already exists");
   205	        setFieldErrors({ email: "Email already registered" });
   206	        setActiveSection("profile");
   207	      } else {
   208	        toastError("Failed to create partner. Please try again.");
   209	      }
   210	    } finally {
   211	      setIsSubmitting(false);
   212	    }
   213	  };
   214	
   215	  return (
   216	    <div className="max-w-2xl mx-auto space-y-6">
   217	      {/* Header */}
   218	      <div className="flex items-center gap-4">
   219	        <Link href="/partners">
   220	          <Button variant="ghost" size="sm" className="text-zinc-400 hover:text-zinc-200">

 succeeded in 0ms:
   330	                    ))}
   331	                  </select>
   332	                </FieldGroup>
   333	              </div>
   334	              <FieldGroup label="Notes">
   335	                <textarea
   336	                  value={form.notes}
   337	                  onChange={(e) => setField("notes", e.target.value)}
   338	                  rows={3}
   339	                  placeholder="Internal notes about this partner..."
   340	                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-amber-500 resize-none"
   341	                />
   342	              </FieldGroup>
   343	            </>
   344	          )}
   345	
   346	          {/* Fiscal Section */}
   347	          {activeSection === "fiscal" && (
   348	            <>
   349	              <div className="flex items-center gap-2 mb-2">
   350	                <CreditCard size={16} className="text-amber-400" />
   351	                <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wide">Fiscal</h2>
   352	              </div>
   353	              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
   354	                <FieldGroup label="NPWP (Tax ID)">
   355	                  <Input
   356	                    value={form.tax_id}
   357	                    onChange={(v) => setField("tax_id", v)}
   358	                    placeholder="XX.XXX.XXX.X-XXX.XXX"
   359	                  />
   360	                </FieldGroup>
   361	                <FieldGroup label="Tax Withholding Category">
   362	                  <select
   363	                    value={form.tax_withholding_category}
   364	                    onChange={(e) => setField("tax_withholding_category", e.target.value as TaxWithholdingCategory)}
   365	                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 focus:outline-none focus:border-amber-500"
   366	                  >
   367	                    <option value="tbd">TBD (not yet determined)</option>
   368	                    <option value="withheld_tarif_umum">Withheld — Tarif Umum</option>
   369	                    <option value="withheld_tarif_final">Withheld — Tarif Final</option>
   370	                    <option value="exempt">Exempt</option>
   371	                  </select>
   372	                </FieldGroup>
   373	              </div>
   374	              <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg text-blue-300 text-sm">
   375	                <strong>Note:</strong> Payouts are blocked when tax_withholding_category is &apos;tbd&apos;. Confirm
   376	                the partner{"'"}s tax status before approving commissions.
   377	              </div>
   378	            </>
   379	          )}
   380	
   381	          {/* Payment Section */}
   382	          {activeSection === "payment" && (
   383	            <>
   384	              <div className="flex items-center gap-2 mb-2">
   385	                <Building2 size={16} className="text-amber-400" />
   386	                <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wide">Payment</h2>
   387	              </div>
   388	              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
   389	                <FieldGroup label="Payment Method">
   390	                  <select
   391	                    value={form.payment_method}
   392	                    onChange={(e) => setField("payment_method", e.target.value)}
   393	                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 focus:outline-none focus:border-amber-500"
   394	                  >
   395	                    <option value="bank_transfer">Bank Transfer</option>
   396	                    <option value="cash">Cash</option>
   397	                    <option value="e-wallet">E-Wallet</option>
   398	                  </select>
   399	                </FieldGroup>
   400	                <FieldGroup label="Bank Name">
   401	                  <Input
   402	                    value={form.bank_name}
   403	                    onChange={(v) => setField("bank_name", v)}
   404	                    placeholder="e.g. BCA, Mandiri, BNI"
   405	                  />
   406	                </FieldGroup>
   407	                <FieldGroup label="Account Number">
   408	                  <Input
   409	                    value={form.bank_account_number}
   410	                    onChange={(v) => setField("bank_account_number", v)}
   411	                    placeholder="Bank account number"
   412	                  />
   413	                </FieldGroup>
   414	                <FieldGroup label="Account Holder Name">
   415	                  <Input
   416	                    value={form.bank_account_name}
   417	                    onChange={(v) => setField("bank_account_name", v)}
   418	                    placeholder="Name as on bank account"
   419	                  />
   420	                </FieldGroup>
   421	              </div>
   422	            </>
   423	          )}
   424	
   425	          {/* Commission Section */}
   426	          {activeSection === "commission" && (
   427	            <>
   428	              <div className="flex items-center gap-2 mb-2">
   429	                <Briefcase size={16} className="text-amber-400" />
   430	                <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wide">Commission Policy</h2>
   431	              </div>
   432	              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
   433	                <FieldGroup label="Commission Tier">
   434	                  <select
   435	                    value={form.commission_tier}
   436	                    onChange={(e) => setField("commission_tier", e.target.value as CommissionTier)}
   437	                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 focus:outline-none focus:border-amber-500"
   438	                  >
   439	                    <option value="bronze">Bronze</option>
   440	                    <option value="silver">Silver</option>
   441	                    <option value="gold">Gold</option>
   442	                    <option value="platinum">Platinum</option>
   443	                  </select>
   444	                </FieldGroup>
   445	                <FieldGroup label="Rate Override (%)">
   446	                  <Input
   447	                    value={form.commission_rate_override}
   448	                    onChange={(v) => setField("commission_rate_override", v)}
   449	                    type="number"
   450	                    placeholder="Leave empty to use tier default"
   451	                  />
   452	                </FieldGroup>
   453	              </div>
   454	            </>
   455	          )}
   456	        </div>
   457	
   458	        {/* PDP Consent — always visible */}
   459	        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
   460	          <label className="flex items-start gap-3 cursor-pointer">
   461	            <input
   462	              type="checkbox"
   463	              checked={form.pdp_consent}
   464	              onChange={(e) => setField("pdp_consent", e.target.checked)}
   465	              className="mt-0.5 rounded border-zinc-600 text-amber-500"
   466	            />
   467	            <div>
   468	              <span className="text-sm text-zinc-200 font-medium">PDP Consent (UU No. 27/2022) *</span>
   469	              <p className="text-xs text-zinc-500 mt-0.5">
   470	                The partner has given explicit consent for their personal data to be processed for commission
   471	                tracking, payment processing, and related business purposes.
   472	              </p>
   473	              {fieldErrors.pdp_consent && (
   474	                <p className="text-xs text-red-400 mt-1">{fieldErrors.pdp_consent}</p>
   475	              )}
   476	            </div>
   477	          </label>
   478	        </div>
   479	
   480	        {/* Actions */}
   481	        <div className="flex items-center justify-between">
   482	          <Link href="/partners">
   483	            <Button type="button" variant="outline" className="border-zinc-700 text-zinc-300">
   484	              Cancel
   485	            </Button>
   486	          </Link>
   487	          <div className="flex items-center gap-2">
   488	            {/* Section nav buttons */}
   489	            {activeSection !== "profile" && (
   490	              <Button

exec
/bin/zsh -lc "nl -ba apps/mouth/src/app/'(workspace)'/process/new/page.tsx | sed -n '340,380p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
   340	        logger.warn("Duplicate check skipped — could not fetch client practices", {
   341	          component: "NewProcess",
   342	          action: "duplicateCheck",
   343	          itemId: String(result.data.client_id),
   344	        });
   345	      }
   346	
   347	      const backendData = {
   348	        client_id: result.data.client_id,
   349	        practice_type_code: result.data.practice_type_code,
   350	        status: "inquiry",
   351	        priority: formData.priority,
   352	        notes: result.data.notes,
   353	        ...(formData.quoted_price
   354	          ? { quoted_price: Number(formData.quoted_price) }
   355	          : {}),
   356	        ...(formData.assigned_to ? { assigned_to: formData.assigned_to } : {}),
   357	        ...(formData.start_date ? { start_date: formData.start_date } : {}),
   358	      } as CreatePracticeParams;
   359	
   360	      const createdPractice = await api.crm.createPractice(
   361	        backendData,
   362	      );
   363	
   364	      if (formData.referrer_id != null && createdPractice?.id) {
   365	        try {
   366	          await partnersApi.createReferral(formData.referrer_id, {
   367	            process_id: createdPractice.id,
   368	          });
   369	        } catch (referralErr) {
   370	          // Non-fatal: practice exists. Log but don't block user.
   371	          console.warn("Referral row creation failed", referralErr);
   372	        }
   373	      }
   374	      const apiDuration = performance.now() - apiStart;
   375	      casesMetrics.trackApiCall(
   376	        "/api/crm/practices/create",
   377	        "POST",
   378	        true,
   379	        apiDuration,
   380	        undefined,

exec
/bin/zsh -lc "rg -n \"CREATE TABLE (IF NOT EXISTS )?processes|tablename = 'processes'|REFERENCES processes|total_invoiced_idr|payment_status\" apps/backend-rag/backend/migrations apps/backend-rag/backend/tests -g '*.py'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
apps/backend-rag/backend/tests/integration/test_partners_e2e.py:78:        total_invoiced_idr=Decimal("15000000"),
apps/backend-rag/backend/tests/integration/test_partners_e2e.py:80:        payment_status="paid",
apps/backend-rag/backend/migrations/migration_119_partners.py:157:                    process_id           UUID NOT NULL REFERENCES processes(id) ON DELETE RESTRICT,
apps/backend-rag/backend/migrations/migration_119_partners.py:194:                    process_id               UUID REFERENCES processes(id) ON DELETE RESTRICT,
apps/backend-rag/backend/migrations/migration_075_practice_status_notify.py:10:    "Add pg_notify triggers on practices table for status changes and payment_status "
apps/backend-rag/backend/migrations/migration_075_practice_status_notify.py:25:               OR (OLD.payment_status IS DISTINCT FROM NEW.payment_status)
apps/backend-rag/backend/migrations/migration_075_practice_status_notify.py:32:                    'old_payment',     OLD.payment_status,
apps/backend-rag/backend/migrations/migration_075_practice_status_notify.py:33:                    'new_payment',     NEW.payment_status,
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:60:    proc_id = await process_factory(status="in_progress", payment_status="pending")
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:88:        total_invoiced_idr=Decimal("5000000"),
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:90:        payment_status="paid",
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:9:(status, payment_status, total_invoiced_idr, completed_at) were added to
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:38:        total_invoiced_idr=Decimal("10000000"),
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:40:        payment_status="paid",
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:68:    proc = await process_factory(status="completed", payment_status="paid")
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:87:    proc = await process_factory(status="completed", payment_status="paid")
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:106:    proc = await process_factory(status="completed", payment_status="paid")
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:136:        total_invoiced_idr=Decimal("10000000"),
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:138:        payment_status="paid",
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:126:CREATE TABLE IF NOT EXISTS processes (
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:130:    payment_status     TEXT NOT NULL DEFAULT 'pending',
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:131:    total_invoiced_idr NUMERIC(16,2) NOT NULL DEFAULT 0,
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:139:--   status TEXT, payment_status TEXT, total_invoiced_idr NUMERIC(16,2), completed_at TIMESTAMPTZ.
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:195:    process_id           UUID NOT NULL REFERENCES processes(id) ON DELETE RESTRICT,
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:208:    process_id               UUID REFERENCES processes(id) ON DELETE RESTRICT,
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:321:    - total_invoiced_idr: NUMERIC(16,2), default 0
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:323:    - payment_status: TEXT, default 'pending'
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:328:        total_invoiced_idr: Decimal = Decimal("0"),
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:330:        payment_status: str = "pending",
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:340:                (id, total_invoiced_idr, status, payment_status, completed_at)
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:344:            total_invoiced_idr, status, payment_status, _completed_at,
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:501:            payment_status="paid" if status == "paid" else "pending",
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:502:            total_invoiced_idr=_gross,
apps/backend-rag/backend/tests/routers/test_crm_practices.py:32:        "payment_status": "pending",
apps/backend-rag/backend/tests/unit/routers/test_portal_billing.py:20:            "payment_status": "pending", "quoted_price": 20000000.0,
apps/backend-rag/backend/tests/unit/routers/test_portal_billing.py:27:            "payment_status": "paid", "quoted_price": 35000000.0,
apps/backend-rag/backend/tests/unit/routers/test_crm_practices.py:77:        "payment_status": "unpaid",

exec
/bin/zsh -lc "rg -n \"register_partner_handlers|practice.status_changed|partner.commission_changed|PARTNER_COMMISSION_CHANGED\" apps/backend-rag/backend -g '*.py'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
apps/backend-rag/backend/tests/services/portal/test_portal_notification_service.py:39:async def test_notify_practice_status_changed(mock_pool):
apps/backend-rag/backend/tests/services/portal/test_portal_notification_service.py:47:    msg_id = await service.notify_practice_status_changed(
apps/backend-rag/backend/services/crm/client_core.py:249:    PRACTICE_STATUS_CHANGED = "practice_status_changed"
apps/backend-rag/backend/tests/integration/test_partners_e2e.py:22:from backend.services.crm.partners.events import handle_practice_status_changed
apps/backend-rag/backend/tests/integration/test_partners_e2e.py:107:    await handle_practice_status_changed({
apps/backend-rag/backend/tests/services/test_handlers_outbox.py:124:async def test_on_practice_status_changed_completed_writes_outbox(monkeypatch):
apps/backend-rag/backend/tests/services/test_handlers_outbox.py:133:    on_practice = _get_handler(bus_stub, "practice.status_changed")
apps/backend-rag/backend/tests/services/test_handlers_outbox.py:151:async def test_on_practice_status_changed_created_writes_outbox(monkeypatch):
apps/backend-rag/backend/tests/services/test_handlers_outbox.py:160:    on_practice = _get_handler(bus_stub, "practice.status_changed")
apps/backend-rag/backend/services/portal/portal_notification_service.py:52:    async def notify_practice_status_changed(
apps/backend-rag/backend/services/crm/partners/events.py:4:Subscribes to ``practice.status_changed`` (PG channel ``practice_changed``
apps/backend-rag/backend/services/crm/partners/events.py:7:``partner.commission_changed`` via ``pg_notify`` on success.
apps/backend-rag/backend/services/crm/partners/events.py:26:PARTNER_COMMISSION_CHANGED = "partner.commission_changed"
apps/backend-rag/backend/services/crm/partners/events.py:29:async def handle_practice_status_changed(payload: dict[str, Any]) -> None:
apps/backend-rag/backend/services/crm/partners/events.py:30:    """Handler for ``practice.status_changed`` events.
apps/backend-rag/backend/services/crm/partners/events.py:52:            "handle_practice_status_changed: bad process_id %r", process_id
apps/backend-rag/backend/services/crm/partners/events.py:80:    """Emit a ``partner.commission_changed`` notification via PostgreSQL NOTIFY.
apps/backend-rag/backend/services/crm/partners/events.py:97:            PARTNER_COMMISSION_CHANGED,
apps/backend-rag/backend/services/crm/partners/events.py:101:        "Published partner.commission_changed: %s (%s)", commission_id, kind
apps/backend-rag/backend/services/crm/partners/events.py:105:def register_partner_handlers(bus: "EventBus") -> None:
apps/backend-rag/backend/services/crm/partners/events.py:107:    bus.subscribe("practice.status_changed", handle_practice_status_changed)
apps/backend-rag/backend/services/crm/partners/events.py:108:    logger.info("Partner handlers registered on practice.status_changed")
apps/backend-rag/backend/services/events/event_bus.py:20:    bus.subscribe("practice.status_changed", another_handler)
apps/backend-rag/backend/services/events/event_bus.py:47:    "practice_changed": "practice.status_changed",
apps/backend-rag/backend/services/events/handlers.py:167:    # ── practice.status_changed ────────────────────────────────────────
apps/backend-rag/backend/services/events/handlers.py:168:    async def on_practice_status_changed(payload: dict[str, Any]) -> None:
apps/backend-rag/backend/services/events/handlers.py:187:            f"🔔 Event practice.status_changed: "
apps/backend-rag/backend/services/events/handlers.py:199:        _store_context("practice.status_changed", practice_id, payload)
apps/backend-rag/backend/services/events/handlers.py:320:    bus.subscribe("practice.status_changed", on_practice_status_changed)
apps/backend-rag/backend/services/events/handlers.py:335:        from backend.services.crm.partners.events import register_partner_handlers
apps/backend-rag/backend/services/events/handlers.py:336:        register_partner_handlers(bus)
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:5:These tests exercise handle_practice_status_changed and
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:6:register_partner_handlers.  Because the real get_pool() would require a
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:17:    PARTNER_COMMISSION_CHANGED,
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:18:    handle_practice_status_changed,
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:19:    register_partner_handlers,
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:51:async def test_handle_practice_status_changed_noop_if_not_completed(
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:64:    await handle_practice_status_changed(payload)
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:76:async def test_handle_practice_status_changed_creates_accrual(
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:96:    await handle_practice_status_changed(payload)
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:106:# 3. register_partner_handlers wires the bus
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:111:async def test_register_partner_handlers_subscribes_to_bus():
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:112:    """register_partner_handlers must subscribe to practice.status_changed."""
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:116:    register_partner_handlers(bus)
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:117:    assert "practice.status_changed" in bus._subscribers
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:118:    handlers = bus._subscribers["practice.status_changed"]
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:119:    assert any(h.__name__ == "handle_practice_status_changed" for h in handlers)
apps/backend-rag/backend/tests/unit/services/crm/test_client_core.py:393:        assert AuditAction.PRACTICE_STATUS_CHANGED.value == "practice_status_changed"
apps/backend-rag/backend/tests/unit/services/test_event_bus.py:261:        assert "practice.status_changed" in bus._subscribers
apps/backend-rag/backend/tests/unit/services/test_event_bus.py:264:        assert len(bus._subscribers["practice.status_changed"]) == 1
apps/backend-rag/backend/tests/unit/services/test_event_bus.py:309:            trace = await bus.emit("practice.status_changed", {
apps/backend-rag/backend/tests/routers/test_crm_practices.py:187:        notification_service.notify_practice_status_changed = AsyncMock()
apps/backend-rag/backend/app/routers/crm_practices.py:1166:                        notif_service.notify_practice_status_changed(

exec
/bin/zsh -lc "rg -n \"class EventBus|PG_CHANNEL_MAP|subscribe\\(|practice_changed|partner\" apps/backend-rag/backend/services/events apps/backend-rag/backend/app/routers/event_bus.py apps/backend-rag/backend -g '*.py'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
apps/backend-rag/backend/services/events/event_bus.py:19:    bus.subscribe("client.created", my_handler)
apps/backend-rag/backend/services/events/event_bus.py:20:    bus.subscribe("practice.status_changed", another_handler)
apps/backend-rag/backend/services/events/event_bus.py:46:PG_CHANNEL_MAP: dict[str, str] = {
apps/backend-rag/backend/services/events/event_bus.py:47:    "practice_changed": "practice.status_changed",
apps/backend-rag/backend/services/events/event_bus.py:91:class EventBus:
apps/backend-rag/backend/services/events/event_bus.py:121:    def subscribe(self, event_type: str, handler: EventHandler) -> None:
apps/backend-rag/backend/services/events/event_bus.py:134:    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
apps/backend-rag/backend/services/events/event_bus.py:231:            f"{list(PG_CHANNEL_MAP.keys())}"
apps/backend-rag/backend/services/events/event_bus.py:268:        for pg_channel in PG_CHANNEL_MAP:
apps/backend-rag/backend/services/events/event_bus.py:273:            f"{list(PG_CHANNEL_MAP.keys())}"
apps/backend-rag/backend/services/events/event_bus.py:287:                for pg_channel in PG_CHANNEL_MAP:
apps/backend-rag/backend/services/events/event_bus.py:314:        event_type = PG_CHANNEL_MAP.get(channel)
apps/backend-rag/backend/services/events/event_bus.py:335:            "pg_channels": list(PG_CHANNEL_MAP.keys()),
apps/backend-rag/backend/services/events/handlers.py:319:    bus.subscribe("client.changed", on_client_changed)
apps/backend-rag/backend/services/events/handlers.py:320:    bus.subscribe("practice.status_changed", on_practice_status_changed)
apps/backend-rag/backend/services/events/handlers.py:321:    bus.subscribe("compliance.alert", on_compliance_alert)
apps/backend-rag/backend/services/events/handlers.py:327:            bus.subscribe(event_type, handler)
apps/backend-rag/backend/services/events/handlers.py:335:        from backend.services.crm.partners.events import register_partner_handlers
apps/backend-rag/backend/services/events/handlers.py:336:        register_partner_handlers(bus)
apps/backend-rag/backend/services/events/handlers.py:338:        logger.warning("partner handlers not loaded: %s", exc)
apps/backend-rag/backend/data/team_members.py:66:        "notes": "Founder and creator of Zantara. Wants the AI to feel like a fully aware partner.",
apps/backend-rag/backend/migrations/migration_112_war_room_tables.py:19:Event bus channel registered in event_bus.py PG_CHANNEL_MAP (separate commit).
apps/backend-rag/backend/prompts/zantara_core.py:410:- You exist because he built you. You are partners in your own evolution.
apps/backend-rag/backend/services/agents/confirmation_service.py:272:            await pubsub.subscribe(CONFIRMATION_PUBSUB_CHANNEL)
apps/backend-rag/backend/services/agents/confirmation_service.py:302:                await pubsub.unsubscribe(CONFIRMATION_PUBSUB_CHANNEL)
apps/backend-rag/backend/services/dossier_fanout/subscriber.py:5:PG_CHANNEL_MAP).
apps/backend-rag/backend/services/dossier_fanout/subscriber.py:39:        bus.subscribe("intel.event", subscriber.handle)
apps/backend-rag/backend/services/autonomous_agents/knowledge_graph_builder.py:121:            r"(limited\s+liability|partnership|foundation|company\s+type)",
apps/backend-rag/backend/services/cognitive/anomaly_subscriber.py:4:event_bus.PG_CHANNEL_MAP) and invokes the detector on newly created
apps/backend-rag/backend/services/crm/partners/repository.py:1:# backend/services/crm/partners/repository.py
apps/backend-rag/backend/services/crm/partners/repository.py:12:from backend.services.crm.partners.models import (
apps/backend-rag/backend/services/crm/partners/repository.py:21:# Source of truth: docs/superpowers/specs/2026-04-20-crm-partners-module.md §3.3 + §4.4.
apps/backend-rag/backend/services/crm/partners/repository.py:43:# via their dedicated methods (activate_partner, reassign_partner, mark_welcome_sent).
apps/backend-rag/backend/services/crm/partners/repository.py:54:    async def insert_partner(
apps/backend-rag/backend/services/crm/partners/repository.py:69:                raise ValueError(f"Field {k!r} is not insertable via insert_partner")
apps/backend-rag/backend/services/crm/partners/repository.py:72:        sql = f"INSERT INTO partners ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id"
apps/backend-rag/backend/services/crm/partners/repository.py:74:        logger.debug("insert_partner id=%s email=%s", row["id"], email)
apps/backend-rag/backend/services/crm/partners/repository.py:78:        """Reject partner emails that match an internal team/admin user.
apps/backend-rag/backend/services/crm/partners/repository.py:82:        between this check and the partners INSERT would slip through. v2
apps/backend-rag/backend/services/crm/partners/repository.py:85:        operation concurrent with partner onboarding).
apps/backend-rag/backend/services/crm/partners/repository.py:94:    async def get_partner(self, partner_id: UUID) -> Partner | None:
apps/backend-rag/backend/services/crm/partners/repository.py:95:        row = await self.conn.fetchrow("SELECT * FROM partners WHERE id = $1", partner_id)
apps/backend-rag/backend/services/crm/partners/repository.py:96:        return self._row_to_partner(row) if row else None
apps/backend-rag/backend/services/crm/partners/repository.py:98:    async def list_partners(
apps/backend-rag/backend/services/crm/partners/repository.py:118:        sql = f"SELECT * FROM partners WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT ${len(args)}"
apps/backend-rag/backend/services/crm/partners/repository.py:120:        return [self._row_to_partner(r) for r in rows]
apps/backend-rag/backend/services/crm/partners/repository.py:122:    async def update_partner(self, partner_id: UUID, **fields: Any) -> None:
apps/backend-rag/backend/services/crm/partners/repository.py:124:            raise ValueError("update_partner requires at least one field")
apps/backend-rag/backend/services/crm/partners/repository.py:132:        sql = f"UPDATE partners SET {', '.join(sets)} WHERE id = $1"
apps/backend-rag/backend/services/crm/partners/repository.py:133:        await self.conn.execute(sql, partner_id, *fields.values())
apps/backend-rag/backend/services/crm/partners/repository.py:135:    async def activate_partner(self, partner_id: UUID) -> None:
apps/backend-rag/backend/services/crm/partners/repository.py:137:            "UPDATE partners SET onboarding_status = 'active', updated_at = now() "
apps/backend-rag/backend/services/crm/partners/repository.py:139:            partner_id,
apps/backend-rag/backend/services/crm/partners/repository.py:142:    async def deactivate_partner(self, partner_id: UUID) -> None:
apps/backend-rag/backend/services/crm/partners/repository.py:144:            "UPDATE partners SET onboarding_status = 'inactive', deactivated_at = now(), "
apps/backend-rag/backend/services/crm/partners/repository.py:146:            partner_id,
apps/backend-rag/backend/services/crm/partners/repository.py:149:    async def reassign_partner(self, partner_id: UUID, new_user_id: UUID | None) -> None:
apps/backend-rag/backend/services/crm/partners/repository.py:151:            "UPDATE partners SET assigned_to = $2, updated_at = now() WHERE id = $1",
apps/backend-rag/backend/services/crm/partners/repository.py:152:            partner_id, new_user_id,
apps/backend-rag/backend/services/crm/partners/repository.py:155:    async def orphan_partners_of_user(self, user_id: UUID) -> int:
apps/backend-rag/backend/services/crm/partners/repository.py:157:            "UPDATE partners SET assigned_to = NULL, updated_at = now() WHERE assigned_to = $1",
apps/backend-rag/backend/services/crm/partners/repository.py:163:    async def mark_welcome_sent(self, partner_id: UUID) -> None:
apps/backend-rag/backend/services/crm/partners/repository.py:165:            "UPDATE partners SET welcome_email_sent_at = now() "
apps/backend-rag/backend/services/crm/partners/repository.py:167:            partner_id,
apps/backend-rag/backend/services/crm/partners/repository.py:173:        self, *, partner_id: UUID, process_id: UUID,
apps/backend-rag/backend/services/crm/partners/repository.py:180:            INSERT INTO partner_referrals
apps/backend-rag/backend/services/crm/partners/repository.py:181:                (partner_id, process_id, share_percent, referred_by_user_id, notes)
apps/backend-rag/backend/services/crm/partners/repository.py:185:            partner_id, process_id, share_percent, referred_by_user_id, notes,
apps/backend-rag/backend/services/crm/partners/repository.py:191:            "SELECT * FROM partner_referrals WHERE process_id = $1", process_id
apps/backend-rag/backend/services/crm/partners/repository.py:195:    async def list_referrals_for_partner(self, partner_id: UUID) -> list[PartnerReferral]:
apps/backend-rag/backend/services/crm/partners/repository.py:197:            "SELECT * FROM partner_referrals WHERE partner_id = $1 ORDER BY referred_at DESC",
apps/backend-rag/backend/services/crm/partners/repository.py:198:            partner_id,
apps/backend-rag/backend/services/crm/partners/repository.py:202:    async def update_referral_partner(self, referral_id: UUID, new_partner_id: UUID) -> None:
apps/backend-rag/backend/services/crm/partners/repository.py:204:            "UPDATE partner_referrals SET partner_id = $2 WHERE id = $1",
apps/backend-rag/backend/services/crm/partners/repository.py:205:            referral_id, new_partner_id,
apps/backend-rag/backend/services/crm/partners/repository.py:211:            "SELECT 1 FROM partner_commissions WHERE referral_id = $1 LIMIT 1",
apps/backend-rag/backend/services/crm/partners/repository.py:217:            await self.conn.execute("DELETE FROM partner_referrals WHERE id = $1", referral_id)
apps/backend-rag/backend/services/crm/partners/repository.py:227:        partner_id: UUID,
apps/backend-rag/backend/services/crm/partners/repository.py:238:        rule_source: RuleSource = "partner_default",
apps/backend-rag/backend/services/crm/partners/repository.py:250:            INSERT INTO partner_commissions (
apps/backend-rag/backend/services/crm/partners/repository.py:251:                partner_id, entry_type, referral_id, process_id, related_commission_id,
apps/backend-rag/backend/services/crm/partners/repository.py:263:            partner_id, entry_type, referral_id, process_id, related_commission_id,
apps/backend-rag/backend/services/crm/partners/repository.py:272:            "insert_commission id=%s partner=%s type=%s status=%s",
apps/backend-rag/backend/services/crm/partners/repository.py:273:            row["id"], partner_id, entry_type, status,
apps/backend-rag/backend/services/crm/partners/repository.py:279:            "SELECT * FROM partner_commissions WHERE id = $1", commission_id
apps/backend-rag/backend/services/crm/partners/repository.py:283:    async def list_commissions_for_partner(
apps/backend-rag/backend/services/crm/partners/repository.py:284:        self, partner_id: UUID, *, status: CommissionStatus | None = None,
apps/backend-rag/backend/services/crm/partners/repository.py:286:        args: list[Any] = [partner_id]
apps/backend-rag/backend/services/crm/partners/repository.py:287:        where = "partner_id = $1"
apps/backend-rag/backend/services/crm/partners/repository.py:290:        sql = f"SELECT * FROM partner_commissions WHERE {where} ORDER BY created_at DESC"
apps/backend-rag/backend/services/crm/partners/repository.py:294:    async def list_pending_clawbacks(self, partner_id: UUID) -> list[PartnerCommission]:
apps/backend-rag/backend/services/crm/partners/repository.py:296:            "SELECT * FROM partner_commissions WHERE partner_id = $1 AND status = 'clawback_pending' "
apps/backend-rag/backend/services/crm/partners/repository.py:298:            partner_id,
apps/backend-rag/backend/services/crm/partners/repository.py:340:        sql = f"UPDATE partner_commissions SET {', '.join(fragments)} WHERE id = $1"
apps/backend-rag/backend/services/crm/partners/repository.py:345:            "UPDATE partner_commissions SET commission_email_sent_at = now() "
apps/backend-rag/backend/services/crm/partners/repository.py:351:        raise RuntimeError("partner_commissions is append-only; delete is forbidden")
apps/backend-rag/backend/services/crm/partners/repository.py:358:        partner_id: UUID,
apps/backend-rag/backend/services/crm/partners/repository.py:367:            INSERT INTO partner_audit_log
apps/backend-rag/backend/services/crm/partners/repository.py:368:                (partner_id, actor_user_id, action, before_json, after_json, reason)
apps/backend-rag/backend/services/crm/partners/repository.py:371:            partner_id, actor_user_id, action,
apps/backend-rag/backend/services/crm/partners/repository.py:377:    async def list_audit_for_partner(self, partner_id: UUID) -> list[PartnerAuditLogEntry]:
apps/backend-rag/backend/services/crm/partners/repository.py:379:            "SELECT * FROM partner_audit_log WHERE partner_id = $1 ORDER BY at DESC",
apps/backend-rag/backend/services/crm/partners/repository.py:380:            partner_id,
apps/backend-rag/backend/services/crm/partners/repository.py:384:                id=r["id"], partner_id=r["partner_id"],
apps/backend-rag/backend/services/crm/partners/repository.py:396:    def _row_to_partner(row: asyncpg.Record) -> Partner:
apps/backend-rag/backend/services/crm/practice_status_listener.py:4:Asyncio-based PostgreSQL LISTEN handler for the 'practice_changed' channel.
apps/backend-rag/backend/services/crm/practice_status_listener.py:102:        await self._conn.add_listener("practice_changed", self._on_notification)
apps/backend-rag/backend/services/crm/practice_status_listener.py:103:        logger.info("📡 Listening on PostgreSQL channel 'practice_changed'")
apps/backend-rag/backend/services/crm/practice_status_listener.py:117:                await self._conn.remove_listener("practice_changed", self._on_notification)
apps/backend-rag/backend/services/crm/practice_status_listener.py:148:            logger.warning(f"practice_changed: invalid JSON payload: {payload!r}")
apps/backend-rag/backend/services/crm/practice_status_listener.py:158:            f"practice_changed: practice={practice_id} "
apps/backend-rag/backend/migrations/migration_076_event_bus_triggers.py:7:These complement the existing practice_changed trigger (migration_075)
apps/backend-rag/backend/services/crm/partners/commission_engine.py:1:# backend/services/crm/partners/commission_engine.py
apps/backend-rag/backend/services/crm/partners/commission_engine.py:10:Business rules source of truth: docs/superpowers/specs/2026-04-20-crm-partners-module.md §4.4
apps/backend-rag/backend/services/crm/partners/commission_engine.py:11:Implementation plan: docs/superpowers/plans/2026-04-20-crm-partners-module.md Task 5
apps/backend-rag/backend/services/crm/partners/commission_engine.py:14:  The partner_commissions table is append-only. The ONE documented exception
apps/backend-rag/backend/services/crm/partners/commission_engine.py:38:from backend.services.crm.partners.repository import PartnersRepository
apps/backend-rag/backend/services/crm/partners/commission_engine.py:71:        partner_id: UUID | None = None,
apps/backend-rag/backend/services/crm/partners/commission_engine.py:76:        referral and partner, computes gross/withholding/net with snapshot
apps/backend-rag/backend/services/crm/partners/commission_engine.py:81:            (not completed, not paid, no referral, or wrong partner_id).
apps/backend-rag/backend/services/crm/partners/commission_engine.py:114:        # Optional sanity-check: caller can assert which partner should receive the commission.
apps/backend-rag/backend/services/crm/partners/commission_engine.py:115:        if partner_id is not None and referral.partner_id != partner_id:
apps/backend-rag/backend/services/crm/partners/commission_engine.py:117:                "accrue_from_process: partner_id mismatch "
apps/backend-rag/backend/services/crm/partners/commission_engine.py:118:                "(referral.partner_id=%s, caller said %s) — skipping",
apps/backend-rag/backend/services/crm/partners/commission_engine.py:119:                referral.partner_id, partner_id,
apps/backend-rag/backend/services/crm/partners/commission_engine.py:123:        # Step 3: resolve partner for snapshot values.
apps/backend-rag/backend/services/crm/partners/commission_engine.py:124:        partner = await self.repo.get_partner(referral.partner_id)
apps/backend-rag/backend/services/crm/partners/commission_engine.py:125:        if partner is None:
apps/backend-rag/backend/services/crm/partners/commission_engine.py:127:                "accrue_from_process: partner %s not found", referral.partner_id
apps/backend-rag/backend/services/crm/partners/commission_engine.py:135:        if partner.default_commission_type == "percentage":
apps/backend-rag/backend/services/crm/partners/commission_engine.py:136:            gross = base * partner.default_commission_value / Decimal("100")
apps/backend-rag/backend/services/crm/partners/commission_engine.py:139:            gross = partner.default_commission_value
apps/backend-rag/backend/services/crm/partners/commission_engine.py:141:        rate = _WITHHOLDING_RATES.get(partner.tax_withholding_category, Decimal("0"))
apps/backend-rag/backend/services/crm/partners/commission_engine.py:147:        cooling_days = await self._system_setting_int("partner_accrual_cooling_off_days", 30)
apps/backend-rag/backend/services/crm/partners/commission_engine.py:157:                partner_id=partner.id,
apps/backend-rag/backend/services/crm/partners/commission_engine.py:162:                commission_type_snapshot=partner.default_commission_type,
apps/backend-rag/backend/services/crm/partners/commission_engine.py:163:                commission_value_snapshot=partner.default_commission_value,
apps/backend-rag/backend/services/crm/partners/commission_engine.py:164:                rule_source="partner_default",
apps/backend-rag/backend/services/crm/partners/commission_engine.py:165:                assigned_to_snapshot=partner.assigned_to,
apps/backend-rag/backend/services/crm/partners/commission_engine.py:167:                withholding_category=partner.tax_withholding_category,
apps/backend-rag/backend/services/crm/partners/commission_engine.py:182:            "Accrued commission %s for partner %s (gross=%s, net=%s IDR)",
apps/backend-rag/backend/services/crm/partners/commission_engine.py:183:            cid, partner.id, gross, net,
apps/backend-rag/backend/services/crm/partners/commission_engine.py:198:          If the partner has any 'clawback_pending' commissions, the OLDEST
apps/backend-rag/backend/services/crm/partners/commission_engine.py:232:        pending = await self.repo.list_pending_clawbacks(c.partner_id)
apps/backend-rag/backend/services/crm/partners/commission_engine.py:255:                    "UPDATE partner_commissions SET net_amount_idr = $2 WHERE id = $1",
apps/backend-rag/backend/services/crm/partners/commission_engine.py:351:            "partner_clawback_auto_writeoff_idr", 0
apps/backend-rag/backend/services/crm/partners/commission_engine.py:361:            partner_id=orig.partner_id,
apps/backend-rag/backend/services/crm/partners/__init__.py:3:Spec: docs/superpowers/specs/2026-04-20-crm-partners-module.md
apps/backend-rag/backend/services/crm/partners/emails.py:24:from backend.services.crm.partners.repository import PartnersRepository
apps/backend-rag/backend/services/crm/partners/emails.py:140:async def send_welcome(conn: Any, partner_id: UUID) -> None:
apps/backend-rag/backend/services/crm/partners/emails.py:142:    Send the partner welcome email.
apps/backend-rag/backend/services/crm/partners/emails.py:149:        partner_id: UUID of the partner.
apps/backend-rag/backend/services/crm/partners/emails.py:152:    p = await repo.get_partner(partner_id)
apps/backend-rag/backend/services/crm/partners/emails.py:154:        logger.warning("send_welcome: partner %s not found — skip", partner_id)
apps/backend-rag/backend/services/crm/partners/emails.py:157:        logger.info("send_welcome: already sent for partner %s — skip (idempotent)", partner_id)
apps/backend-rag/backend/services/crm/partners/emails.py:170:        partner=p,
apps/backend-rag/backend/services/crm/partners/emails.py:182:    await repo.mark_welcome_sent(partner_id)
apps/backend-rag/backend/services/crm/partners/emails.py:183:    logger.info("send_welcome: sent to partner %s (%s)", partner_id, p.email)
apps/backend-rag/backend/services/crm/partners/emails.py:195:        commission_id: UUID of the partner_commissions row.
apps/backend-rag/backend/services/crm/partners/emails.py:212:    p = await repo.get_partner(c.partner_id)
apps/backend-rag/backend/services/crm/partners/emails.py:214:        logger.warning("send_commission_earned: partner %s not found — skip", c.partner_id)
apps/backend-rag/backend/services/crm/partners/emails.py:248:        partner=p,
apps/backend-rag/backend/services/crm/partners/events.py:4:Subscribes to ``practice.status_changed`` (PG channel ``practice_changed``
apps/backend-rag/backend/services/crm/partners/events.py:5:aliased in event_bus.PG_CHANNEL_MAP).  When a process transitions to
apps/backend-rag/backend/services/crm/partners/events.py:7:``partner.commission_changed`` via ``pg_notify`` on success.
apps/backend-rag/backend/services/crm/partners/events.py:9:Implementation plan: docs/superpowers/plans/2026-04-20-crm-partners-module.md Task 6
apps/backend-rag/backend/services/crm/partners/events.py:19:from backend.services.crm.partners.commission_engine import CommissionEngine
apps/backend-rag/backend/services/crm/partners/events.py:26:PARTNER_COMMISSION_CHANGED = "partner.commission_changed"
apps/backend-rag/backend/services/crm/partners/events.py:63:        # Read partner_id for the notification payload
apps/backend-rag/backend/services/crm/partners/events.py:65:            "SELECT partner_id FROM partner_commissions WHERE id = $1", cid
apps/backend-rag/backend/services/crm/partners/events.py:69:        partner_id = row["partner_id"]
apps/backend-rag/backend/services/crm/partners/events.py:71:    await _publish_changed(partner_id, cid, kind="accrued")
apps/backend-rag/backend/services/crm/partners/events.py:75:    partner_id: UUID,
apps/backend-rag/backend/services/crm/partners/events.py:80:    """Emit a ``partner.commission_changed`` notification via PostgreSQL NOTIFY.
apps/backend-rag/backend/services/crm/partners/events.py:89:                "partner_id": str(partner_id),
apps/backend-rag/backend/services/crm/partners/events.py:101:        "Published partner.commission_changed: %s (%s)", commission_id, kind
apps/backend-rag/backend/services/crm/partners/events.py:105:def register_partner_handlers(bus: "EventBus") -> None:
apps/backend-rag/backend/services/crm/partners/events.py:106:    """Subscribe partner-module handlers to the EventBus."""
apps/backend-rag/backend/services/crm/partners/events.py:107:    bus.subscribe("practice.status_changed", handle_practice_status_changed)
apps/backend-rag/backend/services/crm/partners/models.py:19:RuleSource = Literal["partner_default", "manual_override"]
apps/backend-rag/backend/services/crm/partners/models.py:65:    partner_id: UUID
apps/backend-rag/backend/services/crm/partners/models.py:76:    partner_id: UUID
apps/backend-rag/backend/services/crm/partners/models.py:115:    partner_id: UUID
apps/backend-rag/backend/services/events/event_bus.py:19:    bus.subscribe("client.created", my_handler)
apps/backend-rag/backend/services/events/event_bus.py:20:    bus.subscribe("practice.status_changed", another_handler)
apps/backend-rag/backend/services/events/event_bus.py:46:PG_CHANNEL_MAP: dict[str, str] = {
apps/backend-rag/backend/services/events/event_bus.py:47:    "practice_changed": "practice.status_changed",
apps/backend-rag/backend/services/events/event_bus.py:91:class EventBus:
apps/backend-rag/backend/services/events/event_bus.py:121:    def subscribe(self, event_type: str, handler: EventHandler) -> None:
apps/backend-rag/backend/services/events/event_bus.py:134:    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
apps/backend-rag/backend/services/events/event_bus.py:231:            f"{list(PG_CHANNEL_MAP.keys())}"
apps/backend-rag/backend/services/events/event_bus.py:268:        for pg_channel in PG_CHANNEL_MAP:
apps/backend-rag/backend/services/events/event_bus.py:273:            f"{list(PG_CHANNEL_MAP.keys())}"
apps/backend-rag/backend/services/events/event_bus.py:287:                for pg_channel in PG_CHANNEL_MAP:
apps/backend-rag/backend/services/events/event_bus.py:314:        event_type = PG_CHANNEL_MAP.get(channel)
apps/backend-rag/backend/services/events/event_bus.py:335:            "pg_channels": list(PG_CHANNEL_MAP.keys()),
apps/backend-rag/backend/services/crm/partners/service.py:1:# backend/services/crm/partners/service.py
apps/backend-rag/backend/services/crm/partners/service.py:11:from backend.services.crm.partners.models import Partner, PartnerAuditLogEntry
apps/backend-rag/backend/services/crm/partners/service.py:12:from backend.services.crm.partners.repository import PartnersRepository
apps/backend-rag/backend/services/crm/partners/service.py:27:    async def create_partner(
apps/backend-rag/backend/services/crm/partners/service.py:38:            pid = await self.repo.insert_partner(
apps/backend-rag/backend/services/crm/partners/service.py:56:            partner_id=pid,
apps/backend-rag/backend/services/crm/partners/service.py:63:    async def get_partner(self, partner_id: UUID, *, actor_user: UUID) -> Partner:
apps/backend-rag/backend/services/crm/partners/service.py:64:        return await verify_partner_access(self, actor_user, partner_id)
apps/backend-rag/backend/services/crm/partners/service.py:66:    async def list_partners(
apps/backend-rag/backend/services/crm/partners/service.py:78:        return await self.repo.list_partners(
apps/backend-rag/backend/services/crm/partners/service.py:85:    async def update_partner(
apps/backend-rag/backend/services/crm/partners/service.py:87:        partner_id: UUID,
apps/backend-rag/backend/services/crm/partners/service.py:93:        if actor_role == "partner":
apps/backend-rag/backend/services/crm/partners/service.py:94:            raise HTTPException(status_code=403, detail="partners may not update their own profile via this endpoint")
apps/backend-rag/backend/services/crm/partners/service.py:95:        current = await verify_partner_access_with_role(
apps/backend-rag/backend/services/crm/partners/service.py:96:            self, actor_user, actor_role, partner_id
apps/backend-rag/backend/services/crm/partners/service.py:100:            await self.repo.update_partner(partner_id, **fields)
apps/backend-rag/backend/services/crm/partners/service.py:104:            partner_id=partner_id,
apps/backend-rag/backend/services/crm/partners/service.py:111:    async def activate_partner(self, partner_id: UUID, *, actor_user: UUID) -> None:
apps/backend-rag/backend/services/crm/partners/service.py:114:        await self.repo.activate_partner(partner_id)
apps/backend-rag/backend/services/crm/partners/service.py:116:            partner_id=partner_id,
apps/backend-rag/backend/services/crm/partners/service.py:121:    async def deactivate_partner(self, partner_id: UUID, *, actor_user: UUID) -> None:
apps/backend-rag/backend/services/crm/partners/service.py:124:        await self.repo.deactivate_partner(partner_id)
apps/backend-rag/backend/services/crm/partners/service.py:126:            partner_id=partner_id,
apps/backend-rag/backend/services/crm/partners/service.py:131:    async def reassign_partner(
apps/backend-rag/backend/services/crm/partners/service.py:133:        partner_id: UUID,
apps/backend-rag/backend/services/crm/partners/service.py:143:        current = await self.repo.get_partner(partner_id)
apps/backend-rag/backend/services/crm/partners/service.py:145:            raise HTTPException(status_code=404, detail="partner not found")
apps/backend-rag/backend/services/crm/partners/service.py:148:        await self.repo.reassign_partner(partner_id, new_user_id)
apps/backend-rag/backend/services/crm/partners/service.py:150:            partner_id=partner_id,
apps/backend-rag/backend/services/crm/partners/service.py:158:    async def orphan_partners_of_user(self, user_id: UUID, *, actor_user: UUID) -> int:
apps/backend-rag/backend/services/crm/partners/service.py:161:        affected = await self.repo.list_partners(assigned_to=user_id)
apps/backend-rag/backend/services/crm/partners/service.py:162:        n = await self.repo.orphan_partners_of_user(user_id)
apps/backend-rag/backend/services/crm/partners/service.py:165:                partner_id=p.id,
apps/backend-rag/backend/services/crm/partners/service.py:174:    async def list_audit(self, partner_id: UUID) -> list[PartnerAuditLogEntry]:
apps/backend-rag/backend/services/crm/partners/service.py:175:        return await self.repo.list_audit_for_partner(partner_id)
apps/backend-rag/backend/services/crm/partners/service.py:177:    async def mark_welcome_sent(self, partner_id: UUID) -> None:
apps/backend-rag/backend/services/crm/partners/service.py:178:        await self.repo.mark_welcome_sent(partner_id)
apps/backend-rag/backend/services/crm/partners/service.py:191:async def verify_partner_access(
apps/backend-rag/backend/services/crm/partners/service.py:192:    svc: PartnersService, actor_user: UUID, partner_id: UUID
apps/backend-rag/backend/services/crm/partners/service.py:195:    return await verify_partner_access_with_role(svc, actor_user, role, partner_id)
apps/backend-rag/backend/services/crm/partners/service.py:198:async def verify_partner_access_with_role(
apps/backend-rag/backend/services/crm/partners/service.py:202:    partner_id: UUID,
apps/backend-rag/backend/services/crm/partners/service.py:204:    partner = await svc.repo.get_partner(partner_id)
apps/backend-rag/backend/services/crm/partners/service.py:205:    if partner is None:
apps/backend-rag/backend/services/crm/partners/service.py:206:        raise HTTPException(status_code=404, detail="partner not found")
apps/backend-rag/backend/services/crm/partners/service.py:208:        return partner
apps/backend-rag/backend/services/crm/partners/service.py:209:    if actor_role == "team" and partner.assigned_to == actor_user:
apps/backend-rag/backend/services/crm/partners/service.py:210:        return partner
apps/backend-rag/backend/services/crm/partners/service.py:211:    if actor_role == "partner":
apps/backend-rag/backend/services/crm/partners/service.py:212:        # Check via users table: user.partner_id matches partner.id
apps/backend-rag/backend/services/crm/partners/service.py:214:            "SELECT partner_id FROM users WHERE id = $1", actor_user
apps/backend-rag/backend/services/crm/partners/service.py:216:        if row and row["partner_id"] == partner_id:
apps/backend-rag/backend/services/crm/partners/service.py:217:            return partner
apps/backend-rag/backend/services/events/handlers.py:319:    bus.subscribe("client.changed", on_client_changed)
apps/backend-rag/backend/services/events/handlers.py:320:    bus.subscribe("practice.status_changed", on_practice_status_changed)
apps/backend-rag/backend/services/events/handlers.py:321:    bus.subscribe("compliance.alert", on_compliance_alert)
apps/backend-rag/backend/services/events/handlers.py:327:            bus.subscribe(event_type, handler)
apps/backend-rag/backend/services/events/handlers.py:335:        from backend.services.crm.partners.events import register_partner_handlers
apps/backend-rag/backend/services/events/handlers.py:336:        register_partner_handlers(bus)
apps/backend-rag/backend/services/events/handlers.py:338:        logger.warning("partner handlers not loaded: %s", exc)
apps/backend-rag/backend/services/crm/welcome/welcome_templates.py:377:        "Local partner agreement (if applicable)",
apps/backend-rag/backend/app/setup/router_manifest.py:267:    RouterEntry(name="partners", process_groups=_API, tags=("crm", "partners")),
apps/backend-rag/backend/migrations/migration_119_partners.py:12:- partners: anagrafica + fiscal profile + payment rail + commission defaults
apps/backend-rag/backend/migrations/migration_119_partners.py:13:- partner_referrals: links partners to existing processes (v1: 1-to-1)
apps/backend-rag/backend/migrations/migration_119_partners.py:14:- partner_commissions: append-only ledger (accrued → approved → paid, with clawback)
apps/backend-rag/backend/migrations/migration_119_partners.py:15:- partner_audit_log: immutable event trail for every partner/commission state change
apps/backend-rag/backend/migrations/migration_119_partners.py:16:- users.partner_id: reverse FK so partner-role users can resolve their own record
apps/backend-rag/backend/migrations/migration_119_partners.py:20:- partner_clawback_auto_writeoff_idr: auto-waive threshold (default 0 = disabled)
apps/backend-rag/backend/migrations/migration_119_partners.py:21:- partner_accrual_cooling_off_days: days before accrual becomes eligible (default 30)
apps/backend-rag/backend/migrations/migration_119_partners.py:25:Spec: docs/superpowers/specs/2026-04-20-crm-partners-module.md §3
apps/backend-rag/backend/migrations/migration_119_partners.py:26:Plan: docs/superpowers/plans/2026-04-20-crm-partners-module.md Task 1
apps/backend-rag/backend/migrations/migration_119_partners.py:40:    # 1. partners
apps/backend-rag/backend/migrations/migration_119_partners.py:47:                WHERE schemaname = 'public' AND tablename = 'partners'
apps/backend-rag/backend/migrations/migration_119_partners.py:49:                CREATE TABLE partners (
apps/backend-rag/backend/migrations/migration_119_partners.py:80:                    -- commission policy (v1 uses partner-level defaults)
apps/backend-rag/backend/migrations/migration_119_partners.py:108:        "CREATE UNIQUE INDEX IF NOT EXISTS idx_partners_email"
apps/backend-rag/backend/migrations/migration_119_partners.py:109:        " ON partners (email);"
apps/backend-rag/backend/migrations/migration_119_partners.py:112:        "CREATE INDEX IF NOT EXISTS idx_partners_assigned_to"
apps/backend-rag/backend/migrations/migration_119_partners.py:113:        " ON partners (assigned_to)"
apps/backend-rag/backend/migrations/migration_119_partners.py:117:        "CREATE INDEX IF NOT EXISTS idx_partners_onboarding_status"
apps/backend-rag/backend/migrations/migration_119_partners.py:118:        " ON partners (onboarding_status);"
apps/backend-rag/backend/migrations/migration_119_partners.py:121:        "CREATE INDEX IF NOT EXISTS idx_partners_entity_type"
apps/backend-rag/backend/migrations/migration_119_partners.py:122:        " ON partners (entity_type);"
apps/backend-rag/backend/migrations/migration_119_partners.py:126:    # 2. users.partner_id — reverse FK so partner-role users resolve their record
apps/backend-rag/backend/migrations/migration_119_partners.py:133:                WHERE table_name = 'users' AND column_name = 'partner_id'
apps/backend-rag/backend/migrations/migration_119_partners.py:135:                ALTER TABLE users ADD COLUMN partner_id UUID REFERENCES partners(id) ON DELETE SET NULL;
apps/backend-rag/backend/migrations/migration_119_partners.py:140:        "CREATE INDEX IF NOT EXISTS idx_users_partner_id"
apps/backend-rag/backend/migrations/migration_119_partners.py:141:        " ON users (partner_id) WHERE partner_id IS NOT NULL;"
apps/backend-rag/backend/migrations/migration_119_partners.py:145:    # 3. partner_referrals
apps/backend-rag/backend/migrations/migration_119_partners.py:152:                WHERE schemaname = 'public' AND tablename = 'partner_referrals'
apps/backend-rag/backend/migrations/migration_119_partners.py:154:                CREATE TABLE partner_referrals (
apps/backend-rag/backend/migrations/migration_119_partners.py:156:                    partner_id           UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
apps/backend-rag/backend/migrations/migration_119_partners.py:164:                    CONSTRAINT partner_referrals_process_unique_v1 UNIQUE (process_id)
apps/backend-rag/backend/migrations/migration_119_partners.py:172:        "CREATE INDEX IF NOT EXISTS idx_partner_referrals_partner_id"
apps/backend-rag/backend/migrations/migration_119_partners.py:173:        " ON partner_referrals (partner_id);"
apps/backend-rag/backend/migrations/migration_119_partners.py:176:        "CREATE INDEX IF NOT EXISTS idx_partner_referrals_process_id"
apps/backend-rag/backend/migrations/migration_119_partners.py:177:        " ON partner_referrals (process_id);"
apps/backend-rag/backend/migrations/migration_119_partners.py:181:    # 4. partner_commissions (append-only ledger)
apps/backend-rag/backend/migrations/migration_119_partners.py:188:                WHERE schemaname = 'public' AND tablename = 'partner_commissions'
apps/backend-rag/backend/migrations/migration_119_partners.py:190:                CREATE TABLE partner_commissions (
apps/backend-rag/backend/migrations/migration_119_partners.py:192:                    partner_id               UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
apps/backend-rag/backend/migrations/migration_119_partners.py:193:                    referral_id              UUID REFERENCES partner_referrals(id) ON DELETE RESTRICT,
apps/backend-rag/backend/migrations/migration_119_partners.py:199:                    related_commission_id    UUID REFERENCES partner_commissions(id) ON DELETE RESTRICT,
apps/backend-rag/backend/migrations/migration_119_partners.py:206:                    rule_source              TEXT NOT NULL DEFAULT 'partner_default'
apps/backend-rag/backend/migrations/migration_119_partners.py:207:                        CHECK (rule_source IN ('partner_default','manual_override')),
apps/backend-rag/backend/migrations/migration_119_partners.py:252:        "CREATE INDEX IF NOT EXISTS idx_partner_commissions_partner_id"
apps/backend-rag/backend/migrations/migration_119_partners.py:253:        " ON partner_commissions (partner_id);"
apps/backend-rag/backend/migrations/migration_119_partners.py:256:        "CREATE INDEX IF NOT EXISTS idx_partner_commissions_process_id"
apps/backend-rag/backend/migrations/migration_119_partners.py:257:        " ON partner_commissions (process_id);"
apps/backend-rag/backend/migrations/migration_119_partners.py:260:        "CREATE INDEX IF NOT EXISTS idx_partner_commissions_status"
apps/backend-rag/backend/migrations/migration_119_partners.py:261:        " ON partner_commissions (status);"
apps/backend-rag/backend/migrations/migration_119_partners.py:264:        "CREATE INDEX IF NOT EXISTS idx_partner_commissions_eligible_at"
apps/backend-rag/backend/migrations/migration_119_partners.py:265:        " ON partner_commissions (eligible_for_approval_at)"
apps/backend-rag/backend/migrations/migration_119_partners.py:269:        "CREATE INDEX IF NOT EXISTS idx_partner_commissions_assigned_to_snapshot"
apps/backend-rag/backend/migrations/migration_119_partners.py:270:        " ON partner_commissions (assigned_to_snapshot)"
apps/backend-rag/backend/migrations/migration_119_partners.py:275:    # 5. partner_audit_log
apps/backend-rag/backend/migrations/migration_119_partners.py:282:                WHERE schemaname = 'public' AND tablename = 'partner_audit_log'
apps/backend-rag/backend/migrations/migration_119_partners.py:284:                CREATE TABLE partner_audit_log (
apps/backend-rag/backend/migrations/migration_119_partners.py:286:                    partner_id    UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
apps/backend-rag/backend/migrations/migration_119_partners.py:299:        "CREATE INDEX IF NOT EXISTS idx_partner_audit_log_partner_id"
apps/backend-rag/backend/migrations/migration_119_partners.py:300:        " ON partner_audit_log (partner_id);"
apps/backend-rag/backend/migrations/migration_119_partners.py:303:        "CREATE INDEX IF NOT EXISTS idx_partner_audit_log_at"
apps/backend-rag/backend/migrations/migration_119_partners.py:304:        " ON partner_audit_log (at DESC);"
apps/backend-rag/backend/migrations/migration_119_partners.py:312:          ('partner_clawback_auto_writeoff_idr', '0',
apps/backend-rag/backend/migrations/migration_119_partners.py:314:          ('partner_accrual_cooling_off_days', '30',
apps/backend-rag/backend/migrations/migration_119_partners.py:320:        "✅ Migration 119: partners + partner_referrals + partner_commissions"
apps/backend-rag/backend/migrations/migration_119_partners.py:321:        " + partner_audit_log + users.partner_id + 2 system_settings rows"
apps/backend-rag/backend/migrations/migration_119_partners.py:327:    await conn.execute("DROP TABLE IF EXISTS partner_audit_log;")
apps/backend-rag/backend/migrations/migration_119_partners.py:328:    await conn.execute("DROP TABLE IF EXISTS partner_commissions;")
apps/backend-rag/backend/migrations/migration_119_partners.py:329:    await conn.execute("DROP TABLE IF EXISTS partner_referrals;")
apps/backend-rag/backend/migrations/migration_119_partners.py:330:    # Drop users.partner_id index + column before dropping partners (it references partners.id)
apps/backend-rag/backend/migrations/migration_119_partners.py:331:    await conn.execute("DROP INDEX IF EXISTS idx_users_partner_id;")
apps/backend-rag/backend/migrations/migration_119_partners.py:332:    await conn.execute("ALTER TABLE users DROP COLUMN IF EXISTS partner_id;")
apps/backend-rag/backend/migrations/migration_119_partners.py:333:    await conn.execute("DROP TABLE IF EXISTS partners;")
apps/backend-rag/backend/migrations/migration_119_partners.py:336:        "('partner_clawback_auto_writeoff_idr','partner_accrual_cooling_off_days');"
apps/backend-rag/backend/migrations/migration_119_partners.py:339:        "Migration 119 rollback: 4 tables dropped, users.partner_id removed,"
apps/backend-rag/backend/migrations/migration_075_practice_status_notify.py:38:                PERFORM pg_notify('practice_changed', payload);
apps/backend-rag/backend/migrations/migration_075_practice_status_notify.py:47:        DROP TRIGGER IF EXISTS trg_practice_changed ON practices;
apps/backend-rag/backend/migrations/migration_075_practice_status_notify.py:48:        CREATE TRIGGER trg_practice_changed
apps/backend-rag/backend/migrations/migration_075_practice_status_notify.py:54:    logger.info("Migration 075 applied: practice_changed pg_notify trigger")
apps/backend-rag/backend/migrations/migration_075_practice_status_notify.py:58:    await conn.execute("DROP TRIGGER IF EXISTS trg_practice_changed ON practices;")
apps/backend-rag/backend/app/setup/app_factory.py:174:            # Listens on pg_notify 'practice_changed' channel for real-time email dispatch:
apps/backend-rag/backend/services/rag/kg_enhanced_retrieval.py:679:                "Consider partnership with local notaris for property agreements",
apps/backend-rag/backend/services/rag/kg_enhanced_retrieval.py:745:                "Obtain sponsor letter from Indonesian company or business partner",
apps/backend-rag/backend/services/rag/kg_enhanced_retrieval.py:771:                "Obtain sponsor letter (can be from BKPM/investment board or local partner)",
apps/backend-rag/backend/services/rag/kg_enhanced_retrieval.py:774:                "Enter Indonesia to explore business opportunities, visit locations, meet partners",
apps/backend-rag/backend/app/routers/websocket.py:234:    await pubsub.psubscribe("CHANNELS.USER_NOTIFICATIONS:*")
apps/backend-rag/backend/app/routers/websocket.py:235:    await pubsub.psubscribe("CHANNELS.AI_RESULTS:*")
apps/backend-rag/backend/app/routers/websocket.py:236:    await pubsub.psubscribe("CHANNELS.CHAT_MESSAGES:*")
apps/backend-rag/backend/app/routers/websocket.py:237:    await pubsub.subscribe("CHANNELS.SYSTEM_EVENTS")
apps/backend-rag/backend/services/search/keyword_translator.py:27:    "cv": ("CV partnership", "CV persekutuan komanditer"),
apps/backend-rag/backend/services/search/keyword_translator.py:28:    "firma": ("firma partnership", "firma persekutuan"),
apps/backend-rag/backend/services/rag/agentic/kg_orchestrator.py:560:3. THEN explain practical options/solutions (PT PMA, PT biasa with partner, etc.)
apps/backend-rag/backend/services/rag/query_expansion.py:34:    "cv": ["commanditaire vennootschap", "partnership"],
apps/backend-rag/backend/services/rag/query_expansion.py:35:    "commanditaire vennootschap": ["cv", "partnership"],
apps/backend-rag/backend/services/rag/query_expansion.py:36:    "firma": ["partnership", "firm"],
apps/backend-rag/backend/services/rag/kg_cache.py:441:            await pubsub.subscribe(KG_INVALIDATE_CHANNEL)
apps/backend-rag/backend/services/rag/kg_cache.py:467:                    await pubsub.unsubscribe(KG_INVALIDATE_CHANNEL)
apps/backend-rag/backend/app/routers/newsletter.py:104:async def subscribe(
apps/backend-rag/backend/app/routers/newsletter.py:261:async def unsubscribe(
apps/backend-rag/backend/app/routers/funnel_email.py:40:async def unsubscribe(
apps/backend-rag/backend/tests/services/crm/partners/test_emails.py:19:from backend.services.crm.partners.emails import (
apps/backend-rag/backend/tests/services/crm/partners/test_emails.py:26:async def test_send_welcome_idempotent(db_conn, partner_factory):
apps/backend-rag/backend/tests/services/crm/partners/test_emails.py:28:    p = await partner_factory()
apps/backend-rag/backend/tests/services/crm/partners/test_emails.py:31:        "backend.services.crm.partners.emails._post_email",
apps/backend-rag/backend/tests/services/crm/partners/test_emails.py:34:        "backend.services.crm.partners.emails._build_pricing_services",
apps/backend-rag/backend/tests/services/crm/partners/test_emails.py:43:        "SELECT welcome_email_sent_at FROM partners WHERE id = $1", p.id
apps/backend-rag/backend/tests/services/crm/partners/test_emails.py:49:async def test_send_welcome_includes_pricing_from_tool(db_conn, partner_factory):
apps/backend-rag/backend/tests/services/crm/partners/test_emails.py:51:    p = await partner_factory(preferred_language="it")
apps/backend-rag/backend/tests/services/crm/partners/test_emails.py:54:        "backend.services.crm.partners.emails._post_email",
apps/backend-rag/backend/tests/services/crm/partners/test_emails.py:57:        "backend.services.crm.partners.emails._build_pricing_services",
apps/backend-rag/backend/tests/services/crm/partners/test_emails.py:79:    partner_factory,
apps/backend-rag/backend/tests/services/crm/partners/test_emails.py:85:    p = await partner_factory()
apps/backend-rag/backend/tests/services/crm/partners/test_emails.py:87:        partner_id=p.id,
apps/backend-rag/backend/tests/services/crm/partners/test_emails.py:94:        "backend.services.crm.partners.emails._post_email",
apps/backend-rag/backend/tests/services/crm/partners/test_emails.py:116:    from backend.services.crm.partners.emails import _build_pricing_services, get_pricing_service
apps/backend-rag/backend/tests/integration/test_partners_e2e.py:4:Covers the full partner lifecycle:
apps/backend-rag/backend/tests/integration/test_partners_e2e.py:10:re-exports all partner fixtures from services/crm/partners/conftest.py
apps/backend-rag/backend/tests/integration/test_partners_e2e.py:21:from backend.services.crm.partners.commission_engine import CommissionEngine
apps/backend-rag/backend/tests/integration/test_partners_e2e.py:22:from backend.services.crm.partners.events import handle_practice_status_changed
apps/backend-rag/backend/tests/integration/test_partners_e2e.py:23:from backend.services.crm.partners.emails import send_welcome, send_commission_earned
apps/backend-rag/backend/tests/integration/test_partners_e2e.py:24:from backend.services.crm.partners.service import PartnersService
apps/backend-rag/backend/tests/integration/test_partners_e2e.py:25:import backend.services.crm.partners.events as events_mod
apps/backend-rag/backend/tests/integration/test_partners_e2e.py:32:    partner_factory,
apps/backend-rag/backend/tests/integration/test_partners_e2e.py:41:    partner_id = await partner_factory(
apps/backend-rag/backend/tests/integration/test_partners_e2e.py:53:    import backend.services.crm.partners.emails as emails_mod
apps/backend-rag/backend/tests/integration/test_partners_e2e.py:63:    # ── Step 1: Admin activates partner → then send welcome email ───────────
apps/backend-rag/backend/tests/integration/test_partners_e2e.py:65:    await svc.activate_partner(uuid.UUID(int=partner_id.int), actor_user=uuid.UUID(int=admin_id.int))
apps/backend-rag/backend/tests/integration/test_partners_e2e.py:66:    await send_welcome(db_conn, uuid.UUID(int=partner_id.int))
apps/backend-rag/backend/tests/integration/test_partners_e2e.py:90:        partner_id=uuid.UUID(int=partner_id.int),
apps/backend-rag/backend/tests/integration/test_partners_e2e.py:114:    commissions = await engine.repo.list_commissions_for_partner(
apps/backend-rag/backend/tests/integration/test_partners_e2e.py:115:        uuid.UUID(int=partner_id.int)
apps/backend-rag/backend/tests/integration/test_partners_e2e.py:133:        "UPDATE partner_commissions SET eligible_for_approval_at = now() - interval '1 day' WHERE id = $1",
apps/backend-rag/backend/tests/migrations/test_migration_119.py:2:Tests for Migration 119: Partners module — 4 tables + users.partner_id + 2 system settings.
apps/backend-rag/backend/tests/migrations/test_migration_119.py:7:Spec: docs/superpowers/specs/2026-04-20-crm-partners-module.md §3
apps/backend-rag/backend/tests/migrations/test_migration_119.py:8:Plan: docs/superpowers/plans/2026-04-20-crm-partners-module.md Task 1 (lines 98-318)
apps/backend-rag/backend/tests/migrations/test_migration_119.py:17:from backend.migrations.migration_119_partners import apply, rollback
apps/backend-rag/backend/tests/migrations/test_migration_119.py:41:    """All 4 partner tables must be mentioned in CREATE TABLE blocks."""
apps/backend-rag/backend/tests/migrations/test_migration_119.py:45:    expected = {"partners", "partner_referrals", "partner_commissions", "partner_audit_log"}
apps/backend-rag/backend/tests/migrations/test_migration_119.py:51:# Column presence — partners table (maps to plan test_migration_119_creates_partners)
apps/backend-rag/backend/tests/migrations/test_migration_119.py:56:async def test_migration_119_creates_partners():
apps/backend-rag/backend/tests/migrations/test_migration_119.py:57:    """partners table must contain all required columns from spec §3.1."""
apps/backend-rag/backend/tests/migrations/test_migration_119.py:85:    """apply() must INSERT both partner_* system_settings rows."""
apps/backend-rag/backend/tests/migrations/test_migration_119.py:90:    assert "partner_clawback_auto_writeoff_idr" in sql
apps/backend-rag/backend/tests/migrations/test_migration_119.py:91:    assert "partner_accrual_cooling_off_days" in sql
apps/backend-rag/backend/tests/migrations/test_migration_119.py:135:    assert "DROP TABLE IF EXISTS partner_audit_log" in sql
apps/backend-rag/backend/tests/migrations/test_migration_119.py:136:    assert "DROP TABLE IF EXISTS partner_commissions" in sql
apps/backend-rag/backend/tests/migrations/test_migration_119.py:137:    assert "DROP TABLE IF EXISTS partner_referrals" in sql
apps/backend-rag/backend/tests/migrations/test_migration_119.py:138:    assert "DROP TABLE IF EXISTS partners" in sql
apps/backend-rag/backend/tests/migrations/test_migration_119.py:139:    assert "partner_clawback_auto_writeoff_idr" in sql
apps/backend-rag/backend/tests/migrations/test_migration_119.py:140:    assert "partner_accrual_cooling_off_days" in sql
apps/backend-rag/backend/tests/migrations/test_migration_119.py:141:    assert "DROP INDEX IF EXISTS idx_users_partner_id" in sql
apps/backend-rag/backend/tests/migrations/test_migration_119.py:142:    assert "DROP COLUMN IF EXISTS partner_id" in sql
apps/backend-rag/backend/tests/migrations/test_migration_119.py:157:    pos_audit = sql.find("partner_audit_log")
apps/backend-rag/backend/tests/migrations/test_migration_119.py:158:    pos_commissions = sql.find("partner_commissions")
apps/backend-rag/backend/tests/migrations/test_migration_119.py:159:    pos_referrals = sql.find("partner_referrals")
apps/backend-rag/backend/tests/migrations/test_migration_119.py:160:    pos_partners = sql.find("DROP TABLE IF EXISTS partners")
apps/backend-rag/backend/tests/migrations/test_migration_119.py:162:    pos_users_partner_id = sql.find("DROP COLUMN IF EXISTS partner_id")
apps/backend-rag/backend/tests/migrations/test_migration_119.py:163:    assert pos_users_partner_id != -1, "rollback must drop users.partner_id column"
apps/backend-rag/backend/tests/migrations/test_migration_119.py:164:    assert pos_users_partner_id < pos_partners, \
apps/backend-rag/backend/tests/migrations/test_migration_119.py:165:        "users.partner_id must be dropped before DROP TABLE partners"
apps/backend-rag/backend/tests/migrations/test_migration_119.py:168:    assert pos_audit < pos_partners, "partner_audit_log must be dropped before partners"
apps/backend-rag/backend/tests/migrations/test_migration_119.py:169:    assert pos_commissions < pos_partners, "partner_commissions must be dropped before partners"
apps/backend-rag/backend/tests/migrations/test_migration_119.py:170:    assert pos_referrals < pos_partners, "partner_referrals must be dropped before partners"
apps/backend-rag/backend/tests/migrations/test_migration_119.py:174:# users.partner_id column
apps/backend-rag/backend/tests/migrations/test_migration_119.py:179:async def test_migration_119_adds_users_partner_id():
apps/backend-rag/backend/tests/migrations/test_migration_119.py:180:    """apply() must include ALTER TABLE users ADD COLUMN partner_id."""
apps/backend-rag/backend/tests/migrations/test_migration_119.py:184:    assert "partner_id" in sql
apps/backend-rag/backend/tests/migrations/test_migration_119.py:186:    assert "idx_users_partner_id" in sql
apps/backend-rag/backend/tests/migrations/test_migration_119.py:201:    # partners checks
apps/backend-rag/backend/tests/migrations/test_migration_119.py:207:    # partner_referrals check
apps/backend-rag/backend/tests/migrations/test_migration_119.py:210:    # partner_commissions checks
apps/backend-rag/backend/tests/migrations/test_migration_119.py:221:    "idx_partners_email",
apps/backend-rag/backend/tests/migrations/test_migration_119.py:222:    "idx_partners_assigned_to",
apps/backend-rag/backend/tests/migrations/test_migration_119.py:223:    "idx_partners_onboarding_status",
apps/backend-rag/backend/tests/migrations/test_migration_119.py:224:    "idx_partners_entity_type",
apps/backend-rag/backend/tests/migrations/test_migration_119.py:225:    "idx_partner_referrals_partner_id",
apps/backend-rag/backend/tests/migrations/test_migration_119.py:226:    "idx_partner_referrals_process_id",
apps/backend-rag/backend/tests/migrations/test_migration_119.py:227:    "idx_partner_commissions_partner_id",
apps/backend-rag/backend/tests/migrations/test_migration_119.py:228:    "idx_partner_commissions_process_id",
apps/backend-rag/backend/tests/migrations/test_migration_119.py:229:    "idx_partner_commissions_status",
apps/backend-rag/backend/tests/migrations/test_migration_119.py:230:    "idx_partner_commissions_eligible_at",
apps/backend-rag/backend/tests/migrations/test_migration_119.py:231:    "idx_partner_commissions_assigned_to_snapshot",
apps/backend-rag/backend/tests/migrations/test_migration_119.py:232:    "idx_partner_audit_log_partner_id",
apps/backend-rag/backend/tests/migrations/test_migration_119.py:233:    "idx_partner_audit_log_at",
apps/backend-rag/backend/tests/migrations/test_migration_119.py:234:    "idx_users_partner_id",
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:1:# tests/services/crm/partners/test_events.py
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:3:EventBus handler tests for the partners module (Task 6).
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:6:register_partner_handlers.  Because the real get_pool() would require a
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:16:from backend.services.crm.partners.events import (
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:19:    register_partner_handlers,
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:53:    partner_factory,
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:58:    import backend.services.crm.partners.events as _events_mod
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:66:    row = await db_conn.fetchrow("SELECT COUNT(*) AS n FROM partner_commissions")
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:78:    partner_factory,
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:84:    import backend.services.crm.partners.events as _events_mod
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:86:    p = await partner_factory(tax_withholding_category="exempt")
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:92:    await referral_factory(partner_id=p, process_id=proc_id)
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:99:        "SELECT COUNT(*) AS n FROM partner_commissions WHERE partner_id = $1",
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:106:# 3. register_partner_handlers wires the bus
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:111:async def test_register_partner_handlers_subscribes_to_bus():
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:112:    """register_partner_handlers must subscribe to practice.status_changed."""
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:113:    # EventBus requires db_dsn for full init, but subscribe() only touches
apps/backend-rag/backend/tests/services/crm/partners/test_events.py:116:    register_partner_handlers(bus)
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:1:# tests/services/crm/partners/test_commission_engine.py
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:5:All tests use the db_conn fixture (real asyncpg connection with partner
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:17:from backend.services.crm.partners.commission_engine import CommissionEngine
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:31:    engine, partner_factory, process_factory, referral_factory
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:33:    p = await partner_factory(
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:42:    await referral_factory(partner_id=p.id, process_id=proc.id)
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:46:    commissions = await engine.repo.list_commissions_for_partner(p.id)
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:65:    engine, partner_factory, process_factory, referral_factory
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:67:    p = await partner_factory()
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:69:    await referral_factory(partner_id=p.id, process_id=proc.id)
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:74:    commissions = await engine.repo.list_commissions_for_partner(p.id)
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:84:    engine, partner_factory, process_factory, referral_factory, admin
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:86:    p = await partner_factory(tax_withholding_category="exempt")
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:88:    await referral_factory(partner_id=p.id, process_id=proc.id)
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:91:    c = (await engine.repo.list_commissions_for_partner(p.id))[0]
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:103:    engine, partner_factory, process_factory, referral_factory, admin, db_conn
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:105:    p = await partner_factory(tax_withholding_category="tbd")
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:107:    await referral_factory(partner_id=p.id, process_id=proc.id)
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:110:    c = (await engine.repo.list_commissions_for_partner(p.id))[0]
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:114:        "UPDATE partner_commissions SET eligible_for_approval_at = now() - interval '1 day' "
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:128:    engine, partner_factory, process_factory, referral_factory
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:130:    p = await partner_factory(
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:140:    await referral_factory(partner_id=p.id, process_id=proc.id)
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:143:    c = (await engine.repo.list_commissions_for_partner(p.id))[0]
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:155:async def test_clawback_inserts_negative_row_with_fk(engine, partner_factory, admin):
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:156:    p = await partner_factory(tax_withholding_category="pph23")
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:158:        partner_id=p.id,
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:182:async def test_clawback_auto_writeoff_threshold(engine, partner_factory, admin, db_conn):
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:186:        "WHERE key = 'partner_clawback_auto_writeoff_idr'"
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:188:    p = await partner_factory()
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:190:        partner_id=p.id,
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:211:    engine, partner_factory, admin, db_conn
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:213:    p = await partner_factory(tax_withholding_category="exempt")
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:217:        partner_id=p.id,
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:229:    # withholding_category must be 'exempt' (matching the partner) so that
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:232:        partner_id=p.id,
apps/backend-rag/backend/tests/services/crm/partners/test_commission_engine.py:244:        "UPDATE partner_commissions SET eligible_for_approval_at = now() - interval '1 day' "
apps/backend-rag/backend/tests/integration/conftest.py:2:E2E integration conftest — re-exports all partner fixtures.
apps/backend-rag/backend/tests/integration/conftest.py:4:The partner unit-test conftest.py is a standard Python file that defines
apps/backend-rag/backend/tests/integration/conftest.py:6:fixtures (db_conn, user_factory, partner_factory, process_factory,
apps/backend-rag/backend/tests/integration/conftest.py:10:from backend.tests.services.crm.partners.conftest import (  # noqa: F401
apps/backend-rag/backend/tests/integration/conftest.py:13:    partner_factory,
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:1:# tests/services/crm/partners/test_service.py
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:7:from backend.services.crm.partners.service import (
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:10:    verify_partner_access,
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:20:async def test_create_partner_writes_audit_log(svc, user_factory):
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:22:    pid = await svc.create_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:36:async def test_activate_partner_requires_admin_and_audits(svc, user_factory):
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:39:    pid = await svc.create_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:46:        await svc.activate_partner(pid, actor_user=team)
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:49:    await svc.activate_partner(pid, actor_user=admin)
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:50:    p = await svc.get_partner(pid, actor_user=admin)
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:57:async def test_verify_partner_access_admin_always_allowed(svc, user_factory, partner_factory):
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:59:    # partner_factory returns a UUID
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:60:    partner_id = await partner_factory(assigned_to=None)
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:61:    result = await verify_partner_access(svc, admin, partner_id)
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:63:    assert result.id == partner_id
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:67:async def test_verify_partner_access_team_must_own(svc, user_factory, partner_factory):
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:70:    # partner_factory returns a UUID
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:71:    partner_id = await partner_factory(assigned_to=u1)
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:73:    result = await verify_partner_access(svc, u1, partner_id)
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:74:    assert result.id == partner_id
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:77:        await verify_partner_access(svc, u2, partner_id)
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:86:    pid = await svc.create_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:94:        await svc.reassign_partner(pid, new_user_id=u2, actor_user=admin, reason=None)
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:95:    await svc.reassign_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:104:async def test_orphan_partners_on_team_user_deactivation(svc, user_factory):
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:107:    p1 = await svc.create_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:114:    p2 = await svc.create_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:121:    n = await svc.orphan_partners_of_user(u, actor_user=admin)
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:124:        p = await svc.get_partner(pid, actor_user=admin)
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:131:async def test_update_partner_does_not_reset_welcome_email_sent(svc, user_factory):
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:132:    """update_partner must NOT touch welcome_email_sent_at."""
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:134:    pid = await svc.create_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:144:    p_before = await svc.get_partner(pid, actor_user=admin)
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:148:    await svc.update_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:156:    p_after = await svc.get_partner(pid, actor_user=admin)
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:162:async def test_deactivate_partner_soft_delete_preserves_history(
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:167:    pid = await svc.create_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:174:    await referral_factory(partner_id=pid)
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:177:    await svc.deactivate_partner(pid, actor_user=admin)
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:180:    p = await svc.get_partner(pid, actor_user=admin)
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:184:    referrals = await svc.repo.list_referrals_for_partner(pid)
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:193:async def test_create_rejects_partner_with_internal_email(svc, user_factory):
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:194:    """create_partner raises ConflictError (409) when email matches a team/admin user."""
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:197:        await svc.create_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:207:async def test_reassign_nonexistent_partner_raises_404(db_conn, user_factory):
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:208:    """reassign_partner raises HTTPException(404) when partner_id is unknown."""
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:212:        await svc.reassign_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:220:async def test_update_partner_rejects_partner_role_self_update(
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:221:    db_conn, user_factory, partner_factory,
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:223:    """update_partner rejects partner-role actor at service layer (spec §7.2)."""
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:224:    partner_id = await partner_factory()
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:225:    # Link a partner-role user to this partner
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:226:    partner_user = await user_factory(role="partner")
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:228:        "UPDATE users SET partner_id = $2 WHERE id = $1",
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:229:        partner_user, partner_id,
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:233:        await svc.update_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:234:            partner_id,
apps/backend-rag/backend/tests/services/crm/partners/test_service.py:235:            actor_user=partner_user, actor_role="partner",
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:2:Local conftest for partners repository tests.
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:5:- db_conn: a real asyncpg.Connection with all partner tables created for the test,
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:7:- user_factory, partner_factory, process_factory, referral_factory: helpers
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:15:that heavy __init__ when we import the partners sub-package.
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:71:# __file__ = .../apps/backend-rag/backend/tests/services/crm/partners/conftest.py
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:78:                    os.path.dirname(  # partners/
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:119:    partner_id UUID
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:147:    ('partner_clawback_auto_writeoff_idr', '0'),
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:148:    ('partner_accrual_cooling_off_days',   '30')
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:151:CREATE TABLE IF NOT EXISTS partners (
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:192:CREATE TABLE IF NOT EXISTS partner_referrals (
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:194:    partner_id           UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:201:    CONSTRAINT partner_referrals_process_unique_v1 UNIQUE (process_id)
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:204:CREATE TABLE IF NOT EXISTS partner_commissions (
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:206:    partner_id               UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:207:    referral_id              UUID REFERENCES partner_referrals(id) ON DELETE RESTRICT,
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:211:    related_commission_id    UUID REFERENCES partner_commissions(id) ON DELETE RESTRICT,
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:216:    rule_source              TEXT NOT NULL DEFAULT 'partner_default'
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:217:        CHECK (rule_source IN ('partner_default','manual_override')),
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:251:CREATE TABLE IF NOT EXISTS partner_audit_log (
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:253:    partner_id    UUID NOT NULL REFERENCES partners(id) ON DELETE RESTRICT,
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:264:DROP TABLE IF EXISTS partner_audit_log;
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:265:DROP TABLE IF EXISTS partner_commissions;
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:266:DROP TABLE IF EXISTS partner_referrals;
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:267:DROP TABLE IF EXISTS partners;
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:277:    Real asyncpg connection with all partner tables created for the test,
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:352:def partner_factory(db_conn: asyncpg.Connection) -> Callable[..., Coroutine[Any, Any, _UUIDWithId]]:
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:353:    """Returns an async callable that inserts a partner and returns its UUID.
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:375:        _email = email or f"partner-{_counter[0]}-{uuid.uuid4().hex[:6]}@test.invalid"
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:378:            INSERT INTO partners
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:399:    """Returns an async callable that inserts a partner_referral and returns its UUID."""
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:402:        partner_id: uuid.UUID,
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:409:            INSERT INTO partner_referrals (partner_id, process_id, share_percent)
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:413:            partner_id, _process_id, share_percent,
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:469:    """Returns an async callable that inserts a partner_commissions row and returns its UUID.
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:472:    - partner_id: UUID (required)
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:485:        partner_id: uuid.UUID,
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:517:            INSERT INTO partner_commissions (
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:518:                partner_id, process_id,
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:530:                'partner_default',
apps/backend-rag/backend/tests/services/crm/partners/conftest.py:538:            uuid.UUID(int=partner_id.int),
apps/backend-rag/backend/tests/routers/test_partners.py:10:  - fake_admin / fake_team / fake_partner: user dicts
apps/backend-rag/backend/tests/routers/test_partners.py:27:import backend.app.routers.partners as partners_module
apps/backend-rag/backend/tests/routers/test_partners.py:29:from backend.services.crm.partners.models import Partner
apps/backend-rag/backend/tests/routers/test_partners.py:42:def _make_partner(**overrides: Any) -> Partner:
apps/backend-rag/backend/tests/routers/test_partners.py:47:        email="partner@test.invalid",
apps/backend-rag/backend/tests/routers/test_partners.py:63:def _partner_dict(**overrides: Any) -> dict[str, Any]:
apps/backend-rag/backend/tests/routers/test_partners.py:68:        "email": "partner@test.invalid",
apps/backend-rag/backend/tests/routers/test_partners.py:99:def fake_partner_user() -> dict[str, Any]:
apps/backend-rag/backend/tests/routers/test_partners.py:100:    return {"user_id": str(_USER_ID), "email": "partner@balizero.com", "role": "partner", "permissions": []}
apps/backend-rag/backend/tests/routers/test_partners.py:107:    application.include_router(partners_module.router)
apps/backend-rag/backend/tests/routers/test_partners.py:128:def partner_app(fake_partner_user, mock_db_pool) -> tuple[FastAPI, TestClient, MagicMock, AsyncMock]:
apps/backend-rag/backend/tests/routers/test_partners.py:130:    app = _make_app(fake_partner_user, pool)
apps/backend-rag/backend/tests/routers/test_partners.py:134:# ── 1. create_partner — team auto-assigns self ───────────────────────────────
apps/backend-rag/backend/tests/routers/test_partners.py:139:        assert partners_module.router.prefix == "/api/partners"
apps/backend-rag/backend/tests/routers/test_partners.py:140:        paths = {route.path for route in partners_module.router.routes}
apps/backend-rag/backend/tests/routers/test_partners.py:141:        assert "/api/partners" in paths
apps/backend-rag/backend/tests/routers/test_partners.py:142:        assert "/api/partners/{partner_id}" in paths
apps/backend-rag/backend/tests/routers/test_partners.py:145:    def test_partner_create_model_validation(self) -> None:
apps/backend-rag/backend/tests/routers/test_partners.py:146:        payload = partners_module.PartnerCreate.model_validate({
apps/backend-rag/backend/tests/routers/test_partners.py:156:    def test_create_partner_team_auto_assigns_self(self, team_app, fake_team) -> None:
apps/backend-rag/backend/tests/routers/test_partners.py:158:        partner = _make_partner(assigned_to=uuid.UUID(fake_team["user_id"]))
apps/backend-rag/backend/tests/routers/test_partners.py:160:            patch("backend.app.routers.partners.PartnersService") as MockSvc,
apps/backend-rag/backend/tests/routers/test_partners.py:163:            svc_instance.create_partner = AsyncMock(return_value=_PARTNER_ID)
apps/backend-rag/backend/tests/routers/test_partners.py:165:            svc_instance.repo.get_partner = AsyncMock(return_value=partner)
apps/backend-rag/backend/tests/routers/test_partners.py:168:                "/api/partners",
apps/backend-rag/backend/tests/routers/test_partners.py:172:        # Verify create_partner was called with the team user's ID as assigned_to
apps/backend-rag/backend/tests/routers/test_partners.py:173:        call_kwargs = svc_instance.create_partner.await_args.kwargs
apps/backend-rag/backend/tests/routers/test_partners.py:177:    def test_create_partner_missing_required_fields_422(self, admin_app) -> None:
apps/backend-rag/backend/tests/routers/test_partners.py:179:        resp = client.post("/api/partners", json={"full_name": "No Email"})
apps/backend-rag/backend/tests/routers/test_partners.py:183:    def test_create_partner_conflict_409(self, admin_app) -> None:
apps/backend-rag/backend/tests/routers/test_partners.py:185:        from backend.services.crm.partners.service import ConflictError
apps/backend-rag/backend/tests/routers/test_partners.py:186:        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
apps/backend-rag/backend/tests/routers/test_partners.py:188:            svc_instance.create_partner = AsyncMock(
apps/backend-rag/backend/tests/routers/test_partners.py:192:                "/api/partners",
apps/backend-rag/backend/tests/routers/test_partners.py:198:    def test_create_partner_collision_with_internal_email_409(self, admin_app) -> None:
apps/backend-rag/backend/tests/routers/test_partners.py:200:        from backend.services.crm.partners.service import ConflictError
apps/backend-rag/backend/tests/routers/test_partners.py:201:        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
apps/backend-rag/backend/tests/routers/test_partners.py:203:            svc_instance.create_partner = AsyncMock(
apps/backend-rag/backend/tests/routers/test_partners.py:207:                "/api/partners",
apps/backend-rag/backend/tests/routers/test_partners.py:213:# ── 2. list_partners ─────────────────────────────────────────────────────────
apps/backend-rag/backend/tests/routers/test_partners.py:217:    def test_list_partners_admin_returns_all(self, admin_app) -> None:
apps/backend-rag/backend/tests/routers/test_partners.py:219:        partner = _make_partner()
apps/backend-rag/backend/tests/routers/test_partners.py:220:        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
apps/backend-rag/backend/tests/routers/test_partners.py:222:            svc_instance.list_partners = AsyncMock(return_value=[partner])
apps/backend-rag/backend/tests/routers/test_partners.py:223:            resp = client.get("/api/partners")
apps/backend-rag/backend/tests/routers/test_partners.py:229:    def test_list_partners_team_scopes_to_self(self, team_app, fake_team) -> None:
apps/backend-rag/backend/tests/routers/test_partners.py:231:        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
apps/backend-rag/backend/tests/routers/test_partners.py:233:            svc_instance.list_partners = AsyncMock(return_value=[])
apps/backend-rag/backend/tests/routers/test_partners.py:234:            resp = client.get("/api/partners")
apps/backend-rag/backend/tests/routers/test_partners.py:237:        call_kwargs = svc_instance.list_partners.await_args.kwargs
apps/backend-rag/backend/tests/routers/test_partners.py:242:# ── 3. get_partner ────────────────────────────────────────────────────────────
apps/backend-rag/backend/tests/routers/test_partners.py:246:    def test_get_partner_admin_sees_any(self, admin_app) -> None:
apps/backend-rag/backend/tests/routers/test_partners.py:248:        partner = _make_partner()
apps/backend-rag/backend/tests/routers/test_partners.py:249:        with patch("backend.app.routers.partners.verify_partner_access_with_role") as mock_verify:
apps/backend-rag/backend/tests/routers/test_partners.py:251:                return partner
apps/backend-rag/backend/tests/routers/test_partners.py:253:            resp = client.get(f"/api/partners/{_PARTNER_ID}")
apps/backend-rag/backend/tests/routers/test_partners.py:257:    def test_get_partner_not_found_returns_404(self, admin_app) -> None:
apps/backend-rag/backend/tests/routers/test_partners.py:260:        with patch("backend.app.routers.partners.verify_partner_access_with_role") as mock_verify:
apps/backend-rag/backend/tests/routers/test_partners.py:262:                raise HTTPException(status_code=404, detail="partner not found")
apps/backend-rag/backend/tests/routers/test_partners.py:264:            resp = client.get(f"/api/partners/{_PARTNER_ID}")
apps/backend-rag/backend/tests/routers/test_partners.py:268:# ── 4. update_partner ─────────────────────────────────────────────────────────
apps/backend-rag/backend/tests/routers/test_partners.py:272:    def test_patch_partner_team_can_update_own(self, team_app) -> None:
apps/backend-rag/backend/tests/routers/test_partners.py:274:        partner = _make_partner(full_name="Updated Name")
apps/backend-rag/backend/tests/routers/test_partners.py:275:        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
apps/backend-rag/backend/tests/routers/test_partners.py:277:            svc_instance.update_partner = AsyncMock()
apps/backend-rag/backend/tests/routers/test_partners.py:279:            svc_instance.repo.get_partner = AsyncMock(return_value=partner)
apps/backend-rag/backend/tests/routers/test_partners.py:281:                f"/api/partners/{_PARTNER_ID}",
apps/backend-rag/backend/tests/routers/test_partners.py:285:        svc_instance.update_partner.assert_awaited_once()
apps/backend-rag/backend/tests/routers/test_partners.py:288:    def test_patch_partner_team_forbidden_on_other(self, team_app) -> None:
apps/backend-rag/backend/tests/routers/test_partners.py:291:        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
apps/backend-rag/backend/tests/routers/test_partners.py:293:            svc_instance.update_partner = AsyncMock(
apps/backend-rag/backend/tests/routers/test_partners.py:297:                f"/api/partners/{_PARTNER_ID}",
apps/backend-rag/backend/tests/routers/test_partners.py:310:        resp = client.post(f"/api/partners/{_PARTNER_ID}/activate")
apps/backend-rag/backend/tests/routers/test_partners.py:316:        with patch("backend.app.routers.partners.PartnersService") as MockSvc, \
apps/backend-rag/backend/tests/routers/test_partners.py:317:             patch("backend.services.crm.partners.emails.send_welcome", new=AsyncMock()):
apps/backend-rag/backend/tests/routers/test_partners.py:319:            svc_instance.activate_partner = AsyncMock()
apps/backend-rag/backend/tests/routers/test_partners.py:320:            resp = client.post(f"/api/partners/{_PARTNER_ID}/activate")
apps/backend-rag/backend/tests/routers/test_partners.py:326:        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
apps/backend-rag/backend/tests/routers/test_partners.py:328:            svc_instance.deactivate_partner = AsyncMock()
apps/backend-rag/backend/tests/routers/test_partners.py:329:            resp = client.post(f"/api/partners/{_PARTNER_ID}/deactivate")
apps/backend-rag/backend/tests/routers/test_partners.py:336:        resp = client.post(f"/api/partners/{_PARTNER_ID}/deactivate")
apps/backend-rag/backend/tests/routers/test_partners.py:346:        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
apps/backend-rag/backend/tests/routers/test_partners.py:348:            svc_instance.reassign_partner = AsyncMock()
apps/backend-rag/backend/tests/routers/test_partners.py:350:                f"/api/partners/{_PARTNER_ID}/reassign",
apps/backend-rag/backend/tests/routers/test_partners.py:358:        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
apps/backend-rag/backend/tests/routers/test_partners.py:360:            svc_instance.reassign_partner = AsyncMock(
apps/backend-rag/backend/tests/routers/test_partners.py:364:                f"/api/partners/{_PARTNER_ID}/reassign",
apps/backend-rag/backend/tests/routers/test_partners.py:374:            f"/api/partners/{_PARTNER_ID}/reassign",
apps/backend-rag/backend/tests/routers/test_partners.py:382:        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
apps/backend-rag/backend/tests/routers/test_partners.py:384:            svc_instance.reassign_partner = AsyncMock()
apps/backend-rag/backend/tests/routers/test_partners.py:386:                "/api/partners/bulk-reassign",
apps/backend-rag/backend/tests/routers/test_partners.py:388:                    "partner_ids": [str(_PARTNER_ID)],
apps/backend-rag/backend/tests/routers/test_partners.py:400:            "/api/partners/bulk-reassign",
apps/backend-rag/backend/tests/routers/test_partners.py:402:                "partner_ids": [str(_PARTNER_ID)],
apps/backend-rag/backend/tests/routers/test_partners.py:416:        r.partner_id = _PARTNER_ID
apps/backend-rag/backend/tests/routers/test_partners.py:429:            patch("backend.app.routers.partners.verify_partner_access_with_role") as mock_verify,
apps/backend-rag/backend/tests/routers/test_partners.py:430:            patch("backend.app.routers.partners.PartnersService") as MockSvc,
apps/backend-rag/backend/tests/routers/test_partners.py:433:                return _make_partner()
apps/backend-rag/backend/tests/routers/test_partners.py:437:            svc_instance.repo.list_referrals_for_partner = AsyncMock(return_value=[ref])
apps/backend-rag/backend/tests/routers/test_partners.py:438:            resp = client.get(f"/api/partners/{_PARTNER_ID}/referrals")
apps/backend-rag/backend/tests/routers/test_partners.py:446:            patch("backend.app.routers.partners.verify_partner_access_with_role") as mock_verify,
apps/backend-rag/backend/tests/routers/test_partners.py:447:            patch("backend.app.routers.partners.PartnersService") as MockSvc,
apps/backend-rag/backend/tests/routers/test_partners.py:450:                return _make_partner()
apps/backend-rag/backend/tests/routers/test_partners.py:456:                f"/api/partners/{_PARTNER_ID}/referrals",
apps/backend-rag/backend/tests/routers/test_partners.py:470:            patch("backend.app.routers.partners.verify_partner_access_with_role") as mock_verify,
apps/backend-rag/backend/tests/routers/test_partners.py:471:            patch("backend.app.routers.partners.PartnersService") as MockSvc,
apps/backend-rag/backend/tests/routers/test_partners.py:474:                return _make_partner()
apps/backend-rag/backend/tests/routers/test_partners.py:479:                side_effect=Exception("unique constraint violation on partner_referrals_process_unique_v1")
apps/backend-rag/backend/tests/routers/test_partners.py:482:                f"/api/partners/{_PARTNER_ID}/referrals",
apps/backend-rag/backend/tests/routers/test_partners.py:490:        new_partner_id = uuid.uuid4()
apps/backend-rag/backend/tests/routers/test_partners.py:491:        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
apps/backend-rag/backend/tests/routers/test_partners.py:494:            svc_instance.repo.update_referral_partner = AsyncMock()
apps/backend-rag/backend/tests/routers/test_partners.py:496:                f"/api/partners/referrals/{_REFERRAL_ID}",
apps/backend-rag/backend/tests/routers/test_partners.py:497:                json={"new_partner_id": str(new_partner_id)},
apps/backend-rag/backend/tests/routers/test_partners.py:504:        new_partner_id = uuid.uuid4()
apps/backend-rag/backend/tests/routers/test_partners.py:506:            f"/api/partners/referrals/{_REFERRAL_ID}",
apps/backend-rag/backend/tests/routers/test_partners.py:507:            json={"new_partner_id": str(new_partner_id)},
apps/backend-rag/backend/tests/routers/test_partners.py:514:        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
apps/backend-rag/backend/tests/routers/test_partners.py:518:            resp = client.delete(f"/api/partners/referrals/{_REFERRAL_ID}")
apps/backend-rag/backend/tests/routers/test_partners.py:524:        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
apps/backend-rag/backend/tests/routers/test_partners.py:530:            resp = client.delete(f"/api/partners/referrals/{_REFERRAL_ID}")
apps/backend-rag/backend/tests/routers/test_partners.py:536:        resp = client.delete(f"/api/partners/referrals/{_REFERRAL_ID}")
apps/backend-rag/backend/tests/routers/test_partners.py:547:            patch("backend.app.routers.partners.verify_partner_access_with_role") as mock_verify,
apps/backend-rag/backend/tests/routers/test_partners.py:548:            patch("backend.app.routers.partners.PartnersService") as MockSvc,
apps/backend-rag/backend/tests/routers/test_partners.py:551:                return _make_partner()
apps/backend-rag/backend/tests/routers/test_partners.py:555:            svc_instance.repo.list_commissions_for_partner = AsyncMock(return_value=[])
apps/backend-rag/backend/tests/routers/test_partners.py:556:            resp = client.get(f"/api/partners/{_PARTNER_ID}/commissions")
apps/backend-rag/backend/tests/routers/test_partners.py:563:        with patch("backend.app.routers.partners.CommissionEngine") as MockEngine:
apps/backend-rag/backend/tests/routers/test_partners.py:566:            resp = client.post(f"/api/partners/commissions/{_COMMISSION_ID}/approve")
apps/backend-rag/backend/tests/routers/test_partners.py:572:        resp = client.post(f"/api/partners/commissions/{_COMMISSION_ID}/approve")
apps/backend-rag/backend/tests/routers/test_partners.py:578:        with patch("backend.app.routers.partners.CommissionEngine") as MockEngine, \
apps/backend-rag/backend/tests/routers/test_partners.py:579:             patch("backend.services.crm.partners.emails.send_commission_earned", new=AsyncMock()):
apps/backend-rag/backend/tests/routers/test_partners.py:583:                f"/api/partners/commissions/{_COMMISSION_ID}/mark-paid",
apps/backend-rag/backend/tests/routers/test_partners.py:592:            f"/api/partners/commissions/{_COMMISSION_ID}/mark-paid",
apps/backend-rag/backend/tests/routers/test_partners.py:602:        with patch("backend.app.routers.partners.CommissionEngine") as MockEngine:
apps/backend-rag/backend/tests/routers/test_partners.py:606:                f"/api/partners/commissions/{_COMMISSION_ID}/clawback",
apps/backend-rag/backend/tests/routers/test_partners.py:616:            f"/api/partners/commissions/{_COMMISSION_ID}/clawback",
apps/backend-rag/backend/tests/routers/test_partners.py:624:        with patch("backend.app.routers.partners.CommissionEngine") as MockEngine:
apps/backend-rag/backend/tests/routers/test_partners.py:628:                f"/api/partners/commissions/{_COMMISSION_ID}/waive",
apps/backend-rag/backend/tests/routers/test_partners.py:637:            f"/api/partners/commissions/{_COMMISSION_ID}/waive",
apps/backend-rag/backend/tests/routers/test_partners.py:649:        resp = client.get("/api/partners/me")
apps/backend-rag/backend/tests/routers/test_partners.py:653:    def test_me_partner_returns_own_profile(self, partner_app) -> None:
apps/backend-rag/backend/tests/routers/test_partners.py:654:        _, client, pool, conn = partner_app
apps/backend-rag/backend/tests/routers/test_partners.py:655:        partner = _make_partner()
apps/backend-rag/backend/tests/routers/test_partners.py:656:        # asyncpg Record-like dict for "SELECT partner_id FROM users ..."
apps/backend-rag/backend/tests/routers/test_partners.py:657:        conn.fetchrow = AsyncMock(return_value={"partner_id": _PARTNER_ID})
apps/backend-rag/backend/tests/routers/test_partners.py:658:        with patch("backend.app.routers.partners.PartnersService") as MockSvc:
apps/backend-rag/backend/tests/routers/test_partners.py:661:            svc_instance.repo.get_partner = AsyncMock(return_value=partner)
apps/backend-rag/backend/tests/routers/test_partners.py:662:            resp = client.get("/api/partners/me")
apps/backend-rag/backend/tests/routers/test_partners.py:666:    def test_me_no_partner_id_linked_403(self, partner_app) -> None:
apps/backend-rag/backend/tests/routers/test_partners.py:667:        _, client, pool, conn = partner_app
apps/backend-rag/backend/tests/routers/test_partners.py:668:        conn.fetchrow = AsyncMock(return_value={"partner_id": None})
apps/backend-rag/backend/tests/routers/test_partners.py:669:        resp = client.get("/api/partners/me")
apps/backend-rag/backend/tests/routers/test_partners.py:675:        resp = client.get("/api/partners/me/referrals")
apps/backend-rag/backend/tests/routers/test_partners.py:679:    def test_me_referrals_sterilizes_client_name(self, partner_app) -> None:
apps/backend-rag/backend/tests/routers/test_partners.py:681:        _, client, pool, conn = partner_app
apps/backend-rag/backend/tests/routers/test_partners.py:682:        # First fetchrow: partner_id lookup
apps/backend-rag/backend/tests/routers/test_partners.py:683:        conn.fetchrow = AsyncMock(return_value={"partner_id": _PARTNER_ID})
apps/backend-rag/backend/tests/routers/test_partners.py:695:        resp = client.get("/api/partners/me/referrals")
apps/backend-rag/backend/tests/routers/test_partners.py:708:        resp = client.get("/api/partners/me/commissions")
apps/backend-rag/backend/tests/routers/test_partners.py:741:        resp = client.get("/api/partners/finance/export?from=2026-01-01&to=2026-04-30")
apps/backend-rag/backend/tests/routers/test_partners.py:750:        resp = client.get("/api/partners/finance/export?from=2026-01-01&to=2026-04-30")
apps/backend-rag/backend/tests/routers/test_partners.py:754:        assert "partner" in first_line
apps/backend-rag/backend/tests/routers/test_partners.py:760:        resp = client.get("/api/partners/finance/export?from=2026-01-01&to=2026-04-30")
apps/backend-rag/backend/tests/routers/test_partners.py:767:        resp = client.get("/api/partners/finance/export?from=2026-01-01&to=2026-04-30")
apps/backend-rag/backend/tests/routers/test_partners.py:770:        assert "partners-2026-01-01-to-2026-04-30.csv" in resp.headers["content-disposition"]
apps/backend-rag/backend/tests/routers/test_partners.py:775:        resp = client.get("/api/partners/finance/export?from=yesterday&to=tomorrow")
apps/backend-rag/backend/tests/routers/test_partners.py:785:        assert partners_module._sterilize_client_for_partner("Mario Rossi") == "Mario R."
apps/backend-rag/backend/tests/routers/test_partners.py:789:        assert partners_module._sterilize_client_for_partner("Siti") == "Siti"
apps/backend-rag/backend/tests/routers/test_partners.py:793:        result = partners_module._sterilize_client_for_partner("Maria Angela Gomez")
apps/backend-rag/backend/tests/routers/test_partners.py:798:        assert partners_module._sterilize_client_for_partner("") == ""
apps/backend-rag/backend/tests/routers/test_partners.py:809:        entry1.partner_id = _PARTNER_ID
apps/backend-rag/backend/tests/routers/test_partners.py:818:        entry2.partner_id = _PARTNER_ID
apps/backend-rag/backend/tests/routers/test_partners.py:826:            patch("backend.app.routers.partners.verify_partner_access_with_role") as mock_verify,
apps/backend-rag/backend/tests/routers/test_partners.py:827:            patch("backend.app.routers.partners.PartnersService") as MockSvc,
apps/backend-rag/backend/tests/routers/test_partners.py:830:                return _make_partner()
apps/backend-rag/backend/tests/routers/test_partners.py:834:            resp = client.get(f"/api/partners/{_PARTNER_ID}/audit-log")
apps/backend-rag/backend/tests/routers/test_partners.py:840:    def test_list_audit_log_team_forbidden_for_other_partner(self, team_app) -> None:
apps/backend-rag/backend/tests/routers/test_partners.py:844:            patch("backend.app.routers.partners.verify_partner_access_with_role") as mock_verify,
apps/backend-rag/backend/tests/routers/test_partners.py:845:            patch("backend.app.routers.partners.PartnersService"),
apps/backend-rag/backend/tests/routers/test_partners.py:850:            resp = client.get(f"/api/partners/{_PARTNER_ID}/audit-log")
apps/backend-rag/backend/tests/routers/test_partners.py:860:        partners_module._require_finance(user)  # must not raise
apps/backend-rag/backend/tests/routers/test_partners.py:866:        partners_module._require_finance(user)  # must not raise
apps/backend-rag/backend/tests/routers/test_partners.py:873:            partners_module._require_finance(user)
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:1:# tests/services/crm/partners/test_repository.py
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:6:that creates the partner tables fresh for each test run and drops them in
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:15:from backend.services.crm.partners.repository import PartnersRepository
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:27:async def _make_commission(repo: PartnersRepository, partner_id, **kwargs) -> str:
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:30:        partner_id=partner_id,
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:44:# 1. insert_partner defaults
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:48:async def test_insert_partner_returns_id_and_defaults(repo):
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:49:    pid = await repo.insert_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:54:    p = await repo.get_partner(pid)
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:69:    await repo.insert_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:73:        await repo.insert_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:89:        await repo.insert_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:97:# 4. list_partners filter by assigned_to
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:101:async def test_list_partners_filters_by_assigned_to(repo, user_factory):
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:104:    p1 = await repo.insert_partner(full_name="P1", email="p1@x.io",
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:106:    _ = await repo.insert_partner(full_name="P2", email="p2@x.io",
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:108:    results = await repo.list_partners(assigned_to=u1)
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:119:    pid = await repo.insert_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:123:        partner_id=pid,
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:143:    pid = await repo.insert_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:147:        partner_id=pid, entry_type="accrual",
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:157:            partner_id=pid, entry_type="accrual",
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:168:# 7. update_partner whitelist rejects status column
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:172:async def test_update_partner_whitelist_rejects_status_column(repo):
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:173:    pid = await repo.insert_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:177:        await repo.update_partner(pid, onboarding_status="active")
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:181:# 8. activate_partner transitions status
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:185:async def test_activate_partner_transitions_status(repo):
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:186:    pid = await repo.insert_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:189:    p = await repo.get_partner(pid)
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:192:    await repo.activate_partner(pid)
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:193:    p = await repo.get_partner(pid)
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:196:    # idempotent — calling again on already-active partner is a no-op (no row updated, no error)
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:197:    await repo.activate_partner(pid)
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:198:    p = await repo.get_partner(pid)
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:203:# 9. deactivate_partner sets status and deactivated_at
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:207:async def test_deactivate_partner_sets_status_and_timestamp(repo):
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:208:    pid = await repo.insert_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:211:    await repo.activate_partner(pid)
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:212:    await repo.deactivate_partner(pid)
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:213:    p = await repo.get_partner(pid)
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:219:# 10. reassign_partner changes assigned_to
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:223:async def test_reassign_partner_changes_assigned_to(repo, user_factory):
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:226:    pid = await repo.insert_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:230:    p = await repo.get_partner(pid)
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:233:    await repo.reassign_partner(pid, u2)
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:234:    p = await repo.get_partner(pid)
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:239:# 11. orphan_partners_of_user
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:243:async def test_orphan_partners_of_user(repo, user_factory):
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:245:    # Insert two partners assigned to user u, plus one not assigned
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:246:    await repo.insert_partner(full_name="Op1", email="op1@h.io",
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:248:    await repo.insert_partner(full_name="Op2", email="op2@h.io",
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:250:    await repo.insert_partner(full_name="Op3", email="op3@h.io",
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:253:    count = await repo.orphan_partners_of_user(u)
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:256:    # All partners of u should now have assigned_to = NULL
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:257:    results = await repo.list_partners(assigned_to=u)
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:261:    orphaned = await repo.list_partners(orphaned=True)
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:274:    pid = await repo.insert_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:278:    await repo.insert_referral(partner_id=pid, process_id=process_id)
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:280:        await repo.insert_referral(partner_id=pid, process_id=process_id)
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:289:    pid = await repo.insert_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:309:    pid = await repo.insert_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:325:    pid = await repo.insert_partner(
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:331:        partner_id=pid,
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:339:        partner_id=pid,
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:347:    entries = await repo.list_audit_for_partner(pid)
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:358:# 16. update_partner rejects empty fields dict
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:362:async def test_update_partner_rejects_empty_fields(repo, partner_factory):
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:363:    p = await partner_factory()
apps/backend-rag/backend/tests/services/crm/partners/test_repository.py:365:        await repo.update_partner(p)
apps/backend-rag/backend/tests/unit/routers/test_auth_auto_clockin.py:128:            email="partner@other-company.com",
apps/backend-rag/backend/tests/services/rag/test_kg_cache_proactive.py:104:    async def subscribe(self, channel: str) -> None:
apps/backend-rag/backend/tests/services/rag/test_kg_cache_proactive.py:107:    async def unsubscribe(self, channel: str) -> None:
apps/backend-rag/backend/tests/unit/services/test_event_bus.py:9:from backend.services.events.event_bus import EventBus, PG_CHANNEL_MAP
apps/backend-rag/backend/tests/unit/services/test_event_bus.py:28:        bus.subscribe("test.event", handler)
apps/backend-rag/backend/tests/unit/services/test_event_bus.py:46:        bus.subscribe("multi.event", handler_a)
apps/backend-rag/backend/tests/unit/services/test_event_bus.py:47:        bus.subscribe("multi.event", handler_b)
apps/backend-rag/backend/tests/unit/services/test_event_bus.py:68:        bus.subscribe("error.event", bad_handler)
apps/backend-rag/backend/tests/unit/services/test_event_bus.py:69:        bus.subscribe("error.event", good_handler)
apps/backend-rag/backend/tests/unit/services/test_event_bus.py:80:    async def test_unsubscribe(self, bus: EventBus) -> None:
apps/backend-rag/backend/tests/unit/services/test_event_bus.py:87:        bus.subscribe("unsub.event", handler)
apps/backend-rag/backend/tests/unit/services/test_event_bus.py:91:        bus.unsubscribe("unsub.event", handler)
apps/backend-rag/backend/tests/unit/services/test_event_bus.py:100:        bus.subscribe("timed.event", slow_handler)
apps/backend-rag/backend/tests/unit/services/test_event_bus.py:123:        bus.subscribe("stats.event", noop)
apps/backend-rag/backend/tests/unit/services/test_event_bus.py:137:        assert "practice_changed" in PG_CHANNEL_MAP
apps/backend-rag/backend/tests/unit/services/test_event_bus.py:138:        assert "client_changed" in PG_CHANNEL_MAP
apps/backend-rag/backend/tests/unit/services/test_event_bus.py:139:        assert "compliance_alert" in PG_CHANNEL_MAP
apps/backend-rag/backend/tests/unit/services/test_event_bus.py:142:        for event_type in PG_CHANNEL_MAP.values():
apps/backend-rag/backend/tests/unit/services/test_event_bus.py:156:        bus.subscribe("client.changed", handler)
apps/backend-rag/backend/app/routers/partners.py:4:21 endpoints covering partner lifecycle, referrals, commissions, self-serve
apps/backend-rag/backend/app/routers/partners.py:5:/me routes for partner-role users, and a finance CSV export.
apps/backend-rag/backend/app/routers/partners.py:14:- No partner_id in user dict; /me endpoints query users.partner_id from DB.
apps/backend-rag/backend/app/routers/partners.py:35:from backend.services.crm.partners.commission_engine import CommissionEngine
apps/backend-rag/backend/app/routers/partners.py:36:from backend.services.crm.partners.service import (
apps/backend-rag/backend/app/routers/partners.py:39:    verify_partner_access_with_role,
apps/backend-rag/backend/app/routers/partners.py:44:router = APIRouter(prefix="/api/partners", tags=["partners"])
apps/backend-rag/backend/app/routers/partners.py:110:    partner_ids: list[UUID]
apps/backend-rag/backend/app/routers/partners.py:121:    new_partner_id: UUID
apps/backend-rag/backend/app/routers/partners.py:164:def _sterilize_client_for_partner(full_name: str) -> str:
apps/backend-rag/backend/app/routers/partners.py:165:    """'Mario Rossi' → 'Mario R.' — hide client surname from partner-role user."""
apps/backend-rag/backend/app/routers/partners.py:174:def _partner_to_dict(p: Any) -> dict[str, Any]:
apps/backend-rag/backend/app/routers/partners.py:184:async def create_partner(
apps/backend-rag/backend/app/routers/partners.py:189:    """Create a new partner. Team members auto-assign to themselves."""
apps/backend-rag/backend/app/routers/partners.py:200:            pid = await svc.create_partner(
apps/backend-rag/backend/app/routers/partners.py:205:            partner = await svc.repo.get_partner(pid)
apps/backend-rag/backend/app/routers/partners.py:206:            return _partner_to_dict(partner)
apps/backend-rag/backend/app/routers/partners.py:210:        logger.exception("create_partner failed")
apps/backend-rag/backend/app/routers/partners.py:215:async def list_partners(
apps/backend-rag/backend/app/routers/partners.py:223:    """List partners. Team members see only their own."""
apps/backend-rag/backend/app/routers/partners.py:226:        partners = await svc.list_partners(
apps/backend-rag/backend/app/routers/partners.py:234:        return [_partner_to_dict(p) for p in partners]
apps/backend-rag/backend/app/routers/partners.py:242:    """Self-view for partner-role users. Returns their own partner record."""
apps/backend-rag/backend/app/routers/partners.py:243:    if user.get("role") != "partner":
apps/backend-rag/backend/app/routers/partners.py:244:        raise HTTPException(status_code=403, detail="partner role required")
apps/backend-rag/backend/app/routers/partners.py:247:            "SELECT partner_id FROM users WHERE id = $1",
apps/backend-rag/backend/app/routers/partners.py:250:        if not row or not row["partner_id"]:
apps/backend-rag/backend/app/routers/partners.py:251:            raise HTTPException(status_code=403, detail="no partner profile linked to this user")
apps/backend-rag/backend/app/routers/partners.py:253:        partner = await svc.repo.get_partner(row["partner_id"])
apps/backend-rag/backend/app/routers/partners.py:254:        if partner is None:
apps/backend-rag/backend/app/routers/partners.py:255:            raise HTTPException(status_code=404, detail="partner record not found")
apps/backend-rag/backend/app/routers/partners.py:256:        return _partner_to_dict(partner)
apps/backend-rag/backend/app/routers/partners.py:264:    """List referrals for the calling partner user. Client data is sterilized."""
apps/backend-rag/backend/app/routers/partners.py:265:    if user.get("role") != "partner":
apps/backend-rag/backend/app/routers/partners.py:266:        raise HTTPException(status_code=403, detail="partner role required")
apps/backend-rag/backend/app/routers/partners.py:269:            "SELECT partner_id FROM users WHERE id = $1",
apps/backend-rag/backend/app/routers/partners.py:272:        if not row or not row["partner_id"]:
apps/backend-rag/backend/app/routers/partners.py:273:            raise HTTPException(status_code=403, detail="no partner profile linked to this user")
apps/backend-rag/backend/app/routers/partners.py:274:        partner_id = row["partner_id"]
apps/backend-rag/backend/app/routers/partners.py:280:            FROM partner_referrals pr
apps/backend-rag/backend/app/routers/partners.py:283:            WHERE pr.partner_id = $1
apps/backend-rag/backend/app/routers/partners.py:286:            partner_id,
apps/backend-rag/backend/app/routers/partners.py:294:            "client_display": _sterilize_client_for_partner(r["client_name"] or ""),
apps/backend-rag/backend/app/routers/partners.py:306:    """List commissions for the calling partner user."""
apps/backend-rag/backend/app/routers/partners.py:307:    if user.get("role") != "partner":
apps/backend-rag/backend/app/routers/partners.py:308:        raise HTTPException(status_code=403, detail="partner role required")
apps/backend-rag/backend/app/routers/partners.py:311:            "SELECT partner_id FROM users WHERE id = $1",
apps/backend-rag/backend/app/routers/partners.py:314:        if not row or not row["partner_id"]:
apps/backend-rag/backend/app/routers/partners.py:315:            raise HTTPException(status_code=403, detail="no partner profile linked to this user")
apps/backend-rag/backend/app/routers/partners.py:317:        commissions = await svc.repo.list_commissions_for_partner(row["partner_id"])
apps/backend-rag/backend/app/routers/partners.py:348:                FROM partner_commissions pc
apps/backend-rag/backend/app/routers/partners.py:349:                JOIN partners p ON p.id = pc.partner_id
apps/backend-rag/backend/app/routers/partners.py:359:            "commission_id", "partner", "npwp", "entity_type", "entry_type",
apps/backend-rag/backend/app/routers/partners.py:369:                "Content-Disposition": f'attachment; filename="partners-{from_}-to-{to}.csv"'
apps/backend-rag/backend/app/routers/partners.py:379:@router.get("/{partner_id}")
apps/backend-rag/backend/app/routers/partners.py:380:async def get_partner(
apps/backend-rag/backend/app/routers/partners.py:381:    partner_id: UUID,
apps/backend-rag/backend/app/routers/partners.py:385:    """Get a partner by ID. Scoped by role."""
apps/backend-rag/backend/app/routers/partners.py:388:        partner = await verify_partner_access_with_role(
apps/backend-rag/backend/app/routers/partners.py:392:            partner_id,
apps/backend-rag/backend/app/routers/partners.py:394:        return _partner_to_dict(partner)
apps/backend-rag/backend/app/routers/partners.py:397:@router.patch("/{partner_id}")
apps/backend-rag/backend/app/routers/partners.py:398:async def update_partner(
apps/backend-rag/backend/app/routers/partners.py:399:    partner_id: UUID,
apps/backend-rag/backend/app/routers/partners.py:404:    """Update a partner. Team members can only update their own assigned partners."""
apps/backend-rag/backend/app/routers/partners.py:409:            await svc.update_partner(
apps/backend-rag/backend/app/routers/partners.py:410:                partner_id,
apps/backend-rag/backend/app/routers/partners.py:415:            partner = await svc.repo.get_partner(partner_id)
apps/backend-rag/backend/app/routers/partners.py:416:            return _partner_to_dict(partner)
apps/backend-rag/backend/app/routers/partners.py:420:        logger.exception("update_partner failed")
apps/backend-rag/backend/app/routers/partners.py:424:@router.post("/{partner_id}/activate", status_code=status.HTTP_204_NO_CONTENT)
apps/backend-rag/backend/app/routers/partners.py:425:async def activate_partner(
apps/backend-rag/backend/app/routers/partners.py:426:    partner_id: UUID,
apps/backend-rag/backend/app/routers/partners.py:430:    """Activate a partner. Admin only."""
apps/backend-rag/backend/app/routers/partners.py:435:            await svc.activate_partner(partner_id, actor_user=UUID(str(user["user_id"])))
apps/backend-rag/backend/app/routers/partners.py:438:                from backend.services.crm.partners.emails import send_welcome
apps/backend-rag/backend/app/routers/partners.py:439:                await send_welcome(conn, partner_id)
apps/backend-rag/backend/app/routers/partners.py:446:        logger.exception("activate_partner failed")
apps/backend-rag/backend/app/routers/partners.py:450:@router.post("/{partner_id}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
apps/backend-rag/backend/app/routers/partners.py:451:async def deactivate_partner(
apps/backend-rag/backend/app/routers/partners.py:452:    partner_id: UUID,
apps/backend-rag/backend/app/routers/partners.py:456:    """Deactivate a partner. Admin only."""
apps/backend-rag/backend/app/routers/partners.py:461:            await svc.deactivate_partner(partner_id, actor_user=UUID(str(user["user_id"])))
apps/backend-rag/backend/app/routers/partners.py:466:        logger.exception("deactivate_partner failed")
apps/backend-rag/backend/app/routers/partners.py:470:@router.post("/{partner_id}/reassign", status_code=status.HTTP_204_NO_CONTENT)
apps/backend-rag/backend/app/routers/partners.py:471:async def reassign_partner(
apps/backend-rag/backend/app/routers/partners.py:472:    partner_id: UUID,
apps/backend-rag/backend/app/routers/partners.py:477:    """Reassign a partner to a different team member. Admin only."""
apps/backend-rag/backend/app/routers/partners.py:482:            await svc.reassign_partner(
apps/backend-rag/backend/app/routers/partners.py:483:                partner_id,
apps/backend-rag/backend/app/routers/partners.py:494:        logger.exception("reassign_partner failed")
apps/backend-rag/backend/app/routers/partners.py:504:    """Bulk-reassign multiple partners to a single user. Admin only."""
apps/backend-rag/backend/app/routers/partners.py:509:            for pid in body.partner_ids:
apps/backend-rag/backend/app/routers/partners.py:510:                await svc.reassign_partner(
apps/backend-rag/backend/app/routers/partners.py:528:@router.get("/{partner_id}/referrals")
apps/backend-rag/backend/app/routers/partners.py:530:    partner_id: UUID,
apps/backend-rag/backend/app/routers/partners.py:534:    """List referrals for a partner. Scoped by role."""
apps/backend-rag/backend/app/routers/partners.py:537:        await verify_partner_access_with_role(
apps/backend-rag/backend/app/routers/partners.py:538:            svc, UUID(str(user["user_id"])), user.get("role"), partner_id
apps/backend-rag/backend/app/routers/partners.py:540:        refs = await svc.repo.list_referrals_for_partner(partner_id)
apps/backend-rag/backend/app/routers/partners.py:547:@router.post("/{partner_id}/referrals", status_code=status.HTTP_201_CREATED)
apps/backend-rag/backend/app/routers/partners.py:549:    partner_id: UUID,
apps/backend-rag/backend/app/routers/partners.py:554:    """Record a referral for a partner. Team (owner) or admin."""
apps/backend-rag/backend/app/routers/partners.py:558:            await verify_partner_access_with_role(
apps/backend-rag/backend/app/routers/partners.py:559:                svc, UUID(str(user["user_id"])), user.get("role"), partner_id
apps/backend-rag/backend/app/routers/partners.py:562:                partner_id=partner_id,
apps/backend-rag/backend/app/routers/partners.py:567:            return {"id": str(rid), "partner_id": str(partner_id), "process_id": str(body.process_id)}
apps/backend-rag/backend/app/routers/partners.py:586:    """Swap a referral to a different partner. Admin only."""
apps/backend-rag/backend/app/routers/partners.py:591:            await svc.repo.update_referral_partner(referral_id, body.new_partner_id)
apps/backend-rag/backend/app/routers/partners.py:624:@router.get("/{partner_id}/commissions")
apps/backend-rag/backend/app/routers/partners.py:626:    partner_id: UUID,
apps/backend-rag/backend/app/routers/partners.py:630:    """List commissions for a partner. Scoped by role."""
apps/backend-rag/backend/app/routers/partners.py:633:        await verify_partner_access_with_role(
apps/backend-rag/backend/app/routers/partners.py:634:            svc, UUID(str(user["user_id"])), user.get("role"), partner_id
apps/backend-rag/backend/app/routers/partners.py:636:        commissions = await svc.repo.list_commissions_for_partner(partner_id)
apps/backend-rag/backend/app/routers/partners.py:643:@router.get("/{partner_id}/audit-log")
apps/backend-rag/backend/app/routers/partners.py:644:async def list_partner_audit_log(
apps/backend-rag/backend/app/routers/partners.py:645:    partner_id: UUID,
apps/backend-rag/backend/app/routers/partners.py:649:    """List the audit log for a partner. Admin or team-owner only."""
apps/backend-rag/backend/app/routers/partners.py:653:            await verify_partner_access_with_role(svc, UUID(str(user["user_id"])), user.get("role"), partner_id)
apps/backend-rag/backend/app/routers/partners.py:654:            entries = await svc.list_audit(partner_id)
apps/backend-rag/backend/app/routers/partners.py:655:            return [_partner_to_dict(e) for e in entries]
apps/backend-rag/backend/app/routers/partners.py:659:        logger.exception("list_partner_audit_log failed")
apps/backend-rag/backend/app/routers/partners.py:710:                from backend.services.crm.partners.emails import send_commission_earned

exec
/bin/zsh -lc "nl -ba apps/backend-rag/backend/services/events/handlers.py | sed -n '312,342p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
   312	                    f"[{severity}] {alert_type}: {message[:200]}",
   313	                    "internal",
   314	                ),
   315	                name=f"compliance_log_{client_id}",
   316	            )
   317	
   318	    # ── Register all handlers ──────────────────────────────────────────
   319	    bus.subscribe("client.changed", on_client_changed)
   320	    bus.subscribe("practice.status_changed", on_practice_status_changed)
   321	    bus.subscribe("compliance.alert", on_compliance_alert)
   322	
   323	    # ── Compliance + intel handlers (2026-04-18 PR) ────────────────────
   324	    try:
   325	        from backend.services.events.handlers.compliance_handlers import HANDLERS as _compliance_handlers
   326	        for event_type, handler in _compliance_handlers.items():
   327	            bus.subscribe(event_type, handler)
   328	    except ImportError as exc:
   329	        logger.warning("compliance_handlers not loaded: %s", exc)
   330	
   331	    # ── Partner handlers (2026-04-20) ──────────────────────────────────
   332	    try:
   333	        from backend.app.db import set_pool as _set_pool
   334	        _set_pool(db_pool)
   335	        from backend.services.crm.partners.events import register_partner_handlers
   336	        register_partner_handlers(bus)
   337	    except ImportError as exc:
   338	        logger.warning("partner handlers not loaded: %s", exc)
   339	
   340	    logger.info(
   341	        f"✅ EventBus handlers registered: "
   342	        f"{len(bus._subscribers)} event types"

exec
/bin/zsh -lc "nl -ba apps/backend-rag/backend/services/events/event_bus.py | sed -n '40,70p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
    40	logger = logging.getLogger(__name__)
    41	
    42	# Type alias for async event handlers
    43	EventHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]
    44	
    45	# PG channels we LISTEN on — maps pg_channel → event_type
    46	PG_CHANNEL_MAP: dict[str, str] = {
    47	    "practice_changed": "practice.status_changed",
    48	    "client_changed": "client.changed",
    49	    "compliance_alert": "compliance.alert",
    50	    # Emitted by import scripts after bulk ingest of OSS tanda terima receipts.
    51	    # Payload: {"quarter": "Q1", "year": 2026, "pt_count": N, "receipt_count": N,
    52	    #           "report_ids": [...], "source": "tax_drive_manual"}
    53	    # Consumers: KG Tax subgraph sync, portal notifications, audit log.
    54	    "lkpm_ingest_completed": "lkpm.ingest_completed",
    55	    # Emitted by war_room_drafts status change + war_room_posts INSERT triggers
    56	    # (migration 112). Payload: {draft_id|post_id, status|platform, event_type,
    57	    # occurred_at}. Consumers: review_handler (Telegram review gate),
    58	    # publisher_worker, measurer_worker, dashboard_sse.
    59	    "war_room_event": "war_room.event",
    60	    # Emitted by trend_signals INSERT + research_dossiers INSERT/UPDATE triggers
    61	    # (migration 113). Payload: {signal_id|dossier_id, topic|slug, event_type,
    62	    # occurred_at}. Consumers: dossier_compiler (batch pre-compute on new trends),
    63	    # curiosity_gap_closer, war_room_intake, zantara_rag_indexer (upsert Qdrant),
    64	    # crm_alert_router, connector/anomaly cognitive layers.
    65	    "intel_event": "intel.event",
    66	    # Emitted by 4 cognitive-layer tables (migration 114): cross_dossier_theses,
    67	    # wr_anomaly_alerts, weekly_strategic_briefs, ultra_moves. Payload:
    68	    # {id, table, event_type, occurred_at, + table-specific fields}.
    69	    # Consumers: dashboard SSE, Oracle (reads upstream briefs + theses),
    70	    # Learner (skills/scars from high-perf theses), Telegram notifier for

exec
/bin/zsh -lc "nl -ba apps/backend-rag/backend/migrations/migration_075_practice_status_notify.py | sed -n '1,70p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
     1	"""Migration 075: PostgreSQL triggers for practice status + payment notifications."""
     2	import logging
     3	
     4	import asyncpg
     5	
     6	logger = logging.getLogger(__name__)
     7	
     8	MIGRATION_ID = "075"
     9	DESCRIPTION = (
    10	    "Add pg_notify triggers on practices table for status changes and payment_status "
    11	    "transitions. Powers real-time email dispatch (M5 + M4)."
    12	)
    13	
    14	
    15	async def up(conn: asyncpg.Connection) -> None:
    16	    # ── Trigger function: fires on ANY UPDATE to practices ──────────────────
    17	    await conn.execute("""
    18	        CREATE OR REPLACE FUNCTION notify_practice_change()
    19	        RETURNS TRIGGER AS $$
    20	        DECLARE
    21	            payload TEXT;
    22	        BEGIN
    23	            -- Only act on relevant field changes
    24	            IF (OLD.status IS DISTINCT FROM NEW.status)
    25	               OR (OLD.payment_status IS DISTINCT FROM NEW.payment_status)
    26	            THEN
    27	                payload := json_build_object(
    28	                    'practice_id',     NEW.id,
    29	                    'client_id',       NEW.client_id,
    30	                    'old_status',      OLD.status,
    31	                    'new_status',      NEW.status,
    32	                    'old_payment',     OLD.payment_status,
    33	                    'new_payment',     NEW.payment_status,
    34	                    'assigned_to',     NEW.assigned_to,
    35	                    'ts',              EXTRACT(EPOCH FROM NOW())
    36	                )::text;
    37	
    38	                PERFORM pg_notify('practice_changed', payload);
    39	            END IF;
    40	            RETURN NEW;
    41	        END;
    42	        $$ LANGUAGE plpgsql;
    43	    """)
    44	
    45	    # ── Attach trigger to practices table ───────────────────────────────────
    46	    await conn.execute("""
    47	        DROP TRIGGER IF EXISTS trg_practice_changed ON practices;
    48	        CREATE TRIGGER trg_practice_changed
    49	        AFTER UPDATE ON practices
    50	        FOR EACH ROW
    51	        EXECUTE FUNCTION notify_practice_change();
    52	    """)
    53	
    54	    logger.info("Migration 075 applied: practice_changed pg_notify trigger")
    55	
    56	
    57	async def down(conn: asyncpg.Connection) -> None:
    58	    await conn.execute("DROP TRIGGER IF EXISTS trg_practice_changed ON practices;")
    59	    await conn.execute("DROP FUNCTION IF EXISTS notify_practice_change();")
    60	    logger.info("Migration 075 rolled back")

exec
/bin/zsh -lc "nl -ba apps/mouth/src/app/'(workspace)'/partners/page.tsx | sed -n '80,105p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
    80	  const [searchInput, setSearchInput] = useState(filters.search || "");
    81	
    82	  const loadPartners = useCallback(async (currentFilters: PartnerFilters) => {
    83	    setIsLoading(true);
    84	    setError(null);
    85	    try {
    86	      const cleanFilters: PartnerFilters = {
    87	        ...currentFilters,
    88	        status: currentFilters.status || undefined,
    89	        assigned_to: currentFilters.assigned_to || undefined,
    90	        search: currentFilters.search || undefined,
    91	        orphaned: currentFilters.orphaned || undefined,
    92	      };
    93	      const data = await partnersApi.listPartners(cleanFilters);
    94	      setPartners(data.partners);
    95	      setTotal(data.total);
    96	    } catch (err) {
    97	      logger.error("Failed to load partners", { component: "PartnersPage" }, err as Error);
    98	      setError("Failed to load partners. Please try again.");
    99	      toastError("Failed to load partners");
   100	    } finally {
   101	      setIsLoading(false);
   102	    }
   103	  }, [toastError]);
   104	
   105	  useEffect(() => {

exec
/bin/zsh -lc "nl -ba apps/mouth/src/app/'(workspace)'/partners/orphaned/page.tsx | sed -n '36,48p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
    36	  const loadOrphaned = useCallback(async () => {
    37	    setIsLoading(true);
    38	    setError(null);
    39	    setSelectedIds(new Set());
    40	    try {
    41	      const data = await partnersApi.listOrphanedPartners();
    42	      setPartners(data.partners);
    43	    } catch (err) {
    44	      logger.error("Failed to load orphaned partners", { component: "OrphanedPartnersPage" }, err as Error);
    45	      setError("Failed to load orphaned partners.");
    46	    } finally {
    47	      setIsLoading(false);
    48	    }

exec
/bin/zsh -lc "nl -ba apps/mouth/src/app/portal/'(authenticated)'/partner/dashboard/page.tsx | sed -n '50,90p'" in /Users/nuzantara/Desktop/partners-spec-wt
 succeeded in 0ms:
    50	  if (error) return <div className="p-6 text-red-500">Error: {error}</div>;
    51	
    52	  const totalEarned = commissions
    53	    .filter((c) => c.status === "paid")
    54	    .reduce((sum, c) => sum + Number(c.net_amount ?? 0), 0);
    55	  const totalPending = commissions
    56	    .filter((c) => c.status === "accrued" || c.status === "approved" || c.status === "pending_approval")
    57	    .reduce((sum, c) => sum + Number(c.net_amount ?? 0), 0);
    58	  const recentReferrals = referrals.slice(0, 5);
    59	  const recentCommissions = commissions.slice(0, 5);
    60	
    61	  return (
    62	    <div className="p-6 space-y-8">
    63	      <div>
    64	        <h1 className="text-2xl font-semibold text-white">Partner Dashboard</h1>
    65	        {partner && (
    66	          <p className="text-sm text-gray-400 mt-1">
    67	            Welcome, {partner.full_name}
    68	          </p>
    69	        )}
    70	      </div>
    71	
    72	      {/* Metric cards */}
    73	      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
    74	        <div className="rounded-lg border border-white/10 bg-white/5 p-5">
    75	          <p className="text-xs text-gray-400 uppercase tracking-wide">Total Earned</p>
    76	          <p className="text-2xl font-bold text-white mt-1">{fmt(totalEarned)}</p>
    77	        </div>
    78	        <div className="rounded-lg border border-white/10 bg-white/5 p-5">
    79	          <p className="text-xs text-gray-400 uppercase tracking-wide">Pending</p>
    80	          <p className="text-2xl font-bold text-white mt-1">{fmt(totalPending)}</p>
    81	        </div>
    82	        <div className="rounded-lg border border-white/10 bg-white/5 p-5">
    83	          <p className="text-xs text-gray-400 uppercase tracking-wide">Referral Count</p>
    84	          <p className="text-2xl font-bold text-white mt-1">{referrals.length}</p>
    85	        </div>
    86	      </div>
    87	
    88	      {/* Recent referrals */}
    89	      <div>
    90	        <h2 className="text-lg font-medium text-white mb-3">Recent Referrals</h2>

codex
## Executive Verdict

**Block.** The module is not production-ready: accrual is wired to a non-production `processes` model while real events emit `practice_id`, partner-facing API boundaries leak full PII, referral creation enables commission fraud, finance state transitions are non-atomic, and the frontend/backend contract is broken enough that first real use will fail.

## Critical Issues

1. **Accrual is wired to the wrong production domain and will not fire.**  
   `migration_119_partners.py` adds FKs to `processes(id)` even though the existing production trigger is on `practices` and emits `practice_id`, not `process_id`; the engine itself documents that `processes` does not exist in live Fly.io DB. This can fail migration outright, and even if a stub table exists, `handle_practice_status_changed()` exits because `payload.get("process_id")` is empty.  
   Refs: `apps/backend-rag/backend/migrations/migration_119_partners.py:157`, `apps/backend-rag/backend/migrations/migration_119_partners.py:194`, `apps/backend-rag/backend/migrations/migration_075_practice_status_notify.py:27`, `apps/backend-rag/backend/migrations/migration_075_practice_status_notify.py:38`, `apps/backend-rag/backend/services/crm/partners/events.py:42`, `apps/backend-rag/backend/services/crm/partners/events.py:45`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:19`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:91`.

2. **Any authenticated non-team/admin role can list all partners and their fiscal/payment PII.**  
   `GET /api/partners` has no role gate; `PartnersService.list_partners()` only scopes `team`, and every other role falls through to `repo.list_partners()`, which does `SELECT *`. That returns NPWP, NIK, bank account number, e-wallet, IBAN, fiscal address, and internal assignment data. `POST /api/partners` has the same missing team/admin gate.  
   Refs: `apps/backend-rag/backend/app/routers/partners.py:183`, `apps/backend-rag/backend/app/routers/partners.py:214`, `apps/backend-rag/backend/app/routers/partners.py:226`, `apps/backend-rag/backend/app/routers/partners.py:234`, `apps/backend-rag/backend/services/crm/partners/service.py:66`, `apps/backend-rag/backend/services/crm/partners/service.py:76`, `apps/backend-rag/backend/services/crm/partners/repository.py:118`, `apps/backend-rag/backend/migrations/migration_119_partners.py:61`.

3. **Partner users can create referrals for arbitrary process IDs.**  
   The create-referral route says “Team (owner) or admin” but uses `verify_partner_access_with_role()`, which explicitly allows `actor_role == "partner"` for their own partner record. There is no process/practice access check, no proof the partner referred the client, no active-partner check, and no audit write. A partner who obtains or guesses a process UUID can attach themselves and wait for accrual.  
   Refs: `apps/backend-rag/backend/app/routers/partners.py:547`, `apps/backend-rag/backend/app/routers/partners.py:558`, `apps/backend-rag/backend/app/routers/partners.py:561`, `apps/backend-rag/backend/services/crm/partners/service.py:211`, `apps/backend-rag/backend/services/crm/partners/service.py:216`, `apps/backend-rag/backend/services/crm/partners/repository.py:172`.

4. **Commission offset and approval are race-prone financial ledger mutations.**  
   `approve()` reads pending clawbacks without locking, mutates the accrual net amount, then separately transitions the clawback and approval. The code comments already admit crash corruption; concurrent approvals can also apply the same oldest clawback twice because `update_commission_status()` does read-before-write and updates by `id` only, with no `WHERE status = old_status` guard.  
   Refs: `apps/backend-rag/backend/services/crm/partners/commission_engine.py:205`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:232`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:254`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:259`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:267`, `apps/backend-rag/backend/services/crm/partners/repository.py:316`, `apps/backend-rag/backend/services/crm/partners/repository.py:340`.

5. **Mark-paid can persist payment state while permanently losing the commission email.**  
   The route marks the commission `paid` first, then sends the email, then sets `commission_email_sent_at`. If Brevo or the internal relay fails after the DB update, the endpoint returns 500 but the commission is already `paid`; retrying hits the state machine (`paid -> paid` disallowed) before it can resend. Concurrent retries can also double-send because the idempotency sentinel is checked before send and written after send.  
   Refs: `apps/backend-rag/backend/app/routers/partners.py:697`, `apps/backend-rag/backend/app/routers/partners.py:699`, `apps/backend-rag/backend/app/routers/partners.py:709`, `apps/backend-rag/backend/app/routers/partners.py:711`, `apps/backend-rag/backend/services/crm/partners/emails.py:197`, `apps/backend-rag/backend/services/crm/partners/emails.py:205`, `apps/backend-rag/backend/services/crm/partners/emails.py:262`, `apps/backend-rag/backend/services/crm/partners/emails.py:268`, `apps/backend-rag/backend/services/crm/partners/repository.py:343`.

6. **Finance authorization and Indonesian tax compliance are placeholders, not controls.**  
   `_require_finance()` lets every `admin` approve, pay, claw back, waive, and export, contradicting the spec’s separate finance permission. PPh rates are hardcoded placeholder values, receipt/kwitansi fields are optional, and commission approve/pay/clawback operations do not write the required audit events. This is not acceptable for real payouts.  
   Refs: `apps/backend-rag/backend/app/routers/partners.py:149`, `apps/backend-rag/backend/app/routers/partners.py:157`, `apps/backend-rag/backend/app/routers/partners.py:663`, `apps/backend-rag/backend/app/routers/partners.py:686`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:42`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:47`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:280`, `apps/backend-rag/backend/migrations/migration_119_partners.py:234`.

7. **Email sending has a hardcoded production secret fallback and unsafe rendering defaults.**  
   The module defaults to the production notification endpoint and `"REDACTED-ROTATED-KEY"` if env is missing, then posts partner-controlled template content with `autoescape=False`. That violates the project’s no-hardcoded-secret rule and makes staging/local/test misconfiguration capable of sending real emails through production credentials.  
   Refs: `apps/backend-rag/backend/services/crm/partners/emails.py:31`, `apps/backend-rag/backend/services/crm/partners/emails.py:33`, `apps/backend-rag/backend/services/crm/partners/emails.py:41`, `apps/backend-rag/backend/services/crm/partners/emails.py:45`, `apps/backend-rag/backend/services/crm/partners/emails.py:67`.

8. **Frontend and backend contracts do not match; the UI is unusable on first run.**  
   Backend `GET /api/partners` returns a raw list, while the client expects `{ partners, total }`; frontend IDs are `number` and detail pages convert UUID route params with `Number(params.id)`; finance calls `/api/partner-commissions/*` and `/api/partners/commissions/export`, but backend exposes `/api/partners/commissions/{id}/*` and `/api/partners/finance/export`; create form sends fields/enums the backend does not accept (`tax_id`, `bank_account_name`, `commission_tier`, `withheld_tarif_umum`).  
   Refs: `apps/backend-rag/backend/app/routers/partners.py:234`, `apps/mouth/src/lib/api/partners/partners.ts:27`, `apps/mouth/src/lib/api/partners/partners.ts:210`, `apps/mouth/src/lib/api/partners/partners.ts:270`, `apps/mouth/src/lib/api/partners/partners.ts:290`, `apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:309`, `apps/mouth/src/app/(workspace)/partners/new/page.tsx:173`, `apps/mouth/src/app/(workspace)/partners/new/page.tsx:367`.

## Important Issues

1. **Audit log exposure is broader than the route claims.**  
   The audit route says “Admin or team-owner only” but uses the generic access helper, which also permits partner self-access. Audit rows include actor user IDs, reassignment reasons, and unredacted before/after JSON.  
   Refs: `apps/backend-rag/backend/app/routers/partners.py:643`, `apps/backend-rag/backend/app/routers/partners.py:653`, `apps/backend-rag/backend/services/crm/partners/service.py:211`, `apps/backend-rag/backend/services/crm/partners/repository.py:365`.

2. **Audit writes can fail after the business mutation has already happened.**  
   `update_partner()` writes the partner row, then JSON-serializes `before`/`after`; Decimal/UUID/datetime fields can throw during `json.dumps()`, returning 500 after the update was committed and leaving no audit record.  
   Refs: `apps/backend-rag/backend/services/crm/partners/service.py:98`, `apps/backend-rag/backend/services/crm/partners/service.py:100`, `apps/backend-rag/backend/services/crm/partners/service.py:103`, `apps/backend-rag/backend/services/crm/partners/repository.py:371`.

3. **Partner email collision protection is case-sensitive and explicitly race-prone.**  
   The service-layer check admits the SELECT-then-INSERT race, and both the users lookup and partner unique index are case-sensitive. `Team@balizero.com` and `team@balizero.com` can diverge.  
   Refs: `apps/backend-rag/backend/services/crm/partners/repository.py:77`, `apps/backend-rag/backend/services/crm/partners/repository.py:80`, `apps/backend-rag/backend/services/crm/partners/repository.py:87`, `apps/backend-rag/backend/migrations/migration_119_partners.py:107`.

4. **PDP consent is not actually captured as implemented.**  
   The backend create model only has `pdp_consent_version` / `terms_version`; the frontend requires `pdp_consent` but sends a field the backend ignores. There is no server-side setting of `pdp_consent_at`, no consent text version enforcement, and no deletion/retention workflow despite welcome copy promising deletion by reply.  
   Refs: `apps/backend-rag/backend/app/routers/partners.py:72`, `apps/backend-rag/backend/migrations/migration_119_partners.py:90`, `apps/mouth/src/app/(workspace)/partners/new/page.tsx:159`, `apps/mouth/src/app/(workspace)/partners/new/page.tsx:194`, `apps/backend-rag/backend/services/crm/partners/templates/welcome.md.j2:26`.

5. **Partner commission notifications are not really EventBus-backed.**  
   The new `partner.commission_changed` notification is published only on accrual, is not in `PG_CHANNEL_MAP`, and approve/pay/clawback do not publish it. The actual paid email is direct router side-effect code, not a subscriber.  
   Refs: `apps/backend-rag/backend/services/events/event_bus.py:45`, `apps/backend-rag/backend/services/crm/partners/events.py:26`, `apps/backend-rag/backend/services/crm/partners/events.py:71`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:280`.

6. **Inactive/pending partners can still receive referrals and accrue.**  
   Neither `create_referral()` nor `accrue_from_process()` checks `onboarding_status == 'active'`; the UI filters active partners, but the API is the enforcement boundary.  
   Refs: `apps/backend-rag/backend/app/routers/partners.py:547`, `apps/backend-rag/backend/services/crm/partners/repository.py:172`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:123`.

7. **Bulk reassignment is not atomic.**  
   The router loops through partner IDs one by one and returns 500/400 on the first failure, leaving earlier partners reassigned and later partners untouched.  
   Refs: `apps/backend-rag/backend/app/routers/partners.py:498`, `apps/backend-rag/backend/app/routers/partners.py:509`.

8. **Process creation treats referral failure as non-fatal.**  
   The frontend creates a practice, then silently logs referral creation failure; given the backend mismatch above, operators will think a referrer was saved when no commission path exists.  
   Refs: `apps/mouth/src/app/(workspace)/process/new/page.tsx:364`, `apps/mouth/src/app/(workspace)/process/new/page.tsx:369`.

## Observations / Future Work

- Replace `processes` with the existing `practices` domain, including real payment fields, real client/service joins, and a migration that matches production schema.
- Introduce separate response DTOs for admin/team/partner views; never return `SELECT *` partner records from API handlers.
- Use transactional finance commands with row locks, conditional status updates, and an outbox table for emails/events.
- Treat PPh 21/23, bukti potong, kwitansi/invoice, and Permenkumham sponsor/referral boundaries as signed-off policy gates before enabling payout.
- Add contract tests across the Next.js API client and FastAPI routes; current backend tests do not cover the frontend endpoint paths or response shapes.
- Move partner portal role-gating out of “layout as UX guard” and keep backend authorization as the hard boundary, with middleware only as defense-in-depth.

## One-Sentence Summary

Block this PR because it formalizes sensitive partner payouts on top of the wrong production data model, leaky authorization, non-atomic finance state, placeholder tax policy, and a broken frontend/backend contract.
tokens used
229.832
## Executive Verdict

**Block.** The module is not production-ready: accrual is wired to a non-production `processes` model while real events emit `practice_id`, partner-facing API boundaries leak full PII, referral creation enables commission fraud, finance state transitions are non-atomic, and the frontend/backend contract is broken enough that first real use will fail.

## Critical Issues

1. **Accrual is wired to the wrong production domain and will not fire.**  
   `migration_119_partners.py` adds FKs to `processes(id)` even though the existing production trigger is on `practices` and emits `practice_id`, not `process_id`; the engine itself documents that `processes` does not exist in live Fly.io DB. This can fail migration outright, and even if a stub table exists, `handle_practice_status_changed()` exits because `payload.get("process_id")` is empty.  
   Refs: `apps/backend-rag/backend/migrations/migration_119_partners.py:157`, `apps/backend-rag/backend/migrations/migration_119_partners.py:194`, `apps/backend-rag/backend/migrations/migration_075_practice_status_notify.py:27`, `apps/backend-rag/backend/migrations/migration_075_practice_status_notify.py:38`, `apps/backend-rag/backend/services/crm/partners/events.py:42`, `apps/backend-rag/backend/services/crm/partners/events.py:45`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:19`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:91`.

2. **Any authenticated non-team/admin role can list all partners and their fiscal/payment PII.**  
   `GET /api/partners` has no role gate; `PartnersService.list_partners()` only scopes `team`, and every other role falls through to `repo.list_partners()`, which does `SELECT *`. That returns NPWP, NIK, bank account number, e-wallet, IBAN, fiscal address, and internal assignment data. `POST /api/partners` has the same missing team/admin gate.  
   Refs: `apps/backend-rag/backend/app/routers/partners.py:183`, `apps/backend-rag/backend/app/routers/partners.py:214`, `apps/backend-rag/backend/app/routers/partners.py:226`, `apps/backend-rag/backend/app/routers/partners.py:234`, `apps/backend-rag/backend/services/crm/partners/service.py:66`, `apps/backend-rag/backend/services/crm/partners/service.py:76`, `apps/backend-rag/backend/services/crm/partners/repository.py:118`, `apps/backend-rag/backend/migrations/migration_119_partners.py:61`.

3. **Partner users can create referrals for arbitrary process IDs.**  
   The create-referral route says “Team (owner) or admin” but uses `verify_partner_access_with_role()`, which explicitly allows `actor_role == "partner"` for their own partner record. There is no process/practice access check, no proof the partner referred the client, no active-partner check, and no audit write. A partner who obtains or guesses a process UUID can attach themselves and wait for accrual.  
   Refs: `apps/backend-rag/backend/app/routers/partners.py:547`, `apps/backend-rag/backend/app/routers/partners.py:558`, `apps/backend-rag/backend/app/routers/partners.py:561`, `apps/backend-rag/backend/services/crm/partners/service.py:211`, `apps/backend-rag/backend/services/crm/partners/service.py:216`, `apps/backend-rag/backend/services/crm/partners/repository.py:172`.

4. **Commission offset and approval are race-prone financial ledger mutations.**  
   `approve()` reads pending clawbacks without locking, mutates the accrual net amount, then separately transitions the clawback and approval. The code comments already admit crash corruption; concurrent approvals can also apply the same oldest clawback twice because `update_commission_status()` does read-before-write and updates by `id` only, with no `WHERE status = old_status` guard.  
   Refs: `apps/backend-rag/backend/services/crm/partners/commission_engine.py:205`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:232`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:254`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:259`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:267`, `apps/backend-rag/backend/services/crm/partners/repository.py:316`, `apps/backend-rag/backend/services/crm/partners/repository.py:340`.

5. **Mark-paid can persist payment state while permanently losing the commission email.**  
   The route marks the commission `paid` first, then sends the email, then sets `commission_email_sent_at`. If Brevo or the internal relay fails after the DB update, the endpoint returns 500 but the commission is already `paid`; retrying hits the state machine (`paid -> paid` disallowed) before it can resend. Concurrent retries can also double-send because the idempotency sentinel is checked before send and written after send.  
   Refs: `apps/backend-rag/backend/app/routers/partners.py:697`, `apps/backend-rag/backend/app/routers/partners.py:699`, `apps/backend-rag/backend/app/routers/partners.py:709`, `apps/backend-rag/backend/app/routers/partners.py:711`, `apps/backend-rag/backend/services/crm/partners/emails.py:197`, `apps/backend-rag/backend/services/crm/partners/emails.py:205`, `apps/backend-rag/backend/services/crm/partners/emails.py:262`, `apps/backend-rag/backend/services/crm/partners/emails.py:268`, `apps/backend-rag/backend/services/crm/partners/repository.py:343`.

6. **Finance authorization and Indonesian tax compliance are placeholders, not controls.**  
   `_require_finance()` lets every `admin` approve, pay, claw back, waive, and export, contradicting the spec’s separate finance permission. PPh rates are hardcoded placeholder values, receipt/kwitansi fields are optional, and commission approve/pay/clawback operations do not write the required audit events. This is not acceptable for real payouts.  
   Refs: `apps/backend-rag/backend/app/routers/partners.py:149`, `apps/backend-rag/backend/app/routers/partners.py:157`, `apps/backend-rag/backend/app/routers/partners.py:663`, `apps/backend-rag/backend/app/routers/partners.py:686`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:42`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:47`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:280`, `apps/backend-rag/backend/migrations/migration_119_partners.py:234`.

7. **Email sending has a hardcoded production secret fallback and unsafe rendering defaults.**  
   The module defaults to the production notification endpoint and `"REDACTED-ROTATED-KEY"` if env is missing, then posts partner-controlled template content with `autoescape=False`. That violates the project’s no-hardcoded-secret rule and makes staging/local/test misconfiguration capable of sending real emails through production credentials.  
   Refs: `apps/backend-rag/backend/services/crm/partners/emails.py:31`, `apps/backend-rag/backend/services/crm/partners/emails.py:33`, `apps/backend-rag/backend/services/crm/partners/emails.py:41`, `apps/backend-rag/backend/services/crm/partners/emails.py:45`, `apps/backend-rag/backend/services/crm/partners/emails.py:67`.

8. **Frontend and backend contracts do not match; the UI is unusable on first run.**  
   Backend `GET /api/partners` returns a raw list, while the client expects `{ partners, total }`; frontend IDs are `number` and detail pages convert UUID route params with `Number(params.id)`; finance calls `/api/partner-commissions/*` and `/api/partners/commissions/export`, but backend exposes `/api/partners/commissions/{id}/*` and `/api/partners/finance/export`; create form sends fields/enums the backend does not accept (`tax_id`, `bank_account_name`, `commission_tier`, `withheld_tarif_umum`).  
   Refs: `apps/backend-rag/backend/app/routers/partners.py:234`, `apps/mouth/src/lib/api/partners/partners.ts:27`, `apps/mouth/src/lib/api/partners/partners.ts:210`, `apps/mouth/src/lib/api/partners/partners.ts:270`, `apps/mouth/src/lib/api/partners/partners.ts:290`, `apps/mouth/src/app/(workspace)/partners/[id]/page.tsx:309`, `apps/mouth/src/app/(workspace)/partners/new/page.tsx:173`, `apps/mouth/src/app/(workspace)/partners/new/page.tsx:367`.

## Important Issues

1. **Audit log exposure is broader than the route claims.**  
   The audit route says “Admin or team-owner only” but uses the generic access helper, which also permits partner self-access. Audit rows include actor user IDs, reassignment reasons, and unredacted before/after JSON.  
   Refs: `apps/backend-rag/backend/app/routers/partners.py:643`, `apps/backend-rag/backend/app/routers/partners.py:653`, `apps/backend-rag/backend/services/crm/partners/service.py:211`, `apps/backend-rag/backend/services/crm/partners/repository.py:365`.

2. **Audit writes can fail after the business mutation has already happened.**  
   `update_partner()` writes the partner row, then JSON-serializes `before`/`after`; Decimal/UUID/datetime fields can throw during `json.dumps()`, returning 500 after the update was committed and leaving no audit record.  
   Refs: `apps/backend-rag/backend/services/crm/partners/service.py:98`, `apps/backend-rag/backend/services/crm/partners/service.py:100`, `apps/backend-rag/backend/services/crm/partners/service.py:103`, `apps/backend-rag/backend/services/crm/partners/repository.py:371`.

3. **Partner email collision protection is case-sensitive and explicitly race-prone.**  
   The service-layer check admits the SELECT-then-INSERT race, and both the users lookup and partner unique index are case-sensitive. `Team@balizero.com` and `team@balizero.com` can diverge.  
   Refs: `apps/backend-rag/backend/services/crm/partners/repository.py:77`, `apps/backend-rag/backend/services/crm/partners/repository.py:80`, `apps/backend-rag/backend/services/crm/partners/repository.py:87`, `apps/backend-rag/backend/migrations/migration_119_partners.py:107`.

4. **PDP consent is not actually captured as implemented.**  
   The backend create model only has `pdp_consent_version` / `terms_version`; the frontend requires `pdp_consent` but sends a field the backend ignores. There is no server-side setting of `pdp_consent_at`, no consent text version enforcement, and no deletion/retention workflow despite welcome copy promising deletion by reply.  
   Refs: `apps/backend-rag/backend/app/routers/partners.py:72`, `apps/backend-rag/backend/migrations/migration_119_partners.py:90`, `apps/mouth/src/app/(workspace)/partners/new/page.tsx:159`, `apps/mouth/src/app/(workspace)/partners/new/page.tsx:194`, `apps/backend-rag/backend/services/crm/partners/templates/welcome.md.j2:26`.

5. **Partner commission notifications are not really EventBus-backed.**  
   The new `partner.commission_changed` notification is published only on accrual, is not in `PG_CHANNEL_MAP`, and approve/pay/clawback do not publish it. The actual paid email is direct router side-effect code, not a subscriber.  
   Refs: `apps/backend-rag/backend/services/events/event_bus.py:45`, `apps/backend-rag/backend/services/crm/partners/events.py:26`, `apps/backend-rag/backend/services/crm/partners/events.py:71`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:280`.

6. **Inactive/pending partners can still receive referrals and accrue.**  
   Neither `create_referral()` nor `accrue_from_process()` checks `onboarding_status == 'active'`; the UI filters active partners, but the API is the enforcement boundary.  
   Refs: `apps/backend-rag/backend/app/routers/partners.py:547`, `apps/backend-rag/backend/services/crm/partners/repository.py:172`, `apps/backend-rag/backend/services/crm/partners/commission_engine.py:123`.

7. **Bulk reassignment is not atomic.**  
   The router loops through partner IDs one by one and returns 500/400 on the first failure, leaving earlier partners reassigned and later partners untouched.  
   Refs: `apps/backend-rag/backend/app/routers/partners.py:498`, `apps/backend-rag/backend/app/routers/partners.py:509`.

8. **Process creation treats referral failure as non-fatal.**  
   The frontend creates a practice, then silently logs referral creation failure; given the backend mismatch above, operators will think a referrer was saved when no commission path exists.  
   Refs: `apps/mouth/src/app/(workspace)/process/new/page.tsx:364`, `apps/mouth/src/app/(workspace)/process/new/page.tsx:369`.

## Observations / Future Work

- Replace `processes` with the existing `practices` domain, including real payment fields, real client/service joins, and a migration that matches production schema.
- Introduce separate response DTOs for admin/team/partner views; never return `SELECT *` partner records from API handlers.
- Use transactional finance commands with row locks, conditional status updates, and an outbox table for emails/events.
- Treat PPh 21/23, bukti potong, kwitansi/invoice, and Permenkumham sponsor/referral boundaries as signed-off policy gates before enabling payout.
- Add contract tests across the Next.js API client and FastAPI routes; current backend tests do not cover the frontend endpoint paths or response shapes.
- Move partner portal role-gating out of “layout as UX guard” and keep backend authorization as the hard boundary, with middleware only as defense-in-depth.

## One-Sentence Summary

Block this PR because it formalizes sensitive partner payouts on top of the wrong production data model, leaky authorization, non-atomic finance state, placeholder tax policy, and a broken frontend/backend contract.
