# Renaissance Follow-up #2 — Heartbeat Telegram HTTP 400 (2026-04-30)

Discovery during live test phase of the renaissance:
`apps/evaluator/nlm_deep_research/heartbeat_monitor.py::_send_telegram`
returned `HTTP Error 400: Bad Request` from the Telegram Bot API on
every alert.

The PR-C3 fix (sourcing `~/.nuzantara-secrets.env`) successfully made
`TELEGRAM_BOT_TOKEN` reach the cron environment, so the API call
itself fired — but Telegram rejected the payload.

## Root cause

`_send_telegram` used `parse_mode: "Markdown"` (legacy v1). Pipeline
names contain underscores (`nb1_daily_refresh`, `t4_monitor`,
`db_nlm_sync`), which Markdown v1 interprets as italic delimiters.
Unbalanced underscores → "can't parse entities" → HTTP 400.

## Fix

Switch `parse_mode` from `"Markdown"` to `"HTML"`, and rewrite the
two message builders (`send_alert`, `send_daily_digest`) to emit HTML
tags instead of Markdown:

```diff
- "*NLM Pipeline Alert*"
+ "<b>NLM Pipeline Alert</b>"

- f"`{s['pipeline']}` — {s['status']}"
+ f"<code>{s['pipeline']}</code> — {s['status']}"
```

This is the same pattern `gap_scanner.py::_send_telegram` (and
`apps/cell` Telegram delivery) already use successfully. HTML mode
treats `_` as a literal character, so pipeline names stop breaking
the parser.

The em-dash `—` (`—`) and emoji are unaffected by parse_mode
changes — they're plain Unicode.

## Live verification

After deploying the patched file to Pro and running:

```bash
ssh pro 'cd ~/Desktop/nuzantara && source apps/backend-rag/.venv/bin/activate \
  && set -a && source ~/.nuzantara-secrets.env && set +a \
  && PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.heartbeat_monitor --check'
```

The log emits:

```
2026-04-30 04:21:11,837 [INFO] __main__: Telegram alert sent successfully
```

(Previously: `Failed to send Telegram alert: HTTP Error 400: Bad Request`.)

The alert message arrived in chat `1125336968` with proper formatting:
**NLM Pipeline Alert** in bold, pipeline names in monospace `code`
blocks, status emoji preserved.

## Why not MarkdownV2

MarkdownV2 (Telegram's escape-required successor) would also work,
but requires escaping `_*[]()~`>#+-=|{}.!` in every dynamic string
— easy to miss one and re-introduce HTTP 400. HTML has 3 escape
chars (`<`, `>`, `&`) and the message content here has none of them
by construction (pipeline names are `[a-z0-9_]+`, statuses are
fixed strings).

If a future pipeline name introduces `<` or `>` (unlikely — registry
schema is `pipeline_id: lowercase_with_underscores`), `html.escape()`
should be added in the builder. For now: zero escapes needed.

## Test plan

- [x] py_compile heartbeat_monitor.py
- [x] Live deploy to Pro + manual run → "Telegram alert sent
      successfully"
- [x] Verified message arrives in chat 1125336968 with HTML
      formatting intact
- [ ] (Post-merge, next 6h heartbeat tick `30 */6 * * *`) Cron-driven
      alert delivers without HTTP 400

## Out of scope

- **Wider Telegram delivery audit.** Other scripts on Pro
  (`run_gap_scanner.sh` self-built bash, `heartbeat_monitor.py`,
  `gap_scanner.py`, cell-organism, openclaw) use various
  parse_modes. A standardization pass to HTML across the board would
  reduce future surprises but is a separate cleanup PR.
- **html.escape() in message builders.** Defensive but not needed
  for current input alphabet (no special HTML chars in pipeline
  ids or registry strings).

## Related

- Renaissance summary: `docs/ops/2026-04-30-renaissance-summary.md`
- Predecessor PR-C3: `docs/ops/2026-04-30-pr-c3-missing-env.md`
  (sourced secrets so token reached the API)
- MOS unresolved id 1968 (this discovery)
- Same pattern: `apps/evaluator/nlm_deep_research/gap_scanner.py::_send_telegram`
