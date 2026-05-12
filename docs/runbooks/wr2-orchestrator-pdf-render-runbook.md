# WR2 Orchestrator PDF Render — Production Runbook

## Initial deployment (one-time)

### 1. Generate HMAC key

```bash
echo "WR2_CANVA_HMAC_KEY=$(openssl rand -hex 32)" >> ~/.nuzantara-secrets.env
echo "WR2_CANVA_TOKEN_FILE=$HOME/.config/wr2/canva_tokens.json" >> ~/.nuzantara-secrets.env
echo "WR2_DRAFTS_FOLDER_ID=<your-canva-folder-id>" >> ~/.nuzantara-secrets.env
mkdir -p ~/.config/wr2 && chmod 700 ~/.config/wr2
```

### 2. Apply DB migration

```bash
# Run via flycast tunnel (PG proxy must be running):
psql -h 127.0.0.1 -p 15432 -U postgres -d nuzantara_rag \
  -f apps/backend-rag/backend/db/migrations_v2/169_wr2_draft_lease.sql
```

### 3. Apply Tigris S3 lifecycle

```bash
source ~/.nuzantara-secrets.env
aws s3api put-bucket-lifecycle-configuration \
  --bucket nuzantara-warroom-images \
  --lifecycle-configuration file://infra/tigris/wr2-pdf-lifecycle.json \
  --endpoint-url https://fly.storage.tigris.dev
```

### 4. Bootstrap Canva OAuth

```bash
source ~/.nuzantara-secrets.env
cd ~/Desktop/nuzantara
apps/backend-rag/.venv/bin/python scripts/wr2_bootstrap_canva_oauth.py
# Browser opens. Authorize Bali Zero team. Wait "✅ Bootstrap complete".
ls -la ~/.config/wr2/canva_tokens.json  # mode 0600
```

### 5. Install plists

```bash
cp infra/launchagents/com.balizero.wr2.canva-renderer.plist ~/Library/LaunchAgents/
cp infra/launchagents/com.balizero.wr2.canva-token-watchdog.daily.plist ~/Library/LaunchAgents/
cp infra/launchagents/com.balizero.wr2.canva-lease-watchdog.10min.plist ~/Library/LaunchAgents/
```

### 6. Flip PG kill switch + bootstrap plists

```bash
psql -h 127.0.0.1 -p 15432 -U postgres -d nuzantara_rag \
  -c "UPDATE system_settings SET value='true' WHERE key='wr2_canva_renderer_enabled'"

launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2.canva-renderer.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2.canva-token-watchdog.daily.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2.canva-lease-watchdog.10min.plist
```

### 7. Monitor first 2-3 ticks

```bash
tail -F ~/logs/wr2_canva_pdf_apply.log

psql -h 127.0.0.1 -p 15432 -U postgres -d nuzantara_rag \
  -c "SELECT id, status, canva_edit_url FROM war_room_drafts
      WHERE updated_at > NOW() - INTERVAL '15 minutes'
      ORDER BY updated_at DESC LIMIT 10"
```

## End-to-end smoke (after deployment)

```bash
# 1. Insert synthetic draft
python scripts/wr2_e2e_create_fixture_draft.py

# 2. Wait <=5 minutes for the next cron tick.

# 3. Verify
psql -c "SELECT status, canva_edit_url FROM war_room_drafts
         WHERE id = '00000000-0000-0000-e2e0-000000000001'"
# Expected: status='rendered', canva_edit_url populated.
```

## Rollback

```bash
launchctl bootout gui/$(id -u)/com.balizero.wr2.canva-renderer
psql -c "UPDATE system_settings SET value='false' WHERE key='wr2_canva_renderer_enabled'"
```

## Diagnostics

| Symptom | Check | Fix |
|---|---|---|
| "Exit 4" in log | `ls ~/.config/wr2/canva_tokens.json` | Bootstrap step 4 |
| "Exit 5" in log | Telegram says "refresh revoked" | Re-bootstrap step 4 |
| "Exit 7" in log | HMAC corruption | Backup at `.broken-*.json`, re-bootstrap |
| Drafts stuck `rendering` | Lease watchdog 10min interval | Should self-heal in ≤25min |
| Canva 429 spam | Tigris/MCP rate | Reduce MAX_DRAFTS_PER_RUN |

## Refresh-token expiry handling

Canva refresh tokens decay ~90 days. Telegram alerts at 75d (warn) and
85d (critical). Re-bootstrap:

```bash
rm ~/.config/wr2/canva_tokens.json
apps/backend-rag/.venv/bin/python scripts/wr2_bootstrap_canva_oauth.py
```
