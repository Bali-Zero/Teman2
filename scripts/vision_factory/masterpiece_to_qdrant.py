import json
import uuid
import sys
import os
import logging

logger = logging.getLogger(__name__)


def create_semantic_text(record: dict) -> str:
    """
    Constructs a rich semantic text representation for vector embedding.
    Prioritizes: Title, Scope, Risks, Obligations, and Legal Intelligence.
    Schema: Masterpiece V5 (Indonesian Keys)
    """
    # 1. Header (Identity)
    text_parts = [
        f"KBLI {record.get('kode', 'UNKNOWN')} - {record.get('judul', 'No Title')}",
        f"RISIKO: {record.get('kategori_resiko', 'N/A')}",
        f"SKALA: {record.get('skala_usaha', 'N/A')}",
    ]

    # 2. Scope (Core Definition)
    if record.get("uraian"):
        text_parts.append(f"URAIAN: {record['uraian']}")

    # 3. Licensing & Obligations (The "Must Haves")
    # In V5 (from Mineru), these are strings
    perizinan = record.get("perizinan_berusaha")
    if perizinan and perizinan.strip():
        text_parts.append(f"IZIN: {perizinan}")

    syarat = record.get("persyaratan")
    if syarat and syarat.strip():
        text_parts.append(f"PERSYARATAN: {syarat}")

    kewajiban = record.get("kewajiban")
    if kewajiban and kewajiban.strip():
        text_parts.append(f"KEWAJIBAN: {kewajiban}")

    # 3b. Jangka Waktu (Duration) - Requested by User
    jangka = record.get("jangka_waktu")
    if jangka and jangka.strip():
        text_parts.append(f"JANGKA WAKTU: {jangka}")

    # 4. Intelligence & Sanksi (The "Gotchas")
    # Sanksi comes from Enrichment (Dict)
    sanksi = record.get("sanksi_administratif", {})
    if sanksi and isinstance(sanksi, dict):
        sanksi_text = ", ".join([f"{k}: {v}" for k, v in sanksi.items()])
        text_parts.append(f"SANKSI: {sanksi_text}")

    # Add Legal Notices (Catatan Hukum)
    notices = record.get("catatan_hukum", [])
    if notices:
        notice_titles = [n.get("title", "") for n in notices]
        text_parts.append(f"CATATAN HUKUM: {'; '.join(notice_titles)}")

    # Add UMKU Checklists - Requested by User
    umku = record.get("checklist_umku", [])
    if umku:
        # Assuming simple list of strings or objects. Enriched schema likely lists them.
        # If objects, extract names. If strings, join them.
        # Based on enrich_masterpiece.py it's likely a list of codes or names.
        if isinstance(umku, list):
            # Try to handle if it's list of strings or dicts
            umku_texts = []
            for u in umku:
                if isinstance(u, dict):
                    umku_texts.append(u.get("name", str(u)))
                else:
                    umku_texts.append(str(u))
            if umku_texts:
                text_parts.append(f"UMKU: {', '.join(umku_texts)}")

    # 5. Keywords/Tags
    tags = record.get("tags_intel", [])
    if tags:
        text_parts.append(f"TAGS: {', '.join(tags)}")

    return "\n\n".join(text_parts)


def serialize_for_qdrant(input_path: str, output_path: str):
    logger.info(f"🔌 Serializing {input_path} for Qdrant (Masterpiece V5)...")

    if not os.path.exists(input_path):
        logger.error(f"❌ Input file not found: {input_path}")
        return

    with open(input_path, "r") as f:
        source_data = json.load(f)

    # Handle wrapped data vs list
    records = (
        source_data.get("data", []) if isinstance(source_data, dict) else source_data
    )

    qdrant_payloads = []

    for rec in records:
        # Generate UUID based on KBLI code for consistency
        kbli_code = rec.get("kode")  # Normalized key
        if kbli_code:
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"kbli_{kbli_code}"))
        else:
            point_id = str(uuid.uuid4())

        semantic_text = create_semantic_text(rec)

        payload_obj = {
            "id": point_id,
            "vector_source_text": semantic_text,  # This is what we will embed
            "payload": rec,  # The full original record (V5 Schema)
        }

        qdrant_payloads.append(payload_obj)

    # Save
    with open(output_path, "w") as f:
        json.dump(qdrant_payloads, f, indent=2, ensure_ascii=False)

    logger.info(f"✅ Serialized {len(qdrant_payloads)} records.")
    if len(qdrant_payloads) > 0:
        logger.info(
            f"📝 Semantic Text Preview (Record 1):\n---\n{qdrant_payloads[0]['vector_source_text'][:500]}...\n---"
        )
    logger.info(f"💾 Saved to {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        logger.error(
            "Usage: python3 masterpiece_to_qdrant.py <input_enriched.json> <output_qdrant_ready.json>"
        )
    else:
        serialize_for_qdrant(sys.argv[1], sys.argv[2])
