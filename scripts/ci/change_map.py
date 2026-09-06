#!/usr/bin/env python3
"""Classify a PR's changed files for path-aware CI job selection.

The caller owns changed-file enumeration. In GitHub Actions that caller must
be ``hotzone_changed_files.sh`` so the input is anchored to the merge-base.
This module is deliberately pure: known paths map to one or more domains,
while an empty, malformed, or unclassified input recommends every test job.

Promoted to enforcing 2026-08-14 (.github/workflows/tests.yml gates its six
heavy test jobs on ``suggested_jobs``/``run_all`` below) after a 57-run
shadow-measurement audit that found and closed one real false-skip (see
EXACT_RULES' PricingTool-canonical entry below) — see that workflow's
``changes`` job for the fail-open contract every consumer of this module's
output must honor.
"""

from __future__ import annotations

import json
import posixpath
import re
import sys
from collections.abc import Iterable

ENUMERATION_ERROR = "__CHANGE_MAP_ENUMERATION_ERROR__"

DOMAIN_NAMES = (
    "backend_python",
    "mouth",
    "admin_dashboard",
    "wa_mirror",
    "mcp",
    "evaluator",
    "packages_core",
    "infra_workflows",
    "docs_content_data",
    "security_sensitive",
    "fleet_ops",
)

TEST_JOBS = (
    "backend-tests",
    "mcp-tests",
    "evaluator-critical-tests",
    "frontend-tests",
    "packages-core-tests",
    "e2e-tests",
)

PRODUCT_DOMAINS = frozenset(
    {
        "backend_python",
        "mouth",
        "admin_dashboard",
        "wa_mirror",
        "mcp",
        "evaluator",
        "packages_core",
    }
)

EXACT_RULES: dict[str, set[str] | frozenset[str]] = {
    # This workflow defines every job being measured. Editing it must never
    # produce a self-approved selective recommendation.
    ".github/workflows/tests.yml": PRODUCT_DOMAINS
    | {"infra_workflows", "security_sensitive"},
    "scripts/ci/change_map.py": {"infra_workflows", "security_sensitive"},
    "scripts/ci/test_change_map.py": {"infra_workflows", "security_sensitive"},
    # Harness config, not app code — the six tests.yml jobs never read
    # .claude/settings*.json, and it is verified by immune-enforcement.yml
    # and the hook tests under scripts/tests/, not by tests.yml's jobs.
    # Before this entry both fell into unknown_paths (run_all=True) — every
    # hook/settings PR paid the full suite for a file none of the six jobs
    # touch.
    ".claude/settings.json": {"fleet_ops"},
    ".claude/settings.local.json": {"fleet_ops"},
    "package.json": {
        "mouth",
        "admin_dashboard",
        "wa_mirror",
        "packages_core",
        "security_sensitive",
    },
    "package-lock.json": {
        "mouth",
        "admin_dashboard",
        "wa_mirror",
        "packages_core",
        "security_sensitive",
    },
    "pyproject.toml": {
        "backend_python",
        "mcp",
        "evaluator",
        "security_sensitive",
    },
    # Cross-domain coupling found in the 57-run shadow audit (2026-08-14,
    # run 31648287902): this single backend file is PricingTool's canonical
    # source (PricingService._load_prices() reads it, and
    # scripts/sync_frontend_prices.py regenerates the mouth-side copy from
    # it). Two mouth vitest suites read this exact path directly and fail on
    # drift — apps/mouth/src/lib/pricing-snapshot.test.ts ("keeps every
    # exact PricingTool row in parity") and
    # apps/mouth/src/lib/bali-zero-prices.test.ts ("PricingTool
    # source-of-truth") — so a PR that edits only this backend file, without
    # having regenerated apps/mouth/data/bali-zero-prices.json yet, needs
    # frontend-tests to catch the mismatch before merge. The "apps/backend-rag/"
    # prefix rule below already puts this path in backend_python; this exact
    # entry additionally routes it to mouth. Deliberately an EXACT path, not
    # a directory/prefix rule.
    #
    # CORRECTION (red-team HIGH-8, 2026-08-14): this comment previously
    # claimed "no rulepack path feeds the frontend snapshot" after checking
    # only PricingService. That was wrong, not merely incomplete — Codex's
    # red-team re-read apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/
    # engine-adapter.test.ts and found it DOES read
    # apps/backend-rag/backend/services/visa_engine/contracts/packs/
    # rulepack-prod-*.source.json directly (globs every file matching
    # rulepack-prod-\d+.source.json under that dir and asserts every SUPPORT
    # reason code in them has frontend copy — see productionPackFiles() /
    # supportReasonCodesInPack() in that test). Same suite's
    # fact-mapper.test.ts also reads
    # apps/backend-rag/backend/services/visa_engine/models.py directly,
    # extracting every dotted `alias="a.b"` on ApplicantFactsData as the
    # backend contract. Both couplings are now below (models.py as an exact
    # path; the rulepack family as a filename-pattern rule, since the exact
    # active pack filename changes as new packs are authored ahead of
    # activation — see that test's own comment on why it globs).
    "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json": {
        "backend_python",
        "mouth",
    },
    "apps/backend-rag/backend/services/visa_engine/models.py": {
        "backend_python",
        "mouth",
    },
    # The mouth article ratchet reads this exact backend vocabulary source.
    "apps/backend-rag/backend/services/visa_check/e33_claim_guard.py": {
        "backend_python",
        "mouth",
    },
    # Cross-domain coupling found in the 57-run shadow audit (2026-08-14):
    # apps/mouth/src/lib/kbli-canonical-pins.test.ts (a REQUIRED
    # frontend-tests suite, no path filter) reads these two repo-root `data/`
    # files directly and fails on a stale/mismatched pin — see that test's
    # own header for why the check has to live in mouth rather than in the
    # filiera compilers. The "data/" PREFIX_RULES entry below already routes
    # these to backend_python + docs_content_data; these EXACT entries widen
    # ONLY these two files to also reach mouth (most of data/ — analysis/,
    # competitor/, kb_sources/, etc. — has no such frontend reader, so this
    # is deliberately not a directory/prefix rule).
    "data/source_documents/KBLI_2025_FINAL_CLEAN.json": {
        "backend_python",
        "docs_content_data",
        "mouth",
    },
    "data/kbli-filiera/membership/batch-a-members.json": {
        "backend_python",
        "docs_content_data",
        "mouth",
    },
    # Cross-domain coupling found in the 57-run shadow audit (2026-08-14):
    # apps/backend-rag/backend/tests/app/routers/test_analytics_funnel_parity.py
    # reads these two exact packages/core files directly (regex-extracts the
    # FUNNEL_EVENTS / APP_EVENTS `as const` arrays) and pins backend
    # ALLOWED_EVENTS/FUNNEL_PAGE_EVENTS/FUNNEL_APP_EVENTS as the exact union —
    # a mismatch either direction fails a backend-tests test. The
    # "packages/core/" PREFIX_RULES entry below already routes these to
    # packages_core + mouth; these EXACT entries additionally widen ONLY
    # these two files to backend_python (every other file under
    # packages/core/analytics/ — index.ts, useFunnelApp.ts, the *.test.ts
    # siblings — has no such backend reader, so this is deliberately not a
    # directory/prefix rule).
    "packages/core/analytics/funnel-view.ts": {
        "packages_core",
        "mouth",
        "backend_python",
    },
    "packages/core/analytics/funnel-app.ts": {
        "packages_core",
        "mouth",
        "backend_python",
    },
}

# Filename-pattern coupling (red-team HIGH-8, 2026-08-14): the visa-engine
# rulepack family is authored under a numbered filename
# (rulepack-prod-<N>.source.json) and a NEW pack is written and merged
# BEFORE it is the active one — engine-adapter.test.ts globs every file
# matching this exact pattern under this exact directory (never a directory
# it doesn't also enumerate), so the CI coupling has to match the same
# family, not one pinned filename. Deliberately a narrow regex scoped to
# both the exact directory AND the test's own basename pattern — mirrors
# `/^rulepack-prod-\d+\.source\.json$/` in that test file, not invented.
REGEX_RULES: tuple[tuple[re.Pattern[str], frozenset[str]], ...] = (
    (
        re.compile(
            r"^apps/backend-rag/backend/services/visa_engine/contracts/packs/"
            r"rulepack-prod-\d+\.source\.json$"
        ),
        frozenset({"backend_python", "mouth"}),
    ),
)

# BEGIN SCRIPTS_COUPLING (generated by scripts/ci/scripts_coupling_census.py — do not edit)
SCRIPTS_COUPLING: frozenset[str] = frozenset(
    (
        "scripts/_redact_pii.py", "scripts/agent_start.py", "scripts/ai-dispatch.sh", "scripts/army/spark_lane.sh", "scripts/arsenal_probe.py", "scripts/async_review_supervisor.py", "scripts/audit_httpx_violations.sh", "scripts/autonomous_lab_draft.py", "scripts/autonomous_lab_run.py", "scripts/backfill_portal_profiles.py", "scripts/bot/wa_blind_bench.py", "scripts/build_kbli_l2_oss_risk.py",
        "scripts/check_adversarial_review.py", "scripts/check_llm_cost_tracking.py", "scripts/codex_tri_llm_review.py", "scripts/codex_visual_orchestrator.py", "scripts/conductor/adapter_contracts.py", "scripts/conductor/app_server_rpc.py", "scripts/conductor/codex_shadow.py", "scripts/conductor/codex_shadow_launch.py", "scripts/conductor/consul_broker_client.py",
        "scripts/conductor/consul_native.py", "scripts/conductor/native_canary_contract.py", "scripts/conductor/protected_grants.py", "scripts/consul_broker.py", "scripts/crm_guardian_deep_audit.py", "scripts/crm_guardian_gemini_cli_worker.py", "scripts/crm_guardian_gemini_worker.py", "scripts/crm_guardian_tax_dept_apply.py", "scripts/detect_secrets_auto_triage.py", "scripts/docs_sync.py",
        "scripts/drive_token_watchdog.py", "scripts/expiry_alerter.py", "scripts/federation_orchestrator.py", "scripts/fetch_oss_risk.py", "scripts/fill_kbli_80190.py", "scripts/flowkit_cli.py", "scripts/gap_fill_autonomous.py", "scripts/gsc_resubmit_sitemap.py", "scripts/install-claude-code.sh", "scripts/intake_direct_doc_parser_audit.py", "scripts/intake_drive_folder_id_backfill.py",
        "scripts/intake_identity_backfill.py", "scripts/intake_reprocess_backlog.py", "scripts/intake_review_reader_run.sh", "scripts/intake_wa_mirror_audit.py", "scripts/journey_sentinel.sh", "scripts/kb/cukup_jelas_sample.py", "scripts/kb/kb_inventory_probe.py", "scripts/kb/legal_status_drift_gate.py", "scripts/kb/probe_legal_status_marking.py", "scripts/kbli_apply_editorials.py",
        "scripts/kbli_apply_en_titles.py", "scripts/kbli_dataset_lint.py", "scripts/kbli_filiera/_coverage_basis.py", "scripts/kbli_filiera/_whatchanged_basis.py", "scripts/kbli_filiera/apply_perpres_foreign_caps.py", "scripts/kbli_filiera/cure_canonical_collisions.py", "scripts/kbli_filiera/cure_l23_whatchanged_language.py", "scripts/kbli_filiera/editorial_record_conformance.py",
        "scripts/kbli_filiera/emit_batch_membership.py", "scripts/kbli_filiera/gold_risk_dispute_relation.py", "scripts/kbli_filiera/perpres_body_default_relation.py", "scripts/kbli_filiera/perpres_slice_disclosure_relation.py", "scripts/kbli_filiera/tests/test_withdrawn_umkm_inference_absent.py", "scripts/lead_intent_matcher.py", "scripts/lib/codex_seat.py", "scripts/lib/codex_seat.sh",
        "scripts/lib/heartbeat.py", "scripts/lib/yaml_strict.py", "scripts/lint/lint_claude_headless_model_pin.py", "scripts/lint_avatar_url_validators.py", "scripts/lint_content_reasoning_leak.py", "scripts/lint_home_fork.py", "scripts/lint_i18n_providers.sh", "scripts/lint_tcc_desktop_paths.py", "scripts/lint_telegram_tokens.py", "scripts/lint_test_reward_hacking.py",
        "scripts/mata_garuda_invalidation_sweep.py", "scripts/metabolic_rollup.py", "scripts/nlm_shadow_extractor.py", "scripts/openclaw_whatsapp_bridge.py", "scripts/patch_pricing_contact_block.py", "scripts/pending_arms_report.py", "scripts/pg-to-organism-bridge.py", "scripts/pg.sh", "scripts/pricelist_2026/schema.py", "scripts/probes/intel_lake_e2e_probe.py",
        "scripts/provision_zantara_codex.sh", "scripts/pytest_guards/pytest_verbosity_guard.py", "scripts/rag_canary.py", "scripts/repair_description_fields.py", "scripts/repair_swallowed_titles.py", "scripts/s7_yield_dispatch.py", "scripts/scrape_competitor_serp.py", "scripts/sentinel_lib/__init__.py", "scripts/sentinel_lib/alerter.py", "scripts/sentinel_lib/circuit_breaker.py",
        "scripts/sentinel_lib/classifier.py", "scripts/sentinel_lib/escalations.py", "scripts/sentinel_lib/guardrail_liveness.py", "scripts/sentinel_lib/incident_detector.py", "scripts/sentinel_lib/metrics.py", "scripts/sentinel_lib/repairer.py", "scripts/sentinel_lib/zombie_hunter.py", "scripts/sentry-quota-check.sh", "scripts/sota_infer_personas.py", "scripts/sota_literature_research.py",
        "scripts/suite_growth_probe.py", "scripts/sync_frontend_prices.py", "scripts/sync_kbli_dataset.sh", "scripts/test_cron_single_voice.sh", "scripts/tests/test_adversarial_review_gate.py", "scripts/tests/test_install_claude_code_version_skew.sh", "scripts/tests/test_intake_dsn_guard_covers_every_var.py", "scripts/tests/test_kbli_68112_pp28_mice_collision.py",
        "scripts/tests/test_merah_putih_day_contrast.py", "scripts/tests/test_pytest_verbosity_guard.py", "scripts/tests/test_test_deps_declared.py", "scripts/tg_notify.py", "scripts/token_lint.py", "scripts/tp1_call.py", "scripts/translate-articles-cron-wrapper.sh", "scripts/vercel_prod_deploy.py", "scripts/wa_codex_seat_probe.py", "scripts/wa_media_pull_worker.py",
        "scripts/wa_mirror_intake_sweeper.py", "scripts/whatsapp_export_backfill/import_staging.py", "scripts/wr2-cron-wrapper.sh", "scripts/wr2_bootstrap_canva_oauth.py", "scripts/wr2_canva_pdf_render.py", "scripts/wr2_daily_reconciler.py", "scripts/wr2_damar_publish_consumer.py", "scripts/wr2_draft_generator.py", "scripts/wr2_fact_checker.py", "scripts/wr2_fact_extractor.py",
        "scripts/wr2_html_render_apply.py", "scripts/wr2_ig_profile_harvester.py", "scripts/wr2_ig_publish.py", "scripts/wr2_image_generator.py", "scripts/wr2_queue_writer.py", "scripts/wr2_rerender_requeue.py", "scripts/wr2_supervisor.py", "scripts/wr2_topic_selector.py", "scripts/wr2_validate_master.py", "scripts/wr3_supervisor.py",
    )
)
# END SCRIPTS_COUPLING

PREFIX_RULES: tuple[tuple[str, frozenset[str]], ...] = (
    # OpenAPI feeds mouth's generated types and the backend live-router parity test.
    ("products/garuda-voa/contracts/", frozenset({"backend_python", "mouth"})),
    ("apps/backend-rag/", frozenset({"backend_python"})),
    ("apps/crm-cell/", frozenset({"backend_python"})),
    ("packages/cell-core/", frozenset({"backend_python", "mcp"})),
    ("apps/mouth/", frozenset({"mouth"})),
    ("apps/admin-dashboard/", frozenset({"admin_dashboard"})),
    ("apps/wa-mirror/", frozenset({"wa_mirror"})),
    ("apps/nuzantara-mcp/", frozenset({"mcp"})),
    ("apps/nuzantara-mcp-advanced/", frozenset({"mcp"})),
    ("apps/nuzantara-mcp-browser/", frozenset({"mcp"})),
    ("apps/evaluator/", frozenset({"evaluator"})),
    # packages/core is both its own suite and a direct frontend dependency.
    ("packages/core/", frozenset({"packages_core", "mouth"})),
    (
        "packages/ts-schemas/",
        frozenset({"mouth", "admin_dashboard", "wa_mirror", "packages_core"}),
    ),
    (
        "packages/shared-schemas/",
        frozenset({"mouth", "admin_dashboard", "wa_mirror", "packages_core"}),
    ),
    (".github/", frozenset({"infra_workflows", "security_sensitive"})),
    (".husky/", frozenset({"infra_workflows", "security_sensitive"})),
    (".security/", frozenset({"infra_workflows", "security_sensitive"})),
    ("scripts/ci/", frozenset({"infra_workflows", "security_sensitive"})),
    # More specific than the "infra/" catch-all below, so it must stay ahead
    # of it in this tuple (first match wins). guard-conformance corpora are
    # verified by guard-conformance.yml's own guilt+innocence run (cicatrix
    # #3's own ESEGUIBILE), not by tests.yml's six product suites — before
    # this entry, infra/guard-conformance/registry.json inherited the
    # broad "infra/" rule and forced every one of the six jobs regardless.
    ("infra/guard-conformance/", frozenset({"fleet_ops"})),
    # Also more specific than the catch-all, and the ONE sub-tree of infra/
    # that a tests.yml suite genuinely reads (census 2026-09-05, all 38
    # sub-trees against all six suites):
    # apps/backend-rag/backend/tests/unit/core/test_ingest_target_registry.py
    # opens infra/eventbus/regulatory_ingest_runner.py by that literal path
    # and asserts on its contents, and scripts/ci/ingest_target_lint.py
    # hardcodes the same path in DECLARED_ENTRYPOINTS. Every other sub-tree
    # (ghostty, launchagents, required.d, conductor, vcr, healer, home-fork,
    # …) either has zero hits in the six suites' trees, or hits confined to
    # scripts/ (covered by SCRIPTS_COUPLING below), or — claude-hooks,
    # launchagents — hits that are PROSE inside docstrings naming the
    # directory, not code that opens or imports anything there.
    ("infra/eventbus/", frozenset({"backend_python", "security_sensitive"})),
    # The catch-all. `infra_workflows` (2026-09-05) was the second half of
    # the same over-match `infra/guard-conformance/` was carved out of above,
    # applied to the other 37 sub-trees: infra/ is fleet payload — plists,
    # wrappers, terminal profiles, required-context mirrors — not CI workflow
    # definitions. Those live in .github/, which keeps infra_workflows and
    # keeps forcing all six suites. `security_sensitive` STAYS: CodeQL's
    # config (.github/codeql-config.yml) declares no paths-ignore, so it
    # analyses infra/'s Python and shell like any other tree, and dropping
    # the domain here would silence that scan — the UNDER-match twin of the
    # defect being cured. The security posture of an infra/-only PR is
    # therefore byte-identical to before this change; only the six product
    # suites stop being bought.
    ("infra/", frozenset({"fleet_ops", "security_sensitive"})),
    ("config/", frozenset({"infra_workflows", "security_sensitive"})),
    ("data/", frozenset({"backend_python", "docs_content_data"})),
    # kb/ is the knowledge-base corpus (inventories, topics, journeys, ops
    # probes), added 2026-08-25 and never routed — every kb/-only PR fell into
    # unknown_paths and tripped run_all. It takes data/'s pairing, and the
    # backend_python half is load-bearing, not symmetry: nine suites under
    # apps/backend-rag/backend/tests/unit/kb/ read kb/inventory/*.yaml
    # directly, and _suggested_jobs() grants docs_content_data none of the six
    # jobs — so routing kb/ to docs alone would silence the corpus's own guard.
    ("kb/", frozenset({"backend_python", "docs_content_data"})),
    ("public/", frozenset({"mouth", "docs_content_data"})),
    # fleet_ops (2026-08-20, superseded 2026-09-04): top-level scripts/
    # (outside scripts/ci/, already mapped above) used to be unmappable by
    # pattern — a one-off census found 19+ scripts/*.py modules silently
    # imported into apps/backend-rag/backend/tests/{scripts,unit/scripts}/
    # via a sys.path shim in that tree's own conftest.py, with NO naming or
    # directory pattern in common (cicatrix #3, under-match).
    # scripts_coupling_census.py (see its own docstring) turns that one-off
    # audit into a repeatable, regenerable rule: it greps the six jobs' own
    # trees for a `scripts.<dotted>` import or a literal `scripts/<path>.py`
    # /`.sh` reference and writes each real repo-root hit into
    # SCRIPTS_COUPLING below. `--check` (scripts/ci/test_change_map.py) fails
    # the moment a coupling changes without a regenerated block. These ten
    # directories stay mapped here, ahead of the SCRIPTS_COUPLING check,
    # because each is ALSO verified to contain zero .py files (structurally
    # unreachable by the sys.path mechanism) and has its own narrower CI
    # elsewhere. `fleet_ops` maps to ZERO entries in `_suggested_jobs()` — a
    # change confined to these directories, or to any scripts/ path
    # SCRIPTS_COUPLING does not name, needs none of the six heavy jobs, and
    # combined with anything else keeps whatever job set that other path
    # earns.
    ("scripts/cli/", frozenset({"fleet_ops"})),
    ("scripts/codex/", frozenset({"fleet_ops"})),
    ("scripts/damar-node/", frozenset({"fleet_ops"})),
    ("scripts/data/", frozenset({"fleet_ops"})),
    ("scripts/krisna-node/", frozenset({"fleet_ops"})),
    ("scripts/launchd/", frozenset({"fleet_ops"})),
    ("scripts/mini/", frozenset({"fleet_ops"})),
    ("scripts/pro/", frozenset({"fleet_ops"})),
    ("scripts/review_routes/", frozenset({"fleet_ops"})),
    ("scripts/ruslana-node/", frozenset({"fleet_ops"})),
    # Hook scripts, not app code — verified by their own corpus under
    # scripts/tests/ (e.g. test_precommit_print_gate.sh) and by
    # immune-enforcement.yml, never by the six tests.yml jobs.
    (".claude/hooks/", frozenset({"fleet_ops"})),
)

DOC_PREFIXES = (
    "docs/",
    "research/",
    ".agents/skills/",
    ".claude/skills/",
    ".claude/rules/",
    ".claude/commands/",
    ".claude/agents/",
    # Zero's order 2026-08-27: docs-only PRs must stop paying the 5 heavy
    # required checks. Every agent-produced PR writes evidence/brief.yml +
    # evidence/pack.yml (the modus GROUND/CAPTURE ceremony — see
    # evidence_pack_lint.py, harness-floor.yml) as fixed root-level paths,
    # regardless of what the PR's real change is. Before this line,
    # "evidence/" matched no EXACT_RULES/REGEX_RULES/PREFIX_RULES entry and
    # fell through to `unknown_paths`, which forces run_all=True (the
    # fail-open default) — so a purely-documentary PR that still carries its
    # mandatory evidence pack paid for all six heavy jobs anyway, silently
    # defeating the domain classifier for the single most common PR shape.
    # Routing it into docs_content_data (same as this tuple's other
    # ceremony/metadata prefixes) is correct, not a loophole: this module's
    # `_suggested_jobs()` never grants docs_content_data any of the six
    # heavy jobs, and evidence/*.yml is read by nothing under
    # apps/backend-rag/, apps/mouth/, apps/admin-dashboard*/, apps/wa-mirror/,
    # apps/nuzantara-mcp*/, apps/evaluator/, or packages/core/ (verified by
    # grep, 2026-08-27) — so it cannot mask a real regression. A PR that
    # ALSO changes real code keeps whatever domain that code earns; this
    # only stops evidence/*.yml from being the one unclassified path that
    # forces run_all=True on top of a genuinely narrow diff.
    "evidence/",
)
DOC_SUFFIXES = (
    ".md",
    ".mdx",
    ".txt",
    ".csv",
    ".json",
    ".jsonl",
    ".yml",
    ".yaml",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".svg",
    ".pdf",
)

PYTHON_MANIFEST_NAMES = frozenset(
    {
        "requirements.txt",
        "requirements.lock.txt",
        "requirements-test.txt",
        "requirements-dev.txt",
        "setup.cfg",
        "tox.ini",
        "pytest.ini",
        "uv.lock",
    }
)


def _normalize(raw: str) -> str | None:
    """Return a safe repo-relative POSIX path or ``None``."""

    # ``git diff --name-only`` does not add padding. Treat edge whitespace as
    # malformed instead of silently turning it into a different repository
    # path (Git filenames may legally contain spaces).
    if raw != raw.strip():
        return None
    path = raw
    while path.startswith("./"):
        path = path[2:]
    if not path or "\x00" in path or "\n" in path or "\r" in path:
        return None
    if path.startswith("/") or any(part == ".." for part in path.split("/")):
        return None
    normalized = posixpath.normpath(path)
    if normalized in {"", "."} or normalized.startswith("../"):
        return None
    return normalized


def _domains_for_path(path: str) -> set[str]:
    exact = EXACT_RULES.get(path)
    if exact is not None:
        return set(exact)

    for pattern, domains in REGEX_RULES:
        if pattern.match(path):
            return set(domains)

    basename = path.rsplit("/", 1)[-1]
    if basename in PYTHON_MANIFEST_NAMES or basename.startswith("requirements-"):
        return {"backend_python", "mcp", "evaluator", "security_sensitive"}

    for prefix, domains in PREFIX_RULES:
        if path.startswith(prefix):
            matched = set(domains)
            if any(part in {"auth", "security", "migrations", "deploy"} for part in path.split("/")):
                matched.add("security_sensitive")
            if basename in {"Dockerfile", "fly.toml"}:
                matched.add("security_sensitive")
            # MDX is served by mouth and also consumed by backend indexing code.
            if path.startswith("apps/mouth/") and path.endswith(".mdx"):
                matched.update({"backend_python", "docs_content_data"})
            return matched

    # Reached only for scripts/ paths outside scripts/ci/ and the ten
    # fleet_ops directories above (see the PREFIX_RULES comment). The
    # census (scripts_coupling_census.py) decides the rest: a file the six
    # jobs actually import or subprocess-invoke needs backend_python;
    # everything else is a fleet-ops payload no job reads.
    if path.startswith("scripts/"):
        if path in SCRIPTS_COUPLING:
            return {"backend_python"}
        return {"fleet_ops"}

    if path.startswith(DOC_PREFIXES) and path.lower().endswith(DOC_SUFFIXES):
        return {"docs_content_data"}
    if "/" not in path and path.lower().endswith((".md", ".mdx", ".txt")):
        return {"docs_content_data"}
    return set()


def _suggested_jobs(domains: set[str], run_all: bool) -> list[str]:
    # CI infrastructure can affect any suite indirectly: the workflow files,
    # the classifier itself and the hooks that run around them are known
    # paths, but never candidates for selective execution.
    #
    # `security_sensitive` was in this set until 2026-09-05 and is NOT, because
    # it names TWO unrelated questions under one word (cicatrix #3, over-match
    # on the domain instead of the entity):
    #   1. "which SECURITY SCANNERS must run" — read by
    #      scripts/ci/security_gate_flags.py, which is the only thing this
    #      domain was ever designed to answer, and still answers unchanged;
    #   2. "which of the six PRODUCT TEST SUITES must run" — answered here.
    # Conflating them made every security-sensitive path buy all six suites,
    # whatever its real coupling. Measured on PR #5697: a one-file diff
    # (infra/ghostty/machines/m5.ghostty) classified correctly — run_all
    # false, reason `classified`, only infra_workflows + security_sensitive
    # lit, no frontend domain at all — and still ran Frontend Tests for 16 of
    # its 18 steps, because this line looked at the union.
    #
    # Dropping it here is not an UNDER-match (the twin defect), because no
    # rule reaches `security_sensitive` alone: every entry that carries it —
    # EXACT_RULES' package.json / pyproject.toml, PYTHON_MANIFEST_NAMES,
    # PREFIX_RULES' .github/ .husky/ .security/ scripts/ci/ config/ infra/,
    # and the two additive rules below (`auth|security|migrations|deploy`
    # path parts, Dockerfile/fly.toml basenames) — also carries the domains
    # of the code it actually touches. So a lockfile change still fans out to
    # its own runtimes, a workflow edit still runs everything through
    # infra_workflows, and what stops is only the fan-out to suites that
    # cannot read the changed file: pyproject.toml no longer runs the
    # frontend, package-lock.json no longer runs the Python suites.
    if run_all or domains.intersection({"infra_workflows"}):
        return list(TEST_JOBS)

    jobs: list[str] = []
    if "backend_python" in domains:
        jobs.append("backend-tests")
    if "mcp" in domains:
        jobs.append("mcp-tests")
    if "evaluator" in domains:
        jobs.append("evaluator-critical-tests")
    if domains.intersection({"mouth", "admin_dashboard", "wa_mirror", "packages_core"}):
        jobs.append("frontend-tests")
    if "packages_core" in domains:
        jobs.append("packages-core-tests")
    if domains.intersection({"backend_python", "mouth", "packages_core"}):
        jobs.append("e2e-tests")
    return jobs


def classify(paths: Iterable[str]) -> dict[str, object]:
    """Build the deterministic change-map recommendation for ``paths``."""

    raw_paths = list(paths)
    enumeration_failed = ENUMERATION_ERROR in raw_paths
    normalized: list[str] = []
    malformed: list[str] = []
    for raw in raw_paths:
        if not raw.strip() or raw == ENUMERATION_ERROR:
            continue
        path = _normalize(raw)
        if path is None:
            malformed.append(raw)
        else:
            normalized.append(path)

    changed = sorted(set(normalized))
    domains: set[str] = set()
    unknown: list[str] = []
    for path in changed:
        matched = _domains_for_path(path)
        if matched:
            domains.update(matched)
        else:
            unknown.append(path)

    unknown.extend(malformed)
    unknown = sorted(set(unknown))
    empty = not changed and not malformed and not enumeration_failed
    run_all = enumeration_failed or empty or bool(unknown)
    if enumeration_failed:
        reason = "enumeration_failed"
    elif empty:
        reason = "empty_changed_set"
    elif unknown:
        reason = "unclassified_paths"
    else:
        reason = "classified"

    suggested = _suggested_jobs(domains, run_all)
    return {
        "schema_version": 1,
        # Promoted 2026-08-14 (cicatrix superscar #2, "esiste ≠ armato": a
        # status field that keeps saying "shadow" after the caller starts
        # enforcing it is exactly the false-green this family warns about —
        # the next person to debug a skipped job would read this and assume
        # nothing gates on it). Literal, not derived: this module has exactly
        # one caller (.github/workflows/tests.yml's `changes` job) and it is
        # enforcing; there is no second "shadow" consumer to parametrize for.
        "mode": "enforcing",
        "reason": reason,
        "changed_file_count": len(changed),
        "domains": {name: name in domains for name in DOMAIN_NAMES},
        "unknown_paths": unknown,
        "run_all": run_all,
        "suggested_jobs": suggested,
        "would_skip": [job for job in TEST_JOBS if job not in suggested],
    }


def _read_paths(argv: list[str]) -> list[str]:
    if argv:
        return [line for arg in argv for line in arg.splitlines()]
    return sys.stdin.read().splitlines()


def main(argv: list[str] | None = None) -> int:
    result = classify(_read_paths(list(argv if argv is not None else sys.argv[1:])))
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
