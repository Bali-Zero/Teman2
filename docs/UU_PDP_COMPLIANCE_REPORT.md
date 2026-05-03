# Rapporto di Conformità Strategica e Architetturale

## Legge sulla Protezione dei Dati Personali (UU PDP) dell'Indonesia e Sicurezza nei Sistemi RAG

> Documento di riferimento legale-architetturale per Nuzantara / Bali Zero
> Basato su: UU PDP No. 27/2022, Sentenza Corte Costituzionale 151/2024,
> BSSN Reg. 1/2024 e 2/2024, PMK-112/PMK.03/2022, PER-6/PJ/2024
> Status: REFERENCE DOCUMENT — da consultare per ogni decisione architetturale

---

## 1. Contesto Normativo e Applicabilità Extraterritoriale della UU PDP

La transizione digitale dell'Indonesia, che vanta oltre 200 milioni di utenti internet attivi e una penetrazione dei servizi digitali in rapida espansione, ha reso imperativa l'adozione di un quadro normativo unificato per la salvaguardia delle informazioni personali. La Legge n. 27 del 2022 sulla Protezione dei Dati Personali (Undang-Undang Pelindungan Data Pribadi, di seguito "UU PDP") rappresenta la risposta istituzionale a questa esigenza.

Storicamente, le disposizioni in materia di privacy in Indonesia erano frammentate in oltre 30 leggi settoriali, creando lacune significative che hanno portato a violazioni sistemiche, specialmente nei settori dell'e-commerce, della finanza e della sanità. La promulgazione della UU PDP, ampiamente modellata sui principi del Regolamento Generale sulla Protezione dei Dati (GDPR) dell'Unione Europea, segna un punto di svolta fondamentale, introducendo obblighi rigorosi e un apparato sanzionatorio di natura penale e amministrativa.

Il fattore di criticità assoluta per le organizzazioni internazionali risiede nell'**Articolo 2** della UU PDP, che definisce in modo inequivocabile l'ambito di applicazione extraterritoriale della normativa. La legge si applica a qualsiasi persona fisica, entità pubblica, organizzazione internazionale o corporazione privata, indipendentemente dalla sua sede geografica o dalla localizzazione dei suoi server, qualora le sue attività di elaborazione dei dati abbiano conseguenze legali all'interno della giurisdizione indonesiana o incidano sui soggetti interessati cittadini indonesiani residenti all'estero.

L'elaborazione di documenti identificativi e fiscali di stranieri residenti in Indonesia (come passaporti internazionali, KTP per espatriati e NPWP) ricade pienamente e indiscutibilmente in questo perimetro giurisdizionale, configurando l'organizzazione che acquisisce tali dati come un "Titolare del Trattamento dei Dati Personali" (Personal Data Controller) a tutti gli effetti di legge.

Il periodo di transizione di due anni concesso dal legislatore alle organizzazioni per adeguare le proprie infrastrutture e procedure interne alla UU PDP si è concluso formalmente e in via definitiva il **17 ottobre 2024**. Di conseguenza, il regime sanzionatorio è attualmente pienamente esecutivo e applicabile senza ulteriori deroghe.

L'applicazione della legge è demandata alle autorità di regolamentazione indonesiane, tra cui il Ministero delle Comunicazioni e del Digitale (MOCD), l'Agenzia Nazionale per la Sicurezza e la Crittografia (BSSN) e l'Agenzia per la Protezione dei Dati Personali (Lembaga PDP), un'autorità di vigilanza indipendente istituita dalla legge, la cui piena operatività strutturale e organizzativa è prevista tra la fine del 2025 e il 2026.

---

## 2. Classificazione e Profilo di Rischio dei Dati

### 2.1 Tassonomia Legale dei Dati Elaborati

L'**Articolo 4** della UU PDP stabilisce una dicotomia fondamentale:

| Tipologia di Documento        | Classificazione UU PDP                            | Implicazioni Architetturali                                                                                                                                                                                          |
| ----------------------------- | ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Passaporto Internazionale** | Dato Generale (con elementi Specifici potenziali) | Se la fotografia viene elaborata tramite sistemi automatizzati di riconoscimento facciale o verifica biometrica (es. OCR), i dati estratti transitano nella categoria dei **Dati Personali Specifici (Biometrici)**. |
| **KTP e NIK**                 | Dato Generale                                     | Il NIK (16 cifre) è l'identificatore primario univoco per ogni interazione civile, finanziaria, governativa e sanitaria in Indonesia. La sua esfiltrazione consente profilazioni estese.                             |
| **NPWP**                      | Dato Generale (Finanziario/Fiscale)               | L'associazione con il NIK e con dati transazionali lo rende un elemento sensibile.                                                                                                                                   |

### 2.2 L'Evoluzione del Formato NPWP — Implicazioni per i Sistemi IT

**CRITICO per regex e DLP**: Il formato NPWP è cambiato da 15 a 16 cifre (PMK-112/PMK.03/2022, PER-6/PJ/2024):

- **Cittadini Indonesiani**: NPWP = NIK (16 cifre)
- **Stranieri e Aziende**: vecchio 15 cifre + "0" iniziale → `092.929.292.9-292.000`
- **Filiali**: nuovo NITKU (Business Location Identification Number)

**I sistemi regex configurati per 15 cifre falliranno silenziosamente** sui nuovi NPWP degli stranieri → violazione UU PDP per mancato mascheramento.

---

## 3. Acquisizione del Consenso

### 3.1 Requisiti di Validità (Articoli 20-22)

La UU PDP **rigetta esplicitamente**: opt-out, consenso presunto, pre-spuntatura caselle, continuazione navigazione.

Requisiti del Consent Banner (Art. 21):

| Requisito                | Implementazione                                                    |
| ------------------------ | ------------------------------------------------------------------ |
| Legalità e Scopo         | Dichiarazione chiara del perché passport/KTP/NPWP vengono raccolti |
| Tipologia Dati           | Elenco specifico: "Numero di Passaporto, NIK, NPWP a 16 cifre"     |
| Periodo di Conservazione | Indicazione precisa del ciclo di vita                              |
| Diritti dell'Interessato | Accesso, rettifica, cancellazione, ritiro consenso                 |

### 3.2 Il Limite delle 72 Ore per Ritiro Consenso

**Articoli 9, 40, 43**: una volta ritirato il consenso, il Titolare deve **cancellare tutti i dati entro 72 ore**. Questo è un SLA normativo la cui violazione espone a sanzioni immediate.

L'audit log del consenso deve contenere:

- ID utente o identificatore sessione crittografato
- Timestamp esatto dell'opt-in
- Versione esatta della Privacy Policy presentata
- Flag consenso per ogni finalità specifica

---

## 4. DPO e DPIA

### 4.1 DPIA Obbligatoria (Articolo 34)

Deve essere condotta **prima** di iniziare il processing per:

- Nuove tecnologie (AI generativa sui dati clienti)
- Elaborazione su larga scala di dati specifici
- Decisioni automatizzate con conseguenze legali
- Monitoraggio sistematico (profilazione)

### 4.2 DPO — Sentenza Corte Costituzionale 151/2024

**FONDAMENTALE**: La Corte Costituzionale (30 luglio 2025) ha dichiarato incostituzionale la congiunzione "e" nell'Articolo 53(1), sostituendola con **"e/o"**.

Conseguenza: la nomina del DPO è obbligatoria se si soddisfa **almeno UNA** (non tutte) delle condizioni:

1. Elaborazione per servizi di interesse pubblico
2. **Monitoraggio regolare e sistematico su larga scala** ← NOI
3. Elaborazione su larga scala di Dati Specifici ← NOI (biometria passport)

**La nomina del DPO è un imperativo legale per Bali Zero.**

---

## 5. Incident Response e Direttive BSSN

### 5.1 CIRT Organizzativo (BSSN Reg. 1/2024)

Obbligatorio istituire un Cyber Incident Response Team:

- Registrato presso il National CIRT della BSSN
- Gestione end-to-end: preparazione → identificazione → contenimento → eradicazione → ripristino → post-incident
- **Condivisione obbligatoria IoC** con le autorità (Art. 8 Reg. 1/2024)

### 5.2 Piano di Contingenza (BSSN Reg. 2/2024)

| Fase              | Azioni                                                                 |
| ----------------- | ---------------------------------------------------------------------- |
| **Pre-Crisi**     | Early Warning dal National CIRT, contromisure immediate                |
| **Durante Crisi** | Mitigazione, comunicazione, fondi emergenza, reportistica continua     |
| **Post-Crisi**    | Valutazione forense, stima costi, audit retrospettivi, lezioni apprese |

**Simulazioni obbligatorie**: almeno ogni 2 anni. Piani valutati annualmente dalla BSSN.

---

## 6. Il Protocollo delle 72 Ore

### 6.1 Definizione di Breach

Qualsiasi fallimento che comporti accesso non autorizzato, alterazione, distruzione, perdita o divulgazione di dati. Database contenenti passport/KTP/NPWP esfiltrati → soglia materialità superata istantaneamente.

### 6.2 Cronoprogramma Operativo

| Orizzonte | Fase                             | Dettaglio                                                                                        |
| --------- | -------------------------------- | ------------------------------------------------------------------------------------------------ |
| 0-6h      | Scoperta + Attivazione CIRT      | Rilevamento anomalia, mobilitazione team                                                         |
| 2-24h     | Contenimento + Triage            | Isolamento server, revoca token, analisi forense                                                 |
| 12-48h    | Identificazione dati compromessi | Analisi log, volume e tipologia dati esfiltrati                                                  |
| 40-72h    | Stesura rapporto legale          | DPO + legali redigono notifica Art. 46                                                           |
| 60-72h    | **Notifica**                     | Invio a MOCD (pengendalianaptika@kominfo.go.id) + BSSN (aid70@bssn.go.id) + soggetti interessati |

### 6.3 Contenuto Notifica (Art. 46)

- Natura e tipologia esatta dei dati compromessi
- Tempistica cronologica (inizio incidente + scoperta)
- Meccanica tecnica (vulnerabilità sfruttata)
- Misure intraprese per mitigare

---

## 7. Architettura Sanzionatoria

### 7.1 Sanzioni Amministrative (Art. 57)

1. Avvertimenti formali scritti
2. **Sospensione temporanea** delle operazioni di elaborazione
3. Ordine di cancellazione database non conformi
4. **Ammende fino al 2% del fatturato annuale**

### 7.2 Sanzioni Penali (Artt. 65, 67, 68)

| Reato                     | Pena detentiva | Multa                               |
| ------------------------- | -------------- | ----------------------------------- |
| Divulgazione/uso illecito | 4-5 anni       | IDR 4-5 miliardi                    |
| Falsificazione dati       | **6 anni**     | **IDR 6 miliardi**                  |
| Acquisto/vendita database | —              | Fino a **IDR 60 miliardi** (~$3.8M) |

### 7.3 Responsabilità Corporativa (Art. 69)

Per le aziende condannate:

- Confisca profitti/beni
- Congelamento attività
- Revoca permanente licenze
- **Scioglimento definitivo dell'azienda in Indonesia**

---

## 8. Audit e Sicurezza PII nelle Architetture RAG

### 8.1 Vulnerabilità "Contextual Leakage"

Il sistema RAG estrae documenti sensibili dal database vettoriale e li inietta nel contesto dell'LLM. Una volta nel contesto:

- Prompt injection può estrarre PII
- L'LLM può includere PII nelle risposte
- Il controllo deterministico viene meno

Violazione diretta di Artt. 35, 36, 38 UU PDP.

### 8.2 Pipeline di Sicurezza PII per RAG

| Fase RAG              | Strategia di Sicurezza                                                        |
| --------------------- | ----------------------------------------------------------------------------- |
| **1. Data Ingestion** | Mascheramento pre-vettorizzazione con Presidio (NLP)                          |
| **2. Regex Custom**   | Riconoscitori per NIK 16 cifre, NPWP 16 cifre (con "0" iniziale stranieri)    |
| **3. Embedding**      | Sostituzione PII con token neutri (`<PASSPORT_REDACTED>`) prima del Vector DB |
| **4. Retrieval**      | RBAC basato su metadati per chunk — filtro per autorizzazioni utente          |
| **5. Egress**         | Firewall istruzionali + Egress Scanner sulle risposte LLM                     |

---

## 9. Direttrici di Implementazione

### Immediato:

1. **Consent Banner** crittografico immutabile con audit log
2. **Regex NPWP 16 cifre** aggiornate per stranieri (prefisso "0")
3. **Nomina DPO** (obbligatoria post-Sentenza 151/2024)
4. **DPIA** su tutti i sistemi RAG/LLM

### Organizzativo:

5. Istituzione **CIRT organizzativo** registrato presso BSSN
6. **Simulazioni** crisi biennali
7. Piano contingenza BSSN Reg. 2/2024 completo

### Architetturale:

8. **Presidio** con regex indonesiani su tutta la pipeline RAG
9. **RBAC** sui chunk vettoriali
10. **Egress scanner** sulle risposte LLM
11. **Audit trail** crittografico end-to-end (Art. 37)

---

_Documento di riferimento legale-architetturale_
_Basato su: UU PDP No. 27/2022, CC Sentenza 151/2024, BSSN Reg. 1-2/2024_
_Per: Nuzantara / Bali Zero — conformità sistemi RAG e processing PII_
