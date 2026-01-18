# Patch Gemini CLI per Analisi PDF Lampiran

## 📋 Panoramica

5 patch indipendenti per analizzare i PDF rimanenti usando **Gemini CLI** invece dell'API (per evitare quota limits).

## ⚠️ IMPORTANTE: Soluzione al Problema Token Limit

**Problema originale**: Gemini CLI cercava di caricare tutto il PDF (6M+ tokens) → errore context window.

**Soluzione**: Ogni patch processa **pagina per pagina**:

- Estrae UNA pagina alla volta come immagine PNG
- Invia SOLO quella singola immagine a Gemini CLI
- NON carica mai tutto il PDF in memoria

## 📁 File Disponibili

1. `patch_1_lampiran_ih_gemini_cli.py` - Lampiran I.H (515 pagine)
2. `patch_2_lampiran_ii_gemini_cli.py` - Lampiran I.I (411 pagine)
3. `patch_3_lampiran_ii_gemini_cli.py` - Lampiran II
4. `patch_4_lampiran_iii_gemini_cli.py` - Lampiran III
5. `patch_5_lampiran_iv_gemini_cli.py` - Lampiran IV

## 🚀 Come Usare

### Prerequisiti

```bash
pip install PyMuPDF  # fitz
```

### Esecuzione

Ogni patch può essere eseguita su un'istanza separata di Gemini CLI:

```bash
# Worker 1
python3 scripts/analysis/patch_1_lampiran_ih_gemini_cli.py

# Worker 2
python3 scripts/analysis/patch_2_lampiran_ii_gemini_cli.py

# Worker 3
python3 scripts/analysis/patch_3_lampiran_ii_gemini_cli.py

# Worker 4
python3 scripts/analysis/patch_4_lampiran_iii_gemini_cli.py

# Worker 5
python3 scripts/analysis/patch_5_lampiran_iv_gemini_cli.py
```

## 🔧 Configurazione Gemini CLI

Gli script provano automaticamente diversi formati di comando:

1. `gemini analyze --image <path> --prompt "<prompt>"`
2. `gemini vision --image <path> --prompt "<prompt>"`
3. `python -m gemini analyze --image <path> --prompt "<prompt>"`

Se il tuo comando Gemini CLI è diverso, modifica la funzione `call_gemini_cli_with_image()` in ogni script.

## 📊 Output

Ogni patch salva un file JSON in `reports/lampiran_analysis/`:

```
resoconto_<pdf_name>_<timestamp>.json
```

## ⚙️ Configurazione Agenti

Ogni patch usa:

- **3 agenti paralleli** per PDF
- **50 pagine minime** per agente
- **2 secondi di delay** tra pagine

Modifica le costanti all'inizio di ogni script se necessario:

- `NUM_AGENTS = 3`
- `MIN_PAGES_PER_AGENT = 50`
- `DELAY_BETWEEN_PAGES = 2`

## ✅ Vantaggi

1. ✅ **Nessun problema di token limit** - solo immagini singole
2. ✅ **Nessun problema di quota API** - usa Gemini CLI
3. ✅ **Processamento parallelo** - 3 agenti per PDF
4. ✅ **Resoconti dettagliati** - JSON completo per ogni pagina
5. ✅ **Indipendenti** - ogni patch può girare separatamente
