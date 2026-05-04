# NotebookLM (NB) Authority Guide

Bali Zero pakai NotebookLM (Google) sebagai **ground truth authority**
untuk pertanyaan domain (visa, tax, KBLI, property). Tutor sub-agent
kamu sudah punya akses read ke NB ini lewat MCP.

## Apa itu NotebookLM, ringkas

NotebookLM = Google product. Kasih dia kumpulan dokumen (PDF, markdown,
URL), dia bikin index-nya, lalu kamu bisa tanya berdasarkan dokumen itu
saja (grounded).

Contoh: NB-2 (Immigration) berisi ~50 dokumen resmi (Imigrasi RI,
KemenkumHAM, regulator). Tanya "berapa lama validitas KITAS C7?" → NB-2
jawab dengan cite dokumen sumber, BUKAN dari training data umum.

Ini lebih akurat dibanding tanya Claude / ChatGPT polos, karena polos
hallucinate aturan visa yang sering update.

## Notebook yang relevan untuk Subhi

| Notebook | Isi | Pakai untuk |
| --- | --- | --- |
| **NB-1** | Architecture deep, Symbiosis principles, EventBus, RAG | Pertanyaan teknis sistem |
| **NB-2** | Immigration: KITAS, KITAP, e-VOA, Golden Visa, Investor Visa | Validasi sebelum saran ke client visa |
| **NB-9** | Gov sources: DPMPTSP, BKPM, regulator, peraturan resmi | Validasi prosedur PT PMA, KBLI, NIB |
| **NB-OPS** | Operations Bali Zero: deploy, cron schedules, runbook | Pertanyaan operasi internal |
| **NB-4** | Tax: PPh, PPN, CoreTax, NPWP, SPT | Validasi aturan tax |
| **NB-5** | Property: Hak Pakai, freehold, sewa, PBG, sertifikat | Validasi property law |

Subhi punya read access ke semua via MCP `mcp__notebooklm-mcp__*`.

## Cara query NB via tutor

### Pattern 1: tanya tutor langsung

```
/agent zantara-onboarding query NB-2 tentang KITAS C7 duration extension
```

Tutor akan call `mcp__notebooklm-mcp__notebook_query` dengan parameter
yang sesuai, dapatkan jawaban + citation, paraphrase ke bahasa, kasih
citation source.

### Pattern 2: tanya cross-NB

```
/agent zantara-onboarding cross-check NB-9 dan NB-2: untuk PT PMA hospitality, KITAS apa yang cocok untuk direktur asing?
```

Tutor query 2 NB sekaligus, sintesis jawaban dengan citation dari
keduanya.

### Pattern 3: research mode (tugas Subhi panjang)

```
/agent zantara-onboarding saya mau bikin artikel tentang Golden Visa Indonesia 2026. Apa updates terbaru di NB-2?
```

Tutor list relevant sources di NB-2 → Subhi pilih → tutor extract content
→ Subhi tulis artikel.

## Kapan WAJIB query NB

**Sebelum** kamu kasih saran ke client (lewat Sales / Sahira) atau
tulis artikel publik tentang:

- ✅ Aturan visa / immigration → NB-2
- ✅ Aturan tax / NPWP / SPT → NB-4
- ✅ Aturan property / Hak Pakai → NB-5
- ✅ Prosedur PT PMA / KBLI → NB-9
- ✅ Peraturan terbaru pemerintah → NB-9

JANGAN asumsi dari Google atau training Claude polos. Aturan visa
Indonesia berubah cepat (e-VOA naik turun, KITAS quota, dll).

## Kapan TIDAK perlu query NB

Untuk pertanyaan generic / non-domain:

- "Bagaimana sintaks TypeScript generics?" → Pakai web/dokumentasi
- "Apa perbedaan React useState vs useReducer?" → Documentation React
- "Bagaimana cara bikin branch git?" → Tanya tutor langsung, bukan NB

NB punya cost (rate limit Google) — jangan boros pakai untuk hal trivial.

## Format jawaban tutor pakai NB

Tutor akan jawab dengan struktur:

```
[Jawaban paraphrase bahasa Indonesia]

**Sumber NB-X:**
- [Citation 1: judul dokumen, snippet relevan]
- [Citation 2: ...]
- [Citation 3: ...]

**Catatan:** [Kalau ada uncertainty / dokumen lama, tutor flag di sini]
```

Selalu **cite** sumber. Kalau Subhi paste jawaban ini ke artikel atau
WA ke client, sumber harus dipreserve untuk audit trail.

## Contoh interaksi nyata

### Contoh 1 — Subhi tulis artikel KITAS

**Subhi:** "Saya mau tulis artikel 'KITAS Investor Visa 2026: Panduan
Lengkap'. Update terbaru NB-2?"

**Tutor:** [query NB-2 dengan keyword 'KITAS Investor 2026']
"NB-2 punya 3 dokumen update 2026 untuk Investor Visa:

1. PerMen Imigrasi 22/2025 — minimum investasi naik dari $200k ke $250k
2. Surat Edaran Imigrasi 2026 — fast track 14 hari
3. FAQ Imigrasi 2026 — eligibility revisi

Mau saya extract content lengkap dari 3 dokumen ini untuk basis artikel
kamu? Saya bisa generate outline + key points dengan citation."

### Contoh 2 — Subhi cek aturan untuk distribusi

**Subhi:** "Boleh saya post artikel 'Golden Visa 2026' di group LinkedIn
tanpa disclaimer law firm?"

**Tutor:** [tidak perlu NB — tanya tentang policy internal Bali Zero]
"Subhi, ini bukan domain question — ini policy distribusi. Bali Zero
selalu **wajib** include disclaimer 'Bali Zero is not a law firm. Info
provided is for general guidance, not legal advice.' di artikel publik.

Reference: convention `apps/mouth/src/components/blog/ArticleDisclaimer.tsx`
sudah include otomatis di blog kita. Untuk re-post LinkedIn, tambah
manual di copy LinkedIn."

### Contoh 3 — Subhi research backend question

**Subhi:** "Architecture EventBus pakai Redis Streams atau PG NOTIFY?"

**Tutor:** [query NB-1 architecture]
"Berdasarkan NB-1 (citation: `services/events/__init__.py` PG_CHANNEL_MAP),
EventBus pakai **PostgreSQL LISTEN/NOTIFY**, BUKAN Redis Streams.

Catatan: SYMBIOSIS.md menulis Redis Streams, tapi itu desain awal yang
belum ter-update. Code-as-truth wins — implementasi nyata = PG.
Discrepancy ini dicatat di scar `cicatrix-scars.md` (2026-04-29 audit
zero-crash).

Buat detail lengkap channel + outbox table lihat NB-1 source `Migration
144_events_outbox.sql`."

## Mutations — JANGAN

Subhi punya read-only access ke NB. JANGAN call:

- `mcp__notebooklm-mcp__source_add` — tambah source ke NB
- `mcp__notebooklm-mcp__note_create` — buat note di NB
- `mcp__notebooklm-mcp__studio_create` — buat audio/video summary
- `mcp__notebooklm-mcp__source_delete` — hapus source

Itu prerogatif Antonello. Kalau ada source baru yang berharga (mis.
Subhi ketemu PerMen baru), kasih ke Antonello via WA, dia yang upload
ke NB.

Hook `subhi-bash-guard.sh` tidak block ini langsung (karena hook hanya
cek Bash command, bukan MCP call), tapi sub-agent prompt sudah
instruct untuk read-only. Kalau tutor coba mutation, itu bug — ping
Antonello.

## Kalau NB error / down

Kadang NotebookLM Google punya outage. Kalau tutor jawab "NB-X tidak
bisa diakses", coba:

1. Retry 1-2 kali (mungkin transient)
2. Kalau persisten, tutor fallback ke jawaban dari memory mirror (di
   `.claude/memory-mirror/`)
3. Catat ke Antonello (via WA atau standup besok)

Jangan force tutor jawab dari training generic — risiko hallucinate
aturan visa.
