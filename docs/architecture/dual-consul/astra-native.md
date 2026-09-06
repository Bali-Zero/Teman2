# Astra native integration v4

**Design author:** Astra. **Design reviewer:** Fable 5.1, with accepted v3 comments and final v4 amendments.
**Editorial provenance:** this document implements the owner's consolidated Astra specification; it is not a verbatim recovered Astra response. Fable's cross-review is preserved in [v3 evidence](../../../evidence/dual-consul-v4/design/fable-v3-revised.txt).

## Native surface

Use Codex App Server for the consul integration, preserving native instructions, permissions, sessions, compaction, and agent events. The official protocol exposes `model/list` for discovery, `config/read` for effective configuration, and native thread/turn operations. Its role here is an interactive integration rather than a replacement scheduler. [Official App Server documentation](https://learn.chatgpt.com/docs/app-server), checked 2026-09-06.

Before initial admission, discover the installed runtime's available models and supported efforts, read its effective layered configuration, and record the observed schema/version. Reuse current observations under the cache rules in the [common contract](common-contract.md). Never infer availability on Pro or Mini from a successful M5 consultation or a configuration file.

The execution extension records requested model, observed model and assurance, provider, requested and effective effort, runtime version, host/authentication-context digest, effective configuration digest, native thread/turn identifiers, actual input artifact hash, and mission/grant references. Record missing fields as unknown. A model change invalidates the binding-dependent review and triggers fresh admission.

## Profiles, permissions, and workers

Maintain distinct logical profiles for difficult design, ordinary operation, review, and workers. Set effort from the mission class and discovered runtime support. Reserve `ultra` for a justified difficult task on a surface that supports it. No cross-provider effort equivalence is implied.

Launch with a minimal explicit environment and verify the environment actually seen by the child. `inherit=none` alone is insufficient when layered `env.set` entries survive. Strip disallowed global entries before applying the narrowly approved mission environment; do not log values or copy general service credentials. Keep filesystem/network confinement evidence separate from credential-isolation evidence.

Use scoped native permissions. The broker answers native approval requests from the actual grant and records an `ApprovalReceipt` with that grant reference. The distinct-service-identity executor remains authoritative immediately before effects. An App Server approval response or hook is not proof of external authorization enforcement.

Track observable delegation modes by binary version. The global maximum of four workers applies only when all admitted delegation is observable and controllable. Disable unobservable worker expansion rather than allow hidden delegation to bypass the limit. Four workers is a ceiling, not a default allocation.

## Continuity, cancellation, and evidence

Preserve native compaction and same-mission resume, repeating authorization, fence, config, and input checks first. Thread continuity confers no company-memory authority. A new mission gets a new binding and context boundary.

On cancellation, revoke the mission grant/ownership in PostgreSQL, interrupt the native turn, and terminate supervised processes. Record local interruption independently from remote operation status. Retain bounded, selected, redacted provider evidence for reconciliation; never retain full streams or hidden reasoning by default. Late replies cannot revive a cancelled or superseded attempt.

## Qualification still required

The initial synthetic slice exercises common lifecycle and ownership rules. Operational App Server launch, environment isolation, broker approval handling, delegation observability, native resume, process-group cancellation, and host eligibility require their own versioned evidence. The prior plan reports M5 discovery and narrow sandbox observations; this document does not upgrade them into a fresh runtime attestation.

Focused qualification covers layered `env.set` leakage, identity/config changes, unsupported effort, stale-owner effect refusal despite hook bypass, changed-artifact review invalidation, revoked resume, and local interruption with a late remote response. Share common executor proofs and use protocol fixtures before bounded real smoke tests. Fleet activation is a later stage in the common contract.
