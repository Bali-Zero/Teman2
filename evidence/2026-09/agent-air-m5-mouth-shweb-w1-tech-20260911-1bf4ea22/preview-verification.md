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

Every commit after `40646c54be` (D5: `ARTICLES_ONLY` precedence + export tests) on this branch touches only `evidence/**`
and `.secrets.baseline` (no `apps/mouth` path); the preview verified in §Round 2 below is the build of that product tree,
which equals the gated head `4ec63cdbe7` (corrected in the discharge PR: refuter round 3 F2, the earlier sentence still named `d5e267c735`).

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

## Round 2 — preview of the cured product tree (POST refuter round 2, F2 and F3)

Measured 2026-09-11T13:48Z by the Dux directly (Playwright from the worktree's `node_modules`, Vercel
share cookie, token never written). Raw output in `preview-browser-toggle-out.json`.

- Deployment `dpl_Dxv7wxRwHBVgLJET6V1vjWA7Tawk` (`mouth-41fxy12oi-nuzantara-2026.vercel.app`), state
  **READY** (GitHub check `Vercel` pass at 13:47Z), commit `40646c54becfb09568195b340862d098806c0a38`, the
  commit that carries the FULL_ONLY guard. Commits after it touch only `evidence/**`.
- `{previewPrice}` in ScenarioToggle, reached by loading a property-route plan that also carries the
  deposit answers and opening "What if I took the other route?". The main result stays `edge_case` with no
  price. The deposit preview renders a priced product:

| #   | Plan (`#p=`)                            | Preview product | Preview price  | fontFamily (computed) | fontVariantNumeric | Result |
| --- | --------------------------------------- | --------------- | -------------- | --------------------- | ------------------ | ------ |
| t1  | under 55, property + capital ready_130k | E33             | 35.000.000 IDR | cormorant stack       | tabular-nums       | PASS   |
| t2  | 60+, property + income_only_3k, abroad  | E33F            | 14.000.000 IDR | cormorant stack       | tabular-nums       | PASS   |

Both prices equal the main-result prices recorded above for the same products (S1, S3a).
`document.fonts.check('32px cormorant')` → `true`.

- Exports served by this deployment: `/llms-id.txt` http 200, `# Last updated: 2026-09-11`, 800 `TITLE:`
  records; `/llms-full.txt` http 200, 2559 records; `/llms.txt` freshness 5 entries, 0 duplicated URLs.
- F3 context: `vercel env ls` on project `mouth` lists 44 environment rows and none named `LLMS_*`, so no
  deployed environment sets the legacy flag today. The guard ships anyway.
