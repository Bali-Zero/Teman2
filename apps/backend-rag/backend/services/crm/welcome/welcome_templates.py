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
        "You've just made a courageous decision — choosing to build part of your life "
        "in one of the most complex and rewarding jurisdictions in Southeast Asia. "
        "That choice deserves a team that takes it as seriously as you do."
    ),
    "it": (
        "Hai appena preso una decisione coraggiosa — scegliere di costruire una parte della tua vita "
        "in una delle giurisdizioni più complesse e gratificanti del Sud-Est Asiatico. "
        "Quella scelta merita un team che la prenda sul serio quanto te."
    ),
    "ru": (
        "Вы только что приняли смелое решение — выбрать одну из самых сложных "
        "и перспективных юрисдикций Юго-Восточной Азии для построения своей жизни. "
        "Это решение заслуживает команды, которая относится к нему так же серьёзно, как вы."
    ),
    "uk": (
        "Ви щойно прийняли сміливе рішення — обрати одну з найскладніших "
        "і найперспективніших юрисдикцій Південно-Східної Азії. "
        "Це рішення заслуговує на команду, яка поставиться до нього так само серйозно, як ви."
    ),
    "id": (
        "Anda baru saja membuat keputusan berani — memilih untuk membangun sebagian hidup Anda "
        "di salah satu yurisdiksi paling kompleks dan menguntungkan di Asia Tenggara. "
        "Keputusan itu layak mendapatkan tim yang menganggapnya seserius Anda."
    ),
}

WELCOME_EMAIL_WHO_WE_ARE: dict[str, str] = {
    "en": (
        "Bali Zero was founded as a traditional consulting firm — lawyers, immigration specialists, "
        "and tax advisors based in Canggu. Over the past decade, we evolved into something different: "
        "a hybrid human+AI system where specialized agents handle the deterministic work "
        "(price lookups, document checklists, deadline tracking, legal database searches) "
        "so our human experts can focus entirely on judgment, relationships, and complex problem-solving. "
        "The vast majority of our processes run on rules, not memory — which means you get "
        "consistent, reliable answers whether you reach us on a Monday morning or a Friday afternoon."
    ),
    "it": (
        "Bali Zero è nata come uno studio di consulenza tradizionale — avvocati, specialisti dell'immigrazione "
        "e consulenti fiscali con base a Canggu. Negli ultimi dieci anni ci siamo evoluti in qualcosa di diverso: "
        "un sistema ibrido umano+AI in cui agenti specializzati gestiscono il lavoro deterministico "
        "(ricerche sui prezzi, checklist documenti, scadenze, database legali) "
        "in modo che i nostri esperti umani possano concentrarsi completamente su giudizio, relazioni "
        "e problem-solving complesso. "
        "La grande maggioranza dei nostri processi funziona su regole, non sulla memoria — "
        "il che significa che ricevi risposte coerenti e affidabili in ogni momento."
    ),
    "ru": (
        "Bali Zero была основана как традиционная консалтинговая компания — юристы, специалисты по иммиграции "
        "и налоговые консультанты в Чангу. За последнее десятилетие мы превратились в нечто иное: "
        "гибридную систему «человек + ИИ», где специализированные агенты выполняют детерминированную работу "
        "(запросы цен, чек-листы документов, отслеживание дедлайнов, юридические базы данных), "
        "чтобы наши эксперты могли полностью сосредоточиться на суждениях, отношениях "
        "и решении сложных задач. "
        "Подавляющее большинство наших процессов работает по правилам, а не по памяти — "
        "это означает, что вы получаете стабильные и надёжные ответы в любое время."
    ),
    "uk": (
        "Bali Zero була заснована як традиційна консалтингова компанія — юристи, фахівці з імміграції "
        "та податкові консультанти у Чангу. За останнє десятиліття ми перетворились на щось інше: "
        "гібридну систему «людина + ШІ», де спеціалізовані агенти виконують детерміновану роботу "
        "(запити цін, чек-листи документів, відстеження дедлайнів, юридичні бази даних), "
        "щоб наші фахівці могли зосередитись на судженнях, стосунках і вирішенні складних завдань. "
        "Переважна більшість наших процесів працює за правилами, а не за пам'яттю — "
        "це означає, що ви отримуєте стабільні й надійні відповіді в будь-який час."
    ),
    "id": (
        "Bali Zero didirikan sebagai firma konsultan tradisional — pengacara, spesialis imigrasi, "
        "dan konsultan pajak yang berbasis di Canggu. Selama satu dekade terakhir, kami berkembang menjadi sesuatu "
        "yang berbeda: sistem hybrid manusia+AI di mana agen-agen khusus menangani pekerjaan deterministik "
        "(pencarian harga, daftar periksa dokumen, pelacakan tenggat waktu, database hukum) "
        "sehingga para ahli manusia kami dapat sepenuhnya fokus pada penilaian, hubungan, dan pemecahan masalah. "
        "Sebagian besar proses kami berjalan berdasarkan aturan, bukan ingatan — "
        "yang berarti Anda mendapatkan jawaban yang konsisten dan dapat diandalkan kapan pun."
    ),
}

WELCOME_EMAIL_TEAM_ASSIGNED: dict[str, str] = {
    "en": "Your dedicated advisor is {advisor_name}. They will reach out to you within 2 hours to introduce themselves and understand your goals.",
    "it": "Il tuo consulente dedicato è {advisor_name}. Ti contatterà entro 2 ore per presentarsi e capire i tuoi obiettivi.",
    "ru": "Ваш персональный консультант — {advisor_name}. Он свяжется с вами в течение 2 часов, чтобы представиться и понять ваши цели.",
    "uk": "Ваш особистий консультант — {advisor_name}. Він зв'яжеться з вами протягом 2 годин, щоб представитися і зрозуміти ваші цілі.",
    "id": "Konsultan pribadi Anda adalah {advisor_name}. Mereka akan menghubungi Anda dalam 2 jam untuk memperkenalkan diri dan memahami tujuan Anda.",
}

WELCOME_EMAIL_TEAM_UNASSIGNED: dict[str, str] = {
    "en": "Your advisor will be assigned by today. You will hear from them within 2 hours of assignment.",
    "it": "Il tuo consulente verrà assegnato entro oggi. Sentirai da loro entro 2 ore dall'assegnazione.",
    "ru": "Ваш консультант будет назначен сегодня. Вы получите от него сообщение в течение 2 часов после назначения.",
    "uk": "Ваш консультант буде призначений сьогодні. Ви отримаєте від нього повідомлення протягом 2 годин після призначення.",
    "id": "Konsultan Anda akan ditugaskan hari ini. Anda akan mendapat kabar dari mereka dalam 2 jam setelah penugasan.",
}

WELCOME_EMAIL_CTA: dict[str, str] = {
    "en": "Reply to this email directly — no forms, no waiting room.",
    "it": "Rispondi direttamente a questa email — nessun modulo, nessuna attesa.",
    "ru": "Ответьте прямо на это письмо — без форм, без ожидания.",
    "uk": "Відповідайте прямо на цей лист — без форм, без очікування.",
    "id": "Balas email ini langsung — tanpa formulir, tanpa ruang tunggu.",
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
