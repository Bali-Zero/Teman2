# LocalCI ceremony launcher

`launcher.zsh` is the installed, normative entry point for C3 and C12. It
validates `M` and the ceremony name, verifies its executable closure, fetches
from a literal remote into a fresh bare repository, refuses history rewind,
extracts the body at `M`, and runs that file in a sterile process.

## Properties and tests

| Property | Test |
| --- | --- |
| Exactly two validated arguments and an allow-listed name | `test_argv_refusals_are_64` |
| BSD `-perm +0022`, ACL, symlink target and complete target-parent trust walk | `test_trust_walk_table` |
| `/System/Volumes/Data` targets are refused | `test_shipped_security_contract_is_literal` |
| Git config is an exact allow-list for C3 and C12 | `test_config_allow_list_rejects_every_extra_or_changed_entry`, `test_c3_and_c12_each_match_the_exact_config_list` |
| HTTPS and SSH remotes are literal; C12 SSH has a fixed command and known-hosts file | `test_shipped_security_contract_is_literal` |
| Journal is a regular readable file, forward-only, root-owned 0444 after success | `test_bad_journal_table_halts`, `test_absent_journal_is_allowed_only_for_bootstrap`, `test_journal_forward_same_and_rewind` |
| Body receives verified `M`, work dir, `cwd=work dir`, and only the three supplied environment keys | `test_body_contract_has_two_args_cwd_and_only_the_supplied_env` |
| Body is a file; hostile stdin cannot consume later source | `test_hostile_stdin_cannot_truncate_the_body` |
| Watchdog kills the exec'd fetch and distinguishes timeout from fetch failure | `test_watchdog_timeout_is_70_and_leaves_no_fetch_process`, `test_fetch_failure_is_69` |
| Every post-directory exit removes the bare repository and leaves one receipt | `test_cleanup_and_receipt_after_body_success_or_failure` |
| `/etc/zshenv` must be absent | `test_zshenv_presence_halts` |
| Test code differs from shipped code only by the table below | `test_test_copy_diff_is_exactly_the_declared_patch_table` |

The body contract is `$1=M`, `$2=work dir`, `PWD=$2`. `$2/w.git` contains
`M`'s objects. A body reads repository code only through
`git cat-file blob "${1}:path"`, never through `FETCH_HEAD`.

The C12 Git environment sets:

```text
GIT_SSH_COMMAND=/usr/bin/ssh -F /dev/null -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/Users/zero-ops/.ssh/known_hosts_localci
```

The journal is replaced after a successful body with
`/usr/bin/sudo /usr/bin/install -o root -g wheel -m 0444`. An absent journal
is accepted only for the exact name `C3-bootstrap`.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Ceremony and journal update succeeded |
| 64 | Argument count, commit syntax, or name is invalid |
| 65 | Trust, config, history, extraction, journal, or internal refusal |
| 69 | Fetch exited unsuccessfully |
| 70 | Fetch exceeded the watchdog limit |
| other nonzero | Exact body exit status, propagated |

## Declared test-copy patch set

The harness applies named literal substitutions and asserts the resulting copy
equals their composition:

1. `ceremony-home`: `/Users/zero-ops` to a temporary home.
2. `tool-root`, `trust-owner`, `link-parent-stop`, `trust-roots`,
   `closure-roots`: use a user-owned temporary closure; only trust predicates
   change `root` to the current user.
3. `c3-file-remote`, `c12-file-remote`: use one local bare `file://` remote and
   add only `protocol.file.allow=always` to the copied allow-list.
4. `zshenv-probe`: redirect the absence probe to a temporary path.
5. `unprivileged-install`: replace `sudo install -o root -g wheel` with plain
   `install` while retaining mode 0444.
6. `watchdog-ticks`, `watchdog-tick-duration`, `watchdog-grace`: shorten time
   in the copy only.

Run:

```sh
python3 -m pytest scripts/localci/ceremonies/tests -q
python3 scripts/localci/tests/mutants/ceremony_launcher_mutants.py
```

Tests use local repositories only. Any future network case must carry the
`network` marker and is skipped unless `LOCALCI_NET_TESTS=1`.
