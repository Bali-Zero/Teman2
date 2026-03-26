import asyncio
from playwright.async_api import async_playwright
import os

BROWSER_PROFILE_PATH = os.path.expanduser("~/.gemini/antigravity-browser-profile/")

async def interactive_login():
    async with async_playwright() as p:
        print(f"Avvio browser con profilo persistente: {BROWSER_PROFILE_PATH}")
        # headless=False così puoi vedere la finestra
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=BROWSER_PROFILE_PATH,
            headless=False
        )
        page = await browser.new_page()
        await page.goto("https://notebooklm.google.com/")
        
        print("*"*60)
        print("AZIONE RICHIESTA:")
        print("1. Vai sulla finestra del browser appena aperta.")
        print("2. Fai il login con il tuo account Google su NotebookLM.")
        print("3. Quando vedi la dashboard con i tuoi Notebook, chiudi la finestra del browser.")
        print("*"*60)
        
        # Aspettiamo che l'utente chiuda la pagina
        try:
            await page.wait_for_event("close", timeout=300000) # 5 minuti di tempo
        except Exception:
            pass
        
        await browser.close()
        print("Profilo salvato. Ora posso caricare i file!")

if __name__ == "__main__":
    asyncio.run(interactive_login())
