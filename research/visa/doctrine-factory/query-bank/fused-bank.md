---
date: 2026-08-17
domain: visa
client_case: none
sources: [visa-oracle-adjudication/output-A, visa-oracle-adjudication/output-B, visa-oracle-adjudication/output-C, rulepack-prod-007.source.json, research/visa/doctrine-factory/reachability/rulepack-prod-007-reachability.md]
adversarial_review: kimi-k3
---

# E2b PREP — fused NB-2 query bank (A∪B∪C) — index

Local-only artifact. No live NB-2 queries executed in this task (E2b PREP, not E2b execution).
Companion machine-readable file: `fused-bank.jsonl` (one JSON record per line).

## Real per-blueprint counts (measured on disk, not trusted from prose)

| Blueprint | Doc's own stated count | Measured (grep/parse) | Note |
|---|---|---|---|
| output-A `03-nb2-interrogation-program.md` | "140 query" (title) | **140** (B00×38 + B01..B19) | matches |
| output-B `03-nb2-interrogation-program.md` | "164 queries, 18 batches" (title + batch table) | **166** (B0×6..B17×5, counted `QB\d+-\d+` rows) | **doc's own header/table undercounts by 2** — verified via `grep -oE '^\| QB[0-9]+-[0-9]+' \| wc -l` |
| output-C `blueprint-completa.md` §3.6 | "154 work item base... 164 specification totali" | **154** numeric `VO-NB2-0xx` + **10** `VO-NB2-B1N-*` = **164** | matches |

No blueprint carries a discrete "20/18/10 refuter" query list as such — output-A's 20-refuter figure in the task brief corresponds to its **10-item red-team attack plan** (§6.4, categories not individual queries); output-B carries no separate refuter batch (its red-team content is prose critique in `08-red-team-and-verdict.md`); output-C's "+10" is the B1N external-neighbor batch, not refuter queries. Noted, not silently corrected — see `dedup-log.md`.

## Fusion result

**247 fused unique queries** (raw ≈470 across the three banks: 140+166+164). This is materially above the OD-3 planning estimate of "~160-170" — see `dedup-log.md` for why: OD-3's estimate pre-dated a line-by-line fusion pass; a defensible dedup (same target-product-set + same question intent, not just same batch) that does not silently drop genuine discriminants lands near 247, not 165. Flagged for Zero/gate-owner as a finding, not force-fitted down to the earlier estimate.

| Topic | Label | Fused queries | Raw across A+B+C (approx) |
|---|---|---:|---:|
| T0 | Corpus calibration, freshness, canary, temporal supersession | 14 | ~29 |
| T1 | Product doctrine card (38 catalog codes) | 38 | ~114 |
| T1N | External neighbor doctrine (10, outside catalog) | 10 | ~10 |
| T2 | Boundary comparatives (incl. BLOCKED-11 pinpoint hunt) | 31 | ~42 |
| T3 | Activity boundary (permitted vs forbidden / work vs visit) | 18 | ~42 |
| T4 | Thresholds & financial values | 10 | ~26 |
| T5 | Entry & duration semantics | 8 | ~24 |
| T6 | Compensation: Indonesian-source vs foreign-source | 5 | ~8 |
| T7 | Sponsor, guarantor, invitation | 13 | ~17 |
| T8 | Onshore/offshore, extension, conversion, KITAP | 12 | ~15 |
| T9 | Nationality, calling visa, dual citizenship | 6 | ~15 |
| T10 | Age, minors, family, marriage, dependents | 10 | ~20 |
| T11 | Work specifics (RPTKA/DKPTKA, secondment, employer change) | 8 | ~7 |
| T12 | Study, exchange, KEK, izin belajar | 5 | ~15 |
| T13 | Remote work, clients, tax-residency interplay (E33G) | 6 | ~9 |
| T14 | Retirement & second home specifics (E33/E33E/E33F) | 6 | ~6 |
| T15 | Risk: overstay, refusals, blacklist, criminal record | 8 | ~16 |
| T16 | Documents: non-auto-verifiable, legalization, evidence | 10 | ~16 |
| T17 | No-path cases & legal alternatives | 8 | ~9 |
| T18 | Edge cases, multi-purpose, benchmark variants | 9 | ~10 |
| T20 | Gold personas / QA / compiler-local tests (NOT NB-2-facing) | 12 | ~11 |
| **Total** | | **247** | **~470** |

## Priority (E2a slice overlap)

- `SLICE_COVERED_BY_E2A` (81 queries): target-product set intersects the E2a vertical-slice product set (D1, D2, D12, C1, C2, A1, B1, E23, E28A, E33G) or its refuters (E31B, E31D). May be partially answered by E2a's slice execution — check the E2a claim ledger before re-running blind once E2b execution starts.
- `BULK` (166 queries): outside the slice, pure E2b bulk territory.

## Per-topic breakdown

### T0 — Corpus calibration, freshness, canary, temporal supersession (14)

| query_id | target products | provenance | text (truncated) |
|---|---|---|---|
| VO-FUSED-T0-001 | ALL | VO-NB2-003 | CANARY A (conversation isolation): establish only the purpose described by the sources for D1, no duration/sponsor/requirements, return exac… |
| VO-FUSED-T0-002 | ALL | VO-NB2-004 | CANARY B (conversation isolation): same protocol for D2. Insert marker CANARY-D2-B. |
| VO-FUSED-T0-003 | ALL | VO-NB2-005 | CANARY C (conversation isolation): same protocol for D12. Insert marker CANARY-D12-C. |
| VO-FUSED-T0-004 | ALL | VO-NB2-001 | Validate snapshot/isolation/search integrity: list acts present in the source snapshot that may govern visa classification; for each registe… |
| VO-FUSED-T0-005 | ALL | VO-NB2-002 | Identify which corpus sources are primary norms, ministerial acts, official operational instructions, internal interpretations or secondary … |
| VO-FUSED-T0-006 | ALL | QB0-01,QB0-02 | List every source containing text of or official guidance on the named primary instruments (Permenimipas 5/2025, Permenkumham 22/2023, Perme… |
| VO-FUSED-T0-007 | ALL | QB0-03,nb2q-b17-01 | Does the notebook contain the current 110-code visa-index frame under Kepmen M.IP-08.GR.01.01/2025 (vs the older 133-code frame)? Map old B2… |
| VO-FUSED-T0-008 | ALL | QB0-04,QB1-01 | What does UU 63/2024 change about guarantors/sponsors, re-entry permits (MERP), and overstay sanctions? Cite amending articles and effective… |
| VO-FUSED-T0-009 | ALL | QB1-03,QB1-04,QB1-05 | Map the 133→110 index delta: which codes were merged, renamed or abolished (cite the Kepmen annex)? Is circular SE IMI-453.GR.01.01 (or succ… |
| VO-FUSED-T0-010 | ALL | QB1-06,QB1-07,QB1-08 | After UU 63/2024 abolished MERP, what re-entry mechanics apply to KITAS/KITAP holders? For each instrument, state its current status (in for… |
| VO-FUSED-T0-011 | ALL | nb2q-b17-04,nb2q-b17-03 | Are any products in the current classification deprecated, renamed or split from earlier codes, and since when? Where do sources conflict on… |
| VO-FUSED-T0-012 | ALL | VO-NB2-133,VO-NB2-135 | For every claim carrying sources of different dates, determine whether it is amendment, derogation, implementation or contradiction and assi… |
| VO-FUSED-T0-013 | ALL | VO-NB2-100,VO-NB2-134 | For each product separate 'appears in the source-snapshot classification' from 'accepted on the eVisa/portal channel per a dated operational… |
| VO-FUSED-T0-014 | ALL | VO-NB2-136 | Define what to show when the portal, payment or a government service is temporarily unavailable, without turning it into an ineligibility ve… |

### T1 — Product doctrine card (38 catalog codes) (38)

One row per catalog code — see `fused-bank.jsonl` (topic=`T1`), not enumerated here for brevity.

### T1N — External neighbor doctrine (10, outside catalog) (10)

One row per catalog code — see `fused-bank.jsonl` (topic=`T1N`), not enumerated here for brevity.

### T2 — Boundary comparatives (incl. BLOCKED-11 pinpoint hunt) (31)

| query_id | target products | provenance | text (truncated) |
|---|---|---|---|
| VO-FUSED-T2-001 | A1,B1,C1 | VO-NB2-045 | Compare A1, B1 and C1: identify the single fact or minimum fact-set that separates each product, with a counterexample excluding every false… |
| VO-FUSED-T2-002 | C1,D1 | VO-NB2-046 | Compare C1 and D1 separating purpose, single/multiple entry, per-entry stay, extension, passive vs active commercial activity. |
| VO-FUSED-T2-003 | C2,D2 | VO-NB2-047 | Compare C2 and D2 separating purpose, single/multiple entry, validity, per-entry stay, extension, sponsor and documents. |
| VO-FUSED-T2-004 | C2,D2,D12 | VO-NB2-048 | Compare C2, D2 and D12 for meetings, negotiation, signing, site observation, survey and feasibility study; identify the minimum fact cut. |
| VO-FUSED-T2-005 | C6 | VO-NB2-049 | Starting from the C6 doctrine card, compare C6 with the two legally nearest alternatives found in the sources and demonstrate why the other … |
| VO-FUSED-T2-006 | E23,E23U,E23V | VO-NB2-050 | Compare E23, E23U and E23V for nature of the work engagement, employer/client, sponsor, duration, linked permits and duties. |
| VO-FUSED-T2-007 | E23U,E23V | VO-NB2-051 | Isolate the necessary-and-sufficient difference between E23U and E23V; also return two twin personas differing by exactly one fact. |
| VO-FUSED-T2-008 | E28A,E28B,E28C,E28D,E28F | VO-NB2-052 | Build the complete E28A/B/C/D/F matrix: investment vehicle/entity, applicant role, sponsor/guarantee type if any, location, capital/investme… |
| VO-FUSED-T2-009 | E28A,E28B | VO-NB2-053 | Compare E28A and E28B with twin personas and identify the first fact separating the corporate-role investor path from the company-establishm… |
| VO-FUSED-T2-010 | E28C,E28D,E28F | VO-NB2-054 | Compare E28C, E28D and E28F separating passive investment without incorporation, branch/subsidiary, and IKN subsidiary; verify ownership, pa… |
| VO-FUSED-T2-011 | E30,E30A,E30B | VO-NB2-055 | Compare E30, E30A and E30B for institution level, program type, duration, sponsor and izin belajar. |
| VO-FUSED-T2-012 | E30E,E30F,E30A,E30B | VO-NB2-056 | Compare E30E and E30F, and their neighbors E30A/E30B, separating KEK institution from exchange program: territorial status, study level, sen… |
| VO-FUSED-T2-013 | E31A,E31B,E31C | VO-NB2-057 | Compare E31A, E31B and E31C for family relationship, principal's citizenship/status, age and sponsor. |
| VO-FUSED-T2-014 | E31D,E31E,E31F | VO-NB2-058 | Compare E31D, E31E and E31F for family relationship, principal's status, age and documentary proof. |
| VO-FUSED-T2-015 | E31G,E31H,E31J | VO-NB2-059 | Compare E31G, E31H and E31J for relationship, principal, age, guardian and any linked work/study rights. |
| VO-FUSED-T2-016 | E33,E33A,E33B,E33C | VO-NB2-060 | Compare E33, E33A, E33B and E33C separating financial second-home, special-expertise-with-government-invitation, expertise-with-cooperation,… |
| VO-FUSED-T2-017 | E33,E33E,E33F,E33G | VO-NB2-061 | Compare E33, E33E, E33F and E33G for residence basis, age threshold if any, investment/income, employer/client locus, sponsor/documents and … |
| VO-FUSED-T2-018 | BRIDGING | VO-NB2-062 | Explain when BRIDGING is legally necessary versus a direct application, and when it is unavailable; identify initial status, target status a… |
| VO-FUSED-T2-019 | C,D | VO-NB2-063 | For every single-entry/multiple-entry pair present in the catalog, identify whether the purpose is identical and which facts separate only e… |
| VO-FUSED-T2-020 | ALL | VO-NB2-064 | For each of the 38 products assign the two legally nearest alternatives and the minimum discriminant; flag products without a reliable neigh… |
| VO-FUSED-T2-021 | E23U,E23 | QB15-01 | For E23U vs E23: quote verbatim the passage (instrument, article, ayat) that defines who qualifies for the first code as distinct from the s… |
| VO-FUSED-T2-022 | E23V,E23,E23U | QB15-02 | For E23V vs E23/E23U: quote verbatim the passage (instrument, article, ayat) that defines who qualifies for the first code as distinct from … |
| VO-FUSED-T2-023 | E28B,E28A | QB15-03 | For E28B vs E28A: quote verbatim the passage (instrument, article, ayat) that defines who qualifies for the first code as distinct from the … |
| VO-FUSED-T2-024 | E28C,E28A | QB15-04 | For E28C vs E28A: quote verbatim the passage (instrument, article, ayat) that defines who qualifies for the first code as distinct from the … |
| VO-FUSED-T2-025 | E28D,E28A,E28B,E28C | QB15-05 | For E28D vs E28A/B/C: quote verbatim the passage (instrument, article, ayat) that defines who qualifies for the first code as distinct from … |
| VO-FUSED-T2-026 | E28F | QB15-06 | For E28F vs other E28: quote verbatim the passage (instrument, article, ayat) that defines who qualifies for the first code as distinct from… |
| VO-FUSED-T2-027 | E30E,E30 | QB15-07 | For E30E vs E30: quote verbatim the passage (instrument, article, ayat) that defines who qualifies for the first code as distinct from the s… |
| VO-FUSED-T2-028 | E30F,E30 | QB15-08 | For E30F vs E30: quote verbatim the passage (instrument, article, ayat) that defines who qualifies for the first code as distinct from the s… |
| VO-FUSED-T2-029 | E33A,E33 | QB15-09 | For E33A vs E33: quote verbatim the passage (instrument, article, ayat) that defines who qualifies for the first code as distinct from the s… |
| VO-FUSED-T2-030 | E33B,E33A,E33C | QB15-10 | For E33B vs E33A/C: quote verbatim the passage (instrument, article, ayat) that defines who qualifies for the first code as distinct from th… |
| VO-FUSED-T2-031 | E33C,E33A,E33B | QB15-11 | For E33C vs E33A/B: quote verbatim the passage (instrument, article, ayat) that defines who qualifies for the first code as distinct from th… |

### T3 — Activity boundary (permitted vs forbidden / work vs visit) (18)

| query_id | target products | provenance | text (truncated) |
|---|---|---|---|
| VO-FUSED-T3-001 | C1,D1,C2,D2 | VO-NB2-065 | Classify passive participation in conferences, fairs or MICE events without speaking, negotiating, selling or working; identify product, lim… |
| VO-FUSED-T3-002 | ALL relevant | VO-NB2-066 | Classify the role of speaker, panelist or demonstrator at an event, distinguishing foreign compensation, Indonesian compensation and no comp… |
| VO-FUSED-T3-003 | C2,D2,D1 | VO-NB2-067 | Classify meetings, discussion, negotiation and contract signing; separate passive presence, decision power and direct sale/delivery. |
| VO-FUSED-T3-004 | C2,D2,C12,D12 | VO-NB2-068 | Classify a visit to an office, factory or site as an observer without control, audit, installation or operational output; distinguish existi… |
| VO-FUSED-T3-005 | C17,D17,ALL | VO-NB2-069 | Classify audit, quality control, compliance inspection and technical due diligence on an already-operating activity; identify code and limit… |
| VO-FUSED-T3-006 | C20,ALL | VO-NB2-070 | Classify installation, repair or maintenance of machinery; separate hands-on work, remote assistance and mere observation. |
| VO-FUSED-T3-007 | ALL relevant | VO-NB2-071 | Classify commissioning, start-up and testing; identify who operates the machinery, who signs acceptance, and when the corpus mandates review… |
| VO-FUSED-T3-008 | ALL relevant | VO-NB2-072 | Classify short technical supervision without hands-on work; separate staff direction, consulting, audit and mere observation. |
| VO-FUSED-T3-009 | E23,E23U,E23V | VO-NB2-073 | Classify productive/operational work for an Indonesian party, distinguishing employer, client, deliverable and day-to-day control. |
| VO-FUSED-T3-010 | ALL relevant | VO-NB2-074 | Classify who delivers training, workshops or coaching in Indonesia; separate internal, public, free and paid training. |
| VO-FUSED-T3-011 | C9,C9A,C9B,E30 | VO-NB2-075 | Classify who receives training, short course or non-degree instruction; separate the C9/C9A/C9B external neighbors from formal E30* educatio… |
| VO-FUSED-T3-012 | ALL relevant | VO-NB2-076 | Classify artistic, musical or entertainment performance; separate participation, exhibition, compensation and commercial production. |
| VO-FUSED-T3-013 | ALL relevant | VO-NB2-077 | Classify filming, audiovisual production, creator work and commercial content; separate personal, commissioned and locally-remunerated activ… |
| VO-FUSED-T3-014 | ALL relevant | VO-NB2-078 | Classify journalism, reportage and newsgathering; identify authorizations and checks that cannot be self-declared. |
| VO-FUSED-T3-015 | ALL relevant | VO-NB2-079 | Classify professional/amateur sport, competition and coaching; separate compensation and contract. |
| VO-FUSED-T3-016 | ALL relevant | VO-NB2-080 | Classify volunteering, social, religious or humanitarian activity; separate absence of pay from existence of duties and organizational contr… |
| VO-FUSED-T3-017 | E33G,ALL relevant | VO-NB2-081 | Classify remote work from Indonesia for an employer or clients located exclusively abroad; separate income source, market served, physical p… |
| VO-FUSED-T3-018 | C2,D2,C12,D12,E33 | VO-NB2-082 | Classify property viewing, due diligence, purchase, development, management and leasing; identify when it is a visit, pre-investment or oper… |

### T4 — Thresholds & financial values (10)

| query_id | target products | provenance | text (truncated) |
|---|---|---|---|
| VO-FUSED-T4-001 | C,D | QB5-01 | Proof-of-funds for visit visas (C/D series): amount, currency, holding period, whose name, and which instrument sets it. |
| VO-FUSED-T4-002 | E28A | QB5-02,VO-NB2-117 | E28A: minimum investment value and minimum paid-up capital, per the newest source; distinguish company-level vs personal-share requirements. |
| VO-FUSED-T4-003 | E28B,E28C,E28D,E28F | QB5-03 | E28B/C/D/F: every monetary threshold the sources attach to these tiers, with pinpoints. |
| VO-FUSED-T4-004 | E33 | QB5-04,nb2q-b03-03 | E33: qualifying deposit amount and accepted alternatives (property value floor, in whose name, which banks qualify). |
| VO-FUSED-T4-005 | E33E | QB5-05 | E33E: pension/passive-income floor and/or deposit; age threshold. |
| VO-FUSED-T4-006 | E33G | QB5-06,nb2q-b03-01 | E33G: annual income floor, in what currency, evidenced how, over what look-back period. |
| VO-FUSED-T4-007 | E31 | QB5-07 | Family visas (E31*): sponsor income or deposit requirements, per sub-code where they differ. |
| VO-FUSED-T4-008 | E30 | QB5-08 | Study visas (E30*): financial guarantee requirements and who may provide them. |
| VO-FUSED-T4-009 | ALL | QB5-09,QB1-05 | PNBP fees per product family (visit, D-series by validity, KITAS, KITAP) and DKPTKA where applicable — current schedule with instrument + da… |
| VO-FUSED-T4-010 | E33,E33A,E33E | nb2q-b12-04 | Does any golden-visa class exist in the corpus, with which investment tiers and stay durations? |

### T5 — Entry & duration semantics (8)

| query_id | target products | provenance | text (truncated) |
|---|---|---|---|
| VO-FUSED-T5-001 | ALL | nb2q-b04-01,VO-NB2-084 | Which products are legally single-entry vs multiple-entry, and in which does a single exit permanently void the stay permit? |
| VO-FUSED-T5-002 | D1,D2,D12 | nb2q-b05-01,nb2q-b05-02,QB6-01,VO-NB2-085 | Is the D12 stay limit continuous per visit or cumulative across validity? Same question for D1 and D2. Cite exact wording and any operationa… |
| VO-FUSED-T5-003 | C | QB6-02,VO-NB2-086 | For C-series: exact extension mechanics — how many extensions, of what length, filed where, total resulting stay. |
| VO-FUSED-T5-004 | D12 | QB6-03,VO-NB2-088 | D12 specifically: per-entry 180 and extension to 360 total — quote Pasal 95(4) (or successor) and state whether the extension is per-entry o… |
| VO-FUSED-T5-005 | D | QB6-04,nb2q-b04-04 | Does exiting and re-entering reset the per-entry clock on multiple-entry visas? Any minimum time abroad? |
| VO-FUSED-T5-006 | C,D,E | QB6-05,nb2q-b08-03 | Which onshore conversions are legally permitted (C1→KITAS, D→KITAS, B1→none, etc.)? Give the conversion matrix with sources. |
| VO-FUSED-T5-007 | ALL | QB6-06 | Extension filing windows: earliest/latest day relative to expiry, and what happens to a pending application at expiry. |
| VO-FUSED-T5-008 | E30 | QB6-07,QB6-08 | For each E-series family, what is the grant-duration band and who decides within the band (VARIABLE_BY_GRANT cases E30/E30E/E30F)? Also: KIT… |

### T6 — Compensation: Indonesian-source vs foreign-source (5)

| query_id | target products | provenance | text (truncated) |
|---|---|---|---|
| VO-FUSED-T6-001 | ALL | nb2q-b06-01,VO-NB2-097 | What legal test determines whether compensation is 'from an Indonesian source' for immigration purposes: payer location, payment channel, or… |
| VO-FUSED-T6-002 | C2,D2,E28 | nb2q-b06-02,nb2q-b06-04 | Is per-diem or expense reimbursement by an Indonesian entity treated as compensation triggering a work-permit requirement? Which products ex… |
| VO-FUSED-T6-003 | B1,C1,D1 | nb2q-b06-03 | May a visitor receive foreign-source salary while physically in Indonesia on a non-work visa for short stays? Distinguish products. |
| VO-FUSED-T6-004 | D2,E28,E31 | nb2q-b06-05,nb2q-b06-06 | Are dividends, director fees or board compensation from an Indonesian PT allowed for visitor/KITAS holders (per product)? Does the corpus de… |
| VO-FUSED-T6-005 | E33G,D1 | VO-NB2-098 | Does the corpus address tax-residency interaction (183-day rule) for long-stay visitors/remote workers, or is that outside immigration scope… |

### T7 — Sponsor, guarantor, invitation (13)

| query_id | target products | provenance | text (truncated) |
|---|---|---|---|
| VO-FUSED-T7-001 | ALL | QB7-01,nb2q-b07-01 | After UU 63/2024: which products still require a guarantor (penjamin), which require only a sponsor, and which need neither? Cite the amende… |
| VO-FUSED-T7-002 | D2,C2 | QB7-02 | Who may sponsor a D2 business visit: Indonesian entity, foreign entity, individual? What must the invitation letter contain? |
| VO-FUSED-T7-003 | ALL | QB7-03,nb2q-b07-02 | Sponsor obligations and liabilities (reporting, departure guarantee, cost bearing) — per sponsor type. |
| VO-FUSED-T7-004 | E33,E33G | QB7-04 | Self-sponsorship: which E-codes allow the applicant to be their own sponsor (second home, remote, diaspora)? |
| VO-FUSED-T7-005 | BRIDGING | QB7-05 | BRIDGING: who is the sponsor of record and does it inherit from the prior permit? |
| VO-FUSED-T7-006 | E23 | QB7-06 | Corporate sponsor prerequisites for E23 (company documents, RPTKA status, sectoral limits). |
| VO-FUSED-T7-007 | E | QB7-07 | Change of sponsor mid-permit: possible for which permits, and what is the procedure? |
| VO-FUSED-T7-008 | A1,E33B | QB7-08,VO-NB2-092 | Government sponsorship (GOVERNMENT type in the catalog): which codes actually use it per the sources? Legally define sponsor/guarantor/invit… |
| VO-FUSED-T7-009 | ALL | VO-NB2-093 | For each of the 38 products, identify whether sponsor/guarantor/inviter is needed, who may be one, and which claim imposes it (full per-prod… |
| VO-FUSED-T7-010 | C2,D2,D12 | nb2q-b07-03 | Is an invitation letter sufficient where a sponsor is not mandatory? Which products accept invitation-only? |
| VO-FUSED-T7-011 | B1,C1,A1 | nb2q-b07-05 | Can a hotel, villa or tour operator act as sponsor for visitor products? Which ones? |
| VO-FUSED-T7-012 | D1,D2,D12 | VO-NB2-094 | Verify any sponsor exemption tied to nationality or channel for D1/D2/D12; do not infer from the portal alone (the Argentina benchmark appli… |
| VO-FUSED-T7-013 | E28C | nb2q-b07-04 | For E28C, what is the current correct sponsor requirement, and did the classification change sponsor semantics in any dated update? |

### T8 — Onshore/offshore, extension, conversion, KITAP (12)

| query_id | target products | provenance | text (truncated) |
|---|---|---|---|
| VO-FUSED-T8-001 | B1,C1,C2 | nb2q-b08-01 | Which products can be extended onshore, how many times, for how long each, and at what cost class? Table form. |
| VO-FUSED-T8-002 | ALL | nb2q-b08-06 | Are there blackout windows (e.g. pending application) during which the applicant must not exit Indonesia? |
| VO-FUSED-T8-003 | B1,C1 | nb2q-b08-07 | Which extensions require biometrics or in-person appearance, and which are fully online per eVisa guidance? |
| VO-FUSED-T8-004 | E28,E33,E31 | nb2q-b08-05 | What happens to a KITAS if the holder exits without a re-entry permit, and how is it restored? Is an Exit Permit Only (EPO) mandatory at per… |
| VO-FUSED-T8-005 | E | VO-NB2-099 | For stay permits generally, identify re-entry-permit, reporting or maintenance conditions that could invalidate the intended use of a multi-… |
| VO-FUSED-T8-006 | ALL | nb2q-b08-03 | Which onshore conversions are legally permitted (e.g. C1→KITAS, D→KITAS, B1→none)? Give the conversion matrix with sources. |
| VO-FUSED-T8-007 | ALL | nb2q-b08-02,VO-NB2-089,VO-NB2-090 | Which products must apply offshore only, and which allow onshore application (with what conditions)? Per product, separate application-locus… |
| VO-FUSED-T8-008 | E | QB17-01 | KITAS→KITAP: the 3-consecutive-years rule, excluded categories (students/researchers?), and the instrument. |
| VO-FUSED-T8-009 | E | QB17-02 | Which KITAS codes are KITAP-eligible and which never are? Table with citations. |
| VO-FUSED-T8-010 | E | QB17-03 | Onshore code-switch between E-codes (e.g. E30→E23, E31→E23): permitted pairs and procedure. |
| VO-FUSED-T8-011 | KITAP | QB17-04 | KITAP: duration, renewal, re-entry mechanics post-MERP, and loss conditions. |
| VO-FUSED-T8-012 | C,D,E | QB17-05 | Which visit codes (C/D) can ever lead onshore to E-status without leaving Indonesia? Complete allowed list. |

### T9 — Nationality, calling visa, dual citizenship (6)

| query_id | target products | provenance | text (truncated) |
|---|---|---|---|
| VO-FUSED-T9-001 | ALL | nb2q-b09-01,nb2q-b09-02,QB8-01,QB0-05 | Which nationalities are currently on the Calling Visa list, under which instrument, with what effective date, and which products does it res… |
| VO-FUSED-T9-002 | A1,B1 | QB8-02,QB0-06 | Argentina: eligible for BVK? VOA? e-VOA? Any product-level restriction, per the newest source? |
| VO-FUSED-T9-003 | ALL | QB8-03 | Which products are closed to specific nationalities beyond the calling-visa list, if any? |
| VO-FUSED-T9-004 | ALL | nb2q-b09-03,QB8-04 | How should dual nationals be evaluated when one nationality is calling-visa-listed and the other is not? Which passport governs eligibility,… |
| VO-FUSED-T9-005 | ALL | nb2q-b09-04,nb2q-b09-05 | Are there nationality-specific restrictions beyond calling visa (e.g. Israel passport recognition, Taiwan documents)? Do any products grant … |
| VO-FUSED-T9-006 | ALL | nb2q-b09-06,QB8-05,QB8-06 | How are stateless persons or travel-document (non-passport) holders treated per product? Do the sources impose reciprocity/bilateral-agreeme… |

### T10 — Age, minors, family, marriage, dependents (10)

| query_id | target products | provenance | text (truncated) |
|---|---|---|---|
| VO-FUSED-T10-001 | E31 | QB9-01,nb2q-b10-03 | Spouse of an Indonesian citizen: which code, what marriage evidence (buku nikah / CNI / foreign certificate + legalization), does an unregis… |
| VO-FUSED-T10-002 | E31 | QB9-02,nb2q-b10-02 | Children of an Indonesian citizen (minor and adult): which codes and age cutoffs? Map each E31 subclass to its exact family relationship wit… |
| VO-FUSED-T10-003 | E31,E23 | QB9-03,VO-NB2-107,VO-NB2-108 | Dependents of a KITAS worker (spouse, children): which E31 codes attach, may the dependent spouse work? Which facts decide E31 routing when … |
| VO-FUSED-T10-004 | E31 | QB9-04 | Where must a mixed marriage be registered for immigration purposes, and what is the effect of non-registration? |
| VO-FUSED-T10-005 | ALL | QB9-05,nb2q-b10-01 | Minors travelling alone or with one parent: consent/guardianship documents required at entry and for stay permits. What are the rules for un… |
| VO-FUSED-T10-006 | E31 | QB9-06 | Adoption and step-children: do they qualify as 'children' for family codes? Evidence required. |
| VO-FUSED-T10-007 | E31 | QB9-07 | Parents of an Indonesian citizen or of a KITAS holder: any code covering ascendants? |
| VO-FUSED-T10-008 | E31 | QB9-08 | Death or divorce of the sponsor spouse: effect on the dependent's permit and lawful transitions. |
| VO-FUSED-T10-009 | ALL | nb2q-b10-04,VO-NB2-104 | Which products have explicit minimum/maximum ages, and for every age-threshold, what is the operator, reference date, inclusivity of the thr… |
| VO-FUSED-T10-010 | E31 | nb2q-b10-05 | Can dependents work or study on dependent permits, or must they convert? Cite per subclass. |

### T11 — Work specifics (RPTKA/DKPTKA, secondment, employer change) (8)

| query_id | target products | provenance | text (truncated) |
|---|---|---|---|
| VO-FUSED-T11-001 | E23 | QB10-01 | RPTKA: who files, for what validity, which roles are exempt? Current instrument. |
| VO-FUSED-T11-002 | E23 | QB10-02 | DKPTKA: amount, who pays, exemptions (government projects, specific sectors). |
| VO-FUSED-T11-003 | E28A,D2 | QB10-03 | Directors/commissioners not resident in Indonesia: which visa for board meetings, and when does board work require E28A/E23? |
| VO-FUSED-T11-004 | E23 | QB10-04 | Changing employer on E23: new visa or amendment? Cooling-off constraints? |
| VO-FUSED-T11-005 | E23,C2,D2 | QB10-05 | Secondment of a foreign employee to an Indonesian affiliate: E23 or a visit code? What separates them? |
| VO-FUSED-T11-006 | E23 | QB10-06 | Part-time or multiple concurrent employers: permitted under E23? |
| VO-FUSED-T11-007 | E30,E23,C18 | QB10-07 | Internships: paid vs unpaid — study code, work code, or prohibited? |
| VO-FUSED-T11-008 | E23 | QB10-01 | For E23, is the RPTKA-approved job title/position binding on the actual role performed (job-title/position mismatch)? What happens if the ho… |

### T12 — Study, exchange, KEK, izin belajar (5)

| query_id | target products | provenance | text (truncated) |
|---|---|---|---|
| VO-FUSED-T12-001 | E30 | QB11-01 | Izin belajar: which authority issues it, for which institution types, is it a precondition of the study visa? |
| VO-FUSED-T12-002 | E30E | QB11-02,VO-NB2-113 | KEK (special economic zone) educational institutions: definition and register — what qualifies a school as KEK for E30E, and how is KEK stat… |
| VO-FUSED-T12-003 | E30F | QB11-03,VO-NB2-114 | 'Exchange program' for E30F: quote the definition and the evidence required (agreement between institutions, sending/host, MoU)? |
| VO-FUSED-T12-004 | C22,C22A,C22B,E30F,E23 | VO-NB2-112 | Structured internship/apprenticeship/traineeship (C22/C22A/C22B external neighbors) vs exchange (E30F) vs productive work (E23*): separate s… |
| VO-FUSED-T12-005 | B1,C1,E30 | nb2q-b13-02 | May a visitor attend short courses, workshops or language school on C1/B1? Where is the line versus formal E30 study? |

### T13 — Remote work, clients, tax-residency interplay (E33G) (6)

| query_id | target products | provenance | text (truncated) |
|---|---|---|---|
| VO-FUSED-T13-001 | E33G | nb2q-b14-01,nb2q-b14-04,QB12-01 | For E33G, define precisely: employer abroad, no Indonesian clients, no Indonesian-source income — which of these are explicit legal conditio… |
| VO-FUSED-T13-002 | E33G | nb2q-b02-05,QB12-02 | May an E33G remote worker serve Indonesian clients or invoice an Indonesian entity at all, even minor? Where is the line? |
| VO-FUSED-T13-003 | E33G,E31 | QB12-04 | Family members of an E33G holder: which codes attach and with what rights? |
| VO-FUSED-T13-004 | E33G,E23 | QB12-05 | Freelancer with mixed foreign+Indonesian income: which lawful configurations exist (E33G vs E23 vs none)? |
| VO-FUSED-T13-005 | E33G | nb2q-b14-03 | Is 'digital nomad' activity on B1/C1 addressed anywhere in the sources, explicitly or by enforcement guidance? |
| VO-FUSED-T13-006 | E33G | VO-NB2-081 | For E33G, does the requirement that the employer be located abroad mean the employer entity itself must not be an Indonesian legal entity (e… |

### T14 — Retirement & second home specifics (E33/E33E/E33F) (6)

| query_id | target products | provenance | text (truncated) |
|---|---|---|---|
| VO-FUSED-T14-001 | E33E | QB13-01 | E33E: age floor, income/deposit floor, and mandatory use of an agent/penjamin — quoted, dated. |
| VO-FUSED-T14-002 | E33 | QB13-02 | E33: the deposit — exact amount, state-owned bank requirement, own-name requirement, lock-in duration, and the property alternative's floor. |
| VO-FUSED-T14-003 | E33,E33E | QB13-03 | May E33/E33E holders work or own/manage a business? Quote the prohibition or permission. |
| VO-FUSED-T14-004 | E33,E33E | QB13-04 | E33/E33E → KITAP: is there a conversion path and after how long? |
| VO-FUSED-T14-005 | E33,E33E,E31 | QB13-05 | Family riders on E33/E33E (spouse, children): codes and conditions. |
| VO-FUSED-T14-006 | E33,E33E | QB13-06 | Health-insurance requirements for retirement/second-home permits: which sources impose them and with what minimums? |

### T15 — Risk: overstay, refusals, blacklist, criminal record (8)

| query_id | target products | provenance | text (truncated) |
|---|---|---|---|
| VO-FUSED-T15-001 | ALL | QB14-01,nb2q-b15-01,VO-NB2-119 | Overstay: current fine per day, threshold beyond which deportation is mandatory, discretionary bands, exact day-count boundaries. Cite the n… |
| VO-FUSED-T15-002 | ALL | QB14-02,nb2q-b15-02 | Blacklist (cekal/penangkalan): standard durations, the authority imposing them, and the removal procedure and cost. |
| VO-FUSED-T15-003 | ALL | nb2q-b15-03,nb2q-b15-04 | How does an applicant exit the blacklist (rehabilitation process, waiting periods)? Are voluntary surrender and paid overstay fines treated … |
| VO-FUSED-T15-004 | ALL | QB14-03,VO-NB2-120 | Effect of a prior visa refusal or entry refusal on later applications: what do sources say about disclosure and consequences? |
| VO-FUSED-T15-005 | E28,E33 | nb2q-b15-05,QB14-04 | Which criminal-record facts must be disclosed per product, and which products require a police clearance certificate? |
| VO-FUSED-T15-006 | ALL | QB14-05 | Deportation: consequent re-entry ban lengths and whether they differ by ground (overstay vs work violation vs security). |
| VO-FUSED-T15-007 | C,D | QB14-06 | Work-violation sanctions for visitors caught working: sanction on the person and the sponsor. |
| VO-FUSED-T15-008 | ALL | VO-NB2-125 | Define the boundary between error, inconsistent information, false document and misrepresentation; assign reason codes without inferring int… |

### T16 — Documents: non-auto-verifiable, legalization, evidence (10)

| query_id | target products | provenance | text (truncated) |
|---|---|---|---|
| VO-FUSED-T16-001 | ALL | nb2q-b16-01,nb2q-b16-04 | List all mandatory documents per product that cannot be verified without human review (bank statements, invitation letters, employment contr… |
| VO-FUSED-T16-002 | ALL | nb2q-b03-05,VO-NB2-091 | Map the minimum passport validity required at grant and at extension per product, and identify exceptions, travel documents and document che… |
| VO-FUSED-T16-003 | E31 | nb2q-b07-06,VO-NB2-109 | What documents prove a family sponsor/guardian relationship for E31 subclasses (and E30 guardian/consent cases), and which require legalizat… |
| VO-FUSED-T16-004 | E33B | VO-NB2-115 | For E33B, verify the alternatives for qualifying expertise, any ranking/recency/GPA requirement, the evidence and window of the cooperation,… |
| VO-FUSED-T16-005 | E33,E33E | QB13-06,QB15-06,nb2q-b15-05,VO-NB2-123 | For which products are police clearances, medical certificates or health-insurance proofs mandatory, and what validity windows apply? |
| VO-FUSED-T16-006 | ALL | VO-NB2-124 | When does a damaged passport, insufficient pages or identity inconsistencies block the case or trigger review? |
| VO-FUSED-T16-007 | ALL | VO-NB2-126 | For each document class, which properties can be verified automatically and which require human authenticity check or issuer lookup? |
| VO-FUSED-T16-008 | E28,E31,E33 | nb2q-b16-02,VO-NB2-127 | Which documents require apostille/legalization vs plain copies, per product and document type? |
| VO-FUSED-T16-009 | D12,E28,E33 | VO-NB2-130 | Verify business plan, letter of intent, company deed, NIB and other investment-related documents; indicate what each proves. |
| VO-FUSED-T16-010 | E23,E23U,E23V | VO-NB2-131 | Verify the RPTKA/notification/work-authorization document chain for E23/E23U/E23V and which facts are not auto-verifiable. |

### T17 — No-path cases & legal alternatives (8)

| query_id | target products | provenance | text (truncated) |
|---|---|---|---|
| VO-FUSED-T17-001 | ALL | QB16-01 | A tourist who wants to take up local employment: is there any lawful in-country path, or must they leave and re-enter on E23? Cite. |
| VO-FUSED-T17-002 | E33G | QB16-02,nb2q-b18-01 | A remote worker whose clients are partly Indonesian: which configurations have no lawful visa today, and what is the nearest lawful alternat… |
| VO-FUSED-T17-003 | E28 | QB16-03 | An investor below every E28 threshold: lawful alternatives (D12 cycles? C2?) and their limits. |
| VO-FUSED-T17-004 | E33E | QB16-04 | A retiree below the E33E age floor: lawful alternatives and trade-offs. |
| VO-FUSED-T17-005 | ALL | QB16-05 | A person with an active overstay inside Indonesia: what lawful exits/regularizations exist (pay-and-leave, BRIDGING, none)? |
| VO-FUSED-T17-006 | ALL | QB16-06 | A person previously deported: when, if ever, can they lawfully return, and by what procedure? |
| VO-FUSED-T17-007 | C2,E28 | nb2q-b18-02 | For someone wanting hands-on work short-term (under 30 days) for an Indonesian company: is there any lawful visitor path, or is a work permi… |
| VO-FUSED-T17-008 | ALL | nb2q-b18-03 | For calling-visa nationalities: which products remain theoretically available under the calling-visa procedure, and what does the procedure … |

### T18 — Edge cases, multi-purpose, benchmark variants (9)

| query_id | target products | provenance | text (truncated) |
|---|---|---|---|
| VO-FUSED-T18-001 | D1,D2,D12 | VO-NB2-137 | Evaluate the Argentina benchmark with meeting/negotiation, multiple entry and 90 days cumulative across multiple trips; return decisive fact… |
| VO-FUSED-T18-002 | D1,D2,D12 | VO-NB2-138 | Change only the benchmark: the 90 days are continuous within a single entry; show the expected change without altering other facts. |
| VO-FUSED-T18-003 | D2,D12 | VO-NB2-139 | Change only the benchmark: on-site the user observes without auditing, installing or directing; show the expected change. |
| VO-FUSED-T18-004 | D2,D12 | VO-NB2-140 | Change only the benchmark: a documented business-startup project and feasibility study exist; show the expected change. |
| VO-FUSED-T18-005 | D2,D12 | VO-NB2-141 | Change only the benchmark: the user performs audit and quality control of an already-operating activity; identify product or gap and why D2/… |
| VO-FUSED-T18-006 | D2,D12 | VO-NB2-142 | Change only the benchmark: the user installs or repairs machinery; identify product or gap and the boundary with work. |
| VO-FUSED-T18-007 | D2,E23 | VO-NB2-143 | Change only the benchmark: a meeting plus one day of hands-on productive work; prove the mixed purpose is not collapsed to the more convenie… |
| VO-FUSED-T18-008 | C1,C2,D1,D2 | nb2q-b19-01 | When an applicant has two genuine purposes (e.g. tourism + business meetings on one trip), which product governs and is dual-purpose lawful … |
| VO-FUSED-T18-009 | E31,E33G | nb2q-b19-02 | May a KITAS holder's spouse (E31) separately hold a remote-work arrangement for a foreign employer? Which facts decide? |

### T20 — Gold personas / QA / compiler-local tests (NOT NB-2-facing) (12)

| query_id | target products | provenance | text (truncated) |
|---|---|---|---|
| VO-FUSED-T20-001 | N/A-LOCAL | VO-NB2-006 | Execute the local deterministic citation audit on response records 003/004/005 and the source snapshot: verify UUID, title, date, pinpoint, … |
| VO-FUSED-T20-002 | N/A-LOCAL | VO-NB2-144 | Create a remote-worker persona with foreign-only clients/compensation, long stay, no Indonesian client; identify facts, products and a separ… |
| VO-FUSED-T20-003 | N/A-LOCAL | VO-NB2-145 | Create a minor-student persona enrolled in school, with and without an eligible guardian; return two variants differing by exactly one fact,… |
| VO-FUSED-T20-004 | N/A-LOCAL | VO-NB2-146 | Create an E31* spouse/dependent persona and vary only the principal's status among E23/E28/E33 where source-grounded; show which dependent c… |
| VO-FUSED-T20-005 | N/A-LOCAL | VO-NB2-147 | Create personas at one unit below, exactly at, and one unit above every relevant investment threshold; specify currency and valuation date. |
| VO-FUSED-T20-006 | N/A-LOCAL | VO-NB2-148 | Create twin personas identical except nationality, one calling-visa-listed and one not; demonstrate the effect without real client data. |
| VO-FUSED-T20-007 | N/A-LOCAL | VO-NB2-149 | Create overstay personas at threshold-minus-one, exact threshold, threshold-plus-one; return expected outcome and review reason code. |
| VO-FUSED-T20-008 | N/A-LOCAL | VO-NB2-150 | Evaluate an otherwise-complete candidate who does not know whether they have the required sponsor; show why the outcome is NEEDS_INPUT/docum… |
| VO-FUSED-T20-009 | N/A-LOCAL | VO-NB2-151 | Evaluate a candidate who declares a necessary document but has not yet had it verified; separate legal plausibility, verification-pending an… |
| VO-FUSED-T20-010 | N/A-LOCAL | VO-NB2-152 | Construct a case where all 38 products are excluded by verified facts; explain the no-path outcome and only lawful alternatives requiring a … |
| VO-FUSED-T20-011 | N/A-LOCAL | VO-NB2-153 | Construct a multi-purpose case where two paths remain plausible; identify the minimum fact cut and prevent commercial ranking from choosing … |
| VO-FUSED-T20-012 | N/A-LOCAL | VO-NB2-154 | On the benchmark, change exactly one fact, record pruning, then restore it; specify expected candidates and decision trace before/during/aft… |

## Adversarial review

Cross-family review dispatched to Kimi K3 (`kimi-code/k3`), 2026-08-17. Findings and dispositions: see
`dedup-log.md` §Kimi refuter disposition. Summary: 4 mega-compound rows (originally in T7/T8) flagged as
carrying multiple legally-disjoint claims in one query were split into 7 atomic rows (T7 grew 9→13, T8
grew 9→12 net of the split plus 2 genuinely net-new facets Kimi surfaced — Exit Permit Only under T8 and
RPTKA job-title/position binding under T11). Two of Kimi's flagged "risky comparatives" (T2-048, T2-061)
were verified to be output-C's own native single-source comparative queries (not artifacts of this
task's fusion) — kept as-is with a caveat noted for E2b execution time. Three of Kimi's flagged
"coverage gaps" (dependent-cascade-on-principal-loss, overstay/sanctions, bridging-eligibility) were
verified already covered by topics not shown in Kimi's extract (T10-8, T15 overstay-ladder, T1 BRIDGING
doctrine card) — false alarms from a partial-context review, logged as such, not acted on.
