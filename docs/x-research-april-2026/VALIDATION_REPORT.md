# NB VALIDATION REPORT — Grok Research April 2026
**Validated:** 2026-04-06 via NotebookLM (NB-2 through NB-6)

## ERRORI TROVATI (da correggere nelle ricerche Grok)

### NB-2 Immigration
- **Q13 Golden Visa Tier 1: WRONG** — Grok dice USD 2.5M/10yr → REALE: **USD 5M/10yr** (Permenkumham 11/2024 Pasal 40). USD 2.5M è per 5yr E28B.
- Q08/Q14 E33G $60K income: CONFERMATO
- E33G no Indonesian clients: CONFERMATO
- KITAS Investor E28A 2 years: CONFERMATO
- B211A 180 days no work: CONFERMATO

### NB-3 Company
- **Q15 KBLI deadline: WRONG** — Grok dice June 18, 2026 → REALE: **June 18, 2026** (BKPM Reg 5/2025). Failure = automatic license cancellation.
- **Q27 LKPM "2 missed = NIB suspension": NEEDS CORRECTION** — NB-3 flagged as wrong (check exact penalty wording)
- Q18 PT PMA IDR 2.5B + 12mo lock: CONFERMATO
- Q18 IDR 10B per KBLI/location: CONFERMATO
- Q28 Akta costs IDR 8-25M: CONFERMATO
- Q29 OSS processing times: CONFERMATO

### NB-4 Tax
- **Q11 VAT 12%: PARTIALLY WRONG** — 12% applies ONLY to luxury goods (PMK 131/2024). Standard goods use 11% effective rate (DPP = 11/12 of selling price).
- Q11 Corporate tax 22%: CONFERMATO (+ 50% reduction on first IDR 4.8B if turnover < IDR 50B)
- Q11 CoreTax replaces DJP Online: CONFERMATO
- Q11 NPWP 16-digit: CONFERMATO (but expats get special 16-digit, NOT NIK)
- Q21 183-day rule: CONFERMATO
- PPh final 0.5%: CONFERMATO

### NB-5 Property
- Hak Milik forbidden for foreigners: CONFERMATO
- Hak Pakai 30+20+30=80yr: CONFERMATO
- HGB via PMA 30+20+30: CONFERMATO
- Nominee illegal UUPA Art. 26: CONFERMATO (+ Perda Bali 4/2026 makes it CRIMINAL)
- Pink zone for rentals: CONFERMATO
- BPHTB 5%: CONFERMATO

### NB-6 Operations
- **Q32 Halal exemption tourist areas: WRONG** — NO practical exemption. UU 33/2014 mandatory from Oct 18, 2024 for large-scale PT PMA. Process via SIHALAL, valid 4 years.
- SIUP-MB A/B/C categories: CONFERMATO
- SPPL vs AMDAL: CONFERMATO
- DJKI trademark 6-18 months: PARTIALLY CONFIRMED
- API-U/API-P: CONFERMATO
- BPJS 5% salary: CONFERMATO

## SUMMARY: 4 ERRORS FOUND IN GROK RESEARCH
1. Golden Visa Tier 1: $2.5M → $5M
2. KBLI deadline: June 18 → June 18, 2026
3. VAT: 12% → 11% effective (12% only luxury)
4. Halal: no tourist exemption — mandatory since Oct 2024

These must be corrected before publishing any content.

---

## CROSS-DOMAIN VALIDATION (7 queries, 6 NB)

### Q03 DTA Italy-Indonesia (NB-3 + NB-4)
- Dividend WHT 10%/15% per treaty: **CONFERMATO** (NB-4)
- Tax credit mechanism: **CONFERMATO**
- Combined effective ~40-45%: **PARTIALLY CONFIRMED** — Indonesian side correct, Italian side outside NB scope
- Italian HoldCo 25%+ → 10% WHT: **CONFERMATO** (with strict PMK 112/2025 caveats)
- PT PMA shares ≠ PE: **CONFERMATO** (NB-3)

### Q04 AIRE (NB-2 + NB-4)
- Consulate for Bali: **NB-2 has no AIRE sources** — Italian law outside scope. Need independent verification.
- AIRE ↔ Italian tax residency: **NB-4 confirms Indonesian side** — 183 days = SPDN. CFC Art.167 TUIR outside NB scope.
- Indonesia 22% CIT generally NOT low-tax for CFC: **CONFIRMED** — unless Tax Holiday reduces to 0% (PMK 69/2024), which COULD trigger CFC.
- DTA tie-breaker Art.4: **CONFIRMED** — hierarchy: permanent home → center of vital interests → habitual abode → nationality.

### Q05 CFC/Quadro RW (NB-4)
- CFC rules: **Outside NB scope** (Italian law). NB-4 confirms Indonesia at 22% is generally NOT low-tax.
- Quadro RW/IVAFE: **Outside NB scope** (Italian reporting obligations). Need Italian commercialista.

### Q19+Q42 Property + Villa (NB-5 + NB-3)
- PT PMA HGB for villa: **CONFIRMED**
- Airbnb legal + needs NIB (replaces TDUP): **CONFIRMED** + NEW: March 31, 2026 OTA delisting deadline for non-NIB properties
- Pink zone only: **CONFIRMED**
- Management fee 20-30%: **CONFIRMED** (typically 70/30 or 80/20 owner-favor)
- **PPh rental 10% CONFIRMED for residents, but 20% PPh 26 for non-residents** (reduced by DTA)
- **Villa yields by area: NOT VALIDATED** — NB-5 doesn't have yield data. Grok numbers (8-15%) are unverified.
- **NEW: PHR (Hotel & Restaurant Tax) additional 10%** on top of income tax

### Q21 Tax Residency (NB-2 + NB-4)
- E33G ≠ automatic tax resident: **CONFIRMED** — becomes resident only at 183 days
- KITAS E23 (worker) = automatic tax resident from day 1: **CONFIRMED**
- KITAS E28A (investor) = resident at 183 days: **CONFIRMED**
- KITAP = automatic permanent tax resident: **CONFIRMED**
- B211A/C1 max 180 days: **CONFIRMED** — border runs can still trigger 183-day fiscal rule
- DJP + Immigration sharing data: **CONFIRMED** — active enforcement underway

## NEW FINDINGS FROM CROSS-DOMAIN
1. **OTA delisting deadline March 31, 2026** — all Airbnb/OTA listings need verified NIB or face removal
2. **Non-resident rental income 20% PPh 26** (not 10%) — critical for Italian owners not yet SPDN
3. **PHR 10% hotel/restaurant tax** additional to income tax on villa rental
4. **Tax Holiday (PMK 69/2024) could trigger CFC** — if PT PMA gets 0% rate, Italian CFC rules may apply
5. **KITAS E23 = immediate tax residency** vs E28A/E33G = 183-day trigger
