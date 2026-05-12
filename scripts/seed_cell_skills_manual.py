#!/usr/bin/env python3
"""Seed cell:skills Redis stream with 15-20 hand-crafted StructuralPattern skills.

Phase 2.5 SYMBIOSIS organism completion. Per 4-panel review:
- Option A (extract from observatory.db) was REMOVED (architecturally polluting)
- Only Option B: hand-curated high-signal skills with strict schema

Each skill follows the canonical StructuralPattern shape from
apps/bali-intel-scraper/backend/cell/hgt_publisher.py:

  {
    "skill_id": str,           # namespaced: <cell>.<domain>.<pattern_id>
    "procedure": str,          # plain-English what the pattern says
    "precondition": str,       # when this pattern applies
    "success_criterion": str,  # how to know the pattern still holds
    "confidence": float,       # 0.0-1.0 (HGT publisher threshold 0.7)
    "scope": "Project",        # germline (transferable)
    "domain": str,             # 11 canonical domains per hgt/domains.py
    "cell_origin": str,        # provenance
    "seeded_at": iso8601,      # this seed run
    "seed_source": "manual_v1" # for future filtering
  }

Reference: docs/superpowers/specs/2026-05-12-phase2-core-plumbing-fix-spec.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as redis_async  # type: ignore

logger = logging.getLogger("seed_cell_skills_manual")

# 15-20 hand-crafted skills covering: tax, visa, property, CRM, KBLI, intel, observability
SEED_SKILLS: list[dict[str, Any]] = [
    # === TAX (4 skills) ===
    {
        "skill_id": "intel.scraper.djp_rss_v2_stable",
        "procedure": "DJP regulatory RSS at /api/v2/news endpoint is stable; poll every 6h, expect ≥3 new items/week",
        "precondition": "regulatory monitoring of Indonesian tax authority needed",
        "success_criterion": "≥3 new regulations harvested per 7-day window from pajak.go.id",
        "confidence": 0.92,
        "scope": "Project", "domain": "tax", "cell_origin": "intel-scraper-cell",
    },
    {
        "skill_id": "tax.coretax.npwp_16digit_validation",
        "procedure": "Coretax NPWP enforces 16-digit format (NPWP+0 prefix for legacy 15-digit); validate before submit to avoid TER PMK 168/2023 rejection",
        "precondition": "PT PMA tax filing via Coretax post-Coretax-migration 2026-01",
        "success_criterion": "Coretax accepts NPWP without 'invalid format' rejection",
        "confidence": 0.88,
        "scope": "Project", "domain": "tax", "cell_origin": "tax-cell",
    },
    {
        "skill_id": "tax.spt_extension_pattern_2026",
        "procedure": "SPT Tahunan PPh Badan deadline extensions: when KEP issued before deadline (e.g. KEP-71/PJ/2026), automatic 30-day grace, no application needed",
        "precondition": "fiscal year-end PT PMA SPT submission near 30-Apr deadline",
        "success_criterion": "no denda + bunga PPh 29 in extension window",
        "confidence": 0.85,
        "scope": "Project", "domain": "tax", "cell_origin": "tax-cell",
    },
    {
        "skill_id": "tax.pph21_split_payroll_caveat",
        "procedure": "Split-payroll PT PMA WNA staff: deemed-employer rule means host-country employer is liable PPh 21 even if salary paid abroad",
        "precondition": "WNA on KITAS C-series working for PT PMA with home-country payroll",
        "success_criterion": "PPh 21 setor + lapor monthly in Indonesia regardless of payment origin",
        "confidence": 0.78,
        "scope": "Project", "domain": "tax", "cell_origin": "tax-cell",
    },
    # === VISA (4 skills) ===
    {
        "skill_id": "visa.kitas_c1_to_e28a_migration",
        "procedure": "Permenkumham 22/2023 renamed visa codes: B211A→C1 (visit), E33G→E28A (work). Legacy code on form = automatic rejection by 2026-Q2",
        "precondition": "any visa application 2026+",
        "success_criterion": "Imigrasi accepts form without 'invalid visa code' rejection",
        "confidence": 0.95,
        "scope": "Project", "domain": "immigration", "cell_origin": "visa-cell",
    },
    {
        "skill_id": "visa.e31_family_sponsored_requires_spouse_kitas",
        "procedure": "E31 family-sponsored KITAS requires spouse to have valid C-series KITAS; sponsor must be IMK/IMTA holder OR Indonesian citizen",
        "precondition": "WNA spouse of foreign worker wants stay permit",
        "success_criterion": "Imigrasi issues e-permit within 14 days post-submission",
        "confidence": 0.86,
        "scope": "Project", "domain": "immigration", "cell_origin": "visa-cell",
    },
    {
        "skill_id": "visa.golden_visa_min_investment_2026",
        "procedure": "Indonesia Golden Visa: USD 350k corporate investment OR USD 2.5M individual deposit (BCA/Mandiri escrow). 5-10 year stay permit. Real estate purchase NOT qualifying",
        "precondition": "high-net-worth foreign investor seeking long-term residency",
        "success_criterion": "Golden Visa issued via Direktorat Jenderal Imigrasi",
        "confidence": 0.83,
        "scope": "Project", "domain": "immigration", "cell_origin": "visa-cell",
    },
    {
        "skill_id": "visa.bali_emergency_stay_permit_halt",
        "procedure": "Imigrasi Bali halted emergency 30-day stay permit extensions Apr 2026; only standard B212 + offshore VISA available now",
        "precondition": "tourist with expiring visa seeking stay extension in Bali",
        "success_criterion": "client redirected to Singapore/KL visa run + B212 e-VOA",
        "confidence": 0.82,
        "scope": "Project", "domain": "immigration", "cell_origin": "visa-cell",
    },
    # === PROPERTY (3 skills) ===
    {
        "skill_id": "property.pbg_villa_kutuh_simbg_path",
        "procedure": "PBG submission Bali Kutuh via SIMBG requires OSS NIB + KKPR + KRK + PBG (no SLF until post-construction). Timeline 3-8 months, BATARA puntuale obbligatoria",
        "precondition": "WNA-owned PT PMA building villa in Badung Kutuh zonasi mista",
        "success_criterion": "PBG approval issued by DPMPTSP Badung",
        "confidence": 0.88,
        "scope": "Project", "domain": "property", "cell_origin": "property-cell",
    },
    {
        "skill_id": "property.nominee_arrangement_invalid_post_2026",
        "procedure": "Nominee land arrangements (Indonesian nominee holding HM for WNA beneficial owner) declared invalid by MK Konstitusi rulings; HGB/Hak Pakai are only legal WNA paths",
        "precondition": "WNA acquiring land in Indonesia",
        "success_criterion": "no nominee certificates issued; HGB/Hak Pakai over PT PMA only",
        "confidence": 0.93,
        "scope": "Project", "domain": "property", "cell_origin": "property-cell",
    },
    {
        "skill_id": "property.zonasi_check_per200m_jl_raya_tuka",
        "procedure": "Jl Raya Tuka Tibubeneng has zonasi mista changing every 200-300m; BATARA puntuale (lot-level zoning check) required before purchase, not just kecamatan-level",
        "precondition": "property due diligence in Tibubeneng / Pererenan / Canggu corridor",
        "success_criterion": "zonasi mapping confirmed parcel-by-parcel for the target lot",
        "confidence": 0.90,
        "scope": "Project", "domain": "property", "cell_origin": "property-cell",
    },
    # === CRM/CLIENT ops (3 skills) ===
    {
        "skill_id": "crm.brevo_template_bounce_threshold_segment",
        "procedure": "Brevo email templates with >15% bounce rate per segment indicate stale email list; rebuild list via WhatsApp opt-in instead of re-sending",
        "precondition": "marketing campaign segment showing high bounce metric in Brevo dashboard",
        "success_criterion": "bounce rate < 5% on re-rebuilt list within 30 days",
        "confidence": 0.81,
        "scope": "Project", "domain": "client_ops", "cell_origin": "crm-cell",
    },
    {
        "skill_id": "crm.whatsapp_cta_window_06_09_wita",
        "procedure": "WhatsApp client CTA reads/responses peak 06:00-09:00 WITA (morning prep window); afternoon sends drop 60%+ open rate",
        "precondition": "Bali Zero outbound client message scheduling",
        "success_criterion": "≥90% read-rate when sent in 06-09 WITA window",
        "confidence": 0.84,
        "scope": "Project", "domain": "client_ops", "cell_origin": "crm-cell",
    },
    {
        "skill_id": "crm.lkpm_quarterly_reminder_30days_pre",
        "procedure": "LKPM quarterly reports: BKPM allowlist enforcement strict, 30-day-pre reminder + 7-day-pre reminder reduces late-filing rate from 18% to 4%",
        "precondition": "PT PMA client with active NIB requiring LKPM quarterly compliance",
        "success_criterion": "LKPM filed before deadline ≥96% of quarters",
        "confidence": 0.86,
        "scope": "Project", "domain": "client_ops", "cell_origin": "crm-cell",
    },
    # === KBLI / Company (2 skills) ===
    {
        "skill_id": "kbli.79902_tourism_content_not_travel_agency",
        "procedure": "KBLI 79902 covers tourism attraction info / tourism content / influencer (Risk Rendah), NOT travel agency. Travel agency = KBLI 79111/79121 (Risk Menengah)",
        "precondition": "PT PMA setup with KBLI selection for digital tourism business",
        "success_criterion": "OSS issues NIB without risk-classification mismatch",
        "confidence": 0.91,
        "scope": "Project", "domain": "kbli", "cell_origin": "kbli-cell",
    },
    {
        "skill_id": "kbli.tdup_abolished_pp28_2025_risk_based",
        "procedure": "TDUP (Tanda Daftar Usaha Pariwisata) abolished by PP 5/2021. PP 28/2025 enforces risk-based regime: NIB + sertifikat standar (Risk Menengah) / izin (Risk Tinggi)",
        "precondition": "tourism business setup post-2025",
        "success_criterion": "no TDUP required; correct risk-tier certification issued",
        "confidence": 0.89,
        "scope": "Project", "domain": "kbli", "cell_origin": "kbli-cell",
    },
    # === Observability / Infra (2 skills) ===
    {
        "skill_id": "obs.flyctl_proxy_eventbus_pattern",
        "procedure": "Pro→Fly Postgres bridge via flyctl proxy 15432:5432 KeepAlive=true. EVENTBUS_DATABASE_URL=postgresql://...@localhost:15432/... in secrets.env, NEVER hardcoded in plist EnvironmentVariables",
        "precondition": "any Pro-local script needing Fly EventBus PG access",
        "success_criterion": "no plaintext password in plist; bridge reconnects within 60s of drop",
        "confidence": 0.95,
        "scope": "Project", "domain": "observability", "cell_origin": "obs-cell",
    },
    {
        "skill_id": "obs.pg_notify_8000_byte_limit_use_outbox_id",
        "procedure": "pg_notify hard cap 8000 bytes/payload. Always NOTIFY minimal stub with _outbox_id + cell_id + pulse_result.classifier_self; full payload stays in events_outbox row queryable by id",
        "precondition": "cell emitting pulse via cell_core.observatory.emit_pulse_observed()",
        "success_criterion": "no 'payload string too long' errors; collector reads full data via outbox row lookup",
        "confidence": 0.97,
        "scope": "Project", "domain": "observability", "cell_origin": "obs-cell",
    },
]


def validate_skill(s: dict[str, Any]) -> tuple[bool, str]:
    """Validate StructuralPattern shape."""
    required = ["skill_id", "procedure", "precondition", "success_criterion",
                "confidence", "scope", "domain", "cell_origin"]
    for k in required:
        if k not in s:
            return False, f"missing_{k}"
    if not isinstance(s["confidence"], (int, float)) or not (0 <= s["confidence"] <= 1):
        return False, f"confidence_invalid: {s['confidence']}"
    if s["scope"] not in ("Project", "Personal"):
        return False, f"scope_invalid: {s['scope']}"
    if not s["skill_id"]:
        return False, "skill_id_empty"
    return True, "ok"


async def main(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    # Validate all skills first
    invalid = []
    for s in SEED_SKILLS:
        ok, reason = validate_skill(s)
        if not ok:
            invalid.append((s.get("skill_id", "?"), reason))
    if invalid:
        for sid, reason in invalid:
            logger.error("invalid skill: %s — %s", sid, reason)
        return 2

    logger.info("All %d skills validate against StructuralPattern schema", len(SEED_SKILLS))

    if args.dry_run:
        logger.info("=== DRY RUN — would XADD %d skills to cell:skills ===", len(SEED_SKILLS))
        for s in SEED_SKILLS:
            logger.info("  %s (conf=%.2f, domain=%s, origin=%s)",
                        s["skill_id"], s["confidence"], s["domain"], s["cell_origin"])
        return 0

    # Connect to Redis
    redis = redis_async.from_url(args.redis_url, decode_responses=True)
    try:
        # Check current stream state
        initial_len = await redis.xlen("cell:skills")
        logger.info("cell:skills initial XLEN: %d", initial_len)

        seeded_at = datetime.now(timezone.utc).isoformat()
        seeded_ids = []
        for s in SEED_SKILLS:
            # Inject seed metadata
            entry = {**s, "seeded_at": seeded_at, "seed_source": "manual_v1"}
            # XADD requires string values
            xadd_data = {k: json.dumps(v) if not isinstance(v, str) else v
                         for k, v in entry.items()}
            stream_id = await redis.xadd("cell:skills", xadd_data)
            seeded_ids.append(stream_id)
            logger.info("XADD %s → stream_id=%s", s["skill_id"], stream_id)

        # Ensure consumer group exists (XGROUP CREATE will fail benignly if exists)
        try:
            await redis.xgroup_create("cell:skills", "sentinel-1", id="0", mkstream=False)
            logger.info("XGROUP sentinel-1 created on cell:skills")
        except Exception as exc:
            if "BUSYGROUP" in str(exc):
                logger.info("XGROUP sentinel-1 already exists")
            else:
                logger.warning("XGROUP create failed (non-blocking): %s", exc)

        final_len = await redis.xlen("cell:skills")
        logger.info(
            "=== Seed complete ===\n"
            "  initial XLEN: %d\n"
            "  seeded: %d\n"
            "  final XLEN: %d\n"
            "  consumer group: sentinel-1",
            initial_len, len(seeded_ids), final_len
        )
        return 0
    finally:
        await redis.aclose()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--redis-url", default=os.environ.get("REDIS_URL", "redis://localhost:6379"),
                   help="Redis URL (default $REDIS_URL or redis://localhost:6379)")
    p.add_argument("--dry-run", action="store_true", help="validate + list, no XADD")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sys.exit(asyncio.run(main(args)))
