# PROMPT: Generazione Schede Tecniche KBLI

## ISTRUZIONI

Genera una scheda tecnica completa e strutturata per il KBLI specificato. La scheda deve essere pronta per essere usata in un sistema RAG (Retrieval Augmented Generation) per assistere investitori stranieri in Indonesia.

---

## INPUT

**KBLI Code:** [INSERISCI CODICE KBLI, es. 55101]
**KBLI Title (Indonesiano):** [INSERISCI TITOLO INDONESIANO]

---

## OUTPUT RICHIESTO

Genera la scheda nel seguente formato:

```markdown
# KBLI [CODE]: [TITLE]

## 1. DEFINIZIONE UFFICIALE

**Nome Indonesiano:** [AKTIVITAS...]
**Traduzione Italiana:** [Attività di...]

**Descrizione completa:**
[2-3 frasi che descrivono esattamente cosa copre questo KBLI, includendo ambito operativo]

---

## 2. AMBITO OPERATIVO

### Cosa è INCLUSO:
- [Attività specifica 1]
- [Attività specifica 2]
- [Attività specifica 3]

### Cosa è ESCLUSO (KBLI diversi):
- [Attività simile ma diversa] → KBLI [XXXXX]
- [Attività simile ma diversa] → KBLI [XXXXX]

---

## 3. ESEMPI CONCRETI DI BUSINESS

| Tipo Business | Descrizione | Dimensione Tipica |
|--------------|-------------|-------------------|
| [Esempio 1] | [Breve descrizione] | [Piccola/Media/Grande] |
| [Esempio 2] | [Breve descrizione] | [Piccola/Media/Grande] |
| [Esempio 3] | [Breve descrizione] | [Piccola/Media/Grande] |

---

## 4. STATUS INVESTIMENTO ESTERO (PMA)

### Apertura a Stranieri:
- [ ] **TERBUKA** (100% Foreign Ownership) - Spiega condizioni
- [ ] **TERBATAS** (Ownership Limitata) - Specifica % massima
- [ ] **TERTUTUP** (Chiuso a stranieri) - Spiega alternative

### Condizioni Speciali:
- [Requisiti specifici per stranieri]
- [Restrizioni geografiche]
- [Requisiti partnership locale]

---

## 5. REQUISITI LEGALI E LICENZE

### Licenze Base (tutti devono avere):
- **NIB** (Nomor Induk Berusaha) - Identificativo fiscale
- **[Altre licenze standard]**

### Licenze Specifiche (se applicabili):
| Licenza | Quando Richiesta | Autorità Rilascio |
|---------|------------------|-------------------|
| [Nome licenza] | [Condizione] | [Ente] |

### Certificazioni Sanitarie/Sicurezza:
- [Lista certificazioni richieste]

---

## 6. LIVELLO RISCHIO E SKALA USAHA

### Classificazione Rischio:
- [ ] **Rendah** (Basso) - Solo NIB
- [ ] **Menengah** (Medio) - NIB + Sertifikat Standar
- [ ] **Tinggi** (Alto) - NIB + Izin Usaha

### Categorie Scala Business:
| Categoria | Investimento | Dipendenti | Esempio |
|-----------|--------------|------------|---------|
| Mikro | < 50M IDR | < 4 | [Esempio] |
| Kecil | 50M-500M IDR | 5-19 | [Esempio] |
| Menengah | 500M-10M IDR | 20-99 | [Esempio] |
| Besar | > 10M IDR | > 100 | [Esempio] |

---

## 7. NOTE SPECIALI BALI

### Moratoria INGUB 6/2025:
- [ ] **Interessato** da moratoria - Specifiche limitazioni
- [ ] **Non interessato** - Spiega perché

### Restrizioni Specifiche Bali:
- [Limitazioni dimensione]
- [Zone vietate/protette]
- [Requisiti Desa Adat]

### Alternative se Bloccato:
- [Località alternative: Lombok, Gili, Java]
- [Strutture già esistenti in vendita]

---

## 8. CONFRONTO CON KBLI SIMILI

| Caratteristica | KBLI [THIS] | KBLI [SIMILE 1] | KBLI [SIMILE 2] |
|----------------|-------------|-----------------|-----------------|
| Struttura | [Tipo] | [Tipo] | [Tipo] |
| Mobilità | [Fissa/Mobile] | [Fissa/Mobile] | [Fissa/Mobile] |
| Investimento | [Livello] | [Livello] | [Livello] |

---

## 9. CASO D'USO CONSIGLIATO

### Scegli questo KBLI se:
- [Scenario ideale 1]
- [Scenario ideale 2]
- [Scenario ideale 3]

### NON scegliere questo KBLI se:
- [Scenario inappropriato 1] → Meglio KBLI [XXXX]
- [Scenario inappropriato 2] → Meglio KBLI [XXXX]

---

## 10. FAQ RAPIDE

**Q: Posso aprire [tipo business] con questo KBLI?**
A: [Risposta specifica]

**Q: Quanto capitale serve minimo?**
A: [Risposta con cifre]

**Q: Ci sono restrizioni per stranieri?**
A: [Risposta dettagliata]

**Q: A Bali ci sono limitazioni?**
A: [Risposta specifica moratoria]

---

## 11. RIFERIMENTI NORMATIVI

- **BPS Regulation:** No. 7 Tahun 2025
- **PP Licensing:** 28/2025 (replaces PP 5/2021)
- **Other relevant regulations:** [List]

---

**Ultimo Aggiornamento:** 2025
**Data Scheda:** [DATA]
**Fonte:** KBLI 2025 BPS + PP 28/2025
```

---

## REGOLE IMPORTANTI

1. **Sii SPECIFICO**: Non usare frasi generiche. Ogni KBLI ha peculiarità precise.

2. **Focus Investitori Stranieri**: Sempre specificare:
   - Se possono avere 100% ownership
   - Quanto capitale serve
   - Restrizioni geografiche (specialmente Bali)

3. **Formato Consistente**: Usa SEMPRE le stesse sezioni nello stesso ordine.

4. **Lingua**: Italiano per investitori, termini indonesiani tra parentesi.

5. **Bali Alert**: SEMPRE verificare impatto moratoria INGUB 6/2025.

6. **Confronti**: Per ogni KBLI, identifica almeno 2 KBLI simili e spiega differenze.

---

## ESEMPIO KBLI 56101 (GIÀ COMPLETATO)

[Vedi file esistente come riferimento qualità]

---

## KBLI DA COMPLETARE (Priorità)

### OSPITALITÀ:
- 55101 - Hotel Bintang
- 55120 - Hotel Melati/Villa  
- 55194 - Guest House
- 55201 - Bungalow

### COMMERCIO:
- 47111 - Supermarket/Minimarket
- 47112 - Minimarket (<400m²)
- 46100 - Perdagangan Besar (Import-Export)
- 46201 - Perdagangan Eceran

### TECNOLOGIA:
- 62019 - Software Development
- 63122 - Portal Web/Digital Marketplace
- 61912 - ISP

### WELLNESS:
- 86995 - Rumah Pijat (Massaggio)
- 96230 - Spa/Sauna
- 86903 - Gym/Fitness

### COSTRUZIONI:
- 41012 - Konstruksi Gedung
- 68111 - Perumahan (Real Estate)
- 43301 - Desain Interior

### ALTRO (dal tuo file):
- [Altri identificati nel file notlmz.pages]

---

## OUTPUT ATTESO

Per ogni KBLI, genera una scheda completa seguendo il template sopra.
La scheda deve essere:
- Tecnicamente accurata
- Pratica per investitori
- Aggiornata a KBLI 2025 + PP 28/2025
- Specifica per Bali dove rilevante
