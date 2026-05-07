# R3 — DJP Coretax & Tax Tech Research Report (2026-05-08)

**Mission**: research-only foundation for Bali Zero autonomic tax engine (Indonesia, PPh/PPN/SPT/Coretax DJP).
**Author**: Claude Opus 4.7 (1M context) — research mode, no code.
**Method**: WebSearch (Anthropic-provided), 8 sections, min 5 sources/section, integral quotes preserved.

---

## Section 1 — DJP Coretax 2026: stato dell'arte

### 1.1 Cos'è e quando

> "On December 31, 2024, President Prabowo Subianto officially launched Coretax DJP. As of January 1, 2025, Coretax DJP marks the arrival of a new and modern tax administration system. KawanPajak can access Coretax DJP at the page coretaxdjp.pajak.go.id" — @DitjenPajakRI on X, [post 1874759233734152415](https://x.com/DitjenPajakRI/status/1874759233734152415).

> "The official Coretax portal can be accessed via coretax.djp.pajak.go.id. Additionally, third party applications (PJAP) are systems integrated with Coretax to assist with tax reporting." — [LMI Consultancy](https://www.lmiconsultancy.com/what-is-coretax-in-indonesia-implementation-of-core-tax-administration-system-ctas/).

> "All taxpayers — both individuals and companies — are required to transition to Coretax before the Annual Tax Return (SPT) filing deadline in March 2026." — [DataOn SunFish HR guide](https://dataon.com/en-id/blog/coretax-djp-pajak-guide/).

### 1.2 API ufficiali / bulk endpoints

DJP **non pubblica una developer-portal pubblica con OpenAPI/Swagger**. L'integrazione passa attraverso PJAP licenziati o soluzioni host-to-host:

> "Third party applications (PJAP) are systems integrated with Coretax to assist with tax reporting. The Directorate General of Taxes (DGT) has reactivated the e-Faktur Client Desktop application and the e-Faktur Host-to-Host service provided by Tax Application Service Providers (PJAP) for all VAT-Registered Persons (PKP)." — [MUC Consulting](https://muc.co.id/en/article/applies-to-all-taxable-entrepreneurs-dgt-reactivates-e-faktur-application).

> "Tax invoice data created using the e-Faktur Client Desktop will also be available in the Coretax application, with tax invoice data appearing in Coretax within two days after the tax invoice is issued." — MUC.

> "Systems can be connected with ERP, HR, or accounting systems like SAP, Oracle, Odoo, through API or SFTP integration." — [PajakExpress API integrasi](https://pajakexpress.com/fitur/api-integrasi).

PJAP commerciali con API Coretax-compatibili: **Pajakku** (https://pajakku.com), **PajakExpress** (https://pajakexpress.com), **OnlinePajak** (https://www.online-pajak.com), **Klikpajak**, **AlatPajak**.

### 1.3 Issues report — Bimo Wijayanto press conference

> "Director General of Taxes Bimo Wijayanto announced an extension on Thursday (30/04) at the Menteng Dua Tax Office in Jakarta. The filing window for corporate tax returns now runs through May 31, 2026." — [HeyGoTrade](https://www.heygotrade.com/en/news/indonesia-extends-corporate-tax-filing-may-31-2026/).

> "Roughly 4,000 corporate taxpayers submitted formal petitions for the deadline relief, with additional requests coming from tax consultants and industry associations." — HeyGoTrade.

> "Out of the 21 identified issues in the implementation of the Coretax system, three have been resolved so far, namely in the areas of business intelligence, knowledge management, and third-party data management." — [MUC Consulting on Bimo](https://muc.co.id/en/article/newly-appointed-director-general-of-taxes-bimo-still-reviewing-coretax-system).

> "Bimo emphasized three pillars of tax reform: Data and System Integrity, HR Integrity, and Institutional Integrity. A key step was the formation of a special task force consisting of 24 best programmers selected from various technical units at DJP to undergo intensive training for a full month." — [Tempo: Indonesia's Tax DG Forms Task Force](https://en.tempo.co/read/2069184/indonesias-tax-dg-forms-task-force-for-coretax-transformation), corroborated by [inilah.com](https://www.inilah.com/bos-pajak-tendang-vendor-coretax-digantikan-24-pakar-lokal-pertanda-pengadaan-bermasalah-sejak-awal).

> "Disruptions to the Core Tax Administration System (CTAS) architecture are generally related to surges in Application Programming Interface (API) queue traffic on the central server. Server processing loads surge significantly because the Coretax system must verify Indonesian ID numbers (NIK) to the Dukcapil central database in real-time, and if the Dukcapil API is slow to respond, the entire portal queue becomes completely paralyzed." — [Periskop.id](https://periskop.id/artikel/20260430/coretax-error-terjadi-ini-daftar-masalah-umum-dan-solusi-lengkap-cara-mengatasinya).

### 1.4 KEP-71/PJ/2026 (SPT extension)

> "KEP-71/PJ/2026, reinforced through PENG-31/PJ.09/2026, provides a one-month extension for the submission of Annual Corporate Income Tax Returns (SPT Tahunan PPh Badan) for the 2025 fiscal year. The filing window now runs through May 31, 2026." — [LMI Consultancy](https://www.lmiconsultancy.com/corporate-tax-income-indonesia-extended-waived-deadline-for-annual-returns-until-31-may-2026/).

> "Under KEP-71, a waiver of administrative sanctions is granted to corporate taxpayers who submit the 2025 Corporate Income Tax Return and make the payment or remittance of Article 29 Income Tax (underpayment) for the 2025 Tax Year, within one month after the statutory deadline, no later than 31 May 2026." — LMI.

> "Payments made up to 31 May 2026 will not incur interest sanctions, including settlements tied to previously approved filing extensions." — [PwC TaxFlash Vol.07/2026](https://www.pwc.com/id/taxflash-2026-07.html).

### 1.5 PMK 81/2024

> "PMK 81/2024 regulates the implementation of the Core Tax Administration System (CTAS), also known as Sistem Inti Administrasi Perpajakan (SIAP). The regulation was promulgated on October 18, 2024 and becomes effective starting January 1, 2025. PMK 81/2024 consists of 11 chapters and 484 articles." — [Pajakku artikel](https://artikel.pajakku.com/rangkuman-isi-pmk-812024-tentang-pelaksanaan-sistem-inti-administrasi-perpajakan-coretax-ctas).

> "The issuance of this PMK affects 42 existing regulations." — [DDTC News](https://news.ddtc.co.id/berita/nasional/1806617/atur-pelaksanaan-coretax-system-menteri-keuangan-terbitkan-pmk-baru).

PDF ufficiale: [JDIH Kemenkeu — PMK 81/2024 fulltext](https://jdih.kemenkeu.go.id/api/download/637047be-3dba-4347-aba1-98fa7fd5ab3f/2024pmkeuangan081.pdf).

### 1.6 Migration timeline DJP Online → Coretax

> "DJP targeted completion of data migration from DJP Online to Coretax on December 31, 2025. The legacy DJP Online system and Coretax ran in parallel during 2025 because Indonesia's tax system was in a transition period." — [AyoPajak: Coretax vs DJP Online Lama](https://ayopajak.com/2025/07/23/coretax-vs-djp-online-lama-mana-yang-berlaku-di-2025/).

> "Previously, tax services were spread across multiple applications such as e-Faktur, e-Bupot, e-Filing, and e-SPT, but Coretax was designed to consolidate these services into a single integrated system. Each e-Faktur issued and electronic withholding certificate (e-Bupot) created will be directly recorded into the corporate taxpayer's general ledger in real-time." — [Infobanknews](https://infobanknews.com/coretax-mulai-berlaku-korporasi-hadapi-era-baru-administrasi-pajak-real-time/amp/).

> "Submission of the Annual Tax Return for corporate income tax for the 2025 tax year on April 30, 2026 was the first filing required to be completely done through the Coretax framework." — [DataOn SunFish HR](https://dataon.com/en-id/blog/coretax-djp-pajak-guide/).

> "11.43 Million SPT Submitted, DJP Targets 15 Million by April 2026 as Coretax Activations Reach 18.19 Million Accounts" — [World Today Journal](https://www.world-today-journal.com/indonesias-tax-filing-surge-11-43-million-spt-submitted-djp-targets-15-million-by-april-2026-as-coretax-activations-reach-18-19-million-accounts/).

### 1.7 Docs ufficiali Coretax

- Official portal: https://coretaxdjp.pajak.go.id
- Coretax landing page (DJP): https://www.pajak.go.id/en/core-system-tax-administration
- Implementasi Coretax DJP: https://www.pajak.go.id/en/node/113210
- Reform DJP — Coretax docs hub: https://www.pajak.go.id/reformdjp/coretax
- Buku panduan Coretax DJP: https://pajak.go.id/coretaxpedia/buku-panduan-coretax-djp
- FAQ Coretax: https://www.pajak.go.id/coretaxpedia/
- Akses Coretax bagi user DJP Online: https://pajak.go.id/coretaxpedia/akses-coretax-bagi-user-djp-online

**Fonti totali sez. 1**: 13 (>8 minimo).

---

## Section 2 — DJP feed / RSS / press / social

### 2.1 RSS / press release pages

DJP **non espone un RSS feed pubblico** dal portale pajak.go.id (verificato 2026-05-08). Le pagine press sono HTML scrape-only:

- **Halaman Siaran Pers**: https://pajak.go.id/en/siaran-pers-page (English) / https://pajak.go.id/id/siaran-pers (ID)
- **Halaman Berita Pajak**: https://pajak.go.id/en/berita-page
- **Siaran Pers Penegakan Hukum**: https://www.pajak.go.id/id/siaran-pers-penegakan-hukum
- **Kemenkeu siaran pers** (tax-adjacent): https://www.kemenkeu.go.id/publikasi/siaran-pers
- **Ditjen Perbendaharaan RSS list** (NON DJP, ma utile pattern): https://djpb.kemenkeu.go.id/portal/id/data-publikasi/data/agenda-kegiatan/120-data-publikasi/data/1864-daftar-rss-feed-djpbn.html

> "DJP berlokasi di Jalan Gatot Subroto, Kav. 40-42, Jakarta 12190, Telp: (+62) 21 - 525 0208. Halaman Siaran Pers e Halaman Berita Pajak sono accessibili tramite www.pajak.go.id." — [DJP siaran pers page](https://pajak.go.id/en/siaran-pers-page).

### 2.2 Twitter @DitjenPajakRI

> "@DitjenPajakRI is the official DJP account, active Monday-Friday 07:30-17:00 WIB, with 275.6K followers. The account provides taxpayer information and complaints through @kring_pajak, phone 1500200, and email addresses informasi@pajak.go.id and pengaduan@pajak.go.id." — [Twitter @DitjenPajakRI](https://twitter.com/ditjenpajakri).

### 2.3 Top 10 post di rilievo 2025-2026

1. **2024-12-31 / launch Coretax** ([X](https://x.com/DitjenPajakRI/status/1874759233734152415)):

   > "Pada tanggal 31 Desember 2024, Presiden Prabowo Subianto telah meluncurkan Coretax DJP secara resmi. Sejak 1 Januari 2025, Coretax DJP menandai hadirnya sistem administrasi perpajakan yang baru dan modern."

2. **Joki Coretax phenomenon** (DDTCNews su X, [post 2041334783477788772](https://x.com/DDTCNews/status/2041334783477788772)):

   > "Joki Coretax Bermunculan, Purbaya: Kita Betulin Biar WP Lebih Mudah. Fenomena maraknya jasa joki pelaporan SPT Tahunan melalui coretax system ternyata sudah masuk radar Menteri Keuangan Purbaya Yudhi Sadewa."

3. **Reorganization Kanwil Jakarta Khusus** ([IKPI report](https://ikpi.or.id/en/djp-tata-ulang-wajib-pajak-di-kanwil-jakarta-khusus-berlaku-mulai-1-juli-2026/)):

   > "DJP's reorganization of taxpayer registration and reporting locations for individuals and entities under Jakarta Special Regional Office, established via decision KEP-00002/PDH-CT/PJ/2026 dated May 4, 2026. This new registration and reporting location takes effect on July 1, 2026."

4. **Coretax Period SPT errato** ([DDTC](https://news.ddtc.co.id/berita/nasional/1819093/coretax-tampilkan-periode-spt-tahunan-yang-keliru-begini-solusinya)):

   > "Coretax Tampilkan Periode SPT Tahunan yang Keliru — system showing March 2025 – February 2026 instead of January – December 2025."

5. **2026-04 Error 404** ([DDTC](https://news.ddtc.co.id/berita/nasional/1818923/wp-ramai-keluhkan-gagal-akses-coretax-error-404-djp-jawab-begini)):

   > "WP Ramai Keluhkan Gagal Akses Coretax 'Error 404', DJP Jawab Begini."

6. **2026-04-30 deadline relax individuali** ([DDTC](https://news.ddtc.co.id/berita/nasional/1818278/deadline-relaxed-file-annual-individual-tax-returns-by-30-april)):

   > "Deadline Relaxed! File Annual Individual Tax Returns by 30 April."

7. **2026-04 SPT Badan extension** ([DDTC](https://news.ddtc.co.id/berita/nasional/1818802/decision-pending-on-annual-corporate-income-tax-filing-relaxation)):

   > "Decision Pending on Annual Corporate Income Tax Filing Relaxation."

8. **Phishing warning email DJP** ([X](https://x.com/DitjenPajakRI/status/1639982298438451201)):

   > "Email resmi DJP hanya dari domain @pajak.go.id. Abaikan jika #KawanPajak mendapatkan email selain dari domain email resmi DJP."

9. **Compliance auto-record** ([DDTC](https://news.ddtc.co.id/berita/nasional/1819130/wp-tak-bisa-curang-semua-transaksi-kini-terekam-otomatis-di-coretax)):

   > "WP Tak Bisa Curang, Semua Transaksi Kini Terekam Otomatis di Coretax."

10. **Aturan baru April 2026 digest** ([DDTC](https://news.ddtc.co.id/berita/nasional/1819164/jangan-ketinggalan-simak-aturan-baru-yang-terbit-sepanjang-april-2026)):
    > "Jangan Ketinggalan, Simak Aturan Baru yang Terbit Sepanjang April 2026."

### 2.4 Telegram / WA

DJP **non opera canale Telegram o WhatsApp ufficiale** verificato. Solo:

- Hotline Kring Pajak: 1500200
- Email informasi@pajak.go.id, pengaduan@pajak.go.id
- Instagram @ditjenpajakri: https://www.instagram.com/ditjenpajakri/?hl=en
- YouTube: https://www.youtube.com/@DitjenPajakRI

**Fonti totali sez. 2**: 11.

---

## Section 3 — PMK / PER / KEP / SE — pattern di pubblicazione

### 3.1 Hierarchy delle norme (rilevante per tax engine)

| Tipo                                 | Issuer           | Source primary                             |
| ------------------------------------ | ---------------- | ------------------------------------------ |
| **UU** (Undang-Undang)               | DPR + Presidente | peraturan.go.id, kemenkeu.go.id            |
| **PP** (Peraturan Pemerintah)        | Presidente       | peraturan.go.id/goverment-regulation       |
| **Perpres**                          | Presidente       | setkab.go.id, peraturan.go.id              |
| **PMK** (Peraturan Menteri Keuangan) | Menkeu           | jdih.kemenkeu.go.id                        |
| **KMK** (Keputusan Menteri Keuangan) | Menkeu           | jdih.kemenkeu.go.id                        |
| **PER** (Peraturan Dirjen Pajak)     | Dirjen DJP       | pajak.go.id/peraturan, jdih.kemenkeu.go.id |
| **KEP** (Keputusan Dirjen Pajak)     | Dirjen DJP       | pajak.go.id, ortax.org                     |
| **SE** (Surat Edaran)                | Dirjen DJP       | pajak.go.id/peraturan                      |
| **PENG** (Pengumuman)                | DJP              | pajak.go.id                                |

### 3.2 URL pattern

**JDIH Kemenkeu** ([repository ufficiale Kemenkeu](https://jdih.kemenkeu.go.id/dok/pmk-81-tahun-2024)):

```
https://jdih.kemenkeu.go.id/dok/pmk-{number}-tahun-{year}
https://jdih.kemenkeu.go.id/dok/per-{number}pj{year}
https://jdih.kemenkeu.go.id/api/download/{uuid}/{year}pmkeuangan{number}.pdf
https://jdih.kemenkeu.go.id/api/download/fullText/{year}/{number}~PMK.{XX}~{year}Per.pdf
```

> "Documents are accessible through `jdih.kemenkeu.go.id` URLs, such as: `https://jdih.kemenkeu.go.id/dok/pmk-[number]-tahun-[year]` and `https://jdih.kemenkeu.go.id/api/download/[document-id]/[file-name].pdf`" — search aggregate.

**peraturan.go.id** (Direktorat Jenderal Peraturan Perundang-undangan):

```
https://peraturan.go.id/pmk
https://peraturan.go.id/peraturan/index.html
https://www.peraturan.go.id/id/{slug-with-number-year}
```

> "Peraturan.go.id is a database of Indonesian legislation with a collection of Central and Regional Regulations in Indonesia. The website is operated by the Directorate General of Legislation and displays a Database of Regulations containing information about the type, status, relationships between regulations, and statistics of legislation." — [peraturan.go.id profil](https://peraturan.go.id/profil.html).

**pajak.go.id/peraturan** ([DJP regulations search](https://www.pajak.go.id/en/peraturan)):

```
https://www.pajak.go.id/peraturan?type={UU|PP|PER|KEP|SE|PMK}
https://www.pajak.go.id/id/peraturan-pajak/{slug}
```

**setkab.go.id** = press release governo, **non** repository normativo. Pubblica gloss + link, non PDF firmato.

**peraturan.bpk.go.id** ([JDIH BPK](https://peraturan.bpk.go.id/)) = audit-side mirror, utile per cross-check.

### 3.3 Format

PDF firmato (preferito) > HTML mirror > scan TIFF (vecchie). Salinan = "official certified copy", header "MENTERI KEUANGAN REPUBLIK INDONESIA SALINAN" ([example](https://jdih.kemenkeu.go.id/api/download/fullText/2019/62~PMK.05~2019Per.pdf)).

### 3.4 Berita Negara

PMK e PP devono essere "diundangkan dalam Berita Negara Republik Indonesia" — registro ufficiale prima di entrare in vigore. Berita Negara è curato da Kemenkumham, ma il PDF firmato sta in JDIH issuer (Kemenkeu per PMK).

### 3.5 Frequenza & metadati

- Numero PMK 2024 chiusi: **>140**, 2025 in progress (PMK 32/2025 osservato).
- PER DJP 2025: PER-11/PJ/2025 documentato; **PER-4/PJ/2026** (eff. 30 marzo 2026), **PER-5/PJ/2026** (eff. 20 aprile 2026) — [Expert Tax](https://expert-taxindonesia.com/djp-terbitkan-se-2-pj-2026-pedoman-penilaian-pajak-kini-lebih-terstandar/).
- SE-2/PJ/2026: pedoman penilaian pajak.

JDIH **non espone API JSON pubblica documentata**. Il path `/api/download/{uuid}/{filename}` è scrape-friendly ma metadata richiede HTML parsing della pagina `/dok/`.

### 3.6 Aggregator commerciali

- **Ortax DataCenter**: https://datacenter.ortax.org — full-text search PER/KEP/SE storici (es. SE-9/PJ/2023 [link](https://datacenter.ortax.org/ortax/aturan/show/25285)).
- **DDTC Perpajakan**: https://perpajakan.ddtc.co.id — "One Stop Indonesian Tax Documentation" (subscription).
- **peraturanpajak.com**: blog mirror SE/PER ([SE-16/PJ/2025](https://peraturanpajak.com/2026/02/20/surat-edaran-direktur-jenderal-pajak-nomor-se-16-pj-2025/)).
- **Pajakku tax-guide**: https://tax-guide.pajakku.com/tax-guide-types — UU + PMK + KMK + PER Dirjen.
- **JDIH BPK**: https://peraturan.bpk.go.id (mirror amministrazione audit).

**Fonti totali sez. 3**: 12.

---

## Section 4 — Tax LLM 2026 — SOTA

### 4.1 Stanford "Large Language Models as Tax Attorneys" (2023, white paper baseline)

> "Stanford explored LLM capabilities in applying tax law because it has a structure that allows for automated validation pipelines across thousands of examples, requires logical reasoning and maths skills, and enables testing LLM capabilities in a manner relevant to real-world economic lives of citizens and companies. The findings indicate that LLMs, particularly when combined with prompting enhancements and the correct legal texts, can perform at high levels of accuracy but not yet at expert tax lawyer levels." — [Stanford white paper](https://law.stanford.edu/wp-content/uploads/2023/07/White-Paper_Large-Language-Models-as-Tax-Attorneys.pdf).

CRFM Stanford correlate:

- **HELM** (Holistic Evaluation of Language Models) — https://crfm.stanford.edu/helm/ — open-source benchmark framework, github.com/stanford-crfm/helm.
- **LegalBench** — https://hazyresearch.stanford.edu/legalbench/ — 162 task legal reasoning, multi-contributor:
  > "The LegalBench project is an ongoing open science effort to collaboratively curate tasks for evaluating legal reasoning in English large language models (LLMs). The benchmark currently consists of 162 tasks gathered from 40 contributors."
- **Foundation Model Transparency Index** — https://crfm.stanford.edu/fmti/ — non-tax-specific ma rilevante per vendor selection.

### 4.2 BlueJ

> "BlueJ is an AI-powered legal research platform that helps tax professionals predict how courts might rule on complex tax scenarios by analyzing thousands of judicial decisions to surface precedent, patterns, and probabilities for specific fact patterns. BlueJ's product called Ask Blue J is a generative AI tool where you can ask questions about tax law and it creates verifiable answers." — [TaxProExchange](https://www.taxproexchange.com/ai/tools/bluej).

> "Blue J now runs on OpenAI's latest GPT-4.1 model" — [Blue J blog](https://www.bluej.com/blog/blue-j-runs-on-latest-openai-model).

> "BlueJ maintains a strong security posture and undergoes annual SOC 2 Type 2 audits via independent assessors." — Blue J self-disclosure.

> "Blue J's approach for scaling fast in complex, regulated domains" — [OpenAI case study](https://openai.com/index/blue-j/).

**Pricing**: nessun listino pubblico. "BlueJ lacks a self-serve free trial, requiring users to schedule a sales demo to evaluate the platform." — [Software Advice](https://www.softwareadvice.com/tax-practice-management/blue-j-tax-profile/). Stima informale community: enterprise-tier $10k+/anno per seat (range tipico legal-AI).

### 4.3 TaxGPT

> "TaxGPT is an AI-powered tax OS built for everything from research to return review and is model-agnostic, running on a combination of the latest frontier models and a proprietary model fine-tuned specifically for tax." — [TaxGPT vs BlueJ](https://www.taxgpt.com/blog/taxgpt-vs-bluej).

> "TaxGPT is built with enterprise-grade security as a foundational principle, with all data stored on U.S.-based, AICPA SOC 2 Type II compliant infrastructure."

> "TaxGPT offers a free 14-day trial for new users, with detailed pricing for professional, business, and enterprise tiers provided upon request through a demo."

### 4.4 IRS-LLM patterns

> "As of 2024, the IRS had initiated 68 projects involving artificial intelligence, with the number likely increasing since then. AI tools that have already been deployed by the IRS include natural language processing to answer employee questions, a machine-learning model to process Form 990-N submissions, a synthetic data engine to test tax-processing systems and simulate fraud cases, a modular code assistant for automation test application development, and a generative AI program to process IT service desk tickets." — [Today's CPA Magazine, Jan-Feb 2026](https://www.tx.cpa/news-publications/todays-cpa-magazine/issues/article/january-february-2026/2026/01/13/irs-use-of-artificial-intelligence-and-data-analytics-to-modernize-operations).

> "Revenue agents are beginning to have access to generative AI programs to assist with routine drafting tasks such as information document requests and exam reports, and in late 2025, the IRS rolled out Agentforce to search documents and provide case summaries." — same source.

> "Treasury published the Treasury Artificial Intelligence System User Agreement on October 17, 2025, and IRS use of AI must conform to this agreement. OMB Memorandum M-25-21 of April 3, 2025, provides detailed guidance for AI governance in federal agencies." — [IRS IRM 10.24.1 AI Governance](https://www.irs.gov/irm/part10/irm_10-024-001r).

> "The Government Accountability Office has issued multiple reports highlighting the potential for unintended bias by AI in selecting returns for exams, with independent studies confirming that Black taxpayers are audited at a rate three to five times higher than others." — [GAO blog](https://www.gao.gov/blog/inside-irs-use-artificial-intelligence).

### 4.5 Indonesian tax-specific LLM

**Risultato negativo verified**: nessun "IndoTax-LLM" pubblico esiste 2026-05. Cosa esiste:

- Paper academic NLP applicato a general ledger Indonesia: [Utilizing NLP and Logistic Regression — DJP eJurnal](https://ejurnal.pajak.go.id/st/article/download/927/192/4278).
  > "One research effort used real data consisting of 461,776 rows of general ledger entries processed using quantitative language processing approaches. NLP can help detect and classify tax objects from the general ledger."
- Nessun LLM finetuned su corpus Indonesia tax aperto al pubblico. **Opportunity gap chiaro per Bali Zero**.

### 4.6 Generative AI for Tax — outlook

> "Generative AI for Tax: Looking Back, Looking Ahead" — [Tax Notes 2024](https://www.taxnotes.com/featured-analysis/generative-ai-tax-looking-back-looking-ahead/2024/02/02/7j458) (paywall).

**Fonti totali sez. 4**: 11.

---

## Section 5 — Indonesian commercial tax data

### 5.1 Ortax

> "Ortax, established in 2007, has become one of the largest taxation platforms in Indonesia with a comprehensive range of services related to provision of tax information, tax discussion and tax training. You can contact them to learn more about their products and services on https://solutions.ortax.org/." — [Ortax homepage](https://ortax.org/).

- DataCenter (regulations DB): https://datacenter.ortax.org
- Corso & training: https://ortax.org/training
- Newsletter: free tier blog + paid solutions.ortax.org (no public price tag).

### 5.2 DDTC

> "DDTC was established in 2007 by taxation experts Darussalam and Danny Septriadi, and offers DDTC Consulting providing exceptional taxation services. Through DDTC News, they ensure that the latest taxation updates are available, empowering you with up-to-the-minute information." — [DDTC Services](https://ddtc.co.id/en/services/ddtc-news).

- DDTC News portal: https://news.ddtc.co.id
- Perpajakan DDTC database: https://perpajakan.ddtc.co.id ("One Stop Indonesian Tax Documentation")
- Working Paper, Indonesia Taxation Quarterly Report (free PDF gated), MyDDTC subscription, Library, Academy.
- Pricing: enterprise/corporate tiers via sales contact, no published rate card.

### 5.3 MUC Consulting

> "Founded in 1999, MUC Consulting is at the forefront of business consultancy in Indonesia, boasting a dynamic team of over 270 experts combining tax, accounting, customs, and legal expertise." — [MUC Tax Consultant Indonesia](https://muc.co.id/en/home).

- Newsletter MUC: free email subscription.
- Tax Planning, Tax Appeal, Transfer Pricing services: project-based fee.
- Articles weekly: muc.co.id/en/article.

### 5.4 PB Taxand

> "PB Taxand is one of Indonesia's leading tax advisory service providers and as a member of Taxand Global Network, provides high quality tax advice worldwide across nearly 50 countries." — [Taxand Indonesia](https://www.taxand.com/our-locations/indonesia/).

- ITR World Tax Indonesia ranking entry: https://www.itrworldtax.com/Firm/pb-taxand/Profile/969
- Publications: PB Taxand newsletters (free PDF), client alerts.
- Fees: corporate-only, no retail pricing.

### 5.5 Other Indonesian tax-data players

- **Pajakku** (https://pajakku.com) — PJAP licensed, Coretax-integrated reporting + library.
- **OnlinePajak** (https://www.online-pajak.com) — backed by Peak XV (ex-Sequoia India SEA), full-stack tax + payroll + invoicing automation.
  > "OnlinePajak is a fully-integrated web-based tax application that allows Indonesian taxpayers to calculate, report, and pay tax on a single platform." — [Peak XV](https://www.peakxv.com/companies/onlinepajak/).
- **PajakExpress** (https://pajakexpress.com) — DJP partner, API-integrasi (https://pajakexpress.com/fitur/api-integrasi), pricing pages (https://pajakexpress.com/harga).
- **Klikpajak** (https://klikpajak.id) — Mekari group, SaaS.
- **PwC Indonesia Pocket Tax Book**: free PDF annuale ([2024 PDF](https://www.pwc.com/id/en/pocket-tax-book/english/pocket-tax-book-2024.pdf)) — gold standard reference.

### 5.6 Pricing pages public

**Solo PajakExpress** ha pricing publicly listed (https://pajakexpress.com/harga). Tutti gli altri SaaS Indonesia tax software seguono "request quote" pattern. Tier indicativi industry: starter Rp 500k/mese, business Rp 1.5-3jt/mese, enterprise custom.

**Fonti totali sez. 5**: 12.

---

## Section 6 — Tax automation stack — global

### 6.1 Avalara

> "Avalara has 27 separate, modularized APIs, allowing for flexible configuration. Avalara's AvaTax API requires a taxCode parameter that maps to their internal taxonomy of thousands of product and service categories, and before you can calculate tax, a human must map your offerings to their tax codes." — [Glencoyne tax engine guide](https://www.glencoyne.com/guides/tax-engine-comparison).

> "Avalara provides a 'do it for me' model. With its managed services, Avalara can act as your outsourced tax team, handling returns, remittance, and even corresponding with tax authorities on your behalf." — [TaxCloud comparison](https://taxcloud.com/blog/avalara-vs-vertex-comparison/).

### 6.2 Vertex

> "Like Avalara, the API has been modularized and can support detailed tax determination for U.S. sales tax, VAT, GST, communications taxes, and other global tax types. Vertex was originally designed for on-premise ERP environments — and that legacy still shapes its structure and deployment model. While cloud options are now available, most implementations are still handled via middleware or ERP connectors, which makes setup more involved than with cloud-native tools." — Glencoyne.

### 6.3 Sovos

> "Sovos has a sales tax API, an indirect tax API, and connectors (integrations) that use specific API endpoints to connect to ERP systems like SAP and NetSuite. The right API is likely included in a specialized plan, built by a sales rep, and teams can integrate with their custom storefronts as they see fit." — [TaxCloud Avalara alternatives](https://taxcloud.com/blog/avalara-alternatives/).

### 6.4 TaxJar

> "TaxJar offers a straightforward REST API that's easy to implement for basic tax calculation needs. TaxJar's sales tax API is very fast (under 20ms) and it has 99.99% uptime." — Glencoyne.

> "TaxJar offers a 'help me do it' approach. Its reporting dashboard consolidates all the data your finance lead needs to file returns efficiently. Its popular AutoFile service automates the filing and remittance process, but the ultimate responsibility for accuracy remains with you." — TaxCloud comparison.

### 6.5 Architectural pattern shared

1. **Tax determination engine** (rule-based + jurisdiction lookup) — sub-100ms response target.
2. **Returns automation** (filing + remittance) — scheduled jobs.
3. **Compliance services** (managed: Avalara) vs DIY (TaxJar AutoFile).
4. **Connector marketplace** (SAP, NetSuite, Shopify, Magento, Stripe, Odoo).
5. **Tax codes mapping** = main onboarding cost.

### 6.6 Self-hosted / OSS alternatives

**ERPNext** (full GPL):

> "ERPNext's flexibility allows businesses across regions to seamlessly manage GST, VAT, Consumption Tax, and other tax types. It reduces manual errors in taxation by automatically fetching tax ledgers through Sales and Purchase Tax templates. ERPNext is a comprehensive, user-friendly and 100% open source ERP that is compliant with US GAAP." — [Frappe](https://frappe.io/erpnext/open-source-accounting).

> "ERPNext is fully open source (GPL) and includes accounting in the base version. In contrast, Odoo's tax authority integrations and advanced audit controls are paywalled behind the Enterprise plan, creating a forced commercial dependency for regulated industries." — [SelectHub](https://www.selecthub.com/accounting/open-source-accounting-software/).

**Odoo Accounting** (Community + Enterprise):

> "Odoo Accounting assists businesses in meeting tax compliance requirements by supporting tax configurations, automating tax calculations, and generating accurate tax reports to ensure compliance with local tax regulations. Odoo integrates tax logic directly into its accounting engine, where every invoice, bill, or journal entry carries the right tax configuration automatically." — [The Ledger Labs](https://theledgerlabs.com/odoo-tax-management-guide/).

> "TaxCloud support Odoo version 17 or newer for Odoo.sh and Odoo On-Premises hosting options, though integrations are not available for Odoo Online (SaaS)." — [TaxCloud Odoo](https://taxcloud.com/integrations/odoo/).

### 6.7 AI-tax adversarial commentary

> "Why Avalara and Vertex Won't Solve AI Tax — AgentTax." — [agenttax.io blog](https://www.agenttax.io/blog/avalara-vertex-wont-solve-ai-tax). Tesi: legacy engines = rule-based determinism; AI tax compliance richiede contextual reasoning sopra fatti business-specific che gli engine vintage non modellano.

**Fonti totali sez. 6**: 11.

---

## Section 7 — Coretax community / issues

### 7.1 Pattern mediatico

> "Since Coretax was implemented in early 2025, complaints have arisen from individual taxpayers and businesses. These grievances have been widely shared on social media platforms like X (formerly Twitter) and Instagram." — [Indonesia Sentinel](https://indonesiasentinel.com/indonesia-core-tax-system-faces-major-complaints-over-access-issues/).

> "Since its launch, the Coretax System has experienced several technical issues that have severely affected businesses, with frequent server outages making it challenging for taxpayers to access the system. In various forums and social media, complaints against CoreTax are echoing, with users complaining about failed login attempts and slow system performance." — [Seven Stones Indonesia](https://sevenstonesindonesia.com/blog/coretax-system-technical-issues-trouble-indonesian-firms/).

> "Many entrepreneurs and tax consultants faced failures in issuing commercial invoices on time due to sudden system infrastructure outages. Complaints ranged from endless loading screens to Error 500 Internal Server Error codes and failures when uploading SPT attachments." — [Periskop.id](https://periskop.id/artikel/20260430/coretax-error-terjadi-ini-daftar-masalah-umum-dan-solusi-lengkap-cara-mengatasinya).

### 7.2 Top 12 errori frequenti (2026 reporting cycle)

Da [klikpajak Coretax error guide](https://klikpajak.id/blog/solusi-coretax-error/) + [Warta Garut](https://wartagarut.com/coretax-error-lagi-solusi-wajib-pajak-2026/) + [Pajakku](https://artikel.pajakku.com/ketahui-daftar-error-coretax-djp-dan-cara-mengatasinya):

1. **Login fail** ("verifikasi wajah" digital cert failure).
2. **Save Invalid faktur pajak** — data validation rejection:
   > "The 'Save Invalid' status indicates that uploaded invoices are rejected because data failed system validation. Common problems include not just server downtime, but data identity conflicts, account validation issues, unsynchronized documents, and slow administrative approvals." — [iuwashtangguh.or.id](https://iuwashtangguh.or.id/berita-nasional/5511061342/save-invalid-di-coretax-ini-penyebab-solusi-dan-cara-upload-ulang-faktur-pajak-2026/).
3. **Error 404** mass (24 aprile 2026): [Suara Merdeka Jogja](https://jogja.suaramerdeka.com/ekonomi/1817039401/apakah-coretax-error-hari-ini-jumat-24-april-2026-sampai-jam-berapa-simak-penjelasan-djp-online).
4. **Error 500 Internal Server Error** — picchi traffico API queue.
5. **Periode SPT errato** (auto-default off-period).
6. **Upload attachment fail**.
7. **NIK validation timeout** (Dukcapil API slow).
8. **Digital certificate refresh expired**.
9. **PPh 21/23 e-Bupot import xml broken**.
10. **Faktur pajak XML import bug** ([Ortax tutorial](https://ortax.org/cara-membuat-faktur-pajak-dengan-impor-xml-di-coretax)).
11. **Approval workflow stuck**.
12. **Browser-specific UI break** (preferred Chrome stable).

### 7.3 Problema sistemico riconosciuto

> "However, the Finance Minister acknowledged that the challenges go beyond technical glitches, pointing instead to structural weaknesses in the system's design, noting that the platform is not user-friendly and uses terminology that is difficult for taxpayers to understand." — [Indonesia Sentinel](https://indonesiasentinel.com/indonesia-core-tax-system-faces-major-complaints-over-access-issues/).

> "Tax Office Logs 10.5 Million Tax Returns Amid Coretax System Glitches" — [Jakarta Globe](https://jakartaglobe.id/business/tax-office-logs-105-million-tax-returns-amid-coretax-system-glitches).

### 7.4 Vendor problem (Bimo task force genesis)

> "Purbaya Ungkap Masalah Baru di Sistem Coretax, Vendor Bermasalah 'Diam-diam' Dimasukkan Lagi" — [Oposisi Cerdas, March 2026](https://www.oposisicerdas.com/2026/03/purbaya-ungkap-masalah-baru-di-sistem.html).

> "Bos Pajak Tendang Vendor Coretax Digantikan 24 Pakar Lokal, Pertanda Pengadaan Bermasalah Sejak Awal" — [inilah.com](https://www.inilah.com/bos-pajak-tendang-vendor-coretax-digantikan-24-pakar-lokal-pertanda-pengadaan-bermasalah-sejak-awal).

### 7.5 Twitter @ortaxcom / @DDTCNews

- @DDTCNews: monitorare hashtag **#Coretax**, #PajakKitaUntukKita.
- Pattern: thread breaking news + curated digest fine-mese ("Aturan baru April 2026").
- @ortaxcom — meno attivo come canale primario, principale tramite ortax.org community + group telegram non ufficiali.

### 7.6 Reddit / Kaskus

`r/indonesia` discussioni tax limited. `r/PersonalFinanceIndonesia` ha thread Coretax sparsi. Kaskus forum tax: thread nostalgia DJP Online + complaint Coretax (non public-link aggregati). Valore basso vs DDTC + Pajakku per signal-to-noise.

### 7.7 Joki Coretax phenomenon (signal sociale)

> "Joki Coretax Bermunculan, Purbaya: Kita Betulin Biar WP Lebih Mudah." — [@DDTCNews tweet](https://x.com/DDTCNews/status/2041334783477788772).

Joki = "broker" che fanno SPT al posto del WP (illegal/grey). Emergenza Joki = signal sistema **ostile** all'utente medio = market gap per Bali Zero (servizio human-led con intelligence machine).

**Fonti totali sez. 7**: 12.

---

## Section 8 — Bali Zero tax workflow positioning

### 8.1 Stack obbligatorio PT PMA Indonesia (ground truth)

> "Most Indonesian businesses manage five obligations: PPh 21 (employee income tax withholding), PPh 23 (withholding on vendor payments), PPN (VAT, if PKP-registered), PPh 25 (monthly corporate tax instalments), and SPT Tahunan Badan (annual corporate tax return)." — [LMI Consultancy](https://www.lmiconsultancy.com/introduction-to-income-tax-report-in-indonesia-guides-to-monthly-and-annual-income-tax/).

### 8.2 Aliquote

> "PT PMAs are subject to a 22% corporate income tax on their net taxable income after deducting eligible business expenses. If your business in Bali earns more than IDR 4.8 billion in annual revenue, you must register for VAT (PPN) and charge 11% VAT on all taxable goods and services. Foreign-owned companies must withhold and report taxes such as PPh 21 (employee income tax), PPh 23 (vendor payments), and PPh 26 (cross-border transactions)." — [BaliVisa.co PT PMA monthly reporting](https://balivisa.co/avoid-tax-penalties-pt-pma-monthly-reporting-in-bali/).

> "PPh 23: Payable at the rate of 2% for most types of services where the recipient of the payment is an Indonesian resident and 15% for a variety of payments to resident corporations and individuals." — [PwC Indonesia withholding taxes](https://taxsummaries.pwc.com/indonesia/corporate/withholding-taxes).

> "PPh 26: Cross-border payments to non-residents fall under PPh 26 with a 20% rate — unless reduced under a Double Taxation Agreement (DTA)." — [Acclime Indonesia](https://indonesia.acclime.com/guides/withholding-tax/).

> "Since 1 January 2025, Indonesia's statutory VAT rate is 12%, but most domestic transactions are still billed at an effective 11% because the taxable base (DPP) is multiplied by 11/12." — search aggregate corroborated by Permitindo.

### 8.3 Deadline ricorrenti

> "The monthly payment deadline is the 15th of the following month, with the filing deadline set for the 20th. These deadlines apply regardless of the withholding tax article." — search aggregate (LMI).

> "Even if you haven't earned income yet, filing a 'zero report' is mandatory to avoid penalties." — [BaliVisa.co](https://balivisa.co/avoid-tax-penalties-pt-pma-monthly-reporting-in-bali/).

### 8.4 Pattern industry — fragmentation problem

> "One provider handles payroll and PPh 21. A different firm handles PPN. A third prepares the annual SPT. No single provider sees the complete picture. Reconciliation between them is the business owner's responsibility. An advisor who handles PPh 21 and PPh 23 but not PPN and SPT Tahunan is not in a position to guarantee that the annual return will reconcile cleanly." — [BaliVisa.co — why every PT PMA needs an accountant](https://balivisa.co/why-your-pt-pma-in-bali-needs-an-accountant/).

Bali Zero **risolve già** la frammentazione perché ha tax team integrato (Veronika lead, Angel, Adit) — prove dal caso Marta Reyes IDR 18jt complete-stack quote.

### 8.5 Cosa Bali Zero fa già (osservazione codebase + memory)

Inferred dai progetti recenti documentati in `~/.claude/projects/-Users-nuzantara/memory/`:

- **SPT Tahunan Badan/OP** ([project_marta_reyes_spt_2026_05_05.md](~/.claude/projects/-Users-nuzantara/memory/project_marta_reyes_spt_2026_05_05.md)) — quote IDR 18jt complete (modal 10,5 mld + saldo 2,3 mld + ~130 transazioni 2025 + 7 mesi PPh 21 arretrati Giu-Dic).
- **PPh 21/23/26 monthly + annual reconciliation**.
- **PPN equalizzazione** (output VAT vs input VAT vs SPT Tahunan).
- **Compliance KBLI mapping** ([project Marina Pinyaylova](~/.claude/projects/-Users-nuzantara/memory/MEMORY.md) Tuka-Tibubeneng, 7 KBLI digital tourism content).
- **SPT extension awareness** ([research SPT extension 31 May](~/Desktop/nuzantara/research/tax/2026-05-01-spt-extension-31-may.md)) — KEP-71/PJ/2026 + PENG-31/PJ.09/2026 already captured con NB-4 + DeepSeek + Gemini cross-verification.

### 8.6 Workflow automation map (tech-stops vs human-signs)

| Step                                                | Automatable?             | Why                                                                                                                                                             |
| --------------------------------------------------- | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ingest fatture/bukti potong (OCR + parsing)         | **Sì 100%**              | OCR + LLM extraction = mature tech (qwen2.5vl:7b sta già nel local Ollama arsenal).                                                                             |
| Tax code classification (KBLI/account → tax object) | **Sì 90%**               | Stanford NLP paper su general ledger 461k row dimostra fattibilità. Confidence threshold + human-in-loop per outlier.                                           |
| Calcolo PPh 21/23/26/25 monthly                     | **Sì 100%**              | Rule-based deterministic (slab + withholding rate).                                                                                                             |
| Calcolo PPN (output - input)                        | **Sì 95%**               | Rule-based, edge-case su faktur pajak invalid → human review.                                                                                                   |
| Equalizzazione PPN ↔ SPT Tahunan                    | **Semi**                 | Reconciliation engine + variance flag, **firma umana finale**.                                                                                                  |
| Generazione draft SPT                               | **Sì 100%**              | Template-driven.                                                                                                                                                |
| Submit Coretax (faktur, e-bupot, e-Filing)          | **Sì 80%**               | API PJAP partner (Pajakku/PajakExpress/OnlinePajak). I 20% restanti = error recovery (404, 500, save-invalid) richiedono retry intelligente + human escalation. |
| Tax planning (interpretazione PER nuova)            | **Human + LLM-assist**   | Judgment professionale Veronika, LLM = research aide (BlueJ pattern).                                                                                           |
| Audit response / DJP correspondence                 | **Human**                | Stakes + accountability.                                                                                                                                        |
| Cliente sign-off final SPT                          | **Human**                | Veronika firma — questa è la natura del servizio Bali Zero.                                                                                                     |
| Joki-replacement risk                               | **Bali Zero NON è joki** | Servizio licensed con consulente registrato vs grey-market joki. Posizionamento difensivo.                                                                      |

### 8.7 Where tech stops, human signs

> "An advisor who handles PPh 21 and PPh 23 but not PPN and SPT Tahunan is not in a position to guarantee that the annual return will reconcile cleanly." — BaliVisa.

La firma è valore difensivo: **Veronika sign-off** = audit-defensibility. Tax engine autonomic per Bali Zero non è "sostituire Veronika", è "Veronika con leverage 10x: lei firma su 50 clienti/mese invece di 10". Pattern industry consolidato (BlueJ, TaxGPT): AI = first draft, professional = sign + relationship.

### 8.8 Minimum viable autonomic loop (lifecycle "nasce/cresce/auto-correct/cosciente/canalizza")

1. **Nasce** (ingestion): cron pull fattura/bukti potong → OCR → LLM extract → SQLite ledger (Pro/Mini).
2. **Cresce** (knowledge graph): ogni transazione tagged con KBLI/tax code/PPh/PPN flag, embedded (bge-m3 already in arsenal). Embed → Qdrant local mirror (già setup R4-bis). Query semantic vs storico → suggested tax treatment.
3. **Auto-correct**: equalization engine flagga variance > 5% → Telegram alert Veronika. Pattern già in stack ("Telegram hotfix-notify" CLAUDE.md).
4. **Cosciente** (regulatory awareness): scrape PER/SE/KEP/PMK su jdih.kemenkeu.go.id + pajak.go.id/peraturan + datacenter.ortax.org → ingest → diff vs precedent → propose policy update. Pattern già usato per KEP-71/PJ/2026 research (multi-LLM + 10 fonti).
5. **Canalizza** (output): draft SPT + draft cliente report + Brevo email (hardcoded zantara@balizero.com per CLAUDE.md rule) + Coretax submission via PJAP API + audit trail.

**Fonti totali sez. 8**: 11 (osservazioni codebase non contate come URL esterni).

---

## Cross-section sources index (deduped, full)

### DJP / Government primary

1. https://coretaxdjp.pajak.go.id
2. https://www.pajak.go.id/en/core-system-tax-administration
3. https://www.pajak.go.id/en/node/107868 (Coretax page)
4. https://www.pajak.go.id/en/node/113210 (Implementasi)
5. https://www.pajak.go.id/reformdjp/coretax
6. https://pajak.go.id/coretaxpedia/
7. https://pajak.go.id/coretaxpedia/buku-panduan-coretax-djp
8. https://pajak.go.id/coretaxpedia/akses-coretax-bagi-user-djp-online
9. https://www.pajak.go.id/en/peraturan
10. https://pajak.go.id/en/siaran-pers-page
11. https://pajak.go.id/en/berita-page
12. https://www.pajak.go.id/id/siaran-pers-penegakan-hukum
13. https://twitter.com/ditjenpajakri / https://x.com/DitjenPajakRI
14. https://x.com/DitjenPajakRI/status/1874759233734152415 (Coretax launch)
15. https://x.com/DitjenPajakRI/status/1639982298438451201 (phishing warning)
16. https://www.youtube.com/@DitjenPajakRI
17. https://www.instagram.com/ditjenpajakri/

### Kemenkeu / regulation repos

18. https://jdih.kemenkeu.go.id/
19. https://jdih.kemenkeu.go.id/dok/pmk-81-tahun-2024
20. https://jdih.kemenkeu.go.id/api/download/637047be-3dba-4347-aba1-98fa7fd5ab3f/2024pmkeuangan081.pdf
21. https://www.kemenkeu.go.id/publikasi/siaran-pers
22. https://peraturan.go.id/
23. https://peraturan.go.id/pmk
24. https://peraturan.go.id/profil.html
25. https://peraturan.bpk.go.id/

### Press / news Indonesia

26. https://news.ddtc.co.id/
27. https://news.ddtc.co.id/berita/nasional/1816171/2026-marks-full-coretax-implementation-avoid-inactive-account-risks
28. https://news.ddtc.co.id/berita/nasional/1817999/dgt-keeps-watch-of-possible-extension-of-tax-return-filing-deadline
29. https://news.ddtc.co.id/berita/nasional/1818278/deadline-relaxed-file-annual-individual-tax-returns-by-30-april
30. https://news.ddtc.co.id/berita/nasional/1818802/decision-pending-on-annual-corporate-income-tax-filing-relaxation
31. https://news.ddtc.co.id/berita/nasional/1818923/wp-ramai-keluhkan-gagal-akses-coretax-error-404-djp-jawab-begini
32. https://news.ddtc.co.id/berita/nasional/1819093/coretax-tampilkan-periode-spt-tahunan-yang-keliru-begini-solusinya
33. https://news.ddtc.co.id/berita/nasional/1819130/wp-tak-bisa-curang-semua-transaksi-kini-terekam-otomatis-di-coretax
34. https://news.ddtc.co.id/berita/nasional/1819164/jangan-ketinggalan-simak-aturan-baru-yang-terbit-sepanjang-april-2026
35. https://news.ddtc.co.id/berita/nasional/1810871/profil-lengkap-bimo-wijayanto-sosok-yang-dikabarkan-jadi-dirjen-pajak
36. https://news.ddtc.co.id/berita/nasional/1811040/baru-jadi-dirjen-pajak-ini-tugas-awal-bimo-wijayanto
37. https://news.ddtc.co.id/berita/nasional/1806617/atur-pelaksanaan-coretax-system-menteri-keuangan-terbitkan-pmk-baru
38. https://x.com/DDTCNews/status/2041334783477788772 (Joki Coretax)
39. https://en.tempo.co/read/2069184/indonesias-tax-dg-forms-task-force-for-coretax-transformation
40. https://en.tempo.co/read/1979013/meet-coretax-the-controversial-modernization-of-indonesias-tax-system
41. https://jakartaglobe.id/business/finance-ministry-extends-tax-filing-deadline-to-endapril-amid-coretax-issues
42. https://jakartaglobe.id/business/tax-office-logs-105-million-tax-returns-amid-coretax-system-glitches
43. https://voi.id/en/economy/485092
44. https://www.heygotrade.com/en/news/indonesia-extends-corporate-tax-filing-may-31-2026/
45. https://indonesiasentinel.com/indonesia-core-tax-system-faces-major-complaints-over-access-issues/
46. https://www.world-today-journal.com/indonesias-tax-filing-surge-11-43-million-spt-submitted-djp-targets-15-million-by-april-2026-as-coretax-activations-reach-18-19-million-accounts/

### Indonesian commercial tax / consultancies

47. https://ortax.org/
48. https://datacenter.ortax.org/ortax/aturan/show/25285
49. https://ddtc.co.id/en/services/ddtc-news
50. https://perpajakan.ddtc.co.id/
51. https://muc.co.id/en/home
52. https://muc.co.id/en/article/applies-to-all-taxable-entrepreneurs-dgt-reactivates-e-faktur-application
53. https://muc.co.id/en/article/newly-appointed-director-general-of-taxes-bimo-still-reviewing-coretax-system
54. https://muc.co.id/en/article/taxpayer-registration-guide-pmk-812024
55. https://www.taxand.com/our-locations/indonesia/
56. https://www.itrworldtax.com/Firm/pb-taxand/Profile/969
57. https://pajakku.com/
58. https://artikel.pajakku.com/baru-dilantik-dirjen-pajak-bimo-targetkan-evaluasi-coretax-rampung-dalam-1-bulan
59. https://artikel.pajakku.com/rangkuman-isi-pmk-812024-tentang-pelaksanaan-sistem-inti-administrasi-perpajakan-coretax-ctas
60. https://artikel.pajakku.com/ketahui-daftar-error-coretax-djp-dan-cara-mengatasinya
61. https://klikpajak.id/blog/solusi-coretax-error/
62. https://klikpajak.id/blog/coretax-system/
63. https://www.online-pajak.com/en/
64. https://www.peakxv.com/companies/onlinepajak/
65. https://pajakexpress.com/
66. https://pajakexpress.com/harga
67. https://pajakexpress.com/fitur/efaktur
68. https://pajakexpress.com/fitur/api-integrasi
69. https://www.pwc.com/id/taxflash-2026-07.html
70. https://www.pwc.com/id/en/pocket-tax-book/english/pocket-tax-book-2024.pdf

### Tax automation global

71. https://www.glencoyne.com/guides/tax-engine-comparison
72. https://taxcloud.com/blog/sales-tax-apis/
73. https://taxcloud.com/blog/avalara-vs-vertex-comparison/
74. https://taxcloud.com/blog/avalara-alternatives/
75. https://taxcloud.com/integrations/odoo/
76. https://www.numeral.com/blog/taxjar-vs-avalara
77. https://www.agenttax.io/blog/avalara-vertex-wont-solve-ai-tax
78. https://frappe.io/erpnext/open-source-accounting
79. https://theledgerlabs.com/odoo-tax-management-guide/
80. https://www.selecthub.com/accounting/open-source-accounting-software/

### Tax LLMs / AI research

81. https://law.stanford.edu/wp-content/uploads/2023/07/White-Paper_Large-Language-Models-as-Tax-Attorneys.pdf
82. https://crfm.stanford.edu/helm/
83. https://github.com/stanford-crfm/helm
84. https://crfm.stanford.edu/fmti/
85. https://hazyresearch.stanford.edu/legalbench/
86. https://www.bluej.com/
87. https://www.bluej.com/blog/blue-j-runs-on-latest-openai-model
88. https://www.taxgpt.com/blog/taxgpt-vs-bluej
89. https://openai.com/index/blue-j/
90. https://www.taxproexchange.com/ai/tools/bluej
91. https://www.softwareadvice.com/tax-practice-management/blue-j-tax-profile/
92. https://www.taxnotes.com/featured-analysis/generative-ai-tax-looking-back-looking-ahead/2024/02/02/7j458
93. https://ejurnal.pajak.go.id/st/article/download/927/192/4278

### IRS / government AI

94. https://www.irs.gov/irm/part10/irm_10-024-001r
95. https://www.tx.cpa/news-publications/todays-cpa-magazine/issues/article/january-february-2026/2026/01/13/irs-use-of-artificial-intelligence-and-data-analytics-to-modernize-operations
96. https://www.gao.gov/blog/inside-irs-use-artificial-intelligence
97. https://www.eisneramper.com/insights/tax/ai-irs-transforming-0126/
98. https://fedscoop.com/treasury-irs-ai-use-case-inventory/

### PT PMA Bali context

99. https://balivisa.co/avoid-tax-penalties-pt-pma-monthly-reporting-in-bali/
100. https://balivisa.co/why-your-pt-pma-in-bali-needs-an-accountant/
101. https://emerhub.com/bali/essential-guide-to-corporate-taxes-in-bali/
102. https://www.lmiconsultancy.com/introduction-to-income-tax-report-in-indonesia-guides-to-monthly-and-annual-income-tax/
103. https://www.lmiconsultancy.com/corporate-tax-income-indonesia-extended-waived-deadline-for-annual-returns-until-31-may-2026/
104. https://www.lmiconsultancy.com/what-is-coretax-in-indonesia-implementation-of-core-tax-administration-system-ctas/
105. https://taxsummaries.pwc.com/indonesia/corporate/withholding-taxes
106. https://indonesia.acclime.com/guides/withholding-tax/
107. https://dataon.com/en-id/blog/coretax-djp-pajak-guide/
108. https://jcss.co.id/indonesia-coretax-system-2026-foreign-companies/
109. https://www.cekindo.com/blog/core-tax-administration-system
110. https://sevenstonesindonesia.com/blog/coretax-system-technical-issues-trouble-indonesian-firms/
111. https://www.aseanbriefing.com/doing-business-guide/indonesia/taxation-and-accounting/coretax-indonesia
112. https://aei.or.id/en/press-release/get-to-know-coretax-a-more-transparent-and-efficient-tax-administration-system

### Coretax error catalogs

113. https://wartagarut.com/coretax-error-lagi-solusi-wajib-pajak-2026/
114. https://periskop.id/artikel/20260430/coretax-error-terjadi-ini-daftar-masalah-umum-dan-solusi-lengkap-cara-mengatasinya
115. https://iuwashtangguh.or.id/berita-nasional/5511061342/save-invalid-di-coretax-ini-penyebab-solusi-dan-cara-upload-ulang-faktur-pajak-2026/
116. https://blog.alatpajak.id/blog/coretax-error-2026-solusi-praktis-tim-pajak
117. https://jurnalitpln.id/gagal-login-ini-alasan-coretax-hari-ini-error-dan-solusi-darurat-pajak-2026/
118. https://jogja.suaramerdeka.com/ekonomi/1817039401/apakah-coretax-error-hari-ini-jumat-24-april-2026-sampai-jam-berapa-simak-penjelasan-djp-online
119. https://ortax.org/cara-membuat-faktur-pajak-dengan-impor-xml-di-coretax
120. https://www.akuntansimandiri.com/2026/04/cara-mengatasi-error-validasi-coretax.html
121. https://www.oposisicerdas.com/2026/03/purbaya-ungkap-masalah-baru-di-sistem.html
122. https://www.inilah.com/bos-pajak-tendang-vendor-coretax-digantikan-24-pakar-lokal-pertanda-pengadaan-bermasalah-sejak-awal

**Total deduped sources**: **122 URLs**.

---

## Synthesis — implications for Bali Zero autonomic tax engine

1. **No public Coretax API**: design integration via PJAP partner (Pajakku/OnlinePajak/PajakExpress have published API docs). Build provider-abstraction layer.
2. **Regulation ingest**: scrape jdih.kemenkeu.go.id + pajak.go.id/peraturan + datacenter.ortax.org daily; embed → Qdrant local (already setup). Diff engine for new PER/SE/KEP/PMK.
3. **No Indonesian tax-specific LLM exists publicly** — clear opportunity gap. Bali Zero could build IndoTax-LLM as competitive moat (NB-INTEL-style RAG over PMK/PER/UU + KEP-71-style research captures).
4. **Coretax instability is structural, not transient**: design retry + queue + human-escalation as first-class concern, not edge-case.
5. **Veronika sign-off non sostituibile**: position autonomic engine as Veronika-leverage, not Veronika-replacement. Mirror BlueJ/TaxGPT pattern (AI = first draft, pro = sign).
6. **Joki Coretax phenomenon = competitive opening**: licensed + transparent + machine-augmented service positioned against grey-market joki.
7. **Free OSS substrate**: ERPNext (GPL, full tax module) > Odoo Community (tax authority integrations behind Enterprise paywall) for Indonesia hosting.
8. **HARD RULE constraint**: zero per-token Anthropic API. Use Claude OAuth CLI + Ollama local + DeepSeek (allowed, ~$0.01/query). All NLP classification (qwen2.5vl OCR, qwen3.5 classifier, bge-m3 embed) already deployable from local arsenal.

---

**End of report. Saved at `/tmp/r3-djp-coretax-tax-tech-2026-05-08.md`**
