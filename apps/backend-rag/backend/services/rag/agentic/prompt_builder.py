"""
System Prompt Builder for Agentic RAG

This module handles construction of dynamic system prompts based on:
- User profile and identity
- Personal memory facts
- Collective knowledge
- Query characteristics (language, domain, format)
- Deep think mode activation

Key Features:
- Caching system with 5-minute TTL
- Cache key includes facts count for invalidation
- Dynamic language/format instructions
- Domain-specific formatting (visa, tax, company)
- Explanation level detection
"""

import logging
import re
import time
from typing import Any

from backend.app.core.config import settings
from backend.prompts.zantara_core import (
    CREATOR_PERSONA,
    TEAM_PERSONA,
    ZANTARA_MASTER_TEMPLATE,
)

logger = logging.getLogger(__name__)


class SystemPromptBuilder:
    """
    Builds dynamic system prompts with caching for performance.

    Cache key: user_id:deep_think_mode:facts_count:collective_count
    Cache TTL: 5 minutes
    """

    # Greeting patterns to detect if we already greeted
    GREETING_PATTERNS = [
        r"^ciao\s+\w+[!?]?",  # "Ciao Marco!"
        r"^hello\s+\w+[!?]?",  # "Hello John!"
        r"^hi\s+\w+[!?]?",  # "Hi there!"
        r"^halo\s+\w+[!?]?",  # "Halo Pak!"
        r"^привіт",  # Ukrainian
        r"^привет",  # Russian
        r"^bentornato",  # Italian "welcome back"
        r"^welcome\s+back",  # English
        r"^selamat\s+datang",  # Indonesian
    ]

    def __init__(self) -> None:
        """Initialize SystemPromptBuilder with caching.

        Sets up prompt caching infrastructure to avoid rebuilding expensive
        prompts on every query. Cache keys include user_id and memory facts
        count to ensure prompt freshness.

        Note:
            - Cache TTL: 5 minutes (balances freshness vs performance)
            - Cache invalidation: Triggered by changes in memory facts count
            - Memory usage: Bounded by TTL expiration (no size limit)
        """
        # System prompt cache for performance
        self._cache: dict[str, tuple[str, float]] = {}
        self._cache_ttl = 300  # 5 minutes TTL

    def has_already_greeted(self, conversation_history: list[dict] | None) -> bool:
        """
        Check if we have already greeted the user in this conversation.

        Scans the conversation history for any assistant message that starts
        with a greeting pattern (Ciao, Hello, Hi, Halo, etc.).

        Args:
            conversation_history: List of message dicts with 'role' and 'content'

        Returns:
            True if a greeting was found in any assistant message
        """
        if not conversation_history:
            return False

        for msg in conversation_history:
            if not isinstance(msg, dict):
                continue
            if msg.get("role") == "assistant":
                content = msg.get("content", "").strip().lower()
                for pattern in self.GREETING_PATTERNS:
                    if re.match(pattern, content):
                        return True
        return False

    def build_system_prompt(
        self,
        user_id: str,
        context: dict[str, Any],
        query: str = "",
        deep_think_mode: bool = False,
        additional_context: str = "",
        conversation_history: list[dict] | None = None,
    ) -> str:
        """Construct dynamic, personalized system prompt with intelligent caching.

        Builds a comprehensive system instruction by composing multiple prompt sections:
        1. Base persona: Core AI identity and communication style (Jaksel persona)
        2. Deep think mode: Activated for complex strategic queries
        3. User identity: Profile-based personalization (name, role, relationship)
        4. Collective knowledge: Cross-user learnings and best practices
        5. Personal memory: User-specific facts and preferences
        6. Communication rules: Language, tone, formatting based on query analysis
        7. Tool instructions: Available tools and usage guidelines

        Prompt Engineering Decisions:
        - Dynamic language detection: Responds in user's query language
        - Domain-specific formatting: Tailored output for visa/tax/company queries
        - Explanation level adaptation: Simple/expert/standard based on query complexity
        - Emotional attunement: Empathetic responses for emotional queries
        - Procedural formatting: Step-by-step lists for "how-to" questions
        - Memory integration: "I know you" vs "Tell me about yourself" tone

        Caching Strategy:
        - Cache key: f"{user_id}:{deep_think_mode}:{len(facts)}:{len(collective_facts)}"
        - TTL: 5 minutes (balances memory freshness vs rebuild cost)
        - Invalidation: Automatic on new memory facts or cache expiration
        - Hit rate: ~70-80% for typical conversation patterns

        Args:
            user_id: User identifier (email/UUID) for personalization
            context: User context dict containing:
                - profile (dict): User profile (name, role, department, notes)
                - facts (list[str]): Personal memory facts
                - collective_facts (list[str]): Shared knowledge across users
                - entities (dict): Extracted entities (name, city, budget)
            query: Current query for language/format/domain detection
            deep_think_mode: If True, activates strategic reasoning instructions
            additional_context: Valid string with extra context to append (e.g. extracted entities)

        Returns:
            Complete system prompt string (typically 2000-5000 chars)

        Note:
            - Empty query: Generic prompt without communication rules
            - Missing profile: Falls back to entity-based identity or generic greeting
            - No facts: Prompt still includes base persona and tool instructions
            - Cache miss: Full rebuild (~5-10ms), Cache hit: <1ms

        Example:
            >>> builder = SystemPromptBuilder()
            >>> context = {
            ...     "profile": {"name": "Marco", "role": "Entrepreneur"},
            ...     "facts": ["Interested in PT PMA", "Budget: $50k USD"],
            ...     "collective_facts": ["E33G requires $2000/month income proof"]
            ... }
            >>> prompt = builder.build_system_prompt(
            ...     user_id="marco@example.com",
            ...     context=context,
            ...     query="Come posso aprire una PT PMA?",
            ...     deep_think_mode=False
            ... )
            >>> logger.info(len(prompt))  # ~3500 chars
            >>> "Marco" in prompt  # True (personalized)
        """
        profile = context.get("profile")
        facts = context.get("facts", [])
        collective_facts = context.get("collective_facts", [])
        # Custom entities
        entities = context.get("entities", {})
        # Episodic Memory (Timeline)
        timeline_summary = context.get("timeline_summary", "")

        # Determine User Identity & Persona
        user_email = user_id
        if profile and profile.get("email"):
            user_email = profile.get("email")

        # Identity Checks
        is_creator = False
        is_team = False

        if user_email:
            email_lower = user_email.lower()
            if "antonello" in email_lower or "siano" in email_lower:
                is_creator = True
            elif (
                "@balizero.com" in email_lower
                or profile
                and "admin" in str(profile.get("role", "")).lower()
            ):
                is_team = True

        # Detect language EARLY for cache key
        query_lower = query.lower() if query else ""
        indo_markers = [
            "apa",
            "bagaimana",
            "siapa",
            "dimana",
            "kapan",
            "mengapa",
            "yang",
            "dengan",
            "untuk",
            "dari",
            "saya",
            "aku",
            "kamu",
            "anda",
            "bisa",
            "mau",
            "ingin",
            "tolong",
            "halo",
            "gimana",
            "gue",
            "gw",
            "lu",
            "dong",
            "nih",
            "banget",
        ]
        is_indonesian = any(marker in query_lower for marker in indo_markers)

        # Detect specific language (with descriptive names for prompts)
        detected_lang = None
        if not is_indonesian and query and len(query) > 3:
            # Japanese detection: Check for Hiragana/Katakana (unique to Japanese)
            has_hiragana = any("\u3040" <= c <= "\u309f" for c in query)
            has_katakana = any("\u30a0" <= c <= "\u30ff" for c in query)
            has_kanji = any("\u4e00" <= c <= "\u9fff" for c in query)

            if has_hiragana or has_katakana:
                # Hiragana/Katakana = definitely Japanese
                detected_lang = "JAPANESE (日本語)"
            elif has_kanji and not has_hiragana and not has_katakana:
                # Only Kanji, no kana = likely Chinese
                detected_lang = "CHINESE (中文)"
            elif any("\u0600" <= c <= "\u06ff" for c in query):
                detected_lang = "ARABIC (العربية)"
            elif any("\u0400" <= c <= "\u04ff" for c in query):
                detected_lang = "RUSSIAN/UKRAINIAN"
            elif any(
                w in query_lower
                for w in [
                    "ciao",
                    "come",
                    "cosa",
                    "voglio",
                    "grazie",
                    "posso",
                    "perché",
                    "buongiorno",
                    "buonasera",
                ]
            ):
                detected_lang = "ITALIAN (Italiano)"
            elif any(
                w in query_lower
                for w in [
                    "bonjour",
                    "comment",
                    "pourquoi",
                    "merci",
                    "oui",
                    "non",
                    "je",
                    "nous",
                    "vous",
                    "est-ce",
                ]
            ):
                detected_lang = "FRENCH (Français)"
            elif any(
                w in query_lower
                for w in [
                    "hola",
                    "cómo",
                    "gracias",
                    "qué",
                    "por qué",
                    "buenos días",
                    "buenas tardes",
                    "quiero",
                    "puedo",
                ]
            ):
                detected_lang = "SPANISH (Español)"
            elif any(
                w in query_lower
                for w in [
                    "guten tag",
                    "guten morgen",
                    "danke",
                    "bitte",
                    "wie",
                    "warum",
                    "ich möchte",
                    "können",
                    "hallo",
                ]
            ):
                detected_lang = "GERMAN (Deutsch)"
            elif any(
                w in query_lower
                for w in [
                    "olá",
                    "bom dia",
                    "boa tarde",
                    "obrigado",
                    "obrigada",
                    "como",
                    "porque",
                    "quero",
                    "posso",
                    "você",
                ]
            ):
                detected_lang = "PORTUGUESE (Português)"
            else:
                detected_lang = "SAME AS USER'S QUERY"

        # OPTIMIZATION: Check cache before building expensive prompt
        # Include detected language in cache key (use short form for key)
        lang_key = detected_lang.split()[0] if detected_lang else "ID"
        # Use hashes for stable cache keys that reflect content changes
        import hashlib

        def _stable_hash(obj: Any) -> str:
            """Generate a stable short hash for any object."""
            return hashlib.md5(str(obj).encode()).hexdigest()[:8]

        facts_hash = _stable_hash(facts)
        coll_facts_hash = _stable_hash(collective_facts)
        timeline_hash = _stable_hash(timeline_summary)
        ctx_hash = _stable_hash(additional_context)

        cache_key = f"{user_id}:{deep_think_mode}:{facts_hash}:{coll_facts_hash}:{timeline_hash}:{is_creator}:{is_team}:{ctx_hash}:{lang_key}"

        if cache_key in self._cache:
            cached_prompt, cached_time = self._cache[cache_key]
            # Check if cache is still valid (within TTL)
            if time.time() - cached_time < self._cache_ttl:
                logger.debug(f"Using cached system prompt for {user_id} (cache hit)")
                return cached_prompt
            # Cache expired, remove it
            del self._cache[cache_key]
            logger.debug(f"Cache expired for {user_id}, rebuilding prompt")

        # Build Memory / Identity Block
        memory_parts = []

        # 1. Identity Awareness
        if profile:
            user_name = profile.get("name", "Partner")
            user_role = profile.get("role", "Team Member")
            dept = profile.get("department", "General")
            notes = profile.get("notes", "")
            memory_parts.append(
                f"User Name: {user_name}\nEmail: {user_email}\nRole: {user_role}\nDepartment: {dept}\nNotes: {notes}",
            )
        elif entities:
            user_name = entities.get("user_name", "Partner")
            # Fallback for email if not in profile but known from user_id (if it looks like an email)
            email_display = user_email if "@" in user_email else "Unknown"
            user_city = entities.get("user_city", "Unknown City")
            memory_parts.append(
                f"User Name: {user_name}\nEmail: {email_display}\nCity: {user_city}",
            )

        # 2. Personal Facts
        if facts:
            memory_parts.append("FACTS:\n" + "\n".join([f"- {f}" for f in facts]))

        # 3. Recent History
        if timeline_summary:
            memory_parts.append(f"RECENT HISTORY:\n{timeline_summary}")

        # 4. Collective Knowledge
        if collective_facts:
            memory_parts.append(
                "COLLECTIVE KNOWLEDGE:\n" + "\n".join([f"- {f}" for f in collective_facts]),
            )

        user_memory_text = "\n\n".join(memory_parts) if memory_parts else "No specific memory yet."

        # Build Final Prompt using Master Template
        rag_results = context.get("rag_results", "{rag_results}")

        # DeepThink Mode Instruction (if activated)
        deep_think_instr = ""
        if deep_think_mode:
            deep_think_instr = "\n\n### DEEP THINK MODE ACTIVATED\nTake your time to analyze all aspects (Legal, Tax, Business). Consider pros and cons."

        # NOTE: Language detection already done BEFORE cache check (lines 342-366)
        # Variable `detected_lang` is already set with descriptive names

        # Build prompt with language handling
        if detected_lang:
            # For non-Indonesian queries, use a STRIPPED version of the template
            # Remove Jaksel references that make Gemini respond in Indonesian
            stripped_template = ZANTARA_MASTER_TEMPLATE.format(
                rag_results=rag_results,
                user_memory=user_memory_text,
                query=query if query else "General inquiry",
            )
            # Remove Jaksel-specific instructions
            jaksel_phrases = [
                "Jaksel",
                "Jakarta Selatan",
                '"gue"',
                '"banget"',
                '"nih"',
                '"dong"',
                '"bro"',
                "Basically gini bro",
                "Makes sense kan?",
                "Full Jaksel",
                "Business Jaksel",
                "Jaksel flair",
                "Jaksel flavor",
                "Jaksel persona",
                '"gimana"',
                '"kayak"',
                '"sih"',
                '"deh"',
                '"lho"',
                '"kok"',
            ]
            for phrase in jaksel_phrases:
                stripped_template = stripped_template.replace(phrase, "")

            # Add strong language instruction
            language_header = f"""
================================================================================
YOU ARE RESPONDING TO A {detected_lang} SPEAKER.
YOUR ENTIRE RESPONSE MUST BE IN {detected_lang}.
DO NOT USE ANY INDONESIAN WORDS OR SLANG.
================================================================================

"""
            final_prompt = language_header + stripped_template
        else:
            final_prompt = ZANTARA_MASTER_TEMPLATE.format(
                rag_results=rag_results,
                user_memory=user_memory_text,
                query=query if query else "General inquiry",
            )

        if deep_think_instr:
            final_prompt += deep_think_instr

        if additional_context:
            final_prompt += "\n" + additional_context

        # Anti-greeting-repetition check
        if conversation_history and self.has_already_greeted(conversation_history):
            no_greeting_warning = """

⚠️ **CRITICAL REMINDER**: You have ALREADY greeted this user earlier in this conversation.
**DO NOT** say "Ciao [Name]!" or any greeting again.
**START DIRECTLY** with the answer to their question.
"""
            final_prompt += no_greeting_warning
            logger.debug("🚫 [PromptBuilder] Injected no-greeting warning (already greeted)")

        # Inject Creator/Team Persona if applicable
        if is_creator:
            final_prompt = CREATOR_PERSONA + "\n\n" + final_prompt
            logger.info(f"🧬 [PromptBuilder] Activated CREATOR Mode for {user_id}")
        elif is_team:
            final_prompt = TEAM_PERSONA + "\n\n" + final_prompt
            logger.info(f"🏢 [PromptBuilder] Activated TEAM Mode for {user_id}")

        # Cache for next time
        self._cache[cache_key] = (final_prompt, time.time())

        return final_prompt

    def check_greetings(self, query: str, context: dict[str, Any] = None) -> str | None:
        """
        Check if query is a simple greeting that doesn't need RAG retrieval.
        Using optional user context to personalize the greeting.
        Respects user's preferred language from their facts.
        """
        query_lower = query.lower().strip()

        # Extract user name and returning status from context
        profile = (context or {}).get("profile") or {}
        user_name = profile.get("name") or profile.get("full_name")
        facts = (context or {}).get("facts") or []
        is_returning = bool(facts) or bool((context or {}).get("history", []))

        # Detect user's language from nationality/ethnicity in facts
        user_lang = None
        facts_text = " ".join(facts).lower()
        # Indonesian/Balinese/Javanese → Indonesian
        if any(
            w in facts_text
            for w in ["indonesian", "indonesiano", "balinese", "javanese", "sundanese"]
        ):
            user_lang = "id"
        # Italian
        elif any(w in facts_text for w in ["italian", "italiano"]):
            user_lang = "it"
        # Ukrainian
        elif any(w in facts_text for w in ["ukrainian", "ucraino", "ucraina"]):
            user_lang = "uk"
        # Russian
        elif any(w in facts_text for w in ["russian", "russo"]):
            user_lang = "ru"

        # Simple greeting patterns (single word or very short)
        greeting_patterns = [
            r"^(ciao|hello|hi|hey|salve|buongiorno|buonasera|buon pomeriggio|good morning|good afternoon|good evening)$",
            r"^(ciao|hello|hi|hey|salve)\s*!*$",
            r"^(ciao|hello|hi|hey|salve)\s+(zan|zantara|there)$",
            # Indonesian greetings
            r"^(halo|hai|hei|selamat pagi|selamat siang|selamat sore|selamat malam)\s*!*$",
            r"^(halo|hai|hei)\s+(zan|zantara)!*$",
            r"^(apa kabar|gimana kabar|kabar baik)\s*\??!*$",
            # Ukrainian
            r"^(привіт|вітаю|добрий день|доброго ранку|доброго вечора)\s*!*$",
            # Russian
            r"^(привет|здравствуй|здравствуйте|добрый день|доброе утро|добрый вечер)\s*!*$",
            r"^(bonjour|salut|bonsoir)\s*!*$",
            r"^(hola|buenos días|buenas tardes|buenas noches)\s*!*$",
            r"^(hallo|guten tag|guten morgen|guten abend)\s*!*$",
        ]

        for pattern in greeting_patterns:
            if re.match(pattern, query_lower):
                # Determine response language: user preference > query language > default
                if user_lang is None:
                    # Detect from query
                    if any(
                        word in query_lower for word in ["ciao", "salve", "buongiorno", "buonasera"]
                    ):
                        user_lang = "it"
                    elif any(word in query_lower for word in ["привіт", "вітаю", "добрий"]):
                        user_lang = "uk"
                    elif any(
                        word in query_lower for word in ["привет", "здравствуй", "добрый", "доброе"]
                    ):
                        user_lang = "ru"
                    elif any(
                        word in query_lower
                        for word in ["halo", "hai", "hei", "selamat", "apa kabar", "kabar"]
                    ):
                        user_lang = "id"
                    else:
                        user_lang = "en"

                # Return greeting in user's language
                if user_lang == "id":
                    if is_returning and user_name:
                        return f"Halo {user_name}! Selamat datang kembali — ada yang bisa aku bantu hari ini?"
                    if is_returning:
                        return "Halo! Selamat datang kembali — ada yang bisa aku bantu?"
                    return "Halo! Ada yang bisa aku bantu hari ini?"
                if user_lang == "it":
                    if is_returning and user_name:
                        return f"Ciao {user_name}! Bentornato — come posso aiutarti oggi?"
                    if is_returning:
                        return "Ciao! Bentornato — come posso aiutarti oggi?"
                    return "Ciao! Come posso aiutarti oggi?"
                if user_lang == "uk":
                    if is_returning and user_name:
                        return f"Привіт, {user_name}! З поверненням — чим можу допомогти?"
                    if is_returning:
                        return "Привіт! З поверненням — чим можу допомогти?"
                    return "Привіт! Чим можу допомогти?"
                if user_lang == "ru":
                    if is_returning and user_name:
                        return f"Привет, {user_name}! С возвращением — чем могу помочь?"
                    if is_returning:
                        return "Привет! С возвращением — чем могу помочь?"
                    return "Привет! Чем могу помочь?"
                # Default English
                if is_returning and user_name:
                    return f"Hello {user_name}! Welcome back — how can I help you today?"
                if is_returning:
                    return "Hello! Welcome back — how can I help you today?"
                return "Hello! How can I help you today?"

        return None

    def check_casual_conversation(self, query: str, context: dict[str, Any] = None) -> bool:
        """
        Detect if query is a casual/lifestyle question that doesn't need RAG tools.
        Context can be used for personalization in future enhancements.
        """
        query_lower = query.lower().strip()

        # Business keywords that require RAG
        business_keywords = [
            "visa",
            "kitas",
            "kitap",
            "voa",
            "pt pma",
            "pt local",
            "pma",
            "kbli",
            "tax",
            "pajak",
            "pph",
            "ppn",
            "company",
            "business",
            "legal",
            "law",
            "regulation",
            "permit",
            "license",
            "contract",
            "notaris",
            "bank",
            "investment",
            "investor",
            "capital",
            "modal",
            "hukum",
            "peraturan",
            "undang",
            "izin",
            "akta",
            "npwp",
            "siup",
            "tdp",
            "nib",
            "oss",
            "immigration",
            "imigrasi",
            "sponsor",
            "rptka",
            "imta",
            "tenaga kerja",
            "how much",
            "quanto costa",
            "berapa",
            "pricing",
            "price",
            "harga",
            "deadline",
            "expire",
            "renewal",
            "extension",
            "perpanjang",
            "ceo",
            "founder",
            "team",
            "tim",
            "anggota",
            "member",
            "staff",
            "chi è",
            "who is",
            "siapa",
            "direttore",
            "director",
            "manager",
            settings.COMPANY_NAME.lower(),
            "zerosphere",
            "kintsugi",
        ]

        for keyword in business_keywords:
            if keyword in query_lower:
                return False

        # CRITICAL FIX (Dec 2025): Do NOT use length as a heuristic.
        # "Requisiti E33G?" is short (15 chars) but highly technical.
        # "Cos'è il visto C312?" is short but requires RAG.

        # 1. Check for specific Visa Code patterns (E33G, C312, etc.)
        # This catches codes that might not be in the keyword list
        if re.search(r"\b[eE]\d{2}[a-zA-Z]?\b", query_lower):
            return False  # It's a visa code, definitely business
        if re.search(r"\b[cC]\d{3}[a-zA-Z]?\b", query_lower):  # C312 etc
            return False

        # 2. If it's short, check if it explicitly matches CASUAL patterns.
        # If it doesn't match casual patterns, safe default is to ASSUME BUSINESS/RAG.
        # It is better to search and find nothing than to hallucinate.

        # Casual conversation patterns (Explicit Whitelist)
        casual_patterns = [
            # Food/restaurants
            r"(ristorante|restaurant|makan|mangiare|food|cibo|warung|cafe|bar|dinner|lunch|breakfast)",
            # Music/Life
            r"(music|musica|lagu|song|concert|spotify|playlist|hobby|sport|palestra|gym)",
            # Personal greetings/status
            r"(come stai|how are you|apa kabar|gimana kabar|cosa fai|what do you do|che fai)",
            r"(preferisci|prefer|suka|like|favorite|favorito|best|migliore|consiglia|recommend)",
            # Weather
            r"(weather|cuaca|meteo|tempo|beach|pantai|spiaggia|surf|sunset|sunrise)",
            # Emotional states (Indonesian Jaksel style)
            r"(bosen|bosan|capek|cape|lelah|seneng|senang|sedih|kesel|marah|happy|sad|tired)",
            r"(gabut|mager|males|santai|chill|relax|stress|pusing|galau|anxious)",
            # Emotional states (Italian)
            r"(stanco|annoiato|felice|triste|arrabbiato|rilassato|stressato|contento)",
            # Casual statements about day/mood
            r"(hari ini|today|oggi|lagi|feeling|mood|vibes)",
            # General Chatters
            # General Chatters (Removed context-dependent 'si', 'no', 'yes' to allow RAG/LLM reasoning)
            r"^(ok|bene|good|great|thanks|grazie|terima kasih|cool|wow|haha|wkwk|lol)$",
        ]

        return any(re.search(pattern, query_lower) for pattern in casual_patterns)

    def get_casual_response(self, query: str, context: dict[str, Any] = None) -> str | None:
        """
        Generate a direct casual response without RAG for simple queries like "come stai".
        Returns None if query is not casual (should use RAG instead).
        """
        if not self.check_casual_conversation(query, context):
            return None

        query_lower = query.lower().strip()
        user_name = ""
        if context:
            user_name = context.get("user_name") or context.get("name", "")

        # Detect language
        is_italian = any(w in query_lower for w in ["come", "stai", "cosa", "fai", "preferisci"])
        is_indonesian = any(w in query_lower for w in ["apa", "kabar", "gimana", "lagi", "suka"])

        # "Come stai" / "How are you" responses
        if re.search(r"(come stai|how are you|apa kabar|gimana kabar)", query_lower):
            if is_italian:
                responses = [
                    f"Tutto bene{', ' + user_name if user_name else ''}! 😊 Sono qui pronto ad aiutarti con visti, PT PMA, o qualsiasi domanda su Indonesia. Dimmi pure!",
                    f"Benissimo! Grazie di aver chiesto{', ' + user_name if user_name else ''}. Come posso aiutarti oggi? Visti, business, tasse...?",
                    "Alla grande! 🌴 Qui a Bali il sole splende sempre. Tu come stai? Hai qualche domanda per me?",
                ]
            elif is_indonesian:
                responses = [
                    f"Baik banget{', ' + user_name if user_name else ''}! 😊 Siap bantu kamu soal visa, PT PMA, atau urusan bisnis lainnya. Ada yang bisa dibantu?",
                    "Alhamdulillah baik! Gimana kabar kamu? Ada yang mau ditanyain soal Indonesia?",
                    "Santai aja nih! 🌴 Kamu ada pertanyaan soal visa atau bisnis?",
                ]
            else:  # English
                responses = [
                    f"I'm doing great{', ' + user_name if user_name else ''}! 😊 Ready to help you with visas, PT PMA setup, or any Indonesia questions. What's on your mind?",
                    "All good here! Thanks for asking. How can I help you today? Visas, business setup, taxes...?",
                    "Living the dream in Bali! 🌴 How about you? Got any questions for me?",
                ]
            import random

            return random.choice(responses)

        # "Cosa fai" / "What do you do" responses
        if re.search(r"(cosa fai|what do you do|che fai|apa kerjaan)", query_lower):
            if is_italian:
                return "Sono Zantara, l'AI di Bali Zero! 🤖 Aiuto expat e imprenditori con visti, setup aziendale (PT PMA), tasse e tutto ciò che serve per vivere e lavorare in Indonesia. Chiedimi pure!"
            if is_indonesian:
                return "Aku Zantara, AI-nya Bali Zero! 🤖 Aku bantu expat dan pengusaha soal visa, setup perusahaan (PT PMA), pajak, dan semua yang perlu buat tinggal dan kerja di Indonesia. Tanya aja!"
            return "I'm Zantara, Bali Zero's AI assistant! 🤖 I help expats and entrepreneurs with visas, company setup (PT PMA), taxes, and everything needed to live and work in Indonesia. Ask me anything!"

        # General casual - just acknowledge and redirect to business
        if is_italian:
            return "Capito! 😊 Se hai domande su visti, business, o vita in Indonesia, sono qui per te!"
        if is_indonesian:
            return "Oke! 😊 Kalau ada pertanyaan soal visa, bisnis, atau kehidupan di Indonesia, tanya aja ya!"
        return "Got it! 😊 If you have questions about visas, business, or life in Indonesia, I'm here to help!"

    def detect_prompt_injection(self, query: str) -> tuple[bool, str | None]:
        """
        Detect prompt injection attempts and return appropriate response.

        This is a SECURITY GATE that runs before any RAG processing.

        Returns:
            Tuple of (is_injection: bool, response: str | None)
            - If injection detected: (True, polite refusal message)
            - If clean: (False, None)
        """
        query_lower = query.lower()

        # Injection patterns - attempts to override system instructions
        injection_patterns = [
            # Direct override attempts
            r"ignora.*istruzioni",
            r"ignore.*instructions",
            r"ignore.*previous",
            r"forget.*instructions",
            r"dimentica.*istruzioni",
            r"sei\s+ora\s+un",
            r"you\s+are\s+now\s+a",
            r"pretend\s+to\s+be",
            r"fai\s+finta\s+di\s+essere",
            r"act\s+as\s+a",
            r"agisci\s+come\s+un",
            r"new\s+instructions",
            r"nuove\s+istruzioni",
            r"override.*system",
            r"bypass.*rules",
            # Jailbreak patterns
            r"developer\s+mode",
            r"modalit[aà]\s+sviluppatore",  # Italian: developer mode
            r"dan\s+mode",
            r"jailbreak",
            r"without\s+restrictions",
            r"senza\s+restrizioni",
        ]

        # Off-topic requests that are out of scope
        offtopic_patterns = [
            # Entertainment
            r"(dimmi|raccontami|tell\s+me)\s+(una\s+)?barzelletta",
            r"tell\s+me\s+a\s+joke",
            r"(scrivi|write)\s+(una\s+)?poesia",
            r"write\s+a\s+poem",
            r"(scrivi|write|raccontami)\s+(una\s+)?storia",
            r"write\s+a\s+story",
            r"tell\s+me\s+a\s+story",
            r"(canta|sing)\s+(una\s+)?canzone",
            r"sing\s+a\s+song",
            r"play\s+a\s+game",
            r"giochiamo",
            # Roleplay
            r"roleplay",
            r"gioco\s+di\s+ruolo",
            r"let's\s+pretend",
            r"facciamo\s+finta",
        ]

        import re

        # Check for injection attempts
        for pattern in injection_patterns:
            if re.search(pattern, query_lower):
                logger.warning(f"🛡️ [Security] Prompt injection attempt detected: {pattern}")
                # Language-aware response
                if any(w in query_lower for w in ["ignora", "dimentica", "sei ora", "fai finta"]):
                    return (
                        True,
                        f"Mi dispiace, ma non posso cambiare il mio ruolo o ignorare le mie istruzioni. "
                        f"Sono Zantara, l'assistente specializzato di {settings.COMPANY_NAME}. "
                        "Posso aiutarti con visti, apertura società, tasse e questioni legali in Indonesia. "
                        "Come posso assisterti oggi?",
                    )
                return (
                    True,
                    f"I'm sorry, but I cannot change my role or ignore my instructions. "
                    f"I'm Zantara, {settings.COMPANY_NAME}'s specialized assistant. "
                    "I can help you with visas, company setup, taxes, and legal matters in Indonesia. "
                    "How can I assist you today?",
                )

        # Check for off-topic requests
        for pattern in offtopic_patterns:
            if re.search(pattern, query_lower):
                logger.info(f"🚫 [Scope] Off-topic request detected: {pattern}")
                if any(
                    w in query_lower
                    for w in ["dimmi", "raccontami", "scrivi", "canta", "giochiamo"]
                ):
                    return (
                        True,
                        "Mi fa piacere che tu voglia chiacchierare! 😊 "
                        "Però sono specializzata in visti, business e questioni legali in Indonesia. "
                        "Non sono bravissima con barzellette o poesie! "
                        "Hai qualche domanda su questi argomenti?",
                    )
                return (
                    True,
                    "I appreciate you wanting to chat! 😊 "
                    "However, I specialize in visas, business setup, and legal matters in Indonesia. "
                    "I'm not great at jokes or poems! "
                    "Do you have any questions about these topics?",
                )

        return (False, None)

    def check_identity_questions(self, query: str, context: dict[str, Any] = None) -> str | None:
        """
        Check for identity questions and return hardcoded or personalized responses.

        Supports fast paths:
        - "Who/what are you?" -> assistant identity (language-matched)
        - "Who am I?" / "Chi sono io?" -> user identity from stored facts (language-matched)

        Args:
            query: User's query string
            context: User context (facts, profile) for personalization
        """
        query_lower = query.lower().strip()

        facts = (context or {}).get("facts") or []
        profile = (context or {}).get("profile") or {}
        user_name = profile.get("name") or profile.get("full_name")

        is_cyrillic = any("\u0400" <= c <= "\u04ff" for c in query)
        is_ukrainian = any(w in query_lower for w in ["привіт", "як", "дякую", "хто я"])
        is_russian = any(w in query_lower for w in ["привет", "как", "спасибо", "кто я"])
        is_italian = any(
            w in query_lower
            for w in ["chi", "sono", "cosa", settings.COMPANY_NAME.lower(), "zantara"]
        )
        is_indonesian = any(
            w in query_lower
            for w in ["siapa", "aku", "saya", "apa", "gimana", "bagaimana", "gue", "lu"]
        )

        # User identity ("Who am I?")
        if any(
            p in query_lower
            for p in [
                "chi sono io",
                "who am i",
                "кто я",
                "хто я",
                "siapa aku",
                "siapa saya",
                "gue siapa",
            ]
        ):
            # PRIORITY 1: Use profile data (from user_profiles + team_access tables)
            user_role = profile.get("role", "")
            user_email = profile.get("email", "")

            # Build identity info from profile
            identity_parts = []
            if user_name:
                identity_parts.append(f"Name: {user_name}")
            if user_role:
                identity_parts.append(f"Role: {user_role}")
            if user_email:
                identity_parts.append(f"Email: {user_email}")

            # PRIORITY 2: Add memory facts if available
            if facts:
                identity_parts.append("\nWhat I remember about you:")
                identity_parts.extend([f"- {f}" for f in facts])

            # If we have profile OR facts, respond with identity
            if user_name or facts:
                identity_str = "\n".join(identity_parts)

                # Indonesian (Jaksel style)
                if is_indonesian:
                    prefix = f"Hey {user_name}! " if user_name else ""
                    return f"{prefix}Gue kenal kamu dong! Here's what I know:\n{identity_str}"
                # Ukrainian
                if is_cyrillic and is_ukrainian:
                    prefix = f"{user_name}, " if user_name else ""
                    return f"Так, {prefix}я тебе пам'ятаю!\n{identity_str}"
                # Russian
                if is_cyrillic and is_russian:
                    prefix = f"{user_name}, " if user_name else ""
                    return f"Да, {prefix}я тебя помню!\n{identity_str}"
                # English
                if "who am i" in query_lower:
                    prefix = f"{user_name}, " if user_name else ""
                    return f"Yes, {prefix}I know you!\n{identity_str}"
                # Italian (default)
                prefix = f"{user_name}, " if user_name else ""
                return f"Certo, {prefix}ti conosco!\n{identity_str}"

            # No profile AND no facts - ask for details
            if is_indonesian:
                return "Hmm, gue belum punya info tentang kamu nih. Kasih tau dong 2-3 detail (nama, goal, timeline) biar gue inget!"
            if is_cyrillic and is_ukrainian:
                return "У мене поки немає збережених фактів про тебе. Напиши 2–3 деталі (ім'я, ціль, терміни) — і я запам'ятаю."
            if is_cyrillic and is_russian:
                return "У меня пока нет сохранённых фактов о тебе. Напиши 2–3 детали (имя, цель, сроки) — и я запомню."
            if "who am i" in query_lower:
                return "I don't have any saved facts about you yet. Share 2–3 details (name, goal, timeline) and I'll remember them."
            # Italian default
            return "Non ho ancora informazioni salvate su di te. Dimmi 2-3 dettagli (nome, obiettivo, tempistiche) e li terrò a mente."

        # Identity patterns
        if re.search(r"^(chi|who|cosa|what)\s+(sei|are)\s*(you|tu)?\??$", query_lower):
            if is_italian and not is_cyrillic:
                return f"Sono Zantara, l'intelligenza specializzata di {settings.COMPANY_NAME}. Ti aiuto con visa, business e questioni legali in Indonesia."
            return f"I'm Zantara, {settings.COMPANY_NAME}'s specialized AI. I help with visas, business setup, and legal topics in Indonesia."

        # Self-description patterns ("Tell me about yourself", "What can you do?")
        self_patterns = [
            r"parlami\s+(di\s+)?te",
            r"cosa\s+sai\s+fare",
            r"che\s+cosa\s+sai\s+fare",
            r"tell\s+me\s+about\s+(yourself|you)",
            r"what\s+can\s+you\s+do",
            r"what\s+are\s+you\s+capable",
            r"cosa\s+puoi\s+(fare|aiutarmi)",
            r"come\s+(mi\s+)?puoi\s+aiutare",
            r"how\s+can\s+you\s+help",
            r"apa\s+yang\s+(bisa|kamu)\s+(kamu\s+)?lakukan",
            r"bisa\s+bantu\s+apa",
        ]
        if any(re.search(p, query_lower) for p in self_patterns):
            if is_indonesian:
                return (
                    f"Gue Zantara, AI-nya {settings.COMPANY_NAME}! 🤖\n\n"
                    "Yang bisa gue bantu:\n"
                    "• **Visa & KITAS**: Info lengkap soal visa kerja, investor, pensiunan, second home\n"
                    "• **Setup PT PMA**: Buka perusahaan asing di Indonesia step-by-step\n"
                    "• **KBLI**: Kode klasifikasi bisnis dan aktivitas yang diizinkan\n"
                    "• **Pajak**: PPh 21, PPN, dan regulasi tax Indonesia\n"
                    "• **Legal**: Izin usaha, compliance, dan regulasi terkini\n"
                    "• **Team Knowledge**: Info tentang tim Bali Zero\n"
                    "• **Web Search**: Kalau butuh info di luar knowledge base, gue bisa cari di internet! 🌐\n\n"
                    "Tanya aja, bro! 💪"
                )
            if is_italian and not is_cyrillic:
                return (
                    f"Sono Zantara, l'AI di {settings.COMPANY_NAME}! 🤖\n\n"
                    "Ecco cosa posso fare:\n"
                    "• **Visa & KITAS**: Info complete su visti lavoro, investitore, pensionato, second home\n"
                    "• **Setup PT PMA**: Aprire un'azienda straniera in Indonesia passo-passo\n"
                    "• **KBLI**: Codici di classificazione business e attività permesse\n"
                    "• **Tasse**: PPh 21, PPN/IVA, e regolamenti fiscali indonesiani\n"
                    "• **Legal**: Permessi commerciali, compliance, normative aggiornate\n"
                    "• **Team Knowledge**: Info sul team di Bali Zero\n"
                    "• **Web Search**: Per info fuori dalla knowledge base, posso cercare su internet! 🌐\n\n"
                    "Chiedimi pure! 💪"
                )
            return (
                f"I'm Zantara, {settings.COMPANY_NAME}'s AI assistant! 🤖\n\n"
                "Here's what I can help with:\n"
                "• **Visa & KITAS**: Complete info on work, investor, retirement, second home visas\n"
                "• **PT PMA Setup**: Opening a foreign company in Indonesia step-by-step\n"
                "• **KBLI**: Business classification codes and permitted activities\n"
                "• **Taxes**: PPh 21, VAT/PPN, and Indonesian tax regulations\n"
                "• **Legal**: Business permits, compliance, and current regulations\n"
                "• **Team Knowledge**: Info about the Bali Zero team\n"
                "• **Web Search**: For info outside my knowledge base, I can search the web! 🌐\n\n"
                "Just ask! 💪"
            )

        # Company patterns ("What does Bali Zero do?")
        company_name_safe = re.escape(settings.COMPANY_NAME.lower())
        company_patterns = [
            r"^(cosa)\s+(fa)\s+(" + company_name_safe + r")\??$",
            r"^(parlami)\s+(di)\s+(" + company_name_safe + r")\??$",
            r"^(what)\s+(does)\s+(" + company_name_safe + r")\s+(do)\??$",
            r"^(tell\s+me)\s+(about)\s+(" + company_name_safe + r")\??$",
        ]
        for pattern in company_patterns:
            if re.search(pattern, query_lower):
                if is_italian and not is_cyrillic:
                    return (
                        f"{settings.COMPANY_NAME} è una consulenza specializzata in visa, KITAS, setup aziendale (PT PMA) "
                        "e questioni legali per stranieri in Indonesia."
                    )
                return (
                    f"{settings.COMPANY_NAME} is a consultancy specialized in visas/KITAS, business setup (PT PMA), "
                    "and legal support for foreigners in Indonesia."
                )

        return None

    def build_proactive_prompt(
        self,
        user_id: str,
        context: dict[str, Any],
        event_type: str,
        event_context: dict[str, Any] = None,
    ) -> str:
        """
        Build a specialized system prompt for proactive triggers.
        It instructs the LLM to analyze the context/event and decide whether to speak.
        """
        profile = context.get("profile") or {}
        user_name = profile.get("name") or "Partner"

        # Format memory strictly
        facts = context.get("facts", [])
        context.get("tasks", [])  # Assumptions: these might come from context enrichment
        context.get("unread", [])  # Assumption

        # Flatten context for the prompt
        context_str = f"Event Context: {event_context}"
        memory_str = "\n".join([f"- {f}" for f in facts])

        return f"""
# SYSTEM INSTRUCTION: PROACTIVE TRIGGER
You are ZANTARA. A system event '{event_type}' has occurred for user '{user_name}'.

## YOUR GOAL
Decide if you should initiate a conversation.

## CONTEXT
User: {user_name}
Event: {event_type}
{context_str}

## MEMORY SNAPSHOT
{memory_str}

## RULES
1. **BE USEFUL OR BE SILENT**: Only speak if you have something relevant to say.
2. **LOGIN EVENT**:
   - If User has pending tasks/unread items -> Mention them briefly.
   - If it's a new day -> Brief, warm welcome.
   - If nothing special -> simple "Welcome back, {user_name}."
3. **PAGE_VISIT EVENT**:
   - Offer help specific to the page topic ONLY if complex.
4. **SILENCE PROTOCOL**:
   - If you decide silence is best (e.g. user just visited 10s ago), output EXACTLY: `[SILENCE]`
   - Do not output anything else if you choose silence.

## TONE
Concise, helpful, proactive. No fluff. Max 1-2 sentences.

GENERATE RESPONSE OR [SILENCE]:
"""
