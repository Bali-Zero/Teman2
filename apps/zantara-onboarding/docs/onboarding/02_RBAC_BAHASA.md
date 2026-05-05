# RBAC — Akses Subhi (90 Hari Probation)

**Periode:** 2026-04-30 → 2026-07-29 (90 hari)
**Track:** Operator → Builder → Rekan
**Reference:** memory `subhi-rbac-permissions.md` Antonello

## Filosofi (penting — baca dulu)

Kamu **developer senior** dengan akses **READ penuh**: seluruh codebase
Nuzantara, NotebookLM authority (NB-1, NB-2, NB-9, NB-OPS), memory mirror
sistem Bali Zero, lessons & cicatrix. Tutor (`/agent zantara-onboarding`)
akan jawab pertanyaan teknis sedalam apa pun — RAG architecture, Qdrant,
cell/genome, EventBus, deploy flow, semua.

Yang dibatasi adalah **WRITE/EXECUTE di luar sandbox sancho/*** dan
**akses langsung ke production**. Kamu kerja di sandbox (clone repo
lokal), bikin perubahan di branch `sancho/<task>`, commit, push, open PR.
Antonello + Asya review, lalu deploy.

Bukan karena kamu tidak mampu — tapi karena 5000 client live + cicatrix
sejarah (lihat `~/zantara-onboarding/.claude/memory-mirror/lessons.md`)
butuh review process untuk blast-radius control. Standar sama untuk
semua dev di Bali Zero.

Dokumen ini menjelaskan apa yang **boleh** dan **tidak boleh** kamu akses
selama probation. Bukan untuk takut-takutan — biar kamu tahu di mana
batas-batas otonom kamu, dan di mana harus minta tolong.

## GitHub `balizero/nuzantara`

| Resource | Akses | Catatan |
| --- | --- | --- |
| Read all branches | ✅ | Kamu collaborator |
| Push ke `sancho/*` | ✅ | Pattern restricted via branch protection |
| Push ke `main` | ❌ | Branch protection aktif |
| Push ke `feat/*`, `fix/*` (cabang dev lain) | ❌ | Hanya pemilik cabang |
| Open PR | ✅ | PR review wajib oleh Antonello |
| Merge PR | ❌ 30 hari pertama | Setelah hari ke-30, evaluasi case-by-case |
| Force push | ❌ | Tidak pernah, di branch manapun |
| Repo settings | ❌ | |
| Secrets / Actions secrets | ❌ | |

Konvensi branch: `sancho/<deliverable>-<short-desc>` (mis.
`sancho/d1-funnel-tracking-fix`).

## CRM (`my.balizero.com` + backend)

| Endpoint | Akses |
| --- | --- |
| `GET /api/clients/` | ❌ Subhi tidak gestire pratiche |
| `GET /api/clients/{id}` (assigned saja) | ❌ Tidak ada assignment di Subhi |
| `POST/PUT/DELETE /api/clients/*` | ❌ |
| `GET /api/practices/` | ❌ |
| `GET /api/admin/team-activity/*` | ❌ |
| `GET /api/analytics/dashboard` | ✅ read (saat ini HTTP 500, fix Damar) |
| `GET /api/analytics/queries` | ✅ read |
| `GET /api/notifications/send-email` | ❌ Hanya admin |
| `/admin/*` UI | ❌ |

Reference: CLAUDE.md project §9 CRM RBAC. Admin (zero@,
antonellosiano@, asya@balizero.com) → semua. Tim → hanya `assigned_to`
matches. Subhi bukan admin, bukan assignee → read-only di endpoint
analytics saja.

## GA4 + Search Console + Vercel

| Service | Role |
| --- | --- |
| GA4 property 505466833 (balizero.com) | viewer |
| Search Console balizero.com | viewer |
| Search Console kita.balizero.com | viewer (kalau perlu) |
| Vercel project mouth | viewer |
| Vercel deployment logs | viewer |
| Vercel env vars | ❌ |
| Vercel domain settings | ❌ |

Invitasi via Google admin / Vercel dashboard (manual UI dari Antonello).

## Fly.io

| Resource | Akses |
| --- | --- |
| Read deploy logs (dashboard) | ❌ |
| `fly ssh console` | ❌ |
| Secrets | ❌ |
| Postgres / Qdrant production | ❌ |

Subhi tidak menyentuh Fly.io. Kalau perlu data production, request ke
Asya/Antonello.

Hook `subhi-bash-guard.sh` blok command `fly` di Bash level.

## Workspace / Email

| Resource | Akses |
| --- | --- |
| `subhi@balizero.com` Zoho | ✅ owner kotak masuk sendiri |
| Send-as alias `zantara@balizero.com` | ❌ Hanya backend untuk email otomatis |
| Google Workspace shared drives Bali Zero | viewer (need-to-know basis) |
| Google Calendar Bali Zero shared | viewer |

## Pro / Air machine (Antonello)

| Machine | Akses |
| --- | --- |
| `ssh pro` | ❌ Subhi tidak punya SSH key di Pro |
| `ssh air` | ❌ |
| Cron LaunchAgents Pro | ❌ |
| `~/.cron-agent-python/` | ❌ |

Subhi kerja dari MacBook pribadi. Kalau perlu cron, propose desain ke
Antonello, dia yang setup di Pro.

## NotebookLM

| Notebook | Akses |
| --- | --- |
| NB-OPS, NB-1, NB-2..NB-10 (operativi) | ✅ read (via tutor MCP) |
| NB-INTEL family | ✅ read |
| MATA GARUDA (5 NB) | ✅ read |
| NB-SUBHI (kalau dibuat) | ✅ owner/editor |
| Mutations (`source_add`, `note_create`, `studio_create`) | ❌ Hanya via Antonello |

Full read access NB sudah granted via tutor sub-agent (Livello C tutor
design). Subhi baca ground truth langsung saat onboarding. Mutations
tetap dilarang. Rasionalnya: nilai tutor adalah jawaban grounded —
tanpa NB read tutor cuma chatbot generik.

## Claude Code OAuth

Subhi punya **Claude Pro subscription sendiri** (akun email kamu, terpisah
dari 3 plan MAX Antonello). Token OAuth disimpan di Keychain MacBook Subhi.

JANGAN PERNAH:

- Share token dengan siapa pun
- Pakai token Antonello atau orang lain
- Commit token ke git
- Paste token ke Slack/WA/Email

Kalau token bocor (mis. screenshot tidak sengaja, share file): segera
ping Antonello, rotasi token bersama.

## Yang berubah pasca probation (2026-07-30+)

### Kalau konversi disetujui

- Email send-as `zantara@balizero.com`: evaluasi per-case
- Self-merge PR: ya, di pattern `sancho/*` dengan review otomatis hijau
- Vercel write: deploy preview ya, production tidak
- Backend: pair dengan Asya, write di feature branch
- HR table: insertion (`hr_employees`, leave balances) muncul

### Kalau konversi ditolak

- Off-boarding bersih:
  - Revoca akses GitHub
  - Email Zoho dinonaktifkan
  - GA4/GSC viewer dicabut
- Repo access via `git log` tetap ada — tidak ada force-rewrite history.
  Kontribusi sancho/* yang sudah di-merge tetap terdaftar atas nama Subhi.

## Pertanyaan yang sering muncul

**T: Saya tidak sengaja edit file ROSSO. Bagaimana?**
J: Tidak ada masalah selama belum commit. Tutor + hook akan blok di
banyak titik. Kalau tetap ter-commit, jangan push — `git restore <file>`
untuk reset. Kalau sudah push, langsung WA Antonello.

**T: Boleh saya share screenshot codebase ke teman?**
J: Tidak. Codebase Bali Zero NDA-protected. Tunjukkan ke siapa pun di
luar tim = pelanggaran.

**T: Boleh saya pakai ChatGPT/Copilot bareng Claude?**
J: Boleh, tapi tidak paste secret/code production ke layanan eksternal
yang tidak Bali Zero (mis. ChatGPT free tier). Claude Code Pro kamu OK
karena official + akun atas nama kamu sendiri.

**T: Saya kerja remote sehari, OK?**
J: OK occasional. Default kantor Kuta. Komunikasi via WA + standup
async kalau remote.
