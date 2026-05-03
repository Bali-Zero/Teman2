#!/usr/bin/env python3
"""Apply Session 08 gold content updates — 6 Transport/Logistics/Tourism KBLI codes"""

with open('lib/kbli-gold-content.ts', 'r') as f:
    content = f.read()

with open('app/kbli/[code]/page.tsx', 'r') as f:
    page = f.read()

print(f"Starting: {len(content.split(chr(10)))} lines in gold content")

# ============================================================
# NEW ENTRIES — 6 transport/logistics/tourism codes
# ============================================================

NEW_6_ENTRIES = '''
  // ---------------------------------------------------------------------------
  // Transport, Logistics & Tourism (49xxx, 52xxx, 77xxx, 79xxx, 82xxx)
  // ---------------------------------------------------------------------------

  "49213": {
    whatItMeans:
      "Urban passenger transport — operating scheduled or chartered buses, minibuses, and shuttle services within and between cities. This includes: city buses and urban transit, airport shuttle services, resort/hotel charter transfers, and inter-city regular routes (AKDP — Antar Kota Dalam Provinsi). The code covers the vehicle operation business itself, whether scheduled (trayek) or unscheduled (non-trayek) charter. Critical PMA distinction: the ride-hailing app model (Gojek, Grab, InDriver for ride orders via app) is explicitly reserved for Indonesian MSMEs and cannot be operated by a PT PMA. The PMA-accessible opportunity is the transport operation itself — charter fleets, shuttle services, hotel/resort transfers, and formal bus routes.",
    whatYouNeed:
      `**All scales**: Low risk (Rendah). NIB issued **automatically** (Otomatis). Authority: **Bupati/Walikota**.\\n\\nThe NIB is auto-issued, but actual operations require additional transport-specific permits:\\n\\n**Step-by-step for a PT PMA urban/charter transport operator:**\\n1. **PT PMA incorporation** — notary deed, AHU registration; transport sector minimum IDR 10B stated (~3–5 weeks)\\n2. **NIB via OSS** — register on oss.go.id, select 49213, Rendah path; auto-issued (1–3 days)\\n3. **Izin Usaha Angkutan** — operational transport license from Dinas Perhubungan Kabupaten/Kota; requires vehicle list (STNK), driver credentials, operational base (pool/garasi)\\n4. **Izin Trayek** (for fixed routes) — route permit from Dishub if operating scheduled routes between specific points. Bali routes (Denpasar–Ubud, Denpasar–Canggu, airport shuttles) require route-specific permits\\n5. **KIR (Uji Berkala Kendaraan Bermotor)** — roadworthiness test mandatory every **6 months** for all commercial passenger vehicles. Performed at Dishub balai uji; vehicles without valid KIR cannot legally operate\\n6. **STNK atas nama PT** — all fleet vehicles must be registered under the PT PMA name\\n7. **Asuransi Jasa Raharja** — mandatory passenger liability insurance (automatically included for registered vehicles)\\n8. **Driver AKAP/AKDP competency** — drivers on inter-city routes require specific Dishub certification\\n9. **Laporan operasi berkala** — periodic operational reports to Dishub\\n\\n**For AKAP routes (inter-provincial, e.g. Bali to Java):**\\n- Additional **Izin Usaha Angkutan AKAP** from Kementerian Perhubungan (Menteri level)\\n- Bali–Java ferry coordination (ASDP Indonesia Ferry) for Bali–Ketapang (Banyuwangi) crossing\\n\\n**Typical total timeline:** 2–4 months from PT PMA to first legally operating vehicle.\\n**Minimum PT PMA capital:** IDR 10 billion stated capital (Rp 2.5B paid-up).\\n\\n**PMA note:** Ride-hailing apps (Gojek, Grab, InDriver passenger model) are **TERTUTUP** for PMA — reserved for Indonesian UMKM. PMA can operate the vehicles and drivers but cannot build/operate the consumer ride-hailing app platform for passengers.\\n\\n**Authority:** Bupati/Walikota.\\n**PMA:** Fully open (Terbuka) — 100% foreign ownership (for charter/shuttle operations).`,
    whatChanged:
      "Direct match from KBLI 2020 (MATCH_LANGSUNG). Urban transport classification is stable. PP 28/2025 adds the formal OSS pathway; KIR and trayek requirements are governed by UU LLAJ 22/2009 and are unchanged.",
    baliContext:
      "**🚌 Bali Transport: The Real PMA Opportunity**\\n- The mass ride-hailing market (Gojek, Grab) is UMKM territory — PMA cannot operate a competing app\\n- The actual PMA opportunity is in **organized charter and shuttle operations** serving the tourism economy\\n\\n**High-demand corridors (2025):**\\n- **Airport–Canggu / Airport–Seminyak:** Kuta taxis still dominate but corporate shuttle contracts for hotels are underserved\\n- **Denpasar–Ubud:** One of the most traveled tourist routes; no quality scheduled service with Western UX exists\\n- **Resort shuttle circuits:** Large Nusa Dua and Uluwatu resorts pay IDR 2–4M/day for dedicated charter vehicles\\n- **AKAP Bali–Surabaya / Bali–Malang:** Long-haul overnight coaches via Ketapang ferry; underserved quality tier\\n\\n**EV fleet opportunity:**\\n- Government incentives for electric commercial vehicles (2024 Perpres 55/2019 and amendments)\\n- An EV shuttle fleet (Tesla vans are too expensive; Hiace/BYD electric conversions are feasible) serving premium Bali hotels is a genuine white space\\n\\n**ITDP/BRT tender:**\\n- Bali Provincial Government has received World Bank/ITDP support for Bus Rapid Transit planning. Formal tender processes for BRT operation could open B2G opportunities for PMA transport companies\\n\\n**⚠ KIR is real enforcement:**\\n- Dishub does conduct roadside checks in Bali, especially in peak season (July–August, December)\\n- Expired KIR = vehicle impounded. 6-month cycle is non-negotiable for commercial operators",
    youllAlsoNeed:
      "- **49231** — Freight transport by road — if you also carry goods for hotels/resorts alongside passengers\\n- **77100** — Vehicle rental (self-drive) — if you also offer undriven vehicle hire\\n- **79110** — Travel agency / biro perjalanan wisata — if you bundle transport within tour packages\\n- **49214** — Special shuttle transport (AKAP) — if you operate inter-provincial scheduled routes\\n- **52219** — Other transport support activities — if you add dispatch/coordination services",
    zantaraOpener:
      "Charter shuttle service, hotel transfers, or organized transport in Bali? 49213 gives you the NIB automatically — but don't overlook KIR every 6 months, Izin Trayek for fixed routes, and the PMA restriction on ride-hailing apps. Let me map out the right structure.",
    tkaInfo: {
      categoryId: 17,
      categoryName: "Transportasi & Pergudangan",
      totalInCategory: 152,
      iscoGroupsSelected: ["13", "31", "83"],
      selectedForThisCode: 8,
      selectionMethod: "ISCO-based",
      relevantPositions: [
        { titleEn: "Transport Operations Manager", titleId: "Manajer Operasional Transportasi", isco: "1324" },
        { titleEn: "Fleet Manager", titleId: "Manajer Armada", isco: "1324" },
        { titleEn: "General Manager", titleId: "Manajer Umum", isco: "1321" },
        { titleEn: "Safety and Compliance Manager", titleId: "Manajer Keselamatan dan Kepatuhan", isco: "1324" },
        { titleEn: "Transport Logistics Coordinator", titleId: "Koordinator Logistik Transportasi", isco: "3339" },
        { titleEn: "Vehicle Maintenance Supervisor", titleId: "Supervisor Perawatan Kendaraan", isco: "3115" },
        { titleEn: "Route Planning Specialist", titleId: "Spesialis Perencanaan Rute", isco: "3339" },
        { titleEn: "Driver Trainer", titleId: "Pelatih Pengemudi", isco: "3359" }
      ],
      insight: "Kepmen 228/2019 lists 152 TKA-eligible positions in this category. Selection optimized using ISCO classification methodology.",
      keduaNote: "Directors and Commissioners who do NOT manage personalia can work without being listed in the jabatan.",
    },
},

  "49231": {
    whatItMeans:
      "General cargo road freight — operating trucks and commercial vehicles to transport non-specialized goods by road for third-party clients. This covers: trucking companies, last-mile delivery for B2B clients, hotel and resort supply chain distribution, construction materials haulage, and general merchandise distribution. The defining characteristic is 'barang umum' (general goods) — contrast with 49239 which covers specialized cargo (liquids, hazardous materials, refrigerated goods, heavy equipment). If you move general dry goods by road for payment, this is the code.",
    whatYouNeed:
      `**Scale-dependent licensing in PP 28/2025:**\\n\\n**Kecil (Small fleet):** Medium-Low risk (Menengah Rendah). NIB + Sertifikat Standar. Authority: **Bupati/Walikota**. Processing: **7 working days**.\\n**Besar (Large fleet / inter-provincial):** Medium-Low risk (Menengah Rendah). NIB + Sertifikat Standar. Authority: **Menteri** (Kementerian Perhubungan). Processing: **7 working days**.\\n\\n**Step-by-step for a PT PMA general freight operator:**\\n1. **PT PMA incorporation** — notary deed, AHU registration; logistics sector minimum IDR 10B stated (~3–5 weeks)\\n2. **NIB via OSS** — register on oss.go.id, select 49231, Menengah Rendah path (~3 days)\\n3. **Izin Usaha Angkutan Barang** — freight transport business license from Dinas Perhubungan Kabupaten/Kota (Kecil) or Kementerian Perhubungan (Besar); documents: STNK fleet list, garansi pool address, NPWP\\n4. **KIR (Uji Berkala Kendaraan Bermotor)** — mandatory vehicle roadworthiness test every **6 months** for all commercial freight vehicles. This is an ongoing operational compliance item — each vehicle has its own KIR schedule. Expired KIR = vehicle cannot legally haul cargo\\n5. **SNI marking verification** — commercial vehicles must use SNI-compliant tires (SNI 1811), brakes, and structural components. When purchasing trucks, verify SNI compliance on key components before putting vehicles into commercial service\\n6. **Surat Jalan** — cargo manifest / delivery letter required for every shipment, documenting origin, destination, cargo type, weight, and vehicle details\\n7. **STNK atas nama PT** — fleet vehicles registered under PT PMA\\n8. **AKAP barang permit** (if crossing provincial borders) — inter-provincial freight requires additional Izin Usaha Angkutan Barang AKAP from Kementerian Perhubungan. Bali–Java crossings (via Ketapang ferry) require this\\n9. **Asuransi kargo** — cargo insurance per shipment; required by most B2B clients\\n10. **Laporan kegiatan usaha** — periodic operational reports (ongoing obligation)\\n\\n**Typical total timeline:** 2–4 months from PT PMA to operational fleet.\\n**Minimum PT PMA capital:** IDR 10 billion stated capital (Rp 2.5B paid-up).\\n\\n**Authority:** Bupati/Walikota (Kecil) · Menteri Perhubungan (Besar/AKAP).\\n**PMA:** Fully open (Terbuka) — 100% foreign ownership.`,
    whatChanged:
      "Direct match from KBLI 2020 (MATCH_LANGSUNG). General road freight is a stable, consistently regulated category. PP 28/2025 formalizes the OSS pathway; KIR and SNI compliance requirements are governed by UU LLAJ 22/2009 and BSNI standards respectively, both predating this regulation.",
    baliContext:
      "**🚛 Road Freight in Bali (Stable B2B Market)**\\n- Bali's logistics market is entirely B2B-driven: there is no large-scale consumer parcel delivery market (that's dominated by JNE/J&T/SiCepat through national networks)\\n- The real opportunity is **dedicated B2B supply chain** serving Bali's hospitality and construction sectors\\n\\n**Hotel and resort supply chain:**\\n- Bali has 4,000+ hotels and 10,000+ villas — each requiring daily/weekly deliveries of F&B supplies, linen, amenities, and maintenance materials\\n- Most large resort groups (Marriott, Hilton, Accor) source from Java-based suppliers; last-mile from Ketapang ferry port to the resort is frequently unreliable\\n- A dedicated 3PL (third-party logistics) company with reliable trucks, temperature-aware dry storage, and hotel-trained drivers is genuinely underserved\\n\\n**Construction haulage:**\\n- Bali's ongoing construction boom (villas, hotels, roads) requires constant movement of building materials. Sand, gravel, steel, and prefab elements from Java via Ketapang are a steady revenue stream\\n\\n**Bali–Java corridor:**\\n- The ASDP ferry (Ketapang–Gilimanuk) is the chokepoint for all surface freight in and out of Bali\\n- Ferry capacity is limited; peak season (July–August, December) creates severe backlogs\\n- A company with pre-booked ferry slots (via ASDP account) has a significant operational advantage\\n\\n**⚠ KIR every 6 months — operational discipline required**\\n- KIR is not a one-time step. Every commercial vehicle has its own 6-month KIR expiry cycle\\n- With a fleet of 10 trucks, you're managing 10 separate KIR schedules\\n- Fleet management software or a dedicated compliance coordinator is essential\\n- Dishub does conduct spot checks on major roads (bypass Ngurah Rai, Sunset Road, etc.)",
    youllAlsoNeed:
      "- **52292** — Non-refrigerated warehousing — if you add dry storage to your logistics offering\\n- **49239** — Specialized cargo transport — if you expand to refrigerated/hazardous/liquid cargo\\n- **52219** — Other transport support activities — if you add dispatch coordination or freight brokerage\\n- **46599** — Wholesale distribution — if you also take ownership of goods in the distribution chain\\n- **49213** — Urban passenger transport — if your fleet also does passenger charter alongside freight",
    zantaraOpener:
      "Freight trucking business in Bali? 49231 is the code — Medium-Low risk, Sertifikat Standar required. The non-negotiable: KIR every 6 months per vehicle. Miss it and your trucks are grounded. Let me show you the full compliance path.",
    tkaInfo: {
      categoryId: 17,
      categoryName: "Transportasi & Pergudangan",
      totalInCategory: 152,
      iscoGroupsSelected: ["13", "31", "83"],
      selectedForThisCode: 8,
      selectionMethod: "ISCO-based",
      relevantPositions: [
        { titleEn: "Logistics Operations Manager", titleId: "Manajer Operasional Logistik", isco: "1324" },
        { titleEn: "Fleet Manager", titleId: "Manajer Armada", isco: "1324" },
        { titleEn: "General Manager", titleId: "Manajer Umum", isco: "1321" },
        { titleEn: "Supply Chain Coordinator", titleId: "Koordinator Rantai Pasokan", isco: "3339" },
        { titleEn: "Transport Safety Officer", titleId: "Petugas Keselamatan Transportasi", isco: "3339" },
        { titleEn: "Customs and Documentation Specialist", titleId: "Spesialis Kepabeanan dan Dokumentasi", isco: "3339" },
        { titleEn: "Vehicle Maintenance Engineer", titleId: "Teknisi Perawatan Kendaraan", isco: "3115" },
        { titleEn: "Warehouse Supervisor", titleId: "Supervisor Gudang", isco: "4321" }
      ],
      insight: "Kepmen 228/2019 lists 152 TKA-eligible positions in this category. Selection optimized using ISCO classification methodology.",
      keduaNote: "Directors and Commissioners who do NOT manage personalia can work without being listed in the jabatan.",
    },
},

  "52292": {
    whatItMeans:
      "Non-refrigerated warehousing and storage — operating dry goods warehouses for third-party clients, providing storage space, inventory management, and logistics handling for general merchandise that does not require controlled temperature. This covers: third-party logistics (3PL) warehousing, general merchandise storage, bonded warehouses (Gudang Berikat — under Bea Cukai supervision for imported goods), and supply chain storage for hotels, resorts, and retail. The defining feature: the goods don't need refrigeration. Contrast with 52291 (cold storage / refrigerated warehousing).",
    whatYouNeed:
      `**Single scale in PP 28/2025 data**: Medium-High risk (Menengah Tinggi). NIB + Izin required — **not automatic**. Issued by **Bupati/Walikota** within **5 working days**.\\n\\n**Step-by-step for a PT PMA non-refrigerated warehouse operator:**\\n1. **PT PMA incorporation** — notary deed, AHU registration; logistics/warehousing sector minimum IDR 10B stated (~3–5 weeks)\\n2. **NIB via OSS** — register on oss.go.id, select 52292, Menengah Tinggi path (~3 days)\\n3. **IMB/PBG (Persetujuan Bangunan Gedung)** — building permit for the warehouse structure from DPMPTSP Kabupaten; documents: site plan, architectural drawings, structural calculations. New warehouses: 4–12 weeks. Existing licensed buildings: verify PBG is current\\n4. **KKPR** (Kesesuaian Kegiatan Pemanfaatan Ruang) — spatial/zoning conformity; warehouse must be in an area zoned for industrial/logistics use. Kawasan industri (Mengwi, Mambal, Pesiapan) are pre-zoned; greenfield sites outside industrial zones require KKPR check\\n5. **Izin Gudang** — warehouse operating license from Dinas Perindustrian dan Perdagangan (Disperindag) Kabupaten; documents: PBG, SKMHT (building ownership), company profile, floor plan\\n6. **Izin from Bupati/Walikota via OSS** — issued within 5 working days after IMB/PBG and Izin Gudang clearance\\n7. **Laporan stok berkala** — mandatory monthly stock reporting to Disperindag for certain commodity categories (rice, sugar, cooking oil, and other strategically regulated goods). If you store these commodities, monthly reporting is non-negotiable\\n8. **Gudang Berikat license** (if storing imported goods pre-customs clearance) — from Bea Cukai; additional process but opens significant B2B opportunity\\n9. **Fire safety compliance** — APAR (fire extinguisher) density, hydrant system, and evacuation plan per Permenaker 04/1980; inspected by Dinas Pemadam Kebakaran\\n10. **Laporan kegiatan usaha** — periodic business activity reports (ongoing obligation)\\n\\n**Typical total timeline:** 3–6 months from PT PMA to operational warehouse (driven primarily by PBG timeline for new construction).\\n**Minimum PT PMA capital:** IDR 10 billion stated capital (Rp 2.5B paid-up).\\n\\n**Authority:** Bupati/Walikota.\\n**PMA:** Fully open (Terbuka) — 100% foreign ownership.`,
    whatChanged:
      "Direct match from KBLI 2020 (MATCH_LANGSUNG). Non-refrigerated warehousing is a stable category. PP 28/2025 formalizes the OSS pathway; the IMB→PBG transition (2021) is the most significant procedural change, replacing the old IMB with the new PBG framework.",
    baliContext:
      "**📦 Bali's Warehousing Gap (Real Market Opportunity)**\\n- Bali has a significant deficit of modern, Class A warehousing. The island has traditionally relied on Java-based warehousing, with goods shipped across the Ketapang–Gilimanuk strait to order\\n- **Why this matters:** Bali's 4,000+ hotels, 10,000+ villas, and hundreds of restaurants place daily orders for F&B supplies, amenities, cleaning products, and linens — most of which are sourced from Surabaya or Jakarta distributors\\n- A local 3PL operator with quality dry storage, reliable inventory management software, and hotel-experienced staff can command premium contract rates\\n\\n**The hotel supply chain model:**\\n- A resort paying IDR 50–150M/month for F&B supply chain services is not unusual for a 5-star property\\n- Consolidating supply for 10–20 hotels into a single warehouse cuts their per-hotel logistics cost by 30–40%\\n- Adding a Gudang Berikat function (bonded warehouse) allows hotel clients to defer import duty on wine, spirits, and luxury food imports — a major selling point\\n\\n**Strategic zone: Mengwi / Mambal / Pesiapan**\\n- These Kabupaten Badung industrial zones have the best access to the airport, Kuta/Seminyak hotel corridor, and the Denpasar port\\n- Land lease rates (Hak Sewa): IDR 200–500M/year for 1,000–2,000m² warehouse\\n- Industrial zone pre-zoning means KKPR is streamlined\\n\\n**Combined model:**\\n- **52292 (dry) + 52291 (cold/refrigerated)** — full-service logistics for hotels requiring ambient-stored F&B (dry goods, packaged) and temperature-controlled goods (fresh produce, dairy, meat) in the same facility\\n\\n**⚠ Laporan stok is real compliance:**\\n- If you store government-regulated commodities (beras/rice, gula/sugar, minyak goreng/cooking oil, tepung), monthly stock reports to Disperindag are mandatory\\n- Non-reporting can trigger warehouse inspection and temporary suspension of Izin Gudang",
    youllAlsoNeed:
      "- **52291** — Cold storage warehousing — combine with 52292 for full-service F&B logistics\\n- **49231** — Road freight transport — if you also move goods between your warehouse and clients\\n- **52219** — Other transport support activities — if you add freight brokerage or dispatch services\\n- **46599** — Wholesale distribution — if you also take ownership of goods alongside storage\\n- **63991** — Other information services — if you offer supply chain visibility/tracking software as part of your 3PL package",
    zantaraOpener:
      "Warehousing and 3PL logistics in Bali? 52292 is the code — Medium-High risk, 5 working days from Bupati. PBG for the building and Izin Gudang are your two key gates. Bali genuinely lacks quality dry storage — if you can deliver hotel-grade 3PL, demand is there.",
    tkaInfo: {
      categoryId: 17,
      categoryName: "Transportasi & Pergudangan",
      totalInCategory: 152,
      iscoGroupsSelected: ["13", "31", "43"],
      selectedForThisCode: 8,
      selectionMethod: "ISCO-based",
      relevantPositions: [
        { titleEn: "Warehouse Operations Manager", titleId: "Manajer Operasional Gudang", isco: "1324" },
        { titleEn: "Supply Chain Manager", titleId: "Manajer Rantai Pasokan", isco: "1324" },
        { titleEn: "General Manager", titleId: "Manajer Umum", isco: "1321" },
        { titleEn: "Inventory Control Specialist", titleId: "Spesialis Pengendalian Inventaris", isco: "4321" },
        { titleEn: "Logistics Coordinator", titleId: "Koordinator Logistik", isco: "3339" },
        { titleEn: "Warehouse Safety Officer", titleId: "Petugas Keselamatan Gudang", isco: "3339" },
        { titleEn: "Customs Documentation Specialist", titleId: "Spesialis Dokumentasi Kepabeanan", isco: "3339" },
        { titleEn: "Quality Control Inspector", titleId: "Inspektur Pengendalian Mutu", isco: "3119" }
      ],
      insight: "Kepmen 228/2019 lists 152 TKA-eligible positions in this category. Selection optimized using ISCO classification methodology.",
      keduaNote: "Directors and Commissioners who do NOT manage personalia can work without being listed in the jabatan.",
    },
},

  "77100": {
    whatItMeans:
      "Vehicle rental without driver — renting out cars, motorbikes, scooters, trucks, and other motor vehicles to customers who drive themselves (self-drive). This is the classic rental business: the customer pays for the vehicle for a period, collects it, drives it, and returns it. No driver is supplied with the vehicle. Includes: short-term car and motorbike rentals for tourists, long-term vehicle leasing for businesses and expats, and fleet leasing for corporate clients. If a driver is included, that is a transport service (49213) — the key distinction is self-drive.",
    whatYouNeed:
      `**All scales**: Low risk (Rendah). NIB issued **automatically** (Otomatis). Authority: **Bupati/Walikota**. Only an NIB is required — the licensing itself is simple.\\n\\n**Critical operational and compliance requirements:**\\n\\n**Step-by-step for a PT PMA vehicle rental operator:**\\n1. **PT PMA incorporation** — notary deed, AHU registration; minimum IDR 10B stated (~3–5 weeks)\\n2. **NIB via OSS** — register on oss.go.id, select 77100, Rendah path; auto-issued (1–3 days)\\n3. **STNK atas nama PT PMA** — all rental vehicles must be registered under the PT PMA entity. Vehicles in a personal name cannot legally be rented commercially\\n4. **KIR (Uji Berkala)** — for vehicles classified as commercial (angkutan umum): mandatory 6-monthly roadworthiness test. For private-use-classified vehicles used in rental: KIR requirements depend on vehicle type and local Dishub policy — verify with Dishub Badung\\n5. **Asuransi kendaraan komersial** — commercial vehicle insurance (TLO — Total Loss Only or comprehensive). Standard private car insurance policies are void when the vehicle is used for commercial rental\\n6. **Rental agreement (Perjanjian Sewa Kendaraan)** — mandatory written agreement with each renter. Must include: vehicle identity (nopol, STNK copy), rental period, return conditions, liability clause\\n7. **SIM verification for renters** — verify customer holds a valid driving license:\\n   - Indonesian SIM A (car) or SIM C (motorbike) for Indonesian nationals\\n   - **International Driving Permit (IDP/SIM Internasional)** for foreign nationals — issued under the 1949 Geneva Convention on Road Traffic. An IDP is only valid in Indonesia alongside the original national license. Tourist note: IDP must be obtained in the renter's home country BEFORE arrival\\n   - A rental agreement accepting a foreign license without IDP exposes the rental company to liability if an accident occurs\\n8. **Laporan kegiatan usaha** — periodic business activity reports (ongoing obligation)\\n\\n**Typical total timeline:** 1–2 months from PT PMA to first vehicle rented.\\n**Minimum PT PMA capital:** IDR 10 billion stated capital (Rp 2.5B paid-up).\\n\\n**Authority:** Bupati/Walikota.\\n**PMA:** Fully open (Terbuka) — 100% foreign ownership.`,
    whatChanged:
      "Direct match from KBLI 2020 (MATCH_LANGSUNG). Vehicle rental classification is stable. The PT PMA requirement for formal operation is unchanged; enforcement of illegal operations (foreigner-owned rental businesses without PT PMA) has intensified.",
    baliContext:
      "**🏍 Vehicle Rental in Bali (The Most Abused and Most Profitable Sector)**\\n\\n**The scale of the informal market:**\\n- Bali receives 5–6 million international tourists annually (2024). The vast majority who want independent mobility rent a motorbike\\n- Conservative estimates: 100,000–200,000+ motorbikes are rented daily at peak season\\n- The reality: the overwhelming majority of Bali's motorbike rental operations are run by foreigners without PT PMA, without NIB, without proper STNK registration — operating illegally from private names or through informal intermediaries\\n- Enforcement risk: Satpol PP and Imigrasi operations have increased; foreigners running motorcycle rental businesses without proper structure face deportation\\n\\n**Why PT PMA is worth it:**\\n- **Legal protection** — a properly structured PT PMA with NIB and commercial STNK can be operated openly, advertised on Google Maps/Airbnb, and scaled\\n- **Insurance** — only commercial insurance (atas nama PT) covers accidents during rental. Informal operations have zero insurance coverage — a single serious accident can be financially catastrophic\\n- **Scalability** — PT PMA allows you to grow from 5 to 100+ vehicles with proper fleet management\\n\\n**Revenue benchmarks (Bali 2025):**\\n- Motorbike (Honda Beat/Scoopy/Vario): IDR 75,000–150,000/day\\n- Car (Toyota Avanza/Rush): IDR 300,000–600,000/day\\n- Luxury SUV (Fortuner, Innova): IDR 800,000–1,500,000/day\\n- Monthly motorbike lease (expat): IDR 900,000–1,500,000/month\\n\\n**Strategic location:** Canggu, Seminyak, Kuta, Ubud are the highest-demand corridors. Online channels (booking.com, Klook, direct website) increasingly dominate discovery\\n\\n**⚠ IDP (International Driving Permit) is your liability shield:**\\n- Insist on IDP from all foreign renters. Without it, your commercial insurance claim can be denied if an accident occurs\\n- In practice, many tourist renters don't have an IDP — you must decide your risk tolerance and rental policy. Document your IDP verification process",
    youllAlsoNeed:
      "- **49213** — Urban passenger transport — if you add a driver service alongside self-drive rental\\n- **45201** — Automotive repair — if you maintain your fleet in-house\\n- **47820** — Automotive spare parts — if you stock parts for your fleet\\n- **82990** — Other business support services — if you manage fleet bookings and dispatch as a separate service\\n\\n**For your renters to check (not your license, but inform them):**\\n- International Driving Permit (IDP) — obtain in home country before arrival (AAA in US, AA in UK, ADAC in Germany, etc.)\\n- IDP is valid only alongside original national driving license\\n- Motorbike license: must be class for motorbike, not just car\\n- Helmet is mandatory under UU LLAJ 22/2009 — provide one",
    zantaraOpener:
      "Motorbike or car rental business in Bali? 77100 is NIB-only, auto-issued. But thousands of foreigners run rental operations illegally — PT PMA + commercial STNK + proper insurance is what separates a real business from a liability trap. Let me show you the right structure.",
    tkaInfo: {
      categoryId: 17,
      categoryName: "Transportasi & Pergudangan",
      totalInCategory: 152,
      iscoGroupsSelected: ["13", "31", "43"],
      selectedForThisCode: 7,
      selectionMethod: "ISCO-based",
      relevantPositions: [
        { titleEn: "Rental Operations Manager", titleId: "Manajer Operasional Penyewaan", isco: "1324" },
        { titleEn: "Fleet Manager", titleId: "Manajer Armada", isco: "1324" },
        { titleEn: "General Manager", titleId: "Manajer Umum", isco: "1321" },
        { titleEn: "Customer Service Manager", titleId: "Manajer Layanan Pelanggan", isco: "1420" },
        { titleEn: "Vehicle Maintenance Technician", titleId: "Teknisi Perawatan Kendaraan", isco: "3115" },
        { titleEn: "Fleet Coordinator", titleId: "Koordinator Armada", isco: "3339" },
        { titleEn: "Insurance and Documentation Specialist", titleId: "Spesialis Asuransi dan Dokumentasi", isco: "3321" }
      ],
      insight: "Kepmen 228/2019 lists 152 TKA-eligible positions in this category. Selection optimized using ISCO classification methodology.",
      keduaNote: "Directors and Commissioners who do NOT manage personalia can work without being listed in the jabatan.",
    },
},

  "79110": {
    whatItMeans:
      "Travel agency (biro perjalanan wisata) — selling travel products and services to the public, including: tour packages (inbound, outbound, and domestic), flight ticket booking, hotel accommodation booking, visa assistance, airport transfer arrangements, and customized itinerary design. The agency acts as an intermediary between the traveler and the suppliers (airlines, hotels, ground handlers). Key distinction: 79110 = travel agency with a B2C retail function (you sell directly to travelers, whether in-person or online). Contrast with 79120 = tour operator wholesaler that sells only to other travel agencies (B2B, no direct public retail). If you want to both sell packages to travelers AND wholesale to agencies, 79110 is the code.",
    whatYouNeed:
      `**Single scale in PP 28/2025 data**: Medium-High risk (Menengah Tinggi). NIB + Izin required — **not automatic**. Issued by **Bupati/Walikota** within **5 working days**.\\n\\n**Mandatory parallel registrations beyond OSS:**\\n\\n**Step-by-step for a PT PMA travel agency:**\\n1. **PT PMA incorporation** — notary deed, AHU registration; tourism/travel sector minimum IDR 10B stated (~3–5 weeks)\\n2. **NIB via OSS** — register on oss.go.id, select 79110, Menengah Tinggi path (~3 days)\\n3. **TDUP Pariwisata (Tanda Daftar Usaha Pariwisata)** — mandatory tourism business registration with Dinas Pariwisata Kabupaten/Kota (Badung for Canggu/Seminyak/Kuta/Nusa Dua; Gianyar for Ubud). Documents: NIB, company deed, office address, list of services. Required for all tourism businesses in Bali; without TDUP you cannot legally offer tourism services\\n4. **Izin Usaha Biro Perjalanan Wisata** — from Kemenparekraf (Kementerian Pariwisata dan Ekonomi Kreatif) for agencies offering outbound international packages; documents include: company profile, financial capacity evidence, qualified tourism professional on staff. Processed via SIUP Pariwisata system\\n5. **Izin from Bupati/Walikota via OSS** — issued within 5 working days after TDUP clearance\\n6. **ASITA membership** (Asosiasi Perusahaan Perjalanan Wisata Indonesia) — not legally mandatory but practically essential for credibility with hotel partners, airline GSAs, and B2B tour operator clients. Required by many hotel group contracting processes\\n7. **IATA accreditation** (if issuing flight tickets directly) — International Air Transport Association agent certification. Required for direct BSP (Billing and Settlement Plan) ticketing. Without IATA accreditation, you can still sell tickets through a sub-agent model via an IATA-accredited agency\\n8. **Office location** — travel agencies in Bali must operate from a registered commercial address (not residential). Badung: Jalan Sunset Road, Legian, Seminyak, Nusa Dua business zones\\n9. **Laporan kegiatan usaha** — periodic business activity reports (ongoing obligation)\\n\\n**Typical total timeline:** 3–5 months from PT PMA to fully licensed (TDUP + Kemenparekraf + OSS).\\n**Minimum PT PMA capital:** IDR 10 billion stated capital (Rp 2.5B paid-up).\\n\\n**Authority:** Bupati/Walikota (OSS Izin) · Kemenparekraf (Izin Usaha outbound).\\n**PMA:** Fully open (Terbuka) — 100% foreign ownership.`,
    whatChanged:
      "Direct match from KBLI 2020 (MATCH_LANGSUNG). Travel agency classification is stable. The primary regulatory development since 2020 is the merger of Ministry of Tourism functions into Kemenparekraf and the digitization of TDUP registration via OSS.",
    baliContext:
      "**✈ Travel Agency in Bali (Entry Point for Tourism PMA)**\\n- 79110 is the most common first KBLI for foreigners entering Bali's tourism sector through a PT PMA\\n- Bali receives 5–6M international visitors/year (2024 recovery) and is Indonesia's premier inbound tourism destination\\n\\n**The DMC Model (Destination Management Company):**\\n- The most profitable travel agency model for Bali PMA is the **DMC** — a company that manages the end-to-end Bali experience for corporate groups, incentive programs, and high-end FITs (Free Individual Travelers)\\n- DMCs serve: multinational corporate incentive programs, association conferences (MICE), UHNW private travelers, and luxury FIT clients\\n- Revenue: DMC margins range from 15–30% on ground handling, accommodation, and activities\\n\\n**Benchmark operators:**\\n- Mason Adventures (mid-market), Bali DMC (corporate), Karma Group (luxury) — these define the competitive landscape\\n- Niche opportunity: specialized thematic DMCs (surfing/wellness/agritourism/diving) are less crowded than general operators\\n\\n**MICE connection:**\\n- A Bali DMC with both 79110 (travel/transfers) and 82300 (event organizing) is positioned for the full MICE contract — conference logistics, pre/post-tour programs, incentive packages\\n\\n**⚠ TDUP is non-negotiable in Bali:**\\n- Dinas Pariwisata Bali conducts periodic sweeping operations to identify tourism businesses operating without TDUP\\n- Operating without TDUP in Bali is not a grey area — fines and operational suspension are real enforcement tools\\n- TDUP renewal is typically annual; build it into your compliance calendar\\n\\n**ASITA membership:** The hotel contracting and tour operator network in Bali runs through ASITA membership. Without it, getting net rates from hotels for your tour packages is significantly harder — hotels prioritize ASITA members in rate negotiations",
    youllAlsoNeed:
      "- **79120** — Tour operator (wholesaler/B2B) — if you also create and sell packages wholesale to other agencies\\n- **82300** — Event organizer / MICE — if you also manage conferences and incentive events\\n- **49213** — Urban/charter transport — if you operate your own fleet for client transfers\\n- **55110** — Hotel / accommodation — if you also develop accommodation alongside tours\\n- **79900** — Other reservation services — if your business model extends to reservation platform operations",
    zantaraOpener:
      "Setting up a travel agency or DMC in Bali? 79110 needs both TDUP from Dinas Pariwisata and Kemenparekraf licensing — the 5-day clock only starts after those are in order. ASITA membership and IATA accreditation aren't mandatory but are commercially essential. Let me walk you through all of it.",
    tkaInfo: {
      categoryId: 19,
      categoryName: "Akomodasi & Makan Minum",
      totalInCategory: 164,
      iscoGroupsSelected: ["13", "24", "42"],
      selectedForThisCode: 8,
      selectionMethod: "ISCO-based",
      relevantPositions: [
        { titleEn: "Travel Agency Manager", titleId: "Manajer Biro Perjalanan Wisata", isco: "1420" },
        { titleEn: "Destination Management Director", titleId: "Direktur Manajemen Destinasi", isco: "1221" },
        { titleEn: "General Manager", titleId: "Manajer Umum", isco: "1321" },
        { titleEn: "Tour Product Developer", titleId: "Pengembang Produk Wisata", isco: "2432" },
        { titleEn: "MICE Coordinator", titleId: "Koordinator MICE", isco: "3339" },
        { titleEn: "Customer Experience Manager", titleId: "Manajer Pengalaman Pelanggan", isco: "1420" },
        { titleEn: "Inbound Tour Specialist", titleId: "Spesialis Wisata Inbound", isco: "4221" },
        { titleEn: "Airline Ticketing Specialist", titleId: "Spesialis Tiket Penerbangan", isco: "4221" }
      ],
      insight: "Kepmen 228/2019 lists 164 TKA-eligible positions in this category. Selection optimized using ISCO classification methodology.",
      keduaNote: "Directors and Commissioners who do NOT manage personalia can work without being listed in the jabatan.",
    },
},

  "82300": {
    whatItMeans:
      "MICE and event management — professional organizing of Meetings, Incentives, Conferences, and Exhibitions (MICE). This covers: Professional Conference Organizer (PCO) services, incentive program design and execution, trade fair and exhibition management, corporate event production, product launches, gala dinners, and awards ceremonies. The defining characteristic: you are the organizer managing the event on behalf of a client — sourcing venues, coordinating logistics, managing suppliers, and delivering the event. Contrast with simply renting a venue (55112 or 56209) or providing entertainment (90003) — 82300 is the end-to-end event management business.",
    whatYouNeed:
      `**Single scale in PP 28/2025 data**: Medium-High risk (Menengah Tinggi). NIB + Izin required — **not automatic**. Issued by **Bupati/Walikota** within **5 working days**.\\n\\n**Step-by-step for a PT PMA MICE/event management company:**\\n1. **PT PMA incorporation** — notary deed, AHU registration; minimum IDR 10B stated capital (~3–5 weeks)\\n2. **NIB via OSS** — register on oss.go.id, select 82300, Menengah Tinggi path (~3 days)\\n3. **Izin Usaha Jasa Penyelenggara Acara** — event management business license from DPMPTSP Kabupaten; documents: company profile, list of services, qualified event professionals, operational address\\n4. **TDUP Pariwisata** (if events include tourism components) — Tanda Daftar Usaha Pariwisata from Dinas Pariwisata; applicable when events involve tour programs, accommodation arrangements, or venue experiences for participants\\n5. **Izin from Bupati/Walikota via OSS** — issued within 5 working days\\n6. **Izin Keramaian** (per-event permit for large public events) — required for events with large public attendance; issued by Polres Bali or Polda Bali. Required documents per event: event plan, venue capacity, security plan, emergency procedures. Timeline: 14 days before event (minimum)\\n7. **IEIA membership** (Indonesian Exhibition Companies Association) — industry body for trade fair and exhibition organizers. Recommended for credibility and access to international exhibition networks\\n8. **Speaker/artist permits** (for international talent) — if your events feature international speakers or performers: coordinating their visa status (Seniman/Ahli visa), work permit (IMTA), and immigration clearance\\n9. **Laporan kegiatan usaha** — periodic business activity reports (ongoing obligation)\\n\\n**Per-event operational permits:**\\n- Izin keramaian from Polres for each large public event\\n- Sound system and noise compliance with Pemda Bali regulations\\n- Food service permits (if catering is bundled): from Dinas Kesehatan for mass catering\\n\\n**Typical total timeline:** 3–5 months from PT PMA to first contracted event.\\n**Minimum PT PMA capital:** IDR 10 billion stated capital (Rp 2.5B paid-up).\\n\\n**Authority:** Bupati/Walikota.\\n**PMA:** Fully open (Terbuka) — 100% foreign ownership.`,
    whatChanged:
      "Direct match from KBLI 2020 (MATCH_LANGSUNG). MICE and event management classification is stable. The major development since 2020 is Bali's post-G20 global profile: the G20 Bali Summit (November 2022) and World Water Forum (May 2024) have elevated Bali's international MICE credibility significantly.",
    baliContext:
      "**🎪 Bali MICE: A Market Coming Into Its Own**\\n\\n**The venues:**\\n- **BICC (Bali International Convention Centre)** — Nusa Dua; capacity 10,000 pax for plenary, 5,000 for banquet; the flagship venue for major international conferences\\n- **Sofitel Bali Nusa Dua Beach Resort** — 706 rooms, MICE capacity 3,500 pax; frequently hosts G2G and corporate MICE\\n- **Conrad Bali** — 360 rooms, MICE capacity 2,000 pax; Jimbaran beachfront\\n- **Mulia Resort Nusa Dua** — 1,000 rooms, multiple ballrooms; top tier for incentive programs\\n- **Kempinski Nusa Dua** — luxury MICE with beachfront incentive options\\n- **INAYA Putri Bali (formerly Westin)** — Nusa Dua, 350 rooms, convention facilities\\n\\n**Pricing benchmarks (Bali MICE, 2025):**\\n- Conference package (venue + F&B + AV + accommodation): **IDR 2–5 million per pax per day** for full-board international-standard events\\n- Incentive program (tours + dinner + activities): IDR 3–8 million per pax per program day\\n- Exhibition space: IDR 5–15 million per 9m² booth per day at major trade fairs\\n\\n**Bali's MICE track record:**\\n- G20 Bali (November 2022): 17,000 participants, 20,000+ media; put Bali on the global MICE map\\n- World Water Forum (May 2024): 30,000 participants from 172 countries\\n- Regular: BaliSpirit Festival, Bali International Marathon (mass events), INACRAFT regional fairs\\n\\n**The PMA opportunity:**\\n- International PCO companies (global conference management firms) have minimal local presence in Bali\\n- Corporate incentive programs from multinationals (healthcare, pharma, tech, finance) represent the highest-margin segment\\n- **ICCA (International Congress and Convention Association)** and **MPI (Meeting Professionals International)** membership connects Bali PCOs to global conference rotation networks — major conferences cycle through destinations; being in the ICCA database is how destinations get selected\\n\\n**⚠ Izin Keramaian — plan early:**\\n- Polres Bali processes Izin Keramaian applications; 14 days minimum before event\\n- For major events (1,000+ participants): coordinate with Polda Bali directly\\n- Security plan (rencana pengamanan) must be submitted; for international events, Bali Police may require dedicated police presence (paid coordination fee)\\n- Events near Pura (temples) or during Nyepi (Balinese New Year, Hari Raya Nyepi) face absolute restrictions — plan your event calendar around the Saka calendar",
    youllAlsoNeed:
      "- **79110** — Travel agency / biro perjalanan wisata — for tour programs, pre/post-conference excursions, and transfer arrangements within your MICE packages\\n- **90003** — Entertainment production — if your events include live performances, concerts, or cultural shows\\n- **56209** — Other F&B catering — if you provide in-house catering for events\\n- **73100** — Advertising and communication — if you also handle event marketing and promotion\\n- **74120** — Industrial design — if you design exhibition stands, event installations, and stage sets in-house",
    zantaraOpener:
      "Building a MICE or event management company in Bali? 82300 is your code. Bali's MICE market is in strong growth — IDR 2–5M per pax per day for international conferences. You'll need TDUP, Izin Keramaian per event, and to be on ICCA's radar to win international contracts.",
    tkaInfo: {
      categoryId: 19,
      categoryName: "Akomodasi & Makan Minum",
      totalInCategory: 164,
      iscoGroupsSelected: ["13", "24", "33"],
      selectedForThisCode: 9,
      selectionMethod: "ISCO-based",
      relevantPositions: [
        { titleEn: "Event Director", titleId: "Direktur Acara", isco: "1221" },
        { titleEn: "MICE Manager", titleId: "Manajer MICE", isco: "1420" },
        { titleEn: "General Manager", titleId: "Manajer Umum", isco: "1321" },
        { titleEn: "Conference Program Director", titleId: "Direktur Program Konferensi", isco: "2432" },
        { titleEn: "Exhibition Manager", titleId: "Manajer Pameran", isco: "1420" },
        { titleEn: "Incentive Program Designer", titleId: "Perancang Program Insentif", isco: "2432" },
        { titleEn: "Event Production Coordinator", titleId: "Koordinator Produksi Acara", isco: "3339" },
        { titleEn: "Venue Liaison Manager", titleId: "Manajer Penghubung Venue", isco: "3339" },
        { titleEn: "Technical Production Specialist", titleId: "Spesialis Produksi Teknis", isco: "3521" }
      ],
      insight: "Kepmen 228/2019 lists 164 TKA-eligible positions in this category. Selection optimized using ISCO classification methodology.",
      keduaNote: "Directors and Commissioners who do NOT manage personalia can work without being listed in the jabatan.",
    },
},
'''

HERO_IMAGES_BLOCK = '''  "49213": {
    src: "https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?w=1600&q=80&auto=format",
    alt: "City transport bus public transportation urban",
    overlay: "linear-gradient(135deg, rgba(10,10,20,0.70) 0%, rgba(18,18,38,0.53) 50%, rgba(10,10,20,0.70) 100%)",
  },
  "49231": {
    src: "https://images.unsplash.com/photo-1601584115197-04ecc0da31d7?w=1600&q=80&auto=format",
    alt: "Freight truck logistics cargo transport road",
    overlay: "linear-gradient(135deg, rgba(15,10,5,0.70) 0%, rgba(28,18,8,0.53) 50%, rgba(15,10,5,0.70) 100%)",
  },
  "52292": {
    src: "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=1600&q=80&auto=format",
    alt: "Modern warehouse logistics storage facility",
    overlay: "linear-gradient(135deg, rgba(5,10,15,0.70) 0%, rgba(8,18,28,0.53) 50%, rgba(5,10,15,0.70) 100%)",
  },
  "77100": {
    src: "https://images.unsplash.com/photo-1449965408869-eaa3f722e40d?w=1600&q=80&auto=format",
    alt: "Car rental fleet vehicles tourism Bali",
    overlay: "linear-gradient(135deg, rgba(10,15,10,0.70) 0%, rgba(18,28,18,0.53) 50%, rgba(10,15,10,0.70) 100%)",
  },
  "79110": {
    src: "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?w=1600&q=80&auto=format",
    alt: "Travel agency tour booking tourism service",
    overlay: "linear-gradient(135deg, rgba(5,10,25,0.70) 0%, rgba(8,18,42,0.53) 50%, rgba(5,10,25,0.70) 100%)",
  },
  "82300": {
    src: "https://images.unsplash.com/photo-1511578314322-379afb476865?w=1600&q=80&auto=format",
    alt: "Event organizer MICE conference Bali",
    overlay: "linear-gradient(135deg, rgba(15,10,20,0.70) 0%, rgba(28,18,38,0.53) 50%, rgba(15,10,20,0.70) 100%)",
  },
'''

# ============================================================
# 1. Insert 6 new entries before closing };
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

print(f"Inserting 6 new entries before line {close_idx+1}")
lines.insert(close_idx, NEW_6_ENTRIES)
content = '\n'.join(lines)
print(f"After inserting: {len(content.split(chr(10)))} lines")

with open('lib/kbli-gold-content.ts', 'w') as f:
    f.write(content)
print("✓ lib/kbli-gold-content.ts written")

# ============================================================
# 2. Add hero images to page.tsx
# ============================================================
# Find last entry before closing }; in GOLD_HERO_IMAGES
# The GOLD_HERO_IMAGES block ends at }; after GOLD_HERO_IMAGES
# Find the }; that closes GOLD_HERO_IMAGES
# It's the first standalone }; after "const GOLD_HERO_IMAGES"

hero_start = page.find('const GOLD_HERO_IMAGES')
if hero_start < 0:
    print("ERROR: GOLD_HERO_IMAGES not found in page.tsx")
    exit(1)

# Find the }; closing this const
close_hero = page.find('\n};', hero_start)
if close_hero < 0:
    print("ERROR: Closing }; of GOLD_HERO_IMAGES not found")
    exit(1)

# Check what's just before the closing
print(f"GOLD_HERO_IMAGES closes at pos {close_hero}")
print(f"Context before close: ...{page[close_hero-100:close_hero+5]}")

# Insert hero images before the closing };
page = page[:close_hero + 1] + HERO_IMAGES_BLOCK + '};\n' + page[close_hero + 4:]

with open('app/kbli/[code]/page.tsx', 'w') as f:
    f.write(page)
print("✓ app/kbli/[code]/page.tsx written")

print("\nDone! Summary:")
print(f"  lib/kbli-gold-content.ts: {len(content.split(chr(10)))} lines")
print(f"  app/kbli/[code]/page.tsx: {len(page.split(chr(10)))} lines")
