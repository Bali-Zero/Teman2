# Legal Properties in Nuzantara/Bali Zero Context

This document outlines Nuzantara's expertise and system interactions related to Indonesian property law, land titles, and real estate investment, extracted from project documentation and codebase analysis.

## Core Property Concepts & Legal Structures

- **Land Titles (Hak Atas Tanah)**:
  - **SHM (Sertifikat Hak Milik - Freehold Right)**:
    - Represents full ownership of land, equivalent to freehold.
    - Generally reserved for Indonesian citizens (WNI).
    - Can be converted to HGB (Hak Guna Bangunan) under a PT PMA for foreign investment purposes.
  - **HGB (Hak Guna Bangunan - Right to Build)**:
    - Grants the right to build and possess a structure on state land or land owned by others for a fixed period (typically 30 years, renewable for 20+20 years, totaling up to 80 years).
    - Commonly held by companies, including PT PMA.
    - Often the preferred route for foreign investment in property.
  - **Hak Pakai (Right to Use)**:
    - Grants the right to use state land or land owned by others for a fixed period.
    - Another form of leasehold often used by foreigners.
  - **Leasehold (Hak Sewa)**:
    - Right to rent property for a fixed term, typically from an Indonesian individual or company.
    - Can be transferred to a PT PMA as capital.
- **PT PMA & Property Investment**:
  - PT PMA is the primary vehicle for foreign direct investment in Indonesian real estate.
  - Can acquire HGB land or take over existing leasehold agreements.
  - Property assets can be injected as capital into a PT PMA, subject to appraisal.
  - Foreign ownership of real estate is generally 100% open, particularly under the PT PMA structure, but KBLI codes and project type (e.g., residential vs. commercial) will determine specific eligibility.
- **KBLI 2025 for Real Estate (Category 68)**:
  - The KBLI 2025 system significantly expanded real estate codes (from 5 to 14), recognizing specialized activities like self-storage, property management, and MICE venues.
  - All 14 Real Estate KBLI codes are `REGULATED` and subject to risk-based licensing (PP 28/2025).

## Nuzantara System & Services

- **`property_knowledge` / `property_unified` Collection**: A Qdrant collection serving as a knowledge base for Indonesian property law, regulations, land titles, and market data.
- **`property_legal_structures` PostgreSQL Table**: Stores legal structure options for property ownership, including foreign eligibility.
- **`property_listings` PostgreSQL Table**: Contains scraped property listings from various sources, tracking `property_type`, `ownership`, `price`, and `area`.
- **`property_due_diligence` PostgreSQL Table**: Stores records of due diligence reports performed on properties.
- **Client Journey Orchestrator (`Property Purchase` Journey)**: Nuzantara has a defined workflow for property acquisition, including steps like property selection, due diligence, and land office registration (BPN - Badan Pertanahan Nasional).
- **Property Due Diligence Services**: Bali Zero provides services including land certificate verification, zoning checks, and overall property due diligence.
- **Notary and PPAT (Pejabat Pembuat Akta Tanah - Land Deed Official)**: Essential roles in property transactions for deed of sale and purchase (AJB) and ownership transfer.
- **Property Taxes**:
  - **PBB (Pajak Bumi dan Bangunan)**: Annual Land and Building Tax.
  - **BPHTB (Bea Perolehan Hak atas Tanah dan Bangunan)**: Land and Building Acquisition Tax, paid by the buyer (5% of transaction price minus NPOPTKP).
  - **PPh Final (Pajak Penghasilan Final)**: Seller's income tax on property sale (2.5% of gross sale price). Rental income is subject to 10% final PPh.
- **Zoning & Permits**: Crucial for legal operation. IMB (Izin Mendirikan Bangunan - Building Permit) is a key document confirming compliance with zoning regulations. Property zoning must be checked _before_ investment.
- **CRM Integration (`04_Property` folder - assumed)**: The CRM system likely organizes client property documents within a dedicated folder (similar to `01_Immigration`, `02_Company`, `03_Tax`).

## Important Considerations

- **Property as PT PMA Capital**: Property can be appraised and injected as capital into a PT PMA.
- **Lease Agreement Clauses**: Specific clauses are critical for commercial property leases (e.g., use for commercial purposes, renovation rights, transfer lease rights, landlord's obligation to provide documents for permits like IMB).
- **Property Insurance**: Recommended for business risk protection, though not always legally mandatory.
