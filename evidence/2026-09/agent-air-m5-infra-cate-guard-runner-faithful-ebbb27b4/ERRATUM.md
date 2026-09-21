# Erratum — evidence pack `agent-air-m5-infra-cate-guard-runner-faithful-ebbb27b4` (PR #7076)

Condition **C2** of the PASS-WITH-CONDITIONS verdict on PR #7076
([pull/7076#issuecomment-5760649866](https://github.com/Bali-Zero/Teman2/pull/7076#issuecomment-5760649866)),
ledger row `PWC-CONDITIONS for PR #7076` in `.claude/skills/modus/PENDING-ARMS.md`.
Written by the session that authored #7076. The pack is left as it was signed: this file
says where it is wrong, and each correction carries the command that shows it. Every
command below was re-run by the writing session on 2026-09-21, after #7076 merged as
`c5c8ca13c1`.

## 1. The runtime cost, "~15s" (pack `residual_risks`) and "about 18s" (brief `risks`) — unmeasured

#7069's gate (finding 4, pull/7069#issuecomment-5759798160) had already flagged both
figures as undated and not measured in CI. #7076 carried them over unchanged. The CI
measurement, one sample on each side, is the "the guards' own corpora" step:

```
$ gh run view 35596863917 --log | grep "guards' own corpora" | grep " passed"
225 passed in 4.64s        # main push, 06a7fefbbf, 2026-09-21T11:58Z — before #7076
$ gh run view 35598050723 --log | grep "guards' own corpora" | grep " passed"
259 passed in 14.97s       # pull_request, 77e7ede3f6 (#7076's head), 2026-09-21T12:10Z
```

So the harness adds **about 10s**, measured 2026-09-21 on one sample per side. It is not a
maintained figure. A later sample, main push run 35602538841 on `c5c8ca13c1`, reads
`273 passed in 15.27s`. Its extra 14 tests come from other suites, so it is not a like-for-like
comparison.

## 2. Receipt 4, "sha256 identical on both sides (4c3f9d6c...)" — the label is wrong

`4c3f9d6c…` is SHA-1, because it is `shasum`'s default. The sha256 is `e59f89ad8d75808d`, and it
too is identical on both sides:

```
$ for r in 6b4ab0a604 77e7ede3f6; do git show $r:.github/workflows/catE-sovereignty-lint.yml \
    | grep -vE '^\s*#' | shasum | cut -c1-16; done
4c3f9d6cb8d76b91
4c3f9d6cb8d76b91
$ … | shasum -a 256 | cut -c1-16
e59f89ad8d75808d
e59f89ad8d75808d
```

The claim, that the non-comment lines are unchanged, stands. Only the algorithm's name was wrong.

## 3. Receipt 4's `ts: "2026-09-21T19:5xZ"` — WITA, not UTC

The pack's two commits are `2d413b8352` at `2026-09-21T20:08:54+08:00` and `77e7ede3f6` at
`2026-09-21T20:09:14+08:00`, which is 12:08Z (`git log --format='%h %ad' --date=iso-strict`).
A receipt taken before them at "19:5x" is 19:5x WITA, which is **11:5xZ**. The trailing `Z` is
wrong. Receipts 1–3 (`11:0xZ`, `09:0xZ`) were not re-derived here.

## 4. Receipt 1, "Innocence on the final head … 47 passed" — not the final head

47 is the count of the predecessor head `eb56f26a34`. The final head `77e7ede3f6` adds
`test_default_env_carries_the_parent_interpreters_pythonuserbase` and collects **48**. Receipt 4
says so itself ("48 passed … 47 from eb56f26a34 plus …"). Re-measured on `c5c8ca13c1`, whose
test file is byte-identical to `77e7ede3f6`'s (`git diff --quiet 77e7ede3f6 c5c8ca13c1 --
scripts/tests/test_cate_trigger_parity.py` → rc 0):
`python3 -m pytest -q scripts/tests/test_cate_trigger_parity.py` → `48 passed`.

## 5. `scope_closure` and the PR body's "Not covered" summary — incomplete; the docstring is authoritative

Both list three uncovered classes: tool-less steps, tool arguments and semantics, and action
refs beyond the pin. At `77e7ede3f6` the module docstring of `scripts/tests/test_cate_trigger_parity.py`
has nine Not-covered bullets. The gate counted seven classes; this count is bullets, from the
parsed docstring. The PR that lands this file adds two more that the gate found green and
undeclared: tool runtime, and PYTHONUSERBASE present in the harness but absent on a runner.
**The authoritative Not-covered list is that docstring**, and neither summary should be read
as complete.
