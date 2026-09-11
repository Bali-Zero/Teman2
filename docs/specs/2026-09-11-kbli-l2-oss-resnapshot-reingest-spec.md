# KBLI L2 re-ingestion from the 2026-09-11 OSS re-snapshot — deterministic launch spec

**Status:** SPEC r1, 2026-09-11. Nothing here is implemented. Ordered by Zero ("pianifica un lancio
deterministico preciso") after the re-snapshot proved that OSS moved on risk and licences while
the classification text stayed identical.

## 0. What is true today (measured 2026-09-11, all on M5)

| fact                                                                                                                                                                                                                                                                                                                                         | evidence                                                            |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| OSS list (2422 records, 1559 five-digit): 0 codes added/removed, 0 judul/uraian/uuid changes since the June 19 ground truth                                                                                                                                                                                                                  | `~/Desktop/oss-resnapshot-20260911/oss_list_diff_20260911.md`       |
| Full 4-endpoint re-snapshot, 1559/1559, 0 failures                                                                                                                                                                                                                                                                                           | `~/nuzantara-vault-20260911/oss/` + `fetch-log.jsonl`               |
| `detail` and `relasi`: 1559/1559 byte-identical to the 2026-07-17 vault                                                                                                                                                                                                                                                                      | `~/Desktop/oss-resnapshot-20260911/oss_vault_diff_20260911.md` §1-2 |
| `ruang_lingkup` risk-tier set changed on **178** codes: 70 = scope "Seluruh" split into named sub-scopes with identical tiers; **108 = new (skala, resiko) combinations**                                                                                                                                                                    | same, §3                                                            |
| `umku`: newly published for 262 codes, dropped for 23, licence set changed on 74 (true removals: 10772/10773 lost SPP-IRT — verified on raw files 13 → 11 rows; 11040 −19; 20114, 20123-20125, 32906, 46442, 43120, 50122, 71202, 93210, 93294)                                                                                              | same, §4; spot-check in session                                     |
| `ruang_lingkup` presence: 1325 both, 212 absent both, **13 old-only, 9 new-only**                                                                                                                                                                                                                                                            | same, §1                                                            |
| Canonical corpus `v10.0-L2-oss-risk` was built on 2026-06-20 (PR #1592 + #1598) by `scripts/build_kbli_l2_oss_risk.py` from `/tmp/oss_risk_raw.jsonl` (single endpoint, `scripts/fetch_oss_risk.py`), **not** from the vault                                                                                                                 | `scripts/build_kbli_l2_oss_risk.py:30-35,142-146`                   |
| That script has `ROOT=/tmp/kbli-l2-risk` and `RAW=/tmp/oss_risk_raw.jsonl` hardcoded; a second, diverged copy lives at `apps/backend-rag/scripts/build_kbli_l2_oss_risk.py` (31 differing lines, different NO_BESAR handling)                                                                                                                | `diff` in session                                                   |
| The vault `ruang_lingkup.json` is the raw response of the same endpoint (`{success,data,meta,code}`) the jsonl stored under `data` — an adapter is enough, no new transform                                                                                                                                                                  | 56101 inspected on both                                             |
| Guards that bite on a corpus change: `apps/mouth/src/lib/kbli-dataset-version.test.ts` (sha sidecar), `scripts/sync_kbli_dataset.sh --check` (CI, 5 copies), count pins 1559 in `apps/kbli-navigator/lib/__tests__/kbli-data.test.ts`, `test_kbli_documents_phantom_cure.py`, `test_kbli_pp28_provenance.py`, `test_kbli_qdrant_pma_sync.py` | Explore map, session                                                |
| Canonical file: 548,352 lines, 36 MB → any rewrite is churn ≫ 1,828 → harness floor **3** by size                                                                                                                                                                                                                                            | `wc -l`, `scripts/evidence_pack_lint.py` thresholds                 |
| KG licensing (what clients read via `kbli_notebook.py:664-699`) is a separate store; spec r4 (`docs/specs/2026-09-02-kbli-kg-licensing-class-cure-spec.md`) has nothing implemented; `umku` never fed the corpus                                                                                                                             | Explore map                                                         |
| Methodology P3: a single 404 is not absence — ≥3 attempts over ≥72h + portal cross-check before `ABSENT`; removals go through quarantine, never deletion                                                                                                                                                                                     | `research/operations/2026-07-16-kbli-filiera-methodology.md`        |

## 1. Scope of THIS launch

**In:** regenerate `per_skala` (tiers, jangka_waktu, perizinan/persyaratan/kewajiban/kewenangan per
scope), `_l2_source/_l2_status`, and the L4-Bali recomputation that the same script already does,
from the September vault, for the 1559 codes. Fix `metadata.source` (`PP28_2024` → `PP28_2025`,
finding C-CLAIM-014) in the same regeneration because it is the same artifact and the same sha bump.

**Out (own specs):** `umku` licences into the KG (spec r4, Lot 0 first — this launch only hands it
the 74-code diff as evidence); English titles; `ruang_lingkup` text (unchanged); any editorial page.

## 2. Determinism contract

1. **One input, frozen.** `~/nuzantara-vault-20260911` is L0 evidence: `chmod -R a-w` after
   `vault_manifest.py --out` writes its sha256 manifest; the manifest sha is quoted in the brief.
   The July vault is never modified.
2. **One adapter, pure.** New `scripts/kbli_filiera/vault_to_risk_jsonl.py <vault-root> <out.jsonl>`:
   for every 5-digit code in the ground truth, in ascending `kode` order, emit
   `{"kode","uuid","status":200|404,"data":<raw ruang_lingkup.json>}` — 404 when the code is in
   `absences.jsonl` for endpoint `ruang_lingkup`. No timestamps, no network, `ensure_ascii=False`.
   Unit test: same vault twice → byte-identical jsonl.
3. **One transform, parameterised, not rewritten.** `scripts/build_kbli_l2_oss_risk.py` gains
   `--root <checkout>` and `--raw <jsonl>` (defaults keep today's literals so the June run is still
   reproducible). No logic change in the same PR. `apps/backend-rag/scripts/build_kbli_l2_oss_risk.py`
   is left untouched and named in the PR body as the diverged copy to reconcile separately.
4. **Reproduce before you change (the gate that decides which script is canonical).**
   Adapter over the **July** vault → jsonl → dry-run of the transform against the current
   canonical. Expected: 0 per-code changes on `per_skala`, `_l2_*`, `l4_bali`. If the `scripts/`
   copy reproduces and the backend copy does not, `scripts/` is canonical, recorded in the spec.
   If neither reproduces, STOP: the June state was produced by something not on `main`, and the
   plan is under-specified (Builder Contract rule 1, fix-of-a-fix depth 1).
5. **Predicted diff = measured diff.** Dry-run over the September jsonl must change exactly the
   codes named in `oss_vault_diff_20260911.md` §3 (178 on tiers) plus whatever perizinan-level
   changes the report's generic flag covers; any code outside that set changing is a STOP.
6. **Absences are not applied.** The 13 codes present in July and 404 today keep their July
   `per_skala` and get `_l2_status: "absent_pending_corroboration"` with `absent_probes: [date]`;
   they flip to `no_oss_risk` only after two more probes ≥72h apart (P3). The 9 new-only codes are
   applied (presence needs no corroboration).
7. **Version and provenance.** `metadata.version = "v11.0-L2-oss-risk-20260911"`,
   `metadata.l2_snapshot = {vault: "nuzantara-vault-20260911", manifest_sha256, fetched: "2026-09-11",
codes_changed: 178, absent_pending: 13}`, `metadata.source` corrected to `PP28_2025`.
8. **Same dump.** `json.dumps(ds, ensure_ascii=False, indent=2)` exactly as today (`:267`), then
   `scripts/sync_kbli_dataset.sh` for the five copies, then the sidecar
   (`datasetSha256 = sha256:<new>`, `lastModified = <commit date>`).

## 3. Launch sequence (one session owns it end to end)

| step                | command / action                                                                                                                                                                                                  | proof                                                                                     |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| L0                  | `python3 scripts/kbli_filiera/vault_manifest.py --vault-root ~/nuzantara-vault-20260911 --out ~/Desktop/oss-resnapshot-20260911/manifest.json` then `chmod -R a-w ~/nuzantara-vault-20260911`                     | manifest sha256 in brief                                                                  |
| PR-A (code, Gear 2) | adapter + `--root/--raw` flags + adapter test + reproduction test that runs the July vault through adapter+transform and asserts 0 changes (fixture: 20 codes, not the whole vault)                               | CI green; `Bites:` = the reproduction test                                                |
| L1                  | adapter over July vault → `/tmp/l2/july.jsonl`; `build_kbli_l2_oss_risk.py --root <fresh worktree> --raw /tmp/l2/july.jsonl` (dry-run)                                                                            | report shows 0 changed codes (rule 4)                                                     |
| L2                  | adapter over September vault → `/tmp/l2/sept.jsonl`; dry-run                                                                                                                                                      | changed set == §3 set of the diff report (rule 5); absent set == 13 (rule 6)              |
| PR-B (data, Gear 3) | `--apply` in the worktree, `sync_kbli_dataset.sh`, sidecar bump, `metadata.*` per rule 7; `evidence/brief.yml` + `evidence/pack.yml` (size floor 3); council per harness                                          | vitest sidecar test, navigator 1559 pins, backend `test_kbli_*` pins, tripwires all green |
| gate                | fresh Opus session signs `harness/fable-gate` on the head; codex refuter round on the per-code diff (generator ≠ grader)                                                                                          | status on head sha                                                                        |
| deploy              | merge = Vercel deploy of apps/mouth; backend `kbli_documents.metadata` resync (the `--licensing-only`-style script used in PR #5513, `apps/backend-rag/backend/scripts/kbli_documents_cure.py`) for the 178 codes | see prove-live                                                                            |
| prove-live          | `curl https://balizero.com/kbli/10215` shows the new tier set (10215 gained 4 tiers); `inspect_kbli 10215` from the MCP returns the same; sidecar sha == live dataset sha                                         | screenshots + curl output in the pack                                                     |
| hand-off            | `oss_vault_diff_20260911.md` §4 (74 licence codes) attached to spec r4 as the umku evidence; 13 absent codes scheduled for re-probe at +24h and +72h                                                              | PENDING-ARMS rows                                                                         |

## 4. Stop conditions

- Rule 4 fails (June state not reproducible) → no PR-B; write the reconciliation spec first.
- Rule 5 fails (unexpected code changes) → no `--apply`; diff the adapter output against the
  vault diff script's parsing, fix one of the two, re-run L1 then L2.
- Any of the 1559 pins moves (a code appears or disappears) → STOP: the list diff says 0/0.
- PII: none possible (public classification data); the pack still runs the personal-data grep.

## 5. Cost and blast radius

- PR-A: ~150 lines of code + tests, Gear 2, one afternoon.
- PR-B: one 36 MB file rewritten in five copies; Gear 3 by size, evidence pack mandatory;
  client-facing change on 178 code pages and on the RAG answers for those codes.
- Nothing touches the KG, the WhatsApp bot rules, or the editorial pages.

## 6. Rule-4 outcome — PR-A gate run, 2026-09-11 (r2)

Measured on M5 with the adapter over the **July** vault (1559/1559, no missing evidence),
`--apply` on a `/tmp` copy only, field-level diff against the canonical `v10.0-L2-oss-risk`:

| field                                                                 | codes differing                                                      | note                                                                                               |
| --------------------------------------------------------------------- | -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `skala_usaha`, `kategori_risiko`, `scope_index`                       | 0                                                                    | L2-owned, reproduced                                                                               |
| `scope_uraian`, `perizinan`, `persyaratan`, `kewajiban`, `kewenangan` | 1 (49213)                                                            | the divergence Lane A already recorded (A-PSK-0001)                                                |
| `jangka_waktu`                                                        | 942                                                                  | NOT L2-owned: rewritten after L2 by `scripts/enrich_kbli_jangka_waktu.py` (2026-06-28, PP28 rules) |
| `fiktif_positif`                                                      | dropped on 1337 codes (9,095 rows; 1342 codes carry it)              | a later layer adds it; the transform does not carry it                                             |
| `jangka_waktu_source`                                                 | dropped on 941 codes (4,200 rows)                                    | same                                                                                               |
| per_skala row count                                                   | 1 (20111: 0 → 12 rows across 3 scopes)                               | new OSS data, not a loss                                                                           |
| `l4_bali.blocked`                                                     | 21 with `scripts/` copy, **0 with `apps/backend-rag/scripts/` copy** | backend copy's NO_BESAR → `CHIUSO_PMA_NO_BESAR` (blocked) is what the canonical carries            |

Rule 5 (September vault): the adapter-driven (scope, skala, resiko) change set equals the
vault-diff set **178/178** (0 in either difference); absences 13 old-only / 9 new-only / 212 both.

**Rulings that follow (r2):**

1. Rule 4 is restated: reproduction means the **L2-owned field set** —
   `per_skala[].{skala_usaha, kategori_risiko, scope_index, scope_uraian, perizinan, persyaratan,
kewajiban, kewenangan}` + `_l2_source` + `_l2_status` — identical on every code except the ones
   the vault diff names. `jangka_waktu`, `fiktif_positif`, `jangka_waktu_source` and the L4 labels
   belong to later layers and are excluded by name, never silently.
2. The canonical L4 logic is the **`apps/backend-rag/scripts/` copy** (NO_BESAR is a block).
   PR-B ports that mapping into `scripts/build_kbli_l2_oss_risk.py` with a test on the 21 codes,
   and the backend copy is retired in a separate backend PR (its merge is a deploy).
3. PR-B's transform needs a **merge policy**, not a rewrite: on `--apply` it must preserve
   `jangka_waktu` where `jangka_waktu_source` is set, and carry `fiktif_positif` and
   `jangka_waktu_source` through; a dry-run field table like the one above is part of PR-B's
   evidence pack, and any non-zero cell outside the predicted set is a STOP.
4. 49213 is resynced from OSS in PR-B (closes A-PSK-0001); 20111 gains its 12 scopes.
