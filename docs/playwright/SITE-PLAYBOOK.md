# Playwright Site Playbook — selectors, flows, gotchas

**One section per site.** Update `Verified` after every successful run. When a selector fails, fix this file FIRST, then the script.

---

## § Canva — Magic Media image generation

- **URL**: `https://www.canva.com/create/images/`
- **Profile**: `~/.nuzantara/playwright-profiles/canva`
- **Verified**: _not yet_
- **Account**: Canva Pro (Antonello's personal)

### Flow: generate image from prompt

1. Navigate to `https://www.canva.com/create/images/`
2. Wait for prompt textarea — selector TBD on first run
3. Type prompt
4. Click "Generate" — selector TBD
5. Wait for 4 image grid (~20-40s)
6. Right-click first image → "Download" OR use the download button overlay
7. Image saves to `~/Downloads/<name>.png` (Playwright can intercept via `page.wait_for_event("download")`)

### Flow: edit existing design (template DAHE6lx1lf8)

1. Navigate to `https://www.canva.com/design/DAHE6lx1lf8/edit`
2. Wait for editor load — selector TBD
3. Click text element → Playwright locator by text content
4. Select all (Cmd+A) → type new text
5. Repeat per slide
6. Click Share → Download → PNG/PDF

### Selectors — TO BE FILLED on first run

```python
SELECTORS = {
    "prompt_input": "TBD",
    "generate_button": "TBD",
    "image_result_grid": "TBD",
    "download_overlay": "TBD",
    # editor
    "text_element": "TBD",
    "share_button": "TBD",
}
```

### Gotchas

- Canva sometimes shows a "what would you like to create" modal on cold load → dismiss with Escape
- Magic Media has a daily quota even on Pro (Imagen-based, ~100/day at most recent check)
- Design URLs like `/design/<id>/view` vs `/edit` — always use `/edit` for automation
- Canva resizes automatically on load → set viewport ≥1440px to get desktop UI

### Recovery

- Login: `rm -rf ~/.nuzantara/playwright-profiles/canva && python3 scripts/playwright_login.py canva`
- Selector change: open https://www.canva.com manually, inspect element, update `SELECTORS` above

---

## § Gemini app — Imagen image generation

- **URL**: `https://gemini.google.com/app`
- **Profile**: `~/.nuzantara/playwright-profiles/gemini`
- **Verified**: _not yet_
- **Account**: Antonello's Google (which plan? Ultra / AI Pro — TBD)

### Flow: generate image

1. Navigate to `https://gemini.google.com/app`
2. Wait for input textarea — likely `rich-textarea` custom element
3. Type prompt prefixed with `generate an image of:` (helps routing to Imagen)
4. Press Enter OR click Send button
5. Wait for response; image appears inline
6. Hover image → download button appears
7. Save PNG

### Selectors — TBD

```python
SELECTORS = {
    "input_textarea": "TBD",  # likely 'rich-textarea > div[contenteditable]'
    "send_button": "button[aria-label*='Send'], button[aria-label*='Invia']",
    "image_response": "img[src*='googleusercontent']",
    "download_button": "TBD",
}
```

### Gotchas

- Google detects vanilla headless in ~5s. Use headed + off-screen, or Xvfb.
- Language: if account locale is Italian, UI is in Italian. Add `hl=en` param or set Accept-Language to EN.
- Image gen needs Imagen opt-in on some accounts — verify manually first.
- If prompt doesn't trigger image gen, prefix with English: `"Please generate an image of: <prompt>"`.

### Recovery

- Login: `rm -rf ~/.nuzantara/playwright-profiles/gemini && python3 scripts/playwright_login.py gemini`
- reCAPTCHA hit → headed login + wait 24h before retry from same IP

---

## § Google Flow — Imagen 4 / Veo

- **URL**: `https://labs.google/fx/tools/flow`
- **Profile**: `~/.nuzantara/playwright-profiles/flow`
- **Verified**: _not yet_
- **Account**: Google with AI Pro/Ultra access

### Flow: generate image

TBD on first run — Flow UI is in active development, selectors volatile.

### Gotchas

- UI redesigns frequently; verify date <7d old before trusting selectors
- Image vs video tool is a toggle — default may switch
- Quota visible in top-right corner; worth scraping for pre-flight

### Recovery

Standard Google recovery.

---

## § ChatGPT — DALL-E 3 / GPT Image (fallback)

- **URL**: `https://chat.openai.com/`
- **Profile**: `~/.nuzantara/playwright-profiles/chatgpt`
- **Verified**: _not yet_
- **Account**: ChatGPT Plus (Antonello's)

### Flow: generate image

1. Navigate to `https://chat.openai.com/`
2. Start new chat (maybe pre-select model GPT-4o)
3. Type prompt: `generate an image of <prompt>`
4. Send
5. Wait for image (often 15-40s)
6. Click image → download icon in the corner

### Selectors — TBD

### Gotchas

- Plus daily image limit (few dozen/day)
- Cloudflare challenge on first load; run headed first time to clear
- Model switcher — ensure GPT-4o or image-capable model selected

### Recovery

Standard recovery.

---

## § Shared across all sites

### Wait-for patterns

```python
# Wait for network-idle after big action (safer than fixed timeout):
page.wait_for_load_state("networkidle", timeout=30000)

# Wait for text to appear (generated image, response):
page.wait_for_selector("text=Generated", timeout=60000)
```

### Download handling

```python
with page.expect_download() as download_info:
    page.locator(DOWNLOAD_BTN).click()
download = download_info.value
out_path = Path("/tmp/wr2-image.png")
download.save_as(out_path)
```

### Debug snapshot on failure

```python
try:
    # ... action ...
except Exception as e:
    page.screenshot(path=f"/tmp/debug-{site}-{int(time.time())}.png", full_page=True)
    Path(f"/tmp/debug-{site}-{int(time.time())}.html").write_text(page.content())
    raise
```

---

_Last updated: 2026-04-24_
