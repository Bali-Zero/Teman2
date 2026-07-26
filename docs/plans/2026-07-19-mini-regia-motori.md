# MINI-A "Regia Motori & Prodotto" — 3 armed session mandates (2026-07-19)

> Conductor: Fable 5 session on Mini (MANDATO MINI-A). Method: Workflow recon (5 parallel readers)
> → 9 raw candidates from 3 angles → 7 consolidated → judge panel (Sonnet-native + Kimi K3
> cross-family; Codex gpt-5.6-sol seat DEAD on Mini — CLI 0.142.0 rejected server-side, declared,
> 2-seat heterogeneous panel accepted as degraded) → Fable final empirical gate (vault PDF, spec,
> branches, gold-content, deploy configs all re-probed on disk this session).
> Twin ledger: MINI-B "Regia Conoscenza & Organismo" runs in parallel on Mini with a disjoint
> perimeter (KB/corpus/CHATKB/WA corpus/Avvocato batch/Qdrant-cron); handoffs listed in §4.

## 1. Recon ground (live-verified, not presumed)

- **Pro** (probed via ssh, process-level): S2 GARUDA-FILIERA LIVE (Lot 7 conductor, extended GO
  through L9 → Batch-A remainder TAKEN) · S3 VISA ORACLE ENGINE LIVE (fresh session on
  mouth-visa-engine-pr1-0718; PR #2827 = engine→UI wiring spec; migration PRs #2840/#2824 open,
  deliberately not auto-armed → engine chain + STEP-6c TAKEN) · S4 IDENTITY-BACKFILL LIVE ·
  Intake Station 1+2 LIVE (#2787 Codex round-13) · meta-session 3-machine LIVE · Avvocato Totale
  charter PR #2814 open but idle.
- **M5** (probed via ssh jump): Wave conductor LIVE in tail-step (watcher on #2832/#2818/#2839);
  17 fresh worktrees; visa worktrees stale (Subhi lane probably-dead).
- **Landed today**: #2821 (navigator dataset resync, commit c320c9147) · #2813 (chat_kbli BKPM
  5/2025 capital doctrine) · #2826 (gold-content 68112/49213) · #2801 (Batch-B design REV-4b).
- **Ledger**: PENDING-ARMS 148 open lines; KBLI-relevant: 362 (kbli_documents whole-table),
  363 (consumer-map rule 6 — blocker #2788 now merged), 364 (ledger-vs-corner contradiction on
  cure apply — W88 class), 365 (KG variant nodes + search_kbli label). No capture-ledger artifact
  exists in the repo (the phrase in wr2 SKILL.md is a passing PR citation).

## 2. Candidates & panel

7 consolidated candidates: C1 Batch-B Phase-0 parser · C2 gold-content task #20 closeout ·
C3 kbli_documents truth substrate · C4 provenance-in-payload (inspect/search) · C5 Visa Track B
FASE 2 interview trees · C6 20 gold personas (G-b) · C7 RulePack content pilot.

Panel verdicts (leads, re-verified by the conductor): Sonnet-native top3 = C5, C1, C6 · Kimi K3
top3 = C1, C5, C4 (totals C1 20, C5 20, C4 19, C3 17, C6 17, C2 16, C7 15). Key panel findings
adopted: C6's DONE is unreachable without C5's trees (sequencing artifact, not a parallel
mandate); C1 had a generator=grader hole inside the §1.4 gate (truth labels must be frozen by a
blind cross-family lane BEFORE scoring); C2's deploy path is genuinely ambiguous (vercel.json AND
netlify.toml present, no CI deploy workflow — verified); C2's lane claim must be WRITTEN, not just
grepped. Conductor final pick: **C1, C5, C2** — C2 over C6 (active client-facing fabrication on
knowledge.balizero.com beats a sequenced artifact) and over C4 (C3+C4 fuse naturally into one
future backend session — benched, not discarded).

## 3. The 3 armed launch prompts (verbatim, Italian — paste-ready)

### MINI-A1 — Batch-B Phase-0: il parser È il censimento

```
MANDATO MINI-A1 — "BATCH-B PHASE-0: IL PARSER È IL CENSIMENTO". Sei Fable 5 (max effort) sul Mini
(nuzantara@mini-pro2), cwd /Users/nuzantara/nuzantara. Orchestratore e final gate — mai mani sul
codice: implementazione via subagenti Sonnet (tool Workflow/Agent — hai il mio opt-in esplicito).
Carica subito: /modus, /kbli-navigator, /workflow.

APERTURA OBBLIGATORIA (twin-grep, ~10 min): (1) git fetch origin --prune && git branch -r |
grep -iE "batch-b|bps|crosswalk|parse" e gh pr list --search "batch-b OR crosswalk OR parser" —
se esiste una lane viva sul parser, twin-velocity: concedi subito e chiudi. (2) Verifica su disco:
research/operations/2026-07-19-kbli-batch-b-design.md (spec FROZEN REV-4b — è la tua legge, non
re-litigare il design), ~/nuzantara-vault/bps/tabel-konversi-kbli-2020-2025-volume2-2026.pdf,
pdfplumber nel venv apps/backend-rag/.venv. (3) Rileggi le righe PENDING-ARMS su Batch-B.

OBIETTIVO (falsificabile): costruire scripts/kbli_filiera/parse_bps_crosswalk.py — estrazione
deterministica row-anchored dal PDF BPS Tabel Konversi Vol.2 (Lampiran 5 pp.131-246
KBLI2020→2025 + Lampiran 10 pp.325-444 reverse; `sebagian` come attributo first-class; uraian
title-diffing per i MATCH_LANGSUNG) — ed eseguire il gate §1.4 VERBATIM dalla spec: draw
stratificato digest-seeded 10 pagine/lampiran, tuning/holdout per rank parity, PASS = precision
AND recall ≥0.995 edge-level sull'holdout, scored EXACTLY ONCE. DONE = PASS o FAIL registrato con
l'artifact set congelato (parser_run_digest CON pin versioni pdfplumber+Python, page-rank table,
holdout scores) committato sotto data/kbli-filiera/ + report in research/operations/. Un FAIL
onesto è un esito valido del mandato — mai ritoccare il parser dopo lo scoring.

ANTI-SELF-GRADING (correzione del panel, vincolante): le truth-labels delle pagine campione
vengono adjudicate e CONGELATE PRIMA dello scoring da una lane cieca di famiglia diversa (Kimi K3
o GLM su render 300dpi; qwen2.5vl locale solo come locator, mai reader) — chi costruisce il
parser non etichetta le proprie pagine di verità. Codex gpt-5.6-sol è MORTO su Mini (CLI 0.142.0,
verificato 2026-07-19): cascata gpt-5.5 xhigh → Kimi K3 → GLM, dichiara il seat usato.

FASI: GROUND → BUILD in worktree via scripts/agent_start.py (lane kbli-filiera) → calibrazione su
2-3 pagine → run completo → truth-labels blind freeze → gate scoring una volta → VERIFY
cross-family sul report → SHIP: PR con auto-merge --auto --squash armato (codice+dati filiera,
non migration) → PROVE-LIVE: artifact rileggibili da origin/main post-merge → CAPTURE (mem save +
aggiornamento LIVE STATE del corner /kbli-navigator).

VINCOLI: scrivi il canonical SOLO via scripts/kbli_filiera/ (data-plane guard — sei nel perimetro
sanzionato). NON dispatchare alcun lotto Batch-B: le ratifiche Legge-5 di Zero (AQL default,
Tier-4 volume) sono operator[business] — la riga PENDING-ARMS esiste (aggiunta 2026-07-19),
verificala. Non toccare Batch-A (Pro S2, L6-L9 extended GO). Zero paid API; ban assoluto
ANTHROPIC_API_KEY (solo CLI OAuth). Mini 24GB: run pesanti in finestre separate dagli altri
build. PII: nessuna (dati regolatori pubblici).
```

### MINI-A2 — Visa Oracle Track B FASE 2: i 7 alberi comportamentali

```
MANDATO MINI-A2 — "VISA ORACLE TRACK B FASE 2: I 7 ALBERI COMPORTAMENTALI". Sei Fable 5 (max
effort) sul Mini (nuzantara@mini-pro2), cwd /Users/nuzantara/nuzantara. Orchestratore e final
gate; authoring via lane Sonnet + review cross-family (opt-in Workflow esplicito). Carica subito:
/modus, /visaoracle, /workflow.

APERTURA OBBLIGATORIA (twin-grep): (1) rileggi /visaoracle LIVE STATE — il claim "TRACK B claimed
by Mini/2026-07-17" è NOSTRO; verifica che nessuna riga nuova dichiari FASE 2 partita altrove;
grep research/visa/ per artefatti FASE-2 già nati (al 2026-07-19 sera: assenti, verificato). (2)
gh pr list --search visa — S3 (Pro) possiede l'engine (STEP-6*, #2840/#2824) e Track C
l'experience: NON toccare apps/backend-rag/backend/services/visa_engine/** né apps/mouth/**. Il
tuo scope ESCLUSIVO: research/visa/** + aggiornamento LIVE STATE del corner.

OBIETTIVO (falsificabile): alberi comportamentali completi — formato §3a-c di
research/visa/2026-07-17-visa-oracle-v2-round2-glm-interview-design.md (Q text EN/ID, opzioni,
why-we-ask con citazione normativa in-force, skip/unknown assumption che alimenta l'honesty
receipt, keeps/kills, review-gate markers) — per le 7 categorie ancora in HUMAN_REVIEW: Tourism &
short visit, Business (no work), Family & marriage, Retirement & second home, Study, Diaspora &
ex-WNI, "Something else" light-intake. Riconciliati con la fact-base FASE 1
(research/visa/2026-07-17-bridging-visa-branch-d7ab-diaspora-closeout.md: Bridging Permen Imipas
3/2025 Ps.45, D7A/D7B/D8A/D8B, diaspora) e col catalogo post-bonifica (110 indici Kepmen
M.IP-08/2025; BVK 19 stati). DONE = un file per categoria (o consolidato) sotto
research/visa/2026-07-19-*, OGNI albero passato da review adversarial cross-family con i claim
load-bearing esplicitamente non-refutati, LIVE STATE del corner aggiornato con l'avanzamento.

ORDINE: Tourism & short visit per primo (frequenza massima), poi Business, Family, Retirement
(qui NON sconfinare nel perimetro prodotto del corner /secondhome: solo logica intervista),
Study, Diaspora, Something else. Le 20 gold personas (criterio G-b ENFORCE) NON sono in scope —
sono il follow-up sequenziale dichiarato una volta che gli alberi esistono (verdetto panel: DONE
delle personas irraggiungibile senza gli alberi).

GATE cross-family: Codex sol MORTO su Mini → gpt-5.5 xhigh o Kimi K3 o GLM; generator≠grader
sempre; ogni numero/regola con fonte primaria in-force e freshness-check della fonte (W90). REGOLE
DI SANGUE: prezzo unico all-inclusive (ruling R1) — mai split PNBP/fee; Legge 5 — nessuna
decisione publish/demo. Worktree dedicato via scripts/agent_start.py (lane research). SHIP: PR
docs con --auto --squash armato. PROVE-LIVE = file su origin/main + LIVE STATE coerente. Zero
paid API; ban ANTHROPIC_API_KEY. PII: nessuna (personas future = sintetiche comunque; qui solo
logica).
```

### MINI-A3 — kbli-navigator gold-content: chiudere task #20

```
MANDATO MINI-A3 — "KBLI-NAVIGATOR GOLD-CONTENT: CHIUDERE TASK #20". Sei Fable 5 (max effort) sul
Mini (nuzantara@mini-pro2), cwd /Users/nuzantara/nuzantara. Orchestratore e final gate; edit via
subagenti Sonnet (opt-in Workflow esplicito). Carica subito: /modus, /kbli-navigator, /workflow.

APERTURA OBBLIGATORIA (twin-grep + CLAIM SCRITTO): (1) git fetch && git branch -r | grep -iE
"gold-content|task-20" + gh pr list --search "gold-content" — il task #20 nasce dall'audit M5
(#2826): se M5 ha una lane fresca, twin-velocity: concedi subito. (2) SCRIVI IL CLAIM nel primo
commit: riga "task #20 claimed by Mini/<data>" nel LIVE STATE del corner /kbli-navigator — il
claim scritto è il lock, il grep da solo non basta (verdetto panel). (3) PRIMA ORA — risolvi il
deploy-path: apps/kbli-navigator ha SIA vercel.json SIA netlify.toml e nessun workflow CI di
deploy (verificato 2026-07-19): stabilisci empiricamente come knowledge.balizero.com si aggiorna.
Se il deploy è operator-only → riga PENDING-ARMS e il DONE si ridefinisce su merge+build con
probe post-deploy delegato al receptor.

OBIETTIVO (falsificabile): riscrivere i 14 override quarantinati residui in
apps/kbli-navigator/lib/kbli-gold-content.ts (39001, 49296, 60103, 60203, 66159, 68123, 68125,
68126, 68127, 68129, 70100, 72101, 75001, 75009) col pattern honest-gap _data_note-grounded di
#2826 (68112/49213), ognuno ancorato al canonical data/source_documents/KBLI_2025_FINAL_CLEAN.json
(_data_note, per_skala_disputed_*, intel_2026.whatYouNeed) — MAI testo plausibile senza
provenance (regola corner #9). Cluster real-estate 68123-68129 per primo (pattern condiviso).
Fixa il bug tier-gating: content-presence bypassa GOLD_CODES (39001/49296/66159 renderizzano dal
ramo gold senza essere tier-gold). Test guilt+innocence per ogni codice. DONE = tsc --noEmit
pulito, next build (1,591 pagine SSG) verde, HTML built dei 14 codici verificato senza
fabbricazioni, PR merged con auto-merge armato, claim rilasciato nel commit di chiusura.

IN CODA (stessa sessione — reconcile night-close 2026-07-19): 3 PROVE-LIVE probes dovuti:
(a) #2813 in prod — chat_kbli su 50113: modal disetor 2,5 mld (BKPM 5/2025) e >10 mld/KBLI/lokasi
come numeri SEPARATI — mai sweep cieco su "10 miliar" (FATAL-3); (b) knowledge.balizero.com serve
canonical post-#2821; (c) corner post-#2823 (banale). Chiudi PENDING-ARMS #363 (consumer-map
rule 6, blocker #2788 merged). Documenta pass/fail di ogni probe nel report.

GATE cross-family: contenuto client-facing → review adversarial obbligatoria (gpt-5.5 xhigh /
Kimi K3 / GLM — Codex sol morto su Mini); generator≠grader; la sensibilità alza il rigore del
gate, non sposta mai il merge su un umano. VINCOLI: gold NON è data-plane-guarded — ogni edit
pinnato da regression test; non toccare il canonical (perimetro compiler filiera). Legge 5:
nessuna decisione business. Zero paid API; ban ANTHROPIC_API_KEY. Worktree via
scripts/agent_start.py. PII: nessuna.
```

## 4. Discarded / benched / handed off (one line each)

| Candidate/idea                                        | Verdict                   | Why                                                          |
| ----------------------------------------------------- | ------------------------- | ------------------------------------------------------------ |
| Visa wiring engine→/visa-oracle (mandate hyp. 3)      | DISCARDED (twin)          | S3 Pro LIVE owns it: #2827 is that spec; #2840/#2824 landing |
| KBLI Lot-8 industrialized (mandate hyp. 3 fallback)   | DISCARDED (twin-velocity) | Pro S2 extended GO covers L6-L9, mid-run now                 |
| C6 — 20 gold personas (G-b)                           | BENCHED (sequenced)       | DONE unreachable without C5 trees; next after MINI-A2        |
| C3 — kbli_documents truth substrate (#362/#364/#365b) | BENCHED                   | fuse with C4 into one backend session next window            |
| C4 — provenance-in-payload inspect/search             | BENCHED                   | fuse with C3 (same file/deploy); instrumentation, not cure   |
| C7 — RulePack content pilot                           | DISCARDED (premature)     | schema-drift risk while S3 iterates PR4-6 under it           |
| CHATKB company-kbli-signed-lots follow-ups            | HANDOFF → MINI-B          | curated_qa/cache cantiere perimeter                          |
| Mouth gold 63-phantom remap table                     | HANDOFF → MINI-B          | mouth curated corpus perimeter                               |
| WA corpus / Avvocato Assoluto batch                   | HANDOFF → MINI-B          | its charter perimeter                                        |
| kbli-navigator dataset desync lane                    | NOT ORPHAN                | M5 conductor-gated, #2821 landed today                       |

## 5. PENDING-ARMS lines added with this PR

1. Batch-B lots dispatch — Zero's Legge-5 ratifications (AQL default accept-or-override + Tier-4
   volume), operator[business]; Phase-0 parser lane (MINI-A1) explicitly does NOT dispatch lots.
2. Codex CLI on Mini stale (0.142.0): gpt-5.6-sol rejected server-side, red-team seat degraded on
   Mini; cascade gpt-5.5 xhigh / Kimi K3 / GLM meanwhile; upgrade in a quiet window + 1-token PONG
   as proof-of-armed.

## 6. Conductor final gate (blood-bought checks)

- merged≠live: every prompt ends in PROVE-LIVE on the consuming surface; A3 carries the 3 owed
  night-close probes explicitly. — consumer-map first: A3 resolves the knowledge.balizero.com
  deploy path in hour 1 before rewriting content; A1 writes only via sanctioned compilers.
- pin-after-data: A1 freezes truth labels BEFORE scoring and pins tool versions in the digest.
- twin-velocity: both mandate hypotheses that collided with live Pro lanes were conceded, not
  raced; A3 writes its claim in the corner as the lock.
- Empirically re-probed by the conductor this session: vault PDF (5,148,040 bytes), REV-4b spec
  (101,761 bytes), codex 0.142.0, zero colliding remote branches, gold-content 68127 fabricated
  block at line 10108, vercel.json+netlify.toml coexistence, no AQL line in PENDING-ARMS (hence §5.1).
