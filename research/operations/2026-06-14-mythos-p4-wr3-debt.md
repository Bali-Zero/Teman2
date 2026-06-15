---
date: 2026-06-14
domain: operations
client_case: false
sources:
  - research/operations/specs/WR3-DEBT-INDEX.md
  - research/operations/specs/WR3-supervisor-revival.md
  - research/operations/specs/WR3-F18-evoskill-zero-pressure.md
  - research/operations/specs/WR3-F20-manifest-validator-incompatible.md
  - research/operations/specs/WR3-F21-reflexion-cron-theater.md
  - .claude/rules/cicatrix-scars-archive.md (W74)
  - Gemini 3.5 Flash (High) second-order synthesis (this session)
  - Codex GPT-5.5 adversarial refuter (this session)
  - live disk/PG re-verification 2026-06-14 (this session)
---

# OPUS MYTHOS — P4 · WR3 feature-debt: i loop di apprendimento "verdi ma vuoti"

> Sessione Mythos 1/8. Organo: il **sistema di apprendimento di WR3** (la video-room) —
> tre loop di auto-miglioramento (F18 evoskill, F20 manifest-validator, F21 reflexion)
> diagnosticati come "armed but inactive / green but empty", più il supervisor a monte.
> Mandato: ESEGUIRE le spec già scritte con giudizio Mythos, nell'ordine giusto.

## §0 — Executive

**Tutto live-ri-verificato su disco questo turno** (le spec hanno 2 giorni; W74 phantom-citation
guardrail). Le spec NON erano phantom — il **checkout main locale era stale** (`e2b355f45` dietro
`origin/main 3d5dd1da3`); su origin/main le 5 spec + W74 esistono. Correzione path evoskill della
spec verificata corretta (`vendor/evoskill/src/cli/shared.py:229`, NON `cli/scorer.py`).

| Step | Stato pre | Cura eseguita | Done (OUTPUT live-verificato) |
|---|---|---|---|
| **STEP-0 supervisor** | sano+idle, exit 74, siccità producer (2 righe outbox, newest 2026-05-22) | B1: heartbeat 2.0→8.0s env-gated (toglie il churn che ha causato la mis-diagnosi "FAILED") | 16/16 test reconnect verdi; dispatch provato **free** da 24 test esistenti |
| **F20 validator** | dead code; manifest reale 17 chiavi → hard-fail 4 gate | normalizer real→schema + `finalize_episode_manifest` + enum `PASS-WITH-NOTES` + wiring-point | il **manifest REALE su disco** normalizzato **VALIDA** (18 campi, 27 claim_ids, cosine 0.79) — 8 test |
| **F21 reflexion** | stub 816B `sys.exit(0)`, cron nemmeno loaded | port reale 314-righe WR2→file-based + **Delta Gate** + plist versionato + install | **live run reale**: 5 episodi → claude Sonnet → **5 lessons.md genuine scritte** — 5 test |
| **F18 evoskill** | infra sana, 0 proposte (curriculum risolto 100%) | **ESCALATO** (perimetro + 402): raccomandazione + scoperta DeepSeek-402 | §Solo-operatore |

**114/114 test WR3 verdi**, zero regressioni. **Zero credito Veo speso**, zero mutazione prod
events_outbox, zero plist hot-edit. Le cure F20/F21 sono shippate come **codice+test indipendenti**
dal supervisor (l'osservabilità live end-to-end resta gated sull'episodio = budget operatore).

## §1 — STEP-0 Supervisor (la premessa era sbagliata, e QUELLO è il finding)

La spec revival aveva già corretto il DEBT-INDEX ("FAILED exit=78"); io ho **ri-verificato live 2026-06-14**:

- `launchctl print` → `state=running`, pid 13712 (~3h up, KeepAlive ok), **last exit 74 EX_IOERR** (dal wrapper, non 78). Sano e idle.
- PG (read-only, Fly): `events_outbox WHERE channel LIKE 'wr3_%'` → **2 righe TOTALI, newest `2026-05-22T16:45:16`, 0 unconsumed**. Siccità producer confermata.

Il supervisor è un **consumer event-bus sano con nulla da consumare**. "Revival" ≠ "riavvia daemon morto".

**Refuter (Codex GPT-5.5) CLAIM-2 — HOLDS con un overstatement, e ha ragione:** io avevo detto
"nessuna prova free del dispatch". Falso: la **logica consume→route→ack è provabile free** e **già
unit-testata** — 24/24 test (`test_wr3_outbox_replay`, `test_wr3_supervisor_reconnect`,
`test_wr3_idempotence`) passano con fake-PG, zero Veo, zero prod. Ciò che NON è free è l'end-to-end
**produttore-reale → agenti-reali → Veo render** = budget operatore.

**Cura eseguita (B1, in-perimetro `scripts/wr3_supervisor.py`):** il timeout `_heartbeat` era 2.0s
hardcoded; su un `fly proxy` tunnel idle questo auto-triggerava ~102 reconnect in 495 righe di log su
un daemon **perfettamente sano**, producendo lo stale exit-74 che il DEBT-INDEX ha mis-letto come
"FAILED exit=78". Alzato a **8.0s env-gated** (`WR3_HEARTBEAT_TIMEOUT`) — cattura ancora il half-open
TCP (scar zombie 2026-05-22), ma non spara sull'idle. Curo così la **causa-radice della confusione
stessa**. 16/16 test reconnect verdi (passano `timeout=2.0` esplicito → testano il meccanismo, non il default).

## §2 — F20 manifest-validator (dead code reso reale)

Live-verificato: il manifest reale `content-creator-3-roads-2026-05-29/episode_manifest.json` ha **17
chiavi**, `critic_verdict="PASS-WITH-NOTES"`, `claim_ids=None`, `wr3_room_version=None` → `validate_manifest`
hard-fail ai gate `:125/:129/:134/:141`. Il validator era cablato in NULLA (il producer è un prompt
free-form a `wr3_supervisor.py:403`, non `ManifestBuilder.write()`).

**Cura (opzione (a)-come-normalizer, in `scripts/wr3_episode_manifest.py`):**
- `normalize_assembler_manifest(raw, *, brief, identity_report)` — mappa real→schema (slug→topic,
  duration_s→duration_master_ms, vo_lufs→lufs_measured, render_cost_cr→flow_credits_spent, variants
  dict→variants_delivered, master_mp4.sha256→asset_hashes) e **deriva** i campi mancanti dagli artefatti
  fratelli (`claim_ids` da `brief.regulatory_citations[].claim_id`, cosine da `identity-report.json`).
- `finalize_episode_manifest(episode_dir)` — il **wiring-point** che il handler `assembly_ready`/CI deve
  chiamare DOPO che il post-assembler scrive: legge → normalizza → valida → scrive `episode_manifest.normalized.json`
  (NON sovrascrive l'originale — difesa in profondità).
- Enum `PASS-WITH-NOTES` aggiunto a `ALLOWED_VERDICTS` — **decisione deliberata e flaggata** (§Solo-operatore):
  è il verdetto che il critic LIVE emette davvero, escluderlo era il bug.

**Refuter CLAIM-1 — BREAKS ("fossilizza un normalizer da UN manifest"):** valido in parte, e mitigato:
ho aggiunto `test_malformed_future_manifest_fails_loud` (verdetto sconosciuto → REJECTED, non fake-green) +
`test_no_claim_ids_still_rejected` (il validator NON è sdentato). Residuo onesto: un manifest con campi
numerici `None` ma chiavi presenti passa il gate-presenza — il contratto di stringere i tipi è una
decisione di schema dell'operatore (non l'ho allargato unilateralmente).

## §3 — F21 reflexion (lo stub-teatro reso synthesizer reale)

Live-verificato: stub 816B `sys.exit(0)` (S7.3 placeholder); WR2 reale 314 righe; **cron wr3 nemmeno
loaded** in launchd (solo `wr2.reflexion` lo è) → F21 ancora più vuoto della spec.

**Cura (port reale, `scripts/wr3_reflexion_synthesis.py`):** port fedele del WR2 da SQLite a **file-based**
(legge gli episode dir + i verdetti, costruisce il prompt, cascade claude Sonnet→Gemini, scrive ≤10
lessons.md per agente + skill draft). Plist versionato in `infra/launchagents/` (punta alla deploy-worktree
come il supervisor → chiude il fix-b durabilità) + `install_wr3_reflexion.sh`.

**Incorpora la contromisura del Meta-pattern (vedi §Meta) — il DELTA GATE:** ogni run appende a
`_reflexion-state.json` `{episodes_found, lessons_written, status}` con `status ∈ {SYNTHESIZED, THIN_SIGNAL,
NO_INPUT, LLM_FAILED}`. Un run senza episodi NON è un `sys.exit(0)` silenzioso → scrive `NO_INPUT`, così
l'operatore VEDE "12 settimane NO_INPUT" invece di scambiare il verde per apprendimento. Un fallimento LLM
con episodi presenti → exit 1 + `LLM_FAILED` (rumoroso, non verde-finto).

## §4 — F18 evoskill (zero-pressure → ESCALATO)

Live-verificato: `seed-patterns.csv` = 31 righe scar-derived, `runner.py:319` pass-bar 0.8, `:327
if len(failures)==0: continue`. Infra sana; 0 proposte BY CONSTRUCTION (curriculum risolto ~100%).

**Scoperta Mythos collaterale (load-bearing):** il refuter DeepSeek che dovevo usare è tornato **HTTP 402
Insufficient Balance**. L'evolver F18 usa `deepseek-v4-pro` come harness E scorer → **oggi crasherebbe
comunque sul 402** (doppiamente morto: zero-pressure *e* giudice non-funzionante). Il 402 colpisce l'intero
tier DeepSeek.

**Decisione Mythos (dichiarata) + ESCALATA:** NON eseguo. Il fix è **operator-decided** per 3 ragioni
convergenti: (1) il cron plist `com.balizero.agent-library-evolver.weekly` è **fuori dal mio perimetro WR3**
(è un plist agent-library, dominio P2); (2) `vendor/evoskill` è vendored upstream (la spec dice "no runner.py
change") — non lo forko; (3) un curriculum diventa la ground-truth del giudice → richiede panel review.

**Raccomandazione (informata da Gemini + Codex, convergenti):** suspend-vs-curriculum è un **falso binario**
(Codex). Il terzo è un **readiness-gated scar-replay** — e quel modello **esiste già nel repo**
(`agent-library/scar_replay/scar_replay.py`: "Gate 1 — baseline MUST fail (proves real headroom)"). Quindi:
non far girare il cron-proposta ora (doppiamente futile); quando si rifà, il curriculum deve venire da scar
REVISIONATE dove la baseline FALLISCE davvero (scoring locale fail-before/pass-after), e DeepSeek deve generare
candidati solo da finanziato. Dettaglio operatore in §Solo-operatore.

## §Meta-pattern — perché i 3 loop sono "verdi ma vuoti" (il vero topic)

Sintesi di 2° ordine (Gemini 3.5 Flash High, gate-ri-verificato da me; refuter Codex convergente):

**La malattia-delle-malattie: "Omeostasi Tautologica" (la mimica del loop vuoto)** — la convinzione che la
**correttezza formale del ciclo** (il cron esce 0) equivalga all'**impatto di stato** (il sistema evolve).
Si confonde la *telemetria di processo* con il *delta di stato persistente*.

È un **fratello distinto** dei meta-pattern già catalogati dell'organismo:
- *"Esistere ≠ Armato"* (W64/W71) è **statico**: lo scudo c'è ma non è cablato.
- *"Catalogare, non curare"* (connectome TAC) è **passivo**: indicizzi il bug, non lo curi.
- *"Omeostasi Tautologica"* è **attivo-ingannevole**: la macchina corre sul tapis roulant e **produce
  attivamente telemetria verde** per mascherare l'assenza di avanzamento. Radice comune: **evitamento
  dell'attrito reale** (cicli progettati per non poter mai fallire né segnalare).

3 evidenze trasversali (stessa radice):
- **F18**: motore di ottimizzazione nutrito con un dataset risolto al 100% dall'inizio → 0 fallimenti
  garantiti → report "green/zero proposals" by design.
- **F20**: guardiano perfetto (18 campi) a presidio del nulla; l'agente reale produce output non conforme
  senza collisione né allarme.
- **F21**: blocco vuoto che ritorna `sys.exit(0)` invece di `NOT_IMPLEMENTED`/exit 1, spacciando l'assenza
  di codice per esecuzione riuscita.

**L'angolo contrarian (decisivo per F18):** i learning-loop sono l'istanza **più insidiosa** perché la loro
salute ideale (la **convergenza**, propongo 0 perché ho imparato tutto) è **fenomenologicamente identica**
alla loro morte clinica (l'**inerzia**, propongo 0 perché il curriculum è rotto/il giudice è 402). La
tautologia si maschera da perfezione.

**Contromisura strutturale (Gemini, "Mutation & Delta Gate") — l'ho applicata a F21 e la raccomando per tutti:**
nessun loop di feedback è "Healthy" se non passa un test a 2 fattori: (1) **failure-injection** (inietta un
input rotto, verifica che il loop ALLARMI davvero); (2) **state-delta** (se il delta persistente resta 0 per
N cicli → degrada forzatamente da "Healthy" a "Degraded/Futility Run"). Il Delta Gate di F21
(`_reflexion-state.json`) è la prima implementazione concreta; F20 ottiene il fattore-1 via i test
fail-loud; F18 ottiene entrambi via il readiness-gate scar_replay già esistente.

## §Terapia-eseguita (verifica LIVE dell'OUTPUT per ciascuno — Done ≠ exit code)

- **F21 — LIVE-PROVEN end-to-end:** `WR3_REFLEXION_WINDOW_DAYS=30 wr3_reflexion_synthesis.py` contro gli
  episodi REALI + claude Sonnet REALE → `SYNTHESIZED: 5 lessons from 5 episodes`; **5 file lessons.md** scritti
  (libass-probe, rerender cost-attribution, b-roll ArcFace coverage, cliche-library WARN, jurisdiction tokens);
  delta-gate `_reflexion-state.json` registra `SYNTHESIZED`. + 5 unit test (NO_INPUT≠silent-exit, in-window→lessons,
  LLM-fail→exit-1, old-episode→NO_INPUT, cap-at-max).
- **F20 — LIVE-PROVEN:** `finalize_episode_manifest()` sul **manifest REALE su disco** → `VALIDATED OK`,
  18 campi, 27 claim_ids derivati, cosine 0.79, `PASS-WITH-NOTES` accettato. + 8 unit test (raw-fails,
  normalized-passes, verdict-accepted, no-claims-rejected, malformed-fails-loud, finalize-writes-sibling,
  real-on-disk).
- **STEP-0 B1 — TEST-PROVEN:** 16/16 reconnect/watchdog; dispatch consume→route→ack provato free da 24 test.
- **Regressione:** 114/114 test WR3 verdi.

## §Solo-operatore (confine — traccia e fermati)

1. **Budget Veo — STEP-0 A1 (innescare un episodio reale).** È l'UNICO modo di provare l'end-to-end live, ma
   spende credito Veo (10 cr/clip × ~18 clip) + muta `events_outbox` prod + invoca agenti reali a cascata.
   **NON eseguito autonomamente.** Quando vuoi: invoca `wr3-design-architect` ("produce WR3 episode for
   [topic non-PII]") con `WR3_DRY_RUN=false`. Il supervisor (già LISTENing, sano) lo dispatcha → produce un
   manifest reale che `finalize_episode_manifest` (F20) validerà e che il reflexion (F21) sintetizzerà.
2. **F18 — decisione suspend-vs-readiness-gate.** Raccomandazione: NON far girare il cron-proposta ora
   (doppiamente futile: zero-pressure + DeepSeek 402). Esecuzione = tua (plist fuori perimetro WR3). Comando:
   `launchctl bootout gui/$(id -u)/com.balizero.agent-library-evolver.weekly`. Re-enable solo con (a) un
   curriculum di scar-revisionate-baseline-failing + (b) DeepSeek finanziato.
3. **DeepSeek 402 (Insufficient Balance)** — operator item a sé: blocca l'evolver E qualunque agente tier-3
   DeepSeek. Ricaricare il saldo o cascadare quegli agenti.
4. **Enum `PASS-WITH-NOTES`** — widening deliberato del set verdetti. Se "PASS-WITH-NOTES" NON deve contare
   come pass per i consumer downstream, dimmelo e lo mappo a `DEGRADED`.
5. **Post-merge (Pro):** `bash infra/launchagents/install_wr3_reflexion.sh` per bootstrappare il cron F21
   (il target script esiste in nuzantara-deploy solo dopo merge+sync); poi opzionale convertire/cancellare
   lo stub HOME `~/.claude/skills/bali-zero-brand/wr3/_reflexion-synthesis.py`.

## Appendice — dispatch multi-AI usato

- **Gemini 3.5 Flash (High)** via `agy`: §Meta-pattern (Omeostasi Tautologica + Mutation/Delta Gate). ✅
- **DeepSeek V4 Pro** refuter: **DOWN 402** → sostituito.
- **Codex GPT-5.5** refuter sostitutivo: 3 verdetti adversariali (CLAIM-1 BREAKS, CLAIM-2 HOLDS+overstatement,
  CLAIM-3 BREAKS-as-framed) — tutti ri-verificati da me (gate round-2 W65) e incorporati (test fail-loud,
  raffinamento STEP-0, terzo-opzione F18). ✅
- **Gate finale: Opus (io)** — ogni claim ri-eseguito su disco/PG/pytest questo turno.
