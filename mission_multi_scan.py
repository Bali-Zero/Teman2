import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURAZIONE ---
WFS_URL = "https://atlas.atrbpn.go.id/geoserver/ows"
LAT = -8.6433
LONG = 115.1544

# BBOX (1km x 1km)
MIN_X = LONG - 0.005
MIN_Y = LAT - 0.005
MAX_X = LONG + 0.005
MAX_Y = LAT + 0.005
BBOX_PARAM = f"{MIN_X},{MIN_Y},{MAX_X},{MAX_Y},EPSG:4326"

# Lista Layer da Testare
LAYERS_TO_TEST = [
    {"name": "geonode:desa", "desc": "Confini Villaggi (Must Have)"},
    {"name": "geonode:lbs_parsial", "desc": "LSD (Risaie Protette)"},
    {"name": "geonode:kab0_638966ed58b76346ce15ca84ea7b8c7e", "desc": "Confini Kabupaten"}
]

def multi_layer_scan():
    print("--- 🔫 OPERATION SCATTERSHOT (MULTI-LAYER TEST) ---")
    print(f"📍 Area: Dalung ({LAT}, {LONG})")
    
    success_count = 0
    
    for layer in LAYERS_TO_TEST:
        l_name = layer['name']
        print(f"\n📡 Testing: {layer['desc']} ({l_name})...")
        
        params = {
            "service": "WFS",
            "version": "1.0.0",
            "request": "GetFeature",
            "typeName": l_name,
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "bbox": BBOX_PARAM,
            "maxFeatures": 3
        }
        
        try:
            resp = requests.get(WFS_URL, params=params, verify=False, timeout=15)
            
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    feats = data.get('features', [])
                    count = len(feats)
                    
                    if count > 0:
                        print(f"   ✅ HIT! Trovati {count} elementi.")
                        print(f"   📝 Esempio: {json.dumps(feats[0]['properties'], indent=2)}")
                        success_count += 1
                        
                        # Salviamo il file per analisi
                        safe_name = l_name.replace(":", "_")
                        with open(f"scan_{safe_name}.json", "w") as f:
                            json.dump(data, f, indent=2)
                    else:
                        print("   ⚠️ Layer vuoto in questa zona.")
                except:
                    print("   ❌ Errore parsing JSON.")
            else:
                print(f"   ❌ HTTP Error {resp.status_code}")
                
        except Exception as e:
            print(f"   ⚠️ Errore Connessione: {str(e)}")

    print(f"\n--- 🏁 RAPPORTO FINALE: {success_count}/{len(LAYERS_TO_TEST)} Layer attivi ---")

if __name__ == "__main__":
    multi_layer_scan()

