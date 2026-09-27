# codex-spalla PII guard — the specification four REWORK rounds were missing (G1-G8)

Status: PROPOSED 2026-09-27. Spec only, no code in this PR. Every state claim is `as_of` `2026-09-27T02:35Z`
unless its line says otherwise (measured 02:28Z-02:40Z). Line numbers are measured at `origin/main`
`a6fcae5afe` ("main") and at PR #7483's head `b79840b54f` ("v4").

**Why this file exists.** `.claude/scripts/codex-spalla.sh` puts `git diff` bodies into a prompt for the
Codex CLI (OpenAI cloud). On 2026-09-26 (dispatch transcript stamped 20:58:01Z) it forwarded a PII-removal
PR's 959 deleted lines of a client `plan.jsonl` in cleartext, a Builder Contract rule-4 breach. The guard
lane then built four times: v1 #7466 (MERGED 2026-09-26T23:07:43Z at a gear-1 floor, 13 minutes after its
gate wrote REWORK-BUILD), v2 #7470 (CLOSED 2026-09-27T00:07:47Z), v3 #7475 (CLOSED 01:23:30Z), v4 #7483
(OPEN, auto-merge off). Every fresh gate said REWORK-BUILD, mostly on causes an earlier gate had named.
Builder Contract rule 1: three reds for one cause suspend the lane, and a wrong fix-of-a-fix means the
surface is under-specified. Ground truth: gate reports 7466, 7470, 7475, 7483 and 7476 (S5), plus the four
builder reports.

**Live on main today, which runs v1 only.**

- `scripts/tests/test_codex_spalla.py` fails 10 of 11 (stub seats on PATH, 0 stub calls), unseen by PR CI.
- The redactor runs without names required (main `scripts/lib/spalla_redact.sh:74`): with `DATABASE_URL`
  unset, CRM names ship in cleartext for any path the refusal misses.
- The refusal list is 7 hand-typed globs (main lib `:34-38`), renames under-match (main wrapper `:250`), and
  no `umask` is set: of 56 files in `~/logs/codex-spalla` on M5, 1 is 0644 (0 bytes, 2026-09-27T02:25:00Z).

A _forwarder_ puts repository or diff content into a prompt for an external seat of any vendor (rule 4 binds
Claude too). The _entrypoint_ is the one guard every forwarder calls (G6).

## Why four rounds failed

B = gate blocker, P = partial or should-fix carried forward, ✓ = cured, · = not raised.

| Rule                            | v1 #7466 | v2 #7470 | v3 #7475 | v4 #7483 | Rounds blocked |
| ------------------------------- | -------- | -------- | -------- | -------- | -------------- |
| G1 refusal list source, renames | B ×2     | P        | P        | P        | 1              |
| G2 fail-closed semantics        | ·        | B        | B        | B        | 3              |
| G3 names on the live path       | B        | B        | B        | ✓        | 3              |
| G4 path robustness              | P        | B        | P        | P        | 1              |
| G5 log hygiene                  | B        | ✓        | ✓        | ✓        | 1              |
| G6 sibling egress               | P        | P        | B        | P        | 1              |
| G7 CI wiring, registry, Bites   | B        | P        | B        | B        | 3              |
| G8 artefact truth               | P        | B        | B        | B        | 3              |
| Blockers numbered by the gate   | 5        | 4        | 5        | 4        | 18             |

- **The acceptance list was the last gate's list.** Each round cured the named instance and the next gate
  found the next edge; G4 appears in all four rounds. The v2 gate wrote G2's cure as "missing, fails to
  parse or comes back empty", and v3 and v4 did two of the three.
- **Gear avoidance.** v4 dropped its PR workflow because it raised the floor from 2 to 3. Under S5 (#7489,
  armed at as_of) these files floor at 3 anyway.
- **Prose outran code.** 6 of the 18 blockers are false or stale sentences in artefacts that stay.
- **The target moved after arming.** v3's first blocker was "none of the lead's add-ons is in the PR".

## G1 — The refusal list comes from one named source

**Gap.** The refused paths have never had a source. v1 hand-typed 7 globs. v2-v4 joined a hand-typed static
half (14 globs, v4 `spalla_redact.sh:66-80`, which it calls "still a hand-typed list" at `:63`) to a live
parse of `PII_PATH_FRAGMENTS` (`scripts/async_review_supervisor.py:40-46`, 5 fragments).

**Evidence.** gate-7466 blocker 2 lists `docs/crm/` (6 tracked files, 1 csv) and 4 `.gitignore` PII shapes
as missed; gate-7470 finds 5 more latent gaps. gate-7466 blocker 3: a rename out of `research/crm/` was not
refused, because `--name-only` lists only the destination. Tracked at as_of: `research/crm/` 7 files,
`docs/crm/` 6, `research/compliance/` 23, `research/wa-copilot/` 2, `scripts/wa_corpus/` 14 (all `.py`).
`.gitignore` carries 22 PII-commented patterns that no guard reads.

**Rule.**

1. One tracked source holds the refusal globs: a new key `egress_refusal_paths` in
   `agent-library/config/redaction-rules.yaml`, the canonical redactor's config, in gitignore syntax with no
   `!` negation. The entrypoint's code and tests hold no path literal from it. `PII_PATH_FRAGMENTS` stays the
   second source, with the supervisor's substring semantics. The refused set is the union.
2. Initial content: the 22 `.gitignore` PII patterns (main lines 372, 373, 381-384, 392, 650, 696, 715, 716,
   721, 934-936, 938, 939, 944, 945, 948, 949, 951), plus four directories `.gitignore` cannot hold without
   blocking research capture: `research/crm/`, `research/compliance/`, `research/wa-copilot/`, `docs/crm/`.
   `scripts/wa_corpus/` stays out: it is code, not data, and G3 redacts any literal in it.
3. Matching follows gitignore semantics, not bash globbing: a basename pattern matches at any depth, a
   leading or middle `/` anchors, a trailing `/` covers the directory, `**` crosses directories.
4. The policy is read at the merge-base and in the working tree, and the union applies, so a diff that
   deletes a source entry cannot disarm its own review.
5. Committed and uncommitted path lists come from `--no-renames -z`, untracked ones from
   `ls-files -z --others --exclude-standard`. A rename contributes both of its paths.
6. Over-refusal is accepted: the fragments match 129 (`/crm/`), 668 (`/fixtures/`) and 134 (`/kb/`) tracked
   files. The logged override (G2) exists for them.

**Tests** (`scripts/tests/test_egress_guard.py`: real repos, fake seats on PATH).

- guilt `test_guilt_every_source_entry_refuses_a_synthetic_path` (one path per entry, generated from both
  sources at test time); `test_guilt_rename_out_of_and_into_a_refused_dir_is_refused` (git reports `R100`);
  `test_guilt_a_diff_deleting_its_own_refusal_entry_is_still_refused`;
  `test_guilt_gitignore_pii_pattern_missing_from_source_fails` (expectations derived from `.gitignore`
  comments at test time, v3's method, which found the missing `compliance_report_*.pdf`).
- innocence `test_innocence_clean_code_diff_prompt_is_byte_identical` (against the pre-#7466 wrapper, the
  gates' case i); `test_innocence_prefix_siblings_are_not_refused` (`docs/crm.md`, `research/crmx/a.md`,
  `scripts/wa_corpus/pilot.py`).

## G2 — Fail closed, under one rc contract

**Gap.** A guard that could not establish its policy has answered "no hit". v2 swallowed every load error;
v3 and v4 accept a found-but-EMPTY fragment tuple (v4 `spalla_redact.sh:136-140` prints nothing, `:155`
marks it `ok`, `:174-178` then miss). The redactor CLI returns 1 for every failure (main
`_redact_pii.py:594-601`), so no caller can tell missing names from a broken redactor from a short input.

**Evidence.** gate-7470 blocker 3; gate-7475 blocker 2 and gate-7483 blocker 1, case b3: both
`PII_PATH_FRAGMENTS = ()` and `: tuple[str, ...] = ()` gave rc 0 and one exec; the real supervisor gave rc 7.
gate-7470 case S12: one small untracked file gave rc 8 via `min_remaining_chars` = 100 (main
`_redact_pii.py:81`). v4 `:104` claims a broken source "is reported once per process", yet the call runs in
`$(…)` at `:167`, and gate-7475 case b1 saw the message once per path.

**Rule.** The entrypoint returns exactly one of these.

| rc  | Class    | Cause                                                                                                                             | The caller must                                                                  | Override                                           |
| --- | -------- | --------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- | -------------------------------------------------- |
| 0   | SEND     | sanitized payload on stdout, possibly empty                                                                                       | send stdout and nothing else                                                     | not needed                                         |
| 10  | REFUSED  | a path hits G1                                                                                                                    | send nothing; print paths only; log `guard=refused`; wrapper exits 7             | `--allow-pii-paths`, logged; G3 and G4 still apply |
| 11  | DEGRADED | the name list (G3), the refusal source or the fragments are missing, unreadable, unparseable or EMPTY, in either assignment shape | send nothing; print the remedy; log `guard=degraded`; wrapper exits 8            | none                                               |
| 12  | ERROR    | redactor exception, non-idempotence, git error, timeout                                                                           | send nothing; print the class, never payload; log `guard=error`; wrapper exits 8 | none                                               |

- Callers allowlist rc 0. Any other rc, including 1, 2, 126, 127 and death by signal, counts as 12.
- Empty input, and input shorter than `min_remaining_chars`, is SEND here: that length gate protects
  NotebookLM usefulness, not PII (`scripts/dynamic_workflow.py:1649-1657` pads around it for that reason).
- The policy sources and the name list load once per dispatch, in one process.

**Tests.**

- guilt `test_guilt_empty_fragments_in_both_assignment_shapes_is_degraded`;
  `test_guilt_missing_unreadable_or_empty_refusal_source_is_degraded`;
  `test_guilt_any_nonzero_guard_rc_sends_nothing` (a stub entrypoint returns 1, 2, 12 and 127 and dies by
  SIGKILL; the fake codex is never called); `test_guilt_override_cannot_bypass_degraded_or_error`.
- innocence `test_innocence_short_benign_untracked_file_is_sent` (case S12);
  `test_innocence_empty_sections_are_not_an_error`.
- `test_policy_and_names_load_once_per_dispatch`: a 3-path diff reads each source once, calls fake `psql` once.

## G3 — CRM names are redacted on the live path, or nothing is sent

**Gap.** v1 redacts static shapes only: the CLI calls `Redactor.load_default()` with its default
`require_dynamic_names=False` (main `_redact_pii.py:458-459`, `:594`), and with `DATABASE_URL` and `PGURL`
unset pass4 is skipped with a warning (`:355-358`). v2-v4 made strictness an opt-in flag, so a caller that
forgets it keeps the weak mode. At v4, FOCUS and the untracked path list are never redacted, and FOCUS also
reaches telemetry and the filename slug (v4 wrapper `:33-37`, `:418`, `:441`).

**Evidence.** gate-7466 blocker 5: a fixture name crossed the "redacted" path while the email on the same
line was redacted. gate-7475 add-on: rc 8 told the operator nothing about loading names. gate-7470 blocker 1:
a v2 fixture, repeated 8 times in this PUBLIC repo, was a PROD client name (exact-match count 1 in
`clients`, measured by gate-7475).

**Rule.**

1. The entrypoint has one mode, names required. No flag or env var weakens it. Other redactor callers keep
   their current default.
2. Names unavailable (env unset, DB unreachable, 0 names in both tables) gives rc 11: nothing is sent and no
   transcript is written (G5). The remedy names the `scripts/pg.sh` recipe and the
   `com.nuzantara.fly-pg-tunnel` LaunchAgent, never a credential. `.claude/commands/codex-second-opinion.md`
   documents exits 7 and 8. Without the name list spalla is unusable, and that cost is accepted.
3. Every prompt byte outside the fixed template passes the entrypoint: committed diff, uncommitted diff,
   untracked bodies, untracked path list and FOCUS. Telemetry and the slug use the redacted FOCUS.
4. Test fixtures are invented names proven absent from PROD before first use (`clients` and `companies`,
   exact and ILIKE, count 0, stated as counts in the PR body). No fixture is copied from another repo file.

**Tests.**

- guilt `test_guilt_no_database_url_sends_nothing`; `test_guilt_zero_names_loaded_sends_nothing`;
  `test_guilt_db_error_sends_nothing` (fake `psql`, rc 11, fake codex never called);
  `test_guilt_fixture_name_in_focus_untracked_path_and_body_is_redacted` (placeholder present, name absent
  in fake-codex stdin, telemetry and the transcript filename).
- innocence `test_innocence_names_loaded_text_without_names_is_unchanged`.

## G4 — Paths are parsed, never guessed

**Gap.** An awk state machine over diff headers decides which lines are suppressed (v4
`spalla_redact.sh:181-221`), and each header oddity git produces has broken it once: a space plus git's
trailing TAB; a `"`, TAB or `\` in the name, quoted by git even with `core.quotePath=false`; `export.CSV`
(case-sensitive match at `:214`); `color.ui=always` in user config. Only DELETED lines of data files are
suppressed, so added and context lines of a data file outside the refusal list reach the redactor raw.

**Evidence.** gate-7466 S6; gate-7470 blocker 2; gate-7475 cases d2, e3, e4; gate-7483 cases d2/d3/d4 (rc 0,
raw body 5 of 5 in the prompt), e3 (raw 5, markers 0), e5 (`q"x.csv`, raw 5). Main tracks 3 paths with a
space, 0 with `"`, `\`, TAB or non-ASCII, 337 `.jsonl`/`.csv`/`.xlsx` and 3 `.tsv` files, 0 mixed-case
data extensions: latent defects.

**Rule.**

1. Every path list is NUL-separated (`-z`) end to end. No path is re-parsed out of diff text.
2. A data file (`.jsonl`, `.csv`, `.tsv`, `.xlsx`, extension matched case-insensitively) never has a body
   line embedded, whether deleted, added or context. Its path (through G3) and its `--numstat` counts are
   embedded instead. The decision uses the `-z` list and is applied by pathspec exclusion, never by reading
   diff headers.
3. Every body capture runs `git -c core.quotePath=false diff --no-color --no-ext-diff --no-textconv`, so no
   user or system git config changes what is captured.
4. G1 applies to the same `-z` list, so a quoted, tabbed or newline-bearing path is compared as spelled.

**Tests.**

- guilt `test_guilt_special_char_paths_under_a_refused_dir_are_refused` (`"`, TAB, `\`, newline, non-ASCII,
  committed on a branch); `test_guilt_data_file_bodies_are_withheld_for_every_spelling` (`export.CSV`,
  `q"x.csv`, `data file.tsv`; added, deleted and context lines; raw fixture count 0);
  `test_guilt_hostile_git_config_cannot_leak_a_body` (`GIT_CONFIG_GLOBAL` with `color.ui=always`, a
  `diff.external` and a textconv driver).
- innocence `test_innocence_space_path_code_file_is_sent_redacted_not_refused`;
  `test_innocence_withheld_data_file_keeps_path_and_counts`.

## G5 — What the logs may hold, and with which modes

**Gap.** v1 writes every artefact under the caller's umask, 022 on M5; v2-v4 added `umask 077` and chmod,
but main runs v1. The transcript is created before the refusal check, so a refused run leaves an empty
file. The BLOCKER copy lands in `$REPO_ROOT/docs/codex-reviews/`, inside a git worktree, kept out of the
public repo by `.gitignore:902` alone.

**Evidence.** gate-7466 blocker 4: 55 of 55 files were group- or world-readable. M5 today: see the header;
`~/logs/codex-spalla.jsonl` is 0600. `~/logs/tri-llm-review` is 0755 on M5 and on Pro, 0 files on each.

**Rule.**

1. Log dirs are 0700 and their files 0600, whatever the caller's umask. Looser pre-existing modes are
   tightened on every run. Temp files are 0600 and removed on exit, signals included.
2. A transcript exists only when a send happens. REFUSED, DEGRADED and ERROR write one telemetry line only.
3. A transcript holds the prompt exactly as sent, the seat's reply and wrapper diagnostics, never
   pre-redaction text. Telemetry holds counts, rc, guard class, redacted FOCUS, the transcript path, no body.
4. The BLOCKER copy lives in the 0700 log dir, outside the repository tree.
5. These rules bind every forwarder's log dir (G6).

**Tests.**

- guilt `test_guilt_umask_000_and_022_still_yield_0600_files_in_0700_dirs`;
  `test_guilt_preexisting_loose_modes_are_tightened`;
  `test_guilt_refused_degraded_or_error_run_creates_no_transcript`.
- innocence `test_innocence_transcript_prompt_equals_what_the_seat_received` (byte compare, fake-codex stdin).

## G6 — One entrypoint for every forwarder

**Gap.** Each round found a forwarder the previous sweep missed: v1's `*.sh`-only grep missed
`scripts/codex_tri_llm_review.py`, and S5 v2 missed `infra/workflows/second-army.js`. v4 disabled the
tri-LLM CLI (exit 3, v4 `:874-892`), but `scripts/review_gate_run.sh` counts rc ≤ 3 as "reviewed" (`:163`,
comment at `:150`), and the tracked `infra/launchagents/com.nuzantara.review-gate.plist` would re-arm it.

**Evidence.** gate-7466 Siblings; gate-7475 blocker 4; gate-7476 blocker 2. Tri-LLM on main puts raw
`gh pr diff`/`git diff` output (`:178`, `:211`) into `build_prompt` (`:231`, `:811`), then into `codex exec`
argv (`:403-407`) and `kimi -p` argv (`:605-610`). second-army.js has its refuter lane run
`git diff origin/main...${FROZEN_REF}` (`:544`) and hand it to a seat door (`:87-120`), with 0 `redact`.
Pro over ssh: `com.nuzantara.review-gate` is not loaded; its plist is parked as `.disabled-20260927-leak`
(ctime 2026-09-26T23:56:21Z, `StartInterval` 600); `~/logs/review-gate.out.log` has 6182 lines, all
"no open agent/\* PRs", last written 2026-09-26T23:55:05Z.

**Rule.**

1. There is exactly one entrypoint, an executable CLI callable from bash, Python and a JS-driven shell lane.
   Recommended: `scripts/egress_guard.py` beside the redactor, since one Python process parses `-z`, loads
   policy and names once (G2) and fits the registry's census shape (G7). `scripts/lib/spalla_redact.sh`
   shrinks to a thin exec shim or is deleted.
2. Every forwarder takes its payload from the entrypoint's stdout and sends nothing else. No seat-bound
   prompt tells a seat or a lane to run `git diff` itself.
3. IN, each routed or deleted in v5: `.claude/scripts/codex-spalla.sh`; the tri-LLM script with
   `scripts/review_gate_run.sh` and the tracked plist (recommended: delete all three in one PR, as 6182
   recorded runs dispatched nothing); the second-army.js refuter lane.
4. OUT, each reason written into the census exemptions: the trigger hook (sends nothing); `scripts/codex/*`
   (name lists only, the seat reads the repo: a declared residual); `scripts/lint_paid_llm_entity.py` (CI,
   secrets redactor); `infra/claude-hooks/session_budget.py` (local file, no seat);
   `scripts/agent-library-evolver-run.sh`, `scripts/_entailment_check.py` and
   `apps/backend-rag/sandbox/egress_proxy.py` (non-diff content).
5. Named follow-up outside v5: `scripts/dynamic_workflow.py:455` and `:1655` call `load_default()` without
   names required and read "unchanged by redaction" as clean. It is the G3 defect in another caller.
6. The entrypoint, `redaction-rules.yaml` and `scripts/async_review_supervisor.py` join S5's hot-zone list
   and its sync test in the PR that creates or first reads them. Measured with #7489's lint, those three
   floor at 1 today and `.claude/scripts/codex-spalla.sh` at 3 (`path`).

**Tests** (precedent: the codex seat census, `scripts/tests/test_codex_seat_lib.py:216` and `:239`).

- guilt `test_guilt_census_flags_a_forwarder_that_bypasses_the_entrypoint` (synthetic `.sh`, `.py` and
  `.js` files that capture a diff and call a seat door);
  `test_guilt_second_army_refuter_prompt_carries_no_raw_git_diff`.
- innocence `test_innocence_census_ignores_prose_and_name_only_callers`.
- verdict `test_every_forwarder_calls_the_one_entrypoint` over `git ls-files`, each exemption with a reason.

## G7 — Tests run on every pull_request, the guard is censused, Bites is post-merge

**Gap.** The spalla tests run only in `scripts-tests-sweep.yml`: `schedule` plus `workflow_dispatch`,
report-only, `continue-on-error: true`. No workflow runs `test_codex_spalla` for a PR. The guard registry
has no entry for the wrapper, the lib or the redactor, so the checker's 0 violations are vacuous. Every
round's `Bites:` cited pre-merge test counts.

**Evidence.** The 10-of-11 red on main; gate-7466, -7475 and -7483; v4 dropping its workflow to keep its
floor at 2. Branch protection requires "Every guard proves guilt AND innocence" (`guard-conformance.yml:91`),
which runs on `pull_request` and `merge_group` behind an in-job path sentinel (`:110-127`) and on `push` to
main behind a paths filter. The registry's `check_bridge` shape (`source`, `census` `ast-def-prefix`,
`test_file`, `guards` with `guilt` and `innocence`) fits a Python entrypoint: v4's "category mismatch" ends.

**Rule.**

1. A step in that required job runs `pytest -q` on `scripts/tests/test_egress_guard.py` and
   `scripts/tests/test_codex_spalla.py`, plus any surviving `.sh` corpus. Its sentinel regex and `push:`
   paths list every guard file: entrypoint, shim, wrapper, `_redact_pii.py`, `redaction-rules.yaml`,
   supervisor, in-scope forwarders, tests. The nightly sweep does not count as CI for this guard.
2. Registry: a new surface `egress_guard` in `infra/guard-conformance/registry.json`, `check_bridge` shape,
   whose `guards` map each `guard_*` function to this spec's guilt and innocence test names, wired by one
   `check_bridge(...)` line in `check_guard_conformance.py::main()`. C1-C4 then fail on an unregistered
   guard, a missing guilt or innocence test, a phantom test name or an unarmed test file.
3. A sync test asserts the sentinel regex matches every registered guard path (precedent
   `scripts/tests/test_hotzone_lists_sync.py`, which lands with #7489).
4. `Bites:` on each v5 PR is an observation made after merge, with its command:
   `gh run list --workflow guard-conformance.yml --branch main --event push --limit 1` shows the merge
   commit's run, whose log has the new step green. On M5 from origin/main with `DATABASE_URL` unset the
   wrapper exits 8, `tail -1 ~/logs/codex-spalla.jsonl` shows `guard=degraded`, and no new transcript
   exists. With names loaded it exits 0, the newest transcript is `-rw-------`, and a planted fixture name
   shows as its placeholder.

**Tests.**

- guilt `test_guilt_sentinel_missing_a_guard_path_fails`.
- innocence `test_innocence_unrelated_path_does_not_trigger_the_sentinel` (`docs/CLAUDE.md`).
- The checker's existing C1-C4 run on the new surface.

## G8 — Artefacts say what is true, in UTC

**Gap.** Six of the 18 blockers were false or stale sentences in artefacts that stay. W140 on main is still
v1's text, and v4's rewrite fixed some sentences while introducing others.

**Evidence.** W140 on main (`docs/scars/cicatrix-scars.md:1780-1819`) claims the two contaminated
transcripts were quarantined (`:1787`), zero additional client-name hits (`:1793`), guards on every prompt
an external seat receives (`:1797`), deleted content that never exists in the prompt (`:1801`), and
transcripts that stay 0600 (`:1808`). Main's lib says deleted data lines are never embedded (`:7`),
falsified by gate-7466 S6. v4's W140 labels WITA times as `Z`, calls Pro "unverified" and the 16 files
untraced; v4's lib calls the drift check future work (`:63`) though `:77` says it exists, and its "reported
once per process" (`:104`) is false (`:167`).

**Rule.** The v5 W140 states the following, and only this.

1. Incident: the dispatch transcript is stamped 2026-09-26T20:58:01Z; the PII-removal diff's 959 deleted
   lines of a client `plan.jsonl` went to OpenAI in cleartext.
2. Window: client-name egress is confirmed from 2026-09-18, not as one event. 14 of the 16 batch files carry
   at least 1 PROD multi-word name, 8 distinct by hash, all 8 also present in tracked files. One of the 8 is
   a `clients.full_name`, found in the transcript stamped 2026-09-18T06:47:33Z (gate-7475).
3. Quarantine, counts only: `~/.agent/pii-quarantine` is 0700, 18 files, 0 with group or other bits. Group A,
   the incident pair, is 2 files moved 2026-09-26T21:41:41Z. Group B is 16 files moved 2026-09-26T22:01:07Z
   by the first builder session's sweep (per the lead; that session died before reporting), with mtimes
   2026-09-05T04:00:18Z to 2026-09-26T15:54:17Z.
4. Pro's review gate, per the G6 evidence: loaded with `StartInterval` 600 until parked at
   2026-09-26T23:56:21Z, 0 dispatches recorded across 6182 log lines.
5. ANTIBODY clauses describe merged behaviour only, each naming the test that pins it. No clause says
   "every" or "never" without a test that enumerates the class.
6. Code comments meet the same bar, and "future work" appears only with a ledger row. No PR text, test or
   scar locates pre-existing PII elsewhere in the repository (gate-7475 should-fix, carried by gate-7483).
7. Timestamps are UTC, from `stat -f %c` and `TZ=UTC date -r`. Every cross-PR state carries `as_of`, per S4
   of `docs/specs/2026-09-27-evidence-pack-fixed-point.md`.

**Tests** (gate probes on the final head).

- guilt `probe_g8_no_local_time_labelled_z` returns 0 on the scar file:
  `grep -cE '2026-09-27T0(5:41:41|6:01:07)Z' docs/scars/cicatrix-scars.md`;
  `probe_g8_every_antibody_test_exists`: each test the ANTIBODY names resolves to a `def`, as C3 checks.
- innocence `probe_g8_utc_pair_present`: `2026-09-26T21:41:41Z` and `2026-09-26T22:01:07Z` each appear.

## Migration

**State.** Main runs v1, with the live gaps in the header. #7483 is OPEN, auto-merge off: close it as
superseded, reusing its tri-LLM refusal test and rc-8 remedy text. #7489 (S5 v3) is OPEN and armed; once it
merges, any PR touching its 7 paths floors at 3, source `path`.

**Order.** Serial, each from a fresh origin/main after the previous one merges.

1. **v5a, entrypoint and policy (G1, G2, G3, G4, G7).** `scripts/egress_guard.py`, the
   `egress_refusal_paths` key, the registry surface and checker line, the `guard-conformance.yml` step and
   sentinel, and the S5 additions of G6.6 with their sync-test entries. The wrapper is not switched, so
   runtime is unchanged. It starts after #7489 merges, since both edit `scripts/evidence_pack_lint.py` and
   `.github/workflows/hot-zone-pr-gate.yml`. The only v5 PR expected above ~400 net lines; its pack says so.
2. **v5b, spalla on the entrypoint (G3.3, G5, G6.2).** The wrapper sends only entrypoint stdout; transcripts,
   telemetry and the BLOCKER copy follow G5; the lib becomes a shim or goes; `codex-second-opinion.md`
   documents exits 7 and 8.
3. **v5c, siblings (G6).** The tri-LLM trio is deleted or routed, the second-army refuter is routed, and the
   census lands with its exemptions.
4. **v5d, truth (G8).** W140 is rewritten against the merged code of v5a-v5c, with the comment sweep.

**Containment.** Until v5b merges, main's wrapper forwards CRM names for any non-refused path when
`DATABASE_URL` is unset. Whether spalla dispatches pause until then is the lead's call; this spec changes
no runtime.

**Gear.** v5a, v5b and v5c each touch at least one S5 path, so each floors at 3 (`path`) and needs
`brief.yml`, `pack.yml` and a fresh gate verdict before arming. v5d floors at 1 on its path, measured on
`docs/scars/cicatrix-scars.md` with main's lint and with #7489's, size term permitting.

**Residuals, not closed by v5.** `codex exec --sandbox read-only` runs in the repo root and is invited to
grep, so a seat can read tracked PII itself; the pii-deep-audit lanes own that data, and `scripts/codex/*`
actors are the same class. Fragment over-refusal (G1.6) can breed override fatigue; watch the share of
`allow_pii_paths=true` telemetry lines.

**Done, per rule** (observed on origin/main after merge).

| Rule | Done when                                                                                       |
| ---- | ----------------------------------------------------------------------------------------------- |
| G1   | G1 tests green in the required job; the entrypoint holds 0 path literals from the source        |
| G2   | the `= ()` case exits 8 with 0 fake-codex calls in the `push` run                               |
| G3   | an M5 dispatch with `DATABASE_URL` unset exits 8, logs `guard=degraded`, writes no transcript   |
| G4   | the five special-name cases and three data spellings pass with raw fixture count 0              |
| G5   | `find ~/logs/codex-spalla -perm +077` returns 0 after one real and one refused dispatch         |
| G6   | census verdict green; the tri-LLM trio gone or routed; the refuter prompt holds no `git diff`   |
| G7   | the `push` run on the merge commit ran the step; the checker reports the `egress_guard` surface |
| G8   | the three G8 probes pass on the v5d head                                                        |
