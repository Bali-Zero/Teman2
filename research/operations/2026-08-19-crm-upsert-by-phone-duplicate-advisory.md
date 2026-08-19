---
date: 2026-08-19
domain: operations
client_case: none
adversarial_review: codex
sources:
  - apps/backend-rag/backend/app/routers/crm_clients.py
  - apps/backend-rag/backend/services/intake/crm_push.py
  - scripts/wa-mirror-auto-promote-leads.py
  - live Fly logs, app nuzantara-rag, machine 1781e5eda03438, ~2026-08-19T14:29Z
  - production Postgres via scripts/pg.sh (role nuzantara_readonly, db nuzantara_rag), read-only counts
---

# `upsert-by-phone`: the same endpoint, two callers, opposite safety postures — and the unsafe one is the one running

Found while chasing something else. A Fly deploy of `nuzantara-rag` returned `RC=0` alongside a
warning that a machine had no listener on `0.0.0.0:8080`. That warning is benign by construction:
`apps/backend-rag/fly.toml` states in its own comment that the `rag` process is reached over 6PN
and *"intentionally has no `[[services]]` Fly Proxy block"*, binding `--host ::`; `drive` is a
worker with no HTTP surface; only `api` sits behind fly-proxy. The advice the warning gives —
bind `0.0.0.0` — would break the design it warns about.

Reading the live log to confirm the rag machine was actually serving surfaced something else.

## What the endpoint does

`POST /api/crm/clients/upsert-by-phone` (`crm_clients.py:1340`) resolves a client by the *core*
of a phone number — the national part, so `0812…` and `62812…` are one identity.
`UPSERT_MATCH_SQL` (`crm_clients.py:91`) deliberately matches across **three** ownership columns
(`phone_normalized`, raw `phone`, `whatsapp`) and orders:

```sql
ORDER BY (deleted_at IS NULL) DESC, updated_at DESC NULLS LAST
FOR UPDATE
```

That breadth is not accidental — the comment above it cites Codex 2026-07-19 rounds 10/12/15
(F15/F21). When more than one row matches, the endpoint acts on `rows[0]` and then logs
(`crm_clients.py:1543-1551`):

> `upsert-by-phone: %s clients share a phone (acted on id=%s) — review for possible duplicate-client merge`

## Two callers, opposite postures

| caller | `reject_ambiguous` | `restore_if_archived` | behaviour on a collision |
|---|---|---|---|
| `services/intake/crm_push.py:157-168` | **`True`** (explicit) | **`False`** (explicit) | refuses; mutates nothing |
| `scripts/wa-mirror-auto-promote-leads.py:819-826` | *(omitted → `False`)* | *(omitted → `True`)* | acts on `rows[0]` |

`crm_push.py` sets both flags with comments naming exactly the hazard:

> *"Resolution must be mutation-safe on shared phones: the endpoint refuses BEFORE any
> restore/rename when >1 rows match (F10)."*
>
> *"NEVER resurrect an archived Fly row during identity resolution — the archived owner of this
> phone may be a DIFFERENT person than the locally-selected client (Codex round 8, F11 archive gap)."*

`wa-mirror-auto-promote-leads.py` sends a payload with **neither flag**, so it takes the model
defaults: `reject_ambiguous: bool = False` (`crm_clients.py:1329`) and
`restore_if_archived: bool = True` (`crm_clients.py:1321`).

**The live log shows which one is running.** The observed warnings read `acted on id=<integer>`.
A `crm_push` collision returns `client_id: None` and would print `acted on id=None`. The traffic
we measured is the defaults path.

## What was measured

Live log, app `nuzantara-rag`, machine `1781e5eda03438`, ~2026-08-19T14:29Z: the warning fired
**4 times in ~40 seconds** of captured log, on 4 distinct client ids — three reporting "2 clients",
one reporting "3 clients". A bulk upsert stream was running.

Production Postgres, read-only via `scripts/pg.sh`, **counts only, no PII extracted**:

| measure | value |
|---|---|
| clients total | 12,118 |
| phone-core collision groups | 849 |
| rows involved | 1,810 |
| … **1 live + N archived** | 412 |
| … **all archived** | 390 |
| … **more than one LIVE row** | 47 |
| max rows sharing one core (live) | 3 |

## What the ORDER BY actually guarantees — and where it stops

Only the **412** groups with exactly one live row are resolved by a *principled* rule: the live
row outranks archived ones. That is 49% of collisions, not the 94% an earlier draft of this note
claimed.

For the other two populations the tiebreak is `updated_at DESC` — recency standing in for truth:

- **47 groups (>1 live)**: the write lands on whichever live client card was touched most
  recently. Two real, distinct, current clients; the more recent one absorbs the update.
- **390 groups (all archived)**: `rows[0]` is archived, and under the defaults path line 1427
  runs `deleted_at = NULL` — it **un-deletes** an archived card chosen by recency, then may
  rename it and append notes. This is precisely the F11 hazard `crm_push.py` refuses to take,
  taken by its sibling caller against a population of 390.

`matched_count = len(rows)` (`crm_clients.py:1391`) and `UPSERT_MATCH_SQL` carries no
`deleted_at` filter, so the warning fires for all 849 groups without distinguishing which of the
three populations it is in. The 412 benign firings are indistinguishable, in the same words, from
the 437 that are not.

## The advisory has no review surface

A repo-wide grep for `duplicate-client|duplicate_client|possible duplicate|merge_clients|merge-clients`
across `apps/`, excluding tests and `.venv`, returns the log line itself and nothing else.
Two near-misses that are not it: `_find_duplicate_client`
(`backend/services/crm/client_core.py:1196`) is dedup at *creation* time, and
`apps/backend-rag/scripts/analyze_duplicates.py` counts duplicate **files**.

Two things do consume the *resolution outcome*, and neither is a review surface: `crm_push.py`
consumes it to decide its own delivery, and `wa-mirror-auto-promote-leads.py:845-850` records
`action` and `matched_count` into its audit record. Nothing surfaces the collision to a human on
`kita.balizero.com`. The sentence asks for a review that no surface offers.

## The log can assert an action that did not happen

Two return paths carry `matched_count > 1` while mutating nothing — `rejected_ambiguous`
(`crm_clients.py:1396`, returns `client_id: None`) and `skipped_archived` (`crm_clients.py:1415`,
returns the id and explicitly does not act). Both reach the log line at 1543, which prints
`acted on id=…`. The `action` field — the one value in `result` that names what actually
happened — is never logged.

Reachability, precisely:

- `rejected_ambiguous` **is reachable in-repo**, via `crm_push.py`, and prints `acted on id=None`.
- `skipped_archived` with `matched_count > 1` is **not** reachable from either in-repo caller:
  `crm_push` short-circuits at 1393 before reaching 1405, and the defaults path has
  `restore_if_archived=True` so it restores instead of skipping. It needs a caller passing
  `reject_ambiguous=False` **and** `restore_if_archived=False`, which neither does today.

## Meta-pattern

Same shape as `research/operations/2026-08-19-crm-portal-handoff-sim/`: a mechanism that
**exists** but does not **participate**. The guard is written, the risk is named, the sentence
tells you what to do — and no surface exists on which anyone does it.

Two sharper edges underneath:

**The cure went to one caller of two.** Fifteen rounds of adversarial review hardened
`crm_push.py`, and the reasoning is preserved verbatim in its comments. The sibling caller was
never brought along, and it is the one in production. This is the class-audit lesson: a
pattern-fix that stops at the call site that bit you does not reduce the risk, it only moves
which caller carries it.

**An alarm that mostly fires on correct outcomes.** 412 benign firings arrive in the same words
as the 437 that are not, so whoever reads the stream learns to stop reading — which is how the
next real one is missed.

## Open questions (human decision — `operator[business]`)

1. Should the 47 live collisions be merged at all? In this business a shared number is often
   **legitimate** — spouses on one handset, a reused office line, an agent fronting for a
   client. "Duplicate" may be the wrong word for many of them, and a merge would destroy a real
   distinction.
2. Should `wa-mirror-auto-promote-leads.py` adopt `crm_push.py`'s posture? That is the smallest
   change with the largest effect, but it converts ~849 silent writes into refusals — a
   behaviour change on a live lead pipeline, not a bug fix.
3. Is resurrecting an archived card ever the intent on the auto-promote path? `crm_push.py` says
   no, in writing, for identity resolution. Whether the lead-promotion path has a different and
   legitimate answer is a business call, not a code call.

## Adversarial review

Seat: **Codex `gpt-5.6-terra`** (`model_reasoning_effort=medium`, `--sandbox read-only`), run
against the first draft with instructions to verify every file:line against the code on disk and
report only defects. It returned `VERDICT: FIX` with three objections. All three were verified
independently on disk before being accepted; all three were real, and two were load-bearing.

1. **"802 of 849 resolve deterministically" — overstated.** The live-outranks-archived rationale
   covers only the 412 mixed groups; the 390 all-archived groups have no live row and fall to the
   same recency tiebreak. Corrected above — the split is 412/437, not 802/47.
2. **"No in-repo caller" — wrong.** `crm_push.py` exists and sets both flags explicitly. This
   objection is the origin of the entire two-callers section, which is now the note's main
   finding. **My own error, and its cause is worth recording**: the grep that produced the false
   claim ended in `| head`, and `crm_push.py` fell past the ten-line cut. Reading absence from a
   truncated list as proof of non-existence is W97, committed while the scar file that names it
   was loaded in context.
3. **"No consumer" — wrong.** Narrowed above: two consumers of the resolution outcome exist;
   neither is an operator review surface, which is the claim that survives.

One correction to the seat, verified on disk: it reported both no-action paths as reachable via
`crm_push.py`. Only `rejected_ambiguous` is — `reject_ambiguous=True` returns at 1393, before the
`skipped_archived` branch at 1405 can be reached. Stated precisely in the section above.
