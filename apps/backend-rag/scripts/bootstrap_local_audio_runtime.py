#!/usr/bin/env python3
"""Bootstrap checks for the Pro/Mini local audio runtime.

This script is intentionally local-only. It never downloads model assets; it
only verifies/copies already-provisioned local files and, when requested,
patches a legacy Chatterbox runtime so the v3 multilingual T3 checkpoint can be
selected explicitly.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import shutil
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

APPROVED_RUNTIME_HOST_ALIASES = {
    "nuzantara": "Nuzantara",
    "mini-pro2": "Mini-Pro2",
}
APPROVED_RUNTIME_HOSTS = frozenset(APPROVED_RUNTIME_HOST_ALIASES.values())
DEFAULT_PKUSEG_CACHE_DIR = Path.home() / ".pkuseg"
PKUSEG_REQUIRED_FILES = (
    "spacy_ontonotes.zip",
    "spacy_ontonotes/features.msgpack",
    "spacy_ontonotes/weights.npz",
)
CHATTERBOX_PATCH_MARKER = "MULTILINGUAL_T3_MODELS = {"


@dataclass
class BootstrapCheck:
    name: str
    status: str
    detail: str
    metadata: dict[str, str | int | bool | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "metadata": self.metadata,
        }


def normalize_hostname(hostname: str) -> str:
    short_hostname = hostname.split(".", 1)[0]
    return APPROVED_RUNTIME_HOST_ALIASES.get(short_hostname.lower(), short_hostname)


def is_approved_runtime_host(hostname: str | None = None) -> bool:
    return normalize_hostname(hostname or socket.gethostname()) in APPROVED_RUNTIME_HOSTS


def chatterbox_mtl_tts_path(module_name: str) -> Path:
    module = importlib.import_module(f"{module_name}.mtl_tts")
    module_file = getattr(module, "__file__", None)
    if not module_file:
        raise RuntimeError(f"{module_name}.mtl_tts has no filesystem path")
    return Path(module_file)


def chatterbox_supports_t3_model(module_name: str) -> bool:
    module = importlib.import_module(f"{module_name}.mtl_tts")
    from_local = module.ChatterboxMultilingualTTS.from_local
    try:
        parameters = inspect.signature(from_local).parameters
    except (TypeError, ValueError):
        return False
    return "t3_model" in parameters


def pkuseg_missing_files(cache_dir: Path) -> list[str]:
    return [relative for relative in PKUSEG_REQUIRED_FILES if not (cache_dir / relative).is_file()]


def copy_pkuseg_assets(*, source_dir: Path, cache_dir: Path) -> None:
    missing_from_source = pkuseg_missing_files(source_dir)
    if missing_from_source:
        raise RuntimeError(f"pkuseg source is incomplete: {missing_from_source[0]}")

    for relative in PKUSEG_REQUIRED_FILES:
        source = source_dir / relative
        target = cache_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def apply_chatterbox_v3_patch(path: Path, *, dry_run: bool = False) -> bool:
    text = path.read_text()
    if _already_patched(text):
        return False
    if not _looks_like_legacy_chatterbox(text):
        raise RuntimeError("Chatterbox runtime is neither v3-ready nor the known legacy layout")

    patched = _patch_chatterbox_source(text)
    if dry_run:
        return True

    backup_path = path.with_suffix(path.suffix + ".before-nuzantara-v3")
    if not backup_path.exists():
        backup_path.write_text(text)
    path.write_text(patched)
    return True


def _already_patched(text: str) -> bool:
    return CHATTERBOX_PATCH_MARKER in text and "t3_model: str | None = None" in text


def _looks_like_legacy_chatterbox(text: str) -> bool:
    return (
        "def from_local(cls, ckpt_dir, device)" in text
        and '"t3_mtl23ls_v2.safetensors"' in text
        and "allow_patterns=[\"ve.pt\", \"t3_mtl23ls_v2.safetensors\"" in text
    )


def _patch_chatterbox_source(text: str) -> str:
    constants = '''REPO_ID = "ResembleAI/chatterbox"
DEFAULT_MULTILINGUAL_T3_MODEL = "t3_mtl23ls_v2.safetensors"
MULTILINGUAL_T3_MODELS = {
    "v2": "t3_mtl23ls_v2.safetensors",
    "t3_mtl23ls_v2": "t3_mtl23ls_v2.safetensors",
    "v3": "t3_mtl23ls_v3.safetensors",
    "t3_mtl23ls_v3": "t3_mtl23ls_v3.safetensors",
}


def _resolve_multilingual_t3_model(t3_model: str | None) -> str:
    if t3_model is None:
        return DEFAULT_MULTILINGUAL_T3_MODEL
    if t3_model in MULTILINGUAL_T3_MODELS:
        return MULTILINGUAL_T3_MODELS[t3_model]
    if t3_model.endswith(".safetensors"):
        return t3_model
    raise ValueError(
        f"Unknown multilingual T3 model '{t3_model}'. "
        f"Expected one of {sorted(MULTILINGUAL_T3_MODELS)} or a .safetensors filename."
    )
'''
    text = text.replace('REPO_ID = "ResembleAI/chatterbox"', constants, 1)

    old_from_local = '''    @classmethod
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
'''
    new_from_local = '''    @classmethod
    def from_local(
        cls,
        ckpt_dir,
        device,
        t3_model: str | None = None,
    ) -> 'ChatterboxMultilingualTTS':
        ckpt_dir = Path(ckpt_dir)
        t3_model = _resolve_multilingual_t3_model(t3_model)

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
        t3_state = load_safetensors(ckpt_dir / t3_model)
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
'''
    text = _replace_required(text, old_from_local, new_from_local, "from_local")

    old_from_pretrained = '''    @classmethod
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
'''
    new_from_pretrained = '''    @classmethod
    def from_pretrained(
        cls,
        device: torch.device,
        t3_model: str | None = None,
    ) -> 'ChatterboxMultilingualTTS':
        # Check if MPS is available on macOS
        if device == "mps" and not torch.backends.mps.is_available():
            if not torch.backends.mps.is_built():
                print("MPS not available because the current PyTorch install was not built with MPS enabled.")
            else:
                print("MPS not available because the current MacOS version is not 12.3+ and/or you do not have an MPS-enabled device on this machine.")
            device = "cpu"

        t3_model = _resolve_multilingual_t3_model(t3_model)
        ckpt_dir = Path(
            snapshot_download(
                repo_id=REPO_ID,
                repo_type="model",
                revision="main",
                allow_patterns=["ve.pt", t3_model, "s3gen.pt", "grapheme_mtl_merged_expanded_v1.json", "conds.pt", "Cangjie5_TC.json"],
                token=os.getenv("HF_TOKEN"),
            )
        )
        return cls.from_local(ckpt_dir, device, t3_model=t3_model)
'''
    return _replace_required(text, old_from_pretrained, new_from_pretrained, "from_pretrained")


def _replace_required(text: str, old: str, new: str, label: str) -> str:
    patched = text.replace(old, new, 1)
    if patched == text:
        raise RuntimeError(f"unable to patch Chatterbox {label}; source layout changed")
    return patched


def build_report(args: argparse.Namespace) -> list[BootstrapCheck]:
    checks: list[BootstrapCheck] = []
    hostname = socket.gethostname()
    approved = is_approved_runtime_host(hostname)
    checks.append(
        BootstrapCheck(
            name="host_role",
            status="pass" if approved else "fail",
            detail=(
                f"{normalize_hostname(hostname)} is approved for local audio bootstrap"
                if approved
                else "local audio bootstrap is allowed only on Nuzantara/Mini-Pro2"
            ),
            metadata={"hostname": hostname, "normalized_hostname": normalize_hostname(hostname)},
        ),
    )
    if not approved:
        return checks

    cache_dir = Path(args.pkuseg_cache_dir).expanduser()
    source_dir = Path(args.pkuseg_source_dir).expanduser() if args.pkuseg_source_dir else None
    if source_dir is not None and pkuseg_missing_files(cache_dir):
        copy_pkuseg_assets(source_dir=source_dir, cache_dir=cache_dir)

    missing_pkuseg = pkuseg_missing_files(cache_dir)
    checks.append(
        BootstrapCheck(
            name="pkuseg_asset",
            status="fail" if missing_pkuseg else "pass",
            detail=(
                f"pkuseg asset cache incomplete: {missing_pkuseg[0]}"
                if missing_pkuseg
                else f"pkuseg asset cache ready: {cache_dir}"
            ),
            metadata={
                "cache_dir": str(cache_dir),
                "missing_count": len(missing_pkuseg),
                "missing_first": missing_pkuseg[0] if missing_pkuseg else None,
            },
        ),
    )

    try:
        mtl_path = chatterbox_mtl_tts_path(args.chatterbox_module)
        supports_v3_selector = chatterbox_supports_t3_model(args.chatterbox_module)
        patched = False
        if not supports_v3_selector and args.apply:
            patched = apply_chatterbox_v3_patch(mtl_path, dry_run=args.dry_run)
            importlib.invalidate_caches()
            supports_v3_selector = True
        checks.append(
            BootstrapCheck(
                name="chatterbox_v3_patch",
                status="pass" if supports_v3_selector else "fail",
                detail=(
                    "Chatterbox runtime supports t3_model selector"
                    if supports_v3_selector and not patched
                    else "Chatterbox v3 selector patch applied"
                    if patched
                    else "Chatterbox runtime is legacy; rerun with --apply"
                ),
                metadata={"module_path": str(mtl_path), "patched": patched},
            ),
        )
    except Exception as exc:
        checks.append(
            BootstrapCheck(
                name="chatterbox_v3_patch",
                status="fail",
                detail=f"Chatterbox runtime patch check failed: {type(exc).__name__}",
            ),
        )

    return checks


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap local audio runtime assets on Pro/Mini")
    parser.add_argument("--chatterbox-module", default="chatterbox")
    parser.add_argument("--pkuseg-cache-dir", default=str(DEFAULT_PKUSEG_CACHE_DIR))
    parser.add_argument("--pkuseg-source-dir")
    parser.add_argument("--apply", action="store_true", help="Patch legacy Chatterbox site-packages in-place")
    parser.add_argument("--dry-run", action="store_true", help="Validate patchability without writing files")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    checks = build_report(args)
    ok = all(check.status == "pass" for check in checks)
    payload: dict[str, Any] = {
        "ok": ok,
        "checks": [check.to_dict() for check in checks],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"local audio bootstrap: {'OK' if ok else 'FAILED'}")
        for check in checks:
            print(f"[{check.status.upper()}] {check.name}: {check.detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
