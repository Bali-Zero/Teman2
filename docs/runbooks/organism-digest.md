# Organism digest — the session-boot "what changed" receptor

**Born**: 2026-07-06, from Zero's mandate: Telegram alerts go unread ("NON LE LEGGO");
compact reports must reach the channel that is actually read daily — the Claude Code
session itself.

## What it is

`scripts/organism_digest.py` renders a ≤15-line digest of the organism's last 24h at
every session boot, via `scripts/hooks/organism_digest_sessionstart.sh` (registered in
`.claude/settings.json` → SessionStart, third sibling of the escalations and
proprioception receptors).

**It migrates no producers.** The ~206 Telegram-sending surfaces keep working; this is a
READER over state that already exists on disk:

| Source | What surfaces |
|---|---|
| `research/regulatory/*-delta.json` (mtime in window) | new regulations: severity, citation, service line — deduped by citation |
| `~/.organism/arsenal/last.json` | AI seats not LIVE (from `arsenal_probe.py`) |
| `~/.organism/last_seen/*.json` | organs silent >26h, or fresh-but-degraded |
| `PENDING-ARMS.md` via `pending_arms_report.py --json` | overdue TECH-DEBT armings count |
| `git log origin/main --first-parent` (no fetch) | what landed on main in the window |

## Contract

- **Anti-calm-liar**: never silent. All-quiet = one-line heartbeat. Broken source = a
  visible `⚠️ receptor:` line, never a swallowed exception.
- **Read-only at boot**: no cursor files, no writes — sibling sessions cannot race.
- **Budget**: SIGALRM 6s inside the script; hook always exits 0 (never blocks boot).
- Kill switch: `ORGANISM_DIGEST_ENABLED=false`.

## Usage

```bash
python3 scripts/organism_digest.py             # compact digest, last 24h
python3 scripts/organism_digest.py --hours 48
python3 scripts/organism_digest.py --json      # machine form
python3 scripts/organism_digest.py --selftest  # guilt+innocence fixtures (10 checks)
```

## Notification-economy doctrine (v1)

1. **Feed the system first**: producers write state to disk/DB (delta JSON, heartbeats,
   ledger). Chat pings are a VIEW, never the store.
2. **Right channel by consumption reality**: session boot (this digest) = daily read
   guaranteed; Telegram = P0-only (rare, loud); weekly rollups for FYI-class events.
3. Telegram sends stay as belt-and-braces but nothing may exist ONLY as a Telegram
   message — if it matters, it must be readable from disk state (this is what makes the
   digest possible without migrating 206 senders).

## Fleet arming

Repo-side registration means the hook arms on each machine at its next `git pull` of the
main checkout + new session. No plists, no HOME copies.
