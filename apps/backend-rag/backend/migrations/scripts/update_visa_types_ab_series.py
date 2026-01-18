#!/usr/bin/env python3
"""
Update visa_types table with complete A and B series visa information.
Extracted from official imigrasi.go.id data.

Run: fly ssh console -a nuzantara-rag -C "python /app/backend/migrations/update_visa_types_ab_series.py"
"""

import asyncio
import json
import os

import asyncpg

# Complete visa data for A and B series
VISA_DATA = {
    "A1": {
        "name": "A1 - Visa-Free Tourism",
        "category": "Visa Free",
        "duration": "30 days",
        "processing_time_normal": "Instant (upon arrival or pre-arrival electronic)",
        "cost_visa": "FREE",
        "renewable": False,
        "requirements": [
            "Valid passport with at least 6 months validity",
            "Return or onward ticket to another country",
            "Certain nationalities only (visa-free eligible countries)",
        ],
        "benefits": [
            "Tourism and leisure activities",
            "Visiting family and friends",
            "Attending meetings, incentives, conventions, exhibitions",
            "Transit to another country",
            "No sponsor required",
        ],
        "restrictions": [
            "Cannot be extended",
            "Cannot be converted to other stay permit types",
            "Prohibited from selling goods or services",
            "Prohibited from receiving compensation or wages from Indonesian sources",
            "Not available for stateless persons",
            "Not available for holders of temporary/emergency passports",
        ],
        "application_methods": [
            "Upon Arrival: Present passport and return ticket at immigration counter",
            "Pre-Arrival (electronic): Apply at evisa.imigrasi.go.id, receive electronic entry stamp",
        ],
        "metadata": {
            "series": "A",
            "entry_type": "Single",
            "visa_type": "Visa-Free Facility",
            "sponsor_required": False,
            "extendable": False,
            "convertible": False,
            "work_allowed": False,
        },
    },
    "A4": {
        "name": "A4 - Visa-Free Government Assignment",
        "category": "Visa Free",
        "duration": "30 days",
        "processing_time_normal": "Instant (upon arrival or pre-arrival electronic)",
        "cost_visa": "FREE",
        "renewable": False,
        "requirements": [
            "Valid passport with at least 6 months validity",
            "Return or onward ticket to another country",
            "Official government assignment documentation",
            "Certain nationalities only (visa-free eligible countries)",
        ],
        "benefits": [
            "Government duties and official assignments",
            "Visiting locations for official government purposes",
            "Conducting activities related to government tasks",
            "Tourism activities while on assignment",
            "Visiting friends and family",
            "No sponsor required",
        ],
        "restrictions": [
            "Cannot be extended",
            "Cannot be converted to other stay permit types",
            "Prohibited from selling goods or services",
            "Prohibited from receiving compensation from Indonesian sources",
            "Not available for stateless persons",
            "Not available for holders of temporary/emergency passports",
        ],
        "application_methods": [
            "Upon Arrival: Present passport and documents at immigration counter",
            "Pre-Arrival (electronic): Apply at evisa.imigrasi.go.id",
        ],
        "metadata": {
            "series": "A",
            "entry_type": "Single",
            "visa_type": "Visa-Free Facility",
            "purpose": "Government Assignment",
            "sponsor_required": False,
            "extendable": False,
            "convertible": False,
            "work_allowed": False,
        },
    },
    "A36": {
        "name": "A36 - Visa-Free Ship and Aircraft Crew",
        "category": "Visa Free",
        "duration": "30 days",
        "processing_time_normal": "Instant (upon arrival or pre-arrival electronic)",
        "cost_visa": "FREE",
        "renewable": False,
        "requirements": [
            "Valid passport with at least 6 months validity",
            "Return or onward ticket",
            "Registered in General Declaration or crew manifest",
            "Must be active crew (captain, pilot, or crew member)",
        ],
        "benefits": [
            "Work duties on transport vehicles (ships, aircraft)",
            "Active crew assignments as captain, pilot, or crew",
            "Tourism activities during shore leave",
            "Shopping and personal activities",
            "Visiting friends and family",
            "No sponsor required",
        ],
        "restrictions": [
            "Cannot be extended",
            "Cannot be converted to other stay permit types",
            "Must be registered in crew manifest or General Declaration",
            "Not applicable for private vehicles or cargo",
            "Prohibited from other employment",
            "Not available for stateless persons",
        ],
        "application_methods": [
            "Upon Arrival: Present passport, crew manifest at immigration counter",
            "Pre-Arrival (electronic): Apply at evisa.imigrasi.go.id",
        ],
        "metadata": {
            "series": "A",
            "entry_type": "Single",
            "visa_type": "Visa-Free Facility",
            "purpose": "Ship and Aircraft Crew",
            "crew_type": ["Captain", "Pilot", "Active Crew"],
            "sponsor_required": False,
            "extendable": False,
            "convertible": False,
            "work_allowed": True,
            "work_type": "Transport crew duties only",
        },
    },
    "A37": {
        "name": "A37 - Visa-Free Ship Crew in Indonesian Waters",
        "category": "Visa Free",
        "duration": "30 days",
        "processing_time_normal": "Instant (upon arrival or pre-arrival electronic)",
        "cost_visa": "FREE",
        "renewable": False,
        "requirements": [
            "Valid passport with at least 6 months validity",
            "Return or onward ticket",
            "Registered in General Declaration or crew manifest",
            "Must be captain, ship crew, or foreign expert on vessel",
            "Vessel must operate in Indonesian waters (Nusantara waters, territorial sea, continental shelf, or EEZ)",
        ],
        "benefits": [
            "Work as captain, ship crew, or foreign expert on marine vessels",
            "Operations in Indonesian archipelagic waters",
            "Operations in territorial sea and continental shelf",
            "Operations in Exclusive Economic Zone (EEZ)",
            "Tourism during shore leave",
            "Visiting friends and family",
            "No sponsor required",
        ],
        "restrictions": [
            "Cannot be extended",
            "Cannot be converted to other stay permit types",
            "Must arrive directly with the vessel",
            "Vessel must operate in Indonesian waters",
            "Not applicable for private vessels or cargo ships not operating in Indonesian waters",
            "Not available for stateless persons",
        ],
        "application_methods": [
            "Upon Arrival: Present passport, crew manifest at immigration counter",
            "Pre-Arrival (electronic): Apply at evisa.imigrasi.go.id",
        ],
        "metadata": {
            "series": "A",
            "entry_type": "Single",
            "visa_type": "Visa-Free Facility",
            "purpose": "Ship Crew in Indonesian Waters",
            "operating_areas": ["Nusantara Waters", "Territorial Sea", "Continental Shelf", "EEZ"],
            "crew_type": ["Captain", "Ship Crew", "Foreign Expert"],
            "sponsor_required": False,
            "extendable": False,
            "convertible": False,
            "work_allowed": True,
            "work_type": "Marine vessel operations only",
        },
    },
    "B1": {
        "name": "B1 - Visa on Arrival (Tourism)",
        "category": "VOA",
        "duration": "30 days (extendable to 60 days)",
        "processing_time_normal": "Instant (upon arrival) or 1x24 hours (e-VOA)",
        "cost_visa": "IDR 500,000 (approx. USD 32)",
        "renewable": True,
        "requirements": [
            "Valid passport with at least 6 months validity",
            "Return or onward ticket to another country",
            "Nationality from VOA-eligible country",
            "Recent color passport photo",
            "For temporary/emergency passport holders: 12 months validity required",
        ],
        "benefits": [
            "Tourism and leisure activities",
            "Visiting family and friends",
            "Attending meetings, incentives, conventions, exhibitions",
            "Transit to another country",
            "Extendable once for additional 30 days",
            "Can be converted to other stay permit via bridging visa",
            "No sponsor required",
            "Multiple application methods available",
        ],
        "restrictions": [
            "Prohibited from selling goods or services",
            "Prohibited from receiving compensation or wages from Indonesian sources",
            "e-VOA valid for 90 days from issuance (must use within this period)",
            "Non-electronic VOA must be used immediately after issuance",
            "Not available for stateless persons",
            "Not available for holders of titre du voyage, certificate of identity, laissez passer",
        ],
        "application_methods": [
            "e-VOA Pre-Arrival: Apply at evisa.imigrasi.go.id or indonesiavoa.vfsevisa.id, pay by debit/credit card",
            "e-VOA Pre-Arrival + Payment on Arrival: Apply online, pay at airport bank counter",
            "Traditional VOA on Arrival: Pay at designated bank counter, obtain visa voucher and sticker",
        ],
        "extension_info": {
            "extendable": True,
            "extension_count": 1,
            "extension_duration": "30 days",
            "total_max_stay": "60 days",
            "extension_method_evoa": "Online at evisa.imigrasi.go.id or indonesiavoa.vfsevisa.id",
            "extension_method_traditional": "At nearest Immigration Office",
        },
        "metadata": {
            "series": "B",
            "entry_type": "Single",
            "visa_type": "Visa on Arrival",
            "purpose": "Tourism",
            "sponsor_required": False,
            "extendable": True,
            "extension_count": 1,
            "convertible": True,
            "conversion_method": "Bridging visa",
            "work_allowed": False,
            "evoa_validity": "90 days from issuance",
        },
    },
    "B4": {
        "name": "B4 - Visa on Arrival (Government Assignment)",
        "category": "VOA",
        "duration": "30 days (extendable to 60 days)",
        "processing_time_normal": "Instant (upon arrival) or 1x24 hours (e-VOA)",
        "cost_visa": "IDR 500,000 (approx. USD 32)",
        "renewable": True,
        "requirements": [
            "Valid passport with at least 6 months validity",
            "Return or onward ticket to another country",
            "Nationality from VOA-eligible country",
            "Official government assignment documentation",
            "Recent color passport photo",
            "For emergency/identity document holders: 12 months validity required",
        ],
        "benefits": [
            "Government duties and official assignments",
            "Visiting locations for official government purposes",
            "Conducting activities related to government tasks",
            "Tourism activities while on assignment",
            "Visiting friends and family",
            "Extendable once for additional 30 days",
            "Can be converted to other stay permit via bridging visa",
            "No sponsor required",
        ],
        "restrictions": [
            "Prohibited from selling goods or services",
            "Prohibited from receiving compensation from Indonesian sources",
            "e-VOA valid for 90 days from issuance",
            "Non-electronic VOA must be used immediately",
            "Not available for stateless persons",
            "Not available for holders of titre du voyage, certificate of identity, laissez passer",
        ],
        "application_methods": [
            "e-VOA Pre-Arrival: Apply at evisa.imigrasi.go.id, pay by debit/credit card",
            "e-VOA Pre-Arrival + Payment on Arrival: Apply online, pay at airport",
            "Traditional VOA on Arrival: Pay at designated bank counter, obtain visa sticker",
        ],
        "extension_info": {
            "extendable": True,
            "extension_count": 1,
            "extension_duration": "30 days",
            "total_max_stay": "60 days",
            "extension_method_evoa": "Online at evisa.imigrasi.go.id",
            "extension_method_traditional": "At nearest Immigration Office",
        },
        "metadata": {
            "series": "B",
            "entry_type": "Single",
            "visa_type": "Visa on Arrival",
            "purpose": "Government Assignment",
            "sponsor_required": False,
            "extendable": True,
            "extension_count": 1,
            "convertible": True,
            "conversion_method": "Bridging visa",
            "work_allowed": False,
            "evoa_validity": "90 days from issuance",
        },
    },
}


async def update_visa_types():
    """Update visa_types table with complete A and B series data."""
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    try:
        print("Updating A and B series visa types with complete information...\n")

        for code, data in VISA_DATA.items():
            # Check if visa exists
            existing = await conn.fetchval("SELECT id FROM visa_types WHERE code = $1", code)

            if existing:
                # Update existing record
                await conn.execute(
                    """
                    UPDATE visa_types SET
                        name = $2,
                        category = $3,
                        duration = $4,
                        processing_time_normal = $5,
                        cost_visa = $6,
                        renewable = $7,
                        requirements = $8,
                        benefits = $9,
                        metadata = $10,
                        last_updated = NOW()
                    WHERE code = $1
                    """,
                    code,
                    data["name"],
                    data["category"],
                    data["duration"],
                    data["processing_time_normal"],
                    data["cost_visa"],
                    data["renewable"],
                    data["requirements"],
                    data["benefits"],
                    json.dumps(
                        {
                            **data["metadata"],
                            "restrictions": data["restrictions"],
                            "application_methods": data["application_methods"],
                            **(
                                {"extension_info": data["extension_info"]}
                                if "extension_info" in data
                                else {}
                            ),
                        }
                    ),
                )
                print(f"  ✓ Updated: {data['name']}")
            else:
                # Insert new record
                await conn.execute(
                    """
                    INSERT INTO visa_types (
                        code, name, category, duration, processing_time_normal,
                        cost_visa, renewable, foreign_eligible, requirements, benefits,
                        metadata, created_at, last_updated
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW(), NOW())
                    """,
                    code,
                    data["name"],
                    data["category"],
                    data["duration"],
                    data["processing_time_normal"],
                    data["cost_visa"],
                    data["renewable"],
                    True,
                    data["requirements"],
                    data["benefits"],
                    json.dumps(
                        {
                            **data["metadata"],
                            "restrictions": data["restrictions"],
                            "application_methods": data["application_methods"],
                            **(
                                {"extension_info": data["extension_info"]}
                                if "extension_info" in data
                                else {}
                            ),
                        }
                    ),
                )
                print(f"  + Inserted: {data['name']}")

        # Show summary
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM visa_types WHERE code IN ('A1', 'A4', 'A36', 'A37', 'B1', 'B4')"
        )
        print(f"\n✅ A and B series updated: {count} visa types")

        # Show all A and B series
        print("\n📋 A and B Series Visa Types:")
        print("-" * 60)
        rows = await conn.fetch(
            """
            SELECT code, name, category, duration, cost_visa
            FROM visa_types
            WHERE code LIKE 'A%' OR code LIKE 'B%'
            ORDER BY code
            """
        )
        for row in rows:
            print(f"  {row['code']:6} | {row['name'][:40]:40} | {row['duration']}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(update_visa_types())
