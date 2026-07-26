---
date: 2026-07-17
subject: backend-modular-kernel-worker-plane
review_mode: asymmetric-independent-panel
spec: docs/superpowers/specs/2026-07-17-backend-modular-kernel-worker-plane-design.md
client_data: none
---

# Independent architecture review brief

Review the linked specification against the repository at commit
`cdaf6bb8553639498a0d333a01c1cc707844ac88`.

The review is read-only. Do not edit files, run mutation commands, contact
external systems, expose secrets, or inspect client records. Repository reads
and deterministic read-only checks are allowed. Do not infer the other
reviewers' opinions and do not optimize for consensus.

## Shared output contract

Return Markdown with exactly these top-level sections:

1. `# Verdict`
2. `# Blocking findings`
3. `# Important findings`
4. `# What survives review`
5. `# Required amendments`
6. `# Falsification test`

The verdict must be one of `GO`, `GO-WITH-CHANGES`, or `NO-GO`, followed by a
confidence from 0 to 100. Every finding must cite the spec section or line and,
when based on repository state, the repository path. Separate verified facts
from inference. A blocking finding must describe a concrete failure mode and a
falsifiable correction; do not use taste or generic best-practice language.

If there are no blocking findings, write `None` under that heading. Keep the
response below 1,500 words.

## Seat A — Fable 5: architecture judge

Judge whether the decision is coherent, reversible, and proportionate. Focus
on hidden irreversibility, boundary quality, migration ordering, whether the
fencing/rollback model can actually prevent dual ownership, and whether the
acceptance gates prove the promised architecture. Prefer deletion or a smaller
decision when it solves the same problem.

## Seat B — Gemini 3.1 Pro: constructive systems reviewer

Assume the direction should be saved. Make it deployable and operationally
complete. Focus on Fly process topology, resource/cold-start effects, queue and
event contracts, observability, rollout order, schema compatibility, and gaps
between the target and the repository's current mechanisms.

## Seat C — GLM 5.2: adversarial refuter

Assume the design is defective. Find the strongest concrete scenario in which
it loses work, duplicates an irreversible side effect, violates sovereignty,
creates a distributed monolith, or produces a green-but-dead gate. Attack
assumptions shared by the entire design, not wording. State the minimum evidence
that would make the design survive the attack.
