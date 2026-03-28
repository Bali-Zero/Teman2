import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class KBLIEye:
    """
    KBLI EYE - Punto fisso deterministico per l'intelligence normativa.
    Centralizza la logica di validazione per evitare frammentazione nei router o agenti.
    """

    # 9 codici KBLI citati esplicitamente nella Surat Gubernur Bali
    # B.27.000/642/PM/DPMPTSP del 28 Gennaio 2026 (Wayan Koster)
    # Motivo: usati da PMA per ottenere izin tinggal senza vera attività
    BALI_GOV_LETTER_CODES: set = {
        "68111",  # Real Estate yang Dimiliki Sendiri atau Disewa
        "70209",  # Aktivitas Konsultasi Manajemen Lainnya
        "77311",  # Penyewaan Motor Tanpa Hak Opsi
        "77100",  # Penyewaan Mobil, Bus, Truk dan Sejenisnya
        "79121",  # Aktivitas Biro Perjalanan Wisata
        "47711",  # Perdagangan Eceran Pakaian
        "47511",  # Perdagangan Eceran Tekstil
        "47249",  # Perdagangan Eceran Makanan Lainnya
        "47991",  # Perdagangan Eceran Keliling Komoditi Makanan
    }

    # 4 codici KBLI sotto moratorium INGUB 6/2025 (toko modern berjejaring)
    BALI_MORATORIUM_RETAIL: set = {
        "47111",
        "47112",
        "47113",
        "47191",
    }

    def __init__(self, db_path: str = "source_documents/KBLI_2025_FINAL_CLEAN.json") -> None:
        # Risolviamo il path rispetto alla root del progetto
        self.db_path = Path(db_path)
        self.data: list = []
        self._load_database()

    def _load_database(self) -> Any:
        if not self.db_path.exists():
            # Prova path alternativo se eseguito da diverse cartelle
            alt_path = Path("apps/backend-rag") / self.db_path
            if alt_path.exists():
                self.db_path = alt_path
            else:
                return  # Database non caricato, get_decision darà errore

        with open(self.db_path) as f:
            content = json.load(f)
            if isinstance(content, dict) and "data" in content:
                self.data = content["data"]
            else:
                self.data = content  # Backup se fosse già una lista

    def get_decision(self, code: str, is_pma: bool = True, location: str = "Bali") -> dict:
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
        primary_skala = per_skala[0] if isinstance(per_skala, list) and len(per_skala) > 0 else {}

        oss_risk = primary_skala.get("kategori_risiko", "Unknown")

        # 3. Matrice di Decisione (Determinismo puro)
        resolved_code = kbli["kode_kbli_2025"]

        if is_pma and not is_open_pma:
            state = "REJECTED"
            reason = "PERPRES_10_2021_RESERVATION"  # DNI list
        elif is_pma and location == "Bali" and resolved_code in self.BALI_GOV_LETTER_CODES:
            # 9 codici citati nella Surat Gubernur 28 Gen 2026
            state = "WARNING"
            reason = "BALI_GOV_LETTER_9_CODES"
        elif location == "Bali" and resolved_code in self.BALI_MORATORIUM_RETAIL:
            # Moratorium toko modern berjejaring (INGUB 6/2025)
            state = "WARNING"
            reason = "BALI_INGUB_6_2025_MORATORIUM"
        else:
            state = "APPROVED"
            reason = "STANDARD_COMPLIANCE"

        # 4. Payload strutturato per Dashboard e WhatsApp
        return {
            "kbli_2025": kbli["kode_kbli_2025"],
            "kbli_2020_ref": kbli.get("kbli_2020_source"),
            "title": kbli["judul"],
            "audit": {
                "state": state,  # APPROVED | WARNING | REJECTED
                "reason_code": reason,  # Codice univoco per la logica
                "oss_risk": oss_risk,
                "authority": primary_skala.get("kewenangan", "Unknown"),
            },
            "compliance_stack": primary_skala.get("kewajiban", []),
            "pma_logic": {
                "max_foreign_ownership": 100 if is_open_pma else 0,
                "is_umkm_reserved": not is_open_pma,
            },
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

    def _resolve_kbli(self, code: str) -> dict | None:
        """Cerca il codice 2025 anche se viene fornito un codice 2020."""
        # Sanitizzazione input
        clean_code = str(code).strip()
        for item in self.data:
            if (
                item.get("kode_kbli_2025") == clean_code
                or item.get("kbli_2020_source") == clean_code
            ):
                return item
        return None


if __name__ == "__main__":
    # Test rapido
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    eye = KBLIEye()
    result = eye.get_decision("55203")
    logger.info(f"KBLI Eye test result: {json.dumps(result, indent=2)}")
