---
name: wr3-voyager-curriculum
description: WR3 Voyager skill library curriculum — incremental skill graduation pipeline. Tracks proposed skills in _proposed/, graduated skills in agent dirs, retired skills in _archived/, dangerous skills in _quarantine/.
---

# WR3 Voyager Curriculum

## Skill lifecycle states

| State | Dir | Trigger | Owner |
|---|---|---|---|
| **Proposed** | `_proposed/` | wr3-reflexion-synth weekly synthesis OR human review queue diff | wr3-reflexion-synth |
| **Graduated** | `<agent>/` (file in skill dir) | 3 consecutive successful uses pre-publish + critic PASS | wr3-design-architect (manual review gate) |
| **Archived** | `_archived/` | unused ≥30 days OR superseded by newer skill | wr3-reflexion-synth |
| **Quarantined** | `_quarantine/` | linked to critic FAIL ≥2 episodes (false claim, missed cliche, etc.) | wr3-critic (auto-flag) |

## Graduation criteria

A skill graduates from `_proposed/` to its agent's skill dir when ALL true:
1. Proposed for ≥7 days
2. Used by agent in ≥3 episodes
3. ≥3 of those episodes passed critic gate
4. No `_quarantine/` flag in last 30 days
5. wr3-design-architect manual review (Antonello sign-off)

### Bootstrap exception (cold-start, first 3 pilots)

**Codex+Gemini+DeepSeek 3/3 panel 2026-05-18** caught the cold-start trap:
the first 3 pilots have ZERO graduated skills, so rule 2 ("used in ≥3
episodes") can never be satisfied. Bootstrap procedure:

1. **First pilot ("Manifesto Zantara"):** all agents run on contract YAML
   + agent .md ONLY, no graduated skills. Critic gate runs without
   on-tone examples or cliche library.
2. **Pilots 2-3:** wr3-reflexion-synth proposes initial skills based on
   pilot 1 lessons. They go into `_proposed/` with `bootstrap: true` flag.
3. **Pilots 4-6:** the proposed skills are USED (not graduated) — they
   are loaded by agents as "candidate" skills with a `bootstrap` warning
   in telemetry. This gives them the ≥3-episodes-used count needed to
   graduate.
4. **Pilot 7 onwards:** standard rule-of-3 applies. Bootstrap flag
   removed from any skill that has passed critic gate ≥3 times.

This is the ONLY exception to "rule of 3" and applies ONCE per agent.

## Anti-skill (quarantine) criteria

A skill is moved to `_quarantine/` when:
- Linked to ≥2 critic FAIL verdicts in 30-day window
- Auto-flag persists 14 days unless human review unlocks
- Quarantined skills are NOT loaded by agents (filter at SKILL.md frontmatter `quarantined: true`)

## Curriculum measurement

Per-agent skill count tracked via wr3-reflexion-synth weekly health check. Target growth: +2 skills/month/agent (sustained 6 months → competitive curriculum vs WR2).
