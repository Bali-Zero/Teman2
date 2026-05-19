| #   | Service            | Root cause (1 line)                                                           | Fix (1 line)                                                                       | Effort | Risk | Order |
| --- | ------------------ | ----------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ------ | ---- | ----- |
| 1   | `wa-audit-bot`     | 2 instances (Pro + Mini) polling Telegram concurrently, causing 409 Conflict. | Implement PG advisory lock for single-flight execution or disable on Mini.         | 10 min | Med  | 1     |
| 2   | `flowkit`          | API returns 403 on Veo 3.1, causing an infinite, unthrottled 10s retry loop.  | Add circuit breaker: suspend job and alert after 3 consecutive 403s.               | 10 min | Med  | 2     |
| 3   | `alert-dispatcher` | `pg-proxy` hiccups cause hard crashes due to missing DB connection backoff.   | Wrap asyncpg connect in a retry loop with exponential backoff (max 60s).           | 15 min | Low  | 3     |
| 4   | `sentinel`         | Sentinel aggressively logs 17 broken/stale tasks as WARNINGs on every cycle.  | Fix the 4 failing jobs directly; relax `stale` threshold (e.g., 24h) for the rest. | 30 min | High | 4     |
| 5   | `dlq_autopilot`    | Python `logging.basicConfig` routes normal INFO status checks to stderr.      | Redirect INFO to `sys.stdout` and split LaunchAgent `StandardOutPath`.             | 5 min  | Low  | 5     |
| 6   | `translate-hourly` | Script logs normal SKIP/DONE file operations to stderr.                       | Redirect INFO to `sys.stdout` and split LaunchAgent `StandardOutPath`.             | 5 min  | Low  | 6     |
| 7   | `heartbeat-bridge` | Uvicorn/httpx standard health checks are routed to stderr by default.         | Redirect INFO to `sys.stdout` and split LaunchAgent `StandardOutPath`.             | 5 min  | Low  | 7     |

### Ship-first rationale

Target active state corruption and external API abuse first. `wa-audit-bot` (Order 1) is actively fighting itself and dropping messages. `flowkit` (Order 2) is hammering Google APIs with 403s and risking an account ban. `alert-dispatcher` (Order 3) ensures we don't miss future failures. The cosmetic logging issues (Orders 5-7) pose zero operational risk and should be batched at the end.

### Hard pass items

Do NOT touch `wr2_queue_server.err.log` (stale since May 11, service likely dead) or any of the Wave 1 fixed logs (`wr2_canva_apply`, `wr2_supervisor`, `wr2_supervisor_watchdog`). A simple `rm` or `truncate` command handles them; zero engineering effort should be spent.

**PANEL_DECISION:** Fix `wa-audit-bot` immediately via Postgres advisory lock to stop the active polling conflict between Pro and Mini.
