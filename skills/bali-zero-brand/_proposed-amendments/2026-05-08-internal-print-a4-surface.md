# Proposed Amendment — Internal Print A4 Surface

**Date**: 2026-05-08
**Author**: Antonello Siano (via Claude Opus 4.7 working session)
**Triggering artifact**: `~/Desktop/BaliZero_4Funnel_MASTER.pdf` + `~/Desktop/BaliZero_Subhi_Brief_W2.pdf` (2026-05-08), strategy briefs for funnel-week-2 work, design replicated from `~/Desktop/PBG_Villa_Kutuh_BaliZero_ID.pdf` (2026-04-29).
**Status**: PROPOSED — awaiting Antonello git-commit to merge into `constitution.md`.

---

## Why this amendment

The current `constitution.md` (rev 2026-05-08) governs **Bali Zero carousel social media** (1080×1350 IG portrait). It is silent on other brand surfaces. In practice, two more surfaces have emerged with their own production cadence:

1. **Internal Print A4 documents** — strategy briefs, technical handovers, client case quotes, regulatory primers (e.g. a SIMBG regulatory primer, a client SPT-2025 tax quote, the MASTER funnel strategy, an operational weekly brief). These are PDFs, A4 portrait, dark-mode cover + light-mode interior, 4-12 pages.
2. **Web frontend (mouth)** — `apps/mouth/`. Already has its own design system in `packages/core/styles/bz-tokens.css` (`--bz-base: #0c0c0e`, `--bz-accent: #d4845a`). Different surface, different constraints (light/dark theme switch, accessibility, web type sizes).

Without a surface taxonomy, agents reading the constitution misapply carousel rules to non-carousel work (e.g. "Article 1.1: aspect ratio 1080×1350" fails an A4 PDF; "Article 9.5: statement-bomb closing" doesn't fit a 11-page strategy brief).

This amendment adds:

- **Article 12 — Surfaces** to `constitution.md`, declaring the closed set of recognized surfaces and pointing to per-surface specs.
- A **new file `surfaces/internal-print-a4.md`** with hard rules specific to A4 internal docs.
- A **canonical template** at `surfaces/internal-print-a4/_template.css` + `surfaces/internal-print-a4/_render.py` that any future A4 brief can import (no copy-paste drift).

## Proposed text (to merge into `constitution.md`)

### Article 12 — Surfaces (closed taxonomy)

12.1 **Recognized surfaces** (closed set):

| Surface ID | Format | Spec file | Production tool |
|---|---|---|---|
| `carousel-ig` | 1080×1350 PNG, 7-10 slides | `constitution.md` Art. 1-11 (this file) | wr2-design-architect |
| `internal-print-a4` | A4 portrait PDF, dark cover + light interior | `surfaces/internal-print-a4.md` | manual HTML+CSS via Playwright |
| `web-mouth` | Next.js frontend, theme-switch | `apps/mouth/CLAUDE.md` + `packages/core/styles/bz-tokens.css` | Vercel deploy |
| `email-template` | HTML email, Brevo-rendered | TBD (no spec yet — open backlog) | Brevo `/api/notifications/send-email` |

12.2 **Cross-surface palette** (always required, all 4 surfaces): the tokens in `tokens.json` (`color.bg.antracite`, `color.text.white`, `color.accent.yellow`, `color.status.red`) are mandatory across surfaces. Surfaces MAY add derived tokens (e.g. light-mode body color for `internal-print-a4`) but MUST NOT redefine the core 4.

12.3 **Cross-surface forbidden phrases** (always required, all 4 surfaces): the closed set in `voice/forbidden-phrases.md` applies regardless of surface.

12.4 **Per-surface deviations are explicit, not inferred**: each spec file enumerates its own deviations from the carousel-default Articles 1-11 (e.g. an A4 brief is not 1080×1350; an email template might allow links). Anything NOT explicitly deviating remains bound to the carousel default.

12.5 **Surface inheritance hierarchy**: `constitution.md` Articles 2 (palette), 3 (typography family), 6.3 (concrete numbers), 6.4 (regulatory verbatim), 6.5 (bilingual lexicon untranslated), 6.7 (no emoji), 7 (forbidden phrases), 8 (spelling/accuracy) are **mandatory across all surfaces**. All other articles are surface-specific (carousel-only by default).

## Files to add (also part of this amendment)

```
~/.claude/skills/bali-zero-brand/
├── surfaces/
│   ├── internal-print-a4.md                  ← spec hard rules per A4 PDF
│   ├── internal-print-a4/
│   │   ├── _template.css                     ← canonical CSS, importable
│   │   ├── _render.py                        ← Playwright→PDF helper
│   │   └── example-brief.html                ← skeleton example (cover + 2 interior pages)
```

## Triggering rationale (why now, not later)

The 2026-05-08 funnel-strategy work shipped 2 internal PDFs that:
- Drifted from the constitution palette (used `#d4a23a` instead of `#F4C430`, `#c94545` instead of `#C8102E`, `#2a2d35` instead of `#2C2F38`).
- Used Georgia serif in the logo glyph (Article 3.2 violation).
- Contained "unlock" + "paradigm" forbidden phrases (Article 7 violation).

These were caught by manual brand-cortex audit AFTER the PDFs were already on Desktop. With a documented surface spec + canonical template, future briefs (Subhi Week 3, client case quotes, regulatory primers) inherit the brand by default — no audit needed.

## Approval checklist (Antonello)

- [ ] Read this amendment + `surfaces/internal-print-a4.md`
- [ ] Spot-check: do the 2 PDFs on Desktop now match the spec?
- [ ] Decide: merge to `constitution.md` Article 12 verbatim, or revise?
- [ ] If approved: `git commit -am "feat(brand): Article 12 — surfaces taxonomy + internal-print-a4 spec"` (skill not yet under git → first commit creates the repo)
- [ ] Move this file from `_proposed-amendments/` to `constitution.md` Art. 12 + delete this proposal file
