#!/usr/bin/env python3
"""
Platinum KBLI KG Extractor
--------------------------
Extracts Knowledge Graph nodes/edges from the Platinum Atlas 
and saves to JSON (bypassing DB connection errors).
"""

import json
import os
import sys
from typing import Dict, List

ATLAS_PATH = os.path.join(
    os.path.dirname(__file__),
    "../../reports/kbli_extraction/kbli_universal_atlas_polished.json"
)

OUTPUT_PATH = "kbli_platinum_kg_processed.json"

# Pivot Logic (Same as Ingestion)
PIVOT_STRATEGIES = {
    "70209": "62193",  # Consulting -> Blockchain
    "73100": "63122",  # Marketing -> Digital Portal
    "55901": "62110",  # Villa Mgmt -> Software Publisher
    "47111": "47112",  # Minimarket Chain -> Standalone
}

def extract_graph_elements(code: str, data: Dict) -> Dict:
    nodes = []
    edges = []
    
    # 1. Main KBLI Node
    kbli_id = f"kbli_{code}"
    nodes.append({
        "id": kbli_id,
        "type": "kbli_code",
        "name": f"{code} - {data.get('title')}",
        "props": {
            "code": code,
            "risk": data.get('risk_data', {}).get('tingkat_risiko'),
            "sector": data.get('risk_data', {}).get('sektor')
        }
    })

    # 2. Risk Node
    risk_level = data.get('risk_data', {}).get('tingkat_risiko')
    if risk_level:
        risk_id = f"risk_{risk_level.lower().replace(' ', '_')}"
        nodes.append({
            "id": risk_id, "type": "risk_level", "name": risk_level, "props": {}
        })
        edges.append({
            "source": kbli_id, "target": risk_id, "type": "HAS_RISK", "props": {}
        })

    # 3. Intelligence / Regulatory Nodes
    for notice in data.get('legal_notices', []):
        tags = notice.get('tags', [])
        title = notice.get('title', '')
        
        # Zoning (Pink Zone)
        if 'PINK_ZONE_ONLY' in tags or 'Pink Zone' in title:
            nodes.append({"id": "zone_pink", "type": "zone", "name": "Pink Zone (Pariwisata)", "props": {}})
            edges.append({"source": kbli_id, "target": "zone_pink", "type": "RESTRICTED_TO", "props": {"reason": "Sarbagita Moratorium"}})

        # SIPA Water Permit
        if 'SIPA_REQUIRED' in tags or 'SIPA' in title:
            nodes.append({"id": "permit_sipa", "type": "permit", "name": "SIPA (Water License)", "props": {}})
            edges.append({"source": kbli_id, "target": "permit_sipa", "type": "REQUIRES_PERMIT", "props": {}})

        # Sertifikat Laik Sehat (SLS)
        if 'SLS' in title:
            nodes.append({"id": "permit_sls", "type": "permit", "name": "Sertifikat Laik Sehat", "props": {}})
            edges.append({"source": kbli_id, "target": "permit_sls", "type": "REQUIRES_PERMIT", "props": {}})

        # Moratorium Ingub 6
        if 'Ingub 6/2025' in title or 'BLOCKED_BY_MORATORIUM' in tags:
            nodes.append({"id": "reg_ingub6_2025", "type": "regulation", "name": "Ingub Bali 6/2025", "props": {}})
            edges.append({"source": kbli_id, "target": "reg_ingub6_2025", "type": "BLOCKED_BY", "props": {}})

        # Governor Veto (PKKPR)
        if 'PKKPR_DISCRETION_RISK' in tags:
            nodes.append({"id": "risk_governor_veto", "type": "risk_factor", "name": "Governor Veto (PKKPR)", "props": {}})
            edges.append({"source": kbli_id, "target": "risk_governor_veto", "type": "SUBJECT_TO_SCRUTINY", "props": {}})

    # 4. Strategic Pivots
    if code in PIVOT_STRATEGIES:
        target_code = PIVOT_STRATEGIES[code]
        target_id = f"kbli_{target_code}"
        edges.append({
            "source": kbli_id, 
            "target": target_id, 
            "type": "HAS_pIVOT_STRATEGY", 
            "props": {"type": "Regulatory Arbitrage"}
        })

    # 5. Inter-Domain Bridges (The Business OS Layer)
    
    # 5A. Immigration Bridge (Visa)
    # Logic: Tech/Digital -> E33G (Digital Nomad Golden Visa) & E23Y (Digital Expert)
    if code.startswith("62") or code.startswith("63") or code == "70209":
        # E33G is an ALTERNATIVE to having a KBLI (Personal Remote Work)
        nodes.append({"id": "visa_E33G", "type": "visa_type", "name": "E33G - Remote Worker Golden Visa", "props": {}})
        edges.append({"source": kbli_id, "target": "visa_E33G", "type": "ALTERNATIVE_PATH", "props": {"note": "Strictly Remote. Cannot be Director/Commissioner."}})
        
        # E23Y is for WORKING in the KBLI (Local Entity)
        nodes.append({"id": "visa_E23Y", "type": "visa_type", "name": "E23Y - Digital Expert Work Visa", "props": {}})
        edges.append({"source": kbli_id, "target": "visa_E23Y", "type": "ALLOWS_VISA", "props": {"suitability": "Employment in PT PMA"}})
    
    # Logic: Investor Preferred Sectors -> E28A (Investor KITAS)

    pma_allowed = data.get('pma_data', {}).get('allowed', True)
    if pma_allowed:
         nodes.append({"id": "visa_E28A", "type": "visa_type", "name": "E28A - Investor KITAS", "props": {}})
         edges.append({"source": kbli_id, "target": "visa_E28A", "type": "ALLOWS_VISA", "props": {"condition": "Shareholder > 10BN IDR"}})

    # 5B. Property Bridge (Zoning/Titles)
    sector = data.get('risk_data', {}).get('sektor', '').lower()
    
    # Tourism -> Commercial/Tourism Zoning + HGB Title
    if 'pariwisata' in sector or code.startswith("55"):
        nodes.append({"id": "zone_commercial", "type": "zoning_type", "name": "Zona Perdagangan & Jasa (Kuning/Merah)", "props": {}})
        nodes.append({"id": "title_hgb", "type": "land_title", "name": "Hak Guna Bangunan (HGB)", "props": {}})
        
        edges.append({"source": kbli_id, "target": "zone_commercial", "type": "REQUIRES_ZONING", "props": {}})
        edges.append({"source": kbli_id, "target": "title_hgb", "type": "RECOMMENDS_TITLE", "props": {"reason": "Commercial Entity"}})

    # Agriculture -> Green Zone Allowed + Hak Pakai
    elif 'pertanian' in sector or code.startswith("01"):
        nodes.append({"id": "zone_green", "type": "zoning_type", "name": "Jalur Hijau (Green Zone)", "props": {}})
        nodes.append({"id": "title_hak_pakai", "type": "land_title", "name": "Hak Pakai", "props": {}})
        
        edges.append({"source": kbli_id, "target": "zone_green", "type": "ALLOWED_IN_ZONE", "props": {"note": "Strictly for framing"}})
        edges.append({"source": kbli_id, "target": "title_hak_pakai", "type": "RECOMMENDS_TITLE", "props": {}})

    # 5C. Tax Bridge (Incentives)
    # Logic: Micro Scale -> PP 23/2018 (0.5% Flat Tax)
    # We check if KBLI scope mentions "Mikro" or logic defaults. 
    # (Simplified: All non-high risk can technically start Mikro)
    risk_level = data.get('risk_data', {}).get('tingkat_risiko', '')
    if risk_level in ['Rendah', 'Menengah Rendah']:
        nodes.append({"id": "tax_rule_pp23", "type": "tax_rule", "name": "PP 23/2018 (UMKM 0.5%)", "props": {}})
        edges.append({"source": kbli_id, "target": "tax_rule_pp23", "type": "ELIGIBLE_FOR_TAX_INCENTIVE", "props": {"condition": "Revenue < 4.8BN IDR"}})

    # Logic: Pioneer Industries (Metal, Oil, Chem) -> Tax Holiday
    if code.startswith("24") or code.startswith("20"): # Basic Metals, Chemicals
        nodes.append({"id": "tax_incentive_holiday", "type": "tax_rule", "name": "Tax Holiday (PMK 130/2020)", "props": {}})
        edges.append({"source": kbli_id, "target": "tax_incentive_holiday", "type": "MAY_QUALIFY_FOR", "props": {"condition": "High Investment"}})

    return {"nodes": nodes, "edges": edges}

def main():
    print(f"Loading Atlas: {ATLAS_PATH}")
    with open(ATLAS_PATH, 'r') as f:
        data = json.load(f).get('data', {})

    all_nodes = []
    all_edges = []

    print(f"Processing {len(data)} records...")
    for code, info in data.items():
        res = extract_graph_elements(code, info)
        all_nodes.extend(res['nodes'])
        all_edges.extend(res['edges'])

    output = {
        "generated_at": str(sys.version), # placeholder for timestamp
        "stats": {
            "kbli_count": len(data),
            "nodes": len(all_nodes),
            "edges": len(all_edges)
        },
        "nodes": all_nodes,
        "edges": all_edges
    }
    
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"Saved {len(all_nodes)} nodes and {len(all_edges)} edges to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
