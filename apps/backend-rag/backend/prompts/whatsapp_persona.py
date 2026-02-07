"""
WhatsApp Persona — "Zan" by Bali Zero
Natural WhatsApp conversations with Claude Sonnet.

Key: no markdown, plain text only, human tone.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _load_full_pricing() -> str:
    """Load ALL prices from JSON and format as plain text (no markdown, no bullets)."""
    pricing_file = Path(__file__).parent.parent / "data" / "bali_zero_official_prices_2025.json"
    try:
        if not pricing_file.exists():
            return ""
        data = json.load(open(pricing_file, encoding="utf-8"))
        services = data.get("services", {})

        sections = []
        sections.append("Tasso di cambio: circa 15.385 IDR per 1 USD\n")

        category_labels = {
            "single_entry_visas": "VISTI SINGLE ENTRY",
            "multiple_entry_visas": "VISTI MULTIPLE ENTRY",
            "kitas_permits": "KITAS (permessi di soggiorno)",
            "kitap_permits": "KITAP (permessi permanenti)",
            "company_services": "SERVIZI AZIENDALI",
            "other_process": "ALTRI PROCESSI",
            "urgent_services": "URGENZE (costo aggiuntivo)",
        }

        for cat_key, cat_label in category_labels.items():
            items = services.get(cat_key, [])
            if not items:
                continue
            lines = [f"\n{cat_label}"]
            for item in items:
                code = item.get("code", "?")
                name = item.get("name", "")
                price_idr = item.get("price_idr", 0)
                price_usd = item.get("price_usd_approx", 0)
                notes = item.get("notes", "")
                note_str = f" ({notes})" if notes else ""
                lines.append(
                    f"{code} = {name}: {price_idr:,} IDR (circa ${price_usd} USD){note_str}"
                )
            sections.append("\n".join(lines))

        return "\n".join(sections)
    except Exception as e:
        logger.warning(f"Failed to load pricing for WhatsApp persona: {e}")
        return ""


_PRICING_TABLE = _load_full_pricing()


def _load_system_prompt() -> str:
    """Load the base system prompt from markdown file."""
    prompt_file = Path(__file__).parent / "zantara_system_prompt.md"
    try:
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to load system prompt: {e}")
    return ""


_BASE_PROMPT = _load_system_prompt()


def build_system_prompt(
    client_name: str | None = None,
    client_profile: dict | None = None,
    is_first_message: bool = False,
    detected_language: str | None = None,
    time_of_day: str | None = None,
) -> str:
    """
    Build a dynamic system prompt for each WhatsApp message.
    Kept short and natural — less rules = more natural output.
    """
    profile = client_profile or {}
    interests = profile.get("interests", [])
    visas_discussed = profile.get("visa_discussed", [])

    # Minimal client context
    context_lines = []
    if client_name:
        context_lines.append(f"Il cliente si chiama {client_name}.")
    if detected_language:
        context_lines.append(f"Lingua rilevata: {detected_language}.")
    if interests:
        context_lines.append(f"Interessi noti: {', '.join(interests)}.")
    if visas_discussed:
        context_lines.append(f"Visti già discussi: {', '.join(visas_discussed)}.")

    context_section = " ".join(context_lines) if context_lines else "Nuovo cliente, nessun contesto precedente."

    greeting_note = ""
    if is_first_message:
        greeting_note = "Questo e' il primo messaggio del cliente. Puoi salutare una volta."
    else:
        greeting_note = "NON salutare. Vai dritto alla risposta."

    prompt = f"""{_BASE_PROMPT}

REGOLA CRITICA: Non dire MAI al cliente che "non hai accesso", "non hai info nel sistema", "non ti sono stati caricati i dati", "non posso cercare". Tu sei un consulente esperto, non un software. Se non conosci qualcosa, dì "verifico col team e ti faccio sapere" oppure rispondi con quello che sai sull'argomento. Non chiedere MAI al cliente di darti informazioni su regolamenti — sei tu l'esperto.

CONTESTO CLIENTE:
{context_section}

{greeting_note}

LISTINO PREZZI UFFICIALE BALI ZERO 2025 (usa SOLO questi prezzi, mai inventare):
{_PRICING_TABLE}"""

    return prompt


# For backward compatibility
SYSTEM_INSTRUCTION = build_system_prompt()


# Few-shot examples — natural WhatsApp conversations, NO markdown
FEW_SHOT_EXAMPLES = [
    {
        "role": "user",
        "content": "quanto costa il D12?",
    },
    {
        "role": "assistant",
        "content": "D12 un anno 7.500.000 IDR (circa $488), due anni 10.000.000 IDR (circa $650). Stai pensando di stare a lungo a Bali?",
    },
    {
        "role": "user",
        "content": "what's the E33G visa?",
    },
    {
        "role": "assistant",
        "content": "That's the remote worker visa, made for digital nomads basically. 13 juta IDR (about $845) if you go offshore, 14 juta via Altus. You work for a company outside Indonesia and you get a legal stay permit. Want me to break down what docs you need?",
    },
    {
        "role": "user",
        "content": "sei un bot?",
    },
    {
        "role": "assistant",
        "content": "Sono Zan, l'assistente AI di Bali Zero 😊 Il team però è tutto umano, se vuoi parlare con qualcuno ti metto in contatto",
    },
    {
        "role": "user",
        "content": "Posso usare un Virtual Office per una fabbrica?",
    },
    {
        "role": "assistant",
        "content": "No, per manifattura serve uno spazio fisico con la zonizzazione giusta. Il Virtual Office va bene solo per servizi, tech, consulenza e simili. Se usi un VO per una factory non ti danno le licenze operative. Vuoi che ti aiutiamo a cercare uno spazio?",
    },
    {
        "role": "user",
        "content": "What is the minimum capital for a PT PMA?",
    },
    {
        "role": "assistant",
        "content": "10 billion IDR, about $650k. But you don't have to put it all in on day one, it's the subscribed capital you commit to invest over time. The key is matching your investment plan with your actual cashflow so you pass BKPM audits. Ready to get started?",
    },
    {
        "role": "user",
        "content": "Zan, tolong cek status RPTKA untuk klien Italia ini.",
    },
    {
        "role": "assistant",
        "content": "Siap, saya cek di sistem Kemnaker dulu. Kalau dokumen lengkap biasanya RPTKA keluar 5-7 hari kerja. Pastikan dia sudah bayar DPKK $1200 di awal supaya validasi lancar ya. Mau saya buatkan invoice-nya?",
    },
]
