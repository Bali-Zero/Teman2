# [DRAFT] feat(streaming): X-Stream-Resume-Token for mid-stream resume

> Draft body for a GitHub issue against `nuzantara-rag`. Copy & open manually
> when ready (frontend cannot create issues from this worktree).

## Problem

`apps/mouth` chat (`apps/mouth/src/lib/api/chat/chat.api.ts:108`, function
`sendMessageStreaming`) consumes SSE from `POST /api/agentic-rag/stream`.
The frontend now retries the **initial handshake** automatically with
exponential backoff (500/1000/2000ms × 3 attempts, see
`apps/mouth/src/lib/api/chat/streaming-retry.ts`). However, once the stream
has begun emitting `token` events and the network drops, we have no way to
resume from the last delivered byte — re-sending the request from scratch
would either:

1. Re-charge the LLM call and produce non-deterministic divergence in the
   answer, or
2. Duplicate already-rendered tokens for the user.

Currently, on mid-stream drop we surface a `NETWORK` error toast and the
user must re-send manually. That's acceptable as a v1 fallback but degrades
UX on flaky 3G/4G mobile clients (a common case for our Bali users).

## Proposal

Backend (`apps/backend-rag/backend/app/streaming.py`) emits a
**resume token** with each chunk and persists incremental conversation
state to Redis (TTL = 5 min). On reconnection, the client passes
`X-Stream-Resume-Token: <token>` header in the retry POST; the backend:

1. Validates the token against the Redis key.
2. Skips already-emitted tokens (returns from the cached response state).
3. Continues the LLM stream from the last chunk if the LLM call is still
   in-flight, or re-emits cached tokens followed by the rest of the
   buffered response if it completed during the disconnection.

### SSE event additions

Augment each `data:` payload with `chunk_id`:

```jsonc
data: {"type":"token","data":"...","chunk_id":42,"resume_token":"sess-abc:42"}
```

### Redis schema

```
KEY: stream:resume:<session_id>:<request_id>
TTL: 300s
VALUE: {
  "tokens": ["...","..."],   // ordered chunks
  "sources": [...],
  "metadata": {...},
  "completed": false,
  "last_chunk_id": 42,
}
```

### Frontend behaviour

`streaming-retry.ts` already classifies error types. After this lands:

- `chat.api.ts` stores the latest `resume_token` from each event.
- On a mid-stream `network` error (i.e. after `firstChunkTime` is set),
  the hook offers a "Resume" button instead of "Retry" and re-POSTs with
  `X-Stream-Resume-Token`.
- Existing TODO marker is in `chat.api.ts` next to the `retryableFetch`
  call — search for `TODO(backend-resume-token)`.

## Acceptance criteria

- [ ] `X-Stream-Resume-Token` header accepted on `POST /api/agentic-rag/stream`
- [ ] `chunk_id` + `resume_token` fields in each SSE `token`/`sources`/`tool_call`
      event (additive, won't break existing parsers)
- [ ] Redis state persisted incrementally during stream (not only on completion
      as today, see `streaming.py:472-477`)
- [ ] 5-min TTL with manual cleanup on `done`
- [ ] Backend integration test: simulate disconnect after chunk 5 → resume → full
      response identical to no-disconnect baseline
- [ ] Frontend wires up the token (separate PR)

## Out of scope

- Mobile-only; desktop already handles this fine via network resilience.
- Multi-tab resume of the same `session_id` (requires per-tab `request_id`).
- Resume across LLM provider failover.

## References

- Frontend retry layer: `apps/mouth/src/lib/api/chat/streaming-retry.ts`
- Frontend integration point: `apps/mouth/src/lib/api/chat/chat.api.ts:265` (look for
  `TODO(backend-resume-token)`)
- Backend save site: `apps/backend-rag/backend/app/streaming.py:472-477`
- Backend SSE emit loop: `apps/backend-rag/backend/app/streaming.py:436-548`
