# 11_brainstorms — Index

For each P0 fix from `09_intervention_plan.md`, a dedicated implementation strategy
with options, tradeoffs, code diffs, dependencies, rollback plan, and L2 autonomy decision.

## P0 brainstorms (8 fixes)

| ID | File | Effort | L2 autonomy | Status |
|----|------|--------|-------------|--------|
| **P0-0** | [P0-0_health_endpoint_classify.md](P0-0_health_endpoint_classify.md) | 1-2h | YES | foundational — implement first |
| **P0-1** | [P0-1_searchservice_degraded_mode.md](P0-1_searchservice_degraded_mode.md) | 1h | YES | needs P0-0 |
| **P0-2** | [P0-2_eventbus_outbox_pattern.md](P0-2_eventbus_outbox_pattern.md) | 1-3 days | PARTIAL | foundational PG durability |
| **P0-3** | [P0-3_launchagents_audit.md](P0-3_launchagents_audit.md) | 3-4h | YES (with dry-run review) | local infra |
| **P0-4** | [P0-4_sql_v2_post_deploy.md](P0-4_sql_v2_post_deploy.md) | 30min | YES | quickest win |
| **P0-5** | [P0-5_httpx_dependencies_audit.md](P0-5_httpx_dependencies_audit.md) | 1-2 days | PARTIAL | needs P0-0/P0-1 |
| **P0-6** | [P0-6_channels_ack_first.md](P0-6_channels_ack_first.md) | 2-3 days | PARTIAL (Twitter creds) | needs P0-0/P0-2 |
| **P0-7** | [P0-7_duplicate_migration_numbers.md](P0-7_duplicate_migration_numbers.md) | 2-4h | PARTIAL (PG query) | independent |

## Implementation order recommendation

1. **P0-0** (1-2h) — must come first; nothing visible to monitoring without it
2. **P0-7** (2-4h) — schema integrity, blocks new migrations cleanly
3. **P0-4** (30min) — chronic pain killer
4. **P0-1** (1h) — most common restart loop
5. **P0-3** (3-4h) — local daemon resilience
6. **P0-6** (2-3 days) — client-facing protection
7. **P0-2** (1-3 days) — foundational PG durability
8. **P0-5** (1-2 days) — eliminates resource leak class

## P1/P2 follow-ups (not yet brainstormed)

The brief from Antonello asks for brainstorms on each part to intervene. The intervention plan
identifies 8 P0, 5 P1, 4 P2, and 7 NB-* (additional) fixes. The 8 P0 brainstorms above are
the most urgent. P1/P2/NB-* will be added in follow-up sessions OR can be brainstormed
on-demand when each is scheduled for implementation.

This is consistent with VADEMECUM Pillar 5 (Sogno): consolidate one cycle, then expand.
