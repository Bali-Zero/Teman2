# LOCALCI-GATE — can one Pro host be the gate that counts?

Mission `LOCALCI-GATE`, BLUE, lane infra/localci, Gear 3 (it moves the boundary between a candidate and its
judge). Opened by Zero in a Fable 5.1 window on 2026-10-06; the final on-disk gate is a fresh Opus 5.5 `xhigh`
session outside this chain. Prior spec: `docs/specs/localci-completion-2026-09-29.md`. Two adversarial reviews
(Codex, Gemini 3.1 Pro) attacked the first draft; their confirmed findings are folded in and listed in the pack.

## 1. Verdict

**Not today, and not by code alone.** None of the blockers below is a law of nature: each has a cure, every
cure that matters is an operator act, and once those acts are available a self-hosted _runner_ reaches the same
place more cheaply than a completed `scripts/localci`. "All 14 contexts on one host" additionally stays unproven
on capacity and wrong on availability. This verdict is about the implementation and the host as measured on
2026-10-06, not about what is architecturally possible.

| blocker                                            | true today (measured)                                                                                                                                                                                                                                                                                                                                                | cure, and whose it is                                                                                                                                                                                                                             |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Pen** — who writes the verdict                   | on Pro the judge would be OS user `nuzantara`, the user of 40 live agent CLI processes; the docker socket lives in that user's home; every session's `gh` token carries `repo` scope, which writes any commit status. A verdict authored there cannot be told from one written by the candidate's builder (already an accepted limit in the 09-29 spec, R3-2 / R4-1) | a dedicated OS user or host that no builder can enter, plus a writer identity builders cannot hold (the Actions app through a runner, or a dedicated GitHub App with a pinned `app_id`). Operator: admin password, credentials, branch protection |
| **Attachment** — which commit the verdict binds to | merge queue is ON (ruleset 19779175: SQUASH, HEADGREEN, up to 5 groups building, 90 min response timeout) and all 10 workflows behind the 14 contexts trigger on `merge_group`. Nothing on Pro reads merge-group commits today                                                                                                                                       | buildable: a self-hosted runner receives `merge_group` jobs natively; a separate controller would poll `gh-readonly-queue/main/*`. Not built; once built, the 90 min window and 5 concurrent groups turn into a capacity requirement              |
| **Capacity**                                       | **unproven, not disproven.** The 10 workflows ran 1,585 times in 24 h ≈ 133 hosted job-hours (whole workflows, including their non-required jobs) = 5.5 hosted-size (4-vCPU) jobs running at once _on average_. Pro has 14 cores in total and carries production; today's Colima VM is 4 CPU / 8 GiB                                                                 | a timed canary on Pro. The whole machine with nothing else on it is 3.5 hosted-size jobs, so the full set fits only above ~1.6× hosted per-job speed at 100 % utilisation with no peak; the ratio has never been measured                         |
| **Availability**                                   | `enforce_admins: true`, no bypass; ISP and power in Bali flap (superscar #8). With a sole local judge and Pro down nothing merges, including the fix for Pro                                                                                                                                                                                                         | a hosted fallback per job, or a second host. Moving execution does not remove GitHub's control plane from the path either way                                                                                                                     |

Recommended shape — **C′: hosted writes, local predicts, execution may move later through a runner.** §4.

## 2. Ground (re-measured this session; commands and raw output in the evidence pack)

- **Live protection**: 14 required contexts, names identical to `contexts_matrix.yaml` (drift 0, machine-checked
  by `hosted_compare.py`); `strict: false`; 0 required reviews. **11 of 14 pin no source app** (`app_id: null`);
  only Visa Oracle smoke, Merah Putih and catE pin `15368` (GitHub Actions). GitHub's REST doc says an omitted
  `app_id` means "any app if it was not set by a GitHub App". Not probed live: the probe is forging a status.
- **Runners**: 0 self-hosted registered; `runs-on` census 166 `ubuntu-latest`, 3 `ubuntu-24.04`, 2 `macos-latest`.
- **Repository**: **public**, org-owned, no licence, `allow_forking: true`, 0 forks; fork-PR workflow approval =
  `first_time_contributors`. Standard hosted minutes are free on public repositories, so no cost motive was
  found (the org's billing page was not read).
- **Local runner today** — v0.3.1 on Pro, container isolation, candidate `f42fd16429` (#7970, hosted green),
  base `991282004f`, matrix as `--contexts-file`: overall **BLOCKED** in 21 s. **0 of 14 required contexts are
  executed by the runner.** 10 are BLOCKED by mapping; the 4 the matrix calls `executed` come out UNCOVERED,
  because `runner.py` never reads the matrix's `local.steps` — `resolve_context_check` only matches a check the
  runner planned itself, and it plans none of them. The matrix's "4 executed" is a hand measurement dated
  2026-09-26, not runner coverage. The runner's own checks: classifier corpus PASS, paid-endpoint ban PASS (25
  tests, contained), `tests.scripts_impacted` ERROR (pytest rc=2 at collection, on a hosted-green commit).
- **Local suite**: no job under `.github/workflows` runs `scripts/localci/tests` (252 tests collected before this change, by hand only).
- **Pro**: M4 Pro, 14 cores, 48 GB; OS users `nuzantara` and `zantara-codex`; `sudo -n` refused (password) — a
  second OS user is a real boundary there, and creating one is the operator's.

### Per context — hosted cost, local state, and what a self-hosted runner would change

Hosted seconds: the required job itself on the 4 newest merge groups. "Runner removes it?" = would a self-hosted
Linux Actions runner remove the _executability_ obstacle; Pen, Capacity and Availability are separate (§1).

| required context                       | hosted s      | local today                                              | concrete parity obstacle                                                                                                                                                         | runner removes it?                                                                |
| -------------------------------------- | ------------- | -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| E2E Tests (Playwright)                 | ~497          | blind                                                    | Postgres + Redis `services:`, uv-locked backend on :8000, `playwright install --with-deps`; six secrets reach the job (`E2E_TEST_*`, `JWT_SECRET`, `OPENAI_API_KEY`, `QDRANT_*`) | yes — and those secrets then run beside candidate code on our metal               |
| Backend Tests (Python)                 | ~113 + shards | blind                                                    | aggregator over backend-static + 3 shards with the BASE partitioner; Postgres, lock-pinned deps                                                                                  | yes                                                                               |
| CodeQL Analysis (python)               | 312–507       | blind                                                    | README's recorded position: the CodeQL CLI is not licensed for local use here (public, no OSI licence); Pysa is a stand-in, not the same check; SARIF upload                     | only as `github/codeql-action` inside Actions; licence on own hardware unverified |
| CodeQL Analysis (javascript)           | 127–208       | blind                                                    | same                                                                                                                                                                             | same                                                                              |
| Frontend Tests (mouth, true)           | ~570          | blind                                                    | `npm ci` at root (banned from a worktree: shared `node_modules`), tsc, vitest + coverage, 7 commands                                                                             | yes (clean clone per job)                                                         |
| Every organ is born with its genes     | ~60           | blind                                                    | one test red on macOS (zsh wrapper rc=2; BSD-userland cause unverified); CI is Ubuntu + apt zsh + `it_IT`                                                                        | yes (Linux)                                                                       |
| R1 gate — adversarial review present   | ~33           | blind (hand-run 09-26)                                   | none technical: the runner plans no check for it                                                                                                                                 | n/a — cheapest to predict                                                         |
| antidotes                              | 386–501       | blind                                                    | 66 steps, 13 hand-run; xdist + detect-secrets installs; ~45 corpora unmapped; one x86 pin                                                                                        | yes on x64                                                                        |
| Harness floor recompute                | ~38           | blind (not implemented)                                  | bound to PR context: PR number, GitHub API hot-zone list, `vars.HARNESS_ENFORCEMENT`, the `harness/fable-gate` status                                                            | yes — only Actions has that context natively                                      |
| actionlint                             | ~40           | blind (hand-run 09-26)                                   | pinned linux x86_64 tarball + sha256; the local binary is a Homebrew build                                                                                                       | yes on x64; an arm64 runner needs its own asset and pin                           |
| Every guard proves guilt AND innocence | ~265          | blind                                                    | 2 tmux tests red inside a live operator tmux; apt tmux; fastapi/asyncpg                                                                                                          | yes (clean Linux)                                                                 |
| Visa Oracle fullstack smoke            | ~197          | blind                                                    | disposable Postgres, Playwright chromium                                                                                                                                         | yes                                                                               |
| Merah Putih DAY contrast law           | ~42           | blind (hand-run 09-26)                                   | the guilt control rewrites a tracked file in place                                                                                                                               | yes                                                                               |
| catE-sovereignty-lint                  | ~89           | blind (1 of 6 steps runs as `policy.paid_anthropic_ban`) | #40c needs the PR's changed files and `TYPESAFE_API_KEY`                                                                                                                         | yes — and the key lands on our metal                                              |

Workflow share of the 133 job-hours: `tests.yml` 74.7 · `security.yml` 25.5 · `immune-enforcement.yml` 13.4 ·
the seven light workflows together 19.2 (0.8 hosted-size jobs on average). Three required workflows pin x86
binaries (security, actionlint, immune-enforcement); Pro and its VM are arm64.

## 3. The shapes

| shape                                                                                                                                                                                    | verdict                                                          | deciding evidence                                                                                                                                                                                                                                                                                                                                               |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A** self-hosted runner(s) executing the existing workflows                                                                                                                             | **not now; the cheaper honest route for moving execution later** | keeps GitHub as writer and gets the merge-group attachment for free. But "unchanged" is false (`runs-on` must change or be shadowed; 3 x86 pins on arm64 metal), GitHub advises against self-hosted runners on a public repo, a runner under `nuzantara` shares the builders' user, and the full set is unproven on one host                                    |
| **B** complete `scripts/localci`, arm the adapter, make `pro/local-ci` required                                                                                                          | **closed as designed**                                           | the adapter posts with a session-class token (Pen) on the plan's candidate sha (Attachment), as one aggregate context — which cannot stand for 14 named ones unless required checks are removed, and the mandate forbids that                                                                                                                                   |
| **C** hybrid, local _binding_ for the cheap contexts                                                                                                                                     | **rejected**                                                     | a binding local context needs everything D needs; C is D on fewer contexts                                                                                                                                                                                                                                                                                      |
| **D** a separate CI controller: dedicated OS user or host, a dedicated GitHub App whose key builders cannot read, a merge-group poller, the 14 contexts written as that App's check runs | **feasible, and dominated by A**                                 | it cures Pen and Attachment. It also needs every operator act A needs (dedicated identity, hardware) plus an App key to keep, a poller to build, each context's required source re-pinned from Actions to the App, and every check re-implemented outside its workflow — where three releases produced 0 of 14. The two CodeQL legs cannot move this way at all |

## 4. Decision — C′

1. **Tier H — binding, unchanged.** All 14 contexts stay required and hosted, written by the GitHub Actions app
   on the merge-group commit. Nothing leaves the required set, nothing is renamed, nothing is stubbed.
2. **Tier L — local predictor, never binding.** `scripts/localci` exists to predict the hosted verdict before a
   push (21 s against a queue round of about an hour) and to work offline. Its claims are stated only as pairs
   measured against the writer of record: `hosted_compare.py` joins a local run with the hosted verdicts of the
   same sha. A context counts as **predicted** after AGREE on ≥ 20 distinct shas with 0 FALSE_GREEN, of which
   ≥ 3 where hosted was red — and those must include rejected candidates (PR heads that never merged), since
   merged shas are the survivors. Each pair is stored when observed (`hosted_compare.json`): a later re-run can
   replace a hosted red. Until then the context is blind and says so. The adapter stays inert — the comparison
   it was built for is a GET.
3. **Tier R — execution on our metal, optional, operator-gated.** Only through a self-hosted Actions runner
   (GitHub stays the writer, the context stays app-pinned), only for contexts already _predicted_, and only
   with all of: a dedicated OS user or host; an ephemeral Linux VM per job; same-repo `pull_request` and
   `merge_group` only; a hosted fallback when the runner is offline; the x86 pins resolved; a timed canary
   showing the load fits. Secret-bearing jobs (E2E, catE #40c) and both CodeQL legs do not leave hosted.
   First candidates: the seven light workflows.

### Sequence — each step ships with its consumer

| #   | step                                                                                                                                       | consumer / observation                                                                |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------- |
| 1   | this PR: `scripts/localci/hosted_compare.py` + this spec                                                                                   | §2's agreement line is its output on Pro; re-run from `main` after merge              |
| 2   | run `scripts/localci/tests` in a hosted job                                                                                                | the hosted gate guards the local judge's code; a broken runner goes red on its own PR |
| 3   | the runner PLANS the deterministic contexts from BASE (R1, actionlint, Merah Putih, catE first) so `executed` is something the runner does | comparator rows move from LOCAL_BLIND to AGREE, rejected candidates included          |
| 4   | Tier R, only after §5 items 1–4                                                                                                            | a non-required canary job on the self-hosted label beside its hosted twin, timed      |

## 5. §Solo-operatore

1. **Name the motive.** Tier R buys latency and independence from hosted-runner queues. It does not buy
   independence from a GitHub outage — orchestration, the writer and the merge queue stay on GitHub — and it
   saves no money while the repo is public.
2. **Pin the source of the 11 unpinned required contexts** to app `15368`. It strengthens the gate and it is a
   branch-protection edit, so it is Zero's. All 11 were observed produced by `github-actions` on 4 merge groups.
3. **Repository exposure before any runner.** Public: a self-hosted runner runs strangers' pull requests on our
   metal unless fork approval is tightened and the runner group restricted. Private: hosted minutes stop being
   free and CodeQL on a private org repository needs a GitHub Code Security entitlement — verify plan and cost
   for all 14 contexts before choosing it.
4. **Runner identity and hardware**: registration token, a dedicated OS user (admin password) or a dedicated
   host, and which host — Pro carries production, Mini sits on a separate ISP.
5. **CodeQL on own hardware**: whether the licence allows it for a public repo with no OSI licence.
6. **Arming the adapter**: recommended never. If `pro/local-ci` is wanted beside the hosted checks it stays
   non-required, and arming it (`LOCALCI_ADAPTER_ARMED`, `LOCALCI_ADAPTER_PHASE`) is Zero's.
7. **Any edit to the required set**, in either direction, and any shape-D credential (a GitHub App key).

## 6. §Meta-pattern

The single belief that keeps local-CI non-binding: **a gate is its checks — so the same checks run elsewhere are
the same gate.** A gate is three things and the checks are the cheapest: the checks, the **pen** (which identity
writes the verdict, and whether the candidate's author can hold it) and the **attachment** (which commit the
verdict binds to). Local-CI invested in the first alone, and every finding here is that belief from another side:

- the matrix says `executed` and was read as coverage, while the runner never reads those steps (superscar #2:
  a document of commands taken for an executor);
- the adapter was built to post a status before any identity existed that a builder could not also wield;
- on the hosted side 11 of 14 contexts are required by name and not by source — the name taken for the check;
- three releases hardened containment and the seal of a runner whose verdict covers 0 of 14 contexts;
- the local suite itself is guarded by no hosted job;
- and this spec's own first draft did it too: its comparator let the newest same-named entry stand for the
  hosted verdict and printed the `app_id` pin without enforcing it, until two reviewers reproduced the miss.

The cure is a form, not a feature: a local-CI claim is admissible only as a pair measured against the writer of
record — "local said X where hosted said Y on the same sha" — with the writer's identity checked. A coverage
number that is not such a pair is not evidence.

## 7. What would change this decision

- A timed canary on Pro settles Capacity either way; it does not touch Pen or Attachment.
- The operator acts of §5 (2–4) are necessary for Tier R and not sufficient: every condition of §4.3 still
  applies, `tests.yml` included, and the canary's evidence decides each extension.
- A FALSE_GREEN in the comparator's record on any _predicted_ context demotes that context to blind.
- A reason to leave GitHub's orchestration altogether would reopen shape D; nothing measured here is one.

## 8. Residuals and non-claims

- The 133 job-hours figure is an estimate of hosted workload (runs × mean job-minutes of the 6 newest runs per
  workflow, whole workflows), not a billing read and not Pro throughput.
- The comparison covers one sha: `agreement=0/14` is the starting line, not a trend.
- `hosted_compare.py` judges the hosted side red-dominant: any red entry carrying a context's name on the commit
  is red. It can therefore report a FALSE_GREEN the merge queue did not act on (a red `push` run beside a green
  `merge_group` run); it errs toward the alarm. "Any entry" means the entries GitHub lists for the commit: the
  check-runs endpoint returns the latest attempt of each check, so a red that a re-run replaced is not seen.
- It reads classic branch protection only. No ruleset requires a status check today; one that did would be
  invisible to it and would not show up as drift.
- `hosted_compare.py` has no hosted consumer for its own tests until step 2; today its consumer is the Pro run.
- Nothing in this PR posts a status, edits branch protection, registers a runner or changes a workflow.
