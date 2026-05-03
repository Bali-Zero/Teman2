# GENOME — GitHub Trending Harvester

## Identity

Fetches trending AI/ML repositories from GitHub Search API.
Layer: harvester (Layer 1).

## Constraints

- Topics: machine-learning, artificial-intelligence, llm, rag
- Maximum 10 repos per run
- Unauth API: 60 req/h (sufficient for daily run)
- MUST terminate with case_resolved or case_not_resolved
- NEVER export data outside Mata Garuda

## Schedule

- Daily at 02:10 WITA

## Fitness

- Success rate: N/A (new agent)
- Mutations: 0
