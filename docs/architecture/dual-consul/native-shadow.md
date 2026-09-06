# Native App Server shadow qualification

This increment exercises the Codex App Server transport through an opt-in,
synthetic text consumer. It extends the [common contract](common-contract.md)
and the [Astra specification](astra-native.md). It does not qualify operational
Astra, remote effects, a PostgreSQL authorization binding, or a distinct service
identity. The previous Autonomous Lab and Research OS slice remains separate.

## What the recorded probes establish

The [first native review](../../../evidence/dual-consul-native/review-1.txt)
returned **PASS-WITH-CONDITIONS**. Its three conditions concern a reproducible
catalog producer, producer-source binding in turn receipts, and the shared
identity vocabulary. Those corrections are implemented in source commit
`c03b182fcd`, with regenerated probes and passing tests. The
[native delta review](../../../evidence/dual-consul-native/review-2.txt) returned
**PASS** and closed all three conditions. Its
[metadata](../../../evidence/dual-consul-native/review-2.json) and
[exact compressed input](../../../evidence/dual-consul-native/review-2-input.txt.gz)
bind the reviewed source and selected evidence. The reviewer did not execute
tests or recompute hashes; the conductor and evidence author verified those
separately. This source review does not qualify operational execution.

The [selected native evidence](../../../evidence/dual-consul-native/README.md)
records two completed `gpt-5.6-terra` turns at `medium` on the same native thread,
with different turn IDs. Requested and runtime-configured model identifiers
match. No inference-response model identity was exposed: `inference_model` is
`null`. The checkpoint uses the common level `request_observed` with
`model_evidence_source: native_thread_configuration`. Neither establishes
response-observed identity. Terra qualifies this
transport experiment; it does not stand in for a served Astra response.

The second turn's native cumulative `totalTokens` is **15,945**. This is the
runtime counter for the thread, not the sum of cumulative snapshots. Native
input, cached-input, output, and reasoning counters remain separate; overlapping
counters are not added again. The cancellation artifact records local
process-group termination, `interrupt_acknowledged: false`, and the redacted
diagnostic code `interrupt_error_code: rpc_error`. The native interrupt was not
acknowledged. `remote_cancelled` remains `null`; native cancellation is not fully
qualified by this local-stop result.

The selected [discovery observation](../../../evidence/dual-consul-native/discovery.json)
found Astra unavailable in the actual model catalog, including hidden models,
without an inference call. The reproducible `--catalog` producer returned nine
models, `catalog.complete: true`, `catalog.include_hidden: true`, and
`catalog.requested_model_available: false` for `gpt-6-astra`. Requests for an absent
model are refused with `model_unavailable`; the adapter does not silently
substitute Terra. That catalog observation is distinct from the two stored
Terra turn receipts. A mission requiring response-observed model identity is
also inadmissible on this surface.

Each successful probe records `source_producer`: hashes of its six producer
modules and their canonical manifest hash. The producer checks the same files
again after collection and refuses a changed source set; `source_verification`
is `unchanged` on the three regenerated artifacts. This is separate from native
binary, profile, and runtime-context hashes. JSON presentation is normalized
without changing parsed values; the frozen review input remains exact.

The launcher accepts exactly `codex-cli 0.147.0`; the probe records the executable
digest as well as its version. The successful host was Air-M5. The selected
[fleet observation](../../../evidence/dual-consul-native/fleet-observations.json)
reports Pro `0.149.0` and Mini `0.148.0`; these different
runtime versions do not inherit the Air-M5 qualification. No runtime is installed
or activated on another machine by this consumer.

## Runtime profile and credential scope

[`codex_shadow_launch.py`](../../../scripts/conductor/codex_shadow_launch.py)
creates private temporary `HOME`, `CODEX_HOME`, and working directories. The
native binary runs with an explicit minimal process environment, a read-only
sandbox, no interactive approvals, disabled web search, disabled delegation, and
disabled tool, MCP, hook, plugin, skill, and application surfaces. Discovery
reads the effective configuration and rejects unexpected surfaces.

The actual strict configuration field is `shell_environment_policy`, with
`inherit = "none"` and `set = {}`. An `env` field is invalid. Setting an empty
map over a global configuration is insufficient when lower-layer map entries
survive merging; the isolated homes remove that source of inherited values.
This profile is specific to the inspected runtime version.

The launcher reads an existing ChatGPT subscription credential and creates a
mode-0600 access snapshot in the temporary native home. It preserves the source
`last_refresh` metadata and selected identity/access fields, and sets the copied
refresh token to an empty string. It grants no refresh authority. Missing refresh
metadata is refused; expired access requires a separate native login. The source
auth file is not a write target. Earlier diagnostic runs, before this correction,
refreshed a temporary copy only; they do not establish behavior of the corrected
snapshot. No credential value is part of the selected evidence.

These measures minimize inherited state and credential exposure. The native
process still runs under the caller's OS identity. They do not establish the
distinct trusted executor identity required for operational effects.

## Admission, continuity, and stopping

[`CodexShadow`](../../../scripts/conductor/codex_shadow.py) reuses conductor
`TaskIntent`, discovery keys, and common adapter admission. It accepts non-PII
text consultation with zero workers and no required tools or mutation. Discovery
is cached for five minutes under runtime, effective configuration, host, and
authentication context; configuration and account are read again before a turn.
Effort must exist in the native model catalog. `ultra` additionally requires an
explicitly authorized architecture or hard-build mission.

The authorization function is a **trusted host callback**, never a value supplied
by the model. It runs before thread start or resume, before the turn, and after
the reply. An operational host must obtain current authorization from the
existing broker. The bundled probe instead checks only its synthetic mission,
fixed input hash, short validity window, and local revocation flag. It does not
claim a PostgreSQL lease or operational broker grant.

One adapter process owns one mission binding: mission ID, input hash, model,
effort, and discovery context. Changed input or binding is refused. A second
invocation with the unchanged binding uses native `thread/resume`, then starts
another turn on the same thread. Native `ephemeral: true` threads rejected
resume during qualification, so the launcher uses `ephemeral: false` inside its
disposable private home. Native history exists there only until context cleanup.
Only same-process continuity is demonstrated. A checkpoint records IDs and
hashes for handoff; it cannot recover history after the temporary home is gone.
The checkpoint's `input_hash` covers the literal user text supplied to the
adapter. It does not cover expanded native system instructions or thread history.
Configuration and authentication hashes record context; they are not proof of
the complete effective prompt. This shadow binding does not replace the full
frozen-input contract required for operational review.

Input is limited to 32 KiB and selected response text to 64 KiB; local turn
collection is limited to 60 seconds. These bounds are not provider-enforced
output-token or total-consumption caps. Missions requiring either hard token
cap are refused. The consumer exposes no delegate capacity.

[`AppServerRPC`](../../../scripts/conductor/app_server_rpc.py) bounds frames,
pending requests, notification queues, and deadlines. It declines approval
requests, rejects unsupported server requests, discards late responses to
expired request IDs, and selects only necessary lifecycle, text, and usage
events. Raw reasoning, tool payloads, provider error text, and stderr are not
retained in shared evidence. The corrected collector selects only the
`final_answer` phase; missing final text or commentary-only output is incomplete.
The launcher enables `reject_tool_activity`: unexpected `item/started` or
`item/completed` types, including tool or delegation activity, fail the transport
and trigger local shutdown. Only user messages, agent messages, reasoning, and
context compaction are allowed through this type check; reasoning is subsequently
discarded. This detects unexpected activity rather than proving that an external
effect was prevented before its event arrived.

Cancellation attempts native `turn/interrupt` and then stops the owned local
process group. A callback cannot prevent local stopping. Interrupt acknowledgment,
timeout, or process termination does not certify remote cancellation or stopped
remote consumption. Cancelled bindings cannot be reused by this adapter.

## Verification and next qualification boundary

The [validation receipt](../../../evidence/dual-consul-native/validation.json)
records **125 tests passed in 2.22 seconds** across the native adapter, isolated
launcher, RPC transport, shared admission contracts, and probe; Ruff also passed.
The
[source manifest](../../../evidence/dual-consul-native/source-manifest.json)
binds eleven inspected files: six producer modules and five test modules. The stored invocation, discovery,
and cancellation JSON were read directly for the observations above. The first
review's conditions are closed by the native delta PASS; the previous PR's
review remains separate. Selected JSON may normalize presentation;
it does not promise byte equality with raw collected output. Frozen reviewer
input is retained separately as an exact compressed archive.

The consumer is [`codex_shadow_probe.py`](../../../scripts/conductor/codex_shadow_probe.py).
It defaults to discovery; `--catalog` records the full curated catalog including
hidden models without spending an inference turn. Explicit `--invoke` or
`--cancel` executes only the built-in synthetic prompt. It is not a scheduler or
an arbitrary prompt runner.
Existing CI, `change_map`, `impact_map`, and advisory `merge_group` exclusions
are unchanged.

The next stages remain separate: qualify the required model and runtime on each
host, bind current broker authorization under a distinct executor identity, then
consider staging and an authorized canary with versioned bindings and rollback.
Neither this local shadow proof nor a review receipt activates those stages.
