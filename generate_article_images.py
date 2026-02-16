#!/usr/bin/env python3
"""Generate article cover images via Pollinations.AI (free, no API key needed)."""

import urllib.request
import urllib.parse
import time
import os
import sys

BASE_URL = "https://image.pollinations.ai/prompt/"
OUTPUT_BASE = "apps/mouth/public/static/insights"

IMAGES = [
    # BUSINESS / KBLI
    {
        "dir": "business",
        "filename": "kbli-2025-education-training.jpg",
        "prompt": "Open books transforming into tropical Bali starling birds flying upward, mathematical formulas and code snippets dissolving into sky, photorealistic digital art, cinematic lighting, sky blue leaf green paper cream accent red color palette",
    },
    {
        "dir": "business",
        "filename": "kbli-2025-agriculture-agritourism.jpg",
        "prompt": "Aerial view of Jatiluwih rice terraces Bali with abstract agricultural zone overlays in translucent colors, farmer silhouette blending with tech dashboard interface, photorealistic, rice green earth brown sky blue golden wheat palette",
    },
    {
        "dir": "business",
        "filename": "kbli-2025-manufacturing-production.jpg",
        "prompt": "Abstract factory interior with robotic arms weaving traditional Balinese textiles, industrial gears intermeshing with mandala patterns, cinematic photography, industrial silver deep red amber charcoal palette",
    },
    {
        "dir": "business",
        "filename": "kbli-2025-healthcare-wellness.jpg",
        "prompt": "Serene Bali spa setting with frangipani flowers overlaid with translucent medical molecule structures and DNA helix patterns, photorealistic, wellness green soft lavender white gold accents palette",
    },
    {
        "dir": "business",
        "filename": "kbli-2025-green-economy-waste.jpg",
        "prompt": "Lush tropical jungle reclaiming abstract recycling symbol, butterflies made of solar panels, vibrant hopeful digital art, rainforest green solar gold ocean blue earth brown palette",
    },
    {
        "dir": "business",
        "filename": "kbli-2025-future-proofing-flexibility.jpg",
        "prompt": "Balinese banyan tree with roots spreading into circuit board patterns underground, multiple branches leading to different business icons, digital art cinematic, ancient bark brown neon green shoots digital blue sunset purple palette",
    },
    {
        "dir": "business",
        "filename": "kbli-2025-brand-positioning-strategy.jpg",
        "prompt": "Chess board with pieces shaped like Balinese statues and modern corporate buildings, dramatic side lighting, professional photography, obsidian black gold deep crimson marble white palette",
    },
    {
        "dir": "business",
        "filename": "kbli-2025-environmental-permits-amdal.jpg",
        "prompt": "Split landscape pristine Bali coral reef below construction skyline above separated by glowing green compliance barrier, dramatic digital art, ocean blue coral pink regulatory green steel gray palette",
    },
    {
        "dir": "business",
        "filename": "kbli-2025-halal-certification-fnb.jpg",
        "prompt": "Elegant Indonesian food presentation with crescent moon and geometric Islamic patterns as abstract overlay, rich appetizing photography, deep green gold warm spice tones cream palette",
    },
    {
        "dir": "business",
        "filename": "kbli-2025-import-export-licenses.jpg",
        "prompt": "Container ship in Benoa harbor Bali with abstract flowing trade route lines connecting to world map dots, vibrant cargo containers, maritime photography, maritime navy container red port concrete ocean teal palette",
    },
    {
        "dir": "business",
        "filename": "kbli-2025-location-restrictions-bali.jpg",
        "prompt": "Bird eye view Bali coastline with abstract colored zoning overlays green for nature gold for tourism blue for commercial, dramatic graphic digital art, zone green zone gold zone blue ocean dark palette",
    },
    {
        "dir": "business",
        "filename": "kbli-2025-bali-transformation.jpg",
        "prompt": "Bali Uluwatu cliff temple at dawn with digital transformation waves radiating outward, traditional stone meets holographic business data, cinematic photography, dawn pink temple gray digital cyan gold palette",
    },
    {
        "dir": "business",
        "filename": "kbli-2025-gold-rush-migration.jpg",
        "prompt": "Abstract gold nuggets morphing into Indonesian Rupiah symbols set against modern Jakarta Bali skyline, rush of movement and energy, dynamic digital art, gold deep red black silver palette",
    },
    {
        "dir": "business",
        "filename": "beginners-guide-kbli-2025.jpg",
        "prompt": "Friendly compass rose made of colorful Indonesian batik patterns pointing toward simplified classification tree, welcoming approachable digital illustration, warm batik brown blue orange green cream palette",
    },
    {
        "dir": "business",
        "filename": "upgrading-indonesia-kbli-2025.jpg",
        "prompt": "Stairs made of stacked regulatory documents ascending through clouds toward glowing modern Indonesia 2025 badge, aspirational digital art, paper white step gray cloud blue badge gold palette",
    },
    {
        "dir": "business",
        "filename": "kbli-2025-new-codes-spotlight.jpg",
        "prompt": "Spotlight beam illuminating holographic display of new tech codes VR headset drone blockchain symbol floating above dark stage, cinematic, spotlight white hologram cyan stage black accent purple palette",
    },
    {
        "dir": "business",
        "filename": "kbli-2025-foreign-ownership-pma-guide.jpg",
        "prompt": "Two hands shaking one made of Indonesian batik fabric one of corporate suit fabric with ownership percentage meters floating between them, digital art, batik earth tones corporate navy gold white palette",
    },
    {
        "dir": "business",
        "filename": "kbli-2025-multi-code-strategy.jpg",
        "prompt": "Abstract Tetris blocks in different colors fitting together perfectly each block labeled with sector icon food tech hotel, vibrant digital art, each block different vibrant color against dark background",
    },
    {
        "dir": "business",
        "filename": "kbli-2025-tax-implications-klu.jpg",
        "prompt": "Calculator morphing into traditional Balinese offering canang sari with tax code numbers floating like incense smoke, surreal digital art, offering green number gold incense gray background warm palette",
    },
    {
        "dir": "business",
        "filename": "kbli-2025-capital-investment-requirements.jpg",
        "prompt": "Towering stack of golden coins IDR 10 Billion with modern PT PMA building growing from top like sprouting plant, digital art, gold coins green growth blue sky concrete palette",
    },
    {
        "dir": "business",
        "filename": "kbli-2025-oss-transition-update.jpg",
        "prompt": "Computer screen showing OSS portal interface rendered as Balinese painting style with intricate gold border details, modern meets traditional digital art, screen blue Balinese gold borders dark background palette",
    },
    {
        "dir": "business",
        "filename": "kbli-2025-license-permit-requirements.jpg",
        "prompt": "Multi-layered skeleton key where each tooth represents different permit level low medium high risk, floating in abstract space, digital art, key bronze risk-red gradient blue background green for low-risk palette",
    },
    {
        "dir": "business",
        "filename": "kbli-2025-red-flags-audit-risk.jpg",
        "prompt": "Dramatic red warning flag planted in field of green compliance checkmarks, storm clouds gathering behind, urgent attention-grabbing digital art, warning red compliance green storm gray lightning white palette",
    },
    {
        "dir": "business",
        "filename": "kbli-2025-visa-kitas-synergy.jpg",
        "prompt": "KITAS card and business license document merging into one holographic unified permit with synergy sparkle effects, digital art, document cream hologram blue sparkle gold background navy palette",
    },
    {
        "dir": "business",
        "filename": "kbli-2020-to-2025-migration-guide.jpg",
        "prompt": "Bridge made of regulatory documents spanning canyon with 2020 on one cliff and 2025 on other, sunrise over destination, cinematic digital art, canyon amber bridge white sunrise gold sky blue palette",
    },
    # IMMIGRATION / VISA
    {
        "dir": "immigration",
        "filename": "e25b-director-kitas-guide.jpg",
        "prompt": "Confident silhouette standing at floor-to-ceiling office window overlooking Bali coastline with translucent KITAS card hologram floating beside them, cinematic photography, power navy gold accents ocean blue warm light palette",
    },
    {
        "dir": "immigration",
        "filename": "e23-employee-kitas-guide.jpg",
        "prompt": "Open modern workspace Bali co-working hub multiple desks each with small floating work permit icon, collaborative energy, bright photography, workspace white employee blue plant green wood warm palette",
    },
    {
        "dir": "immigration",
        "filename": "e33g-remote-worker-visa-guide.jpg",
        "prompt": "Laptop on beanbag in bamboo beach cabana Bali with WiFi signal waves emanating outward turning into tropical flowers, digital nomad paradise, bamboo natural digital blue tropical pink sand gold palette",
    },
    {
        "dir": "immigration",
        "filename": "e28a-investor-kitas-guide.jpg",
        "prompt": "Golden key unlocking door shaped like Indonesia map outline revealing lush investment landscape behind, rich aspirational digital art, key gold door teak brown landscape green sky blue palette",
    },
    {
        "dir": "immigration",
        "filename": "rptka-foreign-worker-plan-guide.jpg",
        "prompt": "Organizational chart flowing like river through Indonesian government buildings with worker silhouettes at each node, systematic clear illustration, flow blue government cream worker teal accent red palette",
    },
    {
        "dir": "immigration",
        "filename": "kitas-extension-renewal-guide.jpg",
        "prompt": "Clock face where each hour mark is different document icon with hands approaching midnight deadline, urgency meets organization, cinematic, clock gold deadline red document white background midnight blue palette",
    },
    {
        "dir": "immigration",
        "filename": "kitas-transfer-change-sponsor.jpg",
        "prompt": "Two corporate buildings exchanging glowing KITAS document via abstract bridge of light, transfer in motion, digital art, building gray transfer gold bridge light cyan sky purple palette",
    },
    {
        "dir": "immigration",
        "filename": "kitas-cancellation-company-closure.jpg",
        "prompt": "Building gently dissolving into origami paper cranes flying away representing graceful closure, bittersweet beautiful digital art, building concrete crane white sunset amber sky lavender palette",
    },
    {
        "dir": "immigration",
        "filename": "kitas-upgrade-downgrade-conversion.jpg",
        "prompt": "Abstract isometric staircase with ascending and descending directions each step different visa type card, digital art, steps gradient from green upgrade to amber maintain to blue convert palette",
    },
    {
        "dir": "immigration",
        "filename": "kitas-renewal-denied-common-reasons.jpg",
        "prompt": "Red stamp DENIED cracking like glass with light breaking through cracks revealing solution path, dramatic hopeful digital art, stamp red glass shatter white light gold background dark palette",
    },
    {
        "dir": "immigration",
        "filename": "e33f-spouse-dependent-kitas-guide.jpg",
        "prompt": "Two wedding rings interlinked one transforming into visa document, frangipani flowers soft Bali temple background, romantic digital art, ring gold love rose document cream temple stone palette",
    },
    {
        "dir": "immigration",
        "filename": "e33e-child-dependent-kitas-guide.jpg",
        "prompt": "Child hand holding parent hand rendered as warm silhouettes with playful visa document elements floating like butterflies, gentle digital art, warm sunset silhouette amber butterfly pastel sky soft blue palette",
    },
    {
        "dir": "immigration",
        "filename": "e311a-retirement-visa-kitas-guide.jpg",
        "prompt": "Hammock between two palm trees with laptop and iced coffee overlooking serene Bali rice terrace, relaxed established lifestyle photography, palm green hammock natural rice terrace gold sky coral palette",
    },
    {
        "dir": "immigration",
        "filename": "kitap-permanent-residence-guide.jpg",
        "prompt": "House with deep roots growing into Indonesian soil with permanent HOME beacon light on top, stability belonging digital art, house warm wood roots earth brown beacon gold soil rich red palette",
    },
    {
        "dir": "immigration",
        "filename": "golden-visa-indonesia-complete-guide.jpg",
        "prompt": "Luxurious gold-embossed visa floating above Indonesia archipelago map with golden particles streaming upward, premium exclusive digital art, pure gold deep navy archipelago emerald cream palette",
    },
    {
        "dir": "immigration",
        "filename": "e-voa-electronic-visa-on-arrival-guide.jpg",
        "prompt": "Smartphone screen showing QR code transforming into boarding pass set against Ngurah Rai airport Balinese architecture, phone black QR teal airport stone arrival warm palette",
    },
    {
        "dir": "immigration",
        "filename": "stm-exit-reentry-permit-guide.jpg",
        "prompt": "Airplane taking off through translucent permit card gate with Bali visible below and destination clouds ahead, freedom with compliance, sky gradient blue plane silver permit gold island green palette",
    },
    {
        "dir": "immigration",
        "filename": "visa-overstay-penalties-indonesia-guide.jpg",
        "prompt": "Ticking time bomb made of stacked Indonesian Rupiah banknotes 1 million per day with visa expiration date visible, urgent impactful digital art, warning red money green time black explosion orange palette",
    },
    {
        "dir": "immigration",
        "filename": "wajib-lapor-reporting-obligations-guide.jpg",
        "prompt": "Checklist transforming into Balinese kite rising into sky compliance as freedom each checkmark colorful ribbon tail, digital art, checklist blue kite multicolor sky clear ribbon red gold green palette",
    },
    {
        "dir": "immigration",
        "filename": "passport-renewal-active-kitas-guide.jpg",
        "prompt": "Two passport booklets old faded and new crisp connected by golden chain link KITAS continuity set against Bali immigration office, passport navy chain gold old fade sepia new crisp blue palette",
    },
    {
        "dir": "immigration",
        "filename": "b211-social-cultural-visit-visa-guide.jpg",
        "prompt": "Vibrant collage of Bali cultural elements gamelan instruments dance mask temple ceremony art class arranged in visa-shaped frame, cultural gold ceremony white art vibrant mix frame teal palette",
    },
    {
        "dir": "immigration",
        "filename": "business-visit-vs-work-visa-indonesia-guide.jpg",
        "prompt": "Balance scale with briefcase on one side and hard hat on other perfectly balanced on Bali stone pedestal, clear visual metaphor photography, scale bronze briefcase black hard hat orange stone gray palette",
    },
    {
        "dir": "immigration",
        "filename": "multiple-entry-vs-single-entry-visa-indonesia.jpg",
        "prompt": "Single ornate Balinese door on left versus corridor of multiple doors receding into perspective on right, architectural photography, door teak corridor gradient gold floor marble wall warm palette",
    },
    {
        "dir": "immigration",
        "filename": "border-runs-indonesia-reality-check-2026.jpg",
        "prompt": "Worn suitcase on treadmill going nowhere with STOP sign and better path highlighted to the side, honest ironic digital art, suitcase brown treadmill gray stop red better path green palette",
    },
    {
        "dir": "immigration",
        "filename": "visa-free-vs-evoa-indonesia-comparison.jpg",
        "prompt": "Two parallel paths through Balinese split gate one labeled FREE short one labeled E-VOA longer with perks, digital art, free path green evoa path blue gate stone sky orange palette",
    },
    {
        "dir": "immigration",
        "filename": "tourist-visa-extension-indonesia-guide.jpg",
        "prompt": "Hourglass filled with tropical Bali sand grains transforming into calendar days as they fall, time running out beautifully, hourglass gold sand warm calendar white background ocean blue palette",
    },
    {
        "dir": "immigration",
        "filename": "emergency-visa-procedures-indonesia-guide.jpg",
        "prompt": "Red cross medical symbol merged with immigration officer badge set against dramatic stormy to clear sky transition, help in crisis digital art, emergency red badge silver storm dark clearing gold palette",
    },
    {
        "dir": "immigration",
        "filename": "immigration-checks-documents-carry-indonesia.jpg",
        "prompt": "Neat wallet document holder splayed open revealing passport KITAS card and supporting documents arranged like survival kit, leather warm brown document whites card blue KITAS gold palette",
    },
    {
        "dir": "immigration",
        "filename": "indonesia-immigration-blacklist-guide.jpg",
        "prompt": "Dark door with red X gradually being opened by golden key labeled APPEAL, dramatic chiaroscuro lighting, door black X red key gold light warm behind door palette",
    },
    {
        "dir": "immigration",
        "filename": "ina-digital-immigration-indonesia-2026.jpg",
        "prompt": "Futuristic holographic interface showing Indonesia INA Digital system biometric scan digital visa QR check-in floating above sleek modern desk, hologram cyan digital purple interface white desk dark palette",
    },
    # TAX & COMPLIANCE
    {
        "dir": "tax-legal",
        "filename": "coretax-login-errors-fixes-2026.jpg",
        "prompt": "Cracked computer screen displaying cryptic error codes with golden wrench emerging from cracks fixing them, digital rain of tax numbers background, error red fix gold screen blue-black code green palette",
    },
    {
        "dir": "tax-legal",
        "filename": "coretax-npwp16-vs-npwp15-foreigners.jpg",
        "prompt": "Two ID cards floating side by side old faded 15-digit NPWP card morphing into sleek new 16-digit NIK card, transition particles flowing between them, old card sepia new card modern blue transition particles gold background dark navy palette",
    },
    {
        "dir": "tax-legal",
        "filename": "coretax-vs-djp-online-what-changed.jpg",
        "prompt": "Dramatic before after split left side cluttered old government website with paper stacks right side clean modern CoreTax interface with holographic elements, old side dusty gray-brown new side crystal blue and white palette",
    },
    {
        "dir": "tax-legal",
        "filename": "tax-amnesty-indonesia-history.jpg",
        "prompt": "Timeline ribbon flowing through dramatic Indonesian landscapes from 2016 volcanic eruption energy through 2022 calm waters to 2026 question mark in clouds, historical gravitas, timeline gold 2016 fiery red 2022 calm blue 2026 mysterious purple palette",
    },
    {
        "dir": "tax-legal",
        "filename": "pph-25-monthly-installments-guide.jpg",
        "prompt": "Twelve stepping stones across river each representing a month with IDR coin stacks on each stone, business figure balancing their way across, river blue stones gray coins gold figure navy nature green palette",
    },
    {
        "dir": "tax-legal",
        "filename": "pph-29-annual-settlement-guide.jpg",
        "prompt": "Massive balance scale at year-end one side holds year of paid installments gold coins other holds actual tax liability red ledger, lightning crackling at pivot point, scale bronze coins gold ledger red lightning white background midnight palette",
    },
]


def generate_image(prompt: str, output_path: str) -> bool:
    """Download image from Pollinations.AI."""
    encoded = urllib.parse.quote(prompt)
    url = f"{BASE_URL}{encoded}?width=1200&height=630&seed=42&nologo=true&model=flux"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as response:
            data = response.read()
            if len(data) < 1000:
                print(f"  ERROR: response too small ({len(data)} bytes)")
                return False
            with open(output_path, "wb") as f:
                f.write(data)
            print(f"  OK ({len(data)//1024}KB)")
            return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    total = len(IMAGES)
    success = 0
    failed = []

    start_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    for i, img in enumerate(IMAGES):
        if i < start_idx:
            continue

        output_dir = f"{OUTPUT_BASE}/{img['dir']}"
        os.makedirs(output_dir, exist_ok=True)
        output_path = f"{output_dir}/{img['filename']}"

        # Skip if already exists
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            print(f"[{i+1}/{total}] SKIP (exists): {img['filename']}")
            success += 1
            continue

        print(f"[{i+1}/{total}] Generating: {img['filename']}", end=" ", flush=True)
        if generate_image(img["prompt"], output_path):
            success += 1
        else:
            failed.append(img["filename"])

        # Rate limit: 1 request every 3 seconds
        if i < total - 1:
            time.sleep(3)

    print(f"\n{'='*50}")
    print(f"Done: {success}/{total} generated")
    if failed:
        print(f"Failed ({len(failed)}):")
        for f in failed:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
