# OWNER DECISION PACKET — Tailscale Funnel evidence → Fly-forwarder pivot

> **Trigger**: production evidence accumulates against the F9 Tailscale Funnel ingress design
> for the team-bot Meta webhook — sustained availability/latency problems, or a webhook-disabled
> event from Meta traced to a Funnel-edge flap. Not a fixed metric threshold (Funnel isn't live
> in a tripwire sense yet — see `TRIPWIRES.md`'s closing note) — this packet is evidence-gated,
> triggered by an operator or an on-call session observing the pattern below, not by an
> automatic action.
>
> **This is a TEMPLATE.** Copy to `<date>-funnel-pivot-packet.md` and fill in every `[ ]` before
> sending to the owner. The recorded dissent below is Kimi K3's (research capture §7 / LENS 6
> §4) — it is not automatically the right call; it becomes actionable only once real evidence
> exists, per F9's own text: "Ship Funnel; keep the dissent alive as a one-day pivot, decision
> to the owner on evidence."

## Context (fill in from actual incidents/metrics, not from the dissent's predictions)

- Incident(s) observed: `[timestamps, what happened, how it was detected]`
- Was the webhook ever disabled by Meta (dashboard warning)? `[y/n, when, how long to
re-enable]`
- `webhook_ack_latency_seconds` p95 during the incident(s): `[n ms]`
- Correlate with Tailscale status/incident page for the affected window: `[link/note]`
- How many Mini reboots/sleep events occurred in the measurement period, and did any coincide
  with a Meta retry storm: `[n, correlation y/n]`
- Current team-bot promotion stage at the time of the incident: `[ingress-only | shadow | owner
replies | staff read | R2 | R3 | auto-failover]`

## What the recorded dissent argued (for reference, not as evidence)

Kimi K3 (research §7 / LENS 6 §4): Funnel terminates TLS on Tailscale's edge — a PII-sovereignty
inconsistency for a design whose whole reason for being local is UU PDP; Meta's webhook-disabled
threshold makes a Tailscale relay incident look identical to "your endpoint is flapping"; Funnel
gives no access logs to correlate against a Meta "delivery failed" report; a reboot/sleep gap is
a retry-storm risk. The proposed alternative: keep the public front door on Fly (already public,
monitored, restart-managed) as a **dumb, HMAC-verified forwarder** — ack Meta 200 immediately,
forward over the tailnet with a Redis/PG-backed retry queue reusing the existing
`inbound_webhooks` ack-first pattern (migration 145). Mini down → queue holds, Meta already
acked, no retry storm, no disabled webhook, Fly logs available for free.

## Options

1. **Hold on Funnel.** No migration cost. Correct if the incident(s) above were a one-off
   Tailscale blip, not a pattern — re-evaluate at the next incident rather than pivoting on one
   data point.
2. **Pivot to the Fly-forwarder-over-tailnet design** (Kimi's proposal, ~100 lines reusing
   existing HMAC-verify + `inbound_webhooks` ack-first code per the dissent). Cost: one new
   small Fly app or route, one deploy, re-pointing the Meta webhook URL once (a one-time GUI
   step, operator[gui]-class). TLS terminates on Fly instead of Tailscale's edge — resolves the
   PII-sovereignty objection.
3. **Cheap always-on VPS running only Caddy+forwarder** — the dissent's own fallback if Fly must
   be fully out of the team-bot path. Strictly worse than option 2 per the dissent's own words;
   include only if the owner has a specific reason to keep Fly untouched.

## Recommendation

`[one option, one sentence why, referencing the incident evidence above]`

## Reversal

The pivot (option 2) is itself reversible: the Fly forwarder is a dumb relay with no state of
its own beyond the retry queue, so reverting to direct Funnel is a webhook-URL re-point, same
cost as the forward pivot. Nothing about team-bot's internal logic (identity, confirmation,
tools) changes either way — this decision is scoped entirely to the ingress transport.
