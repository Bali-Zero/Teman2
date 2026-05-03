#!/usr/bin/env python3
"""Apply Session 13 gold content — 6 Wholesale Food/Grocery KBLI codes"""
import re

with open('lib/kbli-gold-content.ts', 'r') as f:
    content = f.read()

with open('app/kbli/[code]/page.tsx', 'r') as f:
    page = f.read()

print(f"Starting: {len(content.split(chr(10)))} lines")

# ============================================================
# Helper: find end of an entry
# ============================================================
def find_entry_end(text, start_pos):
    i = start_pos
    depth = 0
    in_template = False
    in_string = False
    string_char = None
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
                    if text[i+1:i+3] in (',\n', ',\r'):
                        return i + 3
                    elif text[i+1:i+2] == '\n':
                        return i + 2
                    else:
                        return i + 1
        i += 1
    return len(text)

# ============================================================
# NEW CONTENT — 6 codes
# ============================================================

NEW_46311 = '''  "46311": {
    whatItMeans:
      "Wholesale rice distribution — bulk buying and selling of beras (rice) to retailers, hotels, restaurants, hospitals, and institutional buyers. Rice is a 'barang kebutuhan pokok' (essential staple commodity) in Indonesia — one of nine commodities under direct government price and distribution oversight. If you source rice from millers, cooperatives, or Bulog and distribute it in volume to B2B buyers, this is the code. Covers both regular rice varieties and premium grades (aromatic, organic, imported specialty).",
    whatYouNeed:
      `**All scales**: Low risk (Rendah). NIB issued **automatically** (Otomatis). Authority: **OSS Pusat**.\\n\\nThe NIB is auto-issued, but distributing rice — as a government-controlled essential commodity — triggers additional compliance obligations:\\n\\n**Step-by-step for a PT PMA wholesale rice distributor:**\\n1. **PT PMA incorporation** — notary deed, AHU registration; trading sector minimum IDR 10B stated (~3–5 weeks)\\n2. **NIB via OSS** — register on oss.go.id, select 46311, Rendah path; auto-issued (1–3 days)\\n3. **STP Distributor/Agen** (optional) — Surat Tanda Pendaftaran Distributor/Agen from Kemendag; not legally mandatory for NIB issuance, but required to participate in government distribution programs (kebutuhan pokok distribution channels, Bulog partnerships). Recommended for any serious wholesale rice operation\\n4. **HET compliance (Harga Eceran Tertinggi)** — the government sets maximum retail prices for staple rice. As a wholesaler selling to retailers, you must price such that your retailer customers can still comply with HET. Selling above the permitted distributor margin triggers Kemendag sanctions\\n5. **Laporan distribusi bulanan** — mandatory monthly distribution activity reports to Menteri Perdagangan. This is a real ongoing obligation; non-reporting can trigger license review\\n6. **IT-Beras (Izin Impor Beras)** — if importing rice: a separate import license (Izin Impor / IT-Beras) from Kemendag is required, entirely distinct from your NIB. Standard rice imports are channeled through Bulog (state logistics agency) — private importers require specific Kemendag authorization, typically for non-Bulog categories such as premium aromatic rice, organic varieties, or specialty imports for the hotel segment\\n7. **SNI 6128:2020** — National Standard for rice quality grading; required for packaged rice sold to retail\\n8. **BPOM MD registration** — mandatory for any packaged/branded rice product (beras kemasan) sold to retailers with a food label\\n\\n**Typical total timeline:** 2–4 weeks from PT PMA to NIB. Import license (if applicable): additional 4–8 weeks.\\n**Minimum PT PMA capital:** IDR 10 billion stated capital (Rp 2.5B paid-up).\\n\\n**Authority:** OSS Pusat.\\n**PMA:** Fully open (Terbuka) — 100% foreign ownership.`,
    whatChanged:
      "Direct match from KBLI 2020 (MATCH_LANGSUNG). Wholesale rice is a stable category. The major regulatory development since 2020 is the government's intensified HET enforcement following the 2022 cooking oil crisis, which prompted tighter controls across all 'kebutuhan pokok' commodities including rice.",
    baliContext:
      "**🌾 Rice Wholesale in Bali (Essential Commodity, Managed Market)**\\n\\n**Market scale:**\\n- Bali's 4,000+ hotels, 8,000+ restaurants, 15+ hospitals, and hundreds of school and institutional kitchens represent a massive, captive demand base for rice\\n- Daily F&B operations at a single 5-star resort can consume 50–200 kg/day of rice\\n- The Bali hotel segment is the most reliable buyer: predictable volumes, prompt payment, quality-conscious\\n\\n**The PMA opportunity — premium segment:**\\n- Standard Bulog-grade rice (IR64, medium grade) is dominated by established Javanese distributors. Competing here on price is very difficult for a PMA\\n- The genuine opportunity is **premium and specialty rice** not covered by Bulog's import mandate:\\n  - **Japanese Koshihikari / Akitakomachi** — demanded by Japanese restaurants and hotel Japanese dining outlets across Bali. Sources: direct import or via Tokyo Food/import houses in Jakarta\\n  - **Thai Jasmine (Hom Mali)** — preferred by Thai restaurant kitchens and Bali's large Thai chef community\\n  - **Organic beras merah/hitam (red/black rice)** — growing demand from health-conscious cafes and vegan restaurants in Canggu/Seminyak\\n  - **Bali heritage rice varieties** — Bali has 50+ traditional rice varieties; some are cultivated by sustainable agriculture communities and demanded by eco-resorts\\n\\n**⚠ HET compliance is real enforcement:**\\n- Ministry of Trade (Kemendag) conducts periodic market operations (operasi pasar) when rice prices spike\\n- Distributors found selling above permitted margins face immediate sanctions — license review, administrative fines, and product confiscation\\n- During major national events (Ramadan, Lebaran, Christmas–New Year) enforcement intensifies significantly\\n- Keep all purchase invoices and sales records; inspectors do check distribution chain documentation\\n\\n**⚠ Import IT-Beras is genuinely restrictive:**\\n- Standard rice import is a state monopoly via Bulog\\n- Private importers for premium categories must apply to Kemendag and demonstrate the rice variety is not covered by Bulog's mandate. The process takes 4–8 weeks and requires commercial justification",
    youllAlsoNeed:
      "- **46312** — Wholesale fruits — natural complement for full F&B fresh produce distribution\\n- **46319** — Wholesale other food/beverage — if you also supply spices, condiments, or other dry goods\\n- **52292** — Dry warehousing — if you operate your own rice storage facility\\n- **46590** — Wholesale of other non-food products — if your distribution expands to packaging materials\\n- **10611** — Rice milling — if you vertically integrate from milling to wholesale distribution",
    zantaraOpener:
      "Wholesale rice distribution in Bali? 46311 is NIB-only, auto-issued — but as a 'kebutuhan pokok', you're under monthly reporting to Kemendag, HET price caps, and a separate import license if you bring in premium varieties. The premium hotel segment is where PMA adds real value.",
    tkaInfo: {
      categoryId: 7,
      categoryName: "Perdagangan Besar",
      totalInCategory: 198,
      iscoGroupsSelected: ["13", "24", "31"],
      selectedForThisCode: 8,
      selectionMethod: "ISCO-based",
      relevantPositions: [
        { titleEn: "Wholesale Trade Manager", titleId: "Manajer Perdagangan Besar", isco: "1324" },
        { titleEn: "Supply Chain Manager", titleId: "Manajer Rantai Pasokan", isco: "1324" },
        { titleEn: "General Manager", titleId: "Manajer Umum", isco: "1321" },
        { titleEn: "Procurement Specialist", titleId: "Spesialis Pengadaan", isco: "2421" },
        { titleEn: "Distribution Coordinator", titleId: "Koordinator Distribusi", isco: "3339" },
        { titleEn: "Food Quality Inspector", titleId: "Inspektur Mutu Pangan", isco: "3119" },
        { titleEn: "Import Documentation Specialist", titleId: "Spesialis Dokumentasi Impor", isco: "3339" },
        { titleEn: "Commodity Trading Analyst", titleId: "Analis Perdagangan Komoditas", isco: "2421" }
      ],
      insight: "Kepmen 228/2019 lists 198 TKA-eligible positions in this category. Selection optimized using ISCO classification methodology.",
      keduaNote: "Directors and Commissioners who do NOT manage personalia can work without being listed in the jabatan.",
    },
},
'''

NEW_46312 = '''  "46312": {
    whatItMeans:
      "Wholesale fruit distribution — bulk buying and selling of fresh, dried, or processed fruits to retailers, hotels, restaurants, juice bars, and F&B manufacturers. This covers domestic tropical fruits (mangosteen, dragon fruit, rambutan, salak, durian, jackfruit) as well as imported temperate and exotic varieties (apples, grapes, berries, avocados, cherries). If you source from farmers, cooperatives, or importers and distribute in volume to B2B buyers, this is the code.",
    whatYouNeed:
      `**All scales**: Low risk (Rendah). NIB issued **automatically** (Otomatis). Authority: **OSS Pusat**.\\n\\n**Step-by-step for a PT PMA wholesale fruit distributor:**\\n1. **PT PMA incorporation** — notary deed, AHU registration; trading sector minimum IDR 10B stated (~3–5 weeks)\\n2. **NIB via OSS** — register on oss.go.id, select 46312, Rendah path; auto-issued (1–3 days)\\n3. **API-U (Angka Pengenal Impor Umum)** — if importing fruits: general import license from Kemendag, required for any entity importing goods commercially\\n4. **Phytosanitary compliance** — all imported fresh fruits require:\\n   - Phytosanitary certificate from country of origin (issued by origin country's plant health authority)\\n   - Import quarantine inspection by Badan Karantina Pertanian (Barantan) upon arrival at port\\n   - Any restricted species (certain citrus varieties, mangoes) require specific import permits\\n5. **BPOM ML registration** — mandatory for any packaged/processed fruit products with a food label (dried fruits, packaged fruit salads, fruit preserves) destined for retail sale\\n6. **Cold chain logistics** — fresh imported fruits require temperature-controlled transport and storage (0–4°C for most temperate fruits). Without verified cold chain, shelf life and quality deteriorate rapidly, creating B2B contract risk\\n7. **STP Distributor/Agen** (optional) — Kemendag registration; recommended for access to formal distribution networks\\n8. **Laporan kegiatan usaha** — periodic business activity reports (ongoing obligation)\\n\\n**Horticultural import windows:**\\nPermendag on horticultural imports sets seasonal import quotas and windows for certain fruit categories. Check current Kemendag circular for applicable restrictions before planning import volumes.\\n\\n**Typical total timeline:** 2–4 weeks from PT PMA to NIB. API-U: parallel 4–6 weeks.\\n**Minimum PT PMA capital:** IDR 10 billion stated capital (Rp 2.5B paid-up).\\n\\n**Authority:** OSS Pusat.\\n**PMA:** Fully open (Terbuka) — 100% foreign ownership.`,
    whatChanged:
      "Direct match from KBLI 2020 (MATCH_LANGSUNG). Wholesale fruit distribution is a stable category. The main regulatory development is the tightening of horticultural import controls under Permendag No. 20/2021 and its amendments, which introduced more specific import windows and quota mechanisms.",
    baliContext:
      "**🍍 Fruit Wholesale in Bali (Hotel Buffet Economy)**\\n\\n**The Bali F&B fruit demand:**\\n- Bali's hotel sector is the premium end of Indonesia's fruit wholesale market. A 5-star resort breakfast buffet for 300 guests consumes 80–150 kg of fresh fruit daily — and the quality bar is high\\n- Domestic tropical fruits (salak, mangosteen, dragon fruit, rambutan, snake fruit) are Bali's export face to the world and hotel buffet staples\\n- Imported temperate fruits (Australian avocados, Chilean grapes, US cherries, New Zealand apples) command 3–5x the margin of domestic fruit and are mandatory for international hotel brands\\n\\n**The PMA competitive advantage:**\\n- Direct import relationships with Australian, Chilean, and New Zealand fruit exporters\\n- Cold chain logistics capability (refrigerated trucks + cold storage) — the single biggest differentiator in Bali's fruit wholesale market\\n- Consistent quality grading (GA1/GA2 standards) that domestic pasar wholesalers cannot guarantee\\n\\n**Key buyers:**\\n- 5-star hotel chains: Marriott, Hilton, Accor, Four Seasons, Aman, Como — all purchase through centralized F&B procurement\\n- Juice bar chains in Canggu/Seminyak (Peloton, Sayuri, Milk & Madu, Old Man's) — significant consistent volumes\\n- Japanese and Korean restaurants concentrated in Legian/Seminyak — require Japan-spec quality grading\\n\\n**Bali cold chain gap:**\\n- Most domestic fruit wholesalers in Pasar Badung and Pasar Kumbasari operate without refrigeration\\n- A PMA-operated cold chain fruit distributor serving the hotel corridor (Nusa Dua → Seminyak → Canggu) fills a genuine market gap\\n\\n**⚠ Import windows matter:**\\n- Some fruit import quotas are seasonal and limited (e.g., durian from Thailand has specific import windows). Plan import schedules around Kemendag quota announcements",
    youllAlsoNeed:
      "- **46313** — Wholesale vegetables — natural pairing for full fresh produce distribution\\n- **52291** — Cold storage warehousing — if you operate refrigerated storage alongside distribution\\n- **49239** — Refrigerated goods transport — if you run your own cold chain trucks\\n- **46319** — Wholesale other food — if you expand to honey, spices, or specialty ingredients\\n- **10390** — Processing of fruit and vegetables — if you also process (juice, preserve) alongside wholesale",
    zantaraOpener:
      "Wholesale fruit distribution to Bali's hotels and restaurants? 46311 is NIB-only, auto-issued. The real differentiator is cold chain logistics and direct import relationships — domestic wholesalers can't match that. Let me walk you through the import compliance path.",
    tkaInfo: {
      categoryId: 7,
      categoryName: "Perdagangan Besar",
      totalInCategory: 198,
      iscoGroupsSelected: ["13", "24", "31"],
      selectedForThisCode: 8,
      selectionMethod: "ISCO-based",
      relevantPositions: [
        { titleEn: "Wholesale Trade Manager", titleId: "Manajer Perdagangan Besar", isco: "1324" },
        { titleEn: "Supply Chain Manager", titleId: "Manajer Rantai Pasokan", isco: "1324" },
        { titleEn: "General Manager", titleId: "Manajer Umum", isco: "1321" },
        { titleEn: "Procurement Specialist", titleId: "Spesialis Pengadaan", isco: "2421" },
        { titleEn: "Cold Chain Logistics Coordinator", titleId: "Koordinator Logistik Rantai Dingin", isco: "3339" },
        { titleEn: "Food Quality Inspector", titleId: "Inspektur Mutu Pangan", isco: "3119" },
        { titleEn: "Import Documentation Specialist", titleId: "Spesialis Dokumentasi Impor", isco: "3339" },
        { titleEn: "Commodity Trading Analyst", titleId: "Analis Perdagangan Komoditas", isco: "2421" }
      ],
      insight: "Kepmen 228/2019 lists 198 TKA-eligible positions in this category. Selection optimized using ISCO classification methodology.",
      keduaNote: "Directors and Commissioners who do NOT manage personalia can work without being listed in the jabatan.",
    },
},
'''

NEW_46313 = '''  "46313": {
    whatItMeans:
      "Wholesale vegetable distribution — bulk buying and selling of fresh, frozen, or processed vegetables to the F&B sector, retailers, and institutional buyers. This covers domestic highland vegetables (potatoes, cabbage, carrots, tomatoes, chili) from Bedugul/Kintamani growing areas as well as imported temperate and specialty vegetables (asparagus, artichokes, zucchini, leafy greens, Japanese vegetables) that Bali's hotel kitchens require for Western and Japanese cuisine. If you source from farmers, producers, or importers and distribute in volume to B2B buyers, this is the code.",
    whatYouNeed:
      `**All scales**: Low risk (Rendah). NIB issued **automatically** (Otomatis). Authority: **OSS Pusat**.\\n\\n**Step-by-step for a PT PMA wholesale vegetable distributor:**\\n1. **PT PMA incorporation** — notary deed, AHU registration; trading sector minimum IDR 10B stated (~3–5 weeks)\\n2. **NIB via OSS** — register on oss.go.id, select 46313, Rendah path; auto-issued (1–3 days)\\n3. **API-U** — if importing vegetables: general import license from Kemendag\\n4. **Phytosanitary compliance** — all imported fresh vegetables require:\\n   - Phytosanitary certificate from origin country\\n   - Badan Karantina Pertanian (Barantan) quarantine inspection at arrival port\\n   - Certain vegetables have specific import permits or are restricted (check Barantan's restricted plant product list annually)\\n5. **Pesticide residue monitoring** — BPOM monitors pesticide residue in both imported and domestic fresh produce. Imported vegetables must comply with Indonesian MRL (Maximum Residue Limit) standards. Certified organic produce from recognized certifiers (LSPO, Control Union) avoids MRL scrutiny\\n6. **BPOM ML/MD registration** — mandatory for any packaged/processed vegetable product (frozen vegetables, packaged salads, pre-cut vegetables) with food labeling sold to retail\\n7. **Cold chain** — most fresh vegetables require 2–8°C temperature control in transit and storage. Without refrigerated logistics, losses can reach 30–40% for perishables\\n8. **STP Distributor/Agen** (optional) — Kemendag registration; recommended for formal distribution network access\\n9. **Laporan kegiatan usaha** — periodic business activity reports (ongoing obligation)\\n\\n**Typical total timeline:** 2–4 weeks from PT PMA to NIB. API-U: parallel 4–6 weeks.\\n**Minimum PT PMA capital:** IDR 10 billion stated capital (Rp 2.5B paid-up).\\n\\n**Authority:** OSS Pusat.\\n**PMA:** Fully open (Terbuka) — 100% foreign ownership.`,
    whatChanged:
      "Direct match from KBLI 2020 (MATCH_LANGSUNG). Wholesale vegetable distribution is a stable category. Key development: BPOM's intensified monitoring of pesticide residues in imported vegetables since 2021, and growing institutional demand for certified organic produce.",
    baliContext:
      "**🥬 Vegetable Wholesale in Bali (Two Distinct Markets)**\\n\\n**Market 1 — Domestic highland supply:**\\n- Bedugul (Tabanan), Kintamani (Bangli), and Candikuning are Bali's primary vegetable-growing zones, benefiting from cool highland temperatures\\n- Potatoes, cabbage, carrots, tomatoes, shallots, chili, and leafy greens come from these areas to Pasar Badung (central market)\\n- This is the high-volume, low-margin market dominated by established Balinese traders\\n\\n**Market 2 — Imported specialty vegetables (the PMA opportunity):**\\n- Bali's international hotel kitchens demand vegetables that local highland farms cannot supply reliably: asparagus, artichokes, broccolini, French beans, cherry tomatoes, purple eggplant, Japanese cucumber, daikon, burdock root, shiso, edamame\\n- Source countries: Australia (Western vegetables), Japan/Korea (Japanese/Korean specialty), Netherlands (tulip bulbs and European vegetables via Singapore)\\n- A direct-import vegetable distributor targeting the hotel procurement corridor (Nusa Dua → Uluwatu → Seminyak → Canggu) is genuinely underserved\\n\\n**Organic produce — fast-growing segment:**\\n- Canggu and Seminyak's health-conscious restaurant scene (Nalu Bowls, Shady Shack, Revolver Espresso, Shelter) increasingly demands certified organic produce\\n- Local organic farms (Jiva Nipah in Tabanan, Bali Organik Subak cooperative) produce some organic vegetables, but volume is limited\\n- Imported certified organic vegetables from Australia or New Zealand command 4–6x domestic price and are willingly paid by premium buyers\\n\\n**⚠ BPOM pesticide enforcement:**\\n- BPOM conducts periodic market surveillance of imported fresh vegetables\\n- Non-compliant shipments (exceeding MRL) are rejected at port or recalled from market\\n- Maintain supplier phytosanitary certificates and CoA (Certificate of Analysis) for every lot — required for any BPOM inquiry",
    youllAlsoNeed:
      "- **46312** — Wholesale fruits — natural complement for full fresh produce portfolio\\n- **52291** — Cold storage warehousing — refrigerated storage for perishable vegetable stock\\n- **49239** — Refrigerated transport — cold chain trucks for hotel delivery\\n- **46319** — Wholesale other food — if you expand to herbs, spices, condiments\\n- **01130** — Growing of vegetables — if you vertically integrate into direct farm ownership",
    zantaraOpener:
      "Wholesale vegetables for Bali's hotel kitchens? 46313 is NIB-only, auto-issued. Domestic supply handles the basics — your PMA value is in imported specialty vegetables and certified organic produce that Bedugul farmers can't provide. Cold chain and BPOM compliance are your two main operational gates.",
    tkaInfo: {
      categoryId: 7,
      categoryName: "Perdagangan Besar",
      totalInCategory: 198,
      iscoGroupsSelected: ["13", "24", "31"],
      selectedForThisCode: 8,
      selectionMethod: "ISCO-based",
      relevantPositions: [
        { titleEn: "Wholesale Trade Manager", titleId: "Manajer Perdagangan Besar", isco: "1324" },
        { titleEn: "Supply Chain Manager", titleId: "Manajer Rantai Pasokan", isco: "1324" },
        { titleEn: "General Manager", titleId: "Manajer Umum", isco: "1321" },
        { titleEn: "Procurement Specialist", titleId: "Spesialis Pengadaan", isco: "2421" },
        { titleEn: "Cold Chain Logistics Coordinator", titleId: "Koordinator Logistik Rantai Dingin", isco: "3339" },
        { titleEn: "Food Quality Inspector", titleId: "Inspektur Mutu Pangan", isco: "3119" },
        { titleEn: "Import Documentation Specialist", titleId: "Spesialis Dokumentasi Impor", isco: "3339" },
        { titleEn: "Organic Certification Specialist", titleId: "Spesialis Sertifikasi Organik", isco: "2421" }
      ],
      insight: "Kepmen 228/2019 lists 198 TKA-eligible positions in this category. Selection optimized using ISCO classification methodology.",
      keduaNote: "Directors and Commissioners who do NOT manage personalia can work without being listed in the jabatan.",
    },
},
'''

NEW_46314 = '''  "46314": {
    whatItMeans:
      "Wholesale of coffee, tea, and cacao — bulk buying and selling of coffee (raw green beans, roasted beans, ground coffee, or instant), tea (loose leaf, bagged, specialty), and cacao (raw beans, fermented, semi-processed, cocoa powder/butter) to roasters, cafes, manufacturers, exporters, hotels, and retail distributors. This is not a retail cafe (56301) or a coffee roastery (10720) — it is the wholesale distribution layer that moves product between producers, processors, and buyers at scale. Bali sits at the center of Indonesia's most internationally recognized coffee geography.",
    whatYouNeed:
      `**All scales**: Low risk (Rendah). NIB issued **automatically** (Otomatis). Authority: **OSS Pusat**.\\n\\n**Step-by-step for a PT PMA wholesale coffee/tea/cacao distributor:**\\n1. **PT PMA incorporation** — notary deed, AHU registration; trading sector minimum IDR 10B stated (~3–5 weeks)\\n2. **NIB via OSS** — register on oss.go.id, select 46314, Rendah path; auto-issued (1–3 days)\\n3. **API-U** — if importing specialty teas, Japanese/Taiwanese coffees, or specialty cacao: general import license from Kemendag\\n4. **BPOM MD/ML registration** — mandatory for any packaged coffee, tea, or cacao product with a food label sold to retail or F&B outlets. Green bean or unprocessed commodity trading does not require BPOM, but packaged retail-facing products do\\n5. **Phytosanitary certificate** (for green bean import/export) — required for agricultural commodity movement across borders; issued by origin country's plant health authority and inspected by Barantan\\n6. **Export documentation** (if exporting Bali coffee) — Pemberitahuan Ekspor Barang (PEB), Certificate of Origin (CoO from Disperindag), phytosanitary certificate for green beans. For Kintamani GI-protected coffees: can use EU GI designation on labels for European market\\n7. **Traceability certification** (optional but commercially important) — Rainforest Alliance (formerly UTZ), Fairtrade, 4C, USDA Organic increasingly required by European and US specialty coffee buyers. Budget IDR 50–200M for initial farm-group audit and certification\\n8. **STP Distributor/Agen** (optional) — Kemendag registration\\n9. **Laporan kegiatan usaha** — periodic business activity reports (ongoing obligation)\\n\\n**Typical total timeline:** 2–4 weeks from PT PMA to NIB.\\n**Minimum PT PMA capital:** IDR 10 billion stated capital (Rp 2.5B paid-up).\\n\\n**Authority:** OSS Pusat.\\n**PMA:** Fully open (Terbuka) — 100% foreign ownership.`,
    whatChanged:
      "Direct match from KBLI 2020 (MATCH_LANGSUNG). Wholesale coffee/tea/cacao classification is stable. The major development since 2020 is the explosive growth of Indonesia's specialty coffee export market — Kintamani arabica received EU Geographical Indication (GI) protection in 2022, the first Indonesian coffee to achieve this. Bali's craft cacao sector has also emerged significantly, driven by bean-to-bar chocolate brands sourcing from Jembrana and Buleleng.",
    baliContext:
      "**☕ Bali Coffee and Cacao (Indonesia's Premium Origin Story)**\\n\\n**Kintamani Arabica — Indonesia's first EU GI coffee:**\\n- Grown at 900–1,500m elevation around Lake Batur (Bangli Regency), Kintamani arabica received EU Geographical Indication protection in 2022 — the first Indonesian coffee with this designation\\n- Flavor profile: bright citrus acidity, medium body, floral notes — internationally competitive against Ethiopian and Guatemalan origins\\n- Farming: Subak Abian (water cooperative system), shade-grown, often processed as natural or honey\\n- Wholesale sourcing: direct from farmer cooperatives (Koperasi Petani Kintamani) or through established collectors; season peaks July–September\\n\\n**Other Bali origins worth knowing:**\\n- **Pupuan (Tabanan):** Robusta and arabica, 700–1,000m; full-bodied, used in espresso blends\\n- **Catur (Kintamani):** Village-specific micro-lot arabicas; increasingly sought by specialty importers for Japan/Korea/US\\n- **Nusa Penida:** Emerging small-batch origins on the island southeast of Bali\\n\\n**Bali's 200+ specialty cafes — the domestic B2B market:**\\n- Canggu, Seminyak, and Ubud have Indonesia's highest concentration of specialty (third-wave) coffee cafes per capita\\n- These cafes demand consistent single-origin and traceable lots — direct-trade models between wholesale distributor and cafe are standard at the premium end\\n- Bali's cafe scene imports Japanese-roast specialty coffees (light to medium), Ethiopian washed Yirgacheffe, Kenyan AA — supply these to the cafe sector is a legitimate wholesale model\\n\\n**Cacao — the craft chocolate opportunity:**\\n- Bali itself (Jembrana, Buleleng) and nearby Flores produce quality fermented cacao sought by European and US bean-to-bar chocolate makers\\n- Brands like Bali's Best Chocolate, Bali Chocolate, and international buyers (Raaka, Dandelion Chocolate) have established Bali/Flores cacao on the global craft chocolate map\\n- A wholesale cacao distributor sourcing from Jembrana cooperatives and exporting to Europe/US operates cleanly under 46314\\n\\n**Export angle:**\\n- Green bean coffee export from Bali is fully permissible. Kintamani beans command USD 6–12/kg FOB (vs USD 1.5–3/kg for generic Indonesian robusta)\\n- The GI designation allows premium positioning on European packaging — a significant commercial advantage\\n\\n**⚠ Traceability is now table stakes for premium buyers:**\\n- European Deforestation Regulation (EUDR, enforcement 2025) requires coffee importers to prove beans don't originate from deforested land. Bali's Subak Abian system and traceable farm cooperatives actually provide a strong compliance advantage",
    youllAlsoNeed:
      "- **56301** — Coffee/tea shop (cafe retail) — if you also operate a consumer-facing outlet\\n- **10720** — Coffee and tea processing/roasting — if you add roasting operations to your distribution\\n- **46319** — Wholesale other food/beverage — if you expand to spices, vanilla, or other commodities\\n- **01270** — Growing of beverage crops — if you invest in upstream farm ownership or long-term farm partnerships\\n- **46390** — Non-specialized wholesale food — if you broaden into a general F&B wholesale portfolio",
    zantaraOpener:
      "Wholesale coffee, tea, or cacao in Bali? 46314 is NIB-only, auto-issued. Kintamani arabica has EU GI protection — the first Indonesian coffee to get it. Bali's 200+ specialty cafes and growing craft cacao export market make this one of the most internationally connected commodity wholesale codes on the island.",
    tkaInfo: {
      categoryId: 7,
      categoryName: "Perdagangan Besar",
      totalInCategory: 198,
      iscoGroupsSelected: ["13", "24", "31"],
      selectedForThisCode: 9,
      selectionMethod: "ISCO-based",
      relevantPositions: [
        { titleEn: "Wholesale Trade Manager", titleId: "Manajer Perdagangan Besar", isco: "1324" },
        { titleEn: "Coffee and Commodity Sourcing Manager", titleId: "Manajer Pengadaan Kopi dan Komoditas", isco: "1324" },
        { titleEn: "General Manager", titleId: "Manajer Umum", isco: "1321" },
        { titleEn: "Export Documentation Specialist", titleId: "Spesialis Dokumentasi Ekspor", isco: "3339" },
        { titleEn: "Quality Grading Specialist", titleId: "Spesialis Grading Mutu", isco: "3119" },
        { titleEn: "Traceability and Certification Coordinator", titleId: "Koordinator Keterlacakan dan Sertifikasi", isco: "3339" },
        { titleEn: "Commodity Trading Analyst", titleId: "Analis Perdagangan Komoditas", isco: "2421" },
        { titleEn: "Supply Chain Coordinator", titleId: "Koordinator Rantai Pasokan", isco: "3339" },
        { titleEn: "Sustainability Officer", titleId: "Petugas Keberlanjutan", isco: "2429" }
      ],
      insight: "Kepmen 228/2019 lists 198 TKA-eligible positions in this category. Selection optimized using ISCO classification methodology.",
      keduaNote: "Directors and Commissioners who do NOT manage personalia can work without being listed in the jabatan.",
    },
},
'''

NEW_46315 = '''  "46315": {
    whatItMeans:
      "Wholesale of vegetable oils and fats — bulk buying and selling of cooking oil (minyak goreng), palm oil, coconut oil, olive oil, soybean oil, sunflower oil, and specialty culinary oils to retailers, food manufacturers, hotels, restaurants, and institutional buyers. Cooking oil (minyak goreng) is classified as a 'barang kebutuhan pokok' — a government-controlled essential commodity — placing wholesale distributors under the same monthly reporting and HET (price cap) obligations as rice wholesalers. Specialty oils (virgin coconut oil, olive oil, avocado oil) are outside the 'kebutuhan pokok' framework and are traded freely.",
    whatYouNeed:
      `**All scales**: Low risk (Rendah). NIB issued **automatically** (Otomatis). Authority: **OSS Pusat**.\\n\\n**Step-by-step for a PT PMA vegetable oil wholesale distributor:**\\n1. **PT PMA incorporation** — notary deed, AHU registration; trading sector minimum IDR 10B stated (~3–5 weeks)\\n2. **NIB via OSS** — register on oss.go.id, select 46315, Rendah path; auto-issued (1–3 days)\\n3. **STP Distributor/Agen** (optional) — Kemendag registration; required for participation in government-controlled cooking oil distribution programs (subsidi minyak goreng, operasi pasar)\\n4. **HET compliance (minyak goreng)** — government sets maximum retail prices for cooking oil (both premium and medium grades). Distributors must price within permitted margins; the 2021–2022 cooking oil crisis triggered aggressive enforcement including windfall tax on palm oil exports\\n5. **Laporan distribusi bulanan** — mandatory monthly distribution reports to Menteri Perdagangan for minyak goreng (as kebutuhan pokok). Non-reporting triggers license review\\n6. **API-U** — if importing oils (olive oil, specialty oils): general import license from Kemendag\\n7. **BPOM MD/ML registration** — mandatory for any packaged/branded cooking oil or specialty oil product sold to retail or F&B with a food label. Raw bulk palm oil for industrial use is exempt, but consumer-facing packaged oils require BPOM registration\\n8. **SNI compliance** — SNI 7709:2019 (refined cooking palm oil) and SNI 3741:2013 (cooking oil) are Indonesian national standards; packaged cooking oil for retail must comply\\n9. **Laporan kegiatan usaha** — periodic business activity reports (ongoing obligation)\\n\\n**Typical total timeline:** 2–4 weeks from PT PMA to NIB.\\n**Minimum PT PMA capital:** IDR 10 billion stated capital (Rp 2.5B paid-up).\\n\\n**Authority:** OSS Pusat.\\n**PMA:** Fully open (Terbuka) — 100% foreign ownership.`,
    whatChanged:
      "Direct match from KBLI 2020 (MATCH_LANGSUNG). The most significant development since 2020 is Indonesia's 2021–2022 cooking oil crisis — a global palm oil supply shock combined with domestic hoarding caused a severe shortage and government intervention including export bans (January–May 2022) and aggressive price cap enforcement. The crisis has permanently intensified regulatory scrutiny on cooking oil distributors.",
    baliContext:
      "**🫙 Vegetable Oil Wholesale in Bali (Two Very Different Markets)**\\n\\n**Market 1 — Minyak goreng (cooking oil): high-volume, tightly regulated:**\\n- Every warung, restaurant, and hotel kitchen in Bali uses cooking oil daily. The 8,000+ F&B establishments in Bali represent a steady, captive volume market\\n- This market is dominated by established FMCG distribution networks (Bimoli, Sania, Filma distributed through Indomaret/Alfamart wholesalers)\\n- PMA competing directly in mass-market cooking oil distribution faces strong incumbents and very thin margins under HET\\n\\n**Market 2 — Specialty and premium oils (the PMA opportunity):**\\n\\n**Virgin Coconut Oil (VCO) — Bali's premium export:**\\n- Bali and neighboring Lombok/NTB produce significant quantities of VCO from local coconut farms\\n- VCO for export (US, Europe, Australia) is a legitimate 46315 wholesale operation. Indonesian VCO is in global demand for: food manufacturing, cosmetic ingredients, dietary supplement\\n- Export angle: VCO producers in Tabanan and Buleleng sell through wholesale distributors. PMA wholesale company as the export-facing entity = viable model\\n- Certifications demanded by Western buyers: USDA Organic, EU Organic, non-GMO verified, Fairtrade\\n\\n**Olive oil import for hotel kitchens:**\\n- Bali's 200+ Italian restaurants and international hotel kitchens require imported olive oil (Spanish, Italian, Greek)\\n- A specialized importer/wholesaler serving the hotel procurement corridor is a clean niche. No HET constraints, higher margins, B2B relationship-driven\\n\\n**Specialty culinary oils:**\\n- Truffle oil, avocado oil, walnut oil, sesame oil (Japanese-grade) for luxury hotel restaurants — imported exclusively, commanding significant margins\\n\\n**⚠ Cooking oil crisis aftermath:**\\n- Post-2022, the Indonesian government has maintained heightened surveillance of minyak goreng distribution chains\\n- Distributors are required to register with the SIMIRAH (Sistem Informasi Minyak Goreng Curah) tracking system for bulk cooking oil distribution\\n- Any distributor found accumulating stock beyond permitted levels during shortage conditions faces immediate government action",
    youllAlsoNeed:
      "- **46319** — Wholesale other food — if you expand to condiments, sauces, or other packaged food products\\n- **46311** — Wholesale rice — natural complement for kebutuhan pokok distribution portfolio\\n- **10431** — Vegetable oil refining/processing — if you vertically integrate into processing\\n- **46590** — Wholesale of other non-food — if your distribution includes packaging materials\\n- **52292** — Dry warehousing — if you operate dedicated storage for bulk oil containers",
    zantaraOpener:
      "Wholesale vegetable oil in Bali? 46315 covers everything from mass-market cooking oil to premium VCO and imported olive oil. Minyak goreng is a kebutuhan pokok with HET price caps and monthly reports. The PMA angle: VCO export and specialty imported oils for hotel kitchens, where HET doesn't apply.",
    tkaInfo: {
      categoryId: 7,
      categoryName: "Perdagangan Besar",
      totalInCategory: 198,
      iscoGroupsSelected: ["13", "24", "31"],
      selectedForThisCode: 8,
      selectionMethod: "ISCO-based",
      relevantPositions: [
        { titleEn: "Wholesale Trade Manager", titleId: "Manajer Perdagangan Besar", isco: "1324" },
        { titleEn: "Supply Chain Manager", titleId: "Manajer Rantai Pasokan", isco: "1324" },
        { titleEn: "General Manager", titleId: "Manajer Umum", isco: "1321" },
        { titleEn: "Procurement Specialist", titleId: "Spesialis Pengadaan", isco: "2421" },
        { titleEn: "Distribution Coordinator", titleId: "Koordinator Distribusi", isco: "3339" },
        { titleEn: "Food Quality Inspector", titleId: "Inspektur Mutu Pangan", isco: "3119" },
        { titleEn: "Export Documentation Specialist", titleId: "Spesialis Dokumentasi Ekspor", isco: "3339" },
        { titleEn: "Commodity Compliance Officer", titleId: "Petugas Kepatuhan Komoditas", isco: "2421" }
      ],
      insight: "Kepmen 228/2019 lists 198 TKA-eligible positions in this category. Selection optimized using ISCO classification methodology.",
      keduaNote: "Directors and Commissioners who do NOT manage personalia can work without being listed in the jabatan.",
    },
},
'''

NEW_46319 = '''  "46319": {
    whatItMeans:
      "Wholesale of other agricultural food and beverage products — the catch-all code for wholesale trading of agricultural food/beverage commodities not classified under the specific codes 46311–46315. In practice, this covers: spices (vanilla, cloves, nutmeg, pepper, cinnamon, cardamom), honey and bee products, dried legumes (lentils, dried beans, chickpeas), seeds and grains (quinoa, chia, specialty grains), herbs (fresh and dried), condiments, and specialty beverage ingredients. It also covers bulk commodity trading of products like vanilla beans, dried coconut, and palm sugar. If your wholesale food/beverage product doesn't fit neatly into rice, fruit, vegetable, coffee/tea, or oil — this is the code.",
    whatYouNeed:
      `**All scales**: Low risk (Rendah). NIB issued **automatically** (Otomatis). Authority: **OSS Pusat**.\\n\\n**Step-by-step for a PT PMA specialty food wholesale distributor:**\\n1. **PT PMA incorporation** — notary deed, AHU registration; trading sector minimum IDR 10B stated (~3–5 weeks)\\n2. **NIB via OSS** — register on oss.go.id, select 46319, Rendah path; auto-issued (1–3 days)\\n3. **API-U** — if importing specialty ingredients (truffles, saffron, specialty vinegar, Japanese condiments): general import license from Kemendag\\n4. **BPOM MD/ML registration** — mandatory for any packaged product with a food label sold to retail or F&B:\\n   - **MD** (Made in Indonesia): for domestically produced packaged foods\\n   - **ML** (Made in foreign country): for imported packaged foods\\n   - Raw commodity (bulk spices, unpackaged) does not require BPOM MD/ML, but any packaged retail-facing product does\\n5. **Halal certification (MUI)** — increasingly demanded by major hotel chains for all F&B supplies. The October 2024 halal certification deadline for food/beverage manufacturers means your suppliers' products must already have halal status. Verify halal status of all imported products before proposing to hotel procurement\\n6. **Phytosanitary compliance** (for plant-based agricultural products) — dried spices, herbs, seeds imported from overseas require phytosanitary certificates and Barantan inspection\\n7. **CITES documentation** (if applicable) — some natural ingredients (certain orchids, specialty woods) may require CITES permits. Verify for each product category\\n8. **STP Distributor/Agen** (optional) — Kemendag registration\\n9. **Laporan kegiatan usaha** — periodic business activity reports (ongoing obligation)\\n\\n**Typical total timeline:** 2–4 weeks from PT PMA to NIB.\\n**Minimum PT PMA capital:** IDR 10 billion stated capital (Rp 2.5B paid-up).\\n\\n**Authority:** OSS Pusat.\\n**PMA:** Fully open (Terbuka) — 100% foreign ownership.`,
    whatChanged:
      "Direct match from KBLI 2020 (MATCH_LANGSUNG). This catch-all wholesale code is stable. Key developments since 2020: Indonesia's mandatory halal certification law (UU No. 33/2014) reached its first major deadline for food/beverage products in October 2024, requiring MUI halal certification for virtually all food products sold in Indonesia. This directly affects imported specialty ingredient distributors under 46319.",
    baliContext:
      "**🌿 Specialty Food Wholesale in Bali (The Spice Heritage and Modern Premium Market)**\\n\\n**Indonesia's spice legacy:**\\n- Indonesia was the world's original spice island — and it remains the world's largest producer of several key commodities:\\n  - **Cloves (cengkeh):** Maluku and Sulawesi; used in kretek cigarettes, medicine, and cooking\\n  - **Nutmeg (pala):** Banda Islands; Banda nutmeg is the original variety that sparked European colonial expansion\\n  - **Pepper (lada):** Bangka, Lampung; Indonesia is the world's 2nd largest pepper producer\\n  - **Vanilla (vanili):** Flores and Papua increasingly produce premium vanilla; Flores vanilla is comparable to Madagascar grade\\n  - **Cinnamon (kayu manis):** Sumatra padang cassia; distinct from Ceylon cinnamon\\n\\n**Bali as distribution hub:**\\n- Pasar Badung (Denpasar's central market) is a regional hub for spice wholesale — supplying Bali's F&B sector and connecting to export\\n- Hotel supply chain: premium spice packs (Balinese spice paste — jamu, base genep) supplied to hotel kitchens for authentic Balinese cuisine programs\\n- Export: dried vanilla beans from Flores distributed through Bali-based exporters; Bali has a small vanilla trading community\\n\\n**Luxury hotel kitchen supply (the PMA niche):**\\n- 5-star hotel executive chefs require specialty ingredients not available in domestic markets:\\n  - **Truffles** (black Périgord, white Alba) — imported from France/Italy during season; regular buyers at 5-star restaurants in Bali\\n  - **Saffron** — Iranian and Spanish; consumed by Middle Eastern restaurant outlets in luxury hotels\\n  - **Specialty vinegars** — aged balsamic (Modena DOP), sherry vinegar for European kitchen programs\\n  - **Japanese condiments** — dashi kombu, mirin (real brewed), ponzu — for Japanese restaurant programs\\n  - **Specialty salts** — Himalayan pink, Fleur de Sel, Maldon sea salt for fine dining\\n\\n**Halal compliance — increasingly non-negotiable:**\\n- Major hotel chains (Marriott, Hilton, Accor) have centralized halal compliance requirements for all F&B supplies\\n- The October 2024 MUI halal certification deadline means that any supplier to these chains must already have halal-certified products or face delisting from procurement approved lists\\n- Imported products: halal status from origin country's recognized certification body (MUI-accepted list) is required — not all foreign halal certifiers are accepted by MUI",
    youllAlsoNeed:
      "- **46314** — Wholesale coffee/tea/cacao — natural complement if you also carry beverage commodities\\n- **46312** — Wholesale fruits — if your specialty food range includes dried fruits or fresh exotic fruits\\n- **46315** — Wholesale vegetable oils — if you also carry specialty culinary oils\\n- **10750** — Food condiment manufacturing — if you also process raw spices into packaged spice blends\\n- **46390** — Non-specialized food wholesale — if you broaden into a full general F&B wholesale portfolio",
    zantaraOpener:
      "Specialty spice, vanilla, honey, or imported premium ingredient wholesale in Bali? 46319 is your code — NIB-only, auto-issued. The halal certification requirement from October 2024 is your biggest compliance gate. Indonesia's spice heritage and Bali's luxury hotel kitchen demand make this one of the most internationally interesting wholesale niches on the island.",
    tkaInfo: {
      categoryId: 7,
      categoryName: "Perdagangan Besar",
      totalInCategory: 198,
      iscoGroupsSelected: ["13", "24", "31"],
      selectedForThisCode: 8,
      selectionMethod: "ISCO-based",
      relevantPositions: [
        { titleEn: "Wholesale Trade Manager", titleId: "Manajer Perdagangan Besar", isco: "1324" },
        { titleEn: "Supply Chain Manager", titleId: "Manajer Rantai Pasokan", isco: "1324" },
        { titleEn: "General Manager", titleId: "Manajer Umum", isco: "1321" },
        { titleEn: "Procurement Specialist", titleId: "Spesialis Pengadaan", isco: "2421" },
        { titleEn: "Import Documentation Specialist", titleId: "Spesialis Dokumentasi Impor", isco: "3339" },
        { titleEn: "Food Quality and Halal Compliance Inspector", titleId: "Inspektur Mutu Pangan dan Kepatuhan Halal", isco: "3119" },
        { titleEn: "Commodity Trading Analyst", titleId: "Analis Perdagangan Komoditas", isco: "2421" },
        { titleEn: "Export Specialist", titleId: "Spesialis Ekspor", isco: "3339" }
      ],
      insight: "Kepmen 228/2019 lists 198 TKA-eligible positions in this category. Selection optimized using ISCO classification methodology.",
      keduaNote: "Directors and Commissioners who do NOT manage personalia can work without being listed in the jabatan.",
    },
},
'''

HERO_IMAGES_BLOCK = '''  "46311": {
    src: "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=1600&q=80&auto=format",
    alt: "Rice sacks wholesale grain storage warehouse distribution",
    overlay: "linear-gradient(135deg, rgba(20,18,8,0.70) 0%, rgba(38,35,12,0.53) 50%, rgba(20,18,8,0.70) 100%)",
  },
  "46312": {
    src: "https://images.unsplash.com/photo-1601004890684-d8cbf643f5f2?w=1600&q=80&auto=format",
    alt: "Fresh tropical fruits wholesale market colorful abundance",
    overlay: "linear-gradient(135deg, rgba(20,10,5,0.68) 0%, rgba(38,18,8,0.52) 50%, rgba(20,10,5,0.68) 100%)",
  },
  "46313": {
    src: "https://images.unsplash.com/photo-1540420773420-3366772f4999?w=1600&q=80&auto=format",
    alt: "Fresh vegetables wholesale market produce distribution",
    overlay: "linear-gradient(135deg, rgba(8,20,5,0.68) 0%, rgba(12,38,8,0.52) 50%, rgba(8,20,5,0.68) 100%)",
  },
  "46314": {
    src: "https://images.unsplash.com/photo-1447933601403-0c6688de566e?w=1600&q=80&auto=format",
    alt: "Coffee beans wholesale roastery Bali Kintamani arabica",
    overlay: "linear-gradient(135deg, rgba(25,15,5,0.72) 0%, rgba(45,28,8,0.55) 50%, rgba(25,15,5,0.72) 100%)",
  },
  "46315": {
    src: "https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=1600&q=80&auto=format",
    alt: "Vegetable oil coconut oil wholesale bottles distribution",
    overlay: "linear-gradient(135deg, rgba(20,18,5,0.70) 0%, rgba(38,35,8,0.53) 50%, rgba(20,18,5,0.70) 100%)",
  },
  "46319": {
    src: "https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=1600&q=80&auto=format",
    alt: "Indonesian spices wholesale market vanilla cinnamon cloves",
    overlay: "linear-gradient(135deg, rgba(25,15,5,0.70) 0%, rgba(45,28,8,0.53) 50%, rgba(25,15,5,0.70) 100%)",
  },
'''

# ============================================================
# 1. Replace existing 46314 stub with new content
# ============================================================
start46314 = content.find('  "46314": {')
if start46314 < 0:
    print("ERROR: 46314 not found")
    exit(1)
end46314 = find_entry_end(content, start46314)
print(f"46314 old entry: line {content[:start46314].count(chr(10))+1}, length {end46314-start46314}")
content = content[:start46314] + NEW_46314 + content[end46314:]
print(f"46314 replaced. Lines: {len(content.split(chr(10)))}")

# ============================================================
# 2. Insert 5 new entries before closing };
# ============================================================
NEW_5_ENTRIES = '\n'.join([NEW_46311, NEW_46312, NEW_46313, NEW_46315, NEW_46319])

lines = content.split('\n')
close_idx = None
for i in range(len(lines)-1, 0, -1):
    if lines[i].strip() == '};':
        close_idx = i
        break

if close_idx is None:
    print("ERROR: Could not find closing };")
    exit(1)

print(f"Inserting 5 new entries before line {close_idx+1}")
lines.insert(close_idx, '\n  // ---------------------------------------------------------------------------\n  // Wholesale Food & Grocery (46xxx)\n  // ---------------------------------------------------------------------------\n\n' + NEW_5_ENTRIES)
content = '\n'.join(lines)
print(f"After inserting: {len(content.split(chr(10)))} lines")

# ============================================================
# 3. Write updated gold content
# ============================================================
with open('lib/kbli-gold-content.ts', 'w') as f:
    f.write(content)
print("✓ lib/kbli-gold-content.ts written")

# ============================================================
# 4. Add hero images to page.tsx
# ============================================================
hero_start = page.find('const GOLD_HERO_IMAGES')
close_hero = page.find('\n};', hero_start)
print(f"GOLD_HERO_IMAGES closes at pos {close_hero}")
print(f"Context before close: ...{page[close_hero-60:close_hero+3]}")
page = page[:close_hero + 1] + HERO_IMAGES_BLOCK + '};\n' + page[close_hero + 4:]

with open('app/kbli/[code]/page.tsx', 'w') as f:
    f.write(page)
print("✓ app/kbli/[code]/page.tsx written")

print(f"\nDone. lib: {len(content.split(chr(10)))} lines  page: {len(page.split(chr(10)))} lines")
