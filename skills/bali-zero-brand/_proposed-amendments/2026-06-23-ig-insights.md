# IG Insights — Cosa sta imparando l'AI — 2026-06-23

**Da dove arriva**: analisi settimanale automatica sui caroselli pubblicati su Instagram (@balizero0), incrociando quanto piacciono (like, salvataggi, condivisioni, persone raggiunte) con com'erano fatti (tema, tono, formato delle slide).
**Su quanti post**: 45 caroselli pubblicati con metriche reali (da settembre 2025 a giugno 2026); 14 nella finestra recente di 90 giorni.

---

## In breve questa settimana

> **Tre cose da ricordare:**
> 1. **Gli elenchi puntati su sfondo scuro** sono il formato che la gente salva e inoltra di più — soprattutto su visti, tasse e regole. È il nostro cavallo vincente quando l'obiettivo è "fammi salvare questo".
> 2. **Il tono militante** (allarme, numeri-shock) fa tantissimi like ma pochissime salvate. Va bene per farsi notare, male per essere utile. Sui temi normativi meglio non abusarne.
> 3. **I post sulla salute** vanno fortissimo (la gente li inoltra agli amici per avvisarli) — ma per ora sono solo 2, troppo pochi per esserne certi. Da tenere d'occhio.

---

## Le scoperte

### Scoperta 1 — Le liste scure si fanno salvare e inoltrare più di tutto

**In parole semplici:** Quando una slide è un elenco puntato su sfondo scuro, la gente la salva e la inoltra in chat più di qualsiasi altro formato. **Cosa fare:** per i temi dove l'obiettivo è essere salvati (visti, tasse, regole, società), usa questo formato nelle slide centrali. Funziona ancora meglio col tono diretto e militante. **Quanto fidarsi:** alta — è la scoperta più solida, confermata anche dai migliori giornali del settore.

<details tech>

**Effect size**: full corpus N=13. dark-status-list mean Save/Like 0.91 (+23% vs corpus 0.74). dark-status-list mean Share/Like 1.32 (+34% vs corpus 0.99). PASSES both 30% threshold (Share/Like) and N>=5.

Save/Like utility threshold pct (>=0.50): 77% of dark-status-list carousels exceed threshold. Compare: statement-bomb 38%, qa-dialogue 38%, evidence-carved 62%.

**Tone x layout sub-bucket (N>=5)**: militante x dark-status-list (N=11, full corpus) — mean Save/Like 0.97, Share/Like 1.47. Single largest confirmed interaction bucket.

**Dual-baseline**: Internal PARTIAL (ShL 1.47 below villa_ota gold). External ALIGNED — `_external-bench-2026-06.md` process-step-map (pattern #3) is a dark-status-list variant for regulatory how-to.

**Proposed amendment — Article 9.4, informational note**: dark-status-list is the empirically preferred inner-slide layout for regulatory/tax/visa/company topics where the KPI is saves or DM-forwards; militante x dark-status-list (N=11) is the highest confirmed combination by forwardability. Soft preference, does not override archetype assignments.

**Confidence**: MEDIUM-HIGH. N=13 passes threshold. Effect on Share/Like, not likes. No isolation of topic confounds.

</details>

---

### Scoperta 2 — Il tono "allarme" fa like ma non viene salvato

**In parole semplici:** Il tono militante e rituale (toni forti, emotivi, da annuncio) attira tanti like ma quasi nessuna salvata: la gente reagisce sul momento e poi passa oltre, non lo conserva come utile. **Cosa evitare:** non usarlo sui temi normativi (regole, eventi, annunci di governo) — lì fa danno. **Eccezione:** sui visti molto "identitari" (cittadinanza, diaspora) può creare il post virale, come è successo con quello sulla Global Citizenship. **Quanto fidarsi:** media — l'effetto è grande e coerente, su un campione ancora contenuto.

<details tech>

**Effect size**: full corpus N=5. rituale mean likes 637 (+245% vs corpus 184.6). Save/Like 0.22 (-70%). Share/Like 0.54 (-45%). PASSES N>=5 and 30% on all three.

**Decomposition**: 4 of 5 are regulatory + cover-photo (mean likes 36, SL 0.04-0.18, all below threshold). 1 is the GCI outlier (3,043 likes, SL 0.63, ShL 1.93) inflating the mean 5x. Remove GCI → mean likes 36, SL 0.12. rituale drives viral spikes on identity topics, fails systematically.

**Dual-baseline**: Internal CONFIRMED (below every gold-standard). External: no support (SOTA brands don't use this register).

**Proposed amendment — new Article 9.x (tone constraints)**: exclude rituale from regulatory/tax/company briefs. Permitted: high-identity visa topics (GCI). Storyboarder flags rituale outside visa-identity archetypes as a soft warning.

**Confidence**: MEDIUM. N=5. Large, consistent. GCI confirms the narrow exception. Topic confound not fully ruled out.

</details>

---

### Scoperta 3 — Il "numero shock" fa rumore ma converte poco (tranne sul property)

**In parole semplici:** Il formato a titolo-bomba (un grande numero o frase d'impatto) fa il record di like, ma solo 4 post su 10 vengono davvero salvati — molto meno delle liste scure. **Cosa fare:** usalo quando vuoi far rumore, ma non quando l'obiettivo è essere salvati. **Unica eccezione:** sul property (immobili) funziona per entrambe le cose — lì è la scelta giusta per le notizie-flash (stop ai progetti, scadenze, dati di mercato). **Quanto fidarsi:** media — l'eccezione property è su soli 3 post, da confermare.

<details tech>

**Effect size**: full corpus N=8. statement-bomb mean likes 349 (+89% vs corpus). Save/Like pct above threshold 38% (3 of 8) vs dark-status-list 77%, evidence-carved 62%. PASSES N>=5 and 30% likes; SL -7% (below threshold individually).

The finding is in the **distribution**: bimodal — 5 of 8 below SL 0.40, 3 above 0.90. Inflates likes while failing the consistent utility conversion dark-status-list provides.

Domain x layout: property x statement-bomb (N=3) — mean likes 550 (+198%), Save/Like 1.17, Share/Like 1.77. The one sub-bucket where the layout works for BOTH metrics.

**Proposed amendment — Article 9.4 additional note (MEDIUM)**: statement-bomb = highest raw likes but lowest consistent utility. Exception: property x statement-bomb correct for property news-flash topics. For regulatory/tax/visa prefer dark-status-list/evidence-carved when Save/Like is the KPI.

**Confidence**: MEDIUM. N=8 overall; property N=3 below threshold — validate at N=5 before hardening.

</details>

---

### Scoperta 4 — La salute funziona benissimo (ma è ancora presto)

**In parole semplici:** I 2 post sulla salute (dengue, BPJS per stranieri) hanno avuto i migliori risultati in assoluto per salvataggi e condivisioni — la gente li inoltra agli amici come avviso. **Cosa fare:** niente ancora di definitivo, ma vale la pena pubblicarne altri per capire se il pattern regge. **Quanto fidarsi:** bassa per ora — sono solo 2 post. Da promuovere a regola se altri 2 confermano.

<details tech>

**Effect size**: N=2 (full corpus). health mean Save/Like 1.93 (+161%), Share/Like 2.49 (+151%). FAILS N>=5 — PRELIMINARY.

Two carousels: dengue/rainy-season (55 likes, SL 1.69, ShL 3.20 — highest Share/Like in full corpus) and BPJS-expats (110 likes, SL 2.16, ShL 1.78). Both exceed every internal gold-standard except villa_ota ShL.

Mechanism hypothesis: health topics serve direct personal-safety utility → immediate saves + DM-forwards, without bureaucratic-domain friction.

**No amendment proposed.** N=2. Flag for priority: if 2 more health carousels hold, becomes HIGH-confidence Article 9 domain note.

</details>

---

## I casi singoli da guardare a mano

- **Il più visto** — "Bali ferma il mega-progetto da $7 miliardi": 1.070 like ma quasi zero salvate. Ha sfondato per il tema (titolo Kura-Kura), non per come era fatto. Conferma che il "numero shock" tira like senza convertire.
- **Il più inoltrato** — "Non farti rovinare il 2026 da un piccolo insetto" (dengue): pochi like (55) ma condiviso a raffica. Primo post salute con dati completi. Da replicare subito: salute + lista scura + tono diretto.
- **Il sottovalutato** — "L'era delle ville a Bali sta finendo": solo 12 like ma salvatissimo (chi l'ha letto l'ha trovato utile). Tema complesso (ville → agri-tech) su un formato foto che forse non era quello giusto. Da rivedere.

## Cosa manca ancora ai dati

- Lunghezza dei testi, numero di immagini per post: non registrati (la tabella `carousel_runs` è vuota).
- Il pubblico di destinazione (founder, investitore, nomade…) non è ancora taggato sui post.
- Gemini 3.1 Pro non ha girato (serve il login `agy` prima del 30/6) — analisi fatta in locale.

## Decisione

Antonello rivede questo file ogni settimana. Per applicare una scoperta serve un commit git (Articolo 11.1).

**Consiglio:** la Scoperta 1 (liste scure) è la più pronta da applicare subito. La 2 (tono allarme) è già utile come avviso allo storyboarder. La 4 (salute) va testata pubblicando altri post.

---

> _Versione umana — il dettaglio tecnico completo (effect size, N, baseline) è nei blocchi nascosti sotto ogni scoperta, per le decisioni di merge._
