#!/usr/bin/env python3
"""Reactivation Email Campaign — Segment & Send to Silent Clients.

Finds clients with zero interaction in 30+ days, segments them into
three groups (Urgent / Active Case / Re-Engage), generates a CSV
report, and optionally sends batched emails via the notification API.

Usage:
    cd apps/backend-rag
    source .venv/bin/activate

    # Generate CSV only (default: dry-run)
    PYTHONPATH=. python scripts/reactivation_email_campaign.py

    # Filter by segment
    PYTHONPATH=. python scripts/reactivation_email_campaign.py --segment A

    # Send first 10 emails from segment A
    PYTHONPATH=. python scripts/reactivation_email_campaign.py --segment A --send-batch 10
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg
import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_db_raw: str | None = os.environ.get("DATABASE_URL")
if not _db_raw:
    print("ERROR: DATABASE_URL environment variable is required.", file=sys.stderr)
    sys.exit(1)
DATABASE_URL: str = _db_raw.replace("postgres://", "postgresql://") if _db_raw.startswith("postgres://") else _db_raw

SEND_EMAIL_URL: str = os.environ.get(
    "SEND_EMAIL_URL",
    "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
SEND_EMAIL_API_KEY: str = os.environ.get("SEND_EMAIL_API_KEY", "REDACTED-ROTATED-KEY")
FROM_NAME: str = "Zantara"
FROM_EMAIL: str = "zantara@balizero.com"

OUTPUT_DIR: Path = Path(__file__).resolve().parent / "output"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("reactivation_campaign")


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
QUERY_SILENT_CLIENTS: str = """
    SELECT c.id, c.full_name, c.email, c.status, c.assigned_to,
           c.last_interaction_date,
           d.document_type, d.expiry_date
    FROM clients c
    LEFT JOIN documents d ON d.client_id = c.id AND d.expiry_date IS NOT NULL
    WHERE c.email IS NOT NULL AND c.email != ''
      AND (c.last_interaction_date < NOW() - INTERVAL '30 days'
           OR c.last_interaction_date IS NULL)
      AND c.status IN ('active', 'prospect', 'lead')
    ORDER BY d.expiry_date ASC NULLS LAST
"""

QUERY_ACTIVE_PRACTICES: str = """
    SELECT client_id, practice_type_code AS practice_type, status, assigned_to
    FROM practices
    WHERE status = 'in_progress'
"""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
class CampaignEntry:
    """A single client entry in the campaign."""

    __slots__ = (
        "client_id",
        "full_name",
        "email",
        "segment",
        "subject",
        "personalization_data",
        "assigned_to",
        "status",
    )

    def __init__(
        self,
        *,
        client_id: int,
        full_name: str,
        email: str,
        segment: str,
        subject: str,
        personalization_data: dict[str, Any],
        assigned_to: str,
        status: str,
    ) -> None:
        self.client_id = client_id
        self.full_name = full_name
        self.email = email
        self.segment = segment
        self.subject = subject
        self.personalization_data = personalization_data
        self.assigned_to = assigned_to
        self.status = status

    def as_csv_row(self) -> dict[str, str]:
        """Return a dict suitable for csv.DictWriter."""
        return {
            "client_id": str(self.client_id),
            "full_name": self.full_name,
            "email": self.email,
            "segment": self.segment,
            "subject": self.subject,
            "personalization_data": json.dumps(
                self.personalization_data, default=str
            ),
            "assigned_to": self.assigned_to or "",
        }


# ---------------------------------------------------------------------------
# Segmentation logic
# ---------------------------------------------------------------------------
async def fetch_silent_clients(pool: asyncpg.Pool) -> list[dict[str, Any]]:
    """Fetch clients with no interaction in 30+ days."""
    rows: list[asyncpg.Record] = await pool.fetch(QUERY_SILENT_CLIENTS)
    return [dict(r) for r in rows]


async def fetch_active_practices(pool: asyncpg.Pool) -> dict[int, dict[str, Any]]:
    """Fetch in-progress practices, keyed by client_id (first match wins)."""
    rows: list[asyncpg.Record] = await pool.fetch(QUERY_ACTIVE_PRACTICES)
    practices: dict[int, dict[str, Any]] = {}
    for row in rows:
        cid: int = row["client_id"]
        if cid not in practices:
            practices[cid] = dict(row)
    return practices


def _format_date(d: date | datetime | None) -> str:
    """Format a date for display, or return 'N/A'."""
    if d is None:
        return "N/A"
    if isinstance(d, datetime):
        return d.strftime("%d %B %Y")
    return d.strftime("%d %B %Y")


def _doc_type_display(doc_type: str | None) -> str:
    """Human-readable document type."""
    if not doc_type:
        return "document"
    return (
        doc_type.replace("_", " ")
        .title()
        .replace("Kitas", "KITAS")
        .replace("Kitap", "KITAP")
        .replace("Npwp", "NPWP")
    )


def segment_clients(
    clients: list[dict[str, Any]],
    practices: dict[int, dict[str, Any]],
) -> list[CampaignEntry]:
    """Segment clients into A (Urgent), B (Active Case), C (Re-Engage).

    Deduplicates by client_id: a client appears only once in the
    highest-priority segment (A > B > C).
    """
    today: date = date.today()
    ninety_days = today.toordinal() + 90

    seen_ids: set[int] = set()
    entries: list[CampaignEntry] = []

    # --- Pass 1: Segment A — document expiring within 90 days ---
    for row in clients:
        cid: int = row["id"]
        if cid in seen_ids:
            continue
        expiry: date | datetime | None = row.get("expiry_date")
        if expiry is None:
            continue
        expiry_ord: int = (
            expiry.date().toordinal()
            if isinstance(expiry, datetime)
            else expiry.toordinal()
        )
        if expiry_ord <= ninety_days:
            doc_display: str = _doc_type_display(row.get("document_type"))
            entries.append(
                CampaignEntry(
                    client_id=cid,
                    full_name=row["full_name"] or "",
                    email=row["email"],
                    segment="A",
                    subject=f"Important: Your {doc_display} expires on {_format_date(expiry)}",
                    personalization_data={
                        "document_type": doc_display,
                        "expiry_date": _format_date(expiry),
                        "days_until_expiry": expiry_ord - today.toordinal(),
                    },
                    assigned_to=row.get("assigned_to") or "",
                    status=row.get("status") or "",
                )
            )
            seen_ids.add(cid)

    # --- Pass 2: Segment B — has in-progress practice ---
    for row in clients:
        cid = row["id"]
        if cid in seen_ids:
            continue
        practice: dict[str, Any] | None = practices.get(cid)
        if practice is not None:
            ptype: str = (practice.get("practice_type") or "case").replace("_", " ").title()
            entries.append(
                CampaignEntry(
                    client_id=cid,
                    full_name=row["full_name"] or "",
                    email=row["email"],
                    segment="B",
                    subject=f"Update on your {ptype}",
                    personalization_data={
                        "practice_type": ptype,
                        "practice_status": practice.get("status") or "",
                    },
                    assigned_to=row.get("assigned_to") or "",
                    status=row.get("status") or "",
                )
            )
            seen_ids.add(cid)

    # --- Pass 3: Segment C — re-engage (lead/prospect, no urgency) ---
    for row in clients:
        cid = row["id"]
        if cid in seen_ids:
            entries.append(  # skip duplicate
                CampaignEntry(
                    client_id=cid,
                    full_name="",
                    email="",
                    segment="",
                    subject="",
                    personalization_data={},
                    assigned_to="",
                    status="",
                )
            ) if False else None
            continue
        entries.append(
            CampaignEntry(
                client_id=cid,
                full_name=row["full_name"] or "",
                email=row["email"],
                segment="C",
                subject="Still planning your move to Bali?",
                personalization_data={
                    "last_interaction": _format_date(row.get("last_interaction_date")),
                    "client_status": row.get("status") or "",
                },
                assigned_to=row.get("assigned_to") or "",
                status=row.get("status") or "",
            )
        )
        seen_ids.add(cid)

    return entries


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------
def write_csv(entries: list[CampaignEntry]) -> Path:
    """Write campaign entries to a timestamped CSV file. Return the path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today_str: str = date.today().isoformat()
    filepath: Path = OUTPUT_DIR / f"reactivation_campaign_{today_str}.csv"

    fieldnames: list[str] = [
        "client_id",
        "full_name",
        "email",
        "segment",
        "subject",
        "personalization_data",
        "assigned_to",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            writer.writerow(entry.as_csv_row())

    return filepath


# ---------------------------------------------------------------------------
# Email HTML templates
# ---------------------------------------------------------------------------
def _html_wrapper(body_content: str, first_name: str) -> str:
    """Wrap body content in a branded HTML email template."""
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:24px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;">
  <tr><td style="background:#0f766e;padding:24px 32px;">
    <h1 style="color:#ffffff;margin:0;font-size:22px;">Bali Zero</h1>
    <p style="color:#d4845a;margin:4px 0 0;font-size:13px;">Your trusted partner in Indonesia</p>
  </td></tr>
  <tr><td style="padding:32px;">
    <p style="color:#333;font-size:15px;line-height:1.6;">Hi {first_name},</p>
    {body_content}
    <p style="color:#333;font-size:15px;line-height:1.6;margin-top:24px;">
      Warm regards,<br><strong>Zantara</strong><br>
      <span style="color:#888;font-size:13px;">Bali Zero AI Assistant</span>
    </p>
  </td></tr>
  <tr><td style="background:#f9fafb;padding:16px 32px;text-align:center;">
    <p style="color:#999;font-size:12px;margin:0;">
      Bali Zero &mdash; Visa, Company Setup, Tax &amp; Property Services in Bali<br>
      <a href="https://balizero.com" style="color:#0f766e;">balizero.com</a>
    </p>
    <p style="color:#bbb;font-size:11px;margin:8px 0 0;">
      You received this email because you are a client of Bali Zero.
      To unsubscribe, reply with &ldquo;UNSUBSCRIBE&rdquo; or email
      <a href="mailto:zantara@balizero.com?subject=Unsubscribe" style="color:#999;">zantara@balizero.com</a>.
    </p>
  </td></tr>
</table>
</td></tr></table>
</body>
</html>"""


def build_email_html(entry: CampaignEntry) -> str:
    """Build segment-specific HTML email body."""
    first_name: str = (entry.full_name.split()[0] if entry.full_name else "there")
    data: dict[str, Any] = entry.personalization_data

    if entry.segment == "A":
        doc_type: str = data.get("document_type", "document")
        expiry: str = data.get("expiry_date", "soon")
        days: int = data.get("days_until_expiry", 0)
        urgency: str = (
            "This requires immediate attention."
            if days <= 30
            else "We recommend starting the renewal process soon."
        )
        body = f"""\
    <p style="color:#333;font-size:15px;line-height:1.6;">
      We noticed that your <strong>{doc_type}</strong> is set to expire on
      <strong>{expiry}</strong> ({days} days from now).
    </p>
    <p style="color:#333;font-size:15px;line-height:1.6;">
      {urgency} Renewal processing typically takes 2-4 weeks, so
      getting started now will help ensure there are no gaps in your
      documentation.
    </p>
    <p style="text-align:center;margin:28px 0;">
      <a href="https://kita.balizero.com" style="background:#0f766e;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-size:15px;font-weight:600;">
        Start Renewal Process
      </a>
    </p>
    <p style="color:#666;font-size:14px;line-height:1.6;">
      Simply reply to this email or contact us on WhatsApp, and your
      dedicated consultant will guide you through the renewal.
    </p>"""

    elif entry.segment == "B":
        ptype: str = data.get("practice_type", "case")
        body = f"""\
    <p style="color:#333;font-size:15px;line-height:1.6;">
      We wanted to touch base regarding your <strong>{ptype}</strong>
      that is currently in progress with us.
    </p>
    <p style="color:#333;font-size:15px;line-height:1.6;">
      We may need some additional information or documents from you to
      keep things moving forward. Your consultant is ready to assist
      you with the next steps.
    </p>
    <p style="text-align:center;margin:28px 0;">
      <a href="https://kita.balizero.com" style="background:#0f766e;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-size:15px;font-weight:600;">
        Check My Portal
      </a>
    </p>
    <p style="color:#666;font-size:14px;line-height:1.6;">
      Log in to your portal to see the latest status, or simply reply
      to this email for a quick update.
    </p>"""

    else:  # Segment C
        body = """\
    <p style="color:#333;font-size:15px;line-height:1.6;">
      It's been a while since we last connected, and we wanted to check
      in on your plans for Indonesia.
    </p>
    <p style="color:#333;font-size:15px;line-height:1.6;">
      Whether you're exploring visa options, thinking about setting up a
      company, or considering property in Bali, our team is here to help
      make the process smooth and straightforward.
    </p>
    <p style="text-align:center;margin:28px 0;">
      <a href="https://balizero.com" style="background:#0f766e;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;font-size:15px;font-weight:600;">
        Explore Our Services
      </a>
    </p>
    <p style="color:#666;font-size:14px;line-height:1.6;">
      Feel free to reply to this email with any questions. We're always
      happy to help.
    </p>"""

    return _html_wrapper(body, first_name)


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------
async def send_email(
    client: httpx.AsyncClient,
    entry: CampaignEntry,
) -> bool:
    """Send a single reactivation email via the notification API."""
    html: str = build_email_html(entry)
    payload: dict[str, str] = {
        "to": entry.email,
        "subject": entry.subject,
        "body": html,
    }
    try:
        resp = await client.post(
            SEND_EMAIL_URL,
            json=payload,
            headers={"X-API-Key": SEND_EMAIL_API_KEY},
            timeout=30.0,
        )
        if resp.status_code == 200:
            logger.info(f"  Sent to {entry.email} (client {entry.client_id})")
            return True
        logger.error(
            f"  Failed {entry.email}: HTTP {resp.status_code} — {resp.text[:200]}"
        )
    except httpx.HTTPError as exc:
        logger.error(f"  Failed {entry.email}: {exc}")
    return False


async def send_batch(
    http_client: httpx.AsyncClient,
    entries: list[CampaignEntry],
    batch_size: int,
) -> int:
    """Send emails for the first `batch_size` entries. Return sent count."""
    to_send: list[CampaignEntry] = entries[:batch_size]
    logger.info(f"Sending {len(to_send)} emails...")
    sent: int = 0
    for entry in to_send:
        ok: bool = await send_email(http_client, entry)
        if ok:
            sent += 1
        # Small delay to avoid rate-limiting
        await asyncio.sleep(0.5)
    return sent


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def print_summary(entries: list[CampaignEntry]) -> None:
    """Print a summary of the segmentation."""
    seg_a: list[CampaignEntry] = [e for e in entries if e.segment == "A"]
    seg_b: list[CampaignEntry] = [e for e in entries if e.segment == "B"]
    seg_c: list[CampaignEntry] = [e for e in entries if e.segment == "C"]

    logger.info("")
    logger.info("=" * 60)
    logger.info("  REACTIVATION CAMPAIGN SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  Total silent clients (30+ days): {len(entries)}")
    logger.info("")
    logger.info(f"  Segment A (URGENT — doc expiring <90d): {len(seg_a)}")
    logger.info(f"  Segment B (ACTIVE CASE — in-progress):  {len(seg_b)}")
    logger.info(f"  Segment C (RE-ENGAGE — lead/prospect):  {len(seg_c)}")
    logger.info("=" * 60)

    # Show first 5 of each segment
    for label, seg in [("A", seg_a), ("B", seg_b), ("C", seg_c)]:
        if seg:
            logger.info(f"\n  Segment {label} preview (first 5):")
            for entry in seg[:5]:
                logger.info(
                    f"    [{entry.client_id}] {entry.full_name:<25} "
                    f"{entry.email:<30} | {entry.subject[:50]}"
                )
    logger.info("")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main(
    *,
    dry_run: bool = True,
    send_batch_size: int = 0,
    segment_filter: str | None = None,
) -> None:
    """Run the reactivation campaign pipeline."""
    logger.info("Connecting to database...")
    pool: asyncpg.Pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)
    http_client: httpx.AsyncClient = httpx.AsyncClient()

    try:
        # 1. Fetch data
        logger.info("Fetching silent clients (30+ days no interaction)...")
        raw_clients: list[dict[str, Any]] = await fetch_silent_clients(pool)
        logger.info(f"  Found {len(raw_clients)} rows (may include duplicates from JOIN)")

        logger.info("Fetching active practices...")
        practices: dict[int, dict[str, Any]] = await fetch_active_practices(pool)
        logger.info(f"  Found {len(practices)} clients with in-progress practices")

        # 2. Segment
        all_entries: list[CampaignEntry] = segment_clients(raw_clients, practices)
        logger.info(f"Segmented into {len(all_entries)} unique client entries")

        # 3. Apply segment filter
        entries: list[CampaignEntry]
        if segment_filter:
            entries = [e for e in all_entries if e.segment == segment_filter.upper()]
            logger.info(
                f"Filtered to segment {segment_filter.upper()}: {len(entries)} entries"
            )
        else:
            entries = all_entries

        # 4. Print summary
        print_summary(entries)

        # 5. Write CSV
        csv_path: Path = write_csv(entries)
        logger.info(f"CSV written to: {csv_path}")

        # 6. Send emails if requested
        if send_batch_size > 0 and not dry_run:
            sent: int = await send_batch(http_client, entries, send_batch_size)
            logger.info(f"Sent {sent}/{min(send_batch_size, len(entries))} emails successfully")
        elif send_batch_size > 0 and dry_run:
            logger.info(
                f"DRY RUN — would send {min(send_batch_size, len(entries))} emails. "
                "Remove --dry-run or pass --send-batch without --dry-run to send."
            )
        else:
            logger.info("No emails sent (use --send-batch N to send)")

    finally:
        await http_client.aclose()
        await pool.close()


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Generate reactivation email campaign for silent CRM clients."
    )
    parser.add_argument(
        "--send",
        action="store_true",
        default=False,
        help="Enable sending mode. Without this flag, only CSV is generated.",
    )
    parser.add_argument(
        "--send-batch",
        type=int,
        default=0,
        dest="send_batch",
        help="Send first N emails. Requires --send flag.",
    )
    parser.add_argument(
        "--segment",
        type=str,
        choices=["A", "B", "C", "a", "b", "c"],
        default=None,
        help="Filter to a specific segment (A=urgent, B=active case, C=re-engage).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args: argparse.Namespace = parse_args()
    dry_run: bool = not args.send
    if args.send_batch > 0 and not args.send:
        logger.error(
            "--send-batch requires --send flag. "
            "Run with --send --send-batch N to actually send emails."
        )
        sys.exit(1)
    if not dry_run:
        logger.info(
            f"SEND MODE — will send up to {args.send_batch} emails via API"
        )
    else:
        logger.info("DRY-RUN mode — CSV generation only, no emails sent")

    asyncio.run(
        main(
            dry_run=dry_run,
            send_batch_size=args.send_batch,
            segment_filter=args.segment,
        )
    )
