"""Enrich kbli_2025_final_hybrid with NB-3-validated company setup & licensing concepts.

Existing 4618 KBLI code points are high-quality — don't modify. ADD standalone
concept docs covering PT PMA setup, capital requirements, licensing tiers, DNI list,
popular Bali KBLI codes, and RPTKA/TKA hiring rules.

Source: NB-3 (Company Setup) query 2026-04-17.
References: UU 25/2007, UU 6/2023, PP 28/2025, Perpres 10/2021, Perpres 49/2021,
BKPM Reg 5/2025.

Run:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python ../../scripts/enrich_kbli_company_concepts.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from typing import Any

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("enrich_kbli")


def _load_env(key: str) -> str | None:
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "apps", "backend-rag", ".env",
    )
    try:
        with open(env_path) as fh:
            for line in fh:
                line = line.strip()
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        return None
    return None


QDRANT_URL = os.environ.get(
    "QDRANT_URL",
    "https://5575d2b7-d895-4697-86e5-5c7ceae3ca74.us-east4-0.gcp.cloud.qdrant.io:6333",
)
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY") or _load_env("QDRANT_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or _load_env("OPENAI_API_KEY")
COLLECTION = "kbli_2025_final_hybrid"
EMBEDDING_MODEL = "text-embedding-3-small"


CONCEPT_DOCS: list[dict[str, Any]] = [
    {
        "concept_id": "nb3-pt-pma-setup",
        "title": "PT PMA Setup — Complete Step-by-Step Guide (Indonesia 2025-2026)",
        "category": "company_setup",
        "subcategory": "pt_pma",
        "text": """[CONTEXT: Indonesia Company Setup 2025-2026 — Concept: PT PMA Setup]

# PT PMA (Perseroan Terbatas Penanaman Modal Asing) — Setup Guide

## What is a PT PMA
The only legal entity structure allowing foreign investors to own shares in Indonesia. Regulated by UU 40/2007 (Companies), UU 25/2007 (Investment), and UU 6/2023 (Job Creation / Omnibus Law).

## Requirements
- **Minimum 2 shareholders** (individuals or companies), at least 1 foreigner for PMA status
- **Minimum 1 Direktur** (director) and **1 Komisaris** (commissioner) — can be the same person in small PT
- **Commercial address** required (zona komersial, NOT residential). Virtual office accepted for low/medium-low risk KBLI only.

## Step-by-Step Process

### Step 1 — Akta Pendirian (Deed of Establishment)
Notary (Notaris) drafts the deed in Bahasa Indonesia containing: company name, address, business activities (KBLI codes), capital structure, shareholder identities with percentages, directors and commissioners.

### Step 2 — SK Kemenkumham (Ministry Approval)
Notary submits via AHU Online (notariatahu.go.id). Ministry of Law and Human Rights issues approval decree (SK) within 14 working days. From this date, PT PMA is a legal entity (badan hukum).

### Step 3 — NPWP Badan (Corporate Tax ID)
Register at local KPP (Tax Office) or via e-Registration. Must be obtained within 1 month of starting business activity.

### Step 4 — NIB via OSS (Business Identification Number)
Register on oss.go.id. The OSS system issues NIB automatically, which replaces old TDP, API, and customs access permits. Declare investment plan (Rencana Penanaman Modal) including KBLI codes.

### Step 5 — Sector Licensing (Risk-Based)
OSS RBA (PP 28/2025) classifies each KBLI into risk levels and assigns licensing requirements automatically. See "Licensing Tiers" concept document.

### Step 6 — Bank Account & Capital Deposit
Open corporate bank account in PT PMA name. Deposit minimum paid-up capital (see Capital Requirements).

## Timeline
| Phase | Duration |
|---|---|
| Document preparation + Notary | 3-5 days |
| SK Kemenkumham | 5-10 working days |
| NPWP Badan | 1-2 days |
| NIB via OSS | 1 day (automatic) |
| Sector licenses | 3-14 days (risk-dependent) |
| Bank account opening | 3-7 days |
| **Total (start to operational PT)** | **2-3 weeks** |

## KBLI Selection
- PT PMA can register multiple KBLI codes (primary + supporting)
- Each 5-digit KBLI code per location requires Rp 10 billion total investment plan
- Supporting KBLI codes mandatory to declare (BKPM 5/2025)
- Changing KBLI after incorporation requires: RUPS (shareholder meeting) → Akta Perubahan (notary) → Kemenkumham approval → OSS update. Takes 2-4 weeks.

## PT PMA = Large Enterprise by Law
Foreign investment companies are automatically classified as "Usaha Besar" (large enterprise). Cannot enter UMKM (micro/small/medium) segment. This is deliberate policy to protect local entrepreneurs.

## Legal basis
- UU No. 40/2007 (Companies)
- UU No. 25/2007 (Investment)
- UU No. 6/2023 (Job Creation / Omnibus Law)
- PP No. 28/2025 (Risk-Based Licensing — replaces PP 5/2021)
- BKPM Regulation No. 5/2025 (Capital requirements)
""",
    },
    {
        "concept_id": "nb3-capital-requirements",
        "title": "PT PMA Capital Requirements 2025 (BKPM 5/2025)",
        "category": "company_setup",
        "subcategory": "capital",
        "text": """[CONTEXT: Indonesia Company Setup 2025-2026 — Concept: Capital Requirements]

# PT PMA Capital Requirements (Updated BKPM Regulation 5/2025)

## Key change: paid-up capital REDUCED from Rp 10 billion to Rp 2.5 billion
Effective 2 October 2025, BKPM Regulation No. 5/2025 significantly lowered the barrier:

| Requirement | Before BKPM 5/2025 | After BKPM 5/2025 |
|---|---|---|
| **Minimum paid-up capital** | Rp 10 billion | **Rp 2.5 billion** (~USD 150,000) |
| **Total investment value** (per KBLI per location) | >Rp 10 billion | >Rp 10 billion (unchanged) |
| **Capital lock period** | Not specified | **12 months minimum** (Art. 27) |
| **Land/building value** inclusion | Excluded | Included for property/accommodation |

## Modal Dasar vs Modal Disetor

- **Modal Dasar (Authorized Capital)**: Rp 10 billion minimum for PT PMA (stated in Akta but not fully paid upfront)
- **Modal Disetor (Paid-up Capital)**: Rp 2.5 billion minimum — must be physically deposited in the company's Indonesian bank account

For comparison, PT Lokal (domestic) only requires Rp 50 million Modal Dasar.

## Total Investment Value
- Must exceed **Rp 10 billion per 5-digit KBLI code per project location**
- Includes: paid-up capital + property acquisition + construction + renovation + equipment + working capital
- For property/accommodation sectors: land and building values COUNT toward the total
- Realized progressively over time — you do NOT need Rp 10 billion in cash at incorporation

## Capital Locking (12-month rule)
The Rp 2.5 billion paid-up capital must remain in the corporate bank account for at least 12 months. During this period, funds may ONLY be used for:
- Equipment purchases
- Facility development
- Employee salaries
- Office rent and utilities

**Strictly PROHIBITED**: transferring funds back to shareholders. Violation → license revocation.

## Practical example
Foreigner setting up PT PMA for a villa in Bali:
- Deposit Rp 2.5 billion as paid-up capital
- Villa purchase: Rp 5 billion + renovation: Rp 3 billion
- Total investment: Rp 10.5 billion (including paid-up capital) → satisfies both requirements

## UMKM exception: does NOT exist for PT PMA
The 0.5% final tax regime (PP 55/2022) for businesses with revenue <Rp 4.8 billion is available for PT (max 3 years), but PT PMA effectively NEVER qualifies because:
- Rp 10 billion minimum capital is incompatible with micro/small classification
- PT PMA = automatically "Usaha Besar" (large enterprise) by law

## Legal basis
- Perpres No. 49/2021 (Modal Dasar minimum)
- BKPM Regulation No. 5/2025 (Modal Disetor reduction + capital locking)
- PP No. 28/2025 (OSS-RBA implementation)
""",
    },
    {
        "concept_id": "nb3-licensing-tiers",
        "title": "Business Licensing Tiers — OSS Risk-Based Approach (PP 28/2025)",
        "category": "licensing",
        "subcategory": "oss_rba",
        "text": """[CONTEXT: Indonesia Company Setup 2025-2026 — Concept: Licensing Tiers]

# Business Licensing Tiers — OSS Risk-Based Approach (RBA)

## The system (PP 28/2025, replacing PP 5/2021)

Every business activity (KBLI code) is classified into one of 4 risk levels. The risk level determines what licenses are required before the company can operate.

## Level 1 — RISIKO RENDAH (Low Risk)
- **License**: NIB only (serves as full operating license)
- **Process**: immediate automatic approval
- **Examples**: KBLI 70201 (Business Consulting), 62010 (Software Development), 74300 (Translation/Interpretation)
- **PMA status**: typically TERBUKA (100% foreign ownership allowed)

## Level 2 — RISIKO MENENGAH RENDAH (Medium-Low Risk)
- **License**: NIB + Sertifikat Standar (self-declaration)
- **Process**: certificate generated automatically after entrepreneur declares compliance with standards
- **No government verification before start** — operations can begin immediately
- **Examples**: KBLI 56101 (Restaurant), 56103 (Bar), certain retail activities
- **PMA status**: varies by KBLI

## Level 3 — RISIKO MENENGAH TINGGI (Medium-High Risk)
- **License**: NIB + Sertifikat Standar (government-verified)
- **Process**: government inspectors must verify standards compliance BEFORE operations can begin. 3-14 working days.
- **Examples**: KBLI 55193 (Commercial Villa Rental), 55203, food manufacturing
- **PMA status**: varies

## Level 4 — RISIKO TINGGI (High Risk)
- **License**: NIB + Izin (formal license from competent ministry/authority)
- **Process**: extensive documentation, government review, technical certifications, potentially AMDAL (environmental impact assessment). 30-60 days.
- **Examples**: KBLI 86102 (Specialist Clinic), mining, healthcare, financial services
- **PMA status**: often TERBATAS (restricted foreign ownership %)

## Fiktif Positif (Automatic Approval)
PP 28/2025 enforces Service Level Agreements (SLAs) with binding processing times. If the government agency fails to respond within the deadline, the license is **automatically approved** (fictitious positive principle).

## Important: Risk level ≠ PMA restriction
A KBLI can be TERBUKA (100% PMA allowed) but still require high-risk licensing (e.g., KBLI 86102 clinic = TERBATAS 67% PMA + high-risk licensing). These are two separate classification systems.

## OSS processing times
| Risk Level | Typical Timeline |
|---|---|
| Low | Immediate |
| Medium-Low | Immediate (self-declaration) |
| Medium-High | 7-14 days |
| High | 30-60 days |

## Virtual office compatibility
- Low risk + Medium-Low risk: virtual office in commercial zone accepted
- Medium-High + High risk: physical office generally required (inspectors need to visit)

## Legal basis
- PP No. 28/2025 (Risk-Based Business Licensing)
- UU No. 6/2023 (Job Creation / Omnibus Law)
""",
    },
    {
        "concept_id": "nb3-positive-investment-list",
        "title": "Positive Investment List — Foreign Ownership Restrictions (Perpres 10/2021)",
        "category": "investment_restrictions",
        "subcategory": "dni_positive_list",
        "text": """[CONTEXT: Indonesia Company Setup 2025-2026 — Concept: Investment Restrictions]

# Positive Investment List (Perpres 10/2021 + Perpres 49/2021)

## From DNI to Positive List
The old Daftar Negatif Investasi (Negative Investment List) was replaced by the Positive Investment List under the Omnibus Law. The new principle: **all sectors are OPEN by default**, unless explicitly restricted.

## Three categories

### TERBUKA (Open — 100% PMA allowed)
No restriction on foreign ownership. Foreigner can own 100% of the PT PMA.

**Popular TERBUKA KBLI codes for Bali Zero clients:**
| KBLI | Activity | Risk Level |
|---|---|---|
| 55193 | Villa Rental (commercial) | Medium-High |
| 55203 | Villa Rental (variant) | Medium-High |
| 56101 | Restaurant | Medium-Low |
| 56103 | Bar | Medium-Low |
| 56301 | Cafe | Medium-Low |
| 70201 | Business Consulting | Low |
| 62010 | Software Development / IT | Low |
| 74300 | Translation / Interpretation | Low |
| 73209 | Digital Marketing | Low-Medium |
| 68110 | Real Estate (own property management) | Medium-High |

### TERBATAS (Restricted — partial foreign ownership)
Foreign ownership allowed but capped at a specific percentage. Indonesian partner (WNI) must hold the remainder.

**Key TERBATAS codes relevant to Bali:**
| KBLI | Activity | Max Foreign % |
|---|---|---|
| 73100 | Advertising Agency | 49% |
| 74200 | Commercial Photography | 49% |
| 86101 | General Hospital | 67% |
| 86102 | Specialist Clinic | 67% |
| 86103 | Inpatient Clinic | 67% |
| 41011 | Building Construction | 67% |
| 47211 | Pharmacy Retail | 67% |

### TERTUTUP (Closed — 0% foreign ownership)
Completely reserved for Indonesian citizens (WNI), cooperatives, or UMKM. Foreigners cannot own any shares.

**Key TERTUTUP codes (common mistakes by expats in Bali):**
| KBLI | Activity | Why closed |
|---|---|---|
| **55130** | **Pondok Wisata / Homestay** | Reserved for WNI — the #1 mistake expats make trying to rent out a guesthouse |
| 47111 | Minimarket | Reserved for UMKM |
| 47112 | Supermarket (small) | Reserved for UMKM |
| 01111 | Rice cultivation | Reserved for WNI |
| 69100 | Legal services | Reserved for Indonesian lawyers |

**Critical warning**: KBLI 55130 (Pondok Wisata / Homestay) is CLOSED to foreigners. If you want to rent villas to tourists, use KBLI 55193 (Villa) instead — this is TERBUKA 100%.

## Partnership (Kemitraan) requirement
Mandatory when:
- Operating in TERBATAS sector (WNI partner needed to reach 100% capital)
- Activity is designated as "open to large enterprise in partnership with UMKM"
- Example: KBLI 73100 Advertising requires partnership structure

## Changing KBLI restrictions
Perpres 10/2021 can be amended by presidential regulation. Always verify current status before incorporation. Bali Zero checks against the latest version at time of filing.

## Legal basis
- Perpres No. 10/2021 (Positive Investment List)
- Perpres No. 49/2021 (Amendment — capital minimums)
- UU No. 25/2007 (Investment Law)
- UU No. 6/2023 (Job Creation / Omnibus Law)
""",
    },
    {
        "concept_id": "nb3-popular-bali-kbli",
        "title": "Popular KBLI Codes for Expats in Bali — Business Guide",
        "category": "kbli_guide",
        "subcategory": "bali_popular",
        "text": """[CONTEXT: Indonesia Company Setup 2025-2026 — Concept: Popular KBLI for Bali]

# Popular KBLI Codes for Expat Businesses in Bali

## Restaurant & F&B
| KBLI | Name | PMA | Risk | Notes |
|---|---|---|---|---|
| 56101 | Restoran (Restaurant) | TERBUKA 100% | Medium-Low | Most common F&B code |
| 56103 | Bar | TERBUKA 100% | Medium-Low | Separate from restaurant |
| 56301 | Kafe (Cafe) | TERBUKA 100% | Medium-Low | Coffee shops, juice bars |
| 56210 | Jasa Boga (Catering) | TERBUKA 100% | Medium-Low | Event catering |

## Accommodation & Property
| KBLI | Name | PMA | Risk | Notes |
|---|---|---|---|---|
| 55193 | Villa (Commercial Rental) | TERBUKA 100% | Medium-High | Correct code for tourist villa rental |
| 55203 | Villa (variant) | TERBUKA 100% | Medium-High | Alternative villa code |
| 55110 | Hotel Bintang (Star Hotel) | TERBUKA 100% | High | Full hotel operations |
| 68110 | Real Estate (own property) | TERBUKA 100% | Medium-High | Hold + manage own property |
| **55130** | **Pondok Wisata / Homestay** | **TERTUTUP** | — | **CLOSED to foreigners — use 55193 instead** |

## Consulting & Professional Services
| KBLI | Name | PMA | Risk | Notes |
|---|---|---|---|---|
| 70201 | Konsultasi Manajemen (Business Consulting) | TERBUKA 100% | Low | Most common service PT PMA |
| 62010 | Pemrograman Komputer (Software Dev) | TERBUKA 100% | Low | IT/tech companies |
| 62090 | IT Services (other) | TERBUKA 100% | Low | IT consulting, support |
| 74300 | Penerjemahan (Translation) | TERBUKA 100% | Low | Language services |
| 73209 | Riset Pemasaran (Market Research / Digital Marketing) | TERBUKA 100% | Low-Medium | Marketing agencies |

## Wellness & Fitness
| KBLI | Name | PMA | Risk | Notes |
|---|---|---|---|---|
| 93139 | Aktivitas Kebugaran Lainnya (Fitness/Wellness Other) | TERBUKA 100% | Medium-Low | Yoga studios, wellness retreats |
| 96111 | Spa | TERBUKA 100% | Medium | Traditional spa services |
| 93120 | Klub Olahraga (Sports Club) | TERBUKA 100% | Medium-Low | Gyms, surf schools |

## Construction & Property Development
| KBLI | Name | PMA | Risk | Notes |
|---|---|---|---|---|
| 41011 | Konstruksi Gedung (Building Construction) | TERBATAS 67% | High | Requires Indonesian partner for 33% |
| 41012 | Pembangunan Gedung Tempat Tinggal | TERBATAS 67% | High | Residential construction |

## Import/Export & Trading
| KBLI | Name | PMA | Risk | Notes |
|---|---|---|---|---|
| 46100 | Perdagangan Besar Atas Dasar Balas Jasa (Commission Trading) | TERBUKA 100% | Medium-Low | Import/export agent |
| 47190 | Perdagangan Eceran Lainnya (General Retail) | Varies | Medium | Check specific sub-code |

## Common mistakes expats make
1. **Using 55130 (Homestay) instead of 55193 (Villa)** — 55130 is CLOSED to PMA
2. **Not declaring supporting KBLI** — BKPM 5/2025 requires all supporting activities
3. **Single KBLI with unrelated activities** — e.g., restaurant PT doing construction = compliance violation
4. **Ignoring risk classification** — "TERBUKA" doesn't mean "no license needed"
5. **Not meeting Rp 10 billion investment plan per KBLI per location**

## Tip: the most versatile PT PMA setup for Bali
Primary: 70201 (Business Consulting) — Low risk, immediate NIB, 100% PMA
Supporting: 56101 (Restaurant) + 55193 (Villa) — covers F&B and accommodation

But remember: each KBLI requires Rp 10 billion investment plan per location. If you have 3 KBLI codes in Bali, the total plan must account for Rp 30 billion of investment.
""",
    },
    {
        "concept_id": "nb3-rptka-tka-hiring",
        "title": "Hiring Foreign Workers (TKA) — RPTKA, DKP-TKA, KITAS E23",
        "category": "foreign_workers",
        "subcategory": "rptka_tka",
        "text": """[CONTEXT: Indonesia Company Setup 2025-2026 — Concept: Hiring TKA]

# Hiring Foreign Workers (TKA) in Indonesia — RPTKA Process

## Overview
To hire a foreign worker (Tenaga Kerja Asing / TKA), the Indonesian company (PT PMA or PT Lokal) must obtain an RPTKA (Rencana Penggunaan Tenaga Kerja Asing) from the Ministry of Manpower (Kemnaker).

## Step-by-step process

### Step 1 — RPTKA Application
The employer submits RPTKA through **SIAPKerja** (siapkerja.kemnaker.go.id) specifying:
- Position for the TKA (must be from the approved KBLI-TKA position list)
- Duration of employment
- Justification why a foreigner is needed
- Knowledge transfer plan (pendamping) — Indonesian counterpart who will be trained

### Step 2 — DKP-TKA (Dana Kompensasi Penggunaan TKA)
Employer pays **USD 100 per month per TKA** to the government compensation fund.
- Paid upfront for the entire KITAS period
- Example: 1-year KITAS = USD 1,200
- Must be paid BEFORE KITAS application

### Step 3 — VITAS / KITAS E23
Once RPTKA is approved:
- **Offshore process**: DJP issues e-Visa Telex → TKA enters Indonesia → KITAS E23 activated at border
- **Onshore (alih status)**: if TKA is already in Indonesia on convertible visa (C1, C2, D-series), can convert without exiting — BUT "One Sponsor Policy" (SE Kemnaker 3/836/2026) requires ITK sponsor = RPTKA sponsor

### Step 4 — KITAS E23 (Working KITAS)
- Duration: typically 1 year, renewable
- Tied to the sponsoring company — changing employer requires new RPTKA
- After 3 consecutive years of KITAS: eligible for KITAP conversion

## Which positions can a TKA hold?
The government publishes an approved list of positions per KBLI code (Jabatan TKA). The kbli_tka_hybrid collection in Qdrant contains 246 KBLI codes with their approved TKA positions and ISCO codes.

Common approved positions:
- General Manager, Operations Manager
- Finance Manager, Marketing Manager
- Technical Director, IT Manager
- Chef (Executive Chef, Sous Chef in hotel/restaurant KBLI)

Positions NOT allowed for TKA:
- HR/Personnel Manager (exclusively for WNI)
- Positions below management level (generally)
- Any position not on the approved list for the KBLI

## One Sponsor Policy (SE Kemnaker 3/836/2026)
New enforcement: for alih status from visit visa to KITAS E23, the sponsor on the original ITK (immigration permit) MUST MATCH the sponsor on the RPTKA. If different and no corporate affiliation, alih status is REJECTED → TKA must exit Indonesia and re-enter via offshore scheme.

## Costs (government fees only, not Bali Zero service fees)
- DKP-TKA: USD 100/month × duration
- VITAS E23: USD 150 (PNBP)
- KITAS 1 year: Rp 3,000,000 (PNBP)
- BPJS: employer contributions (see BPJS concept)

## Legal basis
- UU No. 13/2003 (Manpower Law) as amended by UU 6/2023
- PP No. 34/2021 (TKA regulations)
- Permenaker No. 8/2021 (RPTKA procedures)
- SE Kemnaker 3/836/2026 (One Sponsor Policy)
""",
    },
]


async def embed_dense(client: httpx.AsyncClient, text: str) -> list[float]:
    r = await client.post(
        "https://api.openai.com/v1/embeddings",
        json={"model": EMBEDDING_MODEL, "input": text},
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()["data"][0]["embedding"]


async def upsert_concept(client: httpx.AsyncClient, doc: dict[str, Any]) -> None:
    point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"nb3-kbli:{doc['concept_id']}"))
    text = doc["text"].strip()
    dense = await embed_dense(client, text)
    payload = {
        "text": text,
        "metadata": {
            "title": doc["title"],
            "category": doc["category"],
            "subcategory": doc["subcategory"],
            "source": f"NB-3 Concept: {doc['title']}",
            "doc_type": "concept",
            "is_concept": True,
            "validated": "NB-3 2026-04-17",
        },
    }
    body = {"points": [{"id": point_id, "vector": {"dense": dense}, "payload": payload}]}
    r = await client.put(
        f"{QDRANT_URL}/collections/{COLLECTION}/points?wait=true",
        json=body,
        headers={"api-key": QDRANT_API_KEY},
        timeout=60.0,
    )
    if r.status_code >= 400:
        logger.error("[%s] upsert failed: %s", doc["concept_id"], r.text)
    r.raise_for_status()
    logger.info("[%s] upserted id=%s (%d chars)", doc["concept_id"], point_id, len(text))


async def main() -> int:
    if not QDRANT_API_KEY:
        logger.error("QDRANT_API_KEY missing")
        return 1
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY missing")
        return 1

    ok = 0
    fail = 0
    async with httpx.AsyncClient() as client:
        for doc in CONCEPT_DOCS:
            try:
                await upsert_concept(client, doc)
                ok += 1
            except Exception:
                logger.exception("[%s] failed", doc["concept_id"])
                fail += 1

    logger.info("DONE: %d success, %d failed (collection now ~%d points)", ok, fail, 4618 + ok)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
