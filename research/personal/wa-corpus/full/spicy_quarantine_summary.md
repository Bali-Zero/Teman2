# WhatsApp Spicy Conversation Quarantine Summary

Generated UTC: `2026-05-26T18:29:18+00:00`
Input full corpus DB: `full_messages.local.sqlite`
Local quarantine DB: `spicy_quarantine.local.sqlite`
Private quarantine TSV: `spicy_quarantine.local.tsv`
Private usable TSV: `usable_after_spicy_quarantine.local.tsv`

## Privacy Mode

- This tracked summary contains no raw message text.
- This tracked summary contains no message snippets.
- This tracked summary contains no phone numbers or emails.
- This tracked summary contains no raw source paths or contact names.
- Private TSV and SQLite artifacts are ignored by git and stay local-only.

## Policy

- Only conversations with explicit spicy keyword evidence are set aside.
- Romantic/affection hints alone are not quarantined.
- Quarantine is a conservative routing step, not a final claim about the conversation.
- Non-quarantined conversations can feed local CRM/ops/KB mining.

## Counts

| Metric               |  Value |
| -------------------- | -----: |
| Files scanned        |    699 |
| Quarantined files    |      3 |
| Usable files         |    696 |
| Quarantined messages |   1632 |
| Usable messages      | 160530 |
| Total keyword hits   |    234 |

## Hit Strengths

| Strength | Hits |
| -------- | ---: |
| soft     |  231 |
| hard     |    3 |

## Quarantine Sources

| Source           | Files |
| ---------------- | ----: |
| 02_zip-extracted |     2 |
| 01_wa-mirror-db  |     1 |

## Generic Hit Codes

| Code               | Hits |
| ------------------ | ---: |
| romantic_love_en   |  167 |
| romantic_affection |   57 |
| romantic_love_it   |    7 |
| porn_content       |    2 |
| nude_content       |    1 |

## Next Local Step

Use `usable_after_spicy_quarantine.local.tsv` as the file-level include list for full-corpus local mining.
