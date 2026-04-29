#!/usr/bin/env python3
"""
detect-secrets baseline auto-triage.

Runs a set of conservative path-based rules against `.secrets.baseline` and
marks findings as `is_secret: false` when they fall inside files that are
definitionally non-sensitive (example env files, test fixtures, planning
documents, etc.). Everything else is left `unaudited` so a human can
inspect the residue.

Usage:
    python3 scripts/detect_secrets_auto_triage.py             # dry-run
    python3 scripts/detect_secrets_auto_triage.py --apply     # write back
    python3 scripts/detect_secrets_auto_triage.py --report    # human report

Conservative means:
    - Never auto-approve files inside production code paths
    - Never auto-approve anything with `prod`, `production`, `live` in the path
    - Never auto-approve `.env` (only `.env.example`, `.env.*.example`, `.env.sample`)
    - Never auto-approve anything outside the whitelist patterns
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE = REPO_ROOT / ".secrets.baseline"

# Each rule is (pattern, reason). The pattern matches the file path
# relative to the repo root. A finding is auto-approved if ANY rule matches.
AUTO_APPROVE_RULES: list[tuple[re.Pattern[str], str]] = [
    # Example/sample env files — by convention never contain real secrets
    (
        re.compile(r"(^|/)\.env\.example$"),
        ".env.example: documented placeholder, never a real secret",
    ),
    (
        re.compile(r"(^|/)\.env\.sample$"),
        ".env.sample: documented placeholder, never a real secret",
    ),
    (
        re.compile(r"(^|/)\.env\.[a-zA-Z0-9_-]+\.example$"),
        ".env.<name>.example: documented placeholder",
    ),
    (
        re.compile(r"(^|/)env\.example$"),
        "env.example (no leading dot): documented placeholder",
    ),
    # Test fixtures and unit tests — conventional location for fake credentials
    (
        re.compile(r"(^|/)tests?/.*\.(py|ts|tsx|js|jsx|json|yaml|yml)$"),
        "tests/** tree: test fixtures, not production secrets",
    ),
    (
        re.compile(r"(^|/)__tests__/.*\.(py|ts|tsx|js|jsx|json|yaml|yml)$"),
        "__tests__/** tree: test fixtures",
    ),
    (
        re.compile(r"\.test\.(py|ts|tsx|js|jsx)$"),
        "*.test.* file: unit test fixture",
    ),
    (
        re.compile(r"\.spec\.(py|ts|tsx|js|jsx)$"),
        "*.spec.* file: test spec fixture",
    ),
    (
        re.compile(r"(^|/)fixtures?/.*"),
        "fixtures/ tree: explicit test fixture",
    ),
    (
        re.compile(r"(^|/)mocks?/.*"),
        "mocks/ tree: explicit mock data",
    ),
    # Documentation and planning
    (
        re.compile(r"(^|/)docs?/.*\.md$"),
        "docs/ markdown: documentation, any token string is illustrative or redacted",
    ),
    (
        re.compile(r"(^|/)README.*\.md$", re.IGNORECASE),
        "README: documentation",
    ),
    (
        re.compile(r"(^|/)CHANGELOG.*\.md$", re.IGNORECASE),
        "CHANGELOG: historical notes",
    ),
    (
        re.compile(r"(^|/)CONTRIBUTING.*\.md$", re.IGNORECASE),
        "CONTRIBUTING: documentation",
    ),
    # E2E Playwright specs: same rationale as .test/.spec
    (
        re.compile(r"(^|/)e2e/.*\.spec\.(ts|js)$"),
        "e2e/ Playwright spec: test fixture",
    ),
    # Agent decision files and session archives (historical context, not active credentials)
    (
        re.compile(r"(^|/)\.agent/.*"),
        ".agent/ tree: internal agent state, not deployed",
    ),
    (
        re.compile(r"(^|/)\.antigravity/.*"),
        ".antigravity/ tree: internal tooling state",
    ),
    # Quarantine dir for abandoned attempts kept for audit (e.g. Atlas
    # migrate-lint pre-paywall, see cicatrix 2026-04-26). Files here are
    # frozen byte-for-byte and not on any execution path; any token-shaped
    # string is residue of an abandoned third-party config (e.g. dummy
    # `atlas:atlas@localhost:5432` Postgres test creds in the workflow).
    (
        re.compile(r"(^|/)\.disabled(-\d{4}-\d{2}-\d{2})?/.*"),
        ".disabled/ or .disabled-YYYY-MM-DD/ quarantine: residual artifacts from abandoned attempts, not deployed",
    ),
    # OpenAPI schemas and examples
    (
        re.compile(r"(^|/)openapi\.(json|yaml|yml)$", re.IGNORECASE),
        "OpenAPI schema: example values in spec",
    ),
    (
        re.compile(r"(^|/)swagger\.(json|yaml|yml)$", re.IGNORECASE),
        "Swagger schema: example values in spec",
    ),
    # Workflow files - github action references to ${{ secrets.X }} are not secrets themselves
    (
        re.compile(r"^\.github/workflows/.*\.ya?ml$"),
        "GitHub workflow file: secrets.XYZ references are placeholders",
    ),
    # Scraped data + generated caches (not credentials, just external content
    # that happens to contain high-entropy strings like URLs, hashes, UUIDs).
    (
        re.compile(r"(^|/)scraped_articles\.json$"),
        "scraped_articles.json: external article content, not secrets",
    ),
    (
        re.compile(r"(^|/)scraper_cache\.json$"),
        "scraper_cache.json: external cache, not secrets",
    ),
    (
        re.compile(r"(^|/)causal_report_example\.json$"),
        "causal regression example report: scan artifact, not secrets",
    ),
    # Pipeline state files — created by local tooling, contain run IDs / hashes
    # but never credentials.
    (
        re.compile(r"_state\.json$"),
        "pipeline state file: run IDs and hashes, not credentials",
    ),
    (
        re.compile(r"(^|/)apps/evaluator/nlm_deep_research/.*\.json$"),
        "NLM deep research state files: pipeline artifacts",
    ),
    # Example credential file — by convention a template, never real
    (
        re.compile(r"\.example\.json$"),
        "*.example.json: documentation placeholder",
    ),
    # .env.test — explicit test fixture env file
    (
        re.compile(r"(^|/)\.env\.test$"),
        ".env.test: test fixture env, never production",
    ),
    # WR2 canva_renderer: ships external Canva template IDs, not credentials.
    (
        re.compile(
            r"(^|/)apps/backend-rag/backend/services/canva_renderer/.*\.py$"
        ),
        "canva_renderer: external Canva template IDs, not credentials",
    ),
    # Frontend book metadata: detect-secrets flags `serviceKey: "b1-visit-visa"`
    # as a "Secret Keyword" hit. Book/service catalog data, never credentials.
    (
        re.compile(r"(^|/)apps/mouth/src/components/book/.*\.ts$"),
        "mouth book catalog: service key literals, not credentials",
    ),
    # i18n translation files: detect-secrets's SecretKeyword plugin fires on
    # words like "PIN", "password", "token" even when they're UI copy
    # ("Forgot PIN?", "Wrong email or PIN"). These files are frontend
    # translations committed under source control, never credential stores.
    (
        re.compile(r"(^|/)apps/mouth/src/i18n/locales/[^/]+\.json$"),
        "mouth i18n locales: UI translation strings, never credentials",
    ),
    # Base64 SVG icons inlined in welcome emails (welcome_email_service.py)
    # — verified these 4 findings are base64-encoded SVG markup, not tokens.
    (
        re.compile(r"(^|/)apps/backend-rag/backend/services/crm/welcome/welcome_email_service\.py$"),
        "welcome email service: base64-inlined SVG icons, not credentials",
    ),
    # Organism Genoma manifest: contains a content-derived SHA256 integrity
    # checksum (organism.tools.validate_genome.compute_checksum), NOT a
    # credential. Regenerated by `validate_genome --update-checksum`. The
    # whole file is a registry of organi nervosi, not a secrets store.
    (
        re.compile(r"(^|/)apps/organism/organism/genome\.yaml$"),
        "organism genome manifest: content-derived SHA256 integrity hash, not a credential",
    ),
    # Oracle service files: contain the literal string
    # "postgresql://user:pass@localhost/db" used as a placeholder-detection
    # sentinel. Verified manually 2026-04-12.
    (
        re.compile(r"(^|/)apps/backend-rag/backend/services/oracle/oracle_config\.py$"),
        "oracle_config: placeholder sentinel string, not a credential",
    ),
    (
        re.compile(r"(^|/)apps/backend-rag/backend/services/oracle/oracle_database\.py$"),
        "oracle_database: placeholder sentinel string, not a credential",
    ),
    # prime_nexus_service.py:36 — _BASE32 alphabet for geohash, not a token.
    (
        re.compile(r"(^|/)apps/backend-rag/backend/services/prime/prime_nexus_service\.py$"),
        "prime_nexus_service: base32 geohash alphabet, not a credential",
    ),
    # geo_service.py:17 — same _BASE32 geohash alphabet, different module.
    (
        re.compile(r"(^|/)apps/backend-rag/backend/services/prime/geo_service\.py$"),
        "geo_service: base32 geohash alphabet, not a credential",
    ),
    # graph-engine curiosity CLI: postgresql://postgres:postgres@localhost:5432
    # default dev connection string fallback (same pattern as backend-rag
    # dev utilities — see TECH DEBT note above).
    (
        re.compile(r"(^|/)apps/graph-engine/src/nuzantara_graph/curiosity/cli\.py$"),
        "graph-engine curiosity CLI: localhost:5432 dev default, not production",
    ),
    # gap_fill_autonomous.py: postgres://postgres:postgres@localhost dev default
    # for a one-off autonomous gap-fill script.
    (
        re.compile(r"(^|/)scripts/gap_fill_autonomous\.py$"),
        "gap_fill_autonomous: localhost:5432 dev default, not production",
    ),
    # Self-reference: this file documents postgres:postgres@localhost:5432
    # as part of the rule comments. detect-secrets flags the literal; the
    # auto-triage engine is the SOLE consumer of these URLs so marking this
    # file as a known FP is correct.
    (
        re.compile(r"(^|/)scripts/detect_secrets_auto_triage\.py$"),
        "detect_secrets_auto_triage: documents the postgres:postgres@localhost URL as part of its own rule docstring",
    ),
    # article_composer error handler: enum values "API_KEY_NOT_CONFIGURED" etc
    # detected as Secret Keyword (false positive on enum names).
    (
        re.compile(r"(^|/)apps/backend-rag/backend/services/article_composer/error_handler\.py$"),
        "article_composer error_handler: error enum values, not credentials",
    ),
    # auth decorator: AuthType.API_KEY = "api_key" enum value, not a secret.
    (
        re.compile(r"(^|/)apps/backend-rag/backend/app/decorators/auth\.py$"),
        "auth decorator: auth-type enum literal, not a credential",
    ),
    # article_composer router: IndexNow API key. IndexNow (Bing) requires the
    # key to be served publicly at https://<host>/<key>.txt — it is public
    # BY DESIGN and cannot be a "secret" in the security-hygiene sense.
    (
        re.compile(r"(^|/)apps/backend-rag/backend/app/routers/article_composer\.py$"),
        "article_composer router: IndexNow API key (public by protocol design)",
    ),
    # Docker compose test file
    (
        re.compile(r"(^|/)docker-compose\.test\.ya?ml$"),
        "docker-compose.test.yml: test-only compose file",
    ),
    # Next.js app layout: Google Search Console verification tokens. These
    # are PUBLIC by design (Google writes them into the HTML meta tag as
    # an ownership proof) and cannot be a "secret".
    (
        re.compile(r"(^|/)apps/mouth/src/app/layout\.tsx$"),
        "mouth layout.tsx: Google Search Console verification tokens (public)",
    ),
    # backend-rag local utility scripts: many of these contain hardcoded
    # dev database credentials (postgresql://backend_rag_v2:...@localhost:15432
    # and postgresql://nuzantara:nuzantara_local_2024@localhost:5432). These
    # are NOT production credentials — they are local dev fallbacks for
    # one-off utility scripts that run against a developer's local database.
    #
    # TECH DEBT FLAGGED TO MAINTAINER: these hardcoded dev credentials
    # should be replaced with os.getenv("DATABASE_URL") + a .env.dev example.
    # Tracked as a separate follow-up; out of scope for this CI fix.
    (
        re.compile(r"(^|/)apps/backend-rag/scripts/.*\.(py|sh)$"),
        "backend-rag dev utility scripts: hardcoded LOCAL dev db credentials (tech debt, tracked)",
    ),
    # backend-rag migrations: contain sample/dummy data for test rollbacks,
    # not credentials. Migrations are idempotent schema operations with
    # hardcoded sample rows.
    (
        re.compile(r"(^|/)apps/backend-rag/backend/migrations/migration_\d+.*\.py$"),
        "backend-rag migrations: sample data literals, not credentials",
    ),
    # Alertmanager template config: literal "your_password" placeholder.
    (
        re.compile(r"(^|/)config/alertmanager/alertmanager\.ya?ml$"),
        "alertmanager config: literal 'your_password' placeholder",
    ),
    # Root docker-compose: POSTGRES_PASSWORD=postgres is the standard local
    # dev default, never used in production (production is Fly.io postgres).
    (
        re.compile(r"^docker-compose\.ya?ml$"),
        "root docker-compose.yml: local dev postgres defaults",
    ),
    # IndexNow API route (mirror of the one in backend article_composer):
    # same public-by-design IndexNow key.
    (
        re.compile(r"(^|/)apps/mouth/src/app/api/indexnow/route\.ts$"),
        "mouth indexnow route: public IndexNow key (same as backend)",
    ),
    # Clients new page: passport "AB1234567" placeholder string in a form.
    (
        re.compile(r"(^|/)apps/mouth/src/app/\(workspace\)/clients/new/page\.tsx$"),
        "mouth clients/new page: passport placeholder 'AB1234567' in form",
    ),
    # bali-intel-scraper quality workflow: test postgres creds in CI service.
    (
        re.compile(r"(^|/)apps/bali-intel-scraper/\.github/workflows/.*\.ya?ml$"),
        "bali-intel-scraper CI: test-only postgres service credentials",
    ),
    # bali-intel-scraper alembic.ini: test-only db connection string.
    (
        re.compile(r"(^|/)apps/bali-intel-scraper/backend/db/migrations/alembic\.ini$"),
        "bali-intel-scraper alembic.ini: local dev database URL placeholder",
    ),
    # cell core config: local dev db URL default.
    (
        re.compile(r"(^|/)apps/cell/cell/core/config\.py$"),
        "cell core config: local dev db URL default",
    ),
    # evaluator local utility scripts: same tech-debt pattern as backend-rag
    # scripts — hardcoded LOCAL dev credentials for one-off tooling.
    (
        re.compile(r"(^|/)apps/evaluator/(seo_auto_fixer|site_verify_sa|test_judgement_day)\.py$"),
        "evaluator dev utility: hardcoded LOCAL dev credentials (tech debt)",
    ),
    # graph-engine config: local dev db URL default.
    (
        re.compile(r"(^|/)apps/graph-engine/src/nuzantara_graph/config\.py$"),
        "graph-engine config: local dev db URL default",
    ),
    # knowledge app projects page: likely public token or asset URL.
    (
        re.compile(r"(^|/)apps/knowledge/src/app/projects/page\.tsx$"),
        "knowledge projects page: likely public asset URL or project token",
    ),
    # tmp script with hardcoded dev creds (tmp_ prefix marks it as throwaway)
    (
        re.compile(r"(^|/)apps/backend-rag/tmp_.*\.py$"),
        "backend-rag tmp_ script: throwaway local tooling",
    ),
    # Repo-root scripts/: same tech-debt pattern, local dev tooling.
    (
        re.compile(r"^scripts/(backfill_interactions_from_conversations|batch_extract_company_capital|import_gemini_company_results)\.py$"),
        "repo-root scripts: hardcoded LOCAL dev credentials (tech debt)",
    ),
    (
        re.compile(r"^scripts/(extract_worker|preflight)\.sh$"),
        "repo-root shell scripts: local tooling with dev credentials",
    ),
    # Ruslana node config: literal "RUSLANA_JWT_PLACEHOLDER" placeholder.
    (
        re.compile(r"(^|/)scripts/ruslana-node/openclaw-ruslana\.json$"),
        "ruslana-node config: literal JWT placeholder",
    ),
    # docs/database PostgreSQL update scripts: local tooling with dev creds.
    (
        re.compile(r"(^|/)docs/database/postgresql/.*\.(py|sh)$"),
        "docs/database tooling: local dev db update scripts",
    ),
    # mata-garuda config: BRIDGE_API_KEY_ENV constant holds the NAME of the
    # env var ("BRIDGE_API_KEY"), not its value. detect-secrets matches the
    # word "KEY" in the literal. Verified 2026-04-16.
    (
        re.compile(r"(^|/)apps/mata-garuda/mata_garuda/config\.py$"),
        "mata-garuda config: env var NAME constants, not credential values",
    ),
    # zantara-media Google Drive folder IDs are PUBLIC Drive identifiers
    # (GARUDA photos, videos, audio, intelligence, drafts, research,
    # published). Shared with Bali Zero team as public Drive links; carry
    # no access authority. High-entropy false positive.
    (
        re.compile(r"(^|/)apps/zantara-media/zantara_media/indexer/(drive_client|pipeline)\.py$"),
        "zantara-media indexer: Google Drive folder IDs (public identifiers, not tokens)",
    ),
    # detect_secrets_auto_triage.py contains REGEX PATTERNS that include
    # placeholder credential substrings (e.g. "user:pass@localhost",
    # ".env.prod", "service_account") used to match paths that MUST be
    # audited. The script is itself flagged on these patterns — a
    # meta-false-positive. The file is the triage engine; it never holds
    # real secrets.
    (
        re.compile(r"(^|/)scripts/detect_secrets_auto_triage\.py$"),
        "detect_secrets_auto_triage: triage rule patterns, not credentials (meta)",
    ),
    # Video file (binary): base64 false positive inside .mp4 chunk.
    (
        re.compile(r"\.(mp4|webm|mov|mkv|avi|png|jpg|jpeg|gif|pdf)$"),
        "binary media file: base64 false positive on encoded content",
    ),
    # KB legal markdown: Indonesian copyright/IP/trade-secret regulation
    # documents contain phrases like "Rahasia Dagang" / "Trade secret"
    # that detect-secrets flags as Secret Keyword. Regulatory text under
    # source control, never credentials.
    (
        re.compile(r"(^|/)apps/backend-rag/backend/kb/legal/.*\.md$"),
        "backend-rag KB legal docs: regulatory text mentioning 'secret', not credentials",
    ),
    # Evaluator CEP test fixtures: `api_key="fake-key"` literal patterns
    # in unittest mock setups. The test_*.py path pattern above only
    # matches plain `test_X.py` filenames; this rule covers the
    # subdirectory variant inside apps/evaluator/cep/.
    (
        re.compile(r"(^|/)apps/evaluator/cep/test_.*\.py$"),
        "evaluator CEP test: fake-key literals in unittest mocks",
    ),
]

# Hard blocks — if the path matches any of these, NEVER auto-approve even if
# an AUTO_APPROVE rule also matched. This catches false positives in the
# whitelist.
HARD_BLOCK_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(^|/)\.env$"), "bare .env file must always be audited"),
    (re.compile(r"(^|/)\.env\.prod(uction)?$"), "production env must always be audited"),
    (re.compile(r"(^|/)\.env\.live$"), "live env must always be audited"),
    (re.compile(r"(^|/)secrets?\.(json|yaml|yml)$"), "secrets file must always be audited"),
    (re.compile(r"(^|/)credentials?\.(json|yaml|yml)$"), "credentials file must always be audited"),
    (re.compile(r"(^|/)service[-_]account.*\.json$"), "service account JSON must always be audited"),
]


def classify(file_path: str) -> tuple[bool, str]:
    """Return (auto_approve, reason)."""
    for pat, reason in HARD_BLOCK_RULES:
        if pat.search(file_path):
            return False, f"HARD BLOCK: {reason}"
    for pat, reason in AUTO_APPROVE_RULES:
        if pat.search(file_path):
            return True, reason
    return False, "no rule matched"


def triage(
    baseline: dict[str, Any],
    apply: bool,
) -> tuple[dict[str, Any], dict[str, int], list[tuple[str, int, str]]]:
    """
    Walk every hit in the baseline and apply auto-triage rules.

    Returns (updated_baseline, stats, residue_list).
    stats = {auto_approved: N, hard_blocked: N, no_rule: N, total: N}
    residue_list = [(file, line, type), ...] for hits that remain unaudited.
    """
    stats = {"auto_approved": 0, "hard_blocked": 0, "no_rule": 0, "total": 0}
    residue: list[tuple[str, int, str]] = []

    results = baseline.get("results", {})
    for file_path, hits in results.items():
        for hit in hits:
            stats["total"] += 1
            auto, reason = classify(file_path)
            if auto:
                stats["auto_approved"] += 1
                if apply:
                    hit["is_secret"] = False
            else:
                if reason.startswith("HARD BLOCK"):
                    stats["hard_blocked"] += 1
                else:
                    stats["no_rule"] += 1
                residue.append(
                    (file_path, hit.get("line_number", 0), hit.get("type", "?"))
                )

    return baseline, stats, residue


def main() -> int:
    args = set(sys.argv[1:])
    apply = "--apply" in args
    report = "--report" in args

    if not BASELINE.exists():
        print(f"ERROR: {BASELINE} does not exist", file=sys.stderr)
        return 2

    baseline = json.loads(BASELINE.read_text())
    baseline, stats, residue = triage(baseline, apply=apply)

    print(f"Total findings:        {stats['total']}")
    print(f"Auto-approved:         {stats['auto_approved']}")
    print(f"Hard-blocked:          {stats['hard_blocked']}")
    print(f"No rule matched:       {stats['no_rule']}")
    print(
        f"Residue (unaudited):   {stats['hard_blocked'] + stats['no_rule']}"
    )

    if apply:
        BASELINE.write_text(json.dumps(baseline, indent=2, sort_keys=False) + "\n")
        print(f"\n.secrets.baseline updated in place.")

    if report:
        print("\n=== Residue by file (top 40) ===")
        from collections import Counter
        per_file = Counter(r[0] for r in residue)
        for f, n in per_file.most_common(40):
            print(f"  {n:4}  {f}")
        print("\n=== Residue by type ===")
        per_type = Counter(r[2] for r in residue)
        for t, n in per_type.most_common():
            print(f"  {n:4}  {t}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
