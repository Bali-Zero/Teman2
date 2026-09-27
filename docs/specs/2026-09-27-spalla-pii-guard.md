# codex-spalla PII guard — the specification four REWORK rounds were missing (G1-G8)

Status: PROPOSED 2026-09-27, reworked after gate-7513. Spec only, no code in this PR. State claims are
`as_of` `2026-09-27T02:35Z` unless marked; G8 probe results and slice floors were measured at `03:45Z`.
Line numbers are at `origin/main` `a6fcae5afe` ("main") and PR #7483's head `b79840b54f` ("v4"); v2 is
#7470's head `52684c2c7c`, v3 is #7475's head `5d5d452a76`.

**Why this file exists.** `.claude/scripts/codex-spalla.sh` puts `git diff` bodies into a Codex CLI prompt
(OpenAI cloud). On 2026-09-26 (transcript stamped 20:58:01Z) it forwarded a PII-removal PR's 959 deleted lines
of a client `plan.jsonl` in cleartext, a rule-4 breach. The guard lane then built four times: v1 #7466
(MERGED 2026-09-26T23:07:43Z at a gear-1 floor, 13 minutes after its gate wrote REWORK-BUILD), v2 #7470
(CLOSED 00:07:47Z), v3 #7475 (CLOSED 01:23:30Z), v4 #7483 (OPEN, auto-merge off). Every gate said
REWORK-BUILD, mostly on causes an earlier gate had named: per rule 1, the surface is under-specified. Ground
truth: gate reports 7466, 7470, 7475, 7483, 7476 (S5) and 7513.

**Live on main today, which runs v1 only.**

- `scripts/tests/test_codex_spalla.py` fails 10 of 11, unseen by PR CI: the wrapper sources the lib from
  `$REPO_ROOT` (`:113`) and the test's fake repo does not carry it.
- The redactor runs without names required (main `scripts/lib/spalla_redact.sh:74`): with `DATABASE_URL`
  unset, CRM names ship in cleartext for any path the refusal misses.
- The refusal list is 7 hand-typed globs (main lib `:34-38`), renames under-match (main wrapper `:250`), and
  no `umask` is set: of 56 files in `~/logs/codex-spalla` on M5, 1 is 0644 (0 bytes, 2026-09-27T02:25:00Z).
- Under macOS `/bin/bash` 3.2 the wrapper run with no arguments dies at `:63` (`:82` at v4) with
  `_POSITIONAL_ARGS[@]: unbound variable`, rc 1, 0 stub calls.

A _forwarder_ puts repository or diff content into a prompt for an external seat of any vendor. The
_entrypoint_ is the one guard every forwarder calls. Each rule names the Migration slice that delivers it.

## Why four rounds failed

B = gate blocker, P = partial or should-fix carried forward, ✓ = cured, · = not raised.

| Rule                            | v1 #7466 | v2 #7470 | v3 #7475 | v4 #7483 | Rounds blocked |
| ------------------------------- | -------- | -------- | -------- | -------- | -------------- |
| G1 refusal list source, renames | B ×2     | P        | P        | P        | 1              |
| G2 fail-closed semantics        | ·        | B        | B        | B        | 3              |
| G3 names on the live path       | B        | B        | B        | P        | 3              |
| G4 path robustness              | P        | B        | P        | P        | 1              |
| G5 the wrapper: send, exit, log | B        | ✓        | ✓        | P        | 1              |
| G6 sibling egress               | P        | P        | B        | P        | 1              |
| G7 CI wiring, registry, Bites   | B        | P        | B        | B        | 3              |
| G8 artefact truth               | P        | B        | B        | B        | 3              |
| Blockers numbered by the gate   | 5        | 4        | 5        | 4        | 18             |

- **The acceptance list was the last gate's list.** Each round cured the named instance and the next gate
  found the next edge. gate-7470 wrote G2's cure as "missing, fails to parse or comes back empty"; v3 and v4
  did two of the three.
- **Gear avoidance.** v4 dropped its PR workflow to keep its floor at 2; under S5 (#7489) it would be 3.
- **Prose outran code.** 6 of the 18 blockers are false or stale sentences in artefacts that stay.
- **The target moved after arming.** v3's first blocker was "none of the lead's add-ons is in the PR".

## G1 — The refusal list comes from one named source

**Slice v5b, tests in `scripts/tests/test_egress_guard.py`.** The refused paths never had a source. v1
hand-typed 7 globs; v2-v4 joined 14 hand-typed globs (v4 `spalla_redact.sh:66-80`) to a parse of
`PII_PATH_FRAGMENTS` (`scripts/async_review_supervisor.py:40-46`). gate-7466 blocker 2: `docs/crm/` and 4
`.gitignore` PII shapes were missed, and gate-7470 found 5 more. Blocker 3: a rename out of `research/crm/`
passed, as `--name-only` lists only the destination. 22 PII-commented `.gitignore` patterns feed no guard.

**Rule.**

1. One tracked source holds the refusal globs: a new key `egress_refusal_paths` in
   `agent-library/config/redaction-rules.yaml`, the canonical redactor's config, in gitignore syntax with no
   `!` negation. `PII_PATH_FRAGMENTS` stays the second source, with its substring semantics; the union is
   refused. Entrypoint code holds no path literal; the tests pin only the four incident directories.
2. Initial content: the 22 `.gitignore` PII patterns (main lines 372, 373, 381-384, 392, 650, 696, 715, 716,
   721, 934-936, 938, 939, 944, 945, 948, 949, 951), plus `research/crm/`, `research/compliance/`,
   `research/wa-copilot/` and `docs/crm/` (7, 23, 2 and 6 tracked files). `scripts/wa_corpus/` (14 `.py`
   files) stays out: it is code, and G3 redacts any literal in it.
3. Matching follows gitignore semantics, not bash globbing: a basename pattern matches at any depth, a
   leading or middle `/` anchors, a trailing `/` covers the directory, `**` crosses directories.
4. The policy is read at the merge-base and in the working tree, and the union applies: a diff deleting a
   source entry cannot disarm its own review.
5. Committed and uncommitted path lists come from `--no-renames -z`, untracked ones from
   `ls-files -z --others --exclude-standard`. A rename contributes both of its paths.
6. Over-refusal is accepted (129 `/crm/`, 668 `/fixtures/`, 134 `/kb/` tracked files); G2.1's logged
   override exists for them.

- **Guilt** (temp repos, fake `psql`, no seat): `test_guilt_every_source_entry_refuses_a_synthetic_path`
  (one path per entry of both sources, generated at test time); `test_guilt_incident_dirs_are_pinned`;
  `test_guilt_rename_out_of_and_into_a_refused_dir_is_refused` (git reports `R100`);
  `test_guilt_a_diff_deleting_its_own_refusal_entry_is_still_refused`;
  `test_guilt_gitignore_pii_pattern_missing_from_source_fails` (expectations derived from `.gitignore`
  comments at test time, v3's method, which found the missing `compliance_report_*.pdf`).
- **Innocence**: `test_innocence_clean_code_diff_payload_equals_raw_git_diff` (byte for byte);
  `test_innocence_prefix_siblings_are_not_refused` (`docs/crm.md`, `scripts/wa_corpus/pilot.py`).

## G2 — Fail closed, under one rc contract

**Slice v5b for G2.1-G2.3 (entrypoint, `test_egress_guard.py`), v5a for G2.4 (wrapper argv,
`test_codex_spalla.py`).** A guard that could not establish its policy has answered "no hit". v3 and v4
accept a found-but-EMPTY fragment tuple (v4 `spalla_redact.sh:136-140` prints nothing, `:155` marks it `ok`,
`:174-178` miss); gate-7483 case b3 got rc 0 and one exec for both `= ()` shapes. The redactor CLI returns
1 for every failure (main `_redact_pii.py:594-601`), so no caller can tell missing names from a broken
redactor from a short input; gate-7470 case S12 got rc 8 for one small file (`min_remaining_chars`). v4 `:104`
says a broken source "is reported once per process", yet the call runs in `$(…)` at `:167`. Blockers:
gate-7470 3, gate-7475 2, gate-7483 1; the zero-argument crash is a gate-7475 should-fix.

**Rule.**

1. The entrypoint returns exactly one of these.

   | rc  | Class    | Cause                                                                                                                                                      | Override                                           |
   | --- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
   | 0   | SEND     | sanitized payload on stdout, possibly empty                                                                                                                | not needed                                         |
   | 10  | REFUSED  | a path hits G1; stderr lists paths only                                                                                                                    | `--allow-pii-paths`, logged; G3 and G4 still apply |
   | 11  | DEGRADED | the name list (G3), the refusal source or the fragments are missing, unreadable, unparseable or EMPTY, in either assignment shape; stderr names the remedy | none                                               |
   | 12  | ERROR    | redactor exception, non-idempotence, git error, timeout; stderr names the class, never payload                                                             | none                                               |

2. Empty input, and input shorter than `min_remaining_chars`, is SEND on this path: that length gate
   protects NotebookLM usefulness, not PII (`scripts/dynamic_workflow.py:1649-1657` pads around it).
3. The policy sources and the name list load once per dispatch, in one process.
4. The wrapper parses argv without crashing under bash 3.2 `set -u`: zero arguments mean `review main`, an
   invalid argument exits 1 before any capture, and an empty array expands only as `${A[@]+"${A[@]}"}`.

- **v5b guilt**: `test_guilt_empty_fragments_in_both_assignment_shapes_is_degraded`;
  `test_guilt_missing_unreadable_or_empty_refusal_source_is_degraded`;
  `test_guilt_override_cannot_bypass_degraded_or_error`; `test_guilt_unknown_failure_is_error_not_send`.
- **v5b innocence**: `test_innocence_short_benign_untracked_file_is_sent` (case S12);
  `test_innocence_empty_sections_are_not_an_error`; `test_policy_and_names_load_once_per_dispatch` (a
  3-path diff reads each source once and calls fake `psql` once).
- **v5a guilt**: `test_guilt_no_unguarded_empty_array_expansion_under_set_u` (a shape check for CI, where
  bash 5 hides the crash; fails on main's `:63`); `test_guilt_zero_args_under_bash_3_2_do_not_crash` (runs
  where `/bin/bash` is 3.x, as on M5; skipped elsewhere). **Innocence**:
  `test_innocence_explicit_args_parse_unchanged` (`review main focus`, `exec`, `--self-test`).

## G3 — CRM names are redacted by the entrypoint, or it sends nothing

**Slice v5b, tests in `test_egress_guard.py`.** v1 redacts static shapes only: the CLI calls
`Redactor.load_default()` with its default `require_dynamic_names=False` (main `_redact_pii.py:458-459`,
`:594`), and with `DATABASE_URL` and `PGURL` unset pass4 is skipped with a warning (`:355-358`). v2-v4 made
strictness an opt-in flag; at v4, FOCUS and the untracked path list are never redacted (v4 wrapper
`:33-37`, `:418`, `:441`). gate-7466 blocker 5: a fixture name crossed the "redacted" path. gate-7470
blocker 1: a v2 fixture, repeated 8 times in this PUBLIC repo, is the name on one PROD `clients` row
(gate-7475). gate-7475: rc 8 told the operator nothing about loading names.

**Rule.**

1. The entrypoint has one mode, names required; no flag or env var weakens it. Other callers keep theirs.
2. Names unavailable (env unset, DB unreachable, 0 names in both tables) gives rc 11 and 0 bytes on stdout.
   The stderr remedy names `scripts/pg.sh` and the `com.nuzantara.fly-pg-tunnel` LaunchAgent, no credential.
3. The CLI is `scripts/egress_guard.py payload --base <ref> [--allow-pii-paths]` with FOCUS on stdin. Its
   stdout carries every variable prompt section, redacted: committed, uncommitted and untracked diff, the
   untracked path list and FOCUS. Its `text` mode redacts stdin to stdout for non-diff callers.
4. Test fixtures are invented names proven absent from PROD before first use (`clients` and `companies`,
   exact and ILIKE, count 0, stated as counts in the PR body). No fixture is copied from another repo file.

- **Guilt**: `test_guilt_no_database_url_is_degraded_with_empty_stdout` (remedy on stderr, no credential);
  `test_guilt_zero_names_loaded_is_degraded`; `test_guilt_db_error_is_degraded` (fake `psql`);
  `test_guilt_fixture_name_in_focus_untracked_path_and_body_is_redacted` (placeholder in, name out).
- **Innocence**: `test_innocence_names_loaded_text_without_names_is_unchanged`.

## G4 — Paths are parsed, never guessed

**Slice v5b, tests in `test_egress_guard.py`.** An awk state machine over diff headers decides which lines
are suppressed (v4 `spalla_redact.sh:181-221`), and each header oddity git produces has broken it once: a
space plus git's trailing TAB; a `"`, TAB or `\` in the name, quoted by git even with
`core.quotePath=false`; `export.CSV` (case-sensitive match at `:214`); `color.ui=always` in user config.
Only DELETED lines of data files are suppressed, so added and context lines of a data file outside the
refusal list reach the redactor raw. gate-7466 S6; gate-7470 blocker 2; gate-7475 cases d2, e3, e4;
gate-7483 cases d2/d3/d4 (raw body 5 of 5 in the prompt), e3, e5 (`q"x.csv`).

**Rule.**

1. Every path list is NUL-separated (`-z`) end to end. No path is re-parsed out of diff text.
2. A data file (`.jsonl`, `.csv`, `.tsv`, `.xlsx`, extension matched case-insensitively) never has a body
   line embedded, whether deleted, added or context; its path (through G3) and `--numstat` counts are. The
   decision uses the `-z` list and pathspec exclusion, never diff headers.
3. Every body capture runs `git -c core.quotePath=false diff --no-color --no-ext-diff --no-textconv`, so
   no user or system git config changes what is captured.
4. G1 applies to the same `-z` list, so a quoted, tabbed or newline-bearing path is compared as spelled.

- **Guilt**: `test_guilt_special_char_paths_under_a_refused_dir_are_refused` (`"`, TAB, `\`, newline,
  non-ASCII, committed on a branch); `test_guilt_data_file_bodies_are_withheld_for_every_spelling`
  (`export.CSV`, `q"x.csv`, `data file.tsv`; added, deleted and context lines; raw fixture count 0);
  `test_guilt_hostile_git_config_cannot_leak_a_body` (`color.ui=always`, `diff.external`, a textconv).
- **Innocence**: `test_innocence_space_path_code_file_is_sent_redacted_not_refused`;
  `test_innocence_withheld_data_file_keeps_path_and_counts`.

## G5 — The spalla wrapper sends only entrypoint output, exits by contract, logs safely

**Slice v5c, tests in `scripts/tests/test_codex_spalla.py` (fake codex, stub or real entrypoint).** v1
embeds its own captures and writes every artefact under the caller's umask, 022 on M5; v2-v4 added
`umask 077` and chmod, but main runs v1. The transcript is created (main wrapper `:213`) before the refusal
check (`:252`), so a refused run leaves an empty file. FOCUS reaches telemetry (`:232`) and the filename
slug (`:199`). The BLOCKER copy lands in `$REPO_ROOT/docs/codex-reviews/`, inside a git worktree, kept out
of the public repo by `.gitignore:902` alone. v1's `.sh` corpus runs the real codex when it is logged in.
gate-7466 blocker 4: 55 of 55 files were group- or world-readable. gate-7483 should-fix:
`.claude/commands/codex-second-opinion.md` never documents exits 7 and 8.

**Rule.**

1. The prompt is the fixed template plus the entrypoint's rc-0 stdout, nothing else. Entrypoint rc 10 maps
   to wrapper exit 7; every other non-zero rc maps to exit 8. Either way nothing is sent.
2. FOCUS text never reaches telemetry or a filename; both carry its hash and length.
3. Log dirs are 0700 and files 0600 under any umask, looser modes are tightened, and temp files are 0600
   and removed on exit and on signals.
4. A transcript exists only when a send happens and holds the prompt as sent, the reply and diagnostics.
   REFUSED, DEGRADED and ERROR write one telemetry line of counts, rc, guard class and FOCUS hash.
5. The BLOCKER copy lives in the 0700 log dir, outside the repository tree.
6. `.claude/commands/codex-second-opinion.md` documents exits 7 and 8 and the G3.2 remedy. The awk strip in
   `scripts/lib/spalla_redact.sh` and v1's `.sh` corpus are deleted; their assertions live in G4's tests.

- **Guilt**: `test_guilt_any_nonzero_guard_rc_sends_nothing` (stub entrypoint returning 1, 2, 10, 11, 12,
  127 and dying by SIGKILL; 0 fake-codex calls); `test_guilt_no_database_url_exits_8_and_writes_no_transcript`;
  `test_guilt_fixture_name_in_focus_never_reaches_telemetry_or_filename`;
  `test_guilt_umask_000_and_022_still_yield_0600_files_in_0700_dirs`;
  `test_guilt_preexisting_loose_modes_are_tightened`; `test_guilt_temp_files_are_removed_after_sigterm`;
  `test_guilt_blocker_copy_lands_outside_the_repo_tree`; `test_guilt_second_opinion_doc_names_exits_7_and_8`.
- **Innocence**: `test_innocence_clean_code_diff_prompt_is_byte_identical` (against the pre-#7466 wrapper,
  the gates' case i); `test_innocence_transcript_prompt_equals_what_the_seat_received`.

## G6 — One entrypoint for every forwarder

**Slice v5d, tests in `scripts/tests/test_egress_census.py`.** Each round found a forwarder the previous
sweep missed: v1's `*.sh`-only grep missed `scripts/codex_tri_llm_review.py`, and S5 v2 missed
`infra/workflows/second-army.js`. v4 disabled the tri-LLM CLI (exit 3, v4 `:874-892`), but
`scripts/review_gate_run.sh` counts rc ≤ 3 as "reviewed" (`:163`, comment at `:150`), and the tracked
`infra/launchagents/com.nuzantara.review-gate.plist` would re-arm it (gate-7466 Siblings, gate-7475 blocker
4, gate-7476 blocker 2). Tri-LLM on main puts raw `gh pr diff`/`git diff` output (`:178`, `:211`) through
`build_prompt` (`:231`, `:811`) into `codex exec` (`:403-407`) and `kimi -p` (`:605-610`) argv.
second-army.js has its refuter lane run `git diff origin/main...${FROZEN_REF}` (`:544`) for a seat door
(`:87-120`), with 0 `redact`. On Pro the review-gate plist is parked unloaded (ctime 2026-09-26T23:56:21Z,
`StartInterval` 600); its log has 6182 lines, all "no open agent/\* PRs", the last at 23:55:05Z.

**Rule.**

1. `scripts/egress_guard.py` (created in v5b) is the only entrypoint. A forwarder sends only its rc-0 stdout
   plus the forwarder's fixed template, and no seat-bound prompt tells a seat or lane to run `git diff`.
2. IN, each routed or deleted in v5d: `scripts/codex_tri_llm_review.py` with `scripts/review_gate_run.sh`
   and the tracked plist (recommended: delete all three, as 6182 recorded runs dispatched nothing), and the
   second-army.js refuter lane. Spalla is routed in v5c (G5).
3. OUT, each reason written into the census exemptions. `.claude/hooks/codex-spalla-trigger.sh` sends
   nothing. `scripts/codex/*` send name lists and let the seat read the repo (a residual).
   `scripts/lint_paid_llm_entity.py` sends text GitHub already publishes for this PUBLIC repo, through a
   redactor that strips secrets and emails but not CRM names, so it is never a name guard.
   `infra/claude-hooks/session_budget.py` calls no seat. `scripts/agent-library-evolver-run.sh`,
   `scripts/_entailment_check.py` and `apps/backend-rag/sandbox/egress_proxy.py` carry non-diff content.
4. Named follow-up outside v5: `scripts/dynamic_workflow.py:455` and `:1655` call `load_default()` without
   names required and read "unchanged by redaction" as clean, the G3 defect in another caller.

- **Guilt** (precedent: the codex seat census, `scripts/tests/test_codex_seat_lib.py:216` and `:239`):
  `test_guilt_census_flags_a_forwarder_that_bypasses_the_entrypoint` (synthetic `.sh`, `.py` and `.js` files
  that capture a diff and call a seat door); `test_guilt_second_army_refuter_prompt_carries_no_raw_git_diff`.
- **Innocence**: `test_innocence_census_ignores_prose_and_name_only_callers`. **Verdict**:
  `test_every_forwarder_calls_the_one_entrypoint` over `git ls-files`, each exemption with a reason.

## G7 — Each slice wires its own tests; the guard is censused; Bites is post-merge

**Every slice, from v5a.** The spalla tests run only in `scripts-tests-sweep.yml` (`schedule` plus
`workflow_dispatch`, report-only, `continue-on-error: true`); no workflow runs `test_codex_spalla` for a PR.
The guard registry has no entry for the wrapper, the lib or the redactor, so the checker's 0 violations are
vacuous, and every round's `Bites:` cited pre-merge test counts (gate-7466, -7475, -7483). A first draft of
this spec had v5a wire a test v5a could not make green (gate-7513 blocker 1). The required check "Every guard
proves guilt AND innocence" (`guard-conformance.yml:91`) runs on `pull_request` and `merge_group` behind a
path sentinel (`:110-127`) and on `push` to main behind a paths filter.

**Rule.**

1. Each slice adds to that required job, in the same PR, exactly the test files it makes green, and adds
   every file those tests read to the sentinel regex and the `push:` paths. v5a adds `test_codex_spalla.py`
   with the wrapper, the lib and `.claude/commands/codex-second-opinion.md`; v5b adds `test_egress_guard.py`
   with the entrypoint and both policy sources; v5d adds `test_egress_census.py` with the forwarders it
   names. v5c and v5e change no workflow file. No step names a test its own slice cannot make green, and
   the nightly sweep is not CI.
2. v5b adds a `check_bridge`-shaped surface `egress_guard` to `infra/guard-conformance/registry.json`,
   mapping each `guard_*` function to its G1-G4 guilt and innocence tests, wired by one `check_bridge(...)`
   line in `check_guard_conformance.py::main()` that also adds its guard count to the summary line.
3. v5b adds a sync test asserting that the sentinel regex matches every registered guard path (precedent
   `scripts/tests/test_hotzone_lists_sync.py`, which lands with #7489); v5d extends it to the census file.
4. v5b adds `scripts/egress_guard.py`, `agent-library/config/redaction-rules.yaml` and
   `scripts/async_review_supervisor.py` to S5's hot-zone list and its sync test; alone, each floors at 1.
5. Each slice's `Bites:` is the post-merge observation in its Migration entry, stated with its command.

- **v5b guilt**: `test_guilt_sentinel_missing_a_guard_path_fails`. **Innocence**:
  `test_innocence_unrelated_path_does_not_trigger_the_sentinel`. The checker's C1-C4 cover the surface.

## G8 — Artefacts say what is true, and a command proves it

**Slice v5e rewrites W140; P5-P7 bind every v5 head, and its gate runs them.** A first draft of this spec
had probes that a W140 with only its timestamps fixed would pass (gate-7513 blocker 2). W140 on main
(`docs/scars/cicatrix-scars.md:1780-1819`) overclaims at `:1787`, `:1793`, `:1797`, `:1801` and `:1808`,
and main's lib `:7` says deleted data lines are never embedded, falsified by gate-7466 S6. v4's W140 labels
WITA times as `Z`, calls Pro "unverified" and the 16 files untraced; v2's lib cites a missing test file; v2
to v4 add lines that point at where pre-existing PII sits.

**Rule.** The v5 W140 states the following, and only this.

1. Incident: the dispatch transcript is stamped 2026-09-26T20:58:01Z; the PII-removal diff's 959 deleted
   lines of a client `plan.jsonl` went to OpenAI in cleartext.
2. Window: client-name egress is confirmed from 2026-09-18, not as one event. 14 of the 16 batch files carry
   at least 1 PROD multi-word name, 8 distinct by hash, all 8 also present in tracked files. One of the 8 is
   a `clients.full_name`, found in the transcript stamped 2026-09-18T06:47:33Z (gate-7475).
3. Quarantine, counts only: `~/.agent/pii-quarantine` is 0700 and holds 18 files, 0 with group or other
   bits. Group A, the incident pair, is 2 files moved 2026-09-26T21:41:41Z. Group B is 16 files moved
   2026-09-26T22:01:07Z by the first builder session's sweep (per the lead; that session died before
   reporting), with mtimes 2026-09-05T04:00:18Z to 2026-09-26T15:54:17Z.
4. Pro's review gate, per the G6 evidence: loaded with `StartInterval` 600 until parked at
   2026-09-26T23:56:21Z, 0 dispatches recorded across 6182 log lines.
5. ANTIBODY clauses describe merged behaviour only, each naming the test that pins it.
6. Timestamps are UTC (`stat -f %c`, `TZ=UTC date -r`); every cross-PR state carries `as_of` (S4 of
   `docs/specs/2026-09-27-evidence-pack-fixed-point.md`).

The guard files' comments obey the same rule. They claim merged behaviour only, every test they cite
resolves, and no added line of any v5 diff points at where client PII sits.

**Probes.** Run from the repository root of the head under review. Each passes only on the value shown.

```sh
W140() { awk '/^## W140 /{f=1} f&&/^## /&&!/^## W140 /{exit} f' docs/scars/cicatrix-scars.md; }
G='scripts/lib/spalla_redact.sh scripts/egress_guard.py .claude/scripts/codex-spalla.sh'
# P1 utc_quarantine_times: 0, then 2
W140 | grep -cE '2026-09-27T0(5:41:41|6:01:07)Z'
W140 | grep -oE '2026-09-26T(21:41:41|22:01:07)Z' | sort -u | wc -l
# P2 window_from_0918: >= 1
W140 | grep -c '2026-09-18'
# P3 quarantine_inventory: 0, then >= 1, then >= 1
W140 | grep -ciE 'zero additional|zero further|two contaminated|independently trac'
W140 | grep -cE '\b18 files\b'
W140 | grep -cE '\b16 files\b'
# P4 pro_liveness: 0, then >= 1
W140 | grep -ciE 'unverified|unreachable|not wired live'
W140 | grep -c '2026-09-26T23:56:21Z'
# P5 no_false_comment_claims: 0
cat $G 2>/dev/null | grep -ciE 'once per process|future work|still a hand-typed|never embed a deleted line'
# P6 cited_tests_resolve: no output
{ W140; cat $G 2>/dev/null; } | grep -oE 'scripts/tests/[A-Za-z0-9_./-]+\.(py|sh)' | sort -u | while read -r p; do [ -e "$p" ] || echo "missing $p"; done
W140 | perl -ne 'print "$1\n" while /\b(test_[a-z0-9_]+)\b(?!\.(?:py|sh))/g' | sort -u | while read -r t; do git grep -qF "def $t(" -- scripts/tests apps || echo "missing $t"; done
# P7 no_leak_pointer: 0
git diff -U0 "$(git merge-base origin/main HEAD)" HEAD | grep -E '^\+[^+]' | grep -iE -A1 'client_id|real (client|name)|prod client' | grep -cE '[A-Za-z0-9_-]+\.(py|sh|jsonl|csv|json)\b'
```

Measured at 03:45Z on each file at the named head. Guilt is a FAIL on a round the gates rejected; innocence
is a PASS on a true reference. The W140 reference for P1-P4 is this section's own Rule list.

| Probe | v1 (main)         | v2                    | v3           | v4                  | v4, times fixed only | True reference                      |
| ----- | ----------------- | --------------------- | ------------ | ------------------- | -------------------- | ----------------------------------- |
| P1    | FAIL              | FAIL                  | FAIL         | FAIL (2 local-as-Z) | PASS                 | PASS                                |
| P2    | FAIL              | FAIL                  | FAIL         | FAIL                | FAIL                 | PASS                                |
| P3    | FAIL (2 bad)      | FAIL (2 bad)          | FAIL (2 bad) | FAIL (3 bad)        | FAIL                 | PASS                                |
| P4    | FAIL (0 parked)   | FAIL (3 bad)          | FAIL (3 bad) | FAIL (3 bad)        | FAIL                 | PASS                                |
| P5    | FAIL (1)          | FAIL (1)              | FAIL (3)     | FAIL (3)            | n/a                  | PASS on `scripts/lib/codex_seat.sh` |
| P6    | PASS              | FAIL (1 missing file) | PASS         | PASS                | n/a                  | PASS                                |
| P7    | PASS (#7466 diff) | FAIL (1)              | FAIL (3)     | FAIL (2)            | n/a                  | PASS on #7513's diff                |

## Migration

**State.** Close #7483 as superseded, reusing its tri-LLM refusal test and rc-8 remedy text. #7489 (S5 v3)
is OPEN and armed; every slice starts after it merges, because v5a, v5b and v5d edit `guard-conformance.yml`
as #7489 does. Slices run serially, each from a fresh origin/main. Floors are measured on each slice's file
list with main's lint and #7489's; floor 3 (`path`) means gear 3: `brief.yml`, `pack.yml` and a fresh gate
verdict before arming. Every v5 PR states its fixtures' PROD counts (G3.4) and passes P5-P7 at its gate.

1. **v5a, wrapper harness: G2.4, G7.1.** The wrapper sources its lib from its own path (v2's cure, 11 of 11
   green at gate-7470) and survives zero arguments; `test_codex_spalla.py` joins the step. Floor 3. Bites:
   the `push` run on the merge commit ran `test_codex_spalla.py` with 0 failures; on M5, with a stub `codex`
   first on `PATH`, `/bin/bash .claude/scripts/codex-spalla.sh` prints no `unbound variable` and exits 5
   before any capture, so nothing reaches a seat.
2. **v5b, the entrypoint: G1, G2.1-G2.3, G3, G4, G7.1-G7.4.** The entrypoint, the policy key, its tests,
   the registry surface, the sync test and the S5 additions; the wrapper is not switched. Floor 3. Bites:
   the `push` run ran `test_egress_guard.py` with 0 failures and the checker counts `egress_guard` guards
   with 0 violations; on M5 at origin/main, this exits 11 with 0 bytes on stdout:
   `env -u DATABASE_URL -u PGURL python3 scripts/egress_guard.py payload --base main </dev/null`.
3. **v5c, spalla on the entrypoint: G5.** The wrapper sends only entrypoint stdout; the awk strip and the
   `.sh` corpus go. Floor 3 under #7489's lint. Bites: on M5 at origin/main with one untracked file holding
   an invented name, the wrapper with `DATABASE_URL` unset exits 8, the last `~/logs/codex-spalla.jsonl`
   line shows `guard=degraded` and no transcript appears; with names loaded it exits 0, and the new
   transcript is `-rw-------` and shows the placeholder, not the name.
4. **v5d, siblings: G6, G7.1, G7.3.** The tri-LLM trio is deleted or routed and the refuter routed. Floor 3.
   Bites: the `push` run ran the census with 0 failures, and on origin/main
   ``grep -c 'Run `git diff' infra/workflows/second-army.js`` returns 0.
5. **v5e, truth: G8.** W140 is rewritten against merged v5a-v5d. Floor 1 (`none`). Bites: P1-P6 pass on
   origin/main after merge; P7 is checked on each head before merge.

**Containment and residuals.** Until v5c merges, main's wrapper forwards CRM names for any non-refused path
when `DATABASE_URL` is unset; pausing spalla until then is the lead's call. Not closed by v5: a codex seat
in a read-only sandbox can grep tracked PII itself (the pii-deep-audit lanes own that data), and fragment
over-refusal (G1.6) can breed override fatigue; watch the share of `allow_pii_paths=true` telemetry lines.

**Done, per rule**, one criterion each, observed on origin/main after the slice named.

| Rule | Complete after | Criterion                                                                                         |
| ---- | -------------- | ------------------------------------------------------------------------------------------------- |
| G1   | v5b            | the `push` run shows every G1 test passing in the required job                                    |
| G2   | v5b            | the `push` run shows every G2 test passing, G2.4's included since v5a                             |
| G3   | v5b            | on M5, the entrypoint with `DATABASE_URL` unset exits 11 with 0 bytes on stdout                   |
| G4   | v5b            | the `push` run shows every G4 test passing, raw fixture count 0 in each                           |
| G5   | v5c            | on M5, the wrapper with `DATABASE_URL` unset exits 8, logs `guard=degraded`, writes no transcript |
| G6   | v5d            | the `push` run shows `test_every_forwarder_calls_the_one_entrypoint` passing                      |
| G7   | v5d            | the `push` run on v5d's merge commit runs all three test files and the sync test, 0 failures      |
| G8   | v5e            | P1-P6 pass on origin/main                                                                         |
