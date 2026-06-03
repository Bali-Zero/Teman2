# WA Meta Inbox (local)

Desktop-local UI for the **BALI ZERO WhatsApp Business (Meta API)** number
`+62 821-3465-159`. Read and reply to threads, with bot human-in-the-loop
(takeover / release).

This is the **LOCAL LAYER** (Section 5) of the `wa-meta-inbox` feature. It is a
**thin proxy**: it holds **no database**, binds **`127.0.0.1` only**, and
forwards authenticated requests to the FastAPI backend on Fly
(`https://nuzantara-rag.fly.dev/api/wa-inbox/*`), attaching the `X-API-Key`
read from the macOS Keychain. The key is never exposed to the browser.

## Architecture

```
browser (viewer.html, same-origin)
   │  GET  /api/threads, /api/threads/:id            (read, no CSRF)
   │  POST /api/send, /api/takeover, /api/release     (mutation, X-Local-CSRF required)
   ▼
server.cjs  (127.0.0.1:7791, Node builtins + native fetch, NO pg, NO npm deps)
   │  adds X-API-Key (from Keychain)        ephemeral in-memory CSRF token
   ▼
https://nuzantara-rag.fly.dev/api/wa-inbox/*  (FastAPI, authenticated)
```

### Security

- **Bind loopback only.** `127.0.0.1`, never `0.0.0.0`.
- **Fail loud.** Missing/locked API key → precise log + `exit(1)`. No half-broken UI.
- **Ephemeral CSRF.** `crypto.randomUUID()` at startup, in-memory, never on disk,
  injected into `viewer.html`, validated on every mutation (`/send`, `/takeover`,
  `/release`) → `403` if missing/wrong (fail-closed). GET routes do not need it.
- **Known limit (not masked):** the CSRF token protects against *browser-CSRF*
  (other localhost pages). It does **not** protect against a malicious *local
  process* that `curl`s + scrapes the page to lift the token. For a single
  operator on their own Mac (whoever controls the machine already has access)
  this is an accepted risk.

## Setup

### 1. Put the Fly API key in the Keychain

The backend `/api/wa-inbox/*` router uses a dedicated (non-admin) key added to
`Settings.api_keys`. Store it locally in the login Keychain:

```bash
security add-generic-password -s wa-inbox-api-key -a "$USER" -w <KEY>
```

Dev/smoke fallback (no Keychain): `export WA_INBOX_API_KEY=<KEY>` before launch.

### 2. Install the app + LaunchAgent

```bash
bash install_app.sh
```

Idempotent. It:
- generates `~/Desktop/WA Meta Inbox.app` (LSUIElement, opens `http://127.0.0.1:7791/`,
  best-effort bootstraps the LaunchAgent if the daemon is down);
- materializes `~/Library/LaunchAgents/com.balizero.wa-meta-inbox.plist` from
  `com.balizero.wa-meta-inbox.plist.example` (absolute node path, `WorkingDirectory`,
  logs in `~/logs/wa-meta-inbox.{out,err}.log`, port **7791**, KeepAlive);
- runs `plutil -lint`, then `bootout` + `bootstrap` (no duplicate registration).

The label / port / logs are **unique** — no collision with
`com.balizero.wa-dashboard-m1` (which owns `:7790`).

## Verify

```bash
# process is listening on loopback:7791 (and NOT on 0.0.0.0)
lsof -nP -iTCP@127.0.0.1:7791 -sTCP:LISTEN

# LaunchAgent is registered + last exit code
launchctl print "gui/$(id -u)/com.balizero.wa-meta-inbox" | head -20

# local health (no proxy)
curl -s http://127.0.0.1:7791/health.json

# startup logs (auth-probe result: 200 OK / 401 rejected)
tail -n 40 ~/logs/wa-meta-inbox.out.log ~/logs/wa-meta-inbox.err.log
```

Open the UI via the `.app` on the Desktop, or `open http://127.0.0.1:7791/`.

## Files

| File | Purpose |
|---|---|
| `server.cjs` | Thin proxy. Node builtins only, `127.0.0.1:7791`, no DB. |
| `viewer.html` | Single-file vanilla-JS UI (Italian). 2-col inbox + takeover + 24h banner. |
| `package.json` | Minimal manifest (no dependencies). |
| `com.balizero.wa-meta-inbox.plist.example` | LaunchAgent template (placeholders). |
| `install_app.sh` | Idempotent installer (`.app` + plist + bootstrap). |

## Notes

- `WA_INBOX_BACKEND_URL` overrides the Fly base URL (default `https://nuzantara-rag.fly.dev`).
- `WA_INBOX_PORT` overrides the port (default `7791`).
- `WA_INBOX_KEYCHAIN_SERVICE` overrides the Keychain service name (default `wa-inbox-api-key`).
- The backend `/api/wa-inbox/*` endpoints are the **server layer** (Section 4) and are
  not part of this directory; the local proxy assumes they exist on Fly.
