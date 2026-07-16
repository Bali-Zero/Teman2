# Runbook — WhatsApp media PULL worker (Anello 1, sovereign-local)

> **What this is**: the Pro-side worker that pulls WhatsApp document attachments
> sent to the official BALI ZERO line into the LOCAL intake queue, **without any
> client PII ever touching Fly** (SYMBIOSIS Law 2 / UU PDP).

## Architecture (PULL — why it's built this way)

```
WhatsApp doc → Meta → Fly webhook (/webhook/whatsapp)
                         │  publishes METADATA ONLY (media_id + provenance)
                         ▼
              events_outbox(channel=whatsapp_media_pending)   ← on Fly, NO PII bytes
                         │  GET /api/bridge/wa-media/pending   (X-Bridge-Auth)
                         ▼
       Pro worker  scripts/wa_media_pull_worker.py            ← runs ONLY on the Pro
                         │  downloads the file FROM META ITSELF (token from Keychain)
                         ▼
       local blob  ~/.nuzantara/intake-blobs/                 ← PII lives here, Pro only
                         │  enqueue() → LOCAL nuzantara_dev intake_queue
                         ▼
                  POST /api/bridge/wa-media/ack  (only after local enqueue OK)
```

The Fly box **never downloads** the document. It only hands off a `media_id`.
The Pro pulls because the Pro is often offline and cannot be pushed to on demand.

**Accepted risk**: Meta `media_id`s expire (~days). If the Pro stays off too long
a file becomes un-downloadable. Mitigated by the worker's staleness Telegram
alert (`WA_MEDIA_STALE_HOURS`, default 36h) + the 5-minute cron cadence.

## One-time operator setup (on the Pro)

### 1. Store the WhatsApp access token in the Pro Keychain

The worker reads the token from the macOS Keychain — **never** from an env var,
plist, or file on disk (defense against the 2026-04-29 plist-secret-644 scar).

```bash
# On the Pro (user nuzantara). Paste the Meta WhatsApp permanent access token.
# (same token the send-path uses — WHATSAPP_ACCESS_TOKEN / WHATSAPP_API_TOKEN)
security add-generic-password -s balizero-whatsapp -a access-token -w '<PASTE_TOKEN_HERE>'
```

To **rotate** later, delete then re-add:

```bash
security delete-generic-password -s balizero-whatsapp -a access-token
security add-generic-password   -s balizero-whatsapp -a access-token -w '<NEW_TOKEN>'
```

### 2. Store the bridge API key in the Pro Keychain

`BRIDGE_API_KEY` is the shared secret for `GET/POST /api/bridge/*` (same value as
the Fly secret `BRIDGE_API_KEY`). The worker reads it from `BRIDGE_API_KEY` env
**if set**, otherwise from the Keychain — so no secret needs to live in the plist.

```bash
# Use the SAME value as: fly secrets list -a nuzantara-rag | grep BRIDGE_API_KEY
security add-generic-password -s balizero-whatsapp -a bridge-api-key -w '<BRIDGE_API_KEY>'
```

> Verify a stored item without printing it elsewhere: `security find-generic-password -s balizero-whatsapp -a access-token -w | wc -c` (prints the length, not the value).

### 3. Install the LaunchAgent

```bash
mkdir -p ~/logs
cp ~/nuzantara/infra/launchagents/com.nuzantara.wa-media-pull.plist \
   ~/Library/LaunchAgents/
chmod 0644 ~/Library/LaunchAgents/com.nuzantara.wa-media-pull.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.wa-media-pull.plist
launchctl enable gui/$(id -u)/com.nuzantara.wa-media-pull
```

(If a previous version is loaded: `launchctl bootout gui/$(id -u)/com.nuzantara.wa-media-pull` first.)

## Verify it's working

```bash
# Run one tick manually (uses the same Keychain + env the cron uses):
~/nuzantara/apps/backend-rag/.venv/bin/python -u \
  ~/nuzantara/scripts/wa_media_pull_worker.py

# Tail the cron log:
tail -f ~/logs/wa-media-pull.log
```

Healthy lines look like:

```
[wa_media_pull] no pending media (since=0)
# or, after a real doc arrives:
[wa_media_pull] done: pending=1 new=1 dl_err=0 acked=1 since=4242
```

Abort lines (fix and re-run):

- `BRIDGE_API_KEY not in env or Keychain, aborting` → redo setup step 2.
- `no access token in Keychain, aborting` → redo setup step 1.
- `auth failed (401)` → the Keychain `bridge-api-key` ≠ the Fly `BRIDGE_API_KEY`.

## The fire test (end-to-end, real)

1. Confirm setup steps 1–3 done; worker tick prints `no pending media`.
2. From any phone, send a **document** (PDF/image) to the official number
   **+62 821-3465-159** (Meta-verified BALI ZERO line, `phone_number_id=1104946272705747`).
3. Within ~5 min (or run a manual tick) the log shows `pending=1 ... acked=1`.
4. Verify the blob is on the **Pro only** and a row landed in the **local** queue:

   ```bash
   ls -la ~/.nuzantara/intake-blobs/        # the downloaded file is here
   ~/nuzantara/apps/backend-rag/.venv/bin/python -c "
   import asyncio, asyncpg
   async def m():
       c=await asyncpg.connect('postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev')
       r=await c.fetch(\"SELECT id, source, source_ref, status, received_by FROM intake_queue WHERE source='whatsapp' ORDER BY id DESC LIMIT 3\")
       print([dict(x) for x in r]); await c.close()
   asyncio.run(m())"
   ```

5. Confirm **nothing was persisted on Fly**: the `events_outbox` row should be
   `consumed_at` non-NULL (acked), and no blob exists on the Fly container.

## Config reference (env vars; all optional except the Keychain secrets)

| Var                                             | Default                                               | Notes                                  |
| ----------------------------------------------- | ----------------------------------------------------- | -------------------------------------- |
| `FLY_BRIDGE_URL`                                | `https://nuzantara-rag.fly.dev`                       | Fly bridge base URL                    |
| `BRIDGE_API_KEY`                                | (Keychain `bridge-api-key`)                           | env wins; else Keychain                |
| `LOCAL_DATABASE_URL`                            | `postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev` | LOCAL DB only                          |
| `INTAKE_BLOB_ROOT`                              | `~/.nuzantara/intake-blobs`                           | sovereign local blob store             |
| `WA_MEDIA_KEYCHAIN_SERVICE`                     | `balizero-whatsapp`                                   | Keychain service name                  |
| `WA_MEDIA_KEYCHAIN_ACCOUNT`                     | `access-token`                                        | Keychain account for the token         |
| `WA_MEDIA_API_VERSION`                          | `v18.0`                                               | Meta Graph API version                 |
| `WA_MEDIA_STALE_HOURS`                          | `36`                                                  | Telegram alert if oldest pending older |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_OWNER_CHAT_ID` | unset / `1125336968`                                  | staleness alerts                       |

## Notes / boundaries

- `received_by` is `None` in v1 (one shared official line → no per-person
  receiver). This is the single seam to change when a real ownership policy is
  chosen. See memory `decision-intake-anello1-wired-2026-06-06`.
- This worker only gets documents INTO the local intake_queue. OCR / classify /
  routing / CRM writes are the existing intake worker + FASE 5C (separate, and
  `INTAKE_WRITER_ENABLED` stays OFF until that's wired).
- The Fly side (Piece A+B) auto-deploys on merge to main; this worker is the
  only piece the operator must install by hand.
