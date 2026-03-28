"""
Lightweight entity extraction for Agentic RAG.

This is intentionally heuristic-first to keep latency low and avoid unnecessary
LLM calls. It provides optional hooks for future LLM-backed extraction.
"""

from __future__ import annotations

import re
from typing import Any


class EntityExtractionService:
    """
    Service for extracting entities from user queries.

    Extracts and classifies:
    - Visa types (KITAS, KITAP, VITAS, etc.)
    - Tax concepts (NPWP, PPh, PPN, etc.)
    - Property terms (Hak Pakai, HGB, etc.)
    - KBLI codes (business classification)
    - Company types (PT PMA, etc.)
    - Nationalities and budget

    Also determines the primary domain of the query to enable proper routing.
    """

    # Domain constants for routing
    DOMAIN_VISA = "visa"
    DOMAIN_TAX = "tax"
    DOMAIN_PROPERTY = "property"
    DOMAIN_KBLI = "kbli"
    DOMAIN_COMPANY = "company"
    DOMAIN_GENERAL = "general"

    def __init__(self, llm_gateway: Any | None = None) -> None:
        self._llm_gateway = llm_gateway

    async def extract_entities(self, query: str) -> dict[str, Any]:
        """
        Extract entities and determine domain from query.

        Args:
            query: User query string

        Returns:
            Dict with extracted entities and domain classification
            {
                "visa_type": "KITAS",
                "nationality": "Italy",
                "domain": "visa",
                "primary_entity": "KITAS",
                "entity_types": ["visa"],
                ...
            }
        """
        if not query:
            return {"domain": self.DOMAIN_GENERAL, "entity_types": []}

        query_lower = query.lower()
        query_upper = query.upper()

        entities: dict[str, Any] = {
            "domain": self.DOMAIN_GENERAL,
            "entity_types": [],
            "primary_entity": None,
        }

        # Extract visa entities
        visa_result = self._extract_visa_entities(query_lower, query_upper)
        if visa_result:
            entities.update(visa_result)
            entities["entity_types"].append("visa")
            if not entities["primary_entity"]:
                entities["primary_entity"] = entities.get("visa_type")

        # Extract tax entities
        tax_result = self._extract_tax_entities(query_lower, query_upper)
        if tax_result:
            entities.update(tax_result)
            entities["entity_types"].append("tax")
            if not entities["primary_entity"]:
                entities["primary_entity"] = tax_result.get("tax_concept")

        # Extract property entities
        property_result = self._extract_property_entities(query_lower, query_upper)
        if property_result:
            entities.update(property_result)
            entities["entity_types"].append("property")
            if not entities["primary_entity"]:
                entities["primary_entity"] = property_result.get("property_type")

        # Extract KBLI codes
        kbli_result = self._extract_kbli_entities(query_upper)
        if kbli_result:
            entities.update(kbli_result)
            entities["entity_types"].append("kbli")
            if not entities["primary_entity"]:
                entities["primary_entity"] = kbli_result.get("kbli_code")

        # Extract company entities
        company_result = self._extract_company_entities(query_lower, query_upper)
        if company_result:
            entities.update(company_result)
            entities["entity_types"].append("company")
            if not entities["primary_entity"]:
                entities["primary_entity"] = company_result.get("company_type")

        # Extract nationality
        nationality = self._extract_nationality(query_lower)
        if nationality:
            entities["nationality"] = nationality

        # Extract budget
        budget = self._extract_budget(query_lower)
        if budget:
            entities["budget"] = budget

        # Determine primary domain based on entity types and query intent
        entities["domain"] = self._determine_domain(query_lower, entities)

        return entities

    def _extract_visa_entities(self, query_lower: str, query_upper: str) -> dict[str, Any] | None:
        """Extract visa-related entities."""
        visa_codes = re.findall(r"\b(e\d{2}[a-z]?)\b", query_lower)
        visa_type = None

        if visa_codes:
            visa_type = visa_codes[0].upper()
        elif "kitas" in query_lower:
            visa_type = "KITAS"
        elif "kitap" in query_lower:
            visa_type = "KITAP"
        elif "vitas" in query_lower:
            visa_type = "VITAS"
        elif "voa" in query_lower or "visa on arrival" in query_lower:
            visa_type = "VOA"
        elif "rptka" in query_lower:
            visa_type = "RPTKA"
        elif "imta" in query_lower:
            visa_type = "IMTA"
        elif re.search(r"\b(visa|immigration|stay permit|izin tinggal)\b", query_lower):
            visa_type = "VISA_GENERAL"

        if visa_type:
            return {"visa_type": visa_type}
        return None

    def _extract_tax_entities(self, query_lower: str, query_upper: str) -> dict[str, Any] | None:
        """Extract tax-related entities."""
        tax_concept = None
        tax_code = None

        # NPWP - Tax ID
        if "npwp" in query_lower:
            tax_concept = "NPWP"
            tax_code = "npwp"
        # PPh - Income Tax
        elif re.search(r"\bpph\s*(21|23|25|29|pasal)?\b", query_lower):
            match = re.search(r"\bpph\s*(21|23|25|29|pasal)?\b", query_lower)
            tax_concept = "PPh"
            tax_code = f"pph_{match.group(1)}" if match and match.group(1) else "pph"
        # PPN - VAT
        elif "ppn" in query_lower or "vat" in query_lower or "pajak pertambahan" in query_lower:
            tax_concept = "PPN"
            tax_code = "ppn"
        # PBB - Land and Building Tax
        elif "pbb" in query_lower:
            tax_concept = "PBB"
            tax_code = "pbb"
        # General tax terms
        elif re.search(r"\b(pajak|tax|tasse|fiscal)\b", query_lower):
            tax_concept = "TAX_GENERAL"
            tax_code = "tax"

        if tax_concept:
            return {"tax_concept": tax_concept, "tax_code": tax_code}
        return None

    def _extract_property_entities(
        self, query_lower: str, query_upper: str
    ) -> dict[str, Any] | None:
        """Extract property-related entities."""
        property_type = None

        # Hak Pakai - Right to Use
        if "hak pakai" in query_lower:
            property_type = "HAK_PAKAI"
        # HGB - Right to Build
        elif "hgb" in query_lower or "hak guna bangunan" in query_lower:
            property_type = "HGB"
        # Hak Milik - Ownership (for context, though foreigners can't own)
        elif "hak milik" in query_lower:
            property_type = "HAK_MILIK"
        # Lease/Sewa
        elif re.search(r"\b(sewa|lease|hak sewa)\b", query_lower):
            property_type = "HAK_SEWA"
        # Villa/Property general
        elif re.search(r"\b(villa|property|real estate|properti|tanah|land)\b", query_lower):
            property_type = "PROPERTY_GENERAL"

        if property_type:
            return {"property_type": property_type}
        return None

    def _extract_kbli_entities(self, query_upper: str) -> dict[str, Any] | None:
        """Extract KBLI (business classification) codes."""
        # Match KBLI codes: 5 digits
        kbli_match = re.search(r"\b(\d{5})\b", query_upper)
        if kbli_match:
            code = kbli_match.group(1)
            # Validate it's a valid KBLI code range (typically 01000-99999)
            if code.isdigit() and 1000 <= int(code) <= 99999:
                return {"kbli_code": code, "kbli_name": None}
        return None

    def _extract_company_entities(
        self, query_lower: str, query_upper: str
    ) -> dict[str, Any] | None:
        """Extract company-related entities."""
        company_type = None

        if "pt pma" in query_lower:
            company_type = "PT_PMA"
        elif "pt pmdn" in query_lower:
            company_type = "PT_PMDN"
        elif "pt perorangan" in query_lower:
            company_type = "PT_PERORANGAN"
        elif re.search(r"\b(cv|firma|koperasi|yayasan)\b", query_lower):
            match = re.search(r"\b(cv|firma|koperasi|yayasan)\b", query_lower)
            company_type = match.group(1).upper() if match else "COMPANY_OTHER"
        elif "nib" in query_lower:
            company_type = "NIB"
        elif re.search(r"\b(pt|company|perusahaan|azienda)\b", query_lower):
            company_type = "COMPANY_GENERAL"

        if company_type:
            return {"company_type": company_type}
        return None

    def _extract_nationality(self, query_lower: str) -> str | None:
        """Extract nationality from query."""
        nationality_map = {
            "italy": "Italy",
            "italian": "Italy",
            "italiano": "Italy",
            "italiana": "Italy",
            "ukraine": "Ukraine",
            "ukrainian": "Ukraine",
            "ucraina": "Ukraine",
            "russia": "Russia",
            "russian": "Russia",
            "russo": "Russia",
            "usa": "USA",
            "american": "USA",
            "united states": "USA",
            "australia": "Australia",
            "australian": "Australia",
            "germany": "Germany",
            "german": "Germany",
            "germania": "Germany",
            "france": "France",
            "french": "France",
            "francia": "France",
            "netherlands": "Netherlands",
            "dutch": "Netherlands",
            "singapore": "Singapore",
            "singaporean": "Singapore",
            "malaysia": "Malaysia",
            "malaysian": "Malaysia",
            "china": "China",
            "chinese": "China",
            "india": "India",
            "indian": "India",
        }

        for marker, normalized in nationality_map.items():
            if marker in query_lower:
                return normalized
        return None

    def _extract_budget(self, query_lower: str) -> str | None:
        """Extract budget from query."""
        budget_match = re.search(
            r"(?P<cur>\\\$|usd|idr|rp)\\s*(?P<num>\\d{1,3}(?:[\\.,]\\d{3})*(?:[\\.,]\\d+)?)\\s*(?P<unit>k|m|million)?",
            query_lower,
        )
        if budget_match:
            return budget_match.group(0).strip()
        return None

    def _determine_domain(self, query_lower: str, entities: dict[str, Any]) -> str:
        """
        Determine the primary domain of the query.

        Priority:
        1. Explicit domain keywords in query
        2. Entity types detected
        3. Query patterns
        """
        entity_types = entities.get("entity_types", [])

        # Check for visa domain
        visa_keywords = [
            "kitas",
            "kitap",
            "vitas",
            "visa",
            "work permit",
            "rptka",
            "imta",
            "immigration",
            "imigrasi",
            "stay permit",
            "izin tinggal",
            "foreign worker",
            "tenaga kerja asing",
            "tka",
            "e-visa",
            "evisa",
            "molina",
        ]
        if any(kw in query_lower for kw in visa_keywords):
            return self.DOMAIN_VISA

        # Check for tax domain
        tax_keywords = [
            "npwp",
            "pph",
            "ppn",
            "pbb",
            "tax",
            "pajak",
            "tasse",
            "fiscal",
            "vat",
            "income tax",
            "corporate tax",
            "withholding tax",
            "spt",
            "faktur pajak",
            "tax reporting",
            "laporan pajak",
        ]
        if any(kw in query_lower for kw in tax_keywords):
            return self.DOMAIN_TAX

        # Check for property domain
        property_keywords = [
            "hak pakai",
            "hgb",
            "hak milik",
            "hak guna bangunan",
            "property",
            "villa",
            "real estate",
            "land",
            "tanah",
            "sewa",
            "lease",
            "sertifikat",
            "certificate",
            "hak sewa",
            "bangunan",
        ]
        if any(kw in query_lower for kw in property_keywords):
            return self.DOMAIN_PROPERTY

        # Check for KBLI domain
        kbli_keywords = ["kbli", "business code", "kode usaha", "classification"]
        if any(kw in query_lower for kw in kbli_keywords):
            return self.DOMAIN_KBLI

        # Check for company domain
        company_keywords = ["pt pma", "company setup", "establish company", "business setup"]
        if any(kw in query_lower for kw in company_keywords):
            return self.DOMAIN_COMPANY

        # Fall back to entity types if no keywords matched
        if "visa" in entity_types:
            return self.DOMAIN_VISA
        if "tax" in entity_types:
            return self.DOMAIN_TAX
        if "property" in entity_types:
            return self.DOMAIN_PROPERTY
        if "kbli" in entity_types:
            return self.DOMAIN_KBLI
        if "company" in entity_types:
            return self.DOMAIN_COMPANY

        return self.DOMAIN_GENERAL

    def is_non_kbli_domain(self, query: str, entities: dict[str, Any]) -> bool:
        """
        Check if query is clearly NOT a KBLI query.

        Returns True for visa, tax, or property queries that should
        NOT be matched against KBLI codes.
        """
        domain = entities.get("domain", self.DOMAIN_GENERAL)
        return domain in [self.DOMAIN_VISA, self.DOMAIN_TAX, self.DOMAIN_PROPERTY]
