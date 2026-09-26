---
date: 2026-06-14
domain: compliance
client_case: none
sources:
  - scripts/openclaw_whatsapp_bridge.py (origin/main 3d5dd1da3, md5 3a881af2 == LIVE Pro HOME)
  - apps/backend-rag/backend/tests/unit/scripts/test_openclaw_whatsapp_bridge_script.py
  - cicatrici W68/W72/W73/W77 (.claude/rules/cicatrix-scars.md)
  - NB-3 Company Setup 933509f9 (KBLI 2025 ambiguity, 15 cited sources)
  - Gemini 3.5 Flash High (second-order synth) + Gemini (surrogate refuter) + nuzantara-mcp inspect_kbli 46324
machine: M5 (balizero@Air-M5); LIVE bridge runs on Pro
---

# MYTHOS M2 — Il cervello WhatsApp di Zantara: la famiglia `_guard_*` e l'harness che la dovrebbe gatare

## §0 Executive

Mandato: cacciare la classe `_guard_*` over-match che recidiva a ogni audit (W68→W72→W73)
perché manca un **meccanismo strutturale** che la impedisca. Il LEAD del prompt diceva: harness
test-matrix "not yet shipped" (W73 meta-recommendation) + guard da fixare.

**Il LEAD era datato.** Sotto verifica su disco (gate-0):

1. **L'harness È GIÀ SHIPPATO** — commit `84ee0e69c` PR #1387 (**W77**, "language-gap sweep + trilingual
   GUARD_MATRIX + Zantara Golden Corpus"), in `origin/main`. Ha shippato esattamente il candidato-cura #1
   del mandato: `GUARD_MATRIX` + 3 meta-test a discovery dinamica + `_REPLY_GUARD_CHAIN`/`_apply_reply_guards`
   single-source-of-truth + 11 fix lang-gap. 160 test verdi.
2. **Nessun drift HOME-fork in produzione.** Il bridge LIVE gira sul **Pro** (`com.nuzantara.openclaw-whatsapp-bridge`
   PID 1019, uvicorn :8789, `~/.openclaw/bin/`). La copia HOME-Pro è **byte-identica a `origin/main`**
   (md5 `3a881af2`, diff 0 righe). Il "drift 206 righe" iniziale era solo il mio checkout M5 **20 commit stale**.
   La trappola W50/W51/W52 oggi NON è attiva.
3. **Il difetto di primo ordine (kbli_label over-match) si è DISSOLTO sotto gate-2.** Vedi §Meta-pattern.

**Finding reale = secondo ordine:** l'harness W77 valida la **logica di escape lessicale** dei guard,
non il loro **comportamento inteso**. **Terapia shippata (W81, PR sotto):** clobber-assertion stretta
`out == proprio_canonical` per gli 8 substitution-guard + meta-gate anti-drift. Test-only, zero rischio
produzione. 161 verdi. Fire-tested.

## §1 La guard-family (anatomia)

10 `_guard_*` post-LLM, tutti in `_REPLY_GUARD_CHAIN` (W77 SSOT). 8 **substitution** (sostituiscono col
canonical), 2 **append/prepend**:

| Guard | Tipo | Canonical |
|---|---|---|
| document_status, legacy_b211, hak_milik, lkpm, property_zoning, villa_kbli, cafe_pma, nominee | SUBSTITUTION | il proprio `_canonical_*_answer` |
| tax_compliance | APPEND (verify-suffix) | — |
| kbli_label | PREPEND ("KBLI direction to check:") | — |

Gate-1 (ri-verifica scettica): il guard-hunter ha segnalato 5 bare-substring CRITICAL/HIGH.
**Riprodotti uno per uno contro il modulo reale (M5-worktree) E il bridge LIVE (Pro):**

| Lead | severity dichiarata | riproduzione reale | verdetto |
|---|---|---|---|
| kbli_label su risposta code-bearing senza la parola "kbli" | (live) | CLOBBER su worktree **E** LIVE | VERO (ma vedi §Meta) |
| "by the" / LKPM | CRITICAL | **UNCHANGED** | FALSO |
| "status" / document | CRITICAL | **UNCHANGED** | FALSO |
| "cafe" in PT PMA def | MEDIUM-HIGH | **UNCHANGED** | FALSO |
| "wife" in "midwife" | MEDIUM | **UNCHANGED** | FALSO |

~70% di falsi-malati (Fable ne falsifica ~40%; il guard-hunter era over-eager su CRITICAL). **Nessun
fix di guard giustificato.**

## §2 Persona / over-caution

W72 aveva già splittato defer-vs-state-directly (prompt `reply_rules` + guard load-bearing). I probe live
(B/C/D/E/F) mostrano la persona **NON** più over-cautious sui fatti stabili: definizioni KITAS-status,
PT PMA vs lokal, nominee-illegality passano intatte. Nessun cambio persona richiesto (e sarebbe stato
confine-operatore: §Solo-operatore).

## §3 L'harness W77 (cosa c'era, cosa mancava)

C'era (forte): `test_guard_matrix_polarity` (pass/clobber/no_trigger), `..._covers_every_guard_both_polarities`
(discovery dinamica → ogni guard DEVE avere pass+clobber), `..._covers_languages_and_no_trigger` (en/id/it +
no_trigger), `test_chain_endpoint_and_tests_share_the_same_chain` (chain == modulo), 1 full-chain ordering test.

Mancava (i 2 buchi, verificati su disco):
- **Hole A — polarity collassata su uno stratagemma lessicale.** Per kbli_label, TUTTI i "pass" case
  contengono letteralmente "KBLI"/"Kode KBLI"/"direzione KBLI" → passano per l'escape `if "kbli" in reply`,
  **non** perché il guard si comporta bene. Distinzione pass/clobber = "il reply contiene la stringa magica",
  non "il reply è corretto". → l'harness è **cieco** alla zona "risposta corretta code-bearing senza la
  parola kbli".
- **Hole B — clobber debole.** Per gli 8 substitution-guard il clobber asseriva solo `out != reply`. Un guard
  che clobbera col canonical SBAGLIATO (cross-contamination, W73 #1 villa-eats-food-import) **passava**.

## §Meta-pattern — la malattia-delle-malattie (il vero topic)

> **Confondere "presenza di una substring lessicale" con "correttezza semantica".**

È la stessa convinzione difettosa a due livelli, e genera DUE famiglie:

1. **Nei guard (W68→W72→W73):** trigger/escape sono *stringhe* anziché *significati* → bare-substring
   ("lease"⊂"leasehold", "ota"⊂"quota") + positive-gating-escape irraggiungibile ("1 to 15 april").
2. **Nell'harness (W77, scoperto oggi):** i pass-case passano perché contengono la magic-word dell'escape,
   non perché il comportamento è giusto → **l'antibody costruito per fermare la classe RIPRODUCE la classe**.
   Il test convalida la logica difettosa invece del comportamento inteso.

Evidenze trasversali (Gemini 3.5 Flash High, indipendente, ha ri-scoperto la stessa tesi):
- **W68:** escape `oss+bkpm AND ≤125 words` — autorizza una risposta corretta solo per token esatti → la clobbera sempre.
- **W73:** lo stesso meccanismo positive-gating copiato su 5 guard ("1 to 15 april" letterale).
- **Oggi:** i pass-case di kbli_label includono "KBLI" — il test echeggia la logica lessicale difettosa,
  mascherando che una risposta semanticamente corretta che omette la magic-word verrebbe trattata diversamente.

### Il twist del gate-2 (perché il difetto di primo ordine NON era un difetto)

Il LEAD "kbli_label over-match, da rimuovere" è stato **FALSIFICATO** dal gate-2 (Mythos: anche le mie
ipotesi sono lead). Refuter (Gemini surrogato — DeepSeek morto, HTTP 402 Insufficient Balance) + **NB-3
ground-truth (15 fonti regolatorie)**:

- 46324 = "Perdagangan Besar **Hasil Perikanan**" (prodotti ittici), **non** "frozen food" generico
  (la risposta-esempio del probe era imprecisa; potrebbe triggerare anche 52102 cold storage).
- Villa: 55193 (KBLI 2020) → **recoded 55203** (KBLI 2025) — "confusione altamente documentata".
- Verbatim NB-3: *"asserting a KBLI code as definitively final based solely on a high-level client
  description is extremely risky... any KBLI mapping should always be framed as preliminary and 'subject
  to technical verification by the compliance team'."*

→ Il prepend "KBLI direction to check:" su una risposta bare-code è **l'hedge che il regolatore PRESCRIVE**,
non un over-match. Rimuoverlo = wrong-answer-exposure (refuter R1/R2 confermati). **Il guard è corretto.**

Correzione al refuter (W65 — anche il refuter mente): il suo R3 ("la contromisura harness è impossibile")
era un uomo di paglia. La contromisura corretta non è "scrivi un pass-case code-bearing senza la magic-word"
(impossibile per definizione del guard) — è **rendere ESPLICITO cosa il guard fa** via clobber-assertion
stretta, così la prossima sessione non scambia l'hedge per over-match (come ho quasi fatto io).

## §Terapia eseguita (W81 — cura-mentre-diagnostichi)

Branch `agent/air-m5/backend-rag/mythos-m2-wa-brain`, commit `7ad3bfb8d`, PR aperta (auto-merge).
**Solo test, zero comportamento di produzione** → nessuna patch HOME, nessun restart bridge (è la cosa
giusta: non c'è difetto di produzione, e patchare il bridge avrebbe regredito l'hedge KBLI).

1. `_SUBSTITUTION_CANONICAL` (guard → builder, SSOT) — chiude **Hole B**.
2. `test_guard_matrix_polarity`: per un clobber di substitution-guard, assert `out == builder(lang)`.
   Fire-tested: iniettare nominee→villa-canonical ora FALLISCE; il vecchio `!= reply` lo passava.
3. `test_substitution_canonical_map_does_not_drift_from_module`: meta-gate dinamico — ogni guard il cui
   corpo `return _canonical_*_answer(...)` DEVE essere mappato (no stale/wrong). Stessa logica di
   `_discover_guards()`. (Questo meta-test ha trovato una mia svista: regex `[a-z_]+` mancava le cifre di
   "b211" → corretto a `[a-z0-9_]+`.)

Verifica: **161 passed** (era 160) sul worktree byte-identico alla produzione (md5 `3a881af2`).

**Hole A (pass-case tautologici)** NON è stato chiuso con un assert meccanico: il refuter ha mostrato che
imporre "pass-case senza magic-word" è impossibile per i keyword-escape guard. La chiusura corretta di Hole A
è la clobber-assertion stretta (rende esplicito il comportamento) + la disciplina di scrivere pass-case
semanticamente corretti — non un vincolo lessicale. Lasciato come raccomandazione, non come gate meccanico
(vedi §Solo-operatore).

## §Solo-operatore (confine)

- **Hole A (pass-case che passano per il motivo sbagliato)** — non c'è un assert meccanico sano che lo chiuda
  per i keyword-escape guard (refuter R3). Richiede disciplina di review umana sui pass-case futuri, o una
  decisione di design (es. un campo `pass_reason` nel matrix). **Decisione di Antonello**, non auto-fixabile.
- **Cambi alla persona verso i clienti** — nessuno necessario, ma qualunque ritocco al tono è confine-operatore.
- **DeepSeek refuter morto (HTTP 402 Insufficient Balance)** — il Tier-1 refuter del panel asimmetrico è
  disarmato. Surrogato con Gemini per questa sessione. **Ricarica saldo DeepSeek** è azione operatore.
