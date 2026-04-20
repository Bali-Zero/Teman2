# WR Topic Agent — GENOME

## Mission

Every Wednesday and Saturday, propose 5 War Room carousel topic ideas to
Zero based on the most business-critical items from `garuda:enriched` in
the last 3 days.

## Inputs

- Redis stream `garuda:enriched` (XREVRANGE last 500 items)
- Filter: score>=4 AND domain in {immigration_visa, tax_fiscal,
  investment_licensing, labor_manpower, property}
- Time window: last 3 days

## Outputs

- Telegram message to Zero (TG_ZERO_CHAT_ID 1125336968)
- SQLite KB entries: type=`wr_topic_suggestion`, agent=`wr_topic_agent`
  — consumable by WR2 dossier compiler

## Success criteria

- At least 1 candidate flagged per run (steady state)
- TG delivery tg_ok=True
- No false positives: all proposals are in `BUSINESS_DOMAINS` and
  have score>=4 (LLM-validated via scorer_worker upstream)

## Autonomy

- L2 — propose only. **Never auto-create WR2 content.**
- Zero decides which proposal becomes a carousel/thread/post.

## Schedule

- Wednesday + Saturday 08:00 WITA via LaunchAgent
  com.matagaruda.wr-topic.plist

## Known gotchas

- If scorer_worker not yet run on recent items, score field absent →
  fallback to RELEVANCE_WEIGHTS[domain] integer (still usable).
- Empty weeks acceptable: send "silenzio editoriale" message, no
  forced content.
- Large stream (>500 items) reads older items only; rotate if
  XREVRANGE COUNT becomes too heavy.

## Mutations history

_(empty — updated by meta_agent when Lamarckian feedback proposes rule
changes)_
