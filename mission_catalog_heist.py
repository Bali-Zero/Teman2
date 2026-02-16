import asyncio
from playwright.async_api import async_playwright
import json

# --- L'ENDPOINT CHE ABBIAMO SCOPERTO ---
# Aggiungiamo filtri per scaricare più roba possibile (page_size=500)
CATALOG_URL = "https://bhumi.atrbpn.go.id/geonode/api/v2/resources?page_size=500&format=json"

async def steal_catalog():
    print("--- 🏴‍☠️ OPERATION CATALOG HEIST ---")
    print(f"📡 Bersaglio: {CATALOG_URL}")
    
    async with async_playwright() as p:
        # Usiamo sempre WebKit per sicurezza su M4
        browser = await p.webkit.launch(headless=False) 
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()

        # Intercettiamo la risposta specifica
        final_data = {}

        async def handle_response(response):
            if "api/v2/resources" in response.url and response.status == 200:
                print("   🔥 CATTURATO JSON DEL CATALOGO!")
                try:
                    data = await response.json()
                    final_data['resources'] = data
                    print(f"   📦 Dimensione Dati: {len(str(data))} bytes")
                except:
                    print("   ⚠️ Impossibile leggere il JSON")

        page.on("response", handle_response)

        try:
            print("⏳ Connessione al Database API...")
            # Andiamo DIRETTAMENTE all'URL dell'API, non alla mappa visiva
            await page.goto(CATALOG_URL, timeout=30000, wait_until="networkidle")
            
            # Aspettiamo che scarichi
            await page.wait_for_timeout(5000)

        except Exception as e:
            print(f"⚠️ Errore: {str(e)}")

        print("\n--- 🕵️‍♂️ ANALISI INTELLIGENCE ---")
        if 'resources' in final_data:
            data = final_data['resources']
            resources = data.get('resources', []) # GeoNode struttura: {'resources': [...]}
            
            print(f"📚 Mappe Totali nell'Indice: {len(resources)}")
            
            # FILTRO: CERCHIAMO BALI O BADUNG
            bali_maps = []
            for r in resources:
                # Cerca nel titolo o nel nome astratto
                text_blob = (r.get('title', '') + r.get('abstract', '') + r.get('name', '')).lower()
                if 'bali' in text_blob or 'badung' in text_blob or 'denpasar' in text_blob or 'taru' in text_blob:
                    bali_maps.append(r)
            
            print(f"🎯 Mappe Rilevanti per NUZANTARA: {len(bali_maps)}")
            
            for m in bali_maps:
                print(f"\n   🗺️  TITOLO: {m.get('title')}")
                print(f"       ID: {m.get('pk')} | NAME: {m.get('name')}")
                print(f"       TYPE: {m.get('resource_type')}")
                print(f"       DETAIL: {m.get('detail_url')}")

            # Salviamo il bottino
            with open("heist_catalog.json", "w") as f:
                json.dump(data, f, indent=2)
                print("\n✅ Catalogo salvato in 'heist_catalog.json'")
        else:
            # Se fallisce l'intercettazione, prova a leggere il testo della pagina (fallback)
            try:
                content = await page.content()
                # A volte il browser mostra il JSON come testo nel body
                if "{" in content:
                     print("⚠️ Intercettazione fallita, ma vedo testo JSON nella pagina via body().")
                     # Pulizia HTML base
                     import re
                     json_text = re.sub(r'<[^>]+>', '', content)
                     print(f"Snippet: {json_text[:100]}...")
            except:
                pass
            print("❌ Nessun dato estratto.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(steal_catalog())
