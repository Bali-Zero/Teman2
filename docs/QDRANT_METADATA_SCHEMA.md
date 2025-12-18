# Qdrant Metadata Schema Documentation

Questo documento definisce lo schema metadata standardizzato per tutte le collezioni Qdrant.

## Schema per Collezione

### bali_zero_pricing

**Descrizione**: Service pricing information

**Campi**:

| Campo | Tipo | Obbligatorio | Descrizione |
|-------|------|--------------|-------------|
| `service_name` | string | ✅ | Name of the service |
| `service_type` | string | ✅ | Type (visa, company, tax, etc.) |
| `price_usd` | number | ❌ | Price in USD |
| `price_idr` | number | ❌ | Price in IDR |
| `currency` | string | ❌ | Currency code |
| `valid_from` | string | ❌ | Valid from date (ISO format) |
| `valid_until` | string | ❌ | Valid until date (ISO format) |
| `source` | string | ✅ | Source of pricing information |

### bali_zero_team

**Descrizione**: Team member profiles

**Campi**:

| Campo | Tipo | Obbligatorio | Descrizione |
|-------|------|--------------|-------------|
| `id` | string | ✅ | Unique team member ID |
| `name` | string | ✅ | Full name |
| `email` | string | ✅ | Email address |
| `role` | string | ✅ | Job role |
| `department` | string | ✅ | Department |
| `team` | string | ✅ | Team name |
| `languages` | array | ✅ | List of language codes |
| `expertise_level` | string | ✅ | Expertise level |
| `location` | string | ❌ | Location |
| `emotional_preferences` | object | ❌ | Emotional preferences |

### visa_oracle

**Descrizione**: Visa and immigration regulations

**Campi**:

| Campo | Tipo | Obbligatorio | Descrizione |
|-------|------|--------------|-------------|
| `visa_type` | string | ✅ | Visa type code (e.g., C7, D1) |
| `visa_category` | string | ❌ | Category (tourist, business, work) |
| `entry_type` | string | ❌ | Single/Multiple entry |
| `duration` | string | ❌ | Visa duration |
| `fee_usd` | number | ❌ | Fee in USD |
| `requirements` | array | ❌ | List of requirements |
| `source_document` | string | ❌ | Source document name |
| `last_updated` | string | ❌ | Last update date |

### kbli_unified

**Descrizione**: Business classification codes (KBLI)

**Campi**:

| Campo | Tipo | Obbligatorio | Descrizione |
|-------|------|--------------|-------------|
| `kbli_code` | string | ✅ | 5-digit KBLI code |
| `kbli_description` | string | ✅ | Business activity description |
| `category` | string | ❌ | Business category |
| `investment_minimum` | number | ❌ | Minimum investment (IDR) |
| `risk_level` | string | ❌ | Risk level (Low/Medium/High) |
| `required_licenses` | array | ❌ | Required licenses |
| `source` | string | ❌ | Source document |

### tax_genius

**Descrizione**: Indonesian tax regulations

**Campi**:

| Campo | Tipo | Obbligatorio | Descrizione |
|-------|------|--------------|-------------|
| `tax_type` | string | ✅ | Type of tax |
| `tax_rate` | number | ❌ | Tax rate percentage |
| `tax_bracket` | object | ❌ | Tax bracket information |
| `regulation_reference` | string | ❌ | Regulation reference |
| `effective_date` | string | ❌ | Effective date |
| `source_document` | string | ❌ | Source document |

### legal_unified

**Descrizione**: Indonesian laws and regulations

**Campi**:

| Campo | Tipo | Obbligatorio | Descrizione |
|-------|------|--------------|-------------|
| `law_id` | string | ✅ | Law identifier |
| `law_title` | string | ✅ | Law title |
| `pasal` | string | ❌ | Article number |
| `status_vigensi` | string | ❌ | Status (berlaku/dicabut) |
| `wilayah` | string | ❌ | Applicable region |
| `year` | number | ❌ | Year of law |
| `source` | string | ❌ | Source document |

### knowledge_base

**Descrizione**: General knowledge base

**Campi**:

| Campo | Tipo | Obbligatorio | Descrizione |
|-------|------|--------------|-------------|
| `title` | string | ✅ | Document title |
| `category` | string | ❌ | Content category |
| `tags` | array | ❌ | Content tags |
| `source` | string | ❌ | Source |
| `language` | string | ❌ | Language code |
| `last_updated` | string | ❌ | Last update date |

### property_unified

**Descrizione**: Property and real estate information

**Campi**:

| Campo | Tipo | Obbligatorio | Descrizione |
|-------|------|--------------|-------------|
| `property_type` | string | ✅ | Type of property |
| `location` | string | ✅ | Property location |
| `price_range` | object | ❌ | Price range |
| `area` | number | ❌ | Area in square meters |
| `source` | string | ❌ | Source |
