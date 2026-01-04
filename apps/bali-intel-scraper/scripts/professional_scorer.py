"""
Professional News Scoring System for Bali Intel Feed
Multi-dimensional scoring: Relevance, Authority, Recency, Accuracy, Geographic

Based on:
- CRAAP Test Framework (Currency, Relevance, Authority, Accuracy, Purpose)
- GDELT Scoring Methodology
- Editorial Algorithm Best Practices

Formula: FINAL = (R×0.30) + (A×0.20) + (T×0.20) + (C×0.15) + (G×0.15)
"""

import re
import math
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class ScoreResult:
    """Result of scoring a news article"""

    final_score: int
    relevance: int
    authority: int
    recency: int
    accuracy: int
    geographic: int
    priority: str
    matched_keywords: List[str]
    matched_category: str
    explanation: str


# =============================================================================
# KEYWORD DATABASE (Bilingual: English + Bahasa Indonesia)
# =============================================================================

KEYWORDS = {
    "immigration": {
        "direct": [  # Score 100
            # English
            "kitas",
            "kitap",
            "itas",
            "itap",
            "vitas",
            "golden visa",
            "second home visa",
            "digital nomad visa",
            "retirement visa",
            "investor visa",
            "work permit",
            "stay permit",
            "exit permit",
            "re-entry permit",
            # Bahasa Indonesia
            "izin tinggal terbatas",
            "izin tinggal tetap",
            "visa emas",
            "visa pensiun",
            "visa investor",
            "izin kerja",
            "izin masuk kembali",
        ],
        "high": [  # Score 90
            # English
            "rptka",
            "imta",
            "immigration",
            "deportation",
            "visa extension",
            "visa renewal",
            "overstay",
            "sponsor visa",
            "telex visa",
            "visa on arrival",
            "voa",
            "e-visa",
            "evoa",
            "visa free",
            # Bahasa Indonesia
            "imigrasi",
            "deportasi",
            "perpanjangan visa",
            "tenaga kerja asing",
            "tka",
            "izin keluar",
            "bebas visa",
            "visa kunjungan",
        ],
        "medium": [  # Score 70
            "passport",
            "paspor",
            "border",
            "customs",
            "bea cukai",
            "arrival",
            "departure",
            "kedatangan",
            "keberangkatan",
        ],
    },
    "business": {
        "direct": [  # Score 100
            # English
            "pt pma",
            "foreign investment",
            "company registration",
            "nib",
            "business license",
            "oss",
            "bkpm",
            "investment license",
            "business permit",
            # Bahasa Indonesia
            "penanaman modal asing",
            "pendirian pt",
            "nomor induk berusaha",
            "izin usaha",
            "perizinan berusaha",
            "modal asing",
        ],
        "high": [  # Score 90
            # English
            "kbli",
            "siup",
            "trading license",
            "lkpm",
            "company setup",
            "incorporation",
            "shareholder",
            "director",
            "commissioner",
            "articles of association",
            # Bahasa Indonesia
            "klasifikasi baku lapangan usaha",
            "surat izin usaha perdagangan",
            "laporan kegiatan penanaman modal",
            "akta pendirian",
            "pemegang saham",
            "direktur",
            "komisaris",
            "anggaran dasar",
        ],
        "medium": [  # Score 70
            "business",
            "company",
            "corporate",
            "enterprise",
            "startup",
            "sme",
            "umkm",
            "usaha",
            "bisnis",
            "perusahaan",
            "korporasi",
            "wirausaha",
        ],
    },
    "tax": {
        "direct": [  # Score 100
            # English
            "npwp",
            "tax id",
            "pph 21",
            "pph 23",
            "pph 26",
            "ppn",
            "vat",
            "income tax",
            "corporate tax",
            "tax return",
            "spt",
            "coretax",
            "ctas",
            # Bahasa Indonesia
            "nomor pokok wajib pajak",
            "pajak penghasilan",
            "pajak pertambahan nilai",
            "surat pemberitahuan",
            "wajib pajak",
            "sistem inti pajak",
        ],
        "high": [  # Score 90
            # English
            "withholding tax",
            "tax rate",
            "tax compliance",
            "faktur pajak",
            "tax invoice",
            "djp",
            "tax office",
            "tax amnesty",
            "tax holiday",
            "tax incentive",
            # Bahasa Indonesia
            "tarif pajak",
            "kepatuhan pajak",
            "direktorat jenderal pajak",
            "pengampunan pajak",
            "insentif pajak",
            "fasilitas pajak",
        ],
        "medium": [  # Score 70
            "tax",
            "pajak",
            "fiscal",
            "fiskal",
            "taxation",
            "perpajakan",
            "levy",
            "retribusi",
        ],
    },
    "property": {
        "direct": [  # Score 100
            # English
            "hgb",
            "shm",
            "hak pakai",
            "right to build",
            "freehold",
            "leasehold",
            "hak sewa",
            "land title",
            "property ownership",
            "land ownership",
            # Bahasa Indonesia
            "hak guna bangunan",
            "sertifikat hak milik",
            "hak guna usaha",
            "hgu",
            "sertifikat tanah",
            "kepemilikan tanah",
            "kepemilikan properti",
        ],
        "high": [  # Score 90
            # English
            "bpn",
            "land office",
            "land certificate",
            "nominee",
            "real estate",
            "property market",
            "villa",
            "apartment",
            "condo",
            # Bahasa Indonesia
            "badan pertanahan nasional",
            "agraria",
            "pertanahan",
            "properti",
            "perumahan",
        ],
        "medium": [  # Score 70
            "property",
            "land",
            "tanah",
            "rumah",
            "house",
            "building",
            "bangunan",
            "konstruksi",
            "construction",
        ],
    },
    "tech": {
        "direct": [  # Score 100
            # English
            "artificial intelligence",
            " ai ",
            "machine learning",
            "deep learning",
            "nlp",
            "natural language",
            "fintech regulation",
            "ai regulation",
            "ai policy",
            "stranas ka",
            "ai strategy",
            # Bahasa Indonesia
            "kecerdasan buatan",
            "pembelajaran mesin",
            "regulasi ai",
            "kebijakan ai",
            "strategi nasional kecerdasan artifisial",
        ],
        "high": [  # Score 90
            # English
            "startup funding",
            "tech startup",
            "unicorn",
            "venture capital",
            "fintech",
            "digital bank",
            "e-commerce regulation",
            "data protection",
            "ojk fintech",
            "digital economy",
            # Bahasa Indonesia
            "startup teknologi",
            "pendanaan startup",
            "ekonomi digital",
            "bank digital",
            "perlindungan data",
            "siupmse",
        ],
        "medium": [  # Score 70
            "startup",
            "tech",
            "technology",
            "teknologi",
            "digital",
            "software",
            "aplikasi",
            "app",
            "platform",
            "innovation",
            "inovasi",
        ],
    },
    "lifestyle": {
        "high": [  # Score 80
            "expat",
            "expatriate",
            "digital nomad",
            "remote work",
            "coliving",
            "coworking",
            "nomad digital",
            "kerja jarak jauh",
        ],
        "medium": [  # Score 60
            "tourism",
            "tourist",
            "pariwisata",
            "wisatawan",
            "travel",
            "vacation",
            "liburan",
            "holiday",
        ],
    },
}


# =============================================================================
# SOURCE AUTHORITY DATABASE
# =============================================================================

SOURCE_AUTHORITY = {
    # Government Sources (95-100)
    "government": {
        "score": 98,
        "sources": [
            "imigrasi.go.id",
            "pajak.go.id",
            "bkpm.go.id",
            "kemenkeu.go.id",
            "kemlu.go.id",
            "oss.go.id",
            "indonesia.go.id",
            "kominfo.go.id",
            "ojk.go.id",
            "bps.go.id",
            "bi.go.id",
            "atrbpn.go.id",
        ],
    },
    # Major International Media (85-94)
    "major_media": {
        "score": 88,
        "sources": [
            "reuters",
            "bloomberg",
            "bbc",
            "cnbc",
            "cnn",
            "financial times",
            "wall street journal",
            "nikkei",
            "south china morning post",
            "the guardian",
            "associated press",
            "afp",
            "dw.com",
        ],
    },
    # Indonesian National Media (80-89)
    "national_media": {
        "score": 82,
        "sources": [
            "jakarta post",
            "tempo.co",
            "kompas",
            "detik",
            "cnbc indonesia",
            "bisnis.com",
            "kontan",
            "antara news",
            "republika",
            "media indonesia",
            "liputan6",
            "tirto.id",
            "katadata",
        ],
    },
    # Expert/Trade Publications (70-79)
    "expert_trade": {
        "score": 75,
        "sources": [
            "indonesia expat",
            "bali advertiser",
            "now bali",
            "the bali sun",
            "coconuts",
            "tech in asia",
            "e27",
            "dailysocial",
            "techinasia",
            "emerhub",
            "cekindo",
            "letsmoveindonesia",
            "incorp",
            "paul hype page",
        ],
    },
    # Local/Regional News (60-69)
    "local_news": {
        "score": 65,
        "sources": [
            "tribun",
            "bali tribune",
            "nusa bali",
            "radar bali",
            "bali post",
            "kumparan",
            "okezone",
            "sindonews",
            "merdeka",
        ],
    },
    # Blogs/Social (40-59)
    "blogs": {
        "score": 50,
        "sources": [
            "medium.com",
            "wordpress",
            "blogspot",
            "substack",
            "linkedin",
        ],
    },
}


# =============================================================================
# GEOGRAPHIC KEYWORDS
# =============================================================================

GEOGRAPHIC = {
    "bali_specific": {
        "score": 100,
        "keywords": [
            "bali",
            "denpasar",
            "kuta",
            "seminyak",
            "canggu",
            "ubud",
            "sanur",
            "nusa dua",
            "uluwatu",
            "jimbaran",
            "badung",
            "gianyar",
            "tabanan",
            "buleleng",
            "karangasem",
            "klungkung",
            "bangli",
            "ngurah rai",
            "bali governor",
            "gubernur bali",
        ],
    },
    "indonesia_wide": {
        "score": 75,
        "keywords": [
            "indonesia",
            "indonesian",
            "jakarta",
            "java",
            "surabaya",
            "bandung",
            "yogyakarta",
            "lombok",
            "sumatra",
            "sulawesi",
            "kalimantan",
            "papua",
            "national",
            "nasional",
            "pemerintah indonesia",
            "indonesian government",
        ],
    },
    "southeast_asia": {
        "score": 45,
        "keywords": [
            "asean",
            "southeast asia",
            "asia tenggara",
            "singapore",
            "malaysia",
            "thailand",
            "vietnam",
            "philippines",
            "regional",
        ],
    },
}


# =============================================================================
# ACCURACY INDICATORS
# =============================================================================

ACCURACY_POSITIVE = [
    # Citations & Data
    "according to",
    "menurut",
    "stated",
    "menyatakan",
    "official",
    "resmi",
    "confirmed",
    "dikonfirmasi",
    "announced",
    "mengumumkan",
    "regulation",
    "peraturan",
    "law",
    "undang-undang",
    "decree",
    "keputusan",
    "minister",
    "menteri",
    "president",
    "presiden",
    "data shows",
    "statistics",
    "statistik",
    "percent",
    "persen",
    "million",
    "juta",
    "billion",
    "miliar",
    # Source references
    "source:",
    "sumber:",
    "reported by",
    "dilaporkan",
]

ACCURACY_NEGATIVE = [
    # Speculation
    "rumor",
    "allegedly",
    "unconfirmed",
    "belum dikonfirmasi",
    "sources say",
    "might",
    "could",
    "mungkin",
    "bisa jadi",
    "speculation",
    "spekulasi",
    # Clickbait
    "shocking",
    "mengejutkan",
    "you won't believe",
    "click here",
    "klik di sini",
    "viral",
    "exclusive",
    "eksklusif",
    "breaking",
]


# =============================================================================
# SCORING FUNCTIONS
# =============================================================================


def calculate_relevance(title: str, content: str) -> Tuple[int, List[str], str]:
    """
    Calculate relevance score based on keyword matching.
    Returns (score, matched_keywords, category)
    """
    text = f" {title} {content} ".lower()

    best_score = 0
    matched_keywords = []
    matched_category = "general"

    for category, levels in KEYWORDS.items():
        for level, keywords in levels.items():
            level_score = {"direct": 100, "high": 90, "medium": 70}.get(level, 50)

            for keyword in keywords:
                # Use word boundary matching for short keywords
                if len(keyword) <= 3:
                    pattern = rf"\b{re.escape(keyword)}\b"
                else:
                    pattern = re.escape(keyword)

                if re.search(pattern, text):
                    if level_score > best_score:
                        best_score = level_score
                        matched_category = category
                    matched_keywords.append(keyword)

    # No match = low score
    if best_score == 0:
        best_score = 20

    return best_score, list(set(matched_keywords))[:5], matched_category


def calculate_authority(source: str, source_url: str = "") -> int:
    """
    Calculate authority score based on source reputation.
    """
    source_lower = source.lower()
    url_lower = (source_url or "").lower()
    combined = f"{source_lower} {url_lower}"

    for category, data in SOURCE_AUTHORITY.items():
        for known_source in data["sources"]:
            if known_source in combined:
                return data["score"]

    # Unknown source - check if it looks official
    if ".go.id" in url_lower or ".gov" in url_lower:
        return 90
    elif ".co.id" in url_lower or ".com" in url_lower:
        return 55

    return 40  # Unknown


def calculate_recency(published_at: Optional[datetime]) -> int:
    """
    Calculate recency score with exponential decay.
    Half-life = 5 days
    """
    if not published_at:
        return 50  # Unknown date

    now = datetime.utcnow()
    if published_at.tzinfo:
        published_at = published_at.replace(tzinfo=None)

    age_days = (now - published_at).total_seconds() / 86400

    if age_days < 0:
        return 100  # Future date (probably error, treat as fresh)

    # Exponential decay: score = 100 * e^(-age/7)
    score = 100 * math.exp(-age_days / 7)

    return max(10, min(100, int(score)))


def calculate_accuracy(title: str, content: str) -> int:
    """
    Calculate accuracy score based on citation indicators.
    """
    text = f"{title} {content}".lower()

    positive_count = sum(1 for indicator in ACCURACY_POSITIVE if indicator in text)
    negative_count = sum(1 for indicator in ACCURACY_NEGATIVE if indicator in text)

    # Base score
    base_score = 60

    # Adjust based on indicators
    score = base_score + (positive_count * 8) - (negative_count * 15)

    return max(20, min(100, score))


def calculate_geographic(title: str, content: str) -> int:
    """
    Calculate geographic relevance score.
    """
    text = f"{title} {content}".lower()

    # Check Bali-specific first
    for keyword in GEOGRAPHIC["bali_specific"]["keywords"]:
        if keyword in text:
            return GEOGRAPHIC["bali_specific"]["score"]

    # Check Indonesia-wide
    for keyword in GEOGRAPHIC["indonesia_wide"]["keywords"]:
        if keyword in text:
            return GEOGRAPHIC["indonesia_wide"]["score"]

    # Check Southeast Asia
    for keyword in GEOGRAPHIC["southeast_asia"]["keywords"]:
        if keyword in text:
            return GEOGRAPHIC["southeast_asia"]["score"]

    return 25  # No geographic match


def calculate_final_score(
    title: str,
    content: str,
    source: str,
    source_url: str = "",
    published_at: Optional[datetime] = None,
) -> ScoreResult:
    """
    Calculate final multi-dimensional score.

    Formula: FINAL = (R×0.30) + (A×0.20) + (T×0.20) + (C×0.15) + (G×0.15)
    """
    # Calculate individual dimensions
    relevance, matched_keywords, category = calculate_relevance(title, content or "")
    authority = calculate_authority(source, source_url)
    recency = calculate_recency(published_at)
    accuracy = calculate_accuracy(title, content or "")
    geographic = calculate_geographic(title, content or "")

    # Weighted final score
    final = (
        relevance * 0.30
        + authority * 0.20
        + recency * 0.20
        + accuracy * 0.15
        + geographic * 0.15
    )
    final_score = int(round(final))

    # Determine priority
    if final_score >= 75:
        priority = "high"
    elif final_score >= 50:
        priority = "medium"
    elif final_score >= 35:
        priority = "low"
    else:
        priority = "filtered"

    # Build explanation
    explanation = (
        f"R:{relevance} A:{authority} T:{recency} C:{accuracy} G:{geographic} "
        f"→ {final_score} ({priority})"
    )

    return ScoreResult(
        final_score=final_score,
        relevance=relevance,
        authority=authority,
        recency=recency,
        accuracy=accuracy,
        geographic=geographic,
        priority=priority,
        matched_keywords=matched_keywords,
        matched_category=category,
        explanation=explanation,
    )


# =============================================================================
# OLLAMA INTEGRATION (Optional AI-enhanced scoring)
# =============================================================================


async def enhance_with_ollama(
    title: str,
    content: str,
    base_result: ScoreResult,
    ollama_url: str = "http://localhost:11434/api/generate",
    model: str = "llama3.2:3b",
) -> ScoreResult:
    """
    Optionally enhance scoring with Ollama for edge cases.
    Only called when base score is ambiguous (40-60 range).
    """
    import httpx
    import json

    if base_result.final_score < 40 or base_result.final_score > 60:
        return base_result  # Clear decision, no need for AI

    prompt = f"""Rate this news relevance for Bali expats (adjust -10 to +10):

TITLE: {title}
CATEGORY: {base_result.matched_category}
BASE SCORE: {base_result.final_score}

Reply JSON only: {{"adjustment": <-10 to +10>, "reason": "<5 words>"}}"""

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                ollama_url,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 50},
                },
            )

            if response.status_code == 200:
                data = response.json()
                result_text = data.get("response", "").strip()

                if "{" in result_text:
                    json_str = result_text[
                        result_text.find("{") : result_text.rfind("}") + 1
                    ]
                    result = json.loads(json_str)
                    adjustment = int(result.get("adjustment", 0))
                    adjustment = max(-10, min(10, adjustment))

                    new_score = base_result.final_score + adjustment
                    new_score = max(0, min(100, new_score))

                    # Update priority if score changed significantly
                    if new_score >= 75:
                        priority = "high"
                    elif new_score >= 50:
                        priority = "medium"
                    elif new_score >= 35:
                        priority = "low"
                    else:
                        priority = "filtered"

                    return ScoreResult(
                        final_score=new_score,
                        relevance=base_result.relevance,
                        authority=base_result.authority,
                        recency=base_result.recency,
                        accuracy=base_result.accuracy,
                        geographic=base_result.geographic,
                        priority=priority,
                        matched_keywords=base_result.matched_keywords,
                        matched_category=base_result.matched_category,
                        explanation=f"{base_result.explanation} +AI:{adjustment}",
                    )
    except Exception as e:
        logger.warning(f"Ollama enhancement failed: {e}")

    return base_result


# =============================================================================
# MAIN SCORING FUNCTION
# =============================================================================


async def score_article(
    title: str,
    content: str = "",
    source: str = "",
    source_url: str = "",
    published_at: Optional[datetime] = None,
    use_ollama: bool = False,
) -> ScoreResult:
    """
    Main entry point for scoring an article.

    Args:
        title: Article title
        content: Article content/summary
        source: Source name
        source_url: Source URL
        published_at: Publication datetime
        use_ollama: Whether to use Ollama for edge cases

    Returns:
        ScoreResult with all scoring dimensions
    """
    result = calculate_final_score(
        title=title,
        content=content,
        source=source,
        source_url=source_url,
        published_at=published_at,
    )

    if use_ollama:
        result = await enhance_with_ollama(title, content, result)

    return result


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    import asyncio

    test_articles = [
        {
            "title": "Indonesia Launches New Golden Visa Program for Foreign Investors",
            "content": "The Indonesian government announced new golden visa regulations through BKPM.",
            "source": "Jakarta Post",
            "source_url": "https://jakartapost.com/article",
            "published_at": datetime.utcnow() - timedelta(days=1),
        },
        {
            "title": "Bali Governor Announces New KITAS Requirements for Digital Nomads",
            "content": "Gubernur Bali menyatakan peraturan baru untuk izin tinggal terbatas.",
            "source": "Tribun Bali",
            "source_url": "https://tribun.com/bali",
            "published_at": datetime.utcnow() - timedelta(hours=6),
        },
        {
            "title": "AI Startup Funding Reaches Record High in Indonesia",
            "content": "Kecerdasan buatan startups mendapat pendanaan dari venture capital.",
            "source": "Tech in Asia",
            "source_url": "https://techinasia.com",
            "published_at": datetime.utcnow() - timedelta(days=2),
        },
        {
            "title": "Celebrity Wedding in Bali Goes Viral",
            "content": "Famous actor gets married in luxury villa.",
            "source": "Unknown Blog",
            "source_url": "https://randomsite.com",
            "published_at": datetime.utcnow() - timedelta(days=10),
        },
    ]

    async def test():
        print("=" * 70)
        print("PROFESSIONAL NEWS SCORER - TEST")
        print("=" * 70)

        for article in test_articles:
            result = await score_article(**article)
            print(f"\n📰 {article['title'][:60]}...")
            print(f"   Source: {article['source']}")
            print(f"   Score: {result.final_score} → {result.priority.upper()}")
            print(f"   {result.explanation}")
            print(f"   Keywords: {', '.join(result.matched_keywords) or 'none'}")
            print(f"   Category: {result.matched_category}")

    asyncio.run(test())
