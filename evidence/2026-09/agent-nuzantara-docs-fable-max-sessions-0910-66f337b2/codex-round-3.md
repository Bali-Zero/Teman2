# Codex adversarial review — round 3 (seat codex, gpt-5.6-sol, 2026-09-10, on v3 b701479b33)

> Recovered from the session transcript: the Codex context-bridge hook forced a checkpoint after the review was written, so stdout carried only the checkpoint line (276K tokens used).

[Pro] Verdetto complessivo: **REWORK**. F8 non viene riaperto: l’evidenza sul merge queue è vera sul disco.

### Stato dei 17 rilievi

1. **RESOLVED** — BLUE apre Opus, ORANGE apre Sol prima dell’avvio. `README.md:15-18`; `S1:12-16`; `S2:12-16`; `S3:12-16`; `S4:14-18`; `S5:12-16`.
2. **PARTIAL** — l’assenza di Astra è registrata, ma una lettura futura o una waiver di Zero non sostituisce l’approvazione dei due imperator sullo stesso packet hash; Wave 1 è già partita. `README.md:9-11`; `S1:13`; `S5:13`.
3. **RESOLVED** — la grunt lane è rimossa; i lavori maggiori sono finestre queued e i one-liner hanno proprietario o restano queued. `README.md:69-101`.
4. **RESOLVED** — Wave 2 richiede merge, pull riuscito e sei tick puliti. `README.md:47-50`; `S1:70-72,107`; `S3:15`; `S4:17`.
5. **RESOLVED** — DIRTY reale crea un successore da `origin/main`; nessun disarm/re-arm. `README.md:60-67`; `S1:57-63`; `S2:52-55`; `S3:54-57`; `S4:50-53`; `S5:53-56`.
6. **RESOLVED** — S1 possiede solo shepherd e test su Pro; i sibling Mini sono separati. `S1:20-22,38-43`; `README.md:71-74`.
7. **RESOLVED** — la prova usa uguaglianza dei blob, non ancestry. `S1:68-71`; `S2:60-62`; `S3:69-71`; `S4:57-59`; `S5:61-63`.
8. **RESOLVED** — rilievo superato dall’evidenza: la queue richiede `--auto` senza strategy flag. `README.md:105-107`; `scripts/queue_shepherd.py:819-821`; `docs/runbooks/merge-queue-discipline.md:274-278`.
9. **RESOLVED** — i checkpoint usano valori shell concreti e il comando `local broadcast` valido. `S1:95`; `S2:83`; `S3:87`; `S4:79`; `S5:84`.
10. **RESOLVED** — intervallo fissato a 3600 secondi e osservazione confrontata nello stesso minuto con `find`. `S2:22-24,62-65`.
11. **RESOLVED** — schedule, probe/DIVERGED e correzione/OK sono PR distinti; l’attribuzione usa `launchctl` e `invoked_by`. `S3:58-69,95`.
12. **RESOLVED** — la venv root esiste e il comando pytest è eseguibile. `S4:56-57` e analoghi negli altri S-file.
13. **RESOLVED** — ceiling numerico e rollback indipendente dalla baseline zero. `S4:22-24,55-56,88-89`.
14. **RESOLVED** — S5 è ridotta al meccanismo; backup, apply, VACUUM e HOME sync passano a S5b. `README.md:50,72-74`; `S5:20-24`.
15. **RESOLVED** — insert/delete avvengono solo sulla copia scratch; S5b prevede verifica indipendente post-apply. `S5:58-65`; `README.md:74`.
16. **RESOLVED** — backup nel prune esistente, `chmod 600` esplicito e archivio interno al DB. `README.md:74`; `S5:85-89`.
17. **PARTIAL** — il rollback protegge le nuove righe `memories`, ma usa solo `max(id) from memories`: non protegge nuove `raw_observations`, scritte anche dai capture hook mentre il compression daemon è fermo. `README.md:74`; `S5:86-99`; `~/.claude/hooks/mos_capture_post_tool.py:156`; `mos_capture_stop.py:75`; `mos_capture_session_end.py:66`.

### Nuovi blocker

1. **[BLOCKER] I checkpoint sono pubblicati, non consegnati.** Tutti gli S-file eseguono solo `fleet_mail ... broadcast` e presumono che lo staff room legga la mailbox. PARABELLUM richiede wake-up, hash dell’envelope, ack entro 15 minuti, un retry e poi BLOCKED. In S1 questo può perdere il trigger di Wave 2. `S1:72,95`; `S2:83`; `S3:87`; `S4:79`; `S5:84`; `docs/architecture/dual-consul/army-map.md:81-90`.

2. **[BLOCKER] S2 autorizza una mutazione live delle credenziali.** Il perimetro consente `chmod` sotto `~/nuzantara/.secrets`, mentre il Builder Contract riserva le credenziali all’umano. Il detector deve limitarsi a rilevare e segnalare, come già fa per `.env*`. `S2:40-43`; `CLAUDE.md:53-60`.

3. **[BLOCKER] Il worker di S5 non ha un consumer live nello stesso PR.** S5 modifica `scripts/mos-plus-compression-worker.py`, ma vieta l’installazione della HOME copy e dichiara che nulla live cambia; quella copia viene rinviata a S5b. Questo viola il contratto `Bites:`: un job futuro non è un consumer. `S5:20-22,38-40,63-65,97`; `README.md:72-74`; `CLAUDE.md:31-34`.

Non ho trovato altri comandi letteralmente ineseguibili né path esistenti citati ma assenti.

| File                        | Verdetto |
| --------------------------- | -------- |
| README.md                   | REWORK   |
| S1-arm-the-armer.md         | REWORK   |
| S2-custody.md               | REWORK   |
| S3-arm-the-auditors.md      | REWORK   |
| S4-reaper-and-signal.md     | REWORK   |
| S5-brain-that-can-forget.md | REWORK   |
