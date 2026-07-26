"""The companion mode's automatic path, after Zero's 2026-07-26 ruling.

Until now the companion fired a 15-second story on every published carousel.
The ruling made WR3 preordained and bounded it to `60 s ≤ duration ≤ 150 s` in
two language cuts, which happens to be WR3's own native envelope — declared
identically in brief-interpreter (out-of-range = hard_fail), shot-director
(60→8 clips … 150→19), script-editor (duration × 3 words) and the
pre-render-gatekeeper's credit ceilings.

The companion path sets `skip_brief_interpreter: true`, so it never met the
agent that enforces that range — which is the only reason a 15-second default
could live here unchallenged. These are the first tests this dispatcher has
ever had, so the corpus covers both signs deliberately:

GUILT     — the envelope bites the automatic path, and empty claim ids stop the
            episode instead of quietly downgrading it.
INNOCENCE — the opt-in short cut, which is deliberately outside the envelope,
            still runs; a stale flag from the WR2 side does not break a publish
            that already happened.
"""

from __future__ import annotations

import asyncio
import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

_SCRIPTS = Path(__file__).resolve().parents[1]
_REPO = _SCRIPTS.parent


def _load(name: str) -> Any:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def disp() -> Any:
    return _load("wr3_companion_dispatcher")


@pytest.fixture
def cfg(disp) -> Any:
    return disp.load_companion_mode_config()


@pytest.fixture
def payload() -> dict[str, Any]:
    """A payload that satisfies the contract, with claims present."""
    return {
        "slug": "2026-07-26-bkpm-paid-up-capital-2-5-mld",
        "slides_count": 10,
        "hero_image_path": "apps/war-room/output/carousel/x/slides/01.png",
        "primary_claim_ids": ["bkpm-5-2025-paid-up"],
        "domain": "company",
        "audience_segment": "founder",
        "brief_path": "apps/war-room/output/carousel/x/brief.json",
        "slides_path": "apps/war-room/output/carousel/x/slides.json",
    }


# ── The ruling, encoded ──────────────────────────────────────────────────


def test_the_automatic_sub_mode_is_the_episode_not_the_story(cfg) -> None:
    """Zero: "la wr3 è prestabilita e crea il video del carosello della wr2"."""
    assert cfg.default_sub_mode == "episode"
    assert cfg.sub_modes["story_15s"]["is_default"] is False


def test_the_episode_carries_the_ruled_envelope_and_two_cuts(cfg) -> None:
    ep = cfg.sub_modes["episode"]
    assert (ep["min_duration_s"], ep["max_duration_s"]) == (60, 150)
    assert ep["min_duration_s"] <= ep["target_duration_s"] <= ep["max_duration_s"]
    assert ep["language_cuts"] == ["en", "id"]
    # The path that spends without a human in the loop halts hard, unlike the
    # opt-in cuts — the gatekeeper contract already refuses to authorise spend.
    assert ep["cost"]["hard_halt_on_exceed"] is True
    assert cfg.sub_modes["story_15s"]["cost"]["hard_halt_on_exceed"] is False


def test_the_envelope_matches_wr3s_own_contract_not_a_local_opinion() -> None:
    """Anchor: [60,150] is read off brief-interpreter.yaml, never restated here.

    If someone widens or narrows WR3's native range, this fails rather than
    letting the companion lane drift into a second, quieter definition.
    """
    mode = yaml.safe_load(
        (_REPO / "docs/wr3/contracts/modes/companion-mode.yaml").read_text()
    )
    bi = (_REPO / "docs/wr3/contracts/brief-interpreter.yaml").read_text()
    lo = mode["duration_envelope"]["min_s"]
    hi = mode["duration_envelope"]["max_s"]
    assert f"[{lo},{hi}]" in bi, (
        f"companion declares [{lo},{hi}] but brief-interpreter.yaml does not — "
        "the companion lane must not carry its own duration range"
    )


# ── GUILT ────────────────────────────────────────────────────────────────


def test_an_out_of_envelope_automatic_sub_mode_is_refused(disp, cfg) -> None:
    """The whole point: skipping brief-interpreter no longer skips its gate."""
    broken = copy.deepcopy(cfg)
    object.__setattr__(
        broken,
        "sub_modes",
        {**cfg.sub_modes, "episode": {**cfg.sub_modes["episode"], "target_duration_s": 15}},
    )
    with pytest.raises(disp.CompanionDispatchError, match=r"outside WR3's \[60,150\]"):
        disp._assert_duration_envelope(broken, "episode")


def test_empty_claim_ids_skip_the_episode_instead_of_downgrading_it(
    disp, payload
) -> None:
    """0 of 23 WR2 briefs carry claim ids today.

    The old failure mode fell back to the 15-second cut, so an empty list would
    have quietly reinstated the format the ruling replaced — on every single
    episode, since the list is empty on every single one.
    """
    payload["primary_claim_ids"] = []
    briefs = asyncio.run(disp.dispatch_companion(payload, pg_conn=None, dry_run=True))
    assert briefs == []


def test_no_flags_at_all_still_produces_the_episode(disp, payload) -> None:
    """Preordained means preordained — there is no flag that turns it on."""
    briefs = asyncio.run(disp.dispatch_companion(payload, pg_conn=None, dry_run=True))
    assert [b["sub_mode"] for b in briefs] == ["episode"]


def test_the_brief_hands_the_envelope_and_the_cuts_downstream(disp, payload) -> None:
    briefs = asyncio.run(disp.dispatch_companion(payload, pg_conn=None, dry_run=True))
    ep = briefs[0]
    assert ep["min_duration_s"] == 60
    assert ep["max_duration_s"] == 150
    assert ep["language_cuts"] == ["en", "id"]
    assert ep["primary_claim_ids"] == ["bkpm-5-2025-paid-up"]


# ── INNOCENCE ────────────────────────────────────────────────────────────


def test_the_opt_in_short_cut_is_exempt_from_the_envelope(disp, cfg) -> None:
    """15 s is below WR3's minimum on purpose.

    It survives as a human's explicit choice; enforcing the envelope on it would
    delete a capability the ruling never asked to remove.
    """
    assert cfg.sub_modes["story_15s"]["target_duration_s"] == 15
    disp._assert_duration_envelope(cfg, "story_15s")  # must not raise


def test_companion_skip_still_stops_everything(disp, cfg) -> None:
    assert _load("wr3_companion_dispatcher")._resolve_requested_sub_modes(
        {"companion_skip": True}, cfg
    ) == []


def test_the_short_cut_is_reachable_behind_its_own_flag(disp, cfg) -> None:
    got = disp._resolve_requested_sub_modes({"companion_story": True}, cfg)
    assert got == ["episode", "story_15s"]


def test_a_stale_companion_expand_flag_is_ignored_not_fatal(disp, cfg) -> None:
    """`companion_expand` was the old opt-in for the long cut and is now gone.

    WR2 briefs are written by another pipeline. A stale key must not raise on a
    publish that has already happened — and must not add anything either.
    """
    got = disp._resolve_requested_sub_modes({"companion_expand": True}, cfg)
    assert got == ["episode"]


def test_the_backfill_override_reaches_the_dispatcher_at_all(
    disp, payload, tmp_path, monkeypatch, capsys
) -> None:
    """`--sub-modes` was a declared flag that nothing ever read.

    It parsed, it printed in `--help`, and `args.sub_modes` was referenced
    nowhere — so a backfill asking for one sub-mode silently got the brief's
    own resolution instead. Driven through `_cli` on purpose: asserting on
    `dispatch_companion(sub_modes_override=...)` alone would pass just as
    happily with the CLI still dropping the flag on the floor.
    """
    pj = tmp_path / "payload.json"
    pj.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "wr3_companion_dispatcher.py",
            "--wr2-slug",
            payload["slug"],
            "--payload-json",
            str(pj),
            "--sub-modes",
            "story_15s",
        ],
    )
    assert disp._cli() == 0
    briefs = json.loads(capsys.readouterr().out)
    assert [b["sub_mode"] for b in briefs] == ["story_15s"]


def test_an_unknown_override_is_refused_by_name(disp, payload) -> None:
    """Refuse where the operator can read it, not later as a KeyError."""
    with pytest.raises(disp.CompanionDispatchError, match="reel_60s"):
        asyncio.run(
            disp.dispatch_companion(
                payload, pg_conn=None, dry_run=True, sub_modes_override=["reel_60s"]
            )
        )


def test_an_override_cannot_smuggle_an_out_of_envelope_episode(disp, cfg, payload) -> None:
    """An override picks WHICH sub-modes run, never what they may be."""
    broken = copy.deepcopy(cfg)
    object.__setattr__(
        broken,
        "sub_modes",
        {**cfg.sub_modes, "episode": {**cfg.sub_modes["episode"], "target_duration_s": 15}},
    )
    with pytest.raises(disp.CompanionDispatchError, match=r"outside WR3's \[60,150\]"):
        asyncio.run(
            disp.dispatch_companion(
                payload,
                pg_conn=None,
                dry_run=True,
                config=broken,
                sub_modes_override=["episode"],
            )
        )


def test_a_config_without_an_envelope_still_dispatches(disp, cfg, payload) -> None:
    """Older/hand-written configs must degrade, not explode.

    Asserting "does not raise" would be satisfied by a check that silently
    stopped working; asserting the episode still comes out the other end is
    what actually distinguishes graceful degradation from a dead gate.
    """
    no_env = copy.deepcopy(cfg)
    object.__setattr__(no_env, "duration_envelope", {})
    assert no_env.duration_envelope == {}
    briefs = asyncio.run(
        disp.dispatch_companion(payload, pg_conn=None, dry_run=True, config=no_env)
    )
    assert [b["sub_mode"] for b in briefs] == ["episode"]
