# Bali Zero Dispatch normalization (7-vs-9 LaunchAgents) — Sprint 0 Track B1

**Date:** 2026-05-02 · **Author:** Sprint 0 Air session (Claude Opus 4.7 1M)
**Reference:** brainstorm 2026-05-02 round 2 § "Bali Zero Dispatch 7-vs-9 LaunchAgents"

## TL;DR

The brainstorm round 1 talked about "7 LaunchAgents" but enumerated 9 names.
Empirically:

- **`infra/launchagents/com.balizero.wr2.*.plist` in repo:** **13 plist files** (versioned)
- **`~/Library/LaunchAgents/com.balizero.wr2.*.plist` on Pro (round 1 audit):** **16 plist registered in launchd**

Difference: **4 plist live on Pro that are NOT versioned in the repo, +1 in
the repo that is NOT deployed on Pro**:

| In Pro (live) | In repo (versioned) | Status |
|---|---|---|
| `canva-apply` | — (repo has `canva-renderer`, different name) | drift |
| `draft-generator` | — | drift |
| `image-generator` | — | drift |
| `topic-selector` | — | drift |
| `connector` | `connector` | aligned |
| `dossier-compiler` | `dossier-compiler` | aligned |
| `hardening` | `hardening` | aligned |
| `learner-nightly` | `learner-nightly` | aligned |
| `measurer` | `measurer` | aligned |
| `newsletter` | `newsletter` | aligned |
| `oracle` | `oracle` | aligned |
| `pg-proxy` | `pg-proxy` | aligned (daemon, KeepAlive=true) |
| `sla-worker` | `sla-worker` | aligned |
| `strategos` | `strategos` | aligned |
| `supervisor` | `supervisor` | aligned (KeepAlive=dict) |
| `trend-hunter` | `trend-hunter` | aligned |
| — | `canva-renderer` | repo-only (orphan) |

The 4 Pro-only plist are backed by Python files that DO exist in the repo
under `scripts/wr2_canva_apply.py`, `scripts/wr2_draft_generator.py`,
`scripts/wr2_image_generator.py`, `scripts/wr2_topic_selector.py`.
The plist wrappers were deployed on Pro but never committed to
`infra/launchagents/`. This is the drift to close.

## Schedules and runtime types (from `infra/launchagents/` plist parse)

```
canva-renderer    | KA=unset   | every 300s             | -lc                                    (orphan in repo)
connector         | KA=False   | cron H=4 M=0 W=*       | backend.services.cognitive.connector_cli
dossier-compiler  | KA=False   | cron H=4 M=30 W=*      | backend.services.intel.dossier_compiler_cli
hardening         | KA=False   | every 21600s (=6h)     | scripts/wr2-hardening-chain.sh
learner-nightly   | KA=False   | cron H=3 M=0 W=*       | backend.services.learner.learner_cli
measurer          | KA=False   | every 21600s (=6h)     | backend.services.measurer.scheduler_cli
newsletter        | KA=False   | cron H=9 M=0 W=1 (Mon) | backend.services.newsletter.newsletter_cli
oracle            | KA=False   | cron H=22 M=30 W=0     | backend.services.cognitive.oracle_cli
pg-proxy          | KA=True    | RunAtLoad (daemon)     | proxy
sla-worker        | KA=False   | every 1800s (=30min)   | backend.services.review.sla_worker_cli
strategos         | KA=False   | cron H=22 M=0 W=0      | backend.services.cognitive.strategos_cli
supervisor        | KA=dict    | RunAtLoad              | scripts/wr2_supervisor.py
trend-hunter      | KA=False   | every 7200s (=2h)      | backend.services.intel.trend_hunter.cli
```

Pro-only (no plist file in repo, schedules inferred from script
content):

```
canva-apply       | (drift)    | likely cron daily        | scripts/wr2_canva_apply.py
draft-generator   | (drift)    | likely cron daily        | scripts/wr2_draft_generator.py
image-generator   | (drift)    | likely cron daily        | scripts/wr2_image_generator.py
topic-selector    | (drift)    | likely cron Sun/Mon AM   | scripts/wr2_topic_selector.py
```

## Mapping → Cognitive Levels (per round 2 synthesis)

The brainstorm v2 maps WR2 organelle to cognitive levels:

| Cognitive Level | Organelle |
|---|---|
| **L4 (organism)** | `oracle` (single decisional voice) |
| **L3 (system)** | `strategos` (planner) |
| **L2 (organ)** | `supervisor` (orchestrator), `pg-proxy` (event substrate) |
| **L1 (tissue)** | `connector` (Genome→Bali bridge), `learner-nightly`, `trend-hunter`, `measurer`, `dossier-compiler` |
| **operative organelle** | `newsletter`, `sla-worker`, `hardening`, `canva-apply`, `canva-renderer`, `draft-generator`, `image-generator`, `topic-selector` |

The "7-9 LaunchAgents" count in the round 1 briefing corresponds to the
*intentional cognitive set* — the set excluding pure operational/distribution
LaunchAgents (newsletter/canva/draft/image/topic). The actual cognitive
backbone is **9 organelle** (oracle, strategos, supervisor, pg-proxy,
connector, learner-nightly, trend-hunter, measurer, dossier-compiler).
Operational organelle bring the file count to 13 (repo) or 16 (Pro live).

The brainstorm count "7" in round 1 was a transcription mistake; the
"9 names" enumerated also drifted because the operational LaunchAgents
were swapped between rounds. **The right answer for cognitive cell-mapping
is 9, not 7 nor 13/16.**

## Verdict (verdetto finale)

| Question | Answer |
|---|---|
| Is "7" or "9" the canonical count for WR2 cognitive organelle? | **9** (oracle + strategos + supervisor + pg-proxy + connector + learner-nightly + trend-hunter + measurer + dossier-compiler) |
| Is the rest (newsletter/canva-*/draft/image/topic) part of WR2? | **Yes**, but as **operational organelle** (sub-cell level), not cell candidate themselves. They are workflow steps, not autonomous reasoning units. |
| Should the 4 Pro-only plist be committed to repo? | **Yes** — Sprint 0 follow-up (separate PR or Sprint 1 W0). |
| Should `canva-renderer` (repo-only) be removed? | **Maybe** — first investigate whether it was renamed to `canva-apply` (probable). If yes, delete the orphan. |
| Cognitive Level mapping survives round 2? | **Yes** — oracle=L4, strategos=L3, connector=L1 confirmed. |

## Action items (manual, post-merge)

### Immediate (blocking Sprint 1 — WR2 mapping doc)

1. **Antonello: rsync the 4 Pro-only plist into `infra/launchagents/`** (read-only fetch, then commit):
   ```bash
   rsync -av pro:~/Library/LaunchAgents/com.balizero.wr2.canva-apply.plist \
              pro:~/Library/LaunchAgents/com.balizero.wr2.draft-generator.plist \
              pro:~/Library/LaunchAgents/com.balizero.wr2.image-generator.plist \
              pro:~/Library/LaunchAgents/com.balizero.wr2.topic-selector.plist \
              infra/launchagents/
   ```
   Then verify `plutil -lint infra/launchagents/com.balizero.wr2.*.plist` passes.

2. **Antonello: clarify `canva-renderer` vs `canva-apply`** — likely a rename
   that left a dead artifact in repo. Run `git log infra/launchagents/com.balizero.wr2.canva-renderer.plist`
   to find the original commit, decide whether to delete or rename.

### Sprint 1 / Sprint 2 (WR2 mapping work)

3. Lock the cognitive Level mapping in
   `apps/organism/organism/organs_registry.yaml` (file renamed 2026-05-08
   IG-3 from `genome.yaml`) once finalized.
4. Track each organelle's IPC pattern in Sprint 0 Track B2
   (filesystem vs PG NOTIFY). The 9 cognitive ones MUST emit through
   `EventBus.PG_CHANNEL_MAP` to respect the Event-driven Law; the
   operational ones can continue to be cron-style if their output is
   files (e.g. canva exports).

## Out-of-scope today

- Reverse-engineering schedules of the 4 Pro-only plist without their
  plist files in hand. Will be done in Step 1 above.
- Verifying which of the 16 are KeepAlive=true via `launchctl list`. Pro
  is SSH-unreachable at audit time; verification is post-merge.

## References

- `infra/launchagents/com.balizero.wr2.*.plist` (13 versioned)
- `~/Library/LaunchAgents/com.balizero.wr2.*.plist` on Pro (16 live)
- `scripts/wr2_*.py` (operational organelle Python sources)
- `apps/backend-rag/backend/services/cognitive/{oracle,strategos,connector}_cli.py` (cognitive organelle entry points)
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/04_automation_inventory_complete.md` § "Bali Zero Dispatch"
- `docs/audits/2026-05-02-cell-openclaw-brainstorm/99b_synthesis_v2.md` § "Convergenza forte: WR2 LA mature non sub-module"
