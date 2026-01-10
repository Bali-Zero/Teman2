#!/usr/bin/env python3
"""
Estrazione KBLI da PDF multipli per verifica compliance Qdrant

Estrae KBLI da:
- PP Nomor 28 Tahun 2025 (1).pdf
- peraturan-bps-no-7-tahun-2025.pdf
- INGUB-6-TAHUN-2025-PENGHENTIAN-SEMENTARA-PEMBERIAN-IZIN-TOKO-MODERN-BERJEJARING.pdf

Output: JSON strutturati per confronto con Qdrant
"""

import os
import re
import json
import sys
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

try:
    import pypdf
except ImportError:
    from PyPDF2 import PdfReader as _PdfReader

    class _Wrapper:
        def __init__(self, path: str):
            self._reader = _PdfReader(path)

        @property
        def pages(self):
            return self._reader.pages

    class pypdf:  # type: ignore
        PdfReader = _Wrapper

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "reports", "kbli_extraction")

# Paths PDF sul Desktop
PDF_PP28 = "/Users/antonellosiano/Desktop/PP Nomor 28 Tahun 2025 (1).pdf"
PDF_BPS = "/Users/antonellosiano/Desktop/peraturan-bps-no-7-tahun-2025.pdf"
PDF_INGUB = "/Users/antonellosiano/Desktop/INGUB-6-TAHUN-2025-PENGHENTIAN-SEMENTARA-PEMBERIAN-IZIN-TOKO-MODERN-BERJEJARING.pdf"

KBLI_CODE_RE = re.compile(r"\b(\d{5})\b")
RISK_LEVELS = ["Rendah", "Menengah Rendah", "Menengah", "Menengah Tinggi", "Tinggi"]
SCALES = ["Mikro", "Kecil", "Menengah", "Besar"]


@dataclass
class KBLIEntry:
    kode: str
    judul: str
    tingkat_risiko: str = ""
    pma_allowed: Optional[bool] = None
    pma_max_percentage: str = ""
    skala_usaha: List[str] = None
    sektor: str = ""
    persyaratan: List[str] = None
    kewajiban: List[str] = None
    kewenangan: str = ""
    source_file: str = ""
    page: int = 0
    raw_text: str = ""

    def __post_init__(self):
        if self.skala_usaha is None:
            self.skala_usaha = []
        if self.persyaratan is None:
            self.persyaratan = []
        if self.kewajiban is None:
            self.kewajiban = []


def detect_risk_level(text: str) -> str:
    """Rileva livello di rischio dal testo."""
    text_lower = text.lower()
    for risk in RISK_LEVELS:
        if risk.lower() in text_lower:
            return risk
    return ""


def detect_pma_info(text: str) -> tuple[Optional[bool], str]:
    """Rileva informazioni PMA dal testo."""
    text_lower = text.lower()
    pma_allowed = None
    pma_max = ""

    # Pattern per PMA
    if "pma" in text_lower or "kepemilikan asing" in text_lower:
        if any(x in text_lower for x in ["diizinkan", "allowed", "ya", "boleh"]):
            pma_allowed = True
        elif any(x in text_lower for x in ["tidak diizinkan", "tidak boleh", "dilarang"]):
            pma_allowed = False

        # Cerca percentuale
        pct_match = re.search(r"(\d+)%", text)
        if pct_match:
            pma_max = pct_match.group(1) + "%"

    return pma_allowed, pma_max


def detect_scales(text: str) -> List[str]:
    """Rileva skala usaha dal testo."""
    found_scales = []
    text_lower = text.lower()
    for scale in SCALES:
        if scale.lower() in text_lower:
            found_scales.append(scale)
    return found_scales


def extract_kbli_from_pp28(pdf_path: str) -> Dict[str, KBLIEntry]:
    """Estrae KBLI da PP 28/2025 con focus su risk level, PMA, skala usaha."""
    if not os.path.exists(pdf_path):
        print(f"⚠️  PDF non trovato: {pdf_path}")
        return {}

    print(f"📄 Estrazione PP 28/2025 da: {os.path.basename(pdf_path)}")
    reader = pypdf.PdfReader(pdf_path)
    results: Dict[str, KBLIEntry] = {}

    # Accumula testo per analisi multi-linea
    page_texts = []
    for page_num, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
            page_texts.append((page_num, text))
        except Exception as e:
            print(f"  ⚠️  Errore pagina {page_num}: {e}")
            continue

    # Analizza ogni pagina
    for page_num, text in page_texts:
        lines = text.split("\n")
        current_code = None
        current_entry = None
        context_lines = []

        for line in lines:
            clean = line.strip()
            if not clean:
                continue

            # Cerca codice KBLI
            for match in KBLI_CODE_RE.finditer(clean):
                code = match.group(1)

                # Se troviamo un nuovo codice, salva il precedente
                if current_code and current_code != code:
                    if current_entry:
                        # Analizza contesto accumulato per risk/PMA/scales
                        context_text = " ".join(context_lines[-5:])  # Ultime 5 righe
                        current_entry.tingkat_risiko = detect_risk_level(context_text)
                        pma_allowed, pma_max = detect_pma_info(context_text)
                        current_entry.pma_allowed = pma_allowed
                        current_entry.pma_max_percentage = pma_max
                        current_entry.skala_usaha = detect_scales(context_text)
                        results[current_code] = current_entry

                # Nuovo codice trovato
                current_code = code
                start, end = match.span(1)
                rest = clean[end:].strip(" -:\t")
                title = rest if rest else ""

                current_entry = KBLIEntry(
                    kode=code,
                    judul=title,
                    source_file=os.path.basename(pdf_path),
                    page=page_num,
                    raw_text=clean,
                )
                context_lines = [clean]

            # Accumula contesto per analisi
            if current_code:
                context_lines.append(clean)
                if len(context_lines) > 10:
                    context_lines.pop(0)

        # Salva ultimo codice
        if current_code and current_entry:
            context_text = " ".join(context_lines)
            current_entry.tingkat_risiko = detect_risk_level(context_text)
            pma_allowed, pma_max = detect_pma_info(context_text)
            current_entry.pma_allowed = pma_allowed
            current_entry.pma_max_percentage = pma_max
            current_entry.skala_usaha = detect_scales(context_text)
            results[current_code] = current_entry

    print(f"  ✅ Trovati {len(results)} codici KBLI in PP 28/2025")
    return results


def extract_kbli_from_bps(pdf_path: str) -> Dict[str, KBLIEntry]:
    """Estrae KBLI da Peraturan BPS 7/2025 (lista completa codici)."""
    if not os.path.exists(pdf_path):
        print(f"⚠️  PDF non trovato: {pdf_path}")
        return {}

    print(f"📄 Estrazione BPS 7/2025 da: {os.path.basename(pdf_path)}")
    reader = pypdf.PdfReader(pdf_path)
    results: Dict[str, KBLIEntry] = {}

    for page_num, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as e:
            print(f"  ⚠️  Errore pagina {page_num}: {e}")
            continue

        for line in text.split("\n"):
            clean = line.strip()
            if not clean:
                continue

            for match in KBLI_CODE_RE.finditer(clean):
                code = match.group(1)
                if code in results:
                    continue

                start, end = match.span(1)
                rest = clean[end:].strip(" -:\t")
                title = rest if rest else ""

                results[code] = KBLIEntry(
                    kode=code,
                    judul=title,
                    source_file=os.path.basename(pdf_path),
                    page=page_num,
                    raw_text=clean,
                )

    print(f"  ✅ Trovati {len(results)} codici KBLI in BPS 7/2025")
    return results


def extract_ingub_bali(pdf_path: str) -> Dict:
    """Estrae informazioni da INGUB 6/2025 (restrizioni Bali)."""
    if not os.path.exists(pdf_path):
        print(f"⚠️  PDF non trovato: {pdf_path}")
        return {}

    print(f"📄 Analisi INGUB 6/2025 da: {os.path.basename(pdf_path)}")
    reader = pypdf.PdfReader(pdf_path)
    
    result = {
        "source": "INGUB-6-TAHUN-2025",
        "kbli_codes": [],
        "areas": [],
        "restrictions": {},
        "valid_from": "",
        "valid_until": "",
        "full_text": "",
    }

    full_text = ""
    for page_num, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
            full_text += text + "\n"
        except Exception as e:
            print(f"  ⚠️  Errore pagina {page_num}: {e}")
            continue

    result["full_text"] = full_text

    # Cerca KBLI menzionati
    for match in KBLI_CODE_RE.finditer(full_text):
        code = match.group(1)
        if code not in result["kbli_codes"]:
            result["kbli_codes"].append(code)

    # Cerca aree geografiche (Bali, kabupaten, kota)
    area_patterns = [
        r"Kabupaten\s+([A-Z][a-z]+)",
        r"Kota\s+([A-Z][a-z]+)",
        r"Bali",
    ]
    for pattern in area_patterns:
        for match in re.finditer(pattern, full_text, re.IGNORECASE):
            area = match.group(0) if match.lastindex == 0 else match.group(1)
            if area and area not in result["areas"]:
                result["areas"].append(area)

    # Cerca date
    date_pattern = r"(\d{1,2}[-/]\d{1,2}[-/]\d{4})"
    dates = re.findall(date_pattern, full_text)
    if dates:
        result["valid_from"] = dates[0] if len(dates) > 0 else ""
        result["valid_until"] = dates[-1] if len(dates) > 1 else dates[0]

    # Identifica tipo restrizione
    text_lower = full_text.lower()
    if "penghantian" in text_lower or "sementara" in text_lower:
        result["restrictions"]["type"] = "penghantian_sementara"
    if "toko modern" in text_lower or "berjejaring" in text_lower:
        result["restrictions"]["applies_to"] = "toko_modern_berjejaring"

    print(f"  ✅ Analisi completata: {len(result['kbli_codes'])} KBLI, {len(result['areas'])} aree")
    return result


def main():
    """Main extraction function."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("ESTRAZIONE KBLI DA PDF PER VERIFICA COMPLIANCE QDRANT")
    print("=" * 60)

    # 1) Estrai da PP 28/2025
    pp28_kbli = extract_kbli_from_pp28(PDF_PP28)
    pp28_output = os.path.join(OUTPUT_DIR, "pp28_kbli.json")
    with open(pp28_output, "w", encoding="utf-8") as f:
        json.dump(
            {code: asdict(entry) for code, entry in pp28_kbli.items()},
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"💾 Salvato: {pp28_output}")

    # 2) Estrai da BPS 7/2025
    bps_kbli = extract_kbli_from_bps(PDF_BPS)
    bps_output = os.path.join(OUTPUT_DIR, "bps_kbli.json")
    with open(bps_output, "w", encoding="utf-8") as f:
        json.dump(
            {code: asdict(entry) for code, entry in bps_kbli.items()},
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"💾 Salvato: {bps_output}")

    # 3) Analizza INGUB Bali
    ingub_data = extract_ingub_bali(PDF_INGUB)
    ingub_output = os.path.join(OUTPUT_DIR, "ingub_bali_restrictions.json")
    with open(ingub_output, "w", encoding="utf-8") as f:
        json.dump(ingub_data, f, indent=2, ensure_ascii=False)
    print(f"💾 Salvato: {ingub_output}")

    # Statistiche
    print("\n" + "=" * 60)
    print("STATISTICHE ESTRAZIONE")
    print("=" * 60)
    print(f"PP 28/2025: {len(pp28_kbli)} codici")
    print(f"BPS 7/2025: {len(bps_kbli)} codici")
    print(f"INGUB Bali: {len(ingub_data.get('kbli_codes', []))} codici menzionati")
    print(f"\n📁 Output salvato in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
