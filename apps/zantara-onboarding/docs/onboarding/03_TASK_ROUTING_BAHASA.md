# Task Routing — VERDE / GIALLO / ROSSO

**Reference:** memory `subhi-task-routing.md` Antonello
**Goal:** sebelum mulai task baru, cek perimeter. VERDE = langsung kerja,
GIALLO = pair, ROSSO = jangan disentuh.

## Kenapa harus ada perimeter

Subhi adalah **Growth Systems Owner** — bukan backend developer. Sentuh
RAG, Qdrant, embeddings, atau secrets = risiko rusak production yang
Subhi belum bisa nilai. Selain itu, nilai utama peran Subhi ada di
"last mile" frontend → lead, bukan di modifikasi infrastruktur.

Perimeter ini sengaja ketat di awal. Setelah probation 90 hari, kalau
konversi disetujui, scope membesar (lihat `02_RBAC_BAHASA.md` §akhir).

## VERDE — langsung kerjakan

### Frontend mouth

- `apps/mouth/src/app/(blog)/**` — blog content + UX
- `apps/mouth/src/content/articles/**` — artikel markdown (149 file)
- `apps/mouth/src/components/blog/**` — komponen blog
- `apps/mouth/src/app/v2/_components/FunnelFeature.tsx` — 4 funnel CTA
- `apps/mouth/src/app/(marketing)/**` — landing marketing
- `apps/mouth/src/app/kbli/**` — UX/CRO KBLI navigator
  (BUKAN data model 1.563 codes)
- `apps/mouth/src/app/kbli-explorer/**` — entry points + analytics
- `apps/mouth/src/app/visa/**` — UX visa oracle
  (BUKAN scoring logic backend)
- `apps/mouth/src/app/property/eligibility/**` — UX property
- `apps/mouth/src/app/(tax-calendar)/**` — UX tax calendar
- `apps/mouth/src/app/sitemap.ts` + `robots.ts`
- `apps/mouth/public/llms*.txt`

### Library + e2e

- `apps/mouth/src/lib/analytics.ts` — tracking helpers
- `apps/mouth/e2e/**` — Playwright tests funnel CTA

### Distribution + Analytics (luar codebase)

- GA4 dashboard, Search Console queries, UTM taxonomy
- LinkedIn / FB groups / Reddit / Quora distribution (manual)
- Spreadsheet artikel → intent → service mapping

### Contoh task VERDE konkret

- Fix tracking GA4 di `FunnelFeature.tsx` (Day 1 mission)
- Convert 12 articles ke money pages dengan CTA + internal links
- Bangun 4 komponen "Article → Tool" reusable
- Daily distribution batch (LinkedIn / FB / WhatsApp / GBP)
- WhatsApp CTA contextual di pages prioritas
- Search Console query review weekly
- A/B test CTA copy
- Audit articles per cluster komersial (visa / company / tax / property)

## GIALLO — pair dengan Asya atau Antonello

Subhi boleh **propose** desain dan **draft** code, tapi yang menjalankan
edit + merge adalah Asya (backend) atau Antonello.

### Backend pair

- Endpoint baru di `apps/backend-rag/backend/app/routers/visa_oracle.py`
  atau `kbli_notebook.py` (mis. endpoint baru `/visa-oracle/explain`)
- Service baru untuk Funnel 2.0 (mis. `<FunnelConversation>` shared layer)
- Modifikasi `apps/evaluator/seo_cell/dna.json` (budget cell, max_actions)
- Tambah sensor di `apps/evaluator/seo_cell/sensors/`
- Migrations SQL v2 (bahkan INSERT-only) — selalu dengan review
- Modifikasi `apps/backend-rag/backend/app/routers/portal_taxes.py` untuk
  versi public
- Schema cambi di `team_members` atau `users` table

### Cara kerja GIALLO

1. Subhi tulis proposal di `proposals/<topic>.md` (di workspace lokal)
2. Tutor bantu format proposal supaya jelas (problem, solution, alternatives,
   risk)
3. Subhi DM proposal ke Asya/Antonello
4. Mereka review → green light → Subhi pair di IDE / call
5. Edit + commit dilakukan oleh **owner** (Asya/Antonello), bukan Subhi
6. Subhi belajar dari proses — perlahan-lahan dapat write access lebih
   banyak

## ROSSO — JANGAN PERNAH disentuh

Selama probation, file/scope ini benar-benar off-limits. Kalau tutor
nyaranin sentuh = tolak request, jelaskan bahwa ini ROSSO.

### Backend core

- `apps/backend-rag/backend/services/rag/**` — RAG core
- `apps/backend-rag/backend/services/events/**` — EventBus PG LISTEN/NOTIFY
- `apps/backend-rag/backend/prompts/zantara_core.py` — system prompt Zantara
- `apps/backend-rag/backend/db/migrations_v2/**` — schema migrations
  (boleh propose desain, JANGAN apply)

### Cell + Organism

- `apps/cell/cell/core/**` — cell_core package
- `apps/organism/organism/genome.yaml` — registry organi

### Infra + Secrets

- `fly.toml`, `.env*`, `.nuzantara-secrets*`
- Qdrant payload, embedding model `text-embedding-3-small` (FROZEN)
- Auth, JWT, RBAC enforcement
- LaunchAgents Pro, cron Pro, secrets rotation

### Data live

- CRM data live, pratiche cliente reali (read-only assigned, MAI write)
- Deploy production tanpa review

## Eskalasi — siapa minta tolong untuk apa

| Masalah | Person to ping | Channel |
| --- | --- | --- |
| Blocker teknis backend | Asya | Slack/WA |
| Decision strategis / produk | Antonello | WA |
| Pratiche client immigration | Sahira | WA / kantor |
| Pratiche client tax | Surya | WA / kantor |
| Pratiche client visa | Ari Firda | WA / kantor |
| Deploy production approval | Antonello (mai self-merge 30 hari pertama) | PR review |
| HR / contract / leave | Adit | WA |
| Deploy emergency fix | Antonello | WA — tidak pernah independent |

## Format eskalasi yang baik

Bukan: "ada error nih"

Tapi:

> "Ke @Asya — saya coba tambah filter di
> `apps/backend-rag/backend/app/routers/visa_oracle.py` line 89 untuk
> Day 5 mission, butuh review. Branch: `sancho/visa-oracle-filter`.
> PR draft: github.com/.../#234. Goal: filter by `visa_type` query param.
> Risk: belum ada test e2e untuk endpoint ini.
> Saya available pair sore ini 14:00-17:00 WITA, OK?"

Konkret, scoped, ada goal + risk + availability. Itu cara minta tolong
yang efisien untuk semua pihak.

## Saat ragu

Kalau tidak yakin VERDE/GIALLO/ROSSO, **tanya tutor dulu**:

```
/agent zantara-onboarding apakah edit file X.tsx di scope saya?
```

Tutor cek perimeter, jawab dengan label + alasan. Lebih cepat dari
guessing + lebih aman.
