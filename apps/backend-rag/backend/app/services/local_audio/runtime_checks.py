"""Shared static checks for the local audio runtime."""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass, field
from pathlib import Path

VOICE_RUNTIME_HOSTS = frozenset({"Nuzantara", "Mini-Pro2"})
MIN_WHISPER_MODEL_BYTES = 100 * 1024 * 1024
MIN_CHATTERBOX_WEIGHT_BYTES = 1024 * 1024
MIN_CHATTERBOX_JSON_BYTES = 128

BASE_REQUIRED_CHATTERBOX_CHECKPOINT_FILES = (
    "ve.pt",
    "s3gen.pt",
    "grapheme_mtl_merged_expanded_v1.json",
)
CHATTERBOX_T3_MODEL_FILES = {
    "v2": "t3_mtl23ls_v2.safetensors",
    "t3_mtl23ls_v2": "t3_mtl23ls_v2.safetensors",
    "v3": "t3_mtl23ls_v3.safetensors",
    "t3_mtl23ls_v3": "t3_mtl23ls_v3.safetensors",
}


@dataclass(frozen=True)
class LocalAudioCheckResult:
    ok: bool
    detail: str
    metadata: dict[str, str | int | float | bool | None] = field(default_factory=dict)


def normalize_hostname(hostname: str) -> str:
    return hostname.split(".", 1)[0]


def is_approved_voice_runtime_host(hostname: str | None = None) -> bool:
    return normalize_hostname(hostname or socket.gethostname()) in VOICE_RUNTIME_HOSTS


def check_whisper_binary_path(path: Path) -> LocalAudioCheckResult:
    binary_path = Path(path)
    if not binary_path.exists():
        return LocalAudioCheckResult(False, f"binary not found: {binary_path}")
    if not os.access(binary_path, os.X_OK):
        return LocalAudioCheckResult(False, f"binary not executable: {binary_path}")
    return LocalAudioCheckResult(True, f"whisper.cpp binary ready: {binary_path}")


def check_whisper_model_path(path: Path) -> LocalAudioCheckResult:
    model_path = Path(path)
    if not model_path.exists():
        return LocalAudioCheckResult(False, f"model not found: {model_path}")
    if not model_path.is_file():
        return LocalAudioCheckResult(False, f"model is not a file: {model_path}")
    if not os.access(model_path, os.R_OK):
        return LocalAudioCheckResult(False, f"model is not readable: {model_path}")
    try:
        size_bytes = model_path.stat().st_size
    except OSError as exc:
        return LocalAudioCheckResult(False, f"model stat failed: {type(exc).__name__}")
    if size_bytes < MIN_WHISPER_MODEL_BYTES:
        return LocalAudioCheckResult(
            False,
            "model file is too small to be large-v3-turbo",
            {
                "model_path": str(model_path),
                "size_bytes": size_bytes,
                "min_bytes": MIN_WHISPER_MODEL_BYTES,
            },
        )
    return LocalAudioCheckResult(
        True,
        f"whisper.cpp model readable: {model_path}",
        {"size_bytes": size_bytes},
    )


def check_whisper_model_quality(path: Path) -> LocalAudioCheckResult:
    model_path = Path(path)
    if "large-v3-turbo" not in str(model_path).lower():
        return LocalAudioCheckResult(
            False,
            "model is not the production large-v3-turbo choice",
            {"model_path": str(model_path)},
        )
    return LocalAudioCheckResult(
        True,
        "whisper large-v3-turbo selected",
        {"model_path": str(model_path)},
    )


def resolve_chatterbox_t3_model_file(t3_model: str) -> str:
    if t3_model in CHATTERBOX_T3_MODEL_FILES:
        return CHATTERBOX_T3_MODEL_FILES[t3_model]
    if t3_model.endswith(".safetensors"):
        return t3_model
    return CHATTERBOX_T3_MODEL_FILES["v3"]


def missing_chatterbox_checkpoint_files(model_path: Path, t3_model: str) -> list[str]:
    filenames = [
        *BASE_REQUIRED_CHATTERBOX_CHECKPOINT_FILES,
        resolve_chatterbox_t3_model_file(t3_model),
    ]
    return [filename for filename in filenames if not (Path(model_path) / filename).exists()]


def invalid_chatterbox_checkpoint_files(model_path: Path, t3_model: str) -> list[str]:
    filenames = [
        *BASE_REQUIRED_CHATTERBOX_CHECKPOINT_FILES,
        resolve_chatterbox_t3_model_file(t3_model),
    ]
    invalid: list[str] = []
    for filename in filenames:
        path = Path(model_path) / filename
        if not os.access(path, os.R_OK):
            invalid.append(f"{filename}: not readable")
            continue
        try:
            size_bytes = path.stat().st_size
        except OSError as exc:
            invalid.append(f"{filename}: stat failed: {type(exc).__name__}")
            continue
        min_bytes = chatterbox_checkpoint_min_bytes(filename)
        if size_bytes < min_bytes:
            invalid.append(f"{filename}: {size_bytes} bytes < {min_bytes}")
    return invalid


def chatterbox_checkpoint_min_bytes(filename: str) -> int:
    if filename.endswith((".pt", ".safetensors")):
        return MIN_CHATTERBOX_WEIGHT_BYTES
    if filename.endswith(".json"):
        return MIN_CHATTERBOX_JSON_BYTES
    return 1


__all__ = [
    "BASE_REQUIRED_CHATTERBOX_CHECKPOINT_FILES",
    "CHATTERBOX_T3_MODEL_FILES",
    "MIN_CHATTERBOX_JSON_BYTES",
    "MIN_CHATTERBOX_WEIGHT_BYTES",
    "MIN_WHISPER_MODEL_BYTES",
    "VOICE_RUNTIME_HOSTS",
    "LocalAudioCheckResult",
    "chatterbox_checkpoint_min_bytes",
    "check_whisper_binary_path",
    "check_whisper_model_path",
    "check_whisper_model_quality",
    "invalid_chatterbox_checkpoint_files",
    "is_approved_voice_runtime_host",
    "missing_chatterbox_checkpoint_files",
    "normalize_hostname",
    "resolve_chatterbox_t3_model_file",
]
