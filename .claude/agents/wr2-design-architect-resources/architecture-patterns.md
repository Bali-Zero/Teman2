# Vendor Architecture Patterns — Anthropic + OpenAI + Google (2025-2026)

> Synthesis from Agent #3 multi-vendor research, 2026-05-08. What each vendor ships for "build a design agent that grows", and what to actually adopt.

---

## 1. Anthropic — Claude Code subagents + Agent Skills + Memory

**Subagent primitive** (`~/.claude/agents/<name>.md`):

- Markdown file with YAML frontmatter: `name`, `description` (when to invoke), `tools` (whitelist), `model` (haiku/sonnet/opus, default = parent's model).
- Body = system prompt for the subagent.
- Subagents launched via Agent tool from main loop. Each subagent has its own context window — protects parent context from blowing up on long research/explore loops.
- Loaded automatically at session start; no setup beyond writing the file.
- **Cost**: zero on top of OAuth MAX subscription. Critical given the §HARD RULE no paid API.

**Agent Skills** (`~/.claude/skills/<skill-name>/SKILL.md` + supporting files):

- Progressive disclosure: only the YAML frontmatter (`name`, `description`) is loaded at session start; full skill body loaded on demand when agent invokes it.
- Skill folder can include reference data (markdown, JSON, examples), shell scripts, code snippets — all available to the agent when skill activates.
- Same OAuth MAX cost basis as subagents.

**Memory tool** (Sept 2025, Managed Agents Apr 2026):

- Anthropic Memory API exposes per-agent memory store (semantic + episodic) at API layer.
- For Claude Code (CLI, OAuth), the file-based equivalent is `~/.claude/projects/<project-id>/memory/` — already in use here.
- "Dreams" (background memory consolidation) is a research preview — relevant for the reflective layer of the design agent but not yet a stable API.

**Why Anthropic stack is the right base for Bali Zero**:

- Cost = zero on top of existing 3 MAX plans (CLAUDE.md HARD RULE compliance).
- Subagent + Skill primitives cover the multi-agent architecture pattern from research §9 (orchestrator + 4 specialist sub-agents).
- File-based, version-controllable, no vendor lock-in — skills and memory are markdown that survive Anthropic deprecating any specific tool.

---

## 2. OpenAI — Custom GPTs + Assistants API + Agents SDK + AgentKit

**Custom GPTs** (consumer-facing, ChatGPT Plus included):

- No-code, browser config: instructions + uploaded knowledge files + actions (HTTP).
- Good for non-developer use cases. Bali Zero already uses this for Zantara persona on chatgpt.com.
- Brand-design use case: less suited because Custom GPTs cannot run code locally, cannot be embedded in CLI pipeline, cannot read local repo files.

**Assistants API** (deprecated end of 2026, replaced by Responses API + Agents SDK):

- Was the original "stateful agent with tools" primitive. Being phased out.

**Agents SDK** (Q4 2025):

- Python/TS framework for building multi-agent systems. Ships with handoff primitives, tracing, eval harness.
- Worth reading for _architectural ideas_ but binding to OpenAI = paid API per token = violates HARD RULE.

**AgentKit** (early 2026):

- Visual builder + deployment runtime for agent workflows. Same paid-token concern.

**Why OpenAI stack is NOT the base for Bali Zero**:

- All paths route to paid OpenAI tokens. Existing ChatGPT Plus covers Codex CLI usage but not API-based agent runtime.
- Architectural ideas worth borrowing: handoff pattern, tracing, eval harness — all implementable on Anthropic stack.

---

## 3. Google — Gemini Gems + Vertex AI Agent Builder + ADK

**Gemini Gems** (consumer, Gemini Advanced):

- Equivalent of Custom GPTs. No-code, browser config. Same limitations.

**Vertex AI Agent Builder + ADK (Agent Development Kit)** (2025):

- Enterprise framework: agents-as-services on Vertex, with grounding, eval, deployment.
- OAuth Gemini CLI is free for ad-hoc inference (Gemini 3.1 Pro), but Agent Builder runtime is billed per Vertex usage.

**Why Google stack is NOT the base for Bali Zero**:

- Agent Builder is paid per token + paid for hosting. Free-tier Gemini CLI is fine for cross-LLM brainstorming but cannot host the agent runtime.
- Architectural ideas worth borrowing: ADK's tool calling pattern (typed schemas), Vertex grounding via knowledge stores (we have NotebookLM for the same purpose).

---

## 4. Recommended architecture for Bali Zero — composite pattern

**Primary substrate**: Anthropic Claude Code (subagents + skills + file-based memory) on OAuth MAX.

**Multi-agent shape** (4 specialist subagents, all Claude):

- `wr2-design-architect` (orchestrator) — Opus 4.7 — main entry point
- `wr2-brief-interpreter` — Sonnet 4.6 — fast, RAG-over-NB, structured JSON out
- `wr2-storyboarder` — Sonnet 4.6 — narrative arc 8–10 slides
- `wr2-layout-composer` — Sonnet 4.6 — picks parametric skill from library, emits HTML
- `wr2-critic` — Opus 4.7 (vision-capable) — scores against brand rubric
- `wr2-publisher` — Haiku 4.5 — Canva apply + Tigris upload (cheap, mechanical)

**Skill library** (`~/.claude/skills/bali-zero-brand/`):

- `constitution.md` — hard brand rules (palette, type, taboo)
- `tokens.json` — design tokens (machine-readable)
- `voice/` — few-shot examples on-tone vs off-tone
- `layouts/` — parametric layout skills (each = SKILL.md + render snippet)
- `past/` — last N carousels as in-context reference (PNG + brief.md)

**Memory layers**:

- _Episodic_: SQLite at `~/.claude/projects/-Users-nuzantara/memory/wr2-episodic.db` — one row per carousel run.
- _Semantic_: brand cortex files (above).
- _Procedural_: skill library (above).
- _Reflective_: weekly cron synthesizes episodes into lessons appended to voice/ and skills/.

**Cross-LLM verification (bipolar verifier already in CLAUDE.md)**:

- Critic panel: Claude main + Gemini cross-check (free) + NotebookLM ground-truth (NB-DESIGN-AGENT just created).
- DeepSeek as alternate cross-check when Gemini quota exhausted.
- Never include OpenAI in runtime path (would burn Codex Plus quota that's reserved for code review).

**Tools whitelist for orchestrator** (`tools` field in YAML):

- `Read`, `Write`, `Edit`, `Bash`, `Glob`, `Grep` — basic file I/O
- `mcp__nuzantara-fetch__*` — web research for brief
- `mcp__notebooklm-mcp__*` — RAG over Bali Zero NBs (NB-1, NB-5, NB-4, NB-DESIGN-AGENT)
- `mcp__claude_ai_Canva__*` — design publication
- `Agent` (subagent_type whitelist: critic, layout-composer)
- NOT: arbitrary network, no `mcp__playwright__*` (renderer is invoked via Bash from skill)

---

## 5. Growth & feedback loop (Voyager + Reflexion adaptation)

**Voyager-style curriculum** (weekly cron):

- Inspect last 30 carousels in episodic store.
- Identify underrepresented topic-types (e.g., "we did 4 visa carousels but 0 tax this month").
- Generate 1 exploratory variant alongside next production carousel for that underrepresented topic.

**Reflexion-style post-mortem** (per-carousel):

- After Damar publishes manually, designer-override diff is captured (final published version vs agent draft).
- Critic re-scores published version, generates verbal lesson.
- Lessons batched weekly into:
  - new few-shot examples in `voice/` (if voice-related)
  - new candidate skills in `layouts/` (if layout-related)
  - hard rule additions in `constitution.md` (if recurring violation)

**Skill library evolution**:

- Each new skill enters as `_proposed/<name>.md`.
- After 3 successful uses (critic score ≥ threshold) it graduates to `layouts/<name>.md`.
- Skills unused for 60 days move to `_archived/`.

**Hard guardrail**: skill changes are git-committed. Antonello reviews diffs weekly. No autonomous skill modification merges to main without human commit.

---

## 6. Concrete next 7 steps

> **Historical bootstrap record (2026-05-08)** — these 7 steps describe how the system was
> FIRST built, using the HOME paths that were the only copy that existed at the time. Steps
> 1-7 below are done; do not re-run them. As of 2026-07-16, `wr2-design-architect.md` is
> vendored into repo `.claude/agents/` (project-level precedence, CANON marker at the top of
> that file) — step 1's target below is re-rooted to the live, editable copy; the HOME copy it
> shadows must never be edited directly (2026-07-16 red-team finding #7).

1. Write `.claude/agents/wr2-design-architect.md` (orchestrator subagent).
2. Write `~/.claude/skills/bali-zero-brand/constitution.md` (hard rules).
3. Write `~/.claude/skills/bali-zero-brand/SKILL.md` (entry point with progressive disclosure).
4. Stub `~/.claude/skills/bali-zero-brand/tokens.json` (palette + type + spacing — derive from `packages/core/tokens/primitives.css` + WR2 reference PDFs).
5. Stub `~/.claude/skills/bali-zero-brand/voice/on-tone-examples.md` and `off-tone-examples.md` (5 each from past WR2 winners + 3 known fails).
6. Stub `~/.claude/skills/bali-zero-brand/layouts/` with 3 parametric layouts derived from WR2 reference PDFs (cover-photo, photo-headline-yellow-sub, statement-bomb-closing).
7. Wire critic subagent (`wr2-critic`) with vision capability for PNG quality check.
