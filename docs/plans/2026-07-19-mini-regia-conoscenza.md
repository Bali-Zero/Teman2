---
date: 2026-07-19
machine: Mini-Pro2 (nuzantara@mini-pro2)
session: MINI-B — REGIA CONOSCENZA & ORGANISMO (Fable 5, max effort, orchestrator + final gate)
status: ARMED — 3 launch prompts ready, discards handed off
recon: 6-lane Sonnet workflow wf_920d4e80-268 (charter-2814, wa-corpus, chatkb, nb-arsenal, mini-host, anti-twin), 739k tokens, all claims evidence-backed
panel: Codex gpt-5.5 xhigh (red-team; gpt-5.6-sol dead on Mini — CLI 0.142.0 too old) + Kimi K3 (refuter, ran its own live spot-verifications). agy AUTH_DEAD, DeepSeek BALANCE_DEAD (402), GLM CRED_UNAVAILABLE — probed live this session; 2-seat heterogeneous panel = acceptable-degraded, declared.
twin: MINI-A "REGIA MOTORI & PRODOTTO" (live, tmux regia-motori) owns KBLI filiera/navigator, Visa Oracle engine/wiring, cache-cantiere Batch-B (CHATKB), intake/CRM — disjoint by design.
---

# MINI-B — Regia Conoscenza & Organismo: 3 armed sessions

## 1. Reconnaissance synthesis (what changed the hypotheses)

| Front           | Load-bearing finding                                                                                                                                                                                                                                                                                                                     | Evidence                                                 |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| Charter #2814   | Real name is "Avvocato **Totale**" (not Assoluto); PROPOSAL v0 **unratified** (Legge 5); NUZANTARA hard-separated (charter §7: zero net-new standing daemons on Pro/Mini attributable to it). The Pro session 932b2e53 is **already running the census** (4 survey subagents live: qdrant/drive-nlm/pg/disk-survey, started 15:29 today) | `gh pr view 2814`; `ssh pro ps aux`                      |
| WA corpus       | 5,313 pairs verified by len(); Pro-local chmod 600; names NOT scrubbed; clustering **already computed** (4,220 near-unique clusters → corpus = demand signal, not ready Q&A; 4 prior red-team rounds rejected fact-extraction, recall<30%); Pro Ollama has SEA-LION-32B (IT/ID)                                                          | ssh pro python len(); `wa_clusters_semantic.json` exists |
| CHATKB cantiere | 100% M5-owned (`agent/air-m5/*`), inside MINI-A perimeter ("cache cantiere"); rails PR #2810 armed-but-BLOCKED; #2835 red on check-docs-sync. Unclaimed items exist but are not ours                                                                                                                                                     | `gh pr view 2810/2835`                                   |
| NB arsenal      | 96 NBs live, core healthy/growing; REAL free gaps: MATA GARUDA 4 NBs frozen 5 weeks; AIResearch-2 overflow stalled 19 days; Press+AIResearch at 500-source ceiling; reference file 34d stale; account-identity contradiction (CLAUDE.md says zero@, 3 live memories say antonellosiano@)                                                 | live `notebook_list` count=96                            |
| Mini host       | Qdrant completely ABSENT (no binary/docker → from-scratch provisioning); Postgres+Redis STARTED; 30+ LaunchAgents incl. **7 `.bak-tcc-20260716` corpses** (W84 mass event) + one `.disabled-2026-05-10-broken-exit126`; host CLAUDE.md stale/wrong on 3 proven counts; 221Gi disk free; 24GB RAM                                         | live probes                                              |
| Anti-twin       | MINI-A live on this host; visaoracle-b live (visa content); Pro runs S2/S3/S4 + intake + charter; M5 runs KBLI conductor + cache Phase-0. MAX quota at 95% weekly at launch                                                                                                                                                              | tmux ls, ps, `gh pr list`                                |

## 2. Slate → panel → decision

7 candidates generated; panel (Codex red-team + Kimi refuter, verdicts treated as LEADS) converged: **C4 unanimous #1**, C2 GO with quantified PII gate, C3 split (janitorial now / provisioning behind Zero GO), C1 prep-only artifact-driven, C5+C6 fatal twin-collision (hand off), C8 unlocated revival target (salvage-read only). Final gate decision (Fable): merge C4+C3-janitorial into one ORGANISMO session (cures the C3×C4 collision on the matagaruda plists both seats flagged); keep C1 and C2 as the CONOSCENZA pair with the panel's hardening folded in.

## 3. The 3 armed sessions (launch prompts in §6–§8, Italian, operator-facing)

| #   | Session                                            | Front      | Launchable today because                                                                                                                   |
| --- | -------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | AVVOCATO-BATCH — gap-map & ingestion prep          | CONOSCENZA | Target-side corpus map + deterministic gap-map compiler need no census; join runs when Pro survey artifacts land (receptor, not busy-wait) |
| 2   | WA-DEMAND-PACKS — PII-free demand packs            | CONOSCENZA | Corpus, clustering artifacts and NER models all verified live on Pro; falsifiable scrub gate defined                                       |
| 3   | MINI-ORGANISMO STEWARD — NB arsenal + host hygiene | ORGANISMO  | All targets verified-live gaps; nlm auth works from Mini now; zero perimeter exposure                                                      |

## 4. Discard table (one line each, per mandate)

| Candidate                           | Verdict            | Why                                                                                                                                                 | Disposition                                                                    |
| ----------------------------------- | ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| C5 CHATKB-JSONL-LANDING             | DISCARD            | Cantiere = MINI-A perimeter + dossiers only on M5 disk                                                                                              | **Handoff to MINI-A** (§5)                                                     |
| C6 VISA-DB-HYGIENE                  | DISCARD            | Visa Oracle = MINI-A; visaoracle-b live on Mini                                                                                                     | **Handoff to MINI-A** (§5)                                                     |
| C8 WA-V7-REVIVAL                    | DISCARD as session | Revival target unlocated (no v7 worktree found on Mini; Pro shows only ops-wa-tester-runtime detached-HEAD); 6-week drift; why-never-merged unknown | 15-min salvage-read folded into Session 2 F3                                   |
| C3-core Qdrant-arm + cron migration | DEFER              | Structural infra (Legge 5) + charter §7 attribution question + no RAM budget/backup story yet                                                       | Decision-memo to Zero produced by Session 3 F6; PENDING-ARMS operator[Legge-5] |

## 5. Handoff to MINI-A (verified findings, so they are not lost)

1. **JSONL prod-rebuildability invariant currently violated**: ~170-row GARUDA-visa + 20-row VOA corpora live in prod Qdrant `curated_qa` with zero JSONL committed to `apps/backend-rag/data/curated_qa/` (README landed-table empty). Cure belongs post-#2810 merge, inside your cache-cantiere lane.
2. **Visa-DB hygiene** (from CHATKB memory, no PR exists): E31F/E31G swapped; `get_visa_details` returns C2 cost 3.600.000 vs official 2.000.000. Route canonically (PricingTool discipline), never hardcode.
3. **Penangkalan delta-harvest** (lane #22): 3 point-ids, Rp 90M pencabutan-anticipata fee per PP 45/2024 Lampiran VI.E — memory says "fix in esecuzione" but no PR found anywhere.
4. **Villa-KBLI-OSS hot demand cluster** (from WA corpus): villa PT PMA clients told villa/real-estate KBLI codes pulled from OSS, team answering "no official option available" — live regulatory signal for kbli-navigator. Session 2 will deliver the PII-free demand pack; the KBLI action is yours.

## 6. PENDING-ARMS lines (appended to ledger in this PR)

- opened 2026-07-19 | arsenal seat codex `gpt-5.6-*` DEAD on Mini: CLI 0.142.0 too old ("requires a newer version of Codex"), probe passes only because it runs legacy gpt-5.5 | fix = upgrade codex CLI on Mini to ≥0.144 | owner: session lane | proof: `codex exec -m gpt-5.6-sol --sandbox read-only "PONG"` returns PONG
- opened 2026-07-19 | arsenal seat agy AUTH_DEAD on Mini (OAuth re-login is interactive/GUI) | owner: operator[GUI-login] | proof: `agy -p "PONG"` returns PONG in a live session
- opened 2026-07-19 | arsenal seat deepseek BALANCE_DEAD (HTTP 402, second recurrence after 2026-07-03 top-up) | owner: operator[credentials/top-up] | proof: 1-token probe HTTP 200
- opened 2026-07-19 | Qdrant-on-Mini provisioning + heavy-cron migration from Pro + Avvocato ingestion target-store: STRUCTURAL, awaiting decision-memo (Session 3 F6 produces it) and Zero GO | owner: operator[Legge-5] | proof: memo exists in research/operations/ AND Zero's explicit GO recorded
- opened 2026-07-19 | TCC grants for any re-armed LaunchAgent from the 7 `.bak-tcc-20260716` corpses: System Settings only, NEVER `tccutil reset` (W84-recidiva scar) | owner: operator[TCC] | proof: re-armed agent exit 0 AND log content clean (W84 double-check)

## 7. Claim lines (twin discipline)

- TRACK AVVOCATO-BATCH (target-map + gap-map compiler + ingestion plan; NOT the charter, NOT the census) claimed by Mini/2026-07-19 — session 1.
- TRACK WA-DEMAND-PACKS (Pro-side scrub + packs; NOT bot pipeline, NOT curated Q&A supply) claimed by Mini/2026-07-19 — session 2.
- TRACK MINI-ORGANISMO (NB arsenal cure + Mini host janitorial + decision-memo; NOT Qdrant arm, NOT cron migration execution) claimed by Mini/2026-07-19 — session 3.

---

## 8. LAUNCH PROMPT — Session 1: AVVOCATO-BATCH

```text
MANDATO AVVOCATO-BATCH — "GAP-MAP & INGESTION PREP" (braccio batch Fase-0, downstream del census — MAI la charter). Sei Fable 5 (max effort) su Mini (nuzantara@mini-pro2), cwd ~/Desktop/nuzantara, orchestratore + final gate; edit/commit solo via subagenti Sonnet in worktree (scripts/agent_start.py). Carica skill: modus (dichiara GEAR); workflow solo se fan-out ≥3 lane indipendenti.

FIREBREAK (non negoziabile): la charter "Avvocato Totale" (PR #2814) è PROPOSAL v0 NON ratificata (Legge 5) e la conduce la sessione Pro con Zero. Tu NON implementi la charter, NON tocchi i suoi file, NON crei infra NUZANTARA (charter §7: zero daemon nuovi su Pro/Mini attribuibili a NUZANTARA). Sei il braccio PREPARATORIO: artefatti di analisi riusabili qualunque sia l'esito della ratifica.

TWIN-GREP OBBLIGATORIO in apertura (prova su disco, non da memoria): (1) tmux ls && ps aux | grep 'claude --model' | grep -v grep; (2) ssh pro 'ps aux | grep -E "qdrant-survey|drive-nlm-survey|pg-survey|disk-survey" | grep -v grep' — se i 4 survey della sessione Pro 932b2e53 girano ancora o hanno prodotto artifact, il census NON si rifà MAI da qui; (3) gh pr list --state open --limit 40 e grep -iE 'avvocato|census|nuzantara' su titoli + .claude/skills/modus/PENDING-ARMS.md; (4) leggi docs/plans/2026-07-19-mini-regia-conoscenza.md §7 (claim lines) e rispetta i perimetri MINI-A (KBLI/visa-engine/cache-cantiere/intake: MAI toccarli).

FASI:
F1 GROUND — leggi charter + KB-activation-plan dal branch PR #2814 (git fetch origin worktree-nuzantara-charter && git show); verifica SU DISCO apps/backend-rag/scripts/ingest_tier1_gaps.py e la dir Tier1 PDFs (~517MB); individua dove atterreranno gli artifact dei survey Pro (research/operations/ nuovi file census): definisci il CONTRATTO D'INTERFACCIA (path attesi, schema, done-signal) e un receptor PENDING-ARMS se non atterrano in giornata — mai busy-wait.
F2 TARGET-SIDE BUILD (il lavoro di oggi, zero dipendenze dal census) — per i 3 pilot candidati della charter (ketenagakerjaan, KUHP baru, UMKM/OSS) costruisci la TARGET normative corpus map: elenco strutturato delle norme richieste per dominio da fonti pubbliche (JDIH, peraturan.go.id, peraturan.bpk.go.id — fetch read-only, zero PII), schema JSON machine-readable {norm_id, tipo, anno, status_vigenza, priorità, fonte_url, pilot_domain}. ANTI-ALLUCINAZIONE NORMATIVA: ogni norm-id verificato contro la fonte fetchata o NLM query (mai dalla memoria del modello); campione ≥10% ricontrollato dal final gate.
F3 COMPILER — gap-map compiler deterministico (script python, TDD): join census-side × target-side → gap-map + dedup-map. Test su fixture sintetiche fail→pass. Il RUN reale scatta solo quando gli artifact census sono su disco (verificali per CONTENUTO, non per esistenza file).
F4 INGESTION PLAN — piano batch offline riusando il pattern ingest_tier1_gaps.py; il TARGET STORE resta DICHIARATO APERTO nel piano (Mini non ha Qdrant; la scelta Pro-Qdrant vs Mini-futuro vs macchina-NUZANTARA sta nel decision-memo della sessione MINI-ORGANISMO + Zero GO — non risolverla tu). ZERO esecuzione di ingestion in canon: nessuna norma entra in canon senza cross-family gate (principio charter §3.3), e comunque non in questa sessione.
F5 SHIP+ARM — research/operations/2026-07-19-avvocato-batch-gapmap.md + target-map dataset + compiler in PR (branch via broker, gh pr merge --auto --squash armato a PR-open); spalla adversarial sul compiler: codex exec -m gpt-5.5 -c model_reasoning_effort=xhigh --sandbox read-only (NOTA: gpt-5.6-* è morto su Mini finché la CLI non viene aggiornata — PENDING-ARMS esistente) oppure kimi -p ... -m kimi-code/k3. PROVE-LIVE: compiler eseguito davvero su fixture con output letto; target-map validata (count per dominio > 0, fonti raggiungibili a campione).

GATE falsificabili: (a) target-map con ≥20 norme per pilot-domain, ognuna con fonte_url verificata questo turno; (b) compiler test fail→pass su fixture; (c) launchctl list | diff prima/dopo = vuoto (zero daemon nuovi); (d) zero write fuori da research/ + scripts/ + docs/; (e) se census non atterrato: riga PENDING-ARMS "gap-map run pending census artifacts" scritta.
VINCOLI: zero paid API (ban ANTHROPIC_API_KEY assoluto; SDK Anthropic vietato — solo CLI OAuth); Legge 6 (tutto sulle nostre macchine); quota: se la finestra Fable muore il task SOSPENDE (PENDING-ARMS + wakeup), mai degradare il final gate. Lavora in autonomia; blocchi operator-only → PENDING-ARMS e avanti. CAPTURE finale: mem save + close line.
```

## 9. LAUNCH PROMPT — Session 2: WA-DEMAND-PACKS

```text
MANDATO WA-DEMAND-PACKS — dal corpus WA (5.313 Q&A, Pro-local) ai demand-pack PII-free che seminano i dossier del team. Sei Fable 5 (max effort) su Mini (nuzantara@mini-pro2), cwd ~/Desktop/nuzantara. Skill: modus (dichiara GEAR) + corner /bot per contesto canale. Edit/commit solo via subagenti Sonnet in worktree.

FRONTIERA PII (SYMBIOSIS Law 2 / UU PDP — non negoziabile): il corpus vive SOLO su Pro (~/nuzantara-data/wa-catalog/, chmod 600) e NON lascia il Pro in forma raw. Ogni lettura/trasformazione del CONTENUTO gira SUL PRO via ssh pro 'bash -lc "..."' con modelli Ollama Pro-locali. MAI contenuto grezzo verso QUALSIASI modello cloud (Claude incluso, Kimi incluso, tutti inclusi): tu stesso non leggi coppie q/a raw — leggi solo output già scrubbed per l'audit. Il waiver Law-2 del 2026-07-18 era one-time, NON è un precedente.

TWIN-GREP OBBLIGATORIO in apertura: (1) tmux ls && ps aux su Mini E ssh pro 'ps aux | grep claude | grep -v grep'; (2) gh pr list --state open + grep -iE 'wa.corpus|demand|curated' + .claude/skills/modus/PENDING-ARMS.md; (3) leggi docs/plans/2026-07-19-mini-regia-conoscenza.md §7 claims; (4) DEMARCAZIONE CANTIERE: il cantiere CHATKB/curated-cache (M5, MINI-A) produce SUPPLY (risposte curate); tu produci DEMAND (che cosa chiede la gente). Non scrivere MAI Q&A curate, non toccare Redis FAQ né Qdrant curated_qa.

FASI:
F1 GROUND su Pro (via ssh, read-only) — verifica corpus: conteggi via python len() (attesi 4887+426=5313); artifact clustering GIÀ esistenti: wa_clusters_semantic.json, wa_substantive_by_domain.json, wa_question_catalog_v1.json — il clustering NON si rifà: il tuo valore marginale sono i PACK. Verifica modelli: ssh pro 'bash -lc "ollama list"' — atteso aisingapore/Qwen-SEA-LION-v4-32B-IT (NER IT/ID preferito) + qwen3.5:9b fallback. Se SEA-LION assente: fallback dichiarato, mai cloud.
F2 SCRUB GATE (falsificabile, PRIMA di ogni run reale) — costruisci canary-set: 100 coppie sintetiche con PII piantata di ogni classe (nomi IT/ID/EN, telefoni +62/+39, KTP/NPWP/passaporti, indirizzi, nomi società, email, thread-id, combinazioni uniche località+data). Pipeline scrub = NER (SEA-LION su Pro) + layer regex deterministico. GATE: recall 100% sui canary (un solo miss = iterate); poi audit del final gate su 50 item campionati dell'output reale scrubbed (tu leggi SOLO l'output scrubbed): zero PII residua, incluse ri-identificazioni k-anonymity (storia unica, località+data+nazionalità). Niente esce dal Pro prima del doppio gate.
F3 PACK BUILD su Pro — dai cluster ESISTENTI, demand-pack per dominio (baseline verificata: visa 1010, company 419, process 215, tax 162, property 56): per ogni hot-cluster una domanda-tipo PARAFRASATA (mai verbatim cliente), frequenza, trend mensile, dominio, note operative per il dossier-writer del team. Include il salvage-read (15 min, read-only, archeologia) del design v7 NotebookLM-grounded: individua il ref esatto su Pro (candidati: branch feat/wa-inbox-bot-via-outbox-2026-06-04, worktree ops-wa-tester-runtime detached-HEAD) — estrai SOLO le note di design che il fire-test 2026-06-04 aveva validato; MAI revival/merge/rebase di quel worktree.
F4 EXIT dal Pro — si muovono solo i pack passati dal doppio gate F2. Se un dataset derivato entra nel REPO: compiler deterministico come unico writer + entry in infra/claude-hooks/data-plane-registry.json (pattern kbli-filiera, PR #2550) — mai hand-edit del derivato, estensione = registry entry.
F5 SHIP+ARM — research/operations/2026-07-19-wa-demand-packs.md + pack + (se repo-landing) compiler+registry in PR, gh pr merge --auto --squash armato a PR-open; spalla adversarial cross-family (codex gpt-5.5 xhigh o kimi k3) sul compiler e sul metodo scrub. HANDOFF SCRITTO nel doc: il segnale villa-KBLI-OSS va a MINI-A/kbli-navigator (tu NON agisci sul KBLI). PROVE-LIVE: grep-audit finale del final gate sui pack pubblicati nel PR: zero nomi, zero numeri identificanti, zero verbatim.

SCOPE BAN: non toccare wa-mirror (corpse TCC su Mini — non è tuo), non fixare pipeline bot, non scrivere risposte/Q&A, non riesumare il miner CRM c7c07b650 (orfano scarred #1018).
GATE falsificabili: canary recall 100%; audit 50-item zero-leak firmato dal final gate; pack conteggi coerenti con wa_substantive_by_domain.json; zero contenuto verbatim; PR verde con auto-merge armato.
VINCOLI: zero paid API (ban ANTHROPIC_API_KEY assoluto); Legge 5 (nessun uso cliente-facing dei pack senza Zero); Legge 6; blocchi operator-only → PENDING-ARMS e avanti; quota morta → SOSPENDI, mai degradare il gate. CAPTURE: mem save + close line.
```

## 10. LAUNCH PROMPT — Session 3: MINI-ORGANISMO STEWARD

```text
MANDATO MINI-ORGANISMO STEWARD — cura del sistema nervoso della conoscenza (arsenale NotebookLM) + igiene dell'host Mini. Sei Fable 5 (max effort) su Mini (nuzantara@mini-pro2), cwd ~/Desktop/nuzantara. Skill: modus (dichiara GEAR). Edit/commit solo via subagenti Sonnet in worktree.

TWIN-GREP OBBLIGATORIO in apertura: (1) tmux ls && ps aux | grep 'claude --model' | grep -v grep; (2) gh pr list --state open + grep -iE 'notebooklm|nb-|matagaruda|launchagent|tcc|mini' su titoli + .claude/skills/modus/PENDING-ARMS.md; (3) leggi docs/plans/2026-07-19-mini-regia-conoscenza.md §7 claims (MINI-A non tocca questo fronte, ma verifica). Il fronte NB/host è tuo per claim; i contenuti KBLI/visa dei NB restano dei rispettivi corner.

FASI:
F1 NB-INVENTORY — rigenera reference_notebooklm_arsenal_full.md (34 giorni stale) via python scripts/nb_generate_inventory.py --write; verifica PRIMA dove può girare: nlm auth su Mini è vivo (provato 2026-07-19); se lo script è Pro-bound, esegui via ssh pro 'bash -lc ...'. PROVE-LIVE: file rigenerato con count atteso ~96 e data odierna, letto su disco.
F2 GARUDA-PIPE DIAGNOSIS — timeline a 3 EVENTI DISTINTI, non assumere causa unica: (a) freeze NB ~2026-06-14 (4 NB MATA GARUDA congelati a 102/89/51/57 sorgenti); (b) TCC mass-disable 2026-07-16 (7 plist .bak-tcc-20260716, inclusi 4 matagaruda + wa-mirror + gsc-sweep); (c) exit126 2026-05-10 (indexing-sweep). Traccia il pipe bali-intel-scraper→NB: dove si rompe DAVVERO (leggi log content, mai exit code — W84)? Cura ciò che è session-curable (codice/config/re-run/re-auth nlm). I grant TCC sono operator[TCC]: riga PENDING-ARMS con istruzioni precise per Zero (System Settings > Privacy, MAI tccutil reset — scar W84-recidiva 2026-07-08).
F3 CORPSE RECONCILIATION — per ciascuno dei 7 plist .bak-tcc + il .disabled-2026-05-10: verdetto con evidenza {revive-candidate | retire | operator-gated}. Regole: MAI rm (mv in .trash/); wrapper ricollocati FUORI ~/Desktop (famiglia #1/W84); LaunchAgent solo StartInterval+timeout, mai bare KeepAlive su one-shot (famiglia #7); MAI fs_usage/kernel-firehose. Ogni revive proposto = solo design+riga PENDING-ARMS se richiede TCC.
F4 OVERFLOW & CEILING — NB-INTEL-AIResearch-2 stallato dal 2026-06-30: ispeziona la logica auto-overflow di nlm_expander_agent.py (PR #924), diagnosi + cura se session-curable. Press+AIResearch a ceiling 500: PROPOSTA di dedup via nb-curator Mode C (proposta scritta, mai delete diretto). Ogni archive = quarantine + export-metadata-first, MAI delete — e comunque NON prima di F5.
F5 ACCOUNT-IDENTITY + DOC-TRUTH — risolvi la contraddizione account NLM (CLAUDE.md globale dice zero@balizero.com; 3 memorie live-verified dicono antonellosiano@gmail.com): verifica EMPIRICA (nlm profile/auth status) e correggi la riga in ~/.claude/CLAUDE.md. Correggi anche /Users/nuzantara/CLAUDE.md §"What's actually running here" — 3 falsità provate il 2026-07-19: (a) brew services NON è vuoto (postgresql@18 + redis started), (b) LaunchAgents NON sono solo-Google (30+ plist com.nuzantara/balizero/matagaruda), (c) Ollama ha 7 modelli non 4. NESSUNA operazione distruttiva/archive su NB prima di aver stabilito l'account proprietario.
F6 HEALTH-CHECK DESIGN + DECISION-MEMO (solo design, ZERO arm) — progetta il health-check 4-tier con alert Telegram (LaunchAgent StartInterval+timeout, wrapper fuori ~/Desktop, RAM budget dichiarato) e scrivi il decision-memo per Zero in research/operations/: (a) Qdrant-su-Mini: install path (brew formula vs binary — docker NON esiste su Mini), RAM budget su 24GB condivisi con la flotta Fable, backup/snapshot story, attribuzione Bali Zero vs NUZANTARA (charter §7 vieta daemon NUZANTARA su Mini); (b) migrazione cron pesanti da Pro: lista candidata con vincoli TCC; (c) target-store per l'ingestion Avvocato (accoppiato alla sessione AVVOCATO-BATCH che lo dichiara aperto). → riga PENDING-ARMS operator[Legge-5]: il memo propone, Zero decide.

SHIP+ARM — PR unica (branch via broker, gh pr merge --auto --squash a PR-open) con: doc research/operations/2026-07-19-mini-organismo-steward.md + fix dei 2 CLAUDE.md + eventuali cure codice (expander, pipe GARUDA). Spalla adversarial cross-family su ogni cura di codice. PROVE-LIVE per ogni cura: es. GARUDA = nuovo source_count > 102/89/51/57 al primo feed utile (se asincrono: receptor PENDING-ARMS, mai fake-check); inventory = file con data odierna letto su disco; CLAUDE.md = riga corretta letta su disco.
GATE falsificabili: inventory rigenerato oggi; diagnosi GARUDA con evidenza per-evento (3 eventi trattati separatamente); 8 corpse classificati con evidenza; zero delete (solo .trash/quarantine); memo Qdrant/cron consegnato; entrambi i CLAUDE.md corretti e verificati su disco.
VINCOLI: zero paid API (ban ANTHROPIC_API_KEY assoluto); Legge 5 (memo propone, mai esegue); niente daemon nuovi armati in questa sessione; blocchi operator-only → PENDING-ARMS e avanti; quota morta → SOSPENDI. CAPTURE: mem save + close line.
```
