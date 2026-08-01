# Fleet lane dispatch — implementing on all three machines, in parallel

**Organ:** `scripts/fleet_dispatch.py` · **Roster:** `infra/fleet/nodes.json` ·
**Corpus:** `scripts/tests/test_fleet_dispatch.py` (armed in `.github/workflows/immune-enforcement.yml`)

Answers the two questions that come _before_ opening a lane, and that nothing in the
tree answered until 2026-08-01: **where can a lane go**, and **may it go there at all**.
It does not schedule, daemonize, or run the agent. It is a CLI you call, then you open
the session yourself.

## Why it exists

Measured on M5, 2026-08-01 12:07 WITA: the fleet was perfectly ALIGNED (M5, Pro and Mini
all on `8f2a3545e`, 0 behind) and perfectly IMBALANCED — normalized load **M5 0.78 · Pro
0.42 · Mini 0.19**, with Mini up 38 days and zero suite locks held anywhere. The fleet was
not saturated; the work simply had no way to reach the idle machine.

Everything needed to _run_ a lane already existed. What was missing:

- `scripts/agent_start.py` has no `--machine`: it derives the branch namespace from the
  local `socket.gethostname()`, so a session on M5 could only ever create worktrees on M5.
- `scripts/proprioception.py` has no load or memory probe at all; `scripts/fleet_watch.py`
  answers alive-vs-dark — liveness, never capacity.
- Nothing knew that a lane on Mini and a lane on M5 were editing the same file.

## Use

```bash
# Where can a lane go right now?
python3 scripts/fleet_dispatch.py capacity
python3 scripts/fleet_dispatch.py capacity --json          # machine-readable
python3 scripts/fleet_dispatch.py capacity --fetch         # authoritative `behind`

# Open a lane on the best node. --files is what makes it safe.
python3 scripts/fleet_dispatch.py place \
    --lane infra --task-id my-task \
    --files scripts/foo.py backend/bar.py

python3 scripts/fleet_dispatch.py place --lane docs --task-id x --files a.md --dry-run
python3 scripts/fleet_dispatch.py place --lane docs --task-id x --files a.md --prefer mini
```

On success `place` prints the `WORKTREE_READY <node>:<path>` line and the exact command to
enter the lane — locally `cd <path> && claude`, remotely `ssh -t <alias> 'cd <path> && claude'`.

## The quality half — why a collision is a REFUSAL, not a warning

`scripts/federation_parallelize.py` §4 cond. 2 (Google arXiv 2512.08296) already ratified the
finding this repo runs on: of the four kinds of parallelism, three are free and one is
actively negative — **coders on the SAME artifact degrade ~70%**. Parallelism that collides
is worth _less_ than serial work, so `place` exits 1 rather than printing a caveat someone
scrolls past.

Same doctrine as that module on ambiguity: **it resolves to serial.** A live lane whose file
scope cannot be determined — freshly created with nothing written yet (`empty`), or carrying a
git-quoted path (`opaque`) — blocks placement, because non-overlap cannot be _proven_. Override
with `--allow-unknown-scope` only after checking by hand.

Passing no `--files` skips collision checking entirely and says so loudly. Don't.

## What `place` buys you beyond convenience

A lane opened this way goes through `agent_start.py` on the target machine, so it gets
`.husky/_/pre-push` — which is gitignored and install-generated. A worktree made by a bare
`git worktree add` has **no pre-push hook at all**: its push runs no gate, takes 2 seconds,
exits 0, prints nothing. That is the `--no-verify` the fleet forbids, with extra steps.

## Verdicts

| Verdict     | Meaning                                                         | Placeable                |
| ----------- | --------------------------------------------------------------- | ------------------------ |
| `READY`     | load < 0.60/core, ≥ 2048MB available, no suite lock held        | yes (preferred)          |
| `BUSY`      | load ≥ 0.60/core, or a backend suite is mid-flight              | yes, if nothing is READY |
| `SATURATED` | load ≥ 1.00/core, < 2048MB available, **or signals unreadable** | no                       |
| `DARK`      | the node did not answer                                         | no                       |

Unreadable signals degrade to SATURATED, never to READY: an unknown reading is a reason to
withhold work from a machine, not to send it there.

Thresholds are env-tunable: `FLEET_DISPATCH_LOAD_BUSY`, `FLEET_DISPATCH_LOAD_SATURATED`,
`FLEET_DISPATCH_MIN_AVAIL_MB`, `FLEET_DISPATCH_SSH_TIMEOUT`.
Kill switch: `FLEET_DISPATCH_ENABLED=false`.

## Exit codes

| Code | Meaning                                                                     |
| ---- | --------------------------------------------------------------------------- |
| 0    | capacity printed / lane placed                                              |
| 1    | refused — no node placeable, files collide, or a lane's scope is unknowable |
| 2    | usage error                                                                 |
| 4    | **BLIND** — not one node answered; no verdict is possible                   |

Exit 4 is deliberate and is not exit 0. A sweep that probed nothing has not found nothing.

## Gotchas paid for in blood

- **Locale.** Zero's Macs run `LANG=it_IT.UTF-8`, under which `sysctl -n vm.loadavg` prints
  `{ 3,38 ... }` — a comma decimal that `float()` rejects. The probe exported `LC_ALL=C` only
  after the corpus, which _executes_ the snippet, caught every machine reading as SATURATED.
  A parser test would have passed happily on hand-written dot input. Pinned by
  `test_capacity_snippet_is_immune_to_a_comma_decimal_locale`.
- **The exit code is not the reply.** A node that exits 0 having printed no `FLEET_CAP`
  sentinel is DARK, not fine (W104).
- **HEADs are compared to each other, not to origin.** `capacity` reports AGREE/DIVERGE across
  nodes — a claim its own data supports — instead of trusting a possibly-stale local
  `origin/main` ref (W106b). Pass `--fetch` when you need `behind` to be authoritative.
- **No repo path is stored in the roster.** Every node resolves `$HOME/nuzantara` on the
  _target_, because M5 is `balizero` and Pro/Mini are `nuzantara` (superscar family #1).

## Related

- `docs/runbooks/agent-worktree-broker.md` — the per-machine worktree lifecycle this composes.
- `scripts/prepush_suite_lock.sh` — the per-machine single-flight lock `capacity` reads.
- `scripts/fleet_watch.py` — liveness sentinel (dark-node alarms), a different question.
