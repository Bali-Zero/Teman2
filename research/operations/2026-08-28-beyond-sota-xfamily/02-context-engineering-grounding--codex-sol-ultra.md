---
panel: beyond-sota-xfamily
lane: 02-context-engineering-grounding
seat: codex-sol-ultra
model: "gpt-5.6-sol · reasoning_effort=ultra · Codex CLI read-only sandbox · web search on"
started: 2026-08-28T18:24:36Z
finished: 2026-08-28T18:33:34Z
duration_s: 538
exit: 0
words: 4869
prompt_sha256_16: 280e491a78643d9c
prompt_chars: 18776
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 2/13 — Context engineering & grounding
model: OpenAI GPT-5.6 sol at reasoning effort ULTRA (pinned lane)
sources: 12
repo_files_verified: 20
status: complete
---

## 0. TL;DR

Nuzantara is ahead of SOTA in turning measured failures into always-available grounding doctrine, but behind SOTA in measuring whether the right, fresh context actually reaches each agent.
Its verified static boot floor is already 58,509 bytes before global doctrine, memory, repomap, rules, tool schemas, or hook output; the panel’s inherited forks began with approximately 90K tokens, 45% of a 200K window.
The largest gap is not missing knowledge. It is the absence of a per-session, provenance-bearing context bill of materials with freshness, priority, token cost, and evidence of delivery.
Top move 1: compile a ≤20K-token Context Kernel and emit a signed context manifest at every session start.
Top move 2: build ScarReplay ContextEval, using historical failures to measure which context prevents errors and which merely consumes attention.
Top move 3: replace unqualified “ground truth” with bitemporal evidence receipts and independently sourced verification.
Preserve Nuzantara’s scars, local sovereignty, hooks, and corners; progressively disclose their bodies instead of injecting them wholesale.
Non-forked fresh-context lanes should be the default. A 90K-token inherited fork is an explicit exception requiring a measured benefit.

## 1. How Nuzantara does it today

### 1.1 Scope and evidentiary boundary

This review verified 20 repository files in the authorized snapshot. The requested home-scoped runtime files—`/Users/nuzantara/.claude/settings.json`, `/Users/nuzantara/.claude/CLAUDE.md`, `/Users/nuzantara/.claude/scripts/mem`, `/Users/nuzantara/.claude/hooks/*`, `/Users/nuzantara/.nuzantara-repomap.txt`, and every `$MEM/...` path—were outside the snapshot and were not read. Therefore:

- Claims below distinguish checked-in design from live runtime state.
- The stated 1,707 memory bodies, their prefix distribution, current `MEMORY.md` size, pointer/content ratio, and `MEMORY_ARCHIVE.md` size are not measurable from this lane.
- The final-only lane override prohibited creating the report file, so no `ls -la` or `wc -w` file-existence claim is made.

This distinction matters: the repository’s own dominant superscar says that “documented,” “present,” and “armed” are separate states.

### 1.2 The boot path

The checked-in `.claude/settings.json:9-25` registers three project `SessionStart` receptors:

1. `scripts/hooks/escalations_alert_sessionstart.sh`
2. `scripts/hooks/proprioception_sessionstart.sh`
3. `scripts/hooks/organism_digest_sessionstart.sh`

No checked-in `PreCompact`, `PostCompact`, memory-capture, repomap, or symbiosis-core registration appears in that settings file. Those may exist in the unavailable home configuration, but their live registration is unverified here.

The three project receptors are better than conventional “welcome” hooks:

- `scripts/hooks/escalations_alert_sessionstart.sh` calculates unresolved high-priority items and recent task-graveyard signals under a four-second, fail-open budget. It emits `hookSpecificOutput.additionalContext` only when actionable findings exist. That selectivity saves context, but healthy silence is observationally identical to a dead hook.
- `scripts/hooks/proprioception_sessionstart.sh:72-78` follows a stronger never-silent contract. Missing, stale, or erroneous sources become visible, and its output explicitly says that snapshot findings are claims the session must rederive before action.
- `scripts/hooks/organism_digest_sessionstart.sh` summarizes recent organism change under a six-second budget and reports empty/error states instead of implying health. Its source also triggers an asynchronous arsenal refresh when the source report is stale (`scripts/hooks/organism_digest_sessionstart.sh:14-20`); that is checked-in behavior, not evidence that the refresh succeeds live.

This is an unusually mature distinction between context and evidence: the proprioception hook does not present its own snapshot as truth.

### 1.3 Verified boot-budget floor

| Component | Verified size | Loading status | Interpretation |
|---|---:|---|---|
| `CLAUDE.md` | 44,523 bytes, 300 lines | Project-root doctrine | Loaded in full by Claude Code’s documented hierarchy |
| `.claude/rules/cicatrix-superscar.md` | 13,986 bytes, 252 lines | Repository says every session/subagent | Only 14 bytes below its 14,000-byte test ceiling |
| Verified static minimum | **58,509 bytes** | Lower bound only | Excludes global doctrine, memory, repomap, other rules, tools, skill descriptions, and hook output |
| `.claude/skills/visaoracle/SKILL.md` | 136,238 bytes | Triggered domain body | If consumed wholesale, it is 2.33× the verified static minimum |
| `.claude/skills/modus/PENDING-ARMS.md` | 2,202,762 bytes, 1,080 ledger rows | Retrieval-only by design | Must never become boot context |
| `.claude/skills/modus/AMENDMENTS.md` | 51,623 bytes | Retrieval-only | Useful misfire evidence, unsuitable for unconditional loading |

A rough 3–4 bytes/token conversion puts the 58,509-byte static minimum at approximately 14.6K–19.5K tokens, or 7.3%–9.8% of a 200K window. That is an estimate, not a tokenizer measurement. The true boot total is unknown because the runtime-only components were unavailable.

The panel launch supplied a second measurement: inherited fork lanes began with approximately 90K tokens, already 45% of a 200K window. This is consistent with Claude Code’s official distinction between fresh isolated subagents and forks that inherit the parent conversation. It is not an argument against parallel agents; it is an argument that inheritance must be deliberate and measured.

### 1.4 Doctrine, scars, and progressive disclosure

`CLAUDE.md:94-101` describes automatic memory injection plus `mem query` over FTS5. `CLAUDE.md:168-172` states the core anti-hallucination rule: never cite tool output not executed in the current turn. `SYMBIOSIS.md:11-23` requires an agent to locate its organ, producers, consumers, prior reflections, skills, and scars before changing anything.

The strongest context artifact is `.claude/rules/cicatrix-superscar.md`. It compresses roughly 99 individual scars into ten failure families and explicitly calls itself a bridge, not an encyclopedia. `scripts/tests/test_superscar_budget.py` mechanically pins both its 14,000-byte ceiling and referential completeness: every included W-number must resolve to a scar body. That is beyond ordinary prompt documentation because the summary’s pointers are tested against their evidence corpus.

Skills implement partial progressive disclosure. `.claude/skills/skill-catalog/SKILL.md` searches a domain catalog and loads full skills on demand; it explicitly tries to avoid placing every installed skill body into startup context. Sixteen top-level entries were present under `.claude/skills/`, with nine under `.agents/skills/`. The weakness appears after routing: `.claude/skills/visaoracle/SKILL.md` is a 136,238-byte live-state corner. Its header correctly says to prefer live state over obsolete embedded state, but its size makes “skill selected” too close to “entire domain loaded.”

### 1.5 Repomap

`scripts/build_repomap.sh` implements the right high-level design: Aider/tree-sitter first, universal-ctags fallback, atomic replacement, filtering of generated artifacts, and a nominal 4–20KB target. `docs/runbooks/repomap-and-branch-cleanup.md` describes a 15-minute refresh and injection only while fresh.

The implementation has budget ambiguity:

- The preferred path uses `REPOMAP_MAX_TOKENS=1024`.
- The fallback can emit approximately 35–40KB and only warns above 30KB.
- The declared target remains 4–20KB.

Thus the repomap is structurally at SOTA, but target, warning, and fallback ceiling are not one enforceable contract. The live home repomap’s size and freshness were unavailable.

### 1.6 Memory and handoff

`.claude/hooks/memory_budget_gate.py` treats `MEMORY.md` as a concise, always-loaded index and exempts topic bodies. Its actual ceiling is 24,985 UTF-8 bytes. `scripts/tests/test_memory_budget_gate.py` pins that value and verifies exact-path scoping. This conflicts with the lane brief’s asserted 17KB target and indicates contract drift, not necessarily a runtime violation.

`infra/army/chore-queue/memory-budget-gate-hardening.md` records a concrete remaining defect: sequential dependent replacements in one multi-edit can each be checked against the original text, underestimating the final index size. The gate is real, but one mutation shape can evade its prediction.

`.claude/commands/resume.md` defines a disciplined re-entry record: one session ID, objective, changed files, verified commands, risks, and next action. It forbids fabricating a missing handoff or merging multiple handoffs. It does not, however, bind the handoff to a repository revision, context-manifest hash, or evidence receipts. It transfers assertions, not independently checkable state.

### 1.7 NotebookLM grounding

`docs/NOTEBOOKLM_STRATEGY.md` defines NotebookLM as a specialist grounding surface, separates internal-code and external-domain notebooks, and avoids mixing corpora whose volume would drown the intended authority. This resembles a bipolar verifier: one agent synthesizes while a specialist corpus grounds claims.

The strategy document is architectural evidence, not a live health receipt. The snapshot contained no `.mcp.json`, and the ledger documents credential and registration failures. NotebookLM therefore cannot safely be described as continuously available “ground truth.” It is a potentially authoritative corpus whose availability, freshness, and claim provenance must be proven per use.

## 2. Scars & ledger evidence in this area

| Evidence | What actually happened | Context-engineering lesson |
|---|---|---|
| Superscar family #6; W65, W74, W78, W90, W100, W113 | Paths, snapshots, agreement, and corrections were treated as truth without current independent verification | Context must carry a revalidation method, not merely a citation |
| Superscar family #1 | HOME and repository copies diverged | Namespace and source precedence must be explicit in every context packet |
| Superscar family #2 | Artifacts existed but were not armed or consumed | Delivery proof is as important as artifact quality |
| W90, `.claude/rules/cicatrix-scars.md:507` | A “ground-truth” verifier served a stale NotebookLM snapshot | Authority without valid-time metadata is dangerous |
| W100, `.claude/rules/cicatrix-scars.md:760` | Same-family agreement certified seven false-clean results out of eight | Agreement measures shared transcription or bias, not truth |
| W113, `.claude/rules/cicatrix-scars.md:934-940` | A correction introduced a new claim that nobody independently reviewed | Corrections need the same provenance gate as initial claims |
| W82, `.claude/rules/cicatrix-scars.md:214` | A freshness sentinel matched a string rather than the underlying fact | Lexical presence is not semantic freshness |
| W84, `.claude/rules/cicatrix-scars.md:182` | A reproduction was guessed incorrectly three times before using the verbatim transcript | Raw evidence must precede explanation |
| W74 | A local checkout made specifications appear absent although they existed on `origin/main` | Repository revision belongs in every contextual claim |
| W106b | A checkout was used as a proxy for truth; failed fetches blurred “drift” and “cannot verify” | Unknown must remain a first-class state |

The ledgers show recurrence outside the prose doctrine:

- `.claude/skills/modus/PENDING-ARMS.md:1016` records a 13-day NotebookLM silence caused by credential expiry. Interactive login was the only repair, while consumers lacked a proactive validity signal.
- `.claude/skills/modus/PENDING-ARMS.md:1250` records the NotebookLM MCP absent on Mini, leaving machine routing or registration unresolved.
- `.claude/skills/modus/PENDING-ARMS.md:360` records a healer pass that explicitly reverified live signals instead of trusting a spawn snapshot.
- `.claude/skills/modus/PENDING-ARMS.md:554` records a retry mechanism that existed, but a stale CLI made the whole path ineffective.
- `.claude/skills/modus/AMENDMENTS.md:32` says healthy-silent escalation output is indistinguishable from a dead receptor.
- `.claude/skills/modus/AMENDMENTS.md:34` says context budgeting must count descendant agents, not only direct children.
- `.claude/skills/modus/AMENDMENTS.md:52` records a full cure lane dispatched for an issue merged six hours earlier even though memory pointed to it.
- `.claude/skills/modus/AMENDMENTS.md:73` records global and repository doctrine disagreeing for 23 days with no matching memory entry.
- `.claude/skills/modus/AMENDMENTS.md:90` records two “token waste” sessions lasting 44 and 31 hours, producing 8.6M output tokens and roughly ten business commits while 190 overdue arms were injected at every boot.
- `.claude/skills/modus/AMENDMENTS.md:92` records a refuter reading a torn live worktree and fabricating a critical finding.

The corpus establishes severity, but this lane cannot honestly provide a complete recurrence denominator: the archive and home memory bodies were outside the authorized snapshot. The defensible quantitative evidence is approximately 99 scars across ten families, 1,080 PENDING-ARMS rows, one 13-day grounding outage, a seven-of-eight false-clean incident, and the 75-hour/8.6M-token pair of low-yield sessions.

## 3. World SOTA survey

| System/practice | Primary source | Mechanism | Published effect | Transferability |
|---|---|---|---|---|
| Anthropic context engineering | [Anthropic, 2025](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | Smallest high-signal context; hybrid upfront/JIT retrieval; compaction; structured notes; isolated subagents | Reports subagents reducing tens of thousands of exploratory tokens to 1–2K-token summaries; no universal controlled gain | Directly transferable through flat-subscription CLIs |
| Claude Code memory | [Claude Code docs](https://code.claude.com/docs/en/memory) | Hierarchical CLAUDE files, path-scoped rules, pointer index plus topic files | Hard startup ceiling: first 200 memory lines or 25KB; recommends CLAUDE files below 200 lines | Establishes a concrete comparison for Nuzantara’s 300-line project doctrine |
| Cursor rules | [Cursor docs](https://docs.cursor.com/context/rules-for-ai) | Repository-versioned, scoped, auto-attached or manually selected rules | No controlled accuracy result published | Supports moving component-specific doctrine out of unconditional boot |
| Aider repository map | [Aider docs](https://aider.chat/docs/repomap.html) | Tree-sitter tags, dependency graph ranking, token-budgeted repository summary | No single controlled effect on the current page | Nuzantara already uses this architecture; it needs stricter budget telemetry |
| Sourcegraph Search Contexts | [Sourcegraph docs](https://sourcegraph.com/docs/code-search/working/search-contexts) | Named collections of repositories and revisions constrain retrieval | No public task-accuracy result | Revision-scoped retrieval is the missing complement to the repomap |
| MemGPT/Letta | [Packer et al., 2023](https://arxiv.org/abs/2310.08560) | OS-like virtual memory, explicit movement between working and archival tiers | Evaluated on long-document analysis and multi-session conversation | Validates keeping memory bodies outside the prompt and paging them in |
| LongMemEval | [Wu et al., 2024](https://arxiv.org/abs/2410.10813) | 500-question benchmark over information extraction, multi-session reasoning, temporal reasoning, knowledge update, and abstention | Reports roughly 30% degradation in long-term interactive memory settings | Provides the missing model for a Nuzantara memory regression suite |
| Mem0 | [Chhikara et al., 2025](https://arxiv.org/abs/2504.19413) | Dynamic extraction, consolidation, and targeted retrieval instead of replaying full history | Reports 26% relative LLM-judge gain, 91% lower p95 latency, and over 90% token savings against full-context approaches | Strong evidence for compiled boot plus JIT memory retrieval |
| A-MEM | [Xu et al., 2025](https://arxiv.org/abs/2502.12110) | Zettelkasten-style notes whose semantic links and attributes evolve with new evidence | Improves long-memory benchmarks across six foundation models | Useful for memory bodies, but links must remain evidence-bearing and local |
| Zep/Graphiti | [Rasmussen, 2025](https://blog.getzep.com/content/files/2025/01/ZEP__USING_KNOWLEDGE_GRAPHS_TO_POWER_LLM_AGENT_MEMORY_2025011700.pdf) | Incremental, bitemporal knowledge graph with semantic, lexical, and graph retrieval | Reports stronger deep-memory retrieval than MemGPT and competitive long-memory performance | Valid-time and transaction-time semantics directly address W90 |
| Lost in the Middle | [Liu et al., 2023/2024](https://arxiv.org/abs/2307.03172) | Controlled retrieval and multi-document QA with relevant evidence moved across positions | Finds U-shaped performance: beginning/end evidence is used more reliably than middle evidence | Explains why a large context window cannot substitute for selection and layout |
| OpenAI prompt caching | [OpenAI, 2024](https://openai.com/index/api-prompt-caching/) | Stable shared prefix followed by dynamic content; explicit cached-token accounting | Published 50% cached-input discount and lower latency for supported models at launch | Paid API use is prohibited here; stable-prefix layout and cache telemetry still transfer conceptually |

The most important convergence is not a specific memory database. Anthropic, MemGPT, Mem0, and A-MEM all separate a small working set from a much larger retrievable universe. Nuzantara already has the necessary raw materials—an index, topic bodies, repomap, skills, scars—but does not yet compile them into an auditable working set.

LongMemEval supplies the missing evaluative discipline. A memory system should be tested for extraction, temporal reasoning, updates, multi-session synthesis, and abstention. “The index stayed under its byte cap” is a safety property, not evidence that memory improves work.

Graphiti’s bitemporal model is particularly relevant. A claim needs both when the underlying fact was valid and when the organism learned it. Nuzantara’s W90/W106b class cannot be solved by attaching only a file timestamp.

Finally, Lost in the Middle invalidates the implicit assumption that unused capacity is free. Even correct context can reduce performance when placed in an attention-poor region. The optimization target is marginal task utility per token, not maximum occupancy.

## 4. Position vs SOTA

| Sub-dimension | Position | Evidence and judgment |
|---|---|---|
| Dynamic startup receptors | **AHEAD** | Proprioception’s never-silent, “rederive before action” contract is stronger than generic memory injection (`scripts/hooks/proprioception_sessionstart.sh:72-78`) |
| End-to-end boot observability | **BEHIND** | No checked-in manifest proves which global/project/rule/memory/skill blocks loaded, their hashes, ages, or token costs |
| Doctrine scoping | **BEHIND** | `CLAUDE.md` is 300 lines versus Claude Code’s sub-200-line guidance; global/project divergence already persisted 23 days |
| Scar compression | **AHEAD** | Approximately 99 failures are compressed into ten families with a mechanical 14KB and referential-completeness test |
| Scar budget headroom | **BEHIND** | The superscar has only 14 bytes of budget headroom, making any addition a zero-sum emergency |
| Repository mapping | **AT** | Tree-sitter/Aider plus ctags fallback is SOTA architecture; actual fallback size policy and live freshness remain unproven |
| Memory tiering | **AT** | Pointer index, topic bodies, and FTS5 retrieval match frontier practice |
| Memory correctness evaluation | **BEHIND** | No LongMemEval-like suite; requested index measurements were unavailable; sequential multi-edit undercount remains recorded |
| Skill discovery | **AT** | `skill-catalog` performs on-demand routing rather than unconditional body loading |
| Triggered corner size | **BEHIND** | The 136,238-byte Visa Oracle skill risks replacing startup bloat with trigger-time bloat |
| NotebookLM corpus separation | **AHEAD** | Internal-code and external-domain notebooks are deliberately separated to prevent source-volume dominance |
| NotebookLM availability/freshness | **BEHIND** | Recorded 13-day credential silence, missing Mini MCP, stale snapshot scar, and no per-claim health receipt |
| Anti-hallucination doctrine | **AHEAD** | Same-turn tool verification and explicit unknown states are stronger than ordinary agent instructions |
| Mechanical anti-hallucination enforcement | **BEHIND** | Most claims remain prose-governed; W100 and W113 show that agreement and correction can still bypass independent proof |
| Compaction handoff schema | **AT** | `resume` preserves objective, changes, verification, risks, and next action without merging unrelated sessions |
| Handoff integrity | **BEHIND** | No immutable revision, source digests, validity intervals, or context-manifest binding |
| Context economics | **BEHIND** | Claims such as “approximately 50 tool calls saved” are not backed by a repeatable task benchmark; inherited lanes consumed ~90K tokens before work |

Overall position: **AT SOTA architecturally, AHEAD culturally, BEHIND empirically**.

## 5. Beyond-SOTA recommendations

Ranking uses `(impact × confidence) / cost`, with each factor scored 1–5.

### 1. Compile a provenance-bearing Context Kernel — score 12.5

- **What:** Before turn one, compile a task-specific kernel from doctrine, superscars, memory pointers, repomap, active receptors, and selected corner capsules. Emit a manifest containing source path, source revision/hash, generated time, valid time, byte/token cost, sensitivity class, priority, reason selected, and delivery status.
- **Why it beats SOTA:** Existing systems offer scoped rules, JIT retrieval, maps, or virtual memory. None surveyed combines those with a tested scar taxonomy, live receptor health, immutable repository provenance, and a per-session context BOM.
- **Asymmetry:** Nuzantara already owns the scar corpus, hooks, local always-on machines, repomap builder, and cross-family CLI fleet.
- **Before → after:** Unknown total boot cost and a 58,509-byte static floor → tokenizer-measured turn-one context ≤20K tokens, dynamic stale bytes = 0, unproven delivery = 0.
- **Cost:** Three engineering days plus approximately 50 flat-subscription CLI evaluation runs; no paid API.
- **Gear:** 3.
- **Risk/scar family:** #1 if machine copies compile differently; #2 if the manifest exists but is not injected.
- **Metric:** Kernel tokens, source count, stale-source count, manifest coverage, first-pass task success, time to first grounded action.
- **Kill criterion:** Stop automatic compilation if success falls more than two percentage points or median discovery tool calls rise by more than 10% over 50 paired tasks.
- **First PR:** Add `scripts/context_boot_manifest.py` and `scripts/tests/test_context_boot_manifest.py`; ≤380 net lines; manifest only, no hook rollout.

### 2. Build ScarReplay ContextEval — score 10.0

- **What:** Convert redacted W-cases into a benchmark with context ablations: full boot, compiled kernel, no scars, stale memory, wrong revision, same-family verifier, and fresh independent verifier.
- **Why it beats SOTA:** LongMemEval evaluates generic long-term memory. This benchmark would evaluate operational context against Nuzantara’s actual failure distribution across multiple LLM families.
- **Asymmetry:** Approximately 99 categorized failures and six subscription-backed/cross-family execution seats provide data and compute without per-token API billing.
- **Before → after:** No measured causal value for injected context → ≥95% citation/provenance precision, ≥30% turn-one token reduction, zero increase above two percentage points in task failure, and ≥25% fewer obsolete cure lanes.
- **Cost:** Four days and 180–240 CLI runs; all cases must be PII-free.
- **Gear:** 3.
- **Risk/scar family:** #6 if reconstructed cases differ from the original evidence.
- **Metric:** Success, abstention quality, phantom citations, stale actions, tokens, tool calls, elapsed time, and cross-family variance.
- **Kill criterion:** Retire any context block whose removal produces no statistically or operationally meaningful degradation across two model families; suspend the suite if fixtures cannot be tied to redacted primary evidence.
- **First PR:** Add a 12-case schema and deterministic citation checker under `research/operations/context-eval/` plus `scripts/context_eval_validate.py`; ≤400 net lines.

### 3. Introduce bitemporal Evidence Receipts — score 8.3

- **What:** Every dynamic memory, repomap, NotebookLM, handoff, or health claim becomes a receipt with `source_id`, `source_revision`, `observed_at`, `valid_from`, `valid_to`, `confidence`, `cannot_verify_reason`, and a safe revalidation command.
- **Why it beats SOTA:** Graphiti supplies bitemporal memory; Nuzantara adds executable revalidation, immutable code revision, PII class, and a rule that corrections generate new receipts rather than overwriting history.
- **Asymmetry:** Hooks and local state can verify evidence without exposing operational data to cloud outputs.
- **Before → after:** W90/W106b-style unqualified current claims → 100% receipt coverage for injected dynamic blocks, expired claims never rendered as current, stale-action rate ≤1%.
- **Cost:** Three days plus integration by source.
- **Gear:** 3.
- **Risk/scar family:** #6 if a receipt launders a weak source into apparent authority.
- **Metric:** Receipt coverage, expired-use count, successful revalidation rate, and unknown-state preservation.
- **Kill criterion:** Reject the abstraction if it adds more than 5% boot latency or if agents treat receipt presence as truth despite failed validity checks.
- **First PR:** Add `scripts/context_evidence_receipt.py` and tests for valid, expired, revision-mismatched, and cannot-verify states; ≤350 net lines.

### 4. Make compaction handoffs immutable and reconstructable — score 8.0

- **What:** Extend Mnemos/resume handoffs with repository SHA, worktree identity, manifest hash, evidence-receipt IDs, command-output digests, unresolved assertions, and mandatory revalidation instructions.
- **Why it beats SOTA:** Frontier compaction preserves summaries; this design separates remembered assertions from independently reproducible evidence and detects torn-worktree review.
- **Asymmetry:** Full-lifecycle session ownership and content-addressed repository artifacts make exact continuation possible.
- **Before → after:** Narrative handoff with unverifiable “tests passed” claims → resumed objective reconstructed in ≤2 minutes, 100% revision binding, and zero automatic action from a stale checkpoint.
- **Cost:** Two days and 20 controlled compaction/resume trials.
- **Gear:** 2.
- **Risk/scar family:** #1 for wrong-worktree bindings; #6 for output digests presented without the command definition.
- **Metric:** Reconstruction time, revalidation success, stale checkpoint rejection, and post-resume duplicated work.
- **Kill criterion:** Revert mandatory receipt loading if median resume latency exceeds five minutes without reducing duplicate or stale work by at least 50%.
- **First PR:** Update `.claude/commands/resume.md`; add `scripts/context_handoff_verify.py` and tests; ≤300 net lines.

### 5. Upgrade the bipolar verifier to source-independent quorum — score 6.7

- **What:** NotebookLM may propose or corroborate a claim, but high-stakes claims pass only when the verifier uses a distinct evidence lineage, produces a health receipt, and has not inherited the generator’s retrieved passage.
- **Why it beats SOTA:** Multi-agent systems usually seek agreement. This design seeks provenance independence and actively penalizes shared-source agreement.
- **Asymmetry:** The organism has cross-family seats, specialized notebooks, local retrieval, and scars proving the seven-of-eight false-clean mode.
- **Before → after:** Seven false-clean outcomes in eight same-family checks and a 13-day silent outage → 0/50 false-clean on the scar suite; 100% preflight detection of unavailable or stale grounding services.
- **Cost:** Four days plus flat-subscription verifier runs.
- **Gear:** 3.
- **Risk/scar family:** #2 if the quorum policy exists but consumers bypass it; #6 if “independent” sources share an upstream snapshot.
- **Metric:** Evidence-lineage overlap, false-clean rate, abstention rate, auth-health detection, and claim latency.
- **Kill criterion:** Narrow the gate if it adds over 30% latency to low-risk work; never relax it for regulatory, financial, security, or client-impacting claims.
- **First PR:** Add a PII-free `scripts/notebooklm_grounding_gate.py` contract and fixture-based tests; ≤400 net lines.

## 6. 90-day roadmap + first PRs

### Wave 1 — Days 0–30: make context measurable

| First PR | Files | Size/gear | Acceptance test |
|---|---|---:|---|
| `feat(context): emit deterministic boot manifests` | New `scripts/context_boot_manifest.py`, `scripts/tests/test_context_boot_manifest.py` | ≤380 lines, G3 | Six fixture blocks produce stable hashes, exact byte totals, freshness states, and fail on an unknown source |
| `fix(memory): close sequential multi-edit budget bypass` | `.claude/hooks/memory_budget_gate.py`, `scripts/tests/test_memory_budget_gate.py` | ≤180 lines, G2 | Two individually safe dependent replacements whose combined result exceeds the limit are rejected |
| `fix(repomap): enforce one fallback budget` | `scripts/build_repomap.sh`, new focused test | ≤220 lines, G2 | Preferred and ctags outputs both stay under the same configured ceiling |
| `test(context): seed ScarReplay` | New `research/operations/context-eval/`, `scripts/context_eval_validate.py` | ≤400 lines, G3 | Twelve redacted cases validate provenance, expected abstention, and revision binding |

Wave exit: one measured baseline across at least two model families; current `MEMORY.md`, archive, prefix counts, pointer ratio, live repomap, global/project doctrine, tool schemas, and receptor outputs audited from the authorized runtime. No production behavior changes before that baseline.

### Wave 2 — Days 31–60: progressively disclose and prove freshness

| First PR | Files | Size/gear | Acceptance test |
|---|---|---:|---|
| `feat(context): add evidence receipt v1` | New `scripts/context_evidence_receipt.py`, tests | ≤350 lines, G3 | Valid, stale, expired, wrong-revision, and cannot-verify fixtures remain distinguishable |
| `refactor(visaoracle): compile a boot capsule` | `.claude/skills/visaoracle/SKILL.md`, new capsule/index file | ≤400 lines, G3 | Initial selected context ≤12KB; 30 golden domain-gate prompts omit no mandatory safety gate |
| `feat(notebooklm): fail visibly on unhealthy grounding` | New `scripts/notebooklm_grounding_gate.py`, tests | ≤400 lines, G3 | Expired auth, absent MCP, stale corpus, and shared evidence lineage all prevent a “grounded” verdict |

Wave exit: ≥90% reduction from the 136,238-byte corner body to its initial capsule, ≥95% retrieval recall on golden tasks, and 100% dynamic blocks carrying receipts.

### Wave 3 — Days 61–90: close the learning/evaluation loop

| First PR | Files | Size/gear | Acceptance test |
|---|---|---:|---|
| `feat(resume): verify immutable handoff checkpoints` | `.claude/commands/resume.md`, new `scripts/context_handoff_verify.py`, tests | ≤300 lines, G2 | Wrong SHA and torn-worktree checkpoints are rejected; valid continuation reconstructs in ≤2 minutes |
| `feat(context): select kernel by measured marginal utility` | Context manifest/compiler files only | ≤400 lines, G3 | Removing any retained block causes a measured regression or it is demoted to JIT retrieval |
| `test(context): run cross-family context ablations` | ScarReplay runner and result schema | ≤400 lines, G3 | At least 50 tasks × three context variants × two families; no PII and no paid API path |

Ninety-day acceptance: turn-one context ≤20K measured tokens for ordinary coding sessions; ≥30% reduction versus baseline; ≤2-point task-success regression; zero expired claims rendered current; false-clean ≤2%; and no inherited fork above 25% of its window without a manifest-recorded justification.

## 7. Needs-ruling

1. **`needs-ruling` — authority policy:** Zero must decide whether NotebookLM may ever be the sole authority for high-stakes regulatory/client-impacting claims. Recommendation: no; it should be a lead or corroborator until its source corpus, validity interval, and independent evidence lineage are proven per claim.
2. **Operator credential/GUI action:** The open NotebookLM credential-expiry and missing-Mini-MCP conditions require interactive authentication or deliberate routing. Automation should detect and abstain, but must not fabricate, extract, or persist credentials.
3. **Runtime audit consent:** This lane could not inspect home-scoped context, memory, or hook configuration. A follow-up runtime audit needs explicit access to structure and size only, with secrets and memory bodies redacted. It should measure, not copy, any protected corpus.

## 8. §Meta-pattern

The single defective belief is:

> If useful knowledge exists and is injected, the agent is grounded.

Every major failure is a variant of that belief. A memory entry existed but referred to work already merged. A hook was silent and therefore assumed healthy. A NotebookLM snapshot was called ground truth after it became stale. Same-family agreement amplified the same source error. A correction became a new unreviewed claim. A large corner preserved more knowledge while consuming the attention needed to use it. A fork inherited 90K tokens and called that continuity.

The replacement belief is:

> Context is a versioned evidence supply chain. Every injected token needs an owner, provenance, validity interval, delivery proof, marginal utility, and revalidation path.

That reframes context engineering from accumulating instructions to compiling an executable working set. Nuzantara already owns the components that make this composition uniquely powerful: scars provide empirical selection pressure; hooks provide delivery points; repomap and MOS provide indexes; local machines provide sovereign retrieval; the fleet provides cross-family evaluation; full-lifecycle sessions provide outcome labels. What is missing is the compiler and the benchmark.

## 9. Sources

1. [Anthropic — “Effective context engineering for AI agents”](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), 2025-09-29; accessed 2026-08-29. Primary engineering guidance on JIT retrieval, compaction, note-taking, and isolated subagents.
2. [Claude Code — “How Claude remembers your project”](https://code.claude.com/docs/en/memory), continuously updated; accessed 2026-08-29. Authoritative loading, scoping, 200-line, and 25KB memory behavior.
3. [Cursor — Rules documentation](https://docs.cursor.com/context/rules-for-ai), continuously updated; accessed 2026-08-29. Primary documentation for repository-versioned and scoped agent rules.
4. [Aider — Repository map](https://aider.chat/docs/repomap.html), continuously updated; accessed 2026-08-29. Primary implementation description of tree-sitter, graph-ranked, token-budgeted code maps.
5. [Sourcegraph — Search Contexts](https://sourcegraph.com/docs/code-search/working/search-contexts), continuously updated; accessed 2026-08-29. Primary documentation for named repository-and-revision retrieval scopes.
6. [Packer et al. — “MemGPT: Towards LLMs as Operating Systems”](https://arxiv.org/abs/2310.08560), 2023-10-12; accessed 2026-08-29. Primary paper on virtual-context and memory-tier management.
7. [Wu et al. — “LongMemEval”](https://arxiv.org/abs/2410.10813), 2024-10-14; accessed 2026-08-29. Primary benchmark for long-term interactive memory capabilities and failures.
8. [Chhikara et al. — “Mem0”](https://arxiv.org/abs/2504.19413), 2025-04-28; accessed 2026-08-29. Primary paper reporting quality, latency, and token effects of selective memory.
9. [Xu et al. — “A-MEM: Agentic Memory for LLM Agents”](https://arxiv.org/abs/2502.12110), 2025-02-17; accessed 2026-08-29. Primary research on evolving, linked memory notes.
10. [Rasmussen — “Zep: A Temporal Knowledge Graph Architecture for Agent Memory”](https://blog.getzep.com/content/files/2025/01/ZEP__USING_KNOWLEDGE_GRAPHS_TO_POWER_LLM_AGENT_MEMORY_2025011700.pdf), 2025-01; accessed 2026-08-29. Primary description and evaluation of bitemporal Graphiti memory.
11. [Liu et al. — “Lost in the Middle”](https://arxiv.org/abs/2307.03172), 2023-07-06, TACL 2024; accessed 2026-08-29. Primary evidence that long-context utilization depends strongly on evidence position.
12. [OpenAI — “Prompt Caching in the API”](https://openai.com/index/api-prompt-caching/), 2024-10-01; accessed 2026-08-29. Primary source for stable-prefix caching mechanics and published launch economics.