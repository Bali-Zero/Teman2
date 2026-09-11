# Spec — the union-merged ledger has a third dangerous shape, and the gate cannot see it

**Date:** 2026-08-31 · **Status:** SPEC, not implemented · **Surface:**
`.claude/skills/modus/PENDING-ARMS.md`, `scripts/check_ledger_no_silent_loss.py`,
`scripts/queue_unstick.py`

This document exists because the same surface has now been corrected twice in one night
(PR #5379 → #5393 → #5394) and the correction is _still_ incomplete. Agent PR Contract §8:
a fix-of-a-fix chain stops at depth 1 — when the correction is itself incomplete, the surface
is under-specified, and the next artifact is a spec, not a third reword. This is that spec.

Nothing here is implemented. It is written so that whoever implements it starts from the
constraint that defeats the obvious approach, instead of rediscovering it after shipping.

---

## 1. Why this file is special

`.gitattributes` declares exactly one union-merged path:

```
.claude/skills/modus/PENDING-ARMS.md merge=union
```

Every lane on every machine appends a row to it. `merge=union` exists so two lanes appending
at the same place do not conflict — git keeps both.

**git honours that driver. GitHub's merge machinery honours no merge driver at all.** So the
two disagree _permanently_ on any branch that appends to this file after another append has
landed: `git merge-tree` says clean, the PR page says `DIRTY`, and re-probing will never
change either answer. This is not a race and it does not resolve with time.

---

## 2. The three dangerous gestures

The first two were already documented. The third was found on 2026-08-31 by the Mini, on a
branch of its own (#5387), and is the reason this spec exists.

| #   | gesture                                        | what it destroys                                                                                   | evidence                                         |
| --- | ---------------------------------------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| 1   | **hand-resolve the conflict**                  | silently deletes the row another lane appended — the exact loss the union driver exists to prevent | caught on #5355 by `check-ledger-no-silent-loss` |
| 2   | **`git rebase` onto main**                     | rebase _applies_ the union driver, so it replays your append and **duplicates** the row            | #4060                                            |
| 3   | **a clean `git merge origin/main`, then wait** | nothing at merge time; the merge rots                                                              | #5387, 2026-08-31                                |

Shape 3 in full, because it is the counter-intuitive one:

> A session merged `origin/main` into its branch. The union driver applied cleanly. The delta
> was verified `+4/-0` **at that moment** — correct, by every check available. Main then
> advanced. Two rows another lane had since CLOSED (`- opened …` rewritten to `- closed …`)
> were still in their `- opened` form on the now-stale copy, so `git diff origin/main` had
> drifted to `+5/-2` by the time the PR reached the queue. Merging it would have **resurrected
> two rows somebody had just closed.**

**No gesture is required to make shape 3 dangerous — only time.** Any advisory that frames the
danger as "do not hand-resolve and do not rebase" is incomplete, because this case is neither.

### The rule, stated correctly

> A clean union merge is correct only at the instant it runs. It is not a durable property of
> the branch. Re-verify `git diff origin/main -- <file>` immediately before the PR enters the
> queue, not once when the merge is performed.

---

## 3. The gate's measured blind spot

`scripts/check_ledger_no_silent_loss.py` detects rows **LOST** (exit 1) and rows
**DUPLICATED** (exit 2). It does not detect rows **RESURRECTED**, and the reason is structural,
not an oversight in its logic.

Identity comes from `scripts/pending_arms_report.py`:

```python
ENTRY_START_RE = re.compile(r"^-\s*open(?:ed)?\s+\d{4}-\d{2}-\d{2}")
```

Only `- opened <date>` rows become entries. A closed row is rewritten as `- closed …` and
therefore **stops being an entry at all**. So for a stale branch:

- `origin/main` — the closed row is **not** in the entry set;
- the branch — the same row is still `- opened …`, so it **is** in the entry set.

The gate compares entry sets and sees an entry present in HEAD and absent from base. That is
**precisely what a normal, sanctioned append looks like**. A resurrection is not merely
undetected — it is _indistinguishable from the operation the ledger exists to perform_.

Measured on `origin/main`, 2026-08-31:

```
opened rows : 705
closed rows : 462
```

Every one of those 462 is a resurrection waiting for a sufficiently stale branch.

### Why the obvious fix is vacuous — this is the constraint that matters

The natural repair is: parse closed rows too, reconstruct their identity, and flag any HEAD
entry whose identity matches a closed row on main. Identity is `(opened_date, artifact)`.

**The closed form usually does not carry the opened date.** Measured on the same corpus:

```
closed rows carrying an explicit "opened YYYY-MM-DD" : 74  of 462   (16%)
closed rows from which the opened date cannot be read: 388 of 462   (84%)
```

A check keyed on `(opened_date, artifact)` would therefore be **green on 84% of the corpus
because it could not look**, not because nothing was wrong — an always-green gate wearing a
tick. Shipping it would be worse than shipping nothing, because it would close the question.

---

## 4. What an implementation must satisfy

Any candidate must answer all five before it is worth writing:

1. **Identity for closed rows.** Either the closing convention changes so a closed row always
   preserves its `opened` date (a migration over 462 existing rows, and a lint to keep it
   true), or identity is re-keyed onto something both forms carry — the artifact title is the
   only current candidate, and its collision rate over 705 + 462 rows must be **measured**
   before it is trusted, never assumed.
2. **Direction matters.** The gate deliberately permits in-place body edits, because a row's
   status legitimately advances as work progresses (`"NOT fixed"` → `"FIXED in PR #3831"`).
   A _forward_ edit is progress; a _backward_ one (closed → open) is resurrection. The check
   must model direction, not merely difference.
3. **Legitimate reopening.** If reopening a genuinely-regressed item is allowed, the check
   needs an explicit, greppable marker for it — and that marker must be one a stale merge
   cannot produce by accident.
4. **Non-vacuity proof.** The implementation must ship with a case that FAILS against the
   pre-fix gate, using the real 462-row corpus, not a synthetic two-row fixture. A gate whose
   test passes before the fix is documentation.
5. **Fail-closed on cannot-verify.** The existing gate reserves exit 4 for "a ref would not
   read; never silently treated as clean". Any new detection inherits that: if identity cannot
   be reconstructed for a row, the answer is CANNOT-VERIFY for that row — never "clean".

---

## 5. What `queue_unstick.py` should say

The advisory currently names gestures 1 and 2 and prescribes the cure. It must also carry
gesture 3, because a reader who has already merged cleanly will otherwise conclude the warning
does not apply to them — which is exactly the state #5387 was in.

The cure is unchanged and covers all three: rebuild the addition on a branch cut from **fresh**
`origin/main`, then verify `git diff origin/main -- <file>` is `+N/-0`.

Two constraints on the wording, both learned the hard way:

- **It prescribes an action an agent will execute.** It is code, not prose, and is pinned by an
  exact-match test (`test_the_driver_advice_is_exactly_what_was_reviewed`) so any reword goes
  red and a person must look. A substring test is not enough: _"reset the file to origin/main
  and manually re-apply your rows"_ IS hand-resolving, and passes every keyword assertion.
- **Do not prescribe a deletion count via `grep`.** `grep -c '^-[^-]'` reports **zero**
  deletions on this file no matter what, because every content line begins with `-`, so a
  deleted line renders as `--` and the pattern excludes it. Use `--numstat`, or classify diff
  lines in a script after skipping the `+++`/`---`/`@@` headers. (No script or workflow in this
  repo currently uses that shape — verified by `grep -rn` over `scripts/`,
  `.github/workflows/` and `infra/` on 2026-08-31. It appeared in an ad-hoc probe and is
  recorded here so it does not get written on purpose later.)

---

## 6. The alternative worth pricing before implementing any of the above

Every defect in this document descends from one design choice: **a single shared append-only
file that every lane on every machine writes to.** The union driver is a workaround for that
choice, and GitHub does not honour it.

The standard remedy for this class is fragment files — one file per lane or per entry under a
directory, concatenated by a reader (the shape `changelog.d/` uses). It removes the conflict
class entirely rather than detecting its consequences: no union driver, no DIRTY, no
resurrection, and no gate needed to catch any of them.

That is a larger change and it touches a doctrine surface referenced across the repo, so it is
**not** proposed here as the decision — only as the option that must be priced against the
five requirements in §4 before anyone spends effort on the fourth iteration of a detector.
