# Spec v3 — dedicated pinned codex for the WA broker (rework of PR #7340)

Status: SPEC, not code. Written 2026-09-26 against PR #7340 head `3d04590c99`
(`agent/air-m5/ops/wa-codex-pinned-installer`). Supersedes spec v2 for the listed surfaces;
everything v2 says that is not contradicted here still holds.

Committed 2026-09-27. Before that it existed only as a session scratch file, which a reboot
would have deleted. This copy keeps the scratch text for D1–D9, their amendments and the 3-PR
plan. It changes only what the three gates on PR #7420 (PR-1) proved wrong, and it adds:

- §5bis, the closed D5 inventory (condition S2 of the #7420 BLOCK);
- §5ter, the mutation check CI runs against it (S3);
- §5quater, the evidence-text fixes for the resumed build (S4).

§10 lists every change against the scratch text, each with the gate that proved it. The
normative inventory is the sidecar `docs/specs/2026-09-27-codexpin-v3-d5-inventory.yaml`.

Why v3: three BLOCKs for the same cause (privileged-installer hardening: #7313 r0, #7313 r1,
#7340 r0). Builder Contract §1 stops patch rounds. Every open finding below gets a design that
removes the whole class, not the reported instance. Owner decision (Zero): option (a), an
operator-run installer with the open findings fixed.

## 0. Inputs (checked on disk 2026-09-26, all present)

The `…/scratchpad/` paths below were session scratch on M5 and are not preserved. The PR
comments and the repository are the durable record.

| Input                                                                          | Present                                                  |
| ------------------------------------------------------------------------------ | -------------------------------------------------------- |
| `…/cefbda50…/scratchpad/spec_codexpin_v2.md`                                   | yes                                                      |
| `review_7313.md` + `review_7313_out.txt` (r0)                                  | yes                                                      |
| `review_7313_r2.md` + `review_7313_r2_out.txt` (r1)                            | yes                                                      |
| `review_7340.md` + `review_7340_out.txt` (#7340 r0)                            | yes                                                      |
| PR #7340 files at `3d04590c99` (installer, wrapper, 2 test files, chaos table) | yes                                                      |
| SUSPENDED comment on #7340 (7 open findings)                                   | yes (`gh pr view 7340 --json comments`)                  |
| `scripts/wa_codex_seat_sentinel.py`                                            | yes; **not modified** on the #7340 branch (0 diff lines) |

## 1. Threat model (explicit, and it drives every choice below)

- **Adversary A: `zantara-codex`.** It runs an LLM agent on untrusted WhatsApp text, so assume
  code execution as `zantara-codex`. It owns its env file (`0600`) and its home. It must never
  influence what root reads, writes or executes, and it must never be able to change the pinned
  tree it executes.
- **Adversary B: any other non-root account** except the operator's own interactive session.
- **Trusted but careless: the operator's checkout and sudo session.** On Pro the checkout is
  `~/nuzantara` (`~/Desktop/nuzantara` is a symlink to it, verified). Seats edit it, and
  `com.nuzantara.git-pull-main.15min` fast-forwards it every 15 minutes (loaded on Pro,
  verified). A malicious `nuzantara` is out of scope: it can already take the sudo password
  from shell rc files, so no installer design changes that. What IS in scope is carelessness:
  the file changing under a running `sudo bash`, or a stale checkout.
- **Out of scope, as in v2:** npm/OpenAI supply chain. The sha512 comes from the same registry,
  so it proves consistency, not independent approval. `/usr/bin`, `/bin`, `/usr/sbin` tools are
  on the sealed system volume and are not re-verified.

## 2. Non-goals (kept from v2, plus two)

NO sudoers drop-in, NO NOPASSWD, NO admin verbs, NO rollback machinery. Plus: the installer
**never runs `git`** (as root inside a user-owned repo, hooks/config are a code-exec channel),
and **never reads anything under `/Users/zantara-codex` as root** (the live proof in §6 reads
the daemon log AS `zantara-codex`, not as root).

## 3. Design, finding by finding

| #   | Finding (SUSPENDED list + new)                                                              | v3 design: the class it removes                                                                                                                |
| --- | ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| F1  | ancestor/ACL trust chain                                                                    | D1: walk the whole chain from the root, check every component, and prove by induction that nothing non-root can change it                      |
| F2  | `tar -tv` column parsing (space in uname)                                                   | D2: no field splitting anywhere. Types come from byte 1 of `-tv`, names from whole `-tf` lines, and both use the same libarchive that extracts |
| F3  | `-perm -022` lets 0664 through                                                              | D3: single-bit predicates only, plus no reuse path. A pre-existing tree is never trusted                                                       |
| F4  | substring version match                                                                     | D4: every version comparison is string equality with a value built from argv                                                                   |
| F5  | wrapper validation depends on PATH                                                          | D5: parse the pin with builtins only BEFORE the env is sourced, fail closed when the pin is present, hand off via absolute `/usr/bin/env`      |
| F6  | S10 proof gaps                                                                              | D6: restricted-shell execution proof with a mutant self-test, a macOS CI executor, and exact probe argv                                        |
| F7  | sentinel S9 text                                                                            | D7: the sentinel reads the world-readable pin, never blames Homebrew for a pinned daemon, and its cure names the installer                     |
| N1  | **new:** the #7340 tests run in NO gating workflow                                          | D6b: see D6                                                                                                                                    |
| N2  | **new:** bsdtar run as root restores ACLs/fflags/mac-metadata by default                    | D2 extraction flags                                                                                                                            |
| N3  | **new:** a stale or wrong wrapper source gets installed silently                            | D8: stage the wrapper copy and require the pin-protocol line on it                                                                             |
| N4  | **new:** bash reads the script incrementally, so a pull mid-run rewrites what root executes | D9: the whole body sits inside `main`, run as `main "$@"; exit $?`                                                                             |

### D1 — trust chain (F1)

`_verify_chain <path>` walks `${ROOT_PREFIX:-/}` then each component down to `<path>`, top-down.
It runs on `RUNTIME_DIR` (`/usr/local/lib/wa-codex-broker`) and on the parent of `WRAPPER_DST`
(`/usr/local/libexec`) BEFORE any side effect. It runs again on every directory the script
creates, right after creation. Each component must satisfy all of these:

- not a symlink (`[ -L ]` is lstat-based), and it is a directory;
- numeric ids come from `stat -f '%u:%g:%p'`. The output is only digits and colons, so no
  split ambiguity. Names (`%Su`) are never read;
- `uid == TRUST_UID` (0);
- `(( 8#mode & 8#0022 )) == 0`: nobody but the owner can write;
- `(( 8#mode & 8#0001 )) != 0`: others can traverse, so `zantara-codex` (groups: staff,
  everyone, localaccounts, _lpoperator, sharepoint; not wheel, verified on Pro) can reach the
  binary. This turns "the service account can reach it" into a mode fact that CI can test;
- no extended ACL: `find "$P" -maxdepth 0 -acl` prints nothing and exits 0. This rejects deny
  ACEs too (fail closed). Pro's chain carries none (verified);
- components this script owns (`RUNTIME_DIR`, `codex/`, `.staging.*`, `codex/<ver>/`)
  additionally need the exact triple `0:0:40755` (`TRUST_UID:TRUST_GID:40755`).

Why this closes the class: once a component is root-owned, not g/o-writable and ACL-free, only
root can rename, replace or create its entries. So the next component cannot be swapped after
it is verified. By induction the whole chain is fixed for the script's lifetime, and
check-then-use is safe without re-checking. Files the script writes (pin, wrapper) are written
as temp file + `rename` inside a verified directory. Afterwards each is asserted with the exact
triple (`0:0:100644` for the pin, `0:0:100755` for the wrapper) and no ACL. macOS `install(1)`
always writes `INS@XXXXXX` in the target directory and renames it (its man page says temporary
files are "no longer optional"), so the wrapper copy is atomic without `-S`.

Pro today (2026-09-26): `/`, `/usr`, `/usr/local`, `/usr/local/lib`,
`/usr/local/lib/wa-codex-broker` and `/usr/local/libexec` are all `0:0:40755`, with no ACL and
no symlink. `codex/` and `codex-pin.env` do not exist yet, so this is a first install.

### D2 — archive checks with no field parsing (F2, N2)

The checker and the extractor are the SAME parser: `/usr/bin/tar` (bsdtar 3.5.3 / libarchive
3.7.4 on both M5 and Pro). That removes parser-differential attacks by construction. There are
three independent gates. All run BEFORE any `chown`/`chmod` touches the tree.

1. **Listing gate.** `LC_ALL=C tar -tf TGZ > names` and `LC_ALL=C tar -tvf TGZ > long`.
   - Both exit 0 and both leave stderr EMPTY, so any libarchive warning rejects the archive.
   - `NR(names) == NR(long) >= 1`.
   - Every line of `long`: `substr($0,1,1)` is `-` or `d`. Only the first byte is read, never a
     column. That byte is the type (`l` symlink, `h` hardlink, `p` fifo, `c`/`b`/`s` are all
     rejected).
   - Every line of `names` matches the allowlist below as a whole line, and no component is
     `.` or `..`:
     ```
     ^package(/[A-Za-z0-9._+-]+)*/?$
     ```
     Under `LC_ALL=C`, bsdtar escapes every non-printable or high-bit byte and the backslash
     itself (`\n`, `\t`, `\\`, `\351`, `\033` were all observed). So every entry is exactly one
     line, and any escaped name fails the grammar, because `\` and whitespace are outside the
     alphabet.
2. **Extraction.** `tar -x --no-same-owner --no-same-permissions --no-acls --no-xattrs
--no-fflags --no-mac-metadata -f TGZ -C EXTRACT --strip-components=3
package/vendor/aarch64-apple-darwin`. Never `-P` or `-p`. The four `--no-*` flags are required
   because bsdtar(1) documents ACLs, fflags and mac-metadata as the DEFAULT "if tar is run in x
   mode as root". Exit 0 and empty stderr are both required.
3. **On-disk gate, before normalization.** A hardlink to an outside inode must be caught before
   `chmod -R` could loosen that inode. Exact predicate (the outer parentheses are
   load-bearing: without them `-print` binds only to the second alternative):
   ```
   find "$EXTRACT" \( \( ! -type f ! -type d \) -o \( -type f -links +1 \) \) -print
   ```
   The output must be empty.

Rejected alternatives, both measured:

- `tar --format=mtree -cf - @TGZ`: libarchive's mtree writer strips the leading `/`, collapses
  `//`, rewrites `./`, sorts entries and emits hardlinks as `type=file`. It hides exactly the
  anomalies we are looking for.
- Python `tarfile` via `/usr/bin/python3`: a second parser, with differential risk against
  libarchive. `/usr/bin/python3` is also only a Command Line Tools shim.

The real archive passes. `@openai/codex@0.156.1` resolves to 44 entries, all type `-`, all
names inside the grammar, a 132 MB tgz, and `bin/codex` after `--strip-components=3`.

### D3 — mode predicate, and no trusted pre-existing tree (F3)

- **Fresh only.** The v2/S6 reuse branch is deleted. Every run stages, verifies and swaps. If
  `codex/<ver>/` exists, `mv` it into `$_STAGING_DIR/replaced` (the EXIT trap deletes it), then
  `mv "$EXTRACT" "codex/<ver>"`. The window is two renames inside a root-only directory. No
  code path ever pins a tree this run did not just extract, gate and normalize. That removes the
  whole "trust a pre-existing tree through a predicate that can be wrong" class.
- **Normalize:** `chown -R TRUST_UID:TRUST_GID`, `chmod -R u=rwX,go=rX`, `chmod -R ug-s`,
  `chmod -R -N` (strip ACLs).
- **Assert, as a post-condition.** The predicate lives in `_assert_tree`, between the markers
  `# >>> _assert_tree` and `# <<< _assert_tree` (see D6). The output must be empty and find
  must exit 0:
  ```
  find "$T" \( \( ! -type f ! -type d \) -o ! -uid "$TRUST_UID" -o ! -gid "$TRUST_GID" \
      -o -perm -0020 -o -perm -0002 -o -perm -4000 -o -perm -2000 -o -perm -1000 \
      -o \( -type f -links +1 \) -o -acl \) -print
  ```
  Each `-perm -BIT` names exactly one bit, so "all of" and "any of" coincide. This form means
  the same thing in BSD and GNU find. Forbidden forms:
  - `-perm -022` requires BOTH bits (measured on M5: misses 0664 and 0646).
  - `-perm +022` is BSD "any of" and is rejected by GNU find.
  - `-perm /022` is GNU-only.
- **Immutable to its own executor.** The pinned tree is root-owned and not g/o-writable, and
  the daemon runs as `zantara-codex`. Even a codex build that tries to self-update cannot
  rewrite itself. This is the property that makes "NOTHING auto-upgrades it" true by
  construction, not by convention.

### D4 — exact version everywhere (F4)

Every comparison is `[ "$got" = "<literal built from VERSION>" ]`. No `case *"$want"*`, no
prefix glob, no host-prefix allowlist.

| Value                                                      | Must equal exactly                                                             |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------ |
| alias `optionalDependencies["@openai/codex-darwin-arm64"]` | `npm:@openai/codex@${VERSION}-darwin-arm64`                                    |
| `dist.tarball`                                             | `https://registry.npmjs.org/@openai/codex/-/codex-${VERSION}-darwin-arm64.tgz` |
| probe stdout (`$(...)`, trailing newline stripped)         | `codex-cli ${VERSION}`                                                         |
| pin file content                                           | `WA_CODEX_CLI_VERSION_PIN=${VERSION}\n` (one line; see D5)                     |

All shapes were verified live on 2026-09-26 for 0.156.1: the alias, the tarball URL, and the
probe bytes `codex-cli 0.156.1\n`. The installer's accept condition is strictly narrower than
the daemon's (`_SEMVER_RE` first-token equality in `wa_codex_daemon.py`), because
`codex-cli` contains no digit. So installer-accept implies daemon-accept.

The #7340 test fixture uses an unrealistic registry shape
(`npm:@openai/codex-darwin-arm64@9.9.8`, `…/codex-darwin-arm64-9.9.8.tgz`). The v3 fixture
mirrors the real one.

### D5 — wrapper applies the pin with builtins only (F5)

Order in `wa-codex-broker-wrapper.sh`: env-file presence and placeholder checks (unchanged),
then **pin parse (new position)**, then `. "$ENV_FILE"`, then the kill switch and venv checks,
then exec.

- **Pin parse, before the env exists in the shell.** Use only `read`, `case`, `[` and parameter
  expansion. No `expr`, no PATH lookup, so nothing the env file contains can reach it.
  - Pin file absent: legacy behaviour, and log
    `wa-codex-broker-wrapper: no pin file at <path> — codex from the daemon env (legacy)`.
  - Pin file present: it must be a regular file (not a symlink) with EXACTLY one line,
    `WA_CODEX_CLI_VERSION_PIN=<v>`, where `<v>` passes the check below.
  - **Line grammar (amended 2026-09-27, #7420 re-gate #2 D10/D25/D26).** The pin's bytes are
    read with `IFS=` and `-r`. There is no whitespace trimming and no backslash processing, so
    `…=9.9.9 ` (trailing space), a leading tab and `…=9.9.\9` all fail. Both flags are
    requirements, not style. A line is a run of bytes ended by LF, or a non-empty final run
    with no LF. The loop's `|| [ -n "$_pin_row" ]` conjunct counts that final run. Decision:
    - a single line with no final LF is ACCEPTED;
    - `…=1.1.1\n…=9.9.9` (no final LF) is TWO lines and is REFUSED.

    The installer still writes the final LF (D4). The sentinel (D7, PR-3) must apply the same
    line rule, so that the two readers of the pin never disagree.

  - **NUL (amended, spalla review 2026-09-26 and r0 C1).** A NUL byte anywhere refuses (`78`,
    `pin file contains a NUL byte`). The probe is `IFS= read -r -d '' _ < pin`, whose status
    is 0 only when a NUL delimiter comes before EOF. `read -d` is a **bash** builtin option,
    and dash rejects it. The wrapper runs only as macOS `/bin/sh`, which is bash 3.2.57 in
    POSIX mode, so tests must invoke `/bin/sh` explicitly (r0 N2). `-r` is load-bearing in the
    probe too. Without it, a backslash escapes the NUL delimiter (G1b in §5bis).
  - **Check order (as implemented at `04dd6b51e4`):**
    1. `RUNTIME_DIR` searchable;
    2. `-L`;
    3. `-e`;
    4. `! -f`;
    5. `! -r`;
    6. NUL;
    7. line count;
    8. key;
    9. semver;
    10. derived binary.

    Every refusal prints exactly ONE line to stderr, `wa-codex-broker-wrapper: <reason>…`,
    writes `heartbeat refused "pin invalid"` and exits `78`. The reason texts are part of the
    contract (§5bis.4), because each fixture proves which guard refused by asserting its reason.

  - The binary path is DERIVED, never read: `PIN_BIN="$PINNED_CODEX_ROOT/$v/bin/codex"`, with
    the literal constant `PINNED_CODEX_ROOT="/usr/local/lib/wa-codex-broker/codex"`. There is
    no path to validate, so there is no path validator to get wrong.
  - `[ -f "$PIN_BIN" ] && [ -x "$PIN_BIN" ]` must hold (a directory is `-x` too — amended
    2026-09-26 per gate-7420 C2).
  - A pin path that exists but cannot be searched or read (EACCES on the pin directory or file)
    is PRESENT-BUT-INVALID → `exit 78` `pin invalid`, never "absent → legacy" (gate-7420 C3).
    **Implemented rule (amended 2026-09-27):**
    - `RUNTIME_DIR` exists but is not searchable (`[ -d ] && [ ! -x ]`): refuse with
      `pin directory not searchable`.
    - `RUNTIME_DIR` does not exist at all: this is "nothing installed", so the wrapper logs
      legacy and continues. In production the venv check (`VENV_PY` lives under
      `RUNTIME_DIR`) then refuses, and in the test layout `cd` refuses.
    - The pin file exists but is unreadable: refuse with `pin file is not readable` (r0 N4).
    - A searchable `RUNTIME_DIR` under an unsearchable ANCESTOR still reads as absent. See §8
      item 7.
  - Any violation (bad or unknown or duplicate line, bad semver, missing binary, symlinked or
    non-regular pin) means `exit 78` plus `heartbeat refused "pin invalid"`. Fail closed:
    legacy applies ONLY when the file is absent.
- The semver check is exactly this, a POSIX `case`:

  ```sh
  _is_semver() {
      case $1 in
          *[!0-9.]*|.*|*.|*..*|*.*.*.*) return 1 ;;
          *.*.*) return 0 ;;
      esac
      return 1
  }
  ```

  What it accepts is **three non-empty fields of ASCII digits joined by dots**. Leading zeros
  are allowed (`09.9.9` passes). It is not full SemVer: there are no pre-release or build
  suffixes (wording amended per the r0 spec-owner note). Two points about its alternatives:
  - each of the five reject alternatives is the ONLY one that rejects its own witness:
    `a.b.c`, `.1.2`, `1.2.`, `1..2`, `1.2.3.4`;
  - traversal (`../x`) is rejected redundantly by `*[!0-9.]*`, `.*` and `*..*`.

  The text sits between `# >>> _is_semver` / `# <<< _is_semver` markers (r0 N6), so PR-2 can
  extract it.

- **Handoff after sourcing (amended 2026-09-27: positional, not named).** The scratch text
  carried the resolved pin in named variables (`PIN_VER`/`PIN_BIN`). A plain `KEY=value` line
  in the daemon env redefines any named variable once `set -a` exports it (spalla review
  2026-09-26, reproduced; r0 judged the positional form sound). So the resolved pair crosses
  the source as positional parameters:
  ```sh
  set -- "$_wcbw_pin_ver" "$_wcbw_pin_bin"     # right before: set -a; . "$ENV_FILE"; set +a
  …
  if [ -n "$1" ]; then
      echo "$TAG: $(/bin/date -u +%Y-%m-%dT%H:%M:%SZ) pin applied: codex $1 at $2" >&2
      exec /usr/bin/env WA_CODEX_CLI_VERSION_PIN="$1" WA_CODEX_BIN="$2" "$VENV_PY" -m backend.services.integrations.wa_codex_daemon
  fi
  exec "$VENV_PY" -m backend.services.integrations.wa_codex_daemon
  ```
  The absolute `env` plus explicit assignments win over anything the env file exported. Just
  before the exec, log
  `wa-codex-broker-wrapper: <UTC ts via /bin/date> pin applied: codex <v> at <PIN_BIN>`. This
  is the live-proof line in §6.
- **Post-source re-assert (added 2026-09-27, r0 N1).** Right after `set +a` the wrapper
  re-assigns its six private literals: `HOME_DIR`, `RUNTIME_DIR`, `VENV_PY`, `TAG`, `ORGAN_ID`
  and `SIDECAR_DIR`. It then exports `PYTHONPATH="$RUNTIME_DIR"`, so a DATA line in the env can
  redirect neither the exec, the `cd`, the heartbeat, the proof-line prefix nor the daemon's
  import path.
- **Kill-switch precedence (added 2026-09-27, r0 N3).** An invalid pin exits `78` before the
  env is read. `WA_CODEX_BROKER_ENABLED=false` therefore cannot stop the relaunch loop that a
  broken root-owned pin causes. To stop it, repair or remove the pin as root, or run
  `launchctl bootout system/com.balizero.wa-codex-broker`.
- **Protocol line** (for D8), exactly as a whole line: `# pin-protocol: wa-codex-pin/1`.
- The pin file format changes from v2's two keys to ONE key. #7340 never reached main or Pro,
  so nothing migrates.
- **Scope, stated honestly (narrowed 2026-09-27 per the r0 spec-owner note).** This closes the
  stale or wrong env DATA class for:
  - the pin values;
  - the six re-asserted private names;
  - `PYTHONPATH`.

  It does not cover other names the daemon itself reads (`WA_*`, `CODEX_HOME`), which are the
  env's to set. For example, `PATH=/opt/homebrew/bin:/usr/bin` in the env breaks the #7340
  validators, because `expr` is `/bin/expr` on macOS (verified). It does not and cannot close
  a MALICIOUS env file: sourcing it is already code execution as `zantara-codex` (aliases,
  `readonly`, function overrides). The security boundary is the root-owned tree and pin that
  `zantara-codex` cannot write, not the wrapper. See §8.

### D6 — proofs that prove what they claim (F6, N1)

- **"Zero external commands before the argv gate", enforced by the kernel and the shell rather
  than read from a trace:**

  ```
  env -i PATH=<empty tmp dir> /bin/bash -r scripts/install_wa_codex_pinned.sh <bad argv>
  ```

  Pass condition: rc == 2, stdout == "", stderr == exactly one `usage:` line. Restricted mode
  refuses any command containing `/`, output redirection to a file, `command -p` and `exec`.
  With an empty PATH, every bare name is "command not found". Each attempt leaves a diagnostic,
  so the exact-output equality catches it, and nothing can actually execute during the test.
  Measured on M5 (bash 3.2.57) with mutants inserted after `set -euo pipefail` into a copy of
  the #7340 head:

  | Mutant                                    | Detected by                      |
  | ----------------------------------------- | -------------------------------- |
  | `/usr/bin/true`                           | "restricted: cannot specify `/`" |
  | `: "$(/usr/bin/true)"`                    | "restricted: cannot specify `/`" |
  | `tar --version >/dev/null 2>&1 \|\| true` | "cannot redirect output"         |
  | `D="$(dirname "$0")"`                     | "command not found", rc 127      |
  | `command -p true`                         | "restricted"                     |
  | `exec 2>/dev/null`                        | "restricted"                     |

  The unmodified head gives rc 2 and usage only. The #7340 trace-regex detector
  (`^\+\s+/(usr|bin|sbin)`) misses the `$(...)` (`++`) and bare-name forms (r0 review,
  reproduced).

- **Real function text, no test mode.** `_verify_chain`, `_check_listing` and `_assert_tree`
  sit between `# >>> name` / `# <<< name` markers in the shipped script. Tests extract the
  text and run it under `bash -c` with the constants set. This tests the shipped predicate,
  not a copy pasted into the test file. That was a #7340 gap: its wrapper tests re-typed the
  `expr` validators instead of exercising the shipped text. Pipeline tests keep the #7340
  mechanism: `sed`-patch the constants of a COPY (`ROOT_PREFIX`, `TRUST_UID`, `TRUST_GID`,
  `BROKER_USER`, `WRAPPER_SRC`, `*_BIN`). There is no env or flag test mode.
- **Probe identity.** The sudo stub records its argv, and a test asserts it equals exactly
  `-u zantara-codex -H /usr/bin/env -i <abs staged bin> --version`. Reachability is proven by
  D1's `o+x` rule. The actual identity switch is proven only on Pro (§8).
- **Ownership predicate in CI without root.** Move the EXPECTED side: patch `TRUST_UID` or
  `TRUST_GID` to a value that differs from the runner's. The same `! -uid` / `! -gid`
  predicate must fire. Also chgrp one file to a secondary group of the runner.
- **N1, a CI executor.** Today no workflow names `test_install_wa_codex_pinned.py`,
  `test_wa_codex_broker_wrapper.py` or `test_wa_codex_seat_sentinel.py`. Their only runner is
  the nightly `scripts-tests-sweep.yml` on `ubuntu-latest` with `continue-on-error: true`,
  where BSD `stat -f`, `plutil`, `find -acl` and bsdtar do not exist. The fix is a new
  `.github/workflows/wa-codex-pin.yml`:
  - `runs-on: macos-latest`, checkout with `filter: blob:none` (repo convention for the 10x
    runner);
  - `pull_request` path filter on the 3 scripts, the 3 tests and the workflow itself, plus
    `workflow_dispatch`;
  - `python -m pytest <the three files> -q`, NOT continue-on-error;
  - no `sudo` anywhere.

  It is not a required context, following the `alarm-cure-alignment.yml` reasoning. It is an
  executor that CAN go red.

  **Amended 2026-09-27:**
  - Re-gate #1 R1: the PR that adds the workflow also adds its `name:` to
    `main-push-failure-watch.yml` `on.workflow_run.workflows`. Otherwise `Watcher coverage`
    turns main red at merge.
  - r0 N7: each later PR (PR-2, PR-3) extends BOTH `paths:` and the pytest argv.
  - PR-1 also runs the S3 mutation check (§5ter) in the same workflow and pins `pytest` and
    `pyyaml` by exact version.

### D7 — sentinel (F7)

`scripts/wa_codex_seat_sentinel.py` reads `/usr/local/lib/wa-codex-broker/codex-pin.env`
(root-owned 0644, readable without sudo) as data, with the same one-line grammar. The path is
overridable by env for tests, the same pattern as `WA_CODEX_HOMEBREW_PACKAGE_JSON`.
"Same grammar" is exact (amended 2026-09-27), and PR-3 pins each point with a fixture:

- bytes are taken as-is, with no strip;
- a final line without LF counts as a line;
- NUL, a second line, a missing key or a non-matching `<v>` means "pin invalid", never "no pin".

- **Valid pin:** `_pin_drift_message` never names Homebrew drift. A pinned daemon does not
  execute the Homebrew codex. It returns `DAEMON_SILENT_MSG` + ` — codex is pinned at <v>
(dedicated binary); Homebrew drift is not a cause`. `AUTH_DEATH_MSG` names
  `/usr/local/lib/wa-codex-broker/codex/<v>/bin/codex login` instead of `/opt/homebrew/bin/codex`.
- **No pin:** the cure text is exactly `sudo bash scripts/install_wa_codex_pinned.sh
<pkg_version>` (on Pro, from `~/nuzantara`). It never suggests `sed` on the daemon env.
- Every tick prints one line `codex pin: <v> (dedicated)` or `codex pin: none (legacy)`. That
  gives a live observation that does not wait for an outage.

### D8 — wrapper source staging and protocol coupling (N3)

In preflight, before any download:

- refuse if `WRAPPER_SRC` is a symlink or not a regular file;
- copy it ONCE into staging (`$_STAGING_DIR/wrapper.sh`);
- on that copy, require the exact whole line `# pin-protocol: wa-codex-pin/1` (the installer
  constant `PIN_PROTOCOL`).

Later, `install -o 0 -g 0 -m 0755` FROM THE STAGED COPY. What gets checked is what gets
installed. A stale checkout (wrapper without pin support) is refused before 132 MB are
downloaded. A future pin-format change must bump both sides, or the installer refuses.

### D9 — whole-body parse (N4)

The script body is `main() { … }`, followed by exactly the last line `main "$@"; exit $?`. Bash
parses the whole function before running any of it, so a pull that rewrites the file mid-run
changes nothing. S1 still holds: the argv gate is main's first statement, builtins only.
Measured on bash 3.2: a top-level script that appends `touch marker` to itself runs the
appended line; the `main "$@"; exit $?` form does not.

## 4. Installer end-state invariants (what the tests and the operator run must observe)

1. With bad argv, nothing external runs, rc is 2, output is usage only. The gate is D9's first
   statement.
2. The chains `/…/wa-codex-broker` and `/…/libexec` are verified before any write. Dirs the
   script owns are exactly `0:0:40755`.
3. The archive passes all three D2 gates before any metadata change. Otherwise the run exits 1
   with `archive rejected: <gate>: <line>`, and `codex/<ver>` and the pin are untouched.
4. `codex/<ver>/` is always this run's tree. It passes `_assert_tree`, and the probe run as
   `zantara-codex` prints exactly `codex-cli <ver>`.
5. The pin file is exactly `WA_CODEX_CLI_VERSION_PIN=<ver>\n`, `0:0:100644`, no ACL.
6. The wrapper is the staged copy, `0:0:100755`, no ACL, and carries the protocol line.
7. `launchctl kickstart -k system/com.balizero.wa-codex-broker`, then the state line is printed.
   The kickstart kills any in-flight job, which converges as chaos row 5 (lease TTL plus one
   reaper pass).
8. The EXIT trap removes staging, including any replaced tree. Leftover `.staging.*` from a
   SIGKILLed run are root-owned, inert and not auto-pruned. Old `codex/<ver>` trees (~330 MB
   each) are not pruned either (no rollback or cleanup machinery). Pruning is a manual operator
   `sudo rm -rf` of non-pinned versions.

## 5. Acceptance: falsifiable guilt and innocence tests

Every test below runs as non-root on `macos-latest` via `wa-codex-pin.yml`. The "#7340 head"
column is what the SAME assertion does against the `3d04590c99` code. Each finding has at least
one row that is RED on the head and GREEN on v3.

`scripts/tests/test_install_wa_codex_pinned.py` (rewritten):

| Test                                                                                                                      | Finding | Setup                                                                                              | #7340 head                                                                     | v3                                                                                                                                                                                                                                                                                             |
| ------------------------------------------------------------------------------------------------------------------------- | ------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_guilt_chain_refuses_before_any_download[ancestor_group_writable]`                                                   | F1      | `ROOT_PREFIX/usr/local` 0775                                                                       | proceeds to curl: RED                                                          | exit 1, "chain", curl log absent                                                                                                                                                                                                                                                               |
| `…[ancestor_acl]`                                                                                                         | F1      | `chmod +a "everyone allow add_file,add_subdirectory,delete_child"` on `ROOT_PREFIX/usr/local/lib`  | RED                                                                            | refused                                                                                                                                                                                                                                                                                        |
| `…[ancestor_symlink]`                                                                                                     | F1      | `usr/local/lib` → symlink to a real dir                                                            | RED (the head only lstats the leaf)                                            | refused                                                                                                                                                                                                                                                                                        |
| `…[libexec_other_writable]`                                                                                               | F1      | `usr/local/libexec` 0777                                                                           | RED (never checked)                                                            | refused                                                                                                                                                                                                                                                                                        |
| `…[runtime_not_other_traversable]`                                                                                        | F1      | `RUNTIME_DIR` 0750                                                                                 | RED (`750 & 022 == 0`, passthrough-sudo probe succeeds)                        | refused                                                                                                                                                                                                                                                                                        |
| `test_innocence_chain_ok_reaches_download`                                                                                | F1      | whole scratch chain 0755, no ACL                                                                   | —                                                                              | reaches the curl stub                                                                                                                                                                                                                                                                          |
| `test_guilt_listing_rejects[uname_space_dotdot]`                                                                          | F2      | entry `../review-probe`, uname `evil user`                                                         | awk takes column 9 → accepted, install rc 0: RED (reproduced on M5 2026-09-26) | exit 1 "archive rejected", no `codex/9.9.9`, no pin                                                                                                                                                                                                                                            |
| `…[uname_space_absolute]`                                                                                                 | F2      | `/etc/review-probe`, uname `evil user`                                                             | RED                                                                            | rejected                                                                                                                                                                                                                                                                                       |
| `…[name_space]` / `[name_newline]` / `[name_backslash]` / `[dot_slash]` / `[double_slash]` / `[outside_package]`          | F2      | one entry each                                                                                     | RED (names unrestricted)                                                       | rejected                                                                                                                                                                                                                                                                                       |
| `…[symlink_20k_trailing]` / `[hardlink]` / `[hardlink_abs_target]` / `[fifo]`                                             | F2      | as #7340 plus fifo                                                                                 | green (kept as regression pins)                                                | rejected                                                                                                                                                                                                                                                                                       |
| `test_innocence_listing_real_shape_44_regular_files`                                                                      | F2      | fixture mirroring the real 0.156.1 layout                                                          | —                                                                              | accepted                                                                                                                                                                                                                                                                                       |
| `test_extract_argv_disables_every_metadata_channel`                                                                       | N2      | `TAR_BIN` → logging passthrough to `/usr/bin/tar`                                                  | RED (no `--no-acls/--no-xattrs/--no-fflags/--no-mac-metadata`)                 | the four flags present, no `-P` or `-p`                                                                                                                                                                                                                                                        |
| `test_guilt_preexisting_version_dir_is_never_trusted`                                                                     | F3      | plant `codex/9.9.9/bin/codex` (fake, prints `codex-cli 9.9.9`) + `planted` 0664                    | reuse passes `-perm -022`, fake pinned: RED                                    | fake replaced by tarball bytes, `planted` gone, pin → fresh tree                                                                                                                                                                                                                               |
| `test_assert_tree_rejects[0664,0646,0620,0602,4755,2755,1755dir,acl,fifo,hardlink,foreign_uid,foreign_gid,secondary_gid]` | F3      | marker-extracted `_assert_tree` on a hand-built dir; `foreign_*` = patched `TRUST_UID`/`TRUST_GID` | n/a (no function on head)                                                      | each prints the offending path                                                                                                                                                                                                                                                                 |
| `test_assert_tree_mutant_all_of_perm_is_blind`                                                                            | F3      | same harness, predicate text rewritten to `-perm -022`                                             | —                                                                              | the mutant ACCEPTS 0664 and 0646 (proves the fixture discriminates)                                                                                                                                                                                                                            |
| `test_guilt_probe_version_must_match_exactly`                                                                             | F4      | fixture codex prints `codex-cli 9.9.90` for 9.9.9                                                  | substring match, rc 0: RED (r0 reproduced)                                     | exit 1 "does not report exactly"                                                                                                                                                                                                                                                               |
| `test_guilt_metadata_must_match_exactly[alias,tarball_url]`                                                               | F4      | alias `…@9.9.90-darwin-arm64`; URL of another version                                              | no exact check: follows the other version's metadata/URL                       | exit 1 "not exactly", before the tarball download                                                                                                                                                                                                                                              |
| `test_guilt_argv_gate_runs_nothing_external[[], 1.2, 1.2.3.4, 1.2.3;id, v1.2.3, "1.2.3 extra"]`                           | F6      | D6 restricted-shell run of the SHIPPED file                                                        | —                                                                              | rc 2, stdout empty, stderr == usage                                                                                                                                                                                                                                                            |
| `test_argv_detector_catches_mutant[abs,cmdsub,bare_redirect,dirname,command_p,exec_redirect]`                             | F6      | mutant copies of the shipped script                                                                | the #7340 detector passes `cmdsub` and `bare`: RED                             | each mutant fails the D6 condition                                                                                                                                                                                                                                                             |
| `test_guilt_script_rewritten_mid_run_cannot_inject`                                                                       | N4      | curl stub appends `touch $MARKER` to the running copy                                              | marker created: RED                                                            | marker absent                                                                                                                                                                                                                                                                                  |
| `test_probe_requested_as_service_account_with_empty_env`                                                                  | F6      | sudo stub records argv                                                                             | —                                                                              | argv equals D6 exactly                                                                                                                                                                                                                                                                         |
| `test_guilt_wrapper_source_without_pin_protocol_refused[main_wrapper,symlink_src]`                                        | N3      | `WRAPPER_SRC` = main's wrapper / a symlink                                                         | installs it, rc 0: RED                                                         | exit 1 before download                                                                                                                                                                                                                                                                         |
| `test_semver_validators_agree`                                                                                            | F4/F5   | marker-extracted installer `[[ =~ ]]` gate and wrapper `_is_semver` over one corpus                | —                                                                              | identical verdict on every case, AND the expected verdict per case (amended 2026-09-27, re-gate #2 §2): accept `1.2.3`, `0.156.1`, `09.9.9`; reject `a.b.c`, `.1.2`, `1.2.`, `1..2`, `1.2.3.4`, `9.9`, `../x`, empty, `1.2.3-rc1`. Agreement alone would pass two identically wrong validators |
| `test_innocence_full_pipeline_fresh_install`                                                                              | all     | realistic fixture                                                                                  | —                                                                              | exact triples for dirs, pin, wrapper; pin content exact; kickstart logged                                                                                                                                                                                                                      |
| `test_innocence_rerun_same_version_swaps_fresh`                                                                           | F3      | run twice                                                                                          | —                                                                              | second tree is new (inode differs), staging empty after exit                                                                                                                                                                                                                                   |

`scripts/tests/test_wa_codex_broker_wrapper.py` (rewritten). Patchable constants: `HOME_DIR`,
`RUNTIME_DIR`, `VENV_PY`, `CODEX_PIN_FILE`, `PINNED_CODEX_ROOT`.

**Superseded for PR-1 by §5bis (amended 2026-09-27).** The table below is the scratch
original, kept for history. Three gates on PR #7420 proved that this sample, and every
hand-written extension of it, missed guards: r0 found 3 deletable guards, re-gate #1 found 2
and re-gate #2 found 1 conjunct plus 2 read flags. The wrapper's acceptance is now the closed
inventory (§5bis) and the S3 run over it (§5ter).

| Test                                                                                                         | Finding | Setup                                                                                         | #7340 head                                                  | v3                                                            |
| ------------------------------------------------------------------------------------------------------------ | ------- | --------------------------------------------------------------------------------------------- | ----------------------------------------------------------- | ------------------------------------------------------------- |
| `test_guilt_env_path_cannot_disable_the_pin[nonexistent,homebrew_usr_bin]`                                   | F5      | env `PATH=/does-not-exist` / `PATH=/opt/homebrew/bin:/usr/bin`, valid pin, pinned bin present | `expr` not found, the daemon gets env's `WA_CODEX_BIN`: RED | daemon env has the derived pinned bin and version             |
| `test_guilt_present_but_invalid_pin_refuses[bad_semver,unknown_key,two_lines,empty,bin_missing,symlink_pin]` | F5      | one fault each                                                                                | silently legacy, rc 0: RED                                  | rc 78, heartbeat `refused`                                    |
| `test_innocence_valid_pin_overrides_env`                                                                     | F5      | env sets a Homebrew bin and pin 0.0.1                                                         | —                                                           | pinned values reach the stub                                  |
| `test_innocence_missing_pin_is_legacy`                                                                       | F5      | no pin file                                                                                   | green                                                       | env values, "legacy" log line                                 |
| `test_pin_applied_log_line`                                                                                  | §6      | valid pin                                                                                     | —                                                           | stderr carries the exact `pin applied: codex 9.9.9 at …` line |
| `test_wrapper_declares_pin_protocol_line`                                                                    | N3      | read the shipped file                                                                         | RED (no line)                                               | exactly one matching line                                     |

`scripts/tests/test_wa_codex_seat_sentinel.py` (extended):

| Test                                                    | Finding | #7340 head                   | v3                                                                           |
| ------------------------------------------------------- | ------- | ---------------------------- | ---------------------------------------------------------------------------- |
| `test_guilt_pin_drift_cure_names_the_pinned_installer`  | F7      | cure is `sudo sed -i …`: RED | contains `sudo bash scripts/install_wa_codex_pinned.sh 0.156.1`, no `sed -i` |
| `test_innocence_pinned_daemon_never_blamed_on_homebrew` | F7      | RED (blames Homebrew)        | plain wording + "pinned at"                                                  |
| `test_auth_death_names_the_pinned_binary_when_pinned`   | F7      | RED                          | the pinned path is named                                                     |
| `test_tick_reports_pin_state[pinned,none]`              | F7      | RED                          | exact line                                                                   |

Existing sentinel tests that pin the `sed -i` text are updated in the same PR, because their
assertion is the finding.

Recorded limit of the D6 detector: an attempt that deliberately closes its own fds
(`>&- 2>&-`) leaves no diagnostic. Under the test it still cannot EXECUTE (empty PATH plus
restricted mode). The production control for that form is D9 + S1 (the gate is main's first
statement) plus review.

## 5bis. Closed D5 inventory (S2 of the #7420 BLOCK, added 2026-09-27)

### 5bis.1 Why a closed inventory

The same cause produced three gate findings in a row, on the same surface (the PR #7420
wrapper):

| Gate                           | Head         | Guard deletable with the suite still green                                                                                  | Mechanism                                                                                                                |
| ------------------------------ | ------------ | --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| r0 (comment 5847376532)        | `08a5d93537` | NUL probe, exactly-one-line, `_is_semver` (17/17 green each)                                                                | negative fixtures never planted the binary, so the later `-x` check caught every fault first                             |
| re-gate #1 (5848624798)        | `737d16224a` | key `case`; the `-x` half of `-f && -x` (26/26 green)                                                                       | `unknown_key` also fails `_is_semver`; C2 put `-f` in front of `-x`, which removed `-x`'s only discriminating fixture    |
| re-gate #2 (5848838838, BLOCK) | `04dd6b51e4` | `\|\| [ -n "$_pin_row" ]` (28/28 green); also read flags `IFS=`/`-r`, `_is_semver` alternatives S1–S5, C3's `[ -d ]`, P1–P5 | nothing isolated them. Every table was written by hand (the builder's twice, one gate's once) and each missed a conjunct |

Two root causes, each with its own cure:

1. **Masking.** A fixture that claims to test guard X is satisfied by a later guard Y. This
   happens because the tests assert only `rc 78` plus `refused`/`pin invalid`, and every refusal
   produces exactly that. Cure: the fixture contract (5bis.4). Every negative fixture asserts
   the ONE diagnostic line of the guard it isolates, so a masked mutant shows a different
   reason (or two lines, or none) and dies.
2. **Enumeration by hand.** Nobody derived the tables from the file, so every table missed
   something. Cure: a site grammar (5bis.3) that a script extracts mechanically, with closure.
   Every extracted site must belong to exactly one inventory row, or CI fails (§5ter).

### 5bis.2 Format: a YAML sidecar, normative

The inventory is `docs/specs/2026-09-27-codexpin-v3-d5-inventory.yaml`, schema
`wa-codex-wrapper-inventory/1`. It is YAML for four reasons:

- **Anchors need exact text.** The anchors are exact wrapper lines, and they contain `|`,
  `||`, `"`, `'` and `$`. A markdown table cannot be the machine source, because `|` is its
  cell separator and escaping it changes the very text to be matched. JSON would need `\"` in
  almost every anchor.
- **Block scalars need no escaping.** A YAML block scalar written `|2-` carries a line
  verbatim. The explicit indentation indicator `2` is mandatory. Measured: with plain `|-`,
  PyYAML stripped every indented anchor of its own leading spaces.
- **The toolchain already exists.** The repo already parses YAML with PyYAML in CI
  (`catE-sovereignty-lint.yml`, `craft-instruments-daily.yml`), and `wa-codex-pin.yml`
  installs it at a pinned version.
- **It is a spec artifact.** The file sits next to the spec, not next to the test. A
  disposition or a mode is a spec decision, and changing one should read as a spec change in
  review.

The table in 5bis.6 is a rendering of the YAML, and S3 checks that the two agree (§5ter.3
step 9). The YAML header documents the row fields. Row ids in families 1–5 keep the builder's
labels, so the #7420 pack stays readable:

- G1 = NUL probe;
- G2 = exactly one line;
- G3 = semver;
- G4a = symlink, G4b = key;
- G5, G5a, G5b = binary.

The `was` field maps every earlier label: builder `G*`, gate `C*`/`N*`/`R*`, and re-gate #2
`D01`–`D26`, `S1`–`S7`, `P1`–`P6`.

### 5bis.3 Site grammar: what "every guard" means, mechanically

A site is one occurrence, on a code line of the target, of one of the 12 kinds below. Comment
lines and blank lines have no sites. Before matching, the line is masked: the contents of
`'…'` and `"…"` are blanked, so words inside messages never count, and a `#` that follows
whitespace outside quotes starts a comment.

| Kind       | Matches (on the masked line unless stated)                                                                                                              | Sites at `04dd6b51e4` |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------- |
| `cond`     | each `if`, `elif`, `while` or `until` keyword in command position                                                                                       | 15                    |
| `test`     | each `[` test command: a `[` preceded by line start or one of `\s ; & \| ! (` and followed by whitespace. Glob brackets such as `*[!0-9.]*` never match | 14                    |
| `andor`    | each `&&` and each `\|\|`                                                                                                                               | 5                     |
| `alt`      | inside `case … esac`, each `\|`-separated alternative of an arm's pattern (`pattern)` at line start)                                                    | 8                     |
| `readopt`  | per `read` command: the `IFS=…` prefix if present, plus each option word (`-d ''` counts as one)                                                        | 5                     |
| `default`  | on the raw line: each `${NAME:-…}`, `${NAME-…}`, `${NAME:=…}`, `${NAME=…}`, `${NAME:?…}`, `${NAME?…}`, `${NAME:+…}` or `${NAME+…}`                      | 1                     |
| `exit`     | each `exit` or `return` in command position                                                                                                             | 18                    |
| `hb`       | each `heartbeat` call (not its definition)                                                                                                              | 15                    |
| `diag`     | each `echo` or `printf` on a line that redirects `>&2`                                                                                                  | 15                    |
| `exec`     | each `exec`                                                                                                                                             | 2                     |
| `setopt`   | each line that is `set -…` or `set +…`, including `set --`                                                                                              | 4                     |
| `reassert` | each top-level `NAME=` or `export NAME=` after the `. "$ENV_FILE"` line                                                                                 | 7                     |
| **total**  |                                                                                                                                                         | **109**               |

A site's key is `(line, kind)`. When one line carries several sites of the same kind, they
are keyed `kind#1`, `kind#2`, … in textual order. For example, line 134 has `test#1`
(`[ -d … ]`) and `test#2` (`[ ! -x … ]`).

These are deliberately not sites:

- **Constants and initialisations before the source** (`HOME_DIR=…`, `_wcbw_pin_ver=""`,
  `_pin_lines=0`). Deleting one either crashes under `set -u` on every run, which any
  innocence test catches, or matters only when launchd hands the process a hostile
  environment. The plist is root-owned, and root is trusted (§1).
- **The derivation and the prefix strip** (`_wcbw_pin_bin="$PINNED_CODEX_ROOT/…"` and
  `${_pin_line#…}`). Deleting either breaks every valid pin. They are data flow, not guards.
- **The rest:** `. "$ENV_FILE"`, `cd` on its own, and the `printf` that writes the heartbeat
  file.

**Closure rule.** The set of extracted sites must equal the set of claimed sites, and no site
may be claimed twice. A row claims the sites in its `covers` list, on its anchor line, plus the
site on each line that its `stmt` mutants resolve to. Anything new in the wrapper that matches
a kind (a new `[ … ]`, `&&`, case alternative, read flag, `${…:-…}`, `exit`, heartbeat,
diagnostic or re-assert) is an UNCLAIMED site. CI fails until a row claims it. That is what
"closed" means here: a guard added later without a row is a spec violation, and the check
itself reports it.

Measured on the `04dd6b51e4` wrapper with a scratch prototype of the extractor:

- it found exactly 109 sites, and every one was claimed;
- planting five constructs produced 11 UNCLAIMED sites, one per planted site. The constructs
  were an `if [ -s ] && [ -O ]` guard with `exit 3`, a `read -r -n 1`, a `${_z:=q}`, a
  two-alternative `case`, and a post-source `FOO_EXTRA=1`.

**Mutation operators.** Each site kind has a fixed operator, so no one invents mutants per row:

| Site                                                | Mutant(s)                                                                                                                                     |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| refusal guard (an `if` whose block ends in `exit`)  | the condition becomes `false`; inside the block, `exit` → `:`, `heartbeat` → `:` and `echo` → `:`                                             |
| conjunct, disjunct or `\|\|` limb                   | drop that operand together with its operator                                                                                                  |
| selection branch (`elif [ -e ]`, `if [ -n "$1" ]`)  | condition → `true`, and condition → `false`                                                                                                   |
| `while` condition                                   | → `false`                                                                                                                                     |
| case alternative                                    | drop the alternative. A single-alternative accept arm is widened to `*`. The catch-all reject arm is neutralised to `__wcbw_never_matches__)` |
| `return` in the predicate                           | flip `0`↔`1`. Dropping it is equivalent by construction, because the fall-through is `return 1`                                               |
| `readopt`                                           | drop the flag                                                                                                                                 |
| `default`                                           | drop the default (`${X:-true}` → `${X}`)                                                                                                      |
| `setopt`, `reassert`, a lone `hb`, `diag` or `exec` | the statement becomes `:`                                                                                                                     |
| the pinned `exec`                                   | plain `exec "$VENV_PY" …`, and separately `/usr/bin/env` → a PATH-resolved `env`                                                              |

A `stmt` mutant writes `:` instead of deleting the line, so a block never becomes empty. Re-gate
#2's first D23 variant was syntax-broken and counted as a false kill.

### 5bis.4 Fixture contract: the cure for masking

Every test that runs the wrapper asserts one of these two contracts, never less.

**Contract N (refusal).**

1. `rc` equals the row's code: `78`, or `0` for the kill switch.
2. The heartbeat file carries the expected `status` and `note`.
3. Exactly ONE stderr line starts with `wa-codex-broker-wrapper: `, and it contains the
   guard's reason text.
4. The stub did not run (stdout is empty).

**Contract P (start).**

1. `rc == 0`.
2. The stub reports exactly the expected `WA_CODEX_CLI_VERSION_PIN`, `WA_CODEX_BIN` and
   `PYTHONPATH`.
3. Exactly one tagged stderr line: `pin applied: codex <v> at <bin>`, or
   `no pin file at <path> — … (legacy)`.
4. The heartbeat reads `starting` / `exec daemon`. The exception is the two hostile-PATH tests,
   where the PATH-resolved `mkdir`/`date` inside `heartbeat()` is a known pre-existing gap
   (§8 item 6).

N.3 is the clause that kills masking:

- a deleted guard lets its fixture reach a later guard, which prints a different reason;
- a deleted `exit` makes the run fall into a second refusal (two lines) or into the exec
  (`rc 0`);
- a deleted diagnostic leaves zero lines.

Only tagged lines are asserted. Shell error text such as `cd: …` varies with the bash version
and is not the wrapper's contract.

Reason texts are asserted as substrings. They come from the wrapper at `04dd6b51e4`:

- `env file missing`
- `__FILL_ME__ placeholders`
- `pin directory not searchable`
- `pin file is a symlink`
- `pin file is not a regular file`
- `pin file is not readable`
- `pin file contains a NUL byte`
- `pin file must carry exactly one line`
- `pin file has an unrecognized line`
- `pin version is not exact semver`
- `pinned binary missing, not a regular file, or not executable`
- `kill switch active`
- `venv python missing or not executable`

The `cd` refusal has no tagged line of its own. Its fixture asserts the legacy line plus the
heartbeat note `cd failed`.

Fixture rules, one carried over and two new:

- **Plant what the fault would otherwise resolve to** (r0 C1). A negative fixture plants the
  binary tree its version would resolve to, unless the missing tree IS the fault
  (`bin_missing`).
- **Hostile values must exist** (new). When a test proves a re-assert (N1), the env's hostile
  `RUNTIME_DIR`, `VENV_PY` and `HOME_DIR` point at EXISTING alternatives: an executable decoy
  and real directories. The test then asserts that the decoy did not run. A nonexistent
  hostile path turns a fail-open mutant into a crash, and the measured mode then understates
  the risk. Measured: G8b and G8c read `fail-closed-other-rc` with nonexistent paths and
  `fail-open` with real ones.
- **The stub reports `PYTHONPATH`** (new). `_DUMP_ENV_STUB` prints it alongside the two pin
  values.

### 5bis.5 Dispositions, and the decisions re-gate #2 asked for

There are only two dispositions.

- **MUST.** Every mutant of the row must be killed, by at least one of its `killed_by` tests.
- **EQUIVALENT.** No contracted observation can distinguish the mutant, and the row carries a
  `reason`. S3 still runs it. If a test kills it, S3 FAILS: a killed "equivalent" mutant is a
  refuted claim, and the row must become MUST with that test as its killer.

**No row is deferred.** Re-gate #2 allowed deferring `_is_semver`'s corpus to PR-2, and it
called P1–P5 out of scope. Both are MUST in PR-1 instead, for three reasons:

- S3 runs only the wrapper's own test file. A MUST row whose killer lived in PR-2's installer
  tests would leave the wrapper's check red, or silently exempt, until PR-2 merged.
- Each row needs one small fixture (5bis.7). Re-gate #2's probes already showed that S1–S5 fail
  open when deleted: `a.b.c`, `.1.2`, `1.2.`, `1..2` and `1.2.3.4` were each APPLIED with the
  tree planted.
- Deleting P3 (the kill switch) fails open on the operator's own stop control. Deleting P2
  starts the daemon on a placeholder env.

PR-2's `test_semver_validators_agree` still asserts the same corpus for the installer side
(§5, amended).

| Item                          | Decision                                                                                                                                                        | Row                          | Isolating fixture(s)                                                                                                                                                 |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D10 `\|\| [ -n "$_pin_row" ]` | MUST. Keep the conjunct; the wrapper logic does not change. A single line without a final LF is accepted. Two lines whose last line is unterminated are refused | G2a                          | `[two_lines_last_unterminated_planted]` (without the conjunct it fails open and applies `1.1.1`), plus `test_innocence_single_line_without_trailing_newline_applies` |
| D25 `IFS=` (loop)             | MUST: exact bytes, no trimming                                                                                                                                  | G2b                          | `[trailing_space_planted]`, `[leading_tab_planted]`                                                                                                                  |
| D26 `-r` (loop)               | MUST: no backslash processing                                                                                                                                   | G2c                          | `[backslash_in_version_planted]` (`…=9.9.\9` would otherwise apply `9.9.9`)                                                                                          |
| D02 `[ -d "$RUNTIME_DIR" ]`   | MUST, via the diagnosis: an absent `RUNTIME_DIR` means "nothing installed" (the legacy line), not "pin invalid"                                                 | G6a                          | `test_runtime_dir_absent_is_legacy_then_cd_refuses`                                                                                                                  |
| S1–S5                         | MUST in PR-1 (reasons above)                                                                                                                                    | G3a–G3e                      | `[semver_alpha_planted]`, `[semver_leading_dot_planted]`, `[semver_trailing_dot_planted]`, `[semver_empty_field_planted]`, `[semver_four_fields_planted]`            |
| P1–P6                         | MUST in PR-1                                                                                                                                                    | G9c, G9d, G9e, G9g, G9h, G9i | 5bis.7                                                                                                                                                               |

There are three EQUIVALENT rows:

- **G1c** (`IFS=` in the NUL probe). `read`'s status depends only on whether the delimiter
  comes before EOF. IFS shapes only the stored value, and that value is never read.
- **G7c** (`set +a`). Its only effect is that the six re-asserted names are exported to the
  daemon too. `wa_codex_daemon.py` reads only `WA_*` and `CODEX_HOME`.
- **G9b** (`mkdir … || return 0` in `heartbeat`). There is no errexit, and every caller
  ignores the status, so rc and control flow are identical. The only difference is one extra
  shell error line when the sidecar directory cannot be created, and no contract pins that
  line's absence.

### 5bis.6 The inventory (rendered from the YAML)

Mode codes (the exact classification rule is §5ter.3 step 8):

- **FO**, fail-open: the daemon starts where the shipped wrapper refuses, or starts with a
  different binary, version or `PYTHONPATH`.
- **FC**, fail-closed-other-rc: a legitimate start is blocked, or the refusal's rc changes.
- **DX**, same-rc-other-diagnosis: same rc, but a different heartbeat or tagged line.
- **EQ**, equivalent.

Mutant suffixes: `c` condition, `d` diagnostic, `h` heartbeat, `x` exit. Line numbers are
those of blob `4143a795d9`.

<!-- d5-inventory:begin -->

| ID  | was                  | line    | expression                                                     | covers          | mutants (mode)         | disposition | killed by                                                                                                |
| --- | -------------------- | ------- | -------------------------------------------------------------- | --------------- | ---------------------- | ----------- | -------------------------------------------------------------------------------------------------------- |
| G1  | builder G1, D09      | 171–174 | `whole guard: if <NUL probe>; then … exit 78`                  | cond            | c FO, d DX, h DX, x FO | MUST        | `[nul_same_line_planted]`                                                                                |
| G1a | new                  | 171     | `-d ''`                                                        | readopt#3       | -d FC                  | MUST        | `test_innocence_valid_pin_overrides_env`                                                                 |
| G1b | new                  | 171     | `-r (probe)`                                                   | readopt#2       | -r DX                  | MUST        | `[nul_after_backslash_planted]`                                                                          |
| G1c | new                  | 171     | `IFS= (probe)`                                                 | readopt#1       | IFS EQ                 | EQUIVALENT  | — (none, see reason)                                                                                     |
| G2  | builder G2, D11      | 182–185 | `if [ "$_pin_lines" -ne 1 ]; then`                             | cond, test      | c FO, d DX, h DX, x FO | MUST        | `[two_lines_diff_versions_planted]`                                                                      |
| G2a | D10                  | 178     | `\|\| [ -n "$_pin_row" ]`                                      | andor, test     | limb FO                | MUST        | `[two_lines_last_unterminated_planted]`, `test_innocence_single_line_without_trailing_newline_applies`   |
| G2b | D25                  | 178     | `IFS= (loop)`                                                  | readopt#1       | IFS FO                 | MUST        | `[trailing_space_planted]`, `[leading_tab_planted]`                                                      |
| G2c | D26                  | 178     | `-r (loop)`                                                    | readopt#2       | -r FO                  | MUST        | `[backslash_in_version_planted]`                                                                         |
| G2d | new                  | 178     | `while <read loop>`                                            | cond            | c FC                   | MUST        | `test_innocence_valid_pin_overrides_env`                                                                 |
| G3  | builder G3, D13      | 197–200 | `if ! _is_semver "$_wcbw_pin_ver"; then`                       | cond            | c FO, d DX, h DX, x FO | MUST        | `[bad_semver_planted]`, `[traversal_escape_planted]`                                                     |
| G3a | S1                   | 84      | `*[!0-9.]*`                                                    | alt#1           | alt FO                 | MUST        | `[semver_alpha_planted]`                                                                                 |
| G3b | S2                   | 84      | `.*`                                                           | alt#2           | alt FO                 | MUST        | `[semver_leading_dot_planted]`                                                                           |
| G3c | S3                   | 84      | `*.`                                                           | alt#3           | alt FO                 | MUST        | `[semver_trailing_dot_planted]`                                                                          |
| G3d | S4                   | 84      | `*..*`                                                         | alt#4           | alt FO                 | MUST        | `[semver_empty_field_planted]`                                                                           |
| G3e | S5                   | 84      | `*.*.*.*`                                                      | alt#5           | alt FO                 | MUST        | `[semver_four_fields_planted]`                                                                           |
| G3f | new                  | 84      | `return 1 (reject arm)`                                        | exit            | flip FO                | MUST        | `[traversal_escape_planted]`, `[semver_alpha_planted]`                                                   |
| G3g | S6                   | 85      | `*.*.*) return 0 ;;`                                           | alt, exit       | widen FO, flip FC      | MUST        | `[bad_semver_planted]`, `test_innocence_valid_pin_overrides_env`                                         |
| G3h | S7                   | 87      | `return 1`                                                     | exit            | flip FO                | MUST        | `[bad_semver_planted]`                                                                                   |
| G4a | builder G4a, D04     | 142–145 | `if [ -L "$CODEX_PIN_FILE" ]; then`                            | cond, test      | c FO, d DX, h DX, x FO | MUST        | `[symlink_pin]`                                                                                          |
| G4b | builder G4b, D12     | 188     | `WA_CODEX_CLI_VERSION_PIN=*)`                                  | alt             | widen FO               | MUST        | `[bare_version_planted]`                                                                                 |
| G4c | new                  | 191–194 | `*)`                                                           | alt             | c DX, d DX, h DX, x DX | MUST        | `[bare_version_planted]`, `[unknown_key]`                                                                |
| G4d | D05                  | 146     | `elif [ -e "$CODEX_PIN_FILE" ]; then`                          | cond, test      | true FC, false FO      | MUST        | `test_innocence_missing_pin_is_legacy`, `test_innocence_valid_pin_overrides_env`, `[bad_semver_planted]` |
| G4e | D06                  | 147–150 | `if [ ! -f "$CODEX_PIN_FILE" ]; then`                          | cond, test      | c FC, d DX, h DX, x FC | MUST        | `[directory]`, `[dev_null]`                                                                              |
| G4f | N4, D08              | 152–155 | `if [ ! -r "$CODEX_PIN_FILE" ]; then`                          | cond, test      | c DX, d DX, h DX, x DX | MUST        | `test_guilt_mode_000_pin_reports_unreadable_not_line_count`                                              |
| G5  | builder G5, D14      | 206–209 | `whole guard: if ! -f \|\| ! -x; then … exit 78`               | cond            | c FO, d DX, h DX, x FO | MUST        | `[bin_missing]`                                                                                          |
| G5a | builder G5a, C2, D15 | 206     | `[ ! -f "$_wcbw_pin_bin" ]`                                    | test#1          | -f FO                  | MUST        | `[bin_is_directory]`                                                                                     |
| G5b | builder G5b, R3, D16 | 206     | `\|\| [ ! -x "$_wcbw_pin_bin" ]`                               | test#2, andor   | -x FO                  | MUST        | `[bin_not_executable_planted]`                                                                           |
| G6  | C3, D01              | 134–137 | `whole guard: if -d && ! -x; then … exit 78`                   | cond            | c DX, d DX, h DX, x DX | MUST        | `test_guilt_unsearchable_runtime_dir_refuses_not_legacy`                                                 |
| G6a | D02                  | 134     | `[ -d "$RUNTIME_DIR" ] &&`                                     | test#1          | -d DX                  | MUST        | `test_runtime_dir_absent_is_legacy_then_cd_refuses`                                                      |
| G6b | D03                  | 134     | `&& [ ! -x "$RUNTIME_DIR" ]`                                   | test#2, andor   | -x FC                  | MUST        | `test_innocence_valid_pin_overrides_env`                                                                 |
| G7a | D21                  | 218     | `set -- "$_wcbw_pin_ver" "$_wcbw_pin_bin"`                     | setopt          | stmt FC                | MUST        | `test_innocence_valid_pin_overrides_env`                                                                 |
| G7b | new                  | 220     | `set -a`                                                       | setopt          | stmt FO                | MUST        | `test_innocence_missing_pin_is_legacy`                                                                   |
| G7c | new                  | 222     | `set +a`                                                       | setopt          | stmt EQ                | EQUIVALENT  | — (none, see reason)                                                                                     |
| G7d | D22                  | 268     | `if [ -n "$1" ]; then`                                         | cond, test      | false FO, true FO      | MUST        | `test_innocence_valid_pin_overrides_env`, `test_innocence_missing_pin_is_legacy`                         |
| G7e | D24                  | 269     | `echo "$TAG: $(/bin/date -u +%Y-%m-%dT%H:%M:%SZ) pin appli…`   | diag            | stmt DX                | MUST        | `test_pin_applied_log_line`                                                                              |
| G7f | D19, D20             | 270     | `exec /usr/bin/env WA_CODEX_CLI_VERSION_PIN="$1" WA_CODEX_…`   | exec            | plain FO, path-env FC  | MUST        | `test_innocence_valid_pin_overrides_env`, `test_guilt_env_path_cannot_disable_the_pin[nonexistent]`      |
| G7g | new                  | 273     | `exec "$VENV_PY" -m backend.services.integrations.wa_codex…`   | exec            | stmt FC                | MUST        | `test_innocence_missing_pin_is_legacy`                                                                   |
| G7h | D23                  | 212     | `echo "$TAG: no pin file at $CODEX_PIN_FILE — codex from t…`   | diag            | stmt DX                | MUST        | `test_innocence_missing_pin_is_legacy`                                                                   |
| G8a | N1, D17a             | 231     | `HOME_DIR="/Users/zantara-codex"`                              | reassert        | stmt DX                | MUST        | `test_guilt_env_cannot_clobber_post_source_literals`                                                     |
| G8b | N1, D17b             | 232     | `RUNTIME_DIR="/usr/local/lib/wa-codex-broker"`                 | reassert        | stmt FO                | MUST        | `test_guilt_env_cannot_clobber_post_source_literals`                                                     |
| G8c | N1, D17c             | 233     | `VENV_PY="$RUNTIME_DIR/.venv/bin/python3"`                     | reassert        | stmt FO                | MUST        | `test_guilt_env_cannot_clobber_post_source_literals`                                                     |
| G8d | N1, D17d             | 234     | `TAG="wa-codex-broker-wrapper"`                                | reassert        | stmt DX                | MUST        | `test_guilt_env_cannot_clobber_post_source_literals`                                                     |
| G8e | N1, D17e             | 235     | `ORGAN_ID="pro.wa_codex_broker"`                               | reassert        | stmt DX                | MUST        | `test_guilt_env_cannot_clobber_post_source_literals`                                                     |
| G8f | N1, D17f             | 236     | `SIDECAR_DIR="$HOME_DIR/.organism/last_seen"`                  | reassert        | stmt DX                | MUST        | `test_guilt_env_cannot_clobber_post_source_literals`                                                     |
| G8g | new                  | 264     | `export PYTHONPATH="$RUNTIME_DIR"`                             | reassert        | stmt FO                | MUST        | `test_guilt_env_cannot_clobber_pythonpath`                                                               |
| G9a | new                  | 47      | `set -u`                                                       | setopt          | stmt FO                | MUST        | `test_guilt_env_undefined_name_never_execs`                                                              |
| G9b | new                  | 72      | `mkdir -p "$SIDECAR_DIR" 2>/dev/null \|\| return 0`            | andor, exit     | limb EQ                | EQUIVALENT  | — (none, see reason)                                                                                     |
| G9c | P1                   | 91–94   | `if [ ! -f "$ENV_FILE" ]; then`                                | cond, test      | c FC, d DX, h DX, x FC | MUST        | `test_guilt_env_file_missing_refuses`                                                                    |
| G9d | P2                   | 96–99   | `if grep -q "__FILL_ME__" "$ENV_FILE"; then`                   | cond            | c FO, d DX, h DX, x FO | MUST        | `test_guilt_env_placeholders_refuse`                                                                     |
| G9e | P3                   | 251–254 | `whole guard: kill switch … exit 0`                            | cond, test      | c FO, d DX, h DX, x FO | MUST        | `test_kill_switch_stops_without_exec`                                                                    |
| G9f | new                  | 251     | `${WA_CODEX_BROKER_ENABLED:-true}`                             | default         | default FC             | MUST        | `test_innocence_env_without_kill_switch_key_applies`                                                     |
| G9g | P4                   | 257–260 | `if [ ! -x "$VENV_PY" ]; then`                                 | cond, test      | c FC, d DX, h DX, x FC | MUST        | `test_guilt_venv_missing_refuses`                                                                        |
| G9h | P5                   | 263     | `cd "$RUNTIME_DIR" \|\| { heartbeat "refused" "cd failed"; e…` | andor, hb, exit | limb FO, h DX, x FO    | MUST        | `test_runtime_dir_absent_is_legacy_then_cd_refuses`                                                      |
| G9i | P6                   | 266     | `heartbeat "starting" "exec daemon"`                           | hb              | stmt DX                | MUST        | `test_guilt_env_cannot_clobber_post_source_literals`                                                     |

<!-- d5-inventory:end -->

Totals: 54 rows (51 MUST, 3 EQUIVALENT), 109 sites, 99 mutants (96 MUST, 3 EQUIVALENT).
Declared modes: 39 FO, 15 FC, 42 DX, 3 EQ.

### 5bis.7 Fixtures that PR-1 adds or changes

New. N and P refer to the contracts in 5bis.4:

| Test or param id                                                                                                                                          | Row(s)   | Shape                                                                                            | Expected                                                                                                                                      |
| --------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `[nul_after_backslash_planted]`                                                                                                                           | G1b      | bytes `WA_CODEX_CLI_VERSION_PIN=9.9.9\`, NUL, `JUNK`, LF; `9.9.9` planted                        | N: `pin file contains a NUL byte`                                                                                                             |
| `[two_lines_last_unterminated_planted]`                                                                                                                   | G2a      | `…=1.1.1` LF `…=9.9.9`, no final LF; both planted                                                | N: `must carry exactly one line`                                                                                                              |
| `[trailing_space_planted]`                                                                                                                                | G2b      | `…=9.9.9 ` LF; planted                                                                           | N: `not exact semver`                                                                                                                         |
| `[leading_tab_planted]`                                                                                                                                   | G2b      | TAB `…=9.9.9` LF; planted                                                                        | N: `unrecognized line`                                                                                                                        |
| `[backslash_in_version_planted]`                                                                                                                          | G2c      | `…=9.9.\9` LF; `9.9.9` planted                                                                   | N: `not exact semver`                                                                                                                         |
| `[semver_alpha_planted]`, `[semver_leading_dot_planted]`, `[semver_trailing_dot_planted]`, `[semver_empty_field_planted]`, `[semver_four_fields_planted]` | G3a–G3e  | `a.b.c`, `.1.2`, `1.2.`, `1..2`, `1.2.3.4`, each planted at its own derived path                 | N: `not exact semver`                                                                                                                         |
| `test_innocence_single_line_without_trailing_newline_applies`                                                                                             | G2a      | `…=9.9.9` with no LF; planted                                                                    | P: applied `9.9.9`                                                                                                                            |
| `test_guilt_env_cannot_clobber_pythonpath`                                                                                                                | G8g      | env `PYTHONPATH=/nonexistent-evil-pythonpath`; valid pin                                         | P, and the stub's `PYTHONPATH` equals the wrapper's `RUNTIME_DIR`                                                                             |
| `test_guilt_env_undefined_name_never_execs`                                                                                                               | G9a      | env line `WA_CODEX_MODEL=$WA_CODEX_UNDEFINED_FOR_TEST`; valid pin                                | `rc != 0`, the stub did not run, no `starting` heartbeat. This pins today's `set -u` stop; a later 78-plus-heartbeat refusal would still pass |
| `test_guilt_env_file_missing_refuses`                                                                                                                     | G9c      | no env file, no pin                                                                              | N: heartbeat note `env file missing`, reason `env file missing`                                                                               |
| `test_guilt_env_placeholders_refuse`                                                                                                                      | G9d      | env `WA_BROKER_KEY=__FILL_ME__`                                                                  | N: heartbeat note `env placeholders unfilled`, reason `__FILL_ME__ placeholders`                                                              |
| `test_kill_switch_stops_without_exec`                                                                                                                     | G9e      | env `WA_CODEX_BROKER_ENABLED=false`; valid pin planted                                           | N with rc 0: heartbeat `disabled`/`kill switch`, reason `kill switch active`                                                                  |
| `test_innocence_env_without_kill_switch_key_applies`                                                                                                      | G9f      | env without `WA_CODEX_BROKER_ENABLED`; valid pin                                                 | P                                                                                                                                             |
| `test_guilt_venv_missing_refuses`                                                                                                                         | G9g      | `VENV_PY` patched to a missing path; valid pin                                                   | N: heartbeat note `venv python missing`, reason `venv python missing or not executable`                                                       |
| `test_runtime_dir_absent_is_legacy_then_cd_refuses`                                                                                                       | G6a, G9h | `RUNTIME_DIR` patched to a path that does not exist; no pin; the stub `VENV_PY` lives outside it | rc 78, heartbeat `refused`/`cd failed`, exactly one tagged line (the legacy line), the stub did not run                                       |

Changed:

- `test_guilt_present_but_invalid_pin_refuses` is parametrised by `(kind, reason)` and asserts
  contract N. `unknown_key`, `two_lines` and `embedded_nul` now plant `9.9.9` (the r0 C1 rule).
- `test_guilt_mode_000_pin_reports_unreadable_not_line_count` asserts contract N, which adds
  the heartbeat check and kills G4f/h.
- `test_guilt_unsearchable_runtime_dir_refuses_not_legacy` and
  `test_guilt_invalid_pin_beats_the_kill_switch` assert contract N.
- `test_guilt_env_cannot_clobber_post_source_literals` uses existing hostile values (5bis.4).
  It asserts that the decoy did not run, that `PYTHONPATH` is the wrapper's own, and that
  nothing landed in the decoy sidecar.
- Every positive test asserts contract P.
- `_DUMP_ENV_STUB` prints `PYTHONPATH`, and `_run` gains the `WCBW_RUN_LOG` hook (5ter.2).

### 5bis.8 What the `04dd6b51e4` suite kills today (measured 2026-09-27)

Setup: a scratch prototype of §5ter (not the implementation), on M5 with bash 3.2.57,
against the 28-test suite at `04dd6b51e4`.

Results:

- the baseline passed 28 of 28;
- of the 99 mutants, 54 were killed and 45 survived: 42 MUST plus the 3 EQUIVALENT;
- every killed MUST mutant was killed by a test in its `killed_by` list.

Surviving MUST mutants, by row. **Named by re-gate #2:**

- G2a (D10), G2b (D25), G2c (D26) and G6a (D02);
- G3a–G3e (S1–S5);
- G9c, G9d, G9e, G9g and G9h (P1–P5), every mutant of each.

**In no earlier table:**

- G1b (the probe's `-r`);
- the diagnostic-drop mutants of G1, G2, G3, G4a, G4e and G5 (no test asserts a reason);
- G4c, the key case's catch-all arm (its neutralised, diagnostic and exit mutants);
- G4f/h (the mode-000 test never reads the heartbeat);
- G8g (`export PYTHONPATH`);
- G9a (`set -u`);
- G9f (the kill switch's `:-true` default; every test sets the key).

**Feasibility.** A scratch suite of 47 tests applied 5bis.4 and 5bis.7 to the unchanged
wrapper:

- the baseline passed 47 of 47;
- all 96 MUST mutants were killed, each by a test in its `killed_by` list;
- the 3 EQUIVALENT mutants survived;
- no mutant failed `sh -n`;
- every declared mode equalled the measured one;
- the 99 mutants took about 3 minutes of wall time on M5.

The scratch suite shows that the contract can be satisfied. It is not the PR-1 test file; the
resumed build writes that.

## 5ter. S3 — the committed mutation check (added 2026-09-27)

The script is `scripts/ci/wa_codex_wrapper_mutants.py`. It ships in the resumed PR-1 together
with its selftest and runs in `wa-codex-pin.yml`. It is generic over the inventory: the
target file, the test files and the rows all come from the YAML. PR-2 therefore adds an
installer inventory, not a second script. Where the installer uses syntax outside the 12 site
kinds (`[[ … ]]`, `find` predicate terms, `awk` programs), PR-2 extends the grammar in the
same PR, together with guilt and innocence selftests for the new kinds.

### 5ter.1 Interface

```
python scripts/ci/wa_codex_wrapper_mutants.py [--inventory PATH] [--spec PATH]
    [--receipt-dir DIR] [--only ID ...] [--selftest] [--render-table]
```

- `--inventory` defaults to `docs/specs/2026-09-27-codexpin-v3-d5-inventory.yaml`.
- `--spec` names a markdown file whose `d5-inventory` block must equal `--render-table`.
- `--receipt-dir` is where the JSON and markdown receipt go. In CI it is
  `$RUNNER_TEMP/wcbw-mutants`, uploaded as an artifact.
- `--only` is for local debugging. A run with `--only` never counts as the CI verdict, and its
  receipt says so.
- Exit codes: `0` when every check passes; `1` for any verdict failure; `2` for a usage or
  infrastructure error (invalid YAML, red baseline, pytest crash). CI treats both non-zero
  codes as red. There is no `continue-on-error`.

### 5ter.2 Isolation

- **The checkout is never written.** The script builds a temp tree that holds only the target
  and the test files, at their repo-relative paths (the test file finds the wrapper through
  `Path(__file__).parents[2]`). It writes each mutant into that tree and deletes the tree at
  exit. The gate harnesses mutated a worktree in place and restored it by copy. That is
  harmless in CI, but locally it is the `git checkout --` hazard the repo already has a scar
  for.
- **pytest settings.** pytest runs with `cwd=<temp tree>`, `-q -p no:cacheprovider -rf`,
  `PYTHONDONTWRITEBYTECODE=1`, and a wall-clock timeout per run (default 180 s).
- **Run-log hook.** When `$WCBW_RUN_LOG` is set, the test file's `_run` helper appends one
  JSON line per wrapper run: `{test, rc, stdout, heartbeat: [status, note], tagged: […]}`. The
  test's tmp root is replaced by `<T>`, and the timestamp in the `pin applied` line by `<TS>`.
  The hook lives in the TEST file only, so D6's "no test mode in the shipped script" still
  holds.

### 5ter.3 Algorithm

Each step fails with a named error.

1. **Schema.** Load the YAML with `yaml.safe_load` and validate it: the schema string; unique
   row and mutant ids; `disposition` in {MUST, EQUIVALENT}; a `reason` on every EQUIVALENT
   row; at least one `killed_by` on every MUST mutant; `mode` one of the four values; `op` in
   {sub, stmt}. Error: `SCHEMA`.
2. **Anchors.** Resolve every anchor to the `occurrence`-th line whose full text equals it.
   Error: `STALE-ANCHOR`.
3. **Closure.** Extract the sites (5bis.3) and compare them with the claims. Errors:
   `UNCLAIMED <line> <kind>`, `PHANTOM`, `DOUBLE-CLAIM`. A `SITE-COUNT` error fires when the
   target's git blob id starts with `derived_from.blob` (a 10-hex prefix; a longer hex id
   trips the repo's detect-secrets pre-commit guard) but the site count differs from
   `derived_from.sites`. This guards the extractor itself against drift.
4. **Materialise.** Each mutant replaces one line. A `stmt` mutant resolves inside the
   anchor's block, meaning the following lines indented deeper than the anchor, to the first
   line that starts with `echo `, `heartbeat ` or `exit `. Errors: `NO-OP` if the text is
   unchanged, `NO-STMT` if the block has no such line, `SYNTAX` if `/bin/sh -n` or `bash -n`
   rejects the mutant.
5. **Baseline.** The unmutated tree must pass the whole test file. Error: `BASELINE-RED`
   (exit 2).
6. **Run.** For each mutant, run the whole test file and collect the failing node ids from the
   `FAILED` lines. A collection error or a timeout is `ERROR`, never a kill.
7. **Verdicts.**
   - A MUST mutant with no failing test is `SURVIVED`.
   - A MUST mutant that was killed, but where no failing id contains a `killed_by` string, is
     `KILLER-MISS`: the row's fixture claim is false, the same failure as r0's dissent #3.
   - A killed EQUIVALENT mutant is `EQUIVALENCE-REFUTED`.
8. **Mode.** For each killer test, compare its run records under the mutant with the same
   test's baseline records, normalised as in 5ter.2. The first matching rule wins:
   1. the mutant's stdout is non-empty and differs from the baseline's: `fail-open`;
   2. the rc differs, whether the stub ran differs, or the run timed out:
      `fail-closed-other-rc`;
   3. the heartbeat or the tagged lines differ: `same-rc-other-diagnosis`;
   4. otherwise: `equivalent`.

   A mutant's mode is the most severe result over its killer tests, and it must equal the
   YAML `mode`. Error: `MODE-MISMATCH`. Validated in scratch: once the fixture rules of 5bis.4
   were applied, all 99 declared modes equalled the measured ones.

9. **Parity.** The `--render-table` output must equal the spec block between
   `<!-- d5-inventory:begin -->` and `<!-- d5-inventory:end -->`. The comparison is cell by
   cell, after splitting rows on unescaped `|` and stripping each cell, so prettier's column
   padding does not matter. Error: `TABLE-DRIFT`. The resumed build's first S3 run replaces
   the 5bis.6 table in this file with the script's own rendering.
10. **Receipt.** It is always written, on failure too.
    - `mutants.json` holds, per mutant: id, row, line, verdict, failing tests, killer hit,
      measured mode and seconds.
    - `mutants.md` has a header carrying the commit (`GITHUB_SHA` or `git rev-parse HEAD`),
      the target blob sha, the inventory sha256, `generated_at` taken from the runner clock
      at the END of the run, and the counts: sites, rows, mutants, killed,
      equivalent-survived and failures by code.

### 5ter.4 Selftest

`--selftest` runs pytest only in case e below and takes under 30 s.

Guilt cases. Each one must be detected, or the selftest fails:

- **a. Unclaimed sites.** Plant one line in the target:
  `if [ -s "$CODEX_PIN_FILE" ] && [ -O "$CODEX_PIN_FILE" ]; then exit 3; fi`. Exactly its new
  `cond`, `test#1`, `test#2`, `andor` and `exit` sites must be reported UNCLAIMED.
- **b. Stale anchor.** Change one row's anchor by one character: `STALE-ANCHOR`.
- **c. No-op mutant.** Give one mutant a `to` equal to its anchor: `NO-OP`.
- **d. Missing statement.** Point one `stmt` mutant at a row whose block has no heartbeat:
  `NO-STMT`.
- **e. End to end.** This is the observation re-gate #2's S3 asked for. Copy the test file,
  remove every `killed_by` entry of row **G2a**
  (`[two_lines_last_unterminated_planted]` and
  `test_innocence_single_line_without_trailing_newline_applies`), and run only mutant
  `G2a/limb`. It must be `SURVIVED`. Every run thus proves that the job goes red when the D10
  fixture is removed.

Innocence: the committed target and inventory pass closure with exactly `derived_from.sites`
sites (109 at `04dd6b51e4`) and zero schema errors.

### 5ter.5 CI wiring

In `wa-codex-pin.yml`, either in the same job or in a second job after the pytest step:

- `python -m pip install pytest==<pinned> pyyaml==<pinned>`, at exact versions (r0 N7);
- `python scripts/ci/wa_codex_wrapper_mutants.py --selftest`;
- `python scripts/ci/wa_codex_wrapper_mutants.py --spec docs/specs/2026-09-27-codexpin-v3-spec.md --receipt-dir "$RUNNER_TEMP/wcbw-mutants"`;
- `actions/upload-artifact` of the receipt directory, with `if: always()`;
- `paths:` gains the script, the inventory YAML and this spec;
- `timeout-minutes: 25`. The 99 mutants take about 3 min on M5, the FIFO hang mutant costs the
  test's 15 s timeout, and macOS runners are slower.

It is not a required context (the D6 reasoning), but it CAN go red. The resumed PR-1 does not
pass its gate unless this job is green on the PR head.

## 5quater. S4 — evidence text in the resumed PR-1 (added 2026-09-27)

Re-gate #2 §4 found two defects in the pack and PR-body text of `04dd6b51e4`. The resumed
build fixes both in the same commit that adds S3.

1. **Receipt timestamps must be observations.** `pack.yml:349` and `:373` carry
   `ts: "2026-09-27T18:30:00Z"`. That is 24 h after the commit (`2026-09-26T18:25:34Z`) and
   after the gate's own `date -u`. Every `ts:` in the pack and the receipts must be a time
   that a command actually printed: either `date -u +%Y-%m-%dT%H:%M:%SZ` captured in the same
   shell as the run, or the CI run's `generated_at`.
   Observation:
   - `grep -n '2026-09-27T18:30:00Z'` on `pack.yml` prints nothing;
   - no `ts:` in the evidence directory is later than the commit that carries it.
2. **Universal claims are retracted and replaced by the S3 receipt.** Several places say
   "every guard and every conjunct … 20/20 … 0 false negatives":
   - PR body lines 62 and 83;
   - the `pack.yml` R3 lane note, disposition and receipt;
   - the acceptance paragraph of `receipts/mutant-table.md`.

   Replace each with the S3 CI run URL, the committed copy of its `mutants.md` receipt, and
   counts copied FROM that receipt. Nobody writes a coverage count or an "every/all" claim by
   hand. The hand-made `receipts/mutant-table.md` is deleted, or replaced by the S3 receipt.
   Observation: `grep -nE 'every (guard|conjunct)|0 false negatives'` over the PR body and
   the evidence directory returns only lines that cite the S3 receipt.

3. **Cosmetic items from re-gate #2 §4,** in the same commit:
   - "a SECOND, fresh re-gate" becomes the actual count;
   - the line-initial `>=1` that became a blockquote is fixed;
   - the "ten faults" docstring gets the true number (17 at `04dd6b51e4`, more after 5bis.7).

## 6. Operator run on Pro, and proof that it is live

Order: PR-1 and PR-2 merged. Nothing else is required. D8 makes a stale checkout fail before
download, and D9 makes a concurrent pull harmless.

Zero, in an interactive Terminal on Pro:

```sh
cd ~/nuzantara && git fetch -q origin main && git status -sb | head -1   # expect "## main...origin/main", no [behind]
/usr/bin/plutil -extract version raw -o - /opt/homebrew/lib/node_modules/@openai/codex/package.json   # 0.156.1 on 2026-09-26
sudo bash scripts/install_wa_codex_pinned.sh 0.156.1
```

Pin 0.156.1 because it is the Homebrew version the running daemon (pid 574, state running,
2026-09-26) executes today. The switch then changes only the binary PATH, not the version.

Preconditions the installer checks itself, fail-closed, in this order, before any download:

- argv is `X.Y.Z` (builtins);
- EUID is 0;
- the D1 chains for `RUNTIME_DIR` and `/usr/local/libexec` hold;
- the D8 wrapper source and protocol check passes;
- `codex/` exists with the exact triple, or is created that way.

Disk: at least 1 GB free on the Data volume (132 MB tgz + ~330 MB tree while staged).

Installer output to look for:

- `verified … (as zantara-codex): codex-cli 0.156.1`
- `wrote …/codex-pin.env`
- `wrapper installed`
- `daemon state: state = running`

**Bites observations.** O1–O3 and O5 are made by the session over `ssh pro` as `nuzantara`,
with no sudo. O4 is made by Zero.

| #             | Observation                                                                                                                                                                          | Proves                                                                                                                                                                                                 |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| O1            | `stat -f '%u:%g:%p' /usr/local/lib/wa-codex-broker/codex-pin.env` = `0:0:100644`, content = `WA_CODEX_CLI_VERSION_PIN=0.156.1`                                                       | the pin is in place, root-only                                                                                                                                                                         |
| O2            | `launchctl print system/com.balizero.wa-codex-broker` shows `state = running` with pid ≠ 574                                                                                         | the daemon restarted through the new wrapper                                                                                                                                                           |
| O3            | `cmp -s /usr/local/libexec/wa-codex-broker-wrapper.sh ~/nuzantara/infra/launchagents/wrappers/wa-codex-broker-wrapper.sh` exits 0 (the declared home-fork pair goes MATCH)           | the PR-1 wrapper is live                                                                                                                                                                               |
| O4            | `sudo -u zantara-codex /usr/bin/grep -E 'pin applied\|matches pin' /Users/zantara-codex/logs/wa-codex-broker.err \| /usr/bin/tail -2`, read AS the service account and never as root | shows `wa-codex-broker-wrapper: <ts> pin applied: codex 0.156.1 at /usr/local/lib/wa-codex-broker/codex/0.156.1/bin/codex`, then `wa-codex-daemon: CLI version 0.156.1 matches pin — claiming enabled` |
| O5 (decisive) | during the next broker job, `ps -axo user=,comm= \| awk '$1=="zantara-codex"'` lists `/usr/local/lib/wa-codex-broker/codex/0.156.1/bin/codex` and no `/opt/homebrew/…codex`          | the codex call itself uses the pinned binary. `comm` is the executable path only, never argv, so no prompt or PII can print. Verified that `comm` shows full paths on macOS                            |

O5 needs a job to arrive. Run a bounded background watcher (≤ 30 min, 1 s cadence, stop at the
first hit) and pair it with that job's `completion … (outcome=…)` daemon log line. That is
functional equivalence: the native binary runs without the npm JS launcher, which sets only
`CODEX_MANAGED_PACKAGE_ROOT` / `CODEX_MANAGED_BY_*`. A completed job is the proof it does not
need them.

## 7. PR split and size

The whole rework is about 1,250 net lines. That does not fit one PR of ≤ ~400.

| Order | PR                                                                                      | Files                                                                                                                                                                                                                                                    | Net lines (est.)                                                                                                                                                                                      | Bites                                                                                                                                                                                                              |
| ----- | --------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1     | `feat(wa-broker): apply the dedicated codex pin in the wrapper with builtins only`      | wrapper (D5, protocol line), `test_wa_codex_broker_wrapper.py`, new `wa-codex-pin.yml`; **amended 2026-09-27:** + `main-push-failure-watch.yml` entry, + `scripts/ci/wa_codex_wrapper_mutants.py` with selftest (§5ter), + the re-rendered §5bis.6 table | ~360 in the scratch plan; **measured 842 at `04dd6b51e4`** (wrapper 189, tests 567, workflow 66, watch list 10, `.prettierignore` 10); about **1,350** with S3 (~350) and the §5bis.7 fixtures (~150) | CI: the macOS run on the PR, pytest AND the S3 receipt (all MUST rows killed, closure clean). Live: O3/O4 at the operator run. Until then the declared home-fork pair shows DRIFT, which is the pending-arm marker |
| 2     | `feat(wa-broker): pinned codex installer v3 — chain-verified, parser-exact, fresh-only` | installer (D1–D4, D8, D9), `test_install_wa_codex_pinned.py`, chaos-table row 8 (dedupe its doubled path), `change_map.py` census                                                                                                                        | **~800** (script ~300, tests ~480)                                                                                                                                                                    | the operator run + O1–O5                                                                                                                                                                                           |
| 3     | `fix(wa-sentinel): name the pinned installer; never blame Homebrew for a pinned daemon` | sentinel (D7), its tests, add both to the workflow paths                                                                                                                                                                                                 | ~90                                                                                                                                                                                                   | the sentinel's next tick on Pro prints `codex pin: 0.156.1 (dedicated)`                                                                                                                                            |

Recommendation: keep PR-2 whole even though it is about twice the soft cap. The cap says
"where the work allows". Here it does not, because any cut ships either:

- a privileged script without its guilt tests (the opposite of what three BLOCKs demanded), or
- a half-installer with no consumer, which violates §2 "Bites" (a future job is not a consumer).

The only viable cut, if the lead enforces ~400, is 2a = D1–D2 predicates + their marker tests
and 2b = orchestration + pipeline tests. 2a would have no consumer until 2b. PR-3 merges after
PR-2; it does not depend on the operator run. Each PR carries its own evidence brief per repo
convention, not counted above.

**PR-1 size (amended 2026-09-27).** PR-1 is now also over the cap, for the same reason as
PR-2. Its tests and the S3 check ARE the acceptance of a guard whose three gates failed on
proof, not on logic. Split out, the S3 script would have no consumer, because it needs the D5
section and the rewritten tests to run against.

The resumed build continues PR #7420 once this spec is on `origin/main`. It first merges
`origin/main`; the branch was never armed, so it is not frozen. The wrapper logic stays
byte-identical to `04dd6b51e4` (§5bis.5, D10 decision). Any logic change would re-open the
full S3 run, which is cheap now. PR-2 uses the same mechanism: an installer inventory in the
same schema, run by the same script (§5ter).

## 8. Not closable by construction (stated, not hidden)

1. **The real identity switch in the probe** (`sudo -u zantara-codex`) cannot run in CI
   without root. CI proves the requested argv and the `o+x` reachability facts (D1). The switch
   itself is proven only by the installer's own probe on Pro. That probe is fail-closed and
   runs before the pin is written.
2. **A malicious daemon env file against the wrapper.** Sourcing it is code execution as
   `zantara-codex`. No in-process check survives that, and parsing the env as data would not
   create a boundary: `zantara-codex` can exec any binary directly. D5 closes the stale or
   wrong DATA class for the pin values, the six re-asserted private names and `PYTHONPATH`
   (scope narrowed 2026-09-27, see D5). The boundary against a hostile `zantara-codex` is the root-owned,
   non-writable tree and pin (D1/D3), which it cannot change.
   Data-parsing the live env was rejected: its exact syntax cannot be inspected without reading
   a secret file.
3. **Supply-chain integrity.** The sha512 comes from the same registry as the tarball.
   Independent approval would need an external signature or provenance check, outside the
   declared scope (same as v2).
4. **A malicious operator account** (`nuzantara`) is out of model (§1).
5. **A deliberately fd-silenced external call before the gate** is invisible to the D6 detector.
   It cannot execute under the test; in production it is controlled by D9/S1 and review.
6. **`heartbeat()` resolves `mkdir` and `date` through PATH after the env is sourced**
   (re-gate #1 §5, added 2026-09-27). The behaviour is identical on `origin/main`. An env
   `PATH` that lacks them makes the `starting` heartbeat silently absent while the daemon
   still starts. This is not a pin guard, so the D5 inventory does not claim it, and the two
   hostile-PATH tests are exempt from P.4 (5bis.4). The fix is `/bin/mkdir` and `/bin/date`.
   It is a wrapper logic change, so it re-runs S3 in full. It is recommended as its own small
   PR after PR-1, now cheap because S3 exists.
7. **An unsearchable ANCESTOR of `RUNTIME_DIR`** (for example `/usr/local/lib` at 000) makes
   the wrapper log `no pin file … (legacy)` and then exit `78` on the venv check (re-gate #1
   §2, added 2026-09-27). The run still fails closed, because `VENV_PY` lives under
   `RUNTIME_DIR` and N1 pins it, but the diagnosis misleads. PR-2's D1 chain check refuses to
   install into such a chain, so the state is reachable only by a root-side change after
   install.
8. **The process environment launchd hands the wrapper** (added 2026-09-27). Pre-source
   initialisations such as `_wcbw_pin_ver=""` are not inventory sites (5bis.3). They matter
   only if launchd injects those names, and the plist is root-owned (§1).

Adjacent, out of scope, noted: the daemon's venv python is Homebrew `python@3.14` (the `ps`
`comm` on Pro shows `/opt/homebrew/Cellar/python@3.14/…`). A Homebrew python upgrade is the
same "shared Homebrew stops the bot" class for the interpreter.

## 9. Evidence behind the empirical claims (run 2026-09-26)

- M5 and Pro: `bsdtar 3.5.3 - libarchive 3.7.4`.
- Pro chain `stat`/`find -acl`: as §D1. Pro `id -Gn zantara-codex`: no wheel.
- Pro checkout: `~/Desktop/nuzantara -> ~/nuzantara`; `com.nuzantara.git-pull-main.15min`
  loaded. Homebrew codex 0.156.1. Broker `state = running`, pid 574.
- `find -perm -022` misses 0664/0646; `+022` and the single-bit disjunction catch both;
  `find -acl` flags allow and deny ACEs (M5, BSD find).
- bsdtar `-t` escapes (`\n`, `\t`, `\\`, `\351`, `\033`) under `LC_ALL=C`; the mtree writer
  normalizes names and hides hardlinks; extraction strips a leading `/` (including on a
  hardlink target) and refuses `..`.
- The #7340 head awk accepts `../review-probe` and `/etc/review-probe` with uname `evil user`;
  the v3 grammar rejects both.
- The real 0.156.1 tarball: 44 entries, all `-`, grammar-clean. Probe bytes `codex-cli 0.156.1\n`.
- bash 3.2 `-r` with empty PATH: every §D6 mutant detected, the unmodified gate clean.
  Top-level self-append executes; the `main "$@"; exit $?` form does not.
- macOS `install(1)`: temp file + rename always. `chmod -N` present. `ps -o comm` prints full
  executable paths without argv.

Added 2026-09-27 (M5, bash 3.2.57, against the PR #7420 wrapper at `04dd6b51e4`, blob
`4143a795d9`, sha256 prefix `9fb2268887392b6e`; scratch prototypes, not committed):

- **Site extractor (5bis.3).** It found 109 sites, all claimed by the 54 rows. Five planted
  constructs produced 11 UNCLAIMED sites. One changed guard line produced `STALE-ANCHOR`
  before any mutant ran.
- **Current suite (28 tests).** 99 mutants: 54 killed, 45 survived (42 MUST plus the 3
  EQUIVALENT), no `sh -n` failure (5bis.8).
- **Feasibility suite (47 tests, contracts N and P).** 96 of 96 MUST mutants killed, each by
  a declared killer. The 3 EQUIVALENT mutants survived. All 99 declared modes equal the
  measured ones. About 3 minutes of wall time.
- **Consistency with re-gate #2.** On the same blob, the prototype reproduces that gate's
  verdicts: D10, D25, D26, D02, S1–S5 and P1–P5 survive; D09, D11, D12, D13 and D16 die.
- **Shipped-wrapper behaviour.** Under the shipped wrapper,
  `WA_CODEX_CLI_VERSION_PIN=9.9.9\` + NUL + `JUNK` refuses with the NUL reason. With the
  probe's `-r` dropped, it refuses with the semver reason instead (G1b is DX, not FO).

## 10. Changelog against the scratch text (2026-09-27)

Every change below is traceable to a gate on PR #7420 or to the S2–S4 conditions of its
BLOCK. D1–D4, D6's proof design, D8, D9, §1, §2, §4, §6 and the installer and sentinel test
tables are unchanged, except where listed.

| §          | Change                                                                                                                                         | Proved by                                                                |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| header, §0 | Commit note; scratch inputs marked ephemeral                                                                                                   | S2 (the spec lived only in `/private/tmp`)                               |
| D5         | Line grammar: `IFS=`/`-r` are requirements; a single line without a final LF is accepted; two lines with an unterminated last line are refused | re-gate #2 D10, D25, D26                                                 |
| D5         | NUL probe rule, the bash-only `read -d`, explicit `/bin/sh` in tests                                                                           | spalla review 2026-09-26; r0 C1, N2                                      |
| D5         | Implemented check order; one tagged diagnostic line per refusal is contract                                                                    | r0 C1 plus re-gate #1 R3 (masking), this spec §5bis.4                    |
| D5         | EACCES rule made precise (`[ -d ] && [ ! -x ]` on `RUNTIME_DIR`; `-r` on the pin)                                                              | r0 C3, N4                                                                |
| D5         | Semver wording: "three numeric fields", leading zeros allowed; per-alternative witnesses                                                       | r0 spec-owner note; re-gate #2 S1–S5                                     |
| D5         | Handoff through positional `$1`/`$2`, not the named `PIN_VER`/`PIN_BIN`                                                                        | spalla review 2026-09-26 (named vars clobbered by DATA); r0 judged sound |
| D5         | Post-source re-assert of six literals plus `PYTHONPATH`                                                                                        | r0 N1 (sol BLOCKER, `TAG` gap); `PYTHONPATH` by this inventory (G8g)     |
| D5         | Kill-switch precedence stated                                                                                                                  | r0 N3; re-gate #1                                                        |
| D5, §8.2   | Scope narrowed to the named DATA                                                                                                               | r0 spec-owner note                                                       |
| D6         | Watcher-coverage entry; extend `paths:` and the pytest argv; S3 steps; pinned pytest/pyyaml                                                    | re-gate #1 R1; r0 N7; S3                                                 |
| D7         | Sentinel uses the exact same line grammar                                                                                                      | follows from the D10 decision                                            |
| §5         | `test_semver_validators_agree` asserts expected verdicts, not agreement alone                                                                  | re-gate #2 §2                                                            |
| §5         | Wrapper table marked superseded by §5bis                                                                                                       | r0 C1, re-gate #1 R3, re-gate #2 BLOCK                                   |
| §5bis      | Closed D5 inventory, site grammar, fixture contract, dispositions, decisions                                                                   | S2                                                                       |
| §5ter      | S3 mutation check specified                                                                                                                    | S3                                                                       |
| §5quater   | S4 evidence-text fixes                                                                                                                         | S4, re-gate #2 §4                                                        |
| §7         | PR-1 content and measured size; resumption on #7420; PR-2 reuses S3                                                                            | S2–S4                                                                    |
| §8         | Items 6–8 (heartbeat PATH, ancestor EACCES, launchd env)                                                                                       | re-gate #1 §2 and §5; this inventory                                     |
| §9         | 2026-09-27 measurements                                                                                                                        | this spec                                                                |
