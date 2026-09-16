"""Deterministic scripted answer for "who are you?" on the WhatsApp product.

WHY THIS EXISTS (measured in production, 2026-09-15 15:47-15:49 WITA)
--------------------------------------------------------------------
A client opened the thread with ``ciao tu sei Zantara?`` and was answered with
the ABSTAIN stub — "I have no reliable source for this one, a Bali Zero
colleague needs to look at it". Asked again, plainly, ``ti ho chiesto chi sei
tu?``, the bot repeated the refusal, in English, to a client writing Italian.

Both Italian sentences above are the owner's own probe messages, sent to the
sandbox number to test the bot — they name nobody and carry no identifier.

Nothing in that chain is broken. An identity question simply has no retrieval
answer: there is no chunk in any collection that says who Zantara is, so the
evidence gate does exactly what it was built to do — it refuses. The missing
piece is the same one ``wa_greeting`` supplies for "halo": some questions are
answered from the product's own definition, not from the corpus.

The first contact with a client is the whole of this defect's cost. A refusal
on "who are you" reads as a broken assistant, and it is the FIRST thing a new
client sees.

CONTRACT (identical in spirit to ``wa_greeting``)
-------------------------------------------------
- **No LLM, no retrieval, no I/O.** Pure function over the message text.
- **Entity, never substring.** The match runs over whole TOKENS of the
  normalized message, so ``chi sei`` matches "ti ho chiesto chi sei tu" and
  never "chiesero" — scar family #3 is symmetric, and a guard that reads
  characters instead of words fails on both sides at once.
- **Guilt needs innocence.** A question about a PERSON in a case
  ("chi deve firmare la LKPM?", "siapa yang harus tanda tangan akta?") is not
  a question about the assistant. The separator is structural and not a list:
  any DOMAIN term in the message vetoes the match outright (see
  ``_DOMAIN_VETO_TOKENS``), whatever shape the sentence has. ``zantara`` and
  ``bali zero`` are deliberately NOT domain terms — asking who Zantara is IS
  the identity question.
- **Conservative by construction.** Anything unclear returns ``None`` and
  costs nothing: the normal retrieval route still runs.
- **No citation, no price, no client data.** A presentation carries no source
  line; prices come from PricingTool on the answering path, never from here.

MEASURED LIMITS (deliberate, not bugs)
---------------------------------------
- A COMPOUND question under the length brakes — "who are you and can you
  help me move next month?" — matches, and the client's practical half is
  answered by the presentation rather than by retrieval. Cost: one extra
  turn. The alternative today is the ABSTAIN refusal, which is worse.
  Measured, not cured.
- The match is STATELESS: a second identity question in the same thread
  gets the same presentation verbatim. Deliberate — this module is a pure
  function with no thread access, by design.

WHY THE CALL SITE IS THE ONE THE GREETING USES
----------------------------------------------
Same reason, same place: this is where the query is known and where the
greeting already short-circuits, BEFORE the package build. A greeting is
matched first, because ``halo`` on its own is a greeting and not a question
about the assistant; an identity question wearing a greeting
("ciao tu sei Zantara?") is not a bare greeting, so ``match_greeting``
correctly declines it and it arrives here.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Identity questions, keyed on the normalized token SEQUENCE they contain.
# One language per phrase; the matched phrase decides the reply's language,
# for the same reason the greeting token does: the client wrote it.
_IDENTITY_PHRASES: dict[str, str] = {
    # Italian
    "chi sei": "it",
    "chi sei tu": "it",
    "tu chi sei": "it",
    "ma chi sei": "it",
    "sei un bot": "it",
    "sei un robot": "it",
    "sei una macchina": "it",
    "sei una persona": "it",
    "sei umano": "it",
    "sei un umano": "it",
    "sei zantara": "it",
    "chi è zantara": "it",
    "chi e zantara": "it",
    "cosa sai fare": "it",
    "cosa puoi fare": "it",
    "che cosa sai fare": "it",
    "che cosa puoi fare": "it",
    "come funzioni": "it",
    "chi ti ha creato": "it",
    "con chi sto parlando": "it",
    "sei un intelligenza artificiale": "it",
    "sei una intelligenza artificiale": "it",
    "sei un ia": "it",
    "sei un chatbot": "it",
    "e un intelligenza artificiale": "it",
    # English
    "who are you": "en",
    "what are you": "en",
    "who am i talking to": "en",
    "who am i speaking to": "en",
    "are you a bot": "en",
    "are you a robot": "en",
    "are you human": "en",
    "are you a human": "en",
    "are you a machine": "en",
    "are you real": "en",
    "are you zantara": "en",
    "who is zantara": "en",
    "what can you do": "en",
    "what do you do": "en",
    "what can you help with": "en",
    "how do you work": "en",
    "who made you": "en",
    "who created you": "en",
    "are you an ai": "en",
    "are you ai": "en",
    "is this an ai": "en",
    "am i talking to an ai": "en",
    "are you a chatbot": "en",
    "is this a chatbot": "en",
    # Indonesian
    "siapa kamu": "id",
    "kamu siapa": "id",
    "siapa anda": "id",
    "anda siapa": "id",
    "kamu siapa sih": "id",
    "kamu bot": "id",
    "kamu robot": "id",
    "apakah kamu bot": "id",
    "apa kamu bot": "id",
    "kamu manusia": "id",
    "apakah kamu manusia": "id",
    "kamu zantara": "id",
    "siapa zantara": "id",
    "kamu bisa apa": "id",
    "bisa bantu apa": "id",
    "apa yang bisa kamu lakukan": "id",
    "apa yang bisa kamu bantu": "id",
    "kamu bisa bantu apa": "id",
    "apakah kamu ai": "id",
    "kamu ai": "id",
    "apakah ini ai": "id",
    "kamu chatbot": "id",
    "apakah kamu chatbot": "id",
    # Russian
    "кто ты": "ru",
    "кто вы": "ru",
    "ты кто": "ru",
    "вы кто": "ru",
    "ты бот": "ru",
    "вы бот": "ru",
    "ты робот": "ru",
    "ты человек": "ru",
    "ты живой": "ru",
    "ты zantara": "ru",
    "кто такая zantara": "ru",
    "что ты умеешь": "ru",
    "что ты можешь": "ru",
    "чем ты можешь помочь": "ru",
    "кто тебя создал": "ru",
    "ты искусственный интеллект": "ru",
    "это ии": "ru",
    "ты чатбот": "ru",
    # Ukrainian
    "хто ти": "uk",
    "хто ви": "uk",
    "ти хто": "uk",
    "ти бот": "uk",
    "ти робот": "uk",
    "ти людина": "uk",
    "ти zantara": "uk",
    "хто така zantara": "uk",
    "що ти вмієш": "uk",
    "що ти можеш": "uk",
    "чим ти можеш допомогти": "uk",
    "хто тебе створив": "uk",
    "ти штучний інтелект": "uk",
    "це штучний інтелект": "uk",
    "ти чатбот": "uk",
}

_MAX_PHRASE_TOKENS = max(len(p.split()) for p in _IDENTITY_PHRASES)

# The VETO. A message carrying any of these is about a CASE, not about the
# assistant, and goes to the retrieval route whatever its grammar looks like.
# This is the innocence half, written as a structural rule rather than as a
# list of counter-examples: a phrasing nobody enumerated ("what can you do
# about my overstay?") is vetoed the day it arrives, because the veto reads
# the subject matter and not the sentence shape.
#
# Deliberately NOT here: "zantara", "bali zero", "assistente", "assistant" —
# those are the identity question's own vocabulary.
_DOMAIN_VETO_TOKENS: frozenset[str] = frozenset(
    {
        # company / licensing
        "pma",
        "pmdn",
        "pt",
        "nib",
        "oss",
        "kbli",
        "akta",
        "notaio",
        "notary",
        "notaris",
        "perusahaan",
        "company",
        "società",
        "societa",
        "licenza",
        "license",
        "licence",
        "izin",
        "perizinan",
        "lkpm",
        "imb",
        "pbg",
        "modal",
        "capital",
        "saham",
        "shareholder",
        "direktur",
        "komisaris",
        # immigration
        "visa",
        "visto",
        "visti",
        "kitas",
        "kitap",
        "voa",
        "e33",
        "e28",
        "e23",
        "immigration",
        "imigrasi",
        "immigrazione",
        "permesso",
        "permit",
        "sponsor",
        "overstay",
        "deportation",
        "deportasi",
        "paspor",
        "passport",
        "passaporto",
        "extension",
        "perpanjangan",
        "rinnovo",
        # tax / accounting
        "pajak",
        "tax",
        "tasse",
        "npwp",
        "spt",
        "ppn",
        "pph",
        "bpjs",
        "accounting",
        "contabilità",
        "contabilita",
        "faktur",
        "invoice",
        # property
        "properti",
        "property",
        "immobile",
        "immobili",
        "tanah",
        "land",
        "shm",
        "hgb",
        "sertifikat",
        "villa",
        "sewa",
        "lease",
        # commercial
        "harga",
        "biaya",
        "price",
        "prezzo",
        "costo",
        "cost",
        "quotation",
        "preventivo",
        "fee",
        "tarif",
    }
)

# An identity question is short. Two independent brakes on over-match, on top
# of the veto: whatever slips past the phrase rules, a long message is never
# answered from a canned string.
_MAX_IDENTITY_TOKENS = 20
_MAX_IDENTITY_CHARS = 120

_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WS_RE = re.compile(r"\s+", flags=re.UNICODE)

# The scripted presentation, one per supported language. It answers three
# things a client actually wants at first contact: who this is, who it
# works for, and what it can do. No price, no law, no source.
#
# Deliberately NO handoff line ("write X to reach a human"): nothing in this
# repository detects that phrase today (PR #3260's refusal copy settled the
# same question the same way — it does not promise "a colleague will reply
# here" either, because nothing notifies a human). Promising a handoff no
# code keeps is a lie the client can act on and get nothing back. It returns
# in the slice that wires the detector.
_IDENTITY_REPLIES: dict[str, str] = {
    "id": (
        "Saya Zantara, asisten digital Bali Zero.\n\n"
        "Saya bisa bantu mengenai:\n"
        "• Visa & izin tinggal (KITAS, KITAP, visa kunjungan)\n"
        "• Pendirian perusahaan & perizinan (PT PMA, NIB, OSS, KBLI)\n"
        "• Pajak & pelaporan (NPWP, SPT, LKPM)\n"
        "• Properti & sertifikat tanah\n\n"
        "Jawaban saya selalu berdasarkan sumber resmi; jika saya belum yakin, "
        "saya akan sampaikan apa adanya dan tidak menebak.\n\n"
        "Anda juga bisa kapan saja minta bicara dengan konsultan kami."
    ),
    "en": (
        "I'm Zantara, the Bali Zero digital assistant.\n\n"
        "I can help you with:\n"
        "• Visas & stay permits (KITAS, KITAP, visit visas)\n"
        "• Company setup & licensing (PT PMA, NIB, OSS, KBLI)\n"
        "• Tax & reporting (NPWP, SPT, LKPM)\n"
        "• Property & land titles\n\n"
        "My answers come from official sources; when I'm not sure, I say so "
        "instead of guessing.\n\n"
        "You can also ask to talk to a human colleague any time."
    ),
    "it": (
        "Sono Zantara, l'assistente digitale di Bali Zero.\n\n"
        "Posso aiutarti con:\n"
        "• Visti e permessi di soggiorno (KITAS, KITAP, visti d'ingresso)\n"
        "• Apertura società e licenze (PT PMA, NIB, OSS, KBLI)\n"
        "• Tasse e adempimenti (NPWP, SPT, LKPM)\n"
        "• Immobili e titoli di proprietà\n\n"
        "Le mie risposte vengono da fonti ufficiali; quando non sono sicuro te "
        "lo dico, invece di tirare a indovinare.\n\n"
        "Puoi anche chiedere in qualsiasi momento di parlare con una persona "
        "del nostro team."
    ),
    "ru": (
        "Я Zantara, цифровой ассистент Bali Zero.\n\n"
        "Я могу помочь с:\n"
        "• Визы и виды на жительство (KITAS, KITAP, гостевые визы)\n"
        "• Регистрация компании и лицензии (PT PMA, NIB, OSS, KBLI)\n"
        "• Налоги и отчётность (NPWP, SPT, LKPM)\n"
        "• Недвижимость и права на землю\n\n"
        "Мои ответы основаны на официальных источниках; если я не уверена, "
        "я так и скажу, а не буду гадать.\n\n"
        "Вы также можете в любой момент попросить поговорить с человеком."
    ),
    "uk": (
        "Я Zantara, цифровий асистент Bali Zero.\n\n"
        "Я можу допомогти з:\n"
        "• Візи та дозволи на проживання (KITAS, KITAP, гостьові візи)\n"
        "• Реєстрація компанії та ліцензії (PT PMA, NIB, OSS, KBLI)\n"
        "• Податки та звітність (NPWP, SPT, LKPM)\n"
        "• Нерухомість та права на землю\n\n"
        "Моя відповідь ґрунтується на офіційних джерелах; якщо я не впевнена, "
        "я так і скажу, а не вигадуватиму.\n\n"
        "Ви також можете будь-коли попросити поговорити з людиною."
    ),
}

_FALLBACK_LANG = "en"


@dataclass(frozen=True)
class IdentityTurn:
    """A matched identity question and the scripted presentation for it."""

    language: str
    text: str


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation and emoji, collapse whitespace.

    NFKC first so a full-width or decomposed form normalizes to the same
    tokens as the plain one. Accents are PRESERVED (``\\w`` keeps them), so
    "chi è zantara" stays distinct from "chi e zantara" — both spellings are
    carried in the phrase table rather than folded, because folding accents
    would also fold Indonesian and Russian words this module never inspects.
    """
    folded = unicodedata.normalize("NFKC", text).casefold()
    stripped = _PUNCT_RE.sub(" ", folded)
    return _WS_RE.sub(" ", stripped).strip()


def match_identity_question(text: str | None) -> IdentityTurn | None:
    """Return the scripted presentation when `text` asks who the bot is.

    Never raises, never performs I/O. ``None`` is the safe answer and means
    "not my business" — the caller runs the normal generation route.

    Order of judgement, and the order matters: length brakes, then the DOMAIN
    VETO, then the phrase match. The veto runs BEFORE the match so that a
    sentence which happens to contain an identity phrase but is really about a
    case ("cosa puoi fare per la mia PT PMA?") can never be answered from a
    canned string — the expensive half of this guard is its innocence.
    """
    if not text:
        return None

    if len(text) > _MAX_IDENTITY_CHARS:
        return None

    normalized = _normalize(text)
    if not normalized:
        return None

    tokens = normalized.split()
    if not tokens or len(tokens) > _MAX_IDENTITY_TOKENS:
        return None

    if any(token in _DOMAIN_VETO_TOKENS for token in tokens):
        return None

    # Whole-token windows only: a phrase must occupy complete tokens of the
    # message, so "chi sei" is found in "ti ho chiesto chi sei tu" (tokens
    # 4-5) and never inside a single longer token.
    for start in range(len(tokens)):
        for span in range(min(_MAX_PHRASE_TOKENS, len(tokens) - start), 0, -1):
            phrase = " ".join(tokens[start : start + span])
            language = _IDENTITY_PHRASES.get(phrase)
            if language is not None:
                reply = _IDENTITY_REPLIES.get(language) or _IDENTITY_REPLIES[_FALLBACK_LANG]
                return IdentityTurn(language=language, text=reply)

    return None
