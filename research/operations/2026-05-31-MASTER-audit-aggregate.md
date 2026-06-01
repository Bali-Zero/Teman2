---
date: 2026-05-31
domain: operations
client_case: none
sources:
  - research/operations/2026-05-31-rag-truth-FROZEN.json (S2, PR #971)
  - .worktrees/audit-quote-redteam-2026-05-31/research/operations/2026-05-31-quote-redteam-FROZEN.json (S3, commit c9cca1fc8)
  - research/operations/2026-05-31-organism-truth-FROZEN.json (S1, PR #989)
  - research/operations/2026-05-31-structural-debt-FROZEN.json (S4, PR #992)
  - research/operations/2026-05-31-system-audit.md (health-audit, run iniziale)
author: Claude Opus 4.8 (1M context) — orchestratore, numeri ri-verificati da disco/MCP
status: COMPLETE — 4/4 audit done
---

# MASTER aggregate — 4 heavy audits, notte→mattina 2026-05-31

> Tutti i numeri qui sotto sono stati **ri-verificati dall'orchestratore via disco + postgres-MCP**,
> non copiati dai summary degli agenti (che hanno avuto PR# fantasma da output intermedi + sibling-race).

## Verdetti per audit

| #   | Audit                | Verdetto                          | Output                         |
| --- | -------------------- | --------------------------------- | ------------------------------ |
| S2  | RAG-truth vs NB      | ⚠️ PARZIALE per causa strutturale | PR #971 OPEN                   |
| S3  | Quote red-team       | 🔴 GRAVE                          | commit c9cca1fc8 (non pushato) |
| S1  | Organism (167 plist) | 🔴 GRAVE (sicurezza)              | PR #989 OPEN                   |
| S4  | Structural debt      | 🔴 1 bomba esplosa in prod        | PR #992 OPEN                   |

---

## 🔴 LA BOMBA: deploy-worktree desync — ROTTO IN PRODUZIONE ADESSO (S4 #2)

**Verificato dall'orchestratore 09:21:**

- `~/Desktop/nuzantara-deploy` è un **symlink** (creato 01:53 stanotte) → `.worktrees/backend-rag-crm-guardian-audit`
- branch del target: `agent/nuzantara/backend-rag/crm-guardian-audit` (NON `deploy/main`)
- `~/logs/wr2-deploy-pull.log`: `ERROR: deploy worktree on branch=(unknown), expected deploy/main` (ripetuto, hourly, alert cooldown-suppressi)

**Impatto:** WR2 production cron legge **codice stale**, operator-invisibile. È la **terza incarnazione** della scar deploy-desync 2026-05-25 — stavolta via symlink che ha pure ingannato il `test -e .git` di S4 (corretto a exploded-silent via `git worktree list`).

**Fix (needs-Antonello):** ri-puntare `~/Desktop/nuzantara-deploy` a un worktree pulito su `deploy/main`. NON fatto in autonomia (tocca lo stato deploy condiviso).

---

## 🔴 S3 — l'organo che firma quote ai clienti ha 2 difetti critici (verificati nel codice)

| ID       | Difetto (verificato dall'orchestratore nell'agente)                                                                                                             |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| STRUCT-1 | L'agente `client-case-quote-generator` ha `tools: Read,Write,Edit,Bash,WebFetch` — **ZERO PricingTool**. Prezzi da user-input/DeepSeek-math. Viola §8.11/Law 11 |
| STRUCT-2 | Riga 85 usa `"model":"deepseek-reasoner"` (deprecato) → silent downgrade a **v4-flash** → tutta la math fiscale a qualità flash mentre crede reasoner           |
| STRUCT-4 | Gate `devils-advocate` single-LLM (vs 4-LLM promessi) + non fail-closed                                                                                         |

**Numeri:** 3 quote testate, **0/3 send-ready**, 15 difetti (2 crit + 8 high). would-harm-client = rischio illimitato finché gate+price-source non ripristinati.
**Onestà:** PricingTool RBAC-bloccato → agente ha letto il file catalogo (1054 righe) invece di inventare; verdetti legali tutti DOUBT (panel+DeepSeek giù); 0 PR fabbricati.
**Fix needs-Antonello:** i 3 fix toccano `~/.claude/agents/` (fuori-repo) → decidere se editare lì o portare l'agente sotto version-control.

---

## 🔴 S1 — organism: 167 plist, sicurezza compromessa

**Verificato da disco (organism-truth-FROZEN.json): 167 plist → 120 🟢 / 40 🟡 / 7 🔴.**

- **8 plist con secret INLINE in chiaro** (ricomparsa scar 2026-04-29): TELEGRAM_BOT_TOKEN, GH_TOKEN, BALIZEROBOT_TOKEN, DATABASE_URL — in `intel.nightly`, `post-publish-poller`, `wa-mirror-*` (×3), `canva-lease-watchdog`, `federation-alert-dispatcher`, `sentinel`. Di cui 2 erano world-readable 644 → **S1 le ha chmod 0400 (fix shipped PR #989/#992)**, le altre needs-rotation.
- **5 plist binary-missing** (RED): `wr3.supervisor`, `wr3.editorial-bench`, `wr3.yt-metrics`, `wr2.canva-renderer`, `cleanup-ttl-sentinel` — wrapper in `~/.openclaw/bin/` cancellati ma plist ancora LOADED → falliscono al prossimo trigger.
- **4 reboot-bomb** one-shot (NON KeepAlive — sarebbe respawn storm W61; serve StartInterval).
- state-bridge W61: ✅ ALIVE + KeepAlive (remediation 2026-05-28 regge). 0 dead-but-alive reali.

---

## ⚠️ S2 — accuratezza RAG NON misurabile (muro strutturale)

- **RBAC blocca il bipolar verifier:** tool query Zantara (`ask_legal`/`chat_kbli`) rifiutano caller role `unknown`, `get_failed_queries` 401, nessun endpoint RAG non-auth. → 0 confronti Zantara-vs-NB completati → accuracy `null` (non inventata).
- **🔴 corpus claims corrotto:** `nlm_nbX_claims.jsonl` (nb3-6) pieno di dump errore CLI come claim_text, source_ids degradati, claim_id mislabeled `NB2-`. Solo nb2-visa pulito. → baseline-oracolo metà spazzatura.
- UUID NB veri verificati live (corretta una trappola: UUID nel contesto erano sbagliati). Cross-check tax PPN 11% effective converge con ground-truth.
- **needs-Antonello:** service-role credential per sbloccare il braccio Zantara + pulire il corpus claims.

---

## S4 — verdetto 10 cicatrici (ri-verificato)

**rolsuper W38 ARMATA — confermato dall'orchestratore via postgres-MCP:** 8 superuser role (`backend_rag_v2`, `backend_ts_user`, `flypgadmin`, `nuzantara_memory`, `nuzantara_rag`, `postgres`, `repmgr`, `zantara_rag_user`). Spec DRAFT, NON eseguita.

| Verdetto            | Scar                                                                                   |
| ------------------- | -------------------------------------------------------------------------------------- |
| 🔴 ESPLOSA-SILENTE  | #2 deploy-worktree desync (vedi sopra)                                                 |
| 🔴 ARMATA           | W38 rolsuper · #5 test-infra mock≠prod · #6 sibling-race · #10 plist-overwrite         |
| 🔴 PEGGIORATA       | W62 worktree orfani (8 vs 6) · #8 KeepAlive 53→167 plist                               |
| ✅ risolta-di-fatto | #4 mata_garuda (Pro 23/Mini 5, zero overlap) · #7 EventBus doc · #9 migrations 129/130 |

**7 di 10 armate-o-rotte, 3 risolte.**

---

## Fix SHIPPATI (autonomia L2) vs needs-ANTONELLO

### Shippati (verificati via gh, OPEN auto-merge)

- **PR #971** (S2): FROZEN + report RAG-truth — docs only
- **PR #989** (S1): FROZEN + report organism — docs + cicatrix scar
- **PR #992** (S4): FROZEN + report debt + **chmod 0400 sui 2 plist secret world-readable** (l'unico fix di stato, additivo+backup)
- S3: commit `c9cca1fc8` non pushato (agente target fuori-repo, valore = report)

### needs-ANTONELLO (per blast-radius)

1. 🔴 **Fix deploy-symlink rotto** — ri-puntare `~/Desktop/nuzantara-deploy` a deploy/main (WR2 prod legge stale ADESSO)
2. 🔴 **rolsuper W38 demotion** — spec pronta, mai eseguita (top bomb sicurezza)
3. 🔴 **Ruotare i secret esposti** nei plist (GH_TOKEN, Telegram, DATABASE_URL) + trovare il producer del plist-overwrite
4. **Fix agente quote** (deepseek-v4-pro, PricingTool access, gate fail-closed) — decidere version-control fuori-repo
5. **Pulire corpus claims** `nlm_nbX_claims.jsonl` + service-role per sbloccare audit RAG
6. 5 plist binary-missing (decommission/restore) · 4 reboot-bomb (StartInterval) · 5 log /tmp→~/logs · demote altri 7 superuser role

---

## Note di metodo (per i prossimi audit)

- **4 Opus max-effort in PARALLELO = suicidio quota** (bruciato il 5h-window in 13 min, 1° tentativo). **In SERIE funziona** (questo run: 4 audit completati uno alla volta senza ribruciare).
- **args via Workflow si svuotano** → passare prompt come **file-path** (fix che ha funzionato).
- **Sibling-race REALE e attiva** (scar #6): S1 si è fatto wipare il branch mid-sessione, S4 ha avuto il branch-name riusato da un sibling. Gli agenti l'hanno gestita verificando via `git cat-file`/`git show` invece di output intermedi.
- **PR# fantasma:** i summary degli agenti citavano PR#/commit da output intermedi mai persistiti. SEMPRE verificare via `gh pr view` + disco.
