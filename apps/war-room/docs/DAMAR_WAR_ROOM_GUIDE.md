# War Room Guide — Untuk Damar

## Apa ini?

Setiap malam AI (Claude) bikin carousel Instagram baru secara otomatis. Tugasmu: ambil hasilnya, tambahin gambar, rapiin, terus publish.

## Flow Kamu (Setiap Pagi)

### Step 1: Cek "CLAUDE IN CANVA"

Buka design ini:
https://www.canva.com/design/DAHE6lx1lf8/edit

Setiap malam Claude nulis carousel baru di sini. Isinya udah ada:

- Cover slide (headline + subhead)
- Content slides (teks udah bener, posisi udah bener)
- CTA slide
- Endcard

**Teksnya JANGAN diubah** kecuali ada typo jelas.

### Step 2: Copy ke Folder Kita

Copy design ke folder archive:
https://www.canva.com/folder/FAHEwkTYduI

Caranya: buka design → Share → Make a copy → pindahin ke folder itu.
Kasih nama: tanggal + topik, contoh: "2026-03-25 Bank Account Crackdown"

### Step 3: Bikin Gambar

Di setiap carousel ada slide yang butuh gambar. Kamu bakal dapat prompt lewat Telegram dari bot.

Contoh prompt yang kamu terima:

```
🎨 Slide 1 (cover, full-bleed):
"Macro shot of a weathered Balinese stone temple gate reflecting
in a puddle, but the reflection shows a modern digital dashboard.
Golden hour backlight, vivid saturated colors."

🎨 Slide 4 (bottom_half):
"Cinematic landscape of Bali's rice terraces at dawn, bisected by
sharp vertical glowing blue lines like a laser scan grid."
```

Kamu generate pakai Gemini/Midjourney/Flux — terserah tool mana yang hasilnya paling bagus.

**Rules gambar:**

- NO teks di gambar (headline ditambahin di Canva, bukan di gambar)
- NO stock photo (no jabat tangan, no passport generik, no orang senyum di kantor)
- Warna: terracotta, gold, indigo, tropical green — warna Bali
- Mood: cinematic, dramatis, editorial (kayak majalah Wired/Bloomberg)
- Lower third (bagian bawah) harus clean — nanti ditindih teks

### Step 4: Pasang Gambar di Canva

Di copy kamu yang ada di folder archive:

- Cover (slide 1): gambar FULL BLEED — tutupin seluruh slide, teks di atasnya
- Slide tipe C (ada tulisan "bottom_half"): gambar di SETENGAH BAWAH slide
- Slide tipe B (text only): JANGAN kasih gambar — backgroundnya tetap gelap

### Step 5: Final Check

Sebelum kasih ke boss:

- [ ] Semua teks kebaca? Font ga kepotong?
- [ ] Gambar ga blur / ga pecah?
- [ ] Logo Bali Zero ada di setiap slide?
- [ ] Warna konsisten (background gelap #373D42)?
- [ ] Slide terakhir ada "DM AUDIT or WhatsApp us. balizero.com"?

### Step 6: Kasih Tau Selesai

Kirim message di Telegram:
"✅ Carousel [tanggal] — [topik] done. [link Canva]"

---

## Slide Types (Biar Gak Bingung)

| Type               | Kelihatannya                 | Gambar?                |
| ------------------ | ---------------------------- | ---------------------- |
| **A** (Cover)      | Headline gede + foto full    | ✅ WAJIB (full-bleed)  |
| **B** (Text)       | Background gelap, teks doang | ❌ Jangan              |
| **C** (Text+Photo) | Teks atas, foto bawah        | ✅ WAJIB (bottom half) |
| **D** (CTA)        | Kayak B tapi lebih lebar     | ❌ Jangan              |
| **E** (Endcard)    | Logo + kontak                | ❌ Jangan              |

## Jadwal

- **01:00 WITA**: AI pipeline jalan (intel scraper + war room)
- **~02:00 WITA**: Carousel baru ready di "CLAUDE IN CANVA"
- **Pagi**: Kamu ambil, tambahin gambar, rapiin
- **Siang**: Kasih ke boss buat review

## Kontak Kalau Ada Masalah

- Design kosong / error → bilang di Telegram grup
- Prompt gambar ga jelas → tanya di Telegram, Claude bisa jelasin ulang
- Canva ga bisa dibuka → coba lagi 5 menit, kalau masih error bilang

---

_Guide ini dibuat otomatis oleh War Room pipeline. Last updated: 2026-03-25._
