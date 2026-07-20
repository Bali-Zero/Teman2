---
date: 2026-07-20
domain: visa
client_case: none
sources:
  - apps/backend-rag/backend/app/routers/visa_check.py
  - apps/backend-rag/backend/services/visa_engine/evaluator.py
  - apps/backend-rag/backend/services/visa_engine/models.py
  - apps/backend-rag/backend/services/visa_engine/repository.py
  - apps/backend-rag/backend/services/visa_engine/bundle.py
  - apps/backend-rag/backend/services/visa_engine/compiler.py
  - apps/backend-rag/backend/services/visa_engine/enums.py
  - apps/backend-rag/backend/services/visa_check/match_tree.py
  - apps/backend-rag/backend/services/common/background.py
  - apps/backend-rag/backend/db/migrations_v2/252_visa_engine_write_substrate.sql
  - apps/backend-rag/backend/tests/services/visa_engine/test_write_substrate.py
---

# STEP-6c — SHADOW wiring design (task #5)

Wire the visa_engine evaluator to run FIRE-AND-FORGET on real POST /api/visa/match
requests, writing one row to visa_decisions (audit substrate), NEVER rendered,
NEVER logging raw PII facts. Flag-gated, default OFF. Ships dark. generator!=grader:
cross-family adversarial VERIFY on the diff before merge.

## 0. GROUND (verified on origin/main THIS session)
- evaluate() (evaluator.py:1001) + evaluate_product() (:530) exist; migration 252
  (visa_decisions/visa_decision_payloads/visa_source_records) applied. 2026-07-19 map
  superseded on "nothing to call" / "no substrate".
- visa_decisions is MINIMAL: NO facts_hmac/candidate_summary/idempotency_key/
  decision_hmac (deferred in header). Columns are enum/UUID/hash/ts + citations JSONB.
  => a visa_decisions row is PII-FREE by construction, self-sufficient; payloads +
  consent NOT required, NOT touched. No encryption key needed.
- Dedup: decision_id UUID NOT NULL UNIQUE (no idempotency_key) => INSERT ... ON
  CONFLICT (decision_id) DO NOTHING.
- Canonical passing INSERT (test_write_substrate::_insert_decision): decision_id,
  environment, engine_surface, engine_mode, rule_pack_id, ruleset_activation_id,
  rule_pack_sha256, verdict, citations, engine_version, effective_at, observed_at,
  evaluated_at. jurisdiction/decision_domain take DEFAULTs ID/IMMIGRATION_VISA.
- Trigger visa_decisions_pack_binding: rule_pack_id NOT NULL + activation NULL =>
  enforces only env/jur/domain match vs visa_rule_packs + (if set) rule_pack_sha256==
  pack sha. Activation-containment skipped when activation NULL. => writer sets
  rule_pack_id (real DB PK), leaves ruleset_activation_id NULL.
- FK caveat: visa_rule_packs.id is caller-supplied (no runtime insert caller; tests
  set id=payload.rule_pack_id but equality is NOT schema-enforced) => writer RESOLVES
  the DB PK from the DB, never trusts decision.rule_pack.rule_pack_id==DB id.

## 1. Scope
IN: env flag (default OFF), facts adapter (4 fields -> 35-key ApplicantFacts, rest
UNKNOWN), DB pack-ref resolver, evaluate() call, visa_decisions writer (INSERT ON
CONFLICT), fire-and-forget hook in submit_match, full tests. All shadow code in ONE
new module + a ~5-line router edit.
OUT (PENDING-ARMS, not this PR): encrypted visa_decision_payloads + crypto.py key mgmt
(STEP-6d, needed for prod-env packs' real identity_provider); DB-mode instant-rollback
lever (matters at ENFORCE); ENFORCE response-flip (ENFORCE-GATE); wiring /recommend
(Option B, zero traffic) + v2 /visa-oracle interview (Option C).

## 2. New module services/visa_engine/shadow.py
Constants: MATCH_MODE_ENV="VISA_ENGINE_MATCH_MODE" (OFF|SHADOW|ENFORCE; invalid->OFF);
MATCH_ENVIRONMENT_ENV="VISA_ENGINE_MATCH_ENVIRONMENT" (default "PRODUCTION");
ENGINE_VERSION="visa-engine/0.1.0" (owned SSOT for engine_version col; grep=0);
_SHADOW_ASSESSMENT_NAMESPACE=fixed UUID (assessment_id=uuid5(ns, match_hash));
_PURPOSE_REMAP: WORK_REMOTE->REMOTE_WORK, INVESTOR->INVESTMENT, WORK_EMPLOYEE->
EMPLOYMENT, FAMILY->FAMILY, LONG_TOURISM->TOURISM, RETIREMENT->RETIREMENT,
STUDENT->STUDY, OTHER->OTHER.
- resolve_match_shadow_enabled()->bool: re-read env per call; True iff
  getenv.strip().upper() in {SHADOW,ENFORCE}; ENFORCE logs-once "enforcement not
  implemented; running SHADOW-only".
- build_shadow_facts(*, nationality, purpose, duration_months, match_hash)->
  ApplicantFacts|None: build each of 35 alias-keyed fields DEFENSIVELY (Known in try;
  on failure -> UnknownFact), construct ApplicantFactsData once, then ApplicantFacts
  (schema_version="1.0.0", assessment_id=uuid5(ns,match_hash), collected_at=now,
  facts=data). KNOWN: person.nationalities (alpha-2 direct; alpha-3 best-effort ->
  else UNKNOWN NOT_PROVIDED); intent.purposes (remap); intent.stay_days
  (duration_months*30). Rest UNKNOWN NOT_ASKED. None only on total failure.
- _resolve_active_pack_binding(db_pool,*,environment,effective_at,observed_at)->
  _PackBinding|None: shadow-local SQL, documented MIRROR of load_active_rule_pack PLUS
  p.id (DB PK) + p.environment (+ a.id unused). Kept here (NOT repository.py) so the
  most-tested file stays untouched; duplication documented.
- _shadow_evaluate_match(db_pool,*,nationality,purpose,duration_months,match_hash)->
  None: WHOLE body try/except Exception->logger.warning (mirror
  visa_oracle._persist_session_create). now=utcnow; binding=_resolve(...env=
  MATCH_ENVIRONMENT) None->debug->return; facts=build_shadow_facts None->return;
  verified=verify_rule_pack(envelope, trust_store=StaticTrustStore.from_env(),
  observed_at=now) [RulePackVerificationError->warn->return]; compiled=
  build_compiled_pack(verified.pack) [RulePackCompilationError->warn->return];
  decision=evaluate(facts,compiled,effective_at=now,observed_at=now)
  [PlaceholderIdentityNotAllowedError->warn "prod pack needs crypto identity_provider
  (STEP-6d)"->return; Exception->warn->return]; await _save_shadow_decision(...);
  logger.info "shadow match decision written: hash=%s verdict=%s candidates=%d".
  NEVER log nationality/purpose/duration/facts.
- _save_shadow_decision(db_pool,*,decision,rule_pack_db_id,environment)->None:
  acquire own conn; INSERT canonical cols, engine_surface='MATCH',
  engine_mode='SHADOW' ALWAYS, rule_pack_id=rule_pack_db_id, ruleset_activation_id=
  NULL, rule_pack_sha256=decision.rule_pack.payload_sha256, verdict=
  decision.state.value, citations=json array of distinct source_record uuids from
  decision.candidates[].source_refs ([{"source_record_id":str}...] or []),
  engine_version=ENGINE_VERSION, effective/observed/evaluated_at from decision;
  ON CONFLICT (decision_id) DO NOTHING; citations cast $N::jsonb.
- maybe_spawn_shadow_match(db_pool,*,nationality,purpose,duration_months,match_hash)->
  None: WHOLE body try/except (must never break the request): if
  resolve_match_shadow_enabled(): spawn(_shadow_evaluate_match(...)).

## 3. Router edit app/routers/visa_check.py
import maybe_spawn_shadow_match. In submit_match, AFTER save_match try/except closes
and BEFORE proc_days=... (~line 262): call maybe_spawn_shadow_match(db_pool,
nationality=payload.nationality, purpose=payload.purpose,
duration_months=payload.duration_months, match_hash=saved.hash). Additive; response +
201 untouched.

## 4. Tests tests/services/visa_engine/test_shadow_match.py
Unit (no DB): resolve_match_shadow_enabled (OFF/missing/invalid->False; SHADOW/ENFORCE
->True; case-insensitive; ENFORCE warns); build_shadow_facts (8 remaps; duration->days;
nationality alpha2/alpha3/unmappable; assessment_id deterministic; exactly 3 KNOWN, 32
UNKNOWN).
Integration (real DB, visa_schema/db_pool fixtures): (1) writer: Decision via evaluate()
over gold compiled pack (placeholder identity, TEST env) whose rule_pack.rule_pack_id
is ALSO seeded as a visa_rule_packs row (reuse _insert_rule_pack; env/jur/domain/sha
match) -> _save_shadow_decision -> assert 1 row, engine_mode='SHADOW',
engine_surface='MATCH', verdict matches, FK ok; call twice -> still 1 (ON CONFLICT).
(2) resolver: seed pack+activation -> _resolve_active_pack_binding returns DB PK+env;
none -> None. (3) flow (mocked chain): monkeypatch resolver+verify/compile to return
gold CompiledRulePack, MODE=SHADOW -> 1 row; MODE unset -> 0; no pack -> 0, no raise.
(4) router: maybe_spawn spawns iff enabled; never raises. Real-DB INSERT passing IS
the proof the writer satisfies every 252 trigger/FK/CHECK. No raw facts in any
assertion/log.

## 5. Honest limitations (-> PENDING-ARMS)
- PROD today = NO-OP: (a) no rule pack activated (load_active_rule_pack->None);
  (b) prod-env pack's default _placeholder_identity_provider fails closed -> needs
  STEP-6d crypto identity provider. SHADOW yields real rows only for a TEST-env
  activated pack. Plumbing correct + fully tested; lights up when a pack is activated.
- Operator to see SHADOW signal: activate a rule pack; set
  VISA_ENGINE_TRUST_STORE_KEYS_JSON; set VISA_ENGINE_MATCH_MODE=SHADOW +
  VISA_ENGINE_MATCH_ENVIRONMENT; (later) runtime GRANT if ownership moves off
  backend_rag_v2.
