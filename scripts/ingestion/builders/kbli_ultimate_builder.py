"""
Builder che assembla payload ultimate completo per KBLI.
Combina dati arricchiti + template + traduzioni + correlazioni + FAQ.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ingestion.schemas.kbli_ultimate_schema import (
    KBLIUltimatePayload, PMAInfo, SkalaUsahaData, SkalaUsahaInfo,
    TimelineData, TimelinePhase, DocumentiNecessari, ObblighiPostApertura,
    ObbligoPeriodico, ObbligoUnaTantum, Warning, KBLICorrelato, FAQ, Metadata
)
from scripts.ingestion.templates.kbli_templates import (
    get_timeline_for_risk, get_documenti_for_risk, get_warnings_for_kbli,
    SKALA_USAHA_DEFAULTS, OBBLIGHI_POST_APERTURA
)
from scripts.ingestion.templates.kbli_faq_templates import combine_faq_templates
from scripts.ingestion.services.translation_service import get_translation_service


class KBLIUltimateBuilder:
    """Builder per payload ultimate KBLI."""
    
    def __init__(self):
        self.translation_service = get_translation_service()
    
    def build_payload(self, kbli_entry: Dict[str, Any], correlations: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Costruisce payload ultimate completo per un KBLI.
        
        Args:
            kbli_entry: Dati KBLI arricchiti
            correlations: Correlazioni KBLI (opzionale)
        
        Returns:
            Payload ultimate completo
        """
        code = kbli_entry["kode"]
        judul = kbli_entry.get("judul", "")
        judul_en = kbli_entry.get("judul_en") or self.translation_service.translate(judul)
        
        # PMA Info
        pma_info = None
        if kbli_entry.get("pma_allowed") is not None:
            pma_info = PMAInfo(
                allowed=kbli_entry.get("pma_allowed", True),
                max_percentage=kbli_entry.get("pma_max_percentage", "100%"),
                min_investment_idr=10000000000,
                min_paid_up_idr=10000000000,
                notes="Sektor terbuka untuk investasi asing" if kbli_entry.get("pma_allowed") else "Sektor tertutup untuk investasi asing",
                notes_en="Sector open to foreign investment" if kbli_entry.get("pma_allowed") else "Sector closed to foreign investment"
            )
        
        # Skala Usaha
        skala_usaha_data = None
        allowed_scales = kbli_entry.get("skala_usaha", SKALA_USAHA_DEFAULTS["allowed_scales"])
        if allowed_scales:
            skala_usaha_data = SkalaUsahaData(
                allowed_scales=allowed_scales,
                mikro=SkalaUsahaInfo(**SKALA_USAHA_DEFAULTS["mikro"]),
                kecil=SkalaUsahaInfo(**SKALA_USAHA_DEFAULTS["kecil"]),
                menengah=SkalaUsahaInfo(**SKALA_USAHA_DEFAULTS["menengah"]),
                besar=SkalaUsahaInfo(**SKALA_USAHA_DEFAULTS["besar"])
            )
        
        # Timeline
        timeline_data = None
        risk_level = kbli_entry.get("tingkat_risiko")
        if risk_level:
            timeline_range = get_timeline_for_risk(risk_level)
            timeline_data = TimelineData(
                totale_stimato_hari=f"{timeline_range['min']}-{timeline_range['max']}",
                fasi=[
                    TimelinePhase(
                        fase=1,
                        nama="Pembentukan PT",
                        nama_en="PT Establishment",
                        durata_hari="7-14",
                        deskripsi="Akta pendirian, SK Kemenkumham",
                        deskripsi_en="Deed of establishment, Kemenkumham approval"
                    ),
                    TimelinePhase(
                        fase=2,
                        nama="NIB via OSS",
                        nama_en="NIB via OSS",
                        durata_hari="1-3",
                        deskripsi="Registrasi online di OSS RBA",
                        deskripsi_en="Online registration on OSS RBA"
                    )
                ]
            )
        
        # Documenti
        documenti_data = None
        if risk_level:
            doc_dict = get_documenti_for_risk(risk_level)
            documenti_data = DocumentiNecessari(**doc_dict)
        
        # Obblighi post
        obblighi_data = ObblighiPostApertura(
            periodici=[
                ObbligoPeriodico(**ob) for ob in OBBLIGHI_POST_APERTURA["periodici"]
            ],
            una_tantum=[
                ObbligoUnaTantum(**ob) for ob in OBBLIGHI_POST_APERTURA["una_tantum"]
            ]
        )
        
        # Warnings
        warnings_list = get_warnings_for_kbli(
            kbli_entry.get("pma_allowed"),
            kbli_entry.get("pma_max_percentage"),
            risk_level
        )
        warnings = [Warning(**w) for w in warnings_list] if warnings_list else None
        
        # KBLI Correlati
        kbli_correlati = None
        if correlations and code in correlations:
            corr_data = correlations[code]
            kbli_correlati = []
            for rel_type, codes in corr_data.items():
                for corr_code in codes[:2]:  # Max 2 per tipo
                    kbli_correlati.append(KBLICorrelato(
                        kode=corr_code,
                        relasi=rel_type,
                        relasi_en=rel_type.replace("_", " ").title(),
                        catatan=f"KBLI {rel_type}",
                        catatan_en=f"KBLI {rel_type}"
                    ))
        
        # FAQ
        faq_list = combine_faq_templates(
            kbli_entry.get("pma_allowed"),
            kbli_entry.get("pma_max_percentage"),
            allowed_scales,
            risk_level,
            len(kbli_entry.get("pb_umku", [])) > 0,
            len(kbli_entry.get("pb_umku", []))
        )
        faq = [FAQ(**f) for f in faq_list] if faq_list else None
        
        # Metadata
        metadata = Metadata(
            version="2025",
            source_primary=kbli_entry.get("source", "BPS_7_2025"),
            source_pma="Perpres_10_2021" if pma_info else None,
            extraction_date=datetime.now().isoformat(),
            last_verified=datetime.now().isoformat(),
            data_quality=kbli_entry.get("data_quality", "minimal"),
            confidence_score=0.95 if kbli_entry.get("data_quality") == "complete" else 0.7
        )
        
        # Costruisci payload
        payload_dict = {
            "kode": code,
            "judul": judul,
            "judul_en": judul_en,
            "sektor": kbli_entry.get("sektor"),
            "tingkat_risiko": risk_level,
            "risk_level_en": self._get_risk_level_en(risk_level),
            "pma": pma_info.dict() if pma_info else None,
            "skala_usaha": skala_usaha_data.dict() if skala_usaha_data else None,
            "ruang_lingkup": kbli_entry.get("ruang_lingkup"),
            "ruang_lingkup_en": self.translation_service.translate(kbli_entry.get("ruang_lingkup", "")) if kbli_entry.get("ruang_lingkup") else None,
            "timeline": timeline_data.dict() if timeline_data else None,
            "documenti_necessari": documenti_data.dict() if documenti_data else None,
            "obblighi_post_apertura": obblighi_data.dict(),
            "warnings": [w.dict() for w in warnings] if warnings else None,
            "kbli_correlati": [k.dict() for k in kbli_correlati] if kbli_correlati else None,
            "faq": [f.dict() for f in faq] if faq else None,
            "metadata": metadata.dict()
        }
        
        return payload_dict
    
    def _get_risk_level_en(self, risk_level: Optional[str]) -> Optional[str]:
        """Converte risk level ID → EN."""
        if not risk_level:
            return None
        risk_map = {
            "Rendah": "Low",
            "Menengah Rendah": "Low-Medium",
            "Menengah": "Medium",
            "Menengah Tinggi": "Medium-High",
            "Tinggi": "High",
            "Tidak diatur": "Not regulated"
        }
        return risk_map.get(risk_level, risk_level)


def build_all_payloads():
    """Costruisce payload ultimate per tutti i KBLI."""
    DATA_DIR = PROJECT_ROOT / "reports" / "kbli_extraction"
    
    # Carica dati arricchiti
    enriched_file = DATA_DIR / "kbli_enriched_master_list.json"
    with open(enriched_file) as f:
        data = json.load(f)
    
    kbli_data = data.get("kbli_data", {})
    
    # Carica correlazioni
    corr_file = DATA_DIR / "kbli_correlations.json"
    correlations = {}
    if corr_file.exists():
        with open(corr_file) as f:
            corr_data = json.load(f)
            correlations = corr_data.get("correlations", {})
    
    # Build payloads
    builder = KBLIUltimateBuilder()
    payloads = {}
    
    print(f"🔄 Building payloads for {len(kbli_data)} KBLI...")
    for i, (code, entry) in enumerate(kbli_data.items(), 1):
        try:
            payload = builder.build_payload(entry, correlations)
            payloads[code] = payload
            if i % 100 == 0:
                print(f"   Progress: {i}/{len(kbli_data)}")
        except Exception as e:
            print(f"   ⚠️  Error building {code}: {e}")
    
    # Salva
    output_data = {
        "metadata": {
            "build_date": datetime.now().isoformat(),
            "total_payloads": len(payloads)
        },
        "payloads": payloads
    }
    
    output_file = DATA_DIR / f"kbli_ultimate_payloads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Built {len(payloads)} payloads")
    print(f"📁 Saved: {output_file.name}")
    return output_file


if __name__ == "__main__":
    build_all_payloads()
