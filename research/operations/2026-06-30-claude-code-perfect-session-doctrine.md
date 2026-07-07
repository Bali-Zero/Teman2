---
date: 2026-06-30
domain: operations
client_case: none
sources:
  - Anthropic, Effective context engineering for AI agents (2025-09-29)
  - Anthropic, How we built our multi-agent research system (2025-06-13)
  - Anthropic, Building effective agents — Schluntz & Zhao (2024-12)
  - Anthropic, Code execution with MCP (2025-11) + Claude Code best practices (2025)
  - Cognition / Walden Yan, Don't Build Multi-Agents (2025-06-12)
  - HumanLayer / Dex Horthy, 12-Factor Agents (2025)
  - Chroma, Context Rot — Hong/Troynikov/Huber (2025-07)
  - MemGPT→Letta (arXiv 2310.08560) · Generative Agents (Park 2023) · LangMem
  - Chain-of-Verification (Dhuliawala 2023) · Judging with Many Minds (arXiv 2505.19477, 2025)
  - Internal: .claude/rules/cicatrix-superscar.md (98 scars, 10 families) + live disk audit 2026-06-30
  - Multi-LLM panel this session: Claude subagents ×2 + Gemini agy 3.x + Codex GPT-5.5 refuter (DeepSeek dead — see §8)
---

# Claude Code in Nuzantara — Doctrine of the Perfect Session

> **Mandate (Zero, 2026-06-30):** "un essere perfetto da quando comincia la sessione a quando
> la chiude, con zero allucinazioni e tutto funzionante."
>
> This document is the materialization of that mandate. It is grounded in the global frontier
> of agentic-session engineering (Jan 2025 → mid 2026), fused with the organism's own 98 scars,
> and **dogfooded in its own construction**: the meta-pattern below was passed to an adversarial
> refuter (Codex GPT-5.5, a different model family from the author) which reshaped it — that
> reshaping is shown in §6, not hidden. Generator ≠ grader, in the very act of writing this.

---

## §0 — Executive: the one sentence, and why it is not the whole truth

The naive thesis — *"every failure is one disease: treating an artifact's EXISTENCE as proof of
its VERIFIED LIVENESS; the cure is to probe liveness in this turn at every step"* — is **dominant
but not universal.** Under adversarial refute it fractured into **four root axes**. Conflating them
prescribes "more probes" where the real missing control is authority, isolation, confidentiality,
or budget. The honest doctrine is therefore not one law but a **map of four axes, each with its own
control**, plus a **session spine** (7 organs) that applies the right control at the right boundary,
plus **three cross-cutting disciplines** the refute exposed as missing.

"Zero hallucination" is the session-level name of **Axis 1 done right.** "Tutto funzionante" is all
four axes done right. They are different controls; do not collapse them.

---

## §1 — The four axes (the malattia-delle-malattie, bounded)

| # | Axis | The failure | Dominant scar families | The control (NOT always "probe") |
|---|------|-------------|------------------------|----------------------------------|
| **1** | **TRUST-IN-ARTIFACT** | An artifact's existence / a success-claim is promoted to verified-truth without a proportionate, epistemically-independent check of the *actual work*. | **#2 Esiste≠Armato**, **#6 phantom-citation**, **#9 schema-drift-by-proxy**, premature-completion, *hallucination itself* | **Probe the WORK** (not a proxy), effort ∝ blast-radius, grader epistemically ≠ producer. Collapses to a cheap existence-check when the artifact is content-addressed/immutable. |
| **2** | **AUTHORITY / canonicality** | Two artifacts both exist and both are live, but one is the wrong *authority*. A probe against the wrong clone passes and is still false. | **#1 HOME-fork drift** | **Single source of truth** + lint that fails on divergence (`cmp -s` repo-vs-live). Liveness ≠ canonicity. |
| **3** | **ISOLATION / ownership** | Parallel actors, both fully live, collide on shared state. Not blindness — concurrency. | **#5 Sibling-race**, **#10 split-brain** | **Partition, don't probe**: dedicated worktree per agent (`agent_start.py`), declarative `assigned_node`, leave-dirty toward siblings. |
| **4** | **CONFIDENTIALITY + RESILIENCE** | The artifact's *existence* with wide perms IS the failure (secret); or a live connection drops a transaction (flap). | **#4 Secret-in-clear**, **#8 network-flap**, **#7 KeepAlive** | **Minimize / contain** (chmod 0600, redact, Fly secrets) and **retry/keep-alive** (`SELECT 1`, `InterfaceError`). A probe here can *worsen* it (re-emit the secret). |

> **Codex refute, accepted (§6):** Secret-in-clear and Sibling-race do **not** fit Axis 1 — for a
> secret, existence *is* the failure; for a race, both actors are live. HOME-fork is Axis 2, not 1.
> The thesis survived by *narrowing*: Axis 1 is the dominant axis and the one tied to "zero
> hallucination," but it is one of four, not the whole.

**Axis 1 is the spine of this doctrine** because it is the one the mandate names ("zero
allucinazioni"). The rest of the document operationalizes it without forgetting the other three.

---

## §2 — The session as 7 organs + 3 cross-cutting disciplines

Decompose by **anatomy, not to-do** (opus-mythos #1): a checklist has silent holes; a body does not.

### The 7 sequential organs

| Organ | Goal | Driver (tool / LLM / skill) | Axis-1 PROBE (what proves the step, not what claims it) | Scar killed |
|-------|------|------------------------------|---------------------------------------------------------|-------------|
| **1 BOOT** | Load context: memory, heartbeat, repomap, escalations, machine-check | SessionStart hooks (15) → `mos-db`, `organism_alert`, repomap inject, **+escalations receptor (new)** | Receptors inject **live disk state**, not prose. A hook is a receptor; documentation is not. | #2 (the 28-day heartbeat blindness) |
| **2 GROUND** | Orient before reasoning: disk-state, PII scope, falsifiable acceptance | `stadio-zero` skill: memory-hits → **hot-files VERIFIED on disk** → PII scope → acceptance criteria | `ls`/`Read`/`grep` the cited path **in this turn**. A file:line from memory/report is a phantom until re-grepped. | #6 phantom-citation |
| **3 FRAME** | Decompose; decide council-vs-solo; skill discovery | `sota-architecture-loop` + `karpathy-discipline`; skill-catalog gate | The council gate is a probe of *necessity*: 3 conditions true or it's 15× tokens for a rubber stamp. | over-orchestration / decay |
| **4 DISPATCH** | Execute with isolation + right model | `agent_start.py` worktree; **fan-out for reads, funnel-in for writes**; multi-LLM routing (§4) | Each write lands in an **isolated worktree** (partition = Axis-3 control). Reads fan out; writes stay single-threaded. | #5 sibling-race |
| **5 VERIFY** *(continuous, not a gate)* | Prove each increment | empirical gate: `pytest` / `verify` cmd / `codex --sandbox` / `curl`; adversarial refuter ≠ producer | Probe the **WORK by content** (W88), with **adversarial/edge fixtures** (not happy-path), graded by an **epistemically-independent** model. | #2, #9, hallucination |
| **6 PERSIST** | Capture, with a "should this exist?" gate | atomic commit (conv. msg + co-author); `mem save`; `scar` | Commit/memory/scar pass a **boundary gate** (no PII/secret in cleartext — Law 2) *and* a "is this true & worth remembering" gate. | #4 secret, wrong-doctrine persist |
| **7 CLOSE** | Reconcile + handoff (NOT first verification) | `stop_verify.py` hook; `result:`/`needs input:`/`failed:` line; handoff for resume | Dirty-state is intentional or committed; the **build≠armed** reconciliation (W81): anything created-but-not-merged/installed/armed is flagged *suspended, not done*. | #2 Armamento Sospeso |

### The 3 cross-cutting disciplines (apply to ALL organs — the refute's gift)

- **A. VERIFY-CONTINUOUS (not close-loaded).** Frontier "context anxiety" (Anthropic, 2025-06):
  agents *rush, skip verification, cut corners as the window fills* — so CLOSE is the **worst** place
  to first verify. Verify each increment at DISPATCH, checkpoint, summarize while context is fresh.
  A final-only VERIFY gate is exactly where the agent rationalizes. *(Codex #16.)*
- **B. BOUNDARY (security/PII/egress, first-class).** Not a sub-bullet of GROUND. Every organ:
  no secret in cleartext (chmod 0600, never `cat` a key), no PII/OSINT transcribed to any output/
  memory/log/artifact (SYMBIOSIS Law 2, UU PDP Art. 67-68), redact before any cloud egress.
  *(Codex #12, #15, #17.)*
- **C. BUDGET / ALTITUDE (cost-latency-risk stop-loss).** Council = ~15× tokens; multi-agent = 4–15×.
  A "perfect session" without a stop-loss is unbounded. Verification depth is **proportional to
  blast-radius**, not maximal everywhere. Numeri prima (Symbiosis L7). *(Codex #10, #14, #19.)*
- **D. RECONCILE (mid-run human course-correction).** Long sessions get redirected. New user input
  → restate it first, re-derive acceptance, abandon stale plans. Humans correct by **editing context,
  not injecting commands** (12-Factor 3). *(Codex #13.)*

---

## §3 — The liveness-probe discipline, operationalized (Axis 1, post-refute)

A probe is not "re-run everything, every turn, forever." It is five disciplined rules:

1. **Risk-proportional.** Probe depth ∝ blast-radius. High-blast (auth, billing, migration, deploy,
   PII, prod mutation) → full E2E + adversarial fixture. Low-blast (code search, a doc edit) →
   cheap existence check. Universal E2E *worsens* context-anxiety (Codex #10). *(The opposite
   doctrine — existence is good-enough — is **right** for content-addressed/immutable artifacts:
   commit hashes, lockfiles, signed CI, reproducible builds. Codex #18.)*
2. **Probe the WORK, not a proxy.** `bash -n` passing is not the receptor working; a green smoke
   test is not the feature working; "refuter says OK" is not the finding being true. Verify by
   **content** (W88 blob-compare), never by SHA-ancestor / timestamp / substring / exit-code.
   Otherwise it is **probe theater** — artifact-substitution in a new costume (Codex #11).
3. **Epistemically-independent grader, bounded by risk.** "Different actor" is not enough — the
   grader must have different priors/method/fixture (a judge sharing the producer's prompt
   rubber-stamps: judge-conformity, arXiv 2505.19477; Codex #5). And the regress is **bounded**:
   you verify the verifier only as far as blast-radius warrants; the buck stops at the
   operator-facing gate (always Opus on disk — opus-mythos W65). *(Codex #9.)*
4. **In-session vs out-of-session.** What can be proven **this turn** (a file, a test, a value) →
   prove it this turn. What **cannot** (cron liveness, deploy propagation, async jobs, overnight
   monitors) → the probe is a **durable receptor + reconciliation report at the next boundary**,
   NOT a fake this-turn check. The heartbeat receptor and the new escalations receptor (§7) are
   exactly this: they make out-of-band liveness visible at session start. *(Codex #8; scar W81.)*
5. **Adversarial fixtures.** "Live once on a synthetic event" ≠ "correct generally" (Codex #7).
   Probe the edges: real media payload, rate limit, timezone, empty input — not the happy path.

---

## §4 — The arsenal: routing map (verified reachable this session)

| Role | Tool / LLM | Verified state (2026-06-30) | When |
|------|------------|------------------------------|------|
| Orchestrator + final on-disk gate | **Claude Opus 4.8 [1m]** (this session) | live | always the last grep (W65) |
| Fan-out diagnostic (reads) | `Agent` subagents (Explore/general) | live (used ×2 this session) | 1/organ, parallel, breadth-first |
| Width / pattern-synthesis | **Gemini `agy`** 1.0.13 | ✅ live | hold the whole corpus hot; 2nd-order pattern |
| Adversarial refuter | **DeepSeek V4 Pro** → **fallback Codex** | ⚠️ **DeepSeek "Insufficient Balance"** → cascaded to **Codex 0.135.0** ✅ | refute the meta-pattern; ≠ producer family |
| Empirical sandbox gate | **Codex GPT-5.5** `--sandbox read-only` | ✅ live | run/verify code independent of writer |
| Ground-truth (facts/normativa) | **NotebookLM** MCP (~64 NB) | live | bipolar verifier — verify, don't synthesize |
| Local / $0 / PII-safe | **Ollama** (qwen3.5:9b, qwen2.5vl:7b, bge-m3, +glm-ocr, qwen3-vl:8b) | ✅ 6 models (drift vs CLAUDE.md — §8) | classify/vision/embed on PII data, never cloud |

**Live Axis-1 lesson, this session:** the audit reported the DeepSeek key "present ✅ (chmod 600)".
*Existence of the key ≠ liveness of the service.* The end-to-end call returned **Insufficient
Balance** — the refuter tier was itself **Esiste≠Armato**. Caught only because the probe was a real
API call, not a key-existence check. The cascade (DeepSeek→Codex) preserved generator≠grader.

**Routing rule (FRAME):** Claude hallucinates regulations → Gemini `search` for KBLI/visa/normativa;
import-chain/migration → Codex sandbox; grounding → NotebookLM; PII processing → Ollama local. The
council fires **only** when (1) divergent priors can change the answer AND (2) error costs > 15×
tokens AND (3) work is genuinely parallel-breadth — else solo + more budget (Anthropic/Cognition).

---

## §5 — Frontier grounding (sourced; condensed)

The global SOTA (Jan 2025 → mid 2026), cross-checked Claude-subagent vs Gemini, discarding Gemini's
unsourced specifics:

1. **Context engineering** (Anthropic 2025-09-29): treat context as scarce/degrading; **compact
   proactively before rot**, just-in-time retrieval (pointers not payloads), durable scratchpad
   files. Chroma (2025-07): all 18 frontier models degrade non-uniformly with length — *bloat >
   decay even at 1M tokens.*
2. **Memory** (MemGPT/Letta, Generative Agents): tiered working/episodic/semantic/procedural;
   **persist on state-change, retrieve on need**; memory-as-files (auditable, greppable) first,
   vectors for fuzzy semantic recall. No free consolidation — it's an explicit step.
3. **Multi-agent** (Anthropic 2025-06 vs Cognition 2025-06): orchestrator-worker wins research
   **+90.2%** but **coding doesn't parallelize** (shared state, dependencies). Reconciliation:
   **fan-out for reads, funnel-in for writes**; extra agents add *intelligence*, not *actions*;
   pass full traces. Default = one agent + more budget.
4. **Hallucination** (CoVe +23% F1; judge-bias 2024-26): generator ≠ grader; **fresh-context
   adversarial refuter beats consensus** (3-vs-1 majority *amplifies* shared error — conformity);
   verify physical state **this turn**.
5. **Verification** (Claude Code best practices): TDD-for-agents is the strongest pattern; the
   empirical gate beats self-declaration (*"agents declare done when they aren't"*); error-analysis
   -first evals; judge the **end state**, not each step.
6. **Long-horizon** (Anthropic 2025-06): agents are stateful + non-deterministic, errors compound;
   **"context anxiety" degrades reliability near close**; checkpoint durable state outside the agent;
   **human gate before irreversible actions** (12-Factor 7); **green ≠ working**.
7. **Tool/harness** (Anthropic code-execution-with-MCP 2025-11): keep tool results out of context
   (**150k→2k tokens, ~98.7%**); just-in-time tool-schema loading; **hooks enforce what prompts
   only request** ("own your control flow").

---

## §6 — Adversarial test (the dogfood, shown not hidden)

Per generator≠grader, the §1 meta-pattern was passed to **Codex GPT-5.5** (≠ Claude) with an
incentive to *destroy* it. Round-2 gate (opus-mythos #5 — refuter is a lead, not gospel):

**Accepted → reshaped the doctrine:** Axis 1 is not universal (secret-in-clear #4 and sibling-race
#5 fall outside it; HOME-fork is Axis 2) → **split into 4 axes (§1)**. "Producer-independent" needs
**epistemic** independence + **risk-bounded** regress (§3.3). "This-turn" fails for async →
**durable-receptor probe (§3.4)**. Close-loaded verification is backwards → **VERIFY-continuous
(§2.A)**. Three organs were missing → **BOUNDARY, BUDGET, RECONCILE (§2.B–D)**. The opposite
doctrine is right for content-addressed artifacts → **existence-check collapse (§3.1)**.

**Rejected (Codex over-reach, W65):** "the thesis collapses distinct classes into one metaphor, so
revise it away." No — the doc never claimed all 10 families; it claimed Axis-1 *dominance*, and the
dominant cluster (Esiste≠Armato + phantom + schema-drift + hallucination) genuinely shares the
existence-vs-liveness root. The refute *narrowed and strengthened* the thesis; it did not kill it.

**Verdict:** meta-pattern SURVIVES, reshaped from 1 law → 4 axes + 3 cross-cutting disciplines. This
is exactly what an adversarial gate is for, and it is *why this section exists in the deliverable.*

---

## §7 — Cura eseguita (fix-while-diagnosing, opus-mythos #4 — all tested this session)

Shipped in worktree `infra-perfect-session-doctrine`, end-to-end verified:

1. **Killed a live phantom-citation by the organism itself.** The SessionStart heartbeat alert
   (`organism_alert_sessionstart.sh:74`) cites `research/operations/2026-06-28-heartbeat-channel-
   dead-core-organs.md` on **every boot** — a file that **did not exist** (verified `ls` → No such
   file). Created it with the real heartbeat-channel-dead doctrine → the organism's own boot alert
   no longer hallucinates. *(Axis 1 / #6.)*
2. **Built the escalations receptor (cures the same blindness class, still open).** The organ
   heartbeat got a SessionStart receptor; the escalations board (`shared/escalations_pro.jsonl` +
   `~/.agent/decisions/claude_tasks/`) did **not** — read only by the manual `/escalations` command
   (15 SessionStart hooks, zero mention escalation — verified). New
   `scripts/hooks/escalations_alert_sessionstart.sh`: surfaces HIGH-first, **freshness-gated** (HIGH
   <14d only — the 576-file `claude_tasks/` is a graveyard; surfacing all would re-create the
   noise-blindness it cures — SNAPSHOT not graveyard), FAST/FAIL-OPEN/READ-ONLY, kill-switch
   `ESCALATIONS_RECEPTOR_ENABLED=false`. Tested: fires valid JSON (2 HIGH), kill-switch silent,
   freshness gate works. **Wiring into `~/.claude/settings.json` = §8 operator decision** (global
   config, every future session — conservative L2).
3. **A live dogfood, kept honest.** While building the receptor I inserted a dedup block at the
   wrong indent → orphaned `except` → Python crash → fail-open → silent. *I injected an Esiste≠Armato
   into my own receptor*, and the **end-to-end probe** (the JSON-emitting run, not `bash -n`) caught
   it. Recorded here because it is the doctrine proving itself: the probe must test the WORK.

---

## §8 — Solo-operatore (the boundary — needs Zero / physical / strategic)

- **The 9 dead/unhealthy organs** (`cell.observatory` stale 27d, `pro.federation_alert_dispatcher`
  stale 20d **status=ok** ← the green that lies, +7 unhealthy). **Restart is NOT the cure** — the
  heartbeat *writer/bridge* is dead; investigate the writer, not the process. Operator-side infra.
- **Wire the escalations receptor** into `~/.claude/settings.json` SessionStart (one line). Built +
  tested; arming it changes every future session → your call (or say "arma" and I do it + verify).
- **DeepSeek V4 Pro out of balance** — the Tier-2 refuter is down. Top up, or accept Codex as the
  standing refuter (cascade already works).
- **Ollama arsenal drift** vs CLAUDE.md: `deepseek-r1:32b`, `gemma4:26b`, `qwen3:8b`,
  `nomic-embed-text` absent; `glm-ocr`, `qwen3-vl:8b` new. Update CLAUDE.md §arsenal or re-pull.
- **pre-commit lease-check is CI-only**, not in local `.git/hooks/pre-commit` — a local agent can
  commit a leased hot-zone file without the guard firing. Decide: wire local, or accept CI-only.
- **MEMORY.md at 19.2KB / 25.6KB wall** — healthy now, ~75% full; `/mem-trim` is manual. Watch.

---

## §9 — The one-screen card (operational distillation)

```
PREFLIGHT (BOOT+GROUND+FRAME)
  □ Read the receptors: heartbeat + escalations + repomap + last-5 memory (don't skim — act on HIGH)
  □ stadio-zero: hot-files VERIFIED on disk THIS turn · PII scope · falsifiable acceptance
  □ FRAME: council only if (divergent-priors ∧ error>15×tokens ∧ parallel-breadth) else solo+budget
  □ A file:line you didn't re-grep this turn is a PHANTOM. Re-grep before you build.

INFLIGHT (DISPATCH + VERIFY-continuous)
  □ Worktree per agent (agent_start.py). Fan-out reads, funnel-in writes.
  □ Right model: regulation→Gemini · import/migration→Codex · grounding→NB · PII→Ollama-local
  □ VERIFY each increment NOW (not at close): probe the WORK by content, adversarial fixture,
    grader ≠ producer (epistemically). Risk-proportional: content-addressed→existence-check ok;
    high-blast→full E2E. Out-of-session liveness→durable receptor, not a fake this-turn check.
  □ BOUNDARY always: no secret cleartext, no PII to any output/memory/log. BUDGET: stop-loss on depth.
  □ RECONCILE: new operator input → restate first, re-derive acceptance, drop stale plan.

CLOSE (PERSIST + CLOSE)
  □ "Should this persist at all?" gate before commit/mem/scar (PII + truth + worth).
  □ Atomic commit (conv msg + co-author). Capture scar/lesson if a new failure mode appeared.
  □ build ≠ armed: anything created-but-not-merged/installed/armed = SUSPENDED, say so.
  □ result: / needs input: / failed: — one self-contained line. Green ≠ working: read the OUTPUT.
```

> **The whole doctrine in one line:** *existence is a lead, never a verdict; prove the work — by
> content, by an independent grader, in proportion to the blast — and make what you cannot prove
> this turn into a receptor the next session cannot miss.*
