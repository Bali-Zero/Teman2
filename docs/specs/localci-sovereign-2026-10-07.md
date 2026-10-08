# LOCALCI-SOVEREIGN — the local gate decides, GitHub is storage

Ruling: `docs/rules/RULINGS.md`, RULED 2026-10-07 (Zero, option 3 of three). Supersedes the end state of
`docs/specs/localci-gate-2026-10-06.md`; that spec's measurements, per-context table and transition shape stay
valid. This document is the plan, with the acceptance of every phase and the order that never leaves `main`
without a gate.

## 1. End state

- Merges to `main` are decided by a gate that runs on our hardware (Pro first; Mini as the second host later).
- A **merger** on Pro, with its own GitHub identity, is the only principal allowed to push to `main`. It takes a
  pull request marked ready, builds the merge candidate (the PR merged into current `main`, as the queue does),
  runs the local gate on it, and merges through the API when green. Agent sessions keep opening PRs; none can
  push to `main` and none holds the merger's credential.
- GitHub keeps the code, the PRs and their history. Required status checks and the merge queue are gone.
  Hosted workflows may remain as advisory scans (CodeQL, Dependabot) if Zero keeps them; none gates.

## 2. Sequence — each phase lands with its proof before the next starts

| phase                                                     | what                                                                                                                                                                                                                                                                                                                                                                                                               | proof that it is done                                                                                                                                                                                                                 |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A** executor, light contexts (running since 2026-10-07) | `scripts/localci/runner.py` executes the required contexts from `contexts_matrix.yaml`, BASE-trusted, candidate code contained: R1, actionlint, Merah Putih, catE, organ genes, guard conformance, antidotes; CodeQL stays BLOCKED(github_hosted)                                                                                                                                                                  | `hosted_compare.py` on a merged hosted-green sha: AGREE ≥ 7 then ≥ 9, FALSE_GREEN 0; one guilt candidate per context goes RED locally                                                                                                 |
| **B** executor, service contexts                          | Postgres + Redis in docker on Pro for Backend Tests, E2E (Playwright), Visa Oracle smoke; Harness floor as an offline rule                                                                                                                                                                                                                                                                                         | AGREE ≥ 12 of 14 on merged shas; guilt per context                                                                                                                                                                                    |
| **C** merger                                              | a Pro daemon: lease per PR, merge candidate built from `origin/main`, full local gate, merge via API with ITS credential, journal of every decision; only same-repo PRs                                                                                                                                                                                                                                            | a PR merged by the merger in a sandbox repo or behind a label while GitHub still gates; the journal shows the candidate sha, the verdict and the merge sha                                                                            |
| **D** shadow                                              | the merger decides in parallel with GitHub without pushing; every disagreement is classified. A merge counts as COMPARED only when GitHub merged the decided candidate, once per PR. A compared merge needs ≥ 12 contexts compared on both sides, of which ≥ 11 `full` and at most 1 `partial`, the partial one named on the line (ruled 2026-10-08: 14 required − 2 CodeQL hosted-only − 1 E2E partial = 11 full) | READY only when compared merges ≥ 50 AND ≥ 14 days lie between the first and the last of them AND FALSE_GREEN = 0 at every level (ruled 2026-10-07: "or" was too thin — two merges 14 days apart read READY); FALSE_RED rate recorded |
| **E** the flip (operator)                                 | remove required checks and the merge queue; restrict push to `main` to the merger identity; sessions lose nothing they had                                                                                                                                                                                                                                                                                         | the first merge on `main` by the merger with no hosted check in the way; a PR pushed by a session is refused by branch protection                                                                                                     |

**Phase C, step C3a-2: the merger enqueues.** After a verdict, `merger.py` evaluates one criterion on the decision it just
made and, only when it holds and the merger is armed, puts the PR in GitHub's merge queue through the GraphQL mutation
`enqueuePullRequest(pullRequestId, expectedHeadOid = the decided head)`. It never merges or pushes itself, and `merge` still
refuses. The sub-criteria, each of which alone refuses and is named in the line's `refused` and `why`:

- no check of its own is FAIL, ERROR, STALE, INTERRUPTED, RUNNING or QUEUED, except `review.independent`, which must be
  QUEUED or PASS;
- every executed required context is OK; a BLOCKED context passes only when its mapping is `blocked` or `not_implemented`, and
  the line names each one with its mapping beside `executed_required: N/M`;
- every context branch protection requires, read live and never hardcoded, is green on the PR head, red-dominant: failure,
  cancelled, timed out, action required, pending or missing refuses, while skipped and neutral pass as they do on GitHub;
- the PR head is still the decided head; the PR is same-repo, not a draft, based on `main`, open and not in the queue (GraphQL
  `isInMergeQueue` / `mergeQueueEntry`); this head was not enqueued by an earlier tick;
- the label `localci:merge-shadow-ok` is on the PR, applied last by an account whose repository role is admin or maintain.

The arm has two halves: that label, and `LOCALCI_MERGER_ARMED=1` in the tick's environment. Without both, the merger stays
shadow and journals `would_enqueue` with the same criterion, every sub-criterion true or false, and the head oid. That line is
the proof read before arming. The flag stays OFF until a proof PR shows `would_enqueue` with every sub-criterion true and only
`armed_env` refused. The proof PR is docs-only, judged by main's code, and NOT armed with `--auto`, so the merger's enqueue is
the only path into the queue. An enqueue journals `enqueued` with the queue entry id, its position and the head oid. A failed
mutation journals `enqueue_error` with GitHub's message, redacted, and is never retried in that tick. `report` prints
`enqueued` and `would_enqueue` on the phase-E line. Every write runs under the ambient `gh` token on Pro until Zero installs
the merger's own credential (§4.1).

Phase E never precedes D. If D shows a false green, the flip waits and the executor is fixed first. The operator reads `compared_merges`, never the age of the window: error lines and undecided ticks age a journal without proving anything.

## 3. What is lost, and what covers it

| lost                                              | cover                                                                                                                                                          |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CodeQL as a gate (the CLI is not licensed here)   | Pysa taint judge (already in the runner) for python; a hosted advisory CodeQL scan if Zero keeps it; a javascript substitute is open                           |
| GitHub's parallelism (~133 job-hours a day today) | measured per phase: the executor runs contexts in parallel containers on Pro; the capacity decision is taken on the numbers phase A and B produce, not assumed |
| redundancy (Pro down = no merges)                 | Mini as a second merger host with a single lease in Postgres (superscar #10: SSOT, never two active); until then the known cost of the ruling                  |
| stranger PRs on our metal                         | the merger takes same-repo PRs only; fork PRs are read, never executed                                                                                         |

## 4. §Solo-operatore

1. The merger's identity: a GitHub App or machine user, its credential created by Zero and installed under a
   dedicated OS user on Pro that no agent session can read (the Pen blocker of the 2026-10-06 spec — curing it
   is exactly this step).
2. The flip (phase E): removing required checks and the merge queue, restricting push to `main`.
3. Whether CodeQL and Dependabot stay as advisory hosted scans.
4. The second host (Mini) and the admin password for its dedicated user.

## 5. §Meta-pattern

The 2026-10-06 mission answered "can one host be the gate?" inside a premise it never checked with the owner:
that GitHub had to remain the writer. The brief said so, the hard constraints said so, and the spec built a
careful answer on it. The owner's actual goal was the opposite. The loop's defect is the one named in that spec
for local-CI itself, turned on the loop: a document taken for a decision. A governance premise in a brief is a
LEAD; before designing on it, ask the owner one question.
