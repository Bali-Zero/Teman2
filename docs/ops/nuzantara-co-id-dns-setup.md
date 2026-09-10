# DNS setup nuzantara.co.id — Vercel domain + 2 Cloudflare records (manual)

**Status at 2026-09-11:**

- Domain: `nuzantara.co.id` registered 2025-09-26, nameservers on Cloudflare, zone has **no records**.
- Application code: ready. `NUZANTARA_DOMAIN` in `apps/mouth/src/proxy.ts` rewrites every
  path on `nuzantara.co.id` and `www.nuzantara.co.id` to the `(nuzantara)` route group at
  `/nuzantara/*`, with `X-Robots-Tag: noindex, nofollow`. The page itself also declares
  `robots: { index: false, follow: false }`.
- Operator action (owner): steps 1 and 2 below. Nothing here is automated; the available
  `CF_API_TOKEN` is `Zone:Read` only (see `tax-balizero-dns-setup.md`).
- Launch is gated: see "Before launch" at the end. Adding DNS makes the holding page
  reachable; it does not make it a launch.

## Step 1 — Add the domain to the Vercel project `mouth`

Vercel dashboard → project `mouth` → Settings → Domains → **Add**:

1. `nuzantara.co.id` (primary).
2. `www.nuzantara.co.id`, set to **redirect to `nuzantara.co.id`** (308).

Equivalent API call (token from the operator env, never pasted into docs or chat):

```bash
PROJECT=prj_LcXb9ZgeUvWpxaIM9K47tQYPeuee
TEAM=team_jX3mEbUemBs0Zy4i8aFYZsjS
curl -s -X POST -H "Authorization: Bearer $VERCEL_TOKEN" -H "Content-Type: application/json" \
  "https://api.vercel.com/v10/projects/$PROJECT/domains?teamId=$TEAM" \
  -d '{"name":"nuzantara.co.id"}'
curl -s -X POST -H "Authorization: Bearer $VERCEL_TOKEN" -H "Content-Type: application/json" \
  "https://api.vercel.com/v10/projects/$PROJECT/domains?teamId=$TEAM" \
  -d '{"name":"www.nuzantara.co.id","redirect":"nuzantara.co.id","redirectStatusCode":308}'
```

After adding, the Domains panel shows the exact DNS values Vercel expects for this project.
**If they differ from the table below, use the values from the panel.** If the panel asks for a
`_vercel` TXT verification record, add it too, copying the value verbatim from the panel (it is
issued per domain; do not reuse the `tax.balizero.com` value).

## Step 2 — The 2 records to add on Cloudflare

dash.cloudflare.com → zone `nuzantara.co.id` → DNS → Records → **Add record**.

### Record 1 — A (apex)

| Field        | Value                                                           |
| ------------ | --------------------------------------------------------------- |
| Type         | `A`                                                             |
| Name         | `@` (`nuzantara.co.id`)                                         |
| IPv4 address | `76.76.21.21`                                                   |
| TTL          | Auto                                                            |
| Proxy        | **DNS only** (grey cloud, not orange — required for Vercel SSL) |

### Record 2 — CNAME (www)

| Field  | Value                                                           |
| ------ | --------------------------------------------------------------- |
| Type   | `CNAME`                                                         |
| Name   | `www`                                                           |
| Target | `cname.vercel-dns.com`                                          |
| TTL    | Auto                                                            |
| Proxy  | **DNS only** (grey cloud, not orange — required for Vercel SSL) |

## Verify after creation

Wait about a minute for propagation, then:

```bash
dig +short nuzantara.co.id
# expected: 76.76.21.21 (or the value the Vercel panel gave)
dig +short www.nuzantara.co.id
# expected: cname.vercel-dns.com. followed by Vercel IPs

curl -s -o /dev/null -w "%{http_code}\n" https://nuzantara.co.id/
# expected: 200 (proxy rewrite → /nuzantara)
curl -sI https://nuzantara.co.id/ | grep -i x-robots-tag
# expected: x-robots-tag: noindex, nofollow
curl -s https://nuzantara.co.id/ | grep -o "dicek ulang oleh manusia"
# expected: one match (the page promise)
```

## Before launch (not a DNS step, but it blocks launch)

- **PSE registration.** `nuzantara.co.id` is an electronic system serving Indonesian users, so it
  must be registered as a domestic private-scope PSE (PSE Lingkup Privat) through OSS-RBA
  (`oss.go.id`) under the NIB of the PT PMA that operates it, **before** the page is launched
  (indexed, linked, or promoted). Per the 2026-09-11 board (verbale giro 3), this registration
  is not started before day 30 of the Bali Zero pilot.
- Replace the placeholders on the page: `<nama PT>` in the footer (legal name of the PT PMA)
  and the WhatsApp number via the `NEXT_PUBLIC_NUZANTARA_WA` env var on the Vercel project
  (build-time variable; redeploy after setting it).
- Flip `robots` in `apps/mouth/src/app/(nuzantara)/nuzantara/layout.tsx` and the
  `X-Robots-Tag` in the `NUZANTARA_DOMAIN` block of `proxy.ts` only at launch, in one PR.

## Rollback

1. Remove the `NUZANTARA_DOMAIN` block from `apps/mouth/src/proxy.ts` and delete
   `apps/mouth/src/app/(nuzantara)/`.
2. Remove the domain from Vercel:
   ```bash
   curl -X DELETE -H "Authorization: Bearer $VERCEL_TOKEN" \
     "https://api.vercel.com/v9/projects/prj_LcXb9ZgeUvWpxaIM9K47tQYPeuee/domains/nuzantara.co.id?teamId=team_jX3mEbUemBs0Zy4i8aFYZsjS"
   ```
3. Delete the two Cloudflare records.

## Technical notes

- Vercel project ID mouth: `prj_LcXb9ZgeUvWpxaIM9K47tQYPeuee`; team ID: `team_jX3mEbUemBs0Zy4i8aFYZsjS`
  (same as `tax-balizero-dns-setup.md`).
- The route also answers at `balizero.com/nuzantara` (same as `balizero.com/tax-calendar`);
  it is noindex there too and is not listed in `apps/mouth/src/app/sitemap.ts`.
