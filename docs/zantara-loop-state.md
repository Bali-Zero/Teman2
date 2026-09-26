# Zantara WA loop — state ledger

> Read at Step 0 of every `/bot` loop iteration, updated at Step 6. Numbers are stamped with the
> day they were measured; re-measure before trusting any of them.

## Instrument corrections (read before the KPI panel)

- **T1-T5 must be measured on Pro, not on Fly.** Since the 2026-05-24 wa-mirror local-only
  cutover (Symbiosis Law 2), `whatsapp_message_context`, `whatsapp_team_sessions`,
  `team_promises` and `action_queue` on Fly are frozen at 2026-05-25 by design. The live mirror
  writes to Pro `nuzantara_dev` (`ssh pro`, `psql -h 127.0.0.1 -d nuzantara_dev`). No
  backend-rag code reads Fly `whatsapp_team_sessions` (only migrations reference it).
- **Per-line mirror liveness has a dedicated organ**: `scripts/wa_session_liveness.py` (Pro cron
  08:15 daily, 72h threshold, Telegram alert). Read its log
  (`~/logs/cron-tmp/wa-session-liveness.log` on Pro) instead of `whatsapp_team_sessions.status`,
  which churns through janitor-ghost-cleanup rows on Pro as well.
- **F2 must exclude `superseded_by_coalescing`.** It is burst dedup, not a send attempt: the row
  never reaches Meta. A real delivery failure has a `meta_message_id` or a Meta error.
- **Broker liveness is `wa_broker_gauge.broker_last_seen_at` advancing** (the daemon polls every
  2s), never `breaker_state` — the breaker stays `closed` while the daemon is paused.

## KPI: served_by (migration 322, closes the F3/Iteration-2 gap below)

`served_by` is `CodexLegResult.served_by` verbatim, persisted in the SAME fenced terminal write
as `abstained_at`/`evidence_score` (`wa_outbox_worker.py`). Before this column, the
`support_abstain` rate (Iteration 2 "Measured, not fixed") was only visible by hashing message
bodies — this makes it a plain `GROUP BY`. Scoped to `needs_generation` rows only (a human send
never calls the codex leg, so it correctly stays NULL — including it in the denominator would
undercount the real support_abstain rate):

```sql
SELECT served_by, count(*) FROM wa_outbox WHERE needs_generation AND status = 'done' AND created_at > GREATEST(now()-interval '7 days', '2026-09-26 12:53:06+00') GROUP BY 1 ORDER BY 2 DESC;
```

The `GREATEST` floor is the end of the deploy that shipped the column (run 36242358705,
2026-09-26T12:53:06Z). Inside `needs_generation AND status = 'done'` a `NULL` can only be a row
completed BEFORE migration 322 was live — a failed generation never reaches `status = 'done'` —
so without the floor the NULL bucket is historical for the first 7 days and inflates the
denominator. From 2026-10-03 the floor is inert. A `NULL` that appears above the floor is a
defect in the terminal write, not a KPI bucket.
`apps/backend-rag/fly.toml`'s `release_command` (`migrate apply-all && schema_audit`) runs on the
NEW image before Fly replaces any machine and fails the release outright on a pending migration,
so there is no deploy-window gap: the column exists before this worker code is ever live (verified
against real deploy run logs for migrations 318/320/321). The closed vocabulary otherwise is
`codex`, `support_abstain`, `scripted_media_ack`, `scripted_greeting`, `scripted_human_handoff`,
`scripted_identity`.

## Iteration 1 — 2026-09-25 (M5)

| Gate    | Re-measured                                                                                                                                                                                                                                                                                                                            | Verdict                                  |
| ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| T1      | Pro mirror alive: 1,641 rows/24h, 7,470/7d. Lines: 4/7 OK (Ari, Asya, Krisna, Surya); Adit `401 logged_out` (~22 d), Damar `401 logged_out` (~43 d), Vino no-link (~48 d)                                                                                                                                                              | BLOCKED — QR re-pair, operator[physical] |
| T2      | Watchdog exists and alerts daily by name; the three stale lines have been alerted every day with no action                                                                                                                                                                                                                             | organ OK, human loop open                |
| F2      | 14 d: 7 `failed` outbound = 4 `superseded_by_coalescing` (benign) + 2 `standing_no_customer_message` on image-only inbound (client re-sent the photo, got silence, nobody notified) + 1 `broker_absent` (apology sent). Real Meta send failures: 0 of 33 sent                                                                          | re-scoped, see below                     |
| F2-live | **Outage in progress at measurement time**: Homebrew codex on Pro upgraded to 0.156.1 at 2026-09-25 01:07 WITA; the broker daemon (alive, pid 565) stopped claiming on the version-pin mismatch; gauge frozen at 2026-09-24T17:10:32Z; seat sentinel RED `daemon_silent` from 01:30 WITA. Every inbound ends `broker_absent` → apology | BLOCKED — pin bump, operator[credential] |
| F1      | `ack_sent_at` NULL on all rows in 14 d                                                                                                                                                                                                                                                                                                 | not started                              |
| F3      | mean `evidence_score` 0.30 on 21 codex `done` rows, 0.08 on 9 route-less `done` rows                                                                                                                                                                                                                                                   | not started                              |

### Decisions / actions for the owner

1. **Restore the bot (urgent)** — DONE. The owner bumped the pin to 0.156.1 and kickstarted the
   daemon; the gauge is advancing again as of 2026-09-24T18:07Z, after an outage of ~57 min.
2. **QR re-pair** for Adit and Damar (logged out), and decide whether Vino's line is still wanted.

### Next gap

F2 structural half: image-only inbound gets `standing_no_customer_message` → five retries →
silence with no human notified. Then the pin-drift class: the daemon shares the Homebrew codex
with every agent seat, so any seat upgrade silently stops the bot.

## Iteration 2 — 2026-09-25 (M5)

| Gate            | Change                                                                                                                                                                                                                   | Proof                                                                                                      |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| F2-live         | Broker pin-drift outage cured by the owner (pin → 0.156.1, kickstart)                                                                                                                                                    | `wa_broker_gauge.broker_last_seen_at` advancing (18:07:04Z → 18:07:15Z)                                    |
| F2-alarm        | Seat sentinel names a probable version-pin pause and carries the cure (#7293), with `ps` in the C locale (#7298) — Pro's Italian locale had made it inert                                                                | Real readers run on Pro: daemon start parsed, package version/mtime read; guilt simulation prints the cure |
| F2-media        | A caption-less attachment gets a scripted ack (`served_by=scripted_media_ack`) + best-effort human notification instead of 5 silent retries (#7296). Copy claims nothing it cannot verify and says a caption is not read | Deployed 2026-09-24T19:54Z, code grep in the rag container; first real event not yet observed              |
| F1 prerequisite | Language detector: `auto` on real inbound 33.5% → 4.0%, 0 confident flips on 278 real texts, out-of-vocabulary languages (es/fr/de/pt/nl/tl/ms) abstain (#7299)                                                          | Deployed 2026-09-24T20:37Z                                                                                 |
| F1              | Concierge ack armed: `WA_OUTBOX_MANNERS_ENABLED=true`                                                                                                                                                                    | `printenv` = true in the rag machine, `/health` 200, broker gauge fresh; first real ack not yet observed   |

Red team F1: constant text in en/id/it/ru/fr (uk → en); fenced once per outbox row via `ack_sent_at`; throttled 1/phone/120 s in-process; skipped under 25 chars, trivial text, a closed 24h window, human takeover. Rollback: `fly secrets unset WA_OUTBOX_MANNERS_ENABLED -a nuzantara-rag`.

### Measured, not fixed (inputs for the next gaps)

- **F3 is invisible in SQL**: in 30 days, 23 of ~31 questions that reached retrieval got the fixed `support_abstain` stub (EN ×17, ID ×6). `abstained_at` stays NULL on them by design (D6/B2.3b). `served_by` is now persisted (migration 322, see the KPI block above) — the `GROUP BY` there replaces the body-hash count from here on. The lever is KB coverage (F9), not the gate.
- **F7 holds**: 0 inbound answered twice in 30 days. 5 pairs of identical stubs within 2 minutes are one stub per inbound in a burst (UX, not a duplicate send).
- **T3-T7 have no living organ**: `team_promises`, `action_queue`, `whatsapp_practice_candidates` exist only on Fly, unfed since the 2026-05-24 cutover. On Pro, `wa_dashboard_outbound_queue`, `wa_dashboard_threads` and 14-day `whatsapp_operator_actions` are all 0.
- **Open defects found by review** (own PRs): ingestion stores `body` only for `type=='text'`, so captions are lost; `notify_human_handoff` returns True even when the email failed silently (the B2.5-2 handoff copy depends on it); the Homebrew codex is shared between the broker daemon and every agent seat (dedicated pinned binary = sudo provisioning).

### Decisions for the owner

1. QR re-pair: Adit and Damar (401 logged_out); Vino's line — keep or retire?
2. T3-T7: rebuild the team agent Pro-local (Law 2), or retire those gates?
3. Dedicated pinned codex binary for the broker daemon (sudo provisioning), to end the pin-drift class.

### Next gap

F9/F3 — the support_abstain rate (~74%) is the biggest client-facing gap now; start by persisting `served_by` so it is countable, then map the abstained topics to KB coverage.
