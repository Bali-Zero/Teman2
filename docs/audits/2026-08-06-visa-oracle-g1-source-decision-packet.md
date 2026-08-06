# Visa Oracle V2 - G1 source decision packet

**Status:** `SIGNED / ACTIVATION BLOCKED` - national authority and country
treatment are approved and production sequence 2 is signed; immutable
instrument archive and activation remain pending; independent review is LGTM

**Observed:** 2026-08-06 11:52-12:01 WITA (2026-08-06 03:52-04:01 UTC)

**Candidate base:** `7452e05cc9d8a6a6090052b958b1d05275613a80`

**Product consequence:** the recorded national-authority decision and signed
sequence-2 candidate resolve the product country set. Missing immutable
instruments and expired or unverified evidence remain fail-closed. This packet
does not close G1 or authorize activation.

## Executive decision record

### Zero product decision (recorded 2026-08-06)

The national Ditjen Imigrasi list is the canonical country-set authority for
Visa Oracle. Regional displays cannot add or retain a country that is absent
from the national list. Therefore the replacement national Calling Visa
overlay shall contain only `AF IL KP LR NG SO`; `GN` (Guinea), `CM` (Cameroon),
and `NE` (Niger) are excluded. This is a product authority decision for the
new signed RulePack, not a mutation of `rulepack-prod-001` and not a claim that
the missing Kepmen PDFs have been archived.

Until sequence 2 is activated, the current sequence-1 pack remains
immutable and runtime freshness gates continue to abstain conservatively.

Two official web surfaces and the signed production pack do not expose the same Calling Visa country set:

| Surface                                         | Country codes, in displayed order | Count | Stable normalized-list SHA-256                                     |
| ----------------------------------------------- | --------------------------------- | ----: | ------------------------------------------------------------------ |
| Ditjen Imigrasi national list                   | `AF IL KP LR NG SO`               |     6 | `cfc36c1b65af69564e9a56b69c3b680288ece3d17350b6b46e9b396b3888f305` |
| Kanwil Ditjen Imigrasi Sulawesi Tenggara        | `AF GN IL CM LR NE NG KP SO`      |     9 | `be2967172527eb91c6be09ec4e03505b6b9cc08e3661062cebb57abea815d925` |
| Signed RulePack `rulepack-prod-001`, sequence 1 | `AF GN IL CM KP LR NG SO`         |     8 | `c39239e0b7c620eb497dcfb71d5601153aa5754003994066c5772d19c19fb402` |

The normalized hash input is UTF-8 text consisting respectively of the exact label `national`, `regional`, or `signed-pack`, followed by one ISO 3166-1 alpha-2 code per line and a final LF. The raw page hashes below are also retained, but they are not suitable as the only content identity because the national page emits a per-request CSRF token and the regional page emits a per-request JavaScript cache-buster.

Set differences are exact:

- signed minus national: `GN`, `CM`;
- regional minus national: `GN`, `CM`, `NE`;
- regional minus signed: `NE`;
- national minus signed: empty;
- signed minus regional: empty.

At the initial AS-IS inspection, no authority or applicability rule in the
repository resolved these differences. The Zero decision recorded above now
makes the national list controlling for the sequence-2 product overlay. The
regional page remains evidence of source drift, not a separate regional legal
regime.

### Conflict-safe runtime consequence

Following Zero's authority/freshness approval and sequence-2 signing, the
conflict-safe consequence until activation is:

- `AF`, `IL`, `KP`, `LR`, `NG`, `SO`: sequence 2 retains the Calling Visa review, subject to signed source-freshness gates.
- `GN`, `CM`, `NE`: sequence 2 excludes these countries. The current sequence-1 pack must not be edited; until sequence 2 is activated, any result still governed by the old pack remains conservative `HUMAN_REVIEW_REQUIRED` where freshness or source conflict is unresolved.
- A source retrieval failure, unknown effective date, missing official instrument, or expired observation must never resolve the conflict in favour of a recommendation.

This is a source conflict, not evidence of a regional legal regime. No regional divergence is assumed.

## Evidence ledger

### E1 - National Ditjen Imigrasi list

- URL: <https://www.imigrasi.go.id/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-calling-visa>
- Publisher: Direktorat Jenderal Imigrasi.
- Retrieval: HTTP 200 at 2026-08-06 03:52:52 UTC.
- Displayed list: Afghanistan, Israel, Korea Utara, Liberia, Nigeria, Somalia.
- First raw HTML SHA-256: `60b2bec11e1c45f512ffce5337bc2837305675d0193ad04eca5d77767c5d671f`.
- Second raw HTML SHA-256 at 2026-08-06 04:00:41 UTC: `6e9cca541f4075366f24abb5808e1507e83068d53e6e5e0fdc8531b5f1f844c2`.
- Raw difference: only the emitted CSRF token changed. The six-country ordered list did not change.
- Stable normalized-list SHA-256: `cfc36c1b65af69564e9a56b69c3b680288ece3d17350b6b46e9b396b3888f305`.
- Page-level effective date: not stated.
- Page-level last-updated date: blank.

Conclusion: this is current official national display evidence for six countries, not by itself a signed legal instrument or proof of the effective date of each removal.

### E2 - Regional Kanwil Sulawesi Tenggara list

- URL: <https://kanwilsultra.imigrasi.go.id/wna/daftar-subjek-voa-bvk-calling-visa>
- Publisher: Kantor Wilayah Direktorat Jenderal Imigrasi Sulawesi Tenggara.
- Retrieval: HTTP 200 at 2026-08-06 03:52:52 UTC.
- Displayed list: Afghanistan, Guinea, Israel, Kamerun, Liberia, Niger, Nigeria, Korea Utara, Somalia.
- First raw HTML SHA-256: `cf8687f4efc289c7262870fee797c41b10a64b64c9670d7e192ae3f7a05bdd67`.
- Second raw HTML SHA-256 at 2026-08-06 04:00:53 UTC: `87ccfdb22cc6815c55210ce553ec734a2f802d4b9763d45f94ee99d5516f5dce`.
- Raw difference: only the `main.js` cache-buster changed. The nine-country ordered list did not change.
- Stable normalized-list SHA-256: `be2967172527eb91c6be09ec4e03505b6b9cc08e3661062cebb57abea815d925`.
- Page label: `Terakhir Update : 06 Aug 2026`.

The page's update label is not sufficient provenance for the country set: it can be rendered from the current date and is not joined to an instrument, author, revision, or effective date. It must not silently override the national list.

### E3 - Current procedure regulation

- Official record: <https://peraturan.go.id/id/permenkumham-no-2-tahun-2024>.
- Official PDF: <https://peraturan.go.id/files/permenkumham-no-2-tahun-2024.pdf>.
- PDF SHA-256 observed 2026-08-06: `7c90dc281b1d625748f8719e90a0d954b7ca07eda113da99e32e5c0bb801905e`.
- Instrument: Permenkumham No. 2 Tahun 2024, enacted 2024-01-09, promulgated 2024-01-15, official status `Berlaku`.
- Locator: Pasal 2 states that the Minister determines which countries are categorized as Calling Visa countries.
- Locators: Pasal 5-7 establish the coordinating assessment team and require evaluation at least annually or as needed.
- Locator: Pasal 20 revokes Permenkumham No. 33 Tahun 2021.

This regulation establishes who decides and how the category is reviewed. It does not contain the current country list and cannot substitute for the ministerial decision that changes that list.

### E4 - Cameroon removal evidence

- Official national Ditjen Imigrasi press release: <https://www.imigrasi.go.id/siaran_pers/2023/11/29/siaran-pers-kamerun-dicabut-dari-daftar-calling-visa-dirjen-imigrasi-ada-pertimbangan-ekonomi-dan-keamanan?lang=id-ID>.
- Retrieval: HTTP 200 at 2026-08-06 (direct HTTP capture; browser fetch may return 403).
- Raw HTML SHA-256: `6eae2f0d09278c64ce6d11d908dbb7dc47b11377d687e4ee3682081d9bff0681`.
- Primary publication claim: Kepmenkumham No. `M.HH-05.GR.01.06 Tahun 2023`, approved 2023-11-23, removed Cameroon from the Calling Visa list and ended the Cameroon clearing-house procedure.
- The same publication says evaluation of Guinea's removal was in progress at that time.

This national primary publication supports that the signed pack's inclusion of `CM` is stale relative to the 2023 decision. The signed decision PDF itself is not archived in the inspected repository/Drive evidence and remains a required immutable source artifact before G1 and production activation can close. Cameroon can therefore be removed from the new national overlay; the missing PDF remains a provenance/archive gap, not uncertainty about the published operational outcome.

### E5 - Guinea 2024 decision lead, not yet archived proof

- Official Immigration Bandung page: <https://bandung.imigrasi.go.id/layanan-3/warga-negara-asing-wna/daftar-negara-voa-bvk-calling-visa>.
- The official page identifies Kepmenkumham No. `M.HH-03.GR.01.06 Tahun 2024` as the fifth amendment to Kepmenkumham No. `M.HH-03.GR.01.06 Tahun 2012` on Calling Visa countries.
- Direct page capture timed out in this verification run; no defensible raw hash was produced.
- The national six-country list, the 2023 official statement that Guinea removal was under evaluation, and the 2024 fifth-amendment identifier are converging evidence that Guinea may have been removed. That is an inference, not a substitute for the signed/issued decision text.
- No official PDF of Kepmenkumham No. `M.HH-03.GR.01.06 Tahun 2024` was found in the repository, exact Google Drive searches, or the fully scrolled 90-point `visa_oracle` Qdrant collection.

Consequence: Guinea remains `HUMAN_REVIEW_REQUIRED` under `SOURCE_CONFLICT` until the official decision PDF is acquired, its provenance and complete contents are verified, and it is archived with a reproducible hash. An unofficial document-hosting copy is not admissible as RulePack authority.

### E6 - Perpres 43/2011 is archived but unrelated historical evidence

- Local file: `/Users/nuzantara/Downloads/Perpres_no_43_2011.pdf`.
- Local SHA-256: `d4a4fca22fc92f1fec43f169b718e3ff59e095aed9a5c942dd931f0e5667c4e7`.
- PDF: 14,442 bytes, four pages, created 2011-07-29, no encryption, no embedded PDF signature.
- Visual and extracted-text inspection: Perpres No. 43 Tahun 2011 is the third amendment to Keppres No. 18 Tahun 2003 on short-visit visa exemption. Its list concerns historical BVK treatment and adds Cambodia, Laos, and Myanmar.
- Drive archive: `PERPRES_43_2011.pdf`, Drive file id `1pIUZsgX9dA0X0P8iYonaSR4kN2w4-frY`, 14,442 bytes, created and modified 2026-08-05 01:44:37 UTC.
- The Drive connector returned the correct name, MIME type, and size but not a provider checksum; byte identity with the local file is therefore not asserted solely from equal size.

Conclusion: archival of Perpres 43/2011 is DONE, but it does not resolve Calling Visa, Guinea, Cameroon, Niger, or the 2024 ministerial decision.

### E7 - Signed production RulePack

- Signed file: `apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-001.signed.json`.
- File SHA-256: `a1d5a217277d1972077dd4c40aaf16a3655a9cae654e438b0d423a8176fa6039`.
- Source file SHA-256: `632fb426193def8b7197c222dd14124c30edfcad383b054ce3daf56c15a74aa8`.
- Payload SHA-256 asserted by the signed envelope: `47a97c32045c1f58798c8661473c265decbab5d8427e0e606406a29402db5fda`.
- Protected header: Ed25519, RFC 8785, domain `balizero.visa-rulepack.v1`, environment `PRODUCTION`, key id `prod-2026-07-1`, signed at 2026-07-24 17:07:37 UTC.
- Sequence: 1; version: `2026.7.25`.
- Rule `review.calling-visa`: `AF GN IL CM KP LR NG SO`, priority 100, `REQUIRE_REVIEW`, `on_unknown=HUMAN_REVIEW`.
- Referenced source record `cd613d5b-83da-5150-a7b5-759eb4d224fe` is marked `VERIFIED`, retrieved/verified 2026-07-24, and points to the national URL.
- That source record has no locators, no document number, an unexplained `content_sha256` (`d13338d7b707f0803d99f8029accbba39615d9de63e4f7121af33684dc2f09ef`), and a legal period beginning on its retrieval date.

The source record cannot reproduce the current national list or explain why a national URL supports an eight-country value set. The existing signed pack must remain immutable; its source drift can only be cured by a new forward sequence.

### E8 - KB/Drive search coverage

- Native repository and local source directories: no Kepmenkumham No. `M.HH-03.GR.01.06 Tahun 2024` PDF found.
- Connected Drive exact searches for the instrument number and Calling Visa/Guinea terms: no matching official decision PDF. The archived Perpres file was found separately.
- Qdrant `visa_oracle`: 90/90 points scrolled; one C11A service document mentions Calling Visa but contains neither the country list nor the 2024 decision.
- Qdrant `legal_unified_2026` and `legal_unified_hybrid_hybrid`: reachable, but the read-only connector lacks filtered search/offset pagination; absence from those large collections is not asserted.
- Backend Drive/Naga search endpoints returned HTTP 401 in this run. The connected Drive plugin supplied the read-only Drive evidence above.

## Extension-policy contradictions in the signed pack

The model and generated JSON Schema validate field types and numeric ranges but express no cross-field invariant among `allowed`, `maximum_extensions`, and `days_per_extension`.

- Model SHA-256: `apps/backend-rag/backend/services/visa_engine/models.py` = `fd6ede344b0c43909307a51e0f90b7d520944e681c2f7a5667d7b68a9a796311`.
- Contract Schema SHA-256: `apps/backend-rag/backend/services/visa_engine/contracts/contract.schema.json` = `c33969b7437614c0d6e0d13e13228f7475baacef6fdd2457ac50c90fe60e1996`.

Sixteen active product records have `allowed=true` and `days_per_extension=null`:

| Codes                                                                 | `maximum_extensions` | Contradiction                                                                         |
| --------------------------------------------------------------------- | -------------------: | ------------------------------------------------------------------------------------- |
| `E28B`, `E28C`, `E28D`, `E28F`, `E33`, `E33A`, `E33B`, `E33C`, `E33E` |                    1 | Extension is declared allowed and counted, but its duration is not representable.     |
| `E23U`, `E23V`, `E30`, `E30A`, `E30B`, `E30E`, `E30F`                 |                    0 | Extension is declared allowed while the maximum count is zero; duration is also null. |

The latter seven are the exact grader finding. The data may be trying to encode renewable permits, variable programme duration, or an unknown operational decision, but those meanings are not equivalent and must not be inferred.

Conflict-safe consequence:

- do not display a numeric extension timeline from these records;
- treat extension availability/duration as `UNKNOWN` or `HUMAN_REVIEW_REQUIRED` until a cited product-specific policy is approved;
- do not convert `null` to zero, an assumed stay duration, or a default extension;
- do not call `allowed=true, maximum_extensions=0` a supported extension.

## Zero decision record and remaining G1 approvals

G1 cannot close until the items explicitly marked **REMAINING** are complete.

1. **Authority — DECIDED:** the national Ditjen consolidated list is canonical; a Kanwil page is non-controlling for the national product and cannot add a country.
2. **Guinea — COUNTRY TREATMENT DECIDED / ARCHIVE REMAINING:** exclude `GN` under the national-canonical rule; archive and verify Kepmenkumham No. `M.HH-03.GR.01.06 Tahun 2024`, including operative text, effective date and supersession lineage, before G1/activation.
3. **Cameroon — COUNTRY TREATMENT DECIDED / ARCHIVE REMAINING:** exclude `CM`; archive Kepmenkumham No. `M.HH-05.GR.01.06 Tahun 2023`, including its operative locator and effective date, before G1/activation.
4. **Niger — DECIDED:** exclude `NE` from the replacement national overlay. Do not mutate sequence 1; cases governed by sequence 1 remain conservative until sequence 2 activation.
5. **Conflict behaviour — DECIDED:** country/product conflict produces `HUMAN_REVIEW_REQUIRED`; source-integrity or global-provenance failure blocks the complete evaluation.
6. **Freshness — POLICY DECIDED / OPERATIONS REMAINING:** portal evidence is current for 7 days with daily recheck; primary law/implementing regulation for 365 days with monthly recheck. Zero must still assign the production owner/SLA, scheduler and alerting.
7. **Content identity — DECIDED:** dynamic Calling Visa pages use the deterministic normalized-list artifact; raw HTML hashes remain supporting captures only.
8. **Source lineage — DONE / ARCHIVE REMAINING:** sequence 2 records temporal fields, locators, hashes, publisher and forward lineage; the two official Kepmen artifacts remain unarchived.
9. **Extensions — DECIDED:** all 16 uncited policies are explicit neutral `UNKNOWN` with reason `EXTENSION_POLICY_NOT_VERIFIED`; no duration or positive claim is inferred.
10. **Schema — DONE:** sequence 2 requires explicit `VERIFIED` or `UNKNOWN` extension status and rejects contradictory shapes.

## Signed freshness policy record

The policy is signed data in all 28 sequence-2 source records, not an undocumented runtime constant:

| Input                      | Required decision                                                                                                                          |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `source_class`             | Controlling regulation, ministerial decision, consolidated national list, regional operational page, product page, official press release. |
| `authority_rank`           | Explicit precedence and applicability condition; equal rank must conflict, not silently tie-break.                                         |
| `max_observation_age`      | 7 days for official portals; 365 days for primary law and implementing regulations.                                                        |
| `recheck_cadence`          | Daily for portals and monthly for law/regulation; production owner, scheduler and alerting remain operational gates.                       |
| `retrieval_failure_policy` | Fail closed with no fabricated recommendation; escalation ownership remains an operational gate.                                           |
| `effective_date_policy`    | How publication, enactment, promulgation, and stated effective dates are selected.                                                         |
| `conflict_scope`           | Affected nationality/product only or global safety gate.                                                                                   |
| `canonicalization`         | Deterministic extraction version and normalized payload format.                                                                            |
| `immutable_archive`        | Raw artifact location, SHA-256, MIME type, byte size, acquisition URL, and acquisition timestamp.                                          |
| `review_identity`          | Verifier identity, independent grader identity, approval timestamp, and next-review due date.                                              |

An unknown or expired value for any decisive field must produce abstention or human review. It must never inherit the previous answer merely because a URL still resolves.

## Replacement RulePack completion checklist

The repair is forward-only. Items 1 and 11 remain activation gates; the other
steps are complete in the review candidate:

1. **REMAINING:** acquire and archive the official 2023 and 2024 ministerial decisions from an official origin; verify operative text, annexes, dates, issuer and provenance; record PDF SHA-256 and byte size.
2. **DONE:** archive reproducible national/regional observations and the normalized national-list artifact as separate evidence surfaces.
3. **DONE:** record decisive locators and bitemporal fields without treating retrieval time as legal effective time.
4. **DONE:** record Zero's national authority, conflict-scope, freshness, country-treatment and neutral-extension decisions above.
5. **DONE:** author a new source JSON without mutating sequence 1.
6. **DONE:** use sequence 2 and chain `previous_payload_sha256` to `47a97c32045c1f58798c8661473c265decbab5d8427e0e606406a29402db5fda`.
7. **DONE:** correct the country overlay and make all 16 unverified extensions explicit neutral `UNKNOWN`.
8. **DONE:** compile deterministically, validate references and add golden/adversarial vectors.
9. **DONE:** sign the exact canonical payload with the production Ed25519 key `kid=prod-2026-07-1`, preserving domain/environment binding and no unsigned fallback.
10. **DONE:** independently verify signature, hashes, sequence, compatibility, freshness, compilation and test evidence; generator and grader are distinct.
11. **REMAINING:** insert inactive, complete operational approvals/shadow evidence and activate only through the forward-only path. Do not mutate sequence 1 or bypass anti-rollback.

## G1 matrix

| G1 element                                      | Status  | Evidence / missing closure                                                                                                                       |
| ----------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Current national display captured               | DONE    | Six countries, two captures, dynamic-field difference isolated, stable normalized hash recorded.                                                 |
| Current regional display captured               | DONE    | Nine countries, two captures, dynamic-field difference isolated, stable normalized hash recorded.                                                |
| Signed production set inspected                 | DONE    | Eight countries, signed-file/payload hashes, sequence and source record inspected.                                                               |
| Calling Visa procedure authority                | DONE    | Permenkumham 2/2024 official PDF and decisive locators verified.                                                                                 |
| Perpres 43/2011 classification/archive          | DONE    | Historical BVK source identified; local hash and Drive object recorded; explicitly non-dispositive.                                              |
| Cameroon legal lineage                          | PARTIAL | National Ditjen Imigrasi primary publication, decision number and operative outcome verified; official decision PDF/immutable hash missing.      |
| Guinea legal lineage                            | PARTIAL | Official national display and fifth-amendment identifier converge; operative official PDF and effective locator missing.                         |
| Niger legal status                              | DECIDED | Excluded from the replacement national overlay; regional-only inclusion is non-controlling.                                                      |
| Source authority/applicability policy           | DECIDED | National Ditjen list is canonical for the national product; regional pages cannot add countries.                                                 |
| Signed freshness policy                         | DONE    | All 28 sequence-2 source records carry approved max ages; cadence and conflict scope are recorded; production signature verified.                |
| Reproducible current Calling Visa source record | DONE    | Sequence 2 uses the normalized national six-country artifact hash, locator, observation clock, freshness policy and forward source lineage.      |
| Extension source mapping                        | PARTIAL | Sixteen uncited/ambiguous products are explicit `UNKNOWN`; no duration or positive extension claim is emitted pending product-specific locators. |
| Extension cross-field contract                  | DONE    | Sequence 2 requires `VERIFIED` or `UNKNOWN`; unknown is neutral and verified shapes reject count/duration contradictions.                        |
| Replacement RulePack                            | DONE    | Sequence 2, previous-hash chain, corrected national source record, clean compilation and production Ed25519 signature verified; inactive.        |
| Independent implementation review               | DONE    | Independent grader LGTM on review candidate `0f37138fc`; G1 itself remains blocked by the explicitly listed source/policy approvals.             |

## Gate verdict

`G1: PARTIAL / ACTIVATION BLOCKED`.

The national authority and replacement country treatment are now decided:
`AF IL KP LR NG SO`, with `GN CM NE` excluded. The signed replacement pack and
freshness policy are complete. The 16 ambiguous extension policies now remain
explicitly `UNKNOWN`, with no invented duration or positive extension claim.
Activation still requires the missing official instrument archives,
independent verification, and the operational production gates. The existing
sequence-1 pack remains immutable and cannot be silently edited.

The signed sequence-2 candidate records the approved observation policy:
official portal pages are current for 7 days and rechecked daily; primary law
and implementing regulations are current for 365 days and rechecked monthly.
The conflict scope is the affected nationality/product; a source-integrity or
global provenance failure blocks the complete evaluation. These values are
encoded in all 28 candidate source records as signed data inputs, not runtime
defaults. All 19 official-portal sources were successfully re-observed over
HTTP 200 at 2026-08-06 06:19:49 UTC, assigned forward source lineage where
needed, and remain inside the seven-day policy window. The bundle was then
re-signed offline on M5 with `kid=prod-2026-07-1` at 2026-08-06 06:27:56 UTC.
Its payload SHA-256 is
`d51ba2b18230720fbc62e79b8944df46515fb732c962c73c503899edddd9cb31`;
the signed-file SHA-256 is
`fcad4e476f2f8760aefd220e3929eb9eb5b08fda17e9a17c4152544eebe0a775`.
They become production-effective only after activation.

An earlier sequence-2 signing attempt with payload SHA-256
`19817c59a10666397507537f110a28cb39dca71dfbb07b5d02d8a55cd04feae4`
is explicitly **REJECTED** because its portal observations were stale at its
signed clock. It must never be inserted or activated. The Claude-review branch
is constructed as a single commit from `main`, so that rejected signed
artifact is not reachable from the review history; only the canonical
`d51ba2b1...` successor is present.
