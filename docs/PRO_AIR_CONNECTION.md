# Pro <-> Air Connection Guide

**Last Updated:** 2026-03-28

## Machines

| Machine | Hostname    | mDNS                | User             | Hardware                |
| ------- | ----------- | ------------------- | ---------------- | ----------------------- |
| **Pro** | Nuzantara   | `Nuzantara.local`   | `nuzantara`      | MacBook Pro M4 Pro 48GB |
| **Air** | Nuzantara-9 | `Nuzantara-9.local` | `antonellosiano` | MacBook Air M4 16GB     |

## SSH Connection

SSH uses **mDNS** (Bonjour) hostnames instead of static IPs. This means connections work regardless of which WiFi network you're on or what IP the DHCP assigns.

```bash
# From Pro → Air
ssh air

# From Air → Pro
ssh pro
```

### SSH Config (both machines)

**Pro** (`~/.ssh/config`):

```
Host air
    HostName Nuzantara-9.local
    User antonellosiano
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

**Air** (`~/.ssh/config`):

```
Include /Users/antonellosiano/.colima/ssh_config

Host pro
    HostName Nuzantara.local
    User nuzantara
    IdentityFile ~/.ssh/id_ed25519
    AddKeysToAgent yes
    UseKeychain yes
    ServerAliveInterval 60
    ServerAliveCountMax 10

Host air
    HostName Nuzantara-9.local
    User antonellosiano
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
ping -c 1 Nuzantara.local && echo "Pro: OK" || echo "Pro: UNREACHABLE"
ping -c 1 Nuzantara-9.local && echo "Air: OK" || echo "Air: UNREACHABLE"

# Full SSH check
ssh air "echo 'Air SSH: OK'" 2>/dev/null || echo "Air SSH: FAILED"
ssh pro "echo 'Pro SSH: OK'" 2>/dev/null || echo "Pro SSH: FAILED"
```

## Troubleshooting

### mDNS not resolving

Both machines must be on the **same local network** (same WiFi/router). mDNS doesn't work across different networks.

```bash
# Check if mDNS is working
dns-sd -B _ssh._tcp local.
```

### SSH connection refused

Remote Login must be enabled on the target machine:

- **System Settings → General → Sharing → Remote Login → ON**

### Host key changed

If a machine gets reinstalled or hostname changes:

```bash
ssh-keygen -R Nuzantara-9.local  # or Nuzantara.local
```

### Public key not accepted

Copy your public key to the other machine:

```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub air   # from Pro
ssh-copy-id -i ~/.ssh/id_ed25519.pub pro   # from Air
```

## Automatic Git Sync (updated 2026-03-28)

Both machines work on `main` directly. Sync is fully automatic via husky post-commit hooks — zero manual intervention required.

### Topology

```
Pro (nuzantara)          Air (antonellosiano)
────────────────         ──────────────────────
git remote: air ──────→  (bare receive via SSH)
git remote: origin       git remote: pro ──────→ Pro
                         git remote: origin
```

### Pro commits → Air syncs automatically

`.husky/post-commit` on Pro:

```bash
# After any commit on main, Air pulls from Pro
ssh air "cd ~/Projects/nuzantara && git stash -q; git pull pro main --ff-only; git stash pop -q || true"
```

### Air commits → Pro syncs automatically

`.husky/post-commit` on Air:

```bash
# After any commit on main, push to Pro
git push pro main
```

Pro accepts pushes via `receive.denyCurrentBranch=updateInstead`.

### Manual sync (if needed)

```bash
# From Pro — pull what Air pushed
git fetch air && git merge air/main --ff-only

# From Air — pull what Pro committed
git pull pro main --ff-only
```

### Log

Both machines log sync activity to `~/.openclaw/logs/git-sync.log`.

### Working tree conflicts

Air's `.husky/post-commit` uses `git stash/pop` automatically around the pull. If Air has uncommitted changes, they are stashed, the pull happens, then unstashed. If Pro has uncommitted changes when Air pushes, the push will be rejected — stash first: `git stash && git push air main:main`.

## Architecture

- **Pro (48GB):** Active development, Claude Code, heavy tasks, GitHub push
- **Air (16GB):** Server H24 — Ollama, Qdrant, PostgreSQL, Backend RAG, OpenClaw gateway, Telegram bot
