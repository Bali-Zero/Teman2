"""
Welcome Communication Templates
================================
All message strings for welcome WhatsApp and email communications.
Supports 5 languages: EN, IT, RU, UK, ID.

Substitution variables:
    {first_name}   — first word of client.full_name
    {advisor_name} — first name of assigned advisor, or fallback per language
    {service_name} — human-readable practice type name (practice kickoff only)
    {practice_id}  — practice ID number
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────
# ADVISOR FALLBACK NAMES (when client.assigned_to is NULL)
# ─────────────────────────────────────────────────────────

ADVISOR_FALLBACK: dict[str, str] = {
    "en": "our team",
    "it": "il nostro team",
    "ru": "наша команда",
    "uk": "наша команда",
    "id": "tim kami",
}


# ─────────────────────────────────────────────────────────
# WHATSAPP — create_client welcome (Trigger 1a)
# Marketing category templates — require Meta pre-approval.
# Template names: balizero_welcome_en/it/ru/uk/id
# ─────────────────────────────────────────────────────────

WELCOME_WHATSAPP: dict[str, str] = {
    "en": (
        "Hi {first_name} ✅\n\n"
        "Welcome to Bali Zero. {advisor_name} is your dedicated advisor "
        "and will reach out within 2 hours.\n\n"
        "What's the best time for a quick call this week?"
    ),
    "it": (
        "Ciao {first_name} 👋\n\n"
        "Benvenuto in Bali Zero. {advisor_name} è il tuo punto di riferimento "
        "— ti contatterà entro 2 ore.\n\n"
        "Quando sei disponibile per una breve chiamata?"
    ),
    "ru": (
        "Здравствуйте, {first_name}.\n\n"
        "Добро пожаловать в Bali Zero. {advisor_name} — ваш персональный консультант "
        "и свяжется с вами в течение 2 часов.\n\n"
        "Когда вам удобно поговорить на этой неделе?"
    ),
    "uk": (
        "Вітаємо, {first_name} 👋\n\n"
        "Ласкаво просимо до Bali Zero. {advisor_name} — ваш особистий консультант "
        "і зв'яжеться з вами протягом 2 годин.\n\n"
        "Коли вам зручно поговорити цього тижня?"
    ),
    "id": (
        "Halo {first_name} 👋\n\n"
        "Selamat datang di Bali Zero. {advisor_name} adalah konsultan pribadi Anda "
        "dan akan menghubungi Anda dalam 2 jam.\n\n"
        "Kapan waktu yang tepat untuk panggilan singkat minggu ini?"
    ),
}


# ─────────────────────────────────────────────────────────
# EMAIL SUBJECTS — create_client welcome (Trigger 1b)
# ─────────────────────────────────────────────────────────

WELCOME_EMAIL_SUBJECT: dict[str, str] = {
    "en": "You're in good hands — Bali Zero",
    "it": "Sei in buone mani — Bali Zero",
    "ru": "Вы в надёжных руках — Bali Zero",
    "uk": "Ви в надійних руках — Bali Zero",
    "id": "Anda dalam tangan yang baik — Bali Zero",
}


# ─────────────────────────────────────────────────────────
# EMAIL BODY BLOCKS — create_client welcome (Trigger 1b)
# Per-language content blocks assembled in welcome_email_service.py
# ─────────────────────────────────────────────────────────

WELCOME_EMAIL_OPENING: dict[str, str] = {
    "en": (
        "Welcome to Bali Zero, {first_name}.\n\n"
        "We're glad you're here. Whether you're setting up a business, sorting out your visa, "
        "or making Bali your long-term home — you've come to the right place.\n\n"
        "We handle the bureaucracy. You focus on Bali."
    ),
    "it": (
        "Benvenuto in Bali Zero, {first_name}.\n\n"
        "Siamo felici che tu sia qui. Che tu stia aprendo un'azienda, sistemando il visto "
        "o facendo di Bali la tua casa a lungo termine — sei nel posto giusto.\n\n"
        "Noi gestiamo la burocrazia. Tu goditi Bali."
    ),
    "ru": (
        "Добро пожаловать в Bali Zero, {first_name}.\n\n"
        "Рады, что вы здесь. Открываете бизнес, оформляете визу "
        "или планируете остаться на Бали надолго — вы обратились по адресу.\n\n"
        "Бюрократия — наша забота. Бали — ваша."
    ),
    "uk": (
        "Ласкаво просимо до Bali Zero, {first_name}.\n\n"
        "Раді, що ви тут. Відкриваєте бізнес, оформлюєте візу "
        "або плануєте залишитися на Балі надовго — ви звернулися за адресою.\n\n"
        "Бюрократія — наша турбота. Балі — ваше."
    ),
    "id": (
        "Selamat datang di Bali Zero, {first_name}.\n\n"
        "Senang Anda bergabung. Apakah Anda mendirikan bisnis, mengurus visa, "
        "atau menjadikan Bali rumah jangka panjang — Anda datang ke tempat yang tepat.\n\n"
        "Kami urus birokrasinya. Anda nikmati Bali-nya."
    ),
}

WELCOME_EMAIL_WHO_WE_ARE: dict[str, str] = {
    "en": (
        "Bali Zero is a legal and business services firm based in Kerobokan, Bali. "
        "We specialize in immigration, company formation, tax compliance, and property — "
        "everything a foreigner needs to live and work legally in Indonesia.\n\n"
        "Our team combines experienced advisors with an AI system that keeps track of "
        "deadlines, documents, and regulations — so nothing falls through the cracks.\n\n"
        "Want to know more before your first call? Browse our services, pricing, and guides at "
        "<a href=\"https://www.balizero.com\" style=\"color:#d4845a;\">www.balizero.com</a>."
    ),
    "it": (
        "Bali Zero è uno studio di consulenza legale e aziendale con sede a Kerobokan, Bali. "
        "Ci specializziamo in immigrazione, costituzione di società, compliance fiscale e proprietà immobiliare — "
        "tutto ciò di cui un straniero ha bisogno per vivere e lavorare legalmente in Indonesia.\n\n"
        "Il nostro team unisce consulenti esperti a un sistema AI che tiene traccia di "
        "scadenze, documenti e normative — così nulla va perso.\n\n"
        "Vuoi saperne di più prima della prima chiamata? Esplora servizi, prezzi e guide su "
        "<a href=\"https://www.balizero.com\" style=\"color:#d4845a;\">www.balizero.com</a>."
    ),
    "ru": (
        "Bali Zero — юридическая и бизнес-консалтинговая компания, базирующаяся в Керобокан, Бали. "
        "Мы специализируемся на иммиграции, регистрации компаний, налоговом соответствии и недвижимости — "
        "всём, что нужно иностранцу для легальной жизни и работы в Индонезии.\n\n"
        "Наша команда объединяет опытных консультантов с AI-системой, которая отслеживает "
        "сроки, документы и нормативные акты — чтобы ничего не упустить.\n\n"
        "Хотите узнать больше перед первым звонком? Ознакомьтесь с услугами, ценами и гайдами на "
        "<a href=\"https://www.balizero.com\" style=\"color:#d4845a;\">www.balizero.com</a>."
    ),
    "uk": (
        "Bali Zero — юридична та бізнес-консалтингова компанія, що базується в Керобокан, Балі. "
        "Ми спеціалізуємося на імміграції, реєстрації компаній, податковому комплаєнсі та нерухомості — "
        "всьому, що потрібно іноземцю для легального життя та роботи в Індонезії.\n\n"
        "Наша команда поєднує досвідчених консультантів з AI-системою, яка відстежує "
        "дедлайни, документи та нормативи — щоб нічого не загубилось.\n\n"
        "Хочете дізнатися більше перед першим дзвінком? Перегляньте послуги, ціни та гайди на "
        "<a href=\"https://www.balizero.com\" style=\"color:#d4845a;\">www.balizero.com</a>."
    ),
    "id": (
        "Bali Zero adalah firma layanan hukum dan bisnis yang berbasis di Kerobokan, Bali. "
        "Kami berspesialisasi dalam imigrasi, pendirian perusahaan, kepatuhan pajak, dan properti — "
        "semua yang dibutuhkan warga asing untuk tinggal dan bekerja secara legal di Indonesia.\n\n"
        "Tim kami menggabungkan konsultan berpengalaman dengan sistem AI yang melacak "
        "tenggat waktu, dokumen, dan peraturan — agar tidak ada yang terlewat.\n\n"
        "Ingin tahu lebih banyak sebelum panggilan pertama? Jelajahi layanan, harga, dan panduan di "
        "<a href=\"https://www.balizero.com\" style=\"color:#d4845a;\">www.balizero.com</a>."
    ),
}

WELCOME_EMAIL_TEAM_ASSIGNED: dict[str, str] = {
    "en": (
        "Your advisor is <strong>{advisor_name}</strong>. "
        "They'll reach out within 2 hours via WhatsApp to introduce themselves and get your process started. "
        "In the meantime, feel free to reply to this email with any questions."
    ),
    "it": (
        "Il tuo consulente è <strong>{advisor_name}</strong>. "
        "Ti contatterà entro 2 ore via WhatsApp per presentarsi e avviare il tuo percorso. "
        "Nel frattempo, rispondi pure a questa email per qualsiasi domanda."
    ),
    "ru": (
        "Ваш консультант — <strong>{advisor_name}</strong>. "
        "Он свяжется с вами в течение 2 часов через WhatsApp, чтобы представиться и начать работу. "
        "В любое время вы можете написать нам в ответ на это письмо."
    ),
    "uk": (
        "Ваш консультант — <strong>{advisor_name}</strong>. "
        "Він зв'яжеться з вами протягом 2 годин через WhatsApp, щоб представитися та розпочати роботу. "
        "Будь-коли відповідайте на цей лист із запитаннями."
    ),
    "id": (
        "Konsultan Anda adalah <strong>{advisor_name}</strong>. "
        "Mereka akan menghubungi Anda dalam 2 jam via WhatsApp untuk memperkenalkan diri dan memulai prosesnya. "
        "Sementara itu, balas email ini jika ada pertanyaan."
    ),
}

WELCOME_EMAIL_TEAM_UNASSIGNED: dict[str, str] = {
    "en": (
        "Your advisor will be assigned shortly — you'll hear from them via WhatsApp within 2 hours. "
        "In the meantime, feel free to reply to this email with any questions."
    ),
    "it": (
        "Il tuo consulente verrà assegnato a breve — ti contatterà via WhatsApp entro 2 ore. "
        "Nel frattempo, rispondi pure a questa email per qualsiasi domanda."
    ),
    "ru": (
        "Ваш консультант будет назначен в ближайшее время — он свяжется с вами через WhatsApp в течение 2 часов. "
        "В любое время вы можете написать нам в ответ на это письмо."
    ),
    "uk": (
        "Ваш консультант буде призначений найближчим часом — він зв'яжеться з вами через WhatsApp протягом 2 годин. "
        "Будь-коли відповідайте на цей лист із запитаннями."
    ),
    "id": (
        "Konsultan Anda akan segera ditugaskan — mereka akan menghubungi Anda via WhatsApp dalam 2 jam. "
        "Sementara itu, balas email ini jika ada pertanyaan."
    ),
}

WELCOME_EMAIL_CTA: dict[str, str] = {
    "en": "Have a question right now? Reply to this email or WhatsApp us at +62 813 3805 1876",
    "it": "Hai una domanda adesso? Rispondi a questa email o scrivici su WhatsApp al +62 813 3805 1876",
    "ru": "Есть вопрос прямо сейчас? Ответьте на это письмо или напишите нам в WhatsApp: +62 813 3805 1876",
    "uk": "Є питання зараз? Відповідайте на цей лист або пишіть у WhatsApp: +62 813 3805 1876",
    "id": "Ada pertanyaan sekarang? Balas email ini atau hubungi kami di WhatsApp +62 813 3805 1876",
}


# ─────────────────────────────────────────────────────────
# PRACTICE SERVICE NAMES — practice kickoff WhatsApp
# ─────────────────────────────────────────────────────────

PRACTICE_SERVICE_NAMES: dict[str, dict[str, str]] = {
    "KITAS": {
        "en": "KITAS permit",
        "it": "permesso KITAS",
        "ru": "разрешение KITAS",
        "uk": "дозвіл KITAS",
        "id": "izin KITAS",
    },
    "KITAP": {
        "en": "KITAP permanent permit",
        "it": "permesso permanente KITAP",
        "ru": "постоянное разрешение KITAP",
        "uk": "постійний дозвіл KITAP",
        "id": "izin tinggal tetap KITAP",
    },
    "VISA": {
        "en": "visa",
        "it": "visto",
        "ru": "виза",
        "uk": "віза",
        "id": "visa",
    },
    "COMPANY": {
        "en": "company service",
        "it": "servizio aziendale",
        "ru": "корпоративная услуга",
        "uk": "корпоративна послуга",
        "id": "layanan perusahaan",
    },
    "PT_PMA": {
        "en": "PT PMA company",
        "it": "società PT PMA",
        "ru": "компания PT PMA",
        "uk": "компанія PT PMA",
        "id": "perusahaan PT PMA",
    },
    "TAX": {
        "en": "tax registration",
        "it": "registrazione fiscale",
        "ru": "налоговая регистрация",
        "uk": "податкова реєстрація",
        "id": "pendaftaran pajak",
    },
    "PROPERTY": {
        "en": "property service",
        "it": "servizio immobiliare",
        "ru": "услуги по недвижимости",
        "uk": "послуги з нерухомості",
        "id": "layanan properti",
    },
    "URGENT": {
        "en": "urgent processing",
        "it": "pratica urgente",
        "ru": "срочная обработка",
        "uk": "термінова обробка",
        "id": "proses urgent",
    },
    "OTHER": {
        "en": "service",
        "it": "servizio",
        "ru": "услуга",
        "uk": "послуга",
        "id": "layanan",
    },
}

# Map code prefixes to service name keys for the new granular codes
_PREFIX_TO_SERVICE: list[tuple[str, str]] = [
    ("KITAS_", "KITAS"),
    ("KITAP_", "KITAP"),
    ("MERP_", "KITAP"),
    ("VISA_", "VISA"),
    ("EXT_", "VISA"),
    ("COMPANY_", "COMPANY"),
    ("TAX_", "TAX"),
    ("URGENT_", "URGENT"),
    ("OTHER_", "OTHER"),
]


def get_service_name(practice_type_code: str, lang: str) -> str:
    """Return localized service name for practice type. Falls back to EN."""
    code_upper = practice_type_code.upper()

    # Direct match first (legacy codes like KITAS, VISA, TAX, PT_PMA)
    if code_upper in PRACTICE_SERVICE_NAMES:
        type_map = PRACTICE_SERVICE_NAMES[code_upper]
        return type_map.get(lang, type_map["en"])

    # Prefix match for new granular codes (kitas_working_offshore → KITAS)
    for prefix, key in _PREFIX_TO_SERVICE:
        if code_upper.startswith(prefix):
            type_map = PRACTICE_SERVICE_NAMES[key]
            return type_map.get(lang, type_map["en"])

    # Final fallback
    type_map = PRACTICE_SERVICE_NAMES["OTHER"]
    return type_map.get(lang, type_map["en"])


# ─────────────────────────────────────────────────────────
# WHATSAPP — practice kickoff (Trigger 2)
# Single template for all languages and types.
# Template name: balizero_practice_kickoff
# ─────────────────────────────────────────────────────────

PRACTICE_KICKOFF_WHATSAPP = (
    "Hi {first_name} 👋\n\n"
    "Your {service_name} case is now open (ID: {practice_id}).\n"
    "{advisor_name} is your case handler.\n\n"
    "Step 1: we'll send you the document checklist today.\n"
    "Any questions? Reply here."
)


# ─────────────────────────────────────────────────────────
# EMAIL SUBJECTS — practice kickoff (Trigger 2)
# ─────────────────────────────────────────────────────────

PRACTICE_EMAIL_SUBJECT: dict[str, str] = {
    "en": "Your {service_name} — next steps | Bali Zero",
    "it": "Il tuo {service_name} — prossimi passi | Bali Zero",
    "ru": "Ваш {service_name} — следующие шаги | Bali Zero",
    "uk": "Ваш {service_name} — наступні кроки | Bali Zero",
    "id": "{service_name} Anda — langkah selanjutnya | Bali Zero",
}


# ─────────────────────────────────────────────────────────
# DOCUMENT CHECKLISTS — practice kickoff email
# Static per practice type — embedded in service.
# ─────────────────────────────────────────────────────────

PRACTICE_DOCUMENT_CHECKLISTS: dict[str, list[str]] = {
    "KITAS": [
        "Passport (all pages, valid minimum 18 months)",
        "Recent passport photos (4x6 cm, white background)",
        "Previous Indonesian permits or visas (if any)",
        "Sponsor letter or employment contract",
        "Copy of PT PMA deed (if company-sponsored)",
    ],
    "PT_PMA": [
        "Passport (all pages)",
        "NPWP — Indonesian tax number (if already registered)",
        "Business plan outline (sector, activities, investment amount)",
        "Local partner agreement (if applicable)",
        "Proof of investment funds (bank statement or letter)",
    ],
    "TAX": [
        "Passport (main page)",
        "KITAS or KITAP copy",
        "Proof of Indonesian income or contract",
        "Most recent tax filing from home country (if any)",
    ],
    "PROPERTY": [
        "Passport (main page)",
        "KITAS copy (if residing in Indonesia)",
        "Proof of funds for the transaction",
        "Property details: address, certificate type (SHM/HGB/SHGB), asking price",
        "Land certificate copy (from seller/notaris)",
    ],
}


PRACTICE_TIMELINES: dict[str, str] = {
    "KITAS": "4–8 weeks from complete documents submission",
    "PT_PMA": "8–14 weeks from signed notarial deed",
    "TAX": "3–7 business days for NPWP issuance",
    "PROPERTY": "6–12 weeks depending on transaction type (HGB vs Hak Pakai)",
}
