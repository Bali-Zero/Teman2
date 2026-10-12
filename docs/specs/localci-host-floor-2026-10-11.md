# LOCALCI B15 — Pro's host floor of 90 GB, held through the run

Lane infra/localci, BLUE. Prior specs: `docs/specs/localci-sovereign-2026-10-07.md` (B6 start floor, B8 prune), `docs/specs/localci-gate-2026-10-06.md`.

## 1. Why

Zero's directive (2026-10-08, restated 2026-10-10): Pro keeps more than 100 GB free, always. **Zero, 2026-10-11: the floor is now 90 GB, lowered from 100.** The directive was breached on 2026-10-11 (against the old 100):

- the merger tick of 10:43:15Z started at `host_free_gb=111`;
- the pro.janitor journal (a 10-minute statvfs sample of `/System/Volumes/Data`, decimal GB) reads 111.085 at 10:35:40Z, then 106.677, then **99.612 BLACK** at 10:55:41Z.

The cause is the run, not a leak. The `ctx.backend-tests` shard container held a **9.66 GB** writable layer: `docker diff` shows 60,356 files added under `/opt/py311`, the job's own `pip install` from `/opt/wheels`, which re-runs verbatim on purpose, for parity. Between ticks the host sits at 111-114 GB.

What guarded Pro before this change, and why none of it knew Zero's floor:

| guard                                      | where                           | value  | blind spot                                      |
| ------------------------------------------ | ------------------------------- | ------ | ----------------------------------------------- |
| `--min-host-free-gb`                       | merger, once at tick start (B6) | 60     | not the floor; not re-read while the run writes |
| `LOCALCI_MIN_FREE_GB`                      | runner                          | 12     | the docker VM's floor, not the Mac's            |
| `VM_MIN_FREE_GB` + `MAX_IMAGES_PER_RECIPE` | prune (B8)                      | 15 / 2 | VM-internal; the host is not an input           |

## 2. Design

kubelet's node-pressure model: a soft threshold to start, a hard threshold to evict, image GC under pressure.

1. **One floor.** `HOST_FLOOR_GB = 90.0` (Zero, 2026-10-11, lowered from 100; merger constant, flag `--host-floor-gb`). Host free is the statvfs of `HOST_PATH` (`/System/Volumes/Data`, the path prune and the janitor read), in decimal GB.
2. **Start floor.** A run starts only at `HOST_FLOOR_GB + START_MARGIN_GB` (10) = 100 GB: `--min-host-free-gb`, default 100 (was 60); the wrapper's `MERGER_MIN_HOST_FREE_GB` default follows. The `skipped` / `host_below_floor` line keeps its shape and gains `floor_gb` (90) and `start_floor_gb` (100); the wrapper's heartbeat note prints `start_floor_gb=100` (the start floor), while the journal's `floor_gb` stays the pressure floor 90.
3. **Hard eviction.** While the runner's `plan` and `run` steps run, the runner leads its own process group and a watchdog reads the host every 5 s. Under `HOST_FLOOR_GB + EVICT_MARGIN_GB` (1.5) = 91.5 GB: TERM to the group, KILL after 10 s, then `docker rm -f -v` of the containers carrying this run dir's label (`org.nuzantara.localci.run=<run_label>`, the label `runner.run_label` sets and `reap_containers` already reaps by). Three failed statvfs reads in a row count as below the floor: an unmeasured disk does not keep filling. The `status` read is not watched: a verdict already produced is never undone.
4. **An eviction is the host's no-verdict.** The tick journals `{"kind": "evicted", "why": "host_below_floor_during_run", "free_gb", "floor_gb", "context_in_flight", ...}` and no `decision`. Nothing counts toward READY, nothing is enqueued, and the same `(pr, head, base)` is decided again on a later tick (the start floor then gates it). It is never a FAIL or an ERROR of the candidate.
   - **Rotation (M2).** triage treats `evicted` as an attempt for ORDER only: it enters `last` with its ts (behind every head not yet tried) and never `decided`. After `EVICT_CAP` = 3 evictions of one `(pr, head, base)` the key is skipped, with `{"kind": "skipped", "why": "evicted_cap"}` journalled once, until the base or the head moves. Without it the same oldest head would head the queue on every tick and starve the replays.
   - **Orphaned runner (L1).** `start_new_session` takes the runner out of launchd's job group, so a bootout or `kickstart -k` of the merger would leave it unguarded. The merger hands its pid in `LOCALCI_PARENT_PID`; the runner's `plan` and `run` watch that pid every 5 s and TERM their own process group when it is gone. No variable, no watcher.
5. **Image GC under host pressure.** A prune that finds host free under the start floor removes, by explicit tag through its existing path, every deps image that is not the newest of its recipe (fewest 48 h plan references first, then oldest), never the never-list and never the image of the run in progress; the wrapper's `--fstrim` follows. `host_pressure: true` and `host_free_gb` before/after are on the `prune` line and on the `merger prune:` line. The `builder prune` runs after those removals (as in the VM-floor branch), and the journalled rule names the cost: dropping a second-slot image means a cold rebuild of that recipe. The report counts `evicted` beside `errors` and `skipped`.
6. **Not touched.** uv, npm and Playwright caches stay `pro.janitor`'s.

Constraints kept: stdlib only; no `-f` on an image removal, no age prune; containers only by this run's label; no check is weakened.

## 3. Tests and mutants

`scripts/localci/tests/test_host_floor.py` (25), `test_prune.py` (5 `b15`), `test_merger_report.py` (evicted counted), `test_merger.py` (B6 floor tests re-pinned to 90/100). Mutants in `merger_mutants.py`: `floor-start-60`, `evict-disabled`, `evict-spares-containers`, `evict-kills-foreign-run`, `evict-as-fail`, `statvfs-fail-open`, `prune-host-pressure-ignored`, `evict-not-rotated`, `evict-cap-ignored`, `evict-cap-off-by-one`, `parent-pid-not-handed`, `parent-watch-unwired`, `parent-watch-pid-1`, `parent-gone-never`, `prune-pressure-no-builder-prune`, `prune-pressure-rule-silent-on-cost`; the B6 floor mutants re-pinned (`b6-wrapper-floor-99`, `b6-merger-floor-99`).

## B16 (2026-10-12)

Observed on Pro: three runs evicted by B15 left no `status.json`, and prune read "no status.json in the last 48 h" as "run in progress", so their four deps images (13.3 GB, reclaimable) stayed through host pressure; the next runs started short of disk and were evicted in turn. Cure: `prune.run_alive(run)` probes `state/coordinator.lock` with `flock(LOCK_SH | LOCK_NB)`; the run is in progress only while its coordinator holds it. A free lock or no lock file reads dead; a lock that cannot be opened or probed reads held (unknown keeps the image). Tests in `test_prune.py`: `test_b16_an_evicted_run_does_not_keep_its_image_under_host_pressure` (free and absent lock), `test_b16_a_lock_that_cannot_be_opened_counts_as_held`, `test_b16_the_lock_of_a_live_coordinator_process_holds_and_its_death_frees_it`. Mutants: `b16-dead-run-reads-live`, `b16-missing-lock-reads-live`, `b16-unknown-lock-reads-free`.

## 4. Bites

Consumer: the merger tick on Pro (`com.balizero.localci-merger`), which runs `merger.py` from `origin/main` at the tick's sha. Observe on the first tick after merge: its `merger_tick:` line shows the code sha; a run starts only at >= 100 GB, or a `host_below_floor` skip line carries `floor_gb=90` and `start_floor_gb=100`; over the next 48 h the pro.janitor journal's minimum `free_gb_before` is >= 90, or an `evicted` line names the trough it stopped.

**Deploy (M1).** The live wrapper on Pro (`~/.nuzantara-cron/localci_merger_tick.sh`, a declared home-fork pair) passes `--min-host-free-gb=$FLOOR_GB` explicitly, which overrides the merger default: until it is re-installed the start floor stays at 60. At deploy: `cp` from an `origin/main` checkout beside it, `mv -f`, then `cmp -s` (README, Retention section). Observable: `cmp -s` of the live wrapper against the `origin/main` copy is silent and `python3 scripts/lint_home_fork.py --check` is green for that pair; a `host_below_floor` skip line in the journal carries `start_floor_gb` 100 (the wrapper's start line does not print it).
