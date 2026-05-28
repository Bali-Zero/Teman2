# WhatsApp Document Lifecycle Gap Summary

Generated UTC: `2026-05-26T14:18:04+00:00`
Input event SQLite artifact: `allowed_domain_events.local.sqlite`
Local gap SQLite artifact: `allowed_document_lifecycle_gaps.local.sqlite`

## Privacy Mode

- This tracked summary contains no raw message text.
- This tracked summary contains no message snippets.
- This tracked summary contains no phone numbers or emails.
- This tracked summary contains no raw source paths or raw extracted values.
- This analyzer reads only the derived domain event index, not the raw parsed-message DB.

## Counts

| Metric                                      | Value |
| ------------------------------------------- | ----: |
| Event rows read                             | 36398 |
| Lifecycle messages                          |  7335 |
| Document messages                           |  6037 |
| Messages with lifecycle and document events |  5398 |

## Lifecycle Stage Document Coverage

| Stage                    | Lifecycle messages | With document | Without document | Coverage ratio |
| ------------------------ | -----------------: | ------------: | ---------------: | -------------: |
| application_submission   |               3958 |          3381 |              577 |          0.854 |
| identity_passport        |               2192 |          2174 |               18 |          0.992 |
| lead_intake              |               1577 |           707 |              870 |          0.448 |
| extension_renewal_expiry |                969 |           691 |              278 |          0.713 |
| sponsor_company          |                668 |           654 |               14 |          0.979 |
| approval_issuance        |                511 |           412 |               99 |          0.806 |
| appointment_biometric    |                373 |           324 |               49 |          0.869 |
| problem_escalation       |                521 |           297 |              224 |          0.570 |

## Document Coverage Against Lifecycle

| Document code                   | Document messages | With lifecycle | Without lifecycle | Coverage ratio |
| ------------------------------- | ----------------: | -------------: | ----------------: | -------------: |
| visa_immigration_document       |              3370 |           3260 |               110 |          0.967 |
| passport_identity_document      |              2172 |           2172 |                 0 |          1.000 |
| photo_biometric                 |              1692 |           1690 |                 2 |          0.999 |
| company_document                |               630 |            629 |                 1 |          0.998 |
| tax_document                    |               813 |            460 |               353 |          0.566 |
| payment_proof                   |               585 |            390 |               195 |          0.667 |
| property_document               |               229 |            104 |               125 |          0.454 |
| translation_legalization_notary |                69 |             36 |                33 |          0.522 |

## Top Stage x Document Co-Occurrence

| Stage                    | Document code              | Messages | Files |
| ------------------------ | -------------------------- | -------: | ----: |
| application_submission   | visa_immigration_document  |     3183 |    31 |
| identity_passport        | passport_identity_document |     2172 |    31 |
| identity_passport        | photo_biometric            |     1686 |    31 |
| extension_renewal_expiry | visa_immigration_document  |      638 |    31 |
| sponsor_company          | company_document           |      629 |    30 |
| application_submission   | passport_identity_document |      594 |    31 |
| identity_passport        | visa_immigration_document  |      573 |    31 |
| lead_intake              | visa_immigration_document  |      553 |    30 |
| application_submission   | photo_biometric            |      393 |    31 |
| approval_issuance        | visa_immigration_document  |      379 |    31 |
| application_submission   | tax_document               |      352 |    31 |
| application_submission   | payment_proof              |      338 |    31 |
| appointment_biometric    | visa_immigration_document  |      301 |    31 |
| application_submission   | company_document           |      286 |    30 |
| sponsor_company          | visa_immigration_document  |      272 |    29 |
| extension_renewal_expiry | passport_identity_document |      254 |    28 |
| problem_escalation       | visa_immigration_document  |      247 |    31 |
| lead_intake              | passport_identity_document |      227 |    30 |
| identity_passport        | payment_proof              |      222 |    31 |
| approval_issuance        | passport_identity_document |      200 |    30 |
| appointment_biometric    | passport_identity_document |      195 |    30 |
| extension_renewal_expiry | photo_biometric            |      192 |    26 |
| identity_passport        | tax_document               |      189 |    29 |
| appointment_biometric    | photo_biometric            |      177 |    30 |
| lead_intake              | photo_biometric            |      176 |    30 |

## Top Month x Stage Gaps

| Month   | Stage                    | Lifecycle messages | With document | Without document |
| ------- | ------------------------ | -----------------: | ------------: | ---------------: |
| 2025-04 | application_submission   |                268 |           199 |               69 |
| 2026-01 | lead_intake              |                143 |            74 |               69 |
| 2026-03 | lead_intake              |                127 |            58 |               69 |
| 2026-02 | lead_intake              |                103 |            40 |               63 |
| 2025-09 | lead_intake              |                118 |            58 |               60 |
| 2025-09 | application_submission   |                341 |           284 |               57 |
| 2026-05 | lead_intake              |                101 |            47 |               54 |
| 2025-10 | lead_intake              |                 95 |            43 |               52 |
| 2025-04 | lead_intake              |                 77 |            26 |               51 |
| 2025-07 | lead_intake              |                 88 |            37 |               51 |
| 2026-04 | lead_intake              |                 79 |            30 |               49 |
| 2025-06 | lead_intake              |                 81 |            33 |               48 |
| 2025-08 | application_submission   |                217 |           171 |               46 |
| 2025-08 | lead_intake              |                 80 |            35 |               45 |
| 2025-11 | lead_intake              |                 80 |            35 |               45 |
| 2025-10 | application_submission   |                305 |           263 |               42 |
| 2026-01 | application_submission   |                368 |           326 |               42 |
| 2025-12 | lead_intake              |                 80 |            39 |               41 |
| 2025-05 | lead_intake              |                 68 |            28 |               40 |
| 2026-02 | application_submission   |                215 |           179 |               36 |
| 2025-07 | application_submission   |                218 |           183 |               35 |
| 2026-03 | application_submission   |                336 |           302 |               34 |
| 2025-06 | extension_renewal_expiry |                 74 |            41 |               33 |
| 2026-01 | extension_renewal_expiry |                109 |            76 |               33 |
| 2026-05 | application_submission   |                160 |           127 |               33 |

## Operational Reading

- High `without_document_message_count` does not prove a missing document; it marks lifecycle-stage messages with no same-message document event.
- Use the ignored local SQLite for anonymous review queues before changing operational process.
