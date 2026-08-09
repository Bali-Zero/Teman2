# Bali Zero WA-Mirror — Persetujuan Anggota Tim / Team Member Consent

**Versi 1.1 — 2026-08-05** (menggantikan Versi 1.0 — 2026-05-13)
**Tertulis di Bahasa Indonesia + English. Ditandatangani sebelum bridge aktif.**

> ⚠️ **Tanda tangan pada Versi 1.0 hanya berlaku untuk teks Versi 1.0.**
> Bagian "Konsekuensi jika Anda menolak" berubah secara substantif, jadi
> anggota tim yang sudah menandatangani v1.0 perlu menandatangani ulang atau
> menandatangani adendum. Hak karyawan **tidak berkurang** — pencabutan tetap
> tanpa PHK dan tanpa penalti.
>
> **Perubahan dari v1.0.** v1.0 menyebut satu nomor tertentu sebagai "nomor
> resmi Bali Zero yang diakses lewat dashboard" dan menjanjikan peralihan
> bertahap ke nomor itu. Peralihan itu tidak terjadi seperti yang
> digambarkan: sejak 2026-08-05 nomor WhatsApp publik Bali Zero adalah
> **nomor kerja milik salah satu anggota tim** yang tertaut ke CRM, bukan
> nomor terpisah milik perusahaan. Karena itu bagian tersebut ditulis ulang
> agar sesuai kenyataan, dan versi ini sengaja **tidak menyebut nomor telepon
> mana pun**, supaya dokumen tidak menjadi usang lagi ketika nomor berubah.
>
> ⚠️ **A signature on Version 1.0 covers the Version 1.0 text only.** The
> "If you decline" section changed substantively, so team members who already
> signed v1.0 need to re-sign or sign an addendum. No employee right is
> narrowed — revocation still carries no termination and no penalty.
>
> **Change from v1.0.** v1.0 named one specific number as "the official Bali
> Zero number accessed via dashboard" and promised a gradual move onto it.
> That move did not happen as described: since 2026-08-05 the public Bali Zero
> WhatsApp number is **a team member's own work line** linked to the CRM, not
> a separate company-held number. That section is therefore rewritten to match
> reality, and this version deliberately **names no phone number at all**, so
> the document cannot go stale again the next time the number moves.

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

- Pesan masuk/keluar untuk chat satu-lawan-satu pada akun kerja yang
  dikonfigurasi. Jika nomor lawan bicara ada di tabel `clients` Bali Zero,
  pesan ditautkan ke klien/practice. Jika belum ada, pesan tetap disimpan
  sebagai prospect/lead dengan `client_id=NULL`.
- Tanggal, waktu, isi teks, lampiran media (foto akta, paspor, dll. yang sudah
  jadi bagian alur kerja KITAS/PMA).

### Apa yang TIDAK DICATAT sistem

- Group chat, status/story, dan panggilan suara/video. Untuk chat
  satu-lawan-satu, nomor yang belum cocok dengan CRM tidak dibuang karena bisa
  menjadi prospect/lead Bali Zero.
- Daftar kontak Anda. Sistem tidak menyentuh phonebook Anda.
- Status, story, panggilan suara/video.

### Hak Anda

1. **Cabut kapan saja**: WhatsApp → Pengaturan → Perangkat Tertaut → tap
   "Bali Zero WA-Mirror" → Keluar. Sesi mati dalam 5 detik. Tidak ada data
   yang ditarik dari ponsel Anda setelah pemutusan.
2. **Akses data**: Anda berhak melihat semua baris di
   `whatsapp_message_context` yang `team_member_phone = nomor Anda`. Kirim
   email ke zero@balizero.com, dalam 7 hari kerja Anda menerima ekspor JSON.
3. **Penghapusan** (UU PDP art. 17): jika Anda keluar dari Bali Zero, semua
   sesi Anda otomatis dihapus dalam 30 hari setelah surat keluar resmi.
   Pesan historis terkait klien tetap di CRM karena tergolong "data klien
   Bali Zero", bukan data pribadi Anda.

### Yang TIDAK boleh dilakukan oleh Bali Zero / Antonello

- Menggunakan pesan prospect/non-klien di luar kebutuhan bisnis Bali Zero.
  Semua akses tetap melalui RBAC dan audit trail.
- Memberikan akses ke pesan Anda kepada anggota tim lain yang tidak terkait
  klien yang sama. RBAC: Surya melihat pesan klien yang dia tangani; Adit
  melihat pesan klien yang dia tangani; Antonello (owner) melihat semua
  pesan klien.
- Menggunakan isi pesan untuk evaluasi non-profesional (mis. menilai gaya
  bicara pribadi Anda).

### Konsekuensi jika Anda menolak

Tidak ada konsekuensi PHK atau penalti, dan penolakan tidak dicatat sebagai
penilaian kinerja.

Yang terjadi hanyalah ini: percakapan Anda dengan klien tidak masuk ke CRM,
sehingga tidak ada jejak layanan ketika Anda cuti, sakit, atau berhalangan.
Untuk menjaga kelangsungan layanan, Bali Zero dapat mengalihkan klien yang
Anda tangani kepada rekan kerja yang nomor kerjanya tertaut, atau ke nomor
bisnis Bali Zero yang dikelola melalui dashboard. Pengalihan itu menyangkut
klien, bukan status kepegawaian Anda.

### Tanda tangan

**Versi dokumen yang ditandatangani: 1.1 (2026-08-05)** — tulis nomor versi ini
pada salinan yang Anda tanda tangani, supaya di kemudian hari jelas teks mana
yang Anda setujui.

Nama: `______________________________`

Tanggal: `______________________________`

Tanda tangan: `______________________________`

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

- Inbound/outbound one-to-one messages on configured work accounts. If the
  counterpart number exists in the Bali Zero `clients` table, the message is
  linked to that client/practice. If it does not match yet, the message is
  still stored as a prospect/lead with `client_id=NULL`.
- Date, time, text content, media attachments (photos of akta, passport, etc.
  that are already part of the KITAS/PMA workflow).

### What the system does NOT log

- Group chats, status/stories, and voice/video calls. For one-to-one chats,
  an unmatched CRM number is not discarded because it may be a Bali Zero
  prospect/lead.
- Your contact list. The system does not touch your phonebook.
- Status, stories, voice/video calls.

### Your rights

1. **Revoke at any time**: WhatsApp → Settings → Linked Devices → tap
   "Bali Zero WA-Mirror" → Log out. Session dies within 5 seconds. No
   data is pulled from your phone post-disconnect.
2. **Data access**: you have the right to see all rows in
   `whatsapp_message_context` where `team_member_phone = your number`.
   Email zero@balizero.com, you receive a JSON export within 7 business
   days.
3. **Deletion** (UU PDP art. 17): when you leave Bali Zero, all your
   sessions are automatically deleted within 30 days of your official
   resignation letter. Historical client-related messages remain in the
   CRM because they qualify as "Bali Zero client data", not your personal
   data.

### What Bali Zero / Antonello may NOT do

- Use prospect/non-client messages outside Bali Zero business needs. All
  access still goes through RBAC and audit trail.
- Grant access to your messages to other team members not associated with
  the same client. RBAC: Surya sees messages of clients he handles;
  Adit sees messages of clients he handles; Antonello (owner) sees all
  client messages.
- Use message content for non-professional evaluation (e.g. judge your
  personal communication style).

### If you decline

No PHK / no penalty, and declining is not recorded as a performance
judgement.

What happens is only this: your conversations with clients do not reach the
CRM, so there is no service trail when you are on leave, sick, or otherwise
unavailable. To keep service continuous, Bali Zero may reassign the clients
you handle to a colleague whose work number is linked, or to the Bali Zero
business number managed through the dashboard. That reassignment concerns
clients, not your employment status.

### Signature

**Document version signed: 1.1 (2026-08-05)** — write this version number on
the copy you sign, so it stays clear later which text you agreed to.

Name: `______________________________`

Date: `______________________________`

Signature: `______________________________`
