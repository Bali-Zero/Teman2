# Spec v3 — dedicated pinned codex for the WA broker (rework of PR #7340)

Status: SPEC, not code. Written 2026-09-26 against PR #7340 head `3d04590c99`
(`agent/air-m5/ops/wa-codex-pinned-installer`). Supersedes spec v2 for the listed surfaces;
everything v2 says that is not contradicted here still holds.

Committed 2026-09-27. Before that it existed only as a session scratch file, which a reboot
would have deleted. This copy keeps the scratch text for D1–D9, their amendments and the 3-PR
plan. It changes only what the three gates on PR #7420 (PR-1), council rounds 1–4 on this
spec, or the fresh gates on this spec (gate r3, comment 5850401670; gate r4, comment 5852422768) proved wrong, and it adds:

- §5bis, the closed D5 inventory (condition S2 of the #7420 BLOCK);
- §5ter, the mutation check CI runs against it (S3);
- §5quater, the evidence-text fixes for the resumed build (S4).

§10 lists every change against the scratch text, each with the gate that proved it. The
normative inventory is the sidecar `docs/specs/2026-09-27-codexpin-v3-d5-inventory.yaml`.

**Re-scoped by gate r4 (owner ruling 2026-09-27: the generator route).** S3 no longer checks a
mutation table that an author wrote. It generates every mutant from the target, and the YAML
only annotates the generated ids (§5bis.3, §5bis.3a, §5ter.3). Any change to the inventory,
the wrapper's test file, this spec or the S3 script is a Gear-3 change (§5ter.5).

Dates in this spec are calendar dates in Asia/Makassar (UTC+8). The measurements marked
2026-09-27 ran from 2026-09-26T19:00Z on, and the evidence pack gives each one's UTC
start and end. Every timestamp in the evidence pack is UTC, as §5quater requires.

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
- **Heartbeat without PATH (added 2026-09-27, council round 1; ruled by the coordinator the
  same day).** The resumed PR-1 modifies exactly two wrapper lines beyond `04dd6b51e4`, and
  nothing else:
  - line 72, `mkdir -p "$SIDECAR_DIR" …` becomes `/bin/mkdir -p "$SIDECAR_DIR" …`;
  - line 74, `"$(date -u …)"` becomes `"$(/bin/date -u …)"`.

  **Why: G9b's equivalence.** At `04dd6b51e4`, `heartbeat()` resolved `mkdir` and `date`
  through the `PATH` that the sourced env sets. Under `PATH=/does-not-exist` the shipped
  wrapper silently skipped the `starting` heartbeat, while G9b's mutant (the `|| return 0`
  dropped) wrote one with an empty timestamp. That observable difference made G9b's EQUIVALENT
  claim false (5bis.5), and without the fix G9b would have to become MUST, pinning a
  broken heartbeat as contract. With absolute paths the two behave identically, so G9b is
  equivalent, and §8 item 6 closes. Labels G9j and G9k pin the two absolute paths (`abspath`
  sites, §5bis.3), and G9l pins line 74's `-u` (`dateopt`).

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
  - r0 N7: each later PR (PR-2, PR-3) extends BOTH the scope list (`paths:` before gate r3
    R6, below) and the pytest argv.
  - PR-1 also runs the S3 mutation check (§5ter) in the same workflow and pins `pytest` and
    `pyyaml` by exact version.
  - Gate r3 R6: PR-1 ships the workflow in the repo's W69 sentinel shape (no `paths:` under
    `pull_request`, a scope decision inside, an always-reporting `wa-codex-pin verdict` job;
    §5ter.5), so the verdict can become a required context once PR-1 has merged. That arming
    is an operator step. This supersedes the `pull_request` path filter above, and
    "not a required context" holds only until the arming.

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

The same cause produced four gate findings in a row: three on the PR #7420 wrapper, and the
fourth on this spec's own S3 contract:

| Gate                                     | Head         | Guard deletable with the suite still green                                                                                  | Mechanism                                                                                                                                                   |
| ---------------------------------------- | ------------ | --------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| r0 (comment 5847376532)                  | `08a5d93537` | NUL probe, exactly-one-line, `_is_semver` (17/17 green each)                                                                | negative fixtures never planted the binary, so the later `-x` check caught every fault first                                                                |
| re-gate #1 (5848624798)                  | `737d16224a` | key `case`; the `-x` half of `-f && -x` (26/26 green)                                                                       | `unknown_key` also fails `_is_semver`; C2 put `-f` in front of `-x`, which removed `-x`'s only discriminating fixture                                       |
| re-gate #2 (5848838838, BLOCK)           | `04dd6b51e4` | `\|\| [ -n "$_pin_row" ]` (28/28 green); also read flags `IFS=`/`-r`, `_is_semver` alternatives S1–S5, C3's `[ -d ]`, P1–P5 | nothing isolated them. Every table was written by hand (the builder's twice, one gate's once) and each missed a conjunct                                    |
| gate r4 on this spec (5852422768, BLOCK) | `3a2cf979a0` | a miniature of #7340's `[ … ] \|\| die`: the integrity guard, with every S3 check of that head green                        | the spec fixed each kind's operator, but each row still chose which member of the class it carried, and S3 accepted an always-refusing drop as the only one |

Three root causes, each with its own cure:

1. **Masking.** A fixture that claims to test guard X is satisfied by a later guard Y. This
   happens because the tests assert only `rc 78` plus `refused`/`pin invalid`, and every refusal
   produces exactly that. Cure: the fixture contract (5bis.4). Every negative fixture asserts
   the ONE diagnostic line of the guard it isolates, so a masked mutant shows a different
   reason (or two lines, or none) and dies.
2. **Enumeration by hand.** Nobody derived the tables from the file, so every table missed
   something. Cure: a site grammar (5bis.3) that a script extracts mechanically, with closure.
3. **Author choice inside the contract** (gate r4). With sites extracted and operators fixed,
   the row still picked its mutants, and a disposition flip was a one-line edit at Gear floor
   1. Cure: S3 generates every member of every operator class of every site (5bis.3), the YAML
      only annotates the generated ids (5bis.2), and every change to the inventory, the test file,
      this spec or S3 is a Gear-3 change (§5ter.5).

### 5bis.2 Format: a YAML sidecar, normative

The inventory is `docs/specs/2026-09-27-codexpin-v3-d5-inventory.yaml`, schema
`wa-codex-wrapper-inventory/2`. Schema 1 (rows with an anchor line, `covers` and an
author-written `to` per mutant) is retired by gate r4: an author who writes the mutant also
chooses which member of an operator class gets tested, and that choice is the class of fault
this inventory exists to close. It is YAML for two reasons:

- **It is a spec artifact.** The file sits next to the spec, not next to the test. A
  disposition or a mode is a spec decision, and every change to it is a Gear-3 change
  (§5ter.5).
- **The toolchain already exists.** The repo already parses YAML with PyYAML in CI
  (`catE-sovereignty-lint.yml`, `craft-instruments-daily.yml`), and `wa-codex-pin.yml`
  installs it at a pinned version.

The header carries `schema`, `target`, `tests` and `derived_from` (`base_commit`,
`base_blob`, `blob`, `sites`, `mutants`). Then comes `mutants`, a list with exactly one entry
per id that S3 generates from the target (5bis.3, 5bis.3a), in S3's order. An entry carries
at most these six keys:

| Key           | Present         | Meaning                                                                                                                                |
| ------------- | --------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `id`          | always          | the generated id, copied from S3's output and never composed by hand                                                                   |
| `disposition` | always          | `MUST` or `EQUIVALENT` (5bis.5)                                                                                                        |
| `mode`        | always          | the mode S3 measures (5bis.6, §5ter.3 step 8); `equivalent` on exactly the EQUIVALENT entries                                          |
| `killed_by`   | MUST only       | at least one pytest node-id substring, each matching exactly one collected test and naming the fixture that isolates the fault         |
| `reason`      | EQUIVALENT only | why no contracted observation can tell the mutant apart                                                                                |
| `label`       | optional        | the schema-1 row that claimed the mutant's site (G0a–G9l), so the #7420 pack stays readable. S3 renders it and derives nothing from it |

Any other key is `SCHEMA`, `to` included (gate r4 H7). An entry cannot say what a mutant is,
only how it is judged.

The table in 5bis.6 is a rendering of the YAML, and S3 checks that the two agree (§5ter.3
step 9). Labels in families 1–5 keep the builder's names:

- G0 = the constants before the source (added in council round 1, 5bis.3);
- G1 = NUL probe;
- G2 = exactly one line;
- G3 = semver;
- G4a = symlink, G4b = key;
- G5, G5a, G5b = binary.

Schema 1's `was` field, which mapped builder `G*`, gate `C*`/`N*`/`R*` and re-gate #2
`D01`–`D26`, `S1`–`S7`, `P1`–`P6` to the rows, stays readable in the schema-1 file at
`3a2cf979a0`; the decisions table in 5bis.5 keeps the mapping for the items re-gate #2 named.

### 5bis.3 Site grammar: what "every guard" means, mechanically

A site is one occurrence, on a code line of the target, of one of the 17 kinds below. Comment
lines and blank lines have no sites. Before matching, the file is masked: the contents of
`'…'` and `"…"` are blanked, so words inside messages never count, and a `#` that starts a
word outside quotes starts a comment: at line start, or after a blank or one of `; & | ( ) <

> ` (council round 4; the targets have no such comment, and no count changes). Masking runs over the whole file and carries the
quote state across newlines, so a quote opened on one line and closed on a later one blanks
everything between (amended by gate r4's installer receipt, §5ter.6; the wrapper has no
multi-line quote, and no count changes). Outside quotes a backslash escapes the next
character. The kinds matched "on the raw line" read the line with its comment removed and
only its single-quoted text blanked, so they see inside double quotes (`"${X:-true}"`,
`"$(/bin/date …)"`) but never inside an `awk` program.

**Literal code that masking hides is an error** (council round 4). Masking blanks code in
three places, and S3 looks there instead of trusting the blank:

- a `$( … )` inside double quotes (`x="$([ -f "$X" ] || exit 78)"`), nested ones included;
- the string argument of `eval`, the action of `trap`, and the command string of `sh -c`
  (also `bash`, `dash`, `ksh`, `zsh`, by any path).

S3 extracts each such text as a file of its own. If it holds a site of any kind read on the
fully masked line (all kinds except `default`, `abspath` and `dateopt`, which already see
inside double quotes), the error is `MASKED <line> <where>: <kinds>`. Two constructs are not
modelled at all and are `UNSUPPORTED <line> <construct>`: a heredoc (`<<` outside quotes and
outside `$(( ))`; an arithmetic `(( a << b ))` and a here-string `<<<` are reported under the
same name, fail-closed), whose body is data or code depending on its reader and whose
unbalanced quote would shift the masking of every later line; and a backquote substitution
outside single quotes. A target that needs either rewrites it, or extends the grammar in a
reviewed change. Only literal text is examined. Code that reaches an interpreter through a
variable (`eval "$code"`, `sh -c "$G"`), an `alias`, a sourced file, ANSI-C quoting `$'…'`, an
`sh -c` behind option arguments or `env`/`command`, or a `default`, `abspath` or `dateopt` site
inside a single-quoted string is not resolved and raises no error: §8 item 12 (open). On the PR-1 target this finds nothing: its two double-quoted substitutions are
`"$(/bin/date -u …)"` (lines 74 and 269), which hold only `abspath` and `dateopt` sites. On
#7340's installer it reports five `MASKED` lines (§5ter.6).

| Kind       | Matches (on the masked line unless stated)                                                                                                                                            | Sites (PR-1 target) |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| `cond`     | each `if`, `elif`, `while` or `until` keyword in command position                                                                                                                     | 15                  |
| `test`     | each `[` test command: a `[` preceded by line start or one of `\s ; & \| ! (` and followed by whitespace. Glob brackets such as `*[!0-9.]*` never match                               | 14                  |
| `andor`    | each `&&` and each `\|\|`                                                                                                                                                             | 5                   |
| `alt`      | inside `case … esac`, each `\|`-separated alternative of an arm's pattern (`pattern)` or `(pattern)` at line start)                                                                   | 8                   |
| `readopt`  | per `read` command: the `IFS=…` prefix if present, plus each option word. An option that takes an argument (`-a -d -n -p -t -u`) is one site together with it (`-d ''`, `-n 1`)       | 5                   |
| `default`  | on the raw line: each `${NAME:-…}`, `${NAME-…}`, `${NAME:=…}`, `${NAME=…}`, `${NAME:?…}`, `${NAME?…}`, `${NAME:+…}` or `${NAME+…}`                                                    | 1                   |
| `exit`     | each `exit` or `return` in command position                                                                                                                                           | 18                  |
| `hb`       | each `heartbeat` call (not its definition)                                                                                                                                            | 15                  |
| `diag`     | each `echo` or `printf` on a line that redirects `>&2`                                                                                                                                | 15                  |
| `exec`     | each `exec`                                                                                                                                                                           | 2                   |
| `setopt`   | each line that is `set -…` or `set +…`, including `set --`                                                                                                                            | 4                   |
| `reassert` | each `NAME=` word of a top-level (column 0) line that starts `NAME=` or `export NAME=`, after the `. "$ENV_FILE"` line                                                                | 7                   |
| `const`    | the same, before the `. "$ENV_FILE"` line                                                                                                                                             | 11                  |
| `neg`      | each `!` negation: a `!` preceded by line start or one of `\s ; & \| (` and followed by whitespace, as in `if ! …` and `[ ! -f … ]`                                                   | 8                   |
| `redir`    | each input redirection `<`, but not `<<`, `<(`, `<&` or a numbered `N<`                                                                                                               | 2                   |
| `abspath`  | on the raw line: each word that is an absolute path under `/bin`, `/sbin`, `/usr/bin` or `/usr/sbin`, preceded by line start, whitespace or one of `; & \| ( !` (so right after `$(`) | 4                   |
| `dateopt`  | on the raw line: each option word of a `date` command (`date` or `/bin/date`, including right after `$(`), together with its argument for `-f -r -v -z`                               | 2                   |
| **total**  |                                                                                                                                                                                       | **136**             |

The first 12 kinds are the scratch grammar. `const`, `neg` and `redir` were added after council
round 1, which showed a fail-open deletion in each class that no site claimed. `abspath` was
added after council round 2, which showed that nothing pinned the heartbeat's `/bin/date`
(§10). `dateopt` was added on the coordinator's ruling that `date -u` is MUST (§8 item 9).
Gate r3 (R4) made four cells exact without changing any count: the `(pattern)` arm, the
arguments of `read`'s and `date`'s options, and "each `NAME=` word". The round-2 prototype
had read them narrowly, and the normative plant of §5ter.4 (a) now catches that.
The PR-1 target is `04dd6b51e4` plus the D5 heartbeat fix. The fix adds the two `abspath`
sites on lines 72 and 74, so the target has 136 sites and `04dd6b51e4` has 134. The other
kinds count the same on both blobs.

The grammar may over-match: an arithmetic `<` would count as a `redir`, a column-0
`IFS= read` before the source as a `const`, and an absolute path passed as an argument
(`sudo … -H /usr/bin/env`) as an `abspath`. The wrapper has none of them. An over-matched
site fails closed: S3 generates its members, and they stay UNANNOTATED until the YAML judges
them or the grammar is narrowed in a reviewed change.

A site's key is `(line, kind)`. When one line carries several sites of the same kind, they
are keyed `kind#1`, `kind#2`, … in textual order. For example, line 134 has `test#1`
(`[ -d … ]`) and `test#2` (`[ ! -x … ]`).

These are deliberately not sites:

- **Indented working assignments** (`_pin_lines=0`, `_pin_line=""`, the loop's counter and
  copy, the prefix strip `${_pin_line#…}` and the derivation
  `_wcbw_pin_bin="$PINNED_CODEX_ROOT/…"`). They are data flow, not guards. Measured on
  line 176: deleting `_pin_lines=0`, or setting it to `1` or `-1`, failed 30 to 34 of the 50
  tests,
  because a valid single-line pin no longer counts as one line. Deleting line 177,
  `_pin_line=""`, is inert and failed none: every accepted input overwrites it at line 180,
  and an empty file exits on the line count before it is read.
- **Output redirections** (`> "$SIDECAR_DIR/…"`, `2>/dev/null`). The heartbeat write is
  asserted by N.2 and P.4. `2>/dev/null` only silences an untagged line, and untagged lines are
  not the contract (5bis.4).
- **Command options other than `read`'s and `date`'s** (`grep -q`, `mkdir -p`). Measured one
  by one. Dropping `-q` prints the placeholder line to stdout, and N.4's empty-stdout clause
  fails the placeholder test. Dropping `-p` makes `mkdir` fail on the existing sidecar
  directory, so the heartbeat is never written and 44 tests fail. `date`'s options ARE sites
  (`dateopt`): dropping `-u` failed no test until the TZ fixture existed (§8 item 9).
- **The rest:** `. "$ENV_FILE"`, `cd` on its own, and the `printf` that writes the heartbeat
  file.
- **Finer value mutations** (council round 4): swapping a unary test operator (`-f`→`-d`,
  `-n`→`-z`), flipping a string comparison (`=`→`!=`), or changing an option's argument (the
  `''` of `-d ''`). No kind generates them. The `true` and `false` members bound each such
  test's two outcomes, and contract N.3 makes the refusal that follows carry its own reason,
  which is what would expose them. They were not measured one by one: whether a suite kills
  them is a property of its fixtures, not a per-mutant guarantee, and that is the price of a
  finite, reviewable member set.

**Closure rule.** S3 generates every member (below) of every extracted site, and the YAML
must annotate exactly the generated ids: a generated id without an entry is `UNANNOTATED`,
and an entry whose id is not generated is `PHANTOM` (§5ter.3 step 4). Anything new in the
wrapper that matches a kind (a new `[ … ]`, `&&`, `!`, `<`, case alternative, read flag,
`${…:-…}`, `exit`, heartbeat, diagnostic, constant, re-assert, absolute command path or
`date` option) therefore brings new ids, and CI fails until the YAML judges each of them.
That is what "closed" means here. It is stronger than schema 1's closure, where a row claimed
a site and then chose which of its mutations to carry: here the site carries all of them.

Measured with the scratch prototype (non-normative; the generator route, 2026-09-27):

- 136 sites on the PR-1 target and 134 on `04dd6b51e4`, per kind the same as before the
  masking amendment;
- 177 mutants generated on the target and 175 on `04dd6b51e4`, where lines 72 and 74 have no
  `abspath` member. All 177 are annotated, with 0 errors of any code;
- the normative plant of §5ter.4 (a), 27 sites covering all 17 kinds, came back as
  `STALE-DERIVATION` plus `UNANNOTATED` for exactly the 31 ids generated on 12 of its 14
  lines (`case … in` and `esac` carry no site), whose site keys are exactly the 27. The round-2 extractor found 24 of those sites. It
  missed `-d x` after `read`'s `-n 1`, the second assignment of
  `wcbw_plant_b=1 wcbw_plant_c=2`, and `-R` after `date`'s `-r 0`: the overfit gate r3 R4
  predicted, found in this spec's own prototype.

**Generated members.** For every site, S3 generates every member its kind lists below, each
as the target with one line replaced. No author chooses a member, and no entry can add one,
drop one or change its text.

| Kind         | Members (name: the line S3 writes)                                                                                                                                                                                                                                                                                                                                                                                                |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cond`       | `never`: the condition list becomes `false` after `if`, `elif` or `while`, and `true` after `until`. `always`, after `if` and `elif` only: `true`                                                                                                                                                                                                                                                                                 |
| `test`       | `true` and `false`: the `[ … ]` command, brackets included, becomes the constant. Inside a `while` condition list `true` is not generated, and inside an `until` one `false` is not: either could keep the loop running, and the operand's `andor` drops cover it. `relop`, when the test holds `-eq -ne -lt -le -gt -ge`: the first of them shifts, `-ne`→`-gt`, `-eq`→`-ge`, `-lt`→`-le`, `-le`→`-lt`, `-gt`→`-ge`, `-ge`→`-gt` |
| `andor`      | `drop-left`: the operator and the operand on its left are deleted. `drop-right`: the operator and the operand on its right                                                                                                                                                                                                                                                                                                        |
| `alt`        | `drop` when the pattern has several alternatives: the alternative and the `\|` after it (for the last one, the `\|` before it). `widen` for a single alternative other than `*`: it becomes `*`. `neutralise` for a single `*`: it becomes `__wcbw_never_matches__`                                                                                                                                                               |
| `readopt`    | `drop`: the `IFS=…` prefix and the blanks after it, or the option word with its argument and the blanks before it                                                                                                                                                                                                                                                                                                                 |
| `default`    | `drop`: `${X:-v}` becomes `${X}`, for each of the eight forms                                                                                                                                                                                                                                                                                                                                                                     |
| `neg`        | `drop`: the `!` and the blanks after it                                                                                                                                                                                                                                                                                                                                                                                           |
| `redir`      | `drop`: the blanks before the `<`, the `<` and its word. The command then reads the wrapper's stdin, which launchd and the harness both bind to `/dev/null`                                                                                                                                                                                                                                                                       |
| `abspath`    | `strip`: the directory (`/bin/date` → `date`), so the command resolves through the env's `PATH`                                                                                                                                                                                                                                                                                                                                   |
| `dateopt`    | `drop`: the blanks before the option, the option and its argument (`/bin/date -u` → `/bin/date`)                                                                                                                                                                                                                                                                                                                                  |
| `const`      | `value`: `-mutant` appended to the assignment word, inside its closing quote when the word ends in one (`TAG="wa-codex-broker-wrapper-mutant"`)                                                                                                                                                                                                                                                                                   |
| `reassert`   | `remove`: the line becomes `:` at its indentation. `value`: as for `const`                                                                                                                                                                                                                                                                                                                                                        |
| `setopt`     | `remove`: the line becomes `:` at its indentation                                                                                                                                                                                                                                                                                                                                                                                 |
| `hb`, `diag` | `remove`: the simple command becomes `:`                                                                                                                                                                                                                                                                                                                                                                                          |
| `exec`       | `remove`: the simple command becomes `:`. `env-drop`, when the word after `exec` is `env` or `/usr/bin/env` followed by `NAME=…` words: `env` and those words are deleted (G7f's plain `exec`)                                                                                                                                                                                                                                    |
| `exit`       | `remove`: the simple command becomes `:`. `value`, when a literal integer follows: `N` → `1`, and `1` → `0`                                                                                                                                                                                                                                                                                                                       |

Terms, read on the masked line:

- **Condition list:** from the first non-blank after the keyword to the first `;` or single `&`
  outside parentheses and braces, or to the end of the line.
- **And-or list, operand:** the line splits into lists at `;`, `;;`, a single `&`, `(`, `)`,
  a `{` or `}` that stands as a word, and after the reserved words
  `if elif while until then do else` in command position. Inside a list, the `&&` and `||`
  at the list's own depth separate its operands; a `|` pipe stays inside its operand, and so
  does a leading `!` (`! A || B` has the operands `! A` and `B`). Operands are trimmed of
  blanks. `drop-left` deletes from the start of the left operand to the start of the right
  one, and `drop-right` from the end of the left operand to the end of the right one.
- **Simple command** (for `remove`): from the keyword to the first `;`, `&&`, `||`, `|`, `)`,
  or `}` after a blank or `;`, or to the end of the line. Blanks before that end stay outside
  it.

Four rules make the set exact:

1. **Both polarities, no judgement.** Every condition gets `never`, every `if` and `elif`
   also `always`, and every test operand of an and-or list both constants. S3 does not work
   out which constant fails open. In `guard || refuse` it is `true`, in `refuse-if A && B` it
   is `false`, and in `if A || B; then refuse` it is `false` for both operands, so polarity
   depends on what consumes the list. The always-refusing member of each guard is generated
   too, and any innocence test kills it. Schema 1's rule that a refusal guard's condition may
   only become `false` is withdrawn: it let a row pass on the drop that refuses (gate r4 H1
   and H2), and it never reached and-or operands.
2. **Duplicates.** When two members of sites on one line produce the same line, S3 keeps the
   first in canonical order (kinds in the order of the grammar table, keys in textual order,
   members in the order of the table above) and generates nothing for the other. A test that
   is the whole condition of an `if` therefore adds no member of its own: its constants are
   the `cond`'s `always` and `never`. A member reported `SPAN` (rule 4) writes no line, so it
   takes no part in this comparison and cannot absorb a later member.
3. **No-op.** A member whose line equals the target's line is no mutation and is not
   generated. Only a constant condition does that (`never` of `if false`). A site left with no
   member at all, generated or merged by rule 2, is `NO-MEMBER`.
4. **One line in, one line out (gate r4 H7).** A member edits one physical line. When the text
   it must delete or replace is not wholly on that line (it is empty there, it starts a line
   that continues the previous one, or it runs to the end of a line that continues through a
   final unquoted `\` or a quote still open), S3 reports `SPAN <id>` instead of generating
   it. Every generated mutant is checked before any run: the replacement holds no `\n` or
   `\r`, the mutant has the target's line count, and it differs from the target at that one
   line only (`LINES`). The generator only deletes spans and writes the tokens of the table,
   so `LINES` can fire only on an implementation defect, and selftest d proves the check is
   live. The wrapper has no `SPAN`; #7340's installer has ten (§5ter.6).

**Why exit values (gate r3 R2).** Contract N.1 pins the rc. `exit 78` → `exit 1` survives any
test that asserts only a non-zero rc. On the kill switch, changing `exit 0` changes nothing but
the rc, and under `KeepAlive.SuccessfulExit=false` that rc decides whether launchd relaunches
the job. The heartbeat's `return 0` gets its `value` member too, which is EQUIVALENT because no
caller reads the status. Schema 1 exempted a `return N` from removal; the generator removes it
as well, and the two removals that change nothing are EQUIVALENT entries with their reasons
(5bis.5).

**Why relop (gate r3 R3).** `-ne 1` → `-gt 1` on line 182 lets an empty pin file past the
line count, and only `[empty]` notices, through the reason text (`must carry exactly one line`
becomes `unrecognized line`). The class covers arithmetic comparisons only. `=` and `!=` have
no boundary to shift, and the wrapper's one string comparison, `= "false"` on line 251, is the
kill switch's condition, whose `never` member disables it.

**What the generator adds over schema 1, on the PR-1 target.** The 148 schema-1 mutants map
to 148 of the 177 generated ones: 147 by identical line, and G9h/x by effect (the `exit 78`
inside the braces dropped). The other 29 are new:

- `always` of the 12 refusal `if`s that had only `never`;
- nine test constants, on lines 134, 178 and 206;
- `drop-left` of lines 72, 178 and 263; the first and the last are gate r4's H1 and H2;
- `remove` of the four `return`s, and of line 270's `exec`.

27 of them are MUST and killed by a declared killer in the suite of 5bis.8. The other 2 are
EQUIVALENT.

### 5bis.3a Mutant ids (gate r4 re-scope)

A generated id is `<line-id>:<key>:<member>`, for example `f92099df19bdd5b5:andor:drop-right`. `<key>`
is the site key (`kind`, or `kind#n` when one line holds several sites of the kind, numbered in
textual order), and `<member>` is the member's name. No line number enters an id.

`<line-id>` comes from the line's normal form: the line with its comment removed (where masking
finds it), each run of blanks outside quotes collapsed to one space, leading and trailing
blanks removed, and quoted text kept byte for byte. `h(x)` is the first 16 lowercase hex
digits (64 bits) of SHA-256 over the UTF-8 bytes of `x`. Lines whose normal form is empty
(blank or comment only) take no part.

- A line whose normal form occurs once in the file: `h(norm)`.
- A repeated line: `h(norm)@A`. `A` is the anchor, `h` of the nearest earlier line whose normal
  form occurs once in the file, or `^` when there is none. When the same normal form occurs
  more than once between the anchor and this line, its k-th occurrence there (k ≥ 2) gets
  `.k` appended.
- Two different normal forms in the file with the same `h` are `ID-COLLISION`.

Why 64 bits (council round 4). An annotation follows its id, so an id must not survive a change
of the line it names. With 8 hex digits, an edited line could be varied (a quoted no-op, a
spelling) until its first 32 bits match the old line's: about 2^32 tries. The edited line
would keep its old id, and its old disposition would silently judge the new mutant. At 64
bits the same search needs about 2^64 tries, 2^32 times more (no benchmark was run). `ID-COLLISION`
covers the other case, two lines of one file with one `h`, which needs no search to report.

Example: `exit 78` occurs 12 times in the wrapper. Each refusal block's `exit 78` is keyed by
that block's own `echo` line, which is unique, so the symlink refusal's is
`8526388771f87b84@cc48e9e0b1618624:exit:value`.

An id changes only when one of these happens (selftest b):

1. its own line's normal form changes (barring a 64-bit collision);
2. for a repeated line, its anchor changes: a line with a unique normal form is inserted,
   deleted or edited between the anchor and it, or the anchor line itself changes;
3. an edit makes its line, or its anchor line, newly repeated or newly unique.

Nothing else moves it: inserting or deleting other lines, comments or blank lines,
re-indenting, or editing another guard. Point 2 is the one limit a reviewer meets in practice:
a line inserted right after `set +a` re-keys the six re-assert lines, which repeat the
constants and anchor on `set +a`. The re-keyed ids come back as `UNANNOTATED` plus `PHANTOM`,
never silently, and the plant of §5ter.4 (a) goes after `export PYTHONPATH=` for that reason.

### 5bis.4 Fixture contract: the cure for masking

Every test that runs the wrapper asserts one of these two contracts, never less.

**Contract N (refusal).**

1. `rc` equals the guard's code: `78`, or `0` for the kill switch. The exit-value mutants of
   5bis.3 enforce it (gate r3 R2). Before them only review did.
2. The heartbeat file carries the expected `status` and `note`, and its `ts` is a well-formed
   UTC stamp (`YYYY-MM-DDTHH:MM:SSZ`). An empty `ts` is what a PATH-resolved `date` writes
   under a hostile `PATH` (G9k).
3. Exactly ONE stderr line starts with `wa-codex-broker-wrapper: `, and it contains the
   guard's reason text.
4. The stub did not run (stdout is empty).

**Contract P (start).**

1. `rc == 0`.
2. The stub reports exactly the expected `WA_CODEX_CLI_VERSION_PIN`, `WA_CODEX_BIN` and
   `PYTHONPATH`.
3. Exactly one tagged stderr line: `<UTC stamp> pin applied: codex <v> at <bin>`, matched in
   full with the stamp's format, or `no pin file at <path> — … (legacy)`.
4. The heartbeat reads `starting` / `exec daemon` with a well-formed `ts`, the two
   hostile-PATH tests included. The
   scratch contract exempted those two, because `heartbeat()` resolved `mkdir`/`date` through
   `PATH`. The D5 heartbeat fix removes the gap, and with it the exemption.

N.3 is the clause that kills masking:

- a deleted guard lets its fixture reach a later guard, which prints a different reason;
- a deleted `exit` makes the run fall into a second refusal (two lines) or into the exec
  (`rc 0`);
- a deleted diagnostic leaves zero lines.

Only tagged lines are asserted. Shell error text such as `cd: …` varies with the bash version
and is not the wrapper's contract.

Reason texts are asserted as substrings, so no reason may contain another: if one did, a
fixture for the longer reason would also pass on the shorter one, and masking would be back.
They are pairwise non-containing today, and a static test keeps them so (5bis.7). They come
from the wrapper at `04dd6b51e4`:

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

Fixture rules, one carried over and five new:

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
- **Stamps are checked against a non-UTC zone** (new, coordinator ruling 2026-09-27). One
  positive fixture runs with `TZ=Asia/Makassar` in the env file and asserts that both stamps
  are within 120 s of UTC. Without it, a dropped `date -u` passes every contract.
- **The wrapper's stdin is `/dev/null`** (new, council round 1). `_run` passes
  `stdin=subprocess.DEVNULL`, as launchd does by default. Without it, a `redir` mutant reads
  whatever stdin pytest inherited, and its verdict depends on the terminal.
- **Every patched constant is pinned statically** (new, council round 1). `_patched_wrapper`
  rewrites every line `^KEY=` for the five `_PATCHABLE_KEYS`, re-asserts included, so a changed
  value on those lines is invisible to every run. `test_wrapper_ships_production_constants`
  asserts the production value of each such line in the blob. Its key set must equal
  `_PATCHABLE_KEYS`, so a sixth patchable key cannot be added without a pinned value.

### 5bis.5 Dispositions, and the decisions re-gate #2 asked for

There are only two dispositions, and each generated id carries its own.

- **MUST.** The mutant must be killed, by at least one of its `killed_by` tests.
- **EQUIVALENT.** No contracted observation can distinguish the mutant, and the entry carries
  a `reason`. S3 still runs it. If a test kills it, S3 FAILS: a killed "equivalent" mutant is
  a refuted claim, and the entry must become MUST with that test as its killer. The other
  direction, MUST to EQUIVALENT, is invisible to S3 by construction once the isolating fixture
  is gone, which is why every change to this file is a Gear-3 change (§5ter.5).

**Nothing is deferred.** Re-gate #2 allowed deferring `_is_semver`'s corpus to PR-2, and it
called P1–P5 out of scope. Both are MUST in PR-1 instead, for three reasons:

- S3 runs only the wrapper's own test file. A MUST entry whose killer lived in PR-2's
  installer tests would leave the wrapper's check red, or silently exempt, until PR-2 merged.
- Each label needs one small fixture (5bis.7). Re-gate #2's probes already showed that S1–S5 fail
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

There are seven EQUIVALENT entries, under five labels:

- **G0k** (`_wcbw_pin_bin=""`, `const:value`). `$2` is read only when `$1` is non-empty.
  `$1` is non-empty only on the pin path, where line 202 reassigns `_wcbw_pin_bin` before
  the handoff.
- **G1c** (`IFS=` in the NUL probe, `readopt#1:drop`). `read`'s status depends only on
  whether the delimiter comes before EOF. IFS shapes only the stored value, and that value is
  never read.
- **G7c** (`set +a`, `setopt:remove`). Its only effect is that the six re-asserted names are
  exported to the daemon too. The daemon module's only environment reads are in
  `DaemonConfig.from_env` (`wa_codex_daemon.py` at `04dd6b51e4`, lines 164–201): `WA_*` and
  `CODEX_HOME`. Its `codex --version` child inherits the environment (line 289, no `env=`).
  That the codex CLI reads none of the six names is a review judgement, not a measurement
  (council round 4); every contracted observation is identical over the 50 feasibility tests.
- **G9b**, three entries on `/bin/mkdir … || return 0` in `heartbeat`: `andor:drop-right`
  (the limb dropped), `exit:remove` (`|| :`, new with the generator) and `exit:value`
  (`|| return 1`). There is no errexit, and every caller ignores the status, so rc and control
  flow are identical. The only difference is one extra shell error line when the sidecar
  directory cannot be created, and no contract pins that line's absence. This holds only on
  the PR-1 target. At `04dd6b51e4`, `mkdir` and `date` came from `PATH`, and there the claim is
  false. Council round 1 (codex-gpt-5.6-sol) raised it, and its session ended before it could
  execute the check; the author then reproduced it. Under `PATH=/does-not-exist`, with the
  sidecar directory present, the shipped wrapper wrote no heartbeat, while the mutant wrote
  `starting` with an empty timestamp. The D5 heartbeat fix is what makes the label
  equivalent. The fourth member of the line, `andor:drop-left` (`return 0` alone: gate r4 H1),
  is MUST: the heartbeat is never written, and every contract-N test sees it.
- **G3f** (`exit:remove` of the arm's `return 1` in `_is_semver`, new with the generator). The
  `case` ends and the next command is the function's own `return 1` (line 87), so every input
  returns 1 as before.

On the PR-1 target all seven leave identical run records in every test of the file, as
§5ter.3 step 8 requires (5bis.8).

### 5bis.6 The inventory (rendered from the YAML)

Mode codes (the exact classification rule is §5ter.3 step 8):

- **FO**, fail-open: the daemon starts where the shipped wrapper refuses, or starts with a
  different binary, version or `PYTHONPATH`.
- **FC**, fail-closed-other-rc: a legitimate start is blocked, or the refusal's rc changes.
- **DX**, same-rc-other-diagnosis: same rc, but a different heartbeat or tagged line.
- **ST**, static: every killer is a test that reads the blob and never runs it. Used only for
  values the harness overwrites (5bis.4). What such a change does in production is not
  measured. A wrong `CODEX_PIN_FILE` would read as "no pin" and fall back to legacy, so treat
  ST as FO when weighing a survivor.
- **EQ**, equivalent.

One row per generated id, in S3's order: by line, then in the canonical order of 5bis.3.
`member` is the id's `<key>:<member>`. `line` is the line on the PR-1 target; the numbers are
the same on blob `4143a795d9`, where only lines 72 and 74 generate other ids (5bis.8). The
table holds 177 mutants: 170 MUST and 7 EQUIVALENT, with modes FO 50, FC 54, DX 58, ST 8 and
EQ 7.

<!-- d5-inventory:begin -->

| id                                                  | label | line | member           | mode | disposition | killed by                                                                                              |
| --------------------------------------------------- | ----- | ---- | ---------------- | ---- | ----------- | ------------------------------------------------------------------------------------------------------ |
| `2d510a6eb4e36076:setopt:remove`                    | G9a   | 47   | setopt:remove    | FO   | MUST        | `test_guilt_env_undefined_name_never_execs`                                                            |
| `82285122d3446bef@2d510a6eb4e36076:const:value`     | G0a   | 49   | const:value      | ST   | MUST        | `test_wrapper_ships_production_constants`                                                              |
| `93cf1180a8431270@2d510a6eb4e36076:const:value`     | G0b   | 50   | const:value      | ST   | MUST        | `test_wrapper_ships_production_constants`                                                              |
| `0ec6d675792920f3:const:value`                      | G0c   | 51   | const:value      | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `0ff33cfcfcad48ee@0ec6d675792920f3:const:value`     | G0d   | 52   | const:value      | ST   | MUST        | `test_wrapper_ships_production_constants`                                                              |
| `bf2870af16c0a446@0ec6d675792920f3:const:value`     | G0e   | 53   | const:value      | DX   | MUST        | `test_guilt_env_file_missing_refuses`                                                                  |
| `b148bfe29bbd3145@0ec6d675792920f3:const:value`     | G0f   | 54   | const:value      | DX   | MUST        | `test_guilt_env_file_missing_refuses`                                                                  |
| `7c75f442896ed2da@0ec6d675792920f3:const:value`     | G0g   | 55   | const:value      | DX   | MUST        | `test_guilt_env_file_missing_refuses`                                                                  |
| `7257ebff60419f4d:const:value`                      | G0h   | 63   | const:value      | ST   | MUST        | `test_wrapper_ships_production_constants`                                                              |
| `3f551b6a4a9f05ed:const:value`                      | G0i   | 64   | const:value      | ST   | MUST        | `test_wrapper_ships_production_constants`                                                              |
| `9c0148ab94570f73:andor:drop-left`                  | G9b   | 72   | andor:drop-left  | DX   | MUST        | `test_guilt_env_file_missing_refuses`                                                                  |
| `9c0148ab94570f73:andor:drop-right`                 | G9b   | 72   | andor:drop-right | EQ   | EQUIVALENT  | — (see reason)                                                                                         |
| `9c0148ab94570f73:exit:remove`                      | G9b   | 72   | exit:remove      | EQ   | EQUIVALENT  | — (see reason)                                                                                         |
| `9c0148ab94570f73:exit:value`                       | G9b   | 72   | exit:value       | EQ   | EQUIVALENT  | — (see reason)                                                                                         |
| `9c0148ab94570f73:abspath:strip`                    | G9j   | 72   | abspath:strip    | DX   | MUST        | `[nonexistent]`                                                                                        |
| `919178aeb2601828:abspath:strip`                    | G9k   | 74   | abspath:strip    | DX   | MUST        | `[nonexistent]`                                                                                        |
| `919178aeb2601828:dateopt:drop`                     | G9l   | 74   | dateopt:drop     | DX   | MUST        | `test_stamps_are_utc_under_a_non_utc_tz`                                                               |
| `167483363793d9b2:alt#1:drop`                       | G3a   | 84   | alt#1:drop       | FO   | MUST        | `[semver_alpha_planted]`                                                                               |
| `167483363793d9b2:alt#2:drop`                       | G3b   | 84   | alt#2:drop       | FO   | MUST        | `[semver_leading_dot_planted]`                                                                         |
| `167483363793d9b2:alt#3:drop`                       | G3c   | 84   | alt#3:drop       | FO   | MUST        | `[semver_trailing_dot_planted]`                                                                        |
| `167483363793d9b2:alt#4:drop`                       | G3d   | 84   | alt#4:drop       | FO   | MUST        | `[semver_empty_field_planted]`                                                                         |
| `167483363793d9b2:alt#5:drop`                       | G3e   | 84   | alt#5:drop       | FO   | MUST        | `[semver_four_fields_planted]`                                                                         |
| `167483363793d9b2:exit:remove`                      | G3f   | 84   | exit:remove      | EQ   | EQUIVALENT  | — (see reason)                                                                                         |
| `167483363793d9b2:exit:value`                       | G3f   | 84   | exit:value       | FO   | MUST        | `[traversal_escape_planted]`, `[semver_alpha_planted]`                                                 |
| `ac6dc4f641d4266b:alt:widen`                        | G3g   | 85   | alt:widen        | FO   | MUST        | `[bad_semver_planted]`                                                                                 |
| `ac6dc4f641d4266b:exit:remove`                      | G3g   | 85   | exit:remove      | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `ac6dc4f641d4266b:exit:value`                       | G3g   | 85   | exit:value       | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `486d9affb60dbb00:exit:remove`                      | G3h   | 87   | exit:remove      | FO   | MUST        | `[bad_semver_planted]`                                                                                 |
| `486d9affb60dbb00:exit:value`                       | G3h   | 87   | exit:value       | FO   | MUST        | `[bad_semver_planted]`                                                                                 |
| `b877414ba0f87feb:cond:never`                       | G9c   | 91   | cond:never       | FC   | MUST        | `test_guilt_env_file_missing_refuses`                                                                  |
| `b877414ba0f87feb:cond:always`                      | G9c   | 91   | cond:always      | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `b877414ba0f87feb:neg:drop`                         | G9c   | 91   | neg:drop         | FC   | MUST        | `test_innocence_valid_pin_overrides_env`, `test_guilt_env_file_missing_refuses`                        |
| `c1fade95b3813c56:diag:remove`                      | G9c   | 92   | diag:remove      | DX   | MUST        | `test_guilt_env_file_missing_refuses`                                                                  |
| `54cd50f09e27ecc0:hb:remove`                        | G9c   | 93   | hb:remove        | DX   | MUST        | `test_guilt_env_file_missing_refuses`                                                                  |
| `8526388771f87b84@54cd50f09e27ecc0:exit:remove`     | G9c   | 94   | exit:remove      | FC   | MUST        | `test_guilt_env_file_missing_refuses`                                                                  |
| `8526388771f87b84@54cd50f09e27ecc0:exit:value`      | G9c   | 94   | exit:value       | FC   | MUST        | `test_guilt_env_file_missing_refuses`                                                                  |
| `bcb17d0bb9f3e67c:cond:never`                       | G9d   | 96   | cond:never       | FO   | MUST        | `test_guilt_env_placeholders_refuse`                                                                   |
| `bcb17d0bb9f3e67c:cond:always`                      | G9d   | 96   | cond:always      | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `020824d34a8091ee:diag:remove`                      | G9d   | 97   | diag:remove      | DX   | MUST        | `test_guilt_env_placeholders_refuse`                                                                   |
| `ec36a5a8c358f487:hb:remove`                        | G9d   | 98   | hb:remove        | DX   | MUST        | `test_guilt_env_placeholders_refuse`                                                                   |
| `8526388771f87b84@ec36a5a8c358f487:exit:remove`     | G9d   | 99   | exit:remove      | FO   | MUST        | `test_guilt_env_placeholders_refuse`                                                                   |
| `8526388771f87b84@ec36a5a8c358f487:exit:value`      | G9d   | 99   | exit:value       | FC   | MUST        | `test_guilt_env_placeholders_refuse`                                                                   |
| `a591dbf70bd50123:cond:never`                       | G6    | 134  | cond:never       | DX   | MUST        | `test_guilt_unsearchable_runtime_dir_refuses_not_legacy`                                               |
| `a591dbf70bd50123:cond:always`                      | G6    | 134  | cond:always      | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `a591dbf70bd50123:test#1:true`                      | G6a   | 134  | test#1:true      | DX   | MUST        | `test_runtime_dir_absent_is_legacy_then_cd_refuses`                                                    |
| `a591dbf70bd50123:test#1:false`                     | G6a   | 134  | test#1:false     | DX   | MUST        | `test_guilt_unsearchable_runtime_dir_refuses_not_legacy`                                               |
| `a591dbf70bd50123:test#2:true`                      | G6b   | 134  | test#2:true      | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `a591dbf70bd50123:test#2:false`                     | G6b   | 134  | test#2:false     | DX   | MUST        | `test_guilt_unsearchable_runtime_dir_refuses_not_legacy`                                               |
| `a591dbf70bd50123:andor:drop-left`                  | G6a   | 134  | andor:drop-left  | DX   | MUST        | `test_runtime_dir_absent_is_legacy_then_cd_refuses`                                                    |
| `a591dbf70bd50123:andor:drop-right`                 | G6b   | 134  | andor:drop-right | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `a591dbf70bd50123:neg:drop`                         | G6b   | 134  | neg:drop         | FC   | MUST        | `test_innocence_valid_pin_overrides_env`, `test_guilt_unsearchable_runtime_dir_refuses_not_legacy`     |
| `3dd6763e15577a2b:diag:remove`                      | G6    | 135  | diag:remove      | DX   | MUST        | `test_guilt_unsearchable_runtime_dir_refuses_not_legacy`                                               |
| `e7eb6aa9779abace@3dd6763e15577a2b:hb:remove`       | G6    | 136  | hb:remove        | DX   | MUST        | `test_guilt_unsearchable_runtime_dir_refuses_not_legacy`                                               |
| `8526388771f87b84@3dd6763e15577a2b:exit:remove`     | G6    | 137  | exit:remove      | DX   | MUST        | `test_guilt_unsearchable_runtime_dir_refuses_not_legacy`                                               |
| `8526388771f87b84@3dd6763e15577a2b:exit:value`      | G6    | 137  | exit:value       | FC   | MUST        | `test_guilt_unsearchable_runtime_dir_refuses_not_legacy`                                               |
| `68c85aa55e51903d:const:value`                      | G0j   | 140  | const:value      | FO   | MUST        | `test_innocence_missing_pin_is_legacy`                                                                 |
| `b259e08545de7d9b:const:value`                      | G0k   | 141  | const:value      | EQ   | EQUIVALENT  | — (see reason)                                                                                         |
| `f38e1e3bd15a938d:cond:never`                       | G4a   | 142  | cond:never       | FO   | MUST        | `[symlink_pin]`                                                                                        |
| `f38e1e3bd15a938d:cond:always`                      | G4a   | 142  | cond:always      | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `cc48e9e0b1618624:diag:remove`                      | G4a   | 143  | diag:remove      | DX   | MUST        | `[symlink_pin]`                                                                                        |
| `e7eb6aa9779abace@cc48e9e0b1618624:hb:remove`       | G4a   | 144  | hb:remove        | DX   | MUST        | `[symlink_pin]`                                                                                        |
| `8526388771f87b84@cc48e9e0b1618624:exit:remove`     | G4a   | 145  | exit:remove      | FO   | MUST        | `[symlink_pin]`                                                                                        |
| `8526388771f87b84@cc48e9e0b1618624:exit:value`      | G4a   | 145  | exit:value       | FC   | MUST        | `[symlink_pin]`                                                                                        |
| `56256af7dea49700:cond:never`                       | G4d   | 146  | cond:never       | FO   | MUST        | `test_innocence_valid_pin_overrides_env`, `[bad_semver_planted]`                                       |
| `56256af7dea49700:cond:always`                      | G4d   | 146  | cond:always      | FC   | MUST        | `test_innocence_missing_pin_is_legacy`                                                                 |
| `634103c1b53d95f7:cond:never`                       | G4e   | 147  | cond:never       | FC   | MUST        | `[directory]`, `[dev_null]`                                                                            |
| `634103c1b53d95f7:cond:always`                      | G4e   | 147  | cond:always      | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `634103c1b53d95f7:neg:drop`                         | G4e   | 147  | neg:drop         | FC   | MUST        | `test_innocence_valid_pin_overrides_env`, `[directory]`, `[dev_null]`                                  |
| `a496ea1ec476fd67:diag:remove`                      | G4e   | 148  | diag:remove      | DX   | MUST        | `[directory]`                                                                                          |
| `e7eb6aa9779abace@a496ea1ec476fd67:hb:remove`       | G4e   | 149  | hb:remove        | DX   | MUST        | `[directory]`                                                                                          |
| `8526388771f87b84@a496ea1ec476fd67:exit:remove`     | G4e   | 150  | exit:remove      | FC   | MUST        | `[directory]`, `[dev_null]`                                                                            |
| `8526388771f87b84@a496ea1ec476fd67:exit:value`      | G4e   | 150  | exit:value       | FC   | MUST        | `[directory]`, `[dev_null]`                                                                            |
| `ab69b3bd94339e85:cond:never`                       | G4f   | 152  | cond:never       | DX   | MUST        | `test_guilt_mode_000_pin_reports_unreadable_not_line_count`                                            |
| `ab69b3bd94339e85:cond:always`                      | G4f   | 152  | cond:always      | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `ab69b3bd94339e85:neg:drop`                         | G4f   | 152  | neg:drop         | FC   | MUST        | `test_innocence_valid_pin_overrides_env`, `test_guilt_mode_000_pin_reports_unreadable_not_line_count`  |
| `51fb56231344763b:diag:remove`                      | G4f   | 153  | diag:remove      | DX   | MUST        | `test_guilt_mode_000_pin_reports_unreadable_not_line_count`                                            |
| `e7eb6aa9779abace@51fb56231344763b:hb:remove`       | G4f   | 154  | hb:remove        | DX   | MUST        | `test_guilt_mode_000_pin_reports_unreadable_not_line_count`                                            |
| `8526388771f87b84@51fb56231344763b:exit:remove`     | G4f   | 155  | exit:remove      | DX   | MUST        | `test_guilt_mode_000_pin_reports_unreadable_not_line_count`                                            |
| `8526388771f87b84@51fb56231344763b:exit:value`      | G4f   | 155  | exit:value       | FC   | MUST        | `test_guilt_mode_000_pin_reports_unreadable_not_line_count`                                            |
| `71a19acda9e9d654:cond:never`                       | G1    | 171  | cond:never       | FO   | MUST        | `[nul_same_line_planted]`                                                                              |
| `71a19acda9e9d654:cond:always`                      | G1    | 171  | cond:always      | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `71a19acda9e9d654:readopt#1:drop`                   | G1c   | 171  | readopt#1:drop   | EQ   | EQUIVALENT  | — (see reason)                                                                                         |
| `71a19acda9e9d654:readopt#2:drop`                   | G1b   | 171  | readopt#2:drop   | DX   | MUST        | `[nul_after_backslash_planted]`                                                                        |
| `71a19acda9e9d654:readopt#3:drop`                   | G1a   | 171  | readopt#3:drop   | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `71a19acda9e9d654:redir:drop`                       | G1d   | 171  | redir:drop       | FO   | MUST        | `[nul_same_line_planted]`, `[embedded_nul]`                                                            |
| `d3563a941a515024:diag:remove`                      | G1    | 172  | diag:remove      | DX   | MUST        | `[nul_same_line_planted]`                                                                              |
| `e7eb6aa9779abace@d3563a941a515024:hb:remove`       | G1    | 173  | hb:remove        | DX   | MUST        | `[nul_same_line_planted]`                                                                              |
| `8526388771f87b84@d3563a941a515024:exit:remove`     | G1    | 174  | exit:remove      | FO   | MUST        | `[nul_same_line_planted]`                                                                              |
| `8526388771f87b84@d3563a941a515024:exit:value`      | G1    | 174  | exit:value       | FC   | MUST        | `[nul_same_line_planted]`                                                                              |
| `f92099df19bdd5b5:cond:never`                       | G2d   | 178  | cond:never       | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `f92099df19bdd5b5:test:false`                       | G2a   | 178  | test:false       | FO   | MUST        | `[two_lines_last_unterminated_planted]`, `test_innocence_single_line_without_trailing_newline_applies` |
| `f92099df19bdd5b5:andor:drop-left`                  | G2a   | 178  | andor:drop-left  | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `f92099df19bdd5b5:andor:drop-right`                 | G2a   | 178  | andor:drop-right | FO   | MUST        | `[two_lines_last_unterminated_planted]`, `test_innocence_single_line_without_trailing_newline_applies` |
| `f92099df19bdd5b5:readopt#1:drop`                   | G2b   | 178  | readopt#1:drop   | FO   | MUST        | `[trailing_space_planted]`, `[leading_tab_planted]`                                                    |
| `f92099df19bdd5b5:readopt#2:drop`                   | G2c   | 178  | readopt#2:drop   | FO   | MUST        | `[backslash_in_version_planted]`                                                                       |
| `a9f7da6fc4270e96:redir:drop`                       | G2e   | 181  | redir:drop       | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `db5f7e40037a4650:cond:never`                       | G2    | 182  | cond:never       | FO   | MUST        | `[two_lines_diff_versions_planted]`                                                                    |
| `db5f7e40037a4650:cond:always`                      | G2    | 182  | cond:always      | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `db5f7e40037a4650:test:relop`                       | G2    | 182  | test:relop       | DX   | MUST        | `[empty]`                                                                                              |
| `04d80b64424cad2d:diag:remove`                      | G2    | 183  | diag:remove      | DX   | MUST        | `[two_lines_diff_versions_planted]`                                                                    |
| `e7eb6aa9779abace@04d80b64424cad2d:hb:remove`       | G2    | 184  | hb:remove        | DX   | MUST        | `[two_lines_diff_versions_planted]`                                                                    |
| `8526388771f87b84@04d80b64424cad2d:exit:remove`     | G2    | 185  | exit:remove      | FO   | MUST        | `[two_lines_diff_versions_planted]`                                                                    |
| `8526388771f87b84@04d80b64424cad2d:exit:value`      | G2    | 185  | exit:value       | FC   | MUST        | `[two_lines_diff_versions_planted]`                                                                    |
| `c21200da23f1dc4e:alt:widen`                        | G4b   | 188  | alt:widen        | FO   | MUST        | `[bare_version_planted]`                                                                               |
| `69e11195653e133e:alt:neutralise`                   | G4c   | 191  | alt:neutralise   | DX   | MUST        | `[bare_version_planted]`, `[unknown_key]`                                                              |
| `5d20bc7c8d9090c8:diag:remove`                      | G4c   | 192  | diag:remove      | DX   | MUST        | `[bare_version_planted]`                                                                               |
| `e7eb6aa9779abace@5d20bc7c8d9090c8:hb:remove`       | G4c   | 193  | hb:remove        | DX   | MUST        | `[bare_version_planted]`                                                                               |
| `8526388771f87b84@5d20bc7c8d9090c8:exit:remove`     | G4c   | 194  | exit:remove      | DX   | MUST        | `[bare_version_planted]`                                                                               |
| `8526388771f87b84@5d20bc7c8d9090c8:exit:value`      | G4c   | 194  | exit:value       | FC   | MUST        | `[bare_version_planted]`                                                                               |
| `af5687a8e077a442:cond:never`                       | G3    | 197  | cond:never       | FO   | MUST        | `[bad_semver_planted]`, `[traversal_escape_planted]`                                                   |
| `af5687a8e077a442:cond:always`                      | G3    | 197  | cond:always      | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `af5687a8e077a442:neg:drop`                         | G3    | 197  | neg:drop         | FO   | MUST        | `[bad_semver_planted]`, `test_innocence_valid_pin_overrides_env`                                       |
| `bc42b08a01b4b06e:diag:remove`                      | G3    | 198  | diag:remove      | DX   | MUST        | `[bad_semver_planted]`                                                                                 |
| `e7eb6aa9779abace@bc42b08a01b4b06e:hb:remove`       | G3    | 199  | hb:remove        | DX   | MUST        | `[bad_semver_planted]`                                                                                 |
| `8526388771f87b84@bc42b08a01b4b06e:exit:remove`     | G3    | 200  | exit:remove      | FO   | MUST        | `[bad_semver_planted]`, `[traversal_escape_planted]`                                                   |
| `8526388771f87b84@bc42b08a01b4b06e:exit:value`      | G3    | 200  | exit:value       | FC   | MUST        | `[bad_semver_planted]`, `[traversal_escape_planted]`                                                   |
| `1447089bdc0e8175:cond:never`                       | G5    | 206  | cond:never       | FO   | MUST        | `[bin_missing]`                                                                                        |
| `1447089bdc0e8175:cond:always`                      | G5    | 206  | cond:always      | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `1447089bdc0e8175:test#1:true`                      | G5a   | 206  | test#1:true      | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `1447089bdc0e8175:test#1:false`                     | G5a   | 206  | test#1:false     | FO   | MUST        | `[bin_is_directory]`                                                                                   |
| `1447089bdc0e8175:test#2:true`                      | G5b   | 206  | test#2:true      | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `1447089bdc0e8175:test#2:false`                     | G5b   | 206  | test#2:false     | FO   | MUST        | `[bin_not_executable_planted]`                                                                         |
| `1447089bdc0e8175:andor:drop-left`                  | G5a   | 206  | andor:drop-left  | FO   | MUST        | `[bin_is_directory]`                                                                                   |
| `1447089bdc0e8175:andor:drop-right`                 | G5b   | 206  | andor:drop-right | FO   | MUST        | `[bin_not_executable_planted]`                                                                         |
| `1447089bdc0e8175:neg#1:drop`                       | G5a   | 206  | neg#1:drop       | FO   | MUST        | `test_innocence_valid_pin_overrides_env`, `[bin_is_directory]`                                         |
| `1447089bdc0e8175:neg#2:drop`                       | G5b   | 206  | neg#2:drop       | FO   | MUST        | `test_innocence_valid_pin_overrides_env`, `[bin_not_executable_planted]`                               |
| `2e93e4cbc19c5ccb:diag:remove`                      | G5    | 207  | diag:remove      | DX   | MUST        | `[bin_missing]`                                                                                        |
| `e7eb6aa9779abace@2e93e4cbc19c5ccb:hb:remove`       | G5    | 208  | hb:remove        | DX   | MUST        | `[bin_missing]`                                                                                        |
| `8526388771f87b84@2e93e4cbc19c5ccb:exit:remove`     | G5    | 209  | exit:remove      | FO   | MUST        | `[bin_missing]`                                                                                        |
| `8526388771f87b84@2e93e4cbc19c5ccb:exit:value`      | G5    | 209  | exit:value       | FC   | MUST        | `[bin_missing]`                                                                                        |
| `aa434ce1dbd99a3f:diag:remove`                      | G7h   | 212  | diag:remove      | DX   | MUST        | `test_innocence_missing_pin_is_legacy`                                                                 |
| `015f150fe65d6e68:setopt:remove`                    | G7a   | 218  | setopt:remove    | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `cfcc9993533dc30d:setopt:remove`                    | G7b   | 220  | setopt:remove    | FO   | MUST        | `test_innocence_missing_pin_is_legacy`                                                                 |
| `c34b923460d94846:setopt:remove`                    | G7c   | 222  | setopt:remove    | EQ   | EQUIVALENT  | — (see reason)                                                                                         |
| `82285122d3446bef@c34b923460d94846:reassert:remove` | G8a   | 231  | reassert:remove  | DX   | MUST        | `test_guilt_env_cannot_clobber_post_source_literals`                                                   |
| `82285122d3446bef@c34b923460d94846:reassert:value`  | G8a   | 231  | reassert:value   | ST   | MUST        | `test_wrapper_ships_production_constants`                                                              |
| `93cf1180a8431270@c34b923460d94846:reassert:remove` | G8b   | 232  | reassert:remove  | FO   | MUST        | `test_guilt_env_cannot_clobber_post_source_literals`                                                   |
| `93cf1180a8431270@c34b923460d94846:reassert:value`  | G8b   | 232  | reassert:value   | ST   | MUST        | `test_wrapper_ships_production_constants`                                                              |
| `0ff33cfcfcad48ee@c34b923460d94846:reassert:remove` | G8c   | 233  | reassert:remove  | FO   | MUST        | `test_guilt_env_cannot_clobber_post_source_literals`                                                   |
| `0ff33cfcfcad48ee@c34b923460d94846:reassert:value`  | G8c   | 233  | reassert:value   | ST   | MUST        | `test_wrapper_ships_production_constants`                                                              |
| `bf2870af16c0a446@c34b923460d94846:reassert:remove` | G8d   | 234  | reassert:remove  | DX   | MUST        | `test_guilt_env_cannot_clobber_post_source_literals`                                                   |
| `bf2870af16c0a446@c34b923460d94846:reassert:value`  | G8d   | 234  | reassert:value   | DX   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `b148bfe29bbd3145@c34b923460d94846:reassert:remove` | G8e   | 235  | reassert:remove  | DX   | MUST        | `test_guilt_env_cannot_clobber_post_source_literals`                                                   |
| `b148bfe29bbd3145@c34b923460d94846:reassert:value`  | G8e   | 235  | reassert:value   | DX   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `7c75f442896ed2da@c34b923460d94846:reassert:remove` | G8f   | 236  | reassert:remove  | DX   | MUST        | `test_guilt_env_cannot_clobber_post_source_literals`                                                   |
| `7c75f442896ed2da@c34b923460d94846:reassert:value`  | G8f   | 236  | reassert:value   | DX   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `19a916d8fe196194:cond:never`                       | G9e   | 251  | cond:never       | FO   | MUST        | `test_kill_switch_stops_without_exec`                                                                  |
| `19a916d8fe196194:cond:always`                      | G9e   | 251  | cond:always      | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `19a916d8fe196194:default:drop`                     | G9f   | 251  | default:drop     | FC   | MUST        | `test_innocence_env_without_kill_switch_key_applies`                                                   |
| `9111f81d771c3ba0:diag:remove`                      | G9e   | 252  | diag:remove      | DX   | MUST        | `test_kill_switch_stops_without_exec`                                                                  |
| `3fb04a4b6a09dd60:hb:remove`                        | G9e   | 253  | hb:remove        | DX   | MUST        | `test_kill_switch_stops_without_exec`                                                                  |
| `c22995adc29757a9:exit:remove`                      | G9e   | 254  | exit:remove      | FO   | MUST        | `test_kill_switch_stops_without_exec`                                                                  |
| `c22995adc29757a9:exit:value`                       | G9e   | 254  | exit:value       | FC   | MUST        | `test_kill_switch_stops_without_exec`                                                                  |
| `c3bfad593fcd3864:cond:never`                       | G9g   | 257  | cond:never       | FC   | MUST        | `test_guilt_venv_missing_refuses`                                                                      |
| `c3bfad593fcd3864:cond:always`                      | G9g   | 257  | cond:always      | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `c3bfad593fcd3864:neg:drop`                         | G9g   | 257  | neg:drop         | FC   | MUST        | `test_innocence_valid_pin_overrides_env`, `test_guilt_venv_missing_refuses`                            |
| `535fcf39e411110e:diag:remove`                      | G9g   | 258  | diag:remove      | DX   | MUST        | `test_guilt_venv_missing_refuses`                                                                      |
| `a1075c3ed7b74e83:hb:remove`                        | G9g   | 259  | hb:remove        | DX   | MUST        | `test_guilt_venv_missing_refuses`                                                                      |
| `8526388771f87b84@a1075c3ed7b74e83:exit:remove`     | G9g   | 260  | exit:remove      | FC   | MUST        | `test_guilt_venv_missing_refuses`                                                                      |
| `8526388771f87b84@a1075c3ed7b74e83:exit:value`      | G9g   | 260  | exit:value       | FC   | MUST        | `test_guilt_venv_missing_refuses`                                                                      |
| `818836c375d5c9cc:andor:drop-left`                  | G9h   | 263  | andor:drop-left  | FC   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `818836c375d5c9cc:andor:drop-right`                 | G9h   | 263  | andor:drop-right | FO   | MUST        | `test_runtime_dir_absent_is_legacy_then_cd_refuses`                                                    |
| `818836c375d5c9cc:exit:remove`                      | G9h   | 263  | exit:remove      | FO   | MUST        | `test_runtime_dir_absent_is_legacy_then_cd_refuses`                                                    |
| `818836c375d5c9cc:exit:value`                       | G9h   | 263  | exit:value       | FC   | MUST        | `test_runtime_dir_absent_is_legacy_then_cd_refuses`                                                    |
| `818836c375d5c9cc:hb:remove`                        | G9h   | 263  | hb:remove        | DX   | MUST        | `test_runtime_dir_absent_is_legacy_then_cd_refuses`                                                    |
| `422567c140a13db3:reassert:remove`                  | G8g   | 264  | reassert:remove  | FO   | MUST        | `test_guilt_env_cannot_clobber_pythonpath`                                                             |
| `422567c140a13db3:reassert:value`                   | G8g   | 264  | reassert:value   | FO   | MUST        | `test_guilt_env_cannot_clobber_pythonpath`                                                             |
| `a0e431e3489db7f5:hb:remove`                        | G9i   | 266  | hb:remove        | DX   | MUST        | `test_guilt_env_cannot_clobber_post_source_literals`                                                   |
| `858e69f9cd802136:cond:never`                       | G7d   | 268  | cond:never       | FO   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `858e69f9cd802136:cond:always`                      | G7d   | 268  | cond:always      | FO   | MUST        | `test_innocence_missing_pin_is_legacy`                                                                 |
| `ad56e24af0b5d760:diag:remove`                      | G7e   | 269  | diag:remove      | DX   | MUST        | `test_pin_applied_log_line`                                                                            |
| `ad56e24af0b5d760:abspath:strip`                    | G7e   | 269  | abspath:strip    | DX   | MUST        | `[nonexistent]`                                                                                        |
| `ad56e24af0b5d760:dateopt:drop`                     | G7i   | 269  | dateopt:drop     | DX   | MUST        | `test_stamps_are_utc_under_a_non_utc_tz`                                                               |
| `b9a04673c49fc0c4:exec:remove`                      | G7f   | 270  | exec:remove      | FO   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `b9a04673c49fc0c4:exec:env-drop`                    | G7f   | 270  | exec:env-drop    | FO   | MUST        | `test_innocence_valid_pin_overrides_env`                                                               |
| `b9a04673c49fc0c4:abspath:strip`                    | G7f   | 270  | abspath:strip    | FC   | MUST        | `test_guilt_env_path_cannot_disable_the_pin[nonexistent]`                                              |
| `b044fcf5065694b5:exec:remove`                      | G7g   | 273  | exec:remove      | FC   | MUST        | `test_innocence_missing_pin_is_legacy`                                                                 |

Totals: 136 sites, 177 mutants (170 MUST, 7 EQUIVALENT) under 71 labels. Declared modes: 50 FO, 54 FC, 58 DX, 8 ST, 7 EQ.

<!-- d5-inventory:end -->

### 5bis.7 Fixtures that PR-1 adds or changes

New. N and P refer to the contracts in 5bis.4:

| Test or param id                                                                                                                                          | Label(s)                         | Shape                                                                                            | Expected                                                                                                                                      |
| --------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `[nul_after_backslash_planted]`                                                                                                                           | G1b                              | bytes `WA_CODEX_CLI_VERSION_PIN=9.9.9\`, NUL, `JUNK`, LF; `9.9.9` planted                        | N: `pin file contains a NUL byte`                                                                                                             |
| `[two_lines_last_unterminated_planted]`                                                                                                                   | G2a                              | `…=1.1.1` LF `…=9.9.9`, no final LF; both planted                                                | N: `must carry exactly one line`                                                                                                              |
| `[trailing_space_planted]`                                                                                                                                | G2b                              | `…=9.9.9 ` LF; planted                                                                           | N: `not exact semver`                                                                                                                         |
| `[leading_tab_planted]`                                                                                                                                   | G2b                              | TAB `…=9.9.9` LF; planted                                                                        | N: `unrecognized line`                                                                                                                        |
| `[backslash_in_version_planted]`                                                                                                                          | G2c                              | `…=9.9.\9` LF; `9.9.9` planted                                                                   | N: `not exact semver`                                                                                                                         |
| `[semver_alpha_planted]`, `[semver_leading_dot_planted]`, `[semver_trailing_dot_planted]`, `[semver_empty_field_planted]`, `[semver_four_fields_planted]` | G3a–G3e                          | `a.b.c`, `.1.2`, `1.2.`, `1..2`, `1.2.3.4`, each planted at its own derived path                 | N: `not exact semver`                                                                                                                         |
| `test_innocence_single_line_without_trailing_newline_applies`                                                                                             | G2a                              | `…=9.9.9` with no LF; planted                                                                    | P: applied `9.9.9`                                                                                                                            |
| `test_guilt_env_cannot_clobber_pythonpath`                                                                                                                | G8g                              | env `PYTHONPATH=/nonexistent-evil-pythonpath`; valid pin                                         | P, and the stub's `PYTHONPATH` equals the wrapper's `RUNTIME_DIR`                                                                             |
| `test_guilt_env_undefined_name_never_execs`                                                                                                               | G9a                              | env line `WA_CODEX_MODEL=$WA_CODEX_UNDEFINED_FOR_TEST`; valid pin                                | `rc != 0`, the stub did not run, no `starting` heartbeat. This pins today's `set -u` stop; a later 78-plus-heartbeat refusal would still pass |
| `test_guilt_env_file_missing_refuses`                                                                                                                     | G9c                              | no env file, no pin                                                                              | N: heartbeat note `env file missing`, reason `env file missing`                                                                               |
| `test_guilt_env_placeholders_refuse`                                                                                                                      | G9d                              | env `WA_BROKER_KEY=__FILL_ME__`                                                                  | N: heartbeat note `env placeholders unfilled`, reason `__FILL_ME__ placeholders`                                                              |
| `test_kill_switch_stops_without_exec`                                                                                                                     | G9e                              | env `WA_CODEX_BROKER_ENABLED=false`; valid pin planted                                           | N with rc 0: heartbeat `disabled`/`kill switch`, reason `kill switch active`                                                                  |
| `test_innocence_env_without_kill_switch_key_applies`                                                                                                      | G9f                              | env without `WA_CODEX_BROKER_ENABLED`; valid pin                                                 | P                                                                                                                                             |
| `test_guilt_venv_missing_refuses`                                                                                                                         | G9g                              | `VENV_PY` patched to a missing path; valid pin                                                   | N: heartbeat note `venv python missing`, reason `venv python missing or not executable`                                                       |
| `test_runtime_dir_absent_is_legacy_then_cd_refuses`                                                                                                       | G6a, G9h                         | `RUNTIME_DIR` patched to a path that does not exist; no pin; the stub `VENV_PY` lives outside it | rc 78, heartbeat `refused`/`cd failed`, exactly one tagged line (the legacy line), the stub did not run                                       |
| `test_wrapper_ships_production_constants`                                                                                                                 | G0a, G0b, G0d, G0h, G0i, G8a–G8c | static: every `^KEY=` line of the five `_PATCHABLE_KEYS`, re-asserts included                    | each equals its production value; the pinned key set equals `_PATCHABLE_KEYS`                                                                 |
| `test_refusal_reasons_are_pairwise_non_containing`                                                                                                        | (5bis.4)                         | static: the 13 reason texts                                                                      | 13 distinct texts, none a substring of another                                                                                                |
| `test_stamps_are_utc_under_a_non_utc_tz`                                                                                                                  | G7i, G9l                         | env `TZ=Asia/Makassar`; valid pin                                                                | P, and both the heartbeat `ts` and the proof line's stamp lie within 120 s of the test's own UTC clock                                        |

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
- Every positive test asserts contract P, the two hostile-PATH tests included (their
  heartbeat exemption is gone with the D5 heartbeat fix).
- `_DUMP_ENV_STUB` prints `PYTHONPATH`. `_run` passes `stdin=subprocess.DEVNULL` and gains the
  `WCBW_RUN_LOG` hook (5ter.2).

### 5bis.8 What the `04dd6b51e4` suite kills today (measured 2026-09-27)

Setup: the scratch prototype of the generator route (non-normative), on M5 with bash 3.2.57,
against the 28-test suite and the wrapper at `04dd6b51e4`. S3 generates 175 mutants there,
two fewer than on the target, because lines 72 and 74 have no `abspath` site. Their
dispositions are the committed YAML's, carried by line, key and member (lines 72 and 74 have
other ids at `04dd6b51e4`).

Results:

- 134 sites and 175 mutants, with no `SPAN` and no `SYNTAX`;
- the baseline passed 28 of 28;
- 105 killed and 70 survived: 63 MUST under 38 labels, plus the 7 EQUIVALENT. No EQUIVALENT
  mutant was killed;
- six MUST mutants were killed only by tests other than their declared killers. At
  `04dd6b51e4` those killers either do not exist yet or do not yet assert contracts N and P:
  the `value` members of G0f, G0g and G8d–G8f, and G9b's `drop-left`.

The schema-1 mutants keep their verdicts: of the 146 that apply at `04dd6b51e4`, 80 are
killed and 66 survive (61 MUST in 38 rows, 5 EQUIVALENT), as gate r3 measured. Of the 29
generator-only members, 25 are killed, most of them always-refusing ones that any innocence
test catches. Four survive: G6a's `test#1:true` and G2a's `test:false` (MUST: the D02 and D10
fixtures are not in the 28-test suite, and the second is the D10 limb deletion in its other
form), plus the two new EQUIVALENT removals.

Surviving MUST mutants by label, named by re-gate #2:

- G2a (D10), G2b (D25), G2c (D26) and G6a (D02);
- G3a–G3e (S1–S5);
- G9c, G9d, G9e, G9g and G9h (P1–P5), every member of each that is not always-refusing.

In no earlier table (round 1):

- G1b (the probe's `-r`);
- the diagnostic removals of G1, G2, G3, G4a, G4e and G5 (no test asserts a reason);
- G4c, the key case's catch-all arm (its `neutralise`, diagnostic and exit members);
- G4f's heartbeat removal (the mode-000 test never reads the heartbeat);
- G8g (`export PYTHONPATH`), both members;
- G9a (`set -u`);
- G9f (the kill switch's `:-true` default; every test sets the key).

Found by council round 1:

- G0a, G0b, G0d, G0h, G0i and the `value` members of G8a–G8c. These are the five constants
  the harness patches, so a changed value is invisible to every run (ST);
- G0e (`TAG` before the source; no test asserts a refusal's tag).

Found by council round 2: G7e's `abspath:strip` (the proof line's `/bin/date`; no test asserts
its stamp). Added on the coordinator's ruling: G7i and G9l, `dateopt:drop` (a dropped
`date -u`; no test runs under a non-UTC zone). Added by gate r3: G2's `relop` (no test asserts
the empty file's reason) and the `value` members of G9c, G9d, G9e, G9g and G9h (the P1–P5
fixtures are not in the 28-test suite).

**Feasibility.** The same prototype ran S3's steps 1–8 in full on the PR-1 target
(`04dd6b51e4` plus the D5 heartbeat fix), against a scratch suite of 50 tests that applies
5bis.4 and 5bis.7:

- 136 sites and 177 generated mutants, all annotated, with no `SPAN`, `LINES` or `SYNTAX`;
- the baseline passed 50 of 50;
- all 170 MUST mutants were killed, each by a test in its `killed_by` list, and every
  `killed_by` entry matched exactly one collected test;
- the 7 EQUIVALENT mutants survived, and left identical run records in all 47 tests that run
  the wrapper;
- all 177 declared modes equal the measured ones, with 0 errors of any code;
- wall time: 2 to 5 minutes on 5 workers (2026-09-27T04:35:04Z–04:37:14Z at load average 13 to
  20; the re-run on the council's fixes, 05:15:40Z–05:20:27Z at 21 to 38, same verdicts).
  The schema-1 runs took about 5 minutes for 132 mutants at a load average near 7,
  17 minutes for 130 near 35, and 24 minutes for the 148 of gate r3 between 35 and 130.

No fixture beyond 5bis.7 was needed: the 29 generator-only members die on the same 50 tests.

**Modes: measured, not predicted.** After the corrections below, every declared mode equals
the measured one. The declarations were not independent predictions, and S3 does not claim
they were. What S3 guarantees is that a declared mode can never drift from the measured one
later. The corrections:

- Round 1, six mutants. G4e/c and G4e/x were declared DX and measured FC. G7b/stmt, G7d/true
  and G8b/stmt were declared FC and measured FO. G8g/stmt was declared DX and measured FO.
- Round 2, one mutant. G6b/! was declared FO and measured FC: with the `!` dropped, an
  unsearchable `RUNTIME_DIR` falls through to legacy, and the later `cd` refuses it.

The three council-round-2 mutants (G7e/path, G9j/path, G9k/path) and the two added on the
coordinator's ruling (G7i/-u, G9l/-u) were declared DX before any run and measured DX.
Gate r3's 16 carry FC for the 14 exit values, DX for G2/-gt and EQ for G9b/v, and measured
so. With the generator, the 148 carried mutants measured exactly the modes schema 1 declared.
The 29 new members were declared from their first run (FC 18, FO 5, DX 4, EQ 2), as the
table shows.

In every case the YAML carries the measured value. Killer choice matters too. G5a/! and G5b/!
measured FC while their only killer was the valid-pin innocence test. With their isolating
fixtures (`[bin_is_directory]`, `[bin_not_executable_planted]`) added as killers, they
measured FO. Hence the authoring rule in §5ter.3 step 1.

The scratch suite shows that the contract can be satisfied. It is not the PR-1 test file; the
resumed build writes that.

## 5ter. S3 — the committed mutation check (added 2026-09-27)

The script is `scripts/ci/wa_codex_wrapper_mutants.py`. It ships in the resumed PR-1 together
with its selftest and runs in `wa-codex-pin.yml`. It is generic over the inventory: the
target file and the test files come from the YAML, and the mutants come from the target. PR-2
therefore adds an installer inventory, not a second script. Where the installer uses syntax
outside the 17 site kinds (`[[ … ]]`, `find` predicate terms, `awk` programs, a refusal
through a function call such as `die`), PR-2 extends the grammar in the same PR, together
with guilt and innocence selftests for the new kinds. §5ter.6 measures what the generator
does on #7340's installer today.

### 5ter.1 Interface

```
python scripts/ci/wa_codex_wrapper_mutants.py [--inventory PATH] [--spec PATH]
    [--receipt-dir DIR] [--only ID ...] [--selftest] [--render-table] [--list]
```

- `--inventory` defaults to `docs/specs/2026-09-27-codexpin-v3-d5-inventory.yaml`.
- `--spec` names a markdown file whose `d5-inventory` block must equal `--render-table`.
- `--receipt-dir` is where the JSON and markdown receipt go. In CI it is
  `$RUNNER_TEMP/wcbw-mutants`, uploaded as an artifact.
- `--only` is for local debugging and for the selftest. It restricts steps 5–8 to the named
  ids; steps 1–4 always run in full. A run with `--only` never counts as the CI verdict, and
  its receipt says so.
- `--list` prints every generated id with its line number and mutated line, and runs nothing.
  It is how an author gets the ids to annotate: they are copied, never composed.
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
- **pytest settings.** pytest runs with `cwd=<temp tree>`, stdin bound to `/dev/null`,
  `-q -p no:cacheprovider -rf`, `PYTHONDONTWRITEBYTECODE=1`, and a wall-clock timeout per run
  (default 180 s). The test file's `_run` binds the wrapper's stdin to `/dev/null` as well
  (5bis.4).
- **Run-log hook.** When `$WCBW_RUN_LOG` is set, the test file's `_run` helper appends one
  JSON line per wrapper run: `{test, rc, stdout, heartbeat: [ts, status, note], tagged: […]}`.
  The test's tmp root is replaced by `<T>`. Every well-formed stamp, in the heartbeat `ts`
  and in the tagged lines, becomes `<TS>` when it lies within 120 s of the hook's own UTC
  clock and `<TS-SKEW>` when it does not. A malformed or empty stamp is kept as it is. Both
  cases therefore show up as a difference (G9k, G9l, G7i).
  The hook lives in the TEST file only, so D6's "no test mode in the shipped script" still
  holds.

### 5ter.3 Algorithm

Each step fails with a named error. Steps 1–4 run no test.

1. **Schema.** Load the YAML with `yaml.safe_load` and validate it: the schema string
   `wa-codex-wrapper-inventory/2`; unique ids; each entry carries exactly the keys 5bis.2
   allows for its disposition (`killed_by` on MUST only and non-empty, `reason` on EQUIVALENT
   only, `mode: equivalent` on exactly the EQUIVALENT entries), and no other key. Then
   collect the test file's node ids (`pytest --collect-only -q` in the temp tree). Each
   `killed_by` string must be a substring of exactly ONE collected id. A string that matches
   none is a dead claim; one that matches several could be satisfied by a collateral failure.
   Error: `SCHEMA`.

   Authoring rule, checked in review and not by the script: a mutant's `killed_by` names the
   fixture that isolates its fault, not only an innocence test that happens to fail. For an
   always-refusing member the legitimate start IS the isolated observation, so the valid-pin
   innocence test is its killer. The mode is measured on the killers, so a killer list
   without the isolating fixture can understate it (5bis.8, G5a/! and G5b/!). What stays
   review-only is WHY the killer failed. A unique node id cannot show that the failing
   assertion is the one about the isolated fault. Step 8 narrows it: the killer's run records
   must differ from the baseline in the declared mode's way, so a killer that failed on an
   unrelated observation shows up as `MODE-MISMATCH` unless that observation happens to have
   the same mode.

2. **Derivation.** The target's git blob id must start with `derived_from.blob` (a 10-hex
   prefix; a longer hex id trips the repo's detect-secrets pre-commit guard). Otherwise the
   error is `STALE-DERIVATION`, never a silent skip (gate r3 R5): every entry was judged on
   that blob, so a different blob makes the whole inventory unproven. A wrapper change, even a
   comment-only one, therefore always travels with a re-derived inventory, a new
   `derived_from`, and a Gear-3 review (§5ter.5). Steps 3 and 4 still run on a stale blob, so
   the new and vanished ids are reported with it; a comment-only change gives
   `STALE-DERIVATION` alone. In PR-1 this also makes D5's "exactly lines 72 and 74"
   mechanical: any other byte changes the blob. The prefix is 40 bits: it catches every
   accidental change, not a blob searched to match it (about 2^40 tries). Such a search gains
   nothing on a line that carries a site, whose new 64-bit ids come back `UNANNOTATED` and
   `PHANTOM` (5bis.3a). A change confined to site-free lines keeps every id and, with a
   searched prefix, raises no S3 error; the wrapper's path still floors it at 3 (§5ter.5).
   With the blob matching, `SITE-COUNT` fires
   when the extracted site count differs from `derived_from.sites`, and `MUTANT-COUNT` when
   the generated count differs from `derived_from.mutants`. Both guard the generator itself
   against drift.
3. **Generate.** Extract the sites (5bis.3), generate every member (5bis.3), and compute the
   ids (5bis.3a). Errors: `MASKED <line> <where>: <kinds>` and `UNSUPPORTED <line>
<construct>` (5bis.3, what masking hides), `SPAN <id>`, `NO-MEMBER <line-id>:<key>`,
   `ID-COLLISION`, `LINES
<id>` (the one-line check of 5bis.3 rule 4, on every mutant), and `SYNTAX <id>` when
   `/bin/sh -n` or `bash -n` rejects the mutant.
4. **Annotation closure.** Compare the generated ids with the YAML's. Errors:
   `UNANNOTATED <id>` for a generated id with no entry, and `PHANTOM <id>` for an entry whose
   id is not generated. This step replaces schema 1's anchors, `covers`, `OPERATOR`,
   `DOUBLE-CLAIM`, `NO-STMT` and `NO-OP`: with nothing written by the author, nothing is left
   to check against the operator. Gate r3's `while false; do` swap and gate r4's
   always-refusing drops cannot be expressed. The first has no key to go in, and the second is
   one generated member among the others, each of which needs its own entry.

5. **Baseline.** The unmutated tree must pass the whole test file. Error: `BASELINE-RED`
   (exit 2).
6. **Run.** For each mutant, run the whole test file and collect the failing node ids from the
   `FAILED` lines. A collection error or a timeout is `ERROR`, never a kill.
7. **Verdicts.**
   - A MUST mutant with no failing test is `SURVIVED`.
   - A MUST mutant that was killed, but where no failing id contains a `killed_by` string, is
     `KILLER-MISS`: the fixture claim is false, the same failure as r0's dissent #3.
   - A killed EQUIVALENT mutant is `EQUIVALENCE-REFUTED`.
8. **Mode.** For each killer test, compare its run records under the mutant with the same
   test's baseline records, normalised as in 5ter.2. "The stub ran" means the run's stdout is
   non-empty. The first matching rule wins:
   1. the mutant's stdout is non-empty and differs from the baseline's: `fail-open`. The
      wrapper writes nothing to stdout itself (N.4, and P's stdout is the exec'd program's),
      so non-empty stdout means a program was exec'd: the stub, or a decoy in its place.
      Council round 2 proposed counting only runs that print the stub's marker. Measured,
      that reclassified G8c's `reassert:remove`, where the env's decoy `VENV_PY` is exec'd,
      from `fail-open` to `fail-closed-other-rc`. The broader rule can overstate a mode, never
      understate it, so it stays;
   2. the rc differs, whether the stub ran differs, or the run timed out:
      `fail-closed-other-rc`;
   3. the heartbeat or the tagged lines differ: `same-rc-other-diagnosis`;
   4. otherwise: `equivalent`.

   A mutant's mode is the most severe result over its killer tests, in the order
   `fail-open` > `fail-closed-other-rc` > `same-rc-other-diagnosis` > `equivalent`, and it
   must equal the YAML `mode`. Error: `MODE-MISMATCH`.

   A killer test that leaves no run record at baseline is static: it reads the blob and never
   runs it. A mutant's mode is `static` exactly when every one of its killers is static.
   Declaring `static` with a run-based killer, or a run mode with a static killer, is
   `MODE-MISMATCH` too. `static` sits outside the severity order because it never meets a
   run mode on the same mutant.

   An EQUIVALENT mutant has no killers. Its run records are compared over EVERY test in the
   file, and all of them must equal the baseline's. A difference that no test asserts is still
   `MODE-MISMATCH`: an equivalence claim is about the observations, not about today's
   assertions.

9. **Parity.** The `--render-table` output must equal the spec block between
   `<!-- d5-inventory:begin -->` and `<!-- d5-inventory:end -->`. The rendering is one header
   row `| id | label | line | member | mode | disposition | killed by |`, then one row per
   generated id in S3's order: the id and each killer in backticks, the line number on the
   target, `<key>:<member>`, the mode code of 5bis.6, the disposition, and the killers joined
   by `, ` (an EQUIVALENT row shows `— (see reason)`). A `|` inside a cell is written `\|`.
   After the table, a blank line and the Totals paragraph: `Totals: <sites> sites, <n>
mutants (<m> MUST, <e> EQUIVALENT) under <l> labels. Declared modes: <a> FO, <b> FC, <c>
DX, <d> ST, <f> EQ.`, counted from the generation and the YAML (council round 4: the counts
   in prose were outside the check). The comparison is cell by cell, after splitting rows on
   unescaped `|` and stripping each cell, so prettier's column padding does not matter; the
   Totals paragraph is compared with its whitespace collapsed. Error: `TABLE-DRIFT`.
10. **Receipt.** It is always written, on failure too.
    - `mutants.json` holds, per mutant: id, label, line, member, verdict, failing tests, killer
      hit, measured mode and seconds.
    - `mutants.md` has a header carrying the commit (`GITHUB_SHA` or `git rev-parse HEAD`),
      the target blob sha, the inventory sha256, `generated_at` taken from the runner clock
      at the END of the run, and the counts: sites, generated mutants by member, killed,
      equivalent-survived and failures by code.

### 5ter.4 Selftest

`--selftest` runs pytest only in cases e, f, g, h, i and m below, and takes under 90 s: case
e runs two wrapper mutants, h and i one each, f and g only collect, and m runs the eleven
mutants of a five-line script. Case ids name the committed inventory's entries by label and
member; the ids themselves are in the 5bis.6 table.

Guilt cases. Each one must be detected, or the selftest fails:

- **a. Every kind, closed** (normative plant, gate r3 R4). Insert this line after the line that
  starts `PINNED_CODEX_ROOT=`:

  ```sh
  export WCBW_PLANT_A=1
  ```

  and these lines after the line that starts `export PYTHONPATH=` (gate r3 put them after
  `set +a`; that position re-keys the six re-assert lines, 5bis.3a point 2, so the plant moved
  when the ids came):

  ```sh
  wcbw_plant_b=1 wcbw_plant_c=2
  until (! [ -s "$ENV_FILE" ])||:; do :; done
  read -r -n 1 -d x _wcbw_plant <"$ENV_FILE"
  : "${_wcbw_plant:=q}" "${_wcbw_plant+y}"
  [ -O "$ENV_FILE" ] && heartbeat "planted" "planted"
  printf '%s\n' "planted" 1>&2
  if false; then exec /usr/sbin/sysctl -n hw.ncpu; fi
  set -f
  : "$(date -r 0 -R)"
  case "$_wcbw_plant" in
      (a|b) : ;;
      c) exit ;;
  esac
  ```

  The planted file passes `sh -n` and `bash -n`. S3 must report `STALE-DERIVATION` (the blob
  changed) and `UNANNOTATED` for exactly the 31 ids generated on the planted lines, nothing
  more and nothing less. Their site keys are exactly these 27:

  | Planted line                                 | Site keys                              | Members generated                                     |
  | -------------------------------------------- | -------------------------------------- | ----------------------------------------------------- |
  | `export WCBW_PLANT_A=1`                      | const                                  | value                                                 |
  | `wcbw_plant_b=1 wcbw_plant_c=2`              | reassert#1, reassert#2                 | #1 remove and value, #2 value (#2's remove merges)    |
  | `until (! [ -s … ])\|\|:; do :; done`        | cond, test, andor, neg                 | never; true (no `false` in `until`); both drops; drop |
  | `read -r -n 1 -d x … <"$ENV_FILE"`           | readopt#1, readopt#2, readopt#3, redir | drop each                                             |
  | `: "${_wcbw_plant:=q}" "${_wcbw_plant+y}"`   | default#1, default#2                   | drop each                                             |
  | `[ -O … ] && heartbeat …`                    | test, andor, hb                        | true, false; both drops; remove                       |
  | `printf … 1>&2`                              | diag                                   | remove                                                |
  | `if false; then exec /usr/sbin/sysctl …; fi` | cond, exec, abspath                    | always (never is a no-op); remove; strip              |
  | `set -f`                                     | setopt                                 | remove                                                |
  | `: "$(date -r 0 -R)"`                        | dateopt#1, dateopt#2                   | drop each                                             |
  | `(a\|b) : ;;`                                | alt#1, alt#2                           | drop each                                             |
  | `c) exit ;;`                                 | alt, exit                              | widen; remove                                         |

  All 17 kinds are there, each at least once in a form the target does not use: `until`; a
  `!` right after `(`; a `[` at line start; an unspaced `||`; `read -n 1` followed by `-d x`;
  a `<` with no space; the `:=` and `+` defaults; a heartbeat after `&&`; a `printf` to
  `1>&2`; an `exec` after `then`; a path under `/usr/sbin`; `set -f`; a PATH-resolved `date`
  with `-r 0` before `-R`; the `(pattern)` arm; a bare `exit`; an `export` before the source;
  two assignments on one line after it. An extractor fitted to the target's surface forms
  misses some of them. The round-2 prototype did: it found 24 of the 27 sites (5bis.3).

- **b. Stable ids** (gate r4 re-scope). On copies of the target, compare the generated ids
  with the target's:
  - b1: four blocks of a blank line, a comment line, an indented comment line and a blank line
    inserted before lines 47, 60, 100 and 140, and `set -u` re-indented by two spaces: the
    same 177 ids, each with the same mutated line up to indentation;
  - b2: an unrelated guard inserted after `_wcbw_pin_bin=""`
    (`if [ -e "$RUNTIME_DIR/.wcbw-selftest" ]; then`, a tagged `echo`, the
    `heartbeat "refused" "pin invalid"` line, `exit 78`, `fi`): every one of the 177 ids is
    still generated, and the 6 new ids all sit on the inserted lines;
  - b3, the stated limit: `: wcbw_selftest` inserted right after `set +a` re-keys exactly the
    12 ids of the six repeated re-assert lines (12 lost, 12 gained), and nothing else.
- **c. Annotation closure.** Delete one entry: exactly `UNANNOTATED <its id>`. Add an entry
  `deadbeefdeadbeef:test:true`: exactly `PHANTOM deadbeefdeadbeef:test:true`.
- **d. One line in, one line out** (gate r4 H7).
  - d1: add to G2a's `andor:drop-right` entry the key `to`, holding gate r4's two-line text
    (`    while IFS= read -r _pin_row || [ -n "$_pin_row" ]; do #`, a newline, and
    `    :; done; exit 99; while :; do`): exactly one `SCHEMA` error, naming that id and the
    key `to`.
  - d2: hand the materialiser the same two-line text as that id's mutated line: `LINES`.
  - d3: insert `[ -n "$TAG" ] \` and `    || exit 3` after the line that starts
    `export PYTHONPATH=`: exactly one `SPAN`, for the `drop-left` of that `||`, whose left
    operand sits on the previous line.
- **e. End to end** (re-gate #2's S3 observation). Copy the test file into the temp tree and
  delete from the COPY the two tests that kill G2a's limb: the
  `two_lines_last_unterminated_planted` parameter and
  `test_innocence_single_line_without_trailing_newline_applies`. Leave the inventory as it
  is, skip the step 1 collection check for this case only, and run only the two members that
  delete the limb, G2a's `andor:drop-right` and `test:false`. Both must be `SURVIVED`. Every
  run thus proves that the job goes red when the D10 fixture is removed, in both forms the
  generator writes.
- **f. Dead killer.** Point G3's `neg:drop` entry at `killed_by: [test_no_such_fixture]`:
  `SCHEMA`, matching 0 nodes.
- **g. Ambiguous killer.** Point it at `[bad_semver`, which is part of both `[bad_semver]` and
  `[bad_semver_planted]`: `SCHEMA`, matching 2 nodes.
- **h. Wrong mode.** Declare G3's `neg:drop` as `same-rc-other-diagnosis` and run only that
  mutant: `MODE-MISMATCH` (measured `fail-open`).
- **i. Static confusion.** Declare G0a's `const:value` as `fail-open`, and separately G0c's
  as `static`, and run each alone: `MODE-MISMATCH` both times. The first has only a static
  killer; the second only a run-based one.
- **k. Stale derivation** (R5). Change one hex digit of `derived_from.blob`:
  `STALE-DERIVATION`, and nothing else.
- **m. The `[ … ] || die` form** (gate r4 §1). The selftest writes this script as
  `mini/mini.sh` in its own temp tree:

  ```sh
  #!/bin/sh
  die() { echo "mini: $1" >&2; exit 78; }
  [ -n "$GOT" ] || die "empty digest"
  [ "$GOT" = "$WANT" ] || die "integrity mismatch"
  echo "installed"
  ```

  and a test file `mini/test_mini.py` beside it, whose `_run(**env)` runs `/bin/sh mini.sh`
  with `PATH=/usr/bin:/bin` plus the given env and stdin from `/dev/null`, and writes the
  5ter.2 run-log record (tagged lines are those starting `mini: `). It has two tests:
  `test_valid_installs` (`GOT=abc WANT=abc`: rc 0, stdout `installed`, empty stderr) and
  `test_empty_digest_refuses` (`GOT= WANT=abc`: rc 78, empty stdout, stderr exactly
  `mini: empty digest`). The generator gives 6 sites and 11 mutants.
  - m1: an inventory that annotates only what gate r4's miniature carried (the `die` line's
    diagnostic removal, exit removal and exit value, and the `drop-left` of both guards):
    exactly six `UNANNOTATED`, the `test:true`, `test:false` and `andor:drop-right` of both
    guard lines. `true || die "integrity mismatch"` is among them.
  - m2: all 11 annotated, the integrity line's `test:true` and `andor:drop-right` as MUST
    with killer `test_valid_installs`: exactly those two are `SURVIVED`.

- **n. The floor** (gate r4 re-scope, item 2). For each of the four paths §5ter.5 adds to
  the hot-zone list, alone in a changed-files list, `python3 scripts/evidence_pack_lint.py
--print-floor` prints `3` and `--print-floor-source` prints `path`. Gate r4's §5 set (the
  test file, this inventory and this spec, numstat `+3/-14`, `+2/-1`, `+1/-1`) prints `3`.

- **o. What masking hides** (council round 4). Insert one plant after the line that starts
  `export PYTHONPATH=` (line 265 of the planted copy), one case at a time. Each must give
  `STALE-DERIVATION` and exactly the one error shown, none of the plants having a site
  outside its quotes:

  | Case | Planted lines                         | Error                                                 |
  | ---- | ------------------------------------- | ----------------------------------------------------- |
  | o1   | `: "$([ -f "$X" ] \|\| exit 78)"`     | `MASKED l.265 $( ) in double quotes: andor,exit,test` |
  | o2   | `: <<EOF`, `x`, `EOF`                 | `UNSUPPORTED l.265 heredoc`                           |
  | o3   | `eval ': "$X" \|\| exit 78'`          | `MASKED l.265 eval string: andor,exit`                |
  | o4   | ``: "`true`"``                        | `UNSUPPORTED l.265 backquote`                         |
  | o5   | `trap '[ -f "$X" ] \|\| exit 78' HUP` | `MASKED l.265 trap string: andor,exit,test`           |

- **p. Counts, members, collisions** (council round 4).
  - p1: `derived_from.sites` plus one: exactly `SITE-COUNT`; `derived_from.mutants` plus one:
    exactly `MUTANT-COUNT`.
  - p2: `while false; do :; done` after `export PYTHONPATH=`: `STALE-DERIVATION` and exactly
    one `NO-MEMBER`, for that line's `cond` (its only member, `never`, is the line itself).
  - p3: run the id function with `h` cut to one hex digit, a parameter only the selftest sets:
    `ID-COLLISION` is reported. No real collision of 64 bits can be planted, so this is the
    check that the code path is live.

Innocence:

- The PR-1 target and the committed inventory pass steps 1–4 with 136 sites, 177 generated
  ids and zero errors of any code.
- m3: the mini with a third test, `test_integrity_mismatch_refuses` (`GOT=abc WANT=xyz`:
  rc 78, empty stdout, stderr exactly `mini: integrity mismatch`), and m2's two entries
  pointed at it: 11 of 11 killed, zero errors.
- n: `docs/README.md` alone prints `1`.

The scratch prototype produced exactly the expected result in every case, a to p (evidence
pack). Measured beside the cases, not as one: on the mini, flipping m2's two entries to
EQUIVALENT without the mismatch fixture gives zero errors. No observation distinguishes them
once the fixture is gone, so no check that reads only the head can see the flip. That is why
item 2 is answered by the floor (§5ter.5), not by S3.

### 5ter.5 CI wiring

In `wa-codex-pin.yml`, either in the same job or in a second job after the pytest step:

- `python -m pip install pytest==<pinned> pyyaml==<pinned>`, at exact versions (r0 N7);
- `python scripts/ci/wa_codex_wrapper_mutants.py --selftest`;
- `python scripts/ci/wa_codex_wrapper_mutants.py --spec docs/specs/2026-09-27-codexpin-v3-spec.md --receipt-dir "$RUNNER_TEMP/wcbw-mutants"`;
- `actions/upload-artifact` of the receipt directory, with `if: always()`;
- the scope list below names the script, the inventory YAML and this spec;
- `timeout-minutes: 25`. The 177 generated mutants took 2 to 5 min on 5 workers on M5; schema 1's
  148 took 5.5 min on one worker when idle and 24 min under heavy load, the FIFO hang mutant
  costs the test's 15 s timeout, and macOS runners are slower. If the job nears the limit,
  raise it or add workers; never drop mutants to fit.

**What blocks a merge (gate r3 R6).**

- **PR-1 itself.** No required context carries this job yet. PR-1's gate signs only with
  `wa-codex-pin verdict` green on the PR head, and it reads the run, not a claim about the run.
- **Every later PR.** PR-1 ships the workflow in the W69 sentinel shape that
  `guard-conformance.yml` uses for the required `Every guard proves guilt AND innocence`:
  - no `paths:` under `pull_request`. It triggers on every `pull_request` and `merge_group`,
    and on `push` to `main` with a paths filter, so `main-push-failure-watch.yml` still sees
    it (D6);
  - a `scope` job on `ubuntu-latest` decides whether the change touches the scope list: the
    wrapper, `test_wa_codex_broker_wrapper.py`, the inventory YAML, this spec,
    `wa_codex_wrapper_mutants.py` and the workflow itself. On `pull_request` it diffs
    `pull_request.base.sha...HEAD`. On `merge_group` it diffs `merge_group.base_sha` against
    `merge_group.head_sha`, so a queue entry pays for the macOS job only when its group
    touches the scope. PR-2 and PR-3 add their files to the list, as they add them to the
    pytest argv;
  - the macOS job (`needs: scope`) runs pytest and S3 only in scope;
  - a `wa-codex-pin verdict` job on `ubuntu-latest` (`needs: [scope, macos]`,
    `if: always()`) passes when the change is out of scope, and otherwise only when the macOS
    job succeeded. In scope, skipped, cancelled or failed is red, and a failed `scope` job is
    red in every case.

  Making `wa-codex-pin verdict` a required status check is a GitHub branch-protection
  setting, which is operator-only (`docs/rules/operations.md`, "GitHub settings"; the same
  arming note `guard-conformance.yml` carries). No session makes that call. Once the verdict
  job has gone green on `main`, PR-1's ship session opens a PENDING-ARMS row owned by
  `operator[gui]`: before that, a required context that never reports would block every PR.
  The row's proof-of-armed is that `gh api repos/Bali-Zero/Teman2/branches/main/protection`
  lists the context and the next out-of-scope PR shows it green. PRs whose last run predates
  PR-1's merge show the context as expected until their next push.

  Until the row closes, a red S3 does not block a merge by itself. Gate r3 measured the hole:
  a PR that only deleted 12 lines from `test_wa_codex_broker_wrapper.py` had floor 1 (source
  `none`), needed no gate verdict, and would have auto-merged with S3 red. Gate r4 measured
  the same for a PR that deletes a fixture and flips its entry to EQUIVALENT (the test file,
  this inventory and this spec; floor 1). The floor below closes it without waiting for the
  row.

  D6 kept the job optional because a required check stuck red blocks the whole merge queue.
  The scope job answers that. Out of scope, the verdict passes in seconds, so a red S3 blocks
  only the PRs that touch the pinned surface, which are the ones it must block.

**Every change to the S3 surface is Gear 3 (gate r4 re-scope, item 2).** PR-1 adds four
paths to `HOTZONE_PATTERNS` in `scripts/evidence_pack_lint.py`, and to the case-block of
`.github/workflows/hot-zone-pr-gate.yml` that the script names as its declared duplicate:

- `docs/specs/2026-09-27-codexpin-v3-d5-inventory.yaml`;
- `docs/specs/2026-09-27-codexpin-v3-spec.md`;
- `scripts/tests/test_wa_codex_broker_wrapper.py`;
- `scripts/ci/wa_codex_wrapper_mutants.py`.

The wrapper (`infra/launchagents/*`) and the workflow (`.github/workflows/*`) are hot zones
already. PR-2 and PR-3 add their files the same way, in the PR that adds them to the scope
list. PR-1 also extends `scripts/tests/test_evidence_pack_lint.py`: each of the four paths
alone floors at 3 with source `path`, and gate r4's §5 set floors at 3 (guilt); an unrelated
doc floors at 1 (innocence). That test file runs in `guard-conformance.yml`, whose
`Every guard proves guilt AND innocence` is a required context. Selftest n repeats the guilt
half on every S3 run.

Why the floor, and not a base-relative check inside S3. Gate r4 offered both. The floor is
the one that binds, for three reasons measured in this repo:

1. `Harness floor recompute` is a required context today (`gh api
repos/Bali-Zero/Teman2/branches/main/protection` lists it). It computes the floor with
   `evidence_pack_lint.py --print-floor` from the BASE checkout. A floor-3 diff with no
   `evidence/brief.yml` fails outright, a brief below the floor fails, and a brief at Gear 2
   or 3 passes only once a harness/fable-gate verdict is posted on the head (its step 7c,
   `harness_gate_read.py`). So from the first PR after PR-1's merge, a flip cannot merge
   without a gate reading it, unless the pattern list was narrowed first (below), and no
   operator step is needed. PR-1 itself is floor 3 through the wrapper and the workflow.
2. A base-relative check inside S3 would run in `wa-codex-pin verdict`, which is not a
   required context until the operator arms it: it would bind in none of the window that gate
   r3 R6 and gate r4 §5 measured. It would also have to read a sha-bound PR comment from a
   macOS job in both `pull_request` and `merge_group` runs, a second copy of
   `harness_gate_read.py`.
3. A flip is one of several ways a later PR can weaken the inventory: a killer pointed at a
   test that still fails for another reason, a mode relabelled together with the test that
   pinned it, a fixture deleted along with its entry. S3 reads the head only, and on the head
   each of them can be consistent (selftest m's measured flip). The floor puts all of them in
   front of a gate that reads the diff and the S3 run.

The cost is that any edit to the four files, a typo included, needs a Gear-3 brief, a pack
and a gate. They change together with the wrapper, which is floor 3 already, or with this
spec.

**The transition, and what the floor does not cover** (council round 4).

- **A PR that was green before PR-1 merged.** `main`'s ruleset `merge-queue-main` has a
  `merge_queue` rule, is `active` and lists no bypass actors (`gh api
repos/Bali-Zero/Teman2/rulesets/19779175`, 2026-09-27), so every merge goes through the
  queue, and `Harness floor recompute` runs again on the
  `merge_group` event with its base checkout at `merge_group.base_sha`. That base is the
  commit the queue entry is built on: the previous entry's group commit, or `main`. Measured
  2026-09-27: run 36294018919, for #7511's entry, checked out `62c22f61f5`, the group commit
  of #7506, queued just ahead of it. So a PR whose `pull_request` run predates PR-1's merge,
  or that is queued right behind PR-1, is floored by a linter that holds PR-1's four
  patterns, and a pass from before does not carry over.
- **Before PR-1 merges.** Once this spec is on `main`, the inventory and the spec floor at 1
  until PR-1 lands (the test file and S3 do not exist yet). PR-1's gate therefore also reads
  `git log <#7456's merge commit>..<PR-1's base> -- <the inventory> <this spec>`: any commit
  there is reviewed as part of PR-1, and one that weakens an entry is a BLOCK. A commit queued
  ahead of PR-1 in the same batch lands after that read, so PR-1's ship session reads the
  range again up to PR-1's own merge commit, and a weakening commit found there reopens the
  lane.
- **The pattern list itself.** `scripts/evidence_pack_lint.py` floors at 1 (measured with
  `--print-floor`), and nothing checks it against the case-block it duplicates. A PR that
  deletes the four patterns is therefore not Gear 3, and after it the flip is floor 1 again.
  This holds for every hot-zone path in the repo, the wrapper and `.github/workflows/*`
  included, so it is the harness's residual, not this design's; §8 item 11 states it and the
  harness change that would close it.

### 5ter.6 The generator on #7340's installer (feasibility receipt, gate r4 re-scope)

Non-normative: the same scratch prototype, run on `git show
3d04590c99:scripts/install_wa_codex_pinned.sh` (blob `666f1025e2`, 302 lines, `set -euo
pipefail`). PR-2 rebuilds this installer, so the numbers show what the generator does to the
form gate r4 attacked, not PR-2's inventory.

- **137 sites:** abspath 1, alt 8, andor 26, cond 11, const 51, default 1, diag 3, exit 5,
  neg 4, setopt 1, test 26.
- **189 mutants:** `cond` never 10 and always 10; `test` true 22, false 22 and relop 3;
  `andor` drop-left 18 and drop-right 25; `alt` widen 4 and neutralise 4; `const` value 51;
  `exit` remove 5 and value 5; `neg` 4; `diag` 3; `default`, `setopt` and `abspath` 1 each.
- **The 18 `|| die`, 10 of them `[ … ] || die`.** Every one of the 10 gets its fail-open
  `test:true`. Line 197's is `84056dd2ec499d0d:test:true`, `true || die "integrity mismatch for
${TARBALL}"`: the guard gate r4 deleted with every check green now has its own id, which
  the installer inventory must judge. For the 8 `cmd || die`, the guard deletion is
  `drop-right`. Under `set -e` a failing command then aborts with its own rc and no `die`
  line, so that member measures FC or DX rather than FO. This is why the test constants and
  the drops are separate members.
- **10 `SPAN`.** 7 are the `drop-left` of a `|| die` that starts a line continued from the
  previous one (lines 163, 169, 178, 242, 254, 280, 298). One is the `drop-right` of line 238,
  whose `die` message runs onto line 239. Two are `never` and `always` of line 212,
  `if ! "$AWK_BIN" '`, whose condition holds a 16-line `awk` program.
- **Outside the 17 kinds**, measured on the same masked text:
  - 9 `die` calls outside an and-or list (5 bare in `if` blocks, 4 in `case` arms). They are
    refusals with no `remove` member until a kind names them;
  - 4 lines with `&&` or `||` inside a double-quoted `$( … )` (lines 56, 171, 180, 181). The
    masking blanks them, and S3 now says so: `MASKED` on each of the four, and on line 237,
    where `find`'s `!` inside `"$( … )"` reads as a `neg` site. With the 10 `SPAN`, S3 reports
    15 errors on this installer before any annotation;
  - the `[[ … ]]` of the argv gate (line 38); the `awk` program (lines 213–228); the `find`
    predicate list of line 237; 4 `local` lines, 1 `$(( ))` and 1 `trap`.

What this obliges PR-2 to do, in the same PR as its installer inventory:

- keep every and-or list, condition list and `[ … ]` on one physical line, so that no
  member is `SPAN`. Alternatively, extend materialisation to logical lines, with its own
  one-line proof;
- add a kind for refusal through a function (each call of a function whose body ends in
  `exit`, with a `remove` member), and generate members inside double-quoted `$( … )` bodies,
  which S3 now reports as `MASKED` until the grammar does;
- keep heredocs and backquotes out, or model them: S3 reports each as `UNSUPPORTED`;
- extend the grammar for `[[ … ]]`, `find` predicates and `awk` programs, or keep them out of
  guards;
- add the installer, its test file and its inventory to the scope list and to the hot-zone
  paths (§5ter.5).

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

| Order | PR                                                                                      | Files                                                                                                                                                                                                                                                                                                                                                                                                                         | Net lines (est.)                                                                                                                                                                                                                                                                                                           | Bites                                                                                                                                                                                                                            |
| ----- | --------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1     | `feat(wa-broker): apply the dedicated codex pin in the wrapper with builtins only`      | wrapper (D5, protocol line), `test_wa_codex_broker_wrapper.py`, new `wa-codex-pin.yml`; **amended 2026-09-27:** + `main-push-failure-watch.yml` entry, + `scripts/ci/wa_codex_wrapper_mutants.py` with selftest (§5ter), + the re-rendered §5bis.6 table; **gate r4:** + four `HOTZONE_PATTERNS` entries in `evidence_pack_lint.py` and `hot-zone-pr-gate.yml`, + their floor cases in `test_evidence_pack_lint.py` (§5ter.5) | ~360 in the scratch plan; **measured 842 at `04dd6b51e4`** (wrapper 189, tests 567, workflow 66, watch list 10, `.prettierignore` 10); about **1,500** with S3 (~500: the generator replaces schema 1's anchors and operator check) and the §5bis.7 fixtures (~150), plus ~50 for the hot-zone paths and their floor cases | CI: the macOS run on the PR, pytest AND the S3 receipt (all 170 MUST mutants killed, 177 of 177 annotated). Live: O3/O4 at the operator run. Until then the declared home-fork pair shows DRIFT, which is the pending-arm marker |
| 2     | `feat(wa-broker): pinned codex installer v3 — chain-verified, parser-exact, fresh-only` | installer (D1–D4, D8, D9), `test_install_wa_codex_pinned.py`, chaos-table row 8 (dedupe its doubled path), `change_map.py` census                                                                                                                                                                                                                                                                                             | **~800** (script ~300, tests ~480)                                                                                                                                                                                                                                                                                         | the operator run + O1–O5                                                                                                                                                                                                         |
| 3     | `fix(wa-sentinel): name the pinned installer; never blame Homebrew for a pinned daemon` | sentinel (D7), its tests, add both to the workflow paths                                                                                                                                                                                                                                                                                                                                                                      | ~90                                                                                                                                                                                                                                                                                                                        | the sentinel's next tick on Pro prints `codex pin: 0.156.1 (dedicated)`                                                                                                                                                          |

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
`origin/main`; the branch was never armed, so it is not frozen. The wrapper stays
byte-identical to `04dd6b51e4` except for the D5 heartbeat fix, lines 72 and 74 (§5bis.5,
D10 decision). Built from `04dd6b51e4`, that target's blob id starts `78236b6070`, and the
inventory already names it in `derived_from.blob` (with `base_commit`/`base_blob` recording
where it came from). A wrapper with any other bytes fails S3 with `STALE-DERIVATION` (gate r3
R5), so the resumed build either lands exactly that blob or re-derives the inventory in the
same commit, as a reviewed spec change. Any further logic change re-runs S3 in full, which is
cheap now. PR-2 uses the same mechanism: an installer inventory in the same schema,
generated and run by the same script, after the grammar work §5ter.6 lists.

PR-1 must not start its S3 build from this spec at `3a2cf979a0` or earlier (gate r4): the
build implements schema 2 and the generator, and its first S3 run re-renders the 5bis.6
table from its own output.

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
6. **`heartbeat()` resolved `mkdir` and `date` through PATH after the env was sourced**
   (re-gate #1 §5, added 2026-09-27). **Closed in PR-1 by the D5 heartbeat fix.** The
   behaviour is identical on `origin/main`. An env `PATH` that lacks them made the `starting`
   heartbeat silently absent while the daemon still started. The first commit of this spec
   deferred the fix to a PR after PR-1 and exempted the two hostile-PATH tests from P.4.
   Council round 1 then showed that the gap also made G9b's EQUIVALENT claim false at
   `04dd6b51e4`, so the fix moved into PR-1: two lines, re-checked by S3 in the same PR.
7. **An unsearchable ANCESTOR of `RUNTIME_DIR`** (for example `/usr/local/lib` at 000) makes
   the wrapper log `no pin file … (legacy)` and then exit `78` on the venv check (re-gate #1
   §2, added 2026-09-27). The run still fails closed, because `VENV_PY` lives under
   `RUNTIME_DIR` and N1 pins it, but the diagnosis misleads. PR-2's D1 chain check refuses to
   install into such a chain, so the state is reachable only by a root-side change after
   install.
8. **The process environment launchd hands the wrapper** (added 2026-09-27). The G0 entries
   mutate the VALUES of the pre-source constants (5bis.3). Deleting one is different: it
   crashes under `set -u` on every run unless launchd injects that name, and the plist is
   root-owned (§1).
9. **`date -u`** (added 2026-09-27, council round 2; **closed**). Dropping `-u` from the
   heartbeat's or the proof line's `/bin/date` failed no test in the round-2 feasibility
   suite. The stamp would have been local time labelled `Z`, off by the host's UTC offset, and
   §6 reads the proof line's stamp to show that the start is fresh. The coordinator ruled it
   MUST. It is now the `dateopt` kind, labels G7i and G9l, and the fixture
   `test_stamps_are_utc_under_a_non_utc_tz` (5bis.7).
10. **The window before `wa-codex-pin verdict` is required** (added 2026-09-27, gate r3 R6;
    **narrowed by gate r4**). Only the operator can make it a required context, and only after
    PR-1 has merged and the job has reported on `main` (§5ter.5). As gate r3 measured it,
    between those two moments a PR below Gear floor 3 that touched only the tests, the
    inventory or this spec was not blocked by CI if S3 was red. Gate r4's item 2 closes that
    part: from the first PR after PR-1's merge, those paths floor at 3, and the required
    `Harness floor recompute` holds the PR until a gate verdict is posted, a gate that reads
    the S3 run. What remains until the row closes is that a red S3 blocks through the gate's
    reading of the run rather than by itself. The PENDING-ARMS row tracks that.
11. **The hot-zone list is itself floor 1** (added 2026-09-27, council round 4; **open,
    harness-wide**). `scripts/evidence_pack_lint.py`, which holds `HOTZONE_PATTERNS`, floors at
    1, and nothing compares that tuple with the case-block of `hot-zone-pr-gate.yml` that
    duplicates it. A PR that narrows the list needs no gate, and every path it drops, this
    spec's four and the wrapper's `infra/launchagents/*` alike, is floor 1 from then on. Making
    the linter a hot-zone path would close it at the cost of Gear 3 on every linter edit (20
    commits in the 30 days to 2026-09-27). The narrow cure is a step in `harness-floor.yml`,
    which is floor 3 itself: when a diff touches the linter, read `HOTZONE_PATTERNS` as text
    from the base and the head copies (the tuple regex `model_routing_gate.py` already uses)
    and floor the diff at 3 if the head drops any base pattern. That is a harness change for
    every lane, so it is not folded into PR-1: PR-1's ship session files it as an escalation
    for the owner, and until it lands this item stays open. Council round 4b split on its
    weight: codex-gpt-5.6-sol asks that the cure be a prerequisite of PR-1, kimi-code/k3 accepts
    it open for this docs-only PR. That is the owner's call.
12. **Code the masking blanks without a literal** (added 2026-09-27, council round 4b; **open**).
    `MASKED` and `UNSUPPORTED` (5bis.3) read literal text only. A guard that reaches an
    interpreter through a variable (`G='[ -f x ] || exit 78'; eval "$G"`, `sh -c "$G"`,
    `trap "$G" HUP`), an `alias`, a sourced file other than the env file, ANSI-C quoting `$'…'`,
    an `sh -c` behind option arguments (`bash -o errexit -c …`) or behind `env`/`command`, or a
    `default`, `abspath` or `dateopt` site inside a single-quoted string, generates no id and
    raises no error. Both seats found it; neither target uses any of these forms, and adding
    one changes the blob (`STALE-DERIVATION`) and the floor-3 wrapper path, so a gate reads it.
    The cure both seats named: `UNSUPPORTED` for a non-literal `eval`/`trap`/`sh -c` argument,
    for `alias`, for `.`/`source` of anything but the env file and for `$'…'`; the full kind
    set on single-quoted bodies; plants o6–o8. It is a change to the grammar's coverage, made
    after the one fix round this council allowed, so it is left to the gate.

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

Added 2026-09-27 (M5, bash 3.2.57; scratch prototypes, not committed). Blobs: the PR #7420
wrapper at `04dd6b51e4` (blob `4143a795d9`, sha256 prefix `9fb2268887392b6e`), and the PR-1
target, which is that blob plus the D5 heartbeat fix (blob `78236b6070`, sha256 prefix
`022c86115eff1eda`).

Added by the gate r4 re-scope (the generator prototype; non-normative, not committed):

- **Generator (5bis.3, 5bis.3a).** 136 sites and 177 mutants on the PR-1 target, 134 and 175
  on `04dd6b51e4`. Only lines 72 and 74 change ids between the two blobs. The masking
  amendment changes no site count on either.
- **Committed inventory, steps 1–4.** 177 of 177 ids annotated; 0 errors of any code.
- **Selftest.** Cases a–k and m reproduced exactly the expected results of §5ter.4, including
  a (31 `UNANNOTATED` on the 27 plant sites, plus `STALE-DERIVATION`), b1–b3 (177 ids
  unchanged by layout, kept under an unrelated guard with 6 new ids on its lines, and exactly
  the 12 repeated re-assert ids re-keyed by a line after `set +a`), d1–d3 (`SCHEMA` on `to`,
  `LINES` on the two-line text, one `SPAN`), e (both limb members `SURVIVED`), m1 (six
  `UNANNOTATED`), m2 (two `SURVIVED`) and m3 (11 of 11 killed, 0 errors).
- **Floor (item 2).** With `HOTZONE_PATTERNS` as on this branch, `compute_floor` gives 1
  (source `none`) for each of the four scope paths alone and for gate r4's §5 set. With the
  four paths added, it gives 3 (source `path`) for each and for the set, and 1 for
  `docs/README.md` and for `scripts/tests/test_evidence_pack_lint.py`.
- **Feasibility suite (50 tests, PR-1 target).** Steps 1–8: 170 of 170 MUST killed by a
  declared killer, 7 EQUIVALENT with identical records over every test, 177 of 177 modes as
  declared, 0 errors (5bis.8).
- **Current suite (28 tests, `04dd6b51e4`).** 175 mutants: 105 killed, 70 survived (63 MUST
  under 38 labels, plus the 7 EQUIVALENT); 0 EQUIVALENT killed (5bis.8).
- **The flip is invisible to S3.** On the mini of selftest m, m2's two entries flipped to
  EQUIVALENT without the mismatch fixture: 0 errors.
- **Installer (§5ter.6).** 137 sites, 189 mutants, 10 `SPAN`, the 18 `|| die` each with a
  fail-open member.

Added by council round 4 (same prototype, re-run on the committed bytes):

- **Ids at 64 bits.** Re-keying from 8 to 16 hex digits changed no mutant, order or count on
  any of the four scripts (wrapper, `04dd6b51e4`, installer, mini): 177, 175, 189 and 11
  ids, one for one.
- **What masking hides.** 0 `MASKED` and 0 `UNSUPPORTED` on the PR-1 target and on
  `04dd6b51e4`; on the installer, `MASKED` on lines 56, 171, 180, 181 (`andor`) and 237
  (`neg`). Selftest cases o1–o5 and p1–p3 gave exactly their expected errors; the widened
  comment rule changed no count.
- **The queue re-floors.** `main`'s rules include `merge_queue` (SQUASH, up to 5 entries
  built). The `Harness floor recompute` log of run 36294018919 (#7511's queue entry) shows
  `ref: 62c22f61f5…` and `HEAD is now at 62c22f61f feat(images): … (#7506)`: the base it
  floors against is the entry ahead of it, not the `main` of its `pull_request` run.
- **The queue has no bypass.** Ruleset 19779175 (`merge-queue-main`, `refs/heads/main`):
  enforcement `active`, `bypass_actors` empty, one rule, `merge_queue`.
- **The pattern list's own floor.** `compute_floor` gives 1 (source `none`) for
  `scripts/evidence_pack_lint.py`, `scripts/ci/hotzone_changed_files.sh`,
  `scripts/harness_gate_read.py` and `scripts/tests/test_evidence_pack_lint.py`, and 3 for
  `harness-floor.yml`, `hot-zone-pr-gate.yml` and `guard-conformance.yml` (§8 item 11).

Schema-1 measurements, kept as the record gates r3 and r4 judged:

- **Site extractor (5bis.3).** It found 136 sites on the PR-1 target, all claimed by the 71
  rows, and 134 on `04dd6b51e4`, all claimed by the 69 rows that apply there. The normative
  plant of §5ter.4 (a) produced exactly its 27 UNCLAIMED sites plus `STALE-DERIVATION`; the
  round-2 extractor found 24 of them. In round 1, one changed guard line produced
  `STALE-ANCHOR` before any mutant ran.
- **Operator check (gate r3).** On the committed inventory (PR-1 target) and on its projection to `04dd6b51e4` (the
  69-row inventory of 5bis.8): 0 `OPERATOR` errors. Selftest cases j, k, l, m, n and o each produced exactly their expected errors. On
  the inventory at `0ac11b17e8` the same check reported 16: the 14 exit values, G9b's
  `return 0` and G2's `-ne`. The planted file of case (a) passes `sh -n` and `bash -n`.
- **Merge coverage (gate r3 R6).** `evidence_pack_lint.py --print-floor` gives floor 1
  (source `none`) for a 12-line deletion in `test_wa_codex_broker_wrapper.py` and floor 3 for
  a one-line wrapper change.
- **Current suite (28 tests, `04dd6b51e4`).** 130 mutants: 71 killed, 59 survived (55 MUST
  plus the 4 EQUIVALENT), no `sh -n` failure (5bis.8). With gate r3's 16: 146 mutants, 80
  killed, 66 survived (61 MUST plus the 5 EQUIVALENT).
- **Feasibility suite (50 tests, contracts N and P, PR-1 target).** 143 of 143 MUST mutants
  killed, each by a declared killer. The 5 EQUIVALENT mutants survived with identical run
  records. All 148 declared modes equal the measured ones, after the seven corrections that
  5bis.8 names.
- **Council round 1 (codex-gpt-5.6-sol, read-only), by execution.** Dropping the NUL probe's
  `< "$CODEX_PIN_FILE"` let a NUL-bearing pin through, and it was applied. Dropping the `!`
  of `if ! _is_semver` applied `a.b.c`. Neither was a site in the 12-kind grammar, which is
  why G1d, the `neg` kind and the `redir` kind exist.
- **G9b, raised by the same seat and reproduced by the author.** Under
  `PATH=/does-not-exist`, with the sidecar directory present: at `04dd6b51e4` the shipped
  `heartbeat()` wrote no file, and its G9b mutant wrote `{"ts":"","status":"starting"}`. The
  two hostile-PATH feasibility tests, as they stood before the `ts` check was added, failed
  on the shipped `04dd6b51e4` wrapper and passed on its mutant. On the PR-1 target they
  passed on both.
- **Council round 2 (both seats ACCEPT-WITH-NOTES).** kimi-code/k3 found that nothing pinned
  the heartbeat's `/bin/date`. Hence the `abspath` kind, rows G9j and G9k, mutant G7e/path and
  the `ts` clauses of N and P. codex-gpt-5.6-sol found the selftest had no guilt case for the
  round-2 rules; cases f–i were added.
- **Consistency with re-gate #2.** On the same blob, the prototype reproduces that gate's
  verdicts: D10, D25, D26, D02, S1–S5 and P1–P5 survive; D09, D11, D12, D13 and D16 die.
- **Shipped-wrapper behaviour.** Under the shipped wrapper,
  `WA_CODEX_CLI_VERSION_PIN=9.9.9\` + NUL + `JUNK` refuses with the NUL reason. With the
  probe's `-r` dropped, it refuses with the semver reason instead (G1b is DX, not FO).

## 10. Changelog against the scratch text (2026-09-27)

Every change below is traceable to a gate on PR #7420, to the S2–S4 conditions of its
BLOCK, to council rounds 1–4 on this spec (codex-gpt-5.6-sol and kimi-code/k3, journaled in the
PR's evidence pack), or to the fresh gates on this spec (gate r3, comment 5850401670; gate r4,
comment 5852422768, with the owner's ruling for the generator route). D1–D4, D6's proof
design, D8, D9, §1, §2, §4, §6 and the installer and sentinel test tables are unchanged,
except where listed. Gate r4 re-scoped S3 without re-opening the 17-kind grammar, closure over
sites, fixture contracts N and P, the D5 heartbeat fix, R2–R5 or R6's text. Four of those
moved anyway, each because the generator or the installer receipt forced it, and the rows
below say which: the masking became file-wide (no count changed), the plant of R4 moved,
R5's step text now names `MUTANT-COUNT` beside `SITE-COUNT`, and R6's window paragraph was
narrowed by the floor.

| §                                        | Change                                                                                                                                                                                                                                                                                                                                                                 | Proved by                                                                       |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| header, §0                               | Commit note; scratch inputs marked ephemeral                                                                                                                                                                                                                                                                                                                           | S2 (the spec lived only in `/private/tmp`)                                      |
| D5                                       | Line grammar: `IFS=`/`-r` are requirements; a single line without a final LF is accepted; two lines with an unterminated last line are refused                                                                                                                                                                                                                         | re-gate #2 D10, D25, D26                                                        |
| D5                                       | NUL probe rule, the bash-only `read -d`, explicit `/bin/sh` in tests                                                                                                                                                                                                                                                                                                   | spalla review 2026-09-26; r0 C1, N2                                             |
| D5                                       | Implemented check order; one tagged diagnostic line per refusal is contract                                                                                                                                                                                                                                                                                            | r0 C1 plus re-gate #1 R3 (masking), this spec §5bis.4                           |
| D5                                       | EACCES rule made precise (`[ -d ] && [ ! -x ]` on `RUNTIME_DIR`; `-r` on the pin)                                                                                                                                                                                                                                                                                      | r0 C3, N4                                                                       |
| D5                                       | Semver wording: "three numeric fields", leading zeros allowed; per-alternative witnesses                                                                                                                                                                                                                                                                               | r0 spec-owner note; re-gate #2 S1–S5                                            |
| D5                                       | Handoff through positional `$1`/`$2`, not the named `PIN_VER`/`PIN_BIN`                                                                                                                                                                                                                                                                                                | spalla review 2026-09-26 (named vars clobbered by DATA); r0 judged sound        |
| D5                                       | Post-source re-assert of six literals plus `PYTHONPATH`                                                                                                                                                                                                                                                                                                                | r0 N1 (sol BLOCKER, `TAG` gap); `PYTHONPATH` by this inventory (G8g)            |
| D5                                       | Kill-switch precedence stated                                                                                                                                                                                                                                                                                                                                          | r0 N3; re-gate #1                                                               |
| D5, §8.2                                 | Scope narrowed to the named DATA                                                                                                                                                                                                                                                                                                                                       | r0 spec-owner note                                                              |
| D6                                       | Watcher-coverage entry; extend `paths:` and the pytest argv; S3 steps; pinned pytest/pyyaml                                                                                                                                                                                                                                                                            | re-gate #1 R1; r0 N7; S3                                                        |
| D7                                       | Sentinel uses the exact same line grammar                                                                                                                                                                                                                                                                                                                              | follows from the D10 decision                                                   |
| §5                                       | `test_semver_validators_agree` asserts expected verdicts, not agreement alone                                                                                                                                                                                                                                                                                          | re-gate #2 §2                                                                   |
| §5                                       | Wrapper table marked superseded by §5bis                                                                                                                                                                                                                                                                                                                               | r0 C1, re-gate #1 R3, re-gate #2 BLOCK                                          |
| §5bis                                    | Closed D5 inventory, site grammar, fixture contract, dispositions, decisions                                                                                                                                                                                                                                                                                           | S2                                                                              |
| §5ter                                    | S3 mutation check specified                                                                                                                                                                                                                                                                                                                                            | S3                                                                              |
| §5quater                                 | S4 evidence-text fixes                                                                                                                                                                                                                                                                                                                                                 | S4, re-gate #2 §4                                                               |
| §7                                       | PR-1 content and measured size; resumption on #7420; PR-2 reuses S3                                                                                                                                                                                                                                                                                                    | S2–S4                                                                           |
| §8                                       | Items 6–8 (heartbeat PATH, ancestor EACCES, launchd env)                                                                                                                                                                                                                                                                                                               | re-gate #1 §2 and §5; this inventory                                            |
| §9                                       | 2026-09-27 measurements                                                                                                                                                                                                                                                                                                                                                | this spec                                                                       |
| D5, §8.6                                 | Heartbeat calls `/bin/mkdir` and `/bin/date`: the one wrapper change beyond `04dd6b51e4`, moved into PR-1                                                                                                                                                                                                                                                              | council r1: sol raised G9b, the author reproduced it; re-gate #1 §5             |
| §5bis.3                                  | Kinds `const`, `neg`, `redir` (130 sites, 67 rows); value substitution on `const` and `reassert`; the not-sites list restated                                                                                                                                                                                                                                          | council r1: kimi findings 1–2; sol executed the `<` and `!` drops               |
| §5bis.4                                  | Wrapper stdin is `/dev/null`; patched constants pinned statically; reasons pairwise non-containing; P.4 exemption removed                                                                                                                                                                                                                                              | council r1: kimi findings 1 and 6                                               |
| §5bis.5                                  | G0k is EQUIVALENT; G9b holds only on the PR-1 target                                                                                                                                                                                                                                                                                                                   | council r1: sol                                                                 |
| §5bis.8                                  | Round-2 measurements; the seven mode corrections disclosed; the killer-choice rule                                                                                                                                                                                                                                                                                     | council r1: kimi finding 3                                                      |
| §5ter                                    | `killed_by` matches exactly one node id; severity order; `static` mode; EQUIVALENT compared over every test; selftest (e) reworded; stdin                                                                                                                                                                                                                              | council r1: kimi findings 4, 5 and 7                                            |
| §7, §8                                   | PR-1 lands the heartbeat fix and re-arms `SITE-COUNT`; §8 items 6 and 8 restated                                                                                                                                                                                                                                                                                       | council r1                                                                      |
| §5bis.3, D5                              | Kind `abspath` (134 sites on the target, 132 at `04dd6b51e4`); rows G9j and G9k; mutant G7e/path                                                                                                                                                                                                                                                                       | council r2: kimi finding 14 (nothing pinned the heartbeat's `/bin/date`)        |
| §5bis.4                                  | N.2, P.3 and P.4 assert well-formed UTC stamps; the scratch suite's N.4 aligned to empty stdout                                                                                                                                                                                                                                                                        | council r2: kimi finding 14; the `grep -q` probe                                |
| §5bis.3                                  | The not-sites rationale corrected and measured: line 177 inert, `-p` and `-q` killed, `-u` unpinned                                                                                                                                                                                                                                                                    | council r2: sol findings 4–5, kimi finding 16                                   |
| §5ter                                    | FO rule kept and justified (a narrower one misclassified G8c/stmt, measured); selftest cases f–i; the review-only residue of killer causality stated                                                                                                                                                                                                                   | council r2: sol findings 1, 2 and 6, kimi finding 7                             |
| YAML, §7                                 | `derived_from` names the PR-1 target blob, with `base_commit` and `base_blob`                                                                                                                                                                                                                                                                                          | council r2: kimi finding 15                                                     |
| §8                                       | Item 9: `date -u` is pinned by no test; recommended fixture                                                                                                                                                                                                                                                                                                            | council r2 probe                                                                |
| D5, §5bis, §8                            | PR-1's two wrapper lines and their reason (G9b) stated explicitly; `date -u` made MUST: kind `dateopt`, rows G7i and G9l, the TZ fixture, the skew-aware hook                                                                                                                                                                                                          | coordinator ruling 2026-09-27 on the two open questions                         |
| §5bis.3, §5ter.3                         | Every kind's operator fixed, with required classes and a fixed direction for conditions (a refusal guard only `false`, a selection branch both); step 4 `OPERATOR` compares each mutant with the operator S3 computes; selftest cases j, n and o                                                                                                                       | gate r3 R1: G2a's mutant swapped to `while false; do` went green                |
| §5bis.3, §5bis.4, YAML                   | Exit-value operator; 14 `/v` mutants (op `val`) and G9b/v; contract N.1 enforced by mutation                                                                                                                                                                                                                                                                           | gate r3 R2                                                                      |
| §5bis.3, YAML                            | `relop` class on arithmetic comparisons; mutant G2/-gt                                                                                                                                                                                                                                                                                                                 | gate r3 R3                                                                      |
| §5bis.3, §5ter.4                         | Normative 27-site plant covering all 17 kinds; four grammar cells made exact; selftest (a)                                                                                                                                                                                                                                                                             | gate r3 R4; the round-2 prototype found 24 of the 27                            |
| §5ter.3, §7                              | `STALE-DERIVATION`: a blob other than `derived_from.blob` is an error; selftest (k)                                                                                                                                                                                                                                                                                    | gate r3 R5                                                                      |
| D6, §5ter, §8                            | W69 sentinel shape from PR-1 on; `wa-codex-pin verdict` made required by an `operator[gui]` arming step after PR-1, and the window until then stated (§8 item 10); "15 site kinds" corrected to 17                                                                                                                                                                     | gate r3 R6                                                                      |
| header, §5bis.1                          | Re-scope note; the fourth same-cause finding; a third root cause (author choice inside the contract) and its cure                                                                                                                                                                                                                                                      | gate r4 (5852422768); owner ruling 2026-09-27, generator route                  |
| §5bis.2, YAML                            | Schema 2: one entry per generated id carrying disposition, mode and killers (reason on EQUIVALENT, an optional label); no `to`, anchor or `covers`; any other key is `SCHEMA`                                                                                                                                                                                          | gate r4 re-scope items 1 and 3 (H7)                                             |
| §5bis.3                                  | Generated members replace fixed operators and required classes: every member of every class, both constants for test operands, `always` for every `if`/`elif`, `remove` for every `exit`/`return`; rules for duplicates, no-ops, one line in and out (`LINES`) and `SPAN`                                                                                              | gate r4 §1 (H1, H2, the mini `\|\| die`), re-scope items 1 and 3                |
| §5bis.3                                  | Masking runs over the whole file; raw-line kinds skip single-quoted text; the `abspath` cell states the lexical rule the extractor always used. No wrapper count changes                                                                                                                                                                                               | gate r4 re-scope item 5 (installer receipt)                                     |
| §5bis.3a                                 | Mutant ids and their stability, with the one stated limit                                                                                                                                                                                                                                                                                                              | gate r4 re-scope item 1                                                         |
| §5bis.5, §5bis.6, §5bis.8                | 177 mutants (170 MUST, 7 EQUIVALENT), two new EQUIVALENT removals, the rendered table per id, both suites re-measured                                                                                                                                                                                                                                                  | gate r4 re-scope items 1 and 5                                                  |
| §5ter.3                                  | Steps 2–4 rewritten: `MUTANT-COUNT`; generation with `SPAN`, `NO-MEMBER`, `ID-COLLISION`, `LINES`, `SYNTAX`; annotation closure with `UNANNOTATED`, `PHANTOM`. Anchors, `OPERATOR`, `DOUBLE-CLAIM`, `NO-STMT` and `NO-OP` retired; the parity rendering defined                                                                                                        | gate r4 re-scope items 1 and 3                                                  |
| §5ter.4                                  | Plant moved after `export PYTHONPATH=`; new cases b (ids), c (closure), d (one line), m (the `[ … ] \|\| die` form), n (floor); schema-1 cases b, c, d, j, l, m, n and o retired with the mechanisms they tested (letters b, c, d, m, n and o now name new cases)                                                                                                      | gate r4 re-scope item 4                                                         |
| §5ter.5, §7, §8                          | The four S3-surface paths become hot-zone paths (floor 3), with floor tests; why the floor and not a base-relative S3 check; §8 item 10 narrowed                                                                                                                                                                                                                       | gate r4 re-scope item 2                                                         |
| §5ter.6, §9                              | The generator on #7340's installer, and the prototype's receipts                                                                                                                                                                                                                                                                                                       | gate r4 re-scope item 5                                                         |
| §5bis.3, §5ter.3, §5ter.4, §5ter.6       | What masking hides is an error: `MASKED` for a site inside a double-quoted `$( … )` or the string of `eval`, `trap` or `sh -c`; `UNSUPPORTED` for a heredoc or a backquote; the comment rule widened to a `#` after an operator; selftest o                                                                                                                            | council round 4 (codex-gpt-5.6-sol BLOCKER 1, kimi-code/k3 MAJOR 2 and MINOR 3) |
| §5bis.3a, §5bis.6, YAML, §5ter.3         | Ids at 64 bits (16 hex digits), so an edited line cannot be searched into its old id; `ID-COLLISION` defined on the file's normal forms; the 40-bit blob prefix stated as an accident check                                                                                                                                                                            | council round 4 (codex-gpt-5.6-sol BLOCKER 2)                                   |
| §5ter.5, §8, §9                          | The merge queue re-floors a PR against the entry ahead of it (measured); PR-1's gate reads what changed in the inventory and the spec before it; §8 item 11: the hot-zone list is itself floor 1, stated as the harness's residual with its cure                                                                                                                       | council round 4 (codex-gpt-5.6-sol BLOCKER 3 and MAJOR 4, kimi-code/k3 MINOR 5) |
| §5bis.3, §5bis.5, §5ter.3, §5ter.4, YAML | Dedupe ignores `SPAN` members; finer value mutations listed as not generated; G7c's reason split into what was measured and what is judged; the Totals paragraph rendered inside the parity block; selftest p (counts, `NO-MEMBER`, `ID-COLLISION`)                                                                                                                    | council round 4 (kimi-code/k3 MINOR 4, 7, 8, 9; codex-gpt-5.6-sol MINOR 6, 7)   |
| §5bis.3, §5bis.3a, §5ter.3, §5ter.5, §8  | After the delta round, accuracy only: the masking check limited in words to literal text, with §8 item 12 opened for the rest; no time claim on the hash search; the blob prefix's limit restated for site-free lines; the queue ruleset's enforcement and empty bypass list; a second read of the pre-PR-1 range at PR-1's merge; §8 item 11 records the seats' split | council round 4b (codex-gpt-5.6-sol 1–4, 10; kimi-code/k3 2–5)                  |
