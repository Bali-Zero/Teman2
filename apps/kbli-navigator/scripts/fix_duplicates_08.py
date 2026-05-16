#!/usr/bin/env python3
"""Fix duplicate entries created by Session 08 script for 77100, 79110, 82300"""
import re

with open('lib/kbli-gold-content.ts', 'r') as f:
    content = f.read()

print(f"Starting: {len(content.split(chr(10)))} lines")

# ============================================================
# New content for each duplicate code
# ============================================================

NEW_77100 = '''  "77100": {
    whatItMeans:
      "Vehicle rental without driver — renting out cars, motorbikes, scooters, trucks, and other motor vehicles to customers who drive themselves (self-drive). This is the classic rental business: the customer pays for the vehicle for a period, collects it, drives it, and returns it. No driver is supplied with the vehicle. Includes: short-term car and motorbike rentals for tourists, long-term vehicle leasing for businesses and expats, and fleet leasing for corporate clients. If a driver is included, that is a transport service (49213) — the key distinction is self-drive.",
    whatYouNeed:
      `**All scales**: Low risk (Rendah). NIB issued **automatically** (Otomatis). Authority: **Bupati/Walikota**. Only an NIB is required — the licensing itself is simple.\\n\\n**Critical operational and compliance requirements:**\\n\\n**Step-by-step for a PT PMA vehicle rental operator:**\\n1. **PT PMA incorporation** — notary deed, AHU registration; minimum IDR 10B stated (~3–5 weeks)\\n2. **NIB via OSS** — register on oss.go.id, select 77100, Rendah path; auto-issued (1–3 days)\\n3. **STNK atas nama PT PMA** — all rental vehicles must be registered under the PT PMA entity. Vehicles in a personal name cannot legally be rented commercially\\n4. **KIR (Uji Berkala)** — for vehicles classified as commercial (angkutan umum): mandatory 6-monthly roadworthiness test. For private-use-classified vehicles used in rental: KIR requirements depend on vehicle type and local Dishub policy — verify with Dishub Badung\\n5. **Asuransi kendaraan komersial** — commercial vehicle insurance (TLO — Total Loss Only or comprehensive). Standard private car insurance policies are void when the vehicle is used for commercial rental\\n6. **Rental agreement (Perjanjian Sewa Kendaraan)** — mandatory written agreement with each renter. Must include: vehicle identity (nopol, STNK copy), rental period, return conditions, liability clause\\n7. **SIM verification for renters** — verify customer holds a valid driving license:\\n   - Indonesian SIM A (car) or SIM C (motorbike) for Indonesian nationals\\n   - **International Driving Permit (IDP/SIM Internasional)** for foreign nationals — issued under the 1949 Geneva Convention on Road Traffic. An IDP is only valid in Indonesia alongside the original national license. Tourist note: IDP must be obtained in the renter's home country BEFORE arrival\\n   - A rental agreement accepting a foreign license without IDP exposes the rental company to liability if an accident occurs\\n8. **Laporan kegiatan usaha** — periodic business activity reports (ongoing obligation)\\n\\n**Typical total timeline:** 1–2 months from PT PMA to first vehicle rented.\\n**Minimum PT PMA capital:** IDR 10 billion stated capital (Rp 2.5B paid-up).\\n\\n**Authority:** Bupati/Walikota.\\n**PMA:** Fully open (Terbuka) — 100% foreign ownership.`,
    whatChanged:
      "Direct match from KBLI 2020 (MATCH_LANGSUNG). Vehicle rental classification is stable. The PT PMA requirement for formal operation is unchanged; enforcement of illegal operations (foreigner-owned rental businesses without PT PMA) has intensified since 2022.",
    baliContext:
      "**🏍 Vehicle Rental in Bali (The Most Abused and Most Profitable Sector)**\\n\\n**The scale of the informal market:**\\n- Bali receives 5–6 million international tourists annually (2024). The vast majority who want independent mobility rent a motorbike\\n- Conservative estimates: 100,000–200,000+ motorbikes are rented daily at peak season\\n- The reality: the overwhelming majority of Bali's motorbike rental operations are run by foreigners without PT PMA, without NIB, without proper STNK registration — operating illegally from private names or through informal intermediaries\\n- Enforcement risk: Satpol PP and Imigrasi operations have increased; foreigners running motorcycle rental businesses without proper structure face deportation\\n\\n**Why PT PMA is worth it:**\\n- **Legal protection** — a properly structured PT PMA with NIB and commercial STNK can be operated openly, advertised on Google Maps/Airbnb, and scaled\\n- **Insurance** — only commercial insurance (atas nama PT) covers accidents during rental. Informal operations have zero insurance coverage — a single serious accident can be financially catastrophic\\n- **Scalability** — PT PMA allows you to grow from 5 to 100+ vehicles with proper fleet management\\n\\n**Revenue benchmarks (Bali 2025):**\\n- Motorbike (Honda Beat/Scoopy/Vario): IDR 75,000–150,000/day\\n- Car (Toyota Avanza/Rush): IDR 300,000–600,000/day\\n- Luxury SUV (Fortuner, Innova): IDR 800,000–1,500,000/day\\n- Monthly motorbike lease (expat): IDR 900,000–1,500,000/month\\n\\n**Strategic location:** Canggu, Seminyak, Kuta, Ubud are the highest-demand corridors. Online channels (Booking.com, Klook, direct website) increasingly dominate discovery\\n\\n**⚠ IDP (International Driving Permit) is your liability shield:**\\n- Insist on IDP from all foreign renters. Without it, your commercial insurance claim can be denied if an accident occurs\\n- In practice, many tourist renters don't have an IDP — you must decide your risk tolerance and rental policy. Document your IDP verification process",
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
'''

NEW_79110 = '''  "79110": {
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
'''

NEW_82300 = '''  "82300": {
    whatItMeans:
      "MICE and event management — professional organizing of Meetings, Incentives, Conferences, and Exhibitions (MICE). This covers: Professional Conference Organizer (PCO) services, incentive program design and execution, trade fair and exhibition management, corporate event production, product launches, gala dinners, and awards ceremonies. The defining characteristic: you are the organizer managing the event on behalf of a client — sourcing venues, coordinating logistics, managing suppliers, and delivering the event. Contrast with simply renting a venue (55112 or 56209) or providing entertainment (90003) — 82300 is the end-to-end event management business.",
    whatYouNeed:
      `**Single scale in PP 28/2025 data**: Medium-High risk (Menengah Tinggi). NIB + Izin required — **not automatic**. Issued by **Bupati/Walikota** within **5 working days**.\\n\\n**Step-by-step for a PT PMA MICE/event management company:**\\n1. **PT PMA incorporation** — notary deed, AHU registration; minimum IDR 10B stated capital (~3–5 weeks)\\n2. **NIB via OSS** — register on oss.go.id, select 82300, Menengah Tinggi path (~3 days)\\n3. **Izin Usaha Jasa Penyelenggara Acara** — event management business license from DPMPTSP Kabupaten; documents: company profile, list of services, qualified event professionals, operational address\\n4. **TDUP Pariwisata** (if events include tourism components) — Tanda Daftar Usaha Pariwisata from Dinas Pariwisata; applicable when events involve tour programs, accommodation arrangements, or venue experiences for participants\\n5. **Izin from Bupati/Walikota via OSS** — issued within 5 working days\\n6. **Izin Keramaian** (per-event permit for large public events) — required for events with large public attendance; issued by Polres Bali or Polda Bali. Required documents per event: event plan, venue capacity, security plan, emergency procedures. Timeline: 14 days before event (minimum)\\n7. **IEIA membership** (Indonesian Exhibition Companies Association) — industry body for trade fair and exhibition organizers. Recommended for credibility and access to international exhibition networks\\n8. **Speaker/artist permits** (for international talent) — if your events feature international speakers or performers: coordinating their visa status (Seniman/Ahli visa), work permit (IMTA), and immigration clearance\\n9. **Laporan kegiatan usaha** — periodic business activity reports (ongoing obligation)\\n\\n**Per-event operational permits:**\\n- Izin keramaian from Polres for each large public event\\n- Sound system and noise compliance with Pemda Bali regulations\\n- Food service permits (if catering is bundled): from Dinas Kesehatan for mass catering\\n\\n**Typical total timeline:** 3–5 months from PT PMA to first contracted event.\\n**Minimum PT PMA capital:** IDR 10 billion stated capital (Rp 2.5B paid-up).\\n\\n**Authority:** Bupati/Walikota.\\n**PMA:** Fully open (Terbuka) — 100% foreign ownership.`,
    whatChanged:
      "Direct match from KBLI 2020 (MATCH_LANGSUNG). MICE and event management classification is stable. The major development since 2020 is Bali's post-G20 global profile: the G20 Bali Summit (November 2022) and World Water Forum (May 2024) have elevated Bali's international MICE credibility significantly.",
    baliContext:
      "**🎪 Bali MICE: A Market Coming Into Its Own**\\n\\n**The venues:**\\n- **BICC (Bali International Convention Centre)** — Nusa Dua; capacity 10,000 pax for plenary, 5,000 for banquet; the flagship venue for major international conferences\\n- **Sofitel Bali Nusa Dua Beach Resort** — 706 rooms, MICE capacity 3,500 pax; frequently hosts G2G and corporate MICE\\n- **Conrad Bali** — 360 rooms, MICE capacity 2,000 pax; Jimbaran beachfront\\n- **Mulia Resort Nusa Dua** — 1,000 rooms, multiple ballrooms; top tier for incentive programs\\n- **Kempinski Nusa Dua** — luxury MICE with beachfront incentive options\\n\\n**Pricing benchmarks (Bali MICE, 2025):**\\n- Conference package (venue + F&B + AV + accommodation): **IDR 2–5 million per pax per day** for full-board international-standard events\\n- Incentive program (tours + dinner + activities): IDR 3–8 million per pax per program day\\n- Exhibition space: IDR 5–15 million per 9m² booth per day at major trade fairs\\n\\n**Bali's MICE track record:**\\n- G20 Bali (November 2022): 17,000 participants, 20,000+ media; put Bali on the global MICE map\\n- World Water Forum (May 2024): 30,000 participants from 172 countries\\n- Regular: BaliSpirit Festival, Bali International Marathon (mass events), INACRAFT regional fairs\\n\\n**The PMA opportunity:**\\n- International PCO companies (global conference management firms) have minimal local presence in Bali\\n- Corporate incentive programs from multinationals (healthcare, pharma, tech, finance) represent the highest-margin segment\\n- **ICCA (International Congress and Convention Association)** and **MPI (Meeting Professionals International)** membership connects Bali PCOs to global conference rotation networks\\n\\n**⚠ Izin Keramaian — plan early:**\\n- Polres Bali processes Izin Keramaian applications; 14 days minimum before event\\n- For major events (1,000+ participants): coordinate with Polda Bali directly\\n- Events near Pura (temples) or during Nyepi face absolute restrictions — plan your event calendar around the Saka calendar",
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

# ============================================================
# Helper to find the end of an entry starting at start_pos
# ============================================================
def find_entry_end(text, start_pos):
    """Find end of an object entry — returns position after closing },"""
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
                    # Find closing },\n pattern
                    if text[i+1:i+3] in (',\n', ',\r'):
                        return i + 3
                    elif text[i+1:i+2] == '\n':
                        return i + 2
                    else:
                        return i + 1
        i += 1
    return len(text)

# ============================================================
# Step 1: Remove the DUPLICATE entries from the end (inserted by update_gold_08.py)
# For each duplicated code, find ALL occurrences and remove the LAST one
# ============================================================
for code, new_content in [('77100', NEW_77100), ('79110', NEW_79110), ('82300', NEW_82300)]:
    # Find all occurrences
    import re
    pattern = f'  "{code}": {{'
    positions = [m.start() for m in re.finditer(re.escape(pattern), content)]
    print(f"{code}: {len(positions)} occurrences at lines {[content[:p].count(chr(10))+1 for p in positions]}")

    if len(positions) < 2:
        print(f"  ERROR: Expected 2 occurrences for {code}, found {len(positions)}")
        continue

    # Remove the LAST occurrence (the duplicate we just inserted)
    last_pos = positions[-1]
    last_end = find_entry_end(content, last_pos)
    removed_chunk = content[last_pos:last_end]
    print(f"  Removing duplicate at line {content[:last_pos].count(chr(10))+1}, length {len(removed_chunk)} chars")
    content = content[:last_pos] + content[last_end:]

    # Now replace the FIRST (old) occurrence with new content
    first_pos = content.find(f'  "{code}": {{')
    if first_pos < 0:
        print(f"  ERROR: Cannot find first occurrence of {code} after removal")
        continue
    first_end = find_entry_end(content, first_pos)
    old_chunk = content[first_pos:first_end]
    print(f"  Replacing old entry at line {content[:first_pos].count(chr(10))+1}, length {len(old_chunk)} chars")
    content = content[:first_pos] + new_content + content[first_end:]

    print(f"  ✓ {code} done. File now {len(content.split(chr(10)))} lines")

# ============================================================
# Verify no more duplicates
# ============================================================
print("\nVerifying no duplicates remain:")
for code in ['77100', '79110', '82300', '49213', '49231', '52292']:
    import re
    count = len(re.findall(re.escape(f'  "{code}": {{'), content))
    print(f"  {code}: {count} occurrence(s) {'✓' if count == 1 else '*** ERROR ***'}")

with open('lib/kbli-gold-content.ts', 'w') as f:
    f.write(content)
print(f"\n✓ Written. Final: {len(content.split(chr(10)))} lines")
