# Final on-disk gate verdict — fable-max session board

Fresh Opus 5 headless session · 2026-09-11 · HEAD `adbd2a86e7` · verdict **PASS-WITH-CONDITIONS** · receipt https://github.com/Bali-Zero/Teman2/pull/6104#issuecomment-5621804838

The verdict below is verbatim, in the language the gate wrote it; only local scratch paths are replaced by `[scratch]`.

---

VERDICT: PASS-WITH-CONDITIONS

**Ragioni**

1. **Checker:** `check_adversarial_review.py --files …/*.md` ha stampato come ultima riga `PASS — 6 research file(s) carry a valid adversarial review`. HEAD `adbd2a86e7`; PR #6104 risulta `OPEN … BLOCKED auto=false`.
2. **B1 (i checkpoint arrivano davvero):** applicato in `README.md:69-73`, `S1:95-99` (poi `S1:72` e `S1:111` usano l'ack come trigger della wave 2), `S2:83-87`, `S3:87-91` + `S3:15`, `S4:79-83` + `S4:17`, `S5:86-90`. `fleet_mail.sh:315` stampa davvero `($FILENAME)`, quindi l'istruzione sull'envelope id è vera. Segue i passi 1-4 di `army-map.md:84-89`, con una mancanza che diventa la condizione C3.
3. **B2 (S2 solo detect-and-report):** applicato in `S2:40` (niente `--fix` nel plist), `S2:41`, `S2:59` (un test verifica che il mode non cambi), `S2:60`, `S2:64`, `S2:88`, `S2:95`, `README.md:136`. Resta il consumer Mini: condizione C1.
4. **B3 (S5 ha un consumer live):** applicato in `S5:20,22,40,67,100,103-104` e `README.md:43,80`. L'ho verificato dal vivo:
   - la copia HOME è uguale a origin/main (`home-equals-origin-main`);
   - la declared pair ha `[]`;
   - la proiezione `launchctl print` stampa `runs = 30` / `last exit code = 0`;
   - `ttl_days is not null` dà 0.
     Il passo 3 si può eseguire e si osserva che resta inerte.
5. **F2 (approvazione dei due imperator):** applicato in `README.md:11,129`, `S1:13`, `S2:13`, `S3:13`, `S4:15`, `S5:13`. La wave 1 è dichiarata come _non_ approvata da entrambi, ed è una deviazione registrata. Non pretende di rispettare `army-map.md:98-99`.
6. **F17 (rollback che protegge entrambe le tabelle):** applicato in `README.md:80`, `S5:94`, `S5:105`. I tre capture hook esistono su disco.
7. **Dottrina:**
   - Builder Contract regola 1: freeze in `README.md:64-67` e in ogni §3; serializzazione del ledger in `README.md:56`.
   - Regola 5: tre comandi separati, arm immediato, `--auto` senza flag (confermato da `merge-queue-discipline.md:274-278` e `queue_shepherd.py:819-821`); seat esterni prepare-only in `S1:85`, `S2:74`.
   - PARABELLUM: la tabella colori corrisponde a `army-map.md:42-48`; nessun fallback di colore (`README.md:18`); il gate firma soltanto (`S1:84`).
   - Nessuna contraddizione oltre a C2-C4.
8. **Ground rieseguita, torna tutto:**
   - dead ticks 1897/1898;
   - `.secrets` 7/0;
   - propriocezione non schedulata 0/0;
   - chiavi di `last.json` identiche a `S3:30`;
   - digest 0;
   - #6101 `MERGED 2026-09-10T14:24:00Z`, #6054 `OPEN`;
   - fixture S2 `"count": 0`;
   - `INDEX.md:71` = 15 tabelle, `:71` = 11 root di default.
9. **Eseguibilità.** Path controllati con `ls`/`-e`:

   | Tipo                         | Path                                                                                                                                                                                                                                                                                                                                                                                                                           |
   | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
   | 50 nel repo, tutti presenti  | tra cui `army-map.md`, `RULINGS.md`, `battle-window-spec.md`, `merge-queue-discipline.md`, `evidence_paths.py`, `harness_fable_gate.py`, `test_proprioception_receptor_ranking.sh`, `test_tg_notify_identity_ladder.py`, `escalations-digest.weekly.plist`, `mandate_budget.py` (in codex-hooks), `lane_check.py` (in claude-hooks), `codex-spalla.sh`, `CODEX_SPALLA.md`, `declared-pairs.json`, `content_on_main()` a `:205` |
   | 15 HOME/live, tutti presenti | log shepherd, puller, `tg_spool/state.json`, worker HOME, capture hooks, `~/.claude/backups` (0755, come dichiarato), venv con pytest 9.0.3                                                                                                                                                                                                                                                                                    |
   | Assenti                      | tutti marcati "to be created" (`S2:40`, `S3:38`, `S5:22/39`) oppure citati come inesistenti (`scripts/mandate_budget.py`, `scripts/lane_check.py`)                                                                                                                                                                                                                                                                             |

   Comandi controllati (18): `--help` di shepherd, proprioception, secrets audit, fable-gate, agent_start e pending_arms; `KNOWN_LANES` contiene `ops`, `infra` e `db`; il formato `WORKTREE_READY` combacia con l'awk; sintassi di `fleet_mail local broadcast --key --ttl` e `--list`; `evidence_paths.py --ref`; proiezione `launchctl print`; `grep -c` sui ground; `find -perm +077`; confronto sha256 di S5; conteggio sqlite; probe jq del ledger (stampa `[6081,6080,5072]`, cioè oggi un ledger-PR aspetterebbe, come previsto); `gh pr view`.

10. **PII e segreti:** un Grep sui dieci file per AIza, +62, passport, KTP, NPWP, email, `sk-`, `ghp_`, `BEGIN`, forme di token bot e telefoni `08…` → `No matches found`.
11. **Logica delle wave:** regge. I criteri (a)-(d) di `README.md:49` coincidono con `S3:15` e `S4:17`; `S1:72` e `S1:111` producono l'ack che fa da trigger. La divisione S5/S5b è coerente tra `README.md:43/50/80` e `S5:20-24/91-95/103-105`.

**Condizioni**

- **C1 (S2, finestra già in corsa) — consumer non nominato.** Su Mini `com.nuzantara.secrets-perms-sweep` è caricato (ultimo run `2026-09-10T16:00:21Z ok`). Esegue `~/nuzantara/scripts/secrets_permissions_audit.py --fix` con le root di default (`wrappers/mini-secrets-perms-sweep.sh`) e `git-pull-main.5min` tiene quel checkout su main. Quindi:
  - `S2:41` ("neither the detector … changes a credential's mode") è falso riferito al detector;
  - `S2:32` ("No schedule") vale solo per Pro;
  - rendere `.env*` report-only toglie un chmod automatico su Mini, cioè cambia il comportamento di un consumer.

  Serve: nominare lo sweep nel §3; un test che provi che il roots PR non allarga ciò che `--fix` tocca (niente chmod sotto una root `.secrets` né su `.env*`); il `Bites:` del roots PR deve nominare il prossimo run Mini (rc=0, FIXED invariato).
  Owner: staff room → Dux S2. Scadenza: prima che il roots PR di S2 venga armato, al più tardi alla deadline S2 delle 19:59Z.

- **C2 — `Bites:` su ogni PR.** `S1:105`, `S2:92`, `S3:96`, `S4:88`, `S5:100` dicono "every code PR", mentre la regola 2 dice _every PR_. Anche i ledger-only PR e il PR su INDEX.md devono avere `Bites:`.
  Owner: staff room (testo più messaggio a S1/S2). Scadenza: prima dell'apertura della wave 2.
- **C3 — ack e ORANGE.**
  - `army-map.md:87` vuole il `received` registrato contro lo stesso hash. `README.md:72` e i passi 3 dei §6 non chiedono di citare l'envelope id, e gli ack osservati in mailbox citano l'ora, non l'id.
  - Su ORANGE il Dux Sol non ha `SendMessage`: va aggiunta la route per peer Codex di `army-map.md:85-86`.

  Owner: staff room. Scadenza: prima della wave 2 o di qualsiasi dichiarazione ORANGE.

- **C4 — colore.** `README.md:15` ("BLUE unless Zero says ORANGE") contro `army-map.md:38` ("Zero picks the colour with Fable and Astra"). Va estesa la deviazione di `README.md:11` alla scelta del colore.
  Owner: staff room. Scadenza: prima della wave 2.
- **C5 — S5 prima dell'apertura.**
  - Il dry-run di `S5:66` non passa alcun ruling file, mentre `S5:51` vuole i predicati del ruling: vanno nominati path e sha256 del ruling proposto di default (`README.md:131`) e dove il worker lo legge (`S5:22`).
  - `$BK` in `S5:93` non è mai assegnato.
  - `README.md:50` non dà un trigger d'apertura per la wave 3.

  Owner: staff room. Scadenza: prima dell'apertura di S5.

- **C6 — stile residuo.**
  - `$TITLE` e `$BODY` sono definiti solo in `S1:106`: mancano in `S2:93`, `S3:97`, `S4:89`, `S5:101`.
  - Il path di `agent_start.py:2166-2172` è sfasato: la print di `WORKTREE_READY` sta a `:2175`.

  Owner: staff room, insieme a C2.

- **C7 — arm di #6104.** È aperta con `auto=false`: la regola 5 vuole l'arm alla PR-open. Il release owner la arma dopo aver pubblicato questo verdetto; il gate non arma.

**Da sapere**

- `README.md:9` dice che l'imperator "never fans out", ma `README.md:22-23` descrive 12 lettori, 27 verdetti e 6 lettori tardivi senza dire quale sessione li abbia lanciati. Se è stata la finestra imperator, è stato violato `army-map.md:210`: è storia, non tocca le finestre.
- Resta sul disco lo scratch `[scratch]` (contiene solo un `probe.json` vuoto): il permesso per il mio `rm -r` è stato negato.

Serve che lo staff room invii subito C1 alla finestra S2, prima che il suo roots PR venga armato.
gate_exit=0
