"""
Seed Visa Types Data
Professional visa cards for Bali Zero Knowledge Base

Run with:
    fly ssh console -a nuzantara-rag -C "python -m backend.migrations.seed_visa_types"
"""

import asyncio
import os
import json
from datetime import datetime

import asyncpg


# =============================================================================
# Visa Types Data - Bali Zero Professional Cards
# =============================================================================

VISA_TYPES = [
    # =========================================================================
    # KITAS - Work Permits
    # =========================================================================
    {
        "code": "KITAS-312",
        "name": "KITAS 312 - Investor Visa",
        "category": "KITAS",
        "duration": "1 year",
        "extensions": "Up to 4 extensions",
        "total_stay": "5 years maximum",
        "renewable": True,
        "processing_time_normal": "30-45 working days",
        "processing_time_express": "15-20 working days",
        "cost_visa": "IDR 25,000,000",
        "cost_extension": "IDR 12,000,000",
        "cost_details": {
            "government_fees": "IDR 8,500,000",
            "service_fee": "IDR 16,500,000",
            "express_surcharge": "IDR 5,000,000"
        },
        "requirements": [
            "Valid passport (min 18 months validity)",
            "Sponsor letter from PT PMA",
            "Company investment proof (min USD 1 billion IDR)",
            "RPTKA approval",
            "Police clearance certificate (SKCK)",
            "Health certificate",
            "Passport photos 4x6 (red background)",
            "CV/Resume in English",
            "Copy of company documents (NIB, NPWP, Akta)"
        ],
        "restrictions": [
            "Must maintain active investment",
            "Cannot work outside sponsoring company",
            "Must report to immigration every 90 days",
            "Cannot be converted to KITAP before 4 years"
        ],
        "allowed_activities": [
            "Managing your PT PMA company",
            "Signing contracts on behalf of company",
            "Opening bank accounts",
            "Applying for driving license",
            "Property ownership (HGB through company)"
        ],
        "benefits": [
            "Multiple entry visa",
            "Can sponsor family members",
            "Path to KITAP after 4 years",
            "Full working rights in your company",
            "Indonesian tax resident status"
        ],
        "process_steps": [
            "1. Company applies for RPTKA approval",
            "2. Immigration issues Telex visa approval",
            "3. Apply for visa at Indonesian Embassy",
            "4. Enter Indonesia and convert to KITAS",
            "5. Biometric registration at local immigration",
            "6. Receive KITAS card within 14 days"
        ],
        "tips": [
            "Start process 3 months before planned arrival",
            "Ensure company documents are up to date",
            "Budget for yearly extensions",
            "Keep digital copies of all documents",
            "Set reminder for 90-day reporting"
        ],
        "foreign_eligible": True,
        "metadata": {
            "popularity": "high",
            "difficulty": "medium",
            "bali_zero_recommended": True
        }
    },
    {
        "code": "KITAS-313",
        "name": "KITAS 313 - Work Visa (Employee)",
        "category": "KITAS",
        "duration": "1 year",
        "extensions": "Up to 4 extensions",
        "total_stay": "5 years maximum",
        "renewable": True,
        "processing_time_normal": "30-45 working days",
        "processing_time_express": "15-20 working days",
        "cost_visa": "IDR 22,000,000",
        "cost_extension": "IDR 10,000,000",
        "cost_details": {
            "government_fees": "IDR 7,500,000",
            "service_fee": "IDR 14,500,000",
            "dpkk_fee": "USD 1,200/year"
        },
        "requirements": [
            "Valid passport (min 18 months validity)",
            "Sponsor letter from employer (PT PMA)",
            "RPTKA approval for your position",
            "Employment contract",
            "Educational certificates (legalized)",
            "Work experience proof (min 5 years)",
            "Police clearance certificate",
            "Health certificate",
            "Passport photos 4x6 (red background)"
        ],
        "restrictions": [
            "Can only work for sponsoring company",
            "Position must match RPTKA approval",
            "Must train Indonesian replacement (TKA)",
            "Cannot freelance or side-work"
        ],
        "allowed_activities": [
            "Full-time employment at sponsor company",
            "Opening bank accounts",
            "Applying for driving license",
            "Renting property"
        ],
        "benefits": [
            "Multiple entry visa",
            "Can sponsor spouse and children",
            "Indonesian tax resident status",
            "Access to BPJS health insurance"
        ],
        "process_steps": [
            "1. Employer applies for RPTKA quota",
            "2. Submit employee documents for approval",
            "3. Immigration issues Telex visa",
            "4. Apply for visa at Embassy",
            "5. Enter Indonesia and convert to KITAS",
            "6. Register for IMTA work permit"
        ],
        "tips": [
            "Verify employer has valid RPTKA quota",
            "Educational certificates need Apostille",
            "DPKK fee is paid by employer annually",
            "Understand your tax obligations"
        ],
        "foreign_eligible": True,
        "metadata": {
            "popularity": "high",
            "difficulty": "medium"
        }
    },
    {
        "code": "KITAS-317",
        "name": "KITAS 317 - Retirement Visa",
        "category": "KITAS",
        "duration": "1 year",
        "extensions": "Unlimited extensions",
        "total_stay": "Unlimited (yearly renewal)",
        "renewable": True,
        "processing_time_normal": "30-45 working days",
        "processing_time_express": "15-20 working days",
        "cost_visa": "IDR 18,000,000",
        "cost_extension": "IDR 8,000,000",
        "cost_details": {
            "government_fees": "IDR 5,000,000",
            "service_fee": "IDR 13,000,000"
        },
        "requirements": [
            "Age 55 years or older",
            "Valid passport (min 18 months validity)",
            "Pension proof or bank statement (USD 1,500/month income)",
            "Health insurance valid in Indonesia",
            "Police clearance certificate",
            "Health certificate",
            "Rental agreement (min 1 year)",
            "CV stating retirement purpose",
            "Photo 4x6 (red background)"
        ],
        "restrictions": [
            "Cannot work or conduct business",
            "Cannot own property directly",
            "Must maintain health insurance",
            "Must employ Indonesian helper (1 person)"
        ],
        "allowed_activities": [
            "Tourism and leisure activities",
            "Volunteer work (unpaid)",
            "Opening bank accounts",
            "Long-term property rental"
        ],
        "benefits": [
            "Multiple entry visa",
            "Can sponsor spouse (any age)",
            "No investment required",
            "Peaceful retirement in Bali",
            "Lower cost of living"
        ],
        "process_steps": [
            "1. Prepare financial proof documents",
            "2. Secure rental accommodation",
            "3. Apply for Telex approval",
            "4. Get visa at Embassy",
            "5. Enter and convert to KITAS",
            "6. Annual renewal process"
        ],
        "tips": [
            "Health insurance is mandatory - budget accordingly",
            "Rental contract must be notarized",
            "Consider areas with good healthcare access",
            "Join expat retirement communities",
            "Bali Zero can help with accommodation search"
        ],
        "foreign_eligible": True,
        "metadata": {
            "popularity": "medium",
            "difficulty": "low",
            "age_requirement": 55,
            "bali_zero_recommended": True
        }
    },
    {
        "code": "KITAS-318",
        "name": "KITAS 318 - Second Home Visa",
        "category": "KITAS",
        "duration": "5 years",
        "extensions": "One 5-year extension",
        "total_stay": "10 years maximum",
        "renewable": True,
        "processing_time_normal": "30-45 working days",
        "processing_time_express": "20-25 working days",
        "cost_visa": "IDR 35,000,000",
        "cost_extension": "IDR 30,000,000",
        "cost_details": {
            "government_fees": "IDR 15,000,000",
            "service_fee": "IDR 20,000,000"
        },
        "requirements": [
            "Valid passport (min 6 years validity recommended)",
            "Bank statement showing USD 130,000 or equivalent",
            "Health insurance valid in Indonesia",
            "Police clearance certificate",
            "Property ownership/rental proof",
            "No criminal record declaration"
        ],
        "restrictions": [
            "Cannot work locally",
            "Cannot conduct local business",
            "Must maintain financial requirements",
            "Annual reporting obligation"
        ],
        "allowed_activities": [
            "Living in Indonesia long-term",
            "Remote work for foreign companies",
            "Investment activities",
            "Property purchase through PT PMA",
            "Tourism and leisure"
        ],
        "benefits": [
            "5-year validity - no yearly renewals",
            "Multiple entry visa",
            "Can sponsor family members",
            "Premium visa status",
            "No age restriction"
        ],
        "process_steps": [
            "1. Prepare proof of funds (USD 130,000)",
            "2. Secure health insurance",
            "3. Apply for Telex approval",
            "4. Receive visa at Embassy",
            "5. Enter and activate KITAS",
            "6. Renew after 5 years"
        ],
        "tips": [
            "Best option for digital nomads with savings",
            "Can work remotely for overseas clients",
            "Consider tax implications in both countries",
            "5-year passport validity is essential",
            "Premium service available for faster processing"
        ],
        "foreign_eligible": True,
        "metadata": {
            "popularity": "high",
            "difficulty": "low",
            "financial_requirement": 130000,
            "bali_zero_recommended": True,
            "new_visa": True
        }
    },
    # =========================================================================
    # Tourist & Business Visas
    # =========================================================================
    {
        "code": "B211A",
        "name": "B211A - Social/Cultural Visa",
        "category": "Tourist",
        "duration": "60 days",
        "extensions": "Up to 4 extensions (30 days each)",
        "total_stay": "180 days maximum",
        "renewable": False,
        "processing_time_normal": "5-7 working days",
        "processing_time_express": "2-3 working days",
        "cost_visa": "IDR 5,500,000",
        "cost_extension": "IDR 1,500,000",
        "cost_details": {
            "government_fees": "IDR 2,000,000",
            "service_fee": "IDR 3,500,000",
            "extension_govt": "IDR 500,000",
            "extension_service": "IDR 1,000,000"
        },
        "requirements": [
            "Valid passport (min 6 months validity)",
            "Sponsor letter from Indonesian citizen/company",
            "Return flight booking",
            "Accommodation proof",
            "Bank statement (min USD 2,000)",
            "Passport photo 4x6 (white background)"
        ],
        "restrictions": [
            "Cannot work or earn income in Indonesia",
            "Cannot convert to KITAS directly",
            "Must exit after 180 days",
            "Single entry only"
        ],
        "allowed_activities": [
            "Tourism and leisure",
            "Visiting family/friends",
            "Attending courses (non-degree)",
            "Cultural activities",
            "Volunteer work"
        ],
        "benefits": [
            "Longer stay than visa on arrival",
            "Multiple extensions available",
            "Relatively easy to obtain",
            "Good for exploring Indonesia"
        ],
        "process_steps": [
            "1. Find a local sponsor",
            "2. Submit application online",
            "3. Receive Telex approval",
            "4. Apply at Embassy (if outside Indonesia)",
            "5. Enter Indonesia",
            "6. Extend at local immigration office"
        ],
        "tips": [
            "Start extension process 14 days before expiry",
            "Keep sponsor contact information handy",
            "Budget for all 4 extensions if planning long stay",
            "Bali Zero can provide sponsorship service"
        ],
        "foreign_eligible": True,
        "metadata": {
            "popularity": "very_high",
            "difficulty": "low",
            "bali_zero_recommended": True
        }
    },
    {
        "code": "VOA",
        "name": "Visa on Arrival (VOA)",
        "category": "Tourist",
        "duration": "30 days",
        "extensions": "1 extension (30 days)",
        "total_stay": "60 days maximum",
        "renewable": False,
        "processing_time_normal": "On arrival (30 minutes)",
        "processing_time_express": "N/A",
        "cost_visa": "IDR 500,000",
        "cost_extension": "IDR 1,500,000",
        "cost_details": {
            "visa_fee": "IDR 500,000",
            "extension_govt": "IDR 500,000",
            "extension_service": "IDR 1,000,000"
        },
        "requirements": [
            "Valid passport (min 6 months validity)",
            "Return/onward ticket",
            "Proof of accommodation (hotel booking)",
            "Payment (IDR 500,000 or USD equivalent)"
        ],
        "restrictions": [
            "Cannot work",
            "Only 1 extension allowed",
            "Must exit after 60 days",
            "Available at designated ports only"
        ],
        "allowed_activities": [
            "Tourism",
            "Family visit",
            "Social activities",
            "Transit"
        ],
        "benefits": [
            "No pre-arrangement needed",
            "Quick processing",
            "Available for 90+ countries",
            "Extendable once"
        ],
        "process_steps": [
            "1. Arrive at designated airport/seaport",
            "2. Pay VOA fee at counter",
            "3. Receive stamp in passport",
            "4. For extension: apply at immigration 7-14 days before expiry"
        ],
        "tips": [
            "Bring exact amount in IDR if possible",
            "Extension takes 4-5 working days",
            "Apply for extension early - offices get busy",
            "Consider B211A if planning longer stay"
        ],
        "foreign_eligible": True,
        "metadata": {
            "popularity": "very_high",
            "difficulty": "very_low"
        }
    },
    {
        "code": "EVOA",
        "name": "e-Visa on Arrival (e-VOA)",
        "category": "Tourist",
        "duration": "30 days",
        "extensions": "1 extension (30 days)",
        "total_stay": "60 days maximum",
        "renewable": False,
        "processing_time_normal": "Online (instant - 24 hours)",
        "processing_time_express": "N/A",
        "cost_visa": "IDR 500,000",
        "cost_extension": "IDR 1,500,000",
        "cost_details": {
            "visa_fee": "IDR 500,000",
            "extension_govt": "IDR 500,000",
            "extension_service": "IDR 1,000,000"
        },
        "requirements": [
            "Valid passport (min 6 months validity)",
            "Return/onward ticket",
            "Accommodation proof",
            "Credit card for payment"
        ],
        "restrictions": [
            "Cannot work",
            "Only 1 extension allowed",
            "Must exit after 60 days"
        ],
        "allowed_activities": [
            "Tourism",
            "Family visit",
            "Social activities"
        ],
        "benefits": [
            "Apply before arrival - skip queues",
            "Online extension available",
            "Digital record",
            "Same cost as regular VOA"
        ],
        "process_steps": [
            "1. Apply at molina.imigrasi.go.id",
            "2. Pay online with credit card",
            "3. Receive e-Visa via email",
            "4. Show QR code at immigration",
            "5. Extend online if needed"
        ],
        "tips": [
            "Apply 48 hours before travel",
            "Save e-Visa PDF offline",
            "Online extension is more convenient",
            "Check passport number carefully when applying"
        ],
        "foreign_eligible": True,
        "metadata": {
            "popularity": "very_high",
            "difficulty": "very_low"
        }
    },
    # =========================================================================
    # KITAP - Permanent Stay
    # =========================================================================
    {
        "code": "KITAP",
        "name": "KITAP - Permanent Stay Permit",
        "category": "KITAP",
        "duration": "5 years",
        "extensions": "Unlimited renewals",
        "total_stay": "Unlimited",
        "renewable": True,
        "processing_time_normal": "60-90 working days",
        "processing_time_express": "45-60 working days",
        "cost_visa": "IDR 30,000,000",
        "cost_extension": "IDR 25,000,000",
        "cost_details": {
            "government_fees": "IDR 12,000,000",
            "service_fee": "IDR 18,000,000"
        },
        "requirements": [
            "Held KITAS for minimum 4 consecutive years",
            "Valid passport (min 2 years validity)",
            "Proof of continued residence",
            "Indonesian language proficiency (basic)",
            "Knowledge of Pancasila and UUD 1945",
            "Sponsor letter",
            "Tax compliance proof",
            "Police clearance certificate"
        ],
        "restrictions": [
            "Must renew every 5 years",
            "Cannot be absent from Indonesia > 1 year",
            "Must maintain valid passport",
            "Subject to revocation if laws violated"
        ],
        "allowed_activities": [
            "All activities permitted under original KITAS",
            "More flexible work arrangements",
            "Property ownership (through company)",
            "Long-term business planning"
        ],
        "benefits": [
            "5-year validity",
            "No yearly renewals",
            "More stable immigration status",
            "Easier bank account opening",
            "Path to Indonesian citizenship (if eligible)"
        ],
        "process_steps": [
            "1. Complete 4 years on KITAS",
            "2. Pass Indonesian language test",
            "3. Complete Pancasila knowledge test",
            "4. Submit KITAP application",
            "5. Interview at immigration",
            "6. Receive KITAP card"
        ],
        "tips": [
            "Start Indonesian language lessons early",
            "Maintain continuous residence record",
            "Keep all tax documents organized",
            "Interview is usually straightforward",
            "Consider citizenship if married to Indonesian"
        ],
        "foreign_eligible": True,
        "metadata": {
            "popularity": "medium",
            "difficulty": "high",
            "prerequisite": "4 years KITAS"
        }
    },
    {
        "code": "KITAP-SPOUSE",
        "name": "KITAP Spouse - Indonesian Spouse",
        "category": "KITAP",
        "duration": "5 years",
        "extensions": "Unlimited renewals",
        "total_stay": "Unlimited",
        "renewable": True,
        "processing_time_normal": "45-60 working days",
        "processing_time_express": "30-45 working days",
        "cost_visa": "IDR 20,000,000",
        "cost_extension": "IDR 15,000,000",
        "cost_details": {
            "government_fees": "IDR 8,000,000",
            "service_fee": "IDR 12,000,000"
        },
        "requirements": [
            "Marriage certificate (legalized)",
            "Spouse's Indonesian ID (KTP)",
            "Valid passport (min 2 years validity)",
            "Proof of residence together",
            "Family card (Kartu Keluarga)",
            "Police clearance certificate",
            "Sponsor letter from spouse"
        ],
        "restrictions": [
            "Marriage must remain valid",
            "Must live with spouse",
            "Working requires separate IMTA",
            "Subject to divorce provisions"
        ],
        "allowed_activities": [
            "Living in Indonesia permanently",
            "Opening bank accounts",
            "Owning property (Hak Pakai)",
            "Working (with IMTA)",
            "Running business (with permits)"
        ],
        "benefits": [
            "Direct KITAP - no 4-year KITAS wait",
            "Property ownership rights",
            "Stable family status",
            "Path to citizenship after 5 years",
            "Children can have dual citizenship until 18"
        ],
        "process_steps": [
            "1. Legalize marriage certificate",
            "2. Register in Family Card (KK)",
            "3. Apply for KITAP at immigration",
            "4. Biometric registration",
            "5. Receive KITAP card"
        ],
        "tips": [
            "Marriage certificate needs Apostille + translation",
            "Update KK before applying",
            "Consider prenuptial agreement for property",
            "Work permit is separate application",
            "Children born in Indonesia have citizenship options"
        ],
        "foreign_eligible": True,
        "metadata": {
            "popularity": "high",
            "difficulty": "medium",
            "requirement": "Indonesian spouse"
        }
    }
]


async def seed_visa_types():
    """Insert visa types into database"""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    conn = await asyncpg.connect(database_url)

    try:
        # Check current count
        count = await conn.fetchval("SELECT COUNT(*) FROM visa_types")
        print(f"Current visa types in database: {count}")

        if count > 0:
            print("Visa types already exist. Clearing and re-seeding...")
            await conn.execute("DELETE FROM visa_types")

        # Insert each visa type
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
                visa["code"],
                visa["name"],
                visa["category"],
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

        # Final count
        final_count = await conn.fetchval("SELECT COUNT(*) FROM visa_types")
        print(f"\n✅ Seeded {final_count} visa types successfully!")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_visa_types())
