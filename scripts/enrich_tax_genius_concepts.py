"""Enrich tax_genius_hybrid Qdrant collection with NB-4-validated concept docs.

The existing 332 points (PPN cycle, PPh 21 Indonesian, conversational Q&A) are
high-quality training data — we don't touch them. Instead we ADD standalone
concept documents covering the critical gaps for Bali Zero clients:

1. Tax Residency for Foreigners (183-day rule, SPDN/SPLN, KITAS auto-SPDN)
2. NPWP for WNA (requirements, 16-digit format, penalties)
3. PPh Progressive Brackets + PTKP (income tax for resident foreigners)
4. PPh 26 + Tax Treaties (withholding for non-residents, DTA rates)
5. PT PMA Tax Obligations (corporate 22%, monthly/annual deadlines)
6. PPN/VAT 2025 (12% luxury / 11% effective, PKP threshold, e-Faktur)
7. WorldWide Income + WNA Tertentu Exception (PMK 18/2021, 4-year rule)

Source of truth: NB-4 (Tax & Fiscal) query 2026-04-17.
References: UU PPh, UU HPP 7/2021, PP 55/2022, PP 58/2023, PMK 18/2021,
PMK 112/2022, PMK 131/2024, PMK 168/2023, PMK 172/2023, PMK 112/2025.

Run:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python ../../scripts/enrich_tax_genius_concepts.py
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
logger = logging.getLogger("enrich_tax_genius")


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
COLLECTION = "tax_genius_hybrid"
EMBEDDING_MODEL = "text-embedding-3-small"


# ---------------------------------------------------------------------------
# Concept documents
# ---------------------------------------------------------------------------

CONCEPT_DOCS: list[dict[str, Any]] = [
    {
        "concept_id": "nb4-tax-residency-foreigners",
        "title": "Tax Residency for Foreigners in Indonesia (SPDN vs SPLN)",
        "category": "tax_residency",
        "subcategory": "foreigners",
        "text": """[CONTEXT: Indonesia Tax 2024-2026 — Concept: Tax Residency for Foreigners]

# Tax Residency for Foreigners (SPDN vs SPLN)

## The 183-Day Rule (UU PPh Pasal 2, UU HPP 7/2021)

A foreign national (WNA) becomes an Indonesian tax resident (Subjek Pajak Dalam Negeri / SPDN) if ANY of these conditions are met:
1. **Resides in Indonesia** (bertempat tinggal)
2. **Present in Indonesia for more than 183 days** within any 12-month period
3. **Present in Indonesia during a fiscal year** with the **intention to reside** (niat tinggal)

The "intention to reside" is automatically demonstrated by obtaining a long-term stay permit (KITAS or KITAP).

## KITAS/KITAP = Automatic SPDN from Day 1

A WNA who holds a KITAS becomes SPDN from the **first day the KITAS is valid** — they do NOT need to wait 183 days. The permit itself proves intention to reside.

Similarly, KITAP holders are "penduduk tetap" (permanent residents) and are always SPDN.

## Visit visa holders (C1, VoA, Bebas Visa)

Tourists and business travelers on short-stay visas who stay ≤183 days remain **SPLN** (Subjek Pajak Luar Negeri / non-resident taxpayer). They are taxed only on Indonesia-source income via PPh 26 (flat 20% withholding, reducible by DTA).

**Warning**: a digital nomad on C1 tourist visa who stays >183 days in 12 months becomes SPDN, even without KITAS. They owe tax on worldwide income.

## SPDN vs SPLN — consequences

| | SPDN (Resident) | SPLN (Non-Resident) |
|---|---|---|
| Tax type | PPh 21 (progressive 5-35%) | PPh 26 (flat 20%) |
| Taxed on | Worldwide income | Indonesia-source income only |
| SPT filing | Annual SPT Tahunan required | No filing obligation |
| NPWP | Required | Not required (tax via withholding) |
| DTA benefit | Foreign tax credit | Reduced WHT rate via CoD |

## Legal basis
- UU PPh No. 36/2008 Pasal 2
- UU HPP No. 7/2021
- PP 55/2022

## Worldwide Income Exception: "WNA Tertentu" (PP 55/2022 art. 3-4 + PMK 18/2021)

Foreigners with **specific expertise** (STEM fields, researchers, senior managers) who become SPDN are taxed ONLY on Indonesia-source income for the **first 4 fiscal years**. Requirements:
- Hold a position designated by Kemnaker as eligible TKA position, OR
- Be a researcher designated by the relevant government research body
- Have expertise in science, technology, or mathematics (proven by degree from accredited institution or professional certification)
- Minimum 5 years professional experience
- Must NOT claim DTA benefits on foreign income during the 4-year period

This is NOT automatic — the WNA must formally apply to DJP (Pasal 446 PP 55/2022).

**Important**: E33G Digital Nomad visa holders, E28A investors, and E33F retirees do NOT automatically qualify for this exception. It is limited to specific skilled-worker roles.
""",
    },
    {
        "concept_id": "nb4-npwp-for-wna",
        "title": "NPWP (Tax ID) for Foreigners in Indonesia",
        "category": "tax_registration",
        "subcategory": "npwp_foreigners",
        "text": """[CONTEXT: Indonesia Tax 2024-2026 — Concept: NPWP for Foreigners]

# NPWP (Nomor Pokok Wajib Pajak) for Foreigners

## Who needs it
Every WNA classified as SPDN (tax resident) who earns income in Indonesia must obtain an NPWP. This includes:
- KITAS holders (automatic SPDN from day 1 of permit)
- KITAP holders
- Anyone present >183 days in 12 months

## Required documents
- Valid passport copy
- KITAS or KITAP copy
- Employment letter from Indonesian employer (or company docs for investors/directors)
- Employer's NPWP
- Domicile certificate (SKTT or SKD)
- Deed of Establishment and business licence (for shareholders/directors)

## How to register
- **Online**: e-Registration portal (ereg.pajak.go.id)
- **Offline**: at the Kantor Pelayanan Pajak (KPP) matching your domicile/business address
- **Processing**: verification by tax officer, possible interview, then NPWP issued (physical or digital)
- **Activate e-Filing**: must activate EFIN (Electronic Filing Identification Number) at KPP for online tax submissions

## NPWP format (2024-2025)
- **WNI (Indonesian citizens)**: NIK = NPWP (16 digits, PMK 112/2022)
- **WNA (foreigners)**: 16-digit number generated and assigned by DJP (NOT NIK-based)
- Old 15-digit format remains valid during transition period (until further notice from Ministry of Finance)
- CoreTax system (coretax.pajak.go.id) is now mandatory for all filings

## Penalties for not having NPWP
- PPh 21 withholding rate increased by **20%** for employees without NPWP
- PPh 23 withholding rate **doubled** (e.g., 2% → 4%) for domestic service providers without NPWP
- Potential imprisonment up to 6 years and fine up to 4× tax owed (UU 7/2021)

## PT PMA director's personal NPWP
A foreign director (direktur WNA) with KITAS sponsored by a PT PMA is a "wajib pajak" and must obtain a **personal NPWP** (NPWP Pribadi) in addition to the company NPWP (NPWP Badan).

## Deregistration when leaving Indonesia
When a WNA permanently leaves Indonesia (KITAS not renewed, no intention to return), they should deregister their NPWP at the KPP. Failure to do so may result in future compliance issues.

## Legal basis
- UU No. 28/2007 (KUP)
- UU HPP 7/2021
- PMK 112/2022
- PER DJP 6/PJ/2024
""",
    },
    {
        "concept_id": "nb4-pph-progressive-brackets",
        "title": "PPh 21 Progressive Tax Brackets for Foreigners (Indonesia 2024-2026)",
        "category": "income_tax",
        "subcategory": "pph21_foreigners",
        "text": """[CONTEXT: Indonesia Tax 2024-2026 — Concept: PPh 21 Progressive Brackets]

# Personal Income Tax (PPh 21) — Progressive Brackets

## Who pays PPh 21
All tax residents (SPDN), including:
- Indonesian employees (WNI)
- Foreign employees/directors with KITAS/KITAP (WNA as SPDN)

## Progressive tax rates (UU HPP 7/2021)

| Annual Taxable Income (IDR) | Tax Rate |
|---|---|
| Up to 60,000,000 | 5% |
| 60,000,001 – 250,000,000 | 15% |
| 250,000,001 – 500,000,000 | 25% |
| 500,000,001 – 5,000,000,000 | 30% |
| Above 5,000,000,000 | 35% |

The 35% top bracket was introduced by UU HPP 7/2021.

## Non-Taxable Income (PTKP) — deducted before applying brackets

| Status | Annual PTKP (IDR) |
|---|---|
| TK/0 (single, no dependents) | 54,000,000 |
| K/0 (married, no children) | 58,500,000 |
| K/1 (married, 1 child) | 63,000,000 |
| K/2 (married, 2 children) | 67,500,000 |
| K/3 (married, 3 children) | 72,000,000 |

Additional Rp 4,500,000 per dependent (max 3). Working spouse adds Rp 54,000,000.

## TER System (Tarif Efektif Rata-Rata) — since January 2024

Introduced by PP 58/2023 + PMK 168/2023:
- Employees classified into TER Category A, B, or C based on PTKP status
- Monthly withholding: flat effective rate × gross monthly income (simplified calculation)
- **December recalculation**: full-year liability recalculated using progressive brackets above; difference settled

This replaces the old monthly progressive calculation. The employer applies TER Jan-Nov, then adjusts in December.

## Non-cash benefits now taxable (UU HPP 7/2021)
Housing, vehicle, education allowances, and other benefits-in-kind (natura) provided by employer are now taxable income for the employee.

## Director / Commissioner WNA
- If classified as SPDN (KITAS holder): PPh 21 on salary/compensation
- Dividends received: PPh 4(2) final at 10% (for SPDN individuals)
- If zero salary initially (common for new PT PMA): no PPh 21 obligation, but KITAS renewal may require demonstrating employment relationship

## Filing obligations
- Employer must withhold and remit PPh 21 by 15th of following month
- Employer files SPT Masa PPh 21 by 20th of following month
- Employee must file SPT Tahunan Pribadi by March 31

## Legal basis
- UU PPh No. 36/2008 Pasal 17(1)(a)
- UU HPP No. 7/2021
- PP 58/2023, PMK 168/2023 (TER system)
""",
    },
    {
        "concept_id": "nb4-pph26-withholding-treaties",
        "title": "PPh 26 Withholding Tax & Tax Treaties (DTA/P3B) for Non-Residents",
        "category": "income_tax",
        "subcategory": "pph26_treaties",
        "text": """[CONTEXT: Indonesia Tax 2024-2026 — Concept: PPh 26 & Tax Treaties]

# PPh 26 — Withholding Tax for Non-Residents

## Standard rate
**20% flat** on gross Indonesia-source income for all SPLN (non-residents).

Applies to: dividends, interest, royalties, service fees, rent, management fees, and other Indonesian-source income paid to non-residents.

## Tax Treaties (P3B / Persetujuan Penghindaran Pajak Berganda)

Indonesia has signed **71 Double Tax Avoidance Agreements (DTAAs)**.

### Key treaty rates (withholding tax on dividends / interest / royalties):

| Country | Dividends | Interest | Royalties |
|---|---|---|---|
| **Italy** | 10-15% | 10% | 10-15% |
| **Australia** | 15% | 10-15% | 10-15% |
| **USA** | 10-15% | 10% | 10% |
| **UK** | 10-15% | 10-15% | 10-15% |
| **Russia** | 15% | 15% | 15% |
| **Germany** | 10-15% | 10% | 7.5% |
| **Netherlands** | 5-15% | 10% | 10% |
| **Singapore** | 10-15% | 10% | 10% |
| **Japan** | 10-15% | 10% | 10% |
| **France** | 10-15% | 15% | 10% |
| **Hong Kong** | 5-10% | 10% | 5% |
| **South Korea** | 10-15% | 10% | 15% |

Lower rate typically applies when beneficial owner holds ≥25% of capital.

## How to claim treaty benefits

1. Non-resident recipient obtains **Certificate of Domicile (SKD/CoD)** from their home country's tax authority
2. Submit **Form DGT-1** (for dividends/royalties/interest) or **DGT-2** (for employment income/pensions) to the Indonesian payer
3. Indonesian payer applies reduced rate instead of 20%
4. CoD valid for 12 months from issuance
5. **Without valid CoD**: payer MUST apply standard 20% rate. Cannot apply treaty retroactively.

## PMK 112/2025 — Stricter anti-abuse rules

New requirements effective 2025:
- **Beneficial Ownership test**: must prove genuine economic substance
- **Principal Purpose Test (PPT)**: treaty benefits denied if obtaining benefit was primary purpose of arrangement
- **365-day holding period**: for reduced dividend rates, corporate SPLN must hold shares for minimum 365 calendar days including payment date
- **Conduit rules**: substance indicators required
- Electronic submission via DGT portal (CoreTax) is mandatory
- 10 calendar day decision period for Special Form approvals (changed from 5 working days)

## e-Bupot obligation
All PPh 26 withholding certificates must be issued electronically via CoreTax (e-Bupot). Paper bukti potong no longer accepted.

## Legal basis
- UU PPh Pasal 26
- PMK 112/2025 (replaces PER 25/2018 and PER 28/2018)
- Individual treaty texts (available at pajak.go.id)
""",
    },
    {
        "concept_id": "nb4-pt-pma-tax-obligations",
        "title": "PT PMA Tax Obligations — Monthly & Annual Compliance Calendar",
        "category": "corporate_tax",
        "subcategory": "pt_pma_obligations",
        "text": """[CONTEXT: Indonesia Tax 2024-2026 — Concept: PT PMA Tax Compliance]

# PT PMA Tax Obligations — Complete Compliance Calendar

## Corporate Income Tax (PPh Badan)

- **Standard rate**: 22% on net taxable income (UU HPP 7/2021)
- **SME discount**: companies with gross revenue <Rp 50 billion get 50% discount on income proportional to first Rp 4.8 billion of turnover (effective rate 11% on that portion)
- **Listed company discount**: 3% reduction if ≥40% shares traded on IDX → effective 19%
- **UMKM 0.5% regime**: technically available for PT for 3 years from incorporation (PP 55/2022), but PT PMA rarely qualifies due to Rp 10 billion minimum capital requirement

## Monthly Obligations (payment deadline: 15th of following month)

| Tax | What | Rate | Deadline |
|---|---|---|---|
| **PPh 21** | Payroll withholding (employees + directors) | Progressive 5-35% (TER monthly) | Pay by 15th, file by 20th |
| **PPh 23** | Withholding on domestic services, royalties | 2% services / 15% dividends-royalties | Pay by 15th, file by 20th |
| **PPh 25** | Monthly corporate income tax installment | 1/12 of estimated annual tax | Pay by 15th, file by 20th |
| **PPh 26** | Withholding on payments to non-residents | 20% (or treaty rate) | Pay by 15th, file by 20th |
| **PPh 4(2)** | Final tax (rent 10%, construction 2-6%, etc.) | Various | Pay by 15th, file by 20th |
| **PPN (VAT)** | VAT on sales/purchases (if PKP registered) | 11% effective (12% on luxury) | Pay + file by end of following month |
| **BPJS** | Health + employment insurance contributions | 5% health (4% employer) + TK varies | Pay by 15th |

## Quarterly Obligations

| Obligation | What | Deadline |
|---|---|---|
| **LKPM** | Investment activity report (to BKPM via OSS) | Q1: 7 Apr, Q2: 7 Jul, Q3: 7 Oct, Q4: 7 Jan |

## Annual Obligations

| Obligation | What | Deadline |
|---|---|---|
| **SPT Tahunan PPh Badan** | Corporate income tax return (Form 1771) | **30 April** |
| **SPT Tahunan Pribadi** | Personal tax return for directors/employees | **31 March** |
| **Audited financial statements** | Required attachment to SPT Badan | With SPT |

## Late filing penalties
- **SPT Masa (monthly)**: administrative fine applies
- **SPT Tahunan Badan (annual)**: Rp 1,000,000 fine + potential criminal liability
- **SPT Tahunan Pribadi**: Rp 100,000 fine
- Interest penalties: benchmark rate + 5% per month

## CoreTax System (2025 — mandatory)
All filings via coretax.pajak.go.id. Requires:
- NPWP Badan + EFIN activation
- Digital certificate for e-Faktur
- e-Bupot for all withholding certificates

## Transfer Pricing (PMK 172/2023)
All related-party transactions must comply with arm's length principle. Documentation requirements include:
- Master File + Local File (mandatory for all related-party transactions)
- Country-by-Country Report (if group revenue >Rp 11 trillion)
- Advance Pricing Agreements (APA) available via CoreTax

## Legal basis
- UU PPh No. 36/2008
- UU HPP No. 7/2021
- PP 55/2022
- PMK 81/2024 (CoreTax transition)
- PMK 172/2023 (Transfer Pricing)
""",
    },
    {
        "concept_id": "nb4-ppn-vat-2025",
        "title": "PPN (VAT) Indonesia 2025 — Rates, PKP Threshold, e-Faktur",
        "category": "value_added_tax",
        "subcategory": "ppn_2025",
        "text": """[CONTEXT: Indonesia Tax 2024-2026 — Concept: PPN/VAT 2025]

# PPN (Pajak Pertambahan Nilai) — VAT 2025

## Rate change effective January 2025

UU HPP 7/2021 mandated a PPN increase to 12% from 2025. However, PMK 131/2024 implemented it with a crucial distinction:

- **12% full rate**: applies ONLY to **luxury goods** subject to Luxury Goods Sales Tax (PPnBM):
  - Luxury residences ≥Rp 30 billion
  - Private helicopters and jets
  - Private yachts and cruises
  - Air balloons and gliders
  - Private firearms
- **11% effective rate**: applies to ALL OTHER goods and services (using Adjusted Tax Base = 11/12 of sales value, so 12% × 11/12 = 11% effective)

**For most Bali Zero clients (restaurants, villas, consulting, etc.): the effective PPN rate remains 11%.**

## PKP Registration Threshold

- **Mandatory PKP**: when annual gross revenue exceeds **Rp 4,800,000,000** (4.8 billion IDR, ~USD 300,000)
- Must register by end of month following the month threshold was exceeded
- **Voluntary PKP**: PT PMA can register before reaching threshold

## e-Faktur (Electronic Tax Invoice)

- **Mandatory** for all PKP since 2016
- All invoices via DJP e-Faktur system or CoreTax
- Nomor Seri Faktur Pajak (NSFP): pre-approved serial numbers from DJP required before issuing any invoice
- Digital certificate expires every 2 years — must renew

## PPN on Imported Digital Services (PMSE)

Per PMK 60/2022, foreign digital service providers (Google, Netflix, SaaS platforms) designated by DJP collect PPN directly from Indonesian consumers.

If the foreign provider is NOT a registered PMSE collector, the Indonesian PT PMA buyer must self-assess PPN via **Reverse Charge** mechanism (pemanfaatan JKP dari luar Daerah Pabean).

## Input Tax Credit (Pajak Masukan)

PKP can credit input PPN against output PPN. The Adjusted Tax Base mechanism (11/12) preserves input credit eligibility.

## Exempt and non-taxable supplies

Certain goods and services are PPN-exempt: basic foodstuffs, education services, healthcare, public transport, religious services, and others as listed in UU PPN.

## Common PPN errors for PT PMA

1. **Not registering as PKP** when threshold exceeded → penalties
2. **Missing NSFP renewal** → cannot issue invoices
3. **Expired digital certificate** → e-Faktur upload blocked
4. **Not applying reverse charge** on imported SaaS/digital services
5. **Late filing** of SPT Masa PPN → administrative fines

## Legal basis
- UU PPN No. 42/2009 (as amended by UU HPP 7/2021 and UU 6/2023)
- PMK 131/2024 (12% implementation rules)
- PMK 60/2022 (PMSE digital services)
""",
    },
    {
        "concept_id": "nb4-bpjs-social-security",
        "title": "BPJS Social Security for Foreign Workers in Indonesia",
        "category": "social_security",
        "subcategory": "bpjs_foreigners",
        "text": """[CONTEXT: Indonesia Tax 2024-2026 — Concept: BPJS for Foreign Workers]

# BPJS Social Security for Foreign Workers (TKA)

## Overview

All foreign workers (TKA) with KITAS/KITAP working in Indonesia must be enrolled in BPJS (Badan Penyelenggara Jaminan Sosial). This is a legal obligation for the employer (PT PMA).

## BPJS Kesehatan (Health Insurance)

- **Total contribution**: 5% of monthly salary
  - Employer: 4%
  - Employee: 1%
- **Salary cap**: contributions calculated on salary up to Rp 12,000,000/month
- **Coverage**: national health system (clinics, hospitals, medicines)
- **WNA enrolled**: mandatory since PP 86/2013. Foreign workers with KITAS ≥6 months must be enrolled.
- **Deadline**: pay by 15th of following month

## BPJS Ketenagakerjaan (Employment)

Programs applicable to TKA:
- **JKK** (Jaminan Kecelakaan Kerja / Work Accident): 0.24-1.74% employer-paid (varies by industry risk)
- **JKM** (Jaminan Kematian / Death Benefit): 0.3% employer-paid
- **JHT** (Jaminan Hari Tua / Old Age Savings): 5.7% (3.7% employer + 2% employee) — claimable upon leaving Indonesia permanently
- **JP** (Jaminan Pensiun): foreigners are generally **exempt** from pension program (applicable only to WNI)

## Tax deductibility
- Employer contributions to BPJS are **deductible** for PPh Badan purposes
- Employee contributions are **not deductible** from employee taxable income

## Common compliance issues
1. Not enrolling foreign director/commissioner in BPJS (required if they receive salary)
2. Late payment → administrative fines
3. Not claiming JHT refund when foreign worker leaves Indonesia permanently

## Legal basis
- UU SJSN No. 40/2004
- UU BPJS No. 24/2011
- PP 86/2013 (BPJS Kesehatan for foreigners)
- Perpres 82/2018 (BPJS Kesehatan)
""",
    },
]


# ---------------------------------------------------------------------------
# Qdrant helpers
# ---------------------------------------------------------------------------

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
    point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"nb4-tax:{doc['concept_id']}"))
    text = doc["text"].strip()

    dense = await embed_dense(client, text)

    payload = {
        "text": text,
        "metadata": {
            "title": doc["title"],
            "category": doc["category"],
            "subcategory": doc["subcategory"],
            "source": f"NB-4 Concept: {doc['title']}",
            "tier": "A",
            "language": "en",
            "doc_type": "concept",
            "is_concept": True,
            "validated": "NB-4 2026-04-17",
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

    logger.info("DONE: %d success, %d failed (total collection now has %d + %d = %d expected points)",
                ok, fail, 332, ok, 332 + ok)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
