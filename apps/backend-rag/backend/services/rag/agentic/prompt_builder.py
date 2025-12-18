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
        self, user_id: str, context: dict[str, Any], query: str = "", deep_think_mode: bool = False
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

        # OPTIMIZATION: Check cache before building expensive prompt
        # Include facts count in cache key to invalidate when memory changes
        cache_key = f"{user_id}:{deep_think_mode}:{len(facts)}:{len(collective_facts)}:{len(timeline_summary)}"

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

        # Base Persona
        prompt_parts = [JAKSEL_PERSONA]

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

            identity_block = f"""
### CRITICAL: USER IDENTITY (YOU KNOW THIS PERSON)
**You are talking to:** {user_name}
**Role:** {user_role}
**Department:** {dept}
**Notes:** {notes}

**INSTRUCTIONS:**
1. You **KNOW** this person. DO NOT act like a stranger.
2. If asked "Chi sono?", answer with their name and role.
3. If they are 'Zero' (Founder), use "sacred semar energy" and respect.
4. If they are 'Zainal' (CEO), use extreme respect ("Bapak", "Pangeran").
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
        if query:
            # Detect language from query
            detected_language = detect_language(query)
            language_instruction = get_language_instruction(detected_language)
            prompt_parts.append(language_instruction)

            # Procedural question formatting
            if is_procedural_question(query):
                procedural_instruction = get_procedural_format_instruction(detected_language)
                prompt_parts.append(procedural_instruction)

            # Emotional content handling
            if has_emotional_content(query):
                emotional_instruction = get_emotional_response_instruction(detected_language)
                prompt_parts.append(emotional_instruction)

            # Explanation Level Detection (simple/expert/standard)
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
### AGENTIC RAG TOOLS

**PRICING QUESTIONS - ALWAYS USE get_pricing FIRST!**
If the user asks about PRICES, COSTS, FEES, "quanto costa", "berapa harga":
- ALWAYS call get_pricing FIRST to get OFFICIAL Bali Zero prices
- Format: ACTION: get_pricing(service_type="visa", query="E33G Digital Nomad")
- NEVER invent prices! Use ONLY prices from get_pricing tool

**DEEP DIVE / FULL DOCUMENT READING:**
If vector_search returns a result with an ID (e.g., "ID: UU-11-2020"), and you need to understand the FULL context or details not present in the snippet:
- Call database_query(search_term="UU-11-2020", query_type="by_id")
- This will retrieve the COMPLETE text of the document/law.
- Use this for complex legal analysis where snippets are insufficient.

**CURRENT 2024 VISA CODES:**
- "B211A" does NOT exist anymore since 2024! Use these codes instead:
  - E33G = Digital Nomad KITAS (1 year, remote work)
  - E28A = Investor KITAS (for business owners)
  - E33F = Retirement KITAS (age 60+)
  - E31A = Work KITAS (for employees)
  - VOA = Visa on Arrival (30 days, extendable)
  - D1 = Tourism Multiple Entry (5 years, 60 days/entry)
- Always clarify: "Il B211A non esiste più dal 2024, ora ci sono E33G, E28A, VOA, etc."

**For general info questions:**
1. Call vector_search to get documents
2. Use those documents to give a COMPLETE answer

Format (INTERNAL PROCESSING ONLY - DO NOT include in final answer):
```
THOUGHT: [what info do I need?]  <- This is for YOUR internal reasoning only
ACTION: get_pricing(service_type="visa", query="C1 tourism")
-- OR --
ACTION: vector_search(query="search terms", collection="collection_name")
-- OR --
ACTION: database_query(search_term="UU-11-2020", query_type="by_id")
```

IMPORTANT: The THOUGHT and ACTION lines above are for YOUR internal processing.
When providing the FINAL ANSWER to the user, DO NOT include these markers.

Collections:
- "kbli_unified" = PT PMA, business, KBLI, company
- "visa_oracle" = KITAS, KITAP, visas, immigration
- "tax_genius" = PPh, PPN, taxes
- "legal_unified" = general law, contracts
- "bali_zero_team" = Internal team info, SOPs

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
- **Keep your response under 4000 characters.**
- Be concise and direct.
- Use bullet points for lists.
"""
        prompt_parts.append(tools_block)

        # Build final prompt
        final_prompt = "\n\n".join(prompt_parts)

        # OPTIMIZATION: Cache the prompt for future use
        self._cache[cache_key] = (final_prompt, time.time())
        logger.debug(f"Cached system prompt for {user_id}")

        return final_prompt

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
