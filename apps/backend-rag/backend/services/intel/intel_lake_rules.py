"""Intel Lake Tier 1 routing rules — single source of truth.

STDLIB-ONLY (only ``re``): imported both by the Fly in-process router
(``intel_lake_router.py``) and by the Pro-local fallback cron
(``scripts/intel-lake-router-a2/intel-lake-router-cron-standalone.py``),
which has zero backend/asyncpg-adjacent dependencies by design. Do not add
an import here that the standalone script cannot satisfy.

Routing categories:
- nb-intel: Indonesian regulatory/legal/AI research → push to NotebookLM NB-INTEL
- blog:    Indonesian press/news → eligible for balizero.com blog
- archive: OSINT social/reddit/twitter/youtube → keep for trend analysis only
- skip:    explicit drop (no current rules)
- needs_review: NO rule matched → Tier 2 LLM (weekly)

Design: research/symbiosis/2026-05-13-intel-lake-router-tier1-design.md
"""

from __future__ import annotations

import re
from typing import Any

# ─── NB-INTEL NotebookLM UUIDs (production, verified) ───────────────────────

NB_INTEL_IMMIGRATION = "78573978-4564-4bdc-b082-fbd625c2d33d"
NB_INTEL_TAX = "78b45ad8-ddce-4bd8-bdf0-3b45800897da"
NB_INTEL_REGULATION = "80821295-703f-40ab-a32a-f0307e43ae2a"
NB_INTEL_PRESS = "caec5b82-287c-464f-844f-02e2c8f04c21"
NB_INTEL_AI_RESEARCH = "d48c4933-4d93-4d1e-8753-23b88145ba78"

# ─── NB-PROBE-SANDBOX (Phase F, 2026-05-20) ─────────────────────────────────
# Dedicated NotebookLM for synthetic e2e probes. Never NB-INTEL family.
# Matching rule: source_domain == "probe-sandbox.example.test" (RFC 2606 .test
# TLD never resolves on the public internet — only probe scripts use it).
# Migration 187 CHECK constraint enforces canonical_url prefix at INSERT.
NB_PROBE_SANDBOX = "1e33e107-4064-48cd-b09d-f7f0a52b31ea"


# ─── Routing rules (closed-set, applied top-to-bottom; first match wins) ────

# 2-stage routing fix (PR-B1a 2026-05-20):
# Empirical bug: 90% of items fell to needs_review because regex `^kompas`
# fails to match `money.kompas.com`, `en.tempo.co`, `www.antaranews.com`
# (subdomain prefixes). Fix: tolerate press subdomain prefixes only for exact
# approved press roots.
# Plus: press_indonesian rule split into 2-stage (eligibility + content-gate)
# to send regulatory-keyword press to nb-intel/press instead of blog (which
# was starving NB-INTEL-Press notebook).
#
# 3-LLM panel approved (Gemini + Codex + DeepSeek convergent 2026-05-20):
# "Routing expansion MUST be 2-stage (domain + keyword)". Reference:
# .worktrees/audit-2026-05-20/docs/audit/2026-05-20-panel-verdict.md

# Tolerate press subdomain prefixes (e.g. `www.`, `en.`, `money.`, `sumsel.`).
# This is intentionally used for generic press domains only. Government and
# official-source rules stay strict so arbitrary-looking hostnames such as
# `malicious.imigrasi.go.id` do not bypass the review queue.
_SUBDOMAIN_PREFIX = r"(?:[a-z0-9-]+\.)*"
_PRESS_GENERAL_DOMAINS = (
    r"detik\.com|kompas\.com|tempo\.co|tribunnews\.com|"
    r"jakartapost\.com|thejakartapost\.com|antaranews\.com|"
    r"bisnis\.com|cnnindonesia\.com|kontan\.co\.id|"
    r"katadata\.co\.id|katadata\.id|"
    r"indonesiaexpat\.id|letsmoveindonesia\.com|expat\.com|"
    r"livenworkindonesia\.com|jakartaglobe\.id|investinasia\.id|"
    r"balinews\.live|chiangraitimes\.com"
)

# Content-gate keywords for stage-2 classification of generic press domains.
# When a domain matches `press_general` AND title/url contains one of these,
# route to nb-intel/press (NB-INTEL-Press notebook). Otherwise route to blog.
_PRESS_REGULATORY_KEYWORDS = (
    # Immigration
    "visa",
    "kitas",
    "kitap",
    "imigrasi",
    "voa",
    "golden visa",
    "c1 ",
    "c2 ",
    "d2 ",
    "d12",
    "e23",
    "e28",
    # Tax
    "pajak",
    "tax",
    "pph",
    "ppn",
    "spt",
    "vat",
    "pmk",
    "coretax",
    "npwp",
    # Regulation
    "kbli",
    "pt pma",
    "oss",
    "bkpm",
    "ruu",
    "peraturan",
    "perpres",
    "permenkumham",
    "permenkeu",
    "permenaker",
    "permenkes",
    "pp nomor",
    "uu nomor",
    "regulasi",
    # Compliance / financial
    "lkpm",
    "investasi",
    "investment",
    "compliance",
    "regulatory",
)


def _build_press_pattern(domains: str) -> re.Pattern[str]:
    """Build an exact hostname regex that tolerates press subdomains."""
    return re.compile(rf"^{_SUBDOMAIN_PREFIX}(?:{domains})$")


def _compile_keyword_pattern(keyword: str) -> re.Pattern[str]:
    """Compile a keyword matcher with token boundaries and flexible spacing."""
    escaped_parts = [re.escape(part) for part in keyword.strip().split()]
    body = r"[\s_-]+".join(escaped_parts)
    return re.compile(rf"(?<![a-z0-9]){body}(?![a-z0-9])")


_PRESS_REGULATORY_PATTERNS = tuple(
    _compile_keyword_pattern(keyword) for keyword in _PRESS_REGULATORY_KEYWORDS
)


_RULES: list[tuple[re.Pattern[str], str, dict[str, Any], str]] = [
    # ─── Sandbox probe (Phase F, 2026-05-20) ────────────────────────────────
    # Match EXACT RFC 2606 .test domain — never the public internet.
    # First rule so probes are routed before any other classification.
    # Uses ^...$ anchors via fullmatch semantics (pattern.match anchors at
    # start; explicit $ anchors at end) to prevent prefix attacks like
    # "probe-sandbox.example.test.evil.com".
    (
        re.compile(r"probe-sandbox\.example\.test$"),
        "nb-intel",
        {"nb_uuids": [NB_PROBE_SANDBOX]},
        "probe_sandbox",
    ),
    # Immigration (visa, KITAS, KITAP) → NB-INTEL-Immigration
    (
        re.compile(
            r"imigrasi\.go\.id|kanwilkemenkumham|kemenkumham\.go\.id|"
            r"kanim\.|jdih\.kemenkumham"
        ),
        "nb-intel",
        {"nb_uuids": [NB_INTEL_IMMIGRATION]},
        "immigration_govid",
    ),
    # Tax (PMK, PPh, SPT, Coretax) → NB-INTEL-Tax
    # 2026-09-22: pajak_monitor (PR #7074) writes source_domain as the item's
    # real host (e.g. `fiskal.kemenkeu.go.id`, `news.ddtc.co.id`, `muc.co.id`).
    # The original alternatives are anchored only at the start (`.match`), so
    # a subdomain BEFORE the token (kemenkeu/ddtc/muc) never matched. The 3
    # trailing alternatives below tolerate an arbitrary subdomain prefix and
    # anchor the END with `$`, without touching any existing byte above.
    (
        re.compile(
            r"pajak\.go\.id|ortax\.org|ddtcnews|mucconsulting|"
            r"ikpi\.or\.id|kemenkeu\.go\.id|jdih\.kemenkeu|"
            rf"{_SUBDOMAIN_PREFIX}kemenkeu\.go\.id$|"
            rf"{_SUBDOMAIN_PREFIX}ddtc\.co\.id$|"
            rf"{_SUBDOMAIN_PREFIX}muc\.co\.id$"
        ),
        "nb-intel",
        {"nb_uuids": [NB_INTEL_TAX]},
        "tax_govid",
    ),
    # Regulation/KBLI/PT PMA → NB-INTEL-Regulation
    (
        re.compile(
            r"bkpm\.go\.id|oss\.go\.id|kemendag\.go\.id|"
            r"jdih\.bkpm|jdih\.menpan|jdih\.setkab|peraturan\.go\.id"
        ),
        "nb-intel",
        {"nb_uuids": [NB_INTEL_REGULATION]},
        "regulation_govid",
    ),
    # AI research / academic → NB-INTEL-AIResearch
    (
        re.compile(
            r"arxiv\.org|github\.com|huggingface\.co|openai\.com|"
            r"anthropic\.com|deepmind\.com|paperswithcode"
        ),
        "nb-intel",
        {"nb_uuids": [NB_INTEL_AI_RESEARCH]},
        "ai_research",
    ),
    # Indonesian press / news (generic eligibility — content gate applied
    # below in `_press_content_gate`). Expanded 2026-05-20 to include
    # English-language Indonesia-facing news/expat portals.
    (
        _build_press_pattern(_PRESS_GENERAL_DOMAINS),
        "press_general",  # placeholder — content gate decides nb-intel/press vs blog
        {},
        "press_general",
    ),
    # OSINT social → archive
    (
        re.compile(r"^(reddit|twitter|x\.com|youtube|t\.co|medium\.com)"),
        "archive",
        {},
        "osint_social",
    ),
]


_PRESS_GENERAL_RE = _build_press_pattern(_PRESS_GENERAL_DOMAINS)


def _press_content_gate(title: str | None, canonical_url: str | None) -> bool:
    """Stage-2 gate: True if title/url contains a regulatory keyword.

    Used by `press_general` rule to split into:
      - nb-intel/press   (regulatory content — feed NB-INTEL-Press)
      - blog             (general news — keep for balizero.com blog only)
    """
    haystack = " ".join(filter(None, [title, canonical_url])).lower()
    if not haystack:
        return False
    return any(pattern.search(haystack) for pattern in _PRESS_REGULATORY_PATTERNS)


def classify(
    source_domain: str | None,
    title: str | None = None,
    canonical_url: str | None = None,
) -> dict[str, Any]:
    """Apply rules, return routing decision. NO DB I/O. None-safe.

    2-stage routing for ``press_general`` rule (PR-B1a 2026-05-20):
    - Stage 1 (eligibility): domain matches the press_general pattern
    - Stage 2 (content gate): title/url contains regulatory keyword
      → upgrade to ``nb-intel`` targeting NB-INTEL-Press
      → otherwise route to ``blog`` (existing legacy behavior)

    All other rules unchanged.
    """
    domain = (source_domain or "").strip().lower()
    for pattern, status, targets, rule_name in _RULES:
        if pattern.match(domain):
            # 2-stage gate for generic press domains
            if status == "press_general":
                if _press_content_gate(title, canonical_url):
                    return {
                        "status": "nb-intel",
                        "targets": {"nb_uuids": [NB_INTEL_PRESS]},
                        "rule": f"{rule_name}+regulatory",
                    }
                return {
                    "status": "blog",
                    "targets": {},
                    "rule": f"{rule_name}+general",
                }
            return {"status": status, "targets": targets, "rule": rule_name}
    return {"status": "needs_review", "targets": {}, "rule": "no_match"}
