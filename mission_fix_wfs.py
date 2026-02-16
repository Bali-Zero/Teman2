import requests
import xml.etree.ElementTree as ET
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURAZIONE ---
WFS_URL = "https://atlas.atrbpn.go.id/geoserver/ows"
LAYER_NAME = "geonode:status_hak_atas_tanah_berbasis_bidang"
# Coordinate Dalung
LAT = -8.6433
LONG = 115.1544

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fix_and_query():
    print("--- 🔧 WFS DIAGNOSTIC & REPAIR ---")
    
    # 1. SCOPRI IL NOME DELLA COLONNA (SCHEMA)
    print("1️⃣  Scarico lo Schema del Layer...")
    params_schema = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "DescribeFeatureType",
        "typeName": LAYER_NAME
    }
    
    try:
        resp = requests.get(WFS_URL, params=params_schema, headers=HEADERS, verify=False, timeout=10)
        
        # Cerchiamo la parola chiave 'gml:GeometryPropertyType' o simile nell'XML
        geom_col = "the_geom" # Default fallback
        
        if resp.status_code == 200:
            content = resp.text
            if "geom" in content:
                print("   ✅ Schema Trovato!")
                # Parsing grezzo per trovare il nome del campo geometria
                # Cerca <xsd:element name="NOME" type="gml:GeometryPropertyType...
                import re
                match = re.search(r'name="([^"]+)"[^>]*type="gml:(?:Multi)?(?:Polygon|Geometry)PropertyType"', content)
                if match:
                    geom_col = match.group(1)
                    print(f"   🎯 Colonna Geometria Rilevata: '{geom_col}'")
                else:
                    print("   ⚠️ Impossibile estrarre nome esatto, provo varianti comuni.")
            else:
                print("   ⚠️ Schema illeggibile, uso default.")
        
        # 2. RIPROVA LA QUERY CON I PARAMETRI CORRETTI
        print(f"\n2️⃣  Riprovo Query su Dalung con colonna '{geom_col}'...")
        
        # Varianti di filtro per essere sicuri
        # Nota: Usiamo outputFormat='json' (senza application/) che è più compatibile
        params_query = {
            "service": "WFS",
            "version": "1.0.0",
            "request": "GetFeature",
            "typeName": LAYER_NAME,
            "outputFormat": "json", 
            "srsName": "EPSG:4326",
            # Usiamo DWAITHIN invece di INTERSECTS perché è più tollerante se il punto è appena fuori
            # DWITHIN(geom, POINT, distanza, unit) -> Cerca entro 0.0001 gradi (circa 10 metri)
            "cql_filter": f"DWITHIN({geom_col}, POINT({LONG} {LAT}), 0.0001, meters)"
        }
        
        resp_q = requests.get(WFS_URL, params=params_query, headers=HEADERS, verify=False, timeout=15)
        
        if resp_q.status_code == 200:
            if "ServiceException" in resp_q.text:
                print("\n❌ ERRORE WFS (Ancora):")
                print(resp_q.text[:300]) # Stampa l'errore XML per capire
            else:
                try:
                    data = resp_q.json()
                    feats = data.get('features', [])
                    print(f"\n✅ SUCCESSO TOTALE! Trovati {len(feats)} risultati.")
                    if feats:
                        props = feats[0]['properties']
                        print("--- DATI CAMPIONE ---")
                        for k, v in props.items():
                            print(f"   🔹 {k}: {v}")
                except:
                    print(f"\n⚠️ Risposta ricevuta ma non è JSON: {resp_q.text[:100]}")
        else:
            print(f"❌ HTTP Error: {resp_q.status_code}")

    except Exception as e:
        print(f"⚠️ Crash: {str(e)}")

if __name__ == "__main__":
    fix_and_query()
