# SPEC — seat-board drain v1: which alert reaches which board, and which witness proves it

date: 2026-09-21 · owner: me (M5, infra/notify-routing lane) · status: normative, pre-implementation
origin: PR #6973 (merged, the gateway's fourth tier) → consumer attempts #6984, #6988, #6992, #7014,
all four closed. Agent PR Contract rule 1 (a fix-of-a-fix stops at depth 1) routed this surface to a
specification rather than a fifth branch.

**Status: normative.** A consumer may be built from this file without inference. Where an
implementation and this file disagree, this file is wrong or the implementation is — say which, in
a PR, rather than resolving it silently in code.

Constrains any process that closes rows on `shared/escalations_*.jsonl`. The producers it
describes are `scripts/tg_notify.py`, `scripts/cron-state.sh`, `scripts/cron-runner.sh` and
`scripts/cron-wrapper.sh`, plus — found by §2's census — Pro's HOME-only `~/scripts/cron-agent.sh`
and `~/scripts/cron-agent-python/agent_job.py`. The consumer that must satisfy it does not exist yet; the closed
`scripts/board_seat_consumer.py` from PR #7014 is the reference for the parts that were never in
doubt (§7).

**Implementation is a separate PR, after this spec is adjudicated.** Landing both together would
mean the spec was never a spec, only a commit message.

## Why this file exists

PR #6973 gave the gateway a fourth tier: a p0 whose dedup-key is not an `OWNER_FAMILY` stops
reaching Telegram and lands on the escalation board as `type=gateway_routed,
cure_lane.owner=seat`. Nothing drains those rows. Four PRs tried to build the drainer. Each was
closed by a gate, and each gate found the SAME two defects one level lower than the last:

1. **a count measured on one entity and attributed to another**, and
2. **a cure that cannot fire on the node it is armed on**.

| PR    | what the gate found                                                                                                                                                                                                                                                                                                     |
| ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| #6984 | two red deterministic checks; closed while frozen by its own arming                                                                                                                                                                                                                                                     |
| #6988 | the board's `machine` field compared unsplit against a gateway that splits it                                                                                                                                                                                                                                           |
| #6992 | "13 hand-cures in 30d" was the `healer-mini` FAMILY; the `stale-lock` ENTITY had fired once in 74d, and its only emitter runs on Mini, so the cure was unreachable on Pro                                                                                                                                               |
| #7014 | "73 of 123 closable" was measured by importing the CHECKOUT's gateway; it counted 27 of Pro's producers calling a stale HOME copy that does not route at all; §2's census puts it at 74 of 85 active crontab entries. And the witness the consumer looked for was named by a different rule than the one that writes it |

The pattern is not carelessness. It is that **nobody wrote down which gateway copy each producer
reaches, which board each row lands in, or how an alert key becomes a witness filename** — so each
attempt inferred it, inferred it plausibly, and inferred it wrong. That is what this file fixes.
Every table below was measured on Pro on 2026-09-21, and every row names the command that produced
it so the next reader can re-run it rather than trust it.

---

## 1. The gateway is not one file

`tg_notify.py` exists in more than one place on Pro, and the copies do not agree about whether the
routing tier exists at all.

Measured — `ls -la`, `wc -c`, `grep -c gateway_routed`, per path:

| path                                                             | size  | mtime      | `gateway_routed` occurrences | routes?                                                                 |
| ---------------------------------------------------------------- | ----- | ---------- | ---------------------------- | ----------------------------------------------------------------------- |
| `/Users/nuzantara/nuzantara/scripts/tg_notify.py`                | 55192 | 2026-09-21 | 2                            | **yes**                                                                 |
| `/Users/nuzantara/Desktop/nuzantara/scripts/tg_notify.py`        | 55192 | 2026-09-21 | 2                            | **yes** — `Desktop/nuzantara` is a symlink to `~/nuzantara`, same inode |
| `/Users/nuzantara/scripts/tg_notify.py`                          | 43358 | 2026-08-18 | **0**                        | **no**                                                                  |
| `/Users/nuzantara/Desktop/nuzantara-deploy/scripts/tg_notify.py` | —     | —          | —                            | ABSENT (see §2, the fallback)                                           |

The HOME copy also has zero occurrences of `ACT_ROUTING_ENABLED` and zero of `cure_lane`. It is not
a stale-but-equivalent copy. It is a copy from before the tier existed, and a p0 that reaches it
takes the pre-#6973 path: Telegram, or the spool, never the board.

**S1.1 — A measurement of "how many alerts would be routed" SHALL be taken per PRODUCER, against
the gateway copy that producer actually invokes.** Importing `tg_notify` from the checkout and
classifying an archive with its `_owner_reserved()` measures what WOULD happen if every producer
called the checkout. On Pro today that is false for 74 of the 85 active crontab entries (§2). This is the defect that closed
#7014 and it is the one most likely to recur, because the wrong method is the convenient one.

**S1.2 — `infra/home-fork/declared-pairs.json` SHALL declare `~/scripts/tg_notify.py`** against
the checkout canon, so `scripts/lint_home_fork.py` reports the divergence instead of the fleet
discovering it a fifth time. Declaring it is not fixing it; see S2.3.

---

## 2. Which producer reaches which gateway

Each resolver finds the gateway from its own location, not from the repo, and falls back to
`$HOME/nuzantara/scripts/tg_notify.py` **only if the sibling does not exist**:

- `scripts/cron-runner.sh:135`, `scripts/cron-wrapper.sh:124`, `scripts/cron-state.sh:118`, and on Pro
  the HOME-only `~/scripts/cron-agent.sh:121` and `~/scripts/fly-qdrant-backup.sh:70` —
  `gateway="$(dirname "$0")/tg_notify.py"` plus a `[ -f ... ] ||` fallback line.
- `scripts/cron-agent-python/agent_job.py:147` (`_tg_gateway()`) — `Path(__file__).resolve().parent.parent`
  first. The 16 `run.sh <job>` entries reach it through `<job>.py` importing `agent_job`.
- `scripts/job_health.py` and `scripts/drive_token_watchdog.py` — `PROJECT_ROOT / "scripts"` first.

The fallback is the trap. It fires on ABSENCE, not on staleness — so a stale sibling beside the
caller silently wins over a current canon one directory away. And `$0` is the path the file was
INVOKED by: `~/scripts/cron-state.sh` is a FILE symlink into the checkout, so `dirname "$0"` stays
`~/scripts` and the fork wins. An earlier revision of this section said the opposite; two gates on
#7039 and #7047 found it, and found that a count by wrapper NAME kept missing whole populations.

**S2.0 — Every count in this file of which producers reach which gateway SHALL come from
`scripts/tg_gateway_census.py` run on the machine it names, never from a count by wrapper name.**
The census reads `crontab -l` and follows each active entry into what it runs (its docstring lists
how), running each producer's OWN resolution lines in isolation — never the job, and always inside a
macOS `sandbox-exec` jail that denies writes, network and exec. Anything it cannot
run is UNRESOLVED and makes it exit 3. A clean exit means every gateway reference in every file it
followed was run — not more: a resolver counts if the entry loads it, whether or not a given run
calls it, and env set by files a job sources at run time is not modelled (on Pro, `grep -c
TG_NOTIFY_BIN` is 0 in the crontab, `~/.zshrc.secrets` and `~/.nuzantara-secrets.env`, 2026-09-21).

Measured on Pro (`Nuzantara`) at 2026-09-21T16:58Z over all 85 active entries of `crontab -l` —
`ssh pro 'python3 -' < scripts/tg_gateway_census.py`, exit 0, `unresolved=0`:

| resolving code, as invoked                                         | entries | gateway it resolves to                                                                                              | routes?        |
| ------------------------------------------------------------------ | ------- | ------------------------------------------------------------------------------------------------------------------- | -------------- |
| `~/scripts/cron-state.sh` (FILE symlink → checkout)                | 28      | `~/scripts/tg_notify.py`, the 18-Aug fork                                                                           | **no**         |
| `~/scripts/cron-runner.sh` (real file)                             | 24      | the fork                                                                                                            | **no**         |
| `~/scripts/cron-agent-python/agent_job.py` (via `run.sh`)          | 16      | the fork                                                                                                            | **no**         |
| `~/scripts/cron-agent.sh` (real file)                              | 6       | the fork                                                                                                            | **no**         |
| `~/scripts/fly-qdrant-backup.sh` (child of `fly-backup.sh`)        | 1       | the fork — inside one of the 28 `cron-state.sh` entries                                                             | **no**         |
| `~/Desktop/nuzantara/scripts/cron-wrapper.sh` (DIR symlink)        | 7       | `~/nuzantara/scripts/tg_notify.py`, the checkout                                                                    | **yes**        |
| `~/Desktop/nuzantara/scripts/job_health.py`                        | 1       | the checkout — its entry's `cron-state.sh` wrapper reaches the fork too                                             | **yes**        |
| `~/Desktop/nuzantara/scripts/drive_token_watchdog.py`              | 1       | the checkout — inside one of the 7 `cron-wrapper.sh` entries                                                        | **yes**        |
| `~/nuzantara/scripts/sentinel_lib/alerter.py` (package)            | 2       | the checkout — imported by the two WA sentinels, both inside `cron-runner.sh` entries, which reach the fork too     | **yes**        |
| `~/nuzantara/scripts/wa_{session_liveness,codex_seat_sentinel}.py` | 1 + 1   | the checkout — each one's `except` fallback when `alerter` fails to import, same two entries                        | **yes**        |
| `~/Desktop/nuzantara-deploy/scripts/cron-wrapper.sh`               | 1       | none: a symlink to a directory renamed `nuzantara-deploy.retired-20260910`, so the entry never starts (`kb-ingest`) | **never runs** |

Per entry, the 85 split without overlap: **74 reach the fork**, 7 reach only the checkout, 3 reach no
`tg_notify.py` at all (`fly-cost-alert.sh`, `ollama-warm-pin.sh`, `run_peraturan_ingestion.sh`;
two of them name Telegram in their own text, which this census does not measure), and 1 never runs.
Ten entries reach the checkout; three of them (`job_health.py`'s and the two WA sentinels') reach the
fork as well, through the wrapper around them.

**S2.1 — The drain design SHALL state, for each producer family it claims to cure, which gateway
copy that family reaches.** A cure whose producers all reach a non-routing gateway is a cure with
no inflow, however sound its logic.

**S2.2 — A producer that does not route is NOT a producer the consumer may count.** Its alerts do
not appear on the board and never will until S2.3 is done.

**S2.3 — Realigning `~/scripts/tg_notify.py` is a PREREQUISITE, not a side effect, and it is its
own PR.** It changes the behaviour of 74 crontab entries at once: their p0 stop paging and start landing
on a board nobody drains yet. Sequencing therefore matters and is fixed here:

1. the consumer lands first, draining what already routes (the 7 running `cron-wrapper.sh` entries);
2. `~/scripts/tg_notify.py` is realigned second, under its declared HOME pair, with the
   before/after routed-volume measured on the board rather than on an archive;
3. every sibling-first resolver in §2's table is changed third, to prefer the checkout and treat a
   sibling as the fallback — the opposite of today — so the next stale sibling cannot win by existing.

Doing 2 before 1 recreates #6973's own failure at the volume of 74 entries: noise moved from Telegram to a
board nobody reads down.

---

## 3. Which board a row lands in

`tg_notify._board_path()` resolves `Path(__file__).resolve().parents[1] / "shared"` and falls back
to the spool when that directory does not exist. `.resolve()` follows symlinks, so the
`Desktop/nuzantara` callers land in the checkout's `shared/`, which is what
`sentinel_lib.escalations` reads.

The HOME copy has no routing code, so it never reaches this function at all. But if it is realigned
without moving it (S2.3 step 2), it WILL: `parents[1]` of `/Users/nuzantara/scripts/tg_notify.py`
is `/Users/nuzantara`, and `/Users/nuzantara/shared` is not the board. The row would be written to
a file `read_all_escalations()` does not open — present, plausible, and invisible.

**S3.1 — Any gateway copy that routes SHALL resolve to the board `sentinel_lib.escalations` reads,
and the realignment PR SHALL prove it by writing one row and reading it back through
`read_all_escalations()`, not by inspecting the path.**

**S3.2 — `machine` on a board row is written by the gateway as `socket.gethostname().split(".")[0]`
and is NOT normalised historically.** Pro's board carries three spellings today (`pro` 245,
`Nuzantara` 3, `nuzantara` 1) because older writers used other rules. A consumer comparing
`machine` SHALL compare case-insensitively on the bare host, and SHALL treat a row it cannot
attribute as foreign — refusing, never curing.

---

## 4. From alert key to witness filename

This is the contract nobody wrote down, and the one that made #7014's central measurement wrong in
BOTH directions — it counted jobs as un-provable that had a witness, and it would have refused that
witness as a stranger's even if it had found it.

Measured — `grep -n` on each wrapper, on `origin/main` BEFORE the fix (the `cron-wrapper.sh` row is
historical; see S4.4 for what changed and what did not):

| wrapper           | dedup-key it emits                                                         | state file it writes                                                                                    | agree?  |
| ----------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | ------- |
| `cron-state.sh`   | `cron-fail:${JOB_KEY}` (L125) where `JOB_KEY=sanitize_key(JOB_NAME)` (L78) | `$STATE_DIR/$job_key.last.json` (L33), same `JOB_KEY` (L102)                                            | **yes** |
| `cron-runner.sh`  | `cron-fail:${job_key}` (L141)                                              | `$STATE_DIR/$job_key.last.json` (L55), same `job_key` (L160)                                            | **yes** |
| `cron-wrapper.sh` | `cron-fail:${JOB_NAME}` (L129), name **unchanged**                         | `$SENTINEL_JOB_KEY.last.json` (L270) where `SENTINEL_JOB_KEY="$(echo "$JOB_NAME" \| tr '-' '_')"` (L36) | **NO**  |

`sanitize_key()` (cron-state.sh L17) lowercases and replaces every non-alphanumeric run with a
single `_`. `cron-state.sh` and `cron-runner.sh` apply it ONCE and use the result on both sides, so
their key and their filename are the same string by construction. `cron-wrapper.sh` transforms only
the filename.

The live consequence, measured before the fix: `fly-pg-backup` (the W106 PG backup, 3 alerts/30d)
alerted as `cron-fail:fly-pg-backup`. `~/.agent/decisions/state/fly-pg-backup.last.json` does not exist.
`~/.agent/decisions/state/fly_pg_backup.last.json` does, and says
`{"job": "fly_pg_backup", "status": "ok", "ts": 1789932300, "host": "Nuzantara"}`. A consumer that
builds the path from the key verbatim reports "no run-state file" against a witness sitting in the
same directory — and the `job` field inside is underscored too, so a `state_job != name` check
would call it a stranger's witness even after finding it.

And the sting: the 7 running `cron-wrapper.sh` jobs were exactly the ones whose witness could not
be found, while the 74 entries that resolve the fork (§2) never reach the board, whatever their naming.

**S4.1 — For a `cron-fail:` row from any of the three cron wrappers, the witness SHALL be
`<state dir>/<name>.last.json` where `<name>` is the key after the first `:`, verbatim.** This is
true by construction once S4.4 is in: all three derive key and filename from one string. It is an
identity, not an inference, and the consumer SHALL NOT normalise `<name>` further — any transform
it applied would be a second copy of the producer's rule, free to drift from it.

**S4.2 — A row whose producer writes no witness SHALL be refused, never guessed.** Two producers
emit `cron-fail:` keys and write no state file at all: `scripts/wr2-cron-wrapper.sh:84`
(`cron-fail:wr2.${MODULE##*.}.${WR2_STAGE}`) and `infra/openclaw/wr2/wr2-script-wrapper.sh:94`
(`cron-fail:wr2.${SCRIPT_ID}.${WR2_STAGE}`). Their rows have no `<name>.last.json` and the consumer
reports them as such. It does not try a second spelling and take whichever answers: trying both is
how a stranger's witness gets accepted.

**S4.3 — The witness's own `job` field SHALL equal `<name>`**, or the file is a stranger's witness
and the row is refused. Under S4.1 this is an equality check, not a comparison under a transform.

**S4.4 — The fix is upstream, and it is smaller than this section first assumed.** An earlier
revision said unifying the wrapper "renames live state files". It does not have to: the FILE side
already follows the siblings' convention for every job name in Pro's crontab — all eight are
lowercase with hyphens, where `tr '-' '_'` and `sanitize_key` produce the same string — so the fix changes the
KEY and leaves the file alone: `--dedup-key "cron-fail:${SENTINEL_JOB_KEY}"`. No `.last.json` moves,
and the Cell `cron_sensor` that reads the state dir sees no change. The cost is one-time and on the
gateway's side: each of those jobs alerts under a new key, so its repeat ladder restarts from the
first rung once. `scripts/test_cron_wrapper_alert.sh` pins it by asserting the RELATION — key name
== witness stem == the witness's own `job` field — never a literal, so a later transform on either
side cannot pass by agreeing on one example.

S4.1-S4.3 above are written against the state AFTER this fix. The general divergence between
`tr '-' '_'` and `sanitize_key` (uppercase, dots, spaces, doubled or leading hyphens) is real and
pre-existing, and harmless here only because the key and the file now come from the SAME string —
whatever that string is. No live caller exercises the divergent inputs; if one ever does, the
relation still holds and only the cosmetic agreement with the siblings is lost.

---

## 5. A resolution does not reset the ladder

`tg_notify` mutes a repeating condition on a ladder keyed by the dedup-key. Read live on Pro by
importing the checkout's module: `REPEAT_LADDER_H = [6.0, 24.0, 72.0, 168.0]`, so the longest rung
is **168h** and a chronic condition reaches it. Closing a board row touches none of that state. So: a job breaks, the gateway writes a board row, the
consumer proves the job recovered and closes it — and the job breaks AGAIN inside the mute window.
The gateway suppresses. No new board row is written. The consumer never re-checks a row it closed.

The board now reads `resolved` for a job that is failing, which is **strictly worse than the
pending row it replaced**: before the drain, that row sat there being visible.

**S5.1 — The consumer SHALL NOT close a row whose condition can re-fire silently.** At least one of
these SHALL hold, and the implementation SHALL say which:

- (a) the close also clears the gateway's dedup entry for that key, so a re-break pages/routes
  immediately — this couples the consumer to the gateway's state file and needs its own locking; or
- (b) the consumer re-probes previously-closed keys on a cadence shorter than the ladder's longest
  window, and re-opens a row whose witness has gone back to `failed`; or
- (c) the cure is restricted to conditions that cannot recur inside the window, and the restriction
  is stated and measured, not asserted.

**S5.2 — Whichever is chosen, the test for it SHALL break the job again INSIDE the window**, and
assert what a session reading the board at that moment would see. A test that only closes and
re-runs does not exercise this.

---

## 6. What the numbers may say

Every count this lane has published was true of some population and false of the one it named. The
rule that follows is not stylistic:

**S6.1 — A count SHALL name its POPULATION, its WINDOW, its SOURCE FILE and the MACHINE it was read
on, in the same sentence as the number.** "13 in 30 days" is not a claim; "13 `healer-mini:*` alerts
in the 30 days to 2026-09-21 in Pro's `archive-p0.jsonl`" is, and is immediately checkable against
"1 `healer-mini:stale-lock`".

**S6.2 — A count of what a consumer CAN cure SHALL be produced by running that consumer's own code
against the live data, not by re-implementing its logic in a probe.** Both #6992 and #7014 published
a replay that diverged from the code it claimed to model.

**S6.3 — A count of routed volume SHALL be taken on the BOARD, not on the p0 archive**, or it SHALL
be labelled a projection. The archive says what was alerted; only the board says what arrived. On
2026-09-21 the archive projected 285 routed rows over 30 days and the board held 1.

---

## 7. What was never in doubt

The gates verified these and they are the foundation the implementation starts from, not open
questions:

- **prove-then-close**: the cure re-probes the condition live; the alert text is evidence of the
  past only (superscar #6).
- **entity-not-substring**: the family is the segment before the first `:`, compared by equality
  (superscar #3).
- **locality**: a row whose `machine` is not this host is never cured here, and a resolution is
  additionally refused while the same job is pending elsewhere, because every reader collapses by
  `job` alone (superscar #10).
- **fail-open**: unknown shapes, unreadable probes and exceptions exit 0 with the board untouched.
- **a family with no cure is left pending and COUNTED**; the count is the deliverable, not the
  number of rows closed.
- **no blind kickstart**: a restart that does not cure is a green run that fixed nothing
  (superscar #2).

Also settled, from #7014's gate and re-checked here: an alert `ts` that is `NaN`, `Infinity`, `0`
or negative is read as a recovery, because the guard checks the TYPE only. Verified in the
interpreter: `isinstance(float("nan"), (int, float))` is `True`, and `json.dumps({"ts": float("nan")})`
emits `{"ts": NaN}` — non-finite floats are written by default, so they arrive on the board
routinely rather than exotically. **S7.1 — the ts guard SHALL check FINITENESS and a plausible
range, not only the type.**

---

## 8. Acceptance — falsifiable, each with its probe

| #   | the claim                                                                                     | how it is falsified                                                                                                               |
| --- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| A1  | Every producer family the design counts reaches a ROUTING gateway                             | run `scripts/tg_gateway_census.py` on Pro (S2.0); any entry the design counts showing `NONROUTING`, or exit 3, falsifies          |
| A2  | Every row the consumer closes had its witness found by S4.1's identity, not by a second guess | the consumer logs the witness path it opened; any path other than `<state dir>/<key after ':'>.last.json` falsifies               |
| A3  | A job whose raw name had a hyphen is curable                                                  | run the REAL `cron-wrapper.sh` with a failing job `a-b`, then a succeeding one; the board row it produced not closing falsifies   |
| A4  | A stranger's witness is still refused                                                         | seed `cron-fail:a_b` with `a_b.last.json` whose `job` is `c_d`; closing falsifies                                                 |
| A4b | A witness-less producer is refused, not guessed                                               | seed `cron-fail:wr2.x.guard` with no state file and an ok-and-newer `wr2_x_guard.last.json` beside it; closing falsifies          |
| A5  | A job that re-breaks inside the mute window is visible to a session reading the board         | close a row, break the job again without the gateway writing a new row, read the board; a board showing only `resolved` falsifies |
| A6  | The routed-volume figure is measured on the board                                             | any headline count sourced from `archive-p0.jsonl` and not labelled a projection falsifies                                        |
| A7  | The consumer's own code produced the closable count                                           | the count's receipt names the consumer's entrypoint, not a re-implementation; anything else falsifies                             |

---

## 9. Sequencing

1. **This spec is adjudicated.** Done: #7016, merged alone, with no implementation beside it.
2. **`cron-wrapper.sh` key unification** (S4.4) — FIRST, not third. An earlier revision placed it
   after the consumer on the belief that it renamed live state files; it does not (S4.4). It routes
   nothing new — it renames the keys of jobs that ALREADY route — so it cannot move noise onto the
   board, and it deletes the mapping table the consumer would otherwise have to carry and test.
3. **Consumer PR** — one cure, `cron-fail`, with §5's answer chosen and tested and the ts guard of
   S7.1. Its headline number is measured per S6.2 and S6.3, and it will be SMALL — that is the honest
   state of the surface, not a weakness of the PR.
4. **`~/scripts/tg_notify.py` realignment** (S2.3) — declared pair first, then the 74 entries begin
   routing, then the volume is re-measured on the board.
5. **Every sibling-first resolver inverted** (S2.3 step 3) — checkout preferred, sibling as fallback.

Steps 2, 4 and 5 each change live fleet behaviour and each get their own PR and their own
before/after measurement. None of them belongs in step 3.

---

> Every table in this file was measured on Pro on 2026-09-21 over ssh, read-only, with the commands
> named beside it. Nothing here is inherited from the four closed PRs' packs — those are the reason
> this file exists, not a source for it.
