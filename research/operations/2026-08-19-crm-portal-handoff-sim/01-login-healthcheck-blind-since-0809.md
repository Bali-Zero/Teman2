---
date: 2026-08-19
domain: compliance
client_case: none
sources:
  - ~/scripts/login-healthcheck.sh (read in full this run)
  - ~/logs/login-healthcheck.log (5941 lines, counted this run)
  - apps/backend-rag/backend/app/routers/auth.py (login handler, read this run)
  - shared/escalations_pro.jsonl (parsed this run)
adversarial_review: codex
---

# The login guard for kita has been failing for ~10 days, and all 61 of its alarms died at the gateway

**Severity: the highest thing found in this simulation.** Not because the login is broken — it is
not — but because the organ that watches it is dead, mute, and invisible to every lint that exists
to catch exactly this.

## What is true, measured

`~/logs/login-healthcheck.log`, counted this run:

| Signal | Count |
|---|---|
| `status=ok` | **11** — all on 08-19, after the cure |
| `status=fail` (true runs) | 1540 |
| `ALERT: login_fail` (alarm decided) | 61 |
| `telegram: missing creds` (alarm died) | **61** |
| `telegram: post failed` | 0 |

Failures per day, counted on the `result:` line only: **162** (08-14, partial), **286**, **287**,
**282**, **285**, **238** (08-19, partial). Every full day sits just under **288**, the ceiling of a
five-minute cron — which is the shape a permanently-failing probe should have.

An earlier version of this table read `2940` and gave 572-574 failures a day. That came from
`grep -c status=fail`, and every failed run writes the string twice: once on its `result:` line and
once on its `=== login-healthcheck end (status=fail, exit=1) ===` line, at the same timestamp. The
figure was therefore exactly double, and **the error was visible without any log access at all**:
572 runs a day is impossible for a job that fires every five minutes. A number that breaks its own
physical ceiling should never have survived into a table. The alarm counts (61 / 61) were checked
separately and are NOT doubled — those lines appear once per event.

The successes are today's: the probe was cured mid-investigation, which is why `status=ok` is no
longer zero. Last failure **2026-08-19 14:01:06**.
The log's very first line already reads `prev=fail`, so the failure predates the log; the matching
escalations in `shared/escalations_pro.jsonl` (86 of them, all `job: login_healthcheck`) start at
epoch 1786262903 ≈ **2026-08-09**.

Scheduled by `com.nuzantara.login-healthcheck.plist` (launchd), every 5 minutes.

## Failure 1 — the probe wears the wrong persona

`~/scripts/login-healthcheck.sh:10-11`, verbatim:

> *Uses the dedicated healthcheck@balizero.com account (role=client, lowest privilege) — credentials
> in ~/.nuzantara-secrets.env.*

The probe's reported symptom is `http=403 has_token=false`. The login handler
(`apps/backend-rag/backend/app/routers/auth.py`) contains **exactly one** 403 path. The "exactly
one 403" half is what the argument needs and it holds; an earlier draft added "every other rejection
is a 401", which is false — the same handler also returns 429 (rate limit), 500 and 503:

```python
if user["role"] == "client" and (
    not user.get("portal_access") or user.get("linked_client_id") is None
):
    ...
    raise HTTPException(status_code=403, detail="Portal access is not available for this account")
```

So a 403 from this endpoint means one thing and only one thing: **the account is `role=client` and
is not portal-eligible** — no `portal_access`, or no `linked_client_id`. A synthetic monitoring
account has no CRM client row to link to, so it cannot satisfy that condition.

**The source of the cause.** In April a guard was built after an incident where `/health` returned
200 while `/api/auth/login` returned 500. Its own header states the lesson: *"the metric users care
about is 'can I log in', not 'does /health respond'."* It deliberately chose a **client**-role
account for least privilege. Later, the portal identity-join requirement landed — a correct and
desirable tightening: a client login must resolve to a real CRM client before a portal session
exists. That policy is scoped to the **client** persona. The probe watches the **operator** domain
(`kita.balizero.com`) but authenticates as a **client**. A change to one persona silently
decommissioned the guard on the other, and nothing in the system could connect the two: the
security change had no way to know a monitor depended on a non-portal client account still being
able to log in.

The probe used one persona as a proxy for the other. When the proxy's meaning changed, the
measurement died while the alarm kept firing.

## Failure 2 — and the alarm was never connected

This is the worse half, because Failure 1 alone would have been noticed on day one.

`login-healthcheck.sh:40-48`:

```bash
tg_alert() {
    [[ -z "$TELEGRAM_BOT_TOKEN" || -z "$TELEGRAM_CHAT_ID" ]] && { log "telegram: missing creds"; return 1; }
    ...
}
```

The two-consecutive-failure logic worked perfectly: it decided to alert **61 times**. All 61 landed
on `telegram: missing creds` — under launchd, at least one of the two variables resolves empty. The
alarm never left the machine. `telegram: post failed` is 0, so this is not a delivery failure; the
message was never attempted.

Line 28 compounds it:

```bash
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-${BALIZEROBOT_TOKEN:-}}"
```

The fallback is `BALIZEROBOT_TOKEN` — the **decommissioned** `@Balizerobot`, whose token was
published on the default branch of a public repo, cannot be revoked, and whose destination chat
belongs to an account nobody can open (see the fleet notes on the dead pair). So the recovery path,
had it resolved, would have delivered into a mailbox with no reader. Both doors are shut.

## Failure 3 — nothing could have caught it

`login-healthcheck.sh` existed **only** in `$HOME/scripts/` when this was written. There was no copy
in the repository (`find` that run: zero matches outside `.worktrees`), and it was **not listed** in
`infra/home-fork/declared-pairs.json` — an undeclared HOME payload, since the HOME-fork lint compares
declared pairs and an undeclared file is not a pair. The organ sat outside the reach of the guard
built to notice organs drifting or dying in `$HOME`.

**Superseded before this report shipped, and that is worth more than the finding.** A separate PR
merged later the same day tracked the script and declared it: `scripts/login-healthcheck.sh` is now
in `git ls-files`, and `login-healthcheck` appears three times in `declared-pairs.json`. Verified
directly, not inferred. So Failure 3 describes a real gap that **is already closed**, and a reader
checking today will find the opposite of what the paragraph above asserts in the present tense —
which is exactly why it is written in the past tense now and flagged here rather than quietly
deleted. Found by a third cross-family seat (Kimi K3) that re-checked the claim against today's
`origin/main` instead of against the report; neither Codex pass looked.

The lesson generalises past this file: **a finding has a shelf life, and a report that states its
findings in the present tense is asserting they are still true on the day it is read.** Two of this
package's findings expired between measurement and delivery — this one and the eager-import
tollbooth in `03`.

So, at the time of measurement: a monitor whose alarm channel was unarmed, whose probe
authenticated as the wrong persona, and which no lint could see. Three independent layers had to be
absent simultaneously for a ten-day silence — and an earlier draft added "each of which alone would
have surfaced this within an hour", which is a counterfactual, not a measurement, and is dropped.
The third layer has since been closed (see above); the first two were closed during this
investigation.

## Why this belongs to the CRM↔portal mandate

It is not a side finding. This *is* the operator↔client seam: the one production symptom that
persists today is caused precisely by the two personas sharing one `team_members` table, one login
endpoint, and one token, while their eligibility rules diverge. The probe is the first real-world
casualty of that divergence, and it happened to be the organ watching the front door.

## The irony, stated plainly

The guard was built because a green `/health` masked a broken login. It has now spent ten days
being a red signal nobody receives — the same failure mode, one level up. A monitor that cannot
prove its own alarm path is a monitor that reports on everything except itself.

## Remedy — and where the operator boundary falls

Two of the three are operator-only; I am deliberately not acting on them.

1. **`operator[secret]`** — arm `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` in the launchd job's
   environment, pointed at the LIVE bot (`@zantara0bot`, chat `8847435604`), and **delete the
   `BALIZEROBOT_TOKEN` fallback on line 28** rather than leaving a burned-bot path in the code.
   Reading or writing that secrets file is outside what this session may do.
2. **`operator[business]`** — decide what the probe should authenticate as. Two defensible answers,
   and they are not equivalent: give the healthcheck account a real `linked_client_id` +
   `portal_access` (keeps testing the client door, which is what it currently tests), or move it to
   a low-privilege **team** account (tests the operator door, which is the domain it is named
   after and mounted on). The script's own comment says it is watching `kita`; today it is
   measuring `my`.
3. **In-perimeter, and the only durable one** — whichever account is chosen, the probe must fail
   loudly when its own alarm path is unarmed. `telegram: missing creds` is currently logged at the
   same level as routine chatter and is invisible; an unarmed alarm channel should make the probe
   exit non-zero so the launchd/cron receipt layer escalates it, and the script should be added to
   `declared-pairs.json` so the HOME-fork lint can see it at all.

Item 3 is the class fix: items 1 and 2 repair this instance, item 3 is what makes the next instance
audible.

## Method note

No secret value was read: access to `~/.nuzantara-secrets.env` was denied by the permission layer
and was not worked around. The evidence above comes from the script's own log, which reports its
credential state without disclosing it. Probing the login endpoint with invalid credentials tripped
the backend's brute-force limiter (`429 Too many failed attempts`) during this session — a
self-inflicted, self-clearing state, recorded here for honesty.

## Adversarial review

Seat: **Codex `gpt-5.6-terra`** (OpenAI family, effort medium, read-only sandbox), instructed to
default to "the claim is defective". Seven objections; three are load-bearing and are recorded here
without softening.

1. **BLOCKER, accepted.** "*a 403 from this endpoint means one thing and only one thing*" — this
   holds only if the request reached that specific handler branch and no middleware, proxy or
   dependency produced the 403. Nothing in the evidence ties the logged 403 to that branch by
   request id or trace. The root cause was independently confirmed afterwards by flipping the
   account's role and watching the probe turn green, which is what actually supports the conclusion
   — not the uniqueness argument as written.
2. **BLOCKER, accepted.** "*A synthetic monitoring account has no CRM client row to link to, so it
   cannot satisfy that condition*" — stated as a deduction from the word "synthetic". It happens to
   be true of this account and was later measured, but the sentence as written asserts a fact it did
   not check.
3. **BLOCKER, partly rejected.** The reviewer objected that "*the token … cannot be revoked*" is not
   true by definition of an exposed token. Correct in general and wrong here: the mechanism is
   stated in the repo's own `CLAUDE.md` §13 — BotFather answers only to the account that created the
   bot, and that account is no longer reachable. The claim stands *because of that mechanism*, which
   this file should have cited and did not.

Accepted as over-claimed: "failing for ~10 days" dates the retained log and escalations, not the
first failure; the 61-to-61 correspondence between suppressed decisions and credential failures is
two counts, not a proven pairing; and "three independent layers, each of which alone would have
surfaced this within an hour" is a counterfactual, not a measurement.

### Third seat: the supersession, in the words of whoever closed it

**Kimi K3** re-derived this file's claims against the repository as it stands rather than against the
quoted output above, and independently reached the same two results the Codex pass did (the 429
brute-force lockout defeating "every other rejection is a 401"; the tracked-and-declared status of
the script). Its more useful contribution was the provenance: `infra/home-fork/declared-pairs.json`
now carries the pair with a note written by whoever closed the gap, which reads in part —

> *"Promoted to repo canon 2026-08-19 while hardening the alarm-channel-down blindness (61/61
> consecutive-failure alerts logged 'telegram: missing creds' and the script still called it a
> routine log line — exit code and Genoma last_error never said the alarm itself was dead). Was an
> UNDECLARED live payload before this (family #1) — the plist EnvironmentVariables carry only
> HOME+PATH, so it was invisible to lint_home_fork.py entirely."*

Verified verbatim on disk. Two things follow. The gap this file names as Failure 3 was closed the
same day by someone working the same symptom from the other end — the note cites the same 61/61
figure this report measured independently. And the closing note carries a detail this file did not
have: the reason the lint could not see the payload is that the plist's `EnvironmentVariables`
expose only `HOME` and `PATH`, so the discovery pass had nothing to match on. That is a sharper
statement of the mechanism than "it was not listed", and it belongs to the person who wrote it.

The same note also records that the live `$HOME` copy is a real file, not a symlink, and **must be
re-synced by hand after merge** — so the repo-canon entry does not by itself make the running copy
current. Existence is still not participation, one layer further down.
