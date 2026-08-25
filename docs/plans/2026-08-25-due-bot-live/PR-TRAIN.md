# The final PR train — shape measured, not counted

The DoD ends with "shipped dark on main via the final PR train". "117 commits" is the
wrong unit for planning it. What governs the train is the **diff**, and the diff is not
what the commit count suggests.

## Measured shape (against `origin/main`)

```
192 files changed, ~56k insertions, ~212 deletions
  180 files ADDED
   12 files MODIFIED
    0 files DELETED
```

Of the 12 modified, 5 are tests and 1 is `MANDATE.md`. **The entire risk surface of this
train is six production files:**

| file | why it changed | live? |
|---|---|---|
| `app/routers/whatsapp_chat.py` | signature verification hoisted to the shared verifier | **YES — live client bot** |
| `app/routers/instagram_chat.py` | HMAC verification added where there was none | **YES — live** |
| `app/core/config.py` | new dark flags, all defaulting off | additive |
| `services/agents/tool_authorizer.py` | the F5 scope no-op now denies | dark path |
| `services/integrations/messaging_identity_service.py` | raw-phone log redaction | live, log-only |
| `llm/codex_exec_client.py` | broker error taxonomy split | dark leg |

Everything else — `apps/team-bot/` entire, `services/client_bot/`, `services/team_bot_ingress/`,
the goldens, the ops docs — is **net-new and born off**. New code that nothing imports cannot
regress what it does not touch.

## What this means for how the train is cut

The Agent PR Contract's ~400-net-lines guidance says "where the nature of the work permits".
A new dark application does not decompose into 140 meaningful PRs; splitting it would produce
review units that are individually incoherent (half a state machine) and collectively no
easier to judge. The honest cut follows the risk, not the line count:

1. **The live-surface changes go FIRST and SEPARATELY, before the train.** They are the only
   part that can break something today, they benefit from being reviewable in isolation, and
   two of them are security fixes that should not wait for a product release. Two are already
   extracted and in flight as their own PRs to `main` (Instagram HMAC #4885; the raw-phone log
   sweep). The rest of the six follow the same rule.
2. **The dark bulk then lands as few, coherent PRs** — one per subsystem that can be read as
   one thing (client-bot engine + gate; team-bot runtime + registry + executor; ingress +
   failover; goldens + harness; ops/control-tower docs) — each stating in its body that
   everything it adds is off by default, and naming the flag that would turn it on.
3. **Nothing ships armed.** The switchboard (`OWNER-DECISION-PACKET.md`) stays the only
   place a thing gets turned on, and it stays the owner's.

## The gate this train must pass, and how it was learned

`PYTHONPATH=. python3 -m pytest backend/tests` — the **whole** suite, not
`backend/tests/duebot`.

This is written down because it was learned the expensive way on 2026-08-25: every run in
this mandate had been scoped to the code we wrote, and a full run then found **12 failures**,
all introduced by this branch, none ever seen — 11 in the live WhatsApp router's own test
file, 1 a Golden Rule #10 violation in the failover daemon. Both were fixed the same day.
Separately, relocating a PII helper was forced by a thirteenth failure in a CLI script's
`--help` contract, which no test of the code that moved could ever have caught.

A suite scoped to the code you wrote measures the code you wrote. Run the whole thing before
believing the train is green.
