# CVE Triage Policy

This document defines how Nuzantara handles CVE findings surfaced by the
security scanners (Snyk, Safety, Bandit, CodeQL). Before this policy, all
CVE-producing jobs ran with `continue-on-error: true` because there was no
written rule for when an unpatched vulnerability should block a merge. The
wording in `.github/workflows/security.yml` referenced this gap explicitly:

> Advisory-only: CVE policy (which vulns to accept vs fix) requires maintainer
> decisions. Re-enable as blocking gate once apps/backend-rag/requirements.txt
> is triaged.

This file closes that gap.

## Severity → action

| Severity | Action                                                                                                                               |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| CRITICAL | Block PR. No exception without Zero's written approval. Patch or rollback the offending dependency before merging.                   |
| HIGH     | Block deploy. The PR may merge to `main` if the fix is tracked in a follow-up issue **and** the vulnerability is listed in `.security/exceptions.yaml` with a valid `expires_at`. |
| MEDIUM   | Tracked issue required within 7 days. Does not block PRs or deploys.                                                                 |
| LOW      | Batched monthly review. No tracking issue required.                                                                                  |

The `--severity-threshold=high` flag on Snyk/Safety means the scanners only
emit HIGH and CRITICAL — those are the severities enforced by CI. Medium and
low findings are captured by the weekly scheduled run (`cron: "0 0 * * 0"`)
and reviewed out of band.

## Exceptions (`.security/exceptions.yaml`)

Any HIGH/CRITICAL finding that cannot be fixed immediately **must** be added
to `.security/exceptions.yaml` before the blocking gate will let a PR merge.
The file documents who accepted the risk, why, and when the acceptance
expires. A pre-deploy check (`scripts/check_cve_exceptions.py`) verifies
every entry has not expired — expired exceptions fail the deploy.

### Schema

```yaml
exceptions:
  - cve_id: CVE-2025-12345       # required — canonical CVE identifier
    package: example-package      # required — npm/pypi/docker package name
    version: "1.2.3"              # required — pinned version still in use
    reason: "Upstream fix blocked on X; patched via workaround Y" # required
    approved_by: zero             # required — Zero or delegated maintainer
    approved_at: 2026-04-18       # required — ISO date
    expires_at: 2026-07-18        # required — ISO date, max 90 days ahead
    tracking_issue: "#123"        # optional — GitHub issue URL or number
```

### Rules

1. **Maximum 90 days** between `approved_at` and `expires_at`. After that the
   exception must be renewed with fresh justification (forces periodic review).
2. **Zero approves CRITICAL** — no one else. HIGH may be approved by a
   designated maintainer.
3. **One CVE per entry.** If the same package has two CVEs, create two entries
   — they may have different expiration plans.
4. **`reason` must be technical**, not "wait for upstream". Include the
   specific blocker: "aiohttp 3.9.x breaks our websocket handler, fix in 3.10",
   not "will update later".
5. **`tracking_issue` is encouraged** whenever work is already planned. Without
   a tracking issue, the acceptance is assumed to be a permanent trade-off.

## CI enforcement

`.github/workflows/security.yml`:

- `snyk-python`, `snyk-node`, `safety` are **blocking** (`continue-on-error: false`).
- Each job reads `.security/exceptions.yaml` and ignores findings whose
  `cve_id` is listed with a non-expired `expires_at`.
- `snyk-docker` remains advisory-only for now — Docker image vulns ship with
  the base image, separate rotation schedule.

`.github/workflows/fly-deploy.yml`:

- Pre-deploy gate runs `python scripts/check_cve_exceptions.py`, which fails
  the deploy if any exception is expired. This is the last line of defence
  before traffic hits production.

## Runbook — adding an exception

1. Snyk or Safety reports a HIGH finding you cannot fix in this PR.
2. Copy the CVE row from the scan report (`cve_id`, package, version).
3. Open `.security/exceptions.yaml`, append a new entry following the schema
   above. Set `expires_at` to the realistic fix date, capped at 90 days.
4. Get approval in PR review from the designated maintainer (Zero for
   CRITICAL). The reviewer's GitHub handle goes in `approved_by`.
5. Re-run CI — the finding should now pass the blocking gate.
6. File a tracking issue if one does not already exist and reference it in
   `tracking_issue`.

## Runbook — exception expired

`check_cve_exceptions.py` fails the deploy with an explicit error:

```
❌ Exception for CVE-2025-12345 expired on 2026-04-10 (5 days ago).
   Either upgrade the package, renew the exception, or roll back the PR that
   introduced it.
```

Renewal is a PR that updates `approved_at`, `expires_at`, and usually the
`reason` with fresh context. Renewals over a year old warrant revisiting
whether the accepted risk is still acceptable.

## Out of scope

- **SonarQube quality gate** — separate policy. SonarQube governs code-quality
  debt, not CVEs. Tracked in `docs/security/SONARQUBE_POLICY.md` (TBD).
- **`detect-secrets` baseline** — already blocking via
  `scripts/detect_secrets_check_unaudited.py`. Governed by `.secrets.baseline`
  itself, not this file.

## History

- 2026-04-18 — first version. Unblocks Snyk Python/Node and Safety from
  advisory-only mode.
