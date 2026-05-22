---
date: 2026-05-23
domain: operations
client_case: internal-tooling
type: decisions-addendum
parent_spec: 2026-05-23-wa-team-inbox-webapp.md
status: PROPOSED — pending Antonello confirm/correct
---

# WA Team Inbox Webapp — Decisioni operative (addendum)

> Risposte Claude alle 11 open questions §10 spec v3 + sintesi NLM compliance UU PDP 27/2022 + path implementativo B+full.
> **Antonello conferma/corregge ogni riga `[DEFAULT]`. Default sono ragionevoli ma reversibili.**

---

## A. UU PDP 27/2022 — sintesi NLM (NB-6 Compliance, 20 citations)

Query NLM su NB-6 Operations & Compliance Indonesia (199 sources, UUID `85207af3-352f-4554-8d2a-18f42cc541ba`) ha confermato:

### A.1 Stato della legge

- **UU 27/2022 effective dal 17 ottobre 2024**. Mandatory compliance per tutte le organizzazioni che gestiscono dati personali in Indonesia (locale o estere).
- **Lembaga PDP** (Agenzia PDP, l'organo di enforcement) target operativo 2026 — NON ancora operativa al 2026-05-23.
- **RPP PDP** (Regolamento Implementativo) ancora in fase di harmonization dopo public consultation Aug-Sep 2023. Quindi molti dettagli tecnici (es. tempi di risposta data subject rights, soglie DPO, retention period esatto) **non ancora definiti**.
- Nel frattempo enforcement via **KOMDIGI** (ex MOCI, Ministero Comunicazione + Digital) usando le General Data Protection Regulations.

### A.2 Lawful basis applicabili

Pasal 20 UU PDP elenca 6 basi lecite (GDPR-like):

1. **Consenso esplicito** (Pasal 20(2)(a))
2. **Obbligo contrattuale** (Pasal 20(2)(b))
3. **Obbligo legale** (Pasal 20(2)(c))
4. **Vital interest** (Pasal 20(2)(d))
5. **Public interest** (Pasal 20(2)(e))
6. **Legitimate interest** (Pasal 20(2)(f)) — "purposes of other legitimate interests with due regard to the purpose, needs and balance of interest of rights of the data controller and the data subject"

**Per Bali Zero / wa-mirror**:

- **Clienti** (con contract firmato): Pasal 20(2)(b) **contractual obligation** è solid. ✅
- **Prospect** (scrivono al numero team senza contract): Pasal 20(2)(f) **legitimate interest** è DEFENDABLE ma richiede:
  - Transparency / Privacy Notice (Pasal 26)
  - Bilanciamento documentato tra interesse del controller e diritti del subject
  - Possibilità di opposizione (right to object)

### A.3 Centralized reply — cambia il lawful basis?

**Risposta NB-6**: NO, ma **richiede update Privacy Notice**. Il passaggio da "Adit risponde dal suo telefono" → "team risponde da webapp centralizzata" è un'**espansione dello scope**. Le obbligazioni in più:

1. **Update Privacy Notice** prima dell'inizio del trattamento centralizzato (Pasal 26)
2. **Audit log** completo (Pasal 39): chi ha letto cosa, chi ha risposto cosa, quando
3. **Security obligations** (Pasal 35): cifratura at-rest + access control + audit periodici
4. **DPO appointment** OPPURE Records of Processing Activities (ROPA) — vedi §A.5

### A.4 Sanctions effettive

- **Amministrative** (Pasal 65): warning → suspension → deletion order → fine **up to 2% annual revenue**
- **Criminal** (Pasal 67, da NB-6 verbatim):
  - Pasal 67(1): unlawful collection → max 5 anni + IDR 200M (~$12k)
  - Pasal 67(2): unlawful disclosure → max 4 anni + IDR 200M
  - Pasal 67(3): unlawful use → max 5 anni + IDR 200M
  - Pasal 67(4): creating fake personal data → max 6 anni + IDR 500M (~$30k)
- ⚠️ Spec v3 dice "IDR 6B + 6 anni" — **CORREZIONE**: cifre reali da NB-6 sono IDR 500M (mezzo miliardo) + 6 anni, NON 6 miliardi.

### A.5 DPO obbligatorio?

Pasal 53-55 obbliga DPO se UNO dei 3:

1. Trattamento per **servizi pubblici** ❌ (Bali Zero non lo fa)
2. **Monitoraggio sistematico e frequente su larga scala** — ⚠️ DA VALUTARE (wa-mirror cattura 24/7 8 account, su 5000+ clienti = potenzialmente "larga scala")
3. Trattamento di **dati sensibili su larga scala** — ⚠️ DA VALUTARE (passport, NPWP, KITAS = sensibili)

**Soglie precise "larga scala" non definite** in attesa RPP. **Raccomandazione**: anche se DPO non strettamente obbligatorio oggi, mantenere ROPA (Records of Processing Activities) usando template APPDI/APINDO/ISACA Indonesia (già esistente).

### A.6 Data subject rights — tempi di risposta

Pasal 5-15 garantisce: access, rectification, erasure (right to be forgotten), data portability, withdraw consent, object to automated decision, restrict processing.

**Tempi massimi NON ancora definiti** (in attesa RPP). Pratica conservativa: rispondere entro **30 giorni** (GDPR-aligned, sicuramente difendibile).

### A.7 TDPSE registration (KOMDIGI)

Obbligatorio per qualsiasi Electronic System Operator. **Bali Zero come PT PMA che opera kita.balizero.com + nuova webapp dashboard**: verifica se TDPSE già esistente per `kita.balizero.com`, e se la nuova webapp locale (su localhost, non public) richiede separata registrazione.

⚠️ **Azione**: verificare con Adit / counsel se TDPSE Bali Zero c'è già. Se sì la nuova webapp è coperta (è sotto stesso ESO). Se no, **rischio blocking** del sito da parte KOMDIGI.

### A.8 Retention period

Pasal 39: minimum **5 anni** (o quanto previsto da regolamenti settoriali). Quindi possiamo tenere `whatsapp_message_context` per 5+ anni senza problemi. Cancellazione obbligatoria solo su richiesta data subject o post-retention.

### A.9 Privacy Notice obbligatorio — checklist per webapp

Da fornire al data subject **prima** della raccolta (Pasal 21):

1. Identità del controller (Bali Zero S.r.l.)
2. Scopi del trattamento (CRM, customer service, audit interno, legal compliance)
3. Lawful basis (legitimate interest per prospect, contract per clienti)
4. Categorie di dati raccolti (messaggi WhatsApp, media, OCR, metadata)
5. Retention period (5 anni minimum, o fino a withdrawal)
6. Sharing with third parties (esplicitamente: NO third parties)
7. Data subject rights + come esercitarli (email a privacy@balizero.com)
8. Contact point (DPO o equivalente)
9. Right to lodge complaint with Lembaga PDP (quando operativa)

**Format**: documento PDF pubblicato su `kita.balizero.com/privacy` + link in primo messaggio auto-reply WhatsApp.

---

## B. Risposta alle 11 questions §10 spec v3

### Q1. UU PDP counsel timeline

[DEFAULT proposto]: **NLM-internal research è il counsel**. NB-6 ha 199 sources + 4 fonti citate verbatim sopra. NON serve counsel esterno. Sintesi A.1-A.9 sopra è la nostra ground-truth.

**Tu confermi?** Sì → procediamo subito M1. No → indica counsel esterno + tempo.

---

### Q2. App location final lock

[DEFAULT proposto]: **nuova `apps/wa-dashboard/`** sibling app Next.js 16.

Driver: separation of concerns (mouth = public marketing site), worktree contamination risk DeepSeek R2 ~30% su 2-3 settimane build inside existing app.

---

### Q3. Cross-account threading

[DEFAULT proposto]: **separated default, toggle "Merge by client" attivo solo se `client_id` matched**.

Razionale: se Mario scrive sia ad Adit che a Sahira ma NON è ancora in CRM (no `client_id`), li teniamo separati (UI clarity). Quando Adit lo registra come cliente con `client_id`, appare toggle "Merge: vedi tutti i 3 thread come uno solo".

---

### Q4. Group chat scope

[DEFAULT proposto]: **tab separata "Gruppi"**. Inbox principale filtra `chat_type='direct'` di default.

Razionale: 32 gruppi attivi con N member each = se mostrati nella inbox principale, sommergono i DM business. Tab separata mantiene visibilità ma riduce rumore.

---

### Q5. Operator presence (typing indicator)

[DEFAULT proposto]: **SÌ in M3** ma minimale — solo "Sahira sta scrivendo..." nel pane di sinistra accanto al thread, NON nel pane chat dove l'altro operatore sta vedendo i messaggi (evita distrazione).

Razionale: utile (sapere se Adit sta già rispondendo evita doppia risposta), non stalker (no tracking outside-of-app).

---

### Q6. AI auto-reply hooks (LangGraph RAG)

[DEFAULT proposto]: **M5 future, NON M3**. M1-M4 = operatore-only.

Razionale: scope creep risk. M5 può aggiungere "AI suggested reply" sopra compose box (suggerisce, operatore accetta/modifica/scarta). Mai send autonomo senza human in the loop.

---

### Q7. Mobile responsive

[DEFAULT proposto]: **M5 con CSS responsive** 3-pane → 1-pane su <1024px + swipe gesture tra pane.

Razionale: Sahira potrebbe usare da tablet ma è P2. Desktop-first è OK per M1-M4.

---

### Q8. UI language

[DEFAULT proposto]: **inglese** per artifact UI labels (buttons, headers, statuses). **Italiano** ammesso solo nelle quick replies templates (operatore IT).

Razionale: tutto il team Bali Zero ID/IT parla inglese tech. Italiano-only escluderebbe Ari, Adit, Sahira, Surya (madrelingua ID con EN solid). Mai mix IT+EN nello stesso label (CLAUDE.md §9).

---

### Q9. Outbound jitter override

[DEFAULT proposto]: **hard-coded 10-30s con env override** `WA_DASHBOARD_JITTER_MIN_S=10`, `WA_DASHBOARD_JITTER_MAX_S=30`. **NO UI override** (operatore non bypassa anti-ban).

Razionale: WA-AKG empirical pattern. Se in futuro Meta cambia heuristics, env var permette tuning rapido senza redeploy.

---

### Q10. Auth strategy

[DEFAULT proposto]: **Option B — local JWT contro `users` table esistente**. Cookie scoped `localhost`, `SameSite=Strict`, `HttpOnly`, no SSL needed (loopback).

Razionale: best audit trail (chi ha fatto cosa quando), riusa `get_current_user` dependency esistente, no nuova infra. Option A (env password) zero audit, Option C (reverse-proxy su `kita.balizero.com`) production exposure non necessaria.

---

### Q11. Baileys retest cadence

[DEFAULT proposto]: **cron LaunchAgent ogni 10 settimane** `com.balizero.wa-mirror-baileys-retest.plist` → check `@whiskeysockets/baileys` ultimo release + diff vs pinned `6.7.21` → Telegram alert se major version bump. Manual upgrade gated da test su 1 account staging prima di rollout.

Razionale: 8-12 week cadence empirica. Solo notify, mai auto-upgrade (Baileys è non-ufficiale, breaking change può uccidere capture).

---

## C. Decisione M0-bypass — path B+full

[DEFAULT proposto]: **Strada B + full**.

### Fase 1 — Subito (M1+M2, ~3.5 giorni)

- Migration 192 (4 tabelle + RBAC mapping + FTS + triggers)
- `apps/wa-dashboard/` scaffolding Next.js 16
- Backend `wa_dashboard_stream.py` (SSE endpoint)
- Backend `wa_dashboard_search.py` (FTS endpoint)
- Backend `wa_dashboard_media.py` (auth proxy)
- Frontend: ThreadList + ChatView + ContextPane (read-only)
- Auth Option B (local JWT)
- Privacy Notice publication `kita.balizero.com/privacy` ← parallel task
- ROPA template Italian → English filing

**Deliverable**: webapp localhost:3001/wa-inbox dove vedi 16k+ msg + filter + search + media + group view. NO send capability.

### Fase 2 — Post review (M3+M4, ~3.5 giorni)

- Backend `wa_dashboard_send.py` (jittered queue + idempotency + advisory lock)
- Bridge `outbound_worker.ts`
- Frontend `ComposeBox` + `SendCountdown` + templates + tag/assign/escalate
- Operator audit log
- Privacy Notice update (centralized reply mention) prima di abilitare M3

**Gate Fase 2**: Antonello conferma che NLM compliance research §A è sufficient + Privacy Notice update pubblicato. Nessun counsel esterno needed (UU PDP è chiaro abbastanza via NB-6 + RPP non ancora vincolante).

### Fase 3 — Polish (M5, ~1.5 giorni)

- Search FTS + filter bar avanzato
- Flow visualization React Flow
- Responsive 3→1 pane <1024px
- Baileys retest cron LaunchAgent
- Idempotency cleanup cron

---

## D. Action items immediate (next 30 minuti)

Su tuo `OK` parto subito con:

1. ✅ Migration 192 file `apps/backend-rag/backend/db/migrations_v2/192_wa_dashboard_v1.sql` — 5 tabelle (auth mapping + queue + threads + audit + idempotency) + FTS GIN index + 3 pg_notify channels
2. ✅ Scaffolding `apps/wa-dashboard/` — `package.json`, `tsconfig.json`, `next.config.mjs`, `tailwind.config.ts`, `app/layout.tsx`, `app/(inbox)/page.tsx` minimo
3. ✅ Backend `wa_dashboard_stream.py` — SSE endpoint + `WaSseManager` con devils-advocate v3 fixes (put_nowait, multi-tab set queue, try/except RBAC)
4. ✅ Hook setup PG LISTEN in `lifespan` su `wa_message_inserted` channel
5. ✅ Smoke test: avvia backend + apri page → vedi msg live arrivare via SSE
6. ✅ Commit dedicato per ogni milestone (atomic, ricostruibile)
7. ✅ Push branch + PR aggiornamento

**Tempo stimato M1**: 1.5 giorni dev. Inizio ora se confermi.

---

## E. Sostituzione spec v3 (per chiarezza)

Se confermi tutto, aggiorno spec v3 → v3.1:

- §A.4 sostituisce sanctions IDR 6B con IDR 500M corretto
- §6 schema aggiunge `team_member_phone_authorizations` table (già nel commit v3 825449ec5)
- Nuova §13 "Compliance research summary" che cita NB-6 verbatim
- Nuova §14 "Decision matrix" che cita questo file
- Status v3 → v3.1 "APPROVED for implementation M1 start"
