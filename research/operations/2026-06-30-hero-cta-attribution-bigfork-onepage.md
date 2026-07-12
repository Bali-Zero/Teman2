---
date: 2026-06-30
domain: operations
client_case: none
sources:
  - apps/mouth/src/app/v2/_components/HeroCTA.tsx
  - apps/mouth/src/components/lead/WhatsAppLeadButton.tsx
  - apps/mouth/src/lib/analytics.ts
  - apps/mouth/src/lib/whatsapp-utm.ts
  - packages/core/analytics/funnel-view.ts
  - apps/mouth/src/app/(marketing)/page.tsx
  - "Subhi Monthly Work Report 28 May–29 Jun 2026 (Finding 4, Recommendation 1)"
decision_for: "Big Fork — 2 July 2026"
---

# Hero CTA — One-Page Decision (Big Fork, 2 luglio 2026)

> **TL;DR — la premessa del report va corretta.** Il report dice "hero spara zero analytics,
> bloccata dal 3 giugno, server-component vs client-wrapper". **Falso, verificato in codice
> (file:line sotto, doppia verifica: lettura diretta + audit indipendente convergenti).**
> La hero è GIÀ un client component e GIÀ traccia (triple-dispatch GA4+CRM+funnel). La
> "decisione architetturale" server-vs-client **non esiste più** — è già risolta. La decisione
> VERA è un'altra, più piccola e a basso rischio: **il click sulla hero deve diventare un lead
> attribuibile end-to-end (`lead_intent_id`), come blog e KBLI, o resta un evento-funnel senza
> riga CRM?**

---

## 1. Lo stato reale (non quello del report)

La hero homepage è montata: `app/(marketing)/page.tsx:113` → `HeroBlueprint.tsx:131` → `<HeroCTA/>`.

| Strato | Stato | Prova |
|---|---|---|
| È un client component? | ✅ Sì | `HeroCTA.tsx:1` (`"use client"`) |
| Traccia il click? | ✅ Sì, **triple-dispatch** | `HeroCTA.tsx:37` → `trackHeroCTA("hero_cta_book_call")` → `analytics.ts:609-616` (GA4 `sendGA4Event` + CRM bus `trackEvent` + funnel store `trackFunnelEvent`) |
| Evento registrato? | ✅ Sì | `packages/core/analytics/funnel-view.ts:45` (`hero_cta_book_call`) |
| **Crea una riga lead attribuibile?** | ❌ **NO** | il link è `buildWhatsAppLink("home")` = `wa.me` raw con solo UTM (`whatsapp-utm.ts:24-39`). **NON** chiama `/api/lead/capture`, **NON** genera `lead_intent_id` |

**Conclusione**: la hero NON è cieca. È **monca a metà funnel** — registra l'evento click ma non
scrive la `lead_intents` row che permette di unire la sessione GA4 al lead nel CRM.

## 2. Perché il report diceva il contrario

Stesso pattern di #1730 (registry datato): la frase "server-component vs thin-client-wrapper" e
"zero analytics" descrive lo stato di **prima** che `HeroCTA.tsx` fosse estratto a client component
(MYTHOS B2, PR #1205/#1216, cit. nel commento `HeroCTA.tsx:13-22`). Quel lavoro è **già stato fatto**.
Il report fotografa il problema vecchio, non quello residuo.

## 3. La decisione VERA per la Big Fork

> **La hero deve passare da `<a href={wa.me}>` + `trackHeroCTA` a `<WhatsAppLeadButton source="home">`
> per ottenere l'attribuzione lead end-to-end?**

Il componente che già fa la cosa giusta esiste ed è in produzione su blog/KBLI:
`WhatsAppLeadButton.tsx:51-90` → `POST /api/lead/capture` → riga `lead_intents` + `lead_intent_id`
→ `trackLeadWhatsAppCTA(source, {captured:true, lead_intent_id})` (`analytics.ts:255-276`), con
**fallback** al `wa.me` raw se la capture fallisce (utente mai bloccato, `WhatsAppLeadButton.tsx:81-87`).

### Opzione A — Wire la hero a `WhatsAppLeadButton` (RACCOMANDATA)
Sostituire l'`<a>` in `HeroCTA.tsx:27-41` con `<WhatsAppLeadButton source="home" …>`.
- **Pro**: la superficie più vista del sito diventa lead-attribuita end-to-end come tutte le altre; consistenza di pattern (oggi la hero è l'unica eccezione); join GA4↔CRM sul traffico #1.
- **Contro / rischi**: (a) serve che `"home"` sia un valore valido di `LeadSource` enum backend — **DA VERIFICARE prima**, è la stessa trappola di #1730/#1731 (`source` non-in-enum → 422 → fallback wa.me, captured:false, nessun lead_intent_id). Se manca, va aggiunto al backend **prima** del FE (regola notify-before-code, Risk 3 del report); (b) un fetch in più prima del redirect (già mitigato: 100ms beacon window, `WhatsAppLeadButton.tsx:77-79`).
- **Effort**: BASSO. ~1 file FE + eventuale 1 PR backend enum. **Non è architettura** — è uno swap di componente su un pattern già provato.
- **Reward-hacking guard**: NON cambiare wording/colore/`cta-primary` class (pinned e2e, `HeroCTA.tsx:13-17`) — solo il meccanismo di handoff.

### Opzione B — Lasciare com'è (hero = evento-funnel only)
- **Pro**: zero lavoro; il click è comunque conteggiato in GA4 e nel funnel store; nessun fetch pre-redirect.
- **Contro**: il traffico più alto del sito resta **senza riga lead nel CRM** → marketing/sales non può attribuire/seguire i lead originati dalla hero; resta l'incoerenza "tutte le CTA tranne la hero".
- **Quando ha senso**: se la priorità è la *misura aggregata* (quanti click) e non l'*attribuzione del singolo lead*.

### Opzione C — Capture leggero senza WhatsAppLeadButton
Aggiungere solo la chiamata `/api/lead/capture` dentro `trackHeroCTA` senza adottare il componente.
- **Contro**: duplica la logica già incapsulata in `WhatsAppLeadButton` (capture + fallback + `captured` flag) → debito; sconsigliata vs A che riusa il pattern. La scarto, la elenco per completezza.

## 4. Raccomandazione

**Opzione A.** Preflight **già eseguito (2026-06-30)**: l'enum `LeadSource`
(`apps/backend-rag/backend/services/lead_capture/source.py:12-24`) ha i membri
`visa_clock, visa_match, kbli_decoder, kbli_builder, tax_gap, zoning_check, article,
kbli_navigator, zantara_widget_handoff` — **`home`/`hero` NON c'è**. → il rischio 422 è
**confermato, non ipotetico**. Quindi l'Opzione A è una **sequenza a 2 PR (notify-before-code)**:

1. **PR backend PRIMA**: aggiungere `HOME = "home"` (o `HERO = "hero"`) all'enum + i **due dict**
   `human_name` e `result_url_path` (entrambi esaustivi `{...}[self]` → KeyError a runtime se manca
   un membro — stessa trappola sanata in #1731) + 1 test completeness-guard. Merge + deploy
   `nuzantara-rag`.
2. **PR FE DOPO**: swap `<a>` → `<WhatsAppLeadButton source="home">` in `HeroCTA.tsx:27-41`.
   Self-merge `sancho/*` a CI verde (perimetro Subhi).

Effort basso, rischio basso (pattern collaudato), MA **ordine non negoziabile**: FE prima del
backend = 422 silenzioso → hero "sembra wired" ma `captured:false` sempre. La "decisione
architetturale" non c'è: è una scelta di prodotto (vuoi attribuire i lead hero? sì) con
implementazione già collaudata, gated da 1 PR backend.

## 5. Cosa portare al tavolo del 2 luglio (1 frase)

> "La hero traccia già il click; quello che le manca è la riga lead nel CRM. La porto al pattern
> `WhatsAppLeadButton` già usato da blog/KBLI (effort basso), previo check che `home` sia nell'enum
> backend. Non è una scelta server-vs-client — quella è già fatta."

---

### Anchor index (per audit)
- Hero CTA raw link + tracking: `apps/mouth/src/app/v2/_components/HeroCTA.tsx:27-41,37,50`
- trackHeroCTA triple-dispatch: `apps/mouth/src/lib/analytics.ts:609-616`
- WhatsAppLeadButton capture+fallback: `apps/mouth/src/components/lead/WhatsAppLeadButton.tsx:51-90,56,72-76,81-87`
- trackLeadWhatsAppCTA: `apps/mouth/src/lib/analytics.ts:255-276`
- buildWhatsAppLink (UTM only, no capture): `apps/mouth/src/lib/whatsapp-utm.ts:24-39`
- Event registry: `packages/core/analytics/funnel-view.ts:9,12,45`
- Hero mount chain: `app/(marketing)/page.tsx:113` → `HeroBlueprint.tsx:131` → `HeroCTA`
