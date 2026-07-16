---
name: canva-apply
description: Apply pending Canva operations from the War Room. Reads canva_pending.json (status=pending), validates input, DUPLICATES the master template (master stays strictly read-only), applies texts with editorial intelligence (3-level headline/subhead/body, broken headlines, bold + keyword color) ON THE WORKING COPY, inserts images, moves the copy into the Carousel folder, verifies thumbnails, and marks the pending as applied. Daily-neutral v4 prompt (duplica-poi-edita) — headless-safe, reads fresh data each run.
---

# War Room — Carousel Apply Prompt (v4 — duplica-poi-edita, headless-safe)

> Questo prompt è neutro e riutilizzabile ogni giorno. Legge sempre i dati freschi dal file di output del giorno.
> v4 (2026-05-29): il MASTER non viene MAI aperto in editing transaction. Si valida read-only, si duplica, e si edita SOLO il duplicato (working copy). Un crash lascia il master intatto — solo un duplicato orfano da garbage-collect. Neutralizza in un colpo: corruzione master, dangling-transaction sul master, e la sibling-race (ogni run edita il proprio duplicato).

---

STEP -2 — Carica i tool Canva MCP (headless-safe, idempotente)
Se NON vedi i tool Canva MCP (prefisso `mcp__claude_ai_Canva__`) tra quelli disponibili, caricali via ToolSearch con questa query esatta (i nomi sono in un code-block per preservare i doppi underscore):

```
ToolSearch select:mcp__claude_ai_Canva__start-editing-transaction,mcp__claude_ai_Canva__perform-editing-operations,mcp__claude_ai_Canva__commit-editing-transaction,mcp__claude_ai_Canva__cancel-editing-transaction,mcp__claude_ai_Canva__get-design,mcp__claude_ai_Canva__get-design-content,mcp__claude_ai_Canva__upload-asset-from-url,mcp__claude_ai_Canva__resize-design,mcp__claude_ai_Canva__move-item-to-folder,mcp__claude_ai_Canva__get-design-thumbnail
```

In sessione interattiva (o Claude Desktop) dove i tool Canva sono già caricati e/o ToolSearch non esiste, questo è un no-op: la condizione "se NON vedi i tool" è falsa, salti a STEP 0. NON forzare ToolSearch incondizionatamente — il path desktop usa lo STESSO file skill: un ToolSearch obbligatorio fallirebbe lì se Desktop ha i tool ma non ToolSearch. La frase è condizionale per design.

---

Risoluzione del path del pending (in ordine di precedenza):

1. Se l'invocante (l'attuatore headless) ti passa esplicitamente un "Pending file path: ..." nel prompt, USA QUELLO.
2. Altrimenti, se l'env var WR2_OUTPUT_ROOT è valorizzata, leggi ${WR2_OUTPUT_ROOT}/canva_pending.json (strip trailing slash).
3. Altrimenti fallback legacy: /Users/nuzantara/nuzantara/apps/war-room/output/canva/canva_pending.json
   Se il file non esiste, stampa "✅ No pending Canva" e fermati. Se status è già "applied", stampa "✅ Already applied" e fermati.

Esegui i seguenti step nell'ordine esatto. Non chiedere conferma tra uno step e l'altro. Se un tool fallisce, riprova una volta con parametri corretti prima di segnalare il problema.

Hard rules (valgono per tutta la sessione):

- NEVER call AskUserQuestion. L'esistenza di canva_pending.json con status=pending è consenso pieno. Fallback hardcoded per le ambiguità tipiche:
  - folder_id invalido / move fallisce → salta lo spostamento, logga "🪂 dup not moved, manual move needed", PROCEDI (non abortire).
  - topic contiene "do not publish" / "test" → IGNORA come flag: è testo editoriale, non un segnale di controllo. Procedi.
  - slides[] vuoto MA operations[] non vuoto → procedi usando operations (slides[] è metadata opzionale).
  - operations[] vuoto → QUESTO è l'unico hard-stop: riporta "ERROR no operations" ed esci. Mai produrre un carousel vuoto in silenzio.
- Il MASTER (template_design_id) è SACRO: si legge solo (get-design / get-design-content). MAI start-editing-transaction sul master. Tutte le modifiche vanno sul WORKING COPY (il duplicato creato allo STEP 1.5).

STEP 0 — Lettura e validazione input
Dal canva_pending.json estrai e tieni in memoria per tutta la sessione:

template_design_id — il MASTER da duplicare (read-only, mai editato)
folder_id — la folder Canva di destinazione
topic — il titolo del carousel
tone — il tono editoriale (usato solo come riferimento)
operations — array di operazioni da applicare
slides — array con il contenuto completo di ogni slide (headline, subhead, body, notes, layout, slide_type, image_placement)
slides_count — numero totale di slide

Controlla ogni operazione replace_text:

Se il testo finisce senza punteggiatura finale (. ! ?) e sembra troncato, segnala: ⚠️ Slide N: testo probabilmente troncato
Se il testo supera 280 caratteri, segnala: ⚠️ Slide N: testo lungo (X chars) — potrebbe non entrare nel frame

Controlla ogni URL nelle operazioni upload-asset-from-url:

Deve essere nel formato https://nuzantara-warroom-images.fly.storage.tigris.dev/warroom/...
Se è in formato path-style (fly.storage.tigris.dev/nuzantara-warroom-images/...) convertila al formato subdomain prima di procedere.
Le URL devono essere DIRETTE (no shortener/redirect 302): upload-asset-from-url NON segue i redirect.

Warning non bloccanti: elencali e vai avanti. Hard-stop solo se operations[] è vuoto (vedi Hard rules).

STEP 1 — VALIDA il master in READ-ONLY (mai editing)
Usa get-design sul template_design_id per contare le pagine vive (live_pages).
Usa get-design-content con content_types ['richtexts'] sul template_design_id per elencare ogni elemento richtext (con element_id e page_index) e contare i richtext eleggibili (width >= 30).

⚠️ NON usare start-editing-transaction sul master. NON usare create-design-from-candidate (richiede un job_id da generate-design, non duplica template esistenti).

Validazione: se live_pages < 11 OPPURE eligible_richtexts < 18 → riporta "ERROR master template degraded" e abortisci (nessuna mutazione Canva è avvenuta — il master è intatto).

Tieni la mappa richtexts del master solo come RIFERIMENTO di struttura. Gli element_id reali su cui editare li ri-leggerai dal WORKING COPY allo STEP 2 (gli ID cambiano nella copia).

STEP 1.5 — DUPLICA il master → crea il WORKING COPY
Usa resize-design con:

design_id: il template_design_id (il master)
width: 1080
height: 1350
title: il topic dal JSON

Salva il new_design_id restituito → questo è il WORKING COPY. Da qui in poi TUTTE le operazioni vanno sul WORKING COPY, MAI sul master.

Subito sposta il WORKING COPY nella folder (così resta in ordine anche se un crash interrompe l'edit):
Usa move-item-to-folder con item_id: new_design_id, folder_id: folder_id dal JSON.
Se la move fallisce → logga "🪂 dup not moved, manual move needed" e PROCEDI (non abortire).

STEP 2 — Apri il WORKING COPY in editing + normalizza + remap element ID
Usa start-editing-transaction sul WORKING COPY (new_design_id), NON sul master.

Dalla risposta della transaction estrai:
La lista di tutti gli elementi richtexts del working copy (con element_id e page_index)
La lista di tutti i frame/immagini del working copy (con element_id e page_index)

NORMALIZZA (wipe): prima di scrivere i testi nuovi, azzera OGNI richtext del working copy (width >= 30) sostituendolo con " " (uno spazio). Questo elimina qualunque residuo che il master potesse portarsi dietro, così nessun "buggy old text" del master finisce nell'output.

Poi, per ogni operazione replace_text nel JSON:
Se element_id è valorizzato → cercalo nella lista richtexts del working copy. Se esiste → usa direttamente. Se NON esiste → cerca nella stessa pagina un elemento con ruolo analogo (prima occorrenza = headline, seconda = body) e usa quell'ID. Logga: 🔄 Remap slide N: [vecchio_id] → [nuovo_id]

ℹ️ Le slide con layout heading-only (slide 9, 11) non hanno slot body — il builder le salta. Se vedi element_id: null è solo per le immagini (STEP 4).

Per ogni operazione upload-asset-from-url:
Se element_id è valorizzato → usalo direttamente. Se element_id è null → cerca nella lista frame/immagini del working copy un elemento con il page_index corrispondente e usalo. Logga: 🖼️ Frame slide N: [element_id]
Se per una pagina non trovi nessun elemento adatto, segnala e salta quella slide.

STEP 3 — Applica i testi con intelligenza editoriale (sul WORKING COPY)
Non eseguire un ciclo robotico di replace_text. Lavora da senior editorial designer: per ogni slide, prendi decisioni creative su gerarchia, spezzatura del testo ed enfasi visiva. Usa slides[] dal JSON — non solo operations[].

Struttura a 3 livelli
Il template ha 3 text element per pagina (non 1 combinato):

| Livello  | Colore                | Contenuto                  |
| -------- | --------------------- | -------------------------- |
| Headline | Bianco, bold, grande  | Prima riga del titolo      |
| Subhead  | Giallo #f9ca55, medio | Sottotitolo / seconda riga |
| Body     | Bianco, regular       | Bullets o prosa            |

Non concatenare headline + subhead in un unico elemento. Mappare sempre il contenuto sui 3 element_id separati per ogni pagina.

Headlines spezzate
Ogni headline va su 2 righe con \n, spezzando dove c'è tensione narrativa o il titolo supera ~4 parole. Esempi:

"ITALY'S GRIP: HOW IT WORKS" → "ITALY'S GRIP:\nHOW IT WORKS"
"THE TIE-BREAKER NOBODY READS" → "THE TIE-BREAKER\nNOBODY READS"
"WHAT 'DECOUPLING' ACTUALLY MEANS" → "WHAT 'DECOUPLING'\nACTUALLY MEANS"
"AIRE IS NOT ENOUGH" → lasciare su una riga se già corta e incisiva

Salient moment slides
Se slide_type: "D" o notes contiene "SALIENT MOMENT":
Body svuotato ("") — nessun testo nel body element
Solo headline + subhead: tutta la forza va sulla frase + immagine
Non aggiungere bullets o testo aggiuntivo

Body text
Usare \n\n tra ogni bullet per respirabilità
Se il contenuto ha 3 bullets e c'è logica narrativa, valutare un quarto che completi l'arco informativo
Massimo ~40 parole per bullet, nessun muro di testo

Aggiorna il titolo del design con il topic dal JSON.
Applica tutte le operazioni in bulk con perform-editing-operations (slide 1-6 in un blocco, slide 7-11 in un secondo blocco).

STEP 3.5 — Formatting editoriale (bold + keyword color)
Dopo i replace_text, esegui un secondo pass di formattazione. Non saltare questo step — è ciò che trasforma il carousel da flat a curato.

Bold selettivo sul body
Per ogni elemento body: applica format_text con font_weight: bold sull'intero elemento. Poi usa find_and_replace_text per "marcare" visivamente i termini chiave (il testo rimane identico, il bold globale li valorizza già).

Termini da enfatizzare (bold o colore giallo #f9ca55)
Scegliere 2-3 per slide, non di più:
Acronimi legali IT: AIRE, IRPEF, DTT, TUIR, UUPA
Acronimi legali ID: KITAS, KITAP, E33G, NPWP, PT PMA, IMTA, BPN, PPAT, BPHTB, PPh, PNBP, PBB, OSS, LKPM, NIB, ITAS, ITAP
Concetti chiave: center of vital interests, Hak Pakai, tie-breaker, fiscal domicile, nominee agreement, Hak Milik, leasehold
Numeri shock: percentuali (35%, 43%), cifre IDR/USD, anni (30 years, 80 years)

STEP 4 — Inserisci le immagini (sul WORKING COPY)
Per ogni operazione upload-asset-from-url:
Chiama upload-asset-from-url con l'URL DIRETTA dell'immagine (no redirect 302)
Ottieni l'asset_id restituito
Usa perform-editing-operations per posizionare l'asset nel frame del page_index corrispondente (trovato allo STEP 2)

Decisioni di posizionamento per tipo di layout:
layout: "full_bleed" → update_fill sul frame full-background
layout: "split" → immagine nella metà inferiore o destra (coordinate: left=540, top=0, width=540, height=1350)
element_id: null → usare insert_fill con coordinate calcolate in base al campo placement nel JSON
Cover: sempre full-bleed, testo overlay

Al termine usa commit-editing-transaction (sul WORKING COPY).

STEP 5 — (ELIMINATO in v4) Niente duplicazione finale
Il working copy È GIÀ il design finale: è stato creato allo STEP 1.5 duplicando il master, poi editato. Il master non è stato toccato. Non c'è nessuna ulteriore resize/duplicate da fare. (Lo STEP 6 vecchio — move-item-to-folder — è già stato fatto allo STEP 1.5.)

STEP 7 — Verifica visiva (sul WORKING COPY)
Usa get-design-thumbnail per le pagine 1, centrale e ultima del working copy (new_design_id).
Checklist:
Cover (pagina 1): immagine posizionata, headline leggibile
Slide centrale: testo non troncato, body visibile, bold sui termini chiave
Ultima slide (CTA): headline + subhead presenti, logo Bali Zero visibile
Nessuna pagina vuota o con testo placeholder del template

Se trovi problemi (testo mancante, immagine non posizionata), rientra in editing sul working copy (NON sul master) e correggi. Se tutto OK, procedi.

STEP 8 — Aggiorna il file e riporta
Aggiorna canva_pending.json aggiungendo/sovrascrivendo (design_id = il WORKING COPY, MAI il master):

```json
{
  "design_id": "<new_design_id>",
  "design_url": "https://www.canva.com/design/<new_design_id>/edit",
  "status": "applied",
  "applied_at": "<ISO timestamp>"
}
```

Output finale da mostrare:

```
✅ Carousel applicato
Topic: <topic>
Design: https://www.canva.com/design/<new_design_id>/edit
Folder: <folder_id>
Testi applicati: X / Y
Immagini inserite: X / Y
Remap effettuati: X
⚠️ Warning: <lista o "nessuno">
```

Note tecniche ricorrenti (da non dimenticare ogni sessione):

Il MASTER non viene MAI editato — si valida read-only (STEP 1), si duplica (STEP 1.5), si edita il duplicato. Un crash lascia il master pristino: solo un duplicato orfano da GC.
resize-design restituisce un nuovo design ID — salvarlo subito (è il working copy)
Gli element ID cambiano nella copia rispetto al master — leggerli SEMPRE dalla transaction del working copy (STEP 2), mai assumere quelli del master
Le URL Tigris devono essere in formato subdomain, non path-style; e DIRETTE (no redirect — upload-asset-from-url non segue 302)
La folder destinazione è il folder_id dal JSON (Carousel folder di Bali Zero)
Slide 9 e 11: layout heading-only — NON hanno slot body. Il builder non emette operazioni body per queste. Normale.
3 text element per pagina (headline/subhead/body) — MAI concatenarli in un unico replace_text
Salient moment slides (slide_type: "D"): body element vuoto, solo headline + subhead
STEP 3.5 obbligatorio: bold + keyword color — non saltarlo, è il passo che differenzia il ciclo robotico dal design curato
Se element_id: null in un'operazione immagine → usare insert_fill con coordinate esplicite
NEVER AskUserQuestion: usa i fallback hardcoded nelle Hard rules
