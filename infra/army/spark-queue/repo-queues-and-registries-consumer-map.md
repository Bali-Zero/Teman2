# repo-side queues and registries: who reads each one — orphan detection

Read-only analysis — no plan to edit/commit/push anything.

Inventory every repo-side queue/registry/ledger-like surface: directories or
JSON/MD files whose NAME or README declares them a queue, registry, ledger,
allowlist, or state contract (e.g. `infra/army/*-queue/`,
`infra/home-fork/declared-pairs.json`, `infra/guard-conformance/registry.json`,
`infra/retracted-claims/registry.json`, `.claude/skills/modus/PENDING-ARMS.md`,
`infra/tg-gateway/grandfathered.json`, `runtime_state_allowlist.json`, any
`*registry*.json` / `*queue*` / `*ledger*` under `infra/`, `scripts/`,
`.claude/`).

For EACH one, answer with grep evidence:

1. Which code (script/CI workflow/hook) READS it — file:line of the consumer.
2. Which code or convention WRITES it.
3. Verdict: LIVE (read by something that runs), WRITE-ONLY (written but no
   reader found — a ledger nobody reads is W81 "esiste ≠ armato"), or
   ORPHAN (neither read nor written by anything greppable — candidate for
   retirement).

Why (scar family #2 + W107): a registry with no consumer gives false comfort
— the organism believes a guard exists because its data file does. The
2026-08-19 fleet session found the army lanes starving precisely because
nothing watched queue depth.

Output: one markdown table (surface | readers | writers | verdict | evidence
file:line). List every surface found — N of M, never a silent cap.
