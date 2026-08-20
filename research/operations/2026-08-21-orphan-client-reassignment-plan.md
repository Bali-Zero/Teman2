---
date: 2026-08-21
domain: compliance
client_case: null
sources:
  - "prod Postgres (nuzantara-postgres) via scripts/pg.sh, live query 2026-08-21"
  - "team_members roster, live query 2026-08-21"
  - "practices table, live query 2026-08-21 (affinity check)"
---

# Orphan-client reassignment — plan (business decision by owner 2026-08-20/21)

Owner's decision, verbatim: **"spalmali tra surya adit ari vino krisna damar"** — the "who"
(six people) is decided; the "how" (measure, criterion, split) is this document.

## FASE 1 — measured, not assumed

**Orphan definition**: `clients.deleted_at IS NULL` AND no row in `team_members` with
`lower(email) = lower(btrim(assigned_to)) AND active = true`. This single `NOT EXISTS`
predicate covers every broken shape found live: NULL, empty string, a departed
team member's email (`sahira@balizero.com`, `active=false`, left 2026-07-10), a raw
phone number string, and a typo'd/non-existent email (`ari@balizero.com` vs the real
`ari.firda@balizero.com`).

**Real count: 324** (not ~327 — verified twice, via two independent query shapes:
a `LEFT JOIN ... WHERE tm.id IS NULL OR tm.active=false` and a `NOT EXISTS`; both
returned 324). Breakdown:

| assigned_to value | n | why orphan |
|---|---|---|
| `sahira@balizero.com` | 163 | team member `active=false` (left 2026-07-10) |
| NULL | 152 | never assigned |
| `''` (empty string) | 5 | never assigned |
| `+6282134547723` | 2 | phone number, not an owner email |
| `+6282134547725` | 1 | phone number, not an owner email |
| `ari@balizero.com` | 1 | no such team member (real: `ari.firda@balizero.com`) |
| **Total** | **324** | |

Status mix of the 324 (not used as a filter — the owner asked for *all* clients without
a valid owner, not a status-scoped subset): 173 lead, 86 active, 59 prospect, 6 inactive.

**The six recipients — verified active, verified emails, verified role**:

| Name | Email | Role | Department | active |
|---|---|---|---|---|
| Surya | `surya@balizero.com` | Team Leader | setup | true |
| Adit | `adit@balizero.com` | Supervisor | setup | true |
| Ari | `ari.firda@balizero.com` | Team Leader | setup | true |
| Vino | `vino@balizero.com` | Junior Consultant | setup | true |
| Krisna (roster name "Krishna") | `krisna@balizero.com` | Executive Consultant | setup | true |
| Damar | `damar@balizero.com` | Junior Consultant | setup | true |

All six are `active=true` — no stop condition triggered. Damar (Junior Consultant, 78
existing clients) and Krisna (Executive Consultant, 352 existing clients) both already
carry an active caseload of their own, confirming their role does foresee assigned
clients — not loaded on faith.

**Current load (active, non-deleted clients only)**, measured live:

| Person | Current clients |
|---|---|
| Krisna | 352 |
| Ari | 316 |
| Adit | 258 |
| Vino | 250 |
| Surya | 200 |
| Damar | 78 |

**Affinity check** (nationality/language, historical practice ownership): queried
`practices.assigned_to` for the 324 orphan client_ids — the only team-member hit above
a single occurrence is `sahira@balizero.com` itself (45 clients, but she is the departed
person we are redistributing *away* from — not a signal for which of the six to prefer).
No other name clears more than 1 hit. Nationality mix of the 324 is broad (Indonesian 96,
NULL 74, Italian 32, Australian 14, British 6, Spanish 6, French 6, Ukrainian 5, …) with
no team-member field recording language specialization except a free-text HR note that
Vino "speaks very little English" — a soft signal, not a rule to encode without inventing
a policy that doesn't exist. **Conclusion: no decisive affinity signal → pure balancing**,
as instructed for the no-signal case. The Vino note is flagged here for a human to weigh
qualitatively if desired; not acted on algorithmically.

## FASE 2 — the plan

**Criterion**: level the *total* caseload, not divide 324 by 6 (explicit instruction).
Water-filling: solve for a target level `L` such that giving every person below `L`
enough new clients to reach `L` exactly consumes the 324 available, while people already
above `L` receive zero (we can only ADD via this operation — we are not moving existing
clients away from anyone).

`4·L − (78+200+250+258) = 324 → L = 277.5`. Krisna (352) and Ari (316) are both already
above 277.5, so they receive 0 — correctly reproducing the owner's own example ("chi ne
ha già 250 e chi ne ha 10 non è equo"). The remaining 324 close the gap for the other
four as evenly as the integer constraint allows (residual .5 ties broken toward the two
lowest starting points, Damar and Surya, so they round up by one client each):

| Person | Current | New clients | Final total |
|---|---:|---:|---:|
| Damar | 78 | **+200** | 278 |
| Surya | 200 | **+78** | 278 |
| Vino | 250 | **+27** | 277 |
| Adit | 258 | **+19** | 277 |
| Ari | 316 | **+0** | 316 |
| Krisna | 352 | **+0** | 352 |
| **Total** | **1,454** | **+324** | **1,778** |

Max spread across the six after the move: 352 − 277 = 75 (down from 352 − 78 = 274
before). This is the closest the totals can be brought using only additions; fully
equalizing all six would require moving clients away from Ari/Krisna, which is out of
scope for "spread the orphans" and not authorized here.

**Which client_id goes to whom**: deterministic, `ROW_NUMBER() OVER (ORDER BY client
id)` on the 324 orphans, sliced into contiguous blocks sized per the table above (rows
1–200 → Damar, 201–278 → Surya, 279–305 → Vino, 306–324 → Adit). Full mapping (client_id
+ new owner email only, zero PII) in the sibling file
`2026-08-21-orphan-client-reassignment-plan.csv` in this same directory.

## FASE 3 — execution record

See migration `276_reassign_orphaned_clients_setup_team.sql` in
`apps/backend-rag/backend/db/migrations_v2/` (idempotent — the `WHERE` clause re-selects
only still-orphaned rows on any re-run, so a second run is a no-op). PR number and
deploy/verification record: appended below once shipped.
