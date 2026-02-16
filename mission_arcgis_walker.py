import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURAZIONE ---
ROOT_URL = "https://gistaru.atrbpn.go.id/arcgis/rest/services"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def walk_server():
    print("--- 📂 OPERATION DEEP DIVE (ARCGIS WALKER) ---")
    print(f"📡 Target Root: {ROOT_URL}")
    
    try:
        # 1. SCANSIONE ROOT
        resp = requests.get(ROOT_URL, params={"f": "json"}, headers=HEADERS, verify=False, timeout=10)
        
        if resp.status_code != 200:
            print(f"❌ Errore Root: {resp.status_code}")
            return

        data = resp.json()
        folders = data.get("folders", [])
        services = data.get("services", [])
        
        print(f"✅ Accesso Garantito. Trovate {len(folders)} Cartelle e {len(services)} Servizi Root.")
        
        found_maps = []

        # 2. SCANSIONE CARTELLE (LEVEL 1)
        # Gistaru organizza tutto in cartelle come "RDTR", "RTRW", "Penertiban"
        for folder in folders:
            folder_url = f"{ROOT_URL}/{folder}"
            print(f"\n📂 Esplorando Cartella: [{folder}]...")
            
            try:
                f_resp = requests.get(folder_url, params={"f": "json"}, headers=HEADERS, verify=False, timeout=10)
                f_data = f_resp.json()
                f_services = f_data.get("services", [])
                
                print(f"   ↳ Contiene {len(f_services)} servizi.")
                
                # Cerca BALI in questa cartella
                for s in f_services:
                    s_name = s.get("name") # Es: RDTR/Bali_Badung_2024
                    s_type = s.get("type") # Es: MapServer
                    
                    # Logica di ricerca (Case Insensitive)
                    if "bali" in s_name.lower() or "badung" in s_name.lower() or "denpasar" in s_name.lower() or "sarbagita" in s_name.lower():
                        full_url = f"{ROOT_URL}/{s_name}/{s_type}"
                        print(f"   🔥 TROVATO: {s_name} ({s_type})")
                        found_maps.append({
                            "name": s_name,
                            "url": full_url,
                            "folder": folder
                        })
            except Exception as e:
                print(f"   ⚠️ Errore lettura cartella {folder}: {e}")

        # 3. RAPPORTO FINALE
        print("\n\n--- 🏁 RAPPORTO FINALE ---")
        if found_maps:
            print(f"🎯 Abbiamo {len(found_maps)} Mappe di Bali confermate:")
            for m in found_maps:
                print(f"   💎 {m['name']}")
                print(f"      URL: {m['url']}")
            
            # Salvataggio
            with open("gistaru_bali_maps.json", "w") as f:
                json.dump(found_maps, f, indent=2)
                print("\n💾 Lista salvata in 'gistaru_bali_maps.json'")
        else:
            print("❌ Nessuna mappa con nome 'Bali/Badung' trovata nelle cartelle pubbliche.")
            print("   (Potrebbero usare codici numerici o nomi generici come 'Zona_5')")

    except Exception as e:
        print(f"⚠️ Crash Critico: {str(e)}")

if __name__ == "__main__":
    walk_server()
