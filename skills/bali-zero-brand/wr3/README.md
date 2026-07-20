---
name: wr3-cortex-readme
description: WR3 skill cortex root README — directory map, lifecycle states, entry points.
---

# WR3 Skill Cortex Root

## Directory map

```
~/.claude/skills/bali-zero-brand/wr3/
├── README.md                         # this file
├── _voyager-curriculum.md            # skill lifecycle states + graduation rules
├── _reflexion-synthesis.py           # weekly cron driver (Sun 02:30 WITA, S7.5 implements)
├── _proposed/                        # skill drafts awaiting graduation
├── _archived/                        # retired skills (unused ≥30d)
├── _quarantine/                      # dangerous skills (linked to critic FAILs)
├── design-architect/SKILL.md
├── brief-interpreter/
│   ├── SKILL.md
│   ├── nb-routing-domain-map.md      # domain → NB ID mapping
│   └── legal-claim-extraction-templates.md
├── script-editor/SKILL.md
├── shot-director/SKILL.md
├── pre-render-gatekeeper/SKILL.md
├── clip-renderer/SKILL.md
├── audio-asset-producer/SKILL.md
├── post-assembler/SKILL.md
├── critic/SKILL.md
├── reflexion-synth/SKILL.md
├── yt-metrics-analyst/SKILL.md
├── editorial-bench/SKILL.md
└── b-roll-curator/SKILL.md
```

## Cortex sharing

WR3 inherits `bali-zero-brand` parent cortex (palette tokens, voice registers,
taboo phrases, layout families). The WR3 subtree adds video-specific:
- on-tone-examples (populated post-3-pilot)
- cliche-library (250+ banned visual patterns, populated during S7.5)
- lessons growth surface (per-agent)

## Loading discipline

Each wr3-* agent loads ONLY its own `<agent>/SKILL.md` + parent
`~/.claude/skills/bali-zero-brand/` brand cortex. No cross-loading
between WR3 agents (avoids confusion / brand drift).

## See also

- Agent definitions: `~/.claude/agents/wr3-*.md`
- I/O contracts: `~/nuzantara/docs/wr3/contracts/*.yaml`
- Symbiosis precedence: `~/nuzantara/docs/wr3/symbiosis-precedence.md`
- Step 06 architecture: `~/nuzantara/research/wr3/06-architecture-skeleton.md`
