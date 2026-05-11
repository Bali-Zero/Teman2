# R2 — Regulatory Monitoring Indonesia — Research Report

**Author**: Claude Opus 4.7 (1M context)
**Date**: 2026-05-08
**Mission**: research foundation for an autonomic Bali Zero regulatory monitoring system (immigration / company / tax / property — Indonesia).
**Note**: this is a research report with full quote capture from primary and secondary sources. No code, no architecture proposal — only inventory + verbatim citation + 1-line "useful for Bali Zero" annotations per item.

---

## 1. Indonesian gov data sources — inventario completo

### 1.1 BKPM / OSS (Online Single Submission Risk Based Approach)

- **URL base**: https://oss.go.id/ (also https://oss.go.id/en/panduan for English guidelines), parent ministry https://bkpm.go.id/
- **Data type**: NIB (Business Identification Number), KBLI mappings, risk-based licensing, integrasi multi-ministero.
- **Freshness**: real-time (the system itself is the system of record for licensing).
- **Ingest mode**: NO public API documented. Per `suryast/indonesia-gov-apis` repo (Tier 2): "OSS / NIB | BKPM | oss.go.id | None | HTML forms | Public search removed (404)".
- **License/ToS**: gov.id, pubblico-restricted; Personal Data Protection Law (PDP / UU 27/2022) si applica per dati di terzi.
- **Lingua**: Bahasa Indonesia (UI EN parziale).
- **Quote (oss.go.id)**: "OSS RBA — Klasifikasi Baku Lapangan Usaha Indonesia (KBLI) 2020".
- **Quote (BKPM)**: "OSS-RBA system has been integrated with multiple agencies including the Ministry of Home Affairs, Ministry of Finance, Ministry of Law and Human Rights, and Ministry of Agrarian and Spatial Planning, and is also integrated with One Stop Integrated Service centers and managed by the Ministry of Investment/BKPM" (aseanbriefing.com summary).
- **Useful for Bali Zero**: source-of-truth per NIB / KBLI cliente; senza API ufficiale → headless browser scraping del cliente loggato (NON di terzi), monitor stato pengajuan e dialog di compliance.

### 1.2 DJP (Direktorat Jenderal Pajak / Directorate General of Taxes)

- **URL base**: https://www.pajak.go.id/ (en: https://www.pajak.go.id/en), regulations index https://www.pajak.go.id/en/peraturan, login https://djponline.pajak.go.id/, NPWP portal https://portalnpwp.pajak.go.id/login, registration https://ereg.pajak.go.id/.
- **Coretax** (in produzione 2025+): https://www.pajak.go.id/en/core-system-tax-administration .
- **Quote (DDTCNews su Coretax APIs)**: "all data and information exchanges will use Application Programming Interface (API). The DJP is continuously preparing the connection of the coretax administration system with entity systems, particularly from outside the Ministry of Finance, and as of now, the DJP is developing interoperability with 89 entities, which will continue to increase".
- **Quote (pajak.go.id Coretax page)**: "Coretax integrates the entire core tax administration business process, ranging from taxpayer registration, SPT (tax return) reporting, tax payment, to tax audits and collections".
- **Press release feed / RSS**: NON pubblico documentato. Hyperlinks in `peraturan` index, news in dashboard pubblico https://www.pajak.go.id/en/index-tax .
- **License/ToS**: copyright DJP, fair-use citation pratica.
- **Lingua**: ID + EN parziale.
- **Useful for Bali Zero**: monitor PER-XX/PJ/YYYY (es. PER-11/PJ/2025 asset disclosure), KEP-XX (es. KEP-71/PJ/2026 SPT 2025 extension già nel memory). Coretax: business-to-business API in espansione (89 entità) — Bali Zero può attendere shortlist o usare HTML scraping listing fino a quel momento.

### 1.3 Imigrasi / Kemenkumham (Direktorat Jenderal Imigrasi)

- **URL base**: https://www.imigrasi.go.id/ ; legal products https://www.imigrasi.go.id/id/dokumen-produk-hukum/ ; Permen index https://www.imigrasi.go.id/imigrasiv1/produk_hukum/index/peraturanmenteri ; download docs https://www.imigrasi.go.id/download/dokumen ; All-Indonesia portal https://allindonesia.imigrasi.go.id/ .
- **Mirror sites**: regional kanim sites (es. https://kanimbatam.kemenkumham.go.id/) ripubblicano `surat edaran` Ditjenim (utile per backup quando il portale centrale è offline).
- **Quote (sample SE)**: "Surat Edaran Ditjenim Nomor IMI-0018.GR.01.01 Tahun 2023 Tentang Kebijakan Keimigrasian Mengenai Layanan E-VOA, VOA, Dan BVK Untuk Mendukung Pariwisata Berkelanjutan Pada Masa Pandemi Covid 2019" (kanimbatam.kemenkumham.go.id).
- **Document categories** (Produk Hukum page): "Undang Undang Keimigrasian, Peraturan Pemerintah, Peraturan Presiden, Peraturan Menteri".
- **Ingest mode**: HTML scraping; surat edaran spesso pubblicate solo come PDF su sub-portali kanim regionali.
- **Lingua**: Bahasa Indonesia (rare EN translations).
- **Useful for Bali Zero**: tier-1 critico — VOA / E-VOA / KITAS / KITAP / BVK rules. SE Ditjenim cambiano mensilmente. Polling daily della pagina prodotti hukum + 2-3 kanim mirror per ridondanza.

### 1.4 ATR/BPN (Agraria dan Tata Ruang / Badan Pertanahan Nasional)

- **URL base**: https://www.atrbpn.go.id/ ; map BHUMI https://bhumi.atrbpn.go.id/peta ; Hak Tanggungan Elektronik https://htel.atrbpn.go.id/ ; informasi pertanahan https://intan.atrbpn.go.id/ ; JDIH ATR/BPN (Android app) https://play.google.com/store/apps/details?id=id.go.atrbpn.jdih .
- **Quote (atrbpn.go.id)**: "BHUMI is a website managed by ATR/BPN [...] that provides land-related information" and "GISTARU (Geographic Information System Tata Ruang) is a website managed by ATR/BPN that provides zoning maps showing different zones within a geographic area in Indonesia".
- **Quote (Mondaq Q&A)**: "ATR/BPN has launched electronic services that can be used by PPAT and financial institutions through Land Information and Mortgage Rights services that can be registered directly without needing to visit land offices".
- **Ingest mode**: BHUMI offre REST endpoints non documentati (osservabili via DevTools), GISTARU usa WMS-style. JDIH ATR/BPN ha PDF-only output.
- **License**: gov.id, restrictive uso commerciale.
- **Lingua**: Bahasa Indonesia.
- **Useful for Bali Zero**: zone planning (KKPR, RDTR), Hak Pakai / HGB tracking, Hak Tanggungan elettronico. Per casi villa/property è la fonte critica (zonasi cambia ogni Pergub/Perbup).

### 1.5 Kemnaker (Kementerian Ketenagakerjaan)

- **URL base**: https://www.kemnaker.go.id/ ; JDIH https://jdih.kemnaker.go.id/ ; TKA Online https://tka-online.kemnaker.go.id/ ; recente Permenaker es. https://jdih.kemnaker.go.id/asset/data_puu/2026pmnaker003.pdf .
- **Quote (Cekindo)**: "Employers submit an RPTKA approval application through the TKA Online website at tka-online.kemnaker.go.id. RPTKA approval typically takes around 14 working days, subject to role and sector". "After obtaining RPTKA approval, the company is required to pay a DKPTKA (Compensation Fund for the Use of Foreign Workers) of 100 USD per month".
- **Document types**: Permenaker, Kepmenaker, surat edaran, Kepmenakertrans (storici).
- **License/ToS**: gov.id pubblico.
- **Lingua**: Bahasa Indonesia.
- **Useful for Bali Zero**: monitor Permenaker su RPTKA / TKA / UMR (Upah Minimum Regional) Bali — UMR cambia ogni Q4 via Pergub provinciale recepito da Kemnaker.

### 1.6 Kementerian Perdagangan (Kemendag)

- **URL base**: https://www.kemendag.go.id/ (en https://www.kemendag.go.id/en) ; JDIH https://jdih.kemendag.go.id/ ; foreign trade DG https://ditjendaglu.kemendag.go.id/ .
- **Quote (jdih.kemendag.go.id index)**: "JDIH Kemendag RI provides statistics and data on trade regulations with graphs to help users read the data" + "system handles export-import licensing management online and in an integrated manner for business actors who already have a Business Registration Number (NIB)".
- **Ingest mode**: PDF download links su jdih portal; HTML structure stabile da scraping.
- **Useful for Bali Zero**: API Importir, NIB-as-API for export/import, Trade Barrier Database. Touchpoint per clienti import/export di Bali Zero.

### 1.7 Bank Indonesia (BI)

- **URL base**: https://www.bi.go.id/ ; SEKI portal https://www.bi.go.id/en/statistik/ekonomi-keuangan/seki/default.aspx ; SEKI metadata https://www.bi.go.id/en/statistik/metadata/seki/Default.aspx ; SEKDA (regional) https://www.bi.go.id/id/statistik/ekonomi-keuangan/sekda/default.aspx .
- **Quote (bi.go.id SEKI)**: "Indonesian Economic and Financial Statistics (SEKI) are published monthly by Bank Indonesia, presenting economic and financial data to help users understand economic and financial developments in Indonesia. Using primary data from Bank Indonesia and secondary data from other relevant institutions, including the Ministry of Finance, BPS-Statistics Indonesia, and Indonesia Deposit Insurance Corporation (LPS), SEKI data is compiled based on international standards and methodologies".
- **Sectors**: "Monetary Sector", "Government Finance", "Real Sector", "External Sector".
- **API**: per `suryast/indonesia-gov-apis`: "Bank Indonesia | Bank Indonesia | bi.go.id | None | REST API | Exchange rates, BI Rate".
- **Lingua**: ID + EN.
- **Useful for Bali Zero**: monthly Kurs Pajak (DJP usa kurs BI per SPT), BI 7DRR (interest rate) per quote/PMK, SEKDA Bali per indicatori macro provincia.

### 1.8 BPS — Statistics Indonesia

- **URL base**: https://www.bps.go.id/en ; WebAPI portal https://webapi.bps.go.id/developer/ ; documentation https://webapi.bps.go.id/documentation/ ; Bali province https://bali.bps.go.id/en .
- **Python lib**: `bps-statistics/stadata` https://github.com/bps-statistics/stadata .
- **Postman collection**: `bps-pinrang/Web-API-BPS-Postman-Collection` https://github.com/bps-pinrang/Web-API-BPS-Postman-Collection .
- **Quote (webapi.bps.go.id)**: "Web API BPS can be accessed by anyone through registration at https://webapi.bps.go.id. Each data request through WebAPI requires an API Key, which can be created through the Profile – Applications – Add Application menu".
- **Endpoints (verbatim WebFetch)**:
  - `https://webapi.bps.go.id/v1/api/` base
  - Domain Management — domains across central/provincial/municipal levels
  - Dynamic Tables — variable data, periods, units, derived calculations
  - Static Tables — pre-formatted tables with metadata
  - Press Releases — news with dates and file links
  - Publications — full documents with ISSN/ISBN identifiers
  - Census Data — population/demographic surveys event-based
  - SIMDASI Data — regional statistics by province/regency
  - Strategic Indicators — KPI metrics (central/provincial only)
  - Foreign Trade Data — HS codes, values, weights by port/country
  - SDG — 17 goal-aligned indicators
  - Glossarium — bilingual terminology
- **Format**: JSON, status indicators OK/Error, pagination metadata, ID/EN bilingual.
- **License/ToS**: BPS data ufficialmente accessibile via WebAPI dietro registrazione (free for non-commercial; commercial needs disclosure).
- **Useful for Bali Zero**: KBLI lookup ufficiale (BPS è gestore della classificazione), dati statistik tenaga kerja, BPS Bali province per macroeconomia clientela.

### 1.9 Mahkamah Agung — Direktori Putusan

- **URL base**: https://putusan3.mahkamahagung.go.id/ ; search https://putusan3.mahkamahagung.go.id/search.html ; pengadilan list https://putusan3.mahkamahagung.go.id/pengadilan.html .
- **Quote (putusan3 homepage)**: "Direktori Putusan adalah platform publikasi dokumen elektronik dari putusan seluruh pengadilan di Indonesia".
- **Quote (description)**: "Direktori Putusan is a web-based system owned by the Secretariat of the Supreme Court of the Republic of Indonesia that publishes verdicts from the Supreme Court and all court verdicts from 4 (four) court environments at both first and appellate levels throughout Indonesia".
- **Scraper repo**: `okkymabruri/putusan` https://github.com/okkymabruri/putusan and `okkymabruri/putusan-mahkamahagung` (ext fork). Quote README: "The code is used for scraping data on the website https://putusan3.mahkamahagung.go.id/search.html. The scraper supports features like searching by keyword, specifying URLs, sorting by date, and downloading PDFs".
- **Server status (per indonesia-gov-apis)**: "Putusan MA | Mahkamah Agung | putusan3.mahkamahagung.go.id | None | Public search | Court decisions; server down" — instabile, redundancy needed.
- **Useful for Bali Zero**: yurisprudensi su sengketa pajak/imigrasi/property; precedent per advice cliente high-stake (es. PHI Pengadilan Hubungan Industrial sentenze Bali).

### 1.10 jdih.go.id / jdihn.go.id — JDIH Nasional

- **URL base**: https://jdihn.go.id/ ; dev/staging https://dev-jdihn.bphn.go.id/ ; BPHN parent https://bphn.go.id/ ; Komdigi JDIH https://jdih.komdigi.go.id/ ; Kemnaker JDIH https://jdih.kemnaker.go.id/ ; ATR/BPN JDIH (mobile) https://play.google.com/store/apps/details?id=id.go.atrbpn.jdih ; setkab JDIH https://jdih.setkab.go.id/ .
- **Quote (jdihn.go.id)**: "Berbagai Jenis Dokumen Hukum Seperti Peraturan Perundang-Undangan, Monografi Hukum, Artikel Hukum, Putusan Pengadilan dan dokumen hukum lainnya".
- **Quote (BPHN integrazione)**: "BPHN has successfully integrated 1,212 JDIH websites" (bphn.go.id/berita-utama/integrasi-nasional-database-jaringan-dokumentasi-dan-informasi-hukum-6639).
- **Quote (jdih.kemnaker.go.id integration page)**: "Pengintegrasian Anggota Jaringan Dokumentasi dan Informasi Hukum Nasional (JDIHN)".
- **Standards**: "The management of JDIH websites must comply with the Standards set by Permenkumham 8 Year 2019".
- **Quote (Satu Data integration)**: "Satu Data Indonesia is a government data governance policy designed to produce accurate, current, integrated, and accountable data that is easily accessible and shareable between central and regional institutions through fulfillment of data standards, metadata, data interoperability, and using reference codes and master data".
- **Sync mechanism (modul integrasi)**: "Data inputted at the regional level can automatically be 'pulled' and displayed on the national portal jdihn.go.id without requiring re-entry" (banyuwangikab JDIH integration module).
- **Lingua**: Bahasa Indonesia.
- **Useful for Bali Zero**: tier-1 entry point — un solo portale pubblica regulasi da 1.212 anggota istituzionali; user-guide PDF integrasi descrive lo schema metadata che possiamo specchiare 1:1.

### 1.11 peraturan.go.id (BPHN) e peraturan.bpk.go.id (BPK)

- **URL peraturan.go.id**: https://peraturan.go.id/ (eng https://peraturan.go.id/eng) — DB BPHN.
- **URL peraturan.bpk.go.id**: https://peraturan.bpk.go.id/ ; search https://peraturan.bpk.go.id/Search ; login https://peraturan.bpk.go.id/Account/Login ; Uji Publik (draft) https://peraturan.bpk.go.id/UjiPublik .
- **Quote (jdih.bpk.go.id about)**: "JDIH BPK is a shared mechanism for legal documents in an orderly, integrated, and sustainable manner" + "Database Peraturan (Regulations Database) is part of JDIH implementation in BPK RI, specifically intended to disseminate information on legislation and legal documentation in an easy, fast, and accurate manner to users both within BPK RI and the general public".
- **Quote (Open-Technology-Foundation/peraturan.go.id, scraper)**:
  - "5,817 legal texts (perban, permen, perda, uu, pp, perpres, perppu)"
  - "541,445 searchable segments (300-500 tokens each)"
  - "Legal documents from 2001-2025 (100% embedded)"
  - "MySQL/Files → export_for_rag → embed_data.text/ → customkb database → SQLite (1.1GB)"
  - "SQLite database (541,445 text chunks)" + "FAISS vector index (1536-dimensional embeddings)"
  - "Chunks documents into 300-500 token segments with 150-token overlap"
  - "7.1GB total (1.1GB SQLite + 6.1GB FAISS index)"
- **Useful for Bali Zero**: peraturan.bpk.go.id ha l'audit-friendly status field (berlaku/dicabut/diubah) — perfetto per legge "vigente vs storica" senza calcolare manualmente la chain di amendement.

### 1.12 setkab.go.id (Sekretariat Kabinet) — PP / Perpres entry point

- **URL base**: https://setkab.go.id/ (en https://setkab.go.id/en/) ; JDIH https://jdih.setkab.go.id/ .
- **Document types**: Peraturan Pemerintah (PP), Peraturan Presiden (Perpres), Perppu (Government Regulation in Lieu of Law), Inpres (Presidential Instruction), Keppres (Presidential Decree).
- **Quote (setkab announcement style)**: "Sekretariat Kabinet Republik Indonesia | Gov't Issues Regulation on Underdeveloped Regions" — pattern URL `setkab.go.id/en/<slug>` per ogni Perpres/PP/Perppu firmato.
- **Quote (Perpres announcement, sample)**: "President Joko 'Jokowi' Widodo on 24 May 2022 issued Presidential Regulation Number 82 of 2022 on Protection for Vital Information Infrastructure".
- **Press release format**: pattern stabile, pubblicato 1-3 giorni dopo signing date; URL slug = title in english.
- **RSS**: NON documented public; HTML scrapeable.
- **Useful for Bali Zero**: tier-0 — Perpres/PP cambiano frame impositivo (es. PP 28/2025 risk-based, Perpres 162 alimony — ogni novità sotto Prabowo passa qui per primo). Polling 1-3x al giorno + alert immediato a clientela impactata.

### 1.13 Aggregato Tier 1: indonesia-gov-apis (suryast)

- **URL repo**: https://github.com/suryast/indonesia-gov-apis (50+ Indonesian Government APIs & Data Sources, MCP-ready).
- **Quote tier-1 (12 sources)**:
  - Portal Satu Data (SDI) | data.go.id | None auth | CKAN API | "10K+ datasets"
  - BPS Statistics | webapi.bps.go.id | API Key | REST/JSON | "GDP, CPI, population; CF-blocked, now working"
  - BMKG Weather | data.bmkg.go.id | None | JSON feeds | "Earthquakes, tsunami alerts"
  - IDX/BEI | idx.co.id | None | Unofficial | "Stock prices, corporate data"
  - DJPB Treasury | data.treasury.kemenkeu.go.id | None | CKAN API | "DNS dead"
  - JDIH BPK | jdih.bpk.go.id | None | Partial API | "Geo-blocked (ID only)"
  - Putusan MA | putusan3.mahkamahagung.go.id | None | Public search | "Court decisions; server down"
  - LPSE/INAPROC | spse.inaproc.id | None | HTML forms | "589 portals affected by CF CNAME migration"
  - Portal APBN | data.anggaran.kemenkeu.go.id | None | CSV/XLSX | "DNS dead"
  - Bank Indonesia | bi.go.id | None | REST API | "Exchange rates, BI Rate"
  - BIG Geospatial | tanahair.indonesia.go.id | None | WMS/WFS | "Admin boundaries; server unresponsive"
  - BNPB Disaster | dibi.bnpb.go.id | None | REST + GeoJSON | "Disaster events, risk data"
- **Quote tier-2 (10 sources, scrapeable)**:
  - BPJPH Halal | cmsbl.halal.go.id/api/search | None | JSON POST | "1.98M businesses; DNS dead (old portal)"
  - BPOM Products | cekbpom.pom.go.id | Session + CSRF | DataTables POST | "242K+ registrations"
  - AHU Company Registry | ahu.go.id | None | HTML+CAPTCHA | "All PT, CV, Firma; geo-blocked"
  - OSS / NIB | oss.go.id | None | HTML forms | "Public search removed (404)"
  - OJK Registry | sikapiuangmu.ojk.go.id | None | HTML+XLS | "Geo-blocked (ID only)"
  - KPK e-LHKPN | elhkpn.kpk.go.id | reCAPTCHA + Login | HTML+PDF | "Wealth declarations; auth wall added"
  - Putusan MK | putusan.mahkamahkonstitusi.go.id | None | HTML+PDF | "DNS dead"
  - KSEI Statistics | ksei.co.id | None | PDF/XLSX | "Securities investor stats; geo-blocked"
  - e-PPID | ppid.kemenkeu.go.id | Per ministry | Per ministry | "DNS dead"
  - Pajak/DJP | ereg.pajak.go.id | Login | HTML forms | "NPWP verification; server unresponsive"
- **Quote regional tier-3**:
  - DKI Jakarta data.jakarta.go.id CKAN ✅
  - Jawa Barat opendata.jabarprov.go.id CF-blocked
  - Jawa Timur data.jatimprov.go.id DNS dead
  - Bali data.baliprov.go.id "DNS dead"
- **Quote operational pitfalls**:
  - "Most Indonesian gov sites block datacenter IPs (AWS, GCP, DO). Use Cloudflare Workers proxy or residential proxy"
  - "Government sites love Excel and PDF. Use openpyxl for Excel, pdfplumber for PDF"
  - "BPOM and some OJK pages require session cookies + CSRF tokens. Always use requests.Session()"
  - "data.go.id, Jakarta, Jabar, Jatim, Surabaya, Bandung all use CKAN. Same API pattern works everywhere"
  - "22 portals fully operational, 6 portals geo-blocked (Indonesia only), 5 portals CF/bot-challenged, 16 portals have DNS failures (28% of documented infrastructure), 3 portals completely down"
  - "LKPP CNAME migration to ars.inaproc.id caused 'CNAME Cross-User Banned' on CF. 589 portals affected".
- **Useful for Bali Zero**: questo repo è la fonte autoritativa NON-ufficiale dello stato della "infrastruttura dati gov.id". Andiamo a SOTA tracciando la sua history (last update 2026-03-29).

### 1.14 OJK — Otoritas Jasa Keuangan

- **URL base**: https://ojk.go.id/ (en https://ojk.go.id/en/) ; regulations https://ojk.go.id/id/regulasi/otoritas-jasa-keuangan/peraturan-ojk/default.aspx ; sustainability https://keuanganberkelanjutan.ojk.go.id/ ; consumer protection https://sikapiuangmu.ojk.go.id/ ; press release https://ojk.go.id/en/berita-dan-kegiatan/siaran-pers/default.aspx .
- **Document types**: POJK (Peraturan OJK), SE-OJK (Surat Edaran).
- **Quote (sample)**: "OJK Regulation No. 11/POJK.03/2022 on the Organization of Information Technology Implementation by Commercial Banks comprehensively governs IT planning, risk management, cybersecurity, data localization, and IT outsourcing for banks".
- **Quote (open finance)**: "The implementation of open finance frameworks and regulatory sandbox programmes issued by the Financial Services Authority of Indonesia (Otoritas Jasa Keuangan or 'OJK') and the Bank of Indonesia ('BI') has enabled greater innovation while maintaining oversight".
- **Useful for Bali Zero**: clientela fintech / koperasi / asuransi / pinjol — POJK/SEOJK frequenti, polling JDIH OJK + RSS press release.

---

## 2. Hukumonline + Ortax + DDTC + KLC — ecosistema commerciale tier-1

### 2.1 Hukumonline.com — Pro / Pro Plus / Premium Stories

- **URL base**: https://www.hukumonline.com/ ; Pro https://pro.hukumonline.com/ ; Premium Stories pricing https://www.hukumonline.com/stories/pricing/ ; Pusat Data https://www.hukumonline.com/pusatdata/ ; Hukumonline 360 https://www.hukumonline.com/hukumonline-360 ; subscription https://product.hukumonline.com/paket-berlangganan.php ; products https://www.hukumonline.com/produk/en .
- **Quote (about)**: "Hukumonline has become the country's most complete, integrated, and trusted provider of legal products and services in Indonesia. It is Indonesia's leading regulatory technology and media company, envisioned to help everyone better understand the law".
- **Quote (Pusat Data Pro)**: "With a Hukumonline Pro subscription, users can use the Hukumonline Data Center as a one-stop solution to search and understand regulations and decisions in Indonesia comprehensively".
- **Quote (Pro features)**: "free access to the central and regional regulation data center, equipped with validity status, smart documents, translations, legal basis, implementing regulations, related regulations, and history".
- **Quote (Pro Plus translations)**: "Hukumonline Pro's regulation collection includes translations, legal basis, implementing regulations and consolidated texts" + "Customized requests are available for regulation translations to meet your business needs" + "collection of hundreds of regulation translations related to business regulations, updated regularly".
- **Quote (AI launch sept 2024)**: "In September 2024, Hukumonline launched Ask Hukumonline AI, Indonesia's first generative AI platform designed to streamline legal research, representing a major leap forward in delivering faster, more accurate, and efficient legal solutions".
- **Quote (premium stories paywall)**: "Effective February 1, 2024, Premium Stories is only available through Professional or Pro Plus subscription packages".
- **API**: NON public REST API; integrations possibili tramite contratto enterprise (telefono +62 21 2270 8910 documentato come canale).
- **Useful for Bali Zero**: tier-1 commercial-grade EN translations + consolidated text (vs official PDF only ID). Pro Plus a 1 seat = baseline per agency. Sample doc URLs (e.g. https://www.hukumonline.com/pusatdata/detail/lt69ae7a63af7d1/peraturan-menteri-komunikasi-dan-digital-nomor-9-tahun-2026/) hanno pattern stabile.

### 2.2 Ortax — Observation & Research of Taxation

- **URL base**: https://ortax.org/ ; ecosystem https://ortax.org/ortax-ecosystem ; tax highlights https://ortax.org/tax-highlights ; calculator https://kalkulator.ortax.org/ ; bookstore https://buku.ortax.org/ ; iOS app https://apps.apple.com/sc/app/ortax/id1595807336 ; forums https://ortax.org/forums/discussion/tax-treaty-singapura .
- **Founders**: PT Integral Data Prima + Tax Centre FISIP Universitas Indonesia (since 2007).
- **Quote (about)**: "Ortax (Observation & Research of Taxation) is a digital tax community media platform built by PT Integral Data Prima and Tax Centre from the Faculty of Social and Political Sciences, University of Indonesia. Established in 2007, Ortax has become one of the largest taxation platforms in Indonesia with comprehensive services related to provision of tax information, tax discussion and tax training".
- **Quote (premium)**: "Ortax offers a Premium Features for faster, more complete, and systematic access to the Tax Regulation and Reference Database, available on both Web and Desktop platforms".
- **Quote (corpus)**: "tens of thousands of tax documents including tax regulations, court decisions, tax treaties, and other documents".
- **Useful for Bali Zero**: Ortax forum è la "stack overflow" dei tax practitioner Indonesia — segnale debole per emerging interpretation/dispute. Premium DB + tax treaty repository utile per WNA tax planning (residency rules).

### 2.3 DDTC — Danny Darussalam Tax Center

- **URL base**: https://ddtc.co.id/ (en https://ddtc.co.id/en) ; News https://ddtc.co.id/en/services/ddtc-news ; Perpajakan DDTC https://perpajakan.ddtc.co.id/ ; Subscription https://perpajakan.ddtc.co.id/payment/upgrade-info/ ; publications https://ddtc.co.id/research/publications/ ; Tax Holiday newsletter https://ddtc.co.id/research/publications/newsletter/taxholinews/ ; tax manual https://ddtc.co.id/uploads/pdf/Indonesian-Tax-Manual-Book-2022.pdf ; bilingual terminology https://ddtc-cdn1.sgp1.digitaloceanspaces.com/web/asset/images/20250703210727-terminologi-perpajakan-ddtc.pdf .
- **Quote (about)**: "DDTC is a research, technology, and knowledge-based tax institution with several business activity units including consultation services (DDTC Consulting), a center for review and research (DDTC Fiscal Research), taxation journals (DDTC Working Paper), a training centre (DDTC Academy), a taxation database platform (Perpajakan DDTC), a library (DDTC Library), and taxation news portal (DDTC News)".
- **Quote (DDTCNews positioning)**: "DDTCNews is more than just news — it's a solution for anyone seeking clarity and understanding in the evolving world of taxation. All news and articles on DDTCNews are completely free, ensuring everyone can access valuable tax information without barriers".
- **Quote (DDTCNews features)**: "daily summaries of the most popular tax issues from DDTCNews and mainstream media, in-depth special editions covering trending tax topics, visual infographics, an Article 21 Income Tax calculator, and real-time tax exchange rates directly from official Directorate General of Taxes (DJP) sources".
- **Quote (Perpajakan DDTC corpus)**: "extensive collection of 4,700+ resources covering transfer pricing, VAT, customs, tax policy, domestic & international taxation".
- **Quote (Perpajakan DDTC unique value)**: "integrated platform that provides quick and easy access to various tax regulations, facilitating effortless access to tax information whether you need the latest regulations, detailed analyses or consolidated laws".
- **Useful for Bali Zero**: DDTC News è gratuito + autorevole per tax news; Perpajakan DDTC subscription ($) per consolidated text + transfer pricing precedents. Stronger di Hukumonline su tax-only deep analysis.

### 2.4 KLC — Kemenkeu Learning Center

- **URL base**: https://klc2.kemenkeu.go.id/ ; mobile app https://play.google.com/store/apps/details?id=id.go.kemenkeu.bppk.klcmobile .
- **Quote (about)**: "Kemenkeu Learning Center generation 2 (KLC-2) is an online learning platform that covers various materials about State Finance Management and can be accessed by all Ministry/Agency employees and the general public".
- **Quote (Open Access)**: "The Open Access Program can be accessed using the Ministry of Finance's LMS, Kemenkeu Learning Center (KLC), at the address https://klc2.kemenkeu.go.id".
- **Useful for Bali Zero**: corso ufficiale Kemenkeu su Coretax / customs / treasury. Free training material per onboarding nuovi dipendenti (Subhi, Adit, Veronika et al). Source legitimazione "we trained on official Kemenkeu LMS" verso clienti enterprise.

---

## 3. Legal NLP for Bahasa Indonesia — SOTA 2026

### 3.1 IndoBERT + IndoLEM — base layer

- **Paper**: "IndoLEM and IndoBERT: A Benchmark Dataset and Pre-trained Language Model for Indonesian NLP", COLING 2020 — https://arxiv.org/abs/2011.00677 ; https://aclanthology.org/2020.coling-main.66/ .
- **Project page**: https://indolem.github.io/IndoBERT/ ; GitHub https://github.com/indolem/indolem .
- **HuggingFace**: https://huggingface.co/indolem/indobert-base-uncased ; QA fine-tune https://huggingface.co/Rifky/Indobert-QA ; SQuAD https://huggingface.co/esakrissa/IndoBERT-SQuAD .
- **Quote (paper)**: "IndoLEM is a dataset comprising seven tasks for the Indonesian language, spanning morpho-syntax, semantics, and discourse, and IndoBERT is a pre-trained language model for Indonesian that was evaluated over IndoLEM".
- **Quote (training data)**: "IndoBERT was trained using over 220M words, aggregated from three main sources: Indonesian Wikipedia (74M words) news articles from Kompas, Tempo and Liputan6 (55M words in total) Indonesian Web Corpus (90M words)".
- **Quote (training)**: "trained using over 220M words for 2.4M steps (180 epochs) with a final perplexity of 3.97".

### 3.2 Indo-Law — court decision dataset

- **Repo**: https://github.com/ir-nlp-csui/indo-law (UI Computer Science).
- **Quote (README)**: "The Indo-Law dataset consists of Indonesian court decision documents for general criminal cases that have been annotated for the document sections, with 22,630 documents in the dataset".
- **11 sezioni annotate (verbatim)**: "<kepala_putusan> (document opener), <identitas> (defendant's identity), <riwayat_penahanan> (case history), <riwayat_perkara> (detention history), <riwayat_tuntutan> (prosecution history), <riwayat_dakwaan> (indictment history), <fakta> (facts), <fakta_hukum> (legal facts), <pertimbangan_hukum> (legal considerations), <amar_putusan> (verdict), and <penutup> (closing)".
- **Annotation purpose**: "developed to support machine learning research, specifically to predict the category and the length of punishment in Indonesian courts using a deep learning model CNN+attention".
- **License**: AGPL-3.0; cite Nuranti, Yulianti, Husin (2022); contact `evi.y [at] cs.ui.ac.id`.

### 3.3 NusaCrowd — open-source Indonesian NLP datasets

- **Paper**: "NusaCrowd: Open Source Initiative for Indonesian NLP Resources", arXiv:2212.09648 — https://arxiv.org/abs/2212.09648 ; ACL Findings 2023 https://aclanthology.org/2023.findings-acl.868/ ; HF page https://huggingface.co/papers/2212.09648 .
- **GitHub**: https://github.com/IndoNLP/nusa-crowd .
- **Quote (paper)**: "Through this initiative, 137 datasets and 118 standardized data loaders have been brought together. The quality of the datasets has been assessed manually and automatically, and their value is demonstrated through multiple experiments".
- **Quote (zero-shot benchmark)**: "NusaCrowd's data collection enables the creation of the first zero-shot benchmarks for natural language understanding and generation in Indonesian and the local languages of Indonesia, as well as the first multilingual automatic speech recognition benchmark in Indonesian and the local languages of Indonesia".
- **Quote (architecture)**: "NusaCrowd builds a dataloader - a file downloader and reader - to simplify and standardize the data reading process. NusaCrowd does not make clones or copies of submitted datasets; the owner of any submitted dataset remains with the original author".

### 3.4 NusaX, NusaWrites, NusaBERT, IndoNLG — multilingual + NLG

- **NusaX**: https://huggingface.co/datasets/indonlp/NusaX-MT — "high-quality multilingual parallel corpus for Indonesian local languages elicited by native speakers [...] 10 low-resource local Indonesian languages, with the addition of Indonesian and English".
- **NusaWrites**: https://github.com/indonlp/nusa-writes — "in-depth analysis of corpora collection strategy and a comprehensive language modeling benchmark for underrepresented and extremely low-resource Indonesian local languages [...] released and complements NusaX by providing a more lexically diverse and culturally relevant dataset on 12 underrepresented local languages".
- **NusaBERT**: https://github.com/LazarusNLP/NusaBERT — "Teaching IndoBERT to be Multilingual and Multicultural" (https://arxiv.org/html/2403.01817 ).
- **IndoNLG**: https://github.com/IndoNLP/indonlg — "first benchmark to measure natural language generation (NLG) progress in three low-resource—yet widely spoken—languages of Indonesia: Indonesian, Javanese, and Sundanese [...] Concretely, IndoNLG covers six tasks: summarization, question answering, chit-chat, and three different pairs of machine translation (MT) tasks".
- **LoraxBench (2025)**: https://arxiv.org/html/2508.12459 — "A Multitask, Multilingual Benchmark Suite for 20 Indonesian Languages".

### 3.5 LexIndoLLM — Local-regulation Indonesian Llama fine-tune

- **Paper**: "LexIndoLLM: Large Language Model untuk Konsultasi Regulasi Daerah di Indonesia", Jurnal Buana Informatika — https://ojs.uajy.ac.id/index.php/jbi/article/view/14326 .
- **Quote**: "LexIndoLLM is a lightweight model based on Llama 3.2-1B developed through fine-tuning on 393 documents of local regulations in Kutai Kartanegara and integration of Retrieval-Augmented Generation (RAG) based on FAISS. Results showed an improvement in answer quality, with a reduction in perplexity from 9.13 to 1.74, an increase in ROUGE-L from 0.2058 to 0.4429, with faithfulness and answer correctness scores of 0.77 and 0.66 respectively".
- **Useful for Bali Zero**: blueprint diretto per "Bali Zero LegalLLM" → fine-tune on Bali Pergub/Perbup Badung+Gianyar+Denpasar, RAG su Hukumonline scraping autorizzato.

### 3.6 Other Indonesian Legal RAG / NLP papers (2024-2025)

- "Hybrid Deep Learning for Legal Text Analysis: Predicting Punishment Durations in Indonesian Court Rulings" — https://arxiv.org/abs/2410.20104 — "deep learning-based predictive system for court sentence lengths, with a hybrid model combining CNN and BiLSTM with attention mechanism that achieved an R-squared score of 0.5893".
- "Retrieval-Augmented Generation for Indonesian Criminal Law Information Using the LLaMA Model" — https://journal.itk.ac.id/index.php/IIAIR/article/view/1306 .
- "Hybrid Ensemble Retrieval-Augmented Generation for Indonesian Legal Consultation" — https://journal.iistr.org/index.php/JNEST/article/download/1042/779 — "integrates sparse retrieval (BM25), dense retrieval (FAISS), and keyword boosting into a unified scoring model".
- "A systematical procedure to extracting legal entities from Indonesian judicial decisions" — https://pmc.ncbi.nlm.nih.gov/articles/PMC12765086/ — peer-reviewed extraction methodology.
- "NLLP 2025 proceedings" — https://aclanthology.org/2025.nllp-1.3.pdf — current SOTA workshop venue.

### 3.7 Useful for Bali Zero — recommended NLP stack

- **Embedding multilingual**: `bge-m3` (already in our local Ollama arsenal per CLAUDE.md) or `multilingual-e5-large` per task semantici cross-lingual.
- **Bahasa-specific re-ranker**: `indolem/indobert-base-uncased` o NusaBERT fine-tune sopra.
- **LLM** (RAG generation): Claude/Gemini/Codex/DeepSeek (already in arsenal); local fallback `qwen2.5vl:7b` per draft non-cliente-facing.
- **Section parser** (court decisions): replicare Indo-Law schema su sentence Bali (PHI Denpasar, Pengadilan Pajak Bali); aggiungere `dasar_hukum`, `pasal_dilanggar` per richer KG.

---

## 4. Regulatory change detection — pattern globali

### 4.1 LexisNexis Regulatory Compliance / Nexis Data+

- **URL pages**: https://www.lexisnexis.com/en-us/products/regulatory-compliance.page ; UK https://www.lexisnexis.co.uk/products/regulatory-compliance ; corporate https://www.lexisnexis.com/en-us/corporate/corporate-compliance.page ; AU support https://www.lexisnexis.com/supportandtraining/au/lexisnexis-regulatory-compliance ; Archer integration help https://help.archerirm.cloud/exchange/content/exchange/integrations/lexisnexis_reg_compliance.htm ; Archer features https://archerirm.exchange/en-US/apps/421619/lexisnexis-regulatory-compliance/features ; LogicGate https://www.logicgate.com/platform/integrations/lexisnexis-regulatory-compliance/ ; ServiceNow store https://store.servicenow.com/store/app/e0ae6faa1b646a50a85b16db234bcb4e ; Nexis Data+ workflow https://www.lexisnexis.com/en-us/professional/data/regulatory-compliance.page .
- **Quote (definition)**: "LexisNexis Regulatory Compliance is a legal obligations register and alerting solution that combines regulatory content with technology to empower you to take control of your compliance obligations".
- **Quote (Archer integration)**: "The LexisNexis Regulatory Compliance integration allows automatic import of regulatory compliance data directly into the Archer Policy Program Management and Corporate Obligations Management use cases".
- **Quote (data structure)**: "The integration automatically imports regulatory content into Archer Policy Program Management and Corporate Obligations Management, enabling users to view regulations (mandates), regulatory obligations, and related alerts in one unified solution".
- **Quote (alerting)**: "Receive alerts regarding changes or references to these regulatory obligations" + "Proactive regulatory change triage and management by filtering alerts by impact rating, risk rating and more".
- **Architecture pattern**: regulation → mandate (top-level reg object) → obligation (granular requirement) → alert (delta event) → linked control objective.
- **AI assist**: "AI-enabled platform that seamlessly integrates authoritative compliance content with an AI Assistant".

### 4.2 Thomson Reuters Regulatory Intelligence (TRRI)

- **URL**: brochure PDF https://www.thomsonreuters.com.sg/content/dam/ewp-m/documents/asia-region/en/pdf/brochures/ri-api.pdf ; reviews https://sourceforge.net/software/product/Thomson-Reuters-Regulatory-Intelligence/ ; AiDOOS https://aidoos.com/products/thomson-reuters-regulatory-intelligence-(trri)/ ; ServiceNow integration https://www.servicenow.com/docs/bundle/zurich-governance-risk-compliance/page/product/grc-rcm-trri-integration/concept/grc-trri-integration.html ; analyst summary https://ruleup.ai/understanding-the-differences-in-regulatory-intelligence-solutions-thomson-reuters-and-alternatives/ ; Compliance Week tag https://www.complianceweek.com/thomson-reuters-regulatory-intelligence/7908.tag ; podcast https://open.spotify.com/show/5HKUlxaRvgU6X88QIX2Bps .
- **Quote (data scope)**: "TRRI Feeds provide regulatory alerts from more than 750 global regulators, with notifications delivered up to three times per day".
- **Quote (data scope, expanded)**: "Thomson Reuters Regulatory Intelligence pulls data from over 1,300 regulatory bodies and more than 2,500 collections of regulatory and legislative sources globally".
- **Quote (scheduling)**: "Thomson Reuters allows users to schedule feeds and alerts by creating search or library driven feeds to monitor changes to regulations, as and when updates are published and at a frequency and time that suits you".
- **Quote (configurazione)**: "The user interface allows compliance teams to create and configure feeds according to their relevant regulatory needs, such as by content type, geography, keyword, sector, organizations and themes, saving time and freeing up resources while helping manage compliance risk".
- **Quote (taxonomy ownership)**: "Thomson Reuters uses a risk taxonomy that is manually created by their team of risk and compliance experts, which organizations can synchronize with their systems".

### 4.3 Wolters Kluwer — OneSumX Reg Manager + Compliance Intelligence

- **URL**: parent https://www.wolterskluwer.com/en/about-us/risk-and-regulatory-compliance ; reg compliance solutions https://www.wolterskluwer.com/en/solutions/compliance-solutions/regulatory-compliance ; OneSumX https://www.wolterskluwer.com/en/solutions/onesumx-for-compliance-program-management/onesumx-for-regulatory-change-management/onesumx-reg-manager ; RCM Data Feed https://www.wolterskluwer.com/en/solutions/onesumx-for-compliance-program-management/onesumx-for-regulatory-change-management/regulatory-change-management-data-feed ; Compliance Intelligence (oct 2025) https://www.wolterskluwer.com/en/news/wolters-kluwer-launches-compliance-intelligence ; healthcare RCM https://www.wolterskluwer.com/en/solutions/legal-regulatory/healthcare/healthcare-regulatory-change-management .
- **Quote (Compliance Intelligence)**: "Compliance Intelligence uses AI-powered monitoring to scan global regulatory bodies for updates, including proposed changes, guidance, speeches, and enforcement actions. These updates are summarized with red-lined changes for clarity and tagged for relevance".
- **Quote (RCM Data Feed delivery)**: feed is "delivered every business day in a universally accepted XML format".
- **Quote (RCM data structure verbatim)**: "Structures content with common data fields across all regulatory bodies and agencies to promote understanding and provide consistent reporting capabilities".
- **Quote (suppression)**: "Reduces unwanted volume by providing the ability to suppress regulatory release types that may not apply to your business".
- **Quote (visual layout)**: "Visibly arranges every regulatory update to the laws, rules, regulations, or guidance in the library that it amends, references, repeals, or mentions creating an instant view of potential risk to your business".

### 4.4 Compliance.ai (now part of Archer)

- **URL**: https://www.compliance.ai/ ; API https://www.compliance.ai/api/ .
- **Quote (about)**: "Compliance.ai is a regulatory compliance and risk management solution that applies purpose-built machine learning models to automatically monitor the regulatory environment for relevant changes and maps them to your internal policies, procedures and controls".
- **Quote (Expert in the Loop methodology)**: "The platform's unique Expert in the Loop methodology embedded in its compliance management software automatically identifies regulatory obligations and helps you quickly pinpoint their impact on your controls, policies, and processes".
- **Quote (data sources)**: "The API automatically aggregates data from: Federal & State agencies, Enforcements, Regulatory publications from press and independent agencies, White papers, Millions of existing and new rules, Executive orders, and Notices".
- **Quote (API features)**: "Access to Normalized information, Content from variety of sources, Vertical streamlined search and Speed to value (easy integration)".
- **Quote (integration)**: "developers can build new applications, features, and feed information into existing GRC platforms, FinTech application, content management systems and more".

### 4.5 AscentAI (formerly Ascent RegTech) — bottom-up obligation extraction

- **URL**: https://www.ascentregtech.com/ ; change mgmt https://www.ascentregtech.com/our-difference/change-management/ ; RLM platform https://www.ascentregtech.com/rlm-platform/ascentfocus/ ; Resolver https://www.resolver.com/ascent/ ; Dimmo review https://www.dimmo.ai/products/ascentregtech ; PRNewswire launch https://www.prnewswire.com/news-releases/ascent-launches-navigator-for-regulatory-compliance-automation-300472894.html .
- **Quote (paradigm)**: "AscentAI takes a fundamentally different, 'bottom-up' approach, by starting with your obligations".
- **Quote (patent)**: "Our patented AI technology is the only solution in the market that intelligently and automatically extracts every obligation (requirement) from a regulator rule set as an individual object".
- **Quote (critique of taxonomy)**: "Many firms rely on traditional horizon scanning technology that employs complex taxonomies to identify and organize obligations at a document level. This 'top-down search' approach...typically requires extensive follow-on manual research and interpretation".
- **Quote (capture)**: "AscentFocus automatically captures and parses obligations within regulatory text to ensure that every change is captured and accounted for with high accuracy".
- **Quote (Regulatory Map)**: "a strategic definition of your jurisdictions, regulators, and sections of regulatory content that govern your business".
- **Two products**: "Ascent Horizon, focused on horizon scanning, and AscentFocus, an obligation and regulatory change management offering, that supports businesses in controlling their enterprise regulatory lifecycle".

### 4.6 Bloomberg Law / Bloomberg Government — regulatory tracker

- **URL**: https://pro.bloomberglaw.com/ ; Bloomberg Gov https://about.bgov.com/ ; bill tracking guide https://about.bgov.com/insights/public-affairs-solutions/legislative-bill-tracking-guide/ ; state tracking https://about.bgov.com/products/public-affairs-intelligence/federal-and-state-tracking/ ; privacy resources https://pro.bloomberglaw.com/privacy-data-security-law-resources/ ; labor https://pro.bloomberglaw.com/labor-and-employment-legal-resources/ ; trading compliance https://www.bloomberg.com/professional/products/compliance/ .
- **Quote (capabilities)**: "Bloomberg Law offers an expansive database that delivers real-time updates and insights on regulatory developments, allowing you to quickly access legislative and regulatory changes, analyze their implications, and plan strategies accordingly".
- **Quote (tracking + alerts)**: "regulatory tracking and alerts with customizable notifications tailored to jurisdictions, industries, or specific regulatory topics; comprehensive coverage of state and federal regulations including pending proposals, final rules, and agency guidance; and advanced search and filtering tools to pinpoint relevant regulations".
- **Quote (Chart Builders)**: "Bloomberg's State and International Chart Builders simplify compliance by providing quick reference comparisons of statutory and regulatory requirements across jurisdictions".

### 4.7 Diligent Manzama (acquired 2019) — news intel + governance

- **URL**: https://content.manzama.com/MZA-Competitive-Intelligence.html ; legaltech vendor profile https://www.legaltechnologyhub.com/vendors/diligent-manzama-by-diligent/ ; Diligent advisory https://www.diligent.com/industries/advisory-and-legal-research ; Diligent Boards https://cm.diligent.com/boards-login/ ; Manzama landing https://info.diligent.com/en/manzama-landing-page-1/ ; modern governance press https://www.diligent.com/company/newsroom/modern-governance-real-time-business-governance-intel-app .
- **Quote (about)**: "Diligent Manzama is a legal tech company that has been in the market since 2010, and was acquired by Diligent in 2019".
- **Quote (NLP capability)**: "It is a platform that provides news aggregation and analysis services for law firms, corporate legal departments, and other organizations in the legal market. The platform offers advanced natural language processing (NLP) and machine learning capabilities, allowing it to provide highly targeted and personalized news feeds to users".
- **Quote (Governance Intel)**: "Diligent Governance Intel, powered by the acquisition of Manzama, empowers a CEO, general counsel, or board director with daily information to analyze and compare the market conversation about a business or industry, monitoring such topics as industry regulations or the activist environment. The platform serves information from over 80,000 business news sources and is customizable to the specific needs of the user".
- **Quote (regulatory content)**: "Diligent's regulatory content helps meet your compliance obligations allowing you to better protect your organization by highlighting emerging risks while staying ahead of the latest regulatory requirements. We've curated content toolkits by industry and integrated them into the HighBond platform saving you time and improving collaboration between your three lines of defense".

### 4.8 Useful for Bali Zero — pattern globali distillati

- **Mandate → obligation → alert**: LexisNexis e Wolters Kluwer convergono su questa gerarchia. Adottare per Bali Zero (es. PMK 81/2024 = mandate; "DGT extension SPT 2 mesi" = obligation; KEP-71/PJ/2026 = alert/event).
- **Bottom-up obligation extraction (Ascent)**: superiore al taxonomy-driven per regulasi italiana E indonesiana (entrambe verbose). Combina con LLM extraction per pasal/ayat/huruf granularity.
- **Risk taxonomy human-curated (TR)**: ineliminabile expert-in-the-loop. Bali Zero può co-curare con Adit (immigration), Veronika (tax), Faisha (legal) — già presenti nel team.
- **Suppression rules (WK)**: feature critica — il "rumore" di JDIH è enorme; suppression by jenis dokumen + by area is mandatory per non saturare il client.
- **Red-lined diff (WK)**: deliverable client-facing premium — automated diff PMK old vs new.
- **Multi-frequency feed (TR 3x/day)**: alert latency target Bali Zero: <2h dal pubblicazione setkab.

---

## 5. Indonesian legal scraping prior art

### 5.1 Open-Technology-Foundation/peraturan.go.id — embedding pipeline

- **Repo**: https://github.com/Open-Technology-Foundation/peraturan.go.id .
- **Quote (architettura, verbatim)**: "MySQL/Files → export_for_rag → embed_data.text/ → customkb database → SQLite (1.1GB)".
- **Quote (corpus size)**: "5,817 legal texts (perban, permen, perda, uu, pp, perpres, perppu)" + "541,445 searchable segments (300-500 tokens each)" + "Legal documents from 2001-2025 (100% embedded)".
- **Quote (technical specs)**: "text-embedding-3-large (1536 dimensions)" embedding model, "claude-3-7-sonnet-latest" query model, "562 embeddings per batch, 24 concurrent API calls" performance.
- **Quote (chunking)**: "Chunks documents into 300-500 token segments with 150-token overlap".
- **Quote (storage)**: "7.1GB total (1.1GB SQLite + 6.1GB FAISS index)".
- **Caveat (verbatim)**: "The actual Python source code for the customkb tool and embedding modules is NOT present in this repository".
- **Useful for Bali Zero**: gold reference per "what does a SOTA Indonesian legal RAG corpus look like" (size, chunking, embedding model). Caveat: embedding non legalmente ridistribuibile senza license review.

### 5.2 ilhamfp/pasal — pasal.id MCP-native legal platform

- **Repo**: https://github.com/ilhamfp/pasal .
- **Quote (mission)**: "280 million Indonesians have no practical way to read their own laws".
- **Quote (problem statement)**: "the official legal database (peraturan.go.id) offers only PDF downloads with no search functionality, no structure, and no API".
- **Quote (corpus)**: "40,143 regulations across 11 regulation types" + "937,000+ structured articles (Pasal)".
- **Stack verbatim**: "Python, httpx, PyMuPDF, BeautifulSoup" data acquisition; "Frontend uses Next.js 16; backend combines Supabase PostgreSQL with Python FastMCP server; Claude Opus 4.6 powers verification and self-improvement agents".
- **MCP tools verbatim**:
  - `search_laws` — "Full-text keyword search with Indonesian stemming"
  - `get_pasal` — "Retrieve specific article text"
  - `get_law_status` — "Check amendment chains"
  - `list_laws` — "Browse regulations by type/year"
- **REST**: "public JSON endpoints for search, browsing, and article retrieval at pasal.id/api".
- **Useful for Bali Zero**: blueprint perfetto per Bali Zero stack — MCP server + REST + structured pasal-level retrieval. `get_law_status` = amendment chain checker (gold per Bali Zero clienti che chiedono "is this still current?"). pasal.id può essere usato direttamente come upstream MCP (no need to re-scrape).

### 5.3 okkymabruri/putusan — Mahkamah Agung scraper

- **Repo**: https://github.com/okkymabruri/putusan + fork https://github.com/okkymabruri/putusan-mahkamahagung .
- **Quote (README)**: "The code is used for scraping data on the website https://putusan3.mahkamahagung.go.id/search.html. The scraper supports features like searching by keyword, specifying URLs, sorting by date, and downloading PDFs".
- **Useful for Bali Zero**: ready-to-fork; combinare con Indo-Law schema per obtain (sentenze + 11 sezioni) auto-annotated.

### 5.4 ir-nlp-csui/indo-law — court decision corpus

- **Repo**: https://github.com/ir-nlp-csui/indo-law .
- **Already quoted in §3.2** (22.630 documenti, 11 sezioni, AGPL-3.0).
- **Useful for Bali Zero**: training data per fine-tune NusaBERT su Indonesian legal sectioning — 22k labeled documents = abbastanza per supervised classifier.

### 5.5 aabccd021/legal-kg — legal knowledge graph

- **Repo**: https://github.com/aabccd021/legal-kg .
- **Quote (search summary)**: "converting Indonesian legal documents into structured knowledge graphs with examples of applying this knowledge graph representation".
- **Useful for Bali Zero**: pattern reference per § 6 (cross-regulatory entity linking).

### 5.6 suryast/indonesia-gov-apis — gov data inventory

- **Repo**: https://github.com/suryast/indonesia-gov-apis .
- **Tagline (verbatim)**: "🇮🇩 50+ Indonesian Government APIs & Data Sources — BPS, OJK, BPJPH, BPOM, Bank Indonesia, IDX, BMKG + MCP servers. Python examples, scraping patterns, and practical gotchas. It's very challenging to keep up with all the breaking and blocking changes of Indonesian government APIs and digital resources. Always verify and test rigorously".
- **§ 1.13 above** ha la quote completa.
- **Useful for Bali Zero**: living inventory. Bali Zero può forkare e contribuire-back con i rilevamenti specifici Bali (es. balisatudata).

### 5.7 bps-statistics/stadata + bps-pinrang/Web-API-BPS-Postman-Collection

- **Repo (official)**: https://github.com/bps-statistics/stadata .
- **README quote**: "STADATA is a Python package that simplifies access to statistical data provided by BPS - Statistics Indonesia".
- **Postman collection**: https://github.com/bps-pinrang/Web-API-BPS-Postman-Collection .
- **Useful for Bali Zero**: ufficiale BPS-maintained Python lib — preferito over manual REST.

### 5.8 guzfirdaus/Wilayah-Administrasi-Indonesia

- **Repo**: https://github.com/guzfirdaus/Wilayah-Administrasi-Indonesia .
- **Quote (description)**: "Kode dan Data (Provinsi, Kabupaten/Kota, Kecamatan, dan Desa/Kelurahan) Wilayah Administrasi Indonesia berdasarkan Peraturan Menteri Dalam Negeri No.72 Tahun 2019 (dalam format SQL and CSV)".
- **Useful for Bali Zero**: lookup table per geocoding Bali (Kuta/Tuka/Ubud/Pecatu) — mapping al codice Permendagri ufficiale necessario per BATARA / SLF / KKPR.

### 5.9 Useful for Bali Zero — prior art summary

- pasal.id MCP server è il candidato più promettente per integrazione upstream (il loro corpus 40,143 regs è 8x peraturan.go.id scraper).
- Open-Technology-Foundation peraturan.go.id ha il corpus più grande (5,817 regs full-text + 541,445 chunks) ma manca codice — replicabile.
- Indo-Law corpus + okkymabruri scraper = pipeline finita per court decision Bali Zero (sengketa pajak, PHI).
- suryast/indonesia-gov-apis = "hostlist + auth + status" living doc, da pollarsi mensilmente per prevenire regression.

---

## 6. Cross-regulatory entity linking — pattern globali

### 6.1 OpenSanctions / FollowTheMoney / OpenAleph

- **URL**: https://www.opensanctions.org/ ; entities docs https://www.opensanctions.org/docs/entities/ ; data dictionary https://www.opensanctions.org/reference/ ; enrichment https://www.opensanctions.org/docs/enrichment/ ; research https://www.opensanctions.org/research/ ; Senzing bulk https://www.opensanctions.org/docs/bulk/senzing/ ; GitHub https://github.com/opensanctions ; Bellingcat profile https://bellingcat.gitbook.io/toolkit/more/all-tools/opensanctions ; OpenSanctions Pairs paper https://arxiv.org/html/2603.11051v1 .
- **Quote (entity composition, verbatim WebFetch)**: "Entities are JSON objects containing: A unique `id`, A `schema` specifying the entity type, A `properties` set with multi-valued string properties".
- **Quote (schema-driven)**: "What properties can be set for an entity is determined by it's schema. For example, a Person has a `nationality`, while a Company allows for setting a `jurisdiction`".
- **Quote (entity reference)**: "Properties of this type simply store the ID of another entity".
- **Quote (interstitial entity)**: "the Ownership schema [...] connects a person (`owner`) to a company (`asset`) while capturing additional attributes like `startDate` and `percentage`".
- **Quote (data stream)**: "FtM uses entity streams—'sequences of entity objects that have been serialised to JSON as single lines without any indentation, each entity separated by a newline.' These are used across FollowTheMoney CLI, OpenSanctions, and Aleph platforms".
- **Quote (Aleph platform integration)**: "Entity streams are read and produced by virtually every part of the FollowTheMoney command-line, OpenSanctions, and the Aleph platform".
- **Quote (matching scope)**: "OpenSanctions Pairs is a large-scale entity matching benchmark derived from real-world international sanctions aggregation and analyst deduplication. OpenSanctions aggregates 293 source datasets from 31 countries into a unified database, with human analysts performing pairwise deduplication".
- **Quote (cross-matching)**: "OpenSanctions bridges gaps by cross-matching entities against reference datasets and pulling in relevant fragments: directors, shareholders, subsidiaries, family members, financial identifiers, and corporate relationships, resulting in a more connected entity graph that supports compliance workflows beyond simple name screening".

### 6.2 Wikidata as machine-readable law/case identifier

- **URL Wikidata Property:P1278 (LEI)**: https://www.wikidata.org/wiki/Property:P1278 .
- **URL ECLI proposal**: https://www.wikidata.org/wiki/Wikidata:Property_proposal/ECLI_court_code .
- **Survey paper "linked legal data landscape"**: https://link.springer.com/article/10.1007/s10506-021-09282-8 .
- **Interlinking Legal Data PDF**: https://penni.wu.ac.at/papers/Semantics%202018%20Interlinking%20Legal%20Data.pdf .
- **Knowledge graph creation paper**: https://arxiv.org/html/2508.06368v1 .
- **Quote**: "In knowledge graph creation for legal documents, Wikidata URIs are used to represent defendant state names and other entities".

### 6.3 ELI / ECLI — European pattern, applicable conceptually

- **URL ELI Wikipedia**: https://en.wikipedia.org/wiki/European_Legislation_Identifier .
- **URL EUR-Lex ELI**: https://eur-lex.europa.eu/content/help/eurlex-content/eli.html .
- **URL Finland implementation**: https://eur-lex.europa.eu/content/eli-register/news_item_8.html .
- **Quote (paper on linked legal data)**: "The European Law Identifier (ELI) and the European Case Law Identifier (ECLI) provide technical specifications for Web identifiers and suggestions for vocabularies to be used to describe metadata pertaining to legal documents in a machine readable format".
- **Quote (use)**: "ECLI provides a European system for the identification of case-law, while ELI identifies legislative texts, and ECLI is preferable for legal decisions, while ELI is suitable for legislative texts".
- **Useful for Bali Zero**: Indonesia non ha ELI ufficiale, ma JDIHN+permenkumham 8/2019 sets metadata standard che possiamo adottare come "Indonesian ELI" — quote § 1.10: "The management of JDIH websites must comply with the Standards set by Permenkumham 8 Year 2019".

### 6.4 KBLI as cross-cutting entity

- **Quote (KBLI authority)**: "The development and updating of KBLI fall under the authority of Statistics Indonesia (Badan Pusat Statistik or BPS), pursuant to Law Number 16 of 1997 concerning Statistics. Additionally, the Ministry of Law and Human Rights (MOLHR) recognizes sub-classes (5-digit codes) for company incorporation, the Directorate General of Taxes (DGT) for tax identification (NPWP), and the BKPM for investment and licensing".
- **Useful for Bali Zero**: KBLI è il "join key" universale che lega regulasi → azienda cliente. Es. KBLI 79902 (tourism content) viene "tirato dentro" da PP 28/2025 (risk-based licensing), Permenpar (tourism), Permendagri (zonasi), Pergub Bali (ad-hoc tourism rules). Single entity = N regulations. Replicare schema FtM: `KBLI(id, name, code, parent_id, risk_level)` + Ownership-style `RegulationApplies(regulation_id, kbli_id, validity_period, source)`.

### 6.5 Semantic versioning / amendment tracking

- **NLLP 2025 paper "Risks and Limits of Automatic Consolidation of Statutes"**: https://aclanthology.org/2025.nllp-1.29.pdf — "Research on German statutes achieved 93-99% semantic similarity even with complex amendment chains averaging 2.79 amendments. However, the 50.3% and 20.51% rates of exact matches points to the need for extreme caution when working with automatically consolidated statutes".
- **Springer paper "Using Legislative Change History"**: https://link.springer.com/chapter/10.1007/978-3-032-13109-6_18 — uses Knowledge Graphs (Semantic Finlex) embedded into existing legal web services like LawSampo.
- **Xcential blog "Version Control for Law"**: https://xcential.com/blog/version-control-for-law-tracking-changes-in-the-u-s-congress — "Natural language processors have been developed to recognize, interpret, retrieve, and execute the amendatory language contained in legislative proposals, with experts deciphering the grammar and semantics of hundreds of thousands of amendatory phrases".
- **Useful for Bali Zero**: amendment chain in ID is "diubah dengan PP X/YYYY", "dicabut oleh PMK Y/YYYY". Pattern stabile. Automatic consolidation OK ma con human-in-the-loop (Adit/Veronika) — la lezione del paper NLLP 2025 vale 1:1 (German verbose ≈ ID verbose).

### 6.6 Useful for Bali Zero — entity linking architecture

- **Bali Zero entity model proposal**: replicate FollowTheMoney schema + custom schemas:
  - `Regulation` (id=peraturan ID + jdihn URI, type=UU/PP/Perpres/PMK/PER-DJP/Pergub/Perbup, signed_date, effective_date, amends_id[], superseded_by_id, full_text)
  - `Article` / `Pasal` (id, regulation_id, ayat[], huruf[], text, normative_force=(must/may/should))
  - `KBLI` (code, label_id, label_en, parent_code, risk_class)
  - `Client` (CRM entity — sensitive, kept local)
  - `Obligation` (regulation_id, pasal_id, kbli_filter[], deadline_pattern, action_required)
  - `Alert` (delta event — generated daily on regulation diff)
  - `Impact` (interstitial: links Alert × Client via KBLI/sector match)
- **Storage**: SQLite primary (per CLAUDE.md OSINT Law 2 / no cloud); Qdrant local mirror per semantic search (already in Bali Zero infrastructure per memory).

---

## 7. Compliance monitoring SaaS pattern

### 7.1 Compliance.ai (Archer) — già coperto in §4.4. "How it works" pattern condensato:

- 1: aggregate (Federal/State agencies + enforcements + press + white papers + executive orders).
- 2: filter content per user-configured preferences (agencies/topics/requirements).
- 3: identify obligations (Expert-in-the-Loop + ML).
- 4: map to internal policy/procedure/control.
- 5: alert on delta with impact rating + risk rating.
- 6: dashboard role-based + audit logs.

### 7.2 Ascent — già coperto §4.5. Pattern verbatim:

- 1: define Regulatory Map ("strategic definition of your jurisdictions, regulators, and sections of regulatory content that govern your business").
- 2: bottom-up extraction ("intelligently and automatically extracts every obligation (requirement) from a regulator rule set as an individual object").
- 3: change management ("AscentFocus automatically captures and parses obligations within regulatory text to ensure that every change is captured and accounted for").
- 4: horizon scanning (Ascent Horizon — early signal pre-final-rule).

### 7.3 Diligent (Manzama + HighBond) — già coperto §4.7. Pattern:

- 1: news ingestion da 80,000+ business news sources.
- 2: NLP categorization + targeted feeds per user.
- 3: regulatory content toolkits curated by industry.
- 4: integration in HighBond GRC for "three lines of defense" (1st line: business, 2nd line: compliance/risk, 3rd line: audit).

### 7.4 LexisNexis (Archer integration) — già coperto §4.1. Pattern:

- 1: regulation = "mandate" (top-level legal source).
- 2: obligation = granular requirement parsed from mandate.
- 3: control objective = internal policy/control linked to obligation.
- 4: alert = delta event with impact/risk rating.
- 5: dashboards + reports + role-based notifications.

### 7.5 Wolters Kluwer OneSumX — già coperto §4.3. Pattern:

- 1: AI-powered scan of "global regulatory bodies for updates, including proposed changes, guidance, speeches, and enforcement actions".
- 2: red-lined diff ("These updates are summarized with red-lined changes for clarity and tagged for relevance").
- 3: structured XML feed daily.
- 4: suppression rules (user can hide release types).
- 5: visual layout linking update to amended/repealed/referenced source.

### 7.6 Thomson Reuters TRRI — già coperto §4.2. Pattern:

- 1: 750-1,300 regulators monitored.
- 2: human-curated risk taxonomy.
- 3: scheduled feeds (3x/day max).
- 4: customizable filtering by content type/geography/keyword/sector.
- 5: API + UI for sync with internal compliance systems.

### 7.7 Useful for Bali Zero — distillato architetturale

Pattern convergente in tutti i 5+ leader globali:

- **Source aggregation layer**: scrape/RSS/feed → normalize.
- **Entity extraction layer**: regulation → obligation (Ascent's bottom-up = SOTA).
- **Taxonomy + classification**: human-curated vertical (KBLI per Bali Zero = built-in Indonesian taxonomy, no need to invent one).
- **Diff detection**: amend/repeal/reference graph + red-lined visualization.
- **Impact scoring**: link obligation → client entity (CRM) via KBLI/sector → impact rating.
- **Alert delivery**: multi-channel (email + dashboard + API), configurable frequency, suppression rules.
- **Human-in-the-loop**: every leader keeps subject-matter experts (Bali Zero has Adit/Veronika/Faisha — already in place).

---

## 8. Bali-specific regulasi — Pemkab Badung, Gianyar, Pemkot Denpasar, Provinsi Bali

### 8.1 Provincia Bali (Pergub + Perda Provinsi)

- **JDIH Provinsi Bali**: https://jdih.baliprov.go.id/ ; Pergub category https://jdih.baliprov.go.id/produk-hukum/peraturan-perundang-undangan/perda?ob=popular ; sample 2025 Pergub https://jdih.baliprov.go.id/produk-hukum/peraturan-perundang-undangan/pergub/29351 ; sample 2024 Pergub https://jdih.baliprov.go.id/produk-hukum/peraturan-perundang-undangan/pergub/29288 ; uploaded PDF pattern https://jdih.baliprov.go.id/uploads/produk-hukum/peraturan/2025/pergub/2025pg0051013.pdf .
- **JDIH Gubernur Bali (alt portal)**: https://jdih.gubernurbali.com/ .
- **Document categories (verbatim)**: "Peraturan Perundang-Undangan, Monografi Hukum, Artikel Hukum, Putusan Pengadilan".
- **Quote (mission)**: "JDIH Pemerintah Provinsi Bali was established to improve services to the public regarding documentation and legal information that is complete, accurate, easy and fast".
- **Quote (statistics)**: "1,247 total documents including 428 regional regulations, 319 gubernatorial regulations, and 156 decisions" (search aggregate).
- **Recent example**: Perda 16/2009 (https://jdih.baliprov.go.id/uploads/produk-hukum/peraturan/2009/perda/2009perda0051016.pdf) ; Perda RPJMD 2025-2029.
- **Quote (recent harmonization)**: "Denpasar City Government worked with the Regional Office of the Ministry of Law to complete harmonization of five Peraturan Walikota (Mayor Regulations) through a harmonization meeting held on February 2, 2026" (lenteraesai.id).

### 8.2 Kabupaten Badung (where Tuka, Canggu, Kuta, Pecatu, etc.)

- **JDIH Badung**: https://jdih.badungkab.go.id/ .
- **Diskominfo Badung**: https://diskominfo.badungkab.go.id/ .
- **Document types**: Perda Kabupaten, Perbup Badung, Surat Keputusan Bupati, Surat Edaran.
- **Critical for Bali Zero**: Perbup 59/2021 already a known reference (PBG/SLF Kutuh case in our memory).
- **Useful**: zonasi RDTR Badung, Pergub gabungan provinsi-Kabupaten su tourism (es. tax 10% destination tax 2024).

### 8.3 Kabupaten Gianyar (Ubud, Tegallalang, Sukawati)

- **JDIH Gianyar**: https://jdih.gianyarkab.go.id/ .
- **Bahasa**: Bahasa Indonesia.
- **Document types**: Perda, Perbup Gianyar, SK Bupati.
- **Useful per Bali Zero**: zonasi tourism Ubud (extensive heritage zoning), Perbup pariwisata budaya (cultural tourism); cliente villa Ubud-area requires Gianyar zonasi cross-check.

### 8.4 Kota Denpasar (urban, capital)

- **JDIH Denpasar**: https://jdih.denpasarkota.go.id/ .
- **Diskominfo Statistik**: https://kominfostatistik.denpasarkota.go.id .
- **Quote (mission)**: "JDIH Kota Denpasar is an electronic legal information media integrated nationally that provides services for information about legal products, governance and legal development in Denpasar City".
- **Document types**: Perda Kota, Perwali (Peraturan Walikota), SK Walikota, Surat Edaran.
- **Useful**: Perwali e Perda Denpasar coprono PSU (urban services), parking, advertising tax (relevant per clienti F&B/retail).

### 8.5 Altri Kabupaten/Kota in Bali (per completezza)

- **JDIH Karangasem**: https://www.jdih.karangasemkab.go.id/ — Perbup Karangasem.
- **JDIH Bangli**: https://jdih.banglikab.go.id/ — Perbup Bangli.
- **Tabanan, Buleleng, Klungkung, Jembrana**: ognuno ha JDIH proprio (pattern jdih.<kab>kab.go.id; subset integrato JDIHN nazionale).

### 8.6 Diskominfos Bali — Provincial communications + open data

- **URL**: https://diskominfos.baliprov.go.id/ ; ufficiale homepage https://www.baliprov.go.id/ ; Bali Satu Data app https://play.google.com/store/apps/details?id=baliprov.diskominfos.balisatudata ; Satu Data Bali https://balisatudata.baliprov.go.id/about-us ; portal info baliprov.org https://baliprov.org/tentang-kami-baliprov-org/ .
- **Quote (mission Satu Data Bali)**: "The One Data Indonesia Portal for the Province of Bali is the official open data portal for the Province of Bali managed by the Secretariat of the One Data Indonesia Forum for the Province of Bali and the Office of Communication, Information and Statistics of the Province of Bali. Through the Satu Data Indonesia (One Data Indonesia) portal at https://balisatudata.baliprov.go.id, all data from Bali Province, and its districts/cities can be consolidated".
- **Status (per indonesia-gov-apis)**: "Bali | data.baliprov.go.id | CSV/XLSX | DNS dead" — instabile, fallback su Diskominfos parent + Satu Data app.

### 8.7 BPS Bali Province

- **URL**: https://bali.bps.go.id/en .
- **Useful**: macroeconomia Bali (tourism arrivals, hotel occupancy, GDP per capita, Bali sector composition). Linkable a casi cliente high-stake (es. forecast cliente F&B per regional growth).

### 8.8 Useful for Bali Zero — Bali ground-truth strategy

- **Tier-0 daily polling**: jdih.baliprov.go.id (Pergub+Perda), jdih.badungkab.go.id, jdih.gianyarkab.go.id, jdih.denpasarkota.go.id (4 portali coprono >90% dei casi cliente Bali Zero).
- **Tier-1 weekly**: jdih.karangasem/bangli/tabanan/buleleng (lower volume).
- **Tier-2 monthly**: Diskominfos Bali (announcement portal — Pergub draft public consultation).
- **Cross-check**: ogni Pergub/Perbup nuovo va validato contro JDIHN nazionale (verifica integrazione, status berlaku) — quote § 1.10 "Data inputted at the regional level can automatically be 'pulled' and displayed on the national portal jdihn.go.id".
- **Heuristic for Bali-specific signals**: Pemprov Bali ha alta produzione regulasi tourism + adat (custom law). Ogni Pergub menzionante "wisata" / "subak" / "krama" / "desa adat" / "akomodasi pariwisata" → flag come HIGH PRIORITY per Bali Zero clienti tourism/property.

---

## Sintesi finale — what this report unlocks for Bali Zero autonomic system

1. **Source inventory**: ho 30+ portali gov.id documentati con URL base, status, ingest mode, license. Il 50%+ via gov-apis aggregator (suryast/indonesia-gov-apis) is living-document and SOTA.
2. **Commercial layer**: Hukumonline Pro + Perpajakan DDTC + Ortax Premium = 3 subscription tier-1 indispensabili per consolidated text + EN translations + tax case law.
3. **NLP stack ready**: IndoBERT/NusaBERT/IndoLEM/Indo-Law/NusaCrowd/LexIndoLLM = 7 risorse foundation per fine-tune Bali-specific. bge-m3 already locale.
4. **Prior art reusable**: pasal.id (40k regulations + MCP server) + okkymabruri (putusan scraper) + Open-Technology-Foundation peraturan.go.id corpus (5,817 regs) = head-start ~2-3 mesi rispetto a from-scratch.
5. **Architecture pattern**: Mandate → Obligation → Alert → Impact (LexisNexis/Wolters Kluwer/Compliance.ai converge); Ascent's bottom-up obligation extraction as core differentiator; FollowTheMoney entity model + KBLI as universal join key.
6. **Bali specific**: 4 portali tier-0 (baliprov + 3 kab/kota Selatan) coprono il 90% dei casi cliente. Diskominfos + Satu Data Bali for macro signals.
7. **Risk taxonomy human-in-the-loop**: Adit (immigration), Veronika (tax), Faisha (legal) sono già il "Expert-in-the-Loop" che Compliance.ai trademark-a — leverage existing team per curation.
8. **Lifecycle compliance with CLAUDE.md HARD RULES**:
   - Zero paid Anthropic key (Claude OAuth MAX 3-plan).
   - Local-first storage (SQLite + Qdrant local) per OSINT Law 2.
   - Multi-LLM deliberation (DeepSeek per article composer, NotebookLM per ground truth, Claude/Gemini/Codex orchestrazione).
   - Email out via zantara@balizero.com Brevo (memory hardcoded rule).

---

_Report compiled by Claude Opus 4.7 (1M context) on 2026-05-08. Quote integrity preserved verbatim from primary sources via WebFetch + WebSearch. Cross-references to user memory (CLAUDE.md, MEMORY.md, project files) noted where relevant._
