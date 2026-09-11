# cicatrix-superscar.md — le 10 famiglie (NUCLEO)

> **NUCLEO ≤2.560B**, corpo in `cicatrix-scars.md`/`-archive.md` richiamato per pertinenza
> dall'hook SessionStart (non più iniettato in blocco). Dettaglio → grep il W-number, o `scar
> query "<tema>"`/`--list`/`--family N`. Tre nomi disambiguano collisioni: `W81-armamento-sospeso`, `W81b-dlq-blind-heal-loop`, `W84-tcc-dead`.

**Dominanza:** #1 HOME-fork, #2 Esiste≠Armato, #5 Sibling-race, #4 Secret-clear = 65-75%.

---

## #1 — HOME-fork drift · $HOME diverge dal repo, il fix non arriva · lint `cmp -s` live vs git, contro origin/main mai locale · → `scripts/lint_home_fork.py`

## #2 — Esiste≠Armato · cron "verdi" mascherano worker morti, output vuoto · monitora esito/heartbeat non PID/exit-code, green≠working · → `scripts/pending_arms_report.py`

## #3 — Guard-over-match / UNDER-match · guardia giudica substring non entità, OVER/UNDER simmetrici · mai guardia senza guilt+innocence, su entità mai substring · → `infra/guard-conformance/`

## #4 — Secret in the clear · segreti prod esposti nel filesystem, `.bak` eredita l'esposizione · chmod 0600 live+.bak, mai cat secret, ruota se esposto · → `scripts/secrets_permissions_audit.py`

## #5 — Sibling-race / shared-worktree · agenti/cron paralleli sullo stesso checkout, collisioni stash · ogni agent in worktree dedicato, reap solo a 2-AND · → `scripts/agent_start.py`

## #6 — Anti-hallucination blindness · LLM immagina file/righe plausibili, a valle le crede vere · mai costruire su path citato senza find/ls/cat in QUESTO turno

## #7 — Daemon KeepAlive misconfig · KeepAlive=true su one-shot, ogni exit letto come morte · loop bloccante reale o StartInterval senza KeepAlive · → `scripts/lint_plist_keepalive.py`

## #8 — Network flap / proxy fragility · componenti long-running crashano sui flap di rete · socket keep-alive persistenti, retry con backoff, cattura InterfaceError

## #9 — State-schema mutation drift · step cambia formato payload, lettori a valle rompono · deploy unificato sui contratti, già-su-main è CONTENUTO mai SHA-ancestor · → `scripts/branch_graveyard_cleanup.sh::content_on_main()`

## #10 — Active-active split-brain · singleton su host diversi, ognuno credendosi unico · SSOT nel DB, graceful-exit se node≠hostname

---

> **Manutenzione:** scar nuova → corpo in `cicatrix-scars.md`; MEMBRI/Orfane → `scar --list`/`--family N`.
