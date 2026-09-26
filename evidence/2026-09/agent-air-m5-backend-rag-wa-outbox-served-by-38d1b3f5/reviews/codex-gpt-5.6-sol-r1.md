[Air-M5] Revisione statica del solo diff fornito: nessun comando o test eseguito.

**(1) Deploy-window safety — ACCEPT-WITH-NOTES**

La mitigazione copre il caso descritto: se `served_by` manca, PostgreSQL rifiuta il primo UPDATE con `UndefinedColumnError`; l’uscita dal contesto transazionale effettua il rollback prima del secondo `_finalize()`. Il retry mantiene gli stessi parametri e la stessa fence, omette soltanto `served_by` e **non richiama Graph**.

Con la colonna nella forma dichiarata, `$6::text` accetta sia i token stringa sia `None`, convertito in SQL NULL. Non emerge un nuovo problema di tipo o nullabilità.

Note:

- **Non ampliare le eccezioni intercettate.** Errori di connessione, vincoli o altri errori SQL non dimostrano che omettere `served_by` risolva il problema.
- Il `catch` attuale comprende **tutta** `_finalize()`, quindi anche un `UndefinedColumnError` proveniente dall’UPDATE di `meta_inbox_messages` o da `_apply_pending_status`. Il fallback generalmente fallirebbe ancora, ma il warning attribuirebbe erroneamente la causa alla migrazione 322. Meglio distinguere l’errore del primo UPDATE, continuando a intercettarlo **fuori** dalla transazione abortita.
- La soluzione strutturale più pulita è applicare la migrazione dalla nuova release **prima di attivare i nuovi worker**. Il fallback resta una protezione utile.
- La protezione elimina questa specifica causa di mancata finalizzazione; non garantisce assenza assoluta di duplicati se il retry fallisce o la fence viene persa.
- Il test esegue un vero `DROP COLUMN`: deve usare un database/schema sacrificabile e isolato. Ricreare la colonna nel `finally` **non ripristina valori precedenti né il COMMENT**, e non protegge test concorrenti. Dal diff non è dimostrato questo isolamento.

**(2) Rollback e assenza di CHECK — ACCEPT-WITH-NOTES**

Revertire soltanto il worker e lasciare una colonna nullable, senza default, è una strategia compatibile con il vecchio UPDATE mostrato. L’assenza di CHECK è ragionevole per evitare che una nuova etichetta interrompa bookkeeping successivo a un invio irreversibile. La validazione della provenienza può restare nell’applicazione.

Tre precisazioni:

- `-- === ROLLBACK ===` è un commento SQL, non una barriera di esecuzione. L’approvazione presuppone che il migration runner separi questa sezione: eseguire l’intero file aggiungerebbe e poi eliminerebbe la colonna. Il runner non è incluso nel materiale.
- `IF NOT EXISTS` **non verifica** che una colonna preesistente abbia tipo, nullabilità e vincoli corretti.
- La definizione documentata di NULL è troppo restrittiva: include anche righe storiche, completamenti durante il fallback e invii durante un rollback del writer. Va descritto come **“route non registrata”**, non come prova di “nessun completamento”. Questo conta per interpretare il KPI.

L’ADD COLUMN senza riscrittura richiede comunque un lock; i timeout ne limitano l’attesa.

**(3) PII — ACCEPT-WITH-NOTES**

Nel diff la catena visibile è:

`None → leg.served_by → persist_served_by → parametro $6`

Il valore torna a `None` quando il completamento viene scartato. Non vedo assegnazioni da testo del messaggio, telefono o altri campi identificativi; il binding è parametrizzato.

**Non posso però confermare dal diff il vocabolario chiuso del produttore:** la definizione di `CodexLegResult` e le assegnazioni in `wa_codex_leg.py` non sono incluse. Il worker copia il valore senza validarlo, anche nel log. La conclusione sostenibile è: **nessun nuovo percorso PII visibile; garanzia end-to-end subordinata al produttore descritto nel contesto**. Una futura assegnazione arbitraria a `leg.served_by` arriverebbe direttamente alla colonna.
Il mandato era una review statica del diff fornito: non ho modificato codice né eseguito strumenti. Non esiste quindi una ricevuta di verifica prodotta da questa revisione; i test restano non verificati. I tre verdetti restano **ACCEPT-WITH-NOTES**.
Il mandato era una review statica del diff fornito: non ho modificato codice né eseguito strumenti. Non esiste quindi una ricevuta di verifica prodotta da questa revisione; i test restano non verificati. I tre verdetti restano **ACCEPT-WITH-NOTES**.
