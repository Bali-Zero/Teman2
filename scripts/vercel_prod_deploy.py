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

THE TARGET IS NOT main HEAD (2026-08-10)
----------------------------------------
The promote-first path above was correct and still almost never fired, because it looked for
a build of `main HEAD`. This repo lands ~40 PRs a day and almost none touch the frontend, so
HEAD is nearly always a commit Vercel deliberately SKIPPED — there is never a READY build for
it, and production can never equal it. Both of this script's good outcomes were unreachable.

Measured the day it was found: production served a 4h50m-old build; a READY, never-aliased
`target=production` build for the newest frontend commit was sitting on Vercel; `--dry-run`
reported "no READY build for this commit" and the default run would have bought a 6-minute
rebuild instead of a 3-second promote. The alarm that fires in this situation — the Frontend
Live Sentinel — had ALREADY been fixed for exactly this on 2026-07-28 ("does production
INCLUDE this commit, not does it EQUAL this sha"); the cure was simply never taught the same
rule. Two tools answering "which commit must production serve?" now share one definition and
a test that reads one out of the other.

Usage:
    python3 scripts/vercel_prod_deploy.py            # promote (or, failing that, deploy) the newest bundle-relevant commit
    python3 scripts/vercel_prod_deploy.py --force    # act even if production is already current
    python3 scripts/vercel_prod_deploy.py --dry-run  # report the gap and the plan, change nothing
    python3 scripts/vercel_prod_deploy.py --ref SHA  # override the target commit

Exit codes: 0 nothing to do or done · 1 the action failed · 3 (--promote-only) there was no
READY build to promote, and none was created. 3 rather than 2 because argparse owns 2.
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

# Paths that can change what the browser receives. This is the SAME question the Frontend
# Live Sentinel asks in `.github/workflows/frontend-live-sentinel.yml`, and the two must give
# the same answer: that workflow raises the alarm, this script is its cure, and a cure aimed
# at a different commit than the alarm is not a cure. Pinned by
# scripts/tests/test_vercel_prod_deploy_target_rule.py, which reads the list back out of the
# workflow — so editing one without the other fails CI rather than drifting quietly.
#
# apps/mouth/e2e is excluded: those specs run in CI and never reach the bundle, so demanding
# a deploy for them manufactures work with no user-visible referent.
#
# A THIRD file also decides what reaches the bundle — scripts/ci/vercel_should_build.sh, the
# Vercel Ignored Build Step — and it deliberately does NOT exclude e2e. That asymmetry is
# correct and must not be "tidied": that script is fail-open by construction (a build we did
# not need costs minutes; a build we needed and skipped freezes eight domains), so it errs
# toward building. This pair errs toward not nagging. Same paths, opposite safe directions —
# they are not the same question and must not be merged into one constant.
BUNDLE_PATHS = ("apps/mouth", "packages", "package.json", "package-lock.json", "vercel.json")
BUNDLE_EXCLUDE = (":(exclude)apps/mouth/e2e",)


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


# An `expiresAt` in SECONDS cannot plausibly exceed this (year 5138); one in MILLISECONDS
# always does (that is 1973 in ms). Anything above it is therefore ms, not a far-future token.
_MS_CUTOFF = 1e11


def _expiry_seconds(raw: object) -> float | None:
    """Normalise `expiresAt` to seconds. `None` = unknown; any garbage = TREAT AS EXPIRED.

    The docstring at the top of this file has warned since it was written that reading this
    value as milliseconds "makes an expired token look valid until the year 58000" — and the
    code enforced nothing, so the warning was decoration. Caught by an independent review
    (GLM 5.2, which did not write this) and reproduced on disk before being believed: with
    the plain `bool(x) and x < time.time()` test, `0` read as NOT expired (falsy swallows a
    real epoch timestamp), a millisecond value read as NOT expired, and a numeric STRING
    raised an uncaught `TypeError` comparing str to float. Writing the remedy down instead
    of running it is the same defect this whole file was just fixed for.

    Every ambiguous case resolves to EXPIRED on purpose. The cost of being wrong that way is
    one extra ~1s refresh; the cost of the other way is handing out a dead token, i.e. the
    403 that gets misread as "no credential on the fleet".
    """
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0  # unreadable → expired, never "valid because we could not tell"
    if value > _MS_CUTOFF:
        value /= 1000.0
    return value


def _token() -> str:
    data = _read_auth()
    expires_at = _expiry_seconds(data.get("expiresAt"))  # normalised to SECONDS
    expired = expires_at is not None and expires_at < time.time()
    if expired or not data.get("token"):
        print("  Vercel token expired — refreshing via `vercel whoami`", file=sys.stderr)
        if not _refresh_credential():
            sys.exit(
                "Vercel token expired and could not be refreshed — run `vercel login` "
                "on this machine (browser device-code flow, the one step a session cannot do)"
            )
        data = _read_auth()
        # Declared limit: this re-reads the EXPIRY, not the token VALUE. A `whoami` that
        # moved the expiry forward while leaving the same access token in place would pass
        # here. Comparing the value instead was considered and rejected — whether an OAuth
        # refresh must mint a new access token is a guess about Vercel's server, and a cure
        # anchored on a guess about a vendor is W106 verbatim. The file is the authority on
        # its own validity; the API call that follows is what actually settles it.
        refreshed_at = _expiry_seconds(data.get("expiresAt"))
        still_expired = refreshed_at is not None and refreshed_at < time.time()
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


def _git(*args: str) -> str | None:
    """stdout on success, None on ANY failure. Never conflate the two: `git fetch` succeeds
    with empty stdout, so an empty string is a result and None is 'could not look'."""
    try:
        # A TIMEOUT, because this is now called unattended every 900s. Without one, a fetch
        # that half-opens against the network hangs forever; the wrapper's pidfile then sees a
        # live pid on every later tick and skips, and the organ is wedged with no upper bound.
        # 120s is far above a normal fetch here and far below the 900s cadence.
        out = subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True, timeout=120
        )
    except Exception:  # noqa: BLE001 — missing git, not a repo, network, timeout: all "unknown"
        return None
    return out.stdout.strip()


# Three attempts at a 120s timeout plus 3s+9s backoff worst-case at 372s — comfortably inside
# 900s cadence, so a genuinely dead network degrades on THIS tick instead of wedging the organ
# into the next one.
FETCH_ATTEMPTS = 3
FETCH_BACKOFF_S = (3.0, 9.0)


def _fetch_main() -> tuple[bool, str]:
    """Refresh origin/main, riding out a TRANSIENT failure instead of degrading on it.

    This is the only network step on the unattended path, and it runs every 900s on a machine
    whose network measurably flaps. Measured on Mini the day the organ was armed: of the first
    five runs one could not fetch, the system log showed three network-configuration changes
    and a Wi-Fi change in the five minutes before it, and the good run that followed took 39s
    against a usual 4s. Degrading on a lone blip is correct but expensive — it costs 15 minutes
    of blindness — so the one-shot network action is wrapped in a bounded retry (superscar #8).

    Returns (ok, detail). On failure `detail` is what git actually SAID. `_git` deliberately
    collapses every cause into `None`, which is right for a caller that only needs "could not
    look" — but it left the operator-facing message unable to name the cause, and a refused
    connection, DNS, a dead credential and a 120s timeout call for four different answers. The
    discriminator that was available that day and invisible in the log: `gh api` answered over
    HTTPS in the same second the SSH fetch failed. A message that does not name its cause sends
    the reader away from it (W106).
    """
    detail = "no attempt ran"
    for attempt in range(1, FETCH_ATTEMPTS + 1):
        try:
            subprocess.run(
                ["git", "fetch", "--no-tags", "--quiet", "origin", "main"],
                capture_output=True, text=True, check=True, timeout=120,
            )
        except subprocess.TimeoutExpired:
            detail = "timed out after 120s"
        except subprocess.CalledProcessError as exc:
            said = ((exc.stderr or "") + " " + (exc.output or "")).strip()
            detail = (" ".join(said.split())[:200]) or f"git exited {exc.returncode}"
        except Exception as exc:  # noqa: BLE001 — no git, not a repo: still "could not look"
            detail = f"{type(exc).__name__}: {exc}"[:200]
        else:
            if attempt > 1:
                print(f"  fetch recovered on attempt {attempt} (transient)")
            return True, f"attempt {attempt}"
        if attempt < FETCH_ATTEMPTS:
            print(f"  fetch attempt {attempt} failed ({detail}) — retrying")
            time.sleep(FETCH_BACKOFF_S[min(attempt - 1, len(FETCH_BACKOFF_S) - 1)])
    return False, detail


def _deploy_relevant_head() -> tuple[str, str]:
    """The newest commit on main that can change the built app, plus how it was obtained.

    NOT main HEAD. This repo lands ~40 PRs a day and almost none of them touch the frontend,
    so main HEAD is nearly always a commit that cannot change the bundle. Asking whether
    production runs THAT sha made two answers impossible: 'production is current' (unreachable
    unless HEAD happens to be a frontend commit) and 'a READY build already exists' (there is
    never one for a skipped commit). Measured 2026-08-10: production had been serving a
    4h50m-old build while a READY, never-aliased production build for the newest frontend
    commit sat on Vercel; this script's --dry-run said 'no READY build for this commit' and
    would have spent a 6-minute rebuild instead of a 3-second promote.

    Degrades to main HEAD — the old behaviour — when git cannot answer, and SAYS so. Being
    unable to look is not evidence that no frontend commit exists.
    """
    fetched, why = _fetch_main()
    if not fetched:
        return _main_head(), f"main HEAD — git fetch failed ({why}), could not filter by path"
    sha = _git("log", "-1", "--format=%H", "origin/main", "--", *BUNDLE_PATHS, *BUNDLE_EXCLUDE)
    if sha is None:
        return _main_head(), "main HEAD — git log failed, could not filter by path"
    if not sha:
        return _main_head(), "main HEAD — no commit in history touches a bundle path"
    return sha, "newest bundle-relevant commit on main"


def _production_includes(target: str, live: str | None) -> bool:
    """Does production already carry this commit? Production may legitimately be AHEAD of the
    target and must never be nagged for that; it may never be behind.

    Ancestry is normally a proxy that lies (W88) — here it does not, for the reason the
    sentinel states: both shas live on main's linear history. Anything that cannot be placed
    in that history fails CLOSED (act), because 'I could not check' is not 'it is fine'.
    """
    if not live:
        return False
    if live == target:
        return True
    rc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", target, live], capture_output=True, text=True
    )
    # 0 = ancestor, 1 = not, 128 = an object we do not have. Only 0 is currency.
    return rc.returncode == 0


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


# How far back to look for an older bundle-relevant commit when the newest one has no READY
# build yet. Bounds the worst case at this many `_ready_deployment_for` calls (one GET each).
FALLBACK_SCAN_DEPTH = 10


def _ready_deployment_among_recent_bundle_commits(
    live: str | None,
) -> tuple[str, str, str] | None:
    """--promote-only's fallback: the newest bundle-relevant commit is the correct target, but
    Vercel may not have built it yet (still building, or skipped it — see the BUNDLE_PATHS
    comment). Walking backward through the last FALLBACK_SCAN_DEPTH bundle-relevant commits for
    one that already has a READY build lets production advance to it instead of sitting on
    whatever it already serves for another 15-minute cron tick.

    This is NOT a relaxation of --promote-only's contract (still never builds). It only widens
    which already-built commit counts as 'the thing to promote'.

    Walks newest-first and stops at the first commit production already includes: on a linear
    history that commit's parents are ancestors too, so scanning past it can only repeat 'already
    current' — the caller does that check on the primary target already.

    Returns (sha, deployment_id, readySubstate) for the first one found, or None.
    """
    shas = _git("log", f"-{FALLBACK_SCAN_DEPTH}", "--format=%H", "origin/main", "--", *BUNDLE_PATHS, *BUNDLE_EXCLUDE)
    if not shas:
        return None
    for candidate in shas.splitlines():
        if _production_includes(candidate, live):
            break
        existing = _ready_deployment_for(candidate)
        if existing:
            return candidate, existing[0], existing[1]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="deploy even when production is already current")
    parser.add_argument("--dry-run", action="store_true", help="report the gap and exit without deploying")
    parser.add_argument("--ref", default=None, help="commit sha to deploy (default: main HEAD)")
    parser.add_argument(
        "--promote-only",
        action="store_true",
        help="promote an existing READY build and NEVER create one (the mode a cron may run)",
    )
    args = parser.parse_args()

    if args.ref:
        sha, how = args.ref, "--ref override"
    else:
        sha, how = _deploy_relevant_head()
    live = _served_commit()
    print(f"target commit   : {sha}")
    print(f"  chosen as     : {how}")
    print(f"production runs : {live}")

    if _production_includes(sha, live) and not args.force:
        print("production already includes this commit — nothing to do")
        return 0
    # Prefer promoting an existing READY build for this exact commit over rebuilding it.
    existing = _ready_deployment_for(sha)
    if existing:
        dpl, substate = existing
        print(f"already built     : {dpl} (readySubstate={substate}) — promote, do not rebuild")
    # No READY build for the newest bundle-relevant commit yet — before giving up (dry-run's
    # verdict and --promote-only's real behaviour must agree), look for an older bundle-relevant
    # commit that IS already built. Only relevant to the two restricted paths below; the
    # interactive default can just build sha itself, so it never needs this.
    fallback = None
    if not existing and (args.dry_run or args.promote_only):
        fallback = _ready_deployment_among_recent_bundle_commits(live)
        if fallback:
            fb_sha, fb_dpl, fb_substate = fallback
            print(
                f"no READY build for {sha[:9]} (the newest bundle-relevant commit) — found an "
                f"older one already built and unpromoted: {fb_sha[:9]} ({fb_dpl}, "
                f"readySubstate={fb_substate})"
            )
    if args.dry_run:
        if existing:
            print("dry-run: would PROMOTE the build above, changing nothing")
        elif fallback:
            print(f"dry-run: would PROMOTE the older commit {fallback[0][:9]} above, changing nothing")
        else:
            print("dry-run: no READY build for this commit — would deploy, changing nothing")
        return 0

    # --promote-only is the CRON contract, and it is a restriction, not an optimisation.
    # Unattended, "no READY build exists" must never buy a rebuild: at a 15-minute cadence
    # that is a build loop nobody asked for, and the condition itself is an anomaly worth a
    # human's eyes (Vercel skipped the commit, or the build failed). Exit 2 says exactly that
    # and is deliberately NOT 1 — a wrapper reading one failure bit cannot tell "the promote
    # broke" from "there was nothing to promote", and those need different responses.
    if args.promote_only:
        if not existing and fallback:
            fb_sha, fb_dpl, _ = fallback
            if _promote(fb_dpl, fb_sha):
                print(
                    f"OK — balizero.com serves {fb_sha[:9]} (promoted {fb_dpl}, no rebuild; "
                    f"newest bundle-relevant commit {sha[:9]} still awaits its own build)"
                )
                return 0
            print(f"::error::promote of {fb_dpl} did not move the domains to {fb_sha[:9]}")
            return 1
        if not existing:
            print(f"no READY production build for {sha[:9]} — --promote-only will not create one")
            # 3, NOT 2. argparse exits 2 on an unrecognised flag, and an unattended wrapper
            # cannot tell those two apart from the code alone — it would read "the script does
            # not know --promote-only" (nothing ran, nothing was cured) as the benign "there
            # was nothing to promote" and report a healthy-ish heartbeat forever. Measured,
            # not imagined: running --promote-only against the pre-merge copy on Mini exits 2.
            return 3
        if _promote(existing[0], sha):
            print(f"OK — balizero.com serves {sha[:9]} (promoted {existing[0]}, no rebuild)")
            return 0
        print(f"::error::promote of {existing[0]} did not move the domains to {sha[:9]}")
        return 1

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
