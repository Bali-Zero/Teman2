#!/usr/bin/env python3
"""Apply Session 07 gold content updates to kbli-gold-content.ts and page.tsx"""
import re

# ============================================================
# Read files
# ============================================================
with open('lib/kbli-gold-content.ts', 'r') as f:
    content = f.read()

with open('app/kbli/[code]/page.tsx', 'r') as f:
    page = f.read()

original_len = len(content.split('\n'))
print(f"Starting file length: {original_len} lines")

# ============================================================
# Helper: find entry bounds (from key start to closing },\n)
# ============================================================
def find_entry_end(text, start_pos):
    """Find the end of an entry starting at start_pos.
    Returns position after the closing },\n"""
    # An entry ends with "},\n" at indentation level 0 (just },)
    # We look for the pattern: \n}, (at the start of a line, not indented)
    pos = start_pos
    depth = 0
    in_template = False
    in_string = False
    string_char = None
    i = pos
    while i < len(text):
        c = text[i]
        if in_template:
            if c == '`' and (i == 0 or text[i-1] != '\\'):
                in_template = False
        elif in_string:
            if c == string_char and (i == 0 or text[i-1] != '\\'):
                in_string = False
        else:
            if c == '`':
                in_template = True
            elif c in ('"', "'"):
                in_string = True
                string_char = c
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    # Check if followed by ,\n
                    rest = text[i:i+3]
                    if rest.startswith('},'):
                        return i + 3  # after },\n or },
                    elif text[i+1:i+2] == '\n':
                        return i + 2
                    else:
                        return i + 1
        i += 1
    return len(text)

# ============================================================
# New content blocks
# ============================================================

NEW_47901_CONTENT = '''  "47901": {
    whatItMeans:
      "Digital marketplace platform for retail intermediation — operating an e-commerce platform, website, or mobile app that connects third-party buyers and sellers for retail transactions, earning a commission or fee from the transaction without ever taking ownership of the goods sold. This is the Tokopedia, Shopee, Bukalapak, or Airbnb model: the platform facilitates; the individual sellers own the inventory. If your platform lists products from multiple independent vendors and earns per transaction, this is the code. Contrast: if you sell your own goods online (D2C), that is 47909.",
    whatYouNeed:
      `**All scales (Micro, Small, Medium, Large)**: Low risk (Rendah). NIB issued **automatically** (Otomatis). Authority: **OSS Pusat**.\\n\\nThe OSS licensing is genuinely minimal — NIB only. But operating a digital platform in Indonesia requires compliance with two additional regulatory frameworks outside the standard OSS licensing system:\\n\\n**Critical parallel obligation: PSE Registration at Kominfo**\\n- **PP 71/2019** mandates that any **Penyelenggara Sistem Elektronik (PSE)** — including e-commerce marketplace platforms — must register with the Ministry of Communication and IT (Kominfo)\\n- **Threshold:** Any platform processing personal data of Indonesian users must register. In practice: if you have Indonesian users and process any transaction or personal data, register\\n- **Consequence of non-compliance:** Kominfo has demonstrated willingness to IP-block non-compliant platforms (PayPal, Steam, Epic Games blocked July 2022). A blocked platform is a non-operating business\\n- PSE registration is done via pse.kominfo.go.id\\n\\n**Step-by-step for a PT PMA digital marketplace platform:**\\n1. **PT PMA incorporation** — notary deed, AHU registration; tech/digital sector minimum capital IDR 10B stated (~3–5 weeks)\\n2. **NIB via OSS** — register on oss.go.id, select 47901, Rendah path; auto-issued (1–3 days)\\n3. **PSE registration at Kominfo** — submit via pse.kominfo.go.id; documents: company identity (NIB, akta), platform description, system architecture overview, data flow documentation. Timeline: 1–2 weeks for standard platforms\\n4. **Data localization compliance** — under PP 71/2019 and UU PDP 2022: user personal data of Indonesian citizens must be stored on servers within Indonesian territory, or a copy maintained domestically\\n5. **Data Protection Officer (DPO)** — UU PDP 2022 requires a designated DPO for platforms processing personal data at scale\\n6. **PB UMKU per product category** (if applicable) — if your marketplace handles regulated goods (cosmetics, food, medicines), your platform-level governance over listed products may be scrutinized\\n7. **Laporan kegiatan usaha** — periodic business activity reports to Kemendag\\n8. **OJK compliance** (if fintech features) — if your platform includes buy-now-pay-later, escrow, or payment processing beyond a standard payment gateway, OJK licensing may apply separately\\n\\n**Typical total timeline:** 1–3 months from PT PMA to platform compliant.\\n**Minimum PT PMA capital:** IDR 10 billion stated capital (Rp 2.5B paid-up).\\n\\n**Authority:** OSS Pusat.\\n**PMA:** Fully open (Terbuka) — 100% foreign ownership.`,
    whatChanged:
      "MATCH_CON_AGGREGAZIONE — consolidated from multiple KBLI 2020 codes covering digital commerce intermediation into a single modernized 47901 framework. The PP 71/2019 PSE obligation and UU PDP 2022 data protection requirements are the most significant developments since KBLI 2020.",
    baliContext:
      "**💻 Digital Marketplaces from Bali (The Niche Opportunity)**\\n- The national horizontal marketplaces (Tokopedia, Shopee, Lazada, Bukalapak) are effectively unassailable at scale. The opportunity is **vertical and niche**:\\n- **Artisan and craft marketplace:** Bali has Indonesia's highest density of artisan producers (silverwork, textiles, ceramics, woodwork). A curated, internationally-targeted platform connecting Bali artisans with global buyers is genuinely underserved\\n- **Eco/organic/sustainable products:** Bali's expat community and eco-tourism sector create demand for sustainable, organic, and locally-sourced products that mainstream Indonesian marketplaces don't serve well\\n- **Hospitality B2B marketplace:** Connecting Bali hotel and villa operators with verified F&B suppliers, laundry services, and amenity vendors\\n- **Short-term rental intermediary:** Villa and accommodation booking platforms focused on Bali-specific inventory\\n\\n---\\n\\n**⚠ PSE Registration Is Not Optional**\\n- The 2022 blocking of major international platforms by Kominfo was a genuine shock. The enforcement mechanism exists and has been used\\n- Timeline: PSE registration is fast (1–2 weeks); do it the week you get your NIB\\n- **UU PDP 2022 compliance:** Full enforcement began October 2024. If your platform collects any user data, you need a Privacy Policy aligned with UU PDP, a DPO, and a data retention/deletion procedure\\n- **Cloud hosting:** AWS Jakarta (ap-southeast-3), Google Cloud Jakarta, Azure Indonesia are the primary compliant hosting options. Offshore-only hosting creates compliance risk",
    youllAlsoNeed:
      "- **47909** — If your operation also facilitates non-digital intermediary services (buying agent, concierge)\\n- **62011 / 62019** — Software development — if your PT PMA builds the platform tech in-house\\n- **63122** — Web portal operation — if your platform also functions as an informational portal\\n- **56400** — Food delivery platform — if your marketplace includes F&B delivery as a core feature\\n- **96400** — Other digital services — if your platform offers subscription or digital content alongside marketplace features",
    zantaraOpener:
      "Building an e-commerce marketplace in Indonesia? 47901 is NIB-only, auto-issued — but PSE registration at Kominfo and UU PDP 2022 data compliance are non-negotiable. Miss either and your platform gets blocked. Let me walk you through both.",
        tkaInfo: {
      categoryId: 16,
      categoryName: "Perdagangan Besar & Eceran",
      totalInCategory: 181,
      iscoGroupsSelected: ["13", "21", "31"],
      selectedForThisCode: 10,
      selectionMethod: "ISCO-based",
      relevantPositions: [
        { titleEn: "Operational Manager", titleId: "Manajer Operasional", isco: "1321" },
        { titleEn: "Purchasing Manager", titleId: "Manajer Pembelian", isco: "1324" },
        { titleEn: "General Manager", titleId: "Manajer Umum", isco: "1321" },
        { titleEn: "Procurement Manager", titleId: "Manajer Pengadaan", isco: "1324" },
        { titleEn: "Technical Manager", titleId: "Manajer Teknis", isco: "1324" },
        { titleEn: "Mechanical Advisor", titleId: "Penasihat Permesinan", isco: "3115" },
        { titleEn: "Machine Maintenance Advisor", titleId: "Penasihat Perawatan Mesin", isco: "3115" },
        { titleEn: "Electrical Advisor", titleId: "Penasihat Kelistrikan", isco: "3113" },
        { titleEn: "Mechanical Engineer", titleId: "Ahli Mesin", isco: "2144" },
        { titleEn: "Mechanical Maintenance Engineer", titleId: "Ahli Perawatan Mesin", isco: "2144" }
      ],
      insight: "Kepmen 228/2019 lists 181 TKA-eligible positions in this category. Selection optimized using ISCO classification methodology.",
      keduaNote: "Directors and Commissioners who do NOT manage personalia can work without being listed in the jabatan.",
    },
},
'''

NEW_47909_CONTENT = '''  "47909": {
    whatItMeans:
      "Other retail intermediary services — the catch-all code for businesses that facilitate retail transactions between parties without themselves being a digital marketplace platform (47901) or a wholesale trade agent (46100). This includes: aggregators who consolidate orders from multiple buyers, personal shoppers and buying agents, luxury goods concierge services, villa supply procurement specialists, and any intermediary that earns a fee or commission for facilitating retail purchases. The common thread: you don't own the goods you help source or procure — you earn a service fee for connecting buyer to seller or procuring on the buyer's behalf.",
    whatYouNeed:
      `**Scale-dependent risk in PP 28/2025:**\\n\\n**Standard operators (Rendah — the path for most businesses):**\\n- Low risk (Rendah). NIB issued **automatically** (Otomatis). Authority: **OSS Pusat**.\\n- Only an NIB is required. Genuinely the simplest licensing path in the retail sector.\\n\\n**Large-scale operators (Tinggi — MLM/direct selling at scale):**\\n- High risk (Tinggi). NIB + **Izin** required. Authority: **Menteri** (Minister of Trade level). Processing time: **5 working days**.\\n- This applies to large-scale direct selling and MLM network marketing operations — not to standard intermediary/concierge businesses.\\n\\n**For the standard Rendah path (most PT PMA applications):**\\n\\n**Step-by-step:**\\n1. **PT PMA incorporation** — notary deed, AHU registration; minimum IDR 10B stated capital (~3–5 weeks)\\n2. **NIB via OSS** — register on oss.go.id, select 47909, Rendah path; auto-issued (1–3 days)\\n3. **Define your service model clearly in company documents** — buying agent, procurement specialist, concierge, aggregator. The NIB is issued against your stated business activities; documenting what you do protects you in any audit\\n4. **Laporan kegiatan usaha** — periodic business activity reports to Kemendag (ongoing)\\n5. **Product-specific permits for regulated goods** — if you procure food, supplements, cosmetics, or medicines on behalf of clients, ensure your clients hold the relevant BPOM/Kemendag product permits\\n\\n**For the Tinggi path (direct selling / MLM operations only):**\\n1. Steps 1–2 above\\n2. **Izin from Menteri Perdagangan** — required documents: company deed, marketing plan (rencana pemasaran), distributor code of conduct (kode etik), sample distributor agreement, list of registered distributors\\n3. **Marketing plan review** — Kemendag scrutinizes MLM structures; ensure your structure complies with Permendag No. 70/2019\\n4. Izin issued within **5 working days** once documentation is complete\\n\\n**Typical total timeline (Rendah path):** 3–6 weeks from PT PMA to NIB in hand.\\n**Minimum PT PMA capital:** IDR 10 billion stated capital (Rp 2.5B paid-up).\\n\\n**Authority:** OSS Pusat (Rendah) · Menteri Perdagangan (Tinggi/MLM).\\n**PMA:** Fully open (Terbuka) — 100% foreign ownership.`,
    whatChanged:
      "MATCH_CON_AGGREGAZIONE — consolidated from multiple KBLI 2020 codes covering various non-platform retail intermediary types including direct selling, mail order, catalog sales, and other non-standard retail channels. The 2025 version explicitly separates standard intermediary (Rendah, NIB only) from MLM/direct selling at scale (Tinggi, Izin required).",
    baliContext:
      "**🛍 Intermediary Services in Bali (Where the Real Opportunity Is)**\\n- 47909 is the correct code for a cluster of Bali business models that are genuinely profitable but often misclassified:\\n\\n**Villa supply procurement specialist:**\\n- Bali has 10,000+ active villas, many managed by professional villa management companies. The management company procures F&B supplies, linen, toiletries, maintenance materials, and decor for villa owners\\n- A specialized villa procurement/sourcing company (47909) earns a service fee or commission on every purchase it facilitates on behalf of villa clients\\n- This is distinct from wholesale distribution — you don't warehouse goods; you identify, negotiate, and coordinate procurement\\n\\n**Luxury shopping concierge:**\\n- Bali's UHNW tourist segment (private jet arrivals, villa charters in Seminyak/Uluwatu, luxury resort guests) creates demand for personal shopping and luxury goods procurement services\\n- Personal shopper/concierge arranging luxury items (watches, bags, jewelry, bespoke garments) for wealthy visitors — earning commission or retainer fees\\n\\n**Corporate procurement aggregator:**\\n- Aggregating purchasing needs of multiple hotel groups or F&B operators and negotiating bulk pricing with suppliers — earning an aggregation/coordination fee\\n\\n---\\n\\n**⚠ Know When 47909 Ends and Other Codes Begin**\\n- **47901 (digital marketplace):** If you build a platform where third parties transact, that's 47901. 47909 is for human-mediated intermediary service, not automated platform facilitation\\n- **46100 (wholesale agents/brokers):** If you intermediate wholesale (B2B, volume) transactions — buyer is a business, not a consumer — that's 46100, not 47909\\n- **MLM/network marketing:** If your business recruits distributors who recruit distributors (downline structure), Kemendag scrutiny is real; enforcement of Permendag 70/2019 has intensified\\n- **Scale threshold:** In practice, a standard service-fee intermediary (concierge, buying agent) stays Rendah regardless of revenue. The Tinggi path is specifically activated by the MLM/direct-selling structure, not by business size alone",
    youllAlsoNeed:
      "- **47901** — If your operation evolves into a platform where multiple third-party sellers transact (marketplace model)\\n- **46100** — If you intermediate wholesale/B2B purchases rather than retail consumer transactions\\n- **82990** — Miscellaneous business support services — if your concierge/procurement activity is better framed as a B2B service\\n- **79110** — Travel agent/tour operator — if your concierge service includes travel and experience booking alongside retail procurement\\n- **68130** — Property management — if your villa supply procurement is bundled within a full villa management service",
    zantaraOpener:
      "Luxury concierge, villa procurement specialist, or buying agent in Bali? 47909 is your code — NIB only, auto-issued, 100% PMA. The catch-all for retail intermediaries that aren't a digital marketplace. Let me explain exactly what fits here.",
        tkaInfo: {
      categoryId: 16,
      categoryName: "Perdagangan Besar & Eceran",
      totalInCategory: 181,
      iscoGroupsSelected: ["13", "21", "31"],
      selectedForThisCode: 10,
      selectionMethod: "ISCO-based",
      relevantPositions: [
        { titleEn: "Operational Manager", titleId: "Manajer Operasional", isco: "1321" },
        { titleEn: "Purchasing Manager", titleId: "Manajer Pembelian", isco: "1324" },
        { titleEn: "General Manager", titleId: "Manajer Umum", isco: "1321" },
        { titleEn: "Procurement Manager", titleId: "Manajer Pengadaan", isco: "1324" },
        { titleEn: "Technical Manager", titleId: "Manajer Teknis", isco: "1324" },
        { titleEn: "Mechanical Advisor", titleId: "Penasihat Permesinan", isco: "3115" },
        { titleEn: "Machine Maintenance Advisor", titleId: "Penasihat Perawatan Mesin", isco: "3115" },
        { titleEn: "Electrical Advisor", titleId: "Penasihat Kelistrikan", isco: "3113" },
        { titleEn: "Mechanical Engineer", titleId: "Ahli Mesin", isco: "2144" },
        { titleEn: "Mechanical Maintenance Engineer", titleId: "Ahli Perawatan Mesin", isco: "2144" }
      ],
      insight: "Kepmen 228/2019 lists 181 TKA-eligible positions in this category. Selection optimized using ISCO classification methodology.",
      keduaNote: "Directors and Commissioners who do NOT manage personalia can work without being listed in the jabatan.",
    },
},
'''

NEW_4_ENTRIES = '''
  // ---------------------------------------------------------------------------
  // Retail — Automotive, Pharma Raw Materials (47xxx)
  // ---------------------------------------------------------------------------

  "47729": {
    whatItMeans:
      "Retail of pharmaceutical raw materials (Active Pharmaceutical Ingredients / APIs) and miscellaneous health-adjacent products — bulk pharmaceutical ingredients, chemical synthesis intermediates, lab reagents, and specialty health items that are not finished medicines (apotek = 47721) and not consumer medical devices (47725). The customer is typically a pharmaceutical manufacturer, compounding pharmacy, clinical laboratory, or research institution — not the end patient buying off a shelf.",
    whatYouNeed:
      `**Single scale in PP 28/2025 data**: Medium-High risk (Menengah Tinggi). NIB + Izin required — **not automatic**. Issued by **Bupati/Walikota** within **20 working days** — the longest processing time of any retail code in this section.\\n\\n**Mandatory regulatory approvals on top of OSS licensing:**\\n- **BPOM approval per substance** — every Active Pharmaceutical Ingredient requires a separate distribution authorization from BPOM. GMP documentation from the supplier, Certificate of Analysis per batch, BPOM product file submission\\n- **Izin from Kemenkes** — Ministry of Health permit for dealing in pharmaceutical raw materials\\n- **Import permit** — if importing APIs: Angka Pengenal Impor (API-U or API-P) + Nomor Induk Kepabeanan (NIK) from Bea Cukai; plus Kemenkes specific import authorization for controlled APIs\\n\\n**Step-by-step for a PT PMA pharmaceutical raw materials retailer:**\\n1. **PT PMA incorporation** — notary deed, AHU registration; pharma sector minimum IDR 10B stated (~3–5 weeks)\\n2. **NIB via OSS** — register on oss.go.id, select 47729, Menengah Tinggi path (~3 days)\\n3. **BPOM documentation per substance** — submit GMP certificate from manufacturer, Certificate of Analysis, product specification, stability data. Each API = separate BPOM file (2–6 months per substance; parallel submissions possible)\\n4. **Izin distribusi bahan baku farmasi** — submitted to Kemenkes; requires company profile, qualified pharmacist (Apoteker) as Penanggung Jawab, facility inspection (2–3 months)\\n5. **Kemenkes facility inspection** — storage facility must meet cold-chain or controlled storage requirements\\n6. **Izin from Bupati/Walikota via OSS** — issued within 20 working days after BPOM and Kemenkes clearance\\n7. **API import license** (if importing) — Kemenkes-specific import authorization per substance per year\\n8. **Penanggung Jawab Apoteker** — a licensed pharmacist must be formally designated; without this, no BPOM or Kemenkes approvals proceed\\n9. **Annual reporting** — laporan kegiatan usaha periodic to BPOM and Kemenkes\\n\\n**Typical total timeline:** 6–12 months from PT PMA to first substance cleared for sale.\\n**Minimum PT PMA capital:** IDR 10 billion stated capital (Rp 2.5B paid-up).\\n\\n**Authority:** Bupati/Walikota.\\n**PMA:** Fully open (Terbuka) — 100% foreign ownership.`,
    whatChanged:
      "Direct match from KBLI 2020 (MATCH_LANGSUNG). Code and scope unchanged — pharmaceutical raw materials retail has been a consistently regulated category. PP 28/2025 adds the formal OSS licensing pathway but does not change the underlying BPOM/Kemenkes requirements.",
    baliContext:
      "**🧪 Pharma Raw Materials in Bali (Niche Reality)**\\n- This is a small, specialized market concentrated in Denpasar and Sanur where clinics, compounding pharmacies, and aesthetic medicine practices are located\\n- Most demand comes from: compounding pharmacies (racikan resep), aesthetic clinics sourcing cosmeceutical actives, veterinary compounders, and research institutions (Universitas Udayana)\\n- Volume play is limited in Bali; the real Indonesian pharma raw materials market is in Jakarta, Surabaya, and Bandung near manufacturing clusters\\n\\n---\\n\\n**🎯 Where PMA Adds Genuine Value**\\n- **Specialty API importing** — foreign pharma companies with access to European/US GMP-certified APIs that Indonesian manufacturers cannot source locally\\n- **Lab reagents and diagnostics** — importing high-purity reagents for clinical labs and diagnostic centers; Bali's growing medical tourism sector creates demand\\n- **Cosmeceutical actives** — the boundary between pharma raw materials and cosmetic actives is thin; specialty actives used in aesthetic medicine (peptides, hyaluronic acid bulk, etc.)\\n\\n---\\n\\n**⚠ Critical Compliance Points**\\n- **Apoteker is non-negotiable** — you cannot get BPOM or Kemenkes approvals without a licensed pharmacist on staff as Penanggung Jawab\\n- **Cold chain compliance** — many APIs require controlled temperature storage (2–8°C or 15–25°C). BPOM inspects storage facilities\\n- **Per-substance approval** — each new API requires a separate BPOM process. Adding a new substance mid-operation means restarting the approval cycle for that substance\\n- **Controlled substance list** — some APIs are narkotika/psikotropika precursors; additional BNN authorization required. Do not assume all APIs are equivalent\\n- **20 hari = working days** — longest business license processing time in retail. BPOM and Kemenkes clearances must come FIRST",
    youllAlsoNeed:
      "- **47721** — Apotek (finished medicine retail) — if you also dispense to end consumers\\n- **47725** — Medical devices retail — if your product range includes diagnostic equipment or health devices\\n- **46441** — Wholesale pharmaceutical distribution — if you supply to other distributors or hospitals in bulk\\n- **21001 / 21002** — Pharmaceutical manufacturing — if your operation extends to compounding or processing APIs into finished dosage forms",
    zantaraOpener:
      "Importing or distributing pharmaceutical raw materials in Indonesia? 47729 carries the longest processing time in retail — 20 working days — plus mandatory BPOM approval per substance and a licensed pharmacist on staff. Let me show you the full path.",
    tkaInfo: {
      categoryId: 16,
      categoryName: "Perdagangan Besar & Eceran",
      totalInCategory: 181,
      iscoGroupsSelected: ["13", "21", "31"],
      selectedForThisCode: 10,
      selectionMethod: "ISCO-based",
      relevantPositions: [
        { titleEn: "Operational Manager", titleId: "Manajer Operasional", isco: "1321" },
        { titleEn: "Purchasing Manager", titleId: "Manajer Pembelian", isco: "1324" },
        { titleEn: "General Manager", titleId: "Manajer Umum", isco: "1321" },
        { titleEn: "Procurement Manager", titleId: "Manajer Pengadaan", isco: "1324" },
        { titleEn: "Technical Manager", titleId: "Manajer Teknis", isco: "1324" },
        { titleEn: "Mechanical Advisor", titleId: "Penasihat Permesinan", isco: "3115" },
        { titleEn: "Machine Maintenance Advisor", titleId: "Penasihat Perawatan Mesin", isco: "3115" },
        { titleEn: "Electrical Advisor", titleId: "Penasihat Kelistrikan", isco: "3113" },
        { titleEn: "Mechanical Engineer", titleId: "Ahli Mesin", isco: "2144" },
        { titleEn: "Mechanical Maintenance Engineer", titleId: "Ahli Perawatan Mesin", isco: "2144" }
      ],
      insight: "Kepmen 228/2019 lists 181 TKA-eligible positions in this category. Selection optimized using ISCO classification methodology.",
      keduaNote: "Directors and Commissioners who do NOT manage personalia can work without being listed in the jabatan.",
    },
},

  "47811": {
    whatItMeans:
      "Retail of brand-new automobiles — operating a car dealership that sells new vehicles directly to end consumers. This covers franchised dealerships (Toyota, Honda, Mitsubishi, Suzuki, BYD, etc.) as well as independent new-car importers/retailers. The defining feature: the vehicles are new, never previously registered. You sell to the buyer; you don't manufacture the cars.",
    whatYouNeed:
      `**Scale-dependent licensing in PP 28/2025:**\\n\\n**Kecil (Small — local dealer):** Low risk (Rendah). NIB issued **automatically** (Otomatis). Authority: **Bupati/Walikota**.\\n**Besar (Large — national chain):** Low risk (Rendah). NIB issued **automatically** (Otomatis). Authority: **OSS Pusat**.\\n\\nBoth scales require only an NIB — no Sertifikat Standar, no Izin, no separate approval. The licensing burden is genuinely low.\\n\\n**The real operational requirements come from manufacturers and vehicle registration law:**\\n\\n**Step-by-step for a PT PMA new car dealership:**\\n1. **PT PMA incorporation** — notary deed, AHU registration; automotive retail minimum capital typically IDR 10B stated (~3–5 weeks)\\n2. **NIB via OSS** — register on oss.go.id, select 47811, Rendah path; auto-issued (1–3 days)\\n3. **Principal/Dealer Agreement** — negotiate and execute dealer franchise agreement with the car manufacturer/principal (ATPM — Agen Tunggal Pemegang Merek); without this, you cannot access official new car inventory\\n4. **Showroom setup** — location must meet manufacturer's showroom standards. KKPR check for commercial vehicle retail use\\n5. **STNK/BPKB dealer authorization** — establish coordination with local Samsat to process STNK and BPKB issuance on behalf of buyers\\n6. **SNI compliance for EV charging** — if your dealership offers EV models with charging infrastructure: SNI 8972 for SPKLU applies; coordinate with PLN for power connection\\n7. **Laporan kegiatan usaha** — periodic business activity reports to Kemendag (ongoing obligation)\\n\\n**Typical total timeline:** 2–4 months from PT PMA to showroom-ready.\\n**Minimum PT PMA capital:** IDR 10 billion stated capital (Rp 2.5B paid-up).\\n\\n**Authority:** Bupati/Walikota (Kecil) · OSS Pusat (Besar).\\n**PMA:** Fully open (Terbuka) — 100% foreign ownership.`,
    whatChanged:
      "Direct match from KBLI 2020 (MATCH_LANGSUNG). New car retail has been a stable category. No substantive change in licensing requirements under PP 28/2025.",
    baliContext:
      "**🚗 Bali's Car Market (Reality Check)**\\n- **Dominant players:** Toyota (Auto2000), Honda (Honda Prospect Motor dealers), Mitsubishi (Krama Yudha Tiga Berlian), Suzuki — all have established dealer networks across Bali\\n- **Market reality:** The national dealers have Bali locked up. A new PMA entering standard mass-market new car retail would face extremely stiff competition from entrenched ATPM networks\\n- **EV segment:** The real near-term opportunity. BYD (now assembling in Indonesia), Wuling Air EV, and Hyundai Ioniq are generating genuine demand. The EV dealership ecosystem is nascent — ATPM agreements are newer, competition is lower, and government EV incentives (PPnBM reduction, SPKLU infrastructure grants) are active\\n- **Luxury imports:** Mercedes-Benz, BMW, Porsche, Audi serve the high-net-worth expat and local entrepreneur market. Bali has limited dedicated luxury car showrooms outside Denpasar — Canggu and Seminyak's expat density creates underserved demand\\n\\n---\\n\\n**⚠ Practical Traps**\\n- **The ATPM bottleneck:** Getting a genuine new car dealer agreement with a major ATPM as a new PMA is hard. Japanese brands have closed their Bali dealer networks — you'd need to acquire an existing dealership or find a brand without full Bali coverage\\n- **CBU vs CKD imports:** Completely Built-Up (CBU) imported cars face 50–80% import duties + 10% PPnBM; CKD assembled locally are far cheaper. PMA luxury car importers must price CBU units accordingly\\n- **EV infrastructure obligation:** If you sell EVs, customers increasingly expect charging at the showroom or through a network you can refer them to",
    youllAlsoNeed:
      "- **47812** — Used car retail — if you also trade in second-hand vehicles as part of the dealership\\n- **47820** — Spare parts and accessories retail — almost always combined with a dealership\\n- **45201** — Automotive repair and maintenance — the aftersales service center component\\n- **77110** — Car rental — if you offer demo or courtesy vehicles, or expand into fleet rental",
    zantaraOpener:
      "Opening a car dealership in Bali? 47811 has the simplest licensing of any retail code — NIB only, auto-issued — but the real gate is the manufacturer's Principal Agreement. Let me break down where to focus your effort.",
    tkaInfo: {
      categoryId: 16,
      categoryName: "Perdagangan Besar & Eceran",
      totalInCategory: 181,
      iscoGroupsSelected: ["13", "21", "31"],
      selectedForThisCode: 10,
      selectionMethod: "ISCO-based",
      relevantPositions: [
        { titleEn: "Operational Manager", titleId: "Manajer Operasional", isco: "1321" },
        { titleEn: "Purchasing Manager", titleId: "Manajer Pembelian", isco: "1324" },
        { titleEn: "General Manager", titleId: "Manajer Umum", isco: "1321" },
        { titleEn: "Procurement Manager", titleId: "Manajer Pengadaan", isco: "1324" },
        { titleEn: "Technical Manager", titleId: "Manajer Teknis", isco: "1324" },
        { titleEn: "Mechanical Advisor", titleId: "Penasihat Permesinan", isco: "3115" },
        { titleEn: "Machine Maintenance Advisor", titleId: "Penasihat Perawatan Mesin", isco: "3115" },
        { titleEn: "Electrical Advisor", titleId: "Penasihat Kelistrikan", isco: "3113" },
        { titleEn: "Mechanical Engineer", titleId: "Ahli Mesin", isco: "2144" },
        { titleEn: "Mechanical Maintenance Engineer", titleId: "Ahli Perawatan Mesin", isco: "2144" }
      ],
      insight: "Kepmen 228/2019 lists 181 TKA-eligible positions in this category. Selection optimized using ISCO classification methodology.",
      keduaNote: "Directors and Commissioners who do NOT manage personalia can work without being listed in the jabatan.",
    },
},

  "47812": {
    whatItMeans:
      "Retail of used (second-hand) automobiles — buying vehicles from private sellers, fleet operators, or at auction, then reselling them to end consumers. Unlike a new car dealer (47811) who sells manufacturer-fresh inventory, a used car dealer works with previously owned, registered vehicles where the BPKB (Bukti Pemilik Kendaraan Bermotor — vehicle ownership document) must be transferred at each transaction.",
    whatYouNeed:
      `**All scales**: Low risk (Rendah). NIB issued **automatically** (Otomatis). Authority: **OSS Pusat**. Only an NIB is required — the licensing itself is straightforward.\\n\\n**The operational complexity is not in the permit — it's in the BPKB transfer process and vehicle due diligence:**\\n\\n**Step-by-step for a PT PMA used car dealer:**\\n1. **PT PMA incorporation** — notary deed, AHU registration; minimum capital IDR 10B stated (~3–5 weeks)\\n2. **NIB via OSS** — register on oss.go.id, select 47812, Rendah path; auto-issued (1–3 days)\\n3. **Operational location** — showroom or lot; KKPR check for commercial vehicle retail use\\n4. **BPKB balik nama process per vehicle** — every vehicle requires:\\n   - Cek fisik kendaraan (physical inspection) at Samsat\\n   - BPKB balik nama (ownership document transfer) — via notarial deed or PPAT\\n   - STNK perpanjangan (vehicle registration renewal)\\n   - Cek status BPKB at the bank if the vehicle is collateral-encumbered\\n5. **Escrow/payment flow** — verify BPKB is clean before full payment\\n6. **Laporan kegiatan usaha** — periodic business activity reports (ongoing obligation)\\n\\n**Typical total timeline:** 1–2 months from PT PMA to first vehicle sold.\\n**Minimum PT PMA capital:** IDR 10 billion stated capital (Rp 2.5B paid-up).\\n\\n**Authority:** OSS Pusat.\\n**PMA:** Fully open (Terbuka) — 100% foreign ownership.`,
    whatChanged:
      "Direct match from KBLI 2020 (MATCH_LANGSUNG). Used car retail is a stable category. PP 28/2025 formalizes the OSS pathway; no change to BPKB transfer regulations, which are governed by separate Samsat/Korlantas rules.",
    baliContext:
      "**🚙 Bali's Used Car Market (Niche but Real)**\\n- Bali has an active secondhand car market driven by expatriates and long-term visitors who arrive, buy a car for 2–4 years, then leave. Toyota Rush, Toyota Avanza, Honda HR-V, and Suzuki Jimny are the most liquid used car models\\n- **Expat rotation cycle:** Creates a steady supply of well-maintained, relatively low-mileage vehicles entering the secondhand market every year — a genuine supply opportunity\\n- **Price anomaly:** Good condition secondhand vehicles in Bali often sell at a premium because expat buyers in Canggu/Seminyak are willing to pay for documented condition and hassle-free transfer\\n- **Platform shift:** Younger Bali residents increasingly buy secondhand through OLX, Carmudi, or Moladin. A physical lot business needs digital presence to compete\\n\\n---\\n\\n**⚠ BPKB Irregularities — The Single Biggest Risk**\\n- **Gadai BPKB (BPKB as loan collateral):** A significant portion of second-hand vehicles in Indonesia have their BPKB lodged with a bank or lender as security. Buying such a vehicle without clearing the BPKB releases means you cannot complete the ownership transfer\\n- **Verification:** Always check BPKB status at the issuing Samsat and contact the registered bank before purchase\\n- **Stolen vehicle register:** Cross-check chassis number (VIN) and engine number against the Korlantas stolen vehicle database before buying expensive units\\n- **Pajak mati (lapsed registration):** Vehicles with multiple years of unpaid annual road tax face progressive penalties at Samsat\\n- **Bali notary capacity:** BPKB balik nama in Bali is done through notary (PPAT). During peak real estate seasons, Bali notaries are backlogged — factor in 2–4 week transfer timelines",
    youllAlsoNeed:
      "- **47811** — New car retail — if you also sell brand-new vehicles\\n- **47820** — Spare parts retail — natural complement: used car buyers often need parts\\n- **45201** — Automotive repair and maintenance — reconditioning vehicles before resale\\n- **77110** — Car rental — some used car dealers cross into short-term rental for slower-moving stock",
    zantaraOpener:
      "Used car business in Bali? 47812 is NIB only — dead simple to register. The challenge is entirely operational: BPKB irregularities, Samsat transfers, and building a trustworthy sourcing pipeline. Let me explain what to watch for.",
    tkaInfo: {
      categoryId: 16,
      categoryName: "Perdagangan Besar & Eceran",
      totalInCategory: 181,
      iscoGroupsSelected: ["13", "21", "31"],
      selectedForThisCode: 10,
      selectionMethod: "ISCO-based",
      relevantPositions: [
        { titleEn: "Operational Manager", titleId: "Manajer Operasional", isco: "1321" },
        { titleEn: "Purchasing Manager", titleId: "Manajer Pembelian", isco: "1324" },
        { titleEn: "General Manager", titleId: "Manajer Umum", isco: "1321" },
        { titleEn: "Procurement Manager", titleId: "Manajer Pengadaan", isco: "1324" },
        { titleEn: "Technical Manager", titleId: "Manajer Teknis", isco: "1324" },
        { titleEn: "Mechanical Advisor", titleId: "Penasihat Permesinan", isco: "3115" },
        { titleEn: "Machine Maintenance Advisor", titleId: "Penasihat Perawatan Mesin", isco: "3115" },
        { titleEn: "Electrical Advisor", titleId: "Penasihat Kelistrikan", isco: "3113" },
        { titleEn: "Mechanical Engineer", titleId: "Ahli Mesin", isco: "2144" },
        { titleEn: "Mechanical Maintenance Engineer", titleId: "Ahli Perawatan Mesin", isco: "2144" }
      ],
      insight: "Kepmen 228/2019 lists 181 TKA-eligible positions in this category. Selection optimized using ISCO classification methodology.",
      keduaNote: "Directors and Commissioners who do NOT manage personalia can work without being listed in the jabatan.",
    },
},

  "47820": {
    whatItMeans:
      "Retail of automotive spare parts and accessories — selling car parts, tires, engine oils, filters, car accessories (dashcams, seat covers, audio, lighting), and car care products directly to end consumers and workshops. This covers both an independent parts store (toko spare part mobil) and a dedicated accessories outlet. If you import aftermarket parts, distribute tires, or run an auto accessories shop, this is the code.",
    whatYouNeed:
      `**Principal scale**: Low risk (Rendah). NIB issued **automatically** (Otomatis). Authority: **OSS Pusat**. Only an NIB is required.\\n\\n*(Some auxiliary scales in PP 28/2025 data show Bupati/Walikota authority — this applies at specific smaller sub-scales. For a standard PT PMA operation, OSS Pusat / Rendah is the applicable path.)*\\n\\n**Licensing is simple; import compliance is where the work is:**\\n\\n**Step-by-step for a PT PMA automotive spare parts retailer:**\\n1. **PT PMA incorporation** — notary deed, AHU registration; minimum IDR 10B stated capital (~3–5 weeks)\\n2. **NIB via OSS** — register on oss.go.id, select 47820, Rendah path; auto-issued (1–3 days)\\n3. **For importing parts** — obtain:\\n   - **API-U** (Angka Pengenal Impor Umum) — general import license from Kemendag\\n   - **NIK** (Nomor Induk Kepabeanan) — Bea Cukai customs registration for importing entities\\n4. **SNI compliance for regulated components** — certain auto parts require SNI certification before they can be sold legally:\\n   - Tires (ban): SNI 1811 mandatory\\n   - Safety glass (kaca otomotif): SNI 1326 mandatory\\n   - Seat belts: SNI mandatory\\n   - These require testing by BSNI-accredited lab; factory audits for recurring imports\\n5. **Official distributorship agreement** (optional but commercially important) — if acting as official distributor for a brand (Denso, Bosch, NGK, Bridgestone, etc.)\\n6. **Laporan kegiatan usaha** — periodic business activity reports (ongoing obligation)\\n\\n**Typical total timeline:** 2–4 weeks from PT PMA to NIB in hand. API-U and NIK can run in parallel (4–8 weeks total for import-ready status).\\n**Minimum PT PMA capital:** IDR 10 billion stated capital (Rp 2.5B paid-up).\\n\\n**Authority:** OSS Pusat (Rendah scale).\\n**PMA:** Fully open (Terbuka) — 100% foreign ownership.`,
    whatChanged:
      "Direct match from KBLI 2020 (MATCH_LANGSUNG). Automotive spare parts retail is a stable category. PP 28/2025 formalizes the OSS pathway; SNI requirements for regulated parts predate this regulation and are governed by separate BSNI/Kemenperin rules.",
    baliContext:
      "**🔧 Spare Parts in Bali (Stable Demand, Niche Imports)**\\n- Bali's vehicle density is among the highest in Indonesia per capita — the combination of 4+ million residents, 6+ million annual tourists (2024 figure), and a massive motorbike and rental car fleet creates persistent demand for maintenance parts\\n- **Core market:** Workshop supply (bengkel supply) — local workshops serving private cars, rental fleets, hotel shuttle vehicles. Fast-moving items: oil filters, air filters, brake pads, spark plugs, belts, and lubricants\\n- **Tourist rental fleet:** Bali's car and motorbike rental sector is estimated at 100,000+ registered vehicles\\n\\n---\\n\\n**🎯 PMA Opportunities in This Sector**\\n- **JDM (Japanese Domestic Market) parts importing:** Japanese cars dominate Bali (Toyota, Honda, Suzuki are the top 3 brands). Japanese-spec OEM and high-performance parts have a niche following among Bali's car enthusiast community and premium rental operators\\n- **European OEM parts:** For the growing luxury car segment (BMW, Mercedes, Porsche in Bali), access to genuine European OEM parts is a genuine gap\\n- **EV parts ecosystem:** As EV penetration grows in Bali, demand for EV-specific maintenance items (cabin filters, brake fluid, 12V auxiliary batteries) will grow. First-mover opportunity\\n\\n---\\n\\n**⚠ Practical Points**\\n- **SNI tires is real enforcement:** The tire SNI requirement (SNI 1811) is actively enforced. Importing tires without SNI marking means confiscation. Budget IDR 50–150M per tire model for testing and certification\\n- **Counterfeit parts exposure:** The Indonesian aftermarket parts market has significant counterfeit/KW product circulation. Documented supply chain protects you\\n- **Service + parts combo:** Most successful Bali auto parts businesses combine 47820 (retail) with 45201 (automotive repair). The service workshop drives parts consumption",
    youllAlsoNeed:
      "- **45201** — Automotive repair and maintenance — the natural partner code; service workshop + parts retail\\n- **47811** — New car dealership — if your operation includes new vehicle sales alongside parts\\n- **46591** — Wholesale vehicle parts distribution — if you supply other workshops and retailers at wholesale\\n- **47190** — General retail (catch-all) — if your store also sells non-automotive retail items",
    zantaraOpener:
      "Automotive spare parts in Bali? 47820 is the simplest retail license to get — NIB only, auto-issued. The real work is in SNI compliance for tires, import permits, and building reliable supply chains for the parts that actually move. Let me walk you through it.",
    tkaInfo: {
      categoryId: 16,
      categoryName: "Perdagangan Besar & Eceran",
      totalInCategory: 181,
      iscoGroupsSelected: ["13", "21", "31"],
      selectedForThisCode: 10,
      selectionMethod: "ISCO-based",
      relevantPositions: [
        { titleEn: "Operational Manager", titleId: "Manajer Operasional", isco: "1321" },
        { titleEn: "Purchasing Manager", titleId: "Manajer Pembelian", isco: "1324" },
        { titleEn: "General Manager", titleId: "Manajer Umum", isco: "1321" },
        { titleEn: "Procurement Manager", titleId: "Manajer Pengadaan", isco: "1324" },
        { titleEn: "Technical Manager", titleId: "Manajer Teknis", isco: "1324" },
        { titleEn: "Mechanical Advisor", titleId: "Penasihat Permesinan", isco: "3115" },
        { titleEn: "Machine Maintenance Advisor", titleId: "Penasihat Perawatan Mesin", isco: "3115" },
        { titleEn: "Electrical Advisor", titleId: "Penasihat Kelistrikan", isco: "3113" },
        { titleEn: "Mechanical Engineer", titleId: "Ahli Mesin", isco: "2144" },
        { titleEn: "Mechanical Maintenance Engineer", titleId: "Ahli Perawatan Mesin", isco: "2144" }
      ],
      insight: "Kepmen 228/2019 lists 181 TKA-eligible positions in this category. Selection optimized using ISCO classification methodology.",
      keduaNote: "Directors and Commissioners who do NOT manage personalia can work without being listed in the jabatan.",
    },
},
'''

HERO_IMAGES = '''  "47729": {
    src: "https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?w=1600&q=80&auto=format",
    alt: "Pharmaceutical laboratory raw materials chemicals",
    overlay: "linear-gradient(135deg, rgba(5,15,25,0.70) 0%, rgba(8,25,42,0.53) 50%, rgba(5,15,25,0.70) 100%)",
  },
  "47811": {
    src: "https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?w=1600&q=80&auto=format",
    alt: "New car dealership showroom luxury automobile",
    overlay: "linear-gradient(135deg, rgba(10,10,20,0.70) 0%, rgba(18,18,38,0.53) 50%, rgba(10,10,20,0.70) 100%)",
  },
  "47812": {
    src: "https://images.unsplash.com/photo-1502877338535-766e1452684a?w=1600&q=80&auto=format",
    alt: "Used car lot dealership second hand vehicles",
    overlay: "linear-gradient(135deg, rgba(15,10,10,0.68) 0%, rgba(28,18,18,0.52) 50%, rgba(15,10,10,0.68) 100%)",
  },
  "47820": {
    src: "https://images.unsplash.com/photo-1486262715619-67b85e0b08d3?w=1600&q=80&auto=format",
    alt: "Car spare parts accessories automotive retail",
    overlay: "linear-gradient(135deg, rgba(15,15,10,0.68) 0%, rgba(28,28,18,0.52) 50%, rgba(15,15,10,0.68) 100%)",
  },
  "47901": {
    src: "https://images.unsplash.com/photo-1563013544-824ae1b704d3?w=1600&q=80&auto=format",
    alt: "E-commerce platform digital marketplace online shopping",
    overlay: "linear-gradient(135deg, rgba(5,10,30,0.72) 0%, rgba(8,18,52,0.55) 50%, rgba(5,10,30,0.72) 100%)",
  },
  "47909": {
    src: "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=1600&q=80&auto=format",
    alt: "Retail intermediary service shopping concierge luxury",
    overlay: "linear-gradient(135deg, rgba(20,10,5,0.68) 0%, rgba(38,18,8,0.52) 50%, rgba(20,10,5,0.68) 100%)",
  },
'''

# ============================================================
# 1. Find and replace 47901 entry
# ============================================================
old47901_marker = '  "47901": {\n    whatItMeans:\n      "Digital Platform for Retail Intermediation'
pos47901 = content.find(old47901_marker)
if pos47901 < 0:
    print("ERROR: 47901 old stub not found")
    exit(1)

# Find end of 47901 entry (goes to next entry)
end47901 = find_entry_end(content, pos47901)
old47901_chunk = content[pos47901:end47901]
print(f"47901 old chunk length: {len(old47901_chunk)} chars, ends with: ...{old47901_chunk[-50:]}")

content = content[:pos47901] + NEW_47901_CONTENT + '\n' + content[end47901:]
print(f"47901 replaced. New content length: {len(content.split(chr(10)))} lines")

# ============================================================
# 2. Find and replace 47909 entry
# ============================================================
old47909_marker = '  "47909": {\n    whatItMeans:\n      "Retail intermediary services via other media'
pos47909 = content.find(old47909_marker)
if pos47909 < 0:
    print("ERROR: 47909 old stub not found")
    exit(1)

end47909 = find_entry_end(content, pos47909)
old47909_chunk = content[pos47909:end47909]
print(f"47909 old chunk length: {len(old47909_chunk)} chars, ends with: ...{old47909_chunk[-50:]}")

content = content[:pos47909] + NEW_47909_CONTENT + '\n' + content[end47909:]
print(f"47909 replaced. New content length: {len(content.split(chr(10)))} lines")

# ============================================================
# 3. Insert 4 new entries before closing };
# ============================================================
lines = content.split('\n')
close_idx = None
for i in range(len(lines)-1, 0, -1):
    if lines[i].strip() == '};':
        close_idx = i
        break

if close_idx is None:
    print("ERROR: Could not find closing };")
    exit(1)

print(f"Inserting 4 new entries before line {close_idx+1}")
# Insert before the closing };
lines.insert(close_idx, NEW_4_ENTRIES)
content = '\n'.join(lines)
print(f"After inserting 4 new entries: {len(content.split(chr(10)))} lines")

# ============================================================
# 4. Write updated gold content
# ============================================================
with open('lib/kbli-gold-content.ts', 'w') as f:
    f.write(content)
print("✓ lib/kbli-gold-content.ts written")

# ============================================================
# 5. Add hero images to page.tsx
# ============================================================
HERO_MARKER = '  "96900": {\n    src: "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b'
if HERO_MARKER not in page:
    print("ERROR: hero image marker not found in page.tsx")
    # Try alternative
    print("Trying alternative marker...")
    HERO_MARKER2 = '"96900": {'
    if HERO_MARKER2 in page:
        idx = page.find(HERO_MARKER2)
        # Find closing }; of this entry
        entry_end = page.find('\n};', idx)
        print(f"96900 block found, closing }}; at pos {entry_end}")
else:
    # Find the closing }, of 96900 entry and insert after
    idx = page.find(HERO_MARKER)
    # Find the },\n}; pattern (end of GOLD_HERO_IMAGES)
    close_bracket = page.find('\n};', idx)
    if close_bracket > 0:
        # Insert HERO_IMAGES before the };
        page = page[:close_bracket + 1] + HERO_IMAGES + '};\n' + page[close_bracket + 4:]
        print(f"✓ Hero images inserted in page.tsx (before closing}})")
    else:
        # Try finding the end of 96900 entry differently
        idx96900_end = page.find('\n  },\n};', idx)
        if idx96900_end > 0:
            page = page[:idx96900_end + 6] + '\n' + HERO_IMAGES + '};' + page[idx96900_end + 8:]
            print(f"✓ Hero images inserted using alt method")
        else:
            print("ERROR: could not insert hero images")

with open('app/kbli/[code]/page.tsx', 'w') as f:
    f.write(page)
print("✓ app/kbli/[code]/page.tsx written")

print("\nDone! Summary:")
print(f"  lib/kbli-gold-content.ts: {len(content.split(chr(10)))} lines")
print(f"  app/kbli/[code]/page.tsx: {len(page.split(chr(10)))} lines")
