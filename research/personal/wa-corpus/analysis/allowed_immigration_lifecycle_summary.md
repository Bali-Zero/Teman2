# Allowed Immigration Lifecycle Summary

- Generated UTC: `2026-05-26T14:12:12+00:00`
- Input DBs: `allowed_messages.local.sqlite`, `allowed_candidates.local.sqlite`, `allowed_signal_hits.local.sqlite`
- Local lifecycle SQLite artifact: `allowed_immigration_lifecycle.local.sqlite`
- Privacy boundary: tracked markdown is aggregate-only and contains no raw message text, snippets, extracted values, phone numbers, emails, raw contact names, or raw source paths.
- Classification is deterministic local regex plus local signal/candidate codes; it is not legal advice and not an LLM interpretation.

## Overview

| Metric                        | Value |
| ----------------------------- | ----- |
| Messages read                 | 20169 |
| Messages with lifecycle stage | 7335  |
| Stage evidence hits           | 21909 |
| Skipped system events         | 34    |
| Feature-only orphan messages  | 0     |

## Stage Totals

| stage_code               | stage_label              | hit_count | message_count | file_count |
| ------------------------ | ------------------------ | --------- | ------------- | ---------- |
| application_submission   | application/submission   | 8791      | 3958          | 31         |
| identity_passport        | identity/passport        | 6536      | 2192          | 31         |
| lead_intake              | lead/intake              | 1577      | 1577          | 30         |
| extension_renewal_expiry | extension/renewal/expiry | 969       | 969           | 31         |
| sponsor_company          | sponsor/company          | 1926      | 668           | 30         |
| problem_escalation       | problem/escalation       | 1226      | 521           | 31         |
| approval_issuance        | approval/issuance        | 511       | 511           | 31         |
| appointment_biometric    | appointment/biometric    | 373       | 373           | 31         |

## Stage x Month

| stage_code             | stage_label            | month   | hit_count | message_count | file_count |
| ---------------------- | ---------------------- | ------- | --------- | ------------- | ---------- |
| application_submission | application/submission | 2026-01 | 841       | 368           | 22         |
| application_submission | application/submission | 2025-09 | 752       | 341           | 19         |
| application_submission | application/submission | 2026-03 | 788       | 336           | 23         |
| application_submission | application/submission | 2025-10 | 668       | 305           | 24         |
| application_submission | application/submission | 2025-04 | 530       | 268           | 12         |
| application_submission | application/submission | 2025-12 | 501       | 226           | 21         |
| identity_passport      | identity/passport      | 2026-01 | 653       | 219           | 19         |
| application_submission | application/submission | 2025-07 | 470       | 218           | 16         |
| application_submission | application/submission | 2025-08 | 465       | 217           | 17         |
| application_submission | application/submission | 2026-02 | 477       | 215           | 20         |
| application_submission | application/submission | 2025-05 | 414       | 184           | 15         |
| application_submission | application/submission | 2026-04 | 400       | 184           | 24         |
| application_submission | application/submission | 2025-06 | 393       | 183           | 13         |
| identity_passport      | identity/passport      | 2026-03 | 492       | 164           | 21         |
| application_submission | application/submission | 2025-11 | 357       | 163           | 16         |
| application_submission | application/submission | 2026-05 | 341       | 160           | 20         |
| identity_passport      | identity/passport      | 2025-09 | 469       | 157           | 16         |
| lead_intake            | lead/intake            | 2026-01 | 143       | 143           | 22         |
| application_submission | application/submission | 2024-11 | 328       | 139           | 7          |
| identity_passport      | identity/passport      | 2025-04 | 410       | 138           | 12         |
| identity_passport      | identity/passport      | 2025-07 | 408       | 136           | 15         |
| lead_intake            | lead/intake            | 2026-03 | 127       | 127           | 20         |
| identity_passport      | identity/passport      | 2025-12 | 370       | 124           | 17         |
| identity_passport      | identity/passport      | 2025-10 | 369       | 123           | 17         |
| identity_passport      | identity/passport      | 2026-02 | 352       | 118           | 16         |

_Showing 25 of 211 rows._

## Stage x Source Tag

| stage_code               | stage_label              | source_tag     | hit_count | message_count | file_count |
| ------------------------ | ------------------------ | -------------- | --------- | ------------- | ---------- |
| application_submission   | application/submission   | tag-f6302850cc | 3356      | 1484          | 10         |
| application_submission   | application/submission   | tag-f4c6a73c2c | 2868      | 1336          | 10         |
| application_submission   | application/submission   | tag-02a8764847 | 2567      | 1138          | 11         |
| identity_passport        | identity/passport        | tag-f6302850cc | 2819      | 945           | 10         |
| identity_passport        | identity/passport        | tag-f4c6a73c2c | 2491      | 835           | 10         |
| lead_intake              | lead/intake              | tag-f6302850cc | 607       | 607           | 10         |
| lead_intake              | lead/intake              | tag-f4c6a73c2c | 574       | 574           | 10         |
| identity_passport        | identity/passport        | tag-02a8764847 | 1226      | 412           | 11         |
| lead_intake              | lead/intake              | tag-02a8764847 | 396       | 396           | 10         |
| extension_renewal_expiry | extension/renewal/expiry | tag-f6302850cc | 394       | 394           | 10         |
| extension_renewal_expiry | extension/renewal/expiry | tag-f4c6a73c2c | 360       | 360           | 10         |
| sponsor_company          | sponsor/company          | tag-f6302850cc | 836       | 284           | 10         |
| extension_renewal_expiry | extension/renewal/expiry | tag-02a8764847 | 215       | 215           | 11         |
| approval_issuance        | approval/issuance        | tag-f6302850cc | 212       | 212           | 10         |
| sponsor_company          | sponsor/company          | tag-f4c6a73c2c | 619       | 211           | 9          |
| problem_escalation       | problem/escalation       | tag-f4c6a73c2c | 477       | 197           | 10         |
| approval_issuance        | approval/issuance        | tag-02a8764847 | 190       | 190           | 11         |
| problem_escalation       | problem/escalation       | tag-02a8764847 | 398       | 177           | 11         |
| sponsor_company          | sponsor/company          | tag-02a8764847 | 471       | 173           | 11         |
| problem_escalation       | problem/escalation       | tag-f6302850cc | 351       | 147           | 10         |
| appointment_biometric    | appointment/biometric    | tag-f6302850cc | 139       | 139           | 10         |
| appointment_biometric    | appointment/biometric    | tag-f4c6a73c2c | 137       | 137           | 10         |
| approval_issuance        | approval/issuance        | tag-f4c6a73c2c | 109       | 109           | 10         |
| appointment_biometric    | appointment/biometric    | tag-02a8764847 | 97        | 97            | 11         |

## Stage Co-Occurrence

| stage_code               | stage_label              | paired_stage_code        | paired_stage_label       | message_count | file_count |
| ------------------------ | ------------------------ | ------------------------ | ------------------------ | ------------- | ---------- |
| application_submission   | application/submission   | extension_renewal_expiry | extension/renewal/expiry | 654           | 31         |
| application_submission   | application/submission   | lead_intake              | lead/intake              | 604           | 30         |
| application_submission   | application/submission   | identity_passport        | identity/passport        | 596           | 31         |
| application_submission   | application/submission   | approval_issuance        | approval/issuance        | 401           | 31         |
| application_submission   | application/submission   | sponsor_company          | sponsor/company          | 312           | 30         |
| application_submission   | application/submission   | appointment_biometric    | appointment/biometric    | 308           | 31         |
| application_submission   | application/submission   | problem_escalation       | problem/escalation       | 291           | 31         |
| extension_renewal_expiry | extension/renewal/expiry | identity_passport        | identity/passport        | 254           | 28         |
| identity_passport        | identity/passport        | lead_intake              | lead/intake              | 227           | 30         |
| approval_issuance        | approval/issuance        | identity_passport        | identity/passport        | 200           | 30         |
| appointment_biometric    | appointment/biometric    | identity_passport        | identity/passport        | 196           | 30         |
| approval_issuance        | approval/issuance        | extension_renewal_expiry | extension/renewal/expiry | 170           | 27         |
| extension_renewal_expiry | extension/renewal/expiry | lead_intake              | lead/intake              | 163           | 27         |
| extension_renewal_expiry | extension/renewal/expiry | problem_escalation       | problem/escalation       | 156           | 30         |
| identity_passport        | identity/passport        | sponsor_company          | sponsor/company          | 149           | 27         |
| lead_intake              | lead/intake              | sponsor_company          | sponsor/company          | 127           | 26         |
| appointment_biometric    | appointment/biometric    | extension_renewal_expiry | extension/renewal/expiry | 116           | 27         |
| appointment_biometric    | appointment/biometric    | lead_intake              | lead/intake              | 116           | 27         |
| identity_passport        | identity/passport        | problem_escalation       | problem/escalation       | 116           | 29         |
| lead_intake              | lead/intake              | problem_escalation       | problem/escalation       | 113           | 29         |
| appointment_biometric    | appointment/biometric    | approval_issuance        | approval/issuance        | 107           | 28         |
| approval_issuance        | approval/issuance        | lead_intake              | lead/intake              | 101           | 30         |
| approval_issuance        | approval/issuance        | sponsor_company          | sponsor/company          | 94            | 26         |
| extension_renewal_expiry | extension/renewal/expiry | sponsor_company          | sponsor/company          | 92            | 26         |
| approval_issuance        | approval/issuance        | problem_escalation       | problem/escalation       | 69            | 27         |

_Showing 25 of 28 rows._

## Primary Stage Transitions

| from_stage_code          | from_stage_label         | to_stage_code            | to_stage_label           | transition_count | file_count |
| ------------------------ | ------------------------ | ------------------------ | ------------------------ | ---------------- | ---------- |
| application_submission   | application/submission   | application_submission   | application/submission   | 1496             | 31         |
| identity_passport        | identity/passport        | identity_passport        | identity/passport        | 1068             | 31         |
| application_submission   | application/submission   | identity_passport        | identity/passport        | 636              | 31         |
| identity_passport        | identity/passport        | application_submission   | application/submission   | 610              | 31         |
| lead_intake              | lead/intake              | application_submission   | application/submission   | 356              | 30         |
| application_submission   | application/submission   | lead_intake              | lead/intake              | 346              | 30         |
| lead_intake              | lead/intake              | identity_passport        | identity/passport        | 199              | 30         |
| identity_passport        | identity/passport        | lead_intake              | lead/intake              | 194              | 29         |
| sponsor_company          | sponsor/company          | sponsor_company          | sponsor/company          | 177              | 16         |
| application_submission   | application/submission   | problem_escalation       | problem/escalation       | 168              | 31         |
| problem_escalation       | problem/escalation       | application_submission   | application/submission   | 168              | 29         |
| sponsor_company          | sponsor/company          | application_submission   | application/submission   | 157              | 22         |
| lead_intake              | lead/intake              | lead_intake              | lead/intake              | 152              | 26         |
| application_submission   | application/submission   | sponsor_company          | sponsor/company          | 140              | 20         |
| application_submission   | application/submission   | extension_renewal_expiry | extension/renewal/expiry | 122              | 25         |
| extension_renewal_expiry | extension/renewal/expiry | application_submission   | application/submission   | 116              | 26         |
| identity_passport        | identity/passport        | sponsor_company          | sponsor/company          | 90               | 18         |
| identity_passport        | identity/passport        | problem_escalation       | problem/escalation       | 78               | 25         |
| problem_escalation       | problem/escalation       | identity_passport        | identity/passport        | 78               | 26         |
| sponsor_company          | sponsor/company          | identity_passport        | identity/passport        | 77               | 13         |
| identity_passport        | identity/passport        | extension_renewal_expiry | extension/renewal/expiry | 69               | 22         |
| extension_renewal_expiry | extension/renewal/expiry | identity_passport        | identity/passport        | 60               | 20         |
| extension_renewal_expiry | extension/renewal/expiry | extension_renewal_expiry | extension/renewal/expiry | 57               | 18         |
| application_submission   | application/submission   | approval_issuance        | approval/issuance        | 51               | 18         |
| problem_escalation       | problem/escalation       | lead_intake              | lead/intake              | 51               | 24         |

_Showing 25 of 64 rows._

## Evidence Code Totals

| stage_code               | stage_label              | evidence_code                         | hit_count | message_count |
| ------------------------ | ------------------------ | ------------------------------------- | --------- | ------------- |
| application_submission   | application/submission   | signal:immigration                    | 3171      | 3171          |
| application_submission   | application/submission   | candidate_category:visa_case          | 3163      | 3163          |
| application_submission   | application/submission   | body_keyword:application_submission   | 2457      | 2457          |
| identity_passport        | identity/passport        | body_keyword:identity_passport        | 2190      | 2190          |
| identity_passport        | identity/passport        | candidate_category:identity_document  | 2172      | 2172          |
| identity_passport        | identity/passport        | signal:identity_document              | 2170      | 2170          |
| lead_intake              | lead/intake              | body_keyword:lead_intake              | 1577      | 1577          |
| extension_renewal_expiry | extension/renewal/expiry | body_keyword:extension_renewal_expiry | 969       | 969           |
| sponsor_company          | sponsor/company          | body_keyword:sponsor_company          | 668       | 668           |
| sponsor_company          | sponsor/company          | candidate_category:company_case       | 629       | 629           |
| sponsor_company          | sponsor/company          | signal:company_corporate              | 629       | 629           |
| approval_issuance        | approval/issuance        | body_keyword:approval_issuance        | 511       | 511           |
| problem_escalation       | problem/escalation       | body_keyword:problem_escalation       | 414       | 414           |
| problem_escalation       | problem/escalation       | candidate_category:urgency_case       | 406       | 406           |
| problem_escalation       | problem/escalation       | signal:urgency_risk                   | 406       | 406           |
| appointment_biometric    | appointment/biometric    | body_keyword:appointment_biometric    | 373       | 373           |
| identity_passport        | identity/passport        | candidate_evidence:passport_like_hash | 4         | 4             |

## Caveats

- One message can map to multiple lifecycle stages.
- System-event messages are excluded from lifecycle classification.
- `application_submission` intentionally includes broad immigration/visa signals, so it is a high-recall stage rather than a final case status.
