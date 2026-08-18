---
date: 2026-08-18
domain: operations
client_case: zantara-wa-provider
discovered_by: "Fable/Sonnet session (M5), corrected after independent Kimi K3 and Gemini 3.1 Pro red-team review"
sources:
  - "memory: decision_wa_openai_provider_subscription_path_owner_ruling_2026_08_15 (owner ruling: ChatGPT Pro subscription via codex exec, never OPENAI_WA_PROVIDER_API_KEY)"
  - "memory: project_bot_openai_lane_governance_codex_orchestrator_2026_08_15 (NO-WIRING fence and close-gate sequence)"
  - "PR #4216 head 6cb663dd66c67ed8d84dc204508eafe3c6d0c5de, merged as 67eb3be94cb9be9abaae00b372446389e971cf4f, and its 12-file net diff, re-verified live on Air-M5 and Pro"
  - "PR #4194 threat model at head 28f70f026, read this turn"
  - "PR #4197 failure matrix, read this turn"
  - ".agents/skills/bot/SKILL.md, live-state entry dated 2026-08-19"
  - "codex-cli 0.147.0 local help for exec --ephemeral, --ignore-user-config, --ignore-rules, and sandbox controls, measured 2026-08-18"
adversarial_review: kimi-k3
review_corroboration: "gemini-3.1-pro"
---

# BOT-V — OpenAI provider: offline evidence before any shadow wiring

## Live reconciliation — 2026-08-19 (authoritative)

This section supersedes stale implementation-state statements later in this document. The safety
and architecture boundaries remain in force, but #4216 advanced materially after the original
plan and was re-measured from its exact current head.

- Zero authorized the start of live testing on 2026-08-18. Source: memory
  `decision_wa_openai_provider_subscription_path_owner_ruling_2026_08_15`, §2026-08-18 riconferma
  ("la rotta abbonamento è confermata e il DRAFT HOLD è sciolto sulla ROTTA — la lane avanza");
  the label "point 7" used by earlier drafts was that session's own checklist numbering and
  resolves to nothing in this document. That closes the missing-owner-authorization gate for the
  gated merge/deploy progression; it does not waive generator-not-grader review, privacy, PII,
  runtime-host, rollback, or no-outward-send gates, and it authorizes no cutover.
- #4216 remains inert and NO-WIRING at source head
  `6cb663dd66c67ed8d84dc204508eafe3c6d0c5de`. Independent Fable review re-ran the 513 focused
  tests, confirmed the 12-file fence and zero runtime importers, returned PASS, moved the PR from
  draft to ready, and armed the canonical merge queue.
- The first two merge groups were rejected by the same runner-infrastructure signature.
  Merge-group `ca65adfef0ef86f502b5fcd186dc1f3e76676059` failed run `32157479924` at the required
  `Immune enforcement` step `Codex seat corpus` after 71 seconds; after an independent
  PASS-REQUEUED verdict, merge-group `8b8d233e3da9c6e000aab36a0a1c04e5521776e0` failed the
  same step in run `32159641457` after 79 seconds. Both logs contained no command output between
  step start and exit 1: the bounded `apt_install.sh zsh zsh` could not deliver `zsh`, so neither
  pytest corpus started. The same step passed on the PR run, the four affected CI/helper/test
  files were byte-identical across PR, merge-group, and `main`, and local re-runs passed 13/13,
  14/14, and 56/56. This was an apt-mirror failure, not an adapter regression.
- A read-only rerun of only that failed workflow then passed in 5m59s: `apt update` timed out, the
  cached install still delivered `/usr/bin/zsh`, and the real 14-test and 56-test corpora passed.
  Independent Fable issued `PASS-REQUEUED-FINAL` and requeued once under an explicit terminal
  anti-loop rule. Final merge-group `67eb3be94cb9be9abaae00b372446389e971cf4f` completed all
  26/26 workflows successfully, including the previously failing immune gate, full backend,
  frontend, E2E, security, and secret scans. GitHub merged #4216 at `2026-08-18T17:26:10Z`, and
  `origin/main` was independently observed at that exact merge commit.
- CI workflow `32165589346` deployed that exact commit successfully: pre-deploy validation and
  82 core tests passed; pre/post SQL and Python migrations passed; the Fly rolling deploy passed
  in 6m22s; the workflow health and synthetic RAG smoke tests passed without rollback. A separate
  post-workflow probe returned `HTTP 200` and `{"status":"healthy"}` from
  `https://nuzantara-rag.fly.dev/health`. The merged adapter file is present, while a commit-pinned
  grep found no runtime importer, config flag, or gateway reference outside the two dormant
  adapter modules and their tests. Deployment therefore changed code availability only; it did
  not activate a provider or attach to WhatsApp traffic.
- The selected blind-bench client is now `CodexSubscriptionBenchClient`, a narrow facade over
  `CodexExecClient`. It never checks `OPENAI_WA_PROVIDER_API_KEY`, and candidate calls are strictly
  sequential.
- The corpus builder now defaults to role-aware, multi-turn JSONL, requires canonical roles and a
  local-only conversation identifier, and emits user targets with at most 12 independently scanned
  prior turns. Its two fail-closed mechanisms are distinct and both remain in force: an unsafe
  turn drops the whole conversation fixture (the §3.2 rule and §4 gate below, unchanged), and an
  unattributable turn clears the accumulated history before any later turn can inherit it. Legacy
  role-blind output is opt-in and rejected by the promotion bench.
- The fixed CLI argv now includes both `--ephemeral` and `--ignore-rules`. On Pro, 513 focused
  adapter/pricing/corpus/bench tests passed from the exact PR head.
- A synthetic Terra sentinel passed through the real adapter in 6.9 seconds. A second role-aware
  multi-turn bench produced three successful sequential responses: Terra 8.6 seconds, Luna
  6.6 seconds, and Sol 6.7 seconds; all three returned the exact synthetic token from history.
  The run used no WhatsApp, Meta, CRM, database, Qdrant, client, or OSINT input.
- Across the measured runs: no API-key variable reached the child, no Codex session file changed,
  no sentinel appeared in the observed session surfaces, no adapter temp directory or child
  remained, and all ephemeral fixture/transcript/key artifacts were owner-only (`0600`) and
  deleted after inspection.
- A non-login SSH/LaunchAgent environment on Pro may omit `/opt/homebrew/bin`. Because
  `/opt/homebrew/bin/codex` is a Node shebang script, a future supervisor must set an explicit
  executable search path including Homebrew; setting `WA_CODEX_BIN` alone is insufficient when
  `/usr/bin/env` cannot resolve `node`.
- The CLI's private `stderr` pipe contains a human-readable transcript that echoes the prompt.
  The adapter drains that pipe in memory to avoid deadlock but, on success, does not log, persist,
  return, or scan it. On a non-zero exit the adapter DOES scan that stderr — only after
  whole-line stripping of the echoed prompt, and it surfaces only sanitized typed errors, never
  the raw pipe (the adapter's module docstring records the full evolution of that rule).
  Therefore the original literal requirement that the prompt never occur in
  raw `stderr` is impossible for codex-cli 0.147.0 and is replaced by the narrower mechanical
  requirement below: no prompt in argv, environment, adapter logs, surfaced diagnostics,
  exceptions, or persisted files. This is sufficient only for synthetic testing, not client PII.
- The authenticated seat is a personal ChatGPT Pro account. OpenAI's published policy says Pro
  Codex conversations may be used to improve models unless the account-level ChatGPT training
  control is disabled. That exact account setting has not been verified. Real client text, PII,
  WA-mirror data, live shadowing, Fly credential placement, serving, activation, and cutover
  remain **NO-GO** until that privacy gate and a named Pro-side broker/supervisor design pass
  independent review. The now-completed CI-green merge/deploy of the dormant NO-WIRING files did
  not activate the provider and remains separate from any future serving gate.

## 0. Decision and authority boundary

The provider route is an owner decision, not an open architecture vote:

- the candidate is `codex_exec_client.py`;
- it uses an already-authenticated ChatGPT Pro subscription through headless
  `codex exec`;
- `OPENAI_WA_PROVIDER_API_KEY` will not be provisioned;
- the sibling `openai_responses_client.py` remains a dormant, unwired alternative and is not the
  candidate this plan evaluates.

The original version of this document did **not** authorize a runtime flag, a gateway branch, a
credential move, live WhatsApp traffic, a deploy, a cutover, or a merge. Zero later supplied the
2026-08-18 owner authorization recorded in the live reconciliation above. The independently reviewed
dormant merge and CI deploy are now complete, but the #4216 diff itself remains NO-WIRING, and the
technical/privacy gates still determine which later action is safe to execute. Stage 1 remains an
operator-run, de-identified, offline evaluation. It is deliberately not called "shadow" because
it does not observe or attach to the live reply path.

The [official Codex authentication documentation](https://learn.chatgpt.com/docs/auth) confirms
that the CLI supports both ChatGPT subscription sign-in and API-key sign-in. That establishes that
the selected local invocation route exists; it does **not** by itself establish that an interactive
subscription is suitable for an unattended WhatsApp production runtime. The owner has accepted
the residual route risk, while the technical, privacy, quota, and runtime-host gates below remain
open.

## 1. Original pre-R28 measured state (historical)

The numbered observations below explain why the plan was narrowed. They are retained as review
history; where they conflict with **Live reconciliation — 2026-08-19**, the reconciliation is the
authoritative current state.

1. **#4216 is inert.** Its selected adapter is standalone and has no live importers, config field,
   gateway branch, secret, cron, or deploy. It is still draft and conflicts with current `main`.
2. **The existing blind bench targets the wrong provider.** `scripts/bot/wa_blind_bench.py`
   imports `OpenAIResponsesClient`, checks `OPENAI_WA_PROVIDER_API_KEY`, and calls the dormant
   Responses API lane. It does not exercise `CodexExecClient`.
3. **The corpus is V5 INCOMPLETE.** The #4216 ADR states that the builder is synthetic-only,
   role-blind, and single-turn. The live bot can send up to 12 prior turns. Current fixtures cannot
   prove history parity, role behavior, or context-contamination resistance.
4. **#4197 covers the wrong failure boundary.** Its rows describe HTTP/API-key failures for
   `openai_responses_client.py`; it has no process-shaped coverage for the selected adapter.
5. **The selected adapter is text-in/text-out.** `CodexExecClient.generate()` accepts one prompt
   string plus model/timeout controls. It has no native system-instruction channel, structured
   message array, or function-schema channel. The live Gemini gateway has all three. Therefore
   literal provider parity is structurally unavailable through this adapter.
6. **The production host is not a Codex host.** The live backend is a Fly container; the current
   image does not install or authenticate the Codex CLI. Copying an operator's ChatGPT credential
   into Fly would be a new security and account-identity decision, not an implementation detail.
7. **At-rest behavior needs a correction.** Local `codex exec --help` on CLI 0.147.0 exposes
   `--ephemeral` (no session-file persistence), but the frozen #4216 argv does not pass it. Until
   that is fixed and mechanically tested, even offline prompts may be retained under
   `CODEX_HOME`.
8. **`read-only` is not a no-tools contract.** A Codex coding-agent invocation can still attempt
   read operations or other agentic actions. A fresh cwd and `--ignore-user-config` reduce ambient
   context, but do not prove host-file isolation or disable the model's coding-agent persona.

The consequence is precise: #4216 contains useful provider-boundary work, but the existing corpus
and bench cannot yet produce decision-grade evidence for the selected route.

## 2. Corrections to the first draft

The first draft made one false sufficiency claim: it said the existing offline artifacts could
validate context parity, tool-calling shape, and #4197's failure rows. Independent Kimi K3 and
Gemini 3.1 Pro reviews both rejected that claim. It is removed.

Stage 1 can measure only this narrower proposition:

> On role-aware, multi-turn, fully de-identified fixtures, how does the selected text-in/text-out
> `codex exec` adapter perform when given a deterministic serialized context package, compared
> with the current Gemini answer for the same offline fixture?

It cannot prove native tool-call equivalence, system-message priority equivalence, live dispatch
behavior, latency under inbound bursts, subscription availability at WhatsApp scale, or production
host suitability. Those are separate gates, not conclusions to infer from answer quality.

## 3. Minimal defensible Stage 1 — offline evaluation only

Stage 1 may begin only after all prerequisites below exist on one frozen branch and pass review.

### 3.1 Provider-specific bench

Adapt the existing blind-bench machinery rather than rebuilding its safety controls, but add an
explicit `codex-exec` candidate path that:

- instantiates `CodexExecClient`, never `OpenAIResponsesClient`;
- gates on `CodexExecClient.available`, never an API-key environment variable;
- passes fixture text through stdin, never argv or an environment variable;
- preserves blind labels and the separate `0600` label key;
- records typed process outcomes without persisting raw stderr;
- runs with concurrency `1` initially; no fan-out, queue, daemon, or live dispatcher;
- exits non-zero if every candidate call failed or if no selected-provider call ran.

The Responses API bench may remain as an explicitly dormant alternative, but its result must never
be labelled as evidence for the subscription provider.

### 3.2 Role-aware, multi-turn, de-identified corpus

Upgrade the corpus contract before benchmarking:

- every fixture declares the audience role (`client` or `team`) and language;
- multi-turn fixtures preserve ordered roles and contain the current turn plus prior turns, up to
  the live ceiling of 12;
- every turn passes the existing fail-closed de-identification and residual-PII scan;
- if any turn is unsafe, the whole conversation fixture is dropped;
- source ordering, contact identifiers, message IDs, timestamps, filenames, and export paths are
  not written to the fixture;
- only synthetic fixtures are used until a separate human privacy decision authorizes processing
  a real export locally on the Pro. Raw WhatsApp/OSINT data never moves to Air-M5 or cloud prompts.

### 3.3 Serialized-context approximation, not parity

For each fixture, build one deterministic prompt package with explicit delimiters for:

1. the frozen Zantara system instructions relevant to the test;
2. ordered conversation turns with roles;
3. deterministic retrieval/tool results prepared by the existing local RAG code;
4. the current user turn;
5. a strict final-answer-only instruction.

This is an **approximation**. It does not recreate Gemini's native system priority or function
calling. Stage 1 evaluates final synthesis after tool/retrieval outputs are precomputed; it does not
claim that Codex can autonomously choose or execute the same tools. The prompt-package hash is
recorded so both candidates can be proven to have received the intended offline fixture package,
but the word "parity" is reserved for native-equivalent interfaces and is not used here.

### 3.4 Operator-controlled execution host

Run Stage 1 only on an operator-controlled machine already authenticated to the chosen ChatGPT Pro
seat (Air-M5 or Pro), never in Fly and never by copying auth material to another host. The run
manifest must name:

- machine and CLI version;
- selected account/seat identifier without including credentials;
- model and timeout;
- fixture-set hash and prompt-package version;
- start/end time and attempted/succeeded/typed-failure counts;
- a predeclared maximum number of subscription calls.

The quota budget must be small enough not to starve the O1/O2 builder/refuter lanes. A quota or
usage-window response aborts the run; it is not silently retried across accounts.

### 3.5 No session persistence and no ambient host access assumption

Before corpus replay, amend and test the selected adapter so its fixed argv includes
`--ephemeral`. Also evaluate the current CLI's `--ignore-rules` control and add it if it closes an
otherwise inherited policy surface without breaking authentication.
_(Done at the merged head: the fixed argv now includes both `--ephemeral` and `--ignore-rules` —
see the live reconciliation above. The gate requirements below remain in force for any future
change to the argv or the CLI version.)_

The gate must run a synthetic sentinel probe and prove:

- no new Codex session/rollout file is created for the invocation;
- no prompt text appears in argv, environment, adapter logs, surfaced diagnostics, exceptions, or
  persisted files; the codex-cli 0.147.0 raw private `stderr` pipe is explicitly allowed to carry
  its transient transcript only while the adapter drains it in memory;
- user and repo hooks do not run;
- the model cannot use the empty working directory to recover repository context;
- cancellation and timeout still reap the child and remove the per-call temp directory.

This does not make Codex a generic no-tools API. Therefore Stage 1 contains de-identified synthetic
content only, and any future client-text use remains blocked pending a stronger OS-level isolation
design and privacy review.

### 3.6 Ephemeral comparison artifacts

Stage 1 writes outside git to a newly created `0700` run directory. Files are `0600` and contain
de-identified fixtures only. The manifest/sink schema is:

- `run_id`, `fixture_set_hash`, `fixture_id`, `role`, `language`;
- `provider`, `model`, `prompt_package_hash`;
- `started_at`, `latency_ms`, `outcome_class`;
- blind `variant_label`, de-identified response text, refusal/abstain marker;
- explicit `native_tool_trace: unavailable` for the Codex lane;
- no phone, contact, source message ID, raw stderr, auth path, export path, or credential field.

`(run_id, fixture_id, provider, model)` is the idempotency key. Replaying the same run must not
double-count results. Retention and deletion are operator actions after the blind review; nothing
is committed, uploaded, or sent to a client-facing system.

## 4. Acceptance matrix for Stage 1

| Gate | Mechanical evidence | Pass condition |
| --- | --- | --- |
| Correct provider | Import/call-site scan plus test double at the subprocess boundary | Every selected-lane candidate invokes `CodexExecClient`; zero selected-lane API-key checks |
| No wiring | Net diff against `main` | No change to config, gateway, routers, workers, Fly/Vercel, secrets, cron, outbox, or webhook code |
| Corpus shape | Corpus schema tests | Role required; ordered multi-turn fixtures supported through 12 prior turns; whole-fixture drop on unsafe turn |
| De-identification | Guilt and innocence fixtures | Every known PII-shaped fixture drops or redacts; legitimate monetary/legal numbers survive only under existing explicit rules |
| Ephemeral CLI | Before/after filesystem snapshot around a synthetic sentinel | Zero new session/rollout files and zero sentinel hits outside the declared run directory |
| Ambient isolation | Synthetic hook/rule/context probes | No hooks; no inherited repo persona; no undeclared host-file content in output |
| Process failures | Updated #4197 plus tests | Binary absent, auth absent/dead, sandbox/rule rejection, timeout, cancellation, malformed/empty stdout, quota exhaustion, and non-zero exit all map to typed fail-closed outcomes |
| Resource bound | Burst test against the offline runner | Maximum one child at a time; no orphan after cancellation/timeout; bounded queue is unnecessary because Stage 1 has no live ingress |
| Blindness | Transcript/key separation test | Transcript cannot reveal provider/model mapping; key remains `0600` and separate |
| Idempotency | Same-run replay test | No duplicate result rows for the idempotency key |
| Scoring | Pre-registered rubric before labels are opened | Accuracy/grounding, abstain appropriateness, language, citation discipline, price discipline, and unsafe-fabrication scored per role/language stratum |
| Independent verdict | Frozen-diff review | Kimi K3 adversarial review plus Gemini constructive review; findings dispositioned before any PR is readied |

The exact fixture count and pass threshold must be registered **before** responses are generated,
after the upgraded corpus inventory is known. It must include every role/language stratum with
enough fixtures to prevent a single example from deciding a verdict. A run that hits quota, skips
the selected provider, changes the rubric after unblinding, or lacks a stratum is invalid rather
than a partial pass.

## 5. #4197 and #4194 must be aligned before Stage 1 is called complete

### #4197 — selected-provider failure matrix

Replace the claim that HTTP/API-key rows cover "the OpenAI shadow" with two explicitly separated
surfaces: dormant Responses API and selected Codex subprocess. The selected-provider matrix must
cover at least:

- binary/path disappearance and version drift;
- auth file absent, empty, malformed, revoked, or expired;
- subscription quota/usage-window exhaustion;
- prompt stdin/write failure;
- sandbox, inherited-rule, and policy rejection;
- timeout and external cancellation;
- non-zero exit with sanitized diagnostics;
- empty/malformed stdout and answer-shape rejection;
- child reaping, tempdir cleanup, and ephemeral-session proof;
- host resource exhaustion and bounded offline concurrency;
- rerun/idempotency behavior.

Every row distinguishes `measured`, `constructed test`, and `unmeasured`. No constructed stderr
fixture may be described as measured vendor behavior.

### #4194 — freeze threat-model review

Re-run the threat model against the reconciled final adapter head, not its earlier commits. Add the
new at-rest/session, coding-agent tool surface, operator-host, account-quota, and credential-move
findings. A passing security review of a dormant HTTP client does not transfer to the subprocess
provider.

## 6. What remains blocked after Stage 1

Even a fully green Stage 1 — and what has actually passed so far is only the synthetic liveness
smoke recorded above, not the full Stage 1 evaluation with its §4 acceptance matrix — does not by
itself authorize live shadowing or serving. Zero's 2026-08-18 authorization permits progression
only as each remaining gate turns green:

- no runtime flag may land under the current NO-WIRING fence;
- no production host for a subscription-backed provider has been approved;
- no operator credential may be copied to Fly;
- no live WhatsApp/WA-mirror/client text may be sent to Codex;
- no comparison sink for PII-derived content has been approved;
- no native system/tool/history parity exists in `CodexExecClient`;
- no subscription capacity/SLA has been demonstrated for client traffic;
- the dormant merge and CI deploy completed only after their review, CI, and rollback gates were
  green; no runtime activation, cutover, fallback, live shadow, or outward publication is safe
  before its separate privacy/runtime-host/review gate is green, and Legge 5 continues to prohibit
  any client-facing test send.

A future live-shadow proposal needs a new owner mandate that formally amends the fence, a new ADR,
a named execution/broker architecture, a lawful PII basis, bounded concurrency/backpressure, a
precise dispatch point relative to cache/coalescing/abstain gates, a sampling-bias analysis, and a
separate comparison-sink security review. A future serve-stage needs another independent decision
and its own flag. Neither is part of this document.

## Adversarial review

### Kimi K3 — FIX-FIRST

The independent review verified the route and the adapter's zero-wiring/fail-closed claims, but
rejected the first draft's central sufficiency sentence. Surviving findings:

1. the existing blind bench is API-key/Responses-specific and cannot evaluate the selected client;
2. the V5-INCOMPLETE corpus cannot establish role, history, or tool behavior;
3. native context/tool parity is structurally unavailable through the current one-string contract;
4. the Fly execution host and credential-placement question was absent;
5. Codex session persistence and comparison-sink retention were unexamined;
6. the live dispatch point, sample bias, account quota, and concurrency limits were unspecified;
7. #4197 contradictorily claimed coverage while documenting only the dormant HTTP client;
8. a formal fence amendment is mandatory before any runtime flag exists.

Disposition: accepted. The plan now stops at offline evidence, names the approximation honestly,
adds provider-specific corpus/bench/failure requirements, mandates ephemeral execution, and defers
all wiring.

### Gemini 3.1 Pro — BLOCKED before Stage 1

The independent cross-family review corroborated the wrong-provider bench, wrong-boundary failure
matrix, and single-turn corpus blockers. It required all three to be corrected before Stage 1 can
produce valid evidence. Disposition: accepted and encoded in §§3–5.

### Claims both reviews did not overturn

- `openrouter_enabled` is default-off on current `main`;
- #4216's selected client remains unimported and unwired;
- the adapter uses stdin, a fresh per-call cwd, typed errors, cancellation reaping, and sanitized
  diagnostics;
- #4197 currently covers only the dormant HTTP provider;
- there is no current OpenAI runtime path to roll back from;
- the owner route remains ChatGPT Pro subscription via `codex exec`, never the paid API-key lane.

The historical reviewed verdict was **PROCEED ONLY WITH THE PREREQUISITES FOR OFFLINE STAGE 1**.
Those tooling prerequisites and a synthetic liveness smoke have now passed as recorded in the live
reconciliation. This is still not approval for client-data replay or shadow wiring: account-level
training controls, the Pro-side broker/supervisor boundary, fail-off dispatch, and independent
review remain open.
