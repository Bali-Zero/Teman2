# marketing-skills — vendored skill bundle

## Provenance

| Field                | Value                                                                                                                                                                  |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Upstream source      | https://github.com/yasikvlad/marketing-skills                                                                                                                          |
| Upstream branch      | `main`                                                                                                                                                                 |
| Upstream commit SHA  | `356bda9c6dd529e8336c09a55ba8301220024c37`                                                                                                                             |
| Vendored date        | 2026-10-14                                                                                                                                                             |
| Vendored by          | Bali Zero (owner request, cloud session)                                                                                                                               |
| License              | none declared upstream at the vendored commit                                                                                                                          |
| Reason for vendoring | 34 marketing skills (copywriting, CRO, SEO, ads, content, pricing, email) loaded by Claude Code through `.claude/skills/<name>` symlinks; kept byte-identical upstream |

## Layout

- `skills/<name>/` — byte-identical copies of upstream `skills/<name>/` (SKILL.md, `references/`, `evals/`).
- `README.md` — upstream README, unchanged.
- `.claude/skills/<name>` — relative symlink to `vendor/marketing-skills/skills/<name>`, the same shape the repo already uses for `.claude/skills/<corner>` → `.agents/skills/<corner>`.

## Diff list vs upstream

- `skills/notebooklm/` is NOT vendored: it ships Python browser automation (`patchright`) with its own venv and `.gitignore`, and the repo already has NotebookLM tooling (`nb-curator`). Nothing else is changed, added or removed.

## Why `vendor/` and not `.claude/skills/` directly

- `scripts/evidence_pack_lint.py` excludes `vendor/` path segments from the harness size term: an unmodified third-party tree inflates churn without inflating review burden (the same reason `vendor/evoskill` is excluded).
- `.prettierignore` lists this tree as vendored upstream, so Prettier never rewrites upstream bytes.
- CodeQL already ignores `vendor/`.

## Refresh policy

Re-clone upstream `main`, diff `skills/` against this tree, update the commit SHA and date above. Keep `notebooklm` out unless its Python dependencies are separately authorized.
