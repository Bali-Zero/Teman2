# Cell-Giant Architecture

> "Non costruire un gigante. Diventa la coscienza di uno che esiste già."

## Overview

Cell-Giant è un'architettura di reasoning ibrida che combina:
- **Il Gigante** (LLM) → Ragionamento profondo e libero
- **La Cellula** (KB Bali Zero) → Correzioni, calibrazioni, insights pratici
- **Zantara** → Voce unica che sintetizza tutto

L'utente vede **SOLO Zantara**. Mai riferimenti interni a "Giant" o "Cell".

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER QUERY                                   │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PHASE 1: GIANT REASONER                           │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • Domain detection (visa, company, tax, property, f&b)     │    │
│  │  • Deep reasoning with PRO_MODEL                            │    │
│  │  • Extract: key_points, warnings, legal_refs, costs, steps  │    │
│  │  • Quality scoring (0.0 - 1.0)                              │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PHASE 2: CELL CONSCIENCE                          │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  📍 CORRECTIONS (15+ patterns)                              │    │
│  │     - Critical: B211A deprecated, nominee illegal, etc.     │    │
│  │     - High: Tax residency rules, KITAP requirements         │    │
│  │     - Override Giant reasoning when triggered               │    │
│  │                                                              │    │
│  │  💡 ENHANCEMENTS (90+ insights across 20 topics)            │    │
│  │     - Practical tips from Bali Zero experience              │    │
│  │     - Timeline corrections, hidden requirements             │    │
│  │                                                              │    │
│  │  💰 CALIBRATIONS (21 services)                              │    │
│  │     - Official Bali Zero pricing                            │    │
│  │     - Accurate timelines                                    │    │
│  │     - Consultant assignments                                │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PHASE 3: ZANTARA SYNTHESIZER                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  • Tone detection (professional, casual, urgent, educational)│    │
│  │  • CORRECTIONS override Giant when severity=critical        │    │
│  │  • Response validation (no leaked internal terms)           │    │
│  │  • FLASH_MODEL for speed                                    │    │
│  │  • Streaming support available                              │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       ZANTARA RESPONSE                               │
│  "Bro, per il KITAS E33G ti serve proof of income $2k/mese..."      │
└─────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Basic Usage

```python
from services.rag.agentic.cell_giant import cell_giant_pipeline

# Sync pipeline
response = await cell_giant_pipeline(
    query="Come apro una PT PMA per ristorante?",
    user_context="Utente italiano, primo contatto",
    user_facts=["Budget: 500 juta", "Location: Canggu"]
)
print(response)
```

### Streaming Usage

```python
from services.rag.agentic.cell_giant import cell_giant_pipeline_stream

async for item in cell_giant_pipeline_stream(
    query="Come ottengo un KITAS E33G?",
    user_context="Digital nomad"
):
    if item["type"] == "metadata":
        print(f"Quality: {item['giant_quality']}")
    elif item["type"] == "chunk":
        print(item["content"], end="")
    elif item["type"] == "done":
        print("\n--- Complete ---")
```

### Individual Phases

```python
from services.rag.agentic.cell_giant import (
    giant_reason,
    cell_calibrate,
    synthesize_as_zantara,
    GiantConfig,
    SynthesizerConfig,
    ResponseTone
)

# Phase 1: Giant reasons
giant_result = await giant_reason(
    query="PT PMA per ristorante",
    config=GiantConfig(use_pro_model=True)
)

# Phase 2: Cell calibrates
cell_result = await cell_calibrate(
    query="PT PMA per ristorante",
    giant_reasoning=giant_result
)

# Phase 3: Synthesize
response = await synthesize_as_zantara(
    query="PT PMA per ristorante",
    giant_reasoning=giant_result,
    cell_calibration=cell_result,
    config=SynthesizerConfig(tone=ResponseTone.PROFESSIONAL)
)
```

## Configuration

### GiantConfig

```python
@dataclass
class GiantConfig:
    temperature: float = 0.7        # Creativity level
    max_tokens: int = 4000          # Max reasoning length
    use_pro_model: bool = True      # PRO for complex, FLASH for simple
    min_reasoning_length: int = 500 # Minimum chars for quality
    quality_threshold: float = 0.6  # Minimum acceptable quality
```

### SynthesizerConfig

```python
@dataclass
class SynthesizerConfig:
    tone: ResponseTone = ResponseTone.CASUAL  # Default: Jaksel style
    max_words: int = 600                       # Response word limit
    include_citations: bool = True             # Include legal refs
    include_pricing: bool = True               # Include Bali Zero pricing
    temperature: float = 0.4                   # Lower for consistency
```

### ResponseTone

```python
class ResponseTone(Enum):
    PROFESSIONAL = "professional"  # Formal, detailed
    CASUAL = "casual"              # Jaksel style (default)
    URGENT = "urgent"              # Critical warnings emphasized
    EDUCATIONAL = "educational"    # Step-by-step teaching
```

## KNOWN_CORRECTIONS

Correzioni ad alta priorità che sovrascrivono il ragionamento del Giant.

| Key | Severity | Trigger Example |
|-----|----------|-----------------|
| `b211a` | critical | "B211A visa" |
| `kitas_sponsor` | critical | "KITAS senza sponsor" |
| `dni_restrictions` | critical | "PMA 100% qualsiasi settore" |
| `freelance_illegal` | critical | "freelance legale Indonesia" |
| `tourist_visa_work` | critical | "VOA lavorare" |
| `nominee arrangement` | critical | "nominee", "prestanome" |
| `pt local straniero` | critical | "straniero PT local" |
| `oss_not_automatic` | high | "OSS automatico" |
| `tax_resident_183` | high | "sotto 183 giorni no tax" |
| ... | ... | ... |

## PRACTICAL_INSIGHTS Topics

20 topic categories con 90+ insights:

**Core**: `pt_pma`, `kitas`, `tax`, `f&b`, `ghost_kitchen`

**Extended**: `banking`, `real_estate`, `employment`, `permits`, `digital_nomad`, `import_export`, `tech_startup`, `hospitality`, `manufacturing`, `retail`, `education`, `healthcare`, `construction`, `media_creative`, `logistics`

## BALI_ZERO_SERVICES

21 servizi con pricing ufficiale:

| Category | Services |
|----------|----------|
| **Company** | `pt_pma_setup`, `pt_pma_premium` |
| **Visa** | `kitas_e33g`, `kitas_e31a_worker`, `kitas_e28a_investor`, `kitas_renewal`, `kitap_conversion`, `visa_extension` |
| **F&B** | `ghost_kitchen_setup`, `restaurant_full_setup`, `liquor_license_skpla`, `halal_certification` |
| **Hospitality** | `villa_rental_permit`, `hotel_license` |
| **Tax** | `tax_registration`, `tax_monthly_reporting`, `tax_annual_spt` |
| **Admin** | `bank_account_opening`, `virtual_office`, `company_secretary` |
| **Trade/IP** | `import_license_api`, `trademark_registration` |

## Testing

```bash
# Run all Cell-Giant tests
pytest tests/unit/rag/test_cell_giant.py -v

# Run specific test class
pytest tests/unit/rag/test_cell_giant.py::TestKnownCorrections -v

# Run with coverage
pytest tests/unit/rag/test_cell_giant.py --cov=services.rag.agentic.cell_giant
```

## File Structure

```
cell_giant/
├── __init__.py              # Exports and module docs
├── README.md                # This file
├── giant_reasoner.py        # Phase 1: Free reasoning
├── cell_conscience.py       # Phase 2: KB calibration
└── zantara_synthesizer.py   # Phase 3: Voice synthesis
```

## Rules for Developers

1. **No model names in code** - Use `client.PRO_MODEL` / `client.FLASH_MODEL`
2. **User sees only Zantara** - Never leak internal terminology
3. **Type hints everywhere** - Python 3.10+ style
4. **Corrections override Giant** - When severity=critical
5. **Pricing from BALI_ZERO_SERVICES only** - Never hallucinate prices

## Version History

- **v1.0** - Initial architecture (3 phases)
- **v2.0** - Round 1-20 enhancements:
  - 15 new KNOWN_CORRECTIONS
  - 15 new PRACTICAL_INSIGHTS topics
  - 18 new BALI_ZERO_SERVICES
  - Domain-aware prompting
  - Quality scoring
  - Tone adaptation
  - Streaming support
  - Full test suite

