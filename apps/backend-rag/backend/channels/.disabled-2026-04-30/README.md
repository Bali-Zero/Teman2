# Disabled channels (2026-04-30)

These channel scaffolds are quarantined from active routing for the reasons
below. They are kept under `.disabled-2026-04-30/` for audit so the original
code is preserved if reactivation is ever desired.

## twitter

- **Status:** CRC broken (X webhook handshake fails)
- **Reference:** `CLAUDE.md` §10 Channels table — "❌ CRC broken"
- **Reactivation criteria:** fix the X/Twitter webhook CRC validation
  handshake; verify locally with ngrok before re-enabling.

## gchat (Google Chat)

- **Status:** scaffold only, never wired to a real bot.
- **Reference:** `CLAUDE.md` §10 Channels table — "🔧 Scaffold"
- **Reactivation criteria:** provision Google Chat bot, wire OAuth.
- **Note:** no scaffold files were ever committed under
  `backend/channels/gchat/` at the time of quarantine — the entry exists
  only in the channel taxonomy table.

## slack

- **Status:** scaffold only, never wired to a real workspace.
- **Reference:** `CLAUDE.md` §10 Channels table — "🔧 Scaffold"
- **Reactivation criteria:** create Slack app, wire OAuth.
- **Note:** no scaffold files were ever committed under
  `backend/channels/slack/` at the time of quarantine — the entry exists
  only in the channel taxonomy table.

## Innervation scope

These organs are NOT enrolled in the Innervation Genoma registry
(`apps/organism/organism/organs_registry.yaml`, renamed 2026-05-08 IG-3
from `genome.yaml`) because they are not running in production.
Re-evaluate enrollment when reactivated.

## Files moved here

- `twitter/` — full channel package (adapter, config, formatter, __init__)
- `test_twitter_adapter.py` — unit tests, also disabled (imports now
  resolve to `.disabled-2026-04-30.twitter.*`, so the file is moved to
  prevent stale test collection from `backend/tests/unit/channels/`)
