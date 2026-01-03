# Piano Coinvolgimento Team Bali Zero

> Obiettivo: Trasformare il team da "dipendenti" a "contributori attivi" del sistema Zantara

---

## Timeline Overview

```
Settimana 1-2:  Setup strumenti + Training base
Settimana 3-4:  CRM Population (priorità alta)
Settimana 5-6:  Zantara Feedback Loop
Settimana 7-8:  Content Pipeline
Settimana 9+:   Testing + Continuous Improvement
```

---

## 1. CRM - Popolare migliaia di clienti

### Obiettivo
Importare tutti i clienti storici nel sistema CRM entro 4 settimane.

### Fase 1: Raccolta dati (Settimana 1)

**Fonti da identificare:**
- [ ] Export WhatsApp Business (chat clienti)
- [ ] Spreadsheet Excel esistenti
- [ ] Email (inbox scanning)
- [ ] Documenti cartacei/PDF
- [ ] Zoho CRM precedente (se esiste)

**Tool: Google Sheet "Client Master"**
```
Colonne:
- Nome completo
- Email
- WhatsApp
- Nazionalità
- Servizio richiesto (KITAS/PT PMA/Tax/etc)
- Data primo contatto
- Status (Lead/Active/Completed/Lost)
- Valore stimato (IDR)
- Note
```

### Fase 2: Data Entry Team (Settimana 2-4)

**Assegnazione:**
- Ogni membro team = 1 fonte dati specifica
- Target: 50 clienti/giorno per persona
- Review giornaliero: tu verifichi qualità

**Processo:**
```
Team inserisce in Google Sheet
        ↓
Script automatico valida dati
        ↓
Import in PostgreSQL (tabella clients)
        ↓
Zantara può accedere allo storico
```

### Fase 3: Automazione (Settimana 4+)

**AI-Assisted Import:**
- WhatsApp chat → AI estrae automaticamente nome/email/servizio
- Email inbox → AI categorizza e estrae lead
- Team verifica e approva (non inserisce manualmente)

### Deliverables
- [ ] Google Sheet template con validazione
- [ ] Script import CSV → PostgreSQL
- [ ] Dashboard "CRM Progress" (quanti clienti inseriti)
- [ ] AI extractor per WhatsApp export

---

## 2. Training Zantara - Feedback Loop

### Obiettivo
Ogni errore di Zantara diventa training data. Il team nutre l'AI quotidianamente.

### Sistema "Zantara Ha Sbagliato"

**Form semplice (Google Form → Sheet → Auto-ingest):**
```
1. Domanda del cliente: [text]
2. Risposta di Zantara: [screenshot o copia-incolla]
3. Cosa c'era di sbagliato: [dropdown]
   - Prezzo errato
   - Procedura sbagliata
   - Info mancante
   - Risposta confusa
   - Lingua sbagliata
   - Altro
4. Risposta CORRETTA: [text - OBBLIGATORIO]
5. Fonte (come sai che è corretto): [text]
```

**Workflow automatico:**
```
Team compila form
        ↓
Notifica Slack/Telegram a te
        ↓
Tu approvi con 1 click
        ↓
Auto-ingest in training_conversations
        ↓
Zantara impara
```

### Sistema "Domanda Reale del Cliente"

**Ogni chiamata/chat = training data**

Form giornaliero per team:
```
1. Domanda del cliente (esatta): [text]
2. La tua risposta: [text]
3. Categoria: [dropdown - Visa/Business/Tax/Property/Other]
4. Difficoltà: [1-5]
5. Cliente soddisfatto: [Sì/No/Non so]
```

**Target:** 5 Q&A per persona al giorno = 25/giorno = 175/settimana

### Golden Answers Review

**Settimanale (tu):**
- Revisiona top 20 submission
- Marca come "Golden Answer"
- Queste diventano training prioritario

### Deliverables
- [ ] Google Form "Zantara Ha Sbagliato"
- [ ] Google Form "Domanda Cliente"
- [ ] Script auto-ingest Form → Qdrant
- [ ] Bot Telegram notifiche
- [ ] Dashboard "Training Progress"

---

## 3. Content Pipeline - Sito Web + Blog

### Obiettivo
Pubblicare 2-4 articoli/settimana con contributo del team.

### Ruoli

| Ruolo | Chi | Cosa fa |
|-------|-----|---------|
| **Subject Expert** | Team member | Scrive bullet points / appunti grezzi |
| **AI Writer** | Claude/Zantara | Trasforma in articolo SEO |
| **Reviewer** | Tu | Approva e pubblica |
| **Translator** | Team | Versione Bahasa Indonesia |

### Workflow Articolo

```
1. Team scrive in Google Doc:
   - Titolo idea
   - 5-10 bullet points
   - Fonti/link utili

2. AI (Claude) trasforma in:
   - Articolo 800-1500 parole
   - Meta description
   - FAQ section
   - Internal links

3. Tu revisioni (5 min)

4. Team traduce in Bahasa (se serve)

5. Pubblicazione automatica
```

### Content Calendar

**Assegnazione settimanale:**
```
Lunedì: Visa topic (Ruslana)
Martedì: Business/PT PMA (Krisna)
Mercoledì: Tax topic (Veronika)
Giovedì: Lifestyle/Property (Adit)
Venerdì: News/Updates (rotazione)
```

### Tipi di contenuto facili per il team

1. **"Caso reale"** - Storia di un cliente (anonimizzata)
2. **"Errore comune"** - Cosa sbagliano i clienti
3. **"Novità"** - Cambio normativa/prezzo
4. **"FAQ"** - Domande frequenti della settimana
5. **"Checklist"** - Documenti necessari per X

### Deliverables
- [ ] Google Doc template "Idea Articolo"
- [ ] Content calendar condiviso
- [ ] Script AI: bullet points → articolo
- [ ] Workflow approvazione (1 click)
- [ ] Auto-publish to website

---

## 4. Testing - CI/CD + Team QA

### Obiettivo
Test coverage >90% con team che contribuisce scenari reali.

### Due tipi di testing

#### A. Automated Tests (tu + CI/CD)
```
Push code → GitHub Actions → pytest → Report
```

**Setup:**
- GitHub Actions workflow
- Test report pubblicato su Slack/Telegram
- Badge coverage nel README

#### B. Manual QA (team)

**"Test come un cliente"**

Checklist settimanale per ogni team member:
```
[ ] Login funziona
[ ] Chat risponde entro 30 sec
[ ] Risposta in italiano se chiedo in italiano
[ ] Risposta in inglese se chiedo in inglese
[ ] Prezzi corretti per KITAS
[ ] Prezzi corretti per PT PMA
[ ] Click su "Online" funziona
[ ] Feedback button funziona
[ ] ... (20 items)
```

**Bug Report Form:**
```
1. Cosa stavi facendo: [text]
2. Cosa ti aspettavi: [text]
3. Cosa è successo: [text]
4. Screenshot: [upload]
5. Dispositivo: [dropdown - PC/iPhone/Android]
6. Browser: [dropdown - Chrome/Safari/Firefox]
```

### Test Scenarios dal Team

**Il team scrive in linguaggio naturale:**
```
"Quando un cliente chiede il prezzo del KITAS investor,
Zantara deve rispondere con IDR 45.000.000
e menzionare che include RPTKA"
```

**Io converto in test automatico:**
```python
async def test_kitas_investor_pricing():
    response = await zantara.ask("Quanto costa il KITAS investor?")
    assert "45" in response or "45.000.000" in response
    assert "RPTKA" in response.lower()
```

### Deliverables
- [ ] GitHub Actions workflow
- [ ] Test report Telegram bot
- [ ] QA Checklist Google Sheet
- [ ] Bug Report Google Form
- [ ] Script: scenario naturale → pytest

---

## Setup Iniziale (Settimana 1)

### Strumenti da creare

| Tool | Scopo | Priorità |
|------|-------|----------|
| Google Sheet "CRM Import" | Data entry clienti | P0 |
| Google Form "Zantara Feedback" | Segnalare errori | P0 |
| Google Form "Domanda Cliente" | Training data | P0 |
| Telegram Bot | Notifiche al team | P1 |
| Dashboard Progress | Vedere metriche | P1 |
| Content Calendar | Pianificare articoli | P2 |

### Training Team (1 sessione 2 ore)

**Agenda:**
1. Cos'è Zantara e come funziona (30 min)
2. Demo: fare domande e vedere risposte (15 min)
3. Come segnalare errori (15 min)
4. Come inserire clienti nel CRM (30 min)
5. Come scrivere contenuti (20 min)
6. Q&A (10 min)

### Metriche Successo

| Metrica | Target Settimana 4 | Target Mese 3 |
|---------|-------------------|---------------|
| Clienti in CRM | 500 | 2000+ |
| Training submissions | 100 | 500+ |
| Articoli pubblicati | 4 | 20+ |
| Bug reports | 10 | 50+ |
| Test coverage | 70% | 90%+ |

---

## Incentivi Team

### Gamification

**Leaderboard settimanale:**
- Chi ha inserito più clienti
- Chi ha segnalato più errori utili
- Chi ha scritto più contenuti

**Premi:**
- Top contributor = bonus/regalo
- "Zantara Trainer of the Month"
- Riconoscimento pubblico

### Ownership

**Assegnare aree di responsabilità:**
- Ruslana = "Visa Expert" → responsabile accuracy visa
- Krisna = "Business Expert" → responsabile PT PMA content
- etc.

Quando Zantara risponde bene su visa → merito di Ruslana
Quando sbaglia → Ruslana deve correggere

---

## Next Steps Immediati

### Oggi
1. [ ] Creare Google Sheet CRM template
2. [ ] Creare Google Form "Zantara Feedback"
3. [ ] Setup Telegram bot notifiche

### Questa settimana
4. [ ] Meeting team per spiegare il piano
5. [ ] Assegnare prime task
6. [ ] Iniziare data entry CRM

### Prossima settimana
7. [ ] Review primi risultati
8. [ ] Aggiustare processo
9. [ ] Scalare

---

## Note per Antonello

Ricorda:
- **Pazienza** - non diventeranno esperti in una settimana
- **Feedback positivo** - celebra ogni contributo
- **Iterazione** - il processo migliorerà col tempo
- **Delega vera** - lascia che sbaglino e imparino

Il team indonesiano ha un VANTAGGIO enorme:
- Parlano Bahasa nativo
- Capiscono la cultura locale
- Hanno relazioni con clienti
- Conoscono le procedure dal vivo

Tu hai costruito il cervello (Zantara).
Loro possono essere le mani, gli occhi, le orecchie.

---

*Piano creato: 2 Gennaio 2026*
*Prossima review: 9 Gennaio 2026*
