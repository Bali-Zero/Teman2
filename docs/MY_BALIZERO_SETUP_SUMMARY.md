# Setup my.balizero.com - Riepilogo Completo

**Data:** 2025-01-29  
**Status:** ⏳ Da configurare  
**Obiettivo:** Creare sottodominio dedicato per Portal Clienti

---

## 🎯 Situazione Attuale

### Domini Esistenti

```
✅ balizero.com              → Sito pubblico principale
✅ www.balizero.com          → Sito pubblico (redirect)
✅ kita.balizero.com      → Dashboard admin/intelligence
⏳ my.balizero.com           → Portal clienti (DA CREARE)
```

### Pagine Portal Attuali

Le pagine portal sono attualmente accessibili su:

- `https://kita.balizero.com/portal/*` ✅ Funziona
- `https://www.balizero.com/portal/*` → Redirect a zantara (via middleware)

---

## ✅ Modifiche Implementate nel Codice

### 1. Middleware Aggiornato (`apps/mouth/src/middleware.ts`)

**Aggiunto:**

- `PORTAL_DOMAIN = 'my.balizero.com'`
- Logica per riconoscere `my.balizero.com`
- Redirect automatico da `balizero.com/portal/*` → `my.balizero.com/portal/*`
- Redirect automatico da `kita.balizero.com/portal/*` → `my.balizero.com/portal/*`

**Comportamento:**

- ✅ `my.balizero.com/portal/*` → Permesso (dominio dedicato)
- ✅ `balizero.com/portal/*` → Redirect 301 a `my.balizero.com/portal/*`
- ✅ `kita.balizero.com/portal/*` → Redirect 301 a `my.balizero.com/portal/*`
- ✅ `my.balizero.com/*` (non portal) → Redirect a `balizero.com/*`

### 2. CORS Backend Aggiornato (`apps/backend-rag/backend/app/setup/cors_config.py`)

**Aggiunto:**

- `https://my.balizero.com` negli allowed origins
- `https://www.my.balizero.com` negli allowed origins

**Nota:** Dopo il deploy, aggiornare anche il secret Fly.io:

```bash
fly secrets set ZANTARA_ALLOWED_ORIGINS="https://balizero.com,https://www.balizero.com,https://kita.balizero.com,https://www.kita.balizero.com,https://my.balizero.com,https://www.my.balizero.com,https://kita.balizero.com" -a nuzantara-rag
```

---

## 📋 Checklist Setup Completo

### Step 1: DNS Configuration (Cloudflare) ⏳

**Aggiungere record CNAME:**

```bash
# Record DNS su Cloudflare
Type: CNAME
Name: my
Content: cname.vercel-dns.com
Proxy: ✅ Enabled (Orange Cloud)
TTL: Auto
```

**Verifica:**

```bash
dig my.balizero.com +short
# Expected: cname.vercel-dns.com
```

### Step 2: Vercel Domain Setup ⏳

1. **Vercel Dashboard** → Project `nuzantara-mouth` → **Settings** → **Domains**
2. Clicca **Add Domain**
3. Inserisci: `my.balizero.com`
4. Clicca **Add**

**Vercel genererà un record TXT per verifica:**

```bash
# Record TXT da aggiungere su Cloudflare
Type: TXT
Name: _vercel
Content: vc-domain-verify=my.balizero.com,<VERIFICATION_CODE>
TTL: Auto
```

**Nota:** Il codice di verifica sarà mostrato nel Vercel Dashboard.

### Step 3: Backend CORS Update ⏳

**Dopo che il dominio è attivo, aggiornare Fly.io secrets:**

```bash
fly secrets set ZANTARA_ALLOWED_ORIGINS="https://balizero.com,https://www.balizero.com,https://kita.balizero.com,https://www.kita.balizero.com,https://my.balizero.com,https://www.my.balizero.com,https://kita.balizero.com" -a nuzantara-rag
```

**Verifica:**

```bash
fly secrets list -a nuzantara-rag | grep ZANTARA_ALLOWED_ORIGINS
```

### Step 4: Testing ⏳

**Dopo configurazione DNS e Vercel:**

```bash
# 1. Verifica DNS
dig my.balizero.com +short

# 2. Verifica HTTPS
curl -I https://my.balizero.com

# 3. Test portal pages
curl -I https://my.balizero.com/portal/vault
curl -I https://my.balizero.com/portal/profile
curl -I https://my.balizero.com/portal/settings
curl -I https://my.balizero.com/portal/visa
curl -I https://my.balizero.com/portal/taxes

# 4. Test redirect da balizero.com
curl -I https://www.balizero.com/portal/vault
# Expected: Location: https://my.balizero.com/portal/vault

# 5. Test redirect da kita.balizero.com
curl -I https://kita.balizero.com/portal/vault
# Expected: Location: https://my.balizero.com/portal/vault
```

---

## 🎯 Risultato Finale Atteso

### Domini Finali

```
✅ balizero.com              → Sito pubblico
✅ www.balizero.com          → Sito pubblico
✅ kita.balizero.com      → Dashboard admin/intelligence
✅ my.balizero.com           → Portal clienti dedicato
```

### Routing Finale

```
✅ balizero.com/portal/*     → Redirect 301 → my.balizero.com/portal/*
✅ kita.balizero.com/portal/* → Redirect 301 → my.balizero.com/portal/*
✅ my.balizero.com/portal/* → ✅ Accessibile direttamente
✅ my.balizero.com/*         → Redirect → balizero.com/*
```

---

## 📝 File Modificati

### ✅ Già Modificati (pronti per commit)

- `apps/mouth/src/middleware.ts` - Aggiunto supporto per `my.balizero.com`
- `apps/backend-rag/backend/app/setup/cors_config.py` - Aggiunto `my.balizero.com` a CORS

### 📄 Documentazione Creata

- `docs/MY_BALIZERO_SUBDOMAIN_SETUP.md` - Guida completa setup
- `docs/MY_BALIZERO_SETUP_SUMMARY.md` - Questo file (riepilogo)

---

## 🚀 Prossimi Passi

1. **Commit modifiche codice:**

   ```bash
   git add apps/mouth/src/middleware.ts apps/backend-rag/backend/app/setup/cors_config.py
   git commit -m "feat: add my.balizero.com subdomain support for portal"
   git push
   ```

2. **Configurare DNS su Cloudflare:**
   - Aggiungere CNAME: `my` → `cname.vercel-dns.com`
   - Abilitare Proxy (Orange Cloud)

3. **Aggiungere dominio su Vercel:**
   - Dashboard → Project → Settings → Domains
   - Add Domain: `my.balizero.com`
   - Aggiungere TXT record per verifica

4. **Aggiornare Fly.io secrets:**

   ```bash
   fly secrets set ZANTARA_ALLOWED_ORIGINS="..." -a nuzantara-rag
   ```

5. **Testare:**
   - Verificare DNS risoluzione
   - Testare HTTPS
   - Testare tutte le pagine portal
   - Verificare redirect funzionanti

---

## ✅ Status Checklist

- [x] ✅ Codice middleware aggiornato
- [x] ✅ CORS backend aggiornato
- [x] ✅ Documentazione creata
- [ ] ⏳ DNS configurato (Cloudflare)
- [ ] ⏳ Vercel domain aggiunto
- [ ] ⏳ SSL certificate attivo
- [ ] ⏳ Fly.io secrets aggiornati
- [ ] ⏳ Testing completato

---

**Next Action:** Configurare DNS su Cloudflare e aggiungere dominio su Vercel Dashboard.
