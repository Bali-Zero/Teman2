# News Room "Next Steps" grammar — the spec that was missing (v1, 2026-09-25)

> **Why this file exists.** The News Room converter (`convert_staging_to_enriched_article` in
> `apps/backend-rag/backend/app/routers/intel_scraper.py`) turns a draft's `## Next Steps` body into
> `next_steps = {expat, investor, general}`. Its fix went through four PRs (#7285, #7322, #7331, #7336) and
> three final gates: #7322 BLOCKED (substring audience match), #7331 PASSED and is live, and #7336 — the follow-up
> that cured the edge cases #7331's gates listed — was BLOCKED because one of its cures (bullet
> stripping) regressed the labelled path. That is a fix-of-a-fix past depth 1. The Builder Contract
> (rule 1) applies: _"if the correction is itself wrong, the surface is under-specified, so write the
> spec."_ Every case below was run by a gate against real code; none is hypothetical.
>
> #7336 is CLOSED, branch alive as the starting point: `agent/air-m5/backend-rag/newsroom-fidelity-edges`.

## What is live today (after #7331)

- An audience is named only by a whole **label line**: optional `##`–`####`, optional `**`, optional
  `For `, `Expat(s)` or `Investor(s)`, optional `:`/`**`, nothing else on the line. It runs until the
  next label line or `##`–`####` heading.
- No label line anywhere → every item goes to one neutral `general` group (rendered as
  "Recommended Actions"). Never split, never filled with "Review the article for specific actions".
- Unmapped `##` sections are preserved as `extra_sections`; a draft with no `## Facts` heading does
  not print them twice.
- Proven inside the prod `nuzantara-rag` machine on 2026-09-25 (synthetic draft).

## Invariants (every implementation must hold all of them)

1. **Never lose text.** Every line of the body that contains a word character ends up in exactly one
   rendered item — in `expat`, `investor` or `general` — unless it is a label line or a placeholder
   (invariant 4). No silent drop, no truncation.
2. **Never invent.** No item text that is not in the draft; no audience the draft did not name.
3. **Never render markup as content.** A horizontal rule (`---`, `***`, `___`), a bare bullet, or an
   empty item never becomes an item.
4. **Placeholders are not steps.** An item whose whole text is `TBD`, `TBA`, `N/A`, `NA`, `none` or
   `todo` (case-insensitive, trailing `.` ignored) is dropped; a sentence that merely starts with one
   of those words ("None of the above applies.") is kept.
5. **Keep inline formatting.** Only a leading list marker is removed; `**Deadline**:` keeps its `**`.

## Decisions this spec makes (each was ambiguous in code)

| #   | Question                                                                                              | Decision                                                                                                                                                                               |
| --- | ----------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Is a lone `Expats` / `Investors` line a label?                                                        | Yes (it is a whole label line). A step that happens to be exactly that word is not a real case.                                                                                        |
| D2  | Are inline labels (`For Expats: renew your KITAS`, `- **For Expats:** renew…`) labels?                | No. They stay one intact item in `general`. Splitting inline labels is a separate, optional feature.                                                                                   |
| D3  | Text before the first label, or after a non-audience heading (`### For Everyone`), when labels exist? | Goes to `general` (invariant 1). Today it is dropped — the behaviour inherited from pre-#7331 main.                                                                                    |
| D4  | A neutral paragraph after a labelled group, with no heading between?                                  | Stays with that group (a blank line does not end a group); only a label line or heading does.                                                                                          |
| D5  | Numbered lists (`1.`, `2.`)?                                                                          | Each number starts an item, like `-` and `*`. Today the whole list is one item.                                                                                                        |
| D6  | How many items per group?                                                                             | No silent cap. If a cap is kept for layout, the overflow is appended to the last item or reported — never dropped.                                                                     |
| D7  | Bullet without a space (`-Check`)?                                                                    | Not a list marker (markdown agrees); `-5% tax` keeps its sign.                                                                                                                         |
| D8  | Heading grammar                                                                                       | One grammar for Summary / Facts / Bali Zero Take / Next Steps: optional trailing `:`, `\r?\n` line ends. The classifier that decides "known heading" and the extractors must share it. |

## The case table (run it as one table-driven test)

Input = the `## Next Steps` body (LF unless noted). Output = `{expat, investor, general}`.

| Case | Input                                                                                                                      | Required output                                                        | Status                                    |
| ---- | -------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ----------------------------------------- |
| E1   | `- Investors should file LKPM…` / `- An expatriate employee must hold a KITAS.` / `- Expats: check your visa expiry date.` | all 3 verbatim in general                                              | live (#7331)                              |
| E4   | `#### For Expats` / `- Renew…` / `#### For Investors` / `- File LKPM…`                                                     | expat=[Renew…], investor=[File LKPM…]                                  | live                                      |
| E5   | same with `#####`                                                                                                          | same                                                                   | #7336 (closed)                            |
| E12  | CRLF `**For Expats:**` + `- Ask your investor sponsor for RPTKA.`                                                          | stays under expat                                                      | live                                      |
| E3   | `- Confirm the scope first.` / `Investors` / `- File the annual SPT.`                                                      | general=[Confirm…], investor=[File…] (D1 + D3)                         | open                                      |
| E6   | `For Expats: renew your KITAS` / `For Investors: file the LKPM report`                                                     | general = the two lines, intact (D2)                                   | live                                      |
| E7   | `- **For Expats:** renew your KITAS early.`                                                                                | general=[`**For Expats:** renew your KITAS early.`]                    | #7336 (closed)                            |
| E9   | `All readers should read the regulation first.` then `### For Expats` …                                                    | general=[All readers…] (D3)                                            | open                                      |
| E10  | labels, then `### For Everyone` / `- Keep copies of all filings.`                                                          | general=[Keep copies…] (D3)                                            | open                                      |
| E11  | `### For Expats` / `- Renew your KITAS early.` / blank / `All readers: keep copies.`                                       | expat=[Renew…, All readers…] as two items (D4)                         | open                                      |
| E15  | `*For Expats:*` / `- Renew…`                                                                                               | expat=[Renew…] (italic label is a label line)                          | open                                      |
| E16  | `### For Expats & Investors` / `- Keep copies.`                                                                            | general=[Keep copies.] (heading is not an item)                        | open                                      |
| E19  | 12 neutral bullets                                                                                                         | all 12 (D6)                                                            | open (live caps at 5)                     |
| E20  | `- File SPT` / `- Pay PBB.`                                                                                                | both kept                                                              | #7336 (closed)                            |
| E21  | `1. File SPT.` / `2. Pay PBB.`                                                                                             | two items (D5)                                                         | open                                      |
| E22  | `- **Deadline**: file the SPT by 31 March.`                                                                                | `**Deadline**: file the SPT by 31 March.`                              | #7336 (closed)                            |
| E23  | heading `## Next Steps:` (and CRLF `## Bali Zero Take`)                                                                    | body extracted (D8)                                                    | #7336 (closed)                            |
| E24  | `TBD`                                                                                                                      | no items; no Next Steps section in the MDX                             | #7336 (closed)                            |
| G1   | `**For Expats:**` / `- Check your visa status` / blank / `---`                                                             | expat=[Check your visa status] — the rule is not an item (invariant 3) | **#7336 regressed this** (rendered `---`) |
| G2   | `### For Investors` / `- Review investment plan` / blank / `---` then `## Sources`                                         | investor=[Review investment plan]                                      | **#7336 regressed this**                  |
| G3   | `None of the above applies.`                                                                                               | kept                                                                   | holds everywhere                          |

## How to build the next PR

Start from `origin/main`, write this table as one parametrized test first (it must fail on every
`open` row and on G1/G2), then implement a single line-based parser for the whole body — label
lines, headings, list markers, rules and placeholders classified per line — instead of layering
regex fixes. The #7336 branch holds working cures for E5/E7/E20/E22/E23/E24; G1/G2 need the
invariant-3 filter on the labelled path too. Published MDX already carries items truncated by the
pre-#7331 substring bug (e.g. `riate …` in
`apps/mouth/src/content/articles/tax-legal/indonesias-tax-holiday-trap-gmt-threatens-to-hollow-out-pph-incentives.mdx`);
repairing them is a separate content pass.
