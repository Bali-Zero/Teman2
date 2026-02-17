"""
Email Templates
===============
Multi-language email templates for all alert types.

Languages supported:
- English (en) - Default
- Italian (it)
- Indonesian (id)
- Russian (ru)
- French (fr)
- German (de)
- Spanish (es)
- Chinese (zh)
- Japanese (ja)
"""

from typing import Dict
from .models import AlertType


# Indonesian blessing phrases for birthdays
INDONESIAN_BLESSINGS = [
    "Selamat ulang tahun! Semoga panjang umur, sehat selalu, dan sukses dalam segala hal.",
    "Dirgahayu! Semoga harapan dan cita-cita Anda tercapai.",
    "Met ultah! Tetap semangat dan jangan pernah menyerah.",
]


EMAIL_TEMPLATES: Dict[str, Dict[AlertType, Dict[str, str]]] = {
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
<p style="font-style: italic; color: #666;">
    <strong>Auspicio indonesiano:</strong><br>
    {indonesian_blessing}
</p>
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
<p style="font-style: italic; color: #666;">
    <strong>Auspicio indonesiano:</strong><br>
    {indonesian_blessing}
</p>
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
<p style="font-style: italic; color: #666;">
    <strong>Auspicio indonesiano:</strong><br>
    {indonesian_blessing}
</p>
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


def get_template(language: str, alert_type: AlertType) -> Dict[str, str]:
    """
    Get email template for a specific language and alert type.
    Falls back to English if language not found.
    """
    lang_templates = EMAIL_TEMPLATES.get(language, EMAIL_TEMPLATES["en"])
    return lang_templates.get(alert_type, EMAIL_TEMPLATES["en"][alert_type])


def format_template(template: str, **kwargs) -> str:
    """Format email template with provided variables."""
    return template.format(**kwargs)
