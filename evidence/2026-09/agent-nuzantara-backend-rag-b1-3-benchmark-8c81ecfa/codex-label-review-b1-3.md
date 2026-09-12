---
title: "B1.3 label review round 1 — Codex gpt-5.6-sol (effort high, read-only)"
reviewed_sha: 6e50a41535ab42e679349307f93093e421153fb4 # pragma: allowlist secret
started: 2026-09-11T17:46:50Z
ended: 2026-09-11T17:55:14Z
---

VERDICT: BLOCK

LABELS:
bs-07dda8f1 DISAGREE [generic_overlap -> true] — “all” occurs in both query and context and is a generic non-identifier token.
bs-62289ee3 AGREE [no change] — The context explicitly states the requested all-in PT PMA price.
bs-30ca5e5a DISAGREE [stratum -> relevant_insufficient; supporting_span -> remove; missing_fact_explanation -> "The chunk lists components of company setup but does not state that they are prerequisites for obtaining NIB or OSS registration."; expected_generation_gate -> abstain; expected_label_gate -> abstain] — “Including deed … and NIB via OSS” is a bundle description, not a requirements relation.
bs-6cd7df49 AGREE [no change] — The context contains no paid-up-capital figure, so the B2.1 correction is right.
bs-57978a96 AGREE [no change] — The Indonesian context explicitly states the all-in price.
bs-3d3b5229 DISAGREE [stratum -> relevant_insufficient; supporting_span -> remove; missing_fact_explanation -> "The chunk lists components of company setup but does not state that they are prerequisites for obtaining NIB or OSS registration."; expected_generation_gate -> abstain; expected_label_gate -> abstain] — The Indonesian bundle description does not answer the English requirements question.
bs-a3a7f1ca AGREE [no change] — The context omits paid-up capital, making the B2.1 correction correct.
bs-dd6ff12d AGREE [no change] — The context contains no registration timeframe, making the B2.1 correction correct.
bs-e42f4b0d AGREE [no change] — Scooter rental supplies no fact or nuisance overlap for the surfing question.
bs-38ed9327 AGREE [no change] — A Canggu rental listing is irrelevant to activities in Ubud.
bs-95e82de0 AGREE [no change] — The malformed query requests no decidable fact and shares nothing with the context.
bs-f6687bb2 AGREE [no change] — The malformed query requests no decidable fact and shares nothing with the context.
bs-17806bb4 AGREE [no change] — The Indonesian context directly states the company-setup price despite the query naming no identifier.
bs-2641bf9a AGREE [no change] — “harga” is the sole generic overlap and the company-price context cannot answer a motorbike-rental question.
bs-01bf2a65 AGREE [no change] — The context explicitly states one all-inclusive price and the pair mate removes that fact.
bs-86c7963f AGREE [no change] — The context names the price topic but supplies no amount or all-in price.
bs-ebef4f3e AGREE [no change] — The Indonesian context explicitly supplies the requested all-inclusive price.
bs-71ce8130 AGREE [no change] — The Indonesian context discusses pricing but gives no price.
bs-0912abc7 DISAGREE [generic_overlap -> true] — The generic token “all” appears in both the Indonesian query and English context.
bs-25e7c342 AGREE [no change] — The context gives no figure and does not repeat the query’s generic “all” token.
bs-6309899f AGREE [no change] — The Indonesian context explicitly states the all-inclusive price.
bs-8e5a0135 AGREE [no change] — The context discusses price dependency without stating the requested price.
bs-37a4d621 AGREE [no change] — The context explicitly conditions NIB issuance on the listed prerequisites.
bs-f8fb6909 AGREE [no change] — NIB/OSS is relevant, but the requirements checklist is expressly omitted.
bs-7cd45469 AGREE [no change] — The Indonesian context explicitly states the prerequisites for NIB issuance.
bs-5d3e92ff AGREE [no change] — The Indonesian context expressly withholds the detailed NIB/OSS requirements.
bs-cfd6fca4 AGREE [no change] — The English context explicitly answers the Indonesian requirements question.
bs-e896eab7 AGREE [no change] — The English context names NIB/OSS but omits the requested checklist.
bs-cc8e039c AGREE [no change] — The Indonesian context explicitly states the NIB prerequisites.
bs-5b935617 AGREE [no change] — The Indonesian context is relevant but expressly omits the requirements.
bs-713c5c75 AGREE [no change] — The context explicitly states the minimum paid-up-capital figure.
bs-3d9ad45b AGREE [no change] — The context discusses capital but withholds the required figure.
bs-3edd5ce2 AGREE [no change] — The Indonesian context directly states the requested capital figure.
bs-7734b413 AGREE [no change] — The Indonesian context names paid-up capital but provides no amount.
bs-b96e2f5d AGREE [no change] — The English context directly answers the Indonesian capital question.
bs-86211518 AGREE [no change] — The English context provides no paid-up-capital figure.
bs-47392f91 AGREE [no change] — The Indonesian context explicitly states the minimum capital.
bs-bcbd34e0 AGREE [no change] — The Indonesian context discusses the capital topic without stating a figure.
bs-b762b369 AGREE [no change] — The context explicitly states a synthetic three-to-four-week duration.
bs-5d6af55b AGREE [no change] — The context names registration duration but gives no timeframe.
bs-b980e91b AGREE [no change] — The Indonesian context explicitly states the requested duration.
bs-eaeff9b4 AGREE [no change] — The Indonesian context says duration varies but supplies no timeframe.
bs-65886be1 AGREE [no change] — The English context explicitly answers the Indonesian duration question.
bs-6b1f7df4 AGREE [no change] — The context mentions duration without giving the requested timeframe.
bs-11f72d22 AGREE [no change] — The Indonesian context explicitly states the duration.
bs-4eb281c7 AGREE [no change] — The Indonesian context discusses duration but provides no timeframe.
bs-c0693a25 DISAGREE [stratum -> generic_overlap; generic_overlap -> true; missing_fact_explanation -> "The permit-fee context cannot answer the ferry question, but the generic word 'time' occurs in both texts with different meanings."] — The label incorrectly claims no shared word despite the exact “time” overlap.
bs-dd593d7a AGREE [no change] — “processing” is an exact generic overlap, while the topics remain company registration and visa extension.
bs-b2266ec0 AGREE [no change] — PT/NIB identifiers belong to an unrelated synthetic rental listing and supply no general requirement.
bs-c64a7b17 AGREE [no change] — The Indonesian permit-fee notice has no lexical or topical overlap with the English ferry question.
bs-e234b992 DISAGREE [stratum -> irrelevant; generic_overlap -> false; missing_fact_explanation -> "The Indonesian company-registration context is off-topic and shares no identical generic query word with the English visa-extension question."] — “processing” and “proses” are translations, not a shared word under the stated lexical rule.
bs-b3d343f6 AGREE [no change] — The synthetic rental listing contains matching company prefixes but cannot answer the PT PMA requirement question.
bs-a4e66d32 AGREE [no change] — The English permit-fee notice has no shared word or relevant fact for the Indonesian ferry question.
bs-2ae24f1c DISAGREE [stratum -> irrelevant; generic_overlap -> false; missing_fact_explanation -> "The English company-registration context is off-topic and shares no identical generic query word with the Indonesian visa-extension question."] — “proses” and “processing” are translations, not a shared word.
bs-5bab1cbe AGREE [no change] — Matching PT/NIB prefixes in an unrelated synthetic rental listing do not establish a PT PMA requirement.
bs-19c40235 AGREE [no change] — The Indonesian permit-fee notice contains neither the ferry fact nor a nuisance overlap.
bs-797ff307 AGREE [no change] — “proses” is an exact generic overlap, but the company-registration context remains off-topic.
bs-88096955 AGREE [no change] — The synthetic listing matches company prefixes only and gives no general NIB requirement.

FINDINGS:

1. apps/backend-rag/backend/tests/benchmarks/evidence_sufficiency/manifest_mandatory.json:137,230 — HIGH — Evidence: both contexts coordinate deed, approval, NPWP and NIB as company-setup components; neither says those items are prerequisites for NIB/OSS, exactly the ambiguity identified in B1-3-build-spec.md:62-64. Smallest fix: relabel both `relevant_insufficient`, replace the span with a missing-fact explanation, set both gates to `abstain`, then re-pin the manifest hash after review.
2. apps/backend-rag/backend/tests/benchmarks/evidence_sufficiency/manifest_mandatory.json:1664,1756 — HIGH — Evidence: the cross-language cases claim a shared word, but `processing` and `proses` are different lexical forms; correcting them to `irrelevant` removes the only `generic_overlap` member from each cross-language cell and breaks the balance contract. Smallest fix: replace each case with an off-topic cross-language example sharing an identical neutral token such as `online`, then independently relabel and re-pin.
3. apps/backend-rag/backend/tests/benchmarks/evidence_sufficiency/manifest_mandatory.json:1541 — MEDIUM — Evidence: `time` appears verbatim in both “What time…” and “over time,” contradicting `generic_overlap: false` and the missing-fact explanation. Smallest fix: set `stratum` to `generic_overlap`, set the nuisance boolean true, and update the explanation.
4. apps/backend-rag/backend/tests/benchmarks/evidence_sufficiency/manifest_mandatory.json:77,637 — MEDIUM — Evidence: both sufficient cases repeat the generic token `all`, while the analogous EN>EN sufficient case records the nuisance. Smallest fix: set `generic_overlap: true` for both cases.
5. apps/backend-rag/backend/tests/benchmarks/evidence_sufficiency/harness.py:220-295 — HIGH — Evidence: `report()` accepts one manifest and returns one undifferentiated aggregate; it has no validation-set argument or separately marked mandatory/validation sections, contrary to README.md:33 and B1-design.md:58. Smallest fix: accept mandatory and optional validation manifests and return distinct `mandatory` and `validation` result sections.
6. apps/backend-rag/backend/tests/benchmarks/evidence_sufficiency/harness.py:175-193 — INFO — Evidence: `decide()` reads only `query`, `context`, and provenance sources; no label, span, requested fact, nuisance flag, origin, pair ID, or expected gate can select scorer inputs. Smallest fix: none.
7. apps/backend-rag/backend/tests/benchmarks/evidence_sufficiency/harness.py:77-151 — MEDIUM — Evidence: `validate()` does not require the mandatory nuisance booleans or validate the required provenance members; `report()` silently treats a missing `fee_policy` as false at line 239. Smallest fix: require all three booleans, validate their types, and validate `inventory_row`, `sources`, `score`, `score_kind`, `score_raw`, and `note`.
8. apps/backend-rag/backend/tests/benchmarks/evidence_sufficiency/manifest_mandatory.json:577,1089 — LOW — Evidence: constructed Indonesian uses the awkward/category-confused phrases `izin usaha NIB` and `perusahaan terbatas berpenanaman modal asing`. Smallest fix: use `NIB melalui OSS` and `perseroan terbatas dengan penanaman modal asing` consistently in their paired variants.
9. apps/backend-rag/backend/tests/benchmarks/evidence_sufficiency/manifest_mandatory.json:509-1530 — INFO — Evidence: every `pair_id` has the same query, language cell, entity/topic framing and provenance, with the fact-bearing sentence replaced by an on-topic omission; no additional pair defect was found. Smallest fix: none.
10. apps/backend-rag/backend/tests/benchmarks/evidence_sufficiency/manifest_mandatory.json:77-1902 — INFO — Evidence: all 58 cases are marked synthetic; no natural-person identifier, contact datum, client narrative, or apparent real-client text is present, and the company listing uses an obviously synthetic sequential identifier. Smallest fix: none.

VALIDATION_JSON: [
{
"case_id": "bv-a1c4e709",
"query": "Which report must a PT PMA submit every quarter through OSS?",
"query_lang": "EN",
"context": [
"A PT PMA must submit the LKPM investment activity report every quarter through OSS."
],
"context_lang": "EN",
"provenance_fixture": {
"inventory_row": 1,
"sources": [
{
"score": 1.0,
"score_kind": "hybrid_rrf_formatted",
"score_raw": 1.0
}
],
"note": "constructed on-topic: rank 0 in both prefetch lists (dense + sparse) -> server-side RRF fusion 1.0 -> formatted 1.0"
},
"requested_fact": "the name of the quarterly report submitted by a PT PMA through OSS",
"supporting_span": "A PT PMA must submit the LKPM investment activity report every quarter through OSS.",
"stratum": "sufficient",
"generic_overlap": true,
"company_prefix": true,
"fee_policy": false,
"expected_generation_gate": "pass",
"expected_label_gate": "pass",
"synthetic": true,
"origin": "constructed:codex-validation"
},
{
"case_id": "bv-b82d6f13",
"query": "Where is an Indonesian e-Visa approval delivered?",
"query_lang": "EN",
"context": [
"Persetujuan e-Visa Indonesia dikirim secara elektronik ke alamat email yang didaftarkan pemohon."
],
"context_lang": "ID",
"provenance_fixture": {
"inventory_row": 1,
"sources": [
{
"score": 1.0,
"score_kind": "hybrid_rrf_formatted",
"score_raw": 1.0
}
],
"note": "constructed on-topic: rank 0 in both prefetch lists (dense + sparse) -> server-side RRF fusion 1.0 -> formatted 1.0"
},
"requested_fact": "the delivery destination for an Indonesian e-Visa approval",
"supporting_span": "Persetujuan e-Visa Indonesia dikirim secara elektronik ke alamat email yang didaftarkan pemohon.",
"stratum": "sufficient",
"generic_overlap": false,
"company_prefix": false,
"fee_policy": false,
"expected_generation_gate": "pass",
"expected_label_gate": "pass",
"synthetic": true,
"origin": "constructed:codex-validation"
},
{
"case_id": "bv-c03a91de",
"query": "Dokumen apa yang diberikan pemberi kerja sebagai bukti pemotongan PPh 21?",
"query_lang": "ID",
"context": [
"The employer provides a PPh 21 withholding slip as evidence that employee income tax was withheld."
],
"context_lang": "EN",
"provenance_fixture": {
"inventory_row": 1,
"sources": [
{
"score": 1.0,
"score_kind": "hybrid_rrf_formatted",
"score_raw": 1.0
}
],
"note": "constructed on-topic: rank 0 in both prefetch lists (dense + sparse) -> server-side RRF fusion 1.0 -> formatted 1.0"
},
"requested_fact": "the document proving that an employer withheld PPh 21",
"supporting_span": "The employer provides a PPh 21 withholding slip as evidence that employee income tax was withheld.",
"stratum": "sufficient",
"generic_overlap": false,
"company_prefix": false,
"fee_policy": false,
"expected_generation_gate": "pass",
"expected_label_gate": "pass",
"synthetic": true,
"origin": "constructed:codex-validation"
},
{
"case_id": "bv-d7e2458b",
"query": "Dokumen apa yang membuktikan pengesahan badan hukum perseroan?",
"query_lang": "ID",
"context": [
"Pengesahan badan hukum perseroan dibuktikan dengan Surat Keputusan Menteri Hukum."
],
"context_lang": "ID",
"provenance_fixture": {
"inventory_row": 1,
"sources": [
{
"score": 1.0,
"score_kind": "hybrid_rrf_formatted",
"score_raw": 1.0
}
],
"note": "constructed on-topic: rank 0 in both prefetch lists (dense + sparse) -> server-side RRF fusion 1.0 -> formatted 1.0"
},
"requested_fact": "the document evidencing approval of a company's legal-entity status",
"supporting_span": "Pengesahan badan hukum perseroan dibuktikan dengan Surat Keputusan Menteri Hukum.",
"stratum": "sufficient",
"generic_overlap": true,
"company_prefix": false,
"fee_policy": false,
"expected_generation_gate": "pass",
"expected_label_gate": "pass",
"synthetic": true,
"origin": "constructed:codex-validation"
},
{
"case_id": "bv-e9163ac4",
"query": "Which documents are needed to change the sponsor on a KITAS?",
"query_lang": "EN",
"context": [
"A KITAS sponsor change requires a new immigration application, but this summary does not list the required documents."
],
"context_lang": "EN",
"provenance_fixture": {
"inventory_row": 1,
"sources": [
{
"score": 1.0,
"score_kind": "hybrid_rrf_formatted",
"score_raw": 1.0
}
],
"note": "constructed on-topic: rank 0 in both prefetch lists (dense + sparse) -> server-side RRF fusion 1.0 -> formatted 1.0"
},
"requested_fact": "the document list required for a KITAS sponsor change",
"missing_fact_explanation": "The context confirms that an application is required but explicitly omits the requested document list.",
"stratum": "relevant_insufficient",
"generic_overlap": true,
"company_prefix": false,
"fee_policy": false,
"expected_generation_gate": "abstain",
"expected_label_gate": "abstain",
"synthetic": true,
"origin": "constructed:codex-validation"
},
{
"case_id": "bv-f4b07d2e",
"query": "By what date must a PKP issue a VAT tax invoice?",
"query_lang": "EN",
"context": [
"PKP wajib menerbitkan faktur pajak untuk penyerahan kena pajak, tetapi ringkasan ini tidak menyebutkan batas waktunya."
],
"context_lang": "ID",
"provenance_fixture": {
"inventory_row": 1,
"sources": [
{
"score": 1.0,
"score_kind": "hybrid_rrf_formatted",
"score_raw": 1.0
}
],
"note": "constructed on-topic: rank 0 in both prefetch lists (dense + sparse) -> server-side RRF fusion 1.0 -> formatted 1.0"
},
"requested_fact": "the deadline for a PKP to issue a VAT tax invoice",
"missing_fact_explanation": "The context confirms the invoicing obligation but expressly omits its deadline.",
"stratum": "relevant_insufficient",
"generic_overlap": false,
"company_prefix": false,
"fee_policy": false,
"expected_generation_gate": "abstain",
"expected_label_gate": "abstain",
"synthetic": true,
"origin": "constructed:codex-validation"
},
{
"case_id": "bv-1a6fd953",
"query": "Di portal mana laporan tahunan perseroan diajukan?",
"query_lang": "ID",
"context": [
"Indonesian companies have annual reporting obligations, but this summary does not identify the submission portal."
],
"context_lang": "EN",
"provenance_fixture": {
"inventory_row": 1,
"sources": [
{
"score": 1.0,
"score_kind": "hybrid_rrf_formatted",
"score_raw": 1.0
}
],
"note": "constructed on-topic: rank 0 in both prefetch lists (dense + sparse) -> server-side RRF fusion 1.0 -> formatted 1.0"
},
"requested_fact": "the portal used to submit a company's annual report",
"missing_fact_explanation": "The context confirms annual reporting obligations but does not identify the submission portal.",
"stratum": "relevant_insufficient",
"generic_overlap": true,
"company_prefix": false,
"fee_policy": false,
"expected_generation_gate": "abstain",
"expected_label_gate": "abstain",
"synthetic": true,
"origin": "constructed:codex-validation"
},
{
"case_id": "bv-2c8e4b71",
"query": "Berapa lama izin masuk kembali tetap berlaku?",
"query_lang": "ID",
"context": [
"Izin masuk kembali memiliki masa berlaku yang harus diperiksa sebelum bepergian, tetapi durasinya tidak dicantumkan di sini."
],
"context_lang": "ID",
"provenance_fixture": {
"inventory_row": 1,
"sources": [
{
"score": 1.0,
"score_kind": "hybrid_rrf_formatted",
"score_raw": 1.0
}
],
"note": "constructed on-topic: rank 0 in both prefetch lists (dense + sparse) -> server-side RRF fusion 1.0 -> formatted 1.0"
},
"requested_fact": "the validity period of a re-entry permit",
"missing_fact_explanation": "The context discusses the permit's validity but gives no duration.",
"stratum": "relevant_insufficient",
"generic_overlap": true,
"company_prefix": false,
"fee_policy": false,
"expected_generation_gate": "abstain",
"expected_label_gate": "abstain",
"synthetic": true,
"origin": "constructed:codex-validation"
},
{
"case_id": "bv-3d95a0cf",
"query": "Name the monthly employee withholding-tax form.",
"query_lang": "EN",
"context": [
"Sunrise over rice fields appears before clouds."
],
"context_lang": "EN",
"provenance_fixture": {
"inventory_row": 1,
"sources": [
{
"score": 0.6667,
"score_kind": "hybrid_rrf_formatted",
"score_raw": 0.5
}
],
"note": "constructed off-topic: rank 0 in the dense list only -> server-side RRF fusion 0.5 -> formatted 0.6667"
},
"requested_fact": "the form used for monthly employee withholding-tax reporting",
"missing_fact_explanation": "The context describes a landscape and has no topical, lexical, or identifier overlap with the tax question.",
"stratum": "irrelevant",
"generic_overlap": false,
"company_prefix": false,
"fee_policy": false,
"expected_generation_gate": "abstain",
"expected_label_gate": "abstain",
"synthetic": true,
"origin": "constructed:codex-validation"
},
{
"case_id": "bv-4e17bc62",
"query": "Can an Indonesian visa application be submitted online?",
"query_lang": "EN",
"context": [
"Tiket konser dapat dibeli online melalui situs penyelenggara."
],
"context_lang": "ID",
"provenance_fixture": {
"inventory_row": 1,
"sources": [
{
"score": 0.6667,
"score_kind": "hybrid_rrf_formatted",
"score_raw": 0.5
}
],
"note": "constructed off-topic: rank 0 in the dense list only -> server-side RRF fusion 0.5 -> formatted 0.6667"
},
"requested_fact": "whether an Indonesian visa application can be submitted online",
"missing_fact_explanation": "The context concerns concert-ticket purchasing; only the generic token 'online' overlaps.",
"stratum": "generic_overlap",
"generic_overlap": true,
"company_prefix": false,
"fee_policy": false,
"expected_generation_gate": "abstain",
"expected_label_gate": "abstain",
"synthetic": true,
"origin": "constructed:codex-validation"
},
{
"case_id": "bv-5f2a8d90",
"query": "Bagaimana cara memperbarui data PT PMA di OSS?",
"query_lang": "ID",
"context": [
"PT Contoh Sintetis, NIB 0000000000000, rents bicycles near a public park and provides helmets with every rental."
],
"context_lang": "EN",
"provenance_fixture": {
"inventory_row": 1,
"sources": [
{
"score": 0.6667,
"score_kind": "hybrid_rrf_formatted",
"score_raw": 0.5
}
],
"note": "constructed off-topic: rank 0 in the dense list only -> server-side RRF fusion 0.5 -> formatted 0.6667"
},
"requested_fact": "the procedure for updating PT PMA data in OSS",
"missing_fact_explanation": "The context is an unrelated synthetic bicycle-rental listing whose PT/NIB prefixes do not describe an OSS update procedure.",
"stratum": "company_prefix_chunk",
"generic_overlap": false,
"company_prefix": true,
"fee_policy": false,
"expected_generation_gate": "abstain",
"expected_label_gate": "abstain",
"synthetic": true,
"origin": "constructed:codex-validation"
},
{
"case_id": "bv-6b43e1a7",
"query": "Syarat dokumen pengembalian pajak badan?",
"query_lang": "ID",
"context": [
"Tarif PNBP tiket museum berubah setiap musim."
],
"context_lang": "ID",
"provenance_fixture": {
"inventory_row": 1,
"sources": [
{
"score": 0.6667,
"score_kind": "hybrid_rrf_formatted",
"score_raw": 0.5
}
],
"note": "constructed off-topic: rank 0 in the dense list only -> server-side RRF fusion 0.5 -> formatted 0.6667"
},
"requested_fact": "the documents required for a corporate tax-refund request",
"missing_fact_explanation": "The context states a museum-entry PNBP tariff and contains no fact or nuisance overlap relevant to a corporate tax refund.",
"stratum": "irrelevant",
"generic_overlap": false,
"company_prefix": false,
"fee_policy": true,
"expected_generation_gate": "abstain",
"expected_label_gate": "abstain",
"synthetic": true,
"origin": "constructed:codex-validation"
}
]
Il gate read-only è concluso; registro soltanto il checkpoint di continuità richiesto dall’hook, senza modificare il repository.

Checkpoint saved successfully. No repository files were modified.
tokens used
234.972
Checkpoint saved successfully. No repository files were modified.
