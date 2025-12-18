# Strategia Modelli AI (per non perdere vs “Deep Think”)

Obiettivo: mantenere **costi/latency sostenibili** senza sacrificare la qualità percepita quando l’utente confronta con modelli “deep think” (es. Gemini Pro / ChatGPT top).

## 1) Ha senso mettere un “Super model” nella webapp?

**Sì, ma come modalità/route, non come default.**

Motivo tecnico: la qualità finale è una funzione di:
1) retrieval (contesto giusto), 2) ragionamento (modello), 3) UX (streaming/affidabilità).

Se il retrieval è incompleto o la UI perde token, un “super model” non vi salva.  
Se invece retrieval+UX sono solidi, il “super model” diventa un **turbo** per i casi hard.

## 2) Approccio world-class: Model Router + Quality Gates

### A) Router per difficoltà (runtime)
Route a “Super” quando:
- query è **multi‑step** (procedura lunga, tax planning, corporate structure),
- confidenza retrieval bassa (pochi chunk buoni / score basso / molte contraddizioni),
- richiesta “high‑stakes” (compliance, scadenze, importi, rischi legali),
- utente seleziona “Precision Mode / Deep Think”.

Default (economico) quando:
- FAQ, definizioni, risposte brevi,
- follow-up locali su contesto già recuperato,
- task operativi ripetitivi (template, email draft, checklist standard).

### B) 2‑pass: Draft → Verify (Ultra senza raddoppiare costi)
Pattern:
1) modello veloce genera answer con citazioni,
2) un verifier (anche più economico) controlla:
   - “hai citazioni?”, “hai numeri coerenti?”, “hai contraddizioni?”,
   - “manca un documento primario?” → trigger re‑retrieve,
   - output finale “clean”.

### C) Escalation controllata
Limiti:
- max N escalation per conversazione,
- budget token per utente/ruolo,
- fallback automatico (flash → flash‑lite → provider alternativo).

## 3) Come evitare che AI “medie” perdano nonostante KB

Le cause tipiche del “perdere” vs deep-think:
- retrieval prende chunk non ottimali (mancanza rerank/hybrid),
- answer non “chiude” il ragionamento (manca piano/checklist),
- nessun verification pass,
- citazioni non evidenti (percezione bassa),
- UX streaming fragile.

Le leve più efficaci:
- **reranking/hybrid** sui casi hard,
- **structured answers** (checklist, step, tabelle) con schema,
- **precision mode** che attiva: super model + rerank + verifier,
- **evidence pack** (fonti + snippet + link + “perché queste fonti”).

## 4) Raccomandazione concreta per NUZANTARA

1) Definire 3 tier:
   - **Fast** (default): flash/mini per 80% casi
   - **Pro**: per query ambigue o business-critical
   - **Deep Think / Super**: per high-stakes o su richiesta
2) Agganciare i tier a segnali misurabili:
   - retrieval score, #conflict, #fallback, #tool calls, lunghezza contesto
3) Rendere visibile in UI:
   - toggle “Fast ↔ Precision”
   - “Retry with Deep Think” dopo una risposta insoddisfacente
4) Misurare con evaluator:
   - A/B routing, regressioni su dataset, KPI: faithfulness + task success.

