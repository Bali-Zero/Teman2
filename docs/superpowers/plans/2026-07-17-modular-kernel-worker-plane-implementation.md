# Modular Kernel and Worker Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Review and implement the amended modular transactional kernel and dedicated worker plane through all six migration phases, then ship a bridge-only compatibility release, a separately gated receipt-activation release, and prove the production system under fault and rollback tests.

**Architecture:** Preserve the modular monolith and shared PostgreSQL transaction boundary while making route, workload, event, effect, and table ownership executable. Introduce a private same-image companion worker with dynamic PostgreSQL ownership grants and fencing, move durable workloads one at a time, and add per-subscription event receipts through a rolling-compatible global-ack bridge before a second protected release activates fan-out. Every cutover is reversible and advances the fencing generation in either direction.

**Tech Stack:** Python 3.11, FastAPI, asyncpg, PostgreSQL, Redis Streams, pytest, Ruff, MyPy, Fly.io, GitHub Actions, Docker, Next.js compatibility consumers, Claude Fable 5, Gemini 3.1 Pro High, GLM 5.2.

## Global Constraints

- Work only in `/Users/balizero/nuzantara/.worktrees/backend-rag-modular-worker-plane-impl` on branch `agent/air-m5/backend-rag/modular-worker-plane-impl` until the PR merge workflow begins.
- Treat `docs/superpowers/specs/2026-07-17-backend-modular-kernel-worker-plane-design.md` as the design authority. A phase plan may refine implementation details but may not weaken invariants I1-I7 or gates G1-G17.
- Use the repository virtual environment for every Python command: either activate `apps/backend-rag/.venv` first or invoke `apps/backend-rag/.venv/bin/python` explicitly, always with `PYTHONPATH=.` where package imports require it. Never use system Python.
- Follow strict RED-GREEN-REFACTOR: add one behavioral test, run it and record the intended failure, implement the minimum production change, rerun the focused test, then run the phase regression set.
- Use async I/O, full type annotations, absolute imports, structured logging, environment-backed configuration, and no client PII in prompts, logs, reviews, fixtures, or evidence.
- Do not change the frozen embedding model `text-embedding-3-small` or its 1,536 dimensions.
- Do not promise generic exactly-once delivery. Irreversible effects must declare `provider-idempotent`, `reconcilable`, or `non-reconcilable`; ambiguity must persist as `outcome_unknown`.
- A schedule run key is generation-independent: `(workload_name, scheduled_for)`. An effect key is derived from stable business identity and effect purpose, never a queue attempt or ownership generation.
- Database guards remain disarmed until every live owner heartbeat satisfies the compatibility build floor. Static environment flags never override the PostgreSQL grant.
- Before protected merge, every phase is code-only: repository tests, CI, deterministic simulations, and disposable PostgreSQL are allowed; live staging/production deployment, migration, secret or grant mutation, guard arm/disarm, ownership cutover, and observation are forbidden. Any phase-plan wording about a staging rehearsal is implemented pre-merge as a disposable/CI simulation only; the first live staging mutation occurs in rollout Task 2 from the protected-merged digest.
- Active goal/task `019f6f94-4863-7f62-acc7-16bc5a706f74` authorizes the in-scope implementation, protected Release-A compatibility and Release-B receipt-activation merges, live staging drills, receipt activation, ordered production cutovers, rollback-window observation, later deletion release, and protected evidence PRs in these plans. Every live mutation records that immutable reference and fails closed on any change of workload scope, target environment/app, merged digest, subscriber/provider capability, destructive migration behavior, or rollback policy.
- Run only one implementation worker at a time. The worker writes a review package; a fresh reviewer returns both spec-compliance and code-quality verdicts. Resolve every Blocking and Important finding before the next task.
- After each phase, run independent reviews with the actual `claude-fable-5`, `Gemini 3.1 Pro (High)`, and `glm-5.2` model routes. Save prompts, raw model proof, verdicts, synthesis, fixes, and rerun evidence under `docs/superpowers/reviews/2026-07-17-modular-worker-plane-phase-N/`.
- Commit each coherent task atomically with an English Conventional Commit and `Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>`. Never bypass hooks and never amend a pushed commit.
- Air-M5 performs only light local work. Fly deployment, Docker builds, PostgreSQL/Qdrant integration, resource measurement, and heavy production tests run through GitHub Actions or the Pro via `ssh pro`; never install those services on Air-M5.
- Keep `.husky/_` and `.superpowers/` out of commits. Update `.superpowers/sdd/progress.md` after every task and review gate.

---

## Execution Documents

- Phase 0: `docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-0.md`
- Phase 1: `docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-1.md`
- Phase 2: `docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-2.md`
- Phase 3: `docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-3.md`
- Phase 4: `docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-4.md`
- Phase 5: `docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-5.md`
- Merge, deployment, and production proof: `docs/superpowers/plans/2026-07-17-modular-worker-plane-production-rollout.md`

These phase plans are normative task-level runbooks subject to the stricter pre-merge mutation boundary above. Execute them in order. Phase 0 through Phase 3 require green tests, internal review, and a provisional independent three-model checkpoint before the next phase. Phase 4 Tasks 1–4 plus its compatibility panel form the compatibility checkpoint that gates Phase 5; Phase 4 remains open until Task 5 is delivered in the later deletion release. Final immutable Phase 0–5 and whole-branch review packets are generated only after the feature branch is rebased onto current `origin/main`. Review identity is the canonical review-input projection, not the moving repository `HEAD`: a later change to a covered input byte invalidates every affected packet and requires regeneration plus rerunning its panel, while commits that add only packet/raw-review/normalized-review/disposition attestations require integrity revalidation but no model rerun when `projection(H1) == projection(H0)`. Generated attestations are never recursive review inputs.

---

### Task 1: Freeze the implementation baseline

**Files:**

- Verify: `docs/superpowers/specs/2026-07-17-backend-modular-kernel-worker-plane-design.md`
- Verify: `docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-0.md`
- Record: `.superpowers/sdd/progress.md`

- [ ] **Step 1: Verify branch isolation and record the historical design base**

Run:

```bash
git status --short
git branch --show-current
git log --oneline -3
```

Expected: branch `agent/air-m5/backend-rag/modular-worker-plane-impl`; historical spec commit `af1621b16f` is present but is not treated as approval of the amended spec bytes; no tracked edits outside the implementation plan set.

- [ ] **Step 2: Commit the complete draft authority before rebasing**

Run after `git diff --check` and a path audit prove the draft contains only the amended spec, seven plans, rollout plan, and plan-review brief:

```bash
git add \
  docs/superpowers/specs/2026-07-17-backend-modular-kernel-worker-plane-design.md \
  docs/superpowers/plans \
  docs/superpowers/reviews/2026-07-17-modular-worker-plane-implementation-plan/00-review-brief.md
git commit -m "docs(architecture): draft modular worker plane delivery" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
git status --short
```

Expected: hooks pass; `.husky/_` and `.superpowers/` remain untracked and unstaged; the commit contains the amended spec and complete draft plan set, not review verdicts.

- [ ] **Step 3: Rebase before review and re-run the targeted pristine baseline**

Run `git fetch origin && git rebase origin/main`, resolve only branch-owned documentation conflicts, and record the new base/head. Any covered-byte change caused by conflict resolution must be visible in the later packet manifest. Then run:

Run:

```bash
cd apps/backend-rag
PYTHONPATH=. .venv/bin/python -m pytest -q \
  backend/tests/setup/test_router_registration_parity.py \
  backend/tests/setup/test_router_manifest.py \
  backend/tests/services/ingestion/test_legal_full_worker.py \
  backend/tests/services/events/test_outbox_stale_ttl.py \
  backend/tests/services/events/test_event_bus_replay.py \
  backend/tests/unit/services/test_wa_outbox_scheduler.py \
  backend/tests/unit/services/test_wa_outbox_worker.py \
  backend/tests/unit/services/ingestion/test_legal_full_ingestion_worker.py
```

Expected: `120 passed` on the rebased design branch before implementation changes. If `origin/main` legitimately changes the baseline count or direct-SQL inventory, investigate and record the exact diff rather than mechanically replacing the expected values.

- [ ] **Step 4: Reproduce the direct router-SQL baseline and preserve pristine raw G9 probe inputs**

Run:

```bash
LC_ALL=C rg -l '^\s*(from asyncpg(\.|\s)|import asyncpg(\s|$|,))' \
  apps/backend-rag/backend/app/routers --glob '*.py' | LC_ALL=C sort
LC_ALL=C rg -l '^\s*(from asyncpg(\.|\s)|import asyncpg(\s|$|,))' \
  apps/backend-rag/backend/app/routers --glob '*.py' | LC_ALL=C sort | wc -l
LC_ALL=C rg -l '^\s*(from asyncpg(\.|\s)|import asyncpg(\s|$|,))' \
  apps/backend-rag/backend/app/routers --glob '*.py' | LC_ALL=C sort | shasum -a 256
```

Expected: count `67` and SHA-256 `4002789a56196bd8cdce5440c1c596191f4e349ae6a91cb7e9f3d8ca8d24991a` unless the rebased-source investigation proves a reviewed upstream delta; copy the sanitized path list and command output into the Phase 0 evidence package. Before Phase 0 Task 1 exists, preserve only the pristine rebased HEAD, Pro/CI topology, sanitized runtime argv/readiness inputs, database/metrics endpoint identities, and intended synthetic request schedule; do **not** invent or check in a canonical G9 snapshot. Phase 0 Task 1 first creates and tests the fixed probe protocol/capture tool, then—before any behavioral migration—captures the canonical complete API/RAG startup, steady-memory, database-connection, and HTTP-error baseline live on Pro/CI. Offline/schema-only output is never the comparator baseline, and any unavailable/non-numeric metric blocks Phase 0 exit.

- [ ] **Step 4a: Commit the review-protocol bootstrap before the first packet**

The first panel is allowed one non-runtime bootstrap commit after the documentation rebase. It contains only the canonical freezer, single-buffer launcher, deterministic validator, immutable GLM route configuration, and their guilt tests. These files are committed source dependencies of `H0`, but they are deliberately outside the initial nine-covered-plus-one-instructions review projection. This is not Phase 0 runtime implementation and cannot contain worker-plane behavior, production evidence, or review verdicts.

Run RED/GREEN and the static check before committing:

```bash
apps/backend-rag/.venv/bin/python -m pytest -q \
  scripts/tests/test_worker_plane_review_packet.py \
  scripts/tests/test_launch_worker_plane_review_panel.py \
  scripts/tests/test_check_worker_plane_review.py
apps/backend-rag/.venv/bin/ruff check \
  scripts/freeze_worker_plane_review.py \
  scripts/launch_worker_plane_review_panel.py \
  scripts/check_worker_plane_review.py \
  scripts/tests/test_worker_plane_review_packet.py \
  scripts/tests/test_launch_worker_plane_review_panel.py \
  scripts/tests/test_check_worker_plane_review.py
git add \
  scripts/freeze_worker_plane_review.py \
  scripts/launch_worker_plane_review_panel.py \
  scripts/check_worker_plane_review.py \
  scripts/review_routes/glm-5.2-v1.json \
  scripts/tests/test_worker_plane_review_packet.py \
  scripts/tests/test_launch_worker_plane_review_panel.py \
  scripts/tests/test_check_worker_plane_review.py
git commit -m "test(review): bootstrap immutable worker plane panel" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
```

Expected: the commit contains exactly those seven paths; all clients remain uninvoked by the guilt suite; `git status --porcelain --untracked-files=no` is empty afterward. Record the commit OID and source/blob hashes in the first freeze receipt. Any later change to bootstrap tooling requires its own tested commit before a new `H0` is selected.

- [ ] **Step 5: Freeze one content-addressed plan packet and run all three reviewers**

Use this canonical packet/launcher contract for this plan review and every later phase or release panel; phase plans may add covered code/evidence entries but may not weaken it.

1. Require a clean tracked tree after the rebase, pin `UPSTREAM=$(git rev-parse 'origin/main^{commit}')`, then set `H0=$(git rev-parse 'HEAD^{commit}')` and `BASE=$(git merge-base "$UPSTREAM" "$H0")`. Read all inputs with `git show "$H0:<path>"`, never from the worktree. For this plan review the review-input projection contains exactly nine `role=covered` entries—the amended spec, master plan, Phase 0–5 plans, and rollout plan—and one `role=instructions` entry, `00-review-brief.md`. Raw outputs, normalized reviews, invocation receipts, dispositions, packet files, and attestation manifests are excluded.
2. Canonicalize `input-manifest.json` with `json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')`, no Unicode rewriting or insignificant whitespace. Sort its `entries` lexicographically by the raw UTF-8 byte tuple `(role, path)`; every entry has exactly `{role,path,size,git_blob_oid,sha256}`, where `size` is the byte count and `git_blob_oid` is the OID returned for that path by the recorded Git object database. Reject duplicate `(role,path)` pairs, unknown roles, absolute/non-normalized paths, or two roles for one path. The manifest contains no manifest hash, packet hash, output path, timestamp, current `HEAD`, or mutable status field. `input_manifest_sha256 = SHA256(canonical_manifest_bytes)` is the review-input projection identity. Store `BASE`, `H0`, tree OID, and clean-status proof in the external freeze receipt, not in projection identity.
3. Build `packet.bin` only from the already buffered Git-object bytes, with exact framing `NUZANTARA-REVIEW-PACKET-V1\n`, then `MANIFEST <decimal-byte-length>\n<canonical-manifest-bytes>`, then for each manifest entry in order `ENTRY <role-byte-length> <path-byte-length> <content-byte-length>\n<role-bytes><path-bytes><content-bytes>`, then `END\n`. Do not interpolate delimiters into content. Parse the completed bytes back to EOF and prove every length, path, role, SHA-256, Git blob OID, and manifest entry; trailing or missing bytes fail closed.
4. Compute `packet_sha256` only after packet construction. It is an external transport-integrity value recorded in the freeze/invocation receipts and must never be embedded in the packet or requested from the reviewer. Move immutable objects to `<external-review-store>/sha256/<packet_sha256>/` with exact stored names `packet.bin`, `input-manifest.json`, `freeze-receipt.json`, and `glm-5.2-v1.json`; verify every stored hash after the move, make the directory and files read-only, and retain its inode/device plus the Git-object validation result. The launcher materializes the verified packet into the review output directory as `00-review-packet.bin`; no launcher may reread a mutable worktree path.
5. A single launcher process reads that content-addressed packet once into a byte buffer, recomputes `packet_sha256`, and supplies the identical `input=packet_bytes` over stdin to all three subprocesses from a newly created empty `0700` cwd. Every invocation receives a newly generated, previously nonexistent `.../attempts/<uuid>/` output directory; never reuse a phase root or earlier attempt directory. Never use `-p "$(cat ...)"`, a prompt argument, shell command substitution, or one file reopen per seat: those lose trailing newlines and create argv/TOCTOU exposure. The launcher writes stdout and stderr bytes verbatim, hashes them, and never exposes one seat's output to another before all return. It also produces the three normalized Markdown reviews and invocation receipts atomically; no separate/manual normalization step is permitted.
6. Invoke Fable with absolute binary `/Users/balizero/.local/share/mise/installs/node/22/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe` and exact argv `--print --model claude-fable-5 --effort xhigh --output-format json --no-session-persistence --safe-mode --permission-mode plan --tools "" --disable-slash-commands --strict-mcp-config --mcp-config '{"mcpServers":{}}'`. Invoke GLM with the same absolute Claude binary and exact argv `--print --model glm-5.2 --effort high --output-format json --no-session-persistence --safe-mode --permission-mode plan --tools "" --disable-slash-commands --strict-mcp-config --mcp-config '{"mcpServers":{}}'`. The inline MCP argument is exactly the ASCII bytes `{"mcpServers":{}}`, with no newline; this prevents inherited MCP servers. The launcher UUID is receipt identity, not a provider session argument. Remove `ANTHROPIC_API_KEY` from Fable's environment. Invoke Gemini with absolute binary `/Users/balizero/.local/bin/agy` and exact argv `--mode plan --sandbox --print-timeout 15m --model "Gemini 3.1 Pro (High)"`; do **not** pass `-p`, `-p -`, or any prompt argument. With `agy` 1.1.2+ (live route verified at 1.1.3), piped stdin enters headless mode; its cwd is the same empty sandbox directory and an older client fails closed. GLM additionally uses committed route config `scripts/review_routes/glm-5.2-v1.json`. Its exact canonical UTF-8 bytes, including final newline, are `{"api_timeout_ms":"3000000","base_url":"https://api.z.ai/api/anthropic","model_map":{"haiku":"glm-4.7","opus":"glm-5.2","sonnet":"glm-5.2"},"schema_version":1}\n`. The freezer copies those Git-object bytes into the content-addressed review directory and records their SHA-256; the launcher rejects any other bytes, then maps the fields to `API_TIMEOUT_MS`, `ANTHROPIC_BASE_URL`, and the three `ANTHROPIC_DEFAULT_*_MODEL` variables. Load the GLM token at invocation from absolute executable `/usr/bin/security` with argv `find-generic-password -s glm-coding-plan-token -w`; pass it only as `ANTHROPIC_AUTH_TOKEN`, clear `ANTHROPIC_API_KEY` and `CLAUDE_CODE_OAUTH_TOKEN`, and never persist the value. Do not use `zsh -ic`, `.zshrc`, a shell function, or a shim. The narrower configuration claim is that mutable user/project configuration is never accepted as route proof or as the GLM route source; Fable and Gemini still run through their supported safe client modes, and any client behavior that contradicts the pinned argv, empty-tool/MCP contract, requested route, or receipt proof fails closed.
7. For every seat, generate `launcher_invocation_uuid` before launch and write an immutable receipt containing requested route, absolute executable and SHA-256, client version, exact argv array and hash, route-config hash, UTC start/end, cwd proof, common `input_manifest_sha256`, external `packet_sha256`, exit status, stdout SHA-256, and stderr SHA-256. `provider_session_id` and `reported_model` are nullable and are validated only when the provider emits them. A requested route is never presented as a provider declaration. Reviewers repeat only `input_manifest_sha256`; the external validator checks `packet_sha256` from receipts.
8. Reviewers have no Read/Glob/Grep/Bash/MCP tools and no mutable checkout access. If corroboration is necessary, export selected recorded-`H0` Git objects into a separate read-only archive, hash it in the external receipt, and add the needed bytes to a regenerated covered projection/packet; never grant live-worktree reads.
9. Commit the exact launcher output set and completed disposition from one attempt directory before setting `H1`: validator inputs, three normalized reviews, three raw stdout companions, three `.stderr.bin` companions, three invocation receipts, and `99-disposition.md`. Only then regenerate the projection from `git show "$H1:<covered-path>"` and gate on `projection(H1) == projection(H0)`. The deterministic checker receives `--repo`, `--h0`, `--h1`, the same `--covered-set`/`--instructions`, and only paths whose mutable bytes equal regular Git blobs at `H1`; it revalidates projection equality before review/disposition checks. A changed covered entry, role, path, or byte requires a new manifest/packet and all three reruns. An output/disposition-only change with equal projection requires packet/raw/stderr/receipt/disposition integrity revalidation, not a recursive rerun.

The checked review-protocol bootstrap must encode this framing, round-trip parser, Git-object loader, projection comparator, launcher, validator, and guilt tests before the first packet is frozen. The review brief supplies the exact six-heading/verdict contract; the launcher must not add a second prompt. Phase 0 Task 8 re-runs and may extend these tests, but no temporary or uncommitted launcher/config exception is permitted.

Run the initial implementation-plan panel end to end from the repository root. The review-store default below is an absolute path outside the checkout; an override must also be absolute and the freezer independently rejects a resolved path inside the repository. The launcher itself creates and normalizes the canonical files in the fresh attempt directory. Complete the disposition before the exact artifact commit; the checker is intentionally last because it validates committed `H1` blobs, not uncommitted worktree files.

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"
PYTHON="$REPO_ROOT/apps/backend-rag/.venv/bin/python"
REVIEW_STORE="${WORKER_PLANE_REVIEW_STORE:-${HOME}/.local/share/nuzantara/worker-plane-review-store}"
case "$REVIEW_STORE" in
  /*) ;;
  *) echo "WORKER_PLANE_REVIEW_STORE must be absolute" >&2; exit 2 ;;
esac
case "$REVIEW_STORE" in
  "$REPO_ROOT"|"$REPO_ROOT"/*) echo "review store must be outside the repository" >&2; exit 2 ;;
esac

UPSTREAM="$(git rev-parse 'origin/main^{commit}')"
H0="$(git rev-parse 'HEAD^{commit}')"
BASE="$(git merge-base "$UPSTREAM" "$H0")"
test -z "$(git status --porcelain --untracked-files=no)"
FREEZE_JSON="$("$PYTHON" scripts/freeze_worker_plane_review.py freeze \
  --repo "$REPO_ROOT" --upstream "$UPSTREAM" --base "$BASE" --source "$H0" \
  --covered-set implementation-plan \
  --instructions docs/superpowers/reviews/2026-07-17-modular-worker-plane-implementation-plan/00-review-brief.md \
  --output-store "$REVIEW_STORE")"
PACKET_SHA256="$(printf '%s\n' "$FREEZE_JSON" | "$PYTHON" -c 'import json, sys; print(json.load(sys.stdin)["packet_sha256"])')"

ATTEMPT_ID="$(uuidgen | tr '[:upper:]' '[:lower:]')"
REVIEW_ATTEMPT_DIR="docs/superpowers/reviews/2026-07-17-modular-worker-plane-implementation-plan/attempts/$ATTEMPT_ID"
"$PYTHON" scripts/launch_worker_plane_review_panel.py \
  --frozen-review "$REVIEW_STORE/sha256/$PACKET_SHA256" \
  --output-dir "$REVIEW_ATTEMPT_DIR"

"${EDITOR:-vi}" "$REVIEW_ATTEMPT_DIR/99-disposition.md"
ATTEMPT_FILES=(
  "$REVIEW_ATTEMPT_DIR/00-review-packet.bin"
  "$REVIEW_ATTEMPT_DIR/input-manifest.json"
  "$REVIEW_ATTEMPT_DIR/freeze-receipt.json"
  "$REVIEW_ATTEMPT_DIR/01-fable-5-architecture.md"
  "$REVIEW_ATTEMPT_DIR/01-fable-5-architecture.raw.json"
  "$REVIEW_ATTEMPT_DIR/01-fable-5-architecture.stderr.bin"
  "$REVIEW_ATTEMPT_DIR/01-fable-5-architecture.invocation.json"
  "$REVIEW_ATTEMPT_DIR/02-gemini-3.1-pro-high.md"
  "$REVIEW_ATTEMPT_DIR/02-gemini-3.1-pro-high.raw.txt"
  "$REVIEW_ATTEMPT_DIR/02-gemini-3.1-pro-high.stderr.bin"
  "$REVIEW_ATTEMPT_DIR/02-gemini-3.1-pro-high.invocation.json"
  "$REVIEW_ATTEMPT_DIR/03-glm-5.2-adversarial.md"
  "$REVIEW_ATTEMPT_DIR/03-glm-5.2-adversarial.raw.json"
  "$REVIEW_ATTEMPT_DIR/03-glm-5.2-adversarial.stderr.bin"
  "$REVIEW_ATTEMPT_DIR/03-glm-5.2-adversarial.invocation.json"
  "$REVIEW_ATTEMPT_DIR/99-disposition.md"
)
for artifact in "${ATTEMPT_FILES[@]}"; do test -f "$artifact"; done
git add -- "${ATTEMPT_FILES[@]}"
git commit -m "docs(review): record initial worker plane panel" -m "Co-Authored-By: Codex Opus 4.8 (1M context) <noreply@anthropic.com>"
H1="$(git rev-parse 'HEAD^{commit}')"

"$PYTHON" scripts/freeze_worker_plane_review.py compare-projection \
  --repo "$REPO_ROOT" --left "$H0" --right "$H1" \
  --covered-set implementation-plan \
  --instructions docs/superpowers/reviews/2026-07-17-modular-worker-plane-implementation-plan/00-review-brief.md
"$PYTHON" scripts/check_worker_plane_review.py \
  --repo "$REPO_ROOT" --h0 "$H0" --h1 "$H1" \
  --covered-set implementation-plan \
  --instructions docs/superpowers/reviews/2026-07-17-modular-worker-plane-implementation-plan/00-review-brief.md \
  --packet "$REVIEW_ATTEMPT_DIR/00-review-packet.bin" \
  --input-manifest "$REVIEW_ATTEMPT_DIR/input-manifest.json" \
  --freeze-receipt "$REVIEW_ATTEMPT_DIR/freeze-receipt.json" \
  --disposition "$REVIEW_ATTEMPT_DIR/99-disposition.md" \
  --files \
  "$REVIEW_ATTEMPT_DIR/01-fable-5-architecture.md" \
  "$REVIEW_ATTEMPT_DIR/02-gemini-3.1-pro-high.md" \
  "$REVIEW_ATTEMPT_DIR/03-glm-5.2-adversarial.md"
```

- [ ] **Step 6: Verify the reviewed plan set and real review evidence at `H1`**

Run after the end-to-end block exits 0:

```bash
git show --stat --oneline "$H1"
test -z "$(git status --porcelain --untracked-files=no)"
```

Expected: `H1` contains exactly the fresh attempt's immutable validator inputs, normalized/raw/stderr/invocation outputs, and disposition; the checker has re-read those Git blobs and proved the rebuilt covered/instructions projection equals `H0`, while source-tree and transport hashes remain external receipt metadata.

---

### Task 2: Execute Phase 0 — baseline and recovery gaps

**Plan:** `docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-0.md`

- [ ] **Step 1: Execute every unchecked Phase 0 task with a fresh implementation agent and strict TDD**
- [ ] **Step 2: Resolve every Blocking and Important task-review finding**
- [ ] **Step 3: Run the complete Phase 0 regression, repository G6 reclaim proof, code/CI G11 liveness contract, and G16/G17 proofs; authoritative-runtime G6 and live G11 remain explicitly pending until protected post-merge rollout**
- [ ] **Step 4: Run Fable 5, Gemini 3.1 Pro High, and GLM 5.2 independently against the Phase 0 diff and disposable/CI evidence as a provisional checkpoint**
- [ ] **Step 5: Fix all blocking findings; if any covered/instructions role, path, or byte changes, regenerate the projection/packet and rerun all three seats until the synthesis records `GO` or `GO-WITH-CHANGES` with zero unresolved Blocking/Important finding**
- [ ] **Step 6: Commit the Phase 0 synthesis and mark the phase complete in the SDD ledger**

Expected: every durable loop and mutable table has a checked owner, Redis abandoned work is reclaimed, liveness is behavioral, and aged durable events are quarantined rather than silently acknowledged.

---

### Task 3: Execute Phase 1 — authoritative catalogs and legacy fencing

**Plan:** `docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-1.md`

- [ ] **Step 1: Execute every unchecked Phase 1 task with a fresh implementation agent and strict TDD**
- [ ] **Step 2: Resolve every Blocking and Important task-review finding**
- [ ] **Step 3: Run route mutation, ownership conflict, build-floor, stale-owner, catalog, compatibility proofs, and the Phase 0 G9 API/RAG comparator**
- [ ] **Step 4: Run the independent Fable/Gemini/GLM phase panel**
- [ ] **Step 5: Fix all blocking findings; if any covered/instructions role, path, or byte changes, regenerate the projection/packet and rerun all three seats until the synthesis records `GO` or `GO-WITH-CHANGES` with zero unresolved Blocking/Important finding**
- [ ] **Step 6: Commit review evidence and mark Phase 1 complete**

Expected: runtime mounting and proxying derive from one route catalog; every simulated/disposable legacy claimant dynamically enforces the database grant and fencing generation; guard-arm eligibility is proven without arming any live environment.

---

### Task 4: Execute Phase 2 — inert private worker companion

**Plan:** `docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-2.md`

- [ ] **Step 1: Execute every unchecked Phase 2 task with a fresh implementation agent and strict TDD**
- [ ] **Step 2: Resolve every Blocking and Important task-review finding**
- [ ] **Step 3: Prove lazy imports, private readiness, scoped grants, off/shadow purity, separate worker G13/G14 budgets, and the Phase 0 G9 API/RAG comparator**
- [ ] **Step 4: Run the independent Fable/Gemini/GLM phase panel**
- [ ] **Step 5: Fix all blocking findings; if any covered/instructions role, path, or byte changes, regenerate the projection/packet and rerun all three seats until the synthesis records `GO` or `GO-WITH-CHANGES` with zero unresolved Blocking/Important finding**
- [ ] **Step 6: Commit review evidence and mark Phase 2 complete**

Expected: the companion candidate uses the same test digest as the primary candidate, has no public service, meets readiness and resource budgets in CI/disposable infrastructure, and cannot claim or emit side effects in `off` or `shadow`; no live companion is created pre-merge.

---

### Task 5: Execute Phase 3 — workflow and legal cutover simulations

**Plan:** `docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-3.md`

- [ ] **Step 1: Rehearse the workflow cutover only in CI/simulation against disposable PostgreSQL after compatibility and side-effect gates pass**
- [ ] **Step 2: Inject restart, timeout, duplicate, stale-owner, DB reconnect, and ambiguous-effect faults**
- [ ] **Step 3: Execute a simulated reverse workflow rehearsal, prove an old-owner completion, then reactivate the simulated worker with a new generation**
- [ ] **Step 4: Observe a complete deterministic/disposable workflow cycle and return to the documented standby state before starting legal ingestion**
- [ ] **Step 5: Repeat the complete gated simulation, fault, reverse-cutover, observation, and standby sequence for legal ingestion while rejecting every live staging or production target**
- [ ] **Step 6: Run the Phase 0 G9 API/RAG comparator, resolve task reviews, run the independent Fable/Gemini/GLM panel, fix blockers, and commit a zero-unresolved-finding synthesis**

Expected: no simulated/disposable job records two ownership generations; crashed leases recover; every ambiguous external result is confirmed, reconciled, or durably blocks as `outcome_unknown`; G3/G4/G12/G15 pass; every live staging/production deployment, migration, secret, grant, guard, activation, and observation remains deferred to Task 8 after protected merge.

---

### Task 6: Execute Phase 4 compatibility checkpoint — notification and WhatsApp cutover simulations (Tasks 1–4 only)

**Plan:** `docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-4.md`

- [ ] **Step 1: Implement and rehearse notification scheduling in CI/simulation with disposable PostgreSQL only after deterministic-run, timezone, dedupe, effect, fault, and reverse-cutover gates pass**
- [ ] **Step 2: Observe the declared deterministic/disposable notification cycle and return to the documented standby state**
- [ ] **Step 3: Implement and rehearse WhatsApp in CI/simulation only after thread ordering, takeover, provider capability, outcome ambiguity, fault, and reverse-cutover gates pass**
- [ ] **Step 4: Retain the compatible API/RAG lifecycle wiring as dormant rollback capability in this release**
- [ ] **Step 5: Run the Phase 0 G9 API/RAG comparator, resolve Tasks 1–4 reviews, run the independent Fable/Gemini/GLM compatibility panel, fix blockers, and commit a zero-unresolved-finding compatibility-checkpoint synthesis**
- [ ] **Step 6: Use this compatibility checkpoint to admit Phase 5, while keeping Phase 4 open; defer Task 5 lifecycle deletion, its deletion panel, and final Phase 4 closure to the separate post-observation PR in Task 8**

Expected: CI/disposable evidence proves a logical schedule is emitted once across owner changes; WhatsApp preserves per-thread ordering and never automatically retries a non-reconcilable ambiguous send; the compatibility candidate preserves fenced, dormant rollback wiring; no live environment is mutated. This is Phase 4's compatibility checkpoint, not final Phase 4 completion.

---

### Task 7: Execute Phase 5 — rolling receipt bridge, dormant fan-out activation, and boundary ratchet

**Plan:** `docs/superpowers/plans/2026-07-17-modular-worker-plane-phase-5.md`

- [ ] **Step 1: Execute every unchecked Phase 5 task with a fresh implementation agent and strict TDD**
- [ ] **Step 2: Resolve every Blocking and Important task-review finding**
- [ ] **Step 3: Prove the Release-A global-ack/receipt dual-read/dual-write bridge, deterministic pre-existing-row backfill, all crash points, and the four-cell old/new binary matrix while durable fan-out remains disabled**
- [ ] **Step 4: Prove the dormant Release-B build-floor/catalog-hash/activation-boundary CAS and independent subscription acknowledgement/replay in disposable PostgreSQL while preserving two physical buses; no live receipt activation occurs pre-merge**
- [ ] **Step 5: Run real Mouth/MCP contract compatibility, prohibited-PII pre-publish rejection and sanitized-capture tests, table ownership, direct-SQL/cross-context ratchets, and the Phase 0 G9 comparator**
- [ ] **Step 6: Run the independent Fable/Gemini/GLM phase panel**
- [ ] **Step 7: Fix all blocking findings; rerun all three seats after any covered/instructions projection change, but perform integrity-only revalidation for attestation changes with equal projection; commit a zero-unresolved-finding synthesis and run a final whole-branch SDD review**

Expected: every new cross-process contract is versioned, observable, and replayable; Release A remains bridge-only under every old/new overlap and converges after every tested crash; Release B cannot activate until backfill, catalog hash, activation boundaries, and the complete compatible census are proven; one subscriber cannot acknowledge another subscriber's receipt; Mouth and MCP remain compatible; prohibited raw PII fails before job/event publication and cannot appear in captured logs/DLQ/quarantine; API/RAG G9 metrics and module-boundary metrics cannot regress.

---

### Task 8: Freeze final reviews, protected-merge, stage, independently gate, then prove production

**Plan:** `docs/superpowers/plans/2026-07-17-modular-worker-plane-production-rollout.md`

- [ ] **Step 1: Rebase onto current `origin/main`, rerun the full required suite, resolve only branch-owned conflicts, then push the feature branch and open the protected-merge PR without triggering any live staging/production mutation**
- [ ] **Step 2: Obtain green pre-merge CI and required independent review, prepare non-generated rollout evidence, and address every actionable finding atomically**
- [ ] **Step 3: Immediately before final review freeze, fetch/rebase onto current `origin/main` again; freeze the implementation-input projection, generate final immutable Phase 0–5 and whole-branch packets, rerun every Fable/Gemini/GLM panel, and require zero unresolved Blocking/Important finding. Any later covered-input change invalidates/regenerates every affected packet/panel; content-addressed generated attestations are validated outputs. Push the final attestations, require final CI green, and repeat this step after any implementation-input fix**
- [ ] **Step 4: Merge through the protected branch workflow, record the merge SHA, rebuild the canonical role/path projection from that commit's Git objects, and prove it equals the final reviewed projection; output-only commits may advance `HEAD` and tree OID when this equality holds**
- [ ] **Step 5: Let the existing main-push workflow apply additive production migrations and auto-deploy the exact protected-merged API/RAG compatibility release inert (legacy active, guards unarmed, no production companion or new provider grants/secrets). From the exact merged SHA, perform the protected Pro authoritative `~/scripts/eventbus` allowlisted sync, restart, rollback-manifest, and smoke sequence required to make full G6 green. Then deploy that same recorded digest to live staging and perform every staging migration, secret/grant mutation, guard arm/disarm, ordered forward/reverse drill, live worker-wedge G11/G13 proof, and observation in rollout Task 2; no pre-merge candidate or competing primary deploy path may be used**
- [ ] **Step 6: Pass the independent post-staging release gate with exact Fable/Gemini/GLM routes, immutable raw outputs/model proof, raw SHA validation, and zero unresolved Blocking/Important finding before any production secret/grant mutation, guard arm/disarm, or ownership move; the only earlier production changes are the protected workflow's additive inert compatibility migrations/deploy**
- [ ] **Step 7: After the Release-A post-staging gate, ship the focused protected Release-B receipt-activation PR; keep its production rolling deploy in bridge mode, deploy the exact Release-B digest to staging, prove build floor/backfill/catalog hash/activation boundaries plus bridge -> receipt-authoritative -> bridge -> receipt-authoritative behavior, and pass a fresh immutable three-model activation panel. Then activate production receipts through the audited CAS and observation window. Only afterward use `.github/workflows/worker-plane-production.yml` to deploy that exact Release-B digest to the private `nuzantara-worker` companion with every worker workload off, guards unarmed, base control-plane database capability only, and no provider capability; prove private readiness/heartbeat, then execute each workload through a separate protected capability admission and `.github/workflows/worker-plane-live-control.yml` command in fixed order `workflow_queue -> legal_full_ingestion -> notification_scheduler -> wa_outbox`. Every arm/drain/activate/reverse command consumes the immutable effective-capability run ID/hash and immediately re-audits grants plus allowed secret-symbol hashes before CAS; always source drain -> full barrier -> target active at a newer generation, with full-cycle observation and reverse/re-cutover proof before the next workload receives capability**
- [ ] **Step 8: Run heavy production HTTP, queue, reclaim, fencing, event fan-out, resource, schedule, sovereignty, adapter, and rollback tests through CI/Pro; verify public health, logs, metrics, queue depths, ambiguous effects, DB connections, and absence of duplicate active owners**
- [ ] **Step 9: Store sanitized compatibility-release evidence through protected evidence PRs; every such PR must be CI-green, protected-merged, and have its merged SHA recorded before evidence is considered complete**
- [ ] **Step 10: After all four workload-specific rollback windows close, open, review, merge, and deploy the separate legacy-lifecycle deletion PR. Prove the four-cell old/new primary-worker compatibility matrix, let protected main deploy the primary deletion release, then update the existing worker through `.github/workflows/worker-plane-production.yml` to that exact deletion digest without changing ownership/capability state; on partial failure restore the prior worker digest and roll back primary without reversing ownership. Require final primary/worker digest equality, run the deletion panel, and prove API/RAG own none of the four migrated durable loops, thereby finally closing Phase 4**
- [ ] **Step 11: Bind the final Fable/Gemini/GLM release panel to one canonical `input_manifest_sha256` projection and its externally receipted content-addressed packet, import packet/raw proof/verdicts through a CI-green protected evidence PR, record that PR's merged SHA, and mark the goal complete only after the Release-A, Release-B, and deletion release SHAs, every evidence-PR SHA, every deployed digest, receipt activation boundary/mode, all active generations, heavy test results, deletion proof, all four workload windows, and the deletion observation window are independently re-read from live sources**

Expected: protected merge and coordinated deployment succeed; all G1-G17 evidence is green in the merged production build; no rollback, ambiguity, sovereignty, resource, or liveness alarm remains open.
