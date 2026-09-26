BLOCKER: the positional handoff protects only the two pin values. A DATA-only env line such as `VENV_PY=/opt/homebrew/bin/codex` still overwrites the trusted interpreter after sourcing and is then executed at [wa-codex-broker-wrapper.sh:213](/Users/balizero/nuzantara/.worktrees/infra-gate-7420/infra/launchagents/wrappers/wa-codex-broker-wrapper.sh:213). No shell commands are required in the env file. This is inherited from main, but it remains inside the stated stale/wrong-DATA threat model and can stop the bot or execute an unpinned program.

## 1. D5 conformance — REWORK

Most mechanical requirements are met:

- Pin parsing precedes `. "$ENV_FILE"`.
- Parsing and validation use shell builtins/control syntax; no PATH-resolved validator is used.
- `PINNED_CODEX_ROOT` is a literal, and the binary path is derived from it.
- `_is_semver` is verbatim.
- Missing pin alone enters legacy mode; symlinked and non-regular pin files fail with exit 78 and the required heartbeat.
- `/usr/bin/env` assignments override the daemon env’s pin variables.
- The protocol line is exact.
- With untouched `TAG`, the live-proof line has the required form and uses `/bin/date`.

Two defects prevent acceptance:

1. `[ -x "$PIN_BIN" ]` accepts a mode-0755 directory. The wrapper then logs “pin applied” and starts the daemon with the directory as `WA_CODEX_BIN`. That contradicts “binary missing ⇒ fail closed.” Require at least `-f` and `-x`, with a test.
2. `TAG` remains env-clobberable, so a plain `TAG=anything` line prevents the exact required live-proof prefix from being emitted.

## 2. Positional-parameter deviation — REWORK

The deviation itself is sound. I verified on macOS `/bin/sh` Bash 3.2.57 that shell-function arguments do not destroy the script’s `$1/$2`; after `heartbeat status note`, the original pin parameters are restored.

DATA-only constructs cannot alter `$1/$2`:

- `KEY=value`
- quoted assignments
- `export KEY=value`
- blank lines/comments
- CRLF assignments, although the carriage return may contaminate the assigned value

Changing positional parameters requires executing something such as `set --`, which crosses into the explicitly excluded malicious/code-execution class.

However, these trusted names are still consumed after sourcing and remain clobberable:

- `VENV_PY`: redirects the executable and is the blocker.
- `RUNTIME_DIR`: redirects `cd` and `PYTHONPATH`, commonly stopping the bot.
- `TAG`: falsifies the mandatory proof-line prefix.
- `SIDECAR_DIR` and `ORGAN_ID`: redirect or rename the heartbeat.
- `PATH`: can disable the post-source heartbeat’s unqualified `mkdir`/`date`, although the final proof line correctly uses `/bin/date`.

These weaknesses predate this PR, but “D5 closes the stale/wrong-DATA class” is too broad under the supplied threat model. Preserve or restore all trusted post-source constants via positional parameters, then add collision tests.

## 3. NUL probe — ACCEPT-WITH-NOTES

On the actual target shell, it works. I executed it under Bash 3.2 POSIX mode; `read -r -d ''` returned success on finding NUL.

The dash claim is false. I executed the same command under `/bin/dash`; dash reported:

```text
read: Illegal option -d
```

On dash the probe therefore fails open as a feature check, and the ordinary reader can accept `WA_CODEX_CLI_VERSION_PIN=9.9.9<NUL>JUNK` as the valid prefix. This is not a current-host blocker because the declared launchd `/bin/sh` is Bash 3.2, but the comment must not claim dash support.

The NUL guard is needed for strict byte-level “exactly one line” validation. Without it, junk after a NUL on the same physical line disappears from the shell variable.

The existing test does not prove that. Its bytes are:

```python
b"WA_CODEX_CLI_VERSION_PIN=9.9.9\n\x00JUNK\n"
```

I verified that Bash’s ordinary loop counts this as two rows, so it fails even if the NUL probe is removed. The discriminating fixture is:

```python
b"WA_CODEX_CLI_VERSION_PIN=9.9.9\x00JUNK\n"
```

## 4. Behaviour preservation — ACCEPT-WITH-NOTES

The existing branches remain structurally unchanged:

- Missing env: exit 78, `env file missing`.
- Placeholder: exit 78, `env placeholders unfilled`.
- Kill switch: exit 0 and disabled heartbeat.
- Missing venv: exit 78.
- `cd` failure: exit 78.
- Heartbeat call sites remain.

With an invalid pin and `WA_CODEX_BROKER_ENABLED=false`, the result is exit 78 with `pin invalid`; the env is never sourced, so the kill switch is not observed. This changes operational precedence and may cause launchd relaunching until root fixes/removes the pin, but it is exactly the order D5 mandates and is acceptable as fail-closed behavior.

The inherited post-source name collisions described above remain regressions relative to the threat model, though not relative to main’s bytes.

## 5. Edge inputs — REWORK

Assuming the derived version path otherwise exists:

| Input | Outcome | Assessment |
|---|---|---|
| CRLF pin line | Fail-closed 78 | `\r` fails semver |
| Trailing space | Fail-closed 78 | Correct |
| UTF-8 BOM | Fail-closed 78 | Key is unrecognized |
| No final newline | Applied | Commonly reasonable, but “line” is being interpreted as a record rather than strictly POSIX newline-terminated text |
| `01.2.3` | Applied | Required checker permits leading zeroes despite the “exact semver” label |
| Pin file mode 000 | Fail-closed 78 | Reads fail, line count remains zero |
| `codex` is a mode-0755 directory | **Applied** | Defect: not a binary; should fail 78 |
| `codex` is a symlink to an executable | Applied | D5 does not prohibit this; safety depends on D1/D3 proving the resolved target is root-owned/non-writable |
| Valid line followed by an empty second line | Fail-closed 78 | Correct |

## 6. Tests and CI — REWORK

The test module collects exactly 17 cases. Against main it would go red because main lacks both patchable pin constants and the protocol line. That is discriminating at the suite level, although most tests fail in the patch helper before exercising a behavioral guilt case.

Important missing coverage:

- Same-line NUL that actually mutation-tests the NUL guard.
- DATA collisions for `VENV_PY`, `RUNTIME_DIR`, `TAG`, `SIDECAR_DIR`, and `ORGAN_ID`.
- Executable directory and executable symlink.
- Unreadable pin.
- Invalid pin plus kill switch.
- No-final-newline handling.
- Preservation of the old missing-env, placeholder, venv, `cd`, and kill-switch branches.
- Exact UTC timestamp shape; the current `\S+` regex accepts any token.

The workflow is syntactically valid: I ran `actionlint` successfully. It runs the test file on `macos-latest`, has no `continue-on-error`, and its path filter covers every relevant file in this PR. It is intentionally non-required, so failure will not itself block merging.

I did not complete the 17 tests: the read-only sandbox has no writable temporary directory, and pytest stopped before test execution. I did execute:

- `sh -n` and `bash -n`: passed.
- `actionlint`: passed.
- Pytest collection: 17 cases collected.
- Bash 3.2/dash NUL semantics and positional restoration experiments.
- HEAD verification: `08a5d93537201b9e93da88f6b2905c682e7f6830`.
- Final `git status --short`: clean.

### Meta-pattern

The repeated faulty belief is that protecting the newly introduced values protects the boundary. The pin values are preserved, but older control-plane names remain mutable; similarly, `-x` is treated as “executable file,” and a test that rejects one malformed NUL fixture is treated as proof of the NUL-specific guard.

### Solo-operatore

No operator action is needed for this review. After correction and independent verification, installing the root-owned live wrapper and proving the live log remains an operator/release-owner step.

OVERALL: REWORK