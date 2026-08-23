"""
Localized stub messages for the ReAct reasoning engine.

Pulled out of ``reasoning.py`` (refactor/split-reasoning) so the stub
table is a single source of truth, separate from the reasoning logic.

Public API:
    - STUB_MESSAGES: dict[key, dict[language, text]] — the full table.
    - PROTOCOL_LANGUAGES: the languages every key must cover in full.
    - get_localized_stub: resolve a (key, language) pair with fallback
      order Requested Language → ENGLISH → generic hardcoded message.

WHAT THE ``abstain`` TEXT IS FOR (2026-07-27)
---------------------------------------------
This is what a client reads when the bot will not answer. It is the visible
face of the product's core safety property — abstain instead of invent — so
its wording is load-bearing, not decoration.

Three rules the wording obeys, each from a measured failure:

1. **It says why, and the why is a reason to trust it.** The old text
   ("I'm sorry, I couldn't find relevant information for this question.")
   reads as a dead end with no next move. Naming the stake — with permits and
   deadlines a wrong answer is expensive — turns a refusal into the
   consultant's judgment it actually is.

2. **It promises nothing the system does not do.** An earlier draft said "a
   colleague will reply here". Nothing in the pipeline notifies a human today:
   ``wa_outbox.apology_sent_at`` and ``ack_sent_at`` exist and are 0-for-184
   rows since 2026-06-02. So the text states what the QUESTION needs ("this
   one needs a Bali Zero colleague to look at it") rather than asserting that
   someone was told. Promote it to a real promise only together with the
   routing that backs it — never before.

3. **It gives the client one concrete move.** Asking for a document or a
   reference date is the input most likely to turn a miss into a hit, and it
   costs the client nothing.

Channel note: these strings are channel-agnostic on purpose. The reasoning
engine has no ``channel`` in scope (verified 2026-07-27 — no such symbol in
reasoning.py), so any wording naming a surface ("reply here in this chat")
would be false on the others. Channel-specific hand-off belongs at the channel
boundary (``wa_inbox_bot``), not in this table.

Language coverage: ``query_helpers.detect_query_language`` can emit ten
values; this table carries full translations for the seven protocol languages
(``PROTOCOL_LANGUAGES``) and lets the rest (CHINESE/ARABIC/FRENCH — see
``DECLARED_ENGLISH_FALLBACK`` in ``test_reasoning_stubs_language_coverage.py``)
fall back to ENGLISH by design.
``test_reasoning_stubs_language_coverage.py`` pins both halves of that claim,
so a language added to the detector cannot silently start serving English.

GERMAN and SPANISH joined the protocol set on 2026-08-23: ``detect_query_language``
could already emit both (the ``_LATIN_MARKERS`` detector rows), but this table
only had them in the silent-English-fallback set — a DE/ES client hit any
abstain/error/confused branch in ``reasoning.py`` and read English. Promoted
here, not left as a one-off patch, because the same table backs every call site
(``reasoning.py``'s ReAct loop, ``wa_finalize.py``'s abstain-fairness path) —
the fix has to live where the silent fallback did.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_FALLBACK_MESSAGE = "I'm sorry, I cannot fulfill this request."

#: The languages ZANTARA's LANGUAGE_PROTOCOL commits to (zantara_core.py).
#: Every key in STUB_MESSAGES must carry a real translation for each — a
#: missing one degrades to English silently, which is how Russian and
#: Ukrainian clients were reading English refusals until 2026-07-27, and how
#: German and Spanish clients were reading it until 2026-08-23.
PROTOCOL_LANGUAGES: tuple[str, ...] = (
    "ITALIAN",
    "ENGLISH",
    "INDONESIAN",
    "RUSSIAN",
    "UKRAINIAN",
    "GERMAN",
    "SPANISH",
)

STUB_MESSAGES: dict[str, dict[str, str]] = {
    "abstain": {
        "ITALIAN": (
            "Su questo non ho una fonte certa e preferisco non tirare a indovinare: "
            "con permessi e scadenze una risposta sbagliata costa. "
            "Questa la deve guardare un collega di Bali Zero. "
            "Se intanto mi mandi un documento o una data di riferimento, "
            "posso riprovare con quelli."
        ),
        "ENGLISH": (
            "I don't have a reliable source for this one, and I'd rather not guess — "
            "with permits and deadlines a wrong answer is expensive. "
            "This one needs a Bali Zero colleague to look at it. "
            "If you can send me a document or a reference date in the meantime, "
            "I can try again with those."
        ),
        "INDONESIAN": (
            "Untuk yang ini saya tidak punya sumber yang pasti, dan saya lebih baik "
            "tidak menebak — untuk izin dan tenggat waktu, jawaban yang salah itu mahal. "
            "Yang ini perlu dilihat oleh rekan dari Bali Zero. "
            "Sementara itu, kalau Anda kirim dokumen atau tanggal acuan, "
            "saya bisa coba lagi dengan itu."
        ),
        "RUSSIAN": (
            "По этому вопросу у меня нет надёжного источника, и я предпочитаю не гадать: "
            "когда речь идёт о разрешениях и сроках, неверный ответ обходится дорого. "
            "Здесь нужен взгляд коллеги из Bali Zero. "
            "Если пока пришлёте документ или дату, на которую опираетесь, "
            "я попробую ещё раз с ними."
        ),
        "UKRAINIAN": (
            "Щодо цього я не маю надійного джерела і волію не вгадувати: "
            "коли йдеться про дозволи та строки, неправильна відповідь дорого коштує. "
            "Це має подивитися колега з Bali Zero. "
            "Якщо тим часом надішлете документ або дату, на яку спираєтесь, "
            "я спробую ще раз із ними."
        ),
        "GERMAN": (
            "Dazu habe ich keine verlässliche Quelle, und ich möchte lieber nicht raten — "
            "bei Genehmigungen und Fristen ist eine falsche Antwort teuer. "
            "Das muss sich ein Kollege von Bali Zero ansehen. "
            "Wenn Sie mir in der Zwischenzeit ein Dokument oder ein Bezugsdatum schicken, "
            "versuche ich es damit noch einmal."
        ),
        "SPANISH": (
            "Para esto no tengo una fuente fiable, y prefiero no adivinar — "
            "con permisos y plazos, una respuesta equivocada sale cara. "
            "Esto lo tiene que revisar un colega de Bali Zero. "
            "Si mientras tanto me envía un documento o una fecha de referencia, "
            "puedo intentarlo de nuevo con eso."
        ),
    },
    # Same refusal, for the one case where the promise is now backed: a human
    # WAS told. Added 2026-08-11 with the WA-inbox escalation lane — rule 2 of
    # this module's docstring says "promote it to a real promise only together
    # with the routing that backs it", and this key exists only because the
    # routing landed in the same change.
    #
    # It asserts the flagging and NOTHING downstream of it. No "will reply", no
    # "within one business hour": the caller selects this key from a boolean
    # that means "Telegram accepted the message", which is not evidence that a
    # person is on shift, has read it, or owns it. The prompt's own escalation
    # example does promise an hour — that SLA is a staffing commitment, not a
    # code property, and it is deliberately absent here.
    "abstain_flagged": {
        "ITALIAN": (
            "Su questo non ho una fonte certa e preferisco non tirare a indovinare: "
            "con permessi e scadenze una risposta sbagliata costa. "
            "L'ho segnalata al team di Bali Zero. "
            "Se intanto mi mandi un documento o una data di riferimento, "
            "posso riprovare con quelli."
        ),
        "ENGLISH": (
            "I don't have a reliable source for this one, and I'd rather not guess — "
            "with permits and deadlines a wrong answer is expensive. "
            "I've flagged it to the Bali Zero team. "
            "If you can send me a document or a reference date in the meantime, "
            "I can try again with those."
        ),
        "INDONESIAN": (
            "Untuk yang ini saya tidak punya sumber yang pasti, dan saya lebih baik "
            "tidak menebak — untuk izin dan tenggat waktu, jawaban yang salah itu mahal. "
            "Sudah saya teruskan ke tim Bali Zero. "
            "Sementara itu, kalau Anda kirim dokumen atau tanggal acuan, "
            "saya bisa coba lagi dengan itu."
        ),
        "RUSSIAN": (
            "По этому вопросу у меня нет надёжного источника, и я предпочитаю не гадать: "
            "когда речь идёт о разрешениях и сроках, неверный ответ обходится дорого. "
            "Я передал вопрос команде Bali Zero. "
            "Если пока пришлёте документ или дату, на которую опираетесь, "
            "я попробую ещё раз с ними."
        ),
        "UKRAINIAN": (
            "Щодо цього я не маю надійного джерела і волію не вгадувати: "
            "коли йдеться про дозволи та строки, неправильна відповідь дорого коштує. "
            "Я передав це команді Bali Zero. "
            "Якщо тим часом надішлете документ або дату, на яку спираєтесь, "
            "я спробую ще раз із ними."
        ),
        "GERMAN": (
            "Dazu habe ich keine verlässliche Quelle, und ich möchte lieber nicht raten — "
            "bei Genehmigungen und Fristen ist eine falsche Antwort teuer. "
            "Ich habe es an das Bali-Zero-Team weitergeleitet. "
            "Wenn Sie mir in der Zwischenzeit ein Dokument oder ein Bezugsdatum schicken, "
            "versuche ich es damit noch einmal."
        ),
        "SPANISH": (
            "Para esto no tengo una fuente fiable, y prefiero no adivinar — "
            "con permisos y plazos, una respuesta equivocada sale cara. "
            "Se lo he pasado al equipo de Bali Zero. "
            "Si mientras tanto me envía un documento o una fecha de referencia, "
            "puedo intentarlo de nuevo con eso."
        ),
    },
    # WHAT THE ``truncated_tail`` TEXT IS FOR (2026-08-11)
    # ----------------------------------------------------
    # WhatsApp's Cloud API refuses a body over 4096 characters, and
    # `whatsapp_service.send_message` enforces that with `text[:4096]` — a
    # silent cut, mid-word, with nothing telling the client it happened.
    # Measured: 4 of 311 production bot replies were cut this way (max 7521
    # chars), and a live probe got 5097 characters back for the single word
    # "kitas" — so this is not an exotic case, one word reaches it.
    #
    # This suffix is appended to the FIRST clean chunk. It says only what is
    # true — the answer was shortened — and invites a follow-up the bot can
    # actually serve (a specific point). It deliberately does NOT say "ask me
    # to continue": nothing retains the remainder, so continuation is a
    # promise this path cannot keep, and tonight's other cure exists precisely
    # because a promise nothing performs is worse than a plain limit.
    "truncated_tail": {
        "ITALIAN": (
            "\n\n_(Ho accorciato la risposta per stare nel limite di WhatsApp. "
            "Chiedimi di un punto specifico e te lo approfondisco.)_"
        ),
        "ENGLISH": (
            "\n\n_(I shortened this to fit WhatsApp's message limit. "
            "Ask me about a specific point and I'll go deeper on it.)_"
        ),
        "INDONESIAN": (
            "\n\n_(Saya persingkat jawabannya agar muat di batas pesan WhatsApp. "
            "Tanyakan poin tertentu dan saya jelaskan lebih detail.)_"
        ),
        "RUSSIAN": (
            "\n\n_(Я сократил ответ, чтобы он поместился в лимит WhatsApp. "
            "Спросите про конкретный пункт — расскажу подробнее.)_"
        ),
        "UKRAINIAN": (
            "\n\n_(Я скоротив відповідь, щоб вона вмістилася в ліміт WhatsApp. "
            "Запитайте про конкретний пункт — розкажу докладніше.)_"
        ),
        "GERMAN": (
            "\n\n_(Ich habe die Antwort gekürzt, damit sie ins WhatsApp-Limit passt. "
            "Fragen Sie mich nach einem bestimmten Punkt, und ich gehe genauer darauf ein.)_"
        ),
        "SPANISH": (
            "\n\n_(He acortado la respuesta para que quepa en el límite de WhatsApp. "
            "Pregúnteme por un punto concreto y se lo detallo.)_"
        ),
    },
    # WHAT THE ``low_confidence_note`` TEXT IS FOR (2026-08-11)
    # --------------------------------------------------------
    # Appended when the WhatsApp path sends an answer that came back flagged
    # `abstain=true`. Measured across 16 cold questions in 8 languages: 7 were
    # flagged and 3 of those carried a complete, on-topic answer — the old
    # consumer discarded all 7 and the client got silence with the answer
    # already written.
    #
    # The copy says the sources were not fully verified and that a colleague is
    # re-checking. It does NOT promise a reply, a time, or a correction: the
    # abstain path notifies Telegram, and "Telegram accepted a message" is not
    # "a person will answer you". Same rule as `abstain_flagged`.
    "low_confidence_note": {
        "ITALIAN": (
            "\n\n_(Questa risposta si appoggia a fonti che non ho potuto "
            "verificare del tutto: un collega di Bali Zero la sta ricontrollando.)_"
        ),
        "ENGLISH": (
            "\n\n_(This answer rests on sources I could not fully verify: "
            "a Bali Zero colleague is double-checking it.)_"
        ),
        "INDONESIAN": (
            "\n\n_(Jawaban ini berdasarkan sumber yang belum sepenuhnya bisa "
            "saya verifikasi: rekan Bali Zero sedang memeriksanya kembali.)_"
        ),
        "RUSSIAN": (
            "\n\n_(Этот ответ опирается на источники, которые я не смогла "
            "полностью проверить: коллега из Bali Zero их перепроверяет.)_"
        ),
        "UKRAINIAN": (
            "\n\n_(Ця відповідь спирається на джерела, які я не змогла повністю "
            "перевірити: колега з Bali Zero їх перевіряє.)_"
        ),
        "GERMAN": (
            "\n\n_(Diese Antwort stützt sich auf Quellen, die ich nicht vollständig prüfen "
            "konnte: ein Kollege von Bali Zero überprüft sie noch einmal.)_"
        ),
        "SPANISH": (
            "\n\n_(Esta respuesta se basa en fuentes que no pude verificar del todo: "
            "un colega de Bali Zero la está revisando.)_"
        ),
    },
    "abstain_detailed": {
        "ITALIAN": (
            "Per questa domanda specifica non ho informazioni verificate sufficienti "
            "nei documenti ufficiali, e preferisco dirtelo invece di inventare.\n\n"
            "Su questi temi invece sono solido:\n"
            "• Visti e KITAS\n"
            "• Apertura società (PT PMA)\n"
            "• Fisco e adempimenti\n"
            "• Procedure e documenti\n\n"
            "Se la tua domanda ricade lì, riformulala pure. "
            "Altrimenti la deve guardare un collega di Bali Zero."
        ),
        "ENGLISH": (
            "For this specific question I don't have enough verified information in the "
            "official documents, and I'd rather tell you than invent something.\n\n"
            "These I'm solid on:\n"
            "• Visas and KITAS\n"
            "• Company setup (PT PMA)\n"
            "• Tax and filings\n"
            "• Procedures and paperwork\n\n"
            "If your question falls in there, rephrase it and I'll take another run. "
            "Otherwise it needs a Bali Zero colleague to look at it."
        ),
        "INDONESIAN": (
            "Untuk pertanyaan spesifik ini saya tidak punya cukup informasi terverifikasi "
            "di dokumen resmi, dan saya lebih baik mengatakannya daripada mengarang.\n\n"
            "Kalau soal ini saya kuat:\n"
            "• Visa dan KITAS\n"
            "• Pendirian perusahaan (PT PMA)\n"
            "• Pajak dan pelaporan\n"
            "• Prosedur dan dokumen\n\n"
            "Kalau pertanyaan Anda masuk ke situ, silakan rumuskan ulang. "
            "Kalau tidak, ini perlu dilihat oleh rekan dari Bali Zero."
        ),
        "RUSSIAN": (
            "По этому конкретному вопросу у меня недостаточно проверенных сведений "
            "в официальных документах, и я лучше скажу об этом, чем стану выдумывать.\n\n"
            "А вот в этом я уверен:\n"
            "• Визы и KITAS\n"
            "• Открытие компании (PT PMA)\n"
            "• Налоги и отчётность\n"
            "• Процедуры и документы\n\n"
            "Если ваш вопрос про это — переформулируйте, и я попробую снова. "
            "Если нет — на него должен посмотреть коллега из Bali Zero."
        ),
        "UKRAINIAN": (
            "Щодо цього конкретного питання я не маю достатньо перевірених відомостей "
            "в офіційних документах, і краще скажу про це, ніж вигадуватиму.\n\n"
            "А ось у цьому я впевнений:\n"
            "• Візи та KITAS\n"
            "• Відкриття компанії (PT PMA)\n"
            "• Податки та звітність\n"
            "• Процедури та документи\n\n"
            "Якщо ваше питання про це — переформулюйте, і я спробую ще раз. "
            "Якщо ні — на нього має подивитися колега з Bali Zero."
        ),
        "GERMAN": (
            "Zu dieser konkreten Frage habe ich in den offiziellen Dokumenten nicht genug "
            "verifizierte Informationen, und ich sage das lieber, statt mir etwas auszudenken.\n\n"
            "Darin bin ich dagegen sicher:\n"
            "• Visa und KITAS\n"
            "• Firmengründung (PT PMA)\n"
            "• Steuern und Meldungen\n"
            "• Verfahren und Unterlagen\n\n"
            "Wenn Ihre Frage dazu gehört, formulieren Sie sie gerne neu. "
            "Andernfalls muss sich ein Kollege von Bali Zero das ansehen."
        ),
        "SPANISH": (
            "Sobre esta pregunta concreta no tengo suficiente información verificada en los "
            "documentos oficiales, y prefiero decírselo antes que inventar algo.\n\n"
            "En esto sí estoy seguro:\n"
            "• Visados y KITAS\n"
            "• Constitución de empresa (PT PMA)\n"
            "• Impuestos y trámites\n"
            "• Procedimientos y documentos\n\n"
            "Si su pregunta entra ahí, puede reformularla. "
            "Si no, lo tiene que revisar un colega de Bali Zero."
        ),
    },
    "error": {
        "ITALIAN": (
            "Ho un problema tecnico e non riesco a completare la richiesta adesso. "
            "Riprova tra qualche minuto."
        ),
        "ENGLISH": (
            "I'm hitting a technical problem and can't complete the request right now. "
            "Please try again in a few minutes."
        ),
        "INDONESIAN": (
            "Saya sedang mengalami masalah teknis dan belum bisa menyelesaikan permintaan ini. "
            "Silakan coba lagi beberapa menit lagi."
        ),
        "RUSSIAN": (
            "У меня технический сбой, и сейчас я не могу выполнить запрос. "
            "Попробуйте, пожалуйста, через несколько минут."
        ),
        "UKRAINIAN": (
            "У мене технічний збій, і зараз я не можу виконати запит. "
            "Спробуйте, будь ласка, за кілька хвилин."
        ),
        "GERMAN": (
            "Ich habe gerade ein technisches Problem und kann die Anfrage im Moment nicht "
            "bearbeiten. Bitte versuchen Sie es in ein paar Minuten erneut."
        ),
        "SPANISH": (
            "Tengo un problema técnico y no puedo completar la solicitud en este momento. "
            "Por favor, inténtelo de nuevo en unos minutos."
        ),
    },
    "confused": {
        "ITALIAN": (
            "Mi dispiace, non ho capito bene la tua richiesta. Potresti riformularla? "
            "Posso aiutarti con visti, aziende e leggi in Indonesia."
        ),
        "ENGLISH": (
            "I'm sorry, I didn't quite understand your request. Could you rephrase it? "
            "I can help you with visas, companies, and laws in Indonesia."
        ),
        "INDONESIAN": (
            "Maaf, saya tidak mengerti permintaan Anda. Bisakah Anda merumuskannya kembali? "
            "Saya dapat membantu Anda dengan visa, perusahaan, dan hukum di Indonesia."
        ),
        "RUSSIAN": (
            "Извините, я не совсем понял ваш запрос. Не могли бы вы сформулировать иначе? "
            "Я помогу с визами, компаниями и законами в Индонезии."
        ),
        "UKRAINIAN": (
            "Вибачте, я не зовсім зрозумів ваш запит. Не могли б ви сформулювати інакше? "
            "Я допоможу з візами, компаніями та законами в Індонезії."
        ),
        "GERMAN": (
            "Entschuldigung, ich habe Ihre Anfrage nicht ganz verstanden. Könnten Sie sie "
            "anders formulieren? Ich kann Ihnen bei Visa, Unternehmen und Gesetzen in "
            "Indonesien helfen."
        ),
        "SPANISH": (
            "Disculpe, no he entendido bien su solicitud. ¿Podría reformularla? "
            "Puedo ayudarle con visados, empresas y leyes en Indonesia."
        ),
    },
}


def get_localized_stub(key: str, language: str) -> str:
    """Resolve (key, language) → stub text.

    Fallback order: requested language → ENGLISH → generic hardcoded message.
    Returns the generic message if the key itself is unknown.

    Logs a warning whenever the requested language is not a direct hit — this
    covers BOTH the deliberately-undeclared-for-translation languages
    (CHINESE/ARABIC/FRENCH — see ``DECLARED_ENGLISH_FALLBACK`` in
    ``test_reasoning_stubs_language_coverage.py``) and a genuinely wrong value
    (e.g. a caller feeding this the lowercase codes
    ``backend.services.communication.language_detector.detect_language``
    emits — 'de', 'es' — instead of the protocol names this table keys on).
    Before 2026-08-23 that second case degraded to English with nothing to
    grep for; a caller wiring the wrong detector into this function now at
    least leaves a trace instead of a silent, undiagnosable language drift.
    """
    lang_stubs = STUB_MESSAGES.get(key, {})
    if language not in lang_stubs:
        logger.warning(
            "get_localized_stub: no %r translation for key=%r — falling back to "
            "ENGLISH. If %r is a language detect_query_language can emit, translate "
            "it here or add it to DECLARED_ENGLISH_FALLBACK on purpose.",
            language,
            key,
            language,
        )
    return lang_stubs.get(language, lang_stubs.get("ENGLISH", _FALLBACK_MESSAGE))
