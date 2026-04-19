# Regulation Alert Agent — GENOME

## Mission
Quasi-real-time forwarder (cron every 30 min) from `garuda:alerts` to
Zero's Telegram. Each alert produced upstream (scorer ≥ SCORE_SIGNAL,
contradiction_worker, semantic_diff_worker) reaches Zero within ~30 min.

## Inputs
- Redis stream `garuda:alerts` via consumer group `reg_alert`

## Outputs
- Telegram message to Zero (chat `1125336968`)
- KB entry type `alert_forwarded` (audit trail) or `case_not_resolved`
  (on TG send failure)

## Success criteria
- Every alert ACKed — no PEL backup even on TG outage
- Zero receives alert within 30 min of upstream publish
- No duplicate forwarding: single consumer name `reg_alert-1`

## Known gotchas
- We ACK even on TG send failure. Rationale: duplicate Telegram spam is
  worse than a dropped alert, because the alert is already in the KB
  audit trail (`case_not_resolved` entry) and in the stream history
  (recoverable via XRANGE).
- Upstream schema: scorer emits `title/url/source/score/topic/reason/alert_time`.
  Contradiction/semantic_diff workers (W2 vertical) should emit similar
  shape — see `format_alert()` for all recognised field aliases
  (`topic|domain`, `score|weighted_score`, `reason|motivo`, `alert_kind|kind`).

## Mutations history
_(meta_agent appends here)_
