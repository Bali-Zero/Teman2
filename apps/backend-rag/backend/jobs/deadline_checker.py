"""
Deadline checker background job.
Runs daily to create reminder timeline events for upcoming deadlines.

Features:
- Tax deadline reminders (30/14/7/1 days before)
- Visa expiry reminders (90/60/30 days before)
- Telegram alerts for urgent deadlines (≤7 days)
- Email notifications for T-7 day reminders
- No duplicate reminders (EXISTS check)
"""
import asyncio
from datetime import date, timedelta
from typing import Optional

import structlog
from prometheus_client import Counter, Gauge

logger = structlog.get_logger(__name__)

# Metrics
deadlines_checked = Counter("deadline_checker_total", "Total deadlines checked")
reminders_created = Counter(
    "deadline_reminders_created", "Reminder events created", ["type", "urgency"]
)
telegram_alerts_sent = Counter(
    "deadline_telegram_alerts_sent", "Telegram alerts sent", ["type", "urgency"]
)
email_notifications_sent = Counter(
    "deadline_email_notifications_sent", "Email notifications sent", ["type"]
)
job_last_run = Gauge("deadline_checker_last_run_timestamp", "Last successful run")

# Reminder schedule
TAX_REMINDER_DAYS = [30, 14, 7, 1]
VISA_REMINDER_DAYS = [90, 60, 30]

# Alert thresholds
TELEGRAM_ALERT_THRESHOLD_DAYS = 7  # Send Telegram for ≤7 days
EMAIL_NOTIFICATION_DAY = 7  # Send email at exactly 7 days


async def send_telegram_alert(
    client_id: int,
    client_name: str,
    client_email: str,
    alert_type: str,
    title: str,
    description: str,
    urgency: str,
    db_pool,
) -> bool:
    """
    Send Telegram alert to client for urgent deadline.

    Args:
        client_id: Client database ID
        client_name: Client full name
        client_email: Client email
        alert_type: "tax" or "visa"
        title: Alert title
        description: Alert description
        urgency: "critical", "warning", or "info"
        db_pool: Database connection pool

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        from backend.services.integrations.telegram_bot_service import TelegramBotService

        # Get Telegram chat_id for client
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT mu.telegram_chat_id
                FROM messaging_users mu
                JOIN user_profiles up ON up.id = mu.user_id
                WHERE up.linked_client_id = $1 AND mu.channel = 'telegram' AND mu.active = true
                LIMIT 1
            """,
                client_id,
            )

            if not row or not row["telegram_chat_id"]:
                logger.warning(
                    "No Telegram chat_id for client",
                    client_id=client_id,
                    client_email=client_email,
                )
                return False

            chat_id = row["telegram_chat_id"]

        # Format urgency emoji
        urgency_emoji = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}.get(urgency, "📌")

        # Build message
        message = f"""
{urgency_emoji} **{title}**

{description}

👤 Client: {client_name}
📧 Email: {client_email}

🔔 This is an automated reminder from Bali Zero.
Visit your portal to view details: https://portal.balizero.com
"""

        # Send via Telegram
        telegram_service = TelegramBotService()
        await telegram_service.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")

        telegram_alerts_sent.labels(type=alert_type, urgency=urgency).inc()
        logger.info(
            "Telegram alert sent",
            client_id=client_id,
            alert_type=alert_type,
            urgency=urgency,
            chat_id=chat_id,
        )
        return True

    except Exception as e:
        logger.error(
            "Failed to send Telegram alert", client_id=client_id, error=str(e), exc_info=True
        )
        return False


async def send_email_notification(
    client_id: int,
    client_name: str,
    client_email: str,
    notification_type: str,
    subject: str,
    body: str,
    db_pool,
) -> bool:
    """
    Send email notification to client for T-7 day reminder.

    Args:
        client_id: Client database ID
        client_name: Client full name
        client_email: Client email address
        notification_type: "tax" or "visa"
        subject: Email subject
        body: Email body (HTML)
        db_pool: Database connection pool

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        from backend.services.integrations.zoho_email_service import ZohoEmailService

        # Send via Zoho Email
        zoho_service = ZohoEmailService()

        # Format email body with template
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background-color: #0066cc; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; }}
        .footer {{ background-color: #f5f5f5; padding: 15px; text-align: center; font-size: 12px; color: #666; }}
        .button {{ background-color: #0066cc; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Bali Zero - Deadline Reminder</h1>
    </div>
    <div class="content">
        <p>Dear {client_name},</p>
        {body}
        <p><a href="https://portal.balizero.com" class="button">View Portal Dashboard</a></p>
        <p>If you have any questions, please contact our team.</p>
        <p>Best regards,<br>The Bali Zero Team</p>
    </div>
    <div class="footer">
        <p>This is an automated notification from Bali Zero.</p>
        <p>© 2026 Bali Zero. All rights reserved.</p>
    </div>
</body>
</html>
"""

        await zoho_service.send_email(
            to_email=client_email, subject=subject, body=html_body, from_name="Bali Zero Reminders"
        )

        email_notifications_sent.labels(type=notification_type).inc()
        logger.info(
            "Email notification sent",
            client_id=client_id,
            client_email=client_email,
            notification_type=notification_type,
        )
        return True

    except Exception as e:
        logger.error(
            "Failed to send email notification",
            client_id=client_id,
            client_email=client_email,
            error=str(e),
            exc_info=True,
        )
        return False


async def check_tax_deadlines(db_pool) -> int:
    """
    Check all upcoming tax deadlines and create reminders.

    Reminder schedule:
    - 30 days before: info reminder
    - 14 days before: warning reminder
    - 7 days before: urgent reminder
    - 1 day before: critical reminder

    Returns:
        Number of reminders created
    """
    reminders_count = 0
    today = date.today()

    async with db_pool.acquire() as conn:
        for days in TAX_REMINDER_DAYS:
            target_date = today + timedelta(days=days)
            urgency = "critical" if days <= 7 else ("warning" if days <= 14 else "info")
            color = "error" if days <= 7 else ("warning" if days <= 14 else "info")

            # Find obligations due on target_date without existing reminder
            obligations = await conn.fetch(
                """
                SELECT t.* FROM tax_obligations t
                WHERE t.due_date = $1
                AND t.status IN ('upcoming', 'pending')
                AND NOT EXISTS (
                    SELECT 1 FROM timeline_events e
                    WHERE e.client_id = t.client_id
                    AND e.event_type = 'reminder'
                    AND e.title LIKE '%' || t.name || '%'
                    AND DATE(e.event_date) = $2
                )
            """,
                target_date,
                today,
            )

            for ob in obligations:
                # Create timeline event
                await conn.execute(
                    """
                    INSERT INTO timeline_events
                    (client_id, event_type, title, description, event_date, color, client_visible)
                    VALUES ($1, 'reminder', $2, $3, NOW(), $4, true)
                """,
                    ob["client_id"],
                    f"Tax Reminder: {ob['name']}",
                    f"Due in {days} days ({target_date})",
                    color,
                )
                reminders_count += 1
                reminders_created.labels(type="tax", urgency=urgency).inc()
                logger.info(
                    "Created tax reminder", client_id=ob["client_id"], tax=ob["name"], days=days
                )

                # Send Telegram alert for urgent deadlines (≤7 days)
                if days <= TELEGRAM_ALERT_THRESHOLD_DAYS:
                    # Get client details
                    client_row = await conn.fetchrow(
                        "SELECT full_name, email FROM clients WHERE id = $1", ob["client_id"]
                    )

                    if client_row:
                        await send_telegram_alert(
                            client_id=ob["client_id"],
                            client_name=client_row["full_name"] or "Valued Client",
                            client_email=client_row["email"],
                            alert_type="tax",
                            title=f"Tax Deadline: {ob['name']}",
                            description=f"⏰ Due in {days} days ({target_date})\n💰 Amount: Rp {ob['amount_due']:,.0f}"
                            if ob["amount_due"]
                            else f"⏰ Due in {days} days ({target_date})",
                            urgency=urgency,
                            db_pool=db_pool,
                        )

                # Send email notification at exactly 7 days
                if days == EMAIL_NOTIFICATION_DAY:
                    client_row = await conn.fetchrow(
                        "SELECT full_name, email FROM clients WHERE id = $1", ob["client_id"]
                    )

                    if client_row:
                        email_body = f"""
<p>This is a reminder that your <strong>{ob['name']}</strong> tax obligation is due in <strong>7 days</strong>.</p>

<p><strong>Details:</strong></p>
<ul>
    <li>Due Date: {target_date}</li>
    <li>Tax Type: {ob['tax_type']}</li>
    <li>Period: {ob['period_start']} to {ob['period_end']}</li>
    {"<li>Amount Due: Rp " + f"{ob['amount_due']:,.0f}</li>" if ob['amount_due'] else ""}
</ul>

<p>Please ensure this obligation is filed on time to avoid penalties.</p>
"""

                        await send_email_notification(
                            client_id=ob["client_id"],
                            client_name=client_row["full_name"] or "Valued Client",
                            client_email=client_row["email"],
                            notification_type="tax",
                            subject=f"Tax Reminder: {ob['name']} - Due in 7 Days",
                            body=email_body,
                            db_pool=db_pool,
                        )

    return reminders_count


async def check_visa_expiry(db_pool) -> int:
    """
    Check all visa records for upcoming expiry.

    Actions:
    - 90 days before: send renewal notice
    - 60 days before: create renewal practice (if not exists)
    - 30 days before: update status to 'expiring_soon'

    Returns:
        Number of actions taken
    """
    actions_count = 0
    today = date.today()

    async with db_pool.acquire() as conn:
        # Update status to expiring_soon (30 days)
        result = await conn.execute(
            """
            UPDATE visa_records
            SET status = 'expiring_soon', updated_at = NOW()
            WHERE status = 'active'
            AND expiry_date <= $1
            AND expiry_date > $2
        """,
            today + timedelta(days=30),
            today,
        )

        updated = int(result.split()[-1]) if result else 0
        if updated > 0:
            logger.info("Updated visas to expiring_soon", count=updated)
            actions_count += updated

        # Update status to expired
        result = await conn.execute(
            """
            UPDATE visa_records
            SET status = 'expired', updated_at = NOW()
            WHERE status IN ('active', 'expiring_soon')
            AND expiry_date < $1
        """,
            today,
        )

        expired = int(result.split()[-1]) if result else 0
        if expired > 0:
            logger.info("Updated visas to expired", count=expired)
            actions_count += expired

        # Create reminders for expiring visas
        for days in VISA_REMINDER_DAYS:
            target_date = today + timedelta(days=days)
            urgency = "critical" if days <= 30 else ("warning" if days <= 60 else "info")

            visas = await conn.fetch(
                """
                SELECT v.* FROM visa_records v
                WHERE v.expiry_date = $1
                AND v.status IN ('active', 'expiring_soon')
                AND NOT EXISTS (
                    SELECT 1 FROM timeline_events e
                    WHERE e.client_id = v.client_id
                    AND e.event_type = 'reminder'
                    AND e.title LIKE '%Visa%'
                    AND DATE(e.event_date) = $2
                )
            """,
                target_date,
                today,
            )

            for visa in visas:
                # Create timeline event
                await conn.execute(
                    """
                    INSERT INTO timeline_events
                    (client_id, event_type, title, description, event_date, color, client_visible)
                    VALUES ($1, 'reminder', $2, $3, NOW(), $4, true)
                """,
                    visa["client_id"],
                    f"Visa Expiry Reminder: {visa['visa_type']}",
                    f"Expires in {days} days ({target_date})",
                    "warning" if days > 30 else "error",
                )
                actions_count += 1
                reminders_created.labels(type="visa", urgency=urgency).inc()
                logger.info(
                    "Created visa reminder",
                    client_id=visa["client_id"],
                    visa_type=visa["visa_type"],
                    days=days,
                )

                # Send Telegram alert for urgent visa expiry (≤30 days)
                if days <= 30:
                    client_row = await conn.fetchrow(
                        "SELECT full_name, email FROM clients WHERE id = $1", visa["client_id"]
                    )

                    if client_row:
                        await send_telegram_alert(
                            client_id=visa["client_id"],
                            client_name=client_row["full_name"] or "Valued Client",
                            client_email=client_row["email"],
                            alert_type="visa",
                            title=f"Visa Expiry: {visa['visa_type']}",
                            description=f"⏰ Expires in {days} days ({target_date})\n📄 Visa: {visa.get('visa_number', 'N/A')}",
                            urgency="critical" if days <= 7 else "warning",
                            db_pool=db_pool,
                        )

                # Send email notification at 90 days (renewal notice)
                if days == 90:
                    client_row = await conn.fetchrow(
                        "SELECT full_name, email FROM clients WHERE id = $1", visa["client_id"]
                    )

                    if client_row:
                        email_body = f"""
<p>This is an early notification that your <strong>{visa['visa_type']}</strong> visa will expire in <strong>90 days</strong>.</p>

<p><strong>Visa Details:</strong></p>
<ul>
    <li>Visa Type: {visa['visa_type']}</li>
    <li>Expiry Date: {target_date}</li>
    <li>Visa Number: {visa.get('visa_number', 'N/A')}</li>
    {"<li>Sponsor: " + visa.get('sponsor_name', 'N/A') + "</li>" if visa.get('sponsor_name') else ""}
</ul>

<p><strong>Next Steps:</strong></p>
<p>We recommend starting the renewal process soon to ensure continuous stay in Indonesia. Our team will contact you shortly to discuss renewal options.</p>
"""

                        await send_email_notification(
                            client_id=visa["client_id"],
                            client_name=client_row["full_name"] or "Valued Client",
                            client_email=client_row["email"],
                            notification_type="visa",
                            subject=f"Visa Renewal Notice: {visa['visa_type']} - 90 Days to Expiry",
                            body=email_body,
                            db_pool=db_pool,
                        )

    return actions_count


async def run_deadline_checker():
    """
    Main entry point for deadline checker job.
    Should be scheduled via cron or APScheduler.
    """
    logger.info("Starting deadline checker job")

    try:
        from backend.app.core.database import get_db_pool

        db_pool = await get_db_pool()

        tax_reminders = await check_tax_deadlines(db_pool)
        visa_actions = await check_visa_expiry(db_pool)

        deadlines_checked.inc()
        job_last_run.set_to_current_time()

        logger.info(
            "Deadline checker completed", tax_reminders=tax_reminders, visa_actions=visa_actions
        )

        return {"tax_reminders": tax_reminders, "visa_actions": visa_actions}

    except Exception as e:
        logger.error("Deadline checker failed", error=str(e), exc_info=True)
        raise


# CLI entry point
if __name__ == "__main__":
    asyncio.run(run_deadline_checker())
