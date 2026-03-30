# UU PDP Compliance Plan — Nuzantara / Bali Zero

> Piano di conformità alla Legge sulla Protezione dei Dati Personali
> UU No. 27/2022 (in vigore dal 17 ottobre 2024)
>
> **Reference legale**: `docs/UU_PDP_COMPLIANCE_REPORT.md` — rapporto completo con articoli,
> sentenza Corte Costituzionale 151/2024, direttive BSSN, architettura RAG security
>
> Basato su: xAI deep research (legal + technical), NLM NB-1 PII audit codebase (27+ citazioni),
> NLM NB-9 (85 fonti web), rapporto strategico-architetturale completo
>
> **SCOPERTE CRITICHE POST-REPORT:**
> - **DPO OBBLIGATORIO** — Sentenza CC 151/2024 ha cambiato "e" in "e/o" nell'Art. 53
> - **CIRT OBBLIGATORIO** — BSSN Reg. 1/2024, registrato presso National CIRT
> - **NPWP 16 cifre** — regex da aggiornare per formato stranieri (prefisso "0")
> - **Simulazioni crisi biennali** — BSSN Reg. 2/2024, valutate annualmente dalla BSSN
> - **Scioglimento aziendale** possibile come sanzione (Art. 69)

---

## 1. PERCHÉ CI RIGUARDA

| Fattore | Dettaglio |
|---------|-----------|
| **Legge** | UU PDP No. 27/2022, pienamente in vigore |
| **Applicabilità** | Art. 2: extraterritoriale, si applica a processing con implicazioni legali in Indonesia |
| **Nostri dati** | Passport, KTP, NPWP, telefono, email, indirizzo, dati visa, chat history di 5000+ clienti |
| **Server** | Fly.io Singapore = cross-border transfer (Art. 56) |
| **Penalità** | Admin: 2% fatturato annuo. Penale: fino a 6 anni + IDR 6 miliardi |
| **Breach notification** | 72 ore per notificare autorità + soggetti interessati |
| **Enforcement** | Attivo da ott 2024. Constitutional Court ha confermato Art. 56 gen 2026 |

---

## 2. CLASSIFICAZIONE DEI NOSTRI DATI

### Dati Personali SPECIFICI (Art. 4(1)) — Protezione massima

| Dato | Dove lo processiamo | Perché è "specifico" |
|------|-------------------|---------------------|
| **Passport scan** (foto) | Upload portal → OCR → PostgreSQL + Drive | Contiene biometria (foto facciale) |
| **KTP scan** (foto) | Upload portal → OCR → PostgreSQL + Drive | Biometria + ID nazionale |
| **NPWP document** | Upload → OCR → PostgreSQL | Dato finanziario personale |
| **Dati salary/employer** (visa) | Form KITAS → PostgreSQL | Profilo finanziario |

→ Richiedono: **consenso esplicito** (Art. 21-25), DPIA (Art. 27), protezione rafforzata.

### Dati Personali GENERALI (Art. 4(2)) — Protezione standard

| Dato | Dove lo processiamo |
|------|-------------------|
| Nome completo | PostgreSQL `clients.full_name` |
| Email | PostgreSQL `clients.email` |
| Telefono (+62) | PostgreSQL `clients.phone` |
| Indirizzo | PostgreSQL `clients.address` |
| Nazionalità | PostgreSQL `clients.nationality` |
| Data di nascita | PostgreSQL `clients.date_of_birth` |
| Chat history | PostgreSQL, Redis (24h STM) |
| Passport number (senza foto) | PostgreSQL `clients.passport_number` |

→ Richiedono: base legale (contratto Art. 20(b) O consenso), privacy notice.

---

## 3. BASE LEGALE PER OGNI ATTIVITÀ

| Attività | Base legale | Art. UU PDP |
|----------|------------|-------------|
| Processing dati per servizio visa/company | **Contratto** (Art. 20(b)) | Necessario per adempiere obblighi contrattuali |
| Inquiry pre-contratto (WhatsApp/chat) | **Interesse legittimo** (Art. 20(f)) + consenso | Bilanciamento interessi |
| OCR passport/KTP (dato specifico) | **Consenso esplicito** (Art. 21) | Dato biometrico = specifico |
| Invio comunicazioni marketing | **Consenso** (Art. 21) | Opt-in esplicito |
| Condivisione dati con Gemini/OpenAI API | **Consenso** + safeguards cross-border | Art. 56 |
| Archiviazione post-servizio | **Obbligo legale** (Art. 20(c)) | Conservazione per audit/dispute |

---

## 4. PIANO DI IMPLEMENTAZIONE TECNICA

### Fase 1: IMMEDIATA (1-2 settimane) — Riduzione rischio

#### 1.1 Consent Banner su Portal (3-5 giorni)
```
File: apps/mouth/src/app/portal/(authenticated)/layout.tsx
Stack: CookieConsent.js + httpOnly cookie + PostgreSQL consent table
```

**Implementazione:**
- Banner al primo login con categorie: "Necessary" (sempre), "Data Processing" (PII per servizi), "Analytics"
- Consenso salvato in tabella `consent_records(client_id, category, granted_at, ip, user_agent)`
- FastAPI middleware verifica consenso prima di endpoint PII
- Revocabile in /portal/settings

#### 1.2 PII Scanner su Output LLM (1-2 giorni)
```
Stack: Microsoft Presidio + custom regex per formati indonesiani
File: backend/middleware/ (nuovo middleware)
```

**Implementazione:**
```python
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern

# Custom recognizer per formati indonesiani
ktp_recognizer = PatternRecognizer(
    supported_entity="ID_KTP",
    patterns=[Pattern("KTP", r"\b\d{16}\b", 0.7)]
)
npwp_recognizer = PatternRecognizer(
    supported_entity="ID_NPWP",
    patterns=[Pattern("NPWP", r"\b\d{2}\.\d{3}\.\d{3}\.\d{1}-\d{3}\.\d{3}\b", 0.9)]
)
phone_id_recognizer = PatternRecognizer(
    supported_entity="PHONE_ID",
    patterns=[Pattern("Phone_ID", r"\+62\d{8,12}", 0.8)]
)

analyzer = AnalyzerEngine()
analyzer.registry.add_recognizer(ktp_recognizer)
analyzer.registry.add_recognizer(npwp_recognizer)
analyzer.registry.add_recognizer(phone_id_recognizer)

# Middleware FastAPI
@app.middleware("http")
async def scan_pii_output(request, call_next):
    response = await call_next(request)
    if is_llm_endpoint(request):
        body = await read_response_body(response)
        pii_found = analyzer.analyze(text=body, language="en")
        if pii_found:
            body = anonymizer.anonymize(text=body, analyzer_results=pii_found)
            logger.warning(f"PII redacted from LLM response: {len(pii_found)} entities")
    return response
```

#### 1.3 Audit Logging Base (2-4 giorni)
```
File: backend/middleware/ (nuovo) + nuova migration
```

**Schema:**
```sql
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id TEXT,
    client_id INTEGER REFERENCES clients(id),
    action TEXT NOT NULL,  -- READ, WRITE, DELETE, EXPORT
    resource TEXT NOT NULL, -- 'passport', 'ktp', 'npwp', 'profile'
    ip_address INET,
    user_agent TEXT,
    details JSONB
);

-- Immutable: no UPDATE, no DELETE triggers
CREATE RULE no_update AS ON UPDATE TO audit_logs DO INSTEAD NOTHING;
CREATE RULE no_delete AS ON DELETE TO audit_logs DO INSTEAD NOTHING;

-- Partitioned by month per performance
CREATE INDEX idx_audit_client ON audit_logs (client_id, timestamp);
CREATE INDEX idx_audit_action ON audit_logs (action, timestamp);
```

#### 1.4 Privacy Policy Update (1 giorno)
- Aggiornare privacy policy su balizero.com con:
  - Categorie dati raccolti (Art. 21)
  - Base legale per ogni processing
  - Diritti del soggetto (accesso, rettifica, cancellazione, portabilità)
  - Periodo di retention
  - Contatti DPO
  - Transfer cross-border (Singapore)

### Fase 2: BREVE TERMINE (3-4 settimane) — Compliance strutturale

#### 2.1 Column-Level Encryption per PII (4-7 giorni)
```sql
-- PostgreSQL pgcrypto
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Nuove colonne encrypted
ALTER TABLE clients ADD COLUMN passport_number_enc BYTEA;
ALTER TABLE clients ADD COLUMN npwp_enc BYTEA;
ALTER TABLE clients ADD COLUMN ktp_number_enc BYTEA;

-- Migrazione dati
UPDATE clients SET
    passport_number_enc = pgp_sym_encrypt(passport_number, current_setting('app.encryption_key')),
    npwp_enc = pgp_sym_encrypt(npwp, current_setting('app.encryption_key'))
WHERE passport_number IS NOT NULL;

-- Decrypt on read
-- SELECT pgp_sym_decrypt(passport_number_enc, current_setting('app.encryption_key')) FROM clients;
```

**Key management**: `fly secrets set ENCRYPTION_KEY=...` → `os.getenv` nel backend.
**Performance**: 10-50% overhead su query encrypted — accettabile per PII fields.

#### 2.2 Right to Erasure Endpoint (4-6 giorni)
```
Endpoint: DELETE /api/portal/erasure
File: backend/app/routers/portal.py (nuovo endpoint)
```

**Pipeline di cancellazione:**
1. PostgreSQL: `DELETE FROM clients WHERE id = $1 CASCADE`
2. Qdrant: `client.delete(collection, filter={"must": [{"key": "client_id", "match": {"value": client_id}}]})`
3. Redis: `SCAN + DEL` pattern `*:{client_id}:*`
4. Google Drive: `files.list(q="name contains 'client_{id}'").batch_delete()`
5. Audit log: registra l'avvenuta cancellazione (l'unico record che RESTA)
6. Conferma al cliente entro 72h (Art. 32/40)

#### 2.3 Data Retention Automation (5 giorni)
```
Tabella: retention_policies(data_type, retention_days, action)
Job: Cron giornaliero via OpenClaw
```

| Tipo dato | Retention | Dopo |
|-----------|-----------|------|
| Passport scan | 5 anni post-expiry visa | Soft delete → hard delete 30gg |
| Chat history | 2 anni post-ultima interazione | Hard delete |
| Practice documents | 7 anni (obblighi fiscali) | Archive → cold storage |
| KTP/NPWP | Durata contratto + 5 anni | Encrypt → archive |
| Marketing data | Fino a revoca consenso | Immediate delete |

#### 2.4 Cross-Border Transfer Safeguards (3 giorni)
- Redigere Standard Contractual Clauses per Fly.io Singapore
- DPA (Data Processing Agreement) con:
  - Fly.io (hosting)
  - Google (Drive, Gemini API)
  - OpenAI (embedding API)
  - Upstash (Redis)
- Consent notice per cross-border al primo upload di documento PII

### Fase 3: MEDIO TERMINE (2-3 mesi) — Maturità

#### 3.1 PII Redaction su Qdrant Esistente (1-2 settimane)
Batch job per 93K documenti:
1. Scroll tutti i punti con payload text
2. Presidio scan per PII
3. Se trovato: redact payload text, update point (senza re-embedding)
4. Tag punto con `pii_redacted: true`

#### 3.2 Incident Response Plan (1 settimana)
- Runbook per breach:
  1. Detection: anomaly alert su `audit_logs` (rate PII reads > threshold)
  2. Containment: disable affected endpoints
  3. Notification: template per Lembaga PDP + soggetti (entro 72h)
  4. Post-incident: root cause analysis + fix
- Telegram alert per team
- Simulazione breach trimestrale

#### 3.3 DPIA per Processing Specifico (1 settimana)
Data Protection Impact Assessment obbligatorio per:
- OCR passport/KTP (biometria)
- RAG su documenti legali (decisioni automatizzate)
- Profilazione clienti (intent classification)

#### 3.4 DPO Evaluation
Con 5000+ clienti e processing di dati specifici (biometria):
- Probabilmente obbligatorio nominare DPO (Art. 54)
- Può essere interno o esterno
- Deve riportare direttamente alla direzione

---

## 5. COSTI E TIMELINE

| Fase | Azione | Effort | Costo |
|------|--------|--------|-------|
| **1.1** | Consent banner | 3-5 giorni | $0 |
| **1.2** | PII scanner Presidio | 1-2 giorni | $0 (open-source) |
| **1.3** | Audit logging | 2-4 giorni | $0 |
| **1.4** | Privacy policy update | 1 giorno | $0 |
| **2.1** | Column encryption | 4-7 giorni | $0 (pgcrypto) |
| **2.2** | Right to erasure | 4-6 giorni | $0 |
| **2.3** | Retention automation | 5 giorni | $0 |
| **2.4** | Cross-border safeguards | 3 giorni | ~$500 (legal review) |
| **3.1** | Qdrant PII redaction | 1-2 settimane | $0 |
| **3.2** | Incident response | 1 settimana | $0 |
| **3.3** | DPIA | 1 settimana | ~$1000 (consulente) |
| **3.4** | DPO evaluation | — | TBD |
| **TOTALE** | | ~8-10 settimane | ~$1,500 |

---

## 6. PII AUDIT COMPLETO (NLM NB-1, snapshot 2026-03-23)

### 6.1 Dove PII viene RACCOLTO

| Entry point | File | PII raccolto |
|-------------|------|-------------|
| CRM document upload | `routers/crm_enhanced.py` → `POST /api/crm/clients/{id}/documents` | Passport scan, KTP, NPWP, visa docs |
| Portal document upload | `services/portal/portal_service.py` → `POST /api/portal/documents/upload` | Stessi + VirusScanner pre-storage |
| WhatsApp webhook | `routers/whatsapp_chat.py` | Telefono (+62), nome, messaggio (può contenere PII) |
| Client Identity Resolver | `services/crm/client_identity_resolver.py` | Auto-collega phone + chat_id Telegram ad anagrafica |

### 6.2 Dove PII viene PROCESSATO (OCR)

| Servizio | File | Dati estratti | Provider |
|----------|------|-------------|----------|
| Auto OCR Passport | `routers/crm_enhanced.py` → `_auto_ocr_passport()` | Nome, numero, nazionalità, expiry | Ollama qwen2.5vl:7b → fallback Gemini Vision |
| Auto OCR NPWP | `routers/crm_enhanced.py` → `_auto_ocr_npwp()` | Numero NPWP, indirizzo, KPP | Idem |
| Auto OCR NIB | `routers/crm_enhanced.py` → `_auto_ocr_nib()` | NIB, company data | Idem |
| Portal OCR | `services/portal/portal_service.py` → `DocumentOCR` + `ExpiryDetector` | Testo + date scadenza | Idem |

**🔴 RISCHIO CRITICO**: Quando Ollama locale fallisce, **immagini passport/KTP vanno a Gemini API** (server Google) per OCR. Questo è un cross-border transfer di dati biometrici SENZA consenso esplicito.

### 6.3 Dove PII è SALVATO (PostgreSQL)

| Tabella | Colonne PII | Encryption |
|---------|------------|------------|
| `clients` | `full_name`, `email`, `phone`, `nationality`, `passport_number`, `passport_expiry`, `date_of_birth`, `address`, `gender` | **❌ NESSUNA — tutto in chiaro** |
| `companies` | `nib`, `npwp_company` | ❌ In chiaro |
| `client_family_members` | `passport_number`, contatti familiari | ❌ In chiaro |
| `documents` | `extracted_text` (TEXT, primi 10,000 chars OCR) | **❌ In chiaro — contiene PII estratto da OCR** |

### 6.4 Dove PII è INDICIZZATO (Qdrant)

| Collection | Rischio PII | Protezione |
|-----------|-------------|------------|
| `training_conversations_hybrid` (3,525 vettori) | **🔴 ALTO** — conversazioni con potenziale PII | Regex PII redaction pre-embedding |
| `episodic_memories`, `conversations` | **🟡 MEDIO** — contesto cliente | Regex redaction |
| Altre 8 collection (legal, KBLI, etc.) | BASSO — contenuto regolamentare | No PII by design |

**🔴 RISCHIO**: La PII redaction è **basata su Regex**. Se la regex fallisce (formato inatteso, typo, nuova lingua), PII finisce crudo nel payload vettoriale. **Impossibile da eliminare senza rimuovere il vettore intero.**

### 6.5 Dove PII viene TRASMESSO

| Canale | Cosa viene trasmesso | Destinazione |
|--------|---------------------|-------------|
| WhatsApp | Messaggi con PII potenziale | Meta Cloud API / Twilio |
| **Telegram** | `"Cliente: {display_name} (+{phone})"` + preview messaggio **IN CHIARO** | Telegram API → chat admin |
| Email | Link Google Drive diretti a documenti cliente | Zoho/Brevo → destinatario |
| **Gemini API** | **Immagini passport/KTP per OCR fallback** | Google Cloud (US) |
| Anthropic/OpenRouter | Testi conversazioni + query RAG | API provider (US) |

### 6.6 Dove PII è CACHATO (Redis)

| Pattern key | TTL | Contenuto |
|------------|-----|-----------|
| `client:{client_id}` | 300s (5 min) | Profilo completo con PII |
| `practice:{practice_id}` | 300s | Dettagli pratica |
| STM (Short-Term Memory) | 24h | Contesto conversazione recente |

### 6.7 Condivisione con TERZI

| Servizio terzo | PII condiviso | Necessita |
|---------------|---------------|-----------|
| **Google Drive** | Documenti in cartelle per cliente (00_Profile per KTP/Passport, 03_Tax per NPWP) | DPA + SCC |
| **Google Gemini API** | Immagini passport/KTP quando Ollama fallisce | **CONSENSO ESPLICITO + DPA** |
| **OpenAI API** | Testi per embedding (potenziale PII residuo) | DPA |
| **Anthropic/OpenRouter** | Conversazioni RAG | DPA |
| **Upstash Redis** | Cache con PII (5 min TTL) | DPA |
| **Meta/Twilio** | Messaggi WhatsApp | DPA + privacy policy |

### 6.8 Eliminabilità (Right to Erasure)

| Storage | Eliminabile? | Problema |
|---------|-------------|----------|
| PostgreSQL `clients` | ✅ Si (CASCADE) | — |
| Google Drive | ✅ Si (API delete folder) | — |
| Redis cache | ✅ Si (SCAN + DEL) | — |
| **`documents.extracted_text`** | ✅ Si (DELETE row) | OCR text con PII eliminabile |
| **`crm_audit_log` (WORM)** | **❌ NO** — Write Once, Read Many. `old_values`/`new_values` in JSONB | Se PII redaction regex fallisce, PII scolpito per sempre |
| **Qdrant vectors** | **❌ PARZIALE** — si può eliminare il punto, ma se PII è nel testo embeddato, il vettore semantico ne conserva traccia | Re-embedding necessario per eliminazione completa |
| **Episodic Memory** | **⚠️ Complesso** — serve trovare e eliminare tutti i fatti estratti per client_id | Query + delete selettivo |

### 6.9 DATA FLOW MAP (verificato da NLM)

```
CLIENT
  ↓ upload (portal/CRM) + messaggi (WhatsApp/Telegram/Web)
  ↓
[ENTRY POINTS]
  ├── crm_enhanced.py (team upload)
  ├── portal_service.py (client upload + VirusScanner)
  └── whatsapp_chat.py (webhook + identity resolver)
  ↓
[OCR PROCESSING]
  ├── qwen2.5vl:7b (locale, SICURO) ←── primario
  └── Gemini Vision API (CROSS-BORDER!) ←── fallback 🔴
  ↓
[STORAGE]
  ├── PostgreSQL clients/companies/documents ← IN CHIARO 🔴
  ├── Qdrant (training_conversations + episodic) ← regex redaction 🟡
  ├── Redis (CRM cache 5min, STM 24h) ← PII in cache 🟡
  └── Google Drive (cartelle per cliente) ← CROSS-BORDER 🟡
  ↓
[TRANSMISSION]
  ├── WhatsApp (Meta API) ← messaggi
  ├── Telegram (admin notification CON phone+nome IN CHIARO) 🔴
  ├── Email (link Drive diretti)
  ├── Gemini/OpenAI/Anthropic API ← query + context
  └── LLM Response → PII scanner middleware (DA IMPLEMENTARE)
  ↓
[AUDIT]
  └── crm_audit_log (WORM) ← PII potenziale se regex fallisce 🔴
```

**4 rischi critici identificati:**
1. 🔴 **PostgreSQL PII in chiaro** — nessuna encryption su passport_number, npwp, phone
2. 🔴 **Gemini OCR fallback** — immagini ID inviate a Google senza consenso esplicito
3. 🔴 **Telegram admin notification** — phone+nome in chiaro nel log
4. 🔴 **Audit log WORM** — PII potenzialmente non eliminabile se regex fallisce

---

## 7. PRIORITÀ DI ESECUZIONE

### QUESTA SETTIMANA:
1. ✅ Fix CI coverage (`--cov=backend/`) — 15 min
2. ✅ PII scanner Presidio su output LLM — 2 giorni
3. ✅ Audit logging base — 2 giorni
4. ✅ Privacy policy draft — 1 giorno

### PROSSIME 2 SETTIMANE:
5. Consent banner portal — 3-5 giorni
6. Right to erasure endpoint — 4-6 giorni
7. Column encryption PII — 4-7 giorni

### MESE 2:
8. Data retention automation — 5 giorni
9. Cross-border SCC — 3 giorni (+ legal review)
10. Qdrant PII batch redaction — 1-2 settimane
11. Incident response plan + simulazione — 1 settimana
12. DPIA — 1 settimana

---

---

## 8. CERTIFICAZIONI — PATH PIÙ ECONOMICO E CREDIBILE

### 🔴 PSE Registration — OBBLIGATORIA

| Dettaglio | Valore |
|-----------|--------|
| **Cos'è** | Penyelenggara Sistem Elektronik — registrazione Kominfo per sistemi elettronici |
| **Obbligatoria?** | **SÌ** — per qualsiasi piattaforma che processa dati ID indonesiani, anche se hosted all'estero |
| **Costo** | Gratuita (Kominfo). Con consulente locale: $300-$1,000 |
| **Processo** | OSS-RBA portal → NIB/NPWP/profilo sistema + security policy → submit → verifica |
| **Timeline** | 5-14 giorni lavorativi |
| **Se non registrati** | Blocco sito, multe, sospensione da Kominfo |
| **Azione** | **FARE SUBITO** — è il prerequisito base |

### Path completo: ~$500-$1,500, 1-2 mesi

| Step | Settimana | Azione | Costo | Credibilità |
|------|-----------|--------|-------|-------------|
| **1** | 1 | **PSE Registration** (Kominfo) | $0-$500 | 🟢 Obbligatoria Indonesia |
| **2** | 1-2 | **Self-assess UU PDP** + pubblica compliance report | $0 | 🟡 Marketing + audit aid |
| **3** | 2-4 | **Cyber Essentials** self-assessment (UK gov-backed) | ~$400 | 🟢 Internazionale |
| **4** | Ongoing | **Referenzia certificazioni provider**: Fly.io SOC 2 Type II, OpenAI ISO 27001/27701, Upstash SOC 2, Google ISO 27001 | $0 | 🟢 Ereditata |
| **TOTALE** | | | **~$500-$1,500** | |

### Certificazioni provider che EREDITIAMO (gratis)

| Provider | Certificazione | Noi ereditiamo |
|----------|---------------|----------------|
| **Fly.io** | SOC 2 Type II + ISO 27001 datacenter (Singapore) | ✅ "Hosted on SOC 2 Type II certified infrastructure" |
| **OpenAI** | ISO 27001, 27017, 27018, 27701 + SOC 2 | ✅ "Embeddings processed by ISO 27701 certified provider" |
| **Google** (Drive, Gemini) | ISO 27001 + SOC 2 | ✅ "Documents stored on ISO 27001 certified platform" |
| **Upstash** | SOC 2 Type II (Pro+ plans) | ✅ "Cache on SOC 2 certified Redis" |

### Cosa NON serve (e perché)

| Certificazione | Costo | Perché skip |
|---------------|-------|-------------|
| **ISO 27001 proprio** | $10K-$30K + 6-12 mesi | Troppo costoso. Referenzia Fly.io datacenter cert. |
| **SOC 2 Type II proprio** | $12K-$50K + 12 mesi | Solo se grandi enterprise lo richiedono come vendor |
| **IASME Governance** | ~$2K | UK-specific, no valore in Indonesia |
| **TrustArc** | $10K+ | Enterprise, overkill |

### UU PDP Self-Assessment Report — Template

Pubblica un documento "Bali Zero Data Protection Compliance Report" con:

1. **Introduzione**: chi siamo, cosa processiamo, base legale
2. **Data Inventory**: mappa dei flussi dati (§6 sopra)
3. **Controlli tecnici**: encryption, audit logging, access control, PII scanning
4. **Controlli organizzativi**: privacy policy, consent management, retention policy
5. **Breach response plan**: 72h notification, team responsabile, template
6. **DPO**: nominato o in valutazione
7. **Cross-border**: safeguards, DPA con provider, SCC
8. **Diritti soggetti**: erasure, portability, access, rectification — come li garantiamo
9. **Certificazioni provider**: Fly.io SOC 2, OpenAI ISO, etc.

**Peso legale**: non è difesa contro multe, ma dimostra buona fede + facilita audit + credibilità marketing.

---

## 9. PRIORITÀ ASSOLUTA — COSA FARE PRIMA DI TUTTO

### Questa settimana (30 min - 2 giorni ciascuno):

| # | Azione | Effort | Perché URGENTE |
|---|--------|--------|---------------|
| 1 | **PSE Registration** su OSS-RBA | 1 giorno + 5-14gg attesa | OBBLIGATORIA, rischio blocco sito |
| 2 | **Fix Telegram notification** — rimuovere phone dal log admin | 30 min | PII in chiaro su canale non-encrypted |
| 3 | **Presidio PII scanner** su output LLM | 2 giorni | PII leak nelle risposte AI |
| 4 | **Audit logging table** | 2 giorni | Base per compliance + breach detection |
| 5 | **Consent banner** su portal upload | 3 giorni | Consenso esplicito per dati biometrici (passport scan) |
| 6 | **Fix Gemini OCR fallback** — aggiungere consent check prima di inviare a Gemini | 1 giorno | Cross-border biometria senza consenso |

---

*PDP Compliance Plan v2.0 COMPLETE — 29 marzo 2026*
*Fonti: UU PDP No. 27/2022 (testo ABNR), xAI legal research (Art. specifici),*
*xAI technical research (Presidio, pgcrypto, audit patterns),*
*NLM NB-1 PII audit codebase (in arrivo)*
*Costo totale stimato: ~$1,500 + 8-10 settimane dev*
