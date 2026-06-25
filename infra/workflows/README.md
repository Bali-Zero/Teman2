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
