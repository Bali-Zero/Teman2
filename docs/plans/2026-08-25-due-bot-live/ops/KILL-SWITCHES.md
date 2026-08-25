# KILL-SWITCHES.md — every off switch, in one place (F11, lane B7)

> "A kill switch nobody can find at 3am is not a kill switch." This is that one place. The
> machine-readable source of truth is
> `apps/backend-rag/backend/services/client_bot/kill_switches.py` — `test_kill_switches.py`
> keeps this table from drifting away from it (every `env_var` below must appear in the
> registry, and vice versa). If the two ever disagree, the Python module is right.
>
> **`status` is honest, not aspirational**: `wired` means a named source file reads this env
> var TODAY; `planned` means the name and default are agreed but no lane has landed the read
> yet. Check the column before assuming a flag does anything — this is superscar family #2
> ("esiste != armato") applied to kill switches themselves.

## The 5 F11 planes

Every switch below attaches to exactly one of the five side-effect planes F11 names:
`client_send` · `broker_generation` · `team_replies` · `team_mutations` · `failover_automation`.

## Client bot — per-surface send gates (plane: `client_send`)

| Env var                          | Default | Scope       | Effect when OFF                                     | Owning lane | Status  |
| -------------------------------- | ------- | ----------- | --------------------------------------------------- | ----------- | ------- |
| `CLIENT_BOT_WA_SEND_ENABLED`     | `false` | WhatsApp    | Gate evaluated + logged; no Meta send. Shadow mode. | B1          | planned |
| `CLIENT_BOT_IG_SEND_ENABLED`     | `false` | Instagram   | Gate evaluated; no IG DM sent.                      | B1          | planned |
| `CLIENT_BOT_PORTAL_SEND_ENABLED` | `false` | Portal      | Gate evaluated; no answer returned to session.      | B1          | planned |
| `CLIENT_BOT_KBLI_SEND_ENABLED`   | `false` | KBLI widget | Gate evaluated; no classification returned.         | B1          | planned |

**To flip one surface live**: set the single env var to `true` for that surface only. **To kill
one surface at 3am**: set it back to `false` — the gate keeps evaluating and logging (nothing
about ingestion/audit/durability depends on this flag), only the outbound send stops.

## Codex broker leg (plane: `broker_generation`)

| Env var                           | Default | Scope                      | Effect when OFF                                                                                                                                             | Owning lane | Status  |
| --------------------------------- | ------- | -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | ------- |
| `CLIENT_BOT_CODEX_BROKER_ENABLED` | `false` | Global, all seats/surfaces | `wa_broker` never offers `client_answer_v1` jobs; every turn routes to Gemini only. **This is the flag `codex_secret_canary_hits_total>0` must auto-flip.** | B2          | planned |

A second entry, `WA_CODEX_SEAT_<n>_BREAKER_LATCHED`, exists for completeness but is **not an
operator-set env var** — it names the existing dark implementation's per-seat breaker
(auth-death / 3-consecutive-failure latch), which is **runtime-latched** by the daemon itself.
See `wa_codex_daemon.py`'s `"wa-codex-daemon: codex seat AUTH DEATH detected"` log line.
Clearing it requires an operator `codex login` (owner switchboard item 4), never a flag flip.

## Team bot (planes: `team_replies`, `team_mutations`, `failover_automation`)

`apps/team-bot/` does not exist yet (B3's file ownership) — every row below is `planned`.

| Env var                            | Default | Plane               | Effect when OFF                                                                                                                                              | Owning lane | Status  |
| ---------------------------------- | ------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------- | ------- |
| `TEAM_BOT_INGRESS_ENABLED`         | `false` | team_replies        | Webhook not subscribed; zero inbound team-bot traffic accepted. First promotion rung.                                                                        | B3          | planned |
| `TEAM_BOT_REPLY_ENABLED`           | `false` | team_replies        | Inbound logged + audited; no model reply sent.                                                                                                               | B3          | planned |
| `TEAM_BOT_READ_TOOLS_ENABLED`      | `false` | team_replies        | R0/R1 read tools not exposed to the model.                                                                                                                   | B3          | planned |
| `TEAM_BOT_MULTISTEP_READS_ENABLED` | `false` | team_replies        | Read/search chains capped at exactly ONE step per turn (today's exact behavior). See "Multi-step reads" below — mutations are never affected by this switch. | B3          | planned |
| `TEAM_BOT_MUTATIONS_ENABLED`       | `false` | team_mutations      | R2/R3 tools not registered at all. **The single switch that can stop a write to production CRM — the highest-severity row in this table.**                   | B3          | planned |
| `TEAM_BOT_FAILOVER_AUTO_ENABLED`   | `false` | failover_automation | `team-bot-failoverd` never auto-issues a WABA callback override. Stays dark until a staging-WABA retry drill passes (F9/Kimi dissent — see `TRIPWIRES.md`).  | B5          | planned |

**Multi-step reads** (owner directive #1 §2, 2026-08-25 — amends F4/F5): "one tool per turn"
stays unconditional for **mutations** (always confirmed, never gated by this switch) but is
relaxed for reads/searches only once `TEAM_BOT_MULTISTEP_READS_ENABLED` flips true — at that
point the companion (non-boolean, not itself a kill switch) env var `TEAM_BOT_MAX_READ_STEPS`
(default 8) sets the per-turn read/search step budget. While the switch is false,
`TEAM_BOT_MAX_READ_STEPS` is read but has no effect —
`apps/team-bot/team_bot/flags.py::max_read_steps()` always returns 1 regardless of its value,
so a stray or leftover numeric setting can never silently widen the chain on its own. The
structural type that carries a chain (`ReadPlan`, `apps/team-bot/team_bot/loop/turn_plan.py`)
enforces an absolute ceiling of 20 steps independent of this switch entirely.

**Promotion order** (owner switchboard item 7, verbatim from MANDATE.md):
`ingress/audit → shadow intent/tool selection → fixed replies to owner → allowlisted staff read
tools → R2 writes → R3 practice open → automatic failover`. Each rung is one flag; rolling back
is one flag change per plane, and disabling replies/mutations must never disable webhook
receipt, durable audit, or human handoff (go-live checklist, research §5.5).

## How to verify a flip actually took effect

Never trust the flag alone — verify the effect:

- **Client-send flags**: send (or replay) a probe message on that surface; confirm
  `client_bot_gate_verdict_total` incremented but no outbound Meta/portal call fired in the
  adapter's logs.
- **`CLIENT_BOT_CODEX_BROKER_ENABLED`**: confirm `codex_jobs_total` stops incrementing for that
  seat within one polling interval of flipping to `false`.
- **Team-bot flags** (once B3 lands): confirm the corresponding tool/mutation attempt returns
  403/tool-not-found and the relevant counter (`team_bot_mutation_total`,
  `team_bot_tool_call_total`) stays flat.
- **`TEAM_BOT_FAILOVER_AUTO_ENABLED`**: run the synthetic failover drill (research §5.4);
  confirm zero callback-override calls in the fake Graph API log while `false`.

## Full per-switch detail

See `apps/backend-rag/backend/services/client_bot/kill_switches.py` — each entry also carries a
`verify_command` field with the exact grep/curl/log-line to run, which this document summarizes
rather than duplicates.
