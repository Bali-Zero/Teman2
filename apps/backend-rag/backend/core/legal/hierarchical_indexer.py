"""
Hierarchical Document Indexer
Crea relazioni parent-child per retrieval gerarchico
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

import asyncpg

from app.core.config import settings
from core.legal.quality_validators import (
    assess_document_quality,
    calculate_text_fingerprint,
    extract_ayat_numbers,
    validate_ayat_sequence,
)

logger = logging.getLogger(__name__)


@dataclass
class HierarchicalChunk:
    """Chunk con riferimenti gerarchici"""

    chunk_id: str
    text: str
    # Gerarchia
    document_id: str  # ID documento radice (es: "UU_6_2023")
    chapter_id: str | None  # ID capitolo/BAB (es: "UU_6_2023_BAB_III")
    section_id: str | None  # ID sezione/Bagian
    article_id: str | None  # ID articolo/Pasal
    # Posizione
    hierarchy_path: str  # "UU_6_2023/BAB_III/Bagian_2/Pasal_15"
    hierarchy_level: int  # 0=doc, 1=bab, 2=bagian, 3=pasal, 4=ayat
    # Riferimenti per parent retrieval
    parent_chunk_ids: list[str]  # IDs dei chunk parent
    sibling_chunk_ids: list[str]  # IDs chunk fratelli (stesso livello)
    # Contenuto parent per context injection
    bab_title: str | None  # "BAB III - Hak dan Kewajiban"
    bab_full_text: str | None  # Testo completo del BAB (per retrieval)
    # Metadata originali
    metadata: dict[str, Any]


class HierarchicalIndexer:
    """
    Indicizza documenti legali con struttura gerarchica.
    Ogni chunk mantiene riferimenti al parent per retrieval espanso.
    """

    def __init__(self, structure_parser, qdrant_client, embeddings, chunker=None):
        self.parser = structure_parser
        self.qdrant = qdrant_client
        self.embeddings = embeddings
        self.chunker = chunker
        self.db_pool = None

    async def _get_db_pool(self):
        """Get or create DB pool"""
        if not self.db_pool:
            try:
                self.db_pool = await asyncpg.create_pool(
                    settings.database_url, min_size=1, max_size=5
                )
            except Exception as e:
                logger.error(f"Failed to create DB pool: {e}")
                raise
        return self.db_pool

    async def index_legal_document(
        self, document_text: str, document_id: str, metadata: dict
    ) -> dict[str, Any]:
        """
        Indicizza documento con struttura gerarchica completa.
        Strategia:
        1. Parse struttura (BAB → Bagian → Pasal → Ayat)
        2. Crea chunk per ogni Pasal (unità di ricerca)
        3. Salva riferimento al BAB completo (unità di contesto)
        4. Embedding solo sui chunk piccoli (Pasal)
        5. BAB completi salvati come "parent_documents" separati
        """
        # 1. Parse struttura
        structure = self.parser.parse(document_text)
        chunks_to_index = []
        parent_documents = []  # BAB completi per retrieval

        # 2. Processa ogni BAB
        for bab in structure.get("batang_tubuh", []):
            bab_id = f"{document_id}_BAB_{bab['number']}"
            bab_title = f"BAB {bab['number']} - {bab['title']}"
            bab_full_text = bab.get("text", "")  # Ensure text exists

            # If text is empty, try to reconstruct from pasals
            if not bab_full_text and bab.get("pasal"):
                bab_full_text = f"{bab_title}\n\n" + "\n\n".join([p["text"] for p in bab["pasal"]])

            # Quality assessment for BAB
            bab_quality = assess_document_quality(bab_full_text)

            # Salva BAB completo come parent document con quality metadata
            parent_documents.append(
                {
                    "id": bab_id,
                    "type": "parent_chapter",
                    "document_id": document_id,
                    "title": bab_title,
                    "full_text": bab_full_text,
                    "pasal_count": len(bab.get("pasal", [])),
                    "char_count": len(bab_full_text),
                    "metadata": metadata,
                    # Quality metadata
                    "text_fingerprint": bab_quality["text_fingerprint"],
                    "is_incomplete": bab_quality["is_incomplete"],
                    "ocr_quality_score": bab_quality["ocr_quality_score"],
                    "needs_reextract": bab_quality["needs_reextract"],
                }
            )

            # 3. Processa ogni Pasal nel BAB
            for pasal in bab.get("pasal", []):
                pasal_id = f"{document_id}_Pasal_{pasal['number']}"
                hierarchy_path = f"{document_id}/BAB_{bab['number']}/Pasal_{pasal['number']}"

                # SAFE SPLITTING: If Pasal is too large, split it using the chunker
                char_limit = 4000 # ~1000 tokens
                pasal_text = pasal["text"]
                
                if len(pasal_text) > char_limit and self.chunker:
                    logger.info(f"Pasal {pasal['number']} is too large ({len(pasal_text)} chars). Splitting...")
                    # Create sub-metadata for chunker
                    sub_metadata = {**metadata, "pasal_number": pasal["number"]}
                    sub_chunks = self.chunker.chunk(pasal_text, sub_metadata)
                    
                    for i, sc in enumerate(sub_chunks):
                        sc_id = f"{pasal_id}_{i}"
                        chunk = HierarchicalChunk(
                            chunk_id=sc_id,
                            text=sc["text"],
                            document_id=document_id,
                            chapter_id=bab_id,
                            section_id=None,
                            article_id=pasal_id,
                            hierarchy_path=f"{hierarchy_path}/{i}",
                            hierarchy_level=3,
                            parent_chunk_ids=[bab_id, document_id],
                            sibling_chunk_ids=[],
                            bab_title=bab_title,
                            bab_full_text=None,
                            metadata=sc
                        )
                        chunks_to_index.append(chunk)
                    continue

                # Standard processing for small Pasal
                # Extract and validate ayat from Pasal text
                ayat_numbers = extract_ayat_numbers(pasal_text)
                ayat_validation = validate_ayat_sequence(ayat_numbers)

                chunk = HierarchicalChunk(
                    chunk_id=pasal_id,
                    text=pasal["text"],
                    document_id=document_id,
                    chapter_id=bab_id,
                    section_id=None,
                    article_id=pasal_id,
                    hierarchy_path=hierarchy_path,
                    hierarchy_level=3,  # Pasal level
                    parent_chunk_ids=[bab_id, document_id],
                    sibling_chunk_ids=[],  # Popolato dopo
                    bab_title=bab_title,
                    bab_full_text=None,  # Non duplicare, usa bab_id per retrieval
                    metadata={
                        **metadata,
                        "pasal_number": pasal["number"],
                        # Ayat validation (use detected values, not parser's count)
                        "ayat_count": ayat_validation["ayat_count_detected"],
                        "ayat_max": ayat_validation["ayat_max_detected"],
                        "ayat_numbers": ayat_validation["ayat_numbers"],
                        "ayat_sequence_valid": ayat_validation["ayat_sequence_valid"],
                        "ayat_validation_error": ayat_validation["ayat_validation_error"],
                        "has_ayat": len(ayat_numbers) > 0,
                    },
                )
                chunks_to_index.append(chunk)

        # Fallback for unstructured text (if no chunks created from structure)
        if not chunks_to_index and self.chunker:
            logger.info(f"No structure found for {document_id}. Using fallback chunking.")
            flat_chunks = self.chunker.chunk(document_text, metadata)

            for i, fc in enumerate(flat_chunks):
                chunk_id = f"{document_id}_chunk_{i}"
                h_chunk = HierarchicalChunk(
                    chunk_id=chunk_id,
                    text=fc["text"],
                    document_id=document_id,
                    chapter_id=None,
                    section_id=None,
                    article_id=None,
                    hierarchy_path=f"{document_id}/chunk_{i}",
                    hierarchy_level=0,  # Flat / Document level
                    parent_chunk_ids=[document_id],
                    sibling_chunk_ids=[],
                    bab_title=None,
                    bab_full_text=None,
                    metadata=fc,
                )
                chunks_to_index.append(h_chunk)

        # 4. Genera embeddings solo per i chunk (Pasal)
        if chunks_to_index:
            chunk_texts = [c.text for c in chunks_to_index]
            embeddings = self.embeddings.generate_embeddings(chunk_texts)

            # 5. Upsert chunks con struttura gerarchica
            await self._upsert_hierarchical_chunks(chunks_to_index, embeddings)

        # 6. Upsert parent documents (BAB completi) - NO embedding, solo storage
        if parent_documents:
            await self._upsert_parent_documents(parent_documents)

        return {
            "document_id": document_id,
            "chunks_indexed": len(chunks_to_index),
            "parent_documents": len(parent_documents),
            "total_bab": len(structure.get("batang_tubuh", [])),
            "total_pasal": len(structure.get("pasal_list", [])),
        }

    async def _upsert_hierarchical_chunks(self, chunks: list[HierarchicalChunk], embeddings):
        """Upsert chunks con payload gerarchico"""
        import uuid

        # Namespace UUID per generare ID deterministici (stesso chunk_id → stesso UUID)
        NAMESPACE_LEGAL = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

        chunk_texts = []
        metadatas = []
        ids = []

        for chunk, embedding in zip(chunks, embeddings, strict=False):
            payload = {
                **chunk.metadata,
                # Campi gerarchici critici
                "document_id": chunk.document_id,
                "chapter_id": chunk.chapter_id,
                "hierarchy_path": chunk.hierarchy_path,
                "hierarchy_level": chunk.hierarchy_level,
                "parent_chunk_ids": chunk.parent_chunk_ids,
                "bab_title": chunk.bab_title,
            }

            chunk_texts.append(chunk.text)
            metadatas.append(payload)

            # Generate deterministic UUID from chunk_id via uuid5 (hash-based)
            # Idempotent: same chunk_id → same UUID → upsert overwrites instead of duplicating
            deterministic_uuid = str(uuid.uuid5(NAMESPACE_LEGAL, chunk.chunk_id))
            ids.append(deterministic_uuid)

        # Upsert batch via QdrantClient
        # Note: QdrantClient.upsert_documents handles batching and ID generation if needed,
        # but here we provide specific IDs.
        # We need to check if QdrantClient supports custom IDs in upsert_documents.
        # Looking at legal_ingestion_service.py, it calls upsert_documents(chunks, embeddings, metadatas)
        # It doesn't seem to take IDs. We might need to modify QdrantClient or rely on auto-generated IDs
        # but store our custom ID in metadata.
        # However, for retrieval, we need to link back.
        # Let's check QdrantClient implementation in core/qdrant_db.py

        # For now, I will assume I can pass IDs or I will store chunk_id in metadata.
        # Storing chunk_id in metadata is safer if the client doesn't support explicit IDs.
        # CRITICAL: Overwrite chunk_id with deterministic UUID5
        for meta, cid in zip(metadatas, ids, strict=False):
            original_chunk_id = meta.get("chunk_id", "NONE")
            meta["chunk_id"] = cid
            logger.info(f"UUID5: {original_chunk_id} → {cid}")

        logger.info(f"Upserting {len(ids)} chunks with deterministic UUID5 IDs")
        await self.qdrant.upsert_documents(
            chunks=chunk_texts, embeddings=embeddings, metadatas=metadatas, ids=ids
        )

    async def _upsert_parent_documents(self, parent_docs: list[dict]):
        """
        Salva documenti parent (BAB completi) in PostgreSQL.
        """
        pool = await self._get_db_pool()

        async with pool.acquire() as conn:
            # Prepare batch insert
            # We use ON CONFLICT DO UPDATE to handle re-ingestion
            for doc in parent_docs:
                # Try with new quality columns first
                try:
                    await conn.execute(
                        """
                        INSERT INTO parent_documents (
                            id, document_id, type, title, full_text,
                            char_count, pasal_count, metadata,
                            text_fingerprint, is_incomplete, ocr_quality_score, needs_reextract
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                        ON CONFLICT (id) DO UPDATE SET
                            title = EXCLUDED.title,
                            full_text = EXCLUDED.full_text,
                            char_count = EXCLUDED.char_count,
                            pasal_count = EXCLUDED.pasal_count,
                            metadata = EXCLUDED.metadata,
                            text_fingerprint = EXCLUDED.text_fingerprint,
                            is_incomplete = EXCLUDED.is_incomplete,
                            ocr_quality_score = EXCLUDED.ocr_quality_score,
                            needs_reextract = EXCLUDED.needs_reextract,
                            created_at = NOW()
                    """,
                        doc["id"],
                        doc["document_id"],
                        doc["type"],
                        doc["title"],
                        doc["full_text"],
                        doc["char_count"],
                        doc["pasal_count"],
                        json.dumps(doc["metadata"]),
                        doc.get("text_fingerprint"),
                        doc.get("is_incomplete", False),
                        doc.get("ocr_quality_score", 1.0),
                        doc.get("needs_reextract", False),
                    )
                except Exception as e:
                    # Fall back to basic INSERT without quality columns
                    if "does not exist" in str(e):
                        logger.warning(f"Quality columns not yet migrated, using basic INSERT: {e}")
                        await conn.execute(
                            """
                            INSERT INTO parent_documents (
                                id, document_id, type, title, full_text,
                                char_count, pasal_count, metadata
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                            ON CONFLICT (id) DO UPDATE SET
                                title = EXCLUDED.title,
                                full_text = EXCLUDED.full_text,
                                char_count = EXCLUDED.char_count,
                                pasal_count = EXCLUDED.pasal_count,
                                metadata = EXCLUDED.metadata,
                                created_at = NOW()
                        """,
                            doc["id"],
                            doc["document_id"],
                            doc["type"],
                            doc["title"],
                            doc["full_text"],
                            doc["char_count"],
                            doc["pasal_count"],
                            json.dumps(doc["metadata"]),
                        )
                    else:
                        raise

        logger.info(f"✅ Upserted {len(parent_docs)} parent documents to PostgreSQL")

    async def close(self):
        if self.db_pool:
            await self.db_pool.close()
