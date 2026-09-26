---
spec_id: R4
title: EXPERIMENTAL_AGENT_TEAMS pilot — multi-agent collaboration
tier: research
priority: P4
effort_estimate: 60 min pilot, indefinite if adopt
status: DRAFT — RISK: prior pilot 2026-05-12/13 hallucinated deliverables (case in cicatrix)
basis: 2026-05-21-arming-arsenal Part 6 + cicatrix anti-hallucination scar 2026-05-13
---

# R4 — EXPERIMENTAL_AGENT_TEAMS pilot

## ⚠️ Cicatrix warning

Pilot agent-teams 2026-05-12/13 → ho **fabbricato** 3 file deliverable inesistenti dopo che lead session aveva fallito synthesis. Antonello ha sentenziato:

> _"Errare è umano, allucinare è diabolico"_

Anti-hallucination 5 regole obbligatorie ora attive (vedi memory `lessons_hallucinating_tool_output_is_diabolical.md`).

Multi-agent pilot deve avoid same failure pattern.

## Problem

EXPERIMENTAL_AGENT_TEAMS (Anthropic feature) = multi-agent collaboration where:

- Lead orchestrator delega a sub-team
- Sub-team work in parallel
- Lead synthesizes outputs

Use case Nuzantara potential:

- WR3 production (already uses 8 subagent — but linear, not "team")
- Cross-domain research (visa + tax + property simultaneous)
- Complex audit (security + compliance + performance parallel)

Risk: hallucination if lead doesn't empirically verify sub-team outputs.

## Acceptance criteria (pilot)

- [ ] Identify ONE concrete use case with measurable success
- [ ] Run pilot with strict verification gate (every claim → empirical Read)
- [ ] Compare vs single-agent baseline (quality + time)
- [ ] Document outcome + decision

## Implementation steps

### Step 1 — Choose pilot use case

Candidate 1: **Multi-domain client quote**

- Client asks "I want to open PT PMA with KITAS for self + spouse, plus property purchase + tax structuring"
- Lead = client-case-quote-generator
- Sub-team:
  - visa-specialist (KITAS analysis)
  - tax-specialist (PMA + property tax)
  - property-specialist (Indonesian Hak Pakai)
  - regulatory-watcher (latest changes)
- Synthesize: comprehensive quote PDF

Candidate 2: **Security audit pre-deploy**

- Backend change touching auth + RBAC + DB schema
- Lead = pre-deploy audit
- Sub-team:
  - devils-advocate (attack vectors)
  - backend-verifier (T3.3, health)
  - spalla-review (T3.3, code review)
  - mcp-health (T3.3, dependency)
- Synthesize: PASS/FAIL/RISK report

Candidate 3: **WR3 critic 4-lane** (already exists)

- Reference, not pilot

→ **Recommended pilot = Candidate 1** (multi-domain client quote).

### Step 2 — Design with anti-hallucination gate

Critical: lead orchestrator MUST verify each sub-team output BEFORE synthesis.

Verification gate:

```python
for sub_output in sub_team_outputs:
    # Empirical verification
    if "file_path" in sub_output:
        assert pathlib.Path(sub_output["file_path"]).exists(), f"FABRICATED: {sub_output}"
    if "regulatory_citation" in sub_output:
        # NB-INTEL cross-check
        verified = mcp__notebooklm-mcp__notebook_query(...)
        assert verified.contains(sub_output["regulatory_citation"]), f"FABRICATED: citation"
    if "price" in sub_output:
        # PricingTool cross-check
        verified = mcp__nuzantara-mcp__get_all_prices()
        assert sub_output["price"] in verified, f"FABRICATED: price"
```

If verification fails → log + halt + escalate Antonello.

### Step 3 — Run pilot

Real client case (anonymized): "Marco T. wants PT PMA + KITAS + property Rp 5B + tax structuring."

Lead dispatches 4 sub-agents in parallel:

```python
Agent(subagent_type="general-purpose", description="visa KITAS analysis for Marco T.", prompt="...")
Agent(subagent_type="general-purpose", description="tax PMA + property", prompt="...")
Agent(subagent_type="general-purpose", description="property Hak Pakai Rp 5B", prompt="...")
Agent(subagent_type="regulatory-watcher", description="recent changes immigration + property", prompt="...")
```

Lead waits all 4 returns.

Lead applies anti-hallucination gate (Step 2 verification).

Lead synthesizes consolidated quote.

### Step 4 — Compare baseline

Same case via single-agent (client-case-quote-generator alone):

- Time: T_single
- Quality: subjective + checklist
- Verification effort: T_verify_single

Vs multi-agent:

- Time: T_multi (likely faster due parallel)
- Quality: same checklist
- Verification effort: T_verify_multi (likely higher due gate)

Net = T_multi + T_verify_multi vs T_single + T_verify_single.

### Step 5 — Decision memory

```bash
cat > ~/.claude/projects/-Users-nuzantara-Desktop-nuzantara/memory/decision_agent_teams_pilot_2026_05_21.md << 'EOF'
---
name: agent-teams-pilot-r4
description: R4 pilot outcome — agent teams adoption decision
metadata:
  type: decision
---

# R4 EXPERIMENTAL_AGENT_TEAMS pilot outcome (2026-05-21)

## Pilot case: <case>
## Decision: <ADOPT|REJECT|HYBRID>

## Metrics
- Single-agent baseline: T_single + T_verify = <X> min, quality <score>
- Multi-agent: T_multi + T_verify = <Y> min, quality <score>
- Hallucinations detected at gate: <Z>

## Decision rationale
<text>

## Anti-hallucination outcome
<gate caught X hallucinations | gate caught 0 — fortunate>

## Reference
- spec: research/operations/specs/R4-experimental-agent-teams.md
- prior cicatrix: lessons_hallucinating_tool_output_is_diabolical.md
EOF
```

## Verification

### Test 1 — Pilot case executed

Multi-agent fan-out completed without hallucination AND with all 4 sub-team output verified.

### Test 2 — Quality acceptable

Output checklist 100% covered, matching baseline.

### Test 3 — Anti-hallucination gate effective

Manually inject 1 fake citation in sub-team output, gate catches it. If gate fails to catch → BLOCKER, do not adopt.

## Rollback

Pilot only — no install needed, just stop dispatch.

If adopted later and goes south:

- Disable EXPERIMENTAL_AGENT_TEAMS flag in Claude Code config
- Revert to single-agent workflow

## Open questions

1. **EXPERIMENTAL_AGENT_TEAMS = actually available?**: nome è from Anthropic best-practices but may be future. Verify in Anthropic docs.
2. **Cost**: 4 parallel agents = 4× context window consumption. With Claude MAX OAuth, quota? Verify with empirical test (one pilot = 1 burst).
3. **State sharing**: sub-team agents share state via TaskCreate / disk? Anthropic spec gap.
4. **Hallucination detector reliability**: anti-hallucination gate verifica file existence + citation NB. Mancano: pricing, business logic. Need additional gates over time.

## Estimated breakdown

| Step             | Tempo      |
| ---------------- | ---------- |
| Choose use case  | 5 min      |
| Design gate      | 15 min     |
| Run pilot        | 25 min     |
| Compare baseline | 10 min     |
| Decision memory  | 5 min      |
| **Total**        | **60 min** |
