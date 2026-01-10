#!/usr/bin/env python3
"""
Confronto KBLI tra PDF (PP 28/2025 + Peraturan BPS 7/2025) e Qdrant (kbli_unified)

Steps:
- Estrae KBLI da due PDF sul Desktop
- Seleziona 10 KBLI a campione
- Per ogni codice, interroga la collection `kbli_unified` su Qdrant
- Confronta i campi disponibili
- Genera un report HTML in `reports/kbli_comparison_YYYYMMDD.html`
"""

import os
import re
import sys
import json
import datetime
from dataclasses import dataclass
from typing import List, Dict, Optional

import requests
from dotenv import load_dotenv

try:
    import pypdf
except ImportError:
    # Fallback a PyPDF2 se pypdf non è disponibile
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

PDF_PP28_PATH = "/Users/antonellosiano/Desktop/PP Nomor 28 Tahun 2025 (1).pdf"
PDF_BPS_PATH = "/Users/antonellosiano/Desktop/peraturan-bps-no-7-tahun-2025.pdf"

REPORT_DIR = os.path.join(PROJECT_ROOT, "reports")


KBLI_CODE_RE = re.compile(r"\b(\d{5})\b")


@dataclass
class PDFKBLIEntry:
    code: str
    title: str
    source_file: str
    page: int
    raw_line: str


@dataclass
class QdrantKBLIEntry:
    code: str
    payload: Dict


@dataclass
class KBLIComparison:
    code: str
    pdf: Optional[PDFKBLIEntry]
    qdrant: Optional[QdrantKBLIEntry]
    title_match: Optional[str]
    notes: str


def extract_kbli_from_pdf(pdf_path: str, max_codes: Optional[int] = None) -> Dict[str, PDFKBLIEntry]:
    """
    Estrae KBLI da un PDF usando una regex semplice su linee di testo.

    Ritorna un dict {code -> PDFKBLIEntry} con il primo match per codice.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF non trovato: {pdf_path}")

    print(f"📄 Estrazione KBLI da: {pdf_path}")
    reader = pypdf.PdfReader(pdf_path)

    results: Dict[str, PDFKBLIEntry] = {}

    for page_num, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as e:  # pragma: no cover - difetti PDF
            print(f"  ⚠️  Errore estrazione pagina {page_num}: {e}")
            continue

        for line in text.split("\n"):
            clean = line.strip()
            if not clean:
                continue

            for match in KBLI_CODE_RE.finditer(clean):
                code = match.group(1)

                if code in results:
                    continue

                # Titolo = parte della linea dopo il codice
                start, end = match.span(1)
                rest = clean[end:].strip(" -:\t")
                title = rest if rest else ""

                results[code] = PDFKBLIEntry(
                    code=code,
                    title=title,
                    source_file=os.path.basename(pdf_path),
                    page=page_num,
                    raw_line=clean,
                )

                if max_codes is not None and len(results) >= max_codes:
                    return results

    print(f"  ✅ Trovati {len(results)} codici unici in {os.path.basename(pdf_path)}")
    return results


def get_qdrant_config() -> tuple[str, Optional[str]]:
    """
    Legge configurazione Qdrant da apps/backend-rag/.env o dall'ambiente.
    """
    env_path = os.path.join(PROJECT_ROOT, "apps", "backend-rag", ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        # fallback: carica comunque dall'ambiente
        load_dotenv()

    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")

    if not url:
        raise RuntimeError("QDRANT_URL non impostata (controlla apps/backend-rag/.env)")

    print(f"🔌 Connessione a Qdrant: {url}")
    return url.rstrip("/"), api_key


def _qdrant_scroll(
    base_url: str,
    api_key: Optional[str],
    collection_name: str,
    filter_body: Dict,
) -> List[Dict]:
    """
    Effettua una chiamata REST a /collections/{collection_name}/points/scroll
    con il filtro specificato e ritorna la lista di punti.
    """
    endpoint = f"{base_url}/collections/{collection_name}/points/scroll"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["api-key"] = api_key

    payload = {
        "filter": filter_body,
        "limit": 3,
        "with_payload": True,
    }

    resp = requests.post(endpoint, json=payload, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("result", {}).get("points", [])


def fetch_kbli_from_qdrant(
    base_url: str, api_key: Optional[str], code: str
) -> Optional[QdrantKBLIEntry]:
    """
    Cerca un KBLI in kbli_unified provando sia `kbli_code` sia `metadata.code`.
    """
    collection_name = "kbli_unified"

    # Primo tentativo: campo payload metadata.kode (come da struttura reale)
    filters: List[Dict] = [
        {
            "must": [
                {
                    "key": "metadata.kode",
                    "match": {"value": code},
                }
            ]
        },
        {
            "must": [
                {
                    "key": "metadata.code",
                    "match": {"value": code},
                }
            ]
        },
    ]

    for idx, scroll_filter in enumerate(filters, start=1):
        try:
            points = _qdrant_scroll(base_url, api_key, collection_name, scroll_filter)
        except Exception as e:  # pragma: no cover - errori rete
            print(f"  ⚠️  Errore query Qdrant (tentativo {idx}) per codice {code}: {e}")
            continue

        if points:
            p = points[0]
            payload = p.get("payload") or {}
            # Normalizza: se c'è `metadata.code` ma non `kbli_code`, riempiamo.
            if "kbli_code" not in payload:
                meta = payload.get("metadata", {})
                if isinstance(meta, dict) and meta.get("code"):
                    payload["kbli_code"] = meta.get("code")
            return QdrantKBLIEntry(code=code, payload=payload)

    return None


def title_similarity(a: str, b: str) -> float:
    """
    Similarità molto semplice basata su overlap di parole.
    """
    if not a or not b:
        return 0.0
    set_a = set(a.lower().split())
    set_b = set(b.lower().split())
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0


def compare_kbli(pdf_entry: Optional[PDFKBLIEntry], qdrant_entry: Optional[QdrantKBLIEntry]) -> KBLIComparison:
    if not pdf_entry and not qdrant_entry:
        return KBLIComparison(code="UNKNOWN", pdf=None, qdrant=None, title_match=None, notes="Nessun dato")

    code = pdf_entry.code if pdf_entry else (qdrant_entry.code if qdrant_entry else "UNKNOWN")
    notes: List[str] = []
    title_match: Optional[str] = None

    if pdf_entry and qdrant_entry:
        meta = qdrant_entry.payload.get("metadata", {}) or {}
        q_title = (
            qdrant_entry.payload.get("title")
            or meta.get("title")
            or meta.get("judul", "")
        )
        sim = title_similarity(pdf_entry.title, q_title)
        if sim >= 0.85:
            title_match = "identico/simile"
        elif sim >= 0.5:
            title_match = "parzialmente simile"
        else:
            title_match = "diverso"
            notes.append(f"Titolo divergente (similarità {sim:.2f})")

        # Rischio
        pdf_risk = ""
        lower_line = pdf_entry.raw_line.lower()
        if "rendah" in lower_line:
            pdf_risk = "Rendah"
        elif "menengah tinggi" in lower_line:
            pdf_risk = "Menengah Tinggi"
        elif "menengah rendah" in lower_line:
            pdf_risk = "Menengah Rendah"
        elif "menengah" in lower_line:
            pdf_risk = "Menengah"
        elif "tinggi" in lower_line:
            pdf_risk = "Tinggi"

        q_risk = qdrant_entry.payload.get("risk_level") or qdrant_entry.payload.get(
            "metadata", {}
        ).get("risk_level", "")

        if pdf_risk and q_risk and pdf_risk != q_risk:
            notes.append(f"Risk level diverso: PDF={pdf_risk}, Qdrant={q_risk}")

        # PMA
        q_pma_allowed = qdrant_entry.payload.get("pma_allowed")
        if q_pma_allowed is not None:
            if "pma" not in lower_line and "kepemilikan asing" not in lower_line:
                notes.append("Qdrant ha info PMA, PDF (linea catturata) no")

    elif pdf_entry and not qdrant_entry:
        notes.append("Codice presente nel PDF ma NON trovato in Qdrant (kbli_unified)")
    elif not pdf_entry and qdrant_entry:
        notes.append("Codice presente in Qdrant ma non estratto dal PDF (campione PDF)")

    return KBLIComparison(code=code, pdf=pdf_entry, qdrant=qdrant_entry, title_match=title_match, notes="; ".join(notes))


def choose_sample_codes(pdf_entries: Dict[str, PDFKBLIEntry], sample_size: int = 10) -> List[str]:
    """
    Seleziona un campione di codici, semplicemente ordinando e prendendo i primi N.
    (Si può raffinare in futuro per diversità settori).
    """
    codes = sorted(pdf_entries.keys())
    return codes[:sample_size]


def generate_html_report(
    comparisons: List[KBLIComparison],
    output_path: str,
    stats: Dict[str, int],
) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    date_str = datetime.date.today().isoformat()

    rows_html: List[str] = []
    for cmp in comparisons:
        pdf_title = cmp.pdf.title if cmp.pdf else ""
        q_payload = cmp.qdrant.payload if cmp.qdrant else {}
        meta = q_payload.get("metadata", {}) or {}
        q_title = (
            q_payload.get("title")
            or meta.get("title")
            or meta.get("judul", "")
        )
        sector = q_payload.get("sector") or meta.get("sektor", meta.get("sector", ""))
        risk = q_payload.get("risk_level") or meta.get("risk_level", "")
        pma = q_payload.get("pma_allowed") if "pma_allowed" in q_payload else meta.get("pma_allowed")
        scales = q_payload.get("scales") or meta.get("scales", [])

        notes_class = "ok" if not cmp.notes else "warn"

        rows_html.append(
            "<tr>"
            f"<td>{cmp.code}</td>"
            f"<td>{pdf_title}</td>"
            f"<td>{q_title}</td>"
            f"<td>{sector}</td>"
            f"<td>{risk}</td>"
            f"<td>{pma}</td>"
            f"<td>{', '.join(scales) if isinstance(scales, list) else scales}</td>"
            f"<td>{cmp.title_match or ''}</td>"
            f"<td class='{notes_class}'>{cmp.notes}</td>"
            "</tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>KBLI Comparison Report - {date_str}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif; margin: 24px; }}
    h1, h2 {{ margin-bottom: 0.4rem; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
    th, td {{ border: 1px solid #ccc; padding: 6px 8px; font-size: 13px; vertical-align: top; }}
    th {{ background: #f5f5f5; position: sticky; top: 0; }}
    tr:nth-child(even) {{ background: #fafafa; }}
    .ok {{ color: #167d00; }}
    .warn {{ color: #b00020; font-weight: 500; }}
    .badge {{ display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 11px; }}
    .badge-ok {{ background: #e6f4ea; color: #137333; }}
    .badge-warn {{ background: #fce8e6; color: #c5221f; }}
    .meta {{ color: #666; font-size: 12px; }}
  </style>
</head>
<body>
  <h1>KBLI Comparison Report</h1>
  <p class="meta">Data: {date_str}</p>

  <h2>Panoramica</h2>
  <ul>
    <li><span class="badge badge-ok">Campione</span> {stats.get('sample_size', 0)} codici KBLI analizzati</li>
    <li><span class="badge badge-ok">Match Qdrant</span> {stats.get('found_in_qdrant', 0)} trovati in `kbli_unified`</li>
    <li><span class="badge badge-warn">Non trovati</span> {stats.get('missing_in_qdrant', 0)} non presenti/visibili in `kbli_unified`</li>
    <li><span class="badge badge-warn">Differenze titolo</span> {stats.get('title_mismatch', 0)} con titolo divergente</li>
  </ul>

  <h2>Dettaglio per codice</h2>
  <table>
    <thead>
      <tr>
        <th>KBLI</th>
        <th>Titolo (PDF)</th>
        <th>Titolo (Qdrant)</th>
        <th>Settore (Qdrant)</th>
        <th>Rischio (Qdrant)</th>
        <th>PMA Allowed</th>
        <th>Skala Usaha</th>
        <th>Match Titolo</th>
        <th>Note</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows_html)}
    </tbody>
  </table>

  <hr />
  <p class="meta">
    Fonti:<br/>
    - PDF: PP Nomor 28 Tahun 2025 (1).pdf, peraturan-bps-no-7-tahun-2025.pdf<br/>
    - Qdrant collection: kbli_unified
  </p>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n📄 Report HTML generato: {output_path}")


def main(sample_size: int = 10) -> None:
    # 1) Estrazione dai due PDF
    pp28_entries = extract_kbli_from_pdf(PDF_PP28_PATH)
    bps_entries = extract_kbli_from_pdf(PDF_BPS_PATH)

    # Merge (favorendo PP28 in caso di conflitto)
    combined: Dict[str, PDFKBLIEntry] = dict(pp28_entries)
    for code, entry in bps_entries.items():
        combined.setdefault(code, entry)

    if not combined:
        print("❌ Nessun KBLI estratto dai PDF.")
        sys.exit(1)

    # 2) Campione
    sample_codes = choose_sample_codes(combined, sample_size=sample_size)
    print(f"\n🎯 Campione selezionato ({len(sample_codes)} codici): {', '.join(sample_codes)}")

    # 3) Qdrant
    base_url, api_key = get_qdrant_config()

    comparisons: List[KBLIComparison] = []
    stats = {
        "sample_size": len(sample_codes),
        "found_in_qdrant": 0,
        "missing_in_qdrant": 0,
        "title_mismatch": 0,
    }

    for code in sample_codes:
        pdf_entry = combined.get(code)
        q_entry = fetch_kbli_from_qdrant(base_url, api_key, code)

        if q_entry:
            stats["found_in_qdrant"] += 1
        else:
            stats["missing_in_qdrant"] += 1

        cmp = compare_kbli(pdf_entry, q_entry)
        if cmp.title_match == "diverso":
            stats["title_mismatch"] += 1

        comparisons.append(cmp)

    # 4) Report HTML
    today = datetime.date.today().strftime("%Y%m%d")
    output_path = os.path.join(REPORT_DIR, f"kbli_comparison_{today}.html")
    generate_html_report(comparisons, output_path, stats)

    # 5) Stampa riepilogo JSON leggero in stdout (per debugging rapido)
    summary = {
        "stats": stats,
        "sample_codes": sample_codes,
        "comparisons": [
            {
                "code": c.code,
                "title_match": c.title_match,
                "notes": c.notes,
                "pdf_title": c.pdf.title if c.pdf else None,
                "qdrant_title": (
                    (c.qdrant.payload.get("title") if c.qdrant else None)
                    if c.qdrant
                    else None
                ),
            }
            for c in comparisons
        ],
        "report_path": output_path,
    }
    print("\n=== JSON SUMMARY ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

