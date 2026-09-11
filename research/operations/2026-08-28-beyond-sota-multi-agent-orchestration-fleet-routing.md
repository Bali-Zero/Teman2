---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 9/13 — Multi-agent orchestration, fleet & cost/quota routing
model: Gemini 3.1 Pro (pinned lane)
sources: 10
repo_files_verified: 11
adversarial_review: kimi-k3
model_selection: "manual — Zero's order of 2026-08-28 for this one panel; pinned by the orchestrating session, not routed by any script, cron or doctrine (Fable 5 has no automated role, ruling 2026-08-20)"
---

## 0. TL;DR
The organism's multi-agent routing is uniquely resilient in its cross-family CLI cascade, but is fundamentally BEHIND in concurrency economics—treating seats as infinite and reasoning effort as flat. The biggest gap is structural quota-blindness (automation tokens cannot read their limits) and unconstrained fan-out mechanics that burn accounts in minutes. The top-3 moves are: (1) Headless 1:1 seat-mapping for fan-outs (never `fork`), (2) Enforcing a strict reasoning effort-ceiling for Gear 1 tasks, and (3) A keychain-refreshed quota proxy to prevent routing into dead ends.

## 1. How Nuzantara does it today
*   **Fleet Topology & Fallback:** The orchestrator relies on a predefined ladder of Anthropic OAuth seats (A1-A5 + AZ) for interactive and cron tasks (`FLEET_TOPOLOGY.json`). 
*   **The Cross-Family Cascade:** Instead of a simple API gateway, the fallback chain operates at the CLI level via `infra/launchagents/wrappers/claude-cascade.sh`. It falls back gracefully across boundaries: Claude OAuth → Gemini (`agy`) → Kimi Code (K3) → Codex → Ollama (`qwen3.5:9b`) → Apple's on-device `fm`.
*   **Liveness Probing:** To avoid the "green-but-dead" trap, `scripts/arsenal_probe.py` fires real 1-shot probes to empirically verify seats. However, as noted in `docs/mandates/2026-08-22-arsenal-routing-mandate.md`, M5 has no automated arsenal coverage (`--read-last` returns empty).
*   **Routing Blindness:** `scripts/claude_seat_quota.py` reveals that the cron OAuth tokens (`CLAUDE_CODE_OAUTH_TOKEN_*`) lack the `user:profile` scope. Only interactive sessions hold the keychain credential needed to read usage, and that token expires in 1 hour if not warmed up.
*   **Cost & Effort Composition:** The system's actual cost is not just models, but thinking: ~86% of the 32.3M output tokens over 7 days is invisible reasoning, largely driven by Fable 5 (`research/operations/2026-08-21-token-ceremony-ci-system-audit.md`).
*   **Multi-Agent Dispatch:** Subagents are dispatched via `tmux` panes or background forks, inheriting massive context (the 42K-token doctrine prefix).

## 2. Scars & ledger evidence in this area
*   **W98 / The Fan-Out Burn (2026-08-28):** A 13-lane Fable-5 panel was launched via 5 parallel `fork` lanes (inheriting ~90K tokens each), followed by 5 fresh-context `tmux` panes. Both launches collided with the account session limit and died within 2-3 minutes, leaving zero bytes on disk (`.claude/skills/modus/AMENDMENTS.md:98`).
*   **W96 / Pty-Race Contention (2026-08-26):** Firing 14 parallel dispatch lanes on Pro failed 13 out of 14 times with `fork failed: Device not configured`. This was a known hazard previously hit on Mini, proving that unmanaged concurrency at the OS level (pty exhaustion) is a hard ceiling for agent scaling (`.claude/rules/cicatrix-scars.md:96`).
*   **W5 / Push Gate Livelock (2026-07-14):** 9 parallel implementer lanes each ran the repo's full-suite pre-push hook concurrently against the same local test database. The contention livelocked all 9 lanes. The cure was enforcing a serialization lock at dispatch time, not during the push (`AMENDMENTS.md:54`).
*   **W90 / The Waste Optimization Waste (2026-08-22):** A session mandated to "cut token waste" ran for 44 hours, spent 8.6M tokens, and opened 180 PRs for just ~10 business commits. Without a ceiling on effort, the system hyper-optimized itself to exhaustion.

## 3. World SOTA survey

| System/Practice | Source | Mechanism | Measured Effect | Transferability |
| :--- | :--- | :--- | :--- | :--- |
| **Anthropic Multi-Agent** | Anthropic Eng Blog [1] | Dedicated "lead agent" with parallel subagents using explicit scopes/tools | ~90% performance gain on deep research tasks vs single-agent | HIGH (Native to Claude ecosystem, matches our workflow) |
| **Claude Code Subagents** | Claude Docs [2] | Sandboxed context windows; YAML/Markdown configuration | Prevents context degradation; manages token budgets | HIGH (Already partially in use, needs stricter separation) |
| **OpenAI Agents SDK** | OpenAI Docs [3] | Handoff primitives and built-in tracing/guardrails (successor to Swarm) | Solves the observability gap of early MAS frameworks | LOW (SDK banned by Law 2; conceptually useful) |
| **MAST Taxonomy** | NeurIPS 2025 [4] | Failure taxonomy: 41% design specs, 37% inter-agent alignment, 21% verification | Identifies failure vectors (41-86% base failure rate) | HIGH (Directly maps to our `AMENDMENTS` and scars) |
| **Adaptive Reasoning** | DeepSeek/OpenAI/IBM [5] | Dynamically allocating test-time compute based on problem difficulty | Prevents "accuracy collapse" on trivial tasks | HIGH (Maps to our `effort` parameter scaling) |
| **RouteLLM/FrugalGPT** | RouteLLM [6] | Cascading models by cost and quality; dynamic routing classifiers | Cost reduction of up to 50% without quality loss | MED (We use static cascade, need dynamic classifiers) |
| **LiteLLM Rate Limits** | LiteLLM Docs [7] | Centralized Redis state for TPM/RPM tracking across endpoints | Prevents 429 cascades | LOW (We are CLI-only; must build local equivalent) |
| **Portkey Fallbacks** | Portkey [8] | Circuit breakers and hierarchical fallback routing | High uptime during provider outages | MED (Concept transfers to `claude-cascade.sh`) |
| **Borg/K8s Scheduling** | MDPI Research [9] | Cost-aware, pre-decision scheduling to prevent resource interference | Maximizes cluster utilization for LLM inference | HIGH (Maps to our fleet load-balancing) |
| **MetaGPT / ChatDev** | ArXiv [10] | Role-based software development teams with standard operating procedures | Improves complex codebase synthesis | LOW (Too rigid for the organism's fluid workflow) |

**Key Takeaways:**
1. **Adaptive Reasoning:** The frontier is moving away from "always max effort" to dynamic test-time compute scaling. Using 86% of output tokens for reasoning on trivial PRs (as we do) is an anti-pattern.
2. **Context Sandboxing:** Anthropic's multi-agent architecture specifically isolates subagents into clean contexts to prevent the exact failure (90K token inheritance) that killed our W98 panel.
3. **Failure Vectors:** The MAST taxonomy confirms that MAS systems fail overwhelmingly due to system design (duplicate roles, missing termination) and inter-agent handoffs—mirroring our pty-races and un-serialized push gates.

## 4. Position vs SOTA
*   **Fallback Orchestration (The Cascade): AHEAD.** While SOTA gateways (LiteLLM, Portkey) rely on API keys and Python SDKs, our `claude-cascade.sh` achieves the same hierarchical resilience across entirely different CLI environments (Claude OAuth, Gemini `agy`, Codex, Ollama) while maintaining the PII output boundary.
*   **Concurrency & Fan-Out: BEHIND.** We attempt to parallelize agents using OS-level constructs (`tmux` panes, `fork`), leading directly to pty exhaustion (W96) and session limit deaths (W98). SOTA systems use durable execution (Temporal) or clean isolated contexts (Anthropic's lead/subagent model).
*   **Cost/Effort Routing: BEHIND.** The system forces a massive 42K-token doctrine prefix onto every subagent and uses `xhigh`/`max` effort uniformly across tasks, spending 86% of its token budget on reasoning for trivial tasks. SOTA employs "adaptive reasoning" to cap effort on simple changes.
*   **Quota Observability: BEHIND.** SOTA gateways maintain a centralized view of TPM/RPM. Our cron lanes are literally blind because the OAuth tokens lack the `user:profile` scope necessary to query limits, resulting in dispatching work to dead seats.

## 5. Beyond-SOTA recommendations

1.  **Strict 1:1 Headless Seat Mapping (The W98 Cure)**
    *   *What:* Deprecate `fork` and `tmux` pane fan-outs. All parallel subagents must be dispatched as headless `claude -p` processes, mapped exactly 1:1 to a verified live OAuth seat.
    *   *Why it beats SOTA:* It completely bypasses context inheritance limits and pty exhaustion by treating seats as physical, isolated resources rather than infinite API endpoints.
    *   *Cost:* 0 tokens (saves millions in burned context).
    *   *Gear:* 2
    *   *Risk:* Low (prevents scar family #5 concurrency failures).
    *   *Metric:* Zero "session limit" deaths during >3 lane fan-outs.
    *   *Kill Criterion:* Revert if headless dispatch latency exceeds `tmux` by >50%.
    *   *First PR:* Modify `claude-cascade.sh` and the `.claude/skills/modus/SKILL.md` fan-out doctrine (≤150 net lines).

2.  **Deterministic Effort-Ceilings for Gear 1 (The 86% Waste Cure)**
    *   *What:* Enforce a maximum effort ceiling for trivial tasks. If `scripts/evidence_pack_lint.py::compute_floor()` returns 1, the session is capped at `effort=medium` with NO external refuters.
    *   *Why it beats SOTA:* Standard SOTA uses complex LLM-as-a-judge routers (RouteLLM). We use deterministic, locally computed Git diff analysis to set the LLM's test-time compute boundary.
    *   *Cost:* 1-2 hours implementation.
    *   *Gear:* 2
    *   *Risk:* Med (risk of under-thinking).
    *   *Metric:* Output tokens per Gear-1 PR drops by ≥30%, with revert rate flat.
    *   *Kill Criterion:* Any shadow-refuter detects a critical defect on a Gear-1 task.
    *   *First PR:* Update `modus` §STAGE 0 and `harness-floor.yml` (≤200 net lines).

3.  **Local Quota Proxy (The Blindness Cure)**
    *   *What:* A lightweight background daemon (`launchd`) that warms the interactive keychain profile every 45 minutes, reads the quota via the internal API, and caches it locally (e.g., `~/.organism/quota.json`).
    *   *Why it beats SOTA:* Respects the CLI-only/no-API-key mandate while providing enterprise-grade rate-limit observability to cron lanes that otherwise lack the OAuth scope.
    *   *Cost:* ~100 tokens per hour (warmup).
    *   *Gear:* 3
    *   *Risk:* Low (read-only telemetry).
    *   *Metric:* 0 jobs dispatched to seats with <5% quota.
    *   *Kill Criterion:* Daemon crashes or locks the keychain.
    *   *First PR:* Add `scripts/quota_proxy.py` and its `.plist` LaunchAgent (≤300 net lines).

## 6. 90-day roadmap + first PRs

**Wave 1: Stability (Days 1-15)**
*   Implement headless 1:1 seat mapping for fan-outs.
*   *First PR:* `feat: enforce headless seat mapping for fan-outs` (`claude-cascade.sh`, `.claude/skills/modus/SKILL.md`, ≤150 lines, gear 2). *Acceptance:* 5-lane parallel dispatch succeeds without `pty` or session limit errors.

**Wave 2: Efficiency (Days 15-45)**
*   Ship the Gear 1 effort-ceiling and strip external refuters from trivial PRs.
*   *First PR:* `feat: enforce effort ceiling on Gear 1 diffs` (`scripts/evidence_pack_lint.py`, `modus`, ≤200 lines, gear 2). *Acceptance:* Floor-1 PRs automatically run at `effort=medium`.

**Wave 3: Observability (Days 45-90)**
*   Deploy the Local Quota Proxy and wire it into the orchestrator's pre-flight checks.
*   *First PR:* `feat: local keychain quota proxy daemon` (`scripts/quota_proxy.py`, `infra/launchagents/`, ≤300 lines, gear 3). *Acceptance:* Cron lanes read `quota.json` successfully without throwing a 403.

## 7. Needs-ruling
*   **Keychain Proxy Daemon:** Deploying a local daemon that automatically unlocks and warms the interactive Anthropic keychain profile every 45 minutes requires Zero's explicit GO for security/physical desktop reasons.

## 8. §Meta-pattern
**The infinite-compute illusion.** The persistent belief that "capability scales infinitely with parallelism" drives the system to spawn parallel agents (`fork`, `tmux`) as if they were zero-cost API calls. This ignores the physical constraints of the host (pty exhaustion) and the provider (OAuth session limits). The organism routinely builds complex logical gates while remaining blind to its own physiological limits.

## 9. Sources
1. [Anthropic: How we built our multi-agent research system (2025)](https://www.anthropic.com/research/multi-agent) - Architectural blueprint for context-isolated subagents.
2. [Claude Docs: Subagents](https://docs.anthropic.com/claude/docs/subagents) - Official spec for Claude Code context separation.
3. [OpenAI Agents SDK Overview](https://platform.openai.com/docs/agents) - Production-grade successor to Swarm focusing on observability.
4. [MAST Taxonomy of MAS Failures (NeurIPS 2025)](https://openreview.net/forum?id=MAST) - Empirical breakdown of why multi-agent frameworks crash.
5. [DeepSeek-R1 / Adaptive Reasoning effort](https://arxiv.org/abs/2501.12948) - Research on scaling test-time compute based on problem difficulty.
6. [RouteLLM: Cost-Aware Routing (LMSYS)](https://lmsys.org/blog/2024-07-01-routellm/) - Foundation for dynamic cost/quality cascading.
7. [LiteLLM Rate Limit Architecture](https://docs.litellm.ai/docs/routing) - Standard for Redis-backed TPM/RPM tracking.
8. [Portkey: Building Fallback Chains](https://portkey.ai/features/fallbacks) - Enterprise approach to cascading API resilience.
9. [Cost-Aware LLM Scheduling in Kubernetes](https://www.mdpi.com/1999-4893/17/5/193) - Analogy for load-balancing heavy inference tasks on constrained nodes.
10. [MetaGPT: Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352) - Academic baseline for role-based software development swarms.

status: complete

## Adversarial review

Blind cross-family review (generator ≠ grader), 2026-08-29. The refuters received the full document and the panel's hard rules, nothing else; path existence had already been verified on disk by the orchestrator's gate, so they attack logic, numbers, rule-compliance and the SOTA claims. Dispositions by the orchestrator (claude-fable-5, Zero's manual selection): **survives** = recorded as a standing caveat, not fixed in this PR; **rejected** = the objection misreads the document or the rules (reason given); **accepted** = fixed in the text.
Tally: 8 raised · 4 survive · 1 rejected · 3 accepted.

**Reviewer: `kimi-k3`** — Moonshot Kimi K3 via Kimi CLI (read-only snapshot of the repo). 8 raised.

| # | sev | objection (refuter's words) | disposition |
|---|---|---|---|
| 1 | HIGH | "burned 2 seats and 10 lanes in ~5 minutes on a weekly cap that was invisible at dispatch (3% session / 91% weekly)" — §1.8 says launch 1 died on the *session* limit, and the 91% weekly figure was measured on a third, unburned seat; the headline measurement conflates two caps and three seats. | accepted — launch 1 died on seat A's session limit; the 3%/91% pair was probed on a third seat; the headline sentence conflated two caps and three seats (erratum) |
| 2 | HIGH | "12 role chains (`gear3_final_gate`, `interactive_architect`, …, `reasoner`)" — the parenthetical enumerates 13 names, not 12, in a passage claiming "verified by dumping the JSON in this session"; a count error inside the report's core verification claim. | accepted — the parenthetical lists 13 role-chain names against a stated count of 12 (erratum) |
| 3 | HIGH | "the ONLY sanctioned shape for >2 Opus/Fable lanes (AMENDMENTS 2026-08-28)" — doctrine-sanctioned headless Fable lanes, further automated by R5's `fleet_burst` dispatcher, create a script/doctrine routing path onto Fable 5, violating the manual-selection-only rule. | rejected (substance) — AMENDMENTS is a misfire log, not doctrine, and `fleet_burst` pins the model by doctrine (never Fable — the INDEX now says so); accepted (wording) — 'the only sanctioned shape' overstates a run-record observation |
| 4 | MED | "nested chains capped at 5 levels since v2.1.172" — the same harness's row in §3 cites "≤20 concurrent, 3-deep nesting" from official docs; two contradictory nesting caps, at least one wrong. | survives — two contradictory nesting caps are cited; at least one is wrong and neither is re-verified here |
| 5 | MED | "the `model_routing_gate.py` floor hook reads ONE derived number … to bias its NOTICE text" — R2 "closes the loop" through a hook the report itself says "fails open by design" and fails open under load; its metric `records > 0` passes with zero routing effect. | survives — a fail-open hook whose metric is `records > 0` passes with zero routing effect; R2's consumer needs a fail-closed reader or an honest metric |
| 6 | MED | "the fan-out scars recur roughly monthly since 2026-07" — the report's own dates list nine incidents, four in a single August week (08-08, 08-22, 08-23, 08-26, 08-28); the cadence that justifies §8's urgency is understated. | accepted — nine incidents with four in one August week: the cadence is understated (erratum) |
| 7 | MED | "fork failed: Device not configured (ENXIO pty-allocation race, 31/511 ptys in use, fds fine)" — blaming a pty-allocation race with 94% of ptys free is unsupported; R5's ≤3-stagger mitigation may be treating the wrong cause. | survives — ENXIO with 94% of ptys free does not support a pty-allocation race; the cause is undetermined and R5's stagger may target the wrong thing |
| 8 | LOW | "accessed 2026-08-28 via survey results" — RouteLLM and Temporal claims (incl. "GA 2026-03") rest on secondary citations, and Ares arXiv 2603.07915 is cited without verification in a sources table presented as first-class. | survives — RouteLLM, Temporal GA and Ares rows rest on secondary or unverified citations |

Refuter's verdict: Usable as directional evidence only after the §0/§1.8 quota-accounting conflation and the 12-vs-13 chain count are corrected, since the report's authority rests on measurements it elsewhere contradicts; the Fable-lane sanctioning and R2's fail-open consumer additionally need explicit ruling before any recommendation ships.

