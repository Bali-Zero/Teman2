#!/usr/bin/env python3
"""
Agent 2: Transform KBLI to KG Entities
=======================================
Transforms extracted KBLI data into Knowledge Graph entities format.

Input: data/kbli_extraction_*.json (from Agent 1)
Output: data/kg_entities_YYYYMMDD_HHMMSS.json
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [AGENT-2] - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_kbli_node(kbli_doc: dict) -> dict:
    """
    Create kg_nodes entry for KBLI code.

    Args:
        kbli_doc: KBLI document from Qdrant

    Returns:
        kg_nodes entry dict
    """
    kode = kbli_doc.get("kode_kbli", "")
    entity_id = f"kbli:{kode}"

    return {
        "entity_id": entity_id,
        "entity_type": "kbli",
        "name": f"KBLI {kode}",
        "description": kbli_doc.get("judul", "") or kbli_doc.get("content", "")[:200],
        "metadata": {
            "kode": kode,
            "uraian": kbli_doc.get("content", ""),
            "sektor_id": kbli_doc.get("sektor_id", ""),
            "pma_status": kbli_doc.get("pma_status", ""),
            "kategori_risiko": kbli_doc.get("kategori_risiko", ""),
            "skala_usaha": kbli_doc.get("skala_usaha", ""),
        },
        "confidence": 1.0,
        "source_collection": "kbli_2025_final",
    }


def expand_sektor_ranges(sektor_id: str) -> list[str]:
    """
    Expand consolidated sektor ranges to individual sektors.

    KBLI 2025 has 22 categories (A-V):
    - I.J-P consolidates 7 categories: J, K, L, M, N, O, P
    - I.Q-V consolidates 6 categories: Q, R, S, T, U, V

    Args:
        sektor_id: Original sektor identifier (e.g., "I.J-P")

    Returns:
        List of expanded sektor identifiers
    """
    if sektor_id == "I.J-P":
        # Expand to 7 categories
        return ["I.J", "I.K", "I.L", "I.M", "I.N", "I.O", "I.P"]
    elif sektor_id == "I.Q-V":
        # Expand to 6 categories
        return ["I.Q", "I.R", "I.S", "I.T", "I.U", "I.V"]
    else:
        # Not a range, return as-is
        return [sektor_id]


def normalize_sektor_f(sektor_id: str, consolidate_f: bool = True) -> str:
    """
    Normalize Sektor F subdivisions to a single F category.

    Args:
        sektor_id: Original sektor identifier (e.g., "I.F.a", "I.F.b", etc.)
        consolidate_f: If True, consolidate I.F.a-h to I.F

    Returns:
        Normalized sektor identifier
    """
    if consolidate_f and sektor_id.startswith("I.F."):
        return "I.F"
    return sektor_id


def create_sektor_node(sektor_id: str) -> dict:
    """
    Create kg_nodes entry for Sektor.

    Args:
        sektor_id: Sektor identifier (e.g., "I.B")

    Returns:
        kg_nodes entry dict
    """
    # Map sektor codes to full names (KBLI 2025)
    sektor_names = {
        "I.A": "Pertanian, Kehutanan dan Perikanan",
        "I.B": "Pertambangan dan Penggalian",
        "I.C": "Industri Pengolahan",
        "I.D": "Pengadaan Listrik, Gas, Uap/Air Panas dan Udara Dingin",
        "I.E": "Treatment Air, Pengelolaan Air Limbah, Sampah dan Daur Ulang",
        "I.F": "Konstruksi",
        "I.G": "Perdagangan Besar dan Eceran",
        "I.H": "Pengangkutan dan Pergudangan",
        "I.I": "Penyediaan Akomodasi dan Makan Minum",
        "I.J": "Informasi dan Komunikasi",
        "I.K": "Jasa Keuangan dan Asuransi",
        "I.L": "Real Estate",
        "I.M": "Jasa Profesional, Ilmiah dan Teknis",
        "I.N": "Jasa Persewaan, Ketenagakerjaan, Agen Perjalanan dan Penunjang Usaha Lainnya",
        "I.O": "Administrasi Pemerintahan, Pertahanan dan Jaminan Sosial Wajib",
        "I.P": "Jasa Pendidikan",
        "I.Q": "Jasa Kesehatan dan Kegiatan Sosial",
        "I.R": "Kesenian, Hiburan dan Rekreasi",
        "I.S": "Kegiatan Jasa Lainnya",
        "I.T": "Jasa Perorangan yang Melayani Rumah Tangga",
        "I.U": "Kegiatan Badan Internasional dan Badan Ekstra Internasional Lainnya",
        "I.V": "Kegiatan yang Belum Jelas Batasannya",
    }

    full_name = sektor_names.get(sektor_id, f"Sektor {sektor_id}")

    return {
        "entity_id": f"sektor:{sektor_id}",
        "entity_type": "sektor",
        "name": full_name,
        "description": f"Kategori KBLI 2025: {full_name}",
        "metadata": {
            "sektor_code": sektor_id,
            "kbli_2025_category": sektor_id.replace("I.", ""),
        },
        "confidence": 1.0,
        "source_collection": "kbli_2025_final",
    }


def create_perizinan_nodes(kbli_code: str, per_skala: dict) -> list[dict]:
    """
    Create perizinan nodes from per_skala structure.

    Args:
        kbli_code: KBLI code
        per_skala: Dictionary with scale-specific requirements

    Returns:
        List of perizinan kg_nodes entries
    """
    perizinan_nodes = []

    for scale, requirements in per_skala.items():
        if not requirements:
            continue

        if isinstance(requirements, dict):
            req_list = requirements.get("perizinan", [])
        elif isinstance(requirements, list):
            req_list = requirements
        else:
            continue

        for perizinan_name in req_list:
            if not perizinan_name:
                continue

            # Normalize perizinan name
            perizinan_slug = perizinan_name.lower().replace(" ", "_")
            entity_id = f"perizinan:{perizinan_slug}"

            perizinan_nodes.append(
                {
                    "entity_id": entity_id,
                    "entity_type": "perizinan",
                    "name": perizinan_name,
                    "description": f"Perizinan: {perizinan_name}",
                    "metadata": {
                        "name": perizinan_name,
                        "applicable_scales": [scale],
                    },
                    "confidence": 1.0,
                    "source_collection": "kbli_2025_final",
                }
            )

    return perizinan_nodes


def create_kbli_edges(
    kbli_doc: dict,
    normalized_sektor_ids: list[str],
    perizinan_nodes: list[dict],
) -> list[dict]:
    """
    Create edges for KBLI relationships.

    Args:
        kbli_doc: KBLI document
        normalized_sektor_ids: List of normalized/expanded sektor IDs
        perizinan_nodes: List of perizinan nodes created

    Returns:
        List of kg_edges entries
    """
    edges = []
    kode = kbli_doc.get("kode_kbli", "")
    kbli_entity_id = f"kbli:{kode}"

    # Edge: KBLI BELONGS_TO Sektor (for each expanded sektor)
    for sektor_id in normalized_sektor_ids:
        if sektor_id:
            edges.append(
                {
                    "source_entity_id": kbli_entity_id,
                    "target_entity_id": f"sektor:{sektor_id}",
                    "relationship_type": "BELONGS_TO",
                    "metadata": {
                        "original_sektor": kbli_doc.get("sektor_id", ""),
                    },
                    "confidence": 1.0,
                    "source_collection": "kbli_2025_final",
                }
            )

    # Edge: KBLI REQUIRES Perizinan
    for perizinan_node in perizinan_nodes:
        edges.append(
            {
                "source_entity_id": kbli_entity_id,
                "target_entity_id": perizinan_node["entity_id"],
                "relationship_type": "REQUIRES",
                "metadata": {"scales": perizinan_node["metadata"]["applicable_scales"]},
                "confidence": 1.0,
                "source_collection": "kbli_2025_final",
            }
        )

    return edges


def transform_kbli_to_kg(kbli_documents: list[dict], consolidate_f: bool = True) -> dict:
    """
    Transform KBLI documents to KG entities.

    Args:
        kbli_documents: List of KBLI documents from Qdrant
        consolidate_f: If True, consolidate I.F.a-h to single I.F sektor

    Returns:
        Dict with 'nodes' and 'edges' lists
    """
    nodes = []
    edges = []
    sektor_ids_seen = set()
    perizinan_ids_seen = {}  # entity_id -> node dict

    logger.info(f"Transforming {len(kbli_documents):,} KBLI documents...")
    logger.info(f"Settings: consolidate_f={consolidate_f}")

    for idx, kbli_doc in enumerate(kbli_documents, 1):
        try:
            # Create KBLI node
            kbli_node = create_kbli_node(kbli_doc)
            nodes.append(kbli_node)

            # Get original sektor_id
            original_sektor_id = kbli_doc.get("sektor_id", "")
            if not original_sektor_id:
                continue

            # Step 1: Normalize F subdivisions (optional)
            normalized_sektor = normalize_sektor_f(original_sektor_id, consolidate_f)

            # Step 2: Expand ranges (I.J-P → 7 sektors, I.Q-V → 6 sektors)
            expanded_sektors = expand_sektor_ranges(normalized_sektor)

            # Step 3: Create sektor nodes for each expanded sektor
            for sektor_id in expanded_sektors:
                if sektor_id not in sektor_ids_seen:
                    nodes.append(create_sektor_node(sektor_id))
                    sektor_ids_seen.add(sektor_id)

            # Create Perizinan nodes from per_skala
            per_skala = kbli_doc.get("per_skala", {})
            perizinan_nodes = create_perizinan_nodes(kbli_doc.get("kode_kbli", ""), per_skala)

            # Deduplicate perizinan nodes
            for perizinan_node in perizinan_nodes:
                entity_id = perizinan_node["entity_id"]
                if entity_id not in perizinan_ids_seen:
                    nodes.append(perizinan_node)
                    perizinan_ids_seen[entity_id] = perizinan_node

            # Create edges (KBLI → expanded sektors + perizinan)
            kbli_edges = create_kbli_edges(kbli_doc, expanded_sektors, perizinan_nodes)
            edges.extend(kbli_edges)

            if idx % 1000 == 0:
                logger.info(
                    f"  Processed {idx:,}/{len(kbli_documents):,} "
                    f"({idx / len(kbli_documents) * 100:.1f}%)"
                )

        except Exception as e:
            logger.warning(f"Error processing KBLI {kbli_doc.get('kode_kbli', 'unknown')}: {e}")
            continue

    logger.info("✅ Transformation complete:")
    logger.info(f"   Total nodes: {len(nodes):,}")
    logger.info(f"     - KBLI nodes: {len(kbli_documents):,}")
    logger.info(f"     - Sektor nodes: {len(sektor_ids_seen):,}")
    logger.info(f"     - Perizinan nodes: {len(perizinan_ids_seen):,}")
    logger.info(f"   Total edges: {len(edges):,}")

    # Verify KBLI 2025 compliance (should have 22 sektors)
    expected_sektors = 22
    if len(sektor_ids_seen) == expected_sektors:
        logger.info(f"   ✅ KBLI 2025 compliance: {len(sektor_ids_seen)} sektors (A-V)")
    else:
        logger.warning(f"   ⚠️  Expected {expected_sektors} sektors, got {len(sektor_ids_seen)}")
        missing = expected_sektors - len(sektor_ids_seen)
        logger.warning(f"   Missing {missing} sektors")

    return {"nodes": nodes, "edges": edges}


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description="Transform KBLI extraction to KG entities")
    parser.add_argument(
        "--input",
        type=str,
        help="Path to kbli_extraction JSON file (from Agent 1)",
    )
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("AGENT 2: KBLI TO KG ENTITIES TRANSFORMATION")
    logger.info("=" * 70)

    # Find input file
    if args.input:
        input_file = Path(args.input)
    else:
        # Find latest extraction file
        data_dir = Path(__file__).parent.parent.parent / "data"
        extraction_files = sorted(data_dir.glob("kbli_extraction_*.json"), reverse=True)
        if not extraction_files:
            logger.error("❌ No kbli_extraction_*.json files found in data/")
            return
        input_file = extraction_files[0]

    logger.info(f"Input file: {input_file}")

    # Load data
    with open(input_file, encoding="utf-8") as f:
        kbli_documents = json.load(f)

    logger.info(f"Loaded {len(kbli_documents):,} KBLI documents")

    # Transform
    kg_entities = transform_kbli_to_kg(kbli_documents)

    # Save output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(__file__).parent.parent.parent / "data"
    output_file = output_dir / f"kg_entities_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(kg_entities, f, ensure_ascii=False, indent=2)

    logger.info(f"\n✅ KG entities saved to: {output_file}")
    logger.info(f"📦 File size: {output_file.stat().st_size / 1024 / 1024:.2f} MB")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
