---
paths:
  [
    "scripts/generate_*.py",
    "scripts/*_doc*.py",
    "scripts/*_reference*.py",
  ]
---

# D3.1 — Doc Generator Write Blocklist

Automated doc generators MUST NEVER write to:

- `CLAUDE.md` — human-maintained, git-tracked, noisy diffs confuse AI agents
- `backend/prompts/zantara_core.py` — prompt SSOT, human-only
- `fly.toml` — infrastructure config, human-only
- `.env*` — secrets
- `alembic/env.py` — migration config

**Only allowed output target:** `docs/AUTOMATIONS_REFERENCE.md` (and other files under `docs/` that are explicitly auto-generated).

Any script that writes docs must call `_check_output_safety(path)` before writing.
