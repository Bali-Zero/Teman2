# qwen.md — Nuzantara Project Rules per l'ala Token Plan (Qwen · GLM · MiniMax)

> Per ogni agente/client che opera via Alibaba Model Studio Token Plan (regione Singapore):
> Qwen 3.8 Max, Qwen 3.7, GLM 5.2, MiniMax 2.5, Wan. Legge madre: `AGENTS.md` (§0.0 + §17).
> STATUS: **PROBATION** — load-bearing solo dopo PROBE-1 (API key, burn-rate, qualità).

## 0. Ruoli categorici (roster 2026-08-09)

| Modello                           | Ruolo                                                                                                                                             | Mai                                                                                                                                                                                              |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Qwen 3.8 Max**                  | IL TERZO POLO — 3ª lettura strategica nei panel; esecutore pipeline a istruzioni rigorose; motore doc/video di massa NON-PII; GUI-agent recintato | estrazione compliance-exact NON verificata (debolezza documentata: allucina su formati esatti); coding hot-zone da solo; PII; quote cliente                                                      |
| **Qwen 3.7**                      | LA RISERVA — secondo parere economico, batch di seconda linea                                                                                     | load-bearing                                                                                                                                                                                     |
| **DeepSeek v4-pro/v4-flash/v3.2** | IL SECONDO RAGIONATORE — reasoning second-opinion, refuter reserve (eligible_for_quorum: false)                                                   | PROBATION; riammesso da Zero 2026-08-10 (il ritiro 2026-07-19 fu morte economica del seat standalone 402, non un verdetto di qualita'); PII: parità vendor dal 2026-08-24 (regole comuni, v. §4) |
| **GLM 5.2**                       | IL CONTRO-COSTRUTTORE — contro-implementazioni parallele (il diff coi candidati Sonnet entra nel pack); refactor long-horizon; spike              | architettura di sistema; client-facing; merge                                                                                                                                                    |
| **MiniMax 2.5**                   | IL MACINATORE — throughput: test ripetitivi, docs, batch (dopo PROBE-4)                                                                           | qualità non verificata da un seat Anthropic                                                                                                                                                      |
| **Wan**                           | media-gen, radar WR2 — non attivo                                                                                                                 | —                                                                                                                                                                                                |

## 1. La riga più importante

Il nostro mestiere è **compliance esatta** (KBLI, visti, scadenze, numeri fiscali) e Qwen 3.8 Max ha
tassi di allucinazione documentati SUPERIORI ad Anthropic/Google proprio sull'estrazione a formato esatto.
**Quindi: ogni estrazione exact-format prodotta da questa ala richiede verifica indipendente
(seat Anthropic/Google, o doppia estrazione convergente) PRIMA di entrare in qualsiasi flusso.**

## 2. Meccanica API

- Endpoint: OpenAI-compatible (DashScope) **e** Anthropic-Messages-compatible (baseURL dedicato) — i client CLI esistenti si riconfigurano senza riscrittura.
- `reasoning_effort`: `none|low|medium|high/max` (Qwen; budget max 262k) — MAI sovrapporre `thinking_budget` numerico nello stesso payload. GLM: `max|high` + **`clear_thinking: false`** obbligatorio negli agent coding (altrimenti perde il tracciato decisionale tra tool call).
- Tool calling Qwen in thinking mode: NON supporta la forzatura server-side della chiamata → il controller locale valida SEMPRE schema+permessi (fail-closed).
- Cache: prefissi stabili in testa esatta al prompt (implicita $0.25/M); sessioni iterative → cache esplicita (`x-dashscope-session-cache: enable` + `previous_response_id`, lettura $0.17/M). MAI timestamp/ID casuali dentro il system prompt (invalidano l'hash).
- Rate: 2M token/min, 15k req/min. Finestra economica Qoder (se inclusa nel piano): off-peak 14:00–00:00 UTC = **22:00–08:00 WITA** → lane batch notturna.
- Key: `~/.qwen/settings.json` env `BAILIAN_TOKEN_PLAN_API_KEY` — file 0600 OBBLIGATORIO (era 0644 world-readable, corretto 2026-08-10); 15 modelli censiti 2026-08-10.

## 3. Budget crediti

Il Token Plan è a **crediti mensili** (pool, non per-token puro). Ogni job batch dichiara una stima crediti
nel Task Brief; il burn reale si logga nel ledger arsenal (PROBE-1 stabilisce i burn-rate per modello).
Crediti esauriti → la catena di fallback di `FLEET_TOPOLOGY.json` decide; mai comprare overage senza GO di Zero.

## 4. Confini Nuzantara (identici a tutti gli external agent)

- PII cliente: parità vendor (RULED Zero 2026-08-24 — limite CN/SG abolito a livello di sistema): stesse regole comuni di Anthropic/OpenAI — frontiera-output Law 2 + cascata Art. 56 per i trasferimenti PROD. SEA-LION/locale resta la prima scelta per costo/latenza, non per recinto.
- Mai merge, mai deploy, mai output client-facing, mai pubblicazioni (Legge 5).
- Worktree discipline (AGENTS.md §0.5) per ogni mutazione; off-limits files invariati.
- Lingua: italiano con Zero, inglese per codice/commit.
- Roster completo modelli × punti di forza × effort di TUTTA la flotta: `MODEL_ROSTER.md` (repo root) — leggilo prima di scegliere un seat (ruling Zero 2026-08-14).
