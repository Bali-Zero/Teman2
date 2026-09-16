codex
SHIP

- **MINOR — [wa_package.py:146](/Users/nuzantara/nuzantara/.worktrees/backend-rag-b2-5-greeting-authority/apps/backend-rag/backend/app/routers/wa_package.py:146)**  
  **Evidenza:** `{"domain": plan.domain.value}` passa ancora `"greeting"` al prefetch, mentre il builder riclassifica GENERAL.  
  **Input:** `Halo, apa kabar semuanya di kantor hari ini?`  
  **Effetto riprodotto:** il consumatore reale, con retriever simulato, esegue una ricerca curated-QA e scarta il risultato business; passando `"general"` evita la ricerca. Introduce costo e latenza inutili per questi messaggi.  
  **Correzione:** allineare il dominio del prefetch al fallback del builder; verificare nel test anche il dominio trasmesso e l’assenza della ricerca per GENERAL.

Verifica: passano direttamente in memoria 75 casi greeting, quattro test di autorità e C1 sui 62 testi caricati da disco. La suite pytest completa resta non verificata: le fixture richiedono scritture temporanee vietate dal sandbox.
hook: Stop
