#!/usr/bin/env python3
"""
ZANTARA - Metadata Schema Generator

Crea schema metadata standardizzato per tutte le collezioni Qdrant
basato sull'analisi della struttura documenti esistente.
"""

import json
from pathlib import Path
from typing import Any

SCHEMA_OUTPUT = Path(__file__).parent.parent / "docs" / "qdrant_metadata_schema.json"


METADATA_SCHEMAS = {
    "bali_zero_pricing": {
        "description": "Service pricing information",
        "fields": {
            "service_name": {"type": "string", "required": True, "description": "Name of the service"},
            "service_type": {"type": "string", "required": True, "description": "Type (visa, company, tax, etc.)"},
            "price_usd": {"type": "number", "required": False, "description": "Price in USD"},
            "price_idr": {"type": "number", "required": False, "description": "Price in IDR"},
            "currency": {"type": "string", "required": False, "description": "Currency code"},
            "valid_from": {"type": "string", "required": False, "description": "Valid from date (ISO format)"},
            "valid_until": {"type": "string", "required": False, "description": "Valid until date (ISO format)"},
            "source": {"type": "string", "required": True, "description": "Source of pricing information"},
        },
    },
    "bali_zero_team": {
        "description": "Team member profiles",
        "fields": {
            "id": {"type": "string", "required": True, "description": "Unique team member ID"},
            "name": {"type": "string", "required": True, "description": "Full name"},
            "email": {"type": "string", "required": True, "description": "Email address"},
            "role": {"type": "string", "required": True, "description": "Job role"},
            "department": {"type": "string", "required": True, "description": "Department"},
            "team": {"type": "string", "required": True, "description": "Team name"},
            "languages": {"type": "array", "required": True, "description": "List of language codes"},
            "expertise_level": {"type": "string", "required": True, "description": "Expertise level"},
            "location": {"type": "string", "required": False, "description": "Location"},
            "emotional_preferences": {"type": "object", "required": False, "description": "Emotional preferences"},
        },
    },
    "visa_oracle": {
        "description": "Visa and immigration regulations",
        "fields": {
            "visa_type": {"type": "string", "required": True, "description": "Visa type code (e.g., C7, D1)"},
            "visa_category": {"type": "string", "required": False, "description": "Category (tourist, business, work)"},
            "entry_type": {"type": "string", "required": False, "description": "Single/Multiple entry"},
            "duration": {"type": "string", "required": False, "description": "Visa duration"},
            "fee_usd": {"type": "number", "required": False, "description": "Fee in USD"},
            "requirements": {"type": "array", "required": False, "description": "List of requirements"},
            "source_document": {"type": "string", "required": False, "description": "Source document name"},
            "last_updated": {"type": "string", "required": False, "description": "Last update date"},
        },
    },
    "kbli_unified": {
        "description": "Business classification codes (KBLI)",
        "fields": {
            "kbli_code": {"type": "string", "required": True, "description": "5-digit KBLI code"},
            "kbli_description": {"type": "string", "required": True, "description": "Business activity description"},
            "category": {"type": "string", "required": False, "description": "Business category"},
            "investment_minimum": {"type": "number", "required": False, "description": "Minimum investment (IDR)"},
            "risk_level": {"type": "string", "required": False, "description": "Risk level (Low/Medium/High)"},
            "required_licenses": {"type": "array", "required": False, "description": "Required licenses"},
            "source": {"type": "string", "required": False, "description": "Source document"},
        },
    },
    "tax_genius": {
        "description": "Indonesian tax regulations",
        "fields": {
            "tax_type": {"type": "string", "required": True, "description": "Type of tax"},
            "tax_rate": {"type": "number", "required": False, "description": "Tax rate percentage"},
            "tax_bracket": {"type": "object", "required": False, "description": "Tax bracket information"},
            "regulation_reference": {"type": "string", "required": False, "description": "Regulation reference"},
            "effective_date": {"type": "string", "required": False, "description": "Effective date"},
            "source_document": {"type": "string", "required": False, "description": "Source document"},
        },
    },
    "legal_unified": {
        "description": "Indonesian laws and regulations",
        "fields": {
            "law_id": {"type": "string", "required": True, "description": "Law identifier"},
            "law_title": {"type": "string", "required": True, "description": "Law title"},
            "pasal": {"type": "string", "required": False, "description": "Article number"},
            "status_vigensi": {"type": "string", "required": False, "description": "Status (berlaku/dicabut)"},
            "wilayah": {"type": "string", "required": False, "description": "Applicable region"},
            "year": {"type": "number", "required": False, "description": "Year of law"},
            "source": {"type": "string", "required": False, "description": "Source document"},
        },
    },
    "knowledge_base": {
        "description": "General knowledge base",
        "fields": {
            "title": {"type": "string", "required": True, "description": "Document title"},
            "category": {"type": "string", "required": False, "description": "Content category"},
            "tags": {"type": "array", "required": False, "description": "Content tags"},
            "source": {"type": "string", "required": False, "description": "Source"},
            "language": {"type": "string", "required": False, "description": "Language code"},
            "last_updated": {"type": "string", "required": False, "description": "Last update date"},
        },
    },
    "property_unified": {
        "description": "Property and real estate information",
        "fields": {
            "property_type": {"type": "string", "required": True, "description": "Type of property"},
            "location": {"type": "string", "required": True, "description": "Property location"},
            "price_range": {"type": "object", "required": False, "description": "Price range"},
            "area": {"type": "number", "required": False, "description": "Area in square meters"},
            "source": {"type": "string", "required": False, "description": "Source"},
        },
    },
}


def generate_schema_documentation():
    """Genera documentazione schema in formato Markdown"""
    md_content = """# Qdrant Metadata Schema Documentation

Questo documento definisce lo schema metadata standardizzato per tutte le collezioni Qdrant.

## Schema per Collezione

"""
    for collection_name, schema in METADATA_SCHEMAS.items():
        md_content += f"### {collection_name}\n\n"
        md_content += f"**Descrizione**: {schema['description']}\n\n"
        md_content += "**Campi**:\n\n"
        md_content += "| Campo | Tipo | Obbligatorio | Descrizione |\n"
        md_content += "|-------|------|--------------|-------------|\n"

        for field_name, field_def in schema["fields"].items():
            required = "✅" if field_def.get("required") else "❌"
            md_content += f"| `{field_name}` | {field_def['type']} | {required} | {field_def['description']} |\n"

        md_content += "\n"

    return md_content


def main():
    """Main entry point"""
    print("=" * 80)
    print("ZANTARA - Metadata Schema Generator")
    print("=" * 80)

    # Salva schema JSON
    schema_path = Path(__file__).parent.parent / "docs" / "qdrant_metadata_schema.json"
    schema_path.parent.mkdir(exist_ok=True)

    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(METADATA_SCHEMAS, f, indent=2, ensure_ascii=False)

    print(f"✅ Schema JSON salvato: {schema_path}")

    # Genera documentazione Markdown
    md_path = Path(__file__).parent.parent / "docs" / "QDRANT_METADATA_SCHEMA.md"
    md_content = generate_schema_documentation()

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"✅ Documentazione Markdown salvata: {md_path}")

    print("\n✅ Schema generato per 8 collezioni!")
    print(f"   - {len(METADATA_SCHEMAS)} schemi definiti")
    print(f"   - Totale campi: {sum(len(s['fields']) for s in METADATA_SCHEMAS.values())}")


if __name__ == "__main__":
    main()

