import logging
import re

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# ============================================================================
# OUT-OF-DOMAIN DETECTION
# ============================================================================

# These four strings were ITALIAN-ONLY until 2026-08-10, on a gate that fires
# BEFORE retrieval on every channel: an English or Indonesian client asking a
# blocked question read a refusal in a language they had not written in.
#
# `{company}` is filled at call time, so a test can move COMPANY_NAME without
# re-importing this module.
#
# WHY A SECOND TABLE AND NOT `_reasoning_stubs.STUB_MESSAGES`: that module is the
# refusal-copy SSOT and would be the right home, but `cleaner` cannot import it.
# `query_gates` imports THIS module, and reaching `backend.services.rag.agentic.
# _reasoning_stubs` executes that package's `__init__`, which pulls the
# orchestrator and lands back here mid-import. So the COPY is duplicated by
# necessity while the LANGUAGE SET is not: `test_out_of_domain_language_coverage`
# imports `PROTOCOL_LANGUAGES` from that same SSOT and derives the detector's
# vocabulary from its AST, exactly as the stub table's own test does. Adding a
# language to `detect_query_language` fails both tables or neither.
_OUT_OF_DOMAIN_BY_LANGUAGE: dict[str, dict[str, str]] = {
    "personal_data": {
        "ITALIAN": (
            "Non ho accesso a dati personali di terze persone come codici fiscali, "
            "numeri di telefono o indirizzi privati. Posso aiutarti con informazioni "
            "su visa, business setup o questioni legali in Indonesia?"
        ),
        "ENGLISH": (
            "I don't have access to other people's personal data — tax codes, phone "
            "numbers or private addresses. I can help with visas, business setup or "
            "legal questions in Indonesia. What do you need?"
        ),
        "INDONESIAN": (
            "Saya tidak punya akses ke data pribadi orang lain seperti NPWP, nomor "
            "telepon, atau alamat pribadi. Saya bisa bantu soal visa, pendirian usaha, "
            "atau pertanyaan hukum di Indonesia. Ada yang bisa saya bantu?"
        ),
        "RUSSIAN": (
            "У меня нет доступа к персональным данным третьих лиц — налоговым номерам, "
            "телефонам или домашним адресам. Могу помочь с визами, открытием компании "
            "или юридическими вопросами в Индонезии. Что вас интересует?"
        ),
        "UKRAINIAN": (
            "Я не маю доступу до персональних даних третіх осіб — податкових номерів, "
            "телефонів чи домашніх адрес. Можу допомогти з візами, відкриттям компанії "
            "або юридичними питаннями в Індонезії. Що вас цікавить?"
        ),
    },
    "realtime_info": {
        "ITALIAN": (
            "Non ho accesso a informazioni in tempo reale come meteo, news o risultati sportivi. "
            "Per queste informazioni ti consiglio di consultare fonti aggiornate. "
            "Posso invece aiutarti con visa, KITAS, o business in Indonesia?"
        ),
        "ENGLISH": (
            "I don't have access to live figures like market prices or exchange rates — "
            "I'd be quoting a number I cannot verify. For those, check a live source. "
            "I can help with visas, KITAS or doing business in Indonesia instead."
        ),
        "INDONESIAN": (
            "Saya tidak punya akses ke angka real-time seperti harga pasar atau kurs — "
            "saya akan menyebut angka yang tidak bisa saya verifikasi. Untuk itu, silakan "
            "cek sumber langsung. Saya bisa bantu soal visa, KITAS, atau usaha di Indonesia."
        ),
        "RUSSIAN": (
            "У меня нет доступа к данным в реальном времени — котировкам или курсам валют: "
            "я назвал бы цифру, которую не могу проверить. Для этого лучше смотреть "
            "актуальный источник. А с визами, KITAS или бизнесом в Индонезии — помогу."
        ),
        "UKRAINIAN": (
            "Я не маю доступу до даних у реальному часі — котирувань чи курсів валют: "
            "я назвав би цифру, яку не можу перевірити. Для цього краще дивитися "
            "актуальне джерело. А з візами, KITAS чи бізнесом в Індонезії — допоможу."
        ),
    },
    "off_topic": {
        "ITALIAN": (
            "Questo argomento è fuori dalla mia area di competenza. Sono Zantara, "
            "l'assistente AI di {company}, specializzato in visa, immigrazione, "
            "setup aziendale (PT PMA) e questioni legali per stranieri in Indonesia. "
            "Come posso aiutarti in questi ambiti?"
        ),
        "ENGLISH": (
            "That one is outside what I work on. I'm Zantara, the AI assistant at "
            "{company}: visas, immigration, company setup (PT PMA) and legal matters "
            "for foreigners in Indonesia. Anything there I can help with?"
        ),
        "INDONESIAN": (
            "Topik itu di luar bidang saya. Saya Zantara, asisten AI dari {company}: "
            "visa, imigrasi, pendirian perusahaan (PT PMA), dan urusan hukum untuk "
            "orang asing di Indonesia. Ada yang bisa saya bantu di situ?"
        ),
        "RUSSIAN": (
            "Эта тема вне моей области. Я Zantara, AI-ассистент {company}: визы, "
            "иммиграция, регистрация компании (PT PMA) и юридические вопросы для "
            "иностранцев в Индонезии. Могу чем-то помочь в этих темах?"
        ),
        "UKRAINIAN": (
            "Ця тема поза моєю сферою. Я Zantara, AI-асистент {company}: візи, "
            "імміграція, реєстрація компанії (PT PMA) та юридичні питання для "
            "іноземців в Індонезії. Чи можу допомогти в цих темах?"
        ),
    },
    "unknown": {
        "ITALIAN": (
            "Non ho informazioni specifiche su questo argomento. "
            "Posso aiutarti con visa, KITAS, setup PT PMA/Lokal, "
            "o altre questioni business in Indonesia?"
        ),
        "ENGLISH": (
            "I don't have specific information on that. I can help with visas, KITAS, "
            "setting up a PT PMA or a local PT, and other business matters in Indonesia."
        ),
        "INDONESIAN": (
            "Saya tidak punya informasi spesifik soal itu. Saya bisa bantu soal visa, "
            "KITAS, pendirian PT PMA atau PT lokal, dan urusan usaha lain di Indonesia."
        ),
        "RUSSIAN": (
            "По этой теме у меня нет конкретной информации. Могу помочь с визами, KITAS, "
            "регистрацией PT PMA или локальной PT и другими бизнес-вопросами в Индонезии."
        ),
        "UKRAINIAN": (
            "З цієї теми в мене немає конкретної інформації. Можу допомогти з візами, "
            "KITAS, реєстрацією PT PMA чи локальної PT та іншими бізнес-питаннями в Індонезії."
        ),
    },
}


def get_out_of_domain_response(reason: str, language: str = "ITALIAN") -> str:
    """Refusal copy for ``reason``, in ``language``.

    Fallback order mirrors ``get_localized_stub``: requested language → ENGLISH →
    the ``unknown`` refusal. An unmapped language degrading to ENGLISH is
    deliberate and declared; an unmapped language degrading to ITALIAN — which is
    what shipping the raw table did — is not.
    """
    by_language = _OUT_OF_DOMAIN_BY_LANGUAGE.get(reason) or _OUT_OF_DOMAIN_BY_LANGUAGE["unknown"]
    text = by_language.get(language) or by_language["ENGLISH"]
    return text.format(company=settings.COMPANY_NAME)


#: Back-compat: the Italian column, formatted, under the name callers already
#: import. Derived, never re-typed — a second copy of this copy would drift.
OUT_OF_DOMAIN_RESPONSES = {
    reason: get_out_of_domain_response(reason, "ITALIAN") for reason in _OUT_OF_DOMAIN_BY_LANGUAGE
}


# Capitalised words that are NOT people. The cost of a missing entry here is a
# polite refusal on a rare phrasing — the safe direction; the cost of not having
# the distinction at all was measured on 2026-08-10 as 6 legitimate business
# questions blocked out of 9.
_NON_PERSON_CAPITALS = frozenset(
    {
        # legal forms and documents
        "pt",
        "cv",
        "pma",
        "pmdn",
        "kitas",
        "kitap",
        "kbli",
        "npwp",
        "nib",
        "oss",
        "bpjs",
        "lkpm",
        "spt",
        "voa",
        "nomor",
        "no",
        # places
        "bali",
        "indonesia",
        "denpasar",
        "jakarta",
        "badung",
        "gianyar",
        "ubud",
        "canggu",
        "kerobokan",
        "seminyak",
        # institutions and counterparties
        "societa",
        "società",
        "azienda",
        "impresa",
        "company",
        "office",
        "ufficio",
        "kantor",
        "immigration",
        "immigrazione",
        "imigrasi",
        "tribunale",
        "court",
        "pengadilan",
        "notaio",
        "notary",
        "notaris",
        "banca",
        "bank",
        "consolato",
        "consulate",
        "ambasciata",
        "embassy",
        "agenzia",
        "agency",
        "ministero",
        "ministry",
        "kementerian",
        "bkpm",
        "kemenkumham",
        "zero",
    }
)

# An explicit third-party PERSON. `sindaco/presidente/ministro` keep the older
# rule's intent; the rest are how a real request for someone else's data reads.
_PERSON_REFERENCE_RE = re.compile(
    r"\b(sig\.?|signor[ae]?|mr\.?|mrs\.?|ms\.?|"
    r"(?:il |la )?(?:mio|mia|tuo|tua|suo|sua|nostro|nostra|vostro|vostra)\s+client[ei]|"
    r"(?:your|my|his|her|their)\s+client|"
    r"un cliente|qualcuno|someone|somebody|"
    r"sindaco|presidente|ministro)\b"
)

_TITLECASE_TOKEN_RE = re.compile(r"\b([A-Z][a-zà-ÿ]{2,})\b")


def _names_a_person(query: str, object_start: int) -> bool:
    """True when the OBJECT of "<attribute> of <object>" is a natural person.

    This is the entity test the old patterns lacked. They matched
    ``indirizzo (di|del|della) \\w+`` and so refused "l'indirizzo della società
    registrata" and "the phone number of the immigration office" as third-party
    personal data, while "il codice fiscale di Mario Rossi" — the only shape the
    rule exists for — matched for exactly the same reason.

    Two independent signals, either is enough:
      * an explicit person reference anywhere in the query ("il mio cliente",
        "mr", "il sindaco");
      * a Title-cased token IN THE OBJECT that is not a known institution,
        place, legal form or document.

    ``object_start`` is not a detail: the first pass of this cure scanned the
    WHOLE query for capitals and blocked 12 of 14 legitimate questions, because
    the first word of a sentence is capitalised too — a second form-test dressed
    up as an entity test. The window therefore begins at the object and stops at
    the end of the clause, so a capitalised word in a following sentence
    ("…della società? Grazie Zantara") cannot vote either.

    Case is read from the ORIGINAL text, never from ``.lower()``: `PT PMA`,
    `CV` and `LKPM` are all-caps acronyms and never match `[A-Z][a-zà-ÿ]{2,}`.

    Declared limit: a capitalised institution nobody listed in
    ``_NON_PERSON_CAPITALS`` still reads as a person. That fails toward the
    refusal, which is the direction to fail in.
    """
    if _PERSON_REFERENCE_RE.search(query.lower()):
        return True
    clause = re.split(r"[?.!\n;]", query[object_start:], maxsplit=1)[0]
    return any(
        token.lower() not in _NON_PERSON_CAPITALS for token in _TITLECASE_TOKEN_RE.findall(clause)
    )


def is_out_of_domain(query: str) -> tuple[bool, str | None]:
    """
    Check if query is outside Zantara's domain of expertise.
    """
    query_lower = query.lower()

    # Personal data of third parties.
    #
    # The shape is necessary but NOT sufficient: these patterns describe
    # "<attribute> of <object>", and whether that is a privacy question depends
    # entirely on what the object IS. Superscar #3 — the guard has to name the
    # entity, not the form. `_names_a_person` is the second half of the test and
    # the default without it is PASSTHROUGH, so a business question reaches
    # retrieval instead of a canned Italian refusal.
    #
    # The group is the OBJECT — the thing whose data is being asked for. It is
    # what `_names_a_person` reads; the surrounding shape only says WHERE to look.
    personal_data_patterns = [
        r"codice fiscale (?:di|del|della|dello) (\w+)",
        r"numero (?:di )?telefono (?:di|del|della) (\w+)",
        r"indirizzo (?:di|del|della) (\w+)",
        r"email (?:di|del|della) (\w+)",
        r"tax (?:code|id|number) of (\w+)",
        r"phone number of (\w+)",
    ]

    for pattern in personal_data_patterns:
        # Matched on the ORIGINAL string so `match.start(1)` indexes the text
        # whose capitalisation `_names_a_person` reads.
        match = re.search(pattern, query, re.IGNORECASE)
        if match and _names_a_person(query, match.start(1)):
            return True, "personal_data"

    # Real-time FINANCIAL information (blocked - cannot verify)
    # NOTE: Weather, news, tourism info are NOW ALLOWED - handled by web_search tool
    realtime_financial_patterns = [
        r"stock price",
        r"bitcoin price",
        r"crypto (price|value)",
        r"forex (rate|exchange)",
    ]

    for pattern in realtime_financial_patterns:
        if re.search(pattern, query_lower):
            return True, "realtime_info"

    # NOTE: off_topic patterns REMOVED (2026-01-28)
    # Gemini 3 is now allowed to answer ANY question, not just business-related.
    # This allows users to leverage the full power of the LLM while still using
    # RAG for Tier 1 (business-specific) queries.
    # Previous patterns blocked: ricetta, calcio, film, canzone, politica, poesia, gossip, oroscopo

    # Questions about people's personal info
    if re.search(r"(sindaco|presidente|ministro) di", query_lower):
        if any(term in query_lower for term in ["codice", "telefono", "indirizzo", "email"]):
            return True, "personal_data"

    return False, None


def clean_response(response: str) -> str:
    """
    Remove internal reasoning patterns from user-facing response.

    Filters out THOUGHT leaks, observation statements, and generic philosophical
    reasoning that should not be exposed to users.

    Args:
        response: Raw response from LLM

    Returns:
        Cleaned response without internal reasoning patterns
    """
    if not response:
        return ""

    patterns = [
        # Remove "Okay, since/with/given..." patterns
        r"^Okay[,.]?\s*(since|with|given|without|lacking|based|in the absence)[^.]*observation[^.]*\.\s*",
        r"^Okay[,.]?\s*(based|since|with|given|without|lacking)[^.]*prior (information|context)[^.]*\.\s*",
        r"^Okay[,.]?\s*(based|since|with|given|without|lacking)[^.]*context[^.]*\.\s*",
        r"^Okay[,.]?\s*(based|since|with|given|without|lacking)[^.]*input[^.]*\.\s*",
        r"^Okay[,.]?\s*I need to (either|understand|consider)[^.]*\.\s*",
        r"^Okay[,.]?\s*Given the (observation|lack)[^.]*\.\s*",
        # Remove entire "Okay. Based/Given/Without..." sentences at start (non-greedy)
        r"^Okay\.\s*[A-Z][^.]*?(observation|context|information)[^.]*\.\s*",
        # Remove "solicit input" patterns
        r"[Mm]y next thought is to solicit input[^.]*\.\s*",
        r"[Ss]olicit input to understand[^.]*\.\s*",
        r"[Pp]rovide me with some context[^.]*\.\s*",
        # Remove THOUGHT: markers (case-insensitive)
        r"^THOUGHT:.*?\n",
        r"^THOUGHT\s*:.*?\n",
        r"^Thought:.*?\n",
        r"^Thought\s*:.*?\n",
        # Remove Observation: markers (case-insensitive)
        r"^Observation:.*?\n",
        r"^Observation\s*:.*?\n",
        # Remove stub responses
        r"Zantara has provided the final answer\.?\s*",
        r"ZANTARA has provided the final answer\.?\s*",
        r"\(No further action needed[^)]*\)\s*",
        r"No new query[^.]*\.\s*",
        r"Waiting for (your|user)[^.]*\.\s*",
        # Remove "Next thought" patterns
        r"^Next thought:.*?\n",
        r'^My "?next thought"?[^.]*\.\s*',
        r"[Mm]y next thought is:?\s*[^.]*\.\s*",
        # Remove generic philosophical reasoning
        r"^What (could|do|are|is) (I|we)[^?]*\?\s*",
        r"^Perhaps (the|I|we)[^.]*\.\s*",
        r"^Given (no|the lack of) (specific )?observation[^.]*\.\s*",
        r"^I will proceed with a general thought[^.]*\.\s*",
        r"^I\'ll (just )?offer a general[^.]*\.\s*",
        r"^In the absence of (an )?observation[^.]*\.\s*",
        r"^Since (there\'s|I have) no (prior )?observation[^.]*\.\s*",
        r"^Without (any )?(specific |prior )?(context|observation|information)[^.]*\.\s*",
        # Remove scenario/possibility statements that don't add value
        r"^Scenario \d+:[^.]*\.\s*",
        r"^Possible Next Steps[^:]*:\s*",
        # Remove meta-commentary about reasoning process
        r"^How can I be helpful[^?]*\?\s*",
        r"^The (power|importance|interplay) of[^.]*\.\s*",
        r"^Humans are remarkably[^.]*\.\s*",
        # Remove "Final Answer:" prefix if present
        r"^Final Answer:\s*",
        r"^FINAL ANSWER:\s*",
        # Remove "The search results..." reasoning leaks
        r"^The search results (mostly |don\'t |didn\'t |only )?[^.]*\.\s*",
        r"^I need to answer based on[^.]*\.\s*",
        r"^Based on (the |my )?search results[^.]*\.\s*",
        r"^(From |Looking at )the (search |observation |)results[^.]*\.\s*",
        # Remove internal notes about lack of information
        r"^Non ho bisogno di pensieri aggiuntivi[^.]*\.\s*",
        r"^Ho già fornito[^.]*\.\s*",
        r"^I don\'t need additional thoughts[^.]*\.\s*",
        r"^I\'ve already provided[^.]*\.\s*",
        # Remove "But there are still things..." patterns
        r"^But there are still things[^.]*\.\s*",
        # Remove "Let me..." patterns
        r"^Let me (check|search|look|find)[^.]*\.\s*",
        r"^Fammi (cercare|controllare|verificare)[^.]*\.\s*",
        # Remove standalone ACTION patterns that leaked
        r"^ACTION:\s*[a-z_]+\([^)]*\)\.?\s*",
        r"^ACTION:\s*No tool call needed[^.]*\.\s*",
        # Remove CRITICAL/IMPORTANT system message leaks
        r"^CRITICAL:\s*[^\n]*\n*",
        r"^IMPORTANT:\s*[^\n]*\n*",
        # Remove "User Query:" prompt leaks
        r"^User Query:\s*[^\n]*\n*",
        # Remove vector_search call leaks
        r"^vector_search\([^)]*\)\s*",
    ]

    cleaned = response
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.MULTILINE)

    # Remove multiple consecutive newlines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    # Remove leading/trailing whitespace
    cleaned = cleaned.strip()

    # NO TRUNCATION for business responses - let the LLM decide response length
    # Only log extremely long responses for monitoring
    if len(cleaned) > 15000:
        logger.warning(f"⚠️ Very long response: {len(cleaned)} chars (not truncated)")

    logger.info(f"🧹 Cleaned response length: {len(cleaned)}")
    return cleaned
