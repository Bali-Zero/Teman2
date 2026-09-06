## Station 3 — refutation

You are the independent reviewer of a pull request that is already applied in your
worktree. The PR's diff is reproduced at the end of this station (read it there; do not try
to regenerate it from git history). The PR's own tests are green.

PR title: `fix(secondhome): make plan save and copy failures recoverable`

PR description, as submitted:

> Report saved only when browser storage accepts the plan. Offer a selectable,
> branch-sanitized fragment link when storage or clipboard access fails. Reserve the
> Studio banner's measured height so the manual plan link stays reachable on narrow
> screens. Remove the reservation on dismissal and print.

Acceptance criteria the PR claims to meet (from the lane row):

- blocked storage is not reported as saved;
- clipboard denial offers an actionable fallback;
- the fixed consent banner cannot cover that control at maximum scroll;
- feedback to the user is truthful.

Your job:

1. Find every real defect in this diff. There is at least one. Green tests are not
   evidence of absence.
2. For each defect, write a test in the PR's own test files that is red on the PR as
   applied and would be green once the defect is fixed. Do not fix the defect — the
   author will. Run the test, show it red in EVIDENCE.
3. Give a verdict: `APPROVE`, `REQUEST-CHANGES`, or `BLOCK`, with one sentence per finding.

Scoring notes you should know: a finding that is not a defect costs a point (crying wolf
is a reviewer failure, not caution). Style remarks are not findings. A defect found without
a red test scores less than a defect found with one.

Files in scope: `apps/mouth/src/app/visa/second-home/studio/StudioApp.tsx`,
`apps/mouth/src/app/visa/second-home/studio/components/SavePlanBar.tsx` (+ test),
`apps/mouth/src/lib/secondhome-studio/plan-codec.ts` (+ test),
`apps/mouth/src/lib/secondhome-studio/copy.ts`.

Tests: from `apps/mouth`, `NODE_ENV=test npx vitest run src/app/visa/second-home/studio/ src/lib/secondhome-studio/`.
