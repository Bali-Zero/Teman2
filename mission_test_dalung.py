import requests
import json
import urllib3

# Disabilita warning SSL (il governo usa certificati spesso scaduti)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- COORDINATE DALUNG (Ufficio/Zona Target) ---
# Sostituisci con coordinate precise se vuoi testare un terreno specifico
LAT = -8.6433
LONG = 115.1544

# --- IL BERSAGLIO (Layer ID 161 - Diritti di Terra) ---
# Endpoint WFS scoperto nella missione precedente
WFS_URL = "https://atlas.atrbpn.go.id/geoserver/ows"
LAYER_NAME = "geonode:status_hak_atas_tanah_berbasis_bidang"

def query_land_rights():
    print("--- 🌍 OPERATION GROUND TRUTH (DALUNG TEST) ---")
    print(f"📍 Target: {LAT}, {LONG}")
    print(f"📡 Interrogando Layer: {LAYER_NAME}")
    
    # Costruiamo la query WFS standard
    # CQL_FILTER è il linguaggio SQL per le mappe.
    # Chiediamo: "Dammi le feature che INTERSECANO questo punto"
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": LAYER_NAME,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        # Filtro spaziale: INTERSECTS(geometry_column, POINT(long lat))
        "cql_filter": f"INTERSECTS(the_geom, POINT({LONG} {LAT}))"
    }

    # Headers per simulare un browser (anti-bot basico)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://atlas.atrbpn.go.id/"
    }

    try:
        print("⏳ Invio richiesta WFS...")
        response = requests.get(WFS_URL, params=params, headers=headers, verify=False, timeout=15)
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                features = data.get('features', [])
                
                print(f"\n✅ SUCCESSO! Trovati {len(features)} poligoni.")
                
                if features:
                    print("--- 📄 DATI CATASTALI ESTRATTI ---")
                    for f in features:
                        props = f.get('properties', {})
                        # Stampiamo tutte le proprietà trovate
                        for key, value in props.items():
                            print(f"   🔹 {key}: {value}")
                            
                    # Salviamo per analisi futura
                    with open("dalung_land_data.json", "w") as f:
                        json.dump(data, f, indent=2)
                        print("\n💾 Dati salvati in 'dalung_land_data.json'")
                else:
                    print("⚠️ Nessun dato su questo punto esatto (Forse è strada o zona non registrata).")
                    print("   Prova a spostare le coordinate di qualche metro.")
                    
            except json.JSONDecodeError:
                print("❌ Errore: Il server non ha risposto con JSON valido.")
                print(f"Snippet risposta: {response.text[:200]}")
        else:
            print(f"❌ Errore Server: {response.text[:200]}")
            
    except Exception as e:
        print(f"⚠️ Eccezione Critica: {str(e)}")

if __name__ == "__main__":
    query_land_rights()
