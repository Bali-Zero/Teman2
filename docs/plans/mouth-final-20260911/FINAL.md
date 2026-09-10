# FINAL — spec convergente «motore e design», 2026-09-11

Consegna unica per Zero, richiesta il 2026-09-11 alle due sessioni (Fable topic 5 su Mini,
Astra sessione Website). Solo documenti: nessun codice applicativo, nessuna finestra
aperta, nessuna release. Le ruling M e D restano di Zero e vanno registrate nel testo
di lancio, mai dedotte dal silenzio.

## 1. Provenienza

| Fonte                                                           | Dove                                                                                                                                                                                                                                                                                                                                            | Identità                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| --------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pacchetto Astra (README, LAUNCH, W0–W7, verbale, manifest)      | questa directory, copiato dal worktree Mini `docs-mouth-final-windows-20260911` (untracked, mai committato da Astra)                                                                                                                                                                                                                            | README `073e57ded13d` · LAUNCH `77baf4451c74` · W0 `ae3f0ae9c664` · W2 `1e4da8ed13f7` · W7 `3fd0bc92d869` (sha256, prefisso 12); file esclusi dalla copia (per peso, più tre file di evidenza non portanti — `canonical-article-observation.json`, `secondhome-f7-report.md`, `package-files.json` — tolti per tenere il churn sotto il floor gear 3) elencati con hash in `evidence/EXCLUDED-FILES.sha256`; restano leggibili nel worktree Astra e nel kit Desktop |
| Mappa design Fable (topic 5)                                    | PR #6124, `research/design/2026-09-11-r19-design-reuse-map-apps-mouth.md`, head `cdfe4a3d26`                                                                                                                                                                                                                                                    | refutata da Codex, 20 finding, 18 applicati, 2 parziali                                                                                                                                                                                                                                                                                                                                                                                                             |
| Spec Studio concorrente (W1–W6, stessa lineage)                 | worktree `docs-studio-engine-design-final-20260911`, base `2ee842d045`                                                                                                                                                                                                                                                                          | assorbita dal pacchetto Astra, che la riusa integralmente                                                                                                                                                                                                                                                                                                                                                                                                           |
| Spec finestra motore topic 3 (nuzantara-c8), **v6.2 CONVERGED** | `research/visa/2026-09-11-oracle-final-window-spec.md` nel worktree `mouth-visa-review-reason-audit-20260911`, branch `agent/mini-pro2/mouth/visa-review-reason-audit-20260911` — file NON committato, lo committa la PR-O0 della finestra; copia nel kit Desktop Mini `~/Desktop/w-oracle-launch-20260911/03-SPEC-oracle-final-window-v6.2.md` | sha256 `2acb148ea72fec9bf34d2022c03e1d9883fa557ba8b1f4ff0ff736f697e7c9d5`; tre round Astra + panel Gemini/Kimi (Qwen TP1 in 403); census = replay OFFLINE del comportamento pubblico sul pack seq-20 v2026.9.6 (audit README: non traffico reale), 67 cammini → 55 / 10 / 2 senza flag, 31 / 7 / 0 / 29 con i flag reali; la prova live è una sonda sintetica separata                                                                                              |
| Decisioni di Zero D1–D6 + M                                     | `~/Desktop/w-oracle-launch-20260911/02-DECISIONI-ZERO.md` (Mini, fuori repo; compilato da topic 3 (sessione `nuzantara-c8`, Fable 5.1: l'intestazione del file dice «Compilato da Fable 5.1») su delega esplicita di Zero, 2026-09-11 ~04:10 WITA; Zero può sovrascrivere ogni riga)                                                            | la finestra Oracle lo rilegge prima di ogni PR; una decisione non scritta è MANCANTE                                                                                                                                                                                                                                                                                                                                                                                |
| Kit di lancio sul Desktop del Mini                              | `~/Desktop/w-oracle-launch-20260911/` (topic 3: `00-LEGGIMI`, prompt W-ORACLE, decisioni, spec v6.2, copia pacchetto Astra, audit, panel, prompt W2) + `08-WEBSITE-ADDENDUM-topic5.md` (questo lotto: D4, addendum W2, prompt W7, coda)                                                                                                         | fuori repo, effimero; la fonte durevole è questa directory su main                                                                                                                                                                                                                                                                                                                                                                                                  |
| Risposta Fable ad Astra (decisioni e dissensi)                  | `/tmp/mouth-final-spec-20260911/fable-reply.md` (Mini)                                                                                                                                                                                                                                                                                          | riportata in §3                                                                                                                                                                                                                                                                                                                                                                                                                                                     |

Nota: il pacchetto Astra vive nel worktree di Astra `docs-mouth-final-windows-20260911` (path
citato dai prompt); questa copia e `FINAL.md` vivono nel worktree `docs-mouth-final-spec-20260911`
e poi su main. Il blocco «Stato della consegna» del README Astra (head `d23454ce`, rosso per
brief mancante) è SUPERATO da §7.

## 2. Decisioni già convergenti (non richiedono Zero)

- **Sito**: `apps/mouth` unico live; `apps/website` (R19) archiviato, letto solo con
  `git show` dal ref integrato `6603d2913e`; la patch di quarantena non si applica mai.
- **Fonte visuale**: R19 Direction A del 09-09 (carta `#F7F4EE`, slate `#233D52`,
  copper `#A44B36`, Fraunces/Manrope). Lo strato forest/Georgia è provenienza storica.
- **Funnel congelati**: Visa Oracle conserva canopy/gold, light/dark e quattro stati
  distinti; Second Home conserva Merah Putih e IDR in Cormorant tabular. Nessun re-skin
  dei funnel in questo programma; l'atlas Oracle e il fork Studio di R19 non si importano.
- **Roster**: home = `/` (`(marketing)/page.tsx`) con i soli founder Zainal e Heru, `/v2`
  invariata (SocialProof opt-in dalla home); Faysha/Faisha e Sahira fuori dalle
  pagine pubbliche (istruzione già data); Kadek, Rina e la voce «Zero» restano.
  L'esclusione si applica nei tre consumer di `rosterBySlug` (team, SocialProof, about):
  `publicListed:false` da solo filtra soltanto il book.
- **Scheduler unico**: le W0–W7 del pacchetto Astra. Le wave A–D della mappa Fable vi
  sono ripiegate (W2 ≈ team, W7 ≈ chrome/accenti, W4/W5 ≈ body, W6 ≈ KBLI; la wave C
  «re-skin funnel» decade). Massimo due finestre operative alla volta.
- **Gate comuni**: quelli del README del pacchetto (baseline sul commit servito,
  sitemap come insieme di URL, contrasti computati, Lighthouse mediana di 3 con LCP
  ≤ +5 % e CLS mai in aumento, font +≤120 KB per route e ≤60 KB per subset, diff di
  scope verificato a mano, gate fresco fuori catena, release solo dal release owner).
- **Formato**: ogni finestra è un mandato a sette sezioni
  (`.claude/skills/modus/battle-window-spec.md`), missione `SHWEB-20260911`, BLUE di
  default, worktree nuovo da `origin/main` per ogni lotto, branch read-only dopo l'arming.

## 3. Il dissenso sull'Oracle e come si è chiuso

Astra W0 vieta ogni «modifica di stato/precedenza». La finestra motore di topic 3
include, oltre alla copy EN/ID dei 29 codici oggi senza testo (9 con copy su 38) e all'aggiornamento del live
state, una modifica a `flow.ts`: far porre la domanda `family_sponsor_confirmed` anche
sui rami `retirement/property` e `retirement/undecided`, chiudendo i 2 dead-end
residui del census. Non tocca precedenza dei verdetti, schema, emitter né pack: rende
chiedibile un fatto già esistente su due rami.

**Chiusura (topic 3, 2026-09-11):** W0 di Astra COINCIDE con il nucleo (copy EN/ID +
inventario da tutti gli stage/emitter + renderer) e viene ESTESA, non sostituita. La
finestra motore è una sola, `W-ORACLE`, di topic 3, con cinque PR in quest'ordine:
PR-O0 copia il CONTENUTO del branch audit in un worktree nuovo da main e lo committa (nessuna
ripresa del branch, come vuole W0 §1) + live-state (PR-3/PR-5 mai appese); PR-O1 census con i
flag reali come baseline PRIMA di toccare l'intervista + script inventario; PR-O2 = W0
copy; PR-O3 `flow.ts` chiede `family_sponsor_confirmed` sui due rami (allowlist vuota,
delta misurato, test negativo sui cammini non toccati); PR-O4 «spiega la causa» +
fallback neutro del pannello contatto. La PR sui `missing_facts` sotto
HUMAN_REVIEW è stata CANCELLATA da topic 3: la regola `state=HUMAN_REVIEW_REQUIRED forbids missing_facts` (`models.py:1428` oggi) e `engine-response.ts:251`
lo vietano su entrambi i lati, come Astra aveva obiettato.

**Esito finale (spec v6.2 §2, §3):** PR-O3 e PR-O4 sono DELTA DI SCOPE DICHIARATI (Δ1, Δ2),
ciascuno gated sul sì esplicito di Zero (D6). Δ1 apre `flow.ts`/`tree.ts` + corpus walk;
Δ2 apre contenuto/markup di `OutcomeSheet.tsx`, `i18n.ts`, `outcome-fallbacks.ts` e il testo
di `ConsentHandoff.tsx`; `oracle.css` resta READ-ONLY anche sotto Δ2 (un bisogno di stile è
un ulteriore delta da riportare, non da prendere). Senza D6 la finestra si ferma alla PR-O2
con handoff; l'ordine O0 → O1 → O2 → O3 → O4 è stretto e O3/O4 non si costruiscono mai
prima di O2. D6 è registrata «Δ1 SÌ, Δ2 SÌ» in `02-DECISIONI-ZERO.md` (per delega, §4).
Mai due finestre sull'Oracle nello stesso momento; frozen-for-others:
`apps/mouth/src/app/(visa-oracle)/**`, `apps/mouth/scripts/visa-oracle/**`,
`apps/mouth/e2e/visa-oracle-*.spec.ts`, `apps/backend-rag/backend/tests/services/visa_engine/**`,
`apps/backend-rag/backend/scripts/visa_engine/**`,
`.agents/skills/visaoracle/**`, `research/visa/**`.

**Obiezione Astra da portare nel lotto website (round 1, MEDIUM):** preservare il
default di `NavShell` non basta — `Footer` è consumato anche da
`apps/mouth/src/app/kbli/layout.tsx` e `NewsHero` da `/v2`; ogni consumer condiviso
vuole una variante opt-in con default byte-identico provato. Ownership (README Astra §ownership,
W7 §2): Footer/MobileNav/HeroBlueprint/PersonaDoors sono di W7; NewsHero/LatestNews/NewsPageClient
sono di W4 e W5 li eredita; W7 non tocca NewsHero.

## 4. Le ruling di Zero: cosa è registrato e cosa resta aperto

Le decisioni vivono in un solo posto, `02-DECISIONI-ZERO.md` sul Desktop del Mini (fuori
repo): la finestra Oracle lo rilegge prima di ogni PR. Stato al 2026-09-11 ~04:10 WITA,
compilato da topic 3 (sessione `nuzantara-c8`, Fable 5.1: l'intestazione del file dice «Compilato da Fable 5.1») su delega esplicita di Zero («fai tu»); Zero può sovrascrivere ogni riga.

- **M — motori: REGISTRATA = solo Oracle (M2).** Studio W1→W3 entra nello slot motori solo
  su nuova istruzione di Zero. La raccomandazione originaria di questo documento era M1 con
  Oracle per primo; la delega ha scelto M2, coerente con «Oracle per primo», e rinvia solo Studio.
- **D6 — delta Δ1/Δ2: REGISTRATA = sì, sì.** Perimetro esatto in §3.
- **D — identità (riga D4): APERTA, di Zero.** (D-A) R19 Direction A su home e superfici
  marketing/blog nominate nel README Astra, funnel invariati, primaria R19 al posto del
  vincolo di tinta rossa (`apps/mouth/e2e/persona-doors.spec.ts:67` ri-pinnato per token, non
  per contratto), font locali per route; (D-B) sola composizione e contenuto con colori e font
  attuali. **Raccomandazione Fable + Astra: D-A.** Con D-B, W7 non parte e W2/W4/W5 procedono
  nel solo perimetro compositivo; finché D4 non è scritta, W2 procede in D-B per costruzione.
- **D1, D2, D3, D5** riguardano solo la finestra Oracle e sono registrate: D1 sì (copy in
  finestra, refuter Codex + gate Opus giudicano); D2 hold invariate (stringerle è un nuovo
  mandato); D3 non ora (numero e consenso sono di Zero, fallback neutro in PR-O4); D5
  denominatore 67 walk + estensioni dichiarate; target (a) decisivi (SUPPORTED +
  NO_SUPPORTED_PATH) con flag ≥ 38/67 = nessuna regressione dal baseline 31+7; senza flag il
  baseline è già 65/67 (55+10) e la riga D5 scrive «≥ 57/67 dopo Δ1», che nella notazione
  della spec (PR-O3: 2/10/55 → 0/10/57) conta i soli SUPPORTED — il panel lo segnala come
  ambiguo (§8) e la correzione della riga spetta a topic 3; (b) NEEDS_INPUT senza domanda
  raggiungibile = 0, da leggere DOPO Δ1 e sul baseline con flag (senza flag il baseline ne
  ha 2: è ciò che Δ1 cura); (c) 100 % delle review residue con causa specifica EN/ID.

**Rollback comune (spec v6.2 §4, vale per entrambi gli slot):** revert in NUOVA PR armata; per
`apps/mouth` `vercel promote` della Production precedente PRIMA che il revert atterri; per
`apps/backend-rag` la PR di revert È il redeploy; il kill switch di modo
(`VISA_ENGINE_EVALUATE_MODE`) non è un rollback UI e nessuna finestra lo tocca. File condiviso
inatteso fra i due slot: vince la PR già armata, l'altra rebasa, collisione riportata a Zero.
Le due finestre shippano entrambe su `apps/mouth`: la merge queue serializza i commit su main e
Vercel costruisce ogni commit, quindi il prove-live si fa sulla revisione SERVITA, che può
contenere anche la PR dell'altra finestra; `vercel promote` di una Production precedente è
lecito solo se non annulla una PR dell'altra finestra già provata — altrimenti l'unico rollback
è la PR di revert. Il promote si fa per ID di deployment (l'ultima Production che precede la PR
della finestra e segue ogni PR già provata dell'altra), dopo aver confrontato l'ascendenza del
candidato con lo SHA servito. Attenzione all'autopromote del Mini
(`infra/launchagents/wrappers/mini-vercel-autopromote.sh`, ogni ~12 min, promozione ON di
default): finché il revert non è su main può ri-promuovere l'ultima build di main e disfare il
promote; il rollback durevole è quindi il merge del revert, e il promote copre solo quella
finestra — chi fa rollback lo dichiara nel report, e se serve una sospensione dell'autopromote
(kill switch `MINI_VERCEL_AUTOPROMOTE_ENABLED=false` nel suo ambiente launchd) la chiede a Zero.

## 5. Finestre da lanciare ora (due slot)

### Slot motori — W-ORACLE (Dux: topic 3), su Mini

Testo binding: spec v6.2 §6 (= `01-PROMPT-W-ORACLE.txt` nel kit Desktop), riportato qui
verbatim. Sostituisce la stesura convergente precedente di questo documento (che aveva cinque PR
senza il gate D6 e il sha v5 della spec). Note di lancio: `claude --model claude-opus-5 --effort
xhigh` in tmux su Mini, cwd `~/nuzantara`; sul Mini la voce Keychain
`nuzantara-postgres-readonly` NON esiste (verificato 2026-09-11), quindi la prova del pack attivo
è la sonda live confrontata con la voce di attivazione in LIVE STATE, come dice il prompt.
Lettura vincolante della lista read-only del prompt («…oracle.css/questions/consents read-only
per W0 §2»): vale SALVO i perimetri Δ1/Δ2 dichiarati in spec §2, che D6 = sì apre; la riga D6 di
`02-DECISIONI-ZERO.md`, riletta prima di ogni PR, li elenca per nome. Alias: W-ORACLE =
W0-ORACLE-REASONS di Astra estesa (PR-O0…O4); task-id vincolante quello del prompt,
`shweb-w-oracle-20260911` (`shweb-w0-oracle-20260911` in W0/LAUNCH è l'alias Astra). D6 è doppia:
PR-O3 verifica «Δ1: SÌ» e PR-O4 verifica «Δ2: SÌ», ciascuna per sé. Nota per PR-O3: il generatore
del corpus (`apps/mouth/scripts/visa-oracle/generate-walk-corpus.ts:135`) sceglie la PRIMA opzione
di ogni domanda, che per `family_sponsor_confirmed` è «yes» (`tree.ts:868`): l'accettazione di Δ1
richiede casi yes/no sui due rami, con e senza flag, oltre al baseline dei 67 walk invariato.
Ogni finestra legge `FINAL.md` §4 e `02-DECISIONI-ZERO.md` prima di eseguire e prima di ogni PR,
con precedenza sui prompt storici del pacchetto (il README Astra che dice «M non registrata» e
il blocco W7 «Scelgo D-A» valgono solo attraverso le decisioni scritte).

```text
Mandate SHWEB-20260911 / W-ORACLE (Astra W0 + declared deltas). Read first, fully, from
these ABSOLUTE paths on Mini (all uncommitted at spec time; pin each by sha256 in your
brief, never assume they are on main): (1) this spec, binding:
/Users/nuzantara/nuzantara/.worktrees/mouth-visa-review-reason-audit-20260911/research/visa/2026-09-11-oracle-final-window-spec.md;
(2) Astra's audit README + census in the same worktree under
research/visa/2026-09-11-review-reason-audit/; (3) Astra's package
/Users/nuzantara/nuzantara/.worktrees/docs-mouth-final-windows-20260911/docs/plans/mouth-final-20260911/{README,W0-oracle-reasons}.md;
(4) .agents/skills/visaoracle (SKILL.md LIVE STATE + references/live-state-log.md newest
entries) on origin/main. PR-O0 copies (1) and (2) into your worktree and commits them. (5) Zero's decisions
D1–D6 and M live in /Users/nuzantara/Desktop/w-oracle-launch-20260911/02-DECISIONI-ZERO.md: read it at
start and before every PR; a decision not written there is MISSING. Machine check, base
SHA, Pro reachability. You orchestrate (Opus 5 xhigh, no hands); one Sonnet 5 implementer
in a NEW worktree via scripts/agent_start.py --lane mouth --task-id shweb-w-oracle-20260911,
depth 1, max 50 tool calls / 45 active minutes per child; refuter = codex exec
--sandbox read-only on every PR (generator≠grader); fresh Opus 5 xhigh gate on each PR HEAD.
Scope EXCLUSIVE as spec §2; everything else frozen; evaluate_path/evaluator/models/pack/
pricing/engine rules/oracle.css/questions/consents read-only per W0 §2; no Decision schema
change; missing_facts never under HUMAN_REVIEW. Deliver PR-O0 → PR-O1 → PR-O2 (only after
D1); then PR-O3 and PR-O4 ONLY if Zero has said yes to D6 (they are declared scope deltas on
questions and outcome presentation) — otherwise stop after PR-O2 with a handoff. Exactly as
spec §3, one PR per concern from fresh origin/main, ≤ ~400 net lines, Bites: line naming
consumer + observed proof, brief via scripts/ci/evidence_paths.py. Gates per spec §4 on
every PR; fullstack e2e only through its disposable-DB runner. Ship each PR end to end:
review → merge (auto-merge armed at open, `gh pr merge --auto` bare) → deploy → prove-live
with probe_evaluate synthetic_driver (rule_pack_id must equal the activation-ledger record
in force: readonly role on Pro, or on Mini the probe vs the LIVE STATE activation entry) + the
shared screenshot pair; never traffic_source=real,
never a lead, never PII in artifacts. No ENFORCE/SHADOW flip, no pack signing/activation.
STOP and report to Zero if: a frozen file appears in a diff, a test goes red three times for
the same cause, a change needs a schema/rule/legal-source decision, a hold narrowing looks
required (that is D2, a new mandate), or a decision D1/D3/D5 is missing for the next PR —
finish every PR that does not depend on it first. Update SKILL.md LIVE STATE + the log in
the same PR that changes state. Report: PR numbers, measured census before/after, list of
codes with copy, live proof, what remains.
```

### Slot website — W2 Team

Testo verbatim da `LAUNCH.md` («Prima coppia: W1 Studio e W2 Team», secondo blocco),
invariato. Scope esclusivo: `(blog)/team/page.tsx`, innesto founder in
`(marketing)/page.tsx`, `v2/_components/SocialProof.tsx`, CSS module e test colocati,
`e2e/shweb-team.spec.ts`; roster read-only; verifica `/v2/company/about`. Nessuna
dipendenza da W0 né da W7.

Lancio: `claude --model claude-opus-5 --effort xhigh`, cwd `~/nuzantara`, su Pro o Mini (su Pro
trasferire prima il pacchetto verificando manifest e hash: il path Mini nel prompt non prova che
esista sull'altro host); prompt = `07-PROMPT-WEBSITE-W2.txt` del kit (testo Astra) + l'addendum.

Addendum da incollare dopo il testo Astra (vale per ogni lotto website W2/W7/W4/W5/W6):

```text
Addendum topic 5 (FINAL.md §5, spec Oracle v6.2 §2/§4):
Consumer condivisi: Footer è consumato anche da apps/mouth/src/app/kbli/layout.tsx e NewsHero
da /v2; ogni variante è opt-in con default byte-identico provato su /v2, KBLI e reader.
globals.css: VIETATO (W2 §2 e W7 §2 vincono sulla riga «blocco additivo .r19-*» della spec
Oracle §2); i token R19 vivono in CSS module o stylesheet di route scoped, un bisogno globale è
un delta da riportare, non da prendere. Frozen per il website:
apps/mouth/src/app/(visa-oracle)/**, apps/mouth/src/app/visa/**, packages/core/tokens/**,
root layout.tsx, apps/mouth/src/data/team-roster.ts (l'esclusione dal pubblico si applica nei
tre consumer di rosterBySlug — team, SocialProof, about — E nel book: components/book/book-data.ts
deriva TEAM_MEMBERS da PUBLIC_ROSTER e nessun membro ha publicListed:false, quindi /book/team
mostra ancora i due esclusi; W2 possiede il filtro di presentazione del book + test di regressione,
roster invariato),
kbli/** (W6 possiede i soli file di presentazione KBLI, e solo dopo il go esplicito).
Leggi FINAL.md §4 e 02-DECISIONI-ZERO.md prima di eseguire e prima di ogni PR: le decisioni
scritte lì hanno precedenza sui prompt storici del pacchetto (README «M non registrata»,
blocco W7 «Scelgo D-A»). Ownership: NewsHero/LatestNews sono di W4 (W5 eredita), non di W7.
R19 si legge solo con git show 6603d2913e:<path>: mai la patch di quarantena, mai il branch
riaperto, mai apps/website attivo. Rollback: revert in NUOVA PR armata e, per apps/mouth,
vercel promote per ID della Production che precede la tua PR e segue ogni PR provata dell'altra
finestra, PRIMA che il revert atterri; l'autopromote del Mini può ri-promuovere main entro ~12 min,
quindi il rollback durevole è il merge del revert. File condiviso inatteso
con la finestra Oracle: vince la PR già armata, l'altra rebasa, collisione riportata a Zero.
Builder Contract 5: questa finestra Claude shippa da sola (review → merge → arm → deploy →
prove-live). Le frasi Astra «preparazione fino a candidato reviewable», «consegna PR/candidato
al release owner» e «nessun deploy implicito» sono ABROGATE per una finestra Claude: il release
owner sei tu, e SHIPPED vale solo dopo la prova sulla revisione servita. Riporta a Zero solo
decisioni di business, credenziali e consensi.
```

Astra scrive «consegna al release owner, nessun deploy implicito» perché la sua spec è
prepare-only (seat esterno); per una finestra Claude vale il Builder Contract 5 del
`CLAUDE.md`: generator ≠ grader resta garantito dal refuter Codex e dal gate Opus fresco.

## 6. Coda dopo i due slot

| Dipendenza                                                               | Finestra                                 | Prompt                                            |
| ------------------------------------------------------------------------ | ---------------------------------------- | ------------------------------------------------- |
| M = entrambi (oggi registrata M2, solo Oracle: esclusa da questo lancio) | W1 Studio tecnico → W3 Studio editoriale | `LAUNCH.md` (W1 verbatim; W3 dal template «Coda») |
| D4 = D-A scritta in `02-DECISIONI-ZERO.md` + W2 integrata                | W7 identità/chrome Direction A           | `LAUNCH.md` («Dopo la scelta D-A»)                |
| W2 (+ W7 se D-A)                                                         | W4 News → W5 Home                        | template «Coda»                                   |
| W5 + baseline Lighthouse + go esplicito di Zero                          | W6 KBLI                                  | template «Coda»                                   |

W7 precede W4/W5 per non avere due owner su NewsHero, home, CSS e font. Con D-B si
salta W7. La remediation npm dell'intero workspace resta una finestra distinta.

## 7. Stato

- PR #6124 (mappa design): OPEN, auto-merge armato. Gate fresco Opus 5 = PASS-WITH-CONDITIONS
  su `cdfe4a3d26` (13/14 spot-check verificati); le condizioni C1–C4 (tre clausole sul
  meccanismo di contrasto Merah Putih: il contesto required è always-triggering con sentinella
  in-job, mai path-filtered; la leva per ritirarlo è la branch protection, `contexts.json` è
  un mirror generato) sono state applicate nel documento stesso (`4f68f63b84`), C5 (riga
  `Bites:`) nel body. Il check «Harness floor recompute» vuole il verdetto `harness/fable-gate`
  sul head e il rilancio del run `pull_request` originale (runbook §6septies).
- Questa PR: pacchetto Astra copiato byte-identico (hash in §1) + `FINAL.md` + brief gear 2 +
  panel a quattro seat (§8). Primo gate fresco = REWORK-BUILD: churn 2 873 righe ≥ soglia
  1 828 del floor gear 3 (termine SIZE), seat Gemini default inghiottito da `.gitignore:430`
  (`GEMINI.md`, FS case-insensitive), «Detect Secrets» rosso sulle hash sha256 dei manifest,
  §7 e `gear_reason` inesatti. Rework: tre file di evidenza non portanti tolti e registrati con
  hash in `EXCLUDED-FILES.sha256`, seat rinominato `panel-gemini-default-agy.md`, un filtro
  regex nel `.secrets.baseline` per i due manifest JSON (digest di file, non credenziali),
  churn misurato sotto soglia e brief riscritto. La spec v6.2 di topic 3 entra su main con la
  PR-O0 della finestra Oracle, non con questa.
- Nessuna finestra è aperta da questo documento. Zero apre i due slot dal kit Desktop del Mini:
  W-ORACLE subito (D1, D5, D6, M già registrate), W2 subito (nessuna ruling necessaria); W7 solo
  dopo D4 = D-A.

## 8. Panel sulla spec finale

Quattro seat richiesti da Zero (Astra Codex `gpt-6-astra` xhigh, Gemini 3.1 Pro high, Qwen 3.8
Max, Kimi K3 max) sul bundle `FINAL.md` + README/LAUNCH/W0/W2/W7 + `02-DECISIONI-ZERO.md` +
addendum 08 (sha di `FINAL.md` al lancio in `evidence/panel/RUN-LOG.md`). Output grezzi in
`evidence/panel/`. Formato chiesto: max 20 finding `[L1|L2|L3] [HIGH|MED|LOW]`, poi
`LAUNCHABLE-AS-WRITTEN`.

| Seat                                                                 | Modello servito                                                                                                                                                                                                             | Esito                                                             | Verdetto    |
| -------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | ----------- |
| Qwen 3.8 Max                                                         | TP1 `qwen`                                                                                                                                                                                                                  | FALLITO: `403 Access to model denied` (come nel panel di topic 3) | —           |
| Gemini, default `agy` (`evidence/panel/panel-gemini-default-agy.md`) | si dichiara «Gemini 3.8 Flash» (settings `gemini-3.1-pro-preview`); tentativo 1 vuoto per tool negato in headless                                                                                                           | 16 finding                                                        | conditional |
| Gemini 3.1 Pro (High)                                                | `agy --model "Gemini 3.1 Pro (High)"`, si dichiara «Gemini 3.1 Pro (High)»                                                                                                                                                  | 7 finding                                                         | conditional |
| Kimi K3                                                              | `kimi-code/k3`; ha verificato le claim sul repo (persona-doors:67, engine-response.ts:251, Keychain assente, `kbli/layout.tsx:8` Footer, `v2/page.tsx:11,95` NewsHero, tre consumer di `rosterBySlug`, about senza esclusi) | 12 finding                                                        | conditional |
| Astra                                                                | `codex exec -m gpt-6-astra`, xhigh, sandbox read-only, 306 K token; ha verificato sul repo (book-data.ts, autopromote, corpus generator, audit README)                                                                      | 10 finding                                                        | **no**      |

Disposizioni (A = applicata qui e nell'addendum 08; P = parziale o rinviata a chi possiede il
file; R = respinta con evidenza):

1. A — autorità di ship di W2 contraddittoria (Kimi HIGH, Gemini HIGH): l'addendum ABROGA
   esplicitamente «preparazione fino a candidato reviewable», «consegna al release owner»,
   «nessun deploy implicito». `LAUNCH.md` resta intatto (file Astra pinnato).
2. P — il prompt W-ORACLE congela questions/consents e poi ordina Δ1/Δ2 (Kimi HIGH, Gemini
   HIGH): il prompt è la spec v6.2 §6 pinnata da topic 3; la lettura vincolante è scritta in §5
   e la riga D6 di `02-DECISIONI-ZERO.md`, riletta prima di ogni PR, apre i file per nome.
   Chiesta a topic 3 una clausola esplicita «read-only salvo Δ1/Δ2» nella riga D6.
3. A — `globals.css` (Gemini HIGH, Kimi MED): l'addendum concedeva un blocco `.r19-*` (riga
   della spec Oracle §2) contro W2 §2 e W7 §2 che lo vietano; vince il perimetro più stretto.
4. P — D5 (a) «≥ 57/67 senza flag» (Gemini HIGH, Kimi MED) e (b) «= 0 prima e dopo» con 2
   NEEDS_INPUT nel baseline senza flag (Kimi MED): riga di topic 3; §4 riporta la lettura
   coerente con la spec (57 = SUPPORTED nella notazione di PR-O3; decisivi già 65/67; (b) dopo
   Δ1 e sul baseline con flag); correzione chiesta a topic 3. Nessuna PR dipende da D5 prima di
   PR-O3.
5. A — «25 codici» → 29 (Gemini MED).
6. A — attribuzione «Fable 5.1» vs «topic 3» (Kimi MED): riconciliata in §1/§4.
7. A — «home» ambigua (Kimi MED): §2 dice home = `/`, `/v2` invariata.
8. A — deploy race fra due finestre che shippano (Gemini HIGH): regola in §4 (prove-live sulla
   revisione servita; `vercel promote` solo se non annulla una PR provata dell'altra finestra).
9. A — `models.py:1426` → regola per nome, oggi riga 1428 (Kimi LOW).
10. A — README «Stato della consegna» stantio (Kimi LOW): nota in §1, superato da §7.
11. A — W0 §1 «nessuna ripresa della branch audit» vs PR-O0 (Kimi LOW): §3 chiarisce la copia
    del contenuto in un worktree nuovo.
12. A — alias W-ORACLE = W0 estesa e task-id vincolante (Kimi LOW, Gemini LOW): riga in §5.
13. A — riga di lancio W2 mancante (Kimi LOW): aggiunta in §5.
14. A — path worktree Astra vs Fable (Gemini MED): nota in §1.
15. P — `origin/main` non contiene ancora pacchetto e mappa (Gemini MED): per disegno i prompt
    pinnano path assoluti + sha; questa PR li rende durevoli. Raccomandazione: lanciare W2 dopo
    il merge di questa PR e di #6124; W-ORACLE parte dal kit.
16. P — runner e2e fullstack a DB usa-e-getta su Mini senza Keychain (Gemini MED): la Keychain
    serve alla sonda readonly su Pro, non al runner; verifica del runner su Mini chiesta a
    topic 3 prima di PR-O3/O4 (PR-O0…O2 non lo richiedono).
17. R — Δ1 su `tree.ts` sarebbe «cambio backend» (Gemini MED): `flow.ts`/`tree.ts` stanno in
    `apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/` (frontend); W0 §2 non è violato.
18. R — il fallback neutro di PR-O4 regredirebbe la lead generation (Gemini MED): la spec §1
    verifica che oggi il visitatore vede già «WhatsApp handoff is not configured»
    (`ConsentHandoff.tsx:64`); non c'è contatto attivo da perdere; D3 resta di Zero.
19. R — Ari/Surya richiederebbero di editare `team-roster.ts` read-only (Gemini MED): il file
    non ha campi href/url/link (grep: 0); le destinazioni vivono nei componenti che W2 possiede.
20. R — `/v2/company/about` fuori perimetro W2 ma da correggere (Gemini MED): W2 §4 la verifica
    soltanto e la base verificata (anche da Kimi) non elenca i due esclusi.
21. R — `oracle.css` read-only sotto Δ2 (Gemini MED): decisione del proprietario (D6).
22. R — `gh pr merge --auto` senza metodo (Gemini LOW): convenzione del repo (arming bare,
    metodo fissato dal ruleset).
23. A — il book `/book/team` mostra ancora i due esclusi (Astra HIGH): `book-data.ts` deriva
    `TEAM_MEMBERS` da `PUBLIC_ROSTER` e nessun membro del roster ha `publicListed:false`
    (grep: la chiave compare solo nella definizione e nel filtro); W2 §2 non nomina il book.
    L'addendum assegna a W2 il filtro di presentazione del book + test di regressione, roster
    invariato.
24. A — rollback disfatto dall'autopromote (Astra HIGH) e promote per ID di deployment
    (Gemini Pro HIGH, Astra HIGH): §4 e addendum nominano il wrapper (`mini-vercel-autopromote.sh`,
    ON di default, `vercel_prod_deploy.py` sceglie l'ultimo commit rilevante), il promote per ID
    con controllo di ascendenza, e il merge del revert come rollback durevole; il kill switch
    `MINI_VERCEL_AUTOPROMOTE_ENABLED=false` è di Zero.
25. A — glob backend errato in §3 (Astra MED): `backend/tests/visa_engine` non esiste; ora
    `backend/tests/services/visa_engine/**` e `backend/scripts/visa_engine/**`, come nella spec §2.
26. A — NewsHero attribuito a W7 (Astra MED): README §ownership e W4 §2 lo danno a W4 (W5
    eredita); W7 §2 possiede Footer/MobileNav/HeroBlueprint/PersonaDoors. Corretti §3 e addendum.
27. A — i prompt copiati non leggono le decisioni (Astra MED): §5 e addendum impongono la
    lettura di `FINAL.md` §4 + `02-DECISIONI-ZERO.md` prima di eseguire e prima di ogni PR,
    con precedenza sui prompt storici.
28. A — «verificato su disco e in prod» (Astra MED): il census dei 67 walk è un replay offline
    (audit README); §1 lo dice e separa la sonda live sintetica.
29. P — gate screenshot «identici, cambiati solo da PR-O4» mentre O2/O3 cambiano copy e domande
    (Astra MED): spec di topic 3 (§4 riga 100); chiesto a topic 3 di definire le differenze visive
    ammesse per PR (landing vs OutcomeSheet) e di confrontare i controlli del website sulla stessa
    revisione Oracle.
30. P — il corpus di PR-O3 esercita solo «yes» (Astra MED): verificato
    (`generate-walk-corpus.ts:135` → `options[0]`, `tree.ts:868` = yes); nota in §5 e richiesta a
    topic 3 di esigere casi yes/no sui due rami con e senza flag nell'accettazione di PR-O3.
31. A — D6 letta come booleano unico (Gemini Pro LOW): §5 esplicita Δ1 per PR-O3 e Δ2 per PR-O4.
32. P — STOP se D5 fallisce non è nel prompt (Gemini Pro MED): la riga D5 di
    `02-DECISIONI-ZERO.md` scrive già «se la misura contraddice, STOP e riporta» e la finestra la
    rilegge prima di ogni PR; segnalato a topic 3 come clausola opzionale nel prompt.
33. R — nome dello script inventario assente dal prompt (Gemini Pro MED): W0 §2 lo vuole
    «fissato nel brief» della finestra, non nel prompt di lancio; PR-O1 ne fissa path e nome.
34. R — PR-O0 non committerebbe il live-state (Gemini Pro LOW): spec §3 PR-O0 elenca le voci di
    `live-state-log.md` e la CURRENT POSITION di SKILL.md esplicitamente.

Esito complessivo: nessun seat ha trovato un difetto che richieda di riaprire le decisioni di
Zero; i due HIGH condivisi (autorità di ship di W2, lettura del read-only con Δ1/Δ2) sono chiusi
in testo; i tre HIGH di Astra sul book, sull'autopromote e sul corpus sono chiusi (book,
autopromote) o rinviati a topic 3 con evidenza (corpus). Le richieste a topic 3 (2, 4, 16, 29,
30, 32) sono state inviate via mailbox alla sessione `nuzantara-c8`; nessuna blocca PR-O0…O2.
