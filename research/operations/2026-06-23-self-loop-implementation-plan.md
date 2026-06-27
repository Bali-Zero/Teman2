---
date: 2026-06-23
domain: operations
client_case: none (internal method / organism self-improvement)
sources:
  - research/operations/2026-06-23-anthropic-self-improvement-loop.md  # la research che lo motiva
  - .claude/rules/cicatrix-superscar.md  # le 10 famiglie + antidoti
  - dna_organismo_unico_2026_06_23.md  # le 7 leggi L0-L6
status: PROPOSAL — attende GO Zero anello per anello (L6: cura al confine operatore)
---

# Piano: attivare il self-loop positivo e naturale dell'organismo

> **Tesi (dalla research):** Anthropic non ha *un* loop magico. Ha il principio "**giudicare < generare**"
> istanziato in 4 loop concreti. Il nostro organismo ne istanzia gia 3 su 4 (cascade=debate, hook=verify,
> opus-mythos=generator!=grader). **Manca il Loop B:** trasformare ogni fallimento reale in un **test eseguibile**
> che fallisce se la malattia rimorde. Oggi le nostre cicatrici sono *prosa*; Anthropic le gradua in
> *regression suite*. Questo piano chiude QUEL gap — e lo fa **naturale**: non un framework nuovo, ma
> promuovere a struttura un riflesso che abbiamo gia usato 2 volte oggi (premise_gate, W86).

---

## Principio guida (perche "naturale" e non "costruito")

Un loop e **naturale** quando e il percorso di minor resistenza, non una disciplina che va ricordata.
La superscar #2 lo dice gia: *"se una regola critica e violabile, scrivi un hook. Documentazione non basta."*
Il loop positivo nasce quando **il gesto giusto e anche il piu facile**:

- Oggi: cicatrice nuova -> 5 min per scrivere prosa in cicatrix-scars.md. Il test eseguibile e *extra* -> non si fa.
- Obiettivo: cicatrice nuova -> il `scar` CLI **chiede** "qual e il test che fallisce se rimorde?" e lo crea per te.
  Il test diventa il percorso di default, non l'eccezione virtuosa.

**Cosa NON e questo piano:** non e RLAIF (non addestriamo pesi — non possiamo e non serve, Loop A e Anthropic-only).
E il nostro **Loop B+C runtime**: harness che migliora harness, fallimenti->test, generator!=grader.

---

## I 4 anelli (in ordine di leva, ciascuno indipendente e GO-gated)

### Anello 1 — Scar -> Fact-gate eseguibile  *(il gap chiave; leva massima)*
**Cosa:** estendere il `scar` CLI cosi che ogni nuova cicatrice produca, oltre alla prosa, un **artefatto
eseguibile** che la cattura: un test (test_W<N>.py) o un hook-rule. Il pattern esiste gia — W86 ha
test_w84_strip_noise_cross_line.py (innocenza+colpevolezza), premise_gate ha test_premise_gate.py.
Questo li rende **obbligatori, non occasionali**.

**Implementazione concreta:**
1. `scar` CLI guadagna un prompt finale: *"Test eseguibile per questa scar? (path o 'skip-with-reason')"*.
   `skip` richiede una ragione loggata (no silent-skip — lezione superscar #2).
2. Cartella infra/scar-gates/ raccoglie i test-per-scar. Un runner scripts/scar_gates_run.sh li esegue tutti.
3. **Regola d'oro famiglia #3:** ogni gate ha test di *innocenza* (non scatta su caso legittimo) E *colpevolezza*.
4. Mappa scar->gate in infra/scar-gates/MANIFEST.json (quale W-number ha quale test; quali sono ancora prosa-only).

**Segnale di feedback:** il gate fallisce <=> la malattia e rimorsa. Deterministico, non LLM-judge.
**Cosa chiude il loop:** CI/cron esegue i gate; un fallimento riapre la scar.
**Effort:** M (1 sessione). **Reversibile:** si (CLI flag opt-in inizialmente).

### Anello 2 — Heartbeat Semantico (il monitor L2, da prosa ad allarme)
**Cosa:** il DNA L2 dice "sano = ha sentito il mondo e ha cambiato qualcosa". Oggi e una frase. Renderla
un **reconciliation-report** (gia prescritto dall'antidoto superscar #2 "Armamento Sospeso"): un segnalatore
— NON un auto-attuatore — che ogni N ore confronta *costruito vs attivato* e allarma su deriva.

**Implementazione concreta:**
1. scripts/heartbeat_semantico.py (cron Mini, gia il ruolo H24): per ogni organo censito nel TAC
   (cascade, loop A-F, hook, MOS), verifica un **proof-of-life end-to-end**, non l'exit-code:
   - cascade: 1-token ping per tier (Claude/agy/codex/ollama) — la regola "health-check, non assume".
   - hook: esegui i gate dell'Anello 1 -> tutti verdi?
   - MOS: `mem stats` cresce? ultima `mem save` < 7gg?
   - loop WR2: ultima esecuzione ha *cambiato* qualcosa (nuovo output) o e girata a vuoto?
2. Output: report ~/logs/heartbeat-YYYYMMDD.md + Telegram P1 SOLO se un organo e "verde ma morto".
3. **Distingue firebreak legittimo** (publish/business pause) da debito tecnico (antidoto #2).

**Segnale:** proof-of-life vs exit-code. **Chiude il loop:** allarme -> operatore decide (L6).
**Effort:** M-L. **Reversibile:** si (read-only, mai auto-fix — kill-switch env).

### Anello 3 — Reflexion che impara davvero (curare A-loop: "1/8 impara")
**Cosa:** il TAC ha trovato che dei loop di apprendimento solo 1/8 *impara davvero*. La research conferma il
perche: imparare != proposals_passed; imparare = errore->memoria(con l'esperienza)->comportamento diverso.
Anthropic chiude questo con subagent-memory persistente + reflexion-store. Noi abbiamo MOS — sotto-usato dai loop.

**Implementazione concreta:**
1. Ogni loop agentico (WR2, regulatory-watcher, ecc.) a fine run scrive una **lesson 1-riga in MOS**
   (mem save lesson) SE e SOLO SE ha avuto un override umano o un fallimento — non a ogni run (no noise).
2. A inizio run, il loop fa mem query sul proprio dominio -> carica le proprie lesson passate in context.
   Questo e il reflexion-store Anthropic, su substrato MOS che gia abbiamo.
3. Metrica di salute (per Anello 2): un loop e "che impara" se le sue lesson cambiano il suo output nel tempo.

**Segnale:** override umano / fallimento. **Chiude il loop:** lesson ripescata al run successivo.
**Effort:** L (tocca piu loop). **Reversibile:** si (per-loop opt-in).

### Anello 4 — Generator != Grader come default (promuovere opus-mythos a riflesso)
**Cosa:** la research dice che il pattern piu maturo che abbiamo e opus-mythos TAC ("mai fidarti del proprio
subagent + verifica live su disco"). Renderlo il **default dei workflow critici**, non solo del TAC manuale.

**Implementazione concreta:**
1. Template-workflow riusabile infra/workflows/verify-template.js: gather->adversarial-verify->synthesize
   (esattamente lo schema usato per QUESTA research). Gia provato 3x oggi (KBLI, research). Promuoverlo a
   skill/snippet citabile, cosi ogni futura research/audit lo eredita.
2. Regola: nessun finding critico (security, regulatory, quote cliente) si committa senza un refuter
   indipendente su context fresco. E gia in CLAUDE.md sez.6 (4-LLM panel) — l'Anello lo rende il path di default.

**Segnale:** refuter su context isolato. **Chiude il loop:** finding sopravvive solo se non-refutabile.
**Effort:** S (e cattura di un pattern, non codice nuovo). **Reversibile:** N/A (convenzione).

---

## Sequenza consigliata (leva / effort)

| # | Anello | Leva | Effort | Quando |
|---|---|---|---|---|
| 1 | **Scar->fact-gate** | massima (chiude IL gap) | M | **primo** — e il Loop B mancante |
| 4 | Generator!=grader template | alta | S | **subito dopo** (quasi gratis, e cattura) |
| 2 | Heartbeat Semantico | alta | M-L | terzo (richiede Anello 1 per il check-hook) |
| 3 | Reflexion che impara | media | L | quarto (piu invasivo, tocca i loop vivi) |

**Perche quest'ordine:** Anello 1 e il fondamento (gli altri lo usano come check). Anello 4 e quasi gratis
(promuovi un pattern gia provato). Anello 2 dipende da 1. Anello 3 e il piu invasivo -> ultimo.

---

## Confine operatore (L6) — cosa decidi TU, cosa faccio IO

- **Io, senza chiedere:** Anello 4 (e convenzione + un file template), e lo scaffold read-only di Anello 1/2.
- **GO esplicito tuo, anello per anello:** qualsiasi cosa che *arma* (modifica scar CLI, installa cron Mini,
  tocca i loop WR2 vivi). Stesso pattern di oggi: costruisco+testo (innocenza+colpevolezza) -> ti mostro ->
  **tu armi** (o mi dici "armalo tu").
- **Mai autonomo:** auto-fix da Heartbeat (resta segnalatore, mai attuatore — antidoto #2 + L6).

---

## Il loop, in una frase

> Ogni fallimento dell'organismo diventa un **test che fallisce se rimorde** (Anello 1), monitorato da un
> **battito che misura l'esito non l'exit-code** (Anello 2), con loop che **ricordano i propri errori**
> (Anello 3) e findings che **sopravvivono solo se un refuter non li abbatte** (Anello 4).
> Positivo perche ogni cicatrice rende l'organismo piu forte, non solo piu documentato.
> Naturale perche il gesto giusto diventa il piu facile — non una disciplina da ricordare, un riflesso.

**Gia fatto oggi (la prova che e naturale, non teorico):** premise_gate e W86 SONO due istanze dell'Anello 1
prima ancora che l'Anello 1 esista. Il piano non inventa — promuove a struttura cio che l'organismo gia fa.
