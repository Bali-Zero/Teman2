# SEO Redirect: mo.balizero.com → balizero.com

**Data Implementazione:** 2026-01-21  
**Tipo:** Redirect 301 (Permanent)  
**Motivo:** Consolidare domain authority e prevenire contenuti duplicati

---

## 🎯 Problema

Il sottodominio `mo.balizero.com` (mobile) esisteva e poteva creare problemi SEO:

1. **Contenuti Duplicati:** Google potrebbe indicizzare sia `balizero.com` che `mo.balizero.com`
2. **Domain Authority Split:** Il ranking viene diviso tra due domini invece di essere concentrato
3. **Mobile-First Indexing:** Google preferisce un unico dominio responsive invece di sottodomini separati

---

## ✅ Soluzione Implementata

### Redirect 301 (Permanent)

Tutto il traffico da `mo.balizero.com` viene reindirizzato permanentemente a `balizero.com` mantenendo il path e i query parameters.

**Implementazione:**

- ✅ Middleware Next.js (`src/middleware.ts`)
- ✅ Next.js redirects config (`next.config.ts`)

### Codice Implementato

**1. Middleware (`src/middleware.ts`):**

```typescript
// Redirect 301: mo.balizero.com → balizero.com
if (hostname === MOBILE_DOMAIN || hostname === `www.${MOBILE_DOMAIN}`) {
  const redirectUrl = new URL(pathname, `https://${PUBLIC_DOMAIN}`);
  redirectUrl.search = request.nextUrl.search;
  return NextResponse.redirect(redirectUrl, 301); // Permanent redirect
}
```

**2. Next.js Config (`next.config.ts`):**

```typescript
async redirects() {
  return [
    {
      source: '/:path*',
      has: [
        {
          type: 'host',
          value: 'mo.balizero.com',
        },
      ],
      destination: 'https://balizero.com/:path*',
      permanent: true, // 301 redirect
    },
  ];
}
```

---

## 🔍 Verifica

### Test Manuale

```bash
# Test redirect
curl -I https://mo.balizero.com
# Expected: HTTP/1.1 301 Moved Permanently
# Expected: Location: https://balizero.com/

curl -I https://mo.balizero.com/services
# Expected: HTTP/1.1 301 Moved Permanently
# Expected: Location: https://balizero.com/services
```

### Google Search Console

1. Verificare che `mo.balizero.com` non sia più indicizzato
2. Verificare che tutti i link da `mo.balizero.com` siano stati trasferiti a `balizero.com`
3. Monitorare eventuali errori di crawling

---

## 📊 Benefici SEO

1. **Consolidamento Domain Authority:** Tutto il ranking va a `balizero.com`
2. **Nessun Contenuto Duplicato:** Google vede un solo dominio
3. **Mobile-First:** `balizero.com` è già responsive, non serve sottodominio mobile
4. **Link Equity:** Tutti i link esterni a `mo.balizero.com` vengono trasferiti a `balizero.com`

---

## ⚠️ Note Importanti

1. **DNS:** Il record DNS per `mo.balizero.com` può rimanere attivo (il redirect funziona a livello applicazione)
2. **Tempo di Propagazione:** Google può impiegare alcune settimane per riconoscere il redirect
3. **Backlinks:** I backlink esistenti a `mo.balizero.com` continueranno a funzionare grazie al redirect
4. **Analytics:** Monitorare il traffico da `mo.balizero.com` per verificare che il redirect funzioni

---

## 🚀 Next Steps

1. ✅ Implementato redirect 301
2. ⏳ Verificare in Google Search Console dopo 1-2 settimane
3. ⏳ Monitorare analytics per traffico da `mo.balizero.com`
4. ⏳ Considerare rimozione DNS di `mo.balizero.com` se non più necessario (opzionale)

---

**Status:** ✅ Implementato  
**Deploy:** In attesa di deploy su Vercel
