# Cloudflare DNS Setup - mo.balizero.com Redirect

**Data:** 2026-01-21  
**Obiettivo:** Configurare redirect DNS per `mo.balizero.com` → `balizero.com`

---

## 📋 Situazione Attuale

- **mo.balizero.com:** ❌ Non risolve DNS
- **balizero.com:** ✅ Risolve a `216.150.1.1`
- **Redirect:** ✅ Implementato nel codice (middleware + next.config.ts)

---

## 🔧 Opzioni di Configurazione Cloudflare

### Opzione 1: Redirect Page Rule (Consigliato)

**Vantaggi:**

- Redirect HTTP 301 automatico
- Funziona a livello DNS/CDN
- Più veloce del redirect applicativo

**Configurazione:**

1. Accedi a Cloudflare Dashboard: https://dash.cloudflare.com
2. Seleziona il dominio `balizero.com`
3. Vai a **Rules** → **Page Rules**
4. Crea nuova rule:
   - **URL Pattern:** `mo.balizero.com/*`
   - **Setting:** Forwarding URL
   - **Status Code:** 301 Permanent Redirect
   - **Destination URL:** `https://balizero.com/$1`

---

### Opzione 2: CNAME Record (Se mo.balizero.com è sottodominio)

**Configurazione:**

1. Accedi a Cloudflare Dashboard
2. Seleziona il dominio `balizero.com`
3. Vai a **DNS** → **Records**
4. Aggiungi nuovo record:
   - **Type:** CNAME
   - **Name:** `mo`
   - **Target:** `balizero.com`
   - **Proxy status:** Proxied (arancione cloud)
   - **TTL:** Auto

5. Crea Page Rule per redirect:
   - **URL Pattern:** `mo.balizero.com/*`
   - **Setting:** Forwarding URL
   - **Status Code:** 301
   - **Destination:** `https://balizero.com/$1`

---

### Opzione 3: A Record + Page Rule

**Configurazione:**

1. Aggiungi A Record:
   - **Type:** A
   - **Name:** `mo`
   - **IPv4 address:** `216.150.1.1` (stesso IP di balizero.com)
   - **Proxy status:** Proxied

2. Crea Page Rule per redirect:
   - **URL Pattern:** `mo.balizero.com/*`
   - **Setting:** Forwarding URL
   - **Status Code:** 301
   - **Destination:** `https://balizero.com/$1`

---

## ✅ Verifica Post-Configurazione

Dopo la configurazione, verifica:

```bash
# Verifica DNS resolution
dig mo.balizero.com +short

# Verifica redirect HTTP
curl -I https://mo.balizero.com

# Dovrebbe restituire:
# HTTP/1.1 301 Moved Permanently
# Location: https://balizero.com/
```

---

## 📝 Note

1. **Propagazione DNS:** Può richiedere fino a 24-48 ore (solitamente 5-15 minuti con Cloudflare)

2. **Page Rules Limit:** Cloudflare Free plan ha limite di 3 page rules

3. **Redirect Doppio:** Il redirect è già implementato nel codice (middleware + next.config.ts), quindi funzionerà anche senza Page Rule se il DNS risolve

4. **SEO:** Il redirect 301 è già implementato nel codice, quindi anche se il DNS non risolve, quando risolverà il redirect funzionerà automaticamente

---

## 🚀 Raccomandazione

**Usa Opzione 1 (Page Rule)** se:

- Hai Page Rules disponibili
- Vuoi redirect veloce a livello CDN

**Usa Opzione 2 (CNAME)** se:

- `mo.balizero.com` è un sottodominio esistente
- Vuoi mantenere il sottodominio ma redirectare tutto il traffico

**Usa Opzione 3 (A Record)** se:

- Vuoi semplicemente che il DNS risolva
- Il redirect applicativo è sufficiente

---

**Status:** ⏳ In attesa di configurazione Cloudflare
