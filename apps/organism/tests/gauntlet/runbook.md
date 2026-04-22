# Gauntlet runbook

Manual execution procedure for the 10 adversarial scenarios.

## Prerequisites

- Worktree: `/Users/nuzantara/Desktop/nuzantara` on `main`
- Fresh venv: `cd apps/organism && python3 -m pip install -e '.[dev]'`
- Python 3.11+

## Running the unit-level gauntlet (this PR)

```bash
cd apps/organism
pytest -m gauntlet -v --tb=long
```

Expected: all tests pass in <1 minute. These are unit-style mocked tests
that verify the orchestration paths fire correctly for each scenario.

## Running the integration gauntlet (staging)

The integration gauntlet (with a live Supervisor daemon on isolated
staging) is not part of this PR. When staging is provisioned (W5):

1. `docker-compose -f staging-organism.yml up -d` starts an isolated
   Redis + postgres + qdrant.
2. Load launchd plist pointing to staging Redis.
3. For each scenario, inject the failure (crash guardian via
   `launchctl kill`, corrupt crontab by writing an invalid line,
   etc.) and observe:
   - Supervisor detects + decides within 90s (MTTD)
   - Actuator run completes within 5min (MTTR)
4. Document results in `docs/organism/gauntlet-YYYY-MM-DD.md`.

Scenarios 6-10 require OS-level access:
- 06 Redis down: `sudo pkill -STOP redis-server` (resume with `-CONT`)
- 07 Network partition: `sudo pfctl -e && sudo pfctl -f block.rules`
- 08 Clock skew: `sudo date -v+5M` (staging machine only)
- 09 Claude rate limit: simulate by setting `CLAUDE_CODE_OAUTH_TOKEN=invalid`
- 10 Poison pill: already covered by unit tests in this PR.

## Success criterion

10/10 unit gauntlet scenarios pass. Integration gauntlet runs in a
separate staging session after W5 staging provisioning.
