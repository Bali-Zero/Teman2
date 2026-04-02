#!/usr/bin/env python3
"""Phase 2: Validate generated content against source JSON using Gemma3:12b.
Cross-checks: risk levels, PMA status, hallucinated numbers.
"""
import json
import re

OLLAMA_URL = "http://localhost:11434"
GEMMA_MODEL = "gemma3:12b"

# Known capital amounts that are correct (whitelist)
VALID_CAPITAL_AMOUNTS = {
    "2.5 Billion", "2,5 Miliardi", "2.5B", "Rp 2.5B", "IDR 2.5B",
    "10 Billion", "10B", "IDR 10B", "Rp 10B",
    "25 Billion", "25B",  # OJK Manajer Investasi
    "50 Billion", "50B",  # Construction SBU
}


def validate_pma_consistency(generated: dict, source: dict) -> list[str]:
    """Check that generated content doesn't contradict PMA status."""
    errors = []
    pma_status = source.get("pma_status", "")
    content_text = " ".join(str(v) for v in generated.values())

    if pma_status == "TERTUTUP" and "100% foreign" in content_text.lower():
        errors.append(f"PMA CONTRADICTION: Source says TERTUTUP but content mentions 100% foreign ownership")
    if pma_status == "TERBUKA" and "closed to foreign" in content_text.lower():
        errors.append(f"PMA CONTRADICTION: Source says TERBUKA but content says closed to foreign")

    return errors


def validate_risk_consistency(generated: dict, source: dict) -> list[str]:
    """Check that risk levels mentioned match per_skala data."""
    errors = []
    per_skala = source.get("per_skala", [])
    content_text = " ".join(str(v) for v in generated.values()).lower()

    valid_risks = {s.get("kategori_risiko", "").lower() for s in per_skala}
    valid_risks_en = set()
    for r in valid_risks:
        if "rendah" in r and "menengah" not in r:
            valid_risks_en.add("low risk")
        elif "menengah rendah" in r:
            valid_risks_en.add("medium-low")
        elif "menengah tinggi" in r:
            valid_risks_en.add("medium-high")
        elif "tinggi" in r and "menengah" not in r:
            valid_risks_en.add("high risk")

    # Check for contradictions (only if per_skala has data)
    if valid_risks_en and per_skala:
        if "high risk" in content_text and "high risk" not in valid_risks_en and "high" not in " ".join(valid_risks):
            errors.append(f"RISK MISMATCH: Content says 'high risk' but source has {valid_risks}")
        if "low risk" in content_text and "low risk" not in valid_risks_en and "rendah" not in " ".join(valid_risks):
            if "menengah rendah" not in " ".join(valid_risks):  # medium-low contains "low"
                errors.append(f"RISK MISMATCH: Content says 'low risk' but source has {valid_risks}")

    return errors


def validate_no_hallucinated_numbers(generated: dict) -> list[str]:
    """Check for suspicious invented numbers (capital amounts, percentages, fees)."""
    errors = []
    content_text = " ".join(str(v) for v in generated.values())

    # Check for IDR amounts that aren't in the whitelist
    idr_pattern = r"IDR\s+[\d,.]+\s*(?:Billion|Million|Trillion|B|M|T)"
    matches = re.findall(idr_pattern, content_text, re.IGNORECASE)
    for m in matches:
        if not any(valid in m for valid in VALID_CAPITAL_AMOUNTS):
            errors.append(f"SUSPICIOUS AMOUNT: '{m}' — verify against source data")

    return errors


def validate_entry(generated: dict, source: dict) -> list[str]:
    """Run all validation checks on a single generated entry."""
    errors = []
    errors.extend(validate_pma_consistency(generated, source))
    errors.extend(validate_risk_consistency(generated, source))
    errors.extend(validate_no_hallucinated_numbers(generated))

    # Check required fields are non-empty
    for field in ("whatItMeans", "whatYouNeed", "whatChanged"):
        if not generated.get(field, "").strip():
            errors.append(f"EMPTY FIELD: {field} is empty or missing")

    return errors


def validate_batch(entries: dict[str, dict], source_data: dict[str, dict]) -> dict[str, list[str]]:
    """Validate all generated entries. Returns {code: [errors]} for codes with issues."""
    results = {}
    for code, content in entries.items():
        source = source_data.get(code, {})
        errors = validate_entry(content, source)
        if errors:
            results[code] = errors
    return results
