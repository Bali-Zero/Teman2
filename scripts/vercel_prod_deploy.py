#!/usr/bin/env python3
"""Deploy the `mouth` project to production without the Vercel GitHub App.

WHY THIS EXISTS
---------------
The Vercel GitHub App lost its installation on Bali-Zero/Teman2 on 2026-07-26. Its last
GitHub Deployment is timestamped 2026-07-26T20:07:27Z and there has been none since, so a
push to main creates no Vercel deployment at all. Re-installing it is a GUI-only action
(GitHub does not expose App installation to a PAT), and until that happens every production
deploy has to be made by hand.

`POST /v13/deployments` with a `gitSource` keeps working WITHOUT the project's git link —
repo access lives at team/integration level, not at project-link level. That asymmetry is
the whole reason this script can exist. What does NOT work:

  * `vercel deploy --prod` — no .vercelignore, so it uploads the entire monorepo; measured
    at >25 minutes without producing a deployment on a loaded machine.
  * Deploy Hooks — refused outright: "This project is not connected to a Git repository,
    so it cannot have deploy hooks."

ONE PROJECT, EIGHT DOMAINS
--------------------------
balizero.com and every subdomain (www, kita, my, prime, visa, tax, zantara) are served by
the single `mouth` project. A stale frontend is stale everywhere, never on one page.

THE ALIAS IS NOT AUTOMATIC HERE
-------------------------------
Measured 2026-07-28: a deployment created with `gitSource.ref = <sha>` reached READY with
`aliasAssigned: false` and production kept serving the previous build until an explicit
`POST /v10/projects/<id>/promote/<dpl>`. A deployment created with `ref = "main"` on
2026-07-27 self-aliased within 30s. So promote is attempted whenever the probe still shows
the old commit — and `aliasAssigned` is never read as the verdict: during a build it is
false for every deployment, and even at READY it has been observed disagreeing with what
the domains actually serve. The arbiter is the behavioural probe (W88: verify by content).

CREDENTIAL
----------
Reads the Vercel CLI's OAuth token from its auth.json and never prints it. `expiresAt` in
that file is in SECONDS, not milliseconds — treating it as ms makes an expired token look
valid until the year 58000. Refresh with `vercel whoami`, which renews silently.

Usage:
    python3 scripts/vercel_prod_deploy.py            # deploy main HEAD if production is behind
    python3 scripts/vercel_prod_deploy.py --force    # deploy even if production is current
    python3 scripts/vercel_prod_deploy.py --dry-run  # report the gap, change nothing
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

TEAM_ID = "team_jX3mEbUemBs0Zy4i8aFYZsjS"  # nuzantara-2026
PROJECT_ID = "prj_LcXb9ZgeUvWpxaIM9K47tQYPeuee"  # mouth
REPO_ORG = "Bali-Zero"
REPO_NAME = "Teman2"
HEALTH_URL = "https://balizero.com/api/health"
AUTH_JSON = "~/Library/Application Support/com.vercel.cli/auth.json"

BUILD_TIMEOUT_S = 600
POLL_S = 20


def _token() -> str:
    path = os.path.expanduser(AUTH_JSON)
    if not os.path.exists(path):
        sys.exit(f"no Vercel CLI credential at {AUTH_JSON} — run `vercel login` on this machine")
    with open(path) as fh:
        data = json.load(fh)
    expires_at = data.get("expiresAt")  # SECONDS
    if expires_at and expires_at < time.time():
        sys.exit("Vercel token expired — run `vercel whoami` to refresh it, then retry")
    token = data.get("token")
    if not token:
        sys.exit(f"{AUTH_JSON} holds no token — run `vercel login` on this machine")
    return str(token)


def _api(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    url = f"https://api.vercel.com{path}"
    url += ("&" if "?" in url else "?") + f"teamId={TEAM_ID}"
    payload = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=payload, method=method)
    req.add_header("Authorization", f"Bearer {_token()}")
    if payload:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def _main_head() -> str:
    out = subprocess.run(
        ["gh", "api", f"/repos/{REPO_ORG}/{REPO_NAME}/commits/main", "--jq", ".sha"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def _served_commit() -> str | None:
    """What commit is production actually running? None on any failure — a failed probe is
    never evidence of health."""
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=25) as resp:
            return json.loads(resp.read()).get("commit")
    except Exception as exc:  # noqa: BLE001 — every failure mode means "unknown", identically
        print(f"  probe failed: {exc}")
        return None


def _wait_terminal(deployment_id: str) -> tuple[str | None, bool]:
    deadline = time.time() + BUILD_TIMEOUT_S
    state: str | None = None
    alias_assigned = False
    while time.time() < deadline:
        time.sleep(POLL_S)
        status, body = _api("GET", f"/v13/deployments/{deployment_id}")
        if status != 200:
            print(f"  poll HTTP {status}: {json.dumps(body)[:200]}")
            continue
        state = body.get("readyState")
        alias_assigned = bool(body.get("aliasAssigned"))
        print(f"  state={state} aliasAssigned={alias_assigned}")
        if state in ("READY", "ERROR", "CANCELED"):
            break
    return state, alias_assigned


def _probe_until(sha: str, attempts: int) -> bool:
    for i in range(attempts):
        live = _served_commit()
        print(f"  probe {i + 1}/{attempts}: production serves {live}")
        if live == sha:
            return True
        if i + 1 < attempts:
            time.sleep(15)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="deploy even when production is already current")
    parser.add_argument("--dry-run", action="store_true", help="report the gap and exit without deploying")
    parser.add_argument("--ref", default=None, help="commit sha to deploy (default: main HEAD)")
    args = parser.parse_args()

    sha = args.ref or _main_head()
    live = _served_commit()
    print(f"main HEAD       : {sha}")
    print(f"production runs : {live}")

    if live == sha and not args.force:
        print("production is already serving this commit — nothing to do")
        return 0
    if args.dry_run:
        print("dry-run: would deploy, but changing nothing")
        return 0

    status, deployment = _api("POST", "/v13/deployments", {
        "name": "mouth",
        "project": PROJECT_ID,
        "target": "production",
        "gitSource": {"type": "github", "org": REPO_ORG, "repo": REPO_NAME, "ref": sha},
    })
    if status not in (200, 201):
        print(f"CREATE FAILED HTTP {status}: {json.dumps(deployment)[:600]}")
        return 1
    deployment_id = deployment["id"]
    print(f"created         : {deployment_id} ({deployment.get('readyState')})")

    state, _alias = _wait_terminal(deployment_id)
    if state != "READY":
        print(f"deployment ended {state} — build logs: vercel inspect --logs {deployment_id}")
        return 1

    if _probe_until(sha, attempts=8):
        print(f"OK — balizero.com serves {sha[:9]} (deployment {deployment_id})")
        return 0

    # READY but the domains never moved: the alias did not follow. This is the documented
    # fallback, not the normal path — and it is the observed path for a sha-ref deployment.
    print("production still on the old build at terminal READY → promote")
    status, body = _api("POST", f"/v10/projects/{PROJECT_ID}/promote/{deployment_id}", {})
    print(f"promote HTTP {status}: {json.dumps(body)[:300]}")
    if status not in (200, 201, 202):
        return 1
    if _probe_until(sha, attempts=8):
        print(f"OK after promote — balizero.com serves {sha[:9]}")
        return 0

    print(f"::error::deployment {deployment_id} is READY but the domains still do not serve {sha[:9]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
