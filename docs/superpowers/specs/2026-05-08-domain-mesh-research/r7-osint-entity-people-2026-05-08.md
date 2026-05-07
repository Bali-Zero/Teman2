# Nexus OSINT — Entity Tracking + People-Graph for Indonesia

**Bali Zero research mission, 2026-05-08**
**Scope**: ministri, regulator heads (BKPM/DJP/Imigrasi), Pemprov Bali, business networks Indonesia. 8 sezioni, min 5 fonti per sezione, quote integrali.

---

## 1. OSINT Entity-Graph Platforms

### 1.1 Maltego (Paterva)

Architettura: entity-relationship model con "transforms" come unità di estrazione dati.

> "In Maltego, an Entity represents a single piece of data you want to investigate or analyze. It can be something as simple as an email address, a phone number, a domain name, or an IP address." — StationX

> "Transforms in Maltego are specialized pieces of code that process information in a very particular way. They take an Entity (a defined piece of data like an email address, IP address, or name) as input and then search for related information, returning more Entities as output." — Securium Solutions

> "With Maltego, you can easily mine data from disparate sources, automatically merge matching information in one graph, and visually map it to explore your data landscape. Via the Data Hub, you can connect data from over 30 data partners, a variety of public sources (OSINT) as well as your own data and systems." — Maltego.com

> "Every investigation in Maltego begins with an entity. You drag the entity onto the graph and run transforms. Transforms are automated queries that gather related data. You can continue running transforms on newly discovered entities. This allows you to pivot deeper into the investigation." — Redfox Security (Mar 2026)

URL: https://www.maltego.com/ · Transform Hub include OCCRP Aleph, LittleSis (vedi §3) — direttamente utili per Indonesia tracking.

### 1.2 Aleph (OCCRP)

Open-source platform per "follow the money" — corporate registries + leaks + sanctions in un indice unico.

> "Aleph is a data platform created and maintained by the Organized Crime and Corruption Reporting Project (OCCRP). The tool was built to help investigative journalists track people and companies, usually as part of their corruption investigations." — Bellingcat Toolkit

> "The platform consolidates data from millions of documents, including corporate registries, financial records, leaks, and legal filings, and makes them searchable and cross-referable. Aleph allows cross-referencing mentions of well-known entities (such as people and companies) against watchlists, from prior research or public datasets." — GIJN

> "Each of the names, emails, and entity types in datasets is hyperlinked and opens a new page for the selected item." — docs.aleph.occrp.org

> "Aleph Pro, a next-generation version of Aleph, is launching in October 2025, designed as a faster, more powerful platform for journalists, civic technologists, and investigators." — aleph.discourse.group

URLs: https://docs.aleph.occrp.org/ · https://github.com/alephdata/aleph · Maltego transform: https://www.maltego.com/transform-hub/occrp-aleph/

### 1.3 Palantir Gotham — architecture pattern (NOT for Bali Zero use, ma reference architettonico)

Dynamic ontology a 3 layer: semantic + kinetic + dynamic. Pattern utile da imitare in Nexus OSINT custom.

> "The Ontology sits on top of the digital assets integrated into the Palantir platform (datasets, virtual tables, and models) and connects them to their real-world counterparts… In many settings, the Ontology serves as a digital twin of the organization, containing both the semantic elements (objects, properties, links) and kinetic elements (actions, functions, dynamic security) needed to enable use cases of all types." — palantir.com/docs/foundry/ontology

> "Object Explorer is Palantir Gotham's top-down analysis application, which offers users an intuitive, user-friendly way to analyse vast sets of data. Object Explorer enables users to find entities with similar characteristics and visualise their relationships, run analyses on millions of records at a time." — UK G-Cloud service definition

> "This is analogous to how Palantir's Gotham would find a connection between two people through a chain of links (e.g., Person A–attended same event–as Person B)." — HackMD GPT-5 analysis

3 layer (Medium di Cristian Caruso):

1. **Semantic Layer**: defines the conceptual model — entities, links, properties.
2. **Kinetic Layer**: connects meaning to actual data (databases, APIs, files).
3. **Dynamic Layer**: business rules, workflows, permissions, behavior.

Pattern Bali Zero adopt: separate `entity_definition.yaml` (semantic) da `data_loaders/*.py` (kinetic) da `policy_rules/*.rego` (dynamic).

### 1.4 Investigative Dashboard (OCCRP ID — formerly Investigative Dashboard)

Service di ricerca umana + worldwide company database + Aleph backend.

> "OCCRP ID is an OCCRP service that helps investigative journalists in the OCCRP network conduct research quickly and effectively. Previously known as Investigative Dashboard, OCCRP ID is currently made up of nine researchers based in Latin America, South Asia, the Balkans, Eastern Europe, and the Middle East." — id.occrp.org

> "OCCRP ID offers the public access to a one-of-a-kind global index of registries from 180+ countries in one place. More specifically, OCCRP ID provides a Worldwide Company Database — an ever-expanding list of databases containing information on companies from all over the world, from official sources such as state corporate registries and land records to commercial databases of companies." — OCCRP ID

> "The Dashboard consists of an extensive crowd-sourced database, put together by dozens of reporters and civic hackers, and more than 400 online databases in 120 jurisdictions, including vast numbers of company registration records and other related public records." — GIJN

URLs: https://id.occrp.org/ · https://id.occrp.org/databases/ · Indonesia coverage incluso (AHU MoLHR via OCCRP ID research desk).

### 1.5 Quiztime / Bellingcat Toolkit

Quiztime non è un tool ma una community + curated tool collection.

> "Quiztime's founder Julia Bayer, a journalist and trainer at Deutsche Welle, curates a collection of research tools. Quiztime publishes 'Week in OSINT' and offers Quiztime challenges." — Fiete Stegers, Quiztime/Medium

> "Bellingcat's toolkit includes satellite and mapping services, tools for verifying photos and videos, websites to archive web pages, and much more. Most of the tools that they include can be used for free." — Bellingcat GitBook

> "The toolkit helps you discover tools in categories like satellite imagery and maps, social media, transportation, or archiving, and is designed to help researchers learn how to use each tool by providing in-depth descriptions, common use cases and information on requirements and limitations for each toolkit entry." — Bellingcat GitBook

URLs: https://bellingcat.gitbook.io/toolkit · https://github.com/bellingcat/toolkit

### 1.6 Hunchly

Browser-based evidence capture con SHA-256 hash chain — chiave per Bali Zero compliance dossier.

> "Hunchly automatically collects the URL, timestamps, and hashes of every page you visit and makes full-page captures of sites, searches, and social media." — Forensic Notes

> "As the user browses, Hunchly automatically captures every page visited during a case session, computes a hash, and stores screenshots and metadata in a local archive, with the underlying logic being 'everything I see while working on the case must be reconstructible': a useful paradigm for long investigations on the deep web, social platforms, and cryptocurrency tracing." — Truescreen.io comparison

> "Hunchly automatically generates a SHA-256 hash for every captured page and image. This hash is your digital seal, proving the evidence has not been altered since capture." — Marie Landry Spy Shop, Apr 2026

> "It's important to note that Hunchly does not produce evidence with legal weight in a European court: there is no qualified timestamp, no QTSP digital seal, no ISO/IEC 27037 certified process. The archive is reliable to reconstruct an internal OSINT investigation, but when a Hunchly artifact needs to land in criminal or civil proceedings, a re-acquisition with a forensic-grade tool is almost always required." — Truescreen.io

URL: https://hunch.ly/ · Cost: ~$130 USD/anno license. Versione attuale (2026): Hunchly 2.5.3.

---

## 2. Open-Source OSINT Frameworks

### 2.1 SpiderFoot (smicallef/spiderfoot)

> "SpiderFoot is an open source intelligence (OSINT) automation tool. It integrates with just about every data source available and utilises a range of methods for data analysis, making that data easy to navigate." — Kali Linux Tools

> "SpiderFoot has over 200 modules, most of which don't require API keys, and many of those that do require API keys have a free tier. SpiderFoot is a free, open-source intelligence (OSINT) automation framework written in Python 3." — GeeksforGeeks

> "SpiderFoot HX enables you to 'fire and forget' scan to collect OSINT from over 100 data sources without writing a single line of code. Integrate with your other tools through SpiderFoot HX's fully documented API. SpiderFoot HX also automatically analyzes scan data to identify data points that may be of most interest through its Correlations feature." — spiderfoot.net (Intel 471 ora owner)

GitHub: https://github.com/smicallef/spiderfoot · Active (200+ mods). HX commercial: https://www.spiderfoot.net/

### 2.2 Recon-ng (lanmaster53/recon-ng)

> "Recon-ng is an Open Source Intelligence gathering tool aimed at reducing the time spent harvesting information from open sources. Recon-ng is a completely modular framework and makes it easy for even the newest of Python developers to contribute." — README

> "Each module is a subclass of the Module class, a customized cmd interpreter with built-in interfaces for common tasks such as standardizing output, interfacing with the database, making web requests, and managing third party resource credentials." — recon-ng/recon/core/module.py

GitHub: https://github.com/lanmaster53/recon-ng + marketplace https://github.com/lanmaster53/recon-ng-marketplace · pattern: console-style come Metasploit. Recent commits 2026 active.

### 2.3 theHarvester (laramies/theHarvester)

> "theHarvester is a simple to use, yet powerful tool designed to be used during the reconnaissance stage of a red team assessment or penetration test. It performs open source intelligence (OSINT) gathering to help determine a domain's external threat landscape." — README

> "The tool gathers names, emails, IPs, subdomains, and URLs by using multiple public resources… The tool integrates with numerous OSINT data sources including censys, certspotter, criminalip, dnsdumpster, duckduckgo, hackertarget, and haveibeenpwned." — README

GitHub: https://github.com/laramies/theHarvester · Python 3.12+ required (2026). Maintained continuously since 2011.

### 2.4 Photon (s0md3v/Photon)

> "Photon is an incredibly fast crawler designed for OSINT… Can be launched using a lightweight Python-Alpine (103 MB) Docker image. Extracted information is saved in an organized manner or can be exported as json." — README

> "Users can fetch URLs archived by archive.org to be used as seeds by using --wayback option." — README

GitHub: https://github.com/s0md3v/Photon · Note: progetto un po' meno attivo recentemente (s0md3v ha mosso focus su altri tool — verifica last commit).

### 2.5 Sherlock (sherlock-project/sherlock)

> "Sherlock is an open-source OSINT tool designed to find usernames across a wide range of social networks and websites, with current version 0.16.0 published September 16th, 2025." — Bellingcat Toolkit

> "Sherlock is an open-source OSINT (Open-Source Intelligence) tool designed for automatically checking whether a username exists across hundreds of platforms and social networks. It does not require API keys or login credentials for the sites it checks; instead, it simply constructs the expected profile URL for each site and observes the response to determine whether the username exists on a given platform." — oshy.tech 2025

> "The tool can search for any username across 460+ platforms instantly." — Web Asha

GitHub: https://github.com/sherlock-project/sherlock · `pipx install sherlock-project` · 200+ contributors. Use case Bali Zero: cross-check username pejabat/business owners.

### 2.6 Maigret (soxoj/maigret)

> "Maigret is an easy-to-use and powerful OSINT tool for collecting a dossier on a person by a username (alias) only through checking for accounts on a huge number of sites and gathering all the available information from web pages." — Bellingcat Toolkit

> "Maigret is a Python script that retrieves user information by searching for usernames across various websites and social media platforms, checking for accounts across over 3000 sites without the need for API keys." — README

> "Maigret has a built-in web UI with a results graph and downloadable reports. The tool can generate HTML, PDF, and Xmind8 reports, as well as machine-readable exports in JSON, CSV, and TXT formats." — README

GitHub: https://github.com/soxoj/maigret · Fork of Sherlock, 10× più siti coperti (3000+).

### 2.7 Holehe (megadose/holehe)

> "Holehe checks if an email is attached to an account on sites like twitter, instagram, imgur and more than 120 others. It retrieves information using the forgotten password function." — README

> "It does not alert the target email, runs on Python 3, and can be run from the CLI and rapidly embedded within existing python applications. Sometimes partially obfuscated recovery emails and phone numbers are returned." — README

GitHub: https://github.com/megadose/holehe · Use case: pre-screening client/counterparty email pre-onboarding Bali Zero.

### 2.8 Mosint (alpkeskin/mosint)

> "Mosint is an automated email osint tool written in Go that allows you investigate for target emails in a fast and efficient manner. It consolidates numerous services, enabling security researchers to swiftly access a wealth of information." — README

> "It can validate emails, check social accounts with Socialscan and Holehe, check data breaches and password leaks, find related emails and domains, and scan Pastebin and Throwbin dumps. It also supports Google Search, DNS Lookup, and IP Lookup functions, with output to text file." — README

GitHub: https://github.com/alpkeskin/mosint · Go-based (più veloce di Holehe Python in batch).

---

## 3. People-Graph SaaS / Sanctions

### 3.1 OpenSanctions (opensanctions.org)

> "The OpenSanctions API lets you integrate OpenSanctions into your workflow to search the database and conduct batch screening to identify people or companies on sanctions lists or linked to politically exposed persons (PEPs)." — opensanctions.org/api

> "OpenSanctions Default is a collection that bundles together entities from 325 data sources, and OpenSanctions has over 320 separate dataset collections with multiple sources of data." — opensanctions.org/datasets

**Indonesia coverage diretta**:

> "Indonesian List of Suspected Terrorists and Terrorist Organizations: A list of suspected terrorists and terrorist organizations as determined by the Central Jakarta District Court. You can fetch a simplified tabular form or detailed structured data in JSON format, with updated files provided once a day." — opensanctions.org/datasets/id_dttot

> "Indonesia 2018 Regional Head Election Results: This dataset covers Governors, Regents, and Mayors elected in the 2018 Indonesian regional elections." — opensanctions.org/datasets/id_regional_2018

Cost: free non-commercial / data license commerciale. URL: https://www.opensanctions.org/ · GitHub: https://github.com/opensanctions/opensanctions

### 3.2 LittleSis (public-accountability/littlesis-rails)

> "LittleSis is a free database of who-knows-who at the heights of business and government… brings transparency to influential social networks by tracking the key relationships of politicians, business leaders, lobbyists, financiers, and their affiliated institutions." — littlesis.org/database/about

> "LittleSis started in 2009 and its database contains over 1.6 million relationships between over 400 thousand people and organizations. The data derives from government filings, news articles, and other reputable sources, with some data sets updated automatically and the rest filled in by the user community." — littlesis.org

> "The LittleSis API exposes the raw data used on the LittleSis website, consisting of basic information about people and organizations ('entities'), and the relationships between them. It uses a RESTful interface and responses are formatted in XML and JSON." — littlesis.org/api

URL: https://littlesis.org/api/ · GitHub: https://github.com/public-accountability/littlesis-rails · Indonesia coverage limitata (US-focused) ma utile per cross-border tracking quando un soggetto BKPM ha business US.

### 3.3 Sayari Graph

> "Sayari Graph provides global corporate ownership and control data from 450+ government sources in 250+ jurisdictions, including high-risk, emerging, and global offshore markets." — sayari.com/platform/graph

> "The platform can surface beneficial owners and subsidiaries even when corporate structures span 20+ shell companies across 15 jurisdictions, with what would take analysts days to map manually being surfaced in minutes." — sayari.com

> "Sayari can accelerate cross-border investigations into illicit financial activity with comprehensive beneficial ownership information from offshores and hard-target jurisdictions." — sayari.com/automated-beneficial-ownership

URL: https://sayari.com/ · Cost: enterprise (5-figure USD/anno tipico). Indonesia: yes — coverage via PT/CV, AHU, Mahkamah Agung records. US Dept of Commerce contract 2024.

### 3.4 Refinitiv World-Check (LSEG)

> "World-Check is a database of politically exposed persons (PEPs) and 'heightened risk' individuals and organizations. World Check formed part of the Thomson Reuters Risk Management Solutions suite before being transferred to Refinitiv after a merger deal with The Blackstone Group in October 2018. The database is now operated by LSEG Risk Intelligence (London Stock Exchange Group)." — Wikipedia

> "It cross-references individuals and entities against sanctions lists, politically exposed persons (PEP) data, and adverse media, giving compliance teams a structured way to assess risk before onboarding a client. World-Check maintains one of the deepest Politically Exposed Person databases in the industry, covering current and former government officials, their relatives, and close associates across 240+ countries." — StackGo

> "World-Check, operated by Refinitiv/LSEG, is the most widely used global sanctions and risk intelligence database, screening over 500 million people and entities against sanctions lists, PEP registers, and adverse media sources. World-Check profiles are updated daily by a global research team to reflect the latest sanctions, regulatory actions, and media coverage." — Sanctscan

URL: https://www.lseg.com/en/risk-intelligence/screening-solutions/world-check-kyc-screening · Cost: enterprise.
Caveat 2026: false-positive lawsuits → "World-Check Dispute Lawyer" market exists, indica unreliability.

### 3.5 Dow Jones Risk Center

> "The Dow Jones Risk & Compliance Watchlist consolidates data on individuals and entities subject to increased risks, including sanctioned parties, companies owned or controlled by sanctioned parties, politically exposed persons (PEPs) and their relatives and close associates (RCAs), as well as persons of special interest (SIPs)." — KYC360

> "Screening is performed by screening an individual's name and, when available, date of birth and nationality through Dow Jones Risk and Compliance's Watchlist Standard CSV and XML Feed Services to provide a list of potential matches to sanctions and politically exposed persons (PEPs)." — Maxsight

> "Dow Jones RiskCenter Advanced Screening and Monitoring (ASAM) is a configurable tool with API integration capabilities for fully automated screening." — KYC360

URL: https://kybp.cericosolutions.com/ · Cost: enterprise.

### 3.6 Wikidata as people graph (FREE)

> "Wikidata is a multilingual knowledge graph database that is collaboratively edited and hosted by the Wikimedia Foundation. Wikidata provides a SPARQL endpoint with Web-GUI since September 2015." — Wikidata SPARQL docs

> "From this multilingual and fine granular structured datasource you can select and download lists of names for example of people like politicians for your analysis of document sets & news." — Open Semantic Search

URL: https://query.wikidata.org/ · **Best free option for Bali Zero**: query SPARQL "all current Indonesian ministers" or "DPR members 2024-2029" è gratuita e auto-aggiornata. Property `P39` = position held; `P102` = party; `P108` = employer.

Esempio query (Indonesian PEP starter):

```sparql
SELECT ?person ?personLabel ?position ?positionLabel ?start WHERE {
  ?person wdt:P39 ?position .
  ?position wdt:P17 wd:Q252 .  # Indonesia
  ?person p:P39 ?statement .
  ?statement pq:P580 ?start .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "id,en" }
}
```

### 3.7 Wikipedia / Wikibase (self-hosted ontology pattern)

> "Wikibase is a set of software tools for working with versioned semi-structured data in a central repository, based upon JSON instead of the unstructured data of wikitext normally used in MediaWiki, and stores and organizes information that can be collaboratively edited and read by humans and by computers." — Wikipedia/Wikibase

> "The data model for Wikibase consists of 'entities' which include individual 'items', labels or identifiers to describe them, and semantic statements that attribute 'properties' to the item, where these properties may either be other items within the database, textual information or other semi-structured information." — Wikipedia/Wikibase

> "Properties are describing relationships between items. Statements are how any information known about an item is recorded, formally consisting of key–value pairs, which match a property (such as 'author', or 'publication date') with one or more entity values." — Wikipedia/Wikibase

URL: https://wikiba.se/ · GitHub: https://github.com/shigapov/wikibase-knowledge-graphs · Pattern: Bali Zero potrebbe self-host Wikibase = Nexus OSINT entity store (dump Wikidata Indonesia subset come seed, poi enrich con LHKPN/KPU custom).

---

## 4. Indonesian People / Authority Data Sources

### 4.1 KPK — LHKPN (e-LHKPN portal)

> "LHKPN (Laporan Harta Kekayaan Pejabat Negara) is a list of all assets of state administrators listed in the LHKPN form created by the Corruption Eradication Commission (KPK)… an important instrument used to ensure transparency and accountability of public officials, and through it, the public can know the amount, type, and changes in wealth of state officials from year to year." — kpk.go.id

> "Individuals required to submit LHKPN reports include Echelon II officials and equivalent officials within government agencies or state institutions. Officials with strategic functions such as directors, commissioners, structural officials in State-Owned Enterprises, leaders of the Central Bank, university leaders, Echelon I officials, prosecutors, investigators, court clerks, and even project treasurers are also required to report LHKPN." — kab-yalimo.kpu.go.id

> "The KPK provides LHKPN data accessible to the public without needing to log in, displaying a list of wealth reports from all required reporters that have been verified by the KPK." — kpu.go.id guide

URL: **https://elhkpn.kpk.go.id/** · Search interface: per-pejabat name lookup, asset breakdown JSON. Data: nome, NIP, jabatan, lembaga, total kekayaan, hutang.

### 4.2 KPU — Daftar Caleg / DCT

> "KPU has provided an official online system for the public to view candidate lists for DPR and DPD in their respective regions through the official KPU website." — kpu.go.id

The portal serves multiple datasets:

- Daftar Calon Sementara (DCS): provisional
- Daftar Calon Tetap (DCT): final list per electoral districts

URL: https://infopemilu.kpu.go.id/ · Endpoints utili:

- DPR: https://infopemilu.kpu.go.id/Pemilu/Dct_dpr
- DPD: https://infopemilu.kpu.go.id/Pemilu/Dct_dpd
- DPRD Provinsi/Kabupaten: paths analoghi
- Pasangan Calon (executive elections): https://infopemilu.kpu.go.id/Pemilihan/Pasangan_calon

### 4.3 DPR.go.id — Anggota DPR

> "The main DPR members portal is available at en.dpr.go.id/anggota, which provides access to members of Parliament for the 2024-2029 period, organized by faction, committees, and electoral districts (constituencies)." — dpr.go.id

URLs:

- Members EN: https://en.dpr.go.id/anggota
- Members ID: https://www.dpr.go.id/tentang-dpr/informasi-anggota-dewan
- Open data portal: https://data.dpr.go.id/ ("Satu Data DPR RI")

Ogni profilo: foto, party, dapil, komisi, riwayat pendidikan, riwayat organisasi.

### 4.4 Setkab — Daftar Menteri

> "The current cabinet is the Kabinet Merah Putih (Red and White Cabinet) led by President Prabowo Subianto and Vice President Gibran Rakabuming Raka, established on October 21, 2024, with a tenure through October 20, 2029, consisting of 49 ministries." — setkab.go.id

URL: https://setkab.go.id/profil-kabinet/ + https://setkab.go.id/en/cabinet-profile/

Key ministers (snapshot 2026):

- Coord Politics & Security: Djamari Chaniago
- Coord Economy: Airlangga Hartarto
- Coord Human Dev & Culture: Pratikno
- Coord Infrastructure & Regional Dev: Agus Harimurti Yudhoyono (AHY)
- Interior: Muhammad Tito Karnavian
- Health: Budi Gunadi Sadikin
- Finance: Purbaya Yudhi Sadewa

### 4.5 BKN — ASN/PNS Database (limited public)

> "The BKN RI website is the official portal of Indonesia's State Personnel Agency (Badan Kepegawaian Negara) that provides information about PNS (civil servants)." — bkn.go.id

> "MyASN BKN is a service application for Indonesian National Civil Servants (PNS) from BKN that facilitates access to personnel data… To use the MyASN application, you must first be registered as an ASN (State Civil Apparatus) in the BKN system, and you are required to log in before accessing the services and data available in the MyASN application." — Google Play store description

> "The Satu Data Portal is a management and data sharing medium that can be accessed through information and communication technology for the purpose of data dissemination as a policy for ASN data management to produce accurate, current, integrated, and accountable data that is easily accessible and shareable among central and regional institutions." — satudataasn.bkn.go.id

URLs:

- https://www.bkn.go.id/
- https://satudataasn.bkn.go.id/ (limited public)
- https://helpdesk-sscasn.bkn.go.id/cek_pegawai_non_asn (NIP lookup, when allowed)

Note: full database NOT public — restricted to ASN logged-in. Solo SSCN scraping era pubblico (vedi https://github.com/akirawisnu/ssc-bkn-2019).

### 4.6 BPK — Audit Reports (Badan Pemeriksa Keuangan)

> "BPK (Badan Pemeriksa Keuangan Republik Indonesia) is a high state body in Indonesia responsible for evaluation of management and accountability of state finances conducted by the central government, local governments, Bank Indonesia, state-owned enterprises, the Public Service Board, and institutions or other entities which manage state finances." — bpk.go.id

> "The BPK reports directly to the Indonesian parliament, audits government agencies and state-owned enterprises, issues audit reports and recommendations, and ensures transparency and accountability in public finance." — Wikipedia

URL: https://www.bpk.go.id/page/audit-reports · Searchable by entity (kementerian / lembaga / pemda) → PDF audit reports nominano persone (auditor, auditee). Excellent OSINT mine for "who signed what".

### 4.7 Mahkamah Agung — Judges + Direktori Putusan

> "The Mahkamah Agung Republik Indonesia (MA RI or MA) is a high state institution in Indonesia's constitutional system that holds judicial power jointly with the Constitutional Court and Judicial Commission, and is independent from other branches of power." — mahkamahagung.go.id

> "Judges serving at the Mahkamah Agung are called Supreme Court Judges (Hakim Agung), and consist of leadership (Chief Justice, Deputy Chief Justices, and Chamber Heads) as well as members. The maximum number of supreme court judges is 60 people." — Wikipedia

> "The IKAHI (Ikatan Hakim Indonesia - Indonesian Judges Association) website maintains a member directory listing Supreme Court Judges (Hakim Agung Mahkamah Agung) with their details including place and date of birth and email addresses." — ikahi.or.id/anggota

> "There is a Decision Directory Database (Direktori Putusan) of the Mahkamah Agung Republik Indonesia that allows quick searches for court decisions and policies within the Legal Documentation and Information Network of the Supreme Court." — mahkamahagung.go.id

URLs:

- https://www.mahkamahagung.go.id/
- https://www.ikahi.or.id/anggota (judges directory)
- Direktori Putusan: putusan3.mahkamahagung.go.id (search by name → court rulings mention parties)
- Mahkamah Konstitusi: https://www.mkri.id/

### 4.8 Kompas / Tirto.id (databases + investigations)

> "Tirto.id presents fact-based news and data analysis, written in an engaging way and always accompanied by infographics. It is a born-digital/online news source from Indonesia, often offering alternative perspectives and countering mainstream media." — Library of Congress

> "Kompas is an Indonesian national newspaper published in Jakarta, founded on 28 June 1965. It is considered Indonesia's newspaper of record." — Wikipedia

> "KompasData offers various research services, including in-depth and comprehensive analysis, equipped with visual graphical results that are easy to understand. With experience working with data, facts, and analysis, Kompas Research has the advantage of presenting information in more understandable forms such as text, visual graphics, audio and video according to needs." — KompasData

URLs: https://data.kompas.id/ · https://kompaspedia.kompas.id/ · https://tirto.id/ · https://www.tempo.co/tag/investigasi · https://majalah.tempo.co/kanal/investigasi

---

## 5. Named-Entity Recognition for Bahasa Indonesia (SOTA 2026)

### 5.1 IndoBERT (indolem)

> "IndoBERT is the Indonesian version of BERT model. It was trained using over 220M words, aggregated from three main sources, for 2.4M steps (180 epochs) with the final perplexity over the development set being 3.97." — IndoLEM ACL paper

> "An Indonesian pre-trained language model, IndoBERT, was utilized to provide word embeddings, and for transfer learning settings, IndoBERT was fine-tuned and then tested for NER tasks. On NER tasks, IndoBERT outperforms MBERT, and IndoBERT slightly outperforms MALAYBERT." — IndoLEM paper

URL model: https://huggingface.co/indolem/indobert-base-uncased
GitHub: https://github.com/indolem · Paper: https://aclanthology.org/2020.coling-main.66/

### 5.2 IndoLEM Benchmark

> "IndoLEM is a dataset comprising seven tasks for the Indonesian language, spanning morpho-syntax, semantics, and discourse. IndoBERT, a new pre-trained language model for Indonesian, was released and evaluated over IndoLEM, and experiments show that IndoBERT achieves state-of-the-art performance over most of the tasks in IndoLEM. IndoLEM is a comprehensive Indonesian NLU benchmark, comprising three pillars NLP task: morpho-syntax, semantic, and discourse." — IndoLEM ACL paper

> "The seqeval library was used to evaluate the POS and NER tasks in IndoLEM. Results on NER tasks were measured using entity-level F1 over the test set." — IndoLEM paper

NER UGM dataset (incluso in IndoLEM):

> "NER UGM is a Named Entity Recognition dataset that comprises 2,343 sentences from news articles, and was constructed at the University of Gajah Mada based on five named entity classes: person, organization, location, time, and quantity." — Hugging Face SEACrowd/indolem_ner_ugm

### 5.3 NusaCrowd (IndoNLP)

> "NusaCrowd is a joint collaboration to collect NLP datasets for Indonesian languages. Through this initiative, they have brought together 137 datasets and 118 standardized data loaders. The quality of the datasets has been assessed manually and automatically… NusaCrowd's data collection enables the creation of the first zero-shot benchmarks for natural language understanding and generation in Indonesian and the local languages of Indonesia." — arxiv 2212.09648

URLs: https://github.com/IndoNLP/nusa-crowd · Paper: https://arxiv.org/abs/2212.09648 · Includes NER per Bahasa Indonesia + lokalita (Jawa, Sunda, Bali).

### 5.4 spaCy Bahasa Indonesia

> "SpaCy has not officially released the NER model pre-train for Indonesian. However, there are several community-driven projects and approaches to address this gap." — Purwadhika

> "To use the Indonesian language model in spaCy, you can download and install the id_core_web_sm model using the command: python -m spacy download id_core_web_sm" — Purwadhika

Community projects:

- https://github.com/rrayhka/indonesian-ner-spacy — Fine-tune with custom dataset
- https://github.com/danieldanuega/spacyndo — Dependency parser + NER for Bahasa, spaCy 2.1
- Tutorial: https://yudanta.github.io/posts/train-an-indonesian-ner-from-a-blank-spacy-model/

### 5.5 FastText Indonesian word vectors

> "FastText currently distributes word vectors trained on Wikipedia and Common Crawl for 157 languages. Some developers have packaged fastText Indonesian word vectors as a spaCy model after running python -m spacy init-model." — GitHub explosion/spaCy issue #3622

URL: https://fasttext.cc/docs/en/crawl-vectors.html (Indonesian = `id`).

### 5.6 Cahya / Wuriyanto pre-fine-tuned Indonesian NER models

- https://huggingface.co/cahya/bert-base-indonesian-NER — community model
- https://huggingface.co/wuriyanto/ner-bert-indonesian-v1 — bert-base-multilingual fine-tuned
- Legal NER: "Named entity recognition on Indonesian legal documents: a dataset and study using transformer-based models" — IJECE journal 2026

### 5.7 NusaBERT (LazarusNLP/NusaBERT)

> "NusaBERT: Teaching IndoBERT to be multilingual and multicultural!" — GitHub

GitHub: https://github.com/LazarusNLP/NusaBERT · Best 2026 multi-lingual successor IndoBERT.

**Recommendation Bali Zero Nexus**: pipeline = `cahya/bert-base-indonesian-NER` for production NER su news scraping (Person/Org/Location/Time/Quantity), augmented with custom spaCy fine-tune sui labels Indonesia-specific (Law, KBLI, KEP-PER, Money-IDR).

---

## 6. Investigative Journalism Patterns Indonesia

### 6.1 Tempo (tempo.co/investigasi + Majalah Tempo Investigasi)

> "Investigative reporting by Tempo Magazine is a rigorous and systematic reporting, disclosing wrongdoing based on evidence, facts and data. Investigation's editorials of Tempo Magazine form special teams. The investigation team gives emphasis to quality and capacity of journalists, which coordinated by an editor. Investigasi rubric is systematically a reporting unit integrated with Tempo's editorial management." — Humanities & Social Sciences Reviews

> "Published since 1971, Tempo Magazine contributes a particular attitude and reporting pattern. The banning of Tempo Magazine in 1994 unleashed a wave of protest from various class of society. Its re-publication in 1998 brought together a new rubric called Investigasi." — research paper

> "Program INVESTIGASI BERSAMA TEMPO is an activity of investigation coverage on various issues conducted by a number of journalists from various media together with Tempo. The activity involves journalists, bloggers, and freelance reporters. This program is an initiative of TEMPO INSTITUTE together with Free Press Unlimited (FPU) from the Netherlands." — tempoinstitute.com

URLs: https://www.tempo.co/tag/investigasi · https://majalah.tempo.co/kanal/investigasi · https://tempoinstitute.com/program-khusus/investigasi-bersama-tempo

Pattern: special team + editor → multi-month investigation → magazine cover story. Recent 2026 focus: tax officials wealth ("Treasure of Tax Officials" series, IJSOC 2024 case study).

### 6.2 Tirto.id

> "Tirto.id presents fact-based news and data analysis, written in an engaging way and always accompanied by infographics." — Library of Congress catalog

URL: https://tirto.id/ · Pattern: data + infographic dense per story. Indonesian Data Journalism Awards 2024 vincitori list curata da Tirto.

### 6.3 Project Multatuli

> "Project Multatuli was founded in June by a group of journalists including Evi Mariani, Ary Hermawan, Ahmad Arif and Fahri Salam. Evi and Ary previously worked at the Jakarta Post, Ahmad worked at Kompas, and Fahri worked at Tirto.id. All four have won international awards for their journalistic work." — projectmultatuli.org

> "Project Multatuli practices Public Service Journalism and is nonprofit journalism that presents in-depth reports based on research and data, in Indonesian and English. Their work emphasizes collaboration between media and various organizations that share the same values: democracy, humanity, social justice, environmental sustainability, and equal rights." — Project Multatuli

> "Project Multatuli won the Best Data Visualization category with their interactive report 'Menguliti Oligarki Batubara di Indonesia' (Exposing Coal Oligarchy in Indonesia) at the Indonesian Data Journalism Awards 2023." — TitaStory

URL: https://projectmultatuli.org/ · Pattern: nonprofit + collaborative + bilingual ID/EN.

### 6.4 IDN Times / Narasi (Najwa Shihab / Mata Najwa)

> "Najwa Shihab is an Indonesian journalist, presenter and actress. She started hosting her own talkshow Mata Najwa on Metro TV on 25 November 2009." — Wikipedia

> "Mata Najwa is an investigative interview show recognized for its scrutiny of corruption, political accountability, and social tolerance issues." — Tatler Asia

> "Jakarta-based news anchor Najwa Shihab left news channel Metro TV in 2017 to set up her own media company, Narasi. Eight years later, this trio of women have turned one talk show and Shihab's reputation for grilling the country's top politicians into a nationwide news platform that employs 170 people." — Monocle

> "One of her most famous and controversial moments was an 'empty chair' interview with Indonesia's minister of health that highlighted his inaction during the coronavirus pandemic and led to him being replaced." — Tatler Asia

URLs: https://www.narasi.tv/ · https://www.youtube.com/MataNajwaOfficial · Pattern: long-form on-camera interview dei pejabat (high-leverage public figure pressure).

### 6.5 Watchdoc (Dandhy Laksono)

> "WatchDoc is a media company incorporated in 2011 and founded by two journalists, Dandhy Laksono and Andhy Panca Kurniawan." — RMAward.asia

> "Watchdoc combines the tools of investigative journalism, documentary filmmaking, and digital technology. WatchdoC is known for documentaries that address issues like politics, culture, social matters, the environment, and human rights." — IDN Times

> "In 'Sexy Killers,' investigative journalists Dandhy Laksono and Suparta Arz describe the web of business connections between Indonesian coal and energy companies and the country's political elite. The film has been watched by around 26 million people on YouTube." — Mongabay 2019

> "WatchdoC was the 2021 Ramon Magsaysay Award winner, recognized for teaching communities how to do investigative journalism and documentary filmmaking." — Ramon Magsaysay

Films chiave: Sexy Killers (2019), Asimetris (palm oil), Jakarta Unfair, Samin vs Semen.
URL YouTube: https://www.youtube.com/@WatchdoCImage

### 6.6 IndonesiaLeaks (collaborative platform)

> "IndonesiaLeaks is designed as a collaborative platform between ten media houses to share tasks, responsibilities and resources, as well as risks. IndonesiaLeaks is a safe platform for anyone who wishes to report a crime with relevance to the public interest, commonly referred to as whistleblowers." — Indonesia at Melbourne

> "Tempo and JARING (a member of the Global Investigative Journalism Network) are joined by KBR, CNN Indonesia, The Jakarta Post, Bisnis Indonesia, Suara.com, Independen.id, Sindo and Liputan6, along with civil society organizations Indonesia Corruption Watch, LBH Pers, Change.org, Greenpeace and Auriga." — GIJN

> "The platform can only be accessed by journalists that are members of IndonesiaLeaks. These reporters have been trained in digital security and in the handling any reports that come in. Reporters first determine which leaks or information fulfil requirements and have the potential to be developed into a journalistic investigation. One of the key requirements is that the crime must have relevance to the public interest (and not simply interest the public)." — Free Press Unlimited

> "Investigative media including Tempo and Kompas face contradictory pressure in business models: investigation has social impact (such as reporting on e-KTP corruption or human rights violations in Papua), but the interactions on digital platforms are limited." — Frontiers in Communication 2025

E-KTP corruption case (Setya Novanto, then DPR speaker) was a landmark IndonesiaLeaks/Tempo/KPK collaborative — establishing the playbook: leak → multi-outlet verification → simultaneous publication.

### 6.7 Pattern synthesis for Bali Zero Nexus

- **Multi-outlet replication**: same story across 10+ outlets (IndonesiaLeaks model) protects from single-outlet pressure.
- **Data + infographic** (Tirto/Multatuli): visual oligarchy network maps converted public attention.
- **Long-form interview pressure** (Mata Najwa): face-to-face confrontation forces accountability.
- **Documentary distribution** (Watchdoc/YouTube): bypass TV gatekeepers, viral via YouTube.
- **Special team isolation** (Tempo): protect investigation integrity with dedicated editorial unit.

---

## 7. Network Analysis SOTA 2026

### 7.1 Gephi (open-source)

> "Gephi is an open-source software tool for visualizing and analyzing networks that allows you to customize your networks and maximize visual rendering to find insights effectively." — Brown LibGuides 2026

> "Gephi is one of the most popular open-source software for network analysis, praised for the network visualizations it can produce, and is good for beginners with point-and-click software that can handle basic and advanced network analytics." — McMaster LibGuides

> "Supported data formats include GEXF, GDF, GML, GraphML, Pajek NET, GraphViz DOT, CSV, UCINET DL, Tulip TPL, Netdraw VNA, and spreadsheet formats." — Brown LibGuides

> "ForceAtlas 2 is an improved version that can handle larger networks, for up to a million nodes." — McMaster LibGuides

> "For large networks above 100 nodes, use organic layout algorithms such as ForceAtlas2, which is a spring embedder that shrinks distance among highly connected nodes." — Nesta tutorial

URL: https://gephi.org/ · Use case: import LHKPN dump → ForceAtlas2 layout → identify clusters Pemkab Badung connections, BKPM revolving door (ex-officials → PMA director), tax consultancy networks.

### 7.2 Cytoscape (originally bio, adaptable)

> "Cytoscape is an open source software platform for visualizing complex networks and integrating these with any type of attribute data… Cytoscape is one of the most popular open-source software tools for the visual exploration of biomedical networks composed of protein, gene and other types of interactions." — cytoscape.org

> "It provides an interactive visualization interface along with other core features to import, navigate, filter, cluster, search, and export networks. The central organizing metaphor of Cytoscape is a network graph, with molecular species represented as nodes and intermolecular interactions represented as links, that is, edges, between nodes." — cytoscape.org

> "Since its introduction in 2003, Cytoscape has been a primary hub for biomedical network analysis and visualization, with over 300,000 downloads annually. A lot of Apps are available for various kinds of problem domains, including bioinformatics, social network analysis, and semantic web." — cytoscape.org

URL: https://cytoscape.org/ · Cytoscape Web (2026): browser-based. Less natural fit for OSINT than Gephi but stronger plug-in ecosystem.

### 7.3 NetworkX (Python)

> "NetworkX is a Python library for studying graphs and networks. More specifically, it is a Python package for the creation, manipulation, and study of the structure, dynamics, and functions of complex networks." — Wikipedia

> "NetworkX began development in 2002 by Aric A. Hagberg, Daniel A. Schult, and Pieter J. Swart. NetworkX is free software released under the BSD-new license." — Wikipedia

> "A community detection algorithm seeks to cluster network nodes according to their connectivity, and label propagation is a widely used method for this with an implementation in the Python NetworkX library." — DataCamp

> "The advantage of starting with NetworkX is its ease of use and extensive developer community. However, the main issue with Networkx is memory usage when dealing with large graphs, as Networkx stores graph data in Python objects which makes it incapable of handling tens of millions of objects without consuming the computer memory." — Toptal

URL: https://github.com/networkx/networkx · Use case Bali Zero: scripted analysis (centrality scores per pejabat in network, betweenness for "broker" detection).

### 7.4 Neo4j Bloom (graph database + viz)

> "Neo4j Bloom is a graph exploration application for visually interacting with graph data. It is a beautiful and expressive data visualization tool to quickly explore and freely interact with Neo4j's graph data platform with no coding required." — neo4j.com

> "Neo4j Bloom improves cross-team collaboration with codeless search-to-story design and simplifies complex queries using custom Cypher-based search phrases and near-natural language search functions." — neo4j.com

> "The tool can visualize people, places and things, products, services and accounts, and transactions, identities and events." — neo4j.com

> "Bloom includes a feature called the Slicer, which is basically a playback button for your entire graph—a simple slider linked to the properties stored on nodes, like dates or timestamps." — Shrawan Saproo Medium 2026

URL: https://neo4j.com/product/bloom/ · Comes with AuraDB Instance. Good fit if Nexus OSINT diventa multi-user platform interna Bali Zero.

### 7.5 Graphistry (GPU-accelerated)

> "Graphistry brings visual graph intelligence to big or complex data by automatically transforming data into interactive, visual maps built for the needs of analysts. Graphistry is a visual graph analytics platform designed to help analysts and developers turn large, connected datasets into interactive visual investigations, often via Python, JavaScript, or other integrations." — graphistry.com

> "Graphistry's breakthrough GPU client/cloud technology has raised the bar for interactive visualization by 100X, meaning you can use all the data you want while remaining fast, responsive, and interactive." — graphistry.com/gpu

> "Graphistry gives analysts full control over how data is visualized and provides views ideal for investigations like IR, Threat Hunting, Anti-Fraud, and AML. Their graph-based analysis reveals hidden connections and context across all data, and within seconds lets analysts see key relationships, event scope and progression, patterns, anomalies, and more." — graphistry.com/graph-analytics

> "Force-directed graphs quickly reveal clusters and outliers in data, which are often important for threat hunting." — graphistry.com

> "PyGraphistry is an open source Python library for data scientists and developers to leverage the power of graph visualization, analytics, and AI, using tools like Pandas, Spark, RAPIDS (GPU), and Apache Arrow." — github.com/graphistry/pygraphistry

URL: https://github.com/graphistry/pygraphistry + MCP server https://github.com/graphistry/graphistry-mcp (2026 — interesting for Nexus integration with Claude/LLMs).

**Recommendation per Bali Zero stack**: Gephi (interactive desk) + NetworkX (scripted batch) + Wikidata SPARQL (data source). Skip Graphistry/Neo4j Bloom (cost + Linux GPU req) unless Nexus diventa product.

---

## 8. Privacy / Legal Considerations OSINT (Indonesia + Adjacency)

### 8.1 UU PDP 27/2022 — Indonesian Personal Data Protection Law

> "On October 17, 2022, Indonesia's Personal Data Protection Act (Undang-Undang Nomor 27 Tahun 2022 tentang Pelindungan Data Pribadi) (PDP Act) came into force. The law governs the processing of personal data by organizations within and outside of Indonesia, and aims to guarantee the privacy rights of Indonesian citizens while encouraging the growth of Indonesia's digital economy and communications technology sector." — Library of Congress Global Legal Monitor

> "The law regulates principles; types of personal data; rights of personal data subjects; processing of personal data; obligations of personal data controllers and processors; transfer of personal data; administrative sanctions; institutional framework; international cooperation; public participation; dispute resolution and procedural law; prohibitions in personal data use; and criminal provisions related to personal data protection." — BDO Indonesia

> "The Act articulates core principles (protection, legal certainty, public interest, utility, prudence, balance, accountability and confidentiality), defines types of personal data (general and specific/sensitive categories), establishes rights for data subjects (access, correction, deletion, objection) and duties for data controllers and processors, and sets administrative and criminal sanctions for breaches." — Mondaq

URLs: Official text BPK: https://peraturan.bpk.go.id/Details/229798/uu-no-27-tahun-2022 · ABNR English translation PDF: https://www.abnrlaw.com/lib/files/IND-ENG-UU%2027-2022%20Pelindungan%20Data%20Pribadi%20(ABNR).pdf

### 8.2 GDPR adjacency (EU clients in Bali)

> "The extraterritorial scope of GDPR indicates it is applicable even outside of the borders of the European Union. GDPR applies to the processing of personal data in the context of the activities of an establishment of an organization (controller or processor) in the Union, regardless of whether the processing takes place in the EU or not. Additionally, the GDPR applies to controllers or processors that are not established in the EU if the processing of personal data concerns data subjects who are in the union and the processing activities relate to either the offering of goods or services, or the monitoring of their behaviour that takes place within the Union." — Data Privacy Manager

> "If your OSINT investigation involves personal data of an EU citizen, you'll probably have to take the GDPR into account." — OSINT Central

> "GDPR applies to any organization processing the personal data of EU citizens, regardless of where the company is located, meaning that a U.S.-based fraud prevention company using OSINT data to assess risks for EU customers must comply with GDPR regulations." — Trustfull

> "You need a legal basis for processing personal data, must apply GDPR principles in the processing of personal data, and under GDPR, must never handle more data than you need to answer your investigative question." — Blockint

Bali Zero implication: clienti EU in Bali → se Bali Zero processa loro personal data per offrire servizi (visa, KITAS, PT PMA), GDPR applica anche se Bali Zero è Indonesian entity. Need: privacy notice, lawful basis (typically contract performance), DPO / representative in EU? (debatable per <250 emp, ma high-risk processing trigger).

### 8.3 Bellingcat ethics code

> "Bellingcat is an independent collective of researchers, investigators and citizen journalists who specialise in open source and social media investigation… Bellingcat aims to promote the use of open source tools for investigation and encourages others to try these methods for themselves, but wants people to do so openly and responsibly, committing to lead the way by operating to the highest standards in this regard." — bellingcat.com/about/editorial-standards-practices

> "Researchers will be as clear as possible with potential sources and subjects as to who they are, who they work for and what their intentions are when undertaking research." — Bellingcat editorial standards

> "Researchers must exercise caution when dealing with information they find during investigations and not publish private details without fully justifiable public interest reasons, and care must also be taken to not unnecessarily reveal information or images of those who may be family members or related to the subjects of investigations." — Bellingcat

> "Researchers must consider the consequences for vulnerable groups who may be identifiable in videos or images before using such content in articles and investigations, and the impact on victims, survivors or relatives who have suffered loss due to accidents or disasters must also be carefully considered." — Bellingcat

> "Bellingcat has established an Ethics Committee—a body of staff who debate ethical dilemmas as they present themselves, offering advice on solutions—and are guided by their Editorial Standards & Practices, Principles for Data Collection, and other research on ethics and open source investigations." — bellingcat.com

URL: https://www.bellingcat.com/about/editorial-standards-practices/ · Pattern adopt Bali Zero: Nexus OSINT internal-use only (no publication of private details), Ethics Committee = Antonello + 1 senior team member sign-off prima di any external use.

### 8.4 Doxing line — Indonesia legal framework

> "Currently, existing regulations only implicitly regulate doxing on social media through Article 26 paragraph (1) of the ITE Law and Article 21 paragraph (1) of the Minister of Communication and Information Regulation Number 20 of 2016. However, doxing has been addressed following the enactment of Law Number 27 of 2022 on Personal Data Protection (UU PDP) in October 2022, where doxing is included in Article 16 UU PDP and can be charged under Article 67 paragraph 2 UU PDP." — LK2 FHUI

> "Doxing can be charged under UU ITE Article 32 jo. Article 48 (threatening 8 years imprisonment and Rp 2 billion fine), UU PDP Article 67 (threatening 5 years imprisonment and Rp 5 billion fine), as well as the Criminal Code for crimes of intimidation and defamation that accompany doxing." — Pakar UNAIR

> "Perpetrators of doxing typically use OSINT (Open Source Intelligence) techniques, gathering information from publicly available sources such as social media profiles, domain WHOIS data, public data brokers, online forums, and data from previous data breaches." — Media Justitia

> "Whistleblowing involves revealing information about legal violations or corruption for public interest, typically with certain legal protections, whereas doxing is done to harm individuals personally, not for public interest, with the key difference lying in intent and the type of information disseminated." — Multilingual Journal of Universal Studies

**OSINT lecito vs illegale Indonesia (sintesi)**:
| Activity | Legal status | Reasoning |
|---|---|---|
| Reading e-LHKPN public data | LEGAL | KPK explicitly publishes |
| Querying Daftar Caleg KPU | LEGAL | KPU portal public |
| Compiling internal dossier from public sources | LEGAL (if internal) | UU PDP Art. 15 personal/household exemption questionable for business |
| Publishing pejabat home address | ILLEGAL (doxing) | UU PDP Art. 67(2) — 5y / Rp 5B |
| Publishing pejabat NIK / KTP number | ILLEGAL | sensitive data UU PDP Art. 4 |
| Cross-ref data breach DB to enrich profile | ILLEGAL | UU PDP Art. 65 — unlawful obtainment |
| Using OSINT for KYC / due diligence (internal) | LEGAL | Lawful interest basis, but document |

### 8.5 Bali Zero Nexus OSINT — Recommended Compliance Stance

1. **Internal-use only** dossier policy (no publication).
2. **Source restriction**: solo public/official Indonesian sources (KPK, KPU, DPR, BPK, MA, Setkab) + sanctioned international (OpenSanctions free tier).
3. **No data breach DB use** (HaveIBeenPwned passive check email only OK; no leaked password use).
4. **No address/NIK** in dossier.
5. **Logging**: Hunchly chain-of-custody for evidence audit trail.
6. **Retention**: 24 mesi max post case close, then auto-purge.
7. **Privacy notice** to clients: disclose OSINT due diligence in engagement letter.
8. **No automated mass scraping** of public sites (TOS conflict + UU ITE Art. 30 unauthorized access risk).
9. **EU clients adjacency**: GDPR Art. 6(1)(b) contract basis + Art. 6(1)(f) legitimate interest balancing test documented.
10. **Bellingcat-style ethics review**: Antonello + senior team approval before any output beyond internal note.

URLs key:

- UU PDP: https://peraturan.bpk.go.id/Details/229798/uu-no-27-tahun-2022
- UU ITE compilation: https://jdih.komdigi.go.id/
- GDPR Art. 3 extraterritorial: https://gdpr-info.eu/art-3-gdpr/
- Bellingcat standards: https://www.bellingcat.com/about/editorial-standards-practices/

---

## Summary table — Recommended Nexus OSINT stack for Bali Zero

| Layer                | Tool                                                               | Cost                    | Indonesia fit                                   |
| -------------------- | ------------------------------------------------------------------ | ----------------------- | ----------------------------------------------- |
| Entity ontology      | Self-hosted Wikibase + Wikidata seed                               | FREE                    | Excellent (Indonesian entities exist)           |
| Sanctions screening  | OpenSanctions free tier + API                                      | FREE non-commercial     | Direct ID datasets (DTTOT, regional 2018)       |
| People-graph data    | Wikidata SPARQL + LittleSis API + LHKPN scrape                     | FREE                    | Wikidata/LHKPN strong; LittleSis weak Indonesia |
| Investigative search | OCCRP Aleph (request access) + Aleph Pro (Oct 2025+)               | FREE journalists / paid | OCCRP ID research desk available                |
| Username pivots      | Maigret (3000+ sites)                                              | FREE                    | Bahasa-indifferent                              |
| Email pivots         | Holehe + Mosint                                                    | FREE                    | Bahasa-indifferent                              |
| NER pipeline         | cahya/bert-base-indonesian-NER + custom spaCy                      | FREE                    | High (IndoBERT family)                          |
| Visualization        | Gephi (desk) + NetworkX (script)                                   | FREE                    | Generic                                         |
| Evidence custody     | Hunchly                                                            | $130/yr                 | OK                                              |
| News surveillance    | Tempo/Tirto/Multatuli/Watchdoc RSS + scraper                       | FREE                    | Critical for Bali political/business news       |
| Compliance           | UU PDP-aware policy + GDPR-EU client carve-out + Bellingcat ethics | Internal                | Mandatory                                       |

**Skip for now**: Maltego (good but cost + Windows-leaning), Sayari ($$$$), World-Check ($$$$ + false-pos lawsuits), Palantir (compliance/cost + ethics red flags vedi memory `palantir-anthropic-hybris`), Neo4j Bloom (until product stage).

---

**Fonti totali raccolte: 90+ URL** (≈11 per sezione, supera min 5/sezione).
**Date snapshot**: 2026-05-08 (post Kabinet Merah Putih activation, post Aleph Pro launch).
