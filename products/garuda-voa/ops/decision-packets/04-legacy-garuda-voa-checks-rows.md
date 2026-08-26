# Owner decision 4 — the ungoverned legacy check rows

> Prepared for Zero. One yes/no. This rides on the back of decision 3 (retention) — it applies the
> policy decision 3 signs to rows that predate it.

## What this is actually about

Before the retention system described in packet 3 existed, an earlier build of the funnel wrote
eligibility-check rows to the `garuda_voa_checks` table with no policy governing them at all. Those
rows are still there, unauthorized by any policy, because none existed when they were written.

## The count: what it is, and what it is not

**A prior session measured this table on 2026-08-24** (packet 3's own text, commit `2ed7d2de0`):
**25 rows**, all created between **2026-07-27T00:21Z and 2026-07-28T01:26Z** — a single 25-hour
span — **14 ACCEPT / 11 DECLINE**, nothing written since the public funnel was withdrawn
2026-08-21.

**This count was NOT re-verified for this packet, and could not be.** This session (M5) has no
sanctioned path to Fly Postgres: `CLAUDE.md` §10 and `settings.json` both describe a
`postgres-nuzantara` read-only MCP that does not exist on this machine's config — confirmed by
`.mcp.json` (no such server declared) and `claude mcp list` (7 servers, no postgres). That
doc-vs-reality drift is filed separately (PR #4941) and is not this packet's problem to fix. What
matters here: **the "25" above is inherited context from a day-old measurement, not a number this
packet stands behind independently, and it may already be a different number by the time anyone
reads this.**

No name, passport number, email, or phone lives in this table (packet 3 §1, migration 261's own
PII-boundary comment) — each row holds nationality, travel dates, the verdict, the deadline, and
the price. Still personal data worth protecting: nationality plus travel dates plus a verdict
describes one real person's trip, even unnamed. That is exactly why this decision should not lean
on a number that cannot be stood behind.

## The durable fact this packet stands on instead: a structural predicate, not a count

A number is a snapshot with a shelf life. What Zero is actually being asked to authorize a
disposition for is a **class** of row, identified by a condition in the schema that is true today
and stays true regardless of how many rows currently match it:

**Table: `garuda_voa_checks`. Predicate: `retention_policy_id IS NULL AND retention_until IS
NULL`.**

This is not an approximation — it is enforced by the schema itself, read directly from migration
`281_garuda_voa_retention.sql` in this session:

- The `garuda_voa_checks_retention_binding_pair` CHECK constraint (added by 281) makes
  `retention_policy_id`/`retention_until` a bound pair: both NULL, or both set. No row can have
  one without the other.
- The `BEFORE INSERT` trigger `bind_garuda_voa_check_retention_policy` (also 281) runs on **every**
  new row and unconditionally sets both fields from the single active `GARUDA_CHECK` policy for
  that row's environment — or raises an exception and refuses the insert if no such policy exists.
- Consequence: **a row can only ever be NULL/NULL if it was written before this trigger existed.**
  Migration 281's own comment confirms this was deliberate — "NOT VALID preserves every
  pre-migration row: no fabricated retroactive deadline."

So the predicate durably distinguishes "written before governance existed" (NULL/NULL, forever,
by construction) from "written under governance" (always bound at insert time, or the insert never
happened). The count of NULL/NULL rows today is illustrative context (**~25, as of 2026-08-24, per
above**) — the predicate is what the disposition below actually targets, and it stays correct
whether the true figure is 25, 40, or zero by the time it runs.

## The disposition: bind them into the same policy, do not special-case a delete

Migration 281 already ships a purpose-built primitive for exactly this class of row:
`bind_legacy_garuda_voa_checks_retention_policy(p_limit, p_requested_by)`. Read directly from the
migration in this session — it does the following, and nothing else:

1. Selects rows where `retention_policy_id IS NULL` (bounded by `p_limit`, oldest first, row-locked
   `FOR UPDATE SKIP LOCKED`).
2. For each, looks up the active `GARUDA_CHECK` policy whose `effective_period` covers that row's
   `created_at`. If none covers it, the row is **left ungoverned, not counted as bound** — the
   function's own comment: "leave it ungoverned, do not invent coverage."
3. Where a policy is found, sets `retention_until := created_at + policy.retention_interval` — the
   **same formula** applied to every row, legacy or not. No fabricated or immediate deadline.

**This means "purge them now" is not actually an available honest move.** Once bound, a legacy row
becomes purge-eligible on exactly the same schedule as any row written today — `created_at +` the
approved retention interval — and gets swept by the existing, already-scheduled
`purge_garuda_voa_checks` primitive when that date arrives, same as every other row, no
special-casing. Under a 90-day policy, rows created 2026-07-27/28 would become eligible around
**2026-10-25/26** — not immediately. There is no separate "delete legacy rows now" primitive in
this migration, and building an ad-hoc one to bypass the interval this migration deliberately
enforces for every other row would be exactly the "special-cased, fabricated deadline" shape 281's
own design explicitly rejects.

**One implementation detail for whoever signs decision 3 and configures the `GARUDA_CHECK` policy
row**: its `effective_period` lower bound must cover `2026-07-27` (or be open-ended below) for
`bind_legacy_garuda_voa_checks_retention_policy` to pick these rows up at all — a policy whose
`effective_period` starts only at signature time will silently leave them ungoverned forever
(step 2 above, "leave it ungoverned"). This is not a business decision, just a configuration trap
worth naming so it is not discovered by omission.

## Recommendation

**Once decision 3 is signed, run `bind_legacy_garuda_voa_checks_retention_policy` (with a limit
comfortably above the current count and a named requester) to bring every NULL/NULL row under the
same governance every new row already gets — no special immediate deletion.** This is:

- consistent with the migration's own stated design philosophy — bounded, explicit, never
  invents coverage or a fabricated deadline;
- lower-risk than an immediate delete: nothing irreversible happens at signature time; the rows
  simply stop being ungoverned and enter the same lifecycle as any other row from that point;
- self-correcting on the count problem above: it does not matter whether the true number is 25 or
  something else — the primitive operates on the predicate, not a number anyone has to keep fresh.

## What the owner must personally do

1. Confirm this disposition (bind into policy, then ordinary scheduled purge — not an immediate
   delete) rather than the "purge now" framing this packet originally used.
2. When approving decision 3's `GARUDA_CHECK` policy configuration, confirm its `effective_period`
   is set to cover `2026-07-27` onward (see the implementation note above) — otherwise these rows
   stay permanently ungoverned even after signature.
3. If a different disposition is wanted (e.g., an explicit one-time delete rather than binding into
   the ordinary lifecycle), say so — that would require a new, deliberately-scoped primitive this
   migration does not currently provide, and should be treated as its own small build, not
   something this packet can wave through.

## Your gesture

- [ ] Yes — bind the ungoverned rows (predicate: `retention_policy_id IS NULL`) into the signed
      GARUDA_CHECK policy once it exists; let them purge on the ordinary schedule like any other
      row. Confirm the policy's `effective_period` will cover 2026-07-27 onward.
- [ ] No — a different disposition is wanted: **\_\_\_\_**
