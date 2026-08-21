# network-call retry census: httpx/requests call-sites without retry or backoff, risk-ranked

Read-only analysis — no plan to edit/commit/push anything.

Search `apps/backend-rag/backend` and `apps/` generally for outbound network
calls (`httpx.` async calls, `requests.` where legacy, `aiohttp` if present)
and classify each call-site by whether a transient network failure is
survivable: is there a retry with backoff, a timeout, an exception handler
that distinguishes transient (`TimeoutError`, `httpx.ConnectError`,
`asyncpg.InterfaceError`-class) from permanent?

Why (scar family #8, cicatrix-superscar.md): normal short proxy/WireGuard
flaps have repeatedly cascaded into lost transactions here (W49: 98 lifetime
TimeoutErrors in one watchdog; W55: single-attempt Telegram alerter dropping
alerts).

Classify:

- HIGH: production request path or a client-facing channel (WhatsApp,
  Instagram, web chat) where one flap loses user-visible work
- MEDIUM: cron/background where a flap silently skips a cycle with no receipt
- LOW: retried already, or failure is loud and re-runnable

Output a markdown table: file:line | call (truncated) | timeout? | retry? |
transient-vs-permanent handling? | risk | one-line reason. Sort HIGH first.
State N of M totals, never a silent cap.
