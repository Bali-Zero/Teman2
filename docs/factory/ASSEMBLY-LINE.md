# ASSEMBLY-LINE.md — The product factory procedure (system doctrine)

> **Status**: RULED by Zero 2026-08-24 («fondila per garuda ma fondila a livello di sistema»).
> Synthesized from a 5-seat cross-family panel (Codex Sol xhigh · Kimi K3 · Qwen 3.8 Max ·
> DeepSeek V4 Pro · Gemini 3.1 Pro), each on a disjoint lens, no contact between seats.
> Full panel capture: `research/operations/2026-08-24-product-factory-procedure-5-seat-panel.md`.
> Scope: every PRODUCT build (a user-facing thing with a business outcome). It composes with
> `modus` (which governs mandates in general); where they overlap on product work, this file wins.
> First product on this line: **GARUDA VOA** (`docs/plans/2026-08-24-garuda-voa-live/MANDATE.md`).

## The one inversion everything hangs on

**An artifact exists only if a gate consumes it.** If no automated gate or owner decision reads
a document, it does not get written. Work-state lives in code, contracts, tests, and the merge
queue — never in ledgers, status reports, or handoff prose.

Root cause it kills, re-derivable rather than asserted: of the **last 100 merged PRs** as of
2026-08-24, **39 touched nothing but** `docs/`, `research/`, `CLAUDE.md`, `AMENDMENTS.md` or a
`PENDING-ARMS` ledger —

```
gh pr list --state merged --limit 100 --json number,files --jq '[.[] |
  ([.files[].path] | all(test("^(docs/|research/|\\.claude/skills/.*PENDING-ARMS|AMENDMENTS\\.md$|CLAUDE\\.md$)")))]
  | {total: length, docs_only: (map(select(.)) | length)}'
```

The panel was briefed with "56%", which nothing in this repo reproduces; the figure is
definition-sensitive and window-sensitive, so the query above is the claim and 39/100 is its
value. The conclusion is unchanged either way — roughly two of every five merges move no
product — but a doctrine that cites a number it cannot re-derive is doing the thing it forbids.

## The unit of "done"

Not the PR, not the merge: **a customer journey working in production, meeting its SLO,
producing its business outcome.** "Merged" is an intermediate state.

## The 5 permanent artifacts per product (nothing else survives)

| Artifact       | Content                                                                                                                | Written by                       |
| -------------- | ---------------------------------------------------------------------------------------------------------------------- | -------------------------------- |
| `product.yaml` | customer, problem, promise, price, primary metric, guardrails (≤3), non-goals, **kill criterion**, owner decisions log | Orchestrator drafts, owner signs |
| `journeys/`    | state machine + acceptance scenarios (happy, failure, recovery — every sad path named and test-owned)                  | Architect seat                   |
| `contracts/`   | OpenAPI 3.1 + generated TS client, event schemas, error catalog, N/N−1 compatibility                                   | Architect seat, frozen at gate   |
| code + tests   | the product                                                                                                            | Builder lanes                    |
| `ops/`         | SLOs, synthetic-journey probes, alerts-as-code, runbook                                                                | SRE/grunt lanes                  |

Evidence of a release is CI output (`release-evidence` generated, never hand-written). One ADR
is admitted only for an irreversible decision (embedding-model-freeze class).

## The 8 stages and their gates

0. **INTENT** — owner + orchestrator produce `product.yaml`. Gate G0 (owner): a specific user,
   a falsifiable metric, ≤3 guardrails, a sellable first vertical slice, a kill criterion.
1. **GROUND** — researchers (Gemini long-context, Kimi live-web, NotebookLM domain truth)
   verify every regulatory claim, price, dependency: each tagged `verified` / `assumption` /
   `unknown`. Gate G1: no `unknown` may control payment, eligibility, or a customer promise.
2. **JOURNEY** — state machine + Gherkin/Playwright journey specs written BEFORE code, by a
   different family than the one that will build. Gate G2: specs fail RED cleanly against empty
   endpoints; every sad path (expired link, corrupt file, uncertain OCR, duplicate payment,
   out-of-order webhook) is named and test-owned.
3. **CONTRACT** — OpenAPI + events + error catalog + migrations (expand→migrate→contract).
   TS client generated; hand-written DTOs/fetches banned; breaking-change diff fails CI.
   Gate G3: contract FREEZE. Later changes go through the orchestrator; business-visible
   changes through the owner.
4. **PARALLEL BUILD** — 3-7 lanes max, each a vertical slice behind the product flag, own
   worktree, own file-ownership, frozen contract version. PRs ≤~200 logic lines (≤500 UI).
   Local-first integration branch; daily rebase on main; no status PRs. Gate G4 per PR:
   typecheck, unit+property tests, contract tests, ONE cross-family refuter (see economics).
5. **GAUNTLET** — on the integrated product: the full journey suite green on a real ephemeral
   environment; contract fuzzing; payment/state attack session (replay, race, webhook spoof,
   out-of-order). Gate G5: 100% journeys pass, zero unhandled schema exceptions. Judge verdict
   is binary: SHIP or one-paragraph BLOCK.
6. **SHIP DARK** — merge queue lands it flag-off; immutable build; canary synthetic journey in
   prod. Progressive: internal → 5% → 100%, SLOs green at each step; **at 5%, real users**
   (for a purchase funnel: a handful of real buyers watched end-to-end — no AI judge
   substitutes for a human failing to find the pay button). Rollback = flag off; DB stays
   backward-compatible. Gate G6 (owner): go-live and pricing only.
7. **OPERATE + LEARN** — the paged alert is a BUSINESS INVARIANT ("paid orders in rolling
   24h above 0", "median upload→OCR < 60s"), plus a synthetic transaction that really buys
   (sandbox pay, refunded) every 10-15 min with a dead-man switch: probe silent 15 min → flag
   auto-off + owner alert. Infra-level alerts are demoted. Monthly: kill criterion checked —
   alive / narrowed / killed. Every incident ends in a changed contract, test, monitor, or
   runbook — never in a narrative doc.

## Verification economics (DeepSeek seat, adopted)

- **One cross-family refuter per PR by default — and the default is a budget rule, not a safety
  finding.** The panel's DeepSeek seat justified it with "simulation shows a single reviewer
  catches 70% of bugs; a second adds only 15%". **No simulation was described, parameterised or
  linked**, so treat 70/15 as a plausible heuristic and never as evidence. It is deliberately
  recorded here rather than laundered, because a fabricated-sounding number that argues for LESS
  review is the one kind this factory must not absorb silently.
  **The P0 tier is exempt from the cap**: the doctrine's own `p×r×C > c` formula argues for MORE
  review exactly where payment, eligibility and state live, so a flat "never two" would override
  the formula at its highest values. Multi-seat panels stay reserved for architecture and for the
  integrated product (stage 5); on a P0 PR, a second seat is a judgement call the orchestrator may
  make, not a rule violation.
- **Risk-tiered review** (`p×r×C > c`): payment/eligibility/state code always gets the full
  adversarial pass; cosmetic UI gets contract-tests + visual diff only. The tier map is set
  once per product in `product.yaml`.
  **"Full adversarial pass" is defined, because an undefined gate is not a gate**: a cross-family
  refuter reading the diff, PLUS an attack session against the running surface (replay, race,
  out-of-order, spoofed signature, boundary dates), PLUS an independent re-derivation of every
  money and date figure by a seat that did not build it. Three things, not one reviewer working
  harder.
  **The refuter is dispatched only after the generator is confirmed dead, and only once the
  artifact's hashes hold stable across a settling window.** A refuter set loose over a live
  writer is reviewing a moving target, and a moving target is unreliable in both directions at
  once: it can miss a defect introduced after it looked, and it can just as easily report a
  defect the still-running generator has already cured, handing the orchestrator a stale finding
  dressed as a current one. Measured 2026-08-24 during the GARUDA VOA contract freeze: a refuter
  dispatched while the generator process was still writing watched the contract file's hash
  change twice under it before it froze its own read, and three of its findings — two dead error
  codes, an invalid `discriminator` block, and a security tightening on an authentication route —
  had already been fixed by the live writer by the time the report landed. This is a process
  check, not a file check: `git status` clean proves nothing, because the generator writes
  untracked files. The measurement is no live writer process rooted in the worktree, AND the
  artifact hashes unchanged across a settling window. A report produced over a live writer must
  be re-measured line by line before any finding is accepted or rejected — which costs more than
  waiting for the writer to finish would have.
  **Waiting for the generator to die is not always available, and there is a stronger form that
  works whether or not it is: hand the refuter an extracted artifact at a fixed commit, never a
  live ref.** The Visa Oracle orchestrator hit the same trap the same day, on a generator it had
  no authority to stop — another lane's long-running job — and got past it by extracting the diff
  it cared about into a throwaway worktree pinned to a fixed merge commit, so the refuter read a
  frozen snapshot while the branch underneath kept moving. Two independent lanes finding the same
  structural trap within hours of each other is a property of the process, not of one team's bad
  afternoon. Prefer extraction; fall back to waiting for the writer to die only when extraction is
  impractical.
- **Queueing discipline**: WIP ≤2 PRs per lane; merge-queue utilization <70%; a lane blocked
  over 2h gets split or re-scoped by the orchestrator, not pushed harder.

## Roles (5 families, all used fully — vendor parity per Zero 2026-08-24)

- **Orchestrator (Opus 5)**: owns `product.yaml`, lane graph, contract freeze, exceptions and
  the final gate. Never codes, never style-reviews, max ~5 concurrent decisions — everything
  else is delegated with local lane authority. Escalation to the owner is a one-page decision
  packet: context, recommendation, cost, one button.
- **Architect (Sol or Gemini Pro)**: contracts, state machines, platform reuse.
- **Builders (Sonnet 5, Terra, Kimi-for-coding, GLM 5.2)**: one vertical slice each.
- **Researchers (Gemini 3.1 Pro, Kimi K3 live-web, NotebookLM ground truth, Qwen corpus)**.
- **Refuters (always a different family than the generator — Kimi K3, Sol, DeepSeek V4 Pro,
  Gemini)**: DeepSeek re-derives every date/price/refund number from scratch and must match
  the engine.
- **Grunt (Haiku, Luna, Qwen flash tiers, local Ollama)**: scaffolding, fixtures, migrations,
  i18n, probes. Never where a silent error would go unnoticed.

## Deliberately NOT adopted

Sprints, standups, story points, velocity · human code review · PRD/design-doc chains ·
narrative retrospectives (a postmortem that doesn't end in a mechanical check is theater) ·
dashboards farms (one paged business invariant per product; the rest on demand) · ADR as a
genre · multi-model consensus on mechanical tasks (consensus among LLMs is averaging, not
wisdom) · premature microservices/K8s · 100% coverage as a goal · permanent divergent staging.

## A cost warning that bounds "extreme power"

Multi-agent fan-out costs ~15× tokens (Anthropic measurement) and DEGRADES on sequential
problems (Google research). The fleet's power is spent only on genuinely parallelizable work;
total simplicity is the instrument that decides what qualifies.

## Enforcement backlog (not yet armed — tracked, per superscar #2 "esiste ≠ armato")

1. CI rule: PR touching only `docs/`/`research/` requires an explicit owner-initialed label
   (kills standalone ledger PRs at the gate, not by exhortation).
2. Quarterly gate audit: **a gate that has never blocked anything is deleted.**
3. Silence-on-output detection: an active lane with no merged PR in 48h escalates (replaces
   status reports and heartbeat chatter).
4. Typed-contract toolchain (OpenAPI → TS client generation) wired into CI for the first
   product, then extracted as the platform template (`contracts kit`) for every next one.
5. **Per-PR cross-family refuter check, armed in CI.** Today the refuter discipline that replaces
   human code review is procedural — the R1 adversarial-review gate covers research captures only.
   Until this is armed, the removal of human review rests on a convention, not a check. (Raised by
   the adversarial review of this doctrine, 2026-08-24, finding 5.)
6. **Sweep the unarmed imperatives out of the body and into this list.** The same review found
   eight rules stated in the indicative that nothing enforces: PR line caps, WIP ≤2 per lane,
   merge-queue utilisation <70%, daily rebase, the orchestrator's ~5 concurrent decisions, the
   monthly kill-criterion check, the money/date re-derivation duty, and "every incident ends in a
   changed contract, test, monitor or runbook". Each either gets a named checker or moves here.
   (Finding 4.)
7. **Live-writer check on refuter dispatch, armed as a gate.** Today "confirm the generator is
   dead before dispatching the refuter" is a convention stated in the verification-economics
   section above, not something CI enforces. Until a checker exists (process-liveness in the
   worktree, plus hash-stability across a settling window), the dispatcher must do this by hand
   every time. (Raised by the 2026-08-24 GARUDA VOA contract-freeze incident.)
