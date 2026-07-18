# Batch A — calibration registry v2 (plan §8 A-6(c) successor artifact)

- **Batch:** A
- **Artifact version:** v2
- **Date:** 2026-07-18
- **Plan:** `research/operations/2026-07-18-kbli-batch-a-plan.md`

> **Predecessor:** data/kbli-filiera/batch-reports/batchA-calibration.json (v1) — SIGNED, NEVER rewritten (scar W88/#9). This v2 file is the successor artifact mandated by plan §8 A-6(c); it does not edit or supersede v1's historical record, only the registry going forward.

> **Precondition:** plan §8 A-6(c) — this re-emission is a precondition for ANY Lot 2+ work; Zero's GO for the remainder is only actionable AFTER this registry re-emission is merged.

## Pinned revisions

| Artifact | Pin |
| --- | --- |
| canonical (`data/source_documents/KBLI_2025_FINAL_CLEAN.json`) | git revision `082fa917ba91fedec9dc5cf79fd9943ed9832032` |
| vault manifest (`data/kbli-filiera/manifest/vault-manifest-batch0-2026-07-18.json`) | sha256 `e7d25a377b717ed76efd1c7c806fe74b45067321629c5ed77655aeea9375db9d` |
| membership (`data/kbli-filiera/membership/batch-a-members.json`) | sha256 `2451a78abaf58875a535266cab2fe7da04bf53becc59f8961521fd9fe7c5c823` |

## Control limits m1-m5 (v2 — registry closure per plan §8 A-6(c))

| # | Metric | Limit | Lot-1 reading | State | On breach |
| --- | --- | --- | --- | --- | --- |
| m1 | cross-family extractor-vs-extractor IAA (lane D1 vs blind cross-family extractor with vision) | floor 0.75 | 0.385 | declared-breach | lane pauses at lot boundary, conductor-signed resume note in plan §8 |
| m2 | certification rate per lot | floor 0.20 / ceiling 0.85 | 0.000 | declared-breach | lane pauses (ceiling breach = drift suspicion), conductor-signed resume note |
| m3 | refutation-category registry (closed list) v2 | closed list: `code_collision`, `illegitimate_inheritance`, `wrong_authority_level`, `source_absent_in_vault`, `payload_cross_contamination`, `unresolvable_source_pointer`, `mapping_metadata_false` | n/a | pause (2 new categories) | any category outside the registry = automatic lot pause + conductor triage |
| m4 | tokens/dossier ceiling | ceiling 400000 | n/a (invariant from v1) | ✅ | lane pauses, investigate runaway |
| m5 | gold-set hit rate | 1.00 | NEG 7/8 (halt lifted) | resolved | any miss halts the lot immediately |

m1 note: same-family D1-vs-D5 agreement is NOT an m1 reading (measures transcription fidelity, not truth — scar W100)

m2 rule: per-lot explicit conductor adjudication required; no auto-resume; no floor re-registration (the advisory-floor-0.0 proposal was withdrawn, plan A-4)

m5 NEG-miss ruling (going forward): a NEG miss raising an evidenced completion path is adjudicated per-ancestor image-grade by the conductor: certified -> scheduled data-plane restore + halt lifts (precedent: 49213, plan A-6(b)-RESOLVED); refuted -> halt stands. An in-gate fill is never permitted.

## m3 category rename

`phantom_source_pointer` renamed to `unresolvable_source_pointer` — text-hunt evidence cannot establish nonexistence (plan A-5 terminology note).

## Gold sets v2 (digest-pinned, blind to lanes, new salts)

### NEGATIVE controls (21)

Eligibility: the 21 codes cured as of Lot 1 close: the 8 phase-1 cured codes + the 13 Lot-1 quarantined codes. Digest formula: `sha256(code + "|" + manifest_digest + "|v2")`, sorted:

- `014e8234d907092f034845c2655aa14f5207adbe14f0f756f8173b2a7eede9b2`
- `02604874cd368ec71bd9976078dc11a86932c2c42785a882804e90cee704be19`
- `11f90098169ef334d0de7956d785b328460366ca945a665f2c5ccf278cc871e4`
- `16e477e40123d1cbd418bdba99d75cc2997f196161bd43cd058eee38c6d3e107`
- `18e4a0aa906d384df091ad28ea18f52b0ad5c9e2bc9597b4bbddbddf565756e6`
- `2c05a7ac29586eee7ba315d466b2381c842db9c83eb87442590c031374a15da7`
- `2f534676debc26c64d69ca856561c6b9f0188f357db06f3287918f12bdfb32d4`
- `4c49108820caa50757775df33f6d342bf52bbbdcd8bdd27eb6e595a898e89a68`
- `52bb01e9994e9d74b086239f051dcbb662527c8e34211c2594e0db2e1190e82d`
- `6866596615004278c691f33a9cd4c94f2d4dca0ed1515b513396111f881d56b2`
- `6aaf4293c79fe427982342c68b1e09c1f40ed561e44bb5acb591a8162675d9f8`
- `6ae6d1ae70038c869f025f4b3262e1e236df31a467b79522deba2783224051cb`
- `795c3077643a5081be6762a1291198dd3365ac4457e247c595f3e8625fbee442`
- `89807c4b0c4646ec422392a3ac02e1549ae52700dea527391cf2f9161bb1aba7`
- `8f669f6061bce1f254f4f0ef7cb0aa644a80f53ea2fddecf4622e365bad082ce`
- `9238a3a0511d5d04c18056ce44adf6a1fff7dfdd3c9dc0b58a2b8b70c24c2c91`
- `94ce3b8f0495d807b09a85f70606c84082e8e8064f0b9aca2af70a10f89ee3fa`
- `980baead70e99a7ea95d5c7b6e8d01bd84b84459fc4ffbe6187de947fd016d5a`
- `a83f67443e177d37643927749b6cc62969d811cc288175cde7f276d08bf5388c`
- `e43a40a3fb6689e38f46ae12173f31a5be1085786e79cd3df057f5666b00c27a`
- `e85e8f4947145a810af15d537e68b8e48b48589df9519bff71b88a00e77a5f49`

### POSITIVE controls (8 of 1329 eligible after excluding the 8 Lot-1 revealed controls; 1337 eligible before exclusion)

Eligibility predicate: canonical record has kode_kbli_2025 set AND _l2_source is non-null AND per_skala is non-empty (the OSS-native Batch-C class).

Selection rule: among eligible codes EXCLUDING the 8 Lot-1 revealed positive controls (burned), the 8 with the lowest sha256(code + "|" + manifest_digest + "|v2-lot2") hex digest, sorted ascending — deterministic, never conductor-picked.

Digest formula: `sha256(code + "|" + manifest_digest + "|v2-lot2")`.

- `001344b3ea23e1789a7e563f5ca729d6cf5326291ddc99fc53df280253c57cdf`
- `008369fbc6c1938b6094d0fc9a0ec7daa85fc5f6189b22b453b8d4909a3991f0`
- `00905867be046951777331d287939ea949229d7dedae0687eeaa1580802ce7c8`
- `0123ea9b7da7dccdb1a0285ddb90052795f580ac217b3792881bf824e943de61`
- `016a1ffec19e4f14a86c96b831a96a2168f7d3727fad371ab7c9ec74dc505857`
- `01aab9cfca9e16b8e143c05be50477e81b1ecdd33e5dee340a4d58f22b0e43e4`
- `01afe5668822c686679de3f1f641374065ae430f15ed67442f79b96e1d2fe329`
- `01ebefaa9ecec8bd59f75305c7c1d2ad393db37108ed12d67325ec4f73aea33e`

**Reveal rule:** Plaintext code lists for both control classes are revealed in the lot report AFTER the lot closes (plan §5). Never before.

## Lot 1 outcome (pinned literal, reference)

- Quarantined: 13 · Certified: 0
- m1: 0.385 — declared-breach
- m2: 0.000 — declared-breach
- m3: pause (2 new categories)
- m5 NEG hit rate: 7/8 — halt lifted per A-6(b)-RESOLVED
- References: `research/operations/2026-07-18-kbli-batch-a-lot1-conductor-gate.md` — PR #2721 (docs) + PR #2725 (data apply)

## Pause/resume protocol

Any control-limit breach (m1-m5) pauses the affected lane at the lot boundary. Resume requires a conductor-signed note appended to research/operations/2026-07-18-kbli-batch-a-plan.md §8, citing the specific breached metric and the root cause. No silent resume.

## Sign-off

Conductor sign-off: SIGNED — Fable conductor session (MANDATO S2, post-GO), 2026-07-18
