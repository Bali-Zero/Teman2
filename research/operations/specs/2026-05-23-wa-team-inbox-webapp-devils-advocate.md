## FINDINGS

### 1. CRITICAL — SSE subscriber queue blocks publish under backpressure, freezing all realtime delivery

**WHAT**: `WaSseManager.publish` does `await q.put(payload)` on bounded `asyncio.Queue(maxsize=100)`. When any subscriber’s queue is full (slow client, expensive RBAC check, network stall), `put()` blocks the entire publish loop. The publish is invoked from the asyncpg LISTEN callback (via `asyncio.create_task`), but successive publishes pile up, all blocking on the same subscriber. The event loop stalls, new notifications stop flowing, and the entire SSE fan-out dies silently.
**WHY**: The code in §4.1 explicitly uses maxsize=100 and iterates with `await q.put(payload)`. If the SSE consumer can’t drain fast enough (e.g., a browser tab gone zombie while `request.is_disconnected()` hasn’t yet detected the close), the queue fills. A single stuck subscriber freezes message delivery to _all_ other subscribers. Empirical: at 0.88 msg/s, a 15-second RBAC DB timeout on one subscriber will fill the queue (0.88\*15 ≈ 13 items), but a network hiccup can exhaust the remaining space quickly.
**FIX**: Use `q.put_nowait()` and drop the message if full (with a metric/log), or use an unbounded queue with a per-connection high-water mark that triggers unsubscription. Alternatively, fan-out by enqueuing in a separate task per subscriber with a timeout, so one slow consumer cannot stall others. Never block the publish path.

### 2. CRITICAL — Outbound jitter race: `SELECT MAX(scheduled_for)` without lock allows overlapping schedules, defeating anti-ban

**WHAT**: The send endpoint computes `scheduled_for = max(last, now) + jitter` in a read-committed transaction but does **not** lock the relevant queue rows. Two concurrent operators (or two rapid-fire sends from the same operator via double-click) both read the same `MAX(scheduled_for)`, compute overlapping jitter windows, and insert rows with `scheduled_for` potentially only 1-2 seconds apart. This breaks the mandatory 10–30 s per-account cooldown, risking WhatsApp ban.
**WHY**: The spec’s transaction (`async with db.transaction()`) does `SELECT MAX(scheduled_for) FROM wa_dashboard_outbound_queue WHERE team_member_phone=$1 AND status IN ('pending','dispatching')`. Under read committed, both transactions see the same maximum, add independent uniform jitter, and produce near-simultaneous scheduled times. No `FOR UPDATE` or advisory lock. Baileys non ufficiale; Meta ban heuristics trigger on burst sends.
**FIX**: Wrap the read in `SELECT ... FOR UPDATE` on that queue partition, or acquire a PostgreSQL advisory lock on the team_member_phone hash before computing `scheduled_for`. This serialises scheduling per account within the critical section.

### 3. HIGH — Bridge restart misses future-scheduled outbound messages; they become stuck until a new manual send triggers a notify

**WHAT**: The bridge’s `outbound_worker.ts` only processes messages via live `pg_notify('wa_outbound_queued')` listener. On restart, it does `SELECT … WHERE status='pending' AND scheduled_for > NOW()` (sic) — the description contains the wrong operator; it should be `scheduled_for <= NOW()` to pick due items. Even corrected, pending rows with `scheduled_for > NOW()` (e.g., queued with a 25 s delay) will never receive another notify after restart; no code polls for future-scheduled rows. They remain `pending` indefinitely until the next human send operation accidentally triggers a notify that nudges the bridge.
**WHY**: The spec says “bridge restart → al boot fa SELECT WHERE status='pending' per riprendere pending” but omits persistent timers for future-scheduled rows. The notify channel fires only on INSERT; it is not replayed for rows already in the table. Ergo, scheduled-for-future rows are invisible.
**FIX**: On boot, the worker must `SELECT * FROM wa_dashboard_outbound_queue WHERE status = 'pending'`. For each row: if `scheduled_for <= now()`, send immediately; if future, calculate the remaining delay and schedule a `setTimeout` just like the live notify path. Also, execute the same logic on demand if a live notify arrives (in case a row’s scheduled_for is in the past due to clock skew).

### 4. HIGH — Legacy send endpoint `/api/omnichannel/threads/{id}/messages` bypasses jitter and queue, enabling unprotected outbound

**WHAT**: The spec promises a new outbound path with anti-ban jitter and queue. However, it explicitly lists the existing endpoint `/api/omnichannel/threads/{id}/messages` (POST) as “già esiste! — intervention reply”. That endpoint writes directly to the bridge (or uses the old mechanism) without any 10-30s cooldown, idempotency key enforcement, or queue. An operator using the old UI (or any tool hitting that URL) can send bursts.
**WHY**: The risk matrix does not mention this. If left live, it undermines the entire anti-ban protection. The same operators who are onboarded to the new dashboard could accidentally or intentionally use the old API.
**FIX**: Disable the old send path in production (return 410 Gone) or redirect it to the new queued endpoint, preserving backwards compat only if needed. At minimum, wrap it with the same jitter and queue logic. Document in the risk list.

### 5. HIGH — SSE `WaSseManager.subscribe` overwrites existing connection for the same user, breaking multi-tab

**WHAT**: `subscribe` does `self.subscribers[user_email] = q`, replacing any previous queue for that user. If an operator opens a second tab, the first tab’s SSE connection silently starves — it never receives another message and only gets keepalives until it times out. The operator sees a “frozen” chat view.
**WHY**: The spec models one queue per user. Multiple browser contexts (tab, mobile, tablet) for the same operator are realistic (Sahira on tablet + desktop). The current dict keyed by user_email cannot support fan-out.
**FIX**: Change `subscribers` to `dict[str, set[asyncio.Queue]]`. `subscribe` creates a new queue, adds it to the set, and returns it. `unsubscribe` removes only that specific queue. Publish iterates all queues in the set. This gives true multi-tab support.

### 6. HIGH — `can_send_from` RBAC lacks a backing mapping table; authorization logic undefined

**WHAT**: The send endpoint relies on `can_send_from(db, user, payload.team_member_phone)`, but no table exists that maps user emails to authorised team phone numbers. The spec mentions “team_member_email table” implicitly but never defines it in the schema, migrations, or risk section. Without it, `can_send_from` can’t be implemented, leaving a gap where any authenticated user might send from any account.
**WHY**: The RBAC section says “verifica che user sia mapped a quel numero team, da `team_member_email` table”, but that table is absent from §6 schema, not referenced in §1.2 existing tables, and not in the 192 migration. This is a missing dependency that breaks the security model.
**FIX**: Add a `team_member_phone_authorizations` table (user_email, team_member_phone, granted_at). Implement `can_send_from` as a JOIN. Include in migration 192.

### 7. MEDIUM — No `dispatching` state transition before outbound send; crash during send causes duplicate message

**WHAT**: The bridge worker’s send flow directly does `sock.sendMessage()` and then `UPDATE status='dispatched'`. If the crash happens after the Baileys call succeeds but before the UPDATE, the row remains `pending`. On restart, the worker will re-claim and re-send the same message, causing a duplicate to the recipient.
**WHY**: The schema includes a `dispatching` status in the CHECK constraint, but the spec never mandates a transition to `dispatching` before calling Baileys. The restart logic picks `pending` rows, not `dispatching`. Without an intermediate state, there is no idempotency guard against process crashes.
**FIX**: Immediately after `SELECT … FOR UPDATE SKIP LOCKED`, `UPDATE status='dispatching', dispatched_at=NOW()`. The Baileys send follows. On restart, ignore rows in `dispatching` that are older than a timeout (e.g., 60s) and mark them as failed for manual review.

### 8. MEDIUM — SSE RBAC filter can raise exceptions, terminating the SSE stream without cleanup or retry

**WHAT**: Inside the SSE async generator, the call `if not await can_view_message(user, payload): continue` lacks try/except. If the RBAC check raises (e.g., DB timeout, connection error, coding bug), the generator crashes, the `finally` block unsubscribes, and the user loses their realtime stream permanently until a manual reload.
**WHY**: The spec’s code in §4.1 wraps `q.get()` with try/except for `asyncio.TimeoutError` but not the RBAC call.
**FIX**: Wrap the entire message-processing block in a general `try/except`, log the error, and yield an error event (or silently skip) without breaking the stream. This keeps the connection alive.

### 9. MEDIUM — `wa_outbound_idempotency` rows never cleaned; table grows unbounded

**WHAT**: Idempotency rows have `expires_at` but no automatic cleanup (cron, pg_cron, or periodic DELETE). Over months, every send attempt adds a row; the table swells, degrading index performance and wasting storage.
**WHY**: The schema defines `expires_at DEFAULT NOW() + INTERVAL '24 hours'` but provides no job to delete expired rows. With 10 messages/day/operator, 3 operators → 10k rows/year — not huge, but still a leak.
**FIX**: Add a simple cron job or pg_cron `DELETE FROM wa_outbound_idempotency WHERE expires_at < NOW();` running hourly, or use partitioning by expiration time.

### 10. MEDIUM — `idx_wdt_unique_thread` COALESCE expression allows empty-string vs NULL collision

**WHAT**: `CREATE UNIQUE INDEX ... (counterpart_phone, COALESCE(team_member_phone, ''), COALESCE(group_jid, ''))` will treat NULL and empty string identically. If frontend code accidentally submits `team_member_phone` as `""`, it conflicts with the NULL-based merged thread, causing mysterious unique-constraint violations or silent overwrite.
**WHY**: The column `team_member_phone VARCHAR(20)` doesn’t have a NOT NULL constraint, and the app might send empty string from an uncontrolled input. NULL is used for the “cross-account merged” thread, but empty string merges into the same semantics unexpectedly.
**FIX**: Add a `CHECK (team_member_phone IS NULL OR team_member_phone <> '')` constraint. Reject empty strings at the API level with validation.

### 11. MEDIUM — SSE `Last-Event-ID` replay not designed; message loss during reconnect is unhandled

**WHAT**: The spec mentions “implementare server-side cursor su `wa_message_inserted.id`” for replay but provides zero detail. Without it, if a browser’s SSE reconnects after sleep/wake, all messages inserted during the gap are permanently missed. The operator sees a silent gap in the chat.
**WHY**: R12 acknowledges the need but defers it. The spec’s code simply starts a new stream with no replay logic. The user experience on flaky WiFi would be lossy.
**FIX**: Before the SSE stream begins, parse the `Last-Event-ID` header; query for messages with `id > last_event_id` (limited to a window) and replay them as initial events before going live. This completes the SSE contract.

### 12. LOW — No CSRF protection on send endpoint; localhost-only but still a same-origin assumption risk

**WHAT**: The send endpoint uses cookie-based JWT auth without a CSRF token. The app runs exclusively on localhost, so same-origin attacks from external sites are unlikely. However, a malicious process on the same machine (e.g., a rogue Electron app, a compromised local service) could forge POSTs from the browser’s cookie jar.
**WHY**: Localhost doesn’t guarantee single-user; an attacker with local execution could exploit lack of CSRF to send outbound WhatsApp messages. The risk is LOW due to physical access constraints, but adversaries with local code exec are inside the threat model of a team device.
**FIX**: Add a `X-CSRF-Token` header check (synchronizer token pattern) for write mutation endpoints, or at minimum use `SameSite=Strict` cookies (already implied by localhost).

---

**VERDICT: DON'T SHIP** — The SSE subscriber backpressure deadlock and the outbound jitter race can silently brick realtime delivery and trigger WhatsApp bans on day one; the spec must be patched before any code reaches production.
