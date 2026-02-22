# 📋 PANDUAN SEDERHANA UNTUK ASYA

## Langkah-langkah Kerja (Workflow)

---

### 📌 STATUS 1: WAITING DOCUMENTS

**Kapan:** Klien belum upload semua dokumen

**Yang Asya lakukan:**

- Tunggu saja
- Tidak perlu action

---

### 📌 STATUS 2: SENDING INVOICE ⭐

**Kapan:** Leader pilih status ini

**Yang terjadi OTOMATIS:**

- ✅ Invoice PDF dibuat
- ✅ Email ke klien (dengan invoice)
- ✅ Email ke Asya (notifikasi)

**Yang Asya lakukan:**

1. Cek email di inbox
2. Follow up klien via WhatsApp untuk bayar
3. Tunggu pembayaran masuk

---

### 📌 STATUS 3: WAITING PAYMENT 💳

**Kapan:** Invoice sudah dikirim, menunggu bayar

**Yang Asya lakukan:**

1. Follow up klien via WhatsApp
2. Cek rekening
3. Kalau sudah bayar → ganti status ke **ON PROCESS**

---

### 📌 STATUS 4: ON PROCESS 🚀

**Kapan:** Asya ganti status setelah klien bayar

**Yang terjadi OTOMATIS:**

- ✅ Email ke Team Leader: "Mulai kerja sekarang!"
- ✅ Email ke klien: "Pembayaran diterima, proses dimulai"

**Yang Asya lakukan:**

- Tidak perlu action
- Proses sudah jalan ke Team Leader

---

### 📌 STATUS 5-7: Lanjutan

- `SUBMITTED TO GOV` → Dokumen ke pemerintah
- `APPROVED` → Disetujui
- `COMPLETED` → Selesai

---

## 🔔 Email yang Asya Terima

Asya akan dapat email ketika:

1. **Invoice dikirim** (ada klien baru bayar)
2. **Notifikasi sistem** (kalau ada error)

Email dikirim ke: **asya@balizero.com**

---

## 🖥️ Cara Ganti Status

1. Buka: https://zantara-crm.vercel.app/process
2. Klik nama klien/proses
3. Klik tombol **EDIT** (pojok kanan atas)
4. Pilih dropdown **STATUS**
5. Pilih status baru
6. Klik **SAVE**

---

## 📱 Ringkasan WhatsApp

| Status            | WhatsApp ke Klien?          |
| ----------------- | --------------------------- |
| WAITING DOCUMENTS | ❌ Tidak                    |
| SENDING INVOICE   | ✅ Ya (follow up bayar)     |
| WAITING PAYMENT   | ✅ Ya (ingatkan bayar)      |
| ON PROCESS        | ❌ Tidak (sudah auto email) |

---

## ❓ Ada Masalah?

Hubungi: Zero / Team Leader

---

_Versi: 2026-02-19_
_Sistem: Zantara CRM_
