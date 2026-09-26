Delta re-review round 2, PR #7420 (same wrapper, after fixing round 1's C2 fixture,
C3 fixture, and N1/N4 regressions), same dispatch mechanism as round 1 and the
gate's own council. Condensed from the raw session transcript (hook/tool-call noise
stripped) — see the note in codex-gpt-5.6-sol-delta1.md on why the raw transcript is
not committed.

Resta un finding bloccante: la regressione N1 copre solo tre dei sei nomi protetti.

Nel test dell'epoca (`test_wa_codex_broker_wrapper.py:388`), l'env alterava soltanto
`RUNTIME_DIR`, `VENV_PY` e `TAG`. Non alterava `HOME_DIR`, `ORGAN_ID` o `SIDECAR_DIR`,
né il test verificava l'heartbeat. Rimuovendo solo quelle tre re-assertion heartbeat
dal blocco N1 del wrapper: il probe restava verde (`rc=0`). Quindi la mutazione
dell'intero blocco era discriminante, ma una regressione su metà del "six-name
collision" sopravviveva.

Correzione richiesta: impostare valori ostili anche per `HOME_DIR`, `ORGAN_ID` e
`SIDECAR_DIR`, quindi verificare che l'heartbeat `starting/exec daemon` venga scritto
nel percorso e col nome corretti, e non nella destinazione ostile.

Le altre correzioni sono confermate direttamente:

- C2: `-f/-x` rifiuta la directory con `78`; il mutant `-x`-only la applica con `rc=0`.
- C3: senza guardia compaiono realmente `legacy` e `cd: /var/root: Permission denied`.
- N4: senza `-r` ricompare la diagnosi errata "must carry exactly one line".
- `sh -n`, `bash -n` e `actionlint` passano. La suite pytest completa non era
  rieseguibile nella seat read-only perché pytest non disponeva di alcuna directory
  temporanea scrivibile.

VERDICT: REWORK

## Disposition (this rework)

Fixed per the instruction above: `test_guilt_env_cannot_clobber_post_source_literals`
now sets hostile values for all 6 protected names (HOME_DIR/RUNTIME_DIR/VENV_PY/TAG/
ORGAN_ID/SIDECAR_DIR) and asserts the heartbeat JSON lands at the wrapper's own
`HOME_DIR`/`ORGAN_ID` path with `status=starting`/`note=exec daemon`. Mutation-verified:
removing the HOME_DIR/ORGAN_ID/SIDECAR_DIR re-asserts from the wrapper's N1 block now
turns this test red (see receipts/mutant-table.md).

A round-3 re-review confirming this exact fix was NOT obtained within the
coordinator's time-box (the process had already exited with the verdict above by the
time a status check was run); this file and council-journal.jsonl record the seat's
last ACTUAL verdict (REWORK) rather than an unconfirmed accept, per the coordinator's
instruction to report honestly rather than mark the council line ok:true without a
seat actually granting it.
