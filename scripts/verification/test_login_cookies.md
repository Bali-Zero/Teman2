# Test Login e Cookie - Istruzioni

## Scopo

Verificare che il login funzioni correttamente e che i cookie di autenticazione siano impostati correttamente.

## Procedura

### 1. Test Login

1. Apri `https://zantara.balizero.com/login` nel browser
2. Inserisci credenziali:
   - Email: `zero@balizero.com` (o altro utente valido)
   - PIN: `010719` (o PIN corretto)
3. Clicca "Authenticate"

### 2. Verifica Cookie (DevTools)

1. Apri DevTools (F12)
2. Vai su **Application** → **Cookies** → `https://zantara.balizero.com`
3. Verifica presenza di:

   **Cookie Richiesti:**
   - ✅ `nz_access_token`
     - **Valore**: JWT token (lungo, inizia con `eyJ...`)
     - **Domain**: `.balizero.com` o `zantara.balizero.com`
     - **Path**: `/`
     - **HttpOnly**: ✅ (dovrebbe essere true)
     - **Secure**: ✅ (dovrebbe essere true per HTTPS)
     - **SameSite**: `Lax` o `Strict`

   - ✅ `nz_csrf_token`
     - **Valore**: Token CSRF (stringa alfanumerica)
     - **Domain**: `.balizero.com` o `zantara.balizero.com`
     - **Path**: `/`
     - **HttpOnly**: ✅ (dovrebbe essere true)
     - **Secure**: ✅ (dovrebbe essere true per HTTPS)
     - **SameSite**: `Lax` o `Strict`

### 3. Test API con Cookie

Dopo il login, esegui nella Console del browser (F12 → Console):

```javascript
// Verifica cookie sono presenti
console.log('Cookies:', document.cookie);

// Test API call con cookie
fetch('/api/crm/clients', { 
  credentials: 'include',
  headers: {
    'Content-Type': 'application/json'
  }
})
  .then(r => {
    console.log('Status:', r.status);
    return r.json();
  })
  .then(d => {
    console.log('✅ API Response:', d);
  })
  .catch(e => {
    console.error('❌ API Error:', e);
  });
```

**Output Atteso:**

- ✅ **Status 200**: Cookie funzionano, API raggiungibile
- ❌ **Status 401**: Cookie mancanti o scaduti → Problema autenticazione
- ❌ **Status 403**: Cookie presenti ma permessi insufficienti
- ❌ **CORS Error**: Problema CORS backend
- ❌ **Network Error**: Backend non raggiungibile o proxy non funziona

### 4. Verifica Redirect Dopo Login

Dopo login riuscito, dovresti essere reindirizzato a:
- `/dashboard` (se admin/team member)
- `/portal` (se client)

Se il redirect non avviene o va in loop, c'è un problema con la logica di routing.

## Problemi Comuni

### Cookie Non Impostati

**Sintomi:**
- Login sembra funzionare ma cookie non appaiono in DevTools
- Redirect avviene ma poi errore "Failed to load client data"

**Possibili Cause:**
1. Backend non imposta cookie correttamente (`/api/auth/login`)
2. Cookie sono `HttpOnly` ma dominio non corrisponde
3. Browser blocca cookie di terze parti
4. HTTPS non configurato correttamente

**Soluzione:**
- Verifica backend `/api/auth/login` response headers
- Controlla che `Set-Cookie` header sia presente
- Verifica dominio cookie corrisponde al dominio frontend

### Cookie Presenti ma API Fallisce

**Sintomi:**
- Cookie visibili in DevTools
- API calls restituiscono 401/403

**Possibili Cause:**
1. Cookie scaduti (check `Expires` o `Max-Age`)
2. Cookie non forwardati correttamente dal proxy
3. Backend non legge cookie correttamente
4. CORS non permette cookie

**Soluzione:**
- Verifica proxy forward cookie (`apps/mouth/src/app/api/[...path]/route.ts`)
- Controlla backend middleware auth legge cookie
- Verifica CORS `Access-Control-Allow-Credentials: true`

### Redirect Loop

**Sintomi:**
- Login → Redirect → Login → Redirect...

**Possibili Cause:**
1. Cookie non persistono tra redirect
2. Middleware auth non riconosce cookie
3. Redirect logic errata

**Soluzione:**
- Verifica cookie `Path` e `Domain` sono corretti
- Controlla middleware non forza redirect se già autenticato

## Checklist

- [ ] Login funziona (nessun errore visibile)
- [ ] Cookie `nz_access_token` è presente dopo login
- [ ] Cookie `nz_csrf_token` è presente dopo login
- [ ] Cookie hanno `Secure` flag (HTTPS)
- [ ] Cookie hanno `HttpOnly` flag
- [ ] Cookie hanno `SameSite` appropriato
- [ ] Redirect dopo login funziona
- [ ] API call con cookie restituisce 200 (non 401)
- [ ] Nessun errore CORS nella console

## Comandi Utili

### Verifica Cookie da Terminale

```bash
# Test login endpoint
curl -X POST https://zantara.balizero.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"zero@balizero.com","pin":"010719"}' \
  -v \
  -c cookies.txt

# Verifica cookie salvati
cat cookies.txt
```

### Test API con Cookie

```bash
# Usa cookie salvati per chiamare API
curl https://zantara.balizero.com/api/crm/clients \
  -b cookies.txt \
  -v
```

## Prossimi Passi

Se tutti i test passano:
- ✅ Autenticazione funziona correttamente
- ✅ Il problema è probabilmente nella configurazione Vercel o CORS
- ✅ Procedi con verifica CORS backend

Se i test falliscono:
- ❌ Problema nell'autenticazione backend
- ❌ Verifica `/api/auth/login` endpoint
- ❌ Controlla backend middleware auth
