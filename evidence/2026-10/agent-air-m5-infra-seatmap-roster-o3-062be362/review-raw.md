# Cross-family review of the roster-O3 diff (raw answers, builder = Claude)

## Kimi K3 and kimi-for-coding: NOT AVAILABLE (provider 403: 5-hour usage limit reached), twice

## tp1 qwen3.7-plus (effort low) - raw

BLOCK

1. **Registry and auth dirs contradict on Pro/Mini**  
   **File:** `FLEET_TOPOLOGY.json`, `scripts/lib/codex_seat.sh`  
   **Evidence:** The `codex_seat.sh` header explicitly documents that `~/.codex-acct2` resolves to **O2** on Pro/Mini (`Pro / Mini ~/.codex = O1, ~/.codex-o2 or ~/.codex-acct2 = O2`). However, the registry in `FLEET_TOPOLOGY.json` completely omits Pro/Mini from O2's `codex_home_by_machine` (it only lists `{"Air-M5": "~/.codex-o2"}`), and instead binds `~/.codex-acct2` exclusively to **O3** on Air-M5. A host running Pro/Mini will have an auth dir (`~/.codex-acct2`) that the registry contradicts (it claims it's O3 on Air-M5, but the shell script treats it as O2 on Pro/Mini, and the registry has no Pro/Mini mapping for O2 at all).

2. **Schema `if/else` fails to block O3 on non-Air-M5 hosts**  
   **File:** `infra/conductor/<REDACTED>`  
   **Evidence:** The schema uses an `if/else` construct to restrict non-Air-M5 hosts to `openaiTwoSeats`:

   ```json
   "if": { "properties": { "machine": { "const": "Air-M5" } } },
   "else": { "properties": { "providers": { "properties": { "openai": { "$ref": "#/$defs/openaiTwoSeats" } } } } }
   ```

   Because there is no `then` block, when `machine` is "Air-M5", the `else` constraint is skipped, and the root schema's `oneOf` allows _either_ `openaiTwoSeats` or `openaiThreeSeats`. More critically, the `else` block lacks `additionalProperties: false` or `required` constraints, meaning a malformed document missing the `providers` key entirely on Pro/Mini would silently pass the `else` validation. The schema relies entirely on the root schema's implicit constraints, which are not visible or guaranteed to be strict here.

3. **`auto_rotation_order` is verified circularly, not against the shell script**  
   **File:** `scripts/tests/<REDACTED>`  
   **Evidence:** The test `test_declared_auto_rotation_order_matches_codex_seat_enumeration` does not verify the JSON against the _actual_ runtime order of `codex_seat.sh`. Instead, it feeds the test's own hardcoded dictionary (`pro_dirs = {".codex": "O1", ".codex-acct2": "O2"}`) into the shell script and asserts the output matches the JSON. For Air-M5, it uses `_bound_homes` (the registry) to map the shell script's output. Thus, the test only verifies that the shell script's hardcoded directory list matches the registry/JSON mapping _as interpreted by the test itself_. It does not independently verify that `codex_seat.sh` actually enumerates seats in the declared `auto_rotation_order` at runtime; it just confirms the test's own hardcoded assumptions align with the JSON.

4. **Test `test_schema_rejects_the_three_seat_shape_without_the_marker` cannot go red**  
   **File:** `scripts/tests/<REDACTED>`  
   **Evidence:** The test attempts to verify that removing `quota_independence` from the O3 seat causes a schema validation error:
   ```python
   def test_schema_rejects_the_three_seat_shape_without_the_marker() -> None:
       def drop(openai: dict[str, Any]) -> None:
           _make_three_seat(openai)
           del openai["seats"][2]["quota_independence"]
       assert _openai_errors("Pro", drop)
   ```
   However, `_make_three_seat` sets `canonical_roster` to `["O1", "O2", "O3"]`. When this mutated manifest is validated against the "Pro" shape, the schema's `else` block forces `openai` to match `openaiTwoSeats`. `openaiTwoSeats` strictly requires `canonical_roster` to be `const: ["O1", "O2"]`. Therefore, the schema will reject the document due to the `canonical_roster` mismatch _long before_ it ever evaluates the missing `quota_independence` field on the third seat. The test will always pass (report errors) regardless of whether the `quota_independence` check is actually working, making it a tautology that cannot go red.

## codex O2 gpt-5.6 read-only - raw verdict (tail of the run, reasoning trace omitted)

## Disposition: see the PR body

BLOCK

1. **L’esclusione dichiarata di O3 non funziona.** [codex_seat.sh](/Users/balizero/nuzantara/.worktrees/infra-seatmap-roster-o3/scripts/lib/codex_seat.sh:47) enumera directory con `auth.json`, senza leggere manifest o `auto_rotation_order`. Probe: Air-M5 con ordine `["O1","O2"]` resta valido per lo schema; lo shell continuerebbe a enumerare `.codex-acct2`. Il commento che promette esclusione cambiando un campo è falso.

2. **Pro/Mini possono enumerare tre directory contro un roster di due posti.** [codex_seat.sh](/Users/balizero/nuzantara/.worktrees/infra-seatmap-roster-o3/scripts/lib/codex_seat.sh:51) include entrambi gli alias e deduplica solo percorsi identici. Non impone «al massimo uno dei due». Probe shell in memoria, simulando tre auth presenti: restituisce tutte e tre le directory anche con HOME Pro. Ciò non prova l’identità O3, ma consente una directory autenticata O3 su quei host senza alcun filtro.

3. **La parità dei binding protegge soltanto Air-M5.** [test_conductor_host_seat_maps.py](/Users/balizero/nuzantara/.worktrees/infra-seatmap-roster-o3/scripts/tests/test_conductor_host_seat_maps.py:214) confronta il usage map con il registry solo per Air-M5. Pro/Mini ricevono controlli di assenza O3 nel registry e nel conductor, non nel usage map. **Mutazione eseguita in memoria:** aggiunto `by_machine.Pro.codex_homes["~/.codex-acct2"]="O3"`; il test passa. Inoltre il registry non contiene binding strutturati O1/O2 per Pro/Mini: la fixture Pro li inventa a riga 259.

4. **O3 non è “LAST” nell’ordine effettivo dei tentativi.** [claude-cascade.sh](/Users/balizero/nuzantara/.worktrees/infra-seatmap-roster-o3/infra/launchagents/wrappers/claude-cascade.sh:903) applica un offset rotante: con offset 2, l’ordine è **O3→O1→O2**. Il test a [riga 250](/Users/balizero/nuzantara/.worktrees/infra-seatmap-roster-o3/scripts/tests/test_conductor_host_seat_maps.py:250) invoca davvero lo shell, quindi non confronta soltanto il campo con sé stesso; verifica però l’enumerazione base, non la rotazione del consumer. Per Mini controlla soltanto una costante.

5. **Un caso negativo passa per il motivo sbagliato; l’esclusione legittima fallisce il test.** [test_conductor_host_seat_maps.py:182](/Users/balizero/nuzantara/.worktrees/infra-seatmap-roster-o3/scripts/tests/test_conductor_host_seat_maps.py:182): l’asserzione Pro senza marker resta verde anche rimuovendo il vincolo host, perché il marker mancante basta a invalidare il documento. Probe confermato. Separatamente, a riga 257 il test impone sempre `["O1","O2","O3"]`: l’esclusione O3 ammessa dallo schema lo rende rosso. Nessun intero test mostrato è letteralmente incapace di fallire; questa specifica asserzione negativa non dimostra il vincolo host.

6. **`oneOf` non presenta overlap; il vincolo host dello schema funziona.** [host_seat_map.schema.json](/Users/balizero/nuzantara/.worktrees/infra-seatmap-roster-o3/infra/conductor/host_seat_map.schema.json:146): roster costanti e cardinalità 2/3 rendono i rami disgiunti. Probe: documenti correnti validi; shape O3 su Pro respinta. Tuttavia Air-M5 accetta anche la shape O1/O2, perché manca un `then` che richieda tre posti. I vecchi documenti v1 senza `auto_rotation_order` vengono inoltre respinti senza cambio di `schema_version`.

Verifiche eseguite in memoria; nessun file modificato e nessun auth reale letto.
hook: Stop
hook: Stop Completed
tokens used
34.602
BLOCK

1. **L’esclusione dichiarata di O3 non funziona.** [codex_seat.sh](/Users/balizero/nuzantara/.worktrees/infra-seatmap-roster-o3/scripts/lib/codex_seat.sh:47) enumera directory con `auth.json`, senza leggere manifest o `auto_rotation_order`. Probe: Air-M5 con ordine `["O1","O2"]` resta valido per lo schema; lo shell continuerebbe a enumerare `.codex-acct2`. Il commento che promette esclusione cambiando un campo è falso.

2. **Pro/Mini possono enumerare tre directory contro un roster di due posti.** [codex_seat.sh](/Users/balizero/nuzantara/.worktrees/infra-seatmap-roster-o3/scripts/lib/codex_seat.sh:51) include entrambi gli alias e deduplica solo percorsi identici. Non impone «al massimo uno dei due». Probe shell in memoria, simulando tre auth presenti: restituisce tutte e tre le directory anche con HOME Pro. Ciò non prova l’identità O3, ma consente una directory autenticata O3 su quei host senza alcun filtro.

3. **La parità dei binding protegge soltanto Air-M5.** [test_conductor_host_seat_maps.py](/Users/balizero/nuzantara/.worktrees/infra-seatmap-roster-o3/scripts/tests/test_conductor_host_seat_maps.py:214) confronta il usage map con il registry solo per Air-M5. Pro/Mini ricevono controlli di assenza O3 nel registry e nel conductor, non nel usage map. **Mutazione eseguita in memoria:** aggiunto `by_machine.Pro.codex_homes["~/.codex-acct2"]="O3"`; il test passa. Inoltre il registry non contiene binding strutturati O1/O2 per Pro/Mini: la fixture Pro li inventa a riga 259.

4. **O3 non è “LAST” nell’ordine effettivo dei tentativi.** [claude-cascade.sh](/Users/balizero/nuzantara/.worktrees/infra-seatmap-roster-o3/infra/launchagents/wrappers/claude-cascade.sh:903) applica un offset rotante: con offset 2, l’ordine è **O3→O1→O2**. Il test a [riga 250](/Users/balizero/nuzantara/.worktrees/infra-seatmap-roster-o3/scripts/tests/test_conductor_host_seat_maps.py:250) invoca davvero lo shell, quindi non confronta soltanto il campo con sé stesso; verifica però l’enumerazione base, non la rotazione del consumer. Per Mini controlla soltanto una costante.

5. **Un caso negativo passa per il motivo sbagliato; l’esclusione legittima fallisce il test.** [test_conductor_host_seat_maps.py:182](/Users/balizero/nuzantara/.worktrees/infra-seatmap-roster-o3/scripts/tests/test_conductor_host_seat_maps.py:182): l’asserzione Pro senza marker resta verde anche rimuovendo il vincolo host, perché il marker mancante basta a invalidare il documento. Probe confermato. Separatamente, a riga 257 il test impone sempre `["O1","O2","O3"]`: l’esclusione O3 ammessa dallo schema lo rende rosso. Nessun intero test mostrato è letteralmente incapace di fallire; questa specifica asserzione negativa non dimostra il vincolo host.

6. **`oneOf` non presenta overlap; il vincolo host dello schema funziona.** [host_seat_map.schema.json](/Users/balizero/nuzantara/.worktrees/infra-seatmap-roster-o3/infra/conductor/host_seat_map.schema.json:146): roster costanti e cardinalità 2/3 rendono i rami disgiunti. Probe: documenti correnti validi; shape O3 su Pro respinta. Tuttavia Air-M5 accetta anche la shape O1/O2, perché manca un `then` che richieda tre posti. I vecchi documenti v1 senza `auto_rotation_order` vengono inoltre respinti senza cambio di `schema_version`.

Verifiche eseguite in memoria; nessun file modificato e nessun auth reale letto.
