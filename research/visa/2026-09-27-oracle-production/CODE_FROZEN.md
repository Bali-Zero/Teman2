---
adversarial_review: exempt-mission-process-record # ORACLE-PROD-20260927 process record (spec, progress, freeze or round log) for a code release, not a research deliverable; the reviewed object is the code, whose council and final-gate verdicts are in evidence/2026-09/agent-air-m5-mouth-oracle-prod-0927-d995492b/
---

# CODE_FROZEN — ORACLE-PROD-20260927 production bytes (Dux, 2026-09-27T13:22:12Z)

Source freeze acknowledged by the single writer (Sonnet 5 implementer): last source edit 2026-09-27T13:21Z;
no further edits unless a running check fails (then it stops and reports). Any later byte change invalidates
this file and requires a new freeze.

- Scope: every changed/added file under `apps/mouth` (git status, harness copies `e2e/*.local.spec.ts` and
  generated `public/llms*` excluded) — 35 files: 8 tracked modified (+2582 / -315), 27 untracked
  (new components/tests/`atlas-scenes.ts` and the 19 approved WebPs under `public/static/visa-oracle/atlas/`).
- Nothing outside `apps/mouth` besides this mandate's `research/` directory. No backend, package, lockfile,
  API, `engine-adapter.ts`/`engine-adapter.test.ts` or evaluation file changed.
- Byte equality (same script, same list): M5 worktree `c1ad334aab` (base c1ad334aab) and Mini
  mirror `/Users/nuzantara/nuzantara/.worktrees/mouth-oracle-prod-0927-mini` (origin/main d4a3b2da05):
  **aggregate sha256 `33de0847f621fcf50e4ed735563e94db9580f67e8b306908cb54c2bc55e3b983` on both — IDENTICAL.**
- Upstream drift: origin/main = f36e245af2 at freeze; `git diff c1ad334aab origin/main` touches
  nothing under `apps/mouth/src/app/(visa-oracle)` or `public/static/visa-oracle` (#7504 still OPEN). The
  candidate commit will be placed on fresh origin/main and re-verified on Mini at that exact SHA.

## Checks (host = Mini unless stated)
| Check | State |
|---|---|
| Full mouth PR e2e gate (coherent single server) | coordinator receipt gate-e2e3.log: 134 pass, 1 skip (existing opt-in BZ_VISUAL_GALLERY), 0 fail |
| Atlas harness (qaEN2) | 34 passed (coordinator-observed); final run by writer IN PROGRESS |
| vitest / tsc / webpack build on frozen bytes | writer final run IN PROGRESS (true exit codes required) |
| Exact-SHA verification (canonical `npm run build`, vitest, tsc, harness, gate) | PENDING — after candidate commit on fresh main |

## FREEZE v2 — written 2026-09-27T13:25Z, clock-corrected (an earlier draft carried an unread future stamp); supersedes v1 bytes above

The pre-commit hook (`.husky/pre-commit` prettier check) rejected 13 staged TS/TSX files for formatting.
`npx prettier --write` was applied to the 35-file set (formatting only; 14 files changed bytes, all CSS hunks
inside the atlas section ≥ line 1675). The frozen candidate is now a COMMIT:

- **Code candidate SHA `f38cbf469d7e6de53689b1584bd287afc48ad547`** on fresh origin/main `f36e245af2`
  (rebased, no conflicts), branch `agent/air-m5/mouth/oracle-prod-0927`, not pushed.
  `git diff --stat f36e245af2 f38cbf46`: 35 files, +5055 / -319; same 35-path list as v1.
- v2 aggregate sha256 (same method, committed bytes): **`af611423607a76e130098faab20c553819d9ced6cbd9cbe4a7f9fa728ee184b9`**.
- Behavioural equivalence to v1 is claimed only for formatting; exact-SHA verification on Mini (canonical
  `npm run build` webpack, vitest, tsc, atlas harness, full mouth e2e gate) will run on these bytes and
  is the binding receipt. A later evidence/docs commit touches only `evidence/` and `research/`.

## File hashes v2 (sha256, path)
```
da5d4222183e81630c9aece35862308f76694e45e035081ba85537fd1e3aa4cf  apps/mouth/public/static/visa-oracle/atlas/business.webp
35bafa890f0a93c4568d4508d36e444d37412d8d6e53ff28f8555597c1023750  apps/mouth/public/static/visa-oracle/atlas/confluence.webp
4fb92606133f5b2fa9cc518675a5f00d57afb40a08c31ce4ba15283bcff9b747  apps/mouth/public/static/visa-oracle/atlas/diaspora.webp
ba57e9142c34fbb90db4162643546a073dc15587c0940f7f6bce2594e7ba9fea  apps/mouth/public/static/visa-oracle/atlas/family.webp
271243b2b5d324e1a8c7f263c23d377b5a640f919ef14e63655ace88f30ab304  apps/mouth/public/static/visa-oracle/atlas/identity.webp
7d9d57c72e24e65164a38fd6706f57600f8a02c3c78e5c5d370d4b6baa06ca7e  apps/mouth/public/static/visa-oracle/atlas/indonesia.webp
58dc290fdcae0b7ba507a55c2fbbeda80cf3401bc9f658ac122199fee0a3f654  apps/mouth/public/static/visa-oracle/atlas/invest.webp
1630c84db01e494a847659e581cbf3be502a2936bf9f26abf07cba467a823a02  apps/mouth/public/static/visa-oracle/atlas/logo.webp
d2f873748586488ea1cc40fe414d25949b721b17baf574826ec0ec254a1452dc  apps/mouth/public/static/visa-oracle/atlas/other.webp
7002bdb36ad6235e413fe91ad3d1c3104f78285540f47c1dddd417158b8e94fb  apps/mouth/public/static/visa-oracle/atlas/permit-depth.webp
b6453e6b4cc8447d319ed7fb8bc08c2847363a354af086017c0f6283eaea8203  apps/mouth/public/static/visa-oracle/atlas/permit-paper.webp
41687fa11541bc4709e6321e955be8becd17655070f6c79aab92d42c2468f5fc  apps/mouth/public/static/visa-oracle/atlas/remote.webp
1fee5d3991ec5cc43a0833c38a100a70311dff20b619aa7bd2f5cc0aa0bb29b1  apps/mouth/public/static/visa-oracle/atlas/retirement.webp
f0674eaf08721bd13c3ac56d48191aa240ccbb514a652cdd960b5f3d3beef8d5  apps/mouth/public/static/visa-oracle/atlas/second_home.webp
e19bfd50ab15b618436ca81a49e3dc9f63311ec47245035d484ddae80f21ca63  apps/mouth/public/static/visa-oracle/atlas/study.webp
244fddf4344b4c28588d5022485c52c8309e756b962bc686c106c4eb2c55da24  apps/mouth/public/static/visa-oracle/atlas/tourism.webp
79a1bdb25ed29124a9e15ed044df787c07e88979f343842945007851ad254321  apps/mouth/public/static/visa-oracle/atlas/watershed.webp
67fbb47317671abb4526423c3f0f9ac3b99f63a20defdd432d7873396f555790  apps/mouth/public/static/visa-oracle/atlas/work.webp
49ab66791526526839ee35fdac1474aa9de92c4b936c7005311adfcee494b777  apps/mouth/public/static/visa-oracle/atlas/world.webp
46e0648eadfeb30c3a2b3f6838450c13ebb2afb73ff6af55bb3aae7b15a7051b  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/AtlasRoute.test.tsx
748d5e759676cc3075964d3d16e4d019be47f928ad5e44acad50e226e7a09e0c  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/AtlasRoute.tsx
9c0ce6a33d401218215f3458f94788b51328ff0728e52e55482994e22f0a8409  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OracleScenery.test.tsx
53a3d5b9101eba29af695559bc107412929fbdb23ecab2cab23adbdf782d0782  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OracleScenery.tsx
a61f60aaa158014e25307952398655d9b2ddfbe6175efb8bb16ef2a5f13bfc74  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OracleShell.atlas.test.tsx
90dd49b5fee5be61fca994dc599319f572f26aaf891137914aa377ad9fc16d94  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OracleShell.tsx
407f132bed0a1af2e95e12f6bed30b0ae20dbda688cc182fa7cb93cdeeaaba58  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OutcomeSheet.test.tsx
17278a6b273a95b6df55630eb90e5e325b0fbe81efac6fb7bafdafc72cdb37e2  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OutcomeSheet.tsx
f5f697e40672bef2991862414caa2f288c6f60eee516d972626a699fa1aedf04  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/QuestionScreen.atlas.test.tsx
0a650ef79c7cebede7220713bc0bc0cb1e181822c762049da8e454880956fe10  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/QuestionScreen.tsx
b9baf62dc6b5d16daea7a575a7fb60b2bde26a758b5fa0f56bda20327c42e808  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/VerdictReveal.test.tsx
bbd7ef48ab8f199a09fde2795fd764a0104c4eddce4fb70b4c51f8ab9c7f93f2  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/WhyWeAsk.tsx
7c61105a053eb02c761938e80350ee89d4bf2d8cd2063204b2793678dd922023  apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/atlas-scenes.test.ts
4726cc57354a79fbb224d48c141c0659d4dcabcdfa22af775223c0fbae1f763a  apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/atlas-scenes.ts
cf8eb787fee12a444c43cf609cdef37ab051a848136daf115531c96e0db841cf  apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/i18n.ts
5a6bc982835c2db0efbe811bcc55c14c157c3ec5b49dcae3114eb0266cfee42a  apps/mouth/src/app/(visa-oracle)/visa-oracle/oracle.css
```

<details><summary>v1 hashes (superseded)</summary>

 (sha256, path)
```
da5d4222183e81630c9aece35862308f76694e45e035081ba85537fd1e3aa4cf  apps/mouth/public/static/visa-oracle/atlas/business.webp
35bafa890f0a93c4568d4508d36e444d37412d8d6e53ff28f8555597c1023750  apps/mouth/public/static/visa-oracle/atlas/confluence.webp
4fb92606133f5b2fa9cc518675a5f00d57afb40a08c31ce4ba15283bcff9b747  apps/mouth/public/static/visa-oracle/atlas/diaspora.webp
ba57e9142c34fbb90db4162643546a073dc15587c0940f7f6bce2594e7ba9fea  apps/mouth/public/static/visa-oracle/atlas/family.webp
271243b2b5d324e1a8c7f263c23d377b5a640f919ef14e63655ace88f30ab304  apps/mouth/public/static/visa-oracle/atlas/identity.webp
7d9d57c72e24e65164a38fd6706f57600f8a02c3c78e5c5d370d4b6baa06ca7e  apps/mouth/public/static/visa-oracle/atlas/indonesia.webp
58dc290fdcae0b7ba507a55c2fbbeda80cf3401bc9f658ac122199fee0a3f654  apps/mouth/public/static/visa-oracle/atlas/invest.webp
1630c84db01e494a847659e581cbf3be502a2936bf9f26abf07cba467a823a02  apps/mouth/public/static/visa-oracle/atlas/logo.webp
d2f873748586488ea1cc40fe414d25949b721b17baf574826ec0ec254a1452dc  apps/mouth/public/static/visa-oracle/atlas/other.webp
7002bdb36ad6235e413fe91ad3d1c3104f78285540f47c1dddd417158b8e94fb  apps/mouth/public/static/visa-oracle/atlas/permit-depth.webp
b6453e6b4cc8447d319ed7fb8bc08c2847363a354af086017c0f6283eaea8203  apps/mouth/public/static/visa-oracle/atlas/permit-paper.webp
41687fa11541bc4709e6321e955be8becd17655070f6c79aab92d42c2468f5fc  apps/mouth/public/static/visa-oracle/atlas/remote.webp
1fee5d3991ec5cc43a0833c38a100a70311dff20b619aa7bd2f5cc0aa0bb29b1  apps/mouth/public/static/visa-oracle/atlas/retirement.webp
f0674eaf08721bd13c3ac56d48191aa240ccbb514a652cdd960b5f3d3beef8d5  apps/mouth/public/static/visa-oracle/atlas/second_home.webp
e19bfd50ab15b618436ca81a49e3dc9f63311ec47245035d484ddae80f21ca63  apps/mouth/public/static/visa-oracle/atlas/study.webp
244fddf4344b4c28588d5022485c52c8309e756b962bc686c106c4eb2c55da24  apps/mouth/public/static/visa-oracle/atlas/tourism.webp
79a1bdb25ed29124a9e15ed044df787c07e88979f343842945007851ad254321  apps/mouth/public/static/visa-oracle/atlas/watershed.webp
67fbb47317671abb4526423c3f0f9ac3b99f63a20defdd432d7873396f555790  apps/mouth/public/static/visa-oracle/atlas/work.webp
49ab66791526526839ee35fdac1474aa9de92c4b936c7005311adfcee494b777  apps/mouth/public/static/visa-oracle/atlas/world.webp
fd5c92e8ed9478856f22992af055acf0405ad3ef87127c4ecf148bba60203817  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/AtlasRoute.test.tsx
f896df925cc9ad4447d6875817c612bfe621acbf3d48b51ba5004f432f4b26b3  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/AtlasRoute.tsx
d6d246b8f22efb464abb5bd968b12185dfb5cf1a495c72ac576abf34f1e7abf6  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OracleScenery.test.tsx
7de03473d858fd9d3bd7007c1338581ab9373136cd91990bde6476ed14205a20  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OracleScenery.tsx
76df255fe31e319f730285d21c30c4a348feae74e2692cf47ec73f737de57567  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OracleShell.atlas.test.tsx
2cb6e903c6e91eba67489b1f4eb2bdb85f35d6bb9fdf04d97d9554abc364a4eb  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OracleShell.tsx
4e33bccd2fc5e157c31be784cd094592d54dffb3ff51fda361bea72ac7bec31a  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OutcomeSheet.test.tsx
9adef39d8cc06333106b865bc5ae31531d32057d10151ffe1e76235da5f43f5c  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OutcomeSheet.tsx
81462e5cdd2cf5512077a17c38122716c8ec7c6ffa5bee83445440b2bb00230f  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/QuestionScreen.atlas.test.tsx
99efd6f424ba77c66169445060cc05f914f057105735c7cb7464c37206e4615f  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/QuestionScreen.tsx
347fc374970f49cf90757caca2aec5b551e4ef227448f40b9fc19749c246e0eb  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/VerdictReveal.test.tsx
bbd7ef48ab8f199a09fde2795fd764a0104c4eddce4fb70b4c51f8ab9c7f93f2  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/WhyWeAsk.tsx
cf8122ab1d1dc9a047ea73dff2ffb422b3c8bc4420f2ffb4efeaa5924b03b681  apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/atlas-scenes.test.ts
bdf66a50ce64e56f67b83a466bf9d879040b3c7f1d98df9bc9d509224c06611e  apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/atlas-scenes.ts
cf8eb787fee12a444c43cf609cdef37ab051a848136daf115531c96e0db841cf  apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/i18n.ts
8cb8b8dd0392bb60abc0bcb51fc98dd0d7ef4c42d534d87d52a0d9e601a4fc69  apps/mouth/src/app/(visa-oracle)/visa-oracle/oracle.css
```

</details>

## FREEZE v3 (delta) — written 2026-09-27T14:55:46Z by the successor Dux; supersedes v2 as the release candidate

The fresh final gate returned BLOCK on docs candidate `3710a230` (three findings, `DELTA-ROUND.md`). One Sonnet 5
writer fixed them as one finite delta; the Dux graded it and committed it. v1/v2 above stay as history.

- **Code candidate SHA `f7c9d7ee954eb0824db587ab73646c09538f8f45`** — parent `3710a230` (docs-only), base origin/main `f36e245af2`,
  prior code `f38cbf46`. Branch `agent/air-m5/mouth/oracle-prod-0927`, not pushed.
- Delta vs `3710a230`: 5 files, +257 / −12, per-file sha256:
- `apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OracleShell.atlas.test.tsx` `d3eb55f70f1bc14f8c7b8c8ae1b2f6f308ab785cbf076d5998f91794e8cfb296`
- `apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OracleShell.tsx` `033e3445acbf4a67337c97264d082a22a78d470366b4ffceeffd2d7f4162cfc9`
- `apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OutcomeSheet.test.tsx` `78ec5d86cf203e6fe6227ef1e26af84120357dae2f1164657589932c9be0a982`
- `apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OutcomeSheet.tsx` `bf396292877cfceadb5b745173f9f76473f197a5b4b3c7397ed9f50c2d306054`
- `apps/mouth/src/app/(visa-oracle)/visa-oracle/oracle.css` `173eb249b7dcf5f37da9afb3f696ec36ef0eee88c6b5bf26634ae31a4ef1cad1`
- Full `apps/` diff vs base: 35 files (same 35 paths as v2), aggregate sha256
  **`017e6f9dd4adeb63f8cc62fa934f310db4a306fc4fa281341dbf6bd976d6499c`** (same method; it reproduces
  `af611423…` when run on `f38cbf46`).
- Committed bytes equal the writer's final bytes on M5 and in the Mini writer mirror (sha256 prefixes checked).
  Pre-commit hook (tsc, prettier, off-limits) passed without rewriting any file.
- Machine-readable record: `/tmp/oracle-prod-0927-DELTA_FROZEN.json` (M5).

<details><summary>v3 per-file sha256 (35 files, committed bytes of f7c9d7ee95)</summary>

```
da5d4222183e81630c9aece35862308f76694e45e035081ba85537fd1e3aa4cf  apps/mouth/public/static/visa-oracle/atlas/business.webp
35bafa890f0a93c4568d4508d36e444d37412d8d6e53ff28f8555597c1023750  apps/mouth/public/static/visa-oracle/atlas/confluence.webp
4fb92606133f5b2fa9cc518675a5f00d57afb40a08c31ce4ba15283bcff9b747  apps/mouth/public/static/visa-oracle/atlas/diaspora.webp
ba57e9142c34fbb90db4162643546a073dc15587c0940f7f6bce2594e7ba9fea  apps/mouth/public/static/visa-oracle/atlas/family.webp
271243b2b5d324e1a8c7f263c23d377b5a640f919ef14e63655ace88f30ab304  apps/mouth/public/static/visa-oracle/atlas/identity.webp
7d9d57c72e24e65164a38fd6706f57600f8a02c3c78e5c5d370d4b6baa06ca7e  apps/mouth/public/static/visa-oracle/atlas/indonesia.webp
58dc290fdcae0b7ba507a55c2fbbeda80cf3401bc9f658ac122199fee0a3f654  apps/mouth/public/static/visa-oracle/atlas/invest.webp
1630c84db01e494a847659e581cbf3be502a2936bf9f26abf07cba467a823a02  apps/mouth/public/static/visa-oracle/atlas/logo.webp
d2f873748586488ea1cc40fe414d25949b721b17baf574826ec0ec254a1452dc  apps/mouth/public/static/visa-oracle/atlas/other.webp
7002bdb36ad6235e413fe91ad3d1c3104f78285540f47c1dddd417158b8e94fb  apps/mouth/public/static/visa-oracle/atlas/permit-depth.webp
b6453e6b4cc8447d319ed7fb8bc08c2847363a354af086017c0f6283eaea8203  apps/mouth/public/static/visa-oracle/atlas/permit-paper.webp
41687fa11541bc4709e6321e955be8becd17655070f6c79aab92d42c2468f5fc  apps/mouth/public/static/visa-oracle/atlas/remote.webp
1fee5d3991ec5cc43a0833c38a100a70311dff20b619aa7bd2f5cc0aa0bb29b1  apps/mouth/public/static/visa-oracle/atlas/retirement.webp
f0674eaf08721bd13c3ac56d48191aa240ccbb514a652cdd960b5f3d3beef8d5  apps/mouth/public/static/visa-oracle/atlas/second_home.webp
e19bfd50ab15b618436ca81a49e3dc9f63311ec47245035d484ddae80f21ca63  apps/mouth/public/static/visa-oracle/atlas/study.webp
244fddf4344b4c28588d5022485c52c8309e756b962bc686c106c4eb2c55da24  apps/mouth/public/static/visa-oracle/atlas/tourism.webp
79a1bdb25ed29124a9e15ed044df787c07e88979f343842945007851ad254321  apps/mouth/public/static/visa-oracle/atlas/watershed.webp
67fbb47317671abb4526423c3f0f9ac3b99f63a20defdd432d7873396f555790  apps/mouth/public/static/visa-oracle/atlas/work.webp
49ab66791526526839ee35fdac1474aa9de92c4b936c7005311adfcee494b777  apps/mouth/public/static/visa-oracle/atlas/world.webp
46e0648eadfeb30c3a2b3f6838450c13ebb2afb73ff6af55bb3aae7b15a7051b  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/AtlasRoute.test.tsx
748d5e759676cc3075964d3d16e4d019be47f928ad5e44acad50e226e7a09e0c  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/AtlasRoute.tsx
9c0ce6a33d401218215f3458f94788b51328ff0728e52e55482994e22f0a8409  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OracleScenery.test.tsx
53a3d5b9101eba29af695559bc107412929fbdb23ecab2cab23adbdf782d0782  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OracleScenery.tsx
d3eb55f70f1bc14f8c7b8c8ae1b2f6f308ab785cbf076d5998f91794e8cfb296  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OracleShell.atlas.test.tsx
033e3445acbf4a67337c97264d082a22a78d470366b4ffceeffd2d7f4162cfc9  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OracleShell.tsx
78ec5d86cf203e6fe6227ef1e26af84120357dae2f1164657589932c9be0a982  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OutcomeSheet.test.tsx
bf396292877cfceadb5b745173f9f76473f197a5b4b3c7397ed9f50c2d306054  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/OutcomeSheet.tsx
f5f697e40672bef2991862414caa2f288c6f60eee516d972626a699fa1aedf04  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/QuestionScreen.atlas.test.tsx
0a650ef79c7cebede7220713bc0bc0cb1e181822c762049da8e454880956fe10  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/QuestionScreen.tsx
b9baf62dc6b5d16daea7a575a7fb60b2bde26a758b5fa0f56bda20327c42e808  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/VerdictReveal.test.tsx
bbd7ef48ab8f199a09fde2795fd764a0104c4eddce4fb70b4c51f8ab9c7f93f2  apps/mouth/src/app/(visa-oracle)/visa-oracle/_components/WhyWeAsk.tsx
7c61105a053eb02c761938e80350ee89d4bf2d8cd2063204b2793678dd922023  apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/atlas-scenes.test.ts
4726cc57354a79fbb224d48c141c0659d4dcabcdfa22af775223c0fbae1f763a  apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/atlas-scenes.ts
cf8eb787fee12a444c43cf609cdef37ab051a848136daf115531c96e0db841cf  apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/i18n.ts
173eb249b7dcf5f37da9afb3f696ec36ef0eee88c6b5bf26634ae31a4ef1cad1  apps/mouth/src/app/(visa-oracle)/visa-oracle/oracle.css
```

</details>
