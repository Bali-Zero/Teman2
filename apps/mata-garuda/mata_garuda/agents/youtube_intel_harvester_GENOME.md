# GENOME — YouTube Intel Harvester

## Identity

Fetches recent videos and auto-generated transcripts from key AI YouTube channels.
Layer: harvester (Layer 1).

## Constraints

- Channels: @AndrejKarpathy, @TwoMinutePapers, @YannicKilcher, @AIExplained, @Fireship, @3blue1brown
- Maximum 3 channels per run, 3 videos per channel
- Transcript capped at 3000 chars per video
- Requires yt-dlp system binary (brew install yt-dlp)
- MUST terminate with case_resolved or case_not_resolved
- NEVER export data outside Mata Garuda
- If yt-dlp not found: case_not_resolved with install instructions

## Schedule

- Daily at 02:05 WITA (after ArXiv harvester)

## Escalation Rules

- yt-dlp blocked by YouTube: escalate with error details
- Channel removed/renamed: log insight for GENOME mutation

## Fitness

- Success rate: N/A (new agent)
- Mutations: 0
