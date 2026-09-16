1. [Pro] **BLOCKER** — `apps/backend-rag/backend/services/integrations/wa_inbox_bot.py`: `AND m.id < wo.message_id` with `ORDER BY m.id DESC LIMIT 1`. Concurrent webhook transactions can interleave IDs: inbound A=100, inbound B=101, stub B=102, stub A=103; legacy row A then derives B, a newer inbound than its actual cause. Derive only when the same-thread candidate is causally unambiguous; otherwise fail loudly with a bounded legacy-anchor error rather than guessing.

2. **MAJOR** — `apps/backend-rag/backend/services/integrations/wa_inbox_bot.py`: `AND (id = $2 OR (id < $2 AND body IS NOT NULL AND body <> ''))`. Whitespace-only history entries are not filtered and consume `_HISTORY_TURNS` capacity, so valid older context can be displaced. Use `BTRIM(body) <> ''` before `LIMIT`.

3. **MAJOR** — `apps/backend-rag/backend/services/integrations/wa_inbox_bot.py`: `query = rows[0]["body"] or ""`, followed by `wa_codex_leg.py`: `if not query:`. A whitespace-only anchor remains truthy and reaches generation as the query. Test emptiness with `if not query.strip()` while preserving the original body if whitespace is semantically significant downstream.

4. **MAJOR** — `apps/backend-rag/backend/services/integrations/wa_inbox_bot.py`: `FROM wa_outbox wo WHERE wo.id = $1`. The loader never proves that the requested outbox belongs to the supplied `thread_id`; a router/leg mismatch silently becomes an empty context and follows `no_customer_message`. Bind the lookup to both IDs and raise an invariant error on mismatch instead of returning an ordinary empty context.

5. **MINOR** — `apps/backend-rag/backend/services/integrations/wa_inbox_bot.py`: `SELECT COALESCE(wo.inbound_message_id, (...)) AS anchor_id`. A non-NULL binding is accepted without verifying that it references a customer inbound in `wo.thread_id` and precedes the stub. Join and validate those invariants, failing loudly if violated.

6. **CLEAN — anchor boundary/burst:** `id = $2` becomes `query`, while only `rows[1:]` becomes history; row 2 sees message 1 and older non-empty messages, never message 2 in history or message 3, and the cap is applied after the exact-empty filter.

7. **CLEAN — different-thread legacy derive:** the fallback subquery explicitly requires `m.thread_id = wo.thread_id`; no cross-thread candidate is selected there.

8. **CLEAN — PII:** new logs contain only integer inbound/outbox IDs; no phone number, body, or client name is logged or stored in the new column.

9. **CLEAN — field contract:** `BoundThreadContext.inbound_message_id`, `query`, and `history` are written and read under matching names; no `None` is coerced into message content.

10. **CLEAN — old-behaviour fallback:** apart from the ambiguous legacy derivation in finding 1, this diff does not explicitly fall back to `_load_thread_context` or thread-latest loading.
