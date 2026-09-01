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
  `tree_at_path`, `typechange`.
- **C — whether the path is allowlisted** Pro-authoritative runtime state. `ordinary`,
  `keeplocal`.

76 of the 84 combinations are constructible; the 8 that are not are an untracked local file
meeting an incoming action on a path the base never tracked, and the runner skips them by
construction rather than recording a cell that did not run.

## The design rule

**Classify B by the TYPE of the object at `"$REMOTE:$f"` — blob, tree, or absent — never by
its EXISTENCE.** `git cat-file -e` answers "is there any object here", so a directory created
at a removed file's name answers _yes_ and every existence-based guard declines to fire. Any
future guard on this surface that asks an existence question is the same defect again.

## The register, as measured on `origin/main` at `5f174b4126`

42 cells behave correctly. 34 do not, in five named classes — only the first of which is the
defect the `--no-renames` work set out to fix:

| cells | class                                                                                                                                                                                            |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 4     | **the motivating defect** — `modified × rename_away{,_and_tree}`: rename detection hides the source, the local modification is never classified as a collision, the ff aborts every tick forever |
| 12    | `dangling_symlink × *` — an unresolved local symlink wedges every incoming action; no branch of the resolver handles a non-regular file                                                          |
| 12    | `dir_at_path × *` — a local directory where a tracked file belongs wedges every incoming action; there is no branch for a type mismatch                                                          |
| 4     | `del_unstaged × {delete, tree_at_path}` — nothing to collide with, yet the tick wedges permanently on a `cp` whose source does not exist                                                         |
| 2     | `untracked × tree_at_path` — an untracked local file meeting an incoming tree is neither backed up nor cleared, so the ff can never apply                                                        |

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

## What this instrument does NOT cover

Stated so the fourth "shape nobody asked about" has somewhere to be found:

- **Concurrency.** Every cell is a single tick against a quiet origin. Nothing here exercises
  two pullers, a lock contention, or origin advancing mid-tick.
- **The allowlist's own failure modes** — unparseable file, a path listed for another machine,
  a glob. `C` only distinguishes listed from not-listed for this machine.
- **`restore_kept_local()` beyond what a cell's final on-disk state reveals.** Its
  announcement branch also asked an existence question; no cell in this matrix discriminates
  a fix there, which is a gap, not a clean bill.
- **Path shapes**: spaces, newlines, non-UTF-8, `.gitignore` interaction, nested submodules.
- **Multi-path ticks.** Every cell moves exactly one path; real pulls move many, and an
  early abort hides the behaviour of every later path in the same set.
