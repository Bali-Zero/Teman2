---
date: 2026-07-17
seat: B
reviewer: Gemini 3.1 Pro
model: Gemini 3.1 Pro (High)
role: constructive-systems-reviewer
invocation_result: success
model_proof: "agy selected Gemini 3.1 Pro (High); exit code 0"
client_data: none
repository_access: "spec and brief supplied in full; no autonomous tool access"
---

# Verdict

GO-WITH-CHANGES 85

# Blocking findings

1. **Rollback Generation Mismatch:** Section 13 (Cutover and rollback) states rollback involves reactivating the old owner, while Section 7.2 (Initial ownership migration) states claiming work requires the current `ownership_generation`, which monotonically increases on cutover. An already-running old process with stale configuration cannot claim work if it does not know the new generation, rendering the documented rollback sequence broken.
   _Correction:_ Define how the reactivated old owner learns the newly incremented fencing generation (e.g., via dynamic database polling rather than static startup configuration) to allow it to resume claiming work without requiring a full redeployment.

2. **Fly.io Worker Health Check Contract:** Section 10 (Observability and operations) states worker liveness is a "separate heartbeat/readiness record" and not part of the API readiness. However, Fly.io deployments require a health check (HTTP, TCP, or exec) to mark a deployment as successful and route internal DNS. If the worker does not expose a port or a script check, Fly deployments will hang, timeout, or silently fail to complete the rollout.
   _Correction:_ Specify that the `worker` process group must include a lightweight local HTTP endpoint or a script declared in `fly.toml` `[checks]` to bridge the internal database heartbeat record to the Fly.io infrastructure layer.

# Important findings

1. **Side-Effect Fencing Race Condition:** Section 7.2 relies on `ownership_generation` to stop stale owners from executing side-effects. If a stale worker is already mid-execution when the generation increments, it may execute an external irreversible API call before its next database check. The contract in Section 7.3 must explicitly require a fencing check (e.g., a database lease validation) immediately prior to triggering external side effects.
2. **XAUTOCLAIM Contention:** Section 8.3 mandates `XAUTOCLAIM` for abandoned Redis Streams entries. In a multi-replica local control plane, concurrent consumers aggressively polling `XAUTOCLAIM` can create lock contention or race conditions if not scheduled carefully. The design should specify a dedicated reclaimer loop or a randomized jittered sweep per consumer.
3. **Same-Image Memory Spikes:** Section 4.1 maps the `worker` to the same image as `api` and `rag`. Given the constraints in `ADR-009` ("Single worker on Fly.io memory constraint"), if the worker image imports heavy inference dependencies from `main_rag.py` (even if unused), it will OOM on small Fly VMs. Section 16 mentions a "measured import budget," but the test gates in Section 15 do not explicitly block `worker` startup if it loads heavy RAG modules.

# What survives review

- **Shared Code, Distinct Processes:** Using the existing image for the `worker` process (Section 4.1) is operationally sound and avoids the overhead of managing a new CI/CD pipeline while successfully achieving workload isolation.
- **Incremental Fencing Strategy:** The `off`, `shadow`, `active` workload migration strategy (Section 7.2) is a robust and safe pattern for migrating workloads out of FastAPI/Uvicorn lifespans with minimal downtime.
- **Process-Partitioned Monolith:** Retaining PostgreSQL as the cloud broker (Section 8.1) and explicitly avoiding premature Kubernetes or Kafka adoption (Section 17.D) perfectly aligns with current operational capacity and system complexity constraints.

# Required amendments

1. Update Section 13 (Cutover and rollback) to explicitly state how the old owner acquires the post-rollback `ownership_generation` to prevent a rollback deadlock.
2. Update Section 10 (Observability and operations) to define the Fly.io deployment health check mechanism for the `worker` process.
3. Update Section 7.3 (Job contract) to require a late fencing validation immediately before any irreversible external API call to prevent dual-execution during the cutover window.
4. Add a falsification test (Section 15) to assert that the `worker` entrypoint does not import or allocate memory for Qdrant/inference dependencies.

# Falsification test

**G13 — Worker deployment health check succeeds:**
Deploy the `worker` process group to a Fly.io staging environment. The Fly deployment must successfully report a passing health check and complete the rollout without exposing a public HTTP router, proving the worker liveness is correctly bridged to Fly's deployment lifecycle.

**G14 — Worker memory ceiling is enforced:**
Start the `worker` process and monitor its steady-state memory. The process must stabilize at a baseline consistent with the `api` process, explicitly proving that heavy modules from `rag` (such as ML inference models and Qdrant clients) are not eagerly imported or loaded into the worker's memory space, thereby preventing Fly.io OOM terminations.
