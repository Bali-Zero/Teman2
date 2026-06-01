**Analisi economics agentica per Nuzantara (11.699 clienti, ~241 entità, Fase 1)**  
*Ipotesi di base: 30.000 task/anno (2,5 transazioni/cliente), ARPU $800, margine operativo 30%, costo token 2026 $0,5/1M token blend. Sviluppatore/ML‑Ops in Indonesia ≈ $50k/anno fully loaded.*

---

## 1. Costo multi‑agente (finding “15x chat”) – quando conviene e quando no

| Scenario                    | Token single‑agent | Token multi‑agent | Extra costo/task ($) | Extra costo annuo (30k task) |
|-----------------------------|-------------------|-------------------|----------------------|------------------------------|
| Task semplice (FAQ, lookup) | 1.000             | 15.000            | 0,007               | $210                         |
| Task medio (visa check)     | 3.000             | 45.000            | 0,021               | $630                         |
| Task complesso (risk, frode)| 10.000            | 150.000           | 0,07                | $2.100                       |

**Conviene il multi‑agente se** il valore generato dall’aumento di accuratezza **supera il delta di costo**.  
- Costo errore: respingimento visto → rilavorazione + cliente perso = **$200–$500**.  
- Break‑even per task medio: **0,4% di riduzione errori** (0,004 × $350 = $1,4 > $0,021).  
- Con 30.000 task, bastano 120 errori evitati/anno per coprire il costo extra del multi‑agente.  

**Si giustifica quando**:
- I task hanno rischio elevato (immigrazione, proprietà, compliance fiscale).
- Gli agenti sono **specializzati per dominio**, producono output migliori di un singolo prompt generico.
- L’architettura è stabile e il guadagno di qualità è misurato.

**NON conviene** per:
- FAQ, informazioni statiche (bastano RAG + agente singolo).
- Task a basso valore aggiunto dove l’errore non ha conseguenze economiche.
- Sistemi non manutenuti dove la latenza e la duplicazione logica (5 agenti duplicati trovati) annullano ogni beneficio.

*Intervallo confidenza delta costo: ±30% (dipende da modello e prezzo input/output). Break‑even rimane comunque favorevole per il core business.*

---

## 2. ROI riparazione self‑improvement loop vs costo

**Costo riparazione (one‑off)**  
- Analisi e fix del loop Voyager: **400‑600 ore** (@$80‑130/h) = **$40k‑$80k** (stima centrale $60k).  

**Benefici annuali** (post riparazione, loop funzionante):

| Voce                                      | Stima annuale                        | Note |
|-------------------------------------------|--------------------------------------|------|
| Eliminazione eventi inutili (92k/mese)   | $3k‑$8k                              | 92k eventi/mese a 3‑7k token l’uno |
| Ottimizzazione prompt (riduzione token)   | $0,3k‑$1k                            | Calo 1‑2% su 30.000 task |
| Riduzione errori (‑0,5% task falliti)    | **$30k‑$90k**                         | 150 task evitati × $200‑$600 di costo errore |
| Time‑to‑value migliorato (minori attese)  | $10k‑$20k (NPS → +0,2% retention)    | Valore vita cliente $2.400 |

**Beneficio tot. annuo range:** $43k‑$119k, **centrale $70k/anno**.

**ROI a 3 anni:**  
- Costo riparazione: $60k una tantum.  
- Beneficio cumulativo: $210k.  
- Payback: **<12 mesi** (con beneficio centrale).  
- **ROI ⇒ 250%** (anche con ipotesi conservative 150%).  

*Intervalle di confidenza: ±35% sui benefici, ipotesi principale legata alla sensibilità del tasso di errore. Il break‑even si raggiunge già con solo 0,25% di riduzione errori.*

---

## 3. ROI dei game‑changer candidati (impatto su 11.699 clienti)

| Iniziativa             | Investimento (k$) | Meccanismo di ricavo/risparmio                                                                          | Δ fatt./profitto annuo (k$)      | ROI a 3 anni |
|------------------------|-------------------|---------------------------------------------------------------------------------------------------------|----------------------------------|--------------|
| **Portale‑copilot cliente** | 120‑200          | - Churn ‑3% → 351 clienti risparmiati × LTV $2.400 = $842k in 3 anni<br>- Cross‑sell +10% × 1.170 clienti × $500 serv. extra (margine 50%) = $292k/anno | Fatt. extra $800k, prof. +$350k   | **3‑5x**     |
| **Lead‑qualifier AI**      | 30‑60            | - Conver. lead +3% (2.000 lead/anno → +60 clienti), ricavo medio 1° anno $800, margine 50% = $24k/anno | Prof. +$24k                      | **1,5‑2x**   |
| **Document‑AI (akta)**     | 70‑100           | - Rilavorazione documenti catastali: 1.500 pratiche × 4h risparmiate @$30/h = $180k/anno<br>- Aumento capacità senza nuovo personale (gestione +10% pratiche) | Risparmio + prof. $200k/anno     | **4‑6x**     |
| **Predictive churn/upsell**| 50‑80            | - Churn ‑2% (234 clienti) → $560k LTV in 3 anni (valore attualizzato $420k)<br>- Upsell mirato +5% (585 clienti) × $300 prof. extra = $175k/anno | Prof. +$250k/anno               | **5‑7x**     |

**Priorità d’investimento:**  
1. Document‑AI (risparmi certi, dipendenza minima da comportamento cliente).  
2. Predictive churn/upsell (effetto diretto su ritenzione e margine).  
3. Portale‑copilot (forte impatto ma richiede change management).  
4. Lead‑qualifier (ROI modesto da solo, meglio integrato in funnel marketing).  

*Intervalli confidenza: ±40% su stime fatturato (dipende da penetration rate e adoption); i costi sono concreti (±20%).*

---

## 4. Costo mantenimento 241 entità agentiche vs consolidamento a macro‑agenti

**Situazione attuale (241 agenti mappati)**  
- Manutenzione prompt, versioning, monitor: **2 FTE** (1 senior, 1 junior) → **$100k‑$140k/anno**.  
- Overlap e duplicazione: 5 agenti ridondanti trovati, probabile ≥5% di token sprecati in orchestrazione ridondante → ~$2k‑$5k/anno extra.  
- Rischio operativo: KG morto e loop rotto amplificano errori, costo hard‑to‑quantify.  

**Scenario consolidato (15‑20 macro‑agenti)**  
- Manutenzione: **0,5 FTE** (fino a 1 FTE se integrazione continua) → **$30k‑$50k/anno**.  
- Rafforzamento intelligibile: ogni macro‑agente copre un dominio (Visa, Tax, Property, Onboarding,…), ruoli chiari.  
- Risparmio token stimato: riduzione media token/task del 5‑10% (da 15.000 token a 13.500) → $150‑400/anno, trascurabile ma si somma.  
- Risparmio totale **su manodopera**: **$50k‑$90k/anno** (centrale $70k).  

**Payback della migrazione**  
- Costo redesign e re‑orchestrazione: **$60k‑$100k** (3‑5 mesi uomo).  
- Risparmio annuo $70k → recupero in **12‑18 mesi**.  
- Dopo 3 anni, risparmio netto cumulato $110k‑$170k.

---

**Conclusioni executive (numeri cardinali)**  
- La **multi‑agente architecture è sostenibile** economicamente perché il costo token extra è irrisorio rispetto al valore di un errore evitato.  
- **Riparare il loop di auto‑miglioramento** è un investimento a elevata leva: con $60k si sbloccano $70k/anno di benefici.  
- **Document‑AI e predictive churn/upsell** generano il massimo ritorno finanziario immediato, trainando la crescita senza aumentare il personale.  
- **Consolidare a macro‑agenti** libera $70k/anno riducendo complessità e duplicati, allineandosi alla riorganizzazione post‑Fase 1.  

*Tutti i valori sono espressi in USD, con range che includono variabilità del contesto operativo indonesiano. Gli ordini di grandezza rimangono robusti anche con oscillazioni del 30‑40%.*