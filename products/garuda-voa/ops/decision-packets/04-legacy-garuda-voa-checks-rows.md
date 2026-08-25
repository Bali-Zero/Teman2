# Owner decision 4 — the 25 legacy check rows

> Prepared for Zero. One yes/no. This rides on the back of decision 3 (retention) — it is the
> first thing that policy would do on the day it is signed, not a separate mechanism.

## What this is actually about

Before this session's audit, an earlier build of the funnel wrote eligibility-check rows to the
`garuda_voa_checks` table with no retention policy governing them at all — the fail-closed
retention gate described in packet 3 did not exist yet. Those rows are still there. They predate
every guardrail this product now enforces, and nothing has touched them since.

## What was measured (2026-08-24, against production, counts and dates only — no row content read)

| Fact           | Value                                                                                       |
| -------------- | ------------------------------------------------------------------------------------------- |
| Row count      | **25**                                                                                      |
| Window         | all created between **2026-07-27T00:21Z** and **2026-07-28T01:26Z** — a single 25-hour span |
| Verdict split  | **14 ACCEPT / 11 DECLINE**                                                                  |
| Activity since | **none** — the public funnel was withdrawn 2026-08-21 and has written nothing since         |

No name, passport number, email, or phone lives in this table (packet 3 §1) — each row holds
nationality, travel dates, the verdict, the deadline, and the price. Still personal data worth
protecting: nationality plus travel dates plus a verdict describes one real person's trip, even
unnamed.

## Why this is its own decision and not folded silently into decision 3

Packet 3 proposes a **90-day forward-looking** retention window measured from when a row is
written. These 25 rows are already **~29 days old today** and will be well past any retention
window you are likely to approve by the time this product goes live — they are not "still within
policy and due to expire later," they are already stale under every candidate number on the
table (90 or 150 days). Approving a retention _policy_ does not, by itself, retroactively purge
rows written before the policy existed; that requires an explicit instruction, which is what this
decision is.

## Recommendation

**Purge all 25 rows as the first act of the signed retention policy, keeping only the monthly
aggregate count (14 ACCEPT / 11 DECLINE, July 2026) as the demand-evidence record.** This is:

- consistent with packet 3's own "what survives forever" design — counts only, nothing traceable
  to one visit;
- lower-risk than keeping them: they serve no live customer (nobody can be served by rows from a
  withdrawn pilot they cannot even look up), and every day they sit ungoverned is a day this
  product's stated retention promise is not actually true for its own oldest data;
- irreversible, which is exactly why it is proposed here and not executed — nothing runs until
  you say so.

## What the owner must personally do

1. Say yes or no to purging the 25 rows.
2. If yes, confirm it should happen **at the moment the retention policy (decision 3) is signed**
   — this decision does not need a separate signature ceremony; it executes as decision 3's first
   purge.
3. If no, say what should happen instead (e.g., keep them indefinitely as a labeled exception,
   or purge only after a longer grace window) — nothing here assumes silence means yes.

## Your gesture

- [ ] Yes — purge all 25 rows when the retention policy (decision 3) is signed, keep the monthly
      count only
- [ ] No — keep them; instruction: **\_\_\_\_**
