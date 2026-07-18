# Batch A — calibration artifact (plan §5 gate)

- **Batch:** A
- **Date:** 2026-07-18
- **Plan:** `research/operations/2026-07-18-kbli-batch-a-plan.md`

> No lot starts before this artifact exists (plan §5). It is compiler-emitted from pilot A1 measurements and conductor-signed below; changing a control limit mid-batch requires a logged amendment in the plan's §8, never a silent edit here.

## Pinned revisions

| Artifact | Pin |
| --- | --- |
| canonical (`data/source_documents/KBLI_2025_FINAL_CLEAN.json`) | git revision `954432cdfa278cb5bc84409753a61c93772eb7ac` |
| vault manifest (`data/kbli-filiera/manifest/vault-manifest-batch0-2026-07-18.json`) | sha256 `e7d25a377b717ed76efd1c7c806fe74b45067321629c5ed77655aeea9375db9d` |
| membership (`data/kbli-filiera/membership/batch-a-members.json`) | sha256 `aa0a0a6980117d57321e625fdad4e1a89f19f5b34125614d8d9921fb50f60497` |

## Pilot A1 measurements (conductor-set baseline)

Source: `research/operations/2026-07-17-kbli-pilot-a1-results.md`. Pinned literal, not re-derived by this compiler.

| Metric | Value |
| --- | --- |
| codes / seats | 15 / 29 |
| total Sonnet tokens | 3375127 |
| avg tokens/code | 225008 |
| max tokens/code | 357453 (code 43216) |
| adjudicated | 12 |
| certified-clean | 5 |
| quarantined | 7 |
| innocence untouched | 3 |
| D1/D5 dossier concordance | 11/12 |

## Control limits m1-m5 (falsifiable, pre-registered)

| # | Metric | Limit | Pilot baseline | On breach |
| --- | --- | --- | --- | --- |
| m1 | extractor/refuter blind-concordance floor per lot | floor 0.45 | 0.917 | lane pauses at lot boundary, conductor-signed resume note in plan §8 |
| m2 | certification rate per lot | floor 0.05 / ceiling 0.60 | 0.417 | lane pauses (ceiling breach = drift suspicion), conductor-signed resume note |
| m3 | refutation-category registry (closed list) | closed list: `code_collision`, `illegitimate_inheritance`, `wrong_authority_level`, `phantom_source_pointer`, `source_absent_in_vault` | n/a | any category outside the registry = automatic lot pause + conductor triage |
| m4 | tokens/dossier ceiling | ceiling 400000 | avg 225008 / max 357453 | lane pauses, investigate runaway |
| m5 | gold-set hit rate | 1.00 | n/a | any miss halts the lot immediately |

m1 definition: per-lot fraction of adjudicated dossiers where the D5 blind verdict matches the D1 proposal. m2 definition: certified_clean / adjudicated, per lot — a too-high rate is drift, not excellence.

## Recalibration history — m1/m2 (plan §8 A-3)

The m1/m2 limits in the table above are the CURRENT ones (post-A-3, in force for remaining A-serving lots). The original pilot-derived values are kept here — recalibration is auditable history, never a silent overwrite.

| Metric | Original (pilot-derived) | Current (A-3) | Amendment | Reason |
| --- | --- | --- | --- | --- |
| m1 floor | 0.75 | 0.45 | plan §8 amendment A-3 (2026-07-18) | floors re-derived from the first true-blind lot; original pilot baseline was anchored |
| m2 floor / ceiling | 0.20 / 0.85 | 0.05 / 0.60 | plan §8 amendment A-3 (2026-07-18) | floors re-derived from the first true-blind lot; original pilot baseline was anchored |

Scope: remaining A-serving lots only. m3/m4/m5 are unchanged by this amendment.

## Gold sets (digest-pinned, blind to lanes)

### NEGATIVE controls (8)

Eligibility: the 8 cured codes from the pilot/audit runs (honest-gap must survive). sha256(code + "|" + manifest_digest), sorted:

- `0be62853bc799751a2c1fdf3d35f2b4ca6f42f87bdfdd04c182ab64c07563160`
- `148e8314ff7d55fe6acef963d0e51b4d83b92bd44e568da405c45452dcbca6bb`
- `34ad28116dea958b6481af2155ebd20cbbd7ef807178a7fee49b45e48f5a5402`
- `40bb04a7514c53133acf4d979def4d8d667accb5ea9c1f12f9853364c4148e5b`
- `5fbb35d093c960a1cfe9166d1419a1e3853eec0a82d3fd4dd880bc817729dd97`
- `cce4f93a7687b6c201c046fc55af2fe9659db7857b84cb33e839681b0ec3293f`
- `d279d2b5cf9396272bced8d09a19aa3005150155240433a32a6751b89973ce92`
- `fb5df44ffe81b6af8ac36fb6a666243f815c84e8a02c8d0de223223e77aa4a1e`

### POSITIVE controls (8 of 1336 eligible)

Eligibility predicate: canonical record has kode_kbli_2025 set AND _l2_source is non-null AND per_skala is non-empty (the OSS-native Batch-C class).

Selection rule: among eligible codes, the 8 with the lowest sha256(code + "|" + manifest_digest) hex digest, sorted ascending — deterministic, never conductor-picked.

- `002b2f50370eeb36d78030d3a0137997571b9535954f34c595f032d7d5abcd0b`
- `0090e8cc839d35a849b789fcd4c15816c0c72de46a5a02191abca0f938b6fb24`
- `00bcc0ba8e78902530873e111ffa57b7f86685acbbe26bddad1d43cf36bfd5fd`
- `00c324c333f44f347349f475b9f084f55dd1a7249acf6495f468becaafc5b6d1`
- `00c4757efbe09c7b0f764078d7732b47b557f9ad204fd70cd46fd86d5b5f3c8a`
- `00f964023ee65e7bb184d770624485b8eec6057e78624ef5d6bd187e5ddfa048`
- `011b8eecc4a165dd230b1e25d8fb1e898e9e75a2c55b02889b9f4c813c18204b`
- `0181b72ccb224bd7d53017f67be1e7c9ba6d3e8efbef3524c0a6d4f3f37335df`

**Reveal rule:** Plaintext code lists for both control classes are revealed in the lot report AFTER the lot closes (plan §5). Never before.

## Mutation testing

Per plan §5 (workflow §5 binding): the conductor periodically injects corrupted intermediates (a wrong code string in a render locator, an altered row value) into the pipeline. The refuter/compiler MUST catch every injection. An uncaught mutation is a program-level defect: the lot halts and a root-cause pass runs before any resume.

## Pause/resume protocol

Any control-limit breach (m1-m5) pauses the affected lane at the lot boundary. Resume requires a conductor-signed note appended to research/operations/2026-07-18-kbli-batch-a-plan.md §8, citing the specific breached metric and the root cause. No silent resume.

## Sign-off

Conductor sign-off: SIGNED — Fable conductor session f5892d39, 2026-07-18
