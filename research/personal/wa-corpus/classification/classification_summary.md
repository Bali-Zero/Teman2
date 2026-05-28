# WhatsApp Chat Classification Summary

Generated UTC: `2026-05-26T11:33:40+00:00`
Input registry: `research/personal/wa-corpus/registry/registry.sqlite`
SQLite classification DB: `research/personal/wa-corpus/classification/chat_classification.sqlite`

## Privacy Mode

- Metadata only.
- No raw message text.
- No message snippets.
- No phone numbers.
- No raw source paths.
- No raw contact names.
- Per-chat references use `file_id`, `path_hash`, and hashed `source_tag` only.

## Scope

- This is a deterministic pre-flight taxonomy, not semantic content analysis.
- Every chat remains review-gated before any content mining.
- The output is intended to prevent personal, family, client, and team chats from being mixed accidentally.

## Global Counts

| Metric                           |  Value |
| -------------------------------- | -----: |
| Classified chat files            |    698 |
| Baseline message-start records   | 105532 |
| Normalized message-start records | 162109 |

## Classification Labels

| Label                             | Files | Baseline starts | Normalized starts | Review-required files |
| --------------------------------- | ----: | --------------: | ----------------: | --------------------: |
| bulk_drive_export_candidate       |   210 |           45136 |             67984 |                   210 |
| mirror_contact_archive_unreviewed |   288 |           14847 |             14847 |                   288 |
| pilot_or_test_archive_candidate   |     1 |              46 |                53 |                     1 |
| private_drive_icloud_candidate    |    10 |           15932 |             45224 |                    10 |
| team_operator_archive_candidate   |   189 |           29571 |             34001 |                   189 |

## Processing Gates

| Gate                                          | Files | Baseline starts | Normalized starts |
| --------------------------------------------- | ----: | --------------: | ----------------: |
| deny_content_mining_until_owner_allowlist     |    10 |           15932 |             45224 |
| local_only_team_analysis_after_owner_approval |   189 |           29571 |             34001 |
| manual_review_before_any_use                  |     1 |              46 |                53 |
| manual_review_before_content_mining           |   498 |           59983 |             82831 |

## Source Cross-Tab

| Source           | Label                             | Files |
| ---------------- | --------------------------------- | ----: |
| 01_wa-mirror-db  | mirror_contact_archive_unreviewed |   288 |
| 02_zip-extracted | bulk_drive_export_candidate       |   210 |
| 02_zip-extracted | pilot_or_test_archive_candidate   |     1 |
| 02_zip-extracted | team_operator_archive_candidate   |   189 |
| 03_drive-icloud  | private_drive_icloud_candidate    |    10 |

## Highest-Volume Review Queue

These rows expose only `file_id`, `path_hash`, and hashed `source_tag`.

| File ID      | Source           | Source tag     | Path hash                  | Label                             | Gate                                          | Baseline starts | Normalized starts | Evidence                                                                                                                            | Warnings                       |
| ------------ | ---------------- | -------------- | -------------------------- | --------------------------------- | --------------------------------------------- | --------------: | ----------------: | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| wa-file-0421 | 02_zip-extracted | tag-080dc51dee | `dca227e5ea9b6def548eb487` | bulk_drive_export_candidate       | manual_review_before_content_mining           |            9779 |             26065 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:largest_by_file_count  | unicode_prefixed_export_starts |
| wa-file-0288 | 01_wa-mirror-db  |                | `20c2bb636b4f388a61011646` | mirror_contact_archive_unreviewed | manual_review_before_content_mining           |            6443 |              6443 | source:wa_mirror_db                                                                                                                 |                                |
| wa-file-0698 | 03_drive-icloud  |                | `71719f6968c17b6f7163a950` | private_drive_icloud_candidate    | deny_content_mining_until_owner_allowlist     |            3854 |             10894 | parser_warnings_present, normalized_count_exceeds_baseline, source:drive_icloud                                                     | unicode_prefixed_export_starts |
| wa-file-0697 | 03_drive-icloud  |                | `0857efe74dd35dfeae05595f` | private_drive_icloud_candidate    | deny_content_mining_until_owner_allowlist     |            3854 |             10894 | parser_warnings_present, normalized_count_exceeds_baseline, source:drive_icloud                                                     | unicode_prefixed_export_starts |
| wa-file-0696 | 03_drive-icloud  |                | `96ad9343015e53b6f04a1196` | private_drive_icloud_candidate    | deny_content_mining_until_owner_allowlist     |            3854 |             10894 | parser_warnings_present, normalized_count_exceeds_baseline, source:drive_icloud                                                     | unicode_prefixed_export_starts |
| wa-file-0693 | 03_drive-icloud  |                | `f2f156c250989462d38a68de` | private_drive_icloud_candidate    | deny_content_mining_until_owner_allowlist     |            3854 |             10894 | parser_warnings_present, normalized_count_exceeds_baseline, source:drive_icloud                                                     | unicode_prefixed_export_starts |
| wa-file-0579 | 02_zip-extracted | tag-f4c6a73c2c | `a48f8f255243c6b2ab8018ef` | team_operator_archive_candidate   | local_only_team_analysis_after_owner_approval |            2757 |              3437 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:operator_sized_archive | unicode_prefixed_export_starts |
| wa-file-0513 | 02_zip-extracted | tag-080dc51dee | `c2e62c2d6f22bbae6da016b7` | bulk_drive_export_candidate       | manual_review_before_content_mining           |            2757 |              3437 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:largest_by_file_count  | unicode_prefixed_export_starts |
| wa-file-0351 | 02_zip-extracted | tag-080dc51dee | `364c14535f2c5542db112e91` | bulk_drive_export_candidate       | manual_review_before_content_mining           |            1418 |              1672 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:largest_by_file_count  | unicode_prefixed_export_starts |
| wa-file-0313 | 02_zip-extracted | tag-f6302850cc | `be2a716e5e04e7f995a247dd` | team_operator_archive_candidate   | local_only_team_analysis_after_owner_approval |            1418 |              1672 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:operator_sized_archive | unicode_prefixed_export_starts |
| wa-file-0382 | 02_zip-extracted | tag-080dc51dee | `7230beed750d1e1331b6c9b0` | bulk_drive_export_candidate       | manual_review_before_content_mining           |            1141 |              1360 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:largest_by_file_count  | unicode_prefixed_export_starts |
| wa-file-0286 | 01_wa-mirror-db  |                | `c6be02ad954ca7ab949ee811` | mirror_contact_archive_unreviewed | manual_review_before_content_mining           |            1110 |              1110 | source:wa_mirror_db                                                                                                                 |                                |
| wa-file-0340 | 02_zip-extracted | tag-080dc51dee | `7a9e21f7677dab976f375b3f` | bulk_drive_export_candidate       | manual_review_before_content_mining           |            1080 |              1325 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:largest_by_file_count  | unicode_prefixed_export_starts |
| wa-file-0305 | 02_zip-extracted | tag-f6302850cc | `684e8f8cc0c6f2d04a77fb2a` | team_operator_archive_candidate   | local_only_team_analysis_after_owner_approval |            1080 |              1325 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:operator_sized_archive | unicode_prefixed_export_starts |
| wa-file-0379 | 02_zip-extracted | tag-080dc51dee | `40e5759729571986749e002c` | bulk_drive_export_candidate       | manual_review_before_content_mining           |             951 |              1057 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:largest_by_file_count  | unicode_prefixed_export_starts |
| wa-file-0371 | 02_zip-extracted | tag-080dc51dee | `6fa6ec4f027f635a9dee5e3c` | bulk_drive_export_candidate       | manual_review_before_content_mining           |             942 |              1082 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:largest_by_file_count  | unicode_prefixed_export_starts |
| wa-file-0628 | 02_zip-extracted | tag-02a8764847 | `ff04892834bb4d469a7d4843` | team_operator_archive_candidate   | local_only_team_analysis_after_owner_approval |             816 |               932 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:operator_sized_archive | unicode_prefixed_export_starts |
| wa-file-0503 | 02_zip-extracted | tag-080dc51dee | `ba6c3016dfd88ede4bdca6bd` | bulk_drive_export_candidate       | manual_review_before_content_mining           |             816 |               932 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:largest_by_file_count  | unicode_prefixed_export_starts |
| wa-file-0285 | 01_wa-mirror-db  |                | `f9fb77cba4fda43105f159a2` | mirror_contact_archive_unreviewed | manual_review_before_content_mining           |             798 |               798 | source:wa_mirror_db                                                                                                                 |                                |
| wa-file-0606 | 02_zip-extracted | tag-02a8764847 | `0b03c9d92d90134afd205d7f` | team_operator_archive_candidate   | local_only_team_analysis_after_owner_approval |             791 |               862 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:operator_sized_archive | unicode_prefixed_export_starts |
| wa-file-0423 | 02_zip-extracted | tag-080dc51dee | `1fcfcc336e9352c92e5b1d0b` | bulk_drive_export_candidate       | manual_review_before_content_mining           |             791 |               862 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:largest_by_file_count  | unicode_prefixed_export_starts |
| wa-file-0627 | 02_zip-extracted | tag-02a8764847 | `8ba602d7515113e11e2a523b` | team_operator_archive_candidate   | local_only_team_analysis_after_owner_approval |             736 |               800 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:operator_sized_archive | unicode_prefixed_export_starts |
| wa-file-0502 | 02_zip-extracted | tag-080dc51dee | `dcec0f67876bae7d38747495` | bulk_drive_export_candidate       | manual_review_before_content_mining           |             736 |               800 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:largest_by_file_count  | unicode_prefixed_export_starts |
| wa-file-0331 | 02_zip-extracted | tag-080dc51dee | `f13ff020f6f9e39e6b92c36b` | bulk_drive_export_candidate       | manual_review_before_content_mining           |             713 |               795 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:largest_by_file_count  | unicode_prefixed_export_starts |
| wa-file-0296 | 02_zip-extracted | tag-f6302850cc | `be67634602d3f34e27a8bf72` | team_operator_archive_candidate   | local_only_team_analysis_after_owner_approval |             713 |               795 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:operator_sized_archive | unicode_prefixed_export_starts |
| wa-file-0332 | 02_zip-extracted | tag-080dc51dee | `380904577825de4b7edb0c1c` | bulk_drive_export_candidate       | manual_review_before_content_mining           |             606 |               667 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:largest_by_file_count  | unicode_prefixed_export_starts |
| wa-file-0297 | 02_zip-extracted | tag-f6302850cc | `529f2f93c8ed8f0181f2a636` | team_operator_archive_candidate   | local_only_team_analysis_after_owner_approval |             606 |               667 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:operator_sized_archive | unicode_prefixed_export_starts |
| wa-file-0553 | 02_zip-extracted | tag-f4c6a73c2c | `0f5da7b1091393f774059748` | team_operator_archive_candidate   | local_only_team_analysis_after_owner_approval |             495 |               549 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:operator_sized_archive | unicode_prefixed_export_starts |
| wa-file-0442 | 02_zip-extracted | tag-080dc51dee | `300db8f444104f286cacf8d7` | bulk_drive_export_candidate       | manual_review_before_content_mining           |             495 |               549 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:largest_by_file_count  | unicode_prefixed_export_starts |
| wa-file-0497 | 02_zip-extracted | tag-080dc51dee | `fe9c0331aaa90b4bfa8a4b70` | bulk_drive_export_candidate       | manual_review_before_content_mining           |             485 |               585 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:largest_by_file_count  | unicode_prefixed_export_starts |
| wa-file-0284 | 01_wa-mirror-db  |                | `ff51f86aa2a2e0178c0c2a65` | mirror_contact_archive_unreviewed | manual_review_before_content_mining           |             479 |               479 | source:wa_mirror_db                                                                                                                 |                                |
| wa-file-0634 | 02_zip-extracted | tag-02a8764847 | `b7e8cbd15b503f6228af7ece` | team_operator_archive_candidate   | local_only_team_analysis_after_owner_approval |             464 |               514 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:operator_sized_archive | unicode_prefixed_export_starts |
| wa-file-0527 | 02_zip-extracted | tag-080dc51dee | `c910efa1aca52cbe97a36398` | bulk_drive_export_candidate       | manual_review_before_content_mining           |             464 |               514 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:largest_by_file_count  | unicode_prefixed_export_starts |
| wa-file-0330 | 02_zip-extracted | tag-080dc51dee | `7a71e7422d0b98178cf17b1a` | bulk_drive_export_candidate       | manual_review_before_content_mining           |             463 |               511 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:largest_by_file_count  | unicode_prefixed_export_starts |
| wa-file-0295 | 02_zip-extracted | tag-f6302850cc | `8be3353cc80ac9dbc4389a78` | team_operator_archive_candidate   | local_only_team_analysis_after_owner_approval |             463 |               511 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:operator_sized_archive | unicode_prefixed_export_starts |
| wa-file-0324 | 02_zip-extracted | tag-080dc51dee | `0ad2ae180a0e4ff1c66ea512` | bulk_drive_export_candidate       | manual_review_before_content_mining           |             461 |               548 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:largest_by_file_count  | unicode_prefixed_export_starts |
| wa-file-0322 | 02_zip-extracted | tag-080dc51dee | `d840066fde85fd086f9d03cb` | bulk_drive_export_candidate       | manual_review_before_content_mining           |             459 |               516 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:largest_by_file_count  | unicode_prefixed_export_starts |
| wa-file-0291 | 02_zip-extracted | tag-f6302850cc | `d795e581f5e9f1a9e94db6b0` | team_operator_archive_candidate   | local_only_team_analysis_after_owner_approval |             459 |               516 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:operator_sized_archive | unicode_prefixed_export_starts |
| wa-file-0574 | 02_zip-extracted | tag-f4c6a73c2c | `4142da5f7a6d2e06d1da2868` | team_operator_archive_candidate   | local_only_team_analysis_after_owner_approval |             457 |               487 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:operator_sized_archive | unicode_prefixed_export_starts |
| wa-file-0501 | 02_zip-extracted | tag-080dc51dee | `170a86c943ce386488a60443` | bulk_drive_export_candidate       | manual_review_before_content_mining           |             457 |               487 | parser_warnings_present, normalized_count_exceeds_baseline, source:zip_extracted, source_tag:hashed, zip_tag:largest_by_file_count  | unicode_prefixed_export_starts |

## Operating Rule

- `deny_content_mining_until_owner_allowlist`: do not inspect message bodies unless the owner creates a local allowlist.
- `local_only_team_analysis_after_owner_approval`: can be analyzed only on Pro after explicit local approval for that source group.
- `manual_review_before_content_mining`: safe for metadata counts only until reviewed.
- `manual_review_before_any_use`: do not use except to decide whether the file belongs in the corpus.

## SQLite Inspection Examples

```sql
SELECT classification_label, files, message_starts, normalized_message_starts, review_required_files
FROM classification_summaries
ORDER BY files DESC;

SELECT processing_gate, files, message_starts
FROM gate_summaries
ORDER BY files DESC;

SELECT file_id, source, source_tag, path_hash, classification_label, processing_gate, message_start_count
FROM classified_chats
WHERE review_required = 1
ORDER BY message_start_count DESC
LIMIT 50;
```
