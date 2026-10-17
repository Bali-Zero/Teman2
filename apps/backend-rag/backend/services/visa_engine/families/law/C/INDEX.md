# C family law index (source: imigrasi.go.id, fetched 2026-10-17 UTC)

Raw HTML in raw/, text in <CODE>.txt, structured in <CODE>.json. Requirement counts = items under 'Pengajuan visa' + 'Persyaratan Khusus'.

| code | name | stay (Masa tinggal, verbatim) | extendable (verbatim) | sponsor | #req | status | url |
|---|---|---|---|---|---|---|---|
| C1 | C1 Visa Kunjungan Wisata | maksimal 60 hari, dihitung sejak tanggal kedatangan. | Anda dapat memperpanjang izin tinggal ini beberapa kali hingga maksimal 180 hari. | not required (with exceptions) | 3 | VERIFIED_FROM_SOURCE | https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C1 |
| C2 | C2 Visa Kunjungan Bisnis | maksimal 60 hari, dihitung sejak tanggal kedatangan. | Anda dapat memperpanjang izin tinggal ini beberapa kali hingga maksimal 180 hari. | not required (with exceptions) | 4 | VERIFIED_FROM_SOURCE | https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C2 |
| C6 | C6 Visa Kunjungan Kegiatan Sosial | maksimal 60 hari, dihitung sejak tanggal kedatangan. | Anda dapat memperpanjang izin tinggal ini beberapa kali hingga maksimal 180 hari. | required | 5 | VERIFIED_FROM_SOURCE | https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C6 |
| C7A | C7A Visa Kunjungan Penampilan Musik | maksimal 30 hari, dihitung sejak tanggal kedatangan. | Anda tidak dapat memperpanjang izin tinggal ini. | required | 6 | VERIFIED_FROM_SOURCE | https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C7A |
| C7B | C7B Visa Kunjungan Kru Penampilan Musik | maksimal 30 hari, dihitung sejak tanggal kedatangan. | Anda tidak dapat memperpanjang izin tinggal ini. | required | 6 | VERIFIED_FROM_SOURCE | https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C7B |
| C7C | C7C Visa Kunjungan Penampilan Bakat dan Seni | maksimal 30 hari, dihitung sejak tanggal kedatangan. | Anda tidak dapat memperpanjang izin tinggal ini. | required | 6 | VERIFIED_FROM_SOURCE | https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C7C |
| C8A | C8A Visa Kunjungan Atlet Olahraga | maksimal 60 hari, dihitung sejak tanggal kedatangan. | Anda dapat memperpanjang izin tinggal ini beberapa kali hingga maksimal 180 hari. | required | 5 | VERIFIED_FROM_SOURCE | https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C8A |
| C8B | C8B Visa Kunjungan Ofisial Olahraga | maksimal 60 hari, dihitung sejak tanggal kedatangan. | Anda dapat memperpanjang izin tinggal ini beberapa kali hingga maksimal 180 hari. | required | 5 | VERIFIED_FROM_SOURCE | https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C8B |
| C10 | C10 Visa Kunjungan Narasumber Kegiatan Bisnis | maksimal 60 hari, dihitung sejak tanggal kedatangan. | Anda dapat memperpanjang izin tinggal ini beberapa kali hingga maksimal 180 hari. | required | 5 | VERIFIED_FROM_SOURCE | https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C10 |
| C12 | C12 Visa Kunjungan Pra-Investasi | maksimal 180 hari, dihitung sejak tanggal kedatangan. | Anda dapat memperpanjang izin tinggal ini beberapa kali hingga maksimal 12 bulan. | required | 6 | VERIFIED_FROM_SOURCE | https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C12 |
| C18 | C18 Visa Kunjungan Uji Kemampuan Tenaga Kerja Asing | maksimal 90 hari, dihitung sejak tanggal kedatangan. | Anda tidak dapat memperpanjang izin tinggal ini | required | 4 | VERIFIED_FROM_SOURCE | https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C18 |
| C22A | C22A Visa Kunjungan Pemagangan Akademik | maksimal 180 hari, dihitung sejak tanggal kedatangan. | Anda dapat memperpanjang izin tinggal ini diberikan dengan jangka waktu 180 Hari setiap kali perpanjangan terhitung sejak tanggal berakhirnya Izin Tinggal Kunjungan dengan ketentuan keseluruhan Izin Tinggal di Wilayah Indonesia tidak lebih dari 12 (dua belas) bulan. | required | 5 | VERIFIED_FROM_SOURCE | https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C22A |
| C22B | C22B Visa Kunjungan Pemagangan Kompetensi | maksimal 180 hari, dihitung sejak tanggal kedatangan. | Anda dapat memperpanjang izin tinggal ini diberikan dengan jangka waktu 180 Hari setiap kali perpanjangan terhitung sejak tanggal berakhirnya Izin Tinggal Kunjungan dengan ketentuan keseluruhan Izin Tinggal di Wilayah Indonesia tidak lebih dari 12 (dua belas) bulan. | required | 5 | VERIFIED_FROM_SOURCE | https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C22B |

## Page-level anomalies (flagged, not resolved)
- C18: 'Jenis visa' says maksimal 60 hari + dapat diperpanjang; 'Masa tinggal' says maksimal 90 hari + tidak dapat memperpanjang. TO VERIFY against Kepmen M.IP-08.GR.01.01/2025.
- C22A/C22B: extension sentence garbled in source; extension in 180-day steps, total not more than 12 bulan.
- C1/C2: no sponsor, except stateless / non-national-passport holders / nationals of listed countries (list is a link, not captured). C1 states 'Tidak ada persyaratan khusus'.
- Pages state no offshore/onshore rule: where_to_apply = null for all.

## Facts the questions would need (derived ONLY from the verbatim requirements / conditions)
1. Purpose/activity category (maps to code): tourism-MICE-site visit-medical (C1); business meetings/purchasing (C2); social activity (C6); music performance (C7A); crew supporting music (C7B); talent and arts performance support (C7C); non-commercial sport as athlete (C8A) vs official (C8B); speaker/presenter at MICE (C10); pre-investment survey/feasibility (C12); skills trial at a company (C18); academic internship for foreign education (C22A) vs competency-development internship (C22B).
2. Nationality/document type: national passport vs stateless / non-national travel document (emergency passport, titre du voyage, etc.). Drives: sponsor exception (C1, C2), 12-month passport validity, Izin Masuk Kembali + onward ticket.
3. Nationality on the country list (C1, C2 sponsor exception): list not in page text, needs separate source.
4. Passport validity: at least 6 months remaining (12 months for non-national documents).
5. Funds: proof of living costs, 3-month bank statement in name of the foreigner or sponsor; the USD2000 minimum is stated verbatim only on C1, C10, C12 (C12 also accepts slip gaji / deposito). Other codes state no amount on page: do not assume.
6. Has an Indonesian sponsor/penjamin with an evisa.imigrasi.go.id account (C6, C7A-C, C8A/B, C10, C12, C18, C22A/B; not C1/C2 by default).
7. Inviting/related party letter, by type: government agency or private institution letter/undangan/korespondensi (C2, C6, C12); event organiser invitation (C7x general arts, C8A/B with surat sponsor, C10 with agenda and lecture material detail); trial-of-skills invitation (C18); internship agreement or statement from organiser (C22A/B).
8. Music/arts: general arts-culture participant (organiser invitation) vs music performer or supporter (impresariat application letter + performer-organiser cooperation contract; C7A also impresariat surat penjaminan). C7A also requires surat pernyataan penjamin dari penyelenggara kegiatan.
9. Return/onward ticket: stated explicitly only for C12 (Tiket kembali) and for stateless/non-national-document holders (all codes, Ketentuan lain).
10. Remuneration intent: C1, C2, C6, C12, C18, C22A/B prohibit selling goods/services or receiving payment from Indonesian persons/corporations; C7A-C, C8A/B, C10 permit imbalan/fasilitas but not employment relationship (C7A/C10) . C1 additionally prohibits acting as Pembicara (speaker).
11. Intended length of stay and whether conversion/extension is wanted (30 days fixed for C7x; 60 days extendable to 180 for C1/C2/C6/C8/C10; C12 up to 180 days, 12 months total; C22A/B 180 days, 12 months total).
12. Visa not used within 90 days of issuance expires (all pages).
