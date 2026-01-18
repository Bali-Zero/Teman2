#!/usr/bin/env python3
"""
Platinum KBLI Ingestion Script (2026) - Parallel Collection & Deep Graph
------------------------------------------------------------------------
Ingests the 'kbli_universal_atlas_polished.json' (Platinum Master) into:
1.  Qdrant Collection: `kbli_platinum_2026` (Semantic vector search)
2.  Knowledge Graph (PostgreSQL): Deep relational extraction.

Graph Schema Enriched:
- Nodes: KBLI, Permit (SIPA/SLS), Regulation (Ingub 6), Zone (Pink), Danger (PKKPR Veto)
- Edges: BLOCKED_BY, REQUIRES, RESTRICTED_TO, PIVOT_TO

Usage:
    python scripts/ingestion/ingest_kbli_platinum_2026.py --dry-run
    python scripts/ingestion/ingest_kbli_platinum_2026.py --recreate
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from typing import Dict, List

import httpx
from dotenv import load_dotenv

# Path setup
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "backend-rag")
)
try:
    load_dotenv(
        os.path.join(
            os.path.dirname(__file__), "..", "..", "apps", "backend-rag", ".env"
        )
    )
except:
    pass

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

COLLECTION_NAME = "kbli_platinum_2026"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

ATLAS_PATH = os.path.join(
    os.path.dirname(__file__),
    "../../reports/kbli_extraction/kbli_universal_atlas_polished.json",
)

# Deep Intelligence Maps (Hardcoded Logic for Graph Enrichment)
PIVOT_STRATEGIES = {
    "70209": "62193",  # Consulting -> Blockchain
    "73100": "63122",  # Marketing -> Digital Portal
    "55901": "62110",  # Villa Mgmt -> Software Publisher
    "47111": "47112",  # Minimarket Chain -> Standalone
}

# Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class KBLIPlatinumIngestion:
    def __init__(self, dry_run: bool = False, recreate: bool = False):
        self.dry_run = dry_run
        self.recreate = recreate
        self.stats = {
            "processed": 0,
            "vectors_uploaded": 0,
            "nodes_created": 0,
            "edges_created": 0,
            "errors": [],
        }

    async def _qdrant_request(
        self, client, method: str, endpoint: str, json_data: dict = None
    ) -> dict:
        url = f"{QDRANT_URL}{endpoint}"
        headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}
        if method == "GET":
            resp = await client.get(url, headers=headers)
        elif method == "PUT":
            resp = await client.put(url, headers=headers, json=json_data)
        elif method == "DELETE":
            resp = await client.delete(url, headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def setup_collection(self):
        """Create or recreate the Qdrant collection."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would create collection {COLLECTION_NAME}")
            return

        async with httpx.AsyncClient() as client:
            # Check exist
            try:
                await self._qdrant_request(
                    client, "GET", f"/collections/{COLLECTION_NAME}"
                )
                exists = True
            except httpx.HTTPStatusError:
                exists = False

            if exists:
                if self.recreate:
                    logger.info(f"Deleting existing collection {COLLECTION_NAME}...")
                    await self._qdrant_request(
                        client, "DELETE", f"/collections/{COLLECTION_NAME}"
                    )
                else:
                    logger.info(f"Collection {COLLECTION_NAME} exists. Appending...")
                    return

            logger.info(f"Creating collection {COLLECTION_NAME}...")
            await self._qdrant_request(
                client,
                "PUT",
                f"/collections/{COLLECTION_NAME}",
                {"vectors": {"size": EMBEDDING_DIM, "distance": "Cosine"}},
            )

    def format_kbli_content(self, code: str, data: Dict) -> str:
        """Generate the semantic text chunk for embedding."""
        title = data.get("title", "Unknown")
        risk_data = data.get("risk_data", {})
        legal_notices = data.get("legal_notices", [])

        # Keys in Atlas: risiko, skala, authority, ruang, sektor
        risk_level = risk_data.get("risiko", "Unknown")
        scale = risk_data.get("skala", "None")
        sector = risk_data.get("sektor", "General")
        authority = risk_data.get("authority", "N/A")
        scope = risk_data.get("ruang", "See regulation.")

        # Context Header
        text = f"[CONTEXT: KBLI 2026 PLATINUM - Code {code} - {sector} - Risk {risk_level}]\n\n"

        # Main Body
        text += f"# {code} - {title}\n\n"
        text += f"**Risk Level**: {risk_level} (Scale: {scale})\n"
        text += f"**Sector**: {sector}\n"
        text += f"**Authority**: {authority}\n\n"

        # Scope
        text += f"## Scope\n{scope}\n\n"

        # Legal Notices (Critical for RAG)
        if legal_notices:
            text += "## ⚠️ Critical Intelligence & Notices\n"
            for notice in legal_notices:
                text += f"### {notice.get('title')}\n{notice.get('description', 'No details available.')}\n"
                if notice.get("tags"):
                    text += f"Tags: {', '.join(notice.get('tags'))}\n"
            text += "\n"

        # Sanctions
        if "sanksi_administratif" in risk_data:
            text += f"## Sanctions\n{risk_data['sanksi_administratif']}\n"

        return text

    def extract_graph_elements(self, code: str, data: Dict) -> Dict:
        """Extract KG Nodes and Edges from a single KBLI record."""
        nodes = []
        edges = []

        # 1. Main KBLI Node
        kbli_id = f"kbli_{code}"
        nodes.append(
            {
                "id": kbli_id,
                "type": "kbli_code",
                "name": f"{code} - {data.get('title')}",
                "props": {
                    "code": code,
                    "risk": data.get("risk_data", {}).get("tingkat_risiko"),
                    "sector": data.get("risk_data", {}).get("sektor"),
                },
            }
        )

        # 2. Risk Node
        risk_level = data.get("risk_data", {}).get("tingkat_risiko")
        if risk_level:
            risk_id = f"risk_{risk_level.lower().replace(' ', '_')}"
            nodes.append(
                {"id": risk_id, "type": "risk_level", "name": risk_level, "props": {}}
            )
            edges.append(
                {"source": kbli_id, "target": risk_id, "type": "HAS_RISK", "props": {}}
            )

        # 3. Intelligence / Regulatory Nodes (from Legal Notices)
        for notice in data.get("legal_notices", []):
            tags = notice.get("tags", [])
            title = notice.get("title", "")

            # Zoning (Pink Zone)
            if "PINK_ZONE_ONLY" in tags or "Pink Zone" in title:
                nodes.append(
                    {
                        "id": "zone_pink",
                        "type": "zone",
                        "name": "Pink Zone (Pariwisata)",
                        "props": {},
                    }
                )
                edges.append(
                    {
                        "source": kbli_id,
                        "target": "zone_pink",
                        "type": "RESTRICTED_TO",
                        "props": {"reason": "Sarbagita Moratorium"},
                    }
                )

            # SIPA Water Permit
            if "SIPA_REQUIRED" in tags or "SIPA" in title:
                nodes.append(
                    {
                        "id": "permit_sipa",
                        "type": "permit",
                        "name": "SIPA (Water License)",
                        "props": {},
                    }
                )
                edges.append(
                    {
                        "source": kbli_id,
                        "target": "permit_sipa",
                        "type": "REQUIRES_PERMIT",
                        "props": {},
                    }
                )

            # Sertifikat Laik Sehat (SLS)
            if "SLS" in title:
                nodes.append(
                    {
                        "id": "permit_sls",
                        "type": "permit",
                        "name": "Sertifikat Laik Sehat",
                        "props": {},
                    }
                )
                edges.append(
                    {
                        "source": kbli_id,
                        "target": "permit_sls",
                        "type": "REQUIRES_PERMIT",
                        "props": {},
                    }
                )

            # Moratorium Ingub 6
            if "Ingub 6/2025" in title or "BLOCKED_BY_MORATORIUM" in tags:
                nodes.append(
                    {
                        "id": "reg_ingub6_2025",
                        "type": "regulation",
                        "name": "Ingub Bali 6/2025",
                        "props": {},
                    }
                )
                edges.append(
                    {
                        "source": kbli_id,
                        "target": "reg_ingub6_2025",
                        "type": "BLOCKED_BY",
                        "props": {},
                    }
                )

            # Governor Veto (PKKPR)
            if "PKKPR_DISCRETION_RISK" in tags:
                nodes.append(
                    {
                        "id": "risk_governor_veto",
                        "type": "risk_factor",
                        "name": "Governor Veto (PKKPR)",
                        "props": {},
                    }
                )
                edges.append(
                    {
                        "source": kbli_id,
                        "target": "risk_governor_veto",
                        "type": "SUBJECT_TO_SCRUTINY",
                        "props": {},
                    }
                )

        # 4. Strategic Pivots (Hardcoded Logic)
        if code in PIVOT_STRATEGIES:
            target_code = PIVOT_STRATEGIES[code]
            target_id = f"kbli_{target_code}"
            edges.append(
                {
                    "source": kbli_id,
                    "target": target_id,
                    "type": "HAS_pIVOT_STRATEGY",
                    "props": {"type": "Regulatory Arbitrage"},
                }
            )

        return {"nodes": nodes, "edges": edges}

    async def save_kg_batch(self, nodes: List[Dict], edges: List[Dict]):
        """Save graph elements to PostgreSQL."""
        if not DATABASE_URL:
            logger.warning("No DATABASE_URL. Skipping KG persistence.")
            return

        import asyncpg

        conn = await asyncpg.connect(DATABASE_URL)
        try:
            # Upsert Nodes
            for n in nodes:
                await conn.execute(
                    """
                    INSERT INTO kg_nodes (entity_id, entity_type, name, properties, source_collection, confidence)
                    VALUES ($1, $2, $3, $4::jsonb, $5, 0.95)
                    ON CONFLICT (entity_id) DO UPDATE SET properties = EXCLUDED.properties
                """,
                    n["id"],
                    n["type"],
                    n["name"],
                    json.dumps(n["props"]),
                    COLLECTION_NAME,
                )

            # Upsert Edges
            for e in edges:
                rel_id = f"rel_{e['source']}_{e['type']}_{e['target']}"  # Deterministic Edge ID
                # Ensure target node exists (placeholder) if not in batch
                # (Simple approach: we assume node batches might be disjoint, so we use ON CONFLICT DO NOTHING implies target might be missing
                # but in SQL foreign keys might bite. Here we assume loose schema or we create placeholders.
                # Actually, `ingest_visa_kg` creates placeholders. Let's replicate simple placeholder creation if needed,
                # but for KBLI internal links, they usually exist. For external (Regs), we create them above.)

                await conn.execute(
                    """
                    INSERT INTO kg_edges (relationship_id, source_entity_id, target_entity_id, relationship_type, properties, source_collection, confidence)
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6, 0.95)
                    ON CONFLICT (relationship_id) DO NOTHING
                """,
                    rel_id,
                    e["source"],
                    e["target"],
                    e["type"],
                    json.dumps(e["props"]),
                    COLLECTION_NAME,
                )

        except Exception as err:
            logger.error(f"KG Save error: {err}")
        finally:
            await conn.close()

    async def run(self):
        logger.info(f"Starting Platinum Ingestion. Source: {ATLAS_PATH}")

        # Load Atlas
        with open(ATLAS_PATH, "r") as f:
            atlas = json.load(f)
        data = atlas.get("data", {})
        logger.info(f"Loaded {len(data)} KBLI records.")

        # Setup Qdrant
        await self.setup_collection()

        # Init OpenAI
        import openai

        openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

        # Batch Processing
        batch_size = 50
        items = list(data.items())

        all_nodes = []
        all_edges = []
        pivot_samples = []

        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            points = []

            # Prepare Batch Texts for Embedding
            texts = []
            metadata_list = []

            for code, info in batch:
                # 1. RAG Preparation
                content = self.format_kbli_content(code, info)
                texts.append(content)
                metadata_list.append(
                    {
                        "kbli_code": code,
                        "title": info.get("title"),
                        "sector": info.get("risk_data", {}).get("sektor"),
                        "source": "Platinum Atlas 2026",
                    }
                )

                # 2. KG Extraction
                graph_data = self.extract_graph_elements(code, info)
                all_nodes.extend(graph_data["nodes"])
                all_edges.extend(graph_data["edges"])

                # Capture samples for verification
                for edge in graph_data["edges"]:
                    if edge["type"] == "HAS_pIVOT_STRATEGY":
                        pivot_samples.append(
                            f"{code} -> {edge['target']} ({edge['props']['type']})"
                        )

            # Embed Batch
            if not self.dry_run:
                try:
                    resp = openai_client.embeddings.create(
                        input=[t[:8000] for t in texts], model=EMBEDDING_MODEL
                    )
                    embeddings = [d.embedding for d in resp.data]

                    # Create Points
                    for idx, (code, _) in enumerate(batch):
                        points.append(
                            {
                                "id": str(
                                    uuid.uuid5(uuid.NAMESPACE_DNS, f"kbli_plat_{code}")
                                ),
                                "vector": embeddings[idx],
                                "payload": {
                                    "content": texts[idx],
                                    **metadata_list[idx],
                                },
                            }
                        )

                    # Upload to Qdrant
                    async with httpx.AsyncClient(timeout=60) as client:
                        await self._qdrant_request(
                            client,
                            "PUT",
                            f"/collections/{COLLECTION_NAME}/points",
                            {"points": points},
                        )

                    self.stats["vectors_uploaded"] += len(points)
                    logger.info(f"Uploaded batch {i}-{i + len(batch)}")

                except Exception as e:
                    logger.error(f"Batch embedding/upload failed: {e}")

            self.stats["processed"] += len(batch)

        # Update stats regardless of mode
        self.stats["nodes_created"] = len(all_nodes)
        self.stats["edges_created"] = len(all_edges)

        # Save KG Data (Bulk)
        if not self.dry_run:
            logger.info(
                f"Saving KG Data: {len(all_nodes)} Nodes, {len(all_edges)} Edges..."
            )
            try:
                await self.save_kg_batch(all_nodes, all_edges)
            except Exception as e:
                logger.warning(
                    f"Failed to persist KG to Postgres: {e}. Qdrant ingestion is unaffected."
                )
        else:
            logger.info(
                f"[DRY RUN] Would save {len(all_nodes)} Nodes and {len(all_edges)} Edges."
            )
            logger.info(f"[DRY RUN] Sample Pivots found: {pivot_samples[:5]}")

        logger.info("Ingestion Complete.")
        logger.info(f"Stats: {self.stats}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--recreate", action="store_true")
    args = parser.parse_args()

    ingester = KBLIPlatinumIngestion(dry_run=args.dry_run, recreate=args.recreate)
    asyncio.run(ingester.run())
