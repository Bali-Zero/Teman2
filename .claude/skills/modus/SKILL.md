---
name: modus
description: >
  USE FOR EVERY non-trivial mandate — feature, fix, refactor, research, audit, ops, content —
  coding or not. The master operating loop of the organism: TRIAGE the mandate into a gear
  (1 liscio / 2 standard / 3 profondo), then drive GROUND → DESIGN → BUILD → VERIFY → SHIP+ARM →
  PROVE-LIVE → ALIGN-FLEET → CLEAN → CAPTURE, routing the full arsenal at maximum-without-waste
  (Fable 5 architect+final-gate, Sonnet 5 implementers, Codex red-team+sandbox, Gemini agy width,
  DeepSeek/GLM refuters, Ollama local for PII, NotebookLM ground-truth). Supersedes opus-mythos
  (2026-07-02): Fable is native again — the width-surrogate retires; its deep/wide TAC patterns
  live on as Gear 3. SKIP only true one-liners — and declare it: "GEAR 1: <why>".
---

# MODUS — the master loop (request → prod → fleet → clean → learned)

> **Lineage.** `research/operations/2026-06-30-claude-code-perfect-session-doctrine.md` is the
> LAW (4 failure axes + 7 session-organs + 3 disciplines, adversarially validated). This skill is
> the LOOP that executes those laws across the whole **task arc** — a task may span sessions,
> machines and days; the doctrine's organs stop at session CLOSE, modus does not stop until the
> change is **live in prod, propagated to the fleet, cleaned up after, and learned from**.
> Born 2026-07-02: Fable 5 returned (Mythos-class native), Sonnet 5 exists. The doctrine explains
> WHY; modus tells you WHAT TO DO NEXT. Council-reviewed at birth (Codex red-team + Gemini
> costruttivo; DeepSeek seat dead — probed live, HTTP 402 — which is itself the lesson).

> **The one line:** _triage before ceremony; ground before reasoning; isolate before building;
> probe the work, not the proxy; armed is not built; live is not merged; the fleet is not one
> machine; clean after yourself; write down what bit you._

---

## STAGE 0 — TRIAGE: pick the gear (the anti-sperpero brain)

Classify the mandate from its text + the loop ledgers — a PROVISIONAL gear, announced in 1 line:
`GEAR <n>: <mandate> — <why this gear>`. GROUND then confirms or RE-GEARS it: the gear is
falsifiable, not a vow — blast-radius is often unknowable before reading, and under-gearing
tasks that merely look small is the systematic failure mode. Read the ledgers:
`.claude/skills/modus/PENDING-ARMS.md` (anything suspended from previous runs that this task
touches?) — AMENDMENTS.md is maintained at CAPTURE, read by the bench.

| Gear                    | When                                                                                                                                                        | Ceremony                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **1 · LISCIO** (smooth) | typo, rename, known-cause 1-file fix, pure question, mechanical edit                                                                                        | Skip to BUILD→VERIFY→CLEAN (micro). No council, no fan-out, no Workflow. Declare the skip.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| **2 · STANDARD**        | feature / fix / research with deliverable; anything producing a PR                                                                                          | Full loop, solo-orchestrator. 1 adversarial spalla (independent reviewer, LLM ≠ author) at VERIFY. Subagents only for independent READS or ≥3 parallel well-specified units.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| **3 · PROFONDO** (deep) | deep/wide audit (TAC), architectural decision, migration, cross-system investigation, pre-deploy critical path, client quotes, "vai da solo e non fermarti" | Full loop + Workflow-tool orchestration + the TAC patterns (ex opus-mythos): decompose by ANATOMY not to-do; hunt the SECOND-ORDER pattern (the malattia-delle-malattie — a MANDATORY "§Meta-pattern" section in the deliverable report: what repeats across the findings, which single defective belief generates them); cure-while-diagnosing (spawn fixers for clear+low-risk+in-perimeter findings — in their OWN worktrees, only after the evidence they touch is snapshotted in the report; never mutate a surface still under diagnosis); stop at the operator boundary (a "§Solo-operatore" section in the report: physical / strategic / operator-only actions). Council only if its gate fires (the anti-sperpero rules under TRIAGE). |

**Anti-sperpero rules (BUDGET made a router):**

- **Council is NOT automatic at Gear 3.** Convene it only if ALL THREE: divergent priors can change
  the answer ∧ error costs >15× tokens ∧ genuinely parallel breadth. Else: solo + more reasoning
  budget + 1 red-team spalla (evidence: 1 agent with 10× budget beats homogeneous debate at ⅓ cost).
- Fan-out only when items ≥3 and independent. Fan-out for READS, funnel-in for WRITES.
- Prefer one agent + more budget over N agents (coding barely parallelizes — Anthropic/Cognition).
- Cache-aware waiting (session polling only — the cadence for an external system matches THAT
  system's rate of change): ≤270s (inside the prompt-cache window) or commit to 1200s+; never ~300s.
- Stop-loss: at Gear 3 declare the budget shape up front ("~N agents, ~1 council").
- Escalate gear mid-flight if the terrain grows (RECONCILE); NEVER de-escalate silently — say it.

---

## THE STAGES (1→9)

| #   | Stage           | Goal                    | Driver                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | The PROBE (what proves it, not what claims it)                                                                                                                                                                                                                                                                                   | Scars killed     |
| --- | --------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| 1   | **GROUND**      | Terrain before plan     | `/stadio-zero`: mem+scar query, hot-files verified ON DISK, PII scope, falsifiable acceptance. **Quote the applicable scar ANTIDOTE lines into your working notes** — a scar you only counted doesn't restrict you. Plus reuse-first (search existing code/world before building).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | Every LOAD-BEARING file:line — one you are about to build on — re-executed THIS turn (current evidence for critical claims, not blanket re-reads of every citation). A path from memory/report/spec is a PHANTOM until re-grepped.                                                                                               | #6 phantom       |
| 2   | **DESIGN**      | Decide, adversarially   | `sota-architecture-loop` steps 0-4: frame → ground → reason → council-gate → decision. **Output = a durable spec artifact on disk** (scratchpad or `specs/` — BUILD consumes the file, not the chat memory). Operator GO for L2/L3 risk classes (AUTONOMOUS_OPS preflight). NLM is the ground-truth VERIFIER of facts here, not a reasoning seat.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | A falsifiable metric on the decision. Council verdicts are LEADS — re-verify what they attack AND what they bless (W65: even the refuter hallucinates).                                                                                                                                                                          | #3, groupthink   |
| 3   | **BUILD**       | Execute, isolated       | Worktree via `scripts/agent_start.py` (main checkout read-only; hotfix-preemption gets its OWN lane — worktrees make stashing unnecessary). TDD where testable (code); for non-code deliverables the falsifiable acceptance criteria from GROUND play the test's role. `karpathy-discipline` (no silent assumptions, no collateral edits). Implementer routing → Arsenal. Leave-dirty toward siblings' files.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Tests written first fail→pass. Diff scoped to the mandate — every changed line traceable to it.                                                                                                                                                                                                                                  | #5 sibling       |
| 4   | **VERIFY**      | Prove each increment    | CONTINUOUS, not close-loaded (context-anxiety makes CLOSE the worst first-verify point). Generator≠grader: `infra/workflows/verify-template.js`, `codex-second-opinion`, devils-advocate. Adversarial fixtures (edges, not happy path). Risk-proportional depth.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | The WORK by CONTENT (W88 blob-compare; never SHA-ancestor / timestamp / substring / exit-code). Fable does the last grep — never delegable, never cascadable: the final gate is an EMPIRICAL disk/live check, not a quality opinion (quality already had its independent grader; empiricism needs execution, not heterogeneity). | #2, #6, #9       |
| 5   | **SHIP+ARM**    | Land it end-to-end      | Atomic commits (conventional msg + co-author). PR — opened only AFTER VERIFY passed, so **arming `gh pr merge --auto --squash` immediately** (standing rule 2026-06-25) never merges unreviewed work, by construction (exceptions → operator merges: guardrails, config-critical, migrations, force-push). **Derived contracts travel IN the commit you arm on (W86):** if the diff moves a DOCSYNC-counted surface (backend tests/routers/services), run `python scripts/docs_sync.py` and fold the regen into the SAME commit BEFORE arming `--auto` — with `--auto` there is no 'later': merge fires at first green and any post-arm commit is orphaned. Bump already missing on a pushed PR → open a 1-line repair PR (like #1672), never re-push racing the merge. CI watch async — fire-and-sleep, never busy-wait; merge-train awareness on strict CI. **Deploy follows MERGE** — main is the only deployable ref (Vercel auto-deploys main; `fly deploy` runs from post-merge main via `nuzantara-deploy`; never deploy an unmerged branch). **Capture a pre-deploy baseline** (public health, key endpoints, log tail) so the post-deploy delta is attributable; **migrations get a post-deploy DB-state probe BEFORE public exposure** (upgrade applied? schema as expected?). Then the **ARMED reconciliation**: merged? deployed? installed? loaded? env propagated? cron armed? — anything built-but-not-armed = **SUSPENDED: write a line in `.claude/skills/modus/PENDING-ARMS.md`** (the W81 ledger — read back at every TRIAGE). | Each arming step probed by its own state (PR state=MERGED; `fly status`; `launchctl print` exit AND log content), not by "I ran the command".                                                                                                                                                                                    | W81, W86, #7     |
| 6   | **PROVE-LIVE**  | Done = live in prod     | curl/smoke on the PUBLIC domain against the pre-deploy baseline; runtime state; READ THE OUTPUT/log, not the exit code. Post-deploy browser QA when frontend. **Probe FAILS → STOP-THE-LINE**: no CLEAN, no CAPTURE-as-done — rollback (`fly releases` / revert PR / flag off / migration backout), keep the branch alive, escalate to the operator if prod isn't restored; a broken prod outranks every downstream stage. What cannot be proven this turn (cron liveness, async jobs, propagation) → a DURABLE RECEPTOR + reconciliation at the next boundary — never a fake this-turn check.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | The feature observed working in production, by content. Green ≠ working. `✔ Connected` = TCP handshake, not auth — run `SELECT 1`.                                                                                                                                                                                               | #2, 503-RAG, W87 |
| 7   | **ALIGN-FLEET** | 3 machines = 1 organism | M5/Pro/Mini — MAIN checkouts only (per-task worktrees are exempt; never disturb a sibling's live session: dirty main or active session on a node → skip + `PENDING-ALIGN:<machine>`, never stash/checkout someone else's state): `git pull --ff-only` on siblings (Pro first); restart consumers of changed code; skill/symlink liveness; HOME-fork lint (`cmp -s` repo-vs-live for anything executed from $HOME); plist/TCC liveness where launchd touched (W84: exit-code green can mask TCC death — read the log). Machine-aware paths (`balizero` on M5, `nuzantara` on Pro/Mini). **Partial fleet: if a sibling is unreachable, write `PENDING-ALIGN:<machine>` to PENDING-ARMS.md and PROCEED — never block the loop on a dead node.**                                                                                                                                                                                                                                                                                                                                         | `git rev-parse HEAD` identical on all reachable MAIN checkouts; restarted consumers show a fresh heartbeat/log line, not just a PID.                                                                                                                                                                                             | #1, #10, W84     |
| 8   | **CLEAN**       | Deep hygiene            | Worktree reap only at 3-AND (no live process ∧ no active lease ∧ content-on-main). **Branch delete only after BOTH: PROVE-LIVE passed AND content-on-main verified by BLOB-per-file** (W88 — the three-dot diff lies post-squash; a failed prod verification needs the branch alive for rollback). Scratchpad purged. Leases released. Background tasks stopped. `git status` clean OR leave-dirty declared with owner+reason.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | `git worktree list` back to baseline; no zombie branch of this task; no orphaned process.                                                                                                                                                                                                                                        | #5, W62/W80, W88 |
| 9   | **CAPTURE**     | Learn, then close       | `mem save` (decision 8-10, discovery 7-8 — don't ask, save). `scar` + superscar family if a trauma occurred. Research capture if ≥400 words + ≥3 sources. **AMENDMENTS entry if the LOOP ITSELF misfired** (wrong gear, wasted council, skipped probe that bit — see Self-refinement). Close line: `result:` / `needs input:` / `failed:` — self-contained.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | The memory/scar exists on disk after writing (re-`ls` it — Write can succeed and the file still vanish).                                                                                                                                                                                                                         | memory-loss, W78 |

---

## STATE & RE-ENTRY (tasks outlive sessions)

- **Durable state lives in files, not in the window:** the DESIGN spec artifact, PENDING-ARMS.md,
  the worktree itself. If it matters past this turn, it is on disk.
- **A "durable receptor" is one of three CONCRETE mechanisms, never an abstract intention:**
  (1) a PENDING-ARMS.md line — reconciled at every TRIAGE; (2) a SessionStart hook injecting live
  state at boot (escalations / organism receptors); (3) a harness background task — completion
  re-invokes the loop. When you defer a proof, NAME which receptor carries it.
- **On wake** (sleep, compaction, quota reset, session resume): emit a dense recap block
  (done / verified-live / next) **and re-run a light GROUND** — re-verify the hot files on disk
  before resuming the interrupted stage. The disk may have moved while you slept.
- **Preemption** (a Gear-1 hotfix interrupts a Gear-3 task): park the current worktree as-is
  (it is isolated by construction), run the hotfix in its own lane, return via the recap block.
- **Quota exhaustion:** implementation seats may cascade (Arsenal). **The final gate may NOT** —
  if Fable's window dies mid-task, the task SUSPENDS (PENDING-ARMS line + wakeup after reset),
  it does not hand the last grep to a weaker judge.

---

## THE ARSENAL — routing v2 (the Fable-5 inversion)

**The inversion.** opus-mythos dispatched external AIs to _surrogate the width Fable wasn't there
to provide_ (~75% strategy / ~25% power, the 25% prosthetic). Fable is here. External AIs now
serve what they are GENUINELY better for: **(a) heterogeneity** — adversarial gates need different
training priors; a Claude judging Claude is self-approval in costume; **(b) quota economics** —
MAX windows are finite, subscriptions are flat; **(c) specialized organs** — sandbox execution,
1M-context ingestion, $0 local PII processing.

| Role                                                      | Who                                                        | Invocation                                                                                                  | When                                                                                                                                                                                                                                             |
| --------------------------------------------------------- | ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Architect · orchestrator · judge · final on-disk gate** | **Fable 5** (max effort)                                   | interactive session default                                                                                 | Always. NEVER delegate or cascade the last grep (W65). Window dead → SUSPEND, don't substitute.                                                                                                                                                  |
| **Implementer fan-out**                                   | **Sonnet 5**                                               | `Agent`/`Workflow` `model:"sonnet"` (`claude-sonnet-5`)                                                     | BUILD: well-specified, parallel, testable units. Fable designs, Sonnet builds, Fable verifies.                                                                                                                                                   |
| **Grunt**                                                 | **Haiku 4.5**                                              | `model:"haiku"`                                                                                             | Mechanical lanes inside workflows (format, extract, classify).                                                                                                                                                                                   |
| **Red-team + empirical sandbox**                          | **Codex GPT-5.5**                                          | `codex exec --sandbox read-only / workspace-write` — **`< /dev/null` in scripts** (it blocks on open stdin) | Council red-team; migrations (upgrade+downgrade); independent second opinion on diffs.                                                                                                                                                           |
| **Width / ingestion + costruttivo**                       | **Gemini via `agy`**                                       | `agy -p` (3.5 Flash High default; 3.1 Pro for final architectural synthesis)                                | Corpus-scale reading; KBLI/visa/normativa search (Claude hallucinates regulations); pre-deploy red-team; council costruttivo.                                                                                                                    |
| **Refuter (council 3rd seat)**                            | **DeepSeek V4 Pro → GLM 5.2 → Codex** (probe-then-cascade) | key in `~/.openclaw/workspace/.env.master`; `claude-glm`                                                    | Falsification passes. **PROBE THE SEAT LIVE FIRST** — 2026-06-30 AND 2026-07-02 the key existed while the balance was dead (Esiste≠Armato at the arsenal level). A 2-seat heterogeneous council is acceptable-degraded — DECLARED, never silent. |
| **Second brain (quota relief)**                           | **GLM 5.2**                                                | `claude-glm` (Keychain token, isolated `~/.claude-glm`)                                                     | When MAX OAuth windows are cap-exhausted mid-task. Implementation only — never the final gate.                                                                                                                                                   |
| **PII / offline / $0**                                    | **Ollama** (Mini-first wrapper; local fallback)            | `ollama run qwen3.5:9b`; vision `qwen2.5vl:7b`; embed `bge-m3`                                              | Any transform whose PROMPT would carry client PII. If a cloud model must see the case: redact FIRST to `client_id`/placeholders — the gate is redaction-before-egress, not just model choice (Law 2 output boundary).                            |
| **Ground truth**                                          | **NotebookLM** (profile `default`)                         | `mcp__notebooklm-mcp__*`                                                                                    | Facts/normativa at GROUND and VERIFY: bipolar verifier — NLM verifies, it does not synthesize. Gemini = reasoning width; NLM = retrieval width.                                                                                                  |

**Council composition (when the gate fires):** proponente = the orchestrator · red-team = Codex
(_find the flaw; default to defective_) · costruttivo = Gemini (_save it by improving it_) ·
refuter = DeepSeek/GLM (_falsify the core claim_). Max 3 external seats, rounds capped, NEVER
consensus-seeking ("do you all agree?" generates conformity hallucinations). Verdicts are leads.

**Quota cascade (cron + subprocess):** Sonnet 5 → agy → Codex → Ollama, with a LIVE health-ping
per tier before trusting it (grep for `out of extra usage|quota|429`, fall through on match).
Reference: `~/scripts/regulatory-watcher-run.sh`. Cron tier-1 stays `claude-sonnet-4-6` until the
staged migration to Sonnet 5 is tested per-agent (tracked in PENDING-ARMS when started).

---

## CROSS-CUTTING (every stage, no exceptions)

- **BOUNDARY** — no secret in cleartext (0600, never `cat` a key — read var NAMES only), no
  PII/OSINT transcribed into any output/memory/log/artifact (SYMBIOSIS Law 2 / UU PDP). Redact
  before any cloud egress.
- **BUDGET** — verification depth ∝ blast-radius; council ≈ 15×; declare stop-loss at TRIAGE.
- **RECONCILE** — new operator input mid-run → restate it FIRST, re-derive acceptance, drop stale plans.
- **ASYNC** — any job >30s (CI, deploy, render, external LLM panel) → background + wakeup.
  Busy-waiting a panel in foreground is a violation, not a nuance.
- **OPERATOR BOUNDARY** — physical actions, secret rotation, strategic calls, self-doctrine merges →
  list them in the report's "§Solo-operatore" section and stop there. The operator's veto is not
  the safety layer; the guardrails are.

---

## SELF-REFINEMENT (the organ that sharpens the loop)

Honest name: self-**healing/refinement** — NOT recursive self-improvement (A4 terminology note
2026-06-28: these rings raise reliability, not model capability; the operator gate is the point).

1. **Per-run capture.** When the LOOP ITSELF misfires — wrong gear, council convened for a rubber
   stamp, a probe skipped that later bit, a stage that proved dead weight — append one line to
   `.claude/skills/modus/AMENDMENTS.md`: `date | what misfired | evidence | proposed change`.
   The loop's own scar file, distinct from cicatrix (organism traumas). It is an EVIDENCE LOG,
   not live doctrine: nothing in the loop executes from it; entries land on main through normal
   PR review and become doctrine only via an operator-approved SKILL.md change.
2. **`modus-bench` (on demand, ~monthly, or after a major harness/model release).**
   `Workflow({scriptPath: "infra/workflows/modus-bench.js", args: {today: "<YYYY-MM-DD>"}})` —
   parallel sweeps: INTERNAL (scars Δ30d + AMENDMENTS + PENDING-ARMS: _which recent traumas would
   this loop NOT have prevented?_) × EXTERNAL (Claude Code changelog, Anthropic engineering,
   frontier model releases: _which new capability should the loop exploit? which rule did the world
   obsolete?_) → every proposal faces an adversarial refuter on fresh context → survivors become an
   AMENDMENTS block. No new cron/daemon — 176 daemons exist and W84 proved launchd fragile; the
   bench runs when invoked.
3. **Operator gate, always.** modus NEVER merges changes to itself. Proposals land as AMENDMENTS
   entries or a PR; Zero decides (Legge 5). Model-generation events (as Fable 5's return killed
   opus-mythos's premise on 2026-07-02) are exactly what the bench exists to catch.

---

## ANTI-PATTERNS (the walking dead)

- Busy-waiting an external LLM/CI in foreground → background it, close the turn.
- "È benigno / si sblocca da solo" not falsified by a tool call THIS TURN → a stall in costume.
  Read the log NOW. (Recorded: a 6h-stuck render closed as "quota, self-resolving" — the log held
  a real crash loop.)
- Chasing a merge-train on strict CI with update-branch loops → arm `--auto`, let the queue drain.
- Council for a mechanical decision → 15× tokens for a rubber stamp.
- Green exit / `✔ Connected` / `bash -n` / CI-green as proof → that's the PROXY. Probe the WORK:
  real query, real render, real JSON out, real page in a real browser.
- A subagent's (or refuter's) claim treated as a verdict → it's a LEAD; expect 30-40% false-sick.
- Running all stages on a typo → sperpero. Say `GEAR 1` and go.
- A file:line you didn't re-grep this turn → a phantom you're about to build on.

---

## REFERENCES

- The LAW: `research/operations/2026-06-30-claude-code-perfect-session-doctrine.md` (4 axes, PR #1852)
- The scar families: `.claude/rules/cicatrix-superscar.md` (10 superscar + orphans; `scar query`)
- Entry gate detail: `.claude/commands/stadio-zero.md` · Architecture detail: `sota-architecture-loop`
- Adversarial verify artifact: `infra/workflows/verify-template.js` (A4, generator≠grader)
- Autonomy contract: `AUTONOMOUS_OPS.md` (L2) · Deploy: `nuzantara-deploy` skill
- Superseded: `opus-mythos` (2026-06-13 → 2026-07-02, archaeology — the surrogate-era artifact)
