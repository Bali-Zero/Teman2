# localci — local CI runner and inert release stub (v0.4.0)

A durable coordinator that runs checks against a frozen candidate and refuses to call anything green on
missing evidence. It is a **non-required, single-host** gate: it does not replace GitHub branch protection.

## Commands (`PYTHONPATH=<worktree> python -m scripts.localci.runner ...`)

| command | what it does |
|---|---|
| `plan --run-dir D --worktree W --base B [--builder-seat S] [--builder-seats a,b] [--contexts-file Y] [--max-attempts 2] [--deadline-s 3600] [--python P] [--isolation container\|none] [--isolation-image I]` | freezes candidate/tree/base, extracts the trusted classifier from BASE, builds the check list, records the env hash |
| `run --run-dir D [--only NAME] [--timeout S] [--deadline-s S]` | executes QUEUED checks; re-queues INTERRUPTED ones inside the retry budget |
| `review --run-dir D --file review.json` | imports an independent review (sha/tree/base + `reviewer_seat` != builder, `verdict` exactly `PASS`) |
| `status --run-dir D [--quiet] [--strict]` | recomputes freshness + overall, writes `status.json/html` |
| `python scripts/localci/release_stub.py propose\|reconcile ...` | inert release journal (see below) |
| `python scripts/localci/hosted_compare.py <status.json> [--repo R] [--branch B] [--fixtures F] [--out D]` | read-only: sets the run beside the HOSTED verdicts of the same sha (see below) |

`plan` runs `policy.paid_anthropic_ban` by default: `scripts/tests/test_ban_predicates.py` is extracted from the
BASE ref and executed against the candidate tree (`trusted_pytest`; no candidate `conftest`/ini is honoured).
Trusted checks (classifier, `cmd`, `trusted_pytest`) run `python -I` (ignores user site) with `PYTHONPATH`/`PYTHONSTARTUP`/`PYTHONHOME` removed and `PYTHONSAFEPATH=1`, so a candidate `sitecustomize.py` cannot execute inside them; candidate tests (`pytest` kind) are not trusted checks.
`policy.change_map` mirrors GitHub's `changes` job (v0.3.1): `classified`, `unclassified_paths` and `empty_changed_set` are PASS
there (the last two run every job, which the BLOCKED `tests.*` records carry); any other classifier output is BLOCKED, never FAIL.
`plan.json` is re-hashed against its `plan_hash` on every `run`/`review`/`status`; an edited plan aborts. A `cmd` check with a
`trusted_pythonpath` carries the sha256 map of that directory and refuses to run when a file was rewritten, added or removed.

**Where candidate code runs (v0.3.0).** Candidate code executes in `pytest` checks (the candidate's tests) AND in `trusted_pytest`
checks (the TEST comes from BASE, but it exercises the candidate's implementation: the ban test `exec_module()`s the candidate's
`scripts/check_ban_predicates.py`). With `--isolation container` (the default) both run in a fresh container of the image pinned
by ID at plan time (`scripts/localci/candidate.Dockerfile`, built once: `docker build -t localci-candidate:1 - < scripts/localci/candidate.Dockerfile`):
no bind mount, `--network none`, `--cap-drop ALL`, `no-new-privileges`, uid 65534, no host environment. The candidate tree goes in as
a tar stream built from the OBJECT STORE (never the checkout, so ignored files such as `.env` or a venv stay out; never `git archive`,
which honours the candidate's `export-ignore`); only `/out/junit.xml` comes out (one regular file, size-capped). The host run dir,
receipts, credentials and the Pysa home do not exist inside. Containment is not trust: the junit is still written by a candidate
process, so a `pytest`/`trusted_pytest` verdict remains the candidate's to influence and the seal does not vouch for it. When docker
or the image is missing, candidate checks plan as BLOCKED — never silently uncontained. `--isolation none` is the explicit, recorded
old behaviour (operator's own OS user, advisory only); a plan frozen before v0.3.0 carries no isolation field and reads as `none`.

**The seal (C4) — supported for `--isolation container` plans only.** Trusted `cmd` checks (BASE judge/classifier on a sha-mapped
dir) run first; before the first candidate check the runner prints `seal=` (sha256 over plan + the `cmd` and plan-time `record` checks'
state and receipts, flushed) and writes the exposure marker. Record it OUTSIDE the run dir; `status --seal <≥12 chars>` re-derives it
and goes BLOCKED on a mismatch. After candidate code has run the runner never mints again: a resumed or repeated run prints the seal as
UNCHANGED when it re-derives identically, otherwise `seal REFUSED`; a trusted check is not re-run there (QUEUED/INTERRUPTED become
BLOCKED — plan a fresh run dir); runs where no candidate code ran keep minting. For `--isolation none` and legacy (< 0.3.0) plans the
runner mints NOTHING (`seal WITHHELD`): a lingering same-user process can reset such a run dir to a state no marker distinguishes from
a fresh plan, so no seal could vouch for it. A historical seal already stored is preserved, and `status --seal` on those plans fails
closed (BLOCKED, "unsupported"), showing the recomputed value only as `seal_diagnostic`. Design table and the exact negative case:
`docs/specs/localci-completion-2026-09-29.md` §8.

Every contained attempt runs its archive producer (`git ls-tree`/`cat-file`) and `docker cp` under one budget (`COPY_TIMEOUT_S`); the
container's absence is verified after each attempt, and a run whose cleanup cannot be verified aborts before the next check.

`--extra-check NAME=JSON` adds a check the operator wants beside the planned ones. It is refused when NAME starts with a reserved
prefix (`policy.`, `tests.`, `review.`, `trusted.`) or is already planned, and when the spec is not an executable kind (`cmd`,
`pytest`): an extra check can add evidence, never replace a policy verdict or record a PASS nobody ran (v0.2.2).
An extra `cmd` runs on the host and may execute candidate code, so it is never a trusted check (v0.3.0): it runs after the
runner's own trusted checks, counts as uncontained candidate exposure, and a plan that carries one mints no seal (`seal WITHHELD`,
`status --seal` BLOCKED) exactly like an `--isolation none` plan. Such plans print a WARNING at `plan`: candidate code on the host
can rewrite any Pysa home together with its manifest and baseline index — nothing kept in this user's files can tell, so run
`pysa_check.py setup --home <home> --rebuild` before a contained plan relies on that home again (accepted limit, not a check).

## Required contexts the runner executes (v0.4.0)

`mapping: executed` in `contexts_matrix.yaml` now means the runner runs the context: `plan` reads each executed context's
`local` block and plans ONE check, `local.check` (`ctx.<slug>`), which `evaluate_contexts` resolves for the context. Its
`local.steps` must account for EVERY step of the BASE copy of the context's workflow job (matched by `workflow_step`, or by a
`workflow_step_prefix` that hits exactly one step when the full name spells a banned shape): a transcribed `argv` (`$PY`,
`$BASE_SHA` placeholders), the BASE `run:` body verbatim (container only, `bash --noprofile --norc -eo pipefail`), or
`not_applicable` with a reason. `actions/checkout` and `actions/setup-python` are stood in for by the tree copy and the
interpreter. An unmapped BASE step, a `not_run` step, a `${{ }}` the matrix does not override, a `continue-on-error` step, a
trusted file missing at BASE, or a host step that would run candidate code plans the context as a BLOCKED record naming why.

| `where` | kind | what runs | trust |
|---|---|---|---|
| `host` | `trusted_steps` | `$PY -I <BASE copy of a trusted file>` or a tool whose `-version` equals the BASE workflow's pin (`tool_pins`, else BLOCKED), cwd = the candidate worktree, read as data | trusted: runs before the seal, sealed, its BASE dir sha-mapped and re-verified |
| `container` | `contained_steps` | `steps_driver.py` (runner-owned, sha pinned in the plan) runs the steps in the candidate sandbox with the BASE copies of `trusted_files` laid over the candidate's; `git_index: true` commits the frozen tree inside the container for steps that call `git`; the environment is the `merge_group` event's (`CI`, `GITHUB_EVENT_NAME=merge_group`, offline pip) | contained, like `trusted_pytest`: candidate-produced junit, after the seal |

A context is PASS only when every step it runs returns 0 and every other step is `not_applicable` with a reason; a red step
dominates (FAIL > ERROR > BLOCKED), and a step that cannot start is BLOCKED, never skipped. The driver's exit code and its
junit (one test case per planned step, in order) must agree or the verdict is ERROR. When the candidate rewrites one of the
context's `trusted_files` or its workflow, a green won with the BASE judge is reported **BLOCKED**: hosted judges with the
candidate's copy, which this run did not execute. The matrix is operator input, like the runner: pass the trusted copy with
`--contexts-file`, never the candidate's. `summary.never_claim_parity_for` lists exactly the contexts the runner does not execute
(the suite checks it); `summary.parity_gaps` lists the steps of executed contexts whose hosted twin can still differ.

## Security: Pysa taint judge (`security.pysa_python`)

CodeQL CLI cannot run on this repo (public, no OSI licence), so the python security queries are stood in for by Pysa
(Meta, MIT), chosen on a benchmark against the CodeQL flows GitHub produced for the same commit
(`~/.nuzantara-pilots/local-ci-followup/benchmark/REPORT_BENCHMARK.md`: 80 % flow recall on log-injection, 100 % on
stack-trace / path / SSRF / redirect, 135 s, 1.6 GB). The check is planned whenever the diff touches ANY non-test file under
`apps/backend-rag/backend/` (a `.gitattributes`, a `.pyi` or a config changes what Pysa sees); otherwise NOT_APPLICABLE. It is BLOCKED (never silently green) when the judge or
its models are missing at the BASE ref — they are copied from BASE like the classifier, so a candidate cannot weaken the
models that judge it — or when the Pysa home is not a measured identity:

    python scripts/localci/pysa_check.py setup --home ~/.nuzantara-pilots/local-ci/pysa-home --backend-venv apps/backend-rag/.venv [--rebuild]

**Measured home (C2).** `setup` installs the pinned pyre-check and stubs, checks the installed identity (`uv pip freeze`, stubs HEAD and
clean tree), then writes `manifest.json`: sha256 of every file under `venv/` (pyre, pyrefly, typeshed), `pyre-check/stubs/taint/` and
every linked `site/` package, plus the venv's base interpreter and its stdlib. It refuses to reuse an existing home that has no manifest
or no longer matches it (the old setup silently reused whatever venv/stubs it found); `--rebuild` wipes venv, stubs, site view and
baselines and reinstalls. `plan` runs the BASE judge's `verify-home` and pins the digest into the plan; `judge --expect-home-digest`
re-measures before any scan — a replaced binary, stub, typeshed file or site package, an added file, or a consistently re-measured
different home is rc 2 (ERROR), never a verdict. Pyre runs with `PYTHONPYCACHEPREFIX` in the run's scratch, so no bytecode cached in
the home is loaded. BASE is scanned on every judge run — no baseline cache is trusted, so a planted baseline has nothing to act on (`base_cached` in the report is always false). The anchor is that
no candidate code executes on the host any more (C1): the manifest detects legacy poisoning, replacement and in-run tamper,
not a same-user attacker who rewrites both a file and its record between runs.

Verdict = "no NEW flow versus BASE": each flow is keyed by family, source callable, sink callable and the sink
statement text (a multiset: a second identical sink statement is a second flow), so line shifts do not count; both trees are
materialised from the object store (never `git archive`, which honours a candidate's `export-ignore`); the BASE scan is cached per
(subtree sha, judge+models sha) under the home. rc 1 → FAIL with
`receipts/pysa/report.md` listing the new flows; rc 2 → ERROR (declared via `error_rcs`, a tool failure is not a verdict — and so
are a Pysa run that emits no model record and a tree with no route handler to model: both are refused, never read as clean).
Tests are out of the analysis scope, so an in-scope module that imports from a `tests/` path is reported as a `scope_escape` flow
(new versus BASE → FAIL) instead of quietly widening the blind spot; Pysa rule codes outside the five benchmarked families are kept
as `pysa_<code>` flows, never dropped. `ctx.<name>` extra checks are the operator's explicit way to cover a context locally and are
resolved as such — the operator is the runner's trusted party, the candidate never is.

## Statuses and overall

`QUEUED RUNNING PASS FAIL ERROR BLOCKED STALE INTERRUPTED NOT_APPLICABLE` (NOT_APPLICABLE needs a recorded reason).
pytest rc 1 = FAIL; rc 2-5, crash, timeout, unexecutable, zero collected, all skipped = ERROR (never a verdict on the candidate).

`overall`: **FAIL** if any check FAIL · **BLOCKED** if any ERROR/BLOCKED/STALE/RUNNING/QUEUED/INTERRUPTED, an invalid
contexts file, or a required context mapped `blocked`/`not_implemented` · **SUBSET_PASS** if every check is green but the
contexts file is missing or a required context has no local check · **PASS** only when every required context maps to a
PASS or NOT_APPLICABLE-with-reason check. SUBSET_PASS is never PASS; the release stub DENIES it.

## Interruption semantics

A RUNNING check whose recorded pid is dead becomes **INTERRUPTED** (reason carries pid and `started_at`) in both `status`
(persisted when the coordinator lock is free) and `run`. It is never PASS. `run` re-queues it only while
`attempts < max_attempts` and before the run deadline; otherwise it becomes ERROR "retry budget exhausted" and stays
blocking. SIGTERM/SIGINT during a check marks it INTERRUPTED before exiting; `kill -9` is caught by the next `status`/`run`.

## Freshness

Every receipt binds candidate sha, tree sha, base sha, plan hash and `env_hash` (python, pytest, platform, hostname, git/uv
versions, runner sha256, `deps_lock_sha256` of `pip freeze`/`uv pip freeze`, identity of every tool a check runs).
Candidate moved, dirty tree, or env drift => PASS receipts read STALE; restoring the exact state reads PASS again.
A PASS without a readable, hash-valid receipt reads ERROR.

## What the locks guarantee — and do not

`state/coordinator.lock` and `state/release.lock` are `flock`s: **single-host mutual exclusion**. They are not a
distributed fence and not an ownership guarantee — two hosts each hold their own lock. Cross-host fencing would come from
`scripts/agent_lease.py` (Redis SET-NX leases, token-owned release); this module does not depend on it. The lock owner
`{hostname,pid,token}` is journaled as evidence, not enforcement.

## Release stub (inert) and reconciliation

`propose` only appends to `state/release_journal.jsonl` and never executes anything. ALLOW_PROPOSED needs overall PASS,
review PASS, a fresh worktree, and an unused idempotency key `(candidate_sha, tree_sha, artifact_digest|"none")`; a second
ALLOW for the same key is DENY "duplicate". `reconcile` lists ALLOW_PROPOSED rows with no later ACKED row;
`reconcile --ack REQUEST` records the outcome. A future real releaser that crashes between the journal write and its side
effect gives **at-least-once** delivery: it needs an idempotent side effect plus reconciliation, never exactly-once.

## Hosted comparison (read-only)

`hosted_compare.py` reads the contexts branch protection requires LIVE and the hosted check runs and commit statuses of the run's
candidate sha, and names each required context `AGREE`, `FALSE_GREEN`, `FALSE_RED`, `LOCAL_BLIND` or `HOSTED_PENDING`. It also
reports drift between the live required names and the names the run was planned with, and which required contexts pin no source
app. Every call is a GET through `gh api`: it posts nothing and needs no arming, so the comparison the adapter was built for does
not need the adapter armed. A local verdict counts only where the runner recorded a per-context `OK` or `FAIL`; anything else is
blind. The hosted side is order-free and red-dominant: any red entry GitHub lists under the context's name for the commit is red (latest attempt of each check), and green
needs a complete entry from the required source (the pinned `app_id` when there is one). A `--fixtures` document is refused unless
it is bound to the same repo, branch and sha. Exit 0 = compared and complete, 1 = a FALSE_GREEN or name drift, 2 = unusable input,
3 = incomplete (a required context is still pending). Why this exists and what it measured first (`agreement=0/14` on 2026-10-06):
`docs/specs/localci-gate-2026-10-06.md`.

## Merger (phase C, shadow)

`merger.py` is phase C of `docs/specs/localci-sovereign-2026-10-07.md` in SHADOW mode: it decides what the local gate would
do with a pull request and journals it. It merges nothing, posts nothing, labels nothing; every GitHub API call is a bare
GET through `hosted_compare.gh_get`, and the only other traffic is `git fetch`. `merger.py merge` refuses with exit 2
whatever it is given (phase E is not armed); `merger.py --selftest` runs the triage and lease guilt/innocence offline.

    python scripts/localci/merger.py tick --node Nuzantara [--repo Bali-Zero/Teman2] [--base main] \
        [--state-dir ~/.nuzantara-pilots/local-ci/merger] [--seed ~/nuzantara] [--python <venv python>] \
        [--run-timeout 5400] [--tick-timeout 9000]

One `tick` decides at most one pull request:

1. **Node pin.** On a host whose name is not `--node`, the tick journals `skipped: node` and exits 0 without touching the lease.
2. **Lease.** An `flock` on `lease.lock` plus `lease.json` (`host`, `pid`, `pid_start`, `ts`, `lease_id`). A held flock, a
   holder on another host or a live holder pid (same start time) is respected: `skipped: lease`, exit 0. A file left by a
   dead holder on this host is reclaimed and journalled `lease_reclaimed`; one naming another host is never reclaimed by
   the merger — removing it is an operator act. Single host by construction: a second host is a later step (spec §3, a
   lease in Postgres).
3. **Queue.** Open pull requests on `--base`, non-draft, armed (`auto_merge` set) or labelled `localci:merge`. A head or base
   repository other than `--repo` is a fork: journalled once per head as `refused: fork`, never fetched. Order: a head never
   decided first, then the head whose last decision is oldest, then `created_at` — `main` moves on every merge, so plain
   oldest-first would re-decide one PR at every new base. A (pr, head, base) already decided (or skipped as `head_in_base`)
   is never run again.
4. **Candidate.** In the merger's own bare clone (`--seed` hardlinks a local clone's objects the first time; fetches come
   from `https://github.com/<repo>.git`; a `--remote-url` carrying credentials is refused), `refs/pull/N/head` must still be
   the head the API listed (else `skipped: head_moved`). The candidate is `origin/<base>` plus the head squashed into ONE
   commit — the live merge queue's `merge_method` is `SQUASH` (rules read 2026-10-07) — committed by `localci-merger` with
   the base's commit date, so the same (head, base) always yields the same candidate sha. No hook, signer or rerere runs. A
   conflict is the decision `CONFLICT`, with the conflicted paths and no run. The queue tests a PR on top of the entries
   ahead of it (up to 5 built at once); the merger tests it on `origin/<base>` alone.
5. **Gate.** `plan → run → status --seal` of the runner taken from a worktree of the BASE sha, with BASE's
   `contexts_matrix.yaml` (`trusted_base_required` holds for the merger too): the candidate's runner and matrix never judge
   it. The seal passed on is the first one `run` prints — before any candidate code runs. The runner gets an allowlisted
   environment (no token). Candidate code runs only inside the runner, contained as the runner contains it.
6. **Hosted.** `hosted_compare.compare` against the live required contexts of the PR HEAD sha — the queue's own verdict
   lands on a merge-group commit the merger cannot see; the journal line says so (`hosted_compare.note`).

A failure after a PR is picked (a merge that fails with no conflicted path, a runner that writes no status, the
`--tick-timeout` watchdog) is an `ERROR` decision for that (pr, head, base): never a verdict, not retried at that key, retried
at the next base — so one PR that always fails cannot hold the queue. A failure before (fetch, the GitHub list) and a
SIGTERM are `error` lines: nothing is decided and the next tick retries. A runner past its timeout, or still running at the
watchdog or the stop, gets SIGTERM (it marks its checks INTERRUPTED and removes its container), SIGKILL 60 s later.

State dir (`~/.nuzantara-pilots/local-ci/merger/`):

| path | what |
|---|---|
| `decisions.jsonl` | the journal (0600), one JSON line per event |
| `lease.lock`, `lease.json` | the lease; `lease.json` exists only while a tick holds it, or after a holder died |
| `repo.git/` | the merger's bare clone; `refs/merger/base`, `refs/merger/pr/<N>` |
| `base/<base sha>/` | the BASE worktree the runner runs from (one, the current base) |
| `cand/<key>/` | the candidate worktree, removed after each decision |
| `runs/pr<N>-<head12>-<base12>-<UTC>/` | the runner's run dir, plus `merger.log` (runner argv, rc, output) and `hosted_compare.json` |

Journal: every line has `ts`, `host`, `kind`. `kind=decision` (the only kind a later report counts) carries `mode: shadow`,
`pr`, `head_sha`, `base_sha`, `candidate_sha`, `overall` (the runner's PASS / SUBSET_PASS / BLOCKED / FAIL, or `CONFLICT`,
or `ERROR`), `error`, `contexts_status`, `contexts` (per required context: the runner's verdict, OK / FAIL / UNCOVERED or
the blocking status), `checks` (per check status), `seal`, `runner_rc`, `hosted_compare` (`sha` = the head, `note`,
`agreement`, `counts`, `drift`, `exit`, or `error`), `run_dir`, `elapsed_s`, `lease_id`. Other kinds: `refused`
(`why: fork`), `skipped` (`why: node | lease | head_moved | head_in_base`), `lease_reclaimed` (`stale`: the dead holder's
record), `error` (the tick exits 1, nothing is decided).

Limits, stated: the runner plans `review.independent` and leaves it QUEUED (blocking) until a review is imported, so
`overall` is never PASS in shadow today — the per-context columns are the comparison that carries information. A `kill -9`
of a tick leaves its runner child running to the runner's own deadline; the next tick removes the candidate worktree under
it, so that orphan run is never journalled.

## Tests

`PYTHONPATH=<worktree> python -m pytest scripts/localci/tests -q` (real temporary git repos; the hypothesis state machine
is skipped when hypothesis is absent).

**Hosted run.** `.github/workflows/localci-tests.yml` runs this suite on every pull request that touches `scripts/localci/**`, the
workflow, ancestor pytest configuration or conftests at the repository root or in `scripts/`, or one of the real-repo files the suite
copies from outside it (`runner.TRUSTED_CLASSIFIER_FILES`), with the candidate image built and
hypothesis installed. It is not a required context. `python scripts/localci/skip_budget.py <junit.xml>` then reads the junit report
and applies three rules; each failure is exit 1. (1) `--allow TEST_REGEX REASON_REGEX`: a skip is declared only if the regex matches
its test id and its reason, and each allowance must explain exactly one skip (none is STALE, two or more is OVERUSED); any other
skip is UNDECLARED. (2) `--require TEST_REGEX`: at least one executed test case must match; no executed match is MISSING, including
when every matching test was skipped, deselected or never collected. (3) `--min-executed N`: at least N cases executed (default 1;
331 here, the last proved hosted count). A green job therefore means: the
declared skip (the Pysa end-to-end test, which needs a measured Pysa home) is the only skip, the named required tests executed, and
at least the floor number of cases executed. Junit omits deselected and never-collected tests: an omitted test with no matching
`--require` can still pass if other executed cases keep the count at or above the floor. This does not prove every intended test ran
or that the rest of the suite is as strong as the required tests. Failures and errors stay pytest's own exit code. A blanket pattern
(empty, or matching every string) and an inconsistent report are refused, exit 2.
