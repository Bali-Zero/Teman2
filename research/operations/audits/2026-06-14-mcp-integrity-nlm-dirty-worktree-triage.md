# MCP Integrity Exit-2 and NLM Dirty Worktree Triage

Date: 2026-06-14
Host: Pro (`nuzantara@Nuzantara`)
Branch: `codex-overnight/spark-alarm-20260614_041044-spark-dispatch-20260614_040950-scout-mcp-integrity-exit2-dirty-nlm-worktree-20260614_041044`

## Scope

Spark reported one actionable infrastructure signal plus a broad dirty root worktree:

- `com.nuzantara.mcp-integrity` had `last exit code = 2`.
- The root checkout at `/Users/nuzantara/Desktop/nuzantara` was dirty across NLM, article, automation, and research outputs.
- The overnight worktree itself was clean and isolated.

This audit verifies the signal live, applies only reversible remediation for the root cause, and separates the dirty root worktree from this PR.

## Verified MCP Integrity Evidence

Session-start machine check:

- Local machine: `nuzantara@Nuzantara` (Pro).
- Peer mini was unreachable during the initial check, so git sync with Mini was unverified.

LaunchAgent evidence before remediation:

- `launchctl list` showed `- 2 com.nuzantara.mcp-integrity`.
- `launchctl print gui/$(id -u)/com.nuzantara.mcp-integrity` showed:
  - Program: `/bin/bash /Users/nuzantara/Desktop/nuzantara-deploy/scripts/verify_mcp_integrity.sh`
  - `runs = 8`
  - `last exit code = 2`
  - `StartInterval = 900`
- The deploy script and tracked script matched before this branch changed the tracked script.

Baseline:

```json
{
  "declared": 10,
  "reachable": 12,
  "connected": 12,
  "pending": 0,
  "failed": 5,
  "ts": "2026-06-09T01:54:17Z"
}
```

Live failure before remediation:

```json
{
  "verdict": "RED",
  "reason": "MCP failures INCREASED vs baseline (5 -> 6)",
  "declared": 10,
  "reachable": 21,
  "connected": 11,
  "pending": 10,
  "failed": 6,
  "warnings": 1,
  "failed_servers": [
    "plugin:engineering:asana",
    "plugin:engineering:github",
    "plugin:engineering:pagerduty",
    "plugin:engineering:google calendar",
    "plugin:engineering:gmail",
    "google-workspace"
  ]
}
```

The five `plugin:engineering:*` failures match the tolerated baseline. The new blocker was `google-workspace`.

## Root Cause

`google-workspace` is not declared in the project `.mcp.json`. It is user-local Claude config:

```json
"google-workspace": {
  "type": "stdio",
  "command": "npx",
  "args": [
    "-y",
    "@presto-ai/google-workspace-mcp"
  ],
  "env": {}
}
```

Standalone `npx -y @presto-ai/google-workspace-mcp` initially failed because the npx cache for this package was corrupt or incomplete: `tough-cookie` was missing under the cached dependency tree. The package itself is healthy when installed from a clean cache.

## Remediation Applied

No repo-external config was edited and no baseline was relaxed.

The only runtime remediation was reversible cache quarantine:

```text
Moved:
/Users/nuzantara/.npm/_npx/dee4a18c9dd23cfe

To:
/Users/nuzantara/.npm/_npx/dee4a18c9dd23cfe.bak-codex-20260614_041044
```

After cache reconstruction, the standalone MCP server responded to `initialize`:

```json
{
  "serverInfo": {
    "name": "google-workspace-server",
    "version": "1.0.12"
  }
}
```

The guardian then returned to the baseline failure count:

```json
{
  "verdict": "YELLOW",
  "reason": "1 config warning(s) (missing env vars)",
  "declared": 10,
  "reachable": 22,
  "connected": 12,
  "pending": 10,
  "failed": 5,
  "warnings": 1,
  "failed_servers": [
    "plugin:engineering:asana",
    "plugin:engineering:github",
    "plugin:engineering:pagerduty",
    "plugin:engineering:google calendar",
    "plugin:engineering:gmail"
  ]
}
```

A manual LaunchAgent kickstart using the deploy copy of the script wrote:

```text
[mcp-integrity] GREEN - declared=10 connected=12 pending=0 failed=5 warnings=0
```

`launchctl list` then showed:

```text
-    0    com.nuzantara.mcp-integrity
```

## Repo Change in This PR

The tracked `scripts/verify_mcp_integrity.sh` now emits `failed_servers` in JSON, log lines, and the heartbeat state file. This does not change the health policy; it only makes the next RED diagnosable without manually parsing `claude mcp list`.

The LaunchAgent currently runs the deploy checkout copy at `/Users/nuzantara/Desktop/nuzantara-deploy/scripts/verify_mcp_integrity.sh`, so this diagnostic improvement becomes active there only after the normal merge/sync path updates the deploy checkout.

## Dirty Root Worktree Triage

The main checkout at `/Users/nuzantara/Desktop/nuzantara` remains dirty and was not normalized in this branch:

```text
main...origin/main [ahead 2, behind 160]
```

Likely generated or content-output buckets:

- `apps/bali-intel-scraper/data/published_articles.json`
- `apps/evaluator/nlm_deep_research/output/multimodal/`
- `apps/mouth/src/content/articles/**/*.mdx`
- `outputs/`
- `research/coherence-corpus/`
- `research/commercial/`
- `research/nb-health/2026-06-10..2026-06-14-health.md`
- `research/regulatory/2026-06-10..2026-06-13-delta.json`
- `shared/escalations_pro.jsonl`

Code, config, or automation files that need owner or pipeline-specific review before staging:

- `apps/evaluator/nlm_deep_research/*.py`
- `apps/evaluator/nlm_deep_research/persona_definitions.json`
- `apps/evaluator/nlm_deep_research/t4_nb5_config.json`
- `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`
- `docs/AUTOMATIONS_REFERENCE.md`
- `scripts/curiosity_loop.sh`
- `scripts/nb_export_corpus.py`
- `scripts/nb_generate_inventory.py`
- `apps/crm-cell/war-room/`
- `research/operations/2026-06-11-*.md`

Recommendation: do not bulk stage or reset the root checkout. Split it into at least two follow-up branches:

1. NLM pipeline code/config review with focused tests for the touched NLM modules.
2. Generated editorial/research output review with content-owner acceptance.

## Final Assessment

Outcome for the actionable signal: remediated.

The exit-2 condition was caused by a corrupted npx cache for a user-local MCP server. The cache was quarantined, `google-workspace` now starts, the guardian is no longer RED, and `launchctl list` reports exit status `0`.

Outcome for the dirty root worktree: triaged only.

The dirty root checkout is broad, concurrent, and unrelated to the MCP cache failure. It should remain untouched until a dedicated owner review or pipeline branch separates generated outputs from code/config changes.
