"""
Intent Classifier Module
Fast pattern-based intent classification without AI cost
"""

import logging

logger = logging.getLogger(__name__)

# Pattern matching constants
SIMPLE_GREETINGS = [
    "ciao",
    "hello",
    "hi",
    "hey",
    "salve",
    "buongiorno",
    "buonasera",
    "halo",
    "hallo",
]

# Identity keywords (highest priority - self-recognition queries)
IDENTITY_KEYWORDS = [
    # Italian
    "chi sono",
    "chi sono io",
    "chi sei",
    "mi conosci",
    "sai chi sono",
    "cosa sai di me",
    "il mio nome",
    "il mio ruolo",
    "mi riconosci",
    # English
    "who am i",
    "who am i?",
    "do you know me",
    "my name",
    "my role",
    "recognize me",
    "who is this",
    # Indonesian
    "siapa saya",
    "siapa aku",
    "apakah kamu kenal saya",
    "nama saya",
    "kenal saya",
]

# Team query keywords (team enumeration queries)
TEAM_QUERY_KEYWORDS = [
    # Italian
    "team",
    "membri",
    "colleghi",
    "chi lavora",
    "quanti siamo",
    "dipartimento",
    "bali zero team",
    "conosci i membri",
    "parlami del team",
    # English
    "team members",
    "colleagues",
    "who works",
    "department",
    "know the members",
    "tell me about the team",
    # Indonesian
    "tim",
    "anggota tim",
    "rekan kerja",
]

SESSION_PATTERNS = [
    # Login intents
    "login",
    "log in",
    "sign in",
    "signin",
    "masuk",
    "accedi",
    # Logout intents
    "logout",
    "log out",
    "sign out",
    "signout",
    "keluar",
    "esci",
]

CASUAL_PATTERNS = [
    "come stai",
    "how are you",
    "come va",
    "tutto bene",
    "apa kabar",
    "what's up",
    "whats up",
    "sai chi sono",
    "do you know me",
    "know who i am",
    "recognize me",
    "remember me",
    "mi riconosci",
]

EMOTIONAL_PATTERNS = [
    # Embarrassment / Shyness
    "aku malu",
    "saya malu",
    "i'm embarrassed",
    "i feel embarrassed",
    "sono imbarazzato",
    # Sadness / Upset
    "aku sedih",
    "saya sedih",
    "i'm sad",
    "i feel sad",
    "sono triste",
    "mi sento giù",
    # Anxiety / Worry
    "aku khawatir",
    "saya khawatir",
    "i'm worried",
    "i worry",
    "sono preoccupato",
    "mi preoccupa",
    # Loneliness
    "aku kesepian",
    "saya kesepian",
    "i'm lonely",
    "i feel lonely",
    "mi sento solo",
    # Stress / Overwhelm
    "aku stress",
    "saya stress",
    "i'm stressed",
    "sono stressato",
    "mi sento sopraffatto",
    # Fear
    "aku takut",
    "saya takut",
    "i'm scared",
    "i'm afraid",
    "ho paura",
    # Happiness / Excitement
    "aku senang",
    "saya senang",
    "i'm happy",
    "sono felice",
    "che bello",
]

BUSINESS_KEYWORDS = [
    # Generic business keywords only - no specific codes (KITAS, PT PMA are in database)
    "visa",
    "company",
    "business",
    "investimento",
    "investment",
    "tax",
    "pajak",
    "immigration",
    "imigrasi",
    "permit",
    "license",
    "regulation",
    "real estate",
    "property",
    "kbli",
    "nib",
    "oss",
    "work permit",
    "kitas",
    "kitap",
    "pma",
    "pt",
    "cv",
    "investor",
    "investitori",
    "voa",
    "b211",
    "211a",
    "e33g",
    "e28a",
    # Italian business keywords (added for RAG activation)
    "legale",
    "leggi",
    "contratto",
    "memoria",
    "ricordo",
    "cliente",
    "CRM",
    "funzioni",
    "servizi",
    "errore",
    "sistema",
    "conoscenza",
    "documento",
    "informazione",
    "azienda",
    "consulenza",
    "cerca",
    "controlla",
    "puoi",
    "dimmi",
    "trova",
    "pratiche",
    "visti",
    "licenze",
    "tasse",
    "immigrazione",
]

COMPLEX_INDICATORS = [
    # Process-oriented
    "how to",
    "how do i",
    "come si",
    "bagaimana cara",
    "cara untuk",
    "step",
    "process",
    "procedure",
    "prosedur",
    "langkah",
    # Detail-oriented
    "explain",
    "spiegare",
    "jelaskan",
    "detail",
    "dettaglio",
    "rincian",
    # Requirement-oriented
    "requirement",
    "requisiti",
    "syarat",
    "what do i need",
    "cosa serve",
    # Multi-part questions
    " and ",
    " or ",
    " also ",
    " e ",
    " o ",
    " dan ",
    " atau ",
]

DEEP_THINK_KEYWORDS = [
    "strategy",
    "strategia",
    "strategi",
    "analysis",
    "analisi",
    "analisa",
    "compare",
    "confronta",
    "bandingkan",
    "pros and cons",
    "pro e contro",
    "kelebihan dan kekurangan",
    "recommendation",
    "raccomandazione",
    "rekomendasi",
    "plan",
    "piano",
    "rencana",
    "scenario",
    "risk assessment",
    "valutazione rischi",
    "rischi",
    "rischio",
    "conviene",
    "meglio",
    "migliore",
    "best option",
    "differenza",
    "difference",
    "vs",
]

PRO_KEYWORDS = [
    "requisiti",
    "requirements",
    "costi",
    "costs",
    "prezzo",
    "price",
    "documenti",
    "documents",
    "procedura",
    "procedure",
    "come ottenere",
    "how to get",
    "durata",
    "duration",
    "validità",
    "validity",
    "tasse",
    "taxes",
]

SIMPLE_PATTERNS = [
    "what is",
    "what's",
    "cos'è",
    "apa itu",
    "cosa è",
    "who is",
    "chi è",
    "siapa",
    "when is",
    "quando",
    "kapan",
    "where is",
    "dove",
    "dimana",
]

DEVAI_KEYWORDS = [
    "code",
    "coding",
    "programming",
    "debug",
    "error",
    "bug",
    "function",
    "api",
    "devai",
    "typescript",
    "javascript",
    "python",
    "java",
    "react",
    "algorithm",
    "refactor",
    "optimize",
    "test",
    "unit test",
]


class IntentClassifier:
    """
    Fast pattern-based intent classifier

    Classifies user intents without AI cost using pattern matching:
    - greeting: Simple greetings (Ciao, Hello, Hi)
    - casual: Casual questions (Come stai? How are you?)
    - session_state: Login/logout/identity queries
    - business_simple: Simple business questions
    - business_complex: Complex business/legal questions
    - devai_code: Development/code queries
    - unknown: Fallback category

    Maps to Quality Routing Tiers:
    - fast: Simple queries, greetings, casual (Gemini Flash)
    - pro: Standard business queries (Gemini Pro)
    - deep_think: Complex strategy/analysis (Gemini Pro + Reasoning)
    """

    def __init__(self):
        """Initialize intent classifier with pattern constants"""
        logger.info("🏷️ [IntentClassifier] Initialized (pattern-based, no AI cost)")

    async def classify_intent(self, message: str) -> dict:
        """
        Classify user intent using fast pattern matching

        Args:
            message: User message to classify

        Returns:
            {
                "category": str,
                "confidence": float,
                "suggested_ai": "fast"|"pro"|"deep_think"|"devai",
                "require_memory": bool (optional)
            }
        """
        try:
            message_lower = message.lower().strip()

            # Check exact greetings first
            if message_lower in SIMPLE_GREETINGS:
                logger.info("🏷️ [IntentClassifier] Classified: greeting")
                result = {
                    "category": "greeting",
                    "confidence": 1.0,
                    "suggested_ai": "fast",
                    "require_memory": True,
                }
                result["mode"] = self._derive_mode(result["category"], message_lower)
                return result

            # PRIORITY 1: Identity queries (highest priority - before session_state)
            if any(pattern in message_lower for pattern in IDENTITY_KEYWORDS):
                logger.info("🏷️ [IntentClassifier] Classified: identity")
                result = {
                    "category": "identity",
                    "confidence": 0.95,
                    "suggested_ai": "fast",
                    "requires_team_context": True,
                }
                result["mode"] = self._derive_mode(result["category"], message_lower)
                return result

            # PRIORITY 2: Team queries
            if any(pattern in message_lower for pattern in TEAM_QUERY_KEYWORDS):
                logger.info("🏷️ [IntentClassifier] Classified: team_query")
                result = {
                    "category": "team_query",
                    "confidence": 0.9,
                    "suggested_ai": "fast",
                    "requires_rag_collection": "bali_zero_team",
                }
                result["mode"] = self._derive_mode(result["category"], message_lower)
                return result

            # Check session state patterns
            if any(pattern in message_lower for pattern in SESSION_PATTERNS):
                logger.info("🏷️ [IntentClassifier] Classified: session_state")
                result = {
                    "category": "session_state",
                    "confidence": 1.0,
                    "suggested_ai": "fast",
                    "require_memory": True,
                }
                result["mode"] = self._derive_mode(result["category"], message_lower)
                return result

            # Check casual questions
            if any(pattern in message_lower for pattern in CASUAL_PATTERNS):
                logger.info("🏷️ [IntentClassifier] Classified: casual")
                result = {"category": "casual", "confidence": 1.0, "suggested_ai": "fast"}
                result["mode"] = self._derive_mode(result["category"], message_lower)
                return result

            # Check emotional patterns
            if any(pattern in message_lower for pattern in EMOTIONAL_PATTERNS):
                logger.info("🏷️ [IntentClassifier] Classified: casual (emotional)")
                result = {
                    "category": "casual",
                    "confidence": 1.0,
                    "suggested_ai": "fast",
                }
                result["mode"] = self._derive_mode(result["category"], message_lower)
                return result

            # Check business keywords
            has_business_term = any(keyword in message_lower for keyword in BUSINESS_KEYWORDS)

            if has_business_term:
                # Detect complexity
                has_complex_indicator = any(
                    indicator in message_lower for indicator in COMPLEX_INDICATORS
                )
                has_deep_think_indicator = any(
                    indicator in message_lower for indicator in DEEP_THINK_KEYWORDS
                )
                has_pro_indicator = any(indicator in message_lower for indicator in PRO_KEYWORDS)
                is_simple_question = any(pattern in message_lower for pattern in SIMPLE_PATTERNS)

                # Decision logic:
                # 1. Deep think indicators → DeepThink (Pro + Reasoning)
                # 2. Pro indicators OR Complex indicators → Pro
                # 3. Simple question + short message → Fast (Flash)

                if has_deep_think_indicator:
                    logger.info("🏷️ [IntentClassifier] Classified: business_strategic (DeepThink)")
                    result = {
                        "category": "business_strategic",
                        "confidence": 0.95,
                        "suggested_ai": "deep_think",
                    }
                elif has_pro_indicator or has_complex_indicator or len(message) > 100:
                    logger.info("🏷️ [IntentClassifier] Classified: business_complex (Pro)")
                    result = {
                        "category": "business_complex",
                        "confidence": 0.9,
                        "suggested_ai": "pro",
                    }
                elif is_simple_question and len(message) < 50:
                    logger.info("🏷️ [IntentClassifier] Classified: business_simple (Fast)")
                    result = {
                        "category": "business_simple",
                        "confidence": 0.9,
                        "suggested_ai": "fast",
                    }
                else:
                    logger.info("🏷️ [IntentClassifier] Classified: business_medium (Pro default)")
                    result = {
                        "category": "business_simple",
                        "confidence": 0.8,
                        "suggested_ai": "pro",
                    }
                result["mode"] = self._derive_mode(result["category"], message_lower)
                return result

            # Check DevAI keywords
            if any(keyword in message_lower for keyword in DEVAI_KEYWORDS):
                logger.info("🏷️ [IntentClassifier] Classified: devai_code")
                result = {"category": "devai_code", "confidence": 0.9, "suggested_ai": "devai"}
                result["mode"] = self._derive_mode(result["category"], message_lower)
                return result

            # Fast heuristic fallback: short messages → Fast
            logger.info(f"🏷️ [IntentClassifier] Fallback classification for: '{message[:50]}...'")

            # Smarter fallback: only classify as casual if short AND no business keywords
            if len(message) < 50 and not any(kw in message_lower for kw in BUSINESS_KEYWORDS):
                category = "casual"
                suggested_ai = "fast"
                logger.info(
                    "🏷️ [IntentClassifier] Fallback: casual (short message, no business keywords)"
                )
            else:
                category = "business_simple"  # Default to business, not casual
                suggested_ai = "fast"
                logger.info(
                    "🏷️ [IntentClassifier] Fallback: business_simple (has business keywords or long message)"
                )

            result = {
                "category": category,
                "confidence": 0.7,  # Pattern matching confidence
                "suggested_ai": suggested_ai,
            }

            # Derive communication mode
            result["mode"] = self._derive_mode(result["category"], message_lower)
            return result

        except Exception as e:
            logger.error(f"🏷️ [IntentClassifier] Error: {e}")
            # Fallback: route to Fast
            return {
                "category": "unknown",
                "confidence": 0.0,
                "suggested_ai": "fast",
                "mode": "small_talk",
            }

    def _derive_mode(self, category: str, message_lower: str) -> str:
        """
        Derive the communication mode from the intent category and message content.
        Maps to modes defined in communication_modes.yaml.
        """
        # 1. Direct mapping from category
        if category == "greeting":
            return "greeting"
        if category == "casual" or category == "session_state":
            return "small_talk"
        if category == "identity":
            return "identity_response"
        if category == "devai_code":
            return "technical"

        # 2. Refine business categories
        if category.startswith("business"):
            # Check for procedure/guide request
            if any(
                kw in message_lower
                for kw in ["how to", "come si", "step", "procedura", "process", "guide"]
            ):
                return "procedure_guide"

            # Check for risk/compliance
            if any(
                kw in message_lower
                for kw in ["risk", "rischio", "penalty", "sanzione", "illegal", "compliance"]
            ):
                return "risk_explainer"

            # Check complexity
            if category == "business_complex" or len(message_lower) > 100:
                return "legal_deep"

            return "legal_brief"

        # Default fallback
        return "small_talk"
