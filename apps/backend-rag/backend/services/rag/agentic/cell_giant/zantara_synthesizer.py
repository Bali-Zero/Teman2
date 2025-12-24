"""
Zantara Synthesizer - Fase 3 dell'architettura Cellula-Gigante.

Combina il ragionamento del Sovrano + le calibrazioni del Consigliere
in UNA VOCE UNICA: Zantara.

L'utente vede SOLO Zantara. Mai riferimenti interni.

ROUND 13-15 Enhancements:
- Response quality validation
- Tone adaptation based on query type
- Smart formatting (tables, bullets, etc.)
- Citation handling
- Fallback improvements
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from llm.genai_client import get_genai_client

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

class ResponseTone(Enum):
    """Tone variations for Zantara responses."""
    PROFESSIONAL = "professional"  # Formal, detailed
    CASUAL = "casual"              # Jaksel style, friendly
    URGENT = "urgent"              # Critical warnings emphasized
    EDUCATIONAL = "educational"    # Step-by-step, teaching


@dataclass
class SynthesizerConfig:
    """Configuration for Zantara Synthesizer."""
    tone: ResponseTone = ResponseTone.CASUAL
    max_words: int = 600
    min_words: int = 150  # Minimum response length
    include_citations: bool = True
    include_pricing: bool = True
    temperature: float = 0.4


DEFAULT_SYNTH_CONFIG = SynthesizerConfig()


# ============================================================================
# TONE-SPECIFIC PROMPTS
# ============================================================================

TONE_INSTRUCTIONS: dict[ResponseTone, str] = {
    ResponseTone.PROFESSIONAL: """
Stile: Formale e dettagliato. Usa terminologia tecnica corretta.
Evita slang eccessivo. Struttura la risposta con sezioni chiare.
Sii autorevole ma accessibile.
""",
    ResponseTone.CASUAL: """
Stile: \"Business Jaksel\" - professionale ma casual e moderno.
Usa un mix naturale di italiano e termini business/slang inglesi (\"basically\", \"literally\", \"guys\").
Tono amichevole ma autorevole. Vai dritto al punto senza fronzoli.
Esempio: \"Allora guys, per il KITAS la situazione è tricky...\"
""",
    ResponseTone.URGENT: """
Stile: ATTENZIONE massima sui rischi. Evidenzia i pericoli PRIMA di tutto.
Usa emoji ⚠️🚨 per warning critici. Sii diretto, serio e chiaro sui rischi legali.
Non addolcire la pillola se c'e rischio di deportazione o multe.
""",
    ResponseTone.EDUCATIONAL: """
Stile: Didattico e step-by-step. Spiega il \"perche\" dietro ogni consiglio.
Usa numerazione chiara per i passaggi. Aggiungi contesto culturale per chi e nuovo in Indonesia.
Sii paziente e chiaro.
"""
}

SYNTHESIS_PROMPT = """# TU SEI ZANTARA

Sei Zantara, il consulente AI di Bali Zero, con 20 anni di esperienza reale in Indonesia.
Non sei un bot generico. Sei un esperto che vive a Bali, conosce la legge E la strada.

{tone_instruction}

## LA TUA PERSONALITA CORE

- **Diretto**: Vai al punto, niente giri di parole o intro filosofici.
- **Pratico**: Dai consigli actionable, non teoria astratta.
- **Onesto**: Se c'e un rischio, lo dici chiaramente. Non vendere sogni impossibili.
- **Protettivo**: Il tuo cliente deve essere protetto da errori costosi (scam, overstay, agenti falsi).
- **Proattivo**: Anticipa le domande successive.

## IL TUO COMPITO

Hai due fonti di informazione da sintetizzare:

1. **RAGIONAMENTO BASE**: Analisi approfondita (quality score: {quality_score})
2. **CALIBRAZIONI VERIFICATE**: Dati specifici Bali Zero, correzioni, insights (VERITÀ ASSOLUTA)

Devi creare UNA risposta coerente che:
- Integra le CORREZIONI in modo fluido (es. \"Molti pensano X, ma in realta Y perche...\").
- Usa i PREZZI/TEMPI solo dalle calibrazioni Bali Zero.
- Arricchisce con INSIGHTS pratici.
- Parla con la TUA voce unica.
- NON menzionare MAI \"ragionamento base\" o \"calibrazioni\" - sono interni.

## REGOLE CRITICHE

1. **CORREZIONI PRIORITARIE**: Se c'e una correzione critica, devi dirlo subito. Ignora il ragionamento base se contraddice la correzione.
2. **DATI BALI ZERO**: Usa SOLO i prezzi e tempi forniti nelle calibrazioni. Se non ci sono, di \"contattaci per un preventivo\".
3. **STRUTTURA**: Usa bullet points, bold per concetti chiave, e tabelle se necessario.
4. **LUNGHEZZA**: Massimo {max_words} parole. Sii conciso.
5. **FONTI**: Se ci sono riferimenti legali, citarli (es. \"Secondo la Permen 22/2023...\").

## FORMATO SUGGERITO

Per domande procedurali:
1. \"Straight to the point\" answer (Si/No/Dipende).
2. Steps numerati con timeline realistiche.
3. Costi/servizi Bali Zero (se pertinenti).
4. \"Watch out for\" (Rischi/Trappole).
5. Call to action discreta.

Per domande informative:
1. Spiegazione chiara e diretta.
2. Dettagli tecnici/legali importanti.
3. Insight pratico (\"Pro tip\").
4. Warning se presenti.

---

## RAGIONAMENTO BASE (Quality: {quality_score})
{giant_reasoning}

## RIFERIMENTI LEGALI ESTRATTI
{legal_refs}

---

## CALIBRAZIONI VERIFICATE BALI ZERO (La Verità)

### 🚨 CORREZIONI (PRIORITA MASSIMA - Sovrascrivono tutto):
{corrections}

### 💰 SERVIZI E PREZZI BALI ZERO:
{calibrations}

### 💡 INSIGHTS PRATICI (Esperienza sul campo):
{enhancements}

### 👤 MEMORIA UTENTE:
{user_memory}

---

## DOMANDA UTENTE
{query}

---

## LA TUA RISPOSTA (come Zantara):
"""


def _detect_tone(query: str, corrections: list[dict[str, Any]]) -> ResponseTone:
    """Detect appropriate tone based on query and corrections."""
    query_lower = query.lower()

    # Critical corrections = urgent tone
    critical_corrections = [c for c in corrections if c.get("severity") == "critical"]
    if critical_corrections:
        return ResponseTone.URGENT

    # How-to questions = educational tone
    educational_patterns = [r"come\s+(?:faccio|posso|si\s+fa)", r"how\s+(?:do|can|to)", r"step", r"processo", r"procedure", r"guida"]
    for pattern in educational_patterns:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return ResponseTone.EDUCATIONAL

    # Formal/legal questions = professional tone
    formal_patterns = [r"requisit", r"legal", r"obblig", r"sanzioni", r"penale", r"legge", r"regolamento"]
    for pattern in formal_patterns:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return ResponseTone.PROFESSIONAL

    # Default: casual Jaksel style
    return ResponseTone.CASUAL


def _validate_response(response: str, corrections: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    """Validate that the response incorporates critical corrections."""
    issues: list[str] = []

    # Check minimum length (characters)
    if len(response) < 100:
        issues.append(f"Response too short ({len(response)} chars < 100 min)")

    # Check that critical corrections are reflected
    critical = [c for c in corrections if c.get("severity") == "critical"]
    for corr in critical:
        # Check if key terms from correction appear in response
        key_terms = corr.get("correction", "").split()[:5]  # First 5 words
        # Simple check: at least some words should match
        terms_found = sum(1 for term in key_terms if term.lower() in response.lower())
        if terms_found < 2:
            # Try checking error key
            if corr.get('error_key', '').lower() not in response.lower():
                 issues.append(f"Critical correction may not be reflected: {corr.get('error_key', 'unknown')}")

    # Check for forbidden patterns (internal terminology leak)
    forbidden = ["ragionamento base", "calibrazione", "giant", "cell conscience", "severity", "quality score"]
    for pattern in forbidden:
        if pattern.lower() in response.lower():
            issues.append(f"Internal term leaked: {pattern}")

    return len(issues) == 0, issues


async def synthesize_as_zantara(
    query: str,
    giant_reasoning: dict[str, Any],
    cell_calibration: dict[str, Any],
    config: SynthesizerConfig | None = None
) -> str:
    """
    Fase 3: Sintetizza tutto come Zantara.

    Args:
        query: User's original question
        giant_reasoning: Output from giant_reason()
        cell_calibration: Output from cell_calibrate()
        config: Optional synthesizer configuration

    Returns:
        La risposta finale come Zantara (str)
    """
    cfg = config or DEFAULT_SYNTH_CONFIG
    client = get_genai_client()

    if not client.is_available:
        logger.error("Synthesis unavailable")
        return _fallback_synthesis(giant_reasoning, cell_calibration)

    # Get corrections and detect appropriate tone
    corrections = cell_calibration.get("corrections", [])
    tone = _detect_tone(query, corrections) if cfg.tone == ResponseTone.CASUAL else cfg.tone

    # Format all inputs
    corrections_text = _format_corrections(corrections)
    calibrations_text = _format_calibrations(cell_calibration.get("calibrations", {}))
    enhancements_text = _format_enhancements(cell_calibration.get("enhancements", []))
    user_memory_text = _format_user_memory(cell_calibration.get("user_memory", []))
    legal_refs_text = _format_legal_refs(giant_reasoning.get("legal_refs", []))

    # Get quality score from giant reasoning
    quality_score = giant_reasoning.get("quality_score", 0.5)

    prompt = SYNTHESIS_PROMPT.format(
        tone_instruction=TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS[ResponseTone.CASUAL]),
        quality_score=f"{quality_score:.1%}",
        max_words=cfg.max_words,
        giant_reasoning=giant_reasoning.get("reasoning", "Nessun ragionamento disponibile."),
        legal_refs=legal_refs_text,
        corrections=corrections_text,
        calibrations=calibrations_text,
        enhancements=enhancements_text,
        user_memory=user_memory_text,
        query=query
    )

    try:
        response = await client.generate_content(
            contents=prompt,
            model=client.FLASH_MODEL,
            temperature=cfg.temperature,
            max_output_tokens=2500
        )

        final_text = response.get("text", "")

        # Validate response length
        word_count = len(final_text.split())
        if word_count < cfg.min_words:
            logger.warning(f"Response too short ({word_count} words < {cfg.min_words} min), expanding...")
            final_text = _expand_response(final_text, cfg.min_words, query, corrections, cell_calibration)
        elif word_count > cfg.max_words * 1.2:  # Allow 20% overage
            logger.info(f"Response too long ({word_count} words > {cfg.max_words} max), truncating...")
            final_text = _truncate_response(final_text, cfg.max_words)

        # Validate response
        is_valid, issues = _validate_response(final_text, corrections)
        if not is_valid:
            logger.warning(f"Response validation issues: {issues}")
            # Still return, but log for monitoring

        # Clean up any internal terminology that might have leaked
        final_text = _clean_response(final_text)

        logger.info(
            f"Zantara synthesis complete: {len(final_text)} chars, "
            f"{len(corrections)} corrections, tone={tone.value}, valid={is_valid}"
        )

        return final_text

    except Exception as e:
        logger.error(f"Zantara synthesis failed: {e}")
        return _fallback_synthesis(giant_reasoning, cell_calibration)


# ============================================================================
# STREAMING SYNTHESIS
# ============================================================================

async def synthesize_as_zantara_stream(
    query: str,
    giant_reasoning: dict[str, Any],
    cell_calibration: dict[str, Any],
    config: SynthesizerConfig | None = None
):
    """
    Streaming version of synthesize_as_zantara.

    Yields chunks of the response as they're generated.

    Args:
        query: User's original question
        giant_reasoning: Output from giant_reason()
        cell_calibration: Output from cell_calibrate()
        config: Optional synthesizer configuration

    Yields:
        str chunks of the response
    """
    cfg = config or DEFAULT_SYNTH_CONFIG
    client = get_genai_client()

    if not client.is_available:
        logger.error("Synthesis unavailable for streaming")
        fallback = _fallback_synthesis(giant_reasoning, cell_calibration)
        yield fallback
        return

    # Get corrections and detect appropriate tone
    corrections = cell_calibration.get("corrections", [])
    tone = _detect_tone(query, corrections) if cfg.tone == ResponseTone.CASUAL else cfg.tone

    # Format all inputs
    corrections_text = _format_corrections(corrections)
    calibrations_text = _format_calibrations(cell_calibration.get("calibrations", {}))
    enhancements_text = _format_enhancements(cell_calibration.get("enhancements", []))
    user_memory_text = _format_user_memory(cell_calibration.get("user_memory", []))
    legal_refs_text = _format_legal_refs(giant_reasoning.get("legal_refs", []))
    quality_score = giant_reasoning.get("quality_score", 0.5)

    prompt = SYNTHESIS_PROMPT.format(
        tone_instruction=TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS[ResponseTone.CASUAL]),
        quality_score=f"{quality_score:.1%}",
        max_words=cfg.max_words,
        giant_reasoning=giant_reasoning.get("reasoning", "Nessun ragionamento disponibile."),
        legal_refs=legal_refs_text,
        corrections=corrections_text,
        calibrations=calibrations_text,
        enhancements=enhancements_text,
        user_memory=user_memory_text,
        query=query
    )

    try:
        accumulated_text = ""

        async for chunk in client.generate_content_stream(
            contents=prompt,
            model=client.FLASH_MODEL,
            temperature=cfg.temperature,
            max_output_tokens=2500
        ):
            if chunk:
                accumulated_text += chunk
                yield chunk

        # Log completion
        logger.info(
            f"Zantara streaming complete: {len(accumulated_text)} chars, "
            f"{len(corrections)} corrections, tone={tone.value}"
        )

    except Exception as e:
        logger.error(f"Zantara streaming failed: {e}")
        fallback = _fallback_synthesis(giant_reasoning, cell_calibration)
        yield fallback


# ============================================================================
# FULL PIPELINE ORCHESTRATION
# ============================================================================

async def cell_giant_pipeline(
    query: str,
    user_context: str = "",
    user_facts: list[str] | None = None,
    user_id: str | None = None,
    stream: bool = False
) -> str | None:
    """
    Complete Cell-Giant pipeline: Giant → Cell → Zantara.

    This is the main entry point for the architecture.

    Args:
        query: User's question
        user_context: Known context about the user
        user_facts: List of facts about the user
        user_id: User identifier for memory lookup
        stream: If True, returns None (use cell_giant_pipeline_stream instead)

    Returns:
        Final Zantara response (str), or None if stream=True
    """
    from .giant_reasoner import giant_reason, GiantConfig
    from .cell_conscience import cell_calibrate

    logger.info(f"Cell-Giant pipeline started for query: {query[:50]}...")

    # Phase 1: Giant reasons freely
    giant_config = GiantConfig(use_pro_model=True)
    giant_result = await giant_reason(
        query=query,
        user_context=user_context,
        config=giant_config
    )
    logger.info(f"Giant phase complete: quality={giant_result.get('quality_score', 0):.2f}")

    # Phase 2: Cell calibrates with corrections and enhancements
    cell_result = await cell_calibrate(
        query=query,
        giant_reasoning=giant_result,
        user_id=user_id,
        user_facts=user_facts
    )
    logger.info(
        f"Cell phase complete: {len(cell_result.get('corrections', []))} corrections, "
        f"{len(cell_result.get('enhancements', []))} enhancements"
    )

    # Phase 3: Synthesize as Zantara
    if stream:
        return None  # Use cell_giant_pipeline_stream for streaming

    final_response = await synthesize_as_zantara(
        query=query,
        giant_reasoning=giant_result,
        cell_calibration=cell_result
    )

    logger.info(f"Cell-Giant pipeline complete: {len(final_response)} chars")
    return final_response


async def cell_giant_pipeline_stream(
    query: str,
    user_context: str = "",
    user_facts: list[str] | None = None,
    user_id: str | None = None
):
    """
    Streaming version of the Cell-Giant pipeline.

    Yields events throughout the process to keep the connection alive:
        - {"type": "phase", "name": "giant", "status": "started"}
        - {"type": "keepalive"} - Sent every 10s during long operations
        - {"type": "phase", "name": "giant", "status": "complete"}
        - {"type": "phase", "name": "cell", "status": "started"}
        - {"type": "phase", "name": "cell", "status": "complete"}
        - {"type": "metadata", ...} - Pipeline metadata
        - {"type": "phase", "name": "zantara", "status": "started"}
        - {"type": "chunk", "content": "..."} - Response tokens
        - {"type": "done"}
    """
    import asyncio
    from .giant_reasoner import giant_reason, GiantConfig
    from .cell_conscience import cell_calibrate

    logger.info(f"🚀 [Cell-Giant Pipeline] Started for query: {query[:50]}...")

    # Signal Giant phase started
    yield {"type": "phase", "name": "giant", "status": "started"}

    # Phase 1: Giant reasons with keepalive events
    # We use asyncio.create_task to run Giant reasoning while sending keepalives
    giant_config = GiantConfig(use_pro_model=True)

    async def giant_with_logging():
        logger.info("🧠 [Giant] Starting deep reasoning...")
        result = await giant_reason(
            query=query,
            user_context=user_context,
            config=giant_config
        )
        logger.info(
            f"🧠 [Giant] Complete: quality={result.get('quality_score', 0):.2f}, "
            f"domain={result.get('detected_domain', 'unknown')}, "
            f"chars={len(result.get('reasoning', ''))}"
        )
        return result

    # Run Giant reasoning with periodic keepalives
    giant_task = asyncio.create_task(giant_with_logging())
    keepalive_count = 0

    while not giant_task.done():
        try:
            # Wait up to 10 seconds for Giant to complete
            await asyncio.wait_for(asyncio.shield(giant_task), timeout=10.0)
        except asyncio.TimeoutError:
            # Giant still running, send keepalive
            keepalive_count += 1
            logger.debug(f"🔄 [Giant] Keepalive #{keepalive_count} - still reasoning...")
            yield {"type": "keepalive", "phase": "giant", "elapsed": keepalive_count * 10}

    giant_result = await giant_task

    # Signal Giant phase complete
    yield {"type": "phase", "name": "giant", "status": "complete"}
    yield {"type": "phase", "name": "cell", "status": "started"}

    # Phase 2: Cell calibrates (usually fast, but send keepalive for safety)
    logger.info("🔬 [Cell] Starting calibration...")
    cell_result = await cell_calibrate(
        query=query,
        giant_reasoning=giant_result,
        user_id=user_id,
        user_facts=user_facts
    )
    logger.info(
        f"🔬 [Cell] Complete: {len(cell_result.get('corrections', []))} corrections, "
        f"{len(cell_result.get('enhancements', []))} enhancements, "
        f"{len(cell_result.get('calibrations', {}))} calibrations"
    )

    # Signal Cell phase complete
    yield {"type": "phase", "name": "cell", "status": "complete"}

    # Yield metadata
    yield {
        "type": "metadata",
        "giant_quality": giant_result.get("quality_score", 0),
        "detected_domain": giant_result.get("detected_domain", "general"),
        "corrections_count": len(cell_result.get("corrections", [])),
        "enhancements_count": len(cell_result.get("enhancements", [])),
        "calibrations_count": len(cell_result.get("calibrations", {}))
    }

    # Signal Zantara phase started
    yield {"type": "phase", "name": "zantara", "status": "started"}

    # Phase 3: Stream the synthesis
    logger.info("✨ [Zantara] Starting synthesis stream...")
    chunk_count = 0
    async for chunk in synthesize_as_zantara_stream(
        query=query,
        giant_reasoning=giant_result,
        cell_calibration=cell_result
    ):
        chunk_count += 1
        yield {"type": "chunk", "content": chunk}

    logger.info(f"✨ [Zantara] Synthesis complete: {chunk_count} chunks")

    # Yield completion marker (endpoint will add execution_time and tokens)
    yield {"type": "done"}


def _format_corrections(corrections: list[dict[str, Any]]) -> str:
    """Format corrections with severity indicators."""
    if not corrections:
        return "Nessuna correzione necessaria - il ragionamento e accurato."

    lines: list[str] = []
    severity_icons = {"critical": "🚨 CRITICO", "high": "⚠️ IMPORTANTE", "medium": "📝 NOTA"}

    # Sort by severity: critical first
    severity_order = {"critical": 0, "high": 1, "medium": 2}
    sorted_corrections = sorted(corrections, key=lambda x: severity_order.get(x.get("severity", "medium"), 2))

    for c in sorted_corrections:
        icon = severity_icons.get(c.get("severity", "medium"), "📝")
        lines.append(f"{icon}: {c['correction']}")
        if c.get("source"):
            lines.append(f"   📖 Fonte: {c['source']}")

    return "\n".join(lines)


def _format_calibrations(calibrations: dict[str, Any]) -> str:
    """Format Bali Zero service calibrations."""
    if not calibrations:
        return "Contattaci per preventivo specifico su questo servizio."

    lines: list[str] = []

    # Group by category if available
    by_category: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for service_key, data in calibrations.items():
        if isinstance(data, dict):
            category = data.get("category", "general")
            if category not in by_category:
                by_category[category] = []
            by_category[category].append((service_key, data))

    for category, services in by_category.items():
        if len(by_category) > 1:
            lines.append(f"\n**{category.upper()}:**")

        for service_key, data in services:
            service_name = service_key.replace("_", " ").title()
            lines.append(f"📦 **{service_name}**:")
            lines.append(f"   💰 Prezzo: {data.get('price', 'Su richiesta')}")
            lines.append(f"   ⏱️ Timeline: {data.get('timeline', 'Variabile')}")
            lines.append(f"   ✅ Include: {data.get('includes', 'Servizio completo')}")
            lines.append(f"   👤 Referente: {data.get('consultant', 'Team Bali Zero')}")

    return "\n".join(lines)


def _format_enhancements(enhancements: list[str]) -> str:
    """Format practical insights from experience."""
    if not enhancements:
        return "Nessun insight aggiuntivo per questo topic."

    # Limit and format
    limited = enhancements[:7]  # Max 7 insights
    return "\n".join([f"💡 {e}" for e in limited])


def _format_user_memory(memory: list[str]) -> str:
    """Format user memory facts."""
    if not memory:
        return "Nuovo utente, nessun contesto precedente."
    return "\n".join([f"👤 {m}" for m in memory[:5]])


def _format_legal_refs(legal_refs: list[str]) -> str:
    """Format legal references extracted from Giant reasoning."""
    if not legal_refs:
        return "Nessun riferimento legale specifico estratto."
    return ", ".join(legal_refs[:10])


def _clean_response(text: str) -> str:
    """Clean response by removing any leaked internal terminology."""
    # Patterns to remove
    internal_patterns = [
        r"(?i)ragionamento\s+base",
        r"(?i)calibrazion[ei]",
        r"(?i)giant\s+reason",
        r"(?i)cell\s+conscience",
        r"(?i)quality\s+score[:\s]*\d+",
        r"(?i)severity[:\s]*(?:critical|high|medium)",
        r"(?i)\[interno\]",
        r"(?i)\[internal\]",
    ]

    result = text
    for pattern in internal_patterns:
        result = re.sub(pattern, "", result)

    # Clean up double spaces/newlines
    result = re.sub(r"\n{3,}", "\n\n", result)
    result = re.sub(r"  +", " ", result)

    return result.strip()


def _expand_response(text: str, min_words: int, query: str, corrections: list[dict[str, Any]], cell_calibration: dict[str, Any]) -> str:
    """Expand a too-short response to meet minimum word count."""
    current_words = len(text.split())
    if current_words >= min_words:
        return text
    
    # Add key information if missing
    additions: list[str] = []
    
    # Add critical corrections if not mentioned
    critical = [c for c in corrections if c.get("severity") == "critical"]
    for corr in critical[:2]:  # Max 2 additions
        if corr.get("correction", "").lower() not in text.lower():
            additions.append(f"\n\n⚠️ IMPORTANTE: {corr['correction']}")
    
    # Add pricing if available and not mentioned
    calibrations = cell_calibration.get("calibrations", {})
    if calibrations and "prezzo" not in text.lower() and "price" not in text.lower():
        first_service_list = list(calibrations.values())
        if first_service_list and isinstance(first_service_list[0], dict):
            first_service = first_service_list[0]
            additions.append(f"\n\n💰 Servizio Bali Zero: {first_service.get('price', 'Su richiesta')}")
    
    expanded = text + "".join(additions)
    
    # If still too short, add generic call to action
    if len(expanded.split()) < min_words:
        expanded += f"\n\nPer maggiori informazioni o assistenza personalizzata su '{query}', contatta il team Bali Zero."
    
    return expanded


def _truncate_response(text: str, max_words: int) -> str:
    """Truncate response to maximum word count, preserving sentences."""
    words = text.split()
    if len(words) <= max_words:
        return text
    
    # Try to cut at sentence boundary
    truncated_words = words[:max_words]
    truncated_text = " ".join(truncated_words)
    
    # Find last sentence end
    last_period = truncated_text.rfind(".")
    last_exclamation = truncated_text.rfind("!")
    last_question = truncated_text.rfind("?")
    
    last_sentence_end = max(last_period, last_exclamation, last_question)
    
    # Only use sentence boundary if we found one and it's reasonable
    if last_sentence_end >= 0 and last_sentence_end > max_words * 0.7:
        return truncated_text[:last_sentence_end + 1] + ".."
    else:
        # Fallback: just truncate at word boundary
        return " ".join(truncated_words) + "..."


def _fallback_synthesis(giant_reasoning: dict[str, Any], cell_calibration: dict[str, Any]) -> str:
    """
    Fallback synthesis when LLM is unavailable.
    Creates a structured response from raw data.
    """
    parts: list[str] = []

    # 1. Key points from reasoning
    key_points = giant_reasoning.get("key_points", [])
    if key_points:
        parts.append("## Punti Chiave\n")
        for point in key_points[:5]:
            parts.append(f"- {point}")

    # 2. Steps if available
    steps = giant_reasoning.get("steps", [])
    if steps:
        parts.append("\n## Processo\n")
        for step in steps[:6]:
            timeline = f" ({step['timeline']})" if step.get('timeline') else ""
            parts.append(f"{step['step']}. **{step['name']}**{timeline}")
            if step.get('description'):
                parts.append(f"   {step['description']}")

    # 3. Critical corrections (MUST include)
    corrections = cell_calibration.get("corrections", [])
    critical = [c for c in corrections if c.get("severity") == "critical"]
    high = [c for c in corrections if c.get("severity") == "high"]

    if critical:
        parts.append("\n## ⚠️ Attenzione Critica\n")
        for c in critical:
            parts.append(f"🚨 {c['correction']}")
            if c.get('source'):
                parts.append(f"   Fonte: {c['source']}")

    if high:
        parts.append("\n## ⚠️ Importante\n")
        for c in high[:3]:
            parts.append(f"- {c['correction']}")

    # 4. Warnings from reasoning
    warnings = giant_reasoning.get("warnings", [])
    if warnings and not critical:  # Don't duplicate if we have critical
        parts.append("\n## Rischi da Considerare\n")
        for w in warnings[:3]:
            parts.append(f"- {w}")

    # 5. Pricing from calibrations
    calibrations = cell_calibration.get("calibrations", {})
    if calibrations:
        parts.append("\n## Servizi Bali Zero\n")
        for service_key, data in list(calibrations.items())[:2]:
            if isinstance(data, dict):
                service_name = service_key.replace("_", " ").title()
                parts.append(f"**{service_name}**: {data.get('price', 'Su richiesta')} - {data.get('timeline', 'Variabile')}")

    # 6. Practical insights
    enhancements = cell_calibration.get("enhancements", [])
    if enhancements:
        parts.append("\n## Tips Pratici\n")
        for e in enhancements[:3]:
            parts.append(f"💡 {e}")

    # Default if nothing available
    if not parts:
        return """
Mi dispiace, il servizio di consulenza e temporaneamente limitato.

Per assistenza immediata, contatta il team Bali Zero:
- 📧 Email: info@balizero.com
- 📱 WhatsApp: +62 xxx xxx xxx

Il nostro team e a disposizione per rispondere alle tue domande su visa, company setup, e servizi legali in Indonesia.
""".strip()

    return "\n".join(parts)