#!/usr/bin/env python3
"""
Seed ALL visa types from Qdrant to PostgreSQL visa_types table.
Uses Bali Zero official prices where available, "Contact for quote" otherwise.

Run: fly ssh console -a nuzantara-rag -C "python /app/backend/migrations/seed_all_visas_from_qdrant.py"
"""

import asyncio
import json
import os

import asyncpg
import httpx

# Bali Zero Official Prices 2025
BALI_ZERO_PRICES = {
    # Single Entry Visas (C series)
    "C1": {"price": "IDR 2,300,000", "duration": "60 days", "processing": "7-10 days"},
    "C2": {"price": "IDR 3,600,000", "duration": "60 days", "processing": "7-10 days"},
    "C7A": {"price": "IDR 4,500,000", "duration": "30 days", "processing": "Including Urgent"},
    "C7B": {"price": "IDR 4,500,000", "duration": "30 days", "processing": "Including Urgent"},
    "C18": {"price": "IDR 5,500,000", "duration": "90 days", "processing": "Work trial"},
    "C22A": {"price": "IDR 4,800,000", "duration": "60 days", "processing": "Academic internship"},
    "C22B": {"price": "IDR 4,800,000", "duration": "60 days", "processing": "Skills development"},

    # Multiple Entry Visas (D series)
    "D12": {"price": "IDR 7,500,000 (1Y) / IDR 10,000,000 (2Y)", "duration": "1-2 years", "processing": "7-10 days"},

    # KITAS (E series)
    "E23": {"price": "IDR 34,500,000 (offshore) / IDR 36,000,000 (onshore)", "duration": "1 year", "processing": "4-6 weeks (RPTKA+IMTA)"},
    "E26": {"price": "IDR 11,000,000 (1Y) / IDR 15,000,000 (2Y)", "duration": "1-2 years", "processing": "7-10 days"},
    "E28A": {"price": "IDR 17,000,000 (offshore) / IDR 19,000,000 (onshore)", "duration": "2 years", "processing": "7-10 days"},
    "E31": {"price": "IDR 11,000,000 (1Y) / IDR 15,000,000 (2Y)", "duration": "1-2 years", "processing": "7-10 days"},
    "E33E": {"price": "IDR 14,000,000 (offshore) / IDR 16,000,000 (onshore)", "duration": "1-5 years", "processing": "7-10 days"},
    "E33F": {"price": "IDR 14,000,000 (offshore) / IDR 16,000,000 (onshore)", "duration": "1 year", "processing": "7-10 days"},
    "E33G": {"price": "IDR 13,000,000 (offshore) / IDR 14,000,000 (onshore)", "duration": "1 year", "processing": "7-10 days"},

    # Freelance (special E23)
    "E23_FREELANCE": {"price": "IDR 25,800,000 (offshore) / IDR 27,500,000 (onshore)", "duration": "6 months", "processing": "4-6 weeks"},

    # KITAP
    "KITAP": {"price": "IDR 55,000,000 (Investor) / IDR 33,000,000 (Dependent)", "duration": "5 years", "processing": "Expedited available"},

    # Auxiliary Services (not visas but shown)
    "EPO": {"price": "IDR 700,000", "duration": "Exit permit", "processing": "1-3 days"},
    "ERP": {"price": "IDR 800,000", "duration": "Re-entry permit", "processing": "1-3 days"},
}

# Category mapping based on visa code prefix
def get_category(code: str) -> str:
    if code.startswith("A"):
        return "Visa Free"
    elif code.startswith("B") or code.startswith("F"):
        return "VOA"
    elif code.startswith("C"):
        return "Visit"
    elif code.startswith("D"):
        return "Visit"
    elif code.startswith("E"):
        return "KITAS"
    elif code == "KITAP":
        return "KITAP"
    return "Other"


async def fetch_visas_from_qdrant() -> list[dict]:
    """Fetch all visa documents from Qdrant."""
    qdrant_url = os.environ.get("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
    qdrant_api_key = os.environ.get("QDRANT_API_KEY", "")

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{qdrant_url}/collections/visa_oracle/points/scroll",
            headers={"api-key": qdrant_api_key, "Content-Type": "application/json"},
            json={"limit": 200, "with_payload": True, "with_vector": False}
        )

    points = resp.json().get("result", {}).get("points", [])

    # Group by visa code, take best data for each
    visas_by_code = {}
    for point in points:
        payload = point.get("payload", {})
        code = payload.get("visa_code") or payload.get("metadata", {}).get("code")
        if not code or code == "IMIGRASI":
            continue

        # Extract data
        name = payload.get("title") or payload.get("name") or payload.get("metadata", {}).get("name") or f"Visa {code}"
        content = payload.get("content", "")

        # Parse requirements and benefits from content
        requirements = []
        benefits = []

        if "Persyaratan:" in content:
            req_section = content.split("Persyaratan:")[1].split("\n\n")[0] if "Persyaratan:" in content else ""
            requirements = [r.strip().lstrip("- ") for r in req_section.split("\n") if r.strip() and r.strip() != "-"][:5]

        if not visas_by_code.get(code) or len(content) > len(visas_by_code[code].get("content", "")):
            visas_by_code[code] = {
                "code": code,
                "name": name,
                "content": content,
                "requirements": requirements,
                "benefits": benefits,
            }

    return list(visas_by_code.values())


async def seed_visas():
    """Seed all visas to PostgreSQL."""
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    try:
        # Fetch from Qdrant
        visas = await fetch_visas_from_qdrant()
        print(f"Fetched {len(visas)} unique visa codes from Qdrant")

        # Clear existing
        await conn.execute("DELETE FROM visa_types")
        print("Cleared visa_types table")

        # Insert each visa
        for visa in sorted(visas, key=lambda x: x["code"]):
            code = visa["code"]
            category = get_category(code)

            # Get Bali Zero price if available
            price_info = BALI_ZERO_PRICES.get(code, {})
            cost_visa = price_info.get("price", "Contact for quote")
            duration = price_info.get("duration", "Varies")
            processing = price_info.get("processing", "7-10 days")

            # Clean up name
            name = visa["name"]
            if name == f"Visa {code}":
                # Try to generate a better name
                if code.startswith("C"):
                    name = f"{code} Visit Visa"
                elif code.startswith("D"):
                    name = f"{code} Multiple Entry Visa"
                elif code.startswith("E"):
                    name = f"{code} KITAS"
                elif code.startswith("A"):
                    name = f"{code} Visa Free"
                elif code.startswith("B") or code.startswith("F"):
                    name = f"{code} Visa on Arrival"

            # Default requirements if none found
            requirements = visa.get("requirements", [])
            if not requirements:
                requirements = [
                    "Passport valid min 6 months",
                    "Passport photo 4x6 red background",
                    "Return/onward ticket",
                ]

            # Default benefits
            benefits = visa.get("benefits", [])
            if not benefits:
                if category == "KITAS":
                    benefits = ["Legal stay in Indonesia", "Multiple entry/exit", "Path to KITAP"]
                elif category == "Visit":
                    benefits = ["Tourism and leisure", "Business meetings", "Family visits"]
                elif category == "Visa Free":
                    benefits = ["No visa required", "Instant entry"]
                elif category == "VOA":
                    benefits = ["Quick entry at airport", "Extendable once"]

            await conn.execute(
                """
                INSERT INTO visa_types (
                    code, name, category, duration,
                    processing_time_normal, cost_visa,
                    requirements, benefits,
                    renewable, foreign_eligible,
                    metadata, created_at, last_updated
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW(), NOW()
                )
                """,
                code,
                name,
                category,
                duration,
                processing,
                cost_visa,
                requirements,
                benefits,
                category == "KITAS",  # renewable
                True,  # foreign_eligible
                json.dumps({"series": code[0] if code[0].isalpha() else "X", "bali_zero_service": code in BALI_ZERO_PRICES}),
            )
            print(f"  + {code}: {name} ({category}) - {cost_visa}")

        # Get final count
        count = await conn.fetchval("SELECT COUNT(*) FROM visa_types")
        print(f"\nTotal visa types seeded: {count}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_visas())
