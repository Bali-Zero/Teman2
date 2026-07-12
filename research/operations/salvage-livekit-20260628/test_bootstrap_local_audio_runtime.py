from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_bootstrap_module() -> ModuleType:
    backend_root = Path(__file__).resolve().parents[4]
    script_path = backend_root / "scripts" / "bootstrap_local_audio_runtime.py"
    spec = importlib.util.spec_from_file_location("bootstrap_local_audio_runtime_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_pkuseg_copy_requires_complete_source(tmp_path: Path) -> None:
    module = _load_bootstrap_module()
    source = tmp_path / "source"
    source.mkdir()

    try:
        module.copy_pkuseg_assets(source_dir=source, cache_dir=tmp_path / "cache")
    except RuntimeError as exc:
        assert "source is incomplete" in str(exc)
    else:
        raise AssertionError("expected incomplete pkuseg source to fail")


def test_pkuseg_copy_provisions_required_files(tmp_path: Path) -> None:
    module = _load_bootstrap_module()
    source = tmp_path / "source"
    cache = tmp_path / "cache"
    for relative in module.PKUSEG_REQUIRED_FILES:
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"asset")

    module.copy_pkuseg_assets(source_dir=source, cache_dir=cache)

    assert module.pkuseg_missing_files(cache) == []


def test_chatterbox_patch_adds_v3_selector_to_known_legacy_runtime(tmp_path: Path) -> None:
    module = _load_bootstrap_module()
    fixture = tmp_path / "mtl_tts.py"
    fixture.write_text(
        '''from pathlib import Path
import os
import torch

REPO_ID = "ResembleAI/chatterbox"

class ChatterboxMultilingualTTS:
    @classmethod
    def from_local(cls, ckpt_dir, device) -> 'ChatterboxMultilingualTTS':
        ckpt_dir = Path(ckpt_dir)

        # Always load to CPU first for non-CUDA devices to handle CUDA-saved models
        if device in ["cpu", "mps"]:
            map_location = torch.device('cpu')
        else:
            map_location = None

        ve = VoiceEncoder()
        ve.load_state_dict(
            torch.load(ckpt_dir / "ve.pt", map_location=map_location, weights_only=True)
        )
        ve.to(device).eval()

        t3 = T3(T3Config.multilingual())
        t3_state = load_safetensors(ckpt_dir / "t3_mtl23ls_v2.safetensors")
        if "model" in t3_state.keys():
            t3_state = t3_state["model"][0]
        t3.load_state_dict(t3_state)
        t3.to(device).eval()

        s3gen = S3Gen()
        s3gen.load_state_dict(
            torch.load(ckpt_dir / "s3gen.pt", map_location=map_location, weights_only=True)
        )
        s3gen.to(device).eval()

        tokenizer = MTLTokenizer(
            str(ckpt_dir / "grapheme_mtl_merged_expanded_v1.json")
        )

        conds = None
        if (builtin_voice := ckpt_dir / "conds.pt").exists():
            conds = Conditionals.load(builtin_voice, map_location=map_location).to(device)

        return cls(t3, s3gen, ve, tokenizer, device, conds=conds)

    @classmethod
    def from_pretrained(cls, device: torch.device) -> 'ChatterboxMultilingualTTS':
        # Check if MPS is available on macOS
        if device == "mps" and not torch.backends.mps.is_available():
            if not torch.backends.mps.is_built():
                print("MPS not available because the current PyTorch install was not built with MPS enabled.")
            else:
                print("MPS not available because the current MacOS version is not 12.3+ and/or you do not have an MPS-enabled device on this machine.")
            device = "cpu"

        ckpt_dir = Path(
            snapshot_download(
                repo_id=REPO_ID,
                repo_type="model",
                revision="main",
                allow_patterns=["ve.pt", "t3_mtl23ls_v2.safetensors", "s3gen.pt", "grapheme_mtl_merged_expanded_v1.json", "conds.pt", "Cangjie5_TC.json"],
                token=os.getenv("HF_TOKEN"),
            )
        )
        return cls.from_local(ckpt_dir, device)
''',
    )

    assert module.apply_chatterbox_v3_patch(fixture) is True
    patched = fixture.read_text()

    assert '"v3": "t3_mtl23ls_v3.safetensors"' in patched
    assert "t3_model: str | None = None" in patched
    assert "load_safetensors(ckpt_dir / t3_model)" in patched
    assert fixture.with_suffix(".py.before-nuzantara-v3").exists()
