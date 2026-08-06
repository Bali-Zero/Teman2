#!/usr/bin/env python3
"""wa_session_liveness.py — dice quando una linea wa-mirror ha smesso di catturare.

WHY (2026-08-06): una sessione WhatsApp revocata NON ha nessun guardiano. Il
processo resta `already running`, il PID è vivo, launchd è verde — e la linea
non registra piu una riga. Misurato quel giorno: **due linee su sette erano
morte**, Ari da 8 giorni e vino da 10, e nessun segnale e mai partito. Ari e
stata scoperta solo perche il CTA dei lead le puntava contro; vino non
l'avrebbe trovata nessuno. Il PID non e la prova: la riga scritta si.

COSA MISURA — il LAVORO, non lo stato:
  `max(message_date)` per linea su `whatsapp_message_context`, cioe l'ultima
  volta che quella linea ha effettivamente mirrorato qualcosa. NON legge
  `whatsapp_team_sessions`: quella tabella registra le TRANSIZIONI, e leggerne
  una riga storica come stato corrente e gia costato una diagnosi sbagliata
  (contro-ritrattazione del 6/8 nel memo deeplink). E non legge nemmeno il
  process table: e li che nasce l'illusione.

SOGLIA — misurata, non inventata. Sui 60 giorni precedenti, per le 7 linee
vive: p50 fra due messaggi = 0.01h, p95 = 0.2-0.6h, e i silenzi naturali piu
lunghi (weekend/festivi) arrivano a ~48h. Tutto cio che superava 72h nel
campione erano periodi di morte veri — inclusi due che nessuno aveva notato
(198h su una linea, 81h su un'altra). 72h separa le due popolazioni con
margine su entrambi i lati.

COSA DICE E COSA NON DICE: riporta un FATTO — "questa linea non mirrora da N
ore" — non una diagnosi. Le cause possibili sono la sessione revocata (serve
re-pair QR, gesto fisico) oppure una linea legittimamente ferma. Distinguerle
richiede il telefono in mano; l'allarme porta fin li e si ferma.

FAIL-VISIBLE (W84/W106b): se il file account manca, il DSN manca, il driver
manca o il DB non risponde, questo organo esce **2 = CANNOT-VERIFY** e lo dice.
Non ha una modalita "sembra tutto a posto" quando non ha potuto guardare: e
esattamente il modo in cui un guardiano diventa decorativo.

BOUNDARY (Law 2 / scar #4): non stampa MAI un numero di telefono, ne in stdout
ne nell'alert ne nel JSON — solo il NOME dell'account. Non legge il contenuto
dei messaggi: solo il timestamp piu recente.

USO:
  wa_session_liveness.py                 # misura, alert se serve
  wa_session_liveness.py --json          # machine-readable, nessun alert
  wa_session_liveness.py --no-alert      # dry-run
  wa_session_liveness.py --hours 48      # soglia diversa
  wa_session_liveness.py --selftest      # verifica che l'organo stesso sia sano
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Sequence

REPO = Path(__file__).resolve().parents[1]

DEFAULT_STALE_HOURS = 72

ACCOUNTS_PATH = Path("~/.wa-mirror.accounts.json").expanduser()
SECRETS_PATH = Path("~/.nuzantara-secrets.env").expanduser()
DSN_VAR = "WA_MIRROR_DATABASE_URL"

OK = "OK"
STALE = "STALE"

EXIT_OK = 0
EXIT_CANNOT_VERIFY = 2


class CannotVerify(Exception):
    """Non ho potuto guardare. Non e la stessa cosa di 'va tutto bene'."""


@dataclass(frozen=True)
class LineStatus:
    name: str
    status: str
    hours_silent: Optional[float]
    last_seen: Optional[str]


# ---------------------------------------------------------------------------
# Logica pura — nessun I/O, ed e qui che vivono i test
# ---------------------------------------------------------------------------


def classify(
    name: str,
    last_seen: Optional[datetime],
    now: datetime,
    stale_hours: float = DEFAULT_STALE_HOURS,
) -> LineStatus:
    """Una linea senza NESSUNA riga e STALE, non OK.

    Il caso `last_seen is None` e quello di una linea appena aggiunta o mai
    catturata: trattarlo come OK ("nessun dato, nessun problema") e il modo
    piu diretto per non vedere mai una sessione che non ha mai funzionato.
    """
    if last_seen is None:
        return LineStatus(name, STALE, None, None)
    delta_h = (now - last_seen).total_seconds() / 3600.0
    status = STALE if delta_h >= stale_hours else OK
    return LineStatus(name, status, round(delta_h, 1), last_seen.isoformat())


def format_alert(stale: Sequence[LineStatus], host: str, stale_hours: float) -> str:
    """Solo NOMI: nessun numero di telefono entra in un alert (Law 2)."""
    head = (
        f"\U0001f4f5 wa-mirror [{host}] — {len(stale)} linea/e non mirrorano "
        f"da oltre {stale_hours:g}h:"
    )
    body = []
    for line in stale:
        when = (
            "mai una riga"
            if line.hours_silent is None
            else f"ferma da {line.hours_silent:.0f}h"
        )
        body.append(f"\n• {line.name}: {when}")
    body.append(
        "\n\nIl processo puo essere vivo lo stesso: il PID non e la prova."
        "\nSe la sessione e revocata serve un re-pair QR (gesto fisico):"
        "\n  apps/wa-mirror/scripts/start-one.sh <nome>  → scansione dal telefono"
    )
    return head + "".join(body)


# ---------------------------------------------------------------------------
# I/O — ogni ramo che non puo vedere ALZA, non ritorna un vuoto
# ---------------------------------------------------------------------------


def read_active_lines(path: Path = ACCOUNTS_PATH) -> dict:
    """{nome: e164} dagli account wa-mirror. Il file E la fonte di verita su
    chi e attivo: un ex-membro sparisce da qui e smette di essere sorvegliato.
    """
    try:
        raw = json.loads(path.read_text())
    except OSError as exc:
        raise CannotVerify(f"account file illeggibile ({type(exc).__name__})") from exc
    except json.JSONDecodeError as exc:
        raise CannotVerify("account file non e JSON valido") from exc

    items = raw if isinstance(raw, list) else raw.get("accounts", raw)
    if isinstance(items, dict):
        items = [
            dict(v, name=k) if isinstance(v, dict) else {"name": k}
            for k, v in items.items()
        ]
    lines = {}
    for entry in items:
        if not isinstance(entry, dict):
            continue
        number = (entry.get("e164") or entry.get("phone") or entry.get("number") or "")
        number = str(number).lstrip("+")
        name = entry.get("name") or entry.get("label")
        if number and name:
            lines[str(name)] = number
    if not lines:
        raise CannotVerify("nessun account con E.164 nel file: non c'e niente da sorvegliare")
    return lines


def read_dsn(path: Path = SECRETS_PATH, var: str = DSN_VAR) -> str:
    """Legge SOLO la riga del DSN. Il file non viene mai stampato ne loggato."""
    env = os.environ.get(var)
    if env:
        return env
    try:
        with path.open() as handle:
            for line in handle:
                if line.startswith(f"{var}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError as exc:
        raise CannotVerify(f"secrets file illeggibile ({type(exc).__name__})") from exc
    raise CannotVerify(f"{var} assente: il mirror locale non e configurato qui")


def fetch_last_seen(dsn: str, lines: dict) -> dict:
    """{nome: datetime|None}. Un errore di connessione ALZA CannotVerify."""
    try:
        import asyncpg  # noqa: PLC0415 — import tardivo: assente = CANNOT-VERIFY
    except ImportError as exc:
        raise CannotVerify("driver asyncpg assente in questo interprete") from exc
    import asyncio

    query = (
        "select max(coalesce(message_date, created_at)) "
        "from whatsapp_message_context "
        "where regexp_replace(coalesce(team_member_phone,''),'[^0-9]','','g') "
        "like '%'||$1||'%'"
    )

    async def _run() -> dict:
        conn = await asyncpg.connect(dsn)
        try:
            return {name: await conn.fetchval(query, num) for name, num in lines.items()}
        finally:
            await conn.close()

    try:
        return asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001 — qualunque guaio DB = non ho visto
        raise CannotVerify(f"query mirror fallita ({type(exc).__name__})") from exc


def hostname() -> str:
    return socket.gethostname().split(".")[0]


def send_to_gateway(message: str, host: str, dedup_suffix: str = "") -> bool:
    """Stessa catena degli altri sentinel: alerter (dedup) → tg_notify."""
    try:
        sys.path.insert(0, str(REPO / "scripts"))
        from sentinel_lib import alerter  # noqa: PLC0415

        return bool(alerter.send_alert(message, level="WARNING"))
    except Exception:  # noqa: BLE001 — fallback diretto al gateway
        import subprocess

        gateway = REPO / "scripts" / "tg_notify.py"
        if not gateway.exists():
            return False
        subprocess.run(
            [sys.executable, str(gateway), "--tier", "p0", "--source", "wa-session-liveness",
             "--dedup-key", f"wa-session-{host}{dedup_suffix}", message],
            check=False,
        )
        return True


def emit_alert(stale: Sequence[LineStatus], host: str, stale_hours: float) -> bool:
    if not stale:
        return False
    return send_to_gateway(format_alert(stale, host, stale_hours), host)


def emit_blind_alert(reason: str, host: str) -> bool:
    """CANNOT-VERIFY deve suonare DA SOLO, non per grazia di chi lo invoca.

    Uscire 2 basta finche il chiamante e `cron-runner.sh`, che quel 2 lo legge
    e allarma. Ma allora l'unico modo in cui questo organo si fa sentire e un
    modo che appartiene a un ALTRO organo: spostarlo su un plist, o eseguirlo a
    mano, e sarebbe muto senza che nulla cambi nel suo codice. Un guardiano che
    delega la propria voce e gia mezzo decorativo (W108).
    """
    message = (
        f"\U0001f691 wa-mirror [{host}] — CANNOT-VERIFY: {reason}"
        "\n\nNessuna linea e stata giudicata: questo NON e un verdetto di salute."
        "\nFinche dura, una sessione morta non la vedrebbe nessuno."
    )
    return send_to_gateway(message, host, dedup_suffix="-blind")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def run(stale_hours: float) -> list[LineStatus]:
    lines = read_active_lines()
    dsn = read_dsn()
    last = fetch_last_seen(dsn, lines)
    now = datetime.now(timezone.utc)
    return sorted(
        (classify(name, last.get(name), now, stale_hours) for name in lines),
        key=lambda s: (s.status != STALE, s.name),
    )


def selftest() -> int:
    """Un guardiano silenzioso-quando-sano deve saper dimostrare di essere vivo."""
    problems = []
    now = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
    if classify("x", now - timedelta(hours=100), now).status != STALE:
        problems.append("classify non marca STALE una linea ferma da 100h")
    if classify("x", now - timedelta(hours=1), now).status != OK:
        problems.append("classify non marca OK una linea fresca")
    if classify("x", None, now).status != STALE:
        problems.append("classify tratta 'mai vista' come sana")
    if not (REPO / "scripts" / "tg_notify.py").exists():
        problems.append("tg_notify.py assente: l'allarme non avrebbe dove uscire")
    for problem in problems:
        print(f"  ✗ {problem}")
    print(f"selftest: {'OK' if not problems else str(len(problems)) + ' problemi'}")
    return EXIT_OK if not problems else EXIT_CANNOT_VERIFY


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="wa-mirror line liveness guardian")
    parser.add_argument("--json", action="store_true", help="machine-readable, nessun alert")
    parser.add_argument("--no-alert", action="store_true", help="misura e riporta, mai Telegram")
    parser.add_argument("--selftest", action="store_true", help="verifica l'organo stesso")
    parser.add_argument(
        "--hours",
        type=float,
        default=float(os.environ.get("WA_SESSION_STALE_HOURS", DEFAULT_STALE_HOURS)),
        help=f"ore di silenzio oltre le quali una linea e STALE (default {DEFAULT_STALE_HOURS})",
    )
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    host = hostname()
    try:
        statuses = run(args.hours)
    except CannotVerify as exc:
        payload = {"host": host, "cannot_verify": str(exc), "lines": []}
        print(json.dumps(payload) if args.json else
              f"CANNOT-VERIFY [{host}]: {exc}\n"
              "Non e un verdetto di salute: questo organo non ha potuto guardare.")
        if not (args.json or args.no_alert):
            emit_blind_alert(str(exc), host)
        return EXIT_CANNOT_VERIFY

    stale = [s for s in statuses if s.status == STALE]

    if args.json:
        print(json.dumps({"host": host, "stale_hours": args.hours,
                          "stale": len(stale),
                          "lines": [asdict(s) for s in statuses]}))
    else:
        print(f"wa-mirror liveness [{host}] — soglia {args.hours:g}h")
        for line in statuses:
            icon = "🔴" if line.status == STALE else "🟢"
            when = "mai una riga" if line.hours_silent is None else f"{line.hours_silent:.1f}h fa"
            print(f"  {icon} {line.name:<10} {line.status:<5} ultima riga {when}")
        if not args.no_alert:
            sent = emit_alert(stale, host, args.hours)
            print(f"\nalert: {'inviato' if sent else 'nessuno'} ({len(stale)} STALE)")

    # exit 0 anche con linee STALE: il verdetto viaggia via alert, non via
    # exit-code, come gli altri sentinel. Il 2 e riservato al non-ho-visto.
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
