# Five route-specific adapters v4

**Contributors:** Kimi, Qwen, DeepSeek, Gemini, and GLM. **Synthesis:** Astra; reviewed by Fable 5.1.
**Attribution boundary:** the sections below are editorial synthesis, not verbatim model replies. [Selected consultation observations](../../../evidence/dual-consul-v4/design/consultation-observations.json) index final answers and allowlisted metadata recovered from the original recorded tool outputs. Qwen, DeepSeek, GLM, and Kimi answer hashes match the design packet. Gemini's text and parsed result are recovered, but its original stdout-byte hash cannot be recomputed from the re-serialized record; its newly computed selected-text hash is labeled separately. [Fable's final synthesis](../../../evidence/dual-consul-v4/design/fable-v4-final.txt) is recovered verbatim with verified native provenance.

## Common surface and reported request parameters

Use `discover`, `admit`, `invoke`, `checkpoint/handoff`, and `cancel` through the existing Research OS contracts and route-specific extensions. Admission covers scoped data egress and quota even for a no-tools request. Preserve native definitions of usage counters, unknown completeness, and separate local/remote cancellation. Locally validate structured outputs when required; no route below has a qualified native schema guarantee.

The table describes historical consultations, not current executable qualification. TP1 request/response fields and Kimi request metadata were recovered from recorded tool output; Kimi CLI version and Gemini requested-model/CLI syntax are retained from the design packet. Shared transport does not mean shared parameter support.

| Binding                          | Model sent or resolved                   | Effort sent                                      | Other reported controls                                              | Identity reported   |
| -------------------------------- | ---------------------------------------- | ------------------------------------------------ | -------------------------------------------------------------------- | ------------------- |
| Kimi no-tools CLI 0.41.0 profile | Alias `kimi-code/k3`, request model `k3` | Inherited `max`; no verified per-mission setting | `tools: []`; request `maxTokens=1048576`                             | `request_observed`  |
| Qwen TP1                         | `qwen3.8-max`                            | `medium`                                         | `max_tokens=4096`; local deadline 180 s; one request                 | `response_observed` |
| DeepSeek TP1                     | `deepseek-v4-pro`                        | Omitted                                          | `max_tokens=4096`; local deadline 180 s; one request; user-only body | `response_observed` |
| Gemini `agy`                     | Requested `gemini-3.1-pro-high`          | No separately qualified override                 | Plan mode; boolean `--sandbox`; `--conversation <ID>` for resume     | `unknown`           |
| GLM TP1                          | `glm-5.2`                                | Omitted                                          | `max_tokens=4096`; local deadline 180 s; one request                 | `response_observed` |

The three original TP1 tool records carry HTTP 200, matching model fields, and `finish_reason=stop`. This directly confirms the final user plan. Fable's final review had received a packet without those finish fields and consequently requested them; its historical missing-field premise is corrected here, not silently rewritten in the preserved evidence.

One consultation per family and no retries are reported. Durations, task contexts, and provider counters differ, so these observations are not a comparative benchmark. Request-side identity is insufficient for an exact-model mission. Unknown identity cannot silently pass admission.

## Kimi contribution and binding

[Kimi's original contribution](../../../evidence/dual-consul-v4/design/kimi-answer.txt) distinguished no-tools consultation through the existing profile from future native agentic CLI/ACP use. Preserve these as separate bindings. The observed empty active tool inventory validates participation in that specific consultation only; native tool use, ACP, and mission-governed cancellation remain unqualified.

Record both alias and request-resolved model; do not label request metadata as response identity. Inherited `max` effort and a 1,048,576-token request ceiling do not implement an ordinary mission budget. No `--effort` flag is invented. Both Kimi bindings are ineligible for missions requiring a verified hard output cap until a setting is discovered and tested on the installed surface. Native transcript retention remains product state, separate from shared redacted evidence. A no-tools binding still needs scoped egress and consumption authorization.

## Qwen contribution and binding

Reuse TP1 for `qwen3.8-max`; keep native Qwen CLI qualification separate. The consultation accepted `medium` on the wire. [Qwen's original contribution](../../../evidence/dual-consul-v4/design/tp1-qwen-answer.txt) explicitly left its reasoning semantics, tool calling, native JSON-schema enforcement, and mid-generation cancellation unvalidated. Parameter acceptance does not prove enforcement. Preserve response-model metadata and finish reason when present; unknown or truncated output is not automatically an ambiguous external effect.

Reject costly deliberate timeout/large-output experiments proposed during design. Use bounded fixtures first. Removing reasoning fields from shared output limits retention, not generated token consumption.

## DeepSeek contribution and binding

Reuse TP1 for `deepseek-v4-pro` with effort omitted. The current request body is user-only; do not introduce a fictitious system-directive option. The retired direct API remains excluded. Local `deepseek-r1:32b` is a distinct host-local binding with separate capabilities, never an equivalent fallback.

[DeepSeek's original contribution](../../../evidence/dual-consul-v4/design/tp1-deepseek-answer.txt) described this route as a bounded text transport without native conversation-history, multi-turn, or cancellation management. Exact pre-flight consumption and remote cancellation remain unproven. A mission requiring a total-consumption ceiling is ineligible until enforceable evidence exists. An output cap or local deadline cannot supply that evidence.

## Gemini contribution and binding

Use `agy` with IDs actually exposed by the installed runtime. The successful turn requested `gemini-3.1-pro-high` according to the design packet; the recovered parsed output omitted the served identifier. Record identity as unknown and refuse exact-model admission. [Gemini's original contribution](../../../evidence/dual-consul-v4/design/gemini-answer.txt) invented arguments: the design packet's verified command syntax uses boolean `--sandbox` and `--conversation <ID>`; neither `--sandbox terminal` nor `--conversation resume` is supported by the design evidence.

Do not combine a high-suffixed model with a separate effort override without validation. A successful JSON response does not prove strict schema enforcement, sandbox containment, tool denial, or governed resume. Retain cached usage under its native field definition without adding it to a total again. These operational capabilities remain qualification gaps.

## GLM contribution and binding

Reuse TP1 for `glm-5.2` with effort omitted. Its qualified participation surface is text. Protocol compatibility conveys no native Claude tools, identity, or permissions. [GLM's original contribution](../../../evidence/dual-consul-v4/design/tp1-glm-answer.txt) explicitly rejected treating the local 180-second deadline as provider-side cancellation and treating `max_tokens=4096` as a verified reasoning/total budget. Preserve those limitations at admission and report late replies without restoring cancelled attempts.

## Focused qualification and staged use

Share executor conformance proofs. Per-route fixtures cover incompatible parameters, model mismatch, request-only or missing identity, missing finish reason, truncated text, structural exclusion of reasoning fields, and timeout/late-response behavior. Unknown tool support means unqualified, not proof the model fundamentally lacks it. Retain provider-native usage fields without reasoning double count.

Use a bounded real smoke on introduction or a relevant runtime/configuration/authentication change, within existing authorization. Do not run a full campaign on every PR or force a long response to test a timeout. Promotion follows local, shadow without external effects, staging, authorized canary, and operations under the [common contract](common-contract.md). Initial synthetic executor tests grant none of the native runtime or remote effect capabilities above.
