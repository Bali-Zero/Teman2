---
name: fly-split-brain-verify
description: Use AFTER any Fly.io deploy of nuzantara-rag, or when kita/my/zantara.balizero.com throws 503 "RAG worker unavailable" while /health still returns 200. Replaces the naive "/health==200" post-deploy check with split-brain disambiguation across the api + rag process groups — proves the rag worker actually answers (not just the api front), and tells autostop-idle apart from stuck-after-crashloop. Read-only verification PROCEDURE: it runs fly/curl read-only and may force-start a stopped machine, but NEVER deploys or destroys.
user-invocable: true
---

# Fly Split-Brain Verify

Post-deploy verification for `nuzantara-rag`. The naive check (`curl /health → 200`) is a **trap**: `nuzantara-rag` runs **two process groups** and `/health/ready` is wired to the **api** group only. A dead **rag** worker leaves `/health=200` while every RAG/CRM call 503s. This skill disambiguates.

> Born from the 2026-06-02 "503 RAG worker unavailable" scar family (`.claude/rules/cicatrix-scars.md`). The api machine kept `/health=200` and unauth endpoints `401` while the rag machine was crash-loop-stuck STOPPED — the fix was live in the image for 5h+ but the machine never rebooted to run it.

## What this skill is and is NOT

- **IS**: a read-only verification procedure. It runs `fly status` / `fly logs` / `fly machine status` / `curl` and, at most, `fly machine start <id>` to wake a machine the previous deploy left stopped, then reads its boot log.
- **IS NOT**: a deployer. It NEVER runs `fly deploy`, `fly machine destroy`, `fly machine stop`, `fly secrets`, or any mutation beyond force-starting an already-deployed machine. To deploy, use the `nuzantara-deploy` skill. Off-limits without sign-off: `fly.toml`, `.env*`.

## Topology (why the naive check lies)

`nuzantara-rag` has two `[processes]` (see `apps/backend-rag/fly.toml`):

| Group | Command (abridged)                           | Public?                                                                                  | Health check                        |
| ----- | -------------------------------------------- | ---------------------------------------------------------------------------------------- | ----------------------------------- |
| `api` | `uvicorn backend.app.main_api:app`           | yes — Fly Proxy `[http_service]`, `min_machines_running=1`                               | `GET /health/ready` on **api only** |
| `rag` | `uvicorn backend.app.main_rag:app --host ::` | no — internal 6PN `rag.process.nuzantara-rag.internal:8080`, **no `[[services]]` block** | none via Fly Proxy                  |

A third group, `drive` (`python -m backend.workers.drive_poll_worker`, `apps/backend-rag/fly.toml:33`, VM block at :106), polls Drive outside the HTTP path and has no public service. **`drive` has a standby machine by design**: a stopped/standby `drive` machine in `fly machine list` is expected, NOT a split-brain finding. Only `api` and `rag` states gate the verdict.

So `https://nuzantara-rag.fly.dev/health` only ever talks to the **api** machine. If `rag` is dead, `/health` stays green and the api front returns `401` on protected routes — but any route that calls the rag worker over 6PN returns **503 "RAG worker unavailable"**. That is the split brain.

## Procedure

### 1. Enumerate process groups — assert EACH started/healthy

```bash
fly status --app nuzantara-rag
```

Read the **machines** table, not just the app summary. You must see, per group:

- **api** machine(s): `state=started`, health checks `passing`.
- **rag** machine(s): `state=started`. (rag has no Fly health check, so "started" is the bar — step 3 proves it actually serves.)

A `rag` machine in `state=stopped` is **ambiguous** — it could be autostop-idle OR stuck-after-crashloop. Do NOT treat a green `fly releases` row or green CI as proof the new image is live: a rolling deploy to an autostop machine _stages_ the image and leaves the machine stopped; it does **not** force-boot it. Go to step 4 to disambiguate.

### 2. Confirm /health (necessary, NOT sufficient)

```bash
curl -sS -o /dev/null -w "%{http_code}\n" https://nuzantara-rag.fly.dev/health
```

Expect `200` or `307`. This only proves the **api** front is up. **Never stop here** — it is exactly the masking signal from the scar.

### 3. Probe the rag worker for real (NOT an anonymous 401)

An anonymous `401` from the api machine proves only that the api front rejected auth BEFORE it needed the worker. It says nothing about rag, so it is NOT a pass. (The earlier version of this step treated it as one; that was wrong.) Probe a route that actually answers from the rag side, then cross-check the machine id:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://nuzantara-rag.fly.dev/api/oracle/health
fly logs -a nuzantara-rag --no-tail | tail -50      # read-only
```

- **`200`** -> the rag worker answered (verified live 2026-10-12: 200). PASS for this step.
- **`503`** -> rag is dead / unreachable. Go to step 4.
- Anything else (000, 5xx other than 503, 404) -> do not call PASS; read the log and treat as unknown.

Machine-id cross-check: in the `fly logs` tail, the lines that carry the oracle request (or the rag uvicorn boot/"Application startup complete" lines) must show the machine id of the **rag** machine from `fly status` (step 1), not the api machine id. If the 200 came back but no log line names the rag machine id, the request was served by the wrong group; do not PASS, re-run once and re-read. Never send a real token in a verification curl.

### 4. STOPPED rag machine — disambiguate autostop-idle vs stuck-after-crashloop

Get the rag machine id and its per-machine state:

```bash
fly machine list --app nuzantara-rag           # note the rag machine <id>
fly machine status <rag-machine-id> --app nuzantara-rag
fly logs --app nuzantara-rag --no-tail | tail -200
```

Look in the boot log for **crash-loop signatures**:

- repeated `Starting` / restart cycles hitting the **max-restart cap** (Fly gives up and leaves the machine STOPPED after ~10 rapid restarts),
- a startup traceback: `ModuleNotFoundError` / import error during `include_heavy_routers` (the rag worker's heavy-router load step),
- the **original crash timestamp** — a stuck machine's log carries the _old_ crash time (e.g. the 19:08 crash surfaced hours later); do **not** misread an old trace as a fresh crash.

Classify:

- **autostop-idle**: no crash signatures, machine just scaled to zero on idle. Force-start (step 5) and it boots clean.
- **stuck-after-crashloop**: crash trace + max-restart-cap. The image may already contain the fix but the machine never re-ran it. Force-start (step 5) and **read the boot log** to confirm the new image boots clean.

### 5. Force-start and confirm clean boot past include_heavy_routers

```bash
fly machine start <rag-machine-id> --app nuzantara-rag
fly logs --app nuzantara-rag --no-tail | tail -120
```

A clean rag boot must get **past `include_heavy_routers`** with no traceback and reach the uvicorn "Application startup complete" line. Then re-run step 3 — it must now return `200`, not `503`.

If it crash-loops again on start, the deployed image is genuinely broken (not just a stopped machine) → escalate to a real fix + redeploy via the `nuzantara-deploy` skill. This skill does not deploy.

### 6. Verdict

| Signal                                                                            | Verdict                                                                  |
| --------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| api `started`+passing, rag `started`, `/health`=200/307, `/api/oracle/health`=200 | **PASS** — both halves of the brain alive.                               |
| `/health`=200 but `/api/oracle/health`=503                                        | **SPLIT-BRAIN** — api up, rag down. Run step 4-5.                        |
| rag boots clean past `include_heavy_routers` after force-start, probe→200         | **RECOVERED** — was a stopped machine, image was fine.                   |
| rag crash-loops again on force-start                                              | **BROKEN IMAGE** — escalate to `nuzantara-deploy` (real fix + redeploy). |

## How the backend deploys today (and the break-glass trap)

Routine path (no manual `fly deploy`): merge to `main` -> `mini.zero_sync` mirrors it to `FastLabsNet/zero` (`scripts/zero_sync/README.md:1`, constant `DEFAULT_ZERO` at `scripts/zero_sync/zero_sync.py:30`) -> zero's `fly-deploy.yml` runs on runner `mini-zero-1` -> Fly runs `release_command` = `python -m backend.db.migrate apply-all && python -m backend.db.schema_audit` on the NEW image (`apps/backend-rag/fly.toml:15`) -> rolling replace. Source: `apps/backend-rag/CLAUDE.md:457-465` ("Since 2026-10-11 the workflow runs on `FastLabsNet/zero`"; expect up to ~30 min merge-to-live). Watch: `gh run list -R FastLabsNet/zero --workflow fly-deploy.yml`; prove by `scripts/post-deploy-verify.sh <PR>` (`build_sha` ancestry).

**Python migrations need a manual apply when the automatic step did not run.** `release_command` applies the SQL ledger only (`migrate apply-all`). Python-idiom migrations (`apps/backend-rag/backend/migrations/migration_NNN_*.py`) run in a separate post-deploy job (`run-python-migrations`, `.github/workflows/fly-deploy.yml:421`); if that job is red, skipped, or the deploy was a break-glass one, apply them by hand against the new image and confirm in the ledger. Do not assume they landed because the release is green.

Break-glass only (workflow broken), and it needs a `FLY_API_TOKEN` scoped to `nuzantara-rag`. `fly deploy` from inside `apps/backend-rag/` FAILS (repo-root-relative `COPY` of `packages/cell-core`, `apps/crm-cell`; `apps/backend-rag/CLAUDE.md:474-486`):

```bash
# CORRECT: repo-root build context
cd ~/nuzantara && fly deploy --config apps/backend-rag/fly.toml --dockerfile apps/backend-rag/Dockerfile --strategy rolling -a nuzantara-rag
# WRONG: cd apps/backend-rag && fly deploy
```

The old `~/Desktop/nuzantara-deploy` worktree no longer exists (repos moved out of ~/Desktop on 2026-07-16). This skill does not deploy; it only carries the trap.

## Notes / gotchas (from the scar family)

- **`fly status` rag=stopped is NOT proof of a fix.** A successful `fly releases` row + green CI does not mean the fix runs on an autostop machine that was already dead. Disambiguate only by force-start + boot-log read.
- **`/health=200` is the masking signal**, by design — the check lives on the api group. Always check per-process-group state with `fly status`, never `/health` alone.
- **Old timestamps in `fly logs`**: a stuck machine's crash trace carries the original crash time, surfaced hours later. Cross-check against "now" before calling it a fresh crash.
- **Structural mitigation** (out of scope for this read-only skill, noted for the operator): `cron-fly-restart-detector.yml` is meant to force-start crashed-stopped machines (PR #1043) — verify it actually starts them, not just alerts. Considering `min_machines_running=1` for the rag group would end 503-on-cold-rag but is a `fly.toml` change (off-limits without sign-off).
- **Anti-hallucination**: never report PASS/FAIL from a remembered run. Re-run steps 1-3 in the current turn and read the actual exit codes / HTTP codes before stating a verdict.
