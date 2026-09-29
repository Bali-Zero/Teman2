# Pro local-CI completion

## 1. Mandate

Mission `LOCALCI-COMPLETION-20260929`, BLUE, infra/localci, Gear 3 because the
remaining work changes the boundary between candidate execution and its judge.
Zero explicitly requested completion of the unfinished Pro build/test/deploy
work. The local coordinator remains advisory and non-required; this mandate
does not turn its inert release stub into a deployment service.

Controller worktree: `/Users/balizero/.codex/worktrees/localci-isolation/nuzantara`.
Branch: `agent/air-m5/infra/localci-isolation-0929`.
Base: `8dc84350a97c0388963be26be581766066fde823`.
Heavy execution host: Pro, repository `/Users/nuzantara/nuzantara`; reserve its
test worktree through the existing broker before writing there.

Success means the remaining runner conditions and lint-trigger observations
have current, reproducible evidence, with the reviewed change released by the
BLUE Dux and its actual consumer checked on Pro.

## 2. Owned perimeter

The implementation owner owns `scripts/localci/**`, this specification, its
computed dated evidence directory, and only the proof/status fields of the two
matching local-CI rows in `.claude/skills/modus/PENDING-ARMS.md`.
Preserve all unrelated ledger rows and main-checkout changes. No doctrine,
required GitHub checks, credentials, service settings, production data, or
other running Docker services are part of this write scope.

Parent Codex creates this brief, then transfers implementation ownership to
the Claude Dux. Read-only reviewers never mutate the implementation worktree.
Use the native managed worktree above; do not create a duplicate local checkout.

## 3. Sibling contract

The merged runner is v0.2.2. Its durable plan, candidate/base/tree identities,
fail-closed status classification, independent review requirement, single-host
lock, and inert release stub must retain their meaning. Existing plans lacking
new security evidence must not silently acquire an isolation claim.

Current GitHub scan found no open PR changing `scripts/localci/**`; two unrelated
PRs touch PENDING-ARMS, so refresh and preserve those sibling changes before any
ledger commit. A separate read-only Codex worker is reconstructing lint C2 proof.
There must be only one writer for the ledger closure.

## 4. Acceptance

Runner row opened September 27: C3 was already proved against merged main with
the guilty and innocent Pysa candidates. Remaining conditions are:

- C1: both candidate `pytest` and `trusted_pytest` execute candidate code as the
  operator today. Establish and test a boundary preventing that code from
  reading or changing host run state, trusted receipts, credentials and Pysa
  tool/baseline storage. Both paths need adversarial execution tests. Preserve
  the distinction between containment and the semantic trustworthiness of a
  pytest/JUnit verdict generated in a candidate process.
- C2: bind the Pysa executable, its dependencies/models and baseline reuse to
  measured trusted identities; replacement or tampering must block/error,
  never become an accepted clean result. Inspect setup semantics before relying
  on a rebuild, because the existing setup reuses an existing installation.
- C4: a resumed run must not mint a fresh trusted seal over state that candidate
  code could already have touched. Refuse unsafe resealing and demonstrate the
  interrupted/resumed and repeated-run cases, while retaining legitimate
  trusted-only behavior. Do not claim an operator accepted a remaining risk.

Reuse available infrastructure after measurement. Pro currently has a running
Colima `default` Docker VM and about 15 GiB free on the host. Images include
`nz-parity:1`, Python 3.11 slim/alpine and Ubuntu 24.04. These are inventory, not
proof of suitability. Do not install a second VM or disturb existing services.

Lint row opened September 27: C2(a) needs the first post-merge PR that touches
none of the eleven narrowed inputs, its head and exhaustive associated
pull_request workflow inventory showing none of the fifteen lints. C2(b) needs
the four moved merge_group workflows observed on one queue run. Existing queued
observations are leads; record exactly what was verified, including limitations.

Required evidence: existing unit suites, meaningful negative/adversarial cases,
real isolated execution on Pro, and post-release consumer verification. A passing
mocked command-builder test is not live containment evidence. No local heavy
tests on M5 and no weakening of sandbox or consent controls.

## 5. Team

Resolve roles against `docs/architecture/dual-consul/army-map.md` section 1bis.
Claude Opus 5.5 xhigh is BLUE Dux, implementation owner and release owner.
A fresh Codex reviewer outside the implementation contribution chain performs
adversarial review. A fresh Opus 5.5 xhigh session outside that chain signs the
final on-disk gate. Parent Codex coordinates checkpoints and does not ship.
Record actual model, effort, session and tested commit identities in evidence.

## 6. Appetite and stop-loss

Initial implementation checkpoint deadline: 60 minutes from Dux dispatch,
renewable only by parent coordinator after inspecting progress. At most one
implementation writer and one independent reader concurrently; no council and
no nested implementation children for this bounded continuation. At most two
repair attempts per distinct failure before returning evidence for adjudication.
Do not change accounts, permissions or architecture merely to hide a failure.
Return a reviewable checkpoint before release; parent dispatches the reviewers
and resumes the same Dux for release after their gates succeed.

## 7. Evidence and release

Compute the evidence directory with `scripts/ci/evidence_paths.py`; preserve
exact commands, exit codes, fixture identities, real host observations and
failure evidence. Keep PII and secrets out of reports and reusable prompts.

References: merged runner PR 7486, trigger-change PR 7524, C3 proof PR 7528,
lint-condition registration PR 7542. The original Pro session and its worktree
are no longer active. Recover useful receipts; do not resume a nonexistent
checkout or duplicate already-merged changes.

`Bites:` must name the local-CI consumer on Pro and its observed containment,
tamper rejection, and seal behavior, plus the GitHub trigger observations.
Do not close the runner row on unit tests alone. The Dux follows the existing
review, final gate, PR, queue, main-only release and prove-live sequence, with
separate push/create/merge operations. No Codex arming or deployment.

## 8. Seal design after review round 2 (parent decision, 2026-09-29)

The round-2 review reproduced on Pro that any seal minted for an uncontained plan can be re-minted after a
lingering same-user process erases every exposure marker, attempt, history entry and receipt reference,
resets every trusted check to QUEUED and forges a `record` verdict without touching `plan.json`. No marker in
same-user state can tell that run dir from a fresh one, so no further heuristic over erasable state is
attempted. Container plans are the supported trusted-seal path; uncontained plans lose the claim.

| plan                                   | situation                                            | runner behaviour                                                                                                                                    | `status --seal S`                                                                                                                          |
| -------------------------------------- | ---------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| container                              | no candidate code has run in the run dir             | mints the seal (flushed) before the first candidate check; trusted-only runs mint at the end                                                        | re-derives; mismatch → BLOCKED                                                                                                             |
| container                              | resumed or repeated run, seal re-derives identically | prints it as UNCHANGED, mints nothing                                                                                                               | as above                                                                                                                                   |
| container                              | resumed or repeated run, seal no longer re-derives   | prints `seal REFUSED`, mints nothing                                                                                                                | mismatch → BLOCKED                                                                                                                         |
| container                              | trusted `cmd` check asked to run after exposure      | not run; QUEUED/INTERRUPTED become BLOCKED                                                                                                          | unchanged                                                                                                                                  |
| `--isolation none` or legacy (< 0.3.0) | any run                                              | mints NOTHING: prints `seal WITHHELD`, journals `seal_withheld` at the boundary; a historical seal already in state is preserved, never overwritten | fail closed: overall BLOCKED, "seal evidence unsupported for an uncontained plan"; the recomputed value is shown only as `seal_diagnostic` |

Exact negative case (must hold on the final commit): `--isolation none` plan, full run, then erase
`candidate_exposure`, attempts, history and receipt references, reset every trusted check to QUEUED and forge
a `record` verdict with `plan.json` untouched; a resumed `run` prints no `seal=`, journals no `seal`, leaves any
stored seal unchanged, and `status --seal <any>` is BLOCKED.

Bounded execution: one budget covers the whole archive producer and copy group (`git ls-tree`, `git cat-file`,
`docker cp`); on expiry every member is killed. After each contained attempt the container's absence is
verified; if removal cannot be verified the run aborts before the next check.

## 9. Adversarial review round 3 (Codex, 2026-09-29) and the release session's cure

- **R3-1 (BLOCKER, cured):** an operator `--extra-check` of kind `cmd` ran on the host, was treated as a trusted
  check and was covered by the seal, yet it may execute candidate code. Extras now carry `"extra": true`; an extra
  `cmd` is never trusted, runs after the runner's trusted checks, counts as uncontained exposure, and a plan with one
  is treated exactly like the `--isolation none` row of the §8 table (`seal WITHHELD`, `status --seal` BLOCKED).
- **R3-2 (accepted limit, documented):** candidate code that ran uncontained as the operator's user (an
  `--isolation none` plan or an extra `cmd`) can rewrite a Pysa home together with its manifest and baseline index,
  and a later plan would pin that digest. No marker in this user's files can detect it; `plan` now prints a WARNING
  for every uncontained plan and the README states the rule: `pysa_check.py setup --home <home> --rebuild` before a
  contained plan relies on that home again.
- **R3-3 (MAJOR, cured):** a signal during the tar copy-in raised `KeyboardInterrupt`, which skipped the copy
  group's kill; the `finally` now kills and reaps every still-running member of the group.

Both cures have tests that fail when the cure is removed (mutation-checked on Pro).

## 10. Adversarial review round 4 (Codex, 2026-09-29) — last repair round

- **R4-2 (MAJOR, cured):** an extra could name a `python` the coordinator then executed for its env fingerprint and
  `pip freeze` before the seal boundary. The coordinator interpreter now comes only from runner-planned checks
  (`coordinator_python`), and an extra carrying a runner-owned key (`extra`, `isolation`, `trusted_*`) is refused at plan.
- **R4-3 (MAJOR, cured):** the copy watchdogs started outside their `try`; both now start inside it, so a signal at
  any point after the copy process exists reaches the kill in `finally`.
- **R4-1 (accepted limit, same family as R3-2):** code already running uncontained as the operator's user can rewrite
  `plan.json` and recompute its self-contained `plan_hash` (or rewrite the runner itself) and obtain a fresh seal on a
  run dir that was never contained. Nothing kept in this user's files can authenticate a plan against that user; the
  seal's guarantee is scoped to contained plans whose candidate code never ran on the host. An operator who needs more
  records `plan_hash` and the first `seal=` outside the host at plan time.

Per the PR contract (fix-of-a-fix stops at depth 1) any further finding in these families goes to a new spec, not a
fifth round on this branch.
