"""
Seed Visa Types Data - CORRECTED
Based on official imigrasi.go.id classification and training data

Run with:
    fly ssh console -a nuzantara-rag -C "python3 /app/backend/migrations/seed_visa_types.py"
"""

import asyncio
import json
import os

import asyncpg

# =============================================================================
# Visa Types Data - Official Indonesian Immigration Codes
# Source: imigrasi.go.id + training-data/visa/*
# =============================================================================

VISA_TYPES = [
    # =========================================================================
    # D Series - Visa Kunjungan (Visit Visa - Short Term)
    # =========================================================================
    {
        "code": "D1",
        "name": "D1 Tourism Multiple Entry Visa",
        "category": "Visit",
        "duration": "5 years validity",
        "extensions": "Not extendable per entry",
        "total_stay": "60 days per entry (unlimited entries)",
        "renewable": True,
        "processing_time_normal": "5-7 working days",
        "processing_time_express": "3-5 working days",
        "cost_visa": "IDR 5,500,000",
        "cost_extension": "N/A (exit and re-enter)",
        "cost_details": {
            "government_fees": "IDR 2,000,000",
            "service_fee": "IDR 3,500,000"
        },
        "requirements": [
            "Valid passport (min 6 months validity)",
            "Bank statement (min USD 5,000)",
            "Return/onward ticket",
            "Accommodation proof",
            "Passport photos 4x6"
        ],
        "restrictions": [
            "Cannot work or earn income in Indonesia",
            "Max 60 days per entry - must exit and re-enter",
            "Cannot convert to KITAS directly"
        ],
        "allowed_activities": [
            "Tourism",
            "Family visits",
            "Social activities"
        ],
        "benefits": [
            "5-year validity - no yearly renewals",
            "Unlimited entries",
            "Perfect for frequent travelers"
        ],
        "process_steps": [
            "1. Apply online via evisa.imigrasi.go.id",
            "2. Upload documents",
            "3. Pay visa fee",
            "4. Receive e-Visa",
            "5. Enter Indonesia (60 days max per entry)"
        ],
        "tips": [
            "Best for those visiting Indonesia 3-4x per year",
            "Do visa run to Singapore/Malaysia to reset 60-day counter",
            "Compare with E33G if need longer continuous stay"
        ],
        "foreign_eligible": True,
        "metadata": {
            "popularity": "high",
            "difficulty": "low",
            "source": "training-data/visa/visa_004_d1_tourism_multiple_entry.md"
        }
    },
    {
        "code": "D12",
        "name": "D12 Business Investigation Visa (Pre-Investment)",
        "category": "Visit",
        "duration": "1-2 years validity",
        "extensions": "1x extension per entry (60 days)",
        "total_stay": "180 days per entry + 60 days extension",
        "renewable": False,
        "processing_time_normal": "7-10 working days",
        "processing_time_express": "5-7 working days",
        "cost_visa": "IDR 7,500,000 (1yr) / IDR 10,000,000 (2yr)",
        "cost_extension": "IDR 1,500,000",
        "cost_details": {
            "1_year": "IDR 7,500,000",
            "2_years": "IDR 10,000,000",
            "extension": "IDR 1,500,000"
        },
        "requirements": [
            "Valid passport (min 18 months validity)",
            "Business plan or investment proposal",
            "Sponsor letter from Indonesian company",
            "Bank statement showing sufficient funds",
            "CV/Resume"
        ],
        "restrictions": [
            "Cannot work or earn income",
            "Investigation/survey purposes only",
            "Must have Indonesian sponsor"
        ],
        "allowed_activities": [
            "Market research",
            "Feasibility studies",
            "Site visits",
            "Meeting potential partners",
            "Business investigation"
        ],
        "benefits": [
            "180 days per entry (NOT 60 days!)",
            "Multiple entry",
            "Perfect for pre-PT PMA setup phase"
        ],
        "process_steps": [
            "1. Find Indonesian sponsor company",
            "2. Prepare business proposal",
            "3. Apply via sponsor's evisa account",
            "4. Receive approval",
            "5. Enter Indonesia"
        ],
        "tips": [
            "Use this BEFORE setting up PT PMA",
            "180 days is longest visit visa stay",
            "Can extend once for additional 60 days"
        ],
        "foreign_eligible": True,
        "metadata": {
            "popularity": "medium",
            "difficulty": "medium",
            "source": "training-data/visa/visa_005_d12_business_investigation.md"
        }
    },
    # =========================================================================
    # E28 Series - KITAS Investor
    # =========================================================================
    {
        "code": "E28A",
        "name": "E28A Investor KITAS (PT PMA Director)",
        "category": "KITAS",
        "duration": "2 years",
        "extensions": "Extendable",
        "total_stay": "Up to 5 years, then convert to KITAP",
        "renewable": True,
        "processing_time_normal": "3-4 weeks after PT PMA setup",
        "processing_time_express": "2-3 weeks",
        "cost_visa": "IDR 25,000,000",
        "cost_extension": "IDR 15,000,000",
        "cost_details": {
            "government_fees": "IDR 10,000,000",
            "service_fee": "IDR 15,000,000"
        },
        "requirements": [
            "Active PT PMA company",
            "Akta pendirian PT (deed of incorporation)",
            "NIB (Nomor Induk Berusaha) aktif",
            "NPWP perusahaan",
            "SK Kemenkumham",
            "Proof of capital deposit (min Rp 2.5 miliar)",
            "Valid passport (min 18 months)",
            "Photo 4x6 red background",
            "CV/Resume",
            "Medical checkup",
            "Police clearance (apostille)"
        ],
        "restrictions": [
            "Tied to PT PMA sponsorship",
            "Must maintain active investment",
            "Cannot work outside sponsoring company"
        ],
        "allowed_activities": [
            "Managing PT PMA company",
            "Signing contracts",
            "Opening bank accounts",
            "Applying for driving license",
            "Property ownership via PT PMA"
        ],
        "benefits": [
            "2-year validity",
            "Multiple entry",
            "Full working rights in your company",
            "Path to KITAP after 4+ years",
            "Can sponsor family members"
        ],
        "process_steps": [
            "1. Complete PT PMA setup",
            "2. Prepare all company documents",
            "3. Apply for RPTKA approval",
            "4. Submit E28A application",
            "5. Biometric registration",
            "6. Receive KITAS card"
        ],
        "tips": [
            "PT PMA must be fully active before applying",
            "Capital must be deposited in company account",
            "IMTA not required for directors/commissioners"
        ],
        "foreign_eligible": True,
        "metadata": {
            "popularity": "high",
            "difficulty": "medium",
            "source": "training-data/visa/visa_003_e28a_investor_kitas.md"
        }
    },
    {
        "code": "E28C",
        "name": "E28C Investor KITAS (Portfolio - No PT)",
        "category": "KITAS",
        "duration": "5 years",
        "extensions": "Extendable",
        "total_stay": "5 years, renewable",
        "renewable": True,
        "processing_time_normal": "4-6 weeks",
        "processing_time_express": "3-4 weeks",
        "cost_visa": "IDR 35,000,000",
        "cost_extension": "IDR 25,000,000",
        "cost_details": {
            "government_fees": "IDR 15,000,000",
            "service_fee": "IDR 20,000,000",
            "investment_minimum": "USD 350,000"
        },
        "requirements": [
            "Valid passport (min 2 years validity)",
            "Commitment to invest min USD 350,000",
            "Investment in Indonesian stocks (Tbk) or government bonds",
            "Proof of funds",
            "Health insurance"
        ],
        "restrictions": [
            "Cannot work for Indonesian company",
            "Must complete investment within 90 days of entry",
            "Investment management only"
        ],
        "allowed_activities": [
            "Managing personal investments",
            "Buying/selling stocks and bonds",
            "Living in Indonesia"
        ],
        "benefits": [
            "No need to set up PT PMA",
            "5-year validity",
            "Multiple entry",
            "Portfolio investment option"
        ],
        "process_steps": [
            "1. Prepare proof of funds (USD 350k)",
            "2. Apply for E28C visa",
            "3. Enter Indonesia",
            "4. Complete investment within 90 days",
            "5. Maintain investment throughout visa validity"
        ],
        "tips": [
            "Good option if you don't want to run a company",
            "Investment must be maintained",
            "90-day deadline to invest after entry is strict"
        ],
        "foreign_eligible": True,
        "metadata": {
            "popularity": "low",
            "difficulty": "high",
            "financial_requirement": 350000,
            "source": "notebooklm_session1"
        }
    },
    # =========================================================================
    # E33 Series - Special Purpose KITAS
    # =========================================================================
    {
        "code": "E33G",
        "name": "E33G Digital Nomad KITAS",
        "category": "KITAS",
        "duration": "5 years",
        "extensions": "Extendable",
        "total_stay": "5 years continuous",
        "renewable": True,
        "processing_time_normal": "2-3 weeks",
        "processing_time_express": "1-2 weeks",
        "cost_visa": "IDR 18,000,000",
        "cost_extension": "IDR 12,000,000",
        "cost_details": {
            "government_fees": "IDR 8,000,000",
            "service_fee": "IDR 10,000,000"
        },
        "requirements": [
            "Valid passport (min 18 months validity)",
            "Photo 4x6 red background",
            "Proof of remote work (employment letter or contract)",
            "Proof of income min USD 2,000/month (3 months bank statements)",
            "Travel/health insurance valid in Indonesia",
            "CV/Resume"
        ],
        "restrictions": [
            "Cannot work for Indonesian company",
            "Income must come from abroad",
            "No local employment relationship"
        ],
        "allowed_activities": [
            "Remote work for foreign companies",
            "Freelancing for overseas clients",
            "Living in Indonesia long-term",
            "Opening bank accounts",
            "Renting property"
        ],
        "benefits": [
            "5-year validity",
            "Legal remote work status",
            "No Indonesian sponsor needed",
            "No IMTA/RPTKA required",
            "Multiple entry"
        ],
        "process_steps": [
            "1. Gather proof of remote income",
            "2. Apply online via evisa.imigrasi.go.id",
            "3. Upload documents",
            "4. Pay fee",
            "5. Receive e-Visa",
            "6. Enter Indonesia and convert to KITAS"
        ],
        "tips": [
            "Income can be gross, not net",
            "Bank statements should show regular deposits",
            "Perfect for freelancers and remote workers",
            "No need for Indonesian company sponsorship"
        ],
        "foreign_eligible": True,
        "metadata": {
            "popularity": "very_high",
            "difficulty": "low",
            "income_requirement": 2000,
            "source": "training-data/visa/visa_001_e33g_digital_nomad_basic.md"
        }
    },
    {
        "code": "E33E",
        "name": "E33E Retirement Visa (Lanjut Usia)",
        "category": "KITAS",
        "duration": "1-2 years",
        "extensions": "Unlimited extensions",
        "total_stay": "Unlimited (yearly renewal)",
        "renewable": True,
        "processing_time_normal": "3-4 weeks",
        "processing_time_express": "2-3 weeks",
        "cost_visa": "IDR 15,000,000",
        "cost_extension": "IDR 8,000,000",
        "cost_details": {
            "government_fees": "IDR 5,000,000",
            "service_fee": "IDR 10,000,000"
        },
        "requirements": [
            "Age 55 years or older",
            "Valid passport (min 18 months validity)",
            "Pension proof or bank statement (min USD 1,500/month)",
            "Health insurance valid in Indonesia",
            "Rental agreement (min 1 year)",
            "CV stating retirement purpose"
        ],
        "restrictions": [
            "Cannot work or conduct business",
            "Must maintain health insurance",
            "Rental accommodation required"
        ],
        "allowed_activities": [
            "Tourism and leisure",
            "Volunteer work (unpaid)",
            "Living in Indonesia"
        ],
        "benefits": [
            "Lower cost than Second Home Visa",
            "No large investment required",
            "Can sponsor spouse (any age)",
            "Peaceful retirement in Bali"
        ],
        "process_steps": [
            "1. Prepare pension/income proof",
            "2. Secure rental accommodation",
            "3. Get health insurance",
            "4. Apply for E33E visa",
            "5. Enter Indonesia",
            "6. Annual renewal"
        ],
        "tips": [
            "Budget for yearly renewals",
            "Health insurance is mandatory",
            "Choose areas with good healthcare",
            "Rental must be notarized"
        ],
        "foreign_eligible": True,
        "metadata": {
            "popularity": "medium",
            "difficulty": "low",
            "age_requirement": 55,
            "source": "notebooklm_session1"
        }
    },
    {
        "code": "E35",
        "name": "E35 Second Home Visa",
        "category": "KITAS",
        "duration": "5-10 years",
        "extensions": "One 5-year extension",
        "total_stay": "10 years maximum",
        "renewable": True,
        "processing_time_normal": "4-6 weeks",
        "processing_time_express": "3-4 weeks",
        "cost_visa": "IDR 35,000,000",
        "cost_extension": "IDR 30,000,000",
        "cost_details": {
            "government_fees": "IDR 15,000,000",
            "service_fee": "IDR 20,000,000",
            "financial_requirement": "USD 130,000"
        },
        "requirements": [
            "Valid passport (min 6 years validity recommended)",
            "Bank statement showing USD 130,000 or equivalent",
            "Health insurance valid in Indonesia",
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
            "5-10 year validity",
            "No yearly renewals",
            "Multiple entry",
            "Premium visa status",
            "No age restriction"
        ],
        "process_steps": [
            "1. Prepare proof of funds (USD 130,000)",
            "2. Secure health insurance",
            "3. Apply for Second Home Visa",
            "4. Receive approval",
            "5. Enter and activate KITAS"
        ],
        "tips": [
            "Best for wealthy digital nomads",
            "Can work remotely for overseas clients",
            "Consider tax implications",
            "5+ year passport validity essential"
        ],
        "foreign_eligible": True,
        "metadata": {
            "popularity": "high",
            "difficulty": "low",
            "financial_requirement": 130000,
            "source": "notebooklm_session1"
        }
    },
    # =========================================================================
    # E29 - Research Visa
    # =========================================================================
    {
        "code": "E29",
        "name": "E29 Research Visa (Penelitian)",
        "category": "KITAS",
        "duration": "1 year",
        "extensions": "Extendable",
        "total_stay": "Based on research project",
        "renewable": True,
        "processing_time_normal": "4-8 weeks",
        "processing_time_express": "3-4 weeks",
        "cost_visa": "IDR 12,000,000",
        "cost_extension": "IDR 8,000,000",
        "cost_details": {
            "government_fees": "IDR 5,000,000",
            "service_fee": "IDR 7,000,000"
        },
        "requirements": [
            "Valid passport (min 18 months)",
            "Research permit from BRIN (Badan Riset dan Inovasi Nasional)",
            "Sponsorship from Indonesian research institution",
            "Research proposal",
            "CV/Academic credentials"
        ],
        "restrictions": [
            "Research activities only",
            "Must have BRIN permit",
            "Cannot work commercially"
        ],
        "allowed_activities": [
            "Scientific research",
            "Field studies",
            "Academic collaboration",
            "Can bring family (E31 series)"
        ],
        "benefits": [
            "Legal research status",
            "Access to research sites",
            "Can sponsor family"
        ],
        "process_steps": [
            "1. Get BRIN research permit (mandatory)",
            "2. Find Indonesian research partner",
            "3. Apply for E29 visa",
            "4. Submit research proposal",
            "5. Receive approval"
        ],
        "tips": [
            "BRIN permit is MANDATORY - apply early",
            "Partner with local university",
            "Process can take months"
        ],
        "foreign_eligible": True,
        "metadata": {
            "popularity": "low",
            "difficulty": "high",
            "source": "notebooklm_session1"
        }
    },
    # =========================================================================
    # E31 Series - Family Visa
    # =========================================================================
    {
        "code": "E31B",
        "name": "E31B Family Visa (Spouse of ITAS/ITAP holder)",
        "category": "KITAS",
        "duration": "Matches sponsor's visa",
        "extensions": "Follows sponsor",
        "total_stay": "Based on sponsor's status",
        "renewable": True,
        "processing_time_normal": "2-3 weeks",
        "processing_time_express": "1-2 weeks",
        "cost_visa": "IDR 10,000,000",
        "cost_extension": "IDR 6,000,000",
        "cost_details": {
            "government_fees": "IDR 4,000,000",
            "service_fee": "IDR 6,000,000"
        },
        "requirements": [
            "Valid passport (min 18 months)",
            "Marriage certificate (legalized/apostille)",
            "Translation to Indonesian (sworn translator)",
            "Sponsor's KITAS/KITAP copy",
            "Sponsor letter"
        ],
        "restrictions": [
            "Cannot work without separate work permit",
            "Tied to sponsor's visa status",
            "Must live with sponsor"
        ],
        "allowed_activities": [
            "Accompanying spouse",
            "Living in Indonesia",
            "Opening bank accounts"
        ],
        "benefits": [
            "Stay with spouse legally",
            "Duration matches sponsor",
            "Can apply for work permit separately"
        ],
        "process_steps": [
            "1. Legalize marriage certificate",
            "2. Translate to Indonesian",
            "3. Sponsor applies on your behalf",
            "4. Submit documents",
            "5. Receive dependent KITAS"
        ],
        "tips": [
            "Marriage cert needs apostille + translation",
            "Sponsor's visa must be valid",
            "Can upgrade to work visa later"
        ],
        "foreign_eligible": True,
        "metadata": {
            "popularity": "high",
            "difficulty": "low",
            "source": "notebooklm_session1"
        }
    },
    # =========================================================================
    # VOA - Visa on Arrival
    # =========================================================================
    {
        "code": "VOA",
        "name": "Visa on Arrival (VOA)",
        "category": "Visit",
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
            "Valid passport (min 6 months)",
            "Return/onward ticket",
            "Payment (IDR 500,000)"
        ],
        "restrictions": [
            "Cannot work",
            "Only 1 extension",
            "Must exit after 60 days"
        ],
        "allowed_activities": [
            "Tourism",
            "Family visit",
            "Social activities"
        ],
        "benefits": [
            "No pre-arrangement needed",
            "Quick processing",
            "Available for 90+ countries"
        ],
        "process_steps": [
            "1. Arrive at airport",
            "2. Pay VOA fee at counter",
            "3. Receive stamp",
            "4. Extend at immigration if needed"
        ],
        "tips": [
            "Bring IDR cash if possible",
            "Extension takes 4-5 working days",
            "Consider C1 or D12 for longer stay"
        ],
        "foreign_eligible": True,
        "metadata": {
            "popularity": "very_high",
            "difficulty": "very_low"
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
        # Clear existing data
        await conn.execute("DELETE FROM visa_types")
        print("Cleared existing visa types")

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
        print(f"\n✅ Seeded {final_count} visa types with CORRECT codes!")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_visa_types())
