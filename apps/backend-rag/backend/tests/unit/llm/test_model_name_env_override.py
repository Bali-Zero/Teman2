"""The model slug is a deploy-time knob, and a typo must not take prod down.

`PRIMARY_MODEL_NAME` existed as a Fly secret with zero readers repo-wide, so
the model behind `rag.gateway.chat` — 78% of the LLM bill and the path that
answers clients — could only be changed by editing a constant and shipping.
Wiring it means a bad value is now one `fly secrets set` away, and an unknown
slug 404s every call: the guard has to be as real as the knob.

Guilt: a slug outside the allowlist is refused and the default survives.
Innocence: a legitimate switch goes through, and the three knobs stay separate
— rolling back the web path must not roll back the channels.
"""

import importlib

import pytest


def _reload(monkeypatch, **env):
    """Re-import config under a chosen environment.

    The values are class attributes evaluated at import, which is what makes
    them stable for a process's lifetime — so the only honest way to test the
    override is to actually re-import.
    """
    for k in ("PRIMARY_MODEL_NAME", "FALLBACK_MODEL_NAME", "CHANNEL_MODEL_NAME"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import backend.llm.config as cfg

    return importlib.reload(cfg)


class TestGuilt:
    def test_an_unknown_slug_is_refused_and_the_default_survives(self, monkeypatch):
        cfg = _reload(monkeypatch, PRIMARY_MODEL_NAME="gemini-9.9-turbo-ultra")
        assert cfg.ModelName.PRIMARY == "gemini-3.5-flash"

    def test_a_typo_of_a_real_slug_is_still_refused(self, monkeypatch):
        # The realistic accident: a transposed character in a secret. It must
        # not reach the API, where it becomes a 404 on every call.
        cfg = _reload(monkeypatch, PRIMARY_MODEL_NAME="gemini-2.5-falsh")
        assert cfg.ModelName.PRIMARY == "gemini-3.5-flash"

    def test_the_refusal_is_logged_loudly_enough_to_find(self, monkeypatch, caplog):
        with caplog.at_level("ERROR"):
            _reload(monkeypatch, PRIMARY_MODEL_NAME="not-a-model")
        # getMessage() — NOT `.message`, which is only populated once something
        # has formatted the record, and NOT `.message % .args`, which
        # double-applies the args and raises.
        joined = " ".join(r.getMessage() for r in caplog.records)
        assert "PRIMARY_MODEL_NAME" in joined
        assert "not-a-model" in joined

    def test_whitespace_only_is_treated_as_unset_not_as_a_slug(self, monkeypatch):
        cfg = _reload(monkeypatch, PRIMARY_MODEL_NAME="   ")
        assert cfg.ModelName.PRIMARY == "gemini-3.5-flash"


class TestInnocence:
    def test_a_legitimate_switch_actually_takes_effect(self, monkeypatch):
        # If this ever fails the knob is decorative — the whole point is that
        # the cheap seat can be selected without a code change.
        cfg = _reload(monkeypatch, PRIMARY_MODEL_NAME="gemini-2.5-flash")
        assert cfg.ModelName.PRIMARY == "gemini-2.5-flash"

    def test_unset_environment_reproduces_the_historical_constants(self, monkeypatch):
        cfg = _reload(monkeypatch)
        assert cfg.ModelName.PRIMARY == "gemini-3.5-flash"
        assert cfg.ModelName.FALLBACK == "gemini-2.5-flash"
        assert cfg.ModelName.CHANNEL == "gemini-3.5-flash"

    def test_surrounding_whitespace_in_a_secret_does_not_defeat_a_valid_slug(self, monkeypatch):
        # Fly secrets set from a shell routinely carry a trailing newline.
        cfg = _reload(monkeypatch, PRIMARY_MODEL_NAME=" gemini-2.5-flash\n")
        assert cfg.ModelName.PRIMARY == "gemini-2.5-flash"


class TestKnobsAreSeparate:
    """Rolling back one surface must not roll back another."""

    def test_moving_the_rag_path_leaves_the_channels_alone(self, monkeypatch):
        cfg = _reload(monkeypatch, PRIMARY_MODEL_NAME="gemini-2.5-flash")
        assert cfg.ModelName.PRIMARY == "gemini-2.5-flash"
        assert cfg.ModelName.CHANNEL == "gemini-3.5-flash"

    def test_moving_the_channels_leaves_the_rag_path_alone(self, monkeypatch):
        cfg = _reload(monkeypatch, CHANNEL_MODEL_NAME="gemini-2.5-flash")
        assert cfg.ModelName.CHANNEL == "gemini-2.5-flash"
        assert cfg.ModelName.PRIMARY == "gemini-3.5-flash"

    def test_the_fallback_is_its_own_knob_too(self, monkeypatch):
        cfg = _reload(monkeypatch, FALLBACK_MODEL_NAME="gemini-2.0-flash")
        assert cfg.ModelName.FALLBACK == "gemini-2.0-flash"
        assert cfg.ModelName.PRIMARY == "gemini-3.5-flash"


class TestAllowlist:
    @pytest.mark.parametrize(
        "slug",
        ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-flash-lite"],
    )
    def test_every_slug_we_actually_route_to_is_admitted(self, monkeypatch, slug):
        cfg = _reload(monkeypatch, PRIMARY_MODEL_NAME=slug)
        assert cfg.ModelName.PRIMARY == slug

    def test_the_defaults_are_themselves_inside_the_allowlist(self, monkeypatch):
        # A default outside its own allowlist would mean the guard rejects the
        # very value it falls back to — self-consistency, cheap to pin.
        cfg = _reload(monkeypatch)
        for value in (cfg.ModelName.PRIMARY, cfg.ModelName.FALLBACK, cfg.ModelName.CHANNEL):
            assert value in cfg.KNOWN_GEMINI_MODELS


@pytest.fixture(autouse=True)
def _restore_config_module():
    """Leave the module as the rest of the suite expects to find it (W96)."""
    yield
    import backend.llm.config as cfg

    importlib.reload(cfg)
