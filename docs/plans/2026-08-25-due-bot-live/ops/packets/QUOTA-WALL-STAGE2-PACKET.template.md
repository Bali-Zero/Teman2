# OWNER DECISION PACKET — Codex leg quota wall → stage 2 (metered key)

> **Trigger**: tripwire `codex.quota_fallback_ratio` fired — `codex_quota_fallback_total /
codex_eligible_requests_total` exceeded 5% over 7 days (with >= 50 eligible requests), OR 2
> quota-exhausted windows occurred within 7 days (`tripwires.py`, F3/Sol §2.5).
>
> **This is a TEMPLATE.** Nothing below is filled in until the trigger actually fires — do not
> read this file as a live packet. Whoever/whatever fires the tripwire copies this file to
> `<date>-quota-wall-packet.md` in this same directory and fills in every `[ ]` field with a
> measured number before sending it to the owner. An unfilled template is not a decision packet.

## Context (fill in from the metrics, not from memory)

- Measurement window: `[start] → [end]`
- `codex_quota_fallback_total`: `[n]`
- `codex_eligible_requests_total`: `[n]`
- Ratio: `[n]%`
- Quota-exhausted windows in the last 7 days: `[n]` (list timestamps)
- Which seat(s) hit the wall: `[seat ids]`
- Current active-traffic promotion stage for the codex leg: `[shadow | owner-only | 5% | 25% | per-surface]`
- Gemini-leg health during the same window (it is the thing absorbing the fallback traffic —
  confirm it isn't ALSO under strain): `fallback_provider_failure_total / ..._requests_total` =
  `[n]%`

## What this means

The Codex subscription seats (Max-plan/ChatGPT-Pro OAuth quota, per CLAUDE.md's cost-constraint
hard rule) are hitting their capacity ceiling at the current traffic share. This is not a bug —
it is the subscription-capacity model (F3) doing exactly what a fixed-cost quota does under
load. The options are the ones the mandate always intended this decision to be between; nothing
here proposes silently provisioning a metered key (explicitly forbidden by the tripwire's own
automatic action — "never auto-provision a key").

## Options (recommend one, cost each honestly)

1. **Hold at current promotion stage.** No cost. Fallback continues to absorb overflow onto
   Gemini. Cost: whatever `client_bot_codex_route_seconds` degradation the fallback causes for
   users who would have gotten the (possibly faster/better) Codex answer.
2. **Add another Codex seat/account** (if one of the 5 MAX x20 slots per
   `~/.claude/CLAUDE.md`'s fleet topology has headroom, or a dedicated new subscription). Cost:
   another $X/mo subscription seat, operator OAuth login effort (owner switchboard item 4-class
   work), no per-token spend.
3. **Provision a metered API key for the leg** (stage 2, explicitly an owner decision per F3 —
   "A metered key is stage 2, owner decision, triggered only by measured quota walls"). Cost:
   per-token spend, proportional to `[measured overflow volume]` above. This is the option the
   mandate names as requiring this packet in the first place.
4. **Narrow the promotion stage back down** (e.g. 25% → 5%, or 5% → owner-only) to bring
   `codex_eligible_requests_total` back under the capacity the current seats can serve without
   quota walls. Cost: less Codex-leg exposure, more fallback traffic on Gemini.

## Recommendation

`[one option, one sentence why, referencing the numbers above — not a general argument]`

## Reversal

Whichever option the owner picks, reversal is: `TEAM_BOT`/`CLIENT_BOT_CODEX_BROKER_ENABLED`
stays untouched by this decision (it's a leg-capacity question, not a leg-safety one) — the
promotion stage itself is a single value in the provider-registry routing config, so stepping
back down one rung is always available regardless of which option was chosen.
