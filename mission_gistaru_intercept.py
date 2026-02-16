import asyncio
from playwright.async_api import async_playwright
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- TARGET: LA MAPPA UFFICIALE DI ZONIZZAZIONE ---
# Questa è la pagina che un umano visiterebbe
MAP_VIEWER_URL = "https://gistaru.atrbpn.go.id/rtrw/"

async def intercept_gistaru():
    print("--- 🦅 OPERATION ESRI SWITCH (GISTARU INTERCEPT) ---")
    
    # 1. VERIFICA RAPIDA ENDPOINT ARCGIS
    print("\n📡 Phase 1: ArcGIS Endpoint Check...")
    arcgis_candidates = [
        "https://gistaru.atrbpn.go.id/arcgis/rest/services",
        "https://tataruang.atrbpn.go.id/arcgis/rest/services",
        "https://gis.atrbpn.go.id/arcgis/rest/services"
    ]
    
    for url in arcgis_candidates:
        try:
            # ArcGIS risponde bene se chiedi f=json
            resp = requests.get(url, params={"f": "json"}, verify=False, timeout=5)
            if resp.status_code == 200 and "currentVersion" in resp.text:
                print(f"   ✅ JACKPOT! Server ArcGIS trovato: {url}")
                print("      (Questo è l'indirizzo che cercavamo!)")
            else:
                print(f"   ❌ {url} -> {resp.status_code}")
        except:
            print(f"   💤 {url} -> Unreachable")

    # 2. INTERCETTAZIONE VISIVA (Se la Phase 1 fallisce o per confermare)
    print("\n📡 Phase 2: Visual Intercept (Playwright)...")
    print(f"   Apro il browser su: {MAP_VIEWER_URL}")
    print("   OBIETTIVO: Trovare chiamate 'MapServer' o 'FeatureServer'.")
    
    async with async_playwright() as p:
        browser = await p.webkit.launch(headless=False)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        found_endpoints = set()

        def handle_request(request):
            url = request.url
            # Filtro specifico per ArcGIS
            if "MapServer" in url or "FeatureServer" in url or "/rest/services" in url:
                # Escludiamo le tile immagini, vogliamo i metadati JSON
                if "export" not in url and "tile" not in url:
                    # Pulizia URL: teniamo solo la base del servizio
                    base_url = url.split("/MapServer")[0] + "/MapServer"
                    if base_url not in found_endpoints:
                        print(f"   🔥 CATTURATO: {base_url}")
                        found_endpoints.add(base_url)

        page.on("request", handle_request)

        try:
            print("⏳ Caricamento Mappa (Attendi 15s)...")
            await page.goto(MAP_VIEWER_URL, timeout=60000)
            
            # Aspettiamo che la mappa carichi i layer
            await page.wait_for_timeout(10000)
            
            print("🤖 Simulazione Zoom per forzare il caricamento...")
            # Un piccolo zoom spesso attiva le richieste ai server di dettaglio
            await page.mouse.wheel(0, -500)
            await page.wait_for_timeout(5000)
            
        except Exception as e:
            print(f"⚠️ Nota: {str(e)}")

        print("\n--- 📦 BOTTINO ---")
        if found_endpoints:
            print(f"🎯 Trovati {len(found_endpoints)} Servizi Mappa:")
            for ep in found_endpoints:
                print(f"   💎 {ep}")
                
            # Verifica se c'è Bali
            bali_hits = [e for e in found_endpoints if "bali" in e.lower() or "badung" in e.lower() or "rtrw" in e.lower()]
            if bali_hits:
                print(f"\n✅ LAYER CRITICI RILEVATI ({len(bali_hits)}):")
                for h in bali_hits:
                    print(f"   🚀 {h}")
        else:
            print("❌ Nessun traffico ArcGIS rilevato. Il sito potrebbe usare una tecnologia diversa o essere giù.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(intercept_gistaru())
