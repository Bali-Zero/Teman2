# LocalCI phase F: where the system-job walker's bytes come from (2026-10-12)

> Written under Builder Contract §1. The walker-provenance cause went red three times in the
> phase F intake spec (#8267): rev 6 installed before C1 existed; rev 7 accepted a session-authored
> hash and any commit; rev 8 let the `/usr/bin/git` xcrun shim resolve to a session-owned
> `Xcode.app`. The PR suspended instead of taking a fourth round. This document fixes that surface;
> the intake spec consumes it without re-deriving it.

## The property

In the `zero-ops` ceremonies C3 and C12 (`docs/specs/localci-sovereign-2026-10-07.md`, “Phase F
intake without GitHub”), **no byte a session can write is executed before, during, or after the
privileged credential**. The walker (`scripts/localci/localci-trust-path-walk.sh`) is BASE code. It
is installed root-owned and runs only unprivileged, as `localci`, after `sudo -k`.

Ceremony bodies are no longer pasted session text. They are committed under `docs/ceremonies/`,
frozen and gated at `M`. The only fixed exception is the launcher below: Zero verifies it once and
types `M` (exactly 40 lowercase hex characters, read on the phone) and `NAME`. The rule is: **bytes
frozen and gated at M; Zero verifies the launcher and M**.

## The chain, steps 0–5

| step | value or bytes                                   | tool and authority                                                     | trust source                                                                   |
| ---- | ------------------------------------------------ | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| 0    | CLT git's executable closure and `/bin/realpath` | `/usr/bin/find`, `/bin/realpath`, `/usr/bin/stat`; Apple sealed volume | the closure-only assertion below, before git runs                              |
| 1    | `M`, the main commit                             | Zero reads it on the phone under C9's device rule                      | a device no session drives                                                     |
| 2    | the objects containing `M`                       | CLT git 2.54.0 (Apple Git-157), as `zero-ops`, from an allowed remote  | object verification plus `M`; the transport may lie but cannot choose the tree |
| 3    | walker, wrapper, and ceremony blobs at `${M}:…`  | the same hardened CLT git and `cat-file blob`                          | the tree of `M`                                                                |
| 4    | each extracted blob's sha256                     | `/usr/bin/shasum -a 256`, as `zero-ops`                                | computed in the 0700 work directory and journalled                             |
| 5    | installed walker and wrapper                     | `/usr/bin/sudo /usr/bin/install -o root -g wheel -m 0555`              | only the bytes extracted in step 3                                             |

### Step 0: judge only the executable closure

The runtime assertion walks only
`/Library/Developer/CommandLineTools/usr/bin/git`,
`/Library/Developer/CommandLineTools/usr/libexec/git-core/` (including `git-remote-https`),
`/Library/Developer/CommandLineTools/usr/share/git-core/`, their path ancestors, and
`/bin/realpath`. `/bin/realpath` is `root:wheel`. Non-links must be root-owned, have no group/other
write bit and no write-granting ACL. Every link is judged by `/bin/realpath`: a dangling link or a
target outside CLT, `/usr`, or `/System` halts. Links outside this closure are not judged.

Measured read-only on Pro on 2026-10-12: the closure has 149 links, all resolving inside CLT; the
whole CLT has 22,697 links and one unrelated dangling link,
`usr/bin/crashlog` → `/Library/Developer/SharedFrameworks`. The old 6,714 count described one SDK,
not CLT, so neither number is a whole-tree acceptance rule.

The same gate measured all of the following and steps 0–5 HOLD under test:

- CLT git is 2.54.0 (Apple Git-157); `git` and `git-remote-https` link only into `/usr/lib` and
  `/System`, have no `LC_RPATH`, and the signature is `com.apple.git` with library validation.
- The exec directory remains the CLT directory even when `DEVELOPER_DIR` and `GIT_EXEC_PATH` are
  hostile before `env -i`; the launcher then removes both variables.
- The hardened environment drops every hostile configuration source, refuses `ext::`, and has
  SHA1 collision detection active.
- CLT has no `etc/gitconfig`. Apple's file is `usr/share/git-core/gitconfig`, and
  `GIT_CONFIG_NOSYSTEM=1` disables it.

### The fixed launcher

`REMOTE` is either the fixed GitHub HTTPS URL or Mini's replica (`mini:` or `ssh://mini/…`); `TS`
comes from the sealed system clock. This is the sole launcher, identical for every ceremony. Its
second line is step 0's `find`; its third line is the hardened init, exact-config check, fetch,
forward-only check, and `M` selection; its fourth line streams the ceremony from `M` directly into
`/bin/zsh -f`.

```zsh
setopt pipefail; CLT=/Library/Developer/CommandLineTools; GIT="$CLT/usr/bin/git"; TS=$(/bin/date -u +%Y%m%dT%H%M%SZ); d="/Users/zero-ops/ceremony/$TS"; cfg=(-c core.hooksPath=/dev/null -c core.fsmonitor=false -c maintenance.auto=false); transport=(-c protocol.allow=never -c protocol.https.allow=always); ssh_allow=; case "$REMOTE" in https://github.com/*) ;; mini:*|ssh://mini/*) transport+=(-c protocol.ssh.allow=always); ssh_allow=$'command line:\tprotocol.ssh.allow=always' ;; *) exit 64 ;; esac; g() { /usr/bin/env -i HOME="$d" PATH=/usr/bin:/bin:/usr/sbin:/sbin GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_REPLACE_OBJECTS=1 GIT_TERMINAL_PROMPT=0 "$GIT" "${cfg[@]}" "${transport[@]}" "$@"; }
bad=$({ /usr/bin/find / /Library /Library/Developer "$CLT" "$CLT/usr" "$CLT/usr/bin" "$CLT/usr/libexec" "$CLT/usr/share" /bin /usr /usr/bin /System -prune \( -type l \( ! -exec /bin/zsh -fc 'for p; do r=$(/bin/realpath "$p") || exit 1; case "$r" in /Library/Developer/CommandLineTools/*|/System/*|/usr/*) ;; *) exit 1 ;; esac; done' zsh {} + \) -o ! -type l \( ! -user root -o -perm -0022 -o -acl \) \) -print || exit 65; /usr/bin/find "$CLT/usr/bin/git" "$CLT/usr/libexec/git-core" "$CLT/usr/share/git-core" /bin/realpath \( -type l \( ! -exec /bin/zsh -fc 'for p; do r=$(/bin/realpath "$p") || exit 1; case "$r" in /Library/Developer/CommandLineTools/*|/System/*|/usr/*) ;; *) exit 1 ;; esac; done' zsh {} + \) -o ! -type l \( ! -user root -o -perm -0022 -o -acl \) \) -print || exit 65; }) || exit 65; [[ -z "$bad" ]] || exit 65
/bin/mkdir -m 0700 "$d" || exit 65; [[ -z "$(/usr/bin/find "$d" ! -path "$d" -print -quit)" ]] || exit 65; g init --bare --template= "$d/w.git" || exit 65; expected=$'file:config\tcore.repositoryformatversion=0\nfile:config\tcore.filemode=true\nfile:config\tcore.bare=true\nfile:config\tcore.ignorecase=true\nfile:config\tcore.precomposeunicode=true\ncommand line:\tcore.hookspath=/dev/null\ncommand line:\tcore.fsmonitor=false\ncommand line:\tmaintenance.auto=false\ncommand line:\tprotocol.allow=never\ncommand line:\tprotocol.https.allow=always'; [[ -n "$ssh_allow" ]] && expected+=$'\n'"$ssh_allow"; actual=$(g -C "$d/w.git" config --list --show-origin | /usr/bin/sort); [[ "$actual" == "$(/usr/bin/printf '%s\n' "$expected" | /usr/bin/sort)" ]] || exit 65; [[ ${#M} -eq 40 && "$M" != *[^0-9a-f]* ]] || exit 64; g -C "$d/w.git" fetch --no-tags "$REMOTE" main || exit 69; g -C "$d/w.git" cat-file -e "${M}^{commit}" || exit 65; g -C "$d/w.git" merge-base --is-ancestor "$M" FETCH_HEAD || exit 65; if [[ -r /Library/LocalCI/journal/last-main ]]; then PREV_M=$(/bin/cat /Library/LocalCI/journal/last-main); [[ ${#PREV_M} -eq 40 && "$PREV_M" != *[^0-9a-f]* ]] || exit 65; g -C "$d/w.git" merge-base --is-ancestor "$PREV_M" "$M" || exit 65; fi
g -C "$d/w.git" cat-file blob "${M}:docs/ceremonies/${NAME}.zsh" | /usr/bin/env -i HOME=/Users/zero-ops PATH=/usr/bin:/bin:/usr/sbin:/sbin M="$M" NAME="$NAME" REMOTE="$REMOTE" TS="$TS" /bin/zsh -f
```

The sorted equality above is an exact allow-list, not an empty-config assertion. For HTTPS it has
exactly these ten logical entries (origin whitespace is a tab):

- `file:config` — `core.repositoryformatversion=0`, `core.filemode=true`, `core.bare=true`,
  `core.ignorecase=true`, `core.precomposeunicode=true`;
- `command line:` — `core.hooksPath=/dev/null`, `core.fsmonitor=false`,
  `maintenance.auto=false`, `protocol.allow=never`, `protocol.https.allow=always`.

Mini-over-SSH adds exactly `command line: protocol.ssh.allow=always`. Any duplicate or other line
halts. Every git call carries the same `-c` set. `protocol.allow=never` is the default deny; HTTPS
is always pinned open, and SSH is opened only for Mini's replica.

`M` must exist and be an ancestor of fetched `main`. The root-owned, non-writable
`/Library/LocalCI/journal/last-main` records the preceding accepted `M`; it too must be an ancestor
of the new `M`, or the ceremony halts. On success, the ceremony writes `M` to a zero-ops file and
uses `sudo install -o root -g wheel -m 0444` to replace `last-main`. This detects a rewind. It does
not make GitHub infallible: today force-push and deletion are disabled, `enforce_admins` is true,
and the rulesets have no bypass, but a repo-admin session token could lift the protection,
force-push, and restore it.

## Roles, directories, snapshots, and handoff

Git, `shasum`, and ordinary redirects run only as `zero-ops` in
`/Users/zero-ops/ceremony/$TS`, owner `zero-ops:staff`, mode 0700. `/bin/mkdir -m 0700` must create
the leaf afresh and `find` must show it empty. Git is never run through `sudo`: doing so would put a
network-facing pack parser under root.

Root is used only for the privileged snapshots and `install`. Snapshot files live in the fresh
root-only `/private/var/root/localci-snapshots/$TS`, not in the git work directory. Writes use the
explicit commands below, never a redirect into a root directory. `/etc/crontab`, when present,
uses the same `sudo cat | sudo tee` shape; the root tab existence probe also runs under `sudo`.

`localci` creates `/Users/localci/ceremony-in/$TS` itself, owner `localci:staff`, mode 0700, with
`sudo -u localci /bin/mkdir -m 0700`; creation fails on a pre-existing path, then a non-link and
empty-directory assertion runs as `localci`. For each snapshot, localci writes its own copy with
the third command below. No `install` targets a directory that a symlink could redirect.

```zsh
/usr/bin/sudo /usr/bin/sfltool dumpbtm | /usr/bin/sudo /usr/bin/tee "$SNAP/btm" >/dev/null
/usr/bin/sudo /usr/bin/crontab -l -u root | /usr/bin/sudo /usr/bin/tee "$SNAP/root.crontab" >/dev/null
/usr/bin/sudo /bin/cat "$SNAPFILE" | /usr/bin/sudo -u localci /usr/bin/tee "/Users/localci/ceremony-in/$TS/$SNAPNAME" >/dev/null
```

The per-ceremony rendezvous is fresh and asymmetric:

- `/Users/localci/handoff/$TS`: owner `localci:staff`, mode 0755, created by localci with
  `/usr/bin/sudo -u localci /bin/mkdir -m 0755`; localci writes `ready`, zero-ops reads it.
  `/Users/localci` is `localci:staff` mode 0711 so zero-ops can traverse to that leaf.
- `/Users/zero-ops/handoff/$TS`: owner `zero-ops:staff`, mode 0755, created by zero-ops with
  `/bin/mkdir -m 0755`; zero-ops writes `go`, localci reads it. `/Users/zero-ops` is
  `zero-ops:staff` mode 0711, not 0700; only its handoff leaf is 0755 and its ceremony directory
  remains 0700.

Both `mkdir` calls must create a missing leaf and both leaves must be empty. Therefore stale files
cannot satisfy the order. The waiter starts first and writes `ready`; only then zero-ops runs
`sudo -k` and writes `go`; only then localci runs the walker. Every wait has a bounded failure exit.
`localci` has no sudoers entry and tickets are per user.

The git work directory and both handoff trees sit under the two homes, outside the
`/Library/LocalCI` trust-walk root. They therefore neither make the walk exit 1 nor trip its
`! -user root` rule on every tick.

## C12 and remaining scope facts

C12 extracts **both** `scripts/localci/localci-trust-path-walk.sh` and
`scripts/localci/localci_merger_tick.sh` from `${M}:` with the hardened CLT git above, hashes them
as zero-ops, then installs exactly those extracted files. `/Users/localci/code/current/…` is only a
post-install drift source for `cmp -s`; it is never an install source. Every ceremony body itself
comes from `${M}:docs/ceremonies/${NAME}.zsh` through the fixed launcher.

Docker and gitleaks do not have the same upstream proof. `download.docker.com` publishes no
checksum, so Docker's trust is the vendor endpoint over C9's CA-pinned TLS; a session-authored
Docker hash is only a journal value, not an independent anchor. Gitleaks is checked against its
published checksums.

`/Library/LaunchAgents` remains in scope. On Pro it contains two Keystone plists whose content is
`{}`; it is not empty. Under AdGuard interception, the negative control still exits 60 and the
pinned read fails closed. Session-user jobs remain out of scope because they cross no privilege
boundary; `zantara-codex` is not an admin, and `balizero` does not exist on Pro.

## Tests and mutants the build owes

- `walker-installed-through-shim-git`: a git outside the CLT closure is accepted.
- `walker-sha-from-session`: `M` or a blob hash comes from a session instead of the phone or local
  computation.
- `git-config-honoured-in-ceremony`: a hostile config source affects git.
- `ceremony-dir-unreadable-to-localci`: the handoff cannot be traversed and the block must fail
  within its bound, not hang.
- `walker-runs-before-sudo-k`: `go` is written before credential invalidation.
- `stale-handoff`: a prior ceremony's `ready` or `go` satisfies a new ceremony.
- `ceremony-in-dir-symlink`: the localci input directory is replaced by a symlink.
- `config-list-not-allowlisted`: an extra or duplicate config line is accepted.
- `transport-unpinned`: a protocol other than pinned HTTPS or Mini SSH is accepted.
- `ceremony-not-from-M`: pasted or working-tree ceremony bytes execute.
- `rewind-accepted`: the new `M` is not descended from the journalled preceding `M`.
