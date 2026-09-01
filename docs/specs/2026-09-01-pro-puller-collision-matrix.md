# Spec — the collision matrix for the Pro main puller

> Written because the surface proved under-specified, not because anyone asked for a document.
> `scripts/pro/spec_collision_matrix.sh` is the executable half; this file is the judgement half.

## Why this exists

Three consecutive adversarial passes over one small change to `scripts/pro/pro-git-pull.sh`
each found "the shape nobody asked about", and each cure was itself wrong about a neighbouring
shape:

| pass             | what it found                                                                                                                                       | the cure it produced                              | what the cure got wrong                                                     |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- | --------------------------------------------------------------------------- |
| PR #5492 refuter | `--no-renames` newly admits **removed** paths; one the worktree had already deleted wedges the tick forever                                         | a guard skipping removals of already-absent paths | nothing — but the PR had asserted the shape was _inherited_, and it was not |
| PR #5496 gate    | that guard's removal test is `git cat-file -e`, which answers **"is there any object here"**                                                        | test for a **blob**, not any object               | (not shipped)                                                               |
| —                | a directory standing at the removed file's name resolves as a **tree**, so the guard silently declines and `cp -p` runs on a file that is not there |                                                   |                                                                             |

The builder contract's rule for exactly this: _a fix-of-a-fix stops at depth 1 — if the
correction is itself wrong, the surface is under-specified, so write the spec._ This is that
spec. It is not a patch and deliberately ships no behaviour change.

## What a cell is

`resolve_collisions()` decides, per incoming path, between four outcomes. The whole family of
defects has been one mistake repeated: reading **one** coordinate and inferring the other two.

- **A — what the local worktree holds at the path.** `clean`, `modified`, `del_unstaged`
  (bare `rm`, index entry survives), `del_staged` (`git rm`, index entry gone),
  `dir_at_path`, `dangling_symlink`, `untracked`.
- **B — what the incoming change does to it.** `modify`, `delete`, `rename_away`,
  `rename_away_and_tree` (paired R100 rename whose old name a directory then takes),
  `rename_case_only` (`Subject.md` → `subject.md`), `tree_at_path`, `typechange`.
- **C — whether the path is allowlisted** Pro-authoritative runtime state. `ordinary`,
  `keeplocal`.

88 of the 98 combinations are constructible; the 10 that are not are an untracked local file
meeting an incoming action on a path the base never tracked, and the runner skips them by
construction rather than recording a cell that did not run.

Two properties of the fixtures are load-bearing and easy to get wrong. The body of the file is
long, because git only PAIRS a rename above a similarity threshold and a five-byte file is
reported as delete+add — a different cell. And the path is at the repo ROOT with a capitalised
basename, because on the case-only axis the DIRECTION of the rename decides which spelling the
resolver meets first in a sorted change set.

## The design rule

**Classify B by the TYPE of the object at `"$REMOTE:$f"` — blob, tree, or absent — never by
its EXISTENCE.** `git cat-file -e` answers "is there any object here", so a directory created
at a removed file's name answers _yes_ and every existence-based guard declines to fire. Any
future guard on this surface that asks an existence question is the same defect again.

## The register, as measured on `origin/main` at `5f174b4126`

**50 cells behave correctly. 52 do not, in six named classes** — only the first of which is the
defect the `--no-renames` work set out to fix. These figures moved on 2026-09-01 when an
independent audit graded the HUMAN half of this instrument for the first time; what it found is
recorded under "What the verdicts cost" below, because the numbers alone hide the lesson. The
arithmetic is self-checking: `awk -F'\t' '$8=="KNOWN_BAD"' baseline | wc -l` must equal the sum
of this table.

| cells | class                                                                                                                                                                                                                                                                                                                                                               |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 6     | **`modified × *`** — 4 are the motivating defect (`× rename_away{,_and_tree}`: rename detection hides the source, the local modification is never classified as a collision, the ff aborts forever); the other 2 are `× {tree_at_path, typechange} × keeplocal`, where the keep-local restore reports success while putting Pro's content somewhere nobody declared |
| 12    | `dangling_symlink × *` — an unresolved local symlink wedges every incoming action; no branch of the resolver handles a non-regular file                                                                                                                                                                                                                             |
| 12    | `dir_at_path × *` — a local directory where a tracked file belongs wedges every incoming action; there is no branch for a type mismatch                                                                                                                                                                                                                             |
| 12    | `symlink × *` — a RESOLVING local symlink is silently converted into a copy: `cp -p` dereferences it, so Pro-authoritative state that was a link comes back a file                                                                                                                                                                                                  |
| 8     | `del_unstaged × {delete, tree_at_path, modify, typechange}` — nothing to collide with, yet the tick wedges permanently on a `cp` whose source does not exist                                                                                                                                                                                                        |
| 2     | `untracked × tree_at_path` — an untracked local file meeting an incoming tree is neither backed up nor cleared, so the ff can never apply                                                                                                                                                                                                                           |

## What the verdicts cost, and which side the guard was on

Every adversarial pass before 2026-09-01 graded the MACHINE half — the fixtures, the assertions,
the comparator. The 8th column is a judgement no machine can produce, and nobody had graded it.
An audit that read all 102 rows and rebuilt seven of them against the real puller found:

- **Two `OK` verdicts that were false**, and one of them reproduced exactly:
  `modified × tree_at_path × keeplocal` loses Pro-authoritative content. `restore_kept_local`'s
  `cp -p` targets a path that is now a directory, so cp's directory-target semantics put the
  file INSIDE it — the content lands at `Subject.md/Subject.md`, cp exits 0, and the puller logs
  `restored kept-local Pro-authoritative runtime-state`. A false success. Now `KNOWN_BAD`.
- **Four `OK` rows carrying another cell's reason.** `del_unstaged × {modify, typechange}` was
  annotated with the `del_staged` fail-safe story ("mutates nothing"). Their own measurement
  refutes it: they record `backup=empty`, which is the resolver attempting a backup `cp` and
  crashing, where the genuine fail-safe rows record `backup=no` because the resolver never
  touches them. Same defect as their `KNOWN_BAD` siblings, opposite verdict, identical fields.
- **Two `KNOWN_BAD` rows that were too harsh.** `symlink × rename_case_only` carried the
  `cp -p` dereference reason, but git's pathspec is byte-literal even on a case-folding
  filesystem, so the resolver takes the untracked `mv` branch and the backup is a real symlink.
  Reproduced: `readlink` returns the target. Now `OK`.

**Not every claim survived checking — including mine, and mine was worse.** The audit reported
`modified × typechange × keeplocal` as a silent restore failure. I "refuted" it: I measured
`cp -p` onto a dangling symlink exiting **1**, saw that `restore_kept_local` inspects that exit
code and fires a P0 alert, marked the cell `OK`, and wrote that mechanism into the baseline, into
this document, and into a report. Then the auditor re-ran it and got exit **0**.

Both measurements were real. `cp -p` onto a dangling symlink exits 1 only when the target has a
**missing intermediate directory** — which is what my hand-built probe used (`/nonexistent/x`) —
and exits 0, **following the link**, when the target is a bare filename whose parent exists,
which is what the committed fixture builds (`ln -s "bystander.md"`). I had tested a shape the
instrument does not build, and I did it on the same day I told three reviewers that a probe
answering a neighbouring question is the failure to watch for.

The truth is a third mechanism neither of us named. Reproduced against the real puller: `cp -p`
follows the dangling link and **creates a regular file at the link's target name**. rc=0, log
`restored kept-local`, an untracked `bystander.md` appears at the repo root holding Pro's
content, and `git status` reports `?? bystander.md`. Reading the tracked path does return the
content — but only because the link happens to resolve to a file nobody declared, and the next
tick meets untracked litter it did not create. Now `KNOWN_BAD`, with the shape-dependence of
`cp` written into the reason so the next reader does not re-derive either wrong version.

The same correction reaches `symlink × {tree_at_path, typechange}`: both stay `KNOWN_BAD`, but
their shared reason claimed the restore "converts Pro state from a link into a copy at that
path". It does not. One nests it inside a directory, the other strews it at the link's target.
A reason that names the wrong mechanism is a `KNOWN_BAD` that will be cured in the wrong place.

**The structural lesson is where the guard was.** The baseline already refused a `KNOWN_BAD`
with no reason. It accepted an `OK` with no reason — and 46 of 102 rows were exactly that,
including both false ones. An unargued `KNOWN_BAD` is merely pessimistic; an unargued `OK` is a
defect blessed in writing, which the instrument then certifies forever. The guard now demands a
reason on the optimistic side too, wherever `OK` is a CLAIM rather than an observation: content
was set aside (`backup=file`) and the tracked path did not come back a regular file.

A wedge is `rc=1` with HEAD unmoved. Most are **permanent**: they repeat every five minutes
and nothing red ever fires, which is why they survived this long. The four cells marked `OK`
that also wedge are genuine fail-safes — origin has new content for a path the machine
deleted, and aborting keeps the deletion while mutating nothing.

## How it is armed

`spec_collision_matrix.sh` measures seven fields per cell and diffs them against
`collision-matrix-baseline.tsv`. The baseline carries an eighth, human-written column: the
verdict. The comparison is on fields 1-7 only, so the machine can never overwrite the
judgement.

**A cell that moves in EITHER direction fails.** A `KNOWN_BAD` that silently becomes `OK` is an
unreviewed behaviour change, and this surface's entire history is unreviewed behaviour changes
that looked like improvements. Curing a cell means moving it _and_ rewriting its baseline row
in the same diff, which is what makes the cure reviewable.

## The filesystem is a coordinate

The `rename_case_only` axis measures a defect that **exists only where the filesystem folds
case**. On a case-sensitive volume, `Subject.md → subject.md` is an ordinary rename between two
distinct paths: the cells still run, but they measure a different phenomenon, and the verdicts a
human wrote against the folding behaviour do not describe it.

This is not a hypothetical. The first CI run of this instrument went **red on those fourteen
cells** while the identical command was green on every machine in the fleet — Pro, Mini and M5
are APFS, GitHub's runners are ext4. Neither side was wrong. The baseline was: it had baked one
volume's answers into a file the other volume was being asked to match.

So the script **probes the filesystem it is actually running on** (in `mktemp`'s directory,
which is where the fixtures are built) and:

- on a **case-folding** volume, enumerates all seven origin actions and compares all 102 cells;
- on a **case-sensitive** volume, drops the `rename_case_only` axis, holds the corresponding
  baseline rows OUT of the comparison rather than counting them absent, and says so in its
  output — a green run there covers 88 cells and never claims otherwise;
- **refuses `--write-baseline` entirely** on a case-sensitive volume, because writing there
  would silently delete fourteen reviewed human verdicts while leaving a file that still looks
  complete. The baseline is authored on a folding volume or not at all.

That leaves an obvious question, and a refuter asked it in the sharpest possible form: if the
axis is held out on the only runner CI has, then CI can never catch a regression in the
case-collision path — not weakly, but never — and `test_pro_git_pull.sh`'s 55 assertions contain
no case-only fixture either (measured: zero). The instrument would convert a red into a green
that looks identical whether that path is healthy or freshly broken, and the class is not
hypothetical: `qwen.md → QWEN.md` landed on main in #5371.

**So the axis gets a runner that can express it.** `collision-matrix-case-folding` runs the same
script on `macos-latest`, whose APFS folds, gated on the same four puller paths so a 10x-billed
runner starts only when this surface moves. It opens with a probe that FAILS the job if the
runner is not case-folding — a job whose whole purpose is this axis must not report green while
the script holds it out.

State the residual precisely rather than claiming the gap is shut: that job is **not yet in the
repository's required checks**, so today it makes a regression VISIBLE (the PR goes red) without
being able to BLOCK the merge. Adding it to branch protection is a settings change, tracked
separately. Running the matrix locally on a fleet Mac is therefore still not redundant with CI —
it is just no longer the only thing standing between this surface and a repeat of #5371.

## Two questions, not one: assertions vs verdicts

A reader looking for an `assert_no_damage()` will not find one, and its absence is deliberate
rather than an omission. The two mechanisms here answer different questions:

- The **assertions** (`assert_local_state`, `assert_origin_action`) are PRE-conditions. They
  ask "did this cell get built the way its name says?" and abort the run when the answer is no.
  They exist because an arm that silently degenerates into its neighbour passes every downstream
  check while measuring the wrong thing.
- The **baseline verdicts** are POST-conditions, and they are human. They ask "is the behaviour
  this cell measured correct?" — a judgement no probe can make, which is precisely why the
  comparator refuses a row nobody has judged.

A machine cannot write the second, and the first cannot be deferred to review. Collapsing them
into one function would lose whichever half it kept.

## What this instrument does NOT cover

Stated so the fifth "shape nobody asked about" has somewhere to be found. This list is not
decoration: the `rename_case_only` axis was ON it as prose until someone measured it, and the
measurement produced a live regression the previous pass's cure did not reach.

- **The case-only axis is only PARTLY closed, and only on some volumes.** Measured: `Subject.md
→ subject.md` at the repo root, against all seven local states, **on a case-folding filesystem
  only** (see above — it is held out entirely in CI). Not measured anywhere: a case-only rename
  whose source is **allowlisted keep-local**, and a case-only rename of a **directory**.
- **Object types at a removed path other than blob/tree.** A **submodule / gitlink** (`commit`
  object) standing at a renamed-away name is unmeasured, and it is the same clause that
  produced two of the three regressions on record.
- **Local-state values at a rename source that the `A` axis does not name**: a mode-only change
  (exec bit), an unreadable file, and staged content differing from BOTH `HEAD` and the
  worktree — the `.staged` backup branch of the tracked arm has no cell at all.
- **`restore_kept_local()` beyond what a cell's final on-disk state reveals.** Its
  announcement branch also asks an existence question; no cell here discriminates a fix
  there, which is a gap, not a clean bill.
- **Concurrency.** Every cell is a single tick against a quiet origin — no second puller, no
  lock contention, no origin advancing mid-tick.
- **The allowlist's own failure modes** — unparseable file, a path listed for another machine,
  a glob. `C` only distinguishes listed from not-listed for this machine.
- **Multi-path ticks.** Every cell moves exactly one path; real pulls move many, and an early
  abort hides the behaviour of every later path in the same set.
- **Path shapes**: spaces, newlines, non-UTF-8, `.gitignore` interaction.
- **What a tree at a removed path's name contains, as a BEHAVIOURAL question.** The fixture
  side is now closed: the assertion pins `panel.json`'s blob HASH and counts the blobs under
  the path, so a tree built empty, misnamed, wrong-content, or carrying an extra file aborts
  the run. What remains is inert rather than undetected — `resolve_collisions()` iterates leaf
  paths and never inspects a directory's contents, so there is no behaviour here for a cell to
  measure in the first place.
