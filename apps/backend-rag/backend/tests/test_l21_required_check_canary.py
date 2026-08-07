"""L2.1 CANARY — deliberately red in CI, green locally. NEVER MERGE THIS FILE.

Why this exists
---------------
`gh api .../branches/main/protection/required_status_checks` lists
"Backend Tests (Python)" among main's required contexts. That listing is a
PROXY: it says the context is *registered*, not that GitHub *enforces* it.
Superscar #2 (esiste != armato) is precisely the failure mode where an
artifact is present in a registry and inert in practice — a required context
that is never reported, or reported under a different name, satisfies the API
read while blocking nothing.

The only proof that survives that objection is adversarial: put a red
`Backend Tests (Python)` in front of a real PR and observe GitHub refuse the
merge. This file is that red.

Why it is CI-only red
---------------------
The pre-push gate (`.husky/pre-push` + `scripts/prepush_classify.py`) pays the
full backend suite for any change under `backend/tests/`. A test that failed
locally too would be stopped at the push and never reach GitHub — the canary
would prove nothing about branch protection and would only re-prove that the
local gate works. Failing exclusively under `GITHUB_ACTIONS`/`CI` keeps every
local guard armed and honest while still delivering the red verdict to the
surface actually under test.

Lifecycle
---------
Opened, observed, and closed within one session; the PR carrying it is closed
and its branch deleted, never merged. If you are reading this file on `main`,
the canary escaped its own experiment: delete it and treat the escape as the
P0 finding (branch protection did NOT hold).
"""

import os

_IN_CI = os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI") == "true"


def test_l21_required_check_canary_is_red_in_ci() -> None:
    """Fail under CI so `Backend Tests (Python)` reports a real failure.

    Guilt (CI): the assertion below fails, the job goes red, and branch
    protection must hold the PR.
    Innocence (local/dev): the same assertion passes, so this file never
    blocks a developer push and never masks an unrelated local regression.
    """
    assert not _IN_CI, (
        "L2.1 CANARY: this failure is INTENTIONAL. It exists to prove that the "
        "'Backend Tests (Python)' required status check actually blocks a merge "
        "into main. If you are seeing this on a PR that is not the L2.1 canary, "
        "the file leaked out of its experiment — delete it."
    )
