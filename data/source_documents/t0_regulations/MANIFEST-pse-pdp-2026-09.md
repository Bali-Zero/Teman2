# MANIFEST: PSE and PDP regulation sources (2026-09)

Primary-source PDFs for the PSE (electronic system operator) and PDP (personal data protection)
layer of the compliance stack. Retrieved 2026-09-11 from government primary sources only
(peraturan.go.id, peraturan.bpk.go.id, jdih.komdigi.go.id). No commercial mirror was used.

**Not ingested.** Ingestion into the `legal_unified` collection is a post-merge runtime step
(`POST /api/legal/ingest`, admin-gated) run by the imperator. This file only pins what was
downloaded and where from.

## Size policy applied

- `.pre-commit-config.yaml` runs `check-added-large-files` with `--maxkb=1000`.
- `.gitattributes` has no LFS filter; the repo does not use Git LFS.
- A file above 1000 KB is recorded here with URL and sha256 only; the binary is **not committed**.
  (`PP45_2024_PNBP.pdf`, 1,373,974 bytes, predates this manifest and is not a precedent.)

## Committed PDFs

| File                                                       | Regulation                               | Bytes   | Pages | sha256                                                             |
| ---------------------------------------------------------- | ---------------------------------------- | ------- | ----- | ------------------------------------------------------------------ |
| `pp_71_2019_penyelenggaraan_sistem_transaksi_elektronik.pdf` | PP 71/2019, body (LN 2019/185)           | 581981  | 62    | `687633481f9eae039b0af965dc1dee58d1dd323c97754f789e8acedb32bd0eda` |
| `pp_71_2019_penjelasan_tln_6400.pdf`                       | PP 71/2019, elucidation (TLN 6400)       | 366334  | 36    | `2d846bb8b05cb73b8967a300cd93174a7849cf36a8d3453e0ed50d7dbd26ce82` |
| `permenkominfo_5_2020_pse_lingkup_privat.pdf`              | Permenkominfo 5/2020 (BN 2020/1376)      | 445661  | 41    | `05c3703a288dd72c58f2b85c27a08da06f7a99631fb5c5a4eca40e5db76da002` |
| `permenkominfo_10_2021_perubahan_pse_lingkup_privat.pdf`   | Permenkominfo 10/2021 (BN 2021/554)      | 82925   | 4     | `9a8deed47b1ee471989e1347ec2f9e11803cc32e7c361c60638018da0a353bd9` |

## Recorded only (binary over 1000 KB, not committed)

| Regulation                             | Bytes   | Pages | sha256                                                             |
| -------------------------------------- | ------- | ----- | ------------------------------------------------------------------ |
| UU 27/2022 (LN 2022/196, TLN 6820)     | 2977828 | 50    | `ed952dea04b87d14ecf037f9f324a65d50b396ddd34fc28ddf9ff014391971f6` |
| PMK 37/2025 (BN 2025/489)              | 1621966 | 23    | `46a80cd38d9dab763f53a298cae89e5d3c5ceabc5e7b0fe8e7d8b060aa45d1aa` |

To restore either binary: download from the source URL below and check it with `shasum -a 256`.

## Per-regulation detail

### PP 71/2019: Penyelenggaraan Sistem dan Transaksi Elektronik

- Source URL (body): https://peraturan.go.id/files/LN185-PP71.pdf
- Source URL (elucidation): https://peraturan.go.id/files/TLN-6400+PP71.pdf
- Landing page: https://peraturan.go.id/id/pp-no-71-tahun-2019
- Ditetapkan 4 October 2019; diundangkan 10 October 2019. **Effective: 10 October 2019.**
- Status per peraturan.bpk.go.id: Berlaku. Revokes PP 82/2012.
- Other primary copy: https://peraturan.bpk.go.id/Download/112816/PP%20Nomor%2071%20Tahun%202019.pdf
  (body and elucidation in one file, 5,344,523 bytes, 90 pages, sha256
  `0c454f81e36883d1a2c004247523baaa9f0d121eb60c8b42309cd3487f0ae6a8`; byte-identical to
  https://jdih.komdigi.go.id/produk_hukum/pratinjau/id/695). Not committed: over the size limit.
  The peraturan.go.id split (body + elucidation) is committed instead.

### Permenkominfo 5/2020: Penyelenggara Sistem Elektronik Lingkup Privat

- Source URL: https://peraturan.go.id/files/bn1376-2020.pdf
- Landing page: https://peraturan.go.id/id/permenkominfo-no-5-tahun-2020
- Ditetapkan 16 November 2020; diundangkan 24 November 2020. **Effective: 24 November 2020**
  (Pasal 49: in force on the date of promulgation).
- Status per peraturan.bpk.go.id: Berlaku (amended by Permenkominfo 10/2021).
- Byte-identical copy: https://peraturan.bpk.go.id/Download/197017/Nomor%205%20Tahun%202020.pdf
- Issuing-ministry copy: https://jdih.komdigi.go.id/produk_hukum/pratinjau/id/759 (a different
  rendition of the same text, 479,074 bytes, 41 pages).

### Permenkominfo 10/2021: Perubahan atas Permenkominfo 5/2020

- Source URL: https://peraturan.bpk.go.id/Download/197090/Nomor%2010%20Tahun%202021.pdf
- Landing page: https://peraturan.bpk.go.id/Details/203121/permenkominfo-no-10-tahun-2021
- Ditetapkan and diundangkan 21 May 2021. **Effective: 21 May 2021.**
- Status per peraturan.bpk.go.id: Berlaku.
- Issuing-ministry copy: https://jdih.komdigi.go.id/produk_hukum/pratinjau/id/774 (a different
  rendition of the same text, 359,952 bytes, 4 pages).

### UU 27/2022: Pelindungan Data Pribadi (binary not committed)

- Source URL: https://peraturan.go.id/files/Salinan+UU+Nomor+27+Tahun+2022.pdf
- Landing page: https://peraturan.go.id/id/uu-no-27-tahun-2022
- Byte-identical copies: https://peraturan.bpk.go.id/Download/224884/UU%20Nomor%2027%20Tahun%202022.pdf
  and https://jdih.komdigi.go.id/produk_hukum/pratinjau/id/832
- Ditetapkan and diundangkan 17 October 2022. **Effective: 17 October 2022.** Pasal 74 gives
  controllers and processors at most 2 years from promulgation to comply (to 17 October 2024).
- Status per peraturan.bpk.go.id: Berlaku.
- Skipped because every primary copy found is the same 2,977,828-byte file, above the 1000 KB limit.

### PMK 37/2025: PPh collection by electronic-commerce operators (binary not committed)

- Title: Penunjukan Pihak Lain sebagai Pemungut Pajak Penghasilan serta Tata Cara Pemungutan,
  Penyetoran, dan Pelaporan Pajak Penghasilan yang Dipungut oleh Pihak Lain atas Penghasilan yang
  Diterima atau Diperoleh Pedagang Dalam Negeri dengan Mekanisme Perdagangan melalui Sistem Elektronik.
- Source URL: https://peraturan.bpk.go.id/Download/384094/PMK%20Nomor%2037%20Tahun%202025.pdf
- Landing page: https://peraturan.bpk.go.id/Details/322300/pmk-no-37-tahun-2025
- Ditetapkan 11 June 2025; diundangkan 14 July 2025. **Effective: 14 July 2025.**
- Status per peraturan.bpk.go.id: Berlaku.
- Skipped because the only reachable primary copy is 1,621,966 bytes, above the 1000 KB limit.
  jdih.kemenkeu.go.id did not answer over HTTPS on 2026-09-11 (connection timeout from two hosts on
  separate ISPs), so no smaller Ministry of Finance rendition could be checked.

#### Scope note on PMK 37/2025

PMK 37/2025 exists and is PMSE-related, but it governs **income tax (PPh)** collected by electronic
trading operators from domestic merchants, not VAT. The PMSE **VAT** collection rule was
PMK 60/PMK.03/2022 (https://peraturan.bpk.go.id/Details/215498/pmk-no-60pmk032022), which
peraturan.bpk.go.id lists as Tidak Berlaku, revoked by PMK 81/2024
(https://peraturan.bpk.go.id/Details/306614/pmk-no-81-tahun-2024, effective 31 December 2024).
PMK 81/2024 was not fetched: it is outside this lane's list.

## Verify

```bash
cd data/source_documents/t0_regulations
shasum -a 256 pp_71_2019_*.pdf permenkominfo_5_2020_*.pdf permenkominfo_10_2021_*.pdf
pdfinfo permenkominfo_10_2021_perubahan_pse_lingkup_privat.pdf | grep Pages
```
