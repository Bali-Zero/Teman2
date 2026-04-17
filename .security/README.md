# `.security/` — CVE exception log

This directory holds the running list of CVE findings that Zero has
*temporarily* accepted. Every file here is read by CI.

## Files

- `exceptions.yaml` — the exception list. Schema and approval rules are in
  `docs/security/CVE_TRIAGE_POLICY.md`. The blocking Snyk and Safety jobs in
  `.github/workflows/security.yml` skip CVEs listed here, but only until
  `expires_at`. The pre-deploy gate in `.github/workflows/fly-deploy.yml`
  rejects the release if any entry has expired.

## Adding an exception

Open a PR that appends a new entry to `exceptions.yaml` following the schema
in the triage policy. Reviewers check: `reason` is technical and specific,
`expires_at` ≤ 90 days out, and CRITICAL entries carry Zero's approval.

## Why not silence the scanner globally?

Because a `continue-on-error: true` flag on the workflow hides every future
finding too. An `.security/exceptions.yaml` entry only silences the exact CVE
id, only for the documented reason, only until the documented date — and
forces a maintainer sign-off on each one. That is the entire point of the
triage policy.
