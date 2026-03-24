"""
Lightweight keyword-based query translator for Bali Zero domain.

Translates common Italian/English business terms to Indonesian equivalents
to improve embedding similarity with Indonesian-language documents in Qdrant.

No LLM dependency — uses a curated dictionary of ~200 domain terms.
Falls back gracefully: if no terms match, returns the original query.

Usage:
    translator = KeywordTranslator()
    expanded = translator.translate("Quanto costa aprire una PT PMA?")
    # → "Quanto costa aprire una PT PMA? How much does it cost to open a PT PMA? Berapa biaya membuka PT PMA?"
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Italian → English → Indonesian mappings for Bali Zero domain
# Format: {italian_phrase: (english, indonesian)}
_TERM_MAP: dict[str, tuple[str, str]] = {
    # --- Business Entity Types ---
    "pt pma": ("PT PMA foreign company", "PT PMA perusahaan asing"),
    "pt pmdn": ("PT PMDN domestic company", "PT PMDN perusahaan domestik"),
    "cv": ("CV partnership", "CV persekutuan komanditer"),
    "firma": ("firma partnership", "firma persekutuan"),
    "perseroan terbatas": ("limited liability company", "perseroan terbatas"),
    "società": ("company", "perusahaan"),
    "azienda": ("company business", "perusahaan bisnis"),
    "aprire un'azienda": ("open a company", "membuka perusahaan"),
    "aprire una società": ("establish a company", "mendirikan perusahaan"),
    "aprire una": ("open establish", "membuka mendirikan"),
    # --- Visa Types ---
    "kitas": ("KITAS temporary stay permit", "KITAS izin tinggal terbatas"),
    "kitap": ("KITAP permanent stay permit", "KITAP izin tinggal tetap"),
    "visto": ("visa", "visa"),
    "visto turistico": ("tourist visa", "visa wisata"),
    "visto investitore": ("investor visa", "visa investor"),
    "visto lavoro": ("work visa work permit", "visa kerja izin kerja"),
    "permesso di soggiorno": ("stay permit residence permit", "izin tinggal"),
    "b211a": ("B211A social cultural visa", "B211A visa sosial budaya"),
    "b211": ("B211 visit visa", "B211 visa kunjungan"),
    "e33g": ("E33G digital nomad visa", "E33G visa nomad digital"),
    "rinnovo": ("renewal extension", "perpanjangan pembaruan"),
    "rinnovare": ("renew extend", "memperpanjang memperbarui"),
    "rinnovo visto": ("visa renewal extension", "perpanjangan visa"),
    # --- Documents & Permits ---
    "documenti": ("documents requirements", "dokumen persyaratan"),
    "requisiti": ("requirements", "persyaratan"),
    "nib": ("NIB business identification number", "NIB nomor induk berusaha"),
    "npwp": ("NPWP tax identification number", "NPWP nomor pokok wajib pajak"),
    "imta": ("IMTA foreign worker permit", "IMTA izin mempekerjakan tenaga asing"),
    "rptka": ("RPTKA foreign worker utilization plan", "RPTKA rencana penggunaan tenaga kerja asing"),
    "oss": ("OSS online single submission", "OSS perizinan berusaha"),
    "akte pendirian": ("deed of establishment", "akta pendirian"),
    # --- Costs & Pricing ---
    "quanto costa": ("how much does it cost price", "berapa biaya harga"),
    "costo": ("cost price", "biaya harga"),
    "prezzo": ("price fee", "harga biaya"),
    "tariffe": ("fees rates", "tarif biaya"),
    "contabilità": ("accounting bookkeeping", "akuntansi pembukuan"),
    "servizio": ("service", "layanan jasa"),
    # --- Tax ---
    "tasse": ("taxes", "pajak"),
    "imposta": ("tax", "pajak"),
    "imposta sul reddito": ("income tax", "pajak penghasilan PPh"),
    "iva": ("VAT PPN", "PPN pajak pertambahan nilai"),
    "dichiarazione fiscale": ("tax return", "laporan pajak SPT"),
    "pph": ("PPh income tax", "PPh pajak penghasilan"),
    "ppn": ("PPN value added tax", "PPN pajak pertambahan nilai"),
    # --- Property ---
    "proprietà": ("property real estate", "properti"),
    "terreno": ("land plot", "tanah"),
    "affitto": ("rent lease", "sewa"),
    "hak pakai": ("right to use", "hak pakai"),
    "hgb": ("HGB right to build", "HGB hak guna bangunan"),
    # --- KBLI ---
    "codice kbli": ("KBLI code business classification", "kode KBLI klasifikasi usaha"),
    "classificazione": ("classification", "klasifikasi"),
    "ristorante": ("restaurant food service", "restoran penyediaan makanan"),
    "bar": ("bar cafe", "bar kafe"),
    "hotel": ("hotel accommodation", "hotel akomodasi"),
    "commercio": ("trade commerce", "perdagangan"),
    "costruzione": ("construction", "konstruksi"),
    "tecnologia": ("technology IT", "teknologi informatika"),
    "consulenza": ("consulting advisory", "konsultasi"),
    # --- Banking ---
    "conto bancario": ("bank account", "rekening bank"),
    "banca": ("bank", "bank"),
    # --- Time & Process ---
    "quanto tempo": ("how long duration", "berapa lama durasi"),
    "processo": ("process procedure", "proses prosedur"),
    "procedura": ("procedure steps", "prosedur langkah"),
    "differenza": ("difference comparison", "perbedaan perbandingan"),
    "tra": ("between", "antara"),
    # --- General ---
    "stranieri": ("foreigners expats", "orang asing ekspatriat"),
    "straniero": ("foreigner expat", "orang asing ekspatriat"),
    "indonesia": ("Indonesia", "Indonesia"),
    "bali": ("Bali", "Bali"),
    "come": ("how to", "bagaimana cara"),
    "cosa è": ("what is", "apa itu"),
    "cos'è": ("what is", "apa itu"),
    "quali sono": ("what are", "apa saja"),
    "per": ("for to", "untuk"),
    "ottenere": ("obtain get", "mendapatkan memperoleh"),
    "servono": ("needed required", "diperlukan dibutuhkan"),
}


class KeywordTranslator:
    """
    Lightweight domain-specific query translator.

    Translates Italian/English queries to include English and Indonesian
    equivalents for better embedding match with Indonesian documents.

    No LLM dependency — uses curated term dictionary.
    """

    def __init__(self, term_map: dict[str, tuple[str, str]] | None = None) -> None:
        self._terms = term_map or _TERM_MAP
        # Sort by longest key first for greedy matching
        self._sorted_keys = sorted(self._terms.keys(), key=len, reverse=True)

    def translate(self, query: str) -> str:
        """
        Expand query with English and Indonesian translations.

        Args:
            query: Original query (any language)

        Returns:
            Expanded query: "{original} {english_terms} {indonesian_terms}"
            If no terms matched, returns original unchanged.
        """
        query_lower = query.lower()
        en_parts: list[str] = []
        id_parts: list[str] = []
        matched = set()

        for key in self._sorted_keys:
            if key in query_lower and key not in matched:
                en_term, id_term = self._terms[key]
                en_parts.append(en_term)
                id_parts.append(id_term)
                matched.add(key)
                # Also mark substrings as matched to avoid duplication
                for other_key in self._sorted_keys:
                    if other_key != key and other_key in key:
                        matched.add(other_key)

        if not en_parts:
            return query

        en_expansion = " ".join(en_parts)
        id_expansion = " ".join(id_parts)

        expanded = f"{query} {en_expansion} {id_expansion}"
        logger.debug(
            f"Query expanded: '{query}' → +{len(en_parts)} EN terms, +{len(id_parts)} ID terms"
        )
        return expanded

    def get_translations(self, query: str) -> dict[str, Any]:
        """
        Get detailed translation breakdown.

        Returns:
            Dict with original, english, indonesian, and matched_terms.
        """
        query_lower = query.lower()
        matches: list[dict[str, str]] = []
        matched = set()

        for key in self._sorted_keys:
            if key in query_lower and key not in matched:
                en_term, id_term = self._terms[key]
                matches.append({"term": key, "en": en_term, "id": id_term})
                matched.add(key)
                for other_key in self._sorted_keys:
                    if other_key != key and other_key in key:
                        matched.add(other_key)

        return {
            "original": query,
            "expanded": self.translate(query),
            "matched_terms": matches,
            "num_matches": len(matches),
        }


# Module-level singleton
_translator: KeywordTranslator | None = None


def get_keyword_translator() -> KeywordTranslator:
    """Get or create the singleton KeywordTranslator."""
    global _translator
    if _translator is None:
        _translator = KeywordTranslator()
    return _translator
