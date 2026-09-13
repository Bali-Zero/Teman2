gate: fresh Opus 5, outside the contribution chain
sha: fff7cd26e8
date: 2026-09-11
verdict: PASS-WITH-CONDITIONS

# RC2 — training-data government-fee gate: final on-disk gate

Lane RC2 of the Zantara WA-bot mandate. Branch `agent/nuzantara/backend-rag/rc2-split-corpus-purge`,
1 commit ahead of `origin/main`: `fff7cd26e8 fix(bot): refuse government-fee figures at training-data ingest`,
plus the staged `evidence/2026-09/agent-nuzantara-backend-rag-rc2-split-corpus-pur-870c5354/brief.yml`.
This gate did not write the code. Everything below was EXECUTED in this window; nothing is asserted.

**Condition for arming (one, documentation-only — no code change required):** record the
chunk-boundary residual, with the 225-char measurement and the fact that `--dry-run` is itself
per-chunk, in the PR body or in `brief.yml`. The diff is correct for the artefact it writes.

---

## 0. Pre-flight

    ls "$CLAUDE_PROJECT_DIR/infra/claude-hooks/data_plane_guard.py"
    -> "/infra/claude-hooks/data_plane_guard.py": No such file or directory (os error 2)

`$CLAUDE_PROJECT_DIR` is EMPTY in this session, so the path collapsed to `/infra/...`. That is an
environment artefact, not the fact the stop-condition names. Re-run against the real checkouts:
`infra/claude-hooks/data_plane_guard.py` exists (23k) in the main checkout, in this session's
worktree and in the RC2 worktree. **Not the stop condition — proceeded.**

## 1. The diff

    git -C <wt> diff --stat origin/main...HEAD
    -> 5 files changed, 365 insertions(+), 8 deletions(-)
       backend/services/misc/curated_qa_government_fee_detector.py      |  27 ++-
       backend/tests/unit/scripts/test_training_data_government_fee_gate.py | 232 +++
       scripts/ingest_license_procedures.py                             |  15 +-
       scripts/ingest_single_file.py                                    |  10 +
       scripts/reingest_training_data.py                                |  89 +-

Full diff and `git show :<brief.yml>` read in their entirety.

The shape: the detector gains `text_is_refused()` — the no-marker form of `row_is_refused()` — and the
ruling sentence is extracted into one `_RULING` constant. The three scripts that write local
training-data markdown into `training_conversations_hybrid` call it on EVERY chunk before embedding.
`reingest_training_data.py` also gains `--dry-run` and an `argparse` `main()`.

## 2. The tests

    cd apps/backend-rag/backend && PYTHONPATH=. ../.venv/bin/pytest <file>

| file                                                                                   | result        |
| -------------------------------------------------------------------------------------- | ------------- |
| `backend/tests/unit/scripts/test_training_data_government_fee_gate.py` (new)           | **11 passed** |
| `backend/tests/unit/services/test_curated_qa_government_fee_gate.py` (existing, #5615) | **21 passed** |
| both together                                                                          | **32 passed** |

`git ls-files | grep government_fee` returns exactly three paths: the detector and those two test files.

## 3. Mutation — the test is load-bearing

The gate call inside `reingest_files()` is `reingest_training_data.py:224`; the identical call inside
`dry_run()` is `:160`. Only `:224` was mutated, so the red can have only one cause.

    sha256 before: 698a203201cce48bc5c29185519a94ff15caadaefd827cbecce7fb64c6f91bd9
    sed -i '' '224s/.*/            reason = None/'   # a `cp` backup was taken first
    git status --short  ->  M scripts/reingest_training_data.py
                            A evidence/.../brief.yml
    pytest test_training_data_government_fee_gate.py
    -> 1 failed, 10 passed
       FAILED test_reingest_never_embeds_or_upserts_a_refused_chunk
       AssertionError: assert ['- Jasa Pend...l inclusive.'] == ['Bali Zero q...

The red is the right red: with the gate removed, the itemised chunk reaches the embedder.

**Byte-exact restore:**

    git checkout -- scripts/reingest_training_data.py
    sha256 after:  698a203201cce48bc5c29185519a94ff15caadaefd827cbecce7fb64c6f91bd9   # identical
    git status --short  ->  A evidence/.../brief.yml        # the staged brief.yml ALONE
    pytest test_training_data_government_fee_gate.py -> 11 passed

Nothing was committed, pushed, or written in any other worktree.

## 4. Detector byte-compat — no existing caller changed

    git -C <wt> diff origin/main...HEAD -- .../curated_qa_government_fee_detector.py

The only change to `row_is_refused()` is that its last two string literals become `+ _RULING`, where
`_RULING` is those same two literals concatenated. Reasoned byte-identical; then MEASURED. A scratch
script loaded `origin/main`'s detector via `importlib` alongside HEAD's and compared `row_is_refused`
across 18 hand-built rows (itemised ID/EN, fee-without-figure, our single price, reviewed+note,
reviewed+blank-note, unreviewed+note, `immigration fee`, `tarif resmi`, `tassa governativa`,
`biaya visa`, `official fee`, `state fee`, `penerimaan negara bukan pajak`, `spese governative`,
`answer=None`, `answer=42`, missing key, innocent text):

    A) row_is_refused byte-compat over 18 rows: mismatches=[] refused=8
    A) sample reason identical: True

The existing 21-test curated_qa gate file is the standing receipt and it is green. **No behaviour
change for any existing caller.**

## 5. `--dry-run` safety

Read first: `dry_run()` imports `core.chunker` and the detector only — no embedder, no BM25, no
`requests`, no `upsert_point`. Module level reads `QDRANT_URL`/`QDRANT_API_KEY` via `os.getenv` with a
default and never fails on their absence, so the path needs **no credentials and no network** and was
therefore RUN, with `QDRANT_URL` pointed at an unroutable local port so any write would have errored:

    scripts/reingest_training_data.py --dry-run <synthetic scratch file>
    -> Created 1 chunks / REFUSED ... chunk 0: states a government-fee figure to a client
       (tokens: pnbp). Zero's ruling is ONE all-inclusive client-facing price ...
    -> DRY RUN: the government-fee gate refuses 1/1 chunk(s) in 1 file(s)      rc=0

No embedding call, no Qdrant write. The existing test
`test_dry_run_reports_refusals_and_never_embeds_or_writes` makes `upsert_point` raise and is green.

Then the brief's own cost claim, over the script's real 30-file list (read-only; `training-data/` is
gitignored and empty inside the RC2 worktree, so the files were addressed in the main checkout):

    -> DRY RUN: the government-fee gate refuses 37/761 chunk(s) in 30 file(s)   rc=0
       REFUSED lines: 37     File not found: 0

**`37/761` reproduced exactly.** Only aggregate counts are recorded here; no chunk text.

## 6. Lint

    apps/backend-rag/.venv/bin/ruff check <the 5 touched files>
    -> All checks passed!     (ruff 0.15.22)

## 7. Adversarial read

### (b) CHUNK-BOUNDARY EVASION — MANDATORY ITEM: the evasion is REAL

`scan_government_fee` calls `has_price_content()` on the WHOLE input string: the rule is
"a government-fee token and a money figure in the same input". On the curated_qa path the input is one
row's `answer`. Here it is a 1500-char chunk with 200-char overlap, and `chunker.py:173-178` shows the
overlap is **prepend-only** — chunk N+1 carries the last 200 chars of chunk N, chunk N carries nothing
of N+1.

So the evasion condition is exact: with token at `t`, figure at `f`, and a chunk boundary at `b`,
`t < b-200 <= b <= f` leaves the token alone in chunk N and the figure alone in chunk N+1.
The gate is defeated by a separation just over the OVERLAP, not over the chunk size.

Probe (synthetic markdown through the real `TextChunker(1500, 200)` and the lane's own
`government_fee_refusal`; never against real training-data, never against Qdrant):

    B) gap=  100 chunks=1 refused_chunks=[0] whole_doc_refused=True
    B) gap=  300 chunks=1 refused_chunks=[0] whole_doc_refused=True
    B) gap= 1000 chunks=1 refused_chunks=[0] whole_doc_refused=True
    B) gap= 1400 chunks=2 refused_chunks=[0] whole_doc_refused=True
    B) gap= 1600 chunks=4 refused_chunks=[]  whole_doc_refused=True
    B) gap= 2000 chunks=4 refused_chunks=[]  whole_doc_refused=True
    B) gap= 3000 chunks=5 refused_chunks=[]  whole_doc_refused=True

A second probe swept the token's offset within the chunk (prefix 0..1500 step 50) against the gap
(0..900 step 25), keeping only cases where the whole document is refused and NO chunk is:

    B2) minimal token->figure distance that evades EVERY chunk
        while the whole doc is refused: (225, prefix=1250, gap=200, 2 chunks)

**225 characters.** Just over the 200-char overlap.

**Is it NEW, or the detector's pre-existing window semantics?** Both halves have to be said:

- The SEMANTICS are pre-existing and #5615 accepted them knowingly — the detector's own docstring
  records that a proximity rule was calibrated at every window from 40 to 160 chars and REJECTED on
  its numbers (at most 8 of 9 offenders caught while blocking 11-13 compliant rows). The gate is
  deliberately whole-input co-occurrence, high-recall, refuse-by-default.
- The SURFACE is new. On curated_qa the window is a field an author chose; here it is a boundary a
  chunker imposes mechanically. Nobody picked it, and it can fall anywhere.
- The strongest attenuation, and it is real: the artefact stored and later retrieved IS the chunk, and
  no single stored chunk carries the split. The gate is coherent with what it guards.
- The residual that survives that attenuation: a source file teaching the split across a boundary is
  ingested in both halves, and a retrieval returning adjacent chunks can recompose it.
- The aggravation: `--dry-run` is per-chunk too, so the audit path is blind to the same file the
  per-chunk gate is blind to. `whole_doc_refused=True` above is this gate calling the detector on the
  whole document by hand — it is not something the shipped code does anywhere.

Verdict on (b): **MAJOR, as a named residual, not a blocker.** Before this PR the three scripts had no
gate at all, so nothing regressed; but "refuse-by-default" reads stronger than what is guaranteed, and
the brief — otherwise unusually candid, down to naming the ~5 compliant chunks it over-refuses — does
not name this. Hence the single condition.

### (a) Escape hatch / marker — CLEAN

`text_is_refused()` never reads `government_fee_reviewed`/`government_fee_review_note`; markdown has no
field to carry them and the reason offers none. `test_the_reason_offers_no_marker_that_markdown_cannot_carry`
asserts `REVIEW_FLAG_FIELD` is absent from the reason string. No bypass reachable from a file's content.

### (c) async / sleep in `ingest_license_procedures.py` — CLEAN

`time.sleep(0.3)` -> `await asyncio.sleep(0.3)` at `:219`, inside `async def ingest_files()`; `asyncio`
was already imported at `:12`. The pause is unchanged at 0.3s. `import time` stays USED at `:80`
(the synchronous retry inside `upsert_point`), so no F401 — ruff confirms. That retry's blocking
`time.sleep(wait_time)` is called from the async loop, but it is pre-existing and untouched by this
diff. The change was forced by ASYNC251, which pre-commit enforces on a touched file.

### (d) PII in prints/logs — CLEAN

The three refusal logs print `reason` (matched fee-vocabulary tokens + the ruling sentence), the file
path and the chunk index. **The chunk text is never logged.** The test corpus is synthetic consultant
dialogue with no client data. Nothing in this report carries client data either.

### (e) Any path where a refused chunk is still counted / embedded / upserted — NONE FOUND

In all three scripts the `continue` precedes the embedding call, the BM25 call and `upsert_point`.
`total_chunks += 1` sits after the `continue`, so refused chunks leave the upserted ratio alone;
`reingest_training_data.py` and `ingest_license_procedures.py` report them on their own line.
`point_id` stays keyed on `idx`, so a refusal leaves a hole rather than shifting later ids — the test
asserts exactly that (`ids stay keyed on the chunk index after a refusal`).

### Coverage — no fourth writer

Twenty-one `.py` files name `training_conversations_hybrid`. All but three are readers, routers or the
collection registry; `scripts/run_kg_extraction_all_collections.py`, `scripts/test_kbli_queries.py` and
`scripts/validate_nb_rag_v2.py` each have 0 write-shaped lines
(`points?wait` / `def upsert_point` / `requests.put`). The three gated scripts are the complete set.

---

## Findings, ranked

**BLOCKER** — none.

**MAJOR** — `scripts/reingest_training_data.py:127-136` and `:224`, with the twins
`scripts/ingest_single_file.py:164` and `scripts/ingest_license_procedures.py:178`: chunk-boundary
evasion at a measured **225 characters** of token-to-figure separation, unnamed in the brief and
invisible to `--dry-run`, which is per-chunk as well. Not a regression (no gate existed before); a
weaker guarantee than the wording implies. This is the one condition.

**MINOR** — `scripts/reingest_training_data.py:224-229`: the gate stops a WRITE; it does not delete.
A chunk that used to be overwritten by the reingest is now simply skipped, so a pre-existing point at
the same deterministic id `md5(f"{file_path}_{idx}")` survives untouched with whatever it held. The
brief concedes the other half is out of scope ("deleting the offending points fixes today and nothing
else"), and the lane's purpose is the regeneration, not the purge — but the purge must actually happen
elsewhere or today's offenders stay.

**MINOR** — `scripts/ingest_single_file.py:~200`: the only one of the three with no `total_refused`
counter. Its closing log is `DONE: {total_ok}/{len(chunks)} chunks upserted`, which keeps refused
chunks in the denominator, so a refusal reads as an anonymous failure. The other two scripts print
`REFUSED by the government-fee gate: N chunk(s)`.

---

## The brief's claims, reproduced

| claim                                                      | reproduced                  |
| ---------------------------------------------------------- | --------------------------- |
| mutation: 1 failed / 10 passed, then 11 passed             | YES, exactly                |
| touched test files 21 -> 32 passed                         | YES (11 new + 21 existing)  |
| `--dry-run` refuses 37 of 761 chunks over the 30-file list | YES, exactly                |
| `row_is_refused` byte-identical to `origin/main`           | YES — 18 rows, 0 mismatches |
| ruff clean on the touched files                            | YES                         |

Not verifiable from the diff, and recorded as such rather than as verified: the hand-cure of
`visa_011` (gitignored, outside the diff by design) and the "43 of 768 over all 31 files" figure, which
addresses files the script's own list does not name. The 37/761 that the lane actually gates on is
reproduced, and that is the number the gate turns on.

## Custody

Read-only except the single transient mutation, restored byte-exact and proven by matching sha256 and
by `git status --short` showing the staged `brief.yml` alone. No commit, no push, no branch, no other
worktree touched. Probe scripts and the synthetic markdown live in this session's scratchpad, outside
the repository, and were never run against real training-data or against Qdrant — with the sole
exception of the `--dry-run` READ of the 30 real files, from which only aggregate counts are recorded.
