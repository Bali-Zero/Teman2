---
date: 2026-06-23
domain: operations
client_case: none (internal tooling / dev-stack)
sources:
  - https://developers.googleblog.com/build-with-google-antigravity-our-new-agentic-development-platform/ (primary)
  - https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/ (primary)
  - https://blog.google/innovation-and-ai/technology/developers-tools/google-io-2026-developer-highlights/ (primary)
  - https://techcrunch.com/2026/05/19/google-launches-antigravity-2-0-with-an-updated-desktop-app-and-cli-tool-at-io-2026/ (secondary)
  - https://www.theregister.com/software/2026/03/12/users-protest-as-google-antigravity-price-floats-upward/ (secondary)
  - Wikipedia: Google_Antigravity
  - LOCAL verification this turn: fleet M5+Pro+Mini disk-state (agy/gemini binaries + cron cascade scripts)
method: deep-research workflow (24 sources fetched, 110 claims, 25 adversarially verified 3-vote, 20 confirmed / 5 killed) + on-disk grounding M5/Pro/Mini
---

# Google Antigravity 2.0 — capability scan + piano d'integrazione Nuzantara

> **Verdetto in una riga:** Antigravity 2.0 NON è un tool nuovo da adottare — è la
> versione attuale di un tool che **abbiamo già installato e cablato** (`agy` = la
> Antigravity CLI). "Sfruttarlo a massima potenza" = smettere di usarlo solo come
> Tier-2 fallback, allinearlo su tutto il fleet, e chiudere la crepa `ai-dispatch.sh`
> che punta ancora al Gemini CLI morto. Claude Code resta l'orchestratore PRIMARIO.

## 1. Cos'è (verificato 3-0, fonte primaria)

Piattaforma **agent-first**, non un IDE (lo *contiene*). Modello "mission control":
agent che autonomamente **pianificano → scrivono codice → girano test nel terminale →
guidano un browser per verificare → si auto-correggono**, producendo **Artifacts**
(task list, piani, diff, screenshot, registrazioni browser) commentabili come un Google
Doc; l'agent incorpora il feedback senza fermarsi.

**Multi-provider per davvero** (3-0, contro 3 claim "solo-Gemini" caduti 0-3/1-2):
scelta del modello per-agent tra Gemini 3.5 Flash (default 2.0) / 3.1 Pro (High 1M ctx /
Low), **Claude Sonnet 4.6 / Opus 4.6 Thinking**, GPT-OSS 120B (400K ctx).
⚠️ "OpenAI" = solo GPT-OSS open-weight, NON GPT-5 proprietario.

## 2. Novità 2.0 (Google I/O, 2026-05-19) — 5 superfici, 1 solo agent harness (3-0)

1. **App desktop "Agent Manager"** — orchestra N agent in parallelo, subagent dinamici, task schedulati in background.
2. **Antigravity CLI in Go = `agy`** — più veloce del vecchio Gemini CLI Node, orchestra agent async in background.
3. **SDK** — definisci/ospiti agent custom su tua infra.
4. **Managed Agents API** (Gemini API) — spawn agent isolati con 1 chiamata → **path A PAGAMENTO per-token** (gate autorizzazione Zero).
5. Voice commands + export AI Studio.

Smentito (adversariale): NON è un rebuild da zero (0-3); È genuinamente multi-provider.

## 3. IMPATTO DIRETTO SUL NOSTRO STACK (3-0, primario + GitHub discussion)

**Gemini CLI spento il 2026-06-18**: da quella data Gemini CLI + Code Assist non
servono più richieste su abbonamento AI Pro/Ultra/free. Sostituto GA = **`agy`** (la
Antigravity CLI). Il vecchio Gemini CLI sopravvive SOLO via API key a pagamento o
Code Assist Standard/Enterprise — nessuno dei due è il nostro path (noi = AI Ultra OAuth).

### Stato reale del fleet (verificato su disco, path diretti, questo turno)

| Nodo | `agy` | `gemini` legacy | Note |
|---|---|---|---|
| **M5** | v1.0.10 ✅ | assente ✅ | cutover già pulito |
| **Pro** | v1.0.10 ✅ | 0.40.1 ⚠️ ancora su disco | binario morto presente |
| **Mini** | v1.0.8 ⚠️ (vecchio) | 0.40.1 ⚠️ ancora su disco | drift versione + binario morto |

> ⚠️ Il primo `command -v agy` via SSH ha dato FALSO NEGATIVO ("agy ASSENTE su Pro")
> perché il PATH del login-shell non-interattivo SSH non include `~/.local/bin`.
> I path diretti `~/.local/bin/agy` smentiscono: agy è vivo su tutti e 3.

### Crepa precisa (superscar #2 — verde-che-mente): `ai-dispatch.sh`

- `nb-curator-daily.sh` + `wr3_reflexion_synthesis.py` → usano `agy` correttamente ✅
- `ai-dispatch.sh` → **3 punti rotti** (identici su Pro e Mini):
  - `:255-256` modalità `gemini-*` fa `command -v gemini`; il binario ESISTE → check
    verde → ma le chiamate falliscono a runtime (endpoint OAuth morto dal 18/6). Verde su binario morto.
  - `:499/556/586` fallback NLM degradano a `gemini-explore`/`gemini-search` → ricadono sul CLI morto.
  - `GEMINI_MODEL_PRIMARY="gemini-3.1-pro-preview"` via vecchio CLI = path che non risponderà.
- **Non emergenza** (i due cron principali usano agy), ma `ai-dispatch.sh` è il
  dispatcher generale: ogni `gemini-search`/`gemini-explore` cade in silenzio.
- FIX = redirigere le modalità gemini-* di ai-dispatch.sh su `agy` (o rimuovere il fallback
  morto). Codice su file condiviso → worktree + OK Zero, NON di slancio.

## 4. Pricing/quota (AI Ultra) — 3-0 + 2-1

Bundled negli abbonamenti AI: Pro $19.99 · **Ultra $100 = 5× il limite Antigravity di
Pro** · Ultra $200 = 20×. Cap giornalieri → sostituiti da **pool di compute che si
rigenera ogni 5h fino a cap settimanale** + top-up pay-as-you-go. Bonus $100 una-tantum
GIÀ SCADUTO (2026-05-25). Coerente col nostro Ultra rinnovato 21/05 (10k Flow cr/mo + 2500 AI cr).

## 5. Vs Claude Code — "senza duplicare"

Differenziatore Antigravity = Agent Manager desktop + loop verifica-via-browser +
Artifacts. MA Claude Code ha già worktree-broker, subagent dispatch, workflow paralleli,
MCP browser. La research ha BOCCIATO 1-2 il moat "agent paralleli" (Cursor/Windsurf li
hanno aggiunti). → **Installare l'Agent Manager desktop = rischio orchestration-decay +
duplicazione, non guadagno.** Claude Code resta orchestratore primario; `agy` resta
specialista long-context / quota-overflow.

## 6. Sovranità dati / PII (UU PDP, SYMBIOSIS Law 2) — hard boundary

Antigravity è CLOUD: gli agent mandano codice/contesto/browser-state ai modelli Google.
Accettabile SOLO per NON-PII (research regolatoria, sintesi dati pubblici, codice su file
non-PII, ingestion long-context di corpora pubblici). MAI PII cliente (KTP, passport,
NPWP, akta, OSINT/WhatsApp-mirror raw) → restano locali (Ollama Pro/Mini). Coerente con
posture `agy` esistente. (Law-2 alleggerita Art.56 ha eased il transito, ma OUTPUT-PII
resta non-negoziabile + gap aperto DPA/consenso → default conservativo: non-PII only.)

## 7. Piano operativo (checklist eseguibile)

- [ ] **#1 — Allinea versione agy su Mini** (1.0.8 → 1.0.10): `agy upgrade` o re-install. Non-PII, banale.
- [ ] **#2 — Fix `ai-dispatch.sh`** (Pro+Mini, e M5 se presente): redirigi modalità `gemini-*`
      + fallback NLM su `agy`; rimuovi il check `command -v gemini` che dà verde su binario morto.
      → worktree + commit atomico + OK Zero (file condiviso, hot-zone dispatcher).
- [ ] **#3 — Sfrutta `agy` async multi-agent per batch long-context** dove già eccelle:
      inventario 60-NB, multi-PDF research, mappe refactor 1M ctx. Capability ADD, non replace.
- [ ] **#4 — NON installare** app desktop Agent Manager (duplica Claude Code). Salvo esperimento isolato M5.
- [ ] **#5 — NON cablare** SDK / Managed-Agents-API senza autorizzazione Zero (path Gemini API a pagamento per-token).
- [ ] **#6 — Rimuovi/archivia** i binari `gemini 0.40.1` morti su Pro+Mini (igiene, evita falsi-verdi futuri).

## Open questions (dalla research)

1. Quota AI Ultra Antigravity weekly compute-pool reale per il nostro pattern d'uso? Il
   modello 5h-refresh cambia come il cascade dovrebbe rilevare quota-exhaust (vecchi grep
   "out of extra usage|quota exceeded" potrebbero non matchare i nuovi messaggi).
2. Model-label/routing-fidelity: quando chiediamo Gemini 3.1 Pro high-reasoning per
   synthesis, lo otteniamo davvero? (forum complaint non verificato — assert empirico se conta).
3. L'Agent Manager desktop aggiunge qualcosa che il worktree-broker + subagent dispatch di
   Claude Code non danno già per solo-dev parallelo? (default: no → non installare).

## Caveat

Prodotto fast-moving. Sunset Gemini CLI 18/6 è LIVE (non teorico). Roster modelli drifta
(Sonnet 4.5 al lancio nov-2025 → 4.6/Opus 4.6 ora; Opus 4.7 non ancora nel picker alle
fonti). Comparazione IDE-vs-IDE = direzionale, non benchmark-grade (fonti secondarie). Fix
ai-dispatch.sh verificato su disco questo turno ma NON ancora testato a runtime.
