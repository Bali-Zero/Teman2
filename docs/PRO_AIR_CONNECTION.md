# Pro <-> Air Connection Guide

**Last Updated:** 2026-03-13

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

## nz-connect — One-Command Sync

`nz-connect` is a bilateral sync script that works from either machine. It detects which machine it's running on, checks SSH to the peer, and synchronizes git repos automatically.

```bash
# From either machine — just run:
nz-connect
```

**What it does:**

1. Identifies Pro or Air automatically
2. Verifies SSH peer is reachable (mDNS)
3. Compares local, peer, and origin commit hashes
4. Pushes/pulls as needed (with auto-stash if dirty)
5. Auto-resolves data file conflicts (`bali-intel-scraper/data/`, `published_articles.json`) using `--theirs`
6. Reports final sync status with colors

**Setup:** The alias is in both `.zshrc` files, pointing to `scripts/nz-connect.sh` in the repo.

| Machine | Repo path                                    | Alias        |
| ------- | -------------------------------------------- | ------------ |
| Pro     | `~/Desktop/nuzantara/scripts/nz-connect.sh`  | `nz-connect` |
| Air     | `~/Projects/nuzantara/scripts/nz-connect.sh` | `nz-connect` |

**Backward compat:** `nz-sync` on Air maps to `nz-connect`.

> **Important:** All SSH aliases now use mDNS hostnames from `~/.ssh/config` (`ssh pro`, `ssh air`). No hardcoded IPs. If DHCP changes the IP, everything still works.

## Syncthing

Bidirectional sync is configured between the machines:

- **Pro:** `~/Desktop/nuzantara` → **Air:** `~/Desktop/projects/nuzantara`
- Syncs: `~/.claude/`, `~/.config/`
- Excludes: `node_modules`, `build`, `cache`, `logs` (via `.stignore`)
- Code changes: via **Git push/pull**, NOT Syncthing

## Architecture

- **Pro (48GB):** Active development, Claude Code, heavy tasks
- **Air (16GB):** Server H24 — Ollama, Qdrant, PostgreSQL, Backend RAG, OpenClaw gateway, Telegram bot
