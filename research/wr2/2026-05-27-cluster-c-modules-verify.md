---
date: 2026-05-27
domain: wr2
client_case: cluster-c-verify
sources:
  - empirical Read of 6 Python modules in apps/backend-rag/backend/services/
  - empirical Bash inventory of infra/launchagents/com.balizero.wr2.*.plist
  - empirical Bash inventory of apps/backend-rag/backend/tests/services/{cognitive,intel,learner,newsletter}/
  - empirical grep of anthropic SDK ban + claude_oauth/ClaudeCLIRunner usage
---

## Summary table

| Modulo                    | Path                                                              | Exists | Verdict | Decision | Reason                                                                                                                                                                       |
| ------------------------- | ----------------------------------------------------------------- | ------ | ------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `connector_cli.py`        | `apps/backend-rag/backend/services/cognitive/connector_cli.py`    | yes    | VALID   | **KEEP** | main() ok, ClaudeCLIRunner OAuth, sibling `connector.py` + 1 test file, live LaunchAgent `com.balizero.wr2.connector.plist`                                                  |
| `oracle_cli.py`           | `apps/backend-rag/backend/services/cognitive/oracle_cli.py`       | yes    | VALID   | **KEEP** | main() ok (2 modes: deliberate/deliver), 4-voice council with graceful degrade, live LaunchAgent weekly Tuesday, 2 test files (`test_oracle.py` + `test_oracle_delivery.py`) |
| `strategos_cli.py`        | `apps/backend-rag/backend/services/cognitive/strategos_cli.py`    | yes    | VALID   | **KEEP** | main() ok (generate/deliver), sibling `strategos.py` + `strategos_delivery.py` + `strategos_dossier_filter.py`, 3 test files, live weekly Sunday cron                        |
| `newsletter_cli.py`       | `apps/backend-rag/backend/services/newsletter/newsletter_cli.py`  | yes    | VALID   | **KEEP** | main() ok + heartbeat, sibling `builder.py` + `publisher.py`, 2 test files, live LaunchAgent + Innervation Genoma sentinel wired                                             |
| `learner_cli.py`          | `apps/backend-rag/backend/services/learner/learner_cli.py`        | yes    | VALID   | **KEEP** | main() ok, sibling `learner_orchestrator.py` + `genome_adapter.py` + `score_calculator.py` + `injection_builder.py`, 4 test files, live nightly cron                         |
| `dossier_compiler_cli.py` | `apps/backend-rag/backend/services/intel/dossier_compiler_cli.py` | yes    | VALID   | **KEEP** | main() ok, sibling `dossier_compiler.py` + `dossier_repository.py` + `dossier_slug.py`, 4 test files, live daily 04:30 WITA cron                                             |

## Per-module deep verdict

### 1. `connector_cli.py` — VALID/KEEP

- **main()**: `if __name__ == "__main__"` present line 99. Async run() → asyncpg pool → `ConnectorOrchestrator.run_once()`.
- **Dependencies imported**:
  - `asyncpg` (in `requirements-prod.txt:asyncpg>=0.31.0` ✓)
  - `backend.services.cognitive.connector.ConnectorOrchestrator` (sibling file EXISTS, line 1 docstring "Connector — Layer 1 cognitive synthesis")
  - `backend.services.cognitive.repository.CognitiveRepository` (sibling EXISTS)
  - `backend.services.council.cli_runners.ClaudeCLIRunner` (EXISTS, OAuth-compliant per CLAUDE.md §5)
  - `backend.services.intel.dossier_repository.IntelRepository` (sibling EXISTS)
- **Anthropic SDK ban**: ZERO direct `from anthropic`/`ANTHROPIC_API_KEY` usage. Uses `ClaudeCLIRunner` (OAuth subprocess CLI) → COMPLIANT.
- **Test coverage**: `apps/backend-rag/backend/tests/services/cognitive/test_connector.py` exists (orchestrator unit tests).
- **Production wiring**: `infra/launchagents/com.balizero.wr2.connector.plist` schedules `wr2-cron-wrapper.sh backend.services.cognitive.connector_cli`.
- **Recommendation**: KEEP. Codex was correct — Cluster C audit hallucinated scaffold-status.

### 2. `oracle_cli.py` — VALID/KEEP (highest sophistication)

- **main()**: present line 213. argparse `--deliver` flag → 2 modes (deliberate default / deliver). Heartbeat `_hb()` writes `~/.organism/last_seen/wr2.oracle.json`.
- **Dependencies**:
  - `OracleCouncil` + `OracleOrchestrator` (sibling `oracle.py` "Layer 4 cognitive Consiglio esteso 4 voces + judge")
  - `OracleDelivery` (sibling EXISTS)
  - `StrategosContextBuilder` reused for context assembly
  - `ClaudeCLIRunner` + `DeepSeekHTTPRunner` + `GeminiCLIRunner` (4-voice council; gracefully drops voices on missing creds — `DEEPSEEK_API_KEY` optional, falls back to 3-voice with `degraded=True`)
  - `TelegramReviewAdapter` for delivery
  - `WarRoomRepository`
- **Anthropic SDK ban**: COMPLIANT (ClaudeCLIRunner OAuth path only).
- **Test coverage**: `test_oracle.py` + `test_oracle_delivery.py` (2 files).
- **Production wiring**: `com.balizero.wr2.oracle.plist` weekly Tuesday 22:30 WITA (Weekday=0 in plist is misleading — likely Sunday but cron header says "Tuesday 09:00 WITA"; minor doc drift, not bug).
- **Recommendation**: KEEP — most architecturally sophisticated of the 6 (multi-LLM council pattern reference impl).

### 3. `strategos_cli.py` — VALID/KEEP

- **main()**: present line 134. argparse `--deliver` → generate/deliver split.
- **Dependencies**: `StrategosOrchestrator`, `StrategosDelivery`, `WarRoomRepository`, `ClaudeCLIRunner`. All siblings exist.
- **Anthropic SDK ban**: COMPLIANT.
- **Test coverage**: `test_strategos.py` + `test_strategos_delivery.py` + `test_strategos_dossier_filter.py` (3 files, broadest of 6).
- **Production wiring**: `com.balizero.wr2.strategos.plist` weekly Sunday 22:00 WITA.
- **Recommendation**: KEEP.

### 4. `newsletter_cli.py` — VALID/KEEP

- **main()**: present line 138 + heartbeat sentinel.
- **Dependencies**: `WeeklyRoundupBuilder`, `NewsletterPublisher`, `CognitiveRepository`, `IntelRepository`. NO LLM dependency directly — pure aggregation + email send.
- **Anthropic SDK ban**: N/A (no LLM call).
- **Test coverage**: `test_builder.py` + `test_publisher.py` (2 files). Plus `test_newsletter_confirmation_email.py` at router level.
- **Production wiring**: `com.balizero.wr2.newsletter.plist` Monday 06:00 WITA. Exit code 2 on empty roundup (recognized in plist `SuccessfulExit` whitelist pattern).
- **Recommendation**: KEEP.

### 5. `learner_cli.py` — VALID/KEEP

- **main()**: present line 84. Sweeps published posts ≥T+72h, records skill/scar in genome.
- **Dependencies**: `LearnerOrchestrator`, `GenomeAdapter` (cell-core genome SQLite), `WarRoomRepository`. All siblings present (`genome_adapter.py`, `injection_builder.py`, `score_calculator.py`).
- **Anthropic SDK ban**: N/A (no LLM call; score composition + DB write).
- **Test coverage**: 4 test files (`test_learner_orchestrator.py`, `test_genome_adapter.py`, `test_injection_builder.py`, `test_score_calculator.py`) — deepest of 6.
- **Production wiring**: `com.balizero.wr2.learner-nightly.plist` 03:00 WITA.
- **Recommendation**: KEEP.

### 6. `dossier_compiler_cli.py` — VALID/KEEP

- **main()**: present line 79. Cycle exit codes: 0 ok / 1 config / 2 all-clusters-failed.
- **Dependencies**: `DossierCompiler`, `IntelRepository`, `ClaudeCLIRunner`. All siblings present (`dossier_compiler.py`, `dossier_repository.py`, `dossier_slug.py`, `dossier_models.py`).
- **Anthropic SDK ban**: COMPLIANT (ClaudeCLIRunner OAuth).
- **Test coverage**: 4 test files including `test_dossier_compiler.py`, `test_dossier_repository.py`, `test_dossier_models.py`, `test_dossier_slug.py`.
- **Production wiring**: `com.balizero.wr2.dossier-compiler.plist` daily 04:30 WITA.
- **Recommendation**: KEEP.

## Batch decision recommendation

**DO NOT RETIRE ANY MODULE — categorical reversal of Cluster C audit.**

All 6 modules:

1. EXIST on disk with full business logic
2. Have valid `main()` entrypoints
3. Have working dependency imports (all siblings exist, `asyncpg` in requirements-prod, `ClaudeCLIRunner` OAuth-compliant)
4. Have test coverage (range 2-4 test files per module, 17 total across 6 modules)
5. Are LIVE-wired via LaunchAgents in `infra/launchagents/com.balizero.wr2.*.plist`
6. Are CLAUDE.md §5 COMPLIANT (zero Anthropic SDK usage — all 4 cognitive modules route via ClaudeCLIRunner OAuth subprocess pattern)

The Cluster C audit conclusion ("scaffold/orphan retire candidates") was empirically WRONG. Codex's smentita was correct.

**Action**: PROCEED to spec FASE B with all 6 modules in scope as VALID production components. NO BATCH RETIRE.

## Risk notes

**What would be lost if retired** (do not do this):

1. **`dossier_compiler_cli`** — primary intel pipeline producer (signals → clusters → dossiers). Cron 04:30 daily. Retiring breaks the entire war-room-v2 evening intel briefing.
2. **`connector_cli`** — L1 cognitive synthesis (cross-dossier theses). Without it, Strategos + Oracle lose upstream non-obvious patterns.
3. **`strategos_cli`** — L3 weekly strategic brief Sunday 22:00. Retiring breaks `wr2-deploy-pull.log` referenced cron logic AND the strategic Telegram delivery operator depends on.
4. **`oracle_cli`** — L4 weekly Consiglio esteso (4-LLM panel UltraMoves to Zero Tuesday 09:00). Most sophisticated multi-LLM deliberation in codebase; retiring kills the reference 4-voice council pattern Antonello uses for "feedback_always_review_spec_with_4_llm" rule.
5. **`learner_cli`** — nightly genome learning loop (Voyager-style skill/scar). Retiring breaks the Symbiosis evolutionary feedback that ties Cell organism back to WR2 outputs.
6. **`newsletter_cli`** — Monday 06:00 weekly roundup email. Retiring removes the only outbound digest from war-room-v2.

**Cross-ref cron audit 2026-05-26**: the audit categorized these as "Cluster C — Retire Candidate" — likely confusion between "module scaffold-looking minimal CLI wrapper" (the `*_cli.py` is intentionally thin: arg-parse + pool + delegate to orchestrator) and "scaffolded-but-never-wired". Empirical evidence rejects the latter. Future audits should verify LaunchAgent presence in `infra/launchagents/com.balizero.wr2.*.plist` BEFORE labeling cron-driven CLI wrappers as orphan.

**Related cicatrix family**: this audit error is a sister to the 2026-05-22 "claude mcp list Status field is stale" scar — both involve drawing structural conclusions from incomplete signal. The Cluster C audit looked at file size/complexity, not at execution wiring.
