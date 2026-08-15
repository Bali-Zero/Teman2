# Research OS v1.0.0 — Execution Control Room

**Program state:** `prepared_not_dispatched`
**Frozen architecture:** [`research-os/v1.0.0`](../../specs/evidence-to-action-freeze-2026-08-15/README.md)
**Execution-plan date:** 2026-08-15 WITA
**Authoritative runtime:** Pro
**Control surface:** Air-M5
**Campaign topology:** Pro execution + Air-M5 control; Mini-Pro2 `OUT_OF_CAMPAIGN`

This directory turns the frozen architecture into an executable program without changing the freeze itself. It separates work that can be prepared in parallel from shared integration points that must remain serial.

At creation time:

- no implementation packet has been dispatched from this control room;
- no migration has been applied;
- no production flag, service, scheduler, route, publisher, or render job has been changed;
- no retirement candidate has been disabled or removed;
- the existing freeze remains the semantic authority.

## Control-room artifacts

- [`SESSION-BOARD.md`](./SESSION-BOARD.md) — packet readiness, critical path, logical fleet slots, parallel batches, leases, and review flow.
- [`WAVE-0-DISPATCH.md`](./WAVE-0-DISPATCH.md) — the first launch queue and exact admission rules.
- [`RETIREMENT-REGISTER.md`](./RETIREMENT-REGISTER.md) — candidate inventory and the instrument → shadow → disable → observe → remove protocol.
- [`parallel execution plan`](../../../../docs/superpowers/plans/2026-08-15-research-os-parallel-execution.md) — task-by-task program plan.
- [`DISPATCH-MANIFEST.md`](../../specs/evidence-to-action-freeze-2026-08-15/DISPATCH-MANIFEST.md) — immutable envelope instantiated separately for every child session.
- [`DEPENDENCY-DAG.md`](../../specs/evidence-to-action-freeze-2026-08-15/DEPENDENCY-DAG.md) — canonical packet dependencies and migration reservations.

## Operating model

```mermaid
flowchart LR
    O["Operator + Conductor on Air-M5"] --> C["Pro-only campaign capacity and collision check"]
    C --> P["Parallel preparation lanes"]
    C --> B["Parallel bounded builders"]
    P --> G["Dependency gate"]
    B --> R["Independent reviewer"]
    R --> G
    G --> I["One serial integrator"]
    I --> S["Shadow and reconciliation"]
    S --> A["Separate owner-authorized canary"]
    A --> T["Retirement evidence"]
    T --> D["One-target disable"]
    D --> W["Observation window"]
    W --> X["Separate later removal"]
```

The Conductor is a role, not another background service. It controls scope, order, dependency truth, operator decisions, and the integration queue. Builders implement bounded packets. Reviewers independently test them. Neither a builder nor a reviewer may create real-world authority merely by returning `PASS`.

## Five hard rules

1. **The freeze is immutable during execution.** If evidence contradicts it, stop and raise a versioned freeze-change proposal.
2. **Preparation is broad; mutation is narrow.** Discovery, fixtures, baselines, and interface prototypes may fan out early. Canonical writes, shared registries, migrations, and live effects wait for their declared dependencies.
3. **The migration train is serial:** `270 → 271 → 272 → 273 → 274 → 275 → 276`. Schema preparation may run in parallel, but integration and application may not.
4. **Generator is not grader.** Every implementation branch receives an independent review; G1–G4 also receive a final on-disk empirical gate from the fleet's designated judge.
5. **Retirement is not deletion.** A legacy path is first instrumented, shadowed, proven replaceable, disabled behind a reversible control, observed for a complete window, and only then considered for a separate removal change.

## Campaign topology amendment: Pro + Air only

The operator has removed Mini-Pro2 from this execution campaign. This is a campaign-scoped placement decision, not a global machine retirement and not a semantic change to the frozen Research OS architecture.

- Pro is the only execution, registry, lease, builder, protected-processing, review-runtime, and integration authority.
- Air-M5 remains the lightweight operator/Conductor surface and may host public, minimized, or read-only review work within its existing boundary.
- Mini-Pro2 is `OUT_OF_CAMPAIGN`: it receives no campaign ref, worktree, branch, lease, builder, reviewer, batch, inference, integration, or retirement-effect assignment.
- Mini-Pro2 reachability, capacity, worktree inventory, and local Redis state are not S00 bootstrap inputs and do not block this campaign.
- The generic fleet inventory may still list Mini-Pro2 for other Nuzantara work. The Research OS controller must filter it out before admission and must reject any attempt to place campaign work there.
- Existing H24 services, stores, daemons, and retained Mini-hosted systems are untouched. Their continued operation or later retirement remains governed by their own contracts and authority gates.
- No campaign branch is fetched, checked out, synchronized, or executed on Mini-Pro2. If Mini later becomes reachable, it remains quarantined from this campaign unless a separately reviewed successor control-room decision explicitly re-admits it.
- An independently reviewed successor of this Control Room must contain this amendment before S00 may rely on it.

The participating topology is therefore closed and explicit: `authority_host=Pro`, `control_surface=Air-M5`, `excluded_nodes=[Mini-Pro2]`. Unknown state on a participating component remains fail-closed. An excluded node is not treated as spare capacity and is not probed as an authority dependency.

## S00-only bootstrap exception

The normal packet protocol below depends on controls that Session S00 must first create. Exactly one bounded bootstrap exception is therefore permitted, for S00 only:

1. bind the exact independently reviewed control-room commit as `control_room_sha` and make it visible to Pro through an immutable feature ref;
2. reverify the current Pro source relationship and critical tooling hashes; if the reviewed commit is not a safe source base, an interactive operator-controlled integrator creates one conflict-free bootstrap-composition commit from an operator-approved immutable Pro source ref plus the exact reviewed control-room change, and an independent reviewer approves that exact composed SHA before S00 edits begin;
3. record that final reviewed immutable SHA as `s00_base_sha`, create one dedicated Pro S00 worktree from it, and prove `HEAD == s00_base_sha` before and after acquiring the existing Pro path/repository leases;
4. create an immutable, branch-bound bootstrap scope receipt containing `control_room_sha`, `s00_base_sha`, source repository/ref, exact owned paths, Pro authority identity, lease-backend fingerprint, expiry, and the default zero-live-effect ceiling;
5. use direct Pro-authoritative worktree, path, registry, and lease inventory for the bootstrap collision check, then recheck the same participating Pro/Air campaign resources after worktree creation; fail closed on any unavailable, mismatched, local-only, or fail-open participating authority component;
6. run S00 as the only program session: no packet builder, reviewer repair, integration, migration, deployment, scheduler/service/flag change, publication, protected-data movement, or paid effect may run concurrently;
7. commit the S00 candidate first, independently review its exact SHA and artifact hashes, and route every repair through a successor commit and fresh review.

During this exception, the pre-S00 generic fleet command is diagnostic only and is not an authority gate. If it exits nonzero solely because it probes excluded Mini-Pro2, record `excluded_node_ignored` and continue with the direct Pro-authoritative bootstrap inventory. Any failure or unknown state involving Pro, the Air-M5 control surface, the exact owned paths, the Pro lease backend, or the immutable source remains a hard stop. The exception terminates when the final reviewed S00 SHA becomes `campaign_root_sha` and creates the normal Pro-authoritative registry, sidecars, placement controls, and dedicated integration-manifest contract. It cannot be reused by a packet or live effect. If the immutable Pro source identity or bootstrap receipt cannot be produced, the campaign remains blocked.

## Normal packet session start protocol

After reviewed S00 has terminated the bootstrap exception, before any child session edits a file:

1. refresh the authoritative Pro head, the Pro/Air participating topology, and baseline; do not probe Mini-Pro2 as a campaign dependency;
2. confirm the single-writer Pro run registry, the campaign lease, and the exact Pro Redis/backend fingerprint; Air-M5 and Mini-local registries or lease universes are invalid;
3. confirm the immutable `campaign_root_sha`, the exact monorepo control-plane `dispatch_base_sha` selected from the append-only integration-checkpoint chain, the `source_repository`, and its immutable `source_base_sha`;
4. run the campaign-capacity and collision probe over participating Pro/Air resources only; a generic fleet result must be filtered by the reviewed topology policy;
5. select the highest-priority eligible entry from `SESSION-BOARD.md` without exceeding four active builders;
6. instantiate and hash one immutable Dispatch Manifest from the frozen template;
7. acquire every exact path/shared-resource lease;
8. create one dedicated worktree from an immutable ref in `source_repository` resolving to the exact `source_base_sha`; monorepo lanes require `source_base_sha == dispatch_base_sha`, while an external-repository lane binds its separately approved source SHA and keeps `dispatch_base_sha` as control-plane lineage;
9. verify worktree `HEAD == source_base_sha`, repository identity, metadata, scope sidecar, and participating-topology collisions again; P01/P07 remain blocked until an immutable operator-approved OSINT-Nexus source ref exists;
10. record baseline, fixtures, rollback point, flags, cost ceiling, and hard stops;
11. begin implementation only after the session accepts the exact manifest.

The default side-effect ceiling is:

```yaml
filesystem: isolated_worktree_write
database: disposable_test_only
network: public_read_only
external_messages: none
publication: none
deployment: none
production_flags: none
scheduler: none
service_control: none
secret_rotation: none
paid_usage: none
```

Any higher ceiling requires a successor manifest plus an exact, unexpired, effect-specific authority chain. Technical review establishes eligibility only.

## Program state versus packet state

The control room uses a coordinator-only `program_state`; it does not replace the frozen `DispatchStateReceipt` contract.

| Program state | Meaning | Allowed next move |
|---|---|---|
| `queued_preparation` | Dependencies do not permit implementation, but bounded discovery/fixtures are useful | Dispatch a preparation-only manifest |
| `ready_to_dispatch` | Dependencies, ownership, capacity, and baseline are current | Create worktree and immutable manifest |
| `active` | One accepted implementation session owns the packet | Implement only declared files |
| `review_ready` | Builder has stopped with committed evidence | Independent reviewer reruns critical checks |
| `integration_queued` | Review passed, shared integration still pending | Serial integrator preserves the reviewed SHA in a conflict-free merge and tests |
| `shadow` | Integrated candidate is observing with side effects disabled | Reconcile preregistered windows |
| `owner_gate` | Technical gates passed; a consequential effect still needs authority | Wait for the exact operator decision |
| `complete` | Packet exit criteria and required receipts are satisfied | Unlock dependants |
| `failed` | A hard stop or reviewer failure occurred | Repair through a successor dispatch |
| `superseded` | Scope or baseline changed materially | Issue a new immutable manifest revision |

## Integration and review receipts

Every completed builder handoff contains:

- exact `campaign_root_sha`, monorepo `dispatch_base_sha`, `source_repository`, `source_base_sha`, reviewed source commit, and final source commit;
- exact changed paths;
- deterministic, adversarial, security, and privacy results;
- golden-set and metric references where applicable;
- feature-flag values and migration state;
- observed side effects, normally an empty list;
- unresolved gaps;
- rollback proof;
- the independent review verdict and receipt reference;
- `next_authorized_step: none` unless a separate dispatch exists.

The serial integrator rejects:

- unreviewed branches;
- unexplained file-scope growth;
- stale baselines or manifest hashes;
- migration-number drift;
- unresolved shared-file collisions;
- self-grading;
- tests that label fixture success as live readiness;
- any undocumented outward side effect.

The integrator is a distinct interactive Claude/operator-controlled role with its own hash-bound integration manifest; no external builder or reviewer seat may act as I1. Reviewed S00 must create and validate the dedicated `INTEGRATION-MANIFEST.schema.json` successor contract before I1 exists. The ordinary frozen Dispatch Manifest remains merge-forbidden. One integration manifest authorizes only one exact conflict-free merge of one reviewed source SHA into one named isolated integration branch in the same `source_repository`; it binds the control-plane checkpoint, repository-specific destination checkpoint, leases, review receipt, expected tree/result hashes, expiry, tests, and prohibitions on `main`, rewriting, conflict repair, deployment, production migration, service control, publication, paid use, and all live effects. I1 preserves the reviewed source identity and emits a separate repository result SHA plus a monorepo control-plane integration receipt/checkpoint. If integration requires a rebase, conflict edit, or any rewritten source commit, the candidate returns through a successor repair dispatch and independent review before integration.

## Immediate launch boundary

The first executable queue is defined in [`WAVE-0-DISPATCH.md`](./WAVE-0-DISPATCH.md). It prioritizes the critical path:

1. Packet 04 canonical contracts;
2. Packet 01 NEXUS containment Tasks 1–6;
3. Packet 03 WR3/FlowKit zero-spend readiness;
4. Packet 05 and 06 preparation lanes on Pro, with at most one preparation lane active beside the three hot-path lanes;
5. Packet 02, 07, 08, 12, 14, 17, and 18 preparation in the overflow queue.

Nothing in this directory authorizes execution of those entries. Dispatch begins only after this control-room branch receives independent review and the Conductor records a current capacity/baseline receipt.
