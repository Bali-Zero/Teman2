# scripts/nlm_activation/

Wrapper scripts for the NLM elevation activation runbook
(`docs/operations/NLM_ELEVATION_ACTIVATION.md`).

Each file is **committed but not scheduled**. To activate any one of them,
add the corresponding crontab entry by hand — see the header comment of
each script for the exact `crontab -e` line.

| Script | Stage | Cron schedule (when activated) | Cost / risk |
|---|---|---|---|
| `truth_dashboard_digest.sh` | 1+ | `0 7 * * *` | Free, read-only |
| `run_canary_all.sh` | 3 | `30 4 * * 1-6` | NLM CLI cost (OAuth) |
| `run_cep_daily.sh` | 5 | `0 6 * * *` | DeepSeek ~$0.50/run |
| `collect_cep_answers.py` | 5 | (called by run_cep_daily.sh) | Free |
| `nlm_shadow_run_all.sh` | 6 | `30 3 * * 1-6` | DeepSeek + OpenAI ~$3/night |

## Why not scheduled automatically

The runbook prescribes a sequenced rollout (Stage 1 → 7) where each stage
must be observed for hours/days before the next can begin. Pre-installing
crontab entries would bypass that gating and risk:
- Stage 6 shadow extractor running before CEP baseline is established →
  no way to detect quality regression.
- Stage 4 oracle gate firing before canary verifications populate the
  freshness state → all queries get refused.
- Cost spikes (DeepSeek $50+/month) if shadow extractor runs for weeks
  before being needed.

## Activation order

Read `docs/operations/NLM_ELEVATION_ACTIVATION.md` first. The order is:

1. Merge all 6 PRs (#243-#248 series).
2. Stage 1: deploy. Wait 24h. No cron added yet.
3. Stage 2: heartbeat truth automatic — no cron needed.
4. Stage 2 day 2: enable `truth_dashboard_digest.sh`. Read for 48h to
   build trust in the signal.
5. Stage 3: enable `run_canary_all.sh`. Wait 7 days for canaries to
   stabilize.
6. Stage 4: `fly secrets set NLM_ENFORCE_FRESHNESS=1`.
7. Stage 5: enable `run_cep_daily.sh`. Wait 7 days for CEP baseline.
8. Stage 6: enable `nlm_shadow_run_all.sh`. Wait 7 days for collection
   to fill.
9. Stage 7: `fly secrets set NLM_SHADOW_RETRIEVAL_ENABLED=1`.

Total time from Stage 1 to Stage 7: minimum ~25 days.

## Rollback

To disable any cron: `crontab -e`, comment out the line, save. The
underlying scripts and code stay; only the schedule disappears. The two
env-var-gated stages (4 and 7) roll back via `fly secrets unset`.

## Bypass for testing

Each script supports manual invocation outside cron:

```bash
# Test canary on one NB
PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.freshness_monitor \
    --verify-ingestion <NOTEBOOK_UUID> --no-cleanup

# Test CEP cycle without writing report
PYTHONPATH=. python -m apps.evaluator.cep.run_cep --dry-run

# Test shadow extractor on one domain
PYTHONPATH=. python scripts/nlm_shadow_extractor.py --notebook tax --limit 5

# Print truth dashboard
PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.heartbeat_monitor --truth
```

All four manual paths work at any stage and never modify production state
in destructive ways (canary cleans up its source, dry-run skips writes,
extractor only upserts to its dedicated collection).
