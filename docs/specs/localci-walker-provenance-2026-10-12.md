# LocalCI phase F: where the system-job walker's bytes come from (2026-10-12)

> Written under Builder Contract §1. The walker-provenance cause went red three times in the
> phase F intake spec (#8267): rev 6 installed before C1 existed; rev 7 accepted a session-authored
> hash and any commit; rev 8 let the `/usr/bin/git` xcrun shim resolve to a session-owned
> `Xcode.app`. The PR suspended instead of taking a fourth round. This document fixes that surface;
> phase F intake and C9 mean #8267's last revision, to be re-landed as its successor.

## The property

In the `zero-ops` ceremonies C3 and C12 (`docs/specs/localci-sovereign-2026-10-07.md`), **no byte a
session can write is executed before, during, or after the privileged credential**. The walker
(`scripts/localci/localci-trust-path-walk.sh`) is BASE code. It is installed root-owned and runs
only unprivileged, as `localci`, after `sudo -k`.

Ceremony bodies are committed under `docs/ceremonies/`, frozen and gated at `M`. The launcher is
the repo file `scripts/localci/ceremonies/launcher.zsh`; the merge that lands it records its sha256
literally in `docs/rules/RULINGS.md`. Zero reads both that value and `M` on the phone at github.com,
at `M`. After the one-time bootstrap, Zero types only `M` and an allow-listed ceremony name.

## The chain, steps 0–5

| step | value or bytes                                       | tool and authority                                                     | trust source                                                   |
| ---- | ---------------------------------------------------- | ---------------------------------------------------------------------- | -------------------------------------------------------------- |
| 0    | CLT git closure, `/bin/realpath`, installed launcher | `/usr/bin/find`, `/bin/realpath`, `/usr/bin/stat`; Apple sealed volume | the closure assertion below, before git runs                   |
| 1    | `M` and the launcher's sha256                        | Zero reads both on the phone under C9's device rule                    | a device no session drives                                     |
| 2    | objects containing `M`                               | CLT git 2.54.0 (Apple Git-157), as `zero-ops`, from the pinned remote  | object verification plus `M`; transport cannot choose the tree |
| 3    | launcher, walker, wrapper, and ceremony blobs        | hardened CLT git `cat-file blob "${M}:…"`                              | the tree of `M`                                                |
| 4    | each extracted blob's sha256                         | `/usr/bin/shasum -a 256`, as `zero-ops`                                | computed in the 0700 work directory and journalled             |
| 5    | installed launcher, walker, and wrapper              | `/usr/bin/sudo /usr/bin/install -o root -g wheel -m 0555`              | only bytes extracted and checked in steps 3–4                  |

### Step 0: judge only the executable closure

The runtime assertion walks the CLT git executable closure, `/bin/realpath`, the installed
launcher, and each ancestor named in the launcher below. Non-links must be root-owned, have no
group/other write bit, and have no write-granting ACL. On BSD `find`, `-perm +0022` means any bit in
the mask; `-perm -0022` would require both bits and miss modes such as 0775 and 0757.

Every link is resolved with `/bin/realpath`. A dangling link, a target outside
`/usr/bin/*|/usr/lib/*|/usr/libexec/*|/usr/share/*|/System/*|CLT/*`, or a resolved target that is
not root-owned, is group/other-writable, or has an ACL halts. The CLT allowance includes
`CLT/usr/bin`, where `git-core/scalar` and `git-shell` resolve. `/usr/local/*` is not an allowed
resolved target. With `-exec … {} +`, BSD `find` evaluates the primary as true and reports a
failing invocation through its own exit status, so a bad link halts through `|| exit 65`, never
through printed output. `/etc/zshenv` must be absent because even `zsh -f` always sources it from the data
volume.

Measured read-only on Pro on 2026-10-12: the closure has 149 links, all resolving inside CLT; the
whole CLT has 22,697 links and one unrelated dangling link,
`usr/bin/crashlog` → `/Library/Developer/SharedFrameworks`. The old 6,714 count described one SDK,
not CLT, so neither number is a whole-tree acceptance rule. The gate also measured:

- CLT git is 2.54.0 (Apple Git-157); `git` and `git-remote-https` link only into allowed sealed
  paths, have no `LC_RPATH`, and the signature is `com.apple.git` with library validation.
- A hostile `DEVELOPER_DIR`, `GIT_EXEC_PATH`, or git configuration source is removed or refused;
  `ext::` stays disabled and SHA1 collision detection stays active.
- CLT has no `etc/gitconfig`; `GIT_CONFIG_NOSYSTEM=1` disables Apple's
  `usr/share/git-core/gitconfig`.

### One-time C3 bootstrap

C3 first provisions the directories and accounts described below. Until the root-owned launcher
exists, Zero types these exact lines, never text pasted from a session output. The first line opens
a sterile child, so `exit` terminates only that process. `M` and `H` are copied by hand from the
phone; the fetch is necessarily full and costs about 2.7 GB because a depth-1 fetch cannot prove an
arbitrary ancestor `M`.

```zsh
/usr/bin/env -i HOME=/Users/zero-ops PATH=/usr/bin:/bin:/usr/sbin:/sbin /bin/zsh -f
setopt pipefail; umask 077
M='<40 lowercase hex>'; H='<64 lowercase hex>'; CLT=/Library/Developer/CommandLineTools; GIT="$CLT/usr/bin/git"; d=/Users/zero-ops/ceremony/C3-launcher-bootstrap
/bin/mkdir -m 0700 "$d" || exit 65
g() { /usr/bin/env -i HOME="$d" PATH=/usr/bin:/bin:/usr/sbin:/sbin GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_REPLACE_OBJECTS=1 GIT_TERMINAL_PROMPT=0 "$GIT" -c core.hooksPath=/dev/null -c core.fsmonitor=false -c maintenance.auto=false -c protocol.allow=never -c protocol.https.allow=always "$@"; }
g init --bare --template= "$d/w.git" && g -C "$d/w.git" fetch --no-tags https://github.com/Bali-Zero/Teman2.git main || exit 69
g -C "$d/w.git" cat-file -e "${M}^{commit}" && g -C "$d/w.git" merge-base --is-ancestor "$M" FETCH_HEAD || exit 65
g -C "$d/w.git" cat-file blob "${M}:scripts/localci/ceremonies/launcher.zsh" >"$d/launcher.zsh" || exit 65
/bin/chmod 0500 "$d/launcher.zsh"; [[ "$(/usr/bin/shasum -a 256 "$d/launcher.zsh" | { read -r x _; print -r -- "$x"; })" == "$H" ]] || exit 65
/usr/bin/sudo /usr/bin/install -d -o root -g wheel -m 0555 /usr/local/localci /usr/local/localci/bin && /usr/bin/sudo /usr/bin/install -o root -g wheel -m 0555 "$d/launcher.zsh" /usr/local/localci/bin/ceremony-launcher.zsh || exit 65
exit
```

The installed file and `/`, `/usr`, `/usr/local`, `/usr/local/localci`, and its `bin` ancestor are
part of every subsequent trust walk and must be root-owned, non-writable by group/other, and free
of ACLs.

### The fixed launcher

Every ceremony is a new non-login process, never pasted into an interactive login shell:

```zsh
/usr/bin/env -i HOME=/Users/zero-ops PATH=/usr/bin:/bin:/usr/sbin:/sbin /bin/zsh -f /usr/local/localci/bin/ceremony-launcher.zsh "$M" "$NAME"
```

Arguments survive `env -i`. The launcher validates `$1` as 40 lowercase hex and `$2` against its
allow-list. It sets `REMOTE` internally to one of two literals by ceremony name; callers cannot
select it. Its fetch has a 600-second pure-zsh watchdog; the fetch subshell `exec`s git, so the PID
the watchdog signals is git itself, not a parent shell whose child would outlive it. The
normative repo file contains this text:

```zsh
setopt nounset pipefail
unsetopt BG_NICE
umask 077
(( $# == 2 )) || exit 64
M=$1; NAME=$2
[[ ${#M} -eq 40 && "$M" != *[^0-9a-f]* ]] || exit 64
CLT=/Library/Developer/CommandLineTools; GIT="$CLT/usr/bin/git"
case "$NAME" in
  C3-bootstrap|C3) REMOTE='https://github.com/Bali-Zero/Teman2.git'; transport=(-c protocol.allow=never -c protocol.https.allow=always); ssh_allow= ;;
  C12) REMOTE='ssh://mini/Users/nuzantara/localci/replica.git'; transport=(-c protocol.allow=never -c protocol.ssh.allow=always); ssh_allow=$'command line:\tprotocol.ssh.allow=always' ;;
  *) exit 64 ;;
esac
[[ ! -e /etc/zshenv && ! -L /etc/zshenv ]] || exit 65
TS=$(/bin/date -u +%Y%m%dT%H%M%SZ); d="/Users/zero-ops/ceremony/$TS"
cfg=(-c core.hooksPath=/dev/null -c core.fsmonitor=false -c maintenance.auto=false)
gcmd=(/usr/bin/env -i HOME="$d" PATH=/usr/bin:/bin:/usr/sbin:/sbin GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_REPLACE_OBJECTS=1 GIT_TERMINAL_PROMPT=0 "$GIT" "${cfg[@]}" "${transport[@]}")
g() { "${gcmd[@]}" "$@"; }
link_ok='CLT=/Library/Developer/CommandLineTools; for p; do r=$(/bin/realpath "$p") || exit 1; case "$r" in "$CLT"/*|/usr/bin/*|/usr/lib/*|/usr/libexec/*|/usr/share/*|/System/*) ;; *) exit 1 ;; esac; [[ -z "$(/usr/bin/find "$r" -prune \( ! -user root -o -perm +0022 -o -acl \) -print)" ]] || exit 1; done'
trust=(/ /Library /Library/Developer "$CLT" "$CLT/usr" "$CLT/usr/bin" "$CLT/usr/libexec" "$CLT/usr/share" /bin /usr /usr/bin /System /usr/local /usr/local/localci /usr/local/localci/bin /usr/local/localci/bin/ceremony-launcher.zsh)
bad=$({ /usr/bin/find "${trust[@]}" -prune \( -type l \( ! -exec /bin/zsh -fc "$link_ok" zsh {} + \) -o ! -type l \( ! -user root -o -perm +0022 -o -acl \) \) -print || exit 65; /usr/bin/find "$GIT" "$CLT/usr/libexec/git-core" "$CLT/usr/share/git-core" /bin/realpath \( -type l \( ! -exec /bin/zsh -fc "$link_ok" zsh {} + \) -o ! -type l \( ! -user root -o -perm +0022 -o -acl \) \) -print || exit 65; }) || exit 65
[[ -z "$bad" ]] || exit 65
/bin/mkdir -m 0700 "$d" || exit 65
[[ -z "$(/usr/bin/find "$d" ! -path "$d" -print -quit)" ]] || exit 65
g init --bare --template= "$d/w.git" || exit 65
expected=$'file:config\tcore.repositoryformatversion=0\nfile:config\tcore.filemode=true\nfile:config\tcore.bare=true\nfile:config\tcore.ignorecase=true\nfile:config\tcore.precomposeunicode=true\ncommand line:\tcore.hookspath=/dev/null\ncommand line:\tcore.fsmonitor=false\ncommand line:\tmaintenance.auto=false\ncommand line:\tprotocol.allow=never'
[[ "$REMOTE" == https:* ]] && expected+=$'\ncommand line:\tprotocol.https.allow=always' || expected+=$'\n'"$ssh_allow"
actual=$(g -C "$d/w.git" config --list --show-origin | /usr/bin/sort)
[[ "$actual" == "$(/usr/bin/printf '%s\n' "$expected" | /usr/bin/sort)" ]] || exit 65
watch_fetch() { zmodload zsh/zselect || return 65; local pid=$1; integer ticks=0; while kill -0 "$pid" 2>/dev/null && (( ticks < 600 )); do zselect -t 100; (( ++ticks )); done; kill -0 "$pid" 2>/dev/null || return 0; kill -TERM "$pid" 2>/dev/null; zselect -t 500; kill -KILL "$pid" 2>/dev/null; return 69; }
fetch_with_watchdog() { local fetch_pid watch_pid fetch_rc watch_rc; ( exec "${gcmd[@]}" -C "$d/w.git" fetch --no-tags "$REMOTE" main ) & fetch_pid=$!; watch_fetch "$fetch_pid" & watch_pid=$!; wait "$watch_pid"; watch_rc=$?; (( watch_rc == 0 )) || kill -TERM "$fetch_pid" 2>/dev/null; wait "$fetch_pid"; fetch_rc=$?; (( fetch_rc == 0 && watch_rc == 0 )); }
fetch_with_watchdog || exit 69
g -C "$d/w.git" cat-file -e "${M}^{commit}" || exit 65
g -C "$d/w.git" merge-base --is-ancestor "$M" FETCH_HEAD || exit 65
journal=/Users/zero-ops/ceremony/last-main
if [[ -e "$journal" || -L "$journal" ]]; then
  [[ -f "$journal" && ! -L "$journal" && -r "$journal" ]] || exit 65
  PREV_M=$(/bin/cat "$journal"); [[ ${#PREV_M} -eq 40 && "$PREV_M" != *[^0-9a-f]* ]] || exit 65
  g -C "$d/w.git" merge-base --is-ancestor "$PREV_M" "$M" || exit 65
else
  [[ "$NAME" == C3-bootstrap ]] || exit 65
fi
g -C "$d/w.git" cat-file blob "${M}:docs/ceremonies/${NAME}.zsh" >"$d/ceremony.zsh" || exit 65
/bin/chmod 0500 "$d/ceremony.zsh" || exit 65
/bin/zsh -f "$d/ceremony.zsh"; ceremony_rc=$?
(( ceremony_rc == 0 )) || exit "$ceremony_rc"
/usr/bin/printf '%s\n' "$M" >"$d/last-main.new" && /bin/chmod 0600 "$d/last-main.new" && /bin/mv -f "$d/last-main.new" "$journal" || exit 65
```

The ceremony file is owned by `zero-ops`, mode 0500, inside its fresh 0700 work directory. It is a
path argument, so stdin remains the tty: `read`, a background waiter, or `head -c` in the body
cannot consume or truncate later source and still return 0. The launcher's `exit` statuses end only
its own process.

The sorted config equality is an exact allow-list. Every git call carries the same `-c` set;
`protocol.allow=never` is default deny. GitHub HTTPS is literal for C3; Mini SSH is literal for C12.
`M` must exist and be an ancestor of fetched `main`.

The journal is `/Users/zero-ops/ceremony/last-main`, created and replaced by `zero-ops` at mode 0600. If it exists but is unreadable, the launcher halts. If absent, the launcher halts unless the
name is exactly `C3-bootstrap`; only that ceremony skips the rewind comparison and creates it after
success.

## Roles, directories, snapshots, and handoff

C3/root creates `/Users/zero-ops` as `zero-ops:staff` mode 0711 and removes the macOS default ACL
with `/bin/chmod -N`. `zero-ops` creates `/Users/zero-ops/ceremony` mode 0700 and
`/Users/zero-ops/handoff` mode 0755. C3/root creates `/Users/localci` as `root:wheel` mode 0711;
`localci` creates its own `/Users/localci/handoff` mode 0755 and
`/Users/localci/ceremony-in` mode 0700. Their per-ceremony leaves are fresh: handoff leaves are
0755, the ceremony input leaf is 0700, and each creator owns its leaf.

Git, `shasum`, and redirects run only as `zero-ops` in its 0700 work directory. Git never runs
through `sudo`. Root is used only for snapshots and `install`; snapshot files live in fresh
`/private/var/root/localci-snapshots/$TS`. Writes use explicit commands, never root-directory
redirects:

```zsh
/usr/bin/sudo /usr/bin/sfltool dumpbtm | /usr/bin/sudo /usr/bin/tee "$SNAP/btm" >/dev/null
/usr/bin/sudo /usr/bin/crontab -l -u root | /usr/bin/sudo /usr/bin/tee "$SNAP/root.crontab" >/dev/null
/usr/bin/sudo /bin/cat "$SNAPFILE" | /usr/bin/sudo -u localci /usr/bin/tee "/Users/localci/ceremony-in/$TS/$SNAPNAME" >/dev/null
```

The waiter starts and writes `ready`; then zero-ops runs `sudo -k` and writes `go`; only then
`localci` runs the walker. A missing or untraversable parent can only cause `WAITER-TIMEOUT` rc 72,
a liveness failure, never acceptance. Both timestamp leaves must be newly created, non-links, and
empty. `localci` has no sudoers entry and tickets are per user.

## C12 and remaining scope facts

C12 extracts both `scripts/localci/localci-trust-path-walk.sh` and
`scripts/localci/localci_merger_tick.sh` from `${M}:`, hashes them as zero-ops, and installs exactly
those bytes. `/Users/localci/code/current/…` is only a post-install `cmp -s` source, never an
install source.

Docker has no published checksum, so its trust is the vendor endpoint over C9's CA-pinned TLS; a
session-authored hash is only a journal value. Gitleaks is checked against published checksums.
`/Library/LaunchAgents` remains in scope. Session-user jobs remain out of scope because they cross
no privilege boundary.

## Tests and mutants the build owes

- `walker-installed-through-shim-git`
- `walker-sha-from-session`
- `git-config-honoured-in-ceremony`
- `ceremony-dir-unreadable-to-localci`
- `walker-runs-before-sudo-k`
- `stale-handoff`
- `ceremony-in-dir-symlink`
- `config-list-not-allowlisted`
- `transport-unpinned`
- `ceremony-not-from-M`
- `rewind-accepted`
- `perm-dash-0022-misses-0775`
- `ceremony-from-stdin`
