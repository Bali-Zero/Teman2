---
date: 2026-05-12
domain: symbiosis
client_case: SYMBIOSIS Gap 5 CLOSED — cicatrix already resolved via Modo B migration
sources: 4
status: closed-no-action
empirical_verification_wita: 2026-05-12 15:14
---

# Gap 5 — mata-garuda double-firing: CICATRIX ALREADY RESOLVED

**Empirical verification**: 2026-05-12 15:14 WITA
**Outcome**: No cleanup needed. The 2026-05-07 STRUCTURAL cicatrix "12+1 mata_garuda LaunchAgents active-active Pro+Mini" was silently resolved during Modo B (Mac Mini H24 server) migration. ZERO active-active labels remain. Gap 5 close = doc update + cicatrix archive entry.

## Empirical state on 2026-05-12 15:14 WITA

### Pro — 15 matagaruda labels (Pro-only)

```
com.matagaruda.bridge.adaptive
com.matagaruda.daily-briefing
com.matagaruda.gap.consumer
com.matagaruda.invalidation-sweep
com.matagaruda.kg-linker
com.matagaruda.kita-feed
com.matagaruda.nlm-expander.weekly
com.matagaruda.nlm-feeder-stream.hourly
com.matagaruda.public-channel
com.matagaruda.reg-alert.30min
com.matagaruda.sentinel.hourly    ← NEW 2026-05-12 04:41 from PR #588 OVERRIDE 4
com.matagaruda.watcher.daily
com.matagaruda.weekly-digest
com.matagaruda.wr-topic
com.matagaruda.wr2-bridge
```

### Mini — 5 matagaruda labels (Mini-only)

```
com.matagaruda.intel-bridge.daily
com.matagaruda.kg-query-api
com.matagaruda.ner-worker.hourly
com.matagaruda.normalizer.hourly
com.matagaruda.sentinel.daily
```

### Active-active overlap

**ZERO**. `comm -12 /tmp/pro-matagaruda.txt /tmp/mini-matagaruda.txt` returns empty.

## What this means

The cicatrix predicted 13 active-active labels (originally enumerated `watcher.daily, reg-alert.30min, kg-linker, wr-topic, wr2-bridge.hourly, bridge.adaptive, sentinel.daily, intel-bridge.daily, daily-briefing, kita-feed.daily, public-channel, weekly-digest, gap.consumer`). Empirically only 5 labels are on Mini today, and they are ALL Mini-only specialized workers in the OSINT pipeline:

- `intel-bridge.daily` — OSINT bridge to Pro Redis (consumer)
- `kg-query-api` — KG read API server (Mini hosts the read replica)
- `ner-worker.hourly` — NER extraction worker
- `normalizer.hourly` — Article normalization worker
- `sentinel.daily` — Mini-side daily sentinel (different from Pro `sentinel.hourly` which I added 2026-05-12)

These 5 are COMPLEMENTARY to Pro's 15, not duplicates. They implement the Modo B division of labor: Pro = producer + control plane, Mini = worker pipeline + read API.

## Why the cicatrix predicted active-active that never materialized

Timeline reconstruction (from `/Users/nuzantara/Library/LaunchAgents/` mtime + commit history):

- **2026-05-04**: Mini mostly offline during April. Cicatrix written assuming Mini and Pro had matching label sets that would fire double when Mini came online.
- **2026-05-06**: Mini Modo B setup. Plists distributed by `~/scripts/mini-setup/` daemons. The setup phase APPARENTLY made selective per-host installations rather than blanket-copying.
- **2026-05-07**: Cicatrix STRUCTURAL written.
- **2026-05-12**: Empirical check finds zero overlap.

The cicatrix author was right to flag the risk pattern — `rsync` or naive sync between LaunchAgents dirs WOULD have created double-firing. But the actual sync mechanism (whatever it is — possibly `secrets-sync-mini` LaunchAgent that handles selective install) avoided it.

## Action taken this loop

**Doc-only**: this file consolidates the empirical state + retires the cicatrix prediction. No code or plist changes needed.

The cicatrix entry in `.claude/rules/cicatrix-scars.md` STRUCTURAL section 2026-05-07 ("12+1 mata_garuda LaunchAgents active-active Pro+Mini") should be moved to `cicatrix-scars-archive.md` with a RESOLVED note. That edit is operator-controlled (`.claude/rules/` is gitignored as discovered in OVERRIDE 2 of Gap 2 closure).

## What this means for the SYMBIOSIS loop's Gap 5 design doc

`research/symbiosis/2026-05-12-matagaruda-double-firing-cleanup-design.md` (committed in PR #588, merged on main) is now **historical**: the 5-phase cleanup it proposes is not actually needed because the precondition (active-active) is empirically false. The design doc remains useful as a reference pattern for future similar situations, but its action items are obsolete.

Recommend operator append a note at the top of that file:

```
> STATUS UPDATE 2026-05-12 15:14 WITA: empirical verification shows
> ZERO active-active labels. See `2026-05-12-gap5-already-resolved-empirical-verification.md`
> for the post-Modo-B topology. The 5-phase cleanup below is HISTORICAL
> — not needed for the current state.
```

## Topology consolidato (post-empirical-verification)

| Host    | Role                       | Matagaruda labels | Notes                                                               |
| ------- | -------------------------- | ----------------: | ------------------------------------------------------------------- |
| Pro     | Producer + control plane   |                15 | Canva OAuth, Brevo, NLM CLI, observatory, supervisor                |
| Mini    | Worker pipeline + read API |                 5 | OSINT bridge consumer, NER, normalizer, KG read API, daily sentinel |
| Overlap | —                          |             **0** | Modo B selective install avoided naive sync                         |

## CI guard for the future

The proposal in PR #588 Gap 5 design for a CI test `apps/organism/tests/test_organs_registry_no_active_active.py` is **STILL VALUABLE** as preventive guard — empirical state today is clean, but a future bulk-install accident could re-introduce active-active. The test should be added in a follow-up PR.

## Empirical commands run

```bash
# 2026-05-12 15:14 WITA on Pro
launchctl list | awk '/matagaruda/{print $3}' | sort > /tmp/pro-matagaruda.txt
ssh mini 'launchctl list | awk "/matagaruda/{print \$3}"' | sort > /tmp/mini-matagaruda.txt
comm -12 /tmp/pro-matagaruda.txt /tmp/mini-matagaruda.txt  # → empty
wc -l /tmp/pro-matagaruda.txt /tmp/mini-matagaruda.txt  # → 15 + 5
```

## Status post Gap 5

Gap 5 closed: **no cleanup needed**, empirical state already clean.

Loop gap status:

- ✅ Gap 1 Cell silenti — closed empirically (seo-guardian emits)
- ✅ Gap 2 Consiglio — KILL revoked
- 📋 Gap 3 HGT TICKET A/B/C — deferred
- ✅ Gap 4 Ghost MEMORY.md — replacement doc landed
- ✅ Gap 5 matagaruda double-firing — **no-op closure** (cicatrix already resolved by Modo B migration)
- ✅ Gap 6 MATA GARUDA Gov 313 — apoptosi executed
- 📋 Gap 7 UUID Split-Brain Phase 0.5a — deferred

**5/7 closed** now (1, 2, 4, 5, 6).

## Sources

1. `launchctl list` on Pro 2026-05-12 15:14 WITA (15 matagaruda labels)
2. `ssh mini 'launchctl list'` 2026-05-12 15:14 WITA (5 matagaruda labels)
3. `comm -12` set intersection (empty — zero active-active)
4. `~/Library/LaunchAgents/com.matagaruda.intel-bridge.daily.plist` mtime 2026-05-06 14:28 (post-Modo-B)
