#!/usr/bin/env python3
"""S7 Yield dispatch — recapita le bozze WhatsApp al team member assegnatario.

`scripts/s7_yield_draft_local.py` (cron domenica 04:00 su Pro) scrive bozze di
pitch WhatsApp in `~/.nuzantara-staging/s7-yield/<SEG>-<ts>-drafts.md` più un
sidecar strutturato `<SEG>-<ts>-drafts.jsonl` (un JSON per riga: client_id,
assigned_to, segment, lang, pitch, signals). Fino a questo script nessuno
leggeva quella cartella — 58 file fermi dal 2026-06-02.

Questo script legge SOLO il sidecar (mai il markdown) e recapita ogni bozza,
via email, al membro del team a cui il cliente è assegnato — MAI a un
destinatario di default.

CANCELLO DI RECAPITO — fail-closed, la parte load-bearing (`resolve_recipient`
sotto). Un destinatario è VALID solo se TUTTE e tre le condizioni valgono:
  1. `assigned_to` risolve (case-insensitive) a una riga di `team_members`;
  2. quella riga ha `active = true`;
  3. l'indirizzo termina in `@balizero.com`.
Tutto il resto è HELD: mai inviato, mai un fallback su un destinatario di
default (niente "in dubbio manda a zero@"). Un assegnatario INATTIVO (es.
Sahira, uscita 2026-07-10, 163 clienti) deve finire HELD — se questo script
gli manda anche una sola bozza ha spedito dati cliente alla casella di chi
non lavora più qui.

ANTI-SPAM: un registro `dispatch-registry.json` (0600, nella staging dir)
traccia l'ultimo invio per (client_id, segment) con cooldown di 90 giorni
di default — senza questo, ogni domenica gli stessi clienti verrebbero
ripitchati.

PRIVACY: mai loggare il corpo dell'email o il testo del pitch — nei log SOLO
conteggi e client_id (stesso contratto di yield_optimizer_pitch_gate.py). Il
report a Zero (via `tg_notify.py --tier digest`) porta SOLO conteggi
aggregati + il motivo di ogni HELD — zero nomi/client_id verso Telegram.

`--dry-run` è il DEFAULT — nessuna email reale, nessuna scrittura sul
registro di cooldown. `--send` è l'unico modo di inviare davvero, e richiede
`NOTIFICATIONS_API_KEY` nell'env (mai hardcodata, mai loggata) — se manca,
lo script esce senza inviare nulla (fail-visible, non silenzioso).

Usage:
  python scripts/s7_yield_dispatch.py                    # dry-run, tutti i segmenti
  python scripts/s7_yield_dispatch.py --send              # invio reale
  python scripts/s7_yield_dispatch.py --sidecar <path>    # file esplicito (test/debug)

Exit codes: 0 ok (anche "niente da fare") · 2 team roster (pg.sh) irraggiungibile
· 3 --send senza NOTIFICATIONS_API_KEY (nessun invio tentato).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PG_SH = REPO_ROOT / "scripts" / "pg.sh"
TG_NOTIFY = REPO_ROOT / "scripts" / "tg_notify.py"

STAGING = Path(os.environ.get("S7_STAGING", str(Path.home() / ".nuzantara-staging" / "s7-yield")))
DEFAULT_COOLDOWN_DAYS = 90

EMAIL_API_URL = os.environ.get(
    "INTERNAL_EMAIL_API_URL", "https://nuzantara-rag.fly.dev/api/notifications/send-email"
)
SENDER_EMAIL = "zantara@balizero.com"
SENDER_NAME = "Zantara"

# ---------------------------------------------------------------- gate verdicts
VALID = "VALID"
HELD = "HELD"
HELD_NO_OWNER = "no_owner"
HELD_OWNER_INACTIVE = "owner_inactive"
HELD_NON_COMPANY_ADDRESS = "non_company_address"

_HELD_LABELS_IT = {
    HELD_NO_OWNER: "nessun proprietario valido",
    HELD_OWNER_INACTIVE: "proprietario inattivo",
    HELD_NON_COMPANY_ADDRESS: "indirizzo non aziendale",
}

_STRINGS = {
    "id": {
        "subject": "S7 Yield — {n} klien untuk dihubungi minggu ini",
        "intro": "Berikut draf pesan WhatsApp untuk klien Anda minggu ini:",
    },
    "en": {
        "subject": "S7 Yield — {n} clients to reach out to this week",
        "intro": "Here are this week's WhatsApp pitch drafts for your clients:",
    },
    "it": {
        "subject": "S7 Yield — {n} clienti da ricontattare questa settimana",
        "intro": "Ecco le bozze WhatsApp di questa settimana per i tuoi clienti:",
    },
    "uk": {
        "subject": "S7 Yield — {n} клієнтів для зв'язку цього тижня",
        "intro": "Ось чернетки повідомлень WhatsApp для ваших клієнтів на цьому тижні:",
    },
}


def resolve_recipient(
    assigned_to: str | None, team_by_email: dict[str, dict]
) -> tuple[str, str | None, dict | None]:
    """The delivery gate. Fail-closed by construction: any branch that is not
    the single VALID return at the bottom returns HELD — there is no fallback
    branch that returns a default recipient anywhere in this function.

    Returns (status, held_reason, team_row). `team_row` is populated only when
    status is VALID.
    """
    key = (assigned_to or "").strip().lower()
    if not key:
        return HELD, HELD_NO_OWNER, None
    row = team_by_email.get(key)
    if row is None:
        # Does not resolve to any team_members row at all — NULL, empty,
        # a phone number, or an address not in the roster all land here.
        return HELD, HELD_NO_OWNER, None
    if not row.get("active"):
        return HELD, HELD_OWNER_INACTIVE, None
    if not key.endswith("@balizero.com"):
        # Present + active in the roster (e.g. a personal gmail address used
        # as a login) is still not a company mailbox — HELD, not a fallback.
        return HELD, HELD_NON_COMPANY_ADDRESS, None
    return VALID, None, row


# ---------------------------------------------------------------- team roster
def load_team_roster() -> dict[str, dict]:
    """email(lowercased) -> {"email": <as stored>, "active": bool, "language": str}.

    Postgres access is ONLY via scripts/pg.sh (the one-true-way, see its own
    header) — never a second DSN/Keychain path in this file.
    """
    sql = "COPY (SELECT row_to_json(t) FROM (SELECT email, active, language FROM team_members) t) TO STDOUT"
    proc = subprocess.run(
        ["bash", str(PG_SH), "-tA", "-c", sql], capture_output=True, text=True
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        sys.exit(2)
    roster: dict[str, dict] = {}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        email = (row.get("email") or "").strip()
        if not email:
            continue
        roster[email.lower()] = row
    return roster


# ---------------------------------------------------------------- sidecar I/O
def discover_latest_sidecars(staging: Path) -> list[Path]:
    """Latest sidecar file per segment prefix (`Sx-<ts>-drafts.jsonl`).

    The generator's ts format (%Y%m%dT%H%M%SZ) sorts chronologically as a
    plain string, so a lexicographic sort is enough to keep, per segment,
    only this week's batch — not every historical file ever produced.
    """
    if not staging.is_dir():
        return []
    latest: dict[str, Path] = {}
    for p in sorted(staging.glob("S*-*-drafts.jsonl")):
        seg = p.name.split("-", 1)[0]
        latest[seg] = p  # ascending sort => last write wins => most recent ts
    return list(latest.values())


def read_sidecar_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    try:
        text = path.read_text()
    except OSError as exc:
        print(f"[S7-dispatch] cannot read sidecar {path}: {exc}", file=sys.stderr)
        return rows
    for lineno, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"[S7-dispatch] skipping malformed sidecar line {path}:{lineno}", file=sys.stderr)
    return rows


# ---------------------------------------------------------------- cooldown registry
def load_registry(path: Path) -> dict[str, str]:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def _write_json_0600(path: Path, data: dict) -> None:
    """Same lesson as tg_notify.py's harden(): O_CREAT's mode only applies at
    CREATION, and Path.replace() carries the SOURCE's mode onto the
    destination — so the tmp file must be born 0600, and the final path is
    re-chmod'd in case it pre-existed under a looser mode."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".json.tmp{os.getpid()}")
    fd = os.open(str(tmp), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    try:
        os.write(fd, json.dumps(data, indent=1, sort_keys=True).encode())
    finally:
        os.close(fd)
    tmp.replace(path)
    os.chmod(path, 0o600)


def save_registry(path: Path, registry: dict[str, str]) -> None:
    _write_json_0600(path, registry)


def _cooldown_key(client_id, segment) -> str:
    return f"{client_id}|{segment}"


def in_cooldown(registry: dict, client_id, segment, cooldown_days: int, now: datetime) -> bool:
    ts = registry.get(_cooldown_key(client_id, segment))
    if not ts:
        return False
    try:
        last = datetime.fromisoformat(ts)
    except ValueError:
        return False
    return (now - last) < timedelta(days=cooldown_days)


def mark_sent(registry: dict, client_id, segment, now: datetime) -> None:
    registry[_cooldown_key(client_id, segment)] = now.isoformat()


# ---------------------------------------------------------------- partition
def partition_rows(
    rows: list[dict],
    team: dict[str, dict],
    registry: dict[str, str],
    cooldown_days: int,
    now: datetime,
) -> tuple[Counter, dict[str, list[dict]], dict[str, dict], int, int]:
    """Classify sidecar rows into HELD / cooldown-skipped / no-pitch / deliverable.

    Pulled out of main() so the delivery gate + cooldown + RBAC-grouping logic
    is testable without touching Postgres, the filesystem, or Telegram.

    Returns (held_counts, by_recipient_email, recipient_team_row_by_email,
    cooldown_skipped, no_pitch). `by_recipient_email` never contains a
    client_id whose resolved recipient is not that client's own assigned_to
    — that IS the CRM RBAC boundary, held by construction of this loop.
    """
    held_counts: Counter = Counter()
    cooldown_skipped = 0
    no_pitch = 0
    by_recipient: dict[str, list[dict]] = defaultdict(list)
    recipient_rows: dict[str, dict] = {}
    for row in rows:
        cid = row.get("client_id")
        seg = row.get("segment")
        status, reason, team_row = resolve_recipient(row.get("assigned_to"), team)
        if status == HELD:
            held_counts[reason] += 1
            print(f"[S7-dispatch] HELD client_id={cid} segment={seg} reason={reason}")
            continue
        if in_cooldown(registry, cid, seg, cooldown_days, now):
            cooldown_skipped += 1
            print(f"[S7-dispatch] cooldown client_id={cid} segment={seg}")
            continue
        if not row.get("pitch"):
            no_pitch += 1
            print(f"[S7-dispatch] no_pitch client_id={cid} segment={seg}")
            continue
        by_recipient[team_row["email"]].append(row)
        recipient_rows[team_row["email"]] = team_row
    return held_counts, by_recipient, recipient_rows, cooldown_skipped, no_pitch


# ---------------------------------------------------------------- email
def build_email(language: str, rows: list[dict]) -> tuple[str, str]:
    """Returns (subject, html_body). `rows` are only the clients OWNED by this
    recipient (the caller groups by resolved recipient) — this is what makes
    the CRM RBAC boundary hold: a recipient's email never contains a client_id
    that is not their own assigned_to."""
    strings = _STRINGS.get(language) or _STRINGS["id"]
    subject = strings["subject"].format(n=len(rows))
    parts = [f"<p>{html.escape(strings['intro'])}</p>"]
    for row in rows:
        pitch = html.escape(str(row.get("pitch") or ""))
        cid = html.escape(str(row.get("client_id")))
        seg = html.escape(str(row.get("segment")))
        parts.append(
            f'<p><strong>client_id={cid}</strong> ({seg})<br>{pitch}</p>'
        )
    parts.append("<p><em>Bali Zero · S7 Yield</em></p>")
    return subject, "\n".join(parts)


def send_email(to: str, subject: str, html_body: str) -> tuple[bool, str]:
    """The ONLY sender in this file. Always from=zantara@balizero.com /
    name=Zantara, per CLAUDE.md's fixed email-sending rule. Never reads the
    response body on failure — a server echo of the request could carry the
    pitch text back into a caught exception's string, and this file's whole
    contract is that pitch text never lands in a log."""
    api_key = os.environ.get("NOTIFICATIONS_API_KEY", "")
    if not api_key:
        return False, "NOTIFICATIONS_API_KEY not set"
    payload = json.dumps(
        {
            "to": to,
            "subject": subject,
            "body": html_body,
            "body_html": html_body,
            "from": SENDER_EMAIL,
            "from_name": SENDER_NAME,
        }
    ).encode()
    req = urllib.request.Request(
        EMAIL_API_URL,
        data=payload,
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            ok = 200 <= resp.status < 300
            return ok, "" if ok else f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001 -- network failure is terminal for this recipient, never a crash
        return False, f"{type(exc).__name__}"


# ---------------------------------------------------------------- alert gateway
def notify_zero(
    held_counts: Counter,
    valid_count: int,
    sent_or_simulated: int,
    cooldown_skipped: int,
    no_pitch: int,
    dry_run: bool,
) -> None:
    """Aggregate counts ONLY — zero client_id/nomi verso Telegram.

    Interprete ASSOLUTO (sys.executable, mai `python3` risolto via PATH dopo
    aver sorgentato un venv — W107/W108), rc sempre catturato+loggato, e
    l'intera chiamata è wrapped: un gateway morto non deve mai far fallire
    il dispatcher stesso.
    """
    mode = "DRY-RUN" if dry_run else "INVIATO"
    lines = [
        f"S7 Yield dispatch [{mode}]",
        f"Recapitabili: {valid_count} ({sent_or_simulated} {'simulati' if dry_run else 'inviati'})",
        f"Sospesi per cooldown (90gg): {cooldown_skipped}",
    ]
    if no_pitch:
        lines.append(f"Senza bozza (sidecar dry-run/fallita): {no_pitch}")
    if held_counts:
        lines.append("HELD dal cancello di recapito:")
        for reason, label in _HELD_LABELS_IT.items():
            n = held_counts.get(reason, 0)
            if n:
                lines.append(f"  · {label}: {n}")
    text = "\n".join(lines)
    try:
        proc = subprocess.run(
            [sys.executable, str(TG_NOTIFY), "--tier", "digest", "--source", "s7-dispatch", "--", text],
            capture_output=True,
            text=True,
            timeout=20,
        )
        print(f"[S7-dispatch] tg_notify rc={proc.returncode}")
    except Exception as exc:  # noqa: BLE001 -- alert gateway must never crash the dispatcher
        print(f"[S7-dispatch] tg_notify invocation failed: {type(exc).__name__}: {exc}", file=sys.stderr)


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--staging", default=None, help="override staging dir (default: $S7_STAGING)")
    ap.add_argument("--cooldown-days", type=int, default=DEFAULT_COOLDOWN_DAYS)
    ap.add_argument("--send", action="store_true", help="actually send emails (default: dry-run)")
    ap.add_argument(
        "--sidecar", action="append", default=None,
        help="explicit sidecar file(s), repeatable; default: latest per segment in --staging",
    )
    args = ap.parse_args()

    staging = Path(args.staging) if args.staging else STAGING
    registry_path = staging / "dispatch-registry.json"

    if args.send and not os.environ.get("NOTIFICATIONS_API_KEY"):
        print(
            "[S7-dispatch] FATAL: --send requires NOTIFICATIONS_API_KEY in env — aborting, nothing sent.",
            file=sys.stderr,
        )
        return 3

    sidecar_paths = [Path(p) for p in args.sidecar] if args.sidecar else discover_latest_sidecars(staging)
    if not sidecar_paths:
        print(f"[S7-dispatch] no sidecar files found under {staging} — nothing to do.")
        return 0

    team = load_team_roster()
    registry = load_registry(registry_path)
    now = datetime.now(timezone.utc)

    all_rows: list[dict] = []
    for path in sidecar_paths:
        all_rows.extend(read_sidecar_rows(path))

    held_counts, by_recipient, recipient_rows, cooldown_skipped, no_pitch = partition_rows(
        all_rows, team, registry, args.cooldown_days, now
    )

    valid_count = sum(len(rows) for rows in by_recipient.values())
    sent_or_simulated = 0

    for email, rows in by_recipient.items():
        language = recipient_rows.get(email, {}).get("language") or "id"
        subject, body_html = build_email(language, rows)
        if args.send:
            ok, err = send_email(email, subject, body_html)
            if ok:
                for row in rows:
                    mark_sent(registry, row.get("client_id"), row.get("segment"), now)
                sent_or_simulated += len(rows)
                print(f"[S7-dispatch] sent to recipient clients={len(rows)}")
            else:
                print(f"[S7-dispatch] SEND FAILED clients={len(rows)} err={err}", file=sys.stderr)
        else:
            sent_or_simulated += len(rows)
            print(f"[S7-dispatch] DRY-RUN would send clients={len(rows)}")

    if args.send:
        save_registry(registry_path, registry)

    notify_zero(held_counts, valid_count, sent_or_simulated, cooldown_skipped, no_pitch, dry_run=not args.send)

    summary = {
        "held": dict(held_counts),
        "valid_recipients": len(by_recipient),
        "valid_clients": valid_count,
        "sent_or_simulated": sent_or_simulated,
        "cooldown_skipped": cooldown_skipped,
        "no_pitch": no_pitch,
        "dry_run": not args.send,
    }
    print("[S7-dispatch] SUMMARY " + json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
