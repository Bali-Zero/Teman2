# Blueprint PDF Tracking - Guida Operativa

## 📊 Overview

Sistema di tracking per identificare quali blueprint hanno richieste di download ma non hanno PDF disponibili, permettendo di prioritizzare la creazione dei PDF più richiesti.

## 🎯 Eventi Tracciati

### 1. Download Riuscito
**Evento**: `blueprint_download_success`

**Parametri**:
- `blueprintId`: ID del blueprint (es. `kbli-55110`)
- `blueprintTitle`: Titolo del blueprint (es. `Star Hotel`)
- `blueprintCode`: Codice KBLI (es. `55110`)
- `filename`: Nome del file PDF scaricato
- `version`: Versione richiesta (`EN-Teknis`, `EN-Bisnis`, `ID-Teknis`, `ID-Bisnis`)

### 2. Download Mancante (PDF non disponibile)
**Evento**: `blueprint_download_missing_pdf` ⚠️ **PRIORITÀ**

**Parametri**:
- `blueprintId`: ID del blueprint
- `blueprintTitle`: Titolo del blueprint
- `blueprintCode`: Codice KBLI
- `category`: Categoria (Hospitality, Real Estate, etc.)
- `riskLevel`: Livello di rischio (Low, Medium, High)
- `requestedVersion`: Versione richiesta
- `hasIndonesian`: Se ha versione indonesiana
- `hasBisnis`: Se ha versione business
- `timestamp`: Data/ora della richiesta

## 📈 Come Visualizzare i Dati in Google Analytics

### Metodo 1: Google Analytics 4 Dashboard

1. **Accedi a Google Analytics**
   - Vai a: https://analytics.google.com
   - Seleziona la proprietà Nuzantara

2. **Vai a Reports > Events**
   - Cerca l'evento `blueprint_download_missing_pdf`
   - Clicca per vedere i dettagli

3. **Filtra per Parametri**
   - Usa i parametri personalizzati per vedere:
     - Quali blueprint sono più richiesti
     - Quali categorie hanno più richieste
     - Quali versioni (EN/ID, Teknis/Bisnis) sono più richieste

### Metodo 2: Custom Report

Crea un report personalizzato con:

**Dimensioni**:
- `blueprint_id` (Event parameter)
- `blueprint_code` (Event parameter)
- `category` (Event parameter)
- `requested_version` (Event parameter)

**Metriche**:
- Event count (numero di richieste)
- Unique users (utenti che hanno richiesto)

### Metodo 3: Query Explorer (GA4 Data API)

```sql
SELECT 
  event_params.value.string_value as blueprint_id,
  COUNT(*) as request_count
FROM 
  `your-project.analytics_XXXXXX.events_*`
WHERE 
  event_name = 'blueprint_download_missing_pdf'
  AND _TABLE_SUFFIX BETWEEN '20260101' AND '20260131'
GROUP BY 
  blueprint_id
ORDER BY 
  request_count DESC
LIMIT 20
```

## 🎯 Priorizzazione PDF

### Criteri di Priorità

1. **Frequenza Richieste** (peso: 40%)
   - Blueprint con più richieste = priorità alta

2. **Categoria** (peso: 20%)
   - Hospitality e Real Estate = priorità alta
   - Technology e Services = priorità media

3. **Risk Level** (peso: 20%)
   - High risk = priorità alta (più complessi, più richiesti)

4. **Versione Richiesta** (peso: 20%)
   - Se molte richieste per versione specifica (es. ID-Bisnis), priorità quella versione

### Formula Priorità

```
Priority Score = (request_count * 0.4) + 
                 (category_weight * 0.2) + 
                 (risk_level_weight * 0.2) + 
                 (version_demand * 0.2)
```

## 📋 Report Mensile

### Checklist

- [ ] Estrarre dati GA4 per il mese precedente
- [ ] Identificare top 10 blueprint senza PDF più richiesti
- [ ] Analizzare pattern (categoria, versione, risk level)
- [ ] Creare lista prioritaria per produzione PDF
- [ ] Assegnare risorse per creazione PDF
- [ ] Tracciare progresso creazione

### Template Report

```markdown
# Blueprint PDF Priority Report - [Mese/Anno]

## Top 10 Blueprint Richiesti (senza PDF)

| Rank | Blueprint ID | Codice KBLI | Titolo | Richieste | Categoria | Priorità |
|------|--------------|-------------|--------|-----------|-----------|----------|
| 1    | kbli-55110   | 55110       | Star Hotel | 45 | Hospitality | Alta |
| 2    | ...         | ...         | ...    | ... | ... | ... |

## Analisi Pattern

- **Categoria più richiesta**: Hospitality (60% delle richieste)
- **Versione più richiesta**: EN-Teknis (70% delle richieste)
- **Risk Level più richiesto**: Medium (50% delle richieste)

## Azioni Raccomandate

1. Creare PDF per top 5 blueprint entro [data]
2. Prioritizzare versione EN-Teknis per tutti
3. Considerare versione ID per blueprint Hospitality
```

## 🔍 Query Utili

### Top Blueprint Richiesti (Ultimi 30 giorni)

```javascript
// In GA4 Query Explorer
SELECT 
  (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'blueprint_id') as blueprint_id,
  (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'blueprint_title') as blueprint_title,
  (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'blueprint_code') as blueprint_code,
  COUNT(*) as request_count
FROM 
  `your-project.analytics_XXXXXX.events_*`
WHERE 
  event_name = 'blueprint_download_missing_pdf'
  AND _TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY))
                        AND FORMAT_DATE('%Y%m%d', CURRENT_DATE())
GROUP BY 
  blueprint_id, blueprint_title, blueprint_code
ORDER BY 
  request_count DESC
LIMIT 20
```

### Richieste per Categoria

```javascript
SELECT 
  (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'category') as category,
  COUNT(*) as request_count,
  COUNT(DISTINCT user_pseudo_id) as unique_users
FROM 
  `your-project.analytics_XXXXXX.events_*`
WHERE 
  event_name = 'blueprint_download_missing_pdf'
  AND _TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY))
                        AND FORMAT_DATE('%Y%m%d', CURRENT_DATE())
GROUP BY 
  category
ORDER BY 
  request_count DESC
```

## 🚀 Automazione (Futuro)

### Possibili Miglioramenti

1. **Dashboard Interna**
   - Creare pagina admin per vedere richieste in tempo reale
   - Grafici e tabelle interattive

2. **Alert Automatici**
   - Notifica quando un blueprint supera X richieste
   - Email settimanale con top 10

3. **Integrazione con Backend**
   - API endpoint per query dati
   - Sincronizzazione con sistema di produzione PDF

## 📝 Note Tecniche

- **Eventi inviati a**: Google Analytics 4
- **Frequenza tracking**: Ogni click su download senza PDF
- **Retention dati**: Secondo policy GA4 (default 14 mesi)
- **Privacy**: Nessun dato personale tracciato, solo blueprint ID e metadata

---

**Ultimo aggiornamento**: 2026-01-06  
**Versione**: 1.0.0

