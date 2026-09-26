# Mutation table — exhaustive re-run (R3, fresh re-gate 2026-09-27)

The fresh re-gate on PR #7420 @ `737d16224a` re-ran C1's mutation table itself
(`regate7420/mutants.py`) and found TWO guards still surviving deletion with the
suite green — the same fixture-masking class as the original C1 finding, second
occurrence. Per the Builder Contract's depth rule, the acceptance is now this
EXHAUSTIVE table: every guard AND every conjunct of a compound guard must turn

> =1 test red when deleted alone. This is the builder's own re-run of that same
> exhaustive table, against the CURRENT wrapper (both new fixtures added, R3),
> using a real subprocess mutation harness
> (`/private/tmp/claude-501/.../scratchpad/mutants_r3.py`, not committed — scratch,
> same convention as the gate's own `regate7420/mutants.py`): each guard is
> deleted from the ACTUAL worktree wrapper file (not a copy pasted elsewhere),
> `python3 -m pytest scripts/tests/test_wa_codex_broker_wrapper.py -q` is run as
> a real subprocess against the mutated file, and the file is restored
> byte-for-byte from an in-memory copy after each mutant. Baseline: `28 passed`.
> After the full run: `restored identical: True`, `git hash-object` of the
> wrapper before and after the run match exactly
> (`4143a795d9f2237d11896504d0b3b2487fea7b8e`), and `git status --short` on the
> wrapper shows only this PR's own already-staged N3 comment change, nothing
> left over from the harness.

| Guard deleted                                                                               | Result                     | Discriminating test(s)                                                                                                                                                                                   |
| ------------------------------------------------------------------------------------------- | -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| G1 NUL probe (`read -r -d ''`)                                                              | RED 1/28                   | `[nul_same_line_planted]`                                                                                                                                                                                |
| G2 exactly-one-line check                                                                   | RED 1/28                   | `[two_lines_diff_versions_planted]`                                                                                                                                                                      |
| G3 `_is_semver` call                                                                        | RED 2/28                   | `[bad_semver_planted]`, `[traversal_escape_planted]`                                                                                                                                                     |
| G4a `-L` symlink check                                                                      | RED 1/28                   | `[symlink_pin]`                                                                                                                                                                                          |
| G4b key `case` guard (accept any line as the value)                                         | **RED 1/28 (NEW fixture)** | `[bare_version_planted]`                                                                                                                                                                                 |
| G5 `-f`/`-x` binary check, whole block removed                                              | RED 3/28                   | `[bin_missing]`, `[bin_is_directory]`, `[bin_not_executable_planted]`                                                                                                                                    |
| G5a `-f` half only (revert to `-x`-only, C2's original defect)                              | RED 1/28                   | `[bin_is_directory]`                                                                                                                                                                                     |
| G5b `-x` half only (keep `-f` only)                                                         | **RED 1/28 (NEW fixture)** | `[bin_not_executable_planted]`                                                                                                                                                                           |
| non-regular `-e && ! -f` check                                                              | RED 2/28                   | `[directory]`, `[fifo]`                                                                                                                                                                                  |
| C3 `RUNTIME_DIR` searchable guard                                                           | RED 1/28                   | `test_guilt_unsearchable_runtime_dir_refuses_not_legacy`                                                                                                                                                 |
| N4 `[ -r ]` readability check                                                               | RED 1/28                   | `test_guilt_mode_000_pin_reports_unreadable_not_line_count`                                                                                                                                              |
| N1 re-assert, `HOME_DIR` line only (of 6)                                                   | RED 1/28                   | `test_guilt_env_cannot_clobber_post_source_literals`                                                                                                                                                     |
| N1 re-assert, `RUNTIME_DIR` line only                                                       | RED 1/28                   | `test_guilt_env_cannot_clobber_post_source_literals`                                                                                                                                                     |
| N1 re-assert, `VENV_PY` line only                                                           | RED 1/28                   | `test_guilt_env_cannot_clobber_post_source_literals`                                                                                                                                                     |
| N1 re-assert, `TAG` line only                                                               | RED 1/28                   | `test_guilt_env_cannot_clobber_post_source_literals`                                                                                                                                                     |
| N1 re-assert, `ORGAN_ID` line only                                                          | RED 1/28                   | `test_guilt_env_cannot_clobber_post_source_literals`                                                                                                                                                     |
| N1 re-assert, `SIDECAR_DIR` line only                                                       | RED 1/28                   | `test_guilt_env_cannot_clobber_post_source_literals`                                                                                                                                                     |
| positional handoff → named vars post-source (`$1`/`$2` → `$_wcbw_pin_ver`/`$_wcbw_pin_bin`) | RED 1/28                   | `test_guilt_daemon_env_cannot_clobber_the_resolved_pin`                                                                                                                                                  |
| `exec /usr/bin/env WA_CODEX_CLI_VERSION_PIN=... WA_CODEX_BIN=...` → plain `exec "$VENV_PY"` | RED 6/28                   | both F5 PATH cases, `test_guilt_daemon_env_cannot_clobber_the_resolved_pin`, `test_guilt_env_cannot_clobber_post_source_literals`, `test_innocence_valid_pin_overrides_env`, `test_pin_applied_log_line` |
| (none — shipped wrapper)                                                                    | 0 red, 28 green            | —                                                                                                                                                                                                        |

**A note on the two N1-line entries above and why they are correct now, where
an earlier version of this harness was wrong.** Six of the wrapper's
constants (`HOME_DIR`/`RUNTIME_DIR`/`VENV_PY`/`TAG`/`ORGAN_ID`/`SIDECAR_DIR`)
are each declared TWICE with byte-identical text: once in the top-level
constants block (before the pin parse), and once in the N1 re-assert block
(right after `. "$ENV_FILE"`). A naive single-occurrence text substitution
targeting "the `VENV_PY=` line" with no positional anchor silently deletes the
FIRST (top-level) occurrence instead of the intended N1 one — which is a
near no-op for `VENV_PY` specifically (never read before the N1 block sets
it again) and a much bigger, WRONG-signal break for the other five (used
during pin-parse, before N1 ever runs, so deleting the top declaration
cascades into unrelated `present_but_invalid_pin_refuses` failures that have
nothing to do with the N1 guard under test). This table's harness anchors
each N1 mutation to the N1 comment block specifically (between its own
`# N1 (gate 2026-09-26): re-assert...` marker and the following `# G5_kill_
switch` marker) before deleting the target line, so each of the 6 mutants
turns on exactly the one test the guard is meant to protect.

Acceptance (R3, exhaustive): deleting ANY guard, or EITHER conjunct of a
compound guard, alone, turns >=1 test red. **Met for every row above,
including the two rows the fresh re-gate found surviving at head
`737d16224a` (G4b, G5b) — both are now covered by the two new fixtures
`bare_version_planted` and `bin_not_executable_planted`.**

## History (kept for record, not re-verified in this pass — see the exhaustive table above for current state)

Delta-council round 1 (codex-gpt-5.6-sol, read-only sandbox) caught that the FIRST C3 test broke
`RUNTIME_DIR`'s mode while the pin file lived OUTSIDE it (siblings, not container/contents) — the test
only proved the new top-level guard fires, not the real EACCES-reads-as-absent defect. Corrected: the
pin file now lives INSIDE `RUNTIME_DIR`; mutation-verified (removing the C3 guard now makes the test
fail with the ORIGINAL bug's exact diagnostic, `no pin file at ... (legacy)`, not a generic crash).

Before the REWORK-BUILD fix (gate's own r0 table, head `08a5d93537`, old 17-test file):

| Guard deleted  | Result                                                                                                                                                 |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| NUL probe      | 17/17 green (non-discriminating)                                                                                                                       |
| one-line check | 17/17 green (non-discriminating)                                                                                                                       |
| `_is_semver`   | 17/17 green (non-discriminating); isolating probe: `9.9` APPLIED, `../escape` APPLIED with the derived binary path landing OUTSIDE `PINNED_CODEX_ROOT` |
| `-L` symlink   | 1 red (already discriminating)                                                                                                                         |
| `-x` binary    | 1 red (already discriminating)                                                                                                                         |

The REWORK-BUILD fix: `embedded_nul`/`bad_semver`/`two_lines` (pre-existing cases) never planted the
binary the fault would otherwise resolve to, so the binary-existence check (a LATER guard) masked
whichever EARLIER guard the mutation removed. Four new cases plant the binary/tree the fault
resolves to: `nul_same_line_planted`, `two_lines_diff_versions_planted`, `bad_semver_planted`, and
`traversal_escape_planted`.

The fresh re-gate's R3 finding (this table's own reason for existing): the REWORK-BUILD fix above
closed that class for `_is_semver`/NUL/line-count, but C2's own new `[ -f ] && [ -x ]` compound
guard and the pin-format `case` guard were never individually isolated — `unknown_key`
(`SOMETHING_ELSE=9.9.9`) still fails `_is_semver` on its own characters regardless of the `case`
guard, masking G4b; and no fixture ever isolated the `-x` half of the new `-f && -x` check on its
own, since `bin_missing` fails BOTH conjuncts at once. `bare_version_planted` and
`bin_not_executable_planted` close both.
