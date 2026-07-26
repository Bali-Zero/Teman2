# wa-dashboard

Local-only Next.js 16 app for the Bali Zero team WhatsApp inbox.

**M1 scope**: read-only SSE live stream of all team WA messages, RBAC-filtered server-side.

## Stack

- Next.js 16 + React 19 + Tailwind v4
- SSE via native EventSource → `/api/v1/wa-dashboard/stream`
- Zustand store (1000-message rolling buffer)
- react-virtuoso virtualized list

## Dev

```bash
cd apps/wa-dashboard
npm install
WA_DASHBOARD_BACKEND_URL=http://localhost:8080 npm run dev
# open http://localhost:3030
```

For production backend:

```bash
WA_DASHBOARD_BACKEND_URL=https://nuzantara-rag.fly.dev npm run dev
```

Run the unit tests and the coverage gate for the inbox buffer and action API:

```bash
npm test
npm run test:coverage
```

Auth: cookie-based JWT from `nuzantara-rag` backend. Browser must already
have a valid session (login via main app first).

## Architecture

```
EventSource(/api/v1/wa-dashboard/stream)
  ├─ open      → status=open
  ├─ wa_message → useInboxStore.pushMessage()
  ├─ keepalive  → no-op
  └─ error      → reconnect with exponential backoff + jitter
```

`Last-Event-ID` header is auto-managed by the browser EventSource API —
on reconnect, missed messages are replayed via the backend
`fetch_replay()` query (devils-advocate v3 fix #11).

## What's NOT here (M1 scope boundary)

- No outbound (POST /send is M3, gated on UU PDP compliance docs)
- No thread/conversation grouping (M2 routers)
- No search, no attention queue, no Web Components fancy chat bubbles
- No browser end-to-end coverage yet (unit coverage protects the stream buffer
  and action API contracts)
