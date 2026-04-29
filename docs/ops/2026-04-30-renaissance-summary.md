# Pro Automations Renaissance — Final Report (2026-04-29 / 2026-04-30)

> Canonical record of the multi-PR cleanup + self-learning unblock that
> ran across two sessions (2026-04-29 evening, 2026-04-30 night WITA).
> Source of truth for "what changed" between commit `caa684f6d` and
> commit `ac2b712bd` on `main`.

## TL;DR

**7 PR merged in main**, all auto-merged SQUASH under L2 autonomous
contract. **No human intervention required** beyond the user's
go/no-go on each phase. Numbers verified live on Pro:

- **−233 cron runs/giorno** removed (dead code or oversampled)
- **compliance-ops latency 30 s → 1.78 s** (live measured 2026-04-30 02:25 WITA)
- **29 log paths** moved from volatile `/tmp/` to persistent `~/logs/cron-tmp/`
- **3 self-learning chains unstuck**: gap_scanner (chain #1), cell-organism Cortex/Critic (#2), WR2 canva-apply→measurer→learner-nightly (#3)
- **Audit narrative correction**: gap_scanner Layer B was reported as "100% gap forever" but live test showed 73% FRESH — system had already healed via the 2026-04-19 PATH fix; audit was stale

---

## Phase A: foundational fixes (already merged before this session)

Pre-existing context. Not re-described here.

| PR        | Scope                                    |
| --------- | ---------------------------------------- |
| #358 (A1) | Machine-aware paths Pro/Air + DLQ PATH   |
| #359 (A2) | Port `t4_monitor` SDK → claude OAuth CLI |

## Phase B: tooling baseline

| PR        | Scope                                                   |
| --------- | ------------------------------------------------------- |
| #361 (B1) | Extend `lint_launchagents.sh` with 4 audit-driven rules |

## Phase C: cleanup (this session, all merged)

| PR            | Scope                                                                                                                                                                                                                                                                                                                  | Live effect                                                                                                                                                          |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **#367 (C5)** | Dead code uninstall: 4 cron deleted (core-guardian, weekly-review, fly-restart-loop-detector cron dup, system-doctor cron-wrapper). 2 cron rate-reduced (intel-feed-processor `*/30→0 */2`, vision-doc-extractor `5 *→5 */6`).                                                                                         | −233 cron runs/giorno. Crontab 251 → 243 lines.                                                                                                                      |
| **#368 (C3)** | Source `~/.nuzantara-secrets.env` in `run_peraturan_ingestion.sh` + `run_heartbeat_check.sh`. Add `GOOGLE_APPLICATION_CREDENTIALS` to Pro secrets file.                                                                                                                                                                | Sblocca cron Sun 21:30 UTC peraturan ingestion (3 windows perse recuperabili). 4 NEVER_RAN + 7 CRITICAL + 1 DEAD pipelines diventano visibili al prossimo heartbeat. |
| **#369 (C4)** | Patch 4 cron-agent-python script su Pro (shadow infra, NOT in git): `imigrasi_monitor.py` drop peraturan.go.id source (HTTP 500 da 10gg), `bi_exchange_rate.py` drop BI native API tier, `compliance_ops.py` drop unused session_id (claude --print 30s timeout per nulla), `daily_ops.py` fix logging false-positive. | compliance-ops live verified 30 s → 1.78 s. Backups in `~/.cron-agent-python.backups/20260429T180126Z/`.                                                             |
| **#371 (E1)** | Crontab Pro: 29 cron lines `/tmp/cron-*.log` → `~/logs/cron-tmp/<NAME>.log`. Plus 2 outliers (legal_radar, openclaw-bridge). NLM CLI arg drift fix: `yt_monitor.py` (`--notebook → positional + --youtube`), `multimodal_pipeline.py` (`studio create infographic → infographic create`).                              | Log persistono cross-reboot. yt_monitor può ingestare video YT (era 0/180 prima). multimodal_pipeline può creare infographic/mindmap.                                |

## Phase D: self-learning chains unblock (this session, all merged)

| PR            | Scope                                                                                                                                                                                                                                                                                                                                                             | Live effect                                                                                                                                                                                                                            |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **#372 (D1)** | `gap_scanner.py`: per-query timeout 90 s → 180 s, per-topic progress logging, source `~/.nuzantara-secrets.env` in wrapper. **Riformulato dopo discovery live**: l'audit diceva "Layer B broken, 100% gap because nlm not in PATH" ma run del 2026-04-30 02:30 WITA ha prodotto 73% FRESH — narrativa audit obsoleta dopo cron-runner.sh PATH fix del 2026-04-19. | Layer B funzionale verified 56 topics → 41 FRESH/4 AGING/5 STALE/6 GAP. Sblocca self-learning chain #1.                                                                                                                                |
| **#374 (D3)** | `apps/cell/cell/cortex/critic.py:317`: regex extraction `{.*}` con `re.DOTALL` prima di `json.loads`, stesso pattern di `strategy_mutator.py:180-185`. Sostituisce `parsed = json.loads(text)` raw che falliva su markdown fence/prose Ollama output.                                                                                                             | 25/25 unit test passano. Sblocca self-learning chain #2: cell-organism può flippare `red → yellow/green` perché Critic ora forma expectations valide.                                                                                  |
| **#375 (D2)** | `scripts/wr2_canva_desktop_apply.py`: wrap `_focus_claude_and_send_command` in 5×30 s retry envelope. `_verify_frontmost()` interno intatto — guard di sicurezza preservato.                                                                                                                                                                                      | Sblocca self-learning chain #3: canva-apply tollera transient focus theft. Cascade audit: canva broken → measurer 0 posts → learner-nightly 0 posts_considered → genome non aggiornato. Ora resilient a 2 minuti di focus theft burst. |

## Architectural caveats discovered & documented

### `~/scripts/cron-agent-python/` is NOT in git

31 Python files, ~10k lines, running production cron jobs since
2026-04-14, never versioned. PR-C4 patches 4 files via reproducible
`scripts/ops/pr-c4-api-degraded-patch.sh` (in-place Python rewrite,
idempotent, py_compile validated, backup) so changes survive Pro
rebuilds — but doesn't solve the underlying versioning gap.

**Future PR**: promote the directory to repo under
`scripts/cron-agent-python/` with CI guardrail that fails when Pro's
working tree drifts from HEAD. Out of scope for renaissance.

### Pro crontab is owned by user, edited live with `crontab -e`, NOT version-controlled

PR-C5 and PR-E1 modify it via reproducible shell scripts in
`scripts/ops/pr-{c5,e1}-*.sh`: snapshot before edit, awk-based
in-place rewrite, sanity gates (line-count invariant, residual
pattern grep), post-install verify. Backups in
`~/.crontab.backups/<UTC-ts>.cron`.

### Audit can be stale

The 2026-04-29 audit was the SSOT for prioritization, but live
verification on 2026-04-30 found at least 2 cases where the system
had already healed:

1. **gap_scanner Layer B** — audit said "100% gap forever, nlm CLI
   not in PATH". Live 02:30 WITA test → 73% FRESH (cron-runner.sh
   PATH was fixed 2026-04-19 21:40, before the audit; the audit
   referenced the pre-fix log).
2. **WR2 fact-extractor / fact-checker** — audit said "BROKEN, plist
   references missing scripts". Already quarantined to
   `~/Library/LaunchAgents/.disabled/` by sessione 2026-04-29.

**Lesson saved as scar**: `mai più trust audit alla cieca — verify
live`. The `research/ops/2026-04-29-pro-automations-audit/` artifact
is still authoritative for what was _observed_ on 2026-04-29, but
its narratives about _root cause_ may have been outdated by
intermediate fixes.

## Live verification checklist (post-merge, 24–72 h soak)

| Signal                                | What to check                                                                                                    | Where                                                      |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| compliance-ops latency                | Each cron run finishes < 5 s with no `session_error` warning                                                     | `~/logs/cron-agent-python/compliance-ops.cron.log`         |
| bi-exchange-rate cleanup              | No more `bi_api_failed_fallback_html` warnings; HTML scrape primary                                              | `~/logs/cron-agent-python/bi-exchange-rate.log`            |
| imigrasi-monitor cleanup              | No more `peraturan_fetch_error error="500 Internal Server Error"`                                                | `~/logs/cron-agent-python/imigrasi-monitor.log`            |
| daily-ops false-positive fix          | `fetch_renewals error=None` on empty `[]` results                                                                | `~/logs/cron-agent-python/daily-ops.cron.log`              |
| heartbeat alerts visible              | Telegram alerts to chat 1125336968 fire on CRITICAL/DEAD                                                         | Telegram                                                   |
| peraturan_ingestion success           | Sun 2026-05-03 21:30 UTC: log shows `Google credentials loaded`                                                  | `apps/evaluator/nlm_deep_research/peraturan_ingestion.log` |
| Logs persist cross-reboot             | After next Pro reboot, `~/logs/cron-tmp/*.log` survives, `/tmp/` would have wiped                                | `~/logs/cron-tmp/`                                         |
| yt_monitor ingest works               | New `Ingested <url> into <notebook>` lines instead of `No such option: --notebook`                               | `~/logs/cron-tmp/yt-monitor.log`                           |
| multimodal create works               | Successful `infographic`/`mindmap` creates instead of `No such command 'create'`                                 | `~/logs/cron-tmp/multimodal.log`                           |
| gap_scanner Layer B per-topic logging | `[domain X/8] topic — CLASSIFICATION` lines, not silent gap                                                      | Next Sunday `~/logs/cron-tmp/gap-scanner.log`              |
| cell-organism health                  | `health` field in cell pulse state flips `red → yellow/green` once Critic forms expectations                     | `~/.agent/decisions/state/cell.json`                       |
| Cortex episodes                       | Count resumes incrementing past 21,316 plateau                                                                   | `~/.cell/cortex.db`                                        |
| canva-apply retry visible             | Either single `Draft X rendered` (5/5 succeed) or `attempt N/5 failed: ... succeeded on attempt N/5` (recovered) | `~/logs/wr2_canva_desktop_apply.log`                       |
| learner-nightly resumes               | `posts_considered > 0` in next nightly run after canva-apply lands a post and ages into T+72h                    | `~/logs/wr2_learner_nightly.log`                           |

## Backups (rollback paths)

| PR        | Backup                                                                            | Rollback command                                                                                                                                                       |
| --------- | --------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| #367 (C5) | `~/.crontab.backups/20260429T172541Z.cron`                                        | `ssh pro 'crontab "$HOME/.crontab.backups/20260429T172541Z.cron"'`                                                                                                     |
| #368 (C3) | `~/.nuzantara-secrets.env.bak.20260430-pre-c3`                                    | `ssh pro 'cp ~/.nuzantara-secrets.env.bak.20260430-pre-c3 ~/.nuzantara-secrets.env && chmod 600 ~/.nuzantara-secrets.env'` (env), `git revert <commit>` (script edits) |
| #369 (C4) | `~/.cron-agent-python.backups/20260429T180126Z/*.bak`                             | `ssh pro 'cp ~/.cron-agent-python.backups/20260429T180126Z/<file>.bak ~/scripts/cron-agent-python/<file>'`                                                             |
| #371 (E1) | `~/.crontab.backups/20260429T181551Z.cron` (crontab); `git revert` (script edits) | as above                                                                                                                                                               |
| #372 (D1) | `git revert b127aef35`                                                            | one-liner, no live state                                                                                                                                               |
| #374 (D3) | `git revert 447d5313f`                                                            | one-liner                                                                                                                                                              |
| #375 (D2) | `git revert ac2b712bd`                                                            | one-liner                                                                                                                                                              |

## Per-PR documentation index

- [PR-C5 dead code uninstall](2026-04-30-pr-c5-dead-code.md)
- [PR-C3 missing-env source secrets](2026-04-30-pr-c3-missing-env.md)
- [PR-C4 API degraded fixes](2026-04-30-pr-c4-api-degraded.md)
- [PR-E1 /tmp logs cleanup + NLM CLI arg drift](2026-04-30-pr-e1-cleanup.md)
- [PR-D1 gap_scanner Layer B resilience](2026-04-30-pr-d1-gap-scanner-resilience.md)
- [PR-D3 Cell Critic JSON parse resilience](2026-04-30-pr-d3-cell-critic-json-parse.md)
- [PR-D2 WR2 canva-apply focus retry envelope](2026-04-30-pr-d2-canva-focus-retry.md)

## Reproducible operation scripts

- `scripts/ops/pr-c5-dead-code-disable.sh` — crontab cleanup, idempotent
- `scripts/ops/pr-c4-api-degraded-patch.sh` — 4 in-place Python rewrites on Pro shadow infra
- `scripts/ops/pr-e1-cleanup-tmp-logs.sh` — crontab `/tmp` → `~/logs/cron-tmp/` rewrite

## Remaining work (out of scope, candidate future PRs)

- Promote `~/scripts/cron-agent-python/` (Pro) to repo
- Fix crontab comment on Pro (`Sun 19:00 UTC` is wrong, cron uses WITA)
- Investigate Sunday 2026-04-26 missing gap_scanner Layer B/Remediate run (no log)
- `renewal-alerts` LaunchAgent query reconcile against `/api/crm/expiry-alerts`
- WR2 fact-extractor / fact-checker plist restore or ufficiale uninstall
- Wider Ollama JSON-output cleanup (`skill_library.py`, `goal_generator.py`, `curiosity_engine.py`)
- Migrate canva-apply from GUI automation to Canva REST API (architectural — Canva needs to ship element-level text-replacement API first)

## Reference

- Plan: `~/.claude/plans/RESUME-renaissance-2026-04-29.md`
- Audit SSOT: `research/ops/2026-04-29-pro-automations-audit/automations-audit-2026-04-29.csv`
- L2 autonomous contract: `AUTONOMOUS_OPS.md` (active since 2026-04-21)
- Symbiosis: `SYMBIOSIS.md` (8 inviolable laws)
- Cicatrix scars: `.claude/rules/cicatrix-scars.md`
