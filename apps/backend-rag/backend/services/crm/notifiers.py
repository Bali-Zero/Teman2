"""
CRM Notifiers — consolidated module.

Merges:
  - birthday_notifier_service.py  (BirthdayNotifierService, run_birthday_notifier_task)
  - stale_practice_notifier.py    (StalePracticeNotifier, run_stale_practice_notifier_task)
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any

import asyncpg
import httpx

from backend.app.utils.logging_utils import get_logger
from backend.services.integrations.zoho_email_service import ZohoEmailService

logger = get_logger(__name__)

# Internal email API — uses Brevo, from=zantara@balizero.com
_EMAIL_API_URL = os.getenv(
    "INTERNAL_EMAIL_API_URL", "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
_EMAIL_API_KEY = os.getenv("NUZANTARA_API_KEY", "REDACTED-ROTATED-KEY")


# ─────────────────────────────────────────────────────────────────────────────
# BirthdayNotifierService (from birthday_notifier_service.py)
# ─────────────────────────────────────────────────────────────────────────────

# System user ID for sending emails via Zoho (zero@balizero.com UUID)
SYSTEM_SENDER_USER_ID = "7dfe56b2-ff63-4d40-b78b-90c018127a02"

NATIONALITY_LANGUAGE_MAP: dict[str, str] = {
    "Italian": "it", "Italy": "it", "IT": "it",
    "American": "en", "USA": "en", "United States": "en",
    "British": "en", "UK": "en", "United Kingdom": "en",
    "Australian": "en", "Australia": "en",
    "Canadian": "en", "Canada": "en",
    "Irish": "en", "Ireland": "en",
    "New Zealand": "en", "Kiwi": "en",
    "Indonesian": "id", "Indonesia": "id", "ID": "id",
    "Ukrainian": "uk", "Ukraine": "uk", "UA": "uk",
    "Russian": "ru", "Russia": "ru", "RU": "ru",
    "German": "en", "Germany": "en", "DE": "en",
    "French": "en", "France": "en", "FR": "en",
    "Dutch": "en", "Netherlands": "en", "NL": "en",
}

BIRTHDAY_TEMPLATES: dict[str, dict[str, str]] = {
    "it": {
        "subject": "Buon Compleanno da Bali Zero!",
        "greeting": "Caro/a {name},",
        "message": (
            "\nTi auguriamo un fantastico compleanno! Che questo nuovo anno ti porti tanta gioia, "
            "successo e bellissime avventure.\n\n{personalized_note}\n\nSe hai bisogno di assistenza "
            "con visti, permessi o qualsiasi altra cosa legata alla tua permanenza in Indonesia, "
            "siamo sempre qui per te.\n\nCon i migliori auguri,\nIl Team Bali Zero\n"
        ),
    },
    "en": {
        "subject": "Happy Birthday from Bali Zero!",
        "greeting": "Dear {name},",
        "message": (
            "\nWishing you a wonderful birthday! May this new year bring you joy, success, "
            "and amazing adventures.\n\n{personalized_note}\n\nIf you need assistance with visas, "
            "permits, or anything related to your stay in Indonesia, we're always here for you.\n\n"
            "Warmest wishes,\nThe Bali Zero Team\n"
        ),
    },
    "id": {
        "subject": "Selamat Ulang Tahun dari Bali Zero!",
        "greeting": "Yang terhormat {name},",
        "message": (
            "\nKami mengucapkan selamat ulang tahun! Semoga tahun baru ini membawa kebahagiaan, "
            "kesuksesan, dan petualangan yang luar biasa.\n\n{personalized_note}\n\nJika Anda "
            "membutuhkan bantuan dengan visa, izin, atau hal lain yang berkaitan dengan tinggal di "
            "Indonesia, kami selalu siap membantu.\n\nSalam hangat,\nTim Bali Zero\n"
        ),
    },
    "uk": {
        "subject": "З Днем Народження від Bali Zero!",
        "greeting": "Дорогий/Дорога {name},",
        "message": (
            "\nВітаємо з Днем Народження! Нехай цей новий рік принесе вам радість, успіх та "
            "неймовірні пригоди.\n\n{personalized_note}\n\nЯкщо вам потрібна допомога з візами, "
            "дозволами чи будь-чим іншим, пов'язаним з перебуванням в Індонезії, ми завжди поруч.\n\n"
            "З найкращими побажаннями,\nКоманда Bali Zero\n"
        ),
    },
    "ru": {
        "subject": "С Днем Рождения от Bali Zero!",
        "greeting": "Дорогой/Дорогая {name},",
        "message": (
            "\nПоздравляем с Днем Рождения! Пусть этот новый год принесет вам радость, успех и "
            "удивительные приключения.\n\n{personalized_note}\n\nЕсли вам нужна помощь с визами, "
            "разрешениями или чем-либо еще, связанным с пребыванием в Индонезии, мы всегда рядом.\n\n"
            "С наилучшими пожеланиями,\nКоманда Bali Zero\n"
        ),
    },
}


class BirthdayNotifierService:
    """Service to send personalized birthday emails to clients."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool
        self.email_service = ZohoEmailService(db_pool)

    async def get_todays_birthdays(self) -> list[dict]:
        today = datetime.now(timezone.utc)
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, full_name, email, nationality, date_of_birth, birthplace, custom_fields
                FROM clients
                WHERE date_of_birth IS NOT NULL
                  AND email IS NOT NULL AND email != ''
                  AND status = 'active'
                  AND EXTRACT(MONTH FROM date_of_birth) = $1
                  AND EXTRACT(DAY FROM date_of_birth) = $2
                """,
                today.month, today.day,
            )
            return [dict(row) for row in rows]

    def get_language_for_nationality(self, nationality: str | None) -> str:
        if not nationality:
            return "en"
        return NATIONALITY_LANGUAGE_MAP.get(nationality, "en")

    def get_personalized_note(self, client: dict) -> str:
        custom_fields = client.get("custom_fields")
        if not custom_fields:
            return ""
        if isinstance(custom_fields, str):
            try:
                custom_fields = json.loads(custom_fields)
            except json.JSONDecodeError:
                return ""
        enrichment = custom_fields.get("birthplace_enrichment", {}).get("data", {})
        if not enrichment:
            return ""
        notes = []
        starters = enrichment.get("conversation_starters", [])
        if starters:
            notes.append(starters[0])
        famous = enrichment.get("famous_people", [])
        if famous and client.get("birthplace"):
            notes.append(
                f"As someone from {client['birthplace']}, home of {famous[0]}, you bring a special perspective!"
            )
        specialties = enrichment.get("local_specialties", [])
        if specialties:
            notes.append(f"We hope you get to enjoy some {specialties[0]} today!")
        return " ".join(notes) if notes else ""

    def build_email_content(self, client: dict, language: str) -> tuple[str, str]:
        template = BIRTHDAY_TEMPLATES.get(language, BIRTHDAY_TEMPLATES["en"])
        full_name = client.get("full_name", "")
        first_name = full_name.split()[0] if full_name else "Friend"
        personalized = self.get_personalized_note(client)
        if not personalized:
            personalized = "We value you as a client and appreciate your trust in us."
        subject = "[CLIENT] " + template["subject"]
        greeting = template["greeting"].format(name=first_name)
        message = template["message"].format(name=first_name, personalized_note=personalized)
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50;">{greeting}</h2>
                <p style="white-space: pre-line;">{message}</p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="font-size: 12px; color: #666;">
                    Bali Zero - Your Partner in Indonesia<br>
                    <a href="https://www.balizero.com" style="color: #3498db;">www.balizero.com</a>
                </p>
            </div>
        </body>
        </html>
        """
        return subject, html_content

    async def send_birthday_email(self, client: dict) -> bool:
        try:
            language = self.get_language_for_nationality(client.get("nationality"))
            subject, html_content = self.build_email_content(client, language)
            sent_via_brevo = False
            try:
                async with httpx.AsyncClient(timeout=30.0) as http_client:
                    response = await http_client.post(
                        _EMAIL_API_URL,
                        headers={"X-API-Key": _EMAIL_API_KEY},
                        json={"to": client["email"], "subject": subject, "body": html_content},
                    )
                    response.raise_for_status()
                sent_via_brevo = True
                logger.info(f"Birthday email sent to {client['email']} via Brevo ({language})")
            except Exception as brevo_err:
                logger.warning(f"Brevo failed for birthday {client['email']}, trying Zoho: {brevo_err}")
            if not sent_via_brevo:
                await self.email_service.send_email(
                    user_id=SYSTEM_SENDER_USER_ID,
                    to=[client["email"]],
                    subject=subject,
                    content=html_content,
                    is_html=True,
                )
                logger.info(f"Birthday email sent to {client['email']} via Zoho ({language})")
            return True
        except Exception as e:
            logger.error(f"Failed to send birthday email to {client.get('email')}: {e}")
            return False

    async def run_birthday_notifications(self) -> dict[str, Any]:
        stats: dict[str, Any] = {
            "date": datetime.now(timezone.utc).isoformat(),
            "birthdays_found": 0, "sent": 0, "failed": 0,
        }
        try:
            clients = await self.get_todays_birthdays()
            stats["birthdays_found"] = len(clients)
            if not clients:
                logger.info("No birthdays today")
                return stats
            logger.info(f"Found {len(clients)} birthdays today")
            for client in clients:
                success = await self.send_birthday_email(client)
                if success:
                    stats["sent"] += 1
                else:
                    stats["failed"] += 1
                await asyncio.sleep(2)
            logger.info(f"Birthday notifications complete: {stats}")
            return stats
        except Exception as e:
            logger.error(f"Birthday notification run failed: {e}", exc_info=True)
            stats["error"] = str(e)
            return stats


async def run_birthday_notifier_task(db_pool: asyncpg.Pool) -> dict[str, Any]:
    """Task function for autonomous scheduler."""
    service = BirthdayNotifierService(db_pool)
    return await service.run_birthday_notifications()


# ─────────────────────────────────────────────────────────────────────────────
# StalePracticeNotifier (from stale_practice_notifier.py)
# ─────────────────────────────────────────────────────────────────────────────

ADMIN_EMAIL = "zero@balizero.com"
STALE_DAYS = 7
ACTIVE_STATUSES = ("inquiry", "waiting_documents", "sending_invoice", "on_process")
CRM_PRACTICE_URL = "https://kita.balizero.com/process/{id}"

_TH = (
    "padding:8px 12px;text-align:left;font-size:12px;"
    "color:#93c5fd;font-weight:600;border-bottom:1px solid #334155;"
)
_TD = (
    "padding:7px 12px;font-size:13px;border-bottom:1px solid #1e293b;"
    "color:#cbd5e1;vertical-align:top;"
)


def _esc(value: Any) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt_datetime(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return str(value)


class StalePracticeNotifier:
    """Service to detect stale practices and notify the admin and team leaders."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool

    async def check_and_notify(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "stale_count": 0, "leaders_notified": 0,
            "admin_notified": False, "errors": [],
        }
        try:
            stale = await self._get_stale_practices()
        except Exception as exc:
            logger.error("Failed to query stale practices", exc_info=True)
            result["errors"].append(f"DB query failed: {exc}")
            return result

        result["stale_count"] = len(stale)
        if not stale:
            logger.info("No stale practices found — nothing to notify.")
            return result

        logger.info("Stale practices found", extra={"context": {"count": len(stale), "stale_days": STALE_DAYS}})

        try:
            await self._send_zero_summary(stale)
            result["admin_notified"] = True
        except Exception as exc:
            logger.error("Failed to send admin summary email", exc_info=True)
            result["errors"].append(f"Admin email failed: {exc}")

        by_leader: dict[str, list[dict[str, Any]]] = {}
        for practice in stale:
            leader_email: str | None = practice.get("assigned_to")
            if not leader_email:
                continue
            by_leader.setdefault(leader_email, []).append(practice)

        for leader_email, practices in by_leader.items():
            try:
                await self._send_team_leader_alert(leader_email, practices)
                result["leaders_notified"] += 1
            except Exception as exc:
                logger.error(
                    "Failed to send team-leader alert",
                    extra={"context": {"leader": leader_email}},
                    exc_info=True,
                )
                result["errors"].append(f"Leader email ({leader_email}) failed: {exc}")

        logger.info("Stale practice notification run complete", extra={"context": result})
        return result

    async def _get_stale_practices(self) -> list[dict[str, Any]]:
        query = """
            SELECT
                p.id,
                c.full_name                          AS client_name,
                COALESCE(pt.name, 'N/A')             AS practice_type_name,
                p.status,
                p.assigned_to,
                EXTRACT(DAY FROM (NOW() - p.updated_at))::int AS days_stale,
                p.updated_at
            FROM practices p
            JOIN clients c ON c.id = p.client_id
            LEFT JOIN practice_types pt ON pt.id = p.practice_type_id
            WHERE
                p.status = ANY($1::text[])
                AND p.updated_at < NOW() - INTERVAL '7 days'
                AND NOT EXISTS (
                    SELECT 1 FROM activity_log al
                    WHERE al.entity_type = 'practice'
                      AND al.entity_id   = p.id
                      AND al.performed_at > NOW() - INTERVAL '7 days'
                )
            ORDER BY p.updated_at ASC
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, list(ACTIVE_STATUSES))
            return [dict(row) for row in rows]

    async def _send_zero_summary(self, stale: list[dict[str, Any]]) -> None:
        today: str = datetime.now(tz=timezone.utc).date().isoformat()
        subject = f"[RITARDI] ⏰ {len(stale)} pratiche ferme da {STALE_DAYS}+ giorni — {today}"

        by_leader: dict[str, list[dict[str, Any]]] = {}
        for p in stale:
            leader: str = p.get("assigned_to") or "Non assegnata"
            by_leader.setdefault(leader, []).append(p)

        rows_html = ""
        for leader, practices in sorted(by_leader.items()):
            rows_html += (
                f'<tr><td colspan="6" style="background:#1e293b;color:#94a3b8;'
                f'padding:6px 10px;font-size:12px;font-weight:600;">'
                f"Team Leader: {leader}</td></tr>\n"
            )
            for p in practices:
                crm_url = CRM_PRACTICE_URL.format(id=p["id"])
                updated_str = _fmt_datetime(p.get("updated_at"))
                rows_html += (
                    f"<tr>"
                    f'<td style="{_TD}"><a href="{crm_url}" style="color:#60a5fa;">#{p["id"]}</a></td>'
                    f'<td style="{_TD}">{_esc(p["client_name"])}</td>'
                    f'<td style="{_TD}">{_esc(p["practice_type_name"])}</td>'
                    f'<td style="{_TD}">{_esc(p["status"])}</td>'
                    f'<td style="{_TD}">{updated_str}</td>'
                    f'<td style="{_TD};color:#f87171;font-weight:600;">{p["days_stale"]} giorni</td>'
                    f"</tr>\n"
                )

        body = f"""
        <html>
        <body style="font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;padding:24px;">
          <div style="max-width:820px;margin:0 auto;">
            <h2 style="color:#f1f5f9;margin-bottom:4px;">
              \u23f0 Pratiche ferme da {STALE_DAYS}+ giorni
            </h2>
            <p style="color:#94a3b8;margin-top:0;">
              Report generato il {today} &mdash; {len(stale)} pratiche totali
            </p>
            <table style="width:100%;border-collapse:collapse;margin-top:16px;">
              <thead>
                <tr style="background:#1e3a5f;">
                  <th style="{_TH}">ID</th><th style="{_TH}">Cliente</th>
                  <th style="{_TH}">Tipo pratica</th><th style="{_TH}">Status</th>
                  <th style="{_TH}">Ultimo aggiorn.</th><th style="{_TH}">Giorni ferma</th>
                </tr>
              </thead>
              <tbody>{rows_html}</tbody>
            </table>
            <p style="margin-top:24px;font-size:13px;color:#64748b;">
              Inviato automaticamente da Zantara CRM &mdash;
              <a href="https://kita.balizero.com" style="color:#60a5fa;">Apri CRM</a>
            </p>
          </div>
        </body>
        </html>
        """

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _EMAIL_API_URL,
                headers={"X-API-Key": _EMAIL_API_KEY},
                json={"to": ADMIN_EMAIL, "subject": subject, "body": body},
            )
            response.raise_for_status()

        logger.info("Admin summary sent", extra={"context": {"to": ADMIN_EMAIL, "stale_count": len(stale)}})

    async def _send_team_leader_alert(self, email: str, practices: list[dict[str, Any]]) -> None:
        subject = "[TEAM] ⏰ Pratiche in attesa — aggiornamento richiesto"

        rows_html = ""
        for p in practices:
            crm_url = CRM_PRACTICE_URL.format(id=p["id"])
            rows_html += (
                f"<tr>"
                f'<td style="{_TD}"><a href="{crm_url}" style="color:#60a5fa;">#{p["id"]}</a></td>'
                f'<td style="{_TD}">{_esc(p["client_name"])}</td>'
                f'<td style="{_TD}">{_esc(p["practice_type_name"])}</td>'
                f'<td style="{_TD}">{_esc(p["status"])}</td>'
                f'<td style="{_TD};color:#f87171;font-weight:600;">{p["days_stale"]} giorni</td>'
                f"</tr>\n"
            )

        body = f"""
        <html>
        <body style="font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;padding:24px;">
          <div style="max-width:700px;margin:0 auto;">
            <h2 style="color:#f1f5f9;margin-bottom:4px;">
              Ciao! \ud83d\udc4b Alcune pratiche hanno bisogno della tua attenzione.
            </h2>
            <p style="color:#cbd5e1;line-height:1.6;">
              Alcune tue pratiche non hanno aggiornamenti da <strong>{STALE_DAYS}+ giorni</strong>.
              Puoi controllare lo stato e aggiungere una nota nel CRM?
            </p>
            <table style="width:100%;border-collapse:collapse;margin-top:16px;">
              <thead>
                <tr style="background:#1e3a5f;">
                  <th style="{_TH}">ID</th><th style="{_TH}">Cliente</th>
                  <th style="{_TH}">Tipo pratica</th><th style="{_TH}">Status</th>
                  <th style="{_TH}">Giorni senza agg.</th>
                </tr>
              </thead>
              <tbody>{rows_html}</tbody>
            </table>
            <p style="margin-top:24px;font-size:13px;color:#64748b;">
              Grazie mille! \u2014 Zantara CRM
            </p>
          </div>
        </body>
        </html>
        """

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _EMAIL_API_URL,
                headers={"X-API-Key": _EMAIL_API_KEY},
                json={"to": email, "subject": subject, "body": body},
            )
            response.raise_for_status()

        logger.info("Team-leader alert sent", extra={"context": {"to": email, "practice_count": len(practices)}})


async def run_stale_practice_notifier_task(db_pool: asyncpg.Pool) -> dict[str, Any]:
    """Task function for autonomous scheduler."""
    service = StalePracticeNotifier(db_pool)
    return await service.check_and_notify()
