"""Visa/immigration subgraph — KITAS, KITAP, B211A, VOA, etc.

Identifies the visa type from extracted entities, checks RPTKA/work permit
requirements, retrieves visa-specific documents and costs.
"""

from __future__ import annotations

from typing import Any

import structlog

from nuzantara_graph.services import Services
from nuzantara_schemas.domain.visa import VisaType
from nuzantara_schemas.state import GraphState, RetrievedDocument

logger = structlog.get_logger()

# Visa specifications — Indonesian immigration law
VISA_SPECS: dict[str, dict[str, Any]] = {
    VisaType.KITAS: {
        "duration_months": 12,
        "extendable": True,
        "sponsor_required": True,
        "work_permit_included": True,
        "costs_usd": {"pnbp": 250, "telex": 100, "kitas_card": 50},
        "processing_days": 30,
        "requirements": [
            "Sponsoring company (PT PMA or PT PMDN)",
            "RPTKA (foreign worker utilization plan) approved by Ministry of Labor",
            "IMTA (work permit) via SPKP system",
            "E-Visa application via imigrasi.go.id",
            "Valid passport (min. 18 months validity)",
            "Photo 4x6cm red background",
            "CV/resume for position",
            "Company sponsorship letter",
        ],
    },
    VisaType.KITAP: {
        "duration_months": 60,
        "extendable": True,
        "sponsor_required": True,
        "work_permit_included": False,
        "costs_usd": {"pnbp": 570, "telex": 100, "kitap_card": 50},
        "processing_days": 45,
        "requirements": [
            "Held KITAS for minimum 3 consecutive years",
            "OR married to Indonesian citizen (2 years)",
            "OR retired (55+ with pension proof)",
            "Domicile in Indonesia",
            "Police clearance (SKCK)",
            "Financial proof (bank statements)",
        ],
    },
    VisaType.B211A: {
        "duration_months": 2,
        "extendable": True,
        "max_extensions": 4,
        "sponsor_required": True,
        "work_permit_included": False,
        "costs_usd": {"visa_fee": 120, "extension": 60},
        "processing_days": 5,
        "requirements": [
            "Sponsor (agent or individual Indonesian citizen)",
            "Valid passport (min. 6 months validity)",
            "Return/onward ticket",
            "Proof of funds",
            "Cannot work (social/business visit only)",
        ],
    },
    VisaType.VOA: {
        "duration_months": 1,
        "extendable": True,
        "max_extensions": 1,
        "sponsor_required": False,
        "work_permit_included": False,
        "costs_usd": {"arrival": 35, "extension": 35},
        "processing_days": 0,
        "requirements": [
            "Available at major airports and seaports",
            "Eligible passport holders (90+ countries)",
            "Return/onward ticket required",
            "Valid passport (min. 6 months validity)",
            "Cannot work",
            "Extension to 60 days at immigration office",
        ],
    },
    VisaType.E_VISA: {
        "duration_months": 2,
        "extendable": False,
        "sponsor_required": True,
        "work_permit_included": False,
        "costs_usd": {"visa_fee": 120},
        "processing_days": 3,
        "requirements": [
            "Apply online via molina.imigrasi.go.id",
            "Sponsor required",
            "Must convert to KITAS within 60 days if staying",
        ],
    },
    VisaType.SECOND_HOME: {
        "duration_months": 60,
        "extendable": True,
        "sponsor_required": False,
        "work_permit_included": False,
        "costs_usd": {"visa_fee": 300},
        "processing_days": 10,
        "requirements": [
            "Proof of funds: USD 130,000 in Indonesian bank",
            "OR property ownership in Indonesia",
            "OR proof of retirement income",
            "Health insurance valid in Indonesia",
            "No criminal record",
            "Cannot work (investment/retirement only)",
        ],
    },
}


def _identify_visa_type(state: GraphState) -> VisaType:
    """Determine visa type from extracted entities and query context."""
    entities = state.extracted_entities
    query_lower = state.query.lower()

    # Explicit entity
    if "visa_type" in entities:
        vt = str(entities["visa_type"]).lower()
        if "kitas" in vt:
            return VisaType.KITAS
        if "kitap" in vt:
            return VisaType.KITAP
        if "b211" in vt:
            return VisaType.B211A
        if "voa" in vt or "arrival" in vt:
            return VisaType.VOA
        if "second home" in vt:
            return VisaType.SECOND_HOME

    # Query heuristics
    if "kitas" in query_lower or "work permit" in query_lower or "izin kerja" in query_lower:
        return VisaType.KITAS
    if "kitap" in query_lower or "permanent" in query_lower:
        return VisaType.KITAP
    if "b211" in query_lower or "social" in query_lower:
        return VisaType.B211A
    if "voa" in query_lower or "visa on arrival" in query_lower or "tourist" in query_lower:
        return VisaType.VOA
    if "second home" in query_lower or "retire" in query_lower or "pensiun" in query_lower:
        return VisaType.SECOND_HOME

    # Default for visa intent — most common question
    return VisaType.KITAS


def make_visa_subgraph(services: Services):
    """Factory that creates the visa subgraph node."""

    async def visa_subgraph_node(state: GraphState) -> dict[str, Any]:
        """Execute the visa/immigration subgraph."""
        logger.info("subgraph_visa_start", query=state.query[:80])

        visa_type = _identify_visa_type(state)
        spec = VISA_SPECS.get(visa_type, {})

        # Query KG for visa-related entities
        kg_entities: list[dict[str, Any]] = []
        kg_relationships: list[dict[str, Any]] = []

        try:
            kg_entities = await services.kg_store.get_entities(
                entity_ids=[f"visa:{visa_type.value}"],
            )
            # Check for RPTKA requirement edges
            if spec.get("work_permit_included"):
                rptka_rels = await services.kg_store.get_relationships(
                    entity_id=f"visa:{visa_type.value}",
                    relationship_type="REQUIRES",
                )
                kg_relationships.extend(rptka_rels)
        except Exception as e:
            logger.warning("visa_kg_query_failed", error=str(e))

        # Retrieve domain documents
        docs: list[RetrievedDocument] = []
        try:
            search_query = (
                f"{visa_type.value} visa Indonesia requirements "
                f"processing {state.query}"
            )
            docs = await services.vector_store.search_by_text(
                query=search_query,
                top_k=5,
            )
        except Exception as e:
            logger.warning("visa_vector_search_failed", error=str(e))

        # Build domain context document
        context_parts = [
            f"Visa Type: {visa_type.value.upper()}",
        ]
        if spec:
            context_parts.append(f"Duration: {spec.get('duration_months', '?')} months")
            context_parts.append(f"Extendable: {'Yes' if spec.get('extendable') else 'No'}")
            context_parts.append(
                f"Sponsor Required: {'Yes' if spec.get('sponsor_required') else 'No'}"
            )
            context_parts.append(
                f"Work Permit: {'Included' if spec.get('work_permit_included') else 'Not included'}"
            )
            if spec.get("costs_usd"):
                total = sum(spec["costs_usd"].values())
                cost_items = ", ".join(
                    f"{k}: USD {v}" for k, v in spec["costs_usd"].items()
                )
                context_parts.append(f"Costs: {cost_items} (total ~USD {total})")
            context_parts.append(f"Processing: ~{spec.get('processing_days', '?')} days")
            context_parts.append("Requirements:")
            for req in spec.get("requirements", []):
                context_parts.append(f"  - {req}")

        domain_doc = RetrievedDocument(
            id=f"domain:visa:{visa_type.value}",
            content="\n".join(context_parts),
            score=0.95,
            source="domain",
            metadata={"visa_type": visa_type.value, "subgraph": "visa"},
        )

        all_docs = [domain_doc] + docs

        logger.info(
            "subgraph_visa_complete",
            visa_type=visa_type.value,
            doc_count=len(all_docs),
            kg_count=len(kg_entities),
        )

        return {
            "retrieved_documents": all_docs,
            "kg_entities": kg_entities,
            "kg_relationships": kg_relationships,
            "domain": visa_type.value,
            "current_node": "subgraph_visa",
        }

    return visa_subgraph_node
