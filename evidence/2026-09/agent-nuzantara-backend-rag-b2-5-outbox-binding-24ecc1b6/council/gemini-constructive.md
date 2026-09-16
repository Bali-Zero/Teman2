1. **MAJOR (Focus 1: Client Experience on Burst Failures & Apology Storm)**
   - **Location**: [`wa_outbox_worker.py:421-435`](file:///apps/backend-rag/backend/services/integrations/wa_outbox_worker.py#L421-L435) / [`wa_outbox_worker.py:1053-1070`](file:///apps/backend-rag/backend/services/integrations/wa_outbox_worker.py#L1053-L1070)
   - **Why it matters**: With coalescing removed, all 3 rows in a burst are served independently. If a sustained generation or provider error occurs, message 1 exhausts retries and calls `_maybe_send_apology()`, sending an apology to the client. Message 2 then unblocks, exhausts retries, and sends a _second_ apology; message 3 then sends a _third_ apology. Alternatively, if message 1 fails but message 2 succeeds seconds later, the client receives an apology followed immediately by a regular reply.
   - **Concrete Improvement**: In `_maybe_send_apology()`, check if newer pending rows exist for the same thread (`SELECT 1 FROM wa_outbox WHERE thread_id = $1 AND id > $2 AND status = 'pending' LIMIT 1`) and suppress the apology if a successor is queued, or enforce a per-thread apology rate limit / cooldown.

2. **MAJOR (Focus 1: Head-of-Line Blocking under Exponential Backoff)**
   - **Location**: [`wa_outbox_worker.py:665-678`](file:///apps/backend-rag/backend/services/integrations/wa_outbox_worker.py#L665-L678)
   - **Line content**: `AND older.status IN ('pending', 'claimed', 'generating')`
   - **Why it matters**: If message 1 experiences a transient failure and enters exponential retry backoff (e.g., `next_retry_at = NOW() + 60s`), messages 2 and 3 remain in `status = 'pending'` with `next_retry_at <= NOW()`, but are blocked because message 1 is still `status = 'pending'`. The entire thread stalls for the duration of message 1's backoff ladder without attempting to answer newer queued queries.
   - **Concrete Improvement**: Cap the retry backoff delay for `needs_generation` rows tightly (e.g., max 5s–10s) or classify deterministic generation failures immediately as non-retryable so successor rows unblock promptly without violating FIFO ordering.

3. **MINOR (Focus 2: Lease Heartbeat & Fencing on Pre-Send Takeover Abort)**
   - **Location**: [`wa_outbox_worker.py:1251-1259`](file:///apps/backend-rag/backend/services/integrations/wa_outbox_worker.py#L1251-L1259)
   - **Line content**: `await conn.execute(""" UPDATE wa_outbox SET status = 'failed', generation_fall_off_reason = 'aborted_human_takeover_pre_send' ... WHERE id = $1 AND claim_token = $2 AND status = $3 """, outbox_id, claim_token, expected_status)`
   - **Why it matters**: Unlike all other fenced status transitions in [`_process_claimed_row`](file:///apps/backend-rag/backend/services/integrations/wa_outbox_worker.py#L798-L1335) (which use `fetchrow` and verify `if not fenced: return`), this pre-send abort uses `conn.execute` and ignores whether the update matched. If the claim lease expired during a long generation and another worker or the takeover endpoint stole the row, this write silently updates 0 rows while execution falls through to the 24h window check.
   - **Concrete Improvement**: Use `fenced = await conn.fetchrow(...)` and return early if `not fenced`, matching lines 798, 839, 1053, 1286, and 1322.

4. **MAJOR (Focus 3: Stale Fallback Generator Left Unbound)**
   - **Location**: [`wa_inbox_bot.py:406-407`](file:///apps/backend-rag/backend/services/integrations/wa_inbox_bot.py#L406-L407) & [`wa_codex_leg.py:130-137`](file:///apps/backend-rag/backend/services/integrations/wa_codex_leg.py#L130-L137)
   - **Line content**: `async def generate_bot_reply(pool: asyncpg.Pool, thread: Any) -> str:`
   - **Why it matters**: While [`wa_codex_leg.py`](file:///apps/backend-rag/backend/services/integrations/wa_codex_leg.py#L651) was migrated to [`_load_bound_thread_context`](file:///apps/backend-rag/backend/services/integrations/wa_inbox_bot.py#L327), [`generate_bot_reply`](file:///apps/backend-rag/backend/services/integrations/wa_inbox_bot.py#L406) (the standalone bot generator) still calls the legacy [`_load_thread_context`](file:///apps/backend-rag/backend/services/integrations/wa_inbox_bot.py#L309) without binding to `outbox_id`. Any worker, test, or fallback path using `generate_bot_reply` still exhibits defect D1 (answering latest thread inbound instead of bound inbound).
   - **Concrete Improvement**: Update [`generate_bot_reply`](file:///apps/backend-rag/backend/services/integrations/wa_inbox_bot.py#L406) to accept `outbox_id: int` and use [`_load_bound_thread_context`](file:///apps/backend-rag/backend/services/integrations/wa_inbox_bot.py#L327), or explicitly mark [`_load_thread_context`](file:///apps/backend-rag/backend/services/integrations/wa_inbox_bot.py#L309) as deprecated with warnings that it must not be used for outbox reply generation.

5. **MINOR (Focus 4: Explicit Table Target in `FOR UPDATE SKIP LOCKED`)**
   - **Location**: [`wa_outbox_worker.py:679-680`](file:///apps/backend-rag/backend/services/integrations/wa_outbox_worker.py#L679-L680)
   - **Line content**: `ORDER BY next_retry_at, id FOR UPDATE SKIP LOCKED`
   - **Why it matters**: The partial index [`wa_outbox_thread_needs_generation_active_idx`](file:///apps/backend-rag/backend/db/migrations_v2/316_wa_outbox_inbound_binding_and_terminal_reasons.sql#L164) matches the correlated `NOT EXISTS` subquery shape `(thread_id, id)`. However, using `FOR UPDATE SKIP LOCKED` without `OF w` when querying a aliased table with a correlated subquery on the same table can lead to planner locking ambiguities or prevent anti-join query transformations.
   - **Concrete Improvement**: Change line 680 to `ORDER BY next_retry_at, id FOR UPDATE OF w SKIP LOCKED`.

6. **MAJOR (Focus 5: Unindexed Foreign Key Trap on `inbound_message_id`)**
   - **Location**: [`316_wa_outbox_inbound_binding_and_terminal_reasons.sql:100-105`](file:///apps/backend-rag/backend/db/migrations_v2/316_wa_outbox_inbound_binding_and_terminal_reasons.sql#L100-L105)
   - **Line content**: `ALTER TABLE wa_outbox ADD CONSTRAINT wa_outbox_inbound_message_id_fkey FOREIGN KEY (inbound_message_id) REFERENCES meta_inbox_messages(id) NOT VALID;`
   - **Why it matters**: `wa_outbox.inbound_message_id` references `meta_inbox_messages(id)` without creating an index on `wa_outbox(inbound_message_id)`. Any future deletion, retention cleanup, or GDPR purge on `meta_inbox_messages` will force PostgreSQL into a full sequential scan on `wa_outbox` with table-level locks for each deleted record.
   - **Concrete Improvement**: Add `CREATE INDEX IF NOT EXISTS wa_outbox_inbound_message_id_idx ON wa_outbox (inbound_message_id);` in migration 316 (and add `DROP INDEX IF EXISTS wa_outbox_inbound_message_id_idx;` to the rollback block).
