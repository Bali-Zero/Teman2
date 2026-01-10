#!/usr/bin/env python3
"""
Confronto KBLI tra Qdrant e OSS.go.id

Prende un KBLI specifico, recupera i dati da Qdrant (kbli_unified)
e confronta con i dati disponibili su oss.go.id
"""

import os
import sys
import json
import datetime
import requests
from typing import Dict, Optional
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPORT_DIR = os.path.join(PROJECT_ROOT, "reports")

# Load env
env_path = os.path.join(PROJECT_ROOT, "apps", "backend-rag", ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")


def fetch_kbli_from_qdrant(code: str) -> Optional[Dict]:
    """Recupera dati KBLI da Qdrant collection kbli_unified."""
    url = QDRANT_URL.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if QDRANT_API_KEY:
        headers["api-key"] = QDRANT_API_KEY

    body = {
        "filter": {
            "must": [{"key": "metadata.kode", "match": {"value": code}}]
        },
        "limit": 1,
        "with_payload": True,
    }

    try:
        resp = requests.post(
            f"{url}/collections/kbli_unified/points/scroll",
            headers=headers,
            json=body,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        points = data.get("result", {}).get("points", [])
        if points:
            return points[0].get("payload", {})
    except Exception as e:
        print(f"❌ Errore query Qdrant: {e}")
    return None


def parse_oss_text_data(text: str) -> Dict:
    """
    Parsa dati OSS copiati manualmente da oss.go.id.
    
    Formato atteso:
    - KBLI 2020
    - Codice (es. 01111)
    - Judul
    - URAIAN
    - RUANG LINGKUP
    - PB UMKU (con tabelle persyaratan/kewajiban)
    """
    lines = text.strip().split("\n")
    oss_data = {
        "source": "OSS_MANUAL_COPY",
        "uraian": "",
        "ruang_lingkup": "",
        "pb_umku": [],
    }
    
    current_section = None
    current_pb_umku = {}
    current_table = None
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            i += 1
            continue
            
        # Kode
        if line.isdigit() and len(line) == 5:
            oss_data["kode"] = line
            i += 1
            continue
            
        # Judul (dopo il codice)
        if "kode" in oss_data and "judul" not in oss_data and line:
            oss_data["judul"] = line
            i += 1
            continue
            
        # Sezioni principali
        if line == "URAIAN":
            current_section = "uraian"
            i += 1
            continue
        elif line == "RUANG LINGKUP":
            current_section = "ruang_lingkup"
            i += 1
            continue
        elif line == "PB UMKU":
            current_section = "pb_umku"
            i += 1
            continue
            
        # Accumula contenuto per sezione
        if current_section == "uraian":
            if line and not line.startswith("RUANG"):
                oss_data["uraian"] += line + " "
        elif current_section == "ruang_lingkup":
            if line and not line.startswith("PB"):
                oss_data["ruang_lingkup"] += line + " "
        elif current_section == "pb_umku":
            # Parsing PB UMKU (nome, tabelle)
            if line and not any(x in line for x in ["No", "Parameter", "Kewenangan", "Persyaratan", "Kewajiban"]):
                if "nama_pb_umku" not in current_pb_umku:
                    current_pb_umku["nama_pb_umku"] = line
                    current_pb_umku["persyaratan"] = []
                    current_pb_umku["kewajiban"] = []
            elif "Parameter" in line or "Kewenangan" in line:
                current_table = "parameter"
            elif "Persyaratan" in line:
                current_table = "persyaratan"
            elif "Kewajiban" in line:
                current_table = "kewajiban"
            # TODO: Parsing più dettagliato delle tabelle se necessario
        
        i += 1
    
    # Cleanup
    oss_data["uraian"] = oss_data["uraian"].strip()
    oss_data["ruang_lingkup"] = oss_data["ruang_lingkup"].strip()
    
    if current_pb_umku:
        oss_data["pb_umku"].append(current_pb_umku)
    
    return oss_data


def fetch_kbli_from_oss(code: str, manual_data: Optional[str] = None) -> Optional[Dict]:
    """
    Cerca dati KBLI su oss.go.id.
    Se manual_data è fornito, usa quello invece di cercare online.
    """
    if manual_data:
        return parse_oss_text_data(manual_data)
    
    oss_data = {}

    # Strategia 1: Prova API diretta (se esiste)
    api_urls = [
        f"https://oss.go.id/api/kbli/{code}",
        f"https://api.oss.go.id/kbli/{code}",
        f"https://oss.go.id/api/v1/kbli/{code}",
    ]

    for api_url in api_urls:
        try:
            resp = requests.get(api_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                if "json" in resp.headers.get("Content-Type", ""):
                    oss_data = resp.json()
                    oss_data["source"] = "OSS_API"
                    return oss_data
        except Exception:
            continue

    # Strategia 2: Prova pagina informativa KBLI
    info_url = "https://oss.go.id/informasi/kbli-berbasis-risiko"
    try:
        resp = requests.get(info_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            # Cerca il codice nel contenuto HTML
            html = resp.text
            if code in html:
                oss_data["found_in_page"] = True
                oss_data["source"] = "OSS_WEB_PAGE"
                # Estrai info base se possibile (parsing minimo)
                # In futuro si può migliorare con BeautifulSoup
    except Exception as e:
        print(f"⚠️  Errore accesso OSS web: {e}")

    # Strategia 3: Prova ricerca OSS (se c'è endpoint di ricerca)
    search_urls = [
        f"https://oss.go.id/api/search/kbli?q={code}",
        f"https://oss.go.id/api/kbli/search?code={code}",
    ]

    for search_url in search_urls:
        try:
            resp = requests.get(search_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                if "json" in resp.headers.get("Content-Type", ""):
                    data = resp.json()
                    if data:
                        oss_data.update(data)
                        oss_data["source"] = "OSS_SEARCH_API"
                        return oss_data
        except Exception:
            continue

    return oss_data if oss_data else None


def extract_persyaratan_kewajiban_from_text(text: str) -> Dict:
    """Estrae Persyaratan e Kewajiban dal campo text di Qdrant."""
    result = {
        "persyaratan": [],
        "kewajiban": [],
        "kewenangan": [],
    }
    
    if not text:
        return result
    
    lines = text.split("\n")
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Rileva sezioni
        if "## Persyaratan" in line or "Persyaratan (Requirements)" in line:
            current_section = "persyaratan"
            continue
        elif "## Kewajiban" in line or "Kewajiban (Obligations)" in line:
            current_section = "kewajiban"
            continue
        elif "## Kewenangan" in line or "Kewenangan Penerbit" in line:
            current_section = "kewenangan"
            continue
        elif line.startswith("## "):
            current_section = None
            continue
            
        # Accumula contenuto
        if current_section == "persyaratan":
            if line and (line[0].isdigit() or line.startswith("-")):
                # Rimuovi numerazione
                clean = line.lstrip("0123456789.-) ").strip()
                if clean:
                    result["persyaratan"].append(clean)
        elif current_section == "kewajiban":
            if line and (line[0].isdigit() or line.startswith("-")):
                clean = line.lstrip("0123456789.-) ").strip()
                if clean:
                    result["kewajiban"].append(clean)
        elif current_section == "kewenangan":
            if line.startswith("-") or "**" in line:
                clean = line.lstrip("-* ").strip()
                if clean:
                    result["kewenangan"].append(clean)
    
    return result


def compare_kbli_data(qdrant_data: Optional[Dict], oss_data: Optional[Dict], code: str) -> Dict:
    """Confronta dati Qdrant vs OSS e genera report."""
    comparison = {
        "code": code,
        "qdrant": {},
        "oss": {},
        "matches": {},
        "differences": [],
    }

    if qdrant_data:
        meta = qdrant_data.get("metadata", {})
        text = qdrant_data.get("text", "")
        
        # Estrai Persyaratan e Kewajiban dal text
        reqs = extract_persyaratan_kewajiban_from_text(text)
        
        comparison["qdrant"] = {
            "kode": meta.get("kode"),
            "judul": meta.get("judul"),
            "sektor": meta.get("sektor"),
            "risk_level": meta.get("risk_level"),
            "pma_allowed": meta.get("pma_allowed"),
            "pma_max_percentage": meta.get("pma_max_percentage"),
            "scales": meta.get("scales", []),
            "sources": meta.get("sources", []),
            "persyaratan": reqs["persyaratan"],
            "kewajiban": reqs["kewajiban"],
            "kewenangan": reqs["kewenangan"],
        }

    if oss_data:
        comparison["oss"] = oss_data

    # Confronti base
    if qdrant_data and oss_data:
        q_meta = qdrant_data.get("metadata", {})
        q_judul = q_meta.get("judul", "").lower()
        q_risk = q_meta.get("risk_level", "")
        q_text = qdrant_data.get("text", "")

        # Confronto titolo
        if "judul" in oss_data or "title" in oss_data:
            oss_judul = (oss_data.get("judul") or oss_data.get("title", "")).lower()
            if q_judul and oss_judul:
                if q_judul == oss_judul:
                    comparison["matches"]["title"] = "identico"
                else:
                    comparison["differences"].append(f"Titolo diverso: Qdrant='{q_meta.get('judul')}', OSS='{oss_data.get('judul') or oss_data.get('title')}'")

        # Confronto URAIAN vs contenuto Qdrant
        if "uraian" in oss_data and oss_data["uraian"]:
            if q_text and oss_data["uraian"].lower() in q_text.lower():
                comparison["matches"]["uraian"] = "presente in Qdrant"
            else:
                comparison["differences"].append("URAIAN presente in OSS ma non trovato esattamente in Qdrant")

        # Verifica RUANG LINGKUP
        if "ruang_lingkup" in oss_data and oss_data["ruang_lingkup"]:
            if q_text and any(word in q_text.lower() for word in oss_data["ruang_lingkup"].lower().split()[:5]):
                comparison["matches"]["ruang_lingkup"] = "parzialmente presente"
            else:
                comparison["differences"].append("RUANG LINGKUP presente in OSS ma non chiaramente in Qdrant")

        # Confronto Persyaratan
        q_persyaratan = comparison["qdrant"].get("persyaratan", [])
        if q_persyaratan:
            comparison["matches"]["persyaratan_count"] = f"{len(q_persyaratan)} persyaratan trovati in Qdrant"
            # Verifica se OSS ha persyaratan strutturati
            if "pb_umku" in oss_data and oss_data["pb_umku"]:
                for pb in oss_data["pb_umku"]:
                    if pb.get("persyaratan"):
                        oss_pers_count = len(pb.get("persyaratan", []))
                        if oss_pers_count > 0:
                            comparison["matches"]["persyaratan_oss"] = f"{oss_pers_count} persyaratan in OSS PB UMKU"
                            # Confronto dettagliato se possibile
                            if len(q_persyaratan) != oss_pers_count:
                                comparison["differences"].append(f"Numero persyaratan diverso: Qdrant={len(q_persyaratan)}, OSS={oss_pers_count}")

        # Confronto Kewajiban
        q_kewajiban = comparison["qdrant"].get("kewajiban", [])
        if q_kewajiban:
            comparison["matches"]["kewajiban_count"] = f"{len(q_kewajiban)} kewajiban trovati in Qdrant"
            # Verifica se OSS ha kewajiban strutturati
            if "pb_umku" in oss_data and oss_data["pb_umku"]:
                for pb in oss_data["pb_umku"]:
                    if pb.get("kewajiban"):
                        oss_kew_count = len(pb.get("kewajiban", []))
                        if oss_kew_count > 0:
                            comparison["matches"]["kewajiban_oss"] = f"{oss_kew_count} kewajiban in OSS PB UMKU"
                            if len(q_kewajiban) != oss_kew_count:
                                comparison["differences"].append(f"Numero kewajiban diverso: Qdrant={len(q_kewajiban)}, OSS={oss_kew_count}")

        # Verifica PB UMKU
        if "pb_umku" in oss_data and oss_data["pb_umku"]:
            pb_count = len(oss_data["pb_umku"])
            comparison["matches"]["pb_umku_count"] = f"{pb_count} PB UMKU trovati in OSS"
            # Qdrant ha già i dati strutturati nel text
            if q_persyaratan or q_kewajiban:
                comparison["matches"]["pb_umku_qdrant"] = "Dati PB UMKU presenti in Qdrant (persyaratan/kewajiban estratti)"

        if "risk_level" in oss_data or "risiko" in oss_data:
            oss_risk = oss_data.get("risk_level") or oss_data.get("risiko", "")
            if q_risk and oss_risk and q_risk != oss_risk:
                comparison["differences"].append(f"Risk level diverso: Qdrant={q_risk}, OSS={oss_risk}")

    return comparison


def generate_html_report(comparison: Dict, output_path: str) -> None:
    """Genera report HTML del confronto."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    qdrant = comparison.get("qdrant", {})
    oss = comparison.get("oss", {})
    matches = comparison.get("matches", {})
    differences = comparison.get("differences", [])

    date_str = datetime.date.today().isoformat()

    # Genera HTML per differenze (fuori dall'f-string per evitare problemi con backslash)
    if differences:
        diff_items = "".join([f'<li class="diff">{d}</li>' for d in differences])
        differences_html = f"<h3>Differenze:</h3><ul>{diff_items}</ul>"
    else:
        differences_html = '<p class="match">✅ Nessuna differenza rilevata</p>'

    # Genera HTML per PB UMKU
    if oss.get("pb_umku"):
        pb_items = "".join([f'<li><strong>{pb.get("nama_pb_umku", "N/A")}</strong></li>' for pb in oss.get("pb_umku", [])])
        pb_umku_html = f"<ul>{pb_items}</ul>"
    else:
        pb_umku_html = "N/A"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>KBLI {comparison['code']} - Qdrant vs OSS Comparison</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif; margin: 24px; max-width: 1200px; }}
    h1, h2 {{ margin-bottom: 0.4rem; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
    th, td {{ border: 1px solid #ccc; padding: 8px 12px; font-size: 14px; vertical-align: top; }}
    th {{ background: #f5f5f5; position: sticky; top: 0; }}
    .source-section {{ margin: 20px 0; }}
    .match {{ color: #167d00; font-weight: 500; }}
    .diff {{ color: #b00020; font-weight: 500; }}
    .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
    .badge-ok {{ background: #e6f4ea; color: #137333; }}
    .badge-warn {{ background: #fce8e6; color: #c5221f; }}
    .meta {{ color: #666; font-size: 12px; }}
  </style>
</head>
<body>
  <h1>KBLI {comparison['code']} - Confronto Qdrant vs OSS.go.id</h1>
  <p class="meta">Data: {date_str}</p>

  <div class="source-section">
    <h2>Dati Qdrant (kbli_unified)</h2>
    <table>
      <tr><th>Campo</th><th>Valore</th></tr>
      <tr><td>Kode</td><td>{qdrant.get('kode', 'N/A')}</td></tr>
      <tr><td>Judul</td><td>{qdrant.get('judul', 'N/A')}</td></tr>
      <tr><td>Sektor</td><td>{qdrant.get('sektor', 'N/A')}</td></tr>
      <tr><td>Risk Level</td><td>{qdrant.get('risk_level', 'N/A')}</td></tr>
      <tr><td>PMA Allowed</td><td>{qdrant.get('pma_allowed', 'N/A')}</td></tr>
      <tr><td>PMA Max %</td><td>{qdrant.get('pma_max_percentage', 'N/A')}</td></tr>
      <tr><td>Scales</td><td>{', '.join(qdrant.get('scales', [])) if qdrant.get('scales') else 'N/A'}</td></tr>
      <tr><td>Sources</td><td>{', '.join(qdrant.get('sources', [])) if qdrant.get('sources') else 'N/A'}</td></tr>
      <tr><td>Persyaratan (count)</td><td>{len(qdrant.get('persyaratan', []))}</td></tr>
      <tr><td>Kewajiban (count)</td><td>{len(qdrant.get('kewajiban', []))}</td></tr>
      <tr><td>Kewenangan (count)</td><td>{len(qdrant.get('kewenangan', []))}</td></tr>
    </table>
    {f'<h3>Persyaratan da Qdrant ({len(qdrant.get("persyaratan", []))}):</h3><ol>{"".join([f"<li>{p}</li>" for p in qdrant.get("persyaratan", [])[:10]])}</ol>' if qdrant.get("persyaratan") else ""}
    {f'<h3>Kewajiban da Qdrant ({len(qdrant.get("kewajiban", []))}):</h3><ol>{"".join([f"<li>{k}</li>" for k in qdrant.get("kewajiban", [])[:10]])}</ol>' if qdrant.get("kewajiban") else ""}
  </div>

  <div class="source-section">
    <h2>Dati OSS.go.id</h2>
    <table>
      <tr><th>Campo</th><th>Valore</th></tr>
      <tr><td>Kode</td><td>{oss.get('kode', 'N/A')}</td></tr>
      <tr><td>Judul</td><td>{oss.get('judul', 'N/A')}</td></tr>
      <tr><td>Source</td><td>{oss.get('source', 'N/A')}</td></tr>
      <tr><td>Uraian</td><td>{oss.get('uraian', 'N/A')}</td></tr>
      <tr><td>Ruang Lingkup</td><td>{oss.get('ruang_lingkup', 'N/A')}</td></tr>
      <tr><td>PB UMKU</td><td>{pb_umku_html}</td></tr>
    </table>
  </div>

  <div class="source-section">
    <h2>Confronto</h2>
    <ul>
      <li><span class="badge badge-ok">Match</span> {len(matches)} campi corrispondenti</li>
      <li><span class="badge badge-warn">Differenze</span> {len(differences)} differenze rilevate</li>
    </ul>
    {differences_html}
  </div>

  <hr />
  <p class="meta">
    Fonti:<br/>
    - Qdrant: {QDRANT_URL}/collections/kbli_unified<br/>
    - OSS: https://oss.go.id
  </p>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n📄 Report HTML generato: {output_path}")


def main(kbli_code: str = "01111", oss_manual_data: Optional[str] = None):
    """Main function."""
    print(f"🔍 Analisi KBLI {kbli_code}")
    print("=" * 60)

    # 1) Recupera da Qdrant
    print(f"\n1️⃣  Recupero dati da Qdrant (kbli_unified)...")
    qdrant_data = fetch_kbli_from_qdrant(kbli_code)
    if qdrant_data:
        meta = qdrant_data.get("metadata", {})
        print(f"   ✅ Trovato: {meta.get('judul', 'N/A')}")
        print(f"      Sektor: {meta.get('sektor', 'N/A')}")
        print(f"      Risk: {meta.get('risk_level', 'N/A')}")
    else:
        print(f"   ❌ KBLI {kbli_code} non trovato in Qdrant")
        return

    # 2) Recupera da OSS
    print(f"\n2️⃣  Recupero dati da OSS.go.id...")
    oss_data = fetch_kbli_from_oss(kbli_code, manual_data=oss_manual_data)
    if oss_data:
        print(f"   ✅ Dati recuperati (source: {oss_data.get('source', 'unknown')})")
        if "uraian" in oss_data:
            print(f"      Uraian: {oss_data['uraian'][:100]}...")
    else:
        print(f"   ⚠️  Nessun dato recuperato da OSS.go.id")

    # 3) Confronta
    print(f"\n3️⃣  Confronto dati...")
    comparison = compare_kbli_data(qdrant_data, oss_data, kbli_code)

    # 4) Report
    today = datetime.date.today().strftime("%Y%m%d")
    output_path = os.path.join(REPORT_DIR, f"kbli_{kbli_code}_oss_comparison_{today}.html")
    generate_html_report(comparison, output_path)

    # 5) JSON summary
    summary = {
        "code": kbli_code,
        "qdrant_found": qdrant_data is not None,
        "oss_found": oss_data is not None,
        "comparison": comparison,
        "report_path": output_path,
    }
    print("\n=== JSON SUMMARY ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    import sys
    
    code = sys.argv[1] if len(sys.argv) > 1 else "01111"
    
    # Se c'è un file come secondo argomento, leggi i dati OSS da lì
    oss_data = None
    if len(sys.argv) > 2:
        oss_file = sys.argv[2]
        if os.path.exists(oss_file):
            with open(oss_file, "r", encoding="utf-8") as f:
                oss_data = f.read()
        else:
            # Se non è un file, assume che sia il testo OSS diretto
            oss_data = oss_file
    
    main(code, oss_manual_data=oss_data)
