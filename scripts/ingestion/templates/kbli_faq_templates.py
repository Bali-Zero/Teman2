"""
Template FAQ generiche per KBLI.
FAQ base che possono essere personalizzate con dati specifici KBLI.
"""

from typing import List, Dict, Optional


def get_faq_template_pma(
    pma_allowed: Optional[bool],
    pma_max_percentage: Optional[str],
    min_investment_idr: int = 10000000000
) -> List[Dict[str, str]]:
    """Genera FAQ template per PMA."""
    faq = []
    
    if pma_allowed is False:
        faq.append({
            "pertanyaan": "Bisakah saya membuka bisnis ini sebagai warga negara asing?",
            "pertanyaan_en": "Can I open this business as a foreigner?",
            "jawaban": "Tidak, sektor ini TERTUTUP untuk investasi asing (PMA). Hanya warga negara Indonesia yang dapat membuka bisnis ini.",
            "jawaban_en": "No, this sector is CLOSED to foreign investment (PMA). Only Indonesian citizens can open this business."
        })
    elif pma_allowed is True:
        if pma_max_percentage == "100%":
            faq.append({
                "pertanyaan": "Bisakah saya membuka bisnis ini sebagai warga negara asing?",
                "pertanyaan_en": "Can I open this business as a foreigner?",
                "jawaban": f"Ya, sektor ini 100% terbuka untuk investasi asing melalui PT PMA. Modal minimum yang dibutuhkan adalah IDR {min_investment_idr:,}.",
                "jawaban_en": f"Yes, this sector is 100% open to foreign investment through PT PMA. Minimum capital required is IDR {min_investment_idr:,}."
            })
        else:
            faq.append({
                "pertanyaan": "Bisakah saya membuka bisnis ini sebagai warga negara asing?",
                "pertanyaan_en": "Can I open this business as a foreigner?",
                "jawaban": f"Ya, tetapi investasi asing dibatasi maksimal {pma_max_percentage}. Modal minimum yang dibutuhkan adalah IDR {min_investment_idr:,}.",
                "jawaban_en": f"Yes, but foreign investment is limited to maximum {pma_max_percentage}. Minimum capital required is IDR {min_investment_idr:,}."
            })
        
        faq.append({
            "pertanyaan": "Berapa modal yang dibutuhkan untuk PT PMA?",
            "pertanyaan_en": "How much capital is required for PT PMA?",
            "jawaban": f"Minimum IDR {min_investment_idr:,} (IDR 10 miliar) modal total, dengan IDR {min_investment_idr:,} disetor sebagai paid-up capital.",
            "jawaban_en": f"Minimum IDR {min_investment_idr:,} (IDR 10 billion) total capital, with IDR {min_investment_idr:,} paid-up capital."
        })
    
    return faq


def get_faq_template_skala_usaha(allowed_scales: List[str]) -> List[Dict[str, str]]:
    """Genera FAQ template per skala usaha."""
    scales_str = ", ".join(allowed_scales)
    
    return [
        {
            "pertanyaan": "Skala usaha apa saja yang diizinkan untuk KBLI ini?",
            "pertanyaan_en": "What business scales are allowed for this KBLI?",
            "jawaban": f"KBLI ini dapat dioperasikan oleh semua skala usaha: {scales_str}.",
            "jawaban_en": f"This KBLI can be operated by all business scales: {scales_str}."
        }
    ]


def get_faq_template_risk_level(risk_level: Optional[str]) -> List[Dict[str, str]]:
    """Genera FAQ template per tingkat risiko."""
    if not risk_level or risk_level == "Tidak diatur":
        return []
    
    risk_explanations = {
        "Rendah": {
            "id": "Risiko rendah berarti hanya memerlukan registrasi NIB tanpa audit preventif.",
            "en": "Low risk means only NIB registration required without preventive audit."
        },
        "Menengah Rendah": {
            "id": "Risiko menengah rendah memerlukan NIB dan sertifikat standar.",
            "en": "Low-medium risk requires NIB and standard certificate."
        },
        "Menengah": {
            "id": "Risiko menengah memerlukan dokumen lingkungan (UKL-UPL) dan izin tambahan.",
            "en": "Medium risk requires environmental documents (UKL-UPL) and additional permits."
        },
        "Menengah Tinggi": {
            "id": "Risiko menengah tinggi memerlukan dokumen lingkungan (AMDAL) dan izin khusus.",
            "en": "Medium-high risk requires environmental documents (AMDAL) and special permits."
        },
        "Tinggi": {
            "id": "Risiko tinggi memerlukan dokumen lingkungan (AMDAL), izin khusus, dan persetujuan dari instansi terkait.",
            "en": "High risk requires environmental documents (AMDAL), special permits, and approval from related agencies."
        }
    }
    
    explanation = risk_explanations.get(risk_level, {})
    if not explanation:
        return []
    
    return [
        {
            "pertanyaan": "Apa arti tingkat risiko ini?",
            "pertanyaan_en": "What does this risk level mean?",
            "jawaban": explanation["id"],
            "jawaban_en": explanation["en"]
        }
    ]


def get_faq_template_pb_umku(has_pb_umku: bool, pb_umku_count: int = 0) -> List[Dict[str, str]]:
    """Genera FAQ template per PB UMKU."""
    if not has_pb_umku or pb_umku_count == 0:
        return []
    
    return [
        {
            "pertanyaan": "Permisi apa saja yang diperlukan untuk operasional?",
            "pertanyaan_en": "What permits are required for operations?",
            "jawaban": f"Selain NIB, diperlukan {pb_umku_count} permisi di supporto (PB UMKU) sebelum memulai operasional. Lihat sezione PB UMKU per dettagli.",
            "jawaban_en": f"In addition to NIB, {pb_umku_count} support permits (PB UMKU) are required before starting operations. See PB UMKU section for details."
        }
    ]


def combine_faq_templates(
    pma_allowed: Optional[bool],
    pma_max_percentage: Optional[str],
    allowed_scales: List[str],
    risk_level: Optional[str],
    has_pb_umku: bool = False,
    pb_umku_count: int = 0,
    min_investment_idr: int = 10000000000
) -> List[Dict[str, str]]:
    """Combina tutti i template FAQ."""
    faq = []
    
    # FAQ PMA
    faq.extend(get_faq_template_pma(pma_allowed, pma_max_percentage, min_investment_idr))
    
    # FAQ Skala Usaha
    faq.extend(get_faq_template_skala_usaha(allowed_scales))
    
    # FAQ Risk Level
    faq.extend(get_faq_template_risk_level(risk_level))
    
    # FAQ PB UMKU
    faq.extend(get_faq_template_pb_umku(has_pb_umku, pb_umku_count))
    
    return faq
