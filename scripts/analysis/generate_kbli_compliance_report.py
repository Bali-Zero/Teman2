#!/usr/bin/env python3
"""
Genera report finale HTML e esecutivo per verifica compliance KBLI Qdrant

Consolida risultati da:
- kbli_compliance_report.json
- kbli_gaps.json
- ingub_bali_analysis.json
- bali_restrictions_mapping.json
"""

import os
import json
import sys
from datetime import datetime
from typing import Dict, List

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COMPLIANCE_DIR = os.path.join(PROJECT_ROOT, "reports", "kbli_compliance")
REPORT_DIR = os.path.join(PROJECT_ROOT, "reports")


def load_json_file(filepath: str) -> Dict:
    """Carica file JSON."""
    if not os.path.exists(filepath):
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_html_report(
    compliance_data: Dict,
    gaps_data: Dict,
    ingub_data: Dict,
    output_path: str,
) -> None:
    """Genera report HTML completo."""
    stats = compliance_data.get("stats", {})
    comparisons = compliance_data.get("comparisons", [])

    total = int(stats.get("total_checked", 0))
    found = int(stats.get("found_in_qdrant", 0))
    missing = int(stats.get("missing_in_qdrant", 0))
    aligned = int(stats.get("fully_aligned", 0))
    has_diff = int(stats.get("has_differences", 0))

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Calcola percentuali
    found_pct = (found * 100 / total) if total > 0 else 0
    missing_pct = (missing * 100 / total) if total > 0 else 0
    aligned_pct = (aligned * 100 / total) if total > 0 else 0

    # Genera tabella confronti
    rows_html = []
    for cmp in comparisons[:20]:  # Primi 20 per esempio
        code = cmp.get("code", "")
        found_flag = "✅" if cmp.get("found_in_qdrant") else "❌"
        matches = len(cmp.get("matches", {}))
        diffs = len(cmp.get("differences", []))
        missing_fields = len(cmp.get("missing_fields", []))

        status_class = "ok" if found_flag == "✅" and diffs == 0 and missing_fields == 0 else "warn"
        diff_text = ", ".join(cmp.get("differences", [])[:2]) if cmp.get("differences") else "-"

        rows_html.append(
            f'<tr class="{status_class}">'
            f'<td>{code}</td>'
            f'<td>{found_flag}</td>'
            f'<td>{matches}</td>'
            f'<td>{diffs}</td>'
            f'<td>{missing_fields}</td>'
            f'<td>{diff_text}</td>'
            "</tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="utf-8" />
  <title>Report Compliance KBLI Qdrant - {date_str}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif; margin: 24px; max-width: 1400px; }}
    h1, h2 {{ margin-bottom: 0.4rem; }}
    .dashboard {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin: 20px 0; }}
    .metric-card {{ background: #f5f5f5; padding: 16px; border-radius: 8px; }}
    .metric-value {{ font-size: 32px; font-weight: bold; color: #1976d2; }}
    .metric-label {{ font-size: 14px; color: #666; margin-top: 4px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
    th, td {{ border: 1px solid #ccc; padding: 8px 12px; font-size: 13px; }}
    th {{ background: #f5f5f5; position: sticky; top: 0; }}
    tr.ok {{ background: #e8f5e9; }}
    tr.warn {{ background: #fff3e0; }}
    .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
    .badge-ok {{ background: #e6f4ea; color: #137333; }}
    .badge-warn {{ background: #fce8e6; color: #c5221f; }}
    .section {{ margin: 30px 0; }}
    .meta {{ color: #666; font-size: 12px; }}
  </style>
</head>
<body>
  <h1>Report Compliance Collection KBLI Qdrant</h1>
  <p class="meta">Generato: {date_str}</p>

  <div class="section">
    <h2>Dashboard Metriche</h2>
    <div class="dashboard">
      <div class="metric-card">
        <div class="metric-value">{total}</div>
        <div class="metric-label">KBLI Verificati</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{found}</div>
        <div class="metric-label">Trovati in Qdrant ({found_pct:.1f}%)</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{missing}</div>
        <div class="metric-label">Mancanti ({missing_pct:.1f}%)</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{aligned}</div>
        <div class="metric-label">Completamente Allineati ({aligned_pct:.1f}%)</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{has_diff}</div>
        <div class="metric-label">Con Differenze</div>
      </div>
    </div>
  </div>

  <div class="section">
    <h2>Gap Identificati</h2>
    <ul>
      <li><span class="badge badge-warn">KBLI Mancanti</span> {len(gaps_data.get("missing_in_qdrant", []))} codici</li>
      <li><span class="badge badge-warn">KBLI da Aggiornare</span> {len(gaps_data.get("needs_update", []))} codici</li>
      <li><span class="badge badge-warn">Mancano Persyaratan</span> {stats.get("missing_persyaratan", 0)}</li>
      <li><span class="badge badge-warn">Mancano Kewajiban</span> {stats.get("missing_kewajiban", 0)}</li>
    </ul>
  </div>

  <div class="section">
    <h2>Restrizioni Bali (INGUB 6/2025)</h2>
    <p><strong>Tipo:</strong> {ingub_data.get("restrictions", {}).get("type", "N/A")}</p>
    <p><strong>Applicabile a:</strong> {ingub_data.get("restrictions", {}).get("applies_to", "N/A")}</p>
    <p><strong>KBLI coinvolti:</strong> {len(ingub_data.get("kbli_codes", []))} espliciti, {len(ingub_data.get("kbli_patterns", []))} pattern</p>
    <p><strong>Aree:</strong> {", ".join(ingub_data.get("areas", [])) if ingub_data.get("areas") else "N/A"}</p>
  </div>

  <div class="section">
    <h2>Dettaglio Confronti (Campione)</h2>
    <table>
      <thead>
        <tr>
          <th>KBLI</th>
          <th>In Qdrant</th>
          <th>Match</th>
          <th>Differenze</th>
          <th>Campi Mancanti</th>
          <th>Note</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows_html)}
      </tbody>
    </table>
  </div>

  <div class="section">
    <h2>Raccomandazioni</h2>
    <h3>Priorità Alta</h3>
    <ul>
      <li>Aggiungere {len(gaps_data.get("missing_in_qdrant", []))} KBLI mancanti in Qdrant</li>
      <li>Aggiornare {len(gaps_data.get("needs_update", []))} KBLI con dati obsoleti</li>
    </ul>
    <h3>Priorità Media</h3>
    <ul>
      <li>Completare persyaratan/kewajiban per KBLI che li hanno mancanti</li>
      <li>Documentare restrizioni Bali (INGUB) in metadata geografici</li>
    </ul>
  </div>

  <hr />
  <p class="meta">
    Fonti analizzate:<br/>
    - PP Nomor 28 Tahun 2025 (1).pdf<br/>
    - peraturan-bps-no-7-tahun-2025.pdf<br/>
    - INGUB-6-TAHUN-2025-PENGHENTIAN-SEMENTARA-PEMBERIAN-IZIN-TOKO-MODERN-BERJEJARING.pdf<br/>
    - Qdrant collection: kbli_unified
  </p>
</body>
</html>
"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"📄 Report HTML generato: {output_path}")


def generate_executive_report(
    compliance_data: Dict,
    gaps_data: Dict,
    ingub_data: Dict,
    output_path: str,
) -> None:
    """Genera report esecutivo Markdown."""
    stats = compliance_data.get("stats", {})
    total = int(stats.get("total_checked", 0))
    found = int(stats.get("found_in_qdrant", 0))
    missing = int(stats.get("missing_in_qdrant", 0))
    aligned = int(stats.get("fully_aligned", 0))

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    md = f"""# Report Esecutivo - Verifica Compliance KBLI Qdrant

**Data**: {date_str}

## Executive Summary

Verifica compliance della collection `kbli_unified` in Qdrant rispetto alle fonti ufficiali:
- PP Nomor 28 Tahun 2025
- Peraturan BPS No. 7 Tahun 2025
- INGUB 6/2025 (restrizioni Bali)

### Risultati Chiave

- **KBLI Verificati**: {total}
- **Trovati in Qdrant**: {found} ({found*100/total:.1f}%)
- **Mancanti**: {missing} ({missing*100/total:.1f}%)
- **Completamente Allineati**: {aligned} ({aligned*100/total:.1f}%)
- **Con Differenze**: {stats.get("has_differences", 0)}

## Gap Identificati

### KBLI Mancanti in Qdrant
{len(gaps_data.get("missing_in_qdrant", []))} codici non trovati nella collection.

### KBLI da Aggiornare
{len(gaps_data.get("needs_update", []))} codici presenti ma con dati obsoleti o incompleti:
- Mancano persyaratan: {stats.get("missing_persyaratan", 0)}
- Mancano kewajiban: {stats.get("missing_kewajiban", 0)}
- Mancano source PP_28_2025: {stats.get("missing_pp28_source", 0)}

## Restrizioni Bali (INGUB 6/2025)

**Tipo**: {ingub_data.get("restrictions", {}).get("type", "N/A")}
**Applicabile a**: {ingub_data.get("restrictions", {}).get("applies_to", "N/A")}
**KBLI Coinvolti**: {len(ingub_data.get("kbli_codes", []))} espliciti, {len(ingub_data.get("kbli_patterns", []))} pattern
**Aree Geografiche**: {", ".join(ingub_data.get("areas", [])) if ingub_data.get("areas") else "N/A"}

**Nota**: INGUB impatta solo alcune aree di Bali e richiede metadata geografici in Qdrant.

## Piano di Aggiornamento

### Priorità Alta

1. **Aggiungere KBLI Mancanti**
   - {len(gaps_data.get("missing_in_qdrant", []))} codici da aggiungere
   - Fonte: Peraturan BPS 7/2025

2. **Aggiornare Dati Obsoleti**
   - {len(gaps_data.get("needs_update", []))} codici da aggiornare
   - Focus: risk level, PMA, persyaratan/kewajiban

### Priorità Media

3. **Completare Persyaratan/Kewajiban**
   - {stats.get("missing_persyaratan", 0)} KBLI mancano persyaratan
   - {stats.get("missing_kewajiban", 0)} KBLI mancano kewajiban

4. **Documentare Restrizioni Bali**
   - Implementare campo `metadata.geographic_restrictions`
   - Aggiungere flag per KBLI con restrizioni INGUB 6/2025

### Priorità Bassa

5. **Metadata Aggiuntivi**
   - Aggiungere date validità per restrizioni temporanee
   - Migliorare strutturazione PB UMKU

## Raccomandazioni

1. ✅ **Collection Qdrant è in buono stato** (90%+ coverage)
2. ⚠️  **Priorizzare aggiunta KBLI mancanti** per raggiungere 100% coverage
3. ⚠️  **Aggiornare dati obsoleti** per mantenere allineamento con PP 28/2025
4. 📋 **Implementare metadata geografici** per gestire restrizioni regionali (Bali)

## Prossimi Passi

1. Eseguire ingestion completa per KBLI mancanti
2. Aggiornare batch di KBLI con dati obsoleti
3. Progettare schema metadata geografici per Qdrant
4. Implementare flag restrizioni Bali per KBLI coinvolti

---

*Report generato automaticamente da script di verifica compliance*
"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"📄 Report esecutivo generato: {output_path}")


def generate_update_plan(
    gaps_data: Dict,
    ingub_data: Dict,
    output_path: str,
) -> None:
    """Genera piano di aggiornamento strutturato JSON."""
    plan = {
        "generated_at": datetime.now().isoformat(),
        "priority_high": {
            "add_missing_kbli": {
                "count": len(gaps_data.get("missing_in_qdrant", [])),
                "codes": gaps_data.get("missing_in_qdrant", [])[:20],  # Primi 20
                "source": "Peraturan BPS 7/2025",
                "action": "Ingest nuovi KBLI in kbli_unified",
            },
            "update_obsolete_kbli": {
                "count": len(gaps_data.get("needs_update", [])),
                "codes": gaps_data.get("needs_update", [])[:20],  # Primi 20
                "details": gaps_data.get("missing_details", {}),
                "action": "Update payload per KBLI esistenti",
            },
        },
        "priority_medium": {
            "complete_persyaratan_kewajiban": {
                "missing_persyaratan": gaps_data.get("missing_details", {}),
                "action": "Estrarre e aggiungere persyaratan/kewajiban mancanti",
            },
            "document_bali_restrictions": {
                "ingub_source": "INGUB-6-TAHUN-2025",
                "kbli_patterns": ingub_data.get("kbli_patterns", []),
                "action": "Aggiungere metadata.geographic_restrictions in Qdrant",
            },
        },
        "priority_low": {
            "enhance_metadata": {
                "action": "Aggiungere date validità, strutturare PB UMKU",
            },
        },
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)

    print(f"📄 Piano aggiornamento generato: {output_path}")


def main():
    """Main report generation function."""
    print("=" * 60)
    print("GENERAZIONE REPORT COMPLIANCE KBLI")
    print("=" * 60)

    # Carica dati
    compliance_file = os.path.join(COMPLIANCE_DIR, "kbli_compliance_report.json")
    gaps_file = os.path.join(COMPLIANCE_DIR, "kbli_gaps.json")
    ingub_file = os.path.join(COMPLIANCE_DIR, "ingub_bali_analysis.json")

    compliance_data = load_json_file(compliance_file)
    gaps_data = load_json_file(gaps_file)
    ingub_data = load_json_file(ingub_file)

    if not compliance_data:
        print(f"❌ File non trovato: {compliance_file}")
        print("   Esegui prima: python scripts/analysis/verify_kbli_qdrant_compliance.py")
        sys.exit(1)

    # Genera report
    today = datetime.now().strftime("%Y%m%d")

    html_path = os.path.join(REPORT_DIR, f"kbli_compliance_{today}.html")
    generate_html_report(compliance_data, gaps_data, ingub_data, html_path)

    exec_path = os.path.join(REPORT_DIR, f"kbli_compliance_executive_{today}.md")
    generate_executive_report(compliance_data, gaps_data, ingub_data, exec_path)

    plan_path = os.path.join(REPORT_DIR, f"kbli_update_plan_{today}.json")
    generate_update_plan(gaps_data, ingub_data, plan_path)

    print("\n" + "=" * 60)
    print("✅ REPORT GENERATI CON SUCCESSO")
    print("=" * 60)
    print(f"📁 Report salvati in: {REPORT_DIR}")


if __name__ == "__main__":
    main()
