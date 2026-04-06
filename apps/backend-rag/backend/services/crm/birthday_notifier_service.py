"""
Birthday Notifier Service

Sends personalized birthday emails to clients in their preferred language.
Uses birthplace enrichment data for personalized conversation starters.

Languages supported: IT, EN, ID, UK, RU
Runs daily as a scheduled task.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import asyncpg
import httpx

from backend.services.integrations.zoho_email_service import ZohoEmailService

logger = logging.getLogger(__name__)

# Internal email API — uses Brevo, from=zantara@balizero.com
_EMAIL_API_URL = os.getenv(
    "INTERNAL_EMAIL_API_URL", "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
_EMAIL_API_KEY = os.getenv("NUZANTARA_API_KEY", "")

# System user ID for sending emails via Zoho
# Using zero@balizero.com UUID (same as invoice service)
SYSTEM_SENDER_USER_ID = "7dfe56b2-ff63-4d40-b78b-90c018127a02"

# Nationality to language mapping
NATIONALITY_LANGUAGE_MAP = {
    # Italian
    "Italian": "it",
    "Italy": "it",
    "IT": "it",
    # English (default)
    "American": "en",
    "USA": "en",
    "United States": "en",
    "British": "en",
    "UK": "en",
    "United Kingdom": "en",
    "Australian": "en",
    "Australia": "en",
    "Canadian": "en",
    "Canada": "en",
    "Irish": "en",
    "Ireland": "en",
    "New Zealand": "en",
    "Kiwi": "en",
    # Indonesian
    "Indonesian": "id",
    "Indonesia": "id",
    "ID": "id",
    # Ukrainian
    "Ukrainian": "uk",
    "Ukraine": "uk",
    "UA": "uk",
    # Russian
    "Russian": "ru",
    "Russia": "ru",
    "RU": "ru",
    # German (use English)
    "German": "en",
    "Germany": "en",
    "DE": "en",
    # French (use English)
    "French": "en",
    "France": "en",
    "FR": "en",
    # Dutch (use English)
    "Dutch": "en",
    "Netherlands": "en",
    "NL": "en",
}

# Birthday email templates by language
BIRTHDAY_TEMPLATES = {
    "it": {
        "subject": "Buon Compleanno da Bali Zero!",
        "greeting": "Caro/a {name},",
        "message": """
Ti auguriamo un fantastico compleanno! Che questo nuovo anno ti porti tanta gioia, successo e bellissime avventure.

{personalized_note}

Se hai bisogno di assistenza con visti, permessi o qualsiasi altra cosa legata alla tua permanenza in Indonesia, siamo sempre qui per te.

Con i migliori auguri,
Il Team Bali Zero
""",
    },
    "en": {
        "subject": "Happy Birthday from Bali Zero!",
        "greeting": "Dear {name},",
        "message": """
Wishing you a wonderful birthday! May this new year bring you joy, success, and amazing adventures.

{personalized_note}

If you need assistance with visas, permits, or anything related to your stay in Indonesia, we're always here for you.

Warmest wishes,
The Bali Zero Team
""",
    },
    "id": {
        "subject": "Selamat Ulang Tahun dari Bali Zero!",
        "greeting": "Yang terhormat {name},",
        "message": """
Kami mengucapkan selamat ulang tahun! Semoga tahun baru ini membawa kebahagiaan, kesuksesan, dan petualangan yang luar biasa.

{personalized_note}

Jika Anda membutuhkan bantuan dengan visa, izin, atau hal lain yang berkaitan dengan tinggal di Indonesia, kami selalu siap membantu.

Salam hangat,
Tim Bali Zero
""",
    },
    "uk": {
        "subject": "З Днем Народження від Bali Zero!",
        "greeting": "Дорогий/Дорога {name},",
        "message": """
Вітаємо з Днем Народження! Нехай цей новий рік принесе вам радість, успіх та неймовірні пригоди.

{personalized_note}

Якщо вам потрібна допомога з візами, дозволами чи будь-чим іншим, пов'язаним з перебуванням в Індонезії, ми завжди поруч.

З найкращими побажаннями,
Команда Bali Zero
""",
    },
    "ru": {
        "subject": "С Днем Рождения от Bali Zero!",
        "greeting": "Дорогой/Дорогая {name},",
        "message": """
Поздравляем с Днем Рождения! Пусть этот новый год принесет вам радость, успех и удивительные приключения.

{personalized_note}

Если вам нужна помощь с визами, разрешениями или чем-либо еще, связанным с пребыванием в Индонезии, мы всегда рядом.

С наилучшими пожеланиями,
Команда Bali Zero
""",
    },
}


class BirthdayNotifierService:
    """Service to send personalized birthday emails to clients."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool
        self.email_service = ZohoEmailService(db_pool)

    async def get_todays_birthdays(self) -> list[dict]:
        """
        Get clients with birthday today.

        Returns:
            List of clients celebrating birthday today
        """
        today = datetime.now(timezone.utc)
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    id, full_name, email, nationality, date_of_birth,
                    birthplace, custom_fields
                FROM clients
                WHERE
                    date_of_birth IS NOT NULL
                    AND email IS NOT NULL
                    AND email != ''
                    AND status = 'active'
                    AND EXTRACT(MONTH FROM date_of_birth) = $1
                    AND EXTRACT(DAY FROM date_of_birth) = $2
                """,
                today.month,
                today.day,
            )
            return [dict(row) for row in rows]

    def get_language_for_nationality(self, nationality: str | None) -> str:
        """
        Get language code based on nationality.

        Args:
            nationality: Client's nationality

        Returns:
            Language code (it, en, id, uk, ru)
        """
        if not nationality:
            return "en"  # Default to English
        return NATIONALITY_LANGUAGE_MAP.get(nationality, "en")

    def get_personalized_note(self, client: dict) -> str:
        """
        Generate personalized note from birthplace enrichment data.

        Args:
            client: Client dictionary with custom_fields

        Returns:
            Personalized note string or empty string
        """
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

        # Build personalized note from enrichment data
        notes = []

        # Use conversation starters if available
        starters = enrichment.get("conversation_starters", [])
        if starters:
            notes.append(starters[0])

        # Mention famous people from birthplace
        famous = enrichment.get("famous_people", [])
        if famous and client.get("birthplace"):
            notes.append(
                f"As someone from {client['birthplace']}, home of {famous[0]}, you bring a special perspective!",
            )

        # Mention local specialties
        specialties = enrichment.get("local_specialties", [])
        if specialties:
            notes.append(f"We hope you get to enjoy some {specialties[0]} today!")

        return " ".join(notes) if notes else ""

    def build_email_content(self, client: dict, language: str) -> tuple[str, str]:
        """
        Build email subject and HTML content.

        Args:
            client: Client dictionary
            language: Language code

        Returns:
            Tuple of (subject, html_content)
        """
        template = BIRTHDAY_TEMPLATES.get(language, BIRTHDAY_TEMPLATES["en"])

        # Get first name for greeting
        full_name = client.get("full_name", "")
        first_name = full_name.split()[0] if full_name else "Friend"

        # Get personalized note
        personalized = self.get_personalized_note(client)
        if not personalized:
            personalized = "We value you as a client and appreciate your trust in us."

        subject = "[CLIENT] " + template["subject"]
        greeting = template["greeting"].format(name=first_name)
        message = template["message"].format(
            name=first_name,
            personalized_note=personalized,
        )

        # Build HTML email
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
        """
        Send birthday email to a single client.

        Args:
            client: Client dictionary

        Returns:
            True if email sent successfully
        """
        try:
            language = self.get_language_for_nationality(client.get("nationality"))
            subject, html_content = self.build_email_content(client, language)

            # Primary: Brevo
            sent_via_brevo = False
            try:
                async with httpx.AsyncClient(timeout=30.0) as http_client:
                    response = await http_client.post(
                        _EMAIL_API_URL,
                        headers={"X-API-Key": _EMAIL_API_KEY},
                        json={
                            "to": client["email"],
                            "subject": subject,
                            "body": html_content,
                        },
                    )
                    response.raise_for_status()
                sent_via_brevo = True
                logger.info(f"Birthday email sent to {client['email']} via Brevo ({language})")
            except Exception as brevo_err:
                logger.warning(f"Brevo failed for birthday {client['email']}, trying Zoho: {brevo_err}")

            # Fallback: Zoho
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
        """
        Run birthday notifications for today.

        Returns:
            Statistics dictionary
        """
        stats = {
            "date": datetime.now(timezone.utc).isoformat(),
            "birthdays_found": 0,
            "sent": 0,
            "failed": 0,
        }

        try:
            # Get today's birthdays
            clients = await self.get_todays_birthdays()
            stats["birthdays_found"] = len(clients)

            if not clients:
                logger.info("No birthdays today")
                return stats

            logger.info(f"Found {len(clients)} birthdays today")

            # Send emails
            for client in clients:
                success = await self.send_birthday_email(client)
                if success:
                    stats["sent"] += 1
                else:
                    stats["failed"] += 1

                # Small delay between emails
                await asyncio.sleep(2)

            logger.info(f"Birthday notifications complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Birthday notification run failed: {e}")
            stats["error"] = str(e)
            return stats


async def run_birthday_notifier_task(db_pool: asyncpg.Pool) -> dict[str, Any]:
    """
    Task function for autonomous scheduler.

    Args:
        db_pool: Database connection pool

    Returns:
        Task result statistics
    """
    service = BirthdayNotifierService(db_pool)
    return await service.run_birthday_notifications()
