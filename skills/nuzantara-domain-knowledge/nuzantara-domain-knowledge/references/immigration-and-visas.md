# Immigration & Visas in Nuzantara/Bali Zero Context

This document outlines key aspects of Nuzantara's operations related to Indonesian immigration and various visa types, extracted from project documentation and codebase analysis.

## Core Services & Knowledge Bases

- **`visa_oracle`**: A primary knowledge base (Qdrant collection) containing authoritative legal knowledge and requirements for various Indonesian visas. This is a critical source for factual visa information.
- **`bali_intel_immigration`**: A collection for news and updates related to immigration (less authoritative than `visa_oracle`).
- **CRM Integration**: The Nuzantara CRM system tracks client profiles, including passport and visa information (`current_visa_type`, `visa_expiry`). It also manages client documents categorized under "01_Immigration" for visas, KITAS, and other immigration documents.
- **Article Classification**: The system intelligently classifies articles as either "visa" or "news" based on content keywords, routing them to the appropriate knowledge collections.

## Key Visa Types Handled

Nuzantara and Bali Zero provide consultation and support for a wide range of Indonesian visas, including but not limited to:

- **Tourist Visas:**
  - **B211A Tourist Visa**: Standard tourist visa.
  - **Visa on Arrival (VOA)**: Requirements and process.
  - **Digital Nomad E33G Visa**: Comprehensive application guide for remote workers.
- **Investor & Business Visas:**
  - **Investor KITAS**: Visa for PT PMA (Foreign Investment Company) owners.
  - **D12 Business Visa**: Conversion to Investor KITAS.
- **Family & Spouse Visas:**
  - **Spouse KITAS**: For individuals married to Indonesians.
  - **Dependent Visa**: For bringing family members.
- **Special Visas:**
  - **Indonesia Retirement Visa**: Guide for individuals aged 55+.
  - **Second Home Visa (SHV)**: For long-term stays (5-10 years).
  - **Student Visa**: KITAS for educational purposes.
  - **E-Visa**: Information on the new electronic visa system.
- **Golden Visa**: Specific details on who qualifies and requirements.

## Processes & Systems

- **Visa PDF Generation**: The system generates professional PDF documents for 25 different visa types in Bali Zero style, deployed on Vercel at `apps/mouth/public/files/visa/`.
- **Data Seeding & Migrations**: Extensive migration scripts (`seed_visa_types.py`, `fix_visa_types_from_qdrant.py`, `integrate_visa_complete_ac.py`, etc.) are used to populate and update the `visa_types` database table with accurate, official requirements from sources like `imigrasi.go.id`.
- **Automated Monitoring**: An `intelligent_visa_agent.py` runs daily to fetch new data and monitor immigration-related information.
- **Client Portal (`/portal/visa`):** Frontend interface for clients to check visa status and access immigration documents.
- **API Endpoints (`/api/knowledge/visa`):** Backend API for listing, retrieving specific visa types by code/ID, and managing visa types (admin only).

## Important Considerations

- **Document Requirements**: The system tracks specific document requirements for various visas.
- **Eligibility by KBLI**: Visa eligibility can be linked to KBLI codes for certain business visas.
- **Client Communication**: The system facilitates communication regarding visa applications, emphasizing adherence to banking requirements and avoiding rejections.
- **"Passport and visa upload"** are critical upload points in the system.
