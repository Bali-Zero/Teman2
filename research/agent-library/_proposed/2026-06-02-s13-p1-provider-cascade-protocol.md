# S13-P1 — provider-cascade-protocol

> **Status**: PROPOSED (S13 evolution cycle, 2026-06-02). Draft only — Antonello approves graduation.
> **Kind**: shared-protocol · **Priority**: P1
> **Adversarial verdict**: 🔧 REVISE — right gap, wrong artifact (see revised proposal)

## Problem

7 agents re-implement multi-LLM/asset cascade independently; ALL miss breaker-state + degraded-mode marking (02-patterns#4 PARTIAL). S13 itself hit this: agy OAuth-blocked headless, DeepSeek env-drift killed the evolver — both silent until a downstream symptom.

## Proposal (as originally drafted)

One skill encoding: (a) tier order + stdout-grep exhaust detection (existing), (b) per-tier breaker state file {failures,cooldown_until} for skip-fast, (c) degraded_mode flag marking Tier-3/4 output status=draft-not-client-safe, (d) pre-flight health-ping per tier (codex --version, ollama list grep, agy auth check) so cascade never falls through to a broken tool. Reference impl already 80% in regulatory-watcher-run.sh.

## Agents served

- regulatory-watcher
- deep-researcher
- wr2-external-bench
- wr3-editorial-bench
- wr3-reflexion-synth
- wr3-audio-asset-producer
- wr3-clip-renderer

## Evidence

02-patterns#4; ~/logs/agent-library-evolver.out.log FATAL DEEPSEEK_API_KEY 2026-05-31; this S13 agy-OAuth-block

## Cross-vendor adversarial review

- **DeepSeek V4 Pro** → `REVISE`: Gap is real, but a shared skill protocol would force per-agent reimplementation; a centralized provider router or proxy is the correct fix, not a skill that agents load.
- **Codex GPT-5.5** → `REVISE`: Right gap, wrong artifact boundary. Breakers, cooldowns, health pings, and degraded flags need an executable shared runner/library plus thin skill docs; prose protocol alone will not prevent silent fallthrough.
- **Converged** → `REVISE`

## Disposition (post-adversarial)

**REVISE.** Do NOT graduate as a prose skill. Build an _executable_ shared cascade runner/library (breaker-state file `{failures,cooldown_until}`, per-tier health-ping, `degraded_mode` flag marking Tier-3/4 output `draft-not-client-safe`). DeepSeek: consider a centralized provider router/proxy so per-agent cascade logic disappears. The prose skill alone cannot prevent silent fallthrough — which S13 itself demonstrated (agy OAuth-block + DeepSeek env-drift).
