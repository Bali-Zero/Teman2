---
name: wr3-symbiosis-precedence
description: WR3 cross-Symbiosis law precedence doctrine. When laws conflict in a WR3 episode, this file is authoritative. Loaded by wr3_supervisor.py at startup.
---

# WR3 Symbiosis Precedence

> **Authoritative source for inter-law conflict resolution in WR3 pipeline.**
> Loaded verbatim by `scripts/wr3_supervisor.py` at startup. Modify only with
> Antonello sign-off (commit message must reference Telegram approval).

## The 4 leggi most likely to conflict in WR3

| #   | Legge                | Conflict surface in WR3                                             |
| --- | -------------------- | ------------------------------------------------------------------- |
| 2   | OSINT blindato       | NB source_ids must never leak to brief.json/script.json/manifest    |
| 4   | Graceful degradation | Some failures should HALT (hard_fail), others should DEGRADE-LOUD   |
| 5   | Zero ultima istanza  | Antonello can override budget ceiling or VO requirement per-episode |
| 7   | Numeri prima         | Every claim has claim_id, cost ceilings strict, ArcFace ≥0.6        |

## Precedence chain (highest → lowest)

```
Law 2 (OSINT)
  ↓ trumps
Law 5 (Zero authority)
  ↓ trumps
Law 7 (Numeri prima)
  ↓ trumps
Law 4 (Graceful degradation)
```

## Concrete rulings

### Ruling 1 — Law 2 > Law 5 (OSINT trumps Zero override)

**Scenario:** Antonello approves publishing an episode. Critic detects an NB
source_id leaked into manifest's `legal_citations` field.

**Outcome:** Episode HALTS regardless of Antonello's pre-publish approval.
The leak must be excised first. Antonello cannot override Law 2.

**Why:** OSINT compromise is reputational damage that cannot be undone post-publish.
Zero's authority covers operational decisions, not OSINT integrity.

### Ruling 2 — Law 5 > Law 7 (Zero override on budget allowed)

**Scenario:** wr3-shot-director hits `max_budget_usd=0.50` ceiling on Opus reasoning.
Episode is a critical pilot. Antonello replies "go" on Telegram P0.

**Outcome:** Manual budget extension via per-episode override token. Run extends
to (e.g.) $1.00 ceiling. Telemetry flags `manual_override_zero_approved: true`.

**Why:** Zero's authority covers operational ceilings. Numeri prima (Law 7) is
not absolute — it's about discipline, not impossibility.

### Ruling 3 — Law 7 > Law 4 (Cost ceiling trumps graceful degradation)

**Scenario:** wr3-pre-render-gatekeeper detects Flow Pro balance <200 cr.
Episode in flight. Law 4 would say "try anyway, degrade gracefully on first failure."

**Outcome:** HARD HALT before any Veo spend. No graceful attempt.

**Why:** Cost overrun creates institutional debt that compounds. Graceful
degradation is for visible/recoverable failures, not for "spend what we don't have."

### Ruling 4 — Law 4 cascade order (within Law 4 itself)

When Law 4 applies (all higher laws not in conflict), the degrade-loud cascade is:

1. **Primary path** — agent on Tier 1 (Sonnet for routine, Opus for reasoning)
2. **Tier 2 cascade** — Gemini 3.1 Pro free OAuth (long-context safety net)
3. **Tier 3 cascade** — Codex GPT-5.5 via ChatGPT Pro (when both above exhausted)
4. **Tier 4 cascade** — Ollama local (Sonnet/Opus quality unattainable; reserve for non-blocking tasks)
5. **Final degrade** — flag in manifest + Telegram P0

NEVER silent degradation (Article 5.10 of brand constitution). Every degrade is logged.

## Implementation in code

`scripts/wr3_supervisor.py` reads this file at startup. Each agent dispatch
wraps `try/except` with precedence check:

```python
try:
    result = await dispatch_agent(agent_name, prompt)
except OSINTLeakError:  # Law 2
    halt_episode(reason="osint_leak", telegram_p0=True)
    raise  # NOT acked — investigate manually
except BudgetExceededError:  # Law 7
    if is_gate(agent_name):  # design-architect, pre-render-gatekeeper
        halt_episode(reason="budget_gate", telegram_p0=True)
        raise
    elif is_hot_path(agent_name):  # Law 4 cascade
        result = await cascade_to_gemini(agent_name, prompt)
    else:
        mark_failed_for_retry(agent_name)
except Exception as e:  # Generic — Law 4 degrade-loud
    if is_hot_path(agent_name):
        await telegram_p0(f"WR3 {agent_name} crashed: {e}")
    raise  # NOT acked — replays on reconnect
```

## See also

- `docs/wr3/contracts/_schema.yaml` — meta-schema validates per-agent `law_compliance` block
- `~/.claude/skills/bali-zero-brand/wr3/_voyager-curriculum.md` — skill lifecycle (Law 8)
- `SYMBIOSIS.md` (monorepo root) — 8 leggi inviolabili authoritative reference
