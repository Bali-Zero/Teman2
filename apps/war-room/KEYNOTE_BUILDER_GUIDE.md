# KEYNOTE BUILDER — Training Guide

_Analisi preventiva di 06_keynote_builder.py — verificata live il 2026-03-03_

---

## Architettura dello script

```
claude_slides.json  ──┐
images/manifest.json ──┤──▶ compose_slide() [PIL]  ──▶ composed/slide_NN.jpg
                       │         ↓ per ogni slide
                       └──▶ build_keynote() [AppleScript] ──▶ presentation.key
```

**Due fasi indipendenti:**

- **PIL**: genera i JPEG finali (slide composte testo+immagine) — NON dipende da Keynote
- **AppleScript**: impacchetta i JPEG in un .key — opzionale, può fallire senza bloccare

---

## Bug confermati (test live)

### BUG #1 — CRITICO: `export` dentro `tell newDoc` crasha

**Codice attuale:**

```applescript
tell newDoc
    ...
    export newDoc to POSIX file "..." as slide images ...  ← DENTRO tell newDoc
end tell
```

**Problema:** `export` è un comando a livello applicazione, non di documento.
Dentro `tell newDoc` viene interpretato come comando del documento → crash silenzioso.

**Fix:**

```applescript
tell application "Keynote"
    export testDoc to POSIX file "..." as slide images ...  ← FUORI da tell doc
end tell
```

---

### BUG #2 — CRITICO: Semantica path export

**Come funziona Keynote export:**

```
Input path:  /path/to/output/slides_export
Output files: /path/to/output/slides_export.001.jpeg
              /path/to/output/slides_export.002.jpeg
              ...
```

Il path NON è una directory — è un **prefisso**. I file vengono creati nella directory PADRE.

**Nel codice attuale:**

```python
output_key = "/output/keynote/"          # usato sia per export che per .key
key_path   = output_key + "/presentation.key"
```

→ Export crea `/output/keynote.001.jpeg` nella directory `output/`
→ Save prova a scrivere in `/output/keynote//presentation.key` (doppio slash)

**Fix:** usare prefissi separati:

```python
export_prefix = "/output/keynote/slides"      # → /output/keynote/slides.001.jpeg
key_path      = "/output/keynote/presentation.key"
```

---

### BUG #3 — ALTO: Alias crash se file mancante

**Codice attuale:**

```applescript
set imgAlias1 to (POSIX file "/path/slide_01.jpg") as alias
```

Se il file non esiste → `as alias` fa crashare **l'intero script** prima che venga creata una singola slide.

**Fix:** Controllare esistenza in Python prima di aggiungere la riga AppleScript.
Già presente in parte (`if not Path(img_path).exists(): continue`) ma le variabili sono numerate sequenzialmente → riferimento sbagliato nel loop successivo.

**Fix corretto:** usare un mapping `num → alias_name` basato solo sui file esistenti.

---

### BUG #4 — MEDIO: Slide bianca extra in Keynote

Keynote apre sempre con 1 slide di default. `delete every slide` la rimuove, MA se l'AppleScript viene interrotto prima del loop slide-creation, il documento rimane vuoto.
Nell'ultimo run: 7 file di export invece di 6 → probabile che `delete every slide` non abbia funzionato o che Keynote abbia mantenuto la slide iniziale.

**Fix:** `delete every slide` è corretto ma va eseguito **dopo** `activate` e **prima** di inserire le nuove slide. Aggiungere `delay 1` dopo activate.

---

### BUG #5 — MEDIO: layout `split` non implementato

Slide 2, 4, 6 hanno `layout=split`. Il codice le renderizza identiche a `full_bleed` (immagine full-bleed + testo sovrapposto top-left).

Design corretto per split:

```
┌────────────────────────┐
│  TESTO     │  IMMAGINE │  ← immagine nella metà destra
│            │           │
└────────────────────────┘
```

**Attuale:** immagine dietro tutto, testo sopra → tecnicamente funziona ma ignora il layout.
**Fix:** per split, ridimensiona immagine a 540×1350 e posiziona a destra; testo a sinistra.

---

### BUG #6 — MEDIO: Nessun placeholder per immagini mancanti

Se `05_gemini_images.py` fallisce per una slide (o la slide è `text_only` e non ha immagine nel manifest), `img_path = ""` → compose_slide usa solo il background brand.
Per layout `full_bleed` e `split`, il risultato visivo è uno sfondo piatto senza interesse.

**Fix:** generare un placeholder procedurale (gradiente + pattern geometrico con brand colors) quando l'immagine manca per layout full_bleed/split.

---

### BUG #7 — BASSO: Gradiente overlay anche per text_only

Su slide `text_only` senza immagine, viene applicato il gradiente nero → sfondo già scuro diventa ancora più scuro in basso, senza motivo.

**Fix:** applicare gradiente solo quando `img_path` esiste.

---

### BUG #8 — BASSO: Font brand non installati

`brand.json` specifica LeagueSpartan-ExtraBold e Montserrat-Medium.
**Verificato:** NON installati nel sistema → fallback silenzioso a Impact/Helvetica.

**Fix:** scaricare e installare i font (sono Google Fonts, free), oppure aggiornare brand.json con i font effettivamente disponibili.

```bash
# Install via brew o manuale:
brew install --cask font-league-spartan font-montserrat
```

---

## Dati slide verificati

| Slide | Layout     | Cover | Font size | Headline len | Subhead | Body |
| ----- | ---------- | ----- | --------- | ------------ | ------- | ---- |
| 1     | full_bleed | ✅    | 72        | 49 chars     | ✅      | ❌   |
| 2     | split      | ❌    | 72        | 41 chars     | ❌      | ✅   |
| 3     | text_only  | ❌    | 72        | 39 chars     | ❌      | ✅   |
| 4     | split      | ❌    | 72        | 28 chars     | ✅      | ✅   |
| 5     | full_bleed | ❌    | 72        | 46 chars     | ❌      | ✅   |
| 6     | split      | ❌    | 72        | 37 chars     | ✅      | ✅   |

**Misure verificate a 72px Impact:**

- Linee headline: 59-70px di altezza
- Wrap width=22: produce ~2-3 righe per headline, max 594px larghezza (su 1020px disponibili)
- y_cursor dopo headline cover: ~320px su 1350 totali — ampio spazio per body

---

## Flusso corretto (dopo fix)

```
1. compose_slide() per ogni slide:
   - full_bleed: immagine + overlay gradiente + testo top-left
   - split: immagine metà destra + testo metà sinistra
   - text_only: solo background brand + testo (no gradiente)
   - missing img (full_bleed/split): placeholder procedurale brand colors

2. build_keynote():
   - Verifica esistenza tutti i file prima di generare AppleScript
   - export a livello app (non dentro tell doc)
   - prefisso export separato dal path .key
   - delay 1 dopo activate
   - gestione graceful se Keynote non è aperto
```
