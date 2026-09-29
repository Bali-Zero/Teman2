# localci — local CI runner and inert release stub (v0.3.0)

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

`plan` runs `policy.paid_anthropic_ban` by default: `scripts/tests/test_ban_predicates.py` is extracted from the
BASE ref and executed against the candidate tree (`trusted_pytest`; no candidate `conftest`/ini is honoured).
Trusted checks (classifier, `cmd`, `trusted_pytest`) run `python -I` (ignores user site) with `PYTHONPATH`/`PYTHONSTARTUP`/`PYTHONHOME` removed and `PYTHONSAFEPATH=1`, so a candidate `sitecustomize.py` cannot execute inside them; candidate tests (`pytest` kind) are not trusted checks.
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

**The seal (C4).** Trusted `cmd` checks (BASE judge/classifier on a sha-mapped dir) run first; before the first candidate check the
runner prints `seal=` (sha256 over plan + the `cmd` and plan-time `record` checks' state and receipts) and writes the exposure marker.
Record the seal OUTSIDE the run dir; `status --seal <≥12 chars>` re-derives it and goes BLOCKED on a mismatch. After candidate code has
run in a run dir the runner never mints another seal: a resumed or repeated run re-derives it and prints it as UNCHANGED only when every
candidate check ran contained and the value is identical, otherwise prints `seal REFUSED`; a trusted check is not re-run there
(QUEUED/INTERRUPTED ones become BLOCKED — plan a fresh run dir). Runs where no candidate code ran keep minting as before. Exposure is
read from the marker AND from any candidate check's attempts/history/receipt; under `--isolation none` all of that is same-user state,
so there the only evidence is the seal the operator recorded before exposure.

`--extra-check NAME=JSON` adds a check the operator wants beside the planned ones. It is refused when NAME starts with a reserved
prefix (`policy.`, `tests.`, `review.`, `trusted.`) or is already planned, and when the spec is not an executable kind (`cmd`,
`pytest`): an extra check can add evidence, never replace a policy verdict or record a PASS nobody ran (v0.2.2).

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
the home is loaded. A BASE baseline is reused only when its name carries this judge+models id AND this home digest and its bytes match
the sha256 the judge recorded in `baselines/index.json` when it wrote it; a planted or edited baseline is rc 2. The anchor is that
no candidate code executes on the host any more (C1): the manifest and index detect legacy poisoning, replacement and in-run tamper,
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

## Tests

`PYTHONPATH=<worktree> python -m pytest scripts/localci/tests -q` (real temporary git repos; the hypothesis state machine
is skipped when hypothesis is absent).
