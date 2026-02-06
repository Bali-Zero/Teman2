# Company Formation, Licensing & KBLI in Nuzantara/Bali Zero Context

This document details Nuzantara's expertise and system interactions related to company formation, business licensing, and the Indonesian Standard Industrial Classification (KBLI) codes, extracted from project documentation and codebase analysis.

## KBLI (Klasifikasi Baku Lapangan Usaha Indonesia)

The KBLI system is fundamental to business classification and regulatory compliance in Indonesia.

- **KBLI 2025 Standard**: The latest classification system (based on BPS 7/2025 and ISIC Revision 5) features 1,562 codes across 22 categories (A-V). It formally recognizes emerging economic sectors like the platform economy, green economy, and Islamic finance.
- **Risk-Based Licensing (PP 28/2025)**: KBLI codes directly influence the licensing requirements for businesses, categorized by risk level. Some new KBLI codes, particularly for digital platforms, currently lack defined licensing pathways, representing a "regulatory gap."
- **`kbli_unified` Collection**: A core knowledge base within Nuzantara (Qdrant collection and PostgreSQL tables like `kbli_codes`) that stores comprehensive legal and regulatory information for KBLI codes.
- **KBLI Notebook Explorer**: A specialized user interface (`apps/mouth/kbli-explorer`) and backend API (`/api/v1/kbli-notebook/`) for semantic search, inspection, and chat-based research on KBLI codes, leveraging PostgreSQL and Qdrant.
- **KBLI Blueprints**: Metadata and file references for high-quality KBLI guidance documents.
- **KBLI Data Extraction**: The system includes a `PDFVisionService` capable of extracting KBLI data from PDF tables.
- **OSS (Online Single Submission)**: The primary government portal for business registration and obtaining NIB (Nomor Induk Berusaha) and updating KBLI codes.

## PT PMA (Penanaman Modal Asing - Foreign Investment Company)

PT PMA is the mandatory legal entity for foreign investors establishing businesses in Indonesia.

- **Ownership**: Allows foreign shareholding, from 0% to 100% depending on the KBLI sector.
- **Capital Requirements**:
  - **Authorized Capital**: Minimum IDR 10 Billion (approx. USD 600K), typically per KBLI for certain business activities or if sponsoring foreign workers (expats).
  - **Paid-Up Capital**: Minimum IDR 2.5 Billion, which must be deposited as cash in the PT PMA's Indonesian bank account. This capital is operational and not "locked."
- **Formation Process**:
  1.  **Company Name Approval**: Via KEMENKUMHAM (Ministry of Law and Human Rights).
  2.  **KBLI Selection**: Crucial step, determining permitted business activities and licensing.
  3.  **Deed of Establishment**: Notarized document.
  4.  **NIB (Nomor Induk Berusaha)**: Business Identification Number from OSS.
  5.  **NPWP (Nomor Pokok Wajib Pajak)**: Company Tax ID.
  6.  **Bank Account Opening**: For depositing paid-up capital.
- **Timeline**: Typical PT PMA setup takes 2-3 weeks.
- **Obligations**: Mandatory quarterly LKPM (Laporan Kegiatan Penanaman Modal - Investment Activity Report) to BKPM (Investment Coordinating Board). Failure to report for 90 days can lead to NIB revocation.
- **PT Lokal vs. PT PMA**:
  - **PT Lokal**: 100% Indonesian-owned. Lower capital requirements. No LKPM reporting.
  - **PT PMA**: Allows foreign ownership. Higher capital requirements. Mandatory LKPM. Allows foreign directors.
  - **Conversion**: Possible to convert PT Lokal to PT PMA, but direct PT PMA setup is generally recommended to save time and cost.
- **Investor KITAS (E28A)**: Foreign directors or commissioners of an active PT PMA are eligible for this work permit/visa. It is tied to the PT PMA's sponsorship and KBLI activities.
- **Common Business Scenarios**: Nuzantara supports PT PMA setup for diverse sectors including restaurants (KBLI 56101), villa rentals (KBLI 55130), and tech companies.

## Business Licensing & Permits

Licensing in Indonesia is closely integrated with the KBLI system and the OSS platform.

- **KBLI-Specific Licenses**: Each KBLI code dictates specific licenses and permits required for an activity. This includes import authorizations (API-U, API-P).
- **Health Permits**: For F&B businesses (e.g., restaurants), health permits (BPOM, Dinkes) are necessary after PT PMA and NIB are secured.
- **Alcohol Licensing (NPBBKC)**: Managed by Bea Cukai (Customs). It is complex and depends on the KBLI code (e.g., KBLI 56101 for restaurants is easier than KBLI 56301 for bars).
- **Zoning**: Critical for physical businesses (e.g., restaurants, villas). Must be checked _before_ PT PMA setup, as incorrect zoning can prevent operational licenses.

## Bali Zero Services & System Integration

- **PT PMA Setup Package**: Bali Zero offers an all-inclusive PT PMA setup package for IDR 20,000,000 (2025 official price), covering notary, KEMENKUMHAM, NIB, NPWP, and bank account setup.
- **CRM `02_Company` Folder**: The CRM system organizes client company documents (deeds, NIB, NPWP, etc.) within a dedicated "02_Company" folder.
- **Pricing Service**: The backend includes a pricing service (`backend/services/pricing/pricing_service.py`) that retrieves official Bali Zero prices for company services.
- **Portal Endpoints**: `/api/portal/company/{company_id}` provides detailed company information to clients through the portal, including status and primary company selection.
- **AI CRM Extractor**: Can extract company-related facts (name, KBLI, capital, industry) from conversation.
