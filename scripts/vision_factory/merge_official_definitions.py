import json
import logging

logger = logging.getLogger(__name__)


def merge_definitions(enriched_path, official_path, output_path):
    logger.info(f"🔄 Merging definitions from {official_path} into {enriched_path}...")

    with open(enriched_path, "r", encoding="utf-8") as f:
        enriched_data = json.load(f)

    records = enriched_data.get("data", [])
    if not records:
        logger.error("❌ No records found in enriched data!")
        return

    try:
        with open(official_path, "r", encoding="utf-8") as f:
            official_defs = json.load(f)
    except FileNotFoundError:
        logger.error(
            f"❌ Official definitions file not found at {official_path}. Extraction might have failed or is still running."
        )
        return

    # Create lookup dict for official definitions
    official_map = {item["kode"]: item for item in official_defs.values()}

    updated_count = 0

    for rec in records:
        code = rec.get("kode")
        if code in official_map:
            official_rec = official_map[code]

            # Update Uraian if available and longer/better?
            # User wants authoritative definitions, so we overwrite.
            if official_rec.get("uraian"):
                original_uraian = rec.get("uraian", "")
                rec["uraian"] = official_rec["uraian"]

                # Check formatting: ensure no excessive newlines
                rec["uraian"] = " ".join(rec["uraian"].split())  # Normalize whitespace

                # Update Title if needed, or keep original? Official title is probably safer.
                if official_rec.get("judul"):
                    rec["judul"] = official_rec["judul"].strip()

                # Add metadata source
                if "metadata_sumber" not in rec:
                    rec["metadata_sumber"] = {}

                rec["metadata_sumber"]["sumber_definisi"] = (
                    "Perban BPS No. 7 Tahun 2025"
                )
                rec["metadata_sumber"]["definisi_original"] = (
                    "Replaced with Official Definition"
                )

                updated_count += 1

    enriched_data["data"] = records
    enriched_data["schema_version"] = "Masterpiece V5 + Official Definitions"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(enriched_data, f, indent=2, ensure_ascii=False)

    logger.info(
        f"✅ Merged {updated_count} official definitions. Saved to {output_path}"
    )


if __name__ == "__main__":
    enriched_file = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_extraction/kbli_lampiran_ig_enriched_platinum.json"
    official_file = "/Users/antonellosiano/Desktop/nuzantara/source_documents/official_kbli_definitions.json"
    output_file = "/Users/antonellosiano/Desktop/nuzantara/reports/kbli_extraction/kbli_platinum_with_official_definitions.json"

    merge_definitions(enriched_file, official_file, output_file)
