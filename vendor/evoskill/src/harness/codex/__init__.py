"""Stub for the upstream src/harness/codex package.

Bali Zero Nuzantara vendor strip (panel finding v2 Codex #2 HIGH):
the upstream `executor.py` + `options.py` + `skill_discovery.py`
modules used `openai-codex-sdk` to talk to ChatGPT Pro Codex CLI.
Autonomous loops triggered Cloudflare protections + a 500-msg/3h
quota cap which would lock Antonello's daily ChatGPT Pro access.
We use DeepSeek V4 Pro API (~$0.10-0.30/run) as cheap insurance
instead. The stub stays in place so legacy
`from src.harness.codex import ...` raises a loud ImportError
rather than a silent ModuleNotFoundError.

See `vendor/evoskill/UPSTREAM.md` for the full diff list vs
upstream tag v1.1.0 (SHA 5ae91616...).
"""

raise ImportError(
    "src.harness.codex is disabled per Bali Zero Nuzantara panel "
    "finding (ChatGPT Pro rate-limit risk on autonomous loops). "
    "Use provider=deepseek in agent-library/config/evolver.toml "
    "instead — DeepSeek V4 Pro API ~$0.10-0.30/run, no rate-limit "
    "exposure on Antonello's daily Pro access."
)
