VERDICT: FIX-FIRST

1. **MAJOR** — `apps/backend-rag/backend/db/migrations_v2/315_wa_outbox_fall_off_reason_support_judge_absent.sql:83`  
   Scenario: dopo la prima riga persistita con `generation_fall_off_reason='support_judge_absent'`, il rollback tenta di aggiungere subito il CHECK ristretto; PostgreSQL lo rifiuta per la riga incompatibile, lasciando il rollback incompleto.  
   Fix minimo: prima del CHECK ristretto, convertire atomicamente quelle righe in un valore precedente appropriato, per esempio `unknown`.

2. **MAJOR** — `apps/backend-rag/backend/services/rag/agentic/_support_signal.py:454`  
   Scenario: `has_visible_character()` considera visibile qualsiasi categoria diversa da `Z`/`C`. Un turno finale composto solo da U+FE0F (variation selector, categoria `Mn`) è invisibile ma supera il controllo; il leg offre quindi un package senza domanda, violando V4. Lo stesso errore consente al parser daemon di accettarlo.  
   Fix minimo: escludere almeno i combining mark non autonomamente visibili (`Mn`/`Me`), mantenendo validi i caratteri base, e aggiungere casi U+FE0F/U+0301.

3. **MINOR — UNSURE** — `apps/backend-rag/backend/tests/unit/services/integrations/test_wa_codex_leg_support_negative.py:282`  
   Scenario: `test_invisible_query_package_never_offers` asserisce soltanto stub, reason e carrier (`:294-301`), non che l’offerta sia rimasta a zero. Una regressione che offre il job e poi restituisce lo stesso stub potrebbe passare. Non è verificabile dalle sole asserzioni autorizzate se lo stub dell’offer fallisca automaticamente alla chiamata.  
   Fix minimo: aggiungere un’asserzione esplicita sul contatore/spia dell’offer pari a zero.
