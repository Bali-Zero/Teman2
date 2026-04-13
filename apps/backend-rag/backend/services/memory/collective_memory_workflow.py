"""
LangGraph Workflow for Collective Memory
Gestisce memoria collettiva intelligente (work + personal) con workflow condizionali
"""

import logging
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)

# --- Name lists for regex-based NER ---
# Indonesian common first names (Balinese + Javanese + general)
_INDONESIAN_NAMES: set[str] = {
    # Balinese birth-order names
    "wayan", "made", "nyoman", "ketut", "putu", "kadek", "komang", "iluh", "gede", "luh",
    # Common Indonesian names
    "agung", "sari", "dewi", "adi", "budi", "rizki", "rizky", "putri", "ayu", "dewa",
    "bagus", "surya", "indra", "arya", "hendra", "eka", "dwi", "tri", "catur",
    "yoga", "dian", "rina", "sinta", "wahyu", "andi", "rudi", "yudi", "joko",
    "bambang", "widya", "widi", "febri", "nurul", "fajar", "bayu", "agus", "iwan",
    "dedi", "hari", "yanto", "tono", "wati", "yuni", "mega", "lina", "fitri",
    "nanda", "cahya", "ratna", "kusuma", "wisnu", "rama", "krisna", "dharma",
}

# Italian common first names
_ITALIAN_NAMES: set[str] = {
    "antonello", "maria", "giovanni", "luca", "sara", "marco", "giuseppe", "paolo",
    "anna", "francesca", "alessandro", "matteo", "andrea", "lorenzo", "chiara",
    "valentina", "simone", "davide", "federica", "roberto", "stefano", "cristina",
    "mario", "giulia", "elena", "fabio", "silvia", "carlo", "daniela", "claudio",
    "enrico", "barbara", "massimo", "laura", "giorgio", "angela", "vincenzo",
    "rosa", "pietro", "patrizia", "emanuele", "teresa", "alberto", "michela",
    "nicola", "lucia", "filippo", "monica", "riccardo", "serena",
}

# International common first names (English + common global)
_INTERNATIONAL_NAMES: set[str] = {
    "james", "john", "robert", "michael", "david", "william", "richard", "thomas",
    "mary", "jennifer", "linda", "elizabeth", "sarah", "jessica", "karen",
    "daniel", "matthew", "anthony", "mark", "paul", "steven", "andrew", "peter",
    "alex", "chris", "sam", "max", "ben", "nick", "tom", "jack", "kate", "emma",
    "sophie", "alice", "oliver", "henry", "grace", "lily", "leo", "mia", "noah",
    "muhammad", "ahmed", "ali", "omar", "hassan", "fatima", "aisha",
    "chen", "wei", "ming", "jin", "yuki", "kenji", "sakura", "kim", "lee",
}

_ALL_KNOWN_NAMES: set[str] = _INDONESIAN_NAMES | _ITALIAN_NAMES | _INTERNATIONAL_NAMES

# Titles and honorifics that precede names
_TITLE_PATTERN = r"(?:mr\.?|mrs\.?|ms\.?|dr\.?|prof\.?|pak|bu|ibu|bapak|mas|mbak|sig\.?|signor[ae]?)"

# Compiled regex: title-case words that could be names (2+ chars, not sentence-start common words)
_TITLECASE_RE = re.compile(
    r"(?<!\. )(?<=\s)" + r"([A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20}){0,3})",
)

# Words that are title-case but NOT names (common sentence starters, places, etc.)
_NON_NAME_WORDS: set[str] = {
    "the", "this", "that", "these", "those", "here", "there", "when", "where",
    "what", "which", "who", "how", "why", "today", "tomorrow", "yesterday",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "bali", "jakarta", "indonesia",
    "italy", "roma", "milano", "none", "true", "false", "null",
}


class MemoryCategory(str, Enum):
    WORK = "work"
    PERSONAL = "personal"
    RELATIONSHIP = "relationship"
    CULTURAL = "cultural"
    PREFERENCE = "preference"
    MILESTONE = "milestone"


class CollectiveMemoryState(TypedDict):
    # Input
    query: str
    user_id: str
    session_id: str
    participants: list[str]  # Chi è coinvolto nella conversazione

    # Analisi
    detected_category: MemoryCategory | None
    detected_type: str | None  # 'fact', 'preference', 'story', etc.
    extracted_entities: list[dict]  # Persone, luoghi, eventi menzionati
    sentiment: str | None  # 'positive', 'neutral', 'negative'
    importance_score: float
    personal_importance: float

    # Consolidamento
    existing_memories: list[dict]  # Memorie esistenti correlate
    needs_consolidation: bool
    consolidation_actions: list[str]

    # Relazioni
    relationships_to_update: list[dict]
    new_relationships: list[dict]

    # Output
    memory_to_store: dict | None
    relationships_to_store: list[dict]
    profile_updates: list[dict]

    # Metadati
    confidence: float
    errors: list[str]


def extract_person_names(text: str) -> list[str]:
    """Extract person names using regex-based NER.

    Supports Indonesian (Balinese birth-order + common), Italian,
    and international names via:
    1. Known-name dictionary lookup (case-insensitive word-boundary match)
    2. Title/honorific + name pattern (e.g. "Pak Wayan", "Sig. Rossi")
    3. Title-case multi-word sequences (filtered against non-name words)

    Args:
        text: Input text to scan for names.

    Returns:
        Deduplicated list of extracted names (title-cased).
    """
    if not text or not text.strip():
        return []

    found: dict[str, str] = {}  # lowercase -> display form

    # Strategy 1: Known-name dictionary with word-boundary matching
    text_lower = text.lower()
    for name in _ALL_KNOWN_NAMES:
        pattern = rf"\b{re.escape(name)}\b"
        if re.search(pattern, text_lower):
            found[name] = name.title()

    # Strategy 2: Title/honorific + following capitalized word(s)
    title_name_re = re.compile(
        rf"\b{_TITLE_PATTERN}\s+([A-Z][a-z]{{1,20}}(?:\s+[A-Z][a-z]{{1,20}}){{0,2}})",
        re.IGNORECASE,
    )
    for match in title_name_re.finditer(text):
        raw_name = match.group(1).strip()
        # Only keep words that are plausible names (known or title-case and short)
        words = raw_name.split()
        name_words = []
        for w in words:
            if w.lower() in _ALL_KNOWN_NAMES or (w[0].isupper() and len(w) <= 15):
                name_words.append(w)
            else:
                break  # Stop at first non-name word
        if name_words:
            name_part = " ".join(name_words)
            key = name_part.lower()
            if key not in _NON_NAME_WORDS:
                found[key] = name_part

    # Strategy 3: Title-case sequences not at sentence start
    for match in _TITLECASE_RE.finditer(text):
        candidate = match.group(1).strip()
        words = candidate.split()
        # Keep only words that are plausible names (not common English words)
        name_words = [w for w in words if w.lower() not in _NON_NAME_WORDS and len(w) > 1]
        if name_words:
            name = " ".join(name_words)
            key = name.lower()
            if key not in found:
                found[key] = name

    return list(found.values())


def merge_memories(existing: list[dict], new_content: str) -> dict:
    """Unifica memorie esistenti con nuovo contenuto"""
    if not existing:
        return {"content": new_content}

    # Prendi la memoria più recente come base
    latest = existing[0]
    return {
        "content": f"{latest.get('content', '')}\n{new_content}",
        "memory_key": latest.get("memory_key"),
        "updated": True,
    }


def detect_conflicts(existing: list[dict], new_content: str) -> list[str]:
    """Detect conflicts between existing memories and new content.

    Checks for:
    1. Key overlap — same memory_key with different content
    2. Semantic contradiction — negation patterns, opposing preferences
    3. Temporal conflicts — "now" vs "used to" contradictions

    Args:
        existing: List of existing memory dicts with 'content' and optional 'memory_key'.
        new_content: New content to check against existing memories.

    Returns:
        List of conflict description strings (empty if no conflicts).
    """
    if not existing or not new_content:
        return []

    conflicts: list[str] = []
    new_lower = new_content.lower().strip()

    # Antonym pairs that signal contradiction when one appears in each text.
    # Each tuple is (word_a, word_b) — if existing has word_a and new has word_b
    # (or vice versa), it's a contradiction.
    antonym_pairs = [
        ("piace", "non.*piace"), ("preferisco", "non.*preferisco"),
        ("amo", "odio"), ("voglio", "non.*voglio"),
        ("likes", "dislikes"), ("prefer", "don't prefer"),
        ("loves", "hates"), ("wants", "doesn't want"),
        ("always", "never"),
        ("suka", "tidak.*suka"), ("mau", "tidak.*mau"),  # Indonesian
    ]

    for mem in existing:
        existing_content = mem.get("content", "")
        if not existing_content:
            continue
        existing_lower = existing_content.lower().strip()

        # Check 1: Key overlap with different content
        mem_key = mem.get("memory_key")
        if mem_key and existing_lower != new_lower:
            # Same key, different value — likely an update/conflict
            from difflib import SequenceMatcher
            similarity = SequenceMatcher(None, existing_lower, new_lower).ratio()
            if 0.3 < similarity < 0.85:
                conflicts.append(
                    f"Key '{mem_key}' update: existing='{existing_content[:80]}' "
                    f"vs new='{new_content[:80]}' (similarity={similarity:.2f})"
                )

        # Check 2: Antonym/negation-based contradiction
        for word_a, word_b in antonym_pairs:
            a_in_existing = re.search(rf"\b{word_a}\b", existing_lower) is not None
            b_in_existing = re.search(rf"\b{word_b}", existing_lower) is not None
            a_in_new = re.search(rf"\b{word_a}\b", new_lower) is not None
            b_in_new = re.search(rf"\b{word_b}", new_lower) is not None
            if (a_in_existing and b_in_new) or (b_in_existing and a_in_new):
                conflicts.append(
                    f"Contradiction detected: '{existing_content[:60]}' "
                    f"vs '{new_content[:60]}' (antonyms: {word_a}/{word_b})"
                )
                break

        # Check 3: Temporal contradiction ("now X" vs "used to X")
        temporal_new = any(w in new_lower for w in ["adesso", "ora", "now", "currently", "sekarang"])
        temporal_old = any(
            w in existing_lower for w in ["prima", "una volta", "used to", "formerly", "dulu"]
        )
        if temporal_new and temporal_old:
            # Both talk about time — check if they share key nouns
            new_words = set(new_lower.split())
            old_words = set(existing_lower.split())
            shared = new_words & old_words - {"a", "the", "di", "da", "in", "e", "il", "la", "yang", "dan"}
            if len(shared) >= 2:
                conflicts.append(
                    f"Temporal conflict: past='{existing_content[:60]}' "
                    f"vs present='{new_content[:60]}'"
                )

    return conflicts


def extract_preferences(text: str) -> dict[str, str]:
    """Extract user preferences from text across multiple categories.

    Categories: food/drink, communication style, work hours, language,
    meeting format, work environment, tools.

    Supports Italian, English, and Indonesian preference expressions.

    Args:
        text: Input text to scan for preferences.

    Returns:
        Dict mapping preference category to detected value.
    """
    if not text:
        return {}

    preferences: dict[str, str] = {}
    text_lower = text.lower()

    # Preference trigger patterns (Italian + English + Indonesian)
    has_preference = any(
        w in text_lower
        for w in [
            "preferisco", "preferisce", "mi piace", "gli piace", "le piace",
            "amo", "adoro", "odio", "detesto", "meglio",
            "prefer", "like", "love", "hate", "enjoy", "rather", "favorite", "favourite",
            "suka", "lebih suka", "senang", "benci", "favorit",
        ]
    )

    if not has_preference:
        return preferences

    # --- Food & Drink ---
    drink_map = {
        "espresso": "espresso", "americano": "americano", "cappuccino": "cappuccino",
        "latte": "latte", "macchiato": "macchiato", "tè": "tea", "tea": "tea",
        "kopi": "coffee", "coffee": "coffee", "matcha": "matcha", "jus": "juice",
    }
    for keyword, value in drink_map.items():
        if keyword in text_lower:
            preferences["drink"] = value
            break

    food_map = {
        "vegetariano": "vegetarian", "vegetarian": "vegetarian", "vegan": "vegan",
        "halal": "halal", "kosher": "kosher", "pesce": "pescatarian",
        "pizza": "pizza", "pasta": "pasta", "nasi": "rice-based",
        "sushi": "sushi", "spicy": "spicy food", "piccante": "spicy food",
        "pedas": "spicy food", "dolce": "sweet food", "manis": "sweet food",
    }
    for keyword, value in food_map.items():
        if keyword in text_lower:
            preferences["food"] = value
            break

    # --- Communication Style ---
    comm_patterns = {
        "email": ["email", "e-mail", "mail"],
        "whatsapp": ["whatsapp", "wa", "chat"],
        "telegram": ["telegram", "tg"],
        "phone": ["telefono", "telefonata", "phone", "call", "telepon"],
        "video_call": ["video", "zoom", "meet", "teams"],
        "in_person": ["di persona", "faccia a faccia", "in person", "face to face", "tatap muka"],
        "text": ["messaggio", "sms", "message", "pesan"],
    }
    for style, keywords in comm_patterns.items():
        if any(k in text_lower for k in keywords):
            preferences["communication"] = style
            break

    # --- Work Hours ---
    work_patterns = {
        "morning": ["mattina", "presto", "morning", "early", "pagi"],
        "afternoon": ["pomeriggio", "afternoon", "siang", "sore"],
        "evening": ["sera", "tardi", "evening", "late", "malam"],
        "flexible": ["flessibile", "flexible", "fleksibel"],
        "nine_to_five": ["9-5", "nine to five", "orario ufficio", "jam kantor"],
    }
    for schedule, keywords in work_patterns.items():
        if any(k in text_lower for k in keywords):
            preferences["work_hours"] = schedule
            break

    # --- Language Preference ---
    lang_patterns = {
        "italian": ["italiano", "italian", "italia"],
        "english": ["inglese", "english", "inggris"],
        "indonesian": ["indonesiano", "bahasa", "indonesian"],
        "japanese": ["giapponese", "japanese", "jepang"],
        "chinese": ["cinese", "chinese", "mandarin"],
    }
    for lang, keywords in lang_patterns.items():
        if any(k in text_lower for k in keywords):
            preferences["language"] = lang
            break

    # --- Meeting Format --- (check longer patterns first to avoid substring false positives)
    meeting_patterns = [
        ("informal", ["informale", "informali", "informal", "casual", "rilassato", "santai"]),
        ("formal", ["formale", "formali", " formal", "structured", "strutturato"]),
        ("brief", ["breve", "quick", "brief", "short", "corto", "singkat"]),
        ("detailed", ["dettagliato", "detailed", "thorough", "approfondito", "rinci"]),
        ("async", ["asincrono", "async", "asynchronous", "no meeting"]),
    ]
    for fmt, keywords in meeting_patterns:
        if any(k in text_lower for k in keywords):
            preferences["meeting_format"] = fmt
            break

    return preferences


def _has_word(query: str, words: list[str]) -> bool:
    """Check if any word appears as a whole word in the query (word-boundary match)."""
    for word in words:
        if re.search(rf"\b{re.escape(word)}\b", query):
            return True
    return False


async def analyze_content_intent(state: CollectiveMemoryState) -> CollectiveMemoryState:
    """Analyze intent and categorize the memory content.

    Uses word-boundary matching to avoid false positives from substrings
    (e.g. "amo" should not match inside "dobbiamo").
    """
    query = state["query"].lower()

    # Rileva categoria (word-boundary matching to avoid substring false positives)
    if _has_word(query, ["preferisco", "preferisce", "mi piace", "non mi piace", "amo", "odio"]):
        state["detected_category"] = MemoryCategory.PREFERENCE
    elif _has_word(query, ["compleanno", "anniversario", "festa", "celebrazione"]):
        state["detected_category"] = MemoryCategory.MILESTONE
    elif _has_word(
        query, ["amicizia", "conosco", "incontri", "incontrato", "social", "amico"],
    ):
        state["detected_category"] = MemoryCategory.RELATIONSHIP
    elif _has_word(query, ["cultura", "tradizione", "costume", "locale"]):
        state["detected_category"] = MemoryCategory.CULTURAL
    else:
        state["detected_category"] = MemoryCategory.WORK

    # Rileva tipo
    if state["detected_category"] == MemoryCategory.PREFERENCE:
        state["detected_type"] = "preference"
    elif state["detected_category"] == MemoryCategory.MILESTONE:
        state["detected_type"] = "milestone"
    else:
        state["detected_type"] = "fact"

    return state


def _extract_entity_mentions(text: str) -> list[dict[str, str]]:
    """Extract typed entity mentions from text (persons, locations, organizations).

    Uses pattern matching — not a full NER model, but covers common patterns
    across Italian, English, and Indonesian.

    Extraction order: organizations (most specific pattern), locations
    (preposition + capitalized), then persons (catch-all names).
    Earlier matches take priority via the seen set.

    Args:
        text: Input text.

    Returns:
        List of dicts with 'name', 'type', 'source' keys.
    """
    entities: list[dict[str, str]] = []
    seen: set[str] = set()

    # Organizations first — look for common suffixes (most specific pattern)
    org_re = re.compile(
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+"
        r"(?:Ltd|LLC|Inc|SRL|PT|CV|Corp|GmbH|SpA|SA|Srl)\b",
    )
    for match in org_re.finditer(text):
        org = match.group(0).strip()
        key = org.lower()
        if key not in seen:
            seen.add(key)
            # Also mark individual words as seen to prevent person extraction
            for word in org.split():
                seen.add(word.lower())
            entities.append({"name": org, "type": "organization", "source": "pattern"})

    # Locations second — "in/a/di/ke + Capitalized" (preposition signals location)
    loc_re = re.compile(
        r"\b(?:in|a|di|da|ke|dari|near|at)\s+([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2})\b",
    )
    for match in loc_re.finditer(text):
        loc = match.group(1).strip()
        key = loc.lower()
        if key not in seen and key not in _NON_NAME_WORDS:
            seen.add(key)
            entities.append({"name": loc, "type": "location", "source": "pattern"})

    # Persons last — from name extraction (catch-all)
    for name in extract_person_names(text):
        key = name.lower()
        if key not in seen:
            seen.add(key)
            entities.append({"name": name, "type": "person", "source": "name_extraction"})

    return entities


async def extract_entities_and_relationships(state: CollectiveMemoryState) -> CollectiveMemoryState:
    """Extract entities (persons, locations, orgs) and infer relationships.

    Uses local pattern-based extraction. Falls back to user_id if no
    participants are found.
    """
    query = state["query"]

    # Extract person names as participants
    participants = extract_person_names(query)
    if not participants and state.get("user_id"):
        participants = [state["user_id"]]

    state["participants"] = participants

    # Extract all entity types
    state["extracted_entities"] = _extract_entity_mentions(query)

    # Infer relationships between co-mentioned persons
    person_entities = [e for e in state["extracted_entities"] if e["type"] == "person"]
    new_relationships: list[dict[str, Any]] = []
    for i, ent_a in enumerate(person_entities):
        for ent_b in person_entities[i + 1:]:
            new_relationships.append({
                "entity_a": ent_a["name"],
                "entity_b": ent_b["name"],
                "relationship_type": "co_mentioned",
                "context": query[:120],
            })
    state["new_relationships"] = new_relationships

    return state


async def check_existing_memories(
    state: CollectiveMemoryState,
    memory_service: Any | None,
) -> CollectiveMemoryState:
    """Check for existing memories related to the new content.

    Uses the memory service to:
    1. Search for similar facts by text (ILIKE)
    2. Check user-specific memory for key overlap
    3. Flag consolidation if overlapping memories found

    Args:
        state: Current workflow state.
        memory_service: MemoryServicePostgres instance (or None).

    Returns:
        Updated state with existing_memories and needs_consolidation.
    """
    state["existing_memories"] = []
    state["needs_consolidation"] = False

    if not memory_service:
        return state

    query = state["query"]
    user_id = state.get("user_id", "")

    try:
        # Strategy 1: Text similarity search across all memories
        similar_facts = await memory_service.search(query, limit=5)
        if similar_facts:
            state["existing_memories"] = [
                {
                    "content": fact.get("fact", fact.get("content", "")),
                    "user_id": fact.get("user_id", ""),
                    "confidence": fact.get("confidence", 0.5),
                    "memory_key": fact.get("fact_type", None),
                }
                for fact in similar_facts
            ]

        # Strategy 2: User-specific memory lookup
        if user_id:
            user_memory = await memory_service.get_memory(user_id, force_refresh=False)
            if user_memory and user_memory.profile_facts:
                query_lower = query.lower()
                for fact in user_memory.profile_facts:
                    fact_lower = fact.lower()
                    # Check for keyword overlap (shared meaningful words)
                    query_words = {
                        w for w in query_lower.split() if len(w) > 3
                    }
                    fact_words = {
                        w for w in fact_lower.split() if len(w) > 3
                    }
                    overlap = query_words & fact_words
                    if len(overlap) >= 2:
                        state["existing_memories"].append({
                            "content": fact,
                            "user_id": user_id,
                            "confidence": 0.7,
                            "memory_key": "profile_fact",
                        })

        # Flag consolidation if we found overlapping memories
        if state["existing_memories"]:
            state["needs_consolidation"] = True
            logger.info(
                f"Found {len(state['existing_memories'])} existing memories "
                f"for consolidation (user={user_id})",
            )

    except Exception as e:
        logger.warning(f"Error checking existing memories: {e}")
        # Non-fatal: proceed with empty existing_memories

    return state


async def categorize_memory(state: CollectiveMemoryState) -> CollectiveMemoryState:
    """Categorizza memoria (già fatto in analyze_content_intent)"""
    return state


async def assess_personal_importance(state: CollectiveMemoryState) -> CollectiveMemoryState:
    """Assess personal importance factoring in category, participant count, and content signals.

    Importance calculation:
    - Base score from category (milestone=0.9, relationship=0.8, etc.)
    - Participant boost: more people involved = higher social importance
    - Content length boost: longer content likely carries more detail
    - Conflict boost: conflicting memories need attention
    """
    category = state["detected_category"]
    participant_count = len(state["participants"])

    # Base importance by category
    category_scores: dict[MemoryCategory | None, float] = {
        MemoryCategory.MILESTONE: 0.9,
        MemoryCategory.RELATIONSHIP: 0.8,
        MemoryCategory.CULTURAL: 0.75,
        MemoryCategory.PREFERENCE: 0.6,
        MemoryCategory.PERSONAL: 0.65,
        MemoryCategory.WORK: 0.5,
    }
    importance = category_scores.get(category, 0.5)

    # Participant boost: +0.05 per additional participant (max +0.15)
    if participant_count > 1:
        participant_boost = min((participant_count - 1) * 0.05, 0.15)
        importance += participant_boost

    # Content richness boost: longer content = more detail = more important
    content_len = len(state.get("query", ""))
    if content_len > 200:
        importance += 0.05
    elif content_len > 500:
        importance += 0.1

    # Conflict boost: existing conflicts demand attention
    if state.get("consolidation_actions"):
        importance += 0.1

    # Cap at 1.0
    importance = min(importance, 1.0)

    state["importance_score"] = importance
    # Personal importance gets a social-context multiplier based on participants
    personal_multiplier = 1.0 + (0.1 * min(participant_count, 3))
    state["personal_importance"] = min(importance * personal_multiplier, 1.0)

    return state


async def consolidate_with_existing(state: CollectiveMemoryState) -> CollectiveMemoryState:
    """Consolida con memorie esistenti"""
    existing = state["existing_memories"]
    new_content = state["query"]

    if existing:
        consolidated = merge_memories(existing, new_content)
        conflicts = detect_conflicts(existing, new_content)

        if conflicts:
            state["consolidation_actions"].append(f"Conflict detected: {conflicts}")

        state["memory_to_store"] = consolidated
    else:
        state["memory_to_store"] = {"content": new_content}

    return state


async def update_team_relationships(state: CollectiveMemoryState) -> CollectiveMemoryState:
    """Aggiorna relazioni tra membri del team"""
    participants = state["participants"]
    category = state["detected_category"]

    if len(participants) >= 2 and category in [
        MemoryCategory.RELATIONSHIP,
        MemoryCategory.MILESTONE,
    ]:
        for i, member_a in enumerate(participants):
            for member_b in participants[i + 1 :]:
                relationship = {
                    "member_a": member_a,
                    "member_b": member_b,
                    "relationship_type": (
                        "friendship" if category == MemoryCategory.RELATIONSHIP else "social"
                    ),
                    "last_interaction": datetime.now(tz=timezone.utc).isoformat(),
                }
                state["relationships_to_update"].append(relationship)

    return state


async def update_member_profiles(state: CollectiveMemoryState) -> CollectiveMemoryState:
    """Aggiorna profili personali dei membri"""
    if state["detected_category"] == MemoryCategory.PREFERENCE:
        preferences = extract_preferences(state["query"])
        for participant in state["participants"]:
            state["profile_updates"].append({"member_id": participant, "preferences": preferences})

    return state


async def store_collective_memory(
    state: CollectiveMemoryState, memory_service,
) -> CollectiveMemoryState:
    """Salva memoria collettiva"""
    if state["memory_to_store"] and memory_service:
        try:
            content = state["memory_to_store"].get("content")
            user_id = state.get("user_id")

            if content and user_id:
                # Save as fact
                await memory_service.add_fact(user_id, content, fact_type="collective_memory")
                logger.info(f"💾 Stored collective memory fact for {user_id}: {content}")

                # Also update summary if needed (simplified logic)
                # In a real scenario, we'd append to summary or re-summarize
                # await memory_service.update_summary(user_id, content)

        except Exception as e:
            logger.error(f"❌ Failed to store collective memory: {e}")
            # Add error to state for tracking
            if "errors" not in state:
                state["errors"] = []
            state["errors"].append(str(e))

    return state


def route_by_existence(state: CollectiveMemoryState) -> str:
    """Routing basato su esistenza memorie"""
    if state["needs_consolidation"]:
        return "consolidate"
    if state["existing_memories"]:
        return "exists"
    return "new"


def route_by_importance(state: CollectiveMemoryState) -> str:
    """Routing basato su importanza"""
    if state["personal_importance"] >= 0.8:
        return "high"
    if state["personal_importance"] >= 0.6:
        return "medium"
    return "low"


def create_collective_memory_workflow(memory_service: Any = None, _mcp_client: Any = None) -> Any:
    """Crea workflow LangGraph per memoria collettiva intelligente"""

    workflow = StateGraph(CollectiveMemoryState)

    # Wrappers for dependency injection
    async def check_existing_wrapper(state) -> Any:
        return await check_existing_memories(state, memory_service)

    async def store_memory_wrapper(state) -> Any:
        return await store_collective_memory(state, memory_service)

    # NODES
    workflow.add_node("analyze_content", analyze_content_intent)
    workflow.add_node("extract_entities", extract_entities_and_relationships)
    workflow.add_node("check_existing", check_existing_wrapper)
    workflow.add_node("categorize", categorize_memory)
    workflow.add_node("assess_importance", assess_personal_importance)
    workflow.add_node("consolidate", consolidate_with_existing)
    workflow.add_node("update_relationships", update_team_relationships)
    workflow.add_node("update_profiles", update_member_profiles)
    workflow.add_node("store_memory", store_memory_wrapper)

    # FLOW
    workflow.set_entry_point("analyze_content")

    workflow.add_edge("analyze_content", "extract_entities")
    workflow.add_edge("extract_entities", "check_existing")

    workflow.add_conditional_edges(
        "check_existing",
        route_by_existence,
        {"new": "categorize", "exists": "consolidate", "consolidate": "consolidate"},
    )

    workflow.add_edge("categorize", "assess_importance")
    workflow.add_edge("consolidate", "assess_importance")
    workflow.add_edge("assess_importance", "update_relationships")

    workflow.add_conditional_edges(
        "update_relationships",
        route_by_importance,
        {"high": "update_profiles", "medium": "store_memory", "low": "store_memory"},
    )

    workflow.add_edge("update_profiles", "store_memory")
    workflow.add_edge("store_memory", END)

    return workflow.compile()
