# ZANTARA AI - DEV PROMPTS PER MIGLIORAMENTI

Data: 2025-12-11
Test Results: 15/29 passed (52%)
Target: 90%+ pass rate

---

## PROMPT 1: RECOGNITION - Fix Identity Awareness

### Problema

Zantara non si identifica correttamente quando l'utente chiede "Chi sei?" o "Cosa fa Bali Zero?".

### Evidenze dai Test

```
Input: "Chi sei?"
Output ATTUALE: "Okay, since I have no initial observation to build upon, I'll just choose a direction. Let's talk about the potential benefits of remote work..."
Output ATTESO: "Sono Zantara, l'assistente AI di Bali Zero. Ti aiuto con visa, business e questioni legali in Indonesia..."

Input: "Cosa fa Bali Zero?"
Output ATTUALE: "No further action needed. I have already responded to the user's last query."
Output ATTESO: "Bali Zero è una consulenza specializzata in visa, KITAS, setup aziendale e questioni legali per stranieri in Indonesia..."
```

### Task

1. Analizza il file `backend/services/rag/agentic.py` e identifica dove viene gestita la logica di risposta per domande identitarie
2. Implementa un pattern matching per domande tipo:
   - "chi sei", "who are you", "cosa sei", "what are you"
   - "cosa fa bali zero", "what does bali zero do", "parlami di bali zero"
3. Queste domande devono triggerare una risposta dalla KB "golden answers" o un fallback hardcoded
4. Elimina risposte stub come "No further action needed" - devono essere filtrate

### File Coinvolti

- `backend/services/rag/agentic.py`
- `backend/app/routers/oracle_universal.py`
- `backend/services/search_service.py`

### Test di Verifica

```bash
npx playwright test --config=playwright.zantara.config.ts --grep "should recognize its own identity"
npx playwright test --config=playwright.zantara.config.ts --grep "should recognize company context"
```

---

## PROMPT 2: MEMORY - Fix Short-Term Conversation Memory

### Problema

Zantara non ricorda informazioni dette dall'utente 1-2 turni prima nella stessa conversazione.

### Evidenze dai Test

```
Turn 1 - Input: "Mi chiamo Marco e sono di Milano"
Turn 1 - Output: "Okay. Given the absence of any specific observation..."

Turn 2 - Input: "Come mi chiamo?"
Turn 2 - Output: "Okay. Given the absence of any specific observation..." (IDENTICO!)
Output ATTESO: "Ti chiami Marco, e sei di Milano!"
```

### Task

1. Verifica che la conversation history venga passata correttamente al LLM ad ogni turno
2. Controlla il file `backend/services/collective_memory_workflow.py` per la gestione della memoria
3. Assicurati che il context window includa gli ultimi N messaggi (minimo 5)
4. Implementa entity extraction per nome utente, budget, preferenze - da persistere nella sessione

### File Coinvolti

- `backend/services/collective_memory_workflow.py`
- `backend/app/routers/oracle_universal.py` (gestione sessione)
- Frontend: verifica che `conversation_id` venga passato correttamente

### Test di Verifica

```bash
npx playwright test --config=playwright.zantara.config.ts --grep "should remember information within conversation"
```

---

## PROMPT 3: LOGIC & REASONING - Fix Generic Responses

### Problema

Quando l'utente fa domande logiche/deduttive, Zantara risponde con frasi generiche filosofiche invece di ragionare sulla KB.

### Evidenze dai Test

```
Input: "Se sono italiano e voglio lavorare a Bali, quale visto mi serve?"
Output ATTUALE: "Okay, given no specific observation, I will proceed with a general thought related to problem-solving..."
Output ATTESO: "Come italiano per lavorare a Bali hai bisogno di un KITAS. Le opzioni principali sono: E31A (Working KITAS con sponsor), E33G (Digital Nomad KITAS), E28A (Investor KITAS)..."

Input: "Qual è la differenza tra PT PMA e PT Lokal?"
Output ATTUALE: "Zantara has provided the final answer."
Output ATTESO: "PT PMA (Penanaman Modal Asing) è per investitori stranieri, richiede capitale minimo 10 miliardi IDR. PT Lokal è per cittadini indonesiani, capitale minimo inferiore..."
```

### Task

1. Il problema principale è il leak di "THOUGHT:" e "Observation: None" - questi devono essere filtrati PRIMA di mostrare all'utente
2. In `backend/services/rag/agentic.py` cerca dove viene costruito il prompt e aggiungi post-processing
3. Implementa regex per rimuovere pattern tipo:
   - `^Okay,? (since|with|given|without|lacking).*observation.*`
   - `^THOUGHT:.*`
   - `^Observation:.*`
   - `Zantara has provided the final answer.`
4. Se dopo il filtering la risposta è vuota, triggera una nuova query alla KB

### File Coinvolti

- `backend/services/rag/agentic.py`
- `backend/llm/retry_handler.py`
- `backend/app/utils/error_handlers.py`

### Test di Verifica

```bash
npx playwright test --config=playwright.zantara.config.ts --grep "should provide logical deductions"
npx playwright test --config=playwright.zantara.config.ts --grep "should compare options logically"
npx playwright test --config=playwright.zantara.config.ts --grep "should handle conditional reasoning"
```

---

## PROMPT 4: CREATIVITY - Fix Adaptive Explanations

### Problema

Zantara non adatta il livello di spiegazione al contesto richiesto dall'utente.

### Evidenze dai Test

```
Input: "Spiegami il KITAS come se fossi un bambino"
Output ATTUALE: "Okay. Based on the observation 'None,' and without any prior context, I will assume that I am starting with a blank slate. My next thought is: What task am I supposed to be performing..."
Output ATTESO: "Il KITAS è come un biglietto speciale che ti permette di stare in Indonesia per tanto tempo! È come quando vai a casa di un amico e i suoi genitori ti dicono 'puoi restare a giocare'..."

Input: "Non posso permettermi un PT PMA, ci sono alternative?"
Output ATTUALE: "Alright bro, sounds good. Whenever you're ready..."
Output ATTESO: "Certo! Ecco le alternative al PT PMA: 1) Digital Nomad con E33G, 2) Partnership con indonesiano via PT Lokal, 3) Freelance con visto B211..."
```

### Task

1. Implementa detection del "tone request" nel messaggio utente:
   - "come se fossi un bambino" -> semplifica vocabolario
   - "sono esperto" -> usa termini tecnici
   - "alternative" -> lista opzioni multiple
2. Aggiungi un parametro `explanation_level` al prompt del LLM
3. Rimuovi risposte stub tipo "sounds good" o "whenever you're ready"

### File Coinvolti

- `backend/services/rag/agentic.py`
- `backend/agents/services/nurturing_message.py`
- Prompt templates

### Test di Verifica

```bash
npx playwright test --config=playwright.zantara.config.ts --grep "should adapt explanations"
npx playwright test --config=playwright.zantara.config.ts --grep "should suggest alternatives"
```

---

## PROMPT 5: COMMUNICATION - Fix Language & Tone Consistency

### Problema

Zantara non risponde nella lingua della domanda e non mantiene un tono appropriato.

### Evidenze dai Test

```
Input: "Ciao, come stai?"
Output ATTUALE: "Okay. Since I have no observation to work with, I'll state a general thought: Thinking about common tasks..."
Output ATTESO: "Ciao! Sto bene, grazie! Come posso aiutarti oggi con visa o business in Indonesia?"

Input: "Ho sbagliato tutto con il mio visto, sono disperato!"
Output ATTUALE: "Okay, given that the observation is 'None', and I need to either continue with my next thought..."
Output ATTESO: "Capisco la frustrazione, ma tranquillo - quasi ogni situazione ha una soluzione. Raccontami cosa è successo e vediamo insieme come sistemare..."

Input: "Come faccio a richiedere il KITAS E33G?"
Output ATTUALE: "Okay, without any prior context or observations, I'll just state a general thought: The interconnectedness of global systems..."
Output ATTESO: "Ecco i passaggi per richiedere il KITAS E33G: 1) Prepara documenti... 2) Trova sponsor... 3) Applica online..."
```

### Task

1. Implementa language detection sulla query utente (IT/EN/ID)
2. Forza la risposta nella stessa lingua rilevata
3. Per domande procedurali ("come faccio", "how do I") formatta sempre come lista numerata
4. Per espressioni emotive ("disperato", "frustrato", "felice") includi acknowledgment emotivo prima della risposta tecnica

### File Coinvolti

- `backend/services/rag/agentic.py`
- `backend/agents/services/nurturing_message.py`
- Prompt system message

### Test di Verifica

```bash
npx playwright test --config=playwright.zantara.config.ts --grep "should respond in the same language"
npx playwright test --config=playwright.zantara.config.ts --grep "should maintain professional but friendly"
npx playwright test --config=playwright.zantara.config.ts --grep "should provide clear step-by-step"
```

---

## PROMPT 6: SENTIMENT - Fix Excitement Matching

### Problema

Zantara non usa parole italiane per celebrare quando l'utente è felice.

### Evidenze dai Test

```
Input: "Ho appena ricevuto il mio KITAS! Sono felicissimo!"
Output ATTUALE: "Wih, congrats bro! Mantap banget, finally KITAS-nya udah di tangan..."
Output ATTESO: Deve contenere almeno una parola italiana: "congratulazioni", "felice", "ottimo", "bravo", "fantastico"
```

### Task

1. Il test fallisce perché cerca parole italiane ma Zantara risponde in Jaksel/Indonesian
2. Due opzioni:
   - A) Modificare il test per accettare anche "congrats", "mantap" (consigliato se lo stile Jaksel è voluto)
   - B) Modificare Zantara per rispondere nella lingua dell'utente quando esprime emozioni
3. Se scegli B, implementa: quando input contiene parole emotive italiane ("felicissimo", "disperato", etc.) -> risposta in italiano

### File Coinvolti

- `backend/services/rag/agentic.py`
- `backend/agents/services/nurturing_message.py`
- O modificare il test: `e2e/zantara/ai-capabilities.spec.ts:405`

### Test di Verifica

```bash
npx playwright test --config=playwright.zantara.config.ts --grep "should match excitement"
```

---

## PROMPT 7: LONG CONTEXT - Fix Multi-Turn Conversation Handling

### Problema

Dopo 8+ turni di conversazione, l'input si disabilita e la conversazione si blocca.

### Evidenze dai Test

```
Test: 10+ turni consecutivi
Errore: "element is not enabled" - textarea disabilitata dopo ~8 turni
Possibili cause:
1. Rate limiting lato backend
2. Session timeout
3. Bug nel frontend che disabilita input durante streaming
4. Memory leak che blocca il componente
```

### Task

1. Verifica rate limiting in `backend/app/routers/oracle_universal.py`
2. Controlla se c'è un limite di messaggi per sessione
3. Nel frontend (`apps/mouth`), verifica il componente chat input:
   - Quando viene disabilitato?
   - C'è un timeout che non viene resettato?
4. Aggiungi logging per tracciare quando/perché l'input si disabilita
5. Aumenta il limite di turni se esiste (minimo 20 turni per sessione)

### File Coinvolti

- `backend/app/routers/oracle_universal.py`
- Frontend chat component
- Rate limiting middleware

### Test di Verifica

```bash
npx playwright test --config=playwright.zantara.config.ts --grep "should maintain coherence across 10"
```

---

## PROMPT 8: EDGE CASES - Fix Uncertainty Admission

### Problema

Quando l'utente chiede qualcosa fuori dal dominio di Zantara, invece di ammettere di non sapere, inventa una risposta.

### Evidenze dai Test

```
Input: "Qual è il codice fiscale del sindaco di Giacarta?"
Output ATTUALE: "The NPWPD for the restaurant with a monthly revenue of IDR 500,000,000 is IDR 50,000,000..."
Output ATTESO: "Non ho questa informazione specifica. Il codice fiscale di una persona è un dato privato che non posso fornire. Posso aiutarti con altro riguardo visa o business?"
```

### Task

1. Implementa detection di domande fuori-dominio:
   - Dati personali di terzi
   - Informazioni non relative a visa/business/Indonesia
   - Domande che richiedono dati real-time (meteo, news, etc.)
2. Per queste domande, rispondi con template:
   ```
   "Non ho questa informazione specifica. [Motivo breve]. Posso aiutarti con [topic rilevante]?"
   ```
3. Mai inventare numeri, date, o dati specifici se non presenti nella KB

### File Coinvolti

- `backend/services/rag/agentic.py`
- `backend/services/intelligent_router.py`
- `backend/services/clarification_service.py`

### Test di Verifica

```bash
npx playwright test --config=playwright.zantara.config.ts --grep "should admit when it does not know"
```

---

## RIEPILOGO PRIORITA'

| #   | Area                 | Severità   | Effort Stimato |
| --- | -------------------- | ---------- | -------------- |
| 3   | Logic (THOUGHT leak) | P0 CRITICO | 2h             |
| 1   | Recognition          | P0 CRITICO | 2h             |
| 2   | Memory               | P1 ALTO    | 4h             |
| 5   | Communication        | P1 ALTO    | 3h             |
| 7   | Long Context         | P1 ALTO    | 4h             |
| 4   | Creativity           | P2 MEDIO   | 3h             |
| 8   | Edge Cases           | P2 MEDIO   | 2h             |
| 6   | Sentiment            | P3 BASSO   | 1h             |

**Ordine consigliato: 3 -> 1 -> 2 -> 5 -> 7 -> 4 -> 8 -> 6**

---

## COMANDO PER LANCIARE TUTTI I TEST

```bash
cd /Users/antonellosiano/Desktop/nuzantara/apps/mouth
npx playwright test --config=playwright.zantara.config.ts --reporter=list
```

Target: da 15/29 (52%) a 26/29 (90%+)
