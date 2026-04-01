"""
KBLI Audit Patcher — Parses 50 audit .md files and patches kbli-gold-all.json.

Reads audit intelligence from /Users/nuzantara/Desktop/correzioni kbli navigator/
Outputs patched gold content to apps/mouth/data/kbli-gold-all.json

Rules:
- Append-only for existing gold entries (never replace editorial content)
- Correct "May 31" dates to "June 18, 2026"
- Map old KBLI codes to their 2025 equivalents
- Never touch KBLI_2025_FINAL_CLEAN.json or per_skala data
"""

import json
import re
import os
import sys
from pathlib import Path
from typing import Any

# ─── Paths ───────────────────────────────────────────────────────────────────

AUDIT_DIR = Path("/Users/nuzantara/Desktop/correzioni kbli navigator")
GOLD_PATH = Path("apps/mouth/data/kbli-gold-all.json")
MAIN_JSON = Path("apps/mouth/data/KBLI_2025_FINAL_CLEAN.json")
BACKUP_PATH = Path("apps/mouth/data/kbli-gold-all.json.bak")

# ─── Old → New code mapping (KBLI 2020 → 2025) ─────────────────────────────

CODE_MAP: dict[str, str] = {
    "55193": "55203",  # Villa
    "10792": "10761",  # Coffee (now wet pastries → coffee processing)
    "68112": "68292",  # Real estate management
}

# ─── Valid KBLI 2025 codes (loaded at runtime) ──────────────────────────────

VALID_CODES: set[str] = set()


def load_valid_codes() -> set[str]:
    """Load all valid KBLI 2025 codes from main JSON."""
    with open(MAIN_JSON) as f:
        data = json.load(f)
    return {r["kode_kbli_2025"] for r in data["data"]}


def fix_dates(text: str) -> str:
    """Correct all wrong deadline dates."""
    # May 31 variants → June 18, 2026
    text = re.sub(r"May\s*31,?\s*2026", "June 18, 2026", text)
    text = re.sub(r"31\s*(?:Maggio|May)\s*2026", "June 18, 2026", text)
    text = re.sub(r"31/05/2026", "18/06/2026", text)
    return text


def extract_codes_from_filename(filename: str) -> list[str]:
    """Extract KBLI codes from audit filename patterns."""
    # Remove prefix/suffix
    name = filename.replace("KBLI_", "").replace("_Audit_Notes.md", "")
    # Remove descriptive suffixes like _Bakery, _Coffee, _Furniture, etc.
    name = re.sub(r"_[A-Z][a-z]+.*$", "", name)

    codes: list[str] = []
    # Split on _ to handle multi-code files like 68111_68292
    parts = name.split("_")
    for part in parts:
        # Handle xxx patterns like 46xxx, 66xxx — skip these (not specific codes)
        if "xxx" in part.lower():
            continue
        # Handle range patterns like 38211_39xxx
        if re.match(r"^\d{5}$", part):
            codes.append(part)
    return codes


def map_code(code: str) -> str:
    """Map old KBLI code to 2025 equivalent if needed."""
    return CODE_MAP.get(code, code)


def parse_audit_file(filepath: Path) -> dict[str, Any]:
    """Parse a single audit .md file into structured intelligence."""
    content = filepath.read_text(encoding="utf-8")
    content = fix_dates(content)

    filename = filepath.name
    raw_codes = extract_codes_from_filename(filename)
    target_codes = [map_code(c) for c in raw_codes]

    # Extract the full file as intelligence context
    sections: dict[str, str] = {}

    # Extract REGULATORY DELTA section
    delta_match = re.search(
        r"(?:REGULATORY DELTA|CRITICAL CORRECTIONS|STATUS & ADVANTAGES|"
        r"EDUCATION VS SERVICE|THE 2025 MANAGEMENT SPLIT|"
        r"THE \"LARGE QUALIFICATION\"|ENVIRONMENTAL COMPLIANCE|"
        r"CODE REFINEMENT|MANDATORY LICENSING|"
        r"NEW KBLI CODE|SINGLE ENTITY MANAGEMENT)(.*?)(?=\n## |\n---\s*\n## |\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if delta_match:
        sections["regulatory_delta"] = delta_match.group(0).strip()

    # Extract CALIBRATED REQUIREMENTS section
    cal_match = re.search(
        r"(?:CALIBRATED REQUIREMENTS|INTELLIGENCE INSIGHTS|LIMITATIONS|"
        r"VISA UTILITY|2026 COMPLIANCE|LICENSING)(.*?)(?=\n## |\n---\s*\n## |\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if cal_match:
        sections["requirements"] = cal_match.group(0).strip()

    # Extract AUDIT CHECKLIST items
    checklist_items: list[str] = []
    for match in re.finditer(r"\d+\.\s*\[\s*\]\s*(.+)", content):
        item = match.group(1).strip()
        item = fix_dates(item)
        checklist_items.append(item)

    # Extract all bullet points with concrete info
    warnings: list[str] = []
    for match in re.finditer(r"(?:^|\n)\s*-\s*\*\*(.+?)\*\*:?\s*(.+?)(?:\n|$)", content):
        key = match.group(1).strip()
        val = match.group(2).strip()
        if any(kw in key.lower() for kw in [
            "action", "warning", "critical", "risk", "deadline",
            "mandatory", "prohibited", "required", "paid-up",
            "zoning", "capital", "halal", "pse",
        ]):
            warnings.append(f"{key}: {val}")

    return {
        "filename": filename,
        "raw_codes": raw_codes,
        "target_codes": target_codes,
        "sections": sections,
        "checklist": checklist_items,
        "warnings": warnings,
        "full_content": content,
    }


def build_warning_block(audit: dict[str, Any]) -> str:
    """Build a warning text block from audit intelligence for whatYouNeed."""
    lines: list[str] = []
    content = audit["full_content"]

    # Capital locking rule
    if re.search(r"capital lock", content, re.IGNORECASE):
        lines.append(
            "**⚠️ Capital Lock-in (BKPM 5/2025, Art. 27):** The IDR 2.5 Billion paid-up capital "
            "cannot be withdrawn for **12 months** from deposit date. Only legitimate operational "
            "costs (salaries, rent, assets) are permitted. This is a primary DJP audit trigger in 2026."
        )

    # Perda 4/2026 nominee
    if re.search(r"Perda.*4/2026|nominee.*criminal|nominee.*penal", content, re.IGNORECASE):
        lines.append(
            "**⚠️ Perda No. 4/2026 — Nominee Ban:** Using a local nominee to hold property or "
            "operate a business in Bali is now a **criminal offense** punishable by up to 5 years "
            "imprisonment and IDR 1 billion fine. All structures must use legitimate PT PMA or Hak Pakai."
        )

    # Halal certification
    if re.search(r"halal", content, re.IGNORECASE):
        lines.append(
            "**⚠️ Halal Certification:** Mandatory for all F&B operations. Large-scale PT PMA "
            "compliance was required by 2024. Imported food items deadline: **October 17, 2026**."
        )

    # PSE Kominfo
    if re.search(r"PSE|Kominfo", content, re.IGNORECASE):
        lines.append(
            "**⚠️ PSE Registration (Kominfo):** Mandatory for any PT PMA operating a commercial "
            "website, app, or online platform. Without PSE, payment gateway providers will block operations."
        )

    # OTA/NIB verification (word boundary on OTA to avoid matching "total", "nota" etc.)
    if re.search(r"\bOTA\b|Airbnb|Booking\.com|Verified NIB", content):
        lines.append(
            "**⚠️ OTA Compliance (March 31, 2026):** All accommodation properties on Airbnb/Booking.com "
            "must have a **Verified NIB** (requires SLF — Building Certificate). Unverified listings "
            "face immediate delisting from global platforms."
        )

    # AMDAL/Environmental
    if re.search(r"AMDAL|coastal.*setback|environmental impact", content, re.IGNORECASE):
        lines.append(
            "**⚠️ Environmental Compliance (AMDAL):** Proximity to the coastal buffer zone (Sempadan Pantai) "
            "mandates a full Environmental Impact Assessment under PP 22/2021. Mandatory 100-meter setback "
            "from high-water mark, enforced via satellite/drone audits."
        )

    # KSO / Local partner
    if re.search(r"KSO|joint operation|local.*partner", content, re.IGNORECASE):
        lines.append(
            "**⚠️ Mandatory Local Partnership (KSO):** PT PMA in construction must form a Joint Operation "
            "(KSO) with a local Indonesian construction firm. Physical office required — no virtual office."
        )

    # SBU/BUJK Construction
    if re.search(r"SBU.*BUJK|construction license", content, re.IGNORECASE):
        lines.append(
            "**⚠️ SBU & BUJK Required:** Business Entity Certificate (SBU) and Construction License "
            "(BUJK) are mandatory. Requires demonstrated past project experience and significant net worth."
        )

    # POS integration
    if re.search(r"POS.*integration|PBJT", content, re.IGNORECASE):
        lines.append(
            "**⚠️ POS Integration & PBJT:** Restaurant tax (PBJT) is 10%. Regional governments "
            "(Badung/Denpasar) monitor POS data in real-time — discrepancies trigger automated audits."
        )

    # Holding company limitation
    if re.search(r"PROHIBITED.*commercial|cannot invoice", content, re.IGNORECASE):
        lines.append(
            "**⚠️ Operational Limitation:** A holding company (64210) is **prohibited** from direct "
            "commercial operations — it cannot invoice for services. Must operate through subsidiaries."
        )

    # Alcohol license
    if re.search(r"alcohol.*KBLI|SIUP-MB", content, re.IGNORECASE):
        lines.append(
            "**⚠️ Alcohol License:** Serving alcohol requires a separate KBLI 56301 + SIUP-MB "
            "(Alcoholic Beverage Trade License). This applies to restaurants, beach clubs, and bars."
        )

    # Zoning restrictions
    if re.search(r"PINK.*zone|tourism.*zone|strictly.*pink", content, re.IGNORECASE):
        lines.append(
            "**⚠️ Zoning Restriction:** PT PMA operations must be in a **Pink (Tourism) Zone**. "
            "Confirm zoning designation before land lease or purchase — no exceptions for residential areas."
        )

    # Data protection (UU PDP)
    if re.search(r"UU PDP|Data Protection", content, re.IGNORECASE):
        lines.append(
            "**⚠️ Data Protection (UU PDP):** Data protection compliance is mandatory. Localized data "
            "security protocols and explicit user consent management required. Consider appointing a DPO."
        )

    # BPOM
    if re.search(r"BPOM", content, re.IGNORECASE):
        lines.append(
            "**⚠️ BPOM Registration:** Processed food products require a BPOM MD (Distribution License) "
            "for domestic retail distribution. Mandatory for all manufacturing-scale operations."
        )

    return "\n\n".join(lines)


def build_bali_context_block(audit: dict[str, Any]) -> str:
    """Build additional baliContext intelligence from audit."""
    lines: list[str] = []
    content = audit["full_content"]

    # Code migration warning
    for raw, target in zip(audit["raw_codes"], audit["target_codes"]):
        if raw != target:
            lines.append(
                f"**KBLI 2025 Migration:** This code was renumbered from {raw} (KBLI 2020) to "
                f"{target} (KBLI 2025). All businesses must migrate by **June 18, 2026** "
                f"(BPS Reg. 7/2025). Using the old code after this date will result in NIB suspension."
            )

    # Tax exemption for IT
    if re.search(r"tax exemption|PMK 18/2021|territorial tax", content, re.IGNORECASE):
        lines.append(
            "**Tax Optimization (2026):** This KBLI maps to \"Digital Economy\" expertise, making it "
            "the strongest classification for claiming the **4-year Territorial Tax Exemption** (PMK 18/2021). "
            "Pair with RPTKA for \"Software Architect\" or \"AI Specialist\" work permits."
        )

    # Capital update
    if re.search(r"2\.5\s*Billion|2,5\s*Miliard|IDR\s*2\.5B", content, re.IGNORECASE):
        lines.append(
            "**2026 Capital Update (BKPM 5/2025):** Paid-up capital reduced to **IDR 2.5 Billion** "
            "(~USD 150K). Total investment must still exceed IDR 10 Billion, but land and building "
            "values now count toward this threshold — a game-changer for Bali-based PT PMAs."
        )

    return "\n\n".join(lines)


def build_what_changed_block(audit: dict[str, Any]) -> str:
    """Build additional whatChanged text from audit."""
    lines: list[str] = []
    content = audit["full_content"]

    # Code migration
    for raw, target in zip(audit["raw_codes"], audit["target_codes"]):
        if raw != target:
            lines.append(
                f"**2025 Update:** Code renumbered from {raw} to {target}. "
                f"Migrate by June 18, 2026 to avoid NIB suspension."
            )

    # New split codes
    if re.search(r"MANAGEMENT SPLIT|code split", content, re.IGNORECASE):
        lines.append(
            "**2025 Code Split:** Development and management activities are now separated "
            "into distinct KBLI codes. Check which code matches your actual business activity."
        )

    # New capital rules
    if re.search(r"capital lock|BKPM.*5/2025", content, re.IGNORECASE):
        lines.append(
            "**BKPM 5/2025 Reform:** Paid-up capital reduced to IDR 2.5B (from 10B). "
            "New 12-month capital lock-in rule applies (Art. 27)."
        )

    return "\n\n".join(lines)


def build_new_gold_entry(audit: dict[str, Any], code: str, main_data: dict[str, Any]) -> dict[str, str]:
    """Create a new gold entry for a code that doesn't have one yet."""
    # Try to get intel_2026 from main JSON as base
    code_data = main_data.get(code, {})
    intel = code_data.get("intel_2026", {}) or {}

    content = audit["full_content"]
    title = code_data.get("judul", "").title() if code_data else ""

    # Build whatItMeans from regulatory delta or use intel_2026
    what_it_means = intel.get("whatItMeans", "")
    if not what_it_means:
        # Extract from first section of audit
        desc = code_data.get("uraian", "")
        if desc:
            what_it_means = desc[:500]
        else:
            what_it_means = f"Business activity classified under KBLI {code}. See full regulatory details below."

    # Build whatYouNeed
    what_you_need = intel.get("whatYouNeed", "")
    warnings = build_warning_block(audit)
    if what_you_need and warnings:
        what_you_need = f"{what_you_need}\n\n---\n\n### ⚠️ 2026 Regulatory Updates\n\n{warnings}"
    elif warnings:
        what_you_need = f"### ⚠️ 2026 Regulatory Updates\n\n{warnings}"

    # Build whatChanged
    what_changed = intel.get("whatChanged", "")
    changed_block = build_what_changed_block(audit)
    if what_changed and changed_block:
        what_changed = f"{what_changed}\n\n{changed_block}"
    elif changed_block:
        what_changed = changed_block

    # Build baliContext
    bali_context = intel.get("baliContext", "")
    bali_block = build_bali_context_block(audit)
    if bali_context and bali_block:
        bali_context = f"{bali_context}\n\n---\n\n{bali_block}"
    elif bali_block:
        bali_context = bali_block

    # youllAlsoNeed — extract from checklist or intel
    youll_also_need = intel.get("youllAlsoNeed", "")
    if not youll_also_need:
        # Look for related code suggestions in audit
        related_matches = re.findall(r"KBLI\s+(\d{5})", content)
        related = [c for c in set(related_matches) if c != code][:5]
        if related:
            youll_also_need = "\n".join(f"- **{c}** — Related business activity" for c in related)

    # zantaraOpener
    zantara_opener = intel.get("zantaraOpener", "")
    if not zantara_opener:
        zantara_opener = (
            f"Looking at KBLI {code}? Let me walk you through the 2025 requirements, "
            f"PMA rules, and what changed for foreign investors in Bali."
        )

    return {
        "whatItMeans": what_it_means,
        "whatYouNeed": what_you_need,
        "whatChanged": what_changed or f"Updated for KBLI 2025 catalog. Check migration requirements.",
        "baliContext": bali_context or "Contact Bali Zero for location-specific advice on this business activity in Bali.",
        "youllAlsoNeed": youll_also_need or "Contact Bali Zero for complementary KBLI code recommendations.",
        "zantaraOpener": zantara_opener,
    }


def patch_existing_gold(gold_entry: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    """Patch an existing gold entry by appending audit intelligence."""
    patched = {**gold_entry}

    # Append warnings to whatYouNeed
    warnings = build_warning_block(audit)
    if warnings:
        current = patched.get("whatYouNeed", "")
        # Check if we already appended (idempotency)
        if "2026 Regulatory Updates" not in current:
            patched["whatYouNeed"] = f"{current}\n\n---\n\n### ⚠️ 2026 Regulatory Updates\n\n{warnings}"

    # Append to whatChanged
    changed = build_what_changed_block(audit)
    if changed:
        current = patched.get("whatChanged", "")
        if "BKPM 5/2025 Reform" not in current and "2025 Update" not in current:
            patched["whatChanged"] = f"{current}\n\n{changed}"

    # Append to baliContext
    bali = build_bali_context_block(audit)
    if bali:
        current = patched.get("baliContext", "")
        if "2026 Capital Update" not in current and "KBLI 2025 Migration" not in current:
            patched["baliContext"] = f"{current}\n\n---\n\n{bali}"

    return patched


def main() -> None:
    global VALID_CODES

    # Load valid codes
    VALID_CODES = load_valid_codes()
    print(f"Loaded {len(VALID_CODES)} valid KBLI 2025 codes")

    # Load main JSON for intel_2026 fallback
    with open(MAIN_JSON) as f:
        main_json = json.load(f)
    main_data = {r["kode_kbli_2025"]: r for r in main_json["data"]}

    # Load current gold content
    with open(GOLD_PATH) as f:
        gold = json.load(f)
    print(f"Loaded {len(gold)} existing gold entries")

    # Backup
    with open(BACKUP_PATH, "w") as f:
        json.dump(gold, f, indent=2, ensure_ascii=False)
    print(f"Backup saved to {BACKUP_PATH}")

    # Parse all audit files
    audit_files = sorted(AUDIT_DIR.glob("KBLI_*.md"))
    print(f"\nProcessing {len(audit_files)} audit files...")

    stats = {"patched": 0, "created": 0, "skipped": 0, "unmapped": []}

    for filepath in audit_files:
        audit = parse_audit_file(filepath)

        for code in audit["target_codes"]:
            if code not in VALID_CODES:
                stats["unmapped"].append(f"{audit['filename']}: {code}")
                stats["skipped"] += 1
                continue

            if code in gold:
                # Patch existing entry
                gold[code] = patch_existing_gold(gold[code], audit)
                stats["patched"] += 1
                print(f"  ✏️  Patched: {code} ({audit['filename']})")
            else:
                # Create new entry
                gold[code] = build_new_gold_entry(audit, code, main_data)
                stats["created"] += 1
                print(f"  ✨ Created: {code} ({audit['filename']})")

    # Write patched gold content
    with open(GOLD_PATH, "w") as f:
        json.dump(gold, f, indent=2, ensure_ascii=False)

    # Summary
    print(f"\n{'='*60}")
    print(f"AUDIT PATCH COMPLETE")
    print(f"{'='*60}")
    print(f"  Patched existing: {stats['patched']}")
    print(f"  Created new:      {stats['created']}")
    print(f"  Skipped:          {stats['skipped']}")
    if stats["unmapped"]:
        print(f"\n  ⚠️  Unmapped codes:")
        for item in stats["unmapped"]:
            print(f"    - {item}")
    print(f"\n  Output: {GOLD_PATH}")
    print(f"  Backup: {BACKUP_PATH}")

    # Verify no wrong dates
    gold_text = json.dumps(gold)
    may31_count = len(re.findall(r"May\s*31", gold_text))
    if may31_count > 0:
        print(f"\n  ❌ WARNING: Found {may31_count} 'May 31' occurrences — fix needed!")
        sys.exit(1)
    else:
        print(f"\n  ✅ No 'May 31' dates found — all corrected to June 18, 2026")

    # Verify JSON valid
    with open(GOLD_PATH) as f:
        json.load(f)
    print(f"  ✅ JSON is valid")

    # Count total gold entries
    print(f"  📊 Total gold entries: {len(gold)}")


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent.parent)
    main()
