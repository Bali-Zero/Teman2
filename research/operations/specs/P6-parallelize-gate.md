# PEZZO 6 — Gate "SE parallelizzare" + BUILD∥ in sicurezza

> **Spec studio (non implementazione).** Ciclo calibrato: reuse-first (disk-state VERIFICATO) +
> council 2-LLM (Gemini red-team / DeepSeek logic). Pezzo 6 di 9.
>
> **Inversione-chiave**: l'enunciato del task ("BUILD∥ default") è **smentito dall'evidenza per il
> coding**. Il default corretto è **SERIALE**; il fan-out parallelo è per i tipi di lavoro che NON
> degradano (breadth-ricerca + specialist-ruoli-diversi), **mai coder paralleli sullo stesso
> artefatto**. La richiesta dell'utente ("dove si può in parallelo") è coerente con l'evidenza — perché
> "dove si può" = esattamente quei tipi.

---

## 0. La correzione che precede tutto — quale parallelismo, e il default è seriale

Il task originale dell'utente diceva "si costruisce pezzo per pezzo (dove si può in parallelo)" e il
brief lo aveva tradotto in "BUILD∥ default". Il council ha smontato l'enunciato (Gemini #5, DeepSeek
#2) e l'ha **riconciliato** con la richiesta dell'utente distinguendo i *tipi* di parallelismo:

| Tipo di parallelismo | Degrada? (evidenza) | Esempio |
|---|---|---|
| **Breadth-di-ricerca** (esplorazione, fan-out di letture) | **NO** (+90.2% Anthropic su research) | i 5 angoli della deep-research di questo ciclo |
| **Specialist con RUOLI diversi** | **NO** (è il regime dove multi-agent vince) | federation: gemini-search ∥ codex-sandbox ∥ claude-redteam |
| **Pezzi del sistema strutturalmente indipendenti** | **NO se davvero indipendenti** | modulo A e modulo B con zero file/contratti condivisi |
| **Coder paralleli sullo STESSO artefatto** | **SÌ, −70%** (Google 2512.08296) + failure-mode Devin | 3 agenti che editano lo stesso file/feature |

> **"Dove si può" (utente) = i primi tre tipi.** Il quarto è ciò che l'evidenza vieta. La contraddizione
> desiderio-vs-evidenza è **apparente**: si scioglie limitando il fan-out ai tipi che non degradano.
> Quindi: **il default è seriale (single-orchestrator); il fan-out è un'eccezione gated, non la regola.**

Questo capovolge la forma del pezzo: non "come parallelizzo tutto" ma "come decido i pochi casi in cui
parallelizzare è un guadagno netto, e come lo faccio senza i danni noti".

---

## 1. GROUND — disk-state + evidenza già catturata (VERIFICATO questo turn)

### 1.1 L'infrastruttura di parallelizzazione-SICURA esiste già (~80%)

| Mattone | Stato | Evidenza verificata |
|---|---|---|
| Worktree broker | **GIÀ-PRONTO** | `scripts/agent_start.py` (908 righe) — worktree isolato per session (lane+task-id), metadati JSON, TTL, cleanup WIP-safe con liveness-probe |
| Lease registry | **GIÀ-PRONTO** | `scripts/agent_lease.py` (644) + `docs/runbooks/redis-lease-registry.md` (219) — Redis SET-NX-EX atomic + WATCH/MULTI/EXEC token-owned + heartbeat + flock-fallback. Pre-commit hook blocca hot-zone |
| Fan-out orchestrator | **GIÀ-PRONTO (ma sempre-parallel)** | `scripts/federation_orchestrator.py` (576) — CLASSIFY→CHECKPOINT→DISPATCH(parallel)→ASSEMBLE→REVIEW. Fan-out di SPECIALIST (ruoli diversi), non coder sullo stesso file |

### 1.2 Il GATE "SE parallelizzare" NON esiste (gap #1 ad alto impatto, VERIFICATO)

- `classify_node:222` ritorna tipo/risk/domains/needs_search/explore/sandbox/redteam — **MA non emette
  un flag `parallelizable`** (letto in questo turn).
- `route_after_checkpoint:462` decide *quali* tool lanciare (search/explore/sandbox) — **ma il fan-out
  è incondizionato**: non c'è ramo "single-orchestrator se sequenziale" (letto in questo turn).
- → il sistema fa **sempre** fan-out, indipendentemente dalla parallelizzabilità.

### 1.3 Evidenza quantitativa SOTA (già catturata, VERIFICATA in 2026-06-02-sota-multiagent-orchestration.md)

- **Google "Science of Scaling" arXiv 2512.08296** (riga 60): hard **3-4 agent ceiling**; turn-count
  power-law exp 1.724; **sequential tasks −70%**; best-arch predicted 87%. → "bound 2-7 near-ottimale,
  NON alzarlo".
- (riga 42) Multi-agent **degrada** il coding-sequenziale, aiuta **solo** breadth-first parallelizzabile.
- (riga 112) La federation fa fan-out di **ruoli diversi**, NON coder sullo stesso artefatto → evita il
  failure-mode di Cognition/Devin (decisioni implicite conflittuali su artefatto condiviso).
- (riga 81) Proposta **A1**: CLASSIFY emette `parallelizable: bool`, route → single-orchestrator per
  sequenziale, fan-out solo breadth. Effort 2, "highest-impact code change". NON shippato.

### 1.4 Cicatrici sui danni del parallelismo (famiglia sibling-race, VERIFICATE)

W62 (6 worktree stale 34h), W59 (sibling HEAD-race), W50/51/52 (HOME-fork drift), 2026-04-29 (untracked
files persi da `git stash` no-`-u`, 2× in 9h). **Pattern comune**: due sistemi/agenti credono di avere
world-state diverso → drift/perdita silenziosa. L'infra §1.1 nasce da queste ferite.

---

## 2. I 6 DIFETTI DEL RED-TEAM → risoluzione (DeepSeek)

| # | Difetto (Gemini) | Sev | Risoluzione (DeepSeek) |
|---|---|---|---|
| 1 | classificatore-9B sottodimensionato (Qwen3.5:9b giudica "parallelizzabile"?) | ALTA | §3.1: il flag è `parallelizable_HYPOTHESIS` (stima statica grezza: file-toccati-stimati, struttura repo), NON un giudizio fine. Il 9B fa una stima conservativa; il monitor runtime (§3.2) corregge. + escalation a Claude per task ambigui (cascade). |
| 2 | decisione-a-massima-ignoranza (dipendenze emergono costruendo) | **CRITICA** | §3.2: decisione = **ipotesi revocabile**. Monitor a runtime rileva dipendenze emergenti → **ri-serializza i rami coinvolti** (fan-out → single-orchestrator). Gate = processo distribuito stima→esegui→verifica→ri-serializza, non binario-irrevocabile. |
| 3 | isolamento-fisico vs conflitto-semantico (A=REST/B=GraphQL, mai stesso file) | **CRITICA** | §5 residuo + §3.4: worktree+lease NON catturano il conflitto semantico. Mitigazione: i pezzi paralleli condividono un **contratto esplicito a-priori** (OpenAPI/AsyncAPI di P4) PRIMA del fan-out; il contract-test di P4 al merge cattura la divergenza. Non risolto al 100% (residuo onesto). |
| 4 | cap saturato (4 specialist già = 3-4 ceiling) + starvation CPU Mac | MEDIA-ALTA | §3.3: distinguere agenti-infrastrutturali (search/explore = brevi, I/O-bound) da agenti-build (lunghi, CPU-bound). Il cap 3-4 si applica ai **coder concorrenti**, non al totale dei ruoli. + cap = prior aggiornabile su risorse-Mac reali. |
| 5 | ri-serializzazione al merge (costo nascosto) | MEDIA | §3.5: includere `estimated_merge_cost` nella decisione. Parallelizza **solo se** `tempo_seriale > (tempo_parallelo + costo_merge)`. Valuta la **componibilità**, non solo l'indipendenza. |
| 6 | rigidità dogmatica (un paper come legge, no feedback) | MEDIA | §3.3: il ceiling è **prior bayesiano aggiornabile**, non costante. Feedback empirico locale (tempo/merge-cost/throughput) aggiorna il cap. Re-evaluate se la fleet cresce. |

**Convergenza red-team↔logic**: i 2 difetti CRITICA (#2 ignoranza, #3 semantico) sono il cuore. DeepSeek
ne scioglie uno completamente (#2 → revocabilità) e mitiga l'altro (#3 → contratto-a-priori + residuo).

---

## 3. DESIGN — il gate come processo revocabile, non decisione binaria

### 3.1 CLASSIFY emette un'IPOTESI, non un verdetto (difetto #1)

- `classify_node` aggiunge `parallelizable_hypothesis: bool` + `estimated_files_touched: list` +
  `estimated_merge_cost: low|med|high`. Stima **statica e grezza** (struttura repo, keyword, file
  probabili) — NON un giudizio fine sulle dipendenze (un 9B non ne è capace).
- Per task ambigui/high-risk: escalation a Claude (cascade tier) per la stima, non lasciarla al 9B.
- Il flag è un'**ipotesi di partenza**, dichiaratamente fallibile.

### 3.2 La decisione è REVOCABILE — monitor + ri-serializzazione (difetto #2 CRITICA)

```
stima (CLASSIFY) → esegui (fan-out su ipotesi) → MONITOR (rileva dipendenze emergenti)
   → se emerge dipendenza tra rami paralleli → RI-SERIALIZZA i rami coinvolti (fan-out→single)
```

Il monitor: durante l'esecuzione parallela, se due rami toccano file che la stima aveva creduto
disgiunti (lo scopre dal lease-registry: due task chiedono lease sulla stessa hot-zone), o se un
contract-test fallisce, **i rami coinvolti vengono ri-serializzati** (uno aspetta l'altro, o si fondono
in un single-orchestrator). Il gate non è "parallelo per sempre" — è "parallelo finché regge".

### 3.3 Cap = prior bayesiano, e separa infra da build (difetti #4, #6)

- Cap iniziale = **4** (Google 2512.08296), applicato ai **coder concorrenti** (CPU-bound, lunghi). Gli
  agenti-infrastrutturali (search/explore = I/O-bound, brevi) non contano nello stesso budget.
- Il cap si **aggiorna** con feedback locale (tempo totale, merge-cost, throughput su Mac reale). Se i
  dati locali mostrano beneficio a 5-6 in certe condizioni, il cap si adatta. Né dogma né ignoranza:
  **prior aggiornabile**.
- Bound pratico verificato del repo: 2-7 sessioni concorrenti. Il cap-coder ≤ 4 ci sta dentro.

### 3.4 Contratto esplicito PRIMA del fan-out (difetto #3 CRITICA, mitigazione)

Prima di parallelizzare due pezzi, definire il **contratto** che li lega (OpenAPI per API↔API,
AsyncAPI per evento, signature per funzione — i contract di P4). Gli agenti paralleli costruiscono
*contro il contratto*, non liberamente. Il contract-test di P4 al merge cattura se uno ha divergiato.
**Non elimina** il conflitto semantico (un agente può rispettare il contratto-dati ma divergere su una
decisione non-contrattualizzata) — vedi §5 residuo.

### 3.5 Costo netto positivo — valuta la componibilità (difetto #5)

La decisione finale del gate include il costo di ricomposizione:

```
parallelizza SOLO SE: tempo_seriale_stimato > (tempo_parallelo_stimato + costo_merge_stimato)
```

`costo_merge` stimato da: sovrapposizione dei file-toccati (disgiunti = basso) + esistenza di contratti
espliciti (formalizzati = basso). Pezzi che si ricompongono a costo ~0 (interfacce pulite) →
parallelizzare conviene. Pezzi intrecciati → seriale anche se "sembrano" indipendenti.

### 3.6 BUILD∥ in sicurezza — le 3 condizioni infra (già esistenti)

Quando il gate dice "parallelizza", ogni agente DEVE avere: (a) worktree isolato (`agent_start.py`),
(b) lease sulle hot-zone che tocca (`agent_lease.py`), (c) il contratto esplicito (§3.4). Le 3 insieme.
L'infra c'è (§1.1); manca solo cablare il gate sopra.

---

## 4. LA FORMULAZIONE DEL GATE (DeepSeek, sintesi)

**Parallelizza se e solo se TUTTE vere** (e la decisione è revocabile):

1. **Indipendenza stimata**: file-toccati disgiunti OPPURE API contrattualizzate (basso `merge_cost`).
2. **Tipo di lavoro**: breadth-first (ricerca/esplorazione) OPPURE specialist-ruoli-diversi. **MAI**
   coder multipli sullo stesso artefatto.
3. **Numero**: 2 ≤ n ≤ cap_attuale (prior=4 coder-concorrenti, aggiornato con feedback locale).
4. **Costo netto positivo**: `tempo_seriale > (tempo_parallelo + costo_merge)`.

**Revocabilità**: la decisione iniziale è un'ipotesi. Se a runtime emergono dipendenze/conflitti, i
rami coinvolti si ri-serializzano. **Altrimenti** (qualsiasi condizione falsa) → **seriale
(single-orchestrator)** — che è il default.

---

## 5. RESIDUI ONESTI

1. **Conflitto semantico (red-team #3, CRITICA — il residuo più grave)**: worktree+lease+contratto
   bloccano collisioni-file e divergenze-dati, MA due agenti possono prendere decisioni architetturali
   incompatibili su aspetti **non contrattualizzati** (libreria scelta, pattern di errore, assunzione
   implicita) senza toccare lo stesso file. **Mitigato, non risolto**: il contract-test di P4 cattura
   solo ciò che è nel contratto; il resto emerge al merge/integration. Per un solo-dev, la mitigazione
   pratica è il cap basso (meno rami = meno superficie di conflitto semantico) + la review-umana al
   merge (human-gate di P1). **Onestà: il parallelismo di build resta più rischioso del seriale anche
   con tutta l'infra — per questo è l'eccezione, non il default.**
2. **Classificatore-9B fallibile (red-team #1)**: la stima `parallelizable_hypothesis` può sbagliare.
   Mitigato da revocabilità (§3.2) + escalation-Claude per ambigui, ma una stima sbagliata costa un
   ciclo (fan-out poi ri-serializzato). Costo accettato vs il rischio di fan-out cieco permanente.
3. **Feedback-loop del cap richiede dati**: il cap-bayesiano-aggiornabile ha bisogno di metriche
   accumulate; all'inizio è solo il prior=4. Diventa adattivo solo dopo N esecuzioni misurate.

---

## 6. GATE FALSIFICABILI (Symbiosis Law 7)

- **G1 — sequenziale→single** (binario): un task palesemente sequenziale (es. "refactor lineare di 1
  file", "fix con causa nota") DEVE essere routato a single-orchestrator dal gate, NON fan-outtato.
  Falsificabile: il route ritorna single, non la lista-dispatch. *(Oggi: sempre fan-out → fallisce.)*
- **G2 — revocabilità** (binario): se due rami paralleli chiedono lease sulla stessa hot-zone (dipendenza
  emersa), il monitor DEVE ri-serializzarli (uno aspetta). Falsificabile: il secondo lease-request
  blocca/attende invece di procedere cieco.
- **G3 — coder-stesso-artefatto vietato** (binario): un tentativo di fan-out di ≥2 agenti che editano lo
  stesso file/feature DEVE essere rifiutato dal gate (cond. 2). Falsificabile: il gate ritorna seriale.
- **G4 — costo netto** (numerico): il gate parallelizza solo se la stima `tempo_seriale > tempo_parallelo
  + costo_merge`. Falsificabile: con `costo_merge` alto (file sovrapposti), il gate sceglie seriale.
- **G5 — cap rispettato** (numerico, con caveat): coder-concorrenti ≤ cap_attuale (prior 4). Falsificabile:
  il N+1° fan-out di coder viene accodato, non lanciato. Cap aggiornabile, non fisso.

---

## 7. DECISIONE (kill gate)

**GO sul gate A1 revocabile** (`parallelizable_hypothesis` + monitor + ri-serializzazione), come da
proposta SOTA già groundata (2026-06-02-sota..., riga 81) ma con le 4 condizioni + revocabilità del
council. Riusa l'infra esistente (worktree+lease, ~80%). **Default = seriale**; fan-out = eccezione
gated.

**Inversione dichiarata**: l'enunciato "BUILD∥ default" è **respinto per il coding**. Il parallelismo di
build è l'eccezione (eccezione sicura solo con le 4 condizioni + contratto + cap basso). Per la
*ricerca* invece il fan-out resta il default (è il regime +90.2%).

**Metrica primaria falsificabile**: G1 — se un task sequenziale viene ancora fan-outtato (come oggi), il
gate non esiste e il pezzo ha fallito. Il delta misurabile: % task correttamente routati
(sequenziale→single, breadth→fan-out) vs il 100%-fan-out attuale.

**Residuo grave dichiarato**: il conflitto semantico (§5.1) non è risolto dall'isolamento-file — è la
ragione per cui il build-parallelo resta più rischioso del seriale e va tenuto raro.

---

## 8. Provenienza

- **Reuse-first**: Explore disk-state (claim load-bearing ri-verificati: `classify_node:222` non emette
  flag, `route_after_checkpoint:462` fan-out incondizionato — confermato). agent_start.py 908,
  agent_lease.py 644, federation_orchestrator.py 576. Memory importance-8.
- **Evidenza SOTA**: già catturata in `research/operations/2026-06-02-sota-multiagent-orchestration.md`
  (136 righe, VERIFICATA): Google 2512.08296 (ceiling 3-4, −70% sequential), proposta A1 riga 81. NON
  ri-fatta deep-research (già groundato + 15+ paper della ricerca-madre).
- **Council 2-LLM asimmetrico** (calibrato):
  - Red-team: **Gemini 3.1 Pro** — 6 difetti, 2 CRITICA (decisione-a-ignoranza, isolamento-fisico-vs-
    semantico). Premiato per distruggere.
  - Logic: **DeepSeek V4 Pro** (`reasoning_effort=high`) — scioglie #2 (revocabilità), #4/#6 (prior
    bayesiano), #5 (componibilità/merge-cost); riconcilia desiderio-vs-evidenza (falsa contraddizione,
    tipi di parallelismo). La formulazione del gate (§4) è sua.
- **Famiglia**: P4 (contract-test al merge cattura la divergenza dei rami paralleli; blast-radius =
  stima dell'indipendenza). P3 (worktree isolato è anche il substrato del build-parallelo). P1
  (human-gate al merge = ultima difesa sul conflitto semantico). Cicatrici W62/W59/W50 (i danni del
  parallelismo che l'infra esistente già mitiga).

> **Onestà finale**: il pezzo NON rende il build-parallelo "il default veloce". Lo rende **l'eccezione
> gestita**: il default è seriale (l'evidenza lo impone per il coding), il fan-out è gated da 4
> condizioni + revocabile + cap-basso, e resta più rischioso del seriale a causa del conflitto
> semantico irriducibile (§5.1). Il guadagno reale non è "tutto in parallelo" — è **smettere di
> fan-outtare lavoro sequenziale** (il −70% che paghiamo oggi facendo sempre fan-out). "Velocità
> siderale" per il coding viene dal NON parallelizzare ciò che non si deve, non dal parallelizzare
> tutto.
