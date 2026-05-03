"""Company setup subgraph — PT PMA, PT PMDN, CV, Firma, etc.

Identifies the company type from extracted entities, queries KG for
KBLI eligibility and capital requirements, builds domain-specific
context for the reason node.
"""

from __future__ import annotations

from typing import Any

import structlog

from nuzantara_graph.services import Services
from nuzantara_schemas.domain.company import CompanyType
from nuzantara_schemas.state import GraphState, RetrievedDocument

logger = structlog.get_logger()

# Capital requirements (IDR) — Indonesian law
CAPITAL_REQUIREMENTS: dict[str, dict[str, Any]] = {
    CompanyType.PT_PMA: {
        "min_capital_idr": 10_000_000_000,
        "min_investment_usd": 1_100_000,
        "foreign_ownership_pct": 100.0,
        "timeline_days": 30,
        "requirements": [
            "Minimum authorized capital IDR 10 billion",
            "Minimum paid-up capital IDR 2.5 billion (25%)",
            "Investment plan approved by BKPM/OSS",
            "KBLI codes must allow foreign ownership",
            "Domicile letter required",
            "Deed of Establishment (Akta Pendirian) via notary",
        ],
    },
    CompanyType.PT_PMDN: {
        "min_capital_idr": 50_000_000,
        "foreign_ownership_pct": 0.0,
        "timeline_days": 14,
        "requirements": [
            "Minimum capital IDR 50 million",
            "Indonesian citizens/entities only",
            "Register via OSS (Online Single Submission)",
            "Deed of Establishment via notary",
            "NPWP (tax ID) required",
        ],
    },
    CompanyType.CV: {
        "min_capital_idr": 0,
        "foreign_ownership_pct": 0.0,
        "timeline_days": 7,
        "requirements": [
            "No minimum capital requirement",
            "Indonesian citizens only (no foreign partners)",
            "At least 2 partners (active + silent)",
            "Register via OSS",
        ],
    },
    CompanyType.FIRMA: {
        "min_capital_idr": 0,
        "foreign_ownership_pct": 0.0,
        "timeline_days": 7,
        "requirements": [
            "No minimum capital requirement",
            "Indonesian citizens only",
            "All partners have unlimited liability",
        ],
    },
}


def _identify_company_type(state: GraphState) -> CompanyType:
    """Determine company type from extracted entities and query context."""
    entities = state.extracted_entities
    query_lower = state.query.lower()

    # Explicit entity extraction
    if "company_type" in entities:
        ct = entities["company_type"]
        try:
            return CompanyType(ct)
        except ValueError:
            pass
        # String matching
        ct_lower = str(ct).lower()
        if "pma" in ct_lower:
            return CompanyType.PT_PMA
        if "pmdn" in ct_lower or "lokal" in ct_lower:
            return CompanyType.PT_PMDN
        if ct_lower == "cv":
            return CompanyType.CV

    # Query-based heuristics
    if "pma" in query_lower or "foreign" in query_lower or "asing" in query_lower:
        return CompanyType.PT_PMA
    if "pmdn" in query_lower or "lokal" in query_lower:
        return CompanyType.PT_PMDN
    if " cv " in query_lower or query_lower.startswith("cv "):
        return CompanyType.CV
    if "firma" in query_lower:
        return CompanyType.FIRMA
    if "koperasi" in query_lower:
        return CompanyType.KOPERASI
    if "yayasan" in query_lower or "foundation" in query_lower:
        return CompanyType.YAYASAN

    # Default for business_setup intent
    return CompanyType.PT_PMA


def make_company_subgraph(services: Services):
    """Factory that creates the company subgraph node."""

    async def company_subgraph_node(state: GraphState) -> dict[str, Any]:
        """Execute the company setup subgraph.

        1. Identify company type
        2. Query KG for KBLI eligibility
        3. Retrieve domain-specific documents
        4. Build structured context for reason node
        """
        logger.info("subgraph_company_start", query=state.query[:80])

        company_type = _identify_company_type(state)
        capital_info = CAPITAL_REQUIREMENTS.get(company_type, {})

        # Query KG for company-related entities
        kg_entities: list[dict[str, Any]] = []
        kg_relationships: list[dict[str, Any]] = []

        try:
            # Look up company type entity
            kg_entities = await services.kg_store.get_entities(
                entity_ids=[f"company:{company_type.value}"],
            )

            # Look up KBLI entities if codes provided
            kbli_codes = state.extracted_entities.get("kbli_codes", [])
            if isinstance(kbli_codes, str):
                kbli_codes = [kbli_codes]
            if kbli_codes:
                kbli_entities = await services.kg_store.get_entities(
                    entity_ids=[f"kbli:{code}" for code in kbli_codes],
                )
                kg_entities.extend(kbli_entities)

                # Check PMA eligibility via KG edges
                for entity in kbli_entities:
                    rels = await services.kg_store.get_relationships(
                        entity_id=entity.get("entity_id", ""),
                        relationship_type="REQUIRES",
                    )
                    kg_relationships.extend(rels)

        except Exception as e:
            logger.warning("company_kg_query_failed", error=str(e))

        # Retrieve domain-specific documents
        docs: list[RetrievedDocument] = []
        try:
            search_query = (
                f"{company_type.value} company setup Indonesia "
                f"requirements capital {state.query}"
            )
            docs = await services.vector_store.search_by_text(
                query=search_query,
                top_k=5,
            )
        except Exception as e:
            logger.warning("company_vector_search_failed", error=str(e))

        # Build domain context as a synthetic document
        context_parts = [
            f"Company Type: {company_type.value.upper()}",
        ]
        if capital_info:
            if capital_info.get("min_capital_idr"):
                context_parts.append(
                    f"Minimum Capital: IDR {capital_info['min_capital_idr']:,}"
                )
            if capital_info.get("min_investment_usd"):
                context_parts.append(
                    f"Minimum Investment: USD {capital_info['min_investment_usd']:,}"
                )
            if capital_info.get("foreign_ownership_pct") is not None:
                context_parts.append(
                    f"Foreign Ownership: up to {capital_info['foreign_ownership_pct']}%"
                )
            if capital_info.get("timeline_days"):
                context_parts.append(
                    f"Estimated Timeline: {capital_info['timeline_days']} days"
                )
            for req in capital_info.get("requirements", []):
                context_parts.append(f"- {req}")

        domain_doc = RetrievedDocument(
            id=f"domain:company:{company_type.value}",
            content="\n".join(context_parts),
            score=0.95,
            source="domain",
            metadata={
                "company_type": company_type.value,
                "subgraph": "company",
            },
        )

        all_docs = [domain_doc] + docs

        logger.info(
            "subgraph_company_complete",
            company_type=company_type.value,
            doc_count=len(all_docs),
            kg_count=len(kg_entities),
        )

        return {
            "retrieved_documents": all_docs,
            "kg_entities": kg_entities,
            "kg_relationships": kg_relationships,
            "domain": company_type.value,
            "current_node": "subgraph_company",
        }

    return company_subgraph_node
