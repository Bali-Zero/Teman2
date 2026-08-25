# DIRETTIVA OWNER #1 — bot team: cervello, scope agentico, memoria
(Da Zero via la sessione design M5, 2026-08-25. Emenda il MANDATE `docs/plans/2026-08-25-due-bot-live/MANDATE.md`. Dove contraddice F4/F5/F8, vince questa direttiva; tutto il resto del mandato resta congelato.)

## 1. CERVELLO DEL BOT TEAM — deciso da Zero (sostituisce F8-primario)
- **Primario: `qwen3.7-plus` via porta TP1 Alibaba** (token plan già armato, endpoint Singapore, slug esatti via `GET /models` — mai dedurre dalla tabella; `max_tokens` copre thinking+risposta, thinking≈0 per i turni tool).
- **Catena di fallback, in ordine**: `qwen3.6-flash` (stessa porta, assorbi-burst/economico) → `glm-5.2` (stessa porta, slot-filler obbediente) → **modello locale Qwen sul Mini in sola-lettura** (terza corsia di degradazione: quando il cloud è giù risponde solo ai tool R0 e lo dice).
- Slot predisposto per `qwen3.7-flash` via API key Model Studio (~$3,4/mese): entra come primario quando Zero autorizza la key — cambio via flag/env, cervello pluggabile.
- **Allarmi depletion token-plan a 30% e 10%** + circuit breaker che degrada a sola-lettura (mai bot morto muto). Vincolo PII: Zero ha derogato per questo lane (documenti con consenso cliente già raccolto) — la deroga è per il bot team; Law 2 frontiera-output resta (mai PII in log/memorie persistite in chiaro).
- Conseguenza su B4: l'impianto locale si RIDIMENSIONA a terza corsia (un solo modello, tool R0, niente eval multilingua estese) — il grosso di B4 diventa l'adapter TP1 (client HTTP, error taxonomy, breaker, depletion probe).

## 2. SCOPE AGENTICO AMPLIATO — deciso da Zero (emenda F4/F5)
- Il vincolo "un tool per turno" resta SOLO sulle MUTAZIONI (una mutazione per turno, sempre confermata). **Letture e ricerche: catene multi-step libere** (alza MAX_STEPS a un valore sensato, es. 8, con loop-detector e budget). I gradi di autonomia non si allentano: letture libere · bozze comunicazione → conferma · scritture CRM → conferma con preview · invii al cliente → conferma · distruttivo mai.
- **Mappa capacità a 8 domini** (rollout: v1 = domini 1-4; v2 = 5-7; v3 = 8):
  1. Pratiche & CRM (il set F5 esistente — `team_crm_tools.py`, preview→confirm→commit).
  2. **Documenti in chat**: foto/PDF inoltrati su WhatsApp → OCR locale qwen2.5vl → classificazione → aggancio pratica → checklist aggiornata → "manca: X". Riusa document-intake-classifier + media_download del canale WA.
  3. Scadenze & compliance: sweep KITAS/LKPM/SPT per i MIEI clienti, promemoria proattivi (template utility). Riusa compliance-deadline-sentinel + S7.
  4. Conoscenza & prezzi: ask_legal/visa/kbli/pricing via MCP nuzantara-knowledge, con citazioni, mai a memoria.
  5. Comunicazioni al cliente: draft brand-voice nella lingua del cliente, invio SOLO dopo conferma. Riusa email-template-builder.
  6. Quote & lead: bozza preventivo, qualifica lead. Riusa client-case-quote-generator, lead-intake-qualifier.
  7. Report & pipeline: digest personale, "riassumi la giornata", report settimanale, stalli >10gg.
  8. HR & interno (bahasa): ferie, handbook, escalation a Zero come decision packet. Riusa hr-companion.
- v1 del mandato = domini 1-4 (non più solo il set F5): documenti-in-chat è la killer feature, trattala come cittadino di prima classe.

## 3. MEMORIA PER-MEMBRO — deciso da Zero (nuovo requisito)
Tre strati nello state store locale (sqlite Mini, replicato Pro — la memoria sopravvive al failover):
1. **Profilo** stabile: ruolo/RBAC, lingua preferita per membro, formato risposte, orari.
2. **Episodica**: clienti/pratiche toccati di recente, richieste recenti — i riferimenti anaforici ("e per l'altro cliente?") risolvono da qui.
3. **Pattern appresi**: abitudini ricorrenti → proattività personalizzata (es. digest del lunedì prima che lo chieda).
Meccanica: **member card** compatta (~200 token) iniettata a ogni turno (stesso pattern delle entity card CRM); scrittura memoria automatica post-turno; comando "dimentica X" onorato. La memoria NON va mai al cloud come blob — al modello arriva solo la card.

## 4. EVIDENZA (sintesi della ricerca cervello, 3 lenti su M5)
- Al nostro volume (~80M tok in/mese) le API a consumo costano $3-40/mese — meno dei flat; i 4 abbonamenti flat (agy/ChatGPT Pro/Allegro/GLM plan) sono licenze interattive: si usano per COSTRUIRE, mai come motore H24 (convergenza Kimi K3 + ricerca costi + doc OpenAI).
- Benchmark: Gemini 3.5 Flash 83,6% MCP Atlas; Kimi K2.6 96% τ²-Bench Telecom; Qwen3.7-plus = miglior Bahasa della porta TP1; failure dominante multilingue = "parameter value language mismatch" → mitigazione F8 invariata (enum ASCII, rifiuto server-side, read-before-write).
- Kimi (refuter): su TP1 pin di VERSIONE esplicita mai alias, deprecation churn trimestrale → smoke test a ogni re-pin; RPM cap bassi di default → attenzione ai burst broadcast.

Conferma ricezione con un ack e integra nel piano lane. Domande owner-relevant → decision packet, non righe di ledger.
