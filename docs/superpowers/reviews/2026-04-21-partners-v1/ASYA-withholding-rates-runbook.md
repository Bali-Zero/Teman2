# Asya — Partners v1 withholding rates runbook

**When:** Post-deploy of PR #141 (Partners v1 council fixes).
**What:** Confirm or adjust the Indonesian withholding tax rates used by the commission engine. No code deploy needed — all values live in `system_settings`.

## Current placeholder values (v1 default)

| `system_settings.key` | Value | Meaning |
|---|---|---|
| `partner_withholding_rate_pph21` | `2.5` | PPh 21 rate for individual partners WITH NPWP (percent). |
| `partner_withholding_rate_pph23` | `2.0` | PPh 23 rate for corporate partners (PT/CV) WITH NPWP (percent). |
| `partner_withholding_no_npwp_surcharge` | `20` | Additional percentage-points-as-fraction-of-base for partners WITHOUT NPWP. |
| `partner_accrual_cooling_off_days` | `30` | Days between accrual and eligibility for admin approval. |
| `partner_clawback_auto_writeoff_idr` | `0` | If > 0, clawbacks below this IDR amount auto-waive on creation. 0 = disabled. |

## Effective rate formula

```
if partner.tax_withholding_category == 'exempt':
    rate = 0
elif partner.npwp present:
    rate = base   # from pph21 or pph23 row
else:
    rate = base + (base * no_npwp_surcharge / 100)
    # example: pph23=2.0%, surcharge=20 → effective 2.4%
    # example: pph21=2.5%, surcharge=20 → effective 3.0%
```

Note: Indonesian law states the PPh21 no-NPWP surcharge is **+20% of the base rate** (multiplicative), which is how this code interprets it. If your tax advisor uses a different interpretation (e.g., +20 percentage points), we'll need to adjust the formula — flag it before any real payout.

## How to change a rate without deploying code

SSH to `nuzantara-postgres` via Fly:

```bash
fly ssh console -a nuzantara-postgres
psql -U postgres -d nuzantara
```

Then update any of the keys:

```sql
-- Example: change PPh23 from 2.0% to 1.75%
UPDATE system_settings
SET value = '1.75',
    updated_at = now()
WHERE key = 'partner_withholding_rate_pph23';

-- Check current values:
SELECT key, value, description
FROM system_settings
WHERE key LIKE 'partner_%'
ORDER BY key;
```

The commission engine reads these values fresh on every accrual — no restart needed. New rates apply to the **next** accrual; previously-created commissions keep their snapshot rates (per spec §Q1 immutable snapshot rule).

## First-3-payout review gate

Per spec §Q4, the first 3 real payouts require your sign-off before admin hits `POST /api/partners/commissions/{id}/mark-paid`. The UI soft-warning banner reminds operators of this for the first 3 approvals.

For each of the first 3 payouts:

1. **Verify partner.tax_withholding_category is correct** for that specific partner type (Indonesian individual → pph21; Indonesian PT/CV → pph23; foreign entity or exempt-class → exempt).
2. **Verify NPWP is present** if the partner should be taxed (absence triggers surcharge — make sure that's intended).
3. **Verify calculated gross/withholding/net** on the commission row match your expectation given the current system_settings values.
4. **Verify kwitansi/invoice** uploaded matches partner's legal name + NPWP.
5. Only then mark paid.

## Observability

To see pending accruals waiting for your review:

```sql
SELECT
    pc.id, p.full_name AS partner, p.npwp, p.tax_withholding_category,
    pc.accrued_at, pc.eligible_for_approval_at,
    pc.gross_amount_idr, pc.withholding_rate, pc.withholding_amount_idr, pc.net_amount_idr
FROM partner_commissions pc
JOIN partners p ON p.id = pc.partner_id
WHERE pc.status = 'accrued'
  AND pc.eligible_for_approval_at <= now()
ORDER BY pc.eligible_for_approval_at ASC;
```

Or via the admin UI: `/portal/partners/finance` → "Pending Approval" section.

## Questions to clarify before first payout

- [ ] Is 2.5% the correct base PPh 21 rate for our expected partner types, or should it be the higher progressive bracket?
- [ ] Is the 20% no-NPWP surcharge applied multiplicatively (our v1) or additively (some interpretations)?
- [ ] Should the minimum commission threshold for applying PPh 23 (usually IDR 2M/year per vendor per DJP) be enforced, or do we tax from the first rupiah?
- [ ] Do we need per-month aggregation for PPh 21 (often due to progressive brackets), or does per-commission flat-rate work for Bali Zero's volume?

Document the answers here once confirmed:

```
Answers (YYYY-MM-DD, signed off by Asya):
- Q1: ___
- Q2: ___
- Q3: ___
- Q4: ___
```

## v1.1 follow-ups (not blocking first use)

- PDF bukti potong generator + e-Bupot Unifikasi integration.
- Per-service commission rate rules (currently partner-level default only).
- Progressive PPh 21 bracket calculation for partners with annualized income > threshold.
- Kwitansi structured validation (NPWP, stamp, address).
