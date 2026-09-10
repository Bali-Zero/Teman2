# Codex adversarial review — round 2 (seat codex, gpt-5.6-sol, 2026-09-10, on v2 uncommitted)

Verdetto complessivo: **REWORK**. Ci sono blocker di eseguibilità, accettazioni non falsificabili e rischi seri soprattutto in S5.

1. **[BLOCKER] Il percorso ORANGE apre il modello sbagliato.** Il README consente ORANGE ma ordina sempre di avviare `claude-opus-5`; ogni mandato ripete Dux Opus e apertura Claude anche quando Zero dichiara ORANGE. In ORANGE il Dux deve essere Sol: “ri-risolvere i seat” dopo l’avvio non può trasformare la sessione radice. [README.md:7](README.md:7), [S1:6](S1-arm-the-armer.md:6), [S2:6](S2-custody.md:6), [S3:6](S3-arm-the-auditors.md:6), [S4:8](S4-reaper-and-signal.md:8), [S5:6](S5-brain-that-can-forget.md:6).

2. **[HIGH] Nomina del Dux senza il secondo imperator.** Il board definisce lo staff room come Fable + Zero e i cinque mandati dichiarano il Dux nominato dalla stessa coppia. La dottrina richiede Fable + Astra con Zero e l’approvazione di entrambi gli imperator. [README.md:3](README.md:3), [S1:7](S1-arm-the-armer.md:7), [S5:7](S5-brain-that-can-forget.md:7).

3. **[HIGH] Il “grunt lane” aggira il formato obbligatorio del board.** Il README afferma che ogni implementazione richiede un battle window a sette sezioni, poi assegna modifiche a hook, docs-sync, dipendenze, retry e generatori a una lane senza mandato, Dux, worktree, appetite, Bites o gate. È un sesto programma multi-organo mascherato da coda. [README.md:5](README.md:5), [README.md:81](README.md:81), [README.md:142](README.md:142).

4. **[HIGH] Wave 2 parte prima che S1 abbia dimostrato di funzionare.** README, S3 e S4 aprono Wave 2 appena il PR S1 è “armed”; S1 considera invece riuscita la cura solo dopo merge, pull e sei tick puliti. Un PR armato lascia operativo il vecchio re-armer rotto, quindi non rende affatto più economici i PR successivi. [README.md:59](README.md:59), [S1:63](S1-arm-the-armer.md:63), [S1:119](S1-arm-the-armer.md:119), [S3:9](S3-arm-the-auditors.md:9), [S4:11](S4-reaper-and-signal.md:11).

5. **[BLOCKER] La procedura DIRTY viola il freeze.** Tutti i file autorizzano `disarm → merge origin/main → push → re-arm`. Il Builder Contract dice che una branch diventa read-only dal primo arm; disarmarla non annulla retroattivamente il freeze. Il README riconosce il conflitto, ma inventa una deroga non ruled. [README.md:66](README.md:66), [README.md:114](README.md:114), [S1:47](S1-arm-the-armer.md:47), [S5:73](S5-brain-that-can-forget.md:73).

6. **[HIGH] S1 non è più un solo organo/sessione.** Comprende shepherd su Pro, due sibling su Mini, tre famiglie di comportamento, almeno due code PR, una lane esterna e un’ora di osservazione live. Va separato il lavoro Mini o ridotto al solo shepherd. [S1:14](S1-arm-the-armer.md:14), [S1:30](S1-arm-the-armer.md:30), [S1:51](S1-arm-the-armer.md:51), [S1:79](S1-arm-the-armer.md:79).

7. **[BLOCKER] La prova live di S1 fallisce con uno squash merge.** `merge-base --is-ancestor <sha> HEAD` non può provare la presenza del PR se `<sha>` è il PR HEAD e il merge è squash. Deve verificare il merge commit o, preferibilmente, il contenuto/blob installato. [S1:65](S1-arm-the-armer.md:65).

8. **[MEDIUM] La release omette la strategia canonica.** Tutti i mandati prescrivono `gh pr merge <N> --auto`, mentre modus prescrive `--auto --squash`. Il comando può essere accettato dalla merge queue, ma non dimostra che la strategia richiesta sia stata impostata. [S1:109](S1-arm-the-armer.md:109), [S2:126](S2-custody.md:126), [S3:152](S3-arm-the-auditors.md:152), [S4:119](S4-reaper-and-signal.md:119), [S5:137](S5-brain-that-can-forget.md:137).

9. **[MEDIUM] I comandi checkpoint non funzionano letteralmente.** `<staff-room session id>` viene interpretato dalla shell come redirezione, non come argomento. Per mandati definiti “paste-ready” serve un comando che ricavi e quoti un ID concreto. [S1:93](S1-arm-the-armer.md:93), [S2:109](S2-custody.md:109), [S3:136](S3-arm-the-auditors.md:136), [S4:105](S4-reaper-and-signal.md:105), [S5:113](S5-brain-that-can-forget.md:113).

10. **[HIGH] S2 non definisce l’intervallo che dovrebbe provare.** “Entro un audit interval” e “one scheduled run later” sono non falsificabili perché plist e mandato non fissano alcuna cadenza o latenza massima. Inoltre il risultato live hardcoded “7 files, 0 findings” considera fallimento proprio il caso in cui il detector trovi una vera esposizione o cambi il numero legittimo di file. [S2:16](S2-custody.md:16), [S2:79](S2-custody.md:79), [S2:101](S2-custody.md:101).

11. **[BLOCKER] La sequenza di accettazione S3 è impossibile.** Probe e correzione di INDEX.md sono nello stesso PR, ma la produzione deve mostrare prima DIVERGED e poi OK “dopo la correzione”. Il deploy atomico non può esporre quello stato intermedio. Inoltre l’mtime di `last.json` non prova che sia stato launchd a produrlo. Servono due PR o una prova pre-merge controllata e un log launchd causalmente attribuibile. [S3:41](S3-arm-the-auditors.md:41), [S3:98](S3-arm-the-auditors.md:98), [S3:101](S3-arm-the-auditors.md:101), [S3:158](S3-arm-the-auditors.md:158).

12. **[BLOCKER] Il comando pytest di S4 non esiste in questo checkout.** La root `.venv/bin/python3` è assente; la venv verificata è sotto `apps/backend-rag/.venv`. Il Bite non è eseguibile come scritto. [S4:73](S4-reaper-and-signal.md:73).

13. **[BLOCKER] S4 non definisce il mute ceiling e il rollback può annullare ogni successo.** “Within the bound” non assegna un numero. Peggio: se la baseline delle 24 ore è zero — probabile mentre P0 è silenziato — la prima re-raise voluta supera `2 × 0` e attiva immediatamente il rollback. [S4:18](S4-reaper-and-signal.md:18), [S4:72](S4-reaper-and-signal.md:72), [S4:111](S4-reaper-and-signal.md:111), [S4:128](S4-reaper-and-signal.md:128).

14. **[BLOCKER] S5 non può stare in una sessione da otto ore.** Include nuovo purge tool, logica TTL, schema/archive e FTS, modifica diretta del writer, backup verificato, pausa daemon, purge, VACUUM, sincronizzazione HOME, follow-up PR e ledger. Una prova obbligatoria avviene addirittura “next morning”, esplicitamente oltre il deadline. [S5:14](S5-brain-that-can-forget.md:14), [S5:36](S5-brain-that-can-forget.md:36), [S5:65](S5-brain-that-can-forget.md:65), [S5:87](S5-brain-that-can-forget.md:87), [S5:105](S5-brain-that-can-forget.md:105).

15. **[BLOCKER] S5 contraddice il proprio divieto di DELETE e il gate non copre la chirurgia reale.** Dice che ogni DELETE aspetta ruling e firma, ma l’integrazione cancella un record dal DB live senza tale precondizione. Il gate firma soltanto il dry-run; `--apply`, modifica di `~/.claude/scripts/mem`, copia HOME e VACUUM avvengono dopo, senza un nuovo gate indipendente sullo stato risultante. [S5:18](S5-brain-that-can-forget.md:18), [S5:79](S5-brain-that-can-forget.md:79), [S5:98](S5-brain-that-can-forget.md:98), [S5:139](S5-brain-that-can-forget.md:139).

16. **[BLOCKER] S5 crea nuove copie sensibili senza lifecycle enforcement.** Il backup completo viene messo in `$HOME/memory-surgery`, fuori dal prune delle backup esistenti; “record when it will be deleted” non è un consumer. `mkdir -m 700 -p` inoltre non corregge i permessi di una directory già esistente. Anche “archive table or dated file” lascia aperta la creazione di un file cleartext contenente memoria sensibile, senza path, permessi, cifratura o retention. [S5:45](S5-brain-that-can-forget.md:45), [S5:66](S5-brain-that-can-forget.md:66), [S5:114](S5-brain-that-can-forget.md:114), [S5:122](S5-brain-that-can-forget.md:122).

17. **[BLOCKER] Il rollback S5 può perdere dati validi.** `.restore '$BK'` sostituisce l’intero DB con la copia pre-operazione. Se il daemon è ripartito o sono avvenuti nuovi `mem save`, ogni scrittura successiva al backup viene persa. Serve quiescenza fino alla chiusura del gate oppure rollback per delta con riconciliazione delle nuove righe. [S5:146](S5-brain-that-can-forget.md:146).

Controlli negativi:

- Nessun mandato autorizza modifiche a `zantara_core.py`, `fly.toml` o `apps/bali-intel-scraper/backend/db/migrations/env.py`.
- S2 legge soltanto metadati dei `.env*` e ne vieta apertura/modifica/chmod: non è una mutazione off-limits, ma l’eccezione read-only andrebbe resa esplicita.
- Nel diff non risultano segreti o PII cliente in chiaro. S5, però, autorizza nuovi artefatti potenzialmente sensibili senza controlli sufficienti, come indicato nel finding 16.

| File                        | Verdetto |
| --------------------------- | -------- |
| README.md                   | REWORK   |
| S1-arm-the-armer.md         | REWORK   |
| S2-custody.md               | REWORK   |
| S3-arm-the-auditors.md      | REWORK   |
| S4-reaper-and-signal.md     | REWORK   |
| S5-brain-that-can-forget.md | REWORK   | === stderr tail === |
