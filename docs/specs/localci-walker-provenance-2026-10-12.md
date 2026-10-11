# LocalCI phase F: where the system-job walker's bytes come from (2026-10-12)

> Written under Builder Contract §1. The walker-provenance cause went red three times in the
> phase F intake spec (#8267):
>
> - rev 6 N1: installed before C1 existed;
> - rev 7 HIGH-1: its sha came from a session and was served from any commit;
> - rev 8 HIGH-A: `/usr/bin/git` is the xcrun shim, and it resolved to a session-owned
>   `Xcode.app`.
>
> The PR was suspended instead of taking a fourth round. This document fixes the surface. The
> intake spec's next revision applies it and does not re-derive it.

## The property

In the `zero-ops` ceremonies (C3 and C12, `docs/specs/localci-sovereign-2026-10-07.md`, "Phase F
intake without GitHub"), **no byte a session can write is executed, before, during or after the
privileged credential**. This is 0a's unconditional wording, restored; rev 8's "while the credential
is active" weakened it.

The walker (`scripts/localci/localci-trust-path-walk.sh`) is session-written BASE code. It is
installed root-owned and is only ever executed unprivileged, as `localci`, after `sudo -k`. Every
byte installed, and every binary that touches those bytes before `install`, is chosen by something
no session can write.

The only session-authored input to a ceremony is the ceremony text itself. Zero reads it at paste
time, and this document states that dependency rather than hiding it.

## The chain, step by step

| step | value or bytes                                                     | tool                                                                                                                   | who owns the tool              | where the trust comes from                                                                                            |
| ---- | ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- | ------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| 0    | the git binary and everything it loads                             | `/usr/bin/find`, `/usr/bin/stat` (sealed system volume)                                                                | Apple, SIP                     | the assert below, run before git is ever executed                                                                     |
| 1    | `M`, the main sha                                                  | read by Zero on the phone, under C9's device rule                                                                      | a device no session drives     | outside Pro                                                                                                           |
| 2    | the objects of `M`                                                 | `/Library/Developer/CommandLineTools/usr/bin/git fetch` from any remote (GitHub, the mirror, Mini's replica, a bundle) | root:wheel, asserted in step 0 | content addressing: git hashes every object it reads, so the transport may be hostile; `M` from step 1 fixes the tree |
| 3    | the walker blob, `${M}:scripts/localci/localci-trust-path-walk.sh` | the same git, `cat-file blob "${M}:…"` (braces: zsh's `:s` modifier mangles `$M:s…`, rev 8 MED-B)                      | as step 2                      | the tree of `M`                                                                                                       |
| 4    | `WSHA`                                                             | `/usr/bin/shasum -a 256` on the extracted blob                                                                         | Apple, SIP                     | computed in `zero-ops` and journalled; never supplied by anyone                                                       |
| 5    | the installed file                                                 | `/usr/bin/sudo /usr/bin/install -o root -g wheel -m 0555`                                                              | Apple, SIP                     | the bytes from step 3                                                                                                 |

**Step 0, the tool is judged before it runs.**

- Never use `/usr/bin/git`: it is an xcrun shim that follows `xcode-select` to `Xcode.app`, which is
  `nuzantara:staff` on Pro.
- Never use anything under `/Applications`, `/opt/homebrew` or `/Users`.
- The ceremony asserts, with `/usr/bin/find` only, that `/Library/Developer/CommandLineTools` and
  each of its ancestors meet item 5's predicate: root-owned, no group or other write, no
  write-granting ACL. This covers `usr/bin/git`, `usr/libexec/git-core/` (where
  `git-remote-https` lives) and `etc/gitconfig`. A symlink is judged by its `realpath` target, which must stay
  inside the CLT tree, `/System` or `/usr`, and never by its own `lrwxrwxrwx` bits. Measured on Pro
  on 2026-10-12, read-only:
  - `find … ! -type l \( ! -user root -o -perm -g+w -o -perm -o+w \)` gives 0;
  - `find … ! -type l -acl` gives 0;
  - all 6,714 links resolve inside the CLT tree, `/System` or `/usr`.

  `xcode-select -p` points at `Xcode.app`, which is why the shim is refused.

**The git environment is hardened.**

- Run under `/usr/bin/env -i HOME=$d PATH=/usr/bin:/bin:/usr/sbin:/sbin` with
  `GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_REPLACE_OBJECTS=1
GIT_TERMINAL_PROMPT=0`.
- Initialise with `git init --bare --template= "$d/w.git"`.
- Pass `-c core.hooksPath=/dev/null -c core.fsmonitor=false` on every call.
- Assert that `git config --list --show-origin` prints nothing.
- Then fetch (`git fetch --no-tags <remote> main`) and assert that `M` equals the fetched main or is
  an ancestor of it (`merge-base --is-ancestor`): main may move between the phone read and the
  fetch, and `M`, not the fetched tip, chooses the bytes.

## Snapshots and the handoff to `localci` (rev 8 MED-C, LOW-1, LOW-2)

- `$d` is a root-only ceremony directory, never `mktemp -d`. Under `env -i`, `mktemp` lands in a
  per-user `/var/folders/…/T/` whose parent is 0700, so the `localci` waiter can never see the go
  flag, and C3 and C12 hang. Create it with
  `/usr/bin/sudo /usr/bin/install -d -o root -g wheel -m 0700 /Library/LocalCI/ceremony/<ts>`, and
  remove it in the block's `trap`.
- Root writes the privileged snapshots there, using Apple binaries only:
  `sfltool dumpbtm`, `crontab -l -u root`, `/etc/crontab` if it exists, and the root-run existence
  test on `/usr/lib/cron/tabs/root`. The rev 8 unprivileged test on that 0700 dir was vacuous.
- The snapshots reach `localci` through
  `/usr/bin/sudo /usr/bin/install -o localci -g staff -m 0400` into `/Users/localci/ceremony-in/`,
  a directory only `localci` can read. Root's crontab may hold secrets, so nothing goes to a
  world-readable path.
- **Handoff order:**
  1. The `localci` waiter is started with `sudo -u localci`. It is inline `/bin/sh` text from the
     ceremony, not session code.
  2. It writes `ready` into `/Library/LocalCI/handoff/`, which C3 creates as `zero-ops:wheel` 0755.
  3. Only after `ready` does the ceremony run `/usr/bin/sudo -k` and then write `go`.
  4. The waiter then executes the walker.

  `localci` has no sudoers entry, so it could not reuse a `zero-ops` ticket in any case, since
  tickets are per user. The order removes the race in which the foreground `-k` beat the
  background start and a stray password prompt appeared.

- Every wait has a bounded loop with a failure exit. A missing `ready` or verdict within the bound
  is a failed ceremony, never a hang.

## Other binaries chosen by bytes (rev 8 LOW-6)

The docker CLI and gitleaks follow the same rule as the CAs did in rev 8 L6:

- the expected sha256 is either a literal written in the spec or a value Zero reads on the phone from
  the vendor's published checksums;
- the download uses C9's TEA-disabled, CA-pinned `curl`;
- a sha "fetched on Mini" or with no stated source is refused. Mini runs sessions too, so it gives
  independence from the ISP, not from the sessions.

## Scope notes the next revision carries (rev 8 LOW-3, LOW-4, LOW-5)

- **`/Library/LaunchAgents` is in scope.** Its agents load for `zero-ops` at a ceremony login, and
  `zero-ops` is an in-scope admin. The directory is empty on Pro today.
- **Why session users are out of scope.** Their jobs hold session rights and cross no boundary.
  `zantara-codex` is not an admin. `balizero` does not exist on Pro and is named only so the rule
  is total across hosts.
- **The AdGuard clause.** Under interception, the negative control still exits 60; it is the pinned
  read that then fails closed.

## Tests and mutants the build owes

- `walker-installed-through-shim-git`: a git outside the CLT tree is accepted.
- `walker-sha-from-session`: `M` or `WSHA` is read from anything but the phone or a local
  computation.
- `git-config-honoured-in-ceremony`: the hardened environment is dropped and a `core.hooksPath`
  runs.
- `ceremony-dir-unreadable-to-localci`: the waiter cannot see `go`, and the block must fail within
  its bound, not hang.
- `walker-runs-before-sudo-k`: `go` is written before `-k`.
