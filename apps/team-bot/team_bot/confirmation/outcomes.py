"""ConfirmationOutcome — a closed wrapper around ``store.py``'s four
per-stage StrEnums, plus ``render_outcome``: the ONLY place server-authored
confirmation-flow text is produced.

Why a wrapper, not four separate render functions: F6's state machine has
four CAS entry points (propose/confirm/execute/cancel), each returning its
own StrEnum (``ProposeOutcome``/``ConfirmOutcome``/``ExecuteOutcome``/
``CancelOutcome`` — store.py). A caller assembling a reply needs to route on
"which stage, which outcome" as ONE value, not four independently-typed ones
threaded through separately. ``ConfirmationOutcome`` is that single value —
closed (only the four stages, only each stage's own real enum values
validate; a value borrowed from the wrong stage's enum is rejected by the
model_validator below), and its ``.stage``/``.value`` pair is what
``render_outcome`` and (downstream) ``reply_composer.py`` dispatch on.

``render_outcome`` is pure and deterministic: (outcome, action, locale) ->
str, no model call, no randomness, no I/O. It is SERVER-AUTHORED TEXT ONLY —
this is precisely the text ``reply_composer.py``'s ``compose_reply`` uses
when ``confirmation_outcome`` is supplied, and model-generated content is
never consulted for that branch (see that module's docstring). Every
template string here is hand-written and reviewed; nothing here ever
formats a model's own words back into a reply.

Author: Claude Sonnet 5 (lane B3 — team-bot confirmation state machine)
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import PendingAction
from .store import CancelOutcome, ConfirmOutcome, ExecuteOutcome, ProposeOutcome

__all__ = [
    "ConfirmationOutcome",
    "ConfirmationStage",
    "DEFAULT_LOCALE",
    "Locale",
    "render_outcome",
]


class ConfirmationStage(StrEnum):
    """Which of F6's four CAS entry points produced this outcome."""

    PROPOSE = "propose"
    CONFIRM = "confirm"
    EXECUTE = "execute"
    CANCEL = "cancel"


class Locale(StrEnum):
    """The three languages the team bot's staff-facing text ships in — same
    set MANDATE.md names for the client-facing bot (EN/IT/ID)."""

    EN = "en"
    IT = "it"
    ID = "id"


DEFAULT_LOCALE = Locale.EN

# Which real store.py StrEnum a given stage's ``value`` must be a member of —
# the closed-type check below. Deliberately NOT a Union[ProposeOutcome, ...]
# field: several of these enums share raw string values across stages
# (``ConfirmOutcome.NOT_FOUND`` == ``ExecuteOutcome.NOT_FOUND`` ==
# ``CancelOutcome.NOT_FOUND`` == ``"not_found"``), so a bare Union would let
# pydantic silently pick whichever member happens to match first rather than
# the one the caller actually meant — the stage tag is what disambiguates,
# and the validator below enforces that the two always agree.
_STAGE_ENUM: dict[ConfirmationStage, type[StrEnum]] = {
    ConfirmationStage.PROPOSE: ProposeOutcome,
    ConfirmationStage.CONFIRM: ConfirmOutcome,
    ConfirmationStage.EXECUTE: ExecuteOutcome,
    ConfirmationStage.CANCEL: CancelOutcome,
}


class ConfirmationOutcome(BaseModel):
    """A closed (stage, value) pair — ``value`` must be a real member of the
    StrEnum ``stage`` names, never an arbitrary string and never a value
    borrowed from a different stage's enum."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stage: ConfirmationStage
    value: Annotated[str, Field(min_length=1, max_length=64)]

    @model_validator(mode="after")
    def _value_belongs_to_stage(self) -> ConfirmationOutcome:
        enum_cls = _STAGE_ENUM[self.stage]
        try:
            enum_cls(self.value)
        except ValueError as exc:
            raise ValueError(
                f"{self.value!r} is not a valid {enum_cls.__name__} member "
                f"(stage={self.stage!r})"
            ) from exc
        return self

    @classmethod
    def from_propose(cls, outcome: ProposeOutcome) -> ConfirmationOutcome:
        return cls(stage=ConfirmationStage.PROPOSE, value=outcome.value)

    @classmethod
    def from_confirm(cls, outcome: ConfirmOutcome) -> ConfirmationOutcome:
        return cls(stage=ConfirmationStage.CONFIRM, value=outcome.value)

    @classmethod
    def from_execute(cls, outcome: ExecuteOutcome) -> ConfirmationOutcome:
        return cls(stage=ConfirmationStage.EXECUTE, value=outcome.value)

    @classmethod
    def from_cancel(cls, outcome: CancelOutcome) -> ConfirmationOutcome:
        return cls(stage=ConfirmationStage.CANCEL, value=outcome.value)


# ── Templates ────────────────────────────────────────────────────────────
#
# Keyed by (stage, outcome value) -> {locale: template}. Templates for
# outcomes where ``action`` is GUARANTEED present (verified against
# store.py's actual return sites, not assumed — see the module docstring's
# per-stage notes below) may reference ``{code}``/``{tool}``; templates for
# outcomes where ``action`` can be ``None`` (only the four *_NOT_FOUND
# values) never do, so ``render_outcome``'s ``.format(**kwargs)`` never
# raises a KeyError. WRONG_PRINCIPAL deliberately omits ``{code}``/``{tool}``
# even though ``action`` is present — an actor confirming someone else's
# code should learn only that they can't, not what it was for.

_TEMPLATES: dict[ConfirmationStage, dict[str, dict[Locale, str]]] = {
    ConfirmationStage.PROPOSE: {
        # action always present (ProposeResult.action is not Optional).
        ProposeOutcome.CREATED.value: {
            Locale.EN: "Got it — reply CONFERMA {code} within 5 minutes to run {tool}.",
            Locale.IT: "Ricevuto — rispondi CONFERMA {code} entro 5 minuti per eseguire {tool}.",
            Locale.ID: "Diterima — balas KONFIRMASI {code} dalam 5 menit untuk menjalankan {tool}.",
        },
        ProposeOutcome.REPLAYED_SAME_REQUEST.value: {
            Locale.EN: "That request is already open — reply CONFERMA {code} to confirm it.",
            Locale.IT: "Quella richiesta è già aperta — rispondi CONFERMA {code} per confermarla.",
            Locale.ID: "Permintaan itu sudah terbuka — balas KONFIRMASI {code} untuk mengonfirmasi.",
        },
        ProposeOutcome.ACTOR_HAS_PENDING.value: {
            Locale.EN: (
                "You already have an open request awaiting confirmation (code {code}). "
                "Confirm or let it expire before starting a new one."
            ),
            Locale.IT: (
                "Hai già una richiesta aperta in attesa di conferma (codice {code}). "
                "Confermala o lasciala scadere prima di aprirne una nuova."
            ),
            Locale.ID: (
                "Anda sudah memiliki permintaan terbuka yang menunggu konfirmasi (kode {code}). "
                "Konfirmasi atau biarkan kedaluwarsa sebelum memulai yang baru."
            ),
        },
    },
    ConfirmationStage.CONFIRM: {
        ConfirmOutcome.CONFIRMED.value: {
            Locale.EN: "Confirmed — running {tool} now.",
            Locale.IT: "Confermato — eseguo {tool} ora.",
            Locale.ID: "Dikonfirmasi — menjalankan {tool} sekarang.",
        },
        # action is None here (ConfirmResult.action defaults to None only
        # for NOT_FOUND) — no placeholders.
        ConfirmOutcome.NOT_FOUND.value: {
            Locale.EN: "That code wasn't found or has already expired. Ask again to get a new one.",
            Locale.IT: "Codice non trovato o già scaduto. Richiedi di nuovo per ottenerne uno nuovo.",
            Locale.ID: "Kode tidak ditemukan atau sudah kedaluwarsa. Minta lagi untuk mendapatkan kode baru.",
        },
        # action present but deliberately not referenced — see module note.
        ConfirmOutcome.WRONG_PRINCIPAL.value: {
            Locale.EN: "That code isn't yours to confirm.",
            Locale.IT: "Quel codice non è tuo da confermare.",
            Locale.ID: "Kode itu bukan milik Anda untuk dikonfirmasi.",
        },
        ConfirmOutcome.ALREADY_CONFIRMED.value: {
            Locale.EN: "Already confirmed — {tool} will run shortly.",
            Locale.IT: "Già confermato — {tool} verrà eseguito a breve.",
            Locale.ID: "Sudah dikonfirmasi — {tool} akan segera dijalankan.",
        },
        ConfirmOutcome.ALREADY_EXECUTED.value: {
            Locale.EN: "That one's already done — {tool} was completed.",
            Locale.IT: "Quello è già stato fatto — {tool} è stato completato.",
            Locale.ID: "Itu sudah selesai — {tool} telah diselesaikan.",
        },
        ConfirmOutcome.EXPIRED.value: {
            Locale.EN: "That code expired before it was confirmed. Please ask again.",
            Locale.IT: "Quel codice è scaduto prima di essere confermato. Richiedi di nuovo.",
            Locale.ID: "Kode itu kedaluwarsa sebelum dikonfirmasi. Silakan minta lagi.",
        },
        ConfirmOutcome.WRONG_EPOCH.value: {
            Locale.EN: "Couldn't confirm that just now — please try again.",
            Locale.IT: "Non è stato possibile confermare ora — riprova.",
            Locale.ID: "Tidak dapat mengonfirmasi saat ini — silakan coba lagi.",
        },
    },
    ConfirmationStage.EXECUTE: {
        ExecuteOutcome.EXECUTED.value: {
            Locale.EN: "Done — {tool} completed.",
            Locale.IT: "Fatto — {tool} completato.",
            Locale.ID: "Selesai — {tool} telah diselesaikan.",
        },
        ExecuteOutcome.ALREADY_EXECUTED.value: {
            Locale.EN: "Already completed earlier — {tool} was already done.",
            Locale.IT: "Già completato in precedenza — {tool} era già stato fatto.",
            Locale.ID: "Sudah diselesaikan sebelumnya — {tool} sudah dilakukan.",
        },
        ExecuteOutcome.NOT_CONFIRMED.value: {
            Locale.EN: "That request hasn't been confirmed yet.",
            Locale.IT: "Quella richiesta non è ancora stata confermata.",
            Locale.ID: "Permintaan itu belum dikonfirmasi.",
        },
        ExecuteOutcome.EXECUTION_FAILED.value: {
            Locale.EN: "Something went wrong completing {tool} — reply CONFERMA {code} to retry.",
            Locale.IT: "Qualcosa è andato storto completando {tool} — rispondi CONFERMA {code} per riprovare.",
            Locale.ID: "Terjadi kesalahan saat menyelesaikan {tool} — balas KONFIRMASI {code} untuk mencoba lagi.",
        },
        # action is None (ExecuteResult.action defaults to None only for
        # NOT_FOUND) — no placeholders.
        ExecuteOutcome.NOT_FOUND.value: {
            Locale.EN: "That code wasn't found or has already expired.",
            Locale.IT: "Codice non trovato o già scaduto.",
            Locale.ID: "Kode tidak ditemukan atau sudah kedaluwarsa.",
        },
        ExecuteOutcome.INTEGRITY_FAILURE.value: {
            Locale.EN: "Couldn't complete that safely — please start the request again.",
            Locale.IT: "Non è stato possibile completare in sicurezza — avvia di nuovo la richiesta.",
            Locale.ID: "Tidak dapat menyelesaikan dengan aman — silakan mulai permintaan lagi.",
        },
    },
    ConfirmationStage.CANCEL: {
        CancelOutcome.CANCELLED.value: {
            Locale.EN: "Cancelled — {tool} will not run.",
            Locale.IT: "Annullato — {tool} non verrà eseguito.",
            Locale.ID: "Dibatalkan — {tool} tidak akan dijalankan.",
        },
        # action is None (CancelResult.action defaults to None only for
        # NOT_FOUND) — no placeholders.
        CancelOutcome.NOT_FOUND.value: {
            Locale.EN: "That code wasn't found or has already expired.",
            Locale.IT: "Codice non trovato o già scaduto.",
            Locale.ID: "Kode tidak ditemukan atau sudah kedaluwarsa.",
        },
        CancelOutcome.ALREADY_TERMINAL.value: {
            Locale.EN: "That request is already closed and can't be cancelled.",
            Locale.IT: "Quella richiesta è già chiusa e non può essere annullata.",
            Locale.ID: "Permintaan itu sudah ditutup dan tidak dapat dibatalkan.",
        },
    },
}


def render_outcome(
    outcome: ConfirmationOutcome, action: PendingAction | None, locale: Locale = DEFAULT_LOCALE
) -> str:
    """Pure, deterministic, server-authored text — NEVER model content.

    Raises ``ValueError`` if ``(outcome.stage, outcome.value)`` has no
    template (impossible in practice since ``ConfirmationOutcome`` validates
    ``value`` against the stage's real enum and every enum member has an
    entry here — a lint/test enforces that coverage stays complete as new
    outcome values are added) or ``locale`` is missing from a template
    (same — all three locales are always populated together).
    """
    try:
        by_locale = _TEMPLATES[outcome.stage][outcome.value]
    except KeyError as exc:
        raise ValueError(
            f"no template for stage={outcome.stage!r} value={outcome.value!r}"
        ) from exc
    try:
        template = by_locale[locale]
    except KeyError as exc:
        raise ValueError(f"no {locale!r} template for stage={outcome.stage!r} value={outcome.value!r}") from exc

    kwargs = {"code": action.short_code, "tool": action.tool_name} if action is not None else {}
    return template.format(**kwargs)
