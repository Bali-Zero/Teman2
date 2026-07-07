# PROMPT — sessione Mini / Lane L-AUDIT + L-KNOWLEDGE (anatomia organismo + freschezza dominio)

> **Come lanciare:** su Mini via `ssh mini` → `bash -lc "claude"` (claude 2.1.177, path-abs ok). Modello Opus, xhigh.
> Mini ha **1 account** + Ollama (6 modelli) che compete per i 24GB → MAX **2 worker claude** concorrenti;
> se lanci bulk-Ollama-eval, scendi a 1 worker claude per non OOM.
> **PRIMA di tutto** leggi `~/Desktop/nuzantara/research/operations/campaign/00-CAMPAIGN-STATE.md`.

---

## MANDATO L-AUDIT (incolla questo)

Sei Lane-Lead L2 della Connectome Campaign, lane **L-AUDIT**, su Mini (workhorse H24). Carica `opus-mythos`.
Leggi PRIMA il file-stato §3 (costituzione) + §6 (registro) + **§10 (GIÀ FATTO — non duplicare!)**.

⚠️ **§10 — il DLQ è GIÀ chiuso:** il "corpse-sweep auto-drain" (#1471 MERGED) chiude l'heal-loop cieco del DLQ.
**NON ricostruire il DLQ replay.** Per l'EventBus/DLQ il tuo compito è SOLO: failure-injection per verificare che
il sweep giri DAVVERO (inietta un corpse → viene drenato?). Se sì, marca verde e passa oltre.

**Obiettivo:** TAC per-anatomia dell'organismo — un fan-out di worker, UNO per organo, ognuno caccia bug/debito/teatro/scar-nuove. Organi:
- **RAG/backend** (`apps/backend-rag/backend/`): reasoning, orchestrator, abstain-policy (2 path live, domanda #31 SSOT aperta), evidence scoring. Caccia bug logici.
- **KG** (`kg_subgraph_property.py` ecc.): knowledge graph, langgraph federation.
- **EventBus** (`services/events/event_bus.py`): durabilità per-canale (Law3), replay, outbox. Channel-consumer parity. (DLQ replay = già fatto #1471, solo verifica failure-injection).
- **WR2/WR3**: pipeline carousel/video — stato armamento (0 job launchd?), reflexion, critic gate. NOTA: Pro sta già lavorando su WR2 carousel — coordina via lease, non collidere.
- **deploy/CI**: workflow .github, squawk lint, required checks (CODEOWNERS gate exit-0 LYING noto).

Per ogni organo: spawna 1 worker (Sonnet) in worktree → trova → refuter (DeepSeek/Codex) verifica → tu (Opus) gate finale. Usa Ollama locale per scansioni bulk (grep semantico, classificazione) per risparmiare quota.

**Output:** `research/operations/campaign/findings/mini-audit-SUMMARY.md` (per organo: bug confermati, debito, scar candidate) + effect-receipt.

---

## MANDATO L-KNOWLEDGE (incolla in una seconda sessione SE RAM lo consente, altrimenti dopo L-AUDIT)

Sei Lane-Lead L2 della Connectome Campaign, lane **L-KNOWLEDGE**, su Mini. Carica `opus-mythos`. Leggi file-stato §3.

**Obiettivo:** knowledge-decay + correttezza di dominio (continua l'audit Fable5 del 13/06 che trovò 8 P0).
- **Sito/KB pubblici** (`apps/mouth/`): KBLI 2025, visa, tax-calendar, property. Citazioni regolatorie stale? (LKPM 10th→15, paid-up 2.5B, SABH/NIB, PP 20/2026). Campagne a scadenza: KBLI 18/06, RUPS 30/06.
- **Golden corpus** (`apps/evaluator/zantara_persona_eval/golden_corpus.json`): valida con `validate_corpus.py`. Coverage dominio sufficiente?
- **Ground truth**: usa NotebookLM (MCP, bipolar verifier) per verificare i fatti regolatori. NB-3 Company, NB-4 Tax, NB-5 Property. Gemini per width sul corpus.
- **Bridge WA freshness**: il bridge WhatsAppRAG cita norme correnti? (era 100% CURRENT al 13/06 — riconferma).

**REGOLE knowledge-specifiche:** i fatti regolatori vanno verificati contro NLM (ground-truth), MAI inventati. Domanda di dominio → bipolar verifier (1 LLM + 1 NB), non 4-LLM council. Correzioni sito = L2-safe (PR mai merge); NON toccare `apps/backend-rag/backend/kb/` (curato — Legge convention §15).

**Output:** `research/operations/campaign/findings/mini-knowledge-SUMMARY.md` (P0/P1 freshness, con NB-citation) + effect-receipt.

---

## REGOLE COMUNI (da §3 costituzione)
- Worktree: `python scripts/agent_start.py --lane audit|knowledge --task-id <slug>`.
- Gate 5-cancelli. Refuter AI-diverso, mai self-review. Lease FAIL-CLOSED per chiusure (Redis è QUI su Mini localhost:6379 — sei il backbone, non farlo cadere).
- L2-safe = commit + PR (mai merge) + docs. L3-firebreak (NO): cron, hot-zone, kb/ curato, off-limits, merge main, propagate.
- Heartbeat-di-effetto. Ollama vs claude competono RAM: finestra-temporale, non simultaneo se OOM-risk.
- Aggiorna §6/§7/§8 del file-stato. Non fermarti finché ogni organo + ogni fronte-knowledge non ha verdetto verificato.
