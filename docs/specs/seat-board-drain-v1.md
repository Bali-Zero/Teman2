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
`scripts/cron-wrapper.sh`. The consumer that must satisfy it does not exist yet; the closed
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

| PR    | what the gate found                                                                                                                                                                                                                               |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| #6984 | two red deterministic checks; closed while frozen by its own arming                                                                                                                                                                               |
| #6988 | the board's `machine` field compared unsplit against a gateway that splits it                                                                                                                                                                     |
| #6992 | "13 hand-cures in 30d" was the `healer-mini` FAMILY; the `stale-lock` ENTITY had fired once in 74d, and its only emitter runs on Mini, so the cure was unreachable on Pro                                                                         |
| #7014 | "73 of 123 closable" was measured by importing the CHECKOUT's gateway; 27 of Pro's producers call a stale HOME copy that does not route at all. And the witness the consumer looked for was named by a different rule than the one that writes it |

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
called the checkout. On Pro today that is false for 27 of them. This is the defect that closed
#7014 and it is the one most likely to recur, because the wrong method is the convenient one.

**S1.2 — `infra/home-fork/declared-pairs.json` SHALL declare `~/scripts/tg_notify.py`** against
the checkout canon, so `scripts/lint_home_fork.py` reports the divergence instead of the fleet
discovering it a fifth time. Declaring it is not fixing it; see S2.3.

---

## 2. Which producer reaches which gateway

Each wrapper resolves the gateway from its own location, not from the repo:

- `scripts/cron-runner.sh:135-136` — `gateway="$(dirname "$0")/tg_notify.py"`, falling back to
  `$HOME/nuzantara/scripts/tg_notify.py` **only if that file does not exist**.
- `scripts/cron-wrapper.sh:124-125` — identical two lines.
- `scripts/cron-state.sh` — no gateway resolution of its own; it is reached as a symlink into the
  checkout, so `dirname $0` is already the checkout.

The fallback is the trap. It fires on ABSENCE, not on staleness — so a stale sibling beside the
caller silently wins over a current canon one directory away.

Measured — `crontab -l | grep -oE '(cron-runner|cron-state|cron-wrapper)\.sh' | sort | uniq -c`,
plus `ls -la` on each caller path:

| caller            | crontab entries | physical location                                   | gateway it resolves to                    | routes? |
| ----------------- | --------------- | --------------------------------------------------- | ----------------------------------------- | ------- |
| `cron-state.sh`   | 28              | `~/scripts/cron-state.sh` → symlink → checkout      | checkout copy                             | **yes** |
| `cron-wrapper.sh` | 8               | `~/Desktop/nuzantara/scripts/` (symlink → checkout) | checkout copy                             | **yes** |
| `cron-wrapper.sh` | 1               | `~/Desktop/nuzantara-deploy/scripts/`               | no sibling → **fallback** → checkout copy | **yes** |
| `cron-runner.sh`  | 27              | `~/scripts/cron-runner.sh`, a REAL file             | `~/scripts/tg_notify.py`, the 18-Aug fork | **no**  |

**S2.1 — The drain design SHALL state, for each producer family it claims to cure, which gateway
copy that family reaches.** A cure whose producers all reach a non-routing gateway is a cure with
no inflow, however sound its logic.

**S2.2 — A producer that does not route is NOT a producer the consumer may count.** Its alerts do
not appear on the board and never will until S2.3 is done.

**S2.3 — Realigning `~/scripts/tg_notify.py` is a PREREQUISITE, not a side effect, and it is its
own PR.** It changes the behaviour of 27 cron jobs at once: their p0 stop paging and start landing
on a board nobody drains yet. Sequencing therefore matters and is fixed here:

1. the consumer lands first, draining what already routes (the 9 `cron-wrapper.sh` entries);
2. `~/scripts/tg_notify.py` is realigned second, under its declared HOME pair, with the
   before/after routed-volume measured on the board rather than on an archive;
3. `cron-runner.sh`'s resolution is changed third, to prefer the checkout and treat a sibling as
   the fallback — the opposite of today — so the next stale sibling cannot win by existing.

Doing 2 before 1 recreates #6973's own failure at 27× the volume: noise moved from Telegram to a
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

Measured — `grep -n` on each wrapper:

| wrapper           | dedup-key it emits                                                         | state file it writes                                                                                    | agree?  |
| ----------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | ------- |
| `cron-state.sh`   | `cron-fail:${JOB_KEY}` (L125) where `JOB_KEY=sanitize_key(JOB_NAME)` (L78) | `$STATE_DIR/$job_key.last.json` (L33), same `JOB_KEY` (L102)                                            | **yes** |
| `cron-runner.sh`  | `cron-fail:${job_key}` (L141)                                              | `$STATE_DIR/$job_key.last.json` (L55), same `job_key` (L160)                                            | **yes** |
| `cron-wrapper.sh` | `cron-fail:${JOB_NAME}` (L129), name **unchanged**                         | `$SENTINEL_JOB_KEY.last.json` (L270) where `SENTINEL_JOB_KEY="$(echo "$JOB_NAME" \| tr '-' '_')"` (L36) | **NO**  |

`sanitize_key()` (cron-state.sh L17) lowercases and replaces every non-alphanumeric run with a
single `_`. `cron-state.sh` and `cron-runner.sh` apply it ONCE and use the result on both sides, so
their key and their filename are the same string by construction. `cron-wrapper.sh` transforms only
the filename.

The live consequence, measured: `fly-pg-backup` (the W106 PG backup, 3 alerts/30d) alerts as
`cron-fail:fly-pg-backup`. `~/.agent/decisions/state/fly-pg-backup.last.json` does not exist.
`~/.agent/decisions/state/fly_pg_backup.last.json` does, and says
`{"job": "fly_pg_backup", "status": "ok", "ts": 1789932300, "host": "Nuzantara"}`. A consumer that
builds the path from the key verbatim reports "no run-state file" against a witness sitting in the
same directory — and the `job` field inside is underscored too, so a `state_job != name` check
would call it a stranger's witness even after finding it.

And the sting: the 8 routing `cron-wrapper.sh` jobs are exactly the ones whose witness cannot be
found, while the 27 `cron-runner.sh` jobs whose naming is consistent never reach the board.

**S4.1 — The key→witness mapping SHALL be an explicit, per-wrapper table in the implementation, not
a string interpolation.** A consumer may not assume `key.split(":", 1)[1] + ".last.json"`.

**S4.2 — The mapping SHALL be a FUNCTION of the producer, discovered from the row, not guessed.**
The board row carries `context` (`cron:${JOB_NAME}` for cron-wrapper, per L128) — enough to
identify the wrapper. Where it is not enough, the consumer refuses; it does not try both spellings
and take whichever answers. Trying both is how a stranger's witness gets accepted.

**S4.3 — The `job` field INSIDE the state file SHALL be compared under the same transform as the
filename**, or the stranger-witness check refuses every cron-wrapper row it just learned to find.

**S4.4 — The better fix is upstream and SHALL be offered as its own PR: `cron-wrapper.sh` applying
`sanitize_key` to BOTH sides, as its two siblings already do.** That deletes the mapping table
rather than maintaining it. It is not free — it renames live state files, and a job whose
`.last.json` moves loses its history for one cycle — which is why it is a separate, sequenced
change and not a line in the consumer's PR.

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

| #   | the claim                                                                                        | how it is falsified                                                                                                               |
| --- | ------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| A1  | Every producer family the design counts reaches a ROUTING gateway                                | for each family, resolve the wrapper's gateway path as the wrapper does and `grep -c gateway_routed` it; any 0 falsifies          |
| A2  | Every row the consumer closes had a witness found by the DECLARED mapping, not by a second guess | the consumer logs the witness path it opened; a path not derivable from §4's table for that row's `context` falsifies             |
| A3  | A cron-wrapper job with a hyphen in its name is curable                                          | seed `cron-fail:a-b` with `a_b.last.json` ok-and-newer; not closing falsifies                                                     |
| A4  | A stranger's witness is still refused after A3                                                   | seed `cron-fail:a-b` with `a_b.last.json` whose `job` is `c_d`; closing falsifies                                                 |
| A5  | A job that re-breaks inside the mute window is visible to a session reading the board            | close a row, break the job again without the gateway writing a new row, read the board; a board showing only `resolved` falsifies |
| A6  | The routed-volume figure is measured on the board                                                | any headline count sourced from `archive-p0.jsonl` and not labelled a projection falsifies                                        |
| A7  | The consumer's own code produced the closable count                                              | the count's receipt names the consumer's entrypoint, not a re-implementation; anything else falsifies                             |

---

## 9. Sequencing

1. **This spec is adjudicated.** Not merged alongside an implementation.
2. **Consumer PR** — one cure, `cron-fail`, restricted to the producers §2 shows routing today
   (the 9 `cron-wrapper.sh` entries), with §4's mapping table and §5's answer chosen and tested.
   Its headline number is measured per S6.2 and S6.3, and it will be SMALL — that is the honest
   state of the surface, not a weakness of the PR.
3. **`cron-wrapper.sh` key unification** (S4.4) — deletes the mapping table.
4. **`~/scripts/tg_notify.py` realignment** (S2.3) — declared pair first, then the 27 jobs begin
   routing, then the volume is re-measured on the board.
5. **`cron-runner.sh` resolution inverted** (S2.3 step 3) — checkout preferred, sibling as fallback.

Steps 3-5 each change live fleet behaviour and each get their own PR and their own before/after
measurement. None of them belongs in step 2.

---

> Every table in this file was measured on Pro on 2026-09-21 over ssh, read-only, with the commands
> named beside it. Nothing here is inherited from the four closed PRs' packs — those are the reason
> this file exists, not a source for it.
