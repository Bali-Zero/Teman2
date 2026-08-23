---
adversarial_review: codex
---

# Migration-ledger revision request 001

- **From**: builder H1, work packet P04 (Research OS v1.0.0, Wave 0)
- **To**: S9-C0 (Conductor)
- **Date**: 2026-08-23
- **State**: `awaiting_conductor_decision`
- **Measured at**: 2026-08-23T01:37Z, `main` HEAD `03998cf902ebbdbdb9bae11dab4cccc56546f03e`
  (commit timestamp 2026-08-23T00:47:05Z), worktree `docs-ros-v1-p04-ledger-revision`

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

### Prior claim on the same number — same TOCTOU root as W40, different outcome

The same number, `270`, has already been claimed twice by unrelated work on two different refs:

```
git log --all --oneline --diff-filter=A --name-only -- 'apps/backend-rag/backend/db/migrations_v2/270*'
b139ad3ba  270_wa_broker_jobs.sql          (merged, on main — see table above)
b08efe3e7  270_wa_outbox_abstained_at.sql  (fix(whatsapp): deliver safe localized abstentions)
```

`b08efe3e7` is **not** an ancestor of current `main` HEAD (`git merge-base --is-ancestor b08efe3e7
main` returns false). `git branch -a --contains b08efe3e7` returns only
`remotes/origin/agent/nuzantara/backend-rag/wa-abstain-terminal-p0`, while
`git log main -S'abstained_at' --oneline -- apps/backend-rag/backend/db/migrations_v2` returns
nothing. No second `270` claim ever landed on `main`, and nothing was resolved: an unmerged remote
branch also claims `270`.

Scar **W40** had a different realized failure: two `194_*` files both reached `main` minutes apart,
creating a real duplicate that then had to be renamed. The shared root is the TOCTOU read-then-claim
pattern — multiple lanes can observe the same ledger head and claim its successor without atomic
coordination — but the outcome here is an unmerged competing claim. This is the **same root,
different realized failure**, not an identical defect class. In fact, had the `b08efe3e7` branch
tried to land alongside `270_wa_broker_jobs.sql`, the W41 pre-commit hook
(`.husky/pre-commit:192-202`) and the PR-time lint
(`.github/workflows/lint-migration-numbers.yml:20-28`) would both have caught the duplicate prefix.
That is the strongest available evidence that the duplicate axis is genuinely defended today and
further undercuts any reading of this episode as a near-miss that escaped only by luck.

### No migration PR was open at the measurement instant

```
gh pr list --state open --limit 60 --json number,title,files \
  --jq '.[] | select(.files[]?.path | test("migrations_v2/")) | "\(.number) \(.title)"'
```

Result at the measurement instant recorded in the header — 2026-08-23T01:37Z, at `main` HEAD
`03998cf902ebbdbdb9bae11dab4cccc56546f03e`: **none.** Of the five PRs open at that instant
(`#4586`, `#4585`, `#4584`, `#4581`, `#4569`), none touched `migrations_v2/`. This is a time-bounded network measurement,
not a standing fact. A local clone can prove only what it has fetched: an unfetched remote ref is
invisible to it, as is any PR opened after this measurement. The `279`+ block was free with no
visible in-flight contender at the stated instant; see the broader freshness caveat in §5.

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

**Freshness caveat**: this block is free as measured at `main` HEAD `03998cf902eb` /
2026-08-23T01:37Z (§2). A migration merged by any other lane between this measurement and Conductor
ratification voids it again, the same way the original `270`–`276` block was voided in eight days.
Whichever session integrates first under this ledger must re-run the `ls .../migrations_v2/ | tail`
+ open-PR check in §2 immediately before applying, not trust this document's numbers as still
current.

## 6. Second-order recommendation

The old phrasing in this request said no other part of the repository reads, references, or
enforces `DEPENDENCY-DAG.md`. That was false on both the reference and enforcement axes: four
documents reference the dependency authority, and three working mechanisms enforce migration-number
uniqueness. But none of those mechanisms can enforce the prose-only reservation. That distinction
— not an absence of repository rigour — is the point of this section. At commit `0c7f91c11`, the
four references are:

- `docs/superpowers/plans/2026-08-15-research-os-parallel-execution.md:15`;
- `research/operations/execution/research-os-v1.0.0/README.md:27`;
- `research/operations/execution/research-os-v1.0.0/SESSION-BOARD.md:6`, which names it the
  "Dependency authority";
- `research/operations/specs/evidence-to-action-freeze-2026-08-15/README.md:203`.

The reservation also carries a named lease. `SESSION-BOARD.md:162` records:

> | `migration-ledger-270-276` | I1 only | Design parallel; integrate/apply serial |

The same lease name appears in `WAVE-0-DISPATCH.md:98`.

But all four references and both lease declarations are **prose**, read by humans and sessions, not
mechanisms. A lane that never opens those documents cannot collide with the reservation as an
enforced object; it can only discover the collision later in the migration ledger.

The repository does have real enforcement against duplicates, just not against reservations. Three
mechanisms enforce migration-number **uniqueness**, verified on disk:

- `.husky/pre-commit:192-202` — the W41 (2026-05-23) pre-commit hook, which runs
  `scripts/lint_migration_numbers.py` on staged migration files;
- `.github/workflows/lint-migration-numbers.yml:20-28` — triggered on `pull_request` and on push to
  `main`; W41 added the push trigger specifically because L2 autonomous-ops policy permits direct
  pushes to `main`, closing the bypass found in W40
  (`.github/workflows/lint-migration-numbers.yml:11-18`);
- `apps/backend-rag/backend/db/migration_manager.py:34-62,280-285` — the runtime
  `_assert_unique_migration_numbers` assert. The lint script is its deliberately inlined twin
  (`scripts/lint_migration_numbers.py:21-26,39-44`).

These three mechanisms are real, but they enforce uniqueness, not reservation. They fire when two
files share a prefix. A lane that takes `270` while `270` is reserved-but-empty passes all three
cleanly and stays green, because a reservation is an **absence** and the lint can only see
**presence**. Therefore the repository is well defended against the duplicate and completely
undefended against the reservation. The gap is not missing rigour; it is that the thing being
protected was never expressible to the tools that do the protecting.

This request measured one instance of a narrower shape: a contiguous block reserved against one
shared monotonically increasing counter, concurrent lanes allocating from that counter, no atomic
allocator, and enough elapsed time for the counter to reach the reserved block. Under those
preconditions, the reservation loses usable numbers as the shared counter advances. One block over
eight days (`n=1`) does not establish a universal law that every contiguous block "decays
monotonically." It establishes that this repository's prose-only reservation did so once under the
stated conditions. Measurably, none of the occupying commits or their PR titles references the
reservation, the freeze, or any Wave 0 packet; this request makes no claim about what their authors
knew.

Migration numbering here is a single global mutable counter with seven long-lived claims against
future values of it. Duplicate values are checked by mechanism, but empty reserved values are
checked only by convention. The shared root is the same TOCTOU read-then-claim pattern recorded in
scar **W40**, but, as §2 distinguishes, the realized failure is different.

**Recommendation — Conductor choice between two options**:

1. **Symbolic name with late binding.** Stop reserving integers early. Reserve a symbolic name per
   packet instead (e.g. `research_os_contract_core` for P04, `research_os_publication_truth` for
   P02, and so on), and bind the integer at integration time through the serial integrator (I1,
   per the Wave 0 role split). Late binding narrows the prediction window from days to the
   integration interval; it does not close it. Reading the head, committing, reviewing, and
   merging or applying remain separate moments, and `I1 only` remains a prose lease rather than an
   atomic allocator. Two integrators — or one integrator and an unrelated lane — can still read
   the same head and claim the same successor.
2. **Placeholder file at reservation time.** Commit an empty or comment-only file such as
   `279_research_os_contract_core.sql` (or an equivalent placeholder) when the number is reserved.
   This turns the reservation from absence into presence. The uniqueness lint already exercised
   by the pre-commit hook, every migration-touching PR, every migration-touching push to `main`,
   and runtime discovery then defends the reservation without a new mechanism, a new document for
   other lanes to remember to read, or a change to their workflow. The trade-off is real: the
   placeholder occupies the integer early and reintroduces some of the rigidity that late binding
   is intended to remove.

These are alternatives for the Conductor, not one combined answer. The first minimizes early
rigidity but leaves a narrowed TOCTOU window; the second makes the existing uniqueness enforcement
protect the reservation for free but commits the ledger number early. Fully closing the allocation
race would require allocation atomic with merge or apply.

## 7. What H1 does meanwhile

Migration integration is the only thing stopped. H1 continues, unblocked, on everything that
carries no migration number: contracts, validators, fixtures, and adapters for the P04 canonical
core, plus their tests. The migration SQL itself is **not yet authored.** When it is, it will be
proven applied and rolled back against an isolated local database (local Postgres 17.8 on
`127.0.0.1:5432`, never the `flyctl proxy` route to production on `127.0.0.1:15432`) before its PR
is opened; that PR will then be left **unarmed** (no auto-merge, no `mq arm`) pending the
Conductor's decision on §5. This is H1's **commitment**, not evidence of a completed proof or an
already-opened PR. What is measured today is narrower: the H1/P04 branch contains no change under
`apps/backend-rag/backend/db/migrations_v2`, and no `279_*` file exists in the authoritative
checkout.

The ratified migration must also be **PostgreSQL 15 compatible**, not merely compatible with the
production engine (17.x). CI runs `public.ecr.aws/docker/library/postgres:15` in four workflows —
`tests.yml` (two service definitions, lines 501 and 1385), `fly-deploy.yml`, `intel-router-tests.yml`,
and `scripts-tests-sweep.yml` — and local `docker-compose.yml` (line 34) uses `postgres:15-alpine`.
A migration that relies on a PG16+-only feature will pass a local apply/rollback proof against
Postgres 17.8 and then fail in CI.

## Adversarial review

The Claude-authored document received two cross-family reviews, preserving generator != grader on
both passes.

- **Codex, read-only sandbox — verdict: DEFECTIVE.** It reported seven findings, all applied: the
  false repository-reference claim; an unsupported universal decay claim; mind-reading about what
  other authors knew; an incorrect prior-collision and W40 comparison; an unbounded open-PR claim;
  a late-binding overclaim; and a future commitment presented as completed evidence. Codex finding
  5 was a limitation of that reviewer's sandbox, not a document defect: the attempted network check
  returned `error connecting to api.github.com`. The orchestrator ran it successfully, and §2 now
  records the result as a time-bounded measurement rather than a standing fact.
- **Kimi K3 — verdict: SOUND.** It independently reproduced every load-bearing measurement: both
  verbatim quotations; all nine migration-table rows; head `278` and the freeness of `279` upward;
  the non-ancestor status of `b08efe3e7`; the PostgreSQL 15 inventory; and the seven-packet blast
  radius. It flagged two overstatements overlapping Codex findings 2 and 4, then discovered the
  enforcement-mechanism distinction now incorporated into §2 and §6. Neither the author nor the
  first reviewer had found it, and it changed the document's central argument from "mechanical
  enforcement is absent" to the sharper and accurate claim that uniqueness is strongly enforced
  while prose-only reservation is not representable to those mechanisms.

This document is itself evidence for the review lesson: two reviewers from different model
families produced findings that barely overlapped. The second reviewer's single most valuable
finding was invisible to the first, and the author had been wrong in the same direction as the
first reviewer.
