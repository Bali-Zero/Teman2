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
   promotion nobody diffed is how HOME-fork drift starts — superscar #1. **But "one action" is
   not enough on its own, and the canonical installer does not provide it — see the subsection
   below before running anything.**
4. Only then can the rung-1b harness be re-run to obtain its first real model output. Until
   then, its 20/20 green remains a statement about transport only.

### The promotion is ordered, and `provision_zantara_codex.sh` does not honour that order

Added 2026-08-26 after an adversarial cross-family pass on PR #5028, then re-verified by hand
against the tree at that PR's head (`9ab6606c8`). Point 3 above said "one action over three
payloads" and stopped there. That is right about _atomicity_ and silent about _sequence_, and
sequence is the part that bites.

**The constraint.** `wa_codex_daemon.py` imports `CodexExecQuotaError` (line 78, and catches it
at 511). Measured on `origin/main`: `grep -c "class CodexExecQuotaError"` on the production
client returns **0**. So a daemon that restarts against the old client raises `ImportError`
before it polls or touches the gauge — and under `KeepAlive` that is a restart loop, not a
visible crash. The client is not merely coupled to the daemon; it must be **in place before the
daemon process restarts**. Copy order among the files is irrelevant; the restart is the fence.

**Why the installer cannot be used as-is for this promotion.** Read in file order:

| line    | action                                                                    |
| ------- | ------------------------------------------------------------------------- |
| 142     | installs `codex_exec_client.py`                                           |
| 144-145 | installs `wa_codex_daemon.py`                                             |
| ~158    | `pip install httpx` — fallible, rc captured into `PIP_RC`                 |
| ~249    | `launchctl bootstrap` — **the daemon starts here**                        |
| ~274    | installs `wa_codex_seat_probe.py` — _after_ the daemon is already running |

The probe is refreshed last, after a fallible step and after the daemon has been restarted. Any
failure in between leaves **new daemon + new client + old, quota-blind probe** running. That is
precisely the state this document already names as strictly worse than today: it blinds the one
observability signal that works end-to-end while trying to add the one that is missing.

**The promotion procedure, corrected.**

1. Copy **all three** payloads into the runtime root first — client, daemon, probe — with the
   daemon still running on its old code. Nothing has restarted yet, so nothing can be caught
   half-updated.
2. `cmp -s` each of the three against its repo source, plus `scripts/lint_home_fork.py --check`.
   Abort on any mismatch — do not restart into an unverified tree.
3. Only then restart the daemon (`bootout` + `bootstrap`, not `kickstart -k`: the installer's
   own log at line ~246 records that `kickstart -k` does **not** re-read the plist).
4. Re-run the seat probe and confirm it is still green AND that it reports its primary import,
   not its fallback. A probe on fallback copies cannot fabricate a false `ok` — `VERDICT_OK`
   requires `login_rc == 0 AND exec_rc == 0`, and any nonzero rc falls to `other_failure`
   whether or not a pattern matched. What drifted fallback copies actually do is DOWNGRADE a
   real `auth_death` or `quota_exhausted` into the weaker `other_failure` bucket: the alarm
   still fires, with the wrong diagnosis, so the sentinel prescribes the wrong remedy. Accepting
   `ok` alone is therefore not "closing the loop on nothing" — it is accepting an unknown
   diagnosis quality, which is the thing to close.

**Step 4 is not executable today — measured 2026-08-26.** Read live from Pro,
`/usr/local/var/wa-codex-broker/seat-status.json` carries exactly four keys — `verdict`,
`login_status_rc`, `exec_rc`, `checked_at` — and none of them names how the probe resolved its
detectors. The module computes `_AUTH_DEATH_SOURCE` (`"import"` vs `"fallback-copy"`) and then
only writes it to the log. So the status file cannot distinguish a healthy probe from a blind
one, and the instruction above asks a future session to prove something against a file that
cannot say it.

Until the probe publishes that field, step 4 has to be satisfied out of band: load the deployed
probe module and read `_AUTH_DEATH_SOURCE` directly, rather than reading the status JSON. The
field has been requested as part of the PR that carries the probe; when it lands, delete this
paragraph and step 4 becomes a one-line check again.

A worry raised while writing this and then measured away, recorded so nobody re-raises it: a
daemon left import-dead by a botched promotion does NOT hide behind the probe's `ok`. The seat
probe watches the SEAT; daemon liveness is watched separately, and `scripts/wa_codex_seat_sentinel.py`
lines 257-258 already read `broker_last_seen_at`, `breaker_state` and `consecutive_failures` off
`wa_broker_gauge`, with line 294 handling the NULL "daemon never seen" case. The import that
would fail is at module level (`wa_codex_daemon.py` lines 70-81), so the daemon dies before it
can ever refresh the gauge, the row goes stale, and the sentinel sees it. Nothing needs building.

For the record, the same read confirmed the promotion constraint against the LIVE tree rather
than against `origin/main`: `grep -c "class CodexExecQuotaError"` on
`/usr/local/lib/wa-codex-broker/backend/llm/codex_exec_client.py` returns **0**. Production's
client really does not have the class the new daemon imports.

A note on the ordering the refuter proposed (`probe → client → daemon`): the probe-first half is
not useful. The probe imports its private symbols from the client and swallows a miss in a broad
`except ImportError`, so a probe promoted ahead of the client silently runs on fallback copies
and reports green. Promoting it first buys observability that is not actually observing. What
matters is only that **everything is on disk before the daemon restarts**.
