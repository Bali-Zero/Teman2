"""Tax compliance subgraph — PPh, PPN, BPHTB, PBB, etc.

Identifies applicable taxes based on entity type, retrieves rates
and brackets from KG, builds tax compliance workflow context.
"""

from __future__ import annotations

from typing import Any

import structlog

from nuzantara_graph.services import Services
from nuzantara_schemas.domain.tax import TaxType
from nuzantara_schemas.state import GraphState, RetrievedDocument

logger = structlog.get_logger()

# Tax specifications — Indonesian tax law (DJP)
TAX_SPECS: dict[str, dict[str, Any]] = {
    TaxType.PPH_21: {
        "name": "PPh 21 — Employee Withholding Tax",
        "rate_pct": None,  # Progressive
        "brackets": [
            {"min_idr": 0, "max_idr": 60_000_000, "rate_pct": 5.0},
            {"min_idr": 60_000_000, "max_idr": 250_000_000, "rate_pct": 15.0},
            {"min_idr": 250_000_000, "max_idr": 500_000_000, "rate_pct": 25.0},
            {"min_idr": 500_000_000, "max_idr": 5_000_000_000, "rate_pct": 30.0},
            {"min_idr": 5_000_000_000, "max_idr": None, "rate_pct": 35.0},
        ],
        "filing_frequency": "monthly",
        "filing_deadline": "20th of following month",
        "applicable_entities": ["pt_pma", "pt_pmdn", "cv"],
        "description": (
            "Progressive income tax withheld from employee salaries. "
            "Employer calculates, withholds, and remits monthly."
        ),
    },
    TaxType.PPH_23: {
        "name": "PPh 23 — Service/Rent Withholding Tax",
        "rate_pct": 2.0,
        "filing_frequency": "monthly",
        "filing_deadline": "20th of following month",
        "applicable_entities": ["pt_pma", "pt_pmdn"],
        "description": (
            "2% withholding on payments for services, rent, royalties, "
            "and certain other income to domestic recipients."
        ),
    },
    TaxType.PPH_25: {
        "name": "PPh 25 — Corporate Estimated Tax",
        "rate_pct": 22.0,
        "filing_frequency": "monthly",
        "filing_deadline": "15th of following month",
        "applicable_entities": ["pt_pma", "pt_pmdn"],
        "description": (
            "22% corporate income tax on net profit, divided into 12 monthly "
            "installments based on previous year's tax liability."
        ),
    },
    TaxType.PPH_FINAL: {
        "name": "PPh Final — Final Withholding Tax",
        "rate_pct": 0.5,
        "filing_frequency": "monthly",
        "applicable_entities": ["cv", "perorangan"],
        "description": (
            "0.5% final tax on gross revenue for MSMEs with annual revenue "
            "below IDR 4.8 billion. Simplified regime (PP 23/2018 → PP 55/2022)."
        ),
    },
    TaxType.PPN: {
        "name": "PPN — Value Added Tax (VAT)",
        "rate_pct": 11.0,
        "filing_frequency": "monthly",
        "filing_deadline": "End of following month",
        "applicable_entities": ["pt_pma", "pt_pmdn", "cv"],
        "description": (
            "11% VAT on goods and services. Mandatory PKP registration "
            "when annual revenue exceeds IDR 4.8 billion. "
            "12% only for luxury goods (PPnBM)."
        ),
        "threshold_idr": 4_800_000_000,
    },
    TaxType.BPHTB: {
        "name": "BPHTB — Property Transaction Tax",
        "rate_pct": 5.0,
        "filing_frequency": "one-time",
        "applicable_entities": ["all"],
        "description": (
            "5% tax on property transactions (purchase/transfer). "
            "Based on NJOP or transaction value, whichever is higher. "
            "Tax-free threshold (NPOPTKP) varies by region."
        ),
    },
    TaxType.PBB: {
        "name": "PBB — Annual Property Tax",
        "rate_pct": 0.3,
        "filing_frequency": "annual",
        "applicable_entities": ["all"],
        "description": (
            "Annual property tax based on NJOP (government assessed value). "
            "Rate varies 0.1-0.3% depending on municipality. "
            "Due by August 31 each year."
        ),
    },
}


def _identify_tax_types(state: GraphState) -> list[str]:
    """Determine which taxes are relevant from entities and query."""
    entities = state.extracted_entities
    query_lower = state.query.lower()
    result: list[str] = []

    # Explicit entity
    if "tax_type" in entities:
        tt = str(entities["tax_type"]).lower()
        for tax_type in TaxType:
            if tax_type.value.replace("_", " ") in tt or tax_type.value in tt:
                result.append(tax_type.value)

    # Query heuristics
    tax_keywords = {
        TaxType.PPH_21: ["pph 21", "pph21", "employee tax", "withholding salary", "pajak karyawan"],
        TaxType.PPH_23: ["pph 23", "pph23", "service tax", "withholding service"],
        TaxType.PPH_25: ["pph 25", "pph25", "corporate tax", "pajak badan"],
        TaxType.PPH_FINAL: ["pph final", "final tax", "umkm tax", "0.5%"],
        TaxType.PPN: ["ppn", "vat", "value added", "pajak pertambahan"],
        TaxType.BPHTB: ["bphtb", "property transaction tax", "pajak properti"],
        TaxType.PBB: ["pbb", "property tax annual", "pajak bumi"],
    }

    for tax_type, keywords in tax_keywords.items():
        if any(kw in query_lower for kw in keywords):
            if tax_type.value not in result:
                result.append(tax_type.value)

    # If no specific tax found, return common set based on entity type
    if not result:
        company_type = entities.get("company_type", "")
        if "pma" in str(company_type).lower():
            result = [TaxType.PPH_25, TaxType.PPH_21, TaxType.PPN]
        else:
            result = [TaxType.PPH_25, TaxType.PPH_21, TaxType.PPN]

    return result


def make_tax_subgraph(services: Services):
    """Factory that creates the tax subgraph node."""

    async def tax_subgraph_node(state: GraphState) -> dict[str, Any]:
        """Execute the tax compliance subgraph."""
        logger.info("subgraph_tax_start", query=state.query[:80])

        tax_types = _identify_tax_types(state)

        # Query KG
        kg_entities: list[dict[str, Any]] = []
        kg_relationships: list[dict[str, Any]] = []

        try:
            entity_ids = [f"tax:{tt}" for tt in tax_types]
            kg_entities = await services.kg_store.get_entities(
                entity_ids=entity_ids,
            )
            for entity in kg_entities:
                rels = await services.kg_store.get_relationships(
                    entity_id=entity.get("entity_id", ""),
                )
                kg_relationships.extend(rels)
        except Exception as e:
            logger.warning("tax_kg_query_failed", error=str(e))

        # Retrieve domain documents
        docs: list[RetrievedDocument] = []
        try:
            tax_names = " ".join(tax_types)
            search_query = (
                f"Indonesia tax {tax_names} compliance "
                f"requirements filing {state.query}"
            )
            docs = await services.vector_store.search_by_text(
                query=search_query,
                top_k=5,
            )
        except Exception as e:
            logger.warning("tax_vector_search_failed", error=str(e))

        # Build domain context — one section per relevant tax
        context_parts = ["Tax Compliance Overview:"]

        for tt in tax_types:
            spec = TAX_SPECS.get(tt, {})
            if not spec:
                continue
            context_parts.append(f"\n--- {spec.get('name', tt.upper())} ---")
            context_parts.append(spec.get("description", ""))
            if spec.get("rate_pct") is not None:
                context_parts.append(f"Rate: {spec['rate_pct']}%")
            if spec.get("brackets"):
                context_parts.append("Progressive brackets:")
                for b in spec["brackets"]:
                    max_str = f"IDR {b['max_idr']:,}" if b["max_idr"] else "above"
                    context_parts.append(
                        f"  IDR {b['min_idr']:,} – {max_str}: {b['rate_pct']}%"
                    )
            if spec.get("filing_frequency"):
                context_parts.append(f"Filing: {spec['filing_frequency']}")
            if spec.get("filing_deadline"):
                context_parts.append(f"Deadline: {spec['filing_deadline']}")
            if spec.get("threshold_idr"):
                context_parts.append(
                    f"VAT Threshold: IDR {spec['threshold_idr']:,} annual revenue"
                )

        domain_doc = RetrievedDocument(
            id=f"domain:tax:{'+'.join(tax_types)}",
            content="\n".join(context_parts),
            score=0.95,
            source="domain",
            metadata={"tax_types": tax_types, "subgraph": "tax"},
        )

        all_docs = [domain_doc] + docs

        logger.info(
            "subgraph_tax_complete",
            tax_types=tax_types,
            doc_count=len(all_docs),
            kg_count=len(kg_entities),
        )

        return {
            "retrieved_documents": all_docs,
            "kg_entities": kg_entities,
            "kg_relationships": kg_relationships,
            "domain": "+".join(tax_types),
            "current_node": "subgraph_tax",
        }

    return tax_subgraph_node
