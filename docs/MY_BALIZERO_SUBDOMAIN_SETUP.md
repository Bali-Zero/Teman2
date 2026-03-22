# Setup Subdomain: my.balizero.com

**Purpose:** Portal clienti dedicato per le pagine `/portal/*`  
**Date:** 2025-01-29  
**Status:** ⏳ Da configurare

---

## 🎯 Obiettivo

Creare il sottodominio `my.balizero.com` dedicato esclusivamente al **Portal Clienti** con le pagine:

- `/portal/vault` - Documenti
- `/portal/profile` - Profilo utente
- `/portal/settings` - Impostazioni
- `/portal/visa` - Status visto
- `/portal/taxes` - Tasse e scadenze
- `/portal/chat` - Messaggi
- `/portal/companies` - Aziende

---

## 📋 Configurazione Richiesta

### 1. DNS Configuration (Cloudflare)

Aggiungere record CNAME per `my.balizero.com`:

```bash
# Record DNS da aggiungere su Cloudflare
Type: CNAME
Name: my
Content: cname.vercel-dns.com
Proxy: ✅ Enabled (Orange Cloud)
TTL: Auto
```

**Verifica DNS:**

```bash
dig my.balizero.com +short
# Expected: cname.vercel-dns.com
```

---

### 2. Vercel Domain Configuration

#### Step 1: Aggiungere dominio su Vercel Dashboard

1. Vai su [Vercel Dashboard](https://vercel.com/dashboard)
2. Seleziona progetto `nuzantara-mouth` (o il nome del progetto)
3. Vai su **Settings** → **Domains**
4. Clicca **Add Domain**
5. Inserisci: `my.balizero.com`
6. Clicca **Add**

#### Step 2: Verifica DNS

Vercel genererà un record TXT per la verifica:

```bash
# Record TXT da aggiungere su Cloudflare
Type: TXT
Name: _vercel
Content: vc-domain-verify=my.balizero.com,<VERIFICATION_CODE>
TTL: Auto
```

**Nota:** Il codice di verifica sarà generato da Vercel e mostrato nel dashboard.

#### Step 3: Verifica completamento

Dopo aver aggiunto il record TXT, Vercel verificherà automaticamente il dominio (può richiedere alcuni minuti).

**Status atteso:** ✅ **Valid Configuration**

---

### 3. Backend CORS Configuration

Aggiornare `ZANTARA_ALLOWED_ORIGINS` su Fly.io per includere il nuovo dominio:

```bash
# Aggiungere my.balizero.com agli allowed origins
fly secrets set ZANTARA_ALLOWED_ORIGINS="https://balizero.com,https://www.balizero.com,https://kita.balizero.com,https://www.kita.balizero.com,https://my.balizero.com,https://www.my.balizero.com" -a nuzantara-rag
```

**Verifica:**

```bash
fly secrets list -a nuzantara-rag | grep ZANTARA_ALLOWED_ORIGINS
```

---

### 4. Vercel Environment Variables

Verificare che le variabili d'ambiente siano configurate correttamente:

**Vercel Dashboard** → **Settings** → **Environment Variables**

```bash
NEXT_PUBLIC_API_URL=https://nuzantara-rag.fly.dev
NEXT_PUBLIC_FRONTEND_URL=https://my.balizero.com
```

**Nota:** Se `NEXT_PUBLIC_FRONTEND_URL` è già impostata a `https://www.balizero.com`, considerare se cambiarla o aggiungere una variabile specifica per il portal.

---

## 🔄 Redirect Logic (Opzionale)

### Opzione A: Redirect automatico da `/portal/*` su balizero.com

Se gli utenti accedono a `https://www.balizero.com/portal/*`, possiamo reindirizzarli a `my.balizero.com`:

**File:** `apps/mouth/src/middleware.ts`

```typescript
// Redirect portal routes to my.balizero.com
if (
  request.nextUrl.pathname.startsWith("/portal") &&
  request.nextUrl.hostname !== "my.balizero.com"
) {
  const url = request.nextUrl.clone();
  url.hostname = "my.balizero.com";
  return NextResponse.redirect(url, 301);
}
```

### Opzione B: Mantenere entrambi i domini

Permettere accesso sia da:

- `https://www.balizero.com/portal/*` (sito principale)
- `https://my.balizero.com/portal/*` (sottodominio dedicato)

**Raccomandazione:** Opzione B per maggiore flessibilità.

---

## ✅ Checklist Setup

### DNS (Cloudflare)

- [ ] Aggiungere CNAME record: `my` → `cname.vercel-dns.com`
- [ ] Abilitare Proxy (Orange Cloud)
- [ ] Aggiungere TXT record per verifica Vercel
- [ ] Verificare risoluzione DNS: `dig my.balizero.com`

### Vercel

- [ ] Aggiungere dominio `my.balizero.com` nel dashboard
- [ ] Completare verifica DNS
- [ ] Verificare SSL certificate (automatico)
- [ ] Testare deploy automatico

### Backend (Fly.io)

- [ ] Aggiornare `ZANTARA_ALLOWED_ORIGINS` con `my.balizero.com`
- [ ] Verificare CORS configuration
- [ ] Testare API calls da nuovo dominio

### Testing

- [ ] Testare `https://my.balizero.com/portal/login`
- [ ] Testare tutte le pagine portal
- [ ] Verificare autenticazione funzionante
- [ ] Verificare API calls funzionanti
- [ ] Testare su mobile

---

## 🧪 Testing Post-Setup

### 1. Verifica DNS

```bash
dig my.balizero.com +short
# Expected: cname.vercel-dns.com o IP Vercel
```

### 2. Verifica HTTPS

```bash
curl -I https://my.balizero.com
# Expected: HTTP/2 200 o 307 redirect
```

### 3. Test Portal Pages

```bash
# Test tutte le pagine portal
curl -I https://my.balizero.com/portal/vault
curl -I https://my.balizero.com/portal/profile
curl -I https://my.balizero.com/portal/settings
curl -I https://my.balizero.com/portal/visa
curl -I https://my.balizero.com/portal/taxes
```

### 4. Test Authentication

- Accedere a `https://my.balizero.com/portal/login`
- Verificare redirect dopo login
- Verificare API calls funzionanti

---

## 📊 Domini Attuali vs Proposti

### Attuale Configurazione

```
✅ balizero.com              → Sito principale
✅ www.balizero.com          → Sito principale (redirect)
✅ kita.balizero.com      → Dashboard admin/intelligence
⏳ my.balizero.com           → Portal clienti (DA CREARE)
```

### Proposta Finale

```
✅ balizero.com              → Sito pubblico principale
✅ www.balizero.com          → Sito pubblico principale
✅ kita.balizero.com      → Dashboard admin/intelligence
✅ my.balizero.com           → Portal clienti dedicato
```

---

## 🎯 Vantaggi del Sottodominio Dedicato

1. **Separazione Logica**
   - Portal clienti separato dal sito pubblico
   - URL più chiaro e professionale: `my.balizero.com`

2. **Sicurezza**
   - Possibilità di configurare policy CORS più restrittive
   - Isolamento del portal dal sito pubblico

3. **Branding**
   - URL dedicato per clienti: `my.balizero.com`
   - Più facile da ricordare e comunicare

4. **Scalabilità**
   - Possibilità futura di deploy separato se necessario
   - Configurazioni indipendenti

5. **SEO**
   - Evita confusione con contenuti pubblici
   - Portal non indicizzato (protetto da auth)

---

## 📝 Note Implementazione

### Middleware Considerations

Se implementiamo redirect da `balizero.com/portal/*` a `my.balizero.com`:

```typescript
// apps/mouth/src/middleware.ts
export function middleware(request: NextRequest) {
  const hostname = request.nextUrl.hostname;
  const pathname = request.nextUrl.pathname;

  // Redirect portal routes to dedicated subdomain
  if (pathname.startsWith("/portal") && hostname !== "my.balizero.com") {
    const url = request.nextUrl.clone();
    url.hostname = "my.balizero.com";
    return NextResponse.redirect(url, 301);
  }

  // ... resto del middleware
}
```

### Environment Variables

Considerare variabile d'ambiente per il dominio portal:

```bash
# Vercel Environment Variables
NEXT_PUBLIC_PORTAL_URL=https://my.balizero.com
NEXT_PUBLIC_API_URL=https://nuzantara-rag.fly.dev
```

---

## 🚀 Deployment Steps

### 1. Setup DNS (Cloudflare)

```bash
# Aggiungere CNAME record su Cloudflare
Type: CNAME
Name: my
Target: cname.vercel-dns.com
Proxy: ✅ Enabled
```

### 2. Setup Vercel

1. Dashboard → Project → Settings → Domains
2. Add Domain: `my.balizero.com`
3. Aggiungere TXT record per verifica
4. Attendere verifica completamento

### 3. Update Backend CORS

```bash
fly secrets set ZANTARA_ALLOWED_ORIGINS="..." -a nuzantara-rag
```

### 4. Test

```bash
# Verifica DNS
dig my.balizero.com

# Test HTTPS
curl -I https://my.balizero.com

# Test portal pages
curl -I https://my.balizero.com/portal/vault
```

---

## ✅ Status

- [ ] DNS configurato
- [ ] Vercel domain aggiunto
- [ ] SSL certificate attivo
- [ ] Backend CORS aggiornato
- [ ] Testing completato
- [ ] Documentazione aggiornata

---

**Next Steps:** Configurare DNS su Cloudflare e aggiungere dominio su Vercel Dashboard.
