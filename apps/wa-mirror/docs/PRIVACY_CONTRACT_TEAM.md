# Bali Zero WA-Mirror — Persetujuan Anggota Tim / Team Member Consent

**Versi 1.0 — 2026-05-13**
**Tertulis di Bahasa Indonesia + English. Ditandatangani sebelum bridge aktif.**

---

## Bahasa Indonesia

### Apa yang akan terjadi

Nomor WhatsApp pribadi yang Anda gunakan untuk bekerja di Bali Zero akan
dihubungkan ke sistem internal Bali Zero (kita.balizero.com) melalui fitur
"Perangkat Tertaut" / Linked Devices yang sudah ada di WhatsApp. Tujuannya:
percakapan dengan klien Bali Zero tercatat otomatis di CRM, sehingga
(a) ada jejak audit untuk kepatuhan UU PDP 27/2022,
(b) ketika Anda cuti / sakit / pindah, klien tetap terlayani karena percakapan
sudah ada di sistem,
(c) kualitas layanan terukur untuk semua anggota tim.

### Apa yang DICATAT sistem

- Pesan masuk/keluar **hanya** ketika nomor lawan bicara terdaftar di tabel
  `clients` Bali Zero (klien yang sudah pernah memberikan nomor ke kami).
- Tanggal, waktu, isi teks, lampiran media (foto akta, paspor, dll. yang sudah
  jadi bagian alur kerja KITAS/PMA).

### Apa yang TIDAK DICATAT sistem

- Percakapan dengan keluarga, teman, vendor, ojol, ojek, restoran, atau siapa
  pun yang TIDAK terdaftar sebagai klien Bali Zero. Server menghapus pesan
  tersebut dalam beberapa milidetik tanpa menyimpannya. Yang dicatat hanya
  hitungan numerik ("X pesan terfilter hari ini") untuk metrik kapasitas
  server, tanpa isi.
- Daftar kontak Anda. Sistem tidak menyentuh phonebook Anda.
- Status, story, panggilan suara/video.

### Hak Anda

1. **Cabut kapan saja**: WhatsApp → Pengaturan → Perangkat Tertaut → tap
   "Bali Zero WA-Mirror" → Keluar. Sesi mati dalam 5 detik. Tidak ada data
   yang ditarik dari ponsel Anda setelah pemutusan.
2. **Akses data**: Anda berhak melihat semua baris di
   `whatsapp_message_context` yang `team_member_email = email Anda`. Kirim
   email ke zero@balizero.com, dalam 7 hari kerja Anda menerima ekspor JSON.
3. **Penghapusan** (UU PDP art. 17): jika Anda keluar dari Bali Zero, semua
   sesi Anda otomatis dihapus dalam 30 hari setelah surat keluar resmi.
   Pesan historis terkait klien tetap di CRM karena tergolong "data klien
   Bali Zero", bukan data pribadi Anda.

### Yang TIDAK boleh dilakukan oleh Bali Zero / Antonello

- Membaca pesan yang difilter (non-klien). Filter dijalankan di server,
  Antonello tidak punya tombol "lihat semua, bypass filter". Jika ada bug
  yang menyebabkan pesan non-klien tertulis ke CRM, itu insiden yang harus
  dilaporkan dan diperbaiki dalam 24 jam.
- Memberikan akses ke pesan Anda kepada anggota tim lain yang tidak terkait
  klien yang sama. RBAC: Surya melihat pesan klien yang dia tangani; Adit
  melihat pesan klien yang dia tangani; Antonello (owner) melihat semua
  pesan klien.
- Menggunakan isi pesan untuk evaluasi non-profesional (mis. menilai gaya
  bicara pribadi Anda).

### Konsekuensi jika Anda menolak

Tidak ada konsekuensi PHK atau penalti. Namun ke depan, Bali Zero akan secara
bertahap meminta semua komunikasi klien dilakukan via nomor resmi Bali Zero
(+62 821 31 07 363) yang diakses via dashboard, bukan via nomor pribadi.
Penolakan saat ini = transisi lebih cepat ke nomor resmi untuk Anda.

### Tanda tangan

Nama: ______________________________

Tanggal: ___________________________

Tanda tangan: ______________________

---

## English

### What will happen

Your personal WhatsApp number that you use for Bali Zero work will be
connected to the Bali Zero internal system (kita.balizero.com) via the
existing "Linked Devices" feature of WhatsApp. Goal:

- conversations with Bali Zero clients are auto-logged in the CRM, giving
  (a) audit trail for UU PDP 27/2022 compliance,
  (b) continuity when you are on leave / sick / move on — clients are
  served because the conversation is already in the system,
  (c) measurable service quality across the team.

### What the system DOES log

- Inbound/outbound messages **only** when the counterpart's number is
  registered in the Bali Zero `clients` table (clients who previously gave
  us their number).
- Date, time, text content, media attachments (photos of akta, passport, etc.
  that are already part of the KITAS/PMA workflow).

### What the system does NOT log

- Conversations with family, friends, vendors, ojol, restaurants, or anyone
  NOT registered as a Bali Zero client. The server discards those messages
  in milliseconds without storing them. Only a numeric count is logged
  ("X messages filtered today") for server capacity metrics, no content.
- Your contact list. The system does not touch your phonebook.
- Status, stories, voice/video calls.

### Your rights

1. **Revoke at any time**: WhatsApp → Settings → Linked Devices → tap
   "Bali Zero WA-Mirror" → Log out. Session dies within 5 seconds. No
   data is pulled from your phone post-disconnect.
2. **Data access**: you have the right to see all rows in
   `whatsapp_message_context` where `team_member_email = your email`.
   Email zero@balizero.com, you receive a JSON export within 7 business
   days.
3. **Deletion** (UU PDP art. 17): when you leave Bali Zero, all your
   sessions are automatically deleted within 30 days of your official
   resignation letter. Historical client-related messages remain in the
   CRM because they qualify as "Bali Zero client data", not your personal
   data.

### What Bali Zero / Antonello may NOT do

- Read filtered (non-client) messages. The filter runs server-side.
  Antonello does NOT have a "show all, bypass filter" button. If a bug
  causes non-client messages to be written to the CRM, that is an
  incident to be reported and fixed within 24 hours.
- Grant access to your messages to other team members not associated with
  the same client. RBAC: Surya sees messages of clients he handles;
  Adit sees messages of clients he handles; Antonello (owner) sees all
  client messages.
- Use message content for non-professional evaluation (e.g. judge your
  personal communication style).

### If you decline

No PHK / no penalty. However, going forward, Bali Zero will gradually
require all client communications to happen via the official Bali Zero
number (+62 821 31 07 363) accessed via dashboard, not via personal
numbers. Declining today = faster transition to the official number for you.

### Signature

Name: ______________________________

Date: ______________________________

Signature: __________________________
