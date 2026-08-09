# DECISION RECORD — `com.balizero.nuzantara-repo-sync` writes the M5 main checkout the standing M5 doctrine calls read-only

> **Status: CLOSED 2026-08-08 — Option A (RETIRE) executed on M5.** See §Closure at the bottom
> for what was re-measured, what was run, and how it was proven. The rest of this document is
> preserved as written on 2026-08-07 so the reasoning that led here stays auditable — with one
> exception, marked inline: the record's claim that `Desktop/nuzantara` is a symlink is CORRECT
> and the ledger entry that contradicted it was wrong.
>
> _Superseded header (2026-08-07):_ ~~Status: OPEN. No option below has been executed by this
> record. Owner of the open call: **Zero**.~~ That owner assignment was itself the phantom-operator
> lane the doctrine forbids — unloading a `launchd` job is repo/infra work a session owns, not one
> of the true operator-only categories (physical, GUI, TCC, consent, credential, Legge 5). This
> document still exists so that a future session grepping `nuzantara-repo-sync` lands on the full
> picture — both positions, the measurement, and now the close — instead of re-discovering the
> conflict from scratch.

## The conflict, in one sentence

Two standing rules cannot both hold at once: **(1)** `scripts/proprioception.py`'s
`probe_home_fork_scripts` docstring and the CLAUDE.md "Agent Worktree Discipline" section both say
M5's `~/nuzantara` main checkout is deliberately left behind origin/main and reserved for
operator-interactive + hotfix use — **(2)** a `launchd` job on the same machine fast-forward-merges
`origin/main` into that exact checkout every 5 minutes, and has completed that merge 334 times.

Verbatim, both sides, read from `origin/main` in this worktree (never the stale main checkout —
see Rule 0):

```
$ git -C /Users/balizero/nuzantara/.worktrees/ops-repo-sync-doctrine-conflict show origin/main:CLAUDE.md \
    | grep -n -A2 'Agent Worktree Discipline'
## Agent Worktree Discipline (2026-05-24)

OGNI agent session (subagent dispatch / cron-spawned claude / parallel Claude Code window) DEVE
girare sotto `.worktrees/<lane>-<task-id>/` creato via `scripts/agent_start.py`. Il main checkout
`~/nuzantara` resta read-only per agent — riservato a operator interactive + cicatrix hotfix.
```

```
$ git -C /Users/balizero/nuzantara/.worktrees/ops-repo-sync-doctrine-conflict show origin/main:scripts/proprioception.py \
    | grep -n -B4 -A4 'deliberately left behind'
    A bare live≠checkout comparison cannot say which side is stale, yet the
    remedy it printed ("realign live from repo") only makes sense when the
    checkout is the current one. On 2026-07-27 this probe reported P1 DIVERGED
    on M5 for two files whose LIVE copies matched origin/main exactly — the M5
    checkout was 144 commits behind, and it is deliberately left behind
    (pulling it races ~45 live worktrees). Acting on that P1 would have
    overwritten a current worktree-isolation hook with a two-day-old one.
```

Neither document has been amended by the other since. They are both live doctrine, and they
contradict each other in the presence of this daemon.

## What was measured TODAY (2026-08-07), against yesterday's handoff numbers

Every number below was re-run in this worktree/session on 2026-08-07; the 2026-08-06 figure from
the handoff (`docs/operations/handoff-observability-block-2026-08-06.md` §2) is given alongside it
for comparison — none of today's numbers were carried over from memory.

| Measurement                                                                                                                                                                                                                                              | Command                                                                                                   | 2026-08-06 (handoff)                                                            | 2026-08-07 (this record)                                                                                                                                                                                                         |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Script identity                                                                                                                                                                                                                                          | `readonly REPO="$HOME/Desktop/nuzantara"` in `/Users/balizero/.local/bin/nuzantara-repo-sync`, 42 lines   | 42 lines                                                                        | 42 lines (unchanged)                                                                                                                                                                                                             |
| `Desktop/nuzantara` resolves to the main checkout                                                                                                                                                                                                        | `stat -L -f '%d %i %N' /Users/balizero/Desktop/nuzantara /Users/balizero/nuzantara`                       | same (dev,inode) claimed                                                        | **confirmed**: both `16777233 758478` — `Desktop/nuzantara` is a symlink to `~/nuzantara` (`readlink` confirms), so the daemon writes the main checkout directly, not a separate copy                                            |
| `launchctl` runs                                                                                                                                                                                                                                         | `launchctl print gui/501/com.balizero.nuzantara-repo-sync \| grep -E 'runs\|last exit\|run interval'`     | runs=1128, last exit=0, interval=300s                                           | **runs=1133, last exit code=0, interval=300s** (+5 runs in the elapsed time — consistent with a 300s cadence)                                                                                                                    |
| Script's own log (`~/Library/Logs/nuzantara-repo-sync.log` — distinct from the launchd stdout/stderr capture at `nuzantara-repo-sync-launchd.log`, which is 0 lines/unused because the script redirects all its own output into the log path it manages) | `wc -l`; `grep -c "OK pulled"`; `grep -c "OK pushed"`; `grep "OK pulled" \| tail -1`                      | 23209 lines, 334 "OK pulled", 0 "OK pushed" ever, last pull 2026-08-04 07:47:17 | **23221 lines** (+12), **334 "OK pulled"** (unchanged — no pull since 2026-08-04), **0 "OK pushed"** ever (unchanged), last successful pull still **2026-08-04 07:47:17**                                                        |
| Current cycle outcome                                                                                                                                                                                                                                    | `tail -15` of the script log                                                                              | postponing at "120 commit(s) behind"                                            | postponing at **"121 commit(s) behind"** as of 13:41 — the gap is still growing, one cycle at a time, because the checkout has 20 dirty (untracked/modified) entries that block the daemon's own `git diff --quiet` safety check |
| Presence on Pro / Mini                                                                                                                                                                                                                                   | `ssh -n pro 'ls -la ~/.local/bin/nuzantara-repo-sync'` / `ssh -n mini '…'`                                | absent, both                                                                    | **absent, both** (`ls: … No such file or directory`, RC=1 on both hosts)                                                                                                                                                         |
| Repo canon                                                                                                                                                                                                                                               | `git ls-tree -r origin/main --name-only \| grep -i 'repo-sync'`                                           | 0 hits                                                                          | **0 hits** — the script and its plist exist nowhere under `scripts/`, `infra/`, or `apps/*/scripts/` on `origin/main`                                                                                                            |
| `declared-pairs.json`                                                                                                                                                                                                                                    | `grep -c 'repo-sync' infra/home-fork/declared-pairs.json`; pair count                                     | 0 hits / 110 pairs                                                              | **0 hits / 110 pairs** — confirmed no twin exists to declare (a declared-pairs entry needs a repo-side canon to compare the live copy against; this daemon has none)                                                             |
| Main checkout state (informational only — not touched by this record)                                                                                                                                                                                    | `git -C ~/nuzantara rev-list --count HEAD..origin/main`; `git -C ~/nuzantara status --porcelain \| wc -l` | ~120 behind, ~20 dirty                                                          | **121 behind, 20 dirty**                                                                                                                                                                                                         |

**Reconciliation of the one number that moved**: "OK pulled" stayed at 334 both days because the
daemon has not successfully pulled since 2026-08-04 — the growing "commit(s) behind" figure (120 → 121) and the static pull count agree with each other and with the daemon's own log line ("SAFE
tracked edits present; pull postponed"). No discrepancy to reconcile here; the daemon is currently
inert by accident of the dirty tree, not by design.

## Two options, recorded without a preference exercised

### Option A — RETIRE

Unload or disable the `launchd` job (`launchctl kickstart -k`/disable per the fleet memo — never
`bootout` on a job with detached children, per the M5 fleet runbook) and delete nothing else. No
CLAUDE.md doctrine changes. The daemon has never pushed (0 "OK pushed" in its entire lifetime),
exists on no other machine, has no repo canon, and its sole function — auto-pulling origin into the
main checkout — is the exact act the standing M5 doctrine (proprioception.py + Agent Worktree
Discipline) already prohibits. Retiring it removes the conflict by removing the daemon; the M5
doctrine is left unamended and needs no new exception carved into it.

### Option B — PROMOTE

Move the script + plist into `scripts/` and `infra/launchagents/` (hot-zone: lease-check + PR +
adversarial review per CLAUDE.md §7's guardrail set), repoint `REPO` from the `~/Desktop/nuzantara`
symlink to the canonical `~/nuzantara` path directly, add the pair to
`infra/home-fork/declared-pairs.json` (a separate ledger item, not this record — see Scope below),
write a runbook, and — the part that makes this option coherent rather than a silent policy
override — publish an **explicit, written exception** to the Agent Worktree Discipline invariant in
CLAUDE.md, naming this daemon and stating why a background auto-sync is safe alongside ~45 live
worktrees. Without that written exception, promoting the script would leave the repo documenting
one rule while running another — the same shape of doctrine/reality gap this record exists to close,
just relocated instead of resolved.

### What is recorded here, not decided here

Option A is the lower-blast-radius path on the evidence gathered: the daemon has never performed
its "push" branch in 1133 runs, has no cross-machine presence, and has no repo artifact for a
review to examine — Option B's first review, on the evidence of `api_server.py`'s 2026-08-06 first
CodeQL pass (7 high alerts and a production password in cleartext on first look, per the handoff
this record follows on from), is not free. That observation is offered as context for whoever
closes this record, not as an executed choice — closing either branch is out of scope for this
item (see Scope).

## Scope — what this record does NOT do

- Does **not** unload, disable, `kickstart -k`, or otherwise touch the `launchd` job or its plist.
- Does **not** promote the script into `scripts/`/`infra/launchagents/`.
- Does **not** add an entry to `infra/home-fork/declared-pairs.json` — impossible by construction:
  a declared-pairs entry needs a repo-tracked twin to hash against, and this daemon has none (0
  hits confirmed above). That fact is itself part of why Option A carries less residual risk than
  Option B, which would first have to create the twin this record found missing.
- Does **not** add alerting to a daemon whose disposition is still open — alerting a component that
  may be retired next would itself need retiring.
- Does **not** clean, pull, or otherwise mutate the M5 main checkout `~/nuzantara` to "unstick" the
  daemon. The 20 dirty entries currently blocking it are live sibling work — untracked
  `apps/backend-rag/backend/services/mail_loop/**` and `HANDOFF-zoho-mail-loop.md` — under the
  leave-dirty discipline of cicatrix superscar #5 (sibling-race). Touching them to make this
  daemon's postponement logic succeed would be curing a false problem by causing a real one.
- Does **not** write a `PENDING-ARMS.md` pointer line — per this lane's brief, that line is written
  by the ledger item that dispatched this record, not by this record itself.

## For the next reader

If you are here to close this: re-run every command in the measurement table above before acting —
this record is itself subject to Rule 1 (every number here is a measurement of 2026-08-07 and
expires). If the numbers still show 0 pushes and 0 repo canon, Option A remains the lower-risk
close. If either has changed — a push has happened, or the script has since been promoted from
somewhere else — that change is the new finding, not this one.

---

## Closure — 2026-08-08, Option A (RETIRE) executed

### The instruction above was followed: every row re-measured first

| Measurement                                              | 2026-08-07 (this record) | 2026-08-08 (at close)                                  |
| -------------------------------------------------------- | ------------------------ | ------------------------------------------------------ |
| `launchctl` runs                                         | 1133                     | **1315** (+182, consistent with 300s over ~15h)        |
| `OK pushed` — ever                                       | 0                        | **0**                                                  |
| `OK pulled`                                              | 334                      | **334** (no successful pull since 2026-08-04 07:47:17) |
| commits behind                                           | 121                      | **179**, still growing one cycle at a time             |
| dirty entries in the checkout                            | 20                       | **22**                                                 |
| repo canon under `scripts/`, `infra/`, `apps/*/scripts/` | 0                        | **0**                                                  |
| `declared-pairs.json` entries                            | 0                        | **0**                                                  |
| present on Pro / Mini                                    | absent, both             | **absent, both**                                       |

The closing rule this record wrote for itself — _"if the numbers still show 0 pushes and 0 repo
canon, Option A remains the lower-risk close"_ — holds on both sides.

### One correction, and it runs the opposite way from what the ledger assumed

`.claude/skills/modus/PENDING-ARMS.md` carried a competing claim: that `~/Desktop/nuzantara` is
_"a real, separate checkout (different inode from `~/nuzantara`)"_ — RETRACTED[desktop-nuzantara-is-a-separate-checkout]. **This record was right and
that line was wrong**, measured rather than argued:

```
$ ls -ld ~/Desktop/nuzantara
lrwxr-xr-x  /Users/balizero/Desktop/nuzantara -> /Users/balizero/nuzantara

$ stat -f '%d %i %N  type=%HT' ~/Desktop/nuzantara ~/nuzantara     # WITHOUT -L
16777233 166687231 /Users/balizero/Desktop/nuzantara  type=Symbolic Link
16777233 758478    /Users/balizero/nuzantara          type=Directory

$ stat -L -f '%d %i %N' ~/Desktop/nuzantara ~/nuzantara            # follows the link
16777233 758478 /Users/balizero/Desktop/nuzantara
16777233 758478 /Users/balizero/nuzantara

$ git -C ~/Desktop/nuzantara rev-parse --absolute-git-dir
/Users/balizero/nuzantara/.git
```

`stat` without `-L` reports the **link's own** inode, so comparing that against a directory's
inode manufactures a difference that does not exist. The form (two inodes) lied about the entity
(one checkout) — the same shape as constraint #2 of the handoff this record follows on from.

It matters because it makes the risk **larger**, not smaller: the daemon was never aimed at a side
copy it could churn harmlessly. It was aimed at the main checkout, and the 22 tracked edits that
have been postponing it since 2026-08-04 are live sibling work in that checkout. The moment they
cleared, an unattended `git merge --ff-only origin/main` would have landed on top of them.

### What was run

```
launchctl disable gui/501/com.balizero.nuzantara-repo-sync    # persistent, survives reboot
launchctl bootout  gui/501/com.balizero.nuzantara-repo-sync   # state was 'not running' → no detached children
mv ~/Library/LaunchAgents/com.balizero.nuzantara-repo-sync.plist{,.retired-20260808}
```

`bootout` is used here only because the job was measured `state = not running` first — the fleet
rule against `bootout` on a job with detached children stands unchanged. The plist is renamed with
the `.retired-<date>` suffix the reconciler already protects for 30 days, so it is recoverable, and
the script at `~/.local/bin/nuzantara-repo-sync` is left untouched: Option A deletes nothing else.
Reversal is `launchctl enable` plus renaming the plist back.

### PROVE-LIVE — the outcome, never the exit code

- `launchctl print gui/501/com.balizero.nuzantara-repo-sync` → **RC=113**, no longer loaded.
- `scripts/launchagent_reconcile.py` → **`HOME-fork target (superscar #1) (0)`**, down from 1, with
  `Zombie loaded` still 0 — the disable/bootout/rename left no orphan label behind.
- The daemon's own log stops growing across more than two 300-second tick windows. This is the one
  that actually proves it is dead; the two above prove only that launchd agrees.

### What is deliberately NOT done here

- The M5 main checkout is **not** pulled, cleaned or otherwise touched. It is behind by design, and
  its dirty entries are live sibling work (superscar #5).
- The CLAUDE.md "Agent Worktree Discipline" invariant is **not** amended. Option A exists precisely
  because retiring the daemon removes the conflict without carving an exception into the doctrine.
- The script is **not** promoted to repo canon, so it never gets the first review Option B would
  have required — and that review is not free: the last HOME-only script promoted without one,
  `api_server.py`, drew 7 CodeQL high alerts and a production DSN in cleartext on first look.
