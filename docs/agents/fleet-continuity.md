# Fleet, conductor and continuity — ladder, account lanes, spend order

> Moved out of `AGENTS.md` on 2026-09-10 (boot diet). Substance unchanged.
> §17.1 (conductor-is-a-role) stays in `AGENTS.md`: it carries the PARABELLUM door line.

Binding roster + corrections: research/operations/2026-08-10-fleet-order-spec.md

**SSOT files:** cloud fleet = `FLEET_TOPOLOGY.json` (repo root) · local Ollama = `MODEL_TOPOLOGY.json` (unchanged) · rationale + four-groups study = `research/operations/2026-08-09-quattro-gruppi-e-continuita.md` · roles roster = FLOTTA-LLM doc referenced there.

**Full model roster × strengths × efforts: `MODEL_ROSTER.md`** — read it before choosing seats (Zero ruling 2026-08-14). Every conductor door (claude/codex/agy/kimi/qwen) reads `AGENTS.md`, so this is the shared denominator.

### 17.2 Continuity ladder — no line ever stops

When a seat hits quota or dies, escalate IN ORDER and log each hop in the task evidence:

1. **Rotate account, same model** (zero quality loss): Anthropic ×4 via OAuth profile swap (cswap-style), OpenAI ×2 via `CODEX_HOME=~/.codex-o2`.
2. **Substitute model within the role** per `FLEET_TOPOLOGY.json` chain (builder: sonnet→codex→glm · refuter: sol→k3→gemini · grunt: haiku→local…).
3. **Cross-family fallback**, marked `degraded_execution: true` in the Evidence Pack (the gate sees it).
4. **Queue, never silent-stop**: chain fully dead → park in PENDING-ARMS with reason + timestamp.

**Carve-outs (special ladders):**

- **Gear-3 harness gate (RULED 2026-08-20, supersedes the 2026-08-09 ruling):** **Opus 5 `effort=xhigh`**, rotating across ALL Anthropic accounts (AZ→A2→A3→A1). No fallback tier below it — Fable is out of the workflow, so there is no `gate_degraded: fable→opus` to record anymore. All Anthropic accounts dead → queue. Never pay per-token to unblock.
- **WR2 on-disk content gate (RULED 2026-08-20):** **Opus 5 `effort=xhigh`** — was unconditionally Fable; no fallback either way, window dead → SUSPEND.
- PII lanes = local models only → queue. Client-facing = Anthropic interactive only.

### 17.3 Account-lane mapping (lanes with borrowing, not round-robin)

Lanes are **home assignments, not fences**: each lane drains its home account first, then borrows automatically from the least-loaded other account — nothing sits idle, no line ever stops. Mapping (see `FLEET_TOPOLOGY.json` → `accounts`): **A1** antonellosiano interactive/architect · **A2** kaiser1987… subagents/build+Cowork · **A3** applevisionpro1987 cron/batch, **designated donor** (cron auto-pauses to free its window when the gate calls) · **AZ** zero (Team seat Premium) **gate primary** — the dedicated allowance for the final on-disk gate lives here (Opus 5 xhigh effort, RULED 2026-08-20; was Fable's dedicated weekly allowance) · **O1** antonellosiano (ChatGPT Pro) refuter-primary · **O2** zero (ChatGPT Pro) builders+refuter-backup.

### 17.4 Spend order

Flat subscriptions → Token Plan credits → local. Anything per-token (incl. Google overage credits) requires Zero's explicit GO (CLAUDE.md §5). Note: §15 above is 4.6-era; for 5-family API gotchas (thinking on by default, `max_tokens` covers thinking+answer, no temperature knob, min-cacheable 512, tokenizer ≈+30%) see CLAUDE.md §«5-family» and the fleet research doc.
