## Council review — GARUDA staff contract types → generated OpenAPI types + CI freshness gate

Scope honored: I have no tools; everything below is static reasoning over the supplied diff and source snapshots only. Nothing here is runtime proof.

---

### (1) Findings ordered by severity

**No statically provable defects found.** The following are the checks I ran mentally against the diff, with the specific points that could have broken and did not (within supplied context):

1. **Optional/null field handling — sound.**
   - `StaffPracticeView` (`garuda-voa.generated.d.ts:512–528`) makes `private_staff_note`, `resume_target`, `active_block_id`, `artifact_id`, `artifact_digest` optional-and-nullable. All consumers in `[practiceId]/page.tsx` tolerate absence: truthiness guards at lines 320/330/340, `practice?.active_block_id ?? null` at line 186, and `getAllowedTransitions(state, resumeTarget?)` (`state-machine.ts:93–99`) explicitly accepts `undefined` and returns `[]` for Blocked-without-resume-target. The new `MINIMUM_PRACTICE` fixture (page.test.tsx) contains exactly the six `required` fields from `openapi.yaml:1664–1672` and the generated type — it compiles under the new type and would _not_ have under the old hand-written interface (which required `private_staff_note`/`resume_target`), so the test is correctly coupled to this patch.
   - `StaffPracticeListResponse` widens `next_cursor` from required `string | null` to optional (`garuda-voa.generated.d.ts:2239`). This is a _widening_; the only consumer (`page.tsx:111`) reads `.items` only. No break.
   - The new test's expectations match `[practiceId]/page.tsx` behavior for a Blocked practice with no `resume_target`: empty transitions → "No transitions are available from this state." (line 383), no PR-09/PR-10 buttons, no note block.

2. **Type compatibility — sound, with one pin dependency.** `practice.state` is now the _generated_ `PracticeState` union, passed to `getAllowedTransitions(state: PracticeState)` and used to index `Record<PracticeState, …>` (`page.tsx:223`), where the parameter/record type is the union re-exported from `@/app/visa/voa/orders/types`. String-literal unions are structurally typed, so this compiles iff the two unions have identical members — which the existing `state-machine.test.ts` pin asserts at the value level. Not a defect; see assumption (e).

3. **CI step mechanics — internally consistent.** The new step (`tests.yml:1849–1853`) is ordered after Checkout and `npm install`, gated on the correct `steps.decide.outputs.run` id plus `matrix.app == 'mouth'`, runs from repo root where both path arguments (`products/…/openapi.yaml`, `apps/mouth/…/garuda-voa.generated.d.ts`) are root-relative and match the committed artifact's location. The `.prettierignore` entry is load-bearing (root lint-staged's `*.ts` glob would otherwise reformat the `.d.ts` and cause immediate drift against generator output) and is present. No lockfile/dependency change is consistent with `openapi-typescript: ^7.10.1` already being in `apps/mouth/package.json:102`.

---

### (2) Unresolved assumptions requiring empirical verification

1. **(Highest impact) `products/` must actually be unclassified in `change_map.py`.** The gate's entire goal — "fail when only `products/` changes" — relies on the fail-open fallback (`classify()` → `run_all=True` on unclassified paths, change_map.py:528) because `PREFIX_RULES` is not fully shown in the supplied context. _Trigger if false:_ if `PREFIX_RULES` maps `products/` to a selective domain set excluding `mouth`, a contract-only PR classifies cleanly, `decide` sets `run=false`, the freshness step never executes for exactly the change class it exists to police, and README's claim ("currently select all test suites") is false while everything stays green. Verify with one command: feed a products-only path to `scripts/ci/change_map.py` and confirm `run_all: true` / `frontend-tests` in `suggested_jobs`.
2. **`--check` support and semantics in openapi-typescript 7.10.1.** The patch assumes the CLI accepts `--check`, compares against the `--output` file without writing, and exits non-zero on drift. If the flag is unsupported in the lockfile-pinned version, the required mouth leg goes red immediately — self-revealing on this PR's own run, so limited blast radius, but unverified here.
3. **Binary hoisting.** `./node_modules/.bin/openapi-typescript` at repo root requires npm workspaces hoisting; other workspaces' manifests (admin-dashboard, web, etc.) are not in the supplied context, so a conflicting nested copy cannot be excluded. Also self-revealing on this PR's own run.
4. **Byte-identity of the committed artifact.** The committed `garuda-voa.generated.d.ts` must equal CI's regeneration under Node 24 with the lockfile-pinned generator (e.g., not produced via `npx` latest, not prettier-formatted before the ignore rule landed). The step itself verifies this on first run.
5. **Dual `PracticeState` identity** (see 1.2): the value-level pin exists, but no `tsc --noEmit` step is visible in the supplied `frontend-tests` excerpt, so a future divergence of the two unions would be caught only if typecheck runs elsewhere.

---

### (3) Conclusion

**No actionable defect found within the supplied scope.** Optional/null handling, minimal-response rendering, type widening, CI step ordering/conditioning, and the prettier exclusion are all internally consistent with the supplied sources. The patch's core deliverable — gating products-only contract drift — is _plausible but unproven_: it rests on assumption (2.1), which is verifiable in a single local command and is the one item I would want empirically confirmed before this advances past the council stage. This review is one independent seat, not an approval to ship.
