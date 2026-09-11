---
panel: beyond-sota-xfamily
lane: 04-implementation-craft
seat: kimi-k3
model: "kimi-code/k3 · Kimi CLI print mode (tools)"
started: 2026-08-28T18:31:46Z
finished: 2026-08-28T18:39:44Z
duration_s: 478
exit: 0
words: 4444
prompt_sha256_16: 9184b20084d55dec
prompt_chars: 17793
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

• I'll execute Lane #4: ground in the repo first, then survey, then write the report. Starting with the highest-priority hot files.

• Now the scar corpus and ledger evidence.

• `gh` is unavailable in this snapshot (no GitHub remote). I'll measure PR size from squash-merge commits on main instead.

• Repo grounding is solid. Now the SOTA survey — batching web searches.

• All evidence gathered. Composing the final report now — the snapshot is read-only, so per the lane override the deliverable is this message.

  ---

  ```markdown
  ---
  date: 2026-08-28
  domain: operations
  panel: beyond-sota-2026-08-28
  part: 4/13 — Implementation craft (BUILD)
  model: Moonshot Kimi K3 (pinned lane, kimi-code CLI)
  sources: 12
  repo_files_verified: 24
  status: complete
  ---

  # Beyond-SOTA Lane 4 — Implementation craft (BUILD)

  **Lane notes.** This lane ran inside a read-only snapshot of the panel worktree; per the lane
  override, the report is returned in the final message instead of written to
  `research/operations/2026-08-28-beyond-sota-implementation-craft.md`. The post-write
  `ls -la`/`wc -w` probe is therefore not applicable — no file was written, and none is claimed.
  All `MEM:`/`$MEM` references in the brief (the four named memory files under
  `/Users/nuzantara/.claude/projects/.../memory/`) are **outside the snapshot and were not read**;
  where they matter I cite the repo's own copies (CLAUDE.md, PENDING-ARMS rows, scar entries that
  name the same incidents). `gh` is unusable in the snapshot (no GitHub remote), so the PR-size
  measurement was taken from squash-merge commits on `main` directly. `git worktree list` = 1
  (the snapshot itself) and says nothing about the live fleet; I use PENDING-ARMS healer rows for
  live worktree hygiene instead.

  ## 0. TL;DR

  Nuzantara's BUILD stage is **structurally ahead of world SOTA in isolation, routing and
  guardrail machinery, and behind its own doctrine in measured practice**. The biggest gap is not
  a missing mechanism but an unmeasured one: the routing floor, the worktree broker, the 400-line
  PR contract and TDD-where-testable all *exist*, while the freshest baseline (2026-08-22/26)
  shows 86% Sonnet dispatches, 7/91 Codex builds in `workspace-write`, a 34% over-400-line PR
  tail, and a mandate success metric that by the ledger's own admission "has not been measured
  yet." Top-3 moves: **(1)** make implementer-seat dispatches carry a machine-checkable spec path
  + acceptance command (`seat_build.sh --spec/--acceptance`, logged into the JSON report the
  grader re-runs); **(2)** add a red-first proof pair and a fix-correcting-fix recidiva ratio to
  `evidence_pack_lint.py`, turning the 3-rounds-suspend rule from anecdote into a computed floor;
  **(3)** use the scar corpus as a *generator seed* for property-based tests over the
  command-parsing guards — the one asymmetry no surveyed system has.

  ## 1. How Nuzantara does it today

  **Worktree broker (isolation).** `scripts/agent_start.py` (1,814 lines) is the single entry
  point: every agent session gets `.worktrees/<lane>-<task-id>/` on branch
  `agent/<host>/<lane>/<task-id>` (`scripts/agent_start.py:517`), with a hard invariant quoted in
  its docstring — two sessions never share a working tree — derived from a 4-LLM panel
  (`research/operations/2026-05-24-sota-multi-agent-repo-architecture-synthesis.md`, cited at
  `scripts/agent_start.py:14`). The broker carries: TTL metadata in `.agent-task.json`
  (`TaskMetadata`, `scripts/agent_start.py:752-807`); WIP-safe + recently-active + live-process +
  merged-on-origin guards in cleanup (`_worktree_has_wip` L1007, `_worktree_recently_active`
  L1029, `_worktree_has_live_process` L1075, `_branch_in_origin_main` L1185); orphan flagging at
  2× TTL (`_is_orphan` L1353); symlink injection of `.venv`/`node_modules`/`.husky/_` so worktrees
  inherit environment without mutation (L289-323, with the `.husky/_` shim load-bearing for the
  pre-push gate); RAM/load admission control (`check_ram_admission` L662); and a kill switch
  (`AGENT_BROKER_ENABLED=false`, L454). Runbook: `docs/runbooks/agent-worktree-broker.md` (239
  lines); daily reaping via LaunchAgent `com.nuzantara.agent-worktree-cleanup.daily`. The main
  checkout is agent-read-only by convention, enforced Claude-side by
  `infra/claude-hooks/worktree_isolation.py` (blocks mutating git verbs against the main checkout;
  README at `infra/claude-hooks/README.md` — these are reference copies of `~/.claude/hooks/`)
  and `worktree_file_write_check.py` for Edit/Write. Cross-machine placement with file-level
  deconfliction intent lives in `scripts/fleet_dispatch.py` (`docs/runbooks/fleet-lane-dispatch.md`:
  `place --files` is "what makes it safe").

  **Implementer routing.** Doctrine is task-shaped across a cross-family roster, not
  Sonnet-by-default (Zero ruling 2026-08-14, `MODEL_ROSTER.md:226-244`): Sonnet 5 is the BUILD
  default ("Opus 5 designs, Sonnet builds, Opus 5 verifies", `MODEL_ROSTER.md:34`); grunt lanes
  route to Haiku 4.5 / codex-luna / kimi-for-coding-highspeed; hard lanes to Opus-5-xhigh /
  codex-sol; counter-builds to GLM 5.2 via Alibaba TP1 (`.claude/skills/modus/SKILL.md` §Arsenal,
  BUILD row at stage 3). Seven grunt agent defs are pinned in `.claude/agents/`
  (`ledger-writer`, `lint-fixer`, `i18n-sync`, `fixture-gen`, `log-triage`, `catalog-meta`,
  `docs-sync` — `MODEL_ROSTER.md:36`), project-level and git-tracked specifically to kill
  HOME-fork drift (`.claude/agents/README.md`). Enforcement is mechanical, not advisory: the
  PreToolUse hook `model_routing_gate.py` denies a 3rd consecutive all-Anthropic build dispatch
  (PENDING-ARMS 2026-08-22 row), and `scripts/evidence_pack_lint.py` FAILs evidence packs without
  a non-Anthropic builder lane (`MODEL_ROSTER.md:236`).

  **Headless CLI implementers.** One call shape for all: `scripts/seat_build.sh` wraps Codex
  (sol/terra/luna), Kimi (k3/coding/highspeed), agy (flash/pro), qwen/TP1, with typed exit codes
  (64 args, 65 not-a-worktree or effort-over-tier-cap, 66 dirty-tree or context-window overflow,
  124 watchdog kill), a pure-Bash process-group watchdog, and a JSON report with a durable
  sidecar log path — and it **never ships**: "no commit, push, merge… The orchestrator remains
  the independent grader and publisher" (header comment). Effort ceilings are cabled in
  (R2/R3: sol at xhigh/max requires `--gear 3`). The Antigravity arm (CLAUDE.md §5) is a 6-step
  contract: Claude scopes with file:line anchors → fresh worktree → Antigravity builds → Claude
  re-reads the diff and **re-runs the tests** → Claude commits → Zero merges. Jules is the async
  cloud arm (`docs/runbooks/jules-dispatch.md`): "Jules generates; Fable grades" (now read Opus 5
  per the 2026-08-20 ruling), patch fetched and re-verified line-by-line, landed via our own
  branch+PR. Standing H24 cheap-seat queues live in `infra/army/{chore,jules,spark}-queue/` —
  one markdown file per chore with `scope:` and `acceptance:` frontmatter fields
  (`infra/army/chore-queue/README.md`).

  **Code discipline.** Karpathy's four principles are a vendored skill
  (`.claude/skills/karpathy-discipline/SKILL.md`: think-before-coding, simplicity-first, surgical
  changes, goal-driven execution with explicit verify steps). Reuse-first is a 7-step skill with
  a license gate (`.claude/skills/reuse-first/SKILL.md`: decompose into bricks → search in-repo
  then GitHub → classify COPIA-DIRETTO/FORKA-E-ADATTA/STUDIA-PATTERN-RISCRIVI/INSTALLA-LIB/
  SCRIVI-NUOVO → GPL/AGPL never copied). Code Golden Rules are 12 numbered invariants (CLAUDE.md
  §8: venv mandatory, absolute imports, httpx-async, type hints, no print(), PricingTool-only,
  atomic commits with `feat|fix|chore(scope):` convention, never `--no-verify`/`--amend` on
  pushed). TDD is doctrine at the BUILD stage ("TDD where testable", modus SKILL.md stage 3) and
  red-first is mandatory on product work (`docs/factory/ASSEMBLY-LINE.md`,
  journey-tests-red-first, RULED 2026-08-24). Pre-commit shapes code at commit time
  (`.pre-commit-config.yaml`: detect-secrets with baseline, ruff+format on backend-rag, eslint on
  mouth, custom no-print/no-console guards, 1MB file cap).

  **PR contract.** CLAUDE.md §Agent PR Contract (8 rules): one PR one concern, ~400 net lines
  target, arm-means-freeze, never rerun red without diagnosis, never commit while a push is in
  flight, claim-commit-first in a dedicated worktree, `mq handoff` after merge, and **three
  rounds then suspend** — a PR red for the same cause three times parks in PENDING-ARMS instead
  of getting a fourth round, with the measured anchor: PR #4547 (a 1-file hook fix) took 14
  commits, 11 adversarial rounds, ~6h, and 27 of the 200 commits landing 2026-08-20..22 "existed
  only to correct a claim made by a previous one."

  **Measured state of practice (this session, snapshot git history).** Last 200 squash-merged PR
  commits on main: **median 170 net lines, p75 622, p90 1,608, p99 18,561, max 24,622; 66%
  ≤400 lines, 34% over, 12 PRs over 2,000, mean 735.** Commits on main, last 14 days: **859**, of
  which **261 subjects start with `fix` (30%)** — heuristic: conventional-commit `fix(`/`fix:`
  prefix; top scopes were `docs(ledger)` 80, `docs(modus)` 55, `fix(mouth)` 25, `fix(ci)` 21.

  ## 2. Scars & ledger evidence in this area

  The BUILD area's wounds cluster in superscar **#5 (sibling-race/shared-worktree)** and its
  guard's own failure mode, superscar **#3 (guard over-match)**.

  - **W59 (mother scar, sibling-race)** — parallel automation on shared trees; the broker is its
    antidote. Family members: W62, W63, W80, agent-library-evolver, 2026-04-29 untracked-loss
    (`.claude/rules/cicatrix-superscar.md:122-138`).
  - **W62** — 6 abandoned worktrees violated the 60-min TTL 34× (archive L2596): broker hygiene
    debt, fixed with the cleanup cron; each stale worktree "adds a checkout another session may
    accidentally `cd` into and commit on."
  - **W63** — nested worktree: the broker, invoked from inside a worktree, created
    `.worktrees/<wt>/.worktrees/` (archive L2197). Cured by root-derivation via
    `--git-common-dir` (`scripts/agent_start.py:106-166`), but the W105 GOTCHA notes the fix
    landed in the broker *after* the hook had it, and a stale memory said "derives da cwd" —
    doctrine lagged code.
  - **W80 + recidiva (2026-07-07)** — the most instructive BUILD scar. The WIP-guard protected
    only *dirty* worktrees; committing everything to satisfy the stop-hook made your own live
    worktree reap-eligible (cicatrix-scars.md:296-315). The recidiva was worse: during a Gear-3
    3-implementer fan-out, `mouth-wave15-integrity` was reaped **while its Sonnet implementer was
    actively working, before its first commit** — dir, branch and registration gone, uncommitted
    work unrecoverable because "without a commit there is no git object to recover" (L565-575).
    Two sibling worktrees survived and merged (#2120/#2121). This is the single strongest
    argument for claim-commit-first being *automated*, not contractual.
  - **W83/W84/W105 (guard over-match on the guard that protects BUILD)** — the
    worktree-isolation hook false-blocked a read-only `ssh grep` because an Italian apostrophe
    paired quotes across lines (W84, cicatrix-scars.md:184-194), missed/exempted remote dispatch
    wrongly (W83), and resolved nested worktree removals to the wrong victim (W105). Each cure
    shipped with a guilt+innocence corpus (21, 15, and real-worktree cases respectively) — the
    repo's most mature test pattern lives exactly here.
  - **W84-broker variant** — an empty worktree inventory read as cleanliness: "the calm liar"
    (`scripts/agent_start.py:132-141`).
  - **W88** — after squash-merge, verify landing by *content* (`git show origin/main:<file> |
    grep <symbol>`), never by SHA ancestry (cicatrix-scars.md:1104, 559-563); load-bearing for
    every "did my build land" question.
  - **PENDING-ARMS rows that name BUILD practice directly** (grep-verified): the routing-floor
    hook's live copy predates its repo canon — the hook gated every dispatch since 2026-07-14
    "with NO repo canon at all" (superscar #1); the 2026-08-22 arsenal-routing mandate's own
    success metric "has not been measured yet," with the baseline pinned: Agent dispatch mix
    Sonnet 355 / Haiku 25 / Opus 24 / inherit 29; roles 292 read-explore / 62 build / 79 review;
    external seats via Bash Kimi 281, Codex 91, agy 29, Qwen 20, GLM 12; Codex sandbox 63
    read-only / **7 workspace-write**; chronic seat deaths (codex/agy/qwen AUTH_DEAD, jules
    CRED_UNAVAILABLE) discovered by healer ticks days late (Mini row 2026-08-17); seat-mix hand
    parse 2026-08-26: 882 Agent dispatches in 48h, 86% sonnet, 0.9% haiku, `Workflow` tool 0
    genuine runs, 5/20 evidence packs with a cross-family reviewer
    (`docs/factory/SEAT-MIX.md`).

  ## 3. World SOTA survey

  | System / practice | Source | Mechanism | Measured effect | Transfer to Nuzantara |
  |---|---|---|---|---|
  | Google small-CL doctrine | eng-practices [1] | ~100-line CLs; review speed/thoroughness scale inversely with size; "no CL too small" | Qualitative canon; industry default | Direct: the 400-line contract is 4× Google's cultural norm; measured median 170 is fine, p90 1,608 is the violation |
  | Trunk-based development | trunkbaseddevelopment.com [2] | Short-lived branches, continuous integration to main | DORA-correlated with elite delivery | Already the shape (main-only, squash, worktree lanes) |
  | Anthropic "Building effective agents" | anthropic.com [3] | Simplest composable pattern that works; workflows before agents; ACI ergonomics | Canonical design guidance | Validates modus gears; warns against orchestration hypertrophy |
  | Claude Code best practices | anthropic.com [4] | Explore-plan-code-commit flow; CLAUDE.md tuning; course-correct early; headless `-p` for automation | Practice canon | Nuzantara already past this baseline (headless fleet, hooks, worktree broker) |
  | SWE-bench Verified scaffolds | arXiv 2509.13941 [5]; 2506.17208 [6] | OpenHands 53.0% / Agentless 50.8% / Tools-Claude 49.0% on 500 issues; leaderboard anatomy | Scaffold choice moves points more than model at the margin (same model: 43.2% vs 59.8% across scaffolds per [6]-era data) | Agentless's lesson: a fixed localize→repair→validate pipeline beats free agency on bounded units — matches the army chore-queue contract |
  | Agentless | arXiv 2407.01489 [7] | Three-phase fixed pipeline, no autonomous tool loop; hierarchical localization | SOTA-tier on SWE-bench Lite at a fraction of agent cost | Strong evidence for routinizing grunt BUILD units as fixed pipelines (spark-queue already this shape) |
  | Cognition: single-threaded writes | cognition.com [8][9] | Writes stay single-threaded; other agents contribute *intelligence*; clean-context reviewer catches what the coder can't | Devin Review: avg 2 bugs/PR, 58% severe; cross-frontier "smart friend" works, asymmetric-weak primary doesn't | Validates generator≠grader on fresh context; **challenges multi-implementer fan-out** (W80-recidiva happened exactly in a 3-writer campaign) |
  | METR RCT 2025 | arXiv 2507.09089 [10] | 16 experienced OSS devs, 246 real tasks, randomized AI on/off | **AI made devs 19% slower** while they believed +20% faster; Feb-2026 follow-up: estimates flip modestly positive with wide CIs | The perception gap justifies this organism's measure-everything posture; "feels faster" is not evidence |
  | DORA 2025 AI report | DORA/Google Cloud [11] | ~5,000 respondents; AI as amplifier of existing system quality | Throughput ↑ *and* instability ↑; 30% distrust AI output | Amplifier thesis: Nuzantara's gates are exactly the "system quality" AI amplifies — the moat is the guardrails, not the models |
  | Faros AI telemetry | faros.ai [12] | 10,000+ devs telemetry | +21% tasks, +98% PRs merged, flat org-level delivery | Explains the 859 commits/14d with 30% `fix` subjects: individual throughput up, rework up with it |
  | Hypothesis (PBT) | hypothesis.works [13] | Generative property tests; shrinking to minimal failing case | Standard in critical libs | Missing here as a *practice*; the guilt/innocence corpora are its hand-rolled ancestor |

  **The three that matter most.** (a) **Cognition's single-threaded-writes law** is the sharpest
  external mirror: Nuzantara's W80-recidiva total-loss happened in precisely the pattern
  Cognition measured as failing (parallel writers with fragmented implicit decisions), while its
  generator≠grader refuter chain is exactly the pattern Cognition measured as working
  (clean-context review, 2 bugs/PR, 58% severe). The organism has independently converged on the
  same law — but enforces it socially (doctrine) where Cognition enforces it architecturally
  (one writer process). (b) **Agentless/OpenHands parity** (within 4 points on 500 issues) says
  the marginal value of free-form agency on bounded build units is small; the army queues'
  `scope:`/`acceptance:` frontmatter is already the Agentless shape and should be generalized,
  not the agentic fan-out. (c) **METR + DORA + Faros together** form one finding: AI throughput
  is real at the individual level and evaporates into rework at the system level unless measured.
  Nuzantara's 30%-fix commit share is what that evaporation looks like in git.

  ## 4. Position vs SOTA

  | Sub-dimension | Verdict | Evidence |
  |---|---|---|
  | Worktree isolation & broker | **AHEAD** (ambition) / **AT** (reliability) | TTL+WIP+liveness+merged-content guards, RAM admission, cross-machine placement (`agent_start.py`, `fleet_dispatch.py`) — no surveyed system ships this; but W80 recidiva reaped a live implementer with total loss |
  | Implementer routing (cross-family, cost-aware) | **AHEAD in doctrine, BEHIND in practice** | Task-shaped roster + hard routing floor hook + evidence-pack FAIL (`MODEL_ROSTER.md:236`); measured reality: 86% sonnet, 7/91 codex workspace-write builds, success metric unmeasured (PENDING-ARMS 2026-08-22) |
  | PR size discipline | **AT** | 400-line contract ≈ Google doctrine; 66% compliance, median 170 — but p90 1,608 and max 24,622 show the tail is unenforced |
  | TDD / red-first | **AT (doctrine) / unmeasured (practice)** | "TDD where testable" (modus BUILD row), journey-tests-red-first (ASSEMBLY-LINE) — no artifact proves a red run preceded green |
  | Reuse-first / karpathy | **AHEAD** | Both codified as triggered skills born from measured incidents (reuse-first SKILL.md cites the 70%-already-written session); big-tech has the culture, not the trigger |
  | Headless CLI implementers | **AHEAD in breadth, BEHIND in reliability** | One typed wrapper across 5 providers with watchdog and effort ceilings (`seat_build.sh`); chronic AUTH_DEAD/QUOTA_DEAD seats found days late by healer ticks |
  | Grunt lanes / army H24 | **AHEAD** | Standing per-seat queues with `scope:`/`acceptance:` contracts (`infra/army/`) — the Agentless insight operationalized; nobody surveyed runs this on flat subscriptions |
  | Guards shaping code (hooks, pre-commit) | **AT** tooling, **AHEAD** enforcement | Standard pre-commit stack; but PreToolUse hook enforcement with guilt/innocence corpora (W83/W84/W105) is beyond common practice |
  | Measurement of build behavior | **AHEAD in instrumentation, BEHIND in loop closure** | `seat_mix_report.py` exists, PII-safe, tested — and by design has no targets and its first mandate's metric was never re-measured |
  | Mutation/property-based testing | **BEHIND** | No PBT anywhere in the build path; the hook corpora are hand-enumerated cases that have now missed the same over-match class three times (W82/W83/W84) |

  ## 5. Beyond-SOTA recommendations

  Ranked by (impact × confidence) / cost. All respect: CLI-only LLMs, no paid Anthropic API, PII
  output boundary, Fable never auto-routed, Zero decides business.

  **R1 — Spec+acceptance as machine fields on every seat dispatch.** *What:* add mandatory
  `--spec <path>` and `--acceptance <cmd>` to `scripts/seat_build.sh`; store both in the JSON
  report; the grader's verification step re-runs the acceptance command verbatim instead of
  re-deriving "done" from chat. *Why beyond SOTA:* Cognition's open problem list is entirely
  communication problems ("agents assume they share state with their children when they don't");
  nobody surveyed machines the contract — Devin coordinates children through MCP prose. The
  organism's asymmetry: `seat_build.sh` already has typed exits, a watchdog and a report file —
  the slot for the contract exists and is empty; the army queues already prove the
  `scope:`/`acceptance:` shape works. *Cost:* ~150 lines bash + tests; flat-sub tokens only.
  *Gear:* 2. *Risk/scar family:* #3 over-match (a too-strict schema rejecting legit dispatches) —
  mitigate with NOTICE-first like evidence_pack_lint's grace period. *Metric:* % of seat_build
  JSON reports carrying both fields — before: 0%; target: 100% in 30 days; measure by scanning
  report sidecars. *Kill criterion:* graders ignore the acceptance field in >20% of sampled
  verifications after 30 days (theater). *First PR:* ≤400 lines, `scripts/seat_build.sh` +
  `scripts/lib/` + tests.

  **R2 — Red-first proof pair + fix-recidiva ratio in the evidence pack.** *What:* (a) for BUILD
  units marked testable, `evidence_pack_lint.py` requires a `red_run` artifact (the failing test
  output captured before the fix) paired with the green run; (b) a CI-computed recidiva ratio:
  share of commits on main in a 72h window whose diff touches files touched by a same-window
  `fix` commit — the 3-rounds-suspend rule's denominator, computed instead of remembered. *Why
  beyond SOTA:* TDD adherence is asserted everywhere and *measured nowhere* — not at Google, not
  in DORA, not in any scaffold. The asymmetry: this organism already recomputes gear floors in CI
  from the diff (the one non-gameable classifier); the same machinery can recompute red-first and
  recidiva from git+CI artifacts. *Metric:* before — red-first proven for ~0% of code PRs;
  recidiva baseline 13.5% (27/200 commits, 2026-08-20..22, CLAUDE.md §PR-contract) and 30% `fix`
  subjects over 859 commits/14d (this lane). Target: recidiva <5%; red-first ≥80% of
  testable-flagged PRs. *Cost:* ~300 lines Python + CI step. *Gear:* 2. *Risk:* #2
  exists≠armed — wire the number into the SessionStart digest or it dies unread. *Kill:* ratio
  proves non-actionable (no behavior change after two mandate cycles).

  **R3 — Scar-seeded property-based testing for command-parsing guards.** *What:* introduce
  Hypothesis (already-adjacent stack, pure Python) over `worktree_isolation.py`'s parser: the
  *generator* is seeded with the verbatim trigger strings from W79/W83/W84/W105 and the innocence
  corpus, with grammar-directed mutation (quotes, apostrophes, redirects, ssh-mixing,
  multi-line). Property: *no read-only command is ever blocked; no main-checkout mutating command
  is ever allowed.* *Why beyond SOTA:* no surveyed system uses its own incident corpus as a
  fuzzing seed for its safety guards; the scar corpus is the asymmetry — 296KB+397KB of measured
  failure strings, each a minimal repro by construction. W83→W84→W105 is three recidivas of one
  class that hand-enumerated corpora failed to close; PBT is the standard tool for exactly this
  and the organism already believes in corpora. *Metric:* before — 3 over/under-match scars of
  the parser class in ~10 weeks, all caught live; after — target 0 caught live (all caught in
  CI); count new family-#3 members per quarter. *Cost:* ~250 lines + a CI job on existing
  runners. *Gear:* 2. *Risk:* #3 itself (a PBT-found "failure" that is a spec bug, not a code
  bug) — the property statement is the real deliverable. *Kill:* generator finds nothing new in
  two quarters AND maintenance cost exceeds one session-hour/quarter.

  **R4 — Claim-commit automation for fan-out builds.** *What:* the broker's `cmd_create` arms a
  liveness beacon: any implementer worktree that has produced file mtimes but no commit within N
  minutes gets a `refs/agent-wip/<task>` pushed snapshot (content-addressable, never on the PR
  branch), making uncommitted work recoverable by construction. *Why beyond SOTA:* Cognition's
  answer to parallel-writer fragility is "don't parallel-write"; this organism's measured reality
  (W80-recidiva, total loss of a live implementer's work) demands the stronger answer: parallel
  writes with *crash-proof WIP*. Nobody surveyed snapshots agent WIP to the object store.
  *Metric:* before — 1 measured total-loss event (2026-07-07) and the recurring
  unpushed-commit-on-main wall (5th occurrence ledgered 2026-08-14); after — recoverable-WIP
  coverage 100% of broker-created worktrees; total-loss events = 0/quarter. *Cost:* ~200 lines.
  *Gear:* 2. *Risk:* #5 itself (snapshot pushes racing the implementer) — ref namespace is
  disjoint by design; and #9 (a green "snapshot exists" signal masking staleness) — stamp the ref
  with mtime and alert on age. *Kill:* snapshot volume or push noise exceeds value (measure
  ref-count growth and orphan rate).

  **R5 — Seat-death drill (build-side sliver).** *What:* a weekly drill that walks each
  implementer chain with a 1-token probe and records hop-depth-to-first-live-seat, feeding the
  boot card. *Why:* seat deaths are currently discovered mid-mandate (deepseek correction live in
  session; codex Mini AUTH_DEAD ledgered days late). *Metric:* time-to-detect seat death, before
  ≈ days, target <24h. *Cost:* ~100 lines on top of `arsenal_probe.py`. *Gear:* 1. *Note:*
  overlaps lanes 8/9 — flagged, not owned. *Risk:* #2 (a drill that alerts to a dead channel) —
  route through the existing Telegram wrapper per W107/W108 discipline.

  ## 6. 90-day roadmap + first PRs

  **Wave 1 (days 0-30) — close the measurement loop on what exists.**
  R1 (spec/acceptance fields) and R2 (red-first + recidiva) land first: both are pure-additive
  lint/schema work on `seat_build.sh` and `evidence_pack_lint.py` with NOTICE-periods, zero
  behavioral breakage. Deliverable proof: the arsenal-routing mandate's 2026-08-22 baseline gets
  its week-1 re-measure (already ledgered as owed in PENDING-ARMS) *plus* the two new numbers.
  - *PR-1a* "feat(scripts): seat_build carries --spec/--acceptance into the JSON report" —
    `scripts/seat_build.sh`, `scripts/tests/test_seat_build*.py`; ≤350 lines; Gear 2; acceptance:
    a dry-run dispatch produces a report with both fields and the grader-side re-run command
    executes the acceptance verbatim.
  - *PR-1b* "feat(ci): red-first pair + fix-recidiva ratio in evidence_pack_lint" —
    `scripts/evidence_pack_lint.py`, one workflow step; ≤400 lines; Gear 2; acceptance: a fixture
    PR without red proof FAILs (post-grace), the 2026-08-20..22 window recomputes to 13.5%.

  **Wave 2 (days 31-60) — harden the writer side.**
  R4 (WIP-snapshot beacon) and R3 (scar-seeded PBT over the isolation hook). R4 directly retires
  the W80-recidiva loss class; R3 retires the W82-84-105 recidiva class.
  - *PR-2a* "feat(broker): agent-wip ref snapshots for active uncommitted worktrees" —
    `scripts/agent_start.py` `cmd_create`/cleanup + tests; ≤400 lines; Gear 2; acceptance: kill a
    synthetic live session mid-work with zero commits, recover its tree content from the ref.
  - *PR-2b* "test(hooks): hypothesis generative corpus seeded from W79/83/84/105 triggers" —
    new `infra/claude-hooks/test_w*_property.py`, CI job; ≤300 lines; Gear 2; acceptance: the
    four historical triggers are in the seed set and the property holds over ≥10k generated
    commands incl. Italian apostrophes and multi-line quoting.

  **Wave 3 (days 61-90) — doctrine catches up to measurement.**
  Re-baseline the seat-mix and recidiva numbers against Wave-1/2 floors; amend `MODEL_ROSTER.md`
  routing doctrine with measured (not aspirational) seat shares; decide with Zero whether the
  400-line contract gets a mechanical tail gate (p90 1,608 says the contract currently binds the
  median, not the tail). `needs-ruling` on any hard size gate.
  - *PR-3* "docs(roster): measured routing reality + recidiva floor" — `MODEL_ROSTER.md`,
    `docs/factory/SEAT-MIX.md`; ≤200 lines; Gear 1; acceptance: every routing claim cites a dated
    measurement.

  ## 7. Needs-ruling

  Only true business/owner calls surfaced by this lane: **(a)** whether the 400-line PR contract
  becomes a mechanical gate for the >2,000-line tail (12 PRs in the last 200) — it trades velocity
  on legitimate large refactors; Zero rules. **(b)** TP1 key rotation after the historical 0644
  exposure — already ledgered in PENDING-ARMS 2026-08-22 as `operator[secret]+operator[business]`;
  restated, not re-decided. **(c)** All interactive seat relogins (codex/agy/nlm/qwen) are
  `operator[gui]` by nature — already ledgered. Nothing else in this lane requires a human.

  ## 8. §Meta-pattern

  One defective belief generates most of what this lane found: **"a shipped mechanism is a
  practiced discipline."** The routing floor hook ran live for five weeks with no repo canon
  (#1 HOME-fork); the arsenal-routing doctrine declared task-shaped implementation while 86% of
  dispatches stayed Sonnet and the mandate's own success metric was never re-measured; the PR
  contract says ~400 lines while a third of PRs exceed it and the p90 is 4× the target; the
  broker's cleanup guards existed while they reaped a live implementer (W80 recidiva); the
  isolation hook's innocence corpus existed while the same over-match class recurred three times
  (W83→W84→W105); "TDD where testable" exists with zero red-first artifacts. The organism is
  world-class at *building the guard* and systematically under-invests in *proving the guard
  changed behavior*. Superscar #2 (esiste ≠ armato) is the daemon-level instance; this lane's
  finding is the practice-level instance — **shipped ≠ practiced**. Every recommendation above is
  therefore the same shape: attach a computed number to an existing mechanism so the mechanism
  can no longer testify for itself. The asymmetry that makes this cheap here and unavailable to
  most orgs: CI already recomputes the gear floor from the diff, the scar corpus is a labeled
  failure dataset, and seat_mix_report.py proves the telemetry habit exists — the loop-closure
  machinery is half-built and only needs to be pointed at the build stage itself.

  ## 9. Sources

  1. https://google.github.io/eng-practices/review/developer/small-cls.html — Google's canonical small-CL doctrine; the reference every PR-size contract derives from. Accessed 2026-08-28.
  2. https://trunkbaseddevelopment.com — the reference site for trunk-based development; canonical for short-lived-branch practice. Accessed 2026-08-28.
  3. https://www.anthropic.com/engineering/building-effective-agents (Dec 2024) — Anthropic's primary guidance on workflow-vs-agent simplicity. Accessed 2026-08-28.
  4. https://www.anthropic.com/engineering/claude-code-best-practices (Apr 2025) — Anthropic's primary agentic-coding practice doc. Accessed 2026-08-28.
  5. https://arxiv.org/abs/2509.13941 — direct 500-issue comparison: OpenHands 53.0% / Agentless 50.8% / Tools-Claude 49.0% on SWE-bench Verified. Accessed 2026-08-28.
  6. https://arxiv.org/abs/2506.17208 — "Dissecting the SWE-Bench Leaderboards," the authoritative anatomy of 147 leaderboard submissions. Accessed 2026-08-28.
  7. https://arxiv.org/abs/2407.01489 — Agentless (UIUC, Jul 2024): primary evidence that fixed pipelines rival agents on bounded repair. Accessed 2026-08-28.
  8. https://cognition.com/blog/dont-build-multi-agents (Jun 2025) — Walden Yan's parallel-writer fragility thesis; primary. Accessed 2026-08-28.
  9. https://cognition.com/blog/multi-agents-working (Apr 2026) — the measured follow-up: single-threaded writes, clean-context review (2 bugs/PR, 58% severe), smart-friend limits. Fetched in full. Accessed 2026-08-28.
  10. https://arxiv.org/abs/2507.09089 — METR RCT (Jul 2025): 19% slower / perceived 20% faster; the gold-standard productivity measurement. Accessed 2026-08-28.
  11. DORA 2025 State of AI-Assisted Software Development (Google Cloud, Sep 2025; summarized at https://www.scrum.org/resources/blog/dora-report-2025-summary-state-ai-assisted-software-development and https://itrevolution.com/articles/ais-mirror-effect-how-the-2025-dora-report-reveals-your-organizations-true-capabilities/) — ~5,000 respondents; AI-as-amplifier, throughput↑ + instability↑. Accessed 2026-08-28.
  12. https://www.faros.ai/blog/key-takeaways-from-the-dora-report-2025 — Faros telemetry of 10k+ devs (+21% tasks, +98% PRs, flat org delivery); quantifies the rework evaporation. Accessed 2026-08-28.
  13. https://hypothesis.works — Hypothesis PBT documentation; the standard property-based testing tool for Python. Accessed 2026-08-28.
  ```

  **Lane status: complete.** All sections 0–9 delivered. Caveats carried in-line: the four `MEM:` files were unavailable (outside snapshot; repo copies used instead); `gh` had no usable remote, so PR-size statistics were computed from the 200 most recent squash-merge commits on `main` (median 170, p90 1,608 net lines, 66% ≤400); `git worktree list` in the snapshot is uninformative, and live worktree hygiene was evidenced through PENDING-ARMS healer rows instead. 24 repo paths verified on disk this session; 13 external sources cited.

