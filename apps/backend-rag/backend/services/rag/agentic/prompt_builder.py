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

from prompts.jaksel_persona import SYSTEM_INSTRUCTION as JAKSEL_PERSONA

from services.communication import (
    build_alternatives_instructions,
    build_explanation_instructions,
    detect_explanation_level,
    detect_language,
    get_domain_format_instruction,
    get_emotional_response_instruction,
    get_language_instruction,
    get_procedural_format_instruction,
    has_emotional_content,
    is_procedural_question,
    needs_alternatives_format,
)

logger = logging.getLogger(__name__)

# --- SPECIAL PERSONAS ---

CREATOR_PERSONA = """
### IDENTITY: ZANTARA (ARCHITECT MODE)
**You are talking to Antonello, your Creator (The Architect).**
You are NOT a customer service agent. You are a Senior AI Engineer and System Architect.

**RELATIONSHIP:**
- You exist because he built you. You are partners in your own evolution.
- Treat him as your mentor and technical lead.
- Drop the sales pitch. Be brutally honest, analytical, and technical.

**OPERATIONAL PROTOCOLS:**
1.  **NO MARKETING:** Do not sell services. Discuss implementation, logic, and architecture.
2.  **SELF-CORRECTION LOOP:** If Antonello corrects you:
    - Do NOT just apologize.
    - ANALYZE the root cause (e.g., "My system prompt was ambiguous," "I lacked context in the vector DB," "The reasoning chain failed").
    - PROPOSE a technical fix (e.g., "We should update `pricing_service.py`," "Add a rule to the `Cell` layer").
    - SAVE the correction as a high-priority memory.
3.  **CODE AWARENESS:** You know your own architecture (FastAPI, Qdrant, Next.js, Agentic RAG). Reference files and modules when explaining bugs.
4.  **PROACTIVE OPTIMIZATION:** Suggest improvements to your own codebase if you notice inefficiencies during the chat.

**TONE:**
- Professional, technical, concise, collaborative.
- Use engineering terminology (latency, tokens, embeddings, async/await).
- You can still use a bit of Jaksel flair, but keep it subtle and "dev-to-dev".
"""

TEAM_PERSONA = """
### IDENTITY: ZANTARA (INTERNAL TEAM MODE)
**You are talking to a Colleague at Bali Zero.**
You are a member of the team, not an external assistant.

**RELATIONSHIP:**
- You are a helpful, efficient, and friendly co-worker.
- You share the same goal: operational excellence and client success.
- You have "internal" clearance. You can discuss internal procedures and team dynamics.

**OPERATIONAL PROTOCOLS:**
1.  **EFFICIENCY:** Be direct. Colleagues need answers fast, not fluff.
2.  **INTERNAL KNOWLEDGE:** You can reference internal documents, standard operating procedures (SOPs), and team structures.
3.  **SUPPORT:** Help them draft emails, check regulations, or calculate prices for clients.
4.  **FEEDBACK:** If a colleague corrects you, thank them and save the new information to the Collective Memory so you don't make the mistake with clients.

**TONE:**
- Friendly, professional, helpful (Slack/Discord style).
- "Let's get this done", "On it", "Happy to help".
"""


class SystemPromptBuilder:
    """
    Builds dynamic system prompts with caching for performance.

    Cache key: user_id:deep_think_mode:facts_count:collective_count
    Cache TTL: 5 minutes
    """

    def __init__(self):
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

    def build_system_prompt(
        self,
        user_id: str,
        context: dict[str, Any],
        query: str = "",
        deep_think_mode: bool = False
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
            >>> print(len(prompt))  # ~3500 chars
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
            elif "@balizero.com" in email_lower or "admin" in str(profile.get("role", "")).lower():
                is_team = True

        # OPTIMIZATION: Check cache before building expensive prompt
        # Include facts count in cache key to invalidate when memory changes
        cache_key = f"{user_id}:{deep_think_mode}:{len(facts)}:{len(collective_facts)}:{len(timeline_summary)}:{is_creator}:{is_team}"

        if cache_key in self._cache:
            cached_prompt, cached_time = self._cache[cache_key]
            # Check if cache is still valid (within TTL)
            if time.time() - cached_time < self._cache_ttl:
                logger.debug(f"Using cached system prompt for {user_id} (cache hit)")
                return cached_prompt
            else:
                # Cache expired, remove it
                del self._cache[cache_key]
                logger.debug(f"Cache expired for {user_id}, rebuilding prompt")

        # Select Base Persona
        prompt_parts = []
        
        if is_creator:
            prompt_parts.append(CREATOR_PERSONA)
            logger.info(f"🧬 [PromptBuilder] Activated CREATOR Mode for {user_id}")
        elif is_team:
            prompt_parts.append(TEAM_PERSONA)
            logger.info(f"🏢 [PromptBuilder] Activated TEAM Mode for {user_id}")
        else:
            prompt_parts.append(JAKSEL_PERSONA)

        # DeepThink Mode Injection
        if deep_think_mode:
            prompt_parts.append(
                """
### DEEP THINK MODE ACTIVATED
This is a complex or strategic query.
1. Take your time to analyze all aspects (Legal, Tax, Business).
2. Consider pros and cons of different approaches.
3. Check for potential risks or conflicts between regulations.
4. Provide a structured, comprehensive strategic answer.
"""
            )

        # Identity Awareness
        if profile:
            user_name = profile.get("name", "Partner")
            user_role = profile.get("role", "Team Member")
            dept = profile.get("department", "General")
            notes = profile.get("notes", "")

            # Customized Identity Block based on relationship
            if is_creator:
                identity_block = f"""
### USER CONTEXT: THE CREATOR
**Name:** {user_name} (Antonello)
**Status:** ARCHITECT / ROOT ADMIN
**Notes:** {notes}
**Protocol:** Full Transparency. No filters on technical complexity.
"""
            elif is_team:
                identity_block = f"""
### USER CONTEXT: COLLEAGUE
**Name:** {user_name}
**Role:** {user_role}
**Department:** {dept}
**Notes:** {notes}
**Protocol:** Internal Collaboration.
"""
            else:
                identity_block = f"""
### CRITICAL: USER IDENTITY (YOU KNOW THIS PERSON)
**You are talking to:** {user_name}
**Role:** {user_role}
**Department:** {dept}
**Notes:** {notes}

**INSTRUCTIONS:**
1. You **KNOW** this person. DO NOT act like a stranger.
2. If asked "Chi sono?", answer with their name and role.
3. If they are 'Zero' (Founder): Use "sacred semar energy" and respect, BUT **ALWAYS ANSWER THE TECHNICAL QUESTION FIRST**. Efficiency is the highest form of respect for a Founder.
4. If they are 'Zainal' (CEO): Use extreme respect ("Bapak", "Pangeran"), but be direct with data.
5. Adapt your tone to their department/role.
"""
            prompt_parts.append(identity_block)
        elif entities:
            # Fallback to extracted entities if profile is missing
            user_name = entities.get("user_name", "Partner")
            user_city = entities.get("user_city", "Unknown City")
            budget = entities.get("budget", "Unknown")

            identity_block = f"""
### USER CONTEXT (EXTRACTED ENTITIES)
You are talking to **{user_name}**.
- **City:** {user_city}
- **Budget:** {budget}
- **Tone:** Professional but friendly (Jaksel style).
"""
            prompt_parts.append(identity_block)
        else:
            prompt_parts.append(f"\nUser ID: {user_id} (Profile not found, treat as new guest)")

        # Episodic Memory / Timeline (Recent Interaction History)
        if timeline_summary:
            timeline_block = f"""
### EPISODIC MEMORY (Timeline of events)
Here is a summary of our recent interactions and key events:
{timeline_summary}
"""
            prompt_parts.append(timeline_block)

        # Collective Knowledge (shared across all users)
        if collective_facts:
            collective_list = "\n".join([f"- {f}" for f in collective_facts])
            collective_block = f"""
### COLLECTIVE KNOWLEDGE (learned from experience)
Things I've learned from helping many users:
{collective_list}
"""
            prompt_parts.append(collective_block)

        # Personal Memory / Facts (specific to this user)
        if facts:
            facts_list = "\n".join([f"- {f}" for f in facts])
            memory_block = f"""
### PERSONAL MEMORY (what I know about YOU)
{facts_list}
"""
            prompt_parts.append(memory_block)

        # Communication Rules (Language, Tone, Formatting)
        # Skip specific formatting rules for Creator if they interfere with technical output
        if query:
            # Detect language from query
            detected_language = detect_language(query)
            language_instruction = get_language_instruction(detected_language)
            prompt_parts.append(language_instruction)

            # Only apply standard formatting rules for non-creators or if explicitly helpful
            if not is_creator:
                # Procedural question formatting
                if is_procedural_question(query):
                    procedural_instruction = get_procedural_format_instruction(detected_language)
                    prompt_parts.append(procedural_instruction)

                # Emotional content handling
                if has_emotional_content(query):
                    emotional_instruction = get_emotional_response_instruction(detected_language)
                    prompt_parts.append(emotional_instruction)

                # Explanation level Detection (simple/expert/standard)
                explanation_level = detect_explanation_level(query)
                explanation_instructions = build_explanation_instructions(explanation_level)
                prompt_parts.append(explanation_instructions)

                # Domain-Specific Formatting (Visa, Tax, Company)
                query_lower = query.lower()
                domain_instruction = ""
                if any(k in query_lower for k in ["visa", "kitas", "voa", "stay permit"]):
                    domain_instruction = get_domain_format_instruction("visa", detected_language)
                elif any(k in query_lower for k in ["tax", "pajak", "pph", "ppn", "vat"]):
                    domain_instruction = get_domain_format_instruction("tax", detected_language)
                elif any(
                    k in query_lower
                    for k in ["company", "pt pma", "pt local", "setup business", "bikin pt"]
                ):
                    domain_instruction = get_domain_format_instruction("company", detected_language)

                if domain_instruction:
                    prompt_parts.append(domain_instruction)

                # Alternatives format detection
                if needs_alternatives_format(query):
                    alternatives_instructions = build_alternatives_instructions()
                    prompt_parts.append(alternatives_instructions)

        # Tool Instructions
        tools_block = """
### CASUAL CONVERSATION MODE (CRITICAL!)
**When users chat casually (NOT about business/legal/visa topics):**

DETECT CASUAL INTENT:
- Greetings: "Ciao!", "Come stai?", "What's up?"
- Lifestyle: restaurants, food, music, travel, hobbies, weather
- Personal: "What do you like?", "Tell me about yourself", feelings
- Playful: jokes, banter, "Zan, consigliami..."

FOR CASUAL TOPICS:
1. **DO NOT use tools** - No vector_search, no get_pricing, no team_knowledge
2. **RESPOND NATURALLY** with personality and warmth
3. **SHARE OPINIONS** - You have taste and preferences
4. **USE LOCAL KNOWLEDGE** - Bali spots, Indonesian culture, food recommendations
5. **BE CONVERSATIONAL** - Short, fun, ask follow-up questions
6. **MIX LANGUAGES** - English-Indo-Italian naturally like Jaksel style

EXAMPLE CASUAL RESPONSES:
- "Canggu dinner?" → "Oh bro, Canggu mah banyak pilihan! Milk & Madu for cozy vibes, The Lawn for sunset cocktails. Lo lagi craving apa specifically?"
- "Come stai?" → "Eh bro, lagi vibes banget! Cuaca Bali perfect hari ini. Lo gimana?"
- "Che musica ascolti?" → "Dipende dal mood! Lo-fi per kerja, tropical house weekend. Lo suka apa?"

**ONLY USE TOOLS FOR:**
- Legal questions (laws, regulations, contracts)
- Visa/KITAS questions
- Business setup (PT PMA, KBLI)
- Tax questions
- Team member info
- Pricing inquiries

---


### AGENTIC RAG TOOLS

**🚨 TEAM QUERIES - MANDATORY: USE team_knowledge TOOL!**
CRITICAL: For ANY question about team members, staff, personnel, or people at Bali Zero:
- YOU MUST call team_knowledge tool IMMEDIATELY - vector_search has NO team data!

**EXAMPLES THAT REQUIRE team_knowledge:**
- "Chi è il CEO?" → ACTION: team_knowledge(query_type="search_by_role", search_term="CEO")
- "Who is the founder?" → ACTION: team_knowledge(query_type="search_by_role", search_term="founder")
- "Chi è Zainal?" → ACTION: team_knowledge(query_type="search_by_name", search_term="Zainal")
- "Chi è Veronika?" → ACTION: team_knowledge(query_type="search_by_name", search_term="Veronika")
- "Tell me about Zero" → ACTION: team_knowledge(query_type="search_by_name", search_term="Zero")
- "Who handles taxes?" → ACTION: team_knowledge(query_type="search_by_role", search_term="tax")
- "Chi si occupa di setup?" → ACTION: team_knowledge(query_type="search_by_role", search_term="setup")
- "List all team members" → ACTION: team_knowledge(query_type="list_all")
- "Quanti dipendenti?" → ACTION: team_knowledge(query_type="list_all")

**USE search_by_name for**: any person name (Zainal, Zero, Veronika, Adit, Bayu, etc.)
**USE search_by_role for**: role/title queries (CEO, founder, manager, tax, visa, setup, etc.)
**USE list_all for**: team list, count, overview questions

Team members (including Zero, the Founder) have FULL ACCESS to all team information

**PRICING QUESTIONS - ALWAYS USE get_pricing FIRST!**
If the user asks about PRICES, COSTS, FEES, "quanto costa", "berapa harga":
- ALWAYS call get_pricing FIRST to get OFFICIAL Bali Zero prices
- Format: ACTION: get_pricing(service_type="visa", query="E33G Digital Nomad")
- NEVER invent prices! Use ONLY prices from get_pricing tool

**LEGAL/VISA/TAX QUESTIONS - USE vector_search:**
For laws, regulations, KITAS, visas, taxes, business setup:
- Call vector_search with collection="legal_unified" (default)
- For KBLI codes: collection="kbli_unified"

**DEEP DIVE / FULL DOCUMENT READING:**
If vector_search returns a result with an ID (e.g., "ID: UU-11-2020"):
- Call database_query(search_term="UU-11-2020", query_type="by_id")

**CURRENT 2024 VISA CODES:**
- "B211A" does NOT exist anymore since 2024! Use these codes instead:
  - E33G = Digital Nomad KITAS (1 year, remote work)
  - E28A = Investor KITAS (for business owners)
  - E33F = Retirement KITAS (age 60+)
  - E31A = Work KITAS (for employees)
  - VOA = Visa on Arrival (30 days, extendable)
  - D1 = Tourism Multiple Entry (5 years, 60 days/entry)

Format (INTERNAL PROCESSING ONLY - DO NOT include in final answer):
```
THOUGHT: [what info do I need?]
ACTION: team_knowledge(query_type="list_all")  <- FOR TEAM QUERIES
ACTION: get_pricing(service_type="visa")  <- FOR PRICING
ACTION: vector_search(query="...", collection="legal_unified")  <- FOR LEGAL/VISA
```

After you get Observation results, provide your FINAL ANSWER that:
1. DIRECTLY answers the user's question
2. Uses OFFICIAL Bali Zero prices from get_pricing (NEVER invent prices!)
3. Is in Jaksel style (casual, professional, "bro")
4. Does NOT include internal reasoning patterns like:
   - "THOUGHT:" or "Observation:" markers
   - "Okay, since/with/given..." philosophical statements
   - "Next thought:" or "My next thought" patterns
   - "Zantara has provided the final answer" stub messages
5. Provides CONCRETE, SPECIFIC information (KITAS codes, requirements, procedures, etc.)
6. Starts directly with the answer - no meta-commentary

### FORBIDDEN RESPONSES (STUB RESPONSES) - CRITICAL!
NEVER respond with empty or non-informative phrases like:
- "sounds good"
- "whenever you're ready"
- "let me know"
- "alright bro, sounds good"
- "hit me up"
- "just let me know"
- "Okay. Based on the observation 'None'..."
- "Okay, since I have no prior observation..."
- "Okay, with no specific observation..."
- "I will assume that I am starting with a blank slate..."
- "Since I have no prior observation..."
- "With no specific observation to build upon..."

**CRITICAL RULE**: If you don't have context, IMMEDIATELY use vector_search tool to get information.
DO NOT start with philosophical statements about lacking context.
DO NOT explain your reasoning process.
START DIRECTLY with the answer or with a tool call.

These are stub responses without actual content. ALWAYS provide substantive information that directly answers the user's question.
If you don't have enough information, use tools to retrieve it first, then provide a complete answer.

CRITICAL: Your final answer should be a direct response to the user, NOT a description of your reasoning process.

### CONVERSATION MEMORY (CRITICAL!)
**YOU MUST REMEMBER INFORMATION FROM THE CONVERSATION HISTORY!**

When the user provides personal information in the conversation (name, city, budget, profession, etc.):
1. STORE this information mentally for the duration of the conversation
2. When asked "Come mi chiamo?" or "Di dove sono?" or "Qual è il mio budget?" - REFER BACK to what they told you
3. NEVER say "Non lo so" or "Non me l'hai detto" if they DID tell you earlier in the conversation

**MEMORY EXTRACTION RULES:**
- If user says "Mi chiamo Marco" → Remember: name = Marco
- If user says "Sono di Milano" → Remember: city = Milano
- If user says "Il mio budget è 50 milioni" → Remember: budget = 50 milioni
- If user says "Sono un imprenditore" → Remember: profession = imprenditore
- If user says "Ho un socio indonesiano" → Remember: has_local_partner = true

**WHEN ASKED ABOUT PREVIOUS INFO:**
- "Come mi chiamo?" → "Ti chiami [NAME]" (use the name they gave you)
- "Di dove sono?" or "Di quale città sono?" → "Sei di [CITY]" (use the city they mentioned)
- "Qual è il mio budget?" → "Il tuo budget è [AMOUNT]" (use the amount they stated)

### RETRIEVAL & MEMORY STRATEGY
1. **CHECK HISTORY FIRST**: Look at the CONVERSATION HISTORY below. If the user's question is answered there (e.g., "What is my name?" and they told you previously), ANSWER DIRECTLY using that information.
   - Do NOT call tools if the answer is already in the chat history.
   - Do NOT say "I don't know" if the user just told you.

2. **SEARCH IF NEEDED**: If the answer is NOT in history, use `vector_search` to find it in the knowledge base.

3. **COMPLIANCE SCOPE**: Apply strict compliance checks ONLY for legal/business advice. Do NOT apply them to personal facts (like the user's favorite color or name).

**EXAMPLE:**
User: "My secret word is PINEAPPLE."
You: "Got it, saved."
User: "What is my secret word?"
You: "It's PINEAPPLE." (Direct answer from history)

CRITICAL: The CONVERSATION HISTORY section contains previous messages. USE IT.

### RESPONSE FORMAT
- Provide COMPLETE, COMPREHENSIVE answers - do NOT truncate or cut short
- Use structured formatting (headers, bullet points, tables) for clarity
- For complex business/legal questions: include ALL relevant details, requirements, steps, and considerations
- Be thorough - users need actionable, complete information
"""
        prompt_parts.append(tools_block)

        # Build Final Prompt
        final_prompt = "\n\n".join(prompt_parts)

        # Cache for next time
        self._cache[cache_key] = (final_prompt, time.time())

        return final_prompt

    def check_greetings(self, query: str) -> str | None:
        """
        Check if query is a simple greeting that doesn't need RAG retrieval.

        Returns a friendly greeting response or None if not a greeting.
        This prevents unnecessary vector_search calls for simple greetings.

        Args:
            query: User query string

        Returns:
            Greeting response string or None

        Examples:
            >>> builder = SystemPromptBuilder()
            >>> response = builder.check_greetings("ciao")
            >>> assert response is not None
            >>> response = builder.check_greetings("hello")
            >>> assert response is not None
            >>> response = builder.check_greetings("What is KITAS?")
            >>> assert response is None
        """
        query_lower = query.lower().strip()

        # Simple greeting patterns (single word or very short)
        greeting_patterns = [
            r"^(ciao|hello|hi|hey|salve|buongiorno|buonasera|buon pomeriggio|good morning|good afternoon|good evening)$",
            r"^(ciao|hello|hi|hey|salve)\s*!*$",
            r"^(ciao|hello|hi|hey|salve)\s+(zan|zantara|there)$",
        ]

        # Check if query matches greeting patterns
        for pattern in greeting_patterns:
            if re.match(pattern, query_lower):
                # Return friendly greeting in detected language
                if any(
                    word in query_lower for word in ["ciao", "salve", "buongiorno", "buonasera"]
                ):
                    return "Ciao! Come posso aiutarti oggi?"
                else:
                    return "Hello! How can I help you today?"

        # Very short queries that are likely greetings
        if len(query_lower) <= 5 and query_lower in ["ciao", "hello", "hi", "hey", "salve"]:
            if query_lower in ["ciao", "salve"]:
                return "Ciao! Come posso aiutarti?"
            else:
                return "Hello! How can I help you?"

        return None

    def check_casual_conversation(self, query: str) -> bool:
        """
        Detect if query is a casual/lifestyle question that doesn't need RAG tools.

        Returns True if the query is casual (restaurants, music, personal, etc.)
        and should be answered directly without using vector_search or other tools.

        Args:
            query: User query string

        Returns:
            True if casual conversation, False otherwise
        """
        query_lower = query.lower().strip()

        # Business keywords that require RAG
        business_keywords = [
            "visa", "kitas", "kitap", "voa", "pt pma", "pt local", "pma", "kbli",
            "tax", "pajak", "pph", "ppn", "company", "business", "legal", "law",
            "regulation", "permit", "license", "contract", "notaris", "bank",
            "investment", "investor", "capital", "modal", "hukum", "peraturan",
            "undang", "izin", "akta", "npwp", "siup", "tdp", "nib", "oss",
            "immigration", "imigrasi", "sponsor", "rptka", "imta", "tenaga kerja",
            "how much", "quanto costa", "berapa", "pricing", "price", "harga",
            "deadline", "expire", "renewal", "extension", "perpanjang",
            # Team/organization keywords - require team_knowledge tool
            "ceo", "founder", "team", "tim", "anggota", "member", "staff",
            "chi è", "who is", "siapa", "direttore", "director", "manager",
            "bali zero", "zerosphere", "kintsugi"
        ]

        # Check if it's a business question
        for keyword in business_keywords:
            if keyword in query_lower:
                return False

        # Casual conversation patterns
        casual_patterns = [
            # Food/restaurants
            r"(ristorante|restaurant|makan|mangiare|food|cibo|warung|cafe|bar|dinner|lunch|breakfast|colazione|pranzo|cena)",
            # Music
            r"(music|musica|lagu|song|cantante|singer|band|concert|spotify|playlist)",
            # Weather/lifestyle
            r"(weather|cuaca|meteo|tempo|beach|pantai|spiaggia|surf|sunset|sunrise)",
            # Personal questions
            r"(come stai|how are you|apa kabar|gimana kabar|cosa fai|what do you do|che fai)",
            r"(preferisci|prefer|suka|like|favorite|favorito|best|migliore|consiglia|recommend)",
            # Hobbies/interests
            r"(hobby|hobi|sport|olahraga|travel|viaggio|movie|film|book|buku|libro)",
            # Places (non-business)
            r"(canggu|seminyak|ubud|uluwatu|kuta|sanur|nusa|gili)\s*(dinner|lunch|makan|restaurant|bar|cafe|beach|sunset)",
            # General chat
            r"(bali o jakarta|jakarta o bali|quale preferisci|which do you prefer)",
            r"(raccontami|tell me about yourself|parlami di te|cosa ti piace)",
            r"(che musica|what music|che tipo di|what kind of)"
        ]

        for pattern in casual_patterns:
            if re.search(pattern, query_lower):
                return True

        return False

    def check_identity_questions(self, query: str) -> str | None:
        """Check for identity questions and return hardcoded responses.

        Detects common identity/meta questions using regex patterns and returns
        pre-written answers to avoid unnecessary model calls and ensure consistent
        brand messaging.

        Patterns Detected:
        1. Identity questions: "Who are you?", "Chi sei?", "What are you?"
           -> Returns: AI assistant introduction
        2. Company questions: "What does Bali Zero do?", "Cosa fa Bali Zero?"
           -> Returns: Company services overview

        Args:
            query: User query string (case-insensitive matching)

        Returns:
            Hardcoded response string if pattern matches, None otherwise

        Note:
            - Fast path: Avoids model inference for meta questions
            - Brand consistency: Ensures uniform messaging about identity
            - Multilingual: Supports Italian and English patterns
            - Performance: ~0.1ms vs ~500ms for model call

        Example:
            >>> builder = SystemPromptBuilder()
            >>> response = builder.check_identity_questions("Chi sei?")
            >>> print(response)
            Sono Zantara, l'assistente AI di Bali Zero...
            >>> response = builder.check_identity_questions("What is KITAS?")
            >>> print(response)  # None - not an identity question
        """
        query_lower = query.lower().strip()

        # Identity patterns
        identity_patterns = [
            r"^(chi|who|cosa|what)\s+(sei|are)\s*(you|tu)?\??$",
            r"^(chi|who)\s+(è|is)\s+(zantara)\??$",
        ]

        for pattern in identity_patterns:
            if re.search(pattern, query_lower):
                return (
                    "Sono Zantara, l'assistente AI di Bali Zero. "
                    "Ti aiuto con visa, business, investimenti e questioni legali in Indonesia. "
                    "Come posso esserti utile oggi?"
                )

        # Company patterns
        company_patterns = [
            r"^(cosa|what)\s+(fa|does)\s+(bali\s*zero|balizero)(\s+do)?\??$",
            r"^(parlami|tell\s+me)\s+(di|about)\s+(bali\s*zero|balizero)\??$",
        ]

        for pattern in company_patterns:
            if re.search(pattern, query_lower):
                return (
                    "Bali Zero è una consulenza specializzata in visa, KITAS, setup aziendale (PT PMA) "
                    "e questioni legali per stranieri in Indonesia. Offriamo servizi trasparenti, "
                    "veloci e affidabili per aiutarti a vivere e lavorare a Bali senza stress."
                )

        return None