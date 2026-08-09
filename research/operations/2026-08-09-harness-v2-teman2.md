---
date: 2026-08-09
adversarial_review: exempt-historical-input-consolidated-and-corrected-by-2026-08-10-fleet-order-spec
---

# Harness Operativo v2 — Nuzantara / Teman2

> Data: 2026-08-09 · Origine: piano ChatGPT (v1) + reasoning Fable-5 su costituzione repo
> Stato: RATIFIED by Zero 2026-08-09; amended and superseded-where-conflicting by 2026-08-10-fleet-order-spec.md (see its §0 Precedence)
> Tesi: **il potere non sta nella collezione di famiglie, ma in indipendenza + receipts + enforcement.**

---

## 0. Collocazione — cosa È e cosa NON è

**L'harness non è una seconda dottrina.** Il repo ha già il master loop: skill `modus`
(TRIAGE → GROUND → DESIGN → BUILD → VERIFY → SHIP+ARM → PROVE-LIVE → ALIGN-FLEET → CLEAN → CAPTURE).
Il piano v1 ri-descriveva questo loop senza saperlo. Due costituzioni = doctrine drift —
la stessa malattia condannata dalla ratifica 2026-07-25 ("una regola che mente è peggio di entrambe le opzioni").

I **tre organi genuinamente nuovi** che v1 porta, e che questo documento innesta su modus:

1. **Evidence Pack** — artefatto tipizzato e obbligatorio che il gate consuma (modus ha VERIFY/PROVE-LIVE ma nessun dossier normalizzato).
2. **Grammatica dei verdetti** — PASS / PASS-WITH-CONDITIONS / REWORK / BLOCK con semantica esecutiva.
3. **Matrice seat-ruolo** — chi può fare cosa, con stato di armamento reale.

**Perimetro intoccato (non negoziabile):**
- Il **final on-disk gate** resta com'è: incondizionatamente Fable a max effort, zero classifier/novelty-check/task-shape logic davanti, window dead → SUSPEND. Questo harness lo nomina solo per dire che **non lo tocca, non lo avvolge, non lo condiziona** (un edit in quella direzione è già stato cassato in adversarial review — non si reintroduce, nemmeno indirettamente).
- Ship-lifecycle ownership: **la sessione fa tutto** — review, merge, arm, deploy, prove-live. Il codeowner non mergia, non reviewa, non deploya, by design.
- Fable-paid contingency: se Fable diventa metered, **non si paga mai** — vale per ogni uso non-final-gate.

---

## 1. Intake — classificazione con floor deterministico

Ogni task entra e riceve un **Task Brief**. Chi lo redige: Haiku 4.5 (triage/sintesi) o modello locale se il materiale è PII/sensibile (processing locale-sovrano, Law 2).

**Regola dura: la classe NON la decide un modello.** La classe ha un **floor deterministico**:

```
diff ∩ hot-zone list (la stessa del pre-commit lease-check:
LaunchAgent wrappers, migrations, auth/billing/pricing,
.github/workflows/, sentinel/dlq)          ⇒ Gear 3
spec architetturale / quote cliente /
pre-deploy critical path (doctrine 4-LLM)  ⇒ Gear 3
feature PR standard (L2)                   ⇒ Gear 2 minimo
resto (docs, typo, chore fuori hot-zone)   ⇒ Gear 1
```

Il modello può solo **alzare** la classe proposta, mai abbassarla sotto il floor.
**Monotonia:** dopo l'intake la classe può salire, mai scendere — chiude la scappatoia
"declassa il task per schivare il gate". CI ricalcola il floor dal diff e fallisce se il brief dichiara meno.

**Schema Task Brief** (YAML, nel PR body o `evidence/brief.yml`):

```yaml
task_id: <lane>-<slug>
gear: 1|2|3                 # ≥ floor deterministico, monotono ↑
l_level: L1|L2|L3
gate_class: none|opus|fable # fable ⇔ gear 3
objective: 1-3 righe verificabili
constraints: [...]
acceptance: [criterio + comando che lo prova]
consumer_map: [ogni superficie consumante da provare live]  # merged ≠ live
risks: [...]
grader: <seat>              # assegnato ORA, ≠ builder, famiglia diversa se possibile
budget: {seats: [...], fable_gate_est_tokens: N}
pii: none | present→local-only
```

Il grader si decide **prima di scrivere codice**: il builder sa che sarà giudicato e non sceglie il proprio giudice. Il consumer-map si compila all'intake, non a fine corsa (scar: merged-is-not-live, consumer-map-first).

Ordine memoria: `mem` prima di NotebookLM. Escalations HIGH (`shared/escalations_pro.jsonl`) prima di tutto.

---

## 2. Strategia — piano finito, budget gerarchico

- **Default: Opus 5 `xhigh`** (architettura, trade-off, decomposizione) + **Gemini DeepThink** come seconda lettura cross-family + **NotebookLM/Oracolo** per grounding documentale.
- **Fable-su-strategia = eccezione**, mai default. Richiede una riga di motivo nel brief e vale solo per problemi genuinamente direction-setting. Ragione: strategia e final gate pescano dalla **stessa allowance settimanale Fable** (50% sul seat Team-Premium). **Il gate ha precedenza assoluta.** Se la proiezione settimanale del carico gate non lascia headroom, Fable-su-strategia è la prima cosa che muore. Sotto contingency paywall, muore comunque (mai pagare); il gate invece SOSPENDE, mai degrada.
- Output obbligatorio: **un piano finito** — decomposizione, criteri di accettazione per pezzo, punti di non-ritorno marcati. Il brainstorming senza piano è un fallimento dello stage, non "creatività".

L'A/B corretto (KBLI, 10/14 tie, 0 errori fattuali per parte) ha misurato Fable ≈ Opus sul lavoro grounded/strutturato: spendere l'allowance qui non compra quasi nulla. La v1 diceva "creatività in ingresso, freddezza in uscita" — poetico ma invertito rispetto al budget: **i token Fable scarsi vanno al lato freddo (gate), il lato caldo ha sostituti provati indistinguibili.**

---

## 3. Costruzione — worktree, leases, seat reali

**Isolamento obbligatorio:** ogni builder sotto `.worktrees/<lane>-<task-id>/` via `scripts/agent_start.py`. Main checkout read-only per agent. Hot-zone → lease Redis (`agent_lock:<resource>`) come da pre-commit lease-check; degradazione graceful se Redis down.

### Seat ARMED (load-bearing consentito)

| Seat | Ruolo | Quota | Vincoli non negoziabili |
|---|---|---|---|
| Sonnet 5 | Implementer principale | MAX OAuth | CLI only (SDK Anthropic BANNATO); tokenizer +30%: ri-misurare max_tokens con count_tokens |
| Haiku 4.5 | Grunt/triage | MAX OAuth | — |
| Opus 5 | Architettura, sessione interattiva | MAX OAuth | thinking ON di default; max_tokens copre thinking+risposta; per costo abbassa effort, non disabilitare thinking |
| Codex (Terra/Luna) | Patch alternative, migrazioni Alembic, test | ChatGPT Pro flat (pre-auth) | `--sandbox read-only\|workspace-write` ONLY, mai bypass |
| Codex Sol | **Refuter principale** | ChatGPT Pro flat | xhigh/max per red-team |
| Kimi K3 / kimi-for-coding | Refuter indipendente, long-context, builder alternativo, frontend | Allegro flat | `kimi -p ... -m kimi-code/k3` etc.; mai final gate |
| Gemini agy | search (KBLI/visa/normative — Claude allucina regolamenti), explore (refactor 3+ app), redteam pre-deploy | AI Ultra | mai deploy senza redteam Gemini (federation table) |
| NotebookLM | Oracolo/grounding NB-1 | — | solo dominio o cross-query, dopo mem |
| Antigravity | Braccio autonomo su task ben delimitati | AI Ultra | SEMPRE worktree fresco, MAI main; verify indipendente della sessione (ri-esegue i test); NO architettura, NO PII reale, NO deploy, NO scelta di quali bug contano; mai auto-merge da IDE |
| Ollama locale (Pro/Mini) | PII-safe, cron, fallback, OCR | gratis | vision = `qwen2.5vl:7b` ONLY; `think:false` per Qwen 3.5 |
| Fable 5 | **Final gate** (+ strategia in eccezione) | 50% weekly incluso | vedi §6; mai pagare oltre allowance |

### Seat CANDIDATE (citati in v1, NON armati — vietato renderli load-bearing)

| Seat | Ruolo proposto | Blocco all'ingresso |
|---|---|---|
| Qwen (Max) | Secondo POV strategico, candidato | Regola costi §5 CLAUDE.md: per-token ⇒ GO esplicito di Zero; poi probe in `arsenal_probe.py` + 2 settimane non-load-bearing |
| GLM | Engineering worker alternativo | idem |
| MiniMax | Throughput, batch, docs | idem + entra in cost_baseline (che va comunque ri-misurato sul price table 5-family) |
| Jules | Worker asincrono su repo | opera fuori worktree-discipline (VM propria): ammesso SOLO come candidato via PR, branch protection lo tiene fuori dal merge |

**Principio anti-drift:** la dottrina non cita mai flotte inesistenti. Un seat sta in una sola tabella e la tabella dice la verità. (DeepSeek: RETIRED, seat refuter → Kimi K3 — corretto in v1.)

Checklist onboarding nuovo seat: costo (free/flat/per-token→GO Zero) → niente API key Anthropic-style vietate → probe → probation → promozione con entry in questo file.

---

## 4. Refutazione — disaccordo falsificabile, non rumore

**Motore esistente, non nuovo:** `infra/workflows/verify-template.js` (gather → adversarial-refute → synthesize, refuter su fresh context). Il 4-LLM panel resta obbligatorio per spec/quote/pre-deploy.

Regole che trasformano il "disaccordo utile" da slogan a meccanismo:

1. **Indipendenza reale**: refuter su contesto fresco, famiglia diversa dal builder quando possibile, **lenti diverse** (uno attacca le assunzioni, uno security/regressioni, uno riproducibilità) — la diversità di lente cattura ciò che la ridondanza non vede. 2 refuter davvero indipendenti > 5 correlati.
2. **Falsificabilità**: un'obiezione è bloccante solo se **CONFIRMED** (file:line + repro command + esito). Senza repro è **PLAUSIBLE**: entra nel pack come dissenso registrato, non blocca. Questo impedisce al panel di diventare la macchina del rumore (principio 10 di v1).
3. **Quorum per gear**: Gear 2 = 1 refuter (Sol o K3). Gear 3 = 2 refuter indipendenti + Gemini redteam se pre-deploy. Un finding PLAUSIBLE segnalato indipendentemente da entrambi i refuter → trattato come CONFIRMED-by-convergence.
4. **Pipelined, non barrier**: la refutazione parte per-file appena il build atterra (pattern pipeline del Workflow tool), non come cerimonia a valle.

Simmetria generator≠grader in entrambe le direzioni: il builder non giudica il proprio lavoro, **il giudice non implementa le proprie correzioni** (v1 aveva ragione — si tiene, con nome).

---

## 5. Evidence Pack — contratto machine-checkable

Il pack è **l'unico input del gate**. Non è un report: è un dossier con receipt.

```yaml
brief_ref: evidence/brief.yml
plan_ref: <link piano scelto>
diff: {files: N, insertions/deletions, hotzone_hits: [...]}
receipts:            # OGNI claim ha comando+exit+timestamp+seat, o è declassato a OPINION
  - {claim: "...", cmd: "...", exit: 0, ts: "...", seat: "sonnet-5"}
tests: {cmd: "...", passed: N, failed: 0}
static: {lint: ok, typecheck: ok, build: ok}
runtime_proof: [screenshot/log refs — Vercel/GH Actions quando rilevanti]
dissent:             # campo OBBLIGATORIO, non opzionale
  - {seat: codex-sol, objection: "...", status: CONFIRMED|PLAUSIBLE|RETRACTED, repro: "..."}
residual_risks: [...]
sources: [NLM/doc refs se il task dipende da normativa]
pii_scan: clean      # client_id/hash only — mai PII in chiaro (Law 2, UU PDP)
size_tokens: ≤ 30k   # hard cap
```

**Enforcement (i prompt non bastano — §7 CLAUDE.md):**
- `scripts/evidence_pack_lint.py` (da creare) come **required check**: pack incompleto ⇒ gate fisicamente irraggiungibile. Rifiuta: claim senza receipt, dissent vuoto su Gear 3, PII/secret patterns, oversize.
- **Receipts = anti-allucinazione resa fisica**: "mai citare output di tool non eseguito in questo turn" smette di essere disciplina e diventa formato.
- **Cap 30k**: protegge l'allowance Fable per verdetto e obbliga a comprimere l'evidenza, non a narrare. Overflow = pack difettoso, non "gate più lungo".
- **Zero-dissent su Gear 3 = flag "consenso sospetto"**: o i refuter non hanno provato, o non erano indipendenti. Il linter lo marca.

**Anti-Goodhart (il punto che v1 non vede):** appena il pack esiste, i builder ottimizzeranno *il pack*, non la realtà. Difese:
1. receipts con provenance (comando ri-eseguibile);
2. il gate ha **diritto di spot-check**: può ri-eseguire fino a N receipt a campione o su sospetto (stesso principio del verify indipendente su Antigravity);
3. frode da pack accertata ⇒ scar cicatrix + tripwire test, e il seat responsabile perde load-bearing status fino a nuova probation.

---

## 6. Fable Gate — verdetti con semantica esecutiva

**Giurisdizione:** Gear 3 (`gate_class: fable`). Gear 2 chiude con verdetto Opus + AI-review action + CI. Gear 1 chiude con CI. (Il final on-disk gate è una lane separata e intoccata — sempre Fable per suo conto, fuori da questa tassonomia.)

**Setup:** sessione fresca, `claude-fable-5`, effort max, consuma il pack (+ spot-check facoltativi). Seat Fable morto/limitato ⇒ **SUSPEND in PENDING-ARMS. Mai downgrade, mai pagare.**

| Verdetto | Semantica esecutiva |
|---|---|
| **PASS** | La sessione esegue merge+deploy immediatamente (vedi §7). |
| **PASS-WITH-CONDITIONS** | Ship consentito **solo se** ogni condizione ha entry PENDING-ARMS con owner non-fantasma (`session[...]` o `operator[<categoria>]` — mai bare operator) **e scadenza**. Condizione scaduta non onorata ⇒ auto-escalation a REWORK sul componente. Senza questa regola, PWC è la falla da cui passa tutto. |
| **REWORK-BUILD** | Piano sano, implementazione difettosa → torna a §3, stesso brief, findings del refuter allegati. |
| **REWORK-DESIGN** | Il piano stesso è sbagliato → torna a §2, brief emendato. Il gate DEVE dire quale dei due: previene il thrash. |
| **BLOCK** | Task SOSPESO → entry in `shared/escalations_pro.jsonl`; la motivazione è scar-candidate se rivela trappola sistemica. |

**Bounded loop:** max 2 cicli REWORK; il terzo ⇒ BLOCK + escalation. Nessun polish-loop infinito che brucia la flotta.

**Il gate non costruisce e non ha le mani:** emette verdetti; le mani sono della sessione. Ma attenzione alla lettura sbagliata di v1 ("Fable non effettua merge") → NON significa "aspetta un umano". Significa: **la sessione Anthropic esegue**. Nessun phantom-operator.

**Meccanizzazione (l'upgrade più forte):** il verdetto viene pubblicato come **status check** (`harness/fable-gate: PASS`) via gh. Branch protection lo richiede sui PR gate-class (label applicata all'intake; config del labeler protetta CODEOWNERS-TIER1 + meta-verifier, stesso pattern grader-self-protecting del modello Subhi). Così:
- `gh pr merge --auto --squash` armato a PR-open **resta la legge** (nessun conflitto col doctrine ship-lifecycle);
- il gate diventa **CI-enforced, non prompt-enforced**;
- nessuno — nemmeno il builder più convincente — mergia un gate-class senza il check verde.

**Il gate è dentro il loop immunitario, non sopra:** un PASS ribaltato da un incidente post-ship diventa scar + tripwire. Anche il giudice lascia receipts.

---

## 7. Ship — la sessione esegue, done = live

Dopo PASS (o PWC con ledger a posto):

1. Merge: auto-merge già armato scatta sui required checks verdi. Emergenze: la sessione mergia, mai il codeowner.
2. Deploy: la sessione, da **repo root** (`fly deploy --config apps/backend-rag/fly.toml ...` — mai da `apps/backend-rag`, il wrapper `fly` locale va bypassato). Sequenza pre-deploy di CLAUDE.md §11 invariata. Frontend: Vercel su push.
3. **PROVE-LIVE su OGNI superficie del consumer_map** (dal brief, non improvvisato): curl 200/307 → screenshot via claude-in-chrome → colori/logo/no broken → fix/redeploy se serve. Il pack riceve l'**addendum post-ship**; senza live-proof il task non è "done", è "merged".
4. Verità: GitHub = codice, CI = prova automatica, runtime = verità operativa. Nessun agente esterno auto-mergia o auto-deploya — enforcement: branch protection + required checks, non fiducia.

---

## 8. Capture — l'harness impara o non serve

- `mem save` proattivo obbligatorio: decision 8-10, discovery 7-8, unresolved 5-6. Non si chiede, si salva.
- Ogni BLOCK, ogni refutazione CONFIRMED, ogni PASS ribaltato ⇒ scar-candidate (cicatrix TRAUMA/ANTIBODY/GOTCHA) + dove possibile tripwire test.
- Ricerche sostanziose → convenzione `research/<domain>/` (§15).
- ALIGN-FLEET + CLEAN di modus: worktree via, ledger aggiornati, nessun residuo.

Nota terminologica (2026-06-28): questo è il loop di **self-healing/reliability** (anelli A1-A4), NON "self-improvement"/RSI. Non chiamarlo così.

---

## 9. Invarianti → Enforcement (ogni regola ha il suo dente)

| Invariante (v1 §9) | Meccanismo che la rende inviolabile |
|---|---|
| 1. Generator ≠ grader | Grader assegnato nel brief all'intake + check: author del diff ≠ author del verdetto |
| 2. Fable final gate sui task importanti | Required check `harness/fable-gate` sui PR gear-3; nessun fallback configurato: seat morto ⇒ SUSPEND |
| 3. Esterni producono candidati, non decisioni | Branch protection: nessun seat esterno ha merge rights; i loro output entrano solo come PR/patch nel pack |
| 4. No self-merge | Branch protection + CODEOWNERS-TIER1 + actionlint + meta-verifier (i workflow che gatekeepano non sono disarmabili da chi è gatato) |
| 5. No deploy autonomo esterno | Credenziali Fly/Vercel solo nel perimetro sessione/operator; mai nei seat esterni |
| 6. PII nel perimetro | `pii_scan` nel linter (client_id/hash only) + cloud_vision_gate fail-closed + processing locale-sovrano |
| 7. Decisioni supportate da evidence | Pack linter required: niente pack ⇒ niente gate ⇒ niente merge gear-3 |
| 8. Valore = disaccordo utile | Dissent field obbligatorio + falsificabilità (CONFIRMED/PLAUSIBLE) + zero-dissent flag |
| 9. Modello costoso solo se giustificato | Floor deterministico dei gear + effort ladder (Opus low/medium sopra il loro peso; xhigh sweet spot coding) + budget Fable gerarchico |
| 10. Ridurre il rumore | Cap 30k sul pack + obiezioni senza repro non bloccano + quorum fissi |

E il meta-invariante del repo: **se una regola critica è violabile, scrivi un hook.** Ogni riga di questa tabella che oggi non ha il suo check è un item PENDING-ARMS, non una speranza.

---

## 10. Degradazione e kill switch

- **Liveness dei seat**: `scripts/arsenal_probe.py` è la fonte di verità. Probe stale (>7d) ⇒ il seat non è load-bearing in refutazione finché non ri-probato.
- **Fallback per RUOLO** (mai per il gate): refuter Sol → K3 → Gemini redteam; implementer Sonnet → Codex → kimi-for-coding; grunt Haiku → locale. **Il gate non ha fallback: SUSPEND.**
- **Kill switch**: `HARNESS_ENFORCEMENT=false` (logga il bypass con motivo, non lo zittisce) + i kill switch esistenti restano (`AGENT_BROKER_ENABLED`, `SKIP_PREFLIGHT`, lease enforcement, ...). I sistemi potenti hanno freni che non controllano loro.
- I seat muoiono (DeepSeek ritirato, Fable paywall-risk, OAuth scadenze): l'harness degrada con grazia su tutto tranne che sul gate.

---

## 11. Rollout — tre fasi, nessun big bang

**Fase 1 (doc + attrezzi, 1 PR):** landing di questo doc in `research/operations/2026-08-09-harness-v2-teman2.md` → ratifica Zero → fold normativo in modus SKILL.md (§Gates/§Arsenal) + `scripts/evidence_pack_lint.py` + template brief/pack. *(Punto esatto di innesto in SKILL.md da verificare al landing sui file reali.)*
**Fase 2 (enforcement):** `harness/fable-gate` come required status check sui PR labellati gear-3; CI ricalcola il floor dal diff; linter required. Da qui il gate è macchina, non memoria.
**Fase 3 (flotta):** onboarding CANDIDATE seats uno alla volta (Qwen → GLM → MiniMax → Jules), ognuno con GO-costi, probe, probation. Mai più di un seat in probation per ruolo.

Ogni fase con la sua entry PENDING-ARMS, owner `session[...]`.

---

## Appendice — divergenze deliberate da v1 (per il record)

1. v1 non diceva chi mergia → qui è legge: **la sessione** (anti phantom-operator, feedback 2026-07-16).
2. v1 metteva Fable in strategia senza accoppiarlo al budget del gate → qui precedenza assoluta al gate.
3. v1 elencava GLM/MiniMax/Qwen/Jules come flotta corrente → qui sono CANDIDATE dietro checklist. La dottrina non descrive stati inesistenti.
4. v1 finiva al deploy → qui done = PROVE-LIVE su consumer-map + CAPTURE.
5. v1 non aveva difese anti-Goodhart sul pack → qui receipts + spot-check + scar.
6. v1 "Workspace come memoria" → qui la memoria è MOS (`mem` prima di NLM); Workspace è document store sotto DPA.
7. v1 non aveva semantica per PWC/REWORK → qui ledger con owner+scadenza e due classi di rework, loop bounded.
8. v1 applicava un solo pipeline a tutto → qui gearing con floor deterministico: il rigore scala col rischio, il rumore no.
