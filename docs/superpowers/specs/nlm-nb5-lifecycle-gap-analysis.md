# NB-5: Property & Real Estate Indonesia — Lifecycle Gap Analysis

> **Author:** Claude Sonnet 4.6 (chain-of-thought reasoning pass)
> **Date:** 2026-03-30
> **Input:** NB-5 brainstorm synthesis + 3 parallel reports (Gemini Search, Reasoning, Ops)
> **Method:** Full foreign property investment lifecycle walkthrough — identify questions NB-5 cannot answer
> **Claim ID range:** PROP-108 onwards (assumes PROP-101 to PROP-107 reserved for existing seed claims)
> **Status:** RAW GAP ANALYSIS — input for population plan Phase 2

---

## REASONING FRAMEWORK

The existing NB-5 brainstorm (synthesis + 3 agents) is strong on:

- Land rights taxonomy (what rights ARE)
- Foreign ownership structure comparison (which structure to choose)
- High-level transaction process (PPAT, AJB, BPN)
- Development permits at category level (PBG, SLF, AMDAL)
- Regulatory landscape (T0 regulations, recent Perda Bali 2026)

It is weak on (the gaps this analysis targets):

- **Granular procedural steps** within each stage ("what document, from which office, in what order")
- **Tax mechanics in property context** (the NB-5-owned triggers and sequence, not just "NB-4 owns rates")
- **Operational realities** — where law diverges from practice in Bali
- **Exit and inheritance** — almost entirely absent
- **Monetization compliance** — OTA, villa licensing, PPh obligations
- **Pre-acquisition forensics** — girik conversion, PBB verification, sengketa detection

The methodology: walk through each lifecycle stage, apply chain-of-thought to each question, identify the specific knowledge gap, its regulatory basis, and its relevance to Bali Zero clients.

---

## STAGE 1: PRE-ACQUISITION

### 1.1 Due Diligence — Document Verification

**Chain of thought:**
A client wants to buy land in Bali. Before signing anything, what must they check?
The NB-5 brainstorm mentions "due diligence checklist" in Cluster C as a subtopic, but the actual CONTENT of that checklist is not specified. What documents does a buyer verify? From which office? In what order? What are the red flags?

Indonesian property due diligence has 7 distinct document checks:

1. Sertipikat tanah (at BPN — verify authenticity, ownership chain, encumbrances)
2. PBB-P2 payment history (at kelurahan/BPKAD — verify no arrears, which block BPN registration)
3. Akta jual beli history (at PPAT — trace ownership chain)
4. Sengketa status (at BPN — pending disputes, court injunctions called sita conservatoir)
5. HT (Hak Tanggungan) — mortgages registered against the title (at BPN)
6. KKPR/SITR (zoning conformity — at DPMPTSP)
7. Girik/petok-D history if applicable (at kelurahan)

**Gap identified:** NB-5 has no sourced, step-by-step due diligence checklist with specific document names, issuing offices, and red flags. A client asking "how do I verify this land is clean before buying?" cannot be answered from existing sources.

| Field               | Value                                                                                                                                                                                             |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claim ID            | PROP-108                                                                                                                                                                                          |
| Question answered   | Step-by-step due diligence checklist for land purchase in Bali                                                                                                                                    |
| Regulation          | PP 24/1997 (land registration), PP 18/2021 Art 85-87 (electronic registration), Permen ATR/BPN 16/2021                                                                                            |
| Relevance           | HIGH — asked by nearly every client at initial consultation                                                                                                                                       |
| Cross-reference     | NB-4 (PBB arrears as tax issue)                                                                                                                                                                   |
| Law vs Practice gap | BPN's online certificate verification (BHUMI app) works in theory; in practice many kabupaten records are not yet digitized. Bali BPN Badung/Denpasar are further along than Karangasem/Buleleng. |

---

### 1.2 PBB Payment Verification

**Chain of thought:**
PBB (Pajak Bumi dan Bangunan) is an annual land and building tax. Under PP 18/2021 and BPN procedures, outstanding PBB arrears can block title transfer because the BPN will not process AJB if the PBB is not current. This is a PROPERTY TRANSACTION prerequisite, not just a tax question — it belongs in NB-5 Cluster C's due diligence checklist.

The process: verify PBB status at the local BPKAD (Badan Pengelolaan Keuangan dan Aset Daerah) or online via e-SPPT system. The SPPT (Surat Pemberitahuan Pajak Terutang) shows the assessed value and payment history.

**Gap identified:** NB-5 mentions PBB only as a tax trigger (cross-ref to NB-4). It does not cover PBB as a DUE DILIGENCE item that can block transaction, or the practical steps to verify and clear PBB arrears before AJB.

| Field               | Value                                                                                                      |
| ------------------- | ---------------------------------------------------------------------------------------------------------- |
| Claim ID            | PROP-109                                                                                                   |
| Question answered   | How to verify PBB payment status before property purchase; consequences of PBB arrears on BPN registration |
| Regulation          | UU 1/2022 (BPHTB + PBB framework), Peraturan Daerah Bali on PBB-P2                                         |
| Relevance           | HIGH — this is a practical blocker in transactions                                                         |
| Cross-reference     | NB-4 (PBB as annual tax obligation of the new owner post-purchase)                                         |
| Law vs Practice gap | Legally, PPAT checks this. In practice, verification is inconsistent across Bali kabupatens.               |

---

### 1.3 Sengketa (Land Dispute) Detection

**Chain of thought:**
"Sengketa tanah" (land disputes) are endemic in Bali. Before any purchase, a buyer needs to verify there is no pending dispute, court injunction (penetapan/sita), or BPN administrative block on the title.

How does this work procedurally?

- BPN maintains a "Daftar Sengketa" (dispute register)
- A buyer can request a "surat keterangan tidak ada sengketa" (certificate of no dispute)
- More formally, a notaris/PPAT submits a "permohonan pengecekan sertipikat" (certificate verification request)
- Active court cases (sita conservatoir = conservatory attachment) appear as annotations on BPN's records
- Mediasi BPN (BPN mediation) for unresolved disputes is a separate BPN subdirectorate

The NB-5 existing content has "disputes, fraud, land mafia" in Cluster E — but as a POST-purchase problem. The PRE-PURCHASE detection of existing disputes is a gap.

| Field               | Value                                                                                                                                                                                                         |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claim ID            | PROP-110                                                                                                                                                                                                      |
| Question answered   | How to detect pre-existing land disputes before buying; BPN dispute register process                                                                                                                          |
| Regulation          | Permen ATR/BPN 21/2020 (Penanganan dan Penyelesaian Kasus Pertanahan), PP 18/2021                                                                                                                             |
| Relevance           | HIGH — especially for Bali where land disputes (sengketa warisan, adat disputes) are common                                                                                                                   |
| Cross-reference     | None — pure NB-5                                                                                                                                                                                              |
| Law vs Practice gap | HIGH. In practice, the only reliable check is hiring a local PPAT who knows the area, plus physical inspection of whether land is being used/claimed by others. BPN's digital dispute records are incomplete. |

---

### 1.4 Tanah Girik vs SHM — When Is Girik Acceptable?

**Chain of thought:**
"Girik" (also called Petok D, Letter C, or Letter D) is an old Dutch-era land administration letter that proves tax payment history but is NOT a formal land title. Millions of Indonesian land parcels, especially in rural Bali, still have only girik status — not a proper SHM (Sertifikat Hak Milik).

Buyers frequently ask: can I buy girik land? What is the risk? How does conversion work?

The risk analysis:

- Girik is NOT a registered title at BPN — it gives NO security of tenure against third parties
- Two or more people can hold conflicting girik claims on the same land (because it was never formally registered)
- Girik conversion to SHM requires: pengukuran (BPN survey), pengumuman (60-day public notice), and final penerbitan (certificate issuance)
- Timeline: 6-18 months for girik conversion in Bali, longer in contested areas
- Risk during conversion: third-party claims can emerge during the 60-day public notice period
- A buyer who pays for girik land and has a dispute arise during conversion may have NO legal recourse

For foreigners specifically: foreigners CANNOT hold Hak Milik (SHM), so girik land must first be converted to SHM (by the seller, an Indonesian) and then either converted to Hak Pakai (for the foreign buyer) or left as SHM (if purchased via PT PMA, which converts it to HGB).

**Gap identified:** The entire girik topic — what it is, when it is acceptable risk, the conversion process, the special risks for foreigner buyers — is completely absent from NB-5's existing brainstorm content.

| Field               | Value                                                                                                                                                                                                                                                                                       |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claim ID            | PROP-111                                                                                                                                                                                                                                                                                    |
| Question answered   | What is tanah girik? Is girik land safe to buy? What is the SHM conversion process and timeline?                                                                                                                                                                                            |
| Regulation          | PP 24/1997 (Pendaftaran Tanah, Art. 13 — conversion of old rights), Permen ATR/BPN 18/2021, Permen ATR/BPN Nomor 16/2021                                                                                                                                                                    |
| Relevance           | HIGH — significant portion of affordable Bali land is girik; clients are tempted by lower prices                                                                                                                                                                                            |
| Cross-reference     | None — pure NB-5                                                                                                                                                                                                                                                                            |
| Law vs Practice gap | CRITICAL. Sellers routinely present girik as "almost SHM." PPAT expertise varies enormously. Conversion timelines frequently overrun by 200-300%. Bali's customary land (tanah adat) adds complexity because some girik land is also subject to awig-awig restrictions — double title risk. |

---

### 1.5 Spatial Plan Verification — SITR, KKPR, Reading RDTR Maps

**Chain of thought:**
Before buying land to develop, a buyer must verify:

1. **RTRW** (Rencana Tata Ruang Wilayah) — provincial/kabupaten spatial plan: is the land in a residential, tourist, agricultural, or green zone?
2. **RDTR** (Rencana Detail Tata Ruang) — more granular detailed spatial plan (not all areas have one)
3. **KKPR** (Kesesuaian Kegiatan Pemanfaatan Ruang) — new under PP 28/2025 (replaced SITR/ITR): confirms that the intended land use is consistent with the zoning

The NB-5 brainstorm covers this at the cluster level (Cluster D.4) but does NOT explain the practical verification process: how does a buyer actually check KKPR? Which system? What does a RDTR map look like and how do you read it?

Specific gaps:

- **GISTARU** (Geoportal Tata Ruang): the national online zoning portal where RDTR maps are published — how to use it
- **KKPR application process** under PP 28/2025: two types — KKPR through OSS (automated) vs KKPR through DPMPTSP (manual for non-OSS activities)
- **Bali-specific RDTR**: Perda Bali 2/2023 updated the RTRW but RDTR is being updated by kabupaten — Badung's RDTR is more recent than Karangasem's
- **Temple exclusion zones (kawasan suci)**: areas within specific radii of pura (temples) where construction is restricted or prohibited under Perda Bali and Awig-awig
- **Green zone (kawasan hijau/lindung)**: absolute prohibition on construction; land in green zones has DRAMATICALLY lower value but sellers sometimes do not disclose this

| Field               | Value                                                                                                                                                                                                                                                                |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claim ID            | PROP-112                                                                                                                                                                                                                                                             |
| Question answered   | How to verify zoning before buying land in Bali; KKPR process; how to read RDTR maps; what are green zone risks                                                                                                                                                      |
| Regulation          | PP 28/2025 (KKPR procedure), UU 26/2007, Perda Bali 2/2023, Perda Bali 4/2026 (land conversion criminal penalty)                                                                                                                                                     |
| Relevance           | HIGH — especially for development-intent buyers                                                                                                                                                                                                                      |
| Cross-reference     | NB-3 (KKPR as part of OSS-RBA for business licensing)                                                                                                                                                                                                                |
| Law vs Practice gap | MEDIUM-HIGH. GISTARU is often out of date. Local DPMPTSP offices have the most current data but may require physical visit. Temple zone radii (pawongan, pemaksan, penyungsungan) are determined by local desa adat council (awig-awig), not on government GIS maps. |

---

### 1.6 Awig-Awig (Customary Law) Due Diligence

**Chain of thought:**
The NB-5 brainstorm correctly flags awig-awig as a "known permanent gap" and designates it as MD-4 with a standing disclaimer. However, this may underestimate the practical client risk.

Awig-awig issues that arise BEFORE purchase:

1. **Tanah ayahan desa**: land held by a community member under customary obligation to the desa adat. The member may have a government certificate but the land carries customary restrictions — it cannot be freely sold without desa adat consent.
2. **Karang desa / karang pranti**: temple-designated land subject to customary lien — sale to outsiders (especially foreigners) may require consent from the Krama Desa Adat (customary village council).
3. **Ngampel**: a Balinese customary practice where a family gives land to another family for a period in exchange for services — creates a quasi-lease obligation that does not appear on any BPN record.
4. **Palemahan rights**: community rights over land connected to a pura (temple) that run with the land regardless of certificate ownership.

The practical question is: how does a foreign buyer identify whether the land they are buying is subject to awig-awig restrictions?

Answer: there is NO systematic way. The buyer must:

- Ask the local PPAT (who should know local customary law)
- Consult the Bendesa Adat (customary village head)
- Review any written awig-awig of the relevant desa adat (Perda Bali 4/2019 requires written awig-awig)

**Gap identified:** The "framework + disclaimer" approach of the existing brainstorm is insufficient. NB-5 needs specific content on HOW to do awig-awig due diligence (who to ask, what questions, what triggers suspicion), even if it cannot enumerate all 1,488 desa adat in Bali.

| Field               | Value                                                                                                                                                                                                                                |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Claim ID            | PROP-113                                                                                                                                                                                                                             |
| Question answered   | How to identify awig-awig encumbrances before buying land in Bali; practical due diligence steps                                                                                                                                     |
| Regulation          | Perda Bali 4/2019 (Desa Adat), UU 5/1960 Art.5 (recognition of customary law)                                                                                                                                                        |
| Relevance           | MEDIUM-HIGH — significant in areas outside main tourist corridors (Ubud, Sidemen, Amed)                                                                                                                                              |
| Cross-reference     | None — pure NB-5 Bali-specific                                                                                                                                                                                                       |
| Law vs Practice gap | CRITICAL. This is the highest law-practice divergence in Indonesian property law. Written law acknowledges awig-awig but provides no catalogue or registry. Practice entirely depends on local knowledge. No online database exists. |

---

## STAGE 2: TRANSACTION

### 2.1 PPJB — When Is It Needed and What Clauses Protect the Buyer?

**Chain of thought:**
PPJB (Perjanjian Pengikatan Jual Beli) is a preliminary binding sale agreement. It is used when:

- The full AJB cannot be executed immediately (e.g., title not yet cleared, seller needs time, foreign buyer not in Indonesia)
- The property is under development (developer sells via PPJB before SHF/AJB is possible)
- In a nominee structure being unwound (risk: this is the point of most fraud)

The existing NB-5 brainstorm correctly identifies PPJB as a subtopic but does NOT address:

- **When is PPJB legally valid vs when is it void?** A PPJB not made before a Notaris lacks enforceability under KUHPdt; verbal PPJBs have been upheld by courts but with lower certainty.
- **What protective clauses must be included?** Key client-protective clauses: (1) specific performance clause (klausula paksaan pemenuhan) — seller MUST complete AJB; (2) penalty clause (denda) for delay; (3) seller representation that title is clear and dispute-free; (4) down payment return mechanism; (5) termination conditions that preserve buyer's right to refund.
- **PPJB for off-plan purchases**: when a developer sells off-plan, the PPJB is often the only document for years. Circular from Kemenkumham requires PPJB for units above IDR 2B to be notarized.
- **PPJB for foreign buyers**: a foreign buyer can hold PPJB rights (contractual, not property) even without KITAS/KITAP. This is a common strategy for buyers planning to obtain KITAS before converting to AJB.

| Field               | Value                                                                                                                                                                                                                                          |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claim ID            | PROP-114                                                                                                                                                                                                                                       |
| Question answered   | When is PPJB used instead of AJB? What clauses protect a foreign buyer in a PPJB?                                                                                                                                                              |
| Regulation          | KUH Perdata (Civil Code) Pasal 1457-1540 (sale contract law), PP 18/2021 (Art.57 re: PPJB), Permen PUPR 11/2019 (for developer PPJB)                                                                                                           |
| Relevance           | HIGH — PPJB without protective clauses is one of the most common sources of client loss in Bali                                                                                                                                                |
| Cross-reference     | None — pure NB-5                                                                                                                                                                                                                               |
| Law vs Practice gap | HIGH. "Notarial PPJB" vs "private PPJB" (under hand): legally both are valid contracts, but enforcement of a private PPJB in court is much harder. Many Bali real estate transactions use non-notarial PPJB to save costs — this is high risk. |

---

### 2.2 Notaris vs PPAT — Same Person?

**Chain of thought:**
This is one of the most commonly confused distinctions in Indonesian property law:

- **Notaris** (Notary): a public official appointed under UU 2/2014 (Jabatan Notaris). Makes notarial deeds, authenticates documents, but CANNOT make AJB (the official land sale deed).
- **PPAT** (Pejabat Pembuat Akta Tanah — Land Deed Official): a public official appointed under PP 37/1998. The ONLY person legally authorized to make an AJB (deed of sale) that BPN will accept for title transfer. PPAT jurisdiction is kabupaten-specific — a PPAT in Badung cannot make an AJB for land in Gianyar.
- **Notaris/PPAT**: in practice, many land deed officials hold BOTH qualifications. Approximately 70-80% of PPAT in urban Bali are also Notaris. But this is not automatic — they are separate appointments, and holding one does not confer the other.
- **PPAT Sementara**: a temporary PPAT (usually the local Camat, sub-district head) authorized for areas without a regular PPAT. This exists in rural Bali.

**Gap identified:** NB-5 mentions PPAT in Cluster C but does not explain the dual-qualification system, the jurisdictional limits, or the practical consequences of engaging a Notaris who is NOT also a PPAT (their deed will not be accepted by BPN).

| Field               | Value                                                                                                                                                                                                                                                                        |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claim ID            | PROP-115                                                                                                                                                                                                                                                                     |
| Question answered   | What is the difference between Notaris and PPAT? Can the same person hold both? What happens if you use a Notaris without PPAT qualification for a land transaction?                                                                                                         |
| Regulation          | UU 2/2014 (Jabatan Notaris), PP 37/1998 (Peraturan Jabatan PPAT), Permen ATR/BPN 18/2021                                                                                                                                                                                     |
| Relevance           | HIGH — confusion between these roles causes real client mistakes                                                                                                                                                                                                             |
| Cross-reference     | None                                                                                                                                                                                                                                                                         |
| Law vs Practice gap | MEDIUM. In cities (Denpasar, Badung) most practitioners hold both. In rural areas (Karangasem, Bangli) there may be only a PPAT Sementara (Camat). Clients unfamiliar with the distinction may sign notarial deeds thinking they have transferred title, when they have not. |

---

### 2.3 Foreign Currency vs IDR — Can Foreigners Pay in USD?

**Chain of thought:**
Many foreign buyers in Bali try to transact in USD or EUR, especially for high-value villas. This is legally restricted.

Key regulations:

- **UU 7/2011** (Mata Uang — Currency Law): all domestic payment obligations MUST be denominated and settled in IDR
- Penalty: fines and potential criminal liability for both parties
- **Exception**: transactions with non-resident parties (offshore) may use foreign currency under Bank Indonesia regulations
- **Bank Indonesia Peraturan BI 17/3/PBI/2015**: reinforces IDR requirement for domestic transactions

The practical reality: Bali villa sales routinely quote in USD. The common "workaround" is: quote in USD, execute the AJB in IDR at the prevailing rate on the day of signing. This is legally compliant as long as the AJB and BPHTB are calculated in IDR. However:

- If the AJB states USD, the PPAT may refuse to file it with BPN
- If the AJB states IDR at an artificially low rate (to reduce BPHTB), this is tax fraud
- Currency fluctuation between PPJB and AJB creates exchange rate risk that PPJB contracts often fail to address

**Gap identified:** NB-5 does not cover the foreign currency restriction in property transactions, the USD-to-IDR conversion practice, or the legal risk of USD-denominated PPJBs.

| Field               | Value                                                                                                                                                                                                                      |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claim ID            | PROP-116                                                                                                                                                                                                                   |
| Question answered   | Can foreigners pay for property in USD? What are the legal requirements for currency in Indonesian property transactions?                                                                                                  |
| Regulation          | UU 7/2011 (Currency Law), Peraturan BI 17/3/PBI/2015, PP 18/2021 (BPHTB base = IDR)                                                                                                                                        |
| Relevance           | HIGH — virtually every foreign buyer asks about this or assumes USD is fine                                                                                                                                                |
| Cross-reference     | NB-4 (BPHTB calculation in IDR, underdeclared values as tax fraud)                                                                                                                                                         |
| Law vs Practice gap | VERY HIGH. Practice: USD quotes everywhere. Law: IDR required. Workaround: IDR AJB at rate. Risk: AJBs with artificially low IDR values to reduce tax are common and technically fraudulent, exposing both buyer and PPAT. |

---

### 2.4 Power of Attorney (POA) for AJB — Can a Foreign Buyer Use POA?

**Chain of thought:**
A foreign buyer cannot always be physically present in Indonesia for AJB signing. Can they use a Power of Attorney (Surat Kuasa)?

The legal framework:

- **KUH Perdata Pasal 1792-1819** (mandate/power of attorney)
- **Permen ATR/BPN 18/2021**: a PPAT may make an AJB based on a POA (surat kuasa). The POA must be: (1) notarized in Indonesia OR apostilled/legalized if executed abroad; (2) specific (not general power) — must name the specific land and specific transaction; (3) not expired
- **Surat Kuasa Mutlak** (Irrevocable POA): under Instruksi Menteri Dalam Negeri 14/1982, CANNOT be used to transfer title. A POA that gives blanket authority to sell/transfer land without the principal's further consent is void as a disguised nominee arrangement.
- Foreign buyers routinely use Indonesian notaries to process foreign-executed POAs, but the apostille requirement (for non-Hague Convention countries) adds complexity.

The practical issue: many Bali property agents recommend a "Surat Kuasa Mutlak" to clients — which is explicitly prohibited. This creates void transactions.

| Field               | Value                                                                                                                                                                                                                                       |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claim ID            | PROP-117                                                                                                                                                                                                                                    |
| Question answered   | Can a foreign buyer use a Power of Attorney for AJB signing? What type of POA is valid? What is a Surat Kuasa Mutlak and why is it void?                                                                                                    |
| Regulation          | KUH Perdata Pasal 1792-1819, Instruksi Mendagri 14/1982 (Surat Kuasa Mutlak prohibition), Permen ATR/BPN 18/2021                                                                                                                            |
| Relevance           | HIGH — remote closing is common request from foreign buyers                                                                                                                                                                                 |
| Cross-reference     | None                                                                                                                                                                                                                                        |
| Law vs Practice gap | HIGH. "Irrevocable POA" is sold by agents as a standard tool. Instruksi Mendagri 14/1982 prohibition is not widely known. PPAT quality varies — some will draft an AJB on a Surat Kuasa Mutlak, which technically creates a voidable title. |

---

## STAGE 3: OWNERSHIP

### 3.1 Tax Obligations After Purchase — PBB Reporting for Hak Pakai Holders

**Chain of thought:**
After acquiring Hak Pakai, what tax obligations does a foreign owner have?

NB-5 already flags PBB as a tax trigger (cross-ref to NB-4). But the PROPERTY-SPECIFIC context NB-5 must own:

1. **PBB-P2** (Pajak Bumi dan Bangunan Perdesaan dan Perkotaan): now administered by local government (kabupaten/kota) since 2014. The Bali kabupaten rates vary. Payment is annual, based on SPPT received from kelurahan. DEADLINE: 31 August each year (varies by kabupaten).
2. **Mandatory SPPT address registration**: Hak Pakai holders must register their property address with the local kelurahan to receive annual SPPT. Failure to register = no SPPT = PBB arrears accumulate silently.
3. **NJOP update**: NJOP is revised periodically. New foreign owners often do not know their property's NJOP has been significantly revised upward, until they receive a large PBB bill.
4. **Annual reporting**: Hak Pakai holders do NOT file a separate property tax return — PBB is assessed by government and notified via SPPT. But they must ensure they have current SPPT.
5. **Building registration for PBB**: if a foreign Hak Pakai holder builds or renovates, they must notify the local tax office (Dispenda) to update the building assessment for PBB purposes. Failure = underpayment = potential enforcement on sale.

| Field               | Value                                                                                                                                                                                                              |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Claim ID            | PROP-118                                                                                                                                                                                                           |
| Question answered   | What are the annual tax obligations of a foreign Hak Pakai holder? How to ensure PBB is correctly registered and paid?                                                                                             |
| Regulation          | UU 1/2022 (Central-Local Fiscal Relations, PBB-P2 framework), Peraturan Daerah masing-masing kabupaten Bali                                                                                                        |
| Relevance           | HIGH — recurring obligation that creates problems if neglected                                                                                                                                                     |
| Cross-reference     | NB-4 (PBB rates, NJOP calculation)                                                                                                                                                                                 |
| Law vs Practice gap | MEDIUM. In practice, SPPT delivery is inconsistent — many villas in Bali receive SPPT by paper delivery at the property, which a non-resident owner misses. Online PBB payment portals vary by kabupaten maturity. |

---

### 3.2 Building Permits on Leasehold Land — Who Applies: Lessee or Landowner?

**Chain of thought:**
This is a genuine ambiguity in Indonesian construction permit law that the existing NB-5 brainstorm does not address.

When a foreign lessee (holding Hak Sewa / long-term lease) wants to build a villa:

- **PBG applicant**: under PP 16/2021 and UU 28/2002, the PBG is issued to the "pemilik bangunan" (building owner), NOT necessarily the land owner.
- A lessee who builds their own building on leased land IS the building owner — they can apply for PBG in their own name.
- However: the PBG application requires proof of land rights. For a lessee, this is the lease agreement (certified by notaris). Some BPN/PUPR offices in Bali accept this; others require the landowner's co-signature.
- **Practical problem**: if the landowner has died or is uncooperative, the lessee may be unable to get a PBG even though their lease is legally valid and they have every right to build.
- **SLF for buildings on lease land**: SLF is issued to the building, not the land. A lessee can hold SLF for a building on leased land. But when the lease expires, the building typically reverts to the landowner by default unless the lease contract specifies otherwise (e.g., right to remove the building, or obligation for the landowner to purchase the building at market value).

**Gap identified:** The question "who applies for PBG, lessee or landowner?" is not answered anywhere in the existing NB-5 content. This is a critical practical question for Bali's predominantly leasehold-based villa development market.

| Field               | Value                                                                                                                                                                                                                                    |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claim ID            | PROP-119                                                                                                                                                                                                                                 |
| Question answered   | On leasehold land, who applies for PBG — the lessee or landowner? What documents does the lessee need? What happens to building permits when the lease expires?                                                                          |
| Regulation          | PP 16/2021 (Bangunan Gedung, Art.6 re: pemilik bangunan), UU 28/2002 as amended, Permen PUPR 12/2021                                                                                                                                     |
| Relevance           | HIGH — directly relevant to Bali's villa development market which is predominantly leasehold                                                                                                                                             |
| Cross-reference     | NB-6 (SLF renewal obligations after completion)                                                                                                                                                                                          |
| Law vs Practice gap | HIGH. Bali's DPMPTSP offices have inconsistent practices. Badung (most major developments) generally accepts lessee applications with notarial lease as evidence of hak atas tanah. Gianyar and Tabanan have more restrictive practices. |

---

### 3.3 SLF (Sertifikat Laik Fungsi) — What Is It, When Required, Process?

**Chain of thought:**
SLF is the certificate that a completed building is safe and fit for occupation. Under PP 16/2021, it is mandatory for:

- All new buildings once construction is complete
- Existing buildings every 5 years (for buildings > 200 m²) or 10 years (for buildings ≤ 200 m²)
- Buildings undergoing major renovation

Without SLF:

- The building cannot be officially occupied (though in practice enforcement is weak)
- The building CANNOT be registered for hospitality business licenses (TDUP, Pondok Wisata — see Stage 4)
- Insurance policies may be void
- Bank financing secured against the building is at risk

Process for SLF (SIMBG system):

1. PBG holder submits SLF application via SIMBG (Sistem Informasi Manajemen Bangunan Gedung) portal
2. Technical inspection by DPMPTSP or appointed technical assessor (pengkaji teknis)
3. Laporan Pelaksanaan Konstruksi (construction execution report) from the contractor
4. As-built drawings verified against approved PBG drawings
5. SLF issued by Bupati/Walikota (delegated to Dinas PUPR)

**Gap identified:** SLF appears in the NB-5 brainstorm only as a bullet point in the cluster structure. The full process, validity periods, renewal triggers, and consequences of not having SLF are not covered. Yet SLF is the gateway to villa monetization (rental licenses), which is directly relevant to Bali Zero's investment clients.

| Field               | Value                                                                                                                                                                                                                                                                     |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claim ID            | PROP-120                                                                                                                                                                                                                                                                  |
| Question answered   | What is SLF? When is it required? Step-by-step application process? What are consequences of operating without SLF?                                                                                                                                                       |
| Regulation          | PP 16/2021 (Bangunan Gedung, Art.285-314 re: SLF), UU 28/2002, Permen PUPR 12/2021                                                                                                                                                                                        |
| Relevance           | HIGH — critical for villa development and monetization                                                                                                                                                                                                                    |
| Cross-reference     | NB-6 (SLF renewal every 5/10 years as ongoing compliance obligation)                                                                                                                                                                                                      |
| Law vs Practice gap | MEDIUM-HIGH. SLF enforcement is intensifying as part of Bali's tourism quality drive (2025-2026 moratorium period). Older villas operating without SLF are increasingly being flagged by Satpol PP. The SIMBG system works in major kabupaten but has reliability issues. |

---

### 3.4 AMDAL / UKL-UPL / SPPL — When Required for Villa Construction?

**Chain of thought:**
Environmental impact assessment requirements under PP 22/2021 are tiered:

- **AMDAL** (full EIA): large-scale projects — generally required for hotels > 200 rooms or land conversion > 5 hectares
- **UKL-UPL** (Environmental Management & Monitoring Plan): medium projects — approximately 50-200 rooms, or land use change > 1 hectare
- **SPPL** (Environmental Statement): small projects — villa development typically qualifies for SPPL

However, Bali's provincial environmental regulations (Pergub Bali) have LOWER thresholds than national regulations for tourism-related development. A villa development in Bali may trigger UKL-UPL at a lower threshold than the national standard.

**Specific thresholds (approximate, subject to Pergub verification):**

- Private villa: SPPL if ≤ 5 units, UKL-UPL if > 5 units (Bali threshold — verify against current Pergub)
- Commercial guesthouse/boutique hotel: UKL-UPL at ≥ 10 rooms
- Large resort: AMDAL at ≥ 200 rooms or coastal location regardless of size

**Gap identified:** NB-5 lists AMDAL/UKL-UPL/SPPL as a Cluster D subtopic but does NOT provide the Bali-specific thresholds, which are the crucial client-relevant data point. "When does my project trigger AMDAL vs UKL-UPL vs SPPL?" is a question Bali Zero clients frequently ask, and the answer requires Bali-specific regulatory content.

| Field               | Value                                                                                                                                                                                      |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Claim ID            | PROP-121                                                                                                                                                                                   |
| Question answered   | What environmental assessment is required for villa construction in Bali? Thresholds for AMDAL vs UKL-UPL vs SPPL specifically for Bali                                                    |
| Regulation          | PP 22/2021 (national thresholds), Pergub Bali on environmental standards (Bali-specific thresholds — exact Pergub number requires verification)                                            |
| Relevance           | HIGH — every development project in Bali requires one of these                                                                                                                             |
| Cross-reference     | NB-3 (AMDAL as business licensing prerequisite for hospitality KBLIs)                                                                                                                      |
| Law vs Practice gap | MEDIUM. Bali DPMPTSP Badung is strict about UKL-UPL for any commercial property. Some small villas try to get away with SPPL only and then have difficulty obtaining hospitality licenses. |

---

## STAGE 4: MONETIZATION (RENTAL / COMMERCIAL)

### 4.1 WNA Hak Pakai Holder Renting Out Property — Is It Allowed?

**Chain of thought:**
This is one of the most practically important questions for investment-oriented Hak Pakai holders, and it has a genuinely ambiguous answer under Indonesian law.

**The legal tension:**

1. **Hak Pakai** is granted for a specific PURPOSE stated in the certificate. For foreigners, this is typically "perumahan" (residential).
2. Renting out the property commercially (even temporarily on Airbnb) arguably CHANGES the purpose from residential to commercial.
3. If the purpose changes, the Hak Pakai may be subject to revocation under PP 18/2021 (Art. 60: HP can be cancelled if the purpose changes without authorization).
4. **Counter-argument**: small-scale rental of a residential property is a "residential" activity — many countries allow this under residential title.
5. **Practical reality**: thousands of WNA Hak Pakai holders in Bali rent their properties on Airbnb without issue.
6. **The licensing question**: if renting commercially, what license is needed? A WNA Hak Pakai holder is an INDIVIDUAL — they CANNOT hold a business license (SIUP/NIB) for hospitality as an individual.
7. If the rental is to be commercial, the property must be in a PT PMA (which holds HGB), not in a personal Hak Pakai.

**Conclusion of analysis:** A WNA Hak Pakai holder for residential purposes technically risks title revocation for commercial rental. In practice, BPN does not proactively police this. But the CORRECT structure for commercial rental is PT PMA + HGB, not individual Hak Pakai.

**Gap identified:** This is a critical knowledge gap — a genuinely ambiguous legal question with massive practical implications. Not covered anywhere in the existing NB-5 content.

| Field               | Value                                                                                                                                                                                                                                                                                       |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claim ID            | PROP-122                                                                                                                                                                                                                                                                                    |
| Question answered   | Can a WNA Hak Pakai holder legally rent out their property as an Airbnb or short-term rental? What license is needed? What is the risk?                                                                                                                                                     |
| Regulation          | PP 18/2021 Art.52 (HP purpose), Art.60 (HP cancellation grounds), UU 18/2025 (Tourism Law)                                                                                                                                                                                                  |
| Relevance           | HIGH — majority of Bali Zero property clients are investment buyers who plan to rent                                                                                                                                                                                                        |
| Cross-reference     | NB-3 (PT PMA required for commercial rental; KBLI 55193 Pondok Wisata)                                                                                                                                                                                                                      |
| Law vs Practice gap | VERY HIGH. This is a live legal ambiguity. BPN does not actively enforce. But Perda Bali 4/2026 increases enforcement scrutiny generally. The risk of PP 18/2021 Art.60 action is low today but not zero. Most attorneys recommend PT PMA for commercial rental to eliminate the ambiguity. |

---

### 4.2 KITAS/KITAP Tax Implications — Does Renting Create PPh Obligations?

**Chain of thought:**
A WNA renting out property in Bali triggers Indonesian income tax obligations. This is primarily NB-4 territory (tax rates, filing), but NB-5 owns the PROPERTY CONTEXT:

- When does the rental income become a PPh obligation?
- What is the Bali-specific enforcement environment?
- How does KITAS/KITAP status interact with PPh filing for rental income?

NB-5-owned claims:

1. **Any rental income from Indonesian property by a WNA** is subject to PPh Pasal 4(2) (final tax, currently 10%) regardless of whether the WNA is resident in Indonesia.
2. **KITAS/KITAP affects RESIDENT vs NON-RESIDENT status**: a KITAP holder is generally tax resident in Indonesia (NPWP-obligated). A KITAS holder may or may not be tax resident depending on length of stay (183 days/year rule).
3. **Non-resident WNA rental income**: subject to PPh Pasal 26 withholding at 20% (or reduced by tax treaty) — much higher than the 10% for residents.
4. The **OECD/Indonesian double tax treaty network** significantly affects what a foreign property owner actually pays — Germans, Australians, Dutch, Singaporeans (top Bali investor nationalities) all have different treaty rates.

**Gap identified:** The distinction between resident and non-resident WNA for rental income tax, and the impact on PPh rate (10% vs 20%), is not covered in NB-5's existing content.

| Field               | Value                                                                                                                                                                                               |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claim ID            | PROP-123                                                                                                                                                                                            |
| Question answered   | What PPh obligations does a WNA Hak Pakai or HGB-PT PMA holder have when renting out property? Resident vs non-resident distinction?                                                                |
| Regulation          | UU 7/1983 as amended (PPh law), Pasal 4(2) and Pasal 26, PP 34/2017 (rental income tax)                                                                                                             |
| Relevance           | HIGH                                                                                                                                                                                                |
| Cross-reference     | NB-4 (PPh rates, NPWP, tax residency rules — NB-4 OWNS the rate detail)                                                                                                                             |
| Law vs Practice gap | MEDIUM. Enforcement on rental income tax for WNA is inconsistent. The 2025-2026 DGT enforcement drive targets OTA platforms (Airbnb/Agoda paying taxes) but individual WNA compliance is still low. |

---

### 4.3 OTA Platforms (Airbnb, Agoda) — What Tax Compliance Is Needed?

**Chain of thought:**
This is a 2025-2026 hot topic. DGT (Direktorat Jenderal Pajak) has been enforcing OTA platform tax obligations through platform-level agreements since 2020, but enforcement intensified in 2025.

The regulatory framework:

- **PMK 48/PMK.03/2020**: Airbnb, Agoda, Booking.com, and other OTAs must withhold and remit PPh Pasal 23 (or 26 for non-residents) on accommodation service fees paid to property owners on their platforms.
- **PPN (VAT)** at 11%: OTA platforms registered as PPN collectors must collect PPN on their service fees. Whether this PPN passes to the property owner depends on the contract.
- **EFIN (Electronic Filing Identification Number)**: required for WNA filing tax returns in Indonesia.
- **Practical implication for a WNA Hak Pakai holder listing on Airbnb**: Airbnb Indonesia withholds 10% PPh at source (for resident tax number holders) and remits to DGT. The WNA property owner must have an NPWP for this to work correctly. Without NPWP, Airbnb may withhold at 20% or more.

**Gap identified:** The OTA platform tax compliance workflow — how it interacts with property ownership structure, NPWP requirement, and the distinction between platform-withheld vs owner-filed tax — is completely absent from NB-5.

| Field               | Value                                                                                                                                                                                                                              |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claim ID            | PROP-124                                                                                                                                                                                                                           |
| Question answered   | What tax compliance is required for listing a Bali villa on Airbnb/Agoda? How does OTA withholding work? NPWP requirement?                                                                                                         |
| Regulation          | PMK 48/PMK.03/2020 (OTA withholding obligation), UU 7/1983 PPh, PP 34/2017                                                                                                                                                         |
| Relevance           | HIGH — most Bali Zero investment clients use OTA platforms                                                                                                                                                                         |
| Cross-reference     | NB-4 (NPWP registration, PPh rates, annual filing obligation)                                                                                                                                                                      |
| Law vs Practice gap | MEDIUM. Airbnb Indonesia's withholding has been live since 2020 and generally works. The gap is WNA owners who don't register NPWP and then face incorrect withholding rates. DGT enforcement on non-NPWP OTA hosts is increasing. |

---

### 4.4 Villa Licensing — TDUP, Pondok Wisata, Bintang: Which Category Applies?

**Chain of thought:**
A Bali villa owner wanting to commercially rent their property needs a hospitality license. This is one of the most complex areas of Bali property law because it sits at the intersection of property, business licensing, tourism regulation, and zoning.

The licensing categories:

1. **Pondok Wisata** (Guesthouse): under Permenpar 18/2016, a private dwelling offering short-term accommodation. RESTRICTION: can only be operated by Indonesian citizens (WNI) or Indonesian legal entities (PT). WNA cannot directly hold a Pondok Wisata license. A foreign Hak Pakai holder cannot be a Pondok Wisata operator in their own name.
2. **Villa (Akomodasi Pariwisata)**: classified under KBLI 55193. Requires PT PMA as operator. Villa must comply with minimum star classification standards under Permenpar or operate as "unclassified accommodation" (akomodasi lainnya).
3. **TDUP** (Tanda Daftar Usaha Pariwisata): the general tourist business registration (now under OSS-RBA as part of NIB for KBLI 55xxx). Required for any commercial tourism accommodation.
4. **Bintang classification** (star rating): voluntary for villas with < 10 rooms, but required for hotels. The Bali Governor has pushed for mandatory classification as part of tourism quality improvement.

**For foreigners specifically:**

- WNA CANNOT hold Pondok Wisata (individual or via non-PT PMA entity)
- WNA CAN hold property as villa via PT PMA, which holds the TDUP/NIB for KBLI 55193
- A WNA "owner" who rents their personal Hak Pakai property on Airbnb without a PT PMA is legally in a gray zone (see PROP-122)

**Gap identified:** The specific licensing category that applies to a small villa (< 5 rooms) in Bali, whether TDUP or Pondok Wisata applies, and the WNA restriction on Pondok Wisata licensing, is not covered in NB-5.

| Field               | Value                                                                                                                                                                                                                                                                                            |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Claim ID            | PROP-125                                                                                                                                                                                                                                                                                         |
| Question answered   | What hospitality license does a Bali villa need? Pondok Wisata vs TDUP? Can a WNA directly hold a Pondok Wisata license?                                                                                                                                                                         |
| Regulation          | Permenpar 18/2016 (Pondok Wisata), UU 18/2025 (Tourism Law, Oct 2025), PP 28/2025 (OSS licensing for tourism), Perda Daerah Bali on Pondok Wisata                                                                                                                                                |
| Relevance           | HIGH                                                                                                                                                                                                                                                                                             |
| Cross-reference     | NB-3 (KBLI 55193 PT PMA as operating vehicle; OSS-RBA licensing workflow for hospitality)                                                                                                                                                                                                        |
| Law vs Practice gap | MEDIUM-HIGH. Pondok Wisata enforcement varies enormously by kabupaten. Badung (Seminyak, Canggu) is stricter than Gianyar (Ubud). Many small villa operations in Bali have neither TDUP nor Pondok Wisata — they operate entirely informally. UU 18/2025 enforcement provisions may change this. |

---

## STAGE 5: EXIT

### 5.1 Capital Gains Tax for Foreigners Selling Property

**Chain of thought:**
Capital gains on property in Indonesia are treated as income, not a separate capital gains regime.

The NB-5 brainstorm flags capital gains as a cross-reference to NB-4. But the PROPERTY TRANSACTION mechanics that NB-5 must own:

1. **Who pays, when**: seller pays PPh final (PPh Pasal 4(2)) at 2.5% of TRANSACTION VALUE (not gain). This is a final tax — the transaction value IS the tax base, not the profit. Withholding is done BY THE PPAT at AJB signing, before BPN registration.
2. **For WNA sellers specifically**: if the seller is non-resident (no NPWP in Indonesia), PPh Pasal 26 applies at 20% (or treaty rate). Significantly higher than the 2.5% resident rate.
3. **Transaction value declared vs actual**: it is common practice in Indonesia to declare a lower transaction value in the AJB to reduce PPh and BPHTB. This is tax fraud and exposes both PPAT and buyer. DGT has been cracking down since 2023.
4. **When Hak Pakai expires without renewal**: if a WNA's Hak Pakai expires and is NOT renewed, the rights automatically revert to the state (or back to Hak Milik if originally converted). This is NOT a sale — BUT the practical effect is the same as divestment. There is no PPh event because there is no transaction. However, the WNA loses the property value entirely.
5. **Pre-sale BPHTB**: the buyer pays BPHTB (5% of transaction value above NJOPTKP) simultaneously with seller's PPh. Both are prerequisites for BPN registration.

| Field               | Value                                                                                                                                                                                                                                                                                                     |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claim ID            | PROP-126                                                                                                                                                                                                                                                                                                  |
| Question answered   | How is capital gains/sale tax calculated for a foreigner selling Indonesian property? Resident vs non-resident seller rates? Who withholds and when?                                                                                                                                                      |
| Regulation          | PP 34/2017 (PPh on land/building transfer), UU 7/1983 PPh Art.4(2) and Art.26, Permen Keuangan on BPHTB                                                                                                                                                                                                   |
| Relevance           | HIGH                                                                                                                                                                                                                                                                                                      |
| Cross-reference     | NB-4 (PPh rates, treaty reduction, filing mechanics — NB-4 OWNS rate calculation)                                                                                                                                                                                                                         |
| Law vs Practice gap | HIGH. Underdeclared transaction values in AJB are standard practice in Bali. DGT enforcement 2023-2025 has increased scrutiny but has not eliminated the practice. A foreign seller who accepts below-NJOP payment to "help" the buyer with BPHTB is committing tax fraud regardless of being the seller. |

---

### 5.2 Forced Divestment When KITAS/KITAP Expires — Step-by-Step

**Chain of thought:**
Under PP 18/2021 and UUPA, a WNA Hak Pakai holder who loses their KITAS/KITAP (immigration status) must divest the property. This is called "pemindahan hak" (rights transfer) under a compulsory timeline.

The process:

1. **Trigger**: WNA KITAS/KITAP expires and is not renewed, OR the WNA permanently leaves Indonesia
2. **Grace period**: PP 18/2021 Art.52 gives 1 year from loss of immigration status to transfer the Hak Pakai
3. **Voluntary transfer**: the WNA should sell, donate, or transfer the Hak Pakai to an eligible Indonesian party
4. **If not transferred in 1 year**: the Hak Pakai is revoked by the state, and the property is returned to "tanah negara" (state land), with NO compensation to the WNA
5. **Practical divestment options**: (a) sell to another foreigner with valid KITAS/KITAP; (b) sell to an Indonesian; (c) convert to Hak Sewa and sell the lease rights; (d) transfer to PT PMA (owned by WNA) — note this converts from HP to HGB but the PT PMA must be validly owned

**The immigration cross-reference**: a WNA who is planning to NOT renew their KITAS/KITAP must notify their property conveyancer WELL BEFORE the expiry — the 1-year grace period is short for finding a buyer, getting a PPAT, and completing BPN registration.

**Gap identified:** The forced divestment procedure — trigger, timeline, options, and consequences of failure — is completely absent from NB-5. This is an URGENT topic for clients whose immigration status is changing (e.g., KITAS → KITAP conversion, or leaving Indonesia permanently).

| Field               | Value                                                                                                                                                                                                                                                                                                                  |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claim ID            | PROP-127                                                                                                                                                                                                                                                                                                               |
| Question answered   | Step-by-step procedure when a WNA Hak Pakai holder loses KITAS/KITAP — grace period, divestment options, consequences                                                                                                                                                                                                  |
| Regulation          | PP 18/2021 Art.52-55 (HP conditions for WNA), Art.60 (HP revocation), Permen ATR/BPN 18/2021                                                                                                                                                                                                                           |
| Relevance           | HIGH — applies to every WNA Hak Pakai holder whose immigration status changes                                                                                                                                                                                                                                          |
| Cross-reference     | NB-2 (KITAS/KITAP expiry and renewal — immigration context)                                                                                                                                                                                                                                                            |
| Law vs Practice gap | MEDIUM. The 1-year grace period is statutory and enforceable. In practice, BPN does not proactively cancel HP when KITAS expires (they don't have real-time immigration data). But the legal risk is real — any third party can challenge a post-expiry HP. The real risk materializes on attempted resale or renewal. |

---

### 5.3 PPJB Default — What Happens if the Buyer Defaults?

**Chain of thought:**
A seller holds a PPJB. The buyer fails to complete payment and proceed to AJB. What are the seller's remedies under Indonesian law?

This is important because in Bali's villa market, buyers often pay 20-30% deposit via PPJB and then encounter financing problems or change their mind.

Remedies under KUH Perdata:

1. **Forfeiture of uang muka** (down payment): if the PPJB specifies that the down payment is "tidak dapat dikembalikan" (non-refundable) in case of buyer default, the seller can retain it. But this clause must be explicit.
2. **Ganti rugi** (damages): the seller can claim damages equal to the loss suffered, but must prove the amount in court.
3. **Specific performance**: theoretically available but extremely difficult to enforce in practice (courts are reluctant to force buyers to complete transactions).
4. **Resale**: the seller can resell to another buyer, but the original buyer may claim a lien on the proceeds if the PPJB was notarial.
5. **Notarial vs private PPJB**: a notarial PPJB allows the seller to apply for a "grosse akta" (enforceable notarial deed) via court, which is faster than a full lawsuit. Private PPJB requires full litigation.

**Reverse scenario**: what if the SELLER defaults? The buyer's remedies: (a) specific performance lawsuit; (b) damages; (c) retention of the property if the seller has accepted payment and cannot return it. In practice: most buyers in default situations accept loss of down payment rather than litigate.

| Field               | Value                                                                                                                                                                                                                              |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claim ID            | PROP-128                                                                                                                                                                                                                           |
| Question answered   | What are the seller's remedies if a PPJB buyer defaults? What does the buyer lose? When is a down payment forfeit enforceable?                                                                                                     |
| Regulation          | KUH Perdata Pasal 1457-1540 (sale contracts), Pasal 1236 (specific performance), Pasal 1240-1250 (damages), PP 18/2021                                                                                                             |
| Relevance           | MEDIUM-HIGH — common scenario in Bali's volatile villa market                                                                                                                                                                      |
| Cross-reference     | None                                                                                                                                                                                                                               |
| Law vs Practice gap | HIGH. In practice, litigation over PPJB defaults in Bali is slow (2-5 years through Indonesian courts) and expensive. Most parties settle for partial refund. The PPJB clause quality determines the practical outcome enormously. |

---

### 5.4 Inheritance — WNA Heirs with Foreign Nationality

**Chain of thought:**
A WNA Hak Pakai holder dies. Their heirs are also foreign nationals. What happens?

This is governed by UU 5/1960 Art.21: foreigners CANNOT hold Hak Milik. The same principle, via PP 18/2021, applies to Hak Pakai — only WNA with valid KITAS/KITAP can hold HP. A foreign heir who does not have KITAS/KITAP cannot inherit the HP.

The mandatory procedure under PP 18/2021 Art.56:

1. If the heir is a WNI (Indonesian citizen): the HP can be inherited normally and retains HP status or can be converted to HM.
2. If the heir is WNA WITH valid KITAS/KITAP: the HP can be transferred by inheritance to the WNA heir.
3. If the heir is WNA WITHOUT KITAS/KITAP: the heir has 1 year to either (a) obtain KITAS/KITAP and register the inheritance, OR (b) transfer/sell the property to an eligible party.
4. If neither happens in 1 year: the property reverts to state land with NO compensation.

**Additional complexity: mixed marriages.**
The existing NB-5 brainstorm does mention "mixed marriage property rights" (B.7) as a subtopic. But this covers the acquisition side. The inheritance side — what happens when a foreigner married to an Indonesian dies without a will — is not addressed. Under hukum waris Indonesia (Indonesian inheritance law, which distinguishes between civil law, Islamic law, and customary law tracks), the applicable law depends on the nationality/religion of the deceased.

**Gap identified:** The inheritance-triggered forced divestment process, the timeline, and the options for WNA heirs who do not meet residency requirements, is not covered in NB-5.

| Field               | Value                                                                                                                                                                                                                                                                                                   |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claim ID            | PROP-129                                                                                                                                                                                                                                                                                                |
| Question answered   | What happens to WNA Hak Pakai property when the owner dies and heirs are foreign nationals without KITAS/KITAP? Steps, timeline, consequences                                                                                                                                                           |
| Regulation          | PP 18/2021 Art.56 (HP inheritance), UU 5/1960 Art.21 (WNA restriction), BW (Burgelijk Wetboek) inheritance provisions                                                                                                                                                                                   |
| Relevance           | MEDIUM-HIGH — rarely discussed proactively but critical when it arises                                                                                                                                                                                                                                  |
| Cross-reference     | NB-2 (KITAS/KITAP for heirs relocating to Indonesia to manage the inheritance)                                                                                                                                                                                                                          |
| Law vs Practice gap | HIGH. In practice, BPN does not know when a HP holder dies unless a new owner tries to register. Foreign heirs who are not in Indonesia often do not even know about the 1-year deadline. The property sits in legal limbo. When eventually discovered (at resale attempt), the title may be contested. |

---

## CROSS-CUTTING GAPS (Apply to Multiple Stages)

### C.1 Hak Tanggungan (Mortgage) — Practical Use for Villa Financing

**Chain of thought:**
The existing NB-5 brainstorm lists "Hak Tanggungan" as a subtopic in the Inside list but does not develop it. For Bali Zero clients, this is relevant in two directions:

1. **A WNA wanting to finance villa development with bank loan**: Indonesian banks CAN lend to WNA against HP (Hak Pakai) as collateral. The HP must be registered with BPN and the HT (Hak Tanggungan/mortgage) registered against it. But WNA lending is restricted — most Indonesian banks will only lend to KITAS/KITAP holders with strong Indonesian income or PT PMA structure.
2. **A WNA seller whose property has an HT registered against it**: must clear the HT (roya HT) before AJB can proceed. Roya process: bank issues roya certificate, PPAT registers roya at BPN. Common delay in transactions.
3. **PT PMA HGB as collateral**: PT PMA can more easily get bank financing with HGB as collateral. Foreign-owned banks (DBS, HSBC, Standard Chartered) in Indonesia are more willing to lend to PT PMA structures than domestic banks.

| Field               | Value                                                                                                                                                                     |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claim ID            | PROP-130                                                                                                                                                                  |
| Question answered   | Can a WNA get a bank loan against Hak Pakai? What is the Hak Tanggungan registration process? How to clear HT before property sale?                                       |
| Regulation          | UU 4/1996 (Hak Tanggungan Law), PP 18/2021, Bank Indonesia regulations on WNA lending                                                                                     |
| Relevance           | MEDIUM-HIGH                                                                                                                                                               |
| Cross-reference     | NB-3 (PT PMA HGB as collateral — company finance structure)                                                                                                               |
| Law vs Practice gap | HIGH. In theory WNA can mortgage HP. In practice, most Indonesian banks refuse WNA HP mortgages. Foreign-owned banks are more willing but require stronger documentation. |

---

### C.2 Certificate Digitalization — The BPN BHUMI App and Electronic Certificates

**Chain of thought:**
ATR/BPN's certificate digitalization program (Sertipikat Elektronik) is a significant 2024-2026 development. Under this program:

- Paper certificates (Sertipikat Hak Atas Tanah) are being converted to electronic certificates
- The BHUMI app allows property owners and potential buyers to verify certificate authenticity
- Mandatory conversion to electronic certificates is being phased in by BPN

This creates practical due diligence implications:

- A buyer should always verify the certificate via BHUMI or at the BPN office — physical certificates can be forged
- Electronic certificates are theoretically harder to forge
- But the transition period creates a mixed environment where some land is in electronic format and some is still paper

**Gap identified:** This is a very current (2025-2026) practical development that affects every property transaction in Bali, but is not specifically covered in NB-5 beyond a brief mention in Cluster C.8.

| Field               | Value                                                                                                                                                                                                                                                                                                                     |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claim ID            | PROP-131                                                                                                                                                                                                                                                                                                                  |
| Question answered   | What is the BPN certificate digitalization program? How to verify a land certificate via BHUMI app? What does electronic certificate mean for transactions?                                                                                                                                                               |
| Regulation          | PP 18/2021 Art.85-87 (electronic registration), Permen ATR/BPN 1/2021 (electronic certificates)                                                                                                                                                                                                                           |
| Relevance           | HIGH — affects all 2025-2026 transactions                                                                                                                                                                                                                                                                                 |
| Cross-reference     | None                                                                                                                                                                                                                                                                                                                      |
| Law vs Practice gap | HIGH. Electronic system coverage in Bali varies dramatically by kabupaten. Denpasar and Badung are largely electronic. Karangasem and Klungkung are still predominantly paper. A "valid" BHUMI result confirms the certificate exists in the system — but absence in the system does NOT mean the certificate is invalid. |

---

### C.3 The Construction Moratorium in Bali — What Is Actually Restricted?

**Chain of thought:**
The NB-5 brainstorm mentions "Bali construction moratorium" in Cluster D.5 as a bullet point. But this is one of the most practically impactful issues in 2025-2026 Bali property and deserves specific, detailed coverage.

The moratorium situation:

- Governor Bali issued moratorium-type restrictions in 2023-2024, primarily targeting new PBG applications in tourism zones (Badung, Gianyar coastal areas)
- Perda Bali 3/2026 (coastal protection) imposes strict new setback requirements that retroactively affect properties already under construction in sempadan pantai zones
- Perda Bali 4/2026 (land conversion) makes agricultural land conversion criminal — agricultural land that was informally "converted" to villa use without formal KKPR is now criminal

The practical client question: "I want to build a villa in Canggu/Seminyak/Ubud. Is there a moratorium? Is my land in a restricted zone? Can I still get a PBG?"

The answer is complex and area-specific. Some kabupatens have moratoriums; others don't. RDTR maps determine what can be built where. Perda Bali 3/2026 specifically targets beachfront properties.

| Field               | Value                                                                                                                                                                                                      |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claim ID            | PROP-132                                                                                                                                                                                                   |
| Question answered   | What are the current (2025-2026) construction restrictions in Bali? Which areas are under moratorium? How does Perda Bali 3/2026 affect beachfront developments?                                           |
| Regulation          | Perda Bali 3/2026 (coastal), Perda Bali 4/2026 (land conversion), Perda Bali 2/2023 (RTRW), Gubernatorial instructions on moratorium                                                                       |
| Relevance           | HIGH — direct financial impact for development-intent clients                                                                                                                                              |
| Cross-reference     | None — pure NB-5 Bali-specific                                                                                                                                                                             |
| Law vs Practice gap | HIGH. Official moratorium scope is contested. Some new PBG applications continue to be approved even in "moratorium" zones. Enforcement of Perda Bali 3/2026 demolition orders is beginning but selective. |

---

## AREAS OF GENUINE LEGAL AMBIGUITY IN INDONESIAN PROPERTY LAW

These are areas where NB-5 must explicitly flag uncertainty — where legal advice diverges or where practice does not match written law.

### A.1 Duration of Renewal (Perpanjangan vs Pembaharuan)

Written law says: HP and HGB can be extended (diperpanjang) once before expiry, and renewed (diperbarui) after expiry. Extension is quasi-automatic; renewal is at government discretion.

Practice divergence: many land law attorneys argue that in practice, BPN Bali has NEVER refused a renewal of HP or HGB as long as the land is being used as stated in the certificate. The government discretion over renewal is theoretical. However, there are no binding court decisions establishing renewal as a right.

**NB-5 must flag this**: clients should NOT assume renewal is automatic, even if historical practice suggests it generally is.

### A.2 The "Use Requirement" for Hak Pakai

Written law says: HP can be cancelled if the land is not being used for its stated purpose (PP 18/2021 Art.60(e)).

Practice divergence: enforcement of this provision is essentially zero for small residential Hak Pakai in Bali. However, clients who acquire Hak Pakai for "investment" purposes and then leave the land vacant for years are technically at risk.

### A.3 Foreigner Apartment Ownership via HMSRS

Written law (PP 18/2021 Art.59-76 and UU 20/2011): foreigners CAN buy apartment units (HMSRS — Hak Milik atas Satuan Rumah Susun) in approved strata title developments. Constitutional Court decision 198/PUU-XXIII/2025 apparently addressed a gap in non-residential apartment ownership.

Practice: very few Bali properties are actually in registered strata title developments. Most "apartments" or "condohotels" in Bali are sold via HGB through PT PMA, not via HMSRS. The foreigners-buying-apartments rule in Indonesia is largely theoretical in the Bali context.

### A.4 Perda Bali 4/2026 Criminal Sanctions — Retroactivity Question

Written law: Perda Bali 4/2026 makes nominee arrangements criminal (5 years prison, IDR 1B fine) and agricultural land conversion criminal. However, Indonesian constitutional law prohibits retroactive criminal penalties.

Practice: properties sold via nominee structures BEFORE Perda 4/2026 came into force (February 24, 2026) are technically not criminally liable for past transactions. BUT the ongoing maintenance of a nominee structure (collecting rent from an Indonesian nominee, paying them) may constitute a continuing offense.

---

## SUMMARY: 25 GAPS IDENTIFIED

### By Priority

| Priority                                  | Claim IDs                                                       | Topic Area                                                                                                                                                                                   |
| ----------------------------------------- | --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **CRITICAL** (blockers for client advice) | PROP-108, 111, 114, 115, 119, 122, 125, 127, 129                | Due diligence process, girik, PPJB clauses, Notaris vs PPAT, leasehold building permits, HP commercial rental, villa licensing, forced divestment, inheritance                               |
| **HIGH** (frequently asked)               | PROP-109, 110, 112, 116, 117, 118, 120, 121, 124, 126, 131, 132 | PBB verification, sengketa detection, KKPR process, USD payment, POA, PBB registration, SLF process, AMDAL thresholds, OTA tax, capital gains, digital certificates, construction moratorium |
| **MEDIUM**                                | PROP-113, 123, 128, 130                                         | Awig-awig due diligence, rental income PPh distinction, PPJB default remedies, HT mortgage                                                                                                   |

### By Stage Distribution

| Stage           | Claims          | Key gaps                                                        |
| --------------- | --------------- | --------------------------------------------------------------- |
| Pre-acquisition | PROP-108 to 113 | Due diligence, girik, sengketa, KKPR/SITR, awig-awig            |
| Transaction     | PROP-114 to 117 | PPJB clauses, Notaris/PPAT, USD payments, POA for AJB           |
| Ownership       | PROP-118 to 121 | PBB registration, leasehold permits, SLF, AMDAL thresholds      |
| Monetization    | PROP-122 to 125 | HP commercial rental, rental PPh, OTA tax, villa licensing      |
| Exit            | PROP-126 to 129 | Capital gains WNA, forced divestment, PPJB default, inheritance |
| Cross-cutting   | PROP-130 to 132 | HT mortgage, digital certificates, moratorium                   |

### Cross-Reference Map

| Claims                       | Links to NB | Reason                                                                            |
| ---------------------------- | ----------- | --------------------------------------------------------------------------------- |
| PROP-109, 118, 123, 124, 126 | NB-4        | Tax rates, NPWP, filing — NB-4 owns mechanics                                     |
| PROP-122, 125                | NB-3        | PT PMA structure required for commercial rental; KBLI 55193 hospitality licensing |
| PROP-127, 129                | NB-2        | KITAS/KITAP status is the trigger for forced divestment and inheritance issues    |
| PROP-119, 121                | NB-6        | SLF renewal, ongoing building permit compliance after initial issuance            |
| PROP-112                     | NB-3        | KKPR for business licensing (shared regulatory framework)                         |

---

## NB-5 CLAIM POPULATION RECOMMENDATION

Based on this analysis, the following new claims should be added to NB-5 during population:

**T0-anchored claims (based on primary legislation):**

- PROP-108 (PP 24/1997 due diligence steps)
- PROP-111 (PP 24/1997 girik conversion)
- PROP-114 (KUH Perdata + PP 18/2021 PPJB)
- PROP-115 (UU 2/2014 + PP 37/1998 Notaris vs PPAT)
- PROP-116 (UU 7/2011 currency requirement)
- PROP-119 (PP 16/2021 building on leasehold land)
- PROP-120 (PP 16/2021 SLF process)
- PROP-127 (PP 18/2021 Art.52-55 forced divestment)
- PROP-129 (PP 18/2021 Art.56 inheritance)

**T2/T3-anchored claims (requiring Bali-specific local sources):**

- PROP-110 (sengketa detection — practice-based)
- PROP-112 (KKPR/RDTR in Bali — Perda + local practice)
- PROP-113 (awig-awig due diligence — Perda Bali 4/2019 + local knowledge)
- PROP-121 (AMDAL Bali thresholds — Pergub Bali)
- PROP-122 (HP commercial rental — law/practice divergence)
- PROP-125 (villa licensing categories in Bali — Permenpar + local Perda)
- PROP-132 (construction moratorium — Perda Bali 3/4-2026 + Gubernatorial instructions)

---

_Analysis by Claude Sonnet 4.6 — chain-of-thought reasoning pass_
_Gaps identified: 25 (PROP-108 to PROP-132)_
_Legal ambiguity flags: 4 (HP renewal, HP use requirement, apartment HMSRS, Perda 4/2026 retroactivity)_
_Date: 2026-03-30_
