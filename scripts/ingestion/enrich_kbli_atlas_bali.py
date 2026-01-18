import json

# Paths
ATLAS_PATH = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_extraction/kbli_universal_atlas_final.json"
INGUB_PATH = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_compliance/bali_restrictions_mapping.json"


def enrich_with_bali_restrictions():
    print("🌴 ENRICHING KBLI ATLAS WITH BALI (INGUB 6) RESTRICTIONS...")

    # 1. Load Data
    atlas = json.load(open(ATLAS_PATH))
    ingub = json.load(open(INGUB_PATH))

    patterns = ingub["kbli_restrictions"]

    universe = atlas["data"]
    enriched_count = 0

    for code, record in universe.items():
        # Check against patterns
        matched = False
        restriction_note = ""

        for pat_key, pat_data in patterns.items():
            pat = pat_data["pattern"]
            if code.startswith(pat):
                matched = True
                restriction_note = pat_data.get("restriction", "RESTRICTION")
                break

        if matched:
            # Inject Enrichment
            if "regional_restrictions" not in record:
                record["regional_restrictions"] = []

            record["regional_restrictions"].append(
                {
                    "scope": "PROVINSI_BALI",
                    "source": "INGUB NO 6 TAHUN 2025",
                    "type": "MORATORIUM",
                    "status": "SUSPENDED",  # Penghantian Sementara
                    "details": f"Activity restricted under Bali Moratorium logic (Pattern {pat})",
                }
            )
            enriched_count += 1

    # Update Stats
    atlas["meta"]["Enriched_Bali_Ingub"] = enriched_count

    # Save
    with open(ATLAS_PATH, "w") as f:
        json.dump(atlas, f, indent=2)

    print("✅ Enrichment Complete.")
    print(f"🌴 Bali Restrictions Applied to: {enriched_count} Codes")
    print(f"💾 Updated: {ATLAS_PATH}")


if __name__ == "__main__":
    enrich_with_bali_restrictions()
