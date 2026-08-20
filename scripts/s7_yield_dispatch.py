#!/usr/bin/env python3
"""S7 Yield dispatch — recapita le bozze di ricontatto al team member assegnatario, via WhatsApp.

`scripts/s7_yield_draft_local.py` (cron domenica 04:00 su Pro) scrive bozze di
pitch WhatsApp per il CLIENTE in `~/.nuzantara-staging/s7-yield/<SEG>-<ts>-drafts.md`
più un sidecar strutturato `<SEG>-<ts>-drafts.jsonl` (un JSON per riga:
client_id, assigned_to, segment, lang, pitch, display_name, signals). Fino a
questo script nessuno leggeva quella cartella — 58 file fermi dal 2026-06-02.

Questo script legge SOLO il sidecar (mai il markdown) e recapita ogni bozza
al MEMBRO DEL TEAM a cui il cliente è assegnato, via WhatsApp — non email
(canale cambiato da Zero il 2026-08-21: `NOTIFICATIONS_API_KEY`/Brevo non
esiste su nessuna delle tre macchine). Il canale WhatsApp per questo flusso è
una **deroga nominata alla Legge 2** (SYMBIOSIS.md, Zero 2026-08-21): il
divieto di trascrivere PII cliente in chiaro resta la regola generale, e
questa deroga apre UN varco solo, con limiti stretti — vedi sezione "Payload
allowlist" sotto. Ogni altra superficie della Legge 2 resta invariata.

CANCELLO DI RECAPITO — fail-closed, la parte load-bearing (`resolve_recipient`
sotto). Un destinatario è VALID solo se TUTTE le condizioni valgono:
  1. `assigned_to` (RI-VERIFICATO al momento dell'invio contro `clients` —
     mai ereditato dal sidecar, che riflette lo stato DB al momento della
     bozza e può essere stale di giorni) risolve, case-insensitive, a una
     riga di `team_members`;
  2. quella riga NON è un account di servizio/test (denylist esplicita —
     `healthcheck@`, `test.autocheck@`, `qa.crm.portal.*@`: oggi hanno 0
     clienti assegnati, ma passerebbero le altre condizioni e domani
     qualcuno potrebbe assegnarci un cliente);
  3. la riga ha `active = true`;
  4. l'indirizzo termina in `@balizero.com`;
  5. la riga ha un numero `whatsapp` non vuoto.
Tutto il resto è HELD: mai inviato, mai un fallback su un destinatario di
default. Un assegnatario INATTIVO (es. Sahira, uscita 2026-07-10, 163
clienti) deve finire HELD.

PAYLOAD ALLOWLIST (deroga Legge 2 — limite duro, non negoziabile):
  AMMESSO: nome di battesimo + iniziale del cognome (`display_name`,
    calcolato e già ridotto dal GENERATOR — questo script non vede mai il
    nome completo), `client_id`, tipo di scadenza, data di scadenza, testo
    del pitch destinato al cliente.
  VIETATO: passaporto, KTP, NPWP, numero di qualsiasi documento, indirizzo,
    data di nascita, nome completo, dati di qualunque cliente non assegnato
    al destinatario. Il pitch è testo libero generato da un LLM a partire dal
    record cliente — un filtro sui soli CAMPI strutturati non vede un dato
    vietato scritto dentro una frase, quindi il pitch passa da
    `scan_pitch_for_forbidden_content()` PRIMA dell'invio: un digest il cui
    pitch non supera lo scan resta HELD, non viene ripulito e spedito lo
    stesso. `build_whatsapp_message()` è inoltre un formattatore ad
    ALLOWLIST: legge solo i campi nominati sopra da ogni riga — qualunque
    altra chiave presente (un campo futuro del sidecar, una riga
    corrotta/malevola) non viene mai toccata, per costruzione.

ANTI-SPAM: un registro `dispatch-registry.json` (0600, nella staging dir)
traccia l'ultimo invio per (client_id, segment) con cooldown di 90 giorni.

PRIVACY nei LOG: mai il corpo del messaggio o il testo del pitch — nei log
SOLO conteggi, client_id, e nomi di CATEGORIA di violazione (mai il testo
flaggato). Il report a Zero (`tg_notify.py --tier digest`) porta SOLO
conteggi aggregati + il motivo di ogni HELD — zero nomi/client_id/numeri.

`--dry-run` è il DEFAULT — nessun messaggio reale, nessuna scrittura sul
registro di cooldown. `--send` richiede `NUZANTARA_API_KEY` nell'env (stesso
segreto già presente su Pro per gli altri cron — mai `NOTIFICATIONS_API_KEY`,
mai un token WhatsApp locale: Pro non nomina mai un numero, lo risolve il
backend da `team_members` — vedi `apps/backend-rag/backend/services/crm/
team_whatsapp_sender.py` + `POST /api/cron/notifiers/team-whatsapp`).

Usage:
  python scripts/s7_yield_dispatch.py                    # dry-run, tutti i segmenti
  python scripts/s7_yield_dispatch.py --send              # invio reale
  python scripts/s7_yield_dispatch.py --sidecar <path>    # file esplicito (test/debug)

Exit codes: 0 ok (anche "niente da fare") · 2 team roster / assignment refresh
(pg.sh) irraggiungibile · 3 --send senza NUZANTARA_API_KEY (nessun invio tentato).
"""
from __future__ import annotations

import argparse
import json
import os
import re
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
BATCH_SIZE = 5  # clients per WhatsApp message — readability, not the 4096-char limit (WhatsAppService already fits that)

TEAM_WHATSAPP_API_URL = os.environ.get(
    "TEAM_WHATSAPP_API_URL", "https://nuzantara-rag.fly.dev/api/cron/notifiers/team-whatsapp"
)

# ---------------------------------------------------------------- gate verdicts
VALID = "VALID"
HELD = "HELD"
HELD_NO_OWNER = "no_owner"
HELD_OWNER_INACTIVE = "owner_inactive"
HELD_NON_COMPANY_ADDRESS = "non_company_address"
HELD_SERVICE_ACCOUNT = "service_account"
HELD_NO_WHATSAPP_NUMBER = "no_whatsapp_number"
HELD_PITCH_CONTENT_FLAGGED = "pitch_content_flagged"

_HELD_LABELS_IT = {
    HELD_NO_OWNER: "nessun proprietario valido",
    HELD_OWNER_INACTIVE: "proprietario inattivo",
    HELD_NON_COMPANY_ADDRESS: "indirizzo non aziendale",
    HELD_SERVICE_ACCOUNT: "account di servizio",
    HELD_NO_WHATSAPP_NUMBER: "nessun numero WhatsApp",
    HELD_PITCH_CONTENT_FLAGGED: "contenuto del pitch segnalato (dato vietato)",
}

# Named denylist, not a heuristic: today these 3 have 0 clients assigned
# (measured 2026-08-20), so they cost nothing to exclude now — but they are
# active=true and @balizero.com, so without this they would pass every other
# gate condition the day someone assigns them a client.
_SERVICE_ACCOUNT_EXACT = frozenset({"healthcheck@balizero.com", "test.autocheck@balizero.com"})
_SERVICE_ACCOUNT_PREFIXES = ("qa.crm.portal.",)


def _is_service_account(email_lower: str) -> bool:
    if email_lower in _SERVICE_ACCOUNT_EXACT:
        return True
    local = email_lower.split("@", 1)[0]
    return any(local.startswith(p) for p in _SERVICE_ACCOUNT_PREFIXES)


def resolve_recipient(
    assigned_to: str | None, team_by_email: dict[str, dict]
) -> tuple[str, str | None, dict | None]:
    """The delivery gate. Fail-closed by construction: any branch that is not
    the single VALID return at the bottom returns HELD — there is no fallback
    branch that returns a default recipient anywhere in this function.

    `assigned_to` MUST be the value re-verified against `clients` at send
    time (see `load_current_assignments`) — never the sidecar's stale copy;
    this function itself is agnostic to where the value came from, but every
    call site in this file passes the fresh one.

    Returns (status, held_reason, team_row). `team_row` is populated only when
    status is VALID.
    """
    key = (assigned_to or "").strip().lower()
    if not key:
        return HELD, HELD_NO_OWNER, None
    if _is_service_account(key):
        return HELD, HELD_SERVICE_ACCOUNT, None
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
    phone = (row.get("whatsapp") or "").strip()
    if not phone:
        return HELD, HELD_NO_WHATSAPP_NUMBER, None
    return VALID, None, row


# ---------------------------------------------------------------- pitch content scan
# Best-effort, NOT exhaustive by design — SYMBIOSIS.md's own language: the
# enforcement lives in this corpus (guilt+innocence per category), not in a
# claim of completeness. The pitch is LLM free text, so a forbidden fact can
# be written INTO a sentence; a field-level allowlist alone cannot see that.
_PASSPORT_LIKE_RE = re.compile(r"\b[A-Z]{1,2}\d{6,9}\b")
_ADDRESS_MARKERS = ("jl.", "jalan ", " street", " road", "alamat")
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
# A DOB year is historical; the only date this pitch is allowed to carry is
# an expiry date, which for this business is always near-current. Outside
# [2020, 2035] is treated as suspicious rather than a legitimate expiry.
_PLAUSIBLE_EXPIRY_YEAR_RANGE = (2020, 2035)


def scan_pitch_for_forbidden_content(text: str) -> list[str]:
    """Returns violation category names found in `text`; empty list = clean."""
    violations: list[str] = []
    if not text:
        return violations
    if _PASSPORT_LIKE_RE.search(text):
        violations.append("passport_like")
    for run in re.findall(r"[\d][\d.\-/ ]*\d", text):
        if sum(ch.isdigit() for ch in run) >= 10:  # NPWP=15, KTP=16 digits; an 8-digit date stays under this
            violations.append("long_document_number")
            break
    lowered = text.lower()
    if any(marker in lowered for marker in _ADDRESS_MARKERS):
        violations.append("address_like")
    lo, hi = _PLAUSIBLE_EXPIRY_YEAR_RANGE
    if any(not (lo <= int(y) <= hi) for y in _YEAR_RE.findall(text)):
        violations.append("dob_like")
    return violations


# ---------------------------------------------------------------- team roster
def load_team_roster() -> dict[str, dict]:
    """email(lowercased) -> {"email": <as stored>, "active": bool, "language": str, "whatsapp": str|None}.

    Postgres access is ONLY via scripts/pg.sh (the one-true-way, see its own
    header) — never a second DSN/Keychain path in this file.
    """
    sql = (
        "COPY (SELECT row_to_json(t) FROM "
        "(SELECT email, active, language, whatsapp FROM team_members) t) TO STDOUT"
    )
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


def load_current_assignments(client_ids: list) -> dict[int, str | None]:
    """Fresh `clients.assigned_to` per client_id, queried AT SEND TIME.

    Law-2 derogation requirement (SYMBIOSIS.md 2026-08-21): "la corrispondenza
    assigned_to va ri-verificata al momento dell'invio, non ereditata dal
    momento della bozza" — the sidecar's assigned_to reflects DB state when
    the draft was generated, which can be stale by the time this runs (cron
    cadence is weekly; a client can be reassigned or unassigned in between).
    A client_id absent from the result (deleted, malformed id, or the query
    simply returned nothing for it) resolves to None — unassigned, HELD —
    NEVER falls back to the sidecar's value.
    """
    ids: list[int] = []
    for c in client_ids:
        try:
            ids.append(int(c))
        except (TypeError, ValueError):
            print(f"[S7-dispatch] skipping non-integer client_id in sidecar: {c!r}", file=sys.stderr)
    if not ids:
        return {}
    ids_csv = ",".join(str(i) for i in sorted(set(ids)))  # every element proven int above — no injection surface
    sql = (
        "COPY (SELECT row_to_json(t) FROM "
        f"(SELECT id, assigned_to FROM clients WHERE id IN ({ids_csv}) AND deleted_at IS NULL) t"
        ") TO STDOUT"
    )
    proc = subprocess.run(
        ["bash", str(PG_SH), "-tA", "-c", sql], capture_output=True, text=True
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        sys.exit(2)
    out: dict[int, str | None] = {}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        out[int(row["id"])] = row.get("assigned_to")
    return out


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
    current_assignments: dict,
) -> tuple[Counter, dict[str, list[dict]], dict[str, dict], int, int]:
    """Classify sidecar rows into HELD / cooldown-skipped / no-pitch / deliverable.

    Pulled out of main() so the delivery gate + freshness re-check + cooldown
    + content-scan + RBAC-grouping logic is testable without touching
    Postgres, the filesystem, or the WhatsApp send.

    Returns (held_counts, by_recipient_email, recipient_team_row_by_email,
    cooldown_skipped, no_pitch). `by_recipient_email` never contains a
    client_id whose resolved recipient is not that client's own (FRESH)
    assigned_to — that IS the CRM RBAC boundary, held by construction.
    """
    held_counts: Counter = Counter()
    cooldown_skipped = 0
    no_pitch = 0
    by_recipient: dict[str, list[dict]] = defaultdict(list)
    recipient_rows: dict[str, dict] = {}
    for row in rows:
        cid = row.get("client_id")
        seg = row.get("segment")
        fresh_assigned_to = current_assignments.get(cid)
        status, reason, team_row = resolve_recipient(fresh_assigned_to, team)
        if status == HELD:
            held_counts[reason] += 1
            print(f"[S7-dispatch] HELD client_id={cid} segment={seg} reason={reason}")
            continue
        if in_cooldown(registry, cid, seg, cooldown_days, now):
            cooldown_skipped += 1
            print(f"[S7-dispatch] cooldown client_id={cid} segment={seg}")
            continue
        pitch = row.get("pitch")
        if not pitch:
            no_pitch += 1
            print(f"[S7-dispatch] no_pitch client_id={cid} segment={seg}")
            continue
        violations = scan_pitch_for_forbidden_content(pitch)
        if violations:
            held_counts[HELD_PITCH_CONTENT_FLAGGED] += 1
            print(
                f"[S7-dispatch] HELD client_id={cid} segment={seg} "
                f"reason={HELD_PITCH_CONTENT_FLAGGED} categories={','.join(violations)}"
            )
            continue
        by_recipient[team_row["email"]].append(row)
        recipient_rows[team_row["email"]] = team_row
    return held_counts, by_recipient, recipient_rows, cooldown_skipped, no_pitch


# ---------------------------------------------------------------- WhatsApp message
_LANG_SHORT = {
    "English": "EN",
    "Italian": "IT",
    "Spanish": "ES",
    "French": "FR",
    "German": "DE",
    "Indonesian (Bahasa Indonesia)": "ID",
}


def _short_lang(lang: str | None) -> str:
    if not lang:
        return "??"
    return _LANG_SHORT.get(lang, lang[:2].upper())


def _doc_label(doc_type: str | None) -> str:
    if not doc_type:
        return "—"
    mapping = {"e-visa": "E-VISA", "e_visa": "E-VISA", "telex_visa": "TELEX VISA"}
    return mapping.get(doc_type, doc_type.upper())


_WRAPPER_STRINGS = {
    "id": {
        "title": "Yield mingguan — {n} klien · Minggu {week}",
        "warning": "⚠️ Ini DRAF. Belum dikirim ke klien. Cek dulu, baru kirim.",
        "draft_for_client": "Draf untuk klien ({lang}):",
        "expires_in_word": "habis",
        "expired_word": "sudah habis",
        "days_word": "hari",
        "days_ago_word": "hari lalu",
        "completed_services_word": "layanan selesai",
        "corporate_word": "Perusahaan terdaftar, belum ada layanan aktif",
        "warm_lead_word": "Kontak WA baru-baru ini, belum ada layanan",
        "no_recent_contact_word": "Tidak ada kontak baru-baru ini",
    },
    "en": {
        "title": "Weekly yield — {n} clients · Week of {week}",
        "warning": "⚠️ This is a DRAFT. Not sent to the client yet. Review first, then send.",
        "draft_for_client": "Draft for the client ({lang}):",
        "expires_in_word": "expires",
        "expired_word": "already expired",
        "days_word": "days",
        "days_ago_word": "days ago",
        "completed_services_word": "completed services",
        "corporate_word": "Registered company, no active service yet",
        "warm_lead_word": "Recent WhatsApp contact, no active service",
        "no_recent_contact_word": "No recent contact",
    },
    "it": {
        "title": "Yield settimanale — {n} clienti · Settimana del {week}",
        "warning": "⚠️ Questa è una BOZZA. Non ancora inviata al cliente. Rivedi prima di mandare.",
        "draft_for_client": "Bozza per il cliente ({lang}):",
        "expires_in_word": "scade",
        "expired_word": "già scaduto",
        "days_word": "giorni",
        "days_ago_word": "giorni fa",
        "completed_services_word": "servizi completati",
        "corporate_word": "Società registrata, nessun servizio attivo",
        "warm_lead_word": "Contatto WhatsApp recente, nessun servizio attivo",
        "no_recent_contact_word": "Nessun contatto recente",
    },
    "uk": {
        "title": "Щотижневий yield — {n} клієнтів · Тиждень {week}",
        "warning": "⚠️ Це ЧЕРНЕТКА. Ще не надіслано клієнту. Перевірте перед відправкою.",
        "draft_for_client": "Чернетка для клієнта ({lang}):",
        "expires_in_word": "закінчується",
        "expired_word": "вже закінчився",
        "days_word": "днів",
        "days_ago_word": "днів тому",
        "completed_services_word": "завершених послуг",
        "corporate_word": "Зареєстрована компанія, немає активної послуги",
        "warm_lead_word": "Недавній контакт WhatsApp, немає активної послуги",
        "no_recent_contact_word": "Немає недавнього контакту",
    },
}
_DOC_TYPES_WITH_EXPIRY = ("visa", "kitas", "e-visa", "e_visa", "telex_visa", "passport")


def _week_label() -> str:
    now = datetime.now(timezone.utc)
    monday = now - timedelta(days=now.weekday())
    return monday.strftime("%Y-%m-%d")


def _fact_line(language: str, signals: dict | None) -> str:
    s = _WRAPPER_STRINGS.get(language) or _WRAPPER_STRINGS["id"]
    signals = signals or {}
    doc_type = signals.get("document_type")
    days = signals.get("days_until_expiry")
    expiry = signals.get("expiry_date")

    if doc_type in _DOC_TYPES_WITH_EXPIRY and days is not None:
        label = _doc_label(doc_type)
        if days < 0:
            return f"{label} {s['expired_word']} {expiry} ({abs(days)} {s['days_ago_word']})"
        return f"{label} {s['expires_in_word']} {expiry} ({days} {s['days_word']})"
    if doc_type == "repeat" and days is not None:
        return f"{days} {s['completed_services_word']}"
    if doc_type == "corporate":
        return s["corporate_word"]
    if doc_type == "wa_warm":
        return s["warm_lead_word"]
    if doc_type == "last_contact":
        return f"{s['no_recent_contact_word']} ({expiry})" if expiry else s["no_recent_contact_word"]
    return _doc_label(doc_type)


def batch_rows(rows: list[dict], batch_size: int = BATCH_SIZE) -> list[list[dict]]:
    return [rows[i : i + batch_size] for i in range(0, len(rows), batch_size)]


def build_whatsapp_message(language: str, batch: list[dict]) -> str:
    """Builds ONE WhatsApp text for a single batch (<= BATCH_SIZE rows).

    ALLOWLIST formatter — reads only display_name / client_id / segment /
    lang / pitch / signals.{document_type,days_until_expiry,expiry_date} from
    each row. Any OTHER key a row might carry (a future sidecar field, a
    corrupted or malicious entry) is never touched, so this function
    structurally cannot leak a field it was never told to read — defense in
    depth on top of the fact that the generator never gives the drafting LLM
    a client's surname in the first place (only the first name), so the
    pitch text itself cannot leak a full name even before the content scan.
    """
    s = _WRAPPER_STRINGS.get(language) or _WRAPPER_STRINGS["id"]
    week = _week_label()
    lines = [s["title"].format(n=len(batch), week=week), "", s["warning"], ""]
    for i, row in enumerate(batch, start=1):
        display_name = str(row.get("display_name") or "Client")
        cid = row.get("client_id")
        fact = _fact_line(language, row.get("signals"))
        client_lang = _short_lang(row.get("lang"))
        pitch = str(row.get("pitch") or "").strip()
        lines.append(f"{i}. {display_name} · #{cid} · {fact}")
        lines.append(s["draft_for_client"].format(lang=client_lang))
        lines.append(f"> {pitch}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def send_whatsapp(team_email: str, text: str) -> tuple[bool, str]:
    """The ONLY sender in this file. Calls the backend's team-whatsapp
    primitive (`apps/backend-rag/backend/app/routers/cron_notifiers.py`
    `::run_team_whatsapp_send`, `POST /api/cron/notifiers/team-whatsapp`) —
    this process passes only an @balizero.com EMAIL, never a phone number;
    the server resolves active+number from team_members independently
    (Law-2 derogation, 'il cancello vive anche lato server' — the same fact
    is checked twice, on two machines). Never reads the response body on
    failure: an echoed request could carry the pitch text back into a caught
    exception's string, and this file's whole contract is that pitch text
    never lands in a log."""
    api_key = os.environ.get("NUZANTARA_API_KEY", "")
    if not api_key:
        return False, "NUZANTARA_API_KEY not set"
    payload = json.dumps({"team_email": team_email, "text": text}).encode()
    req = urllib.request.Request(
        TEAM_WHATSAPP_API_URL,
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
    except Exception as exc:  # noqa: BLE001 -- network failure is terminal for this batch, never a crash
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
    """Aggregate counts ONLY — zero client_id/nomi/numeri verso Telegram.

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
    ap.add_argument("--send", action="store_true", help="actually send WhatsApp messages (default: dry-run)")
    ap.add_argument(
        "--sidecar", action="append", default=None,
        help="explicit sidecar file(s), repeatable; default: latest per segment in --staging",
    )
    args = ap.parse_args()

    staging = Path(args.staging) if args.staging else STAGING
    registry_path = staging / "dispatch-registry.json"

    if args.send and not os.environ.get("NUZANTARA_API_KEY"):
        print(
            "[S7-dispatch] FATAL: --send requires NUZANTARA_API_KEY in env — aborting, nothing sent.",
            file=sys.stderr,
        )
        return 3

    sidecar_paths = [Path(p) for p in args.sidecar] if args.sidecar else discover_latest_sidecars(staging)
    if not sidecar_paths:
        print(f"[S7-dispatch] no sidecar files found under {staging} — nothing to do.")
        return 0

    all_rows: list[dict] = []
    for path in sidecar_paths:
        all_rows.extend(read_sidecar_rows(path))

    team = load_team_roster()
    current_assignments = load_current_assignments([r.get("client_id") for r in all_rows])
    registry = load_registry(registry_path)
    now = datetime.now(timezone.utc)

    held_counts, by_recipient, recipient_rows, cooldown_skipped, no_pitch = partition_rows(
        all_rows, team, registry, args.cooldown_days, now, current_assignments
    )

    valid_count = sum(len(rows) for rows in by_recipient.values())
    sent_or_simulated = 0

    for email, rows in by_recipient.items():
        language = recipient_rows.get(email, {}).get("language") or "id"
        for batch in batch_rows(rows):
            text = build_whatsapp_message(language, batch)
            if args.send:
                ok, err = send_whatsapp(email, text)
                if ok:
                    for row in batch:
                        mark_sent(registry, row.get("client_id"), row.get("segment"), now)
                    sent_or_simulated += len(batch)
                    print(f"[S7-dispatch] sent batch clients={len(batch)}")
                else:
                    print(f"[S7-dispatch] SEND FAILED clients={len(batch)} err={err}", file=sys.stderr)
            else:
                sent_or_simulated += len(batch)
                print(f"[S7-dispatch] DRY-RUN would send batch clients={len(batch)}")

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
