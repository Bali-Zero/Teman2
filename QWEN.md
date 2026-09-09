# QWEN.md — Nuzantara Project Rules per l'ala Token Plan (Qwen · GLM · MiniMax)

> Per ogni agente/client che opera via Alibaba Model Studio Token Plan (regione Singapore):
> Qwen 3.8 Max, Qwen 3.7, GLM 5.2, MiniMax 2.5, Wan. Legge madre: `AGENTS.md` (§0.0 + §17).
> STATUS: **PROBATION** — load-bearing solo dopo PROBE-1 (API key, burn-rate, qualità).

<!-- CANON:builder-contract -->

## THE BUILDER CONTRACT — identical in every door, compared by machine

This block is the same in `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` and `QWEN.md`, and
`scripts/proprioception.py`'s `door_canon_parity` probe goes RED if any copy drifts from
`CLAUDE.md`'s. "The same" is what the machine actually enforces, not more: the comparison
hashes the block with TRAILING whitespace and line endings normalised away, so an editor that
strips or adds them is not drift — and anything else, including one reworded sentence or one
extra space mid-line, is. It exists because the CI layer already binds every model equally — a gate does
not care which family opened the PR — while the harness layer did not: a seat that BUILDS used
to start with whatever its own door happened to say. **Do not reword this block in one door.**
Fix it in `CLAUDE.md` and copy it outward, or the probe will name your door.

**1 — PR contract.** One PR, one concern, ≤ ~400 net lines where the work allows. Arming means
freezing: after auto-merge is armed, the branch is read-only and every follow-up starts from a
fresh `origin/main`. Never rerun a red check before you know WHY it is red — the right gesture
depends on the cause, and a blind rerun replays a stale merge ref. Serialize PRs that share a
lockfile. Work in a dedicated worktree on an `agent/<host>/<lane>/...` branch. Three reds for
the SAME cause and the PR suspends instead of taking a fourth round; a fix-of-a-fix stops at
depth 1 — if the correction is itself wrong, the surface is under-specified, so write the spec.

**2 — Every PR body carries a `Bites:` line** naming the CONSUMER and the observation that
proves the change is in force. "A future job will run it" is not a consumer: the job ships in
the same PR. Make the observation before reporting the work done — a merged diff is not a live
one, and this repo's scar record is mostly the distance between those two.

**3 — Bans, stated as an ENTITY and not as a spelling.** What is forbidden is reaching a Claude
model through a **paid per-token Anthropic endpoint** — because the subscription is already paid
and a per-token key duplicates it. The sole sanctioned path is the `claude` CLI with
`CLAUDE_CODE_OAUTH_TOKEN`. `from anthropic import Anthropic` and `ANTHROPIC_API_KEY` are the two
shapes that usually carry it, and grepping for them is a useful first pass — but an alias, a
renamed env var, a wrapper library or a Bedrock/Vertex route reaches the same endpoint without
either literal, and is equally banned. Refuse any new tool, MCP server or cron that requires it. Other paid per-token APIs are not banned but are not
yours to install: they need the owner's explicit authorization first. Never `--dangerously-bypass`
a sandbox; never echo, print or commit a credential — `${VAR:+SET}` reports presence,
`${VAR:-default}` prints the value.

**4 — PII boundary, and it is an OUTPUT boundary.** Processing client data under an authorized
lane is allowed; transcribing it is not. No output, memory, log, alert, report, skill, prompt
saved for reuse, or shared artifact may carry client PII or OSINT in cleartext — use a
`client_id`, a hash, a placeholder or a redaction. This binds every vendor identically: there is
no cloud whose terms make cleartext PII acceptable here, and no seat exempt from it.

**5 — Ship sequence.** The session that owns a mandate runs it end to end: review → merge → arm
→ deploy → prove-live. The codeowner does not merge, does not review and does not deploy — by
design. Arm auto-merge at PR-open. Push, create and merge are three SEPARATE commands, never a
compound one. What stays with the human: business decisions, credentials and consents, and
physical/GUI actions. **The one exception both ways:** an external builder seat (`AGENTS.md`,
`GEMINI.md`, `QWEN.md`) prepares and never ships — it does not merge, arm or deploy its own
work, and a Claude session verifies it. Generator is never grader, in either direction.

<!-- /CANON:builder-contract -->

---

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
- Mai merge, mai deploy, mai output client-facing, mai pubblicazioni **di propria iniziativa** (Legge 5) — l'unica deroga nominata (ordine esplicito di Zero o Damar da canale autenticato, gate dell'artefatto verdi) è definita in `AGENTS.md` §0.0 punto 2, che governa anche te; non ri-derivarne l'estensione da questa riga.
- Worktree discipline (AGENTS.md §0.5) per ogni mutazione; off-limits files invariati.
- Lingua: italiano con Zero, inglese per codice/commit.
- Roster completo modelli × punti di forza × effort di TUTTA la flotta: `MODEL_ROSTER.md` (repo root) — leggilo prima di scegliere un seat (ruling Zero 2026-08-14).
