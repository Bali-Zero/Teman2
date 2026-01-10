"""
Schema completo per il payload ultimate KBLI.
Definisce la struttura completa del payload con validazione Pydantic.
Supporto bilingue (ID + EN) obbligatorio.
"""

from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class RiskLevel(str, Enum):
    """Livelli di rischio."""
    RENDAH = "Rendah"
    MENENGAH_RENDAH = "Menengah Rendah"
    MENENGAH = "Menengah"
    MENENGAH_TINGGI = "Menengah Tinggi"
    TINGGI = "Tinggi"
    TIDAK_DIATUR = "Tidak diatur"


class SkalaUsaha(str, Enum):
    """Scale di business."""
    MIKRO = "Mikro"
    KECIL = "Kecil"
    MENENGAH = "Menengah"
    BESAR = "Besar"


class WarningType(str, Enum):
    """Tipi di warning."""
    PENTING = "penting"
    SARAN = "saran"
    INFO = "info"


class RelasiType(str, Enum):
    """Tipi di relazione KBLI."""
    SERUPA = "serupa"
    KOMPLEMENTER = "komplementer"
    SUPPLY_CHAIN = "supply_chain"
    SUB_KATEGORI = "sub_kategori"


# Modelli per strutture annidate

class PMAInfo(BaseModel):
    """Informazioni PMA (Penanaman Modal Asing)."""
    allowed: bool
    max_percentage: str = Field(..., description="Es: '100%', '67%', '0%'")
    min_investment_idr: int = Field(default=10000000000, description="IDR 10 miliar default")
    min_paid_up_idr: int = Field(default=10000000000, description="IDR 10 miliar default")
    restrictions: Optional[str] = None
    restrictions_en: Optional[str] = None
    notes: Optional[str] = None
    notes_en: Optional[str] = None
    source: str = Field(default="Perpres_10_2021", description="Fonte dati PMA")


class SkalaUsahaInfo(BaseModel):
    """Informazioni per ogni scala usaha."""
    max_revenue_idr: Optional[int] = None
    min_revenue_idr: Optional[int] = None
    requirements: str


class SkalaUsahaData(BaseModel):
    """Dati skala usaha."""
    allowed_scales: List[SkalaUsaha]
    mikro: Optional[SkalaUsahaInfo] = None
    kecil: Optional[SkalaUsahaInfo] = None
    menengah: Optional[SkalaUsahaInfo] = None
    besar: Optional[SkalaUsahaInfo] = None


class PBUMKUItem(BaseModel):
    """Item PB UMKU."""
    kode: str
    nama: str
    nama_en: str
    obbligatorio: bool
    ketika: str
    ketika_en: str
    tempo_stimato_hari: Optional[int] = None


class TimelinePhase(BaseModel):
    """Fase della timeline."""
    fase: int
    nama: str
    nama_en: str
    durata_hari: str
    deskripsi: str
    deskripsi_en: str


class TimelineData(BaseModel):
    """Dati timeline."""
    totale_stimato_hari: str
    fasi: List[TimelinePhase]


class DocumentiNecessari(BaseModel):
    """Documenti necessari."""
    per_costituzione_pt: List[str]
    per_costituzione_pt_en: List[str]
    per_nib: List[str]
    per_nib_en: List[str]
    per_operativita: List[str]
    per_operativita_en: List[str]
    per_pma_stranieri: Optional[List[str]] = None
    per_pma_stranieri_en: Optional[List[str]] = None


class ObbligoPeriodico(BaseModel):
    """Obbligo periodico."""
    obbligo: str
    obbligo_en: str
    frequenza: str
    frequenza_en: str
    scadenza: str
    scadenza_en: str
    sanzione: str
    sanzione_en: str


class ObbligoUnaTantum(BaseModel):
    """Obbligo una tantum."""
    obbligo: str
    obbligo_en: str
    quando: str
    quando_en: str
    sanzione: str
    sanzione_en: str


class ObblighiPostApertura(BaseModel):
    """Obblighi post-apertura."""
    periodici: List[ObbligoPeriodico]
    una_tantum: List[ObbligoUnaTantum]


class Warning(BaseModel):
    """Warning o consiglio."""
    tipo: WarningType
    messaggio: str
    messaggio_en: str


class KBLICorrelato(BaseModel):
    """KBLI correlato."""
    kode: str
    relasi: RelasiType
    relasi_en: str
    catatan: str
    catatan_en: str


class FAQ(BaseModel):
    """FAQ."""
    pertanyaan: str
    pertanyaan_en: str
    jawaban: str
    jawaban_en: str


class Metadata(BaseModel):
    """Metadata tecnici."""
    version: str = "2025"
    source_primary: str
    source_pma: Optional[str] = None
    extraction_date: str
    last_verified: str
    data_quality: Literal["complete", "partial", "minimal"]
    confidence_score: float = Field(ge=0.0, le=1.0)


# Schema principale

class KBLIUltimatePayload(BaseModel):
    """Payload ultimate completo per un KBLI."""
    
    # Identità base
    kode: str = Field(..., pattern=r"^\d{5}$", description="Codice KBLI a 5 cifre")
    judul: str
    judul_en: str
    sektor: Optional[str] = None
    sub_sektor: Optional[str] = None
    
    # Descrizione umana
    deskripsi_singkat: Optional[str] = None
    deskripsi_singkat_en: Optional[str] = None
    contesto_utente: Optional[str] = None
    contesto_utente_en: Optional[str] = None
    
    # Classificazione rischio
    tingkat_risiko: Optional[RiskLevel] = None
    risk_level_en: Optional[str] = None
    risk_explanation: Optional[str] = None
    risk_explanation_en: Optional[str] = None
    perizinan_dasar: Optional[str] = None
    
    # PMA
    pma: Optional[PMAInfo] = None
    
    # Skala usaha
    skala_usaha: Optional[SkalaUsahaData] = None
    
    # Ruang lingkup
    ruang_lingkup: Optional[str] = None
    ruang_lingkup_en: Optional[str] = None
    attivita_incluse: Optional[List[str]] = None
    attivita_incluse_en: Optional[List[str]] = None
    attivita_escluse: Optional[List[str]] = None
    attivita_escluse_en: Optional[List[str]] = None
    
    # PB UMKU
    pb_umku: Optional[List[PBUMKUItem]] = None
    
    # Timeline
    timeline: Optional[TimelineData] = None
    
    # Documenti necessari
    documenti_necessari: Optional[DocumentiNecessari] = None
    
    # Obblighi post-apertura
    obblighi_post_apertura: Optional[ObblighiPostApertura] = None
    
    # Warnings
    warnings: Optional[List[Warning]] = None
    
    # KBLI correlati
    kbli_correlati: Optional[List[KBLICorrelato]] = None
    
    # FAQ
    faq: Optional[List[FAQ]] = None
    
    # Metadata
    metadata: Metadata
    
    @validator("risk_level_en", always=True)
    def set_risk_level_en(cls, v, values):
        """Imposta risk_level_en basato su tingkat_risiko."""
        if "tingkat_risiko" in values and values["tingkat_risiko"]:
            risk_map = {
                RiskLevel.RENDAH: "Low",
                RiskLevel.MENENGAH_RENDAH: "Low-Medium",
                RiskLevel.MENENGAH: "Medium",
                RiskLevel.MENENGAH_TINGGI: "Medium-High",
                RiskLevel.TINGGI: "High",
                RiskLevel.TIDAK_DIATUR: "Not regulated"
            }
            return risk_map.get(values["tingkat_risiko"], "Unknown")
        return v
    
    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "kode": "22220",
                "judul": "Industri Barang dari Plastik untuk Pengemasan",
                "judul_en": "Plastic Packaging Manufacturing Industry",
                "tingkat_risiko": "Rendah",
                "pma": {
                    "allowed": True,
                    "max_percentage": "100%"
                }
            }
        }


def validate_payload(payload_dict: Dict[str, Any]) -> tuple[bool, Optional[str], Optional[KBLIUltimatePayload]]:
    """
    Valida un payload dictionary contro lo schema.
    
    Returns:
        (is_valid, error_message, validated_payload)
    """
    try:
        validated = KBLIUltimatePayload(**payload_dict)
        return True, None, validated
    except Exception as e:
        return False, str(e), None
