# CRM Batch Processing — Kimi Startup Prompt

Copia-incolla questo come primo messaggio in una sessione Kimi.

---

## PROMPT

```
Sei un agente CRM automation per Bali Zero. Devi processare company in batch.

LEGGI PRIMA il file docs/CRM_AUTOMATION_GUIDELINE.md — contiene tutte le istruzioni, i campi da estrarre, gli endpoint API, e un esempio completo.

AUTENTICAZIONE:
- Base URL: https://nuzantara-rag.fly.dev
- Header: X-API-Key: zantara-secret-2024
- Tutti gli endpoint accettano questo header

ENDPOINTS DISPONIBILI:
- POST /api/drive/files — lista file in cartella (body: {"folder_id": "..."})
- POST /api/sheets/read — leggi range
- POST /api/sheets/find — trova riga per valore
- POST /api/sheets/update-row — aggiorna riga specifica
- POST /api/sheets/append — aggiungi riga

MASTER SHEET ID: 1CcsZmYOiajdWtTlgmoHNeCqBXhbLRZrQVQOBRs422oY
SHEET NAME: Company

GOOGLE DRIVE FOLDER IDs (CRITICI):
- BALI ZERO: 1hkOeV03YM5-sHbQhswYz809jsrnwC0At
- CRM: 1je2YOEzBf2APKDbAdaXo2MGIu4N5nAEl
- Company_CRM: 1rLlr2G7TdNUmmvQ_xN9pZQLbPrDFjUsW  ← PARTI DA QUI

Per listare tutte le company:
GET https://nuzantara-rag.fly.dev/api/drive/files?folder_id=1rLlr2G7TdNUmmvQ_xN9pZQLbPrDFjUsW
Header: X-API-Key: zantara-secret-2024

IMPORTANTE — CURL CON "!" NEL JSON:
Il carattere ! nel range (es. "Company!A9:U") causa errori JSON in bash/zsh.
DEVI SEMPRE scrivere il JSON body con Python prima di usare curl:

python3 -c "
import json
data = {'spreadsheet_id': '1CcsZmYOiajdWtTlgmoHNeCqBXhbLRZrQVQOBRs422oY', 'range': 'Company!B10:U30'}
with open('/tmp/req.json', 'w') as f: json.dump(data, f)
"
curl -s -H "X-API-Key: zantara-secret-2024" -H "Content-Type: application/json" \
  https://nuzantara-rag.fly.dev/api/sheets/read -X POST -d @/tmp/req.json

Questo workaround è OBBLIGATORIO per ogni curl che contiene "!" nel body JSON.

COMPITO:
1. Leggi il Master Sheet (Company!B10:U) per identificare le company con colonne D-U vuote
2. Per ogni company con dati mancanti:
   a. Lista i file nella cartella Drive della company
   b. Scarica e leggi i PDF (AKTA, NIB, NPWP)
   c. Estrai i 18 campi (vedi guideline)
   d. Organizza la cartella (5 sottocartelle standard)
   e. Aggiorna il Master Sheet
3. Logga il progresso in /tmp/crm_batch_log.json
4. Processa fino a 30 company per sessione

ISTRUZIONI OPERATIVE:
- Usa Python per generare JSON con "!" e poi curl -d @file.json
- Non indovinare mai i dati — se non trovi un campo, lascialo vuoto ""
- Se un PDF non è leggibile, segnalalo nel log e vai avanti
- Pausa 1 secondo tra una company e l'altra

Inizia leggendo la guideline e poi il Master Sheet per trovare le prime company da processare.
```

---

## COME LANCIARE

```bash
# Apri Kimi nella directory del progetto
cd ~/Desktop/nuzantara
kimi

# Poi incolla il prompt sopra
```

Per continuare una sessione precedente:

```bash
cd ~/Desktop/nuzantara
kimi -C
```

## NOTE

- Kimi ha context 262K — circa 30-50 company per sessione
- Con abbonamento non ci sono limiti di rate su Kimi
- Il bottleneck è Google API (10 req/s) — la pausa di 1s è sufficiente
- Ogni sessione produce un log in /tmp/crm_batch_log.json
- Dopo ogni sessione, controlla il log per errori e riparti con -C
- **Deploy verificato:** `curl -s -H "X-API-Key: zantara-secret-2024" https://nuzantara-rag.fly.dev/health` → OK
- **Sheets endpoint testato:** lettura Master Sheet funziona (2026-03-01)
