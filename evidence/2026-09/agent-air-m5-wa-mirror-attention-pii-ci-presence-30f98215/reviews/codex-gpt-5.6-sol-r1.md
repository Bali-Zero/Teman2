[M5] **REWORK**

1. **HIGH — Identità delle classi persa** (`expected.add((module, sub.name))`, nuova riga 144; `ran.add((module, name))`, 154).  
   `TestA.test_guard`, `TestB.test_guard` e una funzione top-level `test_guard` diventano la stessa chiave. Deselezionarne uno lascia il controllo verde se un altro viene eseguito. Conservare l’intero percorso delle classi nell’identità attesa e in quella estratta dal JUnit. La presenza attuale di queste collisioni è **not shown**.

2. **HIGH — Classi annidate ignorate** (`for sub in node.body`, righe 142–144).  
   Il controllo visita soltanto i metodi direttamente nella classe top-level. Pytest può raccogliere `TestOuter.TestInner.test_guard`, ma questo test non entra in `expected`: eliminarlo dalla raccolta può passare verde quando altri test mantengono `expected` non vuoto. Serve attraversamento ricorsivo delle classi, conservandone il percorso. Classi annidate nei file attuali: **not shown**.

3. **MED — Definizioni duplicate nascoste dal set** (`expected = set()` e aggiunte, righe 134–144).  
   Due `def test_guard` nello stesso scope producono una sola aspettativa; Python mantiene soltanto l’ultima definizione e il controllo passa. Per garantire ogni definizione sorgente, rilevare e rifiutare duplicati nello stesso scope prima della deduplicazione. Questo caso richiede una modifica sorgente, ma contraddice comunque la garanzia dichiarata. Duplicati attuali: **not shown**.

4. **LOW — La copertura resta per definizione, non per parametro** (`split("[")[0]`, riga 150).  
   Deselezionare una sola variante parametrizzata rimane verde se un’altra variante della stessa funzione viene eseguita. È coerente con la normalizzazione richiesta, ma il commento «drops any of them turns this RED» dovrebbe precisare questo limite. Punti o parentesi negli ID non compromettono il riconoscimento del nome base.

Gli altri controlli mostrati sono corretti: `not expected` impedisce il verde vacuo; un file escluso dalla raccolta resta nell’AST e genera assenze; nomi uguali in file con basename differenti restano distinti. Il basename, però, non autentica il percorso completo di eventuali test raccolti altrove; raccolta aggiuntiva: **not shown**.

Non emerge un falso RED generalizzato: i prefissi JUnit ordinari dovuti al rootdir conservano il segmento del modulo; `test`/`Test` corrispondono ai prefissi predefiniti pytest, underscore inclusi. Le definizioni async vengono incluse. Override di raccolta, decorator che sopprimono test o `__test__ = False` possono produrre RED, coerentemente con la regola dichiarata; configurazioni e decorator effettivi: **not shown**.

Il guard sulla base vuota precede correttamente `git diff`. `grep … || rc=$?` preserva il codice senza uscita anticipata sotto `set -e`; i rami 0/1/errore sono corretti. L’indentazione mostrata del blocco YAML e dell’heredoc è valida. Le prove locali riportate dal builder non sono state verificate in questa review statica.
