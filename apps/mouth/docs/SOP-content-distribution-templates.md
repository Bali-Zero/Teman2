# SOP: Content Distribution Templates

**Bali Zero · Nuzantara v5.2.0**
**Owner:** Subhi Darajat · Berlaku: 29 Jul 2026
**Gunakan bersama:** Task content prep (20 artikel) + UTM generator

---

## Cara Pakai

1. Ambil data artikel dari content prep spreadsheet (slug, seoTitle ID, ringkasan 150 kata, 3 poin kunci)
2. Pilih template channel yang sesuai
3. Substitusi semua `[PLACEHOLDER]` — jangan ada yang tertinggal
4. Pasang UTM link dari UTM generator (bukan URL bare)
5. Review: tidak ada nama klien asli, tidak ada kutipan verbatim Google review

---

## Template 1 — Medium (Full Repost)

**Format:** Full article repost dengan canonical link. Gunakan fitur "Import a story" di Medium untuk auto-set canonical.

```
[JUDUL ARTIKEL — sama persis dengan seoTitle ID]

[ISI ARTIKEL LENGKAP — paste dari .id.mdx, strip frontmatter]

---

*Artikel ini pertama kali diterbitkan di [Bali Zero](https://kita.balizero.com/[SLUG]?utm_source=medium&utm_medium=social&utm_campaign=batch1-distribution). Bali Zero adalah konsultan visa, PT PMA, pajak, dan properti untuk ekspatriat dan investor asing di Bali.*

*Butuh bantuan? [Konsultasi via WhatsApp →](https://kita.balizero.com/[SLUG]?utm_source=medium&utm_medium=social&utm_campaign=batch1-distribution)*
```

**Checklist sebelum publish:**

- [ ] Canonical URL sudah diset ke `kita.balizero.com/[slug]` (bukan URL Medium)
- [ ] Tag: Indonesia Business / Bali Expat Life / Tax Legal (pilih yang relevan)
- [ ] Tidak ada harga hardcoded — hapus atau ganti dengan "hubungi kami"

---

## Template 2 — LinkedIn (Native Post)

**Format:** 200–300 kata native. Link di komentar pertama, bukan di body post (algoritma LinkedIn penalti external link di post utama).

```
[HOOK 1 KALIMAT — fakta mengejutkan atau pertanyaan retoris dari artikel]

[PARAGRAF 1 — konteks masalah, 2-3 kalimat]

[PARAGRAF 2 — apa yang berubah / apa yang perlu diketahui, 2-3 kalimat]

[PARAGRAF 3 — actionable insight atau common mistake, 2-3 kalimat]

Kalau kamu atau tim sedang menghadapi situasi ini, ada panduan lengkapnya di link komentar pertama.

#BaliExpat #IndonesiaBusiness #[TAG_RELEVAN]
```

**Komentar pertama (post langsung setelah publish):**

```
Panduan lengkap: [JUDUL ARTIKEL]
→ [UTM LINK]
```

**Checklist:**

- [ ] Body post < 300 kata
- [ ] Tidak ada link di body post
- [ ] Tag maksimal 3 (lebih = spam signal)
- [ ] Prioritas artikel: business + property (audience investor LinkedIn)

---

## Template 3 — Twitter/X Thread (7-Tweet Formula)

**Format:** 7 tweet per artikel. Tweet 1 adalah hook, tweet 7 adalah CTA.

```
Tweet 1 — HOOK (maks 250 karakter):
[FAKTA MENGEJUTKAN atau PERTANYAAN] 🧵

Tweet 2 — KONTEKS:
Banyak yang tidak tau bahwa [INSIGHT UTAMA ARTIKEL].

[DETAIL 1-2 kalimat]

Tweet 3 — POIN KUNCI 1:
[POIN KUNCI 1 dari content prep]

Tweet 4 — POIN KUNCI 2:
[POIN KUNCI 2 dari content prep]

Tweet 5 — POIN KUNCI 3:
[POIN KUNCI 3 dari content prep]

Tweet 6 — COMMON MISTAKE atau GOTCHA:
Yang sering salah: [KESALAHAN UMUM terkait topik artikel]

Tweet 7 — CTA:
Panduan lengkap (gratis):
→ [UTM LINK]

Kalau ada pertanyaan spesifik, reply di sini atau langsung ke tim Bali Zero via WhatsApp.
```

**Checklist:**

- [ ] Tweet 1 tidak ada link (reduce reach)
- [ ] UTM hanya di tweet terakhir
- [ ] Thread di-reply ke tweet 1 sendiri (bukan post terpisah)

---

## Template 4 — Facebook Group (Conversational)

**Format:** Tone conversational, bukan promosi langsung. Banyak grup ban link langsung — framing sebagai sharing pengalaman/informasi.

**Cek dulu rules grup sebelum posting.** Kalau grup larang link → hapus UTM, mention "DM untuk link".

```
[PERTANYAAN PEMBUKA yang relevan ke komunitas grup]

Baru baca artikel menarik soal [TOPIK SINGKAT] — ternyata banyak yang belum tau soal [INSIGHT UTAMA].

Intinya: [RINGKASAN 2-3 kalimat, conversational, bukan bullet point]

Yang bikin saya surprised: [FAKTA MENGEJUTKAN dari artikel]

Ada yang pernah ngalamin situasi ini? Atau ada update terbaru yang kamu tau?

[jika grup allow link:]
Full breakdown di sini kalau mau baca detail: [UTM LINK]
```

**Checklist:**

- [ ] Tidak pakai kata "promo", "jasa", "layanan" di kalimat pertama
- [ ] Buka dengan pertanyaan atau sharing, bukan CTA
- [ ] Cek rules grup (pin post atau deskripsi grup)
- [ ] Frekuensi: maks 2-3x/minggu per grup, jangan setiap hari

---

## Template 5 — Pinterest Pin

**Format:** Visual-first. Prioritas artikel property + lifestyle dulu (paling visual-friendly).

**Copy untuk pin description:**

```
[JUDUL ARTIKEL — max 100 karakter]

[RINGKASAN 2-3 kalimat — informatif, pakai keyword natural]

Panduan lengkap untuk ekspatriat dan investor asing di Bali.

#BaliExpat #IndonesiaBusiness #[KEYWORD_SPESIFIK] #BaliBusiness #ExpatBali
```

**Spec grafis (untuk Damar):**

- Ukuran: 1000 × 1500 px (rasio 2:3)
- Font overlay: Cormorant Garamond untuk judul (brand font)
- Warna background: `#f7f6f2` (paper white) atau foto Bali
- Logo Bali Zero: sudut kanan bawah, ukuran sedang
- Judul artikel: overlay di tengah-bawah, kontras tinggi
- Jangan terlalu ramai — satu focal point

**Checklist:**

- [ ] Link pin → UTM link (bukan bare URL)
- [ ] Board: "Bali Business Guide" atau "Expat Life Bali" (buat jika belum ada)
- [ ] Alt text diisi (SEO signal Pinterest)
- [ ] Prioritas: property (3 artikel) + lifestyle (1) + business (2) = 6 artikel batch awal

---

## UTM Format Reference

```
https://kita.balizero.com/[SLUG]?utm_source=[SOURCE]&utm_medium=social&utm_campaign=batch1-distribution
```

| Channel   | `utm_source` |
| --------- | ------------ |
| Medium    | `medium`     |
| LinkedIn  | `linkedin`   |
| Twitter/X | `twitter`    |
| Facebook  | `facebook`   |
| Pinterest | `pinterest`  |

---

## Urutan Prioritas Distribusi

| Prioritas | Channel        | Alasan                                                     |
| --------- | -------------- | ---------------------------------------------------------- |
| 1         | Medium         | Canonical repost — SEO equity kembali ke kita.balizero.com |
| 2         | LinkedIn       | Audience investor/bisnis paling relevan                    |
| 3         | Twitter/X      | Reach organik masih tinggi untuk thread informatif         |
| 4         | Facebook Group | Community engagement, tapi rules ketat                     |
| 5         | Pinterest      | Long-tail discovery, visual-dependent                      |

---

## Artikel yang TIDAK boleh didistribusikan tanpa review

- Artikel yang `aiConfidenceScore < 0.75` → wajib validasi Surya + Angel dulu
- Artikel dengan nama klien asli → ganti dengan anonymous persona dulu
- Artikel yang belum punya `adversarial_review: approved` di frontmatter

---

_Update SOP ini setiap ada channel baru atau perubahan format terbukti perform lebih baik._
_Review performa: 2 minggu post-distribusi via GA4 → Acquisition → Traffic Acquisition → filter utm_source_
