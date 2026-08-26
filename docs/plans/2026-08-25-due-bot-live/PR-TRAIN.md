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

| file                                                  | why it changed                                        | live?                     |
| ----------------------------------------------------- | ----------------------------------------------------- | ------------------------- |
| `app/routers/whatsapp_chat.py`                        | signature verification hoisted to the shared verifier | **YES — live client bot** |
| `app/routers/instagram_chat.py`                       | HMAC verification added where there was none          | **YES — live**            |
| `app/core/config.py`                                  | new dark flags, all defaulting off                    | additive                  |
| `services/agents/tool_authorizer.py`                  | the F5 scope no-op now denies                         | dark path                 |
| `services/integrations/messaging_identity_service.py` | raw-phone log redaction                               | live, log-only            |
| `llm/codex_exec_client.py`                            | broker error taxonomy split                           | dark leg                  |

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

---

## The one row in that table whose label is wrong: `llm/codex_exec_client.py`

The risk table above marks it **"dark leg"**. That is true of the BRANCH and false of the
DEPLOYMENT, and the difference decides whether this train can be landed in pieces.

**Measured 2026-08-26**, while attempting to cherry-pick the item-13 daemon fix onto `main`
as an independent live-surface PR (which the mandate permits). The cherry-pick conflicted, and
the conflict was the warning:

```
origin/main      : 7 CodexExec* classes — no Quota, no PolicyBlocked, no Ambiguous
feature/due-bot  : 10 classes; CodexExecQuotaError at line 778
grep -c CodexExecQuotaError  on origin/main  ->  0
git diff --stat origin/main HEAD -- .../codex_exec_client.py
   ->  670 insertions, 111 deletions
```

So `wa_codex_daemon.py`'s new `except CodexExecQuotaError:` **cannot be promoted on its own**:
it catches a class today's production does not have. A cherry-pick to `main` raises ImportError
— or worse, gets "fixed" by hand by deleting the arm that carries the point.

**Why it is not merely a dependency but a three-way coupling.** `infra/home-fork/
declared-pairs.json` declares `/usr/local/lib/wa-codex-broker/backend/llm/codex_exec_client.py`
as a live pair, and its own note states that the **seat probe** payload imports
`backend.llm.codex_exec_client._AUTH_DEATH_RE` from that same runtime root: _"the two payloads
share one runtime root by design, so they cannot disagree about the auth-death regex without
both copies being re-provisioned together."_ Three payloads — daemon, client, probe — one root.

**The risk this creates, stated plainly.** The seat probe is the ONLY observability signal that
currently works end-to-end (auth death; verified green 2026-08-26: `verdict=ok`,
`login_status_rc=0`, `exec_rc=0`). A promotion that updates the daemon and the client but leaves
the probe on the old root, or that breaks the shared regex, **blinds the one signal that works
while trying to add the one that is missing.** That is a strictly worse state than today.

### What this means for landing

1. `codex_exec_client.py` is not free to land "early and quietly" as a dark leg. Whichever PR
   carries it is the PR that gates the daemon promotion.
2. The item-13 quota fix and rung 1b of the client ignition ladder are BOTH downstream of it —
   neither is blocked on more code, and neither is unblocked by a single deploy step.
3. After that PR merges, the promotion is **one action over three payloads**, with `cmp -s`
   byte-verification on all three (or `scripts/lint_home_fork.py`), not a per-file copy. A
   promotion nobody diffed is how HOME-fork drift starts — superscar #1.
4. Only then can the rung-1b harness be re-run to obtain its first real model output. Until
   then, its 20/20 green remains a statement about transport only.
