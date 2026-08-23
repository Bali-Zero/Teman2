# Migration-ledger revision request 001

- **From**: builder H1, work packet P04 (Research OS v1.0.0, Wave 0)
- **To**: S9-C0 (Conductor)
- **Date**: 2026-08-23
- **State**: `awaiting_conductor_decision`
- **Measured at**: `main` HEAD `148f0bfcad95e6ebb32c20b300b80ce8c2436b1d` (2026-08-22T23:10:08Z), worktree `docs-ros-v1-p04-ledger-revision`

## 1. The finding

The Wave 0 freeze (`research/operations/specs/evidence-to-action-freeze-2026-08-15/DEPENDENCY-DAG.md`,
commit `10d500e1c`) reserved a contiguous seven-migration block, `270`–`276`, against a stated
authoritative Pro migration head of `269` as of the 2026-08-15 freeze. As measured today,
2026-08-23, the actual on-disk head in `apps/backend-rag/backend/db/migrations_v2/` is `278`, and
**all seven reserved numbers — `270` through `276` — are occupied by migrations that were merged in
the eight days since the freeze and have no relationship to any Wave 0 work packet.** Two further
numbers, `277` and `278`, are also occupied by unrelated merged work, which is additional evidence
of how fast this ledger decays. The reservation as written is void; none of the seven consuming
packets (P04, P02, P05, P06, P09, P12, P13) can safely apply a migration at its frozen number.

## 2. Evidence

| # | Frozen owner (packet) | Frozen purpose | Actual occupying file | Adding commit | Reservation status |
|---:|---|---|---|---|---|
| `270` | P04 | Canonical contract core and canonical OutcomeEvent repository | `270_wa_broker_jobs.sql` | `b139ad3ba` — feat(wa-broker): migration 270 — broker_jobs transport + generation_route (BOT-V4 S2, PR 1/6) (#4346) | **VOID** |
| `271` | P02 | Publication truth, revision, and three-axis state specialization | `271_wa_broker_gauge_half_open_at.sql` | `d7e105ea4` — feat(wa-bot): broker_jobs transport service + /api/wa-broker endpoints (BOT-V4 S2 PR-2) (#4348) | **VOID** |
| `272` | P05 | Intel Lake v2 event, cluster, and outbox additions | `272_wa_broker_package_text.sql` | `d7e105ea4` (same PR as 271) | **VOID** |
| `273` | P06 | NAGA evidence, claim-family, bitemporal, and invalidation additions | `273_wa_broker_completion_digest.sql` | `d7e105ea4` (same PR as 271) | **VOID** |
| `274` | P09 | Publication/SEO projection, cursor, and materialized snapshot additions | `274_wa_broker_completed_at_check.sql` | `1ed3bfc2a` — feat(wa-bot): worker codex broker leg + package wire contract + m274 (BOT-V4 S2 PR-5) (#4373) | **VOID** |
| `275` | P12 | Action Inbox queue, intent, approval, and execution projections | `275_war_room_vision_circuit_breaker.sql` | `053a13af2` — fix(wr2): stop the vision loop from re-probing a quota window it already proved dead (#4431) | **VOID** |
| `276` | P13 | Domain outcome collector cursors and materialized aggregates | `276_garuda_voa_archive_comments.sql` | `665bfd40d` — feat(garuda): add owner-local synthetic preview and retire public routes (#4344) | **VOID** |
| `277` | *(unreserved)* | — | `277_correct_ari_email_typo.sql` | `615bcfcb4` — feat(migrations): correct ari@ typo, water-fill 324 orphaned CRM clients (#4542) | occupied, not reserved |
| `278` | *(unreserved)* | — | `278_reassign_orphaned_clients_setup_team.sql` | `615bcfcb4` (same commit as 277) | occupied, not reserved |

`ls apps/backend-rag/backend/db/migrations_v2/ | tail -30` confirms `278` is the current head and
`279` upward is free (no file matches `^279` or `^28`).

### Prior collision — this is scar W40's failure mode recurring

The same number, `270`, has already been claimed twice by unrelated work on two different refs:

```
git log --all --oneline --diff-filter=A --name-only -- 'apps/backend-rag/backend/db/migrations_v2/270*'
b139ad3ba  270_wa_broker_jobs.sql          (merged, on main — see table above)
b08efe3e7  270_wa_outbox_abstained_at.sql  (fix(whatsapp): deliver safe localized abstentions)
```

`b08efe3e7` is **not** an ancestor of current `main` HEAD (`git merge-base --is-ancestor b08efe3e7
HEAD` returns false) — it lived on a branch that either never merged or merged after being
renumbered, and the number collision was resolved off-ledger, by chance, not by process. This is
the identical defect class documented in repo scar **W40** (migration numbering collision): a
sequential integer reservation with no enforcement mechanism decays the moment more than one lane
touches the same file concurrently.

### No open PR is about to make this worse

```
gh pr list --state open --limit 60 --json number,title,files \
  --jq '.[] | select(.files[]?.path | test("migrations_v2/")) | "\(.number) \(.title)"'
```

Result: **none.** Of the two currently open PRs (`#4581`, `#4569`), neither touches
`migrations_v2/`. The `279`+ block is free as of this measurement with no in-flight contender —
see the freshness caveat in §5.

## 3. Why this is a stop, not a renumber

The freeze document is explicit, verbatim (`DEPENDENCY-DAG.md`, "Migration-number reservation"):

> Every execution session refreshes the authoritative Pro migration head before editing. If any
> reserved number is occupied or its purpose has changed, all downstream migrations stop and the
> Conductor issues one versioned ledger revision; workers never renumber independently.

And the execution board (`SESSION-BOARD.md`, §5 "Serial migration train"):

> If migration 274 cannot validate without P12/P18, the queue stops. The Conductor raises a formal
> ledger revision; no worker skips 274, renumbers independently, or applies 275 first.
>
> Packets 17 and 18 have no reservation. They must reuse P04/P12 persistence. Any newly discovered
> persistence requirement is a hard stop and requires a versioned migration-ledger decision before
> implementation.

H1 has confirmed the reservation is void (§2) and, per this rule, has **not** renumbered, picked a
new number, or applied any migration. H1 is stopped on the migration axis and is raising this
request, exactly as specified.

## 4. Blast radius

The freeze reserved one contiguous block for seven packets, in one order. Voiding it does not void
P04 alone — it voids the reservation for **all seven**: P04, P02, P05, P06, P09, P12, P13. Any of
those packets that reaches its "integrate migration" step and applies its frozen number without
first checking the live head will collide with whichever unrelated migration now occupies that
number (per §2, every one of the seven does). This request is filed by H1/P04 because P04 is first
in the serial migration train (`SESSION-BOARD.md` §5: `270 P04 canonical core → 271 P02 → 272 P05 →
273 P06 → 274 P09 → 275 P12 → 276 P13`), but the ratified renumbering below must be communicated to
all seven packet owners before any of them integrates.

## 5. Requested decision

Preserve the frozen **order** and **purpose** of each packet's migration, shifted to the first free
contiguous block as measured in §2:

| New number | Packet | Purpose (unchanged from freeze) |
|---:|---|---|
| `279` | P04 | Canonical contract core and canonical OutcomeEvent repository |
| `280` | P02 | Publication truth, revision, and three-axis state specialization |
| `281` | P05 | Intel Lake v2 event, cluster, and outbox additions |
| `282` | P06 | NAGA evidence, claim-family, bitemporal, and invalidation additions |
| `283` | P09 | Publication/SEO projection, cursor, and materialized snapshot additions |
| `284` | P12 | Action Inbox queue, intent, approval, and execution projections |
| `285` | P13 | Domain outcome collector cursors and materialized aggregates |

**Freshness caveat**: this block is free as measured at `main` HEAD `148f0bfcad9` /
2026-08-23T01:07Z (§2). A migration merged by any other lane between this measurement and Conductor
ratification voids it again, the same way the original `270`–`276` block was voided in eight days.
Whichever session integrates first under this ledger must re-run the `ls .../migrations_v2/ | tail`
+ open-PR check in §2 immediately before applying, not trust this document's numbers as still
current.

## 6. Second-order recommendation

The real defect is not that this particular block decayed — it is that **any contiguous integer
block frozen at time T decays monotonically**, because the reservation lives in a spec document
(`DEPENDENCY-DAG.md`) that no other part of the repository reads, references, or enforces. Nothing
stops an unrelated lane (BOT-V4, WR2, GARUDA VOA, CRM cleanup — all four appear in §2's occupier
list, none aware a reservation existed) from claiming the next sequential number, because from that
lane's point of view there is no reservation: there is only "what is the current head, add one."
Migration numbering here is a single global mutable counter with seven long-lived claims against
future values of it, checked by convention rather than by mechanism. The eight-day decay measured
in this request is not a one-off: it is the same defect class as repo scar **W40** (migration
numbering collision), reproduced structurally rather than incidentally.

**Recommendation**: stop reserving integers early. Reserve a **symbolic name** per packet instead
(e.g. `research_os_contract_core` for P04, `research_os_publication_truth` for P02, and so on), and
bind the integer **late** — at integration time, assigned by the serial integrator (I1, per the
Wave 0 role split), who is the only role positioned to see the true current head at the moment a
migration is actually about to be applied. This converts a prediction that can be falsified by any
unrelated merge into a fact recorded at the one moment it can't be wrong. It also removes the need
for this class of ledger-revision request going forward: there is nothing to void if nothing was
predicted.

## 7. What H1 does meanwhile

Migration integration is the only thing stopped. H1 continues, unblocked, on everything that
carries no migration number: contracts, validators, fixtures, and adapters for the P04 canonical
core, plus their tests. The migration SQL itself is **not yet authored.** When it is, it will be
proven applied and rolled back against an isolated local database (local Postgres 17.8 on
`127.0.0.1:5432`, never the `flyctl proxy` route to production on `127.0.0.1:15432`) before its PR
is opened; that PR will then be left **unarmed** (no auto-merge, no `mq arm`) pending the
Conductor's decision on §5.

The ratified migration must also be **PostgreSQL 15 compatible**, not merely compatible with the
production engine (17.x). CI runs `public.ecr.aws/docker/library/postgres:15` in four workflows —
`tests.yml` (two service definitions, lines 501 and 1385), `fly-deploy.yml`, `intel-router-tests.yml`,
and `scripts-tests-sweep.yml` — and local `docker-compose.yml` (line 34) uses `postgres:15-alpine`.
A migration that relies on a PG16+-only feature will pass a local apply/rollback proof against
Postgres 17.8 and then fail in CI.
