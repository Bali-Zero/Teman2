# FAQ — Pertanyaan yang sering ditanya Subhi

Daftar Q&A untuk hal yang biasanya membingungkan minggu pertama.
Tutor juga bisa jawab semua ini — FAQ ini cuma referensi cepat.

## Setup + tools

### Apa beda repo onboarding (`~/zantara-onboarding/`) vs main repo (`~/Projects/nuzantara/`)?

- **Onboarding** (`~/zantara-onboarding/`): direktori statik, isi config
  Claude Code + dokumentasi bahasa + exercise harian. **Bukan repo git
  kamu** — di-update via rsync dari Pro Antonello tiap pagi 04:00 WITA.
  Kamu tidak commit di sini.
- **Main repo** (`~/Projects/nuzantara/`): clone repo `balizero/nuzantara`.
  Ini di mana kamu kerja, edit code, push ke `sancho/*` branch, buka PR.

Tutor kamu hidup di `~/zantara-onboarding/`. Code real ada di
`~/Projects/nuzantara/`.

### Kenapa onboarding tidak repo git sendiri?

Pertimbangan privacy + simplicity. Memori Bali Zero (lessons, scar,
project memo) sensitif → tidak boleh di repo public/private GitHub
yang Subhi solo punya akses. Tailscale tailnet Pro→Subhi sudah ada,
rsync over Tailscale = solusi paling aman + simple.

Lihat `docs/superpowers/specs/2026-05-04-subhi-tutor-design-addendum-B.md`
di main repo untuk decision rationale.

### Kenapa file-file `~/zantara-onboarding/` ketimpa setiap pagi?

Karena Antonello update memo / lesson / project di Pro tiap hari, dan
rsync push ke MacBook Subhi 04:00 WITA. Kalau Subhi edit file di
`~/zantara-onboarding/` (mis. catatan pribadi), bakal hilang di rsync
berikutnya.

Untuk catatan pribadi: simpan di `~/zantara-onboarding/local/` —
folder ini di-exclude dari rsync.

### Saya tidak ada di kantor, gimana standup?

Standup default di kantor Kuta jam 09:00 WITA. Kalau remote (sakit /
WFH approved):

1. Async via WA group "Bali Zero Standup" (Antonello tambah kamu Day 1)
2. Format: "Ieri: [...]. Oggi: [...]. Blocker: [...]" — text only
3. Kirim sebelum jam 09:00 WITA — biar tim baca pas standup live
4. Tetap respon kalau ada yang tag kamu

Default kantor Kuta. Remote occasional OK, full remote tidak.

### Tutor tidak jawab dalam Bahasa Indonesia, gimana?

Bug. Kemungkinan:

1. Sub-agent prompt salah load — restart Claude session, retry
2. Kamu CWD bukan di `~/zantara-onboarding/` — `cd ~/zantara-onboarding/`
   dulu lalu `claude`
3. Sub-agent terhapus / di-override — ping Antonello, dia restore

Tutor seharusnya selalu jawab bahasa, even kalau Subhi tanya English.
Kalau tidak: bug.

### `claude` command tidak ditemukan setelah install

Re-source shell config:

```bash
source ~/.zshrc
```

Kalau masih: re-install:

```bash
npm install -g @anthropic-ai/claude-code
```

Kalau npm tidak ada: install Node.js dulu via brew:

```bash
brew install node@20
```

## Workflow + git

### Saya lupa naming branch, bikin `feature/whatever`. Gimana fix?

```bash
# Rename branch local
git branch -m feature/whatever sancho/whatever

# Kalau sudah push:
# Push branch baru:
git push origin sancho/whatever
# Hapus branch lama remote:
git push origin --delete feature/whatever

# Reset upstream:
git push -u origin sancho/whatever
```

Atau lebih simple: `git stash`, `git checkout -b sancho/whatever`,
`git stash pop`, commit ulang.

### Saya commit ke main langsung. Gimana?

Hook block kebanyakan kasus, tapi kalau lolos:

1. Branch out:

```bash
git checkout -b sancho/recovery
git push origin sancho/recovery
```

2. Reset main local (HATI-HATI):

```bash
git checkout main
git reset --hard origin/main  # JANGAN kalau ada commit Subhi yang penting
```

3. WA Antonello — dia mungkin perlu force-protect main lagi

### PR saya menumpuk, conflict dengan main. Gimana?

Rebase:

```bash
git checkout sancho/<task-slug>
git fetch origin
git rebase origin/main

# Resolve conflict di file (open editor manual)
git add <resolved-files>
git rebase --continue

# Force push (allowed di sancho/ branch sendiri)
git push --force-with-lease origin sancho/<task-slug>
```

`--force-with-lease` lebih aman dari `--force` raw — fail kalau ada
push barusan dari orang lain.

### Berapa lama PR saya akan di-review?

Antonello target: <24 jam first review (kalau working day).

Kalau lewat 24 jam: ping WA, "Boss, PR #234 ready for review when ada
waktu, ada blocker?"

Yang TIDAK boleh: nudge tiap jam, atau merge sendiri.

### Saya bisa merge PR sendiri kalau Antonello unreachable >3 hari?

**Tidak**, dalam 30 hari pertama. Probation aturan keras.

Kalau Antonello unreachable >3 hari:

1. Hubungi Asya — dia mungkin punya context / authority
2. Tahan PR, kerjakan task lain (yang tidak dependent)
3. Jangan blocking semua progress di 1 PR

Setelah 30 hari, evaluasi case-by-case.

## Codebase + tools

### Saya pakai Copilot bareng Claude, OK?

Boleh, tapi **tidak paste secret / code production ke Copilot free /
ChatGPT free**. Risiko data leak.

Claude Code (yang kamu pakai sekarang) OK karena ada agreement Anthropic
+ kamu pakai MAX subscription Bali Zero.

### Boleh saya install npm package baru?

Cek dulu:

1. Sudah ada serupa di codebase? (search dengan tutor / VSCode search)
2. Maintainer aktif? (cek github npm page)
3. Lisensi compatible? (MIT, Apache OK; GPL, AGPL — ping Antonello)
4. Audit security: `npm audit` setelah install

Kalau OK semua: `npm install <pkg>` di branch `sancho/*`, commit
`package.json` + `package-lock.json`. PR review akan double-check.

### Test e2e gagal di CI, lokal pass. Gimana?

CI biasanya beda environment (Linux VM, env vars, dll). Cek:

1. `.github/workflows/<workflow>.yml` — CI command yang dipakai
2. Run command yang sama lokal: misal `CI=true npm run test:e2e`
3. Cek log CI untuk error message exact

Kalau fail di CI persisten, kemungkinan:

- Race condition (test depend on timing)
- Environment-specific (process.env vars)
- File path case-sensitivity (macOS case-insensitive, Linux sensitive)

Tutor bantu debug step-by-step.

### Saya butuh data CRM live untuk testing. Boleh?

Tidak, scope ROSSO. Solusi:

1. Mock data di test (Playwright fixture, MSW, dll)
2. Staging environment kalau ada
3. Pair sama Asya — dia provide test data sintetik

NEVER copy production CRM data ke local untuk "test cepat".

### Saya rusak production deploy. Gimana?

Pertama: jangan panik, deploy biasanya bisa di-rollback dalam menit.

1. Stop apa yang kamu lakukan
2. WA Antonello + Asya immediately, deskripsikan apa yang terjadi
3. Mereka rollback via Fly CLI (kamu tidak punya akses, tidak masalah)
4. Post-mortem: tulis 1-page apa yang salah, apa yang dipelajari
5. Pattern ini = "blameless postmortem" — bukan untuk hukum, untuk learn

Probation tidak otomatis fail kalau rusak satu kali. Yang fail: tidak
komunikasi atau coba sembunyikan.

## Domain knowledge

### Apa itu KITAS / KITAP / e-VOA?

Tutor query NB-2 ke kamu. Singkatnya:

- **e-VOA** (e-Visa on Arrival): visa tourist 30 hari, bisa extend
  sekali jadi 60 hari
- **KITAS**: Kartu Izin Tinggal Terbatas — visa kerja / bisnis 1-2 tahun
- **KITAP**: Kartu Izin Tinggal Tetap — permanent residency

Tipe-tipe KITAS: C7 (investor), B211 (visit), C1 (tourist single entry),
dll. Detail di NB-2.

### Apa itu KBLI?

Klasifikasi Baku Lapangan Usaha Indonesia — sistem klasifikasi 1.563
kode untuk kategorisasi bisnis. Setiap PT PMA harus pilih KBLI yang
sesuai aktivitas mereka. Bali Zero punya KBLI Navigator di
`apps/mouth/src/app/kbli/` — UX-nya scope VERDE Subhi, tapi data model
1.563 codes scope ROSSO.

### Apa beda PT PMA dan PT lokal?

- **PT PMA**: Penanaman Modal Asing — perusahaan dengan minimum 1 saham
  dimiliki investor asing
- **PT lokal**: Penanaman Modal Dalam Negeri — 100% saham dimiliki WNI

Mostly Bali Zero gestire PT PMA (klien expat). NB-9 untuk detail
prosedur.

### Apa itu CoreTax?

Sistem pajak Indonesia versi terbaru (2025+) — DJP. Replaced sistem
lama. Bali Zero ada router `apps/backend-rag/backend/app/routers/coretax.py`.
Detail aturan di NB-4.

## Saturday-Sunday — istirahat

### Hari Sabtu / Minggu, ada exercise?

Tidak. Day 6 (Sabtu) + Minggu = istirahat. Probation 90 hari, kerja
hari Senin-Jumat aja.

Kalau Subhi pengen review materi atau eksplor codebase weekend, OK,
tapi tidak ada deliverable wajib.

Day 7 exercise (`day7_money_pages_pick.md`) di-jadwal hari Senin
minggu kedua.

### Boleh saya cek WA balas client weekend?

Bukan tugas Subhi. WA inbound client di-handle Sahira (Sales) +
team operasi. Kamu fokus organic growth surface, weekend = off.

Kalau ada urgent yang Antonello forward ke kamu, OK respond. Kalau
tidak, weekend = istirahat.

## Salam

Selamat onboarding! Kalau ada pertanyaan yang tidak ada di sini,
tanya tutor:

```
/agent zantara-onboarding saya bingung tentang X
```

Atau langsung WA Antonello kalau urgent. Lebih baik tanya cepat
daripada stuck sendirian.
