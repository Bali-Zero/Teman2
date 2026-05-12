# cicatrix-scars.md

Living document of "scars" — past bugs/issues auto-extracted from development history.
Each entry has TRAUMA (what went wrong), ANTIBODY (how it's now protected), and GOTCHA (edge cases).

---

### ⚠️ STRUCTURAL: WR2 master template requires verified richtext slot count (2026-05-10 → architecturally bypassed 2026-05-13)

_Discovered: 2026-05-10 02:53 WITA during run #1 of the post-DAHE6lx1lf8 recovery cycle · Patched 2026-05-10 via `chore/wr2-pipeline-hardening-2026-05-10` (validator + unit test + docstring guard) · **Architecturally bypassed 2026-05-13 via `feat/wr2-canva-pdf-render-2026-05-13`** (ReportLab→Tigris→Canva import flow, no master template required) · Severity: P0 (now defanged)_

**RESOLUTION (2026-05-13 — DAHJEkWpkzY validation gap FINALLY closed):**

The structural validation gap (master template richtext slot count) is now moot
because the new rendering pipeline does not depend on a Canva master template
at all. The PDF is generated server-side via ReportLab (`wr2_canva_pdf_render.py`,
12 layout families auto-routed via `slide.layout_family`), uploaded to Tigris
S3, then imported into Canva via `import-design-from-url` MCP which yields a
layer-editable design without needing pre-existing richtext slots.

Status of the three failing master template IDs:

| Design ID | Status | Reason |
|---|---|---|
| `DAHE6lx1lf8` | DECOMMISSIONED 2026-05-08 | Original master, obsolete |
| `DAHJLYRn_3E` | KEPT AS FAILURE EXAMPLE | Only 2 usable pages (PR #565 failed promotion) |
| `DAHJEkWpkzY` | UNUSED IN NEW FLOW | Was the 2026-05-10 "fix" master; the new flow doesn't read any master |

The validator `scripts/wr2_validate_master.py` is preserved in repo for
documentation and as a tool if anyone needs to evaluate a Canva design's
shape (e.g. for new editorial surfaces). The unit-test contract
`test_template_design_id_format` in
`apps/backend-rag/backend/tests/unit/services/canva_renderer/test_pending_builder.py`
is preserved for the legacy `wr2_canva_apply.py` orchestrator (now disabled
via kill switch — see below).

**Production cron disabled 2026-05-13**: `com.balizero.wr2.canva-renderer.plist`
called the legacy orchestrator (`wr2_canva_apply.py`) which relied on the
broken master template flow. Disabled via:
1. Kill switch flipped to `false`: `system_settings.wr2_canva_renderer_enabled='false'`
2. Plist bootout: `launchctl bootout gui/$(id -u)/com.balizero.wr2.canva-renderer`

Plist file `~/Library/LaunchAgents/com.balizero.wr2.canva-renderer.plist`
preserved on disk for future reload AFTER the orchestrator refactor
integrates the new renderer. Until then: queue stays empty (verified
0 drafts pending at decommission time, status distribution 20 rendered
+ 15 rejected). When the orchestrator refactor lands, the plist will be
updated to call the new pipeline (ReportLab → Tigris → Canva MCP import)
and the kill switch flipped back on.

Branch: `feat/wr2-canva-pdf-render-2026-05-13`. Commits:
- `fafa25267` — feat(wr2): rebuild wr2_canva_pdf_render.py production renderer
- `e697328d5` — fix(wr2): 3 visual fixes (body vcenter + punctuation glue + Quartz stat-card)

**2026-05-13 v3 orchestrator end-to-end design + implementation complete** (PR pending):

The new `canva_renderer_v2` package (~1000 LOC across 9 modules) and 4 scripts + 3 launchd plists are committed on branch `feat/wr2-canva-pdf-render-2026-05-13`. End-to-end loop now codeable: PG draft → ReportLab → Tigris → Canva `import-design-from-url` → PG update. No master template required.

Full implementation tasks T1-T13 (47/47 unit tests passing across all modules) committed as discrete bisect-safe commits:

- T1: `c4a497ac3` — migration 169 lease columns
- T2: `7a43ba1e1` — pkg init + _telegram.py
- T3: `b40d4c2b3` — _schema_adapter.py + 3 fixtures
- T4: `ecaba84c9` — _pdf_pipeline.py subprocess
- T5: `302a7f466` — _tigris.py + S3 lifecycle JSON
- T6: `dc2967ca9` — _token_storage.py (HMAC + flock + proactive refresh)
- T7: `96bc8c203` — _canva_mcp.py (mcp SDK 1.27.0 streamable HTTP + OAuth)
- T8: `d765894b9` — _pg.py asyncpg + lease CAS
- T9: `af33c24bf` — _telemetry.py JSONL + rotation
- T10: `532e93e92` — orchestrator.py top-level (3 integration tests)
- T11: `6e830a2f4` — scripts/wr2_canva_pdf_apply.py entrypoint
- T12: `1bc70a32e` — bootstrap + 2 watchdogs + E2E fixture
- T13: `36b118602` — 3 launchd plists (plutil-lint OK)

Pending T14 (this update) + T15 (PR open). Deploy via `docs/runbooks/wr2-orchestrator-pdf-render-runbook.md`.

Scar moves toward archival — DAHJEkWpkzY validation gap permanently closed by architectural pivot.

_Discovered: 2026-05-10 02:53 WITA during run #1 of the post-DAHE6lx1lf8 recovery cycle · Patched 2026-05-10 via `chore/wr2-pipeline-hardening-2026-05-10` (validator + unit test + docstring guard) · Severity: P0_

**TRAUMA:** PR #565 promoted `DAHJLYRn_3E` as the new master template
in `apps/backend-rag/backend/services/canva_renderer/pending_builder.py`
(`TEMPLATE_DESIGN_ID = "DAHJLYRn_3E"`) without verifying its structural
shape. The design only had richtext slots on pages 2 and 3; the renderer
emits ops for pages 1 + 4-11. Phase A live-mapping detected 19/22 ops
(86%) would drop and the canva-apply skill aborted with
`template_mismatch`. Phase 0 had already committed (3 elements wiped on
the new master) — wasting one transaction round-trip and leaving the
master in blank state.

Concrete sequence:
```
02:53:09  Kickstart canva-apply for draft 6ace6b26 (Golden Visa)
02:53:51  Claude Desktop attempt 2/5 OK
~02:55    Phase 0 wipe 3 elements (DAHJLYRn_3E) committed
~02:57    Phase A live-map: page 1 has 0 richtexts (>=30 width),
          pages 4-12 same → 19/22 ops would drop
~02:58    Skill aborts with `template_mismatch` (no design_id produced)
03:00     Operator confirmed via get-design-content that
          DAHJLYRn_3E is structurally incompatible
03:21     PR #566 swapped master to DAHJEkWpkzY (verified text on all 12 pages)
```

The required CI checks (E2E + MCP) on PR #565 were green. They tested
the python code change (10 unit tests on `pending_builder.py`); they
did NOT test that the live template at the new ID had the structural
shape the renderer assumes. Squawk migration lint, Frontend tests, and
all other guards were also irrelevant.

**ANTIBODY (shipped on `chore/wr2-pipeline-hardening-2026-05-10`):**

1. **Pre-flight validator** `scripts/wr2_validate_master.py` — accepts
   `--design-id <DAHX...>` (optional, defaults to current
   `TEMPLATE_DESIGN_ID`) and exits non-zero if the design is missing
   from Canva, has fewer than 11 usable pages, or has fewer than 18
   richtext elements (heading + body × 9 minimum). Calls Canva MCP via
   the same OAuth flow the apply skill uses. Designed to run from a
   PR-check workflow OR as a `pre-merge` manual check before any commit
   that bumps `TEMPLATE_DESIGN_ID`.
2. **Unit-test contract** in
   `apps/backend-rag/backend/tests/unit/services/canva_renderer/test_pending_builder.py`:
   `test_template_design_id_format` asserts the constant matches
   `^DAH[A-Za-z0-9_-]{8}$` (Canva design ID shape). The empirical
   structural check stays in the validator script — running a Canva
   MCP call from CI is not feasible without Canva-side OAuth.
3. **Docstring header** on `TEMPLATE_DESIGN_ID` now lists the
   verification checklist a contributor MUST run before changing it
   (run validator + post the JSON output in the PR description).

**Phase-1 limitation (documented):** The unit test only checks the
shape of the constant, not the live structural compatibility. A
contributor who points `TEMPLATE_DESIGN_ID` at a syntactically-valid
but structurally-broken Canva design will still slip through CI. The
validator script is the only gate that catches that — relying on
human discipline to run it. Phase 2 (future PR) wires the validator
into a GitHub Action triggered specifically when
`pending_builder.py` is touched, calling Canva MCP via a service
account.

**GOTCHA:**

- Phase 0 of the canva-apply skill commits BEFORE Phase A detects the
  mismatch. This is by design (defense-in-depth: master is always
  blanked at run start). Side-effect: a structurally-incompatible
  master gets wiped of any residual content on the failed run, which
  is harmless if the master is correct shape — but if the master was
  the *wrong design* entirely (e.g. someone pasted a personal design
  ID by accident), Phase 0 wipes that design's text. The validator
  script catches this before any wipe happens; future PRs touching
  `TEMPLATE_DESIGN_ID` MUST run the validator (no CI auto-enforcement
  yet, see Phase 2 above).
- The `start-editing-transaction` MCP call returns ALL richtext
  elements regardless of width. The renderer (and the apply skill)
  filters by `width >= 30` to exclude bullet glyphs and decorative
  rules. Validator uses the same filter. If the filter threshold is
  ever changed in the apply skill, the validator must be updated in
  lockstep — there is no programmatic link between the two.
- `DAHJLYRn_3E` is left in Canva (not trashed) as the canonical
  failure-mode example. Future contributors evaluating new template
  candidates can `get-design-content` it to see what "structurally
  incompatible" looks like. If you trash it, document the new
  cautionary example in this scar entry.
- Future template promotions: prefer designs that are already
  duplicates of a working master (e.g. carousel-folder outputs from
  a prior successful run). They inherit the structural shape by
  construction. The 4 "buggy orphans"
  (`DAHJDtWApaw, DAHJCzTzn1I, DAHHv6JaHiQ, DAHJEkWpkzY`) are
  examples of this — `DAHJEkWpkzY` was promoted to master in PR
  #566 precisely because its structure was a verified clone of the
  original `DAHE6lx1lf8`.

Memory references: see `auto memory` discovery 2026-05-10 04:30 WITA
("WR2 master template structural validation gap"). Recovery commits:
PR #565 (failed master), PR #566 (working master), this PR
(prevention).

---

### ⚠️ STRUCTURAL: WR2 canva-apply path coupling between deploy worktree and main repo (2026-05-10)

_Discovered: 2026-05-10 03:50 WITA during the same recovery cycle as the previous scar · Severity: P0 · Workaround SHIPPED in `chore/wr2-pipeline-hardening-2026-05-10`: skill now accepts `WR2_OUTPUT_ROOT` env var; production runs export `WR2_OUTPUT_ROOT=/Users/nuzantara/Desktop/nuzantara/apps/war-room/output/canva` so both deploy worktree (writer) and main repo (skill reader) point at the same dir. Symlink hack archived._

**TRAUMA:** Production cron runs `wr2_canva_desktop_apply.py` from the
deploy worktree at `/Users/nuzantara/Desktop/nuzantara-deploy`. The
script writes the pending JSON to its own copy of the path:
`apps/war-room/output/canva/canva_pending.json`. The
`/canva-apply` skill at `~/.claude/skills/canva-apply.md` was hardcoded
to read from the **main** repo path
`/Users/nuzantara/Desktop/nuzantara/apps/war-room/output/canva/...`.
Result: the skill reads a different (older or absent) pending JSON
than the script just wrote. During run #1 today (2026-05-10 02:53)
the skill silently timed out polling because the file at the
hardcoded main-repo path was stale.

The temporary fix during the recovery was a runtime symlink:
```
ln -s /Users/nuzantara/Desktop/nuzantara/apps/war-room/output/canva \
      /Users/nuzantara/Desktop/nuzantara-deploy/apps/war-room/output/canva
```
This is fragile because:
- Symlink is not committed to git (it lives in the deploy worktree
  directory only)
- `git worktree remove ... && git worktree add ...` would silently
  destroy it
- Discovery requires `ls -la` — easy to miss

**ANTIBODY (shipped):**

1. **Skill reads `WR2_OUTPUT_ROOT` env var** with fallback to the
   legacy main-repo path. Plist `com.balizero.wr2.canva-apply.plist`
   exports `WR2_OUTPUT_ROOT` matching the writer side; both sides
   resolve to the same canonical path. The symlink is no longer
   required and SHOULD be removed once the skill update is verified
   in production.
2. **Documentation** in `~/.claude/skills/canva-apply.md` header
   notes the env-var contract, with a one-line example of the plist
   directive.
3. **Long-term TODO** (Phase 2, separate PR): move output dir out of
   the git tree entirely (`~/var/wr2/output/canva/`). Working
   runtime data has no business living under a `git pull`-able path.
   This eliminates the worktree coupling entirely.

**GOTCHA:**

- The skill is loaded from `~/.claude/skills/canva-apply.md` — i.e.
  the operator's local Claude config dir. It is NOT in the git tree
  by default. A snapshot copy at `infra/claude-skills/canva-apply.md`
  is added in this PR for change tracking, with a CI check that
  fails if the local skill drifts from the git copy. Operators who
  iterate the skill locally MUST commit the change.
- `WR2_OUTPUT_ROOT` must end without trailing slash for the skill's
  `f"{WR2_OUTPUT_ROOT}/canva_pending.json"` interpolation to work.
  The plist value is normalized server-side (skill strips trailing
  slash on read).
- `wr2_canva_desktop_apply.py` already reads `WR2_REPO_ROOT` — it's
  the same family of env override but a different variable, because
  the script needs the repo root (for venv + module imports) while
  the skill needs only the output dir. Don't conflate them.

---

### ⚠️ STRUCTURAL: LegalIngestionService bypasses OpenAI 300k token batch limit (2026-05-10)

_Discovered: 2026-05-10 ~15:00 WITA during regulatory-ingest skill batch run on 8 Indonesian regulations · Severity: P1 (data loss — ingest reports success but 0 chunks created) · Workaround: skip files >2MB until embed batching shipped_

**TRAUMA:** `LegalIngestionService.ingest_legal_document()` calls `EmbeddingsGenerator._embed_batch()` which sends all chunks in a single OpenAI API request. OpenAI `text-embedding-3-small` has a hard limit of **300,000 tokens per request**. For Indonesian legal PDFs >2-3MB the chunked text can easily exceed this — the API returns `400 max_tokens_per_request`, but the pipeline does NOT propagate this as a fatal error. Instead:

1. `_embed_batch()` returns a partial/empty embeddings array
2. `HierarchicalIndexer._upsert_hierarchical_chunks()` calls `qdrant.upsert_documents_with_sparse(chunks, embeddings, sparse_vectors, metadatas, ids)` with mismatched array lengths
3. `qdrant_db.py:1206` raises `ValueError: chunks, embeddings, sparse_vectors, metadatas, and ids must have same length`
4. The outer `ingest_legal_document()` catches the exception, logs "Ingestion failed", but the calling code receives an `ok=True` result with `chunks_created=0` (silent partial failure — looks successful in batch reports)

Concrete evidence (2026-05-10 batch):

```
[start] Permenkumham 22/2023 — Visa Dan Izin Tinggal (6961 KB)
Error generating embeddings: Error code: 400 - {'error': {'message': 'Requested 460590 tokens, max 300000 tokens per request', 'type': 'max_tokens_per_request', ...}}
Error upserting with sparse vectors: chunks, embeddings, sparse_vectors, metadatas, and ids must have same length
[done]  Permenkumham 22/2023 → chunks=0 in 32s   ← reports "done" but ZERO chunks indexed
```

3 of 8 regulations affected: Permenkumham 22/2023 (7MB / 460k tokens), Permenkumham 11/2024 (11MB), Permen ATR/BPN 18/2021 (4.8MB). All three remain only in NotebookLM, NOT in Qdrant `legal_unified_2026`. The batch report says "4/4 ok, 38 chunks" but should say "1/4 ok, 0 chunks for the failed one + WARN reason".

**Why we found this NOW:** the existing `ingest_t0_regulations.py` reference script was previously tested on small T0 immigration PDFs (<2MB each). The regulatory-ingest skill batch was the first to attempt large Permenkumham documents. The bug exists in production code paths but only triggers on >300k-token documents.

**ANTIBODY (proposed, NOT yet implemented):**

1. **Fix in `LegalIngestionService` / `EmbeddingsGenerator`** — split chunk arrays into sub-batches of max 200k tokens each (safety margin) before calling OpenAI. Aggregate embeddings array across sub-batches. Token counting via `tiktoken` for `cl100k_base` encoding (text-embedding-3-small uses this).

2. **Hard-fail propagation** — `EmbeddingsGenerator._embed_batch()` MUST raise on ANY OpenAI 4xx, NOT return partial array. Caller MUST verify `len(embeddings) == len(chunks)` before passing to upsert.

3. **CI test** — add unit test that builds a synthetic chunk list exceeding 300k tokens, calls `ingest_legal_document()`, asserts either (a) success with all chunks indexed (proper batching) OR (b) explicit `ValueError` with token-count message — never silent `chunks_created=0`.

**Workaround until fix shipped:**
- Skip files >2MB in batch ingest scripts (use `find -size -2M`)
- For large regulations, split PDF manually into <2MB chunks via `pdftk` before ingest
- Always verify `chunks_created > 0` in batch reports; treat 0 as failure even if status="ok"

**GOTCHA:**

- The 300k token limit is per-request, not per-document. Even a 5MB PDF with proper batching of ~10 sub-requests would work. The bug is the absence of batching, not the token limit itself.
- The `ValueError` message ("must have same length") is misleading — it suggests a chunker bug. The real cause is upstream embedding API rejection. Always check OpenAI API logs first when seeing this error.
- `LegalIngestionService` returns `{success: True, chunks_created: 0}` on this failure path. Batch consumers MUST check `chunks_created > 0`, not just `success`. Status code is non-actionable.
- Workaround "split PDF" is destructive: BAB/Pasal hierarchical structure is broken across split boundaries. Real fix MUST be embedding batching at the API call level, not document splitting.

Reference batch: `/tmp/qdrant_batch_ingest_v2.py` + `/tmp/qdrant_small_only.py` (2026-05-10 evidence).
Files affected: `apps/backend-rag/backend/core/embeddings.py`, `apps/backend-rag/backend/core/legal/hierarchical_indexer.py`, `apps/backend-rag/backend/services/ingestion/legal_ingestion_service.py`.

---

### ⚠️ STRUCTURAL: 12+1 mata_garuda LaunchAgents active-active Pro+Mini (2026-05-07)

_Discovered: 2026-05-06 22:45 WITA during Symbiosis W1 genome enrollment audit (Zero verified via `launchctl list` on both nodes via Tailscale) · Severity: P1 · Workaround: TBD (cleanup in dedicated follow-up PR)_

**TRAUMA:** 13 launchd labels load SIMULTANEOUSLY on Pro AND Mini, both producing the same heartbeat at the same schedule. Verified labels (Pro+Mini both):

```
watcher.daily, reg-alert.30min, kg-linker, wr-topic, wr2-bridge.hourly,
bridge.adaptive, sentinel.daily, intel-bridge.daily, daily-briefing,
kita-feed.daily, public-channel, weekly-digest, gap.consumer
```

For cron jobs (most of the list above), this means the same agent/script runs **twice** per scheduled tick — once on Pro, once on Mini. Concrete blast radius depends per-organ:

- `intel-bridge.daily`: publishes to Redis stream `garuda:raw`. Stream entries deduped per-event-id but the harvester emits a NEW event-id per run → two distinct daily entries containing identical OSINT content.
- `regulation-alert.30min`: posts to Telegram. Alerts will fire twice (Pro and Mini both deliver to the same chat_id).
- `kg-linker`: writes to PostgreSQL knowledge graph. Concurrent writes may produce duplicate edges if the dedup logic is per-call rather than per-content-hash.
- `weekly-digest`, `daily-briefing`: same email or Telegram digest sent twice.
- `public-channel`: same scheduled post published twice.

The double-firing was masked until 2026-05-04 because Mini was offline most of April; the dup_resolver `~/scripts/wave1-pro-mini-dup-resolver.sh --check` reports zero conflicts when Mini is offline. The risk only materialises during Mini-up windows.

`~/scripts/wave1-pro-mini-dup-resolver.sh` exists with `--check` and `--resolve` modes but was never invoked because the Wave-1 catalogue assumed single-source plists; the 13 active-active labels are NOT in the resolver's protected list.

**ANTIBODY (proposed, NOT yet implemented — follow-up PR):**

1. **Decision per organ** — for each of the 13, decide: (a) Pro-only and unload from Mini, (b) Mini-only and unload from Pro, or (c) leader-election. Rationale per organ depends on resource locality (e.g. `kg-linker` writes to local Postgres on Pro; `nlm-feeder-stream` reaches NotebookLM CLI which is Pro-only). Default for the 13: prefer (a) Pro-only since Pro has the canonical CRM data and external API tokens.

2. **Plist removal** — `launchctl bootout gui/$(id -u)/com.matagaruda.<label>` + `rm ~/Library/LaunchAgents/com.matagaruda.<label>.plist` on the LOSING side. Update `organs_registry.yaml` (file renamed 2026-05-08 IG-3 from `genome.yaml`; legacy symlink works until 2026-06-08) to drop the corresponding `mini` or `pro` entry once the launchd state is reconciled.

3. **Resolver hardening** — extend `wave1-pro-mini-dup-resolver.sh` protected list to cover the 13 labels with `--resolve` mode that picks the canonical owner per organ. Run via cron after each Mini-up event (heartbeat from `secrets-sync-mini` could trigger).

4. **Test** — register new test in `apps/organism/tests/test_genome_no_active_active.py` that scans `organs_registry.yaml` for entries sharing identical `recovery_params.label` across `pro` and `mini` hosts, fails CI if any pair is found OUTSIDE an explicit allowlist (which starts empty post-cleanup).

Until the cleanup PR ships, the W1 PR registry shows 13 dup pairs cross-linked via `duplicates_id` (header-only convention) — observability without coordination. The Supervisor will surface 2× heartbeats per tick on these labels until reconciled.

**GOTCHA:**

- `organs_registry.yaml` `duplicates_id` is a HEADER-ONLY convention. The validator does NOT enforce it. A future refactor that drops `duplicates_id` accidentally will not surface in CI.
- The dup_resolver's `--check` mode returns "0 conflicts, Mini offline" when Mini is unreachable. Operators reading this output may conclude "no dups exist" — incorrect when Mini is up.
- Cron jobs on Pro and Mini may run at slightly offset wall-clock times because the 2 machines have independent clock skew. Expect a 0-5s window where both fire before either completes — race conditions in shared state (Redis SETNX, Postgres advisory lock) are NOT mitigated by this PR.
- Mata-garuda agents that emit to `garuda:raw` Redis stream pass through Nuzantara's CRM consumer; double-firing inflates `items_processed` metric by 2× until cleanup. Dashboards built on raw counts will misreport — note in dashboard query: filter by `host_pro_or_mini` if the producer label distinguishes.
- The 13th entry `gap.consumer` was reported as 12 in the topology brief but appears active-active in our enrollment; verify post-merge with Zero whether it's a dup pair or Pro-only. If Pro-only, drop the `mini` enrollment and remove the `duplicates_id` cross-link in a small follow-up commit.

**Related:** Wave-1 dup resolver `~/scripts/wave1-pro-mini-dup-resolver.sh [--check|--resolve]` (Pro-local, idle 2026-05-04 14:40 with Mini offline). MEMORY.md ref: "Wave-1 dup resolver" entry.

Brainstorm artifacts: none yet (this entry is post-discovery during the W1 enrollment). Future agents implementing the cleanup follow-up PR should reference this scar + the W1 PR (`feat(organism): enroll Wave 1 organs in Innervation Genoma`) as the inventory source.

---

### ⚠️ STRUCTURAL: NLM feeder split-brain — base_worker redis-cli has no host arg, prod has two local Redis instances (2026-05-06)

_Discovered: 2026-05-06 22:00 WITA during NB-INTEL pipeline resurrection ·
Patched: same day, branch `fix/nlm-feeder-resurrect-2026-05-06` · Severity: P0 ·
Status: code patched + Mini Redis configured; code activates on next merge to main_

**TRAUMA:** `apps/mata-garuda/mata_garuda/workers/base_worker.py` at lines
21–34 (pre-patch) shells out via `subprocess.run(["redis-cli", *args])` with
no `-h` / `-p` flags, so every call connects to **127.0.0.1**. After the
2026-05-02 Modo B reorganization the sentinel was moved to Mini and the
feeder kept running on Pro. Both machines run their own brew-managed
Redis at port 6379:

* Pro Redis `garuda:alerts` — 258 entries, last fresh 2026-05-05 02:01 (frozen)
* Mini Redis `garuda:alerts` — fresh today (latest 2026-05-06 02:01)

The feeder consumed Pro's stale stream every hour for ~36h while NotebookLM
saw `last delivered` of `2026-05-04T07:52:41Z`. Logs showed `processed=0,
fed=0` and operator read it as "stream healthy, no new items" — actually
"feeder pointing at the wrong Redis". The 753 nlm_fed entries in the local
KB are all from the Pro stream, so dedup masks the divergence.

Compounding fault: 2 transient `sqlite3.OperationalError: disk I/O error`
out of 106 hourly runs because `KnowledgeBase.__init__` opened the connection
without enabling WAL — a momentary lock collision between two overlapping
hourly invocations crashed the second one entirely instead of waiting on
the busy_timeout (Python's 5s default). Same class of bug, different
amplitude than the auth/CLI problems that the prompt suspected.

Concrete sentinel ground-truth (2026-05-06 22:30 WITA via `nlm notebook list`):

```
NB-INTEL-Immigration  61 sources  last_updated 2026-05-04T07:52:41Z
NB-INTEL-Tax          14 sources  last_updated 2026-04-19T18:54:05Z
NB-INTEL-Regulation   34 sources  last_updated 2026-05-04T07:52:52Z
NB-INTEL-Press        28 sources  last_updated 2026-05-04T07:52:40Z
NB-INTEL-AIResearch   75 sources  last_updated 2026-05-04T16:43:27Z
```

**ANTIBODY (shipped on `fix/nlm-feeder-resurrect-2026-05-06`):**

1. **`base_worker.redis_cmd` reads `GARUDA_REDIS_HOST` + optional
   `GARUDA_REDIS_PORT` from env** and prepends `-h $host` (and `-p $port`
   when both are set) to every redis-cli invocation. Empty/unset → no flags
   → localhost default (preserves backward compatibility for any caller
   running on the producer host). New `_redis_host_args()` helper documents
   the contract.
2. **`KnowledgeBase.__init__` now enables WAL + `synchronous=NORMAL`** on
   the connection. WAL allows readers + a single writer concurrently and
   makes transient lock contention wait on the busy_timeout instead of
   propagating an I/O error. WAL setting is persisted in the DB header so
   it's a no-op after the first open of an existing DB.
3. **9 new tests** in `tests/test_redis_host_override.py` (5) and
   `tests/test_knowledge_resilience.py` (4): empty/missing env, port-
   without-host ignored, host+port routing, parent dir creation, busy
   timeout ≥1s, journal_mode=wal, concurrent open without I/O error.
4. **Mini Redis reconfigured 2026-05-06 22:35 WITA**:
   `bind 127.0.0.1 ::1 100.93.236.6`, `protected-mode no`, `CONFIG REWRITE`
   persisted. Backup at
   `/opt/homebrew/etc/redis.conf.pre-tailscale-bind-2026-05-06`. Tailnet
   `balizero` is restricted to Pro+Mini devices (Subhi has admin role but
   no enrolled device, no SSH keys), so 6379 on the Tailscale IP is
   private-LAN-only.
5. **Pro plist** `~/Library/LaunchAgents/com.matagaruda.nlm-feeder-stream.hourly.plist`
   gains `GARUDA_REDIS_HOST=100.93.236.6` in `EnvironmentVariables`. Backup
   at `*.pre-redis-host-2026-05-06`. Reloaded via `launchctl bootout` +
   `bootstrap` 2026-05-06 22:38 WITA — verified live via `launchctl print`.

**Empirical AFTER (2026-05-06 23:00 WITA, after manual draining + 1 cron tick):**

```
NB-INTEL-Immigration  79 sources  +18
NB-INTEL-Tax          15 sources  +1
NB-INTEL-Regulation   38 sources  +4
NB-INTEL-Press        56 sources  +28
NB-INTEL-AIResearch   85 sources  +10
                      ──────────
                      +61 total
```

Press +28 and Immigration +18 hit the ≥5 threshold; Tax +1 and Regulation +4
reflect the actual sentinel topic distribution today, not a remaining
plumbing issue. Mini consumer group `nlm_feeder_alerts` shows
`entries-read=23, lag=0` after a synthetic test alert was injected and
consumed end-to-end via the new env path.

**GOTCHA:**

- **`redis-cli` itself does NOT honor `GARUDA_REDIS_HOST`**. The env var is
  read only by the Python `base_worker.redis_cmd` wrapper. A debug session
  that runs `GARUDA_REDIS_HOST=… redis-cli XLEN …` from a Pro shell will
  silently hit Pro localhost, returning numbers that LOOK like they came
  from Mini. Always use the Python wrapper or `redis-cli -h $host`
  explicitly when you debug. Compare `INFO server | grep run_id` — Pro and
  Mini each have a unique `run_id` and that's the only reliable way to
  tell which Redis answered.
- The plist's `WorkingDirectory` and Python interpreter path point at the
  main repo (`apps/mata-garuda/.venv/bin/python` against
  `/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda`), so the env-var
  override **only takes effect after `fix/nlm-feeder-resurrect-2026-05-06`
  merges to main**. Until then, hourly cron runs against the unpatched
  base_worker and silently keeps reading Pro localhost (i.e. a 0/0/0
  no-op). The fix is in production launchd config but inert until the
  binary code matches.
- Both Pro and Mini run a brew-managed Redis listening on 6379. Pro's
  `bind` was unchanged; only Mini's was extended. Future cross-host
  consumers MUST set `GARUDA_REDIS_HOST=100.93.236.6` explicitly — there
  is no auto-discovery. Mini Redis stays the OSINT producer per Modo B
  ("Mini=workhorse, Pro=consumer"); reversing that direction would
  require the symmetric Pro Redis bind change which we did NOT do.
- The KB `data/knowledge.db` retains 753 nlm_fed dedup entries from the
  pre-patch Pro-stream era. Items present in Mini's stream that share a
  URL with a Pro-fed item will be skipped on the first cycle after the
  pivot. This is correct behavior (no double-feed to NotebookLM) but
  visible as `skipped=N` in the JSON summary. The numbers above already
  account for this — Tax +1 / Regulation +4 are honest gains from
  non-overlapping URLs, not undercounts caused by dedup.
- TCC `getcwd: cannot access parent directories: Operation not permitted`
  errors flooding `~/logs/matagaruda-nlm-feeder-stream.error.log` are a
  RED HERRING. They originate from `/bin/zsh -lc` reading shell startup
  files under `/Users/nuzantara/.zshrc` etc. while launchd holds the
  process in a sandboxed cwd; the actual python interpreter starts cleanly
  and the feeder works (verified by the 612/612 test pass and the live
  source_count growth). A `bash` bridge or removing `-l` from the plist
  would silence them but does not change behavior. Out of scope here.

Brainstorm artifacts: none yet (acted directly on diagnostic evidence
visible in logs + `XINFO STREAM`). MOS records the diagnosis as discovery
2026-05-06 22:30 WITA importance 8 + the base_worker fact at importance 7.

---

### ⚠️ STRUCTURAL: Test infrastructure mock != production stack (Sprint 1.B 2026-05-02, 3 hotfix in chain)

_Discovered: 2026-05-02 during Sprint 1.B Era Post-Agentica deploy — 3 hotfix
PRs (#423, #424) chained on the original PR #422 because tests were green
but live endpoints failed. Severity: P1 — every new endpoint addition is at risk._

**TRAUMA:** Sprint 1.B PR #422 added a new FastAPI router
`apps/backend-rag/backend/app/routers/channel_health.py` exposing
`GET /api/channels/{name}/health` for Cell-side heartbeat bridge. Unit tests
all green (4/4), but on prod:

1. **First curl** post-deploy → `401 {"detail":"Authentication required"}`. Cause:
   `HybridAuthMiddleware` blocks all `/api/*` paths not in `PUBLIC_ENDPOINTS` registry.
   Test `_build_app_with_db_pool()` mounted only the router, NOT the middleware
   stack, so auth was never exercised. Fixed by hotfix #423 — added 4 exact-match
   entries in `_INFRA` group of `apps/backend-rag/backend/app/auth/public_endpoints.py`.
2. **Second curl** post-deploy of #423 → `404 {"detail":"Not found"}`. Cause:
   the new router was added to `router_manifest.py` as `RouterEntry(name="channel_health", ...)`
   but `router_registration.py` uses **explicit imports**, not the manifest. The
   manifest is read by tests (`test_router_manifest.py`) but NOT by the runtime
   `include_routers()` and `include_light_routers()` functions. Fixed by hotfix
   #424 — added `from backend.app.routers import channel_health` (×2) and
   `api.include_router(channel_health.router)` (×2) in router_registration.py.
3. After deploy of #424, all 4 endpoints returned 200 + valid JSON.

The 3-PR chain (#422 → #423 → #424) cost ~2 hours of CI/deploy/curl cycles
that could have been avoided if the test infrastructure exercised the full
production stack (middleware + manifest-vs-registration drift).

**ANTIBODY (proposed but not yet implemented in code):**

1. **Integration test layer** — `apps/backend-rag/backend/tests/integration/test_endpoints_reachable.py`
   that mounts the full `main_api` (or `main`) FastAPI app via `create_app()`
   and `httpx.AsyncClient(app=app, base_url="http://test")`, then GETs every
   route returned by `app.routes`. For each path:
   - Expect 401 (if not in PUBLIC_ENDPOINTS) or 200/404/422 (if public).
   - Any new path that returns 404 → test fails.
   - Any new path with `health` in URL that returns 401 → flag as candidate
     for PUBLIC_ENDPOINTS review.

2. **Manifest-vs-registration parity test** — `backend/tests/setup/test_manifest_parity.py`:
   - Read `ROUTER_MANIFEST` from `router_manifest.py`.
   - Read `include_routers()` source via `inspect.getsource()` and grep for
     `include_router(<name>.router)` calls.
   - Assert every `RouterEntry(name=X)` with `process_groups` containing
     `_API` or `_BOTH` has a matching `api.include_router(X.router)` call
     in both `include_routers` AND `include_light_routers`.
   - Catches drift the moment a new manifest entry is added without the
     corresponding explicit imports.

3. **Public endpoint registry test extension** —
   `tests/test_public_endpoints_registry.py` already enforces "every registered
   path resolves to a mounted route". Add the inverse: every route with
   `/api/.*/health` or `/api/.*/heartbeat` pattern that is NOT in PUBLIC_ENDPOINTS
   triggers a test warning (not failure — some health endpoints are intentionally
   admin-only, like `/api/channels/health`). Reviewer must explicitly mark
   `# health-private: <reason>` in the route handler to silence the warning.

**GOTCHA:**

- The test mock `_build_app_with_db_pool()` in
  `backend/tests/unit/app/routers/test_channel_health.py` is the canonical
  pattern for new router unit tests. It is **intentionally minimal** — it
  does not mount middleware. That is correct for unit tests of router logic.
  The bug class is the *absence* of a complementary integration layer, not
  the unit test pattern itself.
- `router_manifest.py` has a SCAR comment at the top referring to PRs
  #54/#55/#60 ("registered routers only in include_routers() but not
  include_light_routers()"). Sprint 1.B Sprint 1.B PR #422 is a **regression**:
  same scar class, different surface. The manifest was created to "make this
  structurally impossible to repeat" — but only for the symmetric case of
  routers added to one include function but missed in the other. It does NOT
  catch routers added ONLY to the manifest with no include_router call at all.
- `HybridAuthMiddleware.__init__` logs `Public Endpoints: {len(self.public_endpoints)}`
  at FastAPI startup. After PR #423 the count went from N to N+4. The log line
  is grep-able as a sanity check after every public-endpoint PR — but only
  on Fly machines, not CI.
- Required CI checks (E2E + MCP + Frontend + Detect Secrets) did NOT catch
  any of the 3 issues. E2E Tests touches frontend only; backend route mounting
  drift is not exercised. Adding the 3 antibody tests above costs ~50ms each
  in CI, no infra needed.

Sprint timeline reference (Sprint 1.B Era Post-Agentica, 2026-05-02):
- 11:30 UTC PR #422 merged → deploy success → 401
- 12:50 UTC PR #423 (public_endpoints) merged → deploy success → 404
- 14:25 UTC PR #424 (router_registration) merged → deploy success → 200 ✅

Brainstorm artifacts: none yet (this entry is post-mortem). Future agents
implementing the antibody integration test should reference this scar as
a self-contained reproduction.

---

### ⚠️ STRUCTURAL: Untracked files lost when sibling automation switches branches mid-session (2026-04-29, twice in 9h)

_Discovered: 2026-04-29 21:42 WITA (incident #1, FASE 1+2 doc-recovery from
context) and 22:30 WITA (incident #2, W0-A `.py` file recovery from
`.git/objects` dangling blobs) · Partial mitigation: WIP-commit-every-10min
pattern (MOS lesson 2026-04-29) · Permanent fix: TBD, requires identifying
producer at the automation layer_

**TRAUMA:** Long-running Claude Code sessions (Opus 4.7 max effort, 1M
context, multi-hour) accumulate untracked work product (`.py` files,
`.yaml`, `.md` design docs) in the working tree before reaching a commit
threshold. Sibling processes — `nuz-sync` watchdog, parallel `claude`
sessions, possibly `agent-*` subagents launched with
`--dangerously-skip-permissions` — perform `git stash` + `git checkout
<other-branch>` + `git pull` sequences automatically, dropping untracked
files from the working tree.

`git stash` without `-u` does NOT stash untracked files. `git checkout
<branch>` allows the operation to proceed even when untracked files would
be silently dropped IF the target branch doesn't have those paths.
Result: file-loss is silent at the git level, observable only by
inspecting the working tree post-switch.

Same-day recurrence with two distinct producers makes this STRUCTURAL,
not a one-off:

| Incident | Time (WITA) | Producer | Lost |
|---|---|---|---|
| #1 | 21:42 | `nuz-sync` watchdog auto-pull | 2 untracked design docs (`00_design_intent.md` + `01_innervation_matrix.md`, ~17 KB combined). Recovered from in-context conversation buffer; NOT recoverable from `.git/objects` because never `git add`-ed before drop. |
| #2 | 22:30:03 | Parallel Claude session checking out `nbe/resend-fallback-team-templates` | 4 untracked `.py` files (~26 KB). Recovered from `.git/objects` dangling blobs because the file content had been hashed during a previous `git add` attempt before the hijack. |

Concrete forensic sequence for incident #2 (full timeline in commit
`7decc8187` `99b_status_2026_04_29_w0a_branch_hijack.md`):

| Time | Event |
|---|---|
| 22:14 | Session-A starts FASE 3 W0-A on `feature/innervation-2026-04-29`. |
| ~22:25 | Session-A writes 4 untracked `.py` files (~26 KB) + 18/18 tests passing. |
| 22:30:03 | Sibling claude session: `git stash` (tracked-only) + `git checkout main`. Tracked edits land in `stash@{0}` as `innervation-wip-pre-NBE`. |
| 22:30:06 | Same sibling: `git pull origin main --ff-only` + `git checkout nbe/resend-fallback-team-templates`. The 4 untracked `.py` files are silently dropped from working tree (target branch doesn't carry those paths). |
| ~22:31 | Session-A's next bash command runs into `cd: no such file` because `apps/cell` symlink resolution is now under a different branch's worktree shape. |
| 22:32 | Session-A diagnoses via `git reflog` + `git fsck --dangling --no-reflogs` and recovers all 4 files from `.git/objects` to `/tmp/innervation-recovery-20260429_223214/`. |
| 22:42 | Path B atomic restore + WIP commit `3980a1403` + push to origin in <30s window. |

**ANTIBODY (partial — permanent fix pending):**

1. **WIP-commit-every-10min policy** (MOS lesson saved 2026-04-29,
   importance 8): every long-running session SHOULD commit a "WIP
   checkpoint" to its feature branch every ~10 minutes whenever
   untracked files exist in the working tree. Committed objects are
   reachable from the branch ref, NOT subject to checkout silent-drop.
   Pattern (in shell, single atomic batch — NEVER as multiple separate
   commands):

   ```bash
   if git ls-files --others --exclude-standard | grep -q .; then
     git add -A apps/<scope>/  # scope-limited, NOT bare `git add -A`
     git commit -m "WIP(<scope>): checkpoint $(date +%H:%M) — work in progress"
     git push origin "$(git rev-parse --abbrev-ref HEAD)"
   fi
   ```

2. **Push within 30 seconds of commit**: protects the local commit
   against further hijack OR Pro disk-loss. Do not run any Write/Read
   tool calls between `git commit` and `git push origin`.

3. **Pre-session check `ps aux | grep claude | wc -l`**: counts
   concurrent Claude processes. If >2 (current session + the
   `~/scripts/claude-max-usage-watcher.py` cron tick), STOP and ask
   Zero which processes to kill before starting work. Concurrent
   sessions are the documented vector of the 22:30 hijack.

4. **Recovery procedure documented for next time**: dangling-blob
   extraction is reliable for content that has been `git add`-ed at
   least once OR written via tools that hash content into the
   object store. To recover any blob from this incident class:

   ```bash
   git fsck --dangling --no-reflogs 2>&1 | grep "dangling blob"
   for h in <hash>; do
     git cat-file -p "$h" > /tmp/recovery-$(date +%s)/<filename>
   done
   ```

   Same-hour recovery is reliable. After ~14 days, `git gc` may
   prune dangling blobs unrecoverably.

**ANTIBODY (TBD, requires investigation):**

- Identify which sibling process performed the 22:30 branch-switch.
  Suspects (per `ps aux` snapshot at 22:32):
  - PID 79949 (long-running Opus, 26 min CPU consumed since 13:19) —
    candidate #1. The session that wrote the FASE 1+2 docs is likely
    still resident.
  - PID 42807 (long-running, since 13:01) — candidate #2.
  - `agent-B-nba`, `agent-D-p02-fase2`, `agent-E-p05-fase2` (wave-2/wave-3
    team agents, `--dangerously-skip-permissions`) — any could have
    issued the checkout via filesystem MCP.
  - Bash background `until` loop watching deploy `410da34b` (PID 29764)
    is a poll, not a checkout actor.
- Until identified, the trigger condition cannot be eliminated.
- Future investigation directions: pre-checkout git hook that refuses
  to switch when untracked files exist AND the parent process is not
  the session that created them; mutex / lockfile on `feature/*`
  branches during long-session work.
- **Innervation Genoma exclusion (2026-04-30)**: `nuz-sync` is
  explicitly NOT enrolled in `apps/organism/organism/organs_registry.yaml`
  (file renamed 2026-05-08 IG-3 from `genome.yaml`)
  despite being a critical Pro organ. Rationale: this scar identifies
  sibling automation as the most likely producer of branch-hijack
  incidents, and `nuz-sync` is the prime suspect for incident #1
  (auto-pull on git changes during long Claude sessions, fired inside
  its 5-min cron tick window at 21:42). If the Organism Supervisor
  were to auto-recover `nuz-sync`, a recovery loop during a
  hijack-in-progress could amplify the file-loss blast radius. Manual
  operator restart only until the producer is conclusively identified
  and isolated. Quarantine documented in PR W1.0 (`chore/innervation-w1-cleanup-2026-04-30`).

**GOTCHA:**

- `git stash list` shows incident #1's stash with descriptive label
  (`feature-innervation-temp-2026-04-29`) but does NOT contain the
  actually-lost design-doc files. The stash only saved tracked-but-dirty
  files (CLAUDE.md, lint, etc.) — the untracked design docs (`00`+`01`
  ~17KB) were dropped between the auto-stash and the checkout. **A stash
  whose label is "temp-<branch>" is not a guarantee that all WIP work
  for that branch is in it.** Always cross-check `git fsck --dangling`
  output against the stash patch before assuming "stash has my work".

- Recovery via `git fsck --dangling --no-reflogs` only works if the
  file content was hashed into `.git/objects` at some point. Files
  written to disk and never `git add`-ed do NOT have a blob there.
  Incident #1 design docs (00 + 01) had been written via the `Write`
  tool but were never `git add`-ed before the 21:42 stash-and-pull;
  they were unrecoverable from objects (had to be reconstructed from
  conversation context). Incident #2 `.py` files HAD been `git add`-ed
  during the in-progress test cycle, so blobs existed and recovery
  was clean.

- Recovery dirs in `/tmp/innervation-recovery-*` are volatile (cleared
  on macOS reboot). Always copy critical recovery artifacts into a
  committed branch within minutes, not hours. The Path B sequence in
  commit `3980a1403` is the canonical idempotent recipe.

- `nuz-sync watchdog` history (per `~/logs/nuz-sync/last-run` mtime
  1777473151 = 22:32:31 UTC) shows the watchdog ran AFTER the 22:30
  hijack — so it isn't the producer of incident #2. It IS likely the
  producer of incident #1 (21:42 was inside its 5-min cron tick
  window). Two different producers, same symptom = structural class.

- `_writer="pro"` field in `shared/escalations_pro.jsonl` confirms the
  hijack was a same-machine concurrent session, not Air→Pro federation.

Memory references: MOS records the 22:30 timeline as decision/discovery
2026-04-29 importance 9 ("Innervation Track C3 W0-A interrupted by
branch hijack — Path B executed, WIP commit 3980a1403 has 9 files / 1029
insertions / 18 tests passing, full forensics in 99b_status_*"). The
21:42 incident reference: `02_dispatch_resilience_log.md` § 6 in the
innervation FASE 1 docs.

---

### ⚠️ STRUCTURAL: Backend `/health` masks `app.state.startup_failed` (2026-04-29)

_Discovered: 2026-04-29 audit zero-crash · Severity: P0 · Workaround: TBD (intervention plan P0-0 in `docs/audits/2026-04-29-zero-crash-audit/11_brainstorms/P0-0_health_endpoint_classify.md`)_

**TRAUMA:** `apps/backend-rag/backend/app/setup/app_factory.py:114-118` catches RuntimeError from critical service initialization, sets `app.state.startup_failed=True`, and returns. `apps/backend-rag/backend/app/routers/health.py:48-55` defines `_check_startup_failed()` helper, but `health_check()` at lines 147-266 NEVER CALLS IT.

A backend with broken critical services keeps returning HTTP 200 from `/health`. **Fly auto-restart only fires on non-2xx**. So a deterministically-broken backend stays "healthy" forever — silent crash. The 2026-04-29 03:11Z incident (kita.balizero.com login broken, machine `d894e65bede478` "in restart loop") is exactly this pattern — could only be detected via downstream login probe.

**Compounding (BS-0b):** `apps/cell/cell/core/pulse.py` classifies green based on `reading.reachable and reading.status_code == 200` — Cell's own nervous system has the same blind spot.

**ANTIBODY (proposed):** P0-0 brainstorm — call `_check_startup_failed(request.app)` at top of `health_check()`, return 503; track `startup_started_at` in `app_factory.py` with 180s warmup deadline; `pulse.py` classify on body status field (`unhealthy/startup_failed/failed/down` → red, `degraded/initializing/warming` → yellow).

**GOTCHA:** Removing `raise` in `_init_critical_services` (graceful degradation per Symbiosis Law 4) is essential. Without it, uvicorn won't bind 8080. Warmup 180s assumes RAG cold-start ≤90-120s.

---

### ⚠️ STRUCTURAL: EventBus is PG LISTEN/NOTIFY but Symbiosis docs say Redis Streams (2026-04-29)

_Discovered: 2026-04-29 audit zero-crash via NotebookLM NB-1 ground-truth · Severity: P0 · **Mitigated 2026-04-29 phase 1 via PR #342** (commit `0062090c4`); **phase 2 callsite refactor + DB triggers shipped 2026-04-29 in feat/p0-2-fase2-callsite-refactor** (Track C wave 3); per-handler ack + pruning cron remain for a future phase 3._

**TRAUMA:** `SYMBIOSIS.md` Law 4 promises "Redis Streams + consumer groups, if Redis is down ogni agente funziona in isolamento". Reality (per NB-1 source citations): EventBus uses **PostgreSQL LISTEN/NOTIFY**. See `apps/backend-rag/backend/services/events/__init__.py` PG_CHANNEL_MAP (`practice_changed`, `client_changed`, `compliance_alert`, `lkpm_ingest_completed`, `war_room_event`, `intel_event`, `cognitive_event`). Listener `_RECONNECT_DELAY_S = 5`.

When PG listener disconnects (5s window), every NOTIFY is **silently lost** — pg_notify is volatile, no queue. Symbiosis Law 4 promise is wrong twice: there's no Redis to be down, AND PG NOTIFY has no durability layer.

**ANTIBODY (phase 1, SHIPPED PR #342 2026-04-29):**

* New `events_outbox` table (migration 144, applied on prod 2026-04-29 10:30 UTC, `execution_time_ms=33`). `BIGINT GENERATED BY DEFAULT AS IDENTITY` PK, JSONB payload, partial indexes on `(created_at) WHERE consumed_at IS NULL` (fast replay) and `(consumed_at) WHERE consumed_at IS NOT NULL` (fast prune). Squawk lint cleared via per-statement `-- squawk-ignore: require-concurrent-index-creation` / `require-timeout-settings` directives — legitimate suppressions on a brand-new empty table where the warned-about lock contention cannot occur.
* New helper `apps/backend-rag/backend/services/events/outbox.py` exposes `publish` / `acknowledge` / `replay_unconsumed` / `prune_consumed` / `get_unconsumed_count` / `validate_channel`. `publish()` writes to outbox + fires `pg_notify($1, $2)` parameterised (NOT via `quote_ident($1)` — that produces a quoted identifier `"channel"` which is the SQL-identifier syntax, **wrong** for the `pg_notify(text, text)` function signature). `_outbox_id` is injected into the NOTIFY payload so consumers can ack idempotently. `replay_unconsumed()` re-dispatches to in-process handlers via caller-provided `dispatch_fn` and auto-acks on success.
* `EventBus._replay_outbox_on_reconnect` is invoked from `_connect_and_listen` after `add_listener` for each PG channel, before the keep-alive loop. Best-effort — a failure on any single channel is logged and the listener proceeds.
* 20 unit tests (16 `test_outbox.py` + 4 `test_event_bus_replay.py`) cover atomicity, `_outbox_id` injection, ack idempotency, replay ordering / max-age filter / continue-on-handler-error, channel-name validation, prune-only-consumed, EventBus reconnect-hook contract.

**Phase-1 limitation (documented):** `replay_unconsumed` auto-acks immediately after `dispatch_fn` returns. If the handler crashes mid-dispatch, the row is still marked consumed. Phase 2 introduces per-handler ack so handler crashes do NOT lose the event.

**ANTIBODY (phase 2, SHIPPED 2026-04-29 in feat/p0-2-fase2-callsite-refactor):**

* `EventBus.emit_pg` now delegates to `outbox.publish` (local import in `event_bus.py` to avoid circular package init), so any future Python caller of `emit_pg` automatically writes to `events_outbox` before the volatile `pg_notify` fires. The 8 KB payload-size warning is preserved, and the `db_pool=None` early-return path stays silent (no publish attempt). Behavior change is observable only to the listener-disconnect window: events that would have been silently dropped now land in `events_outbox` and are replayed by `_replay_outbox_on_reconnect` on the next listener reconnect.
* New SQL migration `db/migrations_v2/146_eventbus_triggers_use_outbox.sql` redefines six trigger functions (`notify_practice_change`, `notify_client_change`, `notify_compliance_alert`, `notify_war_room_event`, `notify_intel_event`, `notify_cognitive_event`) so each one builds the same JSONB payload as before (preserving consumer-visible keys exactly) and then runs `INSERT INTO events_outbox (channel, payload) VALUES (…) RETURNING id INTO outbox_id` followed by `pg_notify(channel, (payload || jsonb_build_object('_outbox_id', outbox_id))::text)` inside the original user transaction. The migration is wrapped in `CREATE OR REPLACE FUNCTION` so it is idempotent. Triggers themselves are NOT dropped — they keep pointing at the same function names. The `-- === ROLLBACK ===` section restores the pre-146 function bodies (still pg_notify-only, byte-identical to migrations 075/076/112/113/114).
* 12 new tests in `backend/tests/services/events/test_outbox_callsite_integration.py` cover: `emit_pg → outbox.publish` delegation, no-raw-pg_notify regression guard, payload round-trip without mutation, 8 KB warning preservation, `db_pool=None` no-op, 100-event disconnect-then-replay round-trip via the existing reconnect hook, `_replay` flag propagation, migration 146 file existence + every trigger-backed channel covered + `_outbox_id` injection per channel + rollback-marker present + out-of-scope channels (`wr2_status_change`, `partner.commission_changed`) NOT touched + war_room payload shape preserved (regex-tolerant).

**Phase-2 limitation (documented):** `replay_unconsumed` still auto-acks immediately after `dispatch_fn` returns, inheriting the phase-1 contract. If a handler returns successfully but silently drops the payload, the row is marked consumed and the event is gone. Per-handler ack moves to phase 3. Consumers must be idempotent on the `_outbox_id` key.

**Channels NOT in scope for phase 2:**

* `lkpm_ingest_completed` — no DB trigger; emitted by Python import scripts after bulk OSS receipt ingest. Those scripts already use `EventBus.emit_pg` (or could), so they pick up the new durable path automatically without a SQL migration.
* `wr2_status_change` (migration 138) — separate consumer (`wr2_supervisor.py` launchd daemon), not registered in `PG_CHANNEL_MAP`, the EventBus reconnect hook would never replay it. Left untouched intentionally; documented in the migration 146 header.
* `partner.commission_changed` (`services/crm/partners/events.py`) — dotted channel name fails `validate_channel` (`^[A-Za-z_][A-Za-z0-9_]{0,62}$` rejects `.`); also not in `PG_CHANNEL_MAP`. Out of scope; documented in the migration 146 header. If a future change registers it in PG_CHANNEL_MAP it must also be renamed to `partner_commission_changed` first.

**ANTIBODY (phase 3, pending future PR):** per-handler acknowledgment so a crashing handler does NOT lose events; pruning cron LaunchAgent on Pro calling `prune_consumed` daily (30-day retention).

**Decision (resolved 2026-04-29):** went with option (a) — keep PG LISTEN/NOTIFY + Outbox. SYMBIOSIS.md still says "Redis Streams"; that needs a doc update in a separate PR (low priority — code-as-truth wins). Migrating to Redis Streams (option b) was rejected as a major architectural change too risky for an audit fix.

**GOTCHA:**

- After phase 2: every PG_CHANNEL_MAP channel except `lkpm_ingest_completed` has a refactored DB trigger in migration 146 that writes to `events_outbox` BEFORE pg_notify. `lkpm_ingest_completed` has no DB trigger (Python emitter only) and now flows through the refactored `EventBus.emit_pg` instead. The four out-of-scope channels (`wr2_status_change`, `partner.commission_changed`, plus any channel not in PG_CHANNEL_MAP) remain volatile by design; see the channel list in the phase-2 ANTIBODY block above for the rationale.
- The trigger function in migration 146 wraps the INSERT INTO events_outbox + pg_notify in the SAME implicit transaction as the user's INSERT/UPDATE. If the user's transaction rolls back, both vanish (Postgres queues NOTIFY until COMMIT, and the outbox row stays invisible to other connections via MVCC). If the user's transaction commits but the listener is disconnected, the outbox row stays unconsumed and is replayed on listener reconnect.
- Consumers must be idempotent for replay safety. The replay path injects `_replay: True` and `_outbox_id` into the payload; consumers can dedup on the `_outbox_id` if they need at-most-once semantics. Phase 3 adds per-handler ack so a crashing handler does NOT auto-consume the event — until then, `replay_unconsumed` auto-acks on `dispatch_fn` return regardless.
- The legacy `_schema_versions` table on prod has only 6 rows (last entry `129_crm_guardian` from 2026-04-24). The active runner uses `schema_migrations` (88 rows, top entry `144_events_outbox`). **Future agents validating "did migration N apply?" must query `schema_migrations`, NOT `_schema_versions`** — querying the wrong table will return NOT_FOUND for every recent migration and look like a deploy failure.
- `pg_notify($1, $2)` with parameterised channel is injection-safe. Defense-in-depth: Python-side `validate_channel` regex `^[A-Za-z_][A-Za-z0-9_]{0,62}$` rejects suspect names early. Do NOT add `quote_ident($1)` — that produces SQL-identifier syntax wrong for the function arg.
- Pruning policy (events_outbox unbounded): still NOT enforced after phase 2. Phase 3 ships the cron. Until then, manually run `await prune_consumed(conn, older_than_days=30)` if monitoring shows table growth.
- Migration 146 must apply on the FRESHLY-DEPLOYED image (not the previous one) — same gotcha that caused the SQL v2 deploy-ordering scar (cf. `run-sql-v2-migrations-post-deploy` job in `fly-deploy.yml`). The job already covers SQL v2 migrations idempotently, so 146 will be picked up by the post-deploy step on first deploy after merge with no manual `workflow_dispatch` needed.

---

### ⚠️ STRUCTURAL: 53 LaunchAgents Pro, only 7 (13%) have KeepAlive=true (2026-04-29)

_Discovered: 2026-04-29 audit zero-crash via Codex empirical scan · Severity: P0 · Workaround: TBD (P0-3 mass plist audit)_

**TRAUMA:** `~/Library/LaunchAgents/com.{nuzantara,balizero,cell}.*.plist`. Codex counted 53 project plist:
- 7/53 (13%) have `KeepAlive=true`
- 11/53 (21%) have NO KeepAlive directive at all
- 5/53 (9%) missing `EnvironmentVariables` (VADEMECUM §11 violation)
- 6/53 (11%) logging to `/tmp/` (lost on reboot, breaks Sentinel)

Critical daemons that should KeepAlive=true but don't include `com.cell.organism` (the actual organism cell), `com.balizero.nlm-bridge`, `com.balizero.post-publish-poller`. Cell's crisis-recovery hierarchy assumes daemon respawns within 10s — only works with KeepAlive=true.

**ANTIBODY (proposed):** P0-3 — `scripts/lint_launchagents.sh` + auto-patcher `scripts/patch_launchagents.sh --dry-run` + PreToolUse hook. Auto-classifies daemon-vs-cron based on `StartInterval`/`StartCalendarInterval` presence (cron) vs absence (daemon).

**GOTCHA:** `RunAtLoad=true + no schedule` is ambiguous (daemon-on-boot vs one-shot-on-load) — manual review. Each plist gets `.pre-vademecum-audit` backup before patching.

---

### ⚠️ STRUCTURAL: SQL v2 migrations duplicate numbers `129_*` and `130_*` (2026-04-29)

_Discovered: 2026-04-29 audit zero-crash via Codex empirical scan · Severity: P0 · Workaround: rename non-applied duplicate (P0-7)_

**TRAUMA:** `apps/backend-rag/backend/db/migrations_v2/` has TWO migration files sharing number `129` and TWO sharing `130`. Runner (`backend/db/migration_manager.py`) tracks via `migration_number` column in `_schema_versions` — duplicates cause undefined apply order and silent corruption risk.

**ANTIBODY (proposed):** P0-7 — compare contents + git history, identify which is in `_schema_versions` (applied), rename the not-applied to next-available number. CI guardrail `lint-migration-numbers.yml` prevents regression. Migration runner asserts uniqueness in `discover_migrations()`.

**GOTCHA:** If both have been applied (unlikely): Zero handoff. Renaming changes file hash but not SQL content — apply order must be re-verified.

---

### ⚠️ STRUCTURAL: Unknown agent overwrites loaded LaunchAgent plist files with their own JSON dump (2026-04-29)

_Discovered: 2026-04-29 ~15:30Z during P0-3 audit · Severity: P0 · Status: Recovery automated, root cause UNKNOWN — escalation HIGH in `shared/escalations_pro.jsonl`_

**TRAUMA:** At `2026-04-29 15:09:15-17 WITA` an unidentified process truncated **51 of 54** project plist files in `~/Library/LaunchAgents/com.{nuzantara,balizero,cell}.*.plist`, replacing each plist XML with a tiny JSON fragment that is the value of *one* of the plist's own keys — typically `StartCalendarInterval` (e.g. `{"Hour":1,"Minute":0}`, 21 bytes) or `EnvironmentVariables` (e.g. `{"GH_TOKEN":"...","FIREWORKS_API_KEY":"...","HOME":"/Users/nuzantara",...}`, ~145-313 bytes). At `2026-04-29 16:05:18` the *same event repeated*: 50 plist re-corrupted (all but the 3 freshly-canary-tested ones) within a single second window. **Cycle ~56 minutes between waves.**

The signature exactly matches `plutil -convert json -o "$plist" -- "$plist"` or equivalent (`subprocess.run(["plutil","-extract","<key>","json"], stdout=open("$plist","w"))`) — a "read one key, write back the value as JSON, but truncate the file first because of `>` redirect" pattern. Grep across `~/scripts ~/Desktop/nuzantara ~/.cron-agent-python ~/.openclaw ~/.claude ~/.agent` for `plutil.*-convert`, `plutil.*>` redirects, `Library/LaunchAgents.*write_text`, etc., turned up **zero matches** — the producer is not a versioned shell/python script with a literal plutil invocation. Sentinel (`nuzantara-sentinel.py`, runs at 16:05), automap-watchdog (60s cycle, runs `automap_autofix.py`), launchagent-state-bridge.py (300s), zombie-hunter (60s), and system_doctor.py (4h) were all checked — all read launchctl but write only to `~/.agent/decisions/state/*.json`, not to plist files.

**Critical observation:** a canary plist NOT loaded in launchd (`com.balizero.canary-final`, file present, never bootstrapped) was NEVER corrupted across two waves. **The producer enumerates services *currently in `launchctl list`* and writes per-label.**

The on-disk corruption was masked for hours because launchd had loaded the *real* config at boot — `launchctl print gui/$(id -u)/<label>` still returned the full config from memory, so production behavior was unaffected. **Reboot would have lost 51 services**, including critical daemons (`com.cell.organism`, `com.balizero.nlm-bridge`, `com.balizero.post-publish-poller`, all WR2 producers) and CRON jobs (`com.balizero.intel.nightly`, `com.balizero.indexing-sweep.daily`, login-healthcheck, fly-restart-loop-detector).

**Secrets leaked into world-readable (mode 0644) plist files** during the event:
- `com.balizero.post-publish-poller.plist` → `GH_TOKEN` (`ghp_iZ4V…`, 40 chars), `FIREWORKS_API_KEY` (`fw_GXzCU…`, 25 chars), `SCRAPER_API_KEY` (`internal-…`, 20 chars)
- `com.balizero.post-publish-webhook.plist` → `POST_PUBLISH_SECRET` (26 chars)
- `com.cell.organism.plist` → `GOOGLE_API_KEY` (`AIzaSy…`), `CELL_TELEGRAM_BOT_TOKEN`, `FLY_API_TOKEN` (FlyV1, 687 chars), `CELL_DATABASE_URL` (postgres password embedded)
- `com.nuzantara.dlq-autopilot.plist` + `com.nuzantara.sentinel.plist` → `TELEGRAM_BOT_TOKEN` (shared bot, same as `cell.organism`)

Backups of the corrupt blobs are kept in `~/p0-3-recovery/plist_corrupt_backup/` for forensic analysis. Rotation plan in `~/p0-3-recovery/secrets_rotation_plan.md` (manual approval required per secret class).

**ANTIBODY (recovery, automated):**

The `~/p0-3-recovery/reconstruct_plist.py` script parses `launchctl print gui/501/<label>` output (which has the in-memory config in launchd's text format) and emits a valid plist XML using `plistlib.dump`. Each output is validated with `plutil -lint` before it is moved into `~/Library/LaunchAgents/`. **Atomic mv preserves the live launchd state** — no `launchctl unload`/`load` needed; the next boot picks up the rebuilt plist while the running process is unaffected. End-to-end recovery for 53/54 plist takes ~30s on Pro and produces zero service flap (verified via PID snapshot diff).

The 1 unrecoverable plist (`com.nuzantara.qwen-code-review.plist`) was never loaded in launchd, has no fallback in `~/Desktop/nuzantara/infra/launchagents/`, and is not referenced by anything currently running — the corrupt 22-byte file was moved to `~/p0-3-recovery/com.nuzantara.qwen-code-review.plist.removed`.

**ANTIBODY (prevention — partial, producer still UNKNOWN):**

The producer of the corruption has not been identified, but two preventive layers are now in place (2026-04-29 18:50 WITA):

1. **Filesystem hardening** — all 54 project plist were chmod'd read-only:
   - 5 plist with leaked secrets (`com.cell.organism`, `com.balizero.post-publish-poller`, `com.balizero.post-publish-webhook`, `com.nuzantara.dlq-autopilot`, `com.nuzantara.sentinel`) → `0400` (owner read only, no world read, no write at all). Stops both *write* and *read by other users*.
   - 49 remaining plist → `0444` (world read OK, no write). Stops only *write*.
   - Verified: 54/54 still plutil-lint OK, `launchctl load/unload` still works, `> "$plist"` redirect now fails with `Permission denied`. To legitimately edit a plist: `chmod u+w "$plist"`, edit, restore mode.
   - Memory ID 1879 has the operational note.

2. **fs_usage audit** active since 19:33 WITA (PID 10080, capture log `~/p0-3-recovery/fs_usage_trap/capture-20260429-193348.log`) — captures any future `WrData`/`O_TRUNC`/`truncate` on project plist with PID + parent PID. To inspect: `grep -E "WrData|O_TRUNC|truncate" ~/p0-3-recovery/fs_usage_trap/capture-*.log`. To stop: `sudo pkill -f "fs_usage -w -f filesys"`.

The originally-suspected **56-minute recurrence cycle was refuted** — by 18:44 WITA (>3.5 h after the 16:05 second wave) no third wave had fired, even before chmod was applied. Most likely scenario: the writer was a one-shot AI agent action (Antigravity/Cline/parallel Claude Code session via filesystem MCP), not a recurring daemon.

If recovery is ever needed again: `python3 ~/p0-3-recovery/reconstruct_plist.py && for src in ~/p0-3-recovery/plist_reconstructed/com.*.plist; do chmod u+w "$HOME/Library/LaunchAgents/$(basename "$src")" 2>/dev/null; install -m 0444 "$src" ~/Library/LaunchAgents/; done` (note the `chmod u+w` step required because of the new hardening).

The original P0-3 audit (mass `KeepAlive=true` enforcement on the 54 plist) remains **paused**: the lint+patch scripts (`scripts/lint_launchagents.sh`, `scripts/patch_launchagents.sh`) need a `chmod u+w` step before patching now. Resumption tracked separately.

**GOTCHA:**

- The producer enumerates **launchd-loaded services only**. A new plist that has never been bootstrapped is left untouched — useful as a canary, useless as production state.
- `plutil -lint` on a corrupted plist returns 1 (failure) but launchd still serves the cached XML from boot. Don't equate "plutil-lint OK" with "service running properly".
- Most-likely remaining candidates (none ruled out): (a) a parallel AI-agent session (Antigravity/Cline/Codex/Gemini/Claude Code subagent) issued the lethal command via filesystem MCP without logging to terminal history — supported by Antigravity network activity at 15:09:05–13 (10 s before corruption); (b) a not-yet-discovered binary running with `plutil -convert -o file file` semantics; (c) launchd-internal race triggered by simultaneous `launchctl list` from many processes. The originally-noted 56-min cycle hypothesis is now **refuted** (no third wave fired by 18:44 WITA, even before hardening).
- The P0-3 lint script is conservatively read-only — only uses `plutil -extract <key> raw 2>/dev/null` redirecting STDERR. The patch script uses `plutil -insert/-replace` directly on the file (in-place, atomic). NEITHER produces the corruption signature.
- After chmod hardening, any future recovery / `patch_launchagents.sh --apply` MUST `chmod u+w` the plist first — otherwise `plutil -insert/-replace` will fail silently with `Operation not permitted`. The lint script (read-only) is unaffected.
- Cross-LLM brainstorm artifacts: `/tmp/kakuro-S4-final-brainstorms/{codex,deepseek,gemini,notebooklm}.md` — DeepSeek's analysis is the most useful (Codex hit auth fail, Gemini hit rate-limit, NotebookLM CLI error).

---

## Archived

Resolved scars moved to [`cicatrix-scars-archive.md`](./cicatrix-scars-archive.md) (not auto-loaded per session). Currently archived:

- ✅ RESOLVED: OpenClaw MCP child apparent mortality = test artifact (2026-05-02)
- ✅ RESOLVED: Backend prod down — drive_poll_service called missing method on ServiceAccountDriveService (2026-04-29)
- ✅ RESOLVED: Atlas migrate-lint paywalled in v0.38 — pivoted to Squawk (2026-04-26)
- ✅ RESOLVED: SQL v2 migrations apply on OLD image, not the freshly-built one (2026-04-26 → 2026-04-29)
- ✅ RESOLVED: Deploy crash before health check went unalerted (Air A3, 2026-04-18)
- ✅ RESOLVED: Dockerfile cell-core missing (PR #56 → PR #62 → monorepo workspace promotion)
