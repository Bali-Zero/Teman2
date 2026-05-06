"""Seed the Skill Registry with hand-picked canonical Bali Zero skills.

Companion to ``catalog_initial_skills.py``. Where the catalog does
AST-based discovery across the whole repo (hundreds of noisy candidates),
this script ships a curated seed of ~32 skills — each with a real
precondition, procedure, and success_criterion distilled from production
runbooks, scars, and the zantara_core prompt.

Usage:

    # Dry-run — print what would be written, touch nothing.
    PYTHONPATH=. python backend/scripts/seed_initial_skills.py

    # Write into the canonical Genome (default: ~/.nuzantara/experience.db).
    PYTHONPATH=. python backend/scripts/seed_initial_skills.py --apply

    # Point at an explicit DB (used by tests and one-off imports).
    PYTHONPATH=. python backend/scripts/seed_initial_skills.py \\
        --db-path /tmp/test.db --apply

Idempotent: skill_ids are stable; re-running updates the procedure while
``Genome.record_skill`` keeps the max(confidence).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# Canonical seed. Each dict maps 1:1 to Genome.record_skill kwargs.
# Confidence starts at 0.6 (above default 0.5) because these are curated
# from real production behaviour, not discovery.
SEED_SKILLS: list[dict[str, Any]] = [
    # ─── experience / memory cell ─────────────────────────────────
    {
        "cell": "experience",
        "skill_id": "experience:normalize_outcome",
        "procedure": (
            "Map free-text outcome tokens to the strict success|failure|partial "
            "enum; return None for ambiguous tokens (completed, done, unknown) "
            "rather than guessing."
        ),
        "precondition": "Raw outcome string from LAM episode or cell pulse reflection.",
        "success_criterion": "Only strict tokens cross into Experience Library; noise stays out.",
        "confidence": 0.7,
    },
    {
        "cell": "experience",
        "skill_id": "experience:record_trajectory",
        "procedure": (
            "Persist sense→think→act→reflect episode via POST /api/experience/record. "
            "Use outcome=failure for Personal-scope scars; success/partial go Project."
        ),
        "precondition": "Pulse has completed with measurable outcome + optional tokens/duration.",
        "success_criterion": "Row appears in genome with type='trajectory' and correct scope.",
        "confidence": 0.7,
    },

    # ─── RAG / retrieval cell ─────────────────────────────────────
    {
        "cell": "rag",
        "skill_id": "rag:hybrid_search_rrf",
        "procedure": (
            "Combine BM25 + dense vector retrieval via Reciprocal Rank Fusion, "
            "then re-rank top-20 with CrossEncoder. Never skip reranking on "
            "authoritative domains (KBLI, visa)."
        ),
        "precondition": "Qdrant + BM25 stores populated; CrossEncoder loaded.",
        "success_criterion": "Top-5 recall > 0.85 on RAGAS canary set.",
        "confidence": 0.8,
    },
    {
        "cell": "rag",
        "skill_id": "rag:evidence_score_gate",
        "procedure": (
            "Gate final answer on evidence score: <0.15 ABSTAIN, 0.15-0.60 "
            "CAUTIOUS with disclaimer, >0.60 NORMAL. Do NOT override to NORMAL "
            "just because the LLM produced prose — check trusted_tools_used."
        ),
        "precondition": "Reasoner has scored retrieval chunks against query.",
        "success_criterion": "Hallucinated answers on empty retrieval are blocked.",
        "confidence": 0.85,
    },
    {
        "cell": "rag",
        "skill_id": "rag:chunk_with_overlap",
        "procedure": (
            "Split documents into 10000-char windows with 800-char overlap. "
            "Preserve section boundaries when possible; never split mid-table."
        ),
        "precondition": "Document pre-processed (OCR done, layout normalised).",
        "success_criterion": "No chunk loses context needed for its neighbour's question.",
        "confidence": 0.8,
    },

    # ─── KBLI cell ────────────────────────────────────────────────
    {
        "cell": "kbli",
        "skill_id": "kbli:flat_payload_contract",
        "procedure": (
            "Always use flat Qdrant payload: kode_kbli, judul, content, sektor_id, "
            "pma_status, skala_usaha, kategori_risiko. Nested dicts break filters "
            "and the UI breadcrumbs."
        ),
        "precondition": "Writing to the kbli_chunks Qdrant collection.",
        "success_criterion": "Filter by kode_kbli = 'XXXXX' returns all chunks.",
        "confidence": 0.9,
    },
    {
        "cell": "kbli",
        "skill_id": "kbli:code_classification",
        "procedure": (
            "Route KBLI classification queries through Gemini search (federation) "
            "instead of Claude — regulations hallucination risk is documented."
        ),
        "precondition": "User query mentions a KBLI code or business sector.",
        "success_criterion": "Grounded answer with source URL from imigrasi/BKPM.",
        "confidence": 0.8,
    },

    # ─── Pricing cell ─────────────────────────────────────────────
    {
        "cell": "pricing",
        "skill_id": "pricing:only_from_tool",
        "procedure": (
            "Retrieve every price via PricingTool. Never infer from KG HAS_FEE "
            "edges (those are government PNBP fees, not Bali Zero quotes). "
            "If a price is missing, respond 'da verificare con il team'."
        ),
        "precondition": "User question has a cost/price shape.",
        "success_criterion": "No invented numbers; all quoted prices traceable to bali_zero_official_prices_2026.json.",
        "confidence": 0.9,
    },

    # ─── akta / document parsing cell ─────────────────────────────
    {
        "cell": "akta",
        "skill_id": "akta:detect_surat_kuasa_proxies",
        "procedure": (
            "Run regex for 'bertindak berdasarkan' / 'surat kuasa' BEFORE the LLM "
            "pass; flag those rows as proxies, not founders. LLM alone misses them "
            "about 15% of the time."
        ),
        "precondition": "OCR text from Indonesian akta pendirian.",
        "success_criterion": "Zero procuratori leak into the founders table.",
        "confidence": 0.85,
    },
    {
        "cell": "akta",
        "skill_id": "akta:ocr_all_pages",
        "procedure": (
            "Always OCR every page of the akta — directors typically appear on "
            "page 2 or 3, not page 1. Use qwen2.5vl:7b (the only vision-capable "
            "local model) with 120s timeout when >3 pages."
        ),
        "precondition": "PDF akta uploaded; OCR pipeline available.",
        "success_criterion": "Directors array populated even when page 1 is cover/seal.",
        "confidence": 0.9,
    },

    # ─── DLP / safety cell ────────────────────────────────────────
    {
        "cell": "safety",
        "skill_id": "safety:dlp_pre_publish",
        "procedure": (
            "Run DLP scan on any draft caption / post / outbound message before "
            "publish. On match, block and emit a 'dlp_hit' trajectory with the "
            "matched rule id; never log the raw PII."
        ),
        "precondition": "Draft content ready, before network send.",
        "success_criterion": "No PII egress; operator sees which rule triggered.",
        "confidence": 0.9,
    },

    # ─── ingestion / chunk pipeline ───────────────────────────────
    {
        "cell": "ingestion",
        "skill_id": "ingestion:uuid5_for_qdrant_ids",
        "procedure": (
            "When ingesting external files (Drive, S3) into Qdrant, map the "
            "external file_id to a UUID via uuid5(namespace, file_id). Qdrant "
            "point IDs must be UUID — raw file IDs fail silently."
        ),
        "precondition": "Upserting a point into any Qdrant collection.",
        "success_criterion": "Idempotent upsert; same source file maps to same point.",
        "confidence": 0.85,
    },

    # ─── CRM cell ─────────────────────────────────────────────────
    {
        "cell": "crm",
        "skill_id": "crm:lkpm_cascade_via_company_id",
        "procedure": (
            "Portal LKPM cascade MUST go via r.company_id (joined through "
            "client_company_links), NEVER r.client_id. Historical rows mix "
            "client_id=company_id (Lori import) with real client_id."
        ),
        "precondition": "Building portal history/receipts query for a client.",
        "success_criterion": "PIM DE BOER (11139) sees PT HANG LOOSE COMPAGNY (2327) reports.",
        "confidence": 0.95,
    },
    {
        "cell": "crm",
        "skill_id": "crm:invalidate_cache_after_mutation",
        "procedure": (
            "After any CRM write, call invalidate_cache('zantara:crm_clients_stats:*') "
            "AND invalidate_cache('zantara:crm_practices:*'). Stale cache is the "
            "#1 dashboard bug."
        ),
        "precondition": "CRM POST/PATCH/DELETE completed successfully.",
        "success_criterion": "Next GET returns fresh aggregate.",
        "confidence": 0.9,
    },
    {
        "cell": "crm",
        "skill_id": "crm:minors_in_parent_family_section",
        "procedure": (
            "Minors (<18) belong inside the parent client's family section, "
            "NOT as their own Drive profile. Create a standalone profile only "
            "when the client turns 18."
        ),
        "precondition": "Processing a family record with dependents.",
        "success_criterion": "No orphan minor folders in Drive CRM root.",
        "confidence": 0.85,
    },

    # ─── crm cell — renewals domain (Sprint 1.A 2026-05-02) ───────
    {
        "cell": "crm",
        "skill_id": "crm:detect_expiring_kitas",
        "procedure": (
            "Query clients table for KITAS expiring in [today, today + N days]. "
            "Return list of (client_id, days_until_expiry, kitas_expiry_date) "
            "ordered by urgency. Source column: clients.kitas_expiry_date. "
            "Filter out clients with deleted_at IS NOT NULL."
        ),
        "precondition": "kitas_expiry_date populated for active clients (data quality assumption).",
        "success_criterion": "All clients with KITAS expiring within window are returned, none missed.",
        "confidence": 0.6,
        "domain": "crm",
    },
    {
        "cell": "crm",
        "skill_id": "crm:propose_renewal_outreach",
        "procedure": (
            "For each (client_id, days_until_expiry) from detect_expiring_kitas, "
            "build a Proposal with channel='whatsapp', urgency = "
            "{<=7d: 'critical', <=30d: 'high', <=60d: 'medium', else: 'low'}, "
            "and a one-line reasoning string. Skip clients with last_outreach < 14 days ago."
        ),
        "precondition": "crm:detect_expiring_kitas produced at least one candidate.",
        "success_criterion": "One Proposal per eligible client; correct urgency tier; no duplicates within 14d.",
        "confidence": 0.6,
        "domain": "crm",
    },
    {
        "cell": "crm",
        "skill_id": "crm:draft_wa_renewal_message",
        "procedure": (
            "Generate WhatsApp draft via Ollama deepseek-r1:32b on Pro local. "
            "Template parameters: client.full_name, kitas_expiry_date, days_until_expiry, "
            "client.preferred_language (default 'en'). Output <= 1000 chars. "
            "Never include NPWP / NIB / passport in payload outside Pro local."
        ),
        "precondition": "Proposal approved by Zero via Telegram; client.phone populated.",
        "success_criterion": "Draft text generated, locale-correct, <= 1000 chars, zero PII leakage.",
        "confidence": 0.6,
        "domain": "crm",
    },
    {
        "cell": "crm",
        "skill_id": "crm:measure_renewal_conversion",
        "procedure": (
            "Cron 24h post-execute: SELECT outcome FROM renewal_alert_outcomes "
            "WHERE alert_id IN (recent_proposals_24h) GROUP BY outcome. "
            "Compute conversion_rate = client_renewed / total_executed. "
            "Store in materialized view renewal_baseline_2024_2026 (Sprint 0 §3.4)."
        ),
        "precondition": "Outreach Proposal executed at least 24h ago; renewal_alert_outcomes populated.",
        "success_criterion": "Conversion rate computed per (skill, segment) tuple; updated weekly.",
        "confidence": 0.6,
        "domain": "crm",
    },
    {
        "cell": "crm",
        "skill_id": "crm:update_renewal_confidence",
        "procedure": (
            "Lamarckian update: on outcome='client_renewed' bump confidence by +0.05 (max 0.95). "
            "On outcome='expired_no_action' decay confidence by -0.10 (min 0.10). "
            "Call Genome.record_skill with new confidence; valid_from = NOW()."
        ),
        "precondition": "At least N=10 outcomes observed for this skill in last 30 days.",
        "success_criterion": "Confidence drifts toward empirical conversion_rate over time; bounded [0.10, 0.95].",
        "confidence": 0.6,
        "domain": "crm",
    },

    # ─── visa / oracle cell ───────────────────────────────────────
    {
        "cell": "visa_oracle",
        "skill_id": "visa_oracle:regulatory_via_gemini_search",
        "procedure": (
            "Dispatch visa / normative queries through Gemini search, NOT "
            "Claude. Claude hallucinates on Indonesian regulation specifics; "
            "Gemini search returns citations."
        ),
        "precondition": "Query mentions KITAS/KITAP/B211/VOA or a visa code.",
        "success_criterion": "Answer includes imigrasi.go.id or official source URL.",
        "confidence": 0.85,
    },

    # ─── article_composer / curator cell ──────────────────────────
    {
        "cell": "article_composer",
        "skill_id": "article_composer:select_photo_by_time_of_day",
        "procedure": (
            "Pick morning photos for AM schedules, sunset/evening shots for PM. "
            "Check EXIF DateTimeOriginal; fall back to GARUDA tag 'morning' / "
            "'evening' when EXIF is missing."
        ),
        "precondition": "Composer has a time-slot schedule + GARUDA photo pool.",
        "success_criterion": "No sunset photo posted at 07:00 and vice-versa.",
        "confidence": 0.75,
    },
    {
        "cell": "article_composer",
        "skill_id": "article_composer:caption_length_cap",
        "procedure": (
            "Instagram: cap caption at 2200 chars, hashtags at 30. WhatsApp "
            "status: cap at 700. Truncate at sentence boundary, never mid-word."
        ),
        "precondition": "Composed caption ready for channel dispatch.",
        "success_criterion": "Publish API never 422s on length.",
        "confidence": 0.9,
    },

    # ─── routing / intent classifier ──────────────────────────────
    {
        "cell": "routing",
        "skill_id": "routing:skip_rag_for_pricing_intent",
        "procedure": (
            "If intent classifier flags any of the 17 pricing keywords, set "
            "skip_rag=True AND trusted_tools_used=True when PricingTool ran. "
            "Bypasses the ABSTAIN gate for cost questions answered by the tool."
        ),
        "precondition": "Intent classifier has tagged the user query.",
        "success_criterion": "Pricing answers with Rp/IDR/USD don't trigger ABSTAIN.",
        "confidence": 0.85,
    },
    {
        "cell": "routing",
        "skill_id": "routing:language_protocol",
        "procedure": (
            "Respond in the language of the user's last message. Zero "
            "(antonellosiano@) gets Italian regardless of query language. "
            "Never mix languages in a single response."
        ),
        "precondition": "Channel dispatcher is about to send outbound.",
        "success_criterion": "Language matches user expectation 100% on sample review.",
        "confidence": 0.9,
    },

    # ─── knowledge_graph cell ─────────────────────────────────────
    {
        "cell": "knowledge_graph",
        "skill_id": "knowledge_graph:subgraph_then_global",
        "procedure": (
            "Try domain subgraph first (Company / Visa / Property / Tax). Only "
            "fall back to global 242k-edge graph when the subgraph returns "
            "zero matches — global is 10x slower."
        ),
        "precondition": "KG query has a classifiable domain.",
        "success_criterion": "p99 KG latency < 400ms on subgraph hit.",
        "confidence": 0.8,
    },

    # ─── llm / orchestration cell ─────────────────────────────────
    {
        "cell": "llm_clients",
        "skill_id": "llm_clients:ollama_qwen_think_false",
        "procedure": (
            "For Qwen 3.5 via Ollama, always send think=False. The model emits "
            "<think>...</think> otherwise, which breaks downstream JSON parsing."
        ),
        "precondition": "Calling ollama_client on Qwen 3.5 family.",
        "success_criterion": "No <think> tokens leak into final_answer.",
        "confidence": 0.9,
    },
    {
        "cell": "llm_clients",
        "skill_id": "llm_clients:persistent_httpx_client",
        "procedure": (
            "Use a module-level httpx.AsyncClient with lifespan-scoped close. "
            "Never `httpx.AsyncClient()` in a method or loop — that leaks "
            "connections and breaks the connection pool on Fly.io."
        ),
        "precondition": "Any outbound HTTP call from backend-rag.",
        "success_criterion": "open_fds count stable under load.",
        "confidence": 0.85,
    },

    # ─── prompts / zantara_core ───────────────────────────────────
    {
        "cell": "prompts",
        "skill_id": "prompts:single_source_of_truth",
        "procedure": (
            "Edit zantara_core.py ONLY. All consumers (channels, routers, "
            "services) import from there. Never copy a prompt section into "
            "an ad-hoc string."
        ),
        "precondition": "About to modify any prompt text used by Zantara.",
        "success_criterion": "grep -r 'SECURITY_BOUNDARY' returns only zantara_core.py as SSoT.",
        "confidence": 0.9,
    },

    # ─── auth / security cell ─────────────────────────────────────
    {
        "cell": "security",
        "skill_id": "security:bridge_exempt_from_jwt",
        "procedure": (
            "Exempt /api/bridge/* from hybrid_auth JWT enforcement. The bridge "
            "is called by OpenClaw loopback (18789) with its own HMAC; JWT on "
            "top breaks internal dispatch."
        ),
        "precondition": "Editing middleware/hybrid_auth allowlist.",
        "success_criterion": "OpenClaw → backend-rag bridge calls succeed with 200.",
        "confidence": 0.85,
    },

    # ─── database / migration cell ────────────────────────────────
    {
        "cell": "database",
        "skill_id": "database:verify_unique_before_upsert",
        "procedure": (
            "Before ON CONFLICT (col) DO ..., query pg_constraint to confirm "
            "the UNIQUE on `col`. Docstrings lie (see lkpm_client_config: "
            "docstring said UNIQUE(client_id), reality was UNIQUE(client_id, "
            "company_id))."
        ),
        "precondition": "Writing any ON CONFLICT clause touching CRM or LKPM.",
        "success_criterion": "Transaction never aborts with 'no unique constraint matching'.",
        "confidence": 0.9,
    },
    {
        "cell": "database",
        "skill_id": "database:wal_mode_sqlite",
        "procedure": (
            "Every SQLite connection in this repo: PRAGMA journal_mode=WAL + "
            "busy_timeout=5000 + foreign_keys=ON. Required for the Genome's "
            "concurrent read-write pattern."
        ),
        "precondition": "Opening a new sqlite3.Connection.",
        "success_criterion": "No 'database is locked' errors under 10-thread stress test.",
        "confidence": 0.95,
    },

    # ─── drive / integrations cell ────────────────────────────────
    {
        "cell": "integrations",
        "skill_id": "integrations:drive_page_token_never_on_fly",
        "procedure": (
            "Drive polling runs ONLY on Pro or Air cron (every 5min). NEVER on "
            "Fly.io — auto_stop loses the page_token and triggers a full "
            "re-scan, flooding the event bus."
        ),
        "precondition": "Scheduling a Drive poll job.",
        "success_criterion": "page_token in system_settings is monotonically advancing.",
        "confidence": 0.95,
    },
    {
        "cell": "integrations",
        "skill_id": "integrations:sheets_service_account_only",
        "procedure": (
            "Google Sheets auth: direct Service Account with spreadsheets + "
            "drive.readonly scopes. NO Domain-Wide Delegation (caused prod "
            "timeouts). Share sheets with SA email as Editor."
        ),
        "precondition": "Setting up a new sheets_service integration.",
        "success_criterion": "Cold boot reads sheet under 2s.",
        "confidence": 0.9,
    },

    # ─── caching cell ─────────────────────────────────────────────
    {
        "cell": "caching",
        "skill_id": "caching:namespace_pattern",
        "procedure": (
            "Cache keys use 'zantara:<namespace>:<id>' prefix. Invalidation "
            "patterns use wildcards like 'zantara:crm_clients_stats:*'. Never "
            "FLUSHDB — other services share Redis."
        ),
        "precondition": "Writing cache read/invalidate code.",
        "success_criterion": "Cache invalidation affects only owning namespace.",
        "confidence": 0.85,
    },

    # ─── federation / mata-garuda cell ────────────────────────────
    {
        "cell": "mata_garuda",
        "skill_id": "mata_garuda:escalation_file_air_to_pro",
        "procedure": (
            "Air writes findings to shared/escalations.json (pending array). "
            "Pro reads at session start and handles before other work. Never "
            "auto-resolve on Air side — Zero is the final instance."
        ),
        "precondition": "Agent on Air discovers a cross-machine issue.",
        "success_criterion": "Escalation reaches Pro within next session start.",
        "confidence": 0.85,
    },

    # ─── test / guardian cell ─────────────────────────────────────
    {
        "cell": "guardian",
        "skill_id": "guardian:dependencies_import_chain_check",
        "procedure": (
            "Before every Fly.io deploy run: python -c 'from backend.app."
            "dependencies import get_current_user'. Rogue AI refactors strip "
            "`Any` from typing imports and crash the whole app on boot."
        ),
        "precondition": "Pre-deploy checklist for nuzantara-rag.",
        "success_criterion": "Import succeeds; deploy proceeds.",
        "confidence": 0.95,
    },
]


def apply_seed(seeds: list[dict[str, Any]], genome) -> dict[str, int]:
    """Write each seed into the supplied Genome. Returns insert/update/skip counts."""
    counts = {"inserted": 0, "updated": 0, "skipped": 0}
    for s in seeds:
        try:
            action = genome.record_skill(
                cell=s["cell"],
                skill_id=s["skill_id"],
                procedure=s["procedure"],
                precondition=s["precondition"],
                success_criterion=s["success_criterion"],
                confidence=s.get("confidence", 0.6),
                scope=s.get("scope", "Project"),
                domain=s.get("domain", "generic"),
            )
            counts[action] += 1
        except Exception as exc:
            logger.warning("skip %s: %s", s.get("skill_id", "?"), exc)
            counts["skipped"] += 1
    return counts


def _default_db_path() -> str:
    return os.environ.get(
        "EXPERIENCE_DB_PATH",
        os.path.expanduser("~/.nuzantara/experience.db"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--db-path", default=_default_db_path(),
        help="Genome SQLite path (default: $EXPERIENCE_DB_PATH or ~/.nuzantara/experience.db).",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually write the seed (default: dry-run).",
    )
    args = parser.parse_args(argv)

    report = {
        "count": len(SEED_SKILLS),
        "by_cell": {},
        "by_confidence": {"low": 0, "mid": 0, "high": 0},
    }
    for s in SEED_SKILLS:
        report["by_cell"][s["cell"]] = report["by_cell"].get(s["cell"], 0) + 1
        c = s.get("confidence", 0.6)
        if c < 0.75:
            report["by_confidence"]["low"] += 1
        elif c < 0.9:
            report["by_confidence"]["mid"] += 1
        else:
            report["by_confidence"]["high"] += 1

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if not args.apply:
        logger.info("dry-run complete. Re-run with --apply to write into %s.", args.db_path)
        return 0

    try:
        from cell_core.genome import Genome
    except ImportError as exc:  # pragma: no cover
        logger.error("cell_core not importable (%s); cannot apply.", exc)
        return 1

    os.makedirs(os.path.dirname(args.db_path) or ".", exist_ok=True)
    genome = Genome(db_path=args.db_path)
    counts = apply_seed(SEED_SKILLS, genome=genome)
    print(json.dumps({"apply": counts}, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
