import json

def analyze_loot():
    print("--- 🔬 AUTOPSIA DEL BOTTINO (JSON ANALYSIS) ---")
    
    try:
        with open("heist_catalog.json", "r") as f:
            data = json.load(f)
            
        resources = data.get('resources', [])
        print(f"📂 Analisi di {len(resources)} risorse...\n")
        
        found_endpoints = []
        
        for r in resources:
            title = r.get('title', 'No Title')
            pk = r.get('pk', 'No ID')
            
            # Cerchiamo link nascosti nei metadati
            links = r.get('links', [])
            distribution = r.get('distribution_url', '')
            csw = r.get('csw_wms_url', '')
            
            print(f"🔹 [{pk}] {title}")
            
            # Se troviamo un link WMS esplicito
            if csw:
                print(f"   🔥 WMS FOUND: {csw}")
                found_endpoints.append(csw)
                
            # Ispezioniamo i link generici
            for l in links:
                url = l.get('url', '')
                l_type = l.get('link_type', '')
                if 'wms' in url or 'geoserver' in url or 'ows' in url:
                     print(f"   🔥 HIDDEN LINK ({l_type}): {url}")
                     found_endpoints.append(url)

        print("\n--- 🏁 RISULTATO ---")
        if found_endpoints:
            print(f"🎯 Abbiamo trovato {len(found_endpoints)} indirizzi server diretti.")
            print("Questi sono i punti di ingresso per bypassare il portale.")
        else:
            print("❌ Nessun indirizzo WMS esplicito trovato nel JSON.")
            
    except FileNotFoundError:
        print("⚠️ Errore: File 'heist_catalog.json' non trovato. Esegui prima la rapina.")

if __name__ == "__main__":
    analyze_loot()
