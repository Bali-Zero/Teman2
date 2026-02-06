# Tax Reporting in Nuzantara/Bali Zero Context

This document outlines Nuzantara's capabilities and system implementations regarding Indonesian tax reporting, for both individuals and companies, extracted from project documentation and codebase analysis.

## Core Tax Concepts & Services

- **Tax Identification Number (NPWP)**:
  - **NPWP Personal**: For individuals (employees, freelancers, foreigners).
  - **NPWP Badan/Corporate**: For companies (PT, CV, PT PMA).
  - **Registration**: Can be applied for online or at a local Tax Office (KPP). Issued in 1-3 days.
  - **Mandatory**: Required for Working KITAS and significant financial transactions.
- **Income Tax (PPh - Pajak Penghasilan)**:
  - **PPh 21**: Employee Income Tax, withheld by the company from salaries. Progressive rates (5-35%). Foreign employees may be subject to PPh 26 (20%) or tax treaty rates.
  - **PPh Badan (Corporate Income Tax)**: 22% on company profits (standard). SME rate of 0.5% of gross revenue for companies with revenue < IDR 4.8 Billion.
  - **PPh 23**: Withholding tax on services, dividends (10-15% for local shareholders).
  - **PPh 26**: Withholding tax for non-residents (20% or lower per tax treaty).
  - **PPh Final 0.5% UMKM**: Final tax for small businesses.
  - **PPh Final 10%**: On gross revenue from property rentals.
  - **PPh 25**: Monthly corporate tax installments.
- **Value Added Tax (PPN - Pajak Pertambahan Nilai)**:
  - **Rate**: 11%.
  - **PKP (Pengusaha Kena Pajak)**: Taxable Entrepreneur status, mandatory if revenue > IDR 4.8 Billion/year. Allows claiming input PPN.
  - **e-Faktur**: Electronic system for creating tax invoices.
  - **Reverse Charge**: Mechanism where the buyer remits PPN, typically for imported services from non-PKP vendors.
  - **Export**: PPN 0%.
- **Annual Tax Return (SPT - Surat Pemberitahuan Tahunan)**:
  - **SPT Tahunan Pribadi**: Annual personal income tax return (due March 31).
  - **SPT Tahunan Badan**: Annual corporate income tax return (due April 30).
  - **NIL SPT**: Must still be filed even with zero income if holding an NPWP.
- **LKPM (Laporan Kegiatan Penanaman Modal - Investment Activity Report)**:
  - **Mandatory**: Quarterly report to BKPM for all PT PMA companies.
  - **Consequences of non-reporting**: NIB suspension/revocation.
- **Coretax System**: New integrated tax system by DJP (launched 2025), replacing old DJP Online. Mandatory migration for all taxpayers.
- **Tax Treaties**: Indonesia has tax treaties with many countries to prevent double taxation.

## Nuzantara System & Services

- **`tax_genius_hybrid` Collection**: A critical knowledge base (Qdrant collection) within Nuzantara, providing authoritative information on Indonesian tax regulations, laws, and procedures.
- **`TaxService` (`backend/services/portal/tax_service.py`)**: Manages client tax obligations.
  - `get_client_taxes()`: Retrieves all tax obligations for a client.
  - `get_tax_summary()`: Provides an aggregated tax summary for dashboard cards.
  - `create_obligation()`: Creates new tax obligations with timeline events.
  - `update_status()`: Updates the status of a tax obligation.
- **`tax_obligations` PostgreSQL Table**: Stores client-specific tax deadlines and obligations, with detailed `tax_type`, `due_date`, `status`, and `amount_due` fields.
- **`portal_taxes` Router (`backend/app/routers/portal_taxes.py`)**: Exposes API endpoints (`/api/portal/taxes`, `/api/portal/taxes/summary`) for the frontend to display tax overview and calendar.
- **`deadline_checker` Job (`backend/jobs/deadline_checker.py`)**: An asynchronous job that monitors upcoming tax deadlines (30, 14, 7, 1 days prior) and triggers automated reminders via Telegram and Email.
- **CRM Integration (`03_Tax` folder)**: The CRM system organizes client fiscal documents (declarations, receipts) in a dedicated "03_Tax" folder.
- **Pricing Service**: The system includes a pricing service that can provide official Bali Zero prices for tax consulting services.
- **Document Categorization**: The `document_categorizer` service can identify and categorize tax-related documents like NPWP, SPT Tahunan, and LKPM reports.
- **Consulting Services**: Bali Zero offers accounting & payroll services, as well as Transfer Pricing (TP) Documentation assistance for PT PMAs involved in intercompany transactions.
- **Monitoring**: Prometheus metrics (`portal_tax_requests_total`, `portal_tax_latency_seconds`) track performance and reliability of tax endpoints.

## Tax Considerations for PT PMA

- **Mandatory LKPM Reporting**: All PT PMA companies must submit quarterly LKPM reports.
- **Corporate Tax**: PT PMAs are subject to PPh Badan (22% standard, or 0.5% for SMEs < IDR 4.8B revenue).
- **Tax Incentives**: PT PMAs may be eligible for tax holidays or allowances depending on investment size and sector.
- **NPWP**: Both the PT PMA (NPWP Badan) and its directors (NPWP Pribadi) need tax IDs.
- **Withholding Tax for Foreign Services**: PT PMAs hiring foreign service providers (e.g., marketing agencies) must withhold PPh 26 (20% or lower per treaty) and self-assess PPN on imported services.
