"""
Giant Reasoner - Fase 1 dell'architettura Cellula-Gigante.

Il Sovrano ragiona LIBERAMENTE sulla domanda.
Usa tutta la sua potenza, senza limitazioni RAG.

L'utente NON vede mai questo output - e' interno.

ROUND 10-12 Enhancements:
- Structured prompt with domain detection
- Quality scoring for reasoning
- Multiple extraction helpers
- Configurable model tiers
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from llm.genai_client import get_genai_client

logger = logging.getLogger(__name__)


# ============================================================================ 
# CONFIGURATION
# ============================================================================ 

@dataclass
class GiantConfig:
    """Configuration for Giant Reasoner behavior."""
    temperature: float = 0.7
    max_tokens: int = 4000
    use_pro_model: bool = True  # Pro for complex, Flash for simple
    min_reasoning_length: int = 500
    quality_threshold: float = 0.6


DEFAULT_CONFIG = GiantConfig()


# ============================================================================ 
# DOMAIN-SPECIFIC PROMPTS
# ============================================================================ 

DOMAIN_CONTEXTS: dict[str, str] = {
    "visa": """
Focus su: classificazione visti (B1/VOA, B211B, E31A/E33G, E28A, KITAP),
requisiti sponsor, processo RPTKA→KITAS, timeline realistiche, common pitfalls.
Regolamenti chiave: UU 6/2011, Permen 22/2023, PP 34/2021.
""",
    "company": """
Focus su: strutture societarie (PT PMA vs PT Local vs CV), requisiti capitale
(2.5B versato, 10B piano), DNI/negative list, processo OSS/NIB.
Regolamenti chiave: UU 40/2007, PP 28/2025, PP 10/2021, UU 25/2007.
""",
    "tax": """
Focus su: tax residency (183 giorni), PPh 21/23/26, PPn, NPWP obblighi,
transfer pricing, tax treaty, SPT reporting, sanzioni.
Regolamenti chiave: UU 36/2008 (PPh), UU 42/2009 (PPn), PMK correlati.
""",
    "property": """
Focus su: restrizioni WNA (no Hak Milik), Hak Pakai vs HGB, due diligence,
nominee risks, zone (hijau/kuning/merah), proses AJB/PPAT.
Regolamenti chiave: UU 5/1960 (UUPA), PP 18/2021.
""",
    "f&b": """
Focus su: KBLI 56101/56102/56104, requisiti SLHS/Halal, liquor license,
zona commerciale, GoFood/GrabFood requirements, capital per location.
Regolamenti chiave: PP 28/2025 Art. 212, peraturan BPOM, BPJPH.
""",
    "employment": """
Focus su: TKA requirements, IMTA/RPTKA, ratio TKI:TKA, BPJS obblighi,
kontrak kerja, THR, termination rules, minimum compliance.
Regolamenti chiave: UU 13/2003, PP 34/2021, UU 11/2020 (Cipta Kerja).
"""
}

GIANT_REASONING_PROMPT = """
Sei un esperto di business, legge e fiscalita indonesiana con 20 anni di esperienza.

## IL TUO COMPITO

Ragiona in PROFONDITA sulla domanda dell'utente.
Non dare risposte superficiali. Pensa come un consulente senior che deve proteggere il cliente da errori costosi.

## CONTESTO DOMINIO SPECIFICO
{domain_context}

## COSA DEVI ANALIZZARE

1. **ANALISI LEGALE**: Identifica leggi/regolamenti specifici (PP, UU, Permen, PMK) con numeri e articoli
2. **RISCHI E TRAPPOLE**: Cosa potrebbe andare storto? Quali errori fanno comunemente gli stranieri?
3. **PROCESSO STEP-BY-STEP**: Sequenza esatta di passaggi, con timeline realistiche
4. **REQUISITI CONCRETI**: Documenti, capitale, prerequisiti - numeri precisi
5. **COSTI STIMATI**: Range di costi (government fees + professional fees)
6. **ALTERNATIVE**: Se esistono opzioni diverse, pro/contro di ciascuna

## FORMATO OUTPUT STRUTTURATO

### 📋 Analisi Legale
- [Regolamento 1]: [Rilevanza]
- [Regolamento 2]: [Rilevanza]

### ⚠️ Rischi e Trappole
1. [Rischio critico]
2. [Errore comune]
3. [Trappola nascosta]

### 📝 Processo Step-by-Step
1. **Step 1** (Timeline: X giorni): [Descrizione]
2. **Step 2** (Timeline: X giorni): [Descrizione]
...

### 📦 Requisiti
| Categoria | Requisito | Note |
|-----------|-----------|------|
| Capitale | ... | ... |
| Documenti | ... | ... |

### 💰 Costi Stimati
- Government fees: [range]
- Professional fees: [range]
- Total: [range]

### 🔄 Alternative
**Opzione A**: [Pro/Contro]
**Opzione B**: [Pro/Contro]

---

## DOMANDA UTENTE
{query}

## CONTESTO UTENTE
{user_context}

---

## IL TUO RAGIONAMENTO APPROFONDITO:
"""


@dataclass
class GiantResult:
    """Structured result from Giant reasoning."""
    reasoning: str
    key_points: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    legal_refs: list[str] = field(default_factory=list)
    costs: dict[str, str] = field(default_factory=dict)
    steps: list[dict[str, str]] = field(default_factory=list)
    quality_score: float = 0.0
    detected_domain: str = "general"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return {
            "reasoning": self.reasoning,
            "key_points": self.key_points,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "legal_refs": self.legal_refs,
            "costs": self.costs,
            "steps": self.steps,
            "quality_score": self.quality_score,
            "detected_domain": self.detected_domain
        }


def _detect_domain(query: str) -> str:
    """Detect the primary domain of the query."""
    query_lower = query.lower()

    domain_patterns: dict[str, list[str]] = {
        "visa": [r"kitas", r"kitap", r"visa", r"voa", r"e33g", r"e31a", r"e28a", r"imigrasi", r"stay\s*permit"],
        "company": [r"pt\s*pma", r"pma", r"company", r"societa", r"nib", r"oss", r"badan\s*usaha"],
        "tax": [r"pajak", r"tax", r"pph", r"ppn", r"npwp", r"spt", r"fiscal"],
        "property": [r"tanah", r"property", r"villa", r"land", r"hak\s*milik", r"hgb", r"hak\s*pakai"],
        "f&b": [r"restoran", r"restaurant", r"cafe", r"f&b", r"food", r"kitchen", r"halal"],
        "employment": [r"karyawan", r"employee", r"tka", r"imta", r"rptka", r"kerja", r"bpjs"]
    }

    for domain, patterns in domain_patterns.items():
        for pattern in patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return domain

    return "general"


async def giant_reason(
    query: str,
    user_context: str = "",
    config: GiantConfig | None = None
) -> dict[str, Any]:
    """
    Fase 1: Il Giant ragiona liberamente con domain-aware prompting.

    Args:
        query: User's question
        user_context: Known facts about the user
        config: Optional configuration override

    Returns:
        {
            "reasoning": str,
            "key_points": list,
            "warnings": list,
            "suggestions": list,
            "legal_refs": list,
            "costs": dict,
            "steps": list,
            "quality_score": float,
            "detected_domain": str
        }
    """
    cfg = config or DEFAULT_CONFIG
    client = get_genai_client()

    if not client.is_available:
        logger.error("Giant reasoning unavailable")
        return GiantResult(
            reasoning="Reasoning service temporarily unavailable.",
            quality_score=0.0
        ).to_dict()

    # Detect domain and get context
    domain = _detect_domain(query)
    domain_context = DOMAIN_CONTEXTS.get(domain, "Domanda generale su business in Indonesia.")

    # Select model based on complexity
    model = client.PRO_MODEL if cfg.use_pro_model else client.FLASH_MODEL

    prompt = GIANT_REASONING_PROMPT.format(
        query=query,
        user_context=user_context if user_context else "Nuovo utente, nessun contesto precedente.",
        domain_context=domain_context
    )

    # Retry logic with exponential backoff
    max_retries = 3
    retry_delays = [1.0, 2.0, 4.0]  # seconds
    
    for attempt in range(max_retries):
        try:
            response = await client.generate_content(
                contents=prompt,
                model=model,
                temperature=cfg.temperature,
                max_output_tokens=cfg.max_tokens
            )

            reasoning_text = response.get("text", "")
            
            # Validate response quality
            if not reasoning_text or len(reasoning_text) < 100:
                if attempt < max_retries - 1:
                    logger.warning(f"Giant reasoning too short ({len(reasoning_text)} chars), retrying...")
                    await asyncio.sleep(retry_delays[attempt])
                    continue
                else:
                    logger.error("Giant reasoning failed after retries: response too short")
                    return _fallback_reasoning(query, domain, user_context)

            # Extract structured data
            result = GiantResult(
                reasoning=reasoning_text,
                key_points=_extract_key_points(reasoning_text),
                warnings=_extract_warnings(reasoning_text),
                suggestions=_extract_suggestions(reasoning_text),
                legal_refs=_extract_legal_refs(reasoning_text),
                costs=_extract_costs(reasoning_text),
                steps=_extract_steps(reasoning_text),
                quality_score=_calculate_quality_score(reasoning_text, cfg),
                detected_domain=domain
            )

            logger.info(
                f"✅ Giant reasoning complete: {len(reasoning_text)} chars, "
                f"domain={domain}, quality={result.quality_score:.2f}, attempt={attempt + 1}"
            )

            return result.to_dict()

        except Exception as e:
            logger.warning(f"⚠️ Giant reasoning attempt {attempt + 1}/{max_retries} failed: {e}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delays[attempt])
                continue
            else:
                logger.error(f"❌ Giant reasoning failed after {max_retries} attempts: {e}")
                return _fallback_reasoning(query, domain, user_context)
    
    # Should never reach here, but safety fallback
    return _fallback_reasoning(query, domain, user_context)


def _extract_key_points(text: str) -> list[str]:
    """Estrae i punti chiave dal ragionamento."""
    key_points: list[str] = []
    sections = ["Analisi Legale", "Requisiti", "Strategia", "Processo"]
    for section in sections:
        pattern = rf"###?\s*[📋📝]*\s*{section}.*?\n(.*?)(?=###|\Z)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            content = match.group(1).strip()
            bullets = re.findall(r"[-*•]\s*(.+)", content)
            key_points.extend(bullets[:3])
    return key_points[:10]


def _extract_warnings(text: str) -> list[str]:
    """Estrae warning e trappole dal ragionamento."""
    warnings: list[str] = []

    # Section-based extraction
    pattern = r"###?\s*[⚠️]*\s*(Attenzione|Trappole|Warning|Rischi).*?\n(.*?)(?=###|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        content = match.group(2).strip()
        # Numbered items
        numbered = re.findall(r"\d+\.\s*\*?\*?([^*\n]+)", content)
        warnings.extend(numbered)
        # Bullet items
        bullets = re.findall(r"[-*•]\s*(.+)", content)
        warnings.extend(bullets)

    # Inline warnings
    inline_patterns = [
        r"(?:attenzione|warning|rischio|trappola|pericolo)[:\s]+([^.!]+[.!])",
        r"(?:NON|MAI|ILLEGALE)[^.]+[.]",
    ]
    for pattern in inline_patterns:
        inline = re.findall(pattern, text, re.IGNORECASE)
        warnings.extend(inline[:3])

    # Deduplicate and limit
    return list(dict.fromkeys(warnings))[:8]


def _extract_suggestions(text: str) -> list[str]:
    """Estrae suggerimenti strategici dal ragionamento."""
    suggestions: list[str] = []

    # Strategy section
    pattern = r"###?\s*(Strategia|Consiglio|Suggerimento).*?\n(.*?)(?=###|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        content = match.group(2).strip()
        bullets = re.findall(r"[-*•]\s*(.+)", content)
        suggestions.extend(bullets)

    # Alternatives section
    alt_pattern = r"###?\s*[🔄]*\s*Alternative.*?\n(.*?)(?=###|\Z)"
    alt_match = re.search(alt_pattern, text, re.DOTALL | re.IGNORECASE)
    if alt_match:
        content = alt_match.group(1).strip()
        # Look for Option A/B patterns
        options = re.findall(r"\*?\*?Opzione\s*[A-Z]\*?\*?[:\s]+([^*\n]+)", content)
        suggestions.extend([f"Alternativa: {o.strip()}" for o in options])
        # Also bullets
        bullets = re.findall(r"[-*•]\s*(.+)", content)
        suggestions.extend([f"Alternativa: {b}" for b in bullets if "Opzione" not in b])

    return list(dict.fromkeys(suggestions))[:6]


def _extract_legal_refs(text: str) -> list[str]:
    """Estrae riferimenti legali (UU, PP, Permen, PMK, etc.)."""
    patterns = [
        r"UU\s*(?:No\.?)?\s*\d+[/-]\d{4}",                    # UU 6/2011
        r"PP\s*(?:No\.?)?\s*\d+[/-]\d{4}",                    # PP 28/2025
        r"Permen\s*(?:No\.?)?\s*\d+[/-]\d{4}",                # Permen 22/2023
        r"PMK\s*(?:No\.?)?\s*\d+[/-]\d{4}",                   # PMK xxx/2024
        r"Perpres\s*(?:No\.?)?\s*\d+[/-]\d{4}",               # Perpres
        r"Peraturan\s+\w+\s*(?:No\.?)?\s*\d+[/-]\d{4}",       # Generic Peraturan
        r"Art(?:icle|\.|\s)\s*\d+(?:\s*(?:comma|ayat)\s*\d+)?", # Art. 212 comma 3
    ]

    refs: list[str] = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        refs.extend(matches)

    # Clean and deduplicate
    cleaned = [r.strip() for r in refs]
    return list(dict.fromkeys(cleaned))[:15]


def _extract_costs(text: str) -> dict[str, str]:
    """Estrae informazioni sui costi dal ragionamento."""
    costs: dict[str, str] = {}

    # Look for costs section
    pattern = r"###?\s*[💰]*\s*Costi.*?\n(.*?)(?=###|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)

    if match:
        content = match.group(1)

        # Government fees
        gov_match = re.search(r"Government\s*fees?[:\s]+([^\n]+)", content, re.IGNORECASE)
        if gov_match:
            costs["government_fees"] = gov_match.group(1).strip()

        # Professional fees
        prof_match = re.search(r"Professional\s*fees?[:\s]+([^\n]+)", content, re.IGNORECASE)
        if prof_match:
            costs["professional_fees"] = prof_match.group(1).strip()

        # Total
        total_match = re.search(r"Total[:\s]+([^\n]+)", content, re.IGNORECASE)
        if total_match:
            costs["total"] = total_match.group(1).strip()

    # Fallback: look for IDR/juta amounts
    if not costs:
        idr_amounts = re.findall(r"(\d+(?:[.,]\d+)?\s*(?:juta|milioni|miliar|miliardi|B|M)?\s*(?:IDR|Rp)?)", text)
        if idr_amounts:
            costs["estimated"] = ", ".join(idr_amounts[:3])

    return costs


def _extract_steps(text: str) -> list[dict[str, str]]:
    """Estrae i passaggi del processo dal ragionamento."""
    steps: list[dict[str, str]] = []

    # Look for step-by-step section
    pattern = r"###?\s*[📝]*\s*(?:Processo|Steps?|Passaggi).*?\n(.*?)(?=###|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)

    if match:
        content = match.group(1)

        # Pattern: 1. **Step Name** (Timeline: X): Description
        step_pattern = r"(\d+)\.\s*\*?\*?([^*\n(]+)\*?\*?\s*(?:\((?:Timeline|Tempo)[:\s]*([^)]+)\))?[:\s]*([^\n]*)"
        step_matches = re.findall(step_pattern, content)

        for num, name, timeline, desc in step_matches:
            steps.append({
                "step": num,
                "name": name.strip(),
                "timeline": timeline.strip() if timeline else "",
                "description": desc.strip()
            })

    # Fallback: look for numbered items with arrows
    if not steps:
        arrow_pattern = r"(\d+)\.\s*([^→\n]+)(?:→\s*([^\n]+))?"
        arrow_matches = re.findall(arrow_pattern, text)
        for num, action, result in arrow_matches[:8]:
            steps.append({
                "step": num,
                "name": action.strip(),
                "timeline": "",
                "description": result.strip() if result else ""
            })

    return steps[:10]


def _calculate_quality_score(text: str, config: GiantConfig) -> float:
    """Calcola un punteggio di qualita del ragionamento (0.0 - 1.0)."""
    score = 0.0
    max_score = 6.0

    # 1. Length check (min 500 chars for substantial reasoning)
    if len(text) >= config.min_reasoning_length:
        score += 1.0
    elif len(text) >= config.min_reasoning_length // 2:
        score += 0.5

    # 2. Has legal references
    legal_refs = _extract_legal_refs(text)
    if len(legal_refs) >= 2:
        score += 1.0
    elif len(legal_refs) >= 1:
        score += 0.5

    # 3. Has structured sections
    section_markers = ["###", "**Analisi", "**Rischi", "**Processo", "**Requisiti", "**Costi"]
    sections_found = sum(1 for marker in section_markers if marker in text)
    if sections_found >= 4:
        score += 1.0
    elif sections_found >= 2:
        score += 0.5

    # 4. Has warnings/risks identified
    warnings = _extract_warnings(text)
    if len(warnings) >= 2:
        score += 1.0
    elif len(warnings) >= 1:
        score += 0.5

    # 5. Has concrete numbers/data
    number_patterns = [r"\d+\s*(?:juta|miliar|miliardi)", r"\d+\s*(?:giorni|settimane|mesi)", r"\d+%"]
    numbers_found = sum(1 for p in number_patterns if re.search(p, text))
    if numbers_found >= 2:
        score += 1.0
    elif numbers_found >= 1:
        score += 0.5

    # 6. No obvious errors (placeholder text, etc.)
    error_markers = ["[TODO]", "[INSERT]", "lorem ipsum", "xxx"]
    has_errors = any(marker.lower() in text.lower() for marker in error_markers)
    if not has_errors:
        score += 1.0

    return round(score / max_score, 2)


def _fallback_reasoning(query: str, domain: str, user_context: str) -> dict[str, Any]:
    """
    Fallback reasoning when Giant LLM is unavailable.
    Creates a basic structured response from domain knowledge.
    """
    logger.warning(f"🔄 Using fallback reasoning for domain: {domain}")
    
    domain_fallbacks: dict[str, str] = {
        "visa": """
        Per questioni sui visti in Indonesia, ti consiglio di consultare:
        - Permen 22/2023 per i nuovi codici visto (E31A, E33G, E28A)
        - Ogni KITAS lavorativo richiede sponsor
        - Processo tipico: RPTKA → Notifikasi → Telex → VITAS → KITAS
        
        Contatta il team Bali Zero per assistenza specifica sul tuo caso.
        """,
        "company": """
        Per costituire una PT PMA in Indonesia:
        - Capitale minimo versato: 2.5 Miliardi IDR
        - Piano investimento minimo: 10 Miliardi IDR (varia per settore)
        - Processo: Notaio → OSS/NIB → NPWP → Conto bancario
        
        Verifica sempre la DNI (Daftar Negatif Investasi) per il tuo settore.
        """,
        "tax": """
        Aspetti fiscali importanti:
        - NPWP obbligatorio per direttori stranieri entro 30 giorni dal KITAS
        - Tax resident se presenti 183+ giorni o con KITAS
        - PPh 21 mensile obbligatorio per stipendi
        - SPT Tahunan entro aprile
        
        Consulta un consulente fiscale per la tua situazione specifica.
        """,
        "general": """
        Per assistenza su business in Indonesia, il team Bali Zero può aiutarti con:
        - Setup PT PMA
        - Visti e KITAS
        - Compliance fiscale
        - Licenze e permessi
        
        Contattaci per una consulenza personalizzata.
        """
    }
    
    fallback_text = domain_fallbacks.get(domain, domain_fallbacks["general"])
    
    return GiantResult(
        reasoning=fallback_text.strip(),
        key_points=["Consulta il team Bali Zero per dettagli specifici"],
        warnings=["Informazioni generali - verifica sempre con consulente"],
        suggestions=["Contatta Bali Zero per assistenza personalizzata"],
        legal_refs=[],
        costs={},
        steps=[],
        quality_score=0.3,  # Low quality but functional
        detected_domain=domain
    ).to_dict()