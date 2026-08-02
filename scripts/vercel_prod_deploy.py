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
valid until the year 58000.

The token lives for hours, so an EXPIRED one is the ordinary state, not a broken machine:
this script now redeems the `refreshToken` sitting next to it by running `vercel whoami`,
instead of telling a human to. It used to print that instruction and exit — which is how a
2026-08-02 census read `403 {"invalidToken": true}` as "no working credential exists
anywhere on the fleet" and parked a merged frontend cure on an operator login that was not
needed. `vercel login` is genuinely the entrance ONLY when the refresh fails.

PROMOTE FIRST, BUILD ONLY IF YOU MUST (2026-07-30)
--------------------------------------------------
The premise at the top of this file has partly EXPIRED, and the correction matters more than
the original. The Vercel GitHub App is installed again — measured 2026-07-30, 20 of the 20
most recent GitHub Deployments were created by `vercel[bot]`, and a merge produces a
`target=production` deployment within seconds that reaches READY after a real build.

What does NOT happen is the promote. Every one of those deployments lands
`readySubstate: STAGED`: built, never aliased. Six of six unpromoted ones were STAGED; the
only two PROMOTED were promoted by hand. `autoAssignCustomDomains` is true and rolling
releases are not configured (`vercel rolling-release fetch` → null), so neither explains it;
the project setting that does is undocumented and is deliberately NOT guessed at here.

So the usual gap is not "production has no build", it is "production has a build nobody
pointed the domains at". This script now looks for that build first and promotes it (~3s)
instead of creating a second deployment of the same tree (~6 min + build minutes). It falls
back to building when there is genuinely nothing READY for the commit.

Usage:
    python3 scripts/vercel_prod_deploy.py            # promote (or, failing that, deploy) main HEAD
    python3 scripts/vercel_prod_deploy.py --force    # act even if production is already current
    python3 scripts/vercel_prod_deploy.py --dry-run  # report the gap and the plan, change nothing
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


def _read_auth() -> dict:
    path = os.path.expanduser(AUTH_JSON)
    if not os.path.exists(path):
        sys.exit(f"no Vercel CLI credential at {AUTH_JSON} — run `vercel login` on this machine")
    with open(path) as fh:
        return json.load(fh)


def _refresh_credential() -> bool:
    """Redeem the `refreshToken` already in auth.json by running `vercel whoami`.

    EXPIRY IS NOT ABSENCE, AND READING IT AS ABSENCE INVENTS AN OPERATOR STEP.
    This token's lifetime is hours, so `403 {"invalidToken": true}` is the NORMAL
    state a few hours after any login. On 2026-08-02 a credential census read that
    403 on M5, plus a placeholder file on Pro and none on Mini, and concluded that
    no working credential existed anywhere on the fleet — so a frontend cure sat
    merged-but-not-served waiting for a human to log in again. The file had held a
    `refreshToken` the whole time: `vercel whoami` redeemed it in one second and the
    same session promoted with it. A human login is the entrance ONLY when the
    refresh itself fails.

    Shelling out to the CLI rather than calling the OAuth endpoint directly is
    deliberate: the endpoint, the client id and the file layout are the CLI's
    business and change without notice, and this script must not own three moving
    parts to save one subprocess.
    """
    try:
        proc = subprocess.run(
            ["vercel", "whoami"], capture_output=True, text=True, timeout=60, check=False
        )
    except FileNotFoundError:
        print("  vercel CLI not on PATH — cannot refresh the token here", file=sys.stderr)
        return False
    except subprocess.TimeoutExpired:
        print("  `vercel whoami` timed out — token not refreshed", file=sys.stderr)
        return False
    if proc.returncode != 0:
        # Never echo the CLI's stdout: it is the account identity, not a secret, but
        # the failure path is where a token most often ends up quoted into a log.
        print(f"  `vercel whoami` exited {proc.returncode} — token not refreshed", file=sys.stderr)
        return False
    return True


def _token() -> str:
    data = _read_auth()
    expires_at = data.get("expiresAt")  # SECONDS, not milliseconds
    expired = bool(expires_at) and expires_at < time.time()
    if expired or not data.get("token"):
        print("  Vercel token expired — refreshing via `vercel whoami`", file=sys.stderr)
        if not _refresh_credential():
            sys.exit(
                "Vercel token expired and could not be refreshed — run `vercel login` "
                "on this machine (browser device-code flow, the one step a session cannot do)"
            )
        data = _read_auth()
        still_expired = bool(data.get("expiresAt")) and data["expiresAt"] < time.time()
        if still_expired:
            sys.exit("`vercel whoami` returned 0 but the credential is still expired — run `vercel login`")
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


def _ready_deployment_for(sha: str) -> tuple[str, str] | None:
    """Is a production build for this commit ALREADY built and merely waiting to be promoted?

    Measured 2026-07-30 on this project: every production deployment the Git integration
    creates lands `READY` with `readySubstate: STAGED` — built, but the custom domains are
    never repointed at it. Six of six unpromoted ones were STAGED; the only two PROMOTED were
    promoted by hand. So the normal state after a merge is "the build you need already exists".

    Promoting it takes ~3s and rebuilds nothing. Creating a second deployment for the same
    commit takes ~6 minutes, burns build minutes, and produces a duplicate — for a tree that
    is byte-identical to one already sitting READY.

    Returns (deployment_id, substate) or None. Any failure returns None: not finding a
    shortcut must never block the rebuild path, only skip the optimisation.
    """
    status, body = _api(
        "GET", f"/v6/deployments?projectId={PROJECT_ID}&target=production&limit=20"
    )
    if status != 200:
        print(f"  could not list deployments (HTTP {status}) — will build instead")
        return None
    for dep in body.get("deployments", []):
        # `state` is the v6 spelling of readyState. CANCELED/ERROR builds are not promotable,
        # and a CANCELED one is the NORMAL outcome for a commit the ignore-step skipped.
        if dep.get("state") != "READY":
            continue
        if (dep.get("meta") or {}).get("githubCommitSha") != sha:
            continue
        uid = dep.get("uid")
        if not uid:
            continue
        return str(uid), str(dep.get("readySubstate"))
    return None


def _promote(deployment_id: str, sha: str) -> bool:
    status, body = _api("POST", f"/v10/projects/{PROJECT_ID}/promote/{deployment_id}", {})
    print(f"promote HTTP {status}: {json.dumps(body)[:300]}")
    if status not in (200, 201, 202):
        return False
    # The arbiter is the behavioural probe, never the HTTP code and never `aliasAssigned`
    # (W88: verify by content). A 202 only says the request was accepted.
    return _probe_until(sha, attempts=8)


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
    # Prefer promoting an existing READY build for this exact commit over rebuilding it.
    existing = _ready_deployment_for(sha)
    if existing:
        dpl, substate = existing
        print(f"already built     : {dpl} (readySubstate={substate}) — promote, do not rebuild")
    if args.dry_run:
        if existing:
            print("dry-run: would PROMOTE the build above, changing nothing")
        else:
            print("dry-run: no READY build for this commit — would deploy, changing nothing")
        return 0

    if existing:
        if _promote(existing[0], sha):
            print(f"OK — balizero.com serves {sha[:9]} (promoted {existing[0]}, no rebuild)")
            return 0
        # Fall through rather than fail: the build may be genuinely unusable (an alias
        # conflict, a deployment deleted mid-flight). A rebuild is slower, never wrong.
        print("promote did not move the domains — falling back to a rebuild")

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
    if _promote(deployment_id, sha):
        print(f"OK after promote — balizero.com serves {sha[:9]}")
        return 0

    print(f"::error::deployment {deployment_id} is READY but the domains still do not serve {sha[:9]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
