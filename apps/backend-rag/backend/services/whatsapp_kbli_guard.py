"""Deterministic WhatsApp guardrails for high-risk KBLI villa answers."""

from __future__ import annotations

import re
from dataclasses import dataclass

_KBLI_CODE_RE = re.compile(r"\b\d{5}\b")
_UNRELATED_OFF_TOPIC_CODES = frozenset(
    {
        "20113",
        "20291",
        "43224",
        "52322",
        "59201",
        "61106",
        "65201",
    }
)
_VILLA_TERMS = (
    "airbnb",
    "akomodasi",
    "alloggio",
    "booking",
    "holiday rental",
    "otel",
    "ota",
    "rent",
    "rental",
    "sewa",
    "short stay",
    "short-term",
    "villa",
    "vila",
    "ville",
)
_KBLI_TERMS = ("kbli", "code", "codes", "codice", "codici", "kode")
_COMPARE_TERMS = (
    "beda",
    "compare",
    "difference",
    "differenza",
    "mana",
    "qual",
    "quale",
    "vs",
)
_MAPPING_TERMS = (
    "2020",
    "2025",
    "legacy",
    "mappa",
    "mappato",
    "mapped",
    "mapping",
    "pp28",
    "renumber",
    "rinumer",
    "source",
    "sorgente",
    "vecchio",
)


@dataclass(frozen=True)
class KbliGuardResult:
    """Result of a deterministic KBLI WhatsApp response check."""

    reply: str
    corrected: bool
    reason: str | None = None


def _normalize(value: str) -> str:
    return (
        value.casefold()
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )


def _contains_any(value: str, terms: tuple[str, ...]) -> bool:
    return any(term in value for term in terms)


def _codes_in(value: str) -> set[str]:
    return set(_KBLI_CODE_RE.findall(value))


def is_villa_kbli_query(message_text: str) -> bool:
    """Return True for villa/Airbnb KBLI questions that need strict handling."""
    normalized = _normalize(message_text)
    codes = _codes_in(normalized)

    if {"55193", "55203"}.issubset(codes):
        return True

    if (codes & {"55193", "55203"}) and _contains_any(normalized, _COMPARE_TERMS):
        return True

    if _contains_any(normalized, _KBLI_TERMS) and _contains_any(normalized, _VILLA_TERMS):
        return True

    if (codes & {"55193", "55203", "55901", "55400"}) and _contains_any(
        normalized,
        _VILLA_TERMS,
    ):
        return True

    return False


def _language_for(message_text: str, detected_language: str | None) -> str:
    language = (detected_language or "").casefold()
    if language.startswith(("it", "id", "en")):
        return language[:2]

    normalized = _normalize(message_text)
    if any(term in normalized for term in ("quanto", "differenza", "codice", "ville")):
        return "it"
    if any(term in normalized for term in ("berapa", "kode", "mana", "sewa", "vila")):
        return "id"
    return "en"


def _villa_kbli_answer(language: str) -> str:
    if language == "id":
        return (
            "Perbedaannya begini:\n\n"
            "55203 - AKTIVITAS VILA: kode KBLI 2025 yang dipakai sebagai arah utama "
            "untuk villa/Airbnb jika perusahaan mengoperasikan villa sebagai akomodasi "
            "jangka pendek.\n\n"
            "55193: bukan kode villa 2025 yang dipilih terpisah. Di dataset kami, ini "
            "kode sumber KBLI 2020/PP28 yang dipetakan ke 55203 di KBLI 2025.\n\n"
            "Kalau hanya mengelola villa milik pihak ketiga dengan management fee, cek "
            "55901. Kalau modelnya platform/intermediasi akomodasi, cek 55400. Finalnya "
            "tetap perlu diverifikasi dari model bisnis, lease/ownership, zoning, dan OSS/NIB."
        )

    if language == "en":
        return (
            "The practical difference is:\n\n"
            "55203 - AKTIVITAS VILA: the KBLI 2025 code to check first for villas/Airbnb "
            "when the company operates the villa as short-stay accommodation.\n\n"
            "55193: not a separate current villa code to choose in KBLI 2025. In our "
            "dataset it is the KBLI 2020/PP28 source code that maps to 55203 in KBLI 2025.\n\n"
            "If you manage third-party villas for a management fee, check 55901. If the "
            "model is accommodation intermediation/platform/booking, check 55400. The final "
            "code still depends on the operating model, lease/ownership, zoning, and OSS/NIB."
        )

    return (
        "La differenza pratica e' questa:\n\n"
        "55203 - AKTIVITAS VILA: e' il codice KBLI 2025 da verificare per ville/Airbnb "
        "quando la societa' opera la villa come alloggio breve.\n\n"
        "55193: non e' un secondo codice villa 2025 da scegliere. Nel nostro dataset e' "
        "il codice sorgente KBLI 2020/PP28 che mappa a 55203 nel KBLI 2025.\n\n"
        "Se invece gestisci ville di terzi con management fee, va verificato 55901. Se il "
        "modello e' piattaforma/intermediazione/prenotazione accommodation, va verificato "
        "55400. Il codice finale dipende comunque da modello operativo, lease/ownership, "
        "zoning e OSS/NIB."
    )


def _reply_explains_55193_55203_mapping(reply: str) -> bool:
    normalized = _normalize(reply)
    codes = _codes_in(normalized)
    return (
        {"55193", "55203"}.issubset(codes)
        and _contains_any(normalized, _MAPPING_TERMS)
        and ("villa" in normalized or "vila" in normalized)
    )


def _reply_needs_villa_kbli_correction(message_text: str, reply: str) -> str | None:
    if not is_villa_kbli_query(message_text):
        return None

    normalized_reply = _normalize(reply)
    reply_codes = _codes_in(normalized_reply)
    message_codes = _codes_in(_normalize(message_text))

    off_topic_codes = sorted(reply_codes & _UNRELATED_OFF_TOPIC_CODES)
    if off_topic_codes:
        return "off_topic_kbli_codes:" + ",".join(off_topic_codes)

    if {"55193", "55203"}.issubset(message_codes) and not _reply_explains_55193_55203_mapping(
        reply,
    ):
        return "missing_55193_to_55203_mapping"

    if "55193" in reply_codes and not _reply_explains_55193_55203_mapping(reply):
        return "legacy_55193_without_2025_mapping"

    if _contains_any(_normalize(message_text), _VILLA_TERMS) and "55203" not in reply_codes:
        return "villa_query_without_55203"

    return None


def sanitize_whatsapp_kbli_reply(
    *,
    message_text: str,
    reply: str,
    detected_language: str | None = None,
) -> KbliGuardResult:
    """Replace unsafe villa KBLI replies with a canonical client-safe answer."""
    reason = _reply_needs_villa_kbli_correction(message_text, reply)
    if reason is None:
        return KbliGuardResult(reply=reply, corrected=False)

    language = _language_for(message_text, detected_language)
    return KbliGuardResult(
        reply=_villa_kbli_answer(language),
        corrected=True,
        reason=reason,
    )
