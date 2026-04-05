#!/usr/bin/env python3
"""Assign Unassigned Clients — report e assegnazione manuale/interattiva.

REGOLA: questo script NON assegna automaticamente senza conferma esplicita.
In dry-run mostra solo chi è senza assigned_to e suggerisce il team member.
In live-run chiede conferma per ogni batch o per singolo cliente.

Usage:
    python scripts/assign_unassigned_clients.py --dry-run          # lista chi manca
    python scripts/assign_unassigned_clients.py --dry-run --limit 20  # top 20
    python scripts/assign_unassigned_clients.py --assign-to surya@balizero.com --limit 10  # assegna 10 a Surya (chiede confirm)
    python scripts/assign_unassigned_clients.py --round-robin --confirm  # round-robin con confirm

Output in dry-run: tabella clienti senza assigned_to (nome, email, data creazione, practice count).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from itertools import cycle
from pathlib import Path
from typing import Any

import asyncpg

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag",
)

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "crm_assignment.log"

logger = logging.getLogger("crm_assign")
logger.setLevel(logging.INFO)
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
for _h in [logging.FileHandler(LOG_FILE), logging.StreamHandler()]:
    _h.setFormatter(_fmt)
    logger.addHandler(_h)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SETUP_TEAM = [
    "ari.firda@balizero.com",   # Team Leader
    "surya@balizero.com",       # Team Leader
    "krisna@balizero.com",      # Executive Consultant
    "dea@balizero.com",         # Executive Consultant
    "sahira@balizero.com",      # Consultant
    "adit@balizero.com",        # Supervisor
    "vino@balizero.com",        # Junior Consultant
    "damar@balizero.com",       # Junior Consultant
]


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
async def get_unassigned_clients(
    conn: asyncpg.Connection,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Restituisce clienti senza assigned_to, ordinati per data creazione."""
    query = """
        SELECT
            c.id,
            c.uuid,
            c.full_name,
            c.email,
            c.phone,
            c.status,
            c.client_type,
            c.created_at,
            c.first_contact_date,
            COUNT(p.id) AS practice_count,
            MAX(p.status) AS latest_practice_status
        FROM clients c
        LEFT JOIN practices p ON p.client_id = c.id
        WHERE (c.assigned_to IS NULL OR c.assigned_to = '')
          AND c.deleted_at IS NULL
        GROUP BY c.id, c.uuid, c.full_name, c.email, c.phone,
                 c.status, c.client_type, c.created_at, c.first_contact_date
        ORDER BY c.created_at DESC
    """
    if limit:
        query += f" LIMIT {limit}"
    rows = await conn.fetch(query)
    return [dict(r) for r in rows]


async def get_team_workload(conn: asyncpg.Connection) -> dict[str, int]:
    """Conta clienti assegnati per team member."""
    rows = await conn.fetch(
        """
        SELECT assigned_to, COUNT(*) AS client_count
        FROM clients
        WHERE assigned_to IS NOT NULL AND assigned_to != ''
          AND deleted_at IS NULL
        GROUP BY assigned_to
        ORDER BY client_count DESC
        """
    )
    return {r["assigned_to"]: r["client_count"] for r in rows}


async def assign_client(
    conn: asyncpg.Connection,
    client_id: int,
    team_email: str,
) -> None:
    """Esegue l'assegnazione di un singolo cliente."""
    await conn.execute(
        "UPDATE clients SET assigned_to = $1, updated_at = NOW() WHERE id = $2",
        team_email, client_id,
    )


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------
def print_table(clients: list[dict[str, Any]]) -> None:
    """Stampa tabella clienti non assegnati."""
    if not clients:
        print("✅ Nessun cliente senza assigned_to.")
        return

    print(f"\n{'ID':<6} {'Nome':<30} {'Email':<35} {'Status':<15} {'Practices':<10} {'Creato':<12}")
    print("-" * 110)
    for c in clients:
        created = c["created_at"].strftime("%Y-%m-%d") if c["created_at"] else "N/A"
        name = (c["full_name"] or "N/A")[:28]
        email = (c["email"] or "N/A")[:33]
        status = (c["status"] or "N/A")[:13]
        print(f"{c['id']:<6} {name:<30} {email:<35} {status:<15} {c['practice_count']:<10} {created:<12}")


def print_workload(workload: dict[str, int]) -> None:
    """Stampa workload corrente del team."""
    print("\n📊 Team workload corrente:")
    for email, count in sorted(workload.items(), key=lambda x: x[1]):
        bar = "█" * min(count // 5, 20)
        print(f"  {email:<35} {count:>4} clienti  {bar}")

    # Mostra anche chi è in SETUP_TEAM ma non ha clienti
    assigned_emails = set(workload.keys())
    for email in SETUP_TEAM:
        if email not in assigned_emails:
            print(f"  {email:<35}    0 clienti")


def suggest_round_robin(
    unassigned: list[dict[str, Any]],
    workload: dict[str, int],
) -> list[tuple[dict[str, Any], str]]:
    """Suggerisce assegnazioni round-robin bilanciando il workload."""
    # Ordina team per workload attuale (meno carichi prima)
    team_sorted = sorted(SETUP_TEAM, key=lambda e: workload.get(e, 0))
    team_cycle = cycle(team_sorted)
    suggestions = []
    for client in unassigned:
        assignee = next(team_cycle)
        suggestions.append((client, assignee))
    return suggestions


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main(
    dry_run: bool,
    limit: int | None,
    assign_to: str | None,
    round_robin: bool,
    confirm: bool,
) -> None:
    logger.info("=" * 60)
    logger.info(f"CRM Assignment — {'DRY RUN' if dry_run else 'LIVE RUN'} — {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 60)

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        unassigned = await get_unassigned_clients(conn, limit=limit)
        workload = await get_team_workload(conn)

        total_unassigned = await conn.fetchval(
            "SELECT COUNT(*) FROM clients WHERE (assigned_to IS NULL OR assigned_to = '') AND deleted_at IS NULL"
        )

        print(f"\n📋 Clienti senza assigned_to: {total_unassigned} totali")
        if limit and len(unassigned) < total_unassigned:
            print(f"   (mostrando i primi {limit})")

        print_workload(workload)
        print_table(unassigned)

        if not unassigned:
            return

        # ----------------------------------------------------------------
        # Dry-run: solo report + suggerimento
        # ----------------------------------------------------------------
        if dry_run:
            if round_robin:
                suggestions = suggest_round_robin(unassigned, workload)
                print("\n💡 Suggerimento round-robin (se eseguissi --round-robin --confirm):")
                for client, assignee in suggestions:
                    print(f"   Client #{client['id']} {client['full_name']:<28} → {assignee}")
            elif assign_to:
                print(f"\n💡 Clienti che verrebbero assegnati a {assign_to}:")
                for c in unassigned:
                    print(f"   #{c['id']} {c['full_name']}")
            else:
                print("\n💡 Opzioni disponibili:")
                print("   --assign-to EMAIL [--limit N]   → assegna N clienti a un membro del team")
                print("   --round-robin --confirm          → distribuisce round-robin (con conferma)")
            print("\n⚠️  DRY RUN — nessuna modifica al DB. Aggiungi --confirm per applicare.")
            return

        # ----------------------------------------------------------------
        # Live run: chiede conferma
        # ----------------------------------------------------------------
        if assign_to:
            if assign_to not in SETUP_TEAM:
                logger.error(f"Email '{assign_to}' non è nel SETUP_TEAM. Validi: {SETUP_TEAM}")
                sys.exit(1)

            print(f"\n⚠️  Stai per assegnare {len(unassigned)} clienti a: {assign_to}")
            if not confirm:
                answer = input("Confermi? (s/N): ").strip().lower()
                if answer not in ("s", "si", "y", "yes"):
                    print("Annullato.")
                    return

            assigned = 0
            for client in unassigned:
                await assign_client(conn, client["id"], assign_to)
                assigned += 1
                logger.info(f"  assegnato client #{client['id']} {client['full_name']} → {assign_to}")

            logger.info(f"✅ {assigned} clienti assegnati a {assign_to}")

        elif round_robin:
            suggestions = suggest_round_robin(unassigned, workload)
            print(f"\n⚠️  Stai per assegnare {len(suggestions)} clienti (round-robin):")
            for client, assignee in suggestions[:10]:
                print(f"   #{client['id']} {client['full_name']:<28} → {assignee}")
            if len(suggestions) > 10:
                print(f"   ... e altri {len(suggestions) - 10}")

            if not confirm:
                answer = input("Confermi? (s/N): ").strip().lower()
                if answer not in ("s", "si", "y", "yes"):
                    print("Annullato.")
                    return

            assigned = 0
            for client, assignee in suggestions:
                await assign_client(conn, client["id"], assignee)
                assigned += 1
                logger.info(f"  assegnato client #{client['id']} → {assignee}")

            logger.info(f"✅ {assigned} clienti assegnati (round-robin)")

        else:
            print("\n❌ Specifica --assign-to EMAIL o --round-robin per eseguire l'assegnazione.")
            print("   Usa --dry-run per preview senza modifiche.")

    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CRM Assign Unassigned Clients")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no DB writes")
    parser.add_argument("--limit", type=int, help="Numero max clienti da mostrare/processare")
    parser.add_argument("--assign-to", metavar="EMAIL", help="Assegna tutti al team member specificato")
    parser.add_argument("--round-robin", action="store_true", help="Distribuisci round-robin al team")
    parser.add_argument("--confirm", action="store_true", help="Salta conferma interattiva (per script)")
    args = parser.parse_args()

    if not args.dry_run and not args.assign_to and not args.round_robin:
        # Default safe: dry-run se nessuna azione specificata
        print("ℹ️  Nessuna azione specificata — eseguo in dry-run. Usa --assign-to o --round-robin per assegnare.")
        args.dry_run = True

    asyncio.run(main(
        dry_run=args.dry_run,
        limit=args.limit,
        assign_to=args.assign_to,
        round_robin=args.round_robin,
        confirm=args.confirm,
    ))
