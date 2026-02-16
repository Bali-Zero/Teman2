import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURAZIONE ---
WFS_URL = "https://atlas.atrbpn.go.id/geoserver/ows"
LAYER_NAME = "geonode:status_hak_atas_tanah_berbasis_bidang"

# Centro Dalung
LAT = -8.6433
LONG = 115.1544

# Creiamo un quadrato di circa 1km x 1km intorno al punto
# 0.01 gradi sono circa 1.1km all'equatore
MIN_X = LONG - 0.005
MIN_Y = LAT - 0.005
MAX_X = LONG + 0.005
MAX_Y = LAT + 0.005

def scan_area():
    print("--- 📡 OPERATION CARPET BOMBING (BBOX SCAN) ---")
    print(f"📍 Area Scan: {MIN_X},{MIN_Y} to {MAX_X},{MAX_Y}")
    
    # Parametri BBOX standard (minx, miny, maxx, maxy)
    # Questa è la richiesta più robusta che esiste in GIS.
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": LAYER_NAME,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "bbox": f"{MIN_X},{MIN_Y},{MAX_X},{MAX_Y},EPSG:4326",
        "maxFeatures": 5  # Prendiamone solo 5 per non intasare il terminale
    }

    try:
        print("⏳ Scansione Area Vasta...")
        response = requests.get(WFS_URL, params=params, verify=False, timeout=20)
        
        if response.status_code == 200:
            try:
                data = response.json()
                features = data.get('features', [])
                count = len(features)
                
                print(f"\n✅ RISULTATO: Trovati {count} terreni nell'area.")
                
                if count > 0:
                    print("--- 🏆 ESEMPIO DATO TROVATO ---")
                    # Prendiamo il primo terreno a caso per vedere cosa c'è dentro
                    first_land = features[0]
                    props = first_land.get('properties', {})
                    
                    for k, v in props.items():
                        print(f"   🔹 {k}: {v}")
                        
                    # Salviamo tutto
                    with open("dalung_area_scan.json", "w") as f:
                        json.dump(data, f, indent=2)
                        print("\n💾 Dump completo salvato in 'dalung_area_scan.json'")
                else:
                    print("⚠️ Area vuota. Ipotesi: Questo layer non copre Badung o usa coordinate diverse.")
                    
            except json.JSONDecodeError:
                print("❌ Errore JSON. Risposta Server:")
                print(response.text[:200])
        else:
            print(f"❌ HTTP {response.status_code}")
            
    except Exception as e:
        print(f"⚠️ Errore Connessione: {str(e)}")

if __name__ == "__main__":
    scan_area()

