---
adversarial_review: exempt-council-artifact
---

<!-- Final answer extracted VERBATIM from the codex exec stream (lines 6755+); the full 6.8k-line execution stream is retained alongside as codex-redteam.stream.log (untracked working file, not part of the PR diff). Extraction boundary: the last "tokens used" marker. -->

304.361
## VERDICT

**FAIL** — il documento contiene analisi utili, ma non è una base affidabile per armare il seat: mescola checkout e snapshot diversi, inverte la canonicalità delle skill e descrive come regole controlli che il runtime Qwen attuale non applica.

Limite operativo: il Pro era irraggiungibile, quindi le affermazioni fleet “NOW” non sono state confermate live. Non ho rilanciato modelli né scritto file; ho letto i receipt esistenti.

## EVIDENCE CHECKS

1. **CONFIRMED — l’analisi originaria usava davvero un main obsoleto.**  
   Comando: `git -C /Users/balizero/nuzantara rev-list --left-right --count HEAD...origin/main` → `0 228`. Nel worktree revisionato lo stesso comando restituisce `0 0`, con `HEAD=origin/main=037327e37c...`. Il documento mescola quindi fatti del main obsoleto con conclusioni sul ref corrente.

2. **CONFIRMED — W2 esisteva come overlay locale; REFUTED — non è drift versionato del repository corrente.**  
   Comandi: `git -C /Users/balizero/nuzantara status --short -- .agents/skills/modus` mostra i tre file come `??` untracked; `git ls-tree -r --name-only HEAD -- .agents/skills/modus .claude/skills/modus` elenca solamente `.claude/skills/modus/*`. Nel worktree attuale `.agents/skills/modus` non esiste. W2 descrive residuo locale non riproducibile da clone, non “repo drift”.

3. **REFUTED — S1/W2 chiamano “live mirror” ledger ormai obsoleti.**  
   Comandi: `stat` e `shasum -a 256` sui ledger. L’overlay obsoleto aveva copie identiche da 793.771 e 38.052 byte; il ref corrente ha solo `.claude/PENDING-ARMS.md` da 971.864 byte e `.claude/AMENDMENTS.md` da 43.183 byte. Nessun mirror `.agents` corrente.

4. **REFUTED — 34 app e 87 workflow.**  
   Comandi: `find apps -mindepth 1 -maxdepth 1 -type d | wc -l` → `32`; stesso conteggio su `packages` → `6`; `find .github/workflows ... '*.yml'/'*.yaml' | wc -l` → `89`. Solo 21 workflow dichiarano `merge_group`, quindi anche la formulazione “merge-queue-era gates that always run” è troppo ampia.

5. **REFUTED — i numeri DOCSYNC citati in W3 sono correnti.**  
   Comando: `sed -n '1,12p' docs/AI_ONBOARDING.md`. Il file ora riporta `330 routers · 689 services · 1307 tests`, non `332/673/1277`. Il finding generale sul drift resta **CONFIRMED**, perché [AGENTS.md](/Users/balizero/nuzantara/.worktrees/ops-qwen-seat-review/AGENTS.md:247) continua a riportare `327/746/1449`.

6. **CONFIRMED — i due guardrail S3 principali esistono staticamente.**  
   `wc -l .husky/pre-push` → `657`; `rg -n 'FAIL-CLOSED|PUSH NOT VERIFIED LOCALLY'` trova il fail-closed e il verdetto non-green. La ricerca dei job in `fly-deploy.yml` conferma gate → migrations → rolling deploy → health → image-only rollback → Telegram. Questo prova il codice, non che ogni sviluppatore esegua sempre l’hook.

7. **REFUTED — W9 conta 1.581 test. CONFIRMED — il blind spot descritto esiste.**  
   Comandi: `find apps/backend-rag/backend/tests -name 'test_*.py'` → `1.307`; top-level `tests` → `276`, totale delle due estate `1.583`; sotto tutto `apps/backend-rag` sono `1.610`. `pytest.ini:7` e `pyproject.toml:266` limitano entrambi `testpaths` a `backend/tests`; `pyproject.toml:106-107` imposta `backend.* → ignore_errors=true`.

8. **CONFIRMED — il catalogo è obsoleto; REFUTED come prova di “11 failing NOW”.**  
   `jq '._updated, (.launchagents|length)' scripts/automation_catalog.json` → `2026-04-16`, `46`. [AUTOMATIONS_REFERENCE.md](/Users/balizero/nuzantara/.worktrees/ops-qwen-seat-review/docs/AUTOMATIONS_REFERENCE.md:4) contiene 235/11/17/18, ma lo snapshot è del 25 luglio. Senza un nuovo snapshot Pro/Mini, “NOW” l’8 agosto è unsupported.

9. **CONFIRMED — i quattro PONG finali compaiono nel transcript Qwen.**  
   Ho classificato con `jq` i `functionResponse` del transcript `~/.qwen/projects/.../2d195116-....jsonl`: Fable, Codex, Gemini e GLM hanno output finale `PONG`. Però il probe manuale contiene una trappola reale: `command-not-found` e `401` precedenti stampano entrambi `exit=0`, perché `... | tail; echo "$?"` misura `tail`, non il modello. Il PONG è quindi confermato dal corpo finale, non dall’exit code. Qwen stesso non è ancora nel probe ufficiale: [arsenal_probe.py](/Users/balizero/nuzantara/.worktrees/ops-qwen-seat-review/scripts/arsenal_probe.py:84).

10. **CONFIRMED — il runtime Qwen attuale non soddisfa ancora il profilo di sicurezza proposto.**  
    Comandi: `stat ~/.qwen/settings.json ~/.qwen/projects/.../*.jsonl`; presenza del token verificata con `jq -e '...length>0'` senza stamparlo; ricerca nel bundle installato. Risultati:

    - `BAILIAN_TOKEN_PLAN_API_KEY` è non vuota in `settings.json`.
    - Settings e transcript sono `0644`; la home è attraversabile dal gruppo `staff`.
    - `chatRecording` non è disabilitato e il codice Qwen usa `params.chatRecording ?? true`.
    - I transcript registrano prompt, tool arguments, tool output e system payload.
    - `qwen review run` usa `approval-mode=yolo` per default e può ricevere `--comment`.
    - Il CLI espone inoltre `review submit`, `publish-assets`, `channel`, MCP e `serve`.
    - Il log d’uso ha registrato circa 6,95 milioni di token, 6,51 milioni cached, in 63 chiamate in circa 31 minuti; `settings.json` non contiene limiti di sessione.

## FINDINGS

1. **P0 — credenziale cloud attiva conservata in chiaro e group-readable.**  
   È una violazione immediata della stessa cicatrix applicata da `claude-glm.sh`: Keychain, mai settings file. Non prova una compromissione esterna, ma rende il seat non armabile.  
   **Chiusura falsificabile:** token ruotato, rimosso dal JSON, recuperato transitoriamente da Keychain, permessi `0600`, test che dimostri assenza del segreto su disco.

2. **P1 — il confine PII è una promessa, non un controllo.**  
   Qwen registra automaticamente conversazione e tool output in file leggibili dal gruppo. Un solo tool che legga CRM/WhatsApp/Drive renderebbe persistente il dato, oltre ad averlo già inviato al provider. Il “dual-write alle Qwen memory dirs” aggiunge un’ulteriore retention surface e confligge con AGENTS R6.  
   **Chiusura:** wrapper-enforced `--chat-recording=false`, nessun accesso diretto alle sorgenti PII, test canary che fallisca prima dell’egress e non lasci transcript.

3. **P1 — il wrapper proposto eredita una superficie di mutazione/pubblicazione incompatibile con Legge 5.**  
   Un clone del pass-through `claude-glm.sh` accetterebbe qualsiasi argomento; Qwen può pubblicare review/assets, aprire channel e avviare un server. `review run` parte addirittura in `yolo`. Un PR ostile può anche alterare `.agents`, `.qwen` o `QWEN.md` e ridefinire il proprio giudice.  
   **Chiusura:** wrapper allowlist, `--bare --safe-mode --chat-recording=false`, approval `plan`, divieto meccanico di `--comment/submit/channel/serve`, regole caricate dal merge-base fidato e test con PR adversarial.

4. **P1 — la canonicalità proposta in §2.4 è sbagliata.**  
   [`.agents/skills/README.md`](/Users/balizero/nuzantara/.worktrees/ops-qwen-seat-review/.agents/skills/README.md:1) rende `.agents` canonico per Tier-A e riserva la glue specifica al tool al Tier-B. Il documento propone l’opposto. Inoltre Qwen cerca `.qwen` e `.agents`, non `.claude`: nel worktree corrente non riceve affatto `modus`.  
   **Chiusura:** adattamento Qwen intenzionale e versionato sotto `.qwen/skills`, oppure core Tier-A tool-agnostic più adapter; mai copia meccanica Claude→Qwen.

5. **P1 — collisione d’identità cloud/local e rischio PII.**  
   `qwen` indica già Ollama locale `qwen3.5`; il nuovo seat è Alibaba cloud, con credenziale, retention, quota ed egress diversi. Esistono inoltre un’automazione `com.nuzantara.qwen-code-review` e `~/scripts/qwen-code-review.sh`, che possono inviare Telegram e creare GitHub issue.  
   **Chiusura:** nomi distinti, per esempio `qwen-cloud-code` e `qwen-local-ollama`, disambiguazione nel registry e quarantena/ridenominazione del legacy wrapper.

6. **P1 — il PONG proposto può certificare il proxy sbagliato.**  
   Un token prova raggiungibilità momentanea, non modello selezionato, fallback, billing route, sandbox, recording, worktree o tool policy. I falsi `exit=0` osservati durante questa stessa sessione dimostrano la trappola.  
   **Chiusura:** subprocess senza pipeline shell, vero return code, risposta esatta, model/provider metadata, fallback disabilitato, stato policy incluso nel receipt e fixture per 401/quota/timeout/PONG-echo.

7. **P1 — economia non delimitata.**  
   “Own subscription/quota” non documenta tipo di piano, reset, overage o concorrenza. Il token-plan endpoint e il consumo della sessione dimostrano una nuova failure/billing domain, quindi “zero blast radius” e “non è un nuovo stack” sono falsi operativamente.  
   **Chiusura:** conferma di Zero sul contratto, cap per run/turn/tool/wall-clock, accounting e stop-loss. Nessun cron o cascade prima di allora.

8. **P2 — diverse conclusioni in §1.2/1.3 e §1.4 sono stale o retoriche.**

   - S4 “maximum heterogeneity value” non ha un benchmark di correlazione degli errori.
   - S6 `~3.836 PRs` sembra derivare dal massimo numero PR; la storia locale mostra 3.169 numeri PR unici, non 3.836 merge provati.
   - S7 “no corner” è una proposizione universale non auditata.
   - S9 `~49 runbooks` è lievemente stale: 53 Markdown, 52 escludendo README.
   - W2 è un overlay locale untracked, non drift del ref.
   - W3 ha numeri sbagliati, sebbene il finding sul drift sia valido.
   - W5 usa uno snapshot del 25 luglio come “NOW”.
   - W9 ha un conteggio falso, anche se il difetto di discovery è vero.
   - §1.4 è monocausale e auto-confermante: credenziali, default insicuri, quote e scheduler non discendono tutti dalla stessa credenza. “Mostly manual” è inoltre non misurato e contrasta con gli stessi automatismi elencati in S3.

   Il paradosso centrale è che il seat ripete la malattia che denuncia: il documento descrive no-PII/no-publish, mentre il runtime registra tutto e può pubblicare.

## Q1-Q4 RULINGS

**Q1 — AGENTS.md vincola Qwen.** Non c’è un vero conflitto: AGENTS parla esplicitamente degli agenti esterni; CLAUDE.md assegna il lifecycle completo a una sessione Claude. Qwen può produrre branch, diff, test e PR in un worktree. Una sessione Claude indipendente verifica, decide, mergea, arma, deploya e prova live. Qwen non giudica né spedisce il proprio lavoro.

**Q2 — non registrare né symlinkare adesso.** Qwen può scrivere il PR di hardening, ma una lane Claude ne possiede gate e merge. Prima servono: rotazione/Keychain, nome `qwen-cloud-code`, wrapper allowlisted, sandbox/policy enforcement, recording off, limiti, modello/provider fissi, nessun fallback, probe strutturato, collision audit e disponibilità machine-scoped. Il probe Mini giornaliero non deve sovrascrivere la verità del seat M5 con `NOT_INSTALLED`.

**Q3 — nessun cron e nessuna cascade.** Tenerlo interattivo e opzionale finché Zero non conferma piano, quota, reset, overage e autorizzazione economica. Poi introdurre cap e stop-loss misurati; non basta “subscription” come etichetta.

**Q4 — nessuna eccezione PII.** Il seat cloud non deve avere accesso diretto a CRM, WhatsApp/OSINT, passaporti, KTP/NPWP, documenti Drive o tool output non redatto. Eventuali input futuri devono attraversare un gateway locale deterministico di aggregazione/redazione; un’istruzione nel prompt non è un controllo.
