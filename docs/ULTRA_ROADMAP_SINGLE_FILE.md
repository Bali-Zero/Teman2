# Roadmap Ultra (spiegazione semplice + piano esecutivo)

Questo file mette tutto in un unico posto:
1) cosa serve ogni punto (in modo molto semplice)  
2) ordine consigliato  
3) piano 2 settimane / 1 mese / 1 quarter con KPI

---

## 0) Idea chiave (in una frase)

Non vinci “solo col modello”: vinci con **retrieval giusto + ragionamento giusto quando serve + UX affidabile + misure di qualità**.

---

## 1) Top 10 “Ultra” — a cosa serve (semplice)

### 1) Quality routing (Fast/Pro/DeepThink)
**A cosa serve:** a usare il modello “forte” solo quando serve davvero.  
**Perché conta:** qualità percepita alta nei casi difficili, senza costi/latency sempre alti.

### 2) 2-pass “Draft → Verify”
**A cosa serve:** a controllare che la risposta sia coerente e basata su fonti, prima di mostrarla.  
**Perché conta:** riduce errori e “hallucination”, aumenta fiducia.

### 3) Retrieval Ultra (hybrid + rerank “solo quando serve”)
**A cosa serve:** a prendere i pezzi giusti della knowledge base quando la domanda è difficile o ambigua.  
**Perché conta:** se il contesto è sbagliato o incompleto, anche il miglior modello sbaglia.

### 4) Eval continua (dataset + regressioni)
**A cosa serve:** a misurare oggettivamente se oggi rispondi meglio o peggio di ieri.  
**Perché conta:** senza misure, non sai se stai migliorando o peggiorando.

### 5) Evidence pack standard (fonti sempre chiare)
**A cosa serve:** a mostrare chiaramente “da dove arriva la risposta”.  
**Perché conta:** trasforma “chat” in “assistente professionale” e riduce discussioni.

### 6) Proactive compliance come prodotto
**A cosa serve:** a ricordare scadenze e rischi prima che diventino problemi.  
**Perché conta:** aumenta retention, upsell, e valore reale per il cliente.

### 7) CRM intelligence (next actions + handoff umano)
**A cosa serve:** a trasformare conversazioni in lavoro operativo: task, follow-up, priorità, assegnazioni.  
**Perché conta:** porta direttamente fatturato (close rate e velocità).

### 8) Privacy-by-design (log redaction + retention + consenso)
**A cosa serve:** a minimizzare il rischio di incidenti su dati sensibili.  
**Perché conta:** un incidente privacy può costare più di qualsiasi miglioramento di modello.

### 9) SLO/observability “business”
**A cosa serve:** a controllare affidabilità e qualità in produzione (p95, error budget, quota, qualità retrieval).  
**Perché conta:** se l’app “non regge”, l’utente percepisce tutto peggio (anche risposte buone).

### 10) Unificazione canali (web/WhatsApp/IG)
**A cosa serve:** a far funzionare le stesse regole e la stessa qualità ovunque (storia, consenso, templates, escalation).  
**Perché conta:** scala operativa, meno bug, esperienza coerente.

---

## 2) Ordine consigliato (per ROI e dipendenze)

1) (1) Routing modelli  
2) (2) Draft→Verify  
3) (3) Retrieval Ultra  
4) (5) Evidence pack  
5) (4) Eval continua  
6) (8) Privacy-by-design  
7) (9) SLO/observability business  
8) (6) Proactive compliance  
9) (7) CRM intelligence  
10) (10) Unificazione canali

Motivo: i punti 1–5 alzano subito qualità percepita e riducono errori; 8–9 riducono rischio e stabilizzano; 6–7 monetizzano; 10 scala.

---

## 3) Piano operativo: 2 settimane / 1 mese / 1 quarter

### Fase A — 2 settimane (impatto immediato)
**Deliverable**
- Definire i 3 tier (Fast/Pro/DeepThink) e regole chiare “quando escalation”.
- Aggiungere il concetto di “verify pass” (anche minimale) e lista controlli: citazioni presenti, numeri coerenti, no contraddizioni.
- Standard di output per 2 domini principali (es. Visa + Tax): formato fisso e leggibile.
- Evidence pack “minimo”: top fonti sempre visibili.

**KPI**
- Riduzione errori “evidenti” (manual review) su un set di domande hard.
- Aumento tasso “utente soddisfatto al primo colpo” (proxy: meno retry / meno follow-up confusi).
- Tempo medio risposta p95 non peggiora oltre un limite definito.

### Fase B — 1 mese (qualità stabile e misurabile)
**Deliverable**
- Retrieval Ultra solo per hard-case: hybrid (o fallback lexical) + rerank selettivo.
- Eval continua: dataset interno (50–200 domande) + report automatico (giornaliero o CI).
- Dashboard base: cache hit rate, escalation rate, citation coverage, error rate.
- Privacy-by-design base: redaction log + retention policy definita.

**KPI**
- Faithfulness / answer relevancy migliorano (anche solo +0.05 è tanto se consistente).
- Citation coverage: percentuale risposte con fonti utili sale e resta stabile.
- Escalation rate sotto controllo (non “tutto deep think”).

### Fase C — 1 quarter (Ultra a livello prodotto)
**Deliverable**
- Proactive compliance completa: scadenze, alert, template messaggi, audit trail.
- CRM intelligence: next best actions, handoff umano, SLA, assegnazioni.
- Unificazione canali: stessa pipeline (session, consent, rate limit, templates, escalation).
- SLO/observability completa: p95/p99, error budget, quota monitor, incident playbook.

**KPI**
- Retention ↑ (clienti che restano) e upsell ↑ (più servizi per cliente).
- Riduzione tempo umano per caso (operazioni più rapide).
- Incidenti privacy/security: 0; MTTR basso; affidabilità p95 stabile.

---

## 4) Regola pratica per competere con “Deep Think”

Se una risposta è “high-stakes” o retrieval è incerto:
1) retrieval Ultra  
2) modello migliore (DeepThink)  
3) verify pass  
4) evidence pack ben visibile  

Altrimenti: Fast/Pro e UX super fluida.

