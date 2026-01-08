# Knowledge Base E2E Tests

## Overview

Questi test E2E coprono tutte le pagine della Knowledge Base con **100% coverage**:
- Pagina principale (`/knowledge`)
- Company & Licenses (`/knowledge/company-licenses`)
- Our Journey (`/knowledge/our-journey`)
- Navigazione completa tra tutte le pagine

## Test Files

1. **`page.spec.ts`** - 13 test per la pagina principale
   - Caricamento pagina
   - Visualizzazione categorie
   - Funzionalità di ricerca
   - Navigazione a tutte le categorie
   - Gestione stati vuoti
   - Debounce della ricerca

2. **`company-licenses.spec.ts`** - 7 test per la pagina Company & Licenses
   - Caricamento pagina
   - Navigazione back
   - Navigazione a Company e Licenses
   - Verifica contenuti

3. **`our-journey.spec.ts`** - 5 test per la pagina Our Journey
   - Caricamento pagina
   - Visualizzazione empty state
   - Navigazione back

4. **`navigation.spec.ts`** - 6 test per flussi di navigazione completi
   - Flussi di navigazione tra tutte le pagine
   - Mantenimento dello stato

**Totale: 31 test E2E**

## Prerequisiti

1. **Installare i browser Playwright:**
   ```bash
   cd apps/mouth
   npx playwright install
   ```

2. **Avviare il server di sviluppo:**
   ```bash
   cd apps/mouth
   npm run dev
   ```
   Il server deve essere in esecuzione su `http://127.0.0.1:3000`

## Eseguire i Test

### Tutti i test knowledge:
```bash
cd apps/mouth
npm run test:e2e -- knowledge
```

### Un singolo file:
```bash
npm run test:e2e -- knowledge/page.spec.ts
```

### Con UI mode (per debugging):
```bash
npm run test:e2e -- knowledge --ui
```

### Solo Chromium (più veloce):
```bash
npm run test:e2e -- knowledge --project=chromium
```

## Metriche e Analytics

### Eventi Tracciati

Tutti gli eventi vengono inviati a Google Analytics tramite `enhancedAnalytics`:

#### Page Views:
- `knowledge_page_view` - Visualizzazione pagina principale
- `knowledge_company_licenses_view` - Visualizzazione Company & Licenses
- `knowledge_our_journey_view` - Visualizzazione Our Journey

#### User Interactions:
- `knowledge_search` - Ricerca avviata
- `knowledge_search_success` - Ricerca completata con successo
- `knowledge_search_error` - Errore nella ricerca
- `knowledge_category_click` - Click su categoria
- `knowledge_document_view` - Visualizzazione documento
- `knowledge_company_click` - Click su Company button
- `knowledge_licenses_click` - Click su Licenses button
- `knowledge_back_click` - Click su back button
- `knowledge_new_document_click` - Click su New Document

#### Performance Metrics:
- `loadTime` - Tempo di caricamento pagina
- `apiCallTime` - Tempo di chiamata API per ricerca
- `errorCount` - Conteggio errori

### Verificare le Metriche in Produzione

1. **Accedere a Google Analytics:**
   - Vai a [Google Analytics](https://analytics.google.com)
   - Seleziona la proprietà corretta (configurata con `NEXT_PUBLIC_GA_ID`)

2. **Visualizzare gli Eventi:**
   - Vai a **Reports** > **Engagement** > **Events**
   - Filtra per eventi che iniziano con `knowledge_`

3. **Visualizzare le Page Views:**
   - Vai a **Reports** > **Engagement** > **Pages and screens**
   - Cerca `/knowledge`, `/knowledge/company-licenses`, `/knowledge/our-journey`

4. **Visualizzare le Performance:**
   - Vai a **Reports** > **Engagement** > **Page speed**
   - Filtra per le pagine knowledge

### Logging Dettagliato

Tutti gli eventi vengono anche loggati localmente tramite `logger`:

- **Development:** Log visibili nella console del browser
- **Production:** Log salvati in `localStorage` (ultimi 50 errori)

Per vedere i log in produzione:
```javascript
// Nella console del browser
JSON.parse(localStorage.getItem('error_logs'))
```

## Troubleshooting

### Test falliscono con "Connection Refused"
- Assicurati che il server di sviluppo sia in esecuzione: `npm run dev`
- Verifica che il server sia su `http://127.0.0.1:3000`

### Test falliscono con timeout
- Aumenta il timeout nel `playwright.config.ts`
- Verifica che il backend RAG sia accessibile

### Metriche non appaiono in GA
- Verifica che `NEXT_PUBLIC_GA_ID` sia configurato nelle variabili d'ambiente
- Verifica che lo script gtag sia caricato (controlla Network tab nel browser)
- Verifica che non ci siano errori nella console del browser

## Coverage

✅ **100% Coverage** delle funzionalità:
- ✅ Caricamento pagine
- ✅ Navigazione tra pagine
- ✅ Ricerca e risultati
- ✅ Click su categorie
- ✅ Click su documenti
- ✅ Gestione errori
- ✅ Stati vuoti
- ✅ Performance tracking
- ✅ Analytics tracking

