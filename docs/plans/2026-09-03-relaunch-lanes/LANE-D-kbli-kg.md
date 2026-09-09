# LANE D — KBLI KG licensing cure: reopen from the six findings

**Machine:** Mini (Postgres, Qdrant, KG, Redis cache, local Ollama; long lots).
**Corner:** `.agents/skills/kbli-navigator/SKILL.md` §1 LIVE STATE (2026-09-02 entry) and the spec
`docs/specs/2026-09-02-kbli-kg-licensing-class-cure-spec.md` — **reopen from its findings table,
never from zero**. **Contract:** `README.md` here.

The spec is SUSPENDED under rule 8 (three Codex-sol rounds: BLOCKED 9 → 11 → 6). The measurements
stand, the design does not. Your first PR is the spec revision that answers the six tabled findings;
your second is code. Cure → bust cache → prove with `inspect_kbli` on prod, in that order
(`kbli_notebook.py:609-614` reads Redis first).

## Facts that bind the design (re-measure, then trust)

- 175 codes in three DISJOINT states: S1 70 (`PENDING_REGULATION`, 0 admitted permits), S2 99
  (`REGULATED`, 0 admitted — the mouth prints "Not listed in our data"), S3 6 (one legacy licence
  rendered). Not "22 of 25".
- `inspect_kbli` reads tier data from the TARGET NODE's `properties`, not from the edge
  (`kbli_notebook.py:664-668, 691-699`): data goes on the node; shared nodes collide on 196 ids —
  use code-scoped ids `perizinan:pp28v10:<code>:<full-payload-hash>`.
- For LICENSING the KG is primary and mandatory; Qdrant only for `pma_status`/`kategori_risiko`.
- Legal basis PP 28/2025 Pasal 128-133 (tier → NIB / NIB+SS self-declared / NIB+verified SS /
  NIB+Izin) read from the BPK gazette PDF whose sha256 is in spec §4.1.
- `NOT_APPLICABLE_OSS` (75 codes) is data in `scripts/kbli_filiera/kg_oss_not_applicable_codes.json`.

## D1 — `--placeholders-only` on the 17 codes (phase-independent, do first)

- Three nodes named `PENDING_REGULATION` are served to clients AS LICENCES on 17 codes (live
  `inspect_kbli 65121`). `pending` is not an admission marker (`kbli_requires_kind.py:178`). Remove
  them; 85586 has 0 rows and 4 of the 17 are non-OSS — none of that changes the gesture. Bust the
  Redis key, prove on prod with `inspect_kbli` for all 17.

## D2 — Phase 1a: the 114 OSS-issued codes, in lots

- Cure script next to `apps/backend-rag/backend/scripts/kbli_documents_cure.py` (its
  `--pma-only` / `--licensing-only` shape is the template; `archive_params` archives a SQL NULL
  metadata as `{}` — fix that first, ledger 2026-09-01).
- Detectors run BOTH directions (KG → canonical and canonical → KG); one exact `node_properties`
  object; `01122` has 8 rows and NO KG node; `91300` is `REGULATED` over a canonical `[]`;
  `skala_usaha` disagrees with the canonical union on 881/1,341 codes — census, then decide.
- Lots of ≤ 30 codes, each proved live before the next. Backend-rag PR = deploy: batch.

## D3 — Phase 1b: the 61 non-OSS codes — Zero decides

- "OSS hanya menerbitkan NIB" codes (85510 among them): relabel now, or gate on the F2 router
  increment that renders the issuer? `ZERO-DECISIONS.md` item 2. Prepare both diffs' size and risk
  in the spec revision; build nothing until ruled.

## Guards

- KBLI = **1,559** codes, never 1,563. Canonical PMA tuple `located` on 54 codes only; the rest is
  `declared_gap` by design — do not "fix" it here.
- `jsonb` double-encodes `json.dumps`; probe with `jsonb_typeof` (memory 2026-08-27).
- The canonical has no `licensing_status` field; the verdict is a function of `per_skala`.

## LIVE STATE (update before ending the session)

- 2026-09-03: spec suspended at round 3; D1 not started; D2 not started; D3 waits for Zero.
