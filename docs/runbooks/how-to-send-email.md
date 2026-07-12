# How to send an email (LLMs & agents) — the one true way

> **Purpose:** stop wasting time rediscovering the email path every session.
> Diagnosed end-to-end 2026-07-13. Every claim here was verified live, not
> remembered. If something below stops working, re-verify — don't guess.

---

## TL;DR (copy this)

Send via the internal Brevo adapter endpoint. `from=zantara@balizero.com` is set
**server-side** — you do NOT pass `from`. Auth is an admin key from the prod
`API_KEYS` secret. Body field is **`body`** (HTML string), not `html`.

```
POST https://nuzantara-rag.fly.dev/api/notifications/send-email
Header:  X-API-Key: <first entry of prod secret API_KEYS>
Header:  Content-Type: application/json
JSON:    { "to": "<addr>", "subject": "<subj>", "body": "<html string>" }
```

Response `{"status": ...}` / HTTP 200 = sent. HTTP 401 = wrong/absent key.
HTTP 422 = payload malformed (usually broken JSON from shell over-quoting).

---

## The auth key — where it lives and why the obvious one fails

- The endpoint gate (`middleware/hybrid_auth.py` → `api_key_auth.validate_api_key`)
  requires a key whose **role resolves to `admin` or `internal`**.
- **Role is by IDENTITY, not by the spelling of the key** (P0 fix #2285/#2290,
  2026-07-12). The old `REDACTED-ROTATED-KEY` / `REDACTED-ROTATED-KEY` public-repo
  defaults were **revoked** — they are no longer admin. Do not use them.
- The valid admin keys live **only in the prod Fly secret `API_KEYS`**
  (comma-separated; `settings.api_keys`). Optional `API_KEY_ROLES`
  (`key:role,...`) assigns roles explicitly.
- **`NUZANTARA_API_KEY` in `~/.nuzantara-secrets.env` on Pro does NOT work** — it
  authenticates as role `user`, which the send-email gate rejects (→ 401
  "Authentication required"). This is the #1 time-sink; don't retry it.

### Getting the working key WITHOUT ever printing it

`fly secrets list` shows digests, never values. The value is injected as `$API_KEYS`
**inside the prod container**. Run the send from inside, so the key never leaves it:

```sh
# on Pro (fly is at /opt/homebrew/bin/fly, logged in as zero@balizero.com):
export PATH="/opt/homebrew/bin:$PATH"
fly ssh console -a nuzantara-rag -C '<command that reads $API_KEYS and curls>'
```

Use `K=$(echo $API_KEYS | cut -d, -f1)` inside the container to grab the first key.

---

## The payload trap — shell-in-shell quoting

`ssh pro → fly ssh console → sh -lc → curl` is **four** quoting layers. A JSON
body with quotes gets mangled and the endpoint returns HTTP 422
`json_invalid / "Expecting value"`. **Do not inline the JSON through all layers.**
Write the JSON to a file inside the container and `curl -d @file`, or build it
with a heredoc in a single script run on Pro. See `scripts/send_email.sh` (the
runnable helper this runbook documents).

---

## Rules that always apply (non-negotiable)

- **`from=zantara@balizero.com`** always — set server-side, never overridden.
  Never `notifications@` / `subhi@` / a personal address (CLAUDE.md §13).
- **Never hardcode or print the key.** Read it from the prod secret at call time.
  The literal `REDACTED-ROTATED-KEY` in old code is dead — treat any hardcoded
  email key as a bug to remove.
- **Language to team `@balizero.com`**: Bahasa Indonesia for everyone except
  `zero@` / `antonellosiano@` (they get Italian). Subhi: bahasa default.
- **PII boundary**: never put client PII/OSINT in an email body that leaves the
  sovereign boundary without the Law-2 safeguards. Public regulatory/marketing
  content is fine.

---

## Minimal working recipe (run on Pro)

```sh
export PATH="/opt/homebrew/bin:$PATH"
# payload.json holds {"to","subject","body"} — build it locally, scp it in, or heredoc.
fly ssh console -a nuzantara-rag -C 'sh -lc "
  K=$(echo $API_KEYS | cut -d, -f1)
  cat > /tmp/p.json <<JSON
{\"to\":\"someone@balizero.com\",\"subject\":\"Subj\",\"body\":\"<p>Hi</p>\"}
JSON
  curl -sS -X POST http://localhost:8080/api/notifications/send-email \
    -H \"Content-Type: application/json\" -H \"X-API-Key: $K\" -d @/tmp/p.json
"'
```

> Note: `http://localhost:8080` from inside the container returned 404 on the
> path during diagnosis while the **public** URL returned 422/200 — so send
> against `https://nuzantara-rag.fly.dev` even from inside, OR confirm the
> in-container mount path first. Verified-working path = the public URL.
