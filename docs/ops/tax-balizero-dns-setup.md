# Setup DNS tax.balizero.com — manuale (blocco agente)

Il rollout v2 L1 Funnel Hub ha un Tax Calendar funnel pronto al codice
(route group `(tax-calendar)` in apps/mouth, middleware rewrite attivo),
ma il dominio `tax.balizero.com` restituisce `ERR_NAME_NOT_RESOLVED`
perché mancano 2 configurazioni manuali che richiedono credenziali
owner non accessibili all'agente.

## Step 1 — Cloudflare DNS

1. Vai su dash.cloudflare.com → zona `balizero.com` → DNS → Records
2. Clic **Add record** con:
   - Type: `CNAME`
   - Name: `tax`
   - Target: `cname.vercel-dns.com`
   - Proxy status: **DNS only** (nuvola grigia, NON arancione —
     importante per Vercel SSL provisioning)
   - TTL: Auto
3. Save.

Verify (dopo propagazione ~1 min):

```bash
dig +short tax.balizero.com
# expected: cname.vercel-dns.com. + 2 IP 76.76.x.x (come visa.)
```

## Step 2 — Vercel project mouth

Il dominio `balizero.com` è registrato in un account Vercel diverso
da `nuzantara-2026` (il mio login via CLI). L'owner deve:

1. Vercel dashboard → progetto `mouth` (nell'account che possiede
   balizero.com — stesso dove è già `visa.balizero.com`)
2. Settings → Domains → **Add Domain**
3. Inserire `tax.balizero.com`
4. Cliccare Add. Vercel verifica CNAME (da Step 1), poi provisiona SSL.

Verify (dopo SSL provisioning ~2–5 min):

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://tax.balizero.com/
# expected: 200 (middleware rewrite → /tax-calendar)
```

## Opzione B — evitare sottodominio

Se creare un altro sottodominio non è desiderato, si può abbandonare
`tax.balizero.com` e usare un path su balizero.com:

1. Rimuovere il blocco `TAX_DOMAIN` in `apps/mouth/src/middleware.ts`
2. Rinominare la route group `(tax-calendar)/tax-calendar/` in
   `(tax)/tax/` (o mantenere `tax-calendar` se si vuole URL descrittivo)
3. Aggiornare `FUNNEL_HREF.tax` in
   `apps/mouth/src/app/v2/_components/FunnelFeature.tsx` e la NavShell
   in tutti i layout L1 a `/tax-calendar` (o `/tax`)
4. Nessun cambio DNS/Vercel necessario: il path vive sotto
   balizero.com esistente.

Con entrambe le opzioni il codice applicativo è già pronto — è solo
una questione di routing.

## Stato attuale

- Codice: ✅ pronto (commit c9b9fba5c: tax-calendar route + middleware)
- DNS: ❌ assente (questo documento)
- Vercel: ❌ dominio non aggiunto al progetto
- Backend: ✅ endpoints `/api/tax-calendar/{deadlines,ical}` funzionanti
