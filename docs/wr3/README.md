---
name: wr3-docs-root-readme
description: WR3 docs root README. Index of contracts + precedence + runbook.
---

# WR3 Docs — Root

## Contents

```
docs/wr3/
├── README.md                       # this file
├── symbiosis-precedence.md         # cross-law conflict resolution doctrine
├── runbook-supervisor.md           # supervisor operational procedures (S7.5 expands)
└── contracts/                      # I/O contracts (S7.4 — this PR)
    ├── _schema.yaml                # meta-schema
    ├── _router.yaml                # channel → agent map
    ├── design-architect.yaml
    ├── brief-interpreter.yaml
    ├── script-editor.yaml
    ├── shot-director.yaml
    ├── pre-render-gatekeeper.yaml
    ├── clip-renderer.yaml
    ├── audio-asset-producer.yaml
    ├── post-assembler.yaml
    ├── critic.yaml
    ├── reflexion-synth.yaml
    ├── yt-metrics-analyst.yaml
    ├── editorial-bench.yaml
    └── b-roll-curator.yaml
```

## Loading at runtime

`scripts/wr3_supervisor.py` (S7.5) loads contracts at startup:

```python
import yaml
from pathlib import Path

CONTRACTS_DIR = Path(__file__).parent.parent / "docs/wr3/contracts"
schema = yaml.safe_load((CONTRACTS_DIR / "_schema.yaml").read_text())
router = yaml.safe_load((CONTRACTS_DIR / "_router.yaml").read_text())
agent_contracts = {
    p.stem: yaml.safe_load(p.read_text())
    for p in CONTRACTS_DIR.glob("*.yaml")
    if not p.name.startswith("_")
}
```

Each contract is validated against `_schema.yaml` (S7.6 lint enforces it pre-commit).

## See also

- Step 06 architecture: `research/wr3/06-architecture-skeleton.md`
- Step 07 execution state: `research/wr3/07-genesis-execution-state.md`
- Skill cortex: `~/.claude/skills/bali-zero-brand/wr3/`
- Agent definitions: `~/.claude/agents/wr3-*.md`
