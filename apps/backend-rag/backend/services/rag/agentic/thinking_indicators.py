"""
Thinking Indicators Service for LLM Gateway.

Provides real-time feedback to users during LLM processing.
Follows Best Practice 2026 for transparent AI interactions.
"""

import logging
import time
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ThinkingPhase(Enum):
    """Phases of LLM thinking process."""

    ANALYZING = "analyzing"
    SEARCHING = "searching"
    REASONING = "reasoning"
    TOOL_CALLING = "tool_calling"
    GENERATING = "generating"


# Multi-language thinking messages
THINKING_MESSAGES = {
    "it": {
        ThinkingPhase.ANALYZING: "🧠 Analizzo la tua richiesta...",
        ThinkingPhase.SEARCHING: "🔍 Cerco nei documenti...",
        ThinkingPhase.REASONING: "💭 Sto ragionando...",
        ThinkingPhase.TOOL_CALLING: "🔧 Uso {tool_name}...",
        ThinkingPhase.GENERATING: "✍️ Scrivo la risposta...",
    },
    "en": {
        ThinkingPhase.ANALYZING: "🧠 Analyzing your request...",
        ThinkingPhase.SEARCHING: "🔍 Searching documents...",
        ThinkingPhase.REASONING: "💭 Thinking...",
        ThinkingPhase.TOOL_CALLING: "🔧 Using {tool_name}...",
        ThinkingPhase.GENERATING: "✍️ Writing response...",
    },
    "id": {
        ThinkingPhase.ANALYZING: "🧠 Menganalisis permintaan...",
        ThinkingPhase.SEARCHING: "🔍 Mencari dokumen...",
        ThinkingPhase.REASONING: "💭 Berpikir...",
        ThinkingPhase.TOOL_CALLING: "🔧 Menggunakan {tool_name}...",
        ThinkingPhase.GENERATING: "✍️ Menulis jawaban...",
    },
}


class ThinkingIndicatorService:
    """
    Service for generating thinking indicators during LLM processing.

    Best Practice 2026: "Show, Don't Tell" - Visual cues are fast.
    "Let me check that for you…" performs better than "Retrieving requested data…"
    """

    def __init__(self, language: str = "it") -> None:
        """
        Initialize thinking indicator service.

        Args:
            language: Language code (it, en, id)
        """
        self.language = language
        self.messages = THINKING_MESSAGES.get(language, THINKING_MESSAGES["en"])
        self._current_phase = None
        self._phase_start_time = None

    def get_message(self, phase: ThinkingPhase, **kwargs) -> str:
        """
        Get thinking message for a phase.

        Args:
            phase: Current thinking phase
            **kwargs: Variables for message formatting

        Returns:
            Formatted thinking message
        """
        template = self.messages.get(phase, "Processing...")
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing template variable {e} for phase {phase}")
            return template

    def create_thinking_event(
        self, phase: ThinkingPhase, message_override: str | None = None, **kwargs,
    ) -> dict[str, Any]:
        """
        Create a thinking event for streaming.

        Args:
            phase: Current thinking phase
            message_override: Optional custom message to show
            **kwargs: Variables for message formatting

        Returns:
            Event dictionary for streaming
        """
        # Update phase tracking
        self._current_phase = phase
        self._phase_start_time = time.time()

        message = message_override if message_override else self.get_message(phase, **kwargs)

        return {"type": "thinking", "data": message, "phase": phase.value, "timestamp": time.time()}

    def create_done_event(self) -> dict[str, Any]:
        """
        Create a done event to clear thinking state.

        Returns:
            Done event dictionary
        """
        return {"type": "thinking_done", "data": "", "timestamp": time.time()}

    def get_phase_duration(self) -> float:
        """
        Get duration of current phase.

        Returns:
            Duration in seconds, or 0 if no phase active
        """
        if self._phase_start_time:
            return time.time() - self._phase_start_time
        return 0.0

    def should_show_thinking(self, phase: ThinkingPhase) -> bool:
        """
        Determine if thinking indicator should be shown for phase.

        Best Practice 2026: Don't overwhelm users with too many indicators.

        Args:
            phase: Current thinking phase

        Returns:
            True if indicator should be shown
        """
        # Always show for these phases
        always_show = {
            ThinkingPhase.SEARCHING,
            ThinkingPhase.TOOL_CALLING,
            ThinkingPhase.GENERATING,
        }

        # Show analyzing only for complex queries
        if phase == ThinkingPhase.ANALYZING:
            return self.get_phase_duration() > 1.0  # Only if taking > 1 second

        # Show reasoning only if taking time
        if phase == ThinkingPhase.REASONING:
            return self.get_phase_duration() > 0.5

        return phase in always_show


# Tool name mappings for user-friendly messages
TOOL_DISPLAY_NAMES = {
    "search_documents": "ricerca documenti",
    "search_knowledge_graph": "ricerca nella knowledge base",
    "get_user_memory": "memoria utente",
    "get_collective_memory": "memoria collettiva",
    "calculator": "calcolatrice",
    "get_pricing": "prezzi",
    "get_team_insights": "insights team",
    "get_burnout_signals": "segnali burnout",
    "get_compliance_info": "informazioni compliance",
    "generate_image": "generazione immagine",
    "transcribe_audio": "trascrizione audio",
    "analyze_sentiment": "analisi sentiment",
    "extract_entities": "estrazione entità",
    "get_current_time": "orario attuale",
    "get_weather": "meteo",
    "get_news": "notizie",
    "get_stock_price": "prezzo azioni",
    "get_currency_rate": "tasso di cambio",
    "translate_text": "traduzione",
    "summarize_text": "riassunto",
    "check_spelling": "controllo ortografia",
    "get_definition": "definizione",
    "get_synonyms": "sinonimi",
    "get_antonyms": "antonimi",
    "check_grammar": "controllo grammatica",
    "format_text": "formattazione testo",
    "convert_units": "conversione unità",
    "calculate_distance": "calcolo distanza",
    "calculate_area": "calcolo area",
    "calculate_volume": "calcolo volume",
    "calculate_weight": "calcolo peso",
    "calculate_temperature": "conversione temperatura",
    "calculate_speed": "calcolo velocità",
    "calculate_time": "calcolo tempo",
    "calculate_date": "calcolo data",
    "calculate_age": "calcolo età",
    "calculate_bmi": "calcolo BMI",
    "calculate_loan": "calcolo prestito",
    "calculate_interest": "calcolo interesse",
    "calculate_tax": "calcolo tasse",
    "calculate_tip": "calcolo mancia",
    "calculate_discount": "calcolo sconto",
    "calculate_markup": "calcolo markup",
    "calculate_margin": "calcolo margine",
    "calculate_profit": "calcolo profitto",
    "calculate_loss": "calcolo perdita",
    "calculate_roi": "calcolo ROI",
    "calculate_roe": "calcolo ROE",
    "calculate_debt": "calcolo debito",
    "calculate_equity": "calcolo patrimonio",
    "calculate_assets": "calcolo attività",
    "calculate_liabilities": "calcolo passività",
    "calculate_cash_flow": "calcolo flusso cassa",
    "calculate_break_even": "calcolo punto di pareggio",
    "calculate_depreciation": "calcolo ammortamento",
    "calculate_amortization": "calcolo ammortamento",
    "calculate_present_value": "calcolo valore attuale",
    "calculate_future_value": "calcolo valore futuro",
    "calculate_net_present_value": "calcolo VAN",
    "calculate_internal_rate_of_return": "calcolo TIR",
    "calculate_payback_period": "calcolo periodo recupero",
    "calculate_profitability_index": "calcolo indice redditività",
    "calculate_cost_benefit": "calcolo analisi costi-benefici",
    "calculate_risk": "calcolo rischio",
    "calculate_volatility": "calcolo volatilità",
    "calculate_beta": "calcolo beta",
    "calculate_alpha": "calcolo alpha",
    "calculate_sharpe_ratio": "calcolo Sharpe ratio",
    "calculate_sortino_ratio": "calcolo Sortino ratio",
    "calculate_tracking_error": "calcolo errore tracciamento",
    "calculate_information_coefficient": "calcolo coefficiente informazione",
    "calculate_active_share": "calcolo quota attiva",
    "calculate_upside_capture": "calcolo cattura upside",
    "calculate_downside_capture": "calcolo cattura downside",
    "calculate_sortino": "calcolo Sortino",
    "calculate_calmar": "calcolo Calmar",
    "calculate_sterling": "calcolo Sterling",
    "calculate_burke": "calcolo Burke",
    "calculate_kappa": "calcolo Kappa",
    "calculate_omega": "calcolo Omega",
    "calculate_gain_loss": "calcolo Gain-Loss",
    "calculate_upside_downside": "calcolo Upside-Downside",
    "calculate_var": "calcolo VaR",
    "calculate_cvar": "calcolo CVaR",
    "calculate_drawdown": "calcolo drawdown",
    "calculate_max_drawdown": "calcolo max drawdown",
    "calculate_recovery": "calcolo recupero",
    "calculate_duration": "calcolo durata",
    "calculate_convexity": "calcolo convessità",
    "calculate_yield": "calcolo rendimento",
    "calculate_spread": "calcolo spread",
    "calculate_basis": "calcolo basis",
    "calculate_forward": "calcolo forward",
    "calculate_future": "calcolo future",
    "calculate_alpha_beta": "calcolo alpha-beta",
    "calculate_tracking_difference": "calcolo differenza tracciamento",
    "calculate_convertible": "calcolo convertibile",
    "calculate_swap": "calcolo swap",
    "calculate_credit_default": "calcolo CDS",
    "calculate_total_return": "calcolo rendimento totale",
    "calculate_excess_return": "calcolo rendimento in eccesso",
    "calculate_information_ratio": "calcolo Information ratio",
    "calculate_treynor_ratio": "calcolo Treynor ratio",
    "calculate_jensen_alpha": "calcolo Jensen alpha",
    "calculate_appraisal_ratio": "calcolo Appraisal ratio",
}


def get_tool_display_name(tool_name: str, language: str = "en") -> str:
    """
    Get user-friendly display name for a tool.

    Args:
        tool_name: Internal tool name
        language: Language code (default "en"; falls back to humanised tool_name
                  when no localized label is registered)

    Returns:
        User-friendly tool name
    """
    if language == "it":
        return TOOL_DISPLAY_NAMES.get(tool_name, tool_name.replace("_", " "))

    # English mappings — the canonical display set. Anything not listed here
    # falls back to the underscore-cleaned tool name (good enough for any
    # English-speaking surface).
    english_names = {
        "search_documents": "document search",
        "search_knowledge_graph": "knowledge base search",
        "get_user_memory": "user memory",
        "get_collective_memory": "collective memory",
        "calculator": "calculator",
        "get_pricing": "pricing",
        "get_team_insights": "team insights",
        "get_burnout_signals": "burnout signals",
        "get_compliance_info": "compliance info",
        "generate_image": "image generation",
        "transcribe_audio": "audio transcription",
        "analyze_sentiment": "sentiment analysis",
        "extract_entities": "entity extraction",
        "get_current_time": "current time",
        "get_weather": "weather",
        "get_news": "news",
        "translate_text": "translation",
        "summarize_text": "summary",
        "get_definition": "definition",
        "convert_units": "unit conversion",
    }
    return english_names.get(tool_name, tool_name.replace("_", " "))
