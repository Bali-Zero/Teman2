#!/usr/bin/env python3
"""
Platinum KBLI KG Extractor
--------------------------
Extracts Knowledge Graph nodes/edges from the Platinum Atlas 
and saves to JSON (bypassing DB connection errors).

STRATEGY: LEAN GRAPH (Safe Mode)
- Extracts ONLY factual nodes (KBLI, Risk, Explicit Regs).
- NO inferred edges (Visa, Tax, etc.) to prevent hallucination.
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

# Pivot Logic (Same as Ingestion - Strategic Knowledge)
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

    # 3. Intelligence / Regulatory Nodes (Explicit)
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

    # 4. Regional Restrictions (Moratoriums like Ingub 6)
    for restriction in data.get('regional_restrictions', []):
        source = restriction.get('source', '')
        if 'INGUB' in source:
            nodes.append({"id": "reg_ingub6_2025", "type": "regulation", "name": "Ingub Bali 6/2025", "props": {}})
            edges.append({"source": kbli_id, "target": "reg_ingub6_2025", "type": "BLOCKED_BY", "props": {"scope": restriction.get("scope")}})

    # 5. Strategic Pivots
    if code in PIVOT_STRATEGIES:
        target_code = PIVOT_STRATEGIES[code]
        target_id = f"kbli_{target_code}"
        edges.append({
            "source": kbli_id, 
            "target": target_id, 
            "type": "HAS_pIVOT_STRATEGY", 
            "props": {"type": "Regulatory Arbitrage"}
        })

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
        "generated_at": str(sys.version),
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
