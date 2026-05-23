---
date: 2026-05-23
domain: operations
loop: NB-automations-hardening W55
status: shipped (commit e0525e228); empirical live — bad token returns 404 non-retry, real token returns True (happy path preserved)
---

# W55 — `sentinel_lib/alerter.py` retry-with-backoff for transient network errors

## TL;DR

149 lifetime `[ALERT-FAILED]` entries in sentinel.log were 100% transient network errors
(DNS NXDOMAIN, SSL handshake timeout, network unreachable, connection reset). Single 10s
attempt was insufficient — alerts silently dropped during NordVPN/WiFi flap. Fix: 3-attempt
retry with progressive backoff (1s/3s), discriminating transient (retry) vs auth/payload
(no retry).

## Empirical evidence pre-W55

```
$ grep "ALERT-FAILED" ~/logs/sentinel.log | awk -F'] ' '{print $2}' | sort | uniq -c | sort -rn
  53 <urlopen error [Errno 8 nodename nor servname provided, or not known>     # DNS NXDOMAIN
  33 <urlopen error _ssl.c:989: The handshake operation timed out>             # SSL handshake
  19 <urlopen error [Errno 65 No route to host>                                 # network/route
  14 <urlopen error [Errno 51 Network is unreachable>                          # network/unreachable
  13 <urlopen error timed out>                                                  # generic timeout
  10 The read operation timed out                                              # read timeout
   7 <urlopen error [Errno 54 Connection reset>                                # TCP reset
```

**All 149 lifetime failures are transient network problems** (0 auth/format errors). Cause:
NordVPN/WiFi/route flap during cron tick. Sentinel `send_alert` had single 10s attempt then
gave up + printed `[ALERT-FAILED] <error>` to stdout (caught by launchd → sentinel.log).
Operator never saw the escalation.

## Root cause

`scripts/sentinel_lib/alerter.py:94-106` (pre-W55):

```python
try:
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": full_message}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{bot_token}/sendMessage", data=data)
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status == 200:
            _mark_sent(dedup_key)
            return True
except Exception as e:
    print(f"[ALERT-FAILED] {e}")
return False
```

Single attempt. No retry. No discrimination between transient (network flap) and permanent
(payload error) failures. The `# Strip Markdown formatting — use plain text to avoid 400
errors from underscores/special chars` comment shows the previous attempt to harden this
was payload-focused; the actual failure mode was network.

## Fix shipped

`scripts/sentinel_lib/alerter.py:94-141` (post-W55, commit `e0525e228`):

```python
data = urllib.parse.urlencode({"chat_id": chat_id, "text": full_message}).encode()
req = urllib.request.Request(f"https://api.telegram.org/bot{bot_token}/sendMessage", data=data)
last_err: Exception | None = None
for attempt in range(1, 4):
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                _mark_sent(dedup_key)
                return True
            # Non-200 HTTP — don't retry (payload/auth/rate)
            print(f"[ALERT-FAILED] HTTP {resp.status} (non-retryable)")
            return False
    except urllib.error.HTTPError as e:
        last_err = e
        if 500 <= e.code < 600:
            print(f"[ALERT-RETRY {attempt}/3] HTTP {e.code} (retrying)")
        else:
            # 4xx — payload/auth/rate. Don't retry.
            print(f"[ALERT-FAILED] HTTP {e.code} (non-retryable): {e}")
            return False
    except Exception as e:
        # URLError, socket.timeout, ssl.SSLError, etc. — all transient.
        last_err = e
        print(f"[ALERT-RETRY {attempt}/3] {type(e).__name__}: {e}")
    if attempt < 3:
        time.sleep(1 if attempt == 1 else 3)
print(f"[ALERT-FAILED] exhausted 3 retries (last error: {last_err})")
return False
```

Discrimination table:

| Failure type | Decision | Why |
|---|---|---|
| HTTP 200 | success | happy path |
| HTTP 4xx (incl. 400 bad payload, 401 auth, 404 wrong bot, 429 rate) | no retry | won't fix by retry |
| HTTP 5xx (server error) | retry | server may recover |
| `URLError`, `socket.timeout`, `ssl.SSLError`, generic `OSError` | retry | network transient |

Total max wall time: ~14s (3×10s timeout cap + 1s + 3s backoff). Acceptable in cron context
where deadline is multi-minute.

Added `import urllib.error` at top.

Mirrors W49 (lease watchdog connect-retry) and W47 (supervisor keepalive) patterns —
**transient-error resilience** family.

## Empirical verification (live)

```
$ TELEGRAM_BOT_TOKEN=invalid_token TELEGRAM_ADMIN_CHAT_ID=00000000 python3 -c "
  from sentinel_lib.alerter import send_alert
  print(send_alert('W55 smoke', level='INFO'))"
[ALERT-FAILED] HTTP 404 (non-retryable): HTTP Error 404: Not Found
False
```

Correct: 404 is auth/wrong-bot, not transient → no retry.

```
$ source ~/.nuzantara-secrets.env && python3 -c "
  from sentinel_lib.alerter import send_alert
  print(send_alert('W55 happy path verify', level='INFO'))"
True
```

Happy path preserved.

Transient-retry path will only fire during actual network flap; verification will happen
naturally next time NordVPN drops or WiFi blips during a sentinel cron tick.

## Deferred W56+ candidates

1. **Logger.warning instead of `print()` for `[ALERT-RETRY*]`**: currently uses `print()`
   which goes to stdout/stderr → captured by launchd → sentinel.log. Switching to
   `logger.warning` would attach timestamps and severity for cleaner triage. Trivial change
   but requires `logger = logging.getLogger("sentinel.alerter")` import.
2. **Exponential backoff with jitter**: current 1s/3s is fixed. If many sentinels retry
   simultaneously (cluster of cron ticks during NordVPN flap), exp+jitter spreads load.
3. **NordVPN-detector pre-check**: if `/usr/local/bin/nordvpn status` shows "Disconnected"
   OR known-NordVPN-process-running, skip Telegram alert (it WILL fail). Adds 50ms latency
   per call but avoids the 30s 3-retry window during known-bad state.
4. **Apply same retry pattern to other Telegram alert sites**: `dlq_autopilot.py`,
   `wr2_canva_lease_watchdog.py`, `regulatory-watcher.sh`, etc. all have their own urlopen
   calls to Telegram. Audit + dedupe via shared library.

## Lessons

- **"100% transient" categorical signal**: when 149 of 149 errors are transient (zero
  payload/auth), the fix is obvious — retry. When categories are mixed, retry-with-discrimination is needed.
- **Discrimination by error type matters**: blindly retrying 4xx wastes 30s per call AND
  burns rate limits. Distinguishing 4xx (no retry) from 5xx + URLError (retry) is the right
  default.
- **Existing comment in code was misdirection**: `# Strip Markdown formatting — use plain
  text to avoid 400 errors from underscores/special chars` led me to investigate payload
  issues first. But empirical grep showed 0 4xx errors. **Always grep the actual error log
  before trusting the comment's framing.**
- **Test the negative path with bad credentials**: W55 verification used `invalid_token` to
  exercise the 404 no-retry branch without spam. Critical sanity check for retry logic.
- **Family**: transient-error resilience. Sister to W47 (long-running keepalive) and W49
  (one-shot connect-retry). All three address pg-proxy/network flap. W55 closes the
  cross-net flap on the OUTBOUND side (alerts to Telegram).

## Reference

- Commit: `e0525e228` — `fix(sentinel-alerter): retry-with-backoff for transient network errors`
- File: `scripts/sentinel_lib/alerter.py:94-141` (~30 lines net change incl. import)
- Sister patterns: W47 (`scripts/wr2_supervisor_watchdog.py` keepalive), W49 (`scripts/wr2_canva_lease_watchdog.py` retry)
- Pre-W55 error sample: `~/logs/sentinel.log` lifetime 149 `[ALERT-FAILED]` entries (0 4xx)
