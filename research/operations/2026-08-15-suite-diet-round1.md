---
date: 2026-08-15
domain: operations
client_case: internal — Merge-OS v3 build order, §6 step 3 ("suite diet from the --durations=50 data")
discovered_by: "Sonnet 5 implementer (M5, lane ops/suite-diet-gate), dispatched to build the remaining Merge-OS v3 step-3 slice"
sources:
  - "research/operations/2026-08-14-merge-os-v3-research-council.md §C1/§6 step 3"
  - "GitHub Actions run 31860900090 (push to main, 2026-08-15T03:05-03:33Z), job 94953999894 'Backend Tests (Python)', raw log via gh api repos/Bali-Zero/Teman2/actions/jobs/94953999894/logs"
  - "~/.nuzantara-mq/suite-growth/20260814T211800Z.json on Pro (scripts/suite_growth_probe.py's first live record)"
  - "apps/backend-rag/pytest.ini, apps/backend-rag/backend/llm/retry_handler.py, apps/backend-rag/backend/middleware/pii_scanner.py, apps/backend-rag/backend/tests/compliance/test_no_clock_in_parametrize.py, apps/backend-rag/backend/tests/services/intake/test_drive_autocreate_apply.py — read live this session"
adversarial_review: codex
---

# Suite diet, round 1 — top-50 durations, top-10 assessed

## 0. What this is and what it explicitly is NOT

This is the `--durations=50` slice of Merge-OS v3 build order step 3
(`research/operations/2026-08-14-merge-os-v3-research-council.md` §6 step 3),
called out there as "both 08-10 refuters' first pick, still undone." It is a
**report**, not a cure. Per the council's own scope line for this whole step —
**"NO auto-deletion on slowness/flake alone"** — nothing in this document
deletes, skips, marks-slow, or quarantines a single test. Every "candidate"
below is exactly that: a candidate, with the evidence that makes it one, left
for a human (or a future, narrowly-scoped PR) to act on individually. Deleting
a test is a decision this report is not authorized to make, and — see §2 —
would not even buy back much of the suite's actual cost.

## 1. Where the data came from

The council doc's own step-3 text names two acceptable sources: "il record
suite-growth su Pro e/o … un run locale `--durations=50` della suite backend."
This report used a third, more direct source that satisfies the same intent
without spending a fresh ~28-minute local run on M5 (memory:
`ops_organ_ward_round` / the general "saturazione M5" caution against running
heavy suites alongside other work): **`.github/workflows/tests.yml`'s own
`Run unit tests` step already invokes pytest with `--durations=50`** (added
2026-08 per that step's own comment, "round-3 queue-acceleration plan, L3")
and tees the full output into the job's own console log. The most recent
completed `push`-to-`main` run of `tests.yml` — run `31860900090`, job
`94953999894` ("Backend Tests (Python)"), `2026-08-15T03:05:27Z` →
`2026-08-15T03:33:52Z` (28m25s wall) — was pulled via
`gh api repos/Bali-Zero/Teman2/actions/jobs/94953999894/logs
--allow-escape-sequences` and the `slowest 50 durations` section extracted
verbatim. This is real production CI data, not a synthetic/local
approximation, and it cross-validates the suite-growth telemetry organ: this
one run's 28.42min sits almost exactly on the `p95_minutes: 28.19` the Pro
record (`20260814T211800Z.json`) reports for the current 7-day window — one
more sample inside the distribution that record already describes, not an
independent number.

Test-file count, for scale: `find apps/backend-rag/backend/tests -name
'test_*.py' | wc -l` → **1,361** files, measured this session (2026-08-15);
the suite-growth record measured **1,359** the day before — the file count is
still climbing, consistent with the ~10%/week wall-time growth that motivated
this whole build step. That is a FILE count, not a test count — a static scan
(`grep -rhoE '^\s*(async\s+)?def test_' backend/tests | wc -l`, run and
independently re-verified this session) finds **20,459** `test_*` functions
under `backend/tests` alone, before parametrize expansion. §2 below uses this
number, not the file count, for the "many small tests" framing.

## 2. The headline finding: the top-50 is a small slice of the step that runs it

**Corrected 2026-08-15 after adversarial review (see §7) — the first draft of
this section divided the top-50's duration by the whole JOB's wall time
(1,705s / 28.42min), which mixes two different clocks: `--durations=50`
times only `pytest`, one step among many (checkout, `uv`/`pip` install,
import-chain smoke check, LLM-cost-tracking check, coverage report, artifact
upload — all visible in the same job log, before and after the pytest step).
The corrected version below compares the top-50 against the wall time of the
SAME step that produced it.**

The `Run unit tests` step itself — bounded in the raw log between its own
`##[group]` open (`2026-08-15T03:09:08.947Z`) and the next step's group open
(`2026-08-15T03:33:34.110Z`, "Check coverage threshold") — ran **1,465.2
seconds (24.42 minutes)**. Summing all 50 durations in the CI-reported list:
**219.7 seconds (3.66 minutes)** — **15.0%** of that step's own wall time
(`219.72 / 1465.16 = 0.1500`, recomputed independently during adversarial
review and confirmed here). Even a (hypothetical, not proposed) deletion of
every single one of the top-50 slowest individual tests would not touch most
of the pytest step's cost, which is the aggregate of the other roughly
20,400+ test functions that are each individually fast but collectively
expensive (fixture setup/teardown, DB round-trips, per-test collection and
import overhead — none of which `--durations` singles out because none of
them, alone, is slow) — plus setup/teardown time attached to tests that never
made the top 50 at all, which this report has not measured and does not
claim to have measured. This is the concrete evidence behind the council's
own "NO auto-deletion on slowness alone" rule: chasing the durations tail is
chasing at most 15% of the pytest step's own cost, and an unmeasured (likely
smaller, per the point above) fraction of the whole job. A future lever aimed
at the other ~85% (import-time cost, fixture scope, DB container reuse,
parallelization, and — separately — the ~4 minutes of non-pytest job
overhead outside the `Run unit tests` step) belongs in a separate,
differently-shaped investigation — out of this report's scope, and flagged
here so it is not silently lost.

## 3. Top 50, as reported by CI (verbatim, `slowest 50 durations` section)

```
12.34s call     backend/tests/unit/llm/test_s12_solidification.py::TestFix2RetryClassification::test_rate_limit_error_is_retried
10.33s call     backend/tests/compliance/test_no_clock_in_parametrize.py::test_no_test_decorator_reads_the_clock
10.07s call     backend/tests/unit/core/legal/test_redos_anchor_patterns.py::TestPayloadSweep::test_control_the_sweep_rejects_the_pre_fix_quadratic
10.06s call     backend/tests/services/intake/test_drive_autocreate_apply.py::test_post_drain_attestation_failure_freezes_lot
9.35s call     backend/tests/compliance/test_no_clock_in_parametrize.py::test_no_test_decorator_reads_a_random_value
8.67s call     backend/tests/unit/app/setup/test_light_router_startup_imports.py::test_light_router_registration_does_not_eager_import_portal_document_pipeline
7.75s call     backend/tests/unit/prompts/test_prompt_source_parity.py::test_no_consumer_imports_raw_template_outside_prompt_manager
7.66s call     backend/tests/unit/middleware/test_pii_scanner.py::TestScanText::test_detect_ktp_16_digits
7.64s call     backend/tests/integration/test_endpoints_reachable.py::TestRoutesAreMounted::test_all_concrete_get_routes_resolve
7.23s call     backend/tests/compliance/test_golden_rules.py::test_golden_rule_8_no_print_statements
7.12s call     backend/tests/db/test_jsonb_double_encoding_class_guard.py::test_no_offenders_in_repo
6.21s call     backend/tests/compliance/test_golden_rules.py::test_golden_rule_5_type_hints
6.09s call     backend/tests/compliance/test_golden_rules.py::test_golden_rule_3_no_relative_imports
6.06s call     backend/tests/scripts/visa_engine/test_gold_replay_driver.py::test_offline_replay_uses_highest_signed_pack_without_claiming_it_is_active
5.95s call     backend/tests/scripts/visa_engine/test_gold_replay_driver.py::test_offline_replay_applies_public_policy_adapter_to_every_persona
5.94s call     backend/tests/services/visa_engine/test_evaluate_endpoint.py::test_runtime_openapi_and_exported_contract_share_five_decision_conditionals
5.54s call     backend/tests/services/visa_engine/test_evaluate_endpoint.py::test_runtime_role_cannot_spoof_retention_capability_gucs
5.01s call     backend/tests/services/council/test_cli_runners.py::test_subprocess_runner_timeout_kills_process
4.76s call     backend/tests/scripts/visa_engine/test_gold_replay_driver.py::test_offline_replay_passes_effective_review_flags_to_public_adapters[0-expected_flags0]
4.75s call     backend/tests/scripts/visa_engine/test_gold_replay_driver.py::test_offline_replay_passes_effective_review_flags_to_public_adapters[2-expected_flags1]
4.48s call     backend/tests/security/test_route_authz_coverage.py::test_every_mutating_route_has_a_declared_authz_posture
4.28s call     backend/tests/test_no_global_cwd_mutation.py::test_no_test_module_chdirs_at_import_time
4.01s call     backend/tests/services/article_composer/test_claude_client.py::test_call_claude_with_retry_wraps_transient_deepseek_errors
3.58s call     backend/tests/services/visa_engine/test_evaluate_endpoint.py::test_retention_binding_legal_hold_and_bounded_purge_are_audited
3.46s call     backend/tests/unit/core/legal/test_redos_anchor_patterns.py::TestPayloadSweep::test_no_cured_pattern_is_superlinear_on_any_swept_payload[PASAL_PATTERN]
3.06s call     backend/tests/compliance/test_golden_rules.py::test_golden_rule_6_no_hardcoded_secrets
3.01s call     backend/tests/services/kg_monitoring/test_scraper_wave2.py::TestUARotationDuringFetch::test_every_attempt_uses_rotated_ua
3.01s call     backend/tests/unit/services/search/test_search_service_comprehensive.py::TestSearchService::test_init_bm25_retry_with_backoff
2.58s call     backend/tests/unit/core/test_embeddings.py::TestEmbeddingsGenerator::test_generate_embeddings_openai_batch
2.55s call     backend/tests/services/intake/test_intake_worker.py::test_kill9_reclaim_no_job_lost
2.51s call     backend/tests/unit/app/routers/test_observed_shell.py::test_router_registered_in_both_include_functions
2.46s call     backend/tests/services/rag/test_autonomous_executor.py::TestRollback::test_rollback_on_step_failure
2.22s call     backend/tests/services/visa_engine/test_evaluate_endpoint.py::test_database_clocks_and_elapsed_deadlines_fail_closed
2.13s call     backend/tests/unit/services/rag/agentic/test_create_agentic_rag_team_crm_flag_gate.py::test_flag_on_does_not_remove_existing_tools
2.08s call     backend/tests/unit/scripts/test_kbli_documents_cure.py::test_the_obligations_are_actually_wired_into_the_document_the_channel_reads
2.01s call     backend/tests/services/kg_monitoring/test_scraper.py::TestLegalScraper::test_fetch_with_retry_success
1.91s call     backend/tests/unit/llm/test_zantara_ai_client.py::test_stream_api_key_leak
1.90s call     backend/tests/integration/multi_service/test_rag_memory_kg_integration.py::TestRAGMemoryKGIntegration::test_memory_facts_influence_rag_response
1.88s call     backend/tests/scripts/visa_engine/test_operational_preflight.py::test_every_forbidden_sensitive_table_grant_fails_its_named_check
1.81s call     backend/tests/unit/services/rag/agentic/test_orchestrator.py::TestEventValidationErrors::test_stream_query_validation_error
1.72s call     backend/tests/test_process_split.py::test_rag_has_health_route
1.69s call     backend/tests/unit/core/legal/test_redos_anchor_patterns.py::TestLinearity::test_the_cure_is_what_makes_it_fast[BAB_PATTERN]
1.61s setup    backend/tests/services/visa_engine/test_prod_sequence2_bundle.py::test_sequence_two_calling_visa_country_golden_vectors[CM-FALSE]
1.61s setup    backend/tests/unit/routers/test_news_router.py::test_rss_feed_db_error
1.61s setup    backend/tests/services/visa_engine/test_prod_sequence2_bundle.py::test_sequence_two_calling_visa_country_golden_vectors[SO-TRUE]
1.61s setup    backend/tests/services/visa_engine/test_prod_sequence2_bundle.py::test_sequence_two_current_sources_preserve_conclusive_supported_persona
1.61s setup    backend/tests/services/visa_engine/test_prod_sequence2_bundle.py::test_sequence_two_signature_compile_and_hash_chain
1.60s setup    backend/tests/services/visa_engine/test_prod_sequence2_bundle.py::test_sequence_two_calling_visa_country_golden_vectors[IL-TRUE]
1.60s setup    backend/tests/services/visa_engine/test_prod_sequence2_bundle.py::test_sequence_two_calling_visa_country_golden_vectors[GN-FALSE]
1.60s setup    backend/tests/services/visa_engine/test_prod_sequence2_bundle.py::test_sequence_two_extension_unknowns_are_explicit_and_neutral
```

## 4. Top-10 assessed — redundancy / value / proposed ownership SLA

Every one of the top 10 was read live this session (source file, and for the
non-obvious ones the production code it exercises) — none of the following is
inferred from the test name alone.

### 1. `test_rate_limit_error_is_retried` — 12.34s

**What it verifies**: `RetryHandler.execute_with_retry` retries a
429-classified error and returns the eventual success (`backend/llm/
retry_handler.py`, S12 fix). **Why it is slow**: `_compute_delay()` gives
`rate_limit`-classified errors a **hardcoded floor** —
`_RATE_LIMIT_BASE_DELAY = 10.0` (line 39) — completely independent of the
`base_delay=0.01` the test constructs its `RetryHandler` with. The test
therefore pays a real `await asyncio.sleep(~10s ± 25% jitter)`, exactly the
production 429 cooldown, to prove a fact (retry count + final result) that
does not require that wall time at all.
**Redundancy: none within this CI job's measured selection** (`tests.yml`'s
`Run unit tests` step, §1) — corrected after adversarial review: a second
429-retry test, `test_execute_with_retry_error_429`, exists at
`apps/backend-rag/tests/unit/test_llm_retry_handler.py:279` but lives OUTSIDE
the path list that step actually invokes (`backend/tests/`,
`tests/test_sentry_lazy_import.py`, `tests/test_sentry_pii_redaction.py`,
`tests/kb/test_politics_hierarchical.py` — see `tests.yml:564-568`), so it
never runs in the job this report measured and never appears in §3's
durations. Whether that second test is itself slow, and whether the two
overlap in what they assert, is unaudited — flagged, not claimed either way.
**Value: high** (S12's own fix history — see the file's docstring,
5 numbered production fixes — makes this a real regression guard).
**Candidate action** (not applied here): monkeypatch `asyncio.sleep` (or
`backend.llm.retry_handler._compute_delay`) in this one test so it asserts
the retry *count* and *classification*, not the *wall-clock cooldown* —
production behavior is unchanged, only the test's own patience is. Estimated
saving: ~10s of this one test's 12.34s.
**Ownership SLA**: whoever next touches `backend/llm/retry_handler.py` (no
per-file CODEOWNERS entry beyond the repo-wide `@Balizero1987`; this is a
solo-dev shop — "ownership" here means "the corner that next has a reason to
be in this file," not a named second engineer).

### 2 & 5. `test_no_test_decorator_reads_the_clock` (10.33s) + `test_no_test_decorator_reads_a_random_value` (9.35s) — `test_no_clock_in_parametrize.py`

**What they verify**: two DIFFERENT real bug classes — a frozen clock value
baked into `@pytest.mark.parametrize` (ages stale while the suite runs,
2026-07-27 scar) and a random/UUID value baked into `@pytest.mark.parametrize`
(breaks pytest-xdist collection, "Different tests were collected between gwN
and gwM"). **Redundancy: none in what they assert** — both must stay. **But**:
both call the SAME `_iter_test_sources()` helper (line 136) independently,
each doing its own `root.rglob("*.py")` over `_TEST_ROOTS`, its own
`path.read_text()` per file, and its own `ast.parse` + `ast.walk` per file —
a full, independent repo-tree read+parse pass, twice, back to back, for two
checks that could share one pass. **Computational redundancy: real** — this
is the one true "redundancy" finding in the top 10 (verified by reading the
function bodies, `backend/tests/compliance/test_no_clock_in_parametrize.py`
lines 136–329).
**Candidate action**: a module-scoped fixture (or `functools.lru_cache`) that
reads+parses each source file ONCE and hands both tests the same parsed-AST
list; each test still runs its own independent walk over the *shared* ASTs
looking for its own pattern. **Saving: real but NOT measured** — corrected
after adversarial review, which is right to reject the first draft's "roughly
half of 19.68s" as an unverified guess: this report did not profile how much
of each test's time is the shared `read_text`+`ast.parse` pass versus its own
`ast.walk`, so no number is claimed here. The redundant work is real (same
`_iter_test_sources()` call, same file set, two independent read+parse
passes) — how much time removing the duplication actually buys back is a
question for whoever implements the fixture, verified by re-running
`--durations` before/after, not for this report to estimate.
**Value: high** (both are `test_compliance` / `test_golden_rules`-class
repo-wide sweeps — the class of guard that has caught real CI breakage
before, per the file's own docstring). **Ownership SLA**: owner of
`backend/tests/compliance/` — same solo-dev caveat as above; SLA proposal:
re-measure after the shared-fixture change lands, not before (no action
without measurement, per this report's own §0 scope).

### 3. `test_control_the_sweep_rejects_the_pre_fix_quadratic` — 10.07s

**What it verifies**: a real, TIMED ReDoS regression sweep — the file's own
`TestPayloadSweep` docstring states this test fires "on the CEILING branch
(`_PRE_FIX_BAB` takes ~7.6s at n=20k, 30x the ceiling)" and is deliberately
NOT mocked: "an anti-load-noise fix verified by timing on a machine whose
load IS the variable under test is a coin flip." **Redundancy: none.**
**Value: very high** — this is a security-boundary test (py/polynomial-ReDoS
findings #7771-#7783) whose entire point is measuring real regex CPU time
against a real adversarial payload; faking the timing would remove the thing
being tested. **Candidate action: NONE proposed** — this is the one top-10
entry this report explicitly flags as **intentional, documented cost**, not
a diet candidate. **Ownership SLA**: `backend/tests/unit/core/legal/` — any
change to `SWEEP_MAX_RATIO` or the payload set needs the same adversarial
scrutiny the file's own header describes it received.

### 4. `test_post_drain_attestation_failure_freezes_lot` — 10.06s

**What it verifies**: R12-3 (intake drive-autocreate) — a real second
Postgres connection racing a drain, guilt (attestation fails → lot freezes)
and innocence (attestation passes → certifies), against the local dev
database, real DB round-trips. **Why it is slow**: `_fake_worker(qid,
run_tag, delay=1.5)` runs `await asyncio.sleep(1.5)` inside the loop that
executes both the guilt AND innocence case — ~3.0s of the 10.06s is exactly
two deliberate 1.5s delays. **Redundancy: none** (real concurrency proof,
not overlapping with any other top-50 entry). **Value: high** — this is a
real-DB race-window test, the class of test that is hardest to fake safely.
**Candidate action: flagged, not proposed** — whether 1.5s can safely shrink
(e.g. to 0.3s) without narrowing the race window it is meant to create is
exactly the kind of judgment call this report is not positioned to make
unilaterally (the note in §2 of the council doc: only proven-redundant or
documented-unstable tests are diet candidates, and race-window timing is
neither — it is a documented, deliberate proof needing an owner's sign-off,
not a report's guess). **Ownership SLA**: `backend/tests/services/intake/`
— the R6/R12 gate-round author is the only one positioned to judge whether
the delay margin has room.

### 6. `test_light_router_registration_does_not_eager_import_portal_document_pipeline` — 8.67s

**What it verifies**: a `subprocess.run` spawning a FRESH Python interpreter
to prove the "light" router registration path does NOT eagerly import a heavy
module — the only way to test "nothing imported yet" is a process that has
imported nothing yet. **Redundancy: none. Value: high** (import-order/startup
regressions are exactly the class this file's own name says it guards).
**Candidate action: none proposed** — interpreter-startup cost here is
structural to what is being proven, same shape as entry #3.
**Ownership SLA**: `backend/tests/unit/app/setup/`.

### 7. `test_no_consumer_imports_raw_template_outside_prompt_manager` — 7.75s

**What it verifies**: the ZANTARA_MASTER_TEMPLATE split-brain regression
guard (research/operations/2026-07-17-zantara-prompt-v4-design.md §1/§4.3) —
a `BACKEND_ROOT.rglob("*.py")` + `ast.walk` sweep (line 78). **Corrected
after adversarial review**: this is a DIFFERENT scope than #2/#5 and #10's
sweeps, not the "same tree" — `test_prompt_source_parity.py:76-85` explicitly
excludes `tests/`, `prompts/`, and the allowed resolver from its own walk,
`test_no_clock_in_parametrize.py` walks ONLY the two test trees, and
`test_golden_rules.py` walks only `app/`, `services/`, `core/`, `middleware/`
(`DIRS_TO_CHECK`, line 26). Three different scopes reading the filesystem
independently is still three separate cold-start `rglob`+`ast.parse` passes
paid on every run, but it is not evidence of ONE shared cache paying off
across all three — see §5's corrected finding. **Redundancy: none in what it
asserts** (unique invariant: no consumer outside `backend.prompts` imports
the raw template) **and no confirmed computational redundancy with another
top-10 entry** (its scope does not overlap #2/#5's or #10's). **Value:
high** — this guard exists because a real production regression (env var
with zero effect on the WhatsApp bot's brain) shipped silently before it did.
**Candidate action: none proposed** — a shared cache would only help THIS
file if it is itself re-run multiple times per suite (unaudited) or if a
future guard is added inside its own already-narrow scope.
**Ownership SLA**: `backend/tests/unit/prompts/`.

### 8. `test_detect_ktp_16_digits` — 7.66s

**What it verifies**: Indonesian PII detection (KTP 16-digit format) via
`backend.middleware.pii_scanner.scan_text`. **Why it is slow — and this is
the report's second most important finding after §2**: `pii_scanner.py`'s
`_get_analyzer()` (line 93) is a **lazy module-level singleton** —
`AnalyzerEngine()` from Microsoft Presidio, which loads its NLP model on
first construction, once per test process. `TestScanText::test_detect_
ktp_16_digits` is simply the first test in the file (and very possibly the
first `scan_text`/`redact_text` caller in the whole run) to touch it, so
`--durations` very likely attributes most of the one-time engine-load cost to
this one assertion. **Softened after adversarial review, which is right to
reject the first draft's "ENTIRE"/"not a slow test" as stronger than the
evidence**: this report confirmed the lazy-singleton MECHANISM is real
(`_analyzer` starts `None`, `_get_analyzer()` builds it exactly once,
`pii_scanner.py:90-93`) but did NOT measure a cold-vs-warm split — the 7.66s
could be construction + first `AnalyzerEngine.analyze()` call + ordinary
per-call cost + CI noise, in unknown proportions. The claim this report
stands behind is narrower: **the number is very likely dominated by shared,
one-time setup that pytest's `call`/`setup` split never separated out**, not
a verified measurement of exactly how much. **Redundancy: none** (unique
KTP-format assertion).
**Value: high** (UU PDP compliance boundary). **Candidate action**: a
session-scoped fixture that calls `_get_analyzer()` once at the start of the
`pii_scanner` test module (or the whole session) so the engine-load cost shows
up honestly as `setup`, not folded into whichever test collection order
happens to run first — this changes what the number MEANS, not what the
suite does, so it is a measurement fix, not a suite-cost fix (the 7.66s does
not go away, it becomes correctly attributed and stops distorting a future
--durations reading of this specific test). **Ownership SLA**:
`backend/middleware/pii_scanner.py` + `backend/tests/unit/middleware/`.

### 9. `test_all_concrete_get_routes_resolve` — 7.64s

**What it verifies**: every mounted route is reachable through real
middleware components — `include_routers()` + `HybridAuthMiddleware` — in a
dedicated test app. **Corrected after adversarial review**: the file's own
comment says this app is "intentionally lighter than `create_app()`"
(`test_endpoints_reachable.py:23`) and does not start lifespan/service
initialization (lines 104-119) — "the REAL production middleware stack" (the
first draft's wording) overstates what this specifically is; "real
middleware components in a realistic test app, not the full `create_app()`
lifespan" is accurate. The file's own docstring cites a real 2026-05-02
incident (`channel_health` router mounted directly on a bare FastAPI app in a
unit test, skipping `HybridAuthMiddleware`, masking a 401 that surprised
reviewers in prod). **Redundancy: none — this IS the anti-mock-drift test.**
**Value: very high**, definitionally: it exists specifically because a
cheaper/faster mocked version already failed to catch a real bug once.
**Candidate action: none proposed** — the whole point of this test is paying
the cost a mock would have skipped. **Ownership SLA**:
`backend/tests/integration/`.

### 10. `test_golden_rule_8_no_print_statements` — 7.23s

**What it verifies**: golden rule 8 ("Clean Logging — `logger` never
`print()`", CLAUDE.md §8) via `get_python_files(directory)` →
`directory.rglob("*.py")` over `DIRS_TO_CHECK = [APP_DIR, SERVICES_DIR,
CORE_DIR, MIDDLEWARE_DIR]` (`test_golden_rules.py:26,41`). **Corrected after
adversarial review**: this is redundant with THREE siblings in the SAME
file over the SAME `DIRS_TO_CHECK` scope — confirmed by reading all four,
not inferred — `test_golden_rule_3_no_relative_imports` (6.09s, line 288),
`test_golden_rule_5_type_hints` (6.21s, line 104), and
`test_golden_rule_6_no_hardcoded_secrets` (3.06s, line 141) each
independently call `get_python_files(directory)` for `directory in
DIRS_TO_CHECK` and then either `parse_python_file`+AST-visit (rules 3, 5, 8)
or a raw `open().read()` + line scan (rule 6) — four independent
`rglob("*.py")` passes over the identical four directories, back to back in
one file. This is NOT, as the first draft claimed, "the third of three
sweeps over the same repo tree" together with #2/#5 and #7 — those two other
files were verified (see #7, corrected) to scan different, non-overlapping
scopes. The real, confirmed redundancy is self-contained in THIS one file,
four-deep. **Redundancy: real, computational, confirmed** (4 rules, not 3,
each re-scanning `DIRS_TO_CHECK` from a cold start). **Value: high**
(`AI_ONBOARDING.md` golden-rule enforcement, "run automatically in CI/CD" per
the file's own header). **Candidate action**: a module-scoped fixture (or
`functools.lru_cache` on `get_python_files`) that reads+parses the four
directories ONCE and hands all four rule-checks the same file list / parsed
ASTs; each rule keeps its own independent visitor. Saving: not measured here
(same discipline as #2/#5 above — re-measure after, don't estimate before).
**Ownership SLA**: `backend/tests/compliance/test_golden_rules.py` — lowest
risk of the two shared-cache candidates in this report (single file, single
owner, no cross-file contract needed), and the natural first one to
prototype the pattern that could later inform #2/#5's cure.

## 5. Cross-cutting finding: two confirmed computational redundancies, not three

**Corrected after adversarial review** — the first draft of this section
claimed `test_no_clock_in_parametrize.py`, `test_prompt_source_parity.py`,
and `test_golden_rules.py` all sweep "the backend tree" and that the
underlying read+parse work is "repeated at least six times" across the
three files, proposing one shared cache across all three as "the single
highest-leverage next step." Reading each file's actual scan scope refutes
that: `test_prompt_source_parity.py` explicitly excludes `tests/`,
`prompts/`, and its own allowed resolver (lines 76-85); `test_no_clock_in_
parametrize.py` walks ONLY the two test trees (`_TEST_ROOTS`); `test_golden_
rules.py` walks ONLY `app/`, `services/`, `core/`, `middleware/`
(`DIRS_TO_CHECK`). Three genuinely different scopes — there is no evidence
one shared cache across all three would pay off, and this report does not
claim there is.

What IS confirmed, by reading the actual function bodies (not inferred from
naming or duration alone): **two separate, self-contained redundancies**,
each inside ONE file, over ONE shared scope:

1. `test_no_clock_in_parametrize.py` — 2 sweeps (`test_no_test_decorator_
   reads_the_clock`, `test_no_test_decorator_reads_a_random_value`), same
   `_iter_test_sources()` / `_TEST_ROOTS` (§4 #2/#5).
2. `test_golden_rules.py` — 4 sweeps (rules 3, 5, 6, 8), same
   `get_python_files()` / `DIRS_TO_CHECK` (§4 #10).

Each is a same-file, same-owner fix (no cross-file contract to design), and
each is independently a smaller, safer first step than the "one universal
cache" this report's first draft over-reached toward. Whether other repo-wide
sweeps exist outside the top 50 with the same shape is unaudited — flagged,
not claimed, per the "no silent caps" convention.

## 6. What this report does NOT recommend

- **No test is deleted, skipped, or marked flaky here.** Per council contract
  (§6 step 3): "NO auto-deletion on slowness/flake alone… deletion requires
  proof of redundancy or documented unstabilizability." Only #2/#5 and #10
  above meet the "proof of redundancy" bar, and even there the redundancy is
  in the SHARED SWEEP MACHINERY, not in the tests' own assertions — nothing
  here proposes deleting an assertion.
- **No `pytest.mark.slow` or CI-skip is proposed** for #3/#4/#6/#9 — their
  cost is the thing being verified, not overhead.
- **No suite-wide restructuring (xdist, container reuse, import lazy-loading)
  is designed here** — §2's finding (the top 50 is ≤15% of the `Run unit
  tests` step's own cost) means that work belongs to a differently-scoped
  investigation this report is flagging, not attempting.

## Adversarial review

**Seat**: `kimi-k3` was attempted first (per this repo's default cross-family
refuter seat) and returned `403 usage limit for this billing cycle` — quota
was exhausted mid-session (a separate, unrelated finding from the same day:
`decision_workhorse_first_routing_doctrine_2026_08_15.md`, "Kimi = solo
chirurgico, 14% mensile bruciato in 1 giorno"). Cascaded to **`codex`**
(`gpt-5.6-sol`, `model_reasoning_effort=high`, `--sandbox read-only`) per this
repo's own cascade convention (CLAUDE.md §Multi-LLM cascade) — a different
model family from this report's author (Sonnet 5), satisfying generator ≠
grader. Prompted to independently re-derive the §3 sum, read every piece of
production code the report makes a claim about, and challenge scope
compliance; told explicitly to rank findings and not skip clean sections.

**Verdict returned: FAIL**, with 1 HIGH, 4 MEDIUM, 4 LOW findings. Math was
confirmed correct (`219.72s` sum, independently recomputed) but the report's
central percentage used the wrong denominator, and several claims were
phrased more strongly than the evidence gathered. Full findings and this
report's disposition of each:

| # | Sev | Finding | Disposition |
|---|-----|---------|-------------|
| 1 | HIGH | §2's "12.9%"/"87%" divided the top-50's pytest-only duration by the whole JOB's wall time (includes install/coverage/upload steps outside `--durations`'s scope), not the `Run unit tests` step alone | **Fixed** — §2 rewritten against the step's own wall time (1,465.2s), corrected figure 15.0% |
| 2 | MEDIUM | "roughly 1,300+ tests" conflated test FILES (1,361) with test FUNCTIONS; a static scan finds 20,459 `test_*` functions | **Fixed** — §1 now states the function count, independently re-verified by this report (`grep` count matches codex's exactly) |
| 3 | MEDIUM | §5 claimed three files (no-clock, prompt-parity, golden-rules) sweep "the same tree" six times; they actually scan three different, non-overlapping scopes | **Fixed** — §5 and §4 #7/#10 rewritten to name only the two CONFIRMED same-file, same-scope redundancies (no-clock ×2, golden-rules ×4) |
| 4 | MEDIUM | "Estimated saving: roughly half of 19.68s" for #2/#5 was an unmeasured guess | **Fixed** — estimate removed, replaced with "not measured, re-verify after the fix lands" |
| 5 | MEDIUM | "ENTIRE cost"/"not a slow test" for the PII singleton (#8) overstated an unmeasured cold-vs-warm split | **Fixed** — softened to "very likely dominated by," mechanism-confirmed but magnitude explicitly marked unmeasured |
| 6 | LOW | "the only test covering 429-classification retry behavior" (#1) ignored a second retry test outside the CI-measured path selection | **Fixed** — #1 now names `test_execute_with_retry_error_429` and scopes the "only" claim to this job's measured selection |
| 7 | LOW | "REAL production middleware stack" (#9) overstated what a deliberately-lighter-than-`create_app()` test app is | **Fixed** — reworded per the file's own comment |
| 8 | LOW | Codex's own read-only sandbox had no network reachability to GitHub/Pro during its review, so it could not itself re-fetch the raw CI log or the Pro record to confirm provenance | **Not a defect in the report** — the `gh api`/`ssh pro` calls this report cites were run live, with authenticated access, by this session (not by the reviewer); noted here for anyone re-running this review in a similarly sandboxed environment |
| 9 | LOW | The adversarial-review section was still the placeholder at review time | **Resolved** — this section |

**What did NOT need fixing** (codex's own explicit "sections without issues"):
§0 scope compliance (no deletions/skips/quarantine proposed), §3's raw data
(exactly 50 durations, sum verified correct), §4 entries #3/#4/#6/#7/#10's
core factual claims (confirmed against the actual source, including #4's
real two-worker `sleep(1.5)` race), and §6's scope statement.

**Net effect of this round**: the report's one number-with-a-denominator-bug
(§2) is fixed and now compares like with like; two overstated conclusions
(§5's "six sweeps, one universal cache" and #8's "entire cost") are narrowed
to what was actually verified; three wording overreaches (#1, #9) are
qualified. No finding from this round required retracting a claim outright —
every corrected number/claim in the table above is now backed by either a
re-verified measurement or an explicit "not measured" disclaimer, which is
the standard this report holds its OWN top-10 assessments to in §4.
