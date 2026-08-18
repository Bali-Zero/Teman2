---
date: 2026-08-18
domain: operations
client_case: "internal — BOT-V3 gate-prep for the Zantara WhatsApp ChatGPT Pro subscription provider"
discovered_by: "Codex orchestrator on Air-M5, resumed from the 2026-08-15 BOT-V lane and re-grounded against current main plus adapter head"
sources:
  - "origin/main at 993e4e868a6e8210328f69ccd136ca9d5c54d776, fetched 2026-08-18"
  - "PR #4216 adapter head b7b2d6652: apps/backend-rag/backend/llm/codex_exec_client.py and tests"
  - "PR #4216 ADR: research/operations/2026-08-15-adr-wa-runtime-openai-provider.md"
  - "PR #4301 branch agent/air-m5/ops/bot-corner-reconfirm-2026-08-18: research/operations/2026-08-18-bot-openai-shadow-wiring-plan.md"
  - "apps/backend-rag/backend/app/routers/whatsapp_chat.py"
  - "apps/backend-rag/backend/services/integrations/wa_outbox_worker.py"
  - "apps/backend-rag/backend/services/integrations/wa_inbox_bot.py"
  - "apps/backend-rag/backend/services/rag/agentic/llm_gateway.py"
  - "apps/backend-rag/backend/app/core/config.py"
  - "codex-cli 0.147.0 local exec help, measured 2026-08-18"
adversarial_review: kimi-k3
---

# BOT-V3 — selected-provider failure matrix, idempotency, and rollback truth

## Executive verdict

The selected candidate is the ChatGPT Pro subscription adapter in
`codex_exec_client.py`, invoked through headless `codex exec`. It is **not** the dormant
`openai_responses_client.py` API-key client. The previous version of this document described the
dormant client's HTTP 401/429/5xx taxonomy as though it covered "the OpenAI shadow". It did not.

Current verdict: **offline evidence only; not ready for shadow wiring or client traffic**. The
adapter has a strong constructed-test baseline around subprocess lifecycle and sanitized failures,
but material boundaries remain unmeasured or unimplemented: subscription quota classification,
ephemeral session proof, inherited rule/tool isolation, partial-output detection, generic stdin
communication errors, concurrency/backpressure, and a production execution host.

## 0. Frozen evidence boundary

This report separates three kinds of evidence:

- **MEASURED** — observed from the installed CLI or current repository state in this session;
- **CONSTRUCTED** — proved by a deterministic test double or synthetic fixture, not observed from
  a real vendor failure;
- **UNMEASURED** — reasoned from code or named as a required probe; no passing claim is made.

The selected adapter evidence is frozen at PR #4216 head `b7b2d6652`. Live-path evidence was
rechecked against current `origin/main` at `993e4e868a6e8210328f69ccd136ca9d5c54d776`.
`git diff HEAD..origin/main` was empty for all cited WhatsApp hot files before this revision.

No client data, WhatsApp export, secret, provider call, config change, runtime flag, deploy, merge,
or outward message was used to produce this report.

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
| Binary missing, path absent, non-executable, or auth file absent/empty | `available=False`; `generate()` raises `CodexExecUnavailableError` before spawn. The ADR also measured that macOS Keychain auth may let the CLI authenticate even when an isolated `CODEX_HOME` lacks `auth.json`, so this gate is deliberately over-strict and is not equivalent to real credential state | CONSTRUCTED filesystem tests plus MEASURED Keychain caveat in ADR §30.4 | Keep fail-closed; bench must report `SKIPPED_UNAVAILABLE`, never a pass. Record that file presence is only a local gate proxy | None; there is no live caller |
| Binary disappears or becomes unusable after availability check | Launch `OSError` maps to sanitized `CodexExecUnavailableError` | CONSTRUCTED tests | Preserve mapping and prove no child/tempdir leak | None |
| Temp directory creation fails | Maps to sanitized `CodexExecUnavailableError` | CONSTRUCTED test | Preserve typed failure | None |
| Invalid model, prompt, or timeout | Positive model allowlist; empty prompt and non-finite/non-positive timeout rejected before spawn | CONSTRUCTED tests | Preserve the already-correct validation; style cleanup is not a Stage 1 gate | None |
| Auth material exists but token is revoked/expired | On non-zero exit, sanitized stderr is matched against auth-death phrases; match raises `CodexExecAuthError` without raw stderr | Classifier behavior is CONSTRUCTED. Only `not logged in` was MEASURED through `codex login status`; the remaining vocabulary plus the wording and exit shape of a real failed `codex exec` are UNMEASURED | Measure an actual controlled `codex exec` auth-death or use a documented real incident; record CLI version; do not treat the status-command vocabulary as proof of the exec-command failure shape | None; future path must page an operator and fail closed |
| ChatGPT Pro usage window / quota / seat throttle | No dedicated classifier. Unless vendor text accidentally matches auth vocabulary, it becomes generic `CodexExecProcessError(exit_code)` | UNMEASURED | Add a distinct sanitized quota/usage-window class only after measuring actual CLI output with Zero's authorization; abort replay, do not rotate seats silently | None; future shadow must never degrade Gemini or consume all O1/O2 capacity |
| Vendor account enforcement / suspension | The accepted subscription-automation ToS residual could present as auth death, quota, or a generic non-zero exit; the current classifier cannot distinguish a dead token from a disabled seat | UNMEASURED | Treat any ambiguous seat-wide failure as operator-only and stop the lane. Do not rotate accounts or relabel it as transient without evidence | None; future runtime suitability remains blocked |
| Sandbox, policy, approval, or inherited-rule rejection | Non-zero exit becomes generic process error; argv has `--sandbox read-only` and `--ignore-user-config`, but not `--ignore-rules` | Partly MEASURED from CLI help; failure wording UNMEASURED | Evaluate `--ignore-rules`; add if safe. Build guilt/innocence probes for hooks/rules and agentic host reads | None |
| Prompt write / `communicate()` failure other than timeout/cancel | Child is killed/reaped, then the original arbitrary exception is re-raised | CONSTRUCTED test | Add a sanitized typed communication error; no raw OS/provider exception should escape a provider boundary | None |
| Wall-clock timeout | Child killed and reaped; `CodexExecTimeoutError`; prompt/raw output excluded from message | CONSTRUCTED test | Preserve; offline runner uses a fixed timeout and records the typed class | None |
| Caller cancellation | Child killed/reaped; `CancelledError` propagates unchanged | CONSTRUCTED test | Preserve; prove tempdir cleanup after real task cancellation | None |
| Other non-zero exit | `CodexExecProcessError` carries numeric exit code only | CONSTRUCTED test | Preserve sanitization; extend matrix only after real failure samples exist | None |
| Exit zero with empty/whitespace stdout | `CodexExecOutputShapeError` | CONSTRUCTED tests | Preserve; bench counts as failed candidate, never empty success | None |
| Exit zero with truncated or partial non-empty text | Accepted as success; the current plain-text result carries no completion/truncation metadata | UNMEASURED and undetectable under the frozen adapter contract | Evaluate CLI 0.147.0's `--output-schema` as a candidate shape constraint, but do not assume it supplies completion metadata. Adopt or reject it by probe; score obvious truncation in the offline rubric | None |
| Model refusal or safety block expressed as prose | Returned as ordinary text; `CodexExecResult` has no refusal field | UNMEASURED | Evaluate whether `--output-schema` can expose a stable refusal field without weakening isolation; otherwise classify by the offline rubric. Do not pretend parity with Responses API refusal objects | None |
| Native function/tool call | Unsupported: the adapter has no tool-schema input or structured tool-call output | MEASURED from function signature and fixed argv | Stage 1 precomputes retrieval/tool results and evaluates final synthesis only; native tool parity is out of scope | None |
| Session transcript persistence | Frozen argv omits `--ephemeral`; CLI 0.147.0 help explicitly offers it | MEASURED argv/help mismatch; actual filesystem residue not yet probed | Add `--ephemeral`; sentinel before/after filesystem test must show zero new rollout/session file and zero prompt residue | None; blocks any replay beyond synthetic de-identified text |
| Ambient repo/user context | Fresh empty cwd and `--ignore-user-config` are present; coding-agent tools still exist and read-only is not a no-tools contract | Fresh-cwd/hook behavior partly MEASURED in adapter ADR; host-read isolation UNMEASURED | Synthetic sentinel and hostile-prompt tests; no real client text until stronger OS isolation is independently approved | None |
| Secret/environment exposure | Child env is reduced to PATH/HOME/TERM/LANG/LC_ALL/TMPDIR plus CODEX_HOME; prompt goes through stdin, not argv/env | CONSTRUCTED tests | Preserve; test prompt absent from argv/env/logs; CODEX_HOME path itself must not enter result artifacts | None |
| Tempdir removal failure | `shutil.rmtree(..., ignore_errors=True)` hides cleanup failure | UNMEASURED | Add a cleanup-verification test or explicit sanitized diagnostic; offline runner must detect residue | None |
| Parallel calls / inbound burst | One subprocess per `generate()`; no semaphore or queue in the client | UNMEASURED | Offline Stage 1 concurrency is exactly 1. Any future dispatcher needs its own bound, drop policy, and resource test | None |
| Retry/backoff | Client performs no retry | MEASURED from code | Correct for fail-closed offline evidence. Future retry policy belongs to a caller and requires idempotency/quota rules | None |

### Load-bearing conclusion

The adapter's current tests prove that many **constructed** process failures are sanitized and
cleaned up. They do not prove how Codex CLI reports a dead subscription, a usage cap, a safety
rejection, or a partial completion in the real service. The gate must never convert a simulated
stderr string into a claim about measured vendor behavior.

## 3. Offline Stage 1 failure semantics

Stage 1 is the de-identified replay proposed in PR #4301 on branch
`agent/air-m5/ops/bot-corner-reconfirm-2026-08-18`, file
`research/operations/2026-08-18-bot-openai-shadow-wiring-plan.md`. That proposal is not yet on
this branch or `main`; the requirements below are repeated here so this document does not depend
on an unresolvable local path. It is not a live shadow branch.

The runner must:

1. use `CodexExecClient`, never infer the selected provider from a generic "OpenAI" label;
2. run only on an operator machine already authenticated to the declared ChatGPT Pro seat;
3. use `--ephemeral`, a fresh cwd, ignored user config/rules as validated, and concurrency 1;
4. never retry auth, quota, policy, or unknown non-zero exits automatically;
5. record only the typed outcome, numeric exit code where already exposed, model, latency, and
   de-identified fixture ID — never raw stderr, auth paths, credentials, phone numbers, or source
   message IDs;
6. fail the entire run if no selected-provider call succeeds, if quota interrupts the registered
   sample, or if a session/prompt residue sentinel is found;
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
idempotency key is the local run key defined in §3. Replaying fixtures must not manufacture larger
sample counts by duplicating rows.

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

- [ ] #4216 rebased/reconciled with current main without widening its 11-file fence.
- [ ] `--ephemeral` added and session/prompt-residue sentinel proven.
- [ ] `--ignore-rules` and coding-agent host-read surface dispositioned.
- [ ] Generic communicate failures mapped to a sanitized typed error.
- [ ] Auth-death wording measured against a controlled real CLI failure.
- [ ] Subscription quota/usage-window behavior measured with Zero's authorization and quota budget.
- [ ] Role-aware, multi-turn de-identified corpus completed.
- [ ] Bench path actually invokes `CodexExecClient`.
- [ ] Offline runner concurrency fixed at 1 and idempotency proved.
- [x] Final frozen diff reviewed by Kimi K3 and Gemini 3.1 Pro.
- [ ] #4194 threat model rerun against the final adapter head.
- [ ] No config, gateway, worker, secret, live traffic, merge, or deploy until a separate mandate.

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

Final frozen-diff verdicts: **Kimi K3 — SHIP; Gemini 3.1 Pro — SHIP.** No reviewer authorized live
traffic, credentials, config, gateway or worker wiring, merge, deploy, or cutover.
