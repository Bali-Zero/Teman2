# Backend Compliance + Intel E2E — Design Spec

**Date:** 2026-04-18
**Session:** PB2 (Pro) — Opus 4.7 (1M ctx) xhigh effort
**Worktree branch:** `pro/backend-compliance-intel-e2e`
**Repo:** `~/Desktop/nuzantara` (Pro)

## Scope

Unify compliance alert generation, add predictive feedback loop, harden Intel ingestion pipeline with 3-tier validators, automate LKPM ready-pack, and correlate revenue estimation with compliance status.

### In-scope directories

- `apps/backend-rag/backend/services/compliance/`
- `apps/backend-rag/backend/services/intel/`
- `apps/backend-rag/backend/app/routers/compliance_alerts.py` (new), `lkpm.py` (mod), `intel.py` (mod)
- `apps/backend-rag/backend/db/migrations_v2/` — migrations 114, 115, 116 (SQL, active loader target)

### Out-of-scope (reserved for Air / PB1 / future)

- `backend/core/`, `services/rag/`, `services/observability/`, `core/reasoning.py`, `core/reranker.py` (Air)
- `routers/dream.py|newsletter.py|debug.py` (Air B2)
- `middleware/`, `self_healing/` (PB1 Pro)
- `services/misc/proactive_compliance_monitor.py` — **5-line deprecation shim only** (documented exception)

## Current state (baseline)

- `AlertGeneratorService` holds alerts in-memory (`self.alerts: dict[str, ComplianceAlert]`) — **lost on restart**.
- `templates.py` has **hardcoded prices** (2M/5M/500K IDR) — violates "PricingTool only" rule.
- Alert dispatch logic duplicated across `alert_generator.py`, `lkpm_deadline_notifier.py`, `visa_expiry_team_notifier.py`.
- `predictive_engine.py` uses hardcoded thresholds, no feedback loop.
- Intel pipeline lacks regex/citation/KG cross-ref validators; no source whitelist.
- LKPM ready-pack requires human step for PDF/Excel; no automated Drive upload + email.
- Revenue estimator not correlated to compliance status.
- Legacy migrations last number: `113_intel_dossiers.py` (`backend/migrations/`, frozen/manual). `migrations_v2/` last: `110_lkpm_allowlist_krisna.sql`. Next global-monotonic available: **114+**.
- Infrastructure already present: `notification_alerts` (m071), `notification_prefs` (m110), `notification_log` (m111), `kg_proposals` (m108), `guardian_decisions` (m098b).

## 11 design decisions (from brainstorming)

| #   | Decision                                                                                                                                     |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Hybrid persistence: new `compliance_alerts` (m114) + link via `ref` convention on existing `notification_log` (m111)                         |
| 2   | Per-category deterministic threshold autotune, kill-switch gated, weekly cron                                                                |
| 3   | Intel validators: regex hard-gate + citation retry+soft-fail + kg cross-ref soft-signal                                                      |
| 4   | reportlab Platypus in dedicated `lkpm_pdf_builder.py` (no new deps)                                                                          |
| 5   | Revenue risk bands (green/yellow/orange/red) with fixed weights (1.0/0.8/0.5/0.2)                                                            |
| 6   | Per-category dedup: visa by `document_id`, lkpm by `reporting_period`, others `category:client_id + 24h window + severity-upgrade promotion` |
| 7   | i18n dict-based `TEMPLATE_REGISTRY` IT/EN/ID with fallback chain `requested → en → it`                                                       |
| 8   | Integration tests: shared test DB + transaction rollback per test                                                                            |
| 9   | NB-2 validation spec-time + `nb2_ref` audit field on dataclasses (visa/BKPM categories)                                                      |
| 10  | Deprecation shim on `proactive_compliance_monitor.py` (5-line exception to scope)                                                            |
| 11  | Dispatch: team channels severity-gated (code-side, unconditional) + client email/wa gated by `notification_prefs` (m110) toggles             |

## Architecture — module map

```
apps/backend-rag/backend/services/compliance/
├── alerts_engine.py        [NEW]  Single entrypoint: generate_alerts(forecasts) -> list[Alert]
├── alert_repository.py     [NEW]  Repo pattern on compliance_alerts (asyncpg, BaseRepository)
├── alert_dedup.py          [NEW]  Per-category dedup + severity upgrade logic
├── alert_dispatcher.py     [NEW]  Channel dispatch (Telegram/Email/In-app) + notification_prefs
├── alert_feedback.py       [NEW]  Outcome tracking + weekly retraining job
├── alert_metrics.py        [NEW]  Precision/recall/F1 per category
├── templates.py            [MOD]  Remove hardcoded prices → PricingTool lookup
├── templates_i18n.py       [NEW]  TEMPLATE_REGISTRY {category: {lang: msg}} + Jinja
├── severity_calculator.py  [KEEP]
├── predictive_engine.py    [MOD]  Read thresholds from system_settings
├── renewal_rules.py        [MOD]  Add nb2_ref: str field to RenewalRule
├── revenue_estimator.py    [MOD]  + classify_client_risk() + get_weighted_revenue()
├── lkpm_pdf_builder.py     [NEW]  reportlab Platypus
├── lkpm_ready_pack.py      [MOD]  Invokes pdf_builder + openpyxl + Drive + Brevo
├── alert_generator.py      [MOD]  Thin shim → alerts_engine (DeprecationWarning)
├── exceptions.py           [NEW]  AlertGenerationError, AlertDispatchError, etc.
└── ...others unchanged

apps/backend-rag/backend/services/intel/
├── intel_validators.py        [NEW]  3-tier validator
├── intel_source_whitelist.py  [NEW]  Gov.id domains + known aggregators
├── intel_kg_bridge.py         [NEW]  Valid intel → kg_proposals (m108)
├── intel_staging_service.py   [MOD]  Hook validators + whitelist + bridge
└── ...others unchanged

apps/backend-rag/backend/app/routers/
├── compliance_alerts.py    [NEW]  POST outcome, GET list/detail/metrics, POST retrain
├── lkpm.py                 [MOD]  POST /ready-pack/{client_id}
└── intel.py                [MOD]  GET /staging/{id}/validation, POST /staging/{id}/revalidate

apps/backend-rag/backend/services/misc/
└── proactive_compliance_monitor.py [MOD-5 lines] DeprecationWarning + redirect

apps/backend-rag/backend/db/migrations_v2/        [active loader target]
├── 114_compliance_alerts.sql         [NEW]
├── 115_alert_outcomes.sql            [NEW]
└── 116_intel_validator_log.sql       [NEW]
```

> **Migration path note.** The active migration system is `backend/db/migrations_v2/*.sql`
> (loaded automatically by `MigrationManager.discover_migrations`). The legacy
> `backend/migrations/migration_*.py` directory is frozen and manual-apply only. Numbers
> `112` and `113` are already taken in legacy (`migration_112_war_room_tables.py`,
> `migration_113_intel_dossiers.py`), so this plan uses **114/115/116** for a
> monotonic global number. Rollback SQL is **mandatory** for any number > 111
> (enforced by `migration_base.py:LEGACY_NO_ROLLBACK_WHITELIST`).

## Data schema

### Migration 114 — `compliance_alerts` (`114_compliance_alerts.sql`)

```sql
CREATE TABLE compliance_alerts (
    alert_id            TEXT PRIMARY KEY,
    client_id           INTEGER NOT NULL REFERENCES clients(id),
    category            TEXT NOT NULL,
    severity            TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending',
    deadline            DATE NOT NULL,
    days_until          INTEGER NOT NULL,
    compliance_item_ref TEXT,
    dedup_key           TEXT NOT NULL,
    message_it          TEXT,
    message_en          TEXT,
    message_id          TEXT,
    suggested_action    TEXT,
    estimated_cost_idr  BIGINT,
    evidence_refs       JSONB DEFAULT '[]',
    nb2_ref             TEXT,
    upgrade_count       INTEGER NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at             TIMESTAMPTZ,
    acknowledged_at     TIMESTAMPTZ,
    resolved_at         TIMESTAMPTZ,

    CONSTRAINT ck_severity CHECK (severity IN ('info','warning','urgent','critical')),
    CONSTRAINT ck_status   CHECK (status IN ('pending','sent','acknowledged','resolved','expired'))
);

CREATE UNIQUE INDEX ux_compliance_alerts_dedup_active
    ON compliance_alerts (dedup_key)
    WHERE status IN ('pending','sent','acknowledged');

CREATE INDEX ix_compliance_alerts_client    ON compliance_alerts (client_id, created_at DESC);
CREATE INDEX ix_compliance_alerts_deadline  ON compliance_alerts (deadline) WHERE status != 'resolved';
CREATE INDEX ix_compliance_alerts_category_sev ON compliance_alerts (category, severity, created_at DESC);
```

UPSERT settings keys seeded in upgrade():

- `compliance_alert_autotune_enabled` (default `"false"`)
- `compliance_alert_autotune_window_days` (default `"90"`)
- `compliance_alert_threshold_urgent_{visa_expiry,tax_filing,lkpm,license_renewal,permit_renewal,regulatory_change}` (initialized to current `severity_calculator.py` values: 7)

### Migration 115 — `alert_outcomes` (`115_alert_outcomes.sql`)

```sql
CREATE TABLE alert_outcomes (
    outcome_id   BIGSERIAL PRIMARY KEY,
    alert_id     TEXT NOT NULL REFERENCES compliance_alerts(alert_id) ON DELETE CASCADE,
    outcome      TEXT NOT NULL,
    actioned_by  TEXT,
    actioned_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    note         TEXT,
    metadata     JSONB DEFAULT '{}',

    CONSTRAINT ck_outcome CHECK (outcome IN ('dismissed','acted','expired'))
);

CREATE INDEX ix_alert_outcomes_alert ON alert_outcomes (alert_id);
CREATE INDEX ix_alert_outcomes_time  ON alert_outcomes (actioned_at DESC);
```

> **`notification_log` NOT altered.** Existing `notification_log` (m111 legacy, schema
> `user_id UUID, channel VARCHAR(20), ref VARCHAR(128), sent_at`) already has `ref` as
> a natural dedup/link column. The dispatcher writes the compliance linkage via the
> convention `ref = f"compliance_alert:{alert_id}"`. No ALTER TABLE needed, no FK.
> Metrics/delivery joins use this string-matched `ref` pattern.

### Migration 116 — `intel_validator_log` (`116_intel_validator_log.sql`)

```sql
CREATE TABLE intel_validator_log (
    log_id         BIGSERIAL PRIMARY KEY,
    staging_id     BIGINT NOT NULL,
    validator_tier TEXT NOT NULL,
    result         TEXT NOT NULL,
    score          NUMERIC(3,2),
    details        JSONB DEFAULT '{}',
    checked_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_tier   CHECK (validator_tier IN ('regex','citation','kg_crossref')),
    CONSTRAINT ck_result CHECK (result IN ('pass','fail','soft_fail','skip'))
);

CREATE INDEX ix_intel_validator_log_staging ON intel_validator_log (staging_id, checked_at DESC);
```

All three migrations are `.sql` files in `backend/db/migrations_v2/` and MUST include a
rollback section (`-- === ROLLBACK ===`) with complete `DROP` statements. Enforced by
`migration_base.py:LEGACY_NO_ROLLBACK_WHITELIST` for any migration number > 111.

### Dedup keys per category

| Category                                                            | dedup_key format                                       | Window               |
| ------------------------------------------------------------------- | ------------------------------------------------------ | -------------------- |
| visa_expiry                                                         | `visa:<client_id>:<document_id>`                       | lifetime of document |
| lkpm                                                                | `lkpm:<client_id>:<reporting_period>` (e.g. `2026-Q1`) | lifetime of period   |
| tax_filing                                                          | `tax_filing:<client_id>:<tax_year>:<period>`           | lifetime of period   |
| license_renewal, permit_renewal, regulatory_change, document_expiry | `<category>:<client_id>`                               | 24h rolling          |

## Flows

### Flow A — Generation

```
Cron WITA or API call
  → PredictiveEngine.scan()                 [reads thresholds from system_settings]
    → list[ComplianceForecast]
  → AlertsEngine.generate_alerts(forecasts)
    for each forecast:
      build dedup_key per category
      existing = AlertRepository.find_active_by_dedup_key(dedup_key)
      if existing and new_severity > existing.severity:
          AlertDedup.promote(existing, new_severity)
          upgrade_count += 1
          AlertDispatcher.dispatch(existing)   # re-dispatch
      elif existing:
          skip (return existing)
      else:
          build Alert (render templates_i18n IT/EN/ID, estimated_cost from PricingTool)
          AlertRepository.insert(alert)
          AlertDispatcher.dispatch(alert)
  → return list[Alert]
```

### Flow B — Dispatch

Two logical audiences: **team channels** (Telegram + in-app for staff) and **client channels**
(email + wa direct to the customer). `notification_prefs` (m110) controls only client-side
opt-in; team channels are severity-gated unconditionally in code.

```
AlertDispatcher.dispatch(alert):
  lang = client.preferred_language or 'it'

  # 1. TEAM channels (severity-gated, always sent, not user-configurable)
  team_channels = severity_default_team(alert.severity)
    # critical → [telegram_owner, inapp_team]
    # urgent   → [telegram_team, inapp_team]
    # warning  → [inapp_team]
    # info     → [inapp_team]

  # 2. CLIENT channels (gated by notification_prefs m110 + severity)
  portal_user_id = resolve_portal_user(client_id)  # clients.portal_user_id
  client_channels = []
  if portal_user_id:
      prefs = SELECT * FROM notification_prefs WHERE user_id = portal_user_id
      severity_allows = alert.severity IN ('critical','urgent','warning')
      if severity_allows:
          if prefs and prefs.email_enabled (default True):
              client_channels.append('email_client')
          if prefs and prefs.wa_enabled:
              client_channels.append('wa_client')
  # if no portal_user_id: skip client channels, log info (cannot notify client)

  # 3. DISPATCH
  for ch in team_channels + client_channels:
      ref = f"compliance_alert:{alert.alert_id}:{ch}"
      # m111 notification_log dedup check
      if NotificationLog.already_sent(portal_user_id, ch, ref, within_hours=24):
          continue   # skip (already notified)
      try:
          send via (brevo_email_service | telegram_service | inapp_service | wa_service)
          insert notification_log(user_id=portal_user_id or SYSTEM_UUID, channel=ch, ref=ref)
      except narrow_exception as e:
          log warning, continue

  alert.status = 'sent' if any_channel_succeeded else unchanged
```

**Notes on existing infrastructure**:

- `notification_log` schema (m111): `user_id UUID, channel VARCHAR(20), ref VARCHAR(128), sent_at`. No FK to `compliance_alerts` — linkage is via string pattern on `ref`.
- `notification_prefs` schema (m110): only `email_enabled, wa_enabled, wa_phone`. No severity-level overrides — severity gating lives in the dispatcher code.
- For team-only channels (`telegram_owner`, `telegram_team`, `inapp_team`), use a constant `SYSTEM_TEAM_UUID` as `user_id` so the ledger stays uniform.

### Flow C — Outcome + retraining

```
POST /api/compliance/alerts/{id}/outcome
  → AlertRepository.update_status(alert_id, acknowledged|resolved)
  → insert alert_outcomes(outcome, actioned_by, note)
  → emit event compliance_alert_outcome (EventBus)

Weekly cron Sun 03:00 WITA (staggered vs Judgement Day 16:00):
  if system_settings.compliance_alert_autotune_enabled != 'true': skip
  AlertFeedback.retrain():
    for category in categories:
        window = last 90d outcomes
        precision = acted / (acted + dismissed)   # ignore 'expired'
        if precision < 0.6:
            threshold_urgent[category] += 1        # fire later
        elif precision > 0.9 and sample_size > 50:
            threshold_urgent[category] -= 1        # fire earlier
        clamp to [1, 30]
        log to guardian_decisions (m098b) for audit
    invalidate_cache("zantara:compliance_thresholds:*")
```

### Flow D — Intel validation

```
IntelStagingService.ingest(doc):
  score = 0.0

  # Tier 1: regex schema (hard gate)
  if not IntelValidators.regex_schema(doc):
      log fail; staging.status = 'rejected'; return
  score += 0.3

  # Tier 2: citation check (retry-aware)
  result = IntelValidators.citation_check(doc)  # httpx 3x retry exp backoff
  if result == 'pass':
      score += 0.4
  elif result == 'definitive_fail':   # 404/403/410
      log fail (no score)
  else:                               # 5xx/timeout exhausted
      log soft_fail; schedule retry +24h

  # Tier 3: KG cross-ref (soft signal)
  entities = kg_auto_expansion.find_entities(doc)
  if entities:
      score += 0.3
      intel_kg_bridge.propose(kg_proposals, doc, entities)  # m108, NOT auto-approved

  # Source whitelist check
  if doc.source_domain not in INTEL_SOURCE_WHITELIST:
      needs_review = True

  # Final status
  if score >= 0.6 and not needs_review:
      staging.status = 'valid'
  elif score >= 0.3:
      staging.status = 'needs_review'
  else:
      staging.status = 'rejected'
```

### Flow E — LKPM ready-pack

```
POST /api/lkpm/ready-pack/{client_id}?period=2026-Q1
  → LkpmValidator.check_completeness(client_id, period)
      fail → 422 with missing_fields list
  → LkpmDataCollector.gather(client_id, period) → dict
  → LkpmPdfBuilder.build(data) → bytes (reportlab Platypus)
  → openpyxl build → bytes
  → google_drive_service.upload_to_client_folder(client_id, pdf, xlsx) → drive_url
  → brevo_email_service.send(
        from='zantara@balizero.com',
        name='Zantara',
        to=client.email,
        subject=template_i18n['lkpm_readypack_subject'][lang],
        body=template_i18n['lkpm_readypack_body'][lang],
        attachments=[drive_url]   # link not bytes
    )
  → EventBus.emit('lkpm_readypack_generated', {...})
  → return {drive_url, pdf_sha256, xlsx_sha256, email_sent_to}
```

## API surface

### New router: `compliance_alerts.py`

```
POST   /api/compliance/alerts/{alert_id}/outcome
         Body: {outcome: "acted|dismissed", note?: str}
         RBAC: admin all, team own clients
GET    /api/compliance/alerts
         Query: client_id?, category?, severity?, status?, limit=50, offset=0
         RBAC: scope by assigned_to
GET    /api/compliance/alerts/{alert_id}
         Returns: alert + outcomes + notification_log entries
GET    /api/compliance/alerts/metrics
         Query: window_days=90, category?
         RBAC: admin only
         Returns: {by_category: {cat: {precision, recall, f1, sample_size, threshold_current}}, overall: {...}}
POST   /api/compliance/alerts/retrain
         Body: {dry_run: bool, category?: str}
         RBAC: admin only
         Gated by: compliance_alert_autotune_enabled
```

### Modified: `lkpm.py`

```
POST   /api/lkpm/ready-pack/{client_id}
         Body: {period: "2026-Q1", send_email: bool=true, dry_run: bool=false}
         422 if LkpmValidator fails
```

### Modified: `intel.py`

```
GET    /api/intel/staging/{staging_id}/validation
         RBAC: admin
POST   /api/intel/staging/{staging_id}/revalidate
         Body: {tier?: "regex|citation|kg_crossref"}
         RBAC: admin
```

### EventBus channels (new PG NOTIFY)

- `compliance_alert_created` — `{alert_id, client_id, category, severity}`
- `compliance_alert_outcome` — `{alert_id, outcome, actioned_by}`
- `intel_validation_complete` — `{staging_id, status, score}`
- `lkpm_readypack_generated` — `{client_id, period, drive_url}`

Handler: `services/events/handlers/compliance_handlers.py` (new).

### Cache invalidation namespaces

- `zantara:compliance_alerts:{client_id}:*`
- `zantara:compliance_metrics:*`
- `zantara:intel_validation:{staging_id}:*`
- `zantara:compliance_thresholds:*`

Enforced via `@cache_invalidating` decorator (PR #103 cache invalidation discipline).

### Integrations

- `PricingTool.get_price(category_key)` — populates `estimated_cost_idr` (NULL if absent; template omits cost line).
- `google_drive_service` — LKPM ready-pack upload. Folder from `clients.drive_folder_id`.
- `brevo_email_service` — sender forced to `zantara@balizero.com / Zantara`.
- `telegram_service` — owner `1125336968` for CRITICAL, team channel for URGENT.
- `kg_auto_expansion` — Intel Tier 3 cross-ref. Output → `kg_proposals` (m108), not auto-promoted.
- `notification_prefs` (m110) — client-side email/wa opt-in (no severity overrides; severity gating lives in dispatcher code).
- `notification_log` (m111) — delivery trace via `ref = f"compliance_alert:{alert_id}:{channel}"` convention; no schema change.
- `guardian_decisions` (m098b) — retrain audit log.

### RBAC matrix

| Endpoint                  | Admin | Team                      | Client |
| ------------------------- | ----- | ------------------------- | ------ |
| POST outcome              | all   | own (`assigned_to` match) | ❌     |
| GET alerts list/detail    | all   | own                       | ❌     |
| GET metrics               | ✅    | ❌                        | ❌     |
| POST retrain              | ✅    | ❌                        | ❌     |
| POST lkpm ready-pack      | all   | own                       | ❌     |
| GET/POST intel validation | ✅    | ❌                        | ❌     |

## Error handling

Principles:

1. Narrow exceptions (PR #101 `broad_except_tighten`).
2. Graceful degradation on external I/O (Brevo/Telegram/Drive failure ≠ alert failure).
3. DB write failures are fatal — rollback + log to `guardian_decisions`.

| Component                        | Error                        | Behavior                                                         |
| -------------------------------- | ---------------------------- | ---------------------------------------------------------------- |
| `AlertsEngine.generate_alerts`   | `PredictiveEngine.scan` fail | log ERROR, return `[]`, emit guardian_decisions                  |
| `AlertRepository.insert`         | `UniqueViolation` on dedup   | catch, re-query existing, return (race-safe)                     |
| `AlertRepository.insert`         | other asyncpg error          | raise (retry on next cron)                                       |
| `AlertDispatcher.dispatch`       | Brevo 5xx                    | log, notification_log.status='failed', continue other channels   |
| `AlertDispatcher.dispatch`       | Telegram 429                 | respect Retry-After, 1 retry, then failed                        |
| `AlertDispatcher.dispatch`       | all channels fail            | alert.status stays 'pending', cron retry (max 3, then 'expired') |
| `IntelValidators.citation_check` | 5xx/timeout                  | retry 3× exp backoff, then soft_fail + schedule +24h             |
| `IntelValidators.citation_check` | 4xx definitive               | no retry                                                         |
| `IntelValidators.kg_crossref`    | `kg_auto_expansion` timeout  | skip tier (score unchanged)                                      |
| `LkpmPdfBuilder.build`           | reportlab error              | raise, endpoint returns 500                                      |
| `LkpmReadyPack`                  | Drive upload fail            | continue, email with warning                                     |
| `LkpmReadyPack`                  | Brevo send fail              | drive_url still returned, `email_sent_to=null`                   |
| `AlertFeedback.retrain`          | any error                    | catch, log, abort retrain, NO threshold change                   |

Custom exceptions in `compliance/exceptions.py`:

- `AlertGenerationError`, `AlertDispatchError`, `IntelValidationError`, `LkpmValidationError`.

## Testing strategy

Pattern: TDD (skill `superpowers:test-driven-development`). Coverage gate **80%+** on `services/compliance/` and `services/intel/`.

DB: shared test DB + transaction rollback per test (conftest fixture yields connection, rolls back at teardown). Mocks: Brevo, Telegram, Drive, httpx (citation), kg_auto_expansion.

### Test file layout

```
tests/services/compliance/
├── conftest.py                               [fixtures: db_tx, sample_client, sample_forecast]
├── test_alerts_engine.py                     [~15 tests]
├── test_alert_repository.py                  [~10 tests, race-safe UniqueViolation]
├── test_alert_dedup.py                       [~8 tests, per-category + promote-on-upgrade]
├── test_alert_dispatcher.py                  [~12 tests, mock Brevo/Telegram]
├── test_alert_feedback.py                    [~10 tests, kill-switch + clamp]
├── test_alert_metrics.py                     [~6 tests]
├── test_templates_i18n.py                    [~8 tests, fallback chain]
├── test_revenue_estimator_bands.py           [~6 tests]
├── test_lkpm_pdf_builder.py                  [~5 tests, bytes roundtrip]
├── test_lkpm_ready_pack_automation.py        [~8 tests, integration]
└── test_compliance_integration.py            [~5 end-to-end scenarios]

tests/services/intel/
├── test_intel_validators.py                  [~12 tests]
├── test_intel_source_whitelist.py            [~6 tests]
├── test_intel_kg_bridge.py                   [~5 tests]
└── test_intel_staging_service_validated.py   [~8 tests]

tests/app/routers/
├── test_compliance_alerts_router.py          [~10 tests, RBAC coverage]
├── test_compliance_lkpm_readypack.py         [~5 tests]
└── test_intel_validation_router.py           [~5 tests]

tests/fixtures/intel_staging/                 [10 anon docs: 5 valid, 3 borderline, 2 invalid]
```

Integration test tagged `@pytest.mark.integration`; required services: PostgreSQL 5432, Redis 6379, Qdrant 6333 (Pro locally).

## Build sequence — 8 commits

1. **`migrations(v2): 114+115+116 compliance_alerts, alert_outcomes, intel_validator_log`**
   - 3 `.sql` files in `backend/db/migrations_v2/` with complete `-- === ROLLBACK ===` sections.
   - `114_compliance_alerts.sql`, `115_alert_outcomes.sql`, `116_intel_validator_log.sql`.
   - Upgrade + rollback verified via `MigrationManager` test harness.
   - Blocker for everything else.

2. **`feat(compliance): alerts_engine core + repository + templates i18n + dedup`**
   - `alerts_engine.py`, `alert_repository.py`, `alert_dedup.py`, `templates_i18n.py`.
   - Remove hardcoded prices from `templates.py` → PricingTool lookup.
   - NB-2 validation for any visa/BKPM rule touched; `nb2_ref` populated on RenewalRule.

3. **`feat(compliance): dispatcher + notification_prefs integration`**
   - `alert_dispatcher.py` with:
     - team-channel severity gating (code-side, not `notification_prefs`-driven)
     - client-channel filtering via `notification_prefs` (m110) `email_enabled` / `wa_enabled`
     - `notification_log` dedup convention `ref = f"compliance_alert:{alert_id}:{channel}"`

4. **`feat(compliance): predictive feedback loop — outcomes + autotune`**
   - `alert_feedback.py`, `alert_metrics.py`.
   - Cron `scripts/compliance_alert_retrain.sh` (Sun 03:00 WITA).
   - Router `compliance_alerts.py` (outcome, metrics, retrain endpoints).

5. **`feat(intel): 3-tier validators + source whitelist + kg bridge`**
   - `intel_validators.py`, `intel_source_whitelist.py`, `intel_kg_bridge.py`.
   - Hook in `intel_staging_service.py`.
   - Router `intel.py` additions.
   - Fixtures: 10 anon staging docs.

6. **`feat(compliance): lkpm ready-pack automation — pdf + drive + email`**
   - `lkpm_pdf_builder.py`, `lkpm_ready_pack.py` extended.
   - Router `lkpm.py` `/ready-pack/{client_id}` endpoint.

7. **`feat(compliance): revenue-compliance correlation — risk bands`**
   - `revenue_estimator.py` extended: `classify_client_risk()`, `get_weighted_revenue()`.

8. **`refactor(compliance): deprecation shims + integration tests + docs`**
   - `alert_generator.py` → shim with DeprecationWarning.
   - `services/misc/proactive_compliance_monitor.py` → 5-line shim (scope exception).
   - End-to-end integration test `test_compliance_integration.py`.
   - Update `apps/backend-rag/CLAUDE.md` with alerts_engine note.

After each commit: GREEN pytest + import chain check (`python -c "from backend.app.dependencies import get_current_user; print('OK')"`).

## Verification before completion

Skill `superpowers:verification-before-completion`: every "done" claim must include pytest output. Required commands:

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/compliance/ backend/tests/services/intel/ \
    backend/tests/app/routers/test_compliance* backend/tests/app/routers/test_intel* \
    -v --tb=short --cov=backend/services/compliance --cov=backend/services/intel \
    --cov-fail-under=80

# Import chain (scar PR #56/#62 prevention)
python -c "from backend.app.dependencies import get_current_user; print('OK')"
```

## Hard constraints

- **NB-2 validation mandatory** for visa/BKPM rules (skill: notebook_query MCP).
- **No hardcoded government prices** — PricingTool only.
- **Email sender**: always `zantara@balizero.com / Zantara`.
- **Telegram**: existing channel-map, no new bots.
- **OAuth-only** for Claude calls.
- **Migration numbering monotonic**, rollback enforced (PR #99).
- **No scope bleed** to Air/PB1 directories.
- **i18n**: IT/EN/ID for every user-facing string.
- **Deploy**: from `apps/backend-rag/`, not monorepo root. Deploy itself **not part of this PR**.

## PR target

Title: `feat(backend): compliance + intel e2e — unified alerts, predictive feedback loop, LKPM automation, intel validators`

Base: `main`. Strategy: squash OR 8-commit preserved (reviewer's choice).

## Open questions / known risks

- **Risk**: `proactive_compliance_monitor.py` scope exception — 5-line shim touch documented and accepted during brainstorming (decision #10). If reviewer objects, fall back to option C (no touch + follow-up task for PB3).
- **Risk**: Autotune thresholds could regress during first 90d of data collection. Mitigation: `compliance_alert_autotune_enabled` defaults to `"false"`; must be explicitly enabled by admin.
- **Risk**: Intel citation_check retries could saturate outbound HTTP on slow gov.id responses. Mitigation: backoff bounded to 3 retries, 24h schedule for transient failures.
- **Assumption**: `clients.preferred_language` column exists and is populated. If missing: fallback chain is `None → 'en' → 'it'` (handled in `templates_i18n.py`). Task 2 verifies the column in the first migration preamble; absent → spawn `114b_clients_preferred_language.sql`.
- **Assumption**: `clients.drive_folder_id` populated for LKPM ready-pack target clients. If missing: LKPM ready-pack returns 409 with actionable error.
- **Assumption**: `clients.portal_user_id UUID` exists and maps clients to portal users for `notification_prefs` / `notification_log` lookups. If absent: dispatcher skips client channels with a logged warning, team channels still fire.
