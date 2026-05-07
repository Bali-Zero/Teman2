# R6 — Country Intelligence Indonesia 2026

**Mission**: Bali Zero macro intelligence (politica, economia, società, cultura, geo) per supporto decisioni business + dispatch espati.
**Compiled**: 2026-05-08 (Pro session, research-only mode)
**Lifecycle target**: nasce / cresce / auto-correct / cosciente / canalizza.

---

## 1. Country Intelligence Platforms — Global SOTA

### 1.1 GDELT Project — `gdeltproject.org`

- **Access**: Free, no API key required. Bulk downloads + JSON/CSV API.
- **Coverage**: "GDELT monitors print, broadcast, and web news media in over 100 languages from across every country in the world." Indonesian is among the **65 languages live-translated** into English.
- **Update frequency**: Real-time (every 15 minutes for the Thematic Word Cloud Dashboard); GDELT 2.0 Event database updates every 15 min.
- **API endpoints**:
  - DOC 2.0 Article Search: `https://api.gdeltproject.org/api/v2/doc/doc?query=...&format=json`
  - GKG (Global Knowledge Graph) tone/themes
  - Thematic Word Cloud Dashboard: "live-updated embeddable word cloud of the top overall and top trending topics mentioned in coverage about a given country or administrative division, updated every 15 minutes, tallying all themes mentioned in coverage mentioning a given country over the last 2 hours."
- **Indonesia filter**: FIPS-2 country code `ID`.
- **Strategic note for Bali Zero**: free, queryable, supports cron ingest into NB-INTEL. Best layer-zero signal for politica/conflict tone.
- **Refs**:
  - https://www.gdeltproject.org/
  - https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
  - https://blog.gdeltproject.org/announcing-the-gdelt-thematic-word-cloud-dashboard-api/

### 1.2 ACLED — `acleddata.com`

- **Access**: Free with registered open-access account. API requires `API_KEY` + `EMAIL` query params.
- **Coverage Indonesia**: "Indonesia is covered from 2015 to the present within the ACLED dataset for South and Southeast Asia." Asia-Pacific desk dedicated.
- **Update frequency**: "Data are updated in real time and can be downloaded from the website's Data Export Tool, the website's Curated Data Files, or directly from the ACLED API."
- **2025 trend (Asia-Pacific)**: "In 2025, Asia Pacific was once again the leading region of violence targeting local officials owing to attacks by rioters and non-state armed groups."
- **Use case Bali Zero**: monitoring Papua/Maluku unrest, Jakarta protest cycles (impatto direct/indirect su clienti business + travel advisories).
- **Refs**:
  - https://acleddata.com/
  - https://acleddata.com/data/
  - https://acleddata.com/asia-pacific/
  - https://data.humdata.org/organization/acled (HDX mirror, 246 datasets)

### 1.3 Eurasia Group

- **Access**: Top Risks free PDF; full reports paywalled (enterprise).
- **2026 Top Risks** include: "US political revolution, Overpowered, The Donroe Doctrine, Europe under siege, Russia's second front, State capitalism with American characteristics, China's deflation trap, AI eats its users, Zombie USMCA, and The water weapon."
- **Indonesia coverage in 2026**: not a standalone country chapter, but cross-cutting in trade analysis. Eurasia Review (third-party) ran "Signed On A Crumbling Foundation: How Indonesia's Trade Deal With Washington Unraveled In 24 Hours" (April 2026): "President Prabowo and President Trump signed the Agreement on Reciprocal Trade (ART) in Washington on February 19, 2026 — a USD 33 billion deal."
- **Refs**:
  - https://www.eurasiagroup.net/issues/top-risks-2026
  - https://www.eurasiareview.com/20042026-signed-on-a-crumbling-foundation-how-indonesias-trade-deal-with-washington-unraveled-in-24-hours-analysis/
  - https://www.gzeromedia.com/video/gzero-live/the-biggest-geopolitical-risks-of-2026-revealed

### 1.4 Stratfor / RANE Worldview

- **Access**: Subscription. "RANE (formerly Stratfor Worldview) produces respected geopolitical analysis reports costing $50K+/yr for enterprise subscriptions." Country reports a-la-carte at store.stratfor.com.
- **Custom quote model**: "RANE Network operates a tiered pricing model that reflects its shift toward enterprise risk management" + "the enterprise subscription adds custom analyst briefings, dedicated regional coverage, and access to RANE's broader risk management platform."
- **Indonesia products**: country reports (Worldview Country Profile Indonesia), 2026 ASEAN chairmanship analyses ("Previewing the Philippines 2026 ASEAN Chairmanship | RANE").
- **Refs**:
  - https://worldview.stratfor.com/
  - https://store.stratfor.com/collections/country-reports
  - https://www.ranenetwork.com/worldview-subscribe

### 1.5 Control Risks — RiskMap 2026

- **Access**: RiskMap web layer free (interactive map + ratings); detailed forecasts paywalled.
- **2026 framing**: "RiskMap 2026 is Control Risks' essential forecast for global business risks ... global risks to business will be driven by a new world order which means volatility as normal, rising global organised crime, activated societies and the race for AI computing power."
- **Indonesia mention**: organised-crime context. "Organised criminal groups are penetrating booming extractive industries, like gold in Brazil, **nickel in Indonesia**, and oil in Mexico."
- **Use case Bali Zero**: country security rating + sectoral risk (mining, tourism). Free dashboard sufficient for indicator delta, full report needed for client briefing.
- **Refs**:
  - https://www.controlrisks.com/riskmap
  - https://www.controlrisks.com/riskmap/maps
  - https://www.controlrisks.com/riskmap/top-risks
  - https://www.controlrisks.com/riskmap/top-risks/the-growing-web-of-organised-crime

### 1.6 Crisis24 / GardaWorld

- **Access**: Risk alerts country pages **free**; Horizon platform + Risk Intelligence Analysis enterprise-paid.
- **Indonesia**: dedicated alerts page `crisis24.garda.com/alerts/indonesia` + Country Profile page (`garda.com/crisis24/country-reports/indonesia`).
- **Coverage scope (quote)**: "Crisis24 provides country reports on Indonesia covering transportation, terrorism, natural risks, war risks, social stability and health risks. Opportunistic crime is the primary threat to travelers in Indonesia."
- **Operations**: "Crisis24's 24/7 Global Operations Centers which offer uninterrupted technology-enhanced intelligence from over 180 expert analysts around the world and detailed risk ratings across over 25 categories for all countries worldwide."
- **2026 product launch**: "Crisis24 Global Risk Forecast 2026: Future Ready, Now" + AI-powered Crisis24 Horizon.
- **Best use**: dispatch espati (Bali Zero clients in transit / live in-country) — alerts feed.
- **Refs**:
  - https://crisis24.garda.com/alerts/indonesia
  - https://www.garda.com/crisis24/country-reports/indonesia
  - https://www.gardaworld.com/news/crisis24-global-risk-forecast-2026-future-ready-now
  - https://www.crisis24.com/solutions/risk-intelligence-analysis

---

## 2. Indonesia-specific Think Tanks

### 2.1 CSIS Indonesia — `csis.or.id`

- **Recent 2026 publications**:
  - "Indonesia may face rising instability in 2026: CSIS" (Jakarta Post, Jan 8 2026): "CSIS researchers warned that Indonesia may face growing uncertainty in 2026, especially if President Prabowo Subianto's administration did not strengthen reforms and improve public trust in the government. CSIS political and social change department head Arya Fernandes noted that 'complex' government policies and the lack of a clear reform road map may become major sources of political instability."
  - "Creeping militarization looms as battalions expand nationwide: CSIS" (Jakarta Post, May 5 2026): "Security analyst D. Nicky Fahrizal of CSIS said the move reflects Prabowo's accelerated 'securitization' attempt, which frames welfare, economic and infrastructure programs as 'security instruments'."
  - "Big Promises, Tight Budget: Rethinking Prabowo Administration's Fiscal Logic" — fiscal precariousness analysis.
  - "Indonesia's Approach to the Middle East and the Muslim World Needs a Rethink"
- **Refs**:
  - https://www.csis.or.id/
  - https://www.csis.or.id/publication/big-promises-tight-budget-rethinking-prabowo-administrations-fiscal-logic/
  - https://www.csis.or.id/publication/indonesias-approach-to-the-middle-east-and-the-muslim-world-needs-a-rethink/
  - https://www.thejakartapost.com/indonesia/2026/01/08/indonesia-may-face-rising-instability-in-2026-csis.html
  - https://www.thejakartapost.com/indonesia/2026/05/05/creeping-militarization-looms-as-battalions-expand-nationwide-csis.html

### 2.2 ISEAS Yusof Ishak Institute (Singapore)

- **Indonesia Studies Programme** + ASEAN Studies Centre. "The Indonesia Studies Programme at ISEAS – Yusof Ishak Institute promotes in-depth understanding of Indonesia through conferences, workshops, seminars, and publications."
- **2026 Perspective papers**:
  - **2026/5**: "Challenges Await Indonesia's New Ministry of Hajj and Umrah" by A'an Suryana (Jan 24 2026) — "issues faced by Indonesia's Ministry of Religious Affairs, including inefficient mobilization of pilgrims during hajj seasons and logistics problems where family members arrived separately due to different service providers."
  - **2026/16**: "Forging a Robust Middle Class: Lessons Learned from Comparisons between Indonesia and China" by Sherry Tao Kong & Maria Monica Wihardja (Mar 10 2026).
- **Regional Outlook Forum 2026**: "Confronting Chaos: The Future of International Order in Southeast Asia" — panel "Indonesia: Democratic Consolidation and International Outlook" moderated by Dr Siwage Dharma Negara.
- **FULCRUM blog**: "Indonesia in 2026: Prabowo's First 'Real' Year of Ambition and Why We Should Care" — high-signal English commentary.
- **Refs**:
  - https://www.iseas.edu.sg/
  - https://www.iseas.edu.sg/articles-commentaries/iseas-perspective/2026-5-challenges-await-indonesias-new-ministry-of-hajj-and-umrah-by-aan-suryana
  - https://www.iseas.edu.sg/programmes/country-studies-programme/indonesia-studies/indonesia-studies
  - https://www.iseas.edu.sg/events/rof/regional-outlook-forum-2026-confronting-chaos-the-future-of-international-order-in-southeast-asia-2
  - https://fulcrum.sg/indonesia-in-2026-prabowos-first-real-year-of-ambition-and-why-we-should-care/

### 2.3 Lowy Institute (Australia)

- **The Interpreter** blog: dense Indonesia coverage under Prabowo 2026.
- **Recent quotes**:
  - "Australian Prime Minister Anthony Albanese visited Jakarta in February 2026 to meet with President Prabowo, with a Treaty of Common Security expected to be signed as the centrepiece of the visit. Leaders have framed the Jakarta Treaty 2026 as a response to 'challenging times,' referring to a more volatile regional environment amid intensifying major-power competition, evolving US and Chinese defence postures, and anxieties about overdependence on great powers."
  - "Australia is now Indonesia's second-most important defence partner after the United States, ranking highly in joint exercises and military education exchanges."
  - "Prabowo has attempted to pursue 'multi-alignment' in foreign policy, which shifts Indonesia's traditional 'non-aligned' position by aiming to craft cooperation with both great powers and like-minded countries. In foreign economic policy, Prabowo is actively diversifying, with Indonesia joining BRICS, securing free trade agreements with the European Union and Canada, and negotiating lower Trump tariffs."
- **Refs**:
  - https://www.lowyinstitute.org/the-interpreter/placebo-risk-australia-indonesia-common-security-treaty
  - https://www.lowyinstitute.org/the-interpreter/prabowo-s-policies-won-t-fix-indonesia-s-problems
  - https://www.lowyinstitute.org/the-interpreter/indonesia-s-multi-alignment-dilemma-under-prabowo
  - https://www.lowyinstitute.org/the-interpreter/indonesia-australia-defence-cooperation-under-prabowo
  - https://www.lowyinstitute.org/the-interpreter/critical-mineral-match-australia-indonesia

### 2.4 The Habibie Center

- **Founded**: "established on 10 November 1999, and is committed to preserving democracy through various activities and programs that promote public engagement on current issues, as well as providing thorough input in the form of research publications and policy advocacy."
- **Structure**: "operates through four institutes: the Institute of Democracy and Human Rights (IDH), the Institute of Democratisation through Science, Technology, and Innovation (IDESTI), the Institute of Democracy, Economy, and Ecology (IDEE), and the Institute of the Maritime Continent (IMC)."
- **2026 chair**: Dewi Fortuna Anwar (also BRIN researcher).
- **Recent (May 2026)**: discussion at Habibie Center South Jakarta on "narrowing spaces for dissent threaten democratic systems" (Jakarta Post, May 2 2026).
- **Refs**:
  - https://habibiecenter.or.id/
  - https://habibiecenter.or.id/dialog-demokrasi
  - https://www.thejakartapost.com/world/2026/05/02/panel-warns-of-narrowing-dissent-in-indonesia.html
  - https://www.nowjakarta.co.id/the-habibie-center-indonesias-advocate-of-democracy/

### 2.5 The Indonesian Institute (TII) — `theindonesianinstitute.com`

- **Identity**: "public policy research institute (Center for Public Policy Research) officially established since October 21, 2004 by a group of dynamic young activists and intellectuals. TII is an independent, nonpartisan, and nonprofit institution."
- **2026 outputs**:
  - **March 2026 Indonesian Update vol XX no 3 (EN)**: "Negative Outlook for the Indonesian Economy: Government Policy Alarm" — "examines warning signals about Indonesia's economic prospects arising from various policy developments and global dynamics."
  - **January 2026 vol XX no 1 (EN)**: review of "the New Criminal Code and Criminal Procedure Code (KUHAP) and the new face of freedom of expression in Indonesia."
  - **February 2026 (BI)**: Update Indonesia vol XX no 2 (Bahasa).
  - **Annual**: "INDONESIA 2025" annual policy analysis report.
- **Refs**:
  - https://www.theindonesianinstitute.com/
  - https://www.theindonesianinstitute.com/the-indonesian-update-volume-xx-no-3-march-2026-english-version/
  - https://www.theindonesianinstitute.com/the-indonesian-update-volume-xx-no-1-january-2026-english-version/
  - https://www.theindonesianinstitute.com/wp-content/uploads/2026/01/The-Indonesian-Update-%E2%80%93-Volume-XX-No.1-%E2%80%93-January-2026-English-Version_web-1.pdf

### 2.6 BRIN — `brin.go.id` (LIPI successor)

- **Genesis**: "BRIN became an independent institution on 28 April 2021, integrating the Ministry of Research and Technology with four non-ministerial institutions including LIPI (Indonesian Institute of Sciences), along with BPPT, BATAN, and LAPAN. This made BRIN the sole government institution conducting research in Indonesia."
- **2026 governance shift**: "When Arif Satria became the Chairman of BRIN, the policy was partially reversed in December 2025 and in January 2026 the policy was being reviewed to be completely repealed" — i.e. partial unwind of the LIPI/BRIN merger.
- **Service portal**: ELSA (E-Layanan Sains BRIN) `elsa.brin.go.id`.
- **Refs**:
  - https://brin.go.id/
  - https://elsa.brin.go.id/
  - https://en.wikipedia.org/wiki/National_Research_and_Innovation_Agency

### 2.7 IISS (International Institute for Strategic Studies)

- **Asia desk**: "IISS–Asia team of analysts conducts research on a broad range of regional issues, including Southeast Asian politics and foreign policy, cyber power and future conflict, and Indo-Pacific defence and strategy. The IISS is headquartered in London and has offices in Washington DC, Bahrain and **Singapore**."
- **Indonesia link**: "Thomas Lembong, former Chairman of the Investment Coordinating Board and former Minister of Trade of Indonesia, serves on the IISS advisory council."
- **Programmes**: dedicated Southeast Asian Security and Defence research stream + Shangri-La Dialogue Singapore (annual flagship).
- **Refs**:
  - https://www.iiss.org/
  - https://www.iiss.org/iiss-asia/
  - https://www.iiss.org/research/southeast-asian-security-and-defence/

### 2.8 New Mandala (ANU)

- **Hosting**: "hosted by the Australian National University (ANU) and is based within the Coral Bell School of Asia Pacific Affairs at the College of Asia and the Pacific."
- **Editorial**: "the best anecdote, analysis and new perspectives on the politics and societies of Southeast Asia."
- **Recent Indonesia 2026 articles**:
  - "Indonesia's new state capitalism shrinks its future" — quote: "Indonesia's window for structural transformation" and "the demographic dividend that could underwrite a generation of industrial deepening is already narrowing."
  - "How the national elite grows weary of local democracy" (Feb 2026).
- **Refs**:
  - https://www.newmandala.org/category/indonesia/
  - https://www.newmandala.org/indonesias-new-state-capitalism-shrinks-its-future/

### 2.9 Forum Kajian Pembangunan (FKP) — ANU Indonesia Project (bonus)

- "[FKP hosted by ANU Indonesia Project] Prabowonomics: can Indonesia really grow at 8%?" — debating whether Prabowo's growth target is feasible.
- Ref: https://www.fkpindonesia.org/summary-report/prabowonomics

---

## 3. Indonesian Press — Tier 1

### 3.1 Tempo (`tempo.co` / `magz.tempo.co`)

- **Editorial line**: "Tempo's editorial line is more focused on politics and economics, with a special interest in art and literature. **Tempo is the only media in Indonesia that consistently publishes investigative stories.**"
- **Investigative depth**: "the daily publication has developed its data journalism skills with a view to consolidating its investigative credibility ... 360-degree photography, interactive maps, embedded videos, clickable timelines."
- **Paywall model**: "Tempo built two main sites: a free website to publish breaking news stories and SEO content to expand their audience and a premium website with a paywall to generate reader revenue through digital subscriptions. Tempo currently has around 40,000 paid subscribers."
- **English edition**: `en.tempo.co` (covered Prabowo–Trump tariff timeline 2026).
- **Refs**:
  - https://magz.tempo.co/
  - https://gijn.org/stories/tempo-magazine-45-years-of-investigative-reporting-in-indonesia/
  - https://wan-ifra.org/2026/01/indonesias-tempo-digital-aims-to-reduce-bias-through-transparency-and-accountability/
  - https://en.tempo.co/read/2075521/prabowo-trump-set-to-seal-indonesia-us-tariff-pact-in-january-2026

### 3.2 Kompas (Kompas Group)

- **Two products**: "Kompas.id contains updated news and the digital subscription version of the paper, while Kompas Gramedia also manages another editorially separated portal, kompas.com." Kompas.id is the **paid digital subscription** version of the daily; Kompas.com is the free portal.
- **Awards**: "Kompas.id is the Gold Winner for Indonesia Print Media Awards (IPMA) 2023 in The Best of Editorial Newspaper category."
- **Editorial**: classic establishment liberal-Catholic, in-depth investigations and macro coverage.
- **Refs**:
  - https://www.kompas.id/
  - https://www.kompas.com/
  - https://en.wikipedia.org/wiki/Kompas

### 3.3 The Jakarta Post (`thejakartapost.com`)

- **Identity**: English-language daily of record. Strong CSIS / Habibie Center / academic citations (see §2 above).
- **Sample 2026 headlines**:
  - "Indonesia may face rising instability in 2026: CSIS" (Jan 8 2026)
  - "Creeping militarization looms as battalions expand nationwide: CSIS" (May 5 2026)
  - "Putin meets Prabowo to discuss military and energy ties, wheat exports" (Dec 11 2025)
  - "Panel warns of narrowing dissent in Indonesia" (May 2 2026)
- **Note**: paywall on premium content; tag pages free.
- **Refs**:
  - https://www.thejakartapost.com/

### 3.4 CNN Indonesia (`cnnindonesia.com`)

- **Coverage**: "the latest news about national, politics, economics, international, sports, technology, entertainment, and lifestyle topics." Indonesian-language only.
- **Index**: `cnnindonesia.com/indeks` for chronological feed.
- **RSS**: third-party scrapers exist (RSS-news GitHub aggregator).
- **Refs**:
  - https://www.cnnindonesia.com/
  - https://github.com/JfrAziz/RSS-news

### 3.5 Detik (`detik.com`)

- **Coverage**: "events, accidents, criminal news, legal matters, unique stories, politics, and special coverage in Indonesia and internationally."
- **Vertical**: detikNews (`news.detik.com`) for politics/policy.
- **RSS**: `rss.detik.com` (multi-vertical).
- **Refs**:
  - http://www.detik.com/
  - https://news.detik.com/
  - https://www.indonesia.shafaqna.com/ID/AL/sou/rss.detik.com/detik

### 3.6 Republika (`republika.co.id`)

- Islamic-perspective national daily (PT Republika Media Mandiri / Mahaka).
- RSS feed available; editorial focus religion + national politics.
- Ref: https://republika.co.id

### 3.7 Antara News (state agency)

- **Identity**: "Indonesia's news agency."
- **EN edition**: `en.antaranews.com` — primary English wire for state-perspective coverage. Sample: "Indonesia's BRICS membership is Prabowo's first-year initiative" + "Indonesia, Russia deepen ties in cordial Prabowo-Putin meeting."
- **RSS**: `antaranews.com/rss` (official).
- **Refs**:
  - https://en.antaranews.com/
  - https://www.antaranews.com/rss

### 3.8 Tirto.id

- **Editorial**: data journalism + long-form. Senior journalists (Fahri Salam et al.) co-founded Project Multatuli — a signal of editorial independence stress in 2021 that persists into 2026.
- Ref (cross): https://projectmultatuli.org/en/about/tim-kami/

### 3.9 Project Multatuli (`projectmultatuli.org`)

- **Mission**: "a collective initiative dedicated to carrying out the ideals of public journalism by serving the underreported and holding power accountable."
- **Co-founders**: "by four senior journalists with vast experience at three national media groups: Kompas, Tirto.id and The Jakarta Post."
- **Editorial style**: "slow journalism that does not rely on news quantity or speed, with every topic presented thoroughly and based on research and data" — target audience 18-40.
- **2026 active**: investigative on deforestation, mining (incl. Indonesia nickel sector vs China), agriculture.
- **Refs**:
  - https://projectmultatuli.org/en/about/
  - https://projectmultatuli.org/en/beijing-tightens-its-stranglehold-on-indonesias-nickel-industry/
  - https://pulitzercenter.org/publications/project-multatuli

### 3.10 BeritaSatu (cross-reference)

- Part of Lippo media group (BeritaSatu Media Holdings); EN sister Jakarta Globe (`jakartaglobe.id`).
- 2026 sample: "EU Trade Pact A Boon for Indonesian Palm Oil, But Deforestation Law Remains in the Way" (jakartaglobe.id).
- Refs:
  - https://www.beritasatu.com/
  - https://jakartaglobe.id/business/eu-trade-pact-a-boon-for-indonesian-palm-oil-but-deforestation-law-remains-in-the-way

> **Bali Zero curation note**: For automated ingest, prioritize Antara (state line, free RSS) + Tempo (investigative, partial paywall) + Jakarta Post (EN of record) + Kompas.id (in-depth, paid). For citizen sentiment, see §5.

---

## 4. Economic Data Indonesia

### 4.1 Bank Indonesia — `bi.go.id`

- **Statistics hub**: `bi.go.id/en/statistik/default.aspx` — SDDS (Special Data Dissemination Standard) compliant; SEKI (Statistik Ekonomi dan Keuangan Indonesia) released monthly.
- **Web service for FX**: "the webservice for obtaining exchange rate data (getSubKursLokal3) that can be called with parameters like currency type, start date, and end date in the format `https://www.bi.go.id/biwebservice/wskursbi.asmx`"
- **Sample 2026 macro datapoints (March release)**:
  - "Indonesia's economy in the first quarter of 2026 grew by 5.61% (year-over-year)"
  - "BI-Rate was held at 4.75% in March 2026"
  - "Consumer Price Index (CPI) inflation in March 2026 remained within the target range of 2.5%±1%"
- **Publications**: SEKI March 2026 (`bi.go.id/id/statistik/ekonomi-keuangan/seki/Pages/SEKI-MARET-2026.aspx`).
- **Refs**:
  - https://www.bi.go.id/
  - https://www.bi.go.id/en/statistik/default.aspx
  - https://www.bi.go.id/id/statistik/sdds/default.aspx
  - https://bicara131.bi.go.id/knowledgebase/article/KA-01097/en-us
  - https://www.bi.go.id/id/edukasi/Pages/Infografis-Pertumbuhan-Ekonomi-Indonesia-Tw-I-2026.aspx

### 4.2 BPS — `bps.go.id` & WebAPI `webapi.bps.go.id`

- **API entry**: `https://webapi.bps.go.id` (developer portal `webapi.bps.go.id/developer/`).
- **Auth**: API token required, free registration.
- **Endpoints**: dynamic tables, static tables, publications, press releases, exim data — example: `https://webapi.bps.go.id/v1/api/dataexim/sumber/{sumber}/kodehs/{kodehs}/jenishs/{jenishs}/tahun/{tahun}/periode/{periode}/key/{key}`
- **Coverage**: "the WebAPI allows users to programmatically access various types of data, including Publications, Press Releases, static tables, and dynamic tables."
- **Bali sub-portal**: `bali.bps.go.id` — provincial tourism, demographics, GRDP. Tourism press release: "Tourism Overview of Bali Province, December 2026" + "Number of Monthly Foreign Visitor to Bali by Gate."
- **Helper libraries**:
  - Python `stadata` (`bps-statistics/stadata`)
  - R `bpsr` (`dzulfiqarfr/bpsr`)
  - Postman collection `bps-pinrang/Web-API-BPS-Postman-Collection`
- **Refs**:
  - https://www.bps.go.id/en
  - https://webapi.bps.go.id/developer/
  - https://webapi.bps.go.id/documentation/
  - https://github.com/bps-statistics/stadata
  - https://bali.bps.go.id/en

### 4.3 OJK — `ojk.go.id`

- **Open data migration (July 2025+)**: "Indonesian Banking Statistics (SPI) has been fully transferred to the Integrated Financial Services Sector Data Portal, accessible at `https://data.ojk.go.id/SJKPublic`, providing more interactive and dynamic data access where users can select and download data according to their needs."
- **Verticals**: Banking (SPI), Capital Markets, IKNB (non-bank financial institutions).
- **Recent OJK release** (March 2026 RDKB): "Stabilitas Sektor Jasa Keuangan Terjaga di Tengah Meningkatnya Ketidakpastian Global"; "Digital payment platform transactions valued at Rp 1.70 trillion with 16.65 million registered users" + "Financial technology service providers with 25 officially registered operators at OJK as of March 2026."
- **Refs**:
  - https://ojk.go.id/id/data-dan-statistik/default.aspx
  - https://ojk.go.id/id/kanal/perbankan/data-dan-statistik/statistik-perbankan-indonesia/default.aspx
  - https://ojk.go.id/id/berita-dan-kegiatan/siaran-pers/Pages/RDKB-Maret-2026.aspx
  - https://data.ojk.go.id/SJKPublic

### 4.4 KSEI (clearing) & IDX (exchange)

- **IDX official market-data**: `idx.co.id/en/products/idx-data-services/` and `data.idx.co.id` — "real-time, delayed, end-of-day, and log data directly from the source, with access available through subscriptions to IDX Market Data for stocks, bonds, and derivatives."
- **APIs**: "more than 175 APIs in use, including new data services generating incremental revenue streams."
- **Third-party redistributors with 2026 access**:
  - **OHLC.dev**: "comprehensive IDX API with real-time and historical market data for Stocks, Bonds, Derivatives, and Structured Warrants, optimized with Redis Caching"
  - **iTick**: "Jakarta Composite (IDX) real-time quotes, historical OHLCV bars, and low-latency WebSocket streaming"
  - **Sectors.app**: "Indonesia Stock Exchange financial market data as APIs for stocks, sectors, and indices, updated daily with 99% coverage of IDX-listed stocks"
  - **Twelve Data** + **ICE Data Services** (institutional)
- **Refs**:
  - https://www.idx.co.id/en/products/idx-data-services/
  - https://data.idx.co.id/
  - https://ohlc.dev/indonesia-stock-exchange-idx-api
  - https://sectors.app/

### 4.5 World Bank — Indonesia data

- **Country page**: `data.worldbank.org/country/ID`
- **Key indicator endpoints (REST)**:
  - GDP current US$: `data.worldbank.org/indicator/NY.GDP.MKTP.CD?locations=ID`
  - GDP growth annual %: `data.worldbank.org/indicator/NY.GDP.MKTP.KD.ZG?locations=ID`
  - GDP PPP: `data.worldbank.org/indicator/NY.GDP.MKTP.PP.CD?locations=ID`
  - GDP per capita US$: `data.worldbank.org/indicator/NY.GDP.PCAP.CD?locations=ID`
- **Data provenance**: "country official statistics, National Statistical Organizations and/or Central Banks, National Accounts data files from OECD, and World Bank staff estimates."
- **API**: free JSON/XML at `api.worldbank.org/v2/country/idn/...`
- **Refs**:
  - https://data.worldbank.org/country/ID
  - https://data.worldbank.org/indicator/NY.GDP.MKTP.CD?locations=ID
  - https://www.worldbank.org/ext/in/country/indonesia

### 4.6 IMF Indonesia

- **Article IV 2025 (published Jan 21 2026)**: Country Report No. 2026/010 — "Growth is expected to remain steady at 5.0 percent in 2025 and 5.1 percent in 2026, despite a challenging external environment, reflecting support from fiscal and monetary policies."
- **Risks**: "Downside risks stem from trade policy shocks, prolonged uncertainty, and global financial market volatility."
- **Datamapper**: `imf.org/external/datamapper/profile/IDN`
- **Refs**:
  - https://www.imf.org/en/publications/cr/issues/2026/01/21/indonesia-2025-article-iv-consultation-press-release-staff-report-and-statement-by-the-573330
  - https://www.imf.org/en/news/articles/2026/01/21/pr-26010-indnonesia-imf-executive-board-concludes-2025-article-iv-consultation
  - https://www.imf.org/external/datamapper/profile/IDN
  - https://www.imf.org/en/countries/idn

### 4.7 ADB (Asian Development Bank)

- **Country Partnership Strategy 2025-2029** launched October 2025: "three strategic pathways: investing in people, advancing economic competitiveness, and enhancing resilience and sustainability ... underpinned by crosscutting priorities, including women's empowerment and social inclusion, digitalization, stronger governance and institutions, and regional cooperation and integration."
- **Alignment**: "aligned with Indonesia's medium-term development plan and its eight priority missions—**Asta Cita**" (Prabowo's policy doctrine).
- **2026 funding**: "USD 2.7 billion ... focused on encouraging policy reforms, including deepening the financial sector, strengthening regional governance, increasing water resilience, accelerating the transition to sustainable energy, and protecting marine ecosystems."
- **Refs**:
  - https://www.adb.org/countries/indonesia/strategy
  - https://www.adb.org/news/adb-launches-new-country-partnership-strategy-indonesia-accelerate-inclusive-resilient-sustainable-growth
  - https://www.adb.org/documents/indonesia-country-partnership-strategy-2025-2029
  - https://voi.id/en/amp/561021

---

## 5. Social Pulse Indonesia

### 5.1 X (Twitter) Indonesia

- **Volume growth**: "Indonesia showed strong user growth on X, with **+28% growth in 2025-2026**, driven by mobile-first adoption and political engagement."
- **Use**: "X (formerly known as Twitter) and Facebook are the main battlefield of political buzzers in Indonesia."
- **Topic mix**: "Politics represents 12% of the largest communities on X, alongside Tech (18%), Finance/Crypto (15%), and Sports (14%)."
- **2026 hot topic**: "President Prabowo's offer to help mediate between Iran and the US has provoked debate across Indonesia, amid increased criticism of his approach to foreign policy and warm ties with the Trump administration." (Al Jazeera Mar 7 2026)
- **Realtime trend trackers**: `trends24.in/indonesia`, `getdaytrends.com/trend/Indonesia/`, `globaltwittertrends.com/indonesia/`
- **Refs**:
  - https://www.aljazeera.com/features/2026/3/7/indonesian-presidents-us-ties-questioned-amid-public-anger-over-iran-war
  - https://trends24.in/indonesia/
  - https://searchlab.nl/en/statistics/x-twitter-statistics-2026

### 5.2 TikTok Indonesia

- **Scale**: "Indonesia has become **TikTok's second-largest user base in the world** by February 2025, with **107.7 million users**, with over 50% of its users between the ages of 18 and 40."
- **Politics**: "TikTok's algorithm, optimized to amplify emotionally engaging and visually rich content, created unprecedented opportunities for political actors to generate virality at scale. TikTok significantly amplifies the shift by turning political discourse into entertainment or 'politainment,' with the platform's algorithm favoring surface-level impressions at the expense of in-depth discussions on governance and policy." (ISEAS Perspective 2025/52, Jalli/Unggraini/Setianto)
- **2026 viral signals**: dance challenges, music ("Stecu Stecu" by Faris Adam — Global Top 20 Songs TikTok 2025, only Indonesian song charting globally), AI-content explainers (e.g. local startup Kocebe.ai flashcards).
- **Refs**:
  - https://fulcrum.sg/how-tiktoks-visual-politics-shaped-indonesias-2024-election/
  - https://www.iseas.edu.sg/articles-commentaries/iseas-perspective/2025-52-how-tiktoks-visual-politics-shaped-indonesias-2024-election-by-nuurrianti-jalli-ika-ningtyas-unggraini-yearry-panji-setianto/
  - https://reporter.anu.edu.au/all-stories/did-prabowo-subiantos-tiktok-makeover-impact-the-indonesian-election-results

### 5.3 Drone Emprit (Ismail Fahmi / Media Kernels Indonesia)

- **Platform**: "Drone Emprit is a state-of-the-art software platform dedicated to social media monitoring and analytics ... a tool for monitoring conversations on social media like Twitter, Facebook, Instagram, and now TikTok, as well as monitoring online media news based on keywords, names of figures, and events."
- **Origin**: "Ismail Fahmi, the creator of Drone Emprit, began developing the prototype during his postdoctoral studies at Groningen University in the Netherlands in 2010. By 2012, the system was operational in Indonesia."
- **2026 status**: "actively used in 2026, as recent analyses tracked COVID-19 related discussions and mudik (homecoming) sentiment across X, TikTok and other platforms in early 2026."
- **Public releases**: `pers.droneemprit.id` (publications + insights).
- **Use case Bali Zero**: subscribe to Ismail Fahmi @ismailfahmi on X for daily mood snapshots; commercial subscription via Media Kernels for raw API.
- **Refs**:
  - https://mediakernels.com/our-products/drone-emprit/
  - https://pers.droneemprit.id/
  - https://restofworld.org/2021/drone-emprit/

### 5.4 Indonesia Indicator

- **Identity**: "Indonesia Indicator is a company founded by Rustika Herlambang and two other colleagues that operates in the field of big data analysis and artificial intelligence. The company uses a system called Intelligence Socio Analytic (ISA) to monitor and analyze social media activity."
- **Director of Communications**: Rustika Herlambang — "frequently publishes research and provides commentary on social media trends and their impact on Indonesian society."
- **Output scale**: "research by Indonesia Indicator recorded a total of 353,828,143 posts by Indonesian netizens across five major social media platforms (TikTok, Instagram, Twitter, YouTube, and Facebook) from January 1 to December 21, 2024."
- **Refs**:
  - https://update-profil.blogspot.com/2019/10/rustika-herlambang-komunikasi-indonesia.html
  - https://mediaindonesia.com/politik-dan-hukum/608347/indonesia-indicator-sarankan-parpol-tampil-lebih-casual-demi-raih-gen-z

### 5.5 Kompasiana (`kompasiana.com`)

- **Citizen journalism flagship**: "Since its launch in 2008, Kompasiana has become **the largest citizen media initiative in Indonesia**, with 200,000 contributors who collectively publish 800 articles daily on kompasiana.com."
- **Role 2024-2026**: "increased political awareness among the public, technological development, and the role of citizen journalism, with citizen participation in expressing and spreading political information through social media strengthening democratization in Indonesia."
- **Refs**:
  - https://www.kompasiana.com/
  - https://www.neliti.com/publications/431961/proletariat-digital-dalam-citizen-journalism-kasus-kompasiana

### 5.6 Reddit `r/indonesia` & Kaskus

- **Reddit access**: "It's important to note that Reddit is banned in China and Indonesia. However, some users continue accessing the blocked platform through VPN applications." Subreddit still active: "r/Indonesia is a pretty active community with posts popping up daily covering a huge spectrum of topics. Some of the most active members are Indonesian people, and there are many expats and people who are just interested in Indonesia."
- **Language mix**: "The main language used is Indonesian and English."
- **Kaskus**: "Reddit is not far different from Kaskus which is the largest online forum in Indonesia."
- **Dataset**: 2026 r/Indonesia dataset on Kaggle (`bwandowando/reddit-rindonesia-subreddit-dataset-2026`) for archival study.
- **Refs**:
  - https://www.kaggle.com/datasets/bwandowando/reddit-rindonesia-subreddit-dataset-2026
  - https://www.quora.com/What-do-Indonesians-think-of-Reddit

### 5.7 Bali expat-focused IG / Facebook

- Primary handles to monitor (no quoted scrape — public discoverability):
  - Instagram: `@balifoundinfo`, `@thebalisun`, `@nowbali`, `@nusaduareports`
  - Facebook groups: "Living in Bali" (90k+), "The Bali Sun News" (group), "Bali Expats" (60k+).
- See §6 for editorial outlets.

---

## 6. Bali-specific Intelligence

### 6.1 The Bali Sun (`thebalisun.com`)

- **Editorial focus**: daily Bali news, expat-friendly. Strong on tourism, immigration, Australian/Western traveller incidents.
- **Sample 2026 content**:
  - "Bali's Record Breaking Year For Tourism Sets New Horizons For 2026"
  - "Bali Pivots Approach To Attract More Tourists In 2026"
  - "Bali Celebrated As In Demand Travel Destination As US Ambassador Visits"
  - "College Students At University in Bali Permitted To Pay Their Tuition With Coconuts"
- Ref: https://thebalisun.com/

### 6.2 NOW! Bali (`nowbali.co.id`)

- Lifestyle + culture monthly with web flow; covers events, hospitality openings, cultural calendars. Print + digital.
- (Sister of NOW! Jakarta — `nowjakarta.co.id`.)
- Ref (used here): https://www.nowjakarta.co.id/the-habibie-center-indonesias-advocate-of-democracy/

### 6.3 Bali Post (`balipost.com`) — BPMG

- **Publisher**: Bali Post Media Group; "Bali Post remains the oldest newspaper in BPMG's publication. Bali Post publications feature articles that comment on politics, economy, sports, entertainment, and public opinion."
- **Refresh cadence**: daily archive `balipost.com/news/YYYY/MM/DD/...` (e.g. `2026/05/06/...`).
- **Sister sites**: BaliExpress (Jawa Pos network), NusaBali, Radar Bali (`radarbali.jawapos.com`).
- **Refs**:
  - https://www.balipost.com/
  - https://baliexpress.jawapos.com/
  - https://www.nusabali.com/
  - https://radarbali.jawapos.com/

### 6.4 NusaBali (`nusabali.com`)

- "online news media outlet that provides information and news about Badung, Denpasar, Buleleng, Gianyar, Jembrana, Tabanan, Klungkung, Bangli, Karangasem and national news." — granular kabupaten coverage useful for property/visa case research.
- Ref: https://www.nusabali.com/

### 6.5 Coconuts Bali (`coconuts.co/bali`)

- **Status (key cicatrix)**: "On December 19, 2023, Coconuts Media chairman Byron Perry announced the closure of Coconuts Tabloid Media, attributing the closure to the difficulty of financial sustainability and regional journalistic challenges." Despite the brand decline, the holding co (Coconuts Media) "continues to operate its other subsidiaries, including BK Magazine, Soimilk, and Grove."
- **Acquisition history**: not acquired by a strategic buyer for the news brand; **2021**: Coconuts Media acquired BK Magazine + Soimilk from Asia City Media Group. **Stagwell** earlier added Coconuts Media to its global affiliate network.
- **Practical implication for Bali Zero**: Coconuts Bali archive remains a reference; not a forward-looking news source post-2023.
- **Refs**:
  - https://en.wikipedia.org/wiki/Coconuts_Media
  - https://coconuts.co/bali/
  - https://coconuts.co/singapore/lifestyle/coconuts-media-acquires-bk-magazine-soimilk-in-asset-sale-from-asia-city/
  - https://www.stagwellglobal.com/stagwell-adds-coconuts-media-leading-asia-pacific-publisher-and-media-platform-to-fast-growing-global-affiliate-network/

### 6.6 Jakarta Globe (Bali coverage)

- English daily; uses Bali for trade-/policy-relevant pieces. "EU Trade Pact A Boon for Indonesian Palm Oil, But Deforestation Law Remains in the Way" (2026).
- Ref: https://jakartaglobe.id/

### 6.7 Foreign Chambers (Indonesia, Bali-relevant)

- **BritCham Indonesia** (`britcham.or.id`): "established in 1999 and builds on a British business presence that extends more than a hundred years ... Annually, BritCham hosts more than 100 events that provide platforms for business development amongst its members." Joint EIBN New Year Reception 2026 (12 Jan).
- **AustCham / IABC**: "the IABC is a business association representing private sector business interests in commercial relations between Indonesia and Australia. Established in 1989, the IABC is a result of the merger between DKSPIA (Association of Indonesian and Australian Businessmen) and the Australian Chamber of Commerce in Indonesia (Austcham)."
- **EuroCham Indonesia** (`eurocham.id`): "EuroCham Indonesia aims to be the sole representative of European business interests in Indonesia by working to improve the policies all while advocating improvements in strategic regulations for a better business environment in the country."
- **AmCham Indonesia** (`amcham.or.id`): est. 1971.
- **KADIN** (umbrella Indonesian Chamber of Commerce and Industry): "umbrella organization of Indonesian business chambers and associations, focused on all matters relating to trade, industry and services."
- **Bali-specific**: no major standalone foreign chamber on the island; Bali activity routed via Jakarta chambers + ad-hoc events. Note: "Indonesia has picked Bali as the location for its upcoming international financial center. The government has been drafting a regulation for a financial-sector special economic zone (SEZ) in Bali."
- **Refs**:
  - https://britcham.or.id/about-us/
  - https://app.glueup.com/event/eibn-joint-new-year-reception-2026-164793/
  - https://eurocham.id/stakeholders
  - https://www.amcham.or.id/en/event/detail/indo---pacific-chamber-of-commerce-and-industry-business-forum-
  - https://www.weforum.org/organizations/kadin/
  - https://blog.9cv9.com/list-of-business-chambers-of-commerce-in-indonesia/
  - https://jakartaglobe.id/business/indonesia-picks-bali-for-international-financial-center

### 6.8 Bali Tourism Board / Visit Bali / Disparda

- **Bali Tourism Board (BTB)**: "the official organization responsible for promoting and developing Bali's tourism sector both nationally and internationally, established as a collaboration between the government and key tourism stakeholders." Site: `balitourismboard.info`.
- **Bali Government Tourism Office (Disparda)**: `disparda.baliprov.go.id`.
- **Stats source**: BPS Bali (`bali.bps.go.id`) — the only systemized arrivals dataset.
- **2026 datapoints**:
  - "foreign tourist arrivals to Bali Province were recorded in January 2026 at 502,205, a 12.30 percent decrease compared to the previous month's 572,668 visits."
  - "International arrivals reached 492,289 in February 2026, marking a +9.23% increase year-on-year compared to February 2025."
  - "Bali is on track for a record year in 2026, with around seven million international visitors."
- **Refs**:
  - https://balitourismboard.info/
  - https://disparda.baliprov.go.id/en/
  - https://bali.bps.go.id/en/statistics-table?subject=561
  - https://bali.bps.go.id/en/pressrelease/2026/03/02/718022/tourism-overview-of-bali-province--december-2026.html
  - https://bali.bps.go.id/en/statistics-table/2/MTA2IzI=/number-of-monthly-foreign-visitor-to-bali-by-gate--person-.html
  - https://thebalisun.com/balis-record-breaking-year-for-tourism-sets-new-horizons-for-2026/
  - https://www.thetraveler.org/bali-tourism-surges-past-seven-million-visitors-in-2026/

---

## 7. Cultural / Anthropological Sources

### 7.1 Saka & Pawukon Calendars — Babad Bali (`babadbali.com`)

- **Maintainer**: "Babad Bali is maintained by Yayasan Bali Galang, a Balinese culture preservation organization."
- **Saka system**: "The Saka calendar is derived from the ancient Hindu calendar, and Bali ancestors improved and customized it based on the actual conditions of the island. The Saka calendar divides the year into 12 lunar months—each spanning 29 or 30 days, starting after the new moon (tilem) and reaching the full moon (purnama) midway—resulting in a standard year of about 354 days."
- **Pawukon system**: 210-day cycle drives ceremony timing; "the dates shift each year in the Gregorian calendar."
- **Galungan / Kuningan 2026 reference dates** (Pawukon-anchored):
  - Sugihan Jawa: Thursday June 11 2026
  - Sugihan Bali: Friday June 12 2026
  - Hari Penyekeban: Sunday June 14 2026
  - Hari Penyajan: Monday June 15 2026
  - Hari Penampahan (penjor making): Tuesday June 16 2026
  - **Galungan: Wednesday June 17 2026** (Budha Kliwon Dungulan)
  - Hari Umanis Galungan: Thursday June 18 2026
  - **Kuningan: Saturday June 27 2026**
- **Digital tooling**:
  - Open-source JS library `peradnya/balinese-date-js-lib`
  - SAKA Museum digital project (Palelintangan, Tika apps): "SAKA Palelintangan and SAKA Tika help users understand complex Balinese calendrical systems through intuitive, easy-to-use interfaces."
- **Refs**:
  - https://www.babadbali.com/pewarigaan/kalender-saka.htm/
  - https://www.babadbali.com/pewarigaan/kalebali.php/
  - https://www.babadbali.com/pewarigaan/pewarigaan.php/
  - https://github.com/peradnya/balinese-date-js-lib
  - https://www.sakamuseum.org/en/articles/kala-02-timeless-balinese-calendars-meet-digital-innovation
  - https://kalenderbali.org/?bulan=6&tanggal=17&tahun=2026
  - https://kalender365.id/galungan-tanggal-berapa/
  - https://www.detik.com/bali/berita/d-8293016/jadwal-lengkap-hari-raya-hindu-sepanjang-tahun-2026-menurut-kalender-bali

### 7.2 Adat law & banjar

- **Definition**: "Adat is a set of local Balinese customs and traditions that govern the way locals interact with each other, conduct ceremonies, and manage their communities. Adat law is a traditional customary legal system that governs various aspects of daily life, community affairs, and cultural practices, rooted in Hindu-Buddhist principles and intertwined with local customs."
- **Banjar institution**: explanatory primer at `whatsnewindonesia.com/bali/feature/education/balis-banjar-where-tradition-culture-and-community-thrive`.
- **Anthropology authority**: "Dr. Brigitta Hauser-Schäublin, Emeritus Professor in Ethnology at Georg-August-Universität in Göttingen, notes that the Balinese see themselves as masyarakat adat ('people whose life is governed by traditions')."

### 7.3 Yadnya (rite categories) reference

- **Manusa Yadnya**: "Life-cycle ceremonies from birth to adulthood, like tooth-filing and otonan, purify and guide individuals."
- **Galungan & Kuningan**: "ten‑day celebration of dharma over adharma, with the island shining with penjor bamboo poles and offerings, honoring ancestors."
- **Ngaben**: "the traditional Balinese cremation ceremony, symbolizing the release of the soul from the body, allowing it to reincarnate."
- Background quotes drawn from Dijiwa Sanctuaries / Bali Holiday Secrets / Bali Institute / Bali Yoga Guide guides — useful as English-language briefing material for clients/expats.
- **Refs**:
  - https://dijiwasanctuaries.com/magazine/balinese-culture-traditions-guide
  - https://www.baliholidaysecrets.com/balinese-culture/
  - https://baliinstitute.com/blog/bali-culture/
  - https://baliyogaguide.com/blog/balinese-culture-customs-traditions/
  - https://en.wikipedia.org/wiki/Balinese_people

### 7.4 Indonesian culture & travel

- **Kompas Travel** (vertical of Kompas.com) — daily destination + cultural feature.
- **NB-5 (NotebookLM property/culture)** + research/property captures (`~/Desktop/nuzantara/research/property/`) — internal layered intelligence already curated.

> Bali Zero internal note: cross-reference §7 with NotebookLM `NB-5` (property/Bali) + `NB-CULTURE` if/when promoted. Galungan/Kuningan 2026 dates (June 17/27) are decision-relevant for client scheduling, banjar approval timelines, vendor closures.

---

## 8. Geopolitical Patterns Indonesia 2026

### 8.1 Indonesia ↔ China (BRI / Nickel)

- **Quote (CSIS)**: "China grabbed 75% of Indonesia's Nickel Refining" (Decoding the Dragon analysis frequently cited).
- **Carnegie**: "How Indonesia Used Chinese Industrial Investments to Turn Nickel into the New Gold."
- **IMIP / Morowali (BRI flagship)**: "The Indonesia Morowali Industrial Park (IMIP), largely financed and constructed by Chinese companies such as Tsingshan Holding Group, stands as a flagship Belt and Road project. In 2013, at the launch of the 21st-Century Maritime Silk Road, Tsingshan signed a memorandum of understanding—witnessed by Xi Jinping and then Indonesian president Susilo Bambang Yudhoyono—to develop what became the Indonesia Morowali Industrial Park (IMIP)."
- **2026 expansion**: "A smelter is expected to be operational by 2026, with a production capacity of 60,000 tonnes of nickel and 5,000 tonnes of cobalt per year in mixed hydroxide precipitate. Additionally, tailings are projected to grow more than fourfold by 2026 to 47 million tonnes."
- **Investigative**: Project Multatuli's "China in the Downstream: Beijing Tightens its Stranglehold on Indonesia's Nickel Industry."
- **Incident 2026**: "on 18 February 2026, a landslide occurred inside the Morowali Industrial Park (IMIP) in Indonesia, one of the world's major nickel mining hubs. One employee was killed by the collapse in a tailings storage area, and operations were suspended."
- **Refs**:
  - https://carnegieendowment.org/research/2023/04/how-indonesia-used-chinese-industrial-investments-to-turn-nickel-into-the-new-gold
  - https://projectmultatuli.org/en/beijing-tightens-its-stranglehold-on-indonesias-nickel-industry/
  - https://www.nbr.org/publication/chinas-influence-in-indonesias-nickel-sector-and-implications-for-the-united-states/
  - https://www.lowyinstitute.org/the-interpreter/china-isn-t-main-culprit-indonesia-s-dirty-nickel-boom
  - https://www.aspistrategist.org.au/chinas-investment-in-indonesia-is-its-global-critical-minerals-template/

### 8.2 Indonesia ↔ USA (trade + Indo-Pacific)

- **White House fact sheet (Feb 2026)**: "On February 19, 2026, the Trump Administration finalized a landmark trade agreement with Indonesia ... President Donald J. Trump and Indonesian President Prabowo Subianto signed a document confirming their strong commitment to implementing this agreement."
- **Tariff terms**: "The United States will maintain a 19% reciprocal tariff rate for imports from Indonesia, except for certain identified products which will receive a 0% reciprocal tariff rate. The U.S. pledged tariff exemptions for certain Indonesian commodities that are not produced in the U.S., including palm oil, cocoa, coffee, and tea."
- **Indonesia commitments**: "Indonesia will eliminate tariff barriers on over 99% of U.S. products exported to Indonesia ... Indonesia will facilitate $10 billion of direct investment in the United States and import up to $33 billion worth of U.S. goods and services, mostly energy, aviation and agricultural products."
- **Twist**: "Twenty-four hours after the agreement was signed on February 19, 2026, the U.S. Supreme Court ruled 6-3 that the legal foundation underpinning Washington's economic pressure on Jakarta was unconstitutional." (Eurasia Review)
- **Defence (April 2026)**: "On the same day as Prabowo's Moscow meeting, Indonesia and the United States announced a new defense cooperation agreement." (Diplomat APAC)
- **Refs**:
  - https://www.whitehouse.gov/fact-sheets/2026/02/fact-sheet-trump-administration-finalizes-trade-deal-with-indonesia/
  - https://id.usembassy.gov/fact-sheet-trump-administration-finalizes-trade-deal-with-indonesia/
  - https://thediplomat.com/2026/03/what-does-indonesia-get-out-of-the-us-indonesia-agreement-on-reciprocal-trade/
  - https://www.eurasiareview.com/20042026-signed-on-a-crumbling-foundation-how-indonesias-trade-deal-with-washington-unraveled-in-24-hours-analysis/
  - https://www.bloomberg.com/news/articles/2026-02-20/trump-prabowo-finalize-trade-deal-slashing-tariff-rate-to-19
  - https://asia.nikkei.com/economy/trade-war/trump-tariffs/indonesia-us-sign-tariff-deal-with-exemptions-for-key-soft-commodities
  - https://thediplomat.com/2026/04/indonesia-us-announce-new-defense-partnership-as-prabowo-visits-russia/

### 8.3 Indonesia ↔ Australia (DFAT)

- **Jakarta Treaty 2026 (Feb)**: Lowy: "Australian Prime Minister Anthony Albanese visited Jakarta in February 2026 to meet with President Prabowo, with a Treaty of Common Security expected to be signed as the centrepiece of the visit."
- **Strategic positioning**: "Australia is now Indonesia's second-most important defence partner after the United States, ranking highly in joint exercises and military education exchanges."
- **Critical view (Lowy)**: "the Australia-Indonesia pact won't shift the regional balance" — middle-power consultation vs blocs.
- **Refs**:
  - https://www.lowyinstitute.org/the-interpreter/placebo-risk-australia-indonesia-common-security-treaty
  - https://www.lowyinstitute.org/the-interpreter/australia-indonesia-pact-won-t-shift-regional-balance
  - https://www.lowyinstitute.org/the-interpreter/indonesia-australia-security-treaty-middle-powers-choosing-consultation-over-blocs
  - https://www.lowyinstitute.org/the-interpreter/step-not-leap-assessing-indonesia-australia-defence-cooperation-agreement

### 8.4 Indonesia ↔ EU (palm oil, CEPA)

- **CEPA**: "Indonesia and the EU inked the Comprehensive Economic Partnership Agreement (IEU-CEPA) earlier this year (2026). The agreement texts are undergoing legal check and translation as of March 2026, with implementation expected around 2027 after ratification."
- **Palm oil framing**: "Indonesia's palm oil industry has called the IEU-CEPA a 'golden ticket' for the country's palm oil exports because the commodity will be free to compete on equal footing with domestic oils such as those derived from rapeseed."
- **EUDR friction (still binding)**: "Although the new IEU-CEPA framework allows the European Union to buy Indonesia's palm oil at zero tariffs, this deal alone is not enough to guarantee smooth exports to Europe." Indonesian Trade Minister Budi Santoso (Sep 2025) noted EU "began to soften its stance on the EUDR following the signing of the Indonesia-EU CEPA."
- **Deforestation reality**: "gross deforestation in Indonesia in 2025 was on track to at least match 2024's tally, which reflected the most extensive losses since 2019, and Indonesia's Merauke Food Estate project involves clearing at least 2 million hectares of forest." (Mongabay Jan 2026)
- **WTO dispute (legacy)**: DS593 EU vs Indonesia palm-oil/biofuel measures — open file at WTO.
- **Refs**:
  - https://ecipe.org/insights/eu-indonesia-cepa/
  - https://jakartaglobe.id/business/eu-trade-pact-a-boon-for-indonesian-palm-oil-but-deforestation-law-remains-in-the-way
  - https://news.mongabay.com/2026/01/after-years-of-progress-indonesia-risks-tragedy-of-a-deforestation-spike/
  - https://www.fern.org/fileadmin/uploads/fern/Documents/2026/Fern_The_EU-Indonesia_Comprehensive_Economic_Partnership_and_Investment_Protection_Agreements_2026.pdf
  - https://www.wto.org/english/tratop_e/dispu_e/cases_e/ds593_e.htm
  - https://link.springer.com/article/10.1007/s10308-025-00732-5

### 8.5 Indonesia ↔ Russia (post-Ukraine)

- **Prabowo–Putin meetings**: "President Prabowo Subianto met with Russian President Vladimir Putin in Moscow, with the two presidents agreeing to increase cooperation on energy and economic issues. This was Prabowo's third visit to Russia in less than a year, with the likely purpose being to consolidate recent progress in relations with Russia and to secure shipments of Russian oil to help fill the current shortfall of supplies from the Gulf." (Foreign Policy April 15 2026)
- **Energy + nuclear**: "Putin offered nuclear energy cooperation and hailed deepening military ties, with the meeting focusing on boosting wheat exports and technology transfers amid ongoing Western sanctions over Ukraine. Both leaders noted strong military cooperation, including Indonesian personnel training in Russia and joint naval exercises in the Java Sea."
- **Doctrine framing**: "Prabowo's administration intends to maintain Indonesia's non-aligned foreign policy doctrine, which emphasizes sustained defense engagements with all major powers, including China and Russia."
- **Refs**:
  - https://foreignpolicy.com/2026/04/15/prabowo-indonesia-russia-putin-visit-us-defense-agreement/
  - https://thediplomat.com/2026/04/indonesia-us-announce-new-defense-partnership-as-prabowo-visits-russia/
  - https://www.thejakartapost.com/world/2025/12/11/putin-meets-prabowo-to-discuss-military-and-energy-ties-wheat-exports.html
  - https://asia.nikkei.com/politics/international-relations/putin-offers-indonesia-s-prabowo-support-on-nuclear-energy
  - https://www.scmp.com/week-asia/politics/article/3336244/indonesia-urged-tread-carefully-russia-courts-prabowo-energy-and-defence-offers
  - https://en.antaranews.com/amp/news/412131/indonesia-russia-deepen-ties-in-cordial-prabowo-putin-meeting

### 8.6 ASEAN dynamics 2026 (Philippines chair)

- **Theme**: "The Philippines took over the ASEAN Chairmanship on January 1, 2026 with the theme 'Navigating Our Future, Together,' steering ASEAN's priorities through three pillars: Peace and Security Anchors, Prosperity Corridors, and People Empowerment."
- **South China Sea Code of Conduct**: "The Philippines has pledged to conclude a legally binding Code of Conduct (COC) in the increasingly contested South China Sea by the end of its chairmanship." Chatham House view: "Tensions between China and the Philippines make agreement on a South China Sea code of conduct unlikely. China is unlikely to grant the Philippines—its most vocal challenger in the South China Sea and a U.S. treaty ally—any political or symbolic victory during its ASEAN chairmanship."
- **US-PH bilat overlay**: "Manila has made clear it intends to prioritize two parallel initiatives that reflect the region's evolving reality: renewed efforts to finalize a legally binding code of conduct with China and a dramatic expansion of U.S.-Philippines military cooperation, with more than 500 joint activities planned for the year."
- **Indonesia angle**: as ASEAN heavyweight + new BRICS member, Indonesia plays balancer; multi-alignment doctrine continues to test ASEAN unity. Risk: "Intra-ASEAN divisions, the continuing crisis in Myanmar and emerging challenges such as digital governance, economic resilience, supply chain security and disaster management will test the bloc's ability to advance a coherent agenda."
- **Refs**:
  - https://www.chathamhouse.org/2025/12/philippines-asean-chair-south-china-sea-agreement-unlikely-be-concluded-2026
  - https://www.csis.org/analysis/rhetoric-vs-reality-philippines-asean-and-south-china-sea
  - https://www.iseas.edu.sg/mec-events/the-philippines-2026-asean-chairmanship-priorities-challenges-and-regional-implications/
  - https://foreignpolicy.com/2026/01/19/philippines-asean-southeast-asia-china-us-trump-tariffs-security-south-china-sea-myanmar/
  - https://worldview.stratfor.com/article/previewing-philippines-2026-asean-chairmanship

### 8.7 BRICS expansion — Indonesia inside

- **Membership confirmed (Jan 2025, in force 2026)**: "Brazil, as BRICS chairman in 2025, announced that Indonesia had officially joined the bloc, becoming **the first Southeast Asian nation to do so**. After being officially declared a full member in January 2025, Indonesia was immediately accepted as the 10th member of BRICS."
- **Prabowo's ownership**: "President Prabowo Subianto prioritized joining BRICS shortly after entering office in October, with Indonesia initially being one of 13 countries invited to become a BRICS partner country, alongside Malaysia, Thailand, and Vietnam. Just days after his inauguration, he sent Foreign Minister Sugiono to the BRICS Summit in Kazan, Russia to formalize Indonesia's application."
- **Multi-alignment ballast**: "Indonesia's formal admission in early 2025 aligns with its commitment to equilibrium through multi-alignment, shown through a parallel application to the Organisation for Economic Co-operation and Development."
- **Regional spread**: "Alongside Indonesia, BRICS also admitted three other Southeast Asian nations – Malaysia, Vietnam, and Thailand – as new members."
- **Refs**:
  - https://www.csis.org/blogs/latest-southeast-asia/latest-southeast-asia-indonesia-joins-brics
  - https://thediplomat.com/2025/01/indonesia-officially-becomes-first-southeast-asian-member-of-brics/
  - https://thediplomat.com/2025/01/what-brics-membership-means-for-indonesias-foreign-policy/
  - https://eastasiaforum.org/2025/03/06/indonesias-brics-accession-underscored-by-prabowos-self-interest/
  - https://www.aspistrategist.org.au/joining-brics-indonesia-sticks-with-multi-alignment-strategy/
  - https://en.antaranews.com/news/364601/indonesias-brics-membership-is-prabowos-first-year-initiative
  - https://www.aljazeera.com/news/2025/1/7/indonesia-joins-brics-group-of-emerging-economies

### 8.8 Prabowo administration foreign policy 2026 (synthesis)

- **Doctrine** (Lowy synthesis): "Prabowo has attempted to pursue 'multi-alignment' in foreign policy, which shifts Indonesia's traditional 'non-aligned' position by aiming to craft cooperation with both great powers and like-minded countries."
- **Operational track record (2026 observations)**:
  - US-ART signed 19 Feb 2026 (19% reciprocal tariff, $33B US imports commitment), shaken by SCOTUS ruling within 24h.
  - Australia: Jakarta Treaty 2026 signed February.
  - EU: IEU-CEPA inked 2026, ratification ~2027.
  - Russia: Prabowo's third Moscow visit (April 2026); nuclear + energy + wheat.
  - China: deeper nickel value-chain entanglement (Tsingshan, IMIP).
  - BRICS: full member from Jan 2025.
  - OECD: parallel accession track open.
- **Domestic ballast issues** (CSIS, Habibie, TII):
  - Fiscal precariousness ("Big Promises, Tight Budget")
  - Creeping militarization (battalion expansion)
  - Narrowing dissent space (Habibie panel May 2026)
  - Negative economic outlook (TII March 2026)
- **External multi-LLM/think-tank consensus**: structurally, Indonesia is hedging across all major poles; risk surface for Bali Zero clients is concentrated in (a) fiscal volatility (rupiah, capital controls?), (b) regulatory accelerations under "Asta Cita" (PMA visa rules, KBLI risk reclassifications already observed in property/tourism — see internal research captures), (c) tighter dissent posture influencing online speech / ITE law enforcement.

---

## Appendix A — Lifecycle Mapping for NB-INTEL-COUNTRY (Nuzantara internal)

| Lifecycle stage                           | Source layer                                                                           | Cadence           | NB target                           |
| ----------------------------------------- | -------------------------------------------------------------------------------------- | ----------------- | ----------------------------------- |
| **Nasce** (raw signal)                    | GDELT (free), ACLED (free), Antara RSS, BPS WebAPI                                     | 15 min – daily    | NB-INTEL-RAW                        |
| **Cresce** (curated)                      | Tempo, Kompas.id, Jakarta Post, Project Multatuli, Tirto                               | daily             | NB-INTEL-PRESS                      |
| **Auto-correct** (think-tank cross-check) | CSIS Indonesia, ISEAS Perspective, Lowy Interpreter, New Mandala, FULCRUM              | weekly            | NB-INTEL-ANALYSIS                   |
| **Cosciente** (panel synthesis)           | DroneEmprit + Indonesia Indicator + bipolar verifier (LLM main + NB)                   | weekly digest     | NB-INTEL-SOCIAL + NB-INTEL-ANALYSIS |
| **Canalizza** (decision support)          | World Bank / IMF / ADB / OJK quarterly + chambers (BritCham/EuroCham/AmCham) bulletins | per-case briefing | NB-INTEL-BUSINESS-BRIEF             |

Bali-specific overlay:

- Tourism arrivals (BPS Bali) → monthly
- The Bali Sun + NusaBali + Bali Post → daily expat/local pulse
- Saka/Pawukon calendar (Babad Bali + JS lib) → ceremony scheduler for client cases (penjor, banjar avail, road closures)

---

## Appendix B — Key Calendar Anchors 2026 (Bali Zero ops)

| Date           | Event                                               | Source                            |
| -------------- | --------------------------------------------------- | --------------------------------- |
| 2026-01-07     | BRICS membership effective (in-year cycle)          | thediplomat.com (2025)            |
| 2026-01-21     | IMF Article IV publication on Indonesia             | imf.org                           |
| 2026-02-19     | Indonesia–US ART signed (Trump–Prabowo)             | whitehouse.gov                    |
| 2026-02-20     | SCOTUS 6-3 ruling shakes ART legal base             | eurasiareview.com                 |
| 2026-02 (mid)  | Jakarta Treaty (Australia–Indonesia)                | lowyinstitute.org                 |
| 2026-04-14/15  | Prabowo in Moscow (3rd visit) + new US defense pact | foreignpolicy.com / aljazeera.com |
| 2026-05-05     | CSIS warns "creeping militarization"                | thejakartapost.com                |
| **2026-06-17** | **Galungan** (Wed) — banjar offline cycle starts    | babadbali.com                     |
| **2026-06-27** | **Kuningan** (Sat) — closes Galungan ten-day cycle  | babadbali.com                     |
| 2026 (TBD)     | IEU-CEPA ratification track (target 2027)           | ecipe.org                         |

End of R6.
