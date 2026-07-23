---
title: WR2 Editorial Intelligence — design accurato (dal disco-rotto al planner editoriale)
date: 2026-07-21
status: SPEC v1.1 — §8 brand decisions RATIFIED by Zero 2026-07-21 (all 4 as recommended); Phase 1 (Mossa A) SHIPPED #2942 + replay gate PASSED (61/61 first-try, 0 fail, 11/11 kinds, 100% family-resolution)
mandate: Zero — "come diamo alla WR2 una intelligenza editoriale tale, e non un disco rotto che ripete schemi fissi" + "disegnamolo con accuratezza e vediamo se altri sistemi nel mondo possiamo vedere il loro codice"
method: session architect (Fable) + 3 seat che hanno LETTO IL CODICE REALE (repo clonati, commit SHA, file:line) + 2 red-team indipendenti (Sonnet con accesso-repo & DB-live; Kimi K3 cross-family)
grounded_by: WR2 file:line VERIFICATI su disco 2026-07-21 (ri-letti da un secondo grader + query sul DB live); STORM/gpt-researcher/gpt-newspaper/instructor/outlines/pydantic codice reale letto
---

## 0. La diagnosi accurata (VERIFICATA su disco + DB live, da due letture indipendenti)

Il "disco rotto" non è un difetto di scrittura del modello. È che **una sola chiamata** decide
tutto insieme — register, arco, spina, copy di ogni slide, prompt immagini — e a valle il contratto
dati è **una sola forma piatta**. Sotto quella pressione un modello collassa sul pattern più vicino.
Quattro fatti dal codice WR2, ognuno ri-verificato da un secondo grader questo turno (§7):

1. **Il contratto slide è UNA forma piatta.** `_normalise_slides` (`wr2_draft_generator.py:1417`,
   dict costruito a `:1441-1453`) appiattisce OGNI slide in `{slide_number, slide_type(str libera,
default "body" a `:1443`), is_cover, is_hero_image, headline[:80], subhead, body[:500],
image_prompt, tonal_palette, image_mode, image_url}`. Grep dell'intero file per
   `list_items`/`qa_pairs`/`timeline_events`/`stat_value` = **zero hit**: nessuna struttura tipizzata
   per-forma. Timeline, dialogo, fact-stack, stat-card possono solo diventare `body` in prosa.

2. **Il renderer ha 15 layout, il produttore AUTONOMO ne raggiunge 4.** `RENDERABLE_FAMILIES`
   (`composer.py:51-67`) = **15 famiglie** reali e skeletonate (incl. qa-dialogue, timeline-pinboard,
   dark-status-list, evidence-carved, source-citation, stat-card-hero, numbered-forces-list,
   elegant-close). Ma `map_slide_to_family` (`composer.py:112-172`) senza pin esplicito ha solo 4
   `return` raggiungibili: `cover-photo` (`:147`), `editorial-text` (`:163`,`:172`), `statement-bomb`
   (`:164`), `photo-headline-yellow-sub` (`:166`). Le altre 11 solo via pin `layout_family` esplicito
   (`:143-145`), e grep di `wr2_draft_generator.py` per `layout_family` = **zero hit**. **Prova sul DB
   live**: `topic_type_log` ultimi 60gg → `{null: 46, "cover-photo": 1}` — 46/47 righe (97.9%) senza
   alcun segnale layout: il branch-pin è codice morto nel produttore autonomo.
   → **NUANCE (dal 2° grader, RAFFORZA il claim):** le 11 famiglie NON sono morte system-wide. Il path
   **manuale/interattivo** (`wr2-storyboarder`, `composer.py:996-1060`) emette GIÀ `list_items`/`events`/
   `qa_pairs` + pin `layout_family` e pilota tutte e 15. Quindi il buco è **specifico del produttore
   autonomo** (quello che fa il volume quotidiano ~1/giorno), e **la forma tipizzata che serve a Move A
   ESISTE GIÀ internamente** — Move A PORTA una forma provata sul path manuale, non ne inventa una nuova.

3. **Una sola chiamata monolitica.** `claude_compose_slides` (`:1071-1097`, singolo `complete_async`,
   `model="claude-opus-4-7"`) è chiamata una volta per tentativo dentro il loop di `_process_one`
   (`:1835-1852`). Il commento del codice stesso (`:1838-1841`) lo dichiara: _"composes brief+storyboard
   in one shot, not two"_. Register + tutti i copy delle slide escono da QUELLA chiamata.

4. **L'unico asse con stato è l'unico che varia** (register/image-mode via `topic_type_log`).

**Il framing accurato**: l'intelligenza non manca al renderer (15 layout, il produttore autonomo ne
usa 4). Manca al **contratto di generazione autonomo**, che sa dire una sola frase piatta. Il redesign
APOA che colpisce Zero usa timeline, triad, label:value, statement, cover, photo-panel, CTA — **tutte
famiglie che il nostro renderer già possiede e che il path manuale già pilota**. Quel livello è
raggiungibile col renderer di oggi, SE il produttore autonomo sapesse produrre contenuto strutturato
e decidere la struttura a monte.

---

## 1. Che i migliori del mondo fanno ESATTAMENTE questo — provato leggendo il loro codice

Tre seat hanno clonato e letto il sorgente reale (non nominato — letto). L'accordo è cross-family
(W100: l'accordo mente quando è same-family; questo è l'opposto).

**Stanford STORM** (`stanford-oval/storm`, MIT, commit `fb951af7`) — il planner→writer di
riferimento in produzione:

- L'outline è generato SENZA prosa e parsato in un albero di `ArticleSectionNode`
  (`interface.py:136-159`); **`content=None` è lo stato esplicito "non ancora scritto"**
  (`storm_dataclass.py::from_outline_str:437-474`).
- Il writer (`article_generation.py::generate_article:53-133`) per ogni sezione affetta l'outline
  al SOLO sottoalbero di quella sezione — **non vede mai le sorelle** (né outline né prosa).
- Scrittura in **parallelo reale** (`ThreadPoolExecutor(max_workers=10)`), merge finale a **zero LLM**.
- Decoupling così forte da **sopravvivere al confine di processo**: l'outline è persistito su
  `storm_gen_outline.txt` e ricaricabile in un'invocazione CLI separata (`engine.py:341-441`).

**gpt-researcher** (`assafelovic/gpt-researcher`, Apache-2.0, `5d84d2f5`):
`EditorAgent.plan_research` (`editor.py:22-50`) emette un outline JSON piatto `{title, sections}`
senza prosa; `WriterAgent.write_sections` (`writer.py:32-71`) ha il **divieto esplicito di
riscrivere i corpi** — scrive solo titolo/TOC/intro/conclusione attorno alle sezioni già finite.

> **Contratto minimo, ridotto all'essenza (STORM+gpt-researcher):**
> `plan(context) → lista_ordinata[slot]` (nessuna prosa) → per ogni slot IN PARALLELO
> `write(slot, contesto_ristretto_allo_slot, frame_condiviso) → content` → `merge` stupido.

**gpt-newspaper** (`assafelovic/gpt-newspaper`, `b86aff2d`) — letto come **monito**: il suo
critic-loop è un `if response == 'None'` (string-equality sull'output grezzo, `critique.py:28`),
**senza cap sul numero di giri** — un critico confuso cicla all'infinito. La nostra loop DEVE avere
il cap (già lo abbiamo nel kicker-guard) e check su CONTENUTO/entità, non su string-match.

**Verdetto framework (provato dal codice, non opinione):** LangGraph/CrewAI sono cablaggio-archi
sottile — in gpt-newspaper il 100% della logica vive in classi plain-Python `run()`, il grafo è 4
`add_edge`. Adottare un framework **RE-CENTRALIZZEREBBE lo stato in-process**, regredendo la
durabilità launchd+Postgres che WR2 già ha → esattamente la famiglia-scar #2 "esiste≠armato". **Si
adotta la FORMA (planner/writer, critic-gated loop, check-deterministico-prima-del-giudizio-LLM),
si rifiuta il framework.**

---

## 2. Il design — 5 mosse + un critico sdoppiato (ognuna shippabile, l'ordine de-rischia)

### Mossa A — Carousel IR: la grammatica tipizzata delle slide ★ fondamento, sblocca le 11 famiglie nel produttore autonomo

Unione discriminata di ~8 forme-slide, ognuna mappata a famiglie che GIÀ abbiamo — **e la forma
strutturata esiste già sul path manuale** (`composer.py:996-1060`: `list_items`/`events`/`qa_pairs`),
quindi è un PORT, non un'invenzione. Enforcement = **validate + retry sul JSON grezzo del CLI**
(pattern instructor, SENZA SDK Anthropic — provato eseguendo la forma WR2 a 7 slide contro pydantic
2.13.4). Ricetta reale, portata verbatim da `instructor/v2/core/json.py` (MIT) + `pydantic
Field(discriminator=...)`:

```python
# forme (estratto — 8 kind totali)
class FactStackSlide(BaseModel):
    kind: Literal["fact_stack"]; heading: str; facts: List[str]
class TimelineSlide(BaseModel):
    kind: Literal["timeline"]; heading: str; steps: List[str]
Slide = Annotated[Union[ProseSlide, StatementSlide, FactStackSlide, QaDialogueSlide,
    StatusListSlide, TimelineSlide, StatCardSlide, CtaSlide], Field(discriminator="kind")]
SlideList = TypeAdapter(List[Slide])

def generate_slides(prompt, max_retries=3) -> List[Slide]:
    ctx = prompt
    for attempt in range(1, max_retries+1):
        raw = call_claude_cli(ctx)                       # nostro path OAuth, mai SDK
        json_str = extract_json_from_codeblock(raw)      # port MIT da instructor
        try:
            return SlideList.validate_json(json_str)     # SUCCESS
        except (ValidationError, json.JSONDecodeError) as e:
            if attempt == max_retries: raise             # → fallback tipizzato, NON coerce-a-prosa
            ctx = f"{prompt}\n\nValidation errors:\n{e}\nFix them; previous attempt:\n{raw}"
```

| kind                      | campi               | famiglia renderer già esistente               |
| ------------------------- | ------------------- | --------------------------------------------- |
| cover / prose / statement | (come oggi)         | cover-photo / editorial-text / statement-bomb |
| fact_stack `rows[]`       | label,value         | **evidence-carved**                           |
| status_list `items[]`     | heading,items,hot[] | **dark-status-list**                          |
| timeline `steps[]`        | date,event,current  | **timeline-pinboard**                         |
| triad `items[3]`          | title,desc          | **numbered-forces-list**                      |
| qa `pairs[]`              | q,a                 | **qa-dialogue**                               |
| stat                      | value,unit,context  | **stat-card-hero**                            |
| citation                  | claim,sources[]     | **source-citation**                           |

**VALIDAZIONE LENIENT-FIRST (correzione red-team BLOCKER-1, §7).** Il normalizzatore di oggi è
_coercitivo_ (tronca `[:80]`/`[:500]`, defaulta, non alza MAI su un campo storto) — ed è quello che
tiene il fail-rate basso (**2 parse_error / 125 draft storici = 1.6%**, e oggi sono hard-fail a zero
retry). Una discriminated-union _stretta_ alza `ValidationError` su un solo enum sbagliato → rischio
concreto di spike di regen che brucia quota MAX allo shakeout. Quindi la validazione è a due livelli:
**stretta SOLO sul discriminatore `kind` + i campi obbligatori-per-kind**; **lenient (coerce/tronca/
default, come oggi) su tutto il resto scalare**. E l'end-state a retry esausto è **esplicito**: NON
"coerce a un kind semplice" (obiezione Kimi #3: i kind-fallback sono sempre i semplici → ri-collasso
sui 4 layout dalla porta di servizio), ma **park del deck** (facts-first park backstop già esistente)
oppure fill minimale che **PRESERVA il `kind` pianificato**. Budget CLI **per-deck bounded** (guardia
finestra-cron: planner + N-writer × retry può esplodere — vedi §5). **Caveat onesto**: la costrizione
grammar-level FSM (outlines) è impossibile col CLI (serve accesso ai logit token-per-token) — noi
possiamo solo validate+retry sul testo finito. È sufficiente. Questa mossa cura anche i finding Codex
C/D (fact-extractor su dialetto sbagliato; language-gate cieca ai campi ricchi) via projection
condivise `reader_texts()`/`claim_bearing_segments()`.

### Mossa B — Planner → Writer: separare DECIDERE da SCRIVERE ★ il cuore anti-disco-rotto

Il monolite diventa DUE stadi, esattamente la forma STORM/gpt-researcher:

- **Planner ("l'editor")** — input: brief + liveness-tier + tema + Creative Ledger. Output: un PIANO
  piccolo, JSON, ZERO prosa, modellato sull'outline-object provato (STORM `content=None` +
  gpt-researcher flat list):
  ```json
  {
    "spine": "...",
    "arc": "news_alert",
    "slides": [
      {
        "slot_id": 1,
        "role": "hook",
        "kind": "cover",
        "heading_intent": "...",
        "bullet_promise_n": null,
        "body": null,
        "hero": true
      },
      {
        "slot_id": 3,
        "role": "discovery",
        "kind": "triad",
        "heading_intent": "3 conditions",
        "bullet_promise_n": 3,
        "body": null,
        "hero": false
      }
    ]
  }
  ```
  **CHI PROPONE ≠ CHI DISPONE (correzione red-team cross-family Kimi, obiezione #1 — §7).** L'arco è
  la decisione PIÙ content-dipendente del deck: metterla in codice cieco al contenuto è l'errore. Quindi:
  il **CODICE PROPONE** priori — pesi + **penalità di cooldown SOFT** dal Ledger — e il **planner-LLM
  DISPONE**, sceglie l'arco DAL CONTENUTO dentro quei vincoli. Un content-override esplicito è lecito:
  una settimana genuinamente breaking (cascata PMK/Omnibus) può ri-scegliere `news_alert` due giorni di
  fila — è un **repeat GIUSTIFICATO**, loggato come tale, non una violazione. **Maschere HARD solo sugli
  assi di SUPERFICIE** dove il contenuto è indifferente (palette, kicker, subhead-pattern, register).
  Mai una maschera hard che forzi un arco sbagliato su una storia che ne chiede un altro.
- **Writer ("il redattore")** — riceve brief + piano bloccato + il proprio slot, **PIÙ gli
  `heading_intent` delle slide sorelle** (non il loro copy — abbastanza per ritmo, callback,
  escalation; non abbastanza per riscriverle). Correzione red-team obiezione Kimi #2: col writer
  slot-cieco puro (STORM stretto) **nessuno possiede la continuità di voce** e il deck resta monotono
  all'orecchio anche con layout vari. Le teste-vicine danno un proprietario alla voce cross-slide.
  Riempie il copy tipizzato; `body=null → content`. Parallelizzabile per-slot.

Beneficio provato da STORM: il critico può **rigenerare la singola slide** invece dell'intero
carosello (cura diretta degli scar bullet-promise/closer di WR2). Il "take = Our read" muore: l'angolo
è dimensione di prima classe che ruota.

### Mossa C — La Spina come campo di prima classe ★ l'insight APOA

`spine` = idea-guida scelta UNA VOLTA dal planner, con **check falsificabile**: il closer echeggia la
spina del cover? Un disco rotto non passa — non HA una spina. **Il check è ENTITÀ/INTENTO, mai
bare-substring** (scar #3, sotto): l'"echo" si misura su chiave-fatto/entità condivisa, non su
sotto-stringa letterale.

### Mossa D — Creative Ledger: memoria editoriale come stato interrogabile — E CHIUSO SUL RISULTATO

Generalizzare il lookback register a TUTTI gli assi. Una riga/draft: `(spine_gist, arc_id, hook_type,
kicker, subhead_pattern, layout_families[], register, palette, hero_concept_class)`. Il planner deriva
cooldown per-asse (soft su arco, hard sugli assi di superficie). "Non ripetere" diventa una query. La
cura kicker (#2873) è il PRIMO asse; il ledger la generalizza.

- **CHIUSO SUL RISULTATO (correzione Kimi #1 — open-loop):** il ledger registra anche l'ESITO —
  pubblicato (atto Legge-5 dell'umano) / parked / metriche IG — non solo "draftato". Senza segnale di
  reward è un indice-dedup, non memoria: non imparerebbe mai che i deck `deadline` sono quelli che Zero
  pubblica. Il reward si aggancia al loop metriche IG già esistente (§WR2 corner).
- **BACKFILL degli assi nuovi (correzione Sonnet BLOCKER-2):** `spine_gist`/`arc_id`/`hook_type` NON
  esistevano quando i 34 deck furono fatti. Il backfill è un **pass di labeling LLM** che
  reverse-engineerizza arco/spina dal copy finito, **con QA a campione umano** (è un task fuzzy, ha il
  suo error-rate) — budgettato dentro lo step-4, NON dato per scontato. **Cold-start esplicito:** finché
  il ledger è rado (primi ~20 deck) i cooldown sono soft/quasi-uniformi; è accettabile (uniforme È vario)
  ma va detto, non nascosto.

### Mossa E — Arc Grammar: archi come libreria combinatoria scelta per tema+liveness

`news_alert`, `myth_buster`, `deadline`, `worked_example`… ogni arco = sequenza di ruoli; ogni ruolo
→ famiglie con alternate. Breaking → arco stretto 5-6; evergreen → arco ricco 9. È QUESTO che fa
"adattare al momento e al tema". L'arco 33/33 identico muore. **Nota (Sonnet MAJOR-4):** 4 archi sono
POCHI per un cooldown domain-partizionato (`fetch_recent_same_domain` è domain-scoped) — la libreria va
ampliata a ~6-8 archi prima che il cooldown sull'asse-arco abbia margine, altrimenti l'escape "proceed
anyway (WARN)" scatta spesso proprio sull'arco.

### Il Critico — SDOPPIATO (correzione dal codice reale) + DISCIPLINA GUARD-CONFORMANCE

Dal `run_overseer_checks.js` di `Maazsiddiqui01/linkedin-carousel-generator` (MIT, `f5963e99`):
un critico editoriale COMPLETO costruibile a **zero LLM** quando i difetti sono strutturalmente
verificabili. Due strati, il primo gratis:

1. **Pre-gate deterministico ($0, 0ms, PRIMA del critico costoso)** — pattern reali: Jaccard
   anti-duplicati (`:41-52`), bullet-count/ceiling (`:118-132`), CTA-presence, coverage ratio
   (`:221-237`), sequenza-chip (`:265-286`). Da noi: closer-echeggia-spina, bullet-promise
   (heading "TRE"→3 bullet), nessun body caps-wall, ogni slide ha un `kind`, kicker-unico (già
   half-fatto, `_kicker_collision:668`).
   **⚠️ SCAR #3 — ogni guardia deterministica È una nuova istanza della famiglia più recidiva
   dell'organismo (guard over/under-match: W68/W72/W73/W82/W83/W84/W85/W91/W92/W94/W95/W99, 8+ volte).
   REQUISITO HARD (Sonnet MAJOR-3, non negoziabile): NESSUN gate ship senza corpus guilt+innocence
   registrato in `infra/guard-conformance/registry.json` + CI `guard-conformance.yml`.** Il Jaccard
   normalizza VIA il boilerplate legale indonesiano (strip token `Pasal/ayat/berdasarkan…`) PRIMA della
   similarità, o falsa-positiva su ogni contenuto regolatorio (obiezione Kimi #3). "closer echeggia
   spina" = match su entità/chiave-fatto, MAI sotto-stringa.
2. **Giudizio LLM (wr2-critic) solo sul soggettivo** — tono, forza narrativa, brand-voice — dopo che
   il pre-gate ha già bocciato il verificabile a costo zero. E con **cap sui giri** (monito
   gpt-newspaper: il loro non ce l'ha e può ciclare all'infinito). **Limite dichiarato (Kimi #2 +
   Sonnet MINOR-8):** il critico LLM è same-family del generatore → indipendenza di CONTESTO, non di
   GIUDIZIO. Il vero sensore di taste resta l'umano a `drafted` + le metriche IG; il critico LLM non
   "chiude" da solo l'asse-gusto.

---

## 3. Sequenza di rollout (ognuna vale da sola; l'ordine de-rischia)

1. **IR tipizzata + projection condivise** (A) — sblocca 11 layout nel produttore autonomo, è il
   contratto che regge tutto. Shadow-mode + replay dei 34 deck storici, con un **GATE ESPLICITO:
   misurare il fail-rate della validazione stretta sul replay PRIMA del cutover** (Sonnet BLOCKER-1);
   se lo spike è reale si tara la lenient-first / il fallback prima di andare live.
2. **Pre-gate deterministico** (Critico strato-1) — cheap, indipendente, valore immediato; ogni gate
   con corpus guilt+innocence (guard-conformance) fin dal primo.
3. **Planner/Writer dual-run** (B) — shadow accanto al monolite, poi cutover. **Il planner porta i
   campi `spine`/`arc` GIÀ da qui (shape inerte)** così lo step-4 li ATTIVA senza ri-tagliare il
   planner (Sonnet MAJOR-5: risolve la dipendenza step3↔step4).
4. **Spine + Ledger + Arc** (C/D/E) sopra il planner — attiva enforcement spina + selezione
   arco-da-contenuto + backfill LLM con QA.
5. **Critico narrativo LLM** (strato-2) con cap.
   Metrics-gated: il bandit sui pesi del planner è un lever a **~6+ mesi** (n≥200 a ~1/giorno — misurato:
   `topic_type_log` 47 righe / 45gg ≈ 1.04/giorno), NON near-term. Non è il motore della varietà iniziale.

## 4. Cosa NON toccare (load-bearing, verificato)

- Il renderer + i 15 layout: NON è la malattia, è la cura già costruita. Adattare il contratto, non
  il CSS. — Facts-first + park (scar fondante; è ANCHE l'end-state del retry esausto). — Generator≠grader
  (planner/writer/critico seat separati). — Legge 5 (stop a `drafted`). — Ban SDK Anthropic (l'IR valida
  sulla stringa CLI). — **Niente framework** (LangGraph/CrewAI regredirebbero la durabilità
  launchd+Postgres; provato dal codice di gpt-newspaper). — **INVARIANTE PERSISTENZA (Sonnet MINOR-7,
  requisito hard):** piano-planner + Creative Ledger vivono in **Postgres**, mai stato in-process
  mid-request; nessuna "cache di efficienza" in-memory che un futuro ingegnere sarebbe tentato di
  aggiungere — sarebbe la scar #2 di ritorno.

## 5. Tradeoff onesto (con i numeri, non a mano)

Più stadi = più chiamate/latenza. **Sizing (Sonnet MAJOR-6):** oggi worst-case
`MAX_DRAFTS_PER_RUN=2` × 3 tentativi × 1 call = **6 call OAuth/run**. Domani planner + 8 writer × 3
tentativi × 2 draft = fino a **~54 call/run (~9×)**, ognuna col timeout 300s (`:1092`) → rischio
finestra-rolling-5h del MAX plan. NON fatale a 1/giorno, ma **va bounded**: cap retry per-slot (≤2),
cap budget-call per-deck, writer paralleli ma contati contro quota. È l'UNICO modo per cui la varietà
smette di essere una richiesta nel prompt e diventa proprietà strutturale verificabile PRIMA del render.

**Rischio-madre onesto (Goodhart — Kimi #2):** l'entropia-layout è un PROXY. Il bersaglio vero è la
varietà _percepita dal lettore_, che vive nell'angolo/voce, non solo nei layout. Le mosse strutturali
sono **necessarie-non-sufficienti**: l'asse-gusto è posseduto da (a) arco scelto-dal-contenuto, (b)
continuità-di-voce via heading-sorelle, (c) il loop umano-pubblica + metriche-IG come reward. Se
misuriamo solo "12/15 layout usati" e l'engagement resta piatto, abbiamo Goodhartato il proxy. Il
successo si dichiara sull'esito IG + sul tasso-di-riscrittura-umana a `drafted`, non sull'entropia.

## 6. Provenienza codice reale (3 seat, tutto clonato + letto — report grezzi archiviati come sibling)

- STORM `fb951af7` + gpt-researcher `5d84d2f5` → `2026-07-21-oss-code-reading-storm-gptresearcher.md` (766 righe)
- gpt-newspaper `b86aff2d` + crewAI-examples `da94a91e` + linkedin-carousel-gen `f5963e99` →
  `2026-07-21-oss-code-reading-statemachine-gptnewspaper.md` (240 righe)
- instructor `47fdb2c` + outlines `cb095ba` + pydantic 2.13.4 (eseguito) + BAML `be5e7cd` →
  `2026-07-21-oss-code-reading-typed-pydantic-instructor.md` (673 righe)

## 7. Red-team — 2 grader INDIPENDENTI (generator≠grader; io ho scritto, loro hanno gradato)

- **Grader 1 — Sonnet 5, accesso-repo + DB live.** Verdetto **SHIP-WITH-FIXES**. Ha ri-letto e
  CONFERMATO tutti e 4 i claim file:line (con query Postgres: 46/47 righe recenti senza segnale layout)
  e aggiunto la nuance §0.2 (path manuale già tipizzato). Fix pretesi e INTEGRATI: BLOCKER-1
  (lenient-first + gate fail-rate su replay + fallback kind-preserving, §Mossa-A/§3.1), BLOCKER-2
  (backfill LLM+QA + cold-start, §Mossa-D), MAJOR-3 (guard-conformance corpus, §Critico), MAJOR-4 (arco
  library ~6-8, §Mossa-E), MAJOR-5 (spine-shape dallo step-3, §3.3), MAJOR-6 (sizing 9×, §5), MINOR-7
  (invariante Postgres, §4), MINOR-8 (limite taste, §Critico/§5).
- **Grader 2 — Kimi K3, cross-family, design-only.** Verdetto **FLAWED-ma-salvabile** ("chassis sano,
  teoria editoriale da correggere"). 3 obiezioni, tutte INTEGRATE: #1 selezione-assi content-blind +
  ledger open-loop (→ chi-propone≠chi-dispone §Mossa-B + ledger chiuso §Mossa-D), #2 Goodhart/taste +
  voce cross-slide senza proprietario (→ heading-sorelle §Mossa-B + rischio-madre §5), #3 retry→fallback
  ri-collassa + Jaccard sul boilerplate (→ fallback kind-preserving §Mossa-A + normalizzazione Jaccard
  §Critico).
- **Convergenza** dei due grader (seat diversi, accessi diversi): stesso nucleo su taste-vs-struttura e
  su retry-fallback → alta confidenza che sono i punti veri, non rumore di un singolo seat.

## 8. Decisioni Zero-gated (Legge 5 — la sessione NON le prende; sono di brand/costituzione)

Il BUILD parte solo dopo ratifica di questi (più i 3 pre-build gate: fail-rate-replay, guilt+innocence
corpus, sizing-quota):

> **RATIFIED by Zero, 2026-07-21 — all 4 as recommended:**
>
> 1. **Arc library = the 7-slate**: `news_alert`, `deadline`, `myth_buster`, `worked_example`,
>    `comparison`, `explainer`, `status_roundup`. Breaking topics → tight 5-6 slide decks via arcs 1/2;
>    evergreen topics → rich 8-9 slide decks via arcs 4/6.
> 2. **Caps only on headings, never on bodies.**
> 3. **"The Bali Zero read"** = recurring CLOSER slot-franchise.
> 4. **Palette rotation per DOMAIN**: immigration = carbon `#373D42` + yellow `#F4C430` ·
>    tax = carbon + red `#C8102E` · company/KBLI = black + yellow · property = paper/cream + carbon ·
>    breaking = red-forward.

Opzioni originali valutate (record storico, mantenute sotto per riferimento):

1. La libreria degli **archi** (quali 6-8, e le loro sequenze di ruoli) — è voce editoriale/brand.
2. La regola **"caps solo su heading, mai sui body"** (già matura, Zero-gated).
3. Lo slot-franchise **"The Bali Zero read"** come ruolo ricorrente d'apertura/chiusura.
4. La **rotazione palette per tema**.
   Tutto il resto (IR tipizzata, planner/writer, ledger, pre-gate deterministico) è ingegneria interna,
   non tocca ciò che esce su IG finché Zero non pubblica.
