# wave3-team-pro — Sessione Pro Wave 3 (P0-6 Channels ack-first)

> Single-file prompt for Claude Code Max x20 (Opus 4.7 max effort) on **Pro**.
> Comando: `leggi wave3-team-pro e esegui`

---

## Mission

Sei l'orchestrator di un agent dedicato a **P0-6: Channels webhook ack-first + Twitter CRC restoration**. Singolo agent, single fix, ma è il fix più grande di Wave 3 (2-3 giorni effort).

**Sessione 1 (mia, qua)** sta gestendo P0-2 fase 2 e P0-5 fase 2 in parallelo nel team `wave3-mio`.

## Context (READ FIRST)

1. `docs/audits/2026-04-29-zero-crash-audit/11_brainstorms/P0-6_channels_ack_first.md` — brainstorm dedicato
2. `docs/audits/2026-04-29-zero-crash-audit/09_intervention_plan.md` section P0-6
3. **Outbox infra disponibile in main da Wave 2** (commit #342, #343, #352): `apps/backend-rag/backend/services/events/outbox.py`. Usa `outbox.publish()` per `inbound_webhook_queued` channel.
4. `apps/backend-rag/backend/channels/` — current router structure (whatsapp, telegram, instagram, twitter, web)
5. Cicatrix: Twitter CRC broken hardcoded in `logging_config.py` since 2026-04-03
6. Memory pattern `2026-04-29 — Antonello NON è dev`: gli agent NON chiedono shell command ad Antonello, fallback ssh-pro o autonomo.

## Files to touch (~10)

1. `apps/backend-rag/backend/db/migrations_v2/145_inbound_webhooks.sql` (NEW migration)
2. `apps/backend-rag/backend/services/channels/webhook_processor.py` (NEW background worker)
3. `apps/backend-rag/backend/channels/whatsapp/webhook_router.py` (modify — ack-first)
4. `apps/backend-rag/backend/channels/instagram/webhook_router.py` (modify)
5. `apps/backend-rag/backend/channels/telegram/webhook_router.py` (modify)
6. `apps/backend-rag/backend/channels/twitter/webhook_router.py` (modify — CRC restoration + ack-first)
7. `apps/backend-rag/backend/channels/logging_config.py` (modify — re-enable twitter)
8. `apps/cell/cell/sensors/channel_sensor.py` (NEW Cell sensor)
9. `apps/backend-rag/backend/tests/services/channels/test_webhook_processor.py` (NEW)
10. `apps/backend-rag/backend/tests/channels/test_*_ack_first.py` (NEW per channel)

## Off-limits

- `apps/backend-rag/backend/prompts/zantara_core.py`
- `apps/backend-rag/fly.toml`
- `.env*`
- `apps/backend-rag/backend/services/events/outbox.py` (è già in main da Wave 2 — usalo, non modificarlo)

## Workflow

### Phase 1 — Cross-LLM brainstorm

```bash
cd /Users/nuzantara/Desktop/nuzantara
source docs/audits/2026-04-29-zero-crash-audit/prompts/wave1/_coordination.sh

cat > /tmp/wave3-pro-brief.txt <<'BRIEF'
PROBLEM: Webhook router (whatsapp, telegram, instagram, twitter) currently process synchronously. If processing > 3s, Meta/Twitter auto-disable webhook after 3 failures in 5 min. Twitter X CRC handshake broken since 2026-04-03 (hardcoded disabled in logging_config.py).

ALSO: on Fly machine crash mid-processing, in-flight webhook is lost — no ack to external = external retry storm = duplicates.

OUTBOX INFRA AVAILABLE: services/events/outbox.py is in main since Wave 2 (PR #342). Provides publish/acknowledge/replay_unconsumed.

TASK: 
1. New migration table inbound_webhooks (id, channel, payload, received_at, processed_at, error_message, attempts, next_retry_at)
2. Each webhook router: persist payload + outbox.publish('inbound_webhook_queued', {...}) → return 200 OK in <200ms
3. Background worker webhook_processor.py: LISTEN on inbound_webhook_queued OR poll inbound_webhooks every 5s, process pending, mark consumed
4. Twitter CRC: rewrite GET /webhook/twitter handshake per HMAC SHA-256 spec
5. Channel sensor for Cell PulseLoop: report inbound queue depth per channel
6. Re-enable twitter.webhook_router in logging_config.py (was disabled 2026-04-03)

CONSTRAINTS:
- Webhook ack must be <200ms guaranteed
- Idempotency: same payload arriving twice → processed once (use Meta-provided message_id as dedup key)
- Retry policy: 5 attempts with exponential backoff (5min × attempt)
- Don't change OAuth or Meta verification logic
- TELEGRAM_BOT_TOKEN is already configured in env (don't hardcode)

Output: per file, conceptual diff + test plan + edge case enumeration.
BRIEF

mkdir -p /tmp/wave3-pro-brainstorms
coord_brainstorm "P0-6 Channels ack-first + Twitter CRC" /tmp/wave3-pro-brief.txt /tmp/wave3-pro-brainstorms

for llm in codex gemini deepseek notebooklm; do
    echo "=== $llm ==="; head -150 /tmp/wave3-pro-brainstorms/$llm.md
    echo ""
done
```

NB: Wave 2 ha esaurito quote di alcuni LLM (Codex usage limit, Gemini 429, NotebookLM CLI). Se più di 1 LLM fallisce, fall back su `11_brainstorms/P0-6_channels_ack_first.md` esistente.

### Phase 2 — Worktree

```bash
cd /Users/nuzantara/Desktop/nuzantara
git fetch origin
git worktree add -b feat/p0-6-channels-ack-first ../nuzantara-wt/p0-6 origin/main
cd ../nuzantara-wt/p0-6
ln -sf /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv apps/backend-rag/.venv
```

### Phase 3 — TDD (tests first per categoria)

```python
# apps/backend-rag/backend/tests/services/channels/test_webhook_processor.py
@pytest.mark.asyncio
async def test_processor_drains_pending(): pass
@pytest.mark.asyncio
async def test_processor_retries_with_backoff(): pass
@pytest.mark.asyncio
async def test_processor_marks_terminal_after_5_attempts(): pass
@pytest.mark.asyncio
async def test_processor_idempotent_on_replay(): pass

# apps/backend-rag/backend/tests/channels/test_whatsapp_ack_first.py
@pytest.mark.asyncio
async def test_whatsapp_acks_in_under_200ms(): pass
@pytest.mark.asyncio
async def test_whatsapp_persists_payload_to_inbound_webhooks(): pass

# Same for telegram, instagram, twitter
# Plus twitter CRC specific
def test_twitter_crc_returns_signed_response(): pass
def test_twitter_crc_uses_consumer_secret_from_env(): pass
```

CWD CRITICAL — pytest from `apps/backend-rag/`:
```bash
cd /Users/nuzantara/Desktop/nuzantara-wt/p0-6/apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/channels/ backend/tests/channels/ -v
```

### Phase 4 — Migration 145

```sql
-- apps/backend-rag/backend/db/migrations_v2/145_inbound_webhooks.sql

CREATE TABLE inbound_webhooks (
    id BIGSERIAL PRIMARY KEY,
    channel TEXT NOT NULL,
    payload JSONB NOT NULL,
    dedup_key TEXT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ NULL,
    error_message TEXT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    next_retry_at TIMESTAMPTZ NULL,
    UNIQUE(channel, dedup_key)
);
CREATE INDEX inbound_webhooks_pending ON inbound_webhooks (channel, received_at)
    WHERE processed_at IS NULL AND (next_retry_at IS NULL OR next_retry_at < NOW());
CREATE INDEX inbound_webhooks_received ON inbound_webhooks (received_at DESC);

-- === ROLLBACK ===
DROP INDEX IF EXISTS inbound_webhooks_pending;
DROP INDEX IF EXISTS inbound_webhooks_received;
DROP TABLE IF EXISTS inbound_webhooks;
```

NB: Squawk ti dirà di aggiungere `set lock_timeout` etc — usa `-- squawk-ignore-all` come Wave 1 canary.

### Phase 5 — Implementation per file

Per ogni router, pattern:
```python
@router.post("/webhook/X")
async def x_webhook(payload: dict, request: Request, db_pool=Depends(get_database_pool)):
    # 1. Verify signature (synchronous, fast)
    if not verify_X_signature(request): raise HTTPException(401)
    
    # 2. Compute dedup key (Meta provides message_id)
    dedup_key = payload.get('messages', [{}])[0].get('id', f'fallback-{time.time()}')
    
    # 3. Persist + notify (atomic)
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO inbound_webhooks (channel, payload, dedup_key)
                   VALUES ($1, $2::jsonb, $3)
                   ON CONFLICT (channel, dedup_key) DO NOTHING""",
                'X', json.dumps(payload), dedup_key
            )
            await outbox.publish(conn, 'inbound_webhook_queued', {'channel': 'X', 'dedup_key': dedup_key})
    
    return {"status": "queued"}  # < 200ms
```

Background processor: LISTEN on `inbound_webhook_queued`, poll fallback every 5s.

Twitter CRC:
```python
import hmac, hashlib, base64, os

@router.get("/webhook/twitter")
async def twitter_crc(crc_token: str) -> dict:
    secret = os.getenv("TWITTER_CONSUMER_SECRET")
    if not secret:
        raise HTTPException(500, "TWITTER_CONSUMER_SECRET not configured")
    signature = hmac.new(secret.encode(), crc_token.encode(), hashlib.sha256).digest()
    return {"response_token": "sha256=" + base64.b64encode(signature).decode()}
```

### Phase 6 — Local end-to-end

```bash
cd /Users/nuzantara/Desktop/nuzantara-wt/p0-6/apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. uvicorn backend.app.main_api:app --port 8001 &
sleep 5

# Synthetic load whatsapp
ab -n 100 -c 10 -p tests/fixtures/whatsapp_payload.json -T application/json \
   -H "X-Hub-Signature-256: sha256=..." \
   http://localhost:8001/webhook/whatsapp
# Expected: 100/100 200 OK, p99 <200ms

# Twitter CRC
TOKEN=$(openssl rand -hex 16)
curl -s "http://localhost:8001/webhook/twitter?crc_token=$TOKEN" | jq
# Expected: {"response_token": "sha256=..."}

kill %1
```

### Phase 7 — Self-review

```bash
cd /Users/nuzantara/Desktop/nuzantara-wt/p0-6
git diff origin/main 2>&1 | head -300
```

Verify:
- No off-limits files
- Migration 145 has rollback section
- All tests cover happy + idempotent + retry paths
- No hardcoded secrets

### Phase 8 — Commit + PR

```bash
source /Users/nuzantara/Desktop/nuzantara/docs/audits/2026-04-29-zero-crash-audit/prompts/wave1/_coordination.sh

cd /Users/nuzantara/Desktop/nuzantara-wt/p0-6

git add apps/backend-rag/backend/db/migrations_v2/145_inbound_webhooks.sql
git add apps/backend-rag/backend/services/channels/webhook_processor.py
git add apps/backend-rag/backend/channels/
git add apps/cell/cell/sensors/channel_sensor.py 2>/dev/null
git add apps/backend-rag/backend/tests/

coord_commit "feat(p0-6): channels webhook ack-first + Twitter CRC restoration

P0-6 from zero-crash audit 2026-04-29 (Track C / Wave 3).
Uses Outbox infra from P0-2 fase 1 (commit 0062090c4 in main since 09:42).

- Migration 145 inbound_webhooks (channel, payload, dedup_key, retry state)
- services/channels/webhook_processor.py: LISTEN-based async processor
- Whatsapp/Instagram/Telegram/Twitter routers refactored to ack-first
  (return 200 OK in <200ms, processing async)
- Twitter CRC handshake restored (HMAC SHA-256 per spec)
- Twitter re-enabled in channels/logging_config.py
- Cell ChannelSensor for inbound queue depth observability
- ~12 new tests (4 processor + 4 router ack-first + 2 Twitter CRC + 2 idempotency)

Cicatrix: Twitter CRC broken (2026-04-03) → resolved.
Cicatrix: webhook synchronous processing race → resolved (ack-first guarantees <200ms)."

coord_push origin feat/p0-6-channels-ack-first

gh pr create --title "feat(p0-6): channels webhook ack-first + Twitter CRC" \
  --body "Track C / Wave 3.

## Summary
- Migration 145 inbound_webhooks
- All 4 channel webhook routers refactored to ack-first pattern
- Twitter CRC restored (HMAC SHA-256)
- Channel sensor for Cell

## Test plan
- [x] 12+ unit tests pass
- [x] Local synthetic load: 100/100 200 OK, p99 <200ms
- [x] Twitter CRC manual test
- [ ] Post-deploy: external Meta webhook send/receive
- [ ] Twitter API webhook re-registration (manual followup with Antonello)

🤖 Generated with [Claude Code](https://claude.com/claude-code)"

gh pr merge --auto --squash
```

### Phase 9 — Watch CI + deploy

```bash
PR=$(gh pr view --json number -q .number)
gh pr checks $PR --watch 2>&1 | tail -20
sleep 30
gh run watch $(gh run list --workflow="Deploy Backend to Fly.io" --limit 1 --json databaseId -q '.[0].databaseId') 2>&1 | tail -30
```

### Phase 10 — Verify deploy

```bash
# Production health
for i in 1 2 3; do
    code=$(curl -s -o /dev/null -w "%{http_code}" https://nuzantara-rag.fly.dev/health)
    echo "health $i: $code"
done

# Migration applied
fly ssh console -a nuzantara-rag --machine d894e65bede478 -C "/bin/sh -c 'cd /app && python -c \"
import asyncio, asyncpg, os
async def chk():
    conn = await asyncpg.connect(os.environ[\\\"DATABASE_URL\\\"])
    rows = await conn.fetch(\\\"SELECT migration_number FROM _schema_versions WHERE migration_number = 145\\\")
    print(rows)
    await conn.close()
asyncio.run(chk())
\"'"
# Expected: row with 145

# Synthetic webhook test (against prod)
TIME=$(curl -s -w "%{time_total}" -o /dev/null https://nuzantara-rag.fly.dev/webhook/health)
echo "webhook response time: ${TIME}s"
# Expected: <0.2 (200ms)
```

### Phase 11 — MOS save + cleanup

```bash
PR=$(gh pr view --json number -q .number)
~/.claude/scripts/mem save decision "P0-6 Channels ack-first + Twitter CRC merged PR #$PR. All webhook routers now ack-first <200ms via Outbox infra. Migration 145 inbound_webhooks. Twitter CRC HMAC SHA-256 restored. Channel sensor for Cell. Wave 3 closed P0-6 (1 of 3)." 9

cd /Users/nuzantara/Desktop/nuzantara
git worktree remove ../nuzantara-wt/p0-6 2>&1 | tail -3
```

## Failure modes

- **Brainstorm partial fail**: continue with available LLMs + brainstorm doc fallback
- **Migration 145 Squawk fail**: aggiungi `-- squawk-ignore-all` per BIGSERIAL etc (canary pattern)
- **CI cwd bug** (lesson da Wave 2 #343): TDD verify ALWAYS `cd apps/backend-rag && pytest`. Mai dal worktree root.
- **CI red su Backend Tests advisory**: ignora se required green (lesson Wave 2)
- **Twitter API webhook re-registration**: questo è manual (need TWITTER_CONSUMER_SECRET in Fly secrets, plus webhook URL POST to Twitter dev portal). Lascia comment in PR per Antonello followup, NON blocca merge.
- **Coord lock stuck**: standard recovery

## L2 autonomy

Yes. Ask before:
- Off-limits file edited
- Twitter webhook re-registration on dev portal (manual)
- Production smoke test that sends real Meta/Twitter messages (use mock or staging)

## Reporting

```
[wave3-team-pro DONE]
- P0-6 Channels ack-first + Twitter CRC merged PR #<num>
- Migration 145 applied in production
- ~12 tests pass
- Local smoke: 100/100 200 OK, p99 <200ms
- Cicatrix Twitter CRC broken resolved
- Twitter API webhook re-registration: deferred to Antonello manual
- Brainstorms in /tmp/wave3-pro-brainstorms
```

Begin now. Phase 1 first.
