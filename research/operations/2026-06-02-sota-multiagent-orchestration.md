---
date: 2026-06-02
domain: operations
client_case: nuzantara-internal
status: draft
session: S16 sota-multiagent-2026
companion_to:
  - research/operations/2026-05-24-sota-multi-agent-repo-architecture-synthesis.md
  - research/operations/2026-05-28-sota-multi-agent-repo-arch-update.md
frozen: research/operations/2026-06-02-sota-multiagent-FROZEN.json
sources:
  - https://arxiv.org/abs/2503.13657
  - https://arxiv.org/abs/2512.08296
  - https://arxiv.org/abs/2604.02460
  - https://arxiv.org/abs/2505.18286
  - https://arxiv.org/abs/2511.07784
  - https://arxiv.org/abs/2603.04474
  - https://arxiv.org/abs/2410.11782
  - https://arxiv.org/abs/2402.16823
  - https://arxiv.org/abs/2505.13516
  - https://arxiv.org/abs/2311.05772
  - https://arxiv.org/abs/2510.01285
  - https://arxiv.org/abs/2307.03172
  - https://www.anthropic.com/engineering/multi-agent-research-system
  - https://cognition.ai/blog/dont-build-multi-agents
  - https://a2a-protocol.org/latest/specification/
  - https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year
method:
  - Claude Code Workflow fan-out (4 angles) + adversarial source-merit verify (34 claims, 27 SUPPORTED / 7 PARTIAL / 0 KILLED)
  - 6 load-bearing claims independently primary-verified by orchestrator (anti-hallucination)
  - 38 agents spawned, 288 tool uses
---

# SOTA Multi-Agent ORCHESTRATION — June 2026 (S16)

> **Scope discipline.** The `2026-05-24` synthesis + `2026-05-28` companion already cover **repo architecture** — worktree isolation, lease registry, merge-queue, repomap. They are done and shipped (L1–L4). This document is the **orthogonal axis the prompt asked for**: orchestration **topology**, **coordination primitives**, **failure modes**, **agent-count scaling** — i.e. what is new *beyond* our broker + worktree + orchestrator-worker. It does not repeat the repo-arch docs.

## TL;DR

The frontier in mid-2026 is **not** "find a cleverer topology". It is three things, in priority order:

1. **Decide WHETHER to fan out at all.** The strongest new primary evidence says multi-agent *degrades* sequential / coding-style work and only helps *breadth-first parallelizable* work. Our `federation_orchestrator` always parallel-dispatches — that is the single highest-value gap.
2. **Verify at every seam, not only at the end.** ~37% of multi-agent failures (MAST) are semantic verification/termination problems that worktree brokers, leases and merge-queues structurally cannot see. Our `REVIEW` node fires once, at the end.
3. **Generate/learn topology per-task** (G-Designer / GPTSwarm / HALO). High impact but research-grade and largest at agent counts we deliberately do *not* run. **Defer to a spike.**

Counter-current that constrains all of the above: at our scale (2–7 local sessions) with improving base models, a **single strong orchestrator under an equal token budget matches or beats** a multi-agent fan-out (Tran & Kiela; Gao; Google scaling 3–4-agent ceiling). Multi-agent's documented win is **breadth-first research** (Anthropic +90.2%, ~15× tokens), explicitly **not coding** (Anthropic *and* Cognition).

**Net for Nuzantara: do NOT grow the fleet. Add a "when-not-to-fan-out" gate + seam verification + MAST review rubric. Keep asymmetric-adversarial review (now measured-justified). Reject A2A/Kafka/debate-layer for our scale.**

---

## 1. The evidence that reframes our roadmap (all primary, verified)

| Finding | Number | Source | What it does to our design |
|---|---|---|---|
| **MAST failure taxonomy** | 14 modes / 3 cats; **FC1 41.77% / FC2 36.94% / FC3 21.30%**; κ=0.88, 1642 traces, 7 frameworks | arXiv 2503.13657 | ~37% of failures are verification+termination — **invisible to L1–L4**. Gives the REVIEW rubric. |
| **MAST intervention ceiling** | **+15.6%** (verification) / +9.4% (role-spec), authors call it "limited and insufficient" | arXiv 2503.13657 | Bounds ROI of *more orchestration cleverness* at ~+10–16%. Spend on verification, not a 5th lane. |
| **Anthropic multi-agent system** | **~15× tokens** vs chat; **+90.2%** research eval; tokens explain **80%** of variance; **coding = poor fit** | anthropic.com/engineering/multi-agent-research-system | Multi-agent is for **breadth-first research**, not code. Our research fan-out (this session) is the right regime. |
| **Cognition "Don't Build Multi-Agents"** | qualitative | cognition.ai/blog/dont-build-multi-agents | Parallel coders make conflicting *implicit* decisions → never fan out parallel coders on the same artifact. |
| **Google "Science of Scaling"** | hard **3–4 agent ceiling**; turn-count power-law exp **1.724**; sequential tasks **−70%**; best-arch predicted **87%** held-out | arXiv 2512.08296 | Quantitative stopping rule: our **2–7 bound is near-optimal; do not raise it**. Motivates the decomposability gate. |
| **Single-agent ≥ multi under equal budget** | SAS ≥ MAS across Qwen3 / DeepSeek-R1-Distill / Gemini 2.5 | arXiv 2604.02460 | The single orchestrator (given the split tokens) is the **baseline a fan-out must beat**, not a strawman. |
| **MAS benefit diminishes** | cascade **+1.1–12%** acc / **−20%** cost; token overhead **4–220×** input | arXiv 2505.18286 | Difficulty-cascade: default single, escalate to fan-out only on hard tasks. |
| **Debate is dominated by the strongest** | **+32–52pt** hard puzzles BUT self-correct **3.6%** (weak) vs 30–34% (strong) vs wrong majority | arXiv 2511.07784 | **Do NOT add a debate/consensus layer.** Keep asymmetric-adversarial review (one critic). |
| **Error cascade from one seed** | single seed → false consensus; governance prevents infection **89%** | arXiv 2603.04474 | Validate **between** hops; one bad upstream output poisons the chain. |
| **Lost-in-the-middle** | U-shaped; mid-context degradation (replicated, TACL 2024) | arXiv 2307.03172 | Re-surface goal/constraints at the **end** of every hop's prompt. |
| **Learned per-task topology** | G-Designer **−92.24%** tokens / 0.3% adversarial drop; GPTSwarm HumanEval **+12pp**, GAIA **+90%** rel; HALO MATH **+22pp** | 2410.11782 / 2402.16823 / 2505.13516 | The real frontier — but research-grade, large-N. **Defer to spike.** |
| **A2A protocol** | v1.0.0, Linux Foundation, **150+ orgs**, 22k+ stars | a2a-protocol.org | Cross-**organizational** interop — over-engineered for 2–7 local sessions (Law 6). **Reject.** |

> **Verification honesty:** the adversarial pass corrected fabrications rather than rubber-stamping. The fan-out's first-pass MAST split (43.8/32.2/23.5) was **fabricated**; corrected to the paper's real 41.77/36.94/21.30 (independently re-verified by the orchestrator). Google scaling's R² was inflated 0.513→0.373; a "−39%" lower bound was fabricated (real endpoint −70.0%); the SWE-bench "single-agent *drives* SOTA" claim was softened to "single-agent scaffolds are *prominent and competitive*" (arXiv 2506.17208 finds architecture diverse once base model held constant). **0 claims survived without a real source.**

---

## 2. Adoption spec — concrete changes to OUR system

Targets are real files: `scripts/federation_orchestrator.py`, `scripts/agent_start.py`, the Claude Code `Workflow` patterns, and the `sota-architecture-loop` skill. Impact/Effort on 1–5.

### ADOPT (7)

| # | Action | Target | I/E | Evidence |
|---|---|---|---|---|
| **A1** | **Pre-dispatch decomposability gate** — `CLASSIFY` emits `parallelizable: bool`; `route_after_checkpoint` returns single-orchestrator (direct Claude) for sequential/low-complexity tasks, fan-out only for breadth-first work. | `federation_orchestrator.py` CLASSIFY + `route_after_checkpoint` | 5/2 | Google 2512.08296 (−70% sequential), Gao 2505.18286, Tran-Kiela 2604.02460 |
| **A2** | **Equal-token-budget baseline** — never compare a fan-out against an under-budgeted single agent; log token spend per route; single-orchestrator is the default to *beat*. | `sota-architecture-loop` decision-gate + federation audit log | 4/1 | Tran-Kiela 2604.02460, Anthropic 15× |
| **A3** | **Verify at the seam** — lightweight sanity gate before `ASSEMBLE` merges each lane's output (cheap local qwen or scoped redteam), not only the end-of-chain REVIEW. | `federation_orchestrator.py` ASSEMBLE + per-dispatch | 5/3 | MAST 2503.13657 (+15.6%), error-cascade 2603.04474 (89%) |
| **A4** | **MAST rubric for REVIEW** — turn `review_node` (and `devils-advocate`/`wr3-critic`) prompts into a 14-point checklist keyed to MAST modes (Step repetition, Reasoning-action mismatch, Fail-to-ask-clarification, Premature termination…). | `review_node` prompt + critic prompts | 3/1 | MAST 2503.13657 |
| **A6** | **Re-surface task state at end of each hop** — put goal+constraints+prior-decisions at the *end* of every dispatch prompt; adopt LangGraph `Command` state-carrying handoff (we are already LangGraph). | dispatch prompts + Workflow `agent()` convention | 4/2 | Lost-in-the-middle 2307.03172, LangGraph Command, OpenAI handoff() |
| **A7** | **Stop symlinking `.venv`/`node_modules` into worktrees** — `SYMLINK_TARGETS` (agent_start.py:87-91) symlinks the venv + node_modules into every worktree; Cursor docs warn this corrupts the *main* worktree. Reinstall per-worktree via `uv`/`pnpm`, keep only the read-only `.env` symlink. | `scripts/agent_start.py` `_create_symlinks` | 3/2 | Cursor 3.5 docs (2026-05-28 companion checklist, now confirmed live) |
| **A9** | **Optimistic concurrency for shared scratchpad** (narrow) — if/when a shared scratchpad is added, use version-vector CAS on Postgres `events_outbox`, *not* a new Redis lease. Keep L2 lease for hot-zones only. | shared-artifact writes (not L2 hot-zone) | 2/2 | OCC at low contention |

### KEEP — vindicated (1)

| # | Action | Evidence |
|---|---|---|
| **A5** | **Keep asymmetric-adversarial review; do NOT add a debate/consensus layer.** Our `sota-architecture-loop` already says "review as asymmetric-adversarial (never consensus)". arXiv 2511.07784 is the *measured* justification: debate is dominated by the strongest agent and weak agents conform to wrong majorities (3.6% vs 34.4% self-correction). | debate 2511.07784 |

### DEFER — spike only (1)

| # | Action | Why defer |
|---|---|---|
| **A8** | **Learned/generated per-task topology** (G-Designer VGAE / GPTSwarm RL-edges / HALO 3-tier / ADaPT failure-recursion). −92% tokens, +12pp HumanEval, +22pp MATH are real and large — but require RL training / graph models, and the benefit peaks at agent counts Google's 3–4 ceiling tells us *not* to run. **A1 captures ~80% of the win** (don't-fan-out-when-sequential) at effort 2 vs 5. Re-evaluate only if the fleet ever grows past 2–7. | research-grade; large-N; Law 6 (must run 100% local) |

### REJECT — with reason (2)

| # | Action | Why reject |
|---|---|---|
| **R1** | **A2A protocol + MCP-as-peer-coordination.** A2A is built for cross-*organizational*, heterogeneous, multi-vendor agent interop — over-engineered for 2–7 local same-codebase Claude sessions under Law 6. MCP sampling/elicitation is client-side (routed through host), not symmetric P2P; using it for agent coordination creates hidden host routing (MAST FC1). Our CLI-subprocess + Postgres EventBus *is* the right local layer. Revisit only if Bali Zero federates with external agent vendors. | Law 6 sovereignty; scale mismatch |
| **R2** | **Kafka event-backbone + full blackboard infra.** Confluent's own framing: infra cost pays off only *above* small agent counts. We already have Postgres LISTEN/NOTIFY + `events_outbox`. **Borrow the blackboard *idea*** (lanes self-declare capability so `CLASSIFY` need not enumerate them — folds into A1) without the Kafka infra. | no new infra (Law 6); EventBus already shipped |

---

## 3. How this maps onto what we already run

- `federation_orchestrator.py` dispatches **specialist** lanes (gemini-search vs gemini-explore vs codex-sandbox vs claude-redteam) — *different roles*, not parallel coders on the same file. That is exactly the regime where multi-agent wins (breadth, distinct tools) and avoids Cognition's failure mode (conflicting implicit decisions on a shared artifact). **The architecture is sound; the gaps are A1 (always-fan-out) and A3 (end-only verify).**
- This very session's research used the `Workflow` fan-out for **research** (breadth-first, parallelizable) — the Anthropic +90.2% regime. We must *not* reuse that pattern to fan out parallel coders on one artifact.
- Our 2–7 concurrent session bound is **quantitatively near-optimal** (Google 3–4 reasoning ceiling). The repo-arch docs worried about *collision* between sessions; the orchestration evidence says the *count* itself is already right.

---

## 4. Disagreements / open questions (left honest)

- **A8 vs A1 priority.** Learned topology (A8) is the academic frontier and has the biggest single numbers (−92% tokens). But it is heavy and large-N. A1 (decide-whether-to-fan-out) gets most of the practical win cheaply. Resolved *for our scale* in favor of A1; A8 stays a spike. A larger fleet would flip this.
- **SWE-bench structural claim** softened to PARTIAL: arXiv 2506.17208 finds top scaffolds are architecturally *diverse* once the base model is held constant — single-agent scaffolds are prominent/competitive, but not the *sole* driver. Do not over-claim "single-agent owns coding SOTA".
- **A3 cost.** Per-seam verification adds latency/tokens; bounded by MAST's +15.6% ceiling. Implement cheaply (local qwen sanity pass) and measure before scaling to the full redteam at each hop.

---

## 5. Suggested order of execution

1. **A2 + A5** (effort 1, zero infra) — discipline + documenting a vindicated choice. Immediate.
2. **A4** (effort 1) — MAST rubric prompt edit.
3. **A1** (effort 2) — the highest-impact code change; one classifier field + one routing branch.
4. **A6 + A7** (effort 2 each) — state-resurfacing handoff; fix the symlink corruption risk.
5. **A3** (effort 3) — seam verification, measured.
6. **A9** (narrow) — only when a shared scratchpad exists.
7. **A8** — spike when/if fleet grows (Google scaling says: it shouldn't).

> Every ADOPT item fits the constraints: CLI-only LLM (no Anthropic API), local sovereignty (Law 6), and is benchmark-grounded (Law 7). No new external infra. No new paid API.
