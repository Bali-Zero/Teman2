# Round 1 — 19 ambiguous NB decisions (2026-05-07)

Total entries pending Zero approval: **19**

| Cluster | Count |
|---|---|
| research_heavy | 5 |
| subhi_merge | 4 |
| zero_value_orphan | 2 |
| orphan_unclear | 8 |

## Cluster: research_heavy

### `201b4b94-deda-40a9-9fcb-0e67a3f81e52` — Digital Sovereignty & Ancestral Wisdom AI

- source_count_live: None
- peer_uuids: []

**Zero decision (2026-05-07):** _____________________________

### `4a8f3162-6f63-4876-9fe9-642dd9ae0606` — Analisi Video AI Agency

- source_count_live: None
- peer_uuids: []

**Zero decision (2026-05-07):** _____________________________

### `50396b3e-b2f9-4903-8df5-65c2b9709eba` — Claude Code optimization research 2026-04-21

- source_count_live: None
- peer_uuids: []

**Zero decision (2026-05-07):** _____________________________

### `917a1300-61ac-4fdb-8d94-8a42503c0442` — World Models 2026 — Comprehensive Survey (Genie, Waypoint, GameNGen, SORA)

- source_count_live: None
- peer_uuids: []

**Zero decision (2026-05-07):** _____________________________

### `d97ff70b-9c14-42a3-8813-5416039b24f7` — Nexus — Palantir Architecture Deep Research

- source_count_live: None
- peer_uuids: []

**Zero decision (2026-05-07):** _____________________________

## Cluster: subhi_merge

### `46b4dfe0-2be9-4fe4-97cd-3d44ef28a8ab` — NB-NLM-ELEVATION — SOTA research & brainstorm 2026-04-25

- source_count_live: None
- peer_uuids: []

**Zero decision (2026-05-07):** _____________________________

### `552072ab-7f09-4cda-a13c-0988f414d36d` — NB-SUBHI Onboarding Frontend SEO CRO 2026-04-30

- source_count_live: None
- peer_uuids: []

**Zero decision (2026-05-07):** _____________________________

### `9a866adc-988c-407f-9920-60dabf5ab164` — NB-SUBHI Misi 60 Hari Probation 2026-04-30

- source_count_live: None
- peer_uuids: []

**Zero decision (2026-05-07):** _____________________________

### `da94d615-0140-4b46-8484-f24a423a91ce` — NB-CRM-VIP — Top Clients Bali Zero

- source_count_live: None
- peer_uuids: []

**Zero decision (2026-05-07):** _____________________________

## Cluster: zero_value_orphan

### `9530b58d-cb7b-4bda-b5c2-c68e723b8118` — Indonesia Restaurant Investment and Regulatory Guide 2026

- source_count_live: None
- peer_uuids: []

**Zero decision (2026-05-07):** _____________________________

### `aaaaaaaa-aaaa-aaaa-aaaa-aaaa00000036` — Indonesian Foreign Investment Real Estate & Tax

- source_count_live: None
- peer_uuids: []

**Zero decision (2026-05-07):** _____________________________

## Cluster: orphan_unclear

### `aaaaaaaa-aaaa-aaaa-aaaa-aaaa00000018` — Unidentified NB orphan 1

- source_count_live: None
- peer_uuids: []

**Zero decision (2026-05-07):** _____________________________

### `aaaaaaaa-aaaa-aaaa-aaaa-aaaa00000019` — Unidentified NB orphan 2

- source_count_live: None
- peer_uuids: []

**Zero decision (2026-05-07):** _____________________________

### `aaaaaaaa-aaaa-aaaa-aaaa-aaaa00000020` — Unidentified NB orphan 3

- source_count_live: None
- peer_uuids: []

**Zero decision (2026-05-07):** _____________________________

### `aaaaaaaa-aaaa-aaaa-aaaa-aaaa00000021` — Unidentified NB orphan 4

- source_count_live: None
- peer_uuids: []

**Zero decision (2026-05-07):** _____________________________

### `aaaaaaaa-aaaa-aaaa-aaaa-aaaa00000022` — Unidentified NB orphan 5

- source_count_live: None
- peer_uuids: []

**Zero decision (2026-05-07):** _____________________________

### `aaaaaaaa-aaaa-aaaa-aaaa-aaaa00000023` — Unidentified NB orphan 6

- source_count_live: None
- peer_uuids: []

**Zero decision (2026-05-07):** _____________________________

### `aaaaaaaa-aaaa-aaaa-aaaa-aaaa00000024` — Unidentified NB orphan 7

- source_count_live: None
- peer_uuids: []

**Zero decision (2026-05-07):** _____________________________

### `aaaaaaaa-aaaa-aaaa-aaaa-aaaa00000025` — Unidentified NB orphan 8

- source_count_live: None
- peer_uuids: []

**Zero decision (2026-05-07):** _____________________________

## Follow-up — `NLM_NOTEBOOKS` callsites pending migration

This PR keeps these consumers on the compat shim. Future PR should migrate them
to `notebook_registry.NOTEBOOK_REGISTRY` directly:

- `apps/mata-garuda/mata_garuda/agents/sentinel_actor.py`
- `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`
- `apps/mata-garuda/mata_garuda/agents/nlm_expander_agent.py`
- `apps/backend-rag/backend/tools/health_tools.py`

Total references: ~9. Migration is a pure refactor (no behavior change required).
