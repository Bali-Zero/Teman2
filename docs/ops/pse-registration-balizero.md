# PSE self-registration data sheet: Bali Zero systems

Status: draft for the staff member filing on OSS-RBA. Prepared 2026-09-11.
Scope: every Bali Zero electronic system with Indonesian users, recorded as a domestic
private-scope PSE (Penyelenggara Sistem Elektronik Lingkup Privat).

This sheet records categories of data only. It holds no personal data values. Every fact
names the repo file or live probe it comes from. Items marked "to confirm" need the owner
or accounting before submission.

## 1. Registry status: not located in the registry on 2026-09-11

No TD-PSE registration was found for Bali Zero, balizero.com, Nuzantara or Zantara.

Method: the public search on the Komdigi PSE portal calls a JSON API, queried directly:

```bash
curl -s -X POST https://pse.komdigi.go.id/api/v1/tdpse/tdpse-list \
  -H 'Content-Type: application/json' \
  -d '{"keyword": "Bali Zero", "length": 20, "start": 0}'
```

The response carries `data.total_rows` and, when rows exist, the PSE name, domain, TDPSE
number, domestic flag, registration date and status ("Terdaftar").

| Keyword             | `total_rows` | Probe                     |
| ------------------- | ------------ | ------------------------- |
| Tokopedia (control) | 22           | this sheet, 2026-09-11    |
| Bali Zero           | 0            | this sheet and prep-check |
| balizero            | 0            | this sheet and prep-check |
| balizero.com        | 0            | this sheet and prep-check |
| Nuzantara           | 0            | this sheet and prep-check |
| zantara             | 0            | this sheet and prep-check |
| PT Bali Zero        | 0            | prep-check, 2026-09-11    |
| Bali Zero Services  | 0            | prep-check, 2026-09-11    |
| kita.balizero       | 0            | prep-check, 2026-09-11    |
| zantara.balizero    | 0            | prep-check, 2026-09-11    |

The control keyword returns rows, so the API answers correctly. One caveat: if the PT's
legal name on the akta does not contain "Bali Zero", repeat the search with that exact
legal name before concluding.

## 2. Company-level fields (shared by every system)

| Field                   | Value                                                                 | Source                                         |
| ----------------------- | --------------------------------------------------------------------- | ---------------------------------------------- |
| Legal entity            | PT PMA, legal name as on the akta (to confirm)                        | `apps/mouth/src/app/terms/page.tsx` ("PT PMA") |
| NIB                     | Active NIB number (to confirm)                                        | owner / accounting                             |
| KBLI                    | KBLI on the NIB that covers the electronic systems below (to confirm) | owner / accounting                             |
| NPWP                    | Company NPWP (to confirm)                                             | owner / accounting                             |
| Akta and SK Kemenkumham | Deed of establishment and ministry decree (to confirm)                | owner / accounting                             |
| Responsible officer     | `<to be named by the owner>`                                          | owner decision                                 |
| Data-protection contact | privacy@balizero.com (role address published in the privacy policy)   | `apps/mouth/src/app/privacy/page.tsx`          |
| Privacy policy          | https://balizero.com/privacy                                          | `apps/mouth/src/app/privacy/page.tsx`          |
| Terms of service        | https://balizero.com/terms                                            | `apps/mouth/src/app/terms/page.tsx`            |
| Registration fee        | None (no PNBP fee)                                                    | prep-check §3                                  |

The privacy policy states it follows UU PDP No. 27/2022 and lists the data categories,
legal bases, storage locations and retention periods reused in section 3.

## 3. Systems

All web frontends are one Next.js app, `apps/mouth`, deployed as the Vercel project
`mouth` (`apps/mouth/vercel.json`). Host-to-route mapping lives in `apps/mouth/src/proxy.ts`.
`vercel.json` pins no region; the live responses on 2026-09-11 carried an `x-vercel-id`
starting with `sin1` (Vercel Singapore edge). All frontends call the backend API in
section 3.7.

Storage locations for personal data, as stated in section 5 of the published privacy
policy:

| Store                       | Provider and location | Role                                                |
| --------------------------- | --------------------- | --------------------------------------------------- |
| Application and PostgreSQL  | Fly.io, Singapore     | API hosting and primary database                    |
| Vector search               | Qdrant Cloud, US      | Knowledge and document search                       |
| Documents and AI processing | Google, global        | Google Drive document storage, Gemini AI processing |
| Cache                       | Upstash, global       | Redis cache, 5-minute TTL                           |
| Document OCR                | Local server, Bali    | Ollama OCR, no cross-border transfer                |

### 3.1 balizero.com and www.balizero.com

| Field               | Value                                                                                                                                                                                                                                           |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Purpose             | Public website: services, articles, tools (KBLI lookup, Visa Oracle eligibility check), contact, newsletter                                                                                                                                     |
| URL                 | https://balizero.com and https://www.balizero.com (www redirects to the apex)                                                                                                                                                                   |
| Users               | Prospective and current clients, public readers                                                                                                                                                                                                 |
| Hosting and region  | Vercel project `mouth`, Singapore edge (`sin1`); backend: Fly.io `sin`                                                                                                                                                                          |
| Repo source         | `apps/mouth` route groups `(marketing)`, `(blog)`; `PUBLIC_DOMAIN` in `apps/mouth/src/proxy.ts`                                                                                                                                                 |
| Data categories     | Newsletter email address; inquiry contact details (name, email, phone, message); Visa Oracle answers held in the browser session (`evaluation-identity-store.ts`); web analytics (Google Analytics, per the CSP in `apps/mouth/next.config.ts`) |
| Privacy policy      | https://balizero.com/privacy; Visa Oracle has its own notice at https://balizero.com/visa-oracle/privacy                                                                                                                                        |
| Responsible officer | `<to be named by the owner>`                                                                                                                                                                                                                    |
| KBLI                | To confirm                                                                                                                                                                                                                                      |

### 3.2 kita.balizero.com

| Field               | Value                                                                                                                                                                                                                                                                                                             |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Purpose             | Internal staff workspace: clients (CRM), case processing, WhatsApp inbox, team management, analytics, notifications, admin                                                                                                                                                                                        |
| URL                 | https://kita.balizero.com (root redirects to `/login`)                                                                                                                                                                                                                                                            |
| Users               | Bali Zero staff only, login required, `noindex`                                                                                                                                                                                                                                                                   |
| Hosting and region  | Vercel project `mouth`, Singapore edge (`sin1`); backend: Fly.io `sin`                                                                                                                                                                                                                                            |
| Repo source         | `APP_DOMAIN` and `INTERNAL_ROUTES` in `apps/mouth/src/proxy.ts`                                                                                                                                                                                                                                                   |
| Data categories     | Staff accounts and roles; client records: identity (name, nationality, date of birth, gender, address), passport data, contact details, family members, company data; case and permit status; client documents (passport, KTP, NPWP scans); message history across channels; financial data for visa applications |
| Privacy policy      | https://balizero.com/privacy                                                                                                                                                                                                                                                                                      |
| Responsible officer | `<to be named by the owner>`                                                                                                                                                                                                                                                                                      |
| KBLI                | To confirm                                                                                                                                                                                                                                                                                                        |

### 3.3 my.balizero.com

| Field               | Value                                                                                                                                                                                                                 |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Purpose             | Client portal: a client follows visas, companies, taxes, LKPM, documents, messages and billing                                                                                                                        |
| URL                 | https://my.balizero.com (unauthenticated visitors go to `/portal/login`)                                                                                                                                              |
| Users               | Bali Zero clients, login required                                                                                                                                                                                     |
| Hosting and region  | Vercel project `mouth`, Singapore edge (`sin1`); backend: Fly.io `sin`                                                                                                                                                |
| Repo source         | `PORTAL_DOMAIN` in `apps/mouth/src/proxy.ts`; pages in `apps/mouth/src/app/portal/(authenticated)/`                                                                                                                   |
| Data categories     | Client account and session cookie; profile; family members; company data; visa and permit status; tax and LKPM data; document vault (passport, KTP, NPWP scans); messages and chat; billing records; privacy settings |
| Privacy policy      | https://balizero.com/privacy                                                                                                                                                                                          |
| Responsible officer | `<to be named by the owner>`                                                                                                                                                                                          |
| KBLI                | To confirm                                                                                                                                                                                                            |

### 3.4 zantara.balizero.com

| Field               | Value                                                                                                                                                                                                                                          |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Purpose             | Zantara AI assistant chat (root rewritten to `/chat`)                                                                                                                                                                                          |
| URL                 | https://zantara.balizero.com                                                                                                                                                                                                                   |
| Users               | Clients and staff, `noindex`                                                                                                                                                                                                                   |
| Hosting and region  | Vercel, Singapore (`sin1` edge and function region observed); backend: Fly.io `sin`                                                                                                                                                            |
| Repo source         | `ZANTARA_DOMAIN` in `apps/mouth/src/proxy.ts`. `apps/web/README.md` also names this host; the live response carries the `x-pathname` header set by the mouth proxy, so mouth serves it today. Confirm in Vercel which project owns the domain. |
| Data categories     | Chat messages and conversation history; account and session                                                                                                                                                                                    |
| Privacy policy      | https://balizero.com/privacy                                                                                                                                                                                                                   |
| Responsible officer | `<to be named by the owner>`                                                                                                                                                                                                                   |
| KBLI                | To confirm                                                                                                                                                                                                                                     |

### 3.5 tax.balizero.com

| Field               | Value                                                                                         |
| ------------------- | --------------------------------------------------------------------------------------------- |
| Purpose             | Tax Compliance Calendar: deadlines and reminders for businesses in Bali                       |
| URL                 | https://tax.balizero.com                                                                      |
| Users               | Public                                                                                        |
| Hosting and region  | Vercel project `mouth`, Singapore edge (`sin1`)                                               |
| Repo source         | `TAX_DOMAIN` in `apps/mouth/src/proxy.ts`; route group `apps/mouth/src/app/(tax-calendar)/`   |
| Data categories     | No input form found in the route group on 2026-09-11: public content only, plus web analytics |
| Privacy policy      | https://balizero.com/privacy                                                                  |
| Responsible officer | `<to be named by the owner>`                                                                  |
| KBLI                | To confirm                                                                                    |

DNS setup for this host: [tax-balizero-dns-setup.md](tax-balizero-dns-setup.md).

### 3.6 prime.balizero.com

| Field               | Value                                                                                                                              |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Purpose             | Prime Nexus: Bali geospatial decision hub for property, with an assistant chat                                                     |
| URL                 | https://prime.balizero.com                                                                                                         |
| Users               | Prospective and current property clients                                                                                           |
| Hosting and region  | Vercel project `mouth`, Singapore edge (`sin1`); backend: Fly.io `sin`                                                             |
| Repo source         | `prime` rewrite in `apps/mouth/src/proxy.ts`; `apps/mouth/src/app/prime/`; chat route `apps/mouth/src/app/api/prime/chat/route.ts` |
| Data categories     | Chat questions forwarded to the backend API; property proposal pages reached by token link                                         |
| Privacy policy      | https://balizero.com/privacy                                                                                                       |
| Responsible officer | `<to be named by the owner>`                                                                                                       |
| KBLI                | To confirm                                                                                                                         |

### 3.7 Backend API: Fly app nuzantara-rag

| Field               | Value                                                                                                                     |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Purpose             | Backend for every system above: accounts, CRM, documents, AI assistant and knowledge search                               |
| Host                | `nuzantara-rag.fly.dev` (named in the CSP `connect-src` of `apps/mouth/next.config.ts`); health: `GET /health`            |
| Users               | No direct end users; called by the frontends                                                                              |
| Hosting and region  | Fly.io app `nuzantara-rag`, `primary_region = 'sin'` (Singapore), processes `api` and `rag` (`apps/backend-rag/fly.toml`) |
| Data categories     | All categories in 3.1 to 3.6; stores listed in the table at the start of section 3                                        |
| Privacy policy      | https://balizero.com/privacy                                                                                              |
| Responsible officer | `<to be named by the owner>`                                                                                              |
| KBLI                | To confirm                                                                                                                |

The API answers `GET` only: `curl -I` (HEAD) returns 404 on `/health` while `GET /health`
returns 200. Probe it with GET.

## 4. OSS-RBA submission checklist

Channel: OSS-RBA (https://oss.go.id), integrated with the Komdigi PSE portal
(https://pse.komdigi.go.id). Output: an electronic TD-PSE certificate.

- [ ] Active NIB with a KBLI coherent with the systems in section 3 (KBLI to confirm)
- [ ] Akta pendirian and SK Kemenkumham
- [ ] Company NPWP
- [ ] Responsible officer: `<to be named by the owner>`, with position and a reachable contact
- [ ] System description and technology, one per system (section 3)
- [ ] Domain or URL for every system, web and app filed separately (section 3)
- [ ] Server and data location (section 3 storage table and each system's hosting row)
- [ ] Privacy policy URL: https://balizero.com/privacy
- [ ] Content categories for each system
- [ ] Repeat the registry search with the PT's exact legal name (section 1) before filing

Cost: no PNBP fee. Processing time: not found.

Legal basis: PP 71/2019; Permenkominfo 5/2020 as amended by Permenkominfo 10/2021; UU ITE;
UU PDP 27/2022. No 2024 to 2026 update was found, which does not rule one out.

Obligations after registration: keep the registered data up to date; keep the responsible
officer reachable; give authorised authorities access to the systems; take content down on
request. The 24-hour and 4-hour (urgent) takedown windows appear only in secondary sources.

Sanctions: written warning, temporary suspension, blocking. An unregistered PSE risks
direct blocking.

Sources for this section are secondary (izin.co.id guide on PSE Kominfo; aptika.kominfo.go.id
on sanctions; jdih.komdigi.go.id for Permenkominfo 5/2020) because the Komdigi pages did not
render for a fetch. Check the live OSS-RBA form before relying on the list.

## 5. Open items for the owner

1. Name the responsible officer.
2. Confirm the legal name, NIB, KBLI and NPWP, then re-run the section 1 search with the
   legal name.
3. Confirm in Vercel which project owns zantara.balizero.com (section 3.4).
4. Confirm the storage locations in the privacy policy still hold (Qdrant Cloud region
   stated as US).

## 6. Reachability check (2026-09-11)

`curl -sI -m 20` on every URL in this sheet. Endpoints that do not route HEAD were also
probed with the method they serve.

| URL                                               | HEAD | Served method |
| ------------------------------------------------- | ---- | ------------- |
| https://balizero.com                              | 200  |               |
| https://www.balizero.com                          | 308  |               |
| https://kita.balizero.com                         | 307  |               |
| https://my.balizero.com                           | 307  |               |
| https://zantara.balizero.com                      | 200  |               |
| https://tax.balizero.com                          | 200  |               |
| https://prime.balizero.com                        | 200  |               |
| https://balizero.com/privacy                      | 200  |               |
| https://balizero.com/terms                        | 200  |               |
| https://balizero.com/visa-oracle/privacy          | 200  |               |
| https://oss.go.id                                 | 307  |               |
| https://pse.komdigi.go.id                         | 200  |               |
| https://pse.komdigi.go.id/api/v1/tdpse/tdpse-list | 405  | POST 200      |
