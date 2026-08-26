"""L7 control tower for GARUDA VOA.

Practice -> CRM handoff, SLA timer, business-invariant alerts, funnel
aggregation and the SYN-01 synthetic purchase probe. Owned exclusively by
lane L7 per `products/garuda-voa/LANES.md`.

Everything here is written against the FROZEN contract
(`products/garuda-voa/contracts/`, `products/garuda-voa/journeys/STATE-MACHINE.md`,
`products/garuda-voa/journeys/SLO.md`) rather than against a live journal
table, because L1 (retention/migrations), L3 (orders/payment journal) and L4
(portal) had not merged into the integration branch at the time this lane
was built (`LANES.md` status: L3 `blocked (owner decision 1)`; no
`garuda_orders`/`garuda_portal` package existed yet; no journal table
migration existed under `apps/backend-rag/backend/db/migrations_v2/`).

The seam is `ports.py`: every consumer here (`crm_handoff`, `invariants`,
`sla_timer`, `funnel_dashboard`, `synthetic_probe`) depends on a `Protocol`,
never on a concrete table. A concrete Postgres-backed implementation of
`JournalReader`/`OrderSnapshotProvider` lands once L1/L3 merge; until then
every module here is fully exercised by fakes in
`apps/backend-rag/backend/tests/services/garuda_ops/`, which is how each
alarm's red/green bite-proof was produced without a live database.
"""
