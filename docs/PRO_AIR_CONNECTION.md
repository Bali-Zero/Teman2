# Pro <-> Mini Connection Guide

**Last Updated:** 2026-05-25

Air (`antonellosiano@Nuzantara-9`) was decommissioned on 2026-05-05. The active server peer is Mini.

## Machines

| Machine  | Hostname  | SSH Alias | Tailscale IP     | User        | Hardware                |
| -------- | --------- | --------- | ---------------- | ----------- | ----------------------- |
| **Pro**  | Nuzantara | `pro`     | `100.107.22.111` | `nuzantara` | MacBook Pro M4 Pro 48GB |
| **Mini** | Mini-Pro2 | `mini`    | `100.93.236.6`   | `nuzantara` | Mac mini M4 Pro 24GB    |

## SSH Connection

SSH uses **Tailscale** aliases/IPs, so connections work across networks when both machines are online in the tailnet.

```bash
# From Pro → Mini
ssh mini

# From Mini → Pro
ssh pro
```

### SSH Config (both machines)

**Pro** (`~/.ssh/config`):

```
Host mini
    HostName 100.93.236.6
    User nuzantara
    IdentityFile ~/.ssh/id_ed25519
    AddKeysToAgent yes
    UseKeychain yes

Host pro
    HostName Nuzantara.local
    User nuzantara
    IdentityFile ~/.ssh/id_ed25519
    AddKeysToAgent yes
    UseKeychain yes
```

**Mini** (`~/.ssh/config`):

```
Host pro
    HostName 100.107.22.111
    User nuzantara
    IdentityFile ~/.ssh/id_ed25519
    AddKeysToAgent yes
    UseKeychain yes
    ServerAliveInterval 60
    ServerAliveCountMax 10

Host mini
    HostName 100.93.236.6
    User nuzantara
    IdentityFile ~/.ssh/id_ed25519
    AddKeysToAgent yes
    UseKeychain yes
    ServerAliveInterval 60
    ServerAliveCountMax 10
```

## Connectivity Check

Run this to verify both machines are reachable:

```bash
# Quick check (from either machine)
ping -c 1 100.107.22.111 && echo "Pro: OK" || echo "Pro: UNREACHABLE"
ping -c 1 100.93.236.6 && echo "Mini: OK" || echo "Mini: UNREACHABLE"

# Full SSH check
ssh mini "echo 'Mini SSH: OK'" 2>/dev/null || echo "Mini SSH: FAILED"
ssh pro "echo 'Pro SSH: OK'" 2>/dev/null || echo "Pro SSH: FAILED"
```

## Troubleshooting

### Tailscale not connected

Both machines must be connected to Tailscale and visible in the same tailnet.

```bash
tailscale status
```

### SSH connection refused

Remote Login must be enabled on the target machine:

- **System Settings → General → Sharing → Remote Login → ON**

### Host key changed

If a machine gets reinstalled or hostname changes:

```bash
ssh-keygen -R 100.93.236.6    # Mini
ssh-keygen -R 100.107.22.111  # Pro
```

### Public key not accepted

Copy your public key to the other machine:

```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub mini  # from Pro
ssh-copy-id -i ~/.ssh/id_ed25519.pub pro   # from Mini
```

## Automatic Git Sync (updated 2026-05-25)

Both machines work on `main` directly. Sync is fully automatic via husky post-commit hooks — zero manual intervention required.

### Topology

```
Pro (nuzantara)          Mini (nuzantara)
────────────────         ──────────────────────
git remote: mini ─────→  (bare receive via SSH)
git remote: origin       git remote: pro ──────→ Pro
                         git remote: origin
```

### Pro commits → Mini syncs automatically

`.husky/post-commit` on Pro:

```bash
# After any commit on main, Mini pulls from Pro
ssh mini "cd ~/nuzantara && git stash -q; git pull pro main --ff-only; git stash pop -q || true"
```

### Mini commits → Pro syncs automatically

`.husky/post-commit` on Mini:

```bash
# After any commit on main, push to Pro
git push pro main
```

Pro accepts pushes via `receive.denyCurrentBranch=updateInstead`.

### Manual sync (if needed)

```bash
# From Pro — pull what Mini pushed
git fetch mini && git merge mini/main --ff-only

# From Mini — pull what Pro committed
git pull pro main --ff-only
```

### Log

Both machines log sync activity to `~/.openclaw/logs/git-sync.log`.

### Working tree conflicts

Mini's `.husky/post-commit` uses `git stash/pop` automatically around the pull. If Mini has uncommitted changes, they are stashed, the pull happens, then unstashed. If Pro has uncommitted changes when Mini pushes, the push will be rejected — stash first: `git stash && git push mini main:main`.

## Architecture

- **Pro (48GB):** Active development, Claude Code, heavy tasks, GitHub push, Server H24
- **Mini (24GB):** Server H24, Ollama dedicated, heavy cron jobs
