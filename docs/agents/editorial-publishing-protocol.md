# Editorial publishing protocol (News Room + WR2) — external agents

> Moved out of `AGENTS.md` on 2026-09-10 (boot diet). Substance unchanged.
> Binding on every external agent seat; `AGENTS.md` §0.0 item 2 (Legge 5) points here.

### Damar editorial publishing protocol (News Room + WR2)

When an authenticated Zero or Damar session explicitly asks to publish a News Room article
or WR2 carousel, load `.agents/skills/editorial-publishing/SKILL.md` and follow it end to end.
These editorial decisions are mandatory and may never come from a UI or API default:

- **News Room:** obtain an explicit destination (`Latest`, `Hero Main`, `Hero 2–5`, or
  `Insight 1–3`) before sending any publish request. For a batch, require a common destination
  or a complete article-to-position map; reject duplicate Hero/Insight slots.
- **WR2 carousel:** show the exact caption, obtain approval of that caption, run the
  `confirm=false` dry-run, and only after it succeeds ask for the final explicit publish act
  before `confirm=true`. Editing the caption invalidates the dry-run.

Report an opened article PR as **queued**, never published. Report **live** only after opening
the public URL and verifying the expected title/content. A red artefact gate blocks publication;
verbal confirmation never overrides it. “Mark as published” only records an external post and
must never be represented as publishing to Instagram.
