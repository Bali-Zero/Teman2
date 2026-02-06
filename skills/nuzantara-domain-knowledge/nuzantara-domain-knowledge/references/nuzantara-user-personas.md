# User Personas & Client Management in Nuzantara/Bali Zero Context

This document outlines Nuzantara's understanding of its target users and the systems in place for client management, extracted from project documentation and codebase analysis.

## Nuzantara's Target Audience

Nuzantara, under the Bali Zero brand, primarily serves **foreigners (expats)** who are living, working, or investing in Indonesia, particularly Bali. The long-term vision includes expanding services to Indonesian citizens (WNI).

**Key Client Segments/Personas:**

- **Expats Seeking Legal Support**: Individuals requiring assistance with Indonesian immigration, visas (KITAS, KITAP, etc.), residency status, and related legal matters.
- **Foreign Entrepreneurs/Investors**: Individuals or entities looking to establish businesses in Indonesia, including PT PMA (Foreign Investment Company) setup, KBLI code selection, licensing, and compliance.
- **Digital Nomads/Remote Workers**: Expats working remotely for foreign companies, seeking guidance on appropriate visas (e.g., E33G Digital Nomad Visa) and tax implications.
- **Individuals with Property Interests**: Foreigners interested in buying, leasing, or investing in Indonesian real estate.
- **Clients with Tax Obligations**: Individuals and companies needing support with Indonesian personal and corporate tax reporting, NPWP registration, PPh, PPN, and LKPM reporting.
- **Families/Spouses of Foreigners**: Clients needing dependent visas or family-related immigration support.

**User Needs & Pain Points (Inferred):**

- Clear, accurate, and up-to-date information on complex Indonesian regulations.
- Efficient processes for legal and business setup.
- Transparent pricing and service explanations.
- Personalized communication and status updates (e.g., "a che punto è la mia pratica?").
- Prevention of legal/financial risks (e.g., "don't fake the injection, or the audit will be brutal" for PT PMA capital).
- Multi-language support for complex legal and tax terms.

## Nuzantara's Client Management System (CRM)

The Nuzantara CRM system is a central hub for managing client relationships and interactions.

- **Client Profiles (`clients` table)**: Stores comprehensive client data including:
  - `full_name`, `email`, `phone`, `whatsapp`
  - `nationality`, `date_of_birth`, `passport_expiry`, `visa_expiry`, `current_visa_type`
  - `client_type` (`individual` or `company`), `company_name` (for corporate clients)
  - `assigned_to` (team member's email), `status` (`lead`, `active`, `inactive`, `prospect`)
  - `google_drive_folder_id` (links to client's dedicated Google Drive folder).
- **Client Portal (`my.balizero.com`)**: A dedicated web portal where authenticated clients can:
  - View their visa status, tax overview, practice progress, and documents.
  - Receive messages and updates from the Bali Zero team.
  - The frontend `apps/mouth/src/app/(workspace)/clients/[id]/page.tsx` serves as the Client 360° view for internal team members.
- **Omnichannel Communication**:
  - **WhatsApp & Telegram Integration**: Enables direct client communication. The system can automatically create new client records from incoming WhatsApp messages and link existing clients across channels using `client_identity_resolver`.
  - **Automated Notifications**: For deadlines (tax, visa expiry) via Telegram and Email.
- **Document Management**:
  - `client_documents` table stores attached documents.
  - Google Drive integration for standardized client folder structures (e.g., `01_Immigration`, `02_Company`, `03_Tax`).
  - `AI CRM Extractor` and Gemini Vision can extract data from passport images or other documents.
- **Practice Management**: The CRM tracks legal practices (services) for clients (e.g., KITAS, PT PMA, tax consulting).
- **Client Timeline (`crm_interactions`)**: Logs all interactions and events related to a client.
- **User Personas (Zantara AI)**: The AI itself has a multi-language persona ("Zantara, the AI assistant for Bali Zero!") designed to be helpful, legally accurate, and conversational.
- **Team Access Control**: Internal team members see clients based on their `assigned_to` field, while super admins (`zero@balizero.com`) have full visibility.
- **Client Value Prediction**: The `client_value_predictor` agent and `ClientScoringService` analyze client data to predict Lifetime Value (LTV) and identify high-risk or high-potential clients for targeted nurturing.
- **User Feedback**: The system collects user feedback for continuous improvement.
