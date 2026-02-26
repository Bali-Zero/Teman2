import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

class KBLIEye:
    """
    KBLI EYE - Punto fisso deterministico per l'intelligence normativa.
    Centralizza la logica di validazione per evitare frammentazione nei router o agenti.
    """
    
    def __init__(self, db_path: str = "source_documents/KBLI_2025_FINAL_CLEAN.json"):
        # Risolviamo il path rispetto alla root del progetto
        self.db_path = Path(db_path)
        self.data = []
        self._load_database()

    def _load_database(self):
        if not self.db_path.exists():
            # Prova path alternativo se eseguito da diverse cartelle
            alt_path = Path("apps/backend-rag") / self.db_path
            if alt_path.exists():
                self.db_path = alt_path
            else:
                return # Database non caricato, get_decision darà errore
        
        with open(self.db_path, "r") as f:
            content = json.load(f)
            if isinstance(content, dict) and "data" in content:
                self.data = content["data"]
            else:
                self.data = content # Backup se fosse già una lista

    def get_decision(self, code: str, is_pma: bool = True, location: str = "Bali") -> Dict:
        """
        Esegue l'audit deterministico. Restituisce uno STATO, non solo testo.
        """
        if not self.data:
            return {"state": "ERROR", "reason_code": "DATABASE_NOT_LOADED"}

        # 1. Risoluzione Codice (Mapping forzato al 2025)
        kbli = self._resolve_kbli(code)
        if not kbli:
            return {"state": "ERROR", "reason_code": "CODE_NOT_FOUND"}

        # 2. Parametri di input per la matrice
        is_open_pma = kbli.get("pma_status") == "TERBUKA"
        
        # Gestione dati per_skala (può essere una lista o un dict a seconda del cleanup)
        per_skala = kbli.get("per_skala", [{}])
        if isinstance(per_skala, list) and len(per_skala) > 0:
            primary_skala = per_skala[0]
        else:
            primary_skala = {}

        oss_risk = primary_skala.get("kategori_risiko", "Unknown")
        is_low_risk = oss_risk in ["Rendah", "Menengah Rendah"]
        
        # 3. Matrice di Decisione (Determinismo puro)
        if is_pma and not is_open_pma:
            state = "REJECTED"
            reason = "PERPRES_10_2021_RESERVATION" # La famosa "V" della foto
        elif is_pma and location == "Bali" and is_low_risk:
            state = "WARNING"
            reason = "BALI_GOV_RESTRICTION_2026"  # Lettera 28 Gen 2026
        else:
            state = "APPROVED"
            reason = "STANDARD_COMPLIANCE"

        # 4. Payload strutturato per Dashboard e WhatsApp
        return {
            "kbli_2025": kbli["kode_kbli_2025"],
            "kbli_2020_ref": kbli.get("kbli_2020_source"),
            "title": kbli["judul"],
            "audit": {
                "state": state,         # APPROVED | WARNING | REJECTED
                "reason_code": reason,  # Codice univoco per la logica
                "oss_risk": oss_risk,
                "authority": primary_skala.get("kewenangan", "Unknown")
            },
            "compliance_stack": primary_skala.get("kewajiban", []),
            "pma_logic": {
                "max_foreign_ownership": 100 if is_open_pma else 0,
                "is_umkm_reserved": not is_open_pma
            },
            "timestamp": datetime.now().isoformat()
        }

    def _resolve_kbli(self, code: str) -> Optional[Dict]:
        """Cerca il codice 2025 anche se viene fornito un codice 2020."""
        # Sanitizzazione input
        clean_code = str(code).strip()
        for item in self.data:
            if item.get("kode_kbli_2025") == clean_code or item.get("kbli_2020_source") == clean_code:
                return item
        return None

if __name__ == "__main__":
    # Test rapido
    eye = KBLIEye()
    print(json.dumps(eye.get_decision("55203"), indent=2))
