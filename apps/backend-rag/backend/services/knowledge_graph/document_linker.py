"""CRM Knowledge Graph — Document Linker

Builds the Tier-A "direct" subgraph after each successful CRM document OCR.

Relationships emitted (per upload):
  - Client(client_id) ← BELONGS_TO ← Document(file_id)
  - Practice(practice_id) ← PART_OF ← Document(file_id)   (if practice_id set)
  - Person(uuid5(passport)) ← DESCRIBES ← Document(file_id)  (passport docs)
  - Company(uuid5(npwp)) ← DESCRIBES ← Document(file_id)     (akta/npwp/nib)

All writes go to crm_kg_nodes / crm_kg_edges (migration 167) — separate from
the domain kg_nodes/kg_edges to keep PII isolated and RBAC simple.

Privacy:
  - passport_number / npwp / phone are NEVER stored raw in this table.
    Person and Company nodes are identified by UUIDv5(NAMESPACE_BALIZERO,
    sha256(raw + CRM_KG_HASH_SALT)).
  - Raw values stay in documents.ocr_data JSONB (existing CRM table) which
    is already protected by client-data RBAC.

Idempotency:
  - Nodes UPSERT by stable lookup key (file_id / client_id / practice_id /
    person_uid / company_uid).
  - Edges DELETE-then-INSERT for the source Document — re-OCR replaces the
    full set of outgoing edges, no orphan edges from a previous OCR pass.

Failure semantics:
  - kg_link_document is best-effort: any exception is logged and swallowed.
    OCR completion is the source of truth; the KG is a derived view that
    can be backfilled by a later cron if a single link write fails.
"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────

# Stable namespace for UUIDv5 person/company identifiers. Derived from a
# fixed UUID4 seed — see docstring of _person_uid for the reasoning.
# Any change to this constant invalidates all existing person/company
# uids (they won't match newly-extracted ones), so it must NEVER change.
_NAMESPACE_BALIZERO_CRM = uuid.UUID("8a7e6d5c-4b3a-4f1e-9d8c-7b6a5d4c3b2a")

# Edge confidence per tier (Level B/C populated by separate workers).
_CONFIDENCE_DIRECT = 1.0


def _hash_salt() -> str:
    """Read CRM_KG_HASH_SALT from env. Returns empty string if unset.

    An empty salt still produces deterministic hashes — it just means the
    hash output is the same as a salt-less hash. Setting the salt in prod
    is a defense-in-depth measure: if the kg table is ever exfiltrated
    independently of the env, the attacker cannot rainbow-table passport
    numbers without also stealing the salt.
    """
    return os.environ.get("CRM_KG_HASH_SALT", "")


def _person_uid(passport_number: str | None) -> uuid.UUID | None:
    """Stable UUID for a Person identified by passport number.

    Two documents that extracted the SAME passport_number produce the
    SAME UUIDv5 → they collapse onto the same Person node automatically
    (mediated SAME_PERSON_AS becomes a no-op, which is the correct
    behavior — "same passport" IS "same person", no edge needed).

    Returns None if passport_number is empty/None — caller must skip
    creating a Person node in that case.
    """
    if not passport_number or not passport_number.strip():
        return None
    digest = hashlib.sha256(
        f"{passport_number.strip().upper()}|{_hash_salt()}".encode(),
    ).hexdigest()
    return uuid.uuid5(_NAMESPACE_BALIZERO_CRM, f"person:{digest}")


def _company_uid(npwp: str | None) -> uuid.UUID | None:
    """Stable UUID for a Company identified by NPWP. See _person_uid."""
    if not npwp or not npwp.strip():
        return None
    # NPWP normalize: strip dots/dashes/spaces (NPWP can be written
    # 01.234.567.8-901.000 or 01234567890123)
    normalized = "".join(c for c in npwp.strip() if c.isdigit())
    if not normalized:
        return None
    digest = hashlib.sha256(
        f"{normalized}|{_hash_salt()}".encode(),
    ).hexdigest()
    return uuid.uuid5(_NAMESPACE_BALIZERO_CRM, f"company:{digest}")


# ─── Public API ─────────────────────────────────────────────────────────

async def kg_link_document(
    db_pool: asyncpg.Pool,
    *,
    file_id: str,
    client_id: int,
    document_type: str,
    extracted_fields: dict[str, Any] | None = None,
    practice_id: int | None = None,
    drive_url: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    """Link an OCR-classified document into the CRM knowledge graph.

    Idempotent: re-running with the same file_id replaces the document's
    outgoing edges and updates its node properties.

    Args:
        db_pool: asyncpg connection pool
        file_id: Drive file id (stable lookup key for Document node)
        client_id: clients.id (Document → Client BELONGS_TO edge)
        document_type: 'passport' | 'visa' | 'akta' | 'npwp' | 'nib' | etc.
        extracted_fields: OCR output (passport_number, npwp, expiry_date, …)
        practice_id: practices.id (Document → Practice PART_OF, optional)
        drive_url: webViewLink (stored in node properties for navigation)
        filename: original filename (stored in node properties)

    Returns:
        {"ok": True, "nodes": <int>, "edges": <int>}
        or {"ok": False, "error": "<reason>"}
    """
    extracted_fields = extracted_fields or {}

    try:
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # 1. Document node (primary entity for this upload)
                doc_props = {
                    "document_type": document_type,
                    "drive_url": drive_url,
                    "filename": filename,
                    # Note: extracted_fields go into ocr_data on documents
                    # table, not duplicated here. We keep just type + nav links.
                }
                doc_id = await _upsert_node(
                    conn,
                    entity_type="crm_document",
                    name=filename or f"document_{file_id[:8]}",
                    properties=doc_props,
                    file_id=file_id,
                )

                # 2. Client node (parent context). Bootstrap if missing.
                client_id_node = await _upsert_node(
                    conn,
                    entity_type="crm_client",
                    name=await _client_full_name(conn, client_id) or f"client_{client_id}",
                    properties={},
                    client_id=client_id,
                )

                # 3. Practice node (if document is tied to a specific practice)
                practice_id_node = None
                if practice_id is not None:
                    practice_id_node = await _upsert_node(
                        conn,
                        entity_type="crm_practice",
                        name=await _practice_name(conn, practice_id) or f"practice_{practice_id}",
                        properties={},
                        practice_id=practice_id,
                    )

                # 4. Person node (passport docs) — collapses to same node
                #    across multiple uploads of same passport.
                person_id_node = None
                pp_num = extracted_fields.get("passport_number")
                if pp_num:
                    p_uid = _person_uid(pp_num)
                    if p_uid is not None:
                        person_id_node = await _upsert_node(
                            conn,
                            entity_type="crm_person",
                            name=extracted_fields.get("full_name") or "person",
                            properties={
                                "nationality": extracted_fields.get("nationality"),
                                "date_of_birth": extracted_fields.get("date_of_birth"),
                                "gender": extracted_fields.get("gender"),
                                # NB: passport_number itself is NOT stored here.
                                # The uid is the only identifier in the graph.
                            },
                            person_uid=p_uid,
                        )

                # 5. Company node (akta / npwp_company / nib docs)
                company_id_node = None
                npwp = (
                    extracted_fields.get("npwp_company")
                    or extracted_fields.get("npwp")
                )
                if npwp:
                    c_uid = _company_uid(npwp)
                    if c_uid is not None:
                        company_id_node = await _upsert_node(
                            conn,
                            entity_type="crm_company",
                            name=extracted_fields.get("company_name") or "company",
                            properties={
                                "modal": extracted_fields.get("akta_modal"),
                                "kbli": extracted_fields.get("akta_kbli"),
                                # NPWP raw NOT stored — only company_uid.
                            },
                            company_uid=c_uid,
                        )

                # 6. Replace this document's outgoing edges atomically
                await conn.execute(
                    "DELETE FROM crm_kg_edges WHERE source_entity_id = $1",
                    doc_id,
                )

                edge_count = 0
                edge_count += await _insert_edge(
                    conn,
                    src=doc_id,
                    tgt=client_id_node,
                    rel_type="BELONGS_TO",
                    edge_tier="direct",
                )
                if practice_id_node is not None:
                    edge_count += await _insert_edge(
                        conn,
                        src=doc_id,
                        tgt=practice_id_node,
                        rel_type="PART_OF",
                        edge_tier="direct",
                    )
                if person_id_node is not None:
                    edge_count += await _insert_edge(
                        conn,
                        src=doc_id,
                        tgt=person_id_node,
                        rel_type="DESCRIBES",
                        edge_tier="direct",
                    )
                if company_id_node is not None:
                    edge_count += await _insert_edge(
                        conn,
                        src=doc_id,
                        tgt=company_id_node,
                        rel_type="DESCRIBES",
                        edge_tier="direct",
                    )

                node_count = sum(
                    1 for n in (
                        doc_id, client_id_node, practice_id_node,
                        person_id_node, company_id_node,
                    ) if n is not None
                )

                logger.info(
                    "kg_link_document: file_id=%s client_id=%d type=%s "
                    "nodes=%d edges=%d",
                    file_id, client_id, document_type, node_count, edge_count,
                )
                return {"ok": True, "nodes": node_count, "edges": edge_count}

    except Exception as e:
        # Best-effort: never let KG-linking errors break the OCR caller.
        logger.error(
            "kg_link_document failed for file_id=%s client_id=%d: %s",
            file_id, client_id, e, exc_info=True,
        )
        return {"ok": False, "error": str(e)}


# ─── Internal helpers ───────────────────────────────────────────────────


async def _upsert_node(
    conn: asyncpg.Connection,
    *,
    entity_type: str,
    name: str,
    properties: dict[str, Any],
    file_id: str | None = None,
    client_id: int | None = None,
    practice_id: int | None = None,
    person_uid: uuid.UUID | None = None,
    company_uid: uuid.UUID | None = None,
) -> uuid.UUID:
    """UPSERT a crm_kg_node by stable lookup key. Returns entity_id."""
    # Map entity_type to its lookup column. Each type has exactly one
    # stable key (enforced by per-type unique partial indexes in m167).
    lookup_col = {
        "crm_document": "file_id",
        "crm_client": "client_id",
        "crm_practice": "practice_id",
        "crm_person": "person_uid",
        "crm_company": "company_uid",
    }[entity_type]
    lookup_val = {
        "file_id": file_id,
        "client_id": client_id,
        "practice_id": practice_id,
        "person_uid": person_uid,
        "company_uid": company_uid,
    }[lookup_col]

    if lookup_val is None:
        msg = f"_upsert_node: missing lookup value for {entity_type} ({lookup_col})"
        raise ValueError(msg)

    # First try update (existing node). Strip None values from properties
    # so a partial OCR doesn't blank out fields from a previous fuller pass.
    clean_props = {k: v for k, v in properties.items() if v is not None}

    existing = await conn.fetchrow(
        f"SELECT entity_id, properties FROM crm_kg_nodes "  # noqa: S608
        f"WHERE {lookup_col} = $1 AND deleted_at IS NULL",
        lookup_val,
    )
    if existing:
        # Merge new fields into existing properties (no overwrite with None)
        merged = {**existing["properties"], **clean_props}
        await conn.execute(
            "UPDATE crm_kg_nodes "
            "SET name = $1, properties = $2, updated_at = NOW() "
            "WHERE entity_id = $3",
            name, merged, existing["entity_id"],
        )
        return existing["entity_id"]

    # Insert new node. Set the appropriate stable-key column.
    columns = ["entity_type", "name", "properties", lookup_col]
    placeholders = ["$1", "$2", "$3", "$4"]
    values: list[Any] = [entity_type, name, clean_props, lookup_val]

    row = await conn.fetchrow(
        f"INSERT INTO crm_kg_nodes ({', '.join(columns)}) "  # noqa: S608
        f"VALUES ({', '.join(placeholders)}) "
        f"RETURNING entity_id",
        *values,
    )
    return row["entity_id"]


async def _insert_edge(
    conn: asyncpg.Connection,
    *,
    src: uuid.UUID,
    tgt: uuid.UUID,
    rel_type: str,
    edge_tier: str,
    properties: dict[str, Any] | None = None,
    confidence: float = _CONFIDENCE_DIRECT,
) -> int:
    """Insert an edge with idempotent ON CONFLICT update. Returns 1."""
    await conn.execute(
        """
        INSERT INTO crm_kg_edges (
            source_entity_id, target_entity_id, relationship_type,
            properties, edge_tier, confidence
        ) VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (source_entity_id, target_entity_id, relationship_type)
        DO UPDATE SET
            properties = EXCLUDED.properties,
            edge_tier = EXCLUDED.edge_tier,
            confidence = EXCLUDED.confidence
        """,
        src, tgt, rel_type, properties or {}, edge_tier, confidence,
    )
    return 1


async def _client_full_name(conn: asyncpg.Connection, client_id: int) -> str | None:
    """Read full_name from clients table for human-readable node name."""
    row = await conn.fetchrow(
        "SELECT full_name FROM clients WHERE id = $1 AND deleted_at IS NULL",
        client_id,
    )
    return row["full_name"] if row else None


async def _practice_name(conn: asyncpg.Connection, practice_id: int) -> str | None:
    """Read a human-readable name for a practice (best-effort)."""
    # Practices schema varies; try common columns and fall back to id.
    for col in ("name", "title", "practice_type_code"):
        try:
            row = await conn.fetchrow(
                f"SELECT {col} FROM practices WHERE id = $1",  # noqa: S608
                practice_id,
            )
            if row and row[col]:
                return str(row[col])
        except asyncpg.UndefinedColumnError:
            continue
    return None
