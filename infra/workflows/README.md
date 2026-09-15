# infra/workflows — reusable Workflow templates

Versioned, repo-tracked Workflow scripts (the `Workflow` tool's `scriptPath` input).
Born from the self-loop plan Anello 4: the generator≠grader pattern was well-documented
in the `sota-architecture-loop` skill but only ever EXECUTED via ad-hoc, ephemeral
session files (`<session>/workflows/scripts/*.js`) that vanish. These are the durable,
citable artifacts.

## saetta.js — portable BLUE missions

Prepare a mission with `scripts/saetta.py` (preflight, prepare, native smoke, run).
Its manifest names durable briefs, repository-relative write scopes and task
dependencies. `maxParallel` is 1–3. Unordered slices must have disjoint literal
file/directory scopes; overlap requires a dependency. Each brief supplies numeric
active-time/child budgets and the authorized release and prove-live steps. Use a
dedicated broker worktree on the launch host.

The scheduler requires a complete Dux result, an independent exact-head PASS,
agent-attested receipt read-back, merge and live proof before releasing dependencies.
The native DSL has no filesystem or GitHub access: gate/release seats perform
those checks; the scheduler checks their structured verdicts and target equality.
Any missing stage keeps those dependencies closed while unrelated tasks proceed.
One mission receipt closes the run; only the imperator can rule on its BLOCK.
This is a successor for new missions, not an in-place update of active session
scripts. Native-app branches without PR gates and ORANGE missions are not accepted.
An unobserved merge stays BLOCK even when the queue merges later; the imperator
must reconcile that target and its live proof before starting a successor.

Behavioral tests: `node --test infra/workflows/tests/test-saetta.mjs`.
These stub agent responses to exercise the real scheduler; native runtime smoke
and live release receipts remain separate, required evidence.

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

## second-army.js — the Gear <= 2 army, made executable

The mechanical layer for the "second army" doctrine (`docs/architecture/dual-consul/army-map.md`
§1ter) — everything BELOW the Gear-3 floor that belongs to the champions' chain of §1
(Generals/Dux/gate/release-owner).

**The direction of verification is the whole point, and it is the opposite of the "cheap
verifier" instinct** (RULED by Zero 2026-09-15): the INFERIOR seats BUILD, the Dux SPAWNS them
and VERIFIES on disk. A weaker seat never grades a stronger one.

```
Workflow({ scriptPath: "infra/workflows/second-army.js", args: {
  mission: "…", colour: "blue" | "orange", floor: 1,
  tasks: [ { key: "t1", prompt: "…", files: ["…"], proof: "…" } ],
  outDir: "research/operations",       // default if omitted
  stamp: "20260915T120000Z",           // REQUIRED — Date is unavailable inside a Workflow script
  frozenRef: "origin/agent/…",         // floor 2 only: the PUSHED ref the refuter reads
}})
```

Returns `{ mission, colour, floor, promoted, built, verified, refuted, refuter, deadTiers, reportPath }`.

- **Floor-3 promotion**: `floor >= 3` PROMOTES the mission to the champions' chain of §1 — no
  build, verify or refute lane runs; only a report lane records the promotion. `deadTiers` still
  carries the four declared-dead seats (see below), unprobed.
- **Who builds** (`CHAIN[colour].builders`, and roster order IS fallthrough order): BLUE, under a
  Sonnet Dux, tries `luna` → `spark` → `flash` → `deepseek-flash` → `qwen-plus` → `haiku`;
  ORANGE, under a Terra Dux, tries `haiku` → `flash` → `deepseek-flash` → `qwen-plus`.
  `chooseBuilder()` skips any seat sharing the Dux's OWN family outright unless it is
  `HAIKU_GRUNT_SEAT`. That exception only ever binds on BLUE, where Haiku is Anthropic-native
  like the Sonnet Dux: there it sits last in the roster, so it is reached only once every
  cross-family door has probed dead, and its use is logged rather than hidden. On ORANGE Haiku is
  first in the roster and correctly so — under a Terra Dux it is already cross-family, and the
  grunt exception never applies. Every build lane is `model:"haiku"`: either Haiku is the chosen
  builder, or Haiku is only the grunt shell that reaches the external door.
- **Who verifies**: the DUX lane, `model:"sonnet"` (`DUX_LANE_MODEL`). It re-derives the proof
  criterion ON DISK — runs the proof command, reads the files, reads the diff — and returns
  `{holds, observation, command}`, so a verdict always names the command that produced it. On
  ORANGE that sonnet lane is only the harness-side driver: it shells to the Terra door so the Dux
  SEAT derives the verdict. The verify lane is read-only by doctrine; a grader that can edit what
  it grades is not a grader.
- **The verifier never sees the builder's claim** — the verify prompt restates the task and the
  `proof` criterion only. The script compares verdict against claim only after the verdict returns.
- **Floor-2 cross-family refuter**: at `floor === 2` exactly ONE cheap seat (`spark`, else `flash`
  — whichever probes live first) reads the FROZEN diff at `args.frozenRef` AFTER push and tries to
  refute it. One seat, never a council. At any other floor no refuter lane is launched and
  `refuter` comes back `null`.
- **Probe-then-trust**: every bash-door seat in play (the Dux door, the whole builder roster, and
  the refuter candidates at floor 2) gets a live 1-token probe THIS run before it can be chosen —
  a seat is never trusted on reputation. Native seats (`sonnet`/`haiku`) are not probed; the
  harness running them is their own probe. `kimi`, `qwen-cloud-code`, `tp1-glm-5.2`,
  `tp1-deepseek-v4-pro` are declared dead WITHOUT probing (probing a known-dead seat burns quota
  for nothing) and always land in `deadTiers` with `reason: "declared-quota-dead-2026-09-15"`.
- **Gemini slug**: `agy models` on M5, 2026-09-15, returned `gemini-3.8-flash-{high,medium,low}`
  and the 3.7/3.6 families — `gemini-3.5-flash`, the spelling the rest of the repo still carries,
  was NOT in the live list. The `flash` door pins `gemini-3.8-flash-low`.
- The run report lands at `` `${outDir}/second-army-${mission}-${stamp}.md` `` — written by a
  `model:"haiku"` lane with the Write tool, never by the script directly.

**Testing**: `node infra/workflows/tests/test-second-army-contract.mjs` — 12 contract tests that
assert the ruled DIRECTION, not merely the syntax. They are run by hand today; nothing in
`.github/workflows/` executes `infra/workflows/tests/` yet, for this suite or any other, and
wiring that up is its own PR because `.github/workflows/` is a hot-zone path.
