# TKA KBLI Verification Report

Generated: 2026-07-01

## Verdict

Research-grade, gaps documented. The dataset validates for all 1559 KBLI codes, but it is not production-ready because zero permitted jabatan rows have been extracted from the official Kepmenaker 228/2019 lampiran in this pass.

## Confirmed

- KBLI record count: 1559.
- Confidence counts: HIGH=0, MEDIUM=0, LOW=1559.
- JDIH Kemnaker marks Kepmenaker 228/2019 as `Berlaku` and lists document `Kepmen_228_2019_OK.pdf`.
- JDIH Kemnaker marks Kepmenaker 349/2019 as `Berlaku`.
- Kepmenaker 349/2019 Lampiran rows 1-18 were read from official PDF text and included as cross-sector forbidden positions.
- PP 34/2021 local PDF supports the model: TKA use is tied to `jabatan tertentu`, RPTKA approval, Indonesian counterpart/skill transfer, and prohibition on personnel-handling positions.
- KBLI source shape was independently checked: `data.length` is 1559, source `sektor_id` is resolved on 1342 records and unresolved on 217.

## Refuted or excluded

- No permitted jabatan from ISCO/KBJI proxy, generated guides, or existing internal mapping was included.
- No permitted jabatan from Kepmenaker 228/2019 was included, because no lampiran row was re-opened and extracted in this pass.
- The internal hint that the closed list contains more than 18 rows was not ingested; only rows visible in the official Kepmenaker 349/2019 PDF text were included.
- KBLI section A-U was not accepted as an authoritative TKA sector map; it is retained only as a fallback QA grouping.

## Downgraded

- All sectors are LOW for the full KBLI-to-permitted-position claim because permitted positions are not yet row-verified.
- All KBLI section fallback groups remain row-unverified against Kepmenaker 228/2019.
- 217 KBLI records have unresolved source `sektor_id`; 42 of those carry candidate `sektors`.

## LOW KBLI section fallback groups

A, B, C, D, E, F, G, H, I, J, K, L, M, N, O, P, Q, R, S, T, U

## Source URLs checked

- https://jdih.kemnaker.go.id/peraturan/detail/1609/keputusan-menteri-ketenagakerjaan-nomor-228-tahun-2019
- https://jdih.kemnaker.go.id/peraturan/detail/1636/keputusan-menteri-ketenagakerjaan-nomor-349-tahun-2019
- https://jdih.kemnaker.go.id/peraturan/detail/1722/peraturan-pemerintah-nomor-34-tahun-2021
- https://jdih.kemnaker.go.id/asset/data_puu/Kepmen_349_2019.pdf

## Most important next verification gate

Download and OCR/parse `Kepmen_228_2019_OK.pdf` on Pro, then perform an independent row-level verification pass before adding any permitted position to `tka_kbli_positions.json`.
