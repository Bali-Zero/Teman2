# Obligations catalog — source verification, September 2026

Scope: the 21 rules in `apps/backend-rag/backend/data/obligations_catalog.yaml`. Before this sweep
every rule carried `verified: false` and every `legal_source` carried a "(verify)" note, so the
reviewer queue could show a proposal without being able to show why it was owed. Retrieved
2026-09-12 unless a row says otherwise.

**Result: 16 of 21 confirmed, 5 left unverified on purpose.** A rule is `verified: true` only when
BOTH the legal basis AND the due-date rule were read on a primary source, and the URL now sits in
`legal_source`. The five that stayed `false` each say in `needs_review_reason` exactly what is
missing; four of them fail for the same honest reason, that their schedule is Bali Zero's cadence
rather than a statutory date, and two fail because the regulation text could not be read at all.

What "primary source" meant here: a government page that rendered as text, or the regulation PDF
downloaded from a government domain and read locally. Secondary tax commentary was used to locate
articles and never to settle one. Three corrections below change behaviour, not just wording.

## The three corrections that change a proposal

| What                                 | Before                            | After                                                    |
| ------------------------------------ | --------------------------------- | -------------------------------------------------------- |
| LKPM deadline                        | 10th of the month after a quarter | 15th, per Permen Investasi/BKPM 5/2025 art. 286(5)       |
| BPJS Ketenagakerjaan non-working day | never moved (`roll: none`)        | moves to the next working day, per PP 44/2015 art. 21(3) |
| Halal UMK deadline                   | "17 or 18 October 2026 (verify)"  | 17 October 2026, per PP 42/2024 art. 160(2)              |

The LKPM change also invalidated a test expectation: `LKPM_2026` in
`apps/backend-rag/backend/tests/services/compliance/test_obligations_register.py` asserted the four
2026 dates on the 10th and now asserts them on the 15th. The same file asserted that no rule in the
catalog was verified, which was the point of the sweep; that assertion is replaced by one that every
verified rule cites a URL, that at least 12 are verified, and that every unverified rule explains
itself.

## The 21 rows

| #   | Rule id                         | Claim checked (basis + due rule)                                                   | Source                                                                                                                                                                                                                                                           | Verdict     | What changed                                                                                                                                                                                                          |
| --- | ------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `lkpm_quarterly`                | Perka BKPM 5/2021; quarterly, 10th of the month after the calendar quarter         | [Permen Investasi/BKPM 5/2025, art. 286](https://jdih-storage.bkpm.go.id/jdih/jdih/2025Permeninvesthil005-.pdf)                                                                                                                                                  | corrected   | Regulation replaced (5/2025, not 5/2021); `due.day` 10 → 15; reason now names the small-scale semester cycle and the micro exemption                                                                                  |
| 2   | `pph21_payment`                 | UU PPh art. 21/26; PMK 81/2024 art. 94; deposit on the 15th of the following month | [UU KUP art. 9(1)](https://www.pajak.go.id/en/node/35330), [DJP on PMK 81/2024](https://www.pajak.go.id/en/node/112032)                                                                                                                                          | confirmed   | "(verify)" removed; UU KUP art. 9(1) added as the statutory 15-day cap; PMK 168/2023 relabelled as the TER calculation, not the deadline                                                                              |
| 3   | `spt_masa_pph21`                | PMK 168/2023; return by the 20th of the following month                            | [UU KUP art. 3(3)(a)](https://www.pajak.go.id/en/node/35330)                                                                                                                                                                                                     | confirmed   | Deadline re-based on the statute (every SPT Masa is due at most 20 days after the period) instead of on PMK 168/2023                                                                                                  |
| 4   | `pph23_26_payment`              | UU PPh art. 23/26; PER-24/PJ/2021; deposit on the 15th                             | [UU KUP art. 9(1)](https://www.pajak.go.id/en/node/35330), [DJP on PMK 81/2024](https://www.pajak.go.id/en/node/112032)                                                                                                                                          | confirmed   | Same re-basing as row 2; third-party-payment caveat kept                                                                                                                                                              |
| 5   | `spt_masa_pph23_26`             | PER-24/PJ/2021 as the source of the 20th                                           | [UU KUP art. 3(3)(a)](https://www.pajak.go.id/en/node/35330)                                                                                                                                                                                                     | corrected   | PER-24/PJ/2021 governs the form of the unified return and e-Bupot, not the deadline; the 20 days come from UU KUP                                                                                                     |
| 6   | `spt_masa_ppn`                  | UU PPN as amended by UU HPP; a PMK on e-Faktur; end of the following month         | [UU PPN art. 15A(1)-(2)](https://www.pajak.go.id/en/node/35341)                                                                                                                                                                                                  | confirmed   | Cited to art. 15A for both payment and return; the vague e-Faktur PMK reference dropped                                                                                                                               |
| 7   | `pph25_installment`             | UU PPh art. 25; payment on the 15th; reporting deemed by payment                   | [UU PPh art. 25(1)](https://www.pajak.go.id/en/node/35337), [UU KUP art. 9(1)](https://www.pajak.go.id/en/node/35330)                                                                                                                                            | corrected   | Instalment and deadline confirmed; the "payment is the report" sub-rule could not be read on a primary page and moved to `notes` flagged as unconfirmed                                                               |
| 8   | `spt_tahunan_badan`             | UU KUP art. 3; 4 months after year end; "2026 deadline extended to 31 May"         | [UU KUP art. 3(3)(c)](https://www.pajak.go.id/en/node/35330), [KEP-71/PJ/2026](https://pajak.go.id/id/pengumuman/kebijakan-penghapusan-sanksi-administratif-atas-keterlambatan-pembayaran-dan-pelaporan-1)                                                       | corrected   | The deadline was never extended: KEP-71/PJ/2026 WAIVES the penalty for one month past it for tax year 2025. Keep proposing 30 April                                                                                   |
| 9   | `bpjs_kesehatan_monthly`        | UU 24/2011; Perpres 82/2018; 10th of the month                                     | [Perpres 82/2018 art. 39(1)](https://peraturan.go.id/files/ps82-2018.pdf)                                                                                                                                                                                        | confirmed   | Article pinned; `notes` states the 10th is of the covered month, and that art. 39 has no non-working-day clause so `roll` stays `none`                                                                                |
| 10  | `bpjs_ketenagakerjaan_monthly`  | PP 44/2015, 45/2015, 46/2015; 15th of the following month; `roll: none`            | [PP 44/2015 art. 21](https://www.bpjsketenagakerjaan.go.id/assets/uploads/peraturan/15122015_104557_PP%2044%20Tahun%202015.pdf), [PP 46/2015 art. 19](https://www.bpjsketenagakerjaan.go.id/assets/uploads/peraturan/15122015_104556_PP%2046%20Tahun%202015.pdf) | corrected   | `roll` → `next_business_day`: art. 21(3) and art. 19(3) both move a 15th falling on a holiday to the next working day. Foreign-worker rule pinned to PP 44/2015 art. 1(4). JP (PP 45/2015) unread, said so in `notes` |
| 11  | `expat_tax_residency_review`    | UU PPh art. 2; PER-43/PJ/2011; monthly review                                      | [PER-23/PJ/2025](https://www.pajak.go.id/en/node/118835), [UU PPh art. 2](https://www.pajak.go.id/en/node/35337)                                                                                                                                                 | unconfirmed | Citation corrected (PER-43/PJ/2011 was revoked on 9 December 2025), but stays `false`: no regulation sets a residency-review date, so the monthly cadence is ours                                                     |
| 12  | `pse_registration`              | PP 71/2019; Permenkominfo 5/2020 as amended by 10/2021; register before operating  | [Permenkominfo 5/2020 art. 2(3)](https://jdih.komdigi.go.id/produk_hukum/view/id/759/t/peraturan+menteri+komunikasi+dan+informatika+nomor+5+tahun+2020)                                                                                                          | confirmed   | Articles pinned (2(3) duty, 7(3) sanctions incl. the 7-day window); `notes` records that Permenkomdigi 5/2025 replaced the rule only for PSE Lingkup Publik                                                           |
| 13  | `pse_data_update`               | Permenkominfo 5/2020 "art. on data changes (verify article and time limit)"        | [Permenkominfo 5/2020 art. 5](https://jdih.komdigi.go.id/produk_hukum/view/id/759/t/peraturan+menteri+komunikasi+dan+informatika+nomor+5+tahun+2020)                                                                                                             | confirmed   | Article is 5, and the missing time limit is a real gap in the regulation: it states none. Do not attach a "within N days" to this rule                                                                                |
| 14  | `pmse_vat_assessment`           | PMK 81/2024 thresholds IDR 600m/50m and 12,000/1,000 accesses                      | PMK 81/2024 — not readable, see note below                                                                                                                                                                                                                       | unconfirmed | Stays `false`. Reason sharpened to say the figures rest on secondary commentary; the PER-12/PJ/2020 origin of the numbers recorded                                                                                    |
| 15  | `pmse_vat_monthly_deposit`      | PMK 81/2024; deposit end of the following month; quarterly report                  | PMK 81/2024 — not readable, see note below                                                                                                                                                                                                                       | unconfirmed | Stays `false`. Commentary says PMK 81/2024 replaced the quarterly report with one per Masa Pajak; recorded as a lead, not a fact                                                                                      |
| 16  | `rups_annual`                   | UU 40/2007 art. 78; RUPS within 6 months of year end                               | [UU 40/2007 art. 78(2)](https://peraturan.bpk.go.id/Download/29563/UU%20Nomor%2040%20Tahun%202007.pdf)                                                                                                                                                           | confirmed   | Exact as claimed; quote and URL added, plus art. 78(3) on the annual-report documents                                                                                                                                 |
| 17  | `wajib_lapor_ketenagakerjaan`   | UU 7/1981; Permenaker 18/2017; 30 days from first hire, then yearly                | [UU 7/1981 art. 6-7](https://peraturan.bpk.go.id/Download/35873/UU%20Nomor%207%20Tahun%201981.pdf)                                                                                                                                                               | corrected   | The trigger is not the first hire: art. 6(1) counts 30 days from establishing, restarting or relocating the company, and art. 7's Penjelasan sets the annual report in the month of the first one                     |
| 18  | `rptka_imta_expat`              | PP 34/2021; Permenaker 8/2021; review 60 days before expiry                        | [PP 34/2021 art. 17 and 21(2)](https://peraturan.go.id/files/pp34-2021bt.pdf)                                                                                                                                                                                    | corrected   | The statutory lead time is 30 WORKING days (art. 21(2)); the 60 days is Bali Zero's buffer and the trigger now says so. RPTKA validity added (6 months / 2 years / 5 years in a KEK)                                  |
| 19  | `pdp_processor_controls`        | UU 27/2022 art. 46; breach notice within 3x24 hours; annual review                 | [UU 27/2022 art. 46(1) and 31](https://jdih.komdigi.go.id/produk_hukum/view/id/832/t/undangundang+nomor+27+tahun+2022)                                                                                                                                           | unconfirmed | Articles confirmed (46(1) notice, 31 processing records) but stays `false`: the annual cadence is not statutory. Implementing PP and the lembaga PDP not confirmed operational                                        |
| 20  | `halal_certification`           | UU 33/2014; PP 42/2024; UMK deadline "17 or 18 October 2026"                       | [PP 42/2024 art. 160](https://peraturan.bpk.go.id/Download/365010/PP%20Nomor%2042%20Tahun%202024.pdf)                                                                                                                                                            | corrected   | 17 October 2026 (a Saturday, hence the "18" in circulation). art. 160(1) closed the medium/large phase on 17 October 2024; cosmetics and supplements sit on the art. 161 schedule                                     |
| 21  | `marketplace_withholding_pmk37` | PMK 37/2025; 0.5 percent; IDR 500m threshold; enforcement from 1 November 2026     | [DJP on PMK 37/2025](https://www.pajak.go.id/en/node/120342)                                                                                                                                                                                                     | unconfirmed | Rate and exemption confirmed, and the exemption is for INDIVIDUALS only, not companies. Stays `false`: the duty starts the month after DJP appoints a given marketplace, not on a single national date                |

## Why PMK 81/2024 could not be read directly

Rows 14 and 15 depend on PMK 81/2024, the 2024 consolidation that revoked PMK 60/2022. Its official
PDF is a 642-page scan with no text layer, so neither a fetch nor a local text extraction produces
quotable article text, and `jdih.kemenkeu.go.id` times out from this machine. The rows that depend
on PMK 81/2024 for a DATE only (2, 4, 7) are still `verified: true`, because the date is
independently fixed by statute: UU KUP art. 9(1) caps a Masa Pajak payment at 15 days after the
period ends, and DJP's own page states the deposit was unified on the 15th of the following month.
The PMSE rows have no such statutory backstop, so they stay `false` until somebody reads the PMK.

## Verbatim quotes behind the corrections

```
Permen Investasi/BKPM 5/2025 art. 286(1): "a. bagi Pelaku Usaha dengan skala usaha kecil setiap 6
(enam) bulan atau semester; dan b. bagi Pelaku Usaha dengan skala usaha menengah dan besar setiap
3 (tiga) bulan atau triwulan."
art. 286(5): "a. laporan triwulan I disampaikan paling lambat tanggal 15 bulan April tahun yang
bersangkutan; ... d. laporan triwulan IV disampaikan paling lambat tanggal 15 bulan Januari tahun
berikutnya."
art. 286(2): "tidak diwajibkan bagi: a. Pelaku Usaha dengan skala usaha mikro"
art. 286(7): a date falling on a libur nasional "akan disesuaikan melalui pemberitahuan resmi" —
an official notice, not an automatic roll.

UU KUP art. 3(3): "paling lama 20 (dua puluh) hari setelah akhir Masa Pajak" (SPT Masa);
"paling lama 4 (empat) bulan setelah akhir Tahun Pajak" (SPT Tahunan badan).
UU KUP art. 9(1): "paling lama 15 (lima belas) hari setelah saat terutangnya pajak atau
berakhirnya Masa Pajak."
DJP on PMK 81/2024: "Jatuh tempo pembayaran atau penyetoran masa beberapa jenis pajak
diseragamkan menjadi tanggal 15 bulan berikutnya."

UU PPN art. 15A(1): "Penyetoran Pajak Pertambahan Nilai ... harus dilakukan paling lama akhir
bulan berikutnya setelah berakhirnya Masa Pajak dan sebelum Surat Pemberitahuan Masa Pajak
Pertambahan Nilai disampaikan."
art. 15A(2): "Surat Pemberitahuan Masa Pajak Pertambahan Nilai disampaikan paling lama akhir bulan
berikutnya setelah berakhirnya Masa Pajak."

Perpres 82/2018 art. 39(1): "Pemberi Kerja wajib memungut Iuran dari Pekerjanya, membayar Iuran
yang menjadi tanggung jawabnya, dan menyetor Iuran tersebut kepada BPJS Kesehatan paling lambat
tanggal 10 (sepuluh) setiap bulan."

PP 44/2015 art. 21(2): "wajib membayar Iuran ... setiap bulan, paling lambat tanggal 15 bulan
berikutnya dari bulan Iuran yang bersangkutan."
art. 21(3): "Apabila tanggal 15 ... jatuh pada hari libur, maka Iuran dibayarkan pada hari kerja
berikutnya."
art. 1(4): "Peserta adalah setiap orang, termasuk orang asing yang bekerja paling singkat 6 (enam)
bulan di Indonesia, yang telah membayar iuran."
PP 46/2015 art. 19(2) and 19(3) carry the same date and the same roll for JHT.

UU 40/2007 art. 78(2): "RUPS tahunan wajib diadakan dalam jangka waktu paling lambat 6 (enam)
bulan setelah tahun buku berakhir."

UU 7/1981 art. 6(1): "wajib melaporkan secara tertulis ... selambat-lambatnya dalam jangka waktu
30 (tiga puluh) hari setelah mendirikan, menjalankan kembali atau memindahkan perusahaan."
Penjelasan art. 7: "apabila perusahaan itu dilaporkan pada bulan Juli maka bulan Juli pada tahun
berikutnya laporan berkala itu disampaikan lagi."

PP 34/2021 art. 21(2): "Permohonan perpanjangan Pengesahan RPTKA ... diajukan paling lambat 30
(tiga puluh) hari kerja sebelum jangka waktu berakhir."

Permenkominfo 5/2020 art. 2(3): "Kewajiban melakukan pendaftaran bagi PSE Lingkup Privat dilakukan
sebelum Sistem Elektronik mulai digunakan oleh Pengguna Sistem Elektronik."
art. 5: "Perubahan terhadap informasi pendaftaran ... wajib dilaporkan kepada Menteri." — no
number of days anywhere in the article.

UU 27/2022 art. 46(1): "Pengendali Data Pribadi wajib menyampaikan pemberitahuan secara tertulis
paling lambat 3 x 24 (tiga kali dua puluh empat) jam kepada: a. Subjek Data Pribadi; dan
b. lembaga."

PP 42/2024 art. 160(2): "Bagi Pelaku Usaha mikro dan kecil, penahapan kewajiban bersertifikat
halal untuk Produk makanan, minuman, hasil sembelihan, dan jasa penyembelihan dimulai dari tanggal
17 Oktober 2019 sampai dengan tanggal 17 Oktober 2026."

PP 28/2025 art. 355(2): "a. peringatan; b. penghentian sementara kegiatan usaha; c. pengenaan
denda administratif; d. pengenaan daya paksa polisional; e. pencabutan lisensi/sertifikasi/
persetujuan; dan/atau f. pencabutan persyaratan dasar, PB, dan/atau PB UMKU."

PMK 37/2025, per DJP: withholding is "0,5% dari omzet atau nilai transaksi" before discounts, the
IDR 500 million exemption is for "wajib pajak orang pribadi", and the duty starts "awal bulan
berikutnya setelah Direktorat Jenderal Pajak (DJP) menerbitkan keputusan penunjukan marketplace".
```

## What a later sweep should pick up

1. PMK 81/2024 art. 332 onward and art. 399: read the PMSE thresholds and the report cadence on the
   regulation itself, then rows 14 and 15 can flip.
2. PP 45/2015 art. on the JP contribution date, to finish row 10's footnote.
3. The PDP implementing PP and whether the lembaga PDP is operational, for row 19.
4. Whether the first DJP penunjukan of marketplaces under PMK 37/2025 fixes a date for row 21.
5. Permenaker 18/2017's current status (reportedly amended by Permenaker 4/2019) — row 17 rests on
   the statute, which is enough for the deadline, but the filing channel should be pinned too.
