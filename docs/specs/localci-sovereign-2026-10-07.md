# LOCALCI-SOVEREIGN — the local gate decides, GitHub is storage

Ruling: `docs/rules/RULINGS.md`, RULED 2026-10-07 (Zero, option 3 of three). Supersedes the end state of
`docs/specs/localci-gate-2026-10-06.md`; that spec's measurements, per-context table and transition shape stay
valid. This document is the plan, with the acceptance of every phase and the order that never leaves `main`
without a gate.

## 1. End state

- Merges to `main` are decided by a gate that runs on our hardware (Pro first; Mini as the second host later).
- A **merger** on Pro, with its own GitHub identity, is the only principal allowed to push to `main`. It takes a
  pull request marked ready, builds the merge candidate (the PR merged into current `main`, as the queue does),
  runs the local gate on it, and merges through the API when green. Agent sessions keep opening PRs; none can
  push to `main` and none holds the merger's credential.
- GitHub keeps the code, the PRs and their history. Required status checks and the merge queue are gone.
  Hosted workflows may remain as advisory scans (CodeQL, Dependabot) if Zero keeps them; none gates.

## 2. Sequence — each phase lands with its proof before the next starts

| phase                                                     | what                                                                                                                                                                                                                                                                                                                                                                                                               | proof that it is done                                                                                                                                                                                                                 |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A** executor, light contexts (running since 2026-10-07) | `scripts/localci/runner.py` executes the required contexts from `contexts_matrix.yaml`, BASE-trusted, candidate code contained: R1, actionlint, Merah Putih, catE, organ genes, guard conformance, antidotes; CodeQL stays BLOCKED(github_hosted)                                                                                                                                                                  | `hosted_compare.py` on a merged hosted-green sha: AGREE ≥ 7 then ≥ 9, FALSE_GREEN 0; one guilt candidate per context goes RED locally                                                                                                 |
| **B** executor, service contexts                          | Postgres + Redis in docker on Pro for Backend Tests, E2E (Playwright), Visa Oracle smoke; Harness floor as an offline rule                                                                                                                                                                                                                                                                                         | AGREE ≥ 12 of 14 on merged shas; guilt per context                                                                                                                                                                                    |
| **C** merger                                              | a Pro daemon: lease per PR, merge candidate built from `origin/main`, full local gate, merge via API with ITS credential, journal of every decision; only same-repo PRs                                                                                                                                                                                                                                            | a PR merged by the merger in a sandbox repo or behind a label while GitHub still gates; the journal shows the candidate sha, the verdict and the merge sha                                                                            |
| **D** shadow                                              | the merger decides in parallel with GitHub without pushing; every disagreement is classified. A merge counts as COMPARED only when GitHub merged the decided candidate, once per PR. A compared merge needs ≥ 12 contexts compared on both sides, of which ≥ 11 `full` and at most 1 `partial`, the partial one named on the line (ruled 2026-10-08: 14 required − 2 CodeQL hosted-only − 1 E2E partial = 11 full) | READY only when compared merges ≥ 50 AND ≥ 14 days lie between the first and the last of them AND FALSE_GREEN = 0 at every level (ruled 2026-10-07: "or" was too thin — two merges 14 days apart read READY); FALSE_RED rate recorded |
| **E** the flip (operator)                                 | remove required checks and the merge queue; restrict push to `main` to the merger identity; sessions lose nothing they had                                                                                                                                                                                                                                                                                         | the first merge on `main` by the merger with no hosted check in the way; a PR pushed by a session is refused by branch protection                                                                                                     |

**Live state 2026-10-08 (read from Pro, not from the plan).** **A** running since 2026-10-07 (`com.balizero.localci-merger`, StartInterval 600, no KeepAlive; heartbeat `~/.organism/last_seen/pro.localci_merger.json`). **B** B1 merged as `ba445b84a1` (#8032: Backend Tests + Harness floor executed; 9/14 on the first tick after C3a-1, 2026-10-07T23:46Z, FALSE_GREEN 0, FALSE_RED 0) and B2 merged as `475fa4ff6d` (#8056: E2E, Frontend (mouth, true) and Visa Oracle smoke executed; first tick on main's code: `2026-10-08T07:47:45Z on PR #8060 (`f948538862`), run `pr8060-f94853886239-1cef6f665e5e-20261008T063148Z`: `executed_required 12/14`, E2E / Frontend (mouth, true) / Visa Oracle smoke OK and AGREE, hosted_compare 11/14 (AGREE 11, FALSE_GREEN 0, FALSE_RED 0, LOCAL_BLIND 3 = CodeQL ×2 + Backend Tests ERROR "backend-shard[2]: timeout after 1800s", a capacity symptom with the host volume at 97%, no verdict)`); the only LOCAL_BLIND left are the two CodeQL contexts. **C** C3a-1 live (#8036, `224d353e89`: READY on both thresholds, heartbeat from the mirror, `hosted_red_merged`, the PR number for the BASE runner); C3a-2 live (#8048, `0394e6beb7`: first `would_enqueue` line 2026-10-08T05:14:25Z on PR #8050, `armed_env:false`, five sub-criteria refused by name, `executed_required 9/14`; phase-E line ends `enqueued=0 would_enqueue=0 enqueue_refused=0 enqueue_error=0`); the label `localci:merge-shadow-ok` exists on the repo since 2026-10-08 and the flag `LOCALCI_MERGER_ARMED` is unset on Pro. **D** shadow since 2026-10-07T07:37Z: 51 decisions, 25 PRs, 10 merged PRs, `compared_merges=0` — a compared merge needs ≥ 12 contexts and the merger executed 9/14 until B2; the counter starts with B2's code. **E** waits on the operator (spec §3, §4). Owed before D can be read as READY: **B3** — nothing reads a context's `coverage` yet, so a `coverage: partial` AGREE (E2E) counts as full in `hosted_compare` and in the merger's compared-context count (cure: `coverage` per row in `hosted_compare`, partial AGREEs counted apart); a disk-full failure in a sandbox reads FAIL instead of no-verdict and no free-space floor runs before a sandbox starts (Pro's Colima VM is 58.8 GB, one backend shard writes ~7–10 GB; `docker rm -f -v` since B2 stops the volume leak). Hosted-side flakiness that removes queued PRs: cured on the `apt` surface by #8053 (`8c7ba3bbbe`, fallback to a direct second mirror, specified against the runner's real `mirror+file` pool).

**Phase C, step C3a-2: the merger enqueues.** After a verdict, `merger.py` evaluates one criterion on the decision it just
made and, only when it holds and the merger is armed, puts the PR in GitHub's merge queue through the GraphQL mutation
`enqueuePullRequest(pullRequestId, expectedHeadOid = the decided head)`. It never merges or pushes itself, and `merge` still
refuses. The sub-criteria, each of which alone refuses and is named in the line's `refused` and `why`:

- no check of its own is FAIL, ERROR, STALE, INTERRUPTED, RUNNING or QUEUED, except `review.independent`, which must be
  QUEUED or PASS;
- every executed required context is OK; a BLOCKED context passes only when its mapping is `blocked` or `not_implemented`, and
  the line names each one with its mapping beside `executed_required: N/M`;
- every context branch protection requires, read live and never hardcoded, is green on the PR head, red-dominant: failure,
  cancelled, timed out, action required, pending or missing refuses, while skipped and neutral pass as they do on GitHub;
- the PR head is still the decided head; the PR is same-repo, not a draft, based on `main`, open and not in the queue (GraphQL
  `isInMergeQueue` / `mergeQueueEntry`); this head was not enqueued by an earlier tick;
- the label `localci:merge-shadow-ok` is on the PR, applied last by an account whose repository role is admin or maintain.

The arm has two halves: that label, and `LOCALCI_MERGER_ARMED=1` in the tick's environment. Without both, the merger stays
shadow and journals `would_enqueue` with the same criterion, every sub-criterion true or false, and the head oid. That line is
the proof read before arming. The flag stays OFF until a proof PR shows `would_enqueue` with every sub-criterion true and only
`armed_env` refused. The proof PR is docs-only, judged by main's code, and NOT armed with `--auto`, so the merger's enqueue is
the only path into the queue. An enqueue journals `enqueued` with the queue entry id, its position and the head oid. A failed
mutation journals `enqueue_error` with GitHub's message, redacted, and is never retried in that tick. `report` prints
`enqueued` and `would_enqueue` on the phase-E line. Every write runs under the ambient `gh` token on Pro until Zero installs
the merger's own credential (§4.1).

**Phase B, step B5: a rewritten judge is no verdict, and a skip is compared as a skip** (RULED 2026-10-08, read from the first tick on B3's code, decision 09:49:54Z on PR #8076).

_The rewritten judge._ A context runs its trusted files from BASE (`trusted_base_required`, `trusted_from_steps`): the candidate never judges itself. When the candidate's diff rewrites one of those files (the plan's `judge_modified`), the BASE judge's run is not a verdict on the candidate in either direction: a green was already not claimed (`steps_verdict` → BLOCKED); from B5 a red is not claimed either — the BASE judge read red against a tool whose contract the same PR changes (#8076: a health state added to the tool, the registry and the test together; the BASE test knew four states, the candidate's tool five; hosted judged with the candidate's test and read green). The rule: a FAIL or ERROR on a step whose trusted inputs the candidate rewrote is `BLOCKED judge_rewritten: <step> read red with the BASE judge while the candidate rewrites <files>; hosted judges with the candidate's copy, which this run did not execute — no verdict (never FAIL, never OK)`; a red on a step whose trusted inputs the candidate did NOT rewrite stays FAIL (the scope is the step, not the context); `hosted_compare` classes it `LOCAL_BLIND`, never `FALSE_RED`; the C3a-2 criterion refuses it (an executed mapping that is not OK). What this does not do: it does not run the candidate's judge. A PR that rewrites a judge is the reviewer's (`review_independent`), and the gate's row says so; running both judges and reporting the pair is a later step if phase D shows judge rewrites are frequent (today: 1 of 60 decisions).

_The agreed skip._ A required context the trusted change_map does not select is NOT_APPLICABLE here and skipped hosted, and GitHub counts a skipped required context as satisfied. The two sides agree on a decision — the classifier's — and that agreement is compared, because a wrong skip would be a false green and must be seen. From B5 the row says what was compared: `local_detail: NOT_APPLICABLE (skip agreed: change_map)` when both sides skipped; `OK (executed; hosted skipped)` when the runner executed what hosted did not (counted full: more was tested here); `NOT_APPLICABLE (skipped here; hosted ran)` when hosted executed what the runner skipped — counted `partial` and named, because the local verdict is a subset of hosted's. The report prints `compared_skip_agreed=N` on the window line, apart from the executed agreements, and the phase-E line names how many of a compared merge's full contexts were skip agreements. The compared-merge rule (≥ 12 compared, ≥ 11 full, ≤ 1 partial) is unchanged: a skip agreement is a full comparison of the decision; it is never silently labelled `OK (executed)`.

**Phase B, step B6: the gate keeps its host above the floor — retention is part of every tick** (RULED 2026-10-08 under Zero's directive: Pro keeps > 100 GB free, always).

_Measured._ Pro's data volume fell 82 → 46 → 13 GiB free in 48 h with the merger running. The writer is the gate itself: five `localci-deps:<digest>` images in 24 h (1.4–11.9 GB each — a new backend image per lockfile change, a new E2E image per recipe change), 34 GB in the VM; and, on the host, Pysa receipts of ~630 MB per run that executes the taint judge (`receipts/pysa/{base,candidate}/results/*.json`), plus closed executor and gate directories nothing prunes because the janitor protects `~/.nuzantara-pilots` wholesale. The `LOCALCI_MIN_FREE_GB` floor (B3) refuses a leg under 12 GB; it reclaims nothing.

_The rule._ Every tick ends with a prune the merger owns and journals (`kind: prune`, what was removed, GB before/after, the rule that allowed each removal):

1. **Deps images** — a `localci-deps:*` image is removed when no plan of the last 48 h names it AND it is not the newest image of its recipe (backend / E2E / frontend, read from the plan that built it); removal is by explicit tag (`docker image rm <tag>`), never by `prune -a` or `until=` (the candidate image and `localci-deps-base:*` are never touched: lesson of 2026-10-08 07:48Z, when an age prune removed `localci-candidate:1` and blocked every contained context for a tick). After removals, `docker builder prune -af --max-used-space 4GB` on the gate's own builder — the cache is kept to a budget (`LOCALCI_BUILDER_CACHE_GB`, default 4, journaled as `builder_prune {rc, keep_storage_gb, flag, freed_gb, deprecated_flag, du_gb, tail}` of the last call, `runs` the number of calls, and the cache's size before the first and after the last), not by age, and with `-a`, since without it moby prunes only source.local, exec.cachemount and git-checkout records, never the layer records (B8; it read `--filter until=24h` until then, and at 2026-10-08T17:20Z the cache held 16.9 GB of which that filter could reclaim 0.5; at 17:23Z `-f --keep-storage 4GB` on a 16.93 GB cache removed 0 B; at 17:27Z `-af` after three image removals freed 20.98 GB). It runs after the cap's removals and again after each floor removal, so the entries tied to a removed image go with it. **Addenda (RULED 2026-10-08 14:00Z; measured at 12:05Z: a second E2E image of 11.9 GB beside the first, 46 GB of deps images in the VM, the host's sparse disk file 38 → 50.7 GiB in one tick).** Per recipe there are **two** slots: the newest image (named or not), and the one the most plans of the last 48 h name, ties going to the youngest reference (B8; it read "one that a plan of the last 48 h names" until then, and at 17:20Z that choice would have evicted the E2E image four armed PRs named to keep a younger one a single PR named); an unnamed image other than the newest takes no slot and goes whatever its age (the age guard of B6-1 is retired: the slots and the lease cover every image a live run can need, and a removal can cost a rebuild, never a verdict); beyond the slots an image stays only when the run holding the lease names it — a run of the last 48 h without `status.json`, since the prune takes the lease itself and never runs beside a live tick (B8 retired the 6 h clock grace: the armed queue of 10 PRs cycles through its lockfile states in about 2 h, every deps image was named by a plan under 3 h old, and the cap never bit); an exact `Created` tie with the newest and an image of an unrecorded recipe are kept (the safe direction); the prune takes the tick's lease (held → `skipped: lease`). The never-list is `localci-candidate:*`, `localci-deps-base:*` and every `service_images` stand-in of the BASE matrix (`postgres:15`, `redis:7` today — read from the matrix at the tick's sha, never hardcoded; an unreadable matrix keeps every image and the prune exits 1, while the builder prune and the run-dir trim still run): the 07:48Z age prune also removed the stand-ins, and the 11:37Z backend tick was BLOCKED "stand-in image 'postgres:15' is not present". Shipped in #8107 `a43431d355`; armed on Pro 2026-10-08T14:25Z (wrappers and plist `cmp`-equal to `origin/main`). **Addendum B8 (RULED 2026-10-08; measured on Pro: the Colima VM's `/var/lib/docker`, 60 GiB, reached 100 % at about 15:27Z and every contained context read ERROR/BLOCKED from then on — no verdict, so no false green, B3's rule held; `vm_free_gb` read 0.0 in every prune line and fstrim returned nothing on a full VM; at 17:20Z images held 58.85 GB — four E2E images of 5.35 GB each, the oldest named by four armed PRs, four frontend images of 0.46 GB, two backend images of 4.64 GB — and the build cache 16.93 GB; recovered by hand at 17:3xZ, journal `~/logs/vm-recovery-20261008.log`).** A **VM free floor outranks the slots**: after the cap, while the VM's free GB (`vm_free_gb.after`, B3's probe) is under `VM_MIN_FREE_GB` (15, env `LOCALCI_VM_MIN_FREE_GB`, read like `LOCALCI_MIN_FREE_GB`), images go fewest plan references of the last 48 h first, ties to the oldest, the builder pruned and the free GB re-read after each, until the floor is met or nothing removable is left. Under the floor the newest-of-its-recipe protection is suspended: only the never-list and what the lease run names are untouchable (amended 2026-10-08 after 17:26Z, when a 4.4 GB pass was refilled by the very next tick: build cache 16.9 → 21.8 GB, the VM at 0 free again). Each such removal's rule reads `vm floor: VM free X GB < 15 GB after the cap; N plan(s) of the last 48 h name it, built H h ago` (`undated` when the image has no readable `Created`) — at 17:20Z the oldest E2E image was named by 4 armed PRs and the newest by 1, so this order buys one rebuild where oldest-first bought four, and the line carries `vm_floor {floor_gb, removed, met}`, or `skipped` on a dry run, an unreadable input, or a VM whose free space could not be measured (the floor acts on a measurement, never on its absence). Images that are not the gate's (`osint-neo4j` and its volumes, 7 GB at 17:20Z) are never the prune's: it lists `localci-deps:*` only. _Measured arithmetic._ Two images per recipe for three live recipes is about 46 GB, plus 7 GB that are not the gate's, plus about 12 GB of scratch for one build: more than the VM's 60 GiB. A 60 GiB VM holds at most ONE image per recipe plus the scratch of one build when three recipes are live; the floor, not the slots, is the rule that holds. B9 (a recipe keyed on the merge result, the open question below) is what makes the slots meaningful again.
   - **B13 addendum (2026-10-10).** buildx 0.34 deprecated `--keep-storage` into the floor `--reserved-space`: on Pro it freed `Total: 0B` of a 22.83 GB cache with rc 0, a green line that freed nothing. The flag is now read once per prune from `docker builder prune --help` (`--max-used-space`; `--keep-storage` only on an old buildx; `--max-used-space` when the help is unreadable). The failure is the entity, not a size: `deprecated_flag: true`, and `failed` naming `builder_prune`, when a line of a call's output names the flag we passed and says it is deprecated or `has been changed to`. `freed_gb` is the sum of buildx's `Total:` lines (record sizes, not disk bytes) and `du_gb {shared, private, reclaimable, total}` is read from `docker buildx du` after the last call; both are measurements and never a verdict, because BuildKit's cap accounting is opaque (Pro, live: after `--max-used-space 4GB` 10.29 GB stayed reclaimable). Image removal rules, floors and VM discard are unchanged.
2. **Run directories** — a run keeps everything for 7 days; after that `logs/` and the Pysa call graphs (`call-graph.json`, `higher-order-call-graph.json`) go and `status.json`, `hosted_compare.json`, `state/plan.json`, `state/journal.jsonl`, `receipts/*.junit.xml`, `receipts/*.json` (small) and `taint-output.json` stay — the journal `decisions.jsonl` is the record of record and is never pruned; after 30 days a run keeps only `status.json`, `hosted_compare.json` and `state/plan.json`.
3. **VM blocks back to the host** — every real prune (not a dry run, not a lease skip) ends with `colima ssh -- sudo fstrim -av`, whether or not an image went: the blocks a run frees are returned to the host at the end of the same tick (measured 2026-10-08T15:16Z: 11.4 GiB returned with no removal, 2 s); the tick reads the host's free GB before and after and journals both (B7, RULED 2026-10-08; it read "after any image removal" until then).
4. **The floor is watched, not assumed** — a launchd organ `pro.disk_floor` (registry `apps/organism/organism/organs_registry.yaml`, wrapper `scripts/ops/pro_disk_floor_tick.sh` with its home-fork declared pair, StartInterval 1800, no KeepAlive) writes `~/.organism/last_seen/pro.disk_floor.json` with `status: ok` above 100 GB free, `warning` between 100 and 60, `failed` under 60 (the heartbeat library writes it as `status: error` with the note prefixed `failed:`), the free GB in `note`, with the three biggest top-level directories when the status is not `ok`; the merger's tick refuses to START a run (journals `skipped: host_below_floor`) when the host has less than 60 GB free, so the gate never finishes the job of filling the disk.

_What this does not do._ It does not delete evidence of a decision (receipts that carry a verdict stay), it does not touch anything outside `~/.nuzantara-pilots/local-ci/merger/` and the gate's own docker objects, and it does not replace the one-shot cleanup of 2026-10-08 (contract + review + execution under `~/logs/pro-disk-cleanup.log`), which brought the host back above the floor.

_B9, closed by measurement (2026-10-09T05:00Z; it was written as an open question)._ The question was whether the deps recipe, keyed per candidate tree, made PRs that never touch a lockfile differ by the main they branched from. It does not. Over the plans of the 17 h before, the main-based PRs (pr7961, 7962, 8093, 8101, 8118, 8120, 8131) named ONE image per recipe across seven different bases (e2e `285e7c11`, backend `76c8ea4a`, frontend `1cd374ee`); the only PRs with images of their own were the five armed dependabot PRs that change a lockfile (pr7979, 7943 and 7945 `package-lock.json`, pr7944 the backend `requirements*`, pr7978 `apps/wa-mirror/package-lock.json`), each kept its own tag as its base moved (pr7979 `1b7ca87c` over four bases, pr7943 `b1c38e03` over four, pr7978 `c695dca1` over five). A recipe keyed on the merge result would change nothing. What churns the VM is those PRs being re-judged every cycle, each rebuilding an E2E image of 5.35 GB unique once the floor has evicted it; three of them read CLEAN and armed on GitHub since 2026-10-05/06 and were never enqueued. The remaining constraint is measured, not solved: an E2E leg writes 12.7 GB of container scratch (2026-10-09T04:31Z, pr8131), so that tick, which started at 16.1 GB free, bottomed out at 3–4 GB, and one starting at the 15 GB floor would keep about 2.3 GB; a tick that must also rebuild a deps image can run out, and then its contexts read no verdict (B3), never a false green. Growing the VM's 60 GiB disk would spend the host's free space, which the owner's floor (> 100 GB free on Pro) forbids.

**B10 (RULED 2026-10-09): a stale hosted verdict is `HOSTED_STALE`, never FALSE_GREEN.** The journal's only FALSE_GREEN of 84 decisions (2026-10-08T18:25:57Z, pr7961 `Backend Tests (Python)`) was hosted red from 2026-10-06T02:54Z on `refs/pull/7961/merge` of that day (`pip-audit` failing on pins main fixed in #7965 and #7996 afterwards) beside a local green on main of 10-08; the comparator joined on the PR head and compared no timestamp. A compared row whose hosted verdict completed before the base the local run used, with main changed in between in a path the BASE change_map selects for that context, is `HOSTED_STALE`: counted apart, never a compared context, only on evidence (otherwise the class is kept and `stale_check` says `unknown`); `merger.py report` re-reads recorded FALSE_GREEN rows with the same rule and READY reads the remainder. The ≥ 12 compared contexts of a compared merge are unchanged.

**Addendum B8b (RULED 2026-10-09): the prune keeps online discard on the VM's data disk.** Measured on Pro: the Colima VM's disk (`/dev/vdb1`, ext4, `rw,relatime` on `/mnt/lima-colima`, bind-mounted on `/var/lib/docker`) is a 60 GiB sparse file on the host (`~/.colima/_lima/_disks/colima/datadisk`), trimmed once per tick, at the end (B7). A read-only sampler (2026-10-09, every 20 s, `~/logs/vm-sampler-20261009.log`) showed that inside a tick the datadisk's host allocation climbs to 54.0 GiB while the VM uses only 36.6-40 GiB: 14-17 GiB of blocks the VM already freed (finished legs' containers and layers) return to the host only at the end-of-tick trim, and the host's free space fell to 104.0 GiB at 12:07:08Z (100.3 GiB at 10:29:44Z, another session's read) against the owner's floor of more than 100 GB free at all times. At 12:07:47Z the disk was remounted by hand with online discard (`mount -o remount,discard /mnt/lima-colima`). Mount options do not survive a VM restart, so before the fstrim every real prune (at the end of a tick: the first tick after a VM restart runs without discard, the next ones with it) reads `/proc/mounts` in the VM, matches the mount-point field and the comma-split options (never a substring), remounts with `discard` if it is off and reads again, and journals `vm_discard {before, after, remounted, rc, error}` (`failed: ["vm_discard"]` only when a remount was attempted and `after` is not true — false, or null when the re-read failed; a read problem is journalled and stops nothing; `LOCALCI_VM_DISCARD=0` skips it). Bites owed: since the hand remount of 12:07:47Z is still in force, the first prune line on Pro reads `vm_discard {before: true, after: true, remounted: false}` (the parser on the real table); the remount branch is proven live by a hand prune between ticks after a hand `remount,nodiscard`, or by the first `remounted: true, after: true` line after the next VM restart; and a second host sample whose intra-tick minimum is above 104.0 GiB with the allocation tracking the VM's usage.

**B11 (RULED 2026-10-09): the merger also replays the commit GitHub merged.** Measured on Pro (report of 2026-10-09T06:33Z, window from 2026-10-07T07:37Z): of 26 merged PRs only 9 were merged by GitHub onto the base the local gate decided; 17 (65 %) were merged onto a main that had moved during a 10-48 minute tick, so `compared_merges` stood at 1 after two days and phase D's >= 50 over >= 14 days was unreachable, not slow. The merger therefore also judges, as a _replay_, the exact main commit that merged a PR: candidate = that commit, BASE = its first parent (already on main, trusted), hosted verdict read on the same sha; replays alternate with PR decisions (a replay when the previous decision was not one, or when no PR is waiting), once per merge commit, newest first (B11b, RULED 2026-10-09 after the first live replay: oldest first, the first replay at 09:54Z judged pr8015's merge of 2026-10-07 on a base whose runner executed no context — 14 LOCAL_BLIND, BLOCKED — and 81 more merges of 10-07/10-08 stood between it and the first base on which a PR decision compared 12 contexts, `86b151beec` of 2026-10-08T15:51Z (the decisions before it compared 0-9: the runner gained its contexts step by step, B1-B4, and the VM was full from 15:27Z to 17:27Z); with main taking 31-56 merges a day against about one decision an hour, oldest first never reaches the present, and each old lockfile costs a deps image of its own). Newest first, a merge can be seconds old at the fetch: a commit whose PR GitHub still shows open is asked again on the next replay turn instead of being journalled `replay_unmapped` for good. A replay that meets the unchanged per-merge thresholds (>= 12 contexts compared, >= 11 of them full, <= 1 partial) is a compared merge by the existing definition, a PR counting once. The READY terms of phase D do not change either: FALSE_GREEN 0 over the whole window (a replay's false green counts there and is never reclassified as stale), >= 50 compared merges, >= 14 days between the first and the last.

**B12 (2026-10-10): a gate verdict not posted yet is no verdict, and is asked again once it is posted.** Measured on Pro 2026-10-09: 10 of the 12 `FALSE_RED` decisions were `ctx.harness-floor` failing at "Gear >= 2 — read the real gate verdict" because the PR's session had not yet posted `harness/fable-gate`. The reader's `::error::harness_gate_read: PENDING` stderr line (matrix key `pending_when`, line-anchored, not retried) becomes `rc: None` → BLOCKED → BLIND; the decision records `gate_pending: true`; `triage` decides the key again only once the head carries the status AND the hosted run of each pending context completed after it (two read-only GETs per PR per tick), at most 3 times per `(pr, head, base)`, then `skipped: gate_pending_cap`. A real failure verdict stays FAIL. Fix round (gate findings on `3d7146932a`): the hosted re-run condition (a re-decision beside the pre-post PENDING red would be a FALSE_GREEN that never clears), `gate_pending` only on a BLOCKED decision, the context marked from a structured flag frozen in the plan and never from its reason text, the matrix line tied to the BASE reader's own output, and the report count of non-replay decisions. See `scripts/localci/README.md` (B12).

**B14 (2026-10-10): the sandbox indexes the candidate tree from a pack the host builds once per run** (`runner.build_tree_pack`, `steps_driver.index_tree`): `git add -A -f` + `repack -a -d` per git_index container cost 62.8 s per container on Pro (about 19 of a tick's 49 minutes); `index-pack` of a shipped pack + `read-tree` + `add -A -f` + `repack -d` costs 9.5 s with the same tree, index and clean status. A bad pack raises (no verdict); an unbuildable pack falls back to the old path with a log line. See `scripts/localci/README.md`, "Sandbox git index (B14)".

**B12b (2026-10-10): a hosted verdict given before the gate verdict the local run read is `HOSTED_STALE`, not a disagreement.** Named by the B12 gate as a residual: the session posts `harness/fable-gate` after GitHub's `pull_request` run of `Harness floor recompute` already failed on the PENDING read, then re-runs it; a local decision between the post and the re-run reads `success` beside the pre-post red, a context FALSE_GREEN B10 never clears. For a compared row whose hosted verdict is RED and whose BASE matrix entry has a `pending_when` step (structural, never a name), the row is `HOSTED_STALE` with `stale_why: gate_posted_after_hosted` only when every red is a check run that completed before the newest `harness/fable-gate` status dated at or before the run's plan time (`state/plan.json` `created_at`), and each one's failure annotations are the reader's PENDING line plus at most the runner's `Process completed with exit code N.`, nothing else. Fix round (gate NO-GO on `6fad79e1c1`): the anchoring status must be `success` and the plan must have frozen rc 0 for the reader step (else a real disagreement, kept); every red must conclude `failure`; the red run's job (`actions/jobs/{id}`, its `check_run_url` naming that check run) must have failed on the reader step alone with every later matrix step skipped; 50 or more annotations is unknown; the tick journals each RED row's `hosted_red` and the report finds every one of them again by id. Unknown keeps the class; not compared, as B10's; the tick, the report's comparison and its re-judgement of recorded rows apply it. See `scripts/localci/README.md` (B12b).

Phase E never precedes D. If D shows a false green, the flip waits and the executor is fixed first. The operator reads `compared_merges`, never the age of the window: error lines and undecided ticks age a journal without proving anything.

_Phase E, prepared (2026-10-10)._ `scripts/localci/phase_e_flip.py` (README, "Phase E flip"): a read-only plan by default; the operator's `--apply` rewrites `merge-queue-main` (merge queue out, `update` in, the DeployKey bypass its only actor) and then deletes the classic protection of `main` — which the flip needs as much as the ruleset: classic protection requires a pull request and the 14 checks and exempts no deploy key, so the phase F credential paragraph's ruleset bypass alone would leave the merger's push refused. Deletion and force-push stay forbidden by the `Copilot review for default branch` ruleset. Refused unless the plan's digest is confirmed, the report is READY and fresh, and exactly one write deploy key exists and is the merger's; every write obeys the README's write discipline; the pre-flip state is saved for `--rollback`.

_Addendum — Write discipline, RULED 2026-10-10 (lead)._ Quiescence is a precondition of `--apply` declared by the operator (`--quiescent`: no session, peer or cron writes rulesets or branch protection during the run); W1 a fresh read of the planned state immediately before every write, the first included ("changed since plan": no write); W5 a read-back after every write against the intended state (a mismatch stops and prints the rollback file). Residual accepted: GitHub's REST API has no compare-and-swap for rulesets or branch protection; quiescence takes concurrent writers out of scope and W5 detects a lost race. Findings of that class beyond W1/W5 are out of scope by this ruling.

**Phase F — local main authority: the merger merges, GitHub stores** (RULED 2026-10-08, Zero's direct directive in session).
**What changed.** Zero's directive of 2026-10-08: the local CI must carry every required check and everything needed to replace GitHub completely; `Bali-Zero/Teman2` will be deleted once Subhi's curated **showroom** repository exists (product code only, never the harness — `~/Desktop/nuzantara-anatomy-en.pdf`, 8 October 2026, maps 09 and the six-step extraction plan); GitHub becomes storage. Phase E as written (flip the ruleset so the merger's enqueue is the only path into GitHub's merge queue) still lets GitHub execute the merge. Phase F replaces the executor, not the decider: the merger that today journals `would_enqueue` fast-forwards `main` itself.

**The mechanism.** The mirror the tick already fetches (`~/.nuzantara-pilots/local-ci/merger/repo.git`, `refs/merger/base`) becomes the authoritative `main`: on a decision that meets the C3a-2 criterion (every sub-criterion, the label, the flag) the merger (1) re-verifies `head_unchanged` and that the candidate's merge-base is the mirror's current `main`, (2) creates the merge commit in the mirror (`git merge --no-ff` of the decided head, the decision id and run dir in the message, `Bites:` carried from the PR body), (3) runs the post-merge seal (the merged tree's sha is journaled as `merged`, with the decision it rests on), (4) pushes `main` to GitHub as storage (`git push origin main`), and (5) marks the PR merged by that push (GitHub closes it as merged when `main` contains its head). A push that GitHub refuses is journaled `push_refused` and the mirror keeps its `main`: the storage lagging the authority is a reported condition, never a reason to re-decide. Candidates arrive as today (branch pushed to GitHub, PR opened, label applied); after Teman2 is deleted they arrive as branches pushed to the mirror over SSH (Pro, Tailscale) and the PR body becomes a `candidate.yml` next to the branch; the criterion's `label_privileged` becomes a signed line by an admin seat; nothing else in the criterion changes.

**The credential (operator[secret], created under the directive).** A write deploy key for the merger, generated on Pro (`~/.nuzantara-pilots/local-ci/merger/deploy_key`, 0600, never printed), registered on the repository with write, and a ruleset bypass for actor type `DeployKey` on `merge-queue-main`; the GitHub App of the phase-C ledger row is not needed. The key pushes `main` only; the tick's wrapper exposes it to `git push` through `GIT_SSH_COMMAND`, never to the runner's model-visible env.

**READY is unchanged.** Phase F arms only when phase D is READY (≥ 50 compared merges over ≥ 14 days, `FALSE_GREEN` 0 at every level); the window counts from the first compared merge and nothing in this phase shortens it. Until then phase F's merge path stays shadow (`would_merge` lines, no merge in the mirror, no push); the C3a-2 enqueue arms on its own proof, as ruled above, and is not gated on READY.

**What stays with Subhi.** The showroom export (which capability, its closure, its acceptance from a clean checkout) and when the old repository is deleted. The local CI runs the showroom's checks the same way (a second `contexts_matrix.yaml` for that repository, BASE-trusted, receipts and seals) — a phase G once the first export exists.

_Status._ F1 (shadow `would_merge` lines, the merge rehearsed with `git merge-tree --write-tree` against GitHub's main read with `git ls-remote`, no ref written, nothing pushed) shipped 2026-10-09.
_Status._ F2 (the executor, disarmed by construction) built 2026-10-10: `merger.py` merges and pushes only when ALL hold at the moment of merging, each failing one named in `phase_f.why` on the `would_merge` line — `LOCALCI_MERGER_PHASE_F=1`; READY recomputed in the tick by the report's own function (evaluated only when the env half and every local condition already hold, so a disarmed tick pays for neither the precheck nor the report); the enqueue step `would_enqueue` (`LOCALCI_MERGER_ARMED` unset in phase F) and F1's tree equal to the judged candidate's; `<state>/deploy_key` a regular file, 0600, owned by the running user; the C3a-2 criterion as `enqueue_step` computed it; F1's `clean` and `base_current`; the PR head re-read; no sticky `<state>/phase_f_halt`. The merge commit is made with `commit-tree` (parents: base, head; subject `<title> (#N)`), the push is plain (a rejection is `push_refused` plus the sticky halt), and the fetch refuses to rewind a main phase F pushed (`storage_diverged`, halt). Not armed anywhere: the armed path's live proof is owed to the day READY holds.

**Arming checklist (phase F proper), in this order.** `main` also carries CLASSIC branch protection (14 required status checks, required pull-request reviews present with 0 approvals, `enforce_admins` true), which no deploy key can bypass: a direct push to `main` is refused until it is removed. The DeployKey bypass on `merge-queue-main` is necessary but not sufficient.

1. Phase D READY (`merger.py report` reads `phase E READY`).
2. The write deploy key generated on Pro at `<state>/deploy_key` (0600, owned by the tick's user, never printed) and registered on the repository with write, and github.com's host key pinned into `<state>/known_hosts` (the push runs `StrictHostKeyChecking=yes` against that file alone) — operator[secret].
3. The phase E flip: `scripts/localci/phase_e_flip.py --apply` (lands in its own PR, not on main yet): `merge-queue-main` restricted to updates with the DeployKey bypass, then the classic protection deleted — operator[gui].
4. The live wrapper re-installed and identical to main's (`cmp -s` of `~/.nuzantara-cron/localci_merger_tick.sh` against an `origin/main` checkout — until then it force-fetches `refs/merger/base`, and a storage divergence rewinds it), and `LOCALCI_MERGER_ARMED` unset (with it set, every armed decision is `enqueued` into GitHub's queue and phase F never acts).
5. `LOCALCI_MERGER_PHASE_F=1` in the tick's environment (the launchd plist) — only after steps 3 and 4, because before them the first push is refused and writes the sticky halt.

Until then every `would_merge` line says `armed: false` and names why. To stop: remove the env, or `touch <state>/phase_f_halt`. To resume after a `push_refused` or `storage_diverged`: read the reason in the halt file and the journal, reconcile GitHub's main with the mirror, then remove the file.

### Phase F intake without GitHub (RULED 2026-10-11, revision 4)

For the day `Bali-Zero/Teman2` is deleted with its history (`docs/runbooks/zero-cutover.md`, gate 9), under Zero's rulings of 2026-10-11 (`docs/rules/RULINGS.md`, #8263; R-A and R-B below). Revision 3 (#8267) made the move an allow-list (0b). On Pro `nuzantara` is in `admin`, so neither "root-owned" nor "the operator" was session-free: revision 4 moves every ceremony to a session-free account (R-A, 0a) and walks the trust path every tick (R-B, precondition 5).

- Invariants: every judge runs from BASE (`refs/merger/base`), no secret enters a model-visible environment, sessions keep building.
- Still owed by Zero: the deploy key and phase E (gate 1). Facts read on Pro and on `origin/main`, 2026-10-11.

**0. Preconditions: the gate leaves the sessions' user.** Today `nuzantara`, the user of every Pro session and `ssh pro` key, owns the whole chain (LaunchAgent, wrapper, venv python linked into `~/.pyenv`, state dir, `repo.git`, journal, `/opt/homebrew/bin` first on `PATH`, the Colima socket, the `xcode-select` dir the `/usr/bin/git` shim runs), so a session could rewrite `refs/merger/base` or the judge. Before arming:

1. `localci` (C1) owns `/Users/localci/merger`, every ancestor root- or `localci`-owned and not group- or world-writable; its home is `root:wheel` 0711, so `~localci/hooks`, `~localci/bin` and `~localci/.ssh` have root-only ancestors. No usable password, but enabled with a real shell: Pro runs `UsePAM yes`, and a disabled account fails PAM (Q3).
2. The merger is a LaunchDaemon (system domain, `UserName localci`, C12); wrapper, interpreter, code and hooks are root- or `localci`-owned.
   - Interpreter: python.org 3.11 (C4), root-owned, group write stripped; never a copy of `~/.pyenv/versions/3.11.11` (`-I` still runs `site`, so a planted `.pth` executes; the CLT python is 3.9.6). Standard library only.
   - Daemon, hooks and `intake-shell` run with `PATH=/Library/Developer/CommandLineTools/usr/bin:/usr/bin:/bin:/usr/sbin:/sbin` and `GIT_NO_REPLACE_OBJECTS=1` (missing today from `GIT_ISOLATED` and the wrapper, so a `refs/replace/*` ref swaps what every merger git call reads), calling the CLT's `git`/`git-shell`, `/usr/bin/ssh-keygen` and `/usr/bin/ssh` by absolute path.
   - Docker: root-owned `/usr/local/localci/bin/docker` (C3), named absolutely in `runner.isolation_spec`; `shutil.which` is never called (on that `PATH` it finds nothing; with brew first, a session-owned binary).
   - Wrapper: root-owned `/usr/local/localci/bin/localci_merger_tick.sh` (C12); fetches nothing; runs the heartbeat library from `~localci/code/current`, never `<state>/heartbeat.sh`; heartbeats `warning` while its bytes differ from `code/current`'s copy (superscar #1).
   - **Heartbeat**: not in `~nuzantara/.organism` (session-owned, unwritable for `localci`) but under `ORGANISM_LAST_SEEN_DIR=/Library/LocalCI/heartbeat` (`localci:wheel` 0755, C5): `pro.localci_merger.json`, 0644 (`Umask 18`), written by temp file and rename inside that dir.
3. sshd (C2): Pro has `PasswordAuthentication yes`, `KbdInteractiveAuthentication yes`, no `AllowUsers`; `localci` gets publickey only, `zero-ops` no method at all.
4. The executor stays session-owned (Q7: error, not attack): `localci` reaches nuzantara's Colima socket via `DOCKER_HOST`, with `staff` membership to traverse `~nuzantara` and a socket ACL a nuzantara LaunchAgent re-applies whenever Colima recreates it; that agent also takes the `colima` upkeep (`prune.keep_vm_discard`, fstrim), which as `localci` would be session code.
5. **Trust-path walk, every tick (R-B).** With `nuzantara` in `admin`, an admin-group-writable file is session-writable whoever owns it. Every file under each root, and every ancestor to `/`, must be root-owned and not group- or world-writable. The root-owned wrapper walks before the interpreter starts (a planted `.pth` runs at start-up), `/usr/bin/find -L <root> <prunes> -prune -o \( ! -user root -o -perm -020 -o -perm -002 \) -print -quit` plus a `stat` per ancestor, and `intake.py` repeats it among item 6's conditions. Output or a non-zero exit (an unreadable dir) halts: `intake.arm` `armed: false`, a `trust_path_violation` line (path, owner, mode), heartbeat `error`, exit before any judge; the hooks follow as the arm lapses. Roots: `/Library/Frameworks/Python.framework/Versions/3.11` (prefix and site-packages, which python.org's installer leaves `root:admin` group-writable: C4 strips it); `/usr/local/localci/bin`; `/Library/LocalCI` minus `heartbeat/` (output only) and `archive/` (root 0700, never read); `~localci/hooks`, `~localci/bin`, `~localci/.ssh`; the CLT's `usr/bin/git`, `usr/bin/git-shell` and `usr/libexec/git-core`; `/usr/bin/ssh-keygen`, `/usr/bin/ssh`, `/bin/bash`, `/bin/sh`.

**0a. The operator account (R-A).** `zero-ops`: admin, used by no session, no ssh method (C2), no key, a password only Zero knows, entered at the console or by Screen Sharing, never by `su`/`ssh` from a `nuzantara` terminal (a session shares that tty). Every ceremony (C1–C12: the `localci` user, sshd, root-owned binaries, `ssh-keygen -K`, the READY seal, the gate-9 marker) runs there in a clean shell, `/usr/bin/env -i HOME=/Users/zero-ops PATH=/usr/bin:/bin:/usr/sbin:/sbin /bin/zsh -f`, the token attached and signing inside it. C0, creating `zero-ops`, runs from an existing admin login or System Settings.

**0b. The move is an allow-list.** Two things cross from the sessions' side: `marker.base`'s object closure, fetched into a fresh repository, and the seal and marker texts, once verified against a key no session can write. The operator or the daemon writes every other file; the rest stays behind, archived root-owned, never parsed:

- the old `repo.git`: its `config` (a repo-local `merge.<x>.driver` runs during `merge --squash` under `GIT_SAFE`/`GIT_ISOLATED`; `include.path` loads), `info/attributes`, alternates, commit-graph, grafts, packed-refs, `refs/replace/*`, and the `refs/candidates*`, `refs/candidate-admit/*`, `refs/gate/fable-gate/*`, `refs/candidates-merged/*` that never passed `pre-receive`;
- the `base/<sha>` and `cand/` worktrees: `fresh_worktree` reuses one whose HEAD matches and whose `status --porcelain` is empty, which `--skip-worktree` over an edited `runner.py`, or an ignored `.pyc`, keeps true;
- `runs/`, `heartbeat.sh`, `decisions.jsonl`, `intake.jsonl`, `lease.json`, `intake.arm`, `phase_f_halt`, `deploy_key`, `known_hosts`.

Nothing is chowned, so no symlink (`chown -R` defaults to `-P`) and no session-held fd crosses.

_The freeze, before gate 8's bundle_, so main cannot move between the final fetch and gate 9:

1. Reconcile any earlier halt; write `phase_f_halt` (`freeze: gate 9`). Assert: `lease.json` absent; `gh api` shows `merge-queue-main` restricting updates to the deploy key (phase E).
2. Final fetch into the old mirror (`+refs/heads/main:refs/merger/base`), then gate 8's `git bundle create --all`. Assert: `git bundle verify` passes; `list-heads` shows `refs/merger/base` at the fetched sha.
3. Gate 9's `ls-remote`. Assert: equal to step 2's sha, else step 1 restarts.
4. C9: in `zero-ops`, Zero reads GitHub's main sha with `curl`, checks that the marker's `base` equals it, touches the token and writes the sha down. Gate 9 deletes.

_The move, after gate 9_, in `zero-ops` (0a). A failed assert stops it, the daemon uninstalled.

1. `sudo launchctl bootout gui/501/com.balizero.localci-merger`. Assert: `launchctl print` fails, no `merger.py` process, `lease.json` absent.
2. Archive the old state dir (root, 0400, `/Library/LocalCI/archive/`), rename it `merger.frozen`, tombstone its path with a regular file so a surviving agent's seed (`mkdir -p`, `clone`) fails rather than seed a second mirror (against accident: `nuzantara` owns the parent). Assert both with `stat`.
3. `install -d -o localci -m 0700 /Users/localci/merger`. Assert: precondition 1.
4. C10, as `localci` under `env -i`: `git init --bare --template= --initial-branch=main` (no sample `hooks/`); `config` becomes a byte copy of the root-owned template `/Library/LocalCI/repo.config` (C6: `core.hooksPath /Users/localci/hooks`, `core.fsmonitor false`, `transfer.fsckObjects`, `receive.fsckObjects`, `receive.maxInputSize 200m`; no `include`, `merge`, `filter`, `diff`, `remote`). Assert: `cmp` equal; no `hooks/`, `info/attributes`, `info/grafts`, `objects/info/alternates`, commit-graph, `packed-refs`, `refs/replace`; `for-each-ref` empty.
5. Re-assert C5: `/Library/LocalCI/seal_signers` (`root:wheel` 0444) is one line `zero-seal namespaces="localci-seal" sk-ssh-ed25519@openssh.com …`, its key the one the token gives `ssh-keygen -K` now (item 3b).
6. C11: `report.json`, `ready.txt`, `marker.txt` and their `.sig`, copied as data from `merger.frozen/seal/` into root-owned `/Library/LocalCI/incoming/seal/`, are verified before any field is read: `ssh-keygen -Y verify -f /Library/LocalCI/seal_signers -I zero-seal -n localci-seal` on both texts, `kind ready` and `kind teman2_deleted`, the marker's `seal` = sha256(`ready.txt`), `report_sha256` = sha256(`report.json`). Then C11 prints `marker.base`; Zero confirms it equals freeze step 4's sha before step 7.
7. As `localci` under `env -i` (precondition 2's `PATH`, `GIT_NO_REPLACE_OBJECTS=1`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`): `git fetch --no-tags <bundle> refs/merger/base:refs/merger/incoming`, from gate 8's bundle or one `nuzantara` writes from `merger.frozen`, installed by root as `/Library/LocalCI/incoming/base.bundle`; `localci` never runs git in a session-owned repository. Assert: `stat` reads `Regular File root:wheel 444` in a root-owned dir (`install` copies, never links); `git bundle verify` passes; `incoming` = `marker.base`; one `update-ref --stdin` sets `refs/merger/base` and `refs/heads/main` to it and deletes `incoming`; `for-each-ref` lists exactly those two; after `git gc --prune=now`, which drops every bundle object outside that closure, `git fsck --strict` prints nothing.
8. Install the verified files in `<state>/seal/` (`localci`, 0400), and a copy beside Mini's replica. Assert: sha256s equal step 6's.
9. Extract the paths the wrapper and hooks run, at `marker.base`, into `~localci/code/<marker.base>/`; swap `current` by atomic symlink rename. Assert: no symlink under it; C7's files match the sha256s C7 printed.
10. Write fresh: empty `decisions.jsonl` and `intake.jsonl` (0600), `phase_f_halt` (`moved`), and as `localci` `mini_key` (0600), its `.pub` and `mini_known_hosts` (item 5). Assert the allow-list: the state dir holds exactly `repo.git`, `seal/` and those six files; `find <new state> -type l` and `find <new state> ! -user localci` print nothing; `lsof +D` of old and new state prints nothing.
11. C12 installs and bootstraps wrapper and LaunchDaemon. The first tick walks the trust path, re-checks steps 4, 6 (with item 3b's UV bit) and 10 in code, then journals `moved` (`marker_sha256`, `marker_base`, `seal_signers_sha256`). Assert: the journal's only line.
12. Repoint zero_sync (read-only key, `ssh://localci@pro/Users/localci/merger/repo.git`, `ZERO_SYNC_CANONICAL_REF=refs/merger/base`) and `origin` on M5, Pro and Mini (intake keys); retarget the organ `pro.localci_merger` (`bridge_source.path: /Library/LocalCI/heartbeat/pro.localci_merger.json`, `recovery_action: human_only`, no `recovery_params`) and the declared pair; remove the old plist (superscar #2). Assert: `mini.zero_sync` `ok` on the new URL; `ls-remote origin refs/heads/main` = `marker.base` on each host; the organ reads the daemon's heartbeat.
13. Remove `phase_f_halt`. Sessions re-push and re-admit open candidates: no candidate, admission or verdict carries over.

_The healer only alerts_ (`human_only`). A `nuzantara` organ cannot `launchctl kickstart system/…`; a sudo-less signal (a file or socket `nuzantara` writes, the daemon reads) would open a session-to-daemon channel outside 0b for nothing, since launchd re-runs the daemon every StartInterval and silence means wedged or unloaded, which takes root. On the `warning`, Zero runs `/usr/bin/sudo /bin/launchctl kickstart -k system/com.balizero.localci-merger` in `zero-ops`.

_Sessions keep building._ The old mirror's `HEAD` and `refs/heads/main` froze at its clone. In the new one `HEAD` names `refs/heads/main`, which no pusher may write and which item 5's transaction fast-forwards with `refs/merger/base`. Gate 7's `git fetch origin` keeps the default refspec; its repoint of `origin` lands at move step 12 (Teman2 until then).

_Restore (Q4)._ If Pro's state is lost, `nuzantara` on Mini bundles the replica's `refs/heads/main`; the move reruns from step 3 with the seal files from any copy (they verify by signature; one sits beside the replica). The replica and zero's synced main are both writable by Mini's sessions, so their agreement proves only that no single copy diverged: trust rests on the signed `marker.base` being an ancestor of the tip (gate 8's bundle anchors that commit, nothing after) and on Zero re-issuing the marker at the tip with a touch (C9's form). Later candidates are re-pushed.

**1. How a candidate arrives.**

- _Names._ Path `<host>/<lane>/<slug>`, ref `refs/candidates/<path>`, twin of the branch `agent/<host>/<lane>/<slug>`: `host` is `agent_start._hostname_short()` (`air-m5`, `nuzantara`, `mini-pro2`), `lane` matches `[a-z0-9-]{1,32}`, `slug` `[a-z0-9][a-z0-9.-]{0,63}` without `..` or a `.lock` suffix. Siblings: `refs/candidate-meta/<path>` (item 2), `refs/candidate-admit/<path>` (item 3).
- _Who pushes._ One intake key per host (`~/.ssh/localci_intake`, 0600), named in an ssh `Host` entry, never in the environment, exposed like today's `gh` login; zero_sync's key is read-only. Each sits in the root-owned `~localci/.ssh/authorized_keys` (C7) behind `restrict,from="127.0.0.1,::1,100.64.0.0/10,fd7a:115c:a1e0::/48",command="/Users/localci/bin/intake-shell <host>"`; `intake-shell` accepts exactly `git-receive-pack '<mirror>'` or `git-upload-pack '<mirror>'` (only the latter for `zero-sync`) and `exec`s the CLT's `git-shell -c` under `env -i` with `LOCALCI_INTAKE_PUSHER=<host>`, `GIT_NO_REPLACE_OBJECTS=1`. `intake.py submit` writes the meta commit, then `git push --atomic` of head and meta.
- _Hooks._ `core.hooksPath` is the root-owned `~localci/hooks` (C7): each hook `exec`s the pinned interpreter `-I` on `~localci/code/current/scripts/localci/intake.py hook <name>`. Instead of today's `mktemp` dir read from `refs/merger/wrapper`, `refs/merger/base` is extracted into a persistent `~localci/code/<sha>/`, `current` swapped by atomic symlink rename. A hook refuses unless `current` is the sha `intake.arm` names.
  - **`pre-receive`** decides the whole push against an allowlist: `refs/candidates/<pusher>/…`, `refs/candidate-meta/<pusher>/…`, `refs/candidate-admit/…` from any pusher (its verified signature is the authority), `refs/gate/fable-gate/<40 hex>`. It refuses everything else (`refs/heads/*`, `refs/tags/*`, `refs/notes/*`, `refs/replace/*`, `refs/merger/*`, the archives) and any push that:
    - leaves candidate and meta disagreeing (meta `head` ≠ the ref, `candidate` ≠ the path, BASE's schema fails);
    - writes a burned path (a `burn` line names it, or `refs/candidates-merged/<path>` exists);
    - deletes or non-fast-forwards an admit or gate ref;
    - carries a secret-scanner finding (Q5). The scanner, root-installed `/usr/local/localci/bin/gitleaks` (C3), fails closed: absent, off its pinned version or the installed binary's pinned sha256 (hashed every run), exiting non-zero, or past 120 s, it refuses. It runs `gitleaks git --redact --config <current>/scripts/localci/gitleaks.toml --log-opts=<range>` on the quarantined push, `<range>` being `old..new`, or `refs/merger/base..new` when `old` is all zeros. That config is owed (not on main today): BASE carries it before arming, `[extend] useDefault = true` over the pinned version's rules, its header pinning version, tarball sha256 and binary sha256; absent, it refuses. A refusal names rule and path from the redacted report, never the match;
    - arrives under B6's 60 GB floor;
    - arrives while the arm does not hold (§6), except a revoke-only push: every commit in `old..new` of each admit ref it updates has a tree of exactly `admit.txt` and `admit.txt.sig`, action `revoke`.
  - Every verdict goes to `<state>/intake.jsonl` (`ts`, `pusher`, `ref`, `old`, `new`, `accepted`, `why`), an accepted candidate deletion with `burn: <path>` on the same line. **`update`** repeats the namespace refusal per ref; **`post-receive`** only archives a deleted candidate as `refs/candidates-closed/<path>`.

**2. `candidate.yml`** is the one blob of a parentless commit at `refs/candidate-meta/<path>`, not a tree file: F2 merges only when the merged tree equals the judged one, which an in-tree file breaks; outside the tree the claim cannot select, exempt or rewrite its judge, and it changes without moving the head. Not a git note: `refs/notes/*` is one ref that pushers race on.

```yaml
schema: localci-candidate/1
candidate: air-m5/docs/localci-intake-spec # == the ref's path
head: <40 hex> # == refs/candidates/<path>, at push and at decision
base: <40 hex> # the commit it was cut from; == merge-base(head, refs/merger/base)
title: "docs(localci): …" # one line, <= 120; merge subject `<title> [<path>]`
bites: "Bites: <consumer> — <observation>" # one line, matched by merger.BITES_RE
gear: 2 # == the gear of the in-tree brief ctx.harness-floor resolves
evidence: evidence/2026-10/<slug>/ # == what scripts/ci/evidence_paths.py resolves on the diff; null only at gear 1
author_seat: claude-opus-5-5@air-m5
draft: false # true keeps it out of the queue (today's non-draft + armed)
```

BASE's `intake.py` validates it against BASE's `scripts/localci/candidate.schema.json` at `pre-receive` and at decision, so a schema edit is judged by the old schema. No client data appears here or in the log.

**3. The seat admission, replacing `localci:merge-shadow-ok` (Q1 = seat).**

- _Today._ `label_arm` passes when the label's last `LabeledEvent` has a `User` actor whose `role_name` is in `ARM_ROLES`: no author is read, the label survives a push, and M5's one admin `gh` login is shared by every session there. A convention.
- _What is signed._ A `localci-admit v1` text (LF, ASCII, fixed order): `repo nuzantara-canonical`, `not_after <UTC>`, `action admit|revoke`, then per candidate `candidate <path> head <sha> base <sha> meta <sha> nonce <32 hex>`; several lines make a batch. `base` is the cut base, since main takes 31–56 merges a day. `pre-receive` refuses a `not_after` beyond its logged receipt time plus 7 days.
- _With what._ A seat key per host, principal `admit-<host>`, presence-free and non-exportable (an operator-chosen store signs through an ssh-agent): the host's sessions can obtain signatures, at parity with the label. `intake.py admit <path>…` prints the text, signs it (`ssh-keygen -Y sign -n localci-admit`) and appends `admit.txt` and `admit.txt.sig` as a fast-forward child on each listed admit ref, in one `git push --atomic`.
- _Who signs._ BASE's `scripts/localci/admit/allowed_signers`, `namespaces="localci-admit"`, changed only through a candidate admitted under BASE's copy. An admit principal never lists `localci-seal`, and a `localci-seal` line there is inert: seals verify against item 3b's pinned file alone.
- _Verification._ `-Y find-principals`, then `-Y verify -I <principal> -n localci-admit` against a temporary copy of BASE's file, at `pre-receive`, at decision (filling `label_privileged`) and at merging (replacing "label still present" in `phase_f_arming`). On the append-only chain, the admission in force is the newest verified `admit` with now ≤ `not_after` whose (path, head, meta) has no verified `revoke` anywhere on it; a revoke is therefore terminal for its triple, and re-admitting needs a new head or meta.
- _Replay._ Binding repo, path, head, cut base and meta ends the label's carry-over. A (path, nonce) in a different signed text (keyed on the text's sha256) is refused at `pre-receive` and ignored at decision. The `merged` line gains `admit_nonce`; another namespace fails verification.

**3b. The seal principal (M1), pinned outside git.** A SEPARATE principal, `zero-seal`, signs the READY seal and the gate-9 marker: Zero's hardware token (`ed25519-sk`, `-O resident -O verify-required -O application=ssh:localci-seal`, `namespaces="localci-seal"` only), touched in `zero-ops` at READY (C8) and gate 9 (C9), never per merge.

- _UV bit._ `-Y verify` cannot show the PIN was entered, so intake decodes the SSHSIG blob and refuses unless the signed `flags` byte (PROTOCOL.u2f) carries user-presence 0x01 and user-verified 0x04.
- _Resident._ `ssh-keygen -K` re-derives the stub from the token in each ceremony, so no file is guarded between them; the cost is that a stolen token plus its PIN is the whole credential, where a non-resident key would also need the stub. A lost token is rotated.
- _Where._ Only in root-owned `/Library/LocalCI/seal_signers` (C5). In git it would change through admission, presence-free under Q1: one admitted second seal principal plus a swap of `<state>/seal/` removes the fence. Gating the file on the token's signature would add a signed-change path for a yearly list; a root-owned file is an OS permission no session holds, and rotation costs a touch and root either way.
- _Rotation._ The seal text, its canonical JSON and the marker stay verbatim in `<state>/seal/`; Zero re-signs the seal text with the new token (READY cannot be recomputed) and re-issues the marker at the current `refs/merger/base`, C5 replaces the pinned file, and §6's `merged`-line rule restarts at the new `marker.base`.

**4. The gate verdict.** `harness_fable_gate.py --sink mirror` writes `refs/gate/fable-gate/<head sha>`, a commit holding `verdict.json` (`schema`, `head`, `verdict`, `state` by today's mapping, `description`, `degraded`, `conditions_ref`, `supersede`, `seat`, `posted_at`), fast-forward only: an overwrite is a child needing `--supersede <reason>`, a racing gate session is refused. No seat signature (a key a gate session can use signs anything for it): authenticity is the pushing host's key in `intake.jsonl`, at parity with today's shared login. `seat` ≠ `author_seat` is journalled, never refused (Q6): both are self-declared.

BASE's `scripts/ci/harness_gate_read.py` (whose `main` requires `--repo`) gains `--event-name localci_intake --repo nuzantara-canonical --candidate-head <sha> --git-dir <mirror>`, reading `git cat-file blob refs/gate/fable-gate/<sha>:verdict.json` without network or `gh`: absent → B12's PENDING; unreadable → CANNOT-VERIFY; `state == "success"` → 0. The matrix step `Gear >= 2 — read the real gate verdict` gains `argv_intake`, and the runner, planned with `--candidate-id`, exposes `${{ localci.candidate_head }}` and `${{ localci.mirror }}`, both on BASE before arming. B12's re-open rule becomes "the ref exists".

**5. Every GitHub read the merger makes, and its intake equivalent.**

| today                                                                               | where                                                 | intake                                                                                         |
| ----------------------------------------------------------------------------------- | ----------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `pulls?state=open` (number, head, repos, draft, `auto_merge`, labels, `created_at`) | `open_prs`, `triage`, `wants_merge`                   | `for-each-ref refs/candidates/`; `draft: false` arms; no forks; order by first push            |
| state OPEN / CLOSED                                                                 | `pr_side`, `phase_f_arming`                           | the candidate ref exists / a `burn` line                                                       |
| head (`headRefOid`, `refs/pull/N/head`)                                             | `pr_side`, `pr_view`, `tick`                          | `rev-parse refs/candidates/<path>` at decision and at merging                                  |
| body (`Bites:`), title                                                              | `pr_side`, `merge_message`                            | meta `bites`, `title`                                                                          |
| labels, labeler, role                                                               | `wants_merge`, `label_arm`                            | the admission in force                                                                         |
| author                                                                              | not read today                                        | meta `author_seat` and `pusher`, journalled                                                    |
| merge queue state, the enqueue mutation                                             | `pr_side`, `enqueue_step`                             | none; `not_in_queue` / `first_enqueue` read "not burned" / "no `merged` line for (path, head)" |
| GitHub main (`fetch`, `ls-remote`)                                                  | `fetch_base`, `merge_shadow_step`                     | `refs/merger/base`, local                                                                      |
| READY: `report()` (`hc.gh_get`, `hc.fetch_live`)                                    | `phase_f_arming`                                      | the signed seal, verified against the pinned key, never recomputed                             |
| `merged`, `merge_commit_sha`, `merged_at`                                           | `replay_pending`, `report`                            | `refs/candidates-merged/<path>` and its `merged` line; replays end                             |
| `commits/{head}/status(es)`, `gh pr view`                                           | `gate_posted_at`, `harness_gate_read.py`, `GateJudge` | `refs/gate/fable-gate/<head>`                                                                  |
| branch protection, check runs (`hosted_required_green`)                             | `hosted_compare`, `hosted_side`, `StaleJudge`         | `required_executed_ok` (Q2, below)                                                             |
| the wrapper's GitHub fetch                                                          | `localci_merger_tick.sh`                              | extract from `refs/merger/base`                                                                |

_Criterion (Q2 = replace)._ `hosted_required_green` becomes `required_executed_ok`: each of the 14 required contexts in BASE's matrix executed OK locally. Pysa stays the python taint judge (`security.pysa_python`). The two CodeQL rows carry `waived: "RULED 2026-10-11 Q2"`; an unnamed blocked context still refuses. The waiver covers only `mapping: blocked`, so an executed CodeQL FAIL refuses, and it lapses automatically once the CodeQL contexts execute locally (lane `agent/air-m5/infra/localci-codeql-1011` sets them to `executed`), so a stale `waived:` never turns a CodeQL red into a merge.

_Merge order._ F2 journals `merged`, pushes, then moves `refs/merger/base` (`phase_f_merge`). Under intake the mirror is the authority:

1. `commit-tree`.
2. One `update-ref --stdin` transaction: `verify` the admit and meta refs at their values read at merging (a late revoke fails it); move `refs/merger/base` and `refs/heads/main` old→new; create `refs/candidates-merged/<path>`; delete the candidate ref at its old value. A failure is `merge_error`; nothing reads as merged.
3. Journal `merged` with `admit_nonce`.
4. Push `<new>:refs/heads/main`, never forced, over Tailscale to Mini's bare replica (Q4), `nuzantara@100.93.236.6:/Users/nuzantara/localci/replica.git`. `GIT_SSH_COMMAND` is built like `push_ssh_command` (`-F /dev/null`, no agent, `<state>/mini_key`), `StrictHostKeyChecking=yes` against `<state>/mini_known_hosts` alone, holding the host key the operator read on Mini (`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`). Mini holds the key as `restrict,from="<Pro's Tailscale address>",command="/Library/Developer/CommandLineTools/usr/bin/git-receive-pack '/Users/nuzantara/localci/replica.git'"`, an absolute path; the replica sets `receive.denyNonFastForwards`, `receive.denyDeletes` and `receive.fsckObjects`. In `git push --porcelain`, a failure with no ref line (no connection) is `storage_unreachable`; a `!` ref line (something else wrote the replica) or a host-key mismatch is `storage_refused`. Neither halts. Both raise `storage_lag`, the merges since the last accepted push, on every tick line; the heartbeat reads `warning` at once on a refusal, and on unreachability past 3 merges or 2 h (superscar #2).

A crash between steps 2 and 3 makes the next tick journal `merged_recovered` first. `phase_f_halt` stays a `phase_f_arming` condition, stopping merges while pushes are accepted; under intake only an operator writes or removes it. The journal's `pr` key becomes `candidate`.

**6. Arming.** `scripts/localci/intake.py` arms the live mirror only when all of these hold:

- `LOCALCI_MERGER_PHASE_F=1` and `LOCALCI_MERGER_ARMED` unset (superscar #10).
- **The seal.** At zero-cutover gate 1, BASE's `merger.py report --seal`, only when `report()` reads READY, writes the canonical report JSON (sorted keys, no spaces) to `<state>/seal/report.json` and emits a `localci-seal v1` text: `kind ready`, `compared_merges`, `first_merge`, `last_merge`, `false_green`, `code_sha`, `report_sha256` (the file's digest, because the dict carries `generated_at`; never recomputed). `zero-seal` signs the text (C8); the _seal's sha256_ is the text's.
- **The marker.** A `localci-seal v1` text signed by `zero-seal` at gate 9 (C9): `kind teman2_deleted`, `seal <seal's sha256>`, `base <sha>` (Teman2's main read by `ls-remote` under the freeze, just before deletion), `halt freeze`. It is never inferred from a failed `ls-remote` (superscar #8).
- **Both verify against `/Library/LocalCI/seal_signers` alone**, UV bit set (item 3b), the marker before `marker.base` is used. The seal's numbers meet `READY_MIN_MERGES` and `READY_MIN_DAYS` read at `marker.base`, with FALSE_GREEN 0. Nothing is read at the current base.
- **The range is real and merged.** `git merge-base --is-ancestor marker.base refs/merger/base` holds, since a rewind empties the range and makes the next rule vacuous; and every first-parent commit in `marker.base..refs/merger/base` has a `merged` line journalled after `moved`.
- **The state is the allow-list, read live:** the user is `localci`, no ancestor is session-owned or group- or world-writable, `config` equals the template, `repo.git`, `seal/` and every top-level entry are `localci`-owned, the top level holds only move step 10's names and the daemon's own (`lease.lock`, `lease.json`, `intake.arm`, `report.json`, `base/`, `cand/`, `runs/`), and the trust path walks clean (precondition 5).

_Signed rather than ordered._ Before gate 1 a moved daemon cannot compute READY (precondition 2's `PATH` has no `gh`, which `hosted_compare.gh_argv` and `merger.gh_graphql` spawn bare); after it, the journal stays session-writable and never crosses (0b). Only the token's signatures carry READY across, with no GitHub credential.

_The arm._ The daemon writes `<state>/intake.arm` (`armed`, `sha`, `written_at`, `expires_at` = +20 min) at tick start and at `drop_lease`. Ticks outlive 20 min (Pro's decision `elapsed_s`: median 908 s, max 4568 s, 47 of 202 over 1200 s), so the arm also holds while `lease.json` names a live holder whose `pid_start` is present and equal to `proc_start(pid)`: stricter than `pid_alive`, which reads a missing start time as alive. It expires 20 min after the lease frees or the holder dies; the kill switch exits before any write. A revoke reaches the ref unarmed (item 1), and the next armed tick refuses its triple, because decision and transaction read the chain. In phases D and E the first condition fails.

_Rehearsal: scratch mirror only._ `intake.py rehearse --state-dir <scratch>` clones the mirror and runs the whole intake with no storage push, refusing the live state dir. A live rehearsal is ruled out on both sides of gate 1: GitHub's queue still merges `--auto` PRs (two writers), and leaving it rewinds the mirror (`fetch_base` force-fetches without a `pushed` anchor, and with one runs `update-ref` with no old value).

_Tests_ (`scripts/localci/tests/test_intake.py`): guilt beside innocence for each rule, signing on real `ssh-keygen -Y` with throwaway non-sk keys; the UV parser runs on constructed SSHSIG blobs (UV set, clear, non-sk), and the walk takes the owner uid as a parameter, so it runs unprivileged.

- Move and arming: `test_first_tick_journals_moved_only_on_the_allow_list`, `test_marker_unverified_by_the_pinned_key_refuses`, `test_seal_principal_in_git_is_inert`, `test_arms_only_on_seal_and_marker`, `test_seal_without_uv_bit_refuses`, `test_seal_numbers_rechecked_against_thresholds_at_marker_base`, `test_admit_principal_cannot_sign_a_seal`, `test_rewound_base_refuses`, `test_every_first_parent_after_marker_base_needs_a_merged_line`, `test_replace_refs_are_ignored`, `test_repo_config_off_template_refuses`, `test_armed_intake_calls_no_report_no_gh`, `test_failed_ls_remote_is_not_gone`, `test_refuses_beside_merger_armed`, `test_refuses_a_session_writable_ancestor`, `test_trust_path_checks_owner_mode_and_every_ancestor` (was `test_binaries_are_absolute_and_root_owned`; still checks absolute binaries, docker never via `shutil.which`), `test_unreadable_trust_dir_halts`, `test_heartbeat_library_read_from_code_current`, `test_heartbeat_written_under_library_localci`, `test_wrapper_drift_from_code_current_warns`, `test_rehearsal_refuses_the_live_state_dir`.
- The arm: `test_expired_arm_closes_the_hook`, `test_arm_holds_while_the_lease_holder_lives`, `test_lease_without_equal_pid_start_does_not_hold_the_arm`, `test_arm_written_at_start_and_at_drop_lease`, `test_a_revoke_lands_while_unarmed`, `test_revoke_only_tree_is_exactly_two_files`.
- The hook: `test_refuses_outside_the_allowlist` / `test_accepts_an_atomic_pair_in_its_namespace`, `test_refuses_another_hosts_namespace`, `test_refuses_refs_replace`, `test_burn_holds_when_post_receive_fails`, `test_a_merged_path_is_burned`, `test_refuses_meta_naming_another_head`, `test_hook_runs_the_armed_base_sha`, `test_secret_finding_refuses_without_echoing_the_match`, `test_scanner_absent_erroring_or_timing_out_refuses`, `test_scanner_binary_off_its_sha256_refuses`, `test_scanner_range_on_a_new_ref_starts_at_base`.
- Admission: `test_schema_and_signers_are_base`, `test_each_bound_field_alone_refuses`, `test_wrong_namespace_expired_or_merged_nonce_refuses`, `test_expiry_checked_at_decision_and_merging`, `test_not_after_past_receipt_plus_7d_refuses`, `test_nonce_keyed_on_text_and_revoke_is_terminal`, `test_batch_admits_only_its_lines`.
- Gate verdict: `test_gate_reader_absent_pending_success_zero`, `test_gate_ref_fast_forward_and_supersede_reason`, `test_seat_equal_author_is_journalled_not_refused`.
- Criterion: `test_codeql_passes_only_with_its_named_waiver`, `test_executed_codeql_fail_refuses_despite_waiver`, `test_waiver_lapses_once_codeql_executes`.
- Merge: `test_merged_only_after_the_transaction`, `test_main_moves_with_base_in_one_transaction`, `test_a_late_revoke_fails_the_transaction`, `test_an_archive_without_merged_line_is_merged_recovered`, `test_mini_push_refusal_is_storage_lag_not_halt`, `test_mini_unreachable_and_refused_are_told_apart`, `test_storage_lag_warns_the_heartbeat`, `test_no_key_path_in_runner_env`.

_Mutants_ added to `scripts/localci/tests/mutants/merger_mutants.py`, each killed by that file:

- Move, arming and the seal: `ready-recomputed`, `seal-optional`, `seal-below-threshold`, `seal-written-not-ready`, `seal-unsigned`, `seal-uv-ignored`, `seal-signed-by-admit-principal`, `seal-verified-against-git-signers`, `marker-read-before-verify`, `thresholds-read-at-current-base`, `base-rewind-vacuous`, `merged-line-requirement-skipped`, `marker-without-seal`, `marker-from-ls-remote`, `allow-list-unchecked`, `replace-objects-honoured`, `intake-beside-armed`, `ancestor-unchecked`, `trust-path-group-writable-accepted`, `trust-walk-error-ignored`, `relative-binary`, `heartbeat-from-state`, `heartbeat-under-session-home`, `wrapper-drift-silent`, `rehearse-live-state`.
- The arm: `arm-never-expires`, `arm-ignores-lease`, `arm-pid-start-optional`, `arm-not-written-at-drop`, `revoke-refused-unarmed`, `revoke-tree-unchecked`.
- The hook: `hook-allows-refs-heads`, `hook-allows-refs-merger`, `hook-allows-refs-replace`, `hook-any-host`, `burn-in-post-receive`, `merged-path-unburned`, `scanner-echoes-match`, `scanner-fail-open`, `scanner-binary-unhashed`, `scanner-range-unbounded`.
- Admission: `schema-from-candidate`, `signers-from-candidate`, `admit-any-namespace`, `admit-{head,base,meta}-unbound`, `not-after-unanchored`, `admit-expiry-ignored`, `nonce-keyed-on-ref`, `revoke-not-terminal`, `batch-any-line`.
- The rest: `gate-absent-is-success`, `waiver-unnamed`, `waiver-covers-executed-fail`, `waiver-survives-execution`, `merged-before-transaction`, `transaction-without-verify`, `main-left-behind`, `merged-recovered-skipped`, `storage-lag-halts`, `storage-unreachable-as-refused`, `storage-lag-silent`.

**7. Residuals.**

- _Generator ≠ grader per merge (Q1)._ The seal fences ARMING, not merges; per merge it is a convention at parity with today's shared `gh` login (a session-owned executor, Q7; a gate ref any pusher writes, Q6; admissions any session signs, Q1). Signatures add binding and replay protection, not a fence.
- _The pin binds the first arm_, and later arms only while BASE's `intake.py`, which admitted merges change, keeps the seal check. `test_arms_only_on_seal_and_marker` and the mutant `seal-optional` catch its removal; a candidate removing the check and both detectors is caught only by review, a convention under Q1.
- _The executor (Q7)._ A session-owned VM decides every contained exit status, and FALSE_GREEN is no longer measurable: parity with today, against error, not attack.
- _The hosted compare ends._ The guilt suites and mutation sweeps hold the gate; zero's CI on `mini-zero-1` is a partial second opinion, for products only.
- _Code scanning ends_: CodeQL is waived until it executes locally (Q2; javascript is uncovered meanwhile, Pysa covers python), Dependabot ends, and the pre-receive scanner (Q5) replaces secret scanning and push protection.
- _Sessions lose_ the PR UI, review comments, `gh pr create/view/checks`, auto-merge as the readiness gesture, notifications and PR numbers. `intake.py status <path>` reads the journal; `pipeline-ship`, `agent_start.py --release` (`gh-closed`) and gate 7's files naming Teman2 are retargeted; `review.independent` is unchanged.
- _Copies._ Mini's replica (session-writable: a backup, trusted only through the restore's ancestor check and touch) and gate 8's bundle.
- _Deploy latency._ A backend merge deploys after zero_sync (≤ 30 min) and zero's CI.

**Rulings (2026-10-11).** Zero answered Q1, Q2, Q4 and Q7 in the M5 zero-migration session's question tool, choosing the recommended option each time; Q3, Q5 and Q6 are the session's defaults, which the owner saw and did not object to.

1. **Q1 seat (Zero).** A presence-free, non-exportable seat key per host admits; the separate `zero-seal` token principal signs seal and marker (3b).
2. **Q2 replace (Zero).** `required_executed_ok`, CodeQL's two contexts waived while blocked, Pysa kept.
3. **Q3 operator admin acts (default).** The blocks below, in `zero-ops`.
4. **Q4 Mini (Zero).** A bare replica on Mini, pushed after each merge.
5. **Q5 scanner (default).** A secret scanner in `pre-receive`.
6. **Q6 journal only (default).**
7. **Q7 residual (Zero).** The executor stays session-owned.
8. **R-A operator account (Zero, 2026-10-11, M5 session question tool).** A dedicated admin account, `zero-ops`, used by no session, runs every ceremony in a clean shell with absolute tool paths, the token signing inside it (0a).
9. **R-B trust-path walk (Zero, 2026-10-11, M5 session question tool).** `nuzantara` stays in `admin`; every tick checks that each trust-path file and ancestor is root-owned and not group- or world-writable, and halts otherwise (precondition 5).

_Operator blocks (Q3, R-A)._ C0 runs from an existing admin login, C1–C12 each in a fresh clean shell in `zero-ops` (0a). A block sets `-euo pipefail` (the first failure closes the shell), calls tools by absolute path, is titled by a `:` no-op (interactive `zsh -f` takes no `#` comments) and ends `OK Cn`; the next starts only after it. `<…>` is a placeholder; a download without a vendor checksum is pinned to the sha256 of the same URL fetched on Mini (separate ISP).

```sh
: "C0 — zero-ops, from an existing admin login"
set -euo pipefail
/usr/bin/sudo /usr/sbin/sysadminctl -addUser zero-ops -fullName "Zero operator" -shell /bin/zsh -admin -password -
/usr/sbin/dseditgroup -o checkmember -m zero-ops admin
echo "OK C0"

: "C1 — localci: enabled, staff, real shell, no usable password, root-owned home"
set -euo pipefail
S=/usr/bin/sudo; D=/usr/bin/dscl; U=/Users/localci
uid=$(( $($D . -list /Users UniqueID | /usr/bin/awk '$2>=501 && $2<1000 {print $2}' | /usr/bin/sort -n | /usr/bin/tail -1) + 1 ))
$S $D . -create $U
for k v in UniqueID $uid PrimaryGroupID 20 UserShell /bin/zsh RealName localci NFSHomeDirectory $U Password '*'; do $S $D . -create $U $k "$v"; done
$S /usr/sbin/createhomedir -c -u localci
$S /usr/sbin/chown root:wheel $U; $S /bin/chmod 0711 $U
$S /usr/bin/install -d -o localci -g staff -m 0700 $U/code $U/logs
$S /usr/bin/install -d -o root -g wheel -m 0755 $U/hooks $U/bin $U/.ssh
/usr/bin/id localci; $S -u localci /usr/bin/true
/usr/bin/stat -f '%N %Su:%Sg %Lp' $U $U/code $U/hooks $U/.ssh
echo "OK C1"

: "C2 — sshd: localci publickey only, zero-ops no method"
set -euo pipefail
/usr/bin/printf '%s\n' '' 'Match User localci' '    AuthenticationMethods publickey' '    PasswordAuthentication no' \
  '    KbdInteractiveAuthentication no' '    DisableForwarding yes' '    PermitTTY no' 'Match User zero-ops' \
  '    PubkeyAuthentication no' '    PasswordAuthentication no' '    KbdInteractiveAuthentication no' |
  /usr/bin/sudo /usr/bin/tee -a /etc/ssh/sshd_config >/dev/null
/usr/bin/sudo /usr/sbin/sshd -t
a=$(/usr/bin/sudo /usr/sbin/sshd -T -C user=localci,host=localhost,addr=127.0.0.1)
z=$(/usr/bin/sudo /usr/sbin/sshd -T -C user=zero-ops,host=localhost,addr=127.0.0.1)
for l in 'authenticationmethods publickey' 'passwordauthentication no' 'kbdinteractiveauthentication no' 'disableforwarding yes' \
  'permittty no'; do /usr/bin/grep -qix "$l" <<< "$a"; done
for l in 'pubkeyauthentication no' 'passwordauthentication no' 'kbdinteractiveauthentication no'; do /usr/bin/grep -qix "$l" <<< "$z"; done
echo "OK C2"

: "C3 — gitleaks (pins: the header of BASE's scripts/localci/gitleaks.toml) and the docker client"
set -euo pipefail
B=/usr/local/localci/bin; d=$(/usr/bin/mktemp -d)
V='<gitleaks version>'; TSHA='<tarball sha256, from the release checksums.txt>'; BSHA='<binary sha256>'
DV='<docker version>'; DSHA='<tarball sha256, fetched on Mini>'
/usr/bin/curl -fsSL --proto =https -o $d/gl.tgz https://github.com/gitleaks/gitleaks/releases/download/v$V/gitleaks_${V}_darwin_arm64.tar.gz
/usr/bin/curl -fsSL --proto =https -o $d/dk.tgz https://download.docker.com/mac/static/stable/aarch64/docker-$DV.tgz
/usr/bin/printf '%s  %s\n' "$TSHA" $d/gl.tgz "$DSHA" $d/dk.tgz | /usr/bin/shasum -a 256 -c -
/usr/bin/tar -xzf $d/gl.tgz -C $d gitleaks; /usr/bin/tar -xzf $d/dk.tgz -C $d docker/docker
/usr/bin/sudo /usr/bin/install -d -o root -g wheel -m 0755 /usr/local/localci $B
/usr/bin/sudo /usr/bin/install -o root -g wheel -m 0755 $d/gitleaks $d/docker/docker $B/
/usr/bin/printf '%s  %s\n' "$BSHA" $B/gitleaks | /usr/bin/shasum -a 256 -c -
$B/gitleaks version; $B/docker --version; /usr/bin/stat -f '%N %Su:%Sg %Lp' $B $B/gitleaks $B/docker
echo "OK C3"

: "C4 — python.org 3.11.9, the last 3.11 installer; group write stripped"
set -euo pipefail
d=$(/usr/bin/mktemp -d); V=3.11.9; SHA='<pkg sha256, fetched on Mini>'; F=/Library/Frameworks/Python.framework
/usr/bin/curl -fsSL --proto =https -o $d/py.pkg https://www.python.org/ftp/python/$V/python-$V-macos11.pkg
/usr/bin/printf '%s  %s\n' "$SHA" $d/py.pkg | /usr/bin/shasum -a 256 -c -
/usr/sbin/pkgutil --check-signature $d/py.pkg | /usr/bin/grep -F 'Developer ID Installer: Python Software Foundation'
/usr/bin/sudo /usr/sbin/installer -pkg $d/py.pkg -target /
/usr/bin/sudo /usr/sbin/chown -R root:wheel $F; /usr/bin/sudo /bin/chmod -R go-w $F
[ -z "$(/usr/bin/find -L $F/Versions/3.11 \( ! -user root -o -perm -020 -o -perm -002 \) -print -quit)" ]
$F/Versions/3.11/bin/python3.11 -I -c 'import sys; print(sys.version)'
echo "OK C4"

: "C5 — /Library/LocalCI and the seal key read from the token, before gate 1"
set -euo pipefail
L=/Library/LocalCI; S=/usr/bin/sudo; I=/usr/bin/install; d=$(/usr/bin/mktemp -d); cd $d
$S $I -d -o root -g wheel -m 0755 $L $L/incoming; $S $I -d -o root -g wheel -m 0700 $L/archive
$S $I -d -o localci -g wheel -m 0755 $L/heartbeat
/usr/bin/grep -qx sk-ssh-ed25519@openssh.com <<< "$(/usr/bin/ssh -Q key)"
: 'first enrolment only: /usr/bin/ssh-keygen -t ed25519-sk -O resident -O verify-required -O application=ssh:localci-seal -C zero-seal -f new'
/usr/bin/ssh-keygen -K
p=( $d/id_ed25519_sk_rk_localci-seal*.pub ); [ ${#p} -eq 1 ]
/usr/bin/awk '{print "zero-seal namespaces=\"localci-seal\" " $1 " " $2}' $p[1] > seal_signers
$S $I -o root -g wheel -m 0444 seal_signers $L/seal_signers
[ "$(/usr/bin/awk '{print $3, $4}' $L/seal_signers)" = "$(/usr/bin/awk '{print $1, $2}' $p[1])" ]
/usr/bin/ssh-keygen -lf $p[1]; /usr/bin/stat -f '%N %Su:%Sg %Lp' $L $L/*; /bin/rm -f $d/id_*_sk_rk*
echo "OK C5"

: "C6 — the repo.config template"
set -euo pipefail
d=$(/usr/bin/mktemp -d); T=/Library/LocalCI/repo.config
/usr/bin/printf '%s\n' '[core]' 'repositoryformatversion = 0' 'filemode = true' 'bare = true' 'hooksPath = /Users/localci/hooks' \
  'fsmonitor = false' '[transfer]' 'fsckObjects = true' '[receive]' 'fsckObjects = true' 'maxInputSize = 200m' > $d/repo.config
/usr/bin/sudo /usr/bin/install -o root -g wheel -m 0444 $d/repo.config $T
[ "$(/Library/Developer/CommandLineTools/usr/bin/git config -f $T --list | /usr/bin/wc -l | /usr/bin/tr -d ' ')" = 8 ]
/usr/bin/shasum -a 256 $T
echo "OK C6"

: "C7 — hooks, intake-shell, authorized_keys (each host's localci_intake.pub, fingerprint checked on that host)"
set -euo pipefail
d=$(/usr/bin/mktemp -d); U=/Users/localci; PY=/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11
for h in pre-receive update post-receive; do
  /usr/bin/printf '#!/bin/sh\nexec %s -I %s/code/current/scripts/localci/intake.py hook %s "$@"\n' $PY $U $h > $d/$h; done
{ /usr/bin/printf '%s\n' '#!/bin/sh'; /bin/cat <<'EOF'
M=/Users/localci/merger/repo.git; C=/Library/Developer/CommandLineTools/usr/bin; c=$SSH_ORIGINAL_COMMAND
case "$1" in
  air-m5|nuzantara|mini-pro2) [ "$c" = "git-receive-pack '$M'" ] || [ "$c" = "git-upload-pack '$M'" ] || exit 65 ;;
  zero-sync) [ "$c" = "git-upload-pack '$M'" ] || exit 65 ;;
  *) exit 65 ;;
esac
exec /usr/bin/env -i HOME=/Users/localci PATH=$C:/usr/bin:/bin:/usr/sbin:/sbin GIT_NO_REPLACE_OBJECTS=1 GIT_CONFIG_NOSYSTEM=1 \
  GIT_CONFIG_GLOBAL=/dev/null LOCALCI_INTAKE_PUSHER="$1" $C/git-shell -c "$c"
EOF
} > $d/intake-shell
/bin/cat > $d/keys <<'EOF'
air-m5 ssh-ed25519 <key>
nuzantara ssh-ed25519 <key>
mini-pro2 ssh-ed25519 <key>
zero-sync ssh-ed25519 <key>
EOF
/usr/bin/awk '{printf "restrict,from=\"127.0.0.1,::1,100.64.0.0/10,fd7a:115c:a1e0::/48\",command=\"/Users/localci/bin/intake-shell %s\" %s %s localci-intake-%s\n", $1, $2, $3, $1}' $d/keys > $d/ak
/usr/bin/sudo /usr/bin/install -o root -g wheel -m 0755 $d/pre-receive $d/update $d/post-receive $U/hooks/
/usr/bin/sudo /usr/bin/install -o root -g wheel -m 0755 $d/intake-shell $U/bin/intake-shell
/usr/bin/sudo /usr/bin/install -o root -g wheel -m 0644 $d/ak $U/.ssh/authorized_keys
/usr/bin/ssh-keygen -lf $U/.ssh/authorized_keys; /usr/bin/shasum -a 256 $U/hooks/* $U/bin/intake-shell
echo "OK C7"

: "C8 — gate 1: Zero reads and signs the READY seal"
set -euo pipefail
O=/Users/nuzantara/.nuzantara-pilots/local-ci/merger/seal; d=$(/usr/bin/mktemp -d); cd $d
h() { /usr/bin/shasum -a 256 "$1" | /usr/bin/awk '{print $1}'; }; f() { /usr/bin/awk -v k="$1" '$1==k {print $2}' "$2"; }
/usr/bin/sudo /usr/bin/install -o zero-ops -m 0400 $O/ready.txt $O/report.json $d/
/bin/cat ready.txt; /usr/bin/grep -qx 'kind ready' ready.txt; [ "$(f false_green ready.txt)" = 0 ]
[ "$(f report_sha256 ready.txt)" = "$(h report.json)" ]
/usr/bin/ssh-keygen -K
p=( $d/id_ed25519_sk_rk_localci-seal*.pub ); [ ${#p} -eq 1 ]
/usr/bin/ssh-keygen -Y sign -f ${p[1]%.pub} -n localci-seal ready.txt
/usr/bin/ssh-keygen -Y verify -f /Library/LocalCI/seal_signers -I zero-seal -n localci-seal -s ready.txt.sig < ready.txt
/usr/bin/sudo /usr/bin/install -o nuzantara -m 0444 ready.txt.sig $O/ready.txt.sig; /bin/rm -f $d/id_*_sk_rk*
echo "OK C8"

: "C9 — freeze step 4: the marker anchored on GitHub's main, signed; Zero writes the sha down"
set -euo pipefail
O=/Users/nuzantara/.nuzantara-pilots/local-ci/merger/seal; d=$(/usr/bin/mktemp -d); cd $d
h() { /usr/bin/shasum -a 256 "$1" | /usr/bin/awk '{print $1}'; }; f() { /usr/bin/awk -v k="$1" '$1==k {print $2}' "$2"; }
G=$(/usr/bin/curl -fsS --proto =https -H 'Accept: application/vnd.github.sha' https://api.github.com/repos/Bali-Zero/Teman2/commits/main)
/usr/bin/sudo /usr/bin/install -o zero-ops -m 0400 $O/marker.txt $O/ready.txt $d/
/bin/cat marker.txt; /usr/bin/grep -qx 'kind teman2_deleted' marker.txt; /usr/bin/grep -qx 'halt freeze' marker.txt
[ "$(f base marker.txt)" = "$G" ]; [ "$(f seal marker.txt)" = "$(h ready.txt)" ]
/usr/bin/ssh-keygen -K
p=( $d/id_ed25519_sk_rk_localci-seal*.pub ); [ ${#p} -eq 1 ]
/usr/bin/ssh-keygen -Y sign -f ${p[1]%.pub} -n localci-seal marker.txt
/usr/bin/ssh-keygen -Y verify -f /Library/LocalCI/seal_signers -I zero-seal -n localci-seal -s marker.txt.sig < marker.txt
/usr/bin/sudo /usr/bin/install -o nuzantara -m 0444 marker.txt.sig $O/marker.txt.sig; /bin/rm -f $d/id_*_sk_rk*
echo "OK C9 github-main $G"

: "C10 — move step 4: the fresh repository, as localci under env -i"
set -euo pipefail
cd /; C=/Library/Developer/CommandLineTools/usr/bin; R=/Users/localci/merger/repo.git
L() { /usr/bin/sudo -u localci "$@"; }
g() { L /usr/bin/env -i HOME=/Users/localci PATH=$C:/usr/bin:/bin GIT_NO_REPLACE_OBJECTS=1 GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null $C/git "$@"; }
g init -q --bare --template= --initial-branch=main $R
L /usr/bin/install -m 0600 /Library/LocalCI/repo.config $R/config
L /usr/bin/cmp /Library/LocalCI/repo.config $R/config
for p in hooks info/attributes info/grafts objects/info/alternates objects/info/commit-graph objects/info/commit-graphs packed-refs refs/replace; do
  L /bin/test ! -e $R/$p; done
[ -z "$(g -C $R for-each-ref)" ]
echo "OK C10"

: "C11 — move step 6: seal and marker verified as data, then marker.base"
set -euo pipefail
O=/Users/nuzantara/.nuzantara-pilots/local-ci/merger.frozen/seal; I=/Library/LocalCI/incoming/seal; K=/Library/LocalCI/seal_signers
h() { /usr/bin/shasum -a 256 "$1" | /usr/bin/awk '{print $1}'; }; f() { /usr/bin/awk -v k="$1" '$1==k {print $2}' "$2"; }
/usr/bin/sudo /usr/bin/install -d -o root -g wheel -m 0755 $I
for x in report.json ready.txt ready.txt.sig marker.txt marker.txt.sig; do /usr/bin/sudo /usr/bin/install -o root -g wheel -m 0444 $O/$x $I/$x; done
cd $I
for t in ready marker; do /usr/bin/ssh-keygen -Y verify -f $K -I zero-seal -n localci-seal -s $t.txt.sig < $t.txt; done
/usr/bin/grep -qx 'kind ready' ready.txt; /usr/bin/grep -qx 'kind teman2_deleted' marker.txt
[ "$(f seal marker.txt)" = "$(h ready.txt)" ]; [ "$(f report_sha256 ready.txt)" = "$(h report.json)" ]
echo "marker.base $(f base marker.txt)"
echo "OK C11"

: "C12 — move step 11: wrapper and LaunchDaemon"
set -euo pipefail
c=/Users/localci/code/current/scripts/localci/localci_merger_tick.sh; W=/usr/local/localci/bin/localci_merger_tick.sh
P=/Library/LaunchDaemons/com.balizero.localci-merger.plist; d=$(/usr/bin/mktemp -d)
/usr/bin/sudo /usr/bin/install -o root -g wheel -m 0755 $c $W; /usr/bin/sudo /usr/bin/cmp $c $W
/bin/cat > $d/p.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict>
  <key>Label</key><string>com.balizero.localci-merger</string>
  <key>UserName</key><string>localci</string>
  <key>GroupName</key><string>staff</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>/usr/local/localci/bin/localci_merger_tick.sh</string></array>
  <key>EnvironmentVariables</key><dict>
    <key>HOME</key><string>/Users/localci</string>
    <key>PATH</key><string>/Library/Developer/CommandLineTools/usr/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>GIT_NO_REPLACE_OBJECTS</key><string>1</string>
    <key>MERGER_STATE_DIR</key><string>/Users/localci/merger</string>
    <key>MERGER_PYTHON</key><string>/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11</string>
    <key>MERGER_HEARTBEAT_LIB</key><string>/Users/localci/code/current/scripts/lib/heartbeat.sh</string>
    <key>ORGANISM_LAST_SEEN_DIR</key><string>/Library/LocalCI/heartbeat</string>
    <key>DOCKER_HOST</key><string>unix:///Users/nuzantara/.colima/default/docker.sock</string>
    <key>MERGER_NODE</key><string>Nuzantara</string>
    <key>LOCALCI_MERGER_PHASE_F</key><string>1</string>
  </dict>
  <key>StartInterval</key><integer>600</integer>
  <key>RunAtLoad</key><true/>
  <key>Umask</key><integer>18</integer>
  <key>StandardOutPath</key><string>/Users/localci/logs/merger.out.log</string>
  <key>StandardErrorPath</key><string>/Users/localci/logs/merger.err.log</string>
</dict></plist>
EOF
/usr/bin/plutil -lint $d/p.plist
/usr/bin/sudo /usr/bin/install -o root -g wheel -m 0644 $d/p.plist $P
/usr/bin/sudo /bin/launchctl bootstrap system $P
/usr/bin/sudo /bin/launchctl print system/com.balizero.localci-merger >/dev/null
/usr/bin/plutil -p $P | /usr/bin/grep -E '"(UserName|ORGANISM_LAST_SEEN_DIR|MERGER_PYTHON)" =>'
echo "OK C12"
```

New ssh connections read C2's file; before the move a key login as `localci` must reach `intake-shell` and nothing else. C3 prints both versions, then `root:wheel 755` per path. The plist sets no `KeepAlive` (superscar #7).

## 3. What is lost, and what covers it

| lost                                              | cover                                                                                                                                                          |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CodeQL as a gate (the CLI is not licensed here)   | Pysa taint judge (already in the runner) for python; a hosted advisory CodeQL scan if Zero keeps it; a javascript substitute is open                           |
| GitHub's parallelism (~133 job-hours a day today) | measured per phase: the executor runs contexts in parallel containers on Pro; the capacity decision is taken on the numbers phase A and B produce, not assumed |
| redundancy (Pro down = no merges)                 | Mini as a second merger host with a single lease in Postgres (superscar #10: SSOT, never two active); until then the known cost of the ruling                  |
| stranger PRs on our metal                         | the merger takes same-repo PRs only; fork PRs are read, never executed                                                                                         |

## 4. §Solo-operatore

1. The merger's identity: a GitHub App or machine user, its credential created by Zero and installed under a
   dedicated OS user on Pro that no agent session can read (the Pen blocker of the 2026-10-06 spec — curing it
   is exactly this step).
2. The flip (phase E): removing required checks and the merge queue, restricting push to `main`.
3. Whether CodeQL and Dependabot stay as advisory hosted scans.
4. The second host (Mini) and the admin password for its dedicated user.

## 5. §Meta-pattern

The 2026-10-06 mission answered "can one host be the gate?" inside a premise it never checked with the owner:
that GitHub had to remain the writer. The brief said so, the hard constraints said so, and the spec built a
careful answer on it. The owner's actual goal was the opposite. The loop's defect is the one named in that spec
for local-CI itself, turned on the loop: a document taken for a decision. A governance premise in a brief is a
LEAD; before designing on it, ask the owner one question.
