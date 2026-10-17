# LOCALCI — the two CodeQL contexts decided on Pro (spec, 2026-10-11)

Mission LOCALCI-SOVEREIGN. Today `CodeQL Analysis (python)` and `CodeQL Analysis (javascript)` are `mapping: blocked`
(`scripts/localci/contexts_matrix.yaml`), which caps the local verdict at SUBSET_PASS. This spec turns them into executed
contexts with coverage `full`, which is the only admissible coverage: the READY criterion allows at most one partial context
per compared merge, and E2E holds it.

**Why `full` is honest.** In this matrix `partial` names a subset of the WORK left undone: E2E is partial because its six secrets are `""` and the tests
that need them do not run. An environment difference is a `parity_gaps` line (arch, runner, a GitHub-side outage); every other `full` context runs arm64
in Colima against hosted x64. What the hosted job can fail on, read from codeql-action v4.38.2 and the GitHub docs, falls in four classes. (1) The CLI
commands: reproduced with the same CLI, pinned by the sentinel and checked again at run time. (2) The analyze action's post-processing of the SARIF,
which runs even with `upload: never`: JSON that does not parse, a missing `runs` array or a run without a `results` array throws; the schema is NOT
validated for CodeQL's own SARIF (`areAllRunsProducedByCodeQL`), so a schema check here would be stricter than hosted, a FALSE_RED. (3) The PR lane's
upload (`upload: always`, whose check run `hosted_compare` reads for the head): the SARIF API rejects a file over its documented limits (10 MB gzip; 20 runs;
25,000 results and rules per run; 100 extensions; 10,000 thread-flow and 1,000 result locations; 20 tags a rule), which the code determines and
`codeql_sarif_check.py` reproduces on the interpreted SARIF. The maxima are rejection limits ("If any of these objects exceeds its maximum value the SARIF file is
rejected"); the display truncation ("only the top 5,000 ...") applies below them. The gzip limit is checked on a bound of the payload hosted would send: the
compact JSON text (`JSON.stringify`), gzip level 6 (`zlib.gzipSync`'s default), plus 32 bytes for every result the action would fingerprint that lacks a
`primaryLocationLineHash` and 256 bytes for every run lacking `automationDetails` (0 on the CLI's real SARIF, which carries both), against **10,000,000**,
the smaller reading of "10 MB": FALSE_GREEN 0 is the hard constraint. (4) A GitHub-side processing error outside those limits, a transient API error, the
status-poll timeout (which continues, not fails) and a hosted runner loss: infrastructure, each a `parity_gaps` line.

Also not reproduced, and named so: the docs table's "Alert Limit 1,000,000" (repository state, not a property of one SARIF), and a failed hosted
"Self-test ring-gating override" step (`security.yml`, `pip install pyyaml` from the network), which makes `changes.result` non-success so hosted runs both languages
(local runs a leg by BASE's flags). One precision: with `upload: never`, a run without `results` does not throw on hosted (`countResultsInSarif` runs only in
`uploadPostProcessedFiles`); local judges as the PR lane does, so it is stricter than the merge_group twin, never greener.

## Preconditions (met)

- **Licence.** #8241 (merged 2026-10-11T00:27Z) released the repo under Apache-2.0, and GitHub detects `spdx_id: Apache-2.0`.
  The GitHub CodeQL Terms allow CodeQL databases for automated analysis/CI on an Open Source Codebase hosted on GitHub.com.
- **Parity, measured on Pro** (probe 2026-10-11T00:44–00:49Z, commit `4be6f5e20352`, CLI 2.27.2 linux-arm64 bundle sha256
  `c1779ce6335606ef86fce4aae0db2ac4d7da869527d6a67bf055d9135695473c`, sandbox `--network none --user 65534:65534 --memory 12g`,
  `--threads=4 --ram=10240`):

  |                      | python   | javascript |
  | -------------------- | -------- | ---------- |
  | results              | 2499     | 186        |
  | rules                | 172      | 200        |
  | wall                 | 170 s    | 72 s       |
  | cgroup `memory.peak` | 8.63 GiB | 7.05 GiB   |
  - Results and rule counts are the same as hosted's (schedule run 38092166320).
  - Every result matched on (ruleId, uri, region, message), with 0 hosted-only and 0 local-only, after two normalisations of
    raw CLI SARIF that the server applies: uri percent-decoding, and implicit endLine/startColumn.
  - File coverage was identical: py 3478/3478, js 1556/1556 TS.

## The hosted job (`.github/workflows/security.yml`, job `codeql`)

- `if: !cancelled()`, `timeout-minutes: 30`, and a matrix over `language: [python, javascript]`.
- `RUN_THIS_LANGUAGE`:
  - It is `(event != pull_request && event != merge_group) || needs.changes.result != 'success' || (python &&
needs.changes.outputs.run_codeql_python != 'false') || (javascript && needs.changes.outputs.run_codeql_js != 'false')`.
  - The flags are produced by the BASE_SHA-extracted `scripts/ci/security_gate_flags.py` on the changed files.
- `Initialize CodeQL`, `Autobuild` and `Perform CodeQL Analysis` each carry `if: env.RUN_THIS_LANGUAGE == 'true'`.
- A language whose flag is `false` runs the job with the three steps skipped. Its conclusion is **success**, not skipped.
- The job turns red only on a CLI or action error, a timeout, or (on the PR lane) a SARIF upload failure. **It never fails on
  findings.** No required check reads the SARIF or the alerts.

## What to build

1. **The bundle image.** A recipe key on the context's local deps, e.g. `codeql: {version, url, sha256}`. It builds the
   deps image with the bundle extracted to `/opt/codeql` and `/opt/codeql` on PATH, and asserts `codeql version` = the pin.
   - The tarball never lands in a layer (`ADD --checksum` into a build stage, or a bind mount), and it is never read whole
     into memory.
   - The recipe digest covers the pin, so a bump builds a new image, and the prune keeps the newest per recipe as today.
2. **Plan-time flags.** The plan runs BASE `security_gate_flags.py` (already in the trusted classifier set) on the plan's
   changed files, after the trusted change map, the way the hosted `changes` job does.
   - It seals `run_codeql_python` / `run_codeql_js` as the `needs.changes` outputs the leg's expressions read.
   - The manual override `vars.MERGEOS_RING_GATING_DISABLED` (the `Manual override` step of `security.yml`'s `changes` job) is read live at plan with
     the operator's gh and evaluated by BASE's own `scripts/ci/ring_gating_override.sh`, run and not re-implemented. It is resolved the way hosted
     resolves `vars.X`: the repository's variables list (`GET repos/{repo}/actions/variables`, `per_page=100`, paginated) first, then, only when
     `GET repos/{repo}` reports `owner.type == "Organization"`, the organization variables visible to it (`actions/organization-variables`); a
     repository variable of that name wins, a name in neither list is unset. Any non-200 status (a 404 included), an unparsable body, a missing
     `variables` array or a `total_count` that disagrees with the rows collected is a read error, and so is a BASE `codeql` or `changes` job that names
     an `environment:` (environment variables are invisible to this read): all fail open. When it is active, hosted skips the classify steps and every
     flag defaults `true`: both flags are `true` here. A read that fails is the same fail-open. The result is sealed in the check spec as
     `ring_gating_override: {read: ok|error, active: bool}`. (tests.yml's `changes` job honours the same variable and the local change map does not: a
     skipped tests.yml context then compares as "skipped here; hosted ran", partial. Partial, and a hosted red is journalled FALSE_GREEN
     (`hosted_compare.classify`), never counted as a full AGREE. Ledgered by the lead, out of this lane.)
   - A classifier error makes `needs.changes.result` something other than `success`, so the leg runs (fail-open, as hosted).
3. **The leg.** One job per language, run in expression mode in the bundle image:
   - network `none`, memory `12g`, no git index;
   - the BASE `timeout-minutes: 30`;
   - `RUN_THIS_LANGUAGE` evaluated from the merge_group shape and the sealed flags;
   - the three steps gated by their own `if:`.

   `Initialize CodeQL` and `Perform CodeQL Analysis` run a BASE-trusted `scripts/localci/codeql_leg.sh <init|analyze> <lang>`,
   which runs exactly the probe's commands:
   - `database init --force-overwrite --db-cluster <D> --source-root=/w --calculate-language-specific-baseline
--sublanguage-file-coverage --extractor-include-aliases --language=<L> --codescanning-config=<augmented config>`;
   - `database trace-command --index-traceless-dbs` (javascript adds the trap-cache `-O` options);
   - `database finalize --finalize-dataset --threads=4 --ram=10240`;
   - `database run-queries --ram=10240 --threads=4 --expect-discarded-cache --min-disk-free=1024`;
   - `database interpret-results` to sarif-latest, with category `/language:<L>`.

   The augmented config is BASE `.github/codeql-config.yml` with `queries` replaced by the workflow's
   `security-extended,security-and-quality` input, exactly as the action composes it.

   `Autobuild` is not applicable: the action runs no command for these languages.

   An all-skipped leg is **PASS**, with the steps NOT_APPLICABLE, so that it compares as AGREE against hosted's success. It
   must never be a record NOT_APPLICABLE skip: `hosted_compare` would call that "skipped here; hosted ran" = partial. `skip_is_pass` is tight: every
   NOT_APPLICABLE step is a matrix `not_applicable` or an `if: ... -> false` the driver evaluated, at least one is the latter, and a step BASE gates
   with an `if:` that was skipped any other way makes the leg ERROR.

   The leg is hardened where it takes inputs: its test seams (`CODEQL_BIN`, `CODEQL_SOURCE_ROOT`, `LOCALCI_CODEQL_WORK`, `CODEQL_BASE_CONFIG`) in a
   composed step env BLOCK the plan; the action refs are `uses_pin`ned (BASE's `uses` differing BLOCKS, and a candidate whose workflow and matrix pins disagree, drop a pin, or move one to a non-`@<40 hex>` ref BLOCKS: a bump carries its matrix pin); at init the leg compares `codeql version
--format=terse` with `CODEQL_PIN` (the matrix passes the recipe's one literal; the deps image build asserts the same pin, `runner.py` `DEPS_CODEQL`)
   and gives no verdict, by dying of a signal, on a difference; a `queries:` block the config rewriter cannot read as text is no verdict too.

4. **Verdict.** PASS when every command exits 0 within the budget and the SARIF is one hosted takes, and FAIL when one exits non-zero or hosted would
   reject the SARIF (not JSON, no `runs`, a run without `results`, or over a documented upload limit: `codeql_sarif_check.py`, a BASE-laid trusted
   file). A timeout, OOM-kill or a local CLI other than the pin is no verdict, as for every leg, and so is the checker's own crash (a
   `RecursionError`, `MemoryError` or `UnicodeEncodeError`: exit 70, which the leg turns into its no-verdict signal; exit 1 means "hosted would reject"). Findings and SARIF counts never change the verdict;
   they go in the receipt as data (results per language).
5. **Version sentinel.** At plan time, read the newest hosted CodeQL analysis per language on `refs/heads/main`
   (`GET /repos/{repo}/code-scanning/analyses?ref=refs/heads/main`, category `/language:<L>`) with the operator's gh, as the
   harness-floor reader does.
   - If `tool.version` differs from the pin, or the read fails, the context is **BLOCKED**, never green. Hosted picks its
     CLI per run by feature flag (2.27.1 → 2.27.2 around 2026-10-09).
   - It is also **BLOCKED** when the newest analysis is older than 7 days, or when the newest completed `security.yml` run of the repository's own
     main has its `CodeQL Analysis (<language>)` job concluded anything but `success` (hosted main is red on this leg, which covers a hosted CLI
     upgrade that fails before it uploads). "Own main" is `head_repository.full_name == repo`, `head_branch == main` and an event that runs
     security.yml on main: its `on:` block lists `push` for `develop` only, so `schedule` and `workflow_dispatch` (a fork's PR branch named main is
     neither). Both are read at plan with the operator's gh; a read failure is CANNOT-VERIFY, as above.
   - A pin bump is a matrix PR that re-runs the parity probe.
6. **BASE judges.** `.github/codeql-config.yml`, `codeql_leg.sh` and `codeql_sarif_check.py` are `trusted_files`. A candidate that changes the
   config gets its green BLOCKED by the existing changed-judge rule, because hosted would analyse with the candidate's
   config.
7. **The matrix.** The two contexts become `mapping: executed`, `coverage: full`, and `trusted_base_required: true`.
   - `summary.blocked` goes to 0 and `never_claim_parity_for` goes to `[]`. The suite checks both.
   - Add these `parity_gaps` lines:
     - **Version.** The hosted CLI version is set per run by GitHub feature flags. Local pins the bundle and is BLOCKED when
       the newest hosted analysis reports another version. The flag can move between that read and the queue run.
     - **Flags.** The action's CLI flags are transcribed from the 2026-10-10 hosted logs and the action source, so a
       feature-flag change to them is not seen. `interpret-results` is reconstructed from `src/codeql.ts`; it adds metadata
       only.
     - **Architecture.** The linux-arm64 bundle is used here and linux64 hosted. A crash, OOM or timeout depends on arch and
       resources (hosted runs 4 threads with `--ram=14575`; here `--ram=10240` under 12g).
     - **Shape.** The merge_group shape with upload `never`. What the PR lane's upload can fail on and the code determines is reproduced on the
       interpreted SARIF (see "Why `full` is honest"). Not reproduced, since GitHub's side decides them: a processing error outside the documented
       limits, a transient API error, the status-poll timeout, a hosted runner loss, the "Alert Limit 1,000,000" (repository state), a failed hosted
       "Self-test ring-gating override" step (both languages then run on hosted). The gzip size is the compact text at level 6 plus a bound of what the action adds
       (fingerprints and automation details, 0 on the CLI's real SARIF); locally it is comparable to the uploaded one (measured: python 556,089 B here,
       431,655 B hosted). A PR-lane diff-informed result set may be narrower than the local one, which only changes data, never the verdict.
   - Also fix the stale "Colima 4 CPU / 8 GiB" parity_gaps line: the VM has been 8 CPU / 16 GiB since 2026-10-10.

## Not in scope

- SARIF upload to code scanning. Hosted still uploads while the workflows exist, so the Security tab does not regress now.
  Uploading locally is for the day the hosted workflows go: storage use, via `codeql github upload-results` or the API.
- Parallel legs. Legs stay serialized: CodeQL peaks at 8.6 GiB and cannot share the VM with a 12g sandbox.

## Bites

The consumer is the merger tick on Pro, through the first candidate decided after merge whose BASE contains this change (the
runner runs from the candidate's BASE worktree). The observation, in that run:

- `ctx.codeql-python` and `ctx.codeql-javascript` have receipts, with a PASS verdict or an honest BLOCKED (version sentinel);
- the results count per language is recorded;
- the merger's line shows `non_executed=[]` instead of the two CodeQL contexts;
- the hosted compare rows for both are AGREE;
- the plan's check spec carries `ring_gating_override: {read: ok, ...}` (a first live plan on Pro that reads `read: error` means the repository, organization or
  environment variable read failed and both languages ran).
