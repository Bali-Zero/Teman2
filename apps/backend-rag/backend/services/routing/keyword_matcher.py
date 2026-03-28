"""
Keyword Matcher Service
Responsibility: Match keywords to domains for query routing
"""

import logging

logger = logging.getLogger(__name__)

# Domain-specific keywords for multi-collection routing
VISA_KEYWORDS = [
    "visa",
    "immigration",
    "imigrasi",
    "passport",
    "paspor",
    "sponsor",
    "stay permit",
    "tourist visa",
    "social visa",
    "work permit",
    "visit visa",
    "long stay",
    "permit",
    "residence",
    "immigration office",
    "dirjen imigrasi",
    # Italian keywords
    "visto",
    "permesso di soggiorno",
    "straniero",
    "immigrazione",
    # Kemnaker/TKA circulars keywords (SE 3/836/2026)
    "alih status",
    "kesamaan sponsor",
    "one sponsor",
    "offshore scheme",
    "tka",
    "tenaga kerja asing",
    "rptka",
    "itk",
    "izin tinggal keimigrasian",
    "siapkerja",
    "wlkp",
    "kemnaker",
    "surat edaran",
]

KBLI_KEYWORDS = [
    "kbli",
    "business classification",
    "klasifikasi baku",
    "oss",
    "nib",
    "risk-based",
    "berbasis risiko",
    "business license",
    "izin usaha",
    "standard industrial",
    "kode usaha",
    "sektor usaha",
    "business sector",
    "foreign ownership",
    "kepemilikan asing",
    "negative list",
    "dnpi",
    "business activity",
    "kegiatan usaha",
    "kode klasifikasi",
    # Italian keywords
    "codice kbli",
    "classificazione",
    "codice attività",
    "attività commerciale",
    # Common business type keywords (trigger KBLI lookup)
    "kode kbli",
    "restaurant",
    "ristorante",
    "cafe",
    "hotel",
    "retail",
    "trading",
    "construction",
    "consulting",
    "it services",
    "manufacturing",
]

TAX_KEYWORDS = [
    "tax",
    "pajak",
    "tax reporting",
    "withholding tax",
    "vat",
    "income tax",
    "corporate tax",
    "fiscal",
    "tax compliance",
    "tax calculation",
    "tax registration",
    "tax filing",
    "tax office",
    "direktorat jenderal pajak",
]

TAX_GENIUS_KEYWORDS = [
    "tax calculation",
    "calculate tax",
    "tax rate",
    "how to calculate",
    "tax example",
    "example",
    "tax procedure",
    "step by step",
    "menghitung pajak",
    "perhitungan pajak",
    "cara menghitung",
    "tax service",
    "bali zero service",
    "pricelist",
    "tarif pajak",
]

LEGAL_KEYWORDS = [
    "company",
    "foreign investment",
    "limited liability",
    "company formation",
    "incorporation",
    "deed",
    "notary",
    "notaris",
    "shareholder",
    "business entity",
    "legal entity",
    "law",
    "hukum",
    "regulation",
    "peraturan",
    "legal compliance",
    "contract",
    "perjanjian",
    # Italian keywords
    "legge",
    "normativa",
    "norma",
    "regolamento",
    "contratto",
    "atto",
    "notaio",
    # Code patterns
    "uu-",
    "undang-undang",
    "pp-",
    "peraturan pemerintah",
    "keputusan menteri",
    "keppres",
    "perpres",
    "permen",
    "pasal",
    "ayat",
    # Italian additions
    "società",
    "costituzione",
    "investimento straniero",
    "responsabilità limitata",
]

PROPERTY_KEYWORDS = [
    "property",
    "properti",
    "villa",
    "land",
    "tanah",
    "house",
    "rumah",
    "apartment",
    "apartemen",
    "real estate",
    "listing",
    "for sale",
    "dijual",
    "lease",
    "sewa",
    "rent",
    "rental",
    "leasehold",
    "freehold",
    "investment property",
    "development",
    "land bank",
    "zoning",
    "setback",
    "due diligence",
    "title deed",
    "sertipikat",
    "ownership structure",
]

TEAM_KEYWORDS = [
    "team",
    "tim",
    "staff",
    "employee",
    "karyawan",
    "personil",
    "team member",
    "colleague",
    "consultant",
    "specialist",
    "setup specialist",
    "tax specialist",
    "consulting",
    "accounting",
    "founder",
    "fondatore",
    "ceo",
    "director",
    "manager",
    "lead",
    "contact",
    "contattare",
    "contatta",
    "whatsapp",
    "email",
    "dipartimento",
    "division",
    "department",
    "professionista",
    "expert",
    "consulente",
]

TEAM_ENUMERATION_KEYWORDS = [
    "lista",
    "elenco",
    "tutti",
    "complete",
    "completa",
    "intero",
    "mostrami",
    "mostra",
    "mostrare",
    "elenca",
    "elenchiamo",
    "chi sono",
    "chi lavora",
    "quante persone",
    "quanti membri",
    "chi fa parte",
    "chi c'è",
    "in totale",
    "insieme",
    "tutti i membri",
    "l'intero team",
    "il team completo",
]

UPDATE_KEYWORDS = [
    "update",
    "updates",
    "pembaruan",
    "recent",
    "terbaru",
    "latest",
    "new",
    "news",
    "berita",
    "announcement",
    "pengumuman",
    "change",
    "perubahan",
    "amendment",
    "revisi",
    "revision",
    "effective date",
    "berlaku",
    "regulation update",
    "policy change",
    "what's new",
    "latest news",
]

# Kemnaker/Immigration Circulars - specific keywords for direct routing
CIRCULAR_KEYWORDS = [
    "alih status",
    "kesamaan sponsor",
    "one sponsor",
    "offshore scheme",
    "surat edaran kemnaker",
    "se kemnaker",
    "se imigrasi",
    "circular",
    "circolare",  # Italian
    "rptka berbeda",
    "sponsor berbeda",
    "pindah sponsor",
    "ganti sponsor",
    "bpjs matching",
    "wlkp verification",
    "siapkerja",
]

BOOKS_KEYWORDS = [
    "plato",
    "aristotle",
    "socrates",
    "philosophy",
    "filsafat",
    "republic",
    "ethics",
    "metaphysics",
    "guénon",
    "traditionalism",
    "zohar",
    "kabbalah",
    "mahabharata",
    "ramayana",
    "bhagavad gita",
    "rumi",
    "sufi",
    "dante",
    "divine comedy",
    "geertz",
    "religion of java",
    "kartini",
    "anderson",
    "imagined communities",
    "javanese culture",
    "indonesian culture",
    "sicp",
    "design patterns",
    "code complete",
    "programming",
    "software engineering",
    "algorithms",
    "data structures",
    "recursion",
    "functional programming",
    "lambda calculus",
    "oop",
    "machine learning",
    "deep learning",
    "neural networks",
    "ml",
    "ai theory",
    "probabilistic",
    "murphy",
    "goodfellow",
    "shakespeare",
    "homer",
    "iliad",
    "odyssey",
    "literature",
]

# Business setup & capital requirements keywords (for training_conversations_hybrid)
BUSINESS_KEYWORDS = [
    "pt pma",
    "pt lokal",
    "business setup",
    "company setup",
    "modal disetor",
    "paid-up capital",
    "capitale versato",
    "capitale minimo",
    "minimum capital",
    "authorized capital",
    "modal dasar",
    "business entity",
    "restaurant setup",
    "villa rental",
    "business guide",
    "setup guide",
    "investment requirement",
    "capital requirement",
    "notarial cost",
    "incorporation cost",
    "lkpm",
    "investment report",
    "business comparison",
    "pt comparison",
    "local vs foreign",
    "investor kitas",
    "business structure",
    # Indonesian license/permit acronyms
    "slhs",
    "npbbkc",
    "siup",
    "siujpt",
    "tdp",
    "skdp",
    "situ",
    "izin lokasi",
    "izin lingkungan",
    "izin mendirikan bangunan",
    "imb",
    "pbg",
    "sertifikat laik fungsi",
    "slf",
    "halal",
    "bpom",
    "pirt",
    "haccp",
    # Italian keywords
    "aprire",
    "avviare",
    "costituire",
    "licenza",
    "licenze",
    "permesso",
    "autorizzazione",
    "societ\u00e0",
    "impresa",
    "attivit\u00e0",
    "straniero",
    "investitore",
    # English additions
    "open a business",
    "start a business",
    "foreigner",
    "foreign investor",
    "license",
    "licence",
    "permits",
]


NEWS_KEYWORDS = [
    "news",
    "notizie",
    "berita",
    "latest",
    "update",
    "aggiornamento",
    "regulation change",
    "new regulation",
    "new law",
    "nuova legge",
    "what's new",
    "cosa c'è di nuovo",
    "recent",
    "recente",
    "announcement",
    "annuncio",
    "pengumuman",
    "article",
    "articolo",
    "insight",
    "briefing",
]


class KeywordMatcherService:
    """
    Service for matching keywords to domains.

    Responsibility: Calculate domain scores based on keyword matching.
    """

    def __init__(self) -> None:
        """Initialize keyword matcher with domain keyword lists."""
        self.domain_keywords = {
            "visa": VISA_KEYWORDS,
            "kbli": KBLI_KEYWORDS,
            "tax": TAX_KEYWORDS,
            "legal": LEGAL_KEYWORDS,
            "property": PROPERTY_KEYWORDS,
            "team": TEAM_KEYWORDS + TEAM_ENUMERATION_KEYWORDS,
            "books": BOOKS_KEYWORDS,
            "circular": CIRCULAR_KEYWORDS,  # Kemnaker/Imigrasi circulars
            "business": BUSINESS_KEYWORDS,  # Business setup & capital (training_conversations_hybrid)
            "news": NEWS_KEYWORDS,  # Intel articles, news, updates (balizero_news)
        }
        self.modifier_keywords = {
            "updates": UPDATE_KEYWORDS,
            "tax_genius": TAX_GENIUS_KEYWORDS,
        }

    def calculate_domain_scores(self, query: str) -> dict[str, int]:
        """
        Calculate domain scores for all domains.

        Args:
            query: User query text

        Returns:
            Dictionary mapping domain names to scores
        """
        query_lower = query.lower()

        scores = {}
        for domain, keywords in self.domain_keywords.items():
            scores[domain] = sum(1 for kw in keywords if kw in query_lower)

        return scores

    def get_modifier_scores(self, query: str) -> dict[str, int]:
        """
        Calculate modifier scores (updates, tax_genius, etc.).

        Args:
            query: User query text

        Returns:
            Dictionary mapping modifier names to scores
        """
        query_lower = query.lower()

        scores = {}
        for modifier, keywords in self.modifier_keywords.items():
            scores[modifier] = sum(1 for kw in keywords if kw in query_lower)

        return scores

    def get_matched_keywords(self, query: str, domain: str) -> list[str]:
        """
        Get list of matched keywords for a domain.

        Args:
            query: User query text
            domain: Domain name

        Returns:
            List of matched keywords
        """
        if domain not in self.domain_keywords:
            return []

        query_lower = query.lower()
        keywords = self.domain_keywords[domain]
        return [kw for kw in keywords if kw in query_lower]

    def detect_multi_domain(self, query: str, threshold: int = 1) -> list[str]:
        """
        Detect if query spans multiple domains.

        Args:
            query: User query text
            threshold: Minimum score to consider a domain active

        Returns:
            List of active domain names (domains with score >= threshold)
        """
        scores = self.calculate_domain_scores(query)
        active_domains = [domain for domain, score in scores.items() if score >= threshold]
        if len(active_domains) > 1:
            active_scores = {k: v for k, v in scores.items() if v > 0}
            logger.info(
                f"🔀 [KeywordMatcher] Multi-domain query detected: {active_domains} "
                f"(scores: {active_scores})",
            )
        return active_domains
