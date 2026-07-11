---
date: 2026-06-20
domain: compliance
client_case: none (infra durability — intake-review reader, Law-2 PII boundary)
sources:
  - live diagnosis on Pro 2026-06-19/20 (launchctl runs=40, ~/logs/intake-review-reader.log)
  - scar #1546 (venv-shell-no-deps reader morto, 2026-06-17)
  - cicatrix superscar #1 (HOME-fork drift), #2 (esiste != armato), #7 (KeepAlive restart-storm)
  - PyPI presidio-analyzer release index (verified 2026-06-20)
  - apps/backend-rag/requirements.txt; scripts/intake_review_reader_run.sh; infra/launchagents/com.nuzantara.intake-review-reader.plist
---

# Intake-review reader — 5-bug auto-heal chain (Pro reboot 2026-06-19)

## Context

The Pro-side intake-review reader is a long-lived uvicorn daemon on `127.0.0.1:18795`
(LaunchAgent `com.nuzantara.intake-review-reader`, KeepAlive=true). The Fly `api` process
proxies `/api/intake/review/*` here over a Cloudflare Tunnel so the intake PII (OCR names,
documents) never leaves the Pro (SYMBIOSIS Law 2 / UU PDP). It backs `kita.balizero.com/review`.

On 2026-06-19 the Pro rebooted. The deploy-worktree `.venv` it ran from evaporated, and the
#1546 auto-heal (which only recreated the venv shell + ran `pip install`) hit a CHAIN of
failures that left the reader crash-looping. This note documents the chain and the cure.

## The 5-bug chain

1. **HOME-fork venv evaporation (superscar #1).** The reader ran from a deploy worktree
   (`~/Desktop/nuzantara-deploy/apps/backend-rag/.venv`) that is not the source of truth.
   On reboot / worktree re-add / GC the `.venv` can disappear, so `exec uvicorn` dies with
   `ModuleNotFoundError: No module named 'uvicorn'`.

2. **presidio floor — requirements headroom (originally diagnosed as "presidio>=2.2.362
   impossible").** `requirements.txt` pinned `presidio-analyzer/anonymizer>=2.2.362`.
   CORRECTION (verified on PyPI 2026-06-20): `2.2.362` DOES exist (uploaded 2026-03-15);
   the "PyPI max is 2.2.359" claim in the original diagnosis is wrong. The real problem was
   resolver headroom under the deploy venv's Python 3.14 (wheel/transitive-constraint
   tightness), not a missing version. The fix — lowering the floor to `>=2.2.355` — is still
   correct and safe: a lower minimum is strictly more permissive and the resolver still
   selects the newest compatible build. Narrative imprecise; code change sound.

3. **Heal under KeepAlive — restart storm (superscar #7).** The ~5-minute `pip install`
   ran under `KeepAlive=true`. launchd restarted the wrapper every `ThrottleInterval` (10s)
   and KILLED the in-flight install, relaunching it from scratch — observed `runs=40` with
   the install never completing. Classic green-but-dead: the agent looked busy, made no
   progress.

4. **Deploy venv pip 26.0 — resolution-too-deep.** A freshly created deploy venv shipped
   pip 26.0, whose resolver dies with `resolution-too-deep` on this requirements graph.
   The known-good main venv carries pip 26.1.1+ (verified: main venv = py3.11, pip 26.1.1).

5. **DEEP ROOT — py3.14 google-cloud matrix `ResolutionImpossible`.** On the deploy venv's
   Python 3.14, a from-scratch `pip install -r requirements.txt` is unresolvable:
   `requirements.txt` asks `google-cloud-storage>=2.10.0`, but `google-cloud-aiplatform`
   (Vertex) requires `google-cloud-storage>=3.10.0` on py>=3.13, plus missing wheels. The
   main venv works only because it was built on py3.11 before those constraints tightened.
   Resolving the google-cloud matrix touches the RAG/Vertex stack and is risky — OUT OF
   SCOPE for a wrapper fix, tracked as a follow-up.

All four early failures were also SILENT (log + exit 75, loop forever, no operator page) —
a #2 "esiste != armato" symptom on top of the chain.

## The cure (this PR — durability, not the live process)

- **Reader repointed to the MAIN checkout venv as the durable path.** The live plist was
  hand-edited the night of the incident to set `INTAKE_REVIEW_REPO_ROOT=/Users/nuzantara/
  Desktop/nuzantara` and point `ProgramArguments` at the main-checkout wrapper. The tracked
  plist is reconciled to match so a reinstall never reverts to the broken deploy-worktree
  path. (Live reader verified running from the main venv, HTTP 404 = alive.)
- **Heal lock (cures #3 / superscar #7).** A stale-safe pid-file lock (`.venv-heal.lock`):
  only one heal runs at a time. A KeepAlive restart during a live heal exits 0 cleanly and
  lets the in-flight install finish; a dead pid is reclaimed. No more restart storm.
- **pip self-upgrade before install (cures #4).** `pip install --upgrade 'pip>=26.1.2'`
  runs before the requirements install so the resolver is never the stale 26.0.
- **requirements floor loosened (addresses #2).** `presidio*>=2.2.355` for resolver headroom.
- **Telegram alert with cooldown (cures the silence / #4-symptom).** On heal-install failure
  the operator is paged at most once per 30-min window. Token read from the 0600
  `~/.nuzantara-secrets.env` — never hardcoded (chat fallback = documented owner chat
  `1125336968`).
- **Main-venv fallback (mitigates #5).** If the deploy venv is unresolvable AND the
  main-repo venv can import uvicorn, the wrapper execs uvicorn from the main venv (derived
  from `MAIN_REPO_ROOT`, not a hardcoded path) and sends a one-shot notice. The reader stays
  UP instead of looping.
- **Happy path unchanged.** When the deploy venv's deps are present, the wrapper short-
  circuits and execs uvicorn from it with no lock/pip/heal overhead.

## Follow-up (open)

The py3.14 google-cloud-storage matrix (`aiplatform>=...` requires `>=3.10.0` vs
requirements `>=2.10.0`) is the deep root and is NOT fixed here. A from-scratch install on
py3.14 remains `ResolutionImpossible`. Cure options: bump `google-cloud-storage` floor to
`>=3.10.0` (risks the RAG/Vertex stack — needs a targeted test pass), or pin the deploy venv
to py3.11. Tracked separately; this PR keeps the reader durable in the meantime.
