• Static review only; I did not execute the wrapper, tests, or workflow.

  **BLOCKER findings: none identified in the new D5 pin mechanism on the stated macOS `/bin/sh` = bash 3.2 POSIX-mode host.**  
  The highest-severity note is the pre-existing ability of a DATA-only env assignment to redirect `VENV_PY` or `RUNTIME_DIR`; that is not a regression from main, but it does make the spec’s broad “closes the stale-or-wrong-DATA class” claim overbroad.

  ## (1) D5 conformance

  **Verdict: ACCEPT-WITH-NOTES**

  The implementation conforms to D5 on the stated host:

  - The pin is parsed **before** `. "$ENV_FILE"`.
  - The pin parser itself uses shell built-ins and expansions: `[`, `read`, `case`, arithmetic expansion, and parameter expansion. It does not invoke `expr` or perform a PATH lookup for validation.
  - The earlier `grep` placeholder check is external, but it runs before the daemon env is sourced and is unchanged from main; the daemon env cannot influence it.
  - The binary path is derived only from:
    ```sh
    PINNED_CODEX_ROOT="/usr/local/lib/wa-codex-broker/codex"
    _wcbw_pin_bin="$PINNED_CODEX_ROOT/$_wcbw_pin_ver/bin/codex"
    ```
    No path string is read from the pin file.
  - Absence is distinguished from present-but-invalid:
    - `[ -L ]` catches symlinks, including dangling symlinks.
    - `[ -e ]` followed by `[ ! -f ]` catches directories, devices, FIFOs, sockets, and other non-regular objects before any attempt to open them.
    - Only true absence reaches the legacy branch.
  - Every identified present-but-invalid case reaches `exit 78` with:
    ```sh
    heartbeat "refused" "pin invalid"
    ```
  - `_is_semver` is textually equivalent to the mandated implementation.
  - The pinned handoff is semantically equivalent to the specified one:
    ```sh
    /usr/bin/env WA_CODEX_CLI_VERSION_PIN="$1" WA_CODEX_BIN="$2" "$VENV_PY" ...
    ```
    The explicit `env` assignments override inherited/exported daemon-env values.
  - Under a normal env file, the live-proof line has the required form:
    ```text
    wa-codex-broker-wrapper: <UTC timestamp> pin applied: codex <version> at <path>
    ```
    It is emitted immediately before the pinned `exec` and uses absolute `/bin/date`.
  - `# pin-protocol: wa-codex-pin/1` is present exactly once as a whole line.

  Notes:

  1. `read -d ''` is a Bash extension, not POSIX `read`. It is appropriate for the guaranteed target shell, but the wrapper should not be described as fully portable POSIX sh while using it. See (3).
  2. The live-proof prefix uses `$TAG` **after** sourcing the env. A DATA-only `TAG=...` assignment can therefore change or mangle the supposedly fixed proof prefix. This does not affect the pin values, but it weakens the “emitted exactly” guarantee.
  3. `_is_semver` accepts leading-zero components such as `01.2.3`. That is exactly what the mandated check does, but it is not strict SemVer 2.0. See (5).

  ## (2) Positional-parameter handoff and remaining named variables

  **Verdict: ACCEPT-WITH-NOTES**

  The positional-parameter handoff is sound in POSIX sh and in bash 3.2 POSIX mode.

  When `. "$ENV_FILE"` is invoked without explicit dot-command arguments, the sourced file inherits the current positional parameters. Ordinary shell data assignments do not replace them:

  - `KEY=value`
  - `KEY="quoted value"`
  - `export KEY=value`
  - blank lines
  - comments
  - CRLF line endings
  - `set -a` / `set +a`

  None of these alter `$1`, `$2`, `$#`, or the `[ -n "$1" ]` branch. A sourced file would have to execute something such as `set --`, `shift`, a function override, `exit`, or another command; that is beyond the stated DATA-only class and already constitutes shell execution as `zantara-codex`.

  The explicit pin arguments to `/usr/bin/env` are therefore safe from a DATA-only env collision.

  ### Remaining named-variable exposure

  The following are still assigned before the source and used afterward:

  - `VENV_PY`
    - A DATA-only assignment such as:
      ```sh
      VENV_PY=/opt/homebrew/bin/python3
      ```
      redirects the interpreter that receives the pinned `WA_CODEX_BIN`.
  - `RUNTIME_DIR`
    - Redirects `cd` and `PYTHONPATH`, and therefore can redirect Python module resolution.
  - `TAG`
    - Changes refusal and live-proof log prefixes.
  - `SIDECAR_DIR` and `ORGAN_ID`
    - Redirect or rename heartbeat output.
  - `PATH`
    - Does not affect the pin parser, but does affect post-source PATH-resolved `mkdir` and `date` inside `heartbeat`.
  - `IFS`
    - Can be reassigned, although the post-source expansions are quoted, so it does not appear to alter the pinned branch or exec words.

  This matters in an absolute reading of the threat model: a plain `VENV_PY` or `RUNTIME_DIR` assignment is DATA-only, needs no alias/function/command substitution, and can stop the bot or redirect execution. It does **not**, however, regress main: main already sourced the env before checking and execing `$VENV_PY`, and the specified D5 handoff itself continues to use `$VENV_PY`.

  I would not block this D5 delta on that pre-existing behavior, but the spec sentence “closes the stale or wrong env DATA class” should be narrowed, or a follow-up should snapshot/restore the wrapper-private constants after sourcing. The same applies to using literal post-source text for the live-proof prefix.

  ## (3) NUL probe

  **Verdict: ACCEPT-WITH-NOTES**

  For Bash, including the intended macOS bash 3.2 `/bin/sh` environment, the idiom:

  ```sh
  IFS= read -r -d '' _pin_nul_probe
  ```

  has the intended semantics: an empty `-d` argument selects NUL as the delimiter. `read` returns success when a NUL delimiter is encountered and failure when it reaches EOF without one. Thus success in the probe means the file contains a NUL.

  This is still a built-in and performs no PATH lookup, but it is **not POSIX `read`**.

  ### Dash

  The comment’s “bash/dash builtin extension” claim is not correct for dash: dash’s `read` does not generally support `-d`.

  If `/bin/sh` were dash, one of two bad outcomes would occur, depending on the exact dash error path:

  - the unsupported option is a fatal builtin syntax error and the script terminates; or
  - the command merely returns failure in the `if`, causing the NUL probe to be skipped.

  Either way, the intended byte-exact validation is lost. On the stated macOS host this does not occur because `/bin/sh` is bash 3.2 in POSIX mode, but the comment and portability claim should be corrected.

  ### Is the probe needed?

  Yes. The later line-count and semver checks operate on shell variables, and shell variables cannot represent NUL bytes.

  For example:

  ```text
  WA_CODEX_CLI_VERSION_PIN=9.9.9<NUL>JUNK\n
  ```

  Without a NUL probe, a shell read can store the valid-looking prefix `WA_CODEX_CLI_VERSION_PIN=9.9.9`, while the bytes after NUL are invisible to the variable. That could otherwise be counted as one valid line and pass semver. The probe is therefore necessary if “exactly one line” is intended to be byte-exact.

  The current test does not isolate this case; see (6).

  ## (4) Behaviour preservation versus main

  **Verdict: ACCEPT-WITH-NOTES**

  The existing behaviours are preserved:

  - Missing env file: unchanged `exit 78` and heartbeat.
  - `__FILL_ME__`: unchanged.
  - Pin absent: falls through to the same legacy env-sourced behaviour as main.
  - Kill switch:
    - pin absent and `WA_CODEX_BROKER_ENABLED=false`: still exits 0 and remains down.
    - valid pin and kill switch false: pin is parsed, then the env is sourced, then the wrapper exits 0 before exec.
  - Missing venv Python: unchanged check and refusal.
  - `cd` failure: unchanged.
  - Heartbeat calls remain in the expected paths.
  - The pinned `/usr/bin/env ... exec` replaces the wrapper process and ultimately execs the Python interpreter, so launchd still monitors the daemon process rather than a short-lived wrapper.

  ### Invalid pin plus kill switch

  A present-but-invalid pin wins over the kill switch:

  ```text
  pin invalid -> exit 78
  ```

  The kill switch is not read because the env has not yet been sourced. Under `KeepAlive.SuccessfulExit=false`, launchd will attempt to relaunch the nonzero exit, subject to launchd throttling.

  That is fail-closed and follows the specified ordering. Operationally, it means an operator cannot use the env-file kill switch to suppress a broken root-owned pin; root must repair/remove the pin or disable the job. I consider that acceptable for the stated fail-closed design, but it should be understood as intentional behaviour.

  One pre-existing caveat: after sourcing, `heartbeat` still invokes PATH-resolved `mkdir` and `date`. A hostile or broken DATA-only `PATH` can suppress or degrade those post-source heartbeat diagnostics. It does not redirect the pinned exec because `/usr/bin/env` and `/bin/date` for the live-proof line are absolute.

  ## (5) Edge inputs

  Assuming the corresponding pinned binary exists and is executable except where the question concerns the binary shape:

  | Input | Predicted result | Reason |
  |---|---|---|
  | CRLF pin line, `WA_CODEX_CLI_VERSION_PIN=1.2.3\r\n` | **Fail closed, 78** | The CR remains in the version and matches `*[!0-9.]*`. |
  | Trailing space after the version | **Fail closed, 78** | Space is rejected by `_is_semver`. |
  | UTF-8 BOM before the key | **Fail closed, 78** | The line no longer matches the literal `WA_CODEX_CLI_VERSION_PIN=*` prefix. |
  | No final newline | **Applied if otherwise valid** | The `while read ... || [ -n "$_pin_row" ]` idiom processes the final incomplete line. |
  | `01.2.3` | **Applied if binary exists** | The mandated case check accepts leading zeros. |
  | Pin file mode 000, unreadable by `zantara-codex` | **Fail closed, 78** | Metadata tests can succeed, but both reads fail; the line count remains zero. |
  | `<root>/<v>/bin/codex` is a directory, mode 0755 | **Accepted/applied** | Directories with search permission satisfy `[ -x ]`. The daemon later receives a directory in `WA_CODEX_BIN`. |
  | `<root>/<v>/bin/codex` is a symlink to an executable | **Accepted/applied** | `[ -x ]` follows the symlink. Only the pin file itself is required not to be a symlink. |
  | Valid pin line followed by an empty second line | **Fail closed, 78** | The loop counts two lines, including the empty line. |

  Two spec-intent concerns:

  1. **Leading zeros:** `01.2.3` is not strict SemVer 2.0, but the spec explicitly mandates this checker, so the implementation is conformant. The spec should call this “three numeric dot-separated fields” rather than “exact semver,” or tighten the checker.
  2. **Executable directory:** accepting a directory as the pinned “binary” is technically a consequence of the specified `[ -x ]` check. If “binary” means regular executable file, the wrapper should additionally require `[ -f "$PIN_BIN" ]`. That would go beyond the literal D5 text; alternatively, the root-owned installer/sentinel must enforce it.

  ## (6) Tests and CI

  **Verdict: ACCEPT-WITH-NOTES**

  There are 17 test instances:

  - 2 hostile-PATH cases
  - 10 invalid-pin cases
  - 1 positional-collision case
  - 2 innocence cases
  - 1 live-proof-line test
  - 1 protocol-line test

  ### Discrimination against main

  Yes, the suite would go red on main. Most runtime tests call `_base_wrapper()`, which attempts to patch `CODEX_PIN_FILE` and `PINNED_CODEX_ROOT`; main has neither assignment, so `_patched_wrapper()` fails its assertion. The protocol-line test also fails on main.

  That is partly structural rather than purely behavioural discrimination, but it is sufficient to prevent the new suite from silently passing against the old wrapper.

  ### Important untested cases

  The most important gap is the NUL fixture. The current case is:

  ```python
  b"WA_CODEX_CLI_VERSION_PIN=9.9.9\n\x00JUNK\n"
  ```

  That would likely fail from the two-line count even if the NUL probe were removed. It therefore does not prove that the probe is load-bearing.

  A discriminating case should put the NUL on the first line:

  ```python
  b"WA_CODEX_CLI_VERSION_PIN=9.9.9\x00JUNK\n"
  ```

  with `9.9.9` planted. Without the probe, this is the case that can collapse to a valid-looking shell variable.

  Other worthwhile missing cases:

  - CRLF
  - trailing whitespace
  - UTF-8 BOM
  - valid line with no final newline
  - leading-zero version
  - valid line followed by a blank line
  - unreadable mode-000 pin
  - pinned path being an executable directory
  - pinned path being a symlink to an executable
  - valid pin plus kill switch
  - invalid pin plus kill switch
  - DATA collisions for `VENV_PY`, `RUNTIME_DIR`, `TAG`, `SIDECAR_DIR`, and `ORGAN_ID`

  The tests should ideally invoke `/bin/sh` explicitly rather than PATH-resolved `"sh"` to make the target-shell guarantee unambiguous, although the macOS GitHub PATH should normally resolve it correctly.

  ### Workflow

  The workflow does run the tests:

  ```yaml
  sh -n ...
  bash -n ...
  python -m pytest scripts/tests/test_wa_codex_broker_wrapper.py -q
  ```

  It has no `continue-on-error`, so a test failure produces a red check. It runs on macOS, uses the actual wrapper file, and installs pytest.

  The `pull_request.paths` filter is adequate for this PR because it includes:

  - the wrapper
  - this test file
  - the workflow itself

  The future installer and sentinel paths are explicitly deferred to later PRs. The workflow is not a required context, so a red result is visible but does not itself block merging; that matches the stated non-required-check rationale.

  Minor CI note: installing unpinned latest `pytest` can eventually introduce an unrelated runner incompatibility with Python 3.11. Pinning or constraining pytest would improve reproducibility, but this is not a defect in the wrapper.

  OVERALL: ACCEPT-WITH-NOTES

