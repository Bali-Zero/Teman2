"""
I18n template registry for compliance messages.

Dict-based registry (decision #7): TEMPLATE_REGISTRY[category][field][lang] = jinja_source.
Fallback chain: requested_lang → 'en' → 'it' → raise KeyError.

Lang codes: 'it' (Italian), 'en' (English), 'id' (Indonesian).
"""
from __future__ import annotations

from typing import Any

import jinja2

TemplateCategory = str  # "visa_expiry", "lkpm", "tax_filing", ...
TemplateField = str     # "title", "body", "action", "subject"
LangCode = str          # "it", "en", "id"


TEMPLATE_REGISTRY: dict[TemplateCategory, dict[TemplateField, dict[LangCode, str]]] = {
    "visa_expiry": {
        "title": {
            "it": "Visto {{ visa_type }} in scadenza",
            "en": "Visa {{ visa_type }} expiring soon",
            "id": "Visa {{ visa_type }} akan habis",
        },
        "body": {
            "it": (
                "Il visto {{ visa_type }} scadrà tra {{ days_until }} giorni. "
                "Per evitare overstay e sanzioni, avvia il rinnovo subito."
            ),
            "en": (
                "Your {{ visa_type }} visa will expire in {{ days_until }} days. "
                "To avoid overstay penalties, start the renewal process now."
            ),
            "id": (
                "Visa {{ visa_type }} Anda akan habis dalam {{ days_until }} hari. "
                "Untuk menghindari overstay dan denda, segera mulai proses perpanjangan."
            ),
        },
        "action": {
            "it": "Contatta Bali Zero per iniziare il rinnovo",
            "en": "Contact Bali Zero to start the renewal",
            "id": "Hubungi Bali Zero untuk memulai perpanjangan",
        },
    },
    "lkpm": {
        "title": {
            "it": "LKPM {{ period }} — scadenza in avvicinamento",
            "en": "LKPM {{ period }} — deadline approaching",
            "id": "LKPM {{ period }} — tenggat mendekat",
        },
        "body": {
            "it": (
                "Il report LKPM per il periodo {{ period }} è dovuto entro {{ days_until }} giorni. "
                "Prepara i dati di investimento e KBLI attivi."
            ),
            "en": (
                "The LKPM report for {{ period }} is due in {{ days_until }} days. "
                "Prepare investment data and active KBLIs."
            ),
            "id": (
                "Laporan LKPM untuk periode {{ period }} jatuh tempo dalam {{ days_until }} hari. "
                "Siapkan data investasi dan KBLI aktif."
            ),
        },
        "action": {
            "it": "Compila i dati su OSS e sottometti il report",
            "en": "Fill in data on OSS and submit the report",
            "id": "Isi data di OSS dan kirim laporan",
        },
        "readypack_subject": {
            "it": "LKPM {{ period }} — ready-pack generato",
            "en": "LKPM {{ period }} — ready-pack generated",
            "id": "LKPM {{ period }} — ready-pack siap",
        },
        "readypack_body": {
            "it": "Il ready-pack LKPM è pronto. Accedilo su Drive: {{ drive_url }}",
            "en": "Your LKPM ready-pack is ready. Access it on Drive: {{ drive_url }}",
            "id": "Paket LKPM Anda siap. Akses di Drive: {{ drive_url }}",
        },
    },
    "tax_filing": {
        "title": {
            "it": "{{ title }} — scadenza in avvicinamento",
            "en": "{{ title }} — deadline approaching",
            "id": "{{ title }} — tenggat mendekat",
        },
        "body": {
            "it": "Scadenza fra {{ days_until }} giorni. Prepara la documentazione.",
            "en": "Due in {{ days_until }} days. Prepare documentation.",
            "id": "Jatuh tempo dalam {{ days_until }} hari. Siapkan dokumen.",
        },
        "action": {
            "it": "Contatta il team fiscale",
            "en": "Contact the tax team",
            "id": "Hubungi tim pajak",
        },
    },
    "license_renewal": {
        "title": {
            "it": "Rinnovo licenza {{ license_type }}",
            "en": "License renewal: {{ license_type }}",
            "id": "Perpanjangan lisensi: {{ license_type }}",
        },
        "body": {
            "it": "La licenza {{ license_type }} scade tra {{ days_until }} giorni.",
            "en": "License {{ license_type }} expires in {{ days_until }} days.",
            "id": "Lisensi {{ license_type }} habis dalam {{ days_until }} hari.",
        },
        "action": {
            "it": "Avvia la pratica di rinnovo",
            "en": "Start the renewal process",
            "id": "Mulai proses perpanjangan",
        },
    },
    "permit_renewal": {
        "title": {
            "it": "Rinnovo permesso {{ permit_type }}",
            "en": "Permit renewal: {{ permit_type }}",
            "id": "Perpanjangan izin: {{ permit_type }}",
        },
        "body": {
            "it": "Il permesso {{ permit_type }} scade tra {{ days_until }} giorni.",
            "en": "Permit {{ permit_type }} expires in {{ days_until }} days.",
            "id": "Izin {{ permit_type }} habis dalam {{ days_until }} hari.",
        },
        "action": {
            "it": "Prepara la documentazione",
            "en": "Prepare documentation",
            "id": "Siapkan dokumen",
        },
    },
    "regulatory_change": {
        "title": {
            "it": "Aggiornamento normativo: {{ topic }}",
            "en": "Regulatory update: {{ topic }}",
            "id": "Pembaruan regulasi: {{ topic }}",
        },
        "body": {
            "it": "Nuova normativa applicabile. Entra in vigore tra {{ days_until }} giorni.",
            "en": "New regulation applicable. Effective in {{ days_until }} days.",
            "id": "Regulasi baru berlaku. Berlaku dalam {{ days_until }} hari.",
        },
        "action": {
            "it": "Rivedi impatto operativo",
            "en": "Review operational impact",
            "id": "Tinjau dampak operasional",
        },
    },
    "document_expiry": {
        "title": {
            "it": "Documento {{ doc_type }} in scadenza",
            "en": "Document {{ doc_type }} expiring",
            "id": "Dokumen {{ doc_type }} akan habis",
        },
        "body": {
            "it": "Il documento {{ doc_type }} scade tra {{ days_until }} giorni.",
            "en": "Document {{ doc_type }} expires in {{ days_until }} days.",
            "id": "Dokumen {{ doc_type }} habis dalam {{ days_until }} hari.",
        },
        "action": {
            "it": "Rinnova il documento",
            "en": "Renew the document",
            "id": "Perpanjang dokumen",
        },
    },
}


# Shared Jinja env. Templates render plaintext messages for SMS, Telegram,
# in-app notifications and email subject lines — never HTML — so there is no
# XSS surface to escape against. Adding HTML escaping would mangle apostrophes,
# ampersands and quotes inside legitimate Italian/Indonesian copy.
#
# `select_autoescape([])` is the explicit "no autoescape" form recognized by
# both Bandit (B701) and CodeQL (py/jinja2/autoescape-false) — they accept the
# decision when it's made via the documented API, not via the bare keyword.
_jinja_env = jinja2.Environment(
    autoescape=jinja2.select_autoescape(default=False, default_for_string=False),
    undefined=jinja2.StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)

_FALLBACK_CHAIN: tuple[LangCode, ...] = ("en", "it")


def render_template(
    category: TemplateCategory,
    field: TemplateField,
    lang: LangCode,
    **ctx: Any,
) -> str:
    """
    Render a template with Jinja2 interpolation.

    Fallback: if `lang` missing for `(category, field)`, try 'en', then 'it',
    else raise KeyError.

    Raises:
        KeyError: category, field, or all fallback langs missing.
    """
    if category not in TEMPLATE_REGISTRY:
        raise KeyError(f"Unknown template category: {category!r}")
    if field not in TEMPLATE_REGISTRY[category]:
        raise KeyError(f"Unknown template field: {category}.{field}")

    per_lang = TEMPLATE_REGISTRY[category][field]
    source: str | None = per_lang.get(lang)
    if source is None:
        for fb in _FALLBACK_CHAIN:
            source = per_lang.get(fb)
            if source is not None:
                break
    if source is None:
        raise KeyError(f"No template for {category}.{field} in any of {[lang, *_FALLBACK_CHAIN]}")

    return _jinja_env.from_string(source).render(**ctx)


__all__ = ["TEMPLATE_REGISTRY", "render_template", "TemplateCategory", "TemplateField"]
