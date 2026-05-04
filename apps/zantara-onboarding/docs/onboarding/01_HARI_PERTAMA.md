# Hari Pertama — Walkthrough

**Tanggal:** Hari pertama kamu di kantor Kuta
**Estimasi total:** Setengah hari (09:30 datang, 13:00 pulang siang)

## Yang kamu bawa hari ini

- MacBook Pro 16GB (yang Antonello kasih, kalau belum ada — pinjam dulu)
- Charger MacBook
- Buku catatan (kertas) + pen — bukan gadget tambahan, untuk note manual
- ID/KTP (untuk verifikasi setup akun internal kalau perlu)

Yang **tidak** perlu: pengetahuan codebase. Hari ini kita setup tools dan
baca dokumentasi. Coding mulai Hari 2.

## Jadwal hari ini

### 09:30 — Datang ke kantor

Alamat kantor: Kuta. Lokasi persisnya Antonello kirim via WhatsApp
sehari sebelum.

Kalau telat (macet, hujan, dll), kirim WA ke Antonello — bukan soal
disiplin, soal komunikasi. Telat tidak masalah, telat tanpa kabar masalah.

### 09:35 — Salam tim

Beberapa anggota tim hadir di kantor:

- **Asya** — Platform/Backend (pair coding kamu untuk hal GIALLO)
- **Adit** — Operations / Welcome
- **Sahira** — Sales/WhatsApp (lead handoff)
- Mungkin **Antonello** sendiri (boss)

Cukup salam, perkenalan singkat. Detail kerja bareng nanti.

### 09:40 — Setup MacBook

Antonello (atau Subhi sendiri kalau lebih nyaman) buka:

```
exercises/day1_setup_check.md
```

Run install script (gist URL Antonello kasih), tunggu ~15-20 menit.
Bisa minum kopi. Selama install:

- Login Tailscale (browser akan terbuka)
- Login Claude Code OAuth (browser akan terbuka — pakai akun MAX yang
  Antonello provision)
- Login NLM (browser akan terbuka — pakai subhi@balizero.com)

### 10:00 — Test tutor pertama

Setelah install selesai, di terminal:

```bash
cd ~/zantara-onboarding
claude
```

Lalu di Claude session:

```
/agent zantara-onboarding halo, perkenalkan diri
```

Tutor harus jawab dalam Bahasa Indonesia. Kalau jawab Inggris atau Italia,
ada bug di setup — ping Antonello.

### 10:15 — Baca dokumentasi inti

Urutan baca (bisa di VSCode side-by-side dengan Claude):

1. `docs/onboarding/00_SELAMAT_DATANG.md` (5 menit)
2. `docs/onboarding/02_RBAC_BAHASA.md` (10 menit)
3. `docs/onboarding/03_TASK_ROUTING_BAHASA.md` (10 menit)
4. `docs/onboarding/07_60_DAY_MISSION_BAHASA.md` (45-60 menit — ini yang panjang)

Tidak masalah kalau tidak hafal. Tujuan: tahu **di mana** mencari kalau
butuh.

### 11:00 — Daily standup pertama

Kantor Kuta, 09:00 WITA setiap hari kerja (Senin-Jumat). Hari pertama
kamu: 11:00, jadwal khusus Day 1 supaya kamu sudah setup.

Format standup:

- **Ieri** (kemarin): apa yang dikerjakan
- **Oggi** (hari ini): apa yang akan dikerjakan
- **Blocker**: apa yang menghambat

3-5 menit per orang. Hari pertama kamu cukup bilang:

> "Hari ini setup tools, baca dokumentasi, mulai exercise Day 1."

### 11:30 — Lanjut baca + tanya tutor

Setelah standup, lanjut baca dokumentasi yang belum selesai. Tanya
tutor kapan saja:

- "Apa itu KBLI?"
- "Apa beda VERDE dan ROSSO?"
- "Kenapa harus pakai branch sancho/*?"
- "Apa misi 60 hari saya, ringkas dalam 5 poin?"

Tutor selalu jawab bahasa.

### 12:30 — Review dengan Antonello

Antonello cek:

- Tutor jalan? (screenshot bukti reply bahasa)
- Sudah baca 07_60_DAY_MISSION? (kasih ringkasan 1 paragraf bahasa)
- Ada blocker? (jujur — tidak tahu sesuatu = OK, tapi bilang)

### 13:00 — Pulang siang

Hari pertama selesai. Besok mulai Day 2: `exercises/day2_codebase_tour.md`.

## Yang TIDAK perlu kamu lakukan hari ini

- Tidak perlu hafal semua perimeter
- Tidak perlu paham backend architecture
- Tidak perlu commit code apapun
- Tidak perlu kenal seluruh tim
- Tidak perlu paham 1.563 KBLI codes

Hari ini fokus: **setup + baca + tanya**.

## Mood

Tidak usah tegang. Probation 90 hari berarti kamu punya waktu. Hari
pertama tujuannya cuma satu: pulang dengan tools yang jalan dan
gambaran kasar tentang misi.
