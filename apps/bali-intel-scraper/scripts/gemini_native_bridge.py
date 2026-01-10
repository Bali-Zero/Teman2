#!/usr/bin/env python3
"""
GEMINI NATIVE BRIDGE (No-Playwright Version)
============================================
Pilota il tuo Google Chrome esistente su macOS usando AppleScript nativo.

Vantaggi:
- NESSUNA installazione (niente pip install playwright)
- Usa il tuo Chrome già loggato (sessione attiva)
- Leggerissimo
- Visibile e controllabile

Come funziona:
Invia comandi AppleScript a Chrome per navigare e interagire con il DOM tramite JavaScript.
"""

import subprocess
import time
import sys
import argparse
import json
from loguru import logger

class ChromeBridge:
    def run_applescript(self, script):
        """Esegue AppleScript grezzo"""
        try:
            result = subprocess.run(
                ['osascript', '-e', script], 
                capture_output=True, 
                text=True
            )
            if result.returncode != 0:
                logger.error(f"AppleScript Error: {result.stderr}")
                return None
            return result.stdout.strip()
        except Exception as e:
            logger.error(f"Execution Error: {e}")
            return None

    def execute_js(self, javascript):
        """Esegue JS nella tab attiva di Chrome"""
        # Escape quotes for AppleScript
        js_escaped = javascript.replace('"', '\\"').replace("'", "\\'")
        
        script = f'''
        tell application "Google Chrome"
            if (count of windows) is 0 then
                make new window
            end if
            tell active tab of front window
                execute javascript "{js_escaped}"
            end tell
        end tell
        '''
        return self.run_applescript(script)

    def open_gemini(self):
        """Apre o focalizza Gemini"""
        logger.info("🌍 Apertura Gemini su Chrome...")
        script = '''
        tell application "Google Chrome"
            activate
            set found to false
            repeat with w in windows
                repeat with t in tabs of w
                    if URL of t starts with "https://gemini.google.com" then
                        set active tab index of w to index of t
                        set index of w to 1
                        set found to true
                        exit repeat
                    end if
                end repeat
                if found then exit repeat
            end repeat
            
            if not found then
                open location "https://gemini.google.com/app"
            end if
        end tell
        '''
        self.run_applescript(script)
        time.sleep(3) # Attesa caricamento

    def insert_prompt(self, prompt):
        """Inserisce il prompt nella chat box"""
        logger.info("✍️ Scrittura prompt...")
        
        # JS per trovare la box e scrivere
        # Gemini usa un contenteditable div. Cerchiamo classi comuni o attributi.
        js = f'''
        (function() {{
            // Cerca input area (rich-textarea o contenteditable)
            const input = document.querySelector("div[contenteditable='true']") || 
                          document.querySelector("rich-textarea");
            
            if (input) {{
                input.focus();
                // Simula scrittura
                document.execCommand('insertText', false, "Generate an image: {prompt}");
                
                // Cerca bottone invio (spesso ha aria-label o icona send)
                setTimeout(() => {{
                    const sendBtn = document.querySelector("button[aria-label*='Send']") || 
                                    document.querySelector("button[aria-label*='Invia']");
                    if (sendBtn) {{
                        sendBtn.click();
                        return "SENT";
                    }}
                }}, 500);
                return "TYPED";
            }}
            return "NOT_FOUND";
        }})();
        '''
        return self.execute_js(js)

    def wait_and_get_image(self):
        """Attende e recupera URL ultima immagine"""
        logger.info("🎨 Attesa generazione...")
        
        for i in range(20): # 20 tentativi (circa 40s)
            logger.debug(f"Check {i+1}/20...")
            time.sleep(2)
            
            # JS per trovare l'ultima immagine generata
            js = '''
            (function() {
                const images = Array.from(document.querySelectorAll("img"));
                // Filtra immagini grandi che sembrano generate
                const valid = images.filter(img => {
                    const rect = img.getBoundingClientRect();
                    return rect.width > 300 && rect.height > 300 && img.src.startsWith("https://");
                });
                
                if (valid.length > 0) {
                    const lastImg = valid[valid.length - 1];
                    return lastImg.src;
                }
                return null;
            })();
            '''
            result = self.execute_js(js)
            
            if result and result != "null":
                logger.success(f"📸 Immagine trovata: {result[:50]}...")
                return result
        
        return None

def run_automation(prompt):
    bridge = ChromeBridge()
    
    # 1. Apri Gemini
    bridge.open_gemini()
    
    # 2. Inserisci prompt
    status = bridge.insert_prompt(prompt)
    if status == "NOT_FOUND":
        logger.error("❌ Impossibile trovare la casella di input su Gemini.")
        logger.info("Assicurati di essere loggato e che la pagina sia caricata.")
        return
    
    # 3. Attendi immagine
    img_url = bridge.wait_and_get_image()
    
    if img_url:
        logger.info("⬇️ Per scaricare, Claude dovrebbe ora usare curl sull'URL trovato.")
        # Nota: AppleScript non può scaricare facilmente file binari su disco senza curl
        # Qui potremmo lanciare un curl subprocess
        print(f"\nIMAGE_URL_FOUND: {img_url}")
    else:
        logger.error("❌ Nessuna immagine rilevata dopo il timeout.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default="Bali sunset cinematic photo")
    parser.add_argument("--context", help="Context file path")
    args = parser.parse_args()
    
    prompt = args.prompt
    if args.context and os.path.exists(args.context):
        with open(args.context) as f:
            data = json.load(f)
            prompt = data.get("final_image_prompt", prompt)
            
    run_automation(prompt)
