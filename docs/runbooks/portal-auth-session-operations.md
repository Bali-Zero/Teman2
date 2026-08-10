# Portal authentication and session operations

This runbook covers the client portal session boundary shared by HTTP, cookie,
middleware and WebSocket authentication. It does not authorize a deployment;
normal review, CI and owner-controlled release gates still apply.

## Required production posture

- `ENABLE_TOKEN_REVOCATION=true` (the application default).
- `REDIS_URL` resolves to the canonical production Redis instance.
- RedisManager reports both `sync_client=true` and `async_client=true`.
- Access tokens have `exp`, `iat`, `jti` and `type=access`; normal lifetime is
  one hour.
- A logout revokes the presented `jti` until token expiry.
- Revoke-all stores an epoch marker for 24 hours and rejects only tokens whose
  `iat` is at or before that marker. A subsequent login remains valid.

Before any release, validate both Redis paths from the backend runtime without
printing the URL, tokens or client data:

```bash
cd apps/backend-rag
PYTHONPATH=. .venv/bin/python -c 'import asyncio; from backend.core.redis_manager import RedisManager; m=RedisManager.get_instance(); m.initialize(); h=asyncio.run(m.health_check()); s=m.get_stats(); assert h["connected"] and s["sync_client"] and s["async_client"], "Redis client pair unavailable"; asyncio.run(m.close()); print("Redis auth pair: OK")'
```

The release gate fails if either client is unavailable. Do not accept an
async-only or sync-only state: otherwise identical JWTs can receive different
auth decisions on different routes.

## Emergency availability lever

`ENABLE_TOKEN_REVOCATION=false` is an operator-controlled, incident-only
availability lever. It bypasses Redis denylist checks while cryptographic JWT
expiry and token-type validation remain enforced.

This trade is security-significant: every still-unexpired JWT becomes valid,
including a token previously denylisted by logout or revoke-all. The change
therefore requires an explicit incident decision, the normal secret/config
change procedure and a controlled redeploy. It must never be toggled
automatically by health checks or application code.

When the Redis incident is resolved:

1. verify both Redis clients with the preflight above;
2. restore `ENABLE_TOKEN_REVOCATION=true` through the normal reviewed release;
3. use a synthetic account to prove an existing session works, logout returns
   the browser to login, and replaying that exact JWT returns HTTP 401;
4. prove revoke-all rejects a pre-marker JWT and permits a newly issued JWT;
5. record only route, status and aggregate pass/fail evidence — never token or
   client values.

## WebSocket clients

The `/ws` endpoint intentionally rejects credentials in URL query parameters.
Non-browser clients should send `Authorization: Bearer <token>`. Browser clients
should use the `bearer.<token>` WebSocket subprotocol. The server echoes that
subprotocol after successful authentication. Any legacy `?token=` client must
be migrated before release; query-token compatibility must not be restored
because URLs leak into logs and history.

## Content Security Policy scope

Do not restore the former global
`Content-Security-Policy-Report-Only` header as part of a portal release. That
policy was telemetry-only, included development-only allowances and covered
unrelated application surfaces with different runtime dependencies. The
portal instead has an enforcing `Content-Security-Policy` scoped to
`/portal/:path*`; its automated contract rejects loopback origins,
`unsafe-eval`, framing and unrestricted form submission. Shared non-CSP
security headers remain global. Expanding an enforcing or report-only CSP to
other products is a separate, surface-by-surface compatibility project.
