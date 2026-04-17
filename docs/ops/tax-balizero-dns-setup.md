# Setup DNS tax.balizero.com — 2 record Cloudflare (manuale)

**Status al 2026-04-17 21:57:**

- ✅ Vercel: `tax.balizero.com` aggiunto al progetto `mouth` via API (non-verified, in attesa DNS)
- ❌ Cloudflare: CF_API_TOKEN disponibile ha scope `Zone:Read` ma non `Zone.DNS:Edit`. Serve owner/admin per aggiungere i 2 record.
- 📝 Codice applicativo: pronto (commit `c9b9fba5c`: middleware rewrite + route group + API)

## I 2 record da aggiungere su Cloudflare

dash.cloudflare.com → zona `balizero.com` → DNS → Records → **Add record**.

### Record 1 — TXT (verifica dominio Vercel)

| Campo   | Valore                                                   |
| ------- | -------------------------------------------------------- |
| Type    | `TXT`                                                    |
| Name    | `_vercel`                                                |
| Content | `vc-domain-verify=tax.balizero.com,2c95ec4b5a84a6e343c9` |
| TTL     | Auto                                                     |
| Proxy   | n/a (TXT)                                                |

Questo dimostra a Vercel che sei owner di `balizero.com`. Una volta creato, va verificato UNA sola volta — poi il record resta lì e serve per verifiche future (altri sottodomini).

### Record 2 — CNAME (routing traffico)

| Campo  | Valore                                                                    |
| ------ | ------------------------------------------------------------------------- |
| Type   | `CNAME`                                                                   |
| Name   | `tax`                                                                     |
| Target | `cname.vercel-dns.com`                                                    |
| TTL    | Auto                                                                      |
| Proxy  | **DNS only** (nuvola grigia, NON arancione — obbligatorio per Vercel SSL) |

## Verifica post-creazione

Attendi ~1 min per propagazione, poi:

```bash
# DNS check
dig +short tax.balizero.com
# expected: cname.vercel-dns.com. + 2 IP 76.76.x.x

# Vercel will auto-verify within ~2 min
curl -s -o /dev/null -w "%{http_code}\n" https://tax.balizero.com/
# expected: 200 (middleware rewrite → /tax-calendar)
```

## Se preferisci non aggiungere un subdomain

Opzione B: abbandonare `tax.balizero.com`, usare path `balizero.com/tax-calendar`.
In questo caso:

1. Rimuovere il blocco TAX_DOMAIN in `apps/mouth/src/middleware.ts`
2. Aggiornare `FUNNEL_HREF.tax` in `FunnelFeature.tsx` e la NavShell
   in tutti i layout L1 a `/tax-calendar`
3. Rimuovere il dominio da Vercel:
   ```bash
   VERCEL_TOKEN=<from env>
   curl -X DELETE -H "Authorization: Bearer $VERCEL_TOKEN" \
     "https://api.vercel.com/v9/projects/prj_LcXb9ZgeUvWpxaIM9K47tQYPeuee/domains/tax.balizero.com?teamId=team_jX3mEbUemBs0Zy4i8aFYZsjS"
   ```

## Note tecniche (per future ops)

- Zone ID `balizero.com` su Cloudflare: `2380e2e04c755e59f27be05c57b88d82`
- Vercel project ID mouth: `prj_LcXb9ZgeUvWpxaIM9K47tQYPeuee`
- Vercel team ID: `team_jX3mEbUemBs0Zy4i8aFYZsjS`
- CF_API_TOKEN nel env file ha scope `Zone:Read` → utile per listare zones ma non per modificare DNS. Per automatizzare futuri sottodomini serve un token con `Zone.DNS:Edit` sul solo balizero.com.
- CF_GLOBAL_API_KEY richiede email — non disponibile nel env; inutilizzabile senza owner email.
