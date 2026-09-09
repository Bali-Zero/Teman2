# Claude native integration v4

**Specification author:** Fable 5.1. **Design reviewer:** Astra.
**Editorial assembly:** verified v3 native-spec text plus Fable's final v4 amendments, followed by clearly separated implementation notes.

## Authorship and precedence

The two specification sections below reproduce Fable's own text verbatim from native session `433c29dd-e09f-4070-b1e9-a8da0136970c`. The locally inspected assistant records identify `message.model=claude-fable-5-1`, runtime `2.1.261`, and `stop_reason=end_turn`. Full selected responses and byte hashes are in the [design manifest](../../../evidence/dual-consul-v4/design/manifest.json).

The v4 amendments govern where they narrow or correct v3. In particular, "interactive" eligibility in v3 means only **interactive, tools-empty, plan-mode design text** after the v4 correction. Neither this historical review nor its native model metadata qualifies the implementation being built now. Session links and commit trailers authenticate nothing.

- [V3 source](../../../evidence/dual-consul-v4/design/fable-v3-revised.txt): `715a665f9ae3f90d7d4ead019bef7cb8796d0afe9085b02f389e3bb8c669bf43`.
- [Final v4 source](../../../evidence/dual-consul-v4/design/fable-v4-final.txt): `2a6af479053f98e6da77366e4e9538bab66afc2032ac6f6cccbb96af17af616f`.

## Revised native specification: Fable v3, verbatim

- **Entry.** Version-pinned CLI launched by the trusted launcher, which records the native model identifier, session identifier, CLI version, host, and auth class. Interactive is the current eligible surface. Headless print mode becomes eligible only after the entitlement check passes and is cached by CLI version, account, and host digest. Ambiguity fails closed. The exact flag set is verified from the installed CLI help output and docs, never from my assertion.
- **Binding.** The execution extension under the Claude namespace records requested and resolved model, effort actual, session identifier, config digest, admission budget, and artifact input hash. Assurance level is runtime_observed. Model changes inherit no authorization or prior review.
- **Enforcement.** The distinct-UID executor is authoritative for effects, fencing, and revocation. The hook denies obvious violations early and writes started journal entries. Tools that cannot meet the boundary are disabled for effects and may emit ActionIntents. Review missions get read-only tools. Design missions get none. No claim of OS confinement for the Claude surface until allowed and denied probes exist, which they do not today.
- **Effort, context, cache.** Effort comes from a policy table keyed by mission class. Top levels require a stated reason. Stable contract text precedes variable packet text for cache benefit. Fast mode runs a different model and is excluded from consul verdicts. Capability lookups are cached, not probed per mission.
- **Sessions.** Ephemeral when no resume is needed. Same-mission resume permitted after fresh checks. Native compaction is convenience. Company authority remains PG and provenance records.
- **Cancellation.** Revoke in PG, interrupt the native turn, terminate the supervised process group, mark ambiguous effects reconcile_required, and keep any provider response evidence.
- **Economy.** Observed counters for input, cached, reasoning, and output, with unknown fields explicit. Provider max-output is not a total cap.
- **Tests.** CLI flag capture. Executor deny on stale fence with hook bypass attempted. Journal transitions including timeout after remote commit. Entitlement check with fail-closed ambiguity. Env allowlist. Process-group kill with reconciliation. Receipt invalidation on artifact change. Native usage fields matched to the ledger. Resume with revoked authorization must fail.

## Final amendments: Fable v4, verbatim

- **Validated surface.** Interactive, tools empty, plan mode, design text. Recorded as response_observed identity from the native model field in this session.
- **Unqualified surfaces.** Headless entitlement, interactive tool use under the executor boundary, native resume with fresh checks, hook deny path, env isolation, process-group cancellation. Each stays a recorded gap until its fixture or smoke passes.
- **Identity.** Assurance level runtime_observed, sub-level response_observed. No trailer or link claim.
- **Budget.** Effort from the mission-class table. Where a hard output cap is required and no verified setting exists for the installed CLI version, the binding is ineligible for that requirement rather than silently weakened.
- **Cancellation reporting.** Local interruption and remote cancellation are separate fields. Ambiguous effects only become reconcile_required. Truncated or unfinished text is incomplete.
- **Tests.** As in v3, plus one fixture for unknown completeness and one for request-observed identity mismatch.

## Implementation notes: editorial, not Fable-authored text

The [common contract](common-contract.md) defines canonical receipt semantics. A hook may annotate a local started journal, but a model-side hook cannot issue an authoritative successful receipt or replace the executor's immediate grant/fence/resource checks. The distinct-identity executor is a required operational boundary, not a property established by the first synthetic test.

Headless remains disabled until version-, host-, configuration-, and authentication-specific entitlement and consumption evidence is sufficient. Ambiguity fails admission. Existing authorization can satisfy the check; the design creates no new mandatory human confirmation. A call requiring new spending still needs the owner's authorization. Current Claude documentation states that non-interactive `-p` and Agent SDK requests can bill usage credits without the interactive consent prompt. [Official Fable usage-credit documentation](https://code.claude.com/docs/en/model-config#fable-and-usage-credits), checked 2026-09-06.

Preserve native instructions, permissions, and same-mission continuity without treating them as company authority. Do not equate effort names with another provider or substitute a different model without a fresh binding. Discover exact CLI flags from the installed runtime before use. Evidence retention is selected and redacted under an explicit storage budget; full native transcripts and internal reasoning are excluded from shared evidence by default.

The first synthetic increment does not launch Claude, test entitlement, exercise its tools, resume a native session, or cancel a remote operation. The outstanding fixtures and bounded smoke tests in Fable's text remain a qualification checklist for later stages; they are not an all-PR test requirement. Promotion uses the common staged rollout with per-host evidence and rollback to the prior binding.
