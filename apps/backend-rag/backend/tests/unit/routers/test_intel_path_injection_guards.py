"""
Guilt AND innocence for the three intel path-injection sinks cured in this PR.

The validator already existed (`intel_staging_service.assert_valid_item_id`, born with
the cover-handler fix). This is a CLASS audit of its callers: three surfaces built a
staging path from a caller-supplied `item_id` without ever calling it.

`backend/tests/unit/services/intel/test_intel_item_id_shape.py` owns the validator's
own guilt/innocence and the cover-handler twin; this file owns the ROUTER sinks and the
identity pins that keep the four surfaces from drifting apart.

Honest severity, per sink, measured rather than assumed:

* ``intel.upload_cover_image`` — the worst of the three: path, EXTENSION and CONTENT are
  all request-controlled. Probed anonymously against prod it answers 401 (the global
  middleware gates ``/api/...`` before routing), so the reachable population is
  authenticated team members, not the internet.
* ``telegram_webhook.handle_intel_callback`` — no auth dependency of its own, and
  ``callback_data`` passes through no URL decoder. ``POST /webhook/telegram`` answers
  503 today because ``get_channel_router`` fails to resolve — an accidental barrier
  standing in front of it, not a designed one.
* ``intel_scraper._publish_staging_item`` — its write is NOT reachable with a malformed
  id today, because ``load_staging_item`` 7 lines above returns None for one and the
  function 404s. That defense is remote and is a side effect of a read's contract; the
  guard makes it local. Said plainly so nobody reads this test as "a live hole closed".
"""

import ast
import json
import re
from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.app.routers import intel as intel_mod
from backend.app.routers import intel_scraper as scraper_mod
from backend.app.routers import telegram_webhook as webhook_mod
from backend.services.intel.intel_staging_service import assert_valid_item_id as canonical

# One traversal payload, used everywhere, so a sink that "passes" cannot be passing
# against a weaker input than its neighbours.
TRAVERSAL = "../../../../tmp/pwned"
LEGIT = "news_20260801_120000_a1b2c3d4"


# MEASURED, and NOT fixed here: merely importing `backend.app.routers.intel` constructs
# `IntelStagingService()` and `IntelApprovalService()` at module scope, and BOTH mkdir in
# `__init__` — so collection alone creates `<staging_base>/{visa,news}` and the pending
# dir (with real settings: `/tmp/staging/...`, `/tmp/pending_intel`). Proven by importing
# the module with those paths pointed at names that did not exist: they appeared.
# This PRE-DATES this file (every existing `unit/routers/test_intel_*` already imports the
# same module) and the cure is making those singletons lazy — a production refactor, not a
# test tweak — so it is a ledger line, not a silent assumption. The fixtures below keep
# everything these tests THEMSELVES do inside tmp_path; they cannot undo an import.


def _redirect_staging_root(monkeypatch, tmp_path) -> None:
    """
    W96: a unit test must not mkdir or write the real staging tree.

    Repointing `settings` is NOT enough here: `IntelStagingService.__init__` resolves
    the base dir ONCE and caches it on the instance, and `intel.staging_service` was
    constructed at import time. `intel_scraper` imports that same singleton (it defines
    none of its own), so redirecting it covers both routers — asserted below rather
    than assumed, because a future split into two instances would silently un-redirect
    one of them and the tests would start writing outside tmp_path.
    """
    assert scraper_mod.staging_service is intel_mod.staging_service
    base = Path(tmp_path)
    for attr, value in (
        ("base_staging_dir", base),
        ("visa_staging_dir", base / "visa"),
        ("news_staging_dir", base / "news"),
    ):
        monkeypatch.setattr(intel_mod.staging_service, attr, value)


def _set_settings_attr(monkeypatch, name: str, value: str) -> None:
    """
    Repoint one settings value in BOTH worlds this file runs in.

    `backend/tests/unit/routers/conftest.py` installs a fake `backend.app.core.config`
    whose `settings` is a MagicMock — but ONLY IF the real module is not already in
    `sys.modules`. So which object the code under test reads depends on the INVOCATION:
    run this file alone and it is a MagicMock (plain attributes); run it inside
    `pytest backend/tests/` and something earlier imported the real module, so it is a
    real `Settings` whose `get_intel_pending_path` is a read-only property.

    A helper that handles one world passes in isolation and fails in CI — which is how
    the first draft of this file behaved. Patch whichever object is actually there, and
    assert the binding TOOK rather than assuming setattr means read-back (W110).
    """
    target = webhook_mod.settings
    if isinstance(getattr(type(target), name, None), property):
        monkeypatch.setattr(type(target), name, property(lambda _self: value), raising=True)
    else:
        monkeypatch.setattr(target, name, value, raising=False)
    assert getattr(webhook_mod.settings, name) == value, (
        f"redirect of {name} did not take — the code under test still reads the old value"
    )


def _escape_target(sink_dir: Path, sandbox: Path, marker: str, suffix: str) -> tuple[str, Path]:
    """
    Build a traversal id that lands EXACTLY one level above the sandbox, and return the
    path it would resolve to.

    Hand-writing `../../` and then asserting `not outside.exists()` is how a guilt test
    goes vacuous: the sink appends its own suffix (`.json`, `{ext}`) and each sink sits
    at a different depth under the sandbox, so the name you assert absent is one the code
    could never have written — the assertion passes with the guard REMOVED. Found by the
    live negative control, which reported "nothing written outside" for two sinks while
    one of them had just written a file. Depth and suffix both come from the caller's
    real values here, so the assertion names the file that would actually appear.
    """
    depth = len(sink_dir.resolve().relative_to(sandbox.resolve()).parts) + 1
    item_id = "../" * depth + marker
    target = sandbox.parent / f"{marker}{suffix}"
    assert (sink_dir / f"{item_id}{suffix}").resolve() == target.resolve(), (
        "the escape target this test asserts on is not where the sink would write"
    )
    return item_id, target


def _redirect_pending_root(monkeypatch, tmp_path) -> None:
    """`get_intel_pending_path` is read at call time, so repointing settings suffices."""
    _set_settings_attr(monkeypatch, "get_intel_pending_path", str(tmp_path))


class TestEveryStagingSinkBindsTheSameValidator:
    """
    Identity, not presence.

    A module that grew its own copy of the regex would pass a "is it validated?" test
    and still drift the day the canonical one is tightened. `is canonical` cannot.
    """

    @pytest.mark.parametrize(
        "module",
        [intel_mod, scraper_mod, webhook_mod],
        ids=["intel", "intel_scraper", "telegram_webhook"],
    )
    def test_router_imports_the_shared_validator_object(self, module) -> None:
        assert module.assert_valid_item_id is canonical


class TestCoverUploadRoute:
    """`POST /api/intel/staging/{type}/{item_id}/cover` — intel.py."""

    @pytest.mark.asyncio
    async def test_guilt_a_traversal_id_is_refused_before_anything_is_written(
        self, tmp_path, monkeypatch
    ) -> None:
        _redirect_staging_root(monkeypatch, tmp_path)
        covers_dir = intel_mod.staging_service.get_staging_dir("news") / "covers"
        item_id, target = _escape_target(covers_dir, tmp_path, "zz-cover-never-exists", ".jpg")

        body = intel_mod.CoverImageUploadRequest(cover_image_base64="", cover_image_filename=None)
        with pytest.raises(HTTPException) as exc:
            await intel_mod.upload_cover_image(type="news", item_id=item_id, request=body)

        assert exc.value.status_code == 400
        assert not target.exists(), f"the guard let a write escape to {target}"

    @pytest.mark.asyncio
    async def test_guilt_a_hostile_extension_is_refused_even_with_a_valid_id(
        self, tmp_path, monkeypatch
    ) -> None:
        """
        The id is only half the filename. `PathLib(x).suffix` of an arbitrary string is
        an arbitrary string, so a valid id plus `cover_image_filename="x.py"` chooses
        the extension of a file this endpoint writes attacker-supplied bytes into.
        """
        _redirect_staging_root(monkeypatch, tmp_path)
        monkeypatch.setattr(
            intel_mod.staging_service, "load_staging_item", lambda *_a, **_k: {"title": "ok"}
        )

        # base64 for b"x" — valid, so the 400 can only come from the extension check.
        body = intel_mod.CoverImageUploadRequest(
            cover_image_base64="eA==", cover_image_filename="payload.py"
        )
        with pytest.raises(HTTPException) as exc:
            await intel_mod.upload_cover_image(type="news", item_id=LEGIT, request=body)

        assert exc.value.status_code == 400
        assert ".py" in str(exc.value.detail)
        assert not (tmp_path / "news" / "covers" / f"{LEGIT}.py").exists()

    @pytest.mark.asyncio
    async def test_innocence_a_real_upload_still_writes_its_image(
        self, tmp_path, monkeypatch
    ) -> None:
        """The guard must not trade a traversal for an outage."""
        _redirect_staging_root(monkeypatch, tmp_path)
        saved: dict = {}
        monkeypatch.setattr(
            intel_mod.staging_service, "load_staging_item", lambda *_a, **_k: {"title": "ok"}
        )
        monkeypatch.setattr(
            intel_mod.staging_service,
            "save_staging_item",
            lambda _t, _i, data: saved.update(data),
        )

        body = intel_mod.CoverImageUploadRequest(
            cover_image_base64="eA==", cover_image_filename="hero.PNG"
        )
        result = await intel_mod.upload_cover_image(type="news", item_id=LEGIT, request=body)

        assert result["success"] is True
        written = tmp_path / "news" / "covers" / f"{LEGIT}.png"
        assert written.read_bytes() == b"x"
        assert saved["cover_image"].endswith(f"{LEGIT}.png")

    @pytest.mark.asyncio
    async def test_innocence_a_legitimate_id_gets_past_the_guard_to_the_lookup(
        self, tmp_path, monkeypatch
    ) -> None:
        """404, not 400: the guard is not what stops an ordinary miss."""
        _redirect_staging_root(monkeypatch, tmp_path)
        body = intel_mod.CoverImageUploadRequest(cover_image_base64="eA==")
        with pytest.raises(HTTPException) as exc:
            await intel_mod.upload_cover_image(type="news", item_id=LEGIT, request=body)
        assert exc.value.status_code == 404


class TestTelegramIntelCallback:
    """`handle_intel_callback` — telegram_webhook.py, the least-protected sink."""

    @staticmethod
    def _callback(item_id: str) -> dict:
        return {
            "id": "cb-1",
            "data": f"intel:approve:news:{item_id}",
            "from": {"id": 7, "first_name": "Probe"},
            "message": {"chat": {"id": 1}, "message_id": 2},
        }

    @pytest.mark.asyncio
    async def test_guilt_a_traversal_id_never_reaches_the_status_file(
        self, tmp_path, monkeypatch
    ) -> None:
        _redirect_pending_root(monkeypatch, tmp_path)
        answered: list = []
        monkeypatch.setattr(
            webhook_mod.telegram_bot,
            "answer_callback_query",
            lambda *a, **k: answered.append((a, k)),
        )
        item_id, target = _escape_target(tmp_path, tmp_path, "zz-webhook-never-exists", ".json")

        handled = await webhook_mod.handle_intel_callback(self._callback(item_id))

        assert handled is False
        assert not target.exists(), f"the guard let a write escape to {target}"
        assert answered == []

    @pytest.mark.asyncio
    async def test_innocence_a_legitimate_id_reaches_the_lookup(
        self, tmp_path, monkeypatch
    ) -> None:
        """
        A well-formed id for an absent item must still be HANDLED (True) and get the
        "not found or already processed" answer — that path is downstream of the guard.
        """
        _redirect_pending_root(monkeypatch, tmp_path)
        answered: list = []

        async def _answer(callback_id, text=None, show_alert=False):
            answered.append(text)

        monkeypatch.setattr(webhook_mod.telegram_bot, "answer_callback_query", _answer)

        handled = await webhook_mod.handle_intel_callback(self._callback(LEGIT))

        assert handled is True
        assert answered and "not found" in answered[0].lower()

    @pytest.mark.asyncio
    async def test_innocence_a_non_intel_callback_is_still_declined_the_same_way(
        self, tmp_path, monkeypatch
    ) -> None:
        """The new `return False` must not become the only way to leave this function."""
        _redirect_pending_root(monkeypatch, tmp_path)
        assert await webhook_mod.handle_intel_callback({"id": "x", "data": "other:thing"}) is False


class TestPublishStagingItem:
    """`_publish_staging_item` — the single funnel-in for both publish callers."""

    @pytest.mark.asyncio
    async def test_guilt_a_traversal_id_is_refused_at_the_funnel(
        self, tmp_path, monkeypatch
    ) -> None:
        _redirect_staging_root(monkeypatch, tmp_path)
        with pytest.raises(HTTPException) as exc:
            await scraper_mod._publish_staging_item(
                type="news", item_id=TRAVERSAL, body=None, request=None, actor="test"
            )
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_guilt_the_internal_telegram_caller_is_funnelled_through_it_too(
        self, tmp_path, monkeypatch
    ) -> None:
        """
        The quorum path calls `publish_staging_item_internal`, not the HTTP endpoint.
        Guarding only the endpoint would have left the auth-exempt caller open — the
        exact shape of scar #424.
        """
        _redirect_staging_root(monkeypatch, tmp_path)
        with pytest.raises(HTTPException) as exc:
            await scraper_mod.publish_staging_item_internal(
                "news", TRAVERSAL, actor="telegram:quorum:2"
            )
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_innocence_a_legitimate_absent_id_still_404s(self, tmp_path, monkeypatch) -> None:
        _redirect_staging_root(monkeypatch, tmp_path)
        with pytest.raises(HTTPException) as exc:
            await scraper_mod._publish_staging_item(
                type="news", item_id=LEGIT, body=None, request=None, actor="test"
            )
        assert exc.value.status_code == 404


class TestScraperApiArticleIdRoutes:
    """
    `apps/bali-intel-scraper/api/main.py` — five routes, a DIFFERENT app.

    Structural pin rather than a behavioural test, deliberately and with the limit
    stated: that app's own suite (`apps/bali-intel-scraper/tests/`) is executed by no
    workflow in `.github/workflows/`, and its one test file `importorskip`s an archived
    module — a behavioural test placed there would be armed at nothing (W81). This file
    runs inside `pytest backend/tests/`, which `tests.yml` does execute, so the pin
    lives here and reads the other app's source from disk.

    It walks the AST rather than grepping: a comment mentioning the validator cannot
    satisfy it, only a call as the first statement of each route can.
    """

    # ALL FIVE routes in that file that join `article_id` into a path — not just the
    # two the triage named. The class sweep found the three approval routes only AFTER
    # the two preview ones were already cured; curing 2 of 5 and calling the file done
    # is W107, it only moves which route dies in silence.
    ROUTES = (
        "get_preview",
        "upload_preview",
        "approve_article",
        "reject_article",
        "get_approval_status",
    )

    @pytest.fixture(scope="class")
    def scraper_api_source(self) -> str:
        # backend/tests/unit/routers/<this> → repo root is 6 parents up.
        root = Path(__file__).resolve().parents[6]
        path = root / "apps" / "bali-intel-scraper" / "api" / "main.py"
        assert path.exists(), f"scraper api moved; re-anchor this pin (looked at {path})"
        return path.read_text()

    @pytest.mark.parametrize("route", ROUTES)
    def test_each_route_validates_before_touching_the_path(
        self, scraper_api_source: str, route: str
    ) -> None:
        tree = ast.parse(scraper_api_source)
        fn = next(
            (
                n
                for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == route
            ),
            None,
        )
        assert fn is not None, f"{route} disappeared from the scraper api"

        body = [
            s
            for s in fn.body
            if not isinstance(s, ast.Expr) or not isinstance(s.value, ast.Constant)
        ]
        first = body[0] if body else None
        assert isinstance(first, ast.Expr), f"{route}'s first statement is not a call"
        call = first.value
        assert isinstance(call, ast.Call)
        assert getattr(call.func, "id", None) == "_validate_article_id", (
            f"{route} must validate article_id BEFORE any path is built"
        )

        # The callee NAME is not enough — `_validate_article_id("constant")` would
        # satisfy it while the route still builds its path from the caller's value.
        # Assert the ARGUMENT is the same expression the route goes on to join:
        # the bare `article_id` parameter, or `request.article_id` for the body route.
        # (Raised by the cross-family reviewer against the first version of this pin.)
        assert len(call.args) == 1, f"{route}: validator called with {len(call.args)} args"
        arg = call.args[0]
        if isinstance(arg, ast.Attribute):
            actual = f"{getattr(arg.value, 'id', '?')}.{arg.attr}"
        else:
            actual = getattr(arg, "id", "<not a name>")
        assert actual in ("article_id", "request.article_id"), (
            f"{route} validates `{actual}`, which is not the value it builds its path from"
        )

    def test_the_duplicated_regex_still_matches_the_one_it_was_copied_from(
        self, scraper_api_source: str
    ) -> None:
        """
        Two apps, two processes, nothing to import — so the pattern is duplicated on
        purpose. A duplicate nothing compares is a duplicate that drifts.
        """
        from backend.app.routers.preview import _SAFE_ARTICLE_ID as backend_rag_pattern

        found = re.search(r'_SAFE_ARTICLE_ID = re\.compile\(r"([^"]+)"\)', scraper_api_source)
        assert found, "scraper api lost its _SAFE_ARTICLE_ID definition"
        assert found.group(1) == backend_rag_pattern.pattern

    def test_the_length_bound_is_duplicated_too(self, scraper_api_source: str) -> None:
        """The regex alone is unbounded; the 128 cap is the other half of the guard."""
        assert "len(article_id) > 128" in scraper_api_source


class TestApprovalServiceVotingStatusWrite:
    """
    `IntelApprovalService._save_voting_status` — the WRITE that CREATES the file the
    Telegram callback later reads and rewrites.

    Found by the class sweep, not by the triage and not by CodeQL. Its endpoint
    (`POST /api/intel/staging/approve/{type}/{item_id}`) is defended today only by
    `load_staging_item` returning None upstream, which is the same remote,
    read-contract-shaped defense as the publish path.
    """

    def test_guilt_a_traversal_id_writes_nothing(self, tmp_path, monkeypatch) -> None:
        from backend.services.intel.intel_approval_service import IntelApprovalService

        # __init__ resolves AND mkdirs the pending dir, so redirect first (W96).
        _redirect_pending_root(monkeypatch, tmp_path)
        svc = IntelApprovalService()
        assert svc.pending_intel_path == Path(tmp_path)
        item_id, target = _escape_target(tmp_path, tmp_path, "zz-voting-never-exists", ".json")

        with pytest.raises(ValueError):
            svc._save_voting_status(item_id, "news", {"title": "x"}, None, None)

        assert not target.exists(), f"the guard let a write escape to {target}"

    def test_innocence_a_legitimate_id_still_writes_its_status(self, tmp_path, monkeypatch) -> None:
        from backend.services.intel.intel_approval_service import IntelApprovalService

        _redirect_pending_root(monkeypatch, tmp_path)
        svc = IntelApprovalService()

        svc._save_voting_status(LEGIT, "news", {"title": "ok"}, None, None)

        written = tmp_path / f"{LEGIT}.json"
        assert written.exists()
        assert json.loads(written.read_text())["item_id"] == LEGIT
