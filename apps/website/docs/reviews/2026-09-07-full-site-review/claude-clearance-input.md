# Independent visual follow-up — homepage CTA overlap (VR-1)

You are the independent reviewer of a narrowly corrected local website candidate. Read only; do not write files, run commands, launch browsers, use networks, or request additional permissions. Product CSS was authored by a separate worker; the executor of this review did not author it. Decide from the actual files listed below. This is local visual acceptance only, never production approval.

The first full-site review returned FAIL because lifted tool cards covered the homepage "Explore all services →" link at desktop and tablet widths. It identified `.tools` margin-top -38px (small screens -16px) with z-index 2. The corrected candidate is a single CSS change: bottom padding for `.services-intro` compensates for that lift, while its direct text link gets inline-flex alignment and min-height 44px. Review whether VR-1 is actually resolved and whether this change introduces a visible defect in the adjacent hero/intro/tool-card area. Do not broaden this into a second full-site review.

The original review also noted a portal disclaimer inset, Ari's mobile arrow wrap, and the Tax card's art alignment. These are explicitly deferred minor/cosmetic observations; no fixes to them are claimed. Do not treat their unchanged existence as a new failure of this narrow correction.

Exact worktree root: `/Users/nuzantara/nuzantara/.worktrees/infra-website-r19-pro`.

Read these four new, actual viewport PNGs (all are 1000px high and deliberately scrolled to center the intro; partial hero text beneath the sticky header at the top edge is the chosen scroll position, not a changed hero layout):

1. `output/playwright/website-r19-full-site/clearance-fix/home-services-clearance-1440.png`
2. `output/playwright/website-r19-full-site/clearance-fix/home-services-clearance-768.png`
3. `output/playwright/website-r19-full-site/clearance-fix/home-services-clearance-390.png`
4. `output/playwright/website-r19-full-site/clearance-fix/home-services-clearance-360.png`

Then read:

- `output/playwright/website-r19-full-site/clearance-fix/clearance-metrics.json` — actual geometry, nine sampled elementFromPoint hits per width, and real click destinations. Independently assess the scope of what it proves.
- `output/playwright/website-r19-full-site/clearance-fix/capture-clearance.js` — how those observations and PNGs were produced.
- `apps/website/src/app/globals.css` — only the relevant ranges around lines 6430–6470 (correction), 2832–2847 (desktop tool lift), and 3077–3095 (mobile tool lift). Do not read all ~6500 lines.

Use absolute paths by prepending the exact root. Seven unique files are sufficient; do not read unrelated files or the full 24-view sweep. That sweep is being completed separately and is outside this follow-up's claim.

Return concise English Markdown starting with `**PASS**` or `**FAIL**`. State whether VR-1 is closed, evidence from all four widths, any new blocker in immediate surroundings, and the limits (static PNG/source/recorded browser evidence, no browser execution by you, no production approval). Distinguish actual screenshot observations from facts supplied by the metrics. If essential evidence is missing, fail with the precise gap; do not infer a pass from the prior test/build status.
