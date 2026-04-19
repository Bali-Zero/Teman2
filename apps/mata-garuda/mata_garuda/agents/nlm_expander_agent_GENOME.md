# NLM Expander Agent (L2) — GENOME

## Mission
Weekly scan of `garuda:enriched` to propose new NLM notebooks for
high-volume unmapped domains, and flag existing notebooks that have
gone stale (no feed in 30+ days). **L2 autonomy** — proposes via
Telegram, does NOT create notebooks autonomously.

## Inputs
- Redis stream `garuda:enriched` (XREVRANGE, last ~2000 items → 30d window)
- KB `nlm_fed` entries (freshness signal)
- `config.NLM_DOMAIN_ROUTING` (ground truth for what IS mapped)

## Outputs
- Telegram message to Zero with proposals + stale flags
- KB entry type `proposal`

## Success criteria
- If a domain has >50 items/30d AND is NOT in NLM_DOMAIN_ROUTING →
  proposal surfaces in next weekly TG
- If a configured NB hasn't been fed in 30+ days → stale flag
- NEVER creates a notebook (L2 hard boundary)

## Known gotchas
- `L2` in the agent name is intentional — meta_agent uses it to enforce
  the no-autonomous-creation rule.
- Thresholds (50 items/30d, 30d stale) are defaults — can be overridden
  via the `run_nlm_expander(proposal_threshold=…)` arg, but don't lower
  below 20 without talking to Zero (noise risk).
- `find_stale_notebooks` is conservative: if there's NEVER been a
  `nlm_fed` entry (e.g. brand-new KB), ALL notebooks flag as stale.
  That's intentional — it surfaces the fact that feeding isn't happening.

## Mutations history
_(meta_agent appends here)_
