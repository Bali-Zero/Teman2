---
adversarial_review: exempt-owner-ruled-design-doc
---

# Visa Oracle — Law + Guide (simple model)

Date: 2026-10-17 · Owner ruling (Zero): keep it simple. Two sides only.

## The model

```
            LAW                                   GUIDE
  (what the regulation says)            (how we lead the traveller)
  one card per visa code                one short question path per family
  definition · stay · extension         tile → 2-5 questions → visa(s)
  sponsor · requirements · source       every question = one condition of the law
```

- **LAW** is a card per visa code, copied from the official source (imigrasi.go.id visa index page per code, Permenkumham 22/2023 jo. 11/2024, Kepmen M.IP-08.GR.01.01/2025). Verbatim. No interpretation. Status VERIFIED or TO VERIFY.
- **GUIDE** is per family. It asks only the questions needed to tell the visas of that family apart, in the order that splits them fastest. A question exists only if a law-card condition needs it.
- The engine checks Guide answers against Law cards. Price comes only from the official price list.
- Nothing else. No copy tables keyed to rule codes, no thresholds copied in the frontend.

## The Index (what we cover)

```
A   Visa-free ............ A1
B   Visa on Arrival ...... B1
C   Single-entry visit ... C1 C2 C6 C12*  ·  C7A* C7B* C7C* C8A* C8B* C10*  ·  C18* C22A* C22B*
D   Multiple-entry visit . D1 D2 D12
                           ITAS (KITAS) ............................ → ITAP (KITAP)
E23 Work ................. E23 E23U E23V ........................... → ITAP: TO VERIFY
E28 Investor ............. E28A E28B E28C E28D E28F ................ → Investor KITAP*
E30 Study ................ E30 E30A E30B E30E E30F ................ → ITAP: TO VERIFY
E31 Family / Dependent ... E31A-H E31J ............................. → Dependent KITAP*
E33 Second Home .......... E33 E33A E33B E33C E33E E33F E33G ....... → Retirement KITAP*
X   Bridging ............. BRIDGING
* = sold by Bali Zero, not yet in the Oracle
```

KITAP is not a family. It is the permanent stage of each E family: the same traveller, later in time.
So every E family has two parts: **ITAS** (first permit) and **ITAP** (conversion after holding ITAS).
The ITAP Guide question is one: "Do you already hold this ITAS, and for how long?". Which families can convert, and after how many years, comes from the Law (Permenkumham 22/2023 jo. 11/2024, UU 6/2011) and is TO VERIFY per family during its Law step.

Rule: every code we sell must have a Law card. Coverage check:
`python3 scripts/visa_oracle_family_map.py <pack> --coverage <seed> <prices>` (Appendix B).

## How a family gets finished (4 steps)

1. **Law** — one card per code of the family, from the official source, verbatim.
2. **Guide** — the question path for the family (draw it as a tree on one page).
3. **Test** — every leaf of the tree is a test case against the engine.
4. **Live** — walk each leaf once on prod (internal PIN). Family closed.

Pilot C status: Law cards done (13/13), Guide + data + resolver + 55 path tests green (`apps/backend-rag/backend/services/visa_engine/families/`). Next: wire into the Oracle UI.

Order: **C (pilot, Zero OK 2026-10-17)** → E30 → E28 → E33 → E31 → A/B/D → E23 + Bridging. Each E family includes its ITAP stage.

## The table (ruled 2026-10-17 after the advisor panel)

Panel: Astra (Codex deep), Argon (Gemini 4 Argon high), Kimi K3. Qwen seat answered 403 on every model (known ModelStudio entitlement issue, not consulted).
All three agreed: one row per code, git is master and the DB a projection, requirements as JSONB not a child table, prices only as keys, Guide outside the table, days and months never converted in the schema.
Ruled against: Argon's new table + history table + compatibility view (more moving parts than needed); Kimi's eight separate verbatim columns (the whole card goes in one `law_card` JSONB instead).
Taken from Astra: sponsor is three-valued (C1/C2 are CONDITIONAL), `is_sold` NULL means "to verify".
Taken from Kimi: plain validity dates, `superseded_by` for retired codes (E28G).

Draft migration: `apps/backend-rag/backend/db/migrations_v2/330_visa_types_law_projection.sql` and the generated `331_visa_types_law_family_c.sql` (additive only; existing columns and readers untouched).
Next: one importer `law/<FAMILY>/*.json -> visa_types` with a `--check` mode for CI, then import family C.
Known simplification kept on purpose: the Guide checks month limits as months x 30 days (can only under-approve, never over-approve).

## Open items

- C12 official price: requested from Adit (email 2026-10-17, cc Zero).
- KITAS/KITAP sold under commercial names (Working, Investor, Spouse, Dependent, Retirement, Born; Investor/Dependent/Retirement KITAP + MERP) need a code mapping per family.
- Pack observations to check during each family's Law step (TO VERIFY, not asserted): E31C vs E31F share the same gate; E31D wording vs its sponsor rule; B1 accepts stay ≤ 60 vs a 30-day product; E33A/B/C reached from work/invest tiles.

## Why the old way looped (short)

Questions were hand-written in `flow.ts` while rules lived in the pack, so every rule change needed mirrored frontend edits and re-pinned tests (233 commits, 31 pack versions since July). No family was ever closed. The model above removes the mirror: the Guide is derived from the Law cards.

## Appendix A — generated family map (seq-31)


### A — Visa-free (1 products, 3 gate facts)

- **A1** Visa-Free Tourism Visit (A1) · purposes TOURISM,TRANSIT · stay 30d
  - SUPPORT `purposes∩{TOURISM,TRANSIT} AND person.nationalities∩{BN,MY,TH,SG,PH,KH,...+13} AND stay_days<=30` → A1_BVK_ELIGIBLE
  - EXCLUDE `NOT(person.nationalities∩{BN,MY,TH,SG,PH,KH,...+13})` → BVK_NATIONALITY_ONLY
  - EXCLUDE `process.wants_onshore_conversion=True` → A1_NOT_CONVERTIBLE

### B — VOA (1 products, 2 gate facts)

- **B1** Visa on Arrival — Tourism (B1) · purposes TOURISM · stay 30d
  - SUPPORT `purposes∩{TOURISM} AND stay_days<=60 AND person.nationalities∩{ZA,AL,US,AD,SA,AR,...+91}` → B1_VOA_ELIGIBLE
  - EXCLUDE `NOT(person.nationalities∩{ZA,AL,US,AD,SA,AR,...+91})` → VOA_NATIONALITY_ONLY
  - EXCLUDE `person.nationalities∩{ZA,AL,US,AD,SA,AR,...+91} AND person.nationalities∩{AF,AG,AI,AO,AQ,AS,...+146}` → VOA_DUAL_NATIONALITY_NOT_ASSESSED

### C — Single-entry visit (3 products, 3 gate facts)

- **C1** Tourist Visit Visa (C1) · purposes TOURISM,FAMILY · stay 60d
  - SUPPORT `purposes∩{TOURISM,FAMILY} AND stay_days<=180` → C1_VISIT_ELIGIBLE
- **C2** Business Visit Visa (C2) · purposes BUSINESS_MEETINGS,INVESTMENT · stay 60d
  - SUPPORT `purposes∩{BUSINESS_MEETINGS,INVESTMENT} AND fam.sponsor_confirmed=True AND stay_days<=180` → C2_BUSINESS_ELIGIBLE
  - EXCLUDE `purposes∩{BUSINESS_MEETINGS} AND work.indonesia_source_compensation=True` → BUSINESS_LOCAL_COMPENSATION_NOT_ALLOWED
- **C6** Social Activity Visit Visa (C6) · purposes OTHER · stay 60d
  - SUPPORT `purposes∩{OTHER} AND fam.sponsor_confirmed=True AND stay_days<=180` → C6_SOCIAL_ELIGIBLE

### D — Multiple-entry visit (3 products, 4 gate facts)

- **D1** Visit Visa Tourism — Multiple Entry (D1) · purposes TOURISM,FAMILY,TRANSIT,BUSINESS_MEETINGS · stay 60d
  - SUPPORT `purposes∩{TOURISM,FAMILY,TRANSIT,BUSINESS_MEETINGS} AND stay_days<=180 AND entry_pattern=MULTIPLE` → PURPOSE_PRODUCT_MATCH
  - SUPPORT `purposes∩{TOURISM,FAMILY,TRANSIT,BUSINESS_MEETINGS} AND entry_pattern=MULTIPLE AND purposes∩{TOURISM,FAMILY,TRANSIT,BUSINESS_MEETINGS} AND stay_days<=180 AND entry_pattern=MULTIPLE` → PASSPORT_VALIDITY_6_MONTHS_REQUIRED
  - SUPPORT `purposes∩{TOURISM,FAMILY,TRANSIT,BUSINESS_MEETINGS} AND entry_pattern=MULTIPLE AND purposes∩{TOURISM,FAMILY,TRANSIT,BUSINESS_MEETINGS} AND stay_days<=180 AND entry_pattern=MULTIPLE` → PROOF_OF_FUNDS_D1
  - SUPPORT `purposes∩{TOURISM,FAMILY,TRANSIT,BUSINESS_MEETINGS} AND entry_pattern=MULTIPLE AND purposes∩{TOURISM,FAMILY,TRANSIT,BUSINESS_MEETINGS} AND stay_days<=180 AND entry_pattern=MULTIPLE` → CV_REQUIRED
  - SUPPORT `purposes∩{TOURISM,FAMILY,TRANSIT,BUSINESS_MEETINGS} AND entry_pattern=MULTIPLE AND purposes∩{TOURISM,FAMILY,TRANSIT,BUSINESS_MEETINGS} AND stay_days<=180 AND entry_pattern=MULTIPLE` → ITINERARY_REQUIRED
  - SUPPORT `purposes∩{TOURISM,FAMILY,TRANSIT,BUSINESS_MEETINGS} AND entry_pattern=MULTIPLE AND purposes∩{TOURISM,FAMILY,TRANSIT,BUSINESS_MEETINGS} AND stay_days<=180 AND entry_pattern=MULTIPLE` → SUPPORT_LETTER_REQUIRED
  - EXCLUDE `purposes∩{BUSINESS_MEETINGS} AND work.indonesia_source_compensation=True` → BUSINESS_LOCAL_COMPENSATION_NOT_ALLOWED
- **D2** Visit Visa Business — Multiple Entry (D2) · purposes BUSINESS_MEETINGS,TOURISM,FAMILY · stay 60d
  - SUPPORT `purposes∩{BUSINESS_MEETINGS} AND stay_days<=180` → PURPOSE_PRODUCT_MATCH
  - SUPPORT `purposes∩{BUSINESS_MEETINGS} AND purposes∩{BUSINESS_MEETINGS} AND stay_days<=180` → PASSPORT_VALIDITY_6_MONTHS_REQUIRED
  - SUPPORT `purposes∩{BUSINESS_MEETINGS} AND purposes∩{BUSINESS_MEETINGS} AND stay_days<=180` → PROOF_OF_FUNDS_D2
  - SUPPORT `purposes∩{BUSINESS_MEETINGS} AND purposes∩{BUSINESS_MEETINGS} AND stay_days<=180` → CV_REQUIRED
  - SUPPORT `purposes∩{BUSINESS_MEETINGS} AND purposes∩{BUSINESS_MEETINGS} AND stay_days<=180` → ITINERARY_REQUIRED
  - SUPPORT `purposes∩{BUSINESS_MEETINGS} AND purposes∩{BUSINESS_MEETINGS} AND stay_days<=180` → SUPPORT_LETTER_REQUIRED
  - EXCLUDE `purposes∩{BUSINESS_MEETINGS} AND work.indonesia_source_compensation=True` → BUSINESS_LOCAL_COMPENSATION_NOT_ALLOWED
- **D12** Visit Visa Pre-Investment — Multiple Entry (D12) · purposes INVESTMENT,TOURISM,FAMILY · stay 180d
  - SUPPORT `purposes∩{INVESTMENT} AND stay_days<=360` → PURPOSE_PRODUCT_MATCH
  - SUPPORT `purposes∩{INVESTMENT} AND stay_days<=360` → PASSPORT_VALIDITY_6_MONTHS_REQUIRED
  - SUPPORT `purposes∩{INVESTMENT} AND stay_days<=360` → PROOF_OF_FUNDS_D12
  - SUPPORT `purposes∩{INVESTMENT} AND stay_days<=360` → CV_REQUIRED
  - SUPPORT `purposes∩{INVESTMENT} AND stay_days<=360` → ITINERARY_REQUIRED
  - SUPPORT `purposes∩{INVESTMENT} AND stay_days<=360` → SUPPORT_LETTER_REQUIRED
  - EXCLUDE `process.wants_onshore_conversion=True` → D12_NOT_CONVERTIBLE

### E23 — Work (3 products, 6 gate facts)

- **E23** Working Visa (E23) · purposes EMPLOYMENT,TOURISM · stay 365d
  - SUPPORT `purposes∩{EMPLOYMENT} AND work.employer_is_indonesian_entity=True AND work.indonesian_work_sponsor_confirmed=True` → PURPOSE_PRODUCT_MATCH
  - SUPPORT `purposes∩{EMPLOYMENT} AND inv.proposed_role∈{SHAREHOLDER_DIRECTOR,SHAREHOLDER_COMMISSIONER} AND purposes∩{EMPLOYMENT} AND work.employer_is_indonesian_entity=True AND work.indonesian_work_sponsor_confirmed=True` → E23_REQUIRED_FOR_OPERATIONAL_WORK_EVEN_IF_DIRECTOR
  - EXCLUDE `purposes∩{EMPLOYMENT} AND work.employer_is_indonesian_entity=False` → PAID_ACTIVITY_WITHOUT_INDONESIAN_SPONSOR
- **E23U** Working Visa — Foreign Diplomat House Assistant (E23U) · purposes EMPLOYMENT · stay 365d
  - SUPPORT `purposes∩{EMPLOYMENT} AND sponsor.type=INDIVIDUAL AND sponsor.diplomatic_household=True` → E23U_DIPLOMATIC_HOUSEHOLD_ELIGIBLE
- **E23V** Working Visa — Trade and Economic Office (E23V) · purposes EMPLOYMENT · stay 365d
  - SUPPORT `purposes∩{EMPLOYMENT} AND sponsor.type=GOVERNMENT AND sponsor.trade_office=True` → E23V_TRADE_OFFICE_ELIGIBLE

### E28 — Investor (5 products, 9 gate facts)

- **E28A** Investor Visa (E28A) · purposes INVESTMENT · stay 730d
  - SUPPORT `purposes∩{INVESTMENT} AND inv.pt_pma_committed=True AND inv.paid_up_capital_idr>=2500000000 AND inv.own_shareholding_idr>=10000000000` → E28A_OWN_SHAREHOLDING_ELIGIBLE
  - EXCLUDE `inv.paid_up_capital_idr<2500000000` → E28A_PAID_CAPITAL_BELOW_MIN
  - EXCLUDE `inv.own_shareholding_idr<10000000000` → E28A_OWN_SHAREHOLDING_BELOW_MIN
- **E28B** Investor Golden Visa — Company Establishment (E28B) · purposes INVESTMENT · stay 3650d
  - SUPPORT `purposes∩{INVESTMENT} AND inv.establishes_indonesian_company=True AND inv.meets_published_threshold=True` → E28B_COMPANY_ESTABLISHMENT_ELIGIBLE
- **E28C** Investor Golden Visa — Capital Market (E28C) · purposes INVESTMENT · stay 3650d
  - SUPPORT `purposes∩{INVESTMENT} AND inv.capital_market_only=True AND inv.meets_published_threshold=True` → E28C_CAPITAL_MARKET_ELIGIBLE
- **E28D** Investor Golden Visa — Branch or Subsidiary (E28D) · purposes INVESTMENT · stay 3650d
  - SUPPORT `purposes∩{INVESTMENT} AND inv.foreign_branch_or_subsidiary=True AND inv.meets_published_threshold=True AND inv.proposed_role∈{SHAREHOLDER_DIRECTOR,SHAREHOLDER_COMMISSIONER}` → E28D_BRANCH_OR_SUBSIDIARY_ELIGIBLE
- **E28F** Investor Golden Visa — Branch or Subsidiary in the New Capital (IKN) (E28F) · purposes INVESTMENT · stay 3650d
  - SUPPORT `purposes∩{INVESTMENT} AND inv.ikn_subsidiary=True AND inv.meets_published_threshold=True AND inv.foreign_branch_or_subsidiary=True AND inv.proposed_role∈{SHAREHOLDER_DIRECTOR,SHAREHOLDER_COMMISSIONER}` → E28F_IKN_SUBSIDIARY_ELIGIBLE

### E30 — Study (5 products, 4 gate facts)

- **E30** Education Visa (E30) · purposes STUDY · stay Noned
  - SUPPORT `purposes∩{STUDY} AND study.admission_confirmed=True AND study.sponsor_confirmed=True` → PURPOSE_PRODUCT_MATCH
  - SUPPORT `purposes∩{STUDY} AND purposes∩{STUDY} AND study.admission_confirmed=True AND study.sponsor_confirmed=True` → LIVING_COST_USD2000
  - SUPPORT `purposes∩{STUDY} AND purposes∩{STUDY} AND study.admission_confirmed=True AND study.sponsor_confirmed=True` → PASSPORT_VALIDITY_6_MONTHS_REQUIRED
  - EXCLUDE `purposes∩{STUDY} AND study.admission_confirmed=False OR study.sponsor_confirmed=False` → STUDY_ADMISSION_OR_SPONSOR_NOT_CONFIRMED
- **E30A** Primary/Secondary Education Visa (E30A) · purposes STUDY · stay 730d
  - SUPPORT `purposes∩{STUDY} AND study.admission_confirmed=True AND study.sponsor_confirmed=True` → PURPOSE_PRODUCT_MATCH
  - SUPPORT `purposes∩{STUDY} AND purposes∩{STUDY} AND study.admission_confirmed=True AND study.sponsor_confirmed=True` → LIVING_COST_USD2000
  - SUPPORT `purposes∩{STUDY} AND purposes∩{STUDY} AND study.admission_confirmed=True AND study.sponsor_confirmed=True` → PASSPORT_VALIDITY_6_MONTHS_REQUIRED
  - EXCLUDE `purposes∩{STUDY} AND study.levelnot_in{PRIMARY,SECONDARY}` → LEVEL_BAND_DASMEN
  - EXCLUDE `purposes∩{STUDY} AND study.admission_confirmed=False OR study.sponsor_confirmed=False` → STUDY_ADMISSION_OR_SPONSOR_NOT_CONFIRMED
- **E30B** Higher Education Visa (E30B) · purposes STUDY · stay 1460d
  - SUPPORT `purposes∩{STUDY} AND study.admission_confirmed=True AND study.sponsor_confirmed=True` → PURPOSE_PRODUCT_MATCH
  - SUPPORT `purposes∩{STUDY} AND purposes∩{STUDY} AND study.admission_confirmed=True AND study.sponsor_confirmed=True` → LIVING_COST_USD2000
  - SUPPORT `purposes∩{STUDY} AND purposes∩{STUDY} AND study.admission_confirmed=True AND study.sponsor_confirmed=True` → PASSPORT_VALIDITY_6_MONTHS_REQUIRED
  - SUPPORT `purposes∩{STUDY} AND purposes∩{STUDY} AND study.admission_confirmed=True AND study.sponsor_confirmed=True` → STUDY_PERMIT_KEMDIKBUD
  - EXCLUDE `purposes∩{STUDY} AND study.levelnot_in{VOCATIONAL,UNDERGRADUATE,POSTGRADUATE}` → LEVEL_BAND_DIKTI
  - EXCLUDE `purposes∩{STUDY} AND study.admission_confirmed=False OR study.sponsor_confirmed=False` → STUDY_ADMISSION_OR_SPONSOR_NOT_CONFIRMED
- **E30E** SEZ Education Visa (E30E) · purposes STUDY · stay Noned
  - SUPPORT `purposes∩{STUDY} AND study.admission_confirmed=True AND study.sponsor_confirmed=True AND sponsor.type∈{EDUCATION,INDIVIDUAL}` → PURPOSE_PRODUCT_MATCH
- **E30F** Student Exchange Visa (E30F) · purposes STUDY · stay Noned
  - SUPPORT `purposes∩{STUDY} AND study.admission_confirmed=True AND study.sponsor_confirmed=True AND sponsor.type=EDUCATION` → PURPOSE_PRODUCT_MATCH

### E31 — Family (9 products, 10 gate facts)

- **E31A** Family Visa — Spouse of Indonesian Citizen (E31A) · purposes FAMILY · stay 730d
  - SUPPORT `purposes∩{FAMILY} AND fam.relation_to_sponsor=SPOUSE AND fam.sponsor_nationalities∩{ID} AND fam.marriage_registered=True` → PURPOSE_PRODUCT_MATCH
  - SUPPORT `purposes∩{FAMILY} AND fam.relation_to_sponsor=SPOUSE AND fam.sponsor_nationalities∩{ID} AND purposes∩{FAMILY} AND fam.relation_to_sponsor=SPOUSE AND fam.sponsor_nationalities∩{ID} AND fam.marriage_registered=True` → REQ_FUNDS_2000
  - SUPPORT `purposes∩{FAMILY} AND fam.relation_to_sponsor=SPOUSE AND fam.sponsor_nationalities∩{ID} AND purposes∩{FAMILY} AND fam.relation_to_sponsor=SPOUSE AND fam.sponsor_nationalities∩{ID} AND fam.marriage_registered=True` → SPOUSAL_WORK_ARTICLE_61_CONTEXT
  - SUPPORT `process.wants_onshore_conversion=True AND purposes∩{FAMILY} AND fam.relation_to_sponsor=SPOUSE AND fam.sponsor_nationalities∩{ID} AND fam.marriage_registered=True` → KITAP_TWO_YEAR_MARRIAGE_AND_INTEGRATION_NOT_VERIFIED
- **E31B** Family Visa — Spouse of ITAS/ITAP Holder (E31B) · purposes FAMILY · stay 730d
  - SUPPORT `purposes∩{FAMILY} AND fam.relation_to_sponsor=SPOUSE AND fam.marriage_registered=True AND fam.sponsor_status_code∈{E23,E23U,E23V,E28A,E28B,E28C,...+23}` → PURPOSE_PRODUCT_MATCH
  - SUPPORT `purposes∩{FAMILY} AND fam.relation_to_sponsor=SPOUSE AND purposes∩{FAMILY} AND fam.relation_to_sponsor=SPOUSE AND fam.marriage_registered=True AND fam.sponsor_status_code∈{E23,E23U,E23V,E28A,E28B,E28C,...+23}` → REQ_SPONSOR_ITAS_ITAP
- **E31C** Family Visa — Child of Legal Mixed Marriage (E31C) · purposes FAMILY · stay 730d
  - SUPPORT `purposes∩{FAMILY} AND fam.relation_to_sponsor=PARENT AND fam.sponsor_nationalities∩{ID}` → PURPOSE_PRODUCT_MATCH
  - SUPPORT `purposes∩{FAMILY} AND fam.relation_to_sponsor=PARENT AND fam.sponsor_nationalities∩{ID} AND fam.marriage_registered=True` → REQ_MIXED_MARRIAGE_PARENTS
  - EXCLUDE `purposes∩{FAMILY} AND fam.relation_to_sponsor=PARENT AND fam.marriage_registered=False` → REQ_PARENTS_MARRIAGE_REGISTERED
  - EXCLUDE `purposes∩{FAMILY} AND fam.relation_to_sponsor=PARENT AND NOT(fam.sponsor_nationalities∩{ID})` → REQ_PARENT_SPONSOR_INDONESIAN
- **E31D** Family Visa — Stepchild of Foreigner in Legal Mixed Marriage (E31D) · purposes FAMILY · stay 730d
  - SUPPORT `purposes∩{FAMILY} AND fam.relation_to_sponsor=STEPCHILD AND fam.sponsor_confirmed=True AND fam.stepchild_birth_certificate_confirmed=True AND fam.stepchild_marriage_certificate_confirmed=True` → PURPOSE_PRODUCT_MATCH
  - EXCLUDE `purposes∩{FAMILY} AND fam.relation_to_sponsor=STEPCHILD AND NOT(fam.sponsor_nationalities∩{ID})` → E31D_REQ_SPONSOR_INDONESIAN
- **E31E** Family Visa — Child of ITAS/ITAP Holder (E31E) · purposes FAMILY · stay 730d
  - SUPPORT `purposes∩{FAMILY} AND fam.relation_to_sponsor=PARENT AND fam.sponsor_status_code∈{E23,E23U,E23V,E28A,E28B,E28C,...+23} AND derived.age_years<18 AND person.marital_status=SINGLE` → PURPOSE_PRODUCT_MATCH
  - SUPPORT `purposes∩{FAMILY} AND fam.relation_to_sponsor=PARENT AND purposes∩{FAMILY} AND fam.relation_to_sponsor=PARENT AND fam.sponsor_status_code∈{E23,E23U,E23V,E28A,E28B,E28C,...+23} AND derived.age_years<18 AND person.marital_status=SINGLE` → REQ_SPONSOR_ITAS_ITAP
  - EXCLUDE `purposes∩{FAMILY} AND fam.relation_to_sponsor=PARENT AND derived.age_years>=18` → REQ_UNDER_18
  - EXCLUDE `purposes∩{FAMILY} AND fam.relation_to_sponsor=PARENT AND person.marital_statusneqSINGLE` → REQ_UNMARRIED
- **E31F** Family Visa — Child of Indonesian Citizen Parent (E31F) · purposes FAMILY · stay 730d
  - SUPPORT `purposes∩{FAMILY} AND fam.relation_to_sponsor=PARENT AND fam.sponsor_nationalities∩{ID}` → PURPOSE_PRODUCT_MATCH
  - SUPPORT `purposes∩{FAMILY} AND fam.relation_to_sponsor=PARENT AND fam.sponsor_nationalities∩{ID} AND derived.age_years>=18 AND purposes∩{FAMILY} AND fam.relation_to_sponsor=PARENT AND fam.sponsor_nationalities∩{ID}` → E31F_ADULT_AGE_ADVISOR_CHECK
- **E31G** Family Visa — Parent of Indonesian Citizen Child (E31G) · purposes FAMILY · stay 730d
  - SUPPORT `purposes∩{FAMILY} AND fam.relation_to_sponsor=CHILD AND fam.sponsor_nationalities∩{ID}` → PURPOSE_PRODUCT_MATCH
- **E31H** Family Visa — Parent of Child ITAS/ITAP Holder (E31H) · purposes FAMILY · stay 730d
  - SUPPORT `purposes∩{FAMILY} AND fam.relation_to_sponsor=CHILD AND fam.sponsor_status_code∈{E23,E23U,E23V,E28A,E28B,E28C,...+23}` → PURPOSE_PRODUCT_MATCH
  - SUPPORT `purposes∩{FAMILY} AND fam.relation_to_sponsor=CHILD AND purposes∩{FAMILY} AND fam.relation_to_sponsor=CHILD AND fam.sponsor_status_code∈{E23,E23U,E23V,E28A,E28B,E28C,...+23}` → REQ_SPONSOR_ITAS_ITAP
- **E31J** Family Visa — Child Joining Sibling ITAS/ITAP Holder (E31J) · purposes FAMILY · stay 730d
  - SUPPORT `purposes∩{FAMILY} AND fam.relation_to_sponsor=SIBLING AND fam.sponsor_status_code∈{E23,E23U,E23V,E28A,E28B,E28C,...+23}` → PURPOSE_PRODUCT_MATCH
  - SUPPORT `purposes∩{FAMILY} AND fam.relation_to_sponsor=SIBLING AND purposes∩{FAMILY} AND fam.relation_to_sponsor=SIBLING AND fam.sponsor_status_code∈{E23,E23U,E23V,E28A,E28B,E28C,...+23}` → REQ_SPONSOR_ITAS_ITAP
  - EXCLUDE `purposes∩{FAMILY} AND fam.relation_to_sponsor=SIBLING AND derived.age_years>=18` → E31J_REQ_UNDER_18
  - EXCLUDE `purposes∩{FAMILY} AND fam.relation_to_sponsor=SIBLING AND person.marital_status∈{MARRIED,DIVORCED,WIDOWED}` → E31J_REQ_UNMARRIED
  - REVIEW `purposes∩{FAMILY} AND fam.relation_to_sponsor=SIBLING AND person.marital_status=OTHER` → E31J_MARITAL_STATUS_OTHER_REVIEW

### E33 — Second Home (7 products, 15 gate facts)

- **E33** Second Home Visa (E33) · purposes SECOND_HOME,TOURISM · stay 1825d
  - SUPPORT `purposes∩{SECOND_HOME} AND sh.bank_deposit_usd>=130000 AND sh.bank_deposit_at_state_bank=True AND sh.bank_deposit_in_own_name=True` → E33_DEPOSIT_BASIS_ELIGIBLE
  - SUPPORT `purposes∩{SECOND_HOME} AND sh.qualifying_property_value_usd>=1000000` → E33_PROPERTY_BASIS_ELIGIBLE
  - SUPPORT `purposes∩{SECOND_HOME} AND sh.qualifying_property_value_usd>=1000000 AND purposes∩{SECOND_HOME} AND sh.bank_deposit_usd>=130000 AND sh.bank_deposit_at_state_bank=True AND sh.bank_deposit_in_own_name=True OR purposes∩{SECOND_HOME} AND sh.qualifying_property_value_usd>=1000000` → E33_PROPERTY_QUALIFICATION_ADVISOR_CHECK
  - SUPPORT `purposes∩{SECOND_HOME} AND sh.bank_deposit_usd>=130000 OR sh.qualifying_property_value_usd>=1000000 AND purposes∩{SECOND_HOME} AND sh.bank_deposit_usd>=130000 AND sh.bank_deposit_at_state_bank=True AND sh.bank_deposit_in_own_name=True OR purposes∩{SECOND_HOME} AND sh.qualifying_property_value_usd>=1000000` → GUARANTEE_VALUE_MUST_BE_MAINTAINED
  - EXCLUDE `purposes∩{SECOND_HOME} AND purposes∩{EMPLOYMENT}` → E33_EMPLOYMENT_NOT_COVERED
  - REVIEW `purposes∩{SECOND_HOME} AND sh.bank_deposit_usd<130000 AND sh.qualifying_property_value_usd<1000000` → SECOND_HOME_BELOW_THRESHOLD_STUDIO
- **E33A** Second Home Visa — Special-Expertise Government Invitation (E33A) · purposes EMPLOYMENT,TOURISM,FAMILY · stay 3650d
  - SUPPORT `purposes∩{EMPLOYMENT} AND sponsor.type=GOVERNMENT AND sponsor.government_invitation=True` → E33A_GOVERNMENT_INVITATION_ELIGIBLE
  - EXCLUDE `sponsor.typeneqGOVERNMENT` → E33A_SPONSOR_NOT_GOVERNMENT
- **E33B** Second Home Golden Visa — Special-Expertise Collaboration (E33B) · purposes EMPLOYMENT,BUSINESS_MEETINGS,INVESTMENT,TOURISM,FAMILY · stay 3650d
  - SUPPORT `purposes∩{EMPLOYMENT} AND sponsor.type=NONE AND sponsor.government_collaboration=True` → E33B_GOVERNMENT_COLLABORATION_ELIGIBLE
  - EXCLUDE `sponsor.typenot_in{GOVERNMENT,NONE}` → E33B_SPONSOR_NOT_GOVERNMENT_OR_NONE
  - EXCLUDE `purposes∩{EMPLOYMENT} AND work.employer_is_indonesian_entity=False` → PAID_ACTIVITY_WITHOUT_INDONESIAN_SPONSOR
- **E33C** Second Home Golden Visa — World-Figure Government Invitation (E33C) · purposes INVESTMENT,BUSINESS_MEETINGS,TOURISM,FAMILY · stay 3650d
  - SUPPORT `purposes∩{INVESTMENT} AND sponsor.type=GOVERNMENT AND sponsor.world_figure_invitation=True` → E33C_WORLD_FIGURE_INVITATION_ELIGIBLE
  - EXCLUDE `sponsor.typenot_in{GOVERNMENT,NONE}` → E33C_SPONSOR_NOT_GOVERNMENT_OR_NONE
- **E33E** Second Home Golden Visa — Elderly 5-Year (E33E) · purposes RETIREMENT,SECOND_HOME,TOURISM,FAMILY · stay 1825d
  - SUPPORT `purposes∩{RETIREMENT} AND derived.age_years in [55,59] AND purposes∩{RETIREMENT} AND derived.age_years>=55 AND sh.bank_deposit_usd>=50000 AND sh.bank_deposit_at_state_bank=True AND sh.bank_deposit_in_own_name=True AND sh.passive_monthly_income_usd>=3000` → E33E_AGE_55_59_ADVISOR_CHECK
  - SUPPORT `purposes∩{RETIREMENT} AND derived.age_years>=55 AND sh.bank_deposit_usd>=50000 AND sh.bank_deposit_at_state_bank=True AND sh.bank_deposit_in_own_name=True AND sh.passive_monthly_income_usd>=3000` → E33E_RETIREMENT_ELIGIBLE
  - EXCLUDE `purposes∩{RETIREMENT} AND derived.age_years<55` → AGE_BELOW_55
  - EXCLUDE `purposes∩{RETIREMENT} AND sh.passive_monthly_income_usd<3000` → RETIREMENT_INCOME_BELOW_THRESHOLD
- **E33F** Second Home Visa — Elderly 1-Year (E33F) · purposes RETIREMENT,BUSINESS_MEETINGS,TOURISM,FAMILY · stay 365d
  - SUPPORT `purposes∩{RETIREMENT} AND sh.passive_monthly_income_usd>=3000` → E33F_RETIREMENT_ELIGIBLE
  - EXCLUDE `purposes∩{RETIREMENT} AND derived.age_years<55` → AGE_BELOW_55
  - EXCLUDE `purposes∩{RETIREMENT} AND sh.passive_monthly_income_usd<3000` → RETIREMENT_INCOME_BELOW_THRESHOLD
- **E33G** Second Home Visa — Remote Worker (E33G) · purposes REMOTE_WORK,TOURISM,FAMILY · stay 365d
  - SUPPORT `purposes∩{REMOTE_WORK} AND work.employer_is_indonesian_entity=False AND work.serves_indonesian_clients=False AND work.indonesia_source_compensation=False AND work.annual_foreign_income_usd>=60000` → REMOTE_WORK_ELIGIBLE
  - EXCLUDE `work.employer_is_indonesian_entity=True` → INDONESIAN_EMPLOYER_NOT_ALLOWED
  - EXCLUDE `work.indonesia_source_compensation=True` → INDONESIAN_SOURCE_COMPENSATION_BANNED
  - EXCLUDE `purposes∩{REMOTE_WORK} AND work.serves_indonesian_clients=True` → E33G_LOCAL_MARKET_NOT_ALLOWED
  - EXCLUDE `purposes∩{REMOTE_WORK} AND inv.pt_pma_committed=True` → E33G_LOCAL_COMPANY_NOT_ALLOWED
  - EXCLUDE `purposes∩{REMOTE_WORK} AND work.annual_foreign_income_usd<60000` → E33G_INCOME_BELOW_THRESHOLD

### X — Status bridging (1 products, 5 gate facts)

- **BRIDGING** Bridging Visa — Transitional Stay Permit · purposes OTHER · stay 60d
  - SUPPORT `immigration.currently_in_indonesia=True AND immigration.current_status_expiryknownNone AND purposes∩{OTHER} AND requested_product_codeneqBRIDGING AND requested_product_codeknownNone` → BRIDGING_T3_WINDOW_ADVISOR_CHECK
  - SUPPORT `immigration.currently_in_indonesia=True AND immigration.current_status_expiryknownNone AND purposes∩{OTHER} AND requested_product_codeneqBRIDGING AND requested_product_codeknownNone` → BRIDGING_OVERSTAY_SHIELD_PAYMENT_CHECK
  - SUPPORT `immigration.currently_in_indonesia=True AND immigration.current_status_codeknownNone AND purposes∩{OTHER} AND requested_product_codeneqBRIDGING AND requested_product_codeknownNone` → BRIDGING_SOURCE_STATUS_VERIFY
  - SUPPORT `purposes∩{OTHER} AND requested_product_codeneqBRIDGING AND requested_product_codeknownNone` → BRIDGING_DESTINATION_STATED
  - EXCLUDE `immigration.currently_in_indonesia=False` → BRIDGING_ONSHORE_ONLY
  - EXCLUDE `immigration.current_status_code∈{ITK_FROM_BVK,ITK_FROM_VISIT_C,ITK_FROM_VISIT_D,A1,C1,C2,C6}` → BRIDGING_FROM_VISIT_ITK_PROHIBITED
  - EXCLUDE `immigration.current_status_code=ITK_PERALIHAN` → BRIDGING_TO_BRIDGING_PROHIBITED
  - EXCLUDE `immigration.currently_in_indonesia=True AND immigration.violation_history∩{OVERSTAY,DEPORTATION,BLACKLIST,IMMIGRATION_INVESTIGATION}` → BRIDGING_ADVERSE_HISTORY_NOT_ASSESSED

### GLOBAL hard filters

- `derived.has_indonesian_citizenship=True` → APPLICANT_IS_INDONESIAN_CITIZEN
- `immigration.overstay_days>60` → OVERSTAY_EXCEEDS_60_DAYS
- `person.nationalities∩{AF,IL,KP,LR,NG,SO}` → CALLING_VISA_NATIONALITY_NOT_ASSESSED
- `immigration.overstay_days>0` → ACTIVE_OVERSTAY_SETTLE_FIRST
- `derived.is_minor=True AND fam.sponsor_confirmed=False` → MINOR_SPONSOR_NOT_CONFIRMED


## Appendix B — Index coverage (seed x price list x pack seq-31)

| Code | Name (seed) | Sold | In Oracle |
|---|---|---|---|
| A1 | Visa Free Tourism | yes | yes |
| A4 | Visa Free Government Assignment |  |  |
| A36 | Visa Free Ship and Aircraft Crew |  |  |
| A37 | Visa Free Ship Crew in Indonesian Waters |  |  |
| B1 | Visit Visa Tourism | yes | yes |
| B4 | Visit Visa Government Assignmentan |  |  |
| F1 | Visit Visa Tourism |  |  |
| F4 | Visit Visa Government Assignmentan |  |  |
| C1 | Visit Visa Tourism | yes | yes |
| C2 | Visit Visa Business | yes | yes |
| C3 | Visit Visa Medical Treatment |  |  |
| C4 | Visit Visa Government Assignment |  |  |
| C5 | Visit Visa Media dan Pers |  |  |
| C5A | Visit Visa Content Creator |  |  |
| C6 | Visit Visa Social Activity | yes | yes |
| C7 | Visit Visa Penampilan Seni dan Budaya |  |  |
| C7A | Visit Visa Music Performance | yes |  |
| C7B | Visit Visa Kru Music Performance | yes |  |
| C7C | Visit Visa Penampilan Bakat dan Seni | yes |  |
| C8 | Visit Visa Sports Activity |  |  |
| C8A | Visit Visa Athlete | yes |  |
| C8B | Visit Visa Sports Official | yes |  |
| C9 | Visit Visa Short Study |  |  |
| C9A | Visit Visa Short Religious Training |  |  |
| C9B | Visit Visa Short Indonesian Language Training |  |  |
| C10 | Visit Visa Narasumber Kegiatan Business | yes |  |
| C10A | Visit Visa Religious Lecturer |  |  |
| C11 | Visit Visa Promosi Produk dan Jasa |  |  |
| C11A | Visit Visa Promosi Produk dan Jasa |  |  |
| C12 | Visit Visa Pre-Investment |  |  |
| C13 | Visit Visa Awak Bergabung dengan Alat Angkut |  |  |
| C14 | Visit Visa Pembuatan dan Produksi Film |  |  |
| C15 | Visit Visa Emergency Handling |  |  |
| C16 | Visit Visa Industrial Development Instructor |  |  |
| C17 | Visit Visa Audit, Kendali Mutu, dan Inspeksi Perusahaan |  |  |
| C18 | Visit Visa Foreign Worker Competency Test | yes |  |
| C19 | Visit Visa After-Sales Service |  |  |
| C20 | Visit Visa Pemasangan dan Perbaikan Mesin |  |  |
| C21 | Visit Visa Menghadiri Proses Peradilan |  |  |
| C22 | Visit Visa Internship |  |  |
| C22A | Visit Visa Internship Akademik | yes |  |
| C22B | Visit Visa Internship Kompetensi | yes |  |
| D1 | Visit Visa Tourism (Multiple Entry) | yes | yes |
| D2 | Visit Visa Business | yes | yes |
| D3 | Visit Visa Medical Treatment |  |  |
| D4 | Visit Visa Government Assignment |  |  |
| D7 | Visit Visa Penampilan Seni dan Budaya |  |  |
| D8 | Visit Visa Sports Activity |  |  |
| D12 | Visit Visa Pre-Investment | yes | yes |
| D14 | Visit Visa Pembuatan and Produksi Film |  |  |
| D17 | Visit Visa Audit, Kendali Mutu, dan Inspeksi Perusahaan |  |  |
| E23 | Working Visa | yes | yes |
| E23A | Working Visa Special Economic Zone |  |  |
| E23U | Working Visa Foreign Diplomat House Assistant |  | yes |
| E23V | Working Visa Kantor Dagang dan Ekonomi |  | yes |
| E23X | Working Visa Indonesian Government Expert |  |  |
| E23Y | Working Visa Digital Field Expert |  |  |
| E25 | Working Visa Komisaris dan Eksekutif Perusahaan |  |  |
| E25A | Working Visa Company Commissioner |  |  |
| E25B | Working Visa Company Director |  |  |
| E25C | Working Visa Wakil Company Director |  |  |
| E25D | Working Visa Company General Manager |  |  |
| E25E | Working Visa Company Manager |  |  |
| E25F | Working Visa Company Supervisor |  |  |
| E26 | Working Visa Awak Kapal, Alat Apung, dan Instalasi Lepa |  |  |
| E27 | Working Visa Cleric |  |  |
| E29 | Working Visa Researcher |  |  |
| E28 | Investor Visa |  |  |
| E28A | Investor Visa |  | yes |
| E28B | E28B - Investor Golden Visa (Company Establishment) |  | yes |
| E28C | E28C - Investor Golden Visa (Capital Market) |  | yes |
| E28D | Investor Visa Pendirian Cabang atau Anak Perusahaan Gol |  | yes |
| E28E | Investor Visa Special Economic Zone |  |  |
| E28F | Investor Visa Pendirian Cabang atau Anak Perusahaan di  |  | yes |
| E28G | E28G - Not a current visa (see E28A, E28B or E28C) |  |  |
| E30 | Education Visa |  | yes |
| E30A | Education Visa Dasar dan Menengah | yes | yes |
| E30B | Education Visa Tinggi | yes | yes |
| E30E | Education Visa Special Economic Zone |  | yes |
| E30F | Visa Student Exchange |  | yes |
| E31 | Family Visa |  |  |
| E31A | Family Visa Spouse of Indonesian Citizen |  | yes |
| E31B | Family Visa Spouse of ITAS/ITAP Holder |  | yes |
| E31C | Family Visa Child of Legal Mixed Marriage |  | yes |
| E31D | Family Visa Stepchild of Foreigner in Legal Mixed Marri |  | yes |
| E31E | Family Visa Child of ITAS/ITAP Holder |  | yes |
| E31F | Family Visa Anak Dengan Orang Tua WNI |  | yes |
| E31G | Family Visa Parent of Indonesian Child |  | yes |
| E31H | Family Visa Orang Tua dari Child of ITAS/ITAP Holder |  | yes |
| E31J | Family Visa Anak yang Bergabung dengan Saudara Kandung  |  | yes |
| E32 | Repatriation Visa dan Former Indonesian Citizen Descend |  |  |
| E32A | Repatriation Visa 5 Tahun |  |  |
| E32B | Visa Former Indonesian Citizen Descendant 5 Atau 10 Tah |  |  |
| E32C | Repatriation Visa 2 Tahun |  |  |
| E32D | Repatriation Visa 1 Tahun Golden Visa |  |  |
| E32E | Repatriation Visa Permanent Residence Global Citizen of |  |  |
| E32F | Repatriation Visa Special Expertise Global Citizen of I |  |  |
| E32G | Visa Former Indonesian Citizen Descendant Permanent Res |  |  |
| E32H | Visa Former Indonesian Citizen Descendant Special Exper |  |  |
| E33 | Second Home Visa | yes | yes |
| E33A | Second Home Visa Tenaga Ahli Government Invitation |  | yes |
| E33B | Second Home Visa Kolaborasi Special Expertise Golden Vi |  | yes |
| E33C | Second Home Visa World Figure Government Invitation |  | yes |
| E33D | Second Home Visa World Figure Company Establishment |  |  |
| E33E | Second Home Visa Elderly for 5 Years Golden Visa | yes | yes |
| E33F | Second Home Visa Elderly for 1 Year | yes | yes |
| E33G | Second Home Visa Remote Worker / Digital Nomad Golden V | yes | yes |
| E34 | Visa Medical Treatment |  |  |
| E35 | Working Holiday Visa |  |  |
| E35A | Working Holiday Visa Australia |  |  |
| E23-FREELANCE | Freelance KITAS (E23) |  |  |
| EPO | EPO (Exit Permit Only) | yes |  |
| ERP | ERP (Exit Re-entry Permit) | yes |  |
| SKTT | SKTT Registration | yes |  |

Sold but NOT in Oracle (12): C7A, C7B, C7C, C8A, C8B, C10, C18, C22A, C22B, EPO, ERP, SKTT
