"""
Email Templates
===============
Multi-language email templates for all alert types.

Languages supported:
- English (en) - Default
- Italian (it)
- Indonesian (id)
"""

import logging
import re

from backend.app.modules.notifications.models import AlertType

logger = logging.getLogger(__name__)

# Indonesian blessing phrases for birthdays
INDONESIAN_BLESSINGS = [
    "Selamat ulang tahun! Semoga panjang umur, sehat selalu, dan sukses dalam segala hal.",
    "Dirgahayu! Semoga harapan dan cita-cita Anda tercapai.",
    "Met ultah! Tetap semangat dan jangan pernah menyerah.",
]


EMAIL_TEMPLATES: dict[str, dict[AlertType, dict[str, str]]] = {
    "en": {
        AlertType.PASSPORT_WARNING: {
            "subject": "Passport Renewal Reminder - Action Required",
            "body": """
<h2>Hello {full_name},</h2>

<p>This is a friendly reminder that your passport will expire in <strong>{months_remaining} months</strong> ({expiry_date}).</p>

<div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0;">
    <strong>⚠️ Important:</strong><br>
    In 7 months, you may no longer be permitted to take international flights.
    We strongly recommend contacting your embassy as soon as possible to begin the renewal process.
</div>

<p>If you need assistance with the renewal process, please don't hesitate to contact your account manager or reach out through our chat.</p>

<p>Best regards,<br><strong>The Bali Zero Team</strong></p>
""",
        },
        AlertType.PASSPORT_CRITICAL: {
            "subject": "URGENT: Immediate Passport Action Required",
            "body": """
<h2>Hello {full_name},</h2>

<div style="background: #f8d7da; border-left: 4px solid #dc3545; padding: 15px; margin: 20px 0;">
    <strong>🚨 URGENT:</strong><br>
    Your passport will expire in <strong>{months_remaining} months</strong> ({expiry_date}).
</div>

<p><strong>Action Required:</strong></p>
<ul>
    <li>Contact your embassy in Indonesia <strong>immediately</strong></li>
    <li>Begin emergency passport renewal procedures</li>
    <li>International travel may be restricted</li>
</ul>

<p>Please contact us urgently if you need assistance.</p>

<p>Emergency Contact:<br>
📧 support@balizero.com<br>
📱 WhatsApp: +62 821-4745-1775</p>

<p><strong>Bali Zero Team</strong></p>
""",
        },
        AlertType.PASSPORT_EXPIRED: {
            "subject": "CRITICAL: Your Passport Has Expired",
            "body": """
<h2>Hello {full_name},</h2>

<div style="background: #721c24; color: white; padding: 15px; margin: 20px 0; border-radius: 5px;">
    <strong>⛔ CRITICAL:</strong><br>
    Your passport expired on {expiry_date}.
</div>

<p><strong>Immediate Actions Required:</strong></p>
<ol>
    <li>Contact your embassy immediately for emergency renewal</li>
    <li>You cannot travel internationally with an expired passport</li>
    <li>Inform us of your situation so we can assist</li>
</ol>

<p><strong>Emergency Contacts:</strong><br>
📧 support@balizero.com<br>
📱 WhatsApp: +62 821-4745-1775</p>

<p><strong>Bali Zero Team</strong></p>
""",
        },
        AlertType.VISA_WARNING: {
            "subject": "Visa Renewal Reminder - Plan Ahead",
            "body": """
<h2>Hello {full_name},</h2>

<p>This is a friendly reminder that your <strong>{visa_type}</strong> visa will expire in <strong>{days_remaining} days</strong> ({expiry_date}).</p>

<div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0;">
    <strong>⚠️ Important:</strong><br>
    We recommend starting the renewal process now to avoid any disruptions to your stay in Indonesia.
</div>

<p>Contact us to discuss your renewal options and timeline.</p>

<p>Best regards,<br><strong>The Bali Zero Team</strong></p>
""",
        },
        AlertType.VISA_CRITICAL: {
            "subject": "URGENT: Visa Renewal Planning Required",
            "body": """
<h2>Hello {full_name},</h2>

<div style="background: #f8d7da; border-left: 4px solid #dc3545; padding: 15px; margin: 20px 0;">
    <strong>🚨 URGENT:</strong><br>
    Your {visa_type} visa will expire in <strong>{days_remaining} days</strong> ({expiry_date}).
</div>

<p><strong>Please take immediate action:</strong></p>
<ul>
    <li>Contact us to begin your visa renewal process, OR</li>
    <li>Communicate your departure date from Indonesia</li>
</ul>

<p>Failure to renew or depart before expiry may result in:</p>
<ul>
    <li>Overstay fines</li>
    <li>Immigration complications</li>
    <li>Deportation risk</li>
</ul>

<p>📧 Contact: support@balizero.com<br>
📱 WhatsApp: +62 821-4745-1775</p>

<p><strong>Bali Zero Team</strong></p>
""",
        },
        AlertType.VISA_EXPIRED: {
            "subject": "CRITICAL: Your Visa Has Expired",
            "body": """
<h2>Hello {full_name},</h2>

<div style="background: #721c24; color: white; padding: 15px; margin: 20px 0; border-radius: 5px;">
    <strong>⛔ CRITICAL:</strong><br>
    Your {visa_type} visa expired on {expiry_date}.
</div>

<p><strong>Immediate Actions Required:</strong></p>
<ol>
    <li>Contact us <strong>immediately</strong> to discuss your options</li>
    <li>Overstay penalties accumulate daily</li>
    <li>Do not attempt to leave Indonesia without resolving your visa status</li>
</ol>

<p><strong>Emergency Contacts:</strong><br>
📧 support@balizero.com<br>
📱 WhatsApp: +62 821-4745-1775</p>

<p><strong>Bali Zero Team</strong></p>
""",
        },
        AlertType.BIRTHDAY: {
            "subject": "🎉 Happy Birthday from Bali Zero!",
            "body": """
<h2>🎂 Happy Birthday, {full_name}! 🎂</h2>

<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; margin: 20px 0; border-radius: 10px; text-align: center;">
    <h3 style="margin: 0;">Wishing you a wonderful year ahead!</h3>
    <p style="margin: 10px 0 0 0; font-size: 18px;">May all your dreams come true ✨</p>
</div>

<p>On behalf of the entire Bali Zero team, we want to wish you a very happy birthday filled with joy, success, and unforgettable moments.</p>

<p style="font-style: italic; color: #666; border-left: 3px solid #667eea; padding-left: 15px; margin: 20px 0;">
    <strong>Indonesian blessing:</strong><br>
    {indonesian_blessing}
</p>

<p>Thank you for being part of our community. We look forward to continuing to support you on your journey in Indonesia.</p>

<p>With warm wishes,<br>
<strong>The Bali Zero Team</strong><br>
🌴 Bali, Indonesia</p>
""",
        },
    },
    "it": {
        AlertType.PASSPORT_WARNING: {
            "subject": "Promemoria Rinnovo Passaporto - Azione Richiesta",
            "body": """
<h2>Ciao {full_name},</h2>

<p>Questo è un promemoria amichevole che il tuo passaporto scadrà tra <strong>{months_remaining} mesi</strong> ({expiry_date}).</p>

<div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0;">
    <strong>⚠️ Importante:</strong><br>
    Tra 7 mesi potresti non essere più autorizzato a prendere voli internazionali.
    Ti consigliamo vivamente di contattare la tua ambasciata il prima possibile.
</div>

<p>Se hai bisogno di assistenza, contatta il tuo account manager.</p>

<p>Cordiali saluti,<br><strong>Il Team Bali Zero</strong></p>
""",
        },
        AlertType.PASSPORT_CRITICAL: {
            "subject": "URGENTE: Azione Immediata Richiesta sul Passaporto",
            "body": """
<h2>Ciao {full_name},</h2>

<div style="background: #f8d7da; border-left: 4px solid #dc3545; padding: 15px; margin: 20px 0;">
    <strong>🚨 URGENTE:</strong><br>
    Il tuo passaporto scadrà tra <strong>{months_remaining} mesi</strong> ({expiry_date}).
</div>

<p><strong>Azione Richiesta:</strong></p>
<ul>
    <li>Contatta immediatamente la tua ambasciata in Indonesia</li>
    <li>Inizia le procedure di rinnovo d'emergenza</li>
    <li>I viaggi internazionali potrebbero essere limitati</li>
</ul>

<p><strong>Team Bali Zero</strong></p>
""",
        },
        AlertType.PASSPORT_EXPIRED: {
            "subject": "CRITICO: Il Tuo Passaporto È Scaduto",
            "body": """
<h2>Ciao {full_name},</h2>

<div style="background: #721c24; color: white; padding: 15px; margin: 20px 0; border-radius: 5px;">
    <strong>⛔ CRITICO:</strong><br>
    Il tuo passaporto è scaduto il {expiry_date}.
</div>

<p><strong>Azioni Immediate Richieste:</strong></p>
<ol>
    <li>Contatta immediatamente la tua ambasciata per il rinnovo d'emergenza</li>
    <li>Non puoi viaggiare internazionalmente con un passaporto scaduto</li>
    <li>Informaci della tua situazione per assisterti</li>
</ol>

<p><strong>Contatti di Emergenza:</strong><br>
📧 support@balizero.com<br>
📱 WhatsApp: +62 821-4745-1775</p>

<p><strong>Team Bali Zero</strong></p>
""",
        },
        AlertType.VISA_WARNING: {
            "subject": "Promemoria Rinnovo Visto - Pianifica in Anticipo",
            "body": """
<h2>Ciao {full_name},</h2>

<p>Questo è un promemoria che il tuo visto <strong>{visa_type}</strong> scadrà tra <strong>{days_remaining} giorni</strong> ({expiry_date}).</p>

<div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0;">
    <strong>⚠️ Importante:</strong><br>
    Ti consigliamo di iniziare il processo di rinnovo ora per evitare interruzioni al tuo soggiorno in Indonesia.
</div>

<p>Contattaci per discutere le opzioni e la tempistica del rinnovo.</p>

<p>Cordiali saluti,<br><strong>Il Team Bali Zero</strong></p>
""",
        },
        AlertType.VISA_CRITICAL: {
            "subject": "URGENTE: Pianificazione Rinnovo Visto Richiesta",
            "body": """
<h2>Ciao {full_name},</h2>

<div style="background: #f8d7da; border-left: 4px solid #dc3545; padding: 15px; margin: 20px 0;">
    <strong>🚨 URGENTE:</strong><br>
    Il tuo visto {visa_type} scadrà tra <strong>{days_remaining} giorni</strong> ({expiry_date}).
</div>

<p><strong>Azione immediata richiesta:</strong></p>
<ul>
    <li>Contattaci per iniziare il rinnovo del visto, OPPURE</li>
    <li>Comunica la data di partenza dall'Indonesia</li>
</ul>

<p><strong>Team Bali Zero</strong></p>
""",
        },
        AlertType.VISA_EXPIRED: {
            "subject": "CRITICO: Il Tuo Visto È Scaduto",
            "body": """
<h2>Ciao {full_name},</h2>

<div style="background: #721c24; color: white; padding: 15px; margin: 20px 0; border-radius: 5px;">
    <strong>⛔ CRITICO:</strong><br>
    Il tuo visto {visa_type} è scaduto il {expiry_date}.
</div>

<p><strong>Azioni Immediate Richieste:</strong></p>
<ol>
    <li>Contattaci <strong>immediatamente</strong> per discutere le opzioni</li>
    <li>Le penalità per overstay si accumulano giornalmente</li>
    <li>Non tentare di lasciare l'Indonesia senza risolvere il tuo status</li>
</ol>

<p><strong>Contatti di Emergenza:</strong><br>
📧 support@balizero.com<br>
📱 WhatsApp: +62 821-4745-1775</p>

<p><strong>Team Bali Zero</strong></p>
""",
        },
        AlertType.BIRTHDAY: {
            "subject": "🎉 Tanti Auguri da Bali Zero!",
            "body": """
<h2>🎂 Tanti Auguri, {full_name}! 🎂</h2>

<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; margin: 20px 0; border-radius: 10px; text-align: center;">
    <h3 style="margin: 0;">Ti auguriamo un anno meraviglioso!</h3>
</div>

<p>Per conto di tutto il team Bali Zero, ti auguriamo un compleanno pieno di gioia e successo.</p>

<p style="font-style: italic; color: #666; border-left: 3px solid #667eea; padding-left: 15px; margin: 20px 0;">
    <strong>Auspicio indonesiano:</strong><br>
    {indonesian_blessing}
</p>

<p>Con auguri sinceri,<br>
<strong>Il Team Bali Zero</strong> 🌴</p>
""",
        },
    },
    "id": {
        AlertType.PASSPORT_WARNING: {
            "subject": "Pengingat Perpanjangan Paspor - Tindakan Diperlukan",
            "body": """
<h2>Halo {full_name},</h2>

<p>Ini adalah pengingat bahwa paspor Anda akan berakhir dalam <strong>{months_remaining} bulan</strong> ({expiry_date}).</p>

<div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0;">
    <strong>⚠️ Penting:</strong><br>
    Dalam 7 bulan, Anda mungkin tidak lagi diizinkan untuk penerbangan internasional.
    Kami sangat menyarankan menghubungi kedutaan Anda sesegera mungkin.
</div>

<p>Salam,<br><strong>Tim Bali Zero</strong></p>
""",
        },
        AlertType.PASSPORT_CRITICAL: {
            "subject": "PENTING: Tindakan Segera Diperlukan untuk Paspor",
            "body": """
<h2>Halo {full_name},</h2>

<div style="background: #f8d7da; border-left: 4px solid #dc3545; padding: 15px; margin: 20px 0;">
    <strong>🚨 PENTING:</strong><br>
    Paspor Anda akan berakhir dalam <strong>{months_remaining} bulan</strong> ({expiry_date}).
</div>

<p><strong>Tindakan Diperlukan:</strong></p>
<ul>
    <li>Segera hubungi kedutaan Anda di Indonesia</li>
    <li>Mulai prosedur perpanjangan darurat</li>
</ul>

<p><strong>Tim Bali Zero</strong></p>
""",
        },
        AlertType.PASSPORT_EXPIRED: {
            "subject": "KRITIS: Paspor Anda Telah Berakhir",
            "body": """
<h2>Halo {full_name},</h2>

<div style="background: #721c24; color: white; padding: 15px; margin: 20px 0; border-radius: 5px;">
    <strong>⛔ KRITIS:</strong><br>
    Paspor Anda berakhir pada {expiry_date}.
</div>

<p><strong>Tindakan Segera Diperlukan:</strong></p>
<ol>
    <li>Segera hubungi kedutaan Anda untuk perpanjangan darurat</li>
    <li>Anda tidak dapat bepergian internasional dengan paspor yang telah berakhir</li>
    <li>Informasikan situasi Anda kepada kami agar kami dapat membantu</li>
</ol>

<p><strong>Kontak Darurat:</strong><br>
📧 support@balizero.com<br>
📱 WhatsApp: +62 821-4745-1775</p>

<p><strong>Tim Bali Zero</strong></p>
""",
        },
        AlertType.VISA_WARNING: {
            "subject": "Pengingat Perpanjangan Visa - Rencanakan Sekarang",
            "body": """
<h2>Halo {full_name},</h2>

<p>Ini adalah pengingat bahwa visa <strong>{visa_type}</strong> Anda akan berakhir dalam <strong>{days_remaining} hari</strong> ({expiry_date}).</p>

<div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0;">
    <strong>⚠️ Penting:</strong><br>
    Kami menyarankan untuk memulai proses perpanjangan sekarang agar tidak terjadi gangguan pada masa tinggal Anda di Indonesia.
</div>

<p>Hubungi kami untuk mendiskusikan opsi dan jadwal perpanjangan.</p>

<p>Salam,<br><strong>Tim Bali Zero</strong></p>
""",
        },
        AlertType.VISA_CRITICAL: {
            "subject": "PENTING: Perencanaan Perpanjangan Visa Diperlukan",
            "body": """
<h2>Halo {full_name},</h2>

<div style="background: #f8d7da; border-left: 4px solid #dc3545; padding: 15px; margin: 20px 0;">
    <strong>🚨 PENTING:</strong><br>
    Visa {visa_type} Anda akan berakhir dalam <strong>{days_remaining} hari</strong> ({expiry_date}).
</div>

<p><strong>Tindakan segera diperlukan:</strong></p>
<ul>
    <li>Hubungi kami untuk memulai proses perpanjangan, ATAU</li>
    <li>Komunikasikan tanggal keberangkatan Anda dari Indonesia</li>
</ul>

<p><strong>Tim Bali Zero</strong></p>
""",
        },
        AlertType.VISA_EXPIRED: {
            "subject": "KRITIS: Visa Anda Telah Berakhir",
            "body": """
<h2>Halo {full_name},</h2>

<div style="background: #721c24; color: white; padding: 15px; margin: 20px 0; border-radius: 5px;">
    <strong>⛔ KRITIS:</strong><br>
    Visa {visa_type} Anda berakhir pada {expiry_date}.
</div>

<p><strong>Tindakan Segera Diperlukan:</strong></p>
<ol>
    <li>Hubungi kami <strong>segera</strong> untuk mendiskusikan opsi</li>
    <li>Denda overstay bertambah setiap hari</li>
    <li>Jangan mencoba meninggalkan Indonesia tanpa menyelesaikan status visa Anda</li>
</ol>

<p><strong>Kontak Darurat:</strong><br>
📧 support@balizero.com<br>
📱 WhatsApp: +62 821-4745-1775</p>

<p><strong>Tim Bali Zero</strong></p>
""",
        },
        AlertType.BIRTHDAY: {
            "subject": "🎉 Selamat Ulang Tahun dari Bali Zero!",
            "body": """
<h2>🎂 Selamat Ulang Tahun, {full_name}! 🎂</h2>

<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; margin: 20px 0; border-radius: 10px; text-align: center;">
    <h3 style="margin: 0;">Semoga tahun ini penuh kebahagiaan!</h3>
</div>

<p>Atas nama seluruh tim Bali Zero, kami mengucapkan selamat ulang tahun yang penuh sukacita dan kesuksesan.</p>

<p style="font-style: italic; color: #666; border-left: 3px solid #667eea; padding-left: 15px; margin: 20px 0;">
    <strong>Doa untuk Anda:</strong><br>
    {indonesian_blessing}
</p>

<p>Dengan doa terbaik,<br>
<strong>Tim Bali Zero</strong> 🌴</p>
""",
        },
    },
}


def get_template(language: str, alert_type: AlertType) -> dict[str, str]:
    """
    Get email template for a specific language and alert type.
    Falls back to English if language or alert type not found.
    """
    lang_templates = EMAIL_TEMPLATES.get(language, EMAIL_TEMPLATES["en"])
    template = lang_templates.get(alert_type)
    if template:
        return template
    # Fallback to English for this alert type
    en_template = EMAIL_TEMPLATES["en"].get(alert_type)
    if en_template:
        logger.warning(
            "Template fallback to English: alert_type=%s language=%s",
            alert_type,
            language,
        )
        return en_template
    # Last resort: generic fallback
    logger.warning("No template found for alert_type=%s language=%s", alert_type, language)
    return {
        "subject": f"Notification: {alert_type.value}",
        "body": f"<p>Alert: {alert_type.value}</p>",
    }


def format_template(template: str, **kwargs: str) -> str:
    """Format email template with provided variables, ignoring missing keys."""
    try:
        return template.format(**kwargs)
    except KeyError:
        # Replace missing keys with empty string in a single pass
        result = template
        for match in re.finditer(r"\{(\w+)\}", template):
            key = match.group(1)
            if key not in kwargs:
                result = result.replace(f"{{{key}}}", "")
        # Now format only with the keys we have — use format_map to avoid
        # KeyError on any remaining curly braces (e.g. CSS)
        try:
            return result.format_map(kwargs)
        except (KeyError, ValueError):
            return result
