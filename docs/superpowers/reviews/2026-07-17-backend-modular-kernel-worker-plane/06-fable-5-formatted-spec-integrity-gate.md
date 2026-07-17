---
date: 2026-07-17
reviewer: Fable 5
model: claude-fable-5
role: formatted-spec-integrity-gate
invocation_result: success
model_proof: "modelUsage contained only claude-fable-5; contextWindow 1000000"
spec_sha256: 2d1746b92067af1533d14c59f4751e623203941584c978a15ebe27b839a82e92
verdict: GO-96
client_data: none
repository_access: read-only
---

# Integrity verdict

GO — confidence 96.

# Semantic integrity

Read the full formatted file (1083 lines). All six approved amendment closures survive Prettier reformatting with normative meaning intact:

1. **Schedule-run identity** — §7.3 final paragraph (lines 546–553): run key is `(workload_name, scheduled_for)`, explicitly generation-independent; generation is "a mutable claim attribute, never as part of logical-run identity"; pending unclaimed runs are "adopted under the new grant in the cutover transaction or explicitly cancelled with an audit record; they are never duplicated under a new key". `effect_key` derives from "stable business identity and effect purpose … never … a queue row, attempt number, or ownership generation" (lines 510–514). Cutover steps 4–5 (§13, lines 807–814) inventory and adopt/cancel under the generation-independent key. G12 (lines 942–945) tests the schedule-class fixture across cutover **and** reverse-cutover rollback with "exactly one logical run … at most one business-identity effect".
2. **Claim-guard arming gated** — §7.2 (lines 465–471): "The claim guard is **not** armed merely because its migration exists. Arming is itself a gated ownership transition: every live owner heartbeat must first meet the compatibility build floor, and a stale or missing heartbeat fails closed." Echoed in Phase 1 (lines 725–728: "after every live owner heartbeat meets the compatibility build floor, arm a database claim guard").
3. **Runtime rejection of second durable subscriber** — §8.2 (lines 583–589): "The runtime dispatcher and `subscribe()` registration path also consume that catalog at startup and registration time and fail closed on an uncataloged durable subscription. No naming convention, dynamic registration, or in-process handler list may bypass this guard." Phase 1 (lines 728–730) and G5 (lines 889–891: bypassing `subscribe()` "must fail startup or registration") preserve the not-only-CI enforcement.
4. **Phase 2 governance/Qdrant reconciliation** — lines 740–743: reconciliation of checked infrastructure governance (stale fixed-app-count statements → current inventory plus approved companion target; Qdrant recorded as external where deployed reality) is ordered "before creating the app".
5. **Phase 2 release_command + ordering** — lines 744–747: companion `release_command` "either skips migrations or uses the same advisory-locked migration runner; deploy the primary app and verify schema compatibility before promoting the companion app".
6. **Planning-only boundary** — §20 (lines 1079–1082): approval "authorizes creation of an implementation plan for Phases 0-2 only. It does not authorize production deploy, job cutover, event schema migration, service extraction, or deletion of rollback paths." Reinforced by §2.2 ("no production deployment authorized by this document"), §19 (`reviewed-draft`, implementation unauthorized), and D2 ("accepted for planning").

Formatting deltas observed (wrapped prose, pipe-aligned tables, frontmatter quoting, list indentation) are layout-only; all normative numbers, hashes (`4002789a…`, 67-path baseline), gate texts G1–G17, and mode/state vocabularies are unchanged in meaning. I could not recompute the file SHA-256 (no hashing tool in this read-only surface); I relied on the independently verified hash supplied in the mandate plus full-content re-read.

# Blockers

None.

# Authorization boundary

Intact and unambiguous. The document authorizes only the drafting of an implementation plan for Phases 0–2; production deployment, workload cutover, event-schema migration, service extraction, and rollback-path deletion remain explicitly unauthorized (§20), the owner retains the final approval gate (§19), and the companion-app decision D2 is scoped "accepted for planning". This gate run makes no change to that boundary — verdict is on textual/semantic integrity only, not an implementation authorization.
