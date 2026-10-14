# humanizer-ru — vendored skill

## Provenance

| Field                | Value                                                                                      |
| -------------------- | ------------------------------------------------------------------------------------------ |
| Upstream source      | not stated; third-party community skill, uploaded by the owner as `SKILL.md`               |
| Upstream version     | `2.1.0` (from the SKILL.md frontmatter)                                                    |
| Vendored date        | 2026-10-14                                                                                 |
| Vendored by          | Bali Zero (owner request, cloud session)                                                   |
| License              | none declared in the file                                                                  |
| Reason for vendoring | Russian copy editor (removes officialese, AI vocabulary, filler); loaded through a symlink |

## Layout

- `SKILL.md` — byte-identical to the uploaded file.
- `.claude/skills/humanizer-ru` — relative symlink to `vendor/humanizer-ru`.

## Why `vendor/`

Same reasons as `vendor/marketing-skills/UPSTREAM.md`: unmodified third-party content, excluded from the harness size term and from Prettier.
