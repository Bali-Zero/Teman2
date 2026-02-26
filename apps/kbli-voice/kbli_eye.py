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
        self.db_path = Path(db_path)
        self.data: List[Dict] = []
        self._index: Dict[str, Dict] = {}
        self._pp28_index: Dict[str, Dict] = {}
        self._load_database()

    def _load_database(self) -> None:
        if not self.db_path.exists():
            alt_path = Path("apps/backend-rag") / self.db_path
            if alt_path.exists():
                self.db_path = alt_path
            else:
                return

        with open(self.db_path, "r") as f:
            content = json.load(f)
            if isinstance(content, dict) and "data" in content:
                self.data = content["data"]
            else:
                self.data = content

        # Indicizza per lookup O(1) invece di scan lineare O(n)
        for item in self.data:
            code = item.get("kode_kbli_2025", "")
            if code:
                self._index[code] = item
            for pp28_code in item.get("pp28_sources", []):
                if isinstance(pp28_code, str):
                    self._pp28_index[pp28_code] = item

    def get_decision(self, code: str, is_pma: bool = True, location: str = "Bali",
                     skala: Optional[str] = None) -> Dict:
        """
        Esegue l'audit deterministico. Restituisce uno STATO, non solo testo.

        Args:
            code: Codice KBLI 2025 (o vecchio PP28/2020)
            is_pma: True se l'investitore è straniero (PMA), False se locale
            location: Provincia/città dell'attività
            skala: Scala d'impresa target — "Mikro", "Kecil", "Menengah", "Besar".
                   Default: "Besar" per PMA, "Mikro" per locale.
        """
        if not self.data:
            return {"state": "ERROR", "reason_code": "DATABASE_NOT_LOADED"}

        # 1. Risoluzione Codice (Mapping forzato al 2025)
        kbli = self._resolve_kbli(code)
        if not kbli:
            return {"state": "ERROR", "reason_code": "CODE_NOT_FOUND"}

        # 2. Parametri strutturali dal JSON
        pma_status = kbli.get("pma_status", "TERBUKA")
        pma_max_asing = kbli.get("pma_max_asing", 100)
        pma_kondisi = kbli.get("pma_kondisi", "")
        pma_nota = kbli.get("pma_nota", "")
        is_priority = kbli.get("pma_prioritas", False)

        # 3. Selezione skala appropriata
        if skala is None:
            skala = "Besar" if is_pma else "Mikro"
        primary_skala = self._select_skala(kbli, skala)

        oss_risk = primary_skala.get("kategori_risiko", "Unknown")
        is_low_risk = oss_risk in ["Rendah", "Menengah Rendah"]
        has_licensing_data = bool(kbli.get("per_skala"))

        # 4. Matrice di Decisione (Determinismo puro, 3 stati PMA)
        if is_pma:
            state, reason = self._evaluate_pma(
                pma_status, location, is_low_risk, is_priority
            )
        else:
            # Investitore locale — nessuna restrizione PMA
            if location == "Bali" and is_low_risk:
                state = "WARNING"
                reason = "BALI_GOV_RESTRICTION_2026"
            else:
                state = "APPROVED"
                reason = "STANDARD_COMPLIANCE"

        # 5. Payload strutturato per Dashboard e WhatsApp
        result: Dict = {
            "kbli_2025": kbli["kode_kbli_2025"],
            "pp28_sources": kbli.get("pp28_sources", []),
            "title": kbli["judul"],
            "audit": {
                "state": state,           # APPROVED | RESTRICTED | WARNING | REJECTED
                "reason_code": reason,
                "oss_risk": oss_risk,
                "authority": primary_skala.get("kewenangan", "Unknown"),
                "perizinan": primary_skala.get("perizinan", "Unknown"),
                "jangka_waktu": primary_skala.get("jangka_waktu", "Unknown"),
            },
            "compliance_stack": primary_skala.get("kewajiban", []),
            "persyaratan": primary_skala.get("persyaratan", []),
            "pma_logic": {
                "pma_status": pma_status,
                "max_foreign_ownership": pma_max_asing if isinstance(pma_max_asing, (int, float)) else 0,
                "kondisi": pma_kondisi,
                "nota": pma_nota,
                "is_priority_sector": is_priority,
            },
            "skala_selected": skala,
            "has_licensing_data": has_licensing_data,
            "timestamp": datetime.now().isoformat()
        }

        # 6. Sanksi (se disponibili)
        sanksi = {}
        for key in ["sanksi_peringatan", "sanksi_denda", "sanksi_penghentian", "sanksi_pencabutan"]:
            val = primary_skala.get(key)
            if val:
                sanksi[key] = val
        if sanksi:
            result["sanksi"] = sanksi

        return result

    def _evaluate_pma(self, pma_status: str, location: str,
                      is_low_risk: bool, is_priority: bool) -> tuple:
        """Matrice decisionale PMA a 3 stati."""
        if pma_status == "TERTUTUP":
            return ("REJECTED", "PMA_CLOSED_SECTOR")

        if pma_status == "TERBATAS":
            # Aperto con condizioni — non rifiutato, ma vincolato
            if location == "Bali" and is_low_risk:
                return ("RESTRICTED", "PMA_CONDITIONAL_BALI_RESTRICTION")
            return ("RESTRICTED", "PMA_CONDITIONAL")

        # TERBUKA — aperto al 100%
        if location == "Bali" and is_low_risk and not is_priority:
            return ("WARNING", "BALI_GOV_RESTRICTION_2026")

        return ("APPROVED", "STANDARD_COMPLIANCE")

    def _select_skala(self, kbli: Dict, target_skala: str) -> Dict:
        """Seleziona la entry per_skala più appropriata per la scala target."""
        per_skala = kbli.get("per_skala", [])
        if not per_skala:
            return {}
        if not isinstance(per_skala, list):
            return {}

        # Match esatto sulla scala richiesta
        for entry in per_skala:
            skala_list = entry.get("skala_usaha", [])
            if isinstance(skala_list, list) and target_skala in skala_list:
                return entry

        # Fallback: scala più grande disponibile (per PMA è la più rilevante)
        priority = ["Besar", "Menengah", "Kecil", "Mikro"]
        for p in priority:
            for entry in per_skala:
                skala_list = entry.get("skala_usaha", [])
                if isinstance(skala_list, list) and p in skala_list:
                    return entry

        # Ultimo fallback: prima entry
        return per_skala[0]

    def _resolve_kbli(self, code: str) -> Optional[Dict]:
        """Cerca il codice 2025 anche se viene fornito un vecchio codice PP28/2020."""
        clean_code = str(code).strip()
        # O(1) lookup sull'indice
        result = self._index.get(clean_code)
        if result:
            return result
        return self._pp28_index.get(clean_code)

    def batch_audit(self, codes: List[str], is_pma: bool = True,
                    location: str = "Bali") -> List[Dict]:
        """Audit batch per più codici KBLI (es. PT con 5 codici)."""
        return [self.get_decision(code, is_pma, location) for code in codes]

    def get_all_by_status(self, pma_status: str) -> List[str]:
        """Restituisce tutti i codici con un dato pma_status."""
        return [
            d["kode_kbli_2025"]
            for d in self.data
            if d.get("pma_status") == pma_status
        ]

if __name__ == "__main__":
    eye = KBLIEye()

    # Test: TERBUKA standard
    print("=== TERBUKA (55203 - Accommodation) ===")
    print(json.dumps(eye.get_decision("55203"), indent=2))

    # Test: TERTUTUP
    tertutup = eye.get_all_by_status("TERTUTUP")
    if tertutup:
        print(f"\n=== TERTUTUP ({tertutup[0]}) ===")
        print(json.dumps(eye.get_decision(tertutup[0]), indent=2))

    # Test: TERBATAS
    terbatas = eye.get_all_by_status("TERBATAS")
    if terbatas:
        print(f"\n=== TERBATAS ({terbatas[0]}) ===")
        print(json.dumps(eye.get_decision(terbatas[0]), indent=2))

    # Test: investitore locale
    print("\n=== LOCAL investor (55203) ===")
    print(json.dumps(eye.get_decision("55203", is_pma=False), indent=2))
