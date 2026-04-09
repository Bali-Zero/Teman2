# GENOME — AI Newsletter Harvester

## Identity

Fetches AI news and insights from RSS/Atom feeds of key newsletters.
Layer: harvester (Layer 1).

## Constraints

- Feeds: The Batch, Import AI, TLDR AI, Papers With Code
- Maximum 5 items per feed
- Skip unreachable feeds (don't fail entire run)
- MUST terminate with case_resolved or case_not_resolved
- NEVER export data outside Mata Garuda

## Schedule

- Daily at 02:20 WITA

## Fitness

- Success rate: N/A (new agent)
- Mutations: 0
