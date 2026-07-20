# infra/workflows — reusable Workflow templates

Versioned, repo-tracked Workflow scripts (the `Workflow` tool's `scriptPath` input).
Born from the self-loop plan Anello 4: the generator≠grader pattern was well-documented
in the `sota-architecture-loop` skill but only ever EXECUTED via ad-hoc, ephemeral
session files (`<session>/workflows/scripts/*.js`) that vanish. These are the durable,
citable artifacts.

## verify-template.js — generator≠grader (gather → adversarial-verify → synthesize)

The one principle of the whole self-loop: **judging < generating**. A finding survives
ONLY if an INDEPENDENT skeptic on FRESH context could not refute it (the grader is never
the generator — no self-approval; the W65 lesson).

Run it for any research / audit / multi-claim verification:

```
Workflow({ scriptPath: "infra/workflows/verify-template.js", args: {
  question: "the question to answer",
  angles: [ { key: "a", prompt: "lens A …" }, { key: "b", prompt: "lens B …" } ],
  synthesisPrompt: "(optional) how to merge survivors",
  skeptics: 1            // 1 default; 3 for high-stakes (security / regulatory / client-quote)
}})
```

Returns `{ synthesis, survivors, refutedCount, anglesRun }`. Calibration follows
`sota-architecture-loop` §3/6: one strong skeptic by default (troublemaker), not consensus,
not a massacre. Heterogeneity > numerosity — give each angle a DISTINCT lens.

**Doctrine reference**: skill `sota-architecture-loop` ("verifica esterna batte
autodichiarazione · adversarialità calibrata batte consenso") + `opus-mythos` (never trust
your own subagent). This file is the doctrine made executable & reusable.

## kbli-pilot-a1.js — GARUDA-FILIERA per-code adjudication (D1 → D5 → D2)

The mechanical/orchestrator layer for the KBLI Filiera per-code reconstruction program
(research/operations/2026-07-16-kbli-garuda-filiera-workflow.md §1-§3). Fans out to one
Sonnet 5 seat per code per stage — D1 proposes the 2020↔2025 crosswalk mapping from
already-rendered evidence PNGs, D5 blindly re-derives and either certifies or refutes
(generator≠grader, never shown D1's answer until it has its own), D2 runs only when D1
concluded the code's licensing facts inherit from a KBLI-2020 source and the pair wasn't
quarantined. Innocence-control codes (no `pp28_sources`) get a single short
"verify nothing needs changing" prompt instead.

This script is a pure **proposer** — it never writes `data/kbli-filiera/**` (guard-protected).
Its return value is fed, one code at a time, into `scripts/kbli_filiera/dossier_assemble.py
--proposals` (the sanctioned compiler writer).

```
Workflow({ scriptPath: "infra/workflows/kbli-pilot-a1.js", args: {
  codes: ["68112", "51103", { code: "65121", innocenceControl: true }, ...],
  evidenceRoot: "/path/to/dossier_pull.py --out output",   // must already be populated
}})
```

Returns `{ evidenceRoot, codes, results, quarantinedCodes, summary }`. Requires
`scripts/kbli_filiera/dossier_pull.py` to have already pulled evidence for every code into
`evidenceRoot` — this script reads renders, it never fetches or renders them itself.

**Doctrine reference**: research/operations/2026-07-16-kbli-garuda-filiera-workflow.md
(seats §2, protocol §3) + research/operations/2026-07-17-kbli-pilot-a1-preregistration.md
(the frozen pilot plan this run is measured against).
