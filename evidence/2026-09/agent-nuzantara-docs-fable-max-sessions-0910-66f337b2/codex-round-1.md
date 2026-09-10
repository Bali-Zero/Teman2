# Codex adversarial review — round 1 (seat codex, gpt-5.6-sol, 2026-09-10, read-only sandbox, on v1 dddf6d71f4)

[Pro] Verdetto complessivo: **REWORK**. Il board non è eseguibile in sicurezza come programma autonomo.

1. **Ruolo e autorità sbagliati in tutti i mandati.** Il README assegna l’esecuzione a cinque sessioni Fable e ogni mandato ordina a Fable di implementare, fare fan-out e rilasciare end-to-end: [README.md:14](README.md:14), [README.md:40](README.md:40), [S1:10](S1-arm-the-armer.md:10), [S2:10](S2-custody.md:10), [S3:10](S3-arm-the-auditors.md:10), [S4:10](S4-reaper-and-signal.md:10), [S5:10](S5-brain-that-can-forget.md:10). La dottrina corrente rende Fable un Imperator che non implementa né fa fan-out; in BLUE il Dux/release owner è Opus: [army-map.md:19](/Users/nuzantara/nuzantara/.worktrees/docs-fable-max-sessions-0910/docs/architecture/dual-consul/army-map.md:19), [army-map.md:42](/Users/nuzantara/nuzantara/.worktrees/docs-fable-max-sessions-0910/docs/architecture/dual-consul/army-map.md:42), [RULINGS.md:93](/Users/nuzantara/nuzantara/.worktrees/docs-fable-max-sessions-0910/docs/rules/RULINGS.md:93).

2. **Nessun mandato è una battle-window valida.** Mancano colore, Dux nominato, gear, base SHA, worktree reale, sibling contract, budget in ore/token, deadline, limiti di tentativi e rollback. Sono quindi falsamente dichiarati “ready to paste”: [README.md:14](README.md:14). Il contratto obbligatorio è esplicito in [battle-window-spec.md:8](/Users/nuzantara/nuzantara/.worktrees/docs-fable-max-sessions-0910/.claude/skills/modus/battle-window-spec.md:8) e [battle-window-spec.md:41](/Users/nuzantara/nuzantara/.worktrees/docs-fable-max-sessions-0910/.claude/skills/modus/battle-window-spec.md:41).

3. **Le istruzioni sui worktree lasciano la sessione nel checkout principale.** `agent_start.py` stampa soltanto `WORKTREE_READY`; non può cambiare la directory del processo chiamante: [agent_start.py:2166](/Users/nuzantara/nuzantara/.worktrees/docs-fable-max-sessions-0910/scripts/agent_start.py:2166). Nessun mandato cattura il path e fa `cd`. S3 e S4 mostrano addirittura soltanto flag non eseguibili: [S1:48](S1-arm-the-armer.md:48), [S2:44](S2-custody.md:44), [S3:48](S3-arm-the-auditors.md:48), [S4:47](S4-reaper-and-signal.md:47), [S5:49](S5-brain-that-can-forget.md:49).

4. **S1 è contemporaneamente prerequisito e non prerequisito.** Il README dice che S1 “is not a hard prerequisite for anyone”, ma la riga successiva vieta Wave 2 finché il fix S1 non è live con sei tick puliti: [README.md:41](README.md:41), [README.md:42](README.md:42).

5. **Il parallelismo “disjoint files” è falso.** S1 e S2 devono entrambi appendere operator items a `PENDING-ARMS.md`; lo stesso vale per S3/S4. `merge=union` non protegge su GitHub: una PR parallela diventa DIRTY dopo il merge della sorella e richiede un merge locale, operazione non descritta e incompatibile col divieto assoluto di risolvere: [README.md:41](README.md:41), [README.md:45](README.md:45), [S1:64](S1-arm-the-armer.md:64), [S2:55](S2-custody.md:55). Il comportamento reale è documentato in [modus/SKILL.md:193](/Users/nuzantara/nuzantara/.worktrees/docs-fable-max-sessions-0910/.claude/skills/modus/SKILL.md:193).

6. **S2 può correre contro #6101.** Solo S3 è obbligata ad aspettare #6101, ma S2 crea anch’essa un plist canon nella Wave 1. Il suo mandato dice soltanto di controllare lo stato, senza stop/serializzazione se la PR è aperta: [README.md:42](README.md:42), [S2:24](S2-custody.md:24), [S2:32](S2-custody.md:32), [S2:44](S2-custody.md:44).

7. **S1 non entra in una sessione né in un organo.** Comprende 4–5 PR, riparazione GraphQL, semantica heartbeat, sospensione three-reds, hook pre-push, triage e merge manuale di PR altrui e verifica dei sibling su Mini: [S1:29](S1-arm-the-armer.md:29), [S1:33](S1-arm-the-armer.md:33), [S1:34](S1-arm-the-armer.md:34), [S1:53](S1-arm-the-armer.md:53). Bite 3 prova attività manuale su PR nominate, non che il re-armer sia guarito: [S1:58](S1-arm-the-armer.md:58).

8. **S2 mescola due organi e specifica una persistenza impossibile.** Audit locale e restore drill CI sono missioni indipendenti. Inoltre una GitHub Action effimera non può appendere durevolmente al bus git-tracked e Pro-exclusive senza un trasporto/commit esplicitamente progettato: [S2:31](S2-custody.md:31), [S2:33](S2-custody.md:33), [S2:35](S2-custody.md:35), [escalations.py:4](/Users/nuzantara/nuzantara/.worktrees/docs-fable-max-sessions-0910/scripts/sentinel_lib/escalations.py:4). Bite 5 è soltanto un test e non prova la consegna live: [S2:52](S2-custody.md:52).

9. **S2 può toccare un file off-limits.** Il contratto vieta `.env*`, ma il default audit li include e il risk control ordina di correggere qualsiasi file loosened e il relativo `.bak`: [S2:10](S2-custody.md:10), [S2:18](S2-custody.md:18), [S2:55](S2-custody.md:55). Un finding su `.env*` deve produrre stop/escalation, non `chmod`.

10. **S2 Bite 1 non esegue il fixture dichiarato.** Il comando usa i default roots reali, mentre lo scope richiede una directory scratch a forma di `.secrets`. Senza `--no-default-roots --root <scratch>` il Bite o non vede il fixture o richiede di allentare un file nella directory live: [S2:31](S2-custody.md:31), [S2:48](S2-custody.md:48).

11. **S3 ricrea esattamente il difetto che dice di curare.** Cinque PR più un’operazione live attraversano launchd, cost guard, linter, scar gates, Postgres/INDEX e decommissioning: [S3:28](S3-arm-the-auditors.md:28). Il probe INDEX è “advisory” ma non ha un workflow, schedule o consumer eseguibile; `INDEX.md's readers` non è un consumer meccanico. Bite 5 è quindi un test manuale, non prova che il sensore sia armato: [S3:33](S3-arm-the-auditors.md:33), [S3:59](S3-arm-the-auditors.md:59). Bite 6 prova solo determinismo del generatore, non correttezza del manifest: [S3:60](S3-arm-the-auditors.md:60).

12. **S4 è un programma, non una sessione.** Contiene gateway, sentinel, digest, schema/fingerprint del bus, growth gate, sidecar, reconciler e amministrazione diretta su due macchine: almeno sette concern/PR potenziali: [S4:29](S4-reaper-and-signal.md:29), [S4:31](S4-reaper-and-signal.md:31), [S4:37](S4-reaper-and-signal.md:37), [S4:38](S4-reaper-and-signal.md:38). `HIGH drops below 21` non definisce query, finestra o causalità; la chiusura può inoltre chiudere zero righe e soddisfare vacuamente “drops by the rows closed”: [S4:53](S4-reaper-and-signal.md:53), [S4:55](S4-reaper-and-signal.md:55). Bite 7 chiede “per machine” benché M5 sia esplicitamente esclusa: [S4:44](S4-reaper-and-signal.md:44), [S4:56](S4-reaper-and-signal.md:56).

13. **S5 è sia gated sia avviabile senza ruling.** README e intestazione dicono di non lanciare S5 prima della decisione; il prompt autorizza invece il repo half con ruling vuoto: [README.md:43](README.md:43), [S5:5](S5-brain-that-can-forget.md:5), [S5:15](S5-brain-that-can-forget.md:15).

14. **S5 elimina l’indipendenza proprio sulla parte irreversibile.** Il contratto promette review e final gate, ma il risk control dichiara “no reviewer” e affida la sicurezza allo stesso SQL del generatore: [S5:10](S5-brain-that-can-forget.md:10), [S5:60](S5-brain-that-can-forget.md:60). Backup, purge, VACUUM, writer restart, HOME-copy, settings e 2–3 PR non appartengono a una sola finestra: [S5:31](S5-brain-that-can-forget.md:31), [S5:49](S5-brain-that-can-forget.md:49).

15. **Tre prove S5 non funzionano o non falsificano la promessa.**

- `.backup '<dated path outside…>'` usa un placeholder letterale relativo e quindi non garantisce affatto una destinazione esterna al repo: [S5:37](S5-brain-that-can-forget.md:37).
- Il `DELETE` SQLite “esatto” non stampa il numero di righe; verificato localmente: emette zero byte. Serve `SELECT changes()` o un wrapper equivalente: [S5:21](S5-brain-that-can-forget.md:21), [S5:52](S5-brain-that-can-forget.md:52).
- `mem save fact "probe" 7` lascia una memoria sintetica live e il successivo conteggio globale può essere già non-zero: non prova che quella riga abbia ricevuto TTL: [S5:53](S5-brain-that-can-forget.md:53).
- `ls -la` prova soltanto la dimensione del file, mentre `<newest-backup>` non è un comando eseguibile e il conteggio totale non dimostra che tutte le righe rispettino la retention window: [S5:54](S5-brain-that-can-forget.md:54), [S5:55](S5-brain-that-can-forget.md:55).

16. **Boundary scan:** nessun valore segreto, client PII o payload OSINT in chiaro nel diff. Non risultano scope-in su `zantara_core.py`, `fly.toml` o `apps/bali-intel-scraper/backend/db/migrations/env.py`. L’unico rischio off-limits è la correzione potenziale di `.env*` in S2, finding 9.

### Verdict per file

| File                        | Verdict |
| --------------------------- | ------- |
| README.md                   | REWORK  |
| S1-arm-the-armer.md         | REWORK  |
| S2-custody.md               | REWORK  |
| S3-arm-the-auditors.md      | REWORK  |
| S4-reaper-and-signal.md     | REWORK  |
| S5-brain-that-can-forget.md | REWORK  |
