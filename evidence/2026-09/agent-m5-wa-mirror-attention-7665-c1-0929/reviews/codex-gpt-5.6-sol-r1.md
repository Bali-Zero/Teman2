[M5] **REWORK**

1. **ALTA — Hook importati o rinominati: false-GREEN.** In `conftest.py`, `from helpers import stop as pytest_pyfunc_call` elude `hook_problems`, che ignora gli import. Se `stop` restituisce `True`, i corpi non vengono eseguiti ma JUnit registra successi. Anche `@pytest.hookimpl(specname="pytest_pyfunc_call")` su `def pytest_stop(...)` elude il controllo nominale.

2. **ALTA — `pytest_collection_modifyitems` può sostituire i corpi.** Il commento considera soltanto la rimozione degli item. Un hook consentito può invece assegnare `item.obj = lambda: None`, conservando identità e report. Tutte le definizioni risultano presenti senza essere eseguite.

3. **ALTA — Binding incompleti: false-GREEN.** Dopo `def test_guard(): assert False`, un import alias dentro `if True` può sostituire `test_guard`: il ramo `FLOW` cerca soltanto definizioni. Anche `test_guard, = (noop,)` passa perché il target è una `Tuple`. JUnit può quindi soddisfare l’identità originale eseguendo il sostituto.

4. **ALTA — Basi riconosciute per spelling.** `from unittest import TestCase as C` seguito da `class Checks(C)` non viene riconosciuto. Metodi definiti dentro un `if True` nella classe sfuggono anche a `stray`: deselezionarli lascia GREEN. Inoltre, importare una base con alias `object` aggira `bad_base`, lasciando invisibili i test ereditati.

5. **ALTA — Euristica fixture: entrambi gli errori.** `from pytest import fixture as fx` con `@fx` produce false-RED: una fixture viene richiesta nel report. Viceversa, un normale decoratore chiamato `fixture` esclude una vera definizione da `expected`; deselezionarla può lasciare GREEN.

6. **MEDIA — Hook cercati senza distinguere gli scope: false-RED.** `hook_problems` percorre anche corpi di funzioni e classi. Una variabile locale innocua `pytest_plugins = []` dentro un test viene rifiutata pur non registrando alcun plugin.
