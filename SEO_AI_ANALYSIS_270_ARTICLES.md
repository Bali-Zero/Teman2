# 🎯 SEO AI Analysis: Bali Zero 270-Article Strategy

**Analisi delle pubblicate attuali + Framework per 180 nuovi articoli**

---

## PARTE 1: SEO CURRENT STATE ANALYSIS

### ✅ What's Already Working Well

#### 1. **Frontmatter Excellence** (Grade: A+)

Current articles use a highly optimized MDX frontmatter structure:

```yaml
title: "Action-First Title (60-65 chars, keyword first)"
slug: "kebab-case-long-tail-keyword"
seo:
  title: "55-60 char SEO title with primary keyword"
  description: "155-160 char meta description, answer-first"
  keywords: ["primary", "secondary", "LSI variant", ...]
  focusKeyword: "primary-keyword"

aiOptimization:
  primaryQuestion: "User intent question"
  answerSnippet: "40-50 word direct answer for snippet"
  entityMentions:
    - type: "GovernmentOrganization"
      name: "Direktorat Jenderal Imigrasi"
    - type: "Service"
      name: "PT PMA"

faq:
  - question: "Specific FAQ from KB"
    answer: "Verified answer from official source"

relatedArticles: ["slug-1", "slug-2", "slug-3"]
```

**SEO Impact**:

- ✅ Schema.org ready (aiOptimization.entityMentions → JSON-LD)
- ✅ FAQ schema auto-generated from faq array
- ✅ Internal linking structure pre-planned
- ✅ Answer-first snippet optimization for SERP CTR

#### 2. **Content Structure** (Grade: A)

Articles follow answer-first, structured format:

1. **Opening 150-200 words** - Primary keyword in first sentence, direct answer
2. **Context/Why it matters** - Address search intent depth
3. **Structured sections** (3-5 H2s) - Scannability for featured snippets
4. **Interactive components** - JourneyMap, Calculator, Checklist (engagement → dwell time)
5. **FAQ section** - Schema.org FAQ integration
6. **CTA** - Link to Bali Zero service with pricing

**SEO Impact**:

- ✅ Optimized for voice search (question-answer structure)
- ✅ Featured snippet targets (tables, lists, definitions)
- ✅ High dwell time (interactive elements)
- ✅ Lower bounce rate (comprehensive, answer-first)

#### 3. **Technical SEO Infrastructure** (Grade: A+)

**RSS Feed** (`/feed`):

- ✅ 50 most recent articles in RSS 2.0 with Dublin Core extensions
- ✅ Image metadata included (media:content tags)
- ✅ AI crawler friendly (Perplexity, ChatGPT, Claude detection)
- ✅ Cache-Control: 1 hour (fresh for real-time AI indexing)

**LLMs Full** (`/llms-full.txt`):

- ✅ 200+ articles in single markdown file (standard: llmstxt.org)
- ✅ Auto-strips MDX components, preserves pure content
- ✅ Category-grouped for semantic understanding
- ✅ 24-hour cache (AI model training data refresh)
- ✅ Skip filter: articles < 500 chars (only real content)

**Schema.org Implementation** (Inferred from KB sources):

- ✅ Article schema (author, datePublished, dateModified, image, description)
- ✅ FAQ schema (mainEntity: Question → acceptedAnswer)
- ✅ Organization schema (Bali Zero branding)
- ✅ BreadcrumbList (navigation, crawlability)
- ✅ Entity linking via aiOptimization.entityMentions → @graph

#### 4. **Keyword Strategy** (Grade: B+)

Current articles target:

- ✅ Primary keywords with high intent (PT PMA, KITAS, NPWP)
- ✅ Long-tail variants (PT PMA registration timeline, E28A investor KITAS)
- ✅ Comparison keywords (E25B vs E23 KITAS, KITAS vs KITAP)
- ⚠️ **Gap**: Limited featured snippet optimization for factual queries

Current keyword density in seo.keywords arrays:

- Average 5-8 keywords per article
- Mix of primary, secondary, LSI variants
- Some articles include "focusKeyword" (best practice)

#### 5. **Internal Linking** (Grade: A)

relatedArticles strategy:

- 3-5 related articles per piece
- Thematic clusters (PT PMA → capital requirements → NIB)
- Bidirectional linking (if A → B, B should link to A)

**Example cluster**:

```
PT PMA Registration Guide
  ├→ PT PMA Capital Requirements
  ├→ NIB Explained
  ├→ OSS Registration
  └→ Company Domicile
```

**SEO Impact**:

- ✅ Authority distribution via PageRank
- ✅ Topical cluster authority (TCTL: Topic Cluster Thematic Linking)
- ✅ Breadcrumb-like navigation helps crawlability

#### 6. **Content Depth** (Grade: A)

Current articles:

- **Average length**: 2,000-3,500 words (excellent for competitive keywords)
- **Reading time**: 8-12 minutes (optimal engagement window)
- **Sections**: 4-7 H2s, subsections where relevant
- **Data richness**: Tables, lists, calculations (LSI expansion)

---

## PARTE 2: IDENTIFIED GAPS & OPTIMIZATION OPPORTUNITIES

### 🔴 Critical Gaps (for 270-article plan)

#### Gap 1: **Limited Featured Snippet Targeting**

Current articles cover answers but don't explicitly optimize for snippets.

**Fix for 270 articles**:

- Lead with a **definition table** (Who/What/When/How)
- Use numbered lists for How-To (Google favors 4-8 steps)
- Include a "Quick Answer" box before deep-dive
- Format dates, numbers, percentages consistently

Example (for KBLI article):

```markdown
## What is KBLI 2025?

| Aspect          | Answer                                                |
| --------------- | ----------------------------------------------------- |
| **Definition**  | Indonesian Standard Classification of Business Fields |
| **Total Codes** | 1,562 five-digit classifications                      |
| **Registry**    | Central Bureau of Statistics (BPS)                    |
| **Last Update** | 2025 (supersedes KBLI 2015)                           |
```

→ Google often pulls 1st table for "what is X" queries

#### Gap 2: **Question Variations Not Explicit**

Current FAQ sections are good but don't account for all user search intents.

**Recommended approach for 270**:

- Each article should have explicit targeting of 3-5 question variations:
  - **How**: "How do I get E28A KITAS?"
  - **What**: "What is E28A Investor KITAS?"
  - **Why**: "Why do I need E28A vs E23?"
  - **Cost**: "How much does E28A cost?"
  - **Timeline**: "How long does E28A take?"

Use LSI keywords strategically:

```yaml
keywords:
  - "investor KITAS Indonesia" # Primary
  - "E28A visa" # Alt name
  - "investment visa requirements" # How intent
  - "KITAS cost 2026" # Cost intent
  - "KITAS application timeline" # Timeline intent
```

#### Gap 3: **Entity Linking Incomplete**

Current articles mention entities (BKPM, Kemenkumham) but don't always link to Wikidata/schema definitions.

**Recommended for 270**:

```yaml
entityMentions:
  - type: "GovernmentOrganization"
    name: "BKPM (Badan Koordinasi Penanaman Modal)"
    sameAs: "https://www.wikidata.org/wiki/Q4835153"
    description: "Indonesian investment coordinating authority"

  - type: "Regulation"
    name: "PP 28/2025 (PT PMA Rules)"
    sameAs: "https://jdihn.go.id/..."
    validFrom: "2025-01-01"
```

This enables:

- ✅ Knowledge Graph entity linking
- ✅ Wikipedia infobox cross-reference
- ✅ Schema.org structured data for AI training

#### Gap 4: **Temporal Content Signals Missing**

Articles mention "2026" but don't use explicit schema dates.

**Recommended for 270**:

```yaml
contentTiming:
  validFrom: "2026-02-17"
  validUntil: "2026-12-31" # Expire articles about temporary rules
  nextReview: "2026-06-01"

updatePattern:
  frequency: "monthly" # How often does this topic change?
  reason: "Tax regulations change annually"
```

This helps:

- ✅ Freshness signals (Google's "Update" ranking factor)
- ✅ Evergreen vs time-sensitive distinction
- ✅ Better indexing for fact-based queries

---

## PARTE 3: LONG-TAIL KEYWORD STRATEGY (180 NEW ARTICLES)

### Cluster 1: KBLI 2025 Deep Dive (40 articles)

**Primary Intent Categories**:

#### 1.1 KBLI Sector Guides (15 articles)

Format: "KBLI codes for [SECTOR] in Indonesia"

| Sector        | Primary Keyword              | Secondary Keywords                                  | Search Volume Est. |
| ------------- | ---------------------------- | --------------------------------------------------- | ------------------ |
| Real Estate   | KBLI real estate development | KBLI 41101-41109, property codes, construction KBLI | 320/month          |
| Hospitality   | KBLI hotel Indonesia         | KBLI 55101, villa KBLI, guesthouse codes            | 480/month          |
| F&B           | KBLI restaurant codes        | KBLI 56101, café KBLI, catering codes               | 650/month          |
| IT Services   | KBLI software Indonesia      | KBLI 62010, web development KBLI, cloud KBLI        | 420/month          |
| Consulting    | KBLI consulting business     | KBLI 70201, management consultant codes             | 180/month          |
| E-Commerce    | KBLI e-commerce              | KBLI 47911, online retail codes                     | 540/month          |
| Manufacturing | KBLI manufacturing codes     | KBLI 10101, production Indonesia                    | 220/month          |
| Education     | KBLI language school         | KBLI 85411, training center codes                   | 190/month          |

**Headline Formulas for 40 KBLI articles**:

- "KBLI [Sector]: Codes, Requirements, and Tax Implications 2026"
- "[Sector] Business in Indonesia: KBLI Codes & Compliance"
- "Complete KBLI Code List for [Sector] - What You Need to Know"
- "KBLI [Code Range]: [Sector] Classification Explained"

**Content Structure (1,200+ words)**:

1. What KBLI code(s) apply to [sector]? (definition + table)
2. Which specific KBLI code should I register? (decision tree)
3. Requirements, permits, and compliance by KBLI code
4. Tax, labor, and foreign ownership implications per code
5. Real-world example: company in [sector] registered as KBLI X
6. FAQ: Common questions about KBLI for [sector]

**Featured Snippet Optimization**:

- Lead with KBLI code table (exactly 5-9 rows)
- "Step 1... Step 2... Step 3" format for how-to
- "Here are the 4 main KBLI categories for [sector]..."

---

#### 1.2 KBLI Migration Guides (10 articles)

Format: "KBLI 2020 to 2025: [Topic] Migration Guide"

| Topic           | Keyword                             | User Intent                                    | Word Count |
| --------------- | ----------------------------------- | ---------------------------------------------- | ---------- |
| Split Codes     | KBLI split codes 2025 migration     | "My old KBLI is now X codes, what do I do?"    | 1,500      |
| Merged Codes    | KBLI merged codes                   | "My two codes are now one, cost implications?" | 1,500      |
| Deprecated      | Deleted KBLI codes 2025             | "My industry's code no longer exists"          | 1,800      |
| FDI Impact      | KBLI 2025 foreign ownership changes | "Can I still own 100% PT PMA in my sector?"    | 2,000      |
| Tax KLU         | KBLI KLU fiscal change              | "How does new KBLI affect my tax ID?"          | 1,400      |
| License Remap   | License requirements KBLI 2025      | "Do I need new permits with new KBLI?"         | 1,600      |
| Risk Reclassify | Risk-based licensing KBLI 2025      | "Is my activity still low-risk?"               | 1,500      |
| OSS Update      | Update NIB with new KBLI            | "Process to update PT PMA KBLI code"           | 1,300      |
| Safe vs Risky   | KBLI audit-risk codes               | "Which KBLI codes attract tax audits?"         | 1,400      |

**Headline Formulas**:

- "KBLI 2020 → 2025 Migration: [Sector] Code Updates"
- "Your KBLI Code Was Changed in 2025: Here's What to Do"
- "[Sector] KBLI Deprecation: Timeline and Replacement Codes"
- "KBLI Risk Reclassification 2025: What Changed for [Sector]"

**Unique SEO Angle**: These articles target exact intent of accountants, compliance officers, PT owners who need tactical guidance → High commercial value, less competition.

---

#### 1.3 KBLI + Business Structure (10 articles)

Format: "KBLI [X]: Capital Requirements, Foreign Ownership, Permits"

| Combo Topic        | Primary Keyword                     | Secondary Angle                                       | Users                 |
| ------------------ | ----------------------------------- | ----------------------------------------------------- | --------------------- |
| KBLI + Capital     | KBLI capital requirements Indonesia | "Which KBLI codes require IDR 10B vs 2.5B?"           | Accountants, founders |
| KBLI + PMA         | KBLI foreign ownership 100% PMA     | "Which sectors allow full foreign ownership?"         | Foreign investors     |
| KBLI + Workers     | KBLI TKA ratio requirements         | "How many foreign workers can I hire in [KBLI]?"      | HR, company founders  |
| KBLI + Tax         | KBLI tax incentive eligible codes   | "Does my KBLI qualify for tax holiday?"               | Tax planners          |
| KBLI + Import      | KBLI import license API-P           | "Which KBLI codes require import permits?"            | Importers             |
| KBLI + Location    | KBLI Bali green zone restrictions   | "Can I operate my KBLI in Bali green zone?"           | Property investors    |
| KBLI + Environment | KBLI AMDAL requirements             | "Does my KBLI need environmental audit?"              | Manufacturers         |
| KBLI + Halal       | KBLI halal certification required   | "Which food KBLI requires halal cert?"                | F&B founders          |
| KBLI + Standards   | KBLI SNI mandatory standards        | "What Indonesian standards apply to my KBLI?"         | Manufacturers         |
| KBLI + Export      | KBLI export orientation incentives  | "Can I get tax benefits if I export under this KBLI?" | Exporters             |

**Content Structure**:

1. The KBLI code: What it covers
2. The business requirement: What constraint applies
3. How to check if you're affected
4. Step-by-step compliance guide
5. Cost estimate
6. FAQ with real scenarios

---

#### 1.4 KBLI Strategic Planning (5 articles)

Format: "Advanced KBLI Strategy: [Topic]"

| Topic        | Keyword                                | Decision Point                                      |
| ------------ | -------------------------------------- | --------------------------------------------------- |
| Multi-KBLI   | Register multiple KBLI codes Indonesia | "Should I register 1 code or 5?"                    |
| Future-Proof | KBLI flexibility code selection        | "Which KBLI code is safest for pivoting?"           |
| Red Flags    | KBLI codes attract audit               | "Which KBLI codes trigger immigration scrutiny?"    |
| Visa Sync    | KBLI E25B E28A alignment               | "Does my KBLI match my visa requirements?"          |
| Brand Fit    | KBLI brand positioning                 | "Should I register a broader KBLI for credibility?" |

**Unique Value**: These articles target strategic decisions → High-value audience (business owners, consultants making $5K+ decisions).

---

### Cluster 2: Visa 2026 Comprehensive (50 articles)

#### 2.1 Work Visa Deep Dive (15 articles)

| Visa Code     | Primary Keyword                       | Angle 1          | Angle 2          | Angle 3              |
| ------------- | ------------------------------------- | ---------------- | ---------------- | -------------------- |
| E25B          | E25B director KITAS requirements      | Breakdown        | Timeline         | Costs                |
| E23           | E23 employee KITAS Indonesia          | vs E25B          | Extension        | Downgrade from E25B  |
| E33G          | E33G remote worker visa               | Requirements     | Restrictions     | Company setup        |
| E28A          | E28A investor KITAS                   | (already exists) | KITAP pathway    | vs E25B              |
| RPTKA         | RPTKA work permit Indonesia           | Process          | Quotas           | Foreign ratio        |
| IMTA          | IMTA work permit vs KITAS             | Difference       | When needed      | Cost                 |
| DKP-TKA       | DKP-TKA foreign worker registration   | Process          | Timeline         | Cost with KITAS      |
| Extension     | KITAS extension 1 year to 2 years     | Process          | Documents        | Cost                 |
| Downgrade     | KITAS downgrade E25B to E23           | When needed      | Process          | Tax impact           |
| Upgrade       | KITAS upgrade E23 to E25B             | Promotion path   | Documents needed | Timeline             |
| Multiple      | Multiple KITAS two sponsors           | Legal?           | Tax treatment    | Process              |
| Side Business | E25B director freelance side business | Legal limits     | Tax reporting    | Visa risk            |
| Cancellation  | KITAS cancellation company closes     | Process          | TKA obligations  | ITAS consequences    |
| Transfer      | KITAS transfer employer change        | Process          | Timing           | Do I leave/re-enter? |
| Denial        | KITAS renewal denied reasons          | Common issues    | Appeals          | Prevention           |

**Headlines**:

- "E25B Director KITAS 2026: Requirements, Cost, Timeline"
- "E23 vs E25B: Employee KITAS Comparison & When to Switch"
- "RPTKA Work Permit: How to Get TKA Authorization in Indonesia"
- "KITAS Extension from 1 Year to 2 Years: Process & Documents"

**Featured Snippet Targets** (per article):

- Tables: E25B vs E23 comparison matrix (4 rows minimum)
- Lists: "5 Steps to E25B KITAS Application"
- Numbers: "E25B costs IDR X, timeline Y weeks, requires Z documents"
- Defs: "RPTKA is..."

---

#### 2.2 Family & Dependent Visas (10 articles)

| Visa Type        | Keyword                               | User Intent                           |
| ---------------- | ------------------------------------- | ------------------------------------- |
| E33F Spouse      | E33F dependent spouse visa Indonesia  | Getting spouse here on my KITAS       |
| E33E Children    | E33E child dependent visa             | Can kids stay on parent's KITAS?      |
| E311A Retirement | E311A retirement visa IDR 183M        | Retire in Indonesia visa              |
| Spouse No Work   | KITAS spouse without work rights      | My spouse here but can't work?        |
| KITAP            | KITAP permanent stay after KITAS      | 5-year permit, KITAS pathway          |
| Family Reunion   | Family reunification elderly parents  | Bringing parents to Indonesia         |
| Student E31      | E31 student visa international school | Sending kids to intl school in Bali   |
| Au Pair          | Au pair visa Indonesia                | Does it exist? (spoiler: no official) |
| Newborn          | Newborn KITAS baby born in Indo       | My kid born here gets what permit?    |
| Divorce          | Divorce dependent KITAS implications  | Spouse visa when marriage ends?       |

**Headlines**:

- "E33F Spouse KITAS: Getting Your Partner a Dependent Visa in Indonesia"
- "Can My Kids Get E33E Dependent Visa While I Have KITAS?"
- "E311A Retirement Visa: IDR 183M Income Requirement Explained"
- "Baby Born in Indonesia to KITAS Parent: Visa & Citizenship"

---

#### 2.3 Short-Term & Tourist Visas (10 articles)

| Visa           | Keyword                                        | Angle                        |
| -------------- | ---------------------------------------------- | ---------------------------- |
| E-VOA          | E-VOA electronic visa on arrival 60 days       | How to get online, process   |
| B211A Myth     | B211A visa code doesn't exist 2026             | Clarifying a common mistake  |
| B211 Social    | B211 social-cultural visit visa                | NGO, volunteer, family visit |
| B211 Business  | B211 business visit limited stay               | Short business trip vs E25B  |
| Multi-Entry    | Multiple-entry vs single-entry visa Indonesia  | When to choose which         |
| Border Run     | Border run Timor visa run consequences         | Legal risks, visa overstay   |
| Visa-Free      | 30-day visa-free Indonesia citizens            | When is free enough vs E-VOA |
| Extend Tourist | Extend tourist visa in Indonesia               | Can you extend B211?         |
| Overstay       | Overstay penalties fines deportation Indonesia | How much does it cost?       |
| Emergency Visa | Emergency medical visa Indonesia               | Medical visa process         |

**Headlines**:

- "E-VOA Visa 60-Day: Complete Electronic Visa on Arrival Guide"
- "B211A Visa Doesn't Exist: Clearing Up the Most Common Visa Mistake"
- "Border Run Risks: Why Visa Runs Aren't Actually Safe in 2026"
- "Overstay in Indonesia: Fines, Bans, and How to Fix It"

---

#### 2.4 Golden Visa & High-Value (5 articles)

| Program      | Keyword                                       | Appeal                          |
| ------------ | --------------------------------------------- | ------------------------------- |
| ITAP         | Golden visa Indonesia ITAP investment         | Wealthy investor path           |
| GCI          | Global citizenship Indonesia diaspora         | For diaspora (special program)  |
| vs KITAP     | Golden visa vs KITAP comparison               | Which is easier/better?         |
| Vehicles     | Investment vehicle golden visa Indonesia      | Property, bonds, stocks options |
| Case Studies | Golden visa success Indonesia 2025 statistics | Real examples                   |

---

#### 2.5 Immigration Compliance (10 articles)

| Topic          | Keyword                                   | Compliance Angle               |
| -------------- | ----------------------------------------- | ------------------------------ |
| STM            | STM exit-reentry permit Indonesia         | When you leave and come back   |
| Report         | SKLD SKTT KITAS reporting obligations     | Annual notifications           |
| Address        | Address change notification 24-hour rule  | Moved house, what to do?       |
| Passport       | Passport renewal with active KITAS        | Renewing passport during KITAS |
| Lost Passport  | Lost passport emergency KITAS             | My passport lost abroad        |
| Checks         | Immigration spot checks expect documents  | Random check, what to carry?   |
| Blacklist      | Check immigration blacklist appeal        | Am I on the list?              |
| Overstay Cases | Overstay case studies real scenarios      | What actually happened to X?   |
| Photo          | KITAS biometric photo requirements 2026   | Photo specifications updated?  |
| INA Digital    | INA Digital vs paper documents transition | Digital immigration system     |

---

### Cluster 3: Tax & Compliance 2026 (35 articles)

#### 3.1 CoreTax System (5 articles)

```
NPWP lama → NIK-based system
CoreTax login troubleshooting
CoreTax for foreigners NPWP16
E-Filing via CoreTax SPT Tahunan
CoreTax vs old DJP Online
```

#### 3.2 Personal Tax (10 articles)

```
PPh 21 expat progressive rates
Tax residency 183-day rule
Foreign income worldwide vs territorial
Tax treaties DTA Certificate of Domicile
NPWP foreigners when mandatory
SPT Tahunan deadline March 31
Tax deductions expats housing education
Tax audit survival what triggers prepare
Tax amnesty history will there be another
Expat tax planning optimization
```

#### 3.3 Corporate Tax (10 articles)

```
PPh 25 monthly installments calculation
PPh 29 annual settlement true-up
PPh 23 withholding services interest
PPh 26 foreign withholding payments
VAT PPN 12% when to charge e-Faktur
PPh Badan 22% corporate income tax
Transfer pricing documentation benchmarking
Loss carryforward 5-year rule usage
Tax incentives 2026 eligible industries
Thin capitalization debt-to-equity limits
```

#### 3.4 Property & Investment Tax (5 articles)

```
PBB property tax calculation payment
BPHTB transfer tax buying property
Capital gains property stock sale
Rental income PPh final vs progressive
Crypto tax Indonesia gains
```

#### 3.5 Tax Deadlines (5 articles)

```
2026 tax calendar PT PMA all deadlines
Monthly tax obligations file when
Quarterly reporting e-SPT Masa
Annual reporting SPT Tahunan
Tax payment methods e-Billing bank transfer
```

---

### Cluster 4: Business Operations (30 articles)

#### 4.1 PT PMA Lifecycle (10 articles)

```
PT PMA timeline week-by-week
Deed of Establishment notary process
AHU approval Ministry Law rejection
NIB registration OSS system
Company domicile virtual office physical
Bank account opening which banks PT PMA
Operational licenses which NIB needed
First-year compliance tax immigration labor
PT PMA dormant pause operations
PT PMA closure dissolution timeline
```

#### 4.2 Employment & Labor (10 articles)

```
BPJS Kesehatan healthcare employer obligations
BPJS Ketenagakerjaan accident pension death
Employment contracts PKWT vs PKWTT
Minimum wage 2026 by province
Severance calculation termination amount
Overtime rules maximum hours premium
Annual leave 12 days minimum calculate
Maternity leave 3 months paid father leave
THR religious holiday bonus timing
Foreign worker ratio TKA TKI per industry
```

#### 4.3 Accounting & Reporting (5 articles)

```
Monthly bookkeeping records to keep
Financial statements balance sheet P&L cash flow
Audit requirements revenue thresholds
Accounting software e-Accounting DJP approved
Chart of accounts Indonesian standard SAK
```

#### 4.4 Operational Permits (5 articles)

```
TDP company registration 2026 needed
SIUP business license timeline
API import license general vs producer
Halal certificate BPJPH F&B process
Environmental AMDAL UKL-UPL differences
```

---

### Cluster 5: Property & Real Estate (20 articles)

#### 5.1 Property Ownership (8 articles)

```
Hak Pakai foreigners 30-year renewable
Hak Milik Indonesian-only PT nominee
Leasehold 25-year lease renewal
Strata title apartment ownership
Property via PT PMA pros cons
Land certificates types verification
Due diligence IMB building permit encumbrance
Property notary PPAT role fees
```

#### 5.2 Property Investment (7 articles)

```
Villa investment ROI Seminyak Canggu Ubud
Airbnb regulations 2026 license tax
Property tax calculator PBB BPHTB
Property management cost structure managers
Construction costs Bali per sqm estimates
Zoning laws green yellow zone restrictions
Property market trends price per sqm yields
```

#### 5.3 Property Transactions (5 articles)

```
Buying process AJB BPHTB certificate
Selling process capital gains notary
Property financing mortgage foreigners
Title insurance exist mostly no
Property disputes PTUN administrative court
```

---

### Cluster 6: Lifestyle & Practical (20 articles)

#### 6.1 Bali Living (5 articles)

```
Cost of living 2026 housing food utilities
Best areas Canggu Sanur Ubud Uluwatu
Utilities setup PLN PDAM internet
Shopping supermarkets markets imports
Entertainment memberships clubs gyms
```

#### 6.2 Healthcare (5 articles)

```
Hospitals Bali BIMC Kasih Ibu Siloam
Health insurance international vs local BPJS
Pharmacies prescription drugs OTC
Dental care costs quality
Mental health therapists psychiatrists support
```

#### 6.3 Education (5 articles)

```
International schools fees IB Cambridge
Indonesian schools expat kids public
Homeschooling legal requirements
University studying Indonesia foreigner
Language learning Bahasa Indonesia courses
```

#### 6.4 Banking (3 articles)

```
Opening bank account personal KITAS holders
Money transfer Wise OFX bank wire
ATM limits daily withdrawal fees
```

#### 6.5 Transportation (2 articles)

```
Driving license convert foreign vs local test
Vehicle ownership foreigners cars bikes PT PMA
```

---

## PARTE 4: ADVANCED SEO OPTIMIZATION FRAMEWORK

### A. Entity Linking Strategy (Google Knowledge Graph)

For every article, integrate entity mentions following this schema:

```yaml
entityMentions:
  # Government Organizations
  - type: "GovernmentOrganization"
    name: "[Ministry/Bureau]"
    wikidata: "Q[ID]" # https://www.wikidata.org
    description: "[Role in Indonesia]"
    website: "[official.go.id]"

  # Regulations/Laws
  - type: "CreativeWork"
    name: "[Regulation name] [PP/PERMEN XX/YYYY]"
    datePublished: "YYYY-MM-DD"
    validFrom: "YYYY-MM-DD"

  # Visa/Business/Concept
  - type: "Thing"
    name: "[Concept name]"
    sameAs: "https://en.wikipedia.org/wiki/[URL]"

  # Locations (for property/lifestyle)
  - type: "Place"
    name: "[Province/City]"
    geo:
      latitude: X.XXX
      longitude: X.XXX
```

**Benefit**: Google links articles to Knowledge Graph panels, improving E-E-A-T signals.

---

### B. Internal Linking Topology (TCTL: Topic Cluster Thematic Linking)

Create explicit linking hierarchies per cluster:

```
KBLI Hub
├─ KBLI 2025 Overview (cornerstone)
├─ KBLI Sector 1 (real estate)
│  ├─ KBLI codes
│  ├─ Requirements
│  └─ Tax implications
├─ KBLI Sector 2 (hospitality)
├─ KBLI Sector 3 (F&B)
...
└─ KBLI 2020→2025 Migration Guide (hub)
   ├─ Split codes
   ├─ Merged codes
   ├─ Deprecated codes
   ...
```

**Every article links to**:

1. **Parent cluster** (KBLI Overview → all sector guides)
2. **Sibling articles** (3-5 related KBLI sectors)
3. **Child topics** (KBLI Hospitality → specific hotel reqs)
4. **Cross-cluster** (KBLI → PT PMA setup → tax obligations)

**Link anchor text formula**:

- Primary keyword: "KBLI for [sector]"
- Secondary: "related to [sector]"
- Contextual: "Learn more about [specific requirement]"
- Avoid: "click here", "read more"

---

### C. Featured Snippet Optimization (Per Article Type)

#### Definitional Articles (What is X?)

```markdown
| Element          | Format                                            |
| ---------------- | ------------------------------------------------- |
| **Definition**   | KBLI is Indonesia's Standard Classification of... |
| **Who uses it**  | Every business in Indonesia                       |
| **When created** | 2025 (updated from 2015)                          |
| **Key numbers**  | 1,562 codes across 9 categories                   |

Lead with this table in first 300 words.
```

#### How-To Articles (How to get X?)

```markdown
## 5 Steps to Get E28A KITAS

1. **Form PT PMA** (2-4 weeks): Register company, minimum IDR 10B
2. **Get NIB** (3-5 days): OSS registration, obtain Business ID
3. **Apply VITAS** (5 working days): Indonesian immigration form
4. **Enter country** (automatic): ITAS issued on arrival
5. **Collect KITAS** (5-7 days): Biometrics, physical permit

"For complete details, see Step 1 section below..."
```

#### Comparison Articles (X vs Y?)

```markdown
| Feature                | E25B Director KITAS | E28A Investor KITAS  |
| ---------------------- | ------------------- | -------------------- |
| **Minimum investment** | IDR 10B + salary    | IDR 10B              |
| **Work in company**    | Yes, as director    | No, passive investor |
| **RPTKA required**     | Yes                 | No                   |
| **DKP-TKA fee**        | Yes (~IDR 2M/year)  | No                   |
| **Cost 2026**          | IDR 36M onshore     | IDR 19M onshore      |

→ Include 5-7 row comparisons, avoid 2-3 rows
```

#### Cost/Pricing Articles

```markdown
## PT PMA Setup Cost Breakdown 2026

| Component                         | Cost (IDR)         | Cost (USD)    |
| --------------------------------- | ------------------ | ------------- |
| Notary service                    | 15,000,000         | ~$940         |
| Government fees                   | 5,000,000          | ~$315         |
| Virtual office (1 yr)             | 12,000,000         | ~$750         |
| Bank setup                        | 3,000,000          | ~$190         |
| **Total**                         | **35,000,000**     | **~$2,195**   |
| **Plus**: Paid-up capital minimum | **10,000,000,000** | **~$625,000** |
```

---

### D. Answer Snippet Optimization

Every article should have a structured `answerSnippet` in frontmatter:

```yaml
aiOptimization:
  primaryQuestion: "What is E28A KITAS?"
  answerSnippet: "E28A Investor KITAS is a 2-year Indonesian residence permit for foreign investors with minimum IDR 10 billion shareholding in a PT PMA company. Pure investors don't require work authorization (RPTKA) or foreign worker fees. It's renewable and leads to permanent residency (KITAP) after 3 consecutive years."

  # Verification: 40-50 words, answers question directly, includes key facts
```

This snippet appears in:

1. Google search results (SERP snippet)
2. AI training data (llms-full.txt, RSS)
3. Voice search results
4. Knowledge panels

---

### E. Temporal Freshness Signals

For dynamic topics (tax, visa, regulations), add:

```yaml
contentTiming:
  validFrom: "2026-02-17"
  validUntil: "2026-12-31"
  nextReviewDate: "2026-06-01"
  updateFrequency: "quarterly"
  updateReason: "Tax regulations and visa rules change regularly"

lastContentUpdate:
  date: "2026-02-16"
  type: "regulatory_change" # new_info | clarification | deprecation
  details: "PP 28/2025 implemented new PT PMA timelines"
```

Benefits:

- ✅ Google Fresh ranking factor (updated content ranks higher)
- ✅ AI retraining signals (shows article is maintained)
- ✅ Automatic expiration (readers know when info expires)

---

### F. Citation & Source Attribution (EEAT)

Every claim needs source:

```yaml
faq:
  - question: "What is the minimum investment for E28A KITAS?"
    answer: "Each investor needs minimum IDR 10 billion (~USD 625,000) in shareholding."
    sources:
      - title: "Keputusan Menteri M.IP-08.GR.01.01/2025"
        url: "https://imigrasi.go.id/..."
        type: "official_regulation"
      - title: "BKPM PT PMA Requirements 2025"
        url: "https://bkpm.go.id/..."
        type: "government_guidance"
```

Benefits:

- ✅ E-A-T signals (expertise, authority, trustworthiness)
- ✅ EEAT now includes Experience (verified by sources)
- ✅ AI can trace claims to official sources

---

## PARTE 5: PRODUCTION CHECKLIST (180 NEW ARTICLES)

### Pre-Writing Checklist (Per Article)

- [ ] **Keyword Research**:
  - Primary keyword (main + 2-3 variations)
  - Secondary keywords (LSI, intent variations)
  - Search volume estimate (ahrefs/semrush)
  - Competition level (SERP analysis)
- [ ] **Search Intent Validation**:
  - Top 5 ranking pages on Google
  - Featured snippet type (list, table, def, how-to?)
  - Question variations users ask
- [ ] **Entity Identification**:
  - Government orgs mentioned
  - Regulations/laws cited
  - Locations involved
  - Services/products referenced
- [ ] **Internal Link Opportunities**:
  - 3-5 related articles identified
  - Bidirectional linking planned
- [ ] **FAQ Sources**:
  - 5-8 FAQs identified from KB/search
  - Answers verified from official sources

### During-Writing Checklist

- [ ] **First paragraph** (150-200 words):
  - Primary keyword in first 20 words
  - Direct answer to user question
  - User intent matched
- [ ] **Headings**:
  - Clear hierarchy (H1 > H2 > H3)
  - 4-7 H2 sections (optimal for scanning)
  - Keyword variations in headers
- [ ] **Visual elements**:
  - 1-2 tables (5-9 rows preferred)
  - At least 1 ordered list
  - At least 1 definition/explanation block
- [ ] **Interactive components** (if applicable):
  - Calculator, comparison, checklist, journey map
  - Engages readers, increases dwell time
- [ ] **CTA**:
  - Link to relevant Bali Zero service (if applicable)
  - Mention pricing from pricing JSON
  - Clear value proposition

### Post-Writing Checklist

- [ ] **Word count**: 1,200-2,500 words (minimum 1,200)
- [ ] **Reading time**: 5-10 minutes
- [ ] **Links**:
  - 3-5 internal links (min. 3)
  - 1-2 external links (official sources)
- [ ] **Images**: Cover image 1200x630 + Alt text with keyword
- [ ] **Frontmatter completion**:
  - All SEO fields filled (title, description, keywords)
  - aiOptimization block complete (answerSnippet, entityMentions, FAQ)
  - relatedArticles array (3-5 linked articles)
- [ ] **Plagiarism check**: 0% plagiarism (Copyscape/Grammarly)
- [ ] **Fact verification**: All claims checked against KB sources
- [ ] **Schema validation**: No broken schema markup

---

## PARTE 6: BATCH PRODUCTION WORKFLOW

### Batch 1-18 Workflow (10 articles per batch × 18 batches = 180 articles)

**Timeline per batch: 6-8 hours**

#### Phase 1: Research (2 hours)

1. Select 10 articles from cluster
2. Research keywords (Google SERP top 5)
3. Verify KB sources (visa_oracle, KBLI, pricing)
4. Outline structure + FAQ questions
5. Identify internal links + entities

#### Phase 2: Writing (3 hours)

1. Draft frontmatter (30 min)
2. Write article body (2 hours, ~150 words/15 min)
3. Add tables, lists, interactive components (30 min)

#### Phase 3: Optimization (1.5 hours)

1. Insert internal links (30 min)
2. Verify entity mentions + sources (30 min)
3. Add FAQ section with citations (30 min)

#### Phase 4: Images & Assets (1.5 hours)

1. Design/generate cover image 1200x630 (1 hour)
2. Verify image alt text + keyword inclusion (15 min)
3. Optimize image size (<300KB) (15 min)

#### Phase 5: QA (1 hour)

1. Proofread + grammar (20 min)
2. Validate frontmatter + schema (20 min)
3. Test internal links + load time (20 min)

---

### Git Workflow Per Batch

```bash
# Before starting batch 1
cd /path/to/balizero
git pull origin main
git checkout -b content/kbli-cluster-batch-1

# After completing 10 articles
git add apps/mouth/src/content/articles/business/*
git add apps/mouth/public/static/insights/business/*
git commit -m "content: add KBLI sector guides batch 1 (10 articles)

- KBLI codes for real estate (41101-41109)
- KBLI codes for hospitality (55101-55230)
- KBLI codes for F&B (56101-56309)
- [+ 7 more articles]
- Total: 10 new articles, 1,200+ words each
- Cover images: 10 custom designs
- Internal links: 150+ cross-cluster links
- SEO: Schema.org JSON-LD, FAQ schema, entity mentions verified

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"

git push origin content/kbli-cluster-batch-1

# Create PR on GitHub
gh pr create \
  --title "Add KBLI Sector Guides Batch 1 (10 articles)" \
  --body "Complete 10 KBLI sector articles with SEO optimization"
```

---

## PARTE 7: VERIFICATION & QUALITY GATES

### Per-Batch Verification

After each batch of 10 articles:

```bash
# 1. Build check
npm run build
# Expected: No errors, RSS includes new articles

# 2. Feed verification
curl https://balizero.com/feed | grep -c "<item>"
# Expected: +10 items vs previous batch

# 3. llms-full.txt size
curl https://balizero.com/llms-full.txt | wc -c
# Expected: +45-50KB per 10 articles

# 4. Schema validation
# Test 2 random articles with Google Rich Results Test
# https://search.google.com/test/rich-results
# Expected: Article schema + FAQ schema valid

# 5. Spot-check content
# Read 1 article, verify:
# - Keyword in first paragraph
# - Min 3 internal links present
# - Tables/lists exist
# - FAQ section complete
# - CTA mentions pricing
```

---

### Final Verification (All 270 Articles)

```bash
# Article count
sqlite3 apps/mouth/.next/cache/articles.db \
  "SELECT category, COUNT(*) FROM articles GROUP BY category;"

# Expected distribution:
# business: ~80 (40 new KBLI + 40 existing)
# immigration: ~70 (50 new visa + 20 existing)
# tax: ~50 (35 new tax + 15 existing)
# property: ~35 (20 new + 15 existing)
# lifestyle: ~35 (20 new + 15 existing)
# tech: ~20 (existing)
# TOTAL: 270+

# File size verification
ls -lh apps/mouth/public/static/insights/*/
# Expected: ~180 new images (190-200 total)

# SEO distribution check
# Verify each article has:
# ✅ seo.title (55-60 chars)
# ✅ seo.description (155-160 chars)
# ✅ seo.keywords (5-8 terms)
# ✅ aiOptimization.answerSnippet (40-50 words)
# ✅ relatedArticles (3-5 links)
# ✅ faq section (3-5 questions)
```

---

## Summary & Action Items

✅ **Current SEO Status**: Strong foundation (A-/A rating)

- Excellent frontmatter structure
- Good content formatting
- Technical SEO infrastructure in place
- RSS + llms-full.txt AI-optimized

⚠️ **Optimization Gaps** (fix with 270-article plan):

- Limited featured snippet targeting
- Entity linking could be more comprehensive
- Temporal freshness signals missing
- Long-tail keyword coverage sparse

🎯 **180 New Articles** will provide:

- Complete long-tail keyword coverage (all intents)
- Strong EEAT signals (citing official sources)
- Topical authority (all KBLI, visa, tax angles covered)
- Better featured snippet distribution
- Increased internal link equity

💡 **Recommended Priority**:

1. **Cluster 1** (KBLI 40): Foundation for business articles
2. **Cluster 2** (Visa 50): Highest search volume potential
3. **Cluster 3** (Tax 35): High commercial intent
4. **Clusters 4-6** (55): Supporting content + lifestyle

**Estimated Timeline**: 18 batches × 6-8 hours = 13-18 working days

---

_Analysis complete. Ready to begin Batch 1 when you give the signal._
