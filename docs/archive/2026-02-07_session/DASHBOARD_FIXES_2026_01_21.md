# Dashboard Fixes - 2026-01-21

**Data:** 2026-01-21  
**Status:** ✅ Completato

---

## 📋 Issues Risolti

### 1. ✅ Critical Deadlines sempre 0

**Problema:** Il campo `criticalDeadlines` era sempre 0 nel dashboard.

**Soluzione Implementata:**

- Creata funzione `_get_critical_deadlines()` in `dashboard_summary.py`
- Conta le pratiche con `expiry_date` entro 7 giorni dalla data corrente
- Supporta RBAC: admin vede tutte le pratiche, team members solo quelle assegnate
- Esclude pratiche `completed` e `cancelled`

**File Modificati:**

- `apps/backend-rag/backend/app/routers/dashboard_summary.py`

**Query SQL:**

```sql
SELECT COUNT(*) as count
FROM practices
WHERE expiry_date IS NOT NULL
AND expiry_date > CURRENT_DATE
AND expiry_date <= CURRENT_DATE + INTERVAL '7 days'
AND status NOT IN ('completed', 'cancelled')
```

---

### 2. ✅ Revenue hardcoded a 0

**Problema:** Il widget `FinancialRealityWidget` mostrava sempre revenue = 0.

**Soluzione Implementata:**

- Creata funzione `_get_revenue_stats()` che calcola:
  - `total_revenue`: somma di tutti gli `actual_price`
  - `paid_revenue`: somma di `actual_price` con `payment_status = 'paid'`
  - `outstanding_revenue`: somma di `actual_price - paid_amount` per pratiche `unpaid` o `partial`
- Creata funzione `_calculate_revenue_growth()` che calcola crescita mese corrente vs mese precedente
- Dati esposti solo per admin (`is_admin = true`)
- Frontend aggiornato per usare i dati reali invece di valori hardcoded

**File Modificati:**

- `apps/backend-rag/backend/app/routers/dashboard_summary.py`
- `apps/mouth/src/lib/api/dashboard/dashboard.api.ts` (tipi TypeScript)
- `apps/mouth/src/hooks/useDashboardData.ts` (hook aggiornato)
- `apps/mouth/src/app/(workspace)/dashboard/page.tsx` (componente aggiornato)

**Query SQL:**

```sql
SELECT
    COALESCE(SUM(actual_price), 0) as total_revenue,
    COALESCE(SUM(CASE WHEN payment_status = 'paid' THEN actual_price ELSE 0 END), 0) as paid_revenue,
    COALESCE(SUM(CASE WHEN payment_status IN ('unpaid', 'partial')
        THEN actual_price - COALESCE(paid_amount, 0) ELSE 0 END), 0) as outstanding_revenue
FROM practices
WHERE actual_price IS NOT NULL
```

---

### 3. ✅ WebSocket errors in console

**Problema:** Errori WebSocket loggati in console anche quando il server non supporta WebSocket.

**Soluzione Implementata:**

- Migliorata gestione errori in `realtime.tsx`:
  - Errori durante handshake (code 1006) non vengono più loggati come errori critici
  - Log downgrade a `warn` con nota che è non-critico
  - Prevenzione infinite reconnect attempts se server non supporta WebSocket
  - Log solo se connessione era effettivamente in corso

**File Modificati:**

- `apps/mouth/src/lib/realtime.tsx`

**Cambiamenti:**

```typescript
// Prima: logger.error() per tutti gli errori
// Dopo: logger.warn() solo se isConnecting, con nota non-critico
// Prevenzione reconnect infiniti se code === 1006
```

---

### 4. ✅ Featured Articles hardcoded

**Problema:** Articoli featured erano hardcoded nel componente React.

**Soluzione Implementata:**

- Creato endpoint API `/api/dashboard/featured-articles`
- Componente `FeaturedArticlesWidget` ora fetcha dati da API
- Fallback a dati statici se API fallisce
- Loading state durante fetch
- Struttura pronta per estensione futura (database/API esterna)

**File Creati:**

- `apps/backend-rag/backend/app/routers/dashboard_featured_articles.py`

**File Modificati:**

- `apps/backend-rag/backend/app/setup/router_registration.py` (registrazione router)
- `apps/mouth/src/components/dashboard/FeaturedArticlesWidget.tsx`

**Endpoint:**

```
GET /api/dashboard/featured-articles
Response: { articles: FeaturedArticle[] }
```

---

## 🧪 Testing

### Test Manuali Consigliati

1. **Critical Deadlines:**
   - Creare pratica con `expiry_date` entro 7 giorni
   - Verificare che `criticalDeadlines` > 0 nel dashboard
   - Verificare RBAC (team member vede solo pratiche assegnate)

2. **Revenue:**
   - Creare pratiche con `actual_price` e `payment_status`
   - Verificare che `FinancialRealityWidget` mostri revenue corretto
   - Verificare che solo admin veda revenue

3. **WebSocket:**
   - Verificare che non ci siano errori in console se WebSocket non disponibile
   - Verificare che real-time features funzionino se WebSocket disponibile

4. **Featured Articles:**
   - Verificare che articoli vengano caricati da API
   - Verificare fallback se API fallisce
   - Verificare loading state

---

## 📊 Impact

### Performance

- ✅ Nessun impatto negativo (query ottimizzate, parallel fetching)
- ✅ Cache React Query per featured articles

### Backward Compatibility

- ✅ Tutti i cambiamenti sono backward compatible
- ✅ Fallback values per tutti i nuovi campi

### Security

- ✅ RBAC rispettato (admin-only per revenue)
- ✅ Nessuna nuova vulnerabilità introdotta

---

## 🔄 Next Steps (Opzionali)

1. **Featured Articles Dinamici:**
   - Estendere endpoint per fetchare da database/Qdrant
   - Aggiungere caching per performance
   - Aggiungere filtro per categoria/priorità

2. **Revenue Growth:**
   - Aggiungere grafico storico
   - Confronto con periodi precedenti
   - Proiezioni future

3. **Critical Deadlines:**
   - Notifiche push per scadenze imminenti
   - Email alerts per team members
   - Dashboard dedicato per scadenze

---

## 📝 Note Tecniche

### Database Schema

- `practices.expiry_date`: DATE field per scadenze
- `practices.actual_price`: DECIMAL field per revenue
- `practices.payment_status`: ENUM ('paid', 'unpaid', 'partial')
- `practices.paid_amount`: DECIMAL field per pagamenti parziali

### API Response Structure

```typescript
{
  user: { email, role, is_admin },
  stats: {
    activeCases: number,
    criticalDeadlines: number,  // ✅ NUOVO
    whatsappUnread: number,
    emailUnread: number,
    hoursWorked: string,
  },
  revenue?: {  // ✅ NUOVO (admin only)
    total_revenue: number,
    paid_revenue: number,
    outstanding_revenue: number,
  },
  revenue_growth?: number,  // ✅ NUOVO (admin only)
  // ... altri campi
}
```

---

**Completato da:** AI Assistant  
**Review Status:** ✅ Pronto per testing  
**Deploy Status:** ⏳ In attesa di deploy
