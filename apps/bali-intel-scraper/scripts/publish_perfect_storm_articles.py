#!/usr/bin/env python3
"""
Publish Bali 2026 Perfect Storm Articles
Based on BaliZero Strategic Report - January 2026
"""

import asyncio
import httpx
from datetime import datetime
from typing import List, Dict

API_URL = "https://nuzantara-rag.fly.dev"

# ============================================================================
# ARTICLE 1: BALI'S PERFECT STORM - OVERVIEW
# ============================================================================
ARTICLE_1 = {
    "title": "Bali's Perfect Storm: Why 2026 Demands a New Playbook",
    "summary": "Three converging crises are reshaping Bali. Here's what expats and investors need to know to navigate the transition.",
    "content": """# Bali's Perfect Storm: Why 2026 Demands a New Playbook

---

## ⚡ THE 30-SECOND BRIEF

> **Should I worry?** Yes — but preparation beats panic.

- 🎯 **What:** Three simultaneous crises (environmental, infrastructure, policy) are forcing Bali into rapid transition
- 👤 **Who this affects:** All expats, investors, and long-term residents
- 📅 **When:** Active now through Q2 2026
- ⚠️ **Risk Level:** HIGH

---

## 📋 THE FACTS

Bali is not merely recovering from the pandemic — it's undergoing a forced structural transformation. While tourism numbers exceed 2019 levels, this abundance has triggered systemic fragility.

**The Three Vectors:**

| Vector | Crisis | Timeline |
|--------|--------|----------|
| Environmental | TPA Suwung landfill closure | Dec 23, 2025 |
| Infrastructure | Naval blockades, 4m waves | Until Jan 15, 2026 |
| Policy | "Quality Tourism" shift | Ongoing enforcement |

**Key Numbers:**
- 1,000+ tons/day of waste with no destination
- 636 confirmed dengue cases at Wangaya Hospital
- 65% non-compliance rate on tourism levy ($10M shortfall)
- 40-75% entertainment tax under Pajak Hiburan

The Provincial Government is simultaneously tackling destination degradation through regulatory tightening. The era of unregulated growth is over.

---

## 🧠 THE BALI ZERO TAKE

**What They Don't Tell You:**
This isn't a temporary crisis — it's a permanent reset. The government is deliberately using this convergence to accelerate reforms they've wanted for years.

**Our Analysis:**
The "Perfect Storm" is actually three overlapping storms with different timelines. Environmental issues (waste, dengue) peak in Q1-Q2 2026. Policy changes (taxation, compliance) are permanent. Infrastructure disruptions (blockades) are seasonal but will recur.

**Our Advice:**
Don't wait for "things to go back to normal." They won't. Build your 2026 strategy around the new reality: higher compliance costs, stricter enforcement, and premium on quality over quantity.

---

## 🚀 NEXT STEPS

### If you're a traveler:
1. ✅ Ensure financial documentation is ready (bank statements)
2. ✅ Pay tourism levy BEFORE arrival (keep QR receipt)
3. ✅ Build 2-3 day buffers for maritime connections
4. 🔔 Monitor weather/blockade updates for island-hopping

### If you're an investor/resident:
1. ✅ Review all licenses (Pondok Wisata, PBG, OSS)
2. ✅ Update KBLI codes before March 2026 deadline
3. ✅ Conduct zoning due diligence on any property
4. 🔔 Track Pajak Hiburan developments if in hospitality

---

## 🔗 RESOURCES

- 📄 [Full Crisis Timeline](/news/bali-2026-timeline)
- 💬 [Book Strategic Consultation](/contact)

---

**Category:** lifestyle
**Priority:** high
**Tags:** bali 2026, crisis, regulatory, transition, expat guide
**Source:** BaliZero Strategic Analysis
**Last Updated:** January 2026
""",
    "source": "BaliZero Intelligence",
    "source_url": "https://balizero.com/reports/perfect-storm-2026",
    "category": "lifestyle",
    "priority": "high",
    "image_url": "https://images.unsplash.com/photo-1537996194471-e657df975ab4?w=1200&h=630&fit=crop",
    "external_id": "bz-perfect-storm-2026-overview",
}

# ============================================================================
# ARTICLE 2: SUWUNG LANDFILL CRISIS
# ============================================================================
ARTICLE_2 = {
    "title": "Suwung Landfill Closure: The Waste Crisis Hitting Bali's Tourist Zones",
    "summary": "TPA Suwung permanently closed Dec 23. Over 1,000 tons of daily waste now has nowhere to go. Here's what's happening.",
    "content": """# Suwung Landfill Closure: The Waste Crisis Hitting Bali's Tourist Zones

---

## ⚡ THE 30-SECOND BRIEF

> **Should I worry?** Yes — visible impact in tourist areas.

- 🎯 **What:** Bali's main landfill permanently closed due to fire and landslide risk
- 👤 **Who this affects:** Denpasar, Badung residents, Seminyak/Kuta visitors
- 📅 **When:** December 23, 2025 (permanent)
- ⚠️ **Risk Level:** HIGH

---

## 📋 THE FACTS

TPA Suwung, Bali's primary landfill serving Denpasar and Badung, permanently closed on December 23, 2025 due to fire and landslide risk. The facility handled over 1,000 tons of waste per day.

**The Immediate Reality:**
- Decentralized TPST facilities failed to meet ramp-up timelines
- Waste is currently "stranded" in spontaneous dumps along main roads
- Drainage canals are clogging, increasing flood risk
- The Bangli revolt: mountain villages refuse to become "Denpasar's dustbin"

**The Logistics Nightmare:**
The backup plan required 190 heavy trucks/day traveling 58km uphill (2 hours each way) to Bangli. Local Banjar (villages) are threatening physical road blockades.

> "Bangli will not become Denpasar's dustbin." — Made Joko Arnawa, Bangli DPRD Member

**Impact Timeline:**
| Week | Effect |
|------|--------|
| 1-2 | Roadside accumulation begins |
| 3-4 | Drainage systems compromised |
| 5+ | Flash flood risk escalates |

---

## 🧠 THE BALI ZERO TAKE

**What They Don't Tell You:**
This closure was scheduled for 2027. It was accelerated by 2 years due to critical structural failures. There is no Plan B ready.

**Our Analysis:**
The waste crisis intersects with rainy season (Oct 2025 - May 2026), creating a multiplier effect. Expect visible waste in tourist areas, particularly Seminyak and Legian. Some restaurants and hotels are already implementing emergency waste management.

**Our Advice:**
If you're renting property, confirm your landlord has private waste collection arrangements. For businesses, document your waste management compliance — enforcement sweeps are coming.

---

## 🚀 NEXT STEPS

### If you're a resident:
1. ✅ Verify your waste collection service is operational
2. ✅ Consider private waste management contracts
3. 🔔 Monitor flood warnings for Seminyak/Legian areas

### If you're a business owner:
1. ✅ Document waste management compliance
2. ✅ Secure backup collection services
3. ✅ Brief staff on hygiene protocols

---

## 🔗 RESOURCES

- 📄 [Dengue Prevention Guide](/news/dengue-alert-2026)
- 💬 [Contact BaliZero](/contact)

---

**Category:** lifestyle
**Priority:** high
**Tags:** waste crisis, suwung, environment, seminyak, infrastructure
**Source:** BaliZero Intelligence
**Last Updated:** January 2026
""",
    "source": "BaliZero Intelligence",
    "source_url": "https://balizero.com/reports/suwung-crisis",
    "category": "lifestyle",
    "priority": "high",
    "image_url": "https://images.unsplash.com/photo-1532996122724-e3c354a0b15b?w=1200&h=630&fit=crop",
    "external_id": "bz-suwung-crisis-2026",
}

# ============================================================================
# ARTICLE 3: DENGUE ALERT 2026
# ============================================================================
ARTICLE_3 = {
    "title": "Dengue Alert 2026: 636 Cases and Rising — What Expats Need to Know",
    "summary": "Wangaya Hospital reports 636 confirmed cases. Epidemic peak expected through April. Here's how to protect yourself.",
    "content": """# Dengue Alert 2026: 636 Cases and Rising — What Expats Need to Know

---

## ⚡ THE 30-SECOND BRIEF

> **Should I worry?** Yes — take immediate precautions.

- 🎯 **What:** Aggressive dengue resurgence, epidemic peak through April
- 👤 **Who this affects:** All residents, especially in South Bali
- 📅 **When:** January - April 2026 (peak risk)
- ⚠️ **Risk Level:** HIGH

---

## 📋 THE FACTS

Wangaya Hospital has confirmed 636 dengue cases in January 2026 alone. Health authorities anticipate epidemic levels to continue through April due to early onset of rainy season.

**Why Now?**
The waste crisis has created perfect breeding conditions for *Aedes aegypti* mosquitoes:
- Uncollected waste = stagnant water pools
- Clogged drainage canals = standing water
- Peak rainfall (Oct 2025 - May 2026) = multiplier effect

**High-Risk Zones:**
- Seminyak
- Legian
- Canggu (coastal areas with drainage issues)

**Warning Signs to Monitor:**
| Symptom | Action |
|---------|--------|
| Sudden high fever (39-40°C) | Seek immediate testing |
| Retro-orbital pain (behind eyes) | Do NOT delay |
| Skin rashes (day 3-4) | Hospital assessment needed |
| Severe joint pain | Emergency if combined with bleeding |

---

## 🧠 THE BALI ZERO TAKE

**What They Don't Tell You:**
Dengue is not "just a bad flu." Severe dengue (DHF) can be fatal within 24-48 hours if not properly managed. The key is early detection via NS1 antigen test.

**Our Analysis:**
Expat clinics are seeing a 300% increase in dengue consultations. The good news: Bali's hospitals are experienced with dengue management. The bad news: wait times are increasing. Private clinics offer faster testing.

**Our Advice:**
Do NOT wait to see if symptoms improve. Get NS1 antigen testing within the first 3 days of fever onset. After day 5, the NS1 test becomes unreliable and you need IgM/IgG antibody tests.

---

## 🚀 NEXT STEPS

### Immediate prevention:
1. ✅ Use mosquito repellent with DEET (especially 6-8 AM, 4-6 PM)
2. ✅ Eliminate standing water around your property
3. ✅ Install/repair window screens
4. ✅ Sleep under mosquito nets if no AC

### If you develop fever:
1. ✅ Get NS1 antigen test immediately (within 72 hours)
2. ✅ Stay hydrated — dengue causes severe dehydration
3. ❌ Do NOT take aspirin or ibuprofen (increases bleeding risk)
4. ✅ Take paracetamol only for fever management

### Recommended clinics for testing:
- BIMC Hospital (Kuta, Nusa Dua)
- Siloam Hospital (Denpasar)
- Kasih Ibu Hospital (Denpasar)

---

## 🔗 RESOURCES

- 📄 [Waste Crisis Connection](/news/suwung-landfill-closure)
- 💬 [Emergency Contacts](/contact)

---

**Category:** lifestyle
**Priority:** high
**Tags:** dengue, health, epidemic, mosquito, prevention
**Source:** BaliZero Intelligence + Wangaya Hospital Data
**Last Updated:** January 2026
""",
    "source": "BaliZero Intelligence",
    "source_url": "https://balizero.com/reports/dengue-alert-2026",
    "category": "lifestyle",
    "priority": "high",
    "image_url": "https://images.unsplash.com/photo-1584362917165-526a968ae4d0?w=1200&h=630&fit=crop",
    "external_id": "bz-dengue-alert-2026",
}

# ============================================================================
# ARTICLE 4: MARITIME CHAOS
# ============================================================================
ARTICLE_4 = {
    "title": "Maritime Chaos: Komodo Blockade Strands Thousands — Plan Your Buffer",
    "summary": "Total maritime suspension until Jan 15. Valencia coach missing after vessel sinking. Avoid tight connections.",
    "content": """# Maritime Chaos: Komodo Blockade Strands Thousands — Plan Your Buffer

---

## ⚡ THE 30-SECOND BRIEF

> **Should I worry?** Depends on your travel plans.

- 🎯 **What:** Complete maritime suspension to Labuan Bajo/Komodo
- 👤 **Who this affects:** Anyone planning Komodo trips or Lombok connections
- 📅 **When:** Until January 15, 2026 (weather permitting)
- ⚠️ **Risk Level:** HIGH for island-hopping itineraries

---

## 📋 THE FACTS

All maritime operations to Labuan Bajo and Komodo National Park are suspended until January 15, 2026. Thousands of tourists are stranded.

**Current Conditions:**
- Waves up to 4 meters in Lombok Strait
- Fast boat services completely cancelled
- Slow ferry services suspended
- Flight-only access to Labuan Bajo (limited capacity)

**The Incident:**
A tourist vessel sank in Komodo waters. A foreign national (Valencia football coach) has been missing for over 8 days. Criminal investigation ongoing.

**Affected Routes:**
| Route | Status | Alternative |
|-------|--------|-------------|
| Bali → Lombok (boat) | Suspended | Fly (30 min) |
| Lombok → Gili Islands | Suspended | Wait or cancel |
| Bali → Labuan Bajo (boat) | Suspended | Fly (1.5 hrs) |
| Labuan Bajo → Komodo | Suspended | None available |

---

## 🧠 THE BALI ZERO TAKE

**What They Don't Tell You:**
Maritime blockades are now annual events during peak rainy season. January 2025 saw similar disruptions. This is the new normal.

**Our Analysis:**
Tour operators often sell Komodo packages without weather disclaimers. Many travelers have non-refundable bookings. Insurance coverage varies — most basic policies exclude weather cancellations.

**Our Advice:**
For any itinerary involving maritime transfers, build 2-3 day buffers on each end. Do not book same-day connections from boat to flight. Consider travel insurance that explicitly covers weather-related cancellations.

---

## 🚀 NEXT STEPS

### If you're currently stranded:
1. ✅ Contact your tour operator for rescheduling
2. ✅ Check flight availability (Labuan Bajo airport open)
3. ✅ Document all delays for insurance claims
4. ✅ Monitor official BMKG weather updates

### If you're planning future travel:
1. ✅ Avoid Komodo trips during Dec-Feb peak monsoon
2. ✅ Book flexible/refundable accommodations
3. ✅ Purchase comprehensive travel insurance
4. ✅ Build 3-day minimum buffers for island connections

### Weather monitoring:
- BMKG (Indonesian Meteorological Agency): bmkg.go.id
- Windy.com for real-time wave forecasts

---

## 🔗 RESOURCES

- 📄 [Bali 2026 Crisis Overview](/news/balis-perfect-storm)
- 💬 [Contact BaliZero](/contact)

---

**Category:** lifestyle
**Priority:** high
**Tags:** komodo, maritime, blockade, travel, weather, safety
**Source:** BaliZero Intelligence
**Last Updated:** January 2026
""",
    "source": "BaliZero Intelligence",
    "source_url": "https://balizero.com/reports/maritime-chaos",
    "category": "lifestyle",
    "priority": "high",
    "image_url": "https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=1200&h=630&fit=crop",
    "external_id": "bz-maritime-chaos-2026",
}

# ============================================================================
# ARTICLE 5: PAJAK HIBURAN TAX
# ============================================================================
ARTICLE_5 = {
    "title": "The 40-75% Tax Shock: What Pajak Hiburan Means for Beach Clubs and Nightlife",
    "summary": "New entertainment tax rates hit hospitality hard. Beach clubs face double taxation disputes. Industry threatens legal challenge.",
    "content": """# The 40-75% Tax Shock: What Pajak Hiburan Means for Beach Clubs and Nightlife

---

## ⚡ THE 30-SECOND BRIEF

> **Should I worry?** Yes, if you own or invest in hospitality/entertainment.

- 🎯 **What:** Entertainment tax (Pajak Hiburan) rates of 40-75% under Law 1/2022
- 👤 **Who this affects:** Nightclubs, karaoke, spas, beach clubs
- 📅 **When:** Enforcement active now
- ⚠️ **Risk Level:** HIGH for affected businesses

---

## 📋 THE FACTS

Under Law No. 1/2022 (HKPD), local governments can impose entertainment taxes between 40% and 75% on specific categories.

**Tax Rate Comparison:**
| Business Type | Tax Rate |
|---------------|----------|
| Standard restaurant/dining | 10% |
| Entertainment (nightclub, karaoke) | 40-75% |
| Spa with entertainment elements | 40-75% |
| Beach club (disputed) | 10% or 40-75%? |

**The Beach Club Dilemma:**
Venues mixing dining and DJ performances face a gray area. Are they restaurants (10%) or entertainment venues (40-75%)? Tax authorities are increasingly classifying them as entertainment.

**Industry Response:**
- PHRI (Hotel and Restaurant Association) threatening constitutional challenge
- Celebrity lawyer Hotman Paris publicly opposing the rates
- Some venues considering relocation to other provinces

---

## 🧠 THE BALI ZERO TAKE

**What They Don't Tell You:**
This isn't new legislation — Law 1/2022 has been on the books for years. What's new is enforcement. Cash-strapped local governments see entertainment venues as easy revenue targets.

**Our Analysis:**
The real risk is double taxation. A beach club could face: (1) 10% dining tax on food, (2) 40-75% entertainment tax on cover charges and events, plus (3) 11% VAT on everything. Combined effective rates could exceed 80%.

**Our Advice:**
If you're investing in hospitality, get tax classification in writing BEFORE committing capital. Restructure operations to clearly separate dining from entertainment. Consider the shadow economy risk — many competitors will simply underreport.

---

## 🚀 NEXT STEPS

### If you own an entertainment venue:
1. ✅ Get formal tax classification ruling from local government
2. ✅ Restructure billing to separate dining from entertainment
3. ✅ Consult with tax specialist on compliance strategy
4. 🔔 Monitor constitutional challenge progress

### If you're investing in hospitality:
1. ✅ Include tax risk in due diligence
2. ✅ Verify target's current tax compliance status
3. ✅ Model scenarios at full 75% entertainment rate
4. ✅ Consider alternative provinces with lower rates

### If you're a consumer:
- Expect higher prices at beach clubs and nightlife venues
- "Service charge" and "entertainment tax" line items increasing

---

## 🔗 RESOURCES

- 📄 [PT PMA Setup Guide](/guides/pt-pma)
- 💬 [Tax Consultation](/contact)

---

**Category:** tax
**Priority:** high
**Tags:** pajak hiburan, entertainment tax, beach club, nightlife, HKPD
**Source:** BaliZero Intelligence
**Last Updated:** January 2026
""",
    "source": "BaliZero Intelligence",
    "source_url": "https://balizero.com/reports/pajak-hiburan",
    "category": "tax",
    "priority": "high",
    "image_url": "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=1200&h=630&fit=crop",
    "external_id": "bz-pajak-hiburan-2026",
}

# ============================================================================
# ARTICLE 6: PROPERTY GREEN ZONE ALERT
# ============================================================================
ARTICLE_6 = {
    "title": "Property Alert: Green Zone Crackdown and the End of Easy Villa Permits",
    "summary": "Strict enforcement of Lahan Sawah Dilindungi. PBG denials for commercial projects on green land. Zoning due diligence now mandatory.",
    "content": """# Property Alert: Green Zone Crackdown and the End of Easy Villa Permits

---

## ⚡ THE 30-SECOND BRIEF

> **Should I worry?** Yes, if you're buying or building property.

- 🎯 **What:** Strict enforcement of protected agricultural land (Lahan Sawah Dilindungi)
- 👤 **Who this affects:** Property buyers, villa developers, short-term rental operators
- 📅 **When:** Active enforcement now, OTA compliance deadline March 2026
- ⚠️ **Risk Level:** HIGH for non-compliant properties

---

## 📋 THE FACTS

The Bali government is strictly enforcing "Green Zone" designations under Lahan Sawah Dilindungi (Protected Agricultural Land) regulations.

**What's Changing:**

| Before | Now |
|--------|-----|
| PBG approvals on green land common | PBG denials for commercial projects |
| Enforcement was lax | Demolition orders being issued |
| "Everyone does it" tolerance | Zero tolerance stance |

**Market Shift:**
- Decline in speculative tourist villa demand
- Rise in quality residential homes (Tabanan, North Canggu)
- Premium on properly zoned land increasing

**The Compliance Trap (March 2026):**

Short-term rentals face a double deadline:
1. **Pondok Wisata license** required for legal operation
2. **OTA cross-referencing** — Airbnb/Booking data being matched with tax records

Penalty: Fines and/or closure for unlicensed villas.

**For PT PMA Companies:**
- Mandatory update of OSS systems to KBLI 2025 codes
- Non-compliance = freezing of import licenses, work visas, operational permits

---

## 🧠 THE BALI ZERO TAKE

**What They Don't Tell You:**
Many properties sold to foreigners in the last 5 years are on improperly zoned land. Some have PBGs that were issued incorrectly — these are now being reviewed and revoked.

**Our Analysis:**
The "flip" era is over. Quick-buy-renovate-sell strategies that ignored zoning are increasingly risky. We're seeing deals collapse at due diligence when zoning issues surface. The premium for clean, properly-zoned land is now 20-30% higher than 2024.

**Our Advice:**
Zoning due diligence is no longer optional — it's mandatory. Before ANY capital commitment: (1) verify land classification, (2) confirm PBG validity, (3) check for ongoing disputes. Budget 2-3 weeks for proper due diligence.

---

## 🚀 NEXT STEPS

### If you're buying property:
1. ✅ Hire independent surveyor to verify zoning classification
2. ✅ Check PBG status at local Dinas PUPR
3. ✅ Verify no demolition orders or disputes pending
4. ✅ Get legal opinion on land status before deposit

### If you own a villa/rental:
1. ✅ Verify Pondok Wisata license status
2. ✅ Ensure OTA listings match tax declarations
3. ✅ Prepare for March 2026 compliance sweep
4. 🔔 Consider regularization if currently unlicensed

### If you have a PT PMA:
1. ✅ Update OSS to KBLI 2025 codes immediately
2. ✅ Verify all operational permits current
3. ✅ Cross-check NIB status

---

## 🔗 RESOURCES

- 📄 [PT PMA Setup Guide](/guides/pt-pma)
- 📄 [Pondok Wisata Registration](/guides/pondok-wisata)
- 💬 [Property Due Diligence Service](/contact)

---

**Category:** property
**Priority:** high
**Tags:** property, green zone, PBG, zoning, villa, compliance, OSS
**Source:** BaliZero Intelligence
**Last Updated:** January 2026
""",
    "source": "BaliZero Intelligence",
    "source_url": "https://balizero.com/reports/green-zone-crackdown",
    "category": "property",
    "priority": "high",
    "image_url": "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=1200&h=630&fit=crop",
    "external_id": "bz-property-green-zone-2026",
}

# ============================================================================
# ALL ARTICLES
# ============================================================================
ALL_ARTICLES = [
    ARTICLE_1,
    ARTICLE_2,
    ARTICLE_3,
    ARTICLE_4,
    ARTICLE_5,
    ARTICLE_6,
]


async def publish_articles(articles: List[Dict], dry_run: bool = False):
    """Publish articles to the news API"""

    results = {"success": 0, "failed": 0, "duplicates": 0}

    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, article in enumerate(articles, 1):
            print(f"\n[{i}/{len(articles)}] Publishing: {article['title'][:50]}...")

            if dry_run:
                print(f"  [DRY RUN] Would publish to {API_URL}/api/news")
                results["success"] += 1
                continue

            payload = {
                "title": article["title"],
                "summary": article["summary"],
                "content": article["content"],
                "source": article["source"],
                "source_url": article["source_url"],
                "category": article["category"],
                "priority": article["priority"],
                "image_url": article["image_url"],
                "external_id": article["external_id"],
                "published_at": datetime.utcnow().isoformat(),
            }

            try:
                response = await client.post(
                    f"{API_URL}/api/news",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("duplicate"):
                        print(f"  ⏭️ Duplicate (already exists)")
                        results["duplicates"] += 1
                    else:
                        slug = data.get("data", {}).get("slug", "unknown")
                        print(f"  ✅ Published! Slug: {slug}")
                        results["success"] += 1
                else:
                    print(f"  ❌ Error: {response.status_code} - {response.text[:100]}")
                    results["failed"] += 1

            except Exception as e:
                print(f"  ❌ Exception: {e}")
                results["failed"] += 1

            # Brief pause between requests
            await asyncio.sleep(0.5)

    return results


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Publish Perfect Storm articles")
    parser.add_argument("--dry-run", action="store_true", help="Preview without publishing")
    args = parser.parse_args()

    print("=" * 60)
    print("BALIZERO PERFECT STORM ARTICLES PUBLISHER")
    print("=" * 60)
    print(f"\nArticles to publish: {len(ALL_ARTICLES)}")
    print(f"Target API: {API_URL}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")

    for i, article in enumerate(ALL_ARTICLES, 1):
        print(f"  {i}. [{article['category'].upper()}] {article['title'][:50]}...")

    results = await publish_articles(ALL_ARTICLES, dry_run=args.dry_run)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"✅ Published: {results['success']}")
    print(f"⏭️ Duplicates: {results['duplicates']}")
    print(f"❌ Failed: {results['failed']}")


if __name__ == "__main__":
    asyncio.run(main())
