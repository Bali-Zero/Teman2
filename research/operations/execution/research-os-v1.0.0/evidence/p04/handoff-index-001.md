---
adversarial_review: kimi-k3
---

# P04 Handoff Index — the seven Reviewer-handoff artifacts

**Purpose**: the on-disk index the P04 packet's "Reviewer handoff" clause requires — schemas,
fixtures, compatibility matrix, migration proof, hash specification, adapter loss reports, and the
list of unresolved semantic conflicts — resolved to actual `origin/main` paths, not read from a
document that merely named them. This file exists because that index previously lived only inside
a `SendMessage` between two ephemeral sessions and would have evaporated before S9-C0 (a
not-yet-started fleet session) could read it.

**Verdict**: `PASS_WITH_LIMITS` (`contract-pass-001.md` §1). **What Cohort B (P05 Intel Lake, P06
NAGA) may and may not build against is stated exhaustively in `contract-pass-001.md` §7 "What
Cohort B may and may not start on" — read that section directly. This index does not paraphrase
it and grants nothing on its own.**

**Measured at**: `origin/main` HEAD `35bb9d091cb3b9170ed16f09a2b39676886b2de7` (`docs(ledger): one
fact added, twelve hand-written copies of the count go red (#4766)`, merged 2026-08-24T09:11:19Z),
from worktree `docs-p04-handoff-index`. Every row below was re-verified in this session with
`git ls-tree -r --name-only origin/main -- <path>` against that exact SHA — not copied from an
earlier report, because `origin/main` had already moved twice while this handoff was being
discussed (PR #4783 and its follow-up #4785 both landed between the first draft of this index and
this file — confirmed by commit ancestry, `git merge-base --is-ancestor`, not by PR number, which
does not track merge order in this repo: #4766 was created before #4783/#4785 but merged after
both).

## The seven artifacts

`✅` = exists on `origin/main` as its own dedicated file, exactly as the packet names it. `⚠️` =
the underlying content is on `origin/main`, but only embedded inside another document, or as a
different artifact type than the one named — see the pointed-to annotation before treating it as
delivered.

| # | Artifact | Path(s) | On `origin/main`? |
|---|---|---|---|
| 1 | Schemas | `packages/research-os-core/research_os/schemas/*.schema.json` — 25 files (`git ls-tree` scoped to this exact directory, then `grep -c '\.schema\.json$'` on that scoped output; the directory itself lists 26 entries because it also holds `__init__.py`) | ✅ yes |
| 2 | Fixtures | `packages/research-os-core/fixtures/` — 357 files (`ls-tree` file count, not a grep of the word "fixture") | ✅ yes |
| 3 | Compatibility matrix | `research/operations/execution/research-os-v1.0.0/evidence/p04/compatibility-matrix-001.md` | ✅ yes |
| 4 | Migration proof | SQL: `apps/backend-rag/backend/db/migrations_v2/279_research_os_contract_core.sql` — ✅ dedicated file. Proof narrative: `contract-pass-001.md` §6 — ⚠️ embedded, not standalone | ⚠️ split — **see annotations 1 and 2** |
| 5 | Hash specification | `packages/research-os-core/research_os/hashing.py` | ✅ yes — code is real and dedicated; contract grade is NOT DELIVERED — **see annotation 3** |
| 6 | Adapter loss reports | `apps/backend-rag/backend/services/research_os/loss_report.py` | ⚠️ dedicated file, but the packet asked for "reports" (plural, output artifacts) and what exists is enforcement code (`assert_every_legacy_field_accounted_for()`) exercised at test time, not a generated/persisted report document |
| 7 | List of unresolved semantic conflicts | No dedicated file. Nearest matches: `freeze-change-proposal-001.md` (one specific conflict) and `contract-pass-001.md` §9 "Conditions on this PASS" (eight, each with an owner) | ⚠️ embedded only — **see annotation 1** |

## Three honest annotations — the table above is not seven green checks

**1. Artifacts #4 and #7 have no dedicated file. They are sections inside `contract-pass-001.md`,
identified by real heading, not by memory.** `git show origin/main:research/operations/execution/
research-os-v1.0.0/evidence/p04/contract-pass-001.md | grep -nE '^#+ '` enumerates every heading in
the document as it stands at this file's pin:

```
5:# P04 Deliverable 4 — Independent contract PASS
44:## 1. Verdict
91:## 2. PASS — sound and safe for Cohort B to build against
203:## 3. PARTIAL — state both halves, never round up
293:## 4. NOT DELIVERED — plainly, not softened into "partial"
392:## 5. Finding 1 — the layer is unwired
433:## 6. Finding 2 — the migration's apply/rollback proof exists but is not armed as a test
521:## 7. What Cohort B may and may not start on
554:## 8. Corrections to `SESSION-BOARD.md` — measurements, not an edit
604:## 9. Conditions on this PASS
672:## Adversarial review
```

Artifact 4's narrative half (the migration proof) lives at **§6**. The closest thing to artifact 7
(the conflicts list) is split across two places: the one dedicated, standalone semantic-conflict
document — `CONTRACTS.md` §2 vs §3's UTC-timestamp-spelling inconsistency — is
`freeze-change-proposal-001.md` (state `awaiting_conductor_decision`, not this document); the
fuller enumeration of everything still open across the whole packet is `contract-pass-001.md`
**§9** ("Conditions on this PASS," eight numbered items, each with an owner and a closure test).
Neither §6 nor §9 is titled "migration proof" or "list of unresolved semantic conflicts" verbatim
— the mapping above is this index's own construction, stated so a reader does not go looking for a
heading that was never promised.

**2. Artifact 4's "no automated test" claim, stated bare, is FALSE — and the narrower true claim
needed two separate rounds of correction to land right.** Round one (this document's earlier
draft): `grep`-ing `apps/backend-rag/backend/tests/db/` for the literal strings
`279`/`contract_core` returns zero hits, and no test file there is *named* for migration 279 — both
still hold. But that grep-zero was a substring zero, exactly the trap it looks like: opening the
full directory (45 entries, all opened by name this session) surfaces
`test_migration_280_research_os_objects_truncate_guard.py`, alongside a new migration file,
`280_research_os_objects_truncate_guard.sql` — both landed via PR #4780. **Chronology, corrected
during this file's own adversarial review (see the section at the end): #4780 (migration 280)
merged 2026-08-24T08:34:42Z, which is *before*, not after, `contract-pass-001.md`'s follow-up
freshen PR #4785 (merged 09:10:00Z) — confirmed by commit ancestry
(`git merge-base --is-ancestor 45a298eb4 b89ff092a`, exit 0), not by timestamp alone.** So migration
280 was already on `origin/main` by the time of the document's own last freshen, and it is *still*
mentioned nowhere in it (`grep -n 280 contract-pass-001.md` returns nothing, re-run against the
current tip) — a sharper gap than "landed too late to be included," because the freshen had the
chance to catch it and didn't. Migration 280 is precisely the fix for §9 condition 7 (the `TRUNCATE`
gap M1 found in the adversarial-review pass), and it has a real, dedicated, guilt-armed test — so
**"no automated test at all" is false.**

**The precise, narrower claim, re-verified this round by opening every candidate file, not by
re-grepping:** **migration 280 has a dedicated test. Migration 279 — the canonical core D2 the
Cohort B migrations (271/272/273) chain off of — does not, and no generic sweep covers it either.**
Three candidate generic runners were opened and read in full, not grepped for a name match:
- `test_migration_uniqueness.py` — does sweep every real file under `migrations_v2/*.sql`
  (`real_dir`, `test_real_migrations_v2_has_no_duplicates`), but checks **only** that no two files
  share a numeric prefix. No apply, no rollback.
- `test_migration_sql_validator.py` — `@pytest.mark.parametrize`d entirely on **inline SQL strings**
  written in the test file (e.g. `999_scratch.sql` built from a Python string), never on a real
  migration file. It proves the destructive-statement validator's own guilt/innocence pairs, not
  that any real migration applies or rolls back.
- `test_migration_contract.py` — globs `MIGRATIONS_DIR.glob("migration_*.py")` where
  `MIGRATIONS_DIR = .../backend/migrations` — a **different directory** (`migrations`, not
  `migrations_v2`) holding Python files, not SQL. Migration 279 is not in its scope by construction.

So: none of the three generic sweeps exercises 279's apply or rollback. What DOES touch 279:
- Reading `test_migration_280_...py` directly: its `@pytest.mark.integration` database tests apply
  **migration 279's own forward SQL** as a fixture-setup step (`_apply_clean()`, via the
  transaction-scoped `db_tx` fixture, rolled back at teardown) before exercising 280's guard. So
  **279's forward/apply is exercised by an automated CI test** — as an incidental dependency of
  280's tests, never as a test of 279 in its own right, and never asserted on its own (no assertion
  in that file checks that 279's apply produced the expected table/index/trigger shape — only that
  280's guard, once both are applied, behaves correctly).
- **279's own ROLLBACK is still exercised nowhere.** `_apply_clean()` never calls it; only 280's
  own rollback (`DROP TRIGGER IF EXISTS research_os_objects_no_wipe ...`) is tested.
- The `TRUNCATE` gap itself is closed and proven, guilt-armed, in the same file: the new guard
  blocks `TRUNCATE` but not `INSERT`; the guard's own rollback restores `TRUNCATE`; re-applying the
  guard re-blocks it.

Corrected statement: the manual, twice-independently-reproduced PG15.19 proof in
`contract-pass-001.md` §6 is still the only place migration 279's own apply → rollback → re-apply
cycle is proven end-to-end (§9 condition 6, "convert the manual proof into a permanent CI test," is
still open for 279 itself, unaffected by 280's landing). But "no automated test touches this
migration at all" is no longer an accurate summary: 279's forward SQL is now applied by CI on every
run of `test_migration_280_...py`, and the `TRUNCATE` gap it left behind (§9 condition 7) now has
its own closed, automated, guilt-armed proof — a fact this document is recording because
`contract-pass-001.md` does not yet reflect it.

**One-sentence summary for S9-C0**: migration 280 has a dedicated automated test; migration 279 does
not, no generic sweep exercises its apply or rollback either, and its only apply/rollback/re-apply
proof remains the manual act described in `contract-pass-001.md` §6 — reproduced twice by hand
against a throwaway PG15.19, but never automated, so it does not re-run itself the way a CI test
would.

**3. Artifact 5 (hash specification) remains graded NOT DELIVERED.** `hashing.py` exists and its
plumbing is real (RFC 8785 canonicalization, `object_hash()` wired into 25+ models), but
`contract-pass-001.md` §4 D7 — unchanged by the PR #4785 freshen — keeps the grade NOT DELIVERED:
PR #4781 (the revert of the disqualified, ledger-suspended PR #4615 fold) has merged, but the
underlying `CONTRACTS.md` §2-vs-§3 UTC-spelling conflict it was meant to fix has not been ratified
by S9-C0 — `freeze-change-proposal-001.md`'s own frontmatter still reads
`adversarial_review: pending`. **Independently checked this round, not inferred from the pending
ratification**: `git grep -n BeforeValidator origin/main -- 'packages/research-os-core/**'` returns
zero hits — the model-layer `BeforeValidator` fix that §9 condition 8 calls for has not landed
either, confirmed directly rather than assumed from the ratification state. Owner of the
ratification: **S9-C0**.

## Adversarial review

**Kimi K3 — text-only, no repo access.** Given the full document above and asked to find internal
inconsistencies, overclaims, and unverifiable claims. Seven findings were returned; each was
independently checked against the actual repository before being applied or dropped, because a
refuter can hallucinate exactly as any other model can — the same discipline `contract-pass-001.md`
applies to its own Kimi review.

**Confirmed and applied:**

- **The chronology in (then-)annotation 2 was backwards.** It claimed migration 280 (PR #4780)
  landed "after `contract-pass-001.md`'s last freshen." Checked by `git merge-base --is-ancestor` on
  the actual commit graph (not PR numbers, not timestamps read in isolation): #4780 is an ancestor
  of #4785 (the freshen), so 280 landed *before* the freshen, not after. Applied: annotation 2 is
  corrected in place, and the corrected fact is sharper than the wrong one — the freshen had the
  chance to pick up migration 280 and still didn't mention it.
- **The table read as seven green checks despite the section header disclaiming that.** `✅` was
  used uniformly across all seven rows, including #4, #6, and #7, whose own row text admits the
  named artifact does not exist as a dedicated file. Applied: the table now uses `✅` only where a
  dedicated file exists exactly as named, and `⚠️` elsewhere, with a one-line legend.
- **Annotation 3's "therefore" asserted a causal link (ratification pending ⇒ fix not landed) it
  had not independently established.** Applied: replaced the inference with a direct check —
  `git grep -n BeforeValidator` across `packages/research-os-core/` returns zero hits — so the claim
  now rests on a fact checked this round, not on an inference from a different fact.
- **The one-sentence S9-C0 summary undersold its own body's claim** ("narrated once" against the
  body's "twice-independently-reproduced" a few lines above). Applied: reworded so the summary and
  the body agree — reproduced twice by hand, never automated.

**Refuted as formulated (checked, not applied):**

- **"HEAD pin vs. main moved twice is internally confusing"** — the finding assumed PR number order
  tracks merge order. Checked directly: `git merge-base --is-ancestor` confirms both #4783 and
  #4785 ARE ancestors of this document's pinned HEAD (`35bb9d091`, from #4766, which was created
  before #4783/#4785 but merged after both, 09:11:19Z vs 08:12:03Z/09:10:00Z). The pin was correct;
  the apparent contradiction was an artifact of reading PR numbers as chronology, which this repo's
  own fleet chatter today independently warned against. A one-clause note was added to the header
  making the ancestry check explicit, so a future reader does not repeat Kimi's inference.
- **"`grep -c '\.schema\.json$'` on `ls-tree` output could overcount"** — the concern assumed the
  `ls-tree` listing was not path-scoped. It is: `git ls-tree -r --name-only origin/main --
  packages/research-os-core/research_os/schemas/` restricts the listing to that exact directory
  before the `grep -c` filter ever runs, so a match outside that directory is not possible by
  construction. Row 1's wording was tightened to say so explicitly, but the underlying count stands
  unchanged.
- **"`grep -n 280 contract-pass-001.md` proves less than claimed"** — true in the abstract (a
  substring-absence check is never a semantic-absence proof), but re-run against the document's
  current tip this round with the same result (zero hits), and the document is written in a
  numerals-not-spelled-out register throughout (every other migration in it — 279, 107, 114-116,
  139, 149-153 — is cited digit-first), which makes a prose "migration two-eighty" evasion
  implausible enough not to warrant a stronger check for this specific claim. Left as-is with no
  wording change; recorded here because the point is correct in general even where it does not
  change this file's conclusion.
