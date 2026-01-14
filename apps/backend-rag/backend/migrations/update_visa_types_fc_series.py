#!/usr/bin/env python3
"""
Update visa_types table with complete F and C series visa information.
Extracted from official imigrasi.go.id data.

Run: fly ssh console -a nuzantara-rag -C "python /app/backend/migrations/update_visa_types_fc_series.py"
"""

import asyncio
import json
import os

import asyncpg

# Complete visa data for F and C series
VISA_DATA = {
    # ============ F SERIES (Short-term VOA) ============
    "F1": {
        "name": "F1 - Visa on Arrival (Short Tourism - Riau Islands)",
        "category": "VOA",
        "duration": "7 days",
        "processing_time_normal": "Instant (upon arrival only)",
        "cost_visa": "IDR 250,000 (approx. USD 16)",
        "renewable": False,
        "requirements": [
            "Valid passport with at least 6 months validity",
            "Entry only at designated Riau Islands sea ports",
            "Nationality from VOA-eligible country"
        ],
        "benefits": [
            "Tourism and leisure activities",
            "Visiting family and friends",
            "Attending meetings, incentives, conventions, exhibitions",
            "Transit to another country",
            "No sponsor required",
            "Quick short-term entry for Riau Islands"
        ],
        "restrictions": [
            "Cannot be extended",
            "Cannot be converted to other stay permit types",
            "Only available at specific Riau Islands sea ports",
            "Prohibited from selling goods or services",
            "Prohibited from receiving compensation from Indonesian sources",
            "Not available for stateless persons"
        ],
        "application_methods": [
            "Upon Arrival only: Pay at designated bank counter at sea port, obtain visa sticker"
        ],
        "metadata": {
            "series": "F",
            "entry_type": "Single",
            "visa_type": "Visa on Arrival (Short)",
            "purpose": "Short Tourism",
            "region_restricted": True,
            "allowed_ports": [
                "Nongsa Terminal Bahari",
                "Marina Teluk Senimba",
                "Batam Centre",
                "Citra Tri Tunas",
                "Sri Bintan Pura",
                "Bandar Bentani Telani Lagoi",
                "Tanjung Balai Karimun"
            ],
            "sponsor_required": False,
            "extendable": False,
            "convertible": False,
            "work_allowed": False
        }
    },
    "F4": {
        "name": "F4 - Visa on Arrival (Short Government Assignment - Riau Islands)",
        "category": "VOA",
        "duration": "7 days",
        "processing_time_normal": "Instant (upon arrival only)",
        "cost_visa": "IDR 250,000 (approx. USD 16)",
        "renewable": False,
        "requirements": [
            "Valid passport with at least 6 months validity",
            "Entry only at designated Riau Islands sea ports",
            "Official government assignment documentation"
        ],
        "benefits": [
            "Government duties and official assignments",
            "Tourism activities while on assignment",
            "No sponsor required"
        ],
        "restrictions": [
            "Cannot be extended",
            "Cannot be converted",
            "Only available at specific Riau Islands sea ports",
            "Prohibited from commercial activities"
        ],
        "metadata": {
            "series": "F",
            "entry_type": "Single",
            "visa_type": "Visa on Arrival (Short)",
            "purpose": "Government Assignment",
            "region_restricted": True,
            "sponsor_required": False,
            "extendable": False,
            "convertible": False
        }
    },

    # ============ C SERIES (Visit Visas) ============
    "C1": {
        "name": "C1 - Visit Visa (Tourism)",
        "category": "Visit",
        "duration": "60 days (extendable to 180 days)",
        "processing_time_normal": "5 working days after payment",
        "cost_visa": "IDR 1,000,000 (Bali Zero: IDR 2,300,000)",
        "renewable": True,
        "requirements": [
            "Valid passport with at least 6 months validity (12 months for emergency/temporary passport)",
            "Bank statement showing minimum USD 2,000 (last 3 months)",
            "Recent color passport photo",
            "Account at evisa.imigrasi.go.id"
        ],
        "benefits": [
            "Tourism and personal development",
            "Cruise ship travel",
            "Attending meetings, incentives, conventions, exhibitions",
            "Business discussions, negotiations, contract signing (at offices/factories)",
            "Site inspections (offices, factories, production sites, investment locations, mining sites)",
            "Medical-related activities",
            "Extendable multiple times up to 180 days total",
            "Can be converted to Limited Stay Permit (KITAS)",
            "No sponsor required (for most nationalities)"
        ],
        "restrictions": [
            "Visa valid for 90 days from issuance (must use within this period)",
            "Prohibited from selling goods or services",
            "Prohibited from receiving compensation from Indonesian sources",
            "Prohibited from appearing as speaker/presenter",
            "Stateless persons and certain passport holders require sponsor"
        ],
        "extension_info": {
            "extendable": True,
            "max_total_stay": "180 days",
            "extension_method": "Online at evisa.imigrasi.go.id"
        },
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "visa_type": "Visit Visa",
            "purpose": "Tourism",
            "sponsor_required": False,
            "extendable": True,
            "convertible": True,
            "work_allowed": False,
            "bali_zero_service": True
        }
    },
    "C2": {
        "name": "C2 - Visit Visa (Business)",
        "category": "Visit",
        "duration": "60 days (extendable to 180 days)",
        "processing_time_normal": "5 working days after payment",
        "cost_visa": "IDR 2,000,000 (visa IDR 1M + verification IDR 1M) | Bali Zero: IDR 3,600,000",
        "renewable": True,
        "requirements": [
            "Valid passport with at least 6 months validity",
            "Bank statement (last 3 months)",
            "Recent color passport photo",
            "Invitation letter from Indonesian government agency or private institution",
            "Account at evisa.imigrasi.go.id"
        ],
        "benefits": [
            "Business activities and meetings",
            "Purchasing goods",
            "Business discussions, negotiations, contract signing",
            "Checking goods at offices, factories, production sites",
            "Tourism and visiting friends/family",
            "Extendable multiple times up to 180 days total",
            "Can be converted to Limited Stay Permit (KITAS)",
            "No sponsor required (for most nationalities)"
        ],
        "restrictions": [
            "Visa valid for 90 days from issuance",
            "Prohibited from selling goods or services",
            "Prohibited from receiving compensation from Indonesian sources"
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "visa_type": "Visit Visa",
            "purpose": "Business",
            "sponsor_required": False,
            "extendable": True,
            "convertible": True,
            "work_allowed": False,
            "bali_zero_service": True
        }
    },
    "C3": {
        "name": "C3 - Visit Visa (Medical Treatment)",
        "category": "Visit",
        "duration": "60 days (extendable to 180 days)",
        "processing_time_normal": "5 working days after payment",
        "cost_visa": "IDR 2,000,000",
        "renewable": True,
        "requirements": [
            "Valid passport with at least 6 months validity",
            "Bank statement (last 3 months)",
            "Medical referral or hospital appointment letter",
            "Recent color passport photo"
        ],
        "benefits": [
            "Medical treatment at Indonesian hospitals",
            "Accompanying family member can apply separately",
            "Tourism during recovery",
            "Extendable up to 180 days total"
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "visa_type": "Visit Visa",
            "purpose": "Medical Treatment",
            "sponsor_required": False,
            "extendable": True,
            "work_allowed": False
        }
    },
    "C4": {
        "name": "C4 - Visit Visa (Government Assignment)",
        "category": "Visit",
        "duration": "60 days (extendable to 180 days)",
        "processing_time_normal": "5 working days after payment",
        "cost_visa": "IDR 1,000,000",
        "renewable": True,
        "requirements": [
            "Valid passport with at least 6 months validity",
            "Official government assignment documentation",
            "Invitation letter from Indonesian government agency"
        ],
        "benefits": [
            "Government duties and official assignments",
            "Site visits for official purposes",
            "Tourism during assignment",
            "Extendable up to 180 days total"
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "visa_type": "Visit Visa",
            "purpose": "Government Assignment",
            "sponsor_required": False,
            "extendable": True,
            "work_allowed": False
        }
    },
    "C5": {
        "name": "C5 - Visit Visa (Media and Press)",
        "category": "Visit",
        "duration": "60 days (extendable to 180 days)",
        "processing_time_normal": "5 working days after payment",
        "cost_visa": "IDR 2,000,000",
        "renewable": True,
        "requirements": [
            "Valid passport with at least 6 months validity",
            "Press credentials or media organization letter",
            "Assignment letter detailing coverage scope"
        ],
        "benefits": [
            "Journalism and media coverage",
            "Documentary filming",
            "Press conferences and interviews",
            "Tourism activities"
        ],
        "restrictions": [
            "Must not violate press ethics",
            "Coverage must be approved/appropriate"
        ],
        "metadata": {
            "series": "C",
            "visa_type": "Visit Visa",
            "purpose": "Media and Press",
            "sponsor_required": True,
            "extendable": True,
            "work_allowed": True,
            "work_type": "Journalism only"
        }
    },
    "C5A": {
        "name": "C5A - Visit Visa (Content Creator)",
        "category": "Visit",
        "duration": "60-90 days",
        "processing_time_normal": "5 working days after payment",
        "cost_visa": "USD 2,000 minimum investment requirement",
        "renewable": True,
        "requirements": [
            "Valid passport with at least 6 months validity",
            "Proof of content creator status (social media following, portfolio)",
            "Minimum investment/income proof of USD 2,000",
            "Bank statement showing sufficient funds"
        ],
        "benefits": [
            "Create content in Indonesia (YouTube, Instagram, TikTok, etc.)",
            "Can receive compensation for content work",
            "Tourism and exploration",
            "Build portfolio with Indonesian scenery/culture"
        ],
        "restrictions": [
            "Cannot work for Indonesian companies",
            "Income must be from foreign sources"
        ],
        "metadata": {
            "series": "C",
            "visa_type": "Visit Visa",
            "purpose": "Content Creator",
            "sponsor_required": False,
            "extendable": True,
            "work_allowed": True,
            "work_type": "Content creation only",
            "income_requirement": "USD 2,000 minimum"
        }
    },
    "C6": {
        "name": "C6 - Visit Visa (Social Activities)",
        "category": "Visit",
        "duration": "60 days (extendable to 180 days)",
        "processing_time_normal": "5 working days after payment",
        "cost_visa": "IDR 1,000,000",
        "renewable": True,
        "requirements": [
            "Valid passport with at least 6 months validity",
            "Invitation from organizing institution",
            "Proof of social/charitable purpose"
        ],
        "benefits": [
            "Volunteer and social work",
            "Charitable activities",
            "NGO-related activities",
            "Tourism"
        ],
        "restrictions": [
            "Cannot receive compensation"
        ],
        "metadata": {
            "series": "C",
            "visa_type": "Visit Visa",
            "purpose": "Social Activities",
            "sponsor_required": True,
            "extendable": True,
            "work_allowed": False
        }
    },
    "C7": {
        "name": "C7 - Visit Visa (Arts and Culture Performance)",
        "category": "Visit",
        "duration": "30 days",
        "processing_time_normal": "5 working days after payment",
        "cost_visa": "IDR 1,500,000",
        "renewable": False,
        "requirements": [
            "Valid passport with at least 6 months validity",
            "Invitation from event organizer",
            "Performance/event details"
        ],
        "benefits": [
            "Arts and cultural performances",
            "Can receive compensation for performance",
            "Tourism during stay"
        ],
        "restrictions": [
            "Cannot be extended",
            "Cannot be converted",
            "Must not violate cultural norms"
        ],
        "metadata": {
            "series": "C",
            "visa_type": "Visit Visa",
            "purpose": "Arts and Culture Performance",
            "sponsor_required": True,
            "extendable": False,
            "work_allowed": True,
            "work_type": "Performance only"
        }
    },
    "C7A": {
        "name": "C7A - Visit Visa (Music Performance)",
        "category": "Visit",
        "duration": "30 days",
        "processing_time_normal": "5 working days (Including Urgent available) | Bali Zero: IDR 4,500,000",
        "cost_visa": "IDR 1,500,000 (visa IDR 500K + verification IDR 1M)",
        "renewable": False,
        "requirements": [
            "Valid passport with at least 6 months validity (12 months for emergency passport)",
            "Bank statement (last 3 months)",
            "Sponsor statement letter from event organizer",
            "Invitation letter from event organizer (for general art/culture performers)",
            "Guarantee letter and visa application from impresariat + work contract with organizer (for music performers)",
            "Recent color passport photo"
        ],
        "benefits": [
            "Music performances and concerts",
            "Can receive compensation/fees for performance",
            "Tourism and visiting friends/family",
            "Quick processing with urgent option"
        ],
        "restrictions": [
            "Cannot be extended",
            "Cannot be converted to other stay permit types",
            "Cannot work in employment relationship with Indonesian entities",
            "Must not perform content violating regulations or norms",
            "Visa valid for 90 days from issuance"
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "visa_type": "Visit Visa",
            "purpose": "Music Performance",
            "sponsor_required": True,
            "extendable": False,
            "convertible": False,
            "work_allowed": True,
            "work_type": "Music performance only",
            "can_receive_payment": True,
            "bali_zero_service": True
        }
    },
    "C7B": {
        "name": "C7B - Visit Visa (Music Performance Crew)",
        "category": "Visit",
        "duration": "30 days",
        "processing_time_normal": "5 working days (Including Urgent available) | Bali Zero: IDR 4,500,000",
        "cost_visa": "IDR 1,500,000 (visa IDR 500K + verification IDR 1M)",
        "renewable": False,
        "requirements": [
            "Valid passport with at least 6 months validity",
            "Sponsor statement letter from event organizer",
            "Proof of crew role (technician, roadie, manager, etc.)"
        ],
        "benefits": [
            "Support music performances as crew",
            "Can receive compensation for work",
            "Tourism during stay"
        ],
        "restrictions": [
            "Cannot be extended",
            "Cannot be converted",
            "Must work only for specified event"
        ],
        "metadata": {
            "series": "C",
            "visa_type": "Visit Visa",
            "purpose": "Music Performance Crew",
            "sponsor_required": True,
            "extendable": False,
            "work_allowed": True,
            "work_type": "Music crew support only",
            "bali_zero_service": True
        }
    },
    "C8": {
        "name": "C8 - Visit Visa (Sports Activities)",
        "category": "Visit",
        "duration": "30-60 days",
        "processing_time_normal": "5 working days after payment",
        "cost_visa": "IDR 1,500,000",
        "renewable": False,
        "requirements": [
            "Valid passport with at least 6 months validity",
            "Invitation from sports organization/event organizer",
            "Proof of athlete/official status"
        ],
        "benefits": [
            "Participate in sports events and competitions",
            "Training and practice",
            "Can receive prizes/compensation for competitions"
        ],
        "metadata": {
            "series": "C",
            "visa_type": "Visit Visa",
            "purpose": "Sports Activities",
            "sponsor_required": True,
            "extendable": False,
            "work_allowed": True,
            "work_type": "Sports activities only"
        }
    },
    "C12": {
        "name": "C12 - Visit Visa (Pre-Investment)",
        "category": "Visit",
        "duration": "60 days (extendable to 180 days)",
        "processing_time_normal": "5 working days after payment",
        "cost_visa": "IDR 2,000,000",
        "renewable": True,
        "requirements": [
            "Valid passport with at least 6 months validity",
            "Investment plan documentation",
            "Bank statement showing investment capability"
        ],
        "benefits": [
            "Survey and research for potential investments",
            "Site visits and due diligence",
            "Meeting with potential partners",
            "Extendable for longer research periods",
            "Path to investor KITAS (E28)"
        ],
        "metadata": {
            "series": "C",
            "visa_type": "Visit Visa",
            "purpose": "Pre-Investment",
            "sponsor_required": False,
            "extendable": True,
            "work_allowed": False,
            "pathway_to": "E28 Investor KITAS"
        }
    },
    "C14": {
        "name": "C14 - Visit Visa (Film Production)",
        "category": "Visit",
        "duration": "60 days (extendable to 180 days)",
        "processing_time_normal": "5 working days after payment",
        "cost_visa": "IDR 2,000,000",
        "renewable": True,
        "requirements": [
            "Valid passport with at least 6 months validity",
            "Film production permit",
            "Production company documentation",
            "Filming schedule and locations"
        ],
        "benefits": [
            "Film and video production",
            "Documentary filming",
            "Commercial production",
            "Can receive compensation for production work"
        ],
        "metadata": {
            "series": "C",
            "visa_type": "Visit Visa",
            "purpose": "Film Production",
            "sponsor_required": True,
            "extendable": True,
            "work_allowed": True,
            "work_type": "Film production only"
        }
    },
    "C18": {
        "name": "C18 - Visit Visa (Work Trial / Ability Test)",
        "category": "Visit",
        "duration": "90 days",
        "processing_time_normal": "5 working days after payment | Bali Zero: IDR 5,500,000",
        "cost_visa": "IDR 4,000,000 (visa IDR 2M + verification II IDR 2M)",
        "renewable": False,
        "requirements": [
            "Valid passport with at least 6 months validity (12 months for emergency passport)",
            "Bank statement (last 3 months)",
            "Invitation letter for work trial from government agency or private company",
            "Sponsor statement letter",
            "Recent color passport photo"
        ],
        "benefits": [
            "Work trial/probation at Indonesian company",
            "Test professional capabilities before full employment",
            "Tourism and visiting friends/family",
            "Can be converted to Limited Stay Permit (KITAS) with same sponsor",
            "Path to full work visa (E23 KITAS)"
        ],
        "restrictions": [
            "Cannot be extended (fixed 90 days)",
            "Visa valid for 90 days from issuance",
            "Prohibited from receiving wages from Indonesian sources during trial",
            "Must have company sponsor"
        ],
        "metadata": {
            "series": "C",
            "entry_type": "Single",
            "visa_type": "Visit Visa",
            "purpose": "Work Trial",
            "sponsor_required": True,
            "extendable": False,
            "convertible": True,
            "conversion_to": "KITAS (same sponsor required)",
            "work_allowed": True,
            "work_type": "Trial/probation only",
            "bali_zero_service": True
        }
    },
    "C22A": {
        "name": "C22A - Visit Visa (Academic Internship)",
        "category": "Visit",
        "duration": "60 days (extendable to 180 days)",
        "processing_time_normal": "5 working days | Bali Zero: IDR 4,800,000",
        "cost_visa": "IDR 2,000,000",
        "renewable": True,
        "requirements": [
            "Valid passport with at least 6 months validity",
            "University enrollment proof",
            "Internship acceptance letter from Indonesian institution",
            "Academic supervisor recommendation"
        ],
        "benefits": [
            "Academic internship at Indonesian institutions",
            "Research activities",
            "Practical training as part of academic program",
            "Can be extended for longer programs"
        ],
        "metadata": {
            "series": "C",
            "visa_type": "Visit Visa",
            "purpose": "Academic Internship",
            "sponsor_required": True,
            "extendable": True,
            "work_allowed": True,
            "work_type": "Academic internship only",
            "bali_zero_service": True
        }
    },
    "C22B": {
        "name": "C22B - Visit Visa (Skills Development)",
        "category": "Visit",
        "duration": "60 days (extendable to 180 days)",
        "processing_time_normal": "5 working days | Bali Zero: IDR 4,800,000",
        "cost_visa": "IDR 2,000,000",
        "renewable": True,
        "requirements": [
            "Valid passport with at least 6 months validity",
            "Training program acceptance letter",
            "Skills development program documentation"
        ],
        "benefits": [
            "Professional skills training",
            "Vocational training programs",
            "Technical skills development",
            "Can be extended for longer programs"
        ],
        "metadata": {
            "series": "C",
            "visa_type": "Visit Visa",
            "purpose": "Skills Development",
            "sponsor_required": True,
            "extendable": True,
            "work_allowed": True,
            "work_type": "Training only",
            "bali_zero_service": True
        }
    }
}


async def update_visa_types():
    """Update visa_types table with complete F and C series data."""
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    try:
        print("Updating F and C series visa types with complete information...\n")

        updated = 0
        inserted = 0

        for code, data in VISA_DATA.items():
            # Check if visa exists
            existing = await conn.fetchval(
                "SELECT id FROM visa_types WHERE code = $1", code
            )

            metadata = {
                **data.get("metadata", {}),
                "restrictions": data.get("restrictions", []),
                "application_methods": data.get("application_methods", []),
            }
            if "extension_info" in data:
                metadata["extension_info"] = data["extension_info"]

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
                    json.dumps(metadata),
                )
                print(f"  ✓ Updated: {data['name']}")
                updated += 1
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
                    json.dumps(metadata),
                )
                print(f"  + Inserted: {data['name']}")
                inserted += 1

        # Show summary
        print(f"\n✅ F and C series: {updated} updated, {inserted} inserted")

        # Show all F and C series
        print("\n📋 F and C Series Visa Types:")
        print("-" * 80)
        rows = await conn.fetch(
            """
            SELECT code, name, category, duration, cost_visa
            FROM visa_types
            WHERE code LIKE 'F%' OR code LIKE 'C%'
            ORDER BY code
            """
        )
        for row in rows:
            print(f"  {row['code']:6} | {row['name'][:45]:45} | {row['duration'][:20]}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(update_visa_types())
