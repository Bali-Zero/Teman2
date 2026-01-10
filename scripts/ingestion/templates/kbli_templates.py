"""
Template per campi derivati del payload KBLI ultimate.
Timeline, documenti, obblighi, warnings basati su regole.
"""

from typing import Dict, List, Optional
from scripts.ingestion.schemas.kbli_ultimate_schema import RiskLevel


# Template Timeline (giorni stimati)
TIMELINE_TEMPLATES: Dict[str, Dict[str, int]] = {
    "Rendah": {"min": 30, "max": 60},
    "Menengah Rendah": {"min": 45, "max": 75},
    "Menengah": {"min": 60, "max": 90},
    "Menengah Tinggi": {"min": 90, "max": 120},
    "Tinggi": {"min": 120, "max": 180},
    "Tidak diatur": {"min": 30, "max": 60}  # Default
}


def get_timeline_for_risk(risk_level: Optional[str]) -> Dict[str, int]:
    """Ottiene timeline template per livello di rischio."""
    if not risk_level:
        risk_level = "Tidak diatur"
    return TIMELINE_TEMPLATES.get(risk_level, TIMELINE_TEMPLATES["Tidak diatur"])


# Template Documenti Necessari per livello rischio
DOCUMENTI_BASE = {
    "per_costituzione_pt": [
        "KTP semua pendiri",
        "NPWP semua pendiri",
        "Foto 3x4 semua pendiri",
        "Domisili usaha",
        "Draft Akta Pendirian"
    ],
    "per_costituzione_pt_en": [
        "ID card of all founders",
        "NPWP of all founders",
        "3x4 photos of all founders",
        "Business domicile",
        "Draft Deed of Establishment"
    ],
    "per_nib": [
        "Akta Pendirian + SK Kemenkumham",
        "NPWP Perusahaan",
        "Alamat domisili usaha",
        "Data KBLI yang dipilih"
    ],
    "per_nib_en": [
        "Deed of Establishment + Kemenkumham Approval",
        "Company NPWP",
        "Business domicile address",
        "Selected KBLI data"
    ],
    "per_pma_stranieri": [
        "Passport semua pemegang saham asing",
        "Rencana investasi (Investment Plan)",
        "Bukti modal disetor (paid-up capital)",
        "RPTKA (jika ada tenaga kerja asing)"
    ],
    "per_pma_stranieri_en": [
        "Passport of all foreign shareholders",
        "Investment plan",
        "Proof of paid-up capital",
        "RPTKA (if foreign workers)"
    ]
}

DOCUMENTI_PER_RISIKO = {
    "Rendah": {
        "per_operativita": [
            "Sertifikat standar industri (jika diperlukan)"
        ],
        "per_operativita_en": [
            "Industrial standard certificate (if required)"
        ]
    },
    "Menengah Rendah": {
        "per_operativita": [
            "Sertifikat standar industri",
            "Izin lokasi (jika diperlukan)"
        ],
        "per_operativita_en": [
            "Industrial standard certificate",
            "Location permit (if required)"
        ]
    },
    "Menengah": {
        "per_operativita": [
            "Dokumen lingkungan (UKL-UPL)",
            "Sertifikat K3",
            "Sertifikat standar industri",
            "Izin lokasi"
        ],
        "per_operativita_en": [
            "Environmental documents (UKL-UPL)",
            "K3 certificate",
            "Industrial standard certificate",
            "Location permit"
        ]
    },
    "Menengah Tinggi": {
        "per_operativita": [
            "Dokumen lingkungan (AMDAL)",
            "Sertifikat K3",
            "Sertifikat standar industri",
            "Izin lokasi",
            "Izin lainnya sesuai sektor"
        ],
        "per_operativita_en": [
            "Environmental documents (AMDAL)",
            "K3 certificate",
            "Industrial standard certificate",
            "Location permit",
            "Other permits according to sector"
        ]
    },
    "Tinggi": {
        "per_operativita": [
            "Dokumen lingkungan (AMDAL)",
            "Sertifikat K3",
            "Sertifikat standar industri",
            "Izin lokasi",
            "Izin khusus sektor",
            "Persetujuan dari instansi terkait"
        ],
        "per_operativita_en": [
            "Environmental documents (AMDAL)",
            "K3 certificate",
            "Industrial standard certificate",
            "Location permit",
            "Special sector permits",
            "Approval from related agencies"
        ]
    },
    "Tidak diatur": {
        "per_operativita": [
            "Sertifikat standar industri (jika diperlukan)"
        ],
        "per_operativita_en": [
            "Industrial standard certificate (if required)"
        ]
    }
}


def get_documenti_for_risk(risk_level: Optional[str]) -> Dict[str, List[str]]:
    """Ottiene documenti necessari per livello di rischio."""
    base = DOCUMENTI_BASE.copy()
    
    if not risk_level:
        risk_level = "Tidak diatur"
    
    risk_docs = DOCUMENTI_PER_RISIKO.get(risk_level, DOCUMENTI_PER_RISIKO["Tidak diatur"])
    base.update(risk_docs)
    
    return base


# Template Obblighi Post-Apertura (standard per tutti)
OBBLIGHI_POST_APERTURA = {
    "periodici": [
        {
            "obbligo": "LKPM (Laporan Kegiatan Penanaman Modal)",
            "obbligo_en": "LKPM (Investment Activity Report)",
            "frequenza": "Triwulanan",
            "frequenza_en": "Quarterly",
            "scadenza": "Akhir bulan berikutnya setelah triwulan",
            "scadenza_en": "End of month following quarter",
            "sanzione": "Peringatan, pembekuan NIB",
            "sanzione_en": "Warning, NIB suspension"
        },
        {
            "obbligo": "SPT Tahunan",
            "obbligo_en": "Annual Tax Return",
            "frequenza": "Tahunan",
            "frequenza_en": "Annual",
            "scadenza": "Sebelum 30 April",
            "scadenza_en": "Before April 30",
            "sanzione": "Denda + bunga",
            "sanzione_en": "Fine + interest"
        },
        {
            "obbligo": "Laporan Keuangan",
            "obbligo_en": "Financial Report",
            "frequenza": "Tahunan",
            "frequenza_en": "Annual",
            "scadenza": "6 bulan setelah tutup buku",
            "scadenza_en": "6 months after book closing",
            "sanzione": "Denda",
            "sanzione_en": "Fine"
        }
    ],
    "una_tantum": [
        {
            "obbligo": "Registrasi BPJS Kesehatan",
            "obbligo_en": "BPJS Health Registration",
            "quando": "Dalam 30 hari dari mulai operasional",
            "quando_en": "Within 30 days of operations start",
            "sanzione": "Denda + tidak bisa ikut tender",
            "sanzione_en": "Fine + cannot participate in tenders"
        },
        {
            "obbligo": "Registrasi BPJS Ketenagakerjaan",
            "obbligo_en": "BPJS Employment Registration",
            "quando": "Dalam 30 hari dari mulai operasional",
            "quando_en": "Within 30 days of operations start",
            "sanzione": "Denda",
            "sanzione_en": "Fine"
        }
    ]
}


# Template Warnings basati su regole
def get_warnings_for_kbli(
    pma_allowed: Optional[bool],
    pma_max_percentage: Optional[str],
    risk_level: Optional[str]
) -> List[Dict[str, str]]:
    """Genera warnings basati su regole PMA e rischio."""
    warnings = []
    
    # Warning PMA
    if pma_allowed is False:
        warnings.append({
            "tipo": "penting",
            "messaggio": "Sektor ini TERTUTUP untuk investasi asing (PMA).",
            "messaggio_en": "This sector is CLOSED to foreign investment (PMA)."
        })
    elif pma_allowed is True and pma_max_percentage and pma_max_percentage != "100%":
        warnings.append({
            "tipo": "penting",
            "messaggio": f"Investasi asing (PMA) dibatasi maksimal {pma_max_percentage}.",
            "messaggio_en": f"Foreign investment (PMA) is limited to maximum {pma_max_percentage}."
        })
    
    # Warning rischio
    if risk_level == "Tinggi":
        warnings.append({
            "tipo": "penting",
            "messaggio": "Sektor ini memiliki risiko TINGGI. Memerlukan dokumen lingkungan (AMDAL) dan izin khusus.",
            "messaggio_en": "This sector has HIGH risk. Requires environmental documents (AMDAL) and special permits."
        })
    elif risk_level == "Menengah Tinggi":
        warnings.append({
            "tipo": "penting",
            "messaggio": "Sektor ini memiliki risiko MENENGAH TINGGI. Memerlukan dokumen lingkungan dan izin tambahan.",
            "messaggio_en": "This sector has MEDIUM-HIGH risk. Requires environmental documents and additional permits."
        })
    
    return warnings


# Template Skala Usaha defaults
SKALA_USAHA_DEFAULTS = {
    "allowed_scales": ["Mikro", "Kecil", "Menengah", "Besar"],
    "mikro": {
        "max_revenue_idr": 300000000,
        "requirements": "NIB saja"
    },
    "kecil": {
        "max_revenue_idr": 2500000000,
        "requirements": "NIB saja"
    },
    "menengah": {
        "max_revenue_idr": 50000000000,
        "requirements": "NIB + Sertifikat Standar"
    },
    "besar": {
        "min_revenue_idr": 50000000000,
        "requirements": "NIB + Izin"
    }
}
