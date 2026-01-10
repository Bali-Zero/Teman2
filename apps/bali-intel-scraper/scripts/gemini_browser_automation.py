#!/usr/bin/env python3
"""
GEMINI BROWSER AUTOMATION
=========================
L'agente operativo che esegue fisicamente la generazione immagini su Gemini.

Funzionalità:
1. Usa Chrome reale con profilo utente (mantiene il tuo login Google)
2. Naviga su gemini.google.com
3. Inserisce il prompt ottimizzato
4. Attende la generazione
5. Scarica l'immagine in alta qualità

Requisiti:
- Playwright: pip install playwright
- Browser installati: playwright install chromium
"""

import asyncio
import os
import json
import time
from pathlib import Path
from typing import Optional, Dict
from loguru import logger
from playwright.async_api import async_playwright, Page, BrowserContext

# Configurazione per mantenere la sessione (login)
USER_DATA_DIR = Path.home() / ".bali_zero_browser_profile"
HEADLESS_MODE = False  # False per vedere cosa succede (e per debug login)

class GeminiAutomator:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.user_data_dir = USER_DATA_DIR
        self.timeout = 60000  # 60 secondi timeout

    async def _init_browser(self, p) -> Tuple[BrowserContext, Page]:
        """Inizializza browser con profilo persistente"""
        logger.info(f"🚀 Avvio Chrome (Profilo: {self.user_data_dir})...")
        
        # Crea directory profilo se non esiste
        self.user_data_dir.mkdir(parents=True, exist_ok=True)

        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(self.user_data_dir),
            headless=self.headless,
            channel="chrome",  # Usa Chrome installato se possibile, altrimenti chromium
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled", # Nasconde automazione
            ],
            viewport={"width": 1280, "height": 800}
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        return context, page

    async def _check_login(self, page: Page) -> bool:
        """Verifica se l'utente è loggato su Gemini"""
        try:
            # Cerca elemento tipico della chat (es. input area o avatar)
            await page.wait_for_selector("div[contenteditable='true']", timeout=5000)
            logger.success("✅ Login rilevato: Accesso a Gemini confermato")
            return True
        except Exception:
            logger.warning("⚠️ Login non rilevato. Potrebbe essere necessario il login manuale.")
            return False

    async def _download_image(self, page: Page, prompt: str, output_path: str) -> Optional[str]:
        """Trova e scarica l'immagine generata"""
        logger.info("🎨 In attesa delle immagini...")
        
        # Attendi che appaiano immagini (di solito Gemini mostra 4 opzioni o 1)
        # Selettore generico per immagini generate in chat
        try:
            # Attesa intelligente: cerca immagini caricate dopo il nostro prompt
            # Questo selettore potrebbe richiedere aggiornamenti se Google cambia UI
            img_selector = "img[src^='https://generated']" # Esempio, spesso sono blob o url specifici
            # Fallback: cerca immagini grandi nell'ultimo messaggio
            
            # Aspettiamo fino a 30 secondi per la generazione
            for _ in range(30):
                # Cerchiamo l'ultima immagine generata
                images = await page.query_selector_all("img")
                # Filtra icone piccole, tieni solo immagini grandi (> 200px)
                valid_images = []
                for img in images:
                    box = await img.bounding_box()
                    if box and box['width'] > 250 and box['height'] > 250:
                        valid_images.append(img)
                
                if valid_images:
                    target_img = valid_images[-1] # Prendi l'ultima
                    src = await target_img.get_attribute("src")
                    
                    if src:
                        logger.info(f"📸 Immagine trovata! Scaricamento...")
                        
                        # Scarica immagine
                        async with page.context.request.get(src) as response:
                            if response.status == 200:
                                image_data = await response.body()
                                with open(output_path, "wb") as f:
                                    f.write(image_data)
                                logger.success(f"💾 Salvata in: {output_path}")
                                return output_path
                
                await asyncio.sleep(1)
                
            logger.error("❌ Timeout: Nessuna immagine generata trovata")
            return None

        except Exception as e:
            logger.error(f"Errore download immagine: {e}")
            return None

    async def generate_image(self, prompt: str, output_path: str) -> Optional[str]:
        """Flusso principale di generazione"""
        async with async_playwright() as p:
            context, page = await self._init_browser(p)
            
            try:
                # 1. Vai su Gemini
                logger.info("🌍 Navigazione su gemini.google.com...")
                await page.goto("https://gemini.google.com/app")
                
                # 2. Check Login
                if not await self._check_login(page):
                    if self.headless:
                        logger.error("❌ Non loggato e headless=True. Impossibile procedere.")
                        return None
                    
                    logger.warning("🚨 PER FAVORE EFFETTUA IL LOGIN SU GOOGLE (hai 60 secondi)...")
                    # Attendi login manuale
                    try:
                        await page.wait_for_selector("div[contenteditable='true']", timeout=60000)
                        logger.success("✅ Login manuale rilevato!")
                    except:
                        logger.error("❌ Tempo scaduto per il login.")
                        return None

                # 3. Inserisci Prompt
                logger.info("✍️ Inserimento prompt...")
                # Clicca sulla input area
                chat_box = await page.wait_for_selector("div[contenteditable='true']")
                await chat_box.click()
                await page.keyboard.type(f"Generate an image: {prompt}", delay=10) # Digita come umano
                await page.keyboard.press("Enter")
                
                # 4. Attendi e Scarica
                result = await self._download_image(page, prompt, output_path)
                
                # Attendi un attimo prima di chiudere
                await asyncio.sleep(2)
                return result

            except Exception as e:
                logger.error(f"❌ Errore automazione: {e}")
                # Screenshot per debug
                await page.screenshot(path="logs/debug_gemini_error.png")
                return None
            finally:
                await context.close()

# =============================================================================
# CLI UTILITY
# =============================================================================

async def run_from_context(context_file: str):
    """Esegue automazione leggendo file di contesto generato da article_deep_enricher"""
    if not os.path.exists(context_file):
        logger.error(f"File contesto non trovato: {context_file}")
        return

    with open(context_file, 'r') as f:
        data = json.load(f)
    
    # Verifica se c'è un prompt finale (se Claude lo ha già generato)
    # Altrimenti usa il reasoning framework per crearne uno (qui semplifichiamo)
    
    # NOTA: In un flusso agentico puro, Claude avrebbe già aggiornato questo JSON 
    # con il prompt definitivo. Se non c'è, usiamo una logica di fallback.
    
    article = data.get("article", {})
    prompt = data.get("final_image_prompt")
    
    if not prompt:
        # Fallback: crea un prompt base se manca quello "ragionato"
        logger.warning("⚠️ Prompt ragionato mancante. Uso fallback basato su titolo.")
        prompt = f"Hyper-realistic editorial photography for a news article about: {article.get('title')}. Setting: Bali, Indonesia. Style: Cinematic lighting, 8k resolution, photorealistic."
    
    output_path = data.get("output_path", "generated_image.png")
    
    automator = GeminiAutomator(headless=False) # Visibile per vedere cosa succede
    await automator.generate_image(prompt, output_path)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Gemini Browser Automation")
    parser.add_argument("--context", help="Path to image_context_xxx.json")
    parser.add_argument("--prompt", help="Direct prompt override")
    parser.add_argument("--output", default="output.png", help="Output path")
    
    args = parser.parse_args()
    
    if args.context:
        asyncio.run(run_from_context(args.context))
    elif args.prompt:
        automator = GeminiAutomator(headless=False)
        asyncio.run(automator.generate_image(args.prompt, args.output))
    else:
        print("Usa --context <file> o --prompt <text>")
