# Runbook - Codex Nuzantara Profiles

> **What it is.** The operating map for Codex inside Nuzantara. Migrated
> 2026-07-16 (Zero "impostare a fonte") from the legacy single gpt-5.5/xhigh
> baseline to per-profile gpt-5.6 family requirements — `nuzantara-core` runs
> `gpt-5.6-sol` at `high` (everyday coding/review/architecture), `nuzantara-research`
> runs `gpt-5.6-sol` at `xhigh` (deep synthesis). Codex executes work; Skill
> Coach extracts reusable lessons; Genome stores accepted skills/scars;
> Symbiosis governs the boundaries.

## Profiles

| Profile              | Wrapper             | Use for                                             | Default rule                                     |
| -------------------- | ------------------- | --------------------------------------------------- | ------------------------------------------------ |
| `nuzantara-core`     | `codex-nz-core`     | normal coding, review, architecture, repo work      | clean surface, plugins off                       |
| `nuzantara-research` | `codex-nz-research` | deep research, specs, multi-source synthesis        | clean surface, slightly more verbose             |
| `nuzantara-toolful`  | not armed yet       | Drive, Gmail, browser, Canva, connector-heavy tasks | opt-in only after plugin cache cleanup           |
| `nuzantara-operator` | not armed yet       | explicit local operations                           | use only when the operator wants machine control |

The default should stay `nuzantara-core`. Do not make a single always-loaded
"monster" profile.

## Commands

```bash
# Normal Codex session
codex-nz-core exec "task..."

# Research/spec session
codex-nz-research exec "task..."

# Local health check from repo root
python scripts/ops/codex_config_health.py --allow-warnings
```

The wrappers set `RUST_LOG=error` and pick the intended profile. They do not
hide real task failures.

## Health Gates

`scripts/ops/codex_config_health.py` checks:

- Nuzantara profile TOML parses.
- `nuzantara-core` uses `gpt-5.6-sol` with `high`; `nuzantara-research` uses
  `gpt-5.6-sol` with `xhigh` (per-profile requirement, `PROFILE_REQUIREMENTS`
  in the script — the two diverge on purpose, see the profile table above).
- clean profiles keep `plugins=false` and `plugin_hooks=false`.
- Codex and Claude user hook configs have no active `SessionStart`,
  `UserPromptSubmit`, or `Stop` entries.
- local skill frontmatter is shaped so Codex can parse it.
- user/repo `AGENTS.md` files fit the configured context budget.

Warnings are allowed during migration. Failures mean the default Codex surface
is no longer clean.

## Council Trigger

Use one Codex xhigh pass by default.

Escalate to a multi-LLM council only when at least one is true:

- the decision is expensive to reverse;
- the task crosses architecture, data, and ops boundaries;
- there are competing priors that matter;
- the work will become a reusable skill/scar;
- a red-team view is materially useful.

Council roles:

| Reviewer    | Role                                       |
| ----------- | ------------------------------------------ |
| Codex       | implementation and repo feasibility        |
| Claude/Opus | reasoning, ambiguity, instruction quality  |
| Gemini      | long-context and external source synthesis |
| DeepSeek    | adversarial logic and cheap second opinion |

Consensus is not the criterion. The output is useful only when it changes the
spec, test plan, or risk boundary.

## Law 2

Law 2 is a cleartext-output boundary for every LLM in the system.

Client PII, raw OSINT, credentials, passports, KTP, NPWP, and WhatsApp raw data
must not be transcribed or persisted in cleartext inside prompts saved for
reuse, logs, reports, skills, memories, alerts, or shared artifacts. Use IDs,
hashes, placeholders, and redaction.

This is not Hermes-specific and not Codex-specific.

## Worktree Rule

When Codex mutates the Nuzantara repo, work in a dedicated worktree:

```bash
python scripts/agent_start.py --lane ops --task-id <slug>
cd .worktrees/ops-<slug>
codex-nz-core exec "task..."
```

The main checkout is for the operator and emergency hotfixes.

## Experience Bridge

At the end of material work, produce a redacted trajectory candidate for Skill
Coach:

```json
{
  "agent": "codex",
  "machine": "Air-M5|Pro|Mini",
  "organ": "backend-rag|mouth|agent-library|ops|research",
  "outcome": "success|failed|blocked",
  "verification": ["command or observable evidence"],
  "files_touched": ["repo-relative paths"],
  "law2_status": "redacted|not_applicable",
  "candidate_learning": "short reusable lesson"
}
```

Skill Coach may propose a skill/scar. Genome accepts it only after shadow
evaluation and the normal human gate.

## Anti-Pattern

Do not clone the full Claude Code startup behavior into Codex.

Claude Code taught us useful patterns: skills, scars, memory, hooks. Codex
should steal the principles, not inherit the startup noise.
