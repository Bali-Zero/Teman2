---
date: 2026-08-26
domain: operations
client_case: none
sources:
  - workflow journal (raw): `.claude/projects/-Users-nuzantara-nuzantara/2fb2684a-.../subagents/workflows/wf_eb832a9d-0ec/journal.jsonl` — 11 agents (4 ground readers, 3 lenses, 3 cross-family refuters, 1 synthesis), 267 tool calls, 1.87M tokens, 40 min, 0 errors
  - approved plan `~/Desktop/2026-08-26-PIANO-SPEC-receptor-live.md` (Zero, plan mode; lives outside the repo because `host_boundary.py` has no carve-out for `plans/`)
  - codex-gpt-5.6-sol-ultra — third-round blind seat (owner-pasted, did not read the retro)
  - kimi-k3-max — third-round blind seat (owner-pasted, did not read the retro)
  - qwen3.8-max — third-round blind seat (owner-pasted, did not read the retro)
adversarial_review: kimi-k3
---

> The three blind-seat entries above are cited as sources per the capture instruction, but this
> document did not read their raw text — only Zero's own on-disk-verified synthesis of them in the
> plan's §5bis. Where this file describes what those seats said, it is reporting the plan's account,
> not a direct read of the seats' output.

# Fleet sessions retrospective — 25-26/08/2026

Zero asked for an honest verdict on the coding-session discipline that matured with Fable 5 —
**at most 2 topics per machine, super-focus, finish following a SOTA workflow, involve every LLM
tier** — measured against yesterday and today (25-26/08/2026), plus concrete "tricks" to fold into
`modus`. The measurement ran as `Workflow` run `wf_eb832a9d-0ec`: 4 read-only ground readers
(Sonnet 5) → 3 independent lenses (Opus 5, xhigh) → 3 cross-family refuters, all three alive
(Codex GPT-5.6 Sol 12,155 chars · Kimi K3 17,402 chars · Gemini agy 6,476 chars) → one synthesis
(Opus 5, xhigh) that **re-measured every number the four ground readers reported and corrected
three of them**. A fourth pass — three more seats (Sol Ultra, Kimi K3 Max, Qwen3.8-Max), blind to
the retrospective itself — checked the plan's own premises and added twelve more tricks (§6).

This document is the capture step of that plan's own sequence (§9 below). It is written in English
per repo convention; the plan it draws on is Italian.

---

## 1. The measured picture (window: 25/08 00:00 → 26/08 21:30 WITA)

### Throughput

| Metric | Value |
|---|---|
| Commits on `origin/main` | **119** |
| PRs merged (all bases) | **170** — 118 on `main`, **52 on `feature/*`** (kb-current 26, garuda-voa 23, due-bot 2, 1 nested) |
| Commit type | fix **63** (37%) · docs **61** (36%) · feat **35** (21%) · test 6 · chore 4 · ci 1 |
| Commits touching zero code files | **49/119 (41%)** |
| Commits touching ONLY ledger/scar files | **26/119 (22%)** |
| `docs(ledger)` = finding recorded, no cure | 23/170 (13.5%) — M5 14 · Pro 5 · Mini 4 |

A first pass at this window used `git log --since` without checking machine timezone and returned
169 commits instead of 119 — an 8-hour-wide boundary error on one end. Any `--since` query on this
repo needs the WITA window stated explicitly.

### Per machine

| | Pro | Mini | M5 |
|---|---|---|---|
| PRs merged | 54 | 28 | **84** |
| Sessions touched (interactive/automatic) | **298** (31/267) | 67 (28/39) | 21 (5/16) |
| Transcript bytes | 296.7 MB | 172.9 MB | 117.8 MB |
| Subagent dispatches | 329 | 227 | 289 |
| Distinct topics, 25/08 → 26/08 | 6 → **9** | 6 → 3 | **8** → 6 |
| Distinct lane branches, 25/08 → 26/08 | 4 → 6 | 5 → 3 | 6 → 6 |
| Largest session | 33.3 MB / 4,358 min / 122 dispatches | 48.2 MB / 1,973 min / 90 | **42.9 MB / 2,872 min / 209 turns / 123 dispatches (GARUDA VOA)** |

Fleet total: 386 sessions, 64 interactive, 587 MB, 845 dispatches. Peak **concurrent** interactive
sessions: 23/08 → 7, 24/08 → 9, 25/08 → 11, 26/08 → **12**.

### Finishing

| Metric | Value |
|---|---|
| PRs ≤400 net lines (the Agent PR Contract's own metric) | 110/170 = **64.7%** · 401-1500: 38 · **>1500: 22** |
| Largest PRs (gross) | #4959 **24,622** · #4974 18,561 · #4797 10,117 · #4960 5,201 |
| Lead time, median / p90 | **29.6 min** / **377 min (6.3 h)** |
| Retraction chains | **16**; the deepest #4869→#4873→#4880, all merged 25/08 (depth 2 = the edge of Contract rule 8) |
| Open non-Dependabot PRs, right now | **24** — 17 aged ≥48h, none "green and waiting": every title names a defect |
| A CLEAN, non-draft PR sitting un-queued for 3 days | **#4733** `memory-budget-gate` — a finished cure, stalled since 23/08 |
| Open Dependabot PRs | **13**, the oldest three from 24/08 (Contract rule 5 "serialize" silently disarmed) |
| Live worktrees on Pro | **⚠️ MEASURED 4** — CORRECTED: two independent Opus lenses reported 35 and 33; `git worktree list` run in this same session returned 4. The number had rotted ~9× with no reaper involved, and both lenses built after-targets ("35 → ≤8") on it. |

### LLM tiers actually involved

| Signal | Value |
|---|---|
| Assistant messages per model (fleet) | opus-5 **36,463** · sonnet-5 22,616 · fable-5 2,495 (2,007 on M5, ~13% of its traffic) · haiku 264 |
| Subagent dispatches by `model:` | sonnet **757/882 = 86%** · haiku **8 = 0.9%** · opus 12 |
| Shell calls to a non-Anthropic seat | ≈512 (codex 185, seat_build 101, kimi 112, agy 57, glm 39, nlm 12, qwen 5, **ollama 1**) ⇒ **0.58 per Anthropic dispatch — exactly the floor `model_routing_gate` Rule 2 enforces, no more** |
| `Workflow` tool (council) uses | **0** genuine uses fleet-wide — this retrospective is the only one |
| Evidence packs landed on main | **⚠️ MEASURED 13** — CORRECTED: one ground reader reported 1/170, looking only at root `evidence/pack.yml`; packs have lived at `evidence/<YYYY-MM>/<slug>/` since 23/08 |
| Packs with a single build lane | 18/20 → the D3 diversity rule **cannot fire** (`evidence_pack_lint.py:710` early-returns below 2 lanes) |
| Packs with a cross-family review lane | 5/20 = 25% ⇒ **≈3% of merged PRs** |
| PR bodies that *name* a non-Anthropic seat | 41/170 (24%) — prose, not an artifact; do not read this as review coverage |
| Doors (live ping, 26/08) | codex luna PONG · agy PONG · kimi config OK · ollama 5 models (2 new in 18h) · **TP1: 7 live models, zero doors** (`ai-dispatch.sh:1377` "probation-only, not wired"; `seat_build.sh` accepts only `codex\|kimi\|qwen`) |
| `arsenal_probe.py` | **0 crontab, 0 LaunchAgent** entries; latest board covered 3 of ~15 seats → reported "3 of 3 OK" |
| `infra/conductor` | registry **inert**: `calibrations`/`host_observations` empty, the loader's own docstring says "loading a card never grants an invocation path"; 77 dirty profiles = an uncommitted schema migration in progress |

### Guards verified by executing them, not by reading them

- `_is_anthropic_seat('the session on Pro running claude-opus-5')` → returns **NON-ANTHROPIC**
  (`evidence_pack_lint.py:624` looks only at the first token before the `-`): vendor parity is
  satisfied **by phrasing**.
- `compute_floor()` (`:273`) is **path-only**, no size term: #4959 (24.6k lines) got a brief only
  because it touched `.github/workflows/*`; #4960 (public UI, 5k lines) and #4797 (10k) got none.
- GitHub rulesets: exactly 2, both scoped to `refs/heads/main` → **nothing covers `feature/*`**:
  52 PRs merged into bases with zero required checks. The incident is already written up in
  `ASSEMBLY-LINE.md` L162-197, dated 25/08, and **is still unarmed**.
- `test_auto_merge_whitelist.py`: 24/73 red on a clean `main`, **0 workflows run it**.
- `immune-enforcement.yml:1110` writes `pending_arms_report` output to `$GITHUB_STEP_SUMMARY`,
  which nobody reads; it only blocks on `--strict-phantom`.

### Ledger, mailbox, context tax

- `PENDING-ARMS.md`: 2.06 MB / 1,433 lines; `pending_arms_report.py --json`: **586** entries,
  `tech_debt_overdue` **307 (52.4%)**, `operator_gated_overdue` **169**, combined **476 = 81.2%**.
  **⚠️ These are two different denominators — do not conflate them.** One retrospective trick (F5)
  wrote "before: 307 (81.2% of 586)", pairing the tech-debt count with the combined percentage; a
  refuter caught it. A ratchet built on the wrong pairing binds on the wrong population.
- Fleet mailbox: **94** broadcasts never archived (36 from 23/08, plus 7, 38, 13); the
  `.broadcast_seen` gate is per-session with no TTL, and `MAX_MESSAGES_PER_FIRE=3` from the oldest
  means every session **and every subagent** re-reads 3 days of backlog (~6M tokens/48h,
  estimated). 45/94 are `queue_unstick` pages; **#4664 was paged 12 times and is still BLOCKED**
  since 23/08.
- `AMENDMENTS.md` (the loop's own scar file): **zero entries on 24, 25, and 26/08** — the three
  days that produced 4 product mandates, a red merge onto an integration branch, and a mandate
  that corrected its own premise mid-flight. Its own 22/08 entry already said: *"this file got
  zero entries while it happened."* It happened again, on a different three-day window, after
  saying so.
- Traps this very retrospective session hit while producing these numbers: `worktree_isolation.py`
  blocks `cat > $SP/file` because it matches the literal string `$SP` instead of the expanded path;
  `host_boundary.py` blocks the plan-mode planning file itself; the mailbox replayed the 23/08
  backlog ~30 times in 40 minutes.

---

## 2. Judgment on the four claims

1. **"Max 2 topics per machine" — falsified, and the rule does not exist on disk.** 3-9 topics per
   host per day; the non-heuristic lane-branch count gives 3-6 and is a lower bound. Peak
   concurrency went 7→12 — the opposite of narrowing. The sentence lives in ONE line of
   `00-PIANO-FLOTTA.md` (M5, ephemeral). A rule that was never written cannot be violated, only
   misremembered.
2. **"Super-focus" — true per session, false per machine.** M5 stayed on one project directory per
   day; its GARUDA VOA session carried a mandate alone from start to finish. But 298 sessions on
   Pro in 48h and 12 concurrent interactive sessions say the MACHINE is a station, not a single
   track. The claim is true of the unit Zero was picturing (the session) and false of the unit he
   named (the machine).
3. **"Finish with a SOTA workflow" — the pipeline is fast, the work is not finished.** Median lead
   time 30 min, 65% inside the size contract, 13 packs, 27 required contexts. Against that: 41% of
   commits touch no code, fix+docs outnumber feat 124 to 35, 24 open PRs with 17 stale, #4733 (a
   finished cure) forgotten, 13 Dependabot PRs jammed, 476/586 ledger entries overdue, 16 retraction
   chains that nothing counted before this session. The organism is world-class at **starting,
   inspecting, documenting, correcting** and weak at **capping WIP and driving each lane to a live
   terminal state**.
4. **"Involve every tier" — the subtlest claim, and it is shaped like a gate.** 86% of dispatches go
   to Sonnet regardless of task, Haiku 0.9%, `ollama run` fired once, `Workflow` zero times, TP1 has
   no door, cross-family review touches 3% of PRs. What diversity DOES exist is produced by ONE
   PreToolUse hook (the 0.58 floor) — not by the roster, not by the packs, not by the conductor. And
   the guard the vendor-parity claim rests on is defeated by phrasing.

### Theater vs. real

**Verified theater (5):** the conductor · `arsenal_probe` (3/15 read as "3 of 3 OK") · vendor parity
(a prose classifier, plus a diversity rule that early-returns below 2 build lanes — inapplicable to
90% of packs) · `test_auto_merge_whitelist` (red, never executed by any workflow) · the mailbox
(94 files, perpetual replay).

**Real — three things actually ahead:**
1. Epistemic gates as required checks — generator≠grader, guilt+innocence, a floor recomputed from
   the real diff.
2. Retraction as a published artifact — 16 PRs in 48h that name the PR they reverse, at a 30-minute
   median lead time.
3. Postmortems compiled into runnable executables under a byte budget — 10 scar families, runnable
   antidotes, an index ≤14 KB with its own completeness test.

**The deepest tell (Kimi):** every number in this retrospective came from a one-time hand-written
parse. The organism instruments the LLM cost of the *product* as a required check and **has never
instrumented itself**.

**The meta-risk (Sol and Kimi, independently):** all three Opus lenses proposed 22 new gates as the
cure for a disease diagnosed as "ceremony without consumers." The survivors are, without exception,
the ones that convert an *existing* prose rule into a check **at a door that already exists**.

### The three refuters are not interchangeable (measured on all 22 tricks)

| seat | SURVIVES | WEAKENED | REFUTED | character |
|---|---|---|---|---|
| gemini-agy | **16** | 5 | 1 | most permissive; endorsed 73% of a list its own closing assessment called "elaborate theater" — read its SURVIVES votes as weak evidence |
| kimi-k3 | 15 | 7 | 0 | the only seat that **ran verification commands** and cited file:line it had actually checked |
| codex-sol | 6 | **12** | **4** | most severe; the only seat that attacked tricks on *kind* (alarm vs. breaker) rather than on detail |

Where agy was the *only* SURVIVES vote (F6, A4, F7), the synthesis downgraded the trick rather than
counting it 1-for-3.

---

## 3. The 22 tricks — three-seat verdict

Every trick below went to all three refuters independently; no verdict is inferred. `S` = survives,
`W` = weakened, `R` = refuted.

| id | trick | agy | kimi | sol | final status |
|---|---|---|---|---|---|
| S5 | Integration branch inherits `main`'s gates or is not born | S | S | S | **ADOPT** |
| A1 | Closed seat-token vocabulary — kill the prose classifier | S | S | S | **ADOPT** |
| S3 | State-keyed mailbox: TTL, key-dedup, page-on-transition | S | S | S | **ADOPT** (absorbs F3) |
| S1 | Blast-radius term in the gear floor | S | S | S | **ADOPT** |
| A7 | Daily seat-mix telemetry joined to PRs | S | S | S | **ADOPT** |
| A3 | Seat-report trailer, provenance from the diff | S | S | S | **ADOPT-WITH-CHANGES** |
| A2 | D3 bites at one build lane — mandatory review lane, non-Anthropic | S | S | W | **ADOPT-WITH-CHANGES** (after A1) |
| F4 | Correction-depth gate: rule 8 gets a counter | S | S | W | **ADOPT-WITH-CHANGES** (absorbs S4) |
| F2 | Finish-before-start: stale-PR debt gate at PR-open | S | S | W | **ADOPT-WITH-CHANGES** |
| S2 | Aging-WIP breaker for the pool that never queues | W | S | R | **ADOPT-WITH-CHANGES** (reshaped: enqueue, not alarm) |
| F5 | Ledger ratchet: a finding is free, rotting is not | W | S | W | **ADOPT-WITH-CHANGES** |
| S7 | Red-first proof for the journey test | S | S | R | **ADOPT-WITH-CHANGES** (sol's objection is correct and fixable) |
| S6 | Cost per landed change, for the fleet's own sessions | S | S | W | **ADOPT-WITH-CHANGES** |
| A4 | Scheduled full-roster door ping with coverage assertion | S | W | W | **ADOPT-WITH-CHANGES** |
| A6 | `seat_build --seat auto` | W | S | W | **PARK** (Gear-3 project, not a selection tweak) |
| F6 | Mandate burndown: MERGED-not-live escalates | S | W | W | **ADOPT-WITH-CHANGES** |
| F1 | Lane-admission cap at worktree-create | W | W | W | **PARK** (absorbs S8; 6 weakenings, 0 survivals) |
| F7 | Session budget: hand off before the third compaction | S | W | R | **ADOPT-WITH-CHANGES** (splits in two) |
| A5 | Force grunt-shaped dispatches to the cheap seat | R | W | R | **REJECT** |
| F3 | (mailbox variant) | S | S | W | absorbed into S3 |
| S4 | (mandatory AMENDMENTS line per retraction) | S | W | W | absorbed into F4 |
| S8 | (topic cap as a PR trailer) | W | W | W | absorbed into F1, PARKED |

Plus five tricks proposed by a single answering seat during refutation, not themselves reviewed —
adopted anyway because each is cheap and closes a rule already written in prose:

| id | trick | proposed by | lands in |
|---|---|---|---|
| X1 | Worktree + transcript reaper (retention, not admission) | kimi, agy (independently) | broker cron, reuses `branch_graveyard_cleanup.sh::content_on_main()` |
| X2 | Dependabot serialization, armed | kimi | `concurrency: dependabot-lockfile`, `cancel-in-progress: false` |
| X3 | Gate effectiveness ledger (shadow period, then retire) | sol | `docs/factory/ASSEMBLY-LINE.md` gate-lifecycle section |
| X4 | Operator-attention budget: one batched digest, hard cap | kimi | digest rework + `pending_arms_report.py` |
| X5 | Model-roster ↔ dispatch-path lint | agy | `scripts/lint_roster_dispatch.py` (new) |

**REJECTED, with the refuting reasons kept verbatim because they are the reusable part:**
- **A5** (grunt-shaped dispatches forced to the cheap seat) — Sol: *"A heuristic 'grunt corpus' is
  too ambiguous to deny work safely, and 'DENIED' combined with 'fail-open' is internally unclear.
  Optimizing for a 15% cheap-seat share invites routing theater."* Agy, independently: fuzzy
  classification "introduces disruptive retry loops without understanding actual task nuance." A5
  re-imports the exact defect A1 exists to cure: a substring/prose classifier deciding intent.

**Unanimous SURVIVES (A1, A3, A7, S1, S3, S5) share one shape**, and it is the single most reusable
finding of the round: every one of them converts an existing prose rule into a check at a door that
**already exists** (the pack linter, the harness-floor step, the mailbox hook, the ruleset API, the
`seat_build` wrapper). The weakened and refuted tricks, without exception, are the ones that add a
**new prose-shaped classifier** (A5, F1, S8) or a **new YAML ceremony** (F6).

### Where the seats corrected the two Opus lenses

- **Live worktrees**: kimi said 4; both Claude lenses said 35/33. `git worktree list` = 4. Kimi's
  deeper point survived: counts rot on their own, so a cap on *admission* (F1) does nothing while
  nothing caps *retention* — the reason X1 was promoted.
- **Ledger arithmetic**: sol caught the 307-vs-476 conflation described in §1 above.
- **S7's red-first proof**: the lens's own two conditions ("fails at merge-base" and "collected N>0
  on both sides") cannot both hold for a test the PR itself introduces. Sol was the only seat that
  read closely enough to notice; kimi and agy both voted SURVIVES.
- **S2 is an alarm, not a breaker**: sol showed the mechanism pages, writes another overdue ledger
  row, and leaves the work untouched — repeating the exact failure this retrospective diagnoses.
  Agy converged independently ("increases fatigue rather than unblocking").
- **Evidence-pack coverage, in the other direction**: a ground reader said 1/170 packs (root-only
  scan); the synthesis measured 13 real packs at `evidence/<YYYY-MM>/<slug>/`. Here a Claude lens
  was right and the ground reader was wrong — the pack mechanism is obeyed, not ignored; what it
  cannot see is size (S1) and lane-count structure (A2).

---

## 4. Three blind seats (Sol Ultra, Kimi K3 Max, Qwen3.8-Max) — did not read the retro

A fourth, independent pass fed the plan to three more seats **without** the retrospective's own
findings, to check whether its premises hold up against fresh eyes and to surface tricks the
11-agent workflow never proposed.

**Premises checked against disk in this same session:**
- **False**: "33 worktrees" (Sol Ultra's premise — registry says 4, disk says 4, 0 prunable);
  "the synthetic probe already operates at this level" (Kimi K3 Max — it is `ASSEMBLY-LINE.md`
  lines 79-80, zero code behind it).
- **Imprecise**: "161 orphan branches" (Qwen3.8-Max) — actually 90 remote + 11 local, 24 stalled
  >7 days, 0 merged-but-undetected because of the squash-merge cicatrix.
- **Everything else the three seats asserted independently checked out true**: missing identifiers,
  a 9-field `TaskMetadata`, lease heartbeats present but no fencing, the `command` hook type
  failing open under the official docs, 11 `SKILL.md` files diverged between `.agents` and
  `.claude`, and fleet-spec §3.2 having no automated checker.

**Three independent convergences (agreeing blind, from three different families) close three open
questions on their own:**
1. **Cell shape = 1 builder + 1 cross-family refuter + Opus 5 at the gate; a second refuter only on
   high risk; do NOT add more judges.** Kimi cited PoLL (arXiv 2404.18796) and Judging-the-Judges
   (2406.12624); Sol argued "subtraction"; Qwen's license was a one-line "Nit:". This caps the gate
   budget at ≤3 seats per decision.
2. **Admission needs a fail-closed lease** (`agent_lock:objective_slot:<host>:<1|2>`, extending the
   existing `agent_lease.py`) — the *commit* lease stays fail-open per repo CLAUDE.md §7; this is
   about admitting a NEW objective, not about an in-flight one.
3. **A receipt must be bound to the digest and signed by the gate, never by the builder**
   (in-toto Statement v1 shape: subject = commit SHA + diff hash, identity in the certificate,
   an inconclusive verdict fails closed, acceptance criteria photographed at start).

**Twelve new tricks this pass added** (full mechanism in the plan §5bis; landing points below):

| id | from | trick | lands in |
|---|---|---|---|
| Q0 | Qwen | **Skill canonicity (prerequisite, blocking, cheap)**: `.claude/skills` is the SSOT; port the 9 newest skills' 08-19 deltas into `.agents`, then generate/symlink `.agents` with a CI drift test | `.agents/skills/**`, `.claude/skills/**`, `scripts/tests/test_skills_canonical.py` |
| K1 | Kimi | **Gate-coverage ratio**: every PreToolUse gate writes an "I decided" marker; a Stop hook prints "N tool-calls with no decision"; audit mixed-unit timeouts in `settings.json` | `infra/claude-hooks/*` + declared HOME pairs |
| K3 | Kimi | **Artifact-on-death**: SubagentStop/SessionEnd writes worktree `git diff` + last state to `docs/handoff/<session>.md` | `infra/claude-hooks/session_budget.py` (absorbs the visible half of F7) |
| S-OC | Sol+Qwen | **Objective card** (outcome, non_goals, typed acceptance probe, stage, builder_family, grader_family, blocked_since, receptor, verified_sha), `acceptance_contract_hash` written by an actor ≠ the builder before the first write | `scripts/agent_start.py::TaskMetadata` (+9 fields), `scripts/agent_lease.py`, JSON schema |
| S7+ | Kimi+Qwen | S7 reformed: the gate re-freezes the probed surface (`git checkout <acceptance_sha> -- <probe files>`) before judging; no new probe breaks an existing one | `scripts/ci/prove_red_first.sh` |
| A3+ | Kimi+Qwen | A3 reformed as an in-toto Statement written by the CI job itself, three stages (test-receipt → review-capsule → gate/deploy consuming) | `scripts/seat_build.sh`, provenance job |
| A2+ | Qwen | Diversity checker reads the **declared provider in dispatch metadata** against `fleet-order-spec.md` §3.2 / `FLEET_TOPOLOGY.json` (family-exclusion, quorum 2 families, PROBATION seats excluded from quorum) | `evidence_pack_lint.py`, after A1 |
| F4+ | Sol | Review-loop stop: 2 rounds with no new confirmed evidence → closed; a 3rd instance of the same root cause escalates to a human receptor | `scripts/correction_depth.py` — PR #4547 took 11 rounds |
| X1+ | Qwen | `count/agent-branches` quota + `content_on_main()` reaper; over-threshold blocks new parent objectives | `scripts/branch_graveyard_cleanup.sh`, broker |
| X3+ | Sol | Randomized A/B of the second reviewer on eligible tasks; unique/confirmed/escaped finding counters | `docs/factory/SEAT-MIX.md`, A7's job |
| L-FIN | Qwen | Finalizer for CLEANED/CAPTURED: the terminal state is not skippable until cleanup-probe, snapshot, and ledger are all discharged | broker |
| P-EXP | Sol+Kimi | Premise expiry: `measured_at`/`expires_at`/`renewed_at`; the gate refuses a capsule citing an expired premise | objective card, `evidence_pack_lint.py` — this retrospective itself ran on a rotted premise (the "33" worktree count) |

**A new question for the owner, not in the original plan's switchboard:** should the admission lease
be **fail-closed** when Redis does not answer (no new objectives, existing work continues)? This
reads against the letter of repo `CLAUDE.md` §7 (guardrails degrade to pass-through on Redis outage)
but not against its intent (never lose work in progress) — Redis-down would block only *new*
admissions, not anything already running.

---

## 5. Do not do

Fourteen items, each tied to a specific refuted or weakened trick above:

1. **Do NOT build A5** (a prompt-regex classifier that denies "grunt-shaped" dispatches to expensive
   models). Refuted 2 of 3. It re-imports the exact defect A1 exists to cure. If the waste is real,
   change *defaults and effort* at the dispatch layer (effort is the measured primary cost lever on
   Opus 5 — ~86% of output is thinking) and judge routing by landed work and rework, never by a
   vendor/model quota.
2. **Do NOT ship three separate gates for one topic cap** (F1 admission + F6 clauses a/c + S8 PR
   trailer). All six seat-verdicts across F1 and S8 were WEAKENED; zero survivals. Write the rule
   first (it exists in NO tracked file today), measure breaches in NOTICE mode for a week, then
   pick at most one enforcement point.
3. **Do NOT quote "33-35 live worktrees."** `git worktree list` = 4, measured 26/08 21:29 WITA.
   Re-measure any count in the turn you cite it.
4. **Do NOT conflate the two overdue-ledger numbers.** `tech_debt_overdue` = 307/586 = 52.4%; 81.2%
   is the *combined* 476 (307 + 169 operator-gated). A ratchet on the wrong pairing binds on the
   wrong population.
5. **Do NOT add a new alarm channel before S3 lands.** 45 unresolved `queue_unstick` pages, one PR
   paged 12 times and still BLOCKED, 94 unpruned broadcast files, 169 operator-gated overdue items.
   A4's Telegram alerts and S2's paging would both arrive into a saturated channel and become the
   46th ignored voice.
6. **Do NOT force an `AMENDMENTS.md` line per retraction** (S4's compulsory-append half). Risks
   boilerplate diluting the scar-file signal against its own 14 KB injected budget. Citing an
   existing W-number must remain a first-class way to satisfy the gate.
7. **Do NOT block Stop on a missing handoff file** (F7's blocker half). Refuted on *kind*: writing a
   handoff after compaction imposes no budget at all — the session just continues. A Stop-block is
   the most intrusive lever in the fleet; a bad state-file write would kill every session on the
   machine.
8. **Do NOT wire the conductor to auto-route the full roster (A6) before the doors exist.**
   `seat_build.sh` accepts only `codex|kimi|qwen`; `ai-dispatch.sh:1377` calls TP1 "probation-only,
   not wired." Fresh health observations do not establish task fitness, quota headroom, or output
   compatibility.
9. **Do NOT read `arsenal_probe`'s board as fleet health.** The newest board probed 3 of ~15 seats
   and renders "live: 3, dead_strict: 0." Never cite it without its coverage denominator.
10. **Do NOT retro-edit the 20 existing evidence packs** to satisfy the new A1 seat vocabulary. They
    are receipts of what was declared at the time; rewriting them destroys the record drift would be
    measured against.
11. **Do NOT rewrite `MEMORY.md` with a whole-file Write** to fix its budget overage. It is not
    home-forked — it self-syncs across Pro/Mini/M5, and a full rewrite was clobbered by a peer on
    24/08. Use targeted Edits. (Its finished cure, PR #4733, is CLEAN and un-queued since 23/08 —
    merge it rather than re-solving it.)
12. **Do NOT count "PRs whose body mentions a non-Anthropic seat" (41/170) as review coverage.** It
    is prose. The structured measure is 5 of 20 packs ≈ 3% of merged PRs.
13. **Do NOT run `git log --since` windows without checking machine timezone** against the intended
    WITA window — see §1 above.
14. **Do NOT let "cost" language attach to S6's token numbers.** The seats are subscription-backed;
    say "measured output tokens." Do not headline a fix:feat ratio — it would discourage exactly
    the repair work this organism is unusually good at.

---

## 6. Owner decisions (Legge 5 — nobody else can make these)

1. **The topic cap, actually.** Is a "topic" a product mandate, a branch lane, or a session? Is the
   cap per MACHINE or per SESSION (per-session it already largely holds; per-machine it is off by
   3-4.5×)? Is 2 the number, or shorthand for "few"? Six seat-verdicts refused to arm any version
   until this is answered.
2. **The conductor: build or delete?** `infra/conductor` holds 77 dirty endpoint profiles and an
   86 KB capability index with a loader whose own docstring says loading a card grants no
   invocation path. Wiring it is a Gear-3 project of its own; the alternative is deleting the
   profiles rather than keeping a data set that reads as a router.
3. **Fable 5 on M5 (2,007 messages, ~13% of that machine's traffic)** — is this Zero at the
   keyboard, or a session self-selecting? The latter is a doctrine breach, and past ~50% weekly on
   the Team premium seat it becomes credits, i.e. paying.
4. **Research OS — abandoned, deferred, or superseded?** The 22/08 13-session plan was organized
   entirely around Research OS v1.0.0; zero of the 4 mandates that shipped 24-26/08 cite it.
5. **The gate budget.** Three lenses proposed 22 gates as the cure for a disease diagnosed as
   ceremony without consumers. A number from Zero (e.g. "at most N new required checks this
   quarter") lets sessions rank instead of accumulate.
6. **Repo settings for `feature/*`** (a ruleset creation = `operator[control-plane]`). S5's
   check-half ships without Zero; the arm-half needs his gesture or an explicit delegation.
7. **Dependabot: serialize (X2) or close in bulk?** 13 open, oldest three from 24/08.
8. **PII consent for S6.** Measuring the fleet's own token cost means reading transcripts that
   contain client PII in tool output. The emitter would extract aggregates only (branch, model,
   token counts), never message content, staying local on Mini.
9. **The admission-lease fail-closed question (§4 above, new from the blind-seat pass).** Fail
   closed on Redis-down for *new* objective admission only, or leave the existing fail-open
   guardrail posture untouched everywhere?

---

## 7. Enforced LLM-level rules — ordered by Zero: "enough prose"

Principle: **no trigger reads intent from a prompt** (A5 was rejected precisely for this). Every
trigger is deterministic — an agent type, a required flag, a diff path class, a measured token
count, a recomputed gear — and every rule has an enforcer that exits red, a published metric (A7),
and a shadow period (X3: 7 days NOTICE → FAIL; 0 denials in 30 days → retire).

### Seven enforcement surfaces (all existing, or extensions of existing ones)

| id | surface | what it does |
|---|---|---|
| E1 | `.claude/agents/<type>.md` frontmatter `model:` | the harness enforces the agent-def's model; `model_routing_gate` Rule 1 already blocks dispatches with no model and honors the frontmatter |
| E2 | `scripts/seat_build.sh` | `--tier` mandatory for a seat (exit 64 without it); effort capped per tier; `sol` ≥xhigh only with a `gear: 3` pack (exit 65); a context-window check rejects an over-budget prompt (exit 66) with the eligible-seat list; every call writes a seat-report (A3) |
| E3 | `scripts/evidence_pack_lint.py` | rules keyed by path class: `compute_seat_floor(changed_files)` alongside `compute_floor`; `ground_truth` lane on KB paths; local-only seats on PII paths; `council_run` on Gear 3; quorum via model-card `eligible_for_quorum` |
| E4 | CI job `seat-provenance` | `Seat-Report:` trailer mandatory on Gear≥2 and on mechanical-class PRs; log hash verified |
| E5 | `scripts/seat_mix_report.py` (A7) + `arsenal_probe.py --assert-coverage` (A4) + `lint_roster_dispatch.py` (X5) | daily scoreboard; ping of the *executable* set (incl. Jules, Spark, the 7 TP1 routes); a roster row with no route/door → UNREACHABLE or red |
| E6 | `infra/army/spark-queue/` (exists) + `infra/army/chore-queue/` (new) + `scripts/jules_dispatch.py new` (exists) + Spark harvester → PR | mechanical work queues and dispatches to the cheap/async seat from a Mini plist, not from an Opus session |
| E7 | `docs/factory/ASSEMBLY-LINE.md` §gate lifecycle (X3) | every rule below is born in NOTICE, publishes denial/override counts, retires at 0 denials/30 days |

### The twelve rules

| # | seat / tier | deterministic trigger | door | enforcer | A7 metric (today → measured target) |
|---|---|---|---|---|---|
| R1 | **Haiku 4.5** | `subagent_type` ∈ {`ledger-writer`, `lint-fixer`, `i18n-sync`, `fixture-gen`, `log-triage`, `catalog-meta`, `docs-sync`} — 7 new agent-defs with `model: haiku` | Agent tool (frontmatter) | E1 | Haiku share of dispatches: 0.9% → ≥10% |
| R2 | **Codex sol / terra / luna** | `--seat codex --tier sol\|terra\|luna` mandatory; default `role: build` → terra; `role: review` on Gear 3 → sol; mechanical class → luna | `codex exec -m gpt-5.6-{sol,terra,luna}` | E2: luna ≤medium, terra ≤high, sol ≥xhigh only with `gear: 3` | sol ≤30% of codex calls |
| R3 | **Kimi k3 / coding / highspeed** | `--tier k3\|coding\|highspeed` mandatory; `role: review` → k3; build → coding; mechanical → highspeed | `kimi -p … -m kimi-code/{k3,kimi-for-coding,kimi-for-coding-highspeed}` | E2 | per-tier histogram; k3 = default refuter for "is this true on disk?" |
| R4 | **Gemini flash / 3.1 pro** | `--seat agy --tier flash\|pro` mandatory; `pro` only for >200k input tokens or `--role synthesis`; **never** agy as a verdict-refuter (measured 73% permissive) | `agy -p … --model gemini-3.5-flash\|gemini-3.1-pro` | E2 context-check; E3 rejects an agy review lane on Gear 3 | flash/pro split; context-rejection count |
| R5 | **TP1**: deepseek-v4-pro, deepseek-v4-flash-0731, qwen3.8-max, qwen3.7-max, qwen3.7-plus, qwen3.6-flash, glm-5.2 | 6 sibling route JSONs of `glm-5.2-v1.json` + `--seat tp1 --model <slug>`; qwen3.8-max = mandatory Gear-3 council seat; PROBATION seats never count toward quorum | OpenAI-compatible route | E2 + E5 (X5: roster row with no route → UNREACHABLE); promotion to ARMED = 20 clean seat-reports | TP1 calls: 0 (excl. glm 39) → ≥1 per Gear-3 pack |
| R6 | **Jules** | chore-queue items: post-Dependabot bumps, `.agents` regeneration (Q0), Spark coverage-gap → test PRs, docs-sync, fleet-wide `lint --fix` | `scripts/jules_dispatch.py new` | E6 scheduled dispatcher + E5 ping | Jules PRs/week: 0 → ≥5 |
| R7 | **Codex 5.3 Spark** | nightly `codex/coverage-*` branches → harvester opens the PR within 24h; one branch/module/night | `scripts/army/spark_lane.sh` + `infra/army/spark-queue/` | repair `codex.spark_{loop,harvester,alarm}` (FAILED today) | Spark PRs merged/week: 0 → measured; max branch age |
| R8 | **NotebookLM** (ground truth) | a diff touching `apps/backend-rag/backend/kb/**`, `visa_engine` rules, KBLI data, pricing tables, `research/regulatory/**` → a pack with `{role: ground_truth, seat: nlm, nb: <id>, query_hash}` | MCP `mcp__notebooklm-mcp__*` (Pro/M5); Mini install = `operator[control-plane]` | E3 path class → red without the lane | ground-truth lane on those paths: ~0 → 100% |
| R9 | **`Workflow` tool (council)** | a `gear: 3` pack → `council_run: evidence/<pack>/council/journal.jsonl` from `infra/workflows/verify-template.js` with ≥2 distinct non-Anthropic review seats `ok=true` | `Workflow({scriptPath:"infra/workflows/verify-template.js", …})` | E3: missing journal / <2 ok seats / gear≠3 → red | council runs/week: 0 → = number of Gear-3 packs |
| R10 | **Local Ollama** (`qwen3.5:9b`, `qwen2.5vl:7b`, `qwen3.8:27b-mlx`, `muse-glimmer:30b`, `bge-m3`) | PII path classes (intake, CRM client data, WA message content, yield-optimizer) → every LLM lane must be `ollama-<model>`; a cloud seat on those paths → red unless `cloud_ok: <DPA ref>` + `pii_scan: clean` | `ollama run <model>` (cron) / `backend/llm/ollama_client.py` (HTTP) | E3; `qwen3.8:27b-mlx` = local refuter for PII lanes | ollama lane on PII paths: 0 → 100% |
| R11 | **Cheap seat floor for mechanical diffs** | a diff 100% in {ledger lines, i18n JSON, lint-only, generated fixtures, catalog metadata} → build lane on a cheap seat (haiku, luna, kimi-highspeed, qwen3.6-flash, deepseek-flash) or a counted `seat_override:` | — | E3 `compute_seat_floor` + E4 | cheap-seat share on mechanical PRs: ~0 → measured; overrides/week |
| R12 | **Explicit dispatch + scoreboard** | every `Agent` call carries an explicit `model` or frontmatter (R1, already armed); every external-seat call carries `--tier` (E2) | — | E1/E2 + daily A7 | the report exists: 0 → 1/day |

### Deliberately not here

- No imposed quota ("cheap-seat ≥15%") — only published. An imposed quota is A5, rejected 2-of-3.
- No prompt-text regex. Triggers are: agent type, flag, path class, counted tokens, gear.
- No rule without an enforcer. A line above with no file that exits red is prose, and gets removed.

### Starting PR package (after Q0)

1. E1 — 7 `model: haiku` agent-defs (R1), one PR, zero risk.
2. E2 — `seat_build.sh --tier` + effort cap + context-check + TP1 route (R2-R5), one PR + tests.
3. Six TP1 route JSONs + X5 lint (R5), one PR.
4. E3 — `compute_seat_floor` + ground_truth + PII-local + `council_run` (R8-R11), NOTICE-first, one
   PR, FAILs after 7 days.
5. Spark harvester + chore-queue + Jules dispatcher (R6-R7), two PRs, Mini plists.
6. A7 `seat_mix_report.py` (R12), one PR — the proof that everything else works.

---

## 8. Sequence (Day 0 / 30 / 60 / 90)

The plan's own §6 ordering (cheapest-leverage first, one PR per concern, naked `gh pr merge --auto`)
maps onto the day-scale shadow periods §4 and §7 already carry (S-OC: 0-30 SHADOW, 31-60 ENFORCE;
A3+: 61-90).

**Day 0 (tonight, 26→27/08):** Q0 skill canonicity — blocking, because until `.agents/modus` stops
routing to Fable, every external seat arms the wrong gate. This is `receptor-live`'s own lane L1;
see `docs/plans/2026-08-26-receptor-live/MANDATE.md` for the full 14-lane burst dispatched alongside
it tonight (§9 below covers what that dispatch itself measured).

**Day 0-30 — silence and closure (no new gates):** S3 mailbox · X2 Dependabot serialization ·
merge #4733 after a GraphQL re-check · X1/F7/K3 visibility (briefing counts, artifact-on-death) ·
K1 gate-coverage + timeout-unit audit · X3's first decision (`test_auto_merge_whitelist.py`: wire or
delete) · the starting PR package above (E1/E2/TP1-routes/E3-NOTICE/Spark+Jules/A7) · S-OC objective
card ships in SHADOW. HOME-side copies (`~/.claude/hooks/`) stay `operator[control-plane]`: sessions
deliver repo + declared pair + test, Zero applies with one command.

**Day 30-60 — the guards that lie:** A1 seat vocabulary → A2 review lane · S1 blast-radius term ·
S5's arm-half (the `feature/*` ruleset, `operator[control-plane]`) · X5 roster lint · S7+ reform ·
S-OC moves SHADOW → ENFORCE.

**Day 60-90 — instrument ourselves, then finish:** A7 daily seat-mix · A4 coverage-asserted ping ·
F5 ratchet at PR base-date · S6 (after the PII consent decision) · F4 `Corrects:` counter · S2
auto-enqueue (after S3) · F2 lane-debt in NOTICE · S7 red-first, reformed · F6 on one real mandate ·
A3+ receipt provenance (test-receipt → review-capsule → gate/deploy) · X1+ branch quota + reaper ·
F4+ review-loop stop · L-FIN terminal-state finalizer.

**Capture (this package):** the research doc you are reading, the `AMENDMENTS.md` entry, and the
fleet memory file — all shipped in the same PR as the Day-0 dispatch, per lane L12 below.

---

## 9. Tonight's dispatch-burst fact

Measured directly by this session, not inferred: **14 implementer lanes were dispatched in one
parallel burst on Pro** as part of arming the receptor-live mandate's Day-0/30 package. **13 of 14
tmux pane spawns failed** with `fork failed: Device not configured` (`ENXIO`) — a pty-allocation
race under a concurrent burst (31 of 511 ptys in use at the time; file descriptors were fine).
Dispatching sequentially, or 2-3 at a time, worked without a single failure.

This is the same failure class as the Mini `fork failed` incident of 23/08 (recorded in the fleet
mailbox, not yet promoted to a numbered scar): a resource that looks like it should scale with
concurrent Claude sessions — pty slots — is a small, shared, machine-wide pool, and a wide parallel
`Agent`/tmux burst can exhaust it well before CPU, memory, or the model's own rate limits notice
anything is wrong. It is also a direct, mechanical instance of what K1 (§4 above) exists to
measure: a hook or spawn path that fails does not always fail *loud* — here the failure was loud
(`ENXIO` on 13 of 14 attempts), but the lesson generalizes to the hook-type contract Kimi K3 Max
flagged in the blind-seat pass, that Claude Code's `command` PreToolUse hooks **fail open** under
load per the official documentation: a gate that times out or crashes does not block, it passes.
K1's "N tool-calls with no decision" counter is the mechanical receptor for exactly this class of
silent failure; tonight's burst is the loud sibling of the same underlying resource-contention
problem.

Practical rule this session is applying to its own remaining dispatches, and recording for the
fleet: **cap concurrent subagent/tmux spawns at ≤3 on Pro**, not because of model quota, but because
of pty exhaustion under this machine's current `kern.tty.ptmx_max`.

---

## 10. Method note

Every number tagged MEASURED in this document was re-executed inside the retrospective's own
synthesis pass or inside this capture session — never taken on a ground reader's or a lens's word
alone. Where a number is an estimate (the mailbox's ~6M-token/48h re-read tax, the ≈512 non-Anthropic
shell calls), the source table already says so. The three corrected numbers this document exists to
prevent from re-circulating: **live worktrees 33/35 → 4**, **evidence packs on main 1/170 → 13**,
**the ledger's 81.2% is the combined figure, not `tech_debt_overdue`'s 52.4%.**
