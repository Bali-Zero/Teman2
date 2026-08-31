# Owner decision 3 — how long we keep a visitor's check

> Prepared for Zero. One number to approve or change.

**Recommendation: 90 days after delivery, then automatic purge, with permanent anonymous counts.**

## What this is actually about

When a tourist checks their VOA eligibility on the site, we write one row. That row holds no name,
no passport number, no email and no phone — only their nationality, their travel dates, the
accept/decline verdict, the deadline and the price. It is reachable by whoever holds the result
link, and today **nothing ever deletes it**.

That is still personal data worth protecting: nationality plus travel dates plus a verdict
describes one real person's trip, even unnamed. And the same question will apply, more sharply, to
the order side of the funnel, which does hold name and passport.

## The proposal

|                                 |                                                                                                                                                                                                                                                                    |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Anonymous eligibility check** | purge 90 days after the row is written                                                                                                                                                                                                                             |
| **Order and its documents**     | purge 90 days after the visa is delivered                                                                                                                                                                                                                          |
| **What survives forever**       | counts only — how many checks per month, by verdict, by nationality, by decline reason. No dates, no identifier, nothing traceable to one visit. This is the demand evidence the funnel exists to produce, and once the row is gone it is no longer personal data. |
| **The visitor's own control**   | a delete button on their own result page. No email round trip, no support ticket.                                                                                                                                                                                  |

90 days is chosen so that a customer who comes back to ask "what did you tell me in March?" still
has their record during the season they travelled, and so a payment dispute (foreign card networks
allow chargebacks up to 120 days) is not argued against an empty table — that last point is the one
argument for going _longer_ rather than shorter, and you may want 150 days instead. Say the word
and the number changes; nothing in the build depends on it being 90.

## What happens if you do not decide

Nothing gets stored, and the funnel cannot sell. That is deliberate, not a bug. The retention
machinery this reuses is fail-closed by construction: it refuses every write until a policy record
exists carrying a duration, an anchor date, an approver name and an approval reference. Bali Zero
already runs it this way for the Visa Oracle decisions. So this decision is not paperwork chasing
the build — it is a gate the build stops at.

## Related: the 25 rows already in the table (decision 4)

Measured directly against production this session, counts and dates only:

- **25 rows**, all created between **2026-07-27 00:21 UTC and 2026-07-28 01:26 UTC** — a single
  25-hour window, the day the old funnel was built.
- 14 ACCEPT, 11 DECLINE.
- Nothing since. The public funnel was withdrawn on 2026-08-21 and has written nothing since.

This is pilot traffic from a build day, not customers. By the time this product goes live those
rows will be over a year old, they are already older than any retention period you are likely to
approve, and no one can be served by keeping them.

**Recommendation: delete all 25 when the retention policy is signed**, keeping only the monthly
count as aggregate evidence. Deleting data is irreversible, so this is proposed and not executed —
one word from you and it happens as the first purge the new policy performs.

## Your gesture

Approve, or change the number:

- [ ] 90 days, as proposed
- [ ] a different number: \_\_\_\_ days
- [ ] delete the 25 legacy rows when the policy activates — yes / no
