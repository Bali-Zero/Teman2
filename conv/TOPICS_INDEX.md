# Training Conversations - Topics Index

> **Last Updated**: 2025-12-10
> **Total Files**: 34 conversations
> **Languages**: Indonesian, English, Javanese (Timuran), Balinese, Medan dialect

---

## VISA & IMMIGRATION (18 files)

### Visit Visas (Single Entry)
| File | Visa Type | Duration | Languages |
|------|-----------|----------|-----------|
| `b1-visa-conversation-english 2.md` | B1 Business Visit | 60 days | EN |
| `b1-visa-conversation-medan-pekat 2.md` | B1 Business Visit | 60 days | Medan |
| `percakapan-b1-bahasa-bali 2.md` | B1 Business Visit | 60 days | Balinese |
| `c2_business_visit_conversation.md` | C2 Business Visit | 60 days | ID/EN |
| `c7-visa-10bubble-3bahasa 2.md` | C7 Performing | 30 days | ID/JV/EN |
| `c10-visa-10bubble-3bahasa 2.md` | C10 Event Participant | 60 days | ID/JV/EN |
| `c11-visa-10bubble-3bahasa 2.md` | C11 Exhibitor | 60 days | ID/JV/EN |
| `conv_whatsap.md` | C1 Tourism | 60 days | EN/ID/Bali |

### Multiple Entry Visas
| File | Visa Type | Duration | Languages |
|------|-----------|----------|-----------|
| `d1_tourism_visa_conversation_20251210.md` | D1 Tourism | 5 years (60d/entry) | ID/EN |
| `d2_business_visa_conversation_20251210.md` | D2 Business | 1 year (60d/entry) | ID/EN |

### KITAS (Temporary Stay Permit)
| File | Visa Type | Duration | Languages |
|------|-----------|----------|-----------|
| `e33g_digital_nomad_conversation.md` | E33G Digital Nomad | 2 years | ID/EN |
| `e28a_investor_pma_conversation.md` | E28A Investor | 1-2 years | ID/EN |
| `e31a_spouse_mixed_marriage_conversation.md` | E31A Spouse/Mixed Marriage | 1-2 years | ID/EN |
| `e26_spouse_kitas_conversation_20251210.md` | E26 Spouse KITAS | 1-2 years | ID/EN |
| `FREELANCE KITAS (180 Days).md` | Freelance KITAS | 180 days | ID/EN/JV |
| `WORKING KITAS (1 YEAR).md` | Working KITAS | 1 year | ID/EN/JV |
| `percakapan-dependent-kitas-3bahasa 2.md` | Dependent KITAS | follows sponsor | ID/JV/EN |
| `percakapan-investor-kitas-3versi 2.md` | Investor KITAS | 1-2 years | ID/JV/EN |

### KITAP (Permanent Stay Permit)
| File | Visa Type | Duration | Languages |
|------|-----------|----------|-----------|
| `percakapan-investor-kitap-3bahasa 2.md` | Investor KITAP | 5 years | ID/JV/EN |
| `golden_visa_conversation_20251210.md` | Golden Visa | 5-10 years | ID/EN |

---

## BUSINESS & COMPANY SETUP (10 files)

### PT PMA (Foreign Investment Company)
| File | Topic | Languages |
|------|-------|-----------|
| `pt_pma_company_setup_conversation_20251210.md` | Full PT PMA Setup | ID/EN |
| `pt_pma_company_setup_full_conversation_20251210.md` | PT PMA Setup Extended | ID/EN |
| `pt_pma_setup_conversation_20251210.md` | PT PMA Setup Basic | ID/EN |
| `pt_lokal_vs_pma_conversation_20251210.md` | PT Lokal vs PT PMA Comparison | ID/EN |

### KBLI (Business Classification Codes)
| File | Industry | Languages |
|------|----------|-----------|
| `kbli_restaurant_conversation_20251210.md` | F&B / Restaurant | ID/EN |
| `kbli_villa_conversation_20251210.md` | Villa / Property Rental | ID/EN |
| `kbli_it_consulting_conversation_20251210.md` | IT / Consulting Services | ID/EN |

### OSS & NIB (Business Registration)
| File | Topic | Languages |
|------|-------|-----------|
| `oss_nib_registration_conversation_20251210.md` | OSS NIB Registration | ID/EN |
| `oss_nib_registration_full_conversation_20251210.md` | OSS NIB Extended | ID/EN |

---

## TAX & FINANCE (4 files)

| File | Topic | Languages |
|------|-------|-----------|
| `tax_pph_ppn_conversation.md` | PPh & PPN Overview | ID/EN |
| `corporate_income_tax_22_conversation_20251210.md` | Corporate Tax 22% | ID/EN |
| `expatriate_tax_obligations_conversation_20251210.md` | Expat Tax Obligations | ID/EN |
| `transfer_pricing_conversation_20251210.md` | Transfer Pricing Rules | ID/EN |

---

## PROPERTY & REAL ESTATE (1 file)

| File | Topic | Languages |
|------|-------|-----------|
| `indonesian_buying_property_conversation_20251210.md` | Property Purchase Process | ID/EN |

---

## Key Topics Covered

### Visa Topics
- Digital Nomad requirements (E33G)
- Investor KITAS/KITAP process
- Spouse/Family visa options
- Tourism & Business visit visas
- Working permit requirements
- Golden Visa eligibility

### Business Topics
- PT PMA vs PT Lokal differences
- KBLI code selection by industry
- OSS/NIB registration process
- Capital requirements (10B stated vs actual)
- LKPM reporting obligations
- Company structure requirements

### Tax Topics
- PPh 21 (employee tax)
- PPh 22 (corporate tax 22%)
- PPN/VAT (11%)
- Expatriate tax residency rules
- Transfer pricing documentation

### Property Topics
- SHM vs HGB land titles
- PPAT notary process
- BPHTB (5% transfer tax)
- Foreign ownership restrictions

---

## Language Distribution

| Language | Code | Files |
|----------|------|-------|
| Indonesian | ID | 34 |
| English | EN | 30 |
| Javanese Timuran | JV | 8 |
| Balinese | BAN | 3 |
| Medan dialect | MDN | 1 |

---

## Usage Notes

1. **RAG Ingestion**: Run `backend/scripts/ingest_training_conversations.py`
2. **Collection Name**: `training_conversations`
3. **Chunking Strategy**: Q&A pairs grouped by 2-3 exchanges
4. **Metadata**: category, topic, visa_type, language, file_name
