# localci — local CI runner and inert release stub (v0.6.0)

A durable coordinator that runs checks against a frozen candidate and refuses to call anything green on
missing evidence. It is a **non-required, single-host** gate: it does not replace GitHub branch protection — until the
local gate does (RULED 2026-10-07 in `docs/rules/RULINGS.md`; plan and sequence in `docs/specs/localci-sovereign-2026-10-07.md`).

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
there (the last two run every job, which the BLOCKED `tests.*` records carry, until the context that runs the job is planned:
`tests.backend_shards`/`tests.frontend_mouth` are then NOT_APPLICABLE, superseded by `ctx.backend-tests`/`ctx.frontend-tests-mouth`,
which carry its verdict); any other classifier output is BLOCKED, never FAIL.
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

## Required contexts the runner executes (v0.4.0, container shape v0.5.0)

`mapping: executed` in `contexts_matrix.yaml` now means the runner runs the context: `plan` reads each executed context's
`local` block and plans ONE check, `local.check` (`ctx.<slug>`), which `evaluate_contexts` resolves for the context. Its
`local.steps` must account for EVERY step of the BASE copy of the context's workflow job (matched by `workflow_step`, or by a
`workflow_step_prefix` that hits exactly one step when the full name spells a banned shape): a transcribed `argv` (`$PY`,
`$BASE_SHA` placeholders), the BASE `run:` body verbatim (container only, written to a file and run under GitHub's own
template: `bash -e {0}` when the step names no shell, `bash --noprofile --norc -eo pipefail {0}` for `shell: bash`), or
`not_applicable` with a written reason (a string; a flag is refused). `actions/checkout` and `actions/setup-python` are stood
in for by the tree copy and the interpreter. Env merges as GitHub's does: workflow, job, step, then the matrix's overrides. An
unmapped BASE step, a `not_run` step, a `${{ }}` the matrix does not override, a `continue-on-error` step, a job with its own
`container:` or `services:` or another `runs-on` than ubuntu-latest/24.04, a trusted file missing at BASE, or a host step
that would run candidate code plans the context as a BLOCKED record naming why.

| `where` | kind | what runs | trust |
|---|---|---|---|
| `host` | `trusted_steps` | `$PY -I <BASE copy of a trusted file>` or a tool whose `-version` equals the BASE workflow's pin (`tool_pins`, else BLOCKED), cwd = the candidate worktree, read as data | trusted: runs before the seal, sealed, its BASE dir sha-mapped and re-verified |
| `container` | `contained_steps` | `steps_driver.py` (runner-owned, sha pinned in the plan) runs the steps in the candidate sandbox with the BASE copies of `trusted_files` laid over the candidate's; `git_index: true` rebuilds BASE inside the container from the BASE blobs of the paths the candidate changed and commits the candidate on it, so `main`, `origin/main` and `git fetch origin main` name BASE, objects packed as after a fetch; the environment is the `merge_group` event's (`CI`, `GITHUB_EVENT_NAME=merge_group`, offline pip, `HOME=/home/runner`, `SHELL=/bin/bash`) under an init that reaps orphans | contained, like `trusted_pytest`: candidate-produced junit, after the seal |

The image (`candidate.Dockerfile`) is ubuntu 24.04 — the hosted runner's distribution, so `jq`, `curl`, `crontab`, `tmux`,
`zsh`, `shellcheck` answer as they do there — with python 3.12 as the default (also `/usr/bin/python3`) and 3.11 beside it.
A BASE `actions/setup-python` pin selects the default interpreter or one the image declares in `LOCALCI_PYTHONS` (its bin dir
goes first on PATH, as setup-python does); any other pin is BLOCKED. `trusted_from_steps: true` adds to `trusted_files` every
BASE `.py`/`.sh` a step names outright and every one under a directory it names with a trailing slash (`pytest
infra/organ-conformance/`); a step marked `trusted_scan: false` (a path sentinel, whose path list names the surfaces under test,
not judges) is not read. The BASE job's `timeout-minutes` is the context's budget (hosted kills the job there), else `run --timeout`.

A context is PASS only when every step it runs returns 0 and every other step is `not_applicable` with a reason; a red step
dominates (FAIL > ERROR > BLOCKED), and a step that cannot start is BLOCKED, never skipped. The driver's exit code and its
junit (one test case per planned step, in order) must agree or the verdict is ERROR. When the candidate rewrites one of the
context's `trusted_files` or its workflow (a change of tree entry: bytes, mode or type), or — for a container context — any
`.gitattributes`, a green won with the BASE judge is reported **BLOCKED**: hosted judges with the candidate's copy (or
materializes other bytes), which this run did not execute. The matrix is operator input, like the runner: pass the trusted copy with
`--contexts-file`, never the candidate's. `summary.never_claim_parity_for` lists exactly the contexts the runner does not execute
(the suite checks it); `summary.parity_gaps` lists the steps of executed contexts whose hosted twin can still differ.

**Coordinator interpreter.** The env fingerprint hashes the coordinator venv's `pip freeze`. A venv holding an editable install
of a moving checkout (Pro's backend-rag venv carries `cell_core` from the main checkout, so its freeze names that checkout's
HEAD) drifts whenever the checkout moves mid-run, and every receipt goes STALE, as it should. Measure from a venv that tracks
nothing (on Pro: `~/.nuzantara-pilots/local-ci/merger/venv`, the merger's own python3.11 + PyYAML + pytest venv from the arm block
below; `executor-a/venv311` went with the executor-a directory in the 2026-10-08 cleanup) and diff its freeze at
the start and the end of a run when a STALE needs explaining.

## Service contexts (v0.6.0)

A context with `expressions: true` is a **service context** (kind `contained_jobs`): its BASE job and every job it `needs:`
(listed in `local.jobs`, each mapped step by step like any container context) are planned from the BASE workflow and run in
order, each matrix leg in its own fresh sandbox. What the runner reproduces, and what it refuses:

| surface | how | BLOCKED when |
|---|---|---|
| `services:` | BASE's spec only (the candidate's is never read); image via the operator-pinned `service_images` map, id pinned at plan; BASE's literal `env:`; docker health flags only; started before the job, removed after it (`docker rm -f -v`, verified: the anonymous volumes a service image declares die with it) | the tag has no pinned stand-in (tag drift), an option is not a health flag, a port map is not identity, it declares `volumes:` (nothing is ever mounted), env holds an expression (named, never its value), or a service is not healthy within its own health budget |
| networking | the first service owns a loopback-only netns (`--network none`); other services and the job join it, so `localhost:5432` answers as on hosted | — |
| `${{ }}` | `gh_expr.py` (runner-owned, sha-pinned, shipped beside the driver): `github`, `env`, `matrix`, `needs`, `steps`, `vars`, `runner`, status functions; `if:`, `env:`, `run:` evaluated at run time, `continue-on-error`, step `timeout-minutes`, `$GITHUB_OUTPUT` | `secrets.*`, `github.token`, `hashFiles`, `inputs`, any other function, a `GITHUB_ENV`/`GITHUB_PATH` write; the queue ref (`github.ref`, `merge_group.head_ref`) when `plan` has no `--pr-number`; a declared `env.X` in a text the runner evaluates itself (an artifact name or path, a host reader's argv, a checkout ref), where env is empty — a value hosted holds is never read as `''`, and the refusal names the step and variable, never a value |
| install steps | verbatim, offline: the **deps image** (`localci-deps:<recipe digest>`) is the candidate image plus a wheelhouse at `/opt/wheels` built at plan time from the candidate's requirement files reduced to `name==version` pins (`--only-binary`: no build backend runs), the declared extra packages, `deps.node`, and `deps.fetch` files (https, sha256-pinned, outside the tree); verified by label and layer chain on the pinned candidate image | a requirement file is absent, the build fails, or a fetch pin differs |
| egress step | a step marked `side: egress` runs alone in a bridged sandbox holding only its named `inputs`, after a one-shot `rewrite`; its `egress_trusted` files must equal BASE | an input differs from BASE, the rewrite does not match once |
| host reader | a step marked `side: host` must be `$PY <a trusted file present at BASE>`: the BASE copy runs under `-I` at **plan time** (secrets stripped; `gh` answers with its stored login, a read) and its rc is frozen into the plan, folded in at the step's position | any other argv |
| artifacts | `upload-artifact`/`download-artifact` marked `emulate: true` are copied out of the stopped sandbox and laid into the fan-in's tree (≤ 256 MiB) | an upload with no files and `if-no-files-found: error` fails the step, as hosted |
| `needs` | each upstream job's result (`success`/`failure`) and the matrix's `needs:` stand-ins (the `changes` job's merge_group outputs) | a needed job neither planned nor stood in; an upstream that could not run stops the chain (ERROR/BLOCKED, never a downstream green) |

`runs_when` reads the trusted change_map: when hosted would skip the jobs, the context is `NOT_APPLICABLE` (a skipped required
context is satisfied). The workflow file and any changed `.gitattributes` are judges: a green won with BASE's copy while the
candidate changed it is reported BLOCKED. `bare_venv: false` keeps the image interpreter (the job installs with
`uv pip install --system`).

Node jobs (E2E, Visa Oracle smoke) add three deps keys, all built into the same deps image at plan time:

- `npm: package-lock.json` — the candidate's lock and the manifests it installs (root and each declared workspace, read as
  data) fill an npm cache in the official `node:<deps.node>` image with `npm ci --ignore-scripts`: network, no package code.
  Every lock entry must resolve to `https://registry.npmjs.org/` with an `sha512` integrity, be a declared workspace link, or
  name a GitHub repository at a full 40-hex commit (npm fetches its https tarball; no git, no credentials); anything else (a
  tarball URL, a moving git ref, a path) is BLOCKED. `npm:` may list several locks (a standalone app that runs its own `npm ci`). The job's own `npm install` then runs verbatim, offline
  (`npm_config_offline`), its lifecycle scripts inside the sandbox.
- `playwright: chromium` — the lock's `playwright-core` version, from the registry, runs `install --with-deps chromium` as
  root with network at build (`PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright`); the job's browser-install step needs root and
  network the sandbox never has, so it is `not_applicable` with that reason.
- `apt: [postgresql-client]` — OS packages the job's own bounded installer finds already present (`apt_install.sh` exits 0).

A required context that is one leg of a matrix (`Frontend Tests (Next.js) (mouth, true)`) names it with `leg:`; an include-only
matrix expands as hosted expands it. A network failure in the egress sandbox (a timeout or refused connection in its log) is no
verdict on the candidate (the step is BLOCKED, never green; a vulnerability finding stays a verdict): re-run. So is a host reader whose own stderr line starts with the matrix's `no_verdict_when` three times running (the harness gate reader's `CANNOT-VERIFY`, a GitHub 5xx); text it merely echoes cannot trigger it. A BASE `actions/setup-node` pin must equal `deps.node`, or the context is BLOCKED. Repository secrets a step reads are
overridden with `""` in the matrix (the run never holds them, and never reads the operator's); the parity gaps say what that
can change.

### Capacity on Pro (measured 2026-10-07, Colima aarch64, 4 CPU, 8 GiB, 60 GiB)

Checks run one after another and so do a service context's legs (parallelism 1): the backend shards take up to 6 GiB each
and the VM has 8. In-sandbox CPU is the driver's `RUSAGE_CHILDREN` per step; a sibling lane's runs shared the host.

| check | wall s | in-sandbox CPU s | legs (wall / CPU s) |
|---|---|---|---|
| ctx.backend-tests | 1318 | 1365 | static 150/51 · shard 1 321/370 · shard 2 288/472 · shard 3 475/455 · fan-in 85/17 — shards at 4 xdist workers; since B4 they run 2, wall not yet re-measured |
| ctx.harness-floor | 67 | 0.5 | one leg; the Gear ≥ 2 reader ran at plan |
| ctx.e2e-tests | 320 | 207 | one leg: backend + Next.js build + 134 Playwright specs (PR-B2, 1df44b9b65) |
| ctx.frontend-tests-mouth | 297 | 515 | the (mouth, true) leg: contract check, tsc, vitest with coverage, core, admin, wa-mirror |
| ctx.visa-oracle-smoke | 138 | 47 | one leg: disposable DB, signed TEST RulePack, the fullstack Playwright spec |
| whole run, 14 required contexts | 2267 (B1) · 2784 (B2) | — | plan 6-9 s with the deps images cached |

**Shard workers (B4).** `pytest -n auto` starts one xdist worker per CPU, 4 on this VM, and one worker peaks ~2.1 GB
anon-rss: 4 x 2.1 GB exceeds the leg's 6g memory cgroup (no swap), the kernel OOM-killed a worker, xdist printed
`[gwN] node down: Not properly terminated` and shard 2 hung to its 1800 s kill in 4 of 5 merger runs (2026-10-07/08).
The matrix's backend-shard job sets `PYTEST_XDIST_AUTO_NUM_WORKERS=2`: the same command and tests, files whole per worker,
coverage `full`. Hosted runs 4 workers on 16 GB; the cap is a local capacity adaptation that goes the day the VM is resized.
A leg killed on timeout after such a line says so in its reason (worker, log line) and stays ERROR, never FAIL.

The deps image (`localci-deps:<digest16>`, 9.85 GB: 294 aarch64 wheels, node 24, the fetched files) is built once per
recipe: 394 s cold at plan (download, install, export), then a cache hit while the candidate's pins and the image are unchanged.
E2E and Visa Oracle smoke share one recipe (the backend closure plus node 24, the root lock's npm cache, chromium and
postgresql-client: 11.9 GB, its Python layers shared with Backend Tests'); Frontend Tests' node-only recipe is 1.4 GB.

## What a verdict covers, and what is no verdict (B3)

**Coverage travels with the verdict.** Each matrix entry declares `coverage: full` (the default when absent) or
`coverage: partial` with a `coverage_note` naming the subset; a value the runner cannot read is `partial`. `plan` freezes it
from the BASE matrix and every `contexts.results` row of `status.json` carries it. `hosted_compare` keeps the class (a partial
AGREE is still AGREE) but puts `coverage` and `coverage_note` on the row, prints a COVERAGE column, and counts apart:
`agreement_full`, `coverage.compared_full`, `coverage.compared_partial`, `coverage.compared_unrecorded` (a `status.json`
that predates B3). The merger journals each context's coverage beside its verdict; `report` counts a compared merge on ≥ 12
compared contexts of which ≥ 11 `full` and at most one `partial` (a partial context never counts as full), prints
`compared_merges=N (full_only=M, with_partial=K)`, `compared_partial` and `compared_unrecorded` on the window line, and the
phase E line names the partial context of the compared merges. A decision journalled before B3 carries no coverage record: its
contexts are unrecorded and never count as full. The enqueue criterion treats a partial context as executed and passing,
and names it: `executed_required=13/14 (partial: E2E Tests (Playwright))`. A partial FALSE_GREEN is still a FALSE_GREEN.

**A full disk is no verdict.** After every service leg (its log and its egress log) and every contained check, the runner
reads the output line by line for the error lines a write on a full disk prints: libuv/npm `ENOSPC: no space left on device`
and `npm error code ENOSPC`, CPython `[Errno 28] No space left on device`, asyncpg/psycopg `DiskFull(Error): <message>`,
postgres `could not extend file "<path>": ...`, and a C tool's strerror line ending `: No space left on device` that carries
no Python exception name; a service Postgres `the database system is in recovery mode` counts only after one of them. One
such line makes the context `ERROR` with a reason that starts `host_disk_full: <leg>: <first line>` (never FAIL, never OK,
even when the step exited 0, as npm does), and a service chain stops there. A test named `test_enospc_*`, a fixture raising
`OSError("no space left on device")` or an assertion quoting the phrase keeps its verdict. `status.json` names it on the
context (`no_verdict: host_disk_full`), `hosted_compare` reads it as LOCAL_BLIND (never FALSE_RED), and the enqueue
criterion counts it as not executed and refuses, naming it apart from the contexts that are not OK (`host_no_verdict`).
Measured 2026-10-08 against every tracked file: the patterns hit only docs, evidence, the ledger and one fixture of a
workflow that no required context runs (`scripts/test_cost_breaker_deadman.sh`).

**A free-space floor before a service leg.** Before the first container of a service leg, the runner reads the docker host's
free space once per `run` (`df -Pk /` in a throwaway `--network none`, `--cap-drop ALL`, uid 65534 container of the pinned
candidate image; 0.14 s on Pro) and refuses the leg when it is under `LOCALCI_MIN_FREE_GB` (GB of 10^9 bytes, default 12: one
backend shard's sandbox writes 7-10 GB on Pro's 58.8 GB Colima VM, which also holds ~47 GB of images, measured 2026-10-08).
The context is `BLOCKED` with a reason that starts `host_disk_below_floor <free>GB<floor>GB:` — no verdict, never a FAIL; a
probe that cannot read the host is `host_disk_unmeasured`, a floor that is not a number ≥ 0 is `host_disk_floor_invalid`, and
`0` turns the floor off without reading anything. The merger passes `LOCALCI_MIN_FREE_GB` from the tick's environment to the
runner (the only addition to its allowlist) and its criterion counts such a context as not executed, never as a FAIL, and
refuses. The reading is cached for the run: a leg that starts later in the run is judged on the first reading. Measured on
Pro at 07:31Z on 2026-10-08, with the shadow merger running PR #8060's E2E legs: 3.58 GB free (3500604 KiB available, 95% of 61.6 GB used) — under
the default floor every service leg there would be BLOCKED until space is freed or the floor is set in the tick's environment.

**A red read with a rewritten judge is no verdict (B5).** The plan names the trusted files each step reads (`trusted` on the
step). When the candidate rewrites one of them (`judge_modified`), a FAIL or ERROR on that step is `BLOCKED` with a reason
that starts `judge_rewritten: <step> read red with the BASE judge while the candidate rewrites <files>`, never FAIL; a red on a
step whose judges were not rewritten stays FAIL and decides. A rewritten file no step names (the workflow itself, a
`.gitattributes`) reaches every step, and a service context's job steps carry no per-step attribution: those are judged at
context scope, and the reason says so. `status.json` names it (`no_verdict: judge_rewritten`), `hosted_compare` reads it as
LOCAL_BLIND and the enqueue criterion refuses it. The candidate's own judge is not run: a PR that rewrites a judge is the
reviewer's.

**A skip is compared as a skip (B5).** A context the trusted change_map does not select is NOT_APPLICABLE, its verdict OK as
on GitHub, and its result carries `skipped: change_map`. `hosted_compare` puts `skip` on the row with the hosted conclusion:
`agreed` (`NOT_APPLICABLE (skip agreed: change_map)`, full: the classifier's decision is what was compared), `hosted_ran`
(`NOT_APPLICABLE (skipped here; hosted ran)`, partial and named: the local verdict is a subset), `hosted_skipped`
(`OK (executed; hosted skipped)`, full). The merger journals `skipped` per context; `report` prints `compared_skip_agreed=N`
on the window line and, on the phase E line, how many full contexts of the compared merges were skip agreements. The
compared-merge rule is unchanged. A decision journalled before B5 records no skip: its skips read as executions.

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
candidate sha, and names each required context `AGREE`, `FALSE_GREEN`, `FALSE_RED`, `LOCAL_BLIND`, `HOSTED_PENDING` or (B10) `HOSTED_STALE`. It also
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
   the base's commit date, so the same (head, base) always yields the same candidate sha. Git runs with no host or caller configuration (`GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`,
   `GIT_ATTR_NOSYSTEM=1`, every inherited `GIT_*` variable dropped; `core.hooksPath` and `core.attributesFile` are
   `/dev/null`, `core.fsmonitor` is off) and no signer or rerere. A
   conflict is the decision `CONFLICT`, with the conflicted paths and no run. The queue tests a PR on top of the entries
   ahead of it (up to 5 built at once); the merger tests it on `origin/<base>` alone.
5. **Gate.** `plan → run → status --seal` of the runner taken from a worktree of the BASE sha, with BASE's
   `contexts_matrix.yaml` (`trusted_base_required` holds for the merger too): the candidate's runner and matrix never judge
   it. The seal passed on is the first one `run` prints — before any candidate code runs. The runner gets an allowlisted
   environment (no token) with the same git isolation, so its own git calls on the candidate see no host config or hook
   either. Candidate code runs only inside the runner, contained as the runner contains it. `plan` gets `--pr-number <N>`
   whenever the BASE runner's own source takes that flag, so `merge_group.head_ref` names the PR as the queue's does (the
   Harness floor context parses it); a BASE runner older than the flag is planned without it, never broken by it.
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

Journal: every line has `ts`, `host`, `kind`, and `code_sha` when the launchd wrapper ran it (the origin/main commit the
merger was extracted from). `kind=decision` (the only kind a later report counts) carries `mode: shadow`,
`pr`, `head_sha`, `base_sha`, `candidate_sha`, `overall` (the runner's PASS / SUBSET_PASS / BLOCKED / FAIL, or `CONFLICT`,
or `ERROR`), `error`, `contexts_status`, `contexts` (per required context: the runner's verdict, OK / FAIL / UNCOVERED or
the blocking status), `checks` (per check status), `seal`, `runner_rc`, `hosted_compare` (`sha` = the head, `note`,
`agreement`, `counts`, `drift`, `exit`, or `error`), `run_dir`, `elapsed_s`, `lease_id`. Other kinds: `refused`
(`why: fork`), `skipped` (`why: node | lease | head_moved | head_in_base`), `lease_reclaimed` (`stale`: the dead holder's
record), `error` (the tick exits 1, nothing is decided — `gh` or `git` missing from PATH included).

**Replays (B11).** Besides deciding open pull requests, the tick judges **the exact commit GitHub merged**: a *replay*. The tree GitHub
tested in its queue is the main commit that merged the PR, so the gate takes that commit as the CANDIDATE and its FIRST PARENT as the
BASE (trusted: it was on main before the merge, the candidate never supplies its own judge), and `hosted_compare` joins on the merge
commit's own sha, where the `merge_group` runs sit. Selection: the NEWEST merge commit on `refs/merger/base`'s first-parent line, from the
journal's first PR decision on, whose subject ends `(#N)` and which GitHub confirms (PR `N` is merged and its `merge_commit_sha` is this
commit), with no replay yet (B11b: main takes more merges a day than the gate decides, so oldest-first never catches up — the first live
replay, 2026-10-09T09:54Z, judged pr8015's merge of 10-07 on a base whose runner executed no context, and 81 more merges stood between
it and the first base on which a PR decision compared 12 contexts, `86b151beec` of 10-08; newest first, a replay reads a current base and the current deps recipe,
and the merges it leaves behind are not owed: phase D counts compared merges, it does not need every merge; a merge can then be
seconds old at the fetch, so a commit whose PR GitHub still shows open is asked again on the next replay turn); a commit GitHub does not confirm is journalled once (`skipped: replay_unmapped`), an ERROR replay is retried
once. Any failure of a replay but a stop (`Stopped`: no verdict, the same replay is decided next) is its ERROR decision line, with
`replay`, `merge_commit` and the redacted error (`<Type>: <message>` when it is not a gate error), so the alternation advances and the
retry bound holds; a PR decision keeps its old rule (a gate error is its ERROR line, anything else the tick's `error` line or a crash).
Alternation: a tick replays when the previous decision line was not a replay (`schedule: "alternation: the previous decision was not a
replay"`), and also when it has no pull request to decide (`"no pull request to decide"`); otherwise it decides a PR as before.
The line is `kind: decision` with `replay: true`, `pr`, `merge_commit`, `base_sha` (the first parent), `head_sha` (the PR head GitHub
merged, recorded only), `candidate_sha` (the merge commit), `schedule`, and every field of a PR decision; it enqueues nothing, writes no
`would_merge` and nothing to GitHub, and its hosted comparison is never stale (the same tree). Why: measured on Pro 2026-10-09, 17 of 26
merged PRs were merged by GitHub onto a main that had moved while the gate ran (a tick takes 10-48 minutes), so a decision on the base
the gate saw could never be the commit GitHub merged. `merger.py report` counts a replay row as `merged_here` when GitHub's
`merge_commit_sha` for the PR, read at report time, still equals the replayed commit (else the row joins on the head and compares nothing
as merged), a compared merge when `compared_enough`, a PR once whichever way it qualified, and prints `replays (B11): N replay
decision(s) ...; compared_merges=C of which R reached the threshold only through a replay` (`window.replays`,
`window.compared_merges_from_replays`). A replay's recorded FALSE_GREEN is never re-read for staleness: it counts in `N` and is listed
under `kept` as `pr<N> all rows: replay: the same tree on both sides, never stale`.

**A gate verdict not posted yet is no verdict (B12).** `ctx.harness-floor` reads the real `harness/fable-gate` verdict with BASE's
`harness_gate_read.py` on the host, at plan time. A pull request whose session has not posted that status yet makes the reader exit 1 with the
stderr line `::error::harness_gate_read: PENDING` (measured on Pro 2026-10-09: 10 of the gate's 12 `FALSE_RED` decisions). The step's
`pending_when` (beside `no_verdict_when`, matrix key) maps that line, **line-anchored on stderr** and on a non-zero exit, to `rc: None`
with the reason `gate_pending: host, at plan: ...` and the structured flag `gate_pending: true`, frozen in the plan's `precomputed`: the
step, the context and `overall` are BLOCKED, never PASS and never FAIL, so `hosted_compare` and the report read the context as BLIND, not
`FALSE_RED`, and `executed_contexts_ok` still refuses a merge on it. Unlike CANNOT-VERIFY it is **not retried**: a posting session takes
minutes, not the 40 s of the retry waits. A real verdict line (`verdict = 'failure'`, REWORK, BLOCK) stays FAIL, and the same text on stdout
cannot fake it. **The mark is the flag, never text**: `_run_leg` copies the plan's flag onto the BLOCKED step it answered, and the context
result carries `gate_pending: true` only when it is BLOCKED and every step that did not pass is such a read (a second BLOCKED step, or a red
one, stays BLOCKED after the post); the check's state keeps the flag of its current attempt only, and `evaluate_contexts` names the context
`no_verdict: gate_pending` from it, never from its 600-character reason. A test runs BASE `scripts/ci/harness_gate_read.py` and checks that
its not-posted stderr line starts with the matrix's `pending_when` and that its posted states (`pending`, `failure`, `error`) do not.
The decision line records `gate_pending: true` and `gate_pending_contexts` (the GitHub names, as the BASE matrix named them in the plan)
**only when its `overall` is BLOCKED**: on a FAIL elsewhere the missing gate verdict changes nothing. `triage` never re-decides the same
`(pr, head, base)`, and posting a status moves neither head nor base, so a `gate_pending` key becomes eligible again **only when both hold**:
the head carries a `harness/fable-gate` commit status in any state (`repos/{repo}/commits/{head}/statuses`), and every hosted check run named
as a pending context (`repos/{repo}/commits/{head}/check-runs?check_name=<name>&filter=latest`, the latest attempt per check suite)
**completed after that status's newest `updated_at`**. Until the session runs `gh run rerun`, hosted still holds the pre-post PENDING red, and
a local OK decided beside it would be journalled a FALSE_GREEN that nothing clears. No run, one still in progress, one completed before the
post, or a failed read: not eligible this tick. Both reads are read-only GETs through `hosted_compare.gh_get`, paged and bounded like the
hosted compare's. At most 3 `gate_pending` decisions per key; past the cap the key stays decided and `skipped: gate_pending_cap` is journalled
once. Replays (B11) are unaffected: they judge a commit GitHub already merged (its gate was posted before it merged), their lines carry
`replay: true`, and `triage` reads only non-replay decisions. `merger.py report` prints `gate pending (B12): N decision(s)`, counting
non-replay decisions only. A re-opened key sorts last in `triage` and B11's alternation may put a replay first, so the second decision comes
on the key's next turn while the base is unchanged — not necessarily the next tick.

**A hosted verdict given before the gate verdict was posted is stale (B12b).** B12's re-opened key does not cover every race: the PR's
session posts `harness/fable-gate` AFTER GitHub's `pull_request` run of `Harness floor recompute` already failed on the PENDING read, then
re-runs that job; when the local gate decides the PR between the post and the re-run (typically at a NEW base, main moves about every
30 min), the local reader reads `success` while GitHub still lists the pre-post red, and the row would be journalled a context FALSE_GREEN
that B10's tree-drift rule never clears — one honest race holding READY for 14 days. The merger hands `hosted_compare.compare` a second
judge beside B10's (`gate_judge=GateJudge(repo, stale_judge, plan_at, reads)`, called `judge(context, hosted, statuses)`; B10's
`judge(context, completed_at)` is unchanged). It applies only to a compared row whose hosted verdict is RED and whose context is
**gate-reading: its BASE matrix entry has ONE step (its own or one of its jobs') with `pending_when`**, named by its `workflow_step` —
structural, never a context name. The row is `HOSTED_STALE` with `stale_why: "gate_posted_after_hosted"`, `hosted_completed_at`,
`gate_posted_at` and `plan_at` only when all hold: (a) **the local run read a success**: the newest `harness/fable-gate` status (the head's
combined status) whose `updated_at` is at or before the run's plan time (`plan_at`, the run dir's `state/plan.json` `created_at`, stamped
once the plan's host reads are done) is `success`, AND the plan froze rc 0 for that context's reader step (`frozen_reads(run_dir)`: the
`precomputed` answer of every planned job step whose side is `host`, under the seal) — a `failure`/`error` post, or a frozen answer that is
not rc 0, beside a local verdict is a REAL disagreement and keeps its class; (b) every red entry of that name is a check run concluded
`failure` (not `cancelled`/`timed_out`/…), the newest of them completed strictly BEFORE that status; (c) each red run failed on the PENDING
read and nothing else, on two independent readings: its annotations (`GET repos/{repo}/check-runs/{id}/annotations`, paged; 50 or more
raw entries is GitHub's per-job cap, so a list that long may be cut and is unknown) carry at least one failure annotation whose message
starts with the matrix's `pending_when` minus its `::error::` prefix, at most one `Process completed with exit code N.`, and no other
failure (`notice`/`warning` do not count, any other level does); AND its job (`GET repos/{repo}/actions/jobs/{id}`, whose `check_run_url`
must end in `/check-runs/{id}`, so the identity of job and check run is checked on every read, not assumed) lists the reader step exactly
once, it is the job's ONLY step concluded other than `success`/`skipped`, and every step the BASE matrix lists after it is `skipped` (the
runner's own `Post …` / `Complete job` steps run after a failure and conclude `success`, so only the matrix's later steps are required
skipped). The annotation shape was read from #7526's PENDING log (receipt R8 of `evidence/2026-10/agent-air-m5-ci-bites-head-tree-v3-ac882ce3`);
neither API was called for B12b, the tests use fakes. Any other red, a red commit status, a red completed at or after the post, a status
dated only after the plan (with the combined status, an earlier post it replaced is not seen: kept), or a hosted GREEN keeps its class
(`gate_check: fresh (<why>)`). A plan time, frozen reads, matrix, status time, annotation or job read that cannot be read or matched is
`gate_check` and `stale_check: unknown (<why>)`, the class kept; without B10's judge the row's `stale_check` is the gate judge's own word.
`HOSTED_STALE` is not compared, exactly as B10's; no local verdict, check or READY threshold changes. **Where it is judged:** the tick's
`hosted_summary` (the decision's `hosted_compare.stale` entry carries the B12b keys; a B10 entry still carries all of B10's, a missing one
raises as before), and every RED row of `hosted_compare.json` journals `hosted_red`, the red entries it stood on (`id`, `conclusion`,
`completed_at`; a status has id null); the report's own per-decision comparison; and the report's re-judgement of recorded tick-time
FALSE_GREEN rows, which finds EVERY recorded red run again by its id among every attempt of the head's check runs of that name
(`check-runs?check_name=<name>&filter=all`: a re-run after the post hides it from the latest), one of them completed at the row's
`hosted_completed_at`, and judges them the same way (a recorded status is judged as one) — a row without `hosted_red` (journalled before
this rule) or a recorded run no longer listed red is `gate: unknown` and kept. A reclassified row is listed as `pr<N> <context>: hosted ran
<ts>, before the gate post at <ts> the local run read (gate_posted_after_hosted)`; a kept one carries the ground's word as `gate` beside its
B10 `why`. Replays are never judged on it. The PR-level class (merger vs GitHub) is still not judged for staleness (B10's residual).

**Phase F, shadow (F1): `would_merge`.** After every `would_enqueue` / `enqueue_*` line of a decided PR the tick journals ONE
`kind: "would_merge"` line (decisions that reach the enqueue step; CONFLICT, ERROR and skipped decisions carry none): the merge phase F will make, rehearsed with `git merge-tree --write-tree` of the mirror's
`refs/merger/base` and the decided head. F1 merges nothing and pushes nothing: `merge-tree --write-tree` leaves objects in the
mirror's object store, never a ref, a worktree or an index. A git failure lands on the line as `error` (redacted) with `ok` false
and never changes the decision or the tick's exit code (a failed journal write is printed to stderr, never raised). The one
network read is `git ls-remote origin refs/heads/<base>` (read-only, 30 s bound, no ref and no object written): the tick fetches the
mirror once and a gate run can outlast several merges, so `base_current` asks GitHub, the authority until phase F proper. Fields: `pr`, `head_sha`, `base_sha` (the decision's), `mirror_main`
(what `refs/merger/base` resolves to now, the base the merge is rehearsed on), `remote_main` (GitHub's main by `ls-remote`, null
when unreadable), `base_current` (decision base == `remote_main`; false when `remote_main` is null), `head_unchanged`, `merge_tree` (the
merged tree's sha, or null), `clean`, `conflicts` (paths, `[]` when clean), `criterion` (the enqueue path's own sub-criteria, with
`label_privileged`), `armed_env`, `bites` (the PR body carries a `Bites:` line; the text is never kept), `ok` (every
sub-criterion AND `base_current` AND `clean`), `lease_id`, `code_sha`. `merger.py report` prints
`phase F shadow: would_merge=N (ok=M, conflicted=K, base_moved=J, errors=E)` (a conflict never counts a git error, which counts under `errors`;
a conflict needs a tree and no error, a moved base needs a readable `remote_main`) and carries it in `window.would_merge` beside
`phase_f: "shadow"`. An illustrative line (invented shas, not a Pro journal line):

    {"kind": "would_merge", "pr": 8123, "head_sha": "<40 hex>", "base_sha": "<40 hex>", "mirror_main": "<same 40 hex>",
     "remote_main": "<same 40 hex>", "base_current": true, "head_unchanged": true, "merge_tree": "<40 hex>", "clean": true, "conflicts": [], "bites": true,
     "armed_env": false, "ok": false, "criterion": {"review_independent": false, "...": "..."}}

Limits, stated: the runner plans `review.independent` and leaves it QUEUED (blocking) until a review is imported, so
`overall` is never PASS in shadow today — the per-context columns are the comparison that carries information, and the report below sums them. A `kill -9`
of a tick leaves its runner child running to the runner's own deadline; the next tick removes the candidate worktree under
it, so that orphan run is never journalled.

**Phase F, the executor (F2): disarmed by construction.** The same call that journals `would_merge` also decides, now, whether to MERGE. Every
`would_merge` line carries `phase_f: {armed, why}`; `armed` is true only when ALL of these hold, checked at that moment, and `why` names
each one that does not (a disarmed tick does exactly what F1 did and adds only this field):

| condition | `why` when false |
| --- | --- |
| env `LOCALCI_MERGER_PHASE_F=1` in the tick's environment | `LOCALCI_MERGER_PHASE_F unset` |
| phase D READY, recomputed from the journal by `report(emit=False)` — the report's own function, so the thresholds (>= 50 compared merges over >= 14 days, 0 FALSE_GREEN) exist once. Evaluated LAST and ONLY when `LOCALCI_MERGER_PHASE_F` is `1` and every local condition in this table already holds (the full report costs about 4 minutes and hundreds of GitHub reads) | `READY false` / `READY unreadable: ...` / `READY not evaluated` (a local condition above is already false) |
| `<state>/deploy_key` exists, is a regular file (a symlink is not), mode exactly 0600, owned by the running user — read with `lstat` only, its content is never opened | `deploy_key missing` / `mode 0644, not 0600` / `not a regular file` / `not owned by the running user` |
| the decision meets the C3a-2 criterion exactly as `enqueue_step` computed it (`enq["criterion"]`, every sub-criterion incl. `label_privileged`), and the enqueue step journalled `would_enqueue` — never `enqueued`, `enqueue_refused` or `enqueue_error` (GitHub's merge queue path owns those; `LOCALCI_MERGER_ARMED` must be UNSET in phase F) | `criterion false: <names>` / `enqueue step '<kind>', not 'would_enqueue' ...` |
| F1's `would_merge`: `clean`, `base_current` (GitHub's main by `ls-remote` == the decided base), the mirror's `refs/merger/base` == the decided base, and the tree F1 rehearsed equals the tree of the candidate the gate judged (`rev-parse <candidate_sha>^{tree}`; a `merge=union` attribute or any merge-strategy difference would make them differ) | `merge not clean` / `base_current false` / `mirror main is not the decided base` / `merged tree differs from the judged candidate tree` / `judged candidate tree unreadable` |
| the PR re-read at the moment of merging (one GraphQL read, made only when nothing above already says no): head == the decided head, state OPEN, not in the merge queue, not a draft, base == the tick's base and the `localci:merge-shadow-ok` label still present | `head_unchanged false: ...` / `PR state ...` / `the PR is in GitHub's merge queue now` / `the PR is a draft now` / `PR base ...` / `label ... absent at the moment of merging` / `head re-read failed: ...` |
| no sticky halt file `<state>/phase_f_halt` (present means present: a dangling symlink, a directory or a non-UTF-8 file halts too, reason `unreadable`; the report's `phase_f_halted` follows the same rule) | `phase_f_halt present: <reason>` |

When armed: (1) the merge commit is made in the mirror with `git commit-tree` on the tree F1 rehearsed — it writes an object and no ref, so
nothing half-written can exist — parents `refs/merger/base` (first) then the decided head, author and committer `localci-merger`, subject
`<PR title> (#<N>)` (B11's `PR_SUBJECT` recognises it), body = the decision's `ts`, lease id and `run_dir` plus the PR body's `Bites:` line;
(2) `kind: merged` is journalled (`pr`, `head_sha`, `base_sha`, `merge_commit`, `tree`, `decision_ts`, `run_dir`, `lease_id`); (3)
`git push origin <merge_commit>:refs/heads/main`, plain, never forced: any rejection, error or timeout is `kind: push_refused` (redacted
stderr tail) plus the **sticky halt file** `<state>/phase_f_halt` — no further merge until an operator removes it, and the mirror keeps its
`refs/merger/base`; a push that landed moves `refs/merger/base` to the merge commit and journals `kind: pushed` (`mirror_updated`). A
failure making the commit is `kind: merge_error`: nothing pushed, no halt, the next decision retries. The key reaches ONLY the push
subprocess, as `GIT_SSH_COMMAND="ssh -F /dev/null -o IdentityAgent=none -i <state>/deploy_key -o IdentitiesOnly=yes -o BatchMode=yes
-o GlobalKnownHostsFile=/dev/null -o UserKnownHostsFile=<state>/known_hosts -o StrictHostKeyChecking=yes"` (no user ssh config, no
agent, no system-wide known_hosts, only github.com's host key the operator pinned in `<state>/known_hosts`); the runner's env is an allowlist and never sees it. The key's PATH, never its content, can
appear in a refused push's error line (ssh names the identity file it could not use); the content is never opened by the merger.
`--push-url` refuses ANY userinfo on a non-ssh scheme (`https://token@...`, `https://u:p@...`, any case): it would be stored in the
mirror's config; an ssh user (`ssh://git@...`) is a name, not a secret. A push interrupted by SIGTERM or an interrupt writes the sticky
halt BEFORE the interruption propagates (its outcome is unknown), and a refused push writes the halt BEFORE it journals
`push_refused`. The push goes to `--push-url` (default, on the GitHub fetch URL: `git@github.com:<repo>.git`, the ssh form a deploy key
is registered for; `git remote set-url --push` on the mirror).

The fetch no longer rewinds an authoritative main: once a `pushed` line exists and the halt file is absent, the tick fetches GitHub's main
into `refs/merger/incoming` and takes it only when it is a descendant of (or equal to) the last `pushed` merge commit; otherwise it
journals `kind: storage_diverged`, writes the halt file, keeps `refs/merger/base` and exits 1. (A merge made but never pushed is no
anchor. While the halt file exists the fetch is the plain one of before, and the guard fires again the first tick after an operator
removes the halt, until GitHub's main again contains the last pushed merge.) There is no re-anchor gesture: clearing a halt is an operator act, done only after reconciling GitHub's main with the mirror, and after reading why: a
`push_refused` can be a plain race (a commit reached GitHub's main between the `ls-remote` and the push).

READY precheck: before the full report (about 4 minutes on Pro's journal, hundreds of GitHub reads) the tick asks the journal alone whether READY can be true yet — the first decision (less `READY_SPAN_SLACK_DAYS` = one day: the report's span runs on GitHub's `merged_at`, which can precede its own decision line by up to one tick) to now under `READY_MIN_DAYS`, or fewer than `READY_MIN_MERGES` distinct decided PRs (both constants are the report's own) — and says `READY false: journal window N.N days (+1 of slack) < 14` without running it. Neither runs unless the env half and every local condition hold: a disarmed tick pays for neither (`READY not evaluated`). The precheck only ever short-circuits to false; past it the full report decides.

Arming order (spec §2 phase F): (1) phase D READY; (2) the deploy key generated on Pro at `<state>/deploy_key` (0600) and registered with write, and github.com's host key pinned into `<state>/known_hosts` (verified out of band against GitHub's published fingerprints; the push uses `StrictHostKeyChecking=yes`, so without it the push is refused and halts) — operator[secret]; (3) the phase E flip, `scripts/localci/phase_e_flip.py --apply` (lands in its own PR, not on main yet): `merge-queue-main` restricted with the DeployKey bypass, then `main`'s classic protection (14 required checks, reviews, `enforce_admins`), which no deploy key bypasses, deleted — operator[gui]; (4) the live wrapper re-installed and identical to main's (`cmp -s ~/.nuzantara-cron/localci_merger_tick.sh scripts/localci/localci_merger_tick.sh` from an `origin/main` checkout — until then it force-fetches `refs/merger/base` and a storage divergence rewinds it) and `LOCALCI_MERGER_ARMED` unset (with it set every armed decision is `enqueued` into GitHub's queue and phase F never acts); (5) `LOCALCI_MERGER_PHASE_F=1` in the tick's environment, only after (3) and (4): before them the first push is refused and writes the sticky halt.

Report: `phase_f` reads `shadow` until the window holds a `merged` or `push_refused` line, then `armed (N merged, M refused)`;
`phase_f_halted` and the line `phase F executor: ...` (with `HALTED` when the file exists) say the rest; the READY line is unchanged.

### Report (phase D's instrument)

    python scripts/localci/merger.py report [--repo Bali-Zero/Teman2] [--base main] [--state-dir ...] [--since 2026-10-07]

Reads the journal strictly (an unreadable line, a state dir bound to another repo or a decision of another repo is exit 2,
never skipped) and sets every `kind=decision` line since `--since` (`YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SSZ`) beside what
GitHub did with that head, through GETs: the PR (`pulls/N`), the merge commit's parents and the live required contexts.
GitHub's side is the required contexts of the judged sha — the merge commit when the queue merged the decided candidate, else
the head — red-dominant (RED, else PENDING, else GREEN). Merging is no verdict: a merged candidate whose merge commit has not
reported is PENDING, one whose merge commit carries a red required check is RED. The merger's side is GREEN only for
`overall=PASS`, RED only for `FAIL`; everything else (BLOCKED, SUBSET_PASS, CONFLICT, ERROR) is blind. Classes per decision:
`AGREE`, `FALSE_GREEN` (merger PASS, GitHub red), `FALSE_RED`, `BLIND`, `PENDING` (GitHub has no verdict yet).

Apart from the classes, the report reads the required checks on the merge commit of every PR the window decided that GitHub
merged, whichever candidate the merger decided (a merge the merger never decided is no evidence about either gate), and lists as `hosted_red_merged` each one GitHub merged with a required check red there (PR,
merge commit, red contexts; one printed line each). #8026 is the case: decided on an older base, so its row is judged on its
green head and is not a compared merge, yet its queue commit 2a1e00e0d3 merged with `antidotes` red. That is a HOSTED
failure: counted apart and printed on the phase E line as information, and by itself it never blocks READY. A local false
green on a candidate the queue merged still does — a context the local gate passed and the merge commit failed is a context
FALSE_GREEN, and a local PASS against that red is a decision FALSE_GREEN.

Why GitHub merges a red required check (measured 2026-10-07 by GET only). `main`'s merge-queue ruleset 19779175
(`merge-queue-main`, active, no bypass actor) sets `grouping_strategy: HEADGREEN` (`max_entries_to_build` 5,
`max_entries_to_merge` 4) — the UI's "Only merge non-failing pull requests" turned off: a PR whose own group commit fails may
merge when the last entry of its group passes. The classic protection lists `antidotes` among its 14 required contexts
(`strict: false`, no app pinned). #8026's queue commit 2a1e00e0d3 had `antidotes` red (merge_group run, attempt 1); #8027's
queue commit 9637bf5a5e, built on top of it and green on all 36 checks it ran, carried the group, and both merged at
17:18:25Z. The local gate judges every candidate on its own, so it refuses what this queue setting lets through. Changing the
setting is Zero's call, not this code's.

Because the runner leaves `review.independent` QUEUED, `overall` is never PASS in shadow and the per-decision FALSE_GREEN
count is vacuous today. The phase-D instrument is the CONTEXT level, in two parts that are both counted:

- **now:** for every decision whose gate ran, `hosted_compare.compare` of its per-context verdicts against GitHub's, summed over
  the window (`AGREE`, `FALSE_GREEN`, `FALSE_RED`, `LOCAL_BLIND`, `HOSTED_PENDING`). When the queue merged the decided head ON
  THE DECIDED BASE (the merge commit's only parent is the decision's `base_sha`), the comparison is made on `merge_commit_sha` —
  the very candidate the queue tested and pushed, which carries the `merge_group` runs (measured on #8012 → 56c6f70d86: 18
  merge_group workflow runs); any later `push` run of a same-named check on that commit counts too, red-dominant, which can
  only ADD a false green. Otherwise it is made on the head. A merged PR with no merge sha is exit 2.
- **`HOSTED_STALE` (B10).** `hosted_compare` never reads a timestamp by itself; the merger hands it a `StaleJudge`. A compared row (AGREE,
  FALSE_GREEN or FALSE_RED) whose hosted verdict completed BEFORE the base the local run used becomes `HOSTED_STALE` when main changed
  between the main the hosted run merged (the newest first-parent commit of the decision's `base_sha` dated at or before the hosted
  `completed_at`, `hosted_main`) and `base_sha` in a path the BASE `change_map.py` selects for that context (the matrix's `runs_when`; the
  classifier runs as the runner runs it, `-I` and a stripped environment). The class is counted apart, never in AGREE, FALSE_GREEN or
  FALSE_RED, never a compared context, and the row carries `hosted_completed_at`, `hosted_main`, `main_moved_paths` (the selected ones,
  at most 20) and `main_moved_count`. Only on evidence: an unreadable `completed_at`, mirror, matrix or change_map, or a context with no
  `runs_when`, keeps the class and sets `stale_check: "unknown (<why>)"`. The tick computes it going forward (the decision's
  `hosted_compare.stale` / `stale_unknown`); for the past, the report re-reads each recorded FALSE_GREEN row's `hosted_compare.json`, reads the
  head's check-runs through read-only GETs (branch protection, the check-runs and the statuses of the head) and applies the same rule from the mirror, writing nothing, and prints
  `false_green=N (recorded=R, reclassified HOSTED_STALE=S: [pr7961 Backend Tests (Python): main moved <paths> after hosted ran <ts>], kept=K: [pr7961 Backend Tests (Python): unknown (<why>)])`:
  READY reads `N`, the remaining false greens, and every kept row says why it was kept (`recorded_kept_false_green` in the JSON). A recorded red that is no longer the hosted verdict is never reclassified.
- **at tick time:** the `hosted_compare.counts.FALSE_GREEN` each decision line recorded. A red GitHub later re-ran green, or a
  context it stopped requiring, cannot erase a disagreement once seen.

The window line separates `merged_prs` (PRs GitHub merged) from `compared_merges`, and counts the window's `error` lines and
`skipped` lines by reason. A merge is COMPARED when GitHub merged the very candidate the merger decided (the decided head, its
merge commit's sole parent the decided base) and at least 12 contexts had a verdict on both sides, at least 11 of them of
FULL coverage and at most one partial, named (`MIN_COMPARED_CONTEXTS`, `MIN_COMPARED_FULL`, `MAX_COMPARED_PARTIAL`; ruled
2026-10-08: 14 required − 2 CodeQL hosted-only − 1 E2E partial = 11 full): a merge compared on blind contexts is no evidence,
a partial context never counts as full, an unrecorded one counts toward nothing, and the window line prints
`compared_merges=N (full_only=M, with_partial=K)`. Each compared PR counts once, at
GitHub's `merged_at` — two decisions of one PR, or the journal's order, cannot widen the span. **The operator reads
`compared_merges`, not `days`:** the phase E line says READY only on 0 FALSE_GREEN AND ≥ 50 compared merges AND ≥ 14 days
between the first and the last compared merge (spec §2, ruled 2026-10-07: both, never either) — a window that only aged,
with nothing compared, is never READY, and until phase B lands no merge is compared at all. Days are floored in integer
seconds (13.9999 is not 14; 14 is). Three silences are printed: the longest gap between DECISIONS (errors and skips keep a
journal busy without deciding anything), the longest between any two journal lines, and the age of the last line (a merger
that stopped writing at all), never negative — a line dated in the future (a host clock ahead) is counted and printed
instead. Rows carry the `code_sha` that wrote them, the window lists the code shas it saw and counts the decisions without a
valid one (lines older than provenance are counted, never refused). A recorded FALSE_GREEN that is not a
non-negative integer, a timestamp that is not exactly `YYYY-MM-DDTHH:MM:SSZ`, or a merged candidate without `merged_at` is an
unusable input. The ticks line prints the longest and the median decision time and the slowest run of each check in the
window (the runner's `duration_s`, journalled per decision as `durations`). The report writes `<state-dir>/report.json`.
Exit 1 on any FALSE_GREEN (per decision, per context now, or recorded at tick time), 2 on an unusable input or a failed
GitHub read (nothing is counted then), else 0.

### Schedule (launchd, Pro)

`infra/launchagents/com.balizero.localci-merger.plist`: `StartInterval` 600 s, `RunAtLoad`, no `KeepAlive` (a one-shot,
superscar #7), `PATH` set explicitly (a tick without `gh` on PATH is an `error` line). It runs
`~/.nuzantara-cron/localci_merger_tick.sh` (a copy of `scripts/localci/localci_merger_tick.sh`), which drops every inherited `GIT_*`
variable, fetches `origin/main` into the merger's mirror under the wrapper's OWN ref `refs/merger/wrapper` (never `refs/merger/base`,
which is `merger.py`'s `fetch_base` alone: since F2 it is the authority once phase F has pushed, and a force-fetch by the wrapper would
rewind it before the divergence guard looks; a mirror that predates the ref falls back to `refs/merger/base` read-only; a failed fetch
is not fatal: the tick journals its own), resolves ONE
sha and runs `merger.py` and `hosted_compare.py` as committed at it — never a working-tree copy. A failure before Python starts
(no git, no mirror) writes no journal line; it is in `~/logs/localci-merger.err.log`, and the report's `longest_silence` shows
the gap. Every exit writes the organ heartbeat `~/.organism/last_seen/pro.localci_merger.json` (`ok`, `error`, `warning` or `disabled`;
registry id `pro.localci_merger`) by running `scripts/lib/heartbeat.sh` in its own process (its CLI mode, never `source`: the
library cannot change the wrapper's options, traps or exit status). That library too comes from the mirror at the tick's
sha, never from a working checkout: each tick refreshes `<state-dir>/heartbeat.sh`, and an exit before the extraction (the
kill switch, missing configuration) runs the copy the last tick extracted — on a host that never ticked there is none, which
is said on stderr and the organ reads stale. Each run extracts into its own temporary file and publishes it with `mv` only
when it is not empty; an empty library is treated as absent (it would run as a silent no-op). `MERGER_HEARTBEAT_LIB`
overrides the path (tests).
`LOCALCI_MERGER_ENABLED=false` in the plist's environment stops the ticks without uninstalling; its `disabled` heartbeat is
not an unhealthy status — the healer's `EXEMPT_STATUSES` holds it and the sentinel does not page on it — because a kill
switch is an operator's act, not a failure. The wrapper passes `--code-sha=<resolved sha>` when the extracted `merger.py`
knows the flag (an older main, or a stale mirror after a failed fetch, still ticks), so every journal line names the code
that wrote it. The live copy is a declared HOME-fork pair (`infra/home-fork/declared-pairs.json`):
`scripts/lint_home_fork.py --check` on Pro names a drift from the repo. The wrapper refuses with `exit 2`, before any git,
an unset `MERGER_PYTHON` or `MERGER_NODE` or an interpreter that is not executable, and it tests them explicitly, never with
`${VAR:?}`: under macOS `/bin/bash` 3.2 an expansion error reaches the `EXIT` trap with status 0, the script
exits 0 and the heartbeat would say `ok` (measured; the wrapper test keeps it red). Replace the live copy atomically (copy
beside it, then `mv`): bash reads a running script as it goes.

Capacity (measured 2026-10-07). The runner executes its checks one after another — `cmd_run` walks the planned names in a
single loop and no check starts before the previous one has its receipt — so a tick costs the sum of its checks. With
phase A's contained contexts on main, ticks took 883 s, 886 s and 1097 s (#7978, #7979, #7943) against a `StartInterval` of
600 s. launchd never overlaps a job with itself, so the cadence is one PR per tick + 600 s (about 25 minutes), and it grows
with phase B's service contexts. `StartInterval` stays 600 (a shorter one buys nothing while a tick outlasts it); running
checks in parallel is phase B's runner work. The heartbeat is written when a tick ends, so two heartbeats are up to
tick + 600 s apart: the organ's `expected_hb_seconds` is 3600, not 1800. A `running` heartbeat at tick start was not chosen
— the sentinel's `running` branch has no staleness downgrade (`scripts/nuzantara-sentinel.py`), so a hung tick would read
healthy for ever.

The merger runs the BASE runner with its OWN coordinator venv, `~/.nuzantara-pilots/local-ci/merger/venv` (the plist's
`MERGER_PYTHON`): the runner fingerprints the coordinator's `pip freeze` into every receipt, and a shared venv that another job
updates mid-run turns every PASS receipt STALE at `status` time (measured on the backend-rag venv, 2026-10-07). Install
(operator of Pro, user `nuzantara`):

    python3.11 -m venv ~/.nuzantara-pilots/local-ci/merger/venv
    ~/.nuzantara-pilots/local-ci/merger/venv/bin/pip install --quiet pytest==9.0.3 PyYAML==6.0.3
    mkdir -p ~/.nuzantara-cron ~/logs
    cp scripts/localci/localci_merger_tick.sh ~/.nuzantara-cron/.localci_merger_tick.sh.new
    mv -f ~/.nuzantara-cron/.localci_merger_tick.sh.new ~/.nuzantara-cron/localci_merger_tick.sh
    cmp -s scripts/localci/localci_merger_tick.sh ~/.nuzantara-cron/localci_merger_tick.sh && echo "live copy == repo"
    sed -e "s#__HOME__#$HOME#g" infra/launchagents/com.balizero.localci-merger.plist \
        > ~/Library/LaunchAgents/com.balizero.localci-merger.plist
    launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.localci-merger.plist
    tail -3 ~/.nuzantara-pilots/local-ci/merger/decisions.jsonl   # green≠working: read the journal, not the exit code
    cat ~/.organism/last_seen/pro.localci_merger.json

### Retention and the host floor (B6)

`docs/specs/localci-sovereign-2026-10-07.md`, phase B step B6. The wrapper's order on every tick:

1. it reads the host's free GB (`df -Pk /System/Volumes/Data`, whole GB, floored); a `df` that gives no number starts no
   run and the heartbeat is `warning` (`host free space unreadable (df -Pk <path>): no run started`);
2. `merger.py tick … --host-free-gb=N --min-host-free-gb=60`: under the floor the tick journals
   `{"kind":"skipped","why":"host_below_floor","free_gb":N,"floor_gb":60}` before the lease and starts no run;
3. `merger.py prune --state-dir <state> --fstrim`, after the tick and never before it, whether the tick ran, skipped or failed;
4. the heartbeat: `error` when the tick failed, `warning` with the number (`host_below_floor free_gb=N floor_gb=60: no run
   started`) under the floor or when the prune failed, `ok` otherwise. The wrapper exits with the tick's code.

A mirror sha older than B6 still ticks: `prune.py` and `runner.py` are extracted only when the sha has them, and the floor
flags go only to a `merger.py` that knows them (under the floor, a merger that cannot journal the skip is not started).

    python scripts/localci/merger.py prune [--state-dir ~/.nuzantara-pilots/local-ci/merger] [--docker docker] \
        [--dry-run] [--fstrim] [--colima colima]

The prune (`scripts/localci/prune.py`) touches only `localci-deps:*` images and `<state>/runs`:

- **Deps images.** Removed by `docker image rm <tag>` (never `-f`, never `prune -a`), recipe by recipe
  (`MAX_IMAGES_PER_RECIPE` 2, beside the 48 h window), two slots held by distinct images: the newest holds one; the other
  goes to the image the most `state/plan.json` of the last 48 h name by tag or id (distinct plans, not mentions; a tie goes to
  the youngest reference, then the newest image); an image no plan of the window names takes no slot and goes; beyond the
  slots an image stays only when the run holding the lease names it — a run of the last 48 h without a `status.json` yet —
  and the prune never runs beside a tick (it takes the lease). B8 retired the 6 h clock grace (`IN_FLIGHT_GRACE_H`): on Pro
  every image was named under 3 h ago, so the cap never bit and the VM filled (2026-10-08T15:27Z).
  The recipe is the `org.nuzantara.localci.recipe` label the deps build now sets, else the check whose job named the tag in
  any plan; an image whose recipe nothing records is its own recipe and stays. The never-list — `localci-candidate:*`,
  `localci-deps-base:*` and every `service_images` stand-in value of the BASE matrix (`contexts_matrix.yaml`, extracted by the
  wrapper at the tick's sha; read, never hardcoded: today `postgres:15`, `redis:7`) — is never in a removal set and each of
  its images present is journalled under `kept` with its rule. While a plan or the matrix cannot be read, no image is removed;
  a half-written plan still names the tags its text names. Created is read to the nanosecond and as a UTC instant, honouring a
  trailing `Z` or `±HH:MM`/`±HHMM` offset (Pro's docker prints local time with `+08:00`; B8a) — no offset reads as UTC, anything
  else as undated; images built at the same instant rank together.
- **VM floor (B8, amended).** After the cap, the builder prune and the run trim, while the VM's free GB
  (`vm_free_gb.after`) is under `VM_MIN_FREE_GB` (15; `LOCALCI_VM_MIN_FREE_GB` overrides it, a value that is not a finite
  number ≥ 0 reads as 15), images go fewest plan references of the last 48 h first, ties to the oldest, the builder pruned
  and the free GB re-read after each, until the floor is met or nothing removable is left. Under the floor the newest of a
  recipe is NOT protected: only the never-list and what the lease run names are. A 60 GiB VM holds at most ONE image per recipe
  plus the scratch of one build when three recipes are live; the floor, not the slots, is the rule that holds (Pro,
  2026-10-08T17:26Z). Each removal's rule reads `vm floor: VM free X GB < 15 GB after the cap; N plan(s) of the last 48 h name it, built
  H h ago` (`undated` without a readable `Created`); the line carries
  `vm_floor {floor_gb, removed, met}`, or `skipped` on a dry run, an unreadable input, or an unmeasured VM.
- **Builder cache.** Every prune that is not a dry run runs `docker builder prune -af --max-used-space 4GB` (the flag is chosen per B13 below) on the current
  builder, the one the runner's `docker build` uses (`colima` on Pro; `localci-isolated` is not the runner's), after the
  cap's removals and again after each floor removal. `-a` because the entries are the layers of images that exist, which are
  not dangling: without it the prune removed 0 B of a 16.93 GB cache (17:23Z); with it, after three removals, 20.98 GB (17:27Z). The budget is `BUILDER_CACHE_GB` (4;
  `LOCALCI_BUILDER_CACHE_GB` overrides it); the line journals `builder_prune {rc, keep_storage_gb, flag, freed_gb, deprecated_flag, du_gb, tail}` of the last call,
  `runs` the number of calls, and `cache_gb {before, after}` read from `docker system df` before the first and after the last.
  It read `--filter until=24h` until B8: on Pro at 17:20Z that kept 16.9 GB of cache with 0.5 GB reclaimable.
- **Builder cache, B13.** buildx 0.34 turned `--keep-storage` into `--reserved-space` (a floor to keep, not a cap): on Pro
  (buildx v0.34.1, docker client 29.5.2, server 29.2.1; 2026-10-10 ~03:10Z) `builder prune -af --keep-storage 4GB` printed the
  deprecation notice, `Total: 0B` and exited 0 against a 22.83 GB cache (`docker buildx du`: Shared 18.96 GB, Private 3.867 GB,
  Reclaimable 22.03 GB); the journal read `rc 0, cache 22.83 -> 22.83`, and at 01:14Z every heavy leg was
  `host_disk_below_floor 11.8GB<12GB`. Now the flag is read ONCE per prune run from `docker builder prune --help` (30 s bound):
  `--max-used-space` when listed, `--keep-storage` only when the help lists that and not the new one (old buildx), and
  `--max-used-space` when the help cannot be read (rc then decides). The prune fails on the entity that failed, not on a size: the
  line carries `deprecated_flag: true`, and `failed` names `builder_prune`, when a line of a call's output (stdout+stderr) names
  the flag we passed and says it is `deprecated` or `has been changed to` (the Pro line: `Flag --keep-storage has been deprecated,
  keep-storage flag has been changed to reserved-space`); another flag's warning, or the word on a line that does not name ours,
  is not this. `freed_gb` is the sum of buildx's `Total:` over the run's calls (`null` only when no call printed one), and
  `du_gb {shared, private, reclaimable, total}` is read from `docker buildx du` (120 s bound) after the last call (no `Shared:`
  line means no `Private:` either, and private is the total; unreadable is `null`). Both are measurements, never a failure.
  `freed_gb` is buildx's record-size sum, not disk bytes: live on Pro (2026-10-10 ~04:05Z) one `-af --max-used-space 4GB` printed
  `Total: 12.53GB` while the VM data disk went from 39G used to 37G used. BuildKit also leaves more than the cap reclaimable
  (cache 22.83 GB before, 10.29 GB after, against 4 GB), so no size-based "over budget" rule is sound and none is applied.
  An old daemon (BuildKit before 0.17) ignores `max-used-space`, and `-a` then empties the cache: a rebuild cost, never a wrong verdict.
- **Run directories.** Age from the timestamp in the run's name; an undated directory is never touched. Under 7 days a
  run is whole. From 7 days `logs/` and every `call-graph.json` and `higher-order-call-graph.json` go. From 30 days only
  `status.json`, `hosted_compare.json` and `state/plan.json` stay. `decisions.jsonl` is never touched, and a `runs/` that is a
  symlink is never trimmed.
- **fstrim.** With `--fstrim`, every real prune (not a dry run, not a lease skip) ends with `colima ssh -- sudo fstrim -av`,
  whether or not an image went (B7): a run's own containers and layers free blocks inside the VM every tick, and they stay
  allocated in the host's sparse disk until trimmed (2026-10-08T15:16Z: 11.4 GiB back with no removal, in 2 s). The line
  always carries `fstrim` and `host_free_gb.after_fstrim`; a failed trim is `failed: ["fstrim"]`, exit 1.
- **Online discard (B8b).** Before the trim, the same real prune reads the VM's mount table (`colima ssh -- cat /proc/mounts`)
  and, if the data disk (`VM_DOCKER_MOUNT`, `/mnt/lima-colima`, `/dev/vdb1`, the sparse host file `~/.colima/_lima/_disks/colima/datadisk`)
  lacks the `discard` option, runs `sudo mount -o remount,discard /mnt/lima-colima` and reads it again; mount options do not
  survive a VM restart: the prune at the end of each tick puts it back for the next tick, so the first tick after a VM restart
  runs without it. Why: a sampler on Pro (2026-10-09, every 20 s) saw the datadisk's host allocation
  climb to 54.0 GiB inside a tick while the VM used 36.6-40 GiB, 14-17 GiB of freed blocks returning only at the end-of-tick trim,
  and the host's free space fall to 104.0 GiB (100.3 GiB by another session's read) against the owner's floor of 100 GB. The mount point is matched as the
  field of a `/proc/mounts` line and `discard` as one of its comma-split options (`nodiscard` is off; a longer path is another
  mount). The line carries `vm_discard {before, after, remounted, rc, error}` (`null` = unreadable; an error or a timeout is
  journalled, never raised, and stops nothing); `failed: ["vm_discard"]` only when a remount was attempted and `after` is not
  true. `LOCALCI_VM_DISCARD=0` skips it (`vm_discard {skipped}`, no colima call); a dry run has no `vm_discard`.

One journal line per prune (its shape; the numbers below are illustrative, not measured); `--dry-run` writes
`would_remove` instead of `removed` and removes nothing:

    {"ts": "…Z", "host": "…", "code_sha": "…", "kind": "prune", "dry_run": false,
     "vm_free_gb": {"before": 1.2, "after": 15.8},
     "host_free_gb": {"before": 77.1, "after": 77.4, "after_fstrim": 87.0},
     "images": {"removed": [{"tag": "localci-deps:…", "gb": 5.35, "rule": "recipe e2e-tests already keeps 2 images (newest localci-deps:…): beyond the cap, named by 1 plan(s), the youngest 2.1 h ago"},
                            {"tag": "localci-deps:…", "gb": 4.64, "rule": "vm floor: VM free 11.2 GB < 15 GB after the cap; 1 plan(s) of the last 48 h name it, built 20.3 h ago"}],
                "kept": [{"tag": "localci-deps:…", "rule": "the newest image of recipe e2e-tests"},
                         {"tag": "localci-deps:…", "rule": "slot 2 of 2 of recipe e2e-tests: named by 4 plan(s) of the last 48 h, the youngest 1.4 h ago"},
                         {"tag": "postgres:15", "rule": "service stand-in of the BASE matrix: never pruned"}], "errors": []},
     "builder_prune": {"rc": 0, "keep_storage_gb": 4.0, "flag": "max-used-space", "freed_gb": 3.9, "deprecated_flag": false, "du_gb": {"shared": 0.68, "private": 3.3, "reclaimable": 3.5, "total": 3.98}, "cache_gb": {"before": 21.8, "after": 4.0}, "runs": 2, "tail": "Total: 3.9GB"},
     "vm_floor": {"floor_gb": 15.0, "removed": 1, "met": true},
     "runs": {"trimmed_7d": ["pr8060-…-20261001T063148Z"], "trimmed_30d": [], "freed_gb": 0.63},
     "fstrim": {"rc": 0, "tail": "/: 9.6 GiB (10307921510 bytes) trimmed"}, "failed": []}

The prune takes the tick's lease: while a tick holds it, the line is `{"kind": "prune", "skipped": "lease", "holder": …}` and
nothing is removed. `failed` lists `images` (an image still in use, an unreadable plan), `builder_prune` or `fstrim` when
one of them failed; the prune then exits 1 and the organ says `warning`. A VM the probe cannot measure reads `null`. The prune
reaches Pro when the wrapper's live copy is replaced with the commands of the block above (`cp` beside it, `mv`, `cmp -s`).

### Disk floor organ (B6, Pro)

`pro.disk_floor` (`scripts/ops/pro_disk_floor_tick.sh`, `infra/launchagents/com.nuzantara.disk-floor.plist`) reads
`df -Pk /System/Volumes/Data` every 30 minutes (`StartInterval` 1800, `RunAtLoad`, no `KeepAlive`) and writes
`~/.organism/last_seen/pro.disk_floor.json`: `ok` above 100 GB free, `warning` from 60 to 100, and under 60 the mandate's
`failed`, written as `error` (the word `scripts/lib/heartbeat.sh` canonicalises it to and the sentinel and the healer read).
The note is `free_gb=N on /System/Volumes/Data (ok > 100, failed < 60)`; when the organ is not `ok` it adds
`; biggest: ~/<dir> X.YGB, …` for the three biggest top-level directories of `~` (the walk took 94 s on Pro, so it runs only
when the organ pages). The limits are compared in MB, so 100.5 GB is `ok`. Wrong node or `PRO_DISK_FLOOR_ENABLED=false`:
`disabled`; a previous run still alive: `warning` (`skipped: previous run alive (pid N), free space not read`). Registry `expected_hb_seconds` 3600,
silence is a `warning`, recovery `launchctl kickstart`. Arming (operator of Pro, user `nuzantara`, from a checkout at
`origin/main`):

    mkdir -p ~/.nuzantara-cron ~/logs/pro-disk_floor
    cp scripts/ops/pro_disk_floor_tick.sh ~/.nuzantara-cron/.pro_disk_floor_tick.sh.new
    mv -f ~/.nuzantara-cron/.pro_disk_floor_tick.sh.new ~/.nuzantara-cron/pro_disk_floor_tick.sh
    cmp -s scripts/ops/pro_disk_floor_tick.sh ~/.nuzantara-cron/pro_disk_floor_tick.sh && echo "live copy == repo"
    cp infra/launchagents/com.nuzantara.disk-floor.plist ~/Library/LaunchAgents/com.nuzantara.disk-floor.plist
    launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.disk-floor.plist
    cat ~/.organism/last_seen/pro.disk_floor.json   # RunAtLoad: the first heartbeat lands at bootstrap

## Phase E flip (prepared; the operator applies)

    bash scripts/localci/hand_report.sh   # step 1, on Pro, immediately before --apply: the report (about 6 minutes)
    # step 2, the plan (read it); step 3, the apply with the plan's digest
    python scripts/localci/phase_e_flip.py [--repo Bali-Zero/Teman2] [--branch main] [--report <report.json>] [--state-dir <dir>] [--key-pub <deploy_key.pub>]
    python scripts/localci/phase_e_flip.py --apply --confirm <digest> --quiescent   # operator[gui], after READY and the key
    python scripts/localci/phase_e_flip.py --rollback <pre-flip-*.json> [--apply --confirm <digest> --quiescent]

Step 1 recomputes `report.json`, which nothing regenerates on a schedule (since F2 the tick judges READY in memory and writes
no report). `hand_report.sh` runs the merger's own `merger.py report` the way the tick runs it: the code read from the mirror's
ref (`refs/merger/wrapper`, else `refs/merger/base`, resolved once), the same files extracted beside it — the report's
stale-verdict judge loads `runner.py`, and without it every hosted-stale row would stay FALSE_GREEN and READY could never be
true; a test keeps the list equal to the tick's, and a file missing at that commit fails the run — the merger's venv with `-I`,
launchd's environment (HOME and PATH only) and the tick's git isolation. `merger report: refusing — <reason>` writes nothing:
read the reason — a tick appending to the journal at that moment is transient, run it again; an unreadable journal line needs
repair first.

Phase E of `docs/specs/localci-sovereign-2026-10-07.md` leaves the merger's deploy key as the only writer of `main`. Without
`--apply` the script only reads (GETs through `gh api`): the classic protection of the branch with its required set and each
check's source, the `merge-queue-main` ruleset, the ruleset that forbids deletion and force-push, the write deploy keys and the
report; it prints the two writes of the flip with their exact bodies, what still blocks them, and a plan digest. The flip is
(1) `PUT` the `merge-queue-main` ruleset with `merge_queue` replaced by `update` (`update_allows_fetch_and_merge` false) and the
DeployKey bypass (`actor_id` null, `always`) as its only actor, then (2) `DELETE` the classic protection — sent only when
GitHub's answer to (1) shows the ruleset enforced, with that one rule and that one actor, on the same conditions, AND a fresh
read still shows it so, the guard, the one merger key and the scope (a write that does not take, or a guard or key that changed
during the run, stops it before the DELETE: exit 3). The classic protection must go because it requires a pull request and the status
checks, and classic protection exempts no deploy key: while it stands the merger's fast-forward push is refused (`push_refused`,
a sticky halt). Between the two writes nobody can move `main`.
Deletion and force-push stay forbidden by the `Copilot review for default branch` ruleset (`deletion`, `non_fast_forward`, no
bypass actor), which the flip requires.

`--apply` writes nothing unless all of these hold, read fresh: `--confirm` equals the digest of a plan of this very state (the
classic protection, the `merge-queue-main` ruleset, each guard ruleset whole, the write keys by id, date and fingerprint, and the
writes — any of them that moved since the plan changes the digest); the report says `phase_e_ready: true`,
is of the same repository, was generated within the last 2 hours less 5 minutes — the plan and `--apply` judge the same age,
and the per-write re-read keeps the full 2 hours — (and not more than 5 minutes ahead; either refusal says to run the report
now, step 1), and its own window shows
READY (`compared_merges` >= 50, `compared_days` >= 14, and `FALSE_GREEN` the integer 0 at every level the merger sums for READY —
`counts`, `context_counts`, `recorded_context_false_green`; a contradiction is refused, a malformed report is refused, never
raised); exactly one deploy key with write exists (the DeployKey bypass covers every write key of the repository; every page of
the list is read) and it is the merger's: its `SHA256:` fingerprint — the form `ssh-keygen -lf` and GitHub's key page print —
equals that of `--key-pub` (default `~/.nuzantara-pilots/local-ci/merger/deploy_key.pub`; only the fingerprint is printed,
never the key or its title); the live state is pre-flip (classic protection present, a `merge_queue` rule in the
ruleset); the ruleset covers the branch and nothing wider; and the deletion/force-push guard exists — an active ruleset that
GitHub lists with an empty `bypass_actors` (an omitted field is unknown, not none) and whose exclusions name no pattern. Flipped
is read by meaning: no classic protection, the ruleset enforced, covering the branch, one `update` rule that allows no
fetch-and-merge, the DeployKey its one actor, always. An already flipped branch writes nothing and is re-judged — a second write
key, a foreign or unidentifiable key (an unreadable `--key-pub`), a lost guard or a ruleset widened beyond the branch is exit 1
(`already flipped, but: …`); anything neither pre-flip nor flipped is `drifted` and refused. The classic protection reads as
absent only on GitHub's `Branch not protected` 404; any other error, 404s included, refuses. A classic setting this tool cannot restore exactly (push restrictions, signed commits, dismissal restrictions or bypass
allowances, which GitHub lists only when configured) is refused, never dropped. The
pre-flip state is saved first (`<state-dir>/pre-flip-<UTC>.json`, directory 0700, file 0600, created exclusively — no save,
no write); both resources are re-read after the writes and anything but `flipped` is exit 3 with the rollback command.
`--rollback` restores the classic protection first and the ruleset second, under its own plan digest: the ruleset write is sent
only when GitHub's answer to the first shows the classic protection as saved (never the merge queue back without the checks),
and both are re-read after — anything but the saved state is exit 3 (the checks compared as a set: GitHub may list them in
another order). The classic body is sent with `checks` only (GitHub refuses `contexts` beside it) and
`restrictions: null`. A check whose source is
"any" is read as `app_id` null and saved as `-1` (an omitted `app_id` would pin the app that last reported it). Exit codes:
0 plan printed, applied or nothing to do; 1 refused; 2 bad arguments; 3 a write failed or did not take.

**Write discipline — RULED 2026-10-10** (LOCALCI-SOVEREIGN lead, a spec decision after three review reds of one class — a
write sent against a state nobody re-read — on draft #8191; the cause is specified here, not patched).
- *Q, quiescence.* A precondition of `--apply`, declared by the operator who runs it with `--quiescent`: phase E's apply is an
  operator[gui] gesture, and no session, peer or cron writes rulesets or branch protection of the repository during the run.
  The script states it in every plan and refuses `--apply` without the declaration; it does not try to enforce it.
- *W1, before every write.* Immediately before EVERY write, the first included, a fresh read is compared with the state the
  plan confirmed (the digest's state), advanced by the writes already made — component by component: the classic protection
  (its checks as a set), the `merge-queue-main` ruleset (the target by meaning), the guard rulesets whole, the write keys, the
  ruleset's scope, and every rule GitHub applies to the branch (`rules/branches/<branch>`, inherited ones included). On a
  difference the run stops before writing, makes no write, and names what "changed since plan" (exit 1 when nothing was
  sent yet, exit 3 after).
- *W5, after every write.* GitHub's answer must show the write took, and a fresh read after it is compared with the state the
  write intended; a read that differs or fails is read again (3 reads, 2 s apart) before it counts. On a mismatch the run
  stops, writes nothing further, and prints the rollback state file.
- *W1 for the report.* Before every write of the flip the report is read again and must still prove READY (fresh, the
  branch's, the whole journal, FALSE_GREEN 0); otherwise the run stops before that write. The plan and `--apply` want a
  report at least 5 minutes inside its 2-hour age limit, so it does not expire during a normal run (seconds) and leave the
  branch frozen between the two writes; the re-read before each write keeps the full limit. This narrows the window, it does
  not close it: a READY that turns false between that read and the write is the same residual as GitHub's, and quiescence
  covers it.
- *W2, nothing else blocks the key.* Rules layer, and a bypass exempts only its own ruleset: beside `merge-queue-main`'s rule,
  every rule GitHub applies to the branch must be `deletion`, `non_fast_forward` or `copilot_code_review`; any other refuses
  the plan. The guard counts only when `rules/branches` shows its `deletion` and `non_fast_forward` on the branch.
- *W3, READY is the branch's and the whole journal's.* The report's `base` is the branch and it carries `since: null` (a
  missing key is refused); its numbers are finite JSON numbers (`Infinity` and `NaN` are refused at parse).
- *W4, a write sent is a write owned.* Once a write has been sent, any failure — a refused write, a mismatch, an unexpected
  error, Ctrl-C — is exit 3 with the state file and the full rollback command, never a traceback that reads as "refused".
  When a rollback stops after its classic write, the branch is frozen, not open (classic protection and the key-only
  ruleset): run the plan again, or restore the state file's `ruleset` by hand. Before any write, every failure — Ctrl-C included — is exit 1
  ("REFUSED", nothing written), never a traceback; a failure after a write was sent is exit 3 even when it happens outside
  the write loop (the tool's own output failing, say).
- *The state file is sealed.* The flip saves it 0600 with a sha256 of its canonical JSON; `--rollback` refuses, before any
  plan, a file whose checksum does not match its content — one edited since — and then checks the shape of both bodies.
- *Residual, accepted and documented.* GitHub's REST API offers no compare-and-swap (no `If-Match`) for rulesets or branch
  protection, so a sub-second window remains between W1's read and the write it guards. Quiescence takes concurrent writers
  out of scope, and W5 detects a lost race after the fact. A review finding of that class beyond W1/W5 is out of scope by
  this ruling.

**Arming order (phase F's checklist).** (1) Phase D READY: recompute the report on Pro (`bash scripts/localci/hand_report.sh`
from an `origin/main` checkout, the phase E section's step 1) and read `phase_e_ready`. (2) operator[secret]: the merger's deploy key generated on Pro
(`~/.nuzantara-pilots/local-ci/merger/deploy_key`, 0600, never printed) and registered on the repository with write — the only
write deploy key; its `.pub` is what `--key-pub` reads. (3) operator[gui]: the plan, read; then `--apply --confirm <digest> --quiescent` (with no session, peer or cron writing GitHub settings) from
a checkout at `origin/main`, on a host whose `gh` is the owner's (the ruleset and protection writes need admin), with the
merger's `.pub` and a report.json under 2 hours old copied beside it if that host is not Pro (`--key-pub`, `--report`); keep the
printed state file. (4) Only then `LOCALCI_MERGER_PHASE_F=1` in the tick's
environment: before (3) the first push is refused and halts. A session runs the plan only and never `--apply`.

## Tests

`PYTHONPATH=<worktree> python -m pytest scripts/localci/tests -q` (real temporary git repos; the hypothesis state machine
is skipped when hypothesis is absent).

`python3 scripts/localci/tests/mutants/merger_mutants.py` replays the merger's mutation sweep: each single-rule mutant of
`merger.py` or `localci_merger_tick.sh` is applied to a temporary copy of `scripts/localci` and `scripts/lib` (the checkout
is never touched) and must turn its test file red: KILLED means pytest ran and a test failed (exit 1); exit 0 is SURVIVED and
any other exit (nothing collected, a collection error) is ERROR, never a kill. Inherited `PYTEST_*` options are dropped, so a
caller's `-k` cannot deselect the guilt. A rule whose text no longer occurs exactly once is STALE, not skipped. Exit 0 only
when every test-file set passes unmutated and every mutant is killed; `--only NAME` and `--list` narrow it.
`python3 scripts/localci/tests/mutants/phase_e_mutants.py` is the same sweep, harness and verdicts for `phase_e_flip.py`
against `test_phase_e_flip.py`, in its own table. That suite's fake `gh` refuses any PUT body GitHub's own published request
schema refuses: the two schemas are vendored in `scripts/localci/tests/fixtures/github_rest_put_schemas.json` (from
github/rest-api-description at a pinned commit, with the source file's and the extract's sha256; MIT, its notice beside the
file), read by the tests only. One deviation is declared and pinned by a test: the schema lists the deprecated `contexts` as
required in `required_status_checks`, while GitHub refuses `contexts` beside `checks`.

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
