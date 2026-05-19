| #   | Service          | Root cause (1 line)                                                                      | Fix (1 line)                                                                                          | Effort (min) | Risk | Order |
| --- | ---------------- | ---------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | ------------ | ---- | ----- |
| 1   | dlq_autopilot    | INFO logs wrongly routed to stderr due to misconfigured logging stream.                  | Redirect INFO to stdout via `logging.basicConfig(stream=sys.stdout)` and separate plist paths.        | 5            | low  | 4     |
| 2   | translate-hourly | All INFO (including skip messages) goes to stderr instead of stdout.                     | Same logging stream fix + adjust plist for stdout.                                                    | 5            | low  | 5     |
| 3   | heartbeat-bridge | HTTP request INFO logged to stderr (should be stdout).                                   | Same fix: set Python logging to stdout, update plist.                                                 | 5            | low  | 6     |
| 4   | wa-audit-bot     | Two bot instances polling same token cause Conflict errors and 18MB/day logs.            | Boot out duplicate instance; add PG advisory lock for single‑flight.                                  | 10           | low  | 1     |
| 5   | flowkit          | Veo API returns 403 (access denied) causing infinite retries every 10s.                  | Add circuit breaker: stop retry after 3 consecutive 403s, alert, suspend job. Verify account.         | 10           | low  | 2     |
| 6   | alert-dispatcher | pg‑proxy down causes immediate connection refusal; no backoff/retry leads to crash loop. | Add asyncpg retry with exponential backoff and 60s circuit breaker (pattern from intel‑lake modules). | 15           | med  | 3     |
| 7   | sentinel         | WARNING messages on stderr; 17+ tasks are stale/failed, generating 21MB/day.             | Investigate 4 failed tasks root cause; adjust stale threshold to 24h live‑hours; defer deeper fixes.  | 30           | high | 7     |

**Ship-first rationale**

1. Fix wa-audit-bot double instance immediately stops daily log spam and restores bot reliability (P1, low risk).
2. Flowkit 403 circuit breaker prevents infinite retry waste and unblocks WR3 video pipeline (P1, low risk).
3. Alert-dispatcher backoff prevents crash loop when pg-proxy hiccups, ensuring federation alerts survive (P1, med risk).
4. INFO→stderr misconfigs are cheap, low-risk and reduce daily log volume by ~175MB, making alerts cleaner.
5. Sentinel investigation is deferred because it requires deep triage of 17+ tasks and risk of mis-fix; it's the last item.

**Hard pass items**

- wr2_queue_server stale log (excluded per prompt).
- Already-fixed Wave 1 logs (C items) – no action needed.
- Any further sentinel optimization beyond threshold adjustment until root causes of each task are understood.

**PANEL_DECISION: Ship wa-audit-bot double-instance fix first (order 1), then flowkit circuit breaker, then alert-dispatcher retry, then the three log routing fixes; schedule sentinel triage for next wave.**
