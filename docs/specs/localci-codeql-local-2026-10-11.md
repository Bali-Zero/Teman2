# LOCALCI — the two CodeQL contexts decided on Pro (spec, 2026-10-11)

Mission LOCALCI-SOVEREIGN. Today `CodeQL Analysis (python)` and `CodeQL Analysis (javascript)` are `mapping: blocked`
(`scripts/localci/contexts_matrix.yaml`), which caps the local verdict at SUBSET_PASS. This spec turns them into executed
contexts with coverage `full`, which is the only admissible coverage: the READY criterion allows at most one partial context
per compared merge, and E2E holds it.

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
   must never be a record NOT_APPLICABLE skip: `hosted_compare` would call that "skipped here; hosted ran" = partial.

4. **Verdict.** PASS when every command exits 0 within the budget, and FAIL when one exits non-zero. A timeout or OOM-kill
   is no verdict, as for every leg. Findings and SARIF counts never change the verdict; they go in the receipt as data
   (results per language).
5. **Version sentinel.** At plan time, read the newest hosted CodeQL analysis per language on `refs/heads/main`
   (`GET /repos/{repo}/code-scanning/analyses?ref=refs/heads/main`, category `/language:<L>`) with the operator's gh, as the
   harness-floor reader does.
   - If `tool.version` differs from the pin, or the read fails, the context is **BLOCKED**, never green. Hosted picks its
     CLI per run by feature flag (2.27.1 → 2.27.2 around 2026-10-09).
   - A pin bump is a matrix PR that re-runs the parity probe.
6. **BASE judges.** `.github/codeql-config.yml` and `codeql_leg.sh` are `trusted_files`. A candidate that changes the
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
     - **Shape.** The merge_group shape with upload `never`: the PR lane's SARIF upload, which can fail the hosted job, is
       not reproduced. A PR-lane diff-informed result set may be narrower than the local one, which only changes data,
       never the verdict.
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
- the hosted compare rows for both are AGREE.
