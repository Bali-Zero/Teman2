# WhatsApp Allowlist Document Requirement Summary

Generated UTC: `2026-05-26T14:12:13+00:00`
Input raw SQLite artifact: `allowed_messages.local.sqlite`
Input candidate SQLite artifact: `allowed_candidates.local.sqlite`
Local requirement SQLite artifact: `allowed_document_requirements.local.sqlite`

## Privacy Mode

- This tracked summary contains no raw message text.
- This tracked summary contains no message snippets.
- This tracked summary contains no phone numbers or emails.
- This tracked summary contains no raw source paths.
- This tracked summary contains no raw contact names.
- This tracked summary contains no raw extracted document values.
- The ignored local SQLite stores hashes, message indexes, timestamps, and category counters only.

## Scope

- Extracted only from messages parsed out of `content_allowlist.local.jsonl`.
- Denylist and holdlist files were not opened.
- Detection is deterministic regex plus existing hashed candidate context, not LLM interpretation.
- Categories are aggregate routing signals, not legal or client-level conclusions.

## Counts

| Metric                                     | Value |
| ------------------------------------------ | ----: |
| Messages scanned                           | 20169 |
| Candidate rows read                        | 18925 |
| Messages with document requirement signals |  6037 |
| Messages with explicit requirement context |  1531 |
| Requirement hit rows                       | 14489 |
| Distinct requirement categories            |     8 |
| Distinct hashed extracted values           |   137 |

## Requirement Categories

| Requirement category            | Hit rows | Messages |
| ------------------------------- | -------: | -------: |
| visa_immigration_document       |     6536 |     3370 |
| passport_identity_document      |     2922 |     2172 |
| photo_biometric                 |     1692 |     1692 |
| payment_proof                   |     1356 |      585 |
| tax_document                    |      861 |      813 |
| company_document                |      818 |      630 |
| property_document               |      235 |      229 |
| translation_legalization_notary |       69 |       69 |

## Evidence Codes

| Evidence code                           | Hit rows | Messages |
| --------------------------------------- | -------: | -------: |
| visa_immigration_keyword                |     3370 |     3370 |
| candidate_visa_case                     |     3166 |     3166 |
| candidate_identity_document             |     2174 |     2172 |
| photo_biometric_keyword                 |     1692 |     1692 |
| candidate_tax_payment                   |      778 |      778 |
| passport_identity_keyword               |      744 |      744 |
| candidate_company_case                  |      629 |      629 |
| money_like_value_hash                   |      541 |      319 |
| candidate_money_reference               |      541 |      319 |
| payment_proof_keyword                   |      274 |      274 |
| company_document_keyword                |      166 |      166 |
| candidate_property_case                 |      146 |      146 |
| property_document_keyword               |       89 |       89 |
| tax_document_keyword                    |       82 |       82 |
| translation_legalization_notary_keyword |       69 |       69 |
| company_registration_like_value_hash    |       23 |       22 |
| passport_like_value_hash                |        4 |        4 |
| tax_id_like_value_hash                  |        1 |        1 |

## Context Codes

| Context code                 | Hit rows | Messages |
| ---------------------------- | -------: | -------: |
| candidate_context            |     7434 |     5802 |
| document_mention_context     |     4339 |     3949 |
| explicit_requirement_context |     2716 |     1531 |

## Top Month Buckets

| Month   | Requirement category       | Hit rows | Messages |
| ------- | -------------------------- | -------: | -------: |
| 2026-01 | visa_immigration_document  |      639 |      327 |
| 2026-03 | visa_immigration_document  |      580 |      294 |
| 2025-09 | visa_immigration_document  |      553 |      293 |
| 2025-10 | visa_immigration_document  |      511 |      263 |
| 2025-12 | visa_immigration_document  |      394 |      205 |
| 2026-02 | visa_immigration_document  |      354 |      183 |
| 2025-07 | visa_immigration_document  |      351 |      182 |
| 2025-04 | visa_immigration_document  |      347 |      178 |
| 2025-08 | visa_immigration_document  |      333 |      172 |
| 2026-04 | visa_immigration_document  |      309 |      162 |
| 2025-05 | visa_immigration_document  |      308 |      160 |
| 2025-06 | visa_immigration_document  |      294 |      151 |
| 2025-11 | visa_immigration_document  |      284 |      148 |
| 2026-01 | passport_identity_document |      273 |      217 |
| 2024-11 | visa_immigration_document  |      260 |      133 |
| 2026-05 | visa_immigration_document  |      248 |      126 |
| 2025-09 | passport_identity_document |      230 |      156 |
| 2026-03 | passport_identity_document |      222 |      164 |
| 2026-01 | payment_proof              |      194 |       65 |
| 2026-01 | photo_biometric            |      194 |      194 |

## Top Requirement Co-Occurrences

| Requirement A              | Requirement B                   | Messages |
| -------------------------- | ------------------------------- | -------: |
| passport_identity_document | photo_biometric                 |     1686 |
| passport_identity_document | visa_immigration_document       |      572 |
| photo_biometric            | visa_immigration_document       |      396 |
| payment_proof              | tax_document                    |      376 |
| payment_proof              | visa_immigration_document       |      272 |
| company_document           | visa_immigration_document       |      248 |
| tax_document               | visa_immigration_document       |      243 |
| passport_identity_document | payment_proof                   |      222 |
| payment_proof              | photo_biometric                 |      199 |
| passport_identity_document | tax_document                    |      189 |
| company_document           | passport_identity_document      |      146 |
| photo_biometric            | tax_document                    |      136 |
| company_document           | tax_document                    |      111 |
| company_document           | photo_biometric                 |      107 |
| company_document           | payment_proof                   |       97 |
| property_document          | translation_legalization_notary |       50 |
| property_document          | visa_immigration_document       |       49 |
| company_document           | property_document               |       39 |
| passport_identity_document | property_document               |       35 |
| payment_proof              | property_document               |       24 |

## Operational Reading

- Use the ignored SQLite for local queueing by `requirement_code`, `evidence_code`, and month.
- Resolve hashed values only inside local owner-review tools.
- Treat high `candidate_context` volume as inherited signal breadth from the prior candidate extractor.
