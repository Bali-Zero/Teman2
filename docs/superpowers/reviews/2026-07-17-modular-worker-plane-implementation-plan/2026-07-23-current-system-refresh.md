---
date: 2026-07-23
subject: modular-worker-plane-current-system-refresh
evidence_base: origin/main@f3bf426de3805a5085b0cb67601181a0382a6630
client_data: none
authorization: false
---

# Current-system refresh for the modular worker-plane review

This PII-free memo records repository drift verified against
`origin/main@f3bf426de3805a5085b0cb67601181a0382a6630`. It is covered review evidence,
not an amendment to the implementation plan and not authorization to implement,
merge, migrate, deploy, arm, or mutate any environment. Any accepted correction
must change the canonical plan/spec bytes and trigger a completely new
hash-bound panel.

## Verified drift snapshot

1. **Migration allocation has collided.** The live SQL-v2 namespace now reaches
   `255`: current files in the interval are `246_clients_wa_intake_autocreate`,
   `247_kg_staging_status_integrity`, `248_clients_npwp_strongid`,
   `250_visa_engine_core`, `251_visa_activation_writer`,
   `252_visa_engine_write_substrate`,
   `253_visa_activation_writer_hardening`,
   `254_visa_activation_system_period_infinity_guard`, and
   `255_visa_shadow_evidence`. The absent `249` does not make the plan's
   contiguous `247`–`251` block viable; that allocation is occupied and cannot
   be used. `256`–`260` is only the next numerical candidate, with no formal
   lease evidenced by the current packet.
2. **Direct database coupling remains broad but bounded.** The refreshed
   inventory contains 67 router files with direct `asyncpg` coupling. Its
   canonical path-list fingerprint is
   `4002789a56196bd8cdce5440c1c596191f4e349ae6a91cb7e9f3d8ca8d24991a`.
   A future plan must bind the inventory method, count, and hash rather than
   treating the router boundary as an estimate.
3. **The targeted runtime regression slice is green but incomplete.** The
   refreshed targeted run completed with `121 passed`. That result shows
   preserved behavior for the exercised slice; it does not prove shutdown
   ordering, complete effect closure, Fly mutation-route exclusivity, or
   release safety.
4. **API shutdown can race background initialization.**
   `apps/backend-rag/backend/app/main_api.py` stores
   `app.state._init_task`, but shutdown proceeds to scheduler cancellation and
   pool closure without first cancelling and joining that initialization task.
   The plan must define and test a total shutdown order.
5. **The legal RED premise is partly stale.**
   `LegalIngestionService.ingest_document(...)` already accepts
   `document_id`; the missing compatibility control is
   `persist_source_to_drive`. A RED test that expects both parameters to be
   absent would be false-red and must be split around the behavior that is
   actually missing.
6. **Notification effect closure omits a send path.**
   `apps/backend-rag/backend/app/modules/notifications/test_endpoint.py`
   contains a `force_send` branch that calls the notification service. It must
   be inventoried and constrained by the same ownership, capability, and
   effect rules as other notification send paths.
7. **Fly mutation ownership is wider than the plan's named protected routes.**
   Current mutation-capable surfaces also include crashloop recovery, organism,
   cell, remediator, preflight, MCP Advanced, CLI, and legacy
   deploy/setup/migration paths. The plan's single-route claim is not complete
   until every such surface is retired, denied, or placed behind the same
   immutable admission contract. Any retained auto-heal path must be narrowly
   limited to recovery and unable to deploy images, scale topology, change
   secrets, or run migrations.
8. **GitHub Action majors have moved and the repository is mixed.** The relevant
   protected `.github/workflows/fly-deploy.yml` uses
   `actions/setup-python@v7` and `actions/upload-artifact@v7`;
   `.github/workflows/tests.yml` uses `setup-python@v7`,
   `upload-artifact@v7`, and `download-artifact@v8`. Other workflows, including
   doc-freshness/SBOM surfaces, still contain v4 pins. The plan's hardcoded
   upload/download-artifact v4 contract therefore cannot be treated as a
   repository-wide truth; it must bind the exact current pins of each protected
   producer/consumer workflow.
9. **The latest upstream change does not close the worker-plane gaps.**
   `origin/main` advanced from `8e826f0940c483f1050b81e74502fbe57aef2479`
   to `f3bf426de3805a5085b0cb67601181a0382a6630` through PR `#3015`. The
   two-commit delta changes only
   `apps/backend-rag/backend/llm/claude_oauth_client.py` and its unit tests. It
   adds a fourth OAuth fallback seat, a total fallback deadline, stricter
   provider-environment stripping, bounded diagnostic classification, and
   explicit timed-out-child reaping. It does not change the migration,
   startup/shutdown, legal, notification, Fly workflow, or Action-pin surfaces
   above, so none of their blockers is resolved. It does reinforce that
   subprocess ownership, deadline, cancellation, and reaping behavior must be
   explicit whenever a workload crosses into the worker plane.
10. **The OAuth client consumer comment is not an ownership inventory.** Its
    module docstring still claims three consumers and names article composer,
    but article composer now routes through a compatibility wrapper backed by
    another provider. The source graph exposes at least five distinct consuming
    surfaces: the multi-AI adapter, LangChain wrapper, cost-advisor CLI,
    knowledge-graph coreference service, and request-path surface router. Phase
    0 must derive this inventory from imports and call sites, not prose, and
    classify request-path, launchd/CLI, and wrapper ownership separately so two
    layers cannot both own fallback, cancellation, or retry.
11. **External cancellation can bypass OAuth subprocess cleanup.**
    `complete_async(...)` kills and reaps its child when its own
    `asyncio.wait_for(proc.communicate(), ...)` expires, but the surface router
    wraps that coroutine in a separate three-second `asyncio.wait_for`. An outer
    cancellation can therefore interrupt the coroutine outside its internal
    `TimeoutError` handler and skip child reaping plus later span/recorder
    closure. The child is not started in a dedicated session/process group, so
    the helper kills only the direct process and does not prove descendant
    absence. The worker-plane plan needs one cancellation-safe deadline owner,
    a dedicated process group, whole-tree termination and join in `finally`,
    and deterministic caller-cancellation plus shutdown tests. OAuth/keychain
    seats must be explicitly admitted capabilities rather than inherited
    host-global state. The new fourth token is also not a guaranteed attempt:
    the per-seat budget is 120 seconds while the whole fallback chain is capped
    at 300 seconds.
12. **The latest complete panel is historical only.** Its source
   `80a05a10…` and packet `7ad5a150…` predate this refreshed source and reviewed
   evidence, and its roster predates the permanent Gemini + Codex + Kimi
   external phase followed by the sequential Fable gate. It cannot authorize
   the current bytes or any migration-number substitution.

## Questions the panel must answer

- Can the migration block be reallocated atomically across every spec, phase,
  SQL/test command, receipt, rollback, and rollout reference, with a formal
  lease proved before implementation?
- Which runtime-init cancellation/join order prevents a late `_init_task` from
  spawning work after scheduler stop or pool close, and what deterministic RED
  test proves the race?
- Which legal and notification tests fail for the real missing behavior, without
  asserting that an already-present `document_id` parameter is absent?
- What canonical inventory and deny-by-default enforcement reduce all Fly
  mutations to protected routes while preserving only the explicitly bounded
  recovery lane?
- Which exact Action majors and artifact semantics must be pinned between the
  protected producer and consumer, and how is future version drift rejected?
- After amendments, do all three independent Phase-1 reviewers bind the same
  new packet, are all findings dispositioned, and does Fable independently
  pass the resulting bytes in the sequential Phase-2 on-disk gate?

## Authority boundary

This memo deliberately makes no `GO`, `GO-WITH-CHANGES`, or `NO-GO` decision.
The old packet/panel remains non-authoritative. Only a newly frozen packet,
three identity-distinct Phase-1 reviews (Gemini constructive, Codex GPT-5.6
red-team, Kimi K3 refuter), a complete disposition, and a sequential Fable 5
final on-disk verdict can establish a new review result.
