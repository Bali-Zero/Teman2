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
