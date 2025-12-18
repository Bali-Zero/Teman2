# Sentry Auto-Fix Command

Analizza gli errori Sentry e proponi/applica fix automatici.

## Istruzioni

1. **Recupera errori recenti da Sentry** usando l'API:
   - Org: `bali-zero-7p`
   - Projects: `nuzantara-backend`, `nuzantara-frontend`
   - Filtra: `is:unresolved` (solo errori non risolti)

2. **Per ogni errore**:
   - Analizza lo stack trace
   - Identifica il file e la linea esatta
   - Leggi il codice sorgente corrispondente
   - Proponi una fix

3. **Applica la fix**:
   - Modifica il file locale
   - Crea un commit con messaggio: `fix(sentry): [ISSUE-ID] descrizione`
   - NON pushare automaticamente (lascia decidere all'utente)

4. **Crea GitHub Issue** (opzionale):
   - Se la fix è complessa, crea un issue GitHub con dettagli

## API Sentry

```bash
# Lista issues non risolti
curl -s "https://us.sentry.io/api/0/projects/bali-zero-7p/nuzantara-backend/issues/?query=is:unresolved" \
  -H "Authorization: Bearer $SENTRY_AUTH_TOKEN"

# Dettaglio issue
curl -s "https://us.sentry.io/api/0/issues/{issue_id}/events/latest/" \
  -H "Authorization: Bearer $SENTRY_AUTH_TOKEN"
```

## Output atteso

Per ogni errore trovato:
```
## Errore: [titolo]
- **ID**: ISSUE-123
- **File**: backend/app/routers/auth.py:42
- **Tipo**: TypeError
- **Occorrenze**: 15
- **Ultimo**: 2 ore fa

### Stack Trace
[stack trace rilevante]

### Fix Proposta
[descrizione della fix]

### Azione
- [ ] Applicare fix
- [ ] Creare GitHub Issue
- [ ] Ignorare
```
