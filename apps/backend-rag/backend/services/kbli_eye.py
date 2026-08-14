import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.kbli_pma_disclosure import disclose_pma

logger = logging.getLogger(__name__)


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

    # Valori di `pma_kondisi` che dichiarano una RISERVA a favore di K-UMKM.
    # "Kemitraan dengan UMKM/Koperasi" è deliberatamente ASSENTE: un obbligo di
    # PARTNERSHIP non è una riserva, e confondere le due cose è esattamente il
    # modo in cui la vecchia derivazione `not is_open_pma` etichettava 68 codici
    # come "riservati alle UMKM" senza che il dato lo dicesse da nessuna parte.
    UMKM_RESERVED_KONDISI: frozenset = frozenset({"UMKM only"})

    # Nome della colonna del lampiran Perpres 10/2021 che alloca un'attività a
    # cooperative/UMKM. Token strutturato in maiuscolo, non prosa libera.
    UMKM_ALLOCATION_MARKER: str = "DIALOKASIKAN"

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
                # Un `return` NUDO qui ha tenuto questo organo morto e MUTO in
                # produzione: il dataset non entra nell'immagine Docker (il
                # Dockerfile copia backend/scripts/training-data, mai `data/`),
                # quindi ogni get_decision() risponde DATABASE_NOT_LOADED e i
                # due endpoint consumatori degradano il blocco KBLI a
                # `state: "ERROR"` senza che nulla lo dica. Il rifiuto va
                # LOGGATO: un fallimento silenzioso non è un fallimento visto.
                logger.error(
                    "KBLIEye: dataset non trovato (%s né %s) — get_decision() "
                    "risponderà DATABASE_NOT_LOADED a ogni codice. cwd=%s",
                    self.db_path,
                    alt_path,
                    Path.cwd(),
                )
                return

        with open(self.db_path) as f:
            content = json.load(f)
            if isinstance(content, dict) and "data" in content:
                self.data = content["data"]
            else:
                self.data = content  # Backup se fosse già una lista

    @staticmethod
    def _foreign_cap(kbli: dict) -> tuple[int | None, str | None, bool]:
        """Risolve il tetto di proprietà straniera (%) per un codice.

        Il tetto NON è derivabile da `pma_status` da solo: TERBATAS copre 0%,
        49%, 100% e un regime "special" senza percentuale. Il dataset porta già
        la cifra aggiudicata per codice (`pma_max_asing`, con
        `pma_official_basis` che cita il lampiran Perpres 10/2021) — si legge
        quella invece di ri-derivare un binario che il caso di mezzo non sa
        esprimere.

        Ritorna `(cap, basis, verified)`. `cap is None` significa "non possiamo
        dichiarare una cifra": è un gap dichiarato, mai uno 0 silenzioso.
        """
        disclosed = disclose_pma(kbli)
        if disclosed["pma_verification_status"] != "located":
            return None, None, False

        raw = disclosed["pma_max_asing"]
        basis = kbli.get("pma_cap_note") or disclosed["pma_official_basis"]
        verified = bool(disclosed["pma_cap_verified"])

        # `bool` è sottoclasse di `int` in Python: va escluso PRIMA del check.
        if isinstance(raw, bool):
            raw = None
        if isinstance(raw, int):
            return raw, basis, verified
        if isinstance(raw, str) and raw.strip().isdigit():
            return int(raw.strip()), basis, verified
        if raw is not None:
            # es. "special": regime condizionato, nessuna percentuale sulla riga.
            return None, basis, verified

        # Nessuna cifra aggiudicata sul record: si ricade sullo status, che è
        # inequivocabile SOLO ai due estremi.
        status = disclosed["pma_status"]
        if status == "TERBUKA":
            return 100, "Derived from pma_status=TERBUKA (no per-code cap on record)", False
        if status == "TERTUTUP":
            return 0, "Derived from pma_status=TERTUTUP (no per-code cap on record)", False
        return None, None, False

    @classmethod
    def _umkm_reserved(cls, kbli: dict) -> bool | None:
        """`True` solo se il dato NOMINA una riserva K-UMKM; `None` = ignoto.

        Un codice chiuso agli stranieri lo è per molte ragioni (difesa,
        ambiente, cultura, cabotaggio…): dedurne "riservato alle UMKM" è
        un'asserzione plausibile-ma-non-fondata. Meglio un gap dichiarato.
        """
        disclosed = disclose_pma(kbli)
        if disclosed["pma_verification_status"] != "located":
            return None

        kondisi = (disclosed["pma_kondisi"] or "").strip()
        if kondisi in cls.UMKM_RESERVED_KONDISI:
            return True
        if cls.UMKM_ALLOCATION_MARKER in (disclosed["pma_official_basis"] or ""):
            return True
        if disclosed["pma_status"] == "TERBUKA":
            return False
        return None

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
        disclosed = disclose_pma(kbli)
        pma_verified = disclosed["pma_verification_status"] == "located"
        is_open_pma = disclosed["pma_status"] == "TERBUKA"
        cap, cap_basis, cap_verified = self._foreign_cap(kbli)

        # Gestione dati per_skala (può essere una lista o un dict a seconda del cleanup)
        per_skala = kbli.get("per_skala", [{}])
        primary_skala = per_skala[0] if isinstance(per_skala, list) and len(per_skala) > 0 else {}

        oss_risk = primary_skala.get("kategori_risiko", "Unknown")

        # 3. Matrice di Decisione (Determinismo puro)
        resolved_code = kbli["kode_kbli_2025"]

        if is_pma and location == "Bali" and resolved_code in self.BALI_GOV_LETTER_CODES:
            # 9 codici citati nella Surat Gubernur 28 Gen 2026. This local
            # warning is independent of whether the national PMA tuple is
            # located, so it remains actionable during a national gap.
            state = "WARNING"
            reason = "BALI_GOV_LETTER_9_CODES"
        elif location == "Bali" and resolved_code in self.BALI_MORATORIUM_RETAIL:
            # Moratorium toko modern berjejaring (INGUB 6/2025)
            state = "WARNING"
            reason = "BALI_INGUB_6_2025_MORATORIUM"
        elif is_pma and not pma_verified:
            state = "WARNING"
            reason = "PMA_NOT_VERIFIED"
        elif is_pma and cap == 0:
            state = "REJECTED"
            reason = "PERPRES_10_2021_RESERVATION"  # DNI list — 0% asing
        elif is_pma and not is_open_pma:
            # Limitato, NON chiuso. Un PMA può salire fino a `cap` (o deve
            # soddisfare una condizione non-percentuale). WARNING, mai
            # REJECTED: il vecchio binario trasformava una quota lecita del
            # 49% in un rifiuto.
            state = "WARNING"
            reason = "PERPRES_10_2021_FOREIGN_CAP"
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
                # int | None — None = nessuna cifra dichiarabile (gap onesto)
                "max_foreign_ownership": cap,
                "max_foreign_ownership_basis": cap_basis,
                "max_foreign_ownership_verified": cap_verified,
                "pma_status": disclosed["pma_status"],
                "pma_verification_status": disclosed["pma_verification_status"],
                "pma_official_basis": disclosed["pma_official_basis"],
                "pma_source_vintage": disclosed["pma_source_vintage"],
                # bool | None — None = chiuso/limitato per un motivo che il
                # record non dichiara: NON assumere che sia una riserva UMKM
                "is_umkm_reserved": self._umkm_reserved(kbli),
                # verbatim: "Kemitraan dengan ..." è una condizione, non un tetto
                "pma_condition": disclosed["pma_kondisi"],
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
