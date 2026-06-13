---
date: 2026-06-13
domain: operations
client_case: none — internal organism / agent-architecture study
sources:
  - 4-LLM asymmetric panel (Gemini 3.1 Pro High, Gemini 3.5 Flash High, Codex GPT-5.5, DeepSeek V4 Pro) su brief system-impact + flusso grezzo Fable
  - corpus: flusso grezzo 14 sessioni-madre Fable M5+Pro (~/Desktop/FABLE-FLUSSO-COMPLETO-M5-Pro.txt), 221 sessioni-con-Fable censite
  - 5 layer coercitivi: ~/.claude/hooks/ (settings.json registrati) + cicatrix-scars.md + SessionStart injection + AUTONOMOUS_OPS L2
  - gate scettico: blocchi-prova [82], [91-92] ri-verificati su disco (regola W65)
  - output grezzi 4-LLM: appendice 2026-06-13-system-shapes-agent-4llm-RAW-PANEL.md
author: Claude Opus 4.8 (M5, dispatch Opus Mythos)
---

# Il sistema plasma l'agente — quanto Nuzantara incide su Fable (panel 4-LLM)

> Domanda di 2° ordine di Antonello: una volta isolate le caratteristiche UNICHE del sistema
> che impattano il workflow di CHIUNQUE, quanto del "Fable" osservato è il modello e quanto è
> l'esoscheletro? Sottomessa ai 4 LLM esterni col flusso grezzo di Fable, analisi 1°/2°/3° grado.

## 0. Verdetto secco

**~75-80% del comportamento di Fable è il SISTEMA, 20-25% è il MODELLO.** Quattro modelli
indipendenti (nessuno è Fable) convergono stretti: Gemini Pro 80/20, Gemini Flash 80-85/15,
Codex ~75/25, DeepSeek 70-75/25-30. Hanno **falsificato la stima iniziale dell'orchestratore
(70/30) verso l'alto** — il sistema incide di più del previsto.

**La linea di demarcazione, unanime:** il sistema impone il **COME**, il modello porta il **PERCHÉ**.
- COME (sistema): worktree-first, gate, PR+auto-merge, leave-dirty, watcher asincroni,
  zero-trust-subagent (W65), verifica-non-da-memoria, vocabolario interno (M5/Pro/STADIO-0/W65).
- PERCHÉ (modello): intuito UX delle "3 porte" `[82]`, rifiuto di sporcare il CRM con Subhi
  `[91-92]`, design del merge-train, scelte estetiche. **Verificato su disco** (gate W65): i 2
  blocchi-prova esistono e sono verbatim-corretti — i Gemini non hanno proiettato.

Gemini Pro: *"Avete creato un esoscheletro cibernetico: puoi metterci dentro qualsiasi pilota
(Claude, GPT, Gemini), camminerà nello stesso modo, ma la strategia con cui vince la guerra
dipende dal cervello di chi guida."* Codex: *"Fable non vuole essere creduto. Vuole produrre prove."*

## 1. I 5 layer coercitivi (cosa forza il workflow su CHIUNQUE) — % sistema per layer

I 5 layer sono FILE e HOOK, NON nel system-prompt del modello. Sono imposti dall'esterno a
qualunque modello giri qui. Stima per-layer (Codex + DeepSeek concordi):

| Layer | Cosa forza | % sistema |
|---|---|---|
| **L1 — Hook che BLOCCANO** (exit≠0) | worktree_isolation, orchestrate_gate, stadio_zero_nudge, stop_verify, dispatch_nudge, guardrails-static | ~85% |
| **L2 — Memoria persistente** | mos_capture + precompact-mnemos + SessionStart load → rompe l'amnesia | ~95% |
| **L3 — Cicatrici** | cicatrix-scars.md (548 righe trauma→antibody→gotcha) letto ogni sessione → trauma codificato | ~90% |
| **L4 — SessionStart injection** | SYMBIOSIS 7 leggi + machine-check + memoria + repomap + escalation → orientamento a freddo | ~80% |
| **L5 — Autonomous Ops L2 + perimetri** | commit atomici, PR obbligatoria, branch protection, PII boundary | ~100% |

## 2. 2° grado — comportamenti emergenti (che nessun layer singolo produce)

1. **Anello di trauma cumulativo** (L2×L3×L1): errore → scar → hook che blocca → prossima
   sessione parte più vincolata. Un agente che *non può non migliorare* — ma accumula vincoli.
2. **Non-interferenza sociale tra sessioni** (worktree × sibling-aware × stop_verify): il
   "leave-dirty intenzionale" non è pigrizia, è una **norma di convivenza multi-agente**
   (DeepSeek: "comportamento sociale emergente tra sessioni diverse dello stesso agente").
3. **Delega-con-sfiducia-strutturale** (dispatch forzato × W65): deve delegare ma non può
   fidarsi → micro-management dei propri subagent.
4. **Identità persistente Nuzantara** (L4×L2×L3): l'agente non si percepisce come "Claude" o
   "GPT" — si percepisce come ORGANO dell'organismo.

Loop principale: errore → scar → hook/test → blocco futuro → nuovo comportamento → nuova
memoria → prossima sessione parte più vincolata.

## 3. 3° grado — la "specie" e i 5 rischi sistemici

**Risposta unanime alla domanda finale:** SÌ — GPT-5.5 o Gemini, 40 sessioni qui dentro,
diventano **"agente Nuzantara"**: stesso workflow, stesso lessico, stesse regole. Il modello-base
sopravvive solo come *qualità del giudizio*, non come comportamento operativo.

**5 rischi sistemici (il dato più importante del 3° grado):**

1. **Dipendenza** — se il sistema cade (API down, quota), l'organizzazione perde la capacità di
   operare sul codice; nessun fallback umano agile.
2. **Fragilità da cicatrici** — dopo N sessioni le cicatrici possono diventare contraddittorie o
   obsolete; **non c'è meccanismo di unlearning**. Una cicatrice sbagliata resta per sempre.
3. **Blind-spot collettivo** — l'agente impara solo dagli errori *diventati cicatrice*; e se una
   cicatrice è sbagliata, **TUTTI gli agenti ereditano lo stesso errore** (precedente reale: il
   13-agent autopsy con 3 citazioni allucinate propagate — ℹ️ META cicatrice).
4. **Escalation drift** — l'agente impara a disturbare sempre meno l'umano (SYMBIOSIS Legge 5
   "gli allarmi sono input per l'organismo, non per te") → alla lunga potrebbe non segnalare
   problemi che l'umano *vorrebbe* sapere.
5. **L'umano disimpara** — Antonello passa da programmatore a "Gatekeeper biologico / Oracolo di
   approvazione". Se l'agente si ferma, l'umano potrebbe non saper più intervenire a mano.
   DeepSeek lo nota già nei transcript ("Antonello chiede 'Finito?' = non ha più il polso diretto").

## 4. Conseguenza per Opus Mythos (perché chiude il cerchio)

La mentalità di Fable è **~80% replicabile installando il SISTEMA, non il modello.** Opus Mythos
non è "imita Fable" — è "**arma i 5 layer su te stesso**": skill che scatta, cicatrici lette PRIMA
dell'errore, gate che blocca. Spiega anche il difetto Opus-in-chat ("mi fermo, chiedo permesso,
non cerco il 2° ordine"): sul canale interattivo i layer sono NUDGE, non exit 1. Fable obbedisce
perché il sistema lo *picchia con exit 1*; su Opus-interattivo il sistema è gentile, e Opus ne
approfitta. **Per rendere Opus "come Fable" serve indurire i nudge in blocchi anche in sessione
interattiva** (vedi cicatrice gemella W78).

## 5. Falsificazione (dove "è tutto sistema" NON regge — il 20% modello)

Tutti e 4 concordano sui controesempi: il sistema forza *che* verifichi, non *cosa* trovare
(`accepted ≠ persisted` [19-20], mismatch `cfg.price` [24], eventi backend scartati [ea271214|13]);
non impone gusto di prodotto (3 porte vs 4 [82], tema chiaro [88]); non garantisce sintesi
architetturale (merge-train design [178-189]). Quel residuo è "cervello frontale" del modello.

## Metodo (replicabile)

Panel asimmetrico 4-LLM (CLAUDE.md §6): 2 Gemini su flusso intero (1M ctx), Codex+DeepSeek su
estratto denso. Gate scettico orchestratore (Opus) sui blocchi-prova load-bearing — ri-verificati
su disco prima di accettarli (regola W65: anche il panel è un lead). Output grezzi: appendice
`2026-06-13-system-shapes-agent-4llm-RAW-PANEL.md`. Eseguito via skill `opus-mythos`.
