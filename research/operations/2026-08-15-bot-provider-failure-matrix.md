---
date: 2026-08-18
domain: operations
client_case: "internal — BOT-V3 gate-prep for the Zantara WhatsApp ChatGPT Pro subscription provider"
discovered_by: "Codex orchestrator on Air-M5, resumed from the 2026-08-15 BOT-V lane and re-grounded against current main plus adapter head"
sources:
  - "origin/main at 993e4e868a6e8210328f69ccd136ca9d5c54d776, fetched 2026-08-18"
  - "PR #4216 adapter source head 6cc3c845c: Codex subscription adapter, offline harness, tests, CI, and ADR"
  - "PR #4216 ADR: research/operations/2026-08-15-adr-wa-runtime-openai-provider.md"
  - "PR #4301 branch agent/air-m5/ops/bot-corner-reconfirm-2026-08-18: research/operations/2026-08-18-bot-openai-shadow-wiring-plan.md"
  - "apps/backend-rag/backend/app/routers/whatsapp_chat.py"
  - "apps/backend-rag/backend/services/integrations/wa_outbox_worker.py"
  - "apps/backend-rag/backend/services/integrations/wa_inbox_bot.py"
  - "apps/backend-rag/backend/services/rag/agentic/llm_gateway.py"
  - "apps/backend-rag/backend/app/core/config.py"
  - "codex-cli 0.147.0 local exec help, measured 2026-08-18"
adversarial_review: >-
  Kimi K3 and Gemini 3.1 Pro reviewed the earlier failure-matrix rewrite;
  final adapter review is Kimi K3 SHIP plus Gemini 3.7 Flash High degraded
  fallback SHIP after Gemini 3.1 Pro FIX-FIRST; final Fable/Claude gate pending
---

# BOT-V3 — selected-provider failure matrix, idempotency, and rollback truth

## Executive verdict

The selected candidate is the ChatGPT Pro subscription adapter in
`codex_exec_client.py`, invoked through headless `codex exec`. It is **not** the dormant
`openai_responses_client.py` API-key client. The previous version of this document described the
dormant client's HTTP 401/429/5xx taxonomy as though it covered "the OpenAI shadow". It did not.

Current verdict: **offline evidence only; not ready for shadow wiring or client traffic**. The
adapter now has both a strong constructed-test baseline and one narrow, successful subscription
probe through its final argv. Ephemeral execution, rule isolation, generic communication errors,
role-aware history, sequential bench invocation, and repeated-cancellation reaping are closed for
the offline harness. Material boundaries remain: subscription quota classification, tool/RAG
parity, partial-output detection, stronger host-read isolation, benchmark-run idempotency, a
privacy-approved real corpus and blind score, and a production execution host.

## 0. Frozen evidence boundary

This report separates three kinds of evidence:

- **MEASURED** — observed from the installed CLI or current repository state in this session;
- **CONSTRUCTED** — proved by a deterministic test double or synthetic fixture, not observed from
  a real vendor failure;
- **UNMEASURED** — reasoned from code or named as a required probe; no passing claim is made.

The selected adapter evidence is frozen at PR #4216 source head `6cc3c845c`. Live-path evidence was
rechecked against current `origin/main` at `993e4e868a6e8210328f69ccd136ca9d5c54d776`.
`git diff HEAD..origin/main` was empty for all cited WhatsApp hot files before this revision.

No client data, WhatsApp export, secret, config change, runtime flag, deploy, merge, or outward
message was used to produce this report. PR #4216 declares seven synthetic, non-PII subscription
calls across its full development history; the final adapter probe is described narrowly below.

## 1. Provider tripartition — do not collapse these lanes

1. **Gemini — live primary.** The agentic RAG gateway uses a native system instruction, structured
   history, and Gemini function declarations. Its answer can reach the WhatsApp outbox.
2. **OpenRouter — committed fallback, gated OFF.** The gateway contains `_call_openrouter`, but
   `Settings.openrouter_enabled` defaults to `False`. It is not the selected migration route.
3. **Codex subscription — selected candidate, completely dormant.** `CodexExecClient` has no live
   importer, no setting, no gateway branch, and no worker branch. No runtime credential is
   represented in the repository or authorized by this lane; external Fly secret state was not
   inspected and remains UNMEASURED. The adapter accepts one prompt string and returns one text
   string. It is not a native tool-calling peer of the Gemini interface.

`openai_responses_client.py` is a fourth code artifact but not an armed provider lane: Zero ruled
that `OPENAI_WA_PROVIDER_API_KEY` will not be provisioned. Its HTTP matrix is historical evidence
for that dormant alternative only.

## 2. Failure matrix for `CodexExecClient`

| Failure or boundary | Frozen adapter behavior | Evidence | Required disposition before offline Stage 1 | Client-facing implication today |
| --- | --- | --- | --- | --- |
| Binary missing, path absent, non-executable, or auth file absent/empty | `available=False`; `generate()` raises `CodexExecUnavailableError` before spawn. Fresh isolated-home reproduction did **not** reproduce the historical Keychain inference: status was `Not logged in` and controlled exec attempts failed with HTTP 401 | CONSTRUCTED filesystem tests plus MEASURED isolated-home correction in ADR §30.4 | Keep fail-closed; bench reports `SKIPPED_UNAVAILABLE`, never a pass. File presence remains only a local gate proxy, not proof that a credential is live | None; there is no live caller |
| Binary disappears or becomes unusable after availability check | Launch `OSError` maps to sanitized `CodexExecUnavailableError` | CONSTRUCTED tests | Preserve mapping and prove no child/tempdir leak | None |
| Temp directory creation fails | Maps to sanitized `CodexExecUnavailableError` | CONSTRUCTED test | Preserve typed failure | None |
| Invalid model, prompt, or timeout | Positive model allowlist; empty prompt and non-finite/non-positive timeout rejected before spawn | CONSTRUCTED tests | Preserve the already-correct validation; style cleanup is not a Stage 1 gate | None |
| Auth material exists but token is revoked/expired | On non-zero exit, sanitized stderr is matched against auth-death phrases; match raises `CodexExecAuthError` without raw stderr | The real isolated-home `codex exec` HTTP-401 failure class and stable `Not logged in` status phrase are MEASURED. The stored stderr fixture and broader classifier vocabulary remain CONSTRUCTED | Preserve the measured/constructed distinction; do not promote the broader regex vocabulary into vendor-contract evidence | None; future path must page an operator and fail closed |
| ChatGPT Pro usage window / quota / seat throttle | No dedicated classifier. Unless vendor text accidentally matches auth vocabulary, it becomes generic `CodexExecProcessError(exit_code)` | UNMEASURED | Add a distinct sanitized quota/usage-window class only after measuring actual CLI output with Zero's authorization; abort replay, do not rotate seats silently | None; future shadow must never degrade Gemini or consume all O1/O2 capacity |
| Vendor account enforcement / suspension | The accepted subscription-automation ToS residual could present as auth death, quota, or a generic non-zero exit; the current classifier cannot distinguish a dead token from a disabled seat | UNMEASURED | Treat any ambiguous seat-wide failure as operator-only and stop the lane. Do not rotate accounts or relabel it as transient without evidence | None; future runtime suitability remains blocked |
| Sandbox, policy, approval, or inherited-rule rejection | Non-zero exit becomes generic process error; fixed argv now has `--sandbox read-only`, `--ignore-user-config`, and `--ignore-rules` | Flags MEASURED from CLI help and argv; failure wording and remaining coding-agent host-read surface are UNMEASURED | Rule-file inheritance is closed for the offline harness. Stronger OS/process isolation remains an independent human architecture gate before real client data | None |
| Prompt write / `communicate()` failure other than timeout/cancel | Child is killed/reaped, then a fixed-literal `CodexExecCommunicationError` is raised; raw exception type and text do not cross the boundary | CONSTRUCTED test | Closed for the offline harness; preserve the typed, sanitized mapping | None |
| Wall-clock timeout | Child killed and reaped; `CodexExecTimeoutError`; prompt/raw output excluded from message | CONSTRUCTED test | Preserve; offline runner uses a fixed timeout and records the typed class | None |
| Caller cancellation, including a second cancellation during cleanup | One stable shielded wait task finishes child reaping before the latest `CancelledError` propagates unchanged | CONSTRUCTED single- and repeated-cancel tests | Closed for the offline harness; preserve the stable wait-task invariant | None |
| Other non-zero exit | `CodexExecProcessError` carries numeric exit code only | CONSTRUCTED test | Preserve sanitization; extend matrix only after real failure samples exist | None |
| Exit zero with empty/whitespace stdout | `CodexExecOutputShapeError` | CONSTRUCTED tests | Preserve; bench counts as failed candidate, never empty success | None |
| Exit zero with truncated or partial non-empty text | Accepted as success; the current plain-text result carries no completion/truncation metadata | UNMEASURED and undetectable under the frozen adapter contract | `--output-schema` was evaluated and rejected for this purpose: it constrains answer shape but supplies neither completion metadata nor a reliable truncation signal. Score obvious truncation in the offline rubric and keep this boundary explicit | None |
| Model refusal or safety block expressed as prose | Returned as ordinary text; `CodexExecResult` has no refusal field | UNMEASURED | `--output-schema` does not expose provider refusal metadata. Classify by the offline rubric and do not pretend parity with Responses API refusal objects | None |
| Native function/tool call | Unsupported: the adapter has no tool-schema input or structured tool-call output | MEASURED from function signature and fixed argv | Stage 1 precomputes retrieval/tool results and evaluates final synthesis only; native tool parity is out of scope | None |
| Session transcript persistence | Fixed argv includes `--ephemeral`. The final adapter probe returned its synthetic sentinel exactly, kept observed session-file count at `3273 -> 3273`, and found no sentinel residue beneath the searched `~/.codex` tree | MEASURED narrow final-adapter probe plus CONSTRUCTED argv tests | Closed only for the exact searched surfaces and synthetic call; this is not universal non-persistence proof. Independent privacy review still gates real corpus use | None |
| Ambient repo/user context | Fresh empty cwd and `--ignore-user-config` are present; coding-agent tools still exist and read-only is not a no-tools contract | Fresh-cwd/hook behavior partly MEASURED in adapter ADR; host-read isolation UNMEASURED | Synthetic sentinel and hostile-prompt tests; no real client text until stronger OS isolation is independently approved | None |
| Secret/environment exposure | Child env is reduced to PATH/HOME/TERM/LANG/LC_ALL/TMPDIR plus CODEX_HOME; prompt goes through stdin, not argv/env | CONSTRUCTED tests | Preserve; test prompt absent from argv/env/logs; CODEX_HOME path itself must not enter result artifacts | None |
| Tempdir removal failure | `shutil.rmtree(..., ignore_errors=True)` hides cleanup failure | UNMEASURED | Add a cleanup-verification test or explicit sanitized diagnostic; offline runner must detect residue | None |
| Parallel calls / inbound burst | One subprocess per `generate()`; no semaphore in the client. The offline benchmark invokes candidates and fixtures sequentially, so observed harness concurrency is structurally one | MEASURED from the harness loop; runtime burst behavior remains UNMEASURED | Closed for the offline harness. Any future dispatcher needs its own bound, drop policy, and resource test | None |
| Retry/backoff | Client performs no retry | MEASURED from code | Correct for fail-closed offline evidence. Future retry policy belongs to a caller and requires idempotency/quota rules | None |

### Load-bearing conclusion

The adapter's current tests prove that many **constructed** process failures are sanitized and
cleaned up; the narrow final subscription probe additionally proves one successful invocation and
the searched persistence surfaces. They do not prove how Codex CLI reports a usage cap, a safety
rejection, or a partial completion in the real service, and the broader auth vocabulary remains
constructed. The gate must never convert a simulated stderr string into a claim about measured
vendor behavior.

## 3. Offline Stage 1 failure semantics

Stage 1 is the de-identified replay proposed in PR #4301 on branch
`agent/air-m5/ops/bot-corner-reconfirm-2026-08-18`, file
`research/operations/2026-08-18-bot-openai-shadow-wiring-plan.md`. That proposal is not yet on
this branch or `main`; the requirements below are repeated here so this document does not depend
on an unresolvable local path. PR #4216 now implements the role-aware corpus builder and sequential
subscription-backed blind-bench harness, but no real export was processed and no blind quality
score exists. It is not a live shadow branch.

The runner must:

1. use `CodexExecClient`, never infer the selected provider from a generic "OpenAI" label;
2. run only on an operator machine already authenticated to the declared ChatGPT Pro seat;
3. use `--ephemeral`, a fresh cwd, ignored user config/rules as validated, and concurrency 1 — all
   now enforced by the offline harness;
4. never retry auth, quota, policy, or unknown non-zero exits automatically;
5. record only the typed outcome, numeric exit code where already exposed, model, latency, and
   de-identified fixture ID — never raw stderr, auth paths, credentials, phone numbers, or source
   message IDs;
6. fail the entire run if no selected-provider call succeeds, if quota interrupts the registered
   sample, or if a session/prompt residue sentinel is found; the all-provider-failed case is
   implemented, while quota and run-level residue monitoring remain operational gates;
7. keep blind output and provider-label key separate with `0600` files in a `0700` run directory;
8. make `(run_id, fixture_id, provider, model)` the idempotency key.

There is no tool-call row to compare at this stage. Retrieval/tool outputs are precomputed by the
existing local RAG path and serialized into the prompt package. The result measures final synthesis
under that approximation only.

## 4. Idempotency of the real WhatsApp reply path

The provider candidate is not in this path, so these are current Gemini-path invariants a future
design must preserve rather than claims about Codex:

### Inbound deduplication — closed

`whatsapp_chat._handle_meta_inbox_message` inserts the inbound message with:

```sql
ON CONFLICT (meta_message_id) WHERE meta_message_id IS NOT NULL
    DO NOTHING
RETURNING id
```

Meta's `wamid` is the dedup key. A duplicate returns no new row and does not enqueue a second bot
reply.

### Worker lease, fence, and burst coalescing — closed for generation ownership

`wa_outbox_worker` uses a 300-second claim lease, renews it during generation, fences transitions
on `id + claim_token + status`, and marks other pending rows in the same thread
`superseded_by_coalescing`. A lost claimant cannot commit state after its fence is gone.

Generation failures back off from 30 seconds and stop after five attempts. The give-up row is
durable. Client apology/manners behavior is a separate default-OFF flag and must not be treated as
guaranteed delivery.

### Outbound Graph send — residual double-send window remains

After Meta accepts the irreversible send but before the ledger records `sent`, a crash can let a
reclaimer send again. The code logs `RESIDUAL DOUBLE-SEND WINDOW hit`; no reconciliation job closes
it. A provider migration neither creates nor cures this window. Any future serve-stage must state
it rather than claiming end-to-end exactly-once delivery.

### Offline replay idempotency — new, separate keyspace

The Stage 1 run never writes to `meta_inbox_messages`, `wa_outbox`, or any client-facing table. Its
target idempotency key is the local run key defined in §3. The current harness preserves a run's
blind-label recipe through its secret nonce/seed/candidate key file, but it does **not** yet enforce
the proposed `(run_id, fixture_id, provider, model)` key or publish output atomically. Its private
output files are truncated on reuse. Replaying fixtures must not manufacture larger sample counts
by duplicating rows; this remains an explicit gate rather than a passing claim.

### Live-path gaps and trip observables carried forward

This rewrite changes the candidate-provider matrix but must not erase verified baseline findings
from the previous revision:

- **Gemini 5xx/timeout alert gap remains open.** `LLMGateway` routes a provider exception through
  `_alert_quota_exhausted`, but `_classify_quota_exhaustion` returns no subtype unless it sees a
  429/`RESOURCE_EXHAUSTED`-shaped signal. A pure 5xx or timeout is re-raised into the worker's
  retry/give-up path without the dedicated CRITICAL quota alert. A future Codex serve-stage must
  not use "alerts fired" as its only trip signal or inherit this blind spot silently.
- **Current trip observables remain usable:** the deduplicated `gemini_quota_exhausted` CRITICAL
  alert for classified quota failures; exact `wa_outbox.error` families such as
  `bot_generate_failed_after_{N}_attempts` and `send_failed_after_{N}_attempts`; and the
  `RESIDUAL DOUBLE-SEND WINDOW hit` log line. `bot_standing_condition_after_{N}_attempts` must be
  excluded from provider-failure rates because it means the bot was disabled, not that generation
  crashed.
- **Historical findings are not current selected-provider gates:** the old malformed-tool
  comparison-log finding belonged to the discarded `_shadow_provider.py` design, and the
  4,096-character truncation history remains recorded in `.agents/skills/bot/SKILL.md`. Neither is
  silently promoted into evidence about `CodexExecClient`.

## 5. Rollback truth

There is currently nothing to roll back from:

- Gemini is the only unconditional live generation provider;
- OpenRouter is committed but default-OFF;
- `CodexExecClient` is absent from every live path;
- no Codex runtime credential is represented in the repo or authorized by this lane; actual Fly
  secret inventory was not inspected and remains UNMEASURED;
- no OpenAI/Codex runtime flag exists.

Therefore "rollback to Gemini is config-only" is not yet a valid production claim. It describes a
future architecture, not current state. Offline Stage 1 rollback is simply stopping the local
runner; it changes no runtime state.

A future shadow design requires a new, default-OFF flag and must prove that disabling it prevents
all subprocess dispatch without changing the Gemini answer. A future serve design needs another
flag/ADR/gate. Neither is authorized here, and the current NO-WIRING fence must be formally amended
before either file surface can exist.

## 6. Gates that remain open

- [x] #4216 reconciled with `origin/main` at `993e4e868` and held to its declared 11-file fence.
- [x] `--ephemeral` added and one narrow session/prompt-residue sentinel probe passed.
- [x] `--ignore-rules` added; inherited rules are excluded from the offline contract.
- [ ] Stronger coding-agent/host-read isolation independently approved before any real client text.
- [x] Generic communicate failures mapped to a sanitized typed error.
- [x] Controlled isolated-home `codex exec` measured the HTTP-401 class; only the broader auth
      vocabulary remains constructed.
- [ ] Subscription quota/usage-window behavior measured with Zero's authorization and quota budget.
- [x] Role-aware, multi-turn de-identified corpus tooling completed and fail-closed.
- [x] Bench path invokes the `CodexExecClient` facade by default without a paid API key.
- [x] Offline runner candidate/fixture calls are sequential, fixing harness concurrency at 1.
- [ ] Benchmark-run idempotency and crash-safe output publication proved.
- [x] Adapter diff reviewed by Kimi K3; Gemini 3.1 Pro FIX-FIRST findings were dispositioned and
      the degraded Gemini 3.7 Flash High fallback returned SHIP.
- [ ] Mandatory final Fable/Claude on-disk gate.
- [x] #4194 threat/privacy addendum reconciled to source head `6cc3c845c`; its independent Kimi K3
      FIX-FIRST wording findings were corrected. The mandatory Fable/Claude gate remains open.
- [ ] No config, gateway, worker, secret, live traffic, merge, or deploy until a separate mandate.

## R28 reconciliation proof

The PR #4216 source head named above was rechecked from its isolated worktree. One combined,
addopts-free pytest process collected and passed **482 tests**: 71 subscription-adapter tests, 163
dormant Responses-adapter tests, and 248 corpus/benchmark tests. Targeted Ruff `F,I`, workflow YAML
parsing, Prettier, and `git diff --check` also passed. The two co-located offline harness test files
are now explicit arguments in `.github/workflows/tests.yml`; CI runs those deterministic tests but
does not execute a provider call, ingest an export, or perform human scoring.

After Kimi K3 found that the adapter docstring could be read as runtime authorization, source head
`6cc3c845c` narrowed it to the intended future credential-path choice plus the current human-run
offline evidence boundary. The focused 71-test adapter suite and Ruff check passed again after that
documentation-only correction.

## Adversarial review

Kimi K3 reviewed the source-grounded diff, initially returned `FIX-FIRST`, and required the
rewrite to preserve the live Gemini pure-5xx/timeout alert gap and exact trip observables. It also
required the cross-branch Stage 1 plan to be self-contained here, Fly secret state to remain
`UNMEASURED`, the Keychain caveat and vendor-enforcement boundary to be explicit, and
`--output-schema` to remain a probe rather than a promised solution. Those findings were accepted.

Gemini 3.1 Pro then reviewed an inline, read-only evidence bundle and caught a remaining evidence
compression in the auth row. The classifier is constructed; only the `Not logged in` phrase was
measured through `codex login status`; the remaining vocabulary and a real failed `codex exec`
shape are unmeasured. The row now states exactly that distinction. An earlier Gemini attempt that
mutated the file was discarded and does not count as review evidence.

That review applied to the earlier failure-matrix rewrite. The final adapter review subsequently
returned **Kimi K3 — SHIP** and **Gemini 3.1 Pro — FIX-FIRST**. Two real findings were closed:
repeated cancellation can no longer interrupt child reaping, and the co-located offline harness
tests are now named explicitly in the backend PR CI job. A focused Gemini 3.1 Pro re-review timed
out without a verdict; the declared continuity fallback, Gemini 3.7 Flash High, re-read those fixes
and returned **SHIP with `degraded_execution: true`**. The mandatory final Fable/Claude on-disk
gate remains pending. No reviewer authorized live traffic, credentials, config, gateway or worker
wiring, merge, deploy, or cutover.
