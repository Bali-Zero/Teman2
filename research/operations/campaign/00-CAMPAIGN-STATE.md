# CONNECTOME CAMPAIGN — stato condiviso (shared-context layer)

> **Questo file è L'UNICA fonte di verità dello stato di campagna.** Ogni sessione (L0/L2/L3, su qualsiasi
> macchina) lo rilegge al risveglio PRIMA di agire e lo aggiorna a ogni gate-round. È il rimedio al
> context-inconsistency (causa #1 di fallimento multi-agente, ricerca 2026).
> **Path identico su ogni macchina:** `~/Desktop/nuzantara/research/operations/campaign/00-CAMPAIGN-STATE.md`
> (su M5 attualmente nel worktree `infra-tac-loop-megapattern`; verrà mergiato su main per la propagazione).

---

## 0. Genesi e mandato
- **Data avvio:** 2026-06-15
- **Mandato (Zero):** chiudere tutti i loop + trovare tutti i mega-pattern + audit completo + security/Law2 + knowledge-freshness + meta-loop. Autonomia: **trova + chiude tutto tranne firebreak FISICI**. Nessun limite di sessioni.
- **Super-Osservatore (L0):** sessione M5 interattiva di Antonello+Claude (questa). NON esegue lavoro: vigila, raccoglie effect-receipt, decide firebreak fisici, fa gate finale.
- **Fondamento ricerca:** orchestrator-worker (Anthropic, 70% prod, +90% vs single) · reliability compounding 95%^N · context-inconsistency = causa #1 · token ~15× giustificato · parallelismo solo su task indipendenti. Refuter cross-AI OBBLIGATORIO.

## 1. Topologia (verificata su disco 2026-06-15, account aggiornati)
| Host | RAM | Account Claude | Arsenale extra | Ruolo campagna | Max runner SICURO |
|---|---|---|---|---|---|
| **M5** balizero@Air-M5 | **24GB** | **antonellosiano@** (sianoantonello@ esaurita → torna ven) | agy(Gemini Ultra), codex(ChatGPT Pro ×20), ollama→mini, deepseek | **L0 Super-Osservatore + L2 lane META/ricerca-aperta** | **1 worker** (24GB, GUI interattiva) |
| **Pro** nuzantara@Nuzantara | 48GB | **2 indipendenti** (default + kaiser…@acct2) | codex, ollama, deepseek; claude=alias .zshrc (`bash -lc`) | **L2 lane RUNTIME/SECURITY** (canali, CRM, Law2, deploy) | **4 worker** (2 account) |
| **Mini** nuzantara@mini-pro2 | 24GB | **antonellosiano@** (condiviso con M5) | agy, codex, ollama(6), deepseek, 8 MCP validi | **L2 lane AUDIT-PESANTE/KNOWLEDGE** (RAG/KG/eventbus, KBLI/visa/tax) | **2 worker** (Ollama compete RAM) |

### 1bis. Quota Claude — calibrazione (NON è "risparmia Claude", è "moltiplica con l'arsenale")
- **Claude resta motore PRIMARIO di ogni lane.** Codex (ChatGPT Pro ×20, illimitato, OAuth VIVO) + Gemini (Google AI Ultra, VIVO) + DeepSeek + Ollama sono **potenza AGGIUNTIVA in parallelo**, non sostituti.
- **Unica accortezza:** M5 e Mini condividono `antonellosiano@` → stessa finestra rolling-5h. Si danno il turno se la finestra si stringe.
- **Cascade = RETE DI SICUREZZA, non default:** se la quota `antonellosiano@` si esaurisce a metà campagna, la lane NON si ferma → casca su Codex/Gemini per esplorazione+code+refuter (Ollama per PII). Il gate-finale-Opus aspetta che la finestra si riapra (qualità non degrada). Venerdì torna `sianoantonello@` → si ribilancia a 1 account per macchina.
- **Pro è isolato** (2 suoi account) → non tocca la quota condivisa M5/Mini.

- **Redis lease backbone:** Mini `localhost:6379` = PONG (verificato). Arbitro cross-machine unico.
- **Broker worktree:** `scripts/agent_start.py` (39k). **Hook armati e verificati LIVE** (host_boundary + worktree_isolation hanno bloccato write reali in questa sessione).
- **Dispatcher multi-AI:** `scripts/ai-dispatch.sh` (60k, machine-detection + cascade).
- **Max runner concorrenti totali: ~7** (1 M5 + 4 Pro + 2 Mini). NON è il massimo possibile, è il massimo SICURO (banda di verifica del Super-Osservatore + reliability compounding).

## 2. Assegnazione lane → macchina (con razionale)
| Lane | Fronte | Macchina | Razionale |
|---|---|---|---|
| **L-META** | Salute loop apprendimento (#11): failure-injection su ogni loop verde-vuoto + antidoti (arm-gate CI, heartbeat-consumo, promote-gate). Ricerca aperta mega-pattern/scar nuove. | **M5** | tocca hook/cron/loop-logic = dominio dev; M5 ha gli hook da testare |
| **L-RUNTIME** | Audit canali WA/TG/IG, intake, CRM (live) | **Pro** | i canali GIRANO sul Pro (deploy worktree presente) |
| **L-SECURITY** | Security + sovranità Law2: secret in chiaro (#4), PII boundary, OSINT leak, deps/supply-chain | **Pro (ESCLUSIVO)** | firebreak fisico: OSINT/PII non lasciano il Pro (§13). DeepSeek key vive qui. |
| **L-AUDIT** | Audit organismo per-anatomia: RAG/backend, KG, eventbus, WR2/WR3, deploy | **Mini** | read-heavy + Ollama bulk; H24; main 0-behind |
| **L-KNOWLEDGE** | Knowledge freshness + correttezza dominio: KBLI/visa/tax/property, citazioni regolatorie, golden corpus | **Mini** | ground-truth NLM/Gemini + bulk re-embed Ollama |

## 3. Costituzione di sicurezza (NON-NEGOZIABILE — vale per OGNI runner)
1. **Worktree-per-lane + main read-only** (`agent_start.py`). → previene #5 sibling-race.
2. **Account-per-host rigido.** Mai 2 host sullo stesso account. → quota + #10 split-brain.
3. **Lease Redis FAIL-CLOSED per le CHIUSURE** (override del graceful-degrade): Redis down → leggere OK, committare/armare NO.
4. **Gate a 5 cancelli prima di OGNI chiusura autonoma:** (0) grounding prova-in-questo-turn · (1) refuter indipendente su AI DIVERSO, mai self-review · (2) test di EFFETTO (non "i test passano") · (3) classificatore confine L2/L3 (hard) · (4) audit-write PRIMA dell'azione.
5. **Confine L2-safe vs L3-firebreak (HARD):**
   - **L2-safe (runner autonomo):** commit in lane-owned non-hot-zone · aprire PR (MAI merge) · docs/research/memory · fix reversibili con prova-di-effetto · implementare BUILDER items in PR.
   - **L3-FIREBREAK (SOLO Zero):** armare/modificare cron o LaunchAgent · hot-zone (auth/billing/pricing/migrations/.github/workflows) · `~/.claude/` · propagate cross-machine via scp · merge su main · off-limits (`zantara_core.py`, `fly.toml`, `.env*`, `alembic/env.py`) · route flip WA · grant TCC GUI · account.
6. **Heartbeat di EFFETTO, non di esistenza** (#11): exit 0 / "done" / PID NON contano. Conta la terna: (a) delta su disco/stato verificabile · (b) prova-di-causa (comando prima→dopo) · (c) refuter-ack ID. Zero-delta ripetuto = TEATRO → sospendi + scala.
7. **Rollback:** solo azioni reversibili sono L2. Commit→revert (mai force-push/--amend su pushed). Audit-pre obbligatorio. Nuovo orphan-stash non attribuibile = sibling-race in atto.
8. **PII assoluto:** KTP/passport/NPWP/akta/credentials/OSINT → SOLO Ollama-locale. MAI DeepSeek/Gemini/Codex/cloud.
9. **Riserva quota 20%** per macchina intoccabile (per spegnersi in sicurezza). Chiusura NON degrada di modello: se MAX esaurito → chiusura in PAUSA, non con modello debole.

## 4. Dispatch multi-AI (quando-chi)
- **Width / sintesi 2°ordine:** Gemini 3.5 Flash High (default) / 3.1 Pro High (solo sintesi finale) via `agy`.
- **Code / BUILDER / migration test:** Codex GPT-5.5 (illimitato), sandbox `read-only|workspace-write`.
- **Refuter avversariale (non-PII):** DeepSeek V4 Pro `reasoning_effort=high` ($0.01/q).
- **Refuter/processing PII:** Ollama locale Mini (6 modelli).
- **Ground-truth dominio:** NotebookLM via MCP (bipolar verifier).
- **Gate finale on-disk:** SEMPRE Opus (L0/L2). Il padre rifà il grep (W65).

## 5. Effect-receipt (formato che ogni runner emette per ciclo, su path noto)
```json
{"host":"", "lane":"", "task_id":"", "account":"", "git_sha_before":"", "git_sha_after":"",
 "files_touched":[], "artifact_proof":"", "cause_command":"", "cause_exitcode":0,
 "refuter_id":"", "refuter_verdict":"", "lease_held":[], "ts":""}
```
Scritto in `research/operations/campaign/receipts/<host>-<lane>-<taskid>.json`. Il Super-Osservatore li RI-VERIFICA (non si fida del receipt: ri-legge sha, ri-esegue cause_command).

## 6. Registro LIVE (aggiornato dai runner — append)
> Formato: `[TS] HOST/LANE — stato — link finding/receipt`
- [2026-06-15 init] M5/L0 — campagna creata, file-stato + 3 prompt scritti. In attesa di lancio runner.

## 7. Backlog mega-pattern / scar / da-tracciare (cresce durante la campagna)
- #11 Costruito≠Efficace — già identificato (TAC 2026-06-15). Bozza in `2026-06-15-tac-loop-closure-megapattern.md` §6.6. **Da promuovere** in cicatrix-superscar.md (L3, decisione Zero).
- GOTCHA "verificatore-non-verificato" — da agganciare a #2/#6.
- _[i runner aggiungono qui ogni candidato pattern/scar trovato]_

## 8. §Residuo Operatore Puro (cresce — ciò che SOLO Zero può fare)
- WR2 cutover (route flip + bootout Canva + finestra WA Meta) — Legge 5.
- INTAKE FASE 5C (`INTAKE_WRITER_ENABLED`).
- Grant TCC su M5 (Full-Disk-Access launchd/bash) — riarma 2 guardiani morti.
- Promozione Lesson Harvester (shadow→enforcement).
- deploy/main branch decision.
- _[i runner promuovono qui ogni firebreak fisico incontrato]_

## 9. PRE-FLIGHT 2026-06-15 (testato end-to-end, non assunto)
| Macchina | Claude | Codex | Gemini(agy) | NLM | Redis | host_boundary | venv backend | Verdetto |
|---|---|---|---|---|---|---|---|---|
| **M5** | ✅ antonellosiano@ (live) | ✅ | ✅ loggato | ✅ loggato | ✅ (→Mini) | ✅ | ✅ | **PRONTA** |
| **Mini** | ✅ loggato (haiku risponde) | ✅ | 🔴 NO auth | 🔴 auth scaduta | ✅ PONG (backbone) | ✅ | ✅ | **quasi** (agy+nlm login) |
| **Pro** | 🔴 default=401, acct2=not-logged | ✅ | 🔴 missing | — | ✅(→Mini) | ✅ | ✅ | **BLOCCATA** (claude login) |

### Blocchi reali (richiedono atto umano interattivo — firebreak fisico, login OAuth):
1. **Pro Claude**: default account = `401 Invalid credentials` (scaduto), acct2 = `Not logged in`. Binario OK (`~/.local/bin/claude`, ma non in PATH → usare path assoluto). → serve `claude /login` su ENTRAMBI gli account Pro (dallo schermo Pro o tmux interattivo).
2. **Mini agy (Gemini)**: NO auth → `agy login` interattivo (OAuth Google).
3. **Mini nlm (NotebookLM)**: auth scaduta → `nlm login` interattivo (la lane KNOWLEDGE ne dipende).

### Falsi-allarmi smontati (trap, NON blocchi):
- "claude binary assente su Pro" → FALSO: esiste, solo non in PATH (`~/.local/bin` non incluso). Il problema vero è l'AUTH (401/not-logged), non il binario.
- "repo Mini rotto" (sessione precedente) → FALSO: era trap cd-via-ssh; repo sano (main, 0 behind).

### Mezzi CONFERMATI presenti ovunque (dall'inizio alla fine del lifecycle):
broker agent_start.py · lease agent_lease.py · ai-dispatch.sh · redis backbone (Mini PONG) · host_boundary md5 uniforme · venv backend-rag · tmux · codex (illimitato, vivo) · ollama (Mini 6 modelli incl qwen2.5vl vision).

## 10. PRE-LANCIO check 2026-06-16 — GIÀ FATTO da sessioni parallele (NON duplicare!)
> Intuizione operatore: controllare cosa hanno fatto le altre sessioni PRIMA di lanciare. Ha evitato 3 duplicazioni.
- ✅ **DLQ corpse-sweep auto-drain** (#1471 MERGED, Opus 4.8) = era il nostro BUILDER L-OP-3 (data-loss). Chiude heal-loop cieco non-registry (W70/W81b). 14 corpses drenati. → **lane AUDIT: NON ricostruire il DLQ replay; verifica solo che il sweep giri davvero (failure-injection).**
- ✅ **lifecycle-guard "the vase empties itself"** (597f6fe25, antonellosiano@) = **antidoto #11 GIÀ in corso** (auto-GC che AGISCE non avvisa; nato da "chi svuota il vaso? non io"). BONUS sicurezza: rimossi 2 secret (JWT+QDRANT_KEY) nascosti nei permission entries. → **lane META: costruisci SOPRA questo (heartbeat-di-consumo + promote-gate), NON da zero. È la prova vivente di #11.**
- ✅ **Law 2 PII output boundary** chiarito (#1476 + 5263eb50f) → **lane SECURITY: il PII-boundary base è fatto; concentrati su secret-in-chiaro residui (il GC ne ha già trovati 2 → cercane altri) + OSINT-leak + deps.**
- ℹ️ Altro lavoro vivo (non sovrappone): intake NIB/akta filing (#1475), WR2 full-bleed carousel + ban-cliché (Pro), deps bump (82+6+4), team photos (#1469), npm-audit esbuild (worktree Pro).
- ⚠️ **Sessioni VIVE ora:** Pro = Codex (app-server+chronicle+computer-use) + guardrails daemon + rsync→damar. M5 = 9 worktree attivi. → i runner DEVONO usare lease Redis (collisione reale possibile). Verifica `agent_lease list` prima di toccare un file.
