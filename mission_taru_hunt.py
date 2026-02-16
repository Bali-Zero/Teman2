import requests
import xml.etree.ElementTree as ET
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- I SOSPETTI (LISTA TARGET) ---
# Questi sono tutti i domini noti del ministero per la pianificazione
TARGETS = [
    # 1. GISTARU (Il principale)
    "https://gistaru.atrbpn.go.id/geoserver/ows",
    # 2. TATARUANG (Il vecchio nome)
    "https://tataruang.atrbpn.go.id/geoserver/ows",
    # 3. BITR (Basis Informasi Tata Ruang - Spesso usato per i dati tecnici)
    "https://bitr.atrbpn.go.id/geoserver/ows",
    # 4. FP2B (Server specifico per Bali/Java)
    "https://fp2b.atrbpn.go.id/geoserver/ows",
    # 5. GEOPORTAL BADUNG (Se è vivo)
    "https://geoportal.badungkab.go.id/geoserver/ows"
]

def scan_capabilities():
    print("--- 📡 OPERATION TARU HUNT (SERVER SCAN) ---")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    found_something = False

    for url in TARGETS:
        print(f"\n🔭 Pinging: {url} ...")
        
        # Chiediamo il MENU DEL GIORNO (GetCapabilities)
        params = {
            "service": "WFS",
            "version": "1.0.0",
            "request": "GetCapabilities"
        }
        
        try:
            # Timeout breve (5s) per scartare i server morti
            resp = requests.get(url, params=params, headers=headers, verify=False, timeout=10)
            
            if resp.status_code == 200:
                if "FeatureType" in resp.text:
                    print("   ✅ JACKPOT! Server Attivo e WFS Aperto.")
                    found_something = True
                    
                    # Analisi rapida: Quanti layer ci sono?
                    layer_count = resp.text.count("<FeatureType>")
                    print(f"   📦 Layers Disponibili: {layer_count}")
                    
                    # Cerchiamo Bali dentro la risposta
                    if "bali" in resp.text.lower() or "badung" in resp.text.lower():
                        print("   🎯 TARGET ACQUISITO: Trovata menzione di BALI/BADUNG!")
                        
                        # Salviamo la lista completa per leggerla con calma
                        filename = f"capabilities_{url.split('//')[1].split('.')[0]}.xml"
                        with open(filename, "w") as f:
                            f.write(resp.text)
                        print(f"   💾 Lista salvata in: {filename}")
                        
                        # Proviamo a stampare i nomi dei layer interessanti al volo
                        root = ET.fromstring(resp.content)
                        # Namespace XML infernale di OGC
                        ns = {'wfs': 'http://www.opengis.net/wfs', 'ows': 'http://www.opengis.net/ows'}
                        
                        print("   🔎 Anteprima Layer Bali:")
                        # Parsing grezzo perché i namespace variano
                        lines = resp.text.split('\n')
                        for line in lines:
                            if "<Name>" in line and ("bali" in line.lower() or "badung" in line.lower() or "rtrw" in line.lower()):
                                clean_name = line.replace("<Name>", "").replace("</Name>", "").strip()
                                print(f"      🔹 {clean_name}")
                                
                    else:
                        print("   ⚠️ Server attivo ma non vedo 'Bali' nella lista immediata.")
                        
                else:
                    print("   ⚠️ Risposta 200 ma non sembra WFS XML.")
            else:
                print(f"   ❌ Errore HTTP {resp.status_code}")
                
        except Exception as e:
            print(f"   💤 Server irraggiungibile ({str(e)[:50]}...)")

    print("\n--- 🏁 FINE SCANSIONE ---")
    if found_something:
        print("💡 PROSSIMO PASSO: Usa il nome del layer trovato (es. 'geonode:rtrw_bali') nello script di download.")

if __name__ == "__main__":
    scan_capabilities()
