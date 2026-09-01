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
        "GERMAN": (
            "Ich habe keinen Zugriff auf personenbezogene Daten Dritter wie Steuernummern, "
            "Telefonnummern oder Privatadressen. Kann ich Ihnen bei Visa, Firmengründung "
            "oder rechtlichen Fragen in Indonesien helfen?"
        ),
        "SPANISH": (
            "No tengo acceso a datos personales de terceros, como números de identificación "
            "fiscal, teléfonos o direcciones privadas. ¿Puedo ayudarle con visados, "
            "constitución de empresas o cuestiones legales en Indonesia?"
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
        "GERMAN": (
            "Ich habe keinen Zugriff auf Echtzeitdaten wie Marktpreise oder Wechselkurse — "
            "ich würde eine Zahl nennen, die ich nicht überprüfen kann. Dafür schauen Sie "
            "besser in eine aktuelle Quelle. Bei Visa, KITAS oder Geschäften in Indonesien "
            "helfe ich stattdessen gerne."
        ),
        "SPANISH": (
            "No tengo acceso a datos en tiempo real, como precios de mercado o tipos de "
            "cambio — le daría una cifra que no puedo verificar. Para eso, consulte una "
            "fuente actualizada. En cambio, puedo ayudarle con visados, KITAS o negocios "
            "en Indonesia."
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
        "GERMAN": (
            "Das liegt außerhalb meines Fachgebiets. Ich bin Zantara, die KI-Assistentin "
            "von {company}: Visa, Einwanderung, Firmengründung (PT PMA) und rechtliche "
            "Angelegenheiten für Ausländer in Indonesien. Kann ich Ihnen dabei helfen?"
        ),
        "SPANISH": (
            "Ese tema está fuera de mi área. Soy Zantara, la asistente de IA de {company}: "
            "visados, inmigración, constitución de empresas (PT PMA) y asuntos legales para "
            "extranjeros en Indonesia. ¿Puedo ayudarle en algo de eso?"
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
        "GERMAN": (
            "Dazu habe ich keine konkreten Informationen. Ich kann Ihnen bei Visa, KITAS, "
            "der Gründung einer PT PMA oder einer lokalen PT sowie anderen geschäftlichen "
            "Fragen in Indonesien helfen."
        ),
        "SPANISH": (
            "No tengo información específica sobre eso. Puedo ayudarle con visados, KITAS, "
            "la constitución de una PT PMA o una PT local, y otros asuntos de negocios "
            "en Indonesia."
        ),
    },
}


def get_out_of_domain_response(reason: str, language: str = "ITALIAN") -> str:
    """Refusal copy for ``reason``, in ``language``.

    Fallback order mirrors ``get_localized_stub``: requested language → ENGLISH →
    the ``unknown`` refusal. An unmapped language degrading to ENGLISH is
    deliberate and declared; an unmapped language degrading to ITALIAN — which is
    what shipping the raw table did — is not.

    Logs a warning on that fallback, same rationale as ``get_localized_stub``
    (this table's own SSOT docstring above): a caller feeding the wrong
    detector's vocabulary in here degraded silently before 2026-08-23.
    """
    by_language = _OUT_OF_DOMAIN_BY_LANGUAGE.get(reason) or _OUT_OF_DOMAIN_BY_LANGUAGE["unknown"]
    if language not in by_language:
        logger.warning(
            "get_out_of_domain_response: no %r entry for reason=%r — falling back "
            "to ENGLISH. If %r is a language detect_query_language can emit, "
            "translate it here or add it to DECLARED_ENGLISH_FALLBACK on purpose.",
            language,
            reason,
            language,
        )
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


# ============================================================================
# INTERNAL-MONOLOGUE FILTERING
# ============================================================================
#
# Three classes, three anchorings. The split IS the cure for a measured defect:
# every pattern below used to be applied with `re.MULTILINE`, so a `^`-anchored
# "strip the leading preamble" rule matched at EVERY line start and ate lines
# out of the middle of a correct answer. Measured 2026-08-10 against the real
# pattern list: 20 of 22 legitimate answer fragments were altered and 15 were
# deleted outright — `"The power of attorney must be notarised before
# submission."` cleaned to `""`.
#
# The two failure directions are NOT symmetric here, which is why several
# patterns below are NARROWER than the ones they replace:
#   * false negative -> a line of model filler reaches the client;
#   * false positive -> advice the client asked for is deleted from an answer
#     that already passed retrieval AND the abstain gate, and on WhatsApp an
#     emptied answer is silence (`wa_inbox_bot` sends nothing).
# So narrow deliberately. Do not widen any pattern back without a measured
# innocence case; the guilt/innocence corpus lives in
# `backend/tests/services/response/test_cleaner_anchor_not_multiline.py`.

# Protocol markers: tokens the model emits as ReAct/system scaffolding. These
# genuinely can start ANY line of a leaked monologue, so they keep MULTILINE.
_MARKER_PATTERNS: tuple[str, ...] = (
    r"^THOUGHT:.*?\n",
    r"^THOUGHT\s*:.*?\n",
    r"^Thought:.*?\n",
    r"^Thought\s*:.*?\n",
    r"^Observation:.*?\n",
    r"^Observation\s*:.*?\n",
    r"^Next thought:.*?\n",
    r"^ACTION:\s*[a-z_]+\([^)]*\)\.?\s*",
    r"^ACTION:\s*No tool call needed[^.]*\.\s*",
    r"^vector_search\([^)]*\)\s*",
    # W119c (2026-08-31): same-line separator. `\s*` crossed the newline on an
    # EMPTY marker, so the client received the answer with its first line gone.
    r"^User Query:[^\S\n]*[^\n]*\n*",
    # `internal_monologue` — the model emitting the name of the section the
    # system prompt tells it to run SILENTLY (`<internal_monologue_instructions>`
    # in zantara_core.py). Measured live 2026-08-11: 2 of 16 cold answers opened
    # with the literal token, one continuing "The previous answer was rejected
    # because it included detailed inf…" — the machinery, verbatim, to a client.
    #
    # Tagged form: remove the WHOLE block, because the closing tag says where it
    # ends. Bare form: remove ONLY the token. Nothing marks where an untagged
    # monologue stops, and guessing a boundary would eat the answer — the two
    # leaked answers ran straight from the monologue into real content. Opening
    # on a machine token is the part we can fix without inventing an ending.
    # `<?` and `</?` BOTH optional: the leak measured in production carries NO
    # tag at all ("internal_monologue The user is asking…"). A first draft made
    # the `<` mandatory and matched nothing — the guard missed the only shape it
    # was written for, and its own bare-leak test is what caught that.
    r"^(?:</?)?internal_monologue(?:_instructions)?>?\s*:?\s*",
    # Prefix-only strips: the marker goes, the sentence after it stays.
    r"^Final Answer:\s*",
    r"^FINAL ANSWER:\s*",
    # CRITICAL:/IMPORTANT: are system-prompt leaks ONLY when they direct the
    # MODEL. `IMPORTANT: the LKPM must be filed quarterly.` and `IMPORTANT:
    # Always carry your KITAS.` are exactly how compliance answers are written,
    # and the old bare-prefix form deleted the whole line. A directive verb
    # alone does not separate the two (a client warning is imperative too), so
    # the line must ALSO name something only the assistant does.
    # The lookahead is the load-bearing half, mutation-measured: an intermediate
    # draft listed `Your\b` as a directive opener and ate "CRITICAL: your KITAS
    # expires in 14 days.", but re-adding `Your\b` NOW kills no test, because
    # the lookahead already rejects that line. `You\b` does not match "your"
    # (the `\b` needs a non-word char after it); the opener list is a second
    # filter, not the guard.
    r"^(CRITICAL|IMPORTANT):\s*"
    r"(?=[^\n]*\b(?:invent|fabricate|guess|hallucinat\w*|cite|reveal|disclose|"
    r"respond|reply|output|tool|tools|search results|system prompt|instructions|"
    r"the user|the client)\b)"
    r"(You\b|Never\b|Always\b|Do not\b|Don't\b|Use\b|Remember\b|Ensure\b|"
    r"Make sure\b)[^\n]*\n*",
)

# Leading preamble: filler the model puts BEFORE the answer. Compiled without
# MULTILINE, so `^` means start-of-string and these can never reach into the
# body of an answer.
_PREAMBLE_PATTERNS: tuple[str, ...] = (
    r"^Okay[,.]?\s*(since|with|given|without|lacking|based|in the absence)[^.]*observation[^.]*\.\s*",
    r"^Okay[,.]?\s*(based|since|with|given|without|lacking)[^.]*prior (information|context)[^.]*\.\s*",
    r"^Okay[,.]?\s*(based|since|with|given|without|lacking)[^.]*context[^.]*\.\s*",
    r"^Okay[,.]?\s*(based|since|with|given|without|lacking)[^.]*input[^.]*\.\s*",
    r"^Okay[,.]?\s*I need to (either|understand|consider)[^.]*\.\s*",
    r"^Okay[,.]?\s*Given the (observation|lack)[^.]*\.\s*",
    r"^Okay\.\s*[A-Z][^.]*?(observation|context|information)[^.]*\.\s*",
    r'^My "?next thought"?[^.]*\.\s*',
    # NARROWED: `^What (could|do|are|is) (I|we)` deleted the legitimate
    # rhetorical "What are we required to file for the SPT Tahunan?".
    r"^What (could|should|shall) I[^?]*\?\s*",
    r"^What do I (know|have|need)[^?]*\?\s*",
    # NARROWED: `^Perhaps (the|I|we)` deleted "Perhaps the most common case is
    # a PT PMA with a single foreign shareholder.".
    r"^Perhaps I (should|could|need|will|can)[^.]*\.\s*",
    r"^Given (no|the lack of) (specific )?observation[^.]*\.\s*",
    r"^I will proceed with a general thought[^.]*\.\s*",
    r"^I\'ll (just )?offer a general[^.]*\.\s*",
    r"^In the absence of (an )?observation[^.]*\.\s*",
    r"^Since (there\'s|I have) no (prior )?observation[^.]*\.\s*",
    # SPLIT: "observation" is ReAct vocabulary and safe to delete on sight;
    # "Without any prior context, I would still advise filing before 31 March."
    # is a real answer, so the context/information arm now also requires the
    # model to be declaring its own incapacity.
    r"^Without (any )?(specific |prior )?observation[^.]*\.\s*",
    r"^Without (any )?(specific |prior )?(context|information)[^.]*\b"
    r"(I (will|can only|cannot|can\'t|am unable to)|I\'ll) "
    r"(offer|provide|give|proceed|make|assume)[^.]*\.\s*",
    r"^How can I be helpful[^?]*\?\s*",
    # NARROWED: the qualifier is now REQUIRED. Unqualified "The search results
    # confirm the 2026 rate is 11%." carries the fact in the sentence being
    # deleted; the qualified form carries nothing.
    r"^The search results (mostly|don\'t|didn\'t|do not|did not|only)\b[^.]*\.\s*",
    # NARROWED: bare `^I need to answer based on` deleted "…based on the akta
    # you sent - page 2 lists the directors." The object list is what makes it
    # monologue; an answer grounded in a client document is not.
    r"^I need to answer based on (the |my )?"
    r"(observation|context|search results|what I have|nothing|no information)"
    r"[^.]*\.\s*",
    # PREFIX-ONLY (was sentence-delete): keeps "the KBLI code is 68111.".
    r"^Based on (the |my )?search results[,:]?\s*",
    r"^(From |Looking at )the (search |observation |)results[,:]?\s*",
    r"^Non ho bisogno di pensieri aggiuntivi[^.]*\.\s*",
    r"^Ho già fornito[^.]*\.\s*",
    r"^I don\'t need additional thoughts[^.]*\.\s*",
    r"^I\'ve already provided[^.]*\.\s*",
    r"^But there are still things[^.]*\.\s*",
    # NARROWED with `[^.:]`: a colon means the sentence introduces content
    # ("Let me check: the E33G is valid for 5 years."), which must survive.
    # A bare intention ("Let me check the knowledge base.") still goes.
    r"^Let me (check|search|look|find)[^.:]*\.\s*",
    r"^Fammi (cercare|controllare|verificare)[^.:]*\.\s*",
    # Stub responses — anchored, because unanchored they matched mid-answer
    # ("Waiting for your passport scan, we can start the application." -> "").
    r"^Waiting for (your|user) (next |new )?"
    r"(quer(y|ies)|input|response|message|instruction)s?\b[^.]*\.\s*",
    # ── The monologue the TOKEN strip left standing (measured 2026-08-11) ──
    # `_MARKER_PATTERNS` removes the literal `internal_monologue`; it deliberately
    # does NOT guess where an untagged monologue ends. That was right, and it was
    # not enough: probing the Indonesian paid-up-capital ask (probe 35, prod,
    # `ctx=1 ev=0.85` — retrieval had SUCCEEDED) returned 6,214 characters opening
    # `internal_monologue The user is asking for the minimum paid-up capital for
    # PT PMA. I need to find this information **ONLY** within the provided
    # <verified_data>. Let's examine the provided RAG results.` Stripping the token
    # shortened that by 20 characters and shipped the rest. These three peel the
    # SENTENCES, from the preamble position only — where the answer has not started.
    #
    # Third person about the reader: a client-facing answer never calls the person
    # it is addressing "the user". The VERB is load-bearing, not decoration —
    # `^The user\b` alone eats "The user manual for OSS is published by BKPM."
    # (in LEGITIMATE_ANSWER_FRAGMENTS for exactly this reason).
    r"^(Okay[,.]?\s*)?[Tt]he user (is asking|is requesting|asks|wants|would like|"
    r"needs|is inquiring|is looking)\b[^.]*\.\s*",
    # …and the same sentence hiding BEHIND an echo of the question. Measured 20
    # minutes after the pattern above was written, which is why it is here:
    # repeating the identical ask six times, one run answered
    # `What are your office opening hours?\n\nThe user is asking for office
    # opening hours. This information is not pres…` — the echo occupies
    # start-of-string, so a `^`-anchored rule cannot see the monologue behind it.
    # The question line is consumed ONLY when a monologue sentence follows it:
    # deleting a leading question on its own would eat "What is the difference
    # between a KITAS and a KITAP?", a real answer opener already pinned in
    # LEGITIMATE_ANSWER_FRAGMENTS. Bounded length so this cannot swallow a
    # paragraph that merely happens to contain a question mark.
    r"^[^\n]{0,200}\?\s*\n+\s*(Okay[,.]?\s*)?[Tt]he user "
    r"(is asking|is requesting|asks|wants|would like|needs|is inquiring|"
    r"is looking)\b[^.]*\.\s*",
    # Naming the store it was told to consult. The lookahead is the load-bearing
    # half, same idiom as the CRITICAL/IMPORTANT pattern above: without it this
    # deletes "I need to find the missing page of your akta." — a real request to
    # a client. The object must be the MACHINERY, never a client document.
    r"^I need to (find|locate|look for|search for)\b"
    r"(?=[^\n]*\b(verified[ _]data|provided context|search results|RAG results|"
    r"knowledge base|the provided|retrieved (context|results))\b)"
    r"[^.]*\.\s*",
    # Announcing the inspection of a retrieval store. The qualifier is REQUIRED:
    # unqualified, this deletes "Let's review the results of your tax assessment."
    r"^Let'?s (examine|look at|review|inspect) the "
    r"(provided |retrieved )?(RAG|search|retrieval|vector|verified[ _]data)"
    r"\s*(results|chunks)?\b[^.]*\.\s*",
)

# DROPPED, not moved — each was measured deleting ordinary consultant English
# and has no monologue-only trigger left to narrow onto:
#   r"^Scenario \d+:[^.]*\.\s*"                      -> ate "Scenario 1: you already hold a KITAS."
#   r"^Possible Next Steps[^:]*:\s*"                 -> ate a legitimate answer heading
#   r"^The (power|importance|interplay) of[^.]*\.\s*" -> ate "The power of attorney must be notarised."
#   r"[Pp]rovide me with some context[^.]*\.\s*"     -> ate the bot's own clarifying request
#   r"^Humans are remarkably[^.]*\.\s*"             -> ate "…patient with Indonesian
#       bureaucracy, but the deadline is fixed." - same shape-guess at philosophical
#       filler as `The importance of`, same whole-sentence loss.
#   r"^No new quer(y|ies)[^.]*\.\s*"                -> ate "No new query is needed - the
#       NIB already covers this KBLI."; "query" alone is not monologue-only vocabulary.
# The monologue framing they were meant to catch is still covered by the
# "solicit input" / "my next thought" patterns below.

# Unanchored: phrases that are monologue wherever they appear.
_ANYWHERE_PATTERNS: tuple[str, ...] = (
    r"[Mm]y next thought is to solicit input[^.]*\.\s*",
    r"[Ss]olicit input to understand[^.]*\.\s*",
    r"[Mm]y next thought is:?\s*[^.]*\.\s*",
    r"Zantara has provided the final answer\.?\s*",
    r"ZANTARA has provided the final answer\.?\s*",
    r"\(No further action needed[^)]*\)\s*",
)

_MARKER_RE = tuple(re.compile(p, re.IGNORECASE | re.MULTILINE) for p in _MARKER_PATTERNS)
_PREAMBLE_RE = tuple(re.compile(p, re.IGNORECASE) for p in _PREAMBLE_PATTERNS)
_ANYWHERE_RE = tuple(re.compile(p, re.IGNORECASE) for p in _ANYWHERE_PATTERNS)

# Separate tuple: this one needs DOTALL to span the newlines inside a leaked
# block, and DOTALL must NOT be given to the patterns above (their `.*?\n` would
# stop meaning "this line only"). Non-greedy + an explicit closing tag, so it can
# never swallow past the block it opened.
_BLOCK_RE = (
    re.compile(
        r"<internal_monologue(?:_instructions)?>.*?</internal_monologue(?:_instructions)?>",
        re.IGNORECASE | re.DOTALL,
    ),
)

# A response can open with several stacked preamble sentences; each pass peels
# at most one per pattern, so re-run until nothing changes (bounded).
_PREAMBLE_MAX_PASSES = 5


def clean_response(response: str) -> str:
    """
    Remove internal reasoning patterns from user-facing response.

    Filters out THOUGHT leaks, observation statements, and generic philosophical
    reasoning that should not be exposed to users.

    Never returns an empty string for a non-blank input: if the filters would
    consume the whole answer that is a filter defect, not a monologue-only
    answer, and the caller (`PostProcessingStage` -> `wa_inbox_bot`) turns an
    emptied answer into client-facing silence. The original is returned and the
    event logged instead.

    Args:
        response: Raw response from LLM

    Returns:
        Cleaned response without internal reasoning patterns
    """
    if not response:
        return ""

    cleaned = response
    for regex in _BLOCK_RE:
        cleaned = regex.sub("", cleaned)
    for regex in _ANYWHERE_RE:
        cleaned = regex.sub("", cleaned)
    for regex in _MARKER_RE:
        cleaned = regex.sub("", cleaned)
    for _ in range(_PREAMBLE_MAX_PASSES):
        before = cleaned
        for regex in _PREAMBLE_RE:
            cleaned = regex.sub("", cleaned, count=1)
        if cleaned == before:
            break

    # Remove multiple consecutive newlines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    # Remove leading/trailing whitespace
    cleaned = cleaned.strip()

    # Prefix-only strips ("Final Answer: ", "Based on the search results, ")
    # leave the answer opening mid-sentence. Restore sentence case only when
    # the raw answer did NOT start lowercase, i.e. only when we are the ones
    # who chopped its opening.
    if cleaned[:1].islower() and not response.lstrip()[:1].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]

    if not cleaned and response.strip():
        logger.warning(
            "🧹 Cleaner would have emptied a %d-char response - returning it unfiltered "
            "(a monologue filter matched the whole answer; this is a pattern defect)",
            len(response.strip()),
        )
        return response.strip()

    # NO TRUNCATION for business responses - let the LLM decide response length
    # Only log extremely long responses for monitoring
    if len(cleaned) > 15000:
        logger.warning(f"⚠️ Very long response: {len(cleaned)} chars (not truncated)")

    logger.info(f"🧹 Cleaned response length: {len(cleaned)}")
    return cleaned
