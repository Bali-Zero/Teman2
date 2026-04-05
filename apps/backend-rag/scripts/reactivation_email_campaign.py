#!/usr/bin/env python3
"""Reactivation Email Campaign — campagna email per clienti inattivi/prospect.

Segmenti disponibili:
  urgent     → clienti con practice in scadenza entro 90gg, non contattati di recente
  inactive   → clienti status=inactive senza pratiche attive (>6 mesi)
  prospect   → clienti status=prospect senza pratica (mai iniziato)
  stale      → clienti active ma last_interaction > 60gg fa

In dry-run: mostra lista + anteprima email per ogni segmento.
In live-run: invia email via API interna (zantara@balizero.com → Brevo).

Usage:
    python scripts/reactivation_email_campaign.py --dry-run --segment urgent
    python scripts/reactivation_email_campaign.py --dry-run --segment all
    python scripts/reactivation_email_campaign.py --segment urgent --limit 50 --confirm
    python scripts/reactivation_email_campaign.py --segment inactive --limit 20 --confirm
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import asyncpg
import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag",
)
BACKEND_URL = os.environ.get("BACKEND_URL", "https://nuzantara-rag.fly.dev")
EMAIL_API_KEY = os.environ.get("INTERNAL_API_KEY", "zantara-secret-2024")

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "crm_reactivation.log"

logger = logging.getLogger("crm_reactivation")
logger.setLevel(logging.INFO)
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
for _h in [logging.FileHandler(LOG_FILE), logging.StreamHandler()]:
    _h.setFormatter(_fmt)
    logger.addHandler(_h)

# ---------------------------------------------------------------------------
# Email templates
# ---------------------------------------------------------------------------

TEMPLATES: dict[str, dict[str, str]] = {
    "urgent": {
        "subject": "⚠️ Il tuo {practice_type} scade il {expiry_date} — Rinnova ora",
        "body": """\
Ciao {name},

Il tuo {practice_type} è in scadenza il {expiry_date}.

Per evitare complicazioni, ti consigliamo di avviare il processo di rinnovo al più presto.
Il rinnovo richiede solitamente 4–8 settimane.

📞 Contattaci subito:
• WhatsApp: wa.me/6281337777xxx
• Email: zero@balizero.com
• Web: https://kita.balizero.com

Il nostro team è pronto ad assisterti.

Con i migliori saluti,
Team Bali Zero
""",
    },
    "inactive": {
        "subject": "Sei ancora a Bali? Siamo qui per aiutarti",
        "body": """\
Ciao {name},

Siamo Bali Zero, e ci siamo accorti che non ci sentiamo da un po'.

Se hai bisogno di supporto per visa, azienda, tasse o proprietà a Bali,
siamo qui — con un team dedicato e oltre 5.000 clienti assistiti.

🌴 Cosa possiamo fare per te oggi?
• Rinnovo o cambio visto
• Apertura o gestione azienda
• Consulenza fiscale Indonesia
• Ricerca o acquisto proprietà

📩 Rispondi a questa email o scrivici su WhatsApp.

Con i migliori saluti,
Team Bali Zero
""",
    },
    "prospect": {
        "subject": "Stai pensando di vivere o investire a Bali?",
        "body": """\
Ciao {name},

Grazie per aver contattato Bali Zero in passato.

Hai ancora bisogno di supporto per il tuo progetto a Bali?
Che si tratti di un visto, un'azienda o un investimento immobiliare,
il nostro team è pronto a guidarti passo dopo passo.

🎯 Prima consulenza gratuita — senza impegno.

📩 Rispondi a questa email oppure prenota una call:
https://kita.balizero.com/contact

Con i migliori saluti,
Team Bali Zero
""",
    },
    "stale": {
        "subject": "Aggiornamento sul tuo percorso con Bali Zero",
        "body": """\
Ciao {name},

Volevo fare un check-in e assicurarmi che tutto vada bene.

Se hai domande su visa, azienda, tasse o qualsiasi aspetto della vita a Bali,
sono qui per aiutarti.

Puoi rispondere direttamente a questa email o scrivermi su WhatsApp.

Con i migliori saluti,
Team Bali Zero
""",
    },
}


# ---------------------------------------------------------------------------
# Segment queries
# ---------------------------------------------------------------------------
async def get_urgent_segment(
    conn: asyncpg.Connection,
    limit: int | None,
) -> list[dict[str, Any]]:
    """Clienti con practice in scadenza entro 90gg."""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=90)
    query = """
        SELECT DISTINCT ON (c.id)
            c.id, c.full_name, c.email, c.phone,
            c.assigned_to, c.last_interaction_date,
            p.id AS practice_id, p.status AS practice_status,
            pt.name AS practice_type, p.expiry_date
        FROM clients c
        JOIN practices p ON p.client_id = c.id
        LEFT JOIN practice_types pt ON pt.id = p.practice_type_id
        WHERE c.email IS NOT NULL AND c.email != ''
          AND c.deleted_at IS NULL
          AND p.expiry_date BETWEEN $1 AND $2
          AND p.status NOT IN ('completed', 'cancelled', 'pending_renewal')
        ORDER BY c.id, p.expiry_date ASC
    """
    if limit:
        query += f" LIMIT {limit}"
    rows = await conn.fetch(query, now, cutoff)
    return [dict(r) for r in rows]


async def get_inactive_segment(
    conn: asyncpg.Connection,
    limit: int | None,
) -> list[dict[str, Any]]:
    """Clienti status=inactive senza pratiche attive da >180gg."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=180)
    query = """
        SELECT
            c.id, c.full_name, c.email, c.phone,
            c.assigned_to, c.last_interaction_date, c.updated_at,
            COUNT(p.id) FILTER (WHERE p.status NOT IN ('completed', 'cancelled', 'expired')) AS active_practices
        FROM clients c
        LEFT JOIN practices p ON p.client_id = c.id
        WHERE c.email IS NOT NULL AND c.email != ''
          AND c.deleted_at IS NULL
          AND c.status = 'inactive'
          AND (c.last_interaction_date IS NULL OR c.last_interaction_date < $1)
        GROUP BY c.id, c.full_name, c.email, c.phone,
                 c.assigned_to, c.last_interaction_date, c.updated_at
        HAVING COUNT(p.id) FILTER (WHERE p.status NOT IN ('completed', 'cancelled', 'expired')) = 0
        ORDER BY c.last_interaction_date ASC NULLS FIRST
    """
    if limit:
        query += f" LIMIT {limit}"
    rows = await conn.fetch(query, cutoff)
    return [dict(r) for r in rows]


async def get_prospect_segment(
    conn: asyncpg.Connection,
    limit: int | None,
) -> list[dict[str, Any]]:
    """Clienti status=prospect senza nessuna pratica avviata."""
    query = """
        SELECT
            c.id, c.full_name, c.email, c.phone,
            c.assigned_to, c.created_at, c.last_interaction_date,
            COUNT(p.id) AS practice_count
        FROM clients c
        LEFT JOIN practices p ON p.client_id = c.id
        WHERE c.email IS NOT NULL AND c.email != ''
          AND c.deleted_at IS NULL
          AND c.status = 'prospect'
        GROUP BY c.id, c.full_name, c.email, c.phone,
                 c.assigned_to, c.created_at, c.last_interaction_date
        HAVING COUNT(p.id) = 0
        ORDER BY c.created_at DESC
    """
    if limit:
        query += f" LIMIT {limit}"
    rows = await conn.fetch(query)
    return [dict(r) for r in rows]


async def get_stale_segment(
    conn: asyncpg.Connection,
    limit: int | None,
) -> list[dict[str, Any]]:
    """Clienti active con last_interaction > 60gg fa."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=60)
    query = """
        SELECT
            c.id, c.full_name, c.email, c.phone,
            c.assigned_to, c.last_interaction_date, c.status,
            COUNT(p.id) FILTER (WHERE p.status NOT IN ('completed', 'cancelled')) AS active_practices
        FROM clients c
        LEFT JOIN practices p ON p.client_id = c.id
        WHERE c.email IS NOT NULL AND c.email != ''
          AND c.deleted_at IS NULL
          AND c.status = 'active'
          AND (c.last_interaction_date IS NULL OR c.last_interaction_date < $1)
        GROUP BY c.id, c.full_name, c.email, c.phone,
                 c.assigned_to, c.last_interaction_date, c.status
        ORDER BY c.last_interaction_date ASC NULLS FIRST
    """
    if limit:
        query += f" LIMIT {limit}"
    rows = await conn.fetch(query, cutoff)
    return [dict(r) for r in rows]


SEGMENT_FNS = {
    "urgent": get_urgent_segment,
    "inactive": get_inactive_segment,
    "prospect": get_prospect_segment,
    "stale": get_stale_segment,
}


# ---------------------------------------------------------------------------
# Email builder
# ---------------------------------------------------------------------------
def build_email(segment: str, client: dict[str, Any]) -> dict[str, str]:
    """Costruisce subject + body per un cliente."""
    tmpl = TEMPLATES[segment]
    name = (client.get("full_name") or "").split()[0] if client.get("full_name") else "Cliente"

    # Dati specifici per segmento urgent
    practice_type = client.get("practice_type") or "pratica"
    expiry_date = ""
    if client.get("expiry_date"):
        expiry_date = client["expiry_date"].strftime("%d/%m/%Y")

    subject = tmpl["subject"].format(
        name=name,
        practice_type=practice_type,
        expiry_date=expiry_date,
    )
    body = tmpl["body"].format(
        name=name,
        practice_type=practice_type,
        expiry_date=expiry_date,
    )
    return {"subject": subject, "body": body, "to": client["email"]}


# ---------------------------------------------------------------------------
# Email sender
# ---------------------------------------------------------------------------
async def send_email(
    http_client: httpx.AsyncClient,
    to: str,
    subject: str,
    body: str,
) -> bool:
    """Invia email via API interna."""
    try:
        resp = await http_client.post(
            f"{BACKEND_URL}/api/notifications/send-email",
            json={
                "to": to,
                "subject": subject,
                "body": body,
                "from": "zantara@balizero.com",
                "from_name": "Bali Zero",
            },
            headers={"X-API-Key": EMAIL_API_KEY},
            timeout=30,
        )
        if resp.status_code == 200:
            return True
        logger.warning(f"  Email API error {resp.status_code} for {to}: {resp.text[:100]}")
        return False
    except httpx.HTTPError as e:
        logger.error(f"  HTTP error sending to {to}: {e}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def run_segment(
    conn: asyncpg.Connection,
    segment: str,
    dry_run: bool,
    limit: int | None,
    confirm: bool,
) -> dict[str, int]:
    fn = SEGMENT_FNS[segment]
    clients = await fn(conn, limit=limit)

    logger.info(f"\n▶ Segmento '{segment}': {len(clients)} clienti trovati")

    if not clients:
        return {"segment": 0, "sent": 0, "errors": 0}

    # Preview prime 3 email
    print(f"\n{'=' * 60}")
    print(f"Segmento: {segment.upper()} — {len(clients)} clienti")
    print("Anteprima prima email:")
    email_preview = build_email(segment, clients[0])
    print(f"  To: {email_preview['to']}")
    print(f"  Subject: {email_preview['subject']}")
    print(f"  Body (primi 200 chars): {email_preview['body'][:200].strip()}...")
    print()

    if dry_run:
        print(f"⚠️  DRY RUN — {len(clients)} email NON inviate.")
        for c in clients[:10]:
            e = build_email(segment, c)
            print(f"  [{c['id']}] {(c.get('full_name') or 'N/A'):<28} → {e['to']}")
        if len(clients) > 10:
            print(f"  ... e altri {len(clients) - 10}")
        return {"segment": len(clients), "sent": 0, "errors": 0}

    # Conferma prima di inviare
    if not confirm:
        answer = input(f"\nConfermi invio di {len(clients)} email per segmento '{segment}'? (s/N): ").strip().lower()
        if answer not in ("s", "si", "y", "yes"):
            print("Annullato.")
            return {"segment": len(clients), "sent": 0, "errors": 0}

    sent = 0
    errors = 0
    async with httpx.AsyncClient() as http_client:
        for client in clients:
            if not client.get("email"):
                errors += 1
                continue
            email = build_email(segment, client)
            ok = await send_email(http_client, email["to"], email["subject"], email["body"])
            if ok:
                sent += 1
                logger.info(f"  ✅ email inviata → {email['to']} ({client.get('full_name')})")
            else:
                errors += 1
                logger.warning(f"  ❌ errore → {email['to']}")
            # Rate limit: max 10/min → 6s delay
            await asyncio.sleep(6)

    logger.info(f"[{segment}] sent={sent}, errors={errors}")
    return {"segment": len(clients), "sent": sent, "errors": errors}


async def main(
    dry_run: bool,
    segment: str,
    limit: int | None,
    confirm: bool,
) -> None:
    logger.info("=" * 60)
    logger.info(f"CRM Reactivation Campaign — {'DRY RUN' if dry_run else 'LIVE RUN'}")
    logger.info(f"Segment: {segment} | Limit: {limit} | {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 60)

    segments_to_run = list(SEGMENT_FNS.keys()) if segment == "all" else [segment]

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        total_results: dict[str, dict[str, int]] = {}
        for seg in segments_to_run:
            result = await run_segment(conn, seg, dry_run, limit, confirm)
            total_results[seg] = result

        print("\n" + "=" * 60)
        print("📊 Report finale:")
        for seg, res in total_results.items():
            print(f"   {seg:<12} found={res['segment']:>4}  sent={res['sent']:>4}  errors={res['errors']:>3}")
        if dry_run:
            print("\n⚠️  DRY RUN — nessuna email inviata. Usa --confirm per inviare.")

    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CRM Reactivation Email Campaign")
    parser.add_argument(
        "--segment",
        choices=[*list(SEGMENT_FNS.keys()), "all"],
        default="urgent",
        help="Segmento clienti da targetizzare",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no email sent")
    parser.add_argument("--limit", type=int, help="Max email da inviare per segmento")
    parser.add_argument("--confirm", action="store_true", help="Salta conferma interattiva")
    args = parser.parse_args()
    asyncio.run(main(
        dry_run=args.dry_run,
        segment=args.segment,
        limit=args.limit,
        confirm=args.confirm,
    ))
