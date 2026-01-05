# Blueprints Section - Complete Documentation

## 📋 Table of Contents

1. [Overview](#overview)
2. [Data Structure](#data-structure)
3. [Google Drive Integration](#google-drive-integration)
4. [Adding New Blueprints](#adding-new-blueprints)
5. [Categories & KBLI Classification](#categories--kbli-classification)
6. [Indonesian & Bisnis Versions](#indonesian--bisnis-versions)
7. [Icons Reference](#icons-reference)
8. [Deployment](#deployment)

---

## Overview

**What are Blueprints?**

Blueprints are comprehensive business setup guides based on **KBLI (Klasifikasi Baku Lapangan Usaha Indonesia)** business classifications as defined in **PP 28/2025** (Peraturan Pemerintah). Each blueprint provides:

- ✅ Step-by-step setup instructions
- ✅ Regulatory requirements (PP 28/2025 compliant)
- ✅ Risk-based licensing framework
- ✅ PMA (Foreign Investment) eligibility
- ✅ Technical (Teknis) & Business (Bisnis) perspectives
- ✅ English & Indonesian versions

**Location:**
- **Page:** `/knowledge/blueprints`
- **Component:** `apps/mouth/src/app/(workspace)/knowledge/blueprints/page.tsx`
- **Current Count:** 88 blueprints (as of January 2026)

---

## Data Structure

### Blueprint Interface

```typescript
interface Blueprint {
  // Identifiers
  id: string;                    // Unique ID: 'kbli-55110'
  kbli_code: string;             // Official KBLI code: '55110'

  // Titles
  title: string;                 // English title
  title_id: string;              // Indonesian title

  // Classification
  category: 'Hospitality' | 'Real Estate' | 'Services' | 'Technology' | 'Trade' | 'Construction' | 'Leasing';
  risk_level: 'Low' | 'Medium' | 'High';
  pma_allowed: boolean;          // Foreign investment allowed?
  pma_percentage: string;        // '100%', '67%', '49%', etc.

  // PDF Files
  pdf_filename: string;          // Default technical version (English)
  pdf_url?: string;              // Direct download URL (optional)

  // Business Version (optional)
  pdf_bisnis_filename?: string;
  pdf_bisnis_url?: string;
  has_bisnis?: boolean;          // Show Bisnis/Teknis toggle?

  // Indonesian Version (optional)
  pdf_id_teknis_url?: string;    // Indonesian technical
  pdf_id_bisnis_url?: string;    // Indonesian business
  has_indonesian?: boolean;      // Show ID 🇮🇩 button?

  // Visual
  icon: string;                  // Icon identifier
  description: string;           // Brief description
}
```

### Example Entry

```typescript
{
  id: 'kbli-55110',
  kbli_code: '55110',
  title: 'Star Hotel',
  title_id: 'Hotel Bintang',
  category: 'Hospitality',
  risk_level: 'Medium',
  pma_allowed: true,
  pma_percentage: '100%',
  pdf_filename: 'KBLI_55110_Star_Hotel.pdf',
  has_indonesian: true,    // ✅ Shows ID button
  has_bisnis: true,        // ✅ Shows Bisnis/Teknis toggle
  icon: 'hotel',
  description: 'Comprehensive guide for establishing star-rated hotels in Indonesia under PP 28/2025.',
}
```

---

## Google Drive Integration

### Folder Structure

**Main Folder:** `PRESENTATIONS`
**Subfolders:**
1. **Surya - Professional Services & Consulting**
   - Contains: Professional services (KBLI 69xxx, 70xxx, 73xxx, 82xxx)
   - Files: Direct PDF files with KBLI codes in filename

2. **Damar - Retail & Wholesale**
   - Contains: Trade services (KBLI 46xxx, 47xxx)
   - Structure: Subfolders per KBLI code, each containing presentation files

### File Naming Convention

**Pattern:** `KBLI_CODE - Title_Keywords.pdf`

**Examples:**
- `69103 - Indonesia_New_Licensing_Era_2025.pdf`
- `70204 - Perizinan_Usaha_Indonesia_Panduan.pdf`
- `82920 - Pengawasan_Berkelanjutan_Jasa_Pen.pdf`
- `47911 - Perdagangan_Eceran_Melalui_Media.pdf`

**Identifying Versions:**

| Filename Pattern | Interpretation |
|-----------------|----------------|
| `Indonesia_` or `_Indonesia_` | English title about Indonesia |
| `Perizinan`, `Panduan`, `Jasa` | Indonesian language version |
| `Business_Licensing` | English technical version |
| `Strategi_Bisnis` | Indonesian business version |

**Multi-Version Detection:**

If a KBLI folder contains **2 files** with same code:
- Likely **Teknis** + **Bisnis** versions
- OR **English** + **Indonesian** versions

**Recommendation:** Always check actual filenames to determine exact version type.

---

## Adding New Blueprints

### Step 1: Identify New KBLI Codes

**From Google Drive:**
1. Navigate to `PRESENTATIONS` folder
2. Check `Surya - Professional Services & Consulting` for professional services
3. Check `Damar - Retail & Wholesale` subfolders for trade
4. Extract KBLI codes from filenames (first 5 digits)

**Check for Duplicates:**
```bash
# Search existing KBLI codes
grep "kbli_code: '" apps/mouth/src/app/\(workspace\)/knowledge/blueprints/page.tsx
```

### Step 2: Determine Category

**KBLI Code Ranges:**

| Code Range | Category | Examples |
|-----------|----------|----------|
| 55xxx | Hospitality | 55110 (Star Hotel), 55120 (Budget Hotel) |
| 68xxx | Real Estate | 68111 (Residential Sale), 68200 (Rental) |
| 96xxx | Services (Beauty) | 96121 (Salon), 96122 (Spa) |
| 62xxx, 63xxx | Services (IT/Data) | 62011 (Software), 63111 (Data Processing) |
| 69xxx, 70xxx, 73xxx, 82xxx | **Services (Professional)** | Consulting, advisory |
| 41xxx, 42xxx, 43xxx | Construction | Building, civil engineering |
| 77xxx | Leasing | Vehicle, equipment rental |
| 49xxx, 53xxx | Transportation | Logistics, freight |
| 79xxx | Travel | Tour operators |
| 10xxx, 11xxx, 56xxx | Food/Beverage | Manufacturing, dining |
| **46xxx, 47xxx** | **Trade** | Wholesale, retail |

### Step 3: Add Blueprint Entry

**Location:** `apps/mouth/src/app/(workspace)/knowledge/blueprints/page.tsx`
**Array:** `const BLUEPRINTS: Blueprint[]`

**Template:**

```typescript
{
  id: 'kbli-XXXXX',
  kbli_code: 'XXXXX',
  title: 'English Business Title',
  title_id: 'Judul Bisnis Indonesia',
  category: 'Services',  // or Trade, Hospitality, etc.
  risk_level: 'Low',     // or Medium, High
  pma_allowed: true,
  pma_percentage: '100%',
  pdf_filename: 'KBLI_XXXXX_English_Title_Teknis.pdf',
  has_indonesian: true,  // Set to true if Indonesian version exists
  has_bisnis: true,      // Set to true if Business version exists
  icon: 'briefcase',     // Choose appropriate icon
  description: 'Brief description of the business activity and regulatory framework.',
},
```

### Step 4: Update Icons (If Needed)

**If using a new icon:**

1. **Import icon** (top of file):
```typescript
import { NewIcon } from 'lucide-react';
```

2. **Add to icon type** (line ~69):
```typescript
icon: '...' | 'newicon';
```

3. **Add to getIcon function** (line ~1500):
```typescript
case 'newicon':
  return NewIcon;
```

### Step 5: Verify TypeScript

```bash
cd apps/mouth
npx tsc --noEmit --skipLibCheck --jsx preserve src/app/\(workspace\)/knowledge/blueprints/page.tsx
```

**Expected:** No errors related to your changes.

---

## Categories & KBLI Classification

### Hospitality (55xxx)
- **55110** - Star Hotel
- **55120** - Budget Hotel (Melati)
- **55130** - Homestay (Pondok Wisata)
- **55191** - Youth Hostel
- **55192** - Guesthouse
- **55193** - Villa Accommodation
- **55194** - Bungalow/Cottage
- **55199** - Other Accommodation
- **55900** - Backpacker Hostel

### Real Estate (68xxx)
- **68111** - Residential Property Sale
- **68112** - Commercial Property Sale
- **68120** - Residential Rental
- **68200** - Commercial Rental
- **68130** - Property Management

### Services - Professional (69xxx, 70xxx, 73xxx, 82xxx)
**Business Advisory:**
- **69101** - Business Licensing Reform Services
- **69103** - New Licensing Era 2025 Consulting
- **69201** - Licensing Reform & Accountability

**Investment Advisory:**
- **70100** - Investment Regulatory Blueprint
- **70201** - Risk-Based Licensing Strategy
- **70202** - Transportation Licensing Navigation
- **70203** - Investment Blueprint Certification
- **70204** - Business Licensing Guide Indonesia
- **70209** - 2025 Business Reforms Strategy

**Strategic Consulting:**
- **73100** - Policy Meets Corporate Practice
- **73201** - Regulatory Overhaul Strategy
- **73202** - Risk-Based Licensing (Market Research)

**Business Support:**
- **82190** - PP 28/2025 Reform & Realization
- **82911** - Debt Collection Standards
- **82912** - Business Licensing Reform Support
- **82920** - Continuous Supervision Services

### Services - IT/Data (62xxx, 63xxx)
- **62011** - Custom Software Development
- **62012** - IT Consulting
- **62014** - Web Portal Development
- **62019** - Other Software Development
- **63111** - Data Processing Services
- **63112** - Web Hosting
- **63121** - Cloud Services

### Services - Beauty (96xxx)
- **96121** - Hair Salon
- **96122** - Spa & Beauty Treatment

### Technology (No specific range)
Various tech-related KBLI codes scattered across ranges

### Construction (41xxx, 42xxx, 43xxx)
**Building Construction:**
- **41011-41020** - Various building types (residential, commercial, industrial, etc.)

**Civil Engineering:**
- **42203** - Electricity & Telecom Infrastructure
- **42913** - Water Canal Construction
- **42916** - Water Well Drilling
- **42924** - Marine Construction
- **42930** - Other Civil Engineering

**Specialized Construction:**
- **43212** - Plumbing Installation
- **43903** - Scaffolding Services
- **43909** - Other Specialized Construction

### Leasing (77xxx)
- **77100** - Car Rental
- **77292** - Equipment Rental

### Trade - Wholesale (46xxx)
- **46333** - Building Materials Wholesale
- **46414** - Wholesale of Other Goods
- **46422** - Wholesale of Printed Materials
- **46635** - Wholesale of Construction Materials
- **46900** - Wholesale of Various Goods

### Trade - Retail (47xxx)
**Specialized Retail:**
- **47414** - Telecommunication Equipment
- **47591** - Furniture
- **47594** - Glassware & Ceramics
- **47612** - Printed Materials
- **47735** - Jewelry & Accessories
- **47779** - Chemicals & Pharmaceuticals
- **47782** - Handicrafts
- **47795** - Transportation Equipment
- **47832** - Street Retail (Kaki Lima)

**E-Commerce:**
- **47911** - E-Commerce (Food, Beverage, Pharma)
- **47919** - E-Commerce (Other Goods)
- **47920** - Direct Selling & MLM

### Transportation & Logistics (49xxx, 53xxx)
- **49221** - Taxi Services
- **49415** - Freight Transport
- **53100** - Postal Services
- **53201** - Courier Services
- **53202** - Delivery Services

### Travel (79xxx)
- **79911** - Travel Agency
- **79912** - Tour Operator

### Food & Beverage (10xxx, 11xxx, 56xxx)
- **10211** - Meat Processing
- **10234** - Noodle Manufacturing
- **56102** - Restaurant
- **10771** - Sugar Confectionery
- **11052** - Mineral Water Production

---

## Indonesian & Bisnis Versions

### Understanding the Flags

#### `has_indonesian: boolean`

**When `true`:**
- Shows **ID 🇮🇩** button in top-left of blueprint card
- User can toggle between English and Indonesian language versions
- Affects which PDF is downloaded

**Files Required:**
- `pdf_id_teknis_url` - Indonesian technical version
- `pdf_id_bisnis_url` - Indonesian business version (if has_bisnis is also true)

**UI Behavior:**
```
User clicks ID 🇮🇩 → showIndonesian = true
Download button → Downloads Indonesian PDF
```

#### `has_bisnis: boolean`

**When `true`:**
- Shows **Bisnis/Teknis** toggle button in top-left of blueprint card
- User can toggle between Technical and Business perspectives
- Affects which PDF is downloaded

**Perspectives:**
- **Teknis (Technical):** Legal requirements, permits, compliance, technical specifications
- **Bisnis (Business):** Market analysis, financial projections, business strategy, ROI

**Files Required:**
- `pdf_bisnis_filename` - Business version filename
- `pdf_bisnis_url` - English business version
- `pdf_id_bisnis_url` - Indonesian business version (if has_indonesian is also true)

**UI Behavior:**
```
User clicks Bisnis → showBisnis = true
Download button → Downloads Business version PDF
```

### Download Logic

**Priority Matrix:**

| Indonesian? | Bisnis? | PDF Downloaded |
|------------|---------|----------------|
| ❌ No | ❌ No | `pdf_url` (English Teknis - default) |
| ❌ No | ✅ Yes | `pdf_bisnis_url` (English Bisnis) |
| ✅ Yes | ❌ No | `pdf_id_teknis_url` (Indonesian Teknis) |
| ✅ Yes | ✅ Yes | `pdf_id_bisnis_url` (Indonesian Bisnis) |

**Implementation:**
```typescript
if (showIndonesian && blueprint.has_indonesian) {
  if (showBisnis && blueprint.has_bisnis && blueprint.pdf_id_bisnis_url) {
    pdfUrl = blueprint.pdf_id_bisnis_url;  // ID + Bisnis
  } else if (blueprint.pdf_id_teknis_url) {
    pdfUrl = blueprint.pdf_id_teknis_url;  // ID + Teknis
  }
} else if (showBisnis && blueprint.has_bisnis && blueprint.pdf_bisnis_url) {
  pdfUrl = blueprint.pdf_bisnis_url;       // EN + Bisnis
} else {
  pdfUrl = blueprint.pdf_url;              // EN + Teknis (default)
}
```

### When to Set Flags

**Best Practice:**

**Set both to `true` by default** if you see multiple files in the Google Drive folder for that KBLI code.

**Conservative Approach:**

If unsure about file availability:
- Set `has_indonesian: false`
- Set `has_bisnis: false`
- User can request specific versions later

**Verification Method:**

For each KBLI code, check Google Drive folder:
- **1 file only** → `has_indonesian: false`, `has_bisnis: false`
- **2 files** → Likely one flag is `true` (check filenames for "Indonesia" or "Bisnis" keywords)
- **4 files** → Both flags should be `true` (EN Teknis, EN Bisnis, ID Teknis, ID Bisnis)

---

## Icons Reference

### Available Icons

| Icon Name | Component | Use Case |
|-----------|-----------|----------|
| `hotel` | `Hotel` | Hospitality |
| `home` | `Home` | Real estate, homestays |
| `tent` | `Tent` | Camping, outdoor accommodation |
| `building` | `Building2` | Commercial buildings |
| `scissors` | `Scissors` | Beauty services |
| `code` | `Code` | Software development |
| `gamepad` | `Gamepad2` | Gaming, entertainment |
| `globe` | `Globe` | International services |
| `database` | `Database` | Data processing |
| `server` | `Server` | Web hosting, cloud |
| `cart` | `ShoppingCart` | Retail, e-commerce |
| `monitor` | `Monitor` | E-commerce, online services |
| `radio` | `Radio` | Media, broadcasting |
| `wrench` | `Wrench` | Maintenance, repair |
| `laptop` | `Laptop` | IT services |
| `hardhat` | `HardHat` | Construction |
| `factory` | `Factory` | Manufacturing |
| `warehouse` | `Warehouse` | Wholesale, storage |
| `health` | `Stethoscope` | Healthcare |
| `education` | `GraduationCap` | Education |
| `entertainment` | `Sparkles` | Entertainment |
| `car` | `Car` | Transportation |
| `anchor` | `Anchor` | Marine, shipping |
| `mining` | `Mountain` | Mining, extraction |
| `satellite` | `Satellite` | Communications |
| `antenna` | `Antenna` | Telecom |
| `grid` | `LayoutGrid` | General services |
| **`briefcase`** | **`Briefcase`** | **Professional services, consulting** |

### Adding New Icons

**Step 1: Import**
```typescript
import { YourIcon } from 'lucide-react';
```

**Step 2: Update Interface**
```typescript
icon: '...' | 'youricon';
```

**Step 3: Update getIcon Function**
```typescript
case 'youricon':
  return YourIcon;
```

---

## Deployment

### Local Development

**Run Dev Server:**
```bash
cd apps/mouth
npm run dev
```

**Visit:** http://localhost:3000/knowledge/blueprints

### Production Deployment

**Build:**
```bash
cd apps/mouth
npm run build
```

**Deploy to Fly.io:**
```bash
fly deploy -a nuzantara-mouth
```

**Verify:**
- URL: https://zantara.balizero.com/knowledge/blueprints
- Check total blueprint count updates (was 56, now 88)
- Test category filters work correctly
- Verify new blueprints appear in correct categories

### Post-Deployment Checklist

- [ ] Blueprint count updated (88 total)
- [ ] All 7 categories show correct counts
- [ ] Services category includes new professional services (should be ~21)
- [ ] Trade category includes new retail/wholesale (should be ~25)
- [ ] ID 🇮🇩 button works for blueprints with `has_indonesian: true`
- [ ] Bisnis/Teknis toggle works for blueprints with `has_bisnis: true`
- [ ] Download functionality works
- [ ] Search bar filters blueprints correctly
- [ ] Mobile responsive layout works

---

## Maintenance

### Regular Updates

**When to Add New Blueprints:**
- New presentations added to Google Drive `PRESENTATIONS` folder
- New KBLI codes published by Indonesian government
- Updated PP regulations require new business classifications

**Quality Checks:**
1. **No Duplicates:** Always grep existing KBLI codes before adding
2. **Correct Category:** Verify KBLI code range matches category
3. **File Availability:** Confirm PDFs exist in Google Drive
4. **Consistent Naming:** Follow `KBLI_XXXXX_Title_Version.pdf` convention
5. **TypeScript Validation:** Run `tsc --noEmit` before committing

### Troubleshooting

**Issue: TypeScript error "Type 'iconname' is not assignable"**
- **Solution:** Add icon to interface union type and getIcon function

**Issue: Blueprint not showing in category filter**
- **Solution:** Check category spelling matches exactly (case-sensitive)

**Issue: Download not working**
- **Solution:** Verify `pdf_url` is set or fallback Google Drive folder URL exists

**Issue: Indonesian/Bisnis buttons not appearing**
- **Solution:** Ensure `has_indonesian` and `has_bisnis` flags are `true`

---

## Statistics (January 2026)

**Total Blueprints:** 88

**By Category:**
- **Hospitality:** 10
- **Real Estate:** 5
- **Services:** 21 (IT: 7, Beauty: 2, Professional: 12)
- **Technology:** 7
- **Trade:** 25 (Wholesale: 5, Retail: 20)
- **Construction:** 18
- **Leasing:** 2

**By Risk Level:**
- **Low:** 78
- **Medium:** 8
- **High:** 2

**PMA Status:**
- **100% PMA Allowed:** 88 (100%)

**Features:**
- **Has Indonesian Version:** 88 (100%)
- **Has Bisnis Version:** 88 (100%)

---

## Related Files

**Component:**
- `apps/mouth/src/app/(workspace)/knowledge/blueprints/page.tsx`

**Google Drive:**
- Folder: `PRESENTATIONS`
- Subfolder 1: `Surya - Professional Services & Consulting`
- Subfolder 2: `Damar - Retail & Wholesale`

**Documentation:**
- This file: `apps/mouth/BLUEPRINTS_DOCUMENTATION.md`

---

## Contact

**For Questions:**
- Frontend: Antonello Siano
- Business Logic: Zero (Bali Zero team)
- Content: Surya (Professional Services), Damar (Retail)

**Last Updated:** January 5, 2026
