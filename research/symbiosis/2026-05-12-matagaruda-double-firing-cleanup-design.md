---
date: 2026-05-12
domain: symbiosis
client_case: SYMBIOSIS gap-closure loop · Step 5 · Gap 5 mata-garuda 12+1 active-active cleanup design
sources: 6
status: draft
loop_step: 5
loop_branch: feat/symbiosis-loop-2026-05-12
mode: doc-only
---

# mata-garuda 12+1 LaunchAgents double-firing — Cleanup Design

**Generated**: 2026-05-12 03:30 WITA · Step 5 of SYMBIOSIS gap-closure loop · branch `feat/symbiosis-loop-2026-05-12`.

## Context

`cicatrix-scars.md` STRUCTURAL 2026-05-07: 13 LaunchAgent labels load simultaneously on Pro AND Mini, both producing the same heartbeat at the same schedule. The risk materializes whenever Mini is online; was masked during April when Mini was offline most of the month. `~/scripts/wave1-pro-mini-dup-resolver.sh` exists with `--check`/`--resolve` modes but was never invoked because the Wave-1 catalogue assumed single-source plists.

## Verified active labels on Pro (2026-05-12 03:30 WITA)

```
launchctl list | grep matagaruda
```

Returns 14 entries (the cicatrix prediction of "12+1=13" + `nlm-feeder-stream.hourly` added later):

1. `com.matagaruda.invalidation-sweep`
2. `com.matagaruda.watcher.daily`
3. `com.matagaruda.reg-alert.30min`
4. `com.matagaruda.kg-linker`
5. `com.matagaruda.wr-topic`
6. `com.matagaruda.wr2-bridge`
7. `com.matagaruda.bridge.adaptive`
8. `com.matagaruda.nlm-feeder-stream.hourly`
9. `com.matagaruda.daily-briefing`
10. `com.matagaruda.kita-feed`
11. `com.matagaruda.nlm-expander.weekly`
12. `com.matagaruda.public-channel`
13. `com.matagaruda.weekly-digest`
14. `com.matagaruda.gap.consumer`

Mini status TBD (Mini may be offline at any time — verify via `ssh mini 'launchctl list | grep matagaruda'`).

## Per-organ decision table

For each of the 14 labels, decide: (a) Pro-only and unload from Mini, (b) Mini-only and unload from Pro, (c) leader-election keep-both.

| #   | Label                      |     Decision     | Rationale                                                                                                                                                                | External side effects                                  |
| --- | -------------------------- | :--------------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------ |
| 1   | `invalidation-sweep`       | **(a) Pro-only** | Writes to Pro-local KB SQLite; Mini has no KB writer                                                                                                                     | Local file only                                        |
| 2   | `watcher.daily`            | **(a) Pro-only** | Source of truth for Pro NB-INTEL daily watch                                                                                                                             | Telegram alert (1× Pro)                                |
| 3   | `reg-alert.30min`          | **(a) Pro-only** | Polls Pro PG outbox + Pro Redis                                                                                                                                          | Telegram alert — DUPLICATE today                       |
| 4   | `kg-linker`                | **(a) Pro-only** | Writes to Pro-local Postgres KG                                                                                                                                          | Postgres writes — DUPLICATE today (idempotent? VERIFY) |
| 5   | `wr-topic`                 | **(a) Pro-only** | WR2 topic selector uses Pro Postgres + Canva OAuth                                                                                                                       | Canva API call — DUPLICATE today                       |
| 6   | `wr2-bridge`               | **(a) Pro-only** | WR2 bridge to backend RAG running on Pro                                                                                                                                 | Backend HTTP calls — DUPLICATE today                   |
| 7   | `bridge.adaptive`          | **(a) Pro-only** | Adaptive bridge needs unique scheduler                                                                                                                                   | State machine — DUPLICATE risk                         |
| 8   | `nlm-feeder-stream.hourly` | **(a) Pro-only** | Pivoted to Mini Redis for ALERT consumption per cicatrix `NLM feeder split-brain` 2026-05-06, but the FEEDER ITSELF must stay Pro to avoid double-feeding NotebookLM API | NotebookLM API call — DUPLICATE risk if both fire      |
| 9   | `daily-briefing`           | **(a) Pro-only** | Generates briefing email                                                                                                                                                 | Brevo API + Telegram — DUPLICATE today                 |
| 10  | `kita-feed`                | **(a) Pro-only** | Generates KITA feed                                                                                                                                                      | Email + Telegram — DUPLICATE today                     |
| 11  | `nlm-expander.weekly`      | **(a) Pro-only** | NotebookLM expansion via MCP                                                                                                                                             | NotebookLM API — DUPLICATE risk                        |
| 12  | `public-channel`           | **(a) Pro-only** | Public Telegram channel post                                                                                                                                             | Telegram — DUPLICATE today                             |
| 13  | `weekly-digest`            | **(a) Pro-only** | Weekly digest email                                                                                                                                                      | Email + Telegram — DUPLICATE today                     |
| 14  | `gap.consumer`             | **(a) Pro-only** | Consumes Pro Redis `nexus:gaps` stream                                                                                                                                   | Local stream consumption — possibly OK either way      |

**All 14 → Pro-only**. Rationale: every label has at least one of (i) Pro-local DB/file writes, (ii) Pro-side credentials (Canva OAuth, Brevo, Telegram, NotebookLM CLI), (iii) external API call where duplication is wasteful or violates rate limits.

Mini retains its CONSUMER role (NLM feeder reads ALERTS from Mini Redis per 2026-05-06 split-brain fix), but no PRODUCER role from this label set.

## Cleanup PR plan

### Phase 1: empirical verification (read-only)

1. `ssh mini 'launchctl list | grep matagaruda'` — confirm Mini has the 14 labels loaded
2. Per label, check the Pro vs Mini plist files for `EnvironmentVariables` differences (e.g. `MATAGARUDA_HOST_ROLE` vars)
3. Tag each label with `mini_status: confirmed-active | absent | unknown`

### Phase 2: drafting (no live mutations)

1. For each of the 14 labels with `mini_status: confirmed-active`:
   - Save `ssh mini 'cat ~/Library/LaunchAgents/com.matagaruda.<label>.plist'` to `infra/launchagents-mini-archive/com.matagaruda.<label>.plist.archived-2026-05-12`
   - Document the decision rationale in `apps/organism/organism/organs_registry.yaml` (operator updates the entry's `host_role: pro_only` + `mini_archived: true`)

### Phase 3: live removal (manual user action, NOT this loop)

For each label decided Pro-only:

```bash
ssh mini "launchctl bootout gui/\$UID ~/Library/LaunchAgents/com.matagaruda.<label>.plist"
ssh mini "chmod u+w ~/Library/LaunchAgents/com.matagaruda.<label>.plist"  # reverse 0444 to allow rm
ssh mini "rm ~/Library/LaunchAgents/com.matagaruda.<label>.plist"
```

The `chmod u+w` step is REQUIRED because of the plist corruption scar hardening (chmod 0444 applied 2026-04-29).

### Phase 4: resolver hardening

Extend `~/scripts/wave1-pro-mini-dup-resolver.sh` protected list to the 14 labels. Add `--resolve` mode that detects re-introduction of any of these labels on Mini and auto-removes via the Phase 3 sequence.

### Phase 5: CI guard

Add `apps/organism/tests/test_organs_registry_no_active_active.py`:

```python
"""Test that no Innervation Genoma entry has BOTH host_pro=true AND
host_mini=true unless explicitly in an allowlist."""

import yaml
from pathlib import Path

ALLOWLIST = {
    # Currently empty post-cleanup. Add label only with rationale
    # comment + cicatrix-scars reference.
}

def test_no_active_active_outside_allowlist():
    g = yaml.safe_load(Path("apps/organism/organism/organs_registry.yaml").read_text())
    organs = g.get("organs", g) if isinstance(g, dict) else g
    violations = []
    for o in organs:
        host_role = o.get("host_role")
        if host_role == "active_active" and o["label"] not in ALLOWLIST:
            violations.append(o["label"])
    assert not violations, (
        f"Active-active organs outside allowlist: {violations}. "
        "See cicatrix-scars.md 12+1 mata_garuda LaunchAgents active-active scar."
    )
```

## Refusals enforced this loop

1. NO `ssh mini` autonomous calls (depends on Mini availability + Tailscale)
2. NO `launchctl bootout` on Pro or Mini
3. NO `chmod u+w` on hardened plists
4. NO edit of `apps/organism/organism/organs_registry.yaml` (operator-controlled)
5. NO new CI test file in `apps/organism/tests/` (proposed in doc only)
6. NO extension of `~/scripts/wave1-pro-mini-dup-resolver.sh` (operator-side script)

Doc-only. The 5 phases above add up to ~3-5 person-days. Out of 3h scope.

## What this step does

Produces a per-organ decision table that maps the cicatrix's "13 labels active-active" warning to a concrete 5-phase cleanup plan with:

- 14 explicit labels (cicatrix said 12+1=13, but `nlm-feeder-stream.hourly` was added later → 14)
- For each: chosen verdict (all Pro-only) + rationale + external side effect type
- For each: the exact `launchctl bootout` + `rm` sequence the operator runs

Operator can pick this up as the basis for the cleanup PR.

## Sources

1. `.claude/rules/cicatrix-scars.md` STRUCTURAL 12+1 mata_garuda 2026-05-07 entry
2. `launchctl list | grep matagaruda` (Pro, 2026-05-12 03:30 WITA — 14 labels)
3. `apps/organism/organism/organs_registry.yaml` (Innervation Genoma — 118 entries)
4. `.claude/rules/cicatrix-scars.md` NLM feeder split-brain 2026-05-06 (justifies keeping `nlm-feeder-stream.hourly` Pro-only)
5. `~/scripts/wave1-pro-mini-dup-resolver.sh` (existing resolver with `--check`/`--resolve` modes)
6. `.claude/rules/cicatrix-scars.md` PLIST CORRUPTION SCAR 2026-04-29 (justifies `chmod u+w` step in Phase 3)
