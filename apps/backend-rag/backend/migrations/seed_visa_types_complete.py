"""
Complete Visa Types Seed - All Series A-F
Based on official imigrasi.go.id data + Bali Zero 2025 pricing

Run: fly ssh console -a nuzantara-rag -C "python -m backend.migrations.seed_visa_types_complete"
"""

import asyncio
import asyncpg
import os
import json
from datetime import datetime

VISA_TYPES = [
    # ==========================================================================
    # SERIES A - BEBAS VISA (Visa Free)
    # ==========================================================================
    {
        "code": "A1",
        "name": "Bebas Visa Wisata (Visa Free Tourism)",
        "category": "Visa Free",
        "duration": "30 days",
        "total_stay": "30 days (non-extendable)",
        "renewable": False,
        "processing_time_normal": "On arrival",
        "cost_visa": "FREE",
        "requirements": [
            "Passport valid min 6 months",
            "Return/onward ticket",
            "From visa-free eligible country",
        ],
        "benefits": [
            "No visa required",
            "Instant entry for eligible countries",
            "Tourism activities only",
        ],
        "restrictions": [
            "Cannot be extended",
            "No work allowed",
            "Single entry only",
        ],
        "metadata": {"series": "A", "bali_zero_service": False},
    },
    {
        "code": "A4",
        "name": "Bebas Visa Tugas Pemerintahan (Visa Free Government)",
        "category": "Visa Free",
        "duration": "30 days",
        "total_stay": "30 days",
        "renewable": False,
        "processing_time_normal": "On arrival",
        "cost_visa": "FREE",
        "requirements": [
            "Diplomatic/Service passport",
            "Official government assignment",
        ],
        "benefits": ["No visa required", "Government duty activities"],
        "metadata": {"series": "A", "bali_zero_service": False},
    },

    # ==========================================================================
    # SERIES B - VISA ON ARRIVAL (VOA)
    # ==========================================================================
    {
        "code": "B1",
        "name": "Visa on Arrival (VOA) Tourism",
        "category": "VOA",
        "duration": "30 days",
        "total_stay": "60 days (with extension)",
        "renewable": True,
        "extensions": "1x 30 days",
        "processing_time_normal": "On arrival",
        "cost_visa": "IDR 500,000 (USD 32)",
        "cost_extension": "IDR 500,000",
        "requirements": [
            "Passport valid min 6 months",
            "Return/onward ticket",
            "From VOA eligible country",
            "Payment in IDR/USD/card",
        ],
        "benefits": [
            "Quick entry at airport",
            "Extendable once",
            "Available at major ports",
        ],
        "restrictions": [
            "No work allowed",
            "Max 60 days total",
            "Single entry",
        ],
        "metadata": {"series": "B", "bali_zero_service": True, "popularity": "very_high"},
    },

    # ==========================================================================
    # SERIES C - VISA KUNJUNGAN (Single Entry Visit Visa)
    # ==========================================================================
    {
        "code": "C1",
        "name": "Visa Kunjungan Wisata (Tourism Visit Visa)",
        "category": "Visit",
        "duration": "60 days",
        "total_stay": "180 days (with extensions)",
        "renewable": True,
        "extensions": "3x 60 days",
        "processing_time_normal": "7-10 days",
        "cost_visa": "IDR 1,000,000",
        "cost_extension": "IDR 500,000 per extension",
        "requirements": [
            "Passport valid min 6 months",
            "Bank statement min USD 2,000",
            "Passport photo (red background)",
            "Return/onward ticket",
        ],
        "benefits": [
            "60 days initial stay",
            "Extendable up to 180 days",
            "Tourism and leisure activities",
        ],
        "restrictions": [
            "No work or paid activities",
            "Single entry only",
        ],
        "metadata": {"series": "C", "bali_zero_service": True},
    },
    {
        "code": "C2",
        "name": "Visa Kunjungan Bisnis (Business Visit Visa)",
        "category": "Visit",
        "duration": "60 days",
        "total_stay": "180 days",
        "renewable": True,
        "extensions": "3x 60 days",
        "processing_time_normal": "7-10 days",
        "cost_visa": "IDR 1,500,000",
        "requirements": [
            "Passport valid min 6 months",
            "Bank statement min USD 2,000",
            "Invitation letter from Indonesian company",
            "Business purpose letter",
        ],
        "benefits": [
            "Business meetings and negotiations",
            "Site visits and inspections",
            "Contract discussions",
        ],
        "restrictions": [
            "No work or employment",
            "No selling goods/services",
        ],
        "metadata": {"series": "C", "bali_zero_service": True},
    },
    {
        "code": "C12",
        "name": "Visa Pra-Investasi (Pre-Investment Visa)",
        "category": "Visit",
        "duration": "60 days",
        "total_stay": "180 days",
        "renewable": True,
        "processing_time_normal": "7-10 days",
        "cost_visa": "IDR 2,000,000",
        "requirements": [
            "Passport valid min 6 months",
            "Bank statement min USD 2,000",
            "Investment plan/proposal",
        ],
        "benefits": [
            "Explore investment opportunities",
            "Visit potential sites",
            "Meet with BKPM/OSS",
        ],
        "metadata": {"series": "C", "bali_zero_service": True},
    },

    # ==========================================================================
    # SERIES D - VISA KUNJUNGAN MULTIPLE (Multiple Entry Visit Visa)
    # ==========================================================================
    {
        "code": "D1",
        "name": "Tourism Multiple Entry Visa",
        "category": "Visit",
        "duration": "1-5 years",
        "total_stay": "60 days per entry",
        "renewable": False,
        "processing_time_normal": "7-10 days",
        "cost_visa": "IDR 5,000,000 (1Y) / IDR 7,000,000 (5Y)",
        "requirements": [
            "Passport valid min 18 months",
            "Photo 4x6 red background",
            "Bank statement 3 months (min USD 5,000)",
            "Return flight ticket",
            "Hotel booking or address in Indonesia",
        ],
        "benefits": [
            "5-year validity option",
            "Unlimited entries",
            "60 days per entry",
            "All international entry points",
        ],
        "restrictions": [
            "No work allowed",
            "Must exit every 60 days",
        ],
        "metadata": {
            "series": "D",
            "bali_zero_service": True,
            "bali_zero_price_1y": "IDR 5,000,000",
            "bali_zero_price_5y": "IDR 7,000,000",
        },
    },
    {
        "code": "D2",
        "name": "Business Multiple Entry Visa",
        "category": "Visit",
        "duration": "1-2 years",
        "total_stay": "60 days per entry",
        "renewable": False,
        "processing_time_normal": "7-10 days",
        "cost_visa": "IDR 6,000,000 (1Y) / IDR 8,000,000 (2Y)",
        "requirements": [
            "Passport valid min 18 months",
            "Company invitation letter",
            "Bank statement min USD 5,000",
            "Business purpose letter",
        ],
        "benefits": [
            "Multiple entries for business",
            "Meetings and negotiations",
            "Market research allowed",
        ],
        "metadata": {"series": "D", "bali_zero_service": True},
    },
    {
        "code": "D12",
        "name": "Business Investigation Visa (Pre-Investment)",
        "category": "Visit",
        "duration": "1-2 years",
        "total_stay": "180 days per entry",
        "renewable": False,
        "processing_time_normal": "7-10 days",
        "cost_visa": "IDR 7,500,000 (1Y) / IDR 10,000,000 (2Y)",
        "requirements": [
            "Passport valid min 18 months",
            "Photo 4x6 red background",
            "Bank statement 3 months (min USD 10,000)",
            "Investment plan or business proposal",
            "CV/Resume",
            "Travel itinerary",
        ],
        "benefits": [
            "180 days per entry (not 60!)",
            "Multiple entry for 1-2 years",
            "Explore investment opportunities",
            "Meet with BKPM and local partners",
            "Market research allowed",
        ],
        "restrictions": [
            "No work or employment",
            "Investment investigation only",
        ],
        "metadata": {
            "series": "D",
            "bali_zero_service": True,
            "bali_zero_recommended": True,
            "bali_zero_price_1y": "IDR 7,500,000",
            "bali_zero_price_2y": "IDR 10,000,000",
        },
    },

    # ==========================================================================
    # SERIES E - KITAS (Limited Stay Permit)
    # ==========================================================================

    # --- E23 - Working KITAS ---
    {
        "code": "E23",
        "name": "Working KITAS (IMTA/RPTKA)",
        "category": "KITAS",
        "duration": "1-2 years",
        "total_stay": "1-2 years (renewable)",
        "renewable": True,
        "processing_time_normal": "4-6 weeks",
        "cost_visa": "IDR 30,000,000 (offshore) / IDR 35,000,000 (onshore)",
        "cost_extension": "IDR 28,000,000",
        "requirements": [
            "Passport valid min 18 months",
            "Photo 4x6 red background",
            "CV/Resume",
            "Degree certificate (legalized)",
            "Employment contract",
            "RPTKA approval from Kemenaker",
            "Company documents (NIB, NPWP, SK Kemenkumham)",
        ],
        "benefits": [
            "Work legally in Indonesia",
            "Full employment rights",
            "Multiple entry/exit",
            "Path to KITAP after 4 years",
        ],
        "restrictions": [
            "Must work for sponsoring company",
            "Position must match RPTKA",
            "Cannot freelance or work elsewhere",
        ],
        "metadata": {
            "series": "E",
            "bali_zero_service": True,
            "difficulty": "high",
            "bali_zero_price_offshore": "IDR 30,000,000",
            "bali_zero_price_onshore": "IDR 35,000,000",
            "processing_note": "4-6 weeks due to RPTKA + IMTA requirements",
        },
    },

    # --- E26 - Spouse KITAS ---
    {
        "code": "E26",
        "name": "Spouse KITAS (Indonesian Marriage)",
        "category": "KITAS",
        "duration": "2 years",
        "total_stay": "2 years (renewable to KITAP)",
        "renewable": True,
        "processing_time_normal": "7-10 days",
        "cost_visa": "IDR 14,000,000 (offshore) / IDR 16,000,000 (onshore)",
        "cost_extension": "IDR 12,000,000",
        "requirements": [
            "Passport valid min 18 months",
            "Photo 4x6 red background",
            "Marriage certificate (legalized)",
            "Spouse's KTP and KK",
            "Sponsor letter from spouse",
            "Bank statement 3 months",
        ],
        "benefits": [
            "2-year validity",
            "Multiple entry/exit",
            "Can work with IKTA",
            "Path to KITAP after 2 years",
        ],
        "metadata": {
            "series": "E",
            "bali_zero_service": True,
            "bali_zero_price_offshore": "IDR 14,000,000",
            "bali_zero_price_onshore": "IDR 16,000,000",
        },
    },

    # --- E28 - Investor KITAS ---
    {
        "code": "E28A",
        "name": "Investor KITAS (PT PMA Director/Commissioner)",
        "category": "KITAS",
        "duration": "2 years",
        "total_stay": "2 years (renewable, path to KITAP)",
        "renewable": True,
        "processing_time_normal": "7-10 days",
        "cost_visa": "IDR 17,000,000 (offshore) / IDR 19,000,000 (onshore)",
        "cost_extension": "IDR 18,000,000",
        "requirements": [
            "Passport valid min 18 months",
            "Photo 4x6 red background",
            "CV/Resume",
            "Director/Commissioner appointment letter",
            "PT Deed of Incorporation",
            "Active NIB (Business ID Number)",
            "Company NPWP",
            "SK Kemenkumham",
            "Company Domicile Letter",
            "Capital deposit min IDR 2.5B",
        ],
        "benefits": [
            "Work as PT PMA Director/Commissioner",
            "Multiple entry/exit Indonesia",
            "No minimum stay requirement",
            "Path to KITAP after 4-5 years",
        ],
        "restrictions": [
            "Must own shares or hold position in PT PMA",
            "Min capital IDR 10B for E28A category",
        ],
        "metadata": {
            "series": "E",
            "bali_zero_service": True,
            "bali_zero_recommended": True,
            "difficulty": "medium",
            "bali_zero_price_offshore": "IDR 17,000,000",
            "bali_zero_price_onshore": "IDR 19,000,000",
            "bali_zero_price_extension": "IDR 18,000,000",
        },
    },
    {
        "code": "E28B",
        "name": "Investor KITAS (Company Establishment)",
        "category": "KITAS",
        "duration": "2 years",
        "total_stay": "2 years (renewable)",
        "renewable": True,
        "processing_time_normal": "7-10 days",
        "cost_visa": "IDR 17,000,000",
        "requirements": [
            "Passport valid min 18 months",
            "Investment plan",
            "Bank statement showing capital",
            "Company establishment documents",
        ],
        "benefits": [
            "Establish new PT PMA",
            "Multiple entry/exit",
            "Work as company executive",
        ],
        "metadata": {"series": "E", "bali_zero_service": True},
    },
    {
        "code": "E28C",
        "name": "Investor KITAS (Portfolio Investment USD 350k+)",
        "category": "KITAS",
        "duration": "5 years",
        "total_stay": "5 years (renewable)",
        "renewable": True,
        "processing_time_normal": "7-10 days",
        "cost_visa": "Contact Bali Zero",
        "requirements": [
            "Passport valid min 6 years",
            "Portfolio investment min USD 350,000",
            "Investment in Indonesian stocks/bonds",
            "Bank statement proof",
        ],
        "benefits": [
            "5-year validity (Golden Visa)",
            "No company establishment required",
            "Multiple entry/exit",
        ],
        "metadata": {
            "series": "E",
            "bali_zero_service": True,
            "new_visa": True,
            "golden_visa": True,
        },
    },

    # --- E29 - Research KITAS ---
    {
        "code": "E29",
        "name": "Research KITAS (BRIN Permit)",
        "category": "KITAS",
        "duration": "1-2 years",
        "total_stay": "Project-based",
        "renewable": True,
        "processing_time_normal": "7-10 days",
        "cost_visa": "Contact Bali Zero",
        "requirements": [
            "Passport valid min 18 months",
            "BRIN research permit",
            "University/institution affiliation",
            "Research proposal",
        ],
        "benefits": [
            "Conduct research in Indonesia",
            "Access to research sites",
            "University collaboration",
        ],
        "metadata": {"series": "E", "bali_zero_service": True},
    },

    # --- E30 - Student KITAS ---
    {
        "code": "E30A",
        "name": "Student KITAS",
        "category": "KITAS",
        "duration": "1 year",
        "total_stay": "Study period",
        "renewable": True,
        "processing_time_normal": "7-10 days",
        "cost_visa": "IDR 8,000,000",
        "requirements": [
            "Passport valid min 18 months",
            "Acceptance letter from Indonesian institution",
            "Bank statement (funds for study)",
            "Sponsor letter from institution",
        ],
        "benefits": [
            "Full-time study in Indonesia",
            "Can work part-time (with permit)",
        ],
        "metadata": {"series": "E", "bali_zero_service": True},
    },

    # --- E31 - Family/Dependent KITAS ---
    {
        "code": "E31",
        "name": "Dependent KITAS (Family of KITAS Holder)",
        "category": "KITAS",
        "duration": "Matches sponsor",
        "total_stay": "Matches sponsor KITAS",
        "renewable": True,
        "processing_time_normal": "7-10 days",
        "cost_visa": "IDR 15,000,000 (offshore) / IDR 18,000,000 (onshore)",
        "cost_extension": "IDR 14,000,000",
        "requirements": [
            "Passport valid min 18 months",
            "Photo 4x6 red background",
            "Sponsor's valid KITAS",
            "Family relationship proof (marriage/birth certificate)",
            "Sponsor's passport copy",
        ],
        "benefits": [
            "Live with family in Indonesia",
            "Duration matches sponsor",
            "Multiple entry/exit",
        ],
        "metadata": {
            "series": "E",
            "bali_zero_service": True,
            "bali_zero_price_offshore": "IDR 15,000,000",
            "bali_zero_price_onshore": "IDR 18,000,000",
        },
    },

    # --- E32 - Ex-Indonesian KITAS ---
    {
        "code": "E32B",
        "name": "Ex-Indonesian Citizen KITAS (1st/2nd Degree)",
        "category": "KITAS",
        "duration": "2 years",
        "total_stay": "2 years (renewable)",
        "renewable": True,
        "processing_time_normal": "7-10 days",
        "cost_visa": "IDR 12,000,000",
        "requirements": [
            "Passport valid min 18 months",
            "Proof of former Indonesian citizenship",
            "Family documents (if applicable)",
        ],
        "benefits": [
            "Reconnect with Indonesian roots",
            "Path to KITAP",
            "Multiple entry/exit",
        ],
        "metadata": {"series": "E", "bali_zero_service": True},
    },

    # --- E33 - Special Categories ---
    {
        "code": "E33E",
        "name": "Retirement KITAS (Lanjut Usia 55+)",
        "category": "KITAS",
        "duration": "1-5 years",
        "total_stay": "5 years (extendable to KITAP)",
        "renewable": True,
        "processing_time_normal": "7-10 days",
        "cost_visa": "IDR 18,000,000 (5 years all-inclusive)",
        "cost_extension": "IDR 15,000,000",
        "requirements": [
            "Passport valid min 6 years (for 5Y)",
            "Age 55+ years",
            "Photo 4x6 red background",
            "Pension proof or bank statement min USD 2,500/month",
            "Health insurance valid in Indonesia",
            "CV/Resume",
            "Statement not to work in Indonesia",
            "Accommodation proof (rental/ownership)",
        ],
        "benefits": [
            "5 years without annual renewals",
            "No local sponsor required",
            "Multiple entry/exit",
            "Path to KITAP after 5 years",
        ],
        "restrictions": [
            "Cannot work or conduct business",
            "Must maintain health insurance",
        ],
        "metadata": {
            "series": "E",
            "bali_zero_service": True,
            "bali_zero_recommended": True,
            "difficulty": "low",
            "bali_zero_price": "IDR 18,000,000",
        },
    },
    {
        "code": "E33F",
        "name": "Retirement KITAS (Pension 55+)",
        "category": "KITAS",
        "duration": "1 year",
        "total_stay": "1 year (extendable 5x, then KITAP)",
        "renewable": True,
        "processing_time_normal": "7-10 days",
        "cost_visa": "IDR 14,000,000 (first year)",
        "cost_extension": "IDR 11,000,000 (renewals)",
        "requirements": [
            "Passport valid min 18 months",
            "Age 55+ years",
            "Photo 4x6 red background",
            "Pension proof min USD 1,500/month",
            "Health insurance",
            "CV/Resume",
            "Statement not to work",
        ],
        "benefits": [
            "No large upfront deposit required",
            "Lower financial threshold (USD 1,500 vs USD 3,000)",
            "Multiple entry/exit",
            "Annual renewal option",
        ],
        "metadata": {
            "series": "E",
            "bali_zero_service": True,
            "difficulty": "very_low",
            "bali_zero_price_first": "IDR 14,000,000",
            "bali_zero_price_renewal": "IDR 11,000,000",
        },
    },
    {
        "code": "E33G",
        "name": "Digital Nomad KITAS (Remote Worker)",
        "category": "KITAS",
        "duration": "1 year",
        "total_stay": "1 year (extendable annually)",
        "renewable": True,
        "processing_time_normal": "7-10 days",
        "cost_visa": "IDR 13,000,000 (offshore) / IDR 14,000,000 (onshore)",
        "cost_extension": "IDR 10,000,000",
        "requirements": [
            "Passport valid min 18 months",
            "Photo 4x6 red background",
            "Proof of remote work (employment letter/contract)",
            "Proof of income min USD 5,000/month (USD 60,000/year)",
            "Bank statement 3 months",
            "Travel/health insurance",
            "CV/Resume",
        ],
        "benefits": [
            "Work remotely for foreign companies",
            "Multiple entry/exit Indonesia",
            "No IMTA/RPTKA work permit needed",
            "No Indonesian sponsor required",
            "Path to KITAP after 4-5 years",
        ],
        "restrictions": [
            "Cannot work for Indonesian companies",
            "Income must be from abroad",
        ],
        "metadata": {
            "series": "E",
            "bali_zero_service": True,
            "bali_zero_recommended": True,
            "popularity": "very_high",
            "difficulty": "low",
            "bali_zero_price_offshore": "IDR 13,000,000",
            "bali_zero_price_onshore": "IDR 14,000,000",
            "bali_zero_price_extension": "IDR 10,000,000",
            "tax_note": "No tax obligation if income from abroad + transferred to foreign account",
        },
    },

    # --- E35 - Second Home Visa ---
    {
        "code": "E35",
        "name": "Second Home Visa (USD 130k+)",
        "category": "KITAS",
        "duration": "5-10 years",
        "total_stay": "10 years max",
        "renewable": True,
        "processing_time_normal": "7-10 days",
        "cost_visa": "Contact Bali Zero",
        "requirements": [
            "Passport valid min 10 years",
            "Bank deposit min USD 130,000 in Indonesian bank",
            "Health insurance",
            "Clean criminal record",
        ],
        "benefits": [
            "Up to 10 years stay",
            "Bring family members",
            "Multiple entry/exit",
            "No sponsor required",
        ],
        "restrictions": [
            "Cannot work",
            "Deposit locked for visa duration",
        ],
        "metadata": {
            "series": "E",
            "bali_zero_service": True,
            "new_visa": True,
            "golden_visa": True,
        },
    },

    # ==========================================================================
    # SERIES F - VISA ON ARRIVAL (Special Countries)
    # ==========================================================================
    {
        "code": "F1",
        "name": "Visa on Arrival (Special Countries)",
        "category": "VOA",
        "duration": "30 days",
        "total_stay": "60 days with extension",
        "renewable": True,
        "processing_time_normal": "On arrival",
        "cost_visa": "IDR 500,000",
        "requirements": [
            "Passport valid min 6 months",
            "Return ticket",
            "From eligible country",
        ],
        "benefits": [
            "Quick entry at airport",
            "Extendable once",
        ],
        "metadata": {"series": "F", "bali_zero_service": False},
    },

    # ==========================================================================
    # KITAP (Permanent Stay Permit)
    # ==========================================================================
    {
        "code": "KITAP",
        "name": "KITAP (Permanent Stay Permit)",
        "category": "KITAP",
        "duration": "5 years",
        "total_stay": "Permanent (renewable every 5 years)",
        "renewable": True,
        "processing_time_normal": "7-10 days",
        "cost_visa": "IDR 25,000,000",
        "cost_extension": "IDR 20,000,000 (every 5 years)",
        "requirements": [
            "Valid KITAS for 4-5 consecutive years",
            "Clean immigration record",
            "Current KITAS still valid",
            "All previous KITAS documents",
            "Tax compliance (if applicable)",
        ],
        "benefits": [
            "5-year validity",
            "No more annual renewals",
            "Multiple entry/exit",
            "Can apply for Indonesian drivers license",
            "Easier banking access",
        ],
        "metadata": {
            "series": "KITAP",
            "bali_zero_service": True,
            "bali_zero_price": "IDR 25,000,000",
        },
    },
]


async def seed_visa_types():
    """Seed all visa types into database"""
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    try:
        # Clear existing data
        await conn.execute("DELETE FROM visa_types")
        print("Cleared existing visa_types")

        # Insert new data
        for visa in VISA_TYPES:
            await conn.execute(
                """
                INSERT INTO visa_types (
                    code, name, category, duration, extensions, total_stay, renewable,
                    processing_time_normal, processing_time_express, processing_timeline,
                    cost_visa, cost_extension, cost_details,
                    requirements, restrictions, allowed_activities, benefits, process_steps, tips,
                    foreign_eligible, metadata, created_at, last_updated
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                    $14, $15, $16, $17, $18, $19, $20, $21, NOW(), NOW()
                )
                """,
                visa.get("code"),
                visa.get("name"),
                visa.get("category"),
                visa.get("duration"),
                visa.get("extensions"),
                visa.get("total_stay"),
                visa.get("renewable", False),
                visa.get("processing_time_normal"),
                visa.get("processing_time_express"),
                json.dumps(visa.get("processing_timeline")) if visa.get("processing_timeline") else None,
                visa.get("cost_visa"),
                visa.get("cost_extension"),
                json.dumps(visa.get("cost_details")) if visa.get("cost_details") else None,
                visa.get("requirements", []),
                visa.get("restrictions", []),
                visa.get("allowed_activities", []),
                visa.get("benefits", []),
                visa.get("process_steps", []),
                visa.get("tips", []),
                visa.get("foreign_eligible", True),
                json.dumps(visa.get("metadata")) if visa.get("metadata") else None,
            )
            print(f"  + {visa['code']}: {visa['name']}")

        # Get count
        count = await conn.fetchval("SELECT COUNT(*) FROM visa_types")
        print(f"\nTotal visa types seeded: {count}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_visa_types())
