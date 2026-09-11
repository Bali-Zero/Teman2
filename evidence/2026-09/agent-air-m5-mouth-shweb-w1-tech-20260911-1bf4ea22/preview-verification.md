# W1-SH-TECH — Vercel preview verification (PR #6243)

Measured 2026-09-11 ~12:00–12:10Z by a read-only Sonnet 5 support child of the Dux (Playwright +
Vercel MCP); report returned to the Dux, raw scenario output in `preview-browser-out.json`.
No lead submitted, no message sent, no secret recorded.

## Build — the full `npm run build` production runs

- Deployment `dpl_DnyvbuFFWcEh8oWesLqzBUw5jqxS` (`mouth-5p6zodfmh-nuzantara-2026.vercel.app`),
  state **READY**, branch `agent/air-m5/mouth/shweb-w1-tech-20260911`, commit
  `d5e267c7354e29aa7f805bd382d388f12e2f2a8c`.
- Build log lines:
  - `11:49:22 > LLMS_GENERATE_ARTICLES_ONLY=1 tsx scripts/generate-llms-full.ts && next build --webpack && node scripts/assert-public-login-bundle.mjs`
  - `🚀 Generating AI Master Data files...` → `✅ All AI Master Data files generated successfully.`, with no
    `Generating llms-kbli.txt` before `11:49:24 ▲ Next.js 16.3.4 (webpack)`, so KBLI was skipped.
  - `11:53:30` full route table, including `├ ○ /visa/second-home/studio`.
  - `11:53:30 PUBLIC_LOGIN_BUNDLE_OK: inspected 1 assets; no internal API route prefixes found`
  - `11:53:48 Build Completed in /vercel/output [5m]` → `11:54:30 Deployment completed`.
- The literal `Compiled successfully` string fell outside the captured log windows (the tool caps at about
  59K characters per call). Completion is evidenced by the route table, `Build Completed` and READY.

Every commit after `d5e267c735` on this branch touches only `evidence/**` and `.secrets.baseline`
(no `apps/mouth` path), so this build is the build of the frozen product tree.

## Browser — Studio on the preview (plans loaded through the `#p=` fragment, per `plan-codec.ts`)

| #   | Scenario                              | Band       | Product | Price                   | fontFamily (computed)                                   | fontVariantNumeric | Result |
| --- | ------------------------------------- | ---------- | ------- | ----------------------- | ------------------------------------------------------- | ------------------ | ------ |
| 1   | under 55, deposit USD 130k ready      | strong_fit | E33     | 35.000.000 IDR          | `cormorant, "cormorant Fallback", ui-serif, Georgia, …` | tabular-nums       | PASS   |
| 2   | 60+, deposit USD 50k + income         | strong_fit | E33E    | 45.000.000 IDR          | cormorant stack                                         | tabular-nums       | PASS   |
| 3a  | 60+, income-only USD 3k, abroad       | strong_fit | E33F    | 14.000.000 IDR          | cormorant stack                                         | tabular-nums       | PASS   |
| 3b  | 60+, income-only USD 3k, in Indonesia | strong_fit | E33F    | 16.000.000 IDR          | cormorant stack                                         | tabular-nums       | PASS   |
| 4   | property route                        | edge_case  | none    | no price panel rendered | n/a                                                     | n/a                | PASS   |

- `document.fonts.check('32px cormorant')` → `true` in every scenario.
- Scenario 1, print emulation (`emulateMedia({media:'print'})`): the real price node still computes
  `tabular-nums`; `.custody-map` stays visible (`display: grid`, `visibility: visible`).
- Scenario 1, scenario toggle: flipping to the property route evaluates `edge_case` with no product,
  so `resolveSecondHomePriceKey` abstains and no preview price renders. This is the designed
  behaviour, and it means `{previewPrice}` was not observable in this walk.
- Save/share bar visible. Reloading the same `#p=` URL reproduces the verdict (`strong_fit`).

## Exports served by the preview

- `/llms.txt` freshness block: 5 entries, all dated 2026-09-11, **no duplicated URL**
  (production baseline 2026-09-11T11:12Z listed two URLs twice).
- `/llms-id.txt`: `# Last updated: 2026-09-11`, **800** `TITLE:` records
  (production baseline: `# Last updated: 2026-08-11`, 785 records).
