import asyncio
from playwright.async_api import async_playwright
import json

# --- TARGET ---
TARGET_URL = "https://bhumi.atrbpn.go.id/peta"

async def intercept_traffic():
    print("--- 🦅 OPERATION ROSETTA STONE (OGC / GEOSERVER SNIFFER) ---")
    print(f"📡 Apertura Finestra su: {TARGET_URL}")
    print("🎯 OBIETTIVO: Catturare chiamate WMS, WFS, GeoNode e Vector Tiles.")
    
    async with async_playwright() as p:
        # Usiamo WebKit (Safari Engine) per stabilità su Mac M4
        browser = await p.webkit.launch(headless=False) 
        
        # Simuliamo un browser desktop standard in Indonesia
        context = await browser.new_context(
            viewport={'width': 1440, 'height': 900},
            locale='id-ID',
            timezone_id='Asia/Makassar'
        )
        page = await context.new_page()

        intercepted_endpoints = set()

        # --- IL NUOVO FILTRO "ROSETTA" ---
        # Ascolta tutti i dialetti cartografici (Proprietari e Open Source)
        def handle_request(request):
            url = request.url
            
            # Keywords strategiche per GeoServer e ArcGIS
            keywords = [
                "wms",          # Web Map Service (Standard)
                "wfs",          # Web Feature Service (Dati vettoriali)
                "ows",          # Open Web Services
                "geoserver",    # Il motore software probabile
                "geonode",      # Il portale che abbiamo visto
                "MapServer",    # ESRI Legacy
                "FeatureServer",# ESRI Vector
                "pbf",          # Vector Tiles (Moderni)
                "mvt",          # Mapbox Vector Tiles
                "xyz",          # Coordinate Tiles
                "layers=",      # Parametro chiave WMS
                "typeName="     # Parametro chiave WFS
            ]
            
            # Logica di filtraggio:
            # Se l'URL contiene una keyword GIS...
            if any(k in url for k in keywords):
                # ...e NON è spazzatura statica (CSS, JS, Font)
                if not any(x in url for x in [".css", ".js", ".woff", ".svg", ".ico"]):
                    # Nota: NON escludiamo .png o .jpg perché WMS restituisce immagini!
                    # Ma vogliamo solo quelle che hanno parametri lunghi
                    if len(url) > 50: 
                        print(f"   🔥 CATTURATO: {url[:100]}...")
                        intercepted_endpoints.add(url)

        # Attiva l'orecchio elettronico
        page.on("request", handle_request)

        try:
            print("⏳ Caricamento pagina (Attesa 10s)...")
            await page.goto(TARGET_URL, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)

            # --- FASE 1: BREACH ENTRY (Chiudi Popup) ---
            print("🔨 Tentativo chiusura popup/disclaimer...")
            buttons_to_try = [
                "text=Saya Mengerti", "text=Saya Setuju", 
                "text=Tutup", "text=Close", "text=Mengerti",
                "button.close", "button[aria-label='Close']",
                ".modal-footer button"
            ]
            for btn in buttons_to_try:
                try:
                    if await page.is_visible(btn):
                        print(f"   CLICK -> {btn}")
                        await page.click(btn)
                        await page.wait_for_timeout(1000)
                except:
                    pass

            # --- FASE 2: HUMAN INTERVENTION REQUEST ---
            # I sistemi GeoNode complessi spesso caricano i layer solo se apri il menu
            print("\n👉 ORA TOCCA A TE, COMANDANTE!")
            print("1. Cerca il menu 'Daftar Layer' o l'icona a strati sulla destra/sinistra.")
            print("2. Attiva un layer a caso (es. 'RTRW', 'Zona', 'Bidang Tanah').")
            print("3. Muovi la mappa.")
            print("⏳ Hai 20 secondi per farlo mentre io ascolto...")
            
            await page.wait_for_timeout(20000) 

            # --- FASE 3: SHAKE AUTOMATICO (Backup) ---
            print("🤖 Eseguo Shake finale per sicurezza...")
            await page.mouse.wheel(0, -500) # Zoom In
            await page.wait_for_timeout(2000)
            await page.mouse.wheel(0, 500)  # Zoom Out

        except Exception as e:
            print(f"⚠️ Nota: {str(e)}")

        print("\n--- 📦 ANALISI BOTTINO ---")
        if intercepted_endpoints:
            results = list(intercepted_endpoints)
            
            # Classifica i risultati
            wms_hits = [u for u in results if "wms" in u.lower() or "ows" in u.lower()]
            arcgis_hits = [u for u in results if "MapServer" in u]
            
            print(f"🎯 Totale Endpoint Catturati: {len(results)}")
            print(f"🗺️  WMS/GeoServer Hits: {len(wms_hits)}")
            print(f"🏢 ArcGIS Hits: {len(arcgis_hits)}")
            
            # Mostra i migliori candidati WMS (contengono layers=...)
            print("\n💎 TOP WMS CANDIDATES (Cerca 'layers=' qui sotto):")
            for url in wms_hits[:5]:
                print(f"   📍 {url[:150]}...") # Tronca per leggibilità
                
            with open("scan_rosetta.json", "w") as f:
                json.dump(results, f, indent=2)
                print("\n✅ Salvato in scan_rosetta.json")
        else:
            print("❌ Nessun traffico GIS rilevato.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(intercept_traffic())
