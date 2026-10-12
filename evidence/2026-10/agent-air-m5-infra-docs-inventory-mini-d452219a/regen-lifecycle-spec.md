# Spec: the bounded regen's process lifecycle (mini.docs_inventory_refresh)

This spec was written because the round-2 fix (a719f65355) was itself REWORKed. Kimi found that TERM to the wrapper
orphaned the setpgrp'd regen group. Under the fix-of-a-fix rule, the surface gets a spec before a third cure.

## Actors
- **W:** the wrapper, `bash`. It is the launchd job's main process.
- **H:** the perl helper. It is W's child and sits in W's process group.
- **G:** the regen process group. Its leader is the regen `bash`, forked by H and moved to its own group, so H's bound can
  kill the whole group without killing W.
- launchd stops a job by sending SIGTERM to the main process (W), and possibly to its group. After ExitTimeOut (60 s) it
  sends SIGKILL. When the job dies it kills the remaining processes of W's group, unless AbandonProcessGroup is set.

## Contract

| # | Event | Required outcome |
|---|---|---|
| L1 | The regen exits by itself | H returns the regen's rc (a signal death maps to 128+n). W judges it and on_exit removes the worktree. |
| L2 | The bound is reached | H sends TERM to G (group and leader), waits 2 s, sends KILL to G, reaps the leader and returns 142. No member of G is alive when H returns. |
| L3 | TERM, INT or HUP reaches H (group-signalled stop) | Same group kill as L2, then H returns 128+sig. |
| L4 | TERM, INT or HUP reaches only W (main-process stop) | W is not blocked in a foreground child. It waits on H in the background, so the trap runs at once and forwards TERM to H, then L3 applies. W waits for H and only then exits 143/130/129. on_exit removes the worktree after G is dead. The total stays well under ExitTimeOut, so launchd never escalates to SIGKILL. |
| L5 | A signal arrives between fork and the group being set | Both sides call setpgid (the child does it on itself, the parent does it on the child), so G exists when fork returns in either process. H also signals the leader by pid, not only the group. The child resets the inherited handlers before exec. |
| L6 | The bound value is not a positive integer | W logs it and uses 1800. `alarm 0` would silently disable the bound, so it must never happen. |
| R1 (residual) | H is SIGKILLed directly (manual `kill -9`) | G may outlive the run. The next run's sweep removes the stale run directory and worktree, which a live orphan loses. This is accepted and documented, because launchd only escalates to SIGKILL after ExitTimeOut, and L3/L4 end H in about 2 s. |

## Tests (one per row, each with a guilt run on the pre-cure wrapper)
- **L1:** the existing success and regen-fail cases.
- **L2:** the existing "regen tree kill" case, plus "a hung regen is bounded".
- **L3:** the regen-hang-tree case with a 1800 s bound. Start W in its own process group, wait for the child pid, then
  send `kill -TERM -<W pgid>`. Within 8 s W exits, the child is dead, the worktree is gone and the heartbeat is error.
- **L4:** the same, but `kill -TERM <W pid>` only.
- **L6:** `MINI_DOCS_INVENTORY_REGEN_TIMEOUT=0` with a quick regen gives an ok heartbeat and a "not a positive integer"
  line in the log.
