#!/usr/bin/env python3
"""
FASE 3 — Gemini Image Generator via Browser LAM (CDP attach)
================================================================
PATTERN: Playwright si aggancia a Chrome GIA' APERTO via remote debugging.

PRE-REQUISITO (una tantum):
  Chrome deve essere avviato con --remote-debugging-port=9222
  Script: ~/war_room/chrome-debug.sh

FLUSSO:
  1. Playwright si connette al Chrome esistente (CDP su porta 9222)
  2. Trova/apre il tab gemini.google.com (già loggato come zero@balizero.com)
  3. Per ogni slide:
     a. Apre nuova chat (evita contaminazione tra slide)
     b. Seleziona modello con image generation (es. "2.0 Flash")
     c. Digita il prompt e invia
     d. Aspetta l'immagine generata
     e. Scarica l'immagine (3 strategie: URL auth → canvas → screenshot)
  4. Salva manifest.json con i path delle immagini
"""
import json, argparse, sys, time, base64
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, Browser

# ── Configurazione ─────────────────────────────────────────────────────────────
CDP_URL       = "http://localhost:9222"          # Chrome remote debugging
GEMINI_URL    = "https://gemini.google.com/app"  # URL Gemini app
TARGET_MODEL  = "2.0 Flash"                      # Keyword modello nella dropdown

# Timeout attesa immagine generata (ms) — la gen può richiedere 20-40s
IMAGE_WAIT_MS = 50_000
# Pausa tra slide (sec) — rate limiting
SLIDE_PAUSE   = 8

# ── Selettori UI Gemini ────────────────────────────────────────────────────────
# NOTA: Se Gemini aggiorna la UI, aggiorna questi selettori
SEL = {
    # Bottone/select del modello in alto
    "model_btn":     "button[data-test-id='model-switcher-button'], [jsname='V67aGc'], mat-select",
    # Nuova chat (sidebar o header)
    "new_chat":      "a[href='/app'], [aria-label='New chat'], [aria-label='Nuova chat'], button[data-test-id='new-chat-button']",
    # Campo input testo
    "input":         "rich-textarea .ql-editor[contenteditable='true'], rich-textarea, textarea",
    # Bottone invio
    "send":          "button[data-test-id='send-button'], button[aria-label='Send message'], button[aria-label='Invia messaggio']",
    # Immagini generate (esclude icone UI)
    "gen_image":     "model-response img[src*='lh3.googleusercontent'], model-response img[src*='blob:'], .image-container img, [data-test-id='image-result'] img",
    # Indicatore di loading (per aspettare che finisca)
    "loading":       ".loading-indicator, [aria-label='Generating'], mat-progress-bar",
}


def log(msg: str):
    print(msg, file=sys.stderr, flush=True)


def find_or_open_gemini(browser: Browser) -> Page:
    """
    Trova il tab Gemini già aperto, oppure ne apre uno nuovo.
    Non apre nuovi browser — usa il Chrome esistente.
    """
    for ctx in browser.contexts:
        for page in ctx.pages:
            if "gemini.google.com" in page.url:
                log(f"  ✅ Tab Gemini trovato: {page.url}")
                page.bring_to_front()
                return page

    # Gemini non è aperto → apri nuovo tab nel contesto esistente
    log("  🌐 Gemini non aperto — apro nuovo tab...")
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.goto(GEMINI_URL, timeout=30_000)
    page.wait_for_timeout(4000)
    return page


def select_model(page: Page):
    """Seleziona il modello con image generation dalla dropdown Gemini."""
    log(f"  🔧 Seleziono modello '{TARGET_MODEL}'...")
    try:
        btn = page.locator(SEL["model_btn"]).first
        if btn.count() == 0:
            log("  ⚠️  Dropdown modello non trovata — uso default")
            return
        btn.click()
        page.wait_for_timeout(1200)

        item = page.get_by_text(TARGET_MODEL, exact=False).first
        if item.count() > 0:
            item.click()
            page.wait_for_timeout(800)
            log(f"  ✅ Modello selezionato")
        else:
            page.keyboard.press("Escape")
            log(f"  ⚠️  '{TARGET_MODEL}' non trovato nella lista — uso default")
    except Exception as e:
        log(f"  ⚠️  Errore selezione modello: {e}")


def new_chat(page: Page):
    """
    Apre una nuova conversazione.
    CRITICO: senza questo step, Gemini riceve contesto delle chat precedenti
    e tende a generare immagini simili (es. tutte circuit board).
    """
    try:
        btn = page.locator(SEL["new_chat"]).first
        if btn.count() > 0:
            btn.click()
            page.wait_for_timeout(2000)
        else:
            page.goto(GEMINI_URL, timeout=20_000)
            page.wait_for_timeout(3000)
    except Exception:
        page.goto(GEMINI_URL, timeout=20_000)
        page.wait_for_timeout(3000)


def send_prompt(page: Page, prompt: str):
    """Digita il prompt nel campo input e lo invia."""
    # Trova l'input (rich-textarea è il contenteditable di Gemini)
    inp = page.locator(SEL["input"]).first
    inp.click()
    page.wait_for_timeout(300)

    # Svuota e scrivi
    page.keyboard.press("Control+A")
    inp.fill(prompt)
    page.wait_for_timeout(400)

    # Invia (tasto o bottone)
    send_btn = page.locator(SEL["send"]).first
    if send_btn.count() > 0:
        send_btn.click()
    else:
        page.keyboard.press("Enter")

    log(f"  📨 Prompt inviato")


def download_authenticated(page: Page, url: str, dest: Path) -> bool:
    """
    Scarica un'immagine usando le sessioni/cookie del browser.
    Funziona anche con URL temporanei autenticati Google (lh3.googleusercontent.com).
    """
    try:
        resp = page.request.get(url, timeout=30_000)
        if resp.status == 200:
            dest.write_bytes(resp.body())
            return True
        log(f"    ↳ HTTP {resp.status}")
    except Exception as e:
        log(f"    ↳ Download error: {e}")
    return False


def extract_via_canvas(page: Page, img_locator) -> bytes | None:
    """
    Estrae i pixel dell'immagine via Canvas API.
    Funziona con blob URL e data URL che non si possono scaricare direttamente.
    """
    try:
        data = page.evaluate("""el => new Promise(resolve => {
            const c = document.createElement('canvas');
            c.width = el.naturalWidth || el.width || 800;
            c.height = el.naturalHeight || el.height || 800;
            c.getContext('2d').drawImage(el, 0, 0);
            resolve(c.toDataURL('image/jpeg', 0.95));
        })""", img_locator.element_handle())
        if data and "," in data:
            return base64.b64decode(data.split(",", 1)[1])
    except Exception as e:
        log(f"    ↳ Canvas error: {e}")
    return None


def grab_generated_image(page: Page, slide_num: int, output_dir: Path) -> str | None:
    """
    Aspetta che Gemini generi l'immagine e la scarica.

    Strategie (in ordine):
      1. Trova img con URL googleusercontent → download autenticato
      2. img con blob URL → estrazione canvas
      3. Screenshot dell'intera risposta (fallback)
    """
    dest_jpg = output_dir / f"slide_{slide_num:02d}.jpg"
    dest_png = output_dir / f"slide_{slide_num:02d}.png"

    log(f"  ⏳ Attendo immagine (max {IMAGE_WAIT_MS//1000}s)...")

    try:
        # Aspetta che appaia almeno un'immagine generata
        page.wait_for_selector(SEL["gen_image"], timeout=IMAGE_WAIT_MS)
        # Aspetta ancora un po' per caricamento completo
        page.wait_for_timeout(2500)

        images = page.locator(SEL["gen_image"]).all()
        if not images:
            raise Exception("Nessuna immagine trovata dopo il wait")

        # L'ultima immagine è quella appena generata
        last = images[-1]
        src = last.get_attribute("src") or ""
        log(f"  🖼️  src={src[:80]}...")

        # Strategia 1: URL HTTP → download con cookie sessione
        if src.startswith("http"):
            if download_authenticated(page, src, dest_jpg):
                log(f"  ✅ Slide {slide_num} salvata → {dest_jpg.name}")
                return str(dest_jpg)

        # Strategia 2: blob/data URL → canvas extraction
        img_bytes = extract_via_canvas(page, last)
        if img_bytes:
            dest_jpg.write_bytes(img_bytes)
            log(f"  ✅ Slide {slide_num} salvata → {dest_jpg.name} (canvas)")
            return str(dest_jpg)

    except Exception as e:
        log(f"  ⚠️  Errore attesa/download: {e}")

    # Strategia 3: screenshot dell'ultima risposta
    try:
        log(f"  📸 Fallback: screenshot risposta...")
        resp = page.locator("model-response").last
        target = resp if resp.count() > 0 else page
        target.screenshot(path=str(dest_png))
        log(f"  ⚠️  Slide {slide_num} → {dest_png.name} (screenshot fallback)")
        return str(dest_png)
    except Exception as e:
        log(f"  ❌ Screenshot fallito: {e}")

    return None


def process_slide(page: Page, slide: dict, output_dir: Path, style_suffix: str) -> str | None:
    """Pipeline completa per una singola slide."""
    num = slide["slide_number"]
    prompt = f"Generate an image: {slide['image_prompt']}. {style_suffix}"

    log(f"\n{'='*60}")
    log(f"  SLIDE {num}: {slide.get('title', '')}")
    log(f"  Prompt: {prompt[:120]}...")

    # IMPORTANTE: nuova chat per ogni slide (evita duplicati)
    new_chat(page)

    # Invia prompt
    send_prompt(page, prompt)

    # Aspetta e scarica immagine
    return grab_generated_image(page, num, output_dir)


def main():
    global TARGET_MODEL
    parser = argparse.ArgumentParser(description="Genera immagini via Gemini app (Chrome CDP)")
    parser.add_argument("--slides",  required=True, help="Path al JSON slides")
    parser.add_argument("--output",  required=True, help="Directory output immagini")
    parser.add_argument("--model",   default=TARGET_MODEL, help="Keyword modello Gemini")
    parser.add_argument("--cdp",     default=CDP_URL,      help="URL Chrome remote debugging")
    args = parser.parse_args()

    TARGET_MODEL = args.model

    slides_data  = json.loads(Path(args.slides).read_text())
    output_dir   = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    brand_path   = Path(__file__).parent.parent / "config" / "brand.json"
    brand        = json.loads(brand_path.read_text())
    style_suffix = brand["image_style"]["base_prompt_suffix"]

    slides_with_images = [
        s for s in slides_data.get("slides", [])
        if s.get("image_prompt") and (
            s.get("is_cover") or s.get("layout") in ["full_bleed", "split"]
        )
    ]

    if not slides_with_images:
        log("⚠️  Nessuna slide con image_prompt.")
        print(json.dumps({}))
        return

    log(f"🖼️  {len(slides_with_images)} immagini da generare")
    log(f"🎯 Modello: '{TARGET_MODEL}'  |  CDP: {args.cdp}")

    image_map = {}

    with sync_playwright() as p:
        # ── PATTERN CHIAVE ─────────────────────────────────────────────────
        # connect_over_cdp = aggancia Playwright a Chrome GIA' APERTO.
        # Non apre un nuovo browser. Non serve chiudere Chrome.
        # Chrome deve essere stato avviato con --remote-debugging-port=9222
        # (usa ~/war_room/chrome-debug.sh per abilitarlo).
        # ───────────────────────────────────────────────────────────────────
        try:
            browser = p.chromium.connect_over_cdp(args.cdp)
            log(f"✅ Connesso a Chrome esistente via CDP ({args.cdp})")
        except Exception as e:
            log(f"❌ Impossibile connettersi a Chrome via CDP: {e}")
            log(f"   Soluzione: esegui ~/war_room/chrome-debug.sh prima di avviare la pipeline")
            sys.exit(1)

        # Trova/apri tab Gemini nel Chrome già aperto
        page = find_or_open_gemini(browser)

        # Seleziona modello (solo una volta, persiste nella sessione)
        select_model(page)
        page.wait_for_timeout(1000)

        for slide in slides_with_images:
            img_path = process_slide(page, slide, output_dir, style_suffix)
            if img_path:
                image_map[slide["slide_number"]] = img_path
            time.sleep(SLIDE_PAUSE)

        # NON chiudiamo il browser — è Chrome dell'utente!
        log("\n✅ Done — Chrome lasciato aperto.")

    # Salva manifest
    manifest = output_dir / "manifest.json"
    manifest.write_text(json.dumps(image_map, indent=2))
    log(f"📋 Manifest → {manifest}")
    print(json.dumps(image_map, indent=2))


if __name__ == "__main__":
    main()
