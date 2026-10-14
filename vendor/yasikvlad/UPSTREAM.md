# yasikvlad workshop skills — vendored copies

## Provenance

Four Claude Code skills from Vlad Yasko's "Упаковка продукта" workshop #4, vendored
byte-identical (every tracked upstream file, nothing added or removed inside each dir).
The loaded skills are the thin pointer files under `.claude/skills/<name>/SKILL.md`;
they read the files here. Vendored 2026-10-14 by the Bali Zero AI Team on behalf of the
Ukr Bali Zero owner (workshop participant).

| Dir | Upstream | Commit SHA | Upstream date | Loaded as |
| --- | --- | --- | --- | --- |
| `client-dna-v2/` | https://github.com/yasikvlad/client-dna-v2 | `6be773ac0c441df8622a388d03c232b1d2a1a126` | 2026-03-05 | `.claude/skills/client-dna/` |
| `hunt-ladder/` | https://github.com/yasikvlad/hunt-ladder | `cf218c49be84515ae1396ed3af7f6b09320aba8a` | 2026-03-12 | `.claude/skills/hunt-ladder/` |
| `hormozi-offer/` | https://github.com/yasikvlad/hormozi-offer | `8bbbab533d5e78b7436aac34bf6172fea44a296f` | 2026-03-13 | `.claude/skills/hormozi-offer/` |
| `tone-of-voice/` | https://github.com/yasikvlad/tone-of-voice | `cbd8d1979f29e1f4b2adab2dccee8c5fef8161fc` | 2026-03-29 | `.claude/skills/tone-of-voice/` |

## License

None of the four upstream repos ships a LICENSE file. They are public GitHub repos the
author distributes to workshop participants; this copy is for internal Bali Zero use only.
Do not redistribute the vendored text outside the company without the author's consent.

## Diff list vs upstream

None — byte-identical. All adaptation (YAML frontmatter for `hunt-ladder`, a SKILL.md for
`hormozi-offer`, pointer bodies) lives in `.claude/skills/<name>/SKILL.md`, not here.

## Refresh

Clone the upstream repo fresh, delete the matching `vendor/yasikvlad/<repo>/` directory,
copy every `git ls-files` entry of the clone back into it (nothing else), then update the
SHA and date row above. Keep this directory byte-identical: adaptations go in
`.claude/skills/<name>/SKILL.md`.
