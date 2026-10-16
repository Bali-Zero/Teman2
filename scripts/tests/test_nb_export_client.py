"""Export client account binding, using only synthetic credentials."""
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import nb_export_corpus


def test_export_client_preserves_credential_owner_host_and_revision(monkeypatch):
    seen = {}
    tokens = SimpleNamespace(cookies={}, csrf_token="", session_id="", build_label="",
                             base_host="notebooklm.google.com", revision="r1")
    tokens.cookies = {"synthetic": "test"}

    def load(*, profile_name):
        seen["profile"] = profile_name
        return tokens

    def client(**kwargs):
        seen["client"] = kwargs
        return object()

    library = ModuleType("notebooklm_tools")
    library.NotebookLMClient = client
    core = ModuleType("notebooklm_tools.core")
    auth = ModuleType("notebooklm_tools.core.auth")
    auth.load_cached_tokens = load
    monkeypatch.setitem(sys.modules, "notebooklm_tools", library)
    monkeypatch.setitem(sys.modules, "notebooklm_tools.core", core)
    monkeypatch.setitem(sys.modules, "notebooklm_tools.core.auth", auth)
    monkeypatch.setenv("NLM_PROFILE", "research")

    assert nb_export_corpus._load_client() is not None
    assert seen["profile"] == "research"
    assert seen["client"]["profile_name"] == "research"
    assert seen["client"]["base_host"] == tokens.base_host
    assert seen["client"]["auth_revision"] == "r1"
