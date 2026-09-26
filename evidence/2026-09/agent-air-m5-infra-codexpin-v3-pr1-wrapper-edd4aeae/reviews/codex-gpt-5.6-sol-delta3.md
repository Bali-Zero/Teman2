Delta re-review round 3, PR #7420 (same wrapper), scope NARROWED to round 2's single
remaining gap only (N1's regression clobbered 3 of 6 protected literals and never
checked the heartbeat). Same dispatch mechanism as rounds 1–2: `codex exec -m
gpt-5.6-sol --sandbox read-only -c model_reasoning_effort=high`, `env -i` (scrubbed
env, only HOME/PATH set), cwd = this worktree. Condensed from the raw session
transcript (hook/tool-call noise stripped) — see the note in
codex-gpt-5.6-sol-delta1.md on why the raw transcript is not committed.

Conferma: il gap N1 e' chiuso.

- Il test ora clobbera tutti e sei i literal protetti: `HOME_DIR`, `RUNTIME_DIR`,
  `VENV_PY`, `TAG`, `ORGAN_ID`, `SIDECAR_DIR`
  (`scripts/tests/test_wa_codex_broker_wrapper.py:398`).
- Il wrapper li reimposta tutti dopo il source dell'env
  (`infra/launchagents/wrappers/wa-codex-broker-wrapper.sh:220`).
- L'heartbeat usa effettivamente `SIDECAR_DIR/$ORGAN_ID.json`, e il test richiede il
  file canonico con `starting`/`exec daemon`. Rimuovere anche una sola re-assert tra
  `HOME_DIR`, `ORGAN_ID` e `SIDECAR_DIR` rende assente quel file canonico, quindi la
  mutazione di round 2 non puo' piu' restare verde.
- Un controllo statico (contratto sui due file) e' passato nel sandbox read-only. Il
  pytest mirato non era eseguibile nella seat (pytest non poteva creare una directory
  temporanea nel sandbox), quindi il 26/26 dichiarato dal builder non e' stato
  ri-verificato da questo seat come esecuzione indipendente — solo per contratto
  statico. Nessun finding residuo nell'unico perimetro ammesso (N1's six-name +
  heartbeat regression).

VERDICT: ACCEPT
