#!/usr/bin/env python3
"""wa-mirror attention Telegram alerter (Phase 1)

Two modes:
- `--digest`: send a single end-of-day summary (08:00 / 18:00 cron). Always sends.
- `--realtime`: scan for new HIGH messages since last_seen_state, alert only on
  critical reason codes (refund/complaint/deadline/payment_dispute/lawyer/audit).
  Dedup per phone within 4h.

OSINT-safe: Telegram message contains only:
- contact display_name + phone (last 4 digits masked)
- reason codes (no free text)
- N unresolved
- link to local dashboard (http://localhost:8767)

Raw body NEVER sent to Telegram cloud.

State: ~/.cache/wa-mirror-attention-state.json
"""
from __future__ import annotations
import asyncio
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import asyncpg

ENV_FILE = Path.home() / ".wa-mirror.env"


def read_env_file(path: Path) -> dict[str, str]:
    """Missing file = empty config, not an import-time crash.

    This used to be a bare `path.read_text()`, so importing this module on any
    machine without ~/.wa-mirror.env raised FileNotFoundError before a single
    line of logic ran. That is why this file had NO test corpus and why a PII
    leak sat in it unreviewed: the module could not be imported to be examined
    except on the one host that happens to have the file.

    Degrading is safe here because every consumer already has a fallback:
    DASHBOARD_URL goes through first_nonempty() to a literal default, and
    DB_URL being None fails loudly at the asyncpg call — a clear "no database
    configured" instead of a stack trace at line 38 of an import.
    """
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def first_nonempty(*values: str | None) -> str:
    for value in values:
        if value:
            return value
    return ""


ENV_VALUES = read_env_file(ENV_FILE)
# os.environ FIRST, matching how DASHBOARD_URL is already resolved below. Only
# the env FILE was consulted here, so there was no way to point this module at
# anything but the one host's live database — which, combined with the hard
# sys.exit(2) under it, made the module impossible to import for inspection
# anywhere else. A file that cannot be imported cannot be reviewed, and this
# one carried an unreviewed PII leak for a month.
DB_URL = first_nonempty(
    os.environ.get("WA_MIRROR_DATABASE_URL"),
    ENV_VALUES.get("WA_MIRROR_DATABASE_URL"),
)
if not DB_URL:
    print("ERR: WA_MIRROR_DATABASE_URL missing", file=sys.stderr)
    sys.exit(2)
# W57 (2026-05-26): removed legacy rewrite to pg-proxy Fly (cf. wa-mirror-attention-classifier.py).
# Post-cutover 2026-05-24 wa-mirror is LOCAL-ONLY → honor URL as written.
DB_URL = DB_URL.replace("postgres://","postgresql://")

DASHBOARD_URL = first_nonempty(os.environ.get("WA_DASHBOARD_URL"), ENV_VALUES.get("WA_DASHBOARD_URL")) or "http://localhost:8767"
STATE_PATH = Path.home() / ".cache" / "wa-mirror-attention-state.json"
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

CRITICAL_REASONS = {"refund", "complaint", "deadline", "payment_dispute", "lawyer", "audit"}
DEDUP_WINDOW = timedelta(hours=4)


def mask_phone(phone: str) -> str:
    """+62812****7456 — keep prefix(4) + suffix(4).

    A number too SHORT for that rule gets masked MORE, not less. The previous
    branch returned `f"+{phone}"` — the whole thing, in the clear, out of
    the function whose only job is not to do that. The masker was defeated by
    its own fallback, which is the same defect its callers had.
    """
    if not phone:
        return "+?"
    if len(phone) < 6:
        return "+" + "*" * len(phone)
    return f"+{phone[:4]}****{phone[-4:]}"


def contact_label(item: dict) -> str:
    """How a contact is NAMED in an alert. One rule, one place.

    Both compose paths (single contact / roster) inlined
    `display = crm_name or f"+{phone}"` and then printed `mask_phone(phone)`
    right after it. For a contact the CRM does not know — a NEW LEAD, i.e.
    exactly the case this alerter exists to surface — that rendered the FULL
    number and its masked form side by side:

        +6281312415572 — +6281****5572

    The masking was not bypassed; it was made pointless by the fallback
    standing next to it. This file's own docstring already promised "phone
    (last 4 digits masked)", so the leak breached its declared contract — it
    is not a judgement call (UU PDP Art. 67-68 / SYMBIOSIS Law 2).

    Two writers of one field means the rule lives in ONE function, so a third
    call site cannot reintroduce the leak by copying the old inline form.
    """
    masked = mask_phone(item.get("phone") or "")
    name = item.get("crm_name")
    return f"{name} — {masked}" if name else masked


def send_telegram(text: str, tier: str = "p0", dedup_key: str = "") -> bool:
    """Route through the notification gateway (cohort-2, 2026-07-07).

    Realtime criticals → tier p0 (immediate, daily budget); daily summary →
    tier digest (merged into the ONE grouped gateway digest). Gateway owns
    token resolution + 6h dedup; plain text only (no parse_mode).
    Returns True if the gateway accepted (sent or spooled).
    """
    gateway = Path(__file__).resolve().parent / "tg_notify.py"
    if not gateway.is_file():
        root = Path(os.environ.get("NUZANTARA_ROOT", str(Path.home() / "Desktop" / "nuzantara")))
        gateway = root / "scripts" / "tg_notify.py"
    cmd = [sys.executable, str(gateway), "--tier", tier, "--source", "wa-attention"]
    if dedup_key:
        cmd += ["--dedup-key", dedup_key]
    cmd += ["--", text]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        raw = (proc.stderr or "") + "\n" + (proc.stdout or "")
        outcome = ""
        for line in raw.splitlines():
            if line.startswith("tg_notify:"):
                outcome = line.split(":", 1)[1].strip().split(" ")[0]
        return outcome in ("sent", "spooled", "logged", "p0_overflow_spooled", "p0_unsent_spooled")
    except Exception as e:
        print(f"ERR: gateway send: {e}", file=sys.stderr)
        return False


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"last_alerted": {}, "last_digest_at": None}
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {"last_alerted": {}, "last_digest_at": None}


def save_state(state: dict):
    STATE_PATH.write_text(json.dumps(state, indent=2, default=str))


async def fetch_high_unresolved(conn: asyncpg.Connection) -> list[dict]:
    rows = await conn.fetch("""
      WITH highs AS (
        SELECT
          REGEXP_REPLACE(m.raw_baileys_event->'key'->>'senderPn', '@.*', '') AS phone,
          MIN(m.id) AS first_high_id,
          MAX(m.id) AS last_high_id,
          MIN(m.created_at) AS first_high_at,
          MAX(m.created_at) AS last_high_at,
          COUNT(*) AS n_high,
          ARRAY_AGG(DISTINCT reason) AS reasons
        FROM whatsapp_message_context m,
             LATERAL UNNEST(COALESCE(m.attention_reason, ARRAY[]::text[])) AS reason
        WHERE m.attention_priority = 'HIGH'
          AND m.attention_resolved_at IS NULL
          AND m.direction = 'inbound'
          AND m.raw_baileys_event->'key'->>'senderPn' ~ '^[0-9]+@'
        GROUP BY 1
      )
      SELECT h.*,
             c.id AS crm_id, c.full_name AS crm_name, c.status AS crm_status, c.lead_source
      FROM highs h
      LEFT JOIN clients c ON c.phone_normalized = h.phone AND c.deleted_at IS NULL
      ORDER BY h.last_high_at DESC
    """)
    return [dict(r) for r in rows]


async def fetch_digest_metrics(conn: asyncpg.Connection) -> dict:
    """Aggregate metrics for end-of-day digest (last 24h window)."""
    row = await conn.fetchrow("""
      WITH window_msgs AS (
        SELECT * FROM whatsapp_message_context
        WHERE direction='inbound'
          AND created_at >= NOW() - INTERVAL '24 hours'
          AND raw_baileys_event->'key'->>'senderPn' ~ '^[0-9]+@'
      )
      SELECT
        COUNT(*) FILTER (WHERE attention_priority='HIGH' AND attention_resolved_at IS NULL) AS high_open,
        COUNT(*) FILTER (WHERE attention_priority='HIGH' AND attention_resolved_at IS NOT NULL) AS high_resolved,
        COUNT(*) FILTER (WHERE attention_priority='MEDIUM') AS medium,
        COUNT(DISTINCT REGEXP_REPLACE(raw_baileys_event->'key'->>'senderPn','@.*','')) AS distinct_phones_24h,
        COUNT(*) AS inbound_24h
      FROM window_msgs
    """)
    new_leads = await conn.fetchval("""
      SELECT COUNT(*) FROM clients
      WHERE created_by='wa-mirror-auto-promote'
        AND created_at >= NOW() - INTERVAL '24 hours'
    """)
    return {**dict(row), "new_leads_24h": new_leads}


def _load_episodes(state: dict) -> dict:
    """Read episode state, migrating the pre-2026-08-08 `last_alerted` shape.

    Old shape: {"<phone>:<reason>": "<iso ts>"} — one entry per contact+reason,
    the value a bare timestamp. New shape is keyed on PHONE alone and carries
    the reason set that has already bought a P0:

        {"<phone>": {"ts": "<iso>", "reasons": ["deadline", ...]}}

    Keyed on phone, NOT on phone+reason, and that is the whole point: the old
    key embedded `sorted(critical)[0]`, so a contact whose reasons IMPROVED
    from ["audit","deadline"] to ["deadline"] would change key, look brand new,
    and buy a fresh P0 — an alert fired by things getting better.

    Migration treats a legacy entry as an episode ALREADY in progress. That is
    the quiet direction on purpose: the loud alternative would read every one
    of the ~9 live contacts as a first entry and fire a P0 burst on the first
    run after deploy, which is the exact failure this change exists to end.
    """
    raw = state.get("episodes")
    if isinstance(raw, dict):
        return raw
    migrated: dict = {}
    for key, ts in (state.get("last_alerted") or {}).items():
        if not isinstance(key, str):
            continue
        phone, _, reason = key.partition(":")
        ep = migrated.setdefault(phone, {"ts": ts if isinstance(ts, str) else "", "reasons": []})
        if reason and reason not in ep["reasons"]:
            ep["reasons"].append(reason)
    return migrated


async def cmd_realtime(force: bool = False):
    state = load_state()
    episodes = _load_episodes(state)
    now = datetime.now(timezone.utc)

    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=2, ssl=False)
    try:
        async with pool.acquire() as conn:
            items = await fetch_high_unresolved(conn)
    finally:
        await pool.close()

    # PASS 1 — decide WHO is due and AT WHICH TIER, without sending anything
    # yet. A scan that finds N due contacts used to send N separate P0s: on
    # 2026-07-26 that was 8 messages in 60 seconds, which ate the gateway's
    # whole daily P0 budget (12) by 02:01. One scan is one message per tier.
    #
    # Tier rule (Zero, 2026-08-08). Measured on the live spool that day:
    # wa-attention was 165 of the 390 P0s the whole organism delivered in 32
    # days — 42.3% of every immediate alert — for NINE recurring conditions
    # re-raised roughly every 11 hours. The budget is 12/day and ran fully
    # consumed every single day, so those repeats were not "extra" news: they
    # were pushing OTHER sources' genuine P0s into the digest.
    #
    #   first entry into HIGH  → p0   (news)
    #   condition persists     → digest (already told you; the digest groups by
    #                            source, so all of it costs ONE line)
    #   a NEW critical reason  → p0   (genuinely worse, not merely still true)
    #
    # An episode ENDS when the contact leaves the HIGH-unresolved set; the
    # pruning below is what makes "first entry" mean first entry rather than
    # first ever.
    first_or_worse: list = []
    persisting: list = []
    live_phones: set = set()
    for it in items:
        critical = [r for r in (it["reasons"] or []) if r in CRITICAL_REASONS]
        if not critical:
            continue
        phone = it["phone"]
        live_phones.add(phone)
        # DELIBERATE, not an oversight: this key is the LOCAL 4h dedup state in
        # ~/.cache/wa-mirror-attention-state.json. It never reaches Telegram and
        # never reaches the gateway spool — the wire key is the sha256 set
        # signature below. CLAUDE.md §14 / SYMBIOSIS Law 2 draw the line at
        # OUTPUT, not at local processing: "il processing PII resta
        # locale-sovrano sul Pro". Recorded here so the next reader can tell a
        # considered boundary from a missed one.
        cur = sorted(critical)
        ep = episodes.get(phone)
        if ep is None:
            first_or_worse.append((phone, it, cur))
            continue
        already = set(ep.get("reasons") or [])
        if set(cur) - already:
            # A reason we have never alerted on for this open episode.
            first_or_worse.append((phone, it, cur))
            continue
        # Still true, nothing new. Goes to the digest, rate-limited by the same
        # window as before so a 10-minute scan cannot write 144 spool records a
        # day per contact — the digest collapses to one LINE, not one EVENT.
        if force:
            persisting.append((phone, it, cur))
            continue
        try:
            if now - datetime.fromisoformat(ep.get("ts") or "") >= DEDUP_WINDOW:
                persisting.append((phone, it, cur))
        except (TypeError, ValueError):
            # Unparseable stored timestamp: treat as due rather than sit silent.
            persisting.append((phone, it, cur))

    # PASS 2 — at most one message per tier for the whole scan.
    alerted = 0
    messages = 0

    def _emit(batch: list, tier: str, prefix: str) -> bool:
        # Keyed on the exact set of contacts, so a scan repeating the same set
        # collapses into a counter at the gateway instead of a new message.
        sig = hashlib.sha256(",".join(sorted(p for p, _, _ in batch)).encode()).hexdigest()[:12]
        msg = _compose_realtime_alert([(p, it, c) for p, it, c in batch], tier=tier)
        return send_telegram(msg, tier=tier, dedup_key=f"wa-attention:{prefix}:{sig}")

    if first_or_worse and _emit(first_or_worse, "p0", "new"):
        for phone, _, cur in first_or_worse:
            ep = episodes.setdefault(phone, {"reasons": []})
            ep["ts"] = now.isoformat()
            ep["reasons"] = sorted(set(ep.get("reasons") or []) | set(cur))
        alerted += len(first_or_worse)
        messages += 1

    if persisting and _emit(persisting, "digest", "still"):
        for phone, _, _ in persisting:
            episodes.setdefault(phone, {"reasons": []})["ts"] = now.isoformat()
        messages += 1

    # An episode ends when the contact drops out of the HIGH-unresolved set.
    # Without this the state grows forever and, worse, a contact who is
    # resolved and later comes back would be read as "already told you" and
    # never earn the P0 that a genuinely new problem deserves.
    episodes = {p: v for p, v in episodes.items() if p in live_phones}

    state["episodes"] = episodes
    state.pop("last_alerted", None)
    save_state(state)
    print(json.dumps({"alerted": alerted, "messages": messages,
                      "persisting": len(persisting), "high_open": len(items),
                      "ts": now.isoformat()}))


def _compose_realtime_alert(due: list, tier: str = "p0") -> str:
    """One contact keeps the full detail; several become a compact roster.

    Same OSINT envelope as before either way: display name, masked phone,
    reason codes, unresolved count, dashboard link. No free text ever.

    `tier` only changes the HEADLINE, never the envelope. A digest batch is a
    reminder about something already reported, and it has to SAY so — a
    "🚨 HIGH attention" banner on the fourth reminder of the same contact is
    how a reader learns to stop reading the banner.
    """
    banner = "🚨 HIGH attention" if tier == "p0" else "🔔 still unresolved"
    if len(due) == 1:
        _, it, critical = due[0]
        crm_tag = f"CRM #{it['crm_id']}" if it["crm_id"] else "new lead"
        return (
            f"{banner}\n"
            f"{contact_label(it)}\n"
            f"{crm_tag} · {it['n_high']} unresolved msg\n"
            f"Reasons: {', '.join(critical)}\n"
            f"→ {DASHBOARD_URL}"
        )
    lines = [f"{banner} — {len(due)} contacts"]
    for _, it, critical in due:
        crm_tag = f"CRM #{it['crm_id']}" if it["crm_id"] else "new lead"
        lines.append(
            f"• {contact_label(it)}\n"
            f"  {crm_tag} · {it['n_high']} unresolved · {', '.join(critical)}"
        )
    lines.append(f"→ {DASHBOARD_URL}")
    return "\n".join(lines)


async def cmd_digest():
    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=2, ssl=False)
    try:
        async with pool.acquire() as conn:
            metrics = await fetch_digest_metrics(conn)
            items = await fetch_high_unresolved(conn)
    finally:
        await pool.close()

    now_iso = datetime.now(timezone.utc).isoformat()
    lines = [
        "📊 WA mirror daily digest",
        datetime.now().strftime("%a %d %b %Y, %H:%M WITA"),
        "",
        "Last 24h:",
        f"  • {metrics['inbound_24h']} inbound msgs from {metrics['distinct_phones_24h']} contacts",
        f"  • {metrics['high_open']} HIGH unresolved · {metrics['high_resolved']} resolved",
        f"  • {metrics['medium']} MEDIUM",
        f"  • {metrics['new_leads_24h']} new leads auto-promoted to CRM",
    ]
    if items:
        lines.append("")
        lines.append("🚨 Needs your attention:")
        for it in items[:8]:  # cap to 8 to keep msg readable
            # The digest path had the SAME leak as the realtime one and was
            # worse: here there is no mask_phone() alongside, so for a contact
            # the CRM does not know the raw number was the ONLY rendering — and
            # this mode "always sends", twice a day. It survived the first pass
            # because the census looked for the FORM of the line already found
            # (`display` / `phone`); this one says `name` / `it['phone']`.
            # A pattern written from the instance you found catches the
            # instance you found.
            name = contact_label(it)
            crm_marker = "" if it["crm_id"] else " (new lead)"
            crit = [r for r in (it["reasons"] or []) if r in CRITICAL_REASONS]
            unanswered = "unanswered_thread_3plus" in (it["reasons"] or [])
            tags = crit[:3]
            if unanswered:
                tags.append("⏰thread")
            lines.append(f"  • {name}{crm_marker} — {it['n_high']} msg · {' '.join(tags)}")
        if len(items) > 8:
            lines.append(f"  …and {len(items)-8} more")
    else:
        lines.append("")
        lines.append("🟢 Everything is acknowledged.")

    lines.append("")
    lines.append(f"→ {DASHBOARD_URL}")
    msg = "\n".join(lines)
    # tier digest: merged into the gateway's grouped digest (2×/day slots align
    # with the historical 08:00/18:00 cron). Dedup key varies by day+hour so a
    # morning and an evening digest both pass the 6h gateway window.
    ok = send_telegram(msg, tier="digest",
                       dedup_key=f"wa-daily-digest:{datetime.now().strftime('%Y%m%d%H')}")
    print(json.dumps({"sent": ok, "high_open": len(items), "ts": now_iso}))


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--digest", action="store_true")
    p.add_argument("--realtime", action="store_true")
    p.add_argument("--force", action="store_true", help="bypass dedup (test only)")
    args = p.parse_args()
    if args.digest:
        await cmd_digest()
    elif args.realtime:
        await cmd_realtime(force=args.force)
    else:
        # default: realtime
        await cmd_realtime(force=False)


if __name__ == "__main__":
    asyncio.run(main())
