"""Property acquisition subgraph — Hak Pakai, HGB, Strata Title, etc.

Identifies property right type, checks foreigner eligibility,
retrieves ownership requirements and restrictions.
"""

from __future__ import annotations

from typing import Any

import structlog

from nuzantara_graph.services import Services
from nuzantara_schemas.domain.property import PropertyRight
from nuzantara_schemas.state import GraphState, RetrievedDocument

logger = structlog.get_logger()

# Property specifications — Indonesian land law (BPN/ATR)
PROPERTY_SPECS: dict[str, dict[str, Any]] = {
    PropertyRight.HAK_PAKAI: {
        "foreigner_eligible": True,
        "duration_years": 30,
        "renewable": True,
        "max_renewals": 2,
        "requires_pt": False,
        "restrictions": [
            "Holder must have KITAS/KITAP",
            "Property for personal residence only (not commercial)",
            "Max 1 property per foreigner",
            "Cannot be in restricted zones (military, border areas)",
        ],
        "requirements": [
            "Valid KITAS or KITAP",
            "Deed of Sale (Akta Jual Beli) via PPAT notary",
            "BPN land certificate verification",
            "Pay BPHTB tax (5% of transaction value)",
            "Register at local BPN (Land Office)",
            "PBB tax must be current",
        ],
    },
    PropertyRight.HGB: {
        "foreigner_eligible": False,
        "duration_years": 30,
        "renewable": True,
        "max_renewals": 2,
        "requires_pt": True,
        "restrictions": [
            "Indonesian legal entity only (PT PMA or PT PMDN)",
            "Commercial or residential use",
            "Foreigners can access via PT PMA ownership",
        ],
        "requirements": [
            "PT company as owner (not individual)",
            "Company deed of establishment",
            "BPHTB tax payment",
            "BPN registration",
            "Building permit (IMB/PBG)",
        ],
    },
    PropertyRight.HAK_MILIK: {
        "foreigner_eligible": False,
        "duration_years": 0,  # Permanent
        "renewable": False,
        "requires_pt": False,
        "restrictions": [
            "Indonesian citizens ONLY",
            "Foreigners cannot hold Hak Milik under any structure",
            "Must be divested if holder loses Indonesian citizenship",
        ],
        "requirements": [
            "Indonesian citizenship (KTP)",
            "Akta Jual Beli via PPAT",
            "BPN registration",
            "BPHTB tax payment",
        ],
    },
    PropertyRight.STRATA_TITLE: {
        "foreigner_eligible": True,
        "duration_years": 30,
        "renewable": True,
        "requires_pt": False,
        "restrictions": [
            "Apartment/condominium only",
            "Maximum 30% foreign ownership per building",
            "Minimum value restrictions may apply per region",
            "Bali minimum: IDR 5 billion for foreigners",
        ],
        "requirements": [
            "Valid KITAS or KITAP",
            "Developer must have Strata Title certification",
            "Notary deed",
            "BPHTB tax payment",
            "Management fee agreement",
        ],
    },
    PropertyRight.LEASEHOLD: {
        "foreigner_eligible": True,
        "duration_years": 25,
        "renewable": True,
        "requires_pt": False,
        "restrictions": [
            "No ownership transfer — lease agreement only",
            "Duration typically 25-30 years (negotiable)",
            "Must be notarized for legal protection",
        ],
        "requirements": [
            "Lease agreement (notarized)",
            "Passport copy",
            "No KITAS requirement for short-term leases",
            "Stamp duty",
        ],
    },
}


def _identify_property_right(state: GraphState) -> PropertyRight:
    """Determine property right type from entities and query."""
    entities = state.extracted_entities
    query_lower = state.query.lower()

    if "property_type" in entities:
        pt = str(entities["property_type"]).lower()
        if "hak pakai" in pt or "pakai" in pt:
            return PropertyRight.HAK_PAKAI
        if "hgb" in pt:
            return PropertyRight.HGB
        if "hak milik" in pt or "milik" in pt:
            return PropertyRight.HAK_MILIK
        if "strata" in pt or "apartment" in pt:
            return PropertyRight.STRATA_TITLE
        if "lease" in pt or "sewa" in pt or "rent" in pt:
            return PropertyRight.LEASEHOLD

    if "hak pakai" in query_lower:
        return PropertyRight.HAK_PAKAI
    if "hgb" in query_lower or "hak guna bangunan" in query_lower:
        return PropertyRight.HGB
    if "hak milik" in query_lower:
        return PropertyRight.HAK_MILIK
    if "strata" in query_lower or "apartment" in query_lower or "condo" in query_lower:
        return PropertyRight.STRATA_TITLE
    if "lease" in query_lower or "rent" in query_lower or "sewa" in query_lower:
        return PropertyRight.LEASEHOLD

    # Default — most common foreigner question
    return PropertyRight.HAK_PAKAI


def make_property_subgraph(services: Services):
    """Factory that creates the property subgraph node."""

    async def property_subgraph_node(state: GraphState) -> dict[str, Any]:
        """Execute the property acquisition subgraph."""
        logger.info("subgraph_property_start", query=state.query[:80])

        right_type = _identify_property_right(state)
        spec = PROPERTY_SPECS.get(right_type, {})

        # Query KG
        kg_entities: list[dict[str, Any]] = []
        kg_relationships: list[dict[str, Any]] = []

        try:
            kg_entities = await services.kg_store.get_entities(
                entity_ids=[f"property:{right_type.value}"],
            )
            if kg_entities:
                rels = await services.kg_store.get_relationships(
                    entity_id=f"property:{right_type.value}",
                )
                kg_relationships.extend(rels)
        except Exception as e:
            logger.warning("property_kg_query_failed", error=str(e))

        # Retrieve domain documents
        docs: list[RetrievedDocument] = []
        try:
            search_query = (
                f"{right_type.value} property Indonesia "
                f"foreigner ownership {state.query}"
            )
            docs = await services.vector_store.search_by_text(
                query=search_query,
                top_k=5,
            )
        except Exception as e:
            logger.warning("property_vector_search_failed", error=str(e))

        # Build domain context
        context_parts = [
            f"Property Right: {right_type.value.upper().replace('_', ' ')}",
        ]
        if spec:
            eligible = "Yes" if spec.get("foreigner_eligible") else "No"
            context_parts.append(f"Foreigner Eligible: {eligible}")
            dur = spec.get("duration_years", 0)
            context_parts.append(
                f"Duration: {'Permanent' if dur == 0 else f'{dur} years'}"
            )
            context_parts.append(
                f"Renewable: {'Yes' if spec.get('renewable') else 'No'}"
            )
            if spec.get("requires_pt"):
                context_parts.append("Requires PT company (not individual ownership)")
            context_parts.append("Restrictions:")
            for r in spec.get("restrictions", []):
                context_parts.append(f"  - {r}")
            context_parts.append("Requirements:")
            for r in spec.get("requirements", []):
                context_parts.append(f"  - {r}")

        domain_doc = RetrievedDocument(
            id=f"domain:property:{right_type.value}",
            content="\n".join(context_parts),
            score=0.95,
            source="domain",
            metadata={"property_right": right_type.value, "subgraph": "property"},
        )

        all_docs = [domain_doc] + docs

        logger.info(
            "subgraph_property_complete",
            right_type=right_type.value,
            doc_count=len(all_docs),
            kg_count=len(kg_entities),
        )

        return {
            "retrieved_documents": all_docs,
            "kg_entities": kg_entities,
            "kg_relationships": kg_relationships,
            "domain": right_type.value,
            "current_node": "subgraph_property",
        }

    return property_subgraph_node
