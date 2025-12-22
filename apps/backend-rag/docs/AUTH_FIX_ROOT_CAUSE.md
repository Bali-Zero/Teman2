# Authentication Fix - Root Cause Analysis

## Problema Identificato

**Root Cause**: Token JWT scaduto (`Signature has expired`)

I log del backend mostrano chiaramente:
```
JWT validation failed: Signature has expired.
Invalid Header JWT from 172.16.51.74
Authentication failed for: /api/team/my-status from 172.16.51.74
```

## Analisi

### Status dei Fix Implementati

Tutti i fix implementati funzionano correttamente:
- ✅ **Dynamic Token Reading**: Il token viene letto correttamente da `localStorage`
- ✅ **Cookie Forwarding**: I cookie vengono inoltrati correttamente dal proxy
- ✅ **Authorization Header**: L'header `Authorization: Bearer <token>` viene incluso nelle richieste

### Il Problema Reale

Il token JWT presente in `localStorage` è **scaduto**. Questo è normale e previsto:
- I token JWT hanno una durata limitata per motivi di sicurezza
- Quando un token scade, il backend rifiuta le richieste con 401
- L'applicazione dovrebbe reindirizzare automaticamente l'utente al login

### Comportamento Atteso

Quando il token scade:
1. ✅ Il backend rifiuta la richiesta con 401
2. ✅ `ApiClientBase` rileva il 401
3. ✅ Il token viene rimosso da `localStorage`
4. ✅ L'utente viene reindirizzato a `/login?expired=true`

## Miglioramenti Implementati

### Gestione Migliorata del Token Scaduto

**File**: `apps/mouth/src/lib/api/client.ts`

**Modifiche**:
- Uso di `window.location.replace()` invece di `window.location.href` per evitare di aggiungere alla cronologia
- Aggiunta del parametro `reason=token_expired` per identificare chiaramente la causa
- Logging migliorato per tracciare i redirect

**Codice**:
```typescript
if (response.status === 401) {
  this.clearToken();
  
  if (typeof window !== 'undefined') {
    const currentPath = window.location.pathname;
    if (currentPath !== '/login' && !currentPath.startsWith('/api/')) {
      console.log('[ApiClient] Token expired or invalid, redirecting to login');
      window.location.replace('/login?expired=true&reason=token_expired');
    }
  }
  
  const error = await response.json().catch(() => ({ detail: 'Authentication required' }));
  throw new Error(error.detail || 'Session expired. Please login again.');
}
```

## Conclusione

**I fix implementati funzionano correttamente**. Il problema era semplicemente che il token era scaduto, il che è un comportamento normale e previsto del sistema di autenticazione.

### Prossimi Passi per l'Utente

1. Fare login di nuovo su `zantara.balizero.com/login`
2. Il nuovo token verrà salvato in `localStorage`
3. Le richieste API funzioneranno correttamente con il nuovo token

### Miglioramenti Futuri (Opzionali)

1. **Token Refresh Automatico**: Implementare un meccanismo di refresh token per evitare che l'utente debba fare login manualmente quando il token scade
2. **Notifica Proattiva**: Avvisare l'utente quando il token sta per scadere (es. 5 minuti prima)
3. **Session Persistence**: Salvare le preferenze dell'utente per ripristinarle dopo il login

